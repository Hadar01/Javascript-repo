"""Row-hash overlap matrix between two dump sets; for each state of A print the best-overlapping state of B.
usage: rhmatch.py A.npz A_static.npz B.npz B_static.npz [step]"""
import sys, numpy as np
def load(p):
    z = np.load(p); o = z['offs']; return z['pos'], [z['h'][o[i]:o[i+1]] for i in range(len(o) - 1)]
pa, ha = load(sys.argv[1]); cta = np.load(sys.argv[2])['ctof']
pb, hb = load(sys.argv[3]); ctb = np.load(sys.argv[4])['ctof']
step = int(sys.argv[5]) if len(sys.argv) > 5 else 1
ia = np.argsort(pa); ib = np.argsort(pb)
M = np.zeros((len(pa), len(pb)), np.int32)
for x, i in enumerate(ia):
    for y, j in enumerate(ib):
        M[x, y] = len(np.intersect1d(ha[i], hb[j], assume_unique=True))
np.save(sys.argv[1].replace('.npz', '') + '_vs_' + sys.argv[3].split('/')[-1].replace('.npz', '') + '.npy', M)
for x in range(0, len(ia), step):
    i = ia[x]; y = int(M[x].argmax()); j = ib[y]
    print(f"A T{int(cta[pa[i]])//1000:4d}k n{len(ha[i]):4d} | best B T{int(ctb[pb[j]])//1000:4d}k n{len(hb[j]):4d} shared {M[x, y]:4d}")
