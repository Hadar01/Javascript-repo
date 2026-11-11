#!/bin/sh
# Run the pinned public DQI generator in isolation.
# Usage (as root):  unshare -m -n --propagation private -- run_generator_sandbox.sh <readonly_src_dir> <venv_dir> <out_dir> <home_dir>
#  - own network namespace (no route anywhere; proxy-injected Kaggle credentials unreachable)
#  - source bind-mounted read-only; cleared environment; memory and time caps
set -e
SRC=$1; VENV=$2; OUT=$3; HOMED=$4
mount --bind "$SRC" "$SRC"
mount -o remount,ro,bind "$SRC"
touch "$SRC/.probe" 2>/dev/null && { echo "RO MOUNT FAILED"; exit 9; } || echo "source is read-only"
exec env -i PATH=/usr/bin:/bin HOME="$HOMED" LANG=C.UTF-8 \
  prlimit --as=20000000000 -- timeout 4h nice -n 10 \
  "$VENV/bin/python" -I -B "$SRC/rebuild_native.py" --out "$OUT"
