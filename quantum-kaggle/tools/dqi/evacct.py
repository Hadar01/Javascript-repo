"""Accounting of Toffolis in a stage event file: chain steps (24-bit swap followed by T run), 12-bit chain steps (12/13-swap + T84/T42), rest."""
import re, sys, collections
for f in sys.argv[1:]:
    toks = [re.match(r'^([A-Z]+)(\d+)@(\d+)$', t) for t in open(f).read().split()]
    toks = [(m.group(1), int(m.group(2))) for m in toks if m]
    acc = collections.Counter(); cnt = collections.Counter()
    i = 0
    while i < len(toks):
        n, v = toks[i]
        if n == 'SW' and v >= 24 and i + 1 < len(toks) and toks[i+1][0] == 'T':
            t = toks[i+1][1]
            kind = 'step24_full(180-190)' if 180 <= t <= 190 else ('step24_scalar(99)' if t == 99 else 'after24swap_other')
            acc[kind] += t; cnt[kind] += 1; i += 2; continue
        if n == 'SW' and 12 <= v <= 13 and i + 1 < len(toks) and toks[i+1][0] == 'T' and toks[i+1][1] in (42, 84):
            t = toks[i+1][1]; kind = f'step12_T{t}'; acc[kind] += t; cnt[kind] += 1; i += 2; continue
        if n in ('T', 'Z', 'CS'): acc['other_' + n] += v
        i += 1
    tot = sum(acc.values())
    print(f, 'total', tot)
    for k, v in sorted(acc.items(), key=lambda x: -x[1]): print(f'   {k:24s} {v:7d}  ({cnt.get(k, 0)} steps)')
