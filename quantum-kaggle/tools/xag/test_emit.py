"""Emit the invsqrt table XAG with kickmix and check it on all 256 addresses (forward values; forward+reverse
leaves everything clean with zero phase).  usage: python test_emit.py tabs.pkl [budget]"""
import sys, itertools, numpy as np
sys.path.insert(0, '/home/user/Javascript-repo/quantum-kaggle/tools/xag')
from bench_invsqrt import table_targets, anf
import xag, kickmix as km
T = table_targets(sys.argv[1]); budget = int(sys.argv[2]) if len(sys.argv) > 2 else None
order = sorted(range(len(T)), key=lambda i: sum(anf(T[i])))
helpers = [c for grp in (range(0, 4), range(4, 8)) for d in range(2, 5) for c in itertools.combinations(grp, d)]
r = (xag.synthesize(T, 8, helpers=helpers, order=order) if budget is None
     else xag.synthesize_budget(T, 8, budget=budget, helpers=helpers, order=order))
def build(rev):
    b = km.CircuitBuilder()
    a = b.create_quantum_register(8, name='a'); t = b.create_quantum_register(len(T), name='t')
    em = xag.Emitter(b, km, list(a), list(t)); em.forward(r['plan'])
    if rev: xag.reverse_fresh(em, r, T, 8)
    return b.finish_circuit()
for rev in (False, True):
    c = build(rev); s = c.operation_statistics()
    sim = km.Simulator(batch_size=256, seed=7)
    sim.use_same_registers_as(c)
    for p in range(256): sim.write_within_shot('a', p, p)
    sim.do(c)
    ok = True
    for p in range(256):
        val = sim.read_within_shot('t', p, out=int)
        want = 0 if rev else sum(((T[i] >> p) & 1) << i for i in range(len(T)))
        if val != want: ok = False
    ph = [sim.read_shot_phase(p) for p in range(256)]
    print('reverse' if rev else 'forward', 'ok', ok, 'toffolis', s.num_toffoli_like, 'qubits', c.num_qubits,
          'phases zero' if rev and all(x % 2 == 0 for x in ph) else '', 'planned ANDs', r['ands'])
