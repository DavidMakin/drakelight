#!/bin/sh
set -e
case "$1" in remove|purge|0) rm -f /etc/udev/rules.d/70-drakelight.rules ;; esac
command -v udevadm >/dev/null 2>&1 && udevadm control --reload || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
exit 0
