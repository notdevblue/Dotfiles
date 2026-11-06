#!/usr/bin/env python3
"""Check RAlt role toggles and G leakage in an isolated Sway + Fcitx5 session.

Requires Kitty, wtype, dbus-daemon, Fcitx5/Hangul, i3ipc and the shared native
verification helper's font setup. SWAY_TEST_BINARY/SWAY_TEST_RENDERER select
the compositor. --release-control reproduces the old double-toggle/G-repeat
failure as a positive control. Never sends input to the real desktop.
"""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time

DESKTOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESKTOP.parent / 'yuru'))
from verify_native import isolated_environment, stop_group

CAPTURE = '''import os, pathlib, select, sys, tty
tty.setraw(0)
path = pathlib.Path(sys.argv[1])
path.write_bytes(b'')
path.with_suffix('.ready').touch()
with path.open('ab', buffering=0) as out:
    while True:
        if select.select([0], [], [], .1)[0]:
            out.write(os.read(0, 4096))
'''

def wait(probe, timeout=6):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = probe()
        if result:
            return result
        time.sleep(.05)
    raise TimeoutError('condition not reached')

with tempfile.TemporaryDirectory(prefix='ralt-toggle-') as name:
    tmp = Path(name)
    env = isolated_environment(tmp)
    env['WLR_RENDERER'] = os.environ.get('SWAY_TEST_RENDERER', 'pixman')
    homeconfig = Path(env['XDG_CONFIG_HOME'])
    (homeconfig / 'sway').symlink_to(DESKTOP / 'config/sway', target_is_directory=True)
    (homeconfig / 'fcitx5').mkdir(parents=True)
    for file in ('config', 'profile'):
        shutil.copyfile(DESKTOP / 'config/fcitx5' / file, homeconfig / 'fcitx5' / file)
    children = []
    log = (tmp / 'log').open('w+')
    def start(args, **kwargs):
        p = subprocess.Popen(args, env=env, stdout=log, stderr=log,
                             start_new_session=True, **kwargs)
        children.append(p)
        return p
    def run(args, **kwargs):
        return subprocess.run(args, env=env, check=True, capture_output=True,
                              timeout=6, **kwargs)
    def ipc(*args):
        return json.loads(run(['swaymsg', '-r', *args], text=True).stdout)
    def ime():
        return run(['fcitx5-remote'], text=True).stdout.strip()
    def role():
        return run([str(DESKTOP / 'config/sway/scripts/toggle-ralt'), '--status'], text=True).stdout.strip()
    def rates():
        return sorted(o['repeat_rate'] for o in ipc('-t', 'get_inputs') if 'repeat_rate' in o)
    try:
        bus = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'],
                               env=env, stdout=subprocess.PIPE, stderr=log,
                               text=True, start_new_session=True)
        children.append(bus)
        if not select.select([bus.stdout], [], [], 6)[0]:
            raise TimeoutError('private session bus did not start')
        env['DBUS_SESSION_BUS_ADDRESS'] = bus.stdout.readline().strip()
        config = tmp / 'sway.conf'
        bindings = (DESKTOP / 'config/sway/config.d/26-game-input.conf').read_text()
        if '--release-control' in sys.argv:
            bindings = bindings.replace('bindsym --no-repeat ', 'bindsym --release --no-repeat ')
        config.write_text('set $mod Mod4\nxwayland disable\nseat seat0 fallback true\n'
                          f'include {DESKTOP / "config/sway/config.d/20-input.conf"}\n' + bindings)
        sway = start([os.environ.get('SWAY_TEST_BINARY', 'sway'), '--unsupported-gpu', '-c', str(config)])
        def ready():
            runtime = Path(env['XDG_RUNTIME_DIR'])
            sockets = list(runtime.glob('sway-ipc.*.sock'))
            displays = [p for p in runtime.glob('wayland-*') if not p.name.endswith('.lock')]
            if sockets and displays:
                env.update(SWAYSOCK=str(sockets[0]), WAYLAND_DISPLAY=displays[0].name)
                return True
        wait(ready)
        start(['fcitx5', '--disable=xcb,notifications'])
        capture = tmp / 'capture.py'
        capture.write_text(CAPTURE)
        received = tmp / 'received.bin'
        start(['kitty', '--config', 'NONE', '-o', 'linux_display_server=wayland', '-o', 'confirm_os_window_close=0',
               'python3', str(capture), str(received)])
        wait(lambda: received.with_suffix('.ready').exists())
        wait(lambda: ime() == '1')
        time.sleep(.4)
        def shortcut(label, expected, keys=None, control=False):
            oldbytes = received.read_bytes()
            beforeime, beforerates = ime(), rates()
            listener = subprocess.Popen(['swaymsg', '-m', '-t', 'subscribe', '["binding"]'], env=env,
                                        stdout=subprocess.PIPE, stderr=log, text=True)
            time.sleep(.1)
            run(['wtype', *(keys or ['-M', 'logo', '-M', 'ctrl', '-P', 'g', '-s', '100', '-p', 'g', '-s', '100', '-m', 'ctrl', '-m', 'logo'])])
            time.sleep(1)
            listener.terminate()
            events = listener.communicate(timeout=3)[0]
            count = events.count('"change": "run"')
            leaked = received.read_bytes()[len(oldbytes):]
            result = {'role': role(), 'bindings': count, 'leaked': repr(leaked), 'ime': ime(), 'rates': rates()}
            print(label, result, flush=True)
            if control:
                assert count >= 2 and b'g' in leaked, result
            else:
                assert count == 1, events
                assert role() == expected, result
                assert not leaked, result
                assert ime() == beforeime, (beforeime, result)
                assert rates() == beforerates, (beforerates, result)
        if '--release-control' in sys.argv:
            shortcut('Original release binding', 'Alt_R', control=True)
        else:
            shortcut('English: Hangul to Alt', 'Alt_R')
            shortcut('English: Alt to Hangul', 'Hangul')
            run(['fcitx5-remote', '-o'])
            wait(lambda: ime() == '2')
            shortcut('Hangul active: Hangul to Alt', 'Alt_R')
            shortcut('Hangul active: Alt to Hangul', 'Hangul')
            shortcut('Long hold', 'Alt_R', keys=['-M', 'logo', '-M', 'ctrl', '-P', 'g', '-s', '1400', '-p', 'g', '-m', 'ctrl', '-m', 'logo'])
            shortcut('Modifiers released first', 'Hangul', keys=['-M', 'logo', '-M', 'ctrl', '-P', 'g', '-s', '100', '-m', 'ctrl', '-m', 'logo', '-s', '100', '-p', 'g'])
            run(['fcitx5-remote', '-c'])
            wait(lambda: ime() == '1')
            before = received.read_bytes()
            run(['wtype', 'g'])
            wait(lambda: received.read_bytes() == before + b'g')
            time.sleep(1)
            assert received.read_bytes() == before + b'g', received.read_bytes()
            print('Normal G is delivered once and does not stay pressed', flush=True)
            ipc('input type:keyboard repeat_rate 0')
            shortcut('Game repeat rate 0: Hangul to Alt', 'Alt_R')
            shortcut('Game repeat rate 0: Alt to Hangul', 'Hangul')
            shortcut('Before reload', 'Alt_R')
            ipc('reload')
            wait(lambda: role() == 'Hangul')
            time.sleep(.3)
            shortcut('After reload: saved binding and default role restored', 'Alt_R')
    except BaseException:
        log.flush()
        log.seek(0)
        print(log.read()[-3500:], file=sys.stderr)
        raise
    finally:
        for p in reversed(children):
            stop_group(p)
        log.close()
