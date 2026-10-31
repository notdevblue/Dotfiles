#!/usr/bin/env python3
"""Small GTK view over CodexBar CLI. Credentials remain in provider stores."""
import concurrent.futures
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading

PROVIDERS = ('codex', 'grok')
INTERVAL = 300


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def normalize(payload, provider):
    """Keep measured quota windows only; do not retain identity or credentials."""
    if not isinstance(payload, list):
        raise ValueError('invalid response')
    rows = [row for row in payload if isinstance(row, dict) and row.get('provider') == provider]
    if len(rows) != 1 or rows[0].get('error'):
        raise ValueError('usage unavailable')
    row = rows[0]
    usage = row.get('usage')
    if not isinstance(usage, dict):
        raise ValueError('usage unavailable')
    labels = row.get('rateWindowLabels') or {}
    if not isinstance(labels, dict):
        raise ValueError('invalid window labels')
    windows = []
    for key in ('primary', 'secondary', 'tertiary'):
        window = usage.get(key)
        if not isinstance(window, dict):
            continue
        used = window.get('usedPercent')
        if isinstance(used, bool) or not isinstance(used, (int, float)):
            continue
        if not math.isfinite(used) or not 0 <= used <= 100:
            raise ValueError('invalid quota')
        minutes = window.get('windowMinutes')
        label = labels.get(key)
        if not isinstance(label, str) or not label.strip():
            if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and minutes > 0:
                label = f'{minutes / 60:g}h' if minutes % 60 == 0 else f'{minutes:g}m'
            else:
                label = key
        # Provider strings are plain text and bounded; never interpreted as markup.
        windows.append({'label': label.lower()[:48], 'remaining': 100 - used,
                        'resetsAt': timestamp(window.get('resetsAt'))})
    return {'provider': provider, 'windows': windows,
            'updatedAt': timestamp(usage.get('updatedAt'))}


def reset_text(reset, now=None):
    if reset is None:
        return 'reset unavailable'
    seconds = reset - (now if now is not None else datetime.now(timezone.utc).timestamp())
    if seconds <= 0:
        return 'reset due; refresh to confirm'
    minutes = math.ceil(seconds / 60)
    days, hours = divmod(minutes // 60, 24)
    if days:
        return f'resets in {days}d {hours}h'
    return f'resets in {hours}h {minutes % 60}m' if hours else f'resets in {minutes}m'


class Fetcher:
    def __init__(self):
        self.lock = threading.Lock()
        self.processes = set()
        self.closed = False

    @staticmethod
    def stop(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def close(self):
        with self.lock:
            self.closed = True
            for process in self.processes:
                self.stop(process)

    def fetch(self, provider):
        executable = shutil.which('codexbar')
        if not executable:
            candidate = Path.home() / '.local/bin/codexbar'
            if not candidate.is_file():
                raise RuntimeError('codexbar is not installed')
            executable = str(candidate)
        args = [executable, 'usage', '--provider', provider, '--source',
                'cli' if provider == 'codex' else 'auto', '--no-credits', '--format', 'json']
        env = dict(os.environ, CODEXBAR_ALLOW_BROWSER_COOKIE_IMPORT='0')
        with self.lock:
            if self.closed:
                raise RuntimeError('closed')
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       text=True, env=env, start_new_session=True)
            self.processes.add(process)
        try:
            try:
                output, _ = process.communicate(timeout=40)
            except subprocess.TimeoutExpired:
                raise RuntimeError('request timed out') from None
            if process.returncode:
                raise RuntimeError('refresh failed; check CLI login')
            try:
                return normalize(json.loads(output), provider)
            except (ValueError, TypeError):
                raise RuntimeError('usage unavailable') from None
        finally:
            self.stop(process)
            process.communicate()
            with self.lock:
                self.processes.discard(process)


def main():
    if '--snapshot' in sys.argv:
        fetcher = Fetcher()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = {p: pool.submit(fetcher.fetch, p) for p in PROVIDERS}
                snapshot = {}
                for provider, future in results.items():
                    try:
                        snapshot[provider] = future.result()
                    except RuntimeError as error:
                        snapshot[provider] = {'error': str(error)}
                print(json.dumps(snapshot, indent=2))
        finally:
            fetcher.close()
        return

    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GLib
    GLib.set_prgname('yuru-usage')

    class Application(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='dev.yuru.Usage')
            self.window = None
            self.fetcher = Fetcher()
            self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
            self.states = {p: {'data': None, 'error': None, 'busy': False} for p in PROVIDERS}
            self.closed = False

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            css = Gtk.CssProvider()
            css.load_from_path(str(Path(__file__).with_name('usage.css')))
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
            self.window = Gtk.ApplicationWindow(application=self, title='usage')
            self.window.set_name('yuru-usage')
            self.window.set_default_size(490, 340)
            self.window.set_size_request(380, 260)
            self.window.connect('destroy', self.close)
            self.window.connect('key-press-event', self.key)
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, margin=22)
            self.window.add(root)
            header = Gtk.Box(spacing=12)
            header.pack_start(self.label('usage'), True, True, 0)
            self.button = Gtk.Button(label='refresh')
            self.button.connect('clicked', lambda *_: self.refresh())
            header.pack_end(self.button, False, False, 0)
            root.pack_start(header, False, False, 0)
            self.bodies = {}
            for provider in PROVIDERS:
                root.pack_start(Gtk.Separator(), False, False, 0)
                body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                self.bodies[provider] = body
                root.pack_start(body, False, False, 0)
            root.pack_end(self.label('r refresh    q quit    / 5 min', 'muted'), False, False, 0)
            self.refresh()
            self.window.show_all()
            GLib.timeout_add_seconds(INTERVAL, self.refresh)
            GLib.timeout_add_seconds(30, self.tick)

        @staticmethod
        def label(text, style=None):
            widget = Gtk.Label(label=text, xalign=0)
            if style:
                widget.get_style_context().add_class(style)
            return widget

        def render(self, provider):
            body, state = self.bodies[provider], self.states[provider]
            for child in body.get_children():
                body.remove(child)
            body.pack_start(self.label(provider, 'provider'), False, False, 0)
            data = state['data']
            if data:
                for quota in data['windows']:
                    line = Gtk.Box(spacing=12)
                    line.pack_start(self.label(quota['label']), True, True, 0)
                    line.pack_end(self.label(f"{quota['remaining']:.0f}% left"), False, False, 0)
                    body.pack_start(line, False, False, 0)
                    bar = Gtk.ProgressBar(fraction=quota['remaining'] / 100)
                    if quota['remaining'] <= 10:
                        bar.get_style_context().add_class('low')
                    body.pack_start(bar, False, False, 0)
                    body.pack_start(self.label(reset_text(quota['resetsAt']), 'muted'), False, False, 0)
                if not data['windows']:
                    body.pack_start(self.label('quota unavailable', 'muted'), False, False, 0)
            if state['error']:
                message = ('stale / ' if data else '') + state['error']
            elif state['busy']:
                message = 'refreshing' + (' / previous result' if data else '')
            elif data and data['updatedAt'] is not None:
                message = 'updated ' + datetime.fromtimestamp(data['updatedAt']).strftime('%H:%M')
            else:
                message = 'update time unavailable'
            body.pack_start(self.label(message, 'stale' if state['error'] else 'muted'), False, False, 0)
            body.show_all()

        def refresh(self):
            if self.closed:
                return False
            for provider, state in self.states.items():
                if state['busy']:
                    continue
                state['busy'] = True
                future = self.pool.submit(self.fetcher.fetch, provider)
                future.add_done_callback(lambda f, p=provider: GLib.idle_add(self.completed, p, f))
                self.render(provider)
            self.button.set_sensitive(False)
            return True

        def completed(self, provider, future):
            if self.closed:
                return False
            state = self.states[provider]
            try:
                state['data'] = future.result()
                state['error'] = None
            except Exception as error:
                state['error'] = str(error) if isinstance(error, RuntimeError) else 'refresh failed'
            state['busy'] = False
            self.render(provider)
            self.button.set_sensitive(not any(s['busy'] for s in self.states.values()))
            return False

        def tick(self):
            if self.closed:
                return False
            for provider in PROVIDERS:
                self.render(provider)
            return True

        def key(self, window, event):
            if Gdk.keyval_name(event.keyval) in ('q', 'Escape'):
                window.destroy()
                return True
            if Gdk.keyval_name(event.keyval) == 'r':
                self.refresh()
                return True
            return False

        def close(self, *_):
            self.closed = True
            self.fetcher.close()
            self.pool.shutdown(wait=False, cancel_futures=True)
            self.quit()

    Application().run([sys.argv[0]])


if __name__ == '__main__':
    main()
