#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/common.sh"
cd "$ROOT"
command -v fpm >/dev/null || { echo "fpm is required (gem install fpm)"; exit 1; }
STAGE="$ROOT/build/rpm/root"
rm -rf "$ROOT/build/rpm"
mkdir -p "$STAGE"
make install DESTDIR="$STAGE" PREFIX=/usr
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f ! -perm -u+x -exec chmod 644 {} +
fpm -s dir -t rpm -n drakelight -v "$VERSION" -a noarch --license MIT \
    --maintainer "$MAINTAINER" --url "$HOMEPAGE" --description "$DESCRIPTION" \
    -d python3 -d python3-gobject -d python3-cairo -d gtk4 -d libadwaita \
    --after-install "$ROOT/packaging/postinst.sh" --after-remove "$ROOT/packaging/postrm.sh" \
    -p "$ROOT/dist/drakelight-${VERSION}-1.noarch.rpm" -C "$STAGE" .
echo "built dist/drakelight-${VERSION}-1.noarch.rpm"
