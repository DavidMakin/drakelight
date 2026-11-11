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

- Test and lint: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy` (or `make test`).
- Wait for CI with `gh pr checks <n> --watch` or `gh run watch`, not sleep loops.
- Run the GUI from a checkout: `PYTHONPATH=. /usr/bin/python3 -m drakelight`. The GTK bindings only exist for the
  system Python, not asdf or venv interpreters.
- Packages: `make dist`, `bash packaging/build-deb.sh`, `build-rpm.sh`, `build-appimage.sh` (outputs in `dist/`).

## Conventions

- Commit subjects use conventional prefixes (`feat:`, `fix:`, `docs:`, `ci:`, `build:`, `chore:`). The release
  workflow groups notes by them.
- Python version lives in `pyproject.toml` (`requires-python`, ruff `target-version`, mypy `python_version`), `.python-version`,
  `packaging/build-deb.sh` (Depends), and `.github/workflows/ci.yml` and `release.yml` (`runs-on`). The packages bundle the
  runner's system Python and its `gi` bindings, so a version bump must move all of them together, and the packages job
  needs a runner that ships that Python.
- Releasing (`scripts/release.sh X.Y.Z` does the bump, gates and commit): bump `__version__` in `drakelight/__init__.py` (the only place the version lives; the CLI, About dialog,
  packages and metainfo all read it), commit, then `git tag -a vX.Y.Z -m "..." && git push --tags`. The workflow fails if the tag and `__version__` differ.
- Keep the two UI themes (light and dark) working; check both when changing styling.
- No AI attribution in commits or PRs.
