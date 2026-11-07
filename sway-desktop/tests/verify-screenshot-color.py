#!/usr/bin/env python3
"""Exercise the real capture converter, layout renderer and PNG writer offline.
Usage: verify-screenshot-color.py GRIM_SOURCE GRIM_BUILD
No compositor, display, clipboard or user configuration is accessed.
"""
import os
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tempfile

source, build = map(lambda p: Path(p).resolve(), sys.argv[1:])
with tempfile.TemporaryDirectory(prefix='grim-color-check-') as name:
    temp = Path(name)
    unit = temp / 'check.c'
    unit.write_text(r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include "color.h"
#include "render.h"
#include "buffer.h"
#include "write_png.h"
static double pq(double nits) {
    double p=pow(nits/10000.,2610./16384.);
    return pow((3424./4096.+2413./128.*p)/(1.+2392./128.*p),2523./32.);
}
static uint32_t gray(double nits,int bits) {
    uint32_t v=lround(pq(nits)*((1<<bits)-1));
    return bits==10 ? v|(v<<10)|(v<<20) : v|(v<<8)|(v<<16);
}
static int channel(pixman_image_t *image,int x,int y,int shift) {
    return (((uint32_t *)((char *)pixman_image_get_data(image)+y*pixman_image_get_stride(image)))[x]>>shift)&255;
}
static void png(pixman_image_t *image,const char *name,bool raw) {
    FILE *f=fopen(name,"wb");assert(f);assert(!write_to_png_stream(image,f,6,raw));fclose(f);
}
int main(void) {
    uint32_t values[16];
    for(int i=0;i<16;i++)values[i]=gray(i==0?0:i==1?80:i==2?603:4000,10);
    pixman_image_t *image=pixman_image_create_bits(PIXMAN_x2r10g10b10,4,4,values,16);
    pixman_image_t *sdr=color_to_sdr(image,603);assert(sdr);
    assert(channel(sdr,0,0,0)==0);
    assert(abs(channel(sdr,1,0,0)-102)<=2);
    assert(channel(sdr,2,0,0)>channel(sdr,1,0,0));
    assert(channel(sdr,3,0,0)==255);
    png(sdr,"sdr.png",false);pixman_image_unref(sdr);
    for(int i=0;i<16;i++)values[i]=gray(603,10);
    sdr=color_to_sdr(image,603);assert(sdr);
    assert(channel(sdr,1,1,0)>=254);pixman_image_unref(sdr);
    // Adjacent XR30 values that would collapse to the same RGB8 sample must
    // remain distinct through PQ decoding before final SDR quantization.
    int preserved=0;
    for(int code=100;code<500;code++) {
        for(int i=0;i<16;i++) {uint32_t v=code+(i&1);values[i]=v|(v<<10)|(v<<20);}
        sdr=color_to_sdr(image,603);assert(sdr);
        if(lround(code*255./1023)==lround((code+1)*255./1023) &&
            channel(sdr,0,0,0)!=channel(sdr,1,0,0))preserved++;
        pixman_image_unref(sdr);
    }
    assert(preserved>10);pixman_image_unref(image);
    // A linear BT.709 primary converted to PQ BT.2020 returns the primary,
    // catching channel-order and primary conversion mistakes.
    float rgb[64];
    pixman_color_t red=color_ui_to_hdr((pixman_color_t){.red=32768,.alpha=65535},603);
    for(int i=0;i<16;i++){rgb[4*i]=red.red/65535.f;rgb[4*i+1]=red.green/65535.f;rgb[4*i+2]=red.blue/65535.f;rgb[4*i+3]=1;}
    image=pixman_image_create_bits(PIXMAN_rgba_float,4,4,(uint32_t *)rgb,64);
    sdr=color_to_sdr(image,603);assert(sdr);
    assert(abs(channel(sdr,1,1,16)-128)<=2 && channel(sdr,1,1,8)<=2 && channel(sdr,1,1,0)<=2);
    pixman_image_unref(sdr);pixman_image_unref(image);
    // Mixed encodings: scaled/rotated HDR output adjacent to unmodified SDR.
    uint32_t hdr[64], plain[16];
    for(int i=0;i<64;i++)hdr[i]=gray(603,8);
    for(int i=0;i<16;i++)plain[i]=0x224466;
    struct grim_state state={0};wl_list_init(&state.captures);
    struct grim_output outputs[2]={{.sdr_white=603},{0}};
    struct grim_buffer buffers[2]={
        {.data=hdr,.width=8,.height=8,.stride=32,.format=WL_SHM_FORMAT_XRGB8888},
        {.data=plain,.width=4,.height=4,.stride=16,.format=WL_SHM_FORMAT_XRGB8888}};
    struct grim_capture captures[2]={
        {.output=&outputs[0],.buffer=&buffers[0],.transform=WL_OUTPUT_TRANSFORM_270,.logical_geometry={0,0,4,4}},
        {.output=&outputs[1],.buffer=&buffers[1],.logical_geometry={4,0,4,4}}};
    for(int i=0;i<2;i++)wl_list_insert(&state.captures,&captures[i].link);
    struct grim_box box={0,0,8,4};image=render(&state,&box,1);assert(image);
    assert(channel(image,2,2,0)>=254);
    assert(channel(image,6,2,16)==0x22 && channel(image,6,2,8)==0x44 && channel(image,6,2,0)==0x66);
    pixman_image_unref(image);
    image=pixman_image_create_bits(PIXMAN_x8r8g8b8,16,8,NULL,0);
    assert(render_to(&state,&box,2,image,true));
    assert(channel(image,4,4,0)==(gray(603,8)&255)); // freeze keeps original PQ samples
    png(image,"raw.png",true);pixman_image_unref(image);
    puts("PASS: PQ/reference white, primary conversion, XR30 precision, mixed rotated/scaled output, raw freeze pixels");
}
''')
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
        'pixman-1', 'libavfilter', 'libavutil', 'wayland-client', 'libpng'], text=True))
    command = shlex.split(os.environ.get('CC', 'cc')) + [
        '-g', '-O1', '-DGRIM_LITTLE_ENDIAN=' + str(int(sys.byteorder == 'little')),
        '-I' + str(source / 'include'), '-I' + str(build / 'grim.p'), str(unit)]
    command += [str(source / file) for file in ('color.c', 'render.c', 'output-layout.c', 'box.c', 'write_png.c')]
    command += [str(build / 'grim.p/color-management-v1-protocol.c'), '-lm', '-o', str(temp / 'check')] + flags
    subprocess.run(command, check=True)
    subprocess.run([str(temp / 'check')], cwd=temp, check=True)
    def chunks(path):
        data = path.read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        result, offset = {}, 8
        while offset < len(data):
            size = struct.unpack('!I', data[offset:offset + 4])[0]
            result[data[offset + 4:offset + 8]] = data[offset + 8:offset + 8 + size]
            offset += 12 + size
        return result
    sdr, raw = chunks(temp / 'sdr.png'), chunks(temp / 'raw.png')
    assert sdr[b'sRGB'] == b'\0' and b'cICP' not in sdr
    assert raw[b'cICP'] == bytes((9, 16, 0, 1)) and b'sRGB' not in raw
    assert sdr[b'IHDR'][8] == raw[b'IHDR'][8] == 8
    print('PASS: default sRGB and explicit raw PQ/BT.2020 cICP PNG tags (both RGB8)')
