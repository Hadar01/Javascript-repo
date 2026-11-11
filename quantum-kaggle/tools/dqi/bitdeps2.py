"""Classical dataflow between a union of op blocks B and the rest of the circuit, by simulating last-writer per bit.
Reports reads in B of values last written outside B (excluding never-written = initial E/zero), and reads outside B of
values last written inside B. usage: bitdeps2.py kmb a1 a2 b1 b2"""
import sys, numpy as np
sys.path.insert(0, '.')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); blocks = [(int(sys.argv[2]), int(sys.argv[3])), (int(sys.argv[4]), int(sys.argv[5]))]
op = d['op']; n = len(op)
inB = np.zeros(n, bool)
for a, b in blocks: inB[a:b + 1] = True
hb = (op & 0x40) != 0; hc = (op & 0x80) != 0
ib = np.cumsum(hb) - hb; ic = np.cumsum(hc) - hc
wr = np.flatnonzero(hb); rd = np.flatnonzero(hc)
# BIT_INVERT(_IF) and BIT_STORE*_IF also read the target bit (invert) -> treat BIT_INVERT target as read+write
events = []
for k in wr: events.append((int(k), 1, int(d['b0'][ib[k]])))          # write
for k in rd: events.append((int(k), 0, int(d['bc'][ic[k]])))          # read (condition)
inv = np.flatnonzero((op & 0x7f) == 0x42)
for k in inv: events.append((int(k), 0, int(d['b0'][ib[k]])))         # invert reads its target
events.sort()
last = {}; in_from_out = set(); out_from_in = set()
for k, w, bt in events:
    if w == 0:
        lw = last.get(bt)
        if lw is not None:
            if inB[k] and not inB[lw]: in_from_out.add(bt)
            if not inB[k] and inB[lw]: out_from_in.add(bt)
    else: last[bt] = k
print('bits read inside blocks, last written outside:', len(in_from_out), sorted(in_from_out)[:15])
print('bits read outside blocks, last written inside:', len(out_from_in), sorted(out_from_in)[:15])
