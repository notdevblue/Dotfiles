#!/usr/bin/env python3
"""Apply installed visual settings without a full Sway reload or closing applications."""
import argparse
import json
import os
import pwd
from pathlib import Path
import signal
import subprocess

HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)
STATE = HOME / '.local/state/yuru-theme'
GTK = {'gtk-theme': "'Adwaita'", 'font-name': "'Ubuntu Mono 11'",
       'monospace-font-name': "'Ubuntu Mono 11'", 'color-scheme': "'prefer-dark'"}
THUNAR = {'last-view': 'ThunarDetailsView', 'last-location-bar': 'ThunarLocationEntry'}


def environment():
    env = os.environ.copy()
    runtime = Path('/run/user') / str(os.getuid())
    env.update(XDG_RUNTIME_DIR=str(runtime), DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(runtime / 'bus'))
    sockets = list(runtime.glob('sway-ipc.*.sock'))
    if sockets:
        env['SWAYSOCK'] = str(sockets[0])
    for proc in Path('/proc').iterdir():
        try:
            if not proc.name.isdigit() or (proc / 'comm').read_text().strip() != 'waybar':
                continue
            values = dict(x.split('=', 1) for x in (proc / 'environ').read_bytes().decode(errors='replace').split('\0') if '=' in x)
            for key in ['DISPLAY', 'WAYLAND_DISPLAY', 'XDG_CURRENT_DESKTOP', 'XDG_SESSION_DESKTOP', 'XDG_SESSION_TYPE']:
                if key in values:
                    env[key] = values[key]
            break
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return env


def run(args, env, check=True):
    return subprocess.run(args, env=env, capture_output=True, text=True, timeout=8, check=check)


def save_before(data):
    from theme import atomic_write
    atomic_write(STATE / 'runtime-before.json', (json.dumps(data, indent=2) + '\n').encode(), 0o600)


def apply(env):
    if not (STATE / 'transaction.json').exists() or 'SWAYSOCK' not in env:
        raise RuntimeError('Install first and run within the current Sway user session')
    if json.loads((STATE / 'transaction.json').read_text())['status'] != 'installed':
        raise RuntimeError('Recover the incomplete installation before activation')
    run(['swaymsg', '-s', env['SWAYSOCK'], '-t', 'get_version', '-r'], env)
    before_path = STATE / 'runtime-before.json'
    before = json.loads(before_path.read_text()) if before_path.exists() else {'gsettings': {}, 'thunar': {}}
    before.setdefault('gsettings', {})
    before.setdefault('thunar', {})
    for key in GTK:
        if key not in before['gsettings']:
            before['gsettings'][key] = run(['gsettings', 'get', 'org.gnome.desktop.interface', key], env).stdout.strip()
    for key in THUNAR:
        if key not in before['thunar']:
            result = run(['xfconf-query', '-c', 'thunar', '-p', '/' + key], env, check=False)
            before['thunar'][key] = result.stdout.strip() if result.returncode == 0 else None
    save_before(before)
    if (HOME / '.local/share/yuru-theme/qt-env.sh').exists():
        env['QT_QPA_PLATFORMTHEME'] = 'qt5ct'
        run(['dbus-update-activation-environment', '--systemd', 'QT_QPA_PLATFORMTHEME'], env)
    for key, value in GTK.items():
        run(['gsettings', 'set', 'org.gnome.desktop.interface', key, value], env)
    for key, value in THUNAR.items():
        args = ['xfconf-query', '-c', 'thunar', '-p', '/' + key, '-s', value]
        if before['thunar'][key] is None:
            args += ['-n', '-t', 'string']
        run(args, env)
    for path in ['sway.conf', 'effects.conf']:
        for line in (HOME / '.local/share/yuru-theme' / path).read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            result = run(['swaymsg', '-s', env['SWAYSOCK'], '--', line.replace('~/', str(HOME) + '/')], env)
            if not all(item.get('success') for item in json.loads(result.stdout)):
                raise RuntimeError(result.stdout)
            if path == 'effects.conf' and line.startswith('for_window '):
                result = run(['swaymsg', '-s', env['SWAYSOCK'], '--', line.removeprefix('for_window ')], env)
                if not all(item.get('success') for item in json.loads(result.stdout)):
                    raise RuntimeError(result.stdout)
    for proc in Path('/proc').iterdir():
        try:
            if proc.name.isdigit() and proc.stat().st_uid == os.getuid():
                name = (proc / 'comm').read_text().strip()
                if name in ['kitty', 'waybar']:
                    os.kill(int(proc.name), signal.SIGUSR1 if name == 'kitty' else signal.SIGUSR2)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    run(['dunstctl', 'reload'], env)
    run(['gdbus', 'call', '--session', '--dest', 'org.fcitx.Fcitx5', '--object-path', '/controller',
         '--method', 'org.fcitx.Fcitx.Controller1.ReloadConfig'], env)
    print('Visual settings applied; no full Sway reload or application termination.')


def restore_settings(env):
    source = STATE / 'runtime-before.json'
    if not source.exists():
        source = STATE.parent / 'yuru-theme-preferences-before.json'
    before = json.loads(source.read_text())
    for key, desired in GTK.items():
        current = run(['gsettings', 'get', 'org.gnome.desktop.interface', key], env).stdout.strip()
        if current == desired and key in before.get('gsettings', {}):
            run(['gsettings', 'set', 'org.gnome.desktop.interface', key, before['gsettings'][key]], env)
        elif key in before.get('gsettings', {}) and current != before['gsettings'][key]:
            print('Preserved post-install preference edit:', key)
    for key, desired in THUNAR.items():
        current = run(['xfconf-query', '-c', 'thunar', '-p', '/' + key], env, check=False)
        if current.returncode != 0 or current.stdout.strip() != desired or key not in before.get('thunar', {}):
            continue
        previous = before['thunar'][key]
        args = ['xfconf-query', '-c', 'thunar', '-p', '/' + key]
        args += ['-r'] if previous is None else ['-s', previous]
        run(args, env)
    values = run(['systemctl', '--user', 'show-environment'], env).stdout.splitlines()
    if 'QT_QPA_PLATFORMTHEME=qt5ct' in values:
        run(['systemctl', '--user', 'unset-environment', 'QT_QPA_PLATFORMTHEME'], env)
        clear = dict(env, QT_QPA_PLATFORMTHEME='')
        run(['dbus-update-activation-environment', 'QT_QPA_PLATFORMTHEME'], clear)
    print('Owned preferences restored where unchanged; file restore/session restart is separate.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['apply', 'restore-settings'])
    args = parser.parse_args()
    (apply if args.command == 'apply' else restore_settings)(environment())
