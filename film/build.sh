#!/usr/bin/env bash
# Beyond the Image 2026 - full rebuild in one command.
#
#   ./build.sh            rebuild everything (draft resampling, fast)
#   ./build.sh final      delivery quality (LANCZOS montage resampling)
#   ./build.sh validate   asset report only, no encode
#
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/scripts:${PYTHONPATH:-}"
MODE="${1:-draft}"
[ "$MODE" = "final" ] && export FILM_QUALITY=final

step() { printf '\n\033[36m== %s\033[0m\n' "$1"; }

step "brand assets"
python3 scripts/extract_brand.py

step "text layer"
python3 scripts/textgen.py

step "partner logo wall"
python3 scripts/logo_wall.py || echo "  (continuing - logos still outstanding)"

step "title cards (S15 blocker, S16)"
python3 scripts/titlecards.py

step "team montage (S12)"
python3 scripts/montage.py

step "validate + placeholders"
python3 scripts/validate.py
[ "$MODE" = "validate" ] && exit 0

step "assemble + encode"
python3 scripts/assemble.py

step "qc contact sheet"
python3 scripts/qc.py

printf '\n\033[32mdone\033[0m — deliverables in out/\n'
ls -la out/
