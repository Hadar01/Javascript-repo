# Pinned artifacts (2026-11-19)

These are the files behind our current best submission and the final-selection analysis. Paths are relative to the
session scratchpad; the large binaries are not committed, so re-obtain them from the named public datasets and check
them against these hashes. The 15 slot-1 angle loaders are listed in `tools/dqi/finalsel/slot1_angle_loaders.sha256`.

| Artifact | sha256 | Source |
|---|---|---|
| `ds_jmt_w/invsqrt.kmb` | `864f81cd20489d80e302f48014fcedec3b3fb703122fbcbac41b0bb2a395a859` | invsqrt slot 1: maoxin123 44-qubit (junmiaotiao/qcc-frontier-20261118w) |
| `ds_jmt_w/dqi.kmb` | `5f901c556cafd02dc11641eee7766171a454e3a0b6687d890ff9f99944e1934c` | DQI slot 1: boristown PW4 on grantprater merged closings (same dataset, unpacked) |
| `ds_jmt_w/dqi_5f901c55.kmb.xz` | `25b4d0342f52ff8fc5e38a9c9b9dffaea35dba7d353a16fe948233fd1b66ddae` | packed form as shipped in that dataset |
| `ds_jmt_w/dfthcsos/submission.npz` | `4d63be3d5c26cfa447a3464eeaf515a652814a1dd4c78f1f1af2f5b7d9e9b8b3` | chemistry slot 1: maoxin123 4,022-T loaders + leotang09 refit table |
| `ds_hayatohikawa_qcc-c8-milestone-portfolio/dqi.kmb` | `4b350932b03931af6040c871209da62aa0ebc74cfac3e77efcb6384e027285cc` | DQI slot-2 fallback: hayatohikawa C8 milestone |
| `ds_hayatohikawa_qcc-c8-milestone-portfolio/invsqrt.kmb` | `090009609ee68ca309b28950c06adb7c0640ed784f8dfbc78f1319088e8322bf` | earlier 44-qubit invsqrt (syed v14 line) |
| `ds_hayatohikawa_qcc-c8-milestone-portfolio/dfthcsos/submission.npz` | `7e6e65d79f3528d7ec64bb22e5498edac4979dd0164b3a3cb4c67f05035133a1` | earlier chemistry table (11.3840) |
| `jeff/invsqrt.kmb` | `9339eeccc3b2d01289c8c51687bda31a70b0260e22bed07c516edb6134705641` | jeffemerson AND-merge on syed v14 (27.6599), rebuilt from published diff |
| `mx10/submission.zip` | `4862c0d995b60d0faee8a2d411bba7c5efbe2b85c3f347eaab4a058b4579f9b4` | our current best submission (ref 58498405, public 28.18965) |
| `nov19/ds_ozertuu/invsqrt.kmb` | `acc7b9c86b4f65c0204194779a85d2c6b6631538316ffab2091c416a178f60a0` | 2026-11-19 frontier invsqrt: maoxin123 44-qubit, cost 74,361.78 (ozertuu/quantum-sim-linalg-cache) |
| `nov19/ds_ozertuu/dqi.kmb` | `f56b04c7138951cdbb2133dd6ea0dfb896528a1adc930597f02593a0506197a8` | 2026-11-19 frontier DQI: goodpjw2008 swap-collapse on Koushik Rudra's 4471b493 (same dataset, dqi.kmb.xz) |
| `nov19/ds_ozertuu/dfthcsos/submission.npz` | `6ef06081cb9c5752ee7235c86d480ddfc5db027f01e5d5d66a544dbda85d1958` | 2026-11-19 chemistry weights: Manvender Singh refit of 4d63be3d; loaders identical to slot 1 |
| `nov19/f23498/invsqrt.kmb` | `ecf908fe…` | same invsqrt as acc7b9c8 with lower-precision angle literals (cost 74,383.70) |
| `mx11/submission.zip` | `5cdb7e4acbe8c082…` | submission ref 58572455 (acc7b9c8 + f56b04c7 + 6ef06081 + slot-1 loaders), local 28.2384 at K=0 |
| `nov19/dqi_4471/dqi.kmb` | `4471b4933c18fd654a3ab7cf15cb01958b98ccbd9…` | DQI slot-2 candidate: Koushik Rudra v60 frontier (asteriospanoras/qcc-circuit-atlas frontier/) |
| `mx12/submission.zip` | `82f3871f2a9a8b1a…` | submission ref 58573441 (mix11 with DQI 4471b493), the slot-2 hedge |
| `kg/data/kickmix/kickmix.so` | `c66b3216c4029e0cdfd09054306aa0feadf53ab2f50c1164e37f752874e5005e` | competition-bundled simulator (results identical to PyPI kickmix 1.0.0) |
