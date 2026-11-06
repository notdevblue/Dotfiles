#!/usr/bin/env python3
"""Render the panel and check interaction races in a private Sway with fake lamps."""
import os
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
state = {'devices':devices, 'selected':'sample-a','error':None}
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
    assert app.selected == 'sample-a', app.selected
    rgba = app.rgb.get_rgba()
    assert rgba.green > .99 and rgba.red < .01, 'HSV state uses stale RGB'
    subprocess.run(['grim','-o','HEADLESS-1',sys.argv[2]],check=True,timeout=3)
    app.combo.set_active_id('sample-b')
    assert app.selected is None, 'old selection is still actionable'
    assert not app.power.get_sensitive(), 'power remains enabled while selecting'
    app.power.set_active(False)
    assert not any(a == 'command' for a,_ in calls), 'selection race sent power to old lamp'
    app.received({'devices':devices,'selected':'sample-a'},None,0)
    assert app.selected is None, 'stale snapshot restored old selection'
def changed():
    assert app.selected == 'sample-b', app.selected
    app.bright.set_value(42)
    app.bright.set_value(43)
    app.bright.set_value(44)
def final():
    commands = [kw for action,kw in calls if action == 'command']
    assert len(commands) == 1, commands
    assert commands[0]['id'] == 'sample-b' and commands[0]['params'][0] == 44, commands
    for device in devices: device['online'] = False
    app.edit_until = 0
    app.received(state,None,app.selection_generation)
    assert not app.power.get_sensitive() and not app.bright.get_sensitive()
    app.quit()
GLib.timeout_add(800, check(initial))
GLib.timeout_add(1800, check(changed))
GLib.timeout_add(2600, check(final))
GLib.timeout_add(6000, lambda: (errors.append('timeout'),app.quit(),False)[-1])
app.run(['yeelight-panel-test'])
if errors: raise RuntimeError('; '.join(errors))
print('PASS GTK panel: HSV, device selection race, stale status, slider coalescing, offline controls')
'''


def main():
    with tempfile.TemporaryDirectory(prefix='yuru-yeelight-ui-') as name:
        temporary = Path(name)
        env = isolated_environment(temporary)
        config = temporary / 'sway.conf'
        config.write_text('xwayland disable\noutput HEADLESS-1 mode 1280x720\nseat seat0 fallback true\n')
        screenshot = ROOT / 'verification/yeelight-panel.png'
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
                result = subprocess.run(['dbus-run-session','--','python','-c',HARNESS,
                                         str(BUILD/'waybar/scripts'),str(screenshot)],
                                        env=env,capture_output=True,text=True,timeout=12)
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
                print(result.stdout.strip())
                print(screenshot)
            finally:
                stop_group(sway)


if __name__ == '__main__':
    main()
