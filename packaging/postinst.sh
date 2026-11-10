#!/bin/sh
set -e
if [ "$1" = configure ] || [ "$1" = 1 ] || [ "$1" = 2 ] || [ -z "$1" ]; then
    command -v udevadm >/dev/null 2>&1 && {
        udevadm control --reload || true
        udevadm trigger --subsystem-match=hidraw --action=change || true
    }
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
fi
exit 0
