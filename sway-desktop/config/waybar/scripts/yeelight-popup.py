#!/usr/bin/env python3
"""Yuru Yeelight control panel; network I/O belongs to the shared LAN daemon."""
import concurrent.futures
import colorsys
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


class Panel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.yuru.Yeelight', flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.window = None
        self.pending = False
        self.selecting = False
        self.selection_generation = 0
        self.syncing = False
        self.devices = {}
        self.selected = None
        self.edit_until = 0
        self.delayed = {}
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
        self.window.set_title('Yeelight')
        self.window.set_default_size(390, -1)
        self.window.set_resizable(False)
        GtkLayerShell.init_for_window(self.window)
        GtkLayerShell.set_namespace(self.window, 'yuru-yeelight')
        GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self.window, GtkLayerShell.KeyboardMode.ON_DEMAND)
        for edge in (GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self.window, edge, True)
        GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.BOTTOM, 50)
        GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.RIGHT, 24)
        # Sway's focused output identifies the monitor on which the panel was invoked.
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
        css = Gtk.CssProvider()
        css.load_from_path(str(Path(__file__).with_name('yeelight.css')))
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window.connect('key-press-event', self.key)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_border_width(18)
        self.window.add(box)
        header = Gtk.Box(spacing=12)
        title = Gtk.Label(label='방 조명', xalign=0)
        title.get_style_context().add_class('title')
        header.pack_start(title, True, True, 0)
        refresh = Gtk.Button(label='다시 검색')
        refresh.connect('clicked', lambda *_: self.send('discover'))
        header.pack_start(refresh, False, False, 0)
        close = Gtk.Button(label='×')
        close.connect('clicked', lambda *_: self.quit())
        header.pack_start(close, False, False, 0)
        box.pack_start(header, False, False, 0)
        self.combo = Gtk.ComboBoxText()
        self.combo.connect('changed', self.choose)
        box.pack_start(self.combo, False, False, 0)
        row = Gtk.Box(spacing=12)
        row.pack_start(Gtk.Label(label='전원', xalign=0), True, True, 0)
        self.power = Gtk.Switch()
        self.power.connect('notify::active', self.power_changed)
        row.pack_end(self.power, False, False, 0)
        box.pack_start(row, False, False, 0)
        self.bright = self.slider(box, '밝기', 1, 100, 1, '%')
        self.bright.connect('value-changed', self.brightness_changed)
        self.mode_box = Gtk.Box(spacing=12)
        self.white = Gtk.RadioButton.new_with_label_from_widget(None, '백색 · 색온도')
        self.color = Gtk.RadioButton.new_with_label_from_widget(self.white, '컬러')
        for mode in (self.white, self.color):
            mode.connect('toggled', self.mode_changed)
            self.mode_box.pack_start(mode, True, True, 0)
        box.pack_start(self.mode_box, False, False, 0)
        self.ct = self.slider(box, '색온도 · 따뜻함 → 차가움', 1700, 6500, 100, ' K')
        self.ct.connect('value-changed', self.temperature_changed)
        colors = Gtk.Box(spacing=12)
        colors.pack_start(Gtk.Label(label='색상', xalign=0), True, True, 0)
        self.rgb = Gtk.ColorButton()
        self.rgb.set_title('조명 색상')
        self.rgb.connect('color-set', self.color_changed)
        colors.pack_end(self.rgb, False, False, 0)
        box.pack_start(colors, False, False, 0)
        hint = Gtk.Label(label='백색과 컬러는 각각의 조명 모드입니다.', xalign=0)
        hint.get_style_context().add_class('muted')
        box.pack_start(hint, False, False, 0)
        self.message = Gtk.Label(label='LAN에서 조명을 검색하고 있습니다…', xalign=0)
        self.message.set_line_wrap(True)
        self.message.set_max_width_chars(40)
        self.message.set_selectable(True)
        self.message.get_style_context().add_class('muted')
        box.pack_start(self.message, False, False, 0)
        self.window.show_all()
        self.refresh()
        GLib.timeout_add_seconds(1, self.refresh)

    def slider(self, box, label, low, high, step, suffix):
        box.pack_start(Gtk.Label(label=label, xalign=0), False, False, 0)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, low, high, step)
        scale.set_digits(0)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.connect('format-value', lambda _, value: f'{round(value)}{suffix}')
        box.pack_start(scale, False, False, 0)
        return scale

    def key(self, _, event):
        if event.keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        return False

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

    def received(self, data, error, generation):
        self.pending = False
        if generation != self.selection_generation or self.selecting:
            return False
        if not self.alive:
            return False
        if error:
            self.message.set_text('조명 서비스 연결 실패: ' + error)
            self.set_sensitive({})
            return False
        devices = {d['id']: d for d in data.get('devices', [])}
        selected = data.get('selected')
        self.syncing = True
        signature = [(d['id'], d.get('name'), d.get('model'), d.get('online')) for d in devices.values()]
        old = [(d['id'], d.get('name'), d.get('model'), d.get('online')) for d in self.devices.values()]
        if signature != old:
            self.combo.remove_all()
            self.combo.append('', '조명을 선택하세요')
            for d in devices.values():
                name = d.get('name') or d.get('model') or 'Yeelight'
                self.combo.append(d['id'], f"{name} · {d['id'][-6:]}" + ('' if d.get('online') else ' · 연결 끊김'))
        self.devices = devices
        self.selected = selected
        if not selected or not self.combo.set_active_id(selected):
            self.combo.set_active(0) if devices else self.combo.set_active(-1)
        d = devices.get(selected, {})
        props = d.get('props', {})
        self.set_sensitive(d)
        if time.monotonic() >= self.edit_until:
            self.power.set_active(props.get('power') == 'on')
            self.bright.set_value(self.number(props, 'bright', 50))
            self.ct.set_value(self.number(props, 'ct', 4000))
            rgb = self.number(props, 'rgb', 0xFFFFFF)
            rgba = Gdk.RGBA((rgb >> 16 & 255) / 255, (rgb >> 8 & 255) / 255, (rgb & 255) / 255, 1)
            if props.get('color_mode') == '3':
                hue = self.number(props, 'hue', 0) % 360
                sat = max(0, min(100, self.number(props, 'sat', 0)))
                red, green, blue = colorsys.hsv_to_rgb(hue / 360, sat / 100, 1)
                rgba = Gdk.RGBA(red, green, blue, 1)
            self.rgb.set_rgba(rgba)
            (self.color if props.get('color_mode') in ('1', '3') else self.white).set_active(True)
        self.syncing = False
        error = d.get('error') or data.get('error')
        text = error or ('연결됨 · 휴대폰 변경도 자동 반영' if d.get('online') else
                         '조명 연결 끊김 · 자동으로 다시 검색합니다.' if d else
                         '선택한 조명을 찾는 중입니다. 위 목록에서 다른 조명을 선택할 수 있습니다.' if devices else
                         '찾은 조명이 없습니다. 같은 LAN과 LAN 제어 설정을 확인하세요.')
        self.message.set_text(str(text))
        return False

    @staticmethod
    def number(props, key, fallback):
        try:
            return int(props.get(key, fallback))
        except (ValueError, TypeError):
            return fallback

    def set_sensitive(self, device):
        methods = device.get('support', []) if device.get('online') else []
        self.power.set_sensitive('set_power' in methods)
        self.bright.set_sensitive('set_bright' in methods)
        self.white.set_sensitive('set_ct_abx' in methods)
        self.color.set_sensitive('set_rgb' in methods)
        self.ct.set_sensitive('set_ct_abx' in methods)
        self.rgb.set_sensitive('set_rgb' in methods)

    def send(self, action, **kwargs):
        def done(result, error):
            if error and self.alive:
                self.message.set_text(error)
            self.refresh()
            return False
        self.background(action, done, **kwargs)

    def choose(self, combo):
        if not self.syncing and combo.get_active_id():
            self.edit_until = 0
            for source in self.delayed.values():
                GLib.source_remove(source)
            self.delayed.clear()
            selected = combo.get_active_id()
            self.selection_generation += 1
            generation = self.selection_generation
            self.selected = None
            self.selecting = True
            self.set_sensitive({})
            def done(result, error):
                if generation == self.selection_generation:
                    self.selecting = False
                    if error:
                        self.message.set_text(error)
                    self.refresh()
                return False
            self.background('select', done, id=selected)

    def command(self, method, params):
        if not self.syncing and self.selected:
            self.edit_until = time.monotonic() + 2
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

    def mode_changed(self, button):
        if not self.syncing and button.get_active():
            if button == self.white:
                self.temperature_changed(self.ct)
            else:
                self.color_changed(self.rgb)


if __name__ == '__main__':
    raise SystemExit(Panel().run(sys.argv))
