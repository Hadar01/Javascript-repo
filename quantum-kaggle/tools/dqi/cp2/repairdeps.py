"""Which measurements does each measurement-dependent Toffoli (classically conditioned CCX/CCZ) repay?
Exact dependency sets: every HMR gets an id; classical bits carry the XOR-set (python int bitset) of HMR outcomes
they are a parity of (BIT_INVERT_IF b if c: S[b] ^= S[c]; STORE: cleared; BIT_STORE1_IF: treated as union).
For each conditioned Toffoli in a reverse stage: union of the sets of its condition bits (PUSH stack + _IF).
Output: per cluster of such Toffolis, the HMR ids it depends on (pickled) for later joining with measured values."""
import sys, json, pickle, numpy as np, collections
sys.path.insert(0, '..')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); cuts = json.load(open(sys.argv[2]))[sys.argv[3]]; out = sys.argv[4]
op = d['op']; n = len(op); nqt = (op >> 4) & 3; bt = op & 0x7f; hb = (op & 0x40) != 0
hasc = ((op & 0x80) != 0) & (op != 0x81); push = op == 0x81; pop = op == 0x01
useb0 = hb & ((nqt == 1) | (nqt == 0)) & (bt != 6) & (bt != 7)
b0 = np.zeros(n, np.int64); b0[useb0] = d['b0'][np.cumsum(useb0)[useb0] - 1]
bc = np.full(n, -1, np.int64); u = hasc | push; bc[u] = d['bc'][np.cumsum(u)[u] - 1]
tof = (nqt == 3) & ~hb & (bt != 6) & (bt != 7)
hmr = useb0 & (nqt == 1)
interesting = np.flatnonzero(hmr | (useb0 & (nqt == 0)) | push | pop | (tof & hasc) | tof)
interesting = interesting[interesting >= cuts[1]]
S = collections.defaultdict(int); hid = 0; hmr_op = []
stack = []; recs = []
opl = op.tolist()
for k in interesting.tolist():
    t = opl[k]
    if hmr[k]:
        S[int(b0[k])] = 1 << hid; hmr_op.append(k); hid += 1; continue
    if useb0[k]:   # classical bit op
        b = int(b0[k]); base = t & 0x7f
        if base == 0x40: S[b] = 0
        elif base == 0x41: S[b] = 0
        elif base == 0x42:
            if t & 0x80: S[b] ^= S[int(bc[k])]
        if (t & 0x80) and base in (0x40, 0x41): S[b] |= S[int(bc[k])]   # conditional store: depends on cond
        continue
    if t == 0x81: stack.append(int(bc[k])); continue
    if t == 0x01:
        if stack: stack.pop()
        continue
    if tof[k] and k >= cuts[5] and k < cuts[8] and (stack or hasc[k]):
        dep = 0
        for b in stack: dep |= S[b]
        if hasc[k]: dep |= S[int(bc[k])]
        recs.append((k, (t & 0x0f), dep))
pickle.dump(dict(hmr_op=hmr_op, recs=recs), open(out, 'wb'))
print('HMRs', hid, 'conditioned reverse Toffolis', len(recs))
