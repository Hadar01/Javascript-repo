"""invsqrt generator v2 (Agent A, our code): L/H split of K0, residual/coarse split of K1, early H phase,
borrowed x[21] carry.  Ideas credited in model.py (anazemcev / Rudra Bhaskar / Kirill Tymchishin / Alex Chilton).
usage: python gen2.py OUT.kmb [--tabs tabs.pkl]
"""
import argparse, pickle, sys, os
from fractions import Fraction
import kickmix as km
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M
from gen import gadd, signed_row, normalize, unnormalize, shift_stages, W


def phase_word(b, f, word, low_exp):
    """Apply 2^(low_exp + j) turns * 2^a to bit j of word (after left shift by a)."""
    ext = b.alloc_qubits(10)
    reg = km.array(list(word) + list(ext))
    shift_stages(b, f, reg, len(word), False)
    for j in range(len(reg)):
        ex = low_exp + j
        if ex < 0:
            b.z_pow(reg[j], Fraction(2) ** (ex + 1))
    shift_stages(b, f, reg, len(word), True)
    b.free(ext)


def build(p, lay, info):
    LB, S, RB, RS, wH, wC = (info[k] for k in ('LB', 'S', 'RB', 'RS', 'wH', 'wC'))
    b = km.CircuitBuilder()
    x = b.create_quantum_register(W, name='x')
    f = b.alloc_qubits(5)
    normalize(b, x, f)
    b.x(x[W - 1])                      # x21 == 1 after normalisation: borrow it as a clean carry
    BOR = (x[W - 1],)
    r = b.alloc_qubits(RB); C = b.alloc_qubits(wC); K2 = b.alloc_qubits(p.w2)
    L = b.alloc_qubits(LB); H = b.alloc_qubits(wH)
    rest = km.array(list(r) + list(C) + list(K2) + list(L))
    full = km.array(list(rest) + list(H))
    t_full, t_rest, t_H = [0] * 256, [0] * 256, [0] * 256
    for (e, a), (k2, c, r0, h, l0) in lay.items():
        v = r0 | (c << RB) | (k2 << (RB + wC)) | (l0 << (RB + wC + p.w2))
        t_rest[a + 128 * e] = v
        t_full[a + 128 * e] = v | (h << (RB + wC + p.w2 + LB))
        t_H[a + 128 * e] = h
    addr = km.array(list(x[14:21]) + [f[0]])
    delta = x[0:M.DB]
    b.init_lookup(table=t_full, address=addr, target=full)
    # high word: phase now, then erase by measurement-based unlookup
    phase_word(b, f, H, S - p.fy - 10)
    b.del_lookup(table=t_H, address=addr, target=H)
    b.free(H)

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

    rrows(False)
    gadd(b, r[RS:], C, borrowed=BOR)          # C += r[11]: R = r[0:11] + 2^11 C
    yrows(False)
    phase_word(b, f, L[p.gy:], p.gy - p.fy - 10)
    yrows(True)
    gadd(b, r[RS:], C, sub=True, borrowed=BOR)
    rrows(True)
    b.del_lookup(table=t_rest, address=addr, target=rest)
    b.free(rest)
    b.x(x[W - 1])
    unnormalize(b, x, f)
    b.free(f)
    return b.finish_circuit()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--tabs')
    a = ap.parse_args()
    p = M.P()
    key, tabs = pickle.load(open(a.tabs, 'rb')); assert key == p.key()
    lay, info = M.layout(p, tabs); print(info)
    c = build(p, lay, info)
    s = c.operation_statistics()
    print('qubits', c.num_qubits, 'toffoli(static)', s.num_toffoli_like, 'rot', s.num_z_pow(min_clifford_hierarchy_level=4),
          'T', s.num_t_like)
    c.to_file(a.out, format='kmb')
