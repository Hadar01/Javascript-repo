#!/bin/bash
# usage: run_census.sh kmb tag first last  -> activity census of ${ACT:-act_ops.txt} groups on inputs/cen/c$i
cd /tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/work_B/cp1
for i in $(seq $3 $4); do
  ACT_OPS=${ACT:-act_ops.txt} ACT_OUT=cen/$2_c$i.txt ../csrc/prof2 $1 ../inputs/cen/c$i 4096 - cen/$2_c${i}_run > cen/$2_c$i.log 2>&1
  rm -f cen/$2_c${i}_run_*.tsv cen/$2_c${i}_run_*.txt
done
