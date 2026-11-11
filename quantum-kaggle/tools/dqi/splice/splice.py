"""Transform: v100 DQI binary with its [convert .. unconvert] block replaced by the generator's (7bd10fca) block,
bridged by an exact affine CNOT/X map (fitted on simulated boundary states, validated on held-out shots).
usage: splice.py v100.kmb gen7bd.kmb state_v_fit state_g_fit state_v_val state_g_val out.kmb report.json"""
import sys, json, numpy as np
sys.path[:0] = ['.', '..']
from kmb import read_kmb
from kmbw import Cols, sha
from gf2 import solve_affine, rank, cnot_synthesis
V_PATH, G_PATH, SVF, SGF, SVV, SGV, OUT, REP = sys.argv[1:9]
EXPECT = {'v100': 'e9f54be304cbdcda7306729c335b1a2314a45d0ca818e05cf60e45ddee969bc4',
          'gen': '7bd10fcab4f2dd653aabfa475cd67b0d7b8ca6bd1aec7149b7905c2b0390dd0f'}
assert sha(V_PATH) == EXPECT['v100'] and sha(G_PATH) == EXPECT['gen'], 'input hash mismatch'
V = read_kmb(V_PATH); G = read_kmb(G_PATH); NQ = 892; W = None
def tagpos(d, name):
    op = d['op']; pos = np.flatnonzero(op == 6)
    return [int(p) for t, p in zip(d['tags'], pos) if t == name]
v1 = tagpos(V, '@enter:convert')[0]; v2 = tagpos(V, '@exit:unconvert')[0]
g1 = tagpos(G, '@enter:convert')[0]; g2 = tagpos(G, '@exit:unconvert')[0]
def load(p):
    raw = np.fromfile(p, dtype=np.uint64); w = raw.size // NQ
    return np.unpackbits(raw.reshape(NQ, w).view(np.uint8), axis=1, bitorder='little')
Sv, Sg = load(SVF), load(SGF)
liveV = [q for q in range(NQ) if Sv[q].any()]; liveG = [q for q in range(NQ) if Sg[q].any()]
# qubits in G's live set NOT affine in V's state (carried flags) are excluded: the block must not touch them.
A, c, r, ok = solve_affine(Sv[liveV], Sg[liveG])
pred = (A.astype(np.int64) @ Sv[liveV].astype(np.int64) + c[:, None]) % 2
badG = [liveG[i] for i in range(len(liveG)) if not np.array_equal(pred[i], Sg[liveG[i]])]
targets = [q for q in liveG if q not in badG]
A, c, r, ok = solve_affine(Sv[liveV], Sg[targets])
assert ok, 'affine fit failed on targets'
# block must not touch excluded qubits
op = G['op']; nq = (op >> 4) & 3; i3 = np.cumsum(nq == 3) - (nq == 3); i2 = np.cumsum(nq == 2) - (nq == 2); i1 = np.cumsum(nq == 1) - (nq == 1)
touched = set()
blk = np.arange(g1, g2 + 1)
for k3 in (G['qqq0'], G['qqq1'], G['qqq2']): touched |= set(k3[i3[blk[nq[blk] == 3]]].tolist())
for k2 in (G['qq0'], G['qq1']): touched |= set(k2[i2[blk[nq[blk] == 2]]].tolist())
touched |= set(G['q0'][i1[blk[nq[blk] == 1]]].tolist())
assert not (touched & set(badG)), ('block touches excluded qubits', sorted(touched & set(badG)))
# square, invertible map on full register space
assert len(liveV) == len(targets), (len(liveV), len(targets))
Asq = A
assert rank(Asq) == len(targets), 'affine map not invertible'
M = np.zeros((NQ, NQ), np.uint8)
for jj, j in enumerate(targets):
    for ii, i in enumerate(liveV): M[j, i] = Asq[jj, ii]
restV = [q for q in range(NQ) if q not in set(liveV)]; restG = [q for q in range(NQ) if q not in set(targets)]
for i, j in zip(restV, restG): M[j, i] = 1
assert rank(M) == NQ
fwd = cnot_synthesis(M)
xs = [targets[jj] for jj in range(len(targets)) if c[jj]]
bridge_in = [('TAG', '@enter:bridge_in')] + fwd + [('X', q) for q in xs] + [('TAG', '@exit:bridge_in')]
inv = [('CX', a, b) for (_, a, b) in reversed(fwd)]
bridge_out = [('TAG', '@enter:bridge_out')] + [('X', q) for q in xs] + inv + [('TAG', '@exit:bridge_out')]
# validation on held-out shots: predicted G state from V state
Vv, Gv = load(SVV), load(SGV)
Mi = M.astype(np.int64); predv = (Mi @ Vv.astype(np.int64)) % 2
for jj, j in enumerate(targets):
    if c[jj]: predv[j] ^= 1
val_mism = int(sum(not np.array_equal(predv[q], Gv[q]) for q in targets))
val_zero = int(sum(predv[q].any() for q in range(NQ) if q not in set(targets)))
assert val_mism == 0 and val_zero == 0, ('held-out validation failed', val_mism, val_zero)
# bit remap for block: keep E bits; fresh ids for every other bit id referenced in the block
hb = (op & 0x40) != 0; hc = (op & 0x80) != 0
ib = np.cumsum(hb) - hb; ic = np.cumsum(hc) - hc
bits_blk = set(G['b0'][ib[blk[hb[blk]]]].tolist()) | set(G['bc'][ic[blk[hc[blk]]]].tolist())
E = set(int(x) & 0x7fffffff for j in range(4095) for x in G['regs'][f'E{j}'])
written_E = set(G['b0'][ib[blk[hb[blk]]]].tolist()) & E
assert not written_E, 'block writes E bits'
bitmap = np.arange(max(G['num_bits'], max(bits_blk) + 1), dtype=np.uint32)
nxt = V['num_bits']
for bt in sorted(bits_blk - E): bitmap[bt] = nxt; nxt += 1
out = Cols()
out.append_slice(V, 0, v1)
out.append_gates(bridge_in)
out.append_slice(G, g1, g2 + 1, bitmap)
out.append_gates(bridge_out)
out.append_slice(V, v2 + 1, len(V['op']))
nb = out.write(OUT, V['regs'], NQ)
rep = dict(inputs=EXPECT, v100_block=[v1, v2], gen_block=[g1, g2], liveV=len(liveV), liveG=len(liveG), excluded_gen_qubits=badG,
           fit_rank=int(r), bridge_cnots=len(fwd), bridge_x=len(xs), heldout_shots=int(Vv.shape[1]), heldout_mismatch=val_mism,
           remapped_bits=len(bits_blk - E), num_bits=nb, output_sha256=sha(OUT),
           credits='Block from atakanaldemir/qcc-c44-five-helper-release-sources (Apache-2.0; SomeJoint, Atakan Aldemir and lineage); host v100 public DQI (lineage credited in heliosli/kirilltym notebooks).')
json.dump(rep, open(REP, 'w'), indent=1); print(json.dumps(rep, indent=1))
