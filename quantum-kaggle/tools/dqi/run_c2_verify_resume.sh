#!/bin/bash
# Resume of run_c2_verify.sh after a worker restart: stress sets 14-21, then official sweeps (3 workers).
cd /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/work_B
C2=/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/work_B/splice/c2.kmb; C1=/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/work_B/splice/c1.kmb
ws=(18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 35 35 35)
for i in $(seq 14 21); do
  w=${ws[$((i-1))]}
  /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python mysample.py /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data 8192 $((7000+i)) inputs/c2s $w > /dev/null
  PROF_SEED=$i ./csrc/prof $C2 inputs/c2s 8192 - wfail_c1/c2_w${w}_$i 1000000000 > wfail_c1/c2_w${w}_$i.log
  echo stress w $w set $i c2 $(awk '{print $6,$8}' wfail_c1/c2_w${w}_$i.log) c1 $(awk '{print $6,$8}' wfail_c1/c1_w${w}_$i.log)
done
A=$(seq -f 'Cx-%02g' 0 9 | paste -sd,); H=$(seq -f 'Cx-%02g' 10 14 | paste -sd,)
/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python sweep.py --comp /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data --circuit $C2 --tag c2 --salts $A --workers 3 --out sweep_cx.jsonl
/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python sweep.py --comp /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data --circuit $C1 --tag c1 --salts $A --workers 3 --out sweep_cx.jsonl
echo MAIN_DONE
/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python sweep.py --comp /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data --circuit $C2 --tag c2_holdout --salts $H --workers 3 --out sweep_cx.jsonl
/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python sweep.py --comp /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data --circuit $C1 --tag c1_holdout --salts $H --workers 3 --out sweep_cx.jsonl
echo ALL_DONE
