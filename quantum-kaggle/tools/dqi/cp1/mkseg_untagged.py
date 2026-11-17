"""Build stage-segment files for the untagged syed-lineage circuits from manually located boundaries.
Segments: 0 pre, 1 extract_fwd, 2 synth_fwd, 3 conv_fwd, 4 scan, 5 conv_rev, 6 synth_rev, 7 extract_rev, 8 post.
Scan = first..last op conditioned on a mask bit E* between the first and last Toffoli. h890 boundaries are found by
matching a 64-op signature of the sy13 boundary within +0..+456 ops (product retention adds 3 ops per retained pair)."""
import sys, json, numpy as np
sys.path.insert(0, '..')
from kmb import read_kmb
B = {  # boundary ops (start op of segments 2, 3, 6, 7) located from tgtsweep.py output
    'sy13': dict(b1=21602927, b2=26423277, b5=41151117, b6=46905812),
    'v119': dict(b1=15641271, b2=20445678, b5=35100458, b6=40837487),
}
def ecnd(d):
    op = d['op']; ebits = np.zeros(d['num_bits'] + 1, bool)
    for nm, ids in d['regs'].items():
        if nm.startswith('E') and nm[1:].isdigit(): ebits[ids[(ids & 0x80000000) == 0]] = True
    hasc = ((op & 0x80) != 0) & (op != 0x81); push = op == 0x81; use = hasc | push
    idx = np.cumsum(use) - 1; ce = np.zeros(len(op), bool); ce[use] = ebits[d['bc'][idx[use]]]
    nqt = (op >> 4) & 3; tof = (nqt == 3) & ((op & 0x40) == 0) & ((op & 0x7f) != 6) & ((op & 0x7f) != 7)
    return ce, tof
res = {}
sy = None
for tag in ['sy13', 'v119', 'h890']:
    d = read_kmb(f'{tag}.kmb'); op = d['op']; ce, tof = ecnd(d); tp = np.flatnonzero(tof); f, l = tp[0], tp[-1]
    mid = np.flatnonzero(ce[f:l + 1]) + f; s0, s1 = int(mid[0]), int(mid[-1]) + 1
    if tag == 'sy13': sy = (op.copy(), B['sy13'])
    if tag == 'h890':
        sop, sb = sy; b = {}
        for k, v in sb.items():
            sig = sop[v:v + 64]
            hit = [v + o for o in range(0, 457) if np.array_equal(op[v + o:v + o + 64], sig)]
            assert len(hit) >= 1, k; b[k] = hit[0]
    else:
        b = B[tag]
    cuts = [0, int(f), b['b1'], b['b2'], s0, s1, b['b5'], b['b6'], int(l) + 1, len(op)]
    assert all(x < y for x, y in zip(cuts, cuts[1:])), cuts
    seg = np.zeros(len(op), np.uint16)
    for i in range(9): seg[cuts[i]:cuts[i + 1]] = i
    seg.tofile(f'{tag}_stage.u16'); res[tag] = cuts
    ct = np.cumsum(tof)
    print(tag, cuts, 'static T per seg', [int(tof[cuts[i]:cuts[i + 1]].sum()) for i in range(9)])
json.dump(res, open('stage_cuts.json', 'w'))
json.dump(['pre', 'extract_fwd', 'synth_fwd', 'conv_fwd', 'scan', 'conv_rev', 'synth_rev', 'extract_rev', 'post'], open('stage_names.json', 'w'))
