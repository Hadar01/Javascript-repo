"""Per state dump: set of 64-bit hashes of each nonzero qubit row (complement-normalised so that x and NOT x match).
Writes <out>.npz with positions and a ragged hash list. usage: rowhash.py out.npz state_files..."""
import sys, numpy as np
out = sys.argv[1]; files = sys.argv[2:]
pos, hs, offs = [], [], [0]
mult = np.random.default_rng(12345).integers(1, 2**63 - 1, size=64, dtype=np.uint64) | np.uint64(1)
for f in files:
    d = np.fromfile(f, dtype=np.uint64).reshape(-1, 64)
    neg = (d[:, 0] & np.uint64(1)).astype(bool); d = d.copy(); d[neg] = ~d[neg]      # normalise: shot 0 bit = 0
    nz = d.any(axis=1)
    with np.errstate(over='ignore'):
        h = (d[nz] * mult).sum(axis=1, dtype=np.uint64) ^ (d[nz] >> np.uint64(17)).sum(axis=1, dtype=np.uint64)
    h = np.unique(h); hs.append(h); offs.append(offs[-1] + len(h)); pos.append(int(f.split('_')[-1][:-4]))
np.savez(out, pos=np.array(pos), offs=np.array(offs), h=np.concatenate(hs))
print(out, len(files))
