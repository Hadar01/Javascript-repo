"""Splice-boundary phase check for DQI C2 = C1 middle + donor (cd71c482) extract/unextract.

Reads per-shot phase bits dumped by prof.cc (PHASE_OPS) after four ops per circuit:
  a = end of `initial`, e = end of `extract`, m = end of `unsynthesis`, x = end of `unextract`.
Block phases per shot: phiE = ph[e]^ph[a], phiM = ph[m]^ph[e], phiX = ph[x]^ph[m].

Checks (all on the same official-sampler inputs):
 1. measurement independence: each block's phase is identical under two independent coin seeds;
 2. identity sanity: C2's pair equals the donor's pair, and C2's middle equals C1's middle, shot by shot;
 3. phase debt: C1's pair phase (phiE^phiX) equals the donor's pair phase, and C1's middle equals the donor's middle.
    If 3 failed on a shot, C2 (C1 middle + donor pair) would differ from both correct parents on that shot.
usage: phase_boundary.py <dir> <nshots>
"""
import sys, numpy as np

D, N = sys.argv[1], int(sys.argv[2])
OPS = {'c1': (2643972, 6537393, 53377008, 59171801),
       'donor': (2643972, 7795815, 53400793, 60454575),
       'c2': (2643972, 7795815, 54635430, 61689212)}


def bits(path):
    w = np.fromfile(path, dtype='<u8')
    return np.unpackbits(w.view(np.uint8), bitorder='little')[:N].astype(np.uint8)


def blocks(name, seed):
    a, e, m, x = (bits(f'{D}/{name}_s{seed}_phase_{o}.bin') for o in OPS[name])
    return {'E': e ^ a, 'M': m ^ e, 'X': x ^ m, 'pair': (e ^ a) ^ (x ^ m)}


R = {(n, s): blocks(n, s) for n in OPS for s in (1, 2)}
ok = True


def report(label, u, v):
    global ok
    diff = int(np.count_nonzero(u != v))
    ok &= diff == 0
    print(f'{label:58s} differing shots: {diff} / {N}')


print('1. measurement-outcome independence (seed 1 vs seed 2); strict for middle and pair')
for n in OPS:
    for b in ('M', 'pair'):
        report(f'   {n} phi{b}', R[(n, 1)][b], R[(n, 2)][b])
    for b in ('E', 'X'):  # informational: a pair-internal fix-up legitimately makes these coin-dependent
        d = int(np.count_nonzero(R[(n, 1)][b] != R[(n, 2)][b]))
        print(f'   {n} phi{b} (informational){"":28s} differing shots: {d} / {N}')
print('2. identical blocks on identical states')
for s in (1, 2):
    report(f'   seed {s}: C2 pair vs donor pair', R[('c2', s)]['pair'], R[('donor', s)]['pair'])
    report(f'   seed {s}: C2 middle vs C1 middle', R[('c2', s)]['M'], R[('c1', s)]['M'])
print('3. phase debt across the boundary')
for s in (1, 2):
    report(f'   seed {s}: C1 pair vs donor pair', R[('c1', s)]['pair'], R[('donor', s)]['pair'])
    report(f'   seed {s}: C1 middle vs donor middle', R[('c1', s)]['M'], R[('donor', s)]['M'])
print('ALL CHECKS PASS' if ok else 'SOME CHECK FAILED')
