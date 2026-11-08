"""Patch marculera's experiments/quantize_rm.py (Apache-2.0) with stage checkpoints, resume and a wall-clock budget.

    python patch_quantize_resume.py SRC/quantize_rm.py DST/quantize_rm_ckpt.py

The patched script reads two environment variables:
  QRM_CKPT    path of the checkpoint .npz (written after every stage, read at start if present)
  QRM_BUDGET  seconds of wall clock after which it saves and exits with status 3 (resume in a later session)
Nothing else in the algorithm changes. Modification notice (Apache-2.0 sec. 4b): checkpointing added by Agent C.
"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()

anchor = "    schedule = tuple(float(x) for x in a.free.split(',')) if a.free else FREE\n"
assert anchor in s
ckpt_code = anchor + '''    import os as _os
    _CK = _os.environ.get('QRM_CKPT'); _BUDGET = float(_os.environ.get('QRM_BUDGET', '1e18')); _T0 = time.time()
    start_stage = 0
    if _CK and _os.path.exists(_CK):
        with np.load(_CK, allow_pickle=False) as _z:
            theta, w = np.array(_z['theta']), f32(np.array(_z['w']))
            frozen, qvals = np.array(_z['frozen']), np.array(_z['qvals'])
            key = jax.random.wrap_key_data(jnp.asarray(_z['key']))
            reserved = np.array(_z['reserved']) if bool(_z['has_reserved']) else None
            locked = (np.array(_z['locked_r']), np.array(_z['locked_m'])) if bool(_z['has_locked']) else None
            clipping = bool(_z['clipping']); start_stage = int(_z['stage'])
        print(f'resumed from {_CK} at stage {start_stage} (frozen {frozen.mean():.4f})', flush=True)

    def _ckpt(next_stage):
        if not _CK:
            return
        tmp = _CK + '.tmp.npz'
        np.savez(tmp, theta=np.asarray(theta), w=np.asarray(w), frozen=frozen, qvals=qvals,
                 key=np.asarray(jax.random.key_data(key)), has_reserved=reserved is not None,
                 reserved=reserved if reserved is not None else np.zeros(1, bool), has_locked=locked is not None,
                 locked_r=locked[0] if locked is not None else np.zeros(1), locked_m=locked[1] if locked is not None else np.zeros(1),
                 clipping=clipping, stage=next_stage)
        _os.replace(tmp, _CK)
        if time.time() - _T0 > _BUDGET and next_stage < len(schedule) + 1:
            print(f'budget reached after stage {next_stage - 1}: checkpoint saved, exiting for resume', flush=True)
            sys.exit(3)
'''
s = s.replace(anchor, ckpt_code)

loop = "    for stage, free in enumerate(schedule + (None,)):\n"
assert loop in s
s = s.replace(loop, loop + "        if stage < start_stage:\n            continue\n")

lb = "                  f'D {float(d_penalty(w)):7.2f}  L-BFGS ({time.time() - t0:.0f} s)', flush=True)\n            continue\n"
assert lb in s
s = s.replace(lb, lb.replace("            continue\n", "            _ckpt(stage + 1)\n            continue\n"))

ad = "              f'D {float(d_penalty(w)):7.2f}  ({time.time() - t0:.0f} s)', flush=True)\n"
assert ad in s
s = s.replace(ad, ad + "        _ckpt(stage + 1)\n")

# `reserved`, `locked` and `clipping` are assigned in main and read by nested functions; the resume block assigns them
# in main's scope, which is where they already live, so no nonlocal changes are needed.
open(dst, 'w').write(s)
print('patched ->', dst)
