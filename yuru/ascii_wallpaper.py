#!/usr/bin/env python3
"""A native-resolution ASCII winter lake below desktop windows.

The scene is deterministic; only snow, water and pointer ripples animate. The
original painted character is a separate alpha asset. No global input hooks.
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
    def __init__(self, width, height, root=ROOT):
        self.palette = json.loads((root / 'palette.json').read_text())
        self.character = cairo.ImageSurface.create_from_png(str(root / 'assets/rin-cutout.png'))
        self.ripples = []
        self.pointer = None
        self.last_motion = -100.0
        self.resize(width, height)

    def color(self, ctx, key, alpha=1):
        ctx.set_source_rgba(*rgb(self.palette.get(key, key)), alpha)

    def font(self, ctx, size=None):
        ctx.select_font_face(self.palette['font'], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(size or self.font_size)

    def resize(self, width, height):
        self.width, self.height = max(1, width), max(1, height)
        self.portrait = height > width
        self.font_size = max(12, min(19, width / (100 if self.portrait else 190)))
        scratch = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))
        self.font(scratch)
        self.cw = scratch.text_extents('M').x_advance
        self.ch = self.font_size * 1.4
        self.waterline = self.height * (0.61 if self.portrait else 0.72)
        self.ripples.clear()
        self.base = self.make_base()
        iw, ih = self.character.get_width(), self.character.get_height()
        scale = min(self.width * (0.9 if self.portrait else 0.38) / iw,
                    self.height * (0.62 if self.portrait else 0.96) / ih)
        sw, sh = max(1, round(iw * scale)), max(1, round(ih * scale))
        self.foreground = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
        cached = cairo.Context(self.foreground)
        cached.scale(sw / iw, sh / ih)
        cached.set_source_surface(self.character)
        cached.get_source().set_filter(cairo.FILTER_BEST)
        cached.paint()
        self.character_x = self.width * 0.98 - sw
        self.character_y = self.height - sh
        rng = random.Random(227)
        self.flakes = [(rng.random(), rng.random(), rng.uniform(0.4, 1), rng.random() * math.tau)
                       for _ in range(min(100, max(28, int(width * height / 65000))))]
        self.water = [(rng.random(), rng.random(), rng.uniform(0.2, 0.8)) for _ in range(150)]

    def ridge(self, x, layer):
        # Three continuous ridges, shared seed and proportions on either output.
        return self.waterline - self.height * (
            [0.17, 0.105, 0.032][layer]
            + [0.065, 0.042, 0.023][layer] * math.sin(x * 8.4 + layer * 1.7)
            + [0.034, 0.024, 0.012][layer] * math.sin(x * 19.7 + layer * 2.1)
            + 0.01 * math.sin(x * 47.1))

    def make_base(self):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
        ctx = cairo.Context(surface)
        self.color(ctx, 'bg')
        ctx.paint()
        self.font(ctx)
        rng = random.Random(764)
        cols, rows = math.ceil(self.width / self.cw), math.ceil(self.height / self.ch)
        for row in range(rows):
            y = row * self.ch
            for col in range(cols):
                x = col * self.cw
                u = x / self.width
                if y < self.waterline:
                    layer = next((i for i in (2, 1, 0) if y >= self.ridge(u, i)), None)
                    if layer is None:
                        if rng.random() > 0.004:
                            continue
                        char, color, alpha = '.', 'fg', rng.uniform(0.17, 0.42)
                    else:
                        ridge = self.ridge(u, layer)
                        edge = y - ridge < self.ch * 1.3
                        snow = y - ridge < self.height * 0.035
                        char = rng.choice('/\\^' if edge else '..:/' if snow else ' .,:;')
                        color = 'mint' if layer == 0 else 'muted'
                        alpha = ([0.24, 0.32, 0.46][layer] if edge or snow else [0.12, 0.17, 0.23][layer])
                        if char == ' ':
                            continue
                else:
                    depth = (y - self.waterline) / max(1, self.height - self.waterline)
                    if rng.random() > 0.13 * (1 - depth * 0.65):
                        continue
                    char, color, alpha = rng.choice('._-'), 'mint', 0.07 + 0.05 * (1 - depth)
                self.color(ctx, color, alpha)
                ctx.move_to(x, y + self.font_size)
                ctx.show_text(char)
        # Scattered distant house lights and their reflections, all glyphs.
        for i in range(22 if not self.portrait else 12):
            u = rng.uniform(0.04, 0.95)
            x, y = u * self.width, self.waterline - rng.uniform(2, self.ch * 0.7)
            self.color(ctx, '#C8AF86', rng.uniform(0.25, 0.6))
            ctx.move_to(x, y)
            ctx.show_text('.' if i % 4 else ':')
            for j in range(rng.randint(1, 4)):
                self.color(ctx, '#C8AF86', 0.14 / (j + 1))
                ctx.move_to(x + rng.uniform(-8, 8), self.waterline + self.ch * (j + 1))
                ctx.show_text('-')
        return surface

    def motion(self, x, y, now):
        self.pointer = (x, y)
        self.last_motion = now

    def leave(self):
        self.pointer = None

    def click(self, x, y, now):
        self.motion(x, y, now)
        if y >= self.waterline:
            self.ripples.append((x, y, now))
            self.ripples = self.ripples[-8:]
            return True
        return False

    def draw(self, ctx, now):
        ctx.set_source_surface(self.base)
        ctx.paint()
        self.font(ctx)
        ctx.save()
        ctx.rectangle(0, self.waterline, self.width, self.height - self.waterline)
        ctx.clip()
        for u, v, phase in self.water:
            x = u * self.width + math.sin(now * 0.27 + phase * 12) * self.cw * 1.5
            y = self.waterline + v * (self.height - self.waterline)
            self.color(ctx, 'mint', 0.065 + 0.04 * math.sin(now * 0.5 + u * 15))
            ctx.move_to(x, y)
            ctx.show_text('~' if v < 0.5 else '-')
        self.ripples = [r for r in self.ripples if 0 <= now - r[2] < 3]
        for x, y, started in self.ripples:
            age = now - started
            for ring in range(2):
                radius = age * 100 - ring * 25
                if radius <= 0:
                    continue
                self.color(ctx, 'mint', (1 - age / 3) * (0.65 if ring == 0 else 0.3))
                for step in range(max(12, int(radius / self.cw * 5))):
                    angle = step * math.tau / max(12, int(radius / self.cw * 5))
                    px = round((x + math.cos(angle) * radius) / self.cw) * self.cw
                    py = round((y + math.sin(angle) * radius * 0.27) / self.ch) * self.ch
                    ctx.move_to(px, py)
                    ctx.show_text('-' if abs(math.sin(angle)) > 0.5 else '.')
        ctx.restore()
        for u, v, speed, phase in self.flakes:
            x = (u * self.width + math.sin(now * 0.3 + phase) * 15 + now * 3 * speed) % self.width
            y = (v * self.height + now * 15 * speed) % self.height
            if self.pointer:
                dx, dy = x - self.pointer[0], y - self.pointer[1]
                distance = math.hypot(dx, dy)
                if 0 < distance < 110:
                    push = (1 - distance / 110) * 36
                    x += dx / distance * push
                    y += dy / distance * push
            self.color(ctx, 'fg', 0.2 + speed * 0.3)
            ctx.move_to(x, y)
            ctx.show_text('.' if speed < 0.75 else '*')
        # The static painting stays crisp while the text field moves behind it.
        ctx.set_source_surface(self.foreground, self.character_x, self.character_y)
        ctx.paint()


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
