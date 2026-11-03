#!/usr/bin/env python3
"""Inspect compiled cursors; optionally exercise them in two private Wayland sessions.

The preview uses pixels decoded by libXcursor, never SVG sources. --native starts
only owned headless Sway instances and clean GTK/Qt fixtures. No live screenshot,
OS reboot, logout/login, or physical device reconnect is performed.
"""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import select
import shlex
import struct
import subprocess
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont, ImageChops
from verify_ascii_wallpaper import wallpaper_environment, wait_for
from verify_native import stop_group

ROOT = Path(__file__).resolve().parent
SIZES = (24, 32, 48, 64)
REQUIRED = ('default', 'left_ptr', 'pointer', 'hand2', 'text', 'xterm', 'move', 'fleur',
            'ew-resize', 'ns-resize', 'nwse-resize', 'nesw-resize', 'wait', 'watch',
            'progress', 'left_ptr_watch', 'not-allowed', 'crosshair', 'help', 'grab', 'grabbing')


# Stable human-readable representatives for equal-byte legacy/hash aliases.
DISPLAY_NAMES = ('default', 'pointer', 'text', 'vertical-text', 'move', 'ew-resize', 'ns-resize',
                 'nwse-resize', 'nesw-resize', 'n-resize', 'e-resize', 's-resize', 'w-resize',
                 'ne-resize', 'se-resize', 'sw-resize', 'nw-resize', 'col-resize', 'row-resize',
                 'wait', 'progress', 'not-allowed', 'no-drop', 'crosshair', 'cell', 'help',
                 'context-menu', 'grab', 'grabbing', 'copy', 'alias', 'zoom-in', 'zoom-out', 'none')


class XImage(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ('version', 'size', 'width', 'height', 'xhot', 'yhot', 'delay')] + [('pixels', C.POINTER(C.c_uint32))]


class XImages(C.Structure):
    _fields_ = [('nimage', C.c_int), ('images', C.POINTER(C.POINTER(XImage))), ('name', C.c_char_p)]


class Decoder:
    def __init__(self):
        self.lib = C.CDLL(ctypes.util.find_library('Xcursor'))
        self.lib.XcursorFilenameLoadAllImages.argtypes = [C.c_char_p]
        self.lib.XcursorFilenameLoadAllImages.restype = C.POINTER(XImages)
        self.lib.XcursorLibraryLoadImages.argtypes = [C.c_char_p, C.c_char_p, C.c_int]
        self.lib.XcursorLibraryLoadImages.restype = C.POINTER(XImages)
        self.lib.XcursorImagesDestroy.argtypes = [C.POINTER(XImages)]

    def decode(self, filename=None, name=None, theme=None, size=None):
        pointer = (self.lib.XcursorFilenameLoadAllImages(os.fsencode(filename)) if filename else
                   self.lib.XcursorLibraryLoadImages(name.encode(), theme.encode(), size))
        if not pointer:
            raise ValueError(f'libXcursor cannot load {filename or (theme, name, size)}')
        try:
            assert 0 < pointer.contents.nimage < 256
            frames = []
            for i in range(pointer.contents.nimage):
                item = pointer.contents.images[i].contents
                assert 0 < item.width <= 256 and 0 < item.height <= 256
                pixels = list(item.pixels[:item.width * item.height])
                frames.append({'size': item.size, 'width': item.width, 'height': item.height,
                               'hotspot': [item.xhot, item.yhot], 'delay_ms': item.delay,
                               'pixels': pixels})
            return frames
        finally:
            self.lib.XcursorImagesDestroy(pointer)


def rgba(frame):
    """Xcursor ARGB is premultiplied; Pillow composites straight RGBA."""
    values = []
    for pixel in frame['pixels']:
        a, r, g, b = (pixel >> 24, pixel >> 16 & 255, pixel >> 8 & 255, pixel & 255)
        values.append((min(255, (r * 255 + a // 2) // a) if a else 0,
                       min(255, (g * 255 + a // 2) // a) if a else 0,
                       min(255, (b * 255 + a // 2) // a) if a else 0, a))
    image = Image.new('RGBA', (frame['width'], frame['height']))
    image.putdata(values)
    return image


def inspect_theme(theme):
    cursor_dir = theme / 'cursors'
    if not (theme / 'index.theme').is_file() or not cursor_dir.is_dir():
        raise ValueError(f'Not a complete cursor theme: {theme}')
    decoder = Decoder()
    for name in REQUIRED:
        assert (cursor_dir / name).is_file(), f'Missing required cursor {name}'
    frames, aliases, evidence = {}, {}, {}
    for path in sorted(cursor_dir.iterdir()):
        target = path.resolve(strict=True)
        assert target.parent == cursor_dir.resolve(), f'Cursor escapes theme: {path}'
        if path.is_symlink():
            aliases[path.name] = target.name
            continue
        assert path.is_file(), f'Unexpected cursor entry {path}'
        data = path.read_bytes()
        assert len(data) >= 16 and data[:4] == b'Xcur', f'Not Xcursor binary: {path}'
        magic, header, version, count = struct.unpack_from('<4I', data)
        assert header >= 16 and version == 0x10000 and 0 < count <= 256
        assert header + count * 12 <= len(data)
        subtypes = []
        for i in range(count):
            kind, subtype, offset = struct.unpack_from('<3I', data, header + i * 12)
            assert kind == 0xfffd0002, f'Unexpected non-image chunk: {path}'
            assert offset + 36 <= len(data)
            length, chunk_kind, nominal, chunk_version, w, h, x, y, delay = struct.unpack_from('<9I', data, offset)
            assert length >= 36 and chunk_kind == kind and nominal == subtype and chunk_version == 1
            assert 0 < w <= 256 and 0 < h <= 256 and x < w and y < h
            assert offset + length + w * h * 4 <= len(data)
            subtypes.append(subtype)
        loaded = decoder.decode(filename=path)
        assert len(loaded) == count
        assert {f['size'] for f in loaded} == set(SIZES), f'Wrong nominal sizes: {path}'
        assert subtypes == [f['size'] for f in loaded]
        for item in loaded:
            size = item['size']
            assert (item['width'], item['height']) == (size, size), f'Unexpected canvas: {path}'
            assert item['hotspot'][0] < size and item['hotspot'][1] < size
            alphas = [p >> 24 for p in item['pixels']]
            if path.name in ('none', 'blank_cursor'):
                assert all(p == 0 for p in item['pixels']), f'Invisible cursor has visible pixels: {path}'
            else:
                assert min(alphas) == 0 and max(alphas) == 255, f'No opaque/transparent regions: {path}'
                assert any(0 < a < 255 for a in alphas), f'No antialiasing: {path}'
            assert all(max(p >> 16 & 255, p >> 8 & 255, p & 255) <= p >> 24 for p in item['pixels']), 'Not premultiplied ARGB'
        metadata = []
        for size in SIZES:
            selected = [f for f in loaded if f['size'] == size]
            if len(selected) > 1:
                assert all(10 <= f['delay_ms'] <= 1000 for f in selected)
                assert len({tuple(f['pixels']) for f in selected}) > 1, f'Static animation: {path}'
            else:
                assert selected[0]['delay_ms'] == 0
            assert len({tuple(f['hotspot']) for f in selected}) == 1, f'Animation hotspot moves: {path}'
            metadata.append({'size': size, 'frames': len(selected), 'hotspot': selected[0]['hotspot'],
                             'delays_ms': [f['delay_ms'] for f in selected]})
        frames[path.name] = loaded
        evidence[path.name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'images': metadata}
    # The installer manages bytes, so alias names may be identical regular files.
    # Identify those independently by content rather than importing builder aliases.
    groups = {}
    for name, entry in evidence.items():
        groups.setdefault(entry['sha256'], []).append(name)
    order = {name: i for i, name in enumerate(dict.fromkeys((*DISPLAY_NAMES, *REQUIRED)))}
    for group in groups.values():
        canonical = min(group, key=lambda n: (order.get(n, len(order)), n))
        for name in group:
            if name != canonical:
                aliases[name] = canonical
    for name in aliases:
        target = aliases[name]
        seen = {name}
        while target in aliases:
            assert target not in seen, f'Alias cycle: {name}'
            seen.add(target)
            target = aliases[target]
        aliases[name] = target
    # Resolve every alias through the native parser, including all animation frames.
    for name, target in aliases.items():
        assert decoder.decode(filename=cursor_dir / name) == frames[target]
    frames = {name: frames[name] for name in sorted(frames, key=lambda n: (order.get(n, len(order)), n)) if name not in aliases}
    for name in ('wait', 'progress'):
        actual = aliases.get(name, name)
        assert all(sum(f['size'] == size for f in frames[actual]) > 1 for size in SIZES), f'Expected animated {name}'
    return frames, {'files': evidence, 'aliases': aliases,
                    'alias_storage': {name: 'symlink' if (cursor_dir / name).is_symlink() else 'identical binary' for name in aliases},
                    'required_names': list(REQUIRED)}


def preview(frames, target):
    names = list(frames)
    width, row_height = 1290, 112
    image = Image.new('RGB', (width, 62 + row_height * len(names)), '#282429')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans.ttf', 13)
    draw.text((15, 10), 'Yuru Cursors / compiled Xcursor pixels decoded by libXcursor', fill='white', font=font)
    draw.text((15, 32), 'Native 24 / 32 / 48 / 64 px + nearest-neighbour 32 px enlarged 2x; first animation frame', fill='#cbc4ca', font=font)
    backgrounds = ('#1e191f', '#f4f1f1', '#808080')
    for row, name in enumerate(names):
        top = 62 + row * row_height
        draw.text((12, top + 44), name, fill='white', font=font)
        for group, background in enumerate(backgrounds):
            left = 185 + group * 365
            draw.rectangle((left, top, left + 355, top + 106), fill=background)
            for offset, size in enumerate(SIZES):
                frame = next(f for f in frames[name] if f['size'] == size)
                cursor = rgba(frame)
                x, y = left + 10 + offset * 67, top + 10
                image.paste(cursor, (x, y), cursor)
                draw.text((x, top + 84), str(size), font=font, fill='#b26480' if group == 0 else '#4c3c46')
            frame = next(f for f in frames[name] if f['size'] == 32)
            cursor = rgba(frame).resize((64, 64), Image.Resampling.NEAREST)
            image.paste(cursor, (left + 282, top + 10), cursor)
            draw.text((left + 282, top + 84), '2x', font=font, fill='#b26480' if group == 0 else '#4c3c46')
    image.save(target)


WAYLAND_PROBE = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <wayland-client.h>
#include <wayland-cursor.h>
static struct wl_shm *shm;
static void global(void *d, struct wl_registry *r, uint32_t n, const char *i, uint32_t v) {
  if (!strcmp(i,"wl_shm")) shm=wl_registry_bind(r,n,&wl_shm_interface,1);
}
static void removed(void *d,struct wl_registry *r,uint32_t n){}
static const struct wl_registry_listener listener={global,removed};
int main(int argc,char **argv) {
 struct wl_display *d=wl_display_connect(NULL);assert(d);
 struct wl_registry *r=wl_display_get_registry(d);wl_registry_add_listener(r,&listener,NULL);
 assert(wl_display_roundtrip(d)>=0);assert(shm);
 for(int s=24;s<=64;s=(s==24?32:s==32?48:s==48?64:65)) {
  struct wl_cursor_theme *t=wl_cursor_theme_load(argv[1],s,shm);assert(t);
  for(int n=2;n<argc;n++) {
   struct wl_cursor *c=wl_cursor_theme_get_cursor(t,argv[n]);assert(c&&c->image_count);
   for(unsigned int i=0;i<c->image_count;i++) {
    struct wl_cursor_image *im=c->images[i];
    assert(im->width==(unsigned)s&&im->height==(unsigned)s);
    assert(im->hotspot_x<im->width&&im->hotspot_y<im->height);
    assert(wl_cursor_image_get_buffer(im));
   }
   printf("%d %s %u\n",s,argv[n],c->image_count);
  }
  wl_cursor_theme_destroy(t);
 }
 assert(wl_display_roundtrip(d)>=0);wl_shm_destroy(shm);wl_registry_destroy(r);wl_display_disconnect(d);
 return 0;
}
'''
GTK_PROBE = r'''
import gi,sys
version=sys.argv[1];gi.require_version('Gtk',version)
from gi.repository import Gtk,Gdk,GLib
GLib.set_prgname('yuru-cursor-probe')
provider=Gtk.CssProvider();provider.load_from_data(b'window {background: #808080;}')
if version=='3.0':
 Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),provider,800)
 w=Gtk.Window();w.fullscreen();w.show_all()
 w.get_window().set_cursor(Gdk.Cursor.new_from_name(Gdk.Display.get_default(),'default'))
 print('ready',flush=True);Gtk.main()
else:
 app=Gtk.Application(application_id='org.yuru.CursorProbe')
 def start(app):
  Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,800)
  w=Gtk.ApplicationWindow(application=app);w.fullscreen();w.set_cursor_from_name('default');w.present()
  print('ready',flush=True)
 app.connect('activate',start);app.run([])
'''
QT_PROBE = r'''
#include <QApplication>
#include <QWidget>
#include <QPalette>
#include <QCursor>
#include <cstdio>
int main(int argc,char **argv){QApplication app(argc,argv);QWidget w;
 QPalette p;p.setColor(QPalette::Window,QColor(128,128,128));w.setPalette(p);w.setAutoFillBackground(true);
 w.setCursor(QCursor(Qt::ArrowCursor));w.showFullScreen();puts("ready");fflush(stdout);return app.exec();}
'''


def command(args, env=None, timeout=8):
    return subprocess.run(args, env=env, check=True, capture_output=True, text=True, timeout=timeout).stdout


def compile_probes(temporary):
    binaries = {}
    for name, source, packages, compiler in (
        ('lookup', WAYLAND_PROBE, ['wayland-client', 'wayland-cursor'], 'cc'),
        ('qt5', QT_PROBE, ['Qt5Widgets'], 'c++'), ('qt6', QT_PROBE, ['Qt6Widgets'], 'c++')):
        path = temporary / (name + ('.cpp' if compiler == 'c++' else '.c'))
        path.write_text(source)
        flags = shlex.split(command(['pkg-config', '--cflags', '--libs', *packages]))
        output = temporary / name
        command([compiler, '-fPIC', str(path), *flags, '-o', str(output)], timeout=30)
        binaries[name] = output
    protocol = ROOT / 'tests/wlr-virtual-pointer-unstable-v1.xml'
    for mode, filename in [('client-header', 'virtual-pointer.h'), ('private-code', 'virtual-pointer.c')]:
        command(['wayland-scanner', mode, str(protocol), str(temporary / filename)])
    pointer = temporary / 'pointer-device'
    command(['cc', '-I', str(temporary), str(ROOT / 'tests/ascii-pointer.c'),
             str(temporary / 'virtual-pointer.c'), '-lwayland-client', '-o', str(pointer)])
    binaries['pointer'] = pointer
    return binaries


def native_run(theme, frames, iteration, binaries):
    with tempfile.TemporaryDirectory(prefix='yuru-cursor-native-') as directory:
        temporary = Path(directory)
        env = wallpaper_environment(temporary)
        # Only this theme is exposed; no inherited default theme can satisfy tests.
        icons = temporary / 'icons'
        icons.mkdir()
        (icons / theme.name).symlink_to(theme, target_is_directory=True)
        env.update(XCURSOR_PATH=str(icons), XCURSOR_THEME=theme.name, XCURSOR_SIZE='32',
                   QT_QPA_PLATFORM='wayland', QT_WAYLAND_DISABLE_WINDOWDECORATION='1')
        for version in ('3.0', '4.0'):
            settings = Path(env['XDG_CONFIG_HOME']) / f'gtk-{version}/settings.ini'
            settings.parent.mkdir(parents=True)
            settings.write_text(f'[Settings]\ngtk-cursor-theme-name={theme.name}\ngtk-cursor-theme-size=32\n')
        config = temporary / 'sway.conf'
        config.write_text('xwayland disable\noutput HEADLESS-1 mode 800x600\nseat seat0 fallback true\n'
                          f'seat seat0 xcursor_theme {theme.name} 32\n')
        children, captures = [], {}
        with (temporary / 'process.log').open('w+') as log:
            try:
                server = subprocess.Popen(['sway', '-c', str(config)], env=env, stdout=log, stderr=log, start_new_session=True)
                children.append(server)
                def ready():
                    runtime = Path(env['XDG_RUNTIME_DIR'])
                    ipc = list(runtime.glob('sway-ipc.*.sock'))
                    displays = [p for p in runtime.glob('wayland-*') if not p.name.endswith('.lock')]
                    if not ipc or not displays:
                        return False
                    env.update(SWAYSOCK=str(ipc[0]), WAYLAND_DISPLAY=displays[0].name)
                    try:
                        return bool(command(['swaymsg', '-r', '-t', 'get_outputs'], env))
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                        return False
                wait_for(ready)
                pointer = subprocess.Popen([str(binaries['pointer'])], env=env, stdout=subprocess.PIPE, stderr=log, start_new_session=True)
                children.append(pointer)
                assert select.select([pointer.stdout], [], [], 3)[0] and pointer.stdout.readline().strip() == b'ready'
                lookups = command([str(binaries['lookup']), theme.name, *REQUIRED], env).splitlines()
                # Xcursor theme lookup is in a fresh process, avoiding process-global path caches.
                lookup_code = ('import sys;sys.path.insert(0,sys.argv[1]);from verify_cursors import Decoder,REQUIRED,SIZES;'
                               'from pathlib import Path;d=Decoder();'
                               'pairs=[(n,s) for n in REQUIRED for s in SIZES];'
                               'assert all(d.decode(name=n,theme=sys.argv[2],size=s)==[f for f in d.decode(filename=Path(sys.argv[3])/"cursors"/n) if f["size"]==s] for n,s in pairs);print("pass")')
                assert command(['/usr/bin/python', '-c', lookup_code, str(ROOT), theme.name, str(theme)], env).strip() == 'pass'
                default_path = theme / 'cursors/default'
                default_frames = Decoder().decode(filename=default_path)
                frame = next(f for f in default_frames if f['size'] == 32)
                expected = Image.new('RGBA', (32, 32), '#808080')
                expected.alpha_composite(rgba(frame))
                expected = expected.convert('RGB')
                for toolkit, args in (
                    ('gtk3', ['/usr/bin/python', '-c', GTK_PROBE, '3.0']),
                    ('gtk4', ['/usr/bin/python', '-c', GTK_PROBE, '4.0']),
                    ('qt5', [str(binaries['qt5'])]), ('qt6', [str(binaries['qt6'])])):
                    application = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=log, start_new_session=True)
                    children.append(application)
                    assert select.select([application.stdout], [], [], 5)[0], f'{toolkit} did not start'
                    assert application.stdout.readline().strip() == b'ready', f'{toolkit} fixture failed'
                    time.sleep(.35)
                    command(['swaymsg', '-r', '--', 'seat seat0 cursor set 400 300'], env)
                    command(['swaymsg', '-r', '--', 'seat seat0 cursor set 401 300'], env)
                    time.sleep(.2)
                    screenshot = temporary / f'{toolkit}.png'
                    command(['grim', '-c', '-o', 'HEADLESS-1', str(screenshot)], env)
                    image = Image.open(screenshot).convert('RGB')
                    x, y = 401 - frame['hotspot'][0], 300 - frame['hotspot'][1]
                    patch = image.crop((x, y, x + 32, y + 32))
                    extrema = ImageChops.difference(patch, expected).getextrema()
                    error = max(high for low, high in extrema)
                    if error > 2:
                        failure = ROOT / f'verification/cursors-native-{toolkit}-failed.png'
                        if failure.is_symlink():
                            raise RuntimeError(f'Refusing symlink output {failure}')
                        image.save(failure)
                        raise AssertionError(f'{toolkit} cursor differs from compiled default (max error {error}); {failure}')
                    assert application.poll() is None
                    captures[toolkit] = {'fresh_start': True, 'native_cursor_matches_compiled_default': True, 'cursor_name': 'default',
                                         'maximum_channel_error': error}
                    if iteration == 2 and toolkit == 'gtk3':
                        # Every toolkit paints the same fixture and pixels.
                        # Keep one representative capture rather than copies.
                        capture = ROOT / 'verification/cursors-native.png'
                        if capture.is_symlink():
                            raise RuntimeError(f'Refusing symlink output {capture}')
                        image.save(capture)
                    stop_group(application)
                    children.remove(application)
                return {'iteration': iteration, 'fresh_private_compositor': True,
                        'libwayland_cursor_names_at_all_sizes': len(lookups),
                        'fresh_libXcursor_theme_lookup': True, 'toolkits': captures}
            except BaseException:
                log.flush(); log.seek(0)
                print(log.read()[-6000:])
                raise
            finally:
                for child in reversed(children):
                    stop_group(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--theme-dir', type=Path, default=ROOT / 'build/cursors/Yuru-Cursors',
                        help='built or installed theme directory (contains index.theme and cursors/)')
    parser.add_argument('--native', action='store_true', help='restart private Sway and GTK3/GTK4/Qt5/Qt6 twice')
    args = parser.parse_args()
    theme = args.theme_dir.expanduser().resolve()
    frames, report = inspect_theme(theme)
    destination = ROOT / 'verification'
    destination.mkdir(exist_ok=True)
    if destination.is_symlink():
        raise RuntimeError('Refusing symlink verification directory')
    for path in [destination / 'cursors.png', destination / 'cursors.json']:
        if path.is_symlink():
            raise RuntimeError(f'Refusing symlink output {path}')
    preview(frames, destination / 'cursors.png')
    report.update(date=time.strftime('%Y-%m-%d'), theme_directory=str(theme),
                  scope='compiled files, independent binary structure and libXcursor decoder; native opt-in',
                  preview='cursors.png', native_capture='cursors-native.png' if args.native else None, native_runs=[],
                  not_tested=['OS reboot', 'logout/login', 'physical device reconnect', 'live desktop applications'])
    if args.native:
        with tempfile.TemporaryDirectory(prefix='yuru-cursor-probes-') as directory:
            binaries = compile_probes(Path(directory))
            report['native_runs'] = [native_run(theme, frames, i, binaries) for i in (1, 2)]
        report['scope'] += '; two fresh private CPU-only Sway sessions, native wl_shm buffers and fresh GTK3/GTK4/Qt5/Qt6 cursors'
    else:
        report['not_tested'].append('native Wayland/compositor/toolkit startup (requires --native)')
    (destination / 'cursors.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS compiled cursor validation: {len(frames)} files, {len(report["aliases"])} aliases')
    print(f'Preview: {destination / "cursors.png"}; evidence: {destination / "cursors.json"}')


if __name__ == '__main__':
    main()
