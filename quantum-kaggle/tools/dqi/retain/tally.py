"""Tally identity violations across check_*.txt files per candidate class.
usage: tally.py <hash records> <check files...>"""
import sys, collections, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0]); import recs
r = recs.load(sys.argv[1]); byk = {int(x['k']): x for x in r[r['sub'] == 0]}; N = 16384
viol = None; nzs = None
for f in sys.argv[2:]:
    rows = [l.split() for l in open(f)]
    v = np.array([int(x[5]) for x in rows]); nz = np.array([int(x[7]) for x in rows])
    viol = v if viol is None else viol + v; nzs = nz if nzs is None else nzs + nz
    keys = rows
def cls(x):
    if x[0] == 'PP': return 'PP group1' if int(x[1]) < 22_000_000 else 'PP groups2-5'
    return 'F popP>=100' if byk[int(x[1])]['popP'] >= 100 else 'F popP<100'
cat = [cls(x) for x in keys]; w = np.array([byk[int(x[2])]['popC'] / N for x in keys])
print(f'{len(sys.argv) - 2} sample sets')
for c in sorted(set(cat)):
    m = np.array([z == c for z in cat]); ok = m & (viol == 0)
    print(f'  {c:14s} candidates {int(m.sum()):5d}  never violated {int(ok.sum()):5d}  weight of survivors {w[ok].sum():8.2f}')
np.save('survivors.npy', np.array([' '.join(x[:4]) for x, v in zip(keys, viol) if v == 0]))
