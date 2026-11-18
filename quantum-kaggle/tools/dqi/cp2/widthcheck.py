"""For erase-then-recompute block pairs (first block's targets measured between): width headroom in the window
[end of first block, start of second block] = 890 - max live; and number of distinct target qubits (value width)."""
import sys, json, numpy as np, collections
sys.path.insert(0, '..')
from kmb import read_kmb
d = read_kmb('w.kmb'); opk = d['op']; nqt = (opk >> 4) & 3; hb = (opk & 0x40) != 0
i3 = np.cumsum(nqt == 3) - 1; i1 = np.cumsum(nqt == 1) - 1
hpos = np.flatnonzero(hb & (nqt == 1)); hq = (d['q0'][i1[hpos]] & 0x7fffffff).astype(np.int64)
live = np.fromfile('w_live.u16', dtype=np.uint16)
R0 = np.fromfile('w_prod.bin', dtype=np.uint64).reshape(-1, 5); R1 = np.fromfile('w_prodf.bin', dtype=np.uint64).reshape(-1, 5)
op = (R0[:, 0] & np.uint64((1 << 40) - 1)).astype(np.int64)
kind = ((R0[:, 1] >> np.uint64(32)) & np.uint64(0xff)).astype(int); cond = (R0[:, 1] & np.uint64(1)).astype(bool)
pc = (R0[:, 1] >> np.uint64(40)).astype(np.int64)
cuts = json.load(open('w_cuts.json'))['w']; names = ['pre','ext','syn','conv','scan',"conv'","syn'","ext'",'post']
tot = collections.Counter()
for s in [1, 2, 3, 5, 6, 7]:
    lo, hi = cuts[s], cuts[s + 1]
    sel = (kind == 1) & ~cond & (pc >= 64) & (op >= lo) & (op < hi)
    occ = collections.defaultdict(list)
    for i in np.flatnonzero(sel): occ[(int(R0[i, 2]), int(R1[i, 2]))].append(int(op[i]))
    pairs = sorted((a, b) for v in occ.values() for a, b in zip(v, v[1:]))
    blocks = []
    for a, b in pairs:
        if blocks and a - blocks[-1]['a1'] < 3000 and abs((b - a) - blocks[-1]['gap']) < 50000:
            blk = blocks[-1]; blk['n'] += 1; blk['a1'] = a; blk['ops'].append(a); blk['b'].append(b)
        else: blocks.append(dict(a0=a, a1=a, n=1, gap=b - a, ops=[a], b=[b]))
    rows = collections.Counter()
    for blk in blocks:
        if blk['n'] < 8 or blk['gap'] >= 300000: continue
        tg = set(int(d['qqq2'][i3[x]] & 0x7fffffff) for x in blk['ops'])
        lo2, hi2 = np.searchsorted(hpos, blk['a1']), np.searchsorted(hpos, min(blk['b']))
        if not (tg & set(hq[lo2:hi2].tolist())): continue
        w = int(live[blk['a1']:min(blk['b'])].max()); head = 890 - w
        rows[(blk['n'], head)] += 1
        tot[(names[s], 'T')] += blk['n']; tot[(names[s], 'T_fits12' if head >= 12 else ('T_fits6' if head >= 6 else 'T_nofit'))] += blk['n']
    print(names[s], 'erase-recompute blocks (size, headroom qubits): count', sorted(rows.items())[:12])
print(dict(tot))
