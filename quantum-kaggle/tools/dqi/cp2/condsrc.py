"""For classically conditioned Toffolis and CCZs in each reverse stage: where do their condition bits come from?
Condition bit producers: HMR (measurement outcome) and BIT_* ops (classical logic). Reports, per reverse stage,
the stage in which the condition bit was last written before use (by HMR or by BIT ops), and CCZ qubit roles."""
import sys, json, numpy as np, collections, bisect
sys.path.insert(0, '..')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); cuts = json.load(open(sys.argv[2]))[sys.argv[3]]
names = ['pre','ext','syn','conv','scan',"conv'","syn'","ext'",'post']
op = d['op']; n = len(op)
bt = op & 0x7f; nqt = (op >> 4) & 3
hasc = ((op & 0x80) != 0) & (op != 0x81); push = op == 0x81; usebc = hasc | push
bci = np.cumsum(usebc) - 1
# b0 operand users: HMR (0x50 family with nqt==1 and 0x40 bit) and BIT ops (nqt==0, 0x40 bit)
hb = (op & 0x40) != 0
useb0 = hb & ((nqt == 1) | (nqt == 0)) & (bt != 6) & (bt != 7)
b0i = np.cumsum(useb0) - 1
writer_pos = np.flatnonzero(useb0); writer_bit = d['b0'][b0i[writer_pos]]
is_hmr = (nqt[writer_pos] == 1)
# last writer of each bit before a given op: build per-bit sorted lists
from collections import defaultdict
wl = defaultdict(list)
for p, b, h in zip(writer_pos.tolist(), writer_bit.tolist(), is_hmr.tolist()): wl[b].append((p, h))
tof = (nqt == 3) & ((op & 0x40) == 0) & (bt != 6) & (bt != 7)
stage = np.zeros(n, np.int8)
for i in range(9): stage[cuts[i]:cuts[i + 1]] = i
# condition stack: track PUSH bits for ops inside PUSH blocks
depth_bits = []; res = collections.Counter(); kinds = collections.Counter()
stk = []
for k in range(cuts[5], cuts[8]):
    t = op[k]
    if t == 0x81: stk.append(int(d['bc'][bci[k]])); continue
    if t == 0x01:
        if stk: stk.pop()
        continue
    if not tof[k]: continue
    bits = list(stk) + ([int(d['bc'][bci[k]])] if hasc[k] else [])
    kind = 'CCZ' if (op[k] & 0x0f) == 0 else 'CCX'
    if not bits:
        kinds[(names[stage[k]], kind, 'uncond')] += 1; continue
    for b in bits[-1:]:
        lst = wl.get(b, [])
        j = bisect.bisect_left([p for p, _ in lst], k) - 1
        if j < 0: src = 'input/mask'
        else:
            p, h = lst[j]; src = ('HMR@' if h else 'BIT@') + names[stage[p]]
        res[(names[stage[k]], kind, src)] += 1
for k, v in sorted(kinds.items()): print('unconditioned', k, v)
for k, v in sorted(res.items()): print('conditioned', k, v)
