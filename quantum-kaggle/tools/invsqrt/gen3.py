"""invsqrt generator v3 (Agent A): gen2 + XAG table construction field by field (tools/xag), K2 erased after
the R rows and rebuilt for the reverse R rows.
usage: python gen3.py OUT.kmb --tabs tabs.pkl [--budget B]"""
import argparse, pickle, sys, os
import kickmix as km
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'xag'))
import model as M
from gen import gadd, signed_row, normalize, unnormalize, W
from gen2 import phase_word
import xag


def field_funcs(lay, key, width):
    out = []
    for bit in range(width):
        v = 0
        for (e, a), vals in lay.items():
            if (vals[key] >> bit) & 1: v |= 1 << (a + 128 * e)
        out.append(v)
    return out


BD = int(os.environ.get('BD', '12'))
def build(p, lay, info, budget=25, seed=0, rebuild_k2=True):
    LB, S, RB, RS, wH, wC = (info[k] for k in ('LB', 'S', 'RB', 'RS', 'wH', 'wC'))
    # lay values: (K2, C, r0, H, L0)
    fK2, fC, fr, fH, fL = (field_funcs(lay, i, w) for i, w in ((0, p.w2), (1, wC), (2, RB), (3, wH), (4, LB)))
    b = km.CircuitBuilder()
    x = b.create_quantum_register(W, name='x')
    f = b.alloc_qubits(5)
    normalize(b, x, f)
    b.x(x[W - 1]); BOR = (x[W - 1],)
    addr = list(x[14:21]) + [f[0]]
    ctx = xag.XagContext(b, km, addr, seed=seed)
    delta = x[0:M.DB]
    # 1. high word: build, phase (kept live, erased once the rest of the table enriches the span)
    H = b.alloc_qubits(wH)
    a0=ctx.ands; ctx.build(fH, list(H), budget=budget, base=True); print('H build', ctx.ands-a0, 'alloc', b.num_allocated_qubits)
    phase_word(b, f, H, S - p.fy - 10)
    # 2. rest of the table
    r = b.alloc_qubits(RB); C = b.alloc_qubits(wC); K2 = b.alloc_qubits(p.w2); L = b.alloc_qubits(LB)
    a0=ctx.ands; ctx.build(fK2 + fC + fr + fL, list(K2) + list(C) + list(r) + list(L), budget=budget, base=True, base_drop=BD); print('rest build', ctx.ands-a0)
    ctx.erase(list(H)); b.free(H)

    def rrows(inv):
        rows = p.r2rows()
        for i in (reversed(rows) if inv else rows):
            sh = p.sh2[i]
            signed_row(b, delta[i], K2[sh:], r, K2[sh - 1] if sh >= 1 else None, inv, BOR)

    Rfull = list(r[:RS]) + list(C)

    def yrows(inv):
        rows = list(reversed(range(M.DB)))
        for i in (reversed(rows) if inv else rows):
            sh = p.sh1[i]
            signed_row(b, delta[i], Rfull[sh:], L, Rfull[sh - 1] if sh >= 1 else None, inv, BOR)

    ctx.forget(list(r))
    rrows(False)
    if rebuild_k2:
        ctx.erase(list(K2))           # span still holds C and L0 (pure table values)
    ctx.forget(list(C)); ctx.forget(list(L))
    gadd(b, r[RS:], C, borrowed=BOR)
    yrows(False)
    phase_word(b, f, L[p.gy:], p.gy - p.fy - 10)
    yrows(True)
    gadd(b, r[RS:], C, sub=True, borrowed=BOR)
    ctx.know(list(C), fC); ctx.know(list(L), fL)
    if rebuild_k2:
        a0=ctx.ands; ctx.build(fK2, list(K2), budget=budget, base=False); print('K2 rebuild', ctx.ands-a0)
    rrows(True)
    ctx.know(list(r), fr)
    a0=ctx.ands; base = ctx.make_base(); print('final base', ctx.ands-a0)
    ctx.erase(list(r) + list(C) + list(K2) + list(L))
    ctx.drop(base)
    b.free(km.array(list(r) + list(C) + list(K2) + list(L)))
    b.x(x[W - 1])
    unnormalize(b, x, f)
    b.free(f)
    return b.finish_circuit(), ctx.ands


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--tabs'); ap.add_argument('--budget', type=int, default=25)
    ap.add_argument('--no-rebuild', action='store_true')
    a = ap.parse_args()
    p = M.P(); key, tabs = pickle.load(open(a.tabs, 'rb')); assert key == p.key()
    lay, info = M.layout(p, tabs)
    c, ands = build(p, lay, info, budget=a.budget, rebuild_k2=not a.no_rebuild)
    s = c.operation_statistics()
    print('qubits', c.num_qubits, 'toffoli(static)', s.num_toffoli_like, 'xag ANDs', ands,
          'rot', s.num_z_pow(min_clifford_hierarchy_level=4))
    c.to_file(a.out, format='kmb')
