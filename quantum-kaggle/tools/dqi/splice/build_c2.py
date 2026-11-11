"""Reproducible build of DQI candidate C2 = C1 with the extract and unextract blocks of the public live file cd71c482.
Host: C1 (sha256 ca59beb8...), built by build_c1.sh from v100 + generator 7bd10fca.
Donor: dqi.kmb (sha256 cd71c482...) from Kaggle dataset heliosli/qcc-circuits-live version 95 (dqi.kmb.xz,
  updated 2026-11-11T10:36:05Z), credited there to team "i want to run gemma 9b" (dataset
  iwanttorungemma9b/vqcc-team-experiments-condensed, Apache-2.0), as shipped in sheroleg's notebook
  quantum-circuits-from-zero-1-sqrt-x-explained (version 6), on the Heliosli / syed3000 / SomeJoint / jday96314 line.
The two donor blocks replace the host's blocks between the same INFO_TAGs; boundary states are bit-identical (checked
separately), the pair's classical bits are renumbered to fresh ids. usage: build_c2.py host.kmb donor.kmb out.kmb report.json"""
import sys, json, numpy as np
sys.path[:0] = ['.', '..']
from kmb import read_kmb
from kmbw import Cols, sha
H_PATH, D_PATH, OUT, REP = sys.argv[1:5]
EXPECT = dict(host='ca59beb811b604c4c18114597745d96fa4ca62dafb131db7c274a558aa5ffb83',
              donor='cd71c4822aa090ad859a826acd0d289e699f631d4c55f6337036cccce90fa671')
assert sha(H_PATH) == EXPECT['host'] and sha(D_PATH) == EXPECT['donor'], 'input hash mismatch'
H = read_kmb(H_PATH); D = read_kmb(D_PATH)
def tags(d):
    pos = np.flatnonzero(d['op'] == 6)
    return {t: int(p) for t, p in zip(d['tags'], pos) if t in ('@enter:extract', '@exit:extract', '@enter:unextract', '@exit:unextract')}
th, td = tags(H), tags(D)
# prefixes before extract must be identical (op types and operands) so the donor blocks see the same state
pe = th['@enter:extract']; assert pe == td['@enter:extract']
assert np.array_equal(H['op'][:pe], D['op'][:pe])
nqh = (H['op'][:pe] >> 4) & 3
for key, cat in (('qq0', 2), ('qq1', 2), ('q0', 1)):
    k = int(np.count_nonzero(nqh == cat)); assert np.array_equal(H[key][:k], D[key][:k]), key
assert all(np.array_equal(H['regs'][k], D['regs'][k]) for k in H['regs'])
# donor bits used in its two blocks -> fresh ids (shared map: tokens flow from extract to unextract)
op = D['op']
def block_bits(a, b):
    sel = op[a:b + 1]
    def cnt(f, upto): return int(np.count_nonzero(f(op[:upto])))
    hb = lambda x: (x & 0x40) != 0; hc = lambda x: (x & 0x80) != 0
    b0 = D['b0'][cnt(hb, a):cnt(hb, b + 1)]; bc = D['bc'][cnt(hc, a):cnt(hc, b + 1)]
    return set(b0.tolist()) | set(bc.tolist()), set(b0.tolist())
b1, w1 = block_bits(td['@enter:extract'], td['@exit:extract']); b2, w2 = block_bits(td['@enter:unextract'], td['@exit:unextract'])
E = set(int(x) & 0x7fffffff for j in range(4095) for x in D['regs'][f'E{j}'])
assert not ((w1 | w2) & E), 'donor blocks write E bits'
used = sorted((b1 | b2) - E)
bitmap = np.arange(max(D['num_bits'], max(used) + 1), dtype=np.uint32)
nxt = H['num_bits']
for bt in used: bitmap[bt] = nxt; nxt += 1
out = Cols()
out.append_slice(H, 0, th['@enter:extract'])
out.append_slice(D, td['@enter:extract'], td['@exit:extract'] + 1, bitmap)
out.append_slice(H, th['@exit:extract'] + 1, th['@enter:unextract'])
out.append_slice(D, td['@enter:unextract'], td['@exit:unextract'] + 1, bitmap)
out.append_slice(H, th['@exit:unextract'] + 1, len(H['op']))
nb = out.write(OUT, H['regs'], 892)
rep = dict(inputs=EXPECT, host_blocks=[th['@enter:extract'], th['@exit:extract'], th['@enter:unextract'], th['@exit:unextract']],
           donor_blocks=[td['@enter:extract'], td['@exit:extract'], td['@enter:unextract'], td['@exit:unextract']],
           remapped_bits=len(used), num_bits=nb, output_sha256=sha(OUT),
           donor_provenance='Kaggle dataset heliosli/qcc-circuits-live v95 (dqi.kmb.xz, 2026-11-11T10:36:05Z), manifest portfolio v112hq_hw25_ay3; credited to team "i want to run gemma 9b" (iwanttorungemma9b/vqcc-team-experiments-condensed, Apache-2.0) via sheroleg/quantum-circuits-from-zero-1-sqrt-x-explained v6',
           credits='Extract/unextract: team "i want to run gemma 9b" rewrites on the Heliosli/syed3000/SomeJoint/jday96314 line (Apache-2.0). Conversion block: atakanaldemir/qcc-c44-five-helper-release-sources v1 (Apache-2.0; SomeJoint, Atakan Aldemir and lineage). Rest: public v100 lineage.')
json.dump(rep, open(REP, 'w'), indent=1); print(json.dumps(rep, indent=1))
