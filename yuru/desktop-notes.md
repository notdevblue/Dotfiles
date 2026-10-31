# Desktop/app staging notes

The rice source now lives in `~/dotfiles/yuru/`. These notes describe the initial
component preparation; README.md and the host log describe current installation.
Firefox additionally has a chrome-only userChrome.css/user.js path for its next
normal startup, without installing an unsigned extension.

These source templates are dormant. Rendering and installing are separate operations; none of the templates has been applied to the running desktop. They intentionally reuse Ubuntu Mono already present on this host. No Sarasa/package installation is needed for this stage.

## Destinations and integration

| Template | Eventual user destination / merge |
| --- | --- |
| `kitty/theme.conf` | `~/.config/kitty/yuru-theme.conf`; append `include yuru-theme.conf` **last** in the existing `kitty.conf`. Preserve behavioral options. This intentionally overrides existing palette, font, opacity, and dynamic opacity only when later installed; retains the existing 1 px padding. |
| `rofi/config.rasi` | Replace `~/.config/rofi/config.rasi` after backup. Standalone; no `automata.rasi` dependency, prompt, icons, extra mode controls or renamed application entries. |
| `dunst/dunstrc` | Replace `~/.config/dunst/dunstrc` after backup. Full current configuration retained except palette/font and descriptive comment; DP-5, `follow=none`, urgency timeouts, input actions and routing stay the same. |
| `waybar/config.jsonc`, `waybar/style.css` | Replace corresponding files under `~/.config/waybar/` after backup; retain currently installed Waybar. Bottom 26 px bar, numeric workspace indices, time only at right. No custom scripts, sensors, tray or usage pollers. Existing Sway bar launch should continue using Waybar. Swaybar/i3status migration is deferred. |
| `fcitx5/themes/yuru/` | Copy rendered directory into `~/.local/share/fcitx5/themes/yuru/`, including four SVG files. |
| `fcitx5/conf/classicui.conf` | Merge its root-level keys into `~/.config/fcitx5/conf/classicui.conf`; **not** a `[General]` section. Select the same theme for light/dark modes. Preserve all other UI keys and every existing `config`, `profile`, `conf/hangul.conf`, and `conf/notifications.conf` setting. |
| `gtklock/style.css` | Replace `~/.config/gtklock/style.css` after backup; keep `config.ini` unchanged. Pure black OLED background and `window:not(#DP-5) > overlay { opacity: 0; }` are preserved exactly. |
| `code/settings.fragment.json` | Manually/key-wise merge `workbench.colorCustomizations` and `editor.tokenColorCustomizations` into the intended VS Code profile `settings.json`. Merge nested objects so unrelated customizations survive. This is a settings fragment, not an extension. Existing credentials, sync state and profile settings were not read. |
| `firefox/manifest.json` | Source for a static Firefox browser-chrome theme, **not an automatic profile install**. Render first; package the manifest into a ZIP/XPI and obtain Mozilla signing for durable normal-release installation, then install the signed add-on later. Temporary loading is for later testing and is not persistence. GTK cannot theme arbitrary web pages. Site content remains controlled by each site. |
| `bash/prompt.bash` | Copy into a chosen user config location and source last from interactive `~/.bashrc`. It assigns only PS1 (path plus user/root prompt character); it does not modify `PROMPT_COMMAND`, shell options, aliases or environment. Truecolor values correspond to this stage's cream/mint palette. |

Kitty uses an opaque background; compositor blur disablement belongs to the separate Sway override. The currently active user-edited `background_opacity 0.90` has not been changed. Reload/restart behavior must be handled in a future user-authorized apply operation after the game ends.

## Format evidence

- Installed `/usr/share/fcitx5/themes/default-dark/theme.conf` supplies the actual v1 theme section/key format. The four small SVG paging/menu glyphs here are original simple geometry. [Fcitx theme customization](https://fcitx-im.org/wiki/Theme_Customization) describes this theme system; [the upstream 5.1.23 classicui source](https://github.com/fcitx/fcitx5/blob/5.1.23/src/ui/classic/classicui.h) confirms `Font`, `MenuFont`, `Theme` and `DarkTheme` root-level option names.
- Installed `/usr/share/man/man5/waybar-sway-workspaces.5.gz` explicitly documents `{index}` as the workspace index. Format does not expose original emoji/name suffixes.
- [Mozilla static theme manifest reference](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/theme) supplies supported browser chrome colors. [Mozilla signing guidance](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/) describes later signing/distribution.
- Rofi uses its ordinary `entry`, `listview`, `element`, `element-text` widgets. Installed `rofi-theme(5)` is the local format reference. No launcher was started to parse or preview it while gaming.

## Validation (2026-10-31)

Performed: static JSON parsing; rendered JSON parsing against the fixed palette; root-level Fcitx key and theme schema checks against installed/upstream sources; SVG XML parsing after token rendering; Bash syntax check; comparison of Dunst behavior and gtklock non-color rules with the active-source files; verification that Waybar contains no executable/custom modules. No active configuration writes, GUI launches, reloads, process/service restarts, package installation, GPU tests, logout or reboot were performed. App rendering, contrast in real applications and persistence across application/session/system restarts remain unverified.
