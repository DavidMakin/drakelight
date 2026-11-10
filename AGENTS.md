# Drakelight

GTK4/libadwaita GUI and CLI for Redragon K631 keyboard lighting (wired USB `258a:0049`). Python, no runtime
dependencies beyond the distro's PyGObject.

## Safety rules (do not relax)

- The USB ID is shared by other keyboards with different memory layouts; a wrong write can brick a board.
- `drakelight/hidraw.py` only allows reads of `(0x83, 0xC6)` and `(0x88, 0xC8)` and writes of `(0x03, 0xC6)` and
  `(0x08, 0xC8)`. Do not add commands or pages.
- `drakelight/lighting.py` validates the header and markers before writing, changes at most 3 bytes per write, backs
  up first and reads back afterwards. Keep all four properties.
- Never write to a real keyboard from tests; use fakes.

## Layout

- `drakelight/`: `hidraw.py` (device access), `lighting.py` (block layout and apply/restore), `preview_fx.py`
  (animation maths for previews), `gui_gtk.py` (UI), `cli.py`, `access.py` (udev rule via pkexec).
- `data/`: desktop entry, icon, AppStream metainfo. `packaging/`: `.deb`, `.rpm`, AppImage builders.
- `docs/screenshots/`: README images.

## Commands

- Test and lint: `.venv/bin/pytest -q && .venv/bin/ruff check .` (or `make test`).
- Run the GUI from a checkout: `PYTHONPATH=. /usr/bin/python3 -m drakelight`. The GTK bindings only exist for the
  system Python, not asdf or venv interpreters.
- Packages: `make dist`, `bash packaging/build-deb.sh`, `build-rpm.sh`, `build-appimage.sh` (outputs in `dist/`).

## Conventions

- Commit subjects use conventional prefixes (`feat:`, `fix:`, `docs:`, `ci:`, `build:`, `chore:`). The release
  workflow groups notes by them.
- Releasing: bump `__version__` in `drakelight/__init__.py` and the release entry in the metainfo, commit, then
  `git tag vX.Y.Z && git push --tags`. The workflow fails if the tag and `__version__` differ.
- Keep the two UI themes (light and dark) working; check both when changing styling.
- No AI attribution in commits or PRs.
