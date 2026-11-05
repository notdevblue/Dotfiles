#!/bin/sh
# Runs inside the greeter Sway. regreet exits after a successful login, and
# this Sway then exits so greetd can start the user session on the same VT.
i=0
while [ "$i" -lt 50 ]; do
    /usr/bin/swaymsg -t get_outputs >/dev/null 2>&1 && break
    i=$((i + 1))
    sleep 0.05
done

outputs=$(/usr/bin/swaymsg -t get_outputs -r 2>/dev/null || true)
if printf '%s' "$outputs" | grep -q '"name": *"DP-5"'; then
    /usr/bin/swaymsg 'output "DP-6" disable' >/dev/null 2>&1 || true
    /usr/bin/swaymsg 'focus output "DP-5"' >/dev/null 2>&1 || true
else
    /usr/bin/swaymsg 'output "DP-6" enable' >/dev/null 2>&1 || true
fi

/usr/bin/regreet
status=$?
/usr/bin/swaymsg exit >/dev/null 2>&1 || true
exit "$status"
