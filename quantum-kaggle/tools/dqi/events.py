"""Compress an op range into coarse events: T<n> (Toffoli-likes), SW<n> (swap runs >=12), H<n> (HMR runs), tags, X-on-ancilla.
Linear (CX/SWAP short) ops are skipped. usage: events.py kmb a b [maxevents]"""
import sys, numpy as np
sys.path.insert(0, '.')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); a, b = int(sys.argv[2]), int(sys.argv[3]); mx = int(sys.argv[4]) if len(sys.argv) > 4 else 400
op = d['op']; tags = d['tags']; pos = {int(p): i for i, p in enumerate(np.flatnonzero(op == 6))}
nq = (op >> 4) & 3; i1 = np.cumsum(nq == 1) - (nq == 1)
ev = []; k = a
def push(e):
    if ev and ev[-1][0] == e[0] and e[0] in ('T', 'Z', 'CS'): ev[-1][1] += e[1]
    else: ev.append(list(e))
while k < b:
    t = op[k]
    if t == 6: ev.append(['#' + tags[pos[k]], 0, k]); k += 1; continue
    if t == 0x22:
        j = k
        while j < b and op[j] == 0x22: j += 1
        if j - k >= 12: ev.append(['SW', j - k, k])
        k = j; continue
    if t == 0x50:
        j = k
        while j < b and op[j] == 0x50: j += 1
        ev.append(['H', j - k, k]); k = j; continue
    if (t & 0x7f) == 0x31: push(['T', 1, k])
    elif (t & 0x7f) == 0x30: push(['Z', 1, k])
    elif (t & 0x7f) == 0x32: push(['CS', 1, k])
    elif t == 0x11 and d['q0'][i1[k]] >= 840: ev.append(['X', int(d['q0'][i1[k]]), k])
    k += 1
out = []
for e in ev[:mx]:
    out.append(f"{e[0]}{e[1] if e[0] not in ('X',) or True else ''}@{e[2]}" if e[0][0] != '#' else f"[{e[0][1:]}]")
print(' '.join(out))
