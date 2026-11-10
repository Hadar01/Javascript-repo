"""Dump ops [a,b) of a kmb as text with operand ids. usage: dump.py kmb a b [onlytof]"""
import sys, numpy as np
sys.path.insert(0, '.')
from kmb import read_kmb, opname
d = read_kmb(sys.argv[1]); op = d['op']; a, b = int(sys.argv[2]), int(sys.argv[3]); only = len(sys.argv) > 4
nq = (op >> 4) & 3; cond = ((op & 0x80) != 0); hb = (op & 0x40) != 0
# operand indices
i3 = np.cumsum(nq == 3) - (nq == 3); i2 = np.cumsum(nq == 2) - (nq == 2); i1 = np.cumsum(nq == 1) - (nq == 1)
ib = np.cumsum(hb) - hb; ic = np.cumsum(cond) - cond
tagpos = np.flatnonzero(op == 6); tagidx = {int(p): i for i, p in enumerate(tagpos)}
def w(q): q = int(q); return f"S{q//12}.{q%12}" if q < 840 else f"a{q}"
for k in range(a, b):
    t = op[k]; n = opname(t); s = []
    if nq[k] == 3: s = [w(d['qqq0'][i3[k]]), w(d['qqq1'][i3[k]]), w(d['qqq2'][i3[k]])]
    elif nq[k] == 2: s = [w(d['qq0'][i2[k]]), w(d['qq1'][i2[k]])]
    elif nq[k] == 1: s = [w(d['q0'][i1[k]])]
    if hb[k]: s.append(f"b{d['b0'][ib[k]]}")
    if cond[k]: s.append(f"if b{d['bc'][ic[k]]}")
    if t == 6: s.append(d['tags'][tagidx[k]])
    if only and nq[k] != 3 and t != 6 and n not in ('HMR', 'PUSH_CONDITION', 'POP_CONDITION'): continue
    print(k, n, *s)
