#!/bin/sh
# Preserve the application's own arguments; add only the verified Qt theme key.
app=${0##*/}
case "$app" in rofi|vlc|fcitx5-configtool) ;; *) exit 2 ;; esac
if [ -r "$HOME/.local/share/yuru-theme/qt-env.sh" ]; then
    . "$HOME/.local/share/yuru-theme/qt-env.sh"
fi
exec "/usr/bin/$app" "$@"
