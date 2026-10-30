# Sway desktop

Arch/Sway adaptation of `shimarin`, using the repo's YoRHa Rofi theme as a
launcher base. Original rice directories are preserved. The active files are
symlinked from `~/.config` into this directory.

`packages.txt` records the installed desktop and gaming packages. Steam needs
the `[multilib]` repository enabled in `/etc/pacman.conf`.

Start from a local TTY as han:

```sh
~/.local/bin/start-sway
```

Kitty, Dunst, Waybar, Fcitx5, wallpaper and locking start with the session.
Right Alt toggles English/Korean (두벌식). The initial input state is English.
Sway remaps Right Alt to the Hangul keysym, which is Fcitx5's toggle key.
Use `fcitx5-configtool` to adjust input methods.

| Shortcut | Action |
| --- | --- |
| Super+Enter | Kitty |
| Super+D | Rofi application launcher |
| Super+B | Firefox |
| Super+Shift+D | Display settings (nwg-displays) |
| Super+arrows | Focus |
| Super+Shift+arrows | Move window |
| Super+1…0 | Workspace |
| Super+Shift+1…0 | Move window to workspace |
| Super+H / Super+V | Horizontal / vertical split |
| Super+F | Fullscreen |
| Super+Shift+Space | Toggle floating |
| Super+R | Resize mode; arrows resize, Escape finishes |
| Super+L | Lock |
| Super+I | Input method configuration |
| Super+Ctrl+G | Toggle Right Alt between Alt and the Hangul key |
| Super+N / Super+Shift+N | Notification history / pause notifications |
| Super+Shift+S | Select a screenshot region, save and copy to clipboard |
| Print / Shift+Print | Region / full screenshot, saved and copied |
| Super+Shift+C | Reload Sway configuration |
| Super+Shift+E | Exit prompt |

Automatic idle locking and display power-off are disabled. The session still
locks before sleep. Screenshots go to `~/Pictures/Screenshots`.
Super+Shift+S opens region selection when the shortcut is released. Drag to
capture and then paste with Ctrl+V; Escape cancels selection.

Locking uses gtklock: all backgrounds are pure black, and the clock/password
form is visible only on the MSI monitor (`DP-5`). The LG OLED (`DP-6`) stays
black while typing and while authentication messages are shown. Styling is
in `config/gtklock/style.css`; the preferred input monitor is set in
`config/gtklock/config.ini`. Super+L and locking before sleep
all use `config/sway/scripts/lock`.

Edit `config/sway/config.d/10-appearance.conf` for borders, gaps, colors and
monitor layout; `20-input.conf` for keyboards; `30-bindings.conf` for shortcuts.
Use `swaymsg -t get_outputs` and `swaymsg -t get_inputs` in the session to find
device names. The wallpaper symlink points to `Wallpapers/shimarin.jpg`.

For graphical display configuration, open **Displays Settings** from Rofi or
press Super+Shift+D. Drag monitors to arrange them, select the resolution,
refresh rate and scale, then apply and confirm the settings. Saved monitor
settings and optional workspace assignments are loaded from `config/sway/outputs`
and `config/sway/workspaces` on subsequent Sway starts.

The G502 X LIGHTSPEED uses the `flat` pointer profile (no acceleration), with
neutral speed adjustment, in `config/sway/config.d/20-input.conf`. Solaar is
available from Rofi for Logitech device settings such as DPI, polling rate,
onboard profile selection and battery status. Its launcher uses window-only
mode to avoid needing an additional tray integration library.
Star Citizen wheel adjustments and their persistence limits are covered in the
[Star Citizen guide](docs/star-citizen.md#휠-과민-반응과-방향-이상).

Waybar uses `config/waybar/style.css`, Rofi uses `config/rofi/config.rasi`,
Kitty uses `config/kitty/kitty.conf`, and Dunst uses `config/dunst/dunstrc`.
The bar shows CPU and NVIDIA GPU usage, plus used/total VRAM and RAM in GiB,
updated every five seconds. NVIDIA metrics are read with `nvidia-smi`.
Left-click the Waybar volume indicator to open pavucontrol for per-app volume,
output devices and microphone settings. Right-click toggles mute; scrolling
adjusts volume. You can also launch pavucontrol from Rofi.
No login manager is configured. `start-sway` uses the Vulkan renderer.
Both the LG ULTRAGEAR+ and MSI MAG401QR are configured for SDR by preference.
These rules live in `config/sway/config.d/15-displays.conf`, after nwg-displays'
generated settings, and match monitor identities so they survive reconnects.
Renderer changes require leaving Sway and starting `~/.local/bin/start-sway`
again; a configuration reload cannot change the renderer. `start-sway` clears
ambient and inheritable capabilities before launching the compositor so bwrap
image loaders can run in sessions started through PAM/systemd. The saved startup
and configuration paths have been checked. A new Sway session initially confirmed
LG HDR on / MSI HDR off; HDR was subsequently disabled on both outputs and the
saved off settings were reapplied live. An actual OS reboot on 2026-10-30 confirmed
that both outputs remained in SDR. Monitor reconnection has not been tested.

For troubleshooting, run `~/.local/bin/start-sway -d 2>~/sway.log`.
Use Ctrl+Alt+F2 to reach another TTY if necessary.

The startup script currently defaults to full repainting
(`WLR_SCENE_DEBUG_DAMAGE=rerender`) to investigate intermittent artifacts in
transparent windows. This takes effect on the next Sway start and can increase
GPU use. To compare with normal partial repainting, start from a local TTY with
`WLR_SCENE_DEBUG_DAMAGE=none ~/.local/bin/start-sway`. Reloading the configuration
does not change this setting for an existing session.

## Gaming

Steam and its 32-bit NVIDIA graphics libraries are installed from Arch's
official repositories. Launch Steam from Rofi, sign in, and select the
appropriate Proton compatibility tool for Windows games.

Game key repeat is handled by `scripts/game-input-guard`: while a recognized
game has focus it disables keyboard repeat, preserving held game keys; ordinary
windows use the normal repeat rate (25). Steam games, Gamescope, and entries in
`game-input.json` are recognized. Only `input type:keyboard repeat_rate` is sent,
once per focus policy change. Shared keyboard/mouse device identifiers are not
targeted, so the pointer side of composite devices is not reconfigured.

IME state and Right Alt mappings never change on focus. Super+Ctrl+G manually
toggles Right Alt between an Alt modifier and the Hangul key using the one-shot
`scripts/toggle-ralt` command. Press Right Alt in Hangul-key mode to switch
English/Korean manually. The shortcut runs on key release without repeat, and
its session state resets when Sway loads the saved default Hangul mapping.

The previous helper changed keyboard maps, IME state and individual device
settings on focus transitions; those operations have been removed. Desktop
repeat is restored when the repeat helper stops, and `exec_always` starts it in
new sessions and reapplies its policy after config reload. Saved configuration
has been checked. The user confirmed held F in-game, ordinary desktop repeat,
and normal pointer/workspace behavior on 1↔5 transitions. Helper stop/restart
was tested; reboot and relogin have not been tested.

Star Citizen installation, launch and update instructions, Vulkan/DLSS setup,
audio, graphics-setting backups, and troubleshooting are collected in the
[Star Citizen guide (한국어)](docs/star-citizen.md). It records the final settings,
abandoned workarounds, local-only files, and the limits of restart verification.
