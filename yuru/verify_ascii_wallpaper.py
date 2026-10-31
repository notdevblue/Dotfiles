#!/usr/bin/env python3
"""Exercise only a private two-output compositor; never send input to the live session."""
import json
import os
from pathlib import Path
import subprocess
import select
import tempfile
import time

from verify_native import isolated_environment, stop_group

ROOT = Path(__file__).resolve().parent


def wait_for(probe, timeout=7):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = probe()
        if value:
            return value
        time.sleep(.1)
    raise TimeoutError('Private wallpaper verification timed out')


def run_once(iteration):
    with tempfile.TemporaryDirectory(prefix='yuru-ascii-verify-') as directory:
        temporary = Path(directory)
        env = isolated_environment(temporary)
        env['WLR_HEADLESS_OUTPUTS'] = '2'
        config = temporary / 'sway.conf'
        config.write_text('xwayland disable\nseat seat0 fallback true\n'
                          'output HEADLESS-1 mode 1280x720 position 0 0\n'
                          'output HEADLESS-2 mode 720x1280 position 1280 0\n')
        diagnostics = temporary / 'diagnostics.json'
        children = []
        log = (temporary / 'process.log').open('w+')
        try:
            compositor = subprocess.Popen(['/usr/bin/sway', '-c', str(config)], env=env,
                                          stdout=log, stderr=log, start_new_session=True)
            children.append(compositor)
            runtime = Path(env['XDG_RUNTIME_DIR'])
            def ready():
                ipc = list(runtime.glob('sway-ipc.*.sock'))
                displays = [p for p in runtime.glob('wayland-*') if not p.name.endswith('.lock')]
                if not ipc or not displays:
                    return False
                env.update(SWAYSOCK=str(ipc[0]), WAYLAND_DISPLAY=displays[0].name)
                result = subprocess.run(['swaymsg', '-r', '-t', 'get_outputs'], env=env,
                                        capture_output=True, timeout=2)
                return result.returncode == 0
            wait_for(ready)
            # Cursor IPC alone does not give an input-less seat pointer capability.
            protocol = ROOT / 'tests/wlr-virtual-pointer-unstable-v1.xml'
            for mode, filename in [('client-header', 'virtual-pointer.h'),
                                   ('private-code', 'virtual-pointer.c')]:
                subprocess.run(['wayland-scanner', mode, str(protocol), str(temporary / filename)],
                               check=True, capture_output=True)
            pointer_binary = temporary / 'pointer-device'
            subprocess.run(['cc', '-I', str(temporary), str(ROOT / 'tests/ascii-pointer.c'),
                            str(temporary / 'virtual-pointer.c'), '-lwayland-client',
                            '-o', str(pointer_binary)], check=True, capture_output=True)
            pointer = subprocess.Popen([str(pointer_binary)], env=env, stdout=subprocess.PIPE,
                                       stderr=log, start_new_session=True)
            children.append(pointer)
            assert select.select([pointer.stdout], [], [], 3)[0]
            assert pointer.stdout.readline().strip() == b'ready'
            def sway(command):
                result = subprocess.run(['swaymsg', '-r', '--', command], env=env,
                                        capture_output=True, text=True, check=True, timeout=3)
                parsed = json.loads(result.stdout)
                assert all(r.get('success') for r in parsed), result.stdout
                return parsed
            def state():
                try:
                    return json.loads(diagnostics.read_text())
                except (FileNotFoundError, ValueError):
                    return {}
            def outputs():
                return state().get('outputs', [])
            wallpaper = subprocess.Popen(['/usr/bin/python3', str(ROOT / 'ascii_wallpaper.py'),
                                          '--diagnostics', str(diagnostics)], env=env,
                                         stdout=log, stderr=log, start_new_session=True)
            children.append(wallpaper)
            wait_for(lambda: len(outputs()) == 2)
            sway('seat seat0 cursor set 200 620')
            time.sleep(.1)
            sway('seat seat0 cursor set 215 620')
            sway('seat seat0 cursor press button1')
            sway('seat seat0 cursor release button1')
            wait_for(lambda: state().get('ripple', 0) >= 1)
            assert state()['motion'] > 0
            # Capture the real native layer surfaces, without any user session content.
            for name, label in [('HEADLESS-1', 'landscape'), ('HEADLESS-2', 'portrait')]:
                subprocess.run(['grim', '-o', name, str(ROOT / f'verification/ascii-native-{label}.png')],
                               env=env, check=True, timeout=5)
            probe_code = '''import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
GLib.set_prgname('yuru-ascii-probe')
w=Gtk.Window(title='input probe');w.connect('destroy',Gtk.main_quit);w.show_all();Gtk.main()
'''
            probe = subprocess.Popen(['/usr/bin/python3', '-c', probe_code], env=env,
                                     stdout=log, stderr=log, start_new_session=True)
            children.append(probe)
            def tree():
                return json.loads(subprocess.check_output(['swaymsg','-r','-t','get_tree'],env=env,timeout=2))
            def nodes(node):
                yield node
                for child in node.get('nodes', []) + node.get('floating_nodes', []):
                    yield from nodes(child)
            wait_for(lambda: any(n.get('app_id') == 'yuru-ascii-probe' for n in nodes(tree())))
            sway('[app_id="yuru-ascii-probe"] move to output HEADLESS-1')
            sway('[app_id="yuru-ascii-probe"] floating enable')
            sway('[app_id="yuru-ascii-probe"] resize set 300 200')
            sway('[app_id="yuru-ascii-probe"] move position 100 540')
            time.sleep(.2)
            before = state()['click']
            sway('seat seat0 cursor set 200 620')
            sway('seat seat0 cursor press button1')
            sway('seat seat0 cursor release button1')
            time.sleep(1.3)
            assert state()['click'] == before, ('Desktop intercepted a click over an application',
                                              [n for n in nodes(tree()) if n.get('app_id')])
            focused = [n for n in nodes(tree()) if n.get('focused')]
            assert any(n.get('app_id') == 'yuru-ascii-probe' for n in focused), focused
            sway('[app_id="yuru-ascii-probe"] fullscreen enable')
            wait_for(lambda: any(o['name'] == 'HEADLESS-1' and o['paused'] for o in outputs()))
            baseline = next(o['frames'] for o in outputs() if o['name'] == 'HEADLESS-1')
            time.sleep(1.4)
            assert next(o['frames'] for o in outputs() if o['name'] == 'HEADLESS-1') == baseline
            sway('[app_id="yuru-ascii-probe"] fullscreen disable')
            wait_for(lambda: all(not o['paused'] for o in outputs()))
            sway('output HEADLESS-2 mode 600x1000')
            wait_for(lambda: any(o['width'] == 600 and o['height'] == 1000 for o in outputs()))
            sway('output HEADLESS-2 disable')
            wait_for(lambda: len(outputs()) == 1)
            sway('output HEADLESS-2 enable')
            wait_for(lambda: len(outputs()) == 2)
            wait_for(lambda: {o['name'] for o in outputs()} == {'HEADLESS-1', 'HEADLESS-2'})
            assert wallpaper.poll() is None
            return {'iteration': iteration, 'two_outputs': True, 'motion_and_ripple': True,
                    'application_input_preserved': True, 'keyboard_focus_preserved': True,
                    'fullscreen_pause_and_resume': True, 'resize_and_output_reconnect': True,
                    'final_state': state()}
        except BaseException:
            if diagnostics.exists():
                print('Last diagnostics:', diagnostics.read_text())
            log.flush();log.seek(0)
            print(log.read()[-8000:])
            raise
        finally:
            for child in reversed(children):
                stop_group(child)
            log.close()


def main():
    results = [run_once(i) for i in (1, 2)]
    report = {'date': time.strftime('%Y-%m-%d'), 'scope': 'two fresh private CPU-only Sway sessions',
              'os_reboot_or_relogin': False, 'runs': results}
    (ROOT / 'verification/ascii-wallpaper.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
