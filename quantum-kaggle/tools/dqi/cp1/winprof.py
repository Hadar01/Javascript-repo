"""Static per-window profile of an (untagged) kmb: static T, conditioned T, HMR, ops whose condition bit is a mask
bit E*, CZ count, op count. Writes <out>.npz with per-op cumulative arrays for later boundary work.
usage: winprof.py kmb out_prefix [window_ops]"""
import sys, numpy as np
sys.path.insert(0, sys.path[0])
from kmb import read_kmb
d = read_kmb(sys.argv[1]); out = sys.argv[2]; WIN = int(sys.argv[3]) if len(sys.argv) > 3 else 100000
op = d['op']; n = len(op)
regs = d['regs']
ebits = np.zeros(d['num_bits'] + 1, bool)
for name, ids in regs.items():
    if name.startswith('E') and name[1:].isdigit():
        b = ids[(ids & 0x80000000) == 0]; ebits[b] = True
hasc = ((op & 0x80) != 0) & (op != 0x81)
ispush = op == 0x81
usesbc = hasc | ispush
bcidx = np.cumsum(usesbc) - 1
cbit = np.full(n, -1, np.int64); cbit[usesbc] = d['bc'][bcidx[usesbc]]
cond_on_E = np.zeros(n, bool); cond_on_E[usesbc] = ebits[cbit[usesbc]]
bt = op & 0x7f; nqt = (op >> 4) & 3
tof = (nqt == 3) & ((op & 0x40) == 0) & (bt != 0x06) & (bt != 0x07)
hmr = (op & 0x7f) == 0x50
cz = (bt == 0x20)
dep = np.cumsum(ispush.astype(np.int32) - (op == 0x01).astype(np.int32))
condtof = tof & ((dep > 0) | hasc)
np.savez_compressed(out + '_static.npz', ctof=np.cumsum(tof).astype(np.int32), ccond=np.cumsum(condtof).astype(np.int32),
                    chmr=np.cumsum(hmr).astype(np.int32), cE=np.cumsum(cond_on_E | (ispush & cond_on_E)).astype(np.int32))
print('ops', n, 'static T', int(tof.sum()), 'cond T', int(condtof.sum()), 'HMR', int(hmr.sum()), 'E-cond ops', int(cond_on_E.sum()),
      'push', int(ispush.sum()), 'nbits', d['num_bits'], 'nq', d['num_qubits'], 'Ebits', int(ebits.sum()))
with open(out + '_win.tsv', 'w') as f:
    f.write('start\tend\tT\tcondT\tHMR\tEcond\tCZ\tcumT\n')
    for a in range(0, n, WIN):
        b = min(n, a + WIN)
        f.write(f"{a}\t{b}\t{int(tof[a:b].sum())}\t{int(condtof[a:b].sum())}\t{int(hmr[a:b].sum())}\t{int(cond_on_E[a:b].sum())}\t{int(cz[a:b].sum())}\t{int(tof[:b].sum())}\n")
