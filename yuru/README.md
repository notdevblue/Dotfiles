# GMK Yuru / Shima Rin

Minimal Sway rice: dark plum, cream text, mint selection and burgundy borders.
Numeric workspaces, a small bottom bar, ordinary Bash prompts and Rin wallpaper.

This folder is the authoritative rice source. `palette.json` owns colors/fonts;
`templates/` contains the GTK3/4, Qt5/6, Kitty, Rofi, Waybar, Dunst, Fcitx,
gtklock, Code and Firefox settings. `assets/` contains landscape/portrait wallpapers
and their imagegen prompts. `build/` is the ignored, locally rendered configuration.

Wallpapers were made with built-in imagegen:
[landscape](assets/wallpaper.png) ([prompt](assets/wallpaper-prompt.txt)),
[portrait](assets/wallpaper-portrait.png) ([prompt](assets/portrait-wallpaper-prompt.txt)).

Softer-light variants, made with built-in imagegen on 2026-10-31:
[landscape](assets/wallpaper-soft.png) — 1938×812 ([prompt](assets/wallpaper-soft-prompt.txt)),
[portrait](assets/wallpaper-portrait-soft.png) — 812×1937 ([prompt](assets/portrait-wallpaper-soft-prompt.txt)).
Village lamps, sharp water reflections and isolated rim highlights were subdued.
These are generated originals for the owner to upscale to 3440×1440 / 1440×3440;
they are not pre-upscaled or automatically activated. The original assets stay in use.
Dimensions, hashes and editing scope: [record](assets/soft-wallpapers.json).

Subtle retouches of the detailed originals (built-in imagegen, 2026-10-31):
[landscape](assets/wallpaper-retouched.png) ([prompt](assets/wallpaper-retouched-prompt.txt)),
[portrait](assets/wallpaper-portrait-retouched.png) ([prompt](assets/portrait-wallpaper-retouched-prompt.txt)).
Keep the original scenery and detail, with a restrained cleanup of blotches and
the harshest small highlights. [Record](assets/retouched-wallpapers.json).
Saved separately for review/upscaling; no desktop activation.

Active wallpaper selection lives in [`wallpapers.json`](wallpapers.json). It now
selects the owner's 2× waifu2x exports: 3876×1624 landscape and 1624×3870 portrait.
They were applied to DP-6 / DP-5 with `fill` on 2026-10-31. The original generated
files and prompts remain available; the earlier variants above are historical.

The existing `../sway-desktop/` retains input, outputs, gaming/fullscreen rules and
active symlink compatibility paths. Its theme files are generated deployment outputs;
edit this folder's palette/templates to update the rice. Monitor names DP-5/DP-6
and startup hooks target HanUseArch; adjust them for another host.

```sh
# Arch dependencies; use the existing Sway desktop's package list for the base session.
doas pacman -S --needed qt5ct qt6ct
python theme.py build
python theme.py plan
python -m unittest -v test_theme.py
python verify_native.py --rofi
```

`build`/`plan` do not change the active desktop. `install` creates a first backup;
`update` preserves that original backup. Both normally refuse a running Sway.
Use `--live` only when deliberately applying to the current session:

```sh
python theme.py install --live  # first install; use update --live if already installed
python activate.py apply       # visual IPC/config reload only; no full Sway reload
```

Original file backups stay outside Git in `~/.local/state/yuru-theme/` with private
permissions. Unknown edits are never overwritten by restore. To revert, preferably
after leaving the session, run `python activate.py restore-settings` followed by
`python theme.py restore`, then start the existing Sway session again.

Firefox chrome styles load on its next normal startup; current shells pick up the
new prompt when started again. A live theme apply is not a reboot/login verification.
GTK apps also load user CSS at process startup. If Firefox's file chooser still
looks like stock Adwaita, close its dialog and run
`systemctl --user restart xdg-desktop-portal-gtk.service`, then open it again.
Restart only the GTK backend; restarting the main portal can interrupt other portal
requests. A fresh login starts the backend with the saved GTK configuration.
Host-specific application history and persistence scope stay in the private
`private-configs/hosts/hanusearch/docs/yuru-theme.md` document.

## Resource and AI usage monitors

`btop` uses a Yuru theme with square borders, cream text and flat mint graphs.
The default layout shows CPU, GPU, RAM and processes, refreshing every two seconds.
The tested Arch package is 1.4.7 with `GPU_SUPPORT=true`; NVIDIA GPU and VRAM
were verified in a native terminal. Use Rofi's **btop (Yuru)** entry or run `btop`.

**Usage** / `yuru-usage` is a small GTK3 window over the upstream CodexBar CLI,
with the same colors/font and no account identity in its UI. It shows measured
Codex/Grok quota windows, percentage remaining, reset countdown and update time.
Missing windows stay absent; failed refreshes keep the previous result visibly
marked stale. Each provider has an independent, bounded request every five
minutes. `r` refreshes, `q` quits. Closing it stops polling and its child processes.
The apps launch on demand; this change adds no login autostart or Waybar pollers.

```sh
doas pacman -S --needed btop gtk3 python-gobject kitty
python install_codexbar.py       # pinned upstream Linux x86_64 CLI + SHA256 check
python theme.py update --live    # use install for a fresh theme installation
yuru-usage
# CLI-only, identity-free diagnostic snapshot:
yuru-usage --snapshot
```

CodexBar CLI 0.82.0 lives in `~/.local/lib/codexbar-cli/0.82.0/`, including its
resource bundle, with a `~/.local/bin/codexbar` symlink. Authentication stays in
the providers' existing stores. The view does not implement another login flow,
import browser cookies, persist usage data, or require another API key.
Restore theme-managed files with the normal restore flow above. To remove this
separate CLI installation, first close Usage, then remove its exact symlink and
version directory; provider login stores remain untouched.

[CodexBar CLI source](https://github.com/steipete/CodexBar/blob/v0.82.0/docs/cli.md),
[btop configuration](https://github.com/aristocratos/btop).
[Native Usage capture](verification/native-usage.png) uses **synthetic values**;
live provider lookup was checked separately without publishing account data.
Tests cover parsing, missing/zero quotas, invalid percentages, unknown resets,
and subprocess timeout cleanup. Native rendering/relaunch was checked in a
private headless Wayland session; actual OS reboot/login remains untested.

Format evidence: [toolkit notes](toolkit-notes.md), [desktop notes](desktop-notes.md).
Verification: [results](verification/results.json), [Rofi](verification/native-rofi.png).
