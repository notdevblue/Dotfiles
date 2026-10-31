#!/usr/bin/env python3
"""Install the reviewed Millennium stable binary as an Arch package using doas.

Only installs the framework/official loader links. Select Yuru in Steam afterward.
No Steam account data, client preferences or update channel are changed.
"""
import hashlib
import os
from pathlib import Path
import platform
import pwd
import subprocess
import tempfile
import urllib.request

VERSION = '3.6.2'
COMMIT = '88fb7c16d04d162cb3e94beedb11a51705ec03fb'
REPO = 'https://github.com/SteamClientHomebrew/Millennium'
ARCHIVE_SHA = '95bda40184dd6437da1668060ec5961c762f3c1e59923f53380e43d4e720f359'
LICENSE_SHA = 'f01d1b8bce439ee29491817247a38611c41f7d1de4360b5577d4498d103fbf8b'
HOOK_SHA = '69903a7e9e0f1b987e6189b825b78f6bc86b19403bddded4be3ca5aa040df413'


def main():
    if os.getuid() == 0 or platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise RuntimeError('Run as the desktop user on Arch Linux x86_64')
    subprocess.run(['pacman', '-Q', 'steam'], check=True)
    # Upstream's root pacman hook visits every desktop account and repairs old
    # launcher patches. This helper is deliberately for one-user desktops.
    others = [p for p in pwd.getpwall() if p.pw_uid >= 1000 and p.pw_uid != os.getuid()
              and p.pw_dir not in ('/', '/nonexistent', '/var/empty')]
    if others:
        raise RuntimeError('Review the upstream loader hook manually on multi-user hosts')
    launcher = Path('/usr/bin/steam')
    legacy = Path('/usr/bin/steam.millennium.bak')
    if legacy.exists() or legacy.is_symlink() or 'LD_PRELOAD' in launcher.read_text():
        raise RuntimeError('Review the legacy Steam launcher patch before running the upstream hook')
    root = Path.home() / '.local/share/Steam'
    if not root.is_dir():
        raise RuntimeError('Start native Steam once before installing Millennium')
    for bit, library in [('32', 'libmillennium_bootstrap_x86.so'),
                         ('64', 'libmillennium_bootstrap_hhx64.so')]:
        link = root / f'ubuntu12_{bit}/libXtst.so.6'
        expected = Path('/usr/lib/millennium') / library
        if (link.exists() or link.is_symlink()) and not (link.is_symlink() and link.readlink() == expected):
            raise RuntimeError('Review the existing loader before replacing: ' + str(link))
    with tempfile.TemporaryDirectory(prefix='yuru-millennium-') as name:
        work = Path(name)
        archive = f'millennium-v{VERSION}-linux-x86_64.tar.gz'
        sources = [
            (archive, f'{REPO}/releases/download/v{VERSION}/{archive}', ARCHIVE_SHA),
            ('LICENSE.md', f'https://raw.githubusercontent.com/SteamClientHomebrew/Millennium/{COMMIT}/LICENSE.md', LICENSE_SHA),
            ('millennium.install', f'https://raw.githubusercontent.com/SteamClientHomebrew/Millennium/{COMMIT}/packages/arch/millennium.install', HOOK_SHA),
        ]
        for filename, url, checksum in sources:
            target = work / filename
            urllib.request.urlretrieve(url, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != checksum:
                raise RuntimeError('Upstream checksum mismatch: ' + filename)
        # The official pacman hook links both Steam loaders on install/upgrade
        # and removes them on uninstall. No shell installer is downloaded/run.
        (work / 'PKGBUILD').write_text(f'''pkgname=millennium-bin
pkgver={VERSION}
pkgrel=1
pkgdesc='Steam Client theme and plugin framework (official stable binary)'
arch=('x86_64')
url='{REPO}'
license=('MIT')
depends=('steam')
provides=('millennium')
conflicts=('millennium' 'millennium-git')
options=('!strip')
install=millennium.install
source=('{archive}' 'LICENSE.md')
sha256sums=('{ARCHIVE_SHA}' '{LICENSE_SHA}')
package() {{
    install -d "$pkgdir/usr/lib/millennium"
    install -m755 "$srcdir"/usr/lib/millennium/* "$pkgdir/usr/lib/millennium/"
    install -Dm644 "$srcdir/LICENSE.md" "$pkgdir/usr/share/licenses/millennium/LICENSE.md"
}}
''')
        subprocess.run(['makepkg', '--noconfirm'], cwd=work, check=True)
        packages = subprocess.check_output(['makepkg', '--packagelist'], cwd=work, text=True).splitlines()
        if len(packages) != 1:
            raise RuntimeError('Expected exactly one framework package')
        subprocess.run(['doas', 'pacman', '-U', '--noconfirm', packages[0]], check=True)
    print('Millennium installed. Restart Steam, then select the Yuru theme.')


if __name__ == '__main__':
    main()
