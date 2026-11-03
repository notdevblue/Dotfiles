#!/usr/bin/env python3
"""Build original Yuru SVG artwork into deterministic, premultiplied Xcursors.

``finalize(theme_dir)`` consumes the palette-rendered cursor template directory.
Requires rsvg-convert (librsvg) and Pillow. No display or xcursorgen is needed.
Geometry is expressed once in a 32px SVG viewBox; source_svg() exposes editable
SVG for previews. Xcursor encoding follows /usr/include/X11/Xcursor/Xcursor.h:
little-endian file header, image TOC, 36-byte image headers, ARGB32 pixels.
"""
from dataclasses import dataclass
from io import BytesIO
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess

from PIL import Image


THEME = 'Yuru-Cursors'
DEFAULT_SIZE = 24
SIZES = (24, 32, 48, 64)
IMAGE_TYPE = 0xFFFD0002

# Ordered contour, including a constant-width shaft with a perpendicular end.
# Keep these parts explicit: an overall bounding-box ratio alone cannot detect
# an oversized wing, a short exposed tail or two diverging shaft edges.
ARROW = {
    'tip': (4, 3),
    'heel': (4, 23),
    'notch': (9.5, 18),
    'tail_left': (15, 29),
    'tail_right': (18.6, 27.2),
    'neck': (14, 18),
    'head': (19, 18),
}


@dataclass(frozen=True)
class CursorSpec:
    hotspot: tuple[int, int]
    frames: int = 1
    delay: int = 0


CURSORS = {
    'default': CursorSpec(ARROW['tip']),
    'pointer': CursorSpec((13, 3)),
    'text': CursorSpec((16, 16)),
    'vertical-text': CursorSpec((16, 16)),
    'move': CursorSpec((16, 16)),
    'ew-resize': CursorSpec((16, 16)),
    'ns-resize': CursorSpec((16, 16)),
    'nwse-resize': CursorSpec((16, 16)),
    'nesw-resize': CursorSpec((16, 16)),
    'n-resize': CursorSpec((16, 4)),
    'e-resize': CursorSpec((28, 16)),
    's-resize': CursorSpec((16, 28)),
    'w-resize': CursorSpec((4, 16)),
    'ne-resize': CursorSpec((25, 7)),
    'se-resize': CursorSpec((25, 25)),
    'sw-resize': CursorSpec((7, 25)),
    'nw-resize': CursorSpec((7, 7)),
    'col-resize': CursorSpec((16, 16)),
    'row-resize': CursorSpec((16, 16)),
    'wait': CursorSpec((16, 16), 8, 90),
    'progress': CursorSpec(ARROW['tip'], 8, 90),
    'not-allowed': CursorSpec((16, 16)),
    'no-drop': CursorSpec(ARROW['tip']),
    'crosshair': CursorSpec((16, 16)),
    'cell': CursorSpec((16, 16)),
    'help': CursorSpec(ARROW['tip']),
    'context-menu': CursorSpec(ARROW['tip']),
    'grab': CursorSpec((16, 15)),
    'grabbing': CursorSpec((16, 15)),
    'copy': CursorSpec(ARROW['tip']),
    'alias': CursorSpec(ARROW['tip']),
    'zoom-in': CursorSpec((13, 13)),
    'zoom-out': CursorSpec((13, 13)),
    'none': CursorSpec((0, 0)),
}

# GTK/Qt/X11 names and legacy cursor hashes. Directional names have their own
# pointed artwork and tip hotspots; double-headed resizes retain a central hot spot.
_ALIAS_GROUPS = {
    'default': ('left_ptr', 'arrow', 'top_left_arrow', 'left-arrow', 'dnd-none'),
    'pointer': ('hand2', 'hand', 'pointing_hand', '9d800788f1b08800ae810202380a0822',
                'e29285e634086352946a0e7090d73106'),
    'text': ('xterm', 'ibeam'),
    'move': ('fleur', 'all-resize', 'all-scroll', 'size_all', 'dnd-move',
             '4498f0e0c1937ffe01fd06f973665830', '9081237383d90e509aa00f00170e968f'),
    'ew-resize': ('sb_h_double_arrow', 'h_double_arrow', 'size_hor', 'split_h',
                  '028006030e0e7ebffc7f7070c0600140', '14fef782d02440884392942c11205230'),
    'ns-resize': ('sb_v_double_arrow', 'v_double_arrow', 'size_ver', 'split_v',
                  '00008160000006810000408080010102', '2870a09082c103050810ffdffffe0204'),
    'nwse-resize': ('bd_double_arrow', 'size_fdiag', 'c7088f0f3e6c8088236ef8e1e3e70000'),
    'nesw-resize': ('fd_double_arrow', 'size_bdiag', 'fcf1c3c7cd4491d801f1e1c78f100000'),
    'n-resize': ('top_side',),
    'e-resize': ('right_side',),
    's-resize': ('bottom_side',),
    'w-resize': ('left_side',),
    'ne-resize': ('top_right_corner',),
    'se-resize': ('bottom_right_corner',),
    'sw-resize': ('bottom_left_corner',),
    'nw-resize': ('top_left_corner',),
    'wait': ('watch', 'busy', '0426c94ea35c87780ff01dc239897213'),
    'progress': ('left_ptr_watch', 'half-busy', '08e8e1c95fe2fc01f976f1e063a24ccd',
                 '3ecb610c1bf2410f44200f48c40d3599'),
    'not-allowed': ('crossed_circle', 'forbidden', 'circle', 'X_cursor',
                    '03b6e0fcb3499374a867c041f52298f0'),
    'no-drop': ('dnd-no-drop', 'dnd-forbidden'),
    'crosshair': ('cross', 'cross_reverse', 'diamond_cross', 'tcross'),
    'help': ('question_arrow', 'whats_this', 'dnd-ask',
             '5c6cd98b3f3ebcb1f9c7f1c204630408', 'd9ce0ab605698f320427677b458ad60b'),
    'context-menu': ('08ffe1cb5fe6fc01f906f1c063814ccd',),
    'grab': ('hand1', 'openhand', 'open_hand', '5aca4d189052212118709018842178c0'),
    'grabbing': ('closedhand', 'closed_hand', '208530c400c041818281048008011002'),
    'copy': ('dnd-copy', '1081e37283d90000800003c07f3ef6bf', '6407b0e94181790501fd1e167b474872'),
    'alias': ('dnd-link', 'link', '3085a0e285430894940527032f8b26df',
              '640fb0e74195791501fd1ed57b41487f', 'a2a266d0498c3104214a47bd64ab0fc8'),
    'none': ('blank_cursor',),
}
ALIASES = {alias: canonical for canonical, names in _ALIAS_GROUPS.items() for alias in names}


def source_svg(name, palette, frame=0):
    """Return an original transparent 32px SVG; frame indexes the spinner phase."""
    name = ALIASES.get(name, name)
    if name not in CURSORS:
        raise ValueError('Unknown cursor: ' + name)
    if not 0 <= frame < CURSORS[name].frames:
        raise ValueError('Invalid animation frame')
    fg, bg, mint, burgundy = (palette[k] for k in ('fg', 'bg', 'mint', 'burgundy'))
    if any(not re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in (fg, bg, mint, burgundy)):
        raise ValueError('Cursor palette requires six-digit hex colors')
    def shape(path, fill=fg, stroke=bg, width=1.8):
        return f'<path d="{path}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="miter"/>'
    def rect(x, y, w, h, fill, stroke='none', width=1.5):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
    def group(content, transform):
        return f'<g transform="{transform}">{content}</g>'
    def arrow():
        path = 'M' + 'L'.join(f'{x:g} {y:g}' for x, y in ARROW.values()) + 'Z'
        return (shape(path, width=1.5)
                + shape('M11.8 20.6L12.35 20.33L14.14 23.91L13.6 24.18Z', burgundy, 'none')
                + shape('M13.8 24.6L15.8 23.6L16.47 24.94L14.47 25.94Z', mint, 'none'))
    def spinner(phase):
        pieces = []
        for i in range(8):
            angle = math.pi * i / 4 - math.pi / 2
            x, y = 16 + 10 * math.cos(angle), 16 + 10 * math.sin(angle)
            # Fixed geometry; only the mint segment moves, so the cursor never wobbles.
            color = mint if i == phase else (burgundy if i == (phase + 7) % 8 else fg)
            pieces.append(rect(f'{x - 2.5:.4f}', f'{y - 2.5:.4f}', 5, 5, color, bg))
        return ''.join(pieces)
    def badge(content):
        return rect(15, 16, 15, 14, fg, bg, 1.8) + content
    def resize(angle=0, single=False):
        path = ('M4 16L12 9V13H27V19H12V23Z' if single else
                'M3 16L11 9V13H21V9L29 16L21 23V19H11V23Z')
        body = shape(path) + rect(14.5, 14, 3, 4, mint)
        return group(body, f'rotate({angle} 16 16)')
    if name == 'default':
        body = arrow()
    elif name == 'pointer':
        body = (shape('M12 18V4L13 3H15V13H19V15H23V17H26V23L22 27H12L5 20L4 17L6 15Z', width=1.5)
                + shape('M15 10V18M19 14V19M23 16V21', 'none', bg, 1)
                + rect(11, 25, 12, 2, mint, bg, 1.3))
    elif name in ('text', 'vertical-text'):
        body = (shape('M11 4H21V6.5H17.5V25.5H21V28H11V25.5H14.5V6.5H11Z', width=1.4)
                + rect(15.2, 14.7, 1.6, 2.6, mint))
        if name == 'vertical-text':
            body = group(body, 'rotate(90 16 16)')
    elif name == 'move':
        body = (shape('M16 2L22 9H19V13H23V10L30 16L23 22V19H19V23H22L16 30L10 23H13V19H9V22L2 16L9 10V13H13V9H10Z')
                + rect(14, 14, 4, 4, mint))
    elif name in ('ew-resize', 'ns-resize', 'nwse-resize', 'nesw-resize', 'col-resize', 'row-resize'):
        angle = {'ew-resize': 0, 'ns-resize': 90, 'nwse-resize': 45,
                 'nesw-resize': -45, 'col-resize': 0, 'row-resize': 90}[name]
        body = resize(angle)
        if name in ('col-resize', 'row-resize'):
            bars = shape('M14 7V25M18 7V25', 'none', bg, 1.5)
            body += group(bars, f'rotate({angle} 16 16)')
    elif name in ('n-resize', 'e-resize', 's-resize', 'w-resize', 'ne-resize', 'se-resize', 'sw-resize', 'nw-resize'):
        angle = {'w': 0, 'nw': 45, 'n': 90, 'ne': 135, 'e': 180, 'se': 225, 's': 270, 'sw': 315}[name.split('-')[0]]
        body = resize(angle, single=True)
    elif name == 'wait':
        body = spinner(frame)
    elif name == 'progress':
        # Preserve the normal arrow's size and tip when background work begins.
        body = arrow() + group(spinner(frame), 'translate(17.8 15.8) scale(.45)')
    elif name in ('not-allowed', 'no-drop'):
        circle = f'<circle cx="16" cy="16" r="12" fill="{fg}" stroke="{bg}" stroke-width="2"/>'
        circle += shape('M8 24L24 8', 'none', burgundy, 4)
        body = circle if name == 'not-allowed' else arrow() + group(circle, 'translate(14 14) scale(.53)')
    elif name in ('crosshair', 'cell'):
        body = (shape('M14 3H18V12H29V20H18V29H14V20H3V12H14Z')
                if name == 'cell' else shape('M14 3H18V14H29V18H18V29H14V18H3V14H14Z'))
        body += rect(14.5, 14.5, 3, 3, mint)
    elif name in ('grab', 'grabbing'):
        path = ('M7 16V10L8 9H11V6H14V5H18V7H21V11H24V22L21 27H12L6 22L4 18Z'
                if name == 'grab' else 'M7 17V12L10 10H22L25 13V22L21 27H12L6 22L4 19Z')
        fingers = ('M11 10V17M14 9V16M18 10V16M21 13V18' if name == 'grab' else
                   'M11 11V17M14 11V16M18 11V16M21 12V18')
        body = (shape(path, width=1.5) + shape(fingers, 'none', bg, 1)
                + rect(11, 25, 12, 2, mint, bg, 1.3))
    elif name in ('help', 'context-menu', 'copy', 'alias'):
        marks = {
            'help': shape('M20 20V19H26V23L23 25V26M23 27V29', 'none', burgundy, 2),
            'context-menu': shape('M19 20H27M19 23H27M19 26H25', 'none', burgundy, 1.8),
            'copy': shape('M22.5 19V27M18.5 23H26.5', 'none', burgundy, 2.5),
            'alias': shape('M19 27V22H26M23 19L26 22L23 25', 'none', burgundy, 2.2),
        }
        body = arrow() + badge(marks[name])
    elif name in ('zoom-in', 'zoom-out'):
        body = (shape('M18 18L29 27L26 30L17 19Z', burgundy)
                + f'<circle cx="13" cy="13" r="9" fill="{fg}" stroke="{bg}" stroke-width="2"/>'
                + shape('M8 13H18' + ('M13 8V18' if name == 'zoom-in' else ''), 'none', burgundy, 2.2))
    else:  # CSS cursor:none intentionally has a completely transparent image.
        body = ''
    return '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">' + body + '</svg>\n'


def _xcursor(images):
    """Encode (size, xhot, yhot, delay, RGBA image) tuples as Xcursor v1."""
    chunks, toc = [], []
    offset = 16 + 12 * len(images)
    for size, xhot, yhot, delay, image in images:
        # PNG RGBA is straight-alpha; Xcursor stores native ARGB premultiplied.
        pixels = bytearray()
        for red, green, blue, alpha in struct.iter_unpack('4B', image.tobytes()):
            pixels.extend(((blue * alpha + 127) // 255, (green * alpha + 127) // 255,
                           (red * alpha + 127) // 255, alpha))
        chunk = struct.pack('<9I', 36, IMAGE_TYPE, size, 1, image.width,
                            image.height, xhot, yhot, delay) + pixels
        toc.append(struct.pack('<3I', IMAGE_TYPE, size, offset))
        chunks.append(chunk)
        offset += len(chunk)
    return struct.pack('<4I', 0x72756358, 16, 0x10000, len(images)) + b''.join(toc + chunks)


def finalize(output_dir):
    """Compile rendered templates into output_dir/cursors, without changing home."""
    output_dir = Path(output_dir)
    renderer = shutil.which('rsvg-convert')
    if not renderer:
        raise RuntimeError('Building Yuru cursors requires rsvg-convert (librsvg)')
    palette = json.loads((output_dir / 'palette.json').read_text())
    generated = {}
    for name, spec in CURSORS.items():
        frames = []
        for size in SIZES:
            xhot, yhot = (min(size - 1, int(value * size / 32 + .5)) for value in spec.hotspot)
            for frame in range(spec.frames):
                png = subprocess.run([renderer, '--width', str(size), '--height', str(size)],
                                     input=source_svg(name, palette, frame).encode(),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=10).stdout
                with Image.open(BytesIO(png)) as raster:
                    frames.append((size, xhot, yhot, spec.delay, raster.convert('RGBA')))
        generated[name] = _xcursor(frames)
    cursors = output_dir / 'cursors'
    cursors.mkdir(exist_ok=True)
    for name, data in generated.items():
        (cursors / name).write_bytes(data)
    for alias, name in ALIASES.items():
        (cursors / alias).write_bytes(generated[name])
    return output_dir
