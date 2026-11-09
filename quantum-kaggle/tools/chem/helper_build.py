"""Helper-carrying ANGLE_k builder: Lera's (marculera) tensor-lookup circuit (tensorqrom.build_circuit, Apache-2.0)
modified so that low-address monomials stored in the words' top bits are reused as cache qubits across batches.

In the public (8, 143, 44) table (syed3000) bit 7 of word j equals bit 6 XOR h_j(l), where h_j is a fixed degree-2
monomial of the four low address bits (l0l1, l0l2, l1l2, l0l3, l1l3 for j = 0..4; a few late columns carry none).
After `b7 ^= b6` the top bit of every incoming word holds h_j, so those monomials need no AND in the low cache.
A helper is used as cache only when the incoming and outgoing batch carry the same monomial in that word ("persisting"),
which makes the circuit correct for both reachable inputs (forward: batch k-1, reverse: batch k).
Words whose helper changes get the correction (h_in XOR h_out) from cache qubits; words without helpers in either batch
lend their cleared top bit as a scratch qubit (heliosli's idea, as in tensorqrom).

Modifications to the Apache-2.0 original by Agent C, 2026-11-09.

usage: python helper_build.py TABLE.npz PLAN_DIR OUT_DIR [--npz-bytes SUBMISSION.npz]
  TABLE.npz: angle_words, codes (+ factorization arrays); PLAN_DIR: circuit_K.json from marculera_plan_search.py.
  --npz-bytes: copy this file byte for byte as OUT_DIR/submission.npz (keeps the words and weights identical).
"""
from __future__ import annotations

import argparse, json, os, shutil, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def setup_paths(scripts: Path):
    for p in (scripts, scripts / 'marculera' / 'dfthc_refit', scripts / 'marculera' / 'dfthc_refit' / 'experiments'):
        sys.path.insert(0, str(p))


def helper_masks(words: np.ndarray, brot: int = 8, lowbits: int = 4) -> np.ndarray:
    """(ncols,) low monomial mask carried in bit brot-1 of each column (0: none). Raises if not a pure low monomial."""
    A, ncol = words.shape
    low = np.arange(A) % (1 << lowbits)
    out = np.zeros(ncol, np.int64)
    for c in range(ncol):
        x = ((words[:, c] >> (brot - 1)) ^ (words[:, c] >> (brot - 2))) & 1
        if not x.any():
            continue
        f = np.zeros(1 << lowbits, np.uint8)
        for l in range(1 << lowbits):
            v = set(x[low == l].tolist())
            assert len(v) == 1, f'column {c}: top-bit helper depends on high address bits'
            f[l] = v.pop()
        anf = f.copy()
        for i in range(lowbits):
            for y in range(1 << lowbits):
                if y >> i & 1:
                    anf[y] ^= anf[y ^ (1 << i)]
        ms = np.flatnonzero(anf)
        assert len(ms) == 1 and bin(ms[0]).count('1') >= 2, f'column {c}: helper is not a single nonlinear monomial'
        out[c] = int(ms[0])
    return out


def fill_dontcare(d: np.ndarray, degs: np.ndarray, n_rows: int, brot: int = 8, lowbits: int = 4) -> np.ndarray:
    """Choose the don't-care rows of the last (partial) 16-address block for the free outputs so that, for the high
    monomial of that block, the low ANF uses only monomials of the low bits already pinned by the real rows."""
    L = 1 << lowbits
    n = n_rows % L
    if not n:
        return d
    d = d.copy()
    H = len(d) // L
    hl = H - 1                                   # the partial chunk index (also its high monomial mask)
    subs = [h for h in range(H) if h & hl == h and h != hl]
    pin = (1 << (n - 1).bit_length()) - 1        # real rows l < n live in the low bits of this mask
    for o in np.flatnonzero(degs == 0):
        w, bit = int(o) // (brot - 1), int(o) % (brot - 1)
        f = lambda h, l: (int(d[h * L + l, w]) >> bit) & 1   # noqa: E731
        g = [0] * L
        for l in range(L):
            for h in subs:
                g[l] ^= f(h, l)
        T = [f(hl, l) ^ g[l] for l in range(L)]
        for l in range(n, L):
            T[l] = T[l & pin] if (l & pin) < n else 0
            v = T[l] ^ g[l]
            d[hl * L + l, w] = (d[hl * L + l, w] & ~(1 << bit)) | (v << bit)
            if bit == brot - 2:                  # keep the signed-gauge top bit equal to bit 6 on padded rows
                d[hl * L + l, w] = (d[hl * L + l, w] & ~(1 << (brot - 1))) | (v << (brot - 1))
    return d


def build_circuit_h(delta, terms, n_sel, brot, lowbits, hin, hout):
    import kickmix as km
    import tensorqrom as tq
    from tensorqrom import anf_tensor, mixed_of, mobius, _monomial_values, _bits, _bits_vec
    delta = np.asarray(delta, dtype=np.int64)
    count, J = delta.shape
    # signed-gauge part of the delta: bit 7 handled separately (= bit 6 xor h_in xor h_out)
    d7 = delta & ~(1 << (brot - 1))
    d7 |= ((d7 >> (brot - 2)) & 1) << (brot - 1)
    C = anf_tensor(d7, brot, lowbits)
    L, H, O = C.shape
    assert np.array_equal(mixed_of(terms, L - 1, H - 1, O), C[1:, 1:]), 'decomposition does not cover the tensor'
    low = C[:, 0].copy()
    high = C[0].copy()
    high[0] = 0
    vl, vh = _monomial_values(L, L), _monomial_values(H, H)
    hb = max(1, (H - 1).bit_length())
    for a1, b1, a2, b2, s in terms:
        outs = np.array(_bits(s))
        if a2:
            pl = mobius((vl @ np.array(_bits_vec(a1, L - 1)) & 1) & (vl @ np.array(_bits_vec(a2, L - 1)) & 1))
            low[:, outs] ^= pl[:, None]
        if b2:
            th = np.zeros(1 << hb, np.uint8)
            th[:H] = (vh @ np.array(_bits_vec(b2, H - 1)) & 1) & (vh @ np.array(_bits_vec(b1, H - 1)) & 1)
            ph = mobius(th)[:H]
            high[:, outs] ^= ph[:, None]
    low[0] ^= high[0]
    high[0] = 0

    b = km.CircuitBuilder()
    sel = b.create_quantum_register(n_sel, 'selection')
    words = [b.create_quantum_register(brot, f'word_{j}') for j in range(J)]
    for w in words:
        b.cx(w[brot - 2], w[brot - 1])          # top bit now holds the incoming helper monomial (or 0)
    outputs = [[words[j][k]] for j in range(J) for k in range(brot - 1)]
    persist = {int(hin[j]): words[j][brot - 1] for j in range(J) if hin[j] and hin[j] == hout[j]}
    pool = [words[j][brot - 1] for j in range(J) if not hin[j] and not hout[j]]
    borrowed: list = []

    def take():
        if pool:
            borrowed.append(pool[-1])
            return pool.pop()
        return b.alloc_qubits(1)[0]

    def give(t) -> None:
        if any(t is q for q in borrowed):
            borrowed[:] = [q for q in borrowed if q is not t]
            pool.append(t)
        else:
            b.free(t)

    def cache(size, offset, made, provided):
        q = {}
        for mask in range(1, size):
            top = mask.bit_length() - 1
            if mask == 1 << top:
                q[mask] = sel[offset + top]
            elif mask in provided:
                q[mask] = provided[mask]
            else:
                t = take()
                b.init_and(q[mask ^ (1 << top)], sel[offset + top], t)
                q[mask] = t
                made.append((q[mask ^ (1 << top)], sel[offset + top], t))
        return q

    made: list = []
    Y = cache(H, lowbits, made, {})
    X = cache(L, 0, made, persist)

    def qubit(q):
        return X[q + 1] if q < L - 1 else Y[q - L + 2]

    def targets(s):
        return [q for o in s for q in outputs[o]]

    def fan_ccx(c1, c2, ts):
        first, rest = ts[0], ts[1:]
        for t in rest:
            b.cx(first, t)
        b.ccx(c1, c2, first)
        for t in reversed(rest):
            b.cx(first, t)

    def product(a1, b1, a2, b2, s):
        m1, m2 = a1 | (b2 << (L - 1)), a2 | (b1 << (L - 1))
        if not m1 or not m2 or m1 == m2:
            return
        p1 = _bits(m1)[0]
        ops = [(q, p1) for q in _bits(m1) if q != p1]
        if m2 >> p1 & 1:
            m2 ^= m1 ^ (1 << p1)
        p2 = next(q for q in _bits(m2) if q != p1)
        ops += [(q, p2) for q in _bits(m2) if q != p2]
        for src, dst in ops:
            b.cx(qubit(src), qubit(dst))
        fan_ccx(qubit(p1), qubit(p2), targets(_bits(s)))
        for src, dst in reversed(ops):
            b.cx(qubit(src), qubit(dst))

    for t in terms:
        product(*t)
    for m in range(L):
        ts = targets(np.flatnonzero(low[m]))
        if ts:
            if m == 0:
                b.x(km.array(ts))
            else:
                b.cx(X[m], km.array(ts))
    for m in range(1, H):
        ts = targets(np.flatnonzero(high[m]))
        if ts:
            b.cx(Y[m], km.array(ts))
    # top bits: target = b6 (new) xor h_target; currently h_current. Correct by (h_in xor h_out) while caches live.
    for j in range(J):
        for m in {int(hin[j]), int(hout[j])} if hin[j] != hout[j] else ():
            if m:
                assert X[m] is not words[j][brot - 1]
                b.cx(X[m], words[j][brot - 1])
    for c1, c2, t in reversed(made):
        b.del_and(c1, c2, t)
        give(t)
    for w in words:
        b.cx(w[brot - 2], w[brot - 1])
    return b.finish_circuit()


def build_family(words, deg, plans: Path, brot=8, J=5, lowbits=4, log=print, dontcare=False, only=None, base=None):
    import rmcode
    from fourqrom import batch_deltas
    hm = helper_masks(words, brot, lowbits)
    A = len(words)
    n_sel = max(1, (A - 1).bit_length())
    fam, total = [], 0
    for k, d in enumerate(batch_deltas(words, J)):
        degs = rmcode.output_degrees(deg, k, J, brot)
        d = rmcode.pad(d, degs, brot)
        if dontcare:
            d = fill_dontcare(d, degs, A, brot, lowbits)
        if only is not None and k not in only:
            fam.append(base[k]); total += base[k].operation_statistics().num_toffoli_like
            log(f'circuit {k}: kept from base, {base[k].operation_statistics().num_toffoli_like} Toffolis'); continue
        plan = json.loads((plans / f'circuit_{k}.json').read_text())
        assert not plan['config'].get('cnots'), 'basis-change plans not supported here'
        terms = [tuple(t) for t in plan['terms']]
        cols = [k * J + j for j in range(J)]
        hout = np.array([hm[c] if c < len(hm) else 0 for c in cols])
        hin = np.array([hm[c - J] if (k and c - J < len(hm)) else 0 for c in cols])
        c = build_circuit_h(d, terms, n_sel, brot, lowbits, hin, hout)
        st = c.operation_statistics().num_toffoli_like
        log(f'circuit {k}: {len(terms)} products, {st} Toffolis, {c.num_qubits} qubits, hin {hin.tolist()} hout {hout.tolist()}')
        assert c.num_qubits <= 128
        fam.append(c); total += st
    log(f'Toffolis per pass {total}')
    return fam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('table'); ap.add_argument('plans'); ap.add_argument('out')
    ap.add_argument('--scripts', default=os.environ.get('QK_SCRIPTS', ''))
    ap.add_argument('--npz-bytes')
    ap.add_argument('--dontcare', action='store_true', help='deltas with fill_dontcare (plans from dc_search.py)')
    ap.add_argument('--only', help='comma list of circuits to build; the rest are copied from --base')
    ap.add_argument('--base', help='directory with angle_k_*.kmb to keep for circuits not in --only')
    a = ap.parse_args()
    setup_paths(Path(a.scripts))
    import build
    with np.load(a.table) as z:
        words, deg = np.asarray(z['angle_words'], np.int64), np.asarray(z['codes'], np.int64)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    only = base = None
    if a.only:
        import kickmix as km
        only = {int(x) for x in a.only.split(',')}
        base = [km.Circuit.from_file(str(Path(a.base) / f'angle_k_{k}.kmb'), format='kmb') for k in range(15)]
    fam = build_family(words, deg, Path(a.plans), dontcare=a.dontcare, only=only, base=base)
    build.write_kmx_family(fam, out, format='kmb')
    if a.npz_bytes:
        shutil.copyfile(a.npz_bytes, out / 'submission.npz')
    print('wrote', out)


if __name__ == '__main__':
    main()
