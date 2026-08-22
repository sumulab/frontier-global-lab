#!/usr/bin/env bash
set -euo pipefail

uv run python scripts/check_public_boundary.py
uv run python -m compileall -q harness
uv run pytest -q
uv run lab claim status
uv run lab claim relationships
uv run lab claim rebuild-index
uv run lab claim index-status
./scripts/smoke_test.sh
git diff --check

printf '\nFrontier automated release checks passed.\n'
