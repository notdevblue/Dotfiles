# Yuru toolkit staging notes

These component notes preserve the initial staging checks. The rice source now
lives in `~/dotfiles/yuru/`; current deployment behavior is documented in README.md
and the private host application log.

These are source templates, not live settings. Replace the named palette tokens before use.
No toolkit app was launched and no live display, package database, session settings, service,
or application configuration was changed. Do not deploy during gaming.

## Files and integration

- `templates/gtk-3.0/gtk.css`: GTK 3.24 overlay, including GtkMenu/GtkMenuItem,
  GtkTreeView, and GTK 3 focus states (Thunar).
- `templates/gtk-4.0/gtk.css`: GTK 4 overlay with GtkPopoverMenu content, GtkListView,
  GtkColumnView, GtkGridView, editable text children and GTK 4 focus states (pavucontrol).
- `templates/qt5ct/colors/yuru.conf`: 21 roles for Qt 5.15.
- `templates/qt6ct/colors/yuru.conf`: 22 roles including Accent for Qt 6.6+.
- `templates/qt{5,6}ct/qss/yuru.qss`: small Fusion refinement with rectangular, opaque
  controls. Native indicator/arrow rendering is retained. The two copies are intentionally
  version-specific deployment assets; their content should stay identical.
- `templates/qt{5,6}ct/qt{5,6}ct.conf.fragment`: merge proposals, not replacement configs.
  Absolute target paths are for `/home/han`; adjust on another host or XDG config root.
  Keep unrelated existing settings. Merge stylesheet paths with any existing list rather
  than silently discard another stylesheet. Font descriptions use the supported two-field
  `family,pointSize` form, avoiding Qt 5/6 weight serialization differences.

GTK overlays are intended for existing Adwaita widget structure. Preserve
`gtk-im-module=fcitx` and other unrelated `settings.ini` keys. The CSS does not itself
choose a GTK theme, set dark preference, install fonts, or change icons.
The root integrator owns settings merge, rendering tokens, installation, and rollback.
GTK4 user CSS can also affect libadwaita applications such as zenity, but no complete
libadwaita style/API compatibility is claimed. Application-specific styles can override it.

Qt files remain dormant while qt5ct/qt6ct are absent. Fusion is built into Qt Widgets;
qtct platform plugins are still required to consume their palettes/configs. No Kvantum
is required. Activate a Qt-major-compatible platform theme only after installing and
verifying the corresponding plugin. A single global `QT_QPA_PLATFORMTHEME=qt6ct` would not configure Qt5 VLC.
The verified upstream shared key is `qt5ct`: qt6ct explicitly accepts it as an alias.
See the routing evidence below; installed-package runtime validation remains required.
Qt Quick, Wine/game UIs and applications that enforce their own style are outside this
Widgets palette overlay. Qtct source explicitly preserves application-owned palettes/styles.

## Color and state choices

Cream text and dark opaque surfaces are primary. Mint selection uses dark text;
burgundy is a focus outline/border accent. Muted text distinguishes disabled controls.
Semantic errors use the separate rose `ERROR` token, not the burgundy focus token.
Error entries retain their rose border when focused. QPalette has no dedicated error
role, so Qt semantic validation remains application-owned. The Qt link-visited role uses
rose as a readable secondary color; it does not imply validation failure.
Selections in active and inactive windows use the same mint background; disabled
selection uses burgundy and cream. BrightText is near-white, not the error role.
No fake labels, background images, gradients, animations or external asset URLs are added.

## Verified format and primary sources

The qtct palette lists are comma-separated QSettings QStringLists inside `[ColorScheme]`,
with `active_colors`, `inactive_colors`, `disabled_colors`, in numeric QPalette role order.
Include NoRole at index 17, PlaceholderText at 20; Qt6 Accent is index 21. The older Qt5
loader checks exact role counts, so the Qt6 palette must not replace the Qt5 palette.
Qt6 upstream can extend an older 21-role palette using Highlight for Accent; the explicit
22-role Qt6 template is used here. Modern Qt6 loaders accept at least NColorRoles.
`[Appearance]` keys `style`, `custom_palette`, `color_scheme_path`, `[Fonts]` keys
`general`, `fixed`, and `[Interface]` key `stylesheets` are read by the platform plugins.

Primary source links checked 2026-10-31:

- [Qt5ct palette reader and config writer](https://github.com/desktop-app/qt5ct/blob/master/src/qt5ct/appearancepage.cpp)
- [Qt5ct platform configuration reader](https://github.com/desktop-app/qt5ct/blob/master/src/qt5ct-qtplugin/qt5ctplatformtheme.cpp)
- [Qt6ct palette reader](https://github.com/trialuser02/qt6ct/blob/master/src/qt6ct-common/qt6ct.cpp)
- [Qt6ct platform configuration reader](https://github.com/trialuser02/qt6ct/blob/master/src/qt6ct-qtplugin/qt6ctplatformtheme.cpp)
- [Qt 5.15 QPalette role order](https://github.com/qt/qtbase/blob/5.15/src/gui/kernel/qpalette.h)
- [Qt 6.10 QPalette role order](https://github.com/qt/qtbase/blob/6.10/src/gui/kernel/qpalette.h)
- [Qt5 QFont two-field parser](https://github.com/qt/qtbase/blob/5.15/src/gui/text/qfont.cpp)
- [Qt6 QFont two-field parser](https://github.com/qt/qtbase/blob/6.10/src/gui/text/qfont.cpp)
- [GTK3 CSS selectors](https://docs.gtk.org/gtk3/css-overview.html)
- [GTK4 CSS selectors](https://docs.gtk.org/gtk4/css-overview.html)
- [Qt stylesheet reference](https://doc.qt.io/qt-6/stylesheet-reference.html)

## Validation scope — 2026-10-31

Offline Python static checks passed: all eight templates have only the declared palette
placeholders, rendered colors are valid six-digit RGB, all CSS/QSS braces balance,
no external URLs/assets are referenced, all three Qt5 lists have exactly 21 roles and
all three Qt6 lists have exactly 22 roles. Active Highlight and HighlightedText map to
mint and dark background. Both config proposals parse as INI and select Fusion/custom
palette. Source inspection verifies role order, setting keys and font serialization.
Follow-up GTK CSS parser checks also passed: each rendered CSS was loaded with its
installed GTK major in a separate Python process using GI CssProvider, without Gtk.init
and with DISPLAY, WAYLAND_DISPLAY and DBUS_SESSION_BUS_ADDRESS unset. Both emitted
zero parsing diagnostics, including the GTK4 link selectors. No display/GPU was used.
These checks do not constitute rendered-widget visual QA, Qtct plugin loading, app
restart, relogin or reboot persistence testing.
No GPU/display probe was performed. Later isolated CPU/headless verification should
capture real widget state
samples including selected/disabled/focus/error controls, and verify actual Qt5/Qt6
palette loading after the required plugins are available. Native-app QA and session
restart persistence verification remain pending until the user is finished gaming.

## Gtklock window override — 2026-10-31

The final rules in both GTK CSS templates target `window#DP-5, window#DP-6` and
set an opaque `#000000` background with no background image. These are the known
gtklock monitor-window names on this host. User GTK CSS takes priority over the
application stylesheet, so this explicit override prevents the general dark-purple
window rule from recoloring the intended pure-black lockscreen. Hidden overlay/widget
rules remain owned by gtklock application CSS. Different monitor names require
updating this selector. Parser checks passed; no lockscreen was launched or reloaded,
and actual locking/unlocking/monitor-layout behavior was not tested.

## Shared Qt platform-theme routing — 2026-10-31

Source inspection rejects the proposed `qt6ct;qt5ct` fallback. In both Qt5 5.15 and
Qt6 6.12, QGuiApplication appends the environment value as one theme name. The
platform-theme factory splits colons into plugin key/parameters; semicolons are not
a fallback separator for this variable. A semicolon list becomes an unavailable
literal key. This differs from `QT_QPA_PLATFORM`, which does support semicolon lists.

The upstream qt6ct `qt6ct.json` metadata advertises `qt6ct` and `qt5ct`; its
`main.cpp` create function accepts either and creates Qt6CTPlatformTheme. Qt5ct
advertises `qt5ct`. Each Qt major searches its own ABI-compatible plugin directory,
and the Qt6 alias continues to read qt6ct configuration, not qt5ct configuration.
The proposed shared value is therefore **`QT_QPA_PLATFORMTHEME=qt5ct`**, subject to
confirmation that both installed packages retain this advertised alias.

`templates/qt-common/environment.sh` contains the single export. For persistence,
the root integrator can source the installed file from the session startup script
before Sway and launchers start, and from login-shell startup as appropriate. Import
that already-exported variable into the user manager and D-Bus activation environment
with the existing session environment import mechanism. For the current session,
updating manager/D-Bus activation environments changes newly activated processes;
it does not rewrite environments of already-running Waybar/rofi or the game. Their
launcher execution path needs the exported value or a dedicated wrapper until the
next normal session start. Avoid restarting the active game/session to update it.
The environment export alone does not install plugins or apply palette files.

Primary source evidence:

- [Qt5 QGuiApplication theme selection](https://github.com/qt/qtbase/blob/5.15/src/gui/kernel/qguiapplication.cpp)
- [Qt5 platform-theme key/parameter splitting](https://github.com/qt/qtbase/blob/5.15/src/gui/kernel/qplatformthemefactory.cpp)
- [Qt6.12 QGuiApplication theme selection](https://github.com/qt/qtbase/blob/6.12/src/gui/kernel/qguiapplication.cpp)
- [Qt6.12 platform-theme key/parameter splitting](https://github.com/qt/qtbase/blob/6.12/src/gui/kernel/qplatformthemefactory.cpp)
- [Qt6ct advertised aliases](https://github.com/trialuser02/qt6ct/blob/master/src/qt6ct-qtplugin/qt6ct.json)
- [Qt6ct alias acceptance](https://github.com/trialuser02/qt6ct/blob/master/src/qt6ct-qtplugin/main.cpp)
- [Qt5ct advertised key](https://github.com/desktop-app/qt5ct/blob/master/src/qt5ct-qtplugin/qt5ct.json)

`verify-qt-routing.py` is a separate native offscreen probe for after plugin
installation. It compiles a tiny QApplication for each installed Qt Widgets major,
uses temporary homes/config/runtime paths and copied built palettes, unsets live
display/socket variables, points D-Bus to an absent temporary socket, disables core
dumps and uses timeouts. It never shows a window. It checks the common `qt5ct` key
selects the respective qt5ct/qt6ct proxy, Fusion base, font and palette colors. The
probe omits optional QSS from its fixture config to isolate platform-theme routing
from QStyleSheetStyle wrapping. Passing this probe verifies actual native plugin
loading/palette routing, not live application visuals or relogin persistence.

Runtime result (2026-10-31): after the main integrator installed qt5ct 1.9-2 and
qt6ct 0.11-9, the isolated native probe passed for Qt 5.15.19 and Qt 6.12.0 using
the shared `QT_QPA_PLATFORMTHEME=qt5ct` value. Qt5 returned `qt5ct-style`; Qt6
returned `qt6ct-style`, proving the installed Qt6 package accepts the Qt5 alias.
Both reported Fusion as the proxy base, Ubuntu Mono as the application font,
Window `#1e191f`, Text `#e1dbd1`, Highlight `#88d4cc`, HighlightedText `#1e191f`.
No Qt window was shown, `app.exec()` was not called, and no live display/session bus
or application configuration was used. Temporary configs used absolute temporary
paths. Core dumps were disabled and subprocess timeouts applied. This verifies
native plugin loading and palette selection; actual VLC/fcitx5-config-qt/pinentry
visuals and session-restart persistence were not tested by this probe.
