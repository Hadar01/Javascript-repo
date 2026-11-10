import re, sys
for f in sys.argv[1:]:
    toks = open(f).read().split(); out = []
    for t in toks:
        m = re.match(r'^([A-Z]+)(\d+)@(\d+)$', t)
        if not m: continue
        name, val = m.group(1), int(m.group(2))
        if name == 'SW' and val >= 24: out.append('S')
        elif name == 'T' and val >= 80: out.append(f'T{val}')
        elif name == 'H' and val >= 24: out.append(f'H{val}')
    s = ' '.join(out)
    # compress "S T1xx" patterns
    s = re.sub(r'S T(18\d)', r'c', s)   # chain step with corrected product (~182-189)
    s = re.sub(r'S T(99)', r'k', s)     # scalar step (one mul24)
    s = re.sub(r'(c ?){2,}', lambda m: f"c*{m.group(0).count('c')} ", s)
    s = re.sub(r'(k ?){2,}', lambda m: f"k*{m.group(0).count('k')} ", s)
    print(f, ':', s[:5000]); print()
