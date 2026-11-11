#!/bin/bash
# Reproducible build of DQI candidate C1:
#   host = public v100 DQI binary (sha256 e9f54be3...), block = [convert..unconvert] of the generator output 7bd10fca...
#   (atakanaldemir/qcc-c44-five-helper-release-sources v1, Apache-2.0; SomeJoint, Atakan Aldemir and lineage),
#   bridged by an exact affine CNOT map fitted on simulated boundary states and validated on held-out shots.
# usage: build_c1.sh <v100.kmb> <gen7bd.kmb> <competition data dir> <python> <workdir> <out.kmb>
set -euo pipefail
V=$1; G=$2; COMP=$3; PY=$4; WD=$5; OUT=$6
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$WD"; cd "$WD"
echo "e9f54be304cbdcda7306729c335b1a2314a45d0ca818e05cf60e45ddee969bc4  $V" | sha256sum -c -
echo "7bd10fcab4f2dd653aabfa475cd67b0d7b8ca6bd1aec7149b7905c2b0390dd0f  $G" | sha256sum -c -
g++ -O3 -march=native -o prof "$HERE/prof.cc"
cp "$HERE/kmb.py" "$HERE/kmbw.py" "$HERE/gf2.py" "$HERE/splice.py" .
"$PY" "$HERE/gen_inputs.py" "$COMP" 4096 12345 fit       # official sampler, fit set
"$PY" "$HERE/gen_inputs.py" "$COMP" 4096 777001 val      # official sampler, held-out set
read v1 g1 < <("$PY" - "$V" "$G" <<'PYEOF'
import sys, numpy as np
sys.path.insert(0, '.')
from kmb import read_kmb
out = []
for p in sys.argv[1:3]:
    d = read_kmb(p); pos = np.flatnonzero(d['op'] == 6)
    out.append(str([int(q) for t, q in zip(d['tags'], pos) if t == '@enter:convert'][0]))
print(' '.join(out))
PYEOF
)
STATE_OPS=$v1 PROF_SEED=1 ./prof "$V" fit 4096 - sv 1000000000 > /dev/null
STATE_OPS=$g1 PROF_SEED=2 ./prof "$G" fit 4096 - sg 1000000000 > /dev/null
STATE_OPS=$v1 PROF_SEED=11 ./prof "$V" val 4096 - vv 1000000000 > /dev/null
STATE_OPS=$g1 PROF_SEED=12 ./prof "$G" val 4096 - gv 1000000000 > /dev/null
"$PY" splice.py "$V" "$G" sv_state_$v1.bin sg_state_$g1.bin vv_state_$v1.bin gv_state_$g1.bin "$OUT" "$OUT.report.json"
sha256sum "$OUT"
