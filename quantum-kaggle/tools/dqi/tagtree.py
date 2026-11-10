"""Static tag tree of a kmb: Toffoli-like (CCX/CCZ/CSWAP, incl _IF) counts per tag path; inside-condition counts."""
import sys, numpy as np, collections, json
sys.path.insert(0, '.')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); op = d['op']; tags = d['tags']
tagpos = np.flatnonzero(op == 0x06); assert len(tagpos) == len(tags)
tof = ((op & 0x30) == 0x30) & ((op & 0x0f) <= 2) & ((op & 0x40) == 0)   # CCZ/CCX/CSWAP and their _IF variants
ctof = np.cumsum(tof); 
# condition depth: PUSH 0x81, POP 0x01
dep = np.cumsum((op == 0x81).astype(np.int32) - (op == 0x01).astype(np.int32))
condtof = tof & ((dep > 0) | ((op & 0x80) != 0))
ccond = np.cumsum(condtof)
def cnt(c, a, b):  # count in ops [a, b)
    return int(c[b - 1] - (c[a - 1] if a > 0 else 0)) if b > a else 0
stack = []; agg = collections.OrderedDict(); top = []
prev = 0; path = ()
nops = len(op)
def add(path, a, b):
    if b <= a: return
    r = agg.setdefault(path, [0, 0, 0, 0])
    r[0] += cnt(ctof, a, b); r[1] += cnt(ccond, a, b); r[2] += b - a
for t, p in zip(tags, tagpos):
    add(tuple(stack), prev, p); prev = p + 1
    kind, name = t.split(':', 1)
    if kind == '@enter':
        stack.append(name); agg.setdefault(tuple(stack), [0, 0, 0, 0])[3] += 1
    else:
        assert stack and stack[-1] == name, (t, stack); stack.pop()
add(tuple(stack), prev, nops)
# roll up inclusive totals
incl = collections.defaultdict(lambda: [0, 0, 0])
for path, (t, c, n, k) in agg.items():
    for i in range(len(path) + 1):
        r = incl[path[:i]]; r[0] += t; r[1] += c; r[2] += n
calls = {p: v[3] for p, v in agg.items()}
tot = incl[()][0]
print('total static toffoli-like', tot, 'in-condition', incl[()][1])
for path in sorted(incl, key=lambda p: (len(p), p)):
    if len(path) <= int(sys.argv[2]) if len(sys.argv) > 2 else 3:
        t, c, n = incl[path]
        print(f"{'  '*len(path)}{'/'.join(path) or 'ROOT'}: calls={calls.get(path,0)} tof={t} ({100*t/tot:.2f}%) cond_tof={c} ops={n}")
json.dump({"/".join(p): dict(incl=[int(x) for x in incl[p]], calls=int(calls.get(p, 0))) for p in incl}, open(sys.argv[1].split('/')[-2] + '_tagtree.json', 'w'))
