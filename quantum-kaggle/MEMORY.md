# Project memory — Google Quantum AI: Verifiable Quantum Circuit Compilation

## Mission
Reach the top 100, then the top 1% (about rank 26), then **win**. Keep iterating until 2027-01-20 23:59 UTC.

## Competition facts (snapshot 2026-11-08)
- URL: https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation (id 161954)
- Prize pool $150k: 1st $50k, then $25k / $10k / 3×$5k. Also $10k mid-competition (2026-11-20, public notebook required),
  $10k longest-leader, and 3×$10k single-task prizes.
- Max team size 5. Merge deadline 2027-01-13. 5 submissions/day. Scoring takes ~45 min.
- Companion paper: arXiv:2610.23832 (Khattar, Rubin, Gidney, Broughton, Low, Babbush).
- Score = (Π_b cost_ref/cost_b)^(1/3) over three tasks:
  - invsqrt (fusion, 1/√x phasing): cost = Q × (Toffoli + T/4)
  - dqi (RS(4095,4025) decoder over GF(2^12)): cost = R(ε+) × Q² × T
  - dfthcsos (FeMoCo block encoding): cost = λ_eff × T × Q, with ≤128 qubits per angle circuit,
    ≤20 mHa error, and limits on Λ and E_gap

## Leaderboard snapshot (2026-11-08, 2602 teams)
| Rank | Score |
|---|---|
| 1 | 29.30 |
| 10 | 27.03 |
| 26 (top 1%) | 26.25 |
| 100 | 25.17 |
| 500 | 25.01 |

- Public plateau ≈ 25.1, from heliosli's "The dataset is public now" notebook:
  invsqrt 21.75× (62 qubits), dqi 65.2× (892 qubits), dfthcsos 11.2× ((8,143,44) table, 15 angle circuits).
- Improvement in the product of ratios needed over 25.1:
  - ×1.008 for top 100
  - ×1.144 for top 1%
  - ×1.59 for #1

## Status log
- 2026-11-08: Found the competition and downloaded the data, the paper and 15 top notebooks (in the session scratchpad;
  re-download with the Kaggle API, which the proxy authenticates). Launched three expert agents
  (invsqrt / DQI / chemistry) to read the paper, the cited references, the verifiers and the notebooks.
  The experts debated (see quantum-kaggle/briefs/). The plan and reading guide are in quantum-kaggle/PLAN.md.
- Key conclusions:
  - The chemistry λ_eff floor is 46.786 (public best 46.893), so weight refitting is finished as a lever.
  - The chemistry levers left are the angle-loader Toffolis and the row-budget loophole:
    a table with ≤ ~650 rows saves an address bit; shape (4,143,88) is predicted at 14.3×, but no table that size
    has been shown to meet 20 mHa yet.
  - DQI: profile the stages first; expected −10–15% cost.
  - invsqrt: qubits 62→60 and rotations 41→35; expected −5–10% cost.
  - Shared tool to build: a GF(2) AND-count minimiser for the DQI multiplier, chemistry loaders and the invsqrt table.
  - Forecast with focused effort: 27.5–29.5.
- 2026-11-08 (Edge-Finder, briefs/E_edges.md):
  - **Top edges:**
    - merge with a per-task specialist before 01-13;
    - re-open invsqrt: #2 is now working on it, and #1's LLM estimates 40–45× for it;
    - use the Apache-2.0 Gu et al. repo (github.com/andigu/uncompute: liveness profiler, DQI stage profile, QROM pruning);
    - private-salt robustness: expected DQI cost; keep chemistry margins ≥ 1e-7 (public files sit at 2.4e-10).
  - **Host rulings:**
    - ANGLE_k only needs to be correct on reachable states;
    - prizes need generators that reproduce the exact circuits;
    - commercial AI is allowed.
  - **Not available:** the organizers' public code holds no better circuits (Qualtran has only a 63-AND Karatsuba multiplier). A GF(4)-tower multiplier below 42 ANDs is proven impossible: μ₄(6)=14.
- NEXT ACTION: Phase 0 of PLAN.md. Submit the public portfolio (about 25.1), build the verifier harness and the
  qubit/Toffoli profiler in Kaggle, then run the chemistry row-budget fit.
- Constraint: running the downloaded kickmix.so locally was blocked by the permission policy. Run circuits in
  Kaggle notebooks instead, or ask the user to allow local runs.

- 2026-11-08 (later):
  - Kaggle user is `aarushpandey`; we had 0 submissions at this point.
  - Pushed the private notebook https://www.kaggle.com/code/aarushpandey/qcc-baseline-harness
    (source: quantum-kaggle/notebooks/qcc_baseline_harness.ipynb). It rebuilds the public portfolio from the dataset
    heliosli/qcc-circuits-live, verifies it under our own salt, and writes submission.zip. Its harness has
    score_task() and profile_circuit().
  - Launched the Edge-Finder agent, which is restricted to legitimate public edges and reports loopholes without
    exploiting them. Output goes to briefs/E_edges.md.

- 2026-11-08 06:40 UTC:
  - The baseline notebook v1 passed all three verifiers under our own salt:
    invsqrt 21.7479, dqi 65.2181, dfthcsos 11.1979, geometric mean 25.13668.
  - Submitted its output (submission ref 58126741); the leaderboard score is pending.
  - Published the explainer artifact https://claude.ai/artifact/3ZiKTAFyHht47npDcNpteR
    (source: quantum-kaggle/explainer/index.html).
  - The Edge-Finder agent stopped early because the usage limit (5-hour window) was hit at about 06:40 UTC
    (resets 07:20 UTC). It needs to be resumed; its output target is briefs/E_edges.md.
  - API notes:
    - Submit a notebook with POST https://www.kaggle.com/api/v1/competitions.CompetitionApiService/CreateCodeSubmission
      {competitionName, kernelOwner, kernelSlug, kernelVersion, fileName, submissionDescription}.
    - Push a notebook with POST /api/v1/kernels/push.

- 2026-11-08 ~12:50 UTC:
  - Submission 58126741 scored **25.13667** on the public leaderboard: **rank 255 of 2,630**.
  - Leaderboard thresholds now:

    | Rank | Score |
    |---|---|
    | 1 | 29.301 |
    | 10 | 27.080 |
    | 26 | 26.260 |
    | 100 | 25.183 |

  - **This is our current best. Every new submission must beat it.**
  - Plan changes from the edge brief:
    - Fusion becomes a main track; a #1-team member estimates 40–45× is possible.
    - Use Gu et al.'s profiler (github.com/andigu/uncompute) instead of building our own.
    - Look for a team merger before 2027-01-13.

- 2026-11-08 evening (local runs approved by the user; kickmix 1.0.0 installed from PyPI in a scratch venv):
  - Public v95 portfolio checked locally:
    - invsqrt 21.7762 (62 qubits, 1538.2 Toffoli-equivalents)
    - dqi 65.2181
    - chem 11.1981
    - combined about 25.15
  - DEAD END, invsqrt gate-level: 0 of 1,409 Toffolis are removable, the rotation angles are optimal, and merging
    41→33 rotations costs a qubit. Next is our own readable generator (reverse arithmetic, phase shift, 61 qubits).
  - DEAD END, chemistry smaller table (4,143,88): error_2 plateaus at about 89 mHa against the 20 mHa gate.
  - DEAD END, chemistry weight refit: the weights are at a local optimum; at most 0.09% is available.
  - Chemistry margins: a fresh private salt cannot change error_1, error_2, Λ or E_gap.
  - Next for chemistry: a lookup-cost-aware new table on a Kaggle GPU (notebooks/chem_gpu_refit.ipynb).

- 2026-11-09 03:30 UTC:
  - We had dropped to rank 487 of 2,667 (more teams copying the public set).
  - Thresholds now:

    | Rank | Score |
    |---|---|
    | 1 | 29.301 |
    | 26 | 26.354 |
    | 100 | 25.206 |

  - The public dataset is now v98. Its dqi has 2 phase errors under our salt (64.68×), so the older v95 dqi with zero
    errors (65.22×) is better. The chemistry file changed but scores the same.
  - Submitted the v95 set as a direct file upload (ref 58149714). Local score 25.148.
  - Direct upload flow:
    1. POST competitions.CompetitionApiService/StartSubmissionUpload, which returns createUrl and token.
    2. PUT the zip to createUrl. The file MUST be named submission.zip.
    3. POST CreateSubmission with {competitionName, blobFileTokens, submissionDescription}.
  - invsqrt track blocker: our generator is at 12.40 (94 qubits). The public 62-qubit architecture is decoded in
    briefs/invsqrt_architecture.md. Reaching it needs a whole-table XAG lookup synthesizer, a shared tool
    (tools/xag/, in progress), plus carry-light reverse adders.
  - Chemistry: the GPU notebook is held (expected to score about 10.9, below public). The CPU loader-trick port is in progress.
  - Agents hit the usage limit at about 21:00 UTC Nov 8 and were resumed after it reset.

- 2026-11-09 ~04:00 UTC:
  - Submission 58149714 (v95 set) scored **25.14772**: **rank 280 of 2,668**. This is our current best.
  - Dead end: the XAG lookup inside the invsqrt generator makes it worse (8.58×), because its helpers cost qubits.
    The real blocker is carry-light reverse adders; invsqrt is paused.
  - Dead end: XAG on the chemistry loaders gives 291 products at best, against our kernel search's 201 and
    syed3000's 195. Closing that gap needs a GF(2) tensor-decomposition search (research); the floor is about 168.
  - Awaiting the user's decision: merger shortlist, and/or one research bet
    (chemistry tensor search, invsqrt adders, or DQI stage profile).

- 2026-11-09 12:30 UTC:
  - We were at rank 422 of 2,691. Top 100 needs 25.220.
  - Public v100 checked:
    - invsqrt: 21.7816 (better).
    - chem: 11.1982 (about the same).
    - dqi: 65.2264 with 0 errors under one salt, 64.93 with 1 value error under another (salt-dependent).
      Keep the v95 dqi.
  - Submitted mix1 (ref 58163722): v100 invsqrt + v95 dqi + v100 chem, local score 25.1498.
    It scored **25.14983**: **rank 306 of 2,693**. This is our current best.
  - Lesson: the public DQI files now trade rare failures for Toffolis. Always score candidate DQI files under
    two or more salts before using them.

- 2026-11-09: Supervisor progress report written as a Claude Doc: https://claude.ai/artifact/Yc3FjAKQLXEfAq75cbTu6D

## SUPERVISOR GUIDANCE (2026-11-09) — follow this
- **Milestone:** one reproducible improvement of our own, independently verified. Stop broad brainstorming.
- **Priority 1: bounded rotation-merge experiment (invsqrt).** Our dismissal was wrong.
  - At exactly +1 qubit and −42 Tof-eq: 63×1495.8 / (62×1537.8) = 0.98838, a 1.16% task-cost cut,
    taking the score to about 25.248 (above the top-100 line).
  - Measure the exact extra qubits, recomputation, phase corrections and full-circuit cost.
- **Priority 2: exact DQI profile, then one targeted redesign.**
  - Measure forward/reverse extraction, polynomial synthesis, scan, peak qubits and workspace reuse.
  - Measure mean T and failures across many independent seeds.
  - Evaluate everything under R(ε+)·Q²·T.
- **Rigour:**
  - "No improvement found" is not "optimal"; narrow every claim to what was tested.
  - Two salts are not enough to rank rare-failure circuits. Use an equal evaluation budget per candidate,
    report uncertainty, and reserve fresh seeds for final validation.
  - The ~168-product chemistry "floor" is not a proven bound, and one failed fit does not prove a
    smaller table is impossible.
- **XAG:** optimise for full-circuit cost and peak workspace, not AND count.
- **Chemistry GPU run:** defer unless there is a specific new hypothesis.
- **Reproducibility:** keep upstream source, licences, versions, parameters and artifact hashes alongside every
  improvement. The exact prize requirements still need confirming.
- **Merger:** the "+3–8%" figure is speculation until a specific contribution is identified.
- **DQI targets, other tasks unchanged:**

  | Target score | DQI cost cut | DQI ratio |
  |---|---|---|
  | 25.22 | −0.83% | 65.77× |
  | 26.35 | −13.05% | 75.01× |
  | 29.30 | −36.76% | 103.13× |

- 2026-11-09 supervisor priority 1 RESOLVED (measured on public v100 invsqrt, sha 034c7c2a…):
  - The rotation merge does not pay. Each merged weight needs its own high-pass bit kept live from op ~8431 to
    ~16276, across several 62-qubit peaks.
    - No qubit is idle over that interval.
    - The bits cannot be recovered as an XOR of live qubits.
    - Neither pass can be moved.
  - Result: m merged weights cost m extra qubits and save m−1 rotations (7.19 Tof-eq each), against 24.8 Tof-eq
    per qubit:

    | m | Cost change |
    |---|---|
    | 1 | +1.6% |
    | 8 | +9.1…11.5% |

  - Untested: recovering those bits non-linearly at the low pass.
  - Tool: tools/invsqrt/merge_probe.py. Details: briefs/invsqrt_log.md.

- 2026-11-09 invsqrt delay line (public v100), measured:
  - 93 Toffolis (89 CSWAP + 4 CCX), all executed every shot, on the 62-qubit peak; 0 of 93 removable.
  - Tested rewrites, none built:
    - cap the shift at 7: net loss, since 63 inputs need phase fixes;
    - classical control: not applicable;
    - merge with an adjacent network: none adjacent;
    - extra buffers: each costs a qubit;
    - better encoding: slack at most about 3 Toffolis (+0.2%), no construction found.
  - Conclusion: the remaining invsqrt levers on the public file are small. Wait for the DQI profile before assigning
    the next research.

- 2026-11-10 04:00 UTC:
  - Rank 510 of 2,730 (25.14983). Thresholds: top 100 25.279, top 300 25.218.
  - DQI profile done: briefs/dqi_profile.md, measured from the circuit's INFO_TAG stage marks.
    - Split of T: extraction 39%, conversion 31%, synthesis 18%, scan 11%.
    - The reverse passes cost 48.1k T more than the forward ones.
    - Redesign #1: reuse D in the reverse extraction instead of re-running the scalar chain. Target −24k T,
      which takes DQI to about 69.4.
  - DQI failure stats (20 salts each plus a 1M-shot census) CORRECT our earlier choice:
    - v95: p 4.2e-6, CI [2.2, 7.2]e-6, E[ratio] 65.094. It has a w=35 phase-error family.
    - v100 (e9f54be3): p 2.9e-6, CI [1.3, 5.5]e-6, E[ratio] 65.140.
    - Use v100 from now on.
  - Public notebook maoxin123 "LB 25.218" (Apache-2.0, ChatGPT-assisted):
    - invsqrt c6519219, 21.9533: CSWAPs cut 226→205 for +9 CCX. This is a coordinated rewrite that our
      single-gate scans missed.
    - Chemistry weights refit, 11.1997.
    - Extracted to scratch mx2/ via scratch/extract_maoxin.py (no notebook code run).
  - Assigned: DQI agent on redesign #1 (splice unextract); invsqrt agent on diffing and generalising the CSWAP
    rewrite.

- 2026-11-10: Submitted mix2 (ref 58185878): invsqrt c6519219 (21.9533, fully verified under salt team-mx2-check) + dqi v100 + refit chem. Local score 25.2179.

- 2026-11-10 12:00 UTC: mix2 (ref 58185878) scored **25.21797** (local matched exactly): rank 494 of 2,753. Top 100 needs 25.312; rank 300 needs 25.227. DQI options A (blocked by policy on running the downloaded generator) and C (multiplier 99 = GF(16)^6, 9×11, optimal within the tower) found no gain.

- 2026-11-10 12:30 UTC:
  - Submitted mix3 (ref 58201004), local score 25.2390. **Scored 25.23899: rank 187 of 2,756 (best so far).** Top 100 needs 25.312:
    - invsqrt 26ebf39d (v104, gengsr shifter): 21.9677, full official PASS.
    - dqi v100 e9f54be3: 65.2263.
    - chem marculera dfthc-c44-build 79bc97e7 (XOR codes): 11.2204, 2 salts PASS.
  - v104 dqi 368d2d1c sweep: 4 failures / 1.024M shots (10 salts); pooled with ibillxia, 5 / 1.33M = 3.8e-6.
    Not distinguishable from v100 (2.9e-6, CI 1.3–5.5). Keep v100 for the private board.
  - invsqrt searches on c6519219 / 26ebf39d all came up empty: window resynthesis (≤8 qubits), pair/triple merges,
    conditional moves, and porting the shifter to the end network.
    - Untested: windows through HMR plus fix-up blocks.

- 2026-11-10 19:00 UTC:
  - The conditional-split branches of 26ebf39d are Gidney adders. There are 11 pairs, worth 37.75 mean T.
  - Every tested rewrite loses or ties at Q=62. Any further saving needs a slot freed at the branch peak by
    something outside the branch.
  - So far, every own-improvement attempt on invsqrt has been exactly negative:
    - rotation merge;
    - delay line;
    - rotation absorption;
    - window, pair and triple merges;
    - conditional moves and fix-up blocks;
    - split branches.
  - Rank slipped to 343 (rank 300 needs 25.254).
  - Public v107 release:
    - invsqrt a15b0d73 (alexchilton) and dqi 9fcda0c1 are new; verification and a 10-salt sweep are running.
    - chem is the marculera build again (11.2204).

- 2026-11-10 ~20:00 UTC:
  - Submitted mix4 (ref 58212324), local score 25.2937. **Scored 25.29371: rank 246 of 2,785 (best score so far).** Top 100 needs 25.354:
    - invsqrt a15b0d73 (alexchilton, v107): 22.1109, full official PASS.
    - dqi v100: 65.2263.
    - chem marculera: 11.2204.
  - v107 dqi 9fcda0c1 failed in 6 of 10 salts (6/1.024M shots, p about 5.9e-6), worse than v100.
    DQI candidates so far, by p:

    | DQI file | p |
    |---|---|
    | v100 | 2.9e-6 |
    | v104 | 3.8e-6 |
    | v95 | 4.2e-6 |
    | v107 | 5.9e-6 |

- 2026-11-11, DQI sprint (supervisor-approved):
  - **Generator.** Reviewed and pinned (briefs/dqi_generator_review.md), then run in a sandbox with no network, a
    read-only source, a cleared environment and caps.
    - Reproduced 7bd10fca byte-exact.
    - Official verifier, 3 fresh salts: PASS, mean T 403,503.
    - Gap to v100: 8,198 mean T.
  - **FIRST OWN VERIFIED IMPROVEMENT: DQI C1** (sha ca59beb8…), built by tools/dqi/splice/build_c1.sh, rebuild
    byte-exact. It is v100 with the generator's convert…unconvert block, joined by an exact affine CNOT bridge
    (rank 842).
    - mean T 393,390 (−1,914.5), Q 892.
    - Over 15 equal-budget salts (10 + 5 hold-out): C1 5 failures, v100 8.
    - p(C1) 3.5e-6 (CI 1.5–6.9e-6). E[ratio] 65.439, against 65.118 for v100.
  - Submitted mix5 (ref 58236986): C1 + invsqrt a15b0d73 + marculera chem.
    Local score 25.3347 if the public draw has 0 failures, 25.2960 if it has 1.

## Repo layout
- explainer/: the HTML explainer page, published as an artifact
- notebooks/: Kaggle notebooks we push (private by default)
- PLAN.md: reading guide and phased plan
- briefs/: three expert briefs plus three debate rebuttals
- tools/chem_cost_model/: Agent C's numpy reimplementation of the chemistry metric and costs (stress.py reproduces the public 11.199×). It was written against scratchpad paths; set the data paths before use.
