#!/usr/bin/env python3
"""Verify an already-rendered build without contacting the live desktop.

Default: GTK CSS parsing only (no Gtk.init/widgets), Bash syntax, standalone
Sway appearance validation. --rofi / --swaynag additionally start a private
headless pixman Sway and capture the native UI. The exit action is inert.
This does not test the installed session or persistence. Run theme.py build first.
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / 'build'
TIMEOUT = 8  # Every subprocess wait is bounded below twelve seconds.
GTK_PARSE = r'''
import gi
import sys
gi.require_version('Gtk', sys.argv[1])
from gi.repository import Gtk
for filename in sys.argv[2:]:
    errors = []
    provider = Gtk.CssProvider()
    provider.connect('parsing-error', lambda provider, section, error: errors.append(str(error)))
    provider.load_from_path(filename)
    if errors:
        raise RuntimeError(filename + ': ' + '; '.join(errors))
    print('PASS GTK ' + sys.argv[1] + ' CSS: ' + filename)
'''


def child_limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.nice(19)


def stop_group(process):
    """Terminate the owned process group, including any remaining descendants."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=1)
    # A group may still contain children after its leader has exited.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=2)


def run(command, env, timeout=TIMEOUT):
    process = subprocess.Popen(command, env=env, cwd=ROOT,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True,
                               preexec_fn=child_limits)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        stop_group(process)
        process.communicate(timeout=2)
        raise
    finally:
        stop_group(process)
    if process.returncode:
        raise RuntimeError(f'{command[0]} exited {process.returncode}:\n{stdout}{stderr}')
    return stdout


def isolated_environment(temporary):
    home = temporary / 'home'
    runtime = temporary / 'runtime'
    home.mkdir(mode=0o700)
    runtime.mkdir(mode=0o700)
    # Deliberately do not inherit DISPLAY, SWAYSOCK, WAYLAND_DISPLAY, DBus,
    # renderer/device, GTK module, shell initialization or application variables.
    return {
        'PATH': '/usr/bin:/bin',
        'HOME': str(home),
        'XDG_RUNTIME_DIR': str(runtime),
        'XDG_CONFIG_HOME': str(home / '.config'),
        'XDG_CACHE_HOME': str(home / '.cache'),
        'XDG_DATA_HOME': str(home / '.local/share'),
        'XDG_DATA_DIRS': '/usr/local/share:/usr/share',
        'LC_ALL': 'C.UTF-8',
        'WLR_BACKENDS': 'headless',
        'WLR_RENDERER': 'pixman',
        'WLR_LIBINPUT_NO_DEVICES': '1',
        'WLR_HEADLESS_OUTPUTS': '1',
        'GDK_BACKEND': 'wayland',
        'WAYLAND_DISPLAY': 'no-live-display',
        'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(runtime / 'no-dbus'),
        'NO_AT_BRIDGE': '1',
    }


def appearance_config(temporary):
    source = (BUILD / 'sway/appearance.conf').read_text()
    old = '~/.local/share/yuru-theme/wallpaper.png'
    if source.count(old) != 1:
        raise RuntimeError('Expected exactly one staged wallpaper reference')
    wallpaper = BUILD / 'wallpaper.png'
    if not wallpaper.is_file():
        raise FileNotFoundError(wallpaper)
    # Sway's config lexer accepts double-quoted paths; JSON quoting handles spaces.
    source = source.replace(old, json.dumps(str(wallpaper)))
    target = temporary / 'appearance.conf'
    target.write_text(source)
    return target


def private_component(temporary, env, component):
    config = temporary / 'private-sway.conf'
    # No include, exec, bars, IME, DBus, live wallpaper or session startup hooks.
    config.write_text('xwayland disable\noutput HEADLESS-1 mode 1280x720\n'
                      'output HEADLESS-1 scale 1\nseat seat0 fallback true\n')
    runtime = Path(env['XDG_RUNTIME_DIR'])
    screenshot = ROOT / f'verification/native-{component}.png'
    screenshot.parent.mkdir(exist_ok=True)
    if screenshot.parent.is_symlink() or screenshot.is_symlink():
        raise RuntimeError('Refusing symlink screenshot destination')
    with (temporary / 'sway.log').open('w+') as log:
        server = subprocess.Popen(['/usr/bin/sway', '--config', str(config)],
                                  env=env, cwd=temporary, stdout=log, stderr=log,
                                  start_new_session=True, preexec_fn=child_limits)
        application = None
        try:
            deadline = time.monotonic() + 4
            display = None
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    log.seek(0)
                    raise RuntimeError('Private Sway exited:\n' + log.read())
                sockets = [p for p in runtime.glob('wayland-*')
                           if stat.S_ISSOCK(p.stat().st_mode)]
                ipc = list(runtime.glob('sway-ipc.*.sock'))
                if sockets and ipc:
                    # A bound Wayland socket may exist before its compositor is ready.
                    # A completed IPC request confirms the private event loop is serving.
                    try:
                        ready = subprocess.run(['/usr/bin/swaymsg', '-s', str(ipc[0]),
                                                '-t', 'get_outputs', '-r'], env=env,
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               text=True, timeout=0.5, preexec_fn=child_limits)
                    except subprocess.TimeoutExpired:
                        ready = None
                    if ready is not None and ready.returncode == 0:
                        display = sockets[0].name
                        break
                time.sleep(0.05)
            if display is None:
                raise TimeoutError('Private Wayland socket did not appear')
            private_env = dict(env, WAYLAND_DISPLAY=display)
            with (temporary / f'{component}.log').open('w+') as app_log:
                command = (['/usr/bin/rofi', '-config', str(BUILD / 'rofi/config.rasi'),
                            '-threads', '1', '-show', 'drun', '-filter', 's']
                           if component == 'rofi' else
                           ['/usr/bin/swaynag', '-c', str(BUILD / 'swaynag/config'),
                            '-t', 'warning', '-m', 'Exit Sway?', '-B', 'Exit', 'true'])
                application = subprocess.Popen(
                    command,
                    env=private_env, cwd=temporary, stdout=app_log, stderr=app_log,
                    start_new_session=True, preexec_fn=child_limits)
                # Layer-shell surfaces are absent from get_tree.
                # Give it bounded paint time, then capture for visual inspection.
                deadline = time.monotonic() + 1.2
                while time.monotonic() < deadline:
                    if application.poll() is not None:
                        app_log.seek(0)
                        raise RuntimeError(f'Private {component} exited:\n' + app_log.read())
                    if server.poll() is not None:
                        raise RuntimeError(f'Private Sway exited during {component} capture')
                    time.sleep(0.05)
                run(['/usr/bin/grim', '-o', 'HEADLESS-1', str(screenshot)], private_env, timeout=3)
                if not screenshot.is_file() or screenshot.stat().st_size < 100:
                    raise RuntimeError('Private screenshot missing or empty')
                app_log.flush()
                app_log.seek(0)
                diagnostics = app_log.read()
                if component == 'swaynag' and any(word in diagnostics for word in ['Invalid', 'Unknown', 'Failed']):
                    raise RuntimeError('Swaynag configuration diagnostics: ' + diagnostics)
                print(f'PASS private {component} capture: ' + str(screenshot))
        finally:
            if application is not None:
                stop_group(application)
            stop_group(server)


def main():
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rofi', action='store_true',
                        help='opt in to private CPU-only headless Rofi screenshot')
    parser.add_argument('--swaynag', action='store_true',
                        help='opt in to private exit-confirmation screenshot; action is inert')
    args = parser.parse_args()
    if not BUILD.is_dir():
        parser.error('Render first with python theme.py build')
    with tempfile.TemporaryDirectory(prefix='yuru-native-') as name:
        temporary = Path(name)
        env = isolated_environment(temporary)
        for version, paths in (
            ('3.0', ['gtk-3.0/gtk.css', 'waybar/style.css', 'gtklock/style.css', 'monitor/usage.css']),
            ('4.0', ['gtk-4.0/gtk.css']),
        ):
            print(run(['/usr/bin/python', '-c', GTK_PARSE, version,
                       *(str(BUILD / path) for path in paths)], env), end='')
        run(['/usr/bin/bash', '--noprofile', '--norc', '-n',
             str(BUILD / 'bash/prompt.bash')], env)
        print('PASS Bash syntax')
        config = appearance_config(temporary)
        run(['/usr/bin/sway', '--validate', '--config', str(config)], env)
        print('PASS standalone Sway appearance validation (headless pixman)')
        if args.rofi:
            private_component(temporary, env, 'rofi')
        if args.swaynag:
            private_component(temporary, env, 'swaynag')
    print('No live configuration or live desktop session was changed.')


if __name__ == '__main__':
    main()
