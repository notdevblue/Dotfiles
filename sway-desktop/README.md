# Sway desktop

Arch/Sway desktop with a minimal GMK Yuru / Shima Rin visual profile. Original
rice directories are preserved. Active files remain symlinked from `~/.config`
into this directory. The palette, generators, wallpaper and rollback tool are
maintained in [../yuru](../yuru/README.md); these theme files are generated outputs.
Restore the base desktop first, then use that bundle's documented install/activate steps.

`packages.txt` records the installed desktop and gaming packages. Steam needs
the `[multilib]` repository enabled in `/etc/pacman.conf`.

Boot login is greetd on tty1 with regreet. The session entry runs
`~/.local/bin/start-sway`, which still selects the local SwayFX build.
Ctrl+Alt+F2 reaches a normal TTY if the greeter does not start. From there,
the same command starts the session directly:

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
| Super+F10 | Switch all displays off / on; background tasks keep running |
| Super+I | Input method configuration |
| Super+Ctrl+G | Toggle Right Alt between Alt and the Hangul key |
| Super+N / Super+Shift+N | Notification history / pause notifications |
| Super+Shift+S | Freeze the current screen, select a region, save and copy |
| Print / Shift+Print | Focused window / full screenshot, saved and copied |
| Super+Shift+C | Reload Sway configuration |
| Super+Shift+E | Exit prompt |

Automatic idle locking and display power-off are disabled. The session still
locks before sleep. Screenshots go to `~/Pictures/Screenshots`.
Super+Shift+S freezes the screen on key press. Drag to capture and then paste
with Ctrl+V; Escape or right-click cancels selection. The saved/copied image
excludes the mouse cursor; the crosshair is visible only during selection.

Locking uses gtklock: the MSI (`DP-5`) shows the current ASCII winter lake/Rin
still with the clock/password form; the LG OLED (`DP-6`) stays pure black,
including while typing. Super+L and locking before sleep both use
`config/sway/scripts/lock`. The preferred input monitor remains in
`config/gtklock/config.ini`. Yuru owns the style, generated background and
output-name module; run the [Yuru lockscreen update](../yuru/README.md#잠금화면)
after restoring these configs to regenerate the image/module. That section also
covers the GTK user-CSS override, hotplug naming fix, validation and rollback.

The visual include at the end of the base Sway config overrides the original
`config/sway/config.d/10-appearance.conf`. Edit the private palette/templates to
regenerate the theme; use `20-input.conf` for keyboards and `30-bindings.conf` for shortcuts.
Use `swaymsg -t get_outputs` and `swaymsg -t get_inputs` in the session to find
device names. The wallpaper symlink points to `Wallpapers/shimarin.jpg`.

For graphical display configuration, open **Displays Settings** from Rofi or
press Super+Shift+D. Drag monitors to arrange them, select the resolution,
refresh rate and scale, then apply and confirm the settings. Saved monitor
settings and optional workspace assignments are loaded from `config/sway/outputs`
and `config/sway/workspaces` on subsequent Sway starts.

Startup workspaces are **LG → 1** and **MSI → 9**. The monitor identity rules in
`config/sway/config.d/15-displays.conf` precede the game workspace 5 assignment in
`25-star-citizen.conf`: Sway chooses the first available workspace assigned to
each output. Previously, LG's only assignment was 5, making it the startup default.
Keep 1/9 ahead of other assignments for these displays, including any added with
nwg-displays. The normal `~/.config/sway` symlink loads these rules on every Sway
start; no startup script or service is needed. To restore automatic selection,
remove the two workspace rules from `15-displays.conf` and restart Sway.
On 2026-11-01 the full saved SwayFX configuration passed validation, and two fresh
isolated SwayFX starts with virtual outputs standing in for LG/MSI selected 1/9;
workspace 5 still opened on the LG stand-in. The running desktop's 1/9 assignments
were also applied by IPC and its existing visible 1/9 layout was confirmed.
An actual desktop restart, OS reboot, account login and physical monitor
reconnection were not performed for this change.

The G502 X LIGHTSPEED uses the `flat` pointer profile (no acceleration), with
neutral speed adjustment, in `config/sway/config.d/20-input.conf`. Solaar is
available from Rofi for Logitech device settings such as DPI, polling rate,
onboard profile selection and battery status. Its launcher uses window-only
mode to avoid needing an additional tray integration library.
Star Citizen wheel adjustments and their persistence limits are covered in the
[Star Citizen guide](docs/star-citizen.md#휠-과민-반응과-방향-이상).

Waybar uses `config/waybar/style.css`, Rofi uses `config/rofi/config.rasi`,
Kitty uses `config/kitty/kitty.conf`, and Dunst uses `config/dunst/dunstrc`.
The bar is bottom-aligned, 26px high, with numeric workspaces, Codex/Grok remaining
quota, microphone mute status and time. Usage scripts run every 60 seconds;
collection, dependencies and restoration are covered in [Yuru AI usage](../yuru/README.md#btop과-ai-사용량).
Open pavucontrol from Rofi for volume,
output devices and microphone settings.
greetd runs ReGreet inside a small stock Sway on tty1. The MSI portrait panel
uses the same ASCII scene, 64px clock, date and raised input panel as gtklock;
the LG OLED stays off while MSI is connected. A pinned ReGreet layout patch
keeps the clock and form together while retaining upstream authentication.
Build, install, verification and rollback are in [the login guide](docs/login.md).
The installer enables greetd for the next boot and refreshes its files without
restarting the active service or ending the desktop session.
`start-sway` reads `~/.config/sway-session` when present. A saved `hdr` selects
`~/.local/lib/sway-hdr/sway`, Vulkan and the host's `~/.config/sway-hdr.conf`.
Without that profile it defaults to the local SwayFX/GLES build. Explicit
`SWAYFX=1`, `SWAYFX=0` and `SWAY_STOCK=1` preserve the recovery paths.
Original Sway fallback modes use Vulkan.
The shared LG/MSI base configuration stays in SDR for recovery; the private HDR
profile overrides the LG output only after including the shared configuration.
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

## Manual display power

Super+F10 switches **all on → all off → all on**. Press the same shortcut to
restore the screens; moving the mouse or typing other keys does not wake them.
This changes display power only: the computer keeps running, and Sway retains
the workspaces and window layout. Locking remains a separate action (Super+L).
The shortcut also works while locked and while an application inhibits shortcuts.

`config/sway/config.d/31-display-power.conf` runs
`config/sway/scripts/toggle-display-power` on key press without repeat. Handling
the press consumes it before the input method relays it. With focused Kitty and
Fcitx5, the former release binding ran twice for a single press, turning the
displays off and immediately back on. The press binding fixes that input path.
The script reads Sway's current output power rather than storing a toggle counter.
If any active display is off, it turns all displays on; otherwise it turns all
off. This also recovers a mixed state instead of swapping which display is on.
Disabled outputs remain disabled. Python 3 and swaymsg are required; no extra
daemon or autostart is needed.

The normal `~/.config/sway` symlink and the existing `config.d/*.conf` include
load the binding on every Sway start. Restore both saved files, preserve the
script's executable bit, and remove the superseded `31-oled-power.conf` if it
exists. When updating from the former release binding, first remove it with
`swaymsg 'unbindsym --locked --inhibited --release Mod4+F10'`; all three flags
are needed to match that binding. Then apply just the new shortcut:

```sh
swaymsg 'bindsym --locked --inhibited --no-repeat Mod4+F10 exec ~/.config/sway/scripts/toggle-display-power'
```

For recovery from a terminal/SSH connection, use
`swaymsg 'output * power on'` in the desktop session's environment. To remove
the shortcut, first turn all displays on, remove `31-display-power.conf`, run
`swaymsg 'unbindsym --locked --inhibited Mod4+F10'`, then remove the helper script.
To restore the former LG-only behavior instead, restore `31-oled-power.conf` from Git and
reload Sway after removing the new binding and script.

Verification (2026-11-07): the full saved SwayFX configuration passed validation
with a headless backend. Two fresh isolated SwayFX sessions each accepted virtual
Super+F10 key presses for all-off/all-on, recovered a mixed power state, and kept
an explicitly disabled output disabled. The running desktop received the binding
through IPC; its physical LG/MSI outputs reported power off and back on through
the same helper, with workspace and geometry unchanged. Both screens were left
on. The initial tests lacked an active input method and missed the double
execution. A focused Kitty/Fcitx5 fixture reproduced two binding events with the
old release binding; the saved press binding generated exactly one event, kept
both outputs off, and restored both with the next press. Holding F10 beyond the
repeat delay and releasing Super before F10 also executed once. The old release
binding was explicitly removed from the running desktop before installing the
press binding. This checks live IPC state, not a visual measurement of the panels.
Actual desktop restart, OS reboot, account login, lockscreen key presses and physical
monitor reconnection were not performed. Startup persistence was checked through
the saved include/symlink structure and the fresh isolated sessions.

## Kitty word deletion

In Kitty, Ctrl+Backspace deletes the previous word at the Bash prompt. Kitty's
legacy Ctrl+Backspace encoding is byte `0x08`, which Bash Readline binds to
single-character deletion. The base `config/kitty/kitty.conf` maps it to Ctrl+W
(`0x17`) in normal and application cursor modes:

```conf
map ctrl+backspace send_text normal,application \x17
```

Applications using the Kitty extended keyboard protocol retain their native
Ctrl+Backspace event. The mapping stays outside the generated theme include.
The normal `~/.config/kitty` symlink loads it on each Kitty start; apply it to
open windows with `pkill -USR1 -x kitty`. To undo, remove the mapping and its
comment and send the same reload signal. No service or device setup is needed.

Verification (2026-11-01): isolated Wayland/Kitty runs reproduced the original
`0x08` signal and checked the saved mapping in fresh Kitty processes. Normal and
application modes sent `0x17`; the extended protocol still sent the original
modified Backspace event. Bash removed English and completed Korean words;
plain Backspace and Alt+Backspace retained their behavior. Three open desktop
Kitty processes reloaded and recorded the mapping in their effective config.
Actual OS reboot/relogin and physical keyboard reconnection were not performed.

## Frozen region screenshots

The region mode of `config/sway/scripts/screenshot` uses a pinned
[grimfreeze](https://github.com/DreamMaoMao/grimfreeze) build. It captures the
outputs first, displays those buffers for selection, then crops the same buffers.
The previous `slurp` → `grim` sequence captured only after the drag finished,
so both the selection background and saved frame kept advancing.
Keeping capture and selection in one client also avoids two competing overlays.
Focused-window and full screenshots use the same color-aware client, so every
mode follows the same conversion and cursor-exclusion path.

The local `patches/grimfreeze-hide-cursor-before-capture.patch` hides the cursor
through a transparent input cover before acquiring the frozen buffers. Output
capture can otherwise include an already-composited software cursor even without
`-c`, for example during screen recording. Presentation callbacks ensure the
cursor is gone before pixels are copied. If Sway has not rebased pointer focus
onto a secondary output's new cover, a zero-distance virtual pointer event
updates that focus without moving the cursor. Keyboard focus and saved input
settings are unchanged. Selection then uses the normal visible crosshair.

Build/install the separate binary (does not replace `/usr/bin/grim`):

```sh
doas pacman -S --needed git gcc pkgconf meson ninja libpng libjpeg-turbo pixman wayland wayland-protocols wlr-protocols ffmpeg python
sh sway-desktop/bin/build-grim-freeze
```

The builder pins commit `b58b43fe1e6edac57b41981d5c793f6ae929f6a9`, applies the cursor
and HDR patches, runs the real C conversion/PNG checks, and installs
`~/.local/lib/grim-freeze/grim`; runtime never depends on the temporary build
directory. Restore this binary before using the screenshot binding. Existing
`~/.config/sway` symlinks load the saved binding on every Sway start. No daemon
or additional autostart is needed. To apply only this binding in a running
session, without restarting the desktop:

```sh
swaymsg 'unbindsym --release Mod4+Shift+s; bindsym --no-repeat Mod4+Shift+s exec ~/.config/sway/scripts/screenshot region'
```

HDR sources are tagged PQ/BT.2020 while showing the frozen original. Before
saving, each HDR output is converted separately through FFmpeg's existing
[zscale and Mobius tone mapper](https://ffmpeg.org/ffmpeg-filters.html#tonemap),
using its configured SDR white; SDR outputs are left unchanged. Only then are
rotated/scaled outputs joined and cropped. Normal PNGs carry an sRGB tag and are
copied unchanged to the clipboard. This avoids interpreting PQ as sRGB or mixing
HDR and SDR encodings in one unlabelled image. The screenshot script supplies
output hints from live Sway state. No private display identities are embedded.

The capture patch also needs libavfilter/libavutil with zscale support,
wayland-protocols >=1.41 and libpng >=1.6.45. When available, XR30 source precision
is retained through float conversion; the final shared PNG is RGB8. Mobius
compresses highlights above the reference range, so the SDR preview is not an
absolute-luminance copy of an HDR panel.

For an explicitly tagged original from one output, use
`~/.config/sway/scripts/screenshot raw-output OUTPUT`. It saves RGB8 PQ/BT.2020 with a cICP tag and does
not replace the clipboard. This is not a high-precision HDR archive; older image
viewers can ignore cICP. `/usr/bin/grim` remains available for raw diagnostics.

For rollback, restore the previous screenshot script and matching cursor-only
grim-freeze binary together, or restore the original slurp/system-grim script
and binding from Git. Reload Sway only if the binding changes. Restoring an old
script alone does not remove the installed client's new dependencies.

Verification (2026-11-01): private two-output SwayFX/GLES and stock Sway/pixman
sessions checked that changing the live background while selecting cannot alter
the displayed or saved frame. Both normal and 270° rotated outputs matched the
original image pixel-for-pixel. A GTK fixture with a visible 24×24 magenta cursor
provides a positive control on both outputs: `grim -c` must contain all cursor
pixels, while frozen PNGs must contain only the fixture background. The initial
pointer-device-only check did not display a cursor sprite and was insufficient.
Clipboard PNG bytes matched the saved file. Repeated invocations,
Escape cancellation, interruption cleanup, full capture and the real
Super+Shift+S press/release/drag binding were checked. The cursor check also
verifies that no temporary input device remains. Run the native check with
Pillow, Python GTK3/gtk-layer-shell, wtype and the Wayland build tools installed:

```sh
uv run --with pillow python sway-desktop/tests/verify-screenshot.py
# To check a separate SwayFX build:
SWAY_TEST_BINARY="$HOME/.local/lib/swayfx-detached/sway" SWAY_TEST_RENDERER=gles2 \
  uv run --with pillow python sway-desktop/tests/verify-screenshot.py
```

The saved paths and next-session load structure were checked. Actual OS
reboot/relogin and monitor disconnect/reconnect were not performed for this change.

## HDR with adjustable SDR brightness

`build-sway-detached --hdr` rebuilds pinned Sway 1.12 with the existing detached
fullscreen patch, `patches/sway-1.12-sdr-white.patch` and a statically linked,
patched wlroots 0.20.2. It installs `~/.local/lib/sway-hdr/sway`; system wlroots
and SwayFX remain independent. The new output command `sdr_white_level` accepts
1–1000 cd/m² or `default` (203). It adjusts SDR content on PQ outputs while
preserving native PQ/extended-linear luminance and leaving SDR outputs unchanged.
Custom SDR brightness uses composited cursors so cursor brightness matches SDR.

The HDR build also supports the Wayland `create_windows_scrgb` description.
Wine and the Vulkan WSI can attach it to float16 game buffers, preserving the
Windows convention of **1.0 = 80 cd/m²**. Untagged float buffers would otherwise
use SDR gamma 2.2, crushing shadows and clipping highlights. The scoped patches
`wlroots-0.20.2-windows-scrgb.patch` and `sway-1.12-windows-scrgb.patch` keep
ordinary extended-linear semantics unchanged. Windows scRGB stays composited
because output descriptions cannot express its absolute luminance convention.

The scRGB implementation was compared with Aqueous's existing wlroots 0.20.2
patches: [Windows-HDR factory and normalization (0006)](https://github.com/Seafoam-Labs/Aqueous/blob/de683d2245e2c8d2f846add9d11fc342b2ddb534/compositor/patches/wlroots/0006-color-management-v1-windows-hdr.patch)
and [scene-buffer scRGB state (0043)](https://github.com/Seafoam-Labs/Aqueous/blob/e52a8cddc93be2a5259de0240660fbc5d7ed85e4/compositor/patches/wlroots/0043-scene-buffer-windows-scrgb.patch).
They use the same factory, buffer flag and 80-nit convention. The local functional
code was independently written; comments adapted from those patches retain
attribution to Zoey Bauer and Christopher Snowhill (kode54) in the patch header,
under GPL-3.0-only (the full text is in [LICENSE](../LICENSE)). This is one scoped
implementation: it keeps the bool/setter already needed by scene buffers, without
an unused snapshot getter or Aqueous's protocol-v3, BT.2100 and output-metadata
extensions. The local SDR-white compensation and explicit scRGB scanout rejection
are retained. This support remains absent from upstream master as checked on
2026-11-07; related upstream proposals
[!5143](https://gitlab.freedesktop.org/wlroots/wlroots/-/merge_requests/5143) and
[!5369](https://gitlab.freedesktop.org/wlroots/wlroots/-/merge_requests/5369) were
closed without merging.

The `hdr3` output patches retain CTA EDID luminance limits and separate the PQ
encoding range from the displayable target. Wayland output descriptions and
surface feedback report the configured SDR reference white and EDID target
volume, and emit change notifications when they change. Display limits are not
reported as measured content MaxCLL/FALL. This scoped implementation adapts
[Aqueous's EDID and primary/target separation](https://github.com/Seafoam-Labs/Aqueous/tree/e52a8cddc93be2a5259de0240660fbc5d7ed85e4/compositor/patches/wlroots);
patch headers retain attribution. The DRM minimum-luminance unit correction is
the existing upstream [f6a01b40](https://gitlab.freedesktop.org/wlroots/wlroots/-/commit/f6a01b40d685ffadbcc5bda02741ca68ea76e863).

The `hdr4` NVIDIA DRM patch adapts the previous-primary-buffer lifetime strategy
in [Smithay #2151](https://github.com/Smithay/smithay/pull/2151) and
[Jay #1317](https://github.com/mahkoh/jay/pull/1317). NVIDIA can report a flip while
still reading the preceding framebuffer. That buffer and its release timeline
are retained until the following synchronous flip. Existing composition and
software-cursor locks also prevent two-buffer direct-scanout clients from
stalling; optional hardware layers use composition and tearing is rejected
(Sway retries without tearing). Other DRM drivers keep their original behavior.

This workaround preserves HDR, pixel format and refresh timing. It adds about
one full-size framebuffer per output and disables NVIDIA direct scanout/hardware
cursor optimizations, without queuing a frame or blocking GPU rendering.
`WLR_DRM_NVIDIA_DELAYED_RELEASE=0` is the explicit session-start A/B opt-out.
Patch headers retain pinned strategy references and distinguish the local C
adaptation from an upstream backport. The builder tests the actual retirement
functions with real wlroots buffers/swapchains and ASan/UBSan against its static
archive, including immediate-reuse and protected-rotation cases.

The composed output encoding is also part of the renderer cache key, preventing
a direct-scanout frame from leaving an SDR transform cached for later PQ
composition. IPC `hdr` continues to describe the applied state, while
`hdr_configured` reports effective HDR intent independently of DPMS power.
A powered-off display no longer needs a launcher's saved-file heuristic.

The builder runs real offscreen Vulkan pixel checks (including float16 scRGB
shadows, negative channels, values above 1 and metadata changes), real protocol
v1/v2 clients, two fresh headless startup/reload/configuration checks and the
existing detached fullscreen regression suite. The tests also commit both
SDR/PQ scanout transitions, exercise a buffered protocol surface and check
reference-only/target changes, old-description immutability and the real DRM
metadata serializer. `SWAY_BUILD_OUTPUT` can select an artifact directory for
verification without replacing the live compositor.
Set `WLR_RENDER_DRM_DEVICE` or `SWAY_TEST_RENDER_NODE` to choose the test GPU.
The installed executable does not depend on a build-cache or patched shared
wlroots. The source pins and build patches are carried alongside the builder.

The HDR4 fresh static build, existing HDR/fullscreen checks and 4,000-flip
ASan/UBSan retirement regression passed. Actual NVIDIA session restart,
three-buffer rotation, unchanged 10-bit/HDR/240Hz output, DPMS and SDR capture/
recording were checked. Physical-panel noise disappearance is not established
by a framebuffer capture; host-specific evidence and limits are recorded privately.

Host-specific output policy belongs in `~/.config/sway-hdr.conf`, which should
include the shared `config.detached` and then set HDR and SDR brightness on the
intended output. Save `hdr` in `~/.config/sway-session` to select it automatically
through the ordinary login launcher. Switching compositors requires logging out
and in. Save `swayfx` instead to restore the previous SDR session.

The `bin/sdr-brightness` launcher reuses Zenity's live slider. Link it into
`~/.local/bin`; the host app-menu entry and Super+Shift+B binding open it. It
selects the focused HDR output and applies each change through IPC, atomically
saving only that output’s SDR-white entry in `~/.config/sway-hdr.conf`. Simple
explicit `output "IDENTIFIER" { hdr on; sdr_white_level NITS; }` blocks are required
(with one command per line). Close keeps the value; Cancel restores the value
from when the dialog opened. `sdr-brightness --set NITS` uses the same saved path;
`--output NAME_OR_IDENTIFIER` selects another output explicitly. Configured HDR
outputs can also be adjusted while powered off. The dialog names its display.
`python3 sway-desktop/tests/verify-sdr-brightness.py` tests independent output
selection, persistence and failure rollback without starting a compositor.
Private output identities/preferences and host restoration evidence are maintained
in the private-configs HDR guide, rather than duplicated as a public host profile.

Validation (2026-11-07): NVIDIA offscreen pixel checks verified SDR brightness,
HDR invariance, alpha blending, SDR output/cursors and PQ scanout eligibility;
Vulkan headless startup/reload tests and all six detached fullscreen groups passed.
A real desktop logout/login loaded the HDR profile and confirmed the configured
HDR/SDR output policy. The slider was opened and user confirmed. Host-specific
brightness preferences and output identities remain in private-configs.
The HDR3 update additionally passed a fresh full static build, committed
scanout/protocol/metadata regressions and an actual desktop relogin. Physical
PQ/SDR video output changes, DPMS restoration and live reference-white feedback
were checked. Panel luminance, OS reboot and cable reconnection were not measured
or tested. Host-specific game and recorder checks are documented privately.

Compositor-side HDR-to-SDR highlight compression and HLG are still absent.
Clients such as mpv gpu-next handle output changes and tone mapping themselves;
a game that keeps sending HDR on an SDR monitor must use its SDR mode. No
unsupported capability flags are advertised to bypass gamescope checks.

## Vulkan HDR and background blur

The local `hdr6` build adds real backdrop blur to the existing Vulkan renderer;
HDR output, SDR-white compensation, scRGB and the NVIDIA buffer-retirement fix
remain in the same static build. No SwayFX renderer is loaded. In an HDR config,
add a narrow rule after the shared configuration:

```sway
for_window [app_id="^kitty$"] background_blur enable
```

Kitty must have a translucent background (the last included theme controls its
`background_opacity`). The command affects the main application surface; text,
popups and subsurfaces are rendered afterward without their own blur. Existing
windows can be toggled with `swaymsg '[app_id="^kitty$"] background_blur disable'`
or `enable`. Remove the saved rule and disable the existing windows to turn it
fully off. This custom command belongs only in the HDR profile, so stock Sway and
SwayFX do not parse it.

`wlroots-0.20.2-background-blur.patch` exposes a narrow scene-buffer flag and an
optional render-pass operation. Vulkan filters the already rendered scene prefix
with a normalized separable Gaussian compute shader (`sigma=6.3`, radius 24
output pixels) at full resolution in the same command buffer, then copies only
the window's clipped region back before drawing its content. Values
above 1 are retained; there is no SDR clamp, contrast or saturation transform.
The design references [Aqueous's Vulkan render seam](https://github.com/Seafoam-Labs/Aqueous/blob/e32ab7fc8f6510b393780b811ef92fe1bac6438e/docs/architecture-decisions/0001-vulkan-render-seam.md),
without copying its Zig pipelines or shaders. Non-Vulkan renderers ignore this
optional operation. The scene flag/setter and Sway glue are enabled only in the
HDR build; the system libraries are untouched.

For correctness, a visible blurred surface currently reconstructs the whole
output scene prefix and uses two full-size FP16 scratch images owned by each
render target. Compute dispatch covers only the effect bounds and required halo.
This costs GPU work and memory; blur strength and an optimized regional damage cache
are not exposed. When an opaque fullscreen window covers all blurred surfaces,
the ordinary no-blur path applies. Normal window capture remains sharp; output
capture contains the composed effect. No background service or login script is
added. The saved HDR profile uses the existing `start-sway` selection each login.
Installing a new executable requires logout/login to replace the running compositor.

The builder runs `verify-blur-pixels.py` on its exact static wlroots archive and
`verify-background-blur.py` against the new Sway before installing.
`verify-blur-quality.py --target-only` also checks real Kitty backdrop edge width,
periodic texture suppression and foreground clarity against the measured SwayFX
reference. Its full comparison mode accepts both compositor binaries. Runtime
integration requires GTK3/PyGObject, Pillow, Kitty, grim and swaybg. Optional
`vulkan-validation-layers` supports GPU synchronization auditing. Host-specific
settings, rollback backups and actual restart evidence are recorded privately.

The initial HDR5 bilinear downsample/upsample passed coarse variance tests but
left periodic glyph/checker aliasing and only 4.48px of edge spread, compared
with 16.20px from the original SwayFX two-pass/radius-three filter. User visual
review rejected it. HDR6 replaces that path completely with a full-resolution
weighted filter: measured spread 17.08px, checker residual zero and fine ASCII
edge energy reduced from 2.907 to 0.405 (SwayFX reference 0.231). Normalized
profiles account for the different GLES and linear HDR blending spaces; the
colors are not expected to match byte for byte. CPU Gaussian comparisons also
cover checker, signed-HDR edge, impulse and periodic line patterns.

Validation (2026-11-07): a fresh pinned static HDR6 build passed the six
existing fullscreen groups, HDR protocol/metadata/scRGB pixel checks, the
4,000-flip NVIDIA retirement regression, and blur FP16/clipping/foreground/
64-frame reuse/odd-size target tests. Two fresh private Vulkan sessions verified
actual Kitty rules/toggles, ordinary and rotated 1.25x outputs, partial damage,
reload/fullscreen and toggles during a stalled transaction snapshot. Opaque
foreground bytes stayed identical while high-frequency backdrop texture was removed. The weighted shader matches independent CPU Gaussian results to
FP16 tolerance. Khronos synchronization validation reported no errors. The
saved default configuration validated successfully. Actual desktop logout/login
then loaded HDR6 through the default HDR profile. The saved Kitty rule and smooth
backdrop were visually checked with HDR output retained. Live IPC reload/ASCII
preservation was checked on HDR5 with the same unchanged fallback-order patch.
Game/VRR performance, panel luminance and cable reconnect were not tested.

## SwayFX blur and detached browser fullscreen

Without a saved HDR profile, `start-sway` prefers `~/.local/lib/swayfx-detached/sway` and
`config/sway/config.swayfx`. This includes `config.detached`, which includes the
normal desktop configuration, so effects stay out of the original Sway config. The current Yuru
include makes Kitty opaque and disables its blur; the earlier 0.95/Kitty-only blur
rules remain as the original fallback beneath the override.
Animations, shadows and rounded corners are disabled.
SwayFX uses SceneFX's GLES renderer and cannot provide Vulkan/HDR output. Both
monitors remain in SDR. Kitty's `background_blur` option is not needed.

Chrome keeps detached fullscreen: **F11** hides/restores browser UI within the
same window, while **Super+F** independently toggles the window's actual
fullscreen size. **Super+Shift+F** toggles detachment for the focused window;
turning it off synchronizes the UI with the current window size. Other
applications keep the usual behavior.

Install/rebuild from this checkout (requires the installed Sway dependencies,
`meson`, `ninja`, `scdoc`, `gcc`, `pkgconf`, `python`, and `git`):

```sh
doas pacman -S --needed scenefx
ln -sfn "$HOME/dotfiles/sway-desktop/bin/build-sway-detached" "$HOME/.local/bin/build-sway-detached"
~/.local/bin/build-sway-detached --swayfx
```

The builder pins SwayFX 0.6 at `fd71a6bdc061bd633b488ae7b83e8a6981d22f86`, applies
`patches/sway-1.12-detached-fullscreen.patch` except its Sway version hunk, and
labels the binary `0.6-detached-fs`. It uses the system `scenefx-0.5` library;
no build-cache library is needed after installation. It runs the shared isolated
fullscreen integration test with GLES before replacing the binary. To rebuild
the older Vulkan fallback, run `build-sway-detached` without arguments; this pins
Sway 1.12 at `88869399f421d9180dd8b6ed0b5a1f4a3585d252` and tests with pixman.
The shared patch ports the idea from upstream PR #4255, adding validation,
state resynchronization, XDG output-move suppression while detached, and IPC
state fields. Rebuild after a wlroots or SceneFX ABI change.

The new compositor starts at the next login. Leaving the session returns to
regreet, which runs `start-sway` again. Reloading cannot replace a running
compositor. Fallbacks preserve the existing system Sway and custom Vulkan build:

```sh
# Previous custom Sway, including detached fullscreen, without blur:
SWAYFX=0 ~/.local/bin/start-sway
# System Sway with its base config:
SWAY_STOCK=1 ~/.local/bin/start-sway
```

Validation (2026-10-31): the installed SwayFX passed all six detached fullscreen
integration groups on the RTX 4090. The actual `start-sway --validate -d` path
loaded `config.swayfx`, the base config and detached rules, and initialized the
NVIDIA GLES renderer successfully. Version checks selected all three expected
binaries. Separate headless Kitty checks verified the saved blur rule and opacity
0.95. After the user restarted the real desktop session, IPC confirmed SwayFX
`0.6-detached-fs-fd71a6b` using `config.swayfx`, GLES, and the saved Kitty blur
rule. Three Kitty windows matched app ID `kitty`; both monitors were active at
3440×1440, approximately 144 Hz, with HDR off. The saved Kitty opacity remained
0.95. OS reboot/login, real Chrome fullscreen UI, VRR behavior and gaming
performance have not been verified with SwayFX; individual live-window opacity
and blur values were not directly queried.

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
