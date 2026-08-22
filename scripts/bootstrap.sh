#!/usr/bin/env bash
set -euo pipefail
uv sync --dev --locked
uv run lab index
uv run lab status
cat <<'MSG'

Frontier Harness v0.5 public example is ready.
Next:
  uv run lab --help
  uv run lab start local-smoke

For an external private workspace:
  uv run lab --project-root /path/to/workspace status
MSG
