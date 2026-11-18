"""Map stage cut points from a reference kmb (h890, cp1 cuts) onto a patched descendant by op-code signature search.
usage: mapcuts.py ref.kmb ref_tag new.kmb new_tag  (reads ../cp1/stage_cuts.json; writes new_tag_stage.u16 and cuts)"""
import sys, json, numpy as np
sys.path.insert(0, '..')
from kmb import read_kmb
ref, rtag, new, ntag = sys.argv[1:5]
cuts = json.load(open('../cp1/stage_cuts.json'))[rtag]
A = read_kmb(ref)['op']; d = read_kmb(new); B = d['op']
def find(sig):
    c = np.flatnonzero(B[:len(B) - len(sig)] == sig[0])
    for k in range(1, len(sig)):
        c = c[B[c + k] == sig[k]]
        if len(c) <= 1: break
    return c
def ecnd(d):
    op = d['op']; ebits = np.zeros(d['num_bits'] + 1, bool)
    for nm, ids in d['regs'].items():
        if nm.startswith('E') and nm[1:].isdigit(): ebits[ids[(ids & 0x80000000) == 0]] = True
    hasc = ((op & 0x80) != 0) & (op != 0x81); push = op == 0x81; use = hasc | push
    idx = np.cumsum(use) - 1; ce = np.zeros(len(op), bool); ce[use] = ebits[d['bc'][idx[use]]]
    nqt = (op >> 4) & 3; tof = (nqt == 3) & ((op & 0x40) == 0) & ((op & 0x7f) != 6) & ((op & 0x7f) != 7)
    return ce, tof
ce, tof = ecnd(d); tp = np.flatnonzero(tof); f, l = int(tp[0]), int(tp[-1])
mid = np.flatnonzero(ce[f:l + 1]) + f; s0, s1 = int(mid[0]), int(mid[-1]) + 1
newc = {}
for name, idx in [('b1', 2), ('b2', 3), ('b5', 6), ('b6', 7)]:
    b = cuts[idx]
    for L in (512, 256, 128, 64):
        c = find(A[b:b + L])
        if len(c):
            off = {'b1': 0, 'b2': s0 - 30335510, 'b5': s1 - 35627791, 'b6': s1 - 35627791}[name] if rtag == 'h890' else 0
            exp = b + off; best = int(c[np.argmin(np.abs(c - exp))])
            newc[name] = best; print(name, 'ref', b, '->', best, 'sig', L, 'matches', len(c), 'nearest-to-expected dist', abs(best - exp), 'next', sorted(np.abs(c - exp))[1:3]); break
    else:
        raise SystemExit('no match for ' + name)
cut = [0, f, newc['b1'], newc['b2'], s0, s1, newc['b5'], newc['b6'], l + 1, len(B)]
assert all(x < y for x, y in zip(cut, cut[1:])), cut
seg = np.zeros(len(B), np.uint16)
for i in range(9): seg[cut[i]:cut[i + 1]] = i
seg.tofile(f'{ntag}_stage.u16')
print(ntag, cut, 'static T per seg', [int(tof[cut[i]:cut[i + 1]].sum()) for i in range(9)])
json.dump({ntag: cut}, open(f'{ntag}_cuts.json', 'w'))
