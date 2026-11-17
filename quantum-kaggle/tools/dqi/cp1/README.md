# DQI checkpoint-1 tools (Agent B, own code)

These tools produced `briefs/dqi_profile.md` §12. They were written against the scratch layout
`work_B/{cp1,csrc,inputs}`, so set the paths before reuse.

| file | what it does |
|---|---|
| `prof2.cc` | `prof.cc` plus several env-driven outputs (below) |
| `span.c` | GF(2) affine-span tools on state dumps: `rank`, `pair` (intersection dimension), `hash` (canonical span), `contain` |
| `winprof.py` | static per-window profile of an untagged kmb: T, conditioned T, HMR, mask-conditioned ops |
| `tgtsweep.py` | per K Toffolis: which syndrome words are targets/controls (stage mapping for untagged files) |
| `topbounds.py` | top-level INFO_TAG boundaries of a tagged kmb |
| `mkseg_untagged.py` | builds 9-stage segment files for sy13/v119/h890. Its boundary op indices were located by hand from `tgtsweep.py` |
| `rowhash.py`, `rhmatch.py` | qubit-row hash overlap between state dumps (basis-dependent; use `span.c pair` for basis-free comparison) |
| `repeats.py`, `retain_bound.py`, `retain2.py` | sample-based product-retention headroom; `retain2.py` cross-checks across input sets |
| `run_census.sh` | activity census of listed Toffolis on fresh official-sampler sets |
| `stage_cuts.json` | the stage boundaries used in §12 |

`prof2.cc` env outputs:
- `STATE_OPS_FILE`: sorted state dumps;
- `PHASE_OPS`;
- `PROD_OUT`: per-Toffoli product hash and popcount;
- `LIVE_OUT`: per-op live count;
- `IDLE_OUT`: touch-based idle windows per qubit;
- `ZP_OPS` / `ZP_OUT`: control popcounts at listed ops;
- `ACT_OPS` / `ACT_OUT`: union activity of listed ops per group. Groups 10/11 record where the product differs from
  one control.
