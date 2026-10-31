#!/usr/bin/env python3
"""Resolve and render the built icon theme using GTK3, without a live display."""
import configparser
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

import cairo
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / 'build'


def main():
    palette = json.loads((ROOT / 'palette.json').read_text())
    source = ROOT / 'templates/icons/Yuru'
    built = BUILD / 'icons/Yuru'
    index = configparser.ConfigParser()
    index.read(built / 'index.theme')
    directories = index['Icon Theme']['Directories'].strip(',').split(',')
    assert all((built / directory).is_dir() for directory in directories)
    theme = Gtk.IconTheme.new()
    theme.prepend_search_path(str(BUILD / 'icons'))
    theme.set_custom_theme('Yuru')
    records = []
    for icon in sorted(built.rglob('*.svg')):
        assert str(icon.parent.relative_to(built)) in directories
        for size in (16, 24, 32, 48):
            info = theme.lookup_icon(icon.stem, size, Gtk.IconLookupFlags.FORCE_SIZE)
            assert info is not None, (icon.stem, size)
            assert Path(info.get_filename()).resolve() == icon.resolve(), (icon, info.get_filename())
            pixbuf = info.load_icon()
            assert (pixbuf.get_width(), pixbuf.get_height()) == (size, size)
        records.append(str(icon.relative_to(built)))
    fallbacks = {}
    for name in ('document-open', 'microphone-disabled-symbolic', 'firefox'):
        info = theme.lookup_icon(name, 24, Gtk.IconLookupFlags.FORCE_SIZE)
        assert info is not None, name
        info.load_icon()
        assert not Path(info.get_filename()).is_relative_to(built)
        fallbacks[name] = info.get_filename()

    gtk4 = subprocess.run([sys.executable, '-c', '''
import json
from pathlib import Path
import sys
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
root = Path(sys.argv[1])
theme = Gtk.IconTheme.new()
theme.set_search_path([str(root / 'icons'), '/usr/local/share/icons', '/usr/share/icons'])
theme.set_theme_name('Yuru')
icons = sorted((root / 'icons/Yuru').rglob('*.svg'))
for icon in icons:
    result = theme.lookup_icon(icon.stem, [], 24, 1, Gtk.TextDirection.NONE, 0)
    assert result.get_file() is not None, icon
    assert Path(result.get_file().get_path()).resolve() == icon.resolve(), icon
result = theme.lookup_icon('document-open', [], 24, 1, Gtk.TextDirection.NONE, 0)
assert result.get_file() is not None
assert not Path(result.get_file().get_path()).is_relative_to(root)
print(json.dumps({'names_resolved': len(icons), 'inherited_lookup': True}))
''', str(BUILD)], capture_output=True, text=True, check=True, timeout=10)

    # Show each original drawing once; aliases use the same rendered bytes.
    originals = [icon for icon in sorted(source.rglob('*.svg')) if not icon.is_symlink()]
    width, tile_width, tile_height = 1200, 200, 112
    height = 70 + ((len(originals) + 5) // 6) * tile_height
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)

    def color(key):
        value = palette[key].lstrip('#')
        ctx.set_source_rgb(*(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)))

    color('bg')
    ctx.paint()
    ctx.select_font_face(palette['font'])
    color('fg')
    ctx.set_font_size(22)
    ctx.move_to(20, 30)
    ctx.show_text('Yuru / native GTK icon preview')
    color('muted')
    ctx.set_font_size(12)
    ctx.move_to(20, 52)
    ctx.show_text('Original SVG drawings at 16, 24, 32 and 48 px / inherited icons omitted')
    for number, icon in enumerate(originals):
        x, y = (number % 6) * tile_width, 70 + (number // 6) * tile_height
        color('surface')
        ctx.rectangle(x + 4, y + 4, tile_width - 8, tile_height - 8)
        ctx.fill()
        for offset, size in zip((12, 44, 84, 132), (16, 24, 32, 48)):
            info = theme.lookup_icon(icon.stem, size, Gtk.IconLookupFlags.FORCE_SIZE)
            pixbuf = info.load_icon()
            Gdk.cairo_set_source_pixbuf(ctx, pixbuf, x + offset, y + 18 + (48 - size) / 2)
            ctx.paint()
        color('fg')
        ctx.set_font_size(11)
        ctx.move_to(x + 10, y + 86)
        ctx.show_text(icon.stem)
        color('muted')
        ctx.set_font_size(10)
        ctx.move_to(x + 10, y + 100)
        ctx.show_text(icon.parent.name)
    verification = ROOT / 'verification'
    surface.write_to_png(str(verification / 'native-icons.png'))
    report = {
        'checked_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'theme': 'Yuru', 'original_drawings': len(originals),
        'icon_names': len(records), 'sizes': [16, 24, 32, 48],
        'gtk3_lookup_and_render': records, 'fallbacks': fallbacks,
        'gtk4_lookup': json.loads(gtk4.stdout),
        'scope': 'Fresh GTK3 render and GTK4 lookup processes; no live display, desktop restart, reboot or relogin.',
    }
    (verification / 'icons.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS {len(records)} icon names at four sizes, {len(originals)} original drawings; inherited icons render')


if __name__ == '__main__':
    main()
