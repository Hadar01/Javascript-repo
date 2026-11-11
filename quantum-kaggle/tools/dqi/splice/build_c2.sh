#!/bin/bash
# Reproducible build of DQI candidate C2 = C1 + extract/unextract blocks of the public live file cd71c482.
# Inputs (SHA-256 checked inside build_c2.py):
#   C1    ca59beb811b604c4c18114597745d96fa4ca62dafb131db7c274a558aa5ffb83 (from build_c1.sh)
#   donor cd71c4822aa090ad859a826acd0d289e699f631d4c55f6337036cccce90fa671 = dqi.kmb.xz of Kaggle dataset
#         heliosli/qcc-circuits-live version 95 (2026-11-11T10:36:05Z), credited to team "i want to run gemma 9b"
#         (iwanttorungemma9b/vqcc-team-experiments-condensed, Apache-2.0) via sheroleg/quantum-circuits-from-zero-1-sqrt-x-explained v6.
# usage: build_c2.sh <c1.kmb> <donor dqi.kmb> <python> <workdir> <out.kmb>
set -euo pipefail
C1=$1; DON=$2; PY=$3; WD=$4; OUT=$5
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$WD"; cd "$WD"
cp "$HERE/kmb.py" "$HERE/kmbw.py" "$HERE/build_c2.py" .
"$PY" build_c2.py "$C1" "$DON" "$OUT" "$OUT.report.json"
sha256sum "$OUT"
