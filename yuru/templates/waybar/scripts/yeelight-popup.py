#!/usr/bin/env python3
"""Compact Yuru controls over the shared Yeelight LAN daemon."""
import colorsys
import concurrent.futures
from datetime import datetime
import json
import os
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
        super().__init__(application_id='io.github.yuru.Yeelight', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.window = None
        self.output_name = None
        self.requested_output = None
        self.pending = self.selecting = self.syncing = False
        self.selection_generation = 0
        self.devices = {}
        self.selected = None
        self.renaming = None
        self.rename_pending = False
        self.name_preedit = False
        self.rename_requested = False
        self.rename_after_select = False
        self.combo_signature = None
        self.edit_until = 0
        self.delayed = {}
        self.gesture_started = {}
        self.mixed = {}
        self.action_error = None
        self.action_error_until = 0
        self.alive = True
        self.add_main_option('rename', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Rename light', None)
        self.add_main_option('output', 0, GLib.OptionFlags.NONE, GLib.OptionArg.STRING, 'Waybar output', 'OUTPUT')
        self.connect('command-line', self.command_line)
        self.connect('activate', self.activate_panel)
        self.connect('shutdown', self.shutdown_panel)

    def command_line(self, _, command_line):
        option = command_line.get_options_dict().lookup_value('output', None)
        self.requested_output = option.unpack() if option is not None else None
        rename = command_line.get_options_dict().lookup_value('rename', None)
        self.rename_requested = bool(rename and rename.unpack())
        self.activate()
        return 0

    def shutdown_panel(self, *_):
        self.alive = False
        self.pool.shutdown(wait=False, cancel_futures=True)

    def activate_panel(self, *_):
        if self.window:
            if self.rename_requested or (self.requested_output and self.requested_output != self.output_name):
                self.place()
                self.window.present()
                self.refresh()
            else:
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
        self.combo = Gtk.ComboBoxText.new_with_entry()
        self.name_entry = self.combo.get_child()
        self.name_entry.set_editable(False)
        self.name_entry.set_can_focus(False)
        self.name_entry.set_width_chars(12)
        self.name_entry.set_max_width_chars(16)
        self.name_entry.set_max_length(64)
        self.name_entry.connect('button-press-event', self.name_button)
        self.name_entry.connect('activate', self.save_name)
        self.name_entry.connect('preedit-changed', lambda _, text: setattr(self, 'name_preedit', bool(text)))
        self.name_entry.connect('key-press-event', self.name_key)
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
        GLib.timeout_add(200, self.refresh)

    def place(self):
        # Follow the clicked output, not whichever application has keyboard focus.
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
        microphone_width = 0
        try:
            muted = subprocess.check_output(['pactl', 'get-source-mute', '@' + 'DEFAULT_SOURCE' + '@'],
                                            text=True, timeout=1, env=dict(os.environ, LC_ALL='C')).strip().endswith('yes')
            if muted:
                microphone_width = 32
        except (OSError, subprocess.SubprocessError):
            pass
        GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.BOTTOM,
                                config.get('height', 26) + config.get('margin-bottom', 12) + 4)
        GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.RIGHT,
                                config.get('margin-right', 24) + clock_width + microphone_width)
        try:
            outputs = json.loads(subprocess.check_output(['swaymsg', '-t', 'get_outputs', '-r'], timeout=2))
            output = next((o for o in outputs if o['name'] == self.requested_output), None)
            output = output or next(o for o in outputs if o.get('focused'))
            self.output_name = output['name']
            rect = output['rect']
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
            if self.renaming:
                if not self.rename_pending:
                    self.finish_rename()
            else:
                self.quit()
            return True
        return False

    def name_button(self, _, event):
        if self.rename_pending:
            return True
        if event.button == 3:
            self.begin_rename()
            return True
        if event.button == 1 and not self.renaming:
            self.combo.popup()
            return True
        return False

    def begin_rename(self):
        if self.selected and self.selected != 'all':
            self.rename_after_select = False
            self.renaming = self.selected
            self.name_entry.set_editable(True)
            self.name_entry.set_can_focus(True)
            self.name_entry.set_text(device_labels(self.devices)[self.selected])
            self.name_entry.get_style_context().add_class('renaming')
            self.name_entry.grab_focus()
            self.name_entry.select_region(0, -1)
        else:
            self.rename_after_select = True
            self.combo.popup()

    def name_key(self, _, event):
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and self.renaming:
            if self.name_preedit:
                return False
            self.save_name()
            return True
        if event.keyval == Gdk.KEY_Escape and self.renaming:
            if not self.rename_pending:
                self.finish_rename()
            return True
        return False

    def finish_rename(self, restore=True):
        self.name_preedit = False
        self.renaming = None
        self.rename_pending = False
        self.combo.set_sensitive(True)
        self.name_entry.set_editable(False)
        self.name_entry.set_can_focus(False)
        self.name_entry.get_style_context().remove_class('renaming')
        if restore:
            self.syncing = True
            self.combo.set_active_id(self.selected)
            self.syncing = False
            self.refresh()

    def save_name(self, *_):
        if not self.renaming or self.rename_pending or self.name_preedit:
            return
        identity = self.renaming
        name = self.name_entry.get_text()
        self.rename_pending = True
        self.combo.set_sensitive(False)
        def done(result, error):
            if not self.alive:
                return False
            self.combo_signature = None
            self.finish_rename(restore=False)
            if error:
                self.action_error = error
                self.action_error_until = time.monotonic() + 5
                self.error(error)
            self.refresh()
            return False
        self.background('rename', done, id=identity, name=name)

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
        if not self.renaming and (signature != self.combo_signature or not self.combo.get_model()):
            self.combo.remove_all()
            self.combo.append('all', '전체')
            labels = device_labels(devices)
            for d in devices.values():
                self.combo.append(d['id'], labels[d['id']] + ('' if d.get('online') else ' —'))
            self.combo_signature = signature
        self.devices, self.selected = devices, selected
        if not self.renaming:
            self.combo.set_active_id(selected) if selected else self.combo.set_active(-1)
        targets = self.targets()
        online = [d for d in targets if d.get('online')]
        self.set_sensitive(online)
        if time.monotonic() >= self.edit_until:
            self.power.set_active(bool(online) and all(d.get('pending', {}).get('power', d.get('props', {}).get('power') if not d.get('stale') else None) == 'on' for d in online))
            self.mixed = {}
            for key, scale, fallback, suffix in [('bright', self.bright, 50, '%'), ('ct', self.ct, 4000, ' K')]:
                method = 'set_bright' if key == 'bright' else 'set_ct_abx'
                values = [self.number(dict(d.get('props', {}), **d.get('pending', {})), key, fallback) for d in online if method in d.get('support', []) and (not d.get('stale') or key in d.get('pending', {}))]
                if not values:
                    self.mixed[key] = '—'
                if values and min(values) != max(values):
                    self.mixed[key] = f'{min(values)}–{max(values)}{suffix}'
                scale.set_value(sum(values) / len(values) if values else fallback)
                scale.queue_draw()
            readable = next((d for d in online if not d.get('stale') or 'rgb' in d.get('pending', {})), {})
            props = dict(readable.get('props', {}), **readable.get('pending', {}))
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
        issues = []
        for d in targets:
            reason = (f"{d['cooldown']}초 대기" if d.get('cooldown') else d.get('error') or
                      ('상태 확인 중' if d.get('stale') else '오프라인' if not d.get('online') else None))
            if reason:
                issues.append(f"{labels[d['id']]}: {reason}")
        recent = self.action_error if time.monotonic() < self.action_error_until else None
        self.error(recent or '\n'.join(issues) or data.get('error'))
        if self.rename_requested or (self.rename_after_select and self.selected and self.selected != 'all'):
            self.rename_requested = False
            self.begin_rename()
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
            if self.renaming == combo.get_active_id():
                return
            if self.renaming:
                self.finish_rename(restore=False)
            self.edit_until = 0
            self.action_error = None
            self.action_error_until = 0
            self.error()
            for source in self.delayed.values():
                GLib.source_remove(source)
            self.delayed.clear()
            self.gesture_started.clear()
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
                now = time.monotonic()
                started = self.gesture_started.setdefault(method, now)
                def flush():
                    self.delayed.pop(method, None)
                    self.gesture_started.pop(method, None)
                    if self.alive and self.selected == selected:
                        self.send('command', id=selected, method=method, params=params)
                    return False
                delay = max(1, min(20, round((started + .04 - now) * 1000)))
                self.delayed[method] = GLib.timeout_add(delay, flush)
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
    arguments = list(sys.argv)
    output = os.environ.get('WAYBAR_OUTPUT_NAME')
    if output and '--output' not in arguments:
        arguments.extend(['--output', output])
    raise SystemExit(Panel().run(arguments))
