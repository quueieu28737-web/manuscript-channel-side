#!/usr/bin/env bash
# Smoke test on a SYNTHETIC live dir (see make_synthetic.py). Not scientific output.
set -euo pipefail
LIVE=${1:?synthetic live dir}; OUT=${2:?new output dir}
HERE=$(cd "$(dirname "$0")/.." && pwd)
rm -rf "$OUT"; mkdir -p "$OUT"
cd "$HERE"
python3 freeze.py --live-dir "$LIVE" --out "$OUT" --no-copy
python3 p0_terminal_coverage.py --live-dir "$LIVE" --out "$OUT" > "$OUT/p0t.log"
python3 p0b_shadow_roles.py --live-dir "$LIVE" --out "$OUT" > "$OUT/p0b.log"
python3 p0a_feature_ablation.py --live-dir "$LIVE" --out "$OUT" --models qwen3:8b > "$OUT/p0a.log"
python3 p0c_record_only_strong.py --live-dir "$LIVE" --out "$OUT" --models qwen3:8b > "$OUT/p0c.log"
for f in p0t-summary.json p0b-summary.json p0a-summary.json p0c-summary.json; do test -s "$OUT/$f"; done
echo "SMOKE OK ($OUT)"
