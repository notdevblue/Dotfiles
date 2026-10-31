#!/usr/bin/env python3
"""Install only Sarasa Mono K Regular/Bold for browser chrome, with pinned SHA."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

from theme import atomic_write

VERSION = '1.0.43'
ARCHIVE = f'SarasaMonoK-TTF-{VERSION}.7z'
SHA256 = '0570424cd4424f9c93300cc4470e917bdd2dbb18364cc0279d3a54e93da87a03'


def install(archive):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError('Font archive checksum mismatch')
    destination = Path.home() / '.local/share/fonts/yuru'
    license_url = f'https://raw.githubusercontent.com/be5invis/Sarasa-Gothic/v{VERSION}/LICENSE'
    license_text = urllib.request.urlopen(license_url, timeout=30).read()
    fonts = {}
    for weight in ('Regular', 'Bold'):
        name = f'SarasaMonoK-{weight}.ttf'
        fonts[name] = subprocess.check_output(['bsdtar', '-xOf', str(archive), name], timeout=60)
    for name, data in fonts.items():
        atomic_write(destination / name, data)
    atomic_write(destination / 'LICENSE.txt', license_text)
    subprocess.run(['fc-cache', '-f', str(destination)], check=True, timeout=30)
    print(f'Sarasa Mono K {VERSION} Regular/Bold: {destination}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Reuse a downloaded archive; SHA is still checked')
    args = parser.parse_args()
    if not shutil.which('bsdtar'):
        raise RuntimeError('Install libarchive for bsdtar')
    if args.archive:
        install(args.archive)
        return
    with tempfile.TemporaryDirectory(prefix='yuru-fonts-') as name:
        archive = Path(name) / ARCHIVE
        urllib.request.urlretrieve(f'https://github.com/be5invis/Sarasa-Gothic/releases/download/v{VERSION}/{ARCHIVE}', archive)
        install(archive)


if __name__ == '__main__':
    main()
