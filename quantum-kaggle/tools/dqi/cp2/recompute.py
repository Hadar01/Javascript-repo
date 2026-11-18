"""Recomputed product blocks per stage: blocks of >= 8 dense products whose identical copies appear later.
For each block pair: size, gap (ops), and whether the first block's target qubits are measured (HMR) between."""
import sys, json, numpy as np, collections
sys.path.insert(0, '..')
from kmb import read_kmb
d = read_kmb('w.kmb'); opk = d['op']; nqt = (opk >> 4) & 3; hb = (opk & 0x40) != 0
i3 = np.cumsum(nqt == 3) - 1; i1 = np.cumsum(nqt == 1) - 1
hpos = np.flatnonzero(hb & (nqt == 1)); hq = (d['q0'][i1[hpos]] & 0x7fffffff).astype(np.int64)
R0 = np.fromfile('w_prod.bin', dtype=np.uint64).reshape(-1, 5); R1 = np.fromfile('w_prodf.bin', dtype=np.uint64).reshape(-1, 5)
op = (R0[:, 0] & np.uint64((1 << 40) - 1)).astype(np.int64)
kind = ((R0[:, 1] >> np.uint64(32)) & np.uint64(0xff)).astype(int); cond = (R0[:, 1] & np.uint64(1)).astype(bool)
pc = (R0[:, 1] >> np.uint64(40)).astype(np.int64)
cuts = json.load(open('w_cuts.json'))['w']; names = ['pre','ext','syn','conv','scan',"conv'","syn'","ext'",'post']
summary = collections.defaultdict(lambda: collections.Counter())
for s in [1, 2, 3, 5, 6, 7]:
    lo, hi = cuts[s], cuts[s + 1]
    sel = (kind == 1) & ~cond & (pc >= 64) & (op >= lo) & (op < hi)
    occ = collections.defaultdict(list)
    for i in np.flatnonzero(sel): occ[(int(R0[i, 2]), int(R1[i, 2]))].append(int(op[i]))
    pairs = []
    for v in occ.values():
        for a, b in zip(v, v[1:]): pairs.append((a, b))
    pairs.sort()
    blocks = []
    for a, b in pairs:
        if blocks and a - blocks[-1]['a1'] < 3000 and abs((b - a) - blocks[-1]['gap']) < 50000:
            blk = blocks[-1]; blk['n'] += 1; blk['a1'] = a; blk['ops'].append(a)
        else: blocks.append(dict(a0=a, a1=a, b0=b, n=1, gap=b - a, ops=[a]))
    for blk in blocks:
        if blk['n'] < 8: continue
        tg = set(int(d['qqq2'][i3[x]] & 0x7fffffff) for x in blk['ops'])
        lo2, hi2 = np.searchsorted(hpos, blk['a1']), np.searchsorted(hpos, blk['a0'] + blk['gap'])
        erased = len(tg & set(hq[lo2:hi2].tolist())) > 0
        g = 'short(<20k)' if blk['gap'] < 20000 else ('mid(<300k)' if blk['gap'] < 300000 else 'long')
        key = (g, 'erased-between' if erased else 'not-erased')
        summary[names[s]][key + ('blocks',)] += 1; summary[names[s]][key + ('T',)] += blk['n']
for s, c in summary.items():
    print(s, {f'{k[0]}/{k[1]}': (c[k[:2] + ('blocks',)], c[k[:2] + ('T',)]) for k in sorted(set(k[:2] for k in c))})
print('=== long/not-erased detail (conv, conv\')')
for s in [3, 5]:
    lo, hi = cuts[s], cuts[s + 1]
    sel = (kind == 1) & ~cond & (pc >= 64) & (op >= lo) & (op < hi)
    occ = collections.defaultdict(list)
    for i in np.flatnonzero(sel): occ[(int(R0[i, 2]), int(R1[i, 2]))].append(int(op[i]))
    pairs = []
    for v in occ.values():
        for a, b in zip(v, v[1:]): pairs.append((a, b))
    pairs.sort(); blocks = []
    for a, b in pairs:
        if blocks and a - blocks[-1]['a1'] < 3000 and abs((b - a) - blocks[-1]['gap']) < 50000:
            blk = blocks[-1]; blk['n'] += 1; blk['a1'] = a; blk['ops'].append(a); blk['ops2'].append(b)
        else: blocks.append(dict(a0=a, a1=a, n=1, gap=b - a, ops=[a], ops2=[b]))
    shown = 0
    for blk in blocks:
        if blk['n'] < 100 or blk['gap'] < 300000: continue
        t1 = collections.Counter(int(d['qqq2'][i3[x]] & 0x7fffffff) for x in blk['ops'])
        t2 = collections.Counter(int(d['qqq2'][i3[x]] & 0x7fffffff) for x in blk['ops2'])
        c1 = set(int(d['qqq0'][i3[x]] & 0x7fffffff) for x in blk['ops']) | set(int(d['qqq1'][i3[x]] & 0x7fffffff) for x in blk['ops'])
        c2 = set(int(d['qqq0'][i3[x]] & 0x7fffffff) for x in blk['ops2']) | set(int(d['qqq1'][i3[x]] & 0x7fffffff) for x in blk['ops2'])
        print(names[s], 'n', blk['n'], 'gap', blk['gap'], 'b1', blk['a0'], 'b2', min(blk['ops2']), '| tgt1', sorted(t1)[:8], 'tgt2', sorted(t2)[:8], 'same-targets', set(t1) == set(t2), '| ctrl1 range', (min(c1), max(c1)), 'ctrl2 range', (min(c2), max(c2)))
        shown += 1
        if shown >= 6: break
