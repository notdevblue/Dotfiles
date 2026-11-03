#!/usr/bin/env python3
"""Apply installed visual settings without a full Sway reload or closing applications."""
import argparse
import json
import os
import pwd
from pathlib import Path
import signal
import shlex
import subprocess

from cursor_theme import DEFAULT_SIZE, THEME

HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)
STATE = HOME / '.local/state/yuru-theme'
PALETTE = json.loads((Path(__file__).resolve().parent / 'palette.json').read_text())
GTK = {'gtk-theme': "'Adwaita'", 'icon-theme': "'Yuru'", 'font-name': repr(PALETTE['browser_font'] + ' 10.5'),
       'monospace-font-name': repr(PALETTE['font'] + ' 11'), 'color-scheme': "'prefer-dark'",
       'cursor-theme': repr(THEME), 'cursor-size': str(DEFAULT_SIZE)}
CURSOR_ENV = {'XCURSOR_THEME': THEME, 'XCURSOR_SIZE': str(DEFAULT_SIZE)}
THUNAR = {'last-view': 'ThunarDetailsView', 'last-location-bar': 'ThunarLocationEntry'}


def environment():
    env = os.environ.copy()
    runtime = Path('/run/user') / str(os.getuid())
    env.update(XDG_RUNTIME_DIR=str(runtime), DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(runtime / 'bus'))
    env.pop('SWAYSOCK', None)
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


def apply_cursors(env, before):
    """Save service environment and the seat baseline before changing either."""
    if 'cursor_environment' not in before:
        values = dict(line.split('=', 1) for line in
                      run(['systemctl', '--user', 'show-environment'], env).stdout.splitlines() if '=' in line)
        before['cursor_environment'] = {key: values.get(key) for key in CURSOR_ENV}
    if 'sway_cursor' not in before:
        # There is no IPC field for the current cursor theme. get_config exposes
        # only the root config, so included seat overrides cannot be inferred.
        # This host had no overrides; retain its desktop interface baseline.
        previous = [shlex.split(before['gsettings']['cursor-theme'])[0],
                    before['gsettings']['cursor-size']]
        config = json.loads(run(['swaymsg', '-s', env['SWAYSOCK'], '-t', 'get_config', '-r'], env).stdout)
        for line in config['config'].splitlines():
            if not line.lstrip().startswith('seat ') or 'xcursor_theme' not in line:
                continue
            words = shlex.split(line, comments=True)
            if len(words) in (4, 5) and words[:1] == ['seat'] and words[1] in ('*', 'seat0') and words[2] == 'xcursor_theme':
                previous = [words[3], words[4] if len(words) == 5 else previous[1]]
        before['sway_cursor'] = previous
    save_before(before)
    # Sway reuses its cursor manager when both name and size are unchanged.
    # Recreate it so a revised SVG build under the same theme appears now.
    command = (f'seat * xcursor_theme {THEME} {DEFAULT_SIZE + 1}; '
               f'seat * xcursor_theme {THEME} {DEFAULT_SIZE}')
    result = run(['swaymsg', '-s', env['SWAYSOCK'], '--', command], env)
    if not all(item.get('success') for item in json.loads(result.stdout)):
        raise RuntimeError(result.stdout)
    env.update(CURSOR_ENV)
    run(['dbus-update-activation-environment', '--systemd', *CURSOR_ENV], env)


def apply(env, icons_only=False, fonts_only=False, cursors_only=False):
    if not (STATE / 'transaction.json').exists() or 'SWAYSOCK' not in env:
        raise RuntimeError('Install first and run within the current Sway user session')
    if json.loads((STATE / 'transaction.json').read_text())['status'] != 'installed':
        raise RuntimeError('Recover the incomplete installation before activation')
    run(['swaymsg', '-s', env['SWAYSOCK'], '-t', 'get_version', '-r'], env)
    before_path = STATE / 'runtime-before.json'
    before = json.loads(before_path.read_text()) if before_path.exists() else {'gsettings': {}, 'thunar': {}}
    before.setdefault('gsettings', {})
    before.setdefault('thunar', {})
    gtk = ({'icon-theme': GTK['icon-theme']} if icons_only else
           {key: GTK[key] for key in ('font-name', 'monospace-font-name')} if fonts_only else
           {key: GTK[key] for key in ('cursor-theme', 'cursor-size')} if cursors_only else GTK)
    thunar = {} if icons_only or fonts_only or cursors_only else THUNAR
    if not cursors_only and not (HOME / '.local/share/icons/Yuru/index.theme').is_file():
        raise RuntimeError('Install the Yuru icon theme before activation')
    if not (icons_only or fonts_only) and not (HOME / f'.local/share/icons/{THEME}/cursors/left_ptr').is_file():
        raise RuntimeError('Install the Yuru cursor theme before activation')
    for key in gtk:
        if key not in before['gsettings']:
            before['gsettings'][key] = run(['gsettings', 'get', 'org.gnome.desktop.interface', key], env).stdout.strip()
    for key in thunar:
        if key not in before['thunar']:
            result = run(['xfconf-query', '-c', 'thunar', '-p', '/' + key], env, check=False)
            before['thunar'][key] = result.stdout.strip() if result.returncode == 0 else None
    save_before(before)
    if icons_only:
        run(['gsettings', 'set', 'org.gnome.desktop.interface', 'icon-theme', GTK['icon-theme']], env)
        print('Yuru icon preference saved; existing applications may need a normal restart.')
        return
    if not fonts_only:
        apply_cursors(env, before)
    if not (fonts_only or cursors_only) and (HOME / '.local/share/yuru-theme/qt-env.sh').exists():
        if 'qt_environment' not in before:
            values = dict(line.split('=', 1) for line in
                          run(['systemctl', '--user', 'show-environment'], env).stdout.splitlines() if '=' in line)
            before['qt_environment'] = values.get('QT_QPA_PLATFORMTHEME')
            save_before(before)
        env['QT_QPA_PLATFORMTHEME'] = 'qt5ct'
        run(['dbus-update-activation-environment', '--systemd', 'QT_QPA_PLATFORMTHEME'], env)
    for key, value in gtk.items():
        run(['gsettings', 'set', 'org.gnome.desktop.interface', key, value], env)
    for key, value in thunar.items():
        args = ['xfconf-query', '-c', 'thunar', '-p', '/' + key, '-s', value]
        if before['thunar'][key] is None:
            args += ['-n', '-t', 'string']
        run(args, env)
    if cursors_only:
        print('Yuru cursor preferences and service environment saved; Sway seat updated. Existing clients may need a normal restart.')
        return
    for path in ['sway.conf', 'effects.conf']:
        for line in (HOME / '.local/share/yuru-theme' / path).read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            if fonts_only and not line.startswith('font '):
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
                if name == 'waybar' or (name == 'kitty' and not fonts_only):
                    os.kill(int(proc.name), signal.SIGUSR1 if name == 'kitty' else signal.SIGUSR2)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    run(['dunstctl', 'reload'], env)
    run(['gdbus', 'call', '--session', '--dest', 'org.fcitx.Fcitx5', '--object-path', '/controller',
         '--method', 'org.fcitx.Fcitx.Controller1.ReloadConfig'], env)
    # ReloadConfig only reads core options; the candidate/status UI is an addon.
    run(['gdbus', 'call', '--session', '--dest', 'org.fcitx.Fcitx5', '--object-path', '/controller',
         '--method', 'org.fcitx.Fcitx.Controller1.ReloadAddonConfig', 'classicui'], env)
    print('Visual settings applied; no full Sway reload or application termination.')


def restore_settings(env):
    source = STATE / 'runtime-before.json'
    if not source.exists():
        source = STATE.parent / 'yuru-theme-preferences-before.json'
    before = json.loads(source.read_text())
    cursor_owned = all(run(['gsettings', 'get', 'org.gnome.desktop.interface', key], env).stdout.strip() == GTK[key]
                       for key in ('cursor-theme', 'cursor-size'))
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
    if cursor_owned and 'sway_cursor' in before and env.get('SWAYSOCK'):
        name, size = before['sway_cursor']
        result = run(['swaymsg', '-s', env['SWAYSOCK'], '--',
                      f'seat * xcursor_theme {shlex.quote(name)} {int(size)}'], env)
        if not all(item.get('success') for item in json.loads(result.stdout)):
            raise RuntimeError(result.stdout)
    current_env = dict(line.split('=', 1) for line in
                       run(['systemctl', '--user', 'show-environment'], env).stdout.splitlines() if '=' in line)
    previous_env = before.get('cursor_environment', {})
    for key, desired in CURSOR_ENV.items():
        if key not in previous_env or current_env.get(key) != desired:
            continue
        previous = previous_env[key]
        clear = dict(env, **{key: previous or ''})
        # D-Bus cannot remove activation variables; an empty value restores
        # ordinary toolkit fallback. Keep systemd's original absence exact.
        run(['dbus-update-activation-environment', key], clear)
        if previous is None:
            run(['systemctl', '--user', 'unset-environment', key], env)
        else:
            run(['systemctl', '--user', 'set-environment', f'{key}={previous}'], env)
    if current_env.get('QT_QPA_PLATFORMTHEME') == 'qt5ct' and 'qt_environment' in before:
        previous = before['qt_environment']
        clear = dict(env, QT_QPA_PLATFORMTHEME=previous or '')
        run(['dbus-update-activation-environment', 'QT_QPA_PLATFORMTHEME'], clear)
        if previous is None:
            run(['systemctl', '--user', 'unset-environment', 'QT_QPA_PLATFORMTHEME'], env)
        else:
            run(['systemctl', '--user', 'set-environment', f'QT_QPA_PLATFORMTHEME={previous}'], env)
    print('Owned preferences restored where unchanged; file restore/session restart is separate.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['apply', 'restore-settings'])
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--icons-only', action='store_true', help='Apply only the installed icon theme preference')
    scope.add_argument('--fonts-only', action='store_true', help='Apply installed UI fonts and reload font users only')
    scope.add_argument('--cursors-only', action='store_true', help='Apply installed cursor theme, seat and service environment only')
    args = parser.parse_args()
    if (args.icons_only or args.fonts_only or args.cursors_only) and args.command != 'apply':
        parser.error('--icons-only/--fonts-only/--cursors-only require apply')
    if args.command == 'apply':
        apply(environment(), icons_only=args.icons_only, fonts_only=args.fonts_only, cursors_only=args.cursors_only)
    else:
        restore_settings(environment())
