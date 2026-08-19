#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
lab index
lab status
cat <<'MSG'

v0.2 bootstrap complete.
Next:
  export OPENAI_API_KEY='...'
  lab run energy-research-001

Without an API key you can still:
  lab search 'microgrid energy'
  lab start energy-research-001
MSG
