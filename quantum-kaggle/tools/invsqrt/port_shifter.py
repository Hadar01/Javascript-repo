"""Can gengsr's 46-CSWAP forward shifter be ported to the un-normalisation network? (Agent A)

Exact analysis over all x on a kmx file:
  * forward network F: CSWAPs in [f_lo, f_hi) (op indices), each with its control as a function of lz;
  * end network E: CSWAPs in [e_lo, e_hi);
  * layout P: which qubit holds x_n bit j at the start of E;  layout Q: which qubit holds x bit i after E;
  * available control functions at E's start: qubits whose value is a function of lz alone;
  * for the inverse of F, run in the virtual layout P: the care set of every CSWAP (lz values where its two
    positions can differ), and whether its control restricted to the care set is an XOR of available functions.
usage: python port_shifter.py circuit.kmx f_lo f_hi e_lo e_hi"""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from winsynth import record_states

MAXX = 3133452


def main(path, f_lo, f_hi, e_lo, e_hi):
    ops = load(path)
    fsw = [k for k in range(f_lo, f_hi) if ops[k][0] == 'CSWAP']
    esw = [k for k in range(e_lo, e_hi) if ops[k][0] == 'CSWAP']
    xs = np.arange(1, MAXX + 1, dtype=np.uint64)
    at = set(fsw) | {e_lo, e_hi, fsw[-1] + 1}
    V, n = record_states(ops, xs, 1, at)
    unp = lambda v: np.unpackbits(v.view(np.uint8), bitorder='little')[:n]
    lz = (21 - np.floor(np.log2(xs.astype(np.float64)))).astype(np.int64)
    xn = (xs.astype(np.int64) << lz)
    def lzfunc(vec):
        f = np.zeros(22, np.int64) - 1
        for L in range(22):
            s = set(vec[lz == L].tolist())
            if len(s) > 1: return None
            f[L] = s.pop()
        return f
    # forward controls
    fctl = []
    for k in fsw:
        c = lzfunc(unp(V[k][int(ops[k][1][0][1:])]))
        assert c is not None
        fctl.append((k, ops[k][1][1], ops[k][1][2], c))
    # state after the forward network: which qubit holds x_n bit j?
    Sf = V[fsw[-1] + 1]
    nq = Sf.shape[0]
    def locate(S, target):
        for qq in range(nq):
            if np.array_equal(unp(S[qq]), target): return qq
        return None
    fpos = {j: locate(Sf, ((xn >> j) & 1).astype(np.uint8)) for j in range(22)}
    print('after forward network, x_n bit j at qubit:', fpos)
    S0 = V[e_lo]; S1 = V[e_hi]
    P = {j: locate(S0, ((xn >> j) & 1).astype(np.uint8)) for j in range(22)}
    Q = {i: locate(S1, ((xs.astype(np.int64) >> i) & 1).astype(np.uint8)) for i in range(22)}
    print('end-network start, x_n bit j at qubit P:', P)
    print('end-network end,   x bit i at qubit Q:', Q)
    avail = {}
    for qq in range(nq):
        f = lzfunc(unp(S0[qq]))
        if f is not None and f.any() and not f.all(): avail[qq] = f
    print('available lz-functions at end start:', {q: ''.join(map(str, f)) for q, f in avail.items()})
    # the end network's own controls
    for k in esw:
        pass
    return fctl, fpos, P, Q, avail, ops, V, unp, lz, xn, esw


if __name__ == '__main__':
    a = sys.argv
    main(a[1], int(a[2]), int(a[3]), int(a[4]), int(a[5]))
