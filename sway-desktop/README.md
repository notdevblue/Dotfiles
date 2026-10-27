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
| Super+N / Super+Shift+N | Notification history / pause notifications |
| Print / Shift+Print | Region / full screenshot, saved and copied |
| Super+Shift+C | Reload Sway configuration |
| Super+Shift+E | Exit prompt |

Automatic idle locking and display power-off are disabled. The session still
locks before sleep. Screenshots go to `~/Pictures/Screenshots`.

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

Waybar uses `config/waybar/style.css`, Rofi uses `config/rofi/config.rasi`,
Kitty uses `config/kitty/kitty.conf`, and Dunst uses `config/dunst/dunstrc`.
The bar shows CPU and NVIDIA GPU usage, plus used/total VRAM and RAM in GiB,
updated every five seconds. NVIDIA metrics are read with `nvidia-smi`.
Left-click the Waybar volume indicator to open pavucontrol for per-app volume,
output devices and microphone settings. Right-click toggles mute; scrolling
adjusts volume. You can also launch pavucontrol from Rofi.
No login manager is configured. HDR is left disabled pending display checks.

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

Star Citizen uses the upstream LUG Helper installed under
`~/.local/share/lug-helper`. Open **Star Citizen LUG Helper** in Rofi and select
**Install Star Citizen**. It downloads a compatible Wine runner and installs
the RSI Launcher into `~/Games/star-citizen` by default. Afterward, sign in to
RSI Launcher and install the game using its default Windows path.

The helper can also be started with `~/.local/bin/lug-helper`; use
`~/.local/bin/lug-helper --no-gui --preflight-check` for its system checks.

Star Citizen window rules in `config/sway/config.d/25-star-citizen.conf` keep
the game fullscreen on workspace 5 on the landscape LG display (`DP-6`).
Use Super+5 to return to the game and Super+1…0 to change workspaces;
Super+F toggles Sway fullscreen. Alt+Tab is not mapped in this configuration.
The RSI Launcher floats so that its dialogs are not squeezed by tiling.

The launcher script runs RSI Launcher and the game inside Gamescope with one
3440×1440 virtual monitor at 240 Hz and `--force-grab-cursor`. This isolates
F interaction cursor warps from the rotated secondary monitor's coordinates.
Sway places the outer Gamescope window on workspace 5. Desktop Super shortcuts
remain available because Gamescope is not started with keyboard grabbing.
The Gamescope WSI bypass layer is disabled (`DISABLE_GAMESCOPE_WSI=1`) for
the composited output path. When checking a black screen, first verify that
gtklock and display sleep are inactive: the LG display intentionally stays
black while the session is locked.

The current game uses 3440×1440 borderless mode. Its `LIVE/user.cfg` and saved
GraphicsSettings.json select DX11 (`r.GraphicsRenderer = 0`) while investigating the Vulkan device
timeout recorded on the RTX 4090. The launcher notification overlay is off,
and the Wine prefix has `HKCU\Software\Wine\X11 Driver\UseTakeFocus=N` to
reduce cursor/focus problems when switching workspaces. Original settings
and the crash log are backed up under `~/.local/state/star-citizen-fixes/`.
