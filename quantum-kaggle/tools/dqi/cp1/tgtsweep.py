"""Per window of K static Toffolis: which syndrome registers (S0..S69, as 12-qubit words) the Toffoli targets and
controls fall in. Prints compact rows: T-start, #targets in workspace, S-word index range of targets (min-max, median),
number of distinct S words touched. usage: tgtsweep.py kmb K [Tmin Tmax]"""
import sys, numpy as np
sys.path.insert(0, sys.path[0])
from kmb import read_kmb
d = read_kmb(sys.argv[1]); K = int(sys.argv[2]); op = d['op']
nq = d['num_qubits']; word = np.full(nq, -1, np.int32)
for i in range(70):
    ids = d['regs'][f'S{i}'] & 0x7fffffff; word[ids] = i
nqt = (op >> 4) & 3; is3 = (nqt == 3)
tof_mask = is3 & ((op & 0x40) == 0) & ((op & 0x7f) != 6) & ((op & 0x7f) != 7)
# qqq index per op
i3 = np.cumsum(is3) - 1
sel = np.flatnonzero(tof_mask); ii = i3[sel]
a, b, c = d['qqq0'][ii] & 0x7fffffff, d['qqq1'][ii] & 0x7fffffff, d['qqq2'][ii] & 0x7fffffff
kind = op[sel] & 0x0f   # 0 CCZ, 1 CCX, 2 CSWAP
tw = word[c]; aw = word[a]; bw = word[b]
lo = int(sys.argv[3]) if len(sys.argv) > 3 else 0; hi = int(sys.argv[4]) if len(sys.argv) > 4 else len(sel)
for s in range(lo, min(hi, len(sel)), K):
    e = min(s + K, len(sel)); t = tw[s:e]; ws = int((t < 0).sum()); tt = t[t >= 0]
    ctl = np.concatenate([aw[s:e], bw[s:e]]); ctl = ctl[ctl >= 0]
    if len(tt): r = f"tgtS {tt.min():2d}-{tt.max():2d} med {int(np.median(tt)):2d} n{len(np.unique(tt)):2d}"
    else: r = "tgtS  -              "
    if len(ctl): r2 = f"ctlS {ctl.min():2d}-{ctl.max():2d} med {int(np.median(ctl)):2d} n{len(np.unique(ctl)):2d}"
    else: r2 = 'ctlS -'
    print(f"{s//1000:4d}k op{sel[s]:9d} wsT {ws:4d} CCZ {int((kind[s:e]==0).sum()):3d} CSW {int((kind[s:e]==2).sum()):3d} {r} | {r2}")
