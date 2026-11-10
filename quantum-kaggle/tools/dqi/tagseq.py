"""Print sequence of tags (depth<=2 children) within a top-level stage with cumulative static Toffoli count."""
import sys, numpy as np
sys.path.insert(0, '.')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); stage = sys.argv[2]; op = d['op']; tags = d['tags']
pos = np.flatnonzero(op == 6)
tof = ((op & 0x30) == 0x30) & ((op & 0x40) == 0); ct = np.cumsum(tof)
stack = []; start = None; last = 0
for t, p in zip(tags, pos):
    kind, name = t.split(':', 1)
    if kind == '@enter':
        stack.append(name)
        if stack == [stage]: start = p; last = p
        elif stack[0] == stage and len(stack) == 2:
            print(f"  +{int(ct[p]-ct[last]):6d} untagged before | enter {name:22s} at op {p-start:9d} cumT {int(ct[p]-ct[start]):7d}")
    else:
        if stack[0] == stage and len(stack) == 2:
            print(f"  {int(ct[p]-ct[last]):7d} in {name}"); last = p
        if stack == [stage]: print(f"  +{int(ct[p]-ct[last]):6d} untagged tail; stage total {int(ct[p]-ct[start])}")
        stack.pop()
