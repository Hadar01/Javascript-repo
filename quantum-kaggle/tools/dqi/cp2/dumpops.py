"""Print ops [a, b) of a kmb in text form (op name, qubits, bits). usage: dumpops.py kmb a b"""
import sys, numpy as np
sys.path.insert(0, '..')
from kmb import read_kmb, opname
d = read_kmb(sys.argv[1]); a, b = int(sys.argv[2]), int(sys.argv[3]); op = d['op']
nqt = (op >> 4) & 3; bt = op & 0x7f; hb = (op & 0x40) != 0
hasc = ((op & 0x80) != 0) & (op != 0x81); push = op == 0x81
i3 = np.cumsum(nqt == 3) - 1; i2 = np.cumsum(nqt == 2) - 1
i1 = np.cumsum(nqt == 1) - 1; ib = np.cumsum(hb & ((nqt == 1) | (nqt == 0)) & (bt != 6) & (bt != 7)) - 1; ic = np.cumsum(hasc | push) - 1
for k in range(a, b):
    t = op[k]; s = f"{k} {opname(t)}"
    if nqt[k] == 3: s += f" q{d['qqq0'][i3[k]]&0x7fffffff} q{d['qqq1'][i3[k]]&0x7fffffff} q{d['qqq2'][i3[k]]&0x7fffffff}"
    elif nqt[k] == 2: s += f" q{d['qq0'][i2[k]]&0x7fffffff} q{d['qq1'][i2[k]]&0x7fffffff}"
    elif nqt[k] == 1: s += f" q{d['q0'][i1[k]]&0x7fffffff}"
    if hb[k] and nqt[k] in (0, 1) and bt[k] not in (6, 7): s += f" b{d['b0'][ib[k]]}"
    if hasc[k] or push[k]: s += f" if b{d['bc'][ic[k]]}"
    print(s)
