#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/drakelight/__init__.py")"
APP_ID="io.github.davidmakin.Drakelight"
MAINTAINER="${MAINTAINER:-David Makin <sleep-er@sleep-er.co.uk>}"
HOMEPAGE="https://github.com/DavidMakin/drakelight"
DESCRIPTION="Keyboard lighting control for the Redragon K631"
mkdir -p "$ROOT/dist"
