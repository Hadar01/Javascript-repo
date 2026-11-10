"""Symbolic GF(2) simulation of a CX/CCX kernel. Values = sets of monomials; monomial = frozenset of var names.
Returns tensor T[k][i][j] for z_k += x_i*y_j and checks inputs restored, z linear part zero."""
import json, sys, itertools
def simulate(ops, X, Y, Z):
    val = {}
    for i, q in enumerate(X): val[q] = {frozenset([('x', i)])}
    for i, q in enumerate(Y): val[q] = {frozenset([('y', i)])}
    for i, q in enumerate(Z): val[q] = set()            # z starts at 0 (xor-into-zero view)
    for o in ops:
        if o[0] == 'CX':
            a, t = o[1], o[2]; val[t] = val[t] ^ val[a]
        else:
            a, b, t = o[1], o[2], o[3]
            prod = set()
            for m1 in val[a]:
                for m2 in val[b]:
                    m = m1 | m2
                    prod ^= {m}
            val[t] = val[t] ^ prod
    return val
if __name__ == '__main__':
    k = json.load(open('kernel0.json')); ops = [tuple(o) for o in k['ops']]
    X = list(range(48, 72)); Y = list(range(72, 96)); Z = sorted({o[3] for o in ops if o[0] == 'CCX'} | {q for o in ops if o[0]=='CX' for q in o[1:] if q >= 840})
    print('Z qubits', Z)
    val = simulate(ops, X, Y, Z)
    ok_x = all(val[q] == {frozenset([('x', i)])} for i, q in enumerate(X))
    ok_y = all(val[q] == {frozenset([('y', i)])} for i, q in enumerate(Y))
    print('x restored', ok_x, 'y restored', ok_y)
    T = [[[0] * 24 for _ in range(24)] for _ in range(24)]; bad = 0
    for kk, q in enumerate(Z):
        for m in val[q]:
            xs = [v for (r, v) in m if r == 'x']; ys = [v for (r, v) in m if r == 'y']
            if len(xs) == 1 and len(ys) == 1: T[kk][xs[0]][ys[0]] ^= 1
            else: bad += 1
    print('non-bilinear monomials in z:', bad)
    json.dump(dict(X=X, Y=Y, Z=Z, T=T), open('tensor0.json', 'w'))
    # symmetry check T[k][i][j]==T[k][j][i]
    print('symmetric:', all(T[k][i][j] == T[k][j][i] for k in range(24) for i in range(24) for j in range(24)))
