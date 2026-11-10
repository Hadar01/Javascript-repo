"""Extract the tagged 'multiply v' kernel instances from v100 and symbolically simulate them over GF(2):
each qubit value is a set of monomials (frozenset of input-variable indices, degree<=2) represented as Python ints
(bit per monomial id). Reports: input/output qubits, whether the map is bilinear, restoration of inputs, temps."""
import sys, json, hashlib, numpy as np
sys.path.insert(0, '..'); sys.path.insert(0, '.')
from kmb import read_kmb, opname
S = '/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad'
d = read_kmb(S + '/cand/pub3/dqi.kmb'); op = d['op']; tags = d['tags']; pos = np.flatnonzero(op == 6)
nq = (op >> 4) & 3; i3 = np.cumsum(nq == 3) - (nq == 3); i2 = np.cumsum(nq == 2) - (nq == 2)
mv = [int(p) for i, p in enumerate(pos) if tags[i] == '@enter:multiply v']
mx = [int(p) for i, p in enumerate(pos) if tags[i] == '@exit:multiply v']
print('instances', len(mv))
inst = []
for a, b in zip(mv, mx):
    ops = []
    for k in range(a + 1, b):
        t = int(op[k])
        if t == 0x21: ops.append(('CX', int(d['qq0'][i2[k]]), int(d['qq1'][i2[k]])))
        elif t == 0x31: ops.append(('CCX', int(d['qqq0'][i3[k]]), int(d['qqq1'][i3[k]]), int(d['qqq2'][i3[k]])))
        else: raise SystemExit(f'unexpected op {opname(t)} in kernel')
    inst.append(ops)
# qubit roles for instance 0
ops = inst[0]
ctrl = set(); tgt = set()
for o in ops:
    if o[0] == 'CCX': ctrl |= {o[1], o[2]}; tgt.add(o[3])
touched = sorted({q for o in ops for q in o[1:]})
print('touched qubits', len(touched), 'CCX', sum(o[0] == 'CCX' for o in ops))
# group touched qubits into the 3 registers using the CX structure: CX within x, within y, within z
import collections
adj = collections.defaultdict(set)
for o in ops:
    if o[0] == 'CX': adj[o[1]].add(o[2]); adj[o[2]].add(o[1])
comp = {}; cid = 0
for q in touched:
    if q in comp: continue
    st = [q]; comp[q] = cid
    while st:
        u = st.pop()
        for w in adj[u]:
            if w not in comp: comp[w] = cid; st.append(w)
    cid += 1
groups = collections.defaultdict(list)
for q, c in comp.items(): groups[c].append(q)
for c, qs in groups.items():
    qs = sorted(qs); r = 'ctrl' if set(qs) & ctrl else 'tgt'
    print('component', c, len(qs), 'qubits', qs[:6], '...', 'role', r, 'targets?', bool(set(qs) & tgt))
json.dump(dict(ops=inst[0], instances=[[o for o in x] for x in inst[:1]]), open('kernel0.json', 'w'))
# are all 6 instances identical up to relabeling? compare op-type sequences and relative structure
sigs = []
for ops_ in inst:
    lab = {}
    sig = []
    for o in ops_:
        sig.append((o[0],) + tuple(lab.setdefault(q, len(lab)) for q in o[1:]))
    sigs.append(hashlib.sha256(repr(sig).encode()).hexdigest()[:16])
print('canonical signatures of instances:', sigs)
