import json, csv, sys, collections
pre = sys.argv[1]; names = json.load(open(sys.argv[2]))
rows = list(csv.DictReader(open(pre + '_seg.tsv'), delimiter='\t'))
H = list(csv.DictReader(open(pre + '_hist.tsv'), delimiter='\t'))
top = lambda s: names[int(s)].split('/')[0] or '(none)'
st = collections.OrderedDict()
for r in rows:
    if float(r['ops']) == 0: continue
    a = st.setdefault(top(r['seg']), dict(static=0, mean=0, hmr=0, peak=0, ws=0, ops=0, first=10**12, last=0))
    a['static'] += float(r['static_tof']); a['mean'] += float(r['mean_tof']); a['hmr'] += float(r['mean_hmr'])
    a['peak'] = max(a['peak'], int(r['peak_live'])); a['ws'] = max(a['ws'], int(r['peak_live_ws'])); a['ops'] += float(r['ops'])
    a['first'] = min(a['first'], int(r['first_op'])); a['last'] = max(a['last'], int(r['last_op']))
hist = collections.defaultdict(lambda: collections.Counter()); ent = collections.defaultdict(lambda: collections.Counter())
for h in H:
    hist[top(h['seg'])][int(h['level'])] += float(h['ops_at_level']); ent[top(h['seg'])][int(h['level'])] += int(h['entries_to_level'])
T = sum(a['mean'] for a in st.values())
print(f"{'stage':16s} {'static':>8s} {'meanT':>10s} {'%T':>6s} {'HMR/shot':>9s} {'peakQ':>6s} {'ws':>3s}  ops@892  ops@>=891 ops@>=890 entries@892 entries@891 entries@890")
order = ['mask_projection','initial','extract','synthesis','convert','scan','unconvert','unsynthesis','unextract','uninitial','restore_masks','(none)']
for k in order:
    if k not in st: continue
    a = st[k]; h = hist[k]; e = ent[k]
    ge = lambda L: sum(v for l, v in h.items() if l >= L)
    print(f"{k:16s} {a['static']:8.0f} {a['mean']:10.1f} {100*a['mean']/T:6.2f} {a['hmr']:9.1f} {a['peak']:6d} {a['ws']:3d} {h[892]:8.0f} {ge(891):9.0f} {ge(890):9.0f} {e[892]:10d} {e[891]:10d} {e[890]:10d}")
print('total mean T', T)
