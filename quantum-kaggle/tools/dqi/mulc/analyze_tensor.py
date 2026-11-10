"""Analyse the kernel tensor: extract the 99 rank-one terms from the op stream (linear forms at CCX time),
verify they reproduce T exactly over all 24x24 basis pairs, check field axioms, find modulus, check tower grouping."""
import json, random, itertools
k = json.load(open('kernel0.json')); ops = [tuple(o) for o in k['ops']]
t = json.load(open('tensor0.json')); X, Y, Z, T = t['X'], t['Y'], t['Z'], t['T']
xi = {q: i for i, q in enumerate(X)}; yi = {q: i for i, q in enumerate(Y)}; zi = {q: i for i, q in enumerate(Z)}
# track linear forms: each x/y qubit holds a 24-bit mask over its register's inputs; each z qubit holds an
# "output responsibility": we track, for z, the linear map from 'injected' AND values to final outputs by
# simulating forward with z as linear functions of AND-term variables.
lx = {q: 1 << i for i, q in enumerate(X)}; ly = {q: 1 << i for i, q in enumerate(Y)}
lz = {q: 0 for q in Z}  # each z qubit value = XOR of AND-terms (bitmask over term index)
terms = []
for o in ops:
    if o[0] == 'CX':
        a, b = o[1], o[2]
        if a in lx and b in lx: lx[b] ^= lx[a]
        elif a in ly and b in ly: ly[b] ^= ly[a]
        elif a in lz and b in lz: lz[b] ^= lz[a]
        else: raise SystemExit('cross-register CX')
    else:
        a, b, c = o[1:]
        ma = lx[a] if a in lx else ly[a]; mb = ly[b] if b in ly else lx[b]
        r = len(terms); terms.append([ma, mb]); lz[c] ^= 1 << r
assert all(lx[q] == 1 << i for i, q in enumerate(X)) and all(ly[q] == 1 << i for i, q in enumerate(Y))
# output vector of term r: which final z bits contain it
for r in range(len(terms)):
    terms[r].append(sum(((lz[q] >> r) & 1) << i for i, q in enumerate(Z)))
print('terms', len(terms), 'symmetric (same mask on x and y):', sum(a == b for a, b, c in terms))
# exact verification over all basis pairs
def B(xm, ym):
    out = 0
    for a, b, c in terms:
        if bin(a & xm).count('1') & 1 and bin(b & ym).count('1') & 1: out ^= c
    return out
ok = all(B(1 << i, 1 << j) == sum(T[kk][i][j] << kk for kk in range(24)) for i in range(24) for j in range(24))
print('rank-99 formula reproduces kernel tensor on all 576 basis pairs:', ok)
def mul(x, y):  # bilinear extension
    out = 0
    for i in range(24):
        if x >> i & 1:
            for j in range(24):
                if y >> j & 1: out ^= TB[i][j]
    return out
TB = [[sum(T[kk][i][j] << kk for kk in range(24)) for j in range(24)] for i in range(24)]
rnd = random.Random(1)
assoc = all(mul(mul(a, b), c) == mul(a, mul(b, c)) for a, b, c in [(rnd.getrandbits(24), rnd.getrandbits(24), rnd.getrandbits(24)) for _ in range(300)])
print('associative on 300 random triples:', assoc)
# unit: solve u with mul(u, e_j) = e_j for all j  (linear system over GF(2))
import numpy as np
rows = []; rhs = []
for j in range(24):
    for kk in range(24):
        rows.append([T[kk][i][j] for i in range(24)]); rhs.append(1 if kk == j else 0)
A = np.array(rows, dtype=np.uint8); bvec = np.array(rhs, dtype=np.uint8)
# gaussian elimination
M = np.concatenate([A, bvec[:, None]], 1); r = 0; piv = []
for c in range(24):
    p = next((i for i in range(r, len(M)) if M[i, c]), None)
    if p is None: continue
    M[[r, p]] = M[[p, r]]
    for i in range(len(M)):
        if i != r and M[i, c]: M[i] ^= M[r]
    piv.append(c); r += 1
consistent = not any(M[i, :24].sum() == 0 and M[i, 24] for i in range(len(M)))
u = 0
for i, c in enumerate(piv): u |= int(M[i, 24]) << c
print('unit element exists:', consistent, 'unit =', hex(u))
# no zero divisors on random samples + order of a random element divides 2^24-1
def power(a, e):
    r_ = u; b_ = a
    while e:
        if e & 1: r_ = mul(r_, b_)
        b_ = mul(b_, b_); e >>= 1
    return r_
g = rnd.getrandbits(24)
print('random element g: g^(2^24-1)==1:', power(g, 2**24 - 1) == u)
# minimal polynomial of x = basis element e1 (bit 1): find linear dependency among powers u, x, x^2, ... x^24
x = 1 << 1; pw = [u]
for _ in range(24): pw.append(mul(pw[-1], x))
# solve sum c_i pw_i = 0 with c_24 = 1
Mat = np.array([[(pw[i] >> b) & 1 for i in range(24)] for b in range(24)], dtype=np.uint8); rhs = np.array([(pw[24] >> b) & 1 for b in range(24)], dtype=np.uint8)
M = np.concatenate([Mat, rhs[:, None]], 1); r = 0; piv = []
for c in range(24):
    p = next((i for i in range(r, 24) if M[i, c]), None)
    if p is None: continue
    M[[r, p]] = M[[p, r]]
    for i in range(24):
        if i != r and M[i, c]: M[i] ^= M[r]
    piv.append(c); r += 1
print('powers of e1 independent (e1 generates GF(2^24)):', r == 24)
if r == 24:
    coef = [0] * 24
    for i, c in enumerate(piv): coef[c] = int(M[i, 24])
    print('minimal polynomial of e1: x^24 + ' + ' + '.join(f'x^{i}' for i in reversed(range(24)) if coef[i]))
# tower check: do terms group into 11 consecutive blocks of 9 whose masks span 4 dims?
def rank(vs):
    vs = list(vs); rk = 0
    for bit in range(24):
        p = next((v for v in vs if v >> bit & 1), None)
        if p is None: continue
        vs = [v ^ p if v >> bit & 1 else v for v in vs if v != p]; rk += 1
    return rk
blocks = [rank(a for a, b, c in terms[9*i:9*i+9]) for i in range(11)]
print('span dimension of each consecutive block of 9 masks:', blocks)
outs = [rank(c for a, b, c in terms[9*i:9*i+9]) for i in range(11)]
print('span dimension of each block of 9 output vectors:', outs)
json.dump(dict(terms=terms, unit=u), open('terms99.json', 'w'))
