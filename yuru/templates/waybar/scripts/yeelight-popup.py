#!/usr/bin/env python3
"""Compact Yuru controls over the shared Yeelight LAN daemon."""
import colorsys
import concurrent.futures
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell
from yeelight import request


def device_labels(devices):
    labels = {}
    groups = {}
    for device in sorted(devices.values(), key=lambda d: (d.get('model', ''), d['id'])):
        model = device.get('model', '')
        base = device.get('name') or ('스트립' if model.startswith('strip') else
                                     '전구' if model.startswith('color') else '조명')
        groups.setdefault(base, []).append(device['id'])
    for base, identities in groups.items():
        for i, identity in enumerate(identities, 1):
            labels[identity] = base if len(identities) == 1 else f'{base} {i}'
    return labels


class Panel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.yuru.Yeelight', flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.window = None
        self.pending = self.selecting = self.syncing = False
        self.selection_generation = 0
        self.devices = {}
        self.selected = None
        self.edit_until = 0
        self.delayed = {}
        self.mixed = {}
        self.action_error = None
        self.action_error_until = 0
        self.alive = True
        self.connect('activate', self.activate_panel)
        self.connect('shutdown', self.shutdown_panel)

    def shutdown_panel(self, *_):
        self.alive = False
        self.pool.shutdown(wait=False, cancel_futures=True)

    def activate_panel(self, *_):
        if self.window:
            self.quit()
            return
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title('조명')
        self.window.set_default_size(268, -1)
        self.window.set_resizable(False)
        GtkLayerShell.init_for_window(self.window)
        GtkLayerShell.set_namespace(self.window, 'yuru-yeelight')
        GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_exclusive_zone(self.window, -1)
        GtkLayerShell.set_keyboard_mode(self.window, GtkLayerShell.KeyboardMode.ON_DEMAND)
        for edge in (GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self.window, edge, True)
        css = Gtk.CssProvider()
        css.load_from_path(str(Path(__file__).with_name('yeelight.css')))
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.window.connect('key-press-event', self.key)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_border_width(9)
        self.window.add(box)
        row = Gtk.Box(spacing=8)
        self.combo = Gtk.ComboBoxText()
        self.combo.connect('changed', self.choose)
        row.pack_start(self.combo, True, True, 0)
        self.problem = Gtk.Label(label='!')
        self.problem.get_style_context().add_class('error')
        self.problem.set_no_show_all(True)
        row.pack_start(self.problem, False, False, 0)
        self.power = Gtk.Switch()
        self.power.set_tooltip_text('전원')
        self.power.connect('notify::active', self.power_changed)
        row.pack_end(self.power, False, False, 0)
        box.pack_start(row, False, False, 0)
        self.bright = self.slider(box, '밝기', 1, 100, 1, '%', 'bright')
        self.bright.connect('value-changed', self.brightness_changed)
        self.ct = self.slider(box, '색온도', 1700, 6500, 100, ' K', 'ct')
        self.ct.connect('value-changed', self.temperature_changed)
        row = Gtk.Box(spacing=8)
        label = Gtk.Label(label='색상', xalign=0)
        label.set_size_request(40, -1)
        row.pack_start(label, False, False, 0)
        self.rgb = Gtk.ColorButton()
        self.rgb.set_title('색상')
        self.rgb.set_hexpand(True)
        self.rgb.connect('color-set', self.color_changed)
        row.pack_start(self.rgb, True, True, 0)
        box.pack_start(row, False, False, 0)
        self.place()
        self.window.show_all()
        self.refresh()
        GLib.timeout_add_seconds(1, self.refresh)

    def place(self):
        # The light module sits directly before the clock. Match the bar edge and
        # clock's actual Pango width instead of leaving an arbitrary screen gap.
        config = {}
        try:
            config = json.loads((Path.home() / '.config/waybar/config.jsonc').read_text())
        except (OSError, ValueError):
            pass
        clock = config.get('clock', {}).get('format', '{:%H:%M}')
        fmt = clock[2:-1] if clock.startswith('{:') and clock.endswith('}') else '%H:%M'
        clock_text = datetime.now().strftime(fmt)
        layout = self.window.create_pango_layout(clock_text)
        clock_width = layout.get_pixel_size()[0] + 20
        GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.BOTTOM,
                                config.get('height', 26) + config.get('margin-bottom', 12))
        GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.RIGHT,
                                config.get('margin-right', 24) + clock_width)
        try:
            outputs = json.loads(subprocess.check_output(['swaymsg', '-t', 'get_outputs', '-r'], timeout=2))
            rect = next(o['rect'] for o in outputs if o.get('focused'))
            display = Gdk.Display.get_default()
            for i in range(display.get_n_monitors()):
                monitor = display.get_monitor(i)
                geometry = monitor.get_geometry()
                if geometry.x == rect['x'] and geometry.y == rect['y']:
                    GtkLayerShell.set_monitor(self.window, monitor)
                    break
        except (OSError, subprocess.SubprocessError, ValueError, StopIteration, KeyError):
            pass

    def slider(self, box, label, low, high, step, suffix, key):
        row = Gtk.Box(spacing=8)
        text = Gtk.Label(label=label, xalign=0)
        text.set_size_request(40, -1)
        row.pack_start(text, False, False, 0)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, low, high, step)
        scale.set_digits(0)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.connect('format-value', lambda _, value: self.mixed.get(key) or f'{round(value)}{suffix}')
        row.pack_start(scale, True, True, 0)
        box.pack_start(row, False, False, 0)
        return scale

    def key(self, _, event):
        if event.keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        return False

    def error(self, text=None):
        self.problem.set_tooltip_text(text)
        self.problem.set_visible(bool(text))

    def background(self, action, callback, **kwargs):
        future = self.pool.submit(request, action, **kwargs)
        def finished(future):
            try:
                result, error = future.result(), None
            except Exception as exc:
                result, error = None, str(exc)
            if self.alive:
                GLib.idle_add(callback, result, error)
        future.add_done_callback(finished)

    def refresh(self):
        if self.alive and not self.pending and not self.selecting:
            self.pending = True
            generation = self.selection_generation
            self.background('status', lambda data, error: self.received(data, error, generation))
        return self.alive

    def targets(self):
        return list(self.devices.values()) if self.selected == 'all' else [self.devices[self.selected]] if self.selected in self.devices else []

    def received(self, data, error, generation):
        self.pending = False
        if generation != self.selection_generation or self.selecting or not self.alive:
            return False
        if error:
            self.error(error)
            self.set_sensitive([])
            return False
        devices = {d['id']: d for d in data.get('devices', [])}
        selected = data.get('selected')
        self.syncing = True
        signature = [(d['id'], d.get('name'), d.get('model'), d.get('online')) for d in devices.values()]
        old = [(d['id'], d.get('name'), d.get('model'), d.get('online')) for d in self.devices.values()]
        if signature != old or not self.combo.get_model():
            self.combo.remove_all()
            self.combo.append('all', '전체')
            labels = device_labels(devices)
            for d in devices.values():
                self.combo.append(d['id'], labels[d['id']] + ('' if d.get('online') else ' —'))
        self.devices, self.selected = devices, selected
        self.combo.set_active_id(selected) if selected else self.combo.set_active(-1)
        targets = self.targets()
        online = [d for d in targets if d.get('online')]
        self.set_sensitive(online)
        if time.monotonic() >= self.edit_until:
            self.power.set_active(bool(online) and all(d.get('props', {}).get('power') == 'on' for d in online))
            self.mixed = {}
            for key, scale, fallback, suffix in [('bright', self.bright, 50, '%'), ('ct', self.ct, 4000, ' K')]:
                method = 'set_bright' if key == 'bright' else 'set_ct_abx'
                values = [self.number(d.get('props', {}), key, fallback) for d in online if method in d.get('support', [])]
                if values and min(values) != max(values):
                    self.mixed[key] = f'{min(values)}–{max(values)}{suffix}'
                scale.set_value(sum(values) / len(values) if values else fallback)
                scale.queue_draw()
            props = online[0].get('props', {}) if online else {}
            rgb = self.number(props, 'rgb', 0xFFFFFF)
            rgba = Gdk.RGBA((rgb >> 16 & 255) / 255, (rgb >> 8 & 255) / 255, (rgb & 255) / 255, 1)
            if props.get('color_mode') == '3':
                hue = self.number(props, 'hue', 0) % 360
                sat = max(0, min(100, self.number(props, 'sat', 0)))
                red, green, blue = colorsys.hsv_to_rgb(hue / 360, sat / 100, 1)
                rgba = Gdk.RGBA(red, green, blue, 1)
            self.rgb.set_rgba(rgba)
        self.syncing = False
        labels = device_labels(devices)
        issues = [f"{labels[d['id']]}: {d.get('error') or '오프라인'}" for d in targets if d.get('error') or not d.get('online')]
        recent = self.action_error if time.monotonic() < self.action_error_until else None
        self.error(recent or '\n'.join(issues) or data.get('error'))
        return False

    @staticmethod
    def number(props, key, fallback):
        try:
            return int(props.get(key, fallback))
        except (ValueError, TypeError):
            return fallback

    def set_sensitive(self, devices):
        methods = {method for d in devices for method in d.get('support', [])}
        self.power.set_sensitive('set_power' in methods)
        self.bright.set_sensitive('set_bright' in methods)
        self.ct.set_sensitive('set_ct_abx' in methods)
        self.rgb.set_sensitive('set_rgb' in methods)

    def send(self, action, **kwargs):
        def done(result, error):
            skipped = result.get('skipped', []) if isinstance(result, dict) else []
            if (error or skipped) and self.alive:
                labels = device_labels(self.devices)
                self.action_error = error or '\n'.join(labels.get(d['id'], '조명') + ': ' +
                    {'offline': '오프라인', 'unsupported': '지원 안 됨'}.get(d['reason'], d['reason']) for d in skipped)
                self.action_error_until = time.monotonic() + 5
                self.error(self.action_error)
            self.refresh()
            return False
        self.background(action, done, **kwargs)

    def choose(self, combo):
        if not self.syncing and combo.get_active_id():
            self.edit_until = 0
            self.action_error = None
            self.action_error_until = 0
            self.error()
            for source in self.delayed.values():
                GLib.source_remove(source)
            self.delayed.clear()
            selected = combo.get_active_id()
            self.selection_generation += 1
            generation = self.selection_generation
            self.selected = None
            self.selecting = True
            self.set_sensitive([])
            def done(result, error):
                if generation == self.selection_generation:
                    self.selecting = False
                    if error:
                        self.error(error)
                    self.refresh()
                return False
            self.background('select', done, id=selected)

    def command(self, method, params):
        if not self.syncing and self.selected:
            self.edit_until = time.monotonic() + 2
            key = {'set_bright': 'bright', 'set_ct_abx': 'ct'}.get(method)
            self.mixed.pop(key, None)
            if method in ('set_bright', 'set_ct_abx', 'set_rgb'):
                previous = self.delayed.pop(method, None)
                if previous:
                    GLib.source_remove(previous)
                selected = self.selected
                def flush():
                    self.delayed.pop(method, None)
                    if self.alive and self.selected == selected:
                        self.send('command', id=selected, method=method, params=params)
                    return False
                self.delayed[method] = GLib.timeout_add(180, flush)
            else:
                self.send('command', id=self.selected, method=method, params=params)

    def power_changed(self, switch, _):
        self.command('set_power', ['on' if switch.get_active() else 'off', 'smooth', 300])

    def brightness_changed(self, scale):
        self.command('set_bright', [round(scale.get_value()), 'smooth', 300])

    def temperature_changed(self, scale):
        self.command('set_ct_abx', [round(scale.get_value()), 'smooth', 300])

    def color_changed(self, button):
        c = button.get_rgba()
        rgb = round(c.red * 255) << 16 | round(c.green * 255) << 8 | round(c.blue * 255)
        self.command('set_rgb', [rgb, 'smooth', 300])


if __name__ == '__main__':
    raise SystemExit(Panel().run(sys.argv))
