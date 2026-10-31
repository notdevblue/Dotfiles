#!/usr/bin/env python3
"""Merge/restore two BetterDiscord stable appearance preferences while stopped.

No account data is copied, and no application or desktop session is restarted.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import stat

from theme import atomic_write, state_directory

THEME = 'Yuru Kitty'
DATA = '.config/BetterDiscord/data/stable'
CSS = '.config/BetterDiscord/themes/YuruKitty.theme.css'


def stopped_guard(home, proc=Path('/proc')):
    """Fixture homes are isolated; live home edits require all Discord processes gone."""
    if Path(home).resolve() != Path(pwd.getpwuid(os.getuid()).pw_dir).resolve():
        return
    names = {'discord', 'discordcanary', 'discordptb', 'discorddevelopment'}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            comm = (entry / 'comm').read_text().strip().lower()
            try:
                executable = Path(os.readlink(entry / 'exe')).name.removesuffix(' (deleted)').lower()
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                executable = ''
            if comm in names or executable in names or comm.startswith('discord helper'):
                raise RuntimeError('Discord is running; quit Discord completely before apply/restore.')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue


def safe_path(home, relative):
    path = Path(home) / relative
    if not path.resolve().is_relative_to(Path(home).resolve()):
        raise RuntimeError('Discord preference path must remain inside home: ' + relative)
    if path.is_symlink() and not path.exists():
        raise RuntimeError('Discord preference path is a dangling symlink: ' + relative)
    return path.resolve()


def backup_path(home):
    path = state_directory(Path(home)) / 'discord-before.json'
    if path.is_symlink():
        raise RuntimeError('Discord backup must not be a symlink')
    return path


def read_preferences(home):
    files = {}
    for name in ('settings', 'themes'):
        path = safe_path(home, DATA + '/' + name + '.json')
        raw = path.read_bytes() if path.exists() else None
        if name == 'settings' and raw is None:
            raise RuntimeError('Initialize BetterDiscord stable settings before applying the theme.')
        try:
            data = json.loads(raw) if raw is not None else {}
        except (ValueError, UnicodeDecodeError) as error:
            raise RuntimeError('Invalid BetterDiscord ' + name + '.json') from error
        if not isinstance(data, dict) or (name == 'settings' and not isinstance(data.get('window', {}), dict)):
            raise RuntimeError('Unexpected BetterDiscord ' + name + '.json structure')
        files[name] = {'path': path, 'raw': raw, 'data': data,
                       'mode': stat.S_IMODE(path.stat().st_mode) if raw is not None else 0o600}
    return files


def snapshot(files):
    values = {'settings': (files['settings']['data'].get('window', {}), 'transparency'),
              'themes': (files['themes']['data'], THEME)}
    return {name: {'existed': key in data, 'value': data.get(key)}
            for name, (data, key) in values.items()}


def owned():
    return {name: {'existed': True, 'value': True} for name in ('settings', 'themes')}


def save_backup(path, backup):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    atomic_write(path, (json.dumps(backup, indent=2) + '\n').encode(), 0o600)


def load_backup(path):
    backup = json.loads(path.read_text())
    if backup.get('version') != 1 or backup.get('status') not in ('prepared', 'installed', 'restoring'):
        raise RuntimeError('Unsupported Discord backup; retained for review')
    return backup


def check_owned(files, backup):
    current = snapshot(files)
    for name, value in current.items():
        allowed = [owned()[name]]
        if backup['status'] != 'installed':
            allowed.append(backup['before'][name])
        # JSON's bool and int compare equal in Python, but are distinct preferences.
        if not any(json.dumps(value, sort_keys=True) == json.dumps(candidate, sort_keys=True)
                   for candidate in allowed):
            raise RuntimeError('Discord appearance changed since installation; backup retained')


def write_preferences(home, files, values, backup=None):
    for name, item in files.items():
        data = item['data']
        container, key = (data.setdefault('window', {}), 'transparency') if name == 'settings' else (data, THEME)
        value = values[name]
        if value['existed']:
            container[key] = value['value']
        else:
            container.pop(key, None)
        if backup and name == 'settings' and not backup['window_existed'] and not container:
            data.pop('window', None)
        stopped_guard(home)
        path = item['path']
        if safe_path(home, DATA + '/' + name + '.json') != path:
            raise RuntimeError('Discord preference symlink changed; backup retained')
        if (path.read_bytes() if path.exists() else None) != item['raw']:
            raise RuntimeError('Discord preferences changed during operation; backup retained')
        if backup and name == 'themes' and not backup['themes_file_existed'] and not data:
            path.unlink(missing_ok=True)
        else:
            atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode(), item['mode'])


def apply(home):
    stopped_guard(home)
    if not safe_path(home, CSS).is_file():
        raise RuntimeError('Install ' + CSS + ' before activating BetterDiscord preferences.')
    path = backup_path(home)
    files = read_preferences(home)
    if path.exists():
        backup = load_backup(path)
        if backup['status'] == 'restoring':
            raise RuntimeError('Finish Discord preference restoration before applying again.')
        check_owned(files, backup)
    else:
        backup = {'version': 1, 'before': snapshot(files),
                  'window_existed': 'window' in files['settings']['data'],
                  'themes_file_existed': files['themes']['raw'] is not None}
    backup['status'] = 'prepared'
    save_backup(path, backup)
    write_preferences(home, files, owned())
    if snapshot(read_preferences(home)) != owned():
        raise RuntimeError('Discord appearance readback mismatch; backup retained')
    backup['status'] = 'installed'
    save_backup(path, backup)


def restore(home):
    stopped_guard(home)
    path = backup_path(home)
    backup = load_backup(path)
    files = read_preferences(home)
    check_owned(files, backup)
    backup['status'] = 'restoring'
    save_backup(path, backup)
    write_preferences(home, files, backup['before'], backup)
    if snapshot(read_preferences(home)) != backup['before']:
        raise RuntimeError('Discord restoration readback mismatch; backup retained')
    path.unlink()


def status(home):
    path = backup_path(home)
    return {'backup': path.exists(), 'phase': load_backup(path)['status'] if path.exists() else None,
            'preferences': snapshot(read_preferences(home))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['apply', 'restore', 'status'])
    parser.add_argument('--home', type=Path, default=Path(pwd.getpwuid(os.getuid()).pw_dir))
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    if args.command == 'status':
        print(json.dumps(status(home), indent=2))
    else:
        {'apply': apply, 'restore': restore}[args.command](home)
        print('Discord appearance ' + ('saved' if args.command == 'apply' else 'restored') + '; application was not restarted.')


if __name__ == '__main__':
    main()
