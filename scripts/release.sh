#!/usr/bin/env bash
# Prepare a release: bump the version, run the gates, commit. Usage: scripts/release.sh X.Y.Z
set -euo pipefail
v="${1:?usage: scripts/release.sh X.Y.Z}"
[[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "version must be X.Y.Z" >&2; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "working tree not clean" >&2; exit 1; }
sed -i "s/^__version__ = .*/__version__ = \"$v\"/" drakelight/__init__.py
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy
git commit -am "chore: bump version to $v"
cat <<EOF
Next, from a branch:
  git push -u origin HEAD && gh pr create --fill
  gh pr checks --watch && gh pr merge --merge
  git fetch origin main && git tag -a v$v -m "v$v" origin/main && git push origin v$v
  gh run watch
EOF
