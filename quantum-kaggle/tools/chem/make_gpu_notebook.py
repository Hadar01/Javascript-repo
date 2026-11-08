"""Write notebooks/chem_gpu_refit.ipynb (Agent C). Run: python make_gpu_notebook.py OUT.ipynb"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCH = (HERE / 'patch_quantize_resume.py').read_text()

cells = []
md = lambda s: cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': s})
code = lambda s: cells.append({'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': s})

md("""# dfthcsos on a GPU: lookup-aware rounding, kernel-search loaders, official verifier

Rounds marculera's continuous (8, 143, 45) compact-group table to 8-bit words with a **lookup-aware code ladder**: more
batches with bit 0 as a Reed–Muller RM(1,4) codeword per 16-address block. Each extra coded circuit saves 22 Toffoli
products per pass. The run then refines and refits the weights, compiles the 15 ANGLE circuits with
qwertykeypadapple's kernel-relation search on Lera's tensor-lookup compiler, and scores with the **unmodified** official
`dfthcsos` verifier.

**Checkpointing.** The rounding writes a checkpoint after every stage to `/kaggle/working/ckpt/`, and stops cleanly
when `BUDGET_H` is used up. To resume, attach this notebook's previous version output as an input and run again. The
checkpoint is found automatically.

**Credits (Apache-2.0).**
- **Lera (marculera):** the DF-THC compact-groups pipeline `dfthc-compact-pipeline`, i.e. the seed, Adam table,
  progressive rounding `quantize_rm.py`, `rmcode`, `refine`, `refit_al` and `tensorqrom`. Lera in turn credits
  ahmedberatozer, somejoint, mrmeows, heliosli, lightningv08, kozykappa, Kozykorpesh, Sumit Chongder, anazemcev,
  phucthaiv02, Michael Rustad, k256net and Dmitrii Gluzdov.
- **qwertykeypadapple:** the kernel-relation search (`qcc-kernel-search-portfolio`).
- **Google Quantum AI:** the starter kit `dfthc` and the verifier.

Our changes: stage checkpoint and resume for `quantize_rm.py` (a patch applied below; the algorithm is unchanged), the
code ladder, and the orchestration.""")

code("""# DATASETS: marculera/dfthc-compact-pipeline, qwertykeypadapple/qcc-kernel-search-portfolio, sohier/verifiable-circuit-compilation-starter-kit
# COMPETITION: google-verifiable-quantum-circuit-compilation
# ---- configuration ----------------------------------------------------------------------------------------------
TABLE      = 'adam_8x143x45.npz'   # marculera's continuous table (error_2 14.155 mHa before rounding)
CODES      = '0:1:0-14'            # lookup-aware ladder: '0:1:3-14' (Lera, proven 19.95 mHa), '0:1:2-14', '0:1:0-14' (all)
LBFGS_IT   = 60000                 # L-BFGS iterations per rounding stage (Lera's converged schedule; 30k did not pass)
BUDGET_H   = 8.4                   # wall-clock hours for the rounding in this session, then checkpoint and stop
KAPPA      = 2e-5
REFIT_TARGET_MHA = 19.995          # refit_al target for error_2; keeps ~5e-6 Ha margin on the 20 mHa gate
SEARCH_SEEDS = '0:6'               # kernel-search seeds per circuit (CPU, parallel)
SCHEDULE = ('0.9995,0.9990,0.9980,0.9970,0.9960,0.9950,0.9930,0.9910,0.9890,0.9860,0.9830,0.9800,0.9750,0.9700,'
            '0.9650,0.9600,0.9550,0.9500,0.9400,0.9300,0.9200,0.9100,0.9000,0.8800,0.8600,0.8400,0.8200,0.7950,'
            '0.7700,0.7450,0.7200,0.6900,0.6600,0.6300,0.6000,0.5700,0.5400,0.5100,0.4800,0.4500,0.4200,0.3900,'
            '0.3600,0.3300,0.3000,0.2750,0.2500,0.2250,0.2000,0.1600,0.1200,0.0900,0.0650,0.0450,0.0300,0.0200,'
            '0.0120,0.0060,0.0000')   # the 59-stage schedule of Lera's round_845_60k run""")

code("""import glob, json, os, shutil, subprocess, sys, time
from pathlib import Path
T_START = time.time()
WORK = Path('/kaggle/working'); WORK.mkdir(exist_ok=True)
def find1(pattern):
    hits = sorted(glob.glob(f'/kaggle/input/**/{pattern}', recursive=True))
    if not hits:
        raise FileNotFoundError(pattern)
    return Path(hits[0])
COMP = next(Path(p) for p in ['/kaggle/input/competitions/google-verifiable-quantum-circuit-compilation',
                              '/kaggle/input/google-verifiable-quantum-circuit-compilation'] if Path(p, 'verifiers').is_dir())
PIPE = find1('dfthc_refit/fastfit.py').parent
QK = find1('src/kernel_search.py').parent
STARTER = find1('dfthc/df_thc_sga.py').parents[1]
print('competition', COMP, '| pipeline', PIPE, '| kernel search', QK, '| starter kit', STARTER)
# the layout the kernel-search drivers expect: P/scripts/{kernel_search,...}.py and P/scripts/marculera/dfthc_refit
P = WORK / 'qk'; SCR = P / 'scripts'
if SCR.exists(): shutil.rmtree(SCR)
(SCR / 'marculera').mkdir(parents=True)
shutil.copytree(PIPE, SCR / 'marculera' / 'dfthc_refit')
for f in QK.glob('*.py'): shutil.copy(f, SCR / f.name)
E = SCR / 'marculera' / 'dfthc_refit' / 'experiments'
os.environ.update(DFTHC_DATA=str(COMP), DFTHC_STARTER=str(STARTER), PYTHONUNBUFFERED='1')
try:
    import optax  # noqa
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'optax'], check=True)
try:
    import kickmix  # noqa
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'kickmix'], check=False)
subprocess.run('nvidia-smi || echo no GPU visible', shell=True)\ntry:\n    import jax; print('jax devices:', jax.devices())\nexcept Exception as e:\n    print('jax import failed:', e)""")

import base64
code("import base64\nPATCH_B64 = '" + base64.b64encode(PATCH.encode()).decode() + "'\n"
     "Path(WORK / 'patch_quantize_resume.py').write_bytes(base64.b64decode(PATCH_B64))\n"
     "subprocess.run([sys.executable, str(WORK / 'patch_quantize_resume.py'), str(E / 'quantize_rm.py'), str(E / 'quantize_rm_ckpt.py')], check=True)")

code("""# ---- stage 1: lookup-aware progressive rounding (GPU), resumable --------------------------------------------------
CK = WORK / 'ckpt'; CK.mkdir(exist_ok=True)
ROUNDED = WORK / 'rounded.npz'
prev = sorted(glob.glob('/kaggle/input/**/ckpt/qrm.npz', recursive=True)) + sorted(glob.glob('/kaggle/input/**/rounded.npz', recursive=True))
for p in prev:                      # resume from an attached previous version of this notebook
    dst = ROUNDED if p.endswith('rounded.npz') else CK / 'qrm.npz'
    if not dst.exists():
        shutil.copy(p, dst); print('resuming from', p)
status = 'done' if ROUNDED.exists() else None
if status is None:
    env = dict(os.environ, QRM_CKPT=str(CK / 'qrm.npz'), QRM_BUDGET=str(BUDGET_H * 3600 - (time.time() - T_START)))
    cmd = [sys.executable, '-u', str(E / 'quantize_rm_ckpt.py'), str(find1(TABLE)), str(ROUNDED), '--brot', '8', '--open',
           '--codes', CODES, '--free', SCHEDULE, '--lbfgs-until', '1.0', '--lbfgs-iters', str(LBFGS_IT), '--kappa', str(KAPPA)]
    with open(WORK / 'round.log', 'a') as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env).returncode
    print(open(WORK / 'round.log').read()[-3000:])
    status = 'done' if rc == 0 else 'paused' if rc == 3 else f'failed ({rc})'
print('rounding:', status)
(WORK / 'status.json').write_text(json.dumps({'rounding': status, 'codes': CODES, 'lbfgs_iters': LBFGS_IT}))""")

code("""# ---- stage 2: refine the one-body rows and refit the weights to the gates (CPU) ---------------------------------
if status == 'done' and not (WORK / 'finish' / 'refit_al.npz').exists():
    cmd = [sys.executable, '-u', str(E / 'finish_rm.py'), str(ROUNDED), str(WORK / 'finish'), '--target', str(REFIT_TARGET_MHA),
           '--trials', '6', '--shots', '64']
    with open(WORK / 'finish.log', 'w') as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, OPENBLAS_NUM_THREADS='1'))
    print(open(WORK / 'finish.log').read()[-2500:])      # includes Lera's own build + official verify as a baseline""")

code("""# ---- stage 3: kernel-relation search loaders (CPU, parallel) + build + official verifier -------------------------
TABLE_FINAL = WORK / 'finish' / 'refit_al.npz'
if status == 'done' and TABLE_FINAL.exists():
    plans, cand = WORK / 'plans', WORK / 'candidate' / 'dfthcsos'
    jobs = str(max(1, os.cpu_count()))
    for args in (['--engine', 'kernel', '--cache', 'full', '--layouts', 'sixes', '--margins', '0', '--trials', '1'],
                 ['--engine', 'kernel', '--cache', 'full', '--layouts', 'sixes,fives,default', '--margins', '0,2', '--trials', '1,6']):
        subprocess.run([sys.executable, '-u', str(SCR / 'marculera_plan_search.py'), str(TABLE_FINAL), str(plans),
                        '--seeds', SEARCH_SEEDS, '--jobs', jobs, *args], env=dict(os.environ, OPENBLAS_NUM_THREADS='1'))
    if cand.exists(): shutil.rmtree(cand)
    subprocess.run([sys.executable, '-u', str(SCR / 'marculera_plan_build.py'), str(TABLE_FINAL), str(plans), str(cand)], check=True)""")

code("""# ---- stage 4: the unmodified official verifier on the candidate folder, default and a private salt ----------------
sys.path.insert(0, str(COMP / 'verifiers'))
from dfthcsos import verify as V
REF = 3355599588.3155375
cand = WORK / 'candidate' / 'dfthcsos'
if cand.exists():
    (cand / 'verify.json').unlink(missing_ok=True)        # the candidate folder holds only angle_k_*.kmb + submission.npz
    out = {}
    for salt in ('', 'agentC-private-check'):
        r = V.verify(str(cand), salt=salt)
        out[salt or 'default'] = {k: v for k, v in r.items() if isinstance(v, (int, float, str, bool))} | {
            'ratio': REF / float(r['score']), 'metrics': r['metrics']}
        print(f"salt {salt!r}: {r['status']} lambda_eff {r['lambda_eff']:.6f} T {r['toffoli_count']:.0f} Q {r['num_qubits']} "
              f"e1 {1e3*r['metrics']['error_1']:.6f} e2 {1e3*r['metrics']['error_2']:.6f} mHa E_gap {r['metrics']['E_gap']:.9f} "
              f"ratio {REF / float(r['score']):.4f}")
    (WORK / 'candidate_verify.json').write_text(json.dumps(out, indent=1, default=str))
    shutil.make_archive(str(WORK / 'candidate_dfthcsos'), 'zip', cand)
print('elapsed', round((time.time() - T_START) / 3600, 2), 'h')""")

nb = {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                   'language_info': {'name': 'python'}}, 'nbformat': 4, 'nbformat_minor': 5}
Path(sys.argv[1]).write_text(json.dumps(nb, indent=1))
print('wrote', sys.argv[1])
