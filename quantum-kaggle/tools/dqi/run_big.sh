#!/bin/bash
# Paired large-shot failure census: same own-sampled shots for v95 and v100. Chunk = 16384 shots.
cd /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/work_B
for i in $(seq 1000 1063); do
  /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python mysample.py /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data 16384 $i inputs/big > /dev/null
  cp inputs/big_err.npz bigfail/err_$i.npz
  for tag in v95:pub v100:pub3; do
    t=${tag%%:*}; d=${tag##*:}
    PROF_SEED=$i ./csrc/prof /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/cand/$d/dqi.kmb inputs/big 16384 - bigfail/${t}_$i 1000000000 > bigfail/${t}_$i.log
  done
  echo chunk $i done $(date +%T)
done
