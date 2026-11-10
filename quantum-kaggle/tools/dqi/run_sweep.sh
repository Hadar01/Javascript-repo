#!/bin/bash
cd /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/work_B
V95=$(seq -f 'Bsweep-%02g' 1 19 | paste -sd,)
ALL=$(seq -f 'Bsweep-%02g' 0 19 | paste -sd,)
/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python sweep.py --comp /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data --circuit /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/cand/pub/dqi.kmb --tag v95 --salts $V95 --workers 2 --out sweep.jsonl
/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/venv/bin/python sweep.py --comp /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data --circuit /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/cand/pub3/dqi.kmb --tag v100 --salts $ALL --workers 2 --out sweep.jsonl
