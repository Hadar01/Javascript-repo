"""For each T-costing repair cluster: earliest later state (grid) whose affine span contains ALL the measured values
the cluster depends on -> the debt could be repaid there with Clifford Z_IF gates instead of the cluster."""
import json, numpy as np, collections, bisect
clusters = json.load(open('w_clusters.json')); mops = np.load('w_meas_ops.npy'); idx = {int(o): i for i, o in enumerate(mops)}
cuts = json.load(open('w_cuts.json'))['w']; names = ['pre','ext','syn','conv','scan',"conv'","syn'","ext'",'post']
cont = {}; cur = None
for l in open('contain_out.txt'):
    if l.startswith('##'): cur = int(l.split('_')[-1].split('.')[0]); cont[cur] = {}; continue
    q, ins, eq, cp = map(int, l.split()); cont[cur][q] = (ins, eq, cp)
grid = sorted(cont)
res = collections.Counter(); Tsum = collections.Counter(); ex = []
for c in clusters:
    rows = [idx[o] for o in c['hmr']]
    stage = names[bisect.bisect_right(cuts, c['first']) - 1]
    found = None
    for g in grid:
        if g <= c['last']: continue
        ok = all(cont[g].get(r, (1, 0, 0))[0] == 1 for r in rows)
        if ok: found = g; break
    k = (stage, 'remat-later' if found else 'never')
    res[k] += 1; Tsum[k] += c['T']
    if found and len(ex) < 12: ex.append((stage, c['n'], round(c['T']), len(rows), c['last'], found, names[bisect.bisect_right(cuts, found) - 1]))
for k in sorted(res): print(k, 'clusters', res[k], 'mean T', round(Tsum[k]))
for e in ex: print(e)
