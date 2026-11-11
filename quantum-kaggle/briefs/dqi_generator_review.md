# DQI generator: pin, security review, sandboxed run

Reviewed 2026-11-11 before execution, as instructed by the supervisor.

## Pin
| Item | Value |
|---|---|
| Dataset | `atakanaldemir/qcc-c44-five-helper-release-sources`, version 1 (2026-11-05), Apache-2.0 |
| Download zip sha256 | `649d398b24cbc3ee897c7283fa67a436fb39dd2465533725d6af086d894b9b28` |
| `release_source.xz` sha256 | `a0f705ea88b888cfaa89b84ddc7c988fa4aa5702c1ffc81cb9b2f917e149b95c` (matches its `MANIFEST.json` `bundle_sha256`) |
| DQI source folder | `datasets/qcc-dqi-nonempty-projective-lean-source-v3` (480 files) |
| Entry point | `rebuild_native.py --out <new dir>` (63 lines; hash-checks every source file against its manifest) |
| Expected output | `7bd10fca…dd0f`, Q = 892, static T = 458,203 (manifest) |
| Python deps (own venv, `requirements.lock`) | kickmix 1.0.0, numpy 2.5.4, scipy 1.18.1, numba 0.68.1, llvmlite 0.50.0 |

**Important:** the generator reproduces an *ancestor* of the public DQI decoder. Its static T is 458,203, against 395,640
for public v100 (`e9f54be3`). v95 and v100 are this lineage after further stream rewrites (product caches, measurement
order, cache routes) that this bundle does not contain. A reproducible v100 baseline therefore needs those later rewrite
steps too.

## Review findings (static, all 392 Python files in the bundle)
- **Network:** no networking library is imported in the DQI source. The only Kaggle URL (in an unrelated chemistry folder) is a string constant that is never fetched.
- **Processes:**
  - The entry point runs the bundle's own scripts as `python -I -B` subprocesses, with the output directory as the working directory.
  - It deletes only `.kmb` files inside the output directory whose sha256 matches a pinned value.
  - The build script installs an audit hook that blocks `os.remove`, `os.rmdir` and `os.rename`.
- **Dynamic code:** about 30 `exec(compile(source…))` calls. Spot checks show source patching: a sibling bundle file is read, exactly one asserted string is replaced, and the result is compiled. No code is fetched or decoded from opaque blobs.
- **Native calls:** one `ctypes.CDLL(None).malloc_trim(0)` (libc memory trim).
- **Writes:** the pipeline writes to the output directory. A few experimental scripts not used by the pipeline write next to their own source; the read-only mount covers this.
- **Environment:** the entry point copies `os.environ` into its children, so the sandbox clears the environment.

## Sandbox used
- `unshare -m -n`: own network namespace with no interfaces. A Kaggle request from inside fails, so the proxy's injected Kaggle credential is unreachable.
- Source is a fresh copy, bind-mounted read-only. Its sha256 list is recorded before the run and re-checked after.
- `env -i PATH=/usr/bin:/bin HOME=<scratch> LANG=C.UTF-8`: no proxy variables and no tokens.
- `prlimit --as=20e9`, `timeout 4h`, `nice -n 10`.
- Script: `tools/dqi/run_generator_sandbox.sh`. Its output is validated only with the unchanged official verifier, on fresh salts.

## Results (2026-11-11)
- **Byte-exact reproduction.** The run finished in 332 s, with status `ISOLATED_SOURCE_AND_PINNED_NEW_PLANS_BYTE_EXACT_PASS`.
  - Output sha256 `7bd10fcab4f2dd653aabfa475cd67b0d7b8ca6bd1aec7149b7905c2b0390dd0f`, as pinned.
  - All six stage boundaries matched their pinned hashes.
- **Source integrity.** The read-only copy's sha256 list is identical before and after the run (480 files).
- **Official verifier** (unchanged), 3 fresh salts, 102,400 shots each:

| Salt | Status | Value / phase errors | Mean T | Static T | Q | Ratio |
|---|---|---|---|---|---|---|
| Cgen-00 | PASS | 0 / 0 | 403,502.7 | 458,203 | 892 | 63.9012 |
| Cgen-01 | PASS | 0 / 0 | 403,502.7 | 458,203 | 892 | 63.9012 |
| Cgen-02 | PASS | 0 / 0 | 403,502.8 | 458,203 | 892 | 63.9012 |

- **Gap to public v100** (e9f54be3; mean T 395,305, ratio 65.226): **8,198 mean T (2.07%)**. That is much smaller than the
  62.6k static-T gap, because most of the extra static T sits in rarely executed conditional branches. The later public
  rewrites therefore recovered about 8.2k mean T, and the sprint's bridge step attributes them by stage.
