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
Host-specific application history and persistence scope stay in the private
`private-configs/hosts/hanusearch/docs/yuru-theme.md` document.

Format evidence: [toolkit notes](toolkit-notes.md), [desktop notes](desktop-notes.md).
Verification: [results](verification/results.json), [Rofi](verification/native-rofi.png).
