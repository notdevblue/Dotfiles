#!/usr/bin/env python3
"""Install D2Coding Regular/Bold as the Hangul fallback for Ubuntu Mono."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import zipfile

from theme import atomic_write

VERSION = '1.4.0'
ARCHIVE = 'D2Coding-Ver1.4.0-20261003.zip'
SHA256 = '17e2da5e2879006eb725b87943f7988736ef8b6c9f8b84bc8e3bdbcb8dd46744'


def install(archive):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError('Font archive checksum mismatch')
    destination = Path.home() / '.local/share/fonts/yuru'
    with zipfile.ZipFile(archive) as source:
        files = {f'D2Coding-{weight}.ttf': source.read(
            f'D2Coding/D2Coding{suffix}-Ver{VERSION}-20261003.ttf')
            for weight, suffix in (('Regular', ''), ('Bold', 'Bold'))}
        files['D2Coding-LICENSE.txt'] = source.read('OFL.txt')
    for name, data in files.items():
        atomic_write(destination / name, data)
    subprocess.run(['fc-cache', '-f', str(destination)], check=True, timeout=30)
    print(f'D2Coding {VERSION} Regular/Bold: {destination}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Reuse a downloaded archive; SHA is still checked')
    args = parser.parse_args()
    if args.archive:
        install(args.archive)
        return
    with tempfile.TemporaryDirectory(prefix='yuru-fonts-') as name:
        archive = Path(name) / ARCHIVE
        urllib.request.urlretrieve(f'https://github.com/naver/d2-coding-font/releases/download/VER{VERSION}/{ARCHIVE}', archive)
        install(archive)


if __name__ == '__main__':
    main()
