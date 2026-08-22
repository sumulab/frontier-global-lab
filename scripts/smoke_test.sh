#!/usr/bin/env bash
set -euo pipefail

smoke_root=$(mktemp -d)
trap 'rm -rf "$smoke_root"' EXIT

cp -R 10_Harness "$smoke_root/10_Harness"
cp -R docs "$smoke_root/docs"
cp README.md "$smoke_root/README.md"

uv run python -m compileall -q harness
uv run python -m harness --project-root "$smoke_root" index
uv run python -m harness --project-root "$smoke_root" \
  search "workspace boundary" --limit 3 \
  >"$smoke_root/search.txt"
grep -q "Engine and Workspace Boundary" "$smoke_root/search.txt"
uv run python -m harness --project-root "$smoke_root" \
  start local-smoke >"$smoke_root/start.txt"
uv run python -m harness --project-root "$smoke_root" status
printf '\nSmoke test passed.\n'
