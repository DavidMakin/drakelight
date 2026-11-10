#!/usr/bin/env bash
# Bundles the system Python, PyGObject, GTK 4 and libadwaita. Build on the oldest distro you want to support
# (the CI uses Ubuntu 24.04): the AppImage needs at least that glibc.
set -euo pipefail
. "$(dirname "$0")/common.sh"
cd "$ROOT"

LINUXDEPLOY_URL=https://github.com/linuxdeploy/linuxdeploy/releases/download/1-alpha-20250213-2/linuxdeploy-x86_64.AppImage
GTK_PLUGIN_URL=https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/7a3fbc31a9e5075073ff8790f26effbac5f84453/linuxdeploy-plugin-gtk.sh
APPIMAGETOOL_URL=https://github.com/AppImage/appimagetool/releases/download/1.9.0/appimagetool-x86_64.AppImage

BUILD="$ROOT/build/appimage"
APPDIR="$BUILD/AppDir"
TOOLS="$ROOT/build/tools"
mkdir -p "$TOOLS"
rm -rf "$BUILD"
mkdir -p "$APPDIR"

fetch() { [ -x "$TOOLS/$1" ] || { curl -fsSL -o "$TOOLS/$1" "$2" && chmod +x "$TOOLS/$1"; }; }
fetch linuxdeploy-x86_64.AppImage "$LINUXDEPLOY_URL"
fetch linuxdeploy-plugin-gtk.sh "$GTK_PLUGIN_URL"
fetch appimagetool-x86_64.AppImage "$APPIMAGETOOL_URL"

make install DESTDIR="$APPDIR" PREFIX=/usr
rm -f "$APPDIR/usr/bin/drakelight"
install -m755 packaging/AppRun "$BUILD/AppRun"

PYV="$(/usr/bin/python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
install -Dm755 "$(readlink -f /usr/bin/python$PYV)" "$APPDIR/usr/bin/python3"
mkdir -p "$APPDIR/usr/lib/python$PYV" "$APPDIR/usr/lib/python3/dist-packages"
(cd /usr/lib/python$PYV && tar cf - --exclude='test' --exclude='tests' --exclude='idlelib' --exclude='config-*' --exclude='tkinter' \
    --exclude='turtledemo' --exclude='ensurepip' --exclude='__pycache__' --exclude='site-packages' \
    --exclude='dist-packages' .) | (cd "$APPDIR/usr/lib/python$PYV" && tar xf -)
for mod in gi cairo; do
    cp -r "$(/usr/bin/python3 -c "import os, $mod; print(os.path.dirname($mod.__file__))")" \
        "$APPDIR/usr/lib/python3/dist-packages/"
done
GIR="$(dirname "$(find /usr/lib -type d -name girepository-1.0 | head -1)")"
cp -r "$GIR/girepository-1.0" "$APPDIR/usr/lib/"

ARGS=(--appdir "$APPDIR" --plugin gtk --custom-apprun "$BUILD/AppRun"
      --desktop-file "data/$APP_ID.desktop" --icon-file "data/$APP_ID.svg"
      --executable "$APPDIR/usr/bin/python3")
for lib in libgtk-4.so.1 libadwaita-1.so.0; do
    ARGS+=(--library "$(ldconfig -p | awk -v l="$lib" '$1 == l {print $NF; exit}')")
done
while IFS= read -r so; do ARGS+=(--library "$so"); done < <(find "$APPDIR/usr/lib" -name '*.so' -o -name '*.so.*' | sort)

export DEPLOY_GTK_VERSION=4
export PATH="$TOOLS:$PATH"
export APPIMAGE_EXTRACT_AND_RUN=1
cp "$TOOLS/linuxdeploy-plugin-gtk.sh" "$TOOLS/linuxdeploy-plugin-gtk"
"$TOOLS/linuxdeploy-x86_64.AppImage" "${ARGS[@]}"

ARCH=x86_64 "$TOOLS/appimagetool-x86_64.AppImage" --appimage-extract-and-run "$APPDIR" \
    "$ROOT/dist/Drakelight-${VERSION}-x86_64.AppImage"
echo "built dist/Drakelight-${VERSION}-x86_64.AppImage"
