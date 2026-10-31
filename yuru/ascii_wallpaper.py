#!/usr/bin/env python3
"""A native-resolution ASCII winter lake below desktop windows.

Scenery is a real printable-character grid on solid paper. Only the selected
restored character is composited as RGB through a separately traced alpha matte.
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
    """A real character grid on solid paper; only Rin uses selected RGB pixels."""
    def __init__(self, width, height, root=ROOT):
        self.root = root
        self.palette = json.loads((root / 'palette.json').read_text())
        self.assets = json.loads((root / 'scene_assets.json').read_text())
        self.last_frame = None
        self.resize(width, height)

    def color(self, ctx, key, alpha=1):
        ctx.set_source_rgba(*rgb(self.palette.get(key, key)), alpha)

    def font(self, ctx):
        ctx.select_font_face(self.blueprint['font_family'], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(self.font_size)

    def source_coordinates(self, x, y):
        return ((x - self.offset_x) / self.source_scale / self.source.get_width(),
                (y - self.offset_y) / self.source_scale / self.source.get_height())

    def region(self, u, v):
        if not 0<=u<=1 or not 0<=v<=1:return 'outside'
        x=self.offset_x+u*self.source.get_width()*self.source_scale
        y=self.offset_y+v*self.source.get_height()*self.source_scale
        col,row=int(x/self.cw),int(y/self.ch)
        if 0<=col<self.cols and 0<=row<self.rows:return self.cells[row*self.cols+col][2]
        return 'outside'

    def matte_alpha(self, x, y):
        return self.matte_data[y*self.matte.get_stride()+x*4+3]/255

    def resize(self, width, height):
        self.width, self.height = max(1,width), max(1,height)
        self.portrait = height > width
        orientation = 'portrait' if self.portrait else 'landscape'
        self.source = cairo.ImageSurface.create_from_png(str(self.root/self.assets[orientation]))
        self.matte = cairo.ImageSurface.create_from_png(str(self.root/self.assets[orientation+'_matte']))
        iw,ih = self.source.get_width(),self.source.get_height()
        if (self.matte.get_width(),self.matte.get_height()) != (iw,ih):
            raise ValueError('Character matte must match its source scene dimensions')
        self.matte.flush()
        self.matte_data = memoryview(self.matte.get_data())
        self.source_scale=max(self.width/iw,self.height/ih)
        self.offset_x=(self.width-iw*self.source_scale)/2
        self.offset_y=(self.height-ih*self.source_scale)/2
        from ascii_landscape import load_blueprint
        self.blueprint=load_blueprint(self.root/self.assets['glyph_blueprint'])
        if self.portrait:
            self.cols=round(100*self.blueprint['columns']/240)
            self.cw=self.width/self.cols
            self.ch=self.cw*(1440/self.blueprint['rows'])/(3440/self.blueprint['columns'])
            self.rows=math.ceil(self.height/self.ch)
        else:
            world_scale=max(self.width/3440,self.height/1440)
            self.cw=world_scale*3440/self.blueprint['columns']
            self.ch=world_scale*1440/self.blueprint['rows']
            self.cols,self.rows=math.ceil(self.width/self.cw),math.ceil(self.height/self.ch)
        self.font_size=self.ch*self.blueprint['font_size_to_cell_height']
        self.baseline=self.ch*self.blueprint['baseline_to_cell_height']
        self.paper=rgb(self.blueprint['paper'])
        self.cells=self.build_grid()
        self.frame_overrides={}
        self.base=self.paint_grid()
        self.character=self.paint_character()
        self.last_frame=None
        rng=random.Random(227)
        self.flakes=[{'x':rng.random()*self.width,'y':rng.random()*self.height,
                      'vx':rng.uniform(-3,3),'vy':rng.uniform(8,17),'mass':rng.uniform(.5,1)}
                     for _ in range(min(90,max(24,int(width*height/65000))))]

    def build_grid(self):
        from ascii_landscape import build_landscape
        cells=build_landscape(self.cols,self.rows,self.portrait,self.blueprint)
        for i,cell in enumerate(cells):
            u,v=self.source_coordinates((i%self.cols+.5)*self.cw,(i//self.cols+.5)*self.ch)
            x=min(self.source.get_width()-1,max(0,int(u*self.source.get_width())))
            y=min(self.source.get_height()-1,max(0,int(v*self.source.get_height())))
            if self.matte_alpha(x,y)>.5:
                cells[i]=(' ',cell[1],'character',0)
        return cells

    def draw_cell(self,ctx,i,char,ink):
        col,row=i%self.cols,i//self.cols
        advance=ctx.text_extents(char).x_advance
        gain=self.blueprint.get('ink_gain',1)
        ctx.set_source_rgb(*(p+(c-p)*gain for p,c in zip(self.paper,ink)))
        ctx.move_to(col*self.cw+(self.cw-advance)/2,row*self.ch+self.baseline)
        ctx.show_text(char)

    def paint_grid(self):
        surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,self.width,self.height)
        ctx=cairo.Context(surface);ctx.set_source_rgb(*self.paper);ctx.paint();self.font(ctx)
        for i,(char,ink,kind,_) in enumerate(self.cells):
            if char!=' ':self.draw_cell(ctx,i,char,ink)
        return surface

    def paint_character(self):
        surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,self.width,self.height)
        ctx=cairo.Context(surface);ctx.translate(self.offset_x,self.offset_y);ctx.scale(self.source_scale,self.source_scale)
        ctx.set_source_surface(self.source);ctx.get_source().set_filter(cairo.FILTER_BEST)
        ctx.mask_surface(self.matte,0,0)
        return surface

    def text(self):
        return '\n'.join(''.join(self.frame_overrides.get(i,self.cells[i])[0] for i in range(y*self.cols,(y+1)*self.cols)) for y in range(self.rows))

    def draw(self,ctx,now):
        elapsed=0 if self.last_frame is None else max(0,now-self.last_frame)
        dt=min(.2,elapsed)
        self.last_frame=now
        ctx.set_source_surface(self.base);ctx.paint();self.font(ctx)
        changed={}
        for flake in self.flakes:
            if dt:
                flake['vx']*=math.exp(-.5*dt)
                flake['x']=(flake['x']+flake['vx']*dt)%self.width
                flake['y']=(flake['y']+flake['vy']*dt)%self.height
            col,row=int(flake['x']/self.cw),int(flake['y']/self.ch)
            i=row*self.cols+col
            if 0<=i<len(self.cells) and self.cells[i][2]!='character':
                changed[i]=('.',tuple(c*(.55+flake['mass']*.25) for c in rgb(self.palette['fg'])),'snow',1)
        self.frame_overrides=changed
        for i,(char,ink,_,_) in changed.items():
            col,row=i%self.cols,i//self.cols
            ctx.set_source_rgb(*self.paper);ctx.rectangle(col*self.cw,row*self.ch,self.cw,self.ch);ctx.fill()
            self.draw_cell(ctx,i,char,ink)
        # This is the only raster paint in the visible scene, and its alpha is
        # the independently traced original character, never a background photo.
        ctx.set_source_surface(self.character);ctx.paint()


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
    counters = {'frames': 0, 'mouse_input': False}
    paused = set()

    def diagnostics():
        if args.diagnostics:
            Path(args.diagnostics).write_text(json.dumps(dict(counters, outputs=[
                {'name': v['name'], 'width': v['scene'].width, 'height': v['scene'].height,
                 'frames': v['frames'], 'mouse_input': False,
                 'glyph_count': len(v['scene'].cells), 'paused': v['name'] in paused or '*' in paused}
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
        area.connect('draw', draw)
        area.connect('size-allocate', resize)
        window.add(area)
        # A wallpaper must not participate in pointer/touch input dispatch.
        window.connect('realize', lambda win: win.get_window().input_shape_combine_region(cairo.Region(), 0, 0))
        window.show_all()

    def remove(_, monitor):
        item = windows.pop(monitor, None)
        if item:
            item['window'].destroy()
        diagnostics()

    def tick():
        for item in windows.values():
            if item['name'] not in paused and '*' not in paused:
                item['area'].queue_draw()
        # Slow ambient animation only; no mouse interactions or wave simulation.
        GLib.timeout_add(125, tick)
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
    parser.add_argument('--diagnostics', type=Path, help='optional geometry and frame diagnostics, no app data')
    parser.add_argument('--ready-file', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 64 <= args.width <= 16384 or not 64 <= args.height <= 16384:
        parser.error('dimensions must be between 64 and 16384')
    if not 0 <= args.time <= 86400:
        parser.error('--time must be between 0 and 86400 seconds')
    if args.render:
        scene = Scene(args.width, args.height)
        # Closed-form idle snow phase; no interactive impulses exist in an offline still.
        damping=math.exp(-.5*args.time)
        for flake in scene.flakes:
            flake['x']=(flake['x']+2*flake['vx']*(1-damping))%scene.width
            flake['vx']*=damping
            flake['y']=(flake['y']+flake['vy']*args.time)%scene.height
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, args.width, args.height)
        scene.draw(cairo.Context(surface), args.time)
        args.render.parent.mkdir(parents=True, exist_ok=True)
        surface.write_to_png(str(args.render))
    else:
        run_desktop(args)


if __name__ == '__main__':
    main()
