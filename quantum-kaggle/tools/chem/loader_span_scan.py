"""Exact shared-product scan for one dfthcsos ANGLE loader on its reachable states.

Simulates ANGLE_0 .. ANGLE_{k-1} then ANGLE_k on exactly the verifier's addresses 0..num_vectors-1 (num_vectors =
rows of `angle_words` in submission.npz), starting from zeroed word registers. Both reachable entry states of ANGLE_k are
scanned together, as the verifier runs each circuit twice: forward (words = batch k-1) and on the reverse traversal
(words = batch k, see scoreinfra/circuits.py recover_words_from_circuits). At every CCX of ANGLE_k it asks whether the
product it XORs into its target is a GF(2) combination of the other live qubits (plus the constant 1) at that moment,
on every simulated state. If so, the CCX can be replaced by CNOTs/X with no extra qubit and no Toffoli; CX/CCX act on
basis states without phase, so the replacement is exact on the reachable subspace.

usage: loader_span_scan.py <dfthcsos dir> <k> <work dir>
"""
import sys, re, pathlib
import numpy as np
import kickmix as km

D, K, WD = pathlib.Path(sys.argv[1]), int(sys.argv[2]), pathlib.Path(sys.argv[3])
WD.mkdir(parents=True, exist_ok=True)
NSEL = 11
NV = int(np.load(D / 'submission.npz')['angle_words'].shape[0])   # verifier's num_vectors
LANES = 2 * NV  # forward lanes then reverse lanes
GATE = re.compile(r'^(CX|CCX|X|R|HMR|CZ)\s+(.*?)(?:\s+if\s+(\S+))?$')


def ops(k):
    p = WD / f'angle_k_{k}.kmx'
    if not p.exists():
        km.Circuit.from_file(str(D / f'angle_k_{k}.kmb'), format='kmb').to_file(str(p), format='kmx')
    out = []
    for line in p.read_text().splitlines():
        m = GATE.match(line.strip())
        if m:
            name, args, cond = m.groups()
            qs = [int(a[1:]) for a in args.split() if a.startswith('q')]
            out.append((name, qs, cond))
    return out


def fresh(nq):
    Q = np.zeros((nq, LANES), dtype=bool)
    sel = np.arange(LANES) % NV
    for i in range(NSEL):
        Q[i] = (sel >> i) & 1
    return Q


def run(Q, prog, scan=False):
    hits, scanned = [], 0
    for idx, (name, qs, cond) in enumerate(prog):
        if cond is not None and name != 'CZ':
            raise SystemExit(f'conditional value op not modelled: {name} {qs} if {cond}')
        if name == 'CX':
            Q[qs[1]] ^= Q[qs[0]]
        elif name == 'X':
            Q[qs[0]] ^= True
        elif name in ('R', 'HMR'):
            Q[qs[0]] = False
        elif name == 'CCX':
            a, b, t = qs
            p = Q[a] & Q[b]
            if scan:
                scanned += 1
                if in_span(Q, p, exclude=t):
                    hits.append((idx, qs))
            Q[t] ^= p
    return hits, scanned


def in_span(Q, p, exclude):
    rows = [Q[q] for q in range(Q.shape[0]) if q != exclude and Q[q].any()]
    rows.append(np.ones(LANES, dtype=bool))
    pad = (-LANES) % 64  # zero padding, identical for every row and for p
    M = np.packbits(np.pad(np.array(rows), ((0, 0), (0, pad))), axis=1).view(np.uint64)  # GF(2) rows
    v = np.packbits(np.pad(p, (0, pad))).view(np.uint64).copy()
    piv = []  # Gaussian elimination, reduce v
    M = M.copy()
    for r in range(M.shape[0]):
        row = M[r]
        for (pr, pw, pb) in piv:
            if (row[pw] >> np.uint64(pb)) & np.uint64(1):
                row ^= M[pr]
        nz = np.flatnonzero(row)
        if nz.size == 0:
            continue
        w = nz[0]; b = int(row[w]).bit_length() - 1
        piv.append((r, w, b))
    for (pr, pw, pb) in piv:
        if (v[pw] >> np.uint64(pb)) & np.uint64(1):
            v ^= M[pr]
    return not v.any()


nq = km.Circuit.from_file(str(D / f'angle_k_{K}.kmb'), format='kmb').num_qubits
nq = max(nq, max(km.Circuit.from_file(str(D / f'angle_k_{k}.kmb'), format='kmb').num_qubits for k in range(K + 1)))
Q = fresh(nq)
for k in range(K):
    run(Q, ops(k))
Qk = Q.copy()
run(Qk, ops(K))                      # words now hold batch K (temporaries are reset by the circuit)
Q[:, NV:] = Qk[:, :NV]               # reverse-traversal entry state for lanes NV..2NV-1
hits, scanned = run(Q, ops(K), scan=True)
print(f'ANGLE_{K}: scanned {scanned} CCX; replaceable by CNOT/X on all {NV} addresses x (forward, reverse) entry states: {len(hits)}')
for idx, qs in hits[:40]:
    print('  op', idx, 'CCX', qs)
