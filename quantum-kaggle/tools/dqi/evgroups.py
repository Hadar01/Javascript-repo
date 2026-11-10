"""Split a stage event file into per-node-group blocks (a block = maximal run containing 24-bit chain steps,
separated by H24 measurement events) and account chain vs glue Toffolis per block."""
import re, sys
for f in sys.argv[1:]:
    toks = [re.match(r'^([A-Z]+)(\d+)@(\d+)$', t) for t in open(f).read().split()]
    toks = [(m.group(1), int(m.group(2)), int(m.group(3))) for m in toks if m]
    # mark chain-step Toffolis
    chain = [False] * len(toks)
    for i in range(len(toks) - 1):
        if toks[i][0] == 'SW' and toks[i][1] >= 24 and toks[i+1][0] == 'T' and (toks[i+1][1] == 99 or 180 <= toks[i+1][1] <= 190):
            chain[i+1] = True
    # boundaries: positions of chain-step runs; group = from first chain step after a gap of >=1 glue region with an H24
    blocks = []; cur = None
    for i, (n, v, p) in enumerate(toks):
        if chain[i]:
            if cur is None or cur['closed']: cur = dict(start=p, chainT=0, full=0, scal=0, glueT=0, glueZ=0, glueCS=0, closed=False, nsteps=0); blocks.append(cur)
            cur['chainT'] += v; cur['nsteps'] += 1
            if v == 99: cur['scal'] += 1
            else: cur['full'] += 1
        elif cur is not None and not cur['closed']:
            if n == 'T': cur['glueT'] += v
            elif n == 'Z': cur['glueZ'] += v
            elif n == 'CS': cur['glueCS'] += v
            elif n == 'H' and v == 24 and cur['nsteps'] > 0:
                # close only if next chain run is a different group: heuristic, close at H24
                cur['closed'] = True
    print(f, len(blocks), 'blocks')
    for b in blocks: print(f"   @{b['start']:9d} steps full={b['full']:2d} scalar={b['scal']:2d} chainT={b['chainT']:6d} glueT={b['glueT']:5d} glueZ={b['glueZ']:4d} glueCS={b['glueCS']:4d}")
