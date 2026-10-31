#!/usr/bin/env python3
"""Build and review offline; install/restore only outside an active Sway session.

No command reloads the desktop, starts apps, writes gsettings, or installs packages.
Backups contain private original settings and stay in local state, never this repo.
"""
import argparse
import configparser
import hashlib
import json
import os
import pwd
from pathlib import Path
import re
import shutil
import stat
import tempfile
import zipfile

import chrome_theme

ROOT = Path(__file__).resolve().parent
BEGIN = '# BEGIN yuru-theme'
END = '# END yuru-theme'


def render(text, palette):
    tokens = {k.upper(): v for k, v in palette.items() if isinstance(v, str)}
    tokens.update({f'ANSI{i}': c for i, c in enumerate(palette['ansi'])})
    tokens.update({name + '_HEX': value[1:] for name, value in list(tokens.items())
                   if re.fullmatch(r'#[0-9A-Fa-f]{6}', value)})
    for name in ('FG', 'MINT'):
        color = tokens[name].lstrip('#')
        tokens[name + '_RGB'] = ';'.join(str(int(color[i:i+2], 16)) for i in (0, 2, 4))
    def replace(m):
        if m[1] not in tokens:
            raise ValueError('Unknown palette token: ' + m[1])
        return tokens[m[1]]
    return re.sub(r'@([A-Z0-9_]+)@', replace, text)


def build():
    palette = json.loads((ROOT / 'palette.json').read_text())
    for key, value in palette.items():
        if key not in ('font', 'browser_font', 'ansi') and not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            raise ValueError('Invalid color: ' + key)
    if len(palette['ansi']) != 16 or not all(re.fullmatch(r'#[0-9A-Fa-f]{6}', c) for c in palette['ansi']):
        raise ValueError('Expected sixteen ANSI colors')
    destination = ROOT / 'build'
    if destination.is_symlink():
        raise RuntimeError('Generated build directory must not be a symlink')
    destination.mkdir(exist_ok=True)
    # Replace only our generated tree; no active home paths are involved.
    with tempfile.TemporaryDirectory(dir=ROOT, prefix='.render-') as temporary:
        out = Path(temporary)
        for source in sorted((ROOT / 'templates').rglob('*')):
            if not source.is_file() or '__pycache__' in source.parts or source.suffix in ('.pyc', '.pyo'):
                continue
            target = out / source.relative_to(ROOT / 'templates')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render(source.read_text(), palette))
        wallpapers = json.loads((ROOT / 'wallpapers.json').read_text())
        for key, name in [('landscape', 'wallpaper.png'), ('portrait', 'wallpaper-portrait.png')]:
            source = (ROOT / wallpapers[key]).resolve()
            if not source.is_relative_to((ROOT / 'assets').resolve()):
                raise ValueError('Wallpaper must be inside assets: ' + key)
            shutil.copy2(source, out / name)
        chrome_theme.finalize(out / 'chrome')
        with zipfile.ZipFile(out / 'firefox-theme-unsigned.xpi', 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(out / 'firefox/manifest.json', 'manifest.json')
        for child in destination.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        for child in out.iterdir():
            shutil.move(str(child), destination / child.name)
    return destination


def managed_block(text, content, css=False, prepend=False):
    start, end = ('/* BEGIN yuru-theme */', '/* END yuru-theme */') if css else (BEGIN, END)
    text = re.sub(re.escape(start) + r'.*?' + re.escape(end) + r'\n?', '', text, flags=re.S)
    block = start + '\n' + content.rstrip() + '\n' + end + '\n'
    if prepend:
        if text.startswith('#!'):
            first, _, rest = text.partition('\n')
            return first + '\n' + block + rest.lstrip('\n')
        return block + text.lstrip('\n')
    return text.rstrip() + '\n\n' + block


def ini_merge(text, changes):
    """Update only specified INI keys, preserving comments, sections and other keys."""
    group = ''
    pending = {g: dict(v) for g, v in changes.items()}
    output = []
    def flush(name):
        for key, value in pending.pop(name, {}).items():
            output.append(f'{key}={value}')
    for line in text.splitlines():
        match = re.match(r'^\s*\[([^]]+)\]', line)
        if match:
            flush(group)
            group = match[1]
        option = re.match(r'^\s*([^#;\s][^=]*?)\s*=', line)
        if option and option[1].strip() in changes.get(group, {}):
            key = option[1].strip()
            line = f'{key}={changes[group][key]}'
            pending.get(group, {}).pop(key, None)
        output.append(line)
    flush(group)
    for group in list(pending):
        if group:
            output.append(f'[{group}]')
        flush(group)
    return '\n'.join(output) + '\n'


def deployment(home, output):
    """Return concrete destination bytes without modifying home or starting anything."""
    targets = {}
    palette = json.loads((ROOT / 'palette.json').read_text())
    qt_ready = all(Path(p).is_file() for p in ['/usr/lib/qt/plugins/platformthemes/libqt5ct.so', '/usr/lib/qt6/plugins/platformthemes/libqt6ct.so'])
    def copy(source, relative):
        targets[relative] = (output / source).read_bytes()
    def old(relative):
        path = home / relative
        return path.read_text() if path.exists() else ''
    def patch(relative, content, css=False):
        targets[relative] = managed_block(old(relative), content, css).encode()
    for source, relative in [
        ('wallpaper.png', '.local/share/yuru-theme/wallpaper.png'),
        ('sway/appearance.conf', '.local/share/yuru-theme/sway.conf'),
        ('sway/effects.conf', '.local/share/yuru-theme/effects.conf'),
        ('bash/prompt.bash', '.local/share/yuru-theme/prompt.bash'),
        ('kitty/theme.conf', '.config/kitty/yuru-theme.conf'),
        ('rofi/config.rasi', '.config/rofi/config.rasi'),
        ('dunst/dunstrc', '.config/dunst/dunstrc'),
        ('waybar/config.jsonc', '.config/waybar/config.jsonc'),
        ('waybar/style.css', '.config/waybar/style.css'),
        ('gtklock/style.css', '.config/gtklock/style.css'),
        ('btop/yuru.theme', '.config/btop/themes/yuru.theme'),
        ('monitor/usage.py', '.local/share/yuru-theme/usage.py'),
        ('monitor/usage.css', '.local/share/yuru-theme/usage.css'),
        ('monitor/yuru-usage', '.local/bin/yuru-usage'),
        ('monitor/usage.desktop', '.local/share/applications/yuru-usage.desktop'),
        ('monitor/btop.desktop', '.local/share/applications/yuru-btop.desktop'),
    ]:
        copy(source, relative)
    btop_options = {}
    for line in (output / 'btop/btop.conf').read_text().splitlines():
        key, value = line.split('=', 1)
        btop_options[key.strip()] = value.strip()
    relative = '.config/btop/btop.conf'
    targets[relative] = ini_merge(old(relative), {'': btop_options}).encode()
    # Warning/error types override the global defaults, so merge their colors too.
    swaynag = configparser.ConfigParser(interpolation=None)
    swaynag.optionxform = str
    swaynag.read_string('[general]\n' + (output / 'swaynag/config').read_text())
    options = {('' if s == 'general' else s): dict(swaynag[s]) for s in swaynag.sections()}
    relative = '.config/swaynag/config'
    targets[relative] = ini_merge(old(relative), options).encode()
    for source in (output / 'chrome').iterdir():
        copy('chrome/' + source.name, '.local/share/yuru-theme/chrome/' + source.name)
    patch('.bashrc', '[ -r "$HOME/.local/share/yuru-theme/prompt.bash" ] && source "$HOME/.local/share/yuru-theme/prompt.bash"')
    patch('.config/kitty/kitty.conf', 'include yuru-theme.conf')
    # Base config is included by stock, detached and SwayFX entry points.
    patch('.config/sway/config', 'include ~/.local/share/yuru-theme/sway.conf')
    if (home / '.config/sway/config.swayfx').exists():
        patch('.config/sway/config.swayfx', 'include ~/.local/share/yuru-theme/effects.conf')
    for major in (3, 4):
        directory = f'.config/gtk-{major}.0'
        copy(f'gtk-{major}.0/gtk.css', f'{directory}/yuru.css')
        patch(f'{directory}/gtk.css', '@import url("yuru.css");', css=True)
        settings = f'{directory}/settings.ini'
        targets[settings] = ini_merge(old(settings), {'Settings': {
            'gtk-theme-name': 'Adwaita', 'gtk-font-name': palette['font'] + ' 11',
            'gtk-icon-theme-name': 'Adwaita', 'gtk-cursor-theme-name': 'Adwaita',
            'gtk-application-prefer-dark-theme': '1'}}).encode()
    for source in (output / 'fcitx5/themes/yuru').iterdir():
        copy(str(source.relative_to(output)), '.local/share/fcitx5/themes/yuru/' + source.name)
    relative = '.config/fcitx5/conf/classicui.conf'
    selection = {}
    for line in (output / 'fcitx5/conf/classicui.conf').read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            selection[key] = value
    targets[relative] = ini_merge(old(relative), {'': selection}).encode()
    # Preserve all unrelated JSON keys. JSONC profiles require a reviewed manual merge.
    relative = '.config/Code - OSS/User/settings.json'
    try:
        settings = json.loads(old(relative) or '{}')
    except json.JSONDecodeError:
        settings = None
    if isinstance(settings, dict):
        fragment = json.loads((output / 'code/settings.fragment.json').read_text())
        def merge(destination, source):
            for key, value in source.items():
                if isinstance(value, dict) and isinstance(destination.get(key), dict):
                    merge(destination[key], value)
                else:
                    destination[key] = value
        merge(settings, fragment)
        targets[relative] = (json.dumps(settings, ensure_ascii=False, indent=2) + '\n').encode()
    if (output / 'wallpaper-portrait.png').exists():
        targets['.local/share/yuru-theme/wallpaper-portrait.png'] = (output / 'wallpaper-portrait.png').read_bytes()
        relative = '.local/share/yuru-theme/sway.conf'
        targets[relative] += b'output DP-5 bg ~/.local/share/yuru-theme/wallpaper-portrait.png fill\n'
    if qt_ready:
        copy('qt-common/environment.sh', '.local/share/yuru-theme/qt-env.sh')
        targets['.config/environment.d/10-yuru-theme.conf'] = b'QT_QPA_PLATFORMTHEME=qt5ct\n'
        for major in (5, 6):
            for child in ['colors/yuru.conf', 'qss/yuru.qss']:
                copy(f'qt{major}ct/{child}', f'.config/qt{major}ct/{child}')
            fragment = configparser.ConfigParser(interpolation=None)
            fragment.optionxform = str
            fragment.read(output / f'qt{major}ct/qt{major}ct.conf.fragment')
            changes = {s: {k: v.replace('/home/han', str(home)) for k, v in fragment[s].items()} for s in fragment.sections()}
            relative = f'.config/qt{major}ct/qt{major}ct.conf'
            targets[relative] = ini_merge(old(relative), changes).encode()
        for app in ['rofi', 'vlc', 'fcitx5-configtool']:
            copy('qt-common/launcher.sh', '.local/bin/' + app)
        patch('.bashrc', '[ -r "$HOME/.local/share/yuru-theme/qt-env.sh" ] && source "$HOME/.local/share/yuru-theme/qt-env.sh"\n'
              '[ -r "$HOME/.local/share/yuru-theme/prompt.bash" ] && source "$HOME/.local/share/yuru-theme/prompt.bash"')
        relative = '.local/bin/start-sway'
        if (home / relative).exists():
            targets[relative] = managed_block(old(relative), '[ ! -r "$HOME/.local/share/yuru-theme/qt-env.sh" ] || . "$HOME/.local/share/yuru-theme/qt-env.sh"', prepend=True).encode()
        relative = '.config/sway/scripts/session-start'
        if (home / relative).exists():
            targets[relative] = managed_block(old(relative), 'if [ -n "${QT_QPA_PLATFORMTHEME:-}" ]; then\n    dbus-update-activation-environment --systemd QT_QPA_PLATFORMTHEME\nfi', prepend=True).encode()
        targets['.config/kitty/yuru-theme.conf'] += b'\nenv QT_QPA_PLATFORMTHEME=qt5ct\n'
    # Firefox styles load on normal restart; content rules target Home/New Tab only.
    for base in [home / '.config/mozilla/firefox', home / '.mozilla/firefox']:
        ini = base / 'profiles.ini'
        if not ini.exists():
            continue
        profiles = configparser.ConfigParser(interpolation=None)
        profiles.read(ini)
        candidates, defaults, install_defaults = [], [], []
        for section in profiles.sections():
            if section.startswith('Install') and profiles.has_option(section, 'Default'):
                value = Path(profiles[section]['Default'])
                profile = base / value if not value.is_absolute() else value
                if profile.resolve().is_relative_to(home.resolve()) and profile.is_dir():
                    install_defaults.append(profile)
            if not profiles.has_option(section, 'Path'):
                continue
            value = Path(profiles[section]['Path'])
            profile = base / value if profiles[section].get('IsRelative') == '1' else value
            if not profile.resolve().is_relative_to(home.resolve()):
                continue
            if (profile / 'lock').is_symlink():
                candidates.append(profile)
            if profiles[section].get('Default') == '1':
                defaults.append(profile)
        selected = candidates if candidates else (list(dict.fromkeys(install_defaults)) or defaults)
        if len(selected) != 1:
            continue
        profile = selected[0]
        # Never incidentally activate unknown site CSS. Our owned New Tab import
        # is expected on subsequent updates and remains safe to manage.
        content = profile / 'chrome/userContent.css'
        if content.exists() and '@import url("yuru-content.css");' not in content.read_text():
            continue
        relative = str(profile.relative_to(home))
        copy('firefox/userChrome.css', relative + '/chrome/yuru.css')
        css = relative + '/chrome/userChrome.css'
        targets[css] = managed_block(old(css), '@import url("yuru.css");', css=True, prepend=True).encode()
        copy('firefox/userContent.css', relative + '/chrome/yuru-content.css')
        copy('wallpaper.png', relative + '/chrome/yuru-newtab.png')
        copy('wallpaper-portrait.png', relative + '/chrome/yuru-newtab-portrait.png')
        css = relative + '/chrome/userContent.css'
        targets[css] = managed_block(old(css), '@import url("yuru-content.css");', css=True, prepend=True).encode()
        js = relative + '/user.js'
        targets[js] = managed_block(old(js), (output / 'firefox/user.js.fragment').read_text(), css=True).encode()
        break
    return targets


def digest(data):
    return hashlib.sha256(data).hexdigest()


def idle_guard(home):
    # Offline fixtures may use another home; live installation requires ending Sway first.
    # This makes accidental execution during this user's running game harmless.
    if home.resolve() != Path(pwd.getpwuid(os.getuid()).pw_dir).resolve():
        return
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid == os.getuid() and (entry / 'comm').read_text().strip() in ('sway', 'swayfx'):
                raise RuntimeError('Sway is running. Install/restore is offline only; finish the game and leave the session first.')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.yuru-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def state_directory(home):
    state = home / '.local/state/yuru-theme'
    if state.is_symlink():
        raise RuntimeError('Backup state directory must not be a symlink')
    resolved = state.resolve()
    if not resolved.is_relative_to(home.resolve()):
        raise RuntimeError('Backup state must remain inside user home')
    if any((parent / '.git').exists() for parent in [resolved, *resolved.parents]):
        raise RuntimeError('Private backups must not be placed inside a Git repository')
    return resolved


def install(home, output, allow_live=False):
    if not allow_live:
        idle_guard(home)
    state = state_directory(home)
    if (state / 'transaction.json').exists():
        raise RuntimeError('An installation backup already exists; restore it before another install.')
    targets = deployment(home, output)
    # Resolve symlinks to retain existing dotfiles ownership and symlink structure.
    entries = []
    resolved = set()
    for relative, data in targets.items():
        logical = home / relative
        target = logical.resolve()
        if not target.is_relative_to(home.resolve()):
            raise RuntimeError('Refusing a symlink outside user home: ' + relative)
        if target in resolved:
            raise RuntimeError('Two destinations resolve to the same file: ' + relative)
        resolved.add(target)
        if logical.is_symlink() and not logical.exists():
            raise RuntimeError('Refusing dangling symlink: ' + relative)
        previous = target.read_bytes() if target.exists() else None
        entries.append({'relative': relative, 'resolved': str(target),
                        'existed': previous is not None,
                        'mode': stat.S_IMODE(target.stat().st_mode) if previous is not None else 0o644,
                        'install_mode': 0o755 if relative.startswith('.local/bin/') else (stat.S_IMODE(target.stat().st_mode) if previous is not None else 0o644),
                        'before': digest(previous) if previous is not None else None,
                        'after': digest(data)})
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state, 0o700)
    for index, entry in enumerate(entries):
        if entry['existed']:
            atomic_write(state / f'{index}.backup', Path(entry['resolved']).read_bytes(), 0o600)
    transaction = {'status': 'prepared', 'entries': entries}
    def save():
        atomic_write(state / 'transaction.json', (json.dumps(transaction, indent=2)+'\n').encode(), 0o600)
    save()
    try:
        for entry in entries:
            target = Path(entry['resolved'])
            if str((home / entry['relative']).resolve()) != entry['resolved']:
                raise RuntimeError('Destination symlink changed during installation: ' + entry['relative'])
            if (digest(target.read_bytes()) if target.exists() else None) != entry['before']:
                raise RuntimeError('Destination changed since preparation: ' + entry['relative'])
            atomic_write(target, targets[entry['relative']], entry.get('install_mode', entry['mode']))
        transaction['status'] = 'installed'
        save()
    except Exception:
        transaction['status'] = 'interrupted'
        save()
        restore(home, allow_live=allow_live)
        raise
    return len(entries)


def amend(home, output, allow_live=False, only=None):
    """Extend an installed theme while retaining the original installation backups."""
    if not allow_live:
        idle_guard(home)
    state = state_directory(home)
    transaction = json.loads((state / 'transaction.json').read_text())
    if transaction['status'] != 'installed':
        raise RuntimeError('Recover the interrupted transaction before updating')
    targets = deployment(home, output)
    if only is not None:
        unknown = set(only) - targets.keys()
        if unknown:
            raise ValueError('Unknown update target: ' + ', '.join(sorted(unknown)))
        targets = {key: value for key, value in targets.items() if key in only}
    entries = transaction['entries']
    index = {e['relative']: e for e in entries}
    for relative, data in targets.items():
        path = (home / relative).resolve()
        if not path.is_relative_to(home.resolve()):
            raise RuntimeError('Refusing a target outside home: ' + relative)
        current = digest(path.read_bytes()) if path.exists() else None
        if relative in index:
            entry = index[relative]
            if entry['resolved'] != str(path) or current != entry['after']:
                raise RuntimeError('Installed target changed; review before update: ' + relative)
            entry['previous_after'] = current
            entry['after'] = digest(data)
        else:
            entry = {'relative': relative, 'resolved': str(path), 'existed': path.exists(),
                     'mode': stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644,
                     'before': current, 'after': digest(data)}
            if entry['existed']:
                atomic_write(state / f'{len(entries)}.backup', path.read_bytes(), 0o600)
            entries.append(entry)
            index[relative] = entry
        entry['install_mode'] = 0o755 if relative.startswith('.local/bin/') else entry['mode']
    transaction['status'] = 'updating'
    def save():
        atomic_write(state / 'transaction.json', (json.dumps(transaction, indent=2)+'\n').encode(), 0o600)
    save()
    try:
        for relative, data in targets.items():
            entry = index[relative]
            path = Path(entry['resolved'])
            if (home / relative).resolve() != path:
                raise RuntimeError('Destination symlink changed: ' + relative)
            expected = entry.get('previous_after', entry['before'])
            if (digest(path.read_bytes()) if path.exists() else None) != expected:
                raise RuntimeError('Destination changed during update: ' + relative)
            atomic_write(path, data, entry['install_mode'])
        transaction['status'] = 'installed'
        for entry in entries:
            entry.pop('previous_after', None)
        save()
    except Exception:
        # Keep the journal for reviewed recovery; never overwrite unknown post-update edits.
        save()
        raise
    return len(entries)


def restore(home, allow_live=False):
    if not allow_live:
        idle_guard(home)
    state = state_directory(home)
    if (state / 'chatgpt-before.json').exists():
        raise RuntimeError('Restore ChatGPT appearance first: python chatgpt_theme.py restore')
    transaction = json.loads((state / 'transaction.json').read_text())
    entries = transaction['entries']
    partial = transaction['status'] in ('prepared', 'interrupted', 'restoring', 'updating')
    # Never clobber edits made after installation, nor unexpectedly retargeted symlinks.
    for index, entry in enumerate(entries):
        logical = home / entry['relative']
        if str(logical.resolve()) != entry['resolved']:
            raise RuntimeError('Destination symlink changed: ' + entry['relative'])
        target = Path(entry['resolved'])
        current = digest(target.read_bytes()) if target.exists() else None
        allowed = {entry['before'], entry['after']} if partial else {entry['after']}
        if partial and 'previous_after' in entry:
            allowed.add(entry['previous_after'])
        if current not in allowed:
            raise RuntimeError('Post-install edits need review; backups retained: ' + entry['relative'])
        if entry['existed'] and digest((state / f'{index}.backup').read_bytes()) != entry['before']:
            raise RuntimeError('Backup checksum mismatch: ' + entry['relative'])
    transaction['status'] = 'restoring'
    atomic_write(state / 'transaction.json', (json.dumps(transaction, indent=2)+'\n').encode(), 0o600)
    for index, entry in reversed(list(enumerate(entries))):
        target = Path(entry['resolved'])
        if entry['existed']:
            atomic_write(target, (state / f'{index}.backup').read_bytes(), entry['mode'])
        else:
            target.unlink(missing_ok=True)
    if (state / 'runtime-before.json').exists():
        atomic_write(state.parent / 'yuru-theme-preferences-before.json', (state / 'runtime-before.json').read_bytes(), 0o600)
    shutil.rmtree(state)
    return len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'plan', 'install', 'update', 'restore'])
    parser.add_argument('--live', action='store_true', help='Explicitly allow authorized file installation/restoration while Sway runs; does not reload or restart anything')
    parser.add_argument('--home', type=Path, default=Path(pwd.getpwuid(os.getuid()).pw_dir), help='Alternate home for isolated offline fixtures')
    parser.add_argument('--only', action='append', help='Update only this home-relative managed file; repeat for multiple files')
    args = parser.parse_args()
    if args.only and args.command != 'update':
        parser.error('--only is supported by update only')
    home = args.home.expanduser().absolute()
    if args.command == 'restore':
        print('Restored files:', restore(home, allow_live=args.live))
        return
    output = build()
    if args.command == 'build':
        print(output)
    elif args.command == 'install':
        print('Installed files:', install(home, output, allow_live=args.live))
        print('No applications or services were started. Start the existing Sway session normally.')
    elif args.command == 'update':
        count = amend(home, output, allow_live=args.live, only=args.only)
        print('Updated selected files:' if args.only else 'Updated managed files:', len(set(args.only)) if args.only else count)
    else:
        for relative, data in deployment(home, output).items():
            target = home / relative
            before = target.read_bytes() if target.exists() else None
            action = 'unchanged' if before == data else ('new' if before is None else 'update')
            print(f'{action:9} {relative}')
        print('Deferred: JSONC Code profiles; Firefox styles apply on normal restart; unknown userContent.css profiles require review.')


if __name__ == '__main__':
    main()
