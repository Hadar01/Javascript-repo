def normalize(b, x, f):
    """v3 step 1: f4, f3, f2 (the binary leading-zero count div 4) from one prefix-AND chain on the unshifted x.
    chain[m] = [x[W-m-2:W] == 0] (top m+2 bits zero); p_j = chain[4j-2] = [lz >= 4j].  f4 = p4, f3 = p2 ^ p4,
    f2 = p1 ^ p2 ^ p3 ^ p4 ^ p5 (nested prefixes, so XOR = bit 2 of lz).  19 ANDs instead of 15 + 7 + 3."""
    bits = [x[W - 1 - m] for m in range(20)]                  # x21, x20, ..., x2
    b.x(km.array(bits))
    chain = b.alloc_qubits(19)
    b.init_and(bits[0], bits[1], chain[0])
    for m in range(1, 19): b.init_and(chain[m - 1], bits[m + 1], chain[m])
    p = {j: chain[4 * j - 2] for j in range(1, 6)}
    b.cx(p[4], f[4])
    b.cx(p[2], f[3]); b.cx(p[4], f[3])
    for j in range(1, 6): b.cx(p[j], f[2])
    for m in reversed(range(1, 19)): b.del_and(chain[m - 1], bits[m + 1], chain[m])
    b.del_and(bits[0], bits[1], chain[0])
    b.free(chain)
    b.x(km.array(bits))
    for (k, d) in NSTAGES:
        top = x[W - d:W]
        if d == 1:
            b.cx(x[W - 1], f[0]); b.x(f[0])
        elif d == 2:
            b.x(top); b.ccx(top[0], top[1], f[1]); b.x(top)
        for i in reversed(range(0, W - d)): b.cswap(f[k], x[i], x[i + d])

def shift_stages(b, f, reg, L, inverse):
    stages = [(1, 1), (2, 2), (3, 4), (4, 8)]
    occ = []; o = L
    for (k, d) in stages: occ.append(o); o = min(o + d, len(reg))
    seq = list(enumerate(stages))
    if not inverse:
        for idx, (k, d) in seq:
            for i in reversed(range(0, occ[idx])):
                if i + d >= len(reg): continue
                if i + d >= occ[idx]:                       # v2: target is |0> for every f
                    b.init_and(f[k], reg[i], reg[i + d]); b.cx(reg[i + d], reg[i])
                else:
                    b.cswap(f[k], reg[i], reg[i + d])
    else:
        for idx, (k, d) in reversed(seq):
            for i in range(0, occ[idx]):
                if i + d >= len(reg): continue
                if i + d >= occ[idx]:
                    b.cx(reg[i + d], reg[i]); b.del_and(f[k], reg[i], reg[i + d])
                else:
                    b.cswap(f[k], reg[i], reg[i + d])