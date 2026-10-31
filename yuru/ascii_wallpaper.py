#!/usr/bin/env python3
"""A native-resolution ASCII winter lake below desktop windows.

The original composition and colors remain continuous; source-informed glyphs
texture the scenery while the character and foreground stay protected.
"""
import argparse
import json
import math
import os
from pathlib import Path
import random
import signal
import socket
import struct
import threading
import time

import cairo

ROOT = Path(__file__).resolve().parent


def rgb(value):
    return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))


class Scene:
    """One continuous source composition; glyphs follow its colors and edges."""
    def __init__(self, width, height, root=ROOT):
        self.root = root
        self.palette = json.loads((root / 'palette.json').read_text())
        self.assets = json.loads((root / 'scene_assets.json').read_text())
        self.ripples = []
        self.pointer = None
        self.last_motion = -100.0
        self.resize(width, height)

    def color(self, ctx, key, alpha=1):
        ctx.set_source_rgba(*rgb(self.palette.get(key, key)), alpha)

    def font(self, ctx):
        ctx.select_font_face(self.palette['font'], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(self.font_size)

    def source_coordinates(self, x, y):
        return ((x - self.offset_x) / self.source_scale / self.source.get_width(),
                (y - self.offset_y) / self.source_scale / self.source.get_height())

    @staticmethod
    def polygon_contains(u, v, polygon):
        inside = False
        previous = polygon[-1]
        for point in polygon:
            x1, y1 = previous
            x2, y2 = point
            if (y1 > v) != (y2 > v) and u < (x2 - x1) * (v - y1) / (y2 - y1) + x1:
                inside = not inside
            previous = point
        return inside

    def region(self, u, v):
        # Conservative keep-outs in SOURCE coordinates, shared by paint and input.
        # The painting itself is never cut, repositioned or regenerated.
        if not 0 <= u <= 1 or not 0 <= v <= 1:
            return 'protected'
        if self.polygon_contains(u, v, self.character_polygon):
            return 'protected'
        if v > self.foreground_line - self.foreground_slope * u:
            return 'protected'
        if v < self.mountain_top:
            return 'sky'
        if v < self.shore:
            return 'mountain'
        return 'lake'

    def clip_scenery(self, ctx):
        """Clip actual pixels as well as cell centers around the painted subject."""
        iw, ih = self.source.get_width(), self.source.get_height()
        def path(points):
            for i, (u, v) in enumerate(points):
                x, y = self.offset_x + u * iw * self.source_scale, self.offset_y + v * ih * self.source_scale
                (ctx.move_to if i == 0 else ctx.line_to)(x, y)
            ctx.close_path()
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.rectangle(0, 0, self.width, self.height)
        path(self.character_polygon)
        ctx.clip()
        ctx.rectangle(0, 0, self.width, self.height)
        path([(0,self.foreground_line), (1,self.foreground_line-self.foreground_slope),
              (1,1.2), (0,1.2)])
        ctx.clip()

    def resize(self, width, height):
        self.width, self.height = max(1, width), max(1, height)
        self.portrait = height > width
        name = self.assets['portrait' if self.portrait else 'landscape']
        self.source = cairo.ImageSurface.create_from_png(str(self.root / name))
        iw, ih = self.source.get_width(), self.source.get_height()
        self.source_scale = max(self.width / iw, self.height / ih)
        self.offset_x = (self.width - iw * self.source_scale) / 2
        self.offset_y = (self.height - ih * self.source_scale) / 2
        if self.portrait:
            self.character_polygon = [(.56,.485),(.77,.475),(1,.475),(1,1),(.425,1),
                                      (.425,.89),(.47,.76),(.54,.68),(.55,.58)]
            self.mountain_top, self.shore = .60, .733
            self.foreground_line, self.foreground_slope = .89, .14
        else:
            self.character_polygon = [(.795,0),(1,0),(1,1),(.68,1),(.68,.78),
                                      (.705,.57),(.728,.48),(.725,.28),(.74,.13),(.82,.08)]
            self.mountain_top, self.shore = .44, .785
            self.foreground_line, self.foreground_slope = 1.04, .20
        self.waterline = self.offset_y + self.shore * ih * self.source_scale
        self.font_size = 12
        scratch = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))
        self.font(scratch)
        self.cw = scratch.text_extents('M').x_advance
        self.ch = self.font_size * 1.25
        self.ripples.clear()
        self.base = self.make_base()
        rng = random.Random(227)
        self.flakes = [(rng.random(), rng.random(), rng.uniform(.4, 1), rng.random() * math.tau)
                       for _ in range(min(90, max(24, int(width * height / 75000))))]

    def make_base(self):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
        ctx = cairo.Context(surface)
        ctx.translate(self.offset_x, self.offset_y)
        ctx.scale(self.source_scale, self.source_scale)
        ctx.set_source_surface(self.source)
        ctx.get_source().set_filter(cairo.FILTER_BEST)
        ctx.paint()
        ctx.identity_matrix()
        self.font(ctx)
        # Area-sample source at cell resolution. No random terrain, global recolor,
        # heavy denoising, fake villages or a second independently scaled subject.
        cols, rows = math.ceil(self.width / self.cw), math.ceil(self.height / self.ch)
        sampled = cairo.ImageSurface(cairo.FORMAT_RGB24, cols, rows)
        small = cairo.Context(sampled)
        small.scale(cols / self.width, rows / self.height)
        small.set_source_surface(surface)
        small.get_source().set_filter(cairo.FILTER_BEST)
        small.paint()
        sampled.flush()
        data, stride = memoryview(sampled.get_data()), sampled.get_stride()
        def pixel(x, y):
            i = min(rows - 1, max(0, y)) * stride + min(cols - 1, max(0, x)) * 4
            b, g, r = data[i], data[i + 1], data[i + 2]
            return (r / 255, g / 255, b / 255)
        def luma(p):
            return .2126 * p[0] + .7152 * p[1] + .0722 * p[2]
        self.cells = []
        ramp = ' .,:;i1tfLCG08@'
        ctx.save()
        self.clip_scenery(ctx)
        for row in range(rows):
            for col in range(cols):
                x, y = (col + .5) * self.cw, (row + .5) * self.ch
                u, v = self.source_coordinates(x, y)
                region = self.region(u, v)
                if region == 'protected' or region == 'sky':
                    continue
                color = pixel(col, row)
                lum = luma(color)
                dx = luma(pixel(col + 1, row)) - luma(pixel(col - 1, row))
                dy = luma(pixel(col, row + 1)) - luma(pixel(col, row - 1))
                edge = math.hypot(dx, dy)
                neighborhood = [luma(pixel(col + ox, row + oy))
                                for ox in (-1, 0, 1) for oy in (-1, 0, 1)]
                contrast = max(neighborhood) - min(neighborhood)
                # Dark silhouettes still carry structure; highlights keep snow and
                # village lights. Dense type is earned by the original luminance.
                value = min(1, max(0, (lum - .025) / .36))
                if region == 'lake':
                    if edge < .015 and (col + row * 3) % 7:
                        continue
                    char = '~' if abs(dy) > abs(dx) else '.'
                    alpha = min(.40, .10 + edge * 1.4 + value * .16)
                else:
                    # Flat sky inside the broad mountain band is still sky:
                    # do not stamp a rectangular carpet of repeated characters.
                    if (edge < .012 and contrast < .024) or (value < .06 and edge < .013):
                        continue
                    if edge > .045:
                        if abs(dx) > abs(dy) * 2:
                            char = '|'
                        elif abs(dy) > abs(dx) * 2:
                            char = '-'
                        else:
                            char = '/' if dx * dy > 0 else '\\'
                    else:
                        char = ramp[min(len(ramp) - 1, max(1, round(value * (len(ramp) - 1))))]
                    alpha = min(.62, .19 + edge * 2 + value * .20)
                # A veil breaks continuous background strokes into a text surface
                # while leaving their color masses and spatial relationships intact.
                ctx.set_source_rgba(*color, .35)
                ctx.rectangle(col * self.cw, row * self.ch, self.cw, self.ch)
                ctx.fill()
                tint = tuple(min(1, channel * 1.4 + .14) for channel in color)
                ctx.set_source_rgba(*tint, alpha)
                ctx.move_to(col * self.cw, row * self.ch + self.font_size)
                ctx.show_text(char)
                self.cells.append((x, y, char, color, region))
        ctx.restore()
        return surface

    def motion(self, x, y, now):
        self.pointer = (x, y)
        self.last_motion = now

    def leave(self):
        self.pointer = None

    def click(self, x, y, now):
        self.motion(x, y, now)
        if self.region(*self.source_coordinates(x, y)) == 'lake':
            self.ripples.append((x, y, now))
            self.ripples = self.ripples[-8:]
            return True
        return False

    def draw(self, ctx, now):
        ctx.set_source_surface(self.base)
        ctx.paint()
        self.font(ctx)
        ctx.save()
        self.clip_scenery(ctx)
        self.ripples = [r for r in self.ripples if 0 <= now - r[2] < 3]
        # Local response samples only the existing lake field and respects its
        # shoreline/character/railing masks. No rings over faces or the foreground.
        for x, y, started in self.ripples:
            age = now - started
            radius = age * 100
            self.color(ctx, 'mint', (1 - age / 3) * .55)
            steps = max(12, int(radius / self.cw * 5))
            drawn = set()
            for step in range(steps):
                angle = step * math.tau / steps
                px = round((x + math.cos(angle) * radius) / self.cw) * self.cw
                py = round((y + math.sin(angle) * radius * .25) / self.ch) * self.ch
                if (px, py) in drawn or self.region(*self.source_coordinates(px, py)) != 'lake':
                    continue
                drawn.add((px, py))
                ctx.move_to(px, py)
                ctx.show_text('~' if abs(math.sin(angle)) > .4 else '.')
        # Sparse snow is also excluded from the character and foreground.
        for u, v, speed, phase in self.flakes:
            x = (u * self.width + math.sin(now * .3 + phase) * 12 + now * 2 * speed) % self.width
            y = (v * self.height + now * 12 * speed) % self.height
            if self.pointer:
                dx, dy = x - self.pointer[0], y - self.pointer[1]
                distance = math.hypot(dx, dy)
                if 0 < distance < 110:
                    push = (1 - distance / 110) * 30
                    x += dx / distance * push
                    y += dy / distance * push
            if self.region(*self.source_coordinates(x, y)) == 'protected':
                continue
            self.color(ctx, 'fg', .12 + speed * .25)
            ctx.move_to(x, y)
            ctx.show_text('.')
        ctx.restore()


def ipc_request(path, message_type, payload=''):
    data = payload.encode()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(path)
        client.sendall(b'i3-ipc' + struct.pack('<II', len(data), message_type) + data)
        def read(n):
            data = b''
            while len(data) < n:
                part = client.recv(n - len(data))
                if not part:
                    raise ConnectionError('Sway IPC closed')
                data += part
            return data
        header = read(14)
        size, _ = struct.unpack('<II', header[6:])
        return json.loads(read(size))


def fullscreen_outputs(tree, active_workspaces):
    result = set()
    def visit(node, output=None):
        if node.get('type') == 'output':
            output = node.get('name')
        if node.get('type') in ('con', 'floating_con') and node.get('fullscreen_mode') and output:
            result.add('*' if node['fullscreen_mode'] == 2 else output)
        for child in node.get('nodes', []) + node.get('floating_nodes', []):
            # Inactive workspaces must not freeze the visible background.
            if child.get('type') == 'workspace' and child.get('name') not in active_workspaces:
                continue
            visit(child, output)
    visit(tree)
    return result


def run_desktop(args):
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import Gdk, GLib, GLibUnix, Gtk, GtkLayerShell
    Gtk.init([])
    if not args.preview and not GtkLayerShell.is_supported():
        raise RuntimeError('A Wayland compositor with layer-shell is required')
    display = Gdk.Display.get_default()
    windows = {}
    started = time.monotonic()
    counters = {'motion': 0, 'click': 0, 'ripple': 0, 'frames': 0}
    paused = set()

    def diagnostics():
        if args.diagnostics:
            Path(args.diagnostics).write_text(json.dumps(dict(counters, outputs=[
                {'name': v['name'], 'width': v['scene'].width, 'height': v['scene'].height,
                 'frames': v['frames'], 'paused': v['name'] in paused or '*' in paused}
                for v in windows.values()]), indent=2) + '\n')
        return True

    def ready():
        if not windows or any(not v['area'].get_mapped() for v in windows.values()):
            return True
        if args.ready_file:
            data = {'pid': os.getpid(), 'outputs': [v['name'] for v in windows.values()],
                    'geometry': [{'name': v['name'], 'width': v['scene'].width,
                                  'height': v['scene'].height} for v in windows.values()]}
            temporary = args.ready_file.with_suffix('.tmp')
            temporary.write_text(json.dumps(data) + '\n')
            temporary.replace(args.ready_file)
        return False

    def add(monitor):
        window = Gtk.Window(title='Yuru ASCII lake preview' if args.preview else 'Yuru ASCII lake')
        if args.preview:
            window.set_default_size(args.width, args.height)
            width, height = args.width, args.height
            window.connect('destroy', lambda *_: Gtk.main_quit())
        else:
            bounds = monitor.get_geometry()
            width, height = bounds.width, bounds.height
            GtkLayerShell.init_for_window(window)
            GtkLayerShell.set_namespace(window, 'yuru-ascii')
            GtkLayerShell.set_monitor(window, monitor)
            GtkLayerShell.set_layer(window, GtkLayerShell.Layer.BOTTOM)
            GtkLayerShell.set_keyboard_mode(window, GtkLayerShell.KeyboardMode.NONE)
            GtkLayerShell.set_exclusive_zone(window, -1)
            for edge in (GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT,
                         GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM):
                GtkLayerShell.set_anchor(window, edge, True)
        area = Gtk.DrawingArea()
        area.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        scene = Scene(width, height)
        name = monitor.get_model() or 'preview'
        # GDK model is not a Sway output name. Map physical monitor geometry.
        if not args.preview and os.environ.get('SWAYSOCK'):
            try:
                outputs = ipc_request(os.environ['SWAYSOCK'], 3)
                geom = monitor.get_geometry()
                name = next((o['name'] for o in outputs if o.get('active') and
                             o['rect']['x'] == geom.x and o['rect']['y'] == geom.y), name)
            except (OSError, ValueError, KeyError, StopIteration):
                pass
        item = {'window': window, 'scene': scene, 'area': area, 'name': name, 'frames': 0}
        windows[monitor] = item
        def draw(_, ctx):
            scene.draw(ctx, time.monotonic() - started)
            counters['frames'] += 1
            item['frames'] += 1
        def resize(_, allocation):
            if (allocation.width, allocation.height) != (scene.width, scene.height):
                scene.resize(allocation.width, allocation.height)
        def motion(_, event):
            counters['motion'] += 1
            scene.motion(event.x, event.y, time.monotonic() - started)
        def click(_, event):
            if event.button == 1:
                counters['click'] += 1
                counters['ripple'] += scene.click(event.x, event.y, time.monotonic() - started)
        area.connect('draw', draw)
        area.connect('size-allocate', resize)
        area.connect('motion-notify-event', motion)
        area.connect('button-press-event', click)
        area.connect('leave-notify-event', lambda *_: scene.leave())
        window.add(area)
        window.show_all()

    def remove(_, monitor):
        item = windows.pop(monitor, None)
        if item:
            item['window'].destroy()
        diagnostics()

    def tick():
        now = time.monotonic() - started
        for item in windows.values():
            if item['name'] not in paused and '*' not in paused:
                item['area'].queue_draw()
        # Low cadence is sufficient for this quiet scene; interaction gets 20fps.
        active = any(now - v['scene'].last_motion < 3 for v in windows.values())
        GLib.timeout_add(50 if active else 125, tick)
        return False

    def update_fullscreen():
        if not os.environ.get('SWAYSOCK') or args.preview:
            return
        def worker():
            try:
                tree = ipc_request(os.environ['SWAYSOCK'], 4)
                outputs = ipc_request(os.environ['SWAYSOCK'], 3)
                active = {o.get('current_workspace') for o in outputs if o.get('active')}
                value = fullscreen_outputs(tree, active)
                def update():
                    for monitor, item in windows.items():
                        geom = monitor.get_geometry()
                        item['name'] = next((o['name'] for o in outputs if o.get('active')
                                             and o['rect']['x'] == geom.x
                                             and o['rect']['y'] == geom.y), item['name'])
                    paused.clear()
                    paused.update(value)
                GLib.idle_add(update)
            except (OSError, ValueError):
                pass
        threading.Thread(target=worker, daemon=True).start()

    def refresh_fullscreen():
        update_fullscreen()
        return True

    if args.preview:
        add(display.get_monitor(0))
    else:
        for i in range(display.get_n_monitors()):
            add(display.get_monitor(i))
        display.connect('monitor-added', lambda _, monitor: add(monitor))
        display.connect('monitor-removed', remove)
        refresh_fullscreen()
        GLib.timeout_add_seconds(2, refresh_fullscreen)
    GLib.timeout_add(125, tick)
    GLib.timeout_add(100, ready)
    GLib.timeout_add_seconds(1, diagnostics)
    for signum in (signal.SIGTERM, signal.SIGINT):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signum, lambda: (Gtk.main_quit(), False)[1])
    if args.quit_after:
        GLib.timeout_add(int(args.quit_after * 1000), lambda: (Gtk.main_quit(), False)[1])
    Gtk.main()
    diagnostics()
    if args.ready_file:
        args.ready_file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true', help='ordinary window; does not change desktop')
    parser.add_argument('--desktop', action='store_true', help='default: layer surfaces below windows')
    parser.add_argument('--render', type=Path, help='save an offline still PNG, no display needed')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    parser.add_argument('--time', type=float, default=12)
    parser.add_argument('--quit-after', type=float)
    parser.add_argument('--diagnostics', type=Path, help='optional geometry and input counters, no app data')
    parser.add_argument('--ready-file', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 64 <= args.width <= 16384 or not 64 <= args.height <= 16384:
        parser.error('dimensions must be between 64 and 16384')
    if args.render:
        scene = Scene(args.width, args.height)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, args.width, args.height)
        scene.draw(cairo.Context(surface), args.time)
        args.render.parent.mkdir(parents=True, exist_ok=True)
        surface.write_to_png(str(args.render))
    else:
        run_desktop(args)


if __name__ == '__main__':
    main()
