#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/common.sh"
cd "$ROOT"
PKG="$ROOT/build/deb/drakelight_${VERSION}_all"
rm -rf "$ROOT/build/deb"
mkdir -p "$PKG/DEBIAN"
make install DESTDIR="$PKG" PREFIX=/usr
find "$PKG" -type d -exec chmod 755 {} +
find "$PKG" -type f ! -perm -u+x -exec chmod 644 {} +
SIZE="$(du -sk --exclude=DEBIAN "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<CONTROL
Package: drakelight
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Installed-Size: ${SIZE}
Maintainer: ${MAINTAINER}
Homepage: ${HOMEPAGE}
Depends: python3 (>= 3.9), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0 (>= 4.10), gir1.2-adw-1 (>= 1.5)
Recommends: pkexec | policykit-1
Description: ${DESCRIPTION}
 Choose onboard lighting effects, colours, brightness and speed for a wired
 Redragon K631 keyboard (USB 258a:0049) and save them to the keyboard.
 Unofficial; not affiliated with Redragon.
CONTROL
install -m755 "$ROOT/packaging/postinst.sh" "$PKG/DEBIAN/postinst"
install -m755 "$ROOT/packaging/postrm.sh" "$PKG/DEBIAN/postrm"
fakeroot dpkg-deb --build --root-owner-group "$PKG" "$ROOT/dist/drakelight_${VERSION}_all.deb"
echo "built dist/drakelight_${VERSION}_all.deb"
