# DQI asymmetry tools (Agent B, own code)

These tools produced `briefs/dqi_profile.md` §13 on 5f901c55. They need `../cp1/prof2.cc` (updated here), built with
the env outputs `PROD_OUT` (product hash, product popcount, condition popcount), `HMR_OUT` (measured-value hash),
`HMRV_OPS`/`HMRV_OUT` (measured vectors), `LIVE_OUT` and `STATE_OPS_FILE`.

| file | what it does |
|---|---|
| `mapcuts.py` | maps the cp1 stage cut points onto a patched file by op-code signature search |
| `w_cuts.json` | stage cut points used for 5f901c55. The reverse boundaries were set from `tgtsweep.py` |
| `decomp.py` | forward/reverse Toffoli decomposition: mirror, new, measurement-dependent, zero-product |
| `condsrc.py`, `repairdeps.py`, `repairjoin.py` | which measurements each conditioned or CCZ reverse Toffoli depends on (exact classical-dataflow sets) |
| `remat.py` | whether each repair's measured values reappear in the affine span of a later state (uses `span contain`) |
| `withinrep.py`, `recompute.py` | blocks of products recomputed within a stage; whether they are erased in between |
| `widthcheck.py` | free qubits in each erase-then-recompute window (per-op live counts) |
| `dumpops.py`, `compact.py` | op listings |
