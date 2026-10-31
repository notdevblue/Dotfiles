#!/usr/bin/env python3
"""Install the pinned upstream Linux CLI in user space; never edit login stores."""
import hashlib
from pathlib import Path
import platform
import shutil
import tarfile
import tempfile
import urllib.request

VERSION = '0.82.0'
SHA256 = 'de1b083e0ddce2b92eb2e2d45026f3f88d889d974876e81fde9df7d83e19363e'


def main():
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise RuntimeError('This pinned release targets Linux x86_64')
    home = Path.home()
    target = home / '.local/lib/codexbar-cli' / VERSION
    link = home / '.local/bin/codexbar'
    expected = target / 'codexbar'
    if link.is_symlink():
        if link.readlink() != expected:
            raise RuntimeError('Existing codexbar link belongs to another installation')
    elif link.exists():
        raise RuntimeError('Existing codexbar executable belongs to another installation')
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.download-', dir=target.parent) as name:
            temporary = Path(name)
            archive = temporary / 'cli.tar.gz'
            url = f'https://github.com/steipete/CodexBar/releases/download/v{VERSION}/CodexBarCLI-v{VERSION}-linux-x86_64.tar.gz'
            urllib.request.urlretrieve(url, archive)
            if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
                raise RuntimeError('Release checksum mismatch')
            extracted = temporary / 'unpacked'
            extracted.mkdir()
            with tarfile.open(archive) as package:
                package.extractall(extracted, filter='data')
            if not (extracted / 'CodexBarCLI').is_file() or not (extracted / 'CodexBar_CodexBarCore.bundle').is_dir():
                raise RuntimeError('Incomplete release archive')
            shutil.move(extracted, target)
    if not expected.is_file():
        raise RuntimeError('Incomplete existing installation; inspect before reinstalling')
    link.parent.mkdir(parents=True, exist_ok=True)
    if not link.is_symlink():
        link.symlink_to(expected)
    print(f'CodexBar CLI {VERSION}: {link}')


if __name__ == '__main__':
    main()
