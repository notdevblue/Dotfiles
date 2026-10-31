#!/usr/bin/env python3
"""Compile approved composition to an explicit printable-character scene.

Offline dependencies: numpy, OpenCV, Pillow, and system Python with pycairo.
The resulting JSON contains only character cells, ink, and material labels.
The reference bitmap is never needed by the wallpaper runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
PAPER = '#0c101c'
COLS, ROWS = 520, 162
FONT_RATIO, BASELINE = 1.17, .88
GLYPHS = " .,:;'\"^/\\|_-=~+*#%@AVov[](){}"

CAIRO_HELPER = r'''
import cairo, json, sys
from pathlib import Path
mode, filename = sys.argv[1:3]
def font(ctx, height):
    ctx.select_font_face('Ubuntu Mono', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(height*1.17)
def glyph(ctx, char, x, y, w, h):
    advance=ctx.text_extents(char).x_advance
    ctx.move_to(x+(w-advance)/2, y+h*.88);ctx.show_text(char)
if mode=='atlas':
    w,h=86,115
    surf=cairo.ImageSurface(cairo.FORMAT_ARGB32,w*95,h)
    ctx=cairo.Context(surf);font(ctx,h);ctx.set_source_rgb(1,1,1)
    for i in range(95):glyph(ctx,chr(i+32),i*w,0,w,h)
    surf.write_to_png(filename)
else:
    data=json.loads(Path(filename).read_text());width,height=map(int,sys.argv[4:6])
    surf=cairo.ImageSurface(cairo.FORMAT_RGB24,width,height);ctx=cairo.Context(surf)
    def color(value):return tuple(int(value[i:i+2],16)/255 for i in (1,3,5))
    ctx.set_source_rgb(*color(data['paper']));ctx.paint()
    cw,ch=width/data['columns'],height/data['rows'];font(ctx,ch)
    for row,chars in enumerate(data['glyph_rows']):
        for col,char in enumerate(chars):
            if char==' ':continue
            paper=color(data['paper']);ink=color(data['ink_rows'][row][col]);gain=data.get('ink_gain',1)
            ctx.set_source_rgb(*(p+(c-p)*gain for p,c in zip(paper,ink)))
            glyph(ctx,char,col*cw,row*ch,cw,ch)
    surf.write_to_png(sys.argv[3])
'''


def cairo_call(*args):
    subprocess.run(['/usr/bin/python3', '-c', CAIRO_HELPER, *map(str,args)], check=True)


def clear_character(rgb, matte):
    """Extend genuine background across the separately composited portrait."""
    alpha=np.asarray(Image.open(matte).convert('RGBA'))[:,:,3]
    alpha=cv2.resize(alpha,(rgb.shape[1],rgb.shape[0]),interpolation=cv2.INTER_LINEAR)
    cw,ch=rgb.shape[1]/COLS,rgb.shape[0]/ROWS
    mask=cv2.dilate((alpha>8).astype(np.uint8),np.ones((int(ch*2)+1,int(cw*2)+1),np.uint8))>0
    out=rgb.copy()
    # Nearest valid pixels mirror a whole background strip, preserving texture;
    # interpolating individual edge colors would invent large flat regions.
    for y in range(len(out)):
        covered=np.flatnonzero(mask[y])
        if not len(covered):continue
        start,end=covered[0],covered[-1]+1
        for x in covered:
            if x-start < end-x or end>=out.shape[1]:
                donor=max(0,start-1-(x-start))
            else:
                donor=min(out.shape[1]-1,end+(end-1-x))
            if mask[y,donor]:donor=max(0,start-1)
            out[y,x]=rgb[y,donor]
    return out,mask


def materials(rgb):
    colors=cv2.resize(rgb,(COLS,ROWS),interpolation=cv2.INTER_AREA)
    labels=[]
    ridge=[(0,.31),(.09,.43),(.20,.42),(.34,.47),(.48,.41),(.59,.34),(.65,.40),(.74,.44),(.90,.40),(1,.19)]
    for row in range(ROWS):
        result=[]
        v=(row+.5)/ROWS
        for col in range(COLS):
            u=(col+.5)/COLS
            top=np.interp(u,[p[0] for p in ridge],[p[1] for p in ridge])
            rail=1.13-.50*u
            r,g,b=colors[row,col]
            warm=r>b*1.30 and g>b*1.15 and r>.22
            if v<top:kind='sky'
            elif v<.63:kind='forest' if v>top+.06 else 'mountain'
            elif v<.70:kind='village' if warm else 'forest'
            elif v<min(.91,rail):kind='lake'
            else:kind='foreground'
            result.append(kind)
        labels.append(result)
    return labels


def compile_scene(source,matte,output,preview):
    original=np.asarray(Image.open(source).convert('RGB'),dtype=np.float32)/255
    rgb,mask=clear_character(original,matte)
    paper=np.array([12,16,28],dtype=np.float32)/255
    # Each cell is fitted as paper + glyph alpha * ink amplitude. Fitting
    # stroke shapes, rather than cell averages, avoids a second density ramp.
    sw,sh=8,12
    small=cv2.resize(rgb,(COLS*sw,ROWS*sh),interpolation=cv2.INTER_AREA)
    pixels=small.reshape(ROWS,sh,COLS,sw,3).transpose(0,2,1,3,4).reshape(-1,sh*sw,3)
    residual=np.maximum(0,pixels-paper)
    luminance=residual@np.array([.2126,.7152,.0722],dtype=np.float32)
    with tempfile.TemporaryDirectory() as directory:
        atlas_path=Path(directory)/'atlas.png';cairo_call('atlas',atlas_path)
        atlas=np.asarray(Image.open(atlas_path).convert('RGBA'))[:,:,3].astype(np.float32)/255
        glyphs=np.stack([cv2.resize(atlas[:,(ord(char)-32)*86:(ord(char)-31)*86],(sw,sh),interpolation=cv2.INTER_AREA).ravel() for char in GLYPHS])
    norms=np.einsum('ij,ij->i',glyphs,glyphs)
    dot=luminance@glyphs.T
    amplitude=np.clip(dot/np.maximum(norms,1e-9),0,1)
    errors=(luminance*luminance).sum(axis=1)[:,None]-2*amplitude*dot+amplitude*amplitude*norms
    labels=materials(rgb)
    # A scene vocabulary keeps the same material grammar as the reference:
    # water uses horizontal strokes, sky small marks, trees branch strokes.
    vocabularies={'sky':" .,:;'\"+*",'lake':' .,:_-=~',
                  'mountain':' .,:;^/\\|v',
                  'forest':' .,:;^/\\|v*#',
                  'village':' .,:;^/\\|_-+*#o[]',
                  'foreground':' .,:;^/\\|_-+*#v'}
    flattened=np.array(labels).reshape(-1)
    for material,allowed in vocabularies.items():
        indices=np.flatnonzero(flattened==material)
        disallowed=np.array([char not in allowed for char in GLYPHS])
        errors[np.ix_(indices,np.flatnonzero(disallowed))]=np.inf
    choices=errors.argmin(axis=1)
    selected=glyphs[choices]
    ink_amplitude=np.einsum('ij,ijk->ik',selected,residual)/np.maximum(norms[choices,None],1e-9)
    # Source characters are not aligned to our new grid. Shape fitting alone
    # dims displaced snow strokes. Partially preserve each fitted cell's light
    # energy after selection; this changes ink, never the selected glyph.
    energy_amplitude=residual.sum(axis=1)/np.maximum(selected.sum(axis=1)[:,None],1e-9)
    ink_amplitude=.55*ink_amplitude+.45*energy_amplitude
    inks=np.clip(paper+ink_amplitude,0,1)
    chars=np.array(list(GLYPHS))[choices].reshape(ROWS,COLS)
    inkbytes=np.rint(inks*255).astype(np.uint8).reshape(ROWS,COLS,3)
    data={'version':1,'columns':COLS,'rows':ROWS,'paper':PAPER,
          'font_family':'Ubuntu Mono','font_weight':'bold',
          'font_size_to_cell_height':FONT_RATIO,'baseline_to_cell_height':BASELINE,'ink_gain':.76,
          'source_sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),
          'glyph_rows':[''.join(row) for row in chars],
          'ink_rows':[['#%02x%02x%02x'%tuple(color) for color in row] for row in inkbytes],
          'material_rows':labels}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(data,separators=(',',':'))+'\n')
    preview.parent.mkdir(parents=True,exist_ok=True)
    cairo_call('render',output,preview,1935,812)
    native=preview.with_name(preview.stem+'-native.png')
    cairo_call('render',output,native,3440,1440)
    # Evaluate only genuine background; character reconstruction is never a goal.
    rendered=np.asarray(Image.open(preview).convert('RGB'),dtype=np.float32)/255
    blurred_reference=cv2.GaussianBlur(original,(0,0),5)
    blurred_render=cv2.GaussianBlur(rendered,(0,0),5)
    mae=float(np.abs(blurred_reference-blurred_render)[~mask].mean())
    print(json.dumps({'columns':COLS,'rows':ROWS,'glyphs':len(GLYPHS),
                      'nonspace_cells':int((choices!=0).sum()),'blueprint_bytes':output.stat().st_size,
                      'background_blurred_rgb_mae':round(mae,4),'preview':str(preview),'native_preview':str(native)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'verification/concept-winter-lake.png')
    parser.add_argument('--matte',type=Path,default=ROOT/'assets/character-landscape-matte.png')
    parser.add_argument('--output',type=Path,default=ROOT/'assets/winter-lake-glyphs.json')
    parser.add_argument('--preview',type=Path,default=ROOT/'verification/reference-grid.png')
    args=parser.parse_args();compile_scene(args.source,args.matte,args.output,args.preview)
