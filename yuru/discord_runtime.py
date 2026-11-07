#!/usr/bin/env python3
"""Build checked BetterDiscord updates and manage the normal Discord launch paths.

Account data and theme preferences are never copied or changed here. Package
updates run unprivileged checks before the only privileged step, pacman -U.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import urllib.request

UPSTREAM = 'https://github.com/BetterDiscord/BetterDiscord.git'
FILES = ('PKGBUILD', 'betterdiscord-resilient-context-menu.patch',
         'betterdiscord-managed-updates.patch', 'context-menu-compat.test.ts',
         'discord-yuru', 'discord_runtime.py', 'Yuru-LICENSE')


def resources(source=None):
    location = Path(source or __file__).resolve()
    root = location if location.is_dir() else location.parent
    if (root / 'betterdiscord/PKGBUILD').is_file():
        return {name: root / ('betterdiscord/' + name if name in ('PKGBUILD', 'discord-yuru', 'Yuru-LICENSE')
                else 'patches/' + name if name.endswith('.patch')
                else 'tests/' + name if name.endswith('.test.ts') else name) for name in FILES}
    if not (root / 'PKGBUILD').is_file():
        root = Path('/usr/share/betterdiscord-yuru') if source is None else root
    return {name: root / name for name in FILES}


def atomic(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def capture_file(path):
    if path.is_symlink():
        return {'type': 'symlink', 'target': os.readlink(path)}
    if path.exists():
        if not path.is_file():
            raise RuntimeError('Preserving non-file launch path: ' + str(path))
        return {'type': 'file', 'data': base64.b64encode(path.read_bytes()).decode(),
                'mode': stat.S_IMODE(path.stat().st_mode)}
    return {'type': 'absent'}


def write_record(path, value):
    if value['type'] == 'file':
        atomic(path, base64.b64decode(value['data']), value['mode'])
    elif value['type'] == 'symlink':
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name('.' + path.name + '.yuru-link')
        if os.path.lexists(temporary):
            raise RuntimeError('Preserving existing temporary link: ' + str(temporary))
        try:
            temporary.symlink_to(value['target'])
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    elif value['type'] == 'absent':
        path.unlink(missing_ok=True)
    else:
        raise RuntimeError('Unknown backup file type')


def journal_path(home):
    return Path(home) / '.local/state/yuru-theme/discord-runtime.json'


def launch_entries(home, desktop):
    source = Path(desktop).read_text()
    if 'Exec=/usr/bin/discord ' not in source:
        raise RuntimeError('Official Discord desktop entry changed; preserving it for review')
    content = source.replace('Exec=/usr/bin/discord ', 'Exec=/usr/bin/discord-yuru ')
    return {Path(home) / '.local/bin/discord': {'type': 'symlink', 'target': '/usr/bin/discord-yuru'},
            Path(home) / '.local/share/applications/discord.desktop':
                {'type': 'file', 'data': base64.b64encode(content.encode()).decode(), 'mode': 0o644}}


def manage_launchers(home, restore=False, desktop='/usr/share/applications/discord.desktop'):
    home = Path(home).resolve()
    journal = journal_path(home)
    if journal.is_symlink():
        raise RuntimeError('Preserving symlinked runtime journal')
    state = json.loads(journal.read_text()) if journal.exists() else None
    if state and state.get('version') != 1:
        raise RuntimeError('Unknown runtime journal; preserving it')
    if restore and not state:
        return
    targets = launch_entries(home, desktop) if not restore else {
        Path(name): entry['before'] for name, entry in state['entries'].items()}
    if state:
        for name, entry in state['entries'].items():
            actual = capture_file(Path(name))
            allowed = [entry['installed']]
            if state['phase'] != 'installed':
                allowed.append(entry['before'])
                if 'previous' in entry:
                    allowed.append(entry['previous'])
            if actual not in allowed:
                raise RuntimeError('Preserving externally changed launcher: ' + name)
    else:
        state = {'version': 1, 'entries': {str(path): {'before': capture_file(path), 'installed': value}
                                         for path, value in targets.items()}}
    if not restore:
        for path, value in targets.items():
            entry = state['entries'][str(path)]
            if entry['installed'] != value:
                entry['previous'] = entry['installed']
                entry['installed'] = value
    state['phase'] = 'restoring' if restore else 'prepared'
    atomic(journal, (json.dumps(state, indent=2) + '\n').encode())
    for path, value in targets.items():
        write_record(path, value)
    if restore:
        journal.unlink()
    else:
        state['phase'] = 'installed'
        for entry in state['entries'].values():
            entry.pop('previous', None)
        atomic(journal, (json.dumps(state, indent=2) + '\n').encode())
    subprocess.run(['update-desktop-database', str(home / '.local/share/applications')],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def release_commit(tag):
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?', tag):
        raise RuntimeError('Expected an official version tag, not a branch or shell expression')
    result = subprocess.check_output(['git', 'ls-remote', '--tags', UPSTREAM,
                                      'refs/tags/' + tag, 'refs/tags/' + tag + '^{}'], text=True)
    commits = {}
    for line in result.splitlines():
        sha, ref = line.split()
        if re.fullmatch(r'[a-f0-9]{40}', sha):
            commits[ref] = sha
    commit = commits.get('refs/tags/' + tag + '^{}') or commits.get('refs/tags/' + tag)
    if not commit:
        raise RuntimeError('Official release tag was not found')
    return commit


def latest_release():
    request = urllib.request.Request('https://api.github.com/repos/BetterDiscord/BetterDiscord/releases/latest',
                                     headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'Yuru-BetterDiscord-Updater'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if not isinstance(data, dict) or not isinstance(data.get('tag_name'), str):
        raise RuntimeError('Official release response has no version tag')
    if data.get('draft') or data.get('prerelease'):
        raise RuntimeError('Expected a stable official release')
    return data['tag_name']


def stage_build(files, destination, commit):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        atomic(destination / name, source.read_bytes(), 0o644)
    pkgbuild = (destination / 'PKGBUILD').read_text()
    pkgbuild, count = re.subn(r'#commit=[a-f0-9]{40}', '#commit=' + commit, pkgbuild)
    if count != 1:
        raise RuntimeError('Expected exactly one pinned upstream source')
    sums = ['SKIP'] + [hashlib.sha256((destination / name).read_bytes()).hexdigest() for name in FILES[1:]]
    pkgbuild, count = re.subn(r'sha256sums=\([^)]*\)', 'sha256sums=(' + ' '.join(repr(s) for s in sums) + ')', pkgbuild)
    if count != 1:
        raise RuntimeError('Expected one local-source checksum declaration')
    atomic(destination / 'PKGBUILD', pkgbuild.encode(), 0o644)


def build(source=None, ref=None, cache=None):
    files = resources(source)
    for path in files.values():
        if not path.is_file():
            raise RuntimeError('Missing managed build resource: ' + str(path))
    pinned = re.search(r'#commit=([a-f0-9]{40})', files['PKGBUILD'].read_text())
    if not pinned:
        raise RuntimeError('Managed package source has no pinned upstream commit')
    commit = release_commit(ref) if ref else pinned.group(1)
    digest = hashlib.sha256(commit.encode() + b''.join(files[name].read_bytes() for name in FILES)).hexdigest()[:16]
    directory = Path(cache or Path.home() / '.cache/betterdiscord-yuru') / digest
    stage_build(files, directory, commit)
    # No --syncdeps: dependency installation must never invoke sudo implicitly.
    subprocess.run(['makepkg', '--cleanbuild', '--force', '--check', '--noconfirm'], cwd=directory, check=True)
    packages = [Path(name) for name in subprocess.check_output(
        ['makepkg', '--packagelist'], cwd=directory, text=True).splitlines() if Path(name).is_file()]
    candidates = []
    for package in packages:
        info = subprocess.check_output(['bsdtar', '-xOf', str(package), '.PKGINFO'], text=True)
        if 'pkgname = betterdiscord-yuru' in info.splitlines():
            candidates.append(package)
    if len(candidates) != 1:
        raise RuntimeError('Expected exactly one completed betterdiscord-yuru package')
    return candidates[0].resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=('build', 'update', 'install', 'restore', 'status'), default='update')
    parser.add_argument('--ref', help='Official version tag; update defaults to latest stable release')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--source', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    home = Path.home()
    state = home / '.local/state/yuru-theme'
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / 'discord-runtime.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command in ('install', 'restore'):
            if args.command == 'install' and not Path('/usr/bin/discord-yuru').is_file():
                raise RuntimeError('Install the checked betterdiscord-yuru package first')
            manage_launchers(home, restore=args.command == 'restore')
            print('Default Discord launch paths ' + ('installed.' if args.command == 'install' else 'restored.'))
        elif args.command == 'status':
            journal = journal_path(home)
            entry = json.loads(journal.read_text()) if journal.exists() else None
            print(json.dumps({'managed_launchers': bool(entry), 'phase': entry['phase'] if entry else None,
                              'launchers_match': bool(entry) and all(capture_file(Path(name)) == value['installed']
                                  for name, value in entry['entries'].items())}, indent=2))
        else:
            tag = args.ref or (latest_release() if args.command == 'update' else None)
            package = build(args.source, tag)
            print('Checked package:', package, flush=True)
            if args.command == 'update' and not args.build_only:
                subprocess.run(['doas', 'pacman', '-U', '--noconfirm', str(package)], check=True)
                if journal_path(home).exists():
                    manage_launchers(home)
                print('Update installed. Quit and reopen Discord to load it; theme preferences were preserved.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print('Yuru Discord:', error, file=sys.stderr)
        sys.exit(1)
