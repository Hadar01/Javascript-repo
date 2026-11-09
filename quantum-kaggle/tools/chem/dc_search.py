"""Plan search (qwertykeypadapple's kernel-relation search on marculera's compiler, both Apache-2.0) on deltas whose
don't-care rows are filled by helper_build.fill_dontcare. Plans are written as circuit_K.json, like
marculera_plan_search.py, and are built with helper_build.py --dontcare.

usage: QK_SCRIPTS=.../qk/scripts python dc_search.py TABLE.npz PLAN_DIR --circuits 4,5 --seeds 0:4 [--layouts sixes]
       [--trials 1] [--margins 0] [--jobs 2] [--no-fill]
"""
import argparse, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helper_build as hb  # noqa: E402

hb.setup_paths(Path(os.environ['QK_SCRIPTS']))
import marculera_plan_search as mps  # noqa: E402
import rmcode  # noqa: E402
from fourqrom import batch_deltas  # noqa: E402


def inputs(table, fill=True):
    with np.load(table) as z:
        words, deg = (np.asarray(z[k], np.int64) for k in ('angle_words', 'codes'))
    out = []
    for k, d in enumerate(batch_deltas(words, 5)):
        degs = rmcode.output_degrees(deg, k, 5, 8)
        d = rmcode.pad(d, degs, 8)
        if fill:
            d = hb.fill_dontcare(d, degs, len(words))
        out.append((d, degs))
    return out, max(1, (len(words) - 1).bit_length()), len(words)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('table'); ap.add_argument('plans')
    ap.add_argument('--circuits', default='0-14'); ap.add_argument('--seeds', default='0:4')
    ap.add_argument('--layouts', default='sixes'); ap.add_argument('--trials', default='1'); ap.add_argument('--margins', default='0')
    ap.add_argument('--jobs', type=int, default=2); ap.add_argument('--no-fill', action='store_true')
    a = ap.parse_args()
    ins, n_sel, n_rows = inputs(a.table, not a.no_fill)
    if '-' in a.circuits:
        c0, c1 = map(int, a.circuits.split('-')); circs = list(range(c0, c1 + 1))
    else:
        circs = [int(x) for x in a.circuits.split(',')]
    s0, s1 = map(int, a.seeds.split(':'))
    plans = Path(a.plans); plans.mkdir(parents=True, exist_ok=True)
    best = {k: json.loads((plans / f'circuit_{k}.json').read_text())['products'] for k in circs if (plans / f'circuit_{k}.json').exists()}
    tasks = [(k, ins[k][0], ins[k][1], n_sel, lay, int(tr), int(mg), s, [], n_rows, 'full', 'kernel')
             for k in circs for lay in a.layouts.split(',') for tr in a.trials.split(',') for mg in a.margins.split(',')
             for s in range(s0, s1)]
    print(f'{len(tasks)} jobs; best so far {best}', flush=True)
    with ProcessPoolExecutor(a.jobs) as ex:
        for fut in as_completed([ex.submit(mps.job, t) for t in tasks]):
            k, cfg, n, exact, terms, dt = fut.result()
            tag = f'circuit {k} {cfg["layout"]} t{cfg["trials"]} m{cfg["margin"]} s{cfg["seed"]} -> {n} products ({dt:.0f}s)'
            if not exact:
                print(tag, 'NOT EXACT'); continue
            if k not in best or n < best[k]:
                best[k] = n
                (plans / f'circuit_{k}.json').write_text(json.dumps(dict(products=n, config=cfg, terms=terms)))
                tag += '  NEW BEST'
            print(tag, flush=True)
    print('best', best, flush=True)


if __name__ == '__main__':
    main()
