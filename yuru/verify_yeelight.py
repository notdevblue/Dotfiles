#!/usr/bin/env python3
"""Render the panel and check interaction races in a private Sway with fake lamps."""
import json
import copy
import select
import socketserver
import threading
import shutil
from pathlib import Path
import stat
import subprocess
import tempfile
import time

from verify_native import isolated_environment, stop_group, ROOT, BUILD

HARNESS = r'''
import importlib.util
import sys
import threading
import time
from pathlib import Path
import subprocess
spec = importlib.util.spec_from_file_location('panel', Path(sys.argv[1]) / 'yeelight-popup.py')
sys.path.insert(0, sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from gi.repository import GLib
props = {'power':'on','bright':'65','ct':'4000','rgb':'16711680','color_mode':'3','hue':'120','sat':'100'}
devices = [{'id':identity,'name':name,'model':'color','online':True,
            'support':['toggle','set_power','set_bright','set_ct_abx','set_rgb'],
            'props':dict(props)} for identity,name in [('sample-a','Yeelight Color'),('sample-b','Yeelight Strip')]]
state = {'devices':devices, 'selected':'all','error':None}
calls = []
lock = threading.Lock()
def request(action, **kw):
    with lock:
        calls.append((action, kw))
        if action == 'select':
            time.sleep(.15)
            state['selected'] = kw['id']
        return __import__('copy').deepcopy(state) if action == 'status' else {'queued':True}
m.request = request
app = m.Panel()
errors = []
def check(fn):
    def run():
        try: fn()
        except Exception as exc:
            __import__('traceback').print_exc(); print('CALLS', calls, 'SELECTION', app.selected, 'GEN', app.selection_generation, flush=True); errors.append(repr(exc)); app.quit()
        return False
    return run
def initial():
    assert app.selected == 'all', app.selected
    assert len(app.targets()) == 2
    assert app.window.get_size().width <= 280 and app.window.get_size().height <= 150
    assert not app.problem.get_visible()
    rgba = app.rgb.get_rgba()
    assert rgba.green > .99 and rgba.red < .01, 'HSV state uses stale RGB'
    subprocess.run(['grim','-o','HEADLESS-1',sys.argv[2]],check=True,timeout=3)
    app.combo.set_active_id('sample-b')
    assert app.selected is None, 'old selection is still actionable'
    assert not app.power.get_sensitive(), 'power remains enabled while selecting'
    app.power.set_active(False)
    assert not any(a == 'command' for a,_ in calls), 'selection race sent power to old lamp'
    app.received({'devices':devices,'selected':'all'},None,0)
    assert app.selected is None, 'stale snapshot restored old selection'
def changed():
    assert app.selected == 'sample-b', app.selected
    from types import SimpleNamespace
    app.name_button(app.name_entry, SimpleNamespace(button=3))
    app.name_entry.emit('preedit-changed', '방')
    assert app.name_key(app.name_entry, SimpleNamespace(keyval=m.Gdk.KEY_Return)) is False
    app.name_entry.emit('activate')
    assert not any(a == 'rename' for a,_ in calls), 'Saved before IME composition committed'
    app.name_entry.emit('preedit-changed', '')
    app.name_key(app.name_entry, SimpleNamespace(keyval=m.Gdk.KEY_Escape))
    app.bright.set_value(42)
    app.bright.set_value(43)
    app.bright.set_value(44)
def group():
    commands = [kw for action,kw in calls if action == 'command']
    assert len(commands) == 1, commands
    assert commands[0]['id'] == 'sample-b' and commands[0]['params'][0] == 44, commands
    app.combo.set_active_id('all')
def group_ready():
    assert app.selected == 'all', app.selected
    devices[0]['props']['bright'] = '20'
    devices[1]['props']['bright'] = '80'
    app.edit_until = 0
    app.received(state,None,app.selection_generation)
    assert app.mixed['bright'] == '20–80%'
    app.ct.set_value(4200)
def final():
    commands = [kw for action,kw in calls if action == 'command']
    assert len(commands) == 2 and commands[-1]['id'] == 'all', commands
    assert commands[-1]['method'] == 'set_ct_abx' and commands[-1]['params'][0] == 4200
    for device in devices: device['online'] = False
    app.edit_until = 0
    app.received(state,None,app.selection_generation)
    assert not app.power.get_sensitive() and not app.bright.get_sensitive()
    app.quit()
GLib.timeout_add(800, check(initial))
GLib.timeout_add(1800, check(changed))
GLib.timeout_add(2600, check(group))
GLib.timeout_add(3400, check(group_ready))
GLib.timeout_add(4200, check(final))
GLib.timeout_add(8000, lambda: (errors.append('timeout'),app.quit(),False)[-1])
app.run(['yeelight-panel-test', '--output', 'HEADLESS-1'])
if errors: raise RuntimeError('; '.join(errors))
print('PASS GTK panel: HSV, device selection race, stale status, slider coalescing, all/individual scopes, mixed values, offline controls')
'''


def click_checks(temporary, env):
    """Drive the real Waybar→shell→GApplication route with fake LAN RPC."""
    state = {'selected': 'all', 'error': None, 'devices': [
        {'id': 'fake', 'name': '', 'model': 'color', 'online': True,
         'support': ['set_power', 'set_bright', 'set_ct_abx', 'set_rgb'],
         'props': {'power': 'on', 'bright': '65', 'ct': '4000', 'rgb': '16777215', 'color_mode': '2'}}]}
    actions = []
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            data = json.loads(self.rfile.readline(65536))
            actions.append(data)
            if data.get('action') == 'rename':
                state['devices'][0]['name'] = data['name'].strip()
            if data.get('action') == 'select':
                state['selected'] = data['id']
            self.wfile.write((json.dumps({'ok': True, 'result': copy.deepcopy(state)}) + '\n').encode())
    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True
    server = Server(str(Path(env['XDG_RUNTIME_DIR']) / 'yuru-yeelight.sock'), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    pointer = None
    try:
        for mode, filename in [('client-header', 'virtual-pointer.h'), ('private-code', 'virtual-pointer.c')]:
            subprocess.run(['wayland-scanner', mode, str(ROOT/'tests/wlr-virtual-pointer-unstable-v1.xml'),
                            str(temporary/filename)], check=True, capture_output=True)
        executable = temporary/'pointer'
        subprocess.run(['cc', '-I', str(temporary), str(ROOT/'tests/ascii-pointer.c'),
                        str(temporary/'virtual-pointer.c'), '-lwayland-client', '-o', str(executable)],
                       check=True, capture_output=True)
        pointer = subprocess.Popen([str(executable)], env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        assert select.select([pointer.stdout], [], [], 3)[0] and pointer.stdout.readline().strip() == b'ready'
        def command(text):
            result = subprocess.run(['swaymsg', '-r', '--', text], env=env, capture_output=True, text=True, timeout=3, check=True)
            assert all(row.get('success') for row in json.loads(result.stdout)), result.stdout
        def click(output, button=1):
            command(f'seat seat0 cursor set {1170 + 1280 * (output - 1)} 694')
            command(f'seat seat0 cursor press button{button}')
            command(f'seat seat0 cursor release button{button}')
        from PIL import Image
        def visible(output):
            shot = temporary/f'output-{output}.png'
            subprocess.run(['grim', '-o', f'HEADLESS-{output}', str(shot)], env=env, check=True, timeout=3)
            pixels = Image.open(shot).convert('RGB')
            return any(pixels.getpixel((x, 677)) == (73, 56, 66) for x in range(900, 1256))
        def wait_for(expected):
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if tuple(visible(i) for i in (1, 2)) == expected:
                    return
                time.sleep(.08)
            log = Path(env['XDG_RUNTIME_DIR'])/'yuru-yeelight-popup.log'
            raise RuntimeError(f'Waybar popup state expected {expected}: ' + (log.read_text() if log.exists() else 'no command log'))
        command('focus output HEADLESS-1')
        click(2)
        wait_for((False, True))
        click(2)
        wait_for((False, False))
        click(1)
        wait_for((True, False))
        def until(predicate):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if predicate():
                    return
                time.sleep(.04)
            raise RuntimeError('Rename action did not complete: ' + repr([a for a in actions if a.get('action') != 'status']) + ' state=' + repr(state))
        shot = temporary/'rename.png'
        subprocess.run(['grim', '-o', 'HEADLESS-1', str(shot)], env=env, check=True)
        pixels = Image.open(shot).convert('RGB')
        boundary = [(x,y) for y in range(450,678) for x in range(900,1256)
                    if pixels.getpixel((x,y)) == (73,56,66)]
        left = min(x for x,y in boundary)
        top = min(y for x,y in boundary)
        def name_click(button):
            command(f'seat seat0 cursor set {left + 55} {top + 19}')
            command(f'seat seat0 cursor press button{button}')
            command(f'seat seat0 cursor release button{button}')
            time.sleep(.08)
        def keys(*args):
            subprocess.run(['wtype', '-s', '150', '-d', '20', *args], env=env, check=True, timeout=4)
        name_click(1)
        command(f'seat seat0 cursor set {left + 55} {top + 74}')
        command('seat seat0 cursor press button1')
        command('seat seat0 cursor release button1')
        until(lambda: state['selected'] == 'fake')
        time.sleep(.3)
        state['devices'][0]['online'] = False
        time.sleep(.3)
        name_click(3)
        keys('Desk', '-k', 'Return')
        until(lambda: state['devices'][0]['name'] == 'Desk')
        time.sleep(.3)
        rename_count = sum(a.get('action') == 'rename' for a in actions)
        name_click(3)
        keys('Cancel', '-k', 'Escape')
        time.sleep(.3)
        assert state['devices'][0]['name'] == 'Desk'
        assert sum(a.get('action') == 'rename' for a in actions) == rename_count
        assert visible(1), 'Escape while editing closed the panel'
        name_click(3)
        keys('-M', 'ctrl', '-k', 'a', '-m', 'ctrl', '-k', 'BackSpace', '-k', 'Return')
        until(lambda: state['devices'][0]['name'] == '')
        assert not any(a.get('action') == 'command' for a in actions), 'Renaming touched lighting controls'
        state['devices'][0]['online'] = True
        print('PASS actual name selection, right-click edit, Enter save, Escape cancel, empty reset, offline edit')
        click(2)
        wait_for((False, True))
        click(2)
        wait_for((False, False))
        click(1, button=3)
        wait_for((True, False))
        time.sleep(.3)
        keys('Bar name', '-k', 'Return')
        until(lambda: state['devices'][0]['name'] == 'Bar name')
        click(1)
        wait_for((False, False))
        state['selected'] = 'all'
        click(1, button=3)
        wait_for((True, False))
        time.sleep(.3)
        command(f'seat seat0 cursor set {left + 55} {top + 74}')
        command('seat seat0 cursor press button1')
        command('seat seat0 cursor release button1')
        until(lambda: state['selected'] == 'fake')
        time.sleep(.3)
        keys('From all', '-k', 'Return')
        until(lambda: state['devices'][0]['name'] == 'From all')
        click(1)
        wait_for((False, False))
        print('PASS Waybar right-click edits individual or picks a lamp from all')
        print('PASS deployed Waybar command with shadow Python: open, close, reopen, switch clicked output')
    finally:
        if pointer is not None:
            stop_group(pointer)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main():
    with tempfile.TemporaryDirectory(prefix='yuru-yeelight-ui-') as name:
        temporary = Path(name)
        env = isolated_environment(temporary)
        env['WLR_HEADLESS_OUTPUTS'] = '2'
        config = temporary / 'sway.conf'
        config.write_text('xwayland disable\noutput HEADLESS-1 mode 1280x720 pos 0 0\noutput HEADLESS-2 mode 1280x720 pos 1280 0\nseat seat0 fallback true\n')
        screenshot = ROOT / 'verification/yeelight-panel.png'
        # Reproduce the real session's PATH: another project's Python precedes
        # /usr/bin and has no gi. Use the exact deployed event command below.
        shadow = temporary / 'shadow-bin'
        shadow.mkdir()
        for name in ('python', 'python3'):
            executable = shadow / name
            executable.write_text('#!/bin/sh\nprintf "wrong Python interpreter\\n" >&2\nexit 86\n')
            executable.chmod(0o755)
        env['PATH'] = str(shadow) + ':' + env['PATH']
        installed = Path(env['HOME']) / '.config/waybar/scripts'
        installed.mkdir(parents=True)
        for name in ('yeelight.py', 'yeelight-popup.py', 'yeelight.css'):
            shutil.copy2(BUILD/'waybar/scripts'/name, installed/name)
        deployed = json.loads((BUILD/'waybar/config.jsonc').read_text())
        bar_config = temporary / 'waybar.json'
        bar_config.write_text(json.dumps({
            'layer':'bottom', 'position':'bottom', 'height':26,
            'margin-left':24, 'margin-right':24, 'margin-bottom':12,
            'modules-right':['custom/codex','custom/grok','custom/yeelight','clock'],
            'custom/codex':{'format':'codex 65%', 'tooltip':False},
            'custom/grok':{'format':'grok 80%', 'tooltip':False},
            'custom/yeelight':{'format':'light 65%', 'tooltip':False, 'on-click': deployed['custom/yeelight']['on-click'], 'on-click-right': deployed['custom/yeelight']['on-click-right']},
            'clock':{'format':'21:00','tooltip':False}}))
        with (temporary / 'sway.log').open('w+') as log:
            sway = subprocess.Popen(['/usr/bin/sway','--config',str(config)],env=env,
                                    stdout=log,stderr=log,start_new_session=True)
            try:
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    sockets = [p for p in Path(env['XDG_RUNTIME_DIR']).glob('wayland-*') if stat.S_ISSOCK(p.stat().st_mode)]
                    if sockets: break
                    if sway.poll() is not None:
                        log.seek(0); raise RuntimeError(log.read())
                    time.sleep(.05)
                else: raise RuntimeError('Private Wayland did not start')
                env['WAYLAND_DISPLAY'] = sockets[0].name
                env['SWAYSOCK'] = str(next(Path(env['XDG_RUNTIME_DIR']).glob('sway-ipc.*.sock')))
                env['GTK_USE_PORTAL'] = '0'
                bar = subprocess.Popen(['dbus-run-session','--', str(Path.home()/'.local/bin/waybar'),'-c',str(bar_config),'-s',str(BUILD/'waybar/style.css')],
                                       env=env,stdout=log,stderr=log,start_new_session=True)
                time.sleep(.3)
                if bar.poll() is not None:
                    log.seek(0)
                    raise RuntimeError('Private Waybar exited: ' + log.read())
                result = subprocess.run(['dbus-run-session','--','/usr/bin/python3','-Es','-c',HARNESS,
                                         str(BUILD/'waybar/scripts'),str(screenshot)],
                                        env=env,capture_output=True,text=True,timeout=14)
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
                print(result.stdout.strip())
                from PIL import Image
                pixels = Image.open(screenshot).convert('RGB')
                border = (73, 56, 66)
                xs = [x for x in range(900, 1256) if pixels.getpixel((x, 677)) == border]
                if not (xs and all(pixels.getpixel((xs[0], y)) == (0, 0, 0) for y in range(678, 682)) and pixels.getpixel((xs[0], 682)) == (30, 25, 31)):
                    log.flush(); log.seek(0)
                    raise RuntimeError('Panel/bar bounds: ' + repr(xs[:5]) + '\n' + log.read())
                print('PASS panel uses native-tooltip 4px gap above Waybar')
                print(screenshot)
                click_checks(temporary, env)
            finally:
                if 'bar' in locals():
                    stop_group(bar)
                stop_group(sway)


if __name__ == '__main__':
    main()
