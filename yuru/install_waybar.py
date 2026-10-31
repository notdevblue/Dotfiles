#!/usr/bin/env python3
"""Build a pinned Waybar with correct rapid-click handling, installed for this user."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
VERSION = '0.15.0'
RELEASE = VERSION + '-yuru-clicks1'
URL = f'https://github.com/Alexays/Waybar/archive/refs/tags/{VERSION}.tar.gz'
SHA256 = '21c2bbef88c40473c355003582f9331d2f9b8a01efdcce0935edfc5f6b023a3e'
PATCH = ROOT / 'patches/waybar-clicks.patch'
TARGET = Path.home() / '.local/lib/yuru-waybar' / RELEASE
LINK = Path.home() / '.local/bin/waybar'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_existing():
    if LINK.is_symlink():
        if LINK.readlink() != TARGET / 'waybar':
            raise RuntimeError('Existing waybar link belongs to another installation')
    elif LINK.exists():
        raise RuntimeError('Existing waybar executable belongs to another installation')
    if TARGET.is_symlink():
        raise RuntimeError('Refusing a symlink installation directory')
    if TARGET.exists():
        record = json.loads((TARGET / 'installation.json').read_text())
        if (set(p.name for p in TARGET.iterdir()) != {'waybar', 'LICENSE', 'installation.json'}
                or record['source_sha256'] != SHA256
                or record['patch_sha256'] != digest(PATCH)
                or record['binary_sha256'] != digest(TARGET / 'waybar')
                or record['license_sha256'] != digest(TARGET / 'LICENSE')):
            raise RuntimeError('Existing installation changed; inspect it before replacing/removing')


def install(binary, license_file):
    check_existing()
    if not TARGET.exists():
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.install-', dir=TARGET.parent) as name:
            staging = Path(name) / RELEASE
            staging.mkdir()
            shutil.copy2(binary, staging / 'waybar')
            (staging / 'waybar').chmod(0o755)
            shutil.copy2(license_file, staging / 'LICENSE')
            record = {'version': RELEASE, 'source_url': URL, 'source_sha256': SHA256,
                      'patch_sha256': digest(PATCH), 'binary_sha256': digest(staging / 'waybar'),
                      'license_sha256': digest(staging / 'LICENSE')}
            (staging / 'installation.json').write_text(json.dumps(record, indent=2) + '\n')
            os.rename(staging, TARGET)
    LINK.parent.mkdir(parents=True, exist_ok=True)
    if not LINK.is_symlink():
        LINK.symlink_to(TARGET / 'waybar')
    print(f'Waybar {RELEASE}: {LINK}')


def build(archive, jobs):
    if digest(archive) != SHA256:
        raise RuntimeError('Waybar source archive checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='yuru-waybar-build-') as name:
        directory = Path(name)
        with tarfile.open(archive) as package:
            package.extractall(directory, filter='data')
        source = directory / ('Waybar-' + VERSION)
        subprocess.run(['patch', '-p1', '--input', str(PATCH)], cwd=source, check=True, timeout=10)
        output = directory / 'build'
        subprocess.run(['meson', 'setup', str(output), str(source), '--prefix=/usr',
                        '--buildtype=release', '--auto-features=enabled', '--wrap-mode=nodownload',
                        '-Dcpp_std=c++20', '-Dexperimental=true', '-Dcava=disabled',
                        '-Dtests=disabled', '-Dman-pages=disabled'], check=True, timeout=60)
        subprocess.run(['meson', 'compile', '-C', str(output), '-j', str(jobs)],
                       check=True, timeout=900)
        install(output / 'waybar', source / 'LICENSE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Reuse the pinned source archive; SHA is checked')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--remove', action='store_true', help='Remove only this owned user installation')
    args = parser.parse_args()
    check_existing()
    if args.remove:
        if LINK.is_symlink():
            LINK.unlink()
        if TARGET.exists():
            shutil.rmtree(TARGET)
        print('Removed the user Waybar override; the next start uses the system package.')
        return
    if TARGET.exists():
        install(TARGET / 'waybar', TARGET / 'LICENSE')
        return
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    for command in ['meson', 'ninja', 'patch', 'gdbus-codegen', 'c++', 'pkg-config']:
        if not shutil.which(command):
            raise RuntimeError('Missing build tool: ' + command)
    if args.archive:
        build(args.archive.resolve(), args.jobs)
    else:
        with tempfile.TemporaryDirectory(prefix='yuru-waybar-source-') as name:
            archive = Path(name) / 'source.tar.gz'
            with urllib.request.urlopen(URL, timeout=30) as response:
                archive.write_bytes(response.read())
            build(archive, args.jobs)


if __name__ == '__main__':
    main()
