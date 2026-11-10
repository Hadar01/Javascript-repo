"""Write per-op uint16 segment ids from INFO_TAG nesting. Segment = innermost tag path. usage: mkseg.py kmb out.u16 out.json"""
import sys, json, numpy as np
sys.path.insert(0, '.')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); op = d['op']; tags = d['tags']
pos = np.flatnonzero(op == 0x06)
paths = {(): 0}; seg = np.zeros(len(op), np.uint16); stack = []; prev = 0; cur = 0
for t, p in zip(tags, pos):
    seg[prev:p + 1] = cur
    kind, name = t.split(':', 1)
    if kind == '@enter': stack.append(name)
    else: stack.pop()
    cur = paths.setdefault(tuple(stack), len(paths)); prev = p + 1
seg[prev:] = cur
seg.tofile(sys.argv[2]); json.dump(['/'.join(p) for p in sorted(paths, key=paths.get)], open(sys.argv[3], 'w'))
print(len(paths), 'segments')
