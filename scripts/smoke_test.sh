#!/usr/bin/env bash
set -euo pipefail
python3 -m compileall -q harness
python3 -m harness index
python3 -m harness search "microgrid energy" --limit 3 >/tmp/lab_search.txt
grep -q "Energy Research 001" /tmp/lab_search.txt
python3 -m harness start daily-loop >/tmp/lab_start.txt
python3 -m harness status
printf '\nSmoke test passed.\n'
