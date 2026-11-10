#!/bin/bash
cd /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/work_B
for w in 1 2 3 4 5 6 8 10 12 14 15 16 17 18 19 20 21 22 23 24 25 26 28 30 32 33 34 35; do
  /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python mysample.py /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data 4096 $((5000+w)) inputs/w 1 > /dev/null 2>&1
  /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python mysample.py /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data 4096 $((5000+w)) inputs/w $w > /dev/null
  for tag in v95:pub v100:pub3; do t=${tag%%:*}; d=${tag##*:}
    PROF_SEED=$w ./csrc/prof /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/cand/$d/dqi.kmb inputs/w 4096 - wfail/${t}_w$w 1000000000 > wfail/${t}_w$w.log
  done
  echo w $w $(cat wfail/v95_w$w.log | awk '{print $6, $8}') $(cat wfail/v100_w$w.log | awk '{print $6, $8}')
done
