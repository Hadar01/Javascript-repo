"""Aggregate paired census: per circuit failures, shot weights, and per-failure details."""
import glob, re, numpy as np, collections, json, sys
res = collections.defaultdict(lambda: dict(n=0, v=0, p=0, fails=[]))
for log in sorted(glob.glob('bigfail/*_*.log')):
    tag, chunk = re.match(r'bigfail/(v\d+)_(\d+)\.log', log).groups()
    s = open(log).read().split()
    if not s: continue
    r = res[tag]; r['n'] += int(s[1]); r['v'] += int(s[5]); r['p'] += int(s[7])
    for line in open(f'bigfail/{tag}_{chunk}_fails.txt'):
        sh, kind = line.split(); e = np.load(f'bigfail/err_{chunk}.npz')
        w = int(e['weight'][int(sh)]); pos = e['pos'][int(sh)][:w]; val = e['val'][int(sh)][:w]
        r['fails'].append(dict(chunk=int(chunk), shot=int(sh), kind=kind, weight=w, pos=sorted(int(x) for x in pos)))
for tag, r in res.items():
    print(tag, 'shots', r['n'], 'value', r['v'], 'phase', r['p'])
    for f in r['fails']: print('   ', f['chunk'], f['shot'], f['kind'], 'w=%d' % f['weight'], f['pos'][:8], '...')
json.dump({k: v for k, v in res.items()}, open('bigfail_summary.json', 'w'), indent=0)
