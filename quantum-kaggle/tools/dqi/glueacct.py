"""Split a stage's non-chain Toffolis into: main-chain region (before first 24-bit chain step), per-node glue regions
(between successive 24-bit chain runs), tail. Chain steps = 24-swap + T(99 or 180-190); 12-bit steps = 12/13-swap + T42/T84."""
import re, sys
f = sys.argv[1]
seq = []
for t in open(f).read().split():
    m = re.match(r'^([A-Z]+)(\d+)@(\d+)$', t)
    if m: seq.append((m.group(1), int(m.group(2)), int(m.group(3))))
n = len(seq); step = [None] * n
for i in range(n - 1):
    if seq[i][0] == 'SW' and seq[i+1][0] == 'T':
        v, t = seq[i][1], seq[i+1][1]
        if v >= 24 and (t == 99 or 180 <= t <= 190): step[i] = step[i+1] = 's24'
        elif 12 <= v <= 13 and t in (42, 84): step[i] = step[i+1] = 's12'
# regions: maximal runs of s24 steps (allowing up to 3 non-step events inside a run)
runs = []; i = 0
while i < n:
    if step[i] == 's24':
        j = i; last = i
        while j < n and (step[j] == 's24' or (j - last) <= 3):
            if step[j] == 's24': last = j
            j += 1
        runs.append((i, last)); i = last + 1
    else: i += 1
def acct(a, b):
    T = Z = C = s12 = 0
    for k in range(a, b):
        nme, v, p = seq[k]
        if step[k] is None:
            if nme == 'T': T += v
            elif nme == 'Z': Z += v
            elif nme == 'CS': C += v
        elif step[k] == 's12' and nme == 'T': s12 += v
    return T, Z, C, s12
print(f, 'chain runs:', len(runs))
prev = 0
for r, (a, b) in enumerate(runs):
    T, Z, C, s12 = acct(prev, a)
    chainT = sum(seq[k][1] for k in range(a, b + 1) if step[k] == 's24' and seq[k][0] == 'T')
    print(f"  gap before run {r:2d}: glueT={T:6d} CCZ={Z:5d} CSWAP={C:5d} 12bit-steps T={s12:5d} | run: chainT={chainT:6d} ops[{seq[a][2]},{seq[b][2]}]")
    prev = b + 1
T, Z, C, s12 = acct(prev, n); print(f"  tail: glueT={T} CCZ={Z} CSWAP={C} 12bit={s12}")
