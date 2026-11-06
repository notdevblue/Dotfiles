# Login and lock screen

The default login path is `greetd.service` → stock Sway using
`/etc/greetd/sway-config` → `/etc/greetd/greeter.sh` →
`/usr/local/lib/regreet-yuru/regreet`. Successful authentication still goes
through ReGreet's greetd IPC/PAM implementation and launches the saved session
(`swayfx.desktop` → `start-sway`). No password, account database or greeter state
is part of this repository.

The gtklock image and login image were already identical. The difference was
ReGreet's separate top clock and central user/session frame, plus its larger
font and default spacing. `patches/regreet-lock-layout.patch` moves the existing
clock widget into the form, hides the username row while entering a password,
and keeps Cancel available to change users/sessions. It changes presentation,
not authentication. The patch is pinned to [upstream ReGreet 0.5.0](https://github.com/rharish101/ReGreet/tree/0.5.0) commit
`290e6f8d65b7034c5b63bc950a20bcf8277ebe5f`; the packaged `/usr/bin/regreet`
remains available for rollback.

`greetd/regreet.css` matches gtklock's panel color/opacity, 1px border, square
corners, 28×32px padding, 560px bottom margin, 64px time and 16px date. The time
and date share the existing clock's update timer through Pango markup in
`greetd/regreet.toml`. Login-specific Cancel/Reboot/Power Off controls remain
available. `skip_selection=true` uses ReGreet's saved user/session after a
successful login; a fresh machine still shows the necessary selection screen.

## Build and apply

After restoring/building the [Yuru lock theme](../../yuru/README.md#잠금화면):

```sh
doas pacman -S --needed rust git pkgconf gtk4 glycin gcc
# Run from the dotfiles checkout as the desktop user:
sway-desktop/bin/build-regreet-yuru
sway-desktop/bin/install-greetd
```

The builder uses the upstream locked Cargo dependencies and caches compilation
under `~/.cache/regreet-yuru/target`. Its installed output is
`~/.local/lib/regreet-yuru/regreet`. The installer escalates with `doas`, checks
all required inputs, validates Sway with a private headless backend, and copies
the executable into the root-owned system path. The login does not depend on a
home directory being mounted or the build cache surviving. Calling the installer
as root requires passing the user's built binary path explicitly.

The installer copies the current generated `config/gtklock/background.png` to
`/etc/greetd/background.png`; rerun it after changing the lock scene. It also
installs the saved session entry and pacman hook which hides the packaged Sway
session. It enables `greetd.service` and leaves its current process running.
The next normal logout or boot starts the saved login configuration.
Do not restart the display-manager service from inside a working desktop.

A later ReGreet/GTK ABI update may require rebuilding the pinned variant. Apply
the patch to a reviewed newer upstream revision and rerun the native checks
before changing the pinned version. Ordinary package updates do not overwrite
`/usr/local/lib/regreet-yuru/regreet` or `/etc/greetd` custom files.

## Verification and rollback

```sh
cd yuru
python verify_regreet.py
```

This opens only private headless Sway/ReGreet demo processes. Demo credentials
are upstream test values; it never authenticates to PAM, launches a real login,
or writes the live greeter cache. The report and portrait preview are
[`regreet.json`](../../yuru/verification/regreet.json) and
[`regreet-msi.png`](../../yuru/verification/regreet-msi.png).

For rollback, from the dotfiles checkout restore the last stock layout:

```sh
restore_dir=$(mktemp -d)
for name in regreet.css regreet.toml greeter.sh; do
    git show "057f4d0:sway-desktop/greetd/$name" > "$restore_dir/$name"
done
doas install -m644 "$restore_dir/regreet.css" "$restore_dir/regreet.toml" /etc/greetd/
doas install -m755 "$restore_dir/greeter.sh" /etc/greetd/greeter.sh
rm -r "$restore_dir"
```

This restores `/usr/bin/regreet` as the executable. Keep the generated
background and compositor/session files. The old top-clock/selection layout
returns at the next login screen. Remove
`/usr/local/lib/regreet-yuru` only after the script uses `/usr/bin/regreet`.
No authentication or saved user/session state needs restoring.

Verified 2026-11-07: build from pinned source, saved system paths and service
activation structure. Native rendering/input results are recorded in the linked
report. Actual user logout/login, PAM authentication, OS reboot and physical
monitor reconnection were not performed for this change.
