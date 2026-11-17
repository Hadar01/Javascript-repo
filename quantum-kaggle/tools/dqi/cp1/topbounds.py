"""Top-level INFO_TAG boundaries: name, enter op, exit op, static T inside. usage: topbounds.py kmb"""
import sys, numpy as np
sys.path.insert(0, sys.path[0])
from kmb import read_kmb
d = read_kmb(sys.argv[1]); op = d['op']; tags = d['tags']; pos = np.flatnonzero(op == 6)
nqt = (op >> 4) & 3; tof = (nqt == 3) & ((op & 0x40) == 0) & ((op & 0x7f) != 6) & ((op & 0x7f) != 7); ct = np.cumsum(tof)
st = []
for t, p in zip(tags, pos):
    k, name = t.split(':', 1)
    if k == '@enter':
        st.append((name, p))
    else:
        nm, p0 = st.pop()
        if not st: print(f"{nm}\t{p0}\t{p}\t{int(ct[p]-ct[p0])}")
