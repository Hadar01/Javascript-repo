"""Per-stage mean T / peak / 892-entries table across profiled circuits (out/<tag>_d4096 + <tag>_seg.json)."""
import csv, json, collections, sys
tags = sys.argv[1:]
order = ['extract', 'synthesis', 'convert', 'scan', 'unconvert', 'unsynthesis', 'padded_unsynthesis', 'unextract']
def load(tag):
    seg = json.load(open(f'{tag}_seg.json'))
    rows = list(csv.DictReader(open(f'out/{tag}_d4096_seg.tsv'), delimiter='\t'))
    H = list(csv.DictReader(open(f'out/{tag}_d4096_hist.tsv'), delimiter='\t'))
    st = collections.defaultdict(lambda: dict(mean=0.0, peak=0, e892=0))
    for r in rows:
        if float(r['ops']) == 0: continue
        s = seg[int(r['seg'])].split('/')[0]
        st[s]['mean'] += float(r['mean_tof']); st[s]['peak'] = max(st[s]['peak'], int(r['peak_live']))
    for h in H:
        if int(h['level']) == 892: st[seg[int(h['seg'])].split('/')[0]]['e892'] += int(h['entries_to_level'])
    return st
D = {t: load(t) for t in tags}
print('stage'.ljust(20) + ''.join(t.rjust(24) for t in tags))
for s in order:
    if not any(s in D[t] for t in tags): continue
    print(s.ljust(20) + ''.join((f"{D[t][s]['mean']:10.1f} {D[t][s]['peak']:3d}/{D[t][s]['e892']:<4d}" if s in D[t] else '-').rjust(24) for t in tags))
print('TOTAL'.ljust(20) + ''.join(f"{sum(v['mean'] for v in D[t].values()):10.1f}".rjust(24) for t in tags))
