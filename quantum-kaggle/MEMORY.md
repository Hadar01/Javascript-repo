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
    **It scored 25.33469 (the 0-failure draw): rank 166 of 2,832, our best.** Top 100 now needs 25.405.
  - Width track closed within the tested routes; see dqi_profile.md §9:
    - the generator's ceiling knobs are already set to 891, and it still peaks at 892;
    - C1 has 487 moments at 892 qubits, 320 of which have no cheap fix.

- 2026-11-11, supervisor decision after the DQI sprint:
  - **Next sprint: invsqrt measurement-crossing search.**
    - Firm checkpoint after ONE focused day: either a fully costed transformation worth implementing, or a write-up of
      why the examined boundaries give no gain. A second day only if justified.
    - Target: ≥1% invsqrt cost at the same Q. That is about +0.335% overall, which would cross the reported 0.28% gap.
    - Base: public best invsqrt a15b0d73 (22.1109, cost 93,925.3).
  - **DQI scouting is a small side task.** Only an actual cheaper block with compatible inputs, outputs, workspace
    and phase counts as a lead; a new notebook alone is not.
  - **Merger outreach deferred** until a specific complementary team is identified.
  - Wording rules:
    - 5 vs 8 failures means "we have not demonstrated a difference". Attribute C1's gain to the gate reduction.
    - Width narrowing at ≥640 T is above the +400 target but below the ~886 break-even, so it is unattractive under
      that budget, not shown unprofitable. Archived.

- 2026-11-11 fusion sprint, day-1 checkpoint: outcome (B), no day 2.
  - Base a15b0d73 has 864 measurements.
    - Correction clusters (mean T): split pairs 36.5, block-boundary carries ~20, speculative chain ~10.4,
      unlookup chains 9, delay lines 8, un-normalisation 4.
  - 6 candidate classes were priced: keep-vs-recompute, deferring fix-ups, Clifford replacement, merging fix-ups,
    split-pair overhead, boundary fix-ups.
  - Every cheaper crossing found needs a qubit at ops where 62 are already live, or a non-Clifford phase on the
    reachable states.
  - A ≥1% gain would need a structural change that frees one qubit across ops 16.3k–22k.
  - This covers the examined boundaries only; it is not an impossibility result. Log: briefs/invsqrt_log.md.

- 2026-11-11 evening: **DQI C2** (sha 3152f1dd…) = C1 plus the extract/unextract blocks of public cd71c482 (team "i want to run gemma 9b").
  - Built by tools/dqi/splice/build_c2.sh. No bridge was needed: the boundary states are bit-identical.
  - mean T 392,453 (−936.6 vs C1), Q 892.
  - Census (1,048,576 shots): the same 3 failing seeds as C1. Stress sets w = 18–35 (172k shots): 0 failures.
  - Official sweeps, equal budget on Cx-00…14: C2 4 failures (all phase), C1 5. Not demonstrated different.
  - E[ratio]: C2 65.624, C1 65.449.
  - Submitted mix6 (ref 58249948): local score 25.3548 at k=0, 25.3161 at k=1. **It scored 25.35482 (k=0), our best score, but rank 300 of 2,862**, because the field moved: rank 150 needs 25.371 and top 100 needs 25.435.
  - Submitted mix7 (ref 58250494): C2 + v112 invsqrt 6c6a734d (22.1255, full PASS) + v112 chem 8d4c99a2 (11.2378). Local score 25.3735 at k=0. **It scored 25.37349: rank 145 of 2,864, best so far.** Top 100 needs 25.435 (+0.24%).
  - Public v112: invsqrt 6c6a734d (22.1255, full PASS); dqi cd71c482 (our C2 donor); chem 8d4c99a2 at 11.2378 (T 14,908), passes.
  - Fusion sprint ended at the day-1 checkpoint with outcome (B). Awaiting the supervisor's call on the
    one-qubit structural change.

- 2026-11-12, supervisor decision: **fusion one-qubit width sprint** (62→61 qubits), two checkpoints.
  - Base: v112 invsqrt 6c6a734d, C = 1513.9247 Tof-eq.
  - Budget, from 61(C+ΔC) < 62C:
    - any gain needs ΔC < 24.82;
    - ≥1% needs ΔC ≤ 9.43.
  - Must confirm the WHOLE circuit's width drops: every 62-qubit peak has to be fixed.
  - Checkpoint 1, feasibility (1 day). Checkpoint 2, implementation, only if a design survives the budget.
- DQI is lightweight. Reopen integration only when scouting finds a specific cheaper, compatible block; do not
  re-check the same lineages.
- C2 follow-up (DQI agent, 1 core): strengthen the splice-boundary PHASE argument.
  - C2's official failures were all phase errors.
  - Replay the failing shots, run the donor cd71c482 baseline on the same salts, and check for phase debt across the
    boundary.
- Wording rule: probabilities such as "~77% zero-failure draw" are sample-based estimates with uncertainty, not
  calibrated guarantees.

- 2026-11-12 fusion width sprint, checkpoint 1: **STOP** (no checkpoint 2).
  - v112 has 8,159 ops at 62 qubits, in 70 regions.
  - 6 regions (6,700 ops; the XAG lookup plus 5 table-only regions) cannot free a qubit without re-synthesising the
    table with one fewer live wire. That cost is not priced (perhaps ~3 ANDs per helper).
  - The other 64 regions need rematerialisations: at least 15 Toffolis optimistically, more realistically 23–31.
  - So ≥1% (≤9.43) is out of reach for the examined designs. Break-even (<24.82) holds only under optimistic pricing
    everywhere.
  - Max plausible net is about 0.3% fusion, about 0.1% overall. Not pursued.

- 2026-11-12 supervisor decision:
  - **Fusion is CLOSED for now**: 5 negative bounded searches. Reopen only for a specific new mechanism. Do not fund
    the table rebuild.
  - Order of work: (1) finish the C2 phase-boundary check; (2) one focused chemistry feasibility day.
  - Chemistry day rules:
    - Confirm the current baseline from our SUBMITTED chem files (v112 8d4c99a2, 11.2378, T 14,908). Catching up
      to the public compiler adds no score.
    - Pin one representative loader: table, circuit, helper state, width, full forward/reverse cost.
    - Reproduce its existing decomposition, with attribution.
    - Test ONE cross-output shared-product search, with workspace and uncompute constraints.
    - Score the complete emitted circuit.
    - Keep the table and weights fixed.
    - Continue only with a verified cheaper loader, or a concrete costed route to one.
  - Milestone: one loader that beats the corresponding circuit in our current submission, verified in the full
    chemistry pipeline.
- **The agents hit the WEEKLY usage limit (resets Nov 16, 22:00 UTC).** Until then I work directly.

- 2026-11-15 **PUBLIC FRONTIER JUMP.**
  - Board: #1 30.285, top 100 at 28.060 (a plateau of about 1,000 teams). We had dropped to rank 1,162 (25.37349).
  - New public pieces, all verified locally with the unchanged verifiers:
    - invsqrt **44 qubits** (syed3000 v14), 27.6277. With jeffemerson's AND-merge patch (sha 9339eecc), 27.6599;
      rebuilt here from the published diff, hash matched.
    - dqi **890 qubits** (syed v13 + hayatohikawa/areebbb product retention, 4b350932), 70.2767, 0/0 on salt team-f-a.
    - chem hayatohikawa (7e6e65d7), 11.3840.
    - Other candidates: v119 a4d46b17 invsqrt 46q 26.3974; v119 821bf8d1 dqi 889q 67.8479; syed dqi 69.93 (1 error);
      syed chem 11.3578; marculera v6 chem 11.3826.
  - Submitted:
    - mix8 (ref 58401421): hayatohikawa portfolio, local score 28.0640;
    - mix9 (ref 58401561): AND-merge invsqrt + hayatohikawa dqi and chem, local score 28.0749.
  - **Scored: mix8 28.06404; mix9 28.07494, which is rank 64 of 3,124, our best rank so far.**
    Thresholds: rank 50 at 28.075, top 26 (1%) at 28.208, #10 at 28.899, #1 at 30.285.
  - **Our C1/C2 DQI work (65.70×) is now obsolete:** the public 890-qubit decoder is at 70.28×.
  - Agents return after Nov 16 22:00 UTC (weekly limit).
  - NEXT: profile the new 890-qubit DQI and the 44-qubit invsqrt with our tools, and look for splice-able cheaper
    blocks (same method as C1/C2).

- 2026-11-17 supervisor decision: restore an independently verified advantage over the public mix.
  - **DQI (primary).** Compare stage costs, representations and workspace across:
    - the 890-qubit baseline (4b350932);
    - the 889-qubit alternative (821bf8d1);
    - syed v13 (46446af1);
    - C2.
    Continue only if a specific replacement improves the TOTAL R(ε+)Q²T, including conversion and cleanup.
    - C2's conversion block gets no special preference. First check whether the new decoder already includes an
      equivalent.
    - Compare mean executed gates AND failure behaviour.
    - 890→889 at the same T is worth only about 0.225%.
  - **Fusion (secondary).** First explain HOW the 44-qubit architecture got there (fewer stored table outputs,
    different arithmetic, more recomputation, …), then measure its bottlenecks. Do not restart the old one-qubit search.
  - Checkpoint 1, one focused workday: a comparison table and at most 2 candidates, each with a full cost estimate and
    a boundary-correctness argument.
  - Checkpoint 2: build the strongest candidate, then validate value, phase and cleanup, then compare against the pinned
    baseline at equal budget plus a fresh hold-out.
  - Target: 28.208 needs about 1.41% lower cost on one task. Keep smaller verified gains too.
  - Pinned baselines:
    - invsqrt 9339eecc (jeff AND-merge on syed v14, 27.6599, 44 qubits);
    - dqi 4b350932 (70.2767, 890 qubits);
    - chem 7e6e65d7 (11.3840).
    - Board: 28.07494, rank 64.

- 2026-11-17 **DQI checkpoint 1 (Agent B), dqi_profile.md §12. Nothing submitted or committed.**
  - Mean T on the same 4,096 shots: h890 4b350932 368,547.5; sy13 46446af1 368,699.5; v119 821bf8d1 382,599.8;
    C2 392,454.7.
  - Q²T against h890: sy13 +0.04%, v119 +3.58%, C2 +6.97%.
  - h890: 0 failures on 57,344 official-sampler shots plus 4,096 weight-35 shots.
  - **h890 is not a v100/C2 descendant.** It is syed's own line with the same skeleton. Against C2: extraction
    −17.4k, synthesis −6.8k, conversion +0.4k, scan equal.
  - v13 against v12: the +1 qubit makes the extractor partly in place (34% of its CCX target the head words, against
    0%). That saves −14.0k T.
  - Retention post-pass: exactly −152 T.
  - Internal boundary states share no GF(2) span across C2 / v12 / v13, so no splices are possible.
  - **No candidate clears the bar:**
    - retention headroom is ~0 after cross-checking;
    - never-active-on-sample Toffolis are rare branches active on 0.48% of fresh shots (selection bias);
    - 890→889 would need to remove 1,265 excursions.
  - The remaining levers are research items: synthesis reverse P-restoration (+9.2k excess), GF(2^24) rank below 99,
    and the rare-branch layout (~15k static).

- 2026-11-17 checkpoint 1 results. **Both NEGATIVE; no checkpoint-2 build.**
  - **DQI** (dqi_profile.md §12):
    - h890 4b350932 is syed's own line. Its extra qubit lets extraction run in place (−14k T); product retention
      adds −152 T.
    - Five routes fail: C2 conversion splice (incompatible representations, needs non-linear converters),
      more retention (not robust), pruning unfired Toffolis (rare-case branches, ~500 failures/run),
      CCX→CX identities (break on 0.9%), 889 qubits (1,265 excursions, ≤0.225%).
    - Research leads: reverse passes cost +17.5k T, mostly a per-node division restoring a measured 24-bit word.
  - **Fusion** (invsqrt_log.md):
    - 62→44 qubits by trading the 8-bit XAG table + Horner polynomial for an in-place integer sqrt, a 13-bit
      64-row table, a multiplier and a restoring division. C +12.7%, Q −29%.
    - Candidates:
      - 43 qubits: the information fits, but the cover costs about 16–30 Tof-eq, at best break-even.
      - Uncompute premiums: 0 hits.
    - Lead: hide a third root bit (as syed does for v10/v11) with cubic or table rebuild formulas. Untested.

- 2026-11-18: the frontier moved again. Board: top 100 28.190, #26 28.452, #1 31.617; we had fallen to rank 926.
  - Public 28.19 set from junmiaotiao/qcc-frontier-20261118w, verified locally:
    - invsqrt 864f81cd (maoxin, 44 qubits): 27.8795.
    - dqi 5f901c55 (boristown PW4 patch, 890 qubits): 70.23 with 1 value error on salt team-w-a; 70.55 if clean.
      The board draw for these bytes was clean.
    - chem 4d63be3d (maoxin 4,022 T/pass loaders + leotang09 refit): 11.3887.
  - Submitted mix10 (ref 58498405): **scored 28.18965, rank 168 of 3,301**. Top 100 is 28.18976 (0.0001 above us); rank 50 is 28.240; #26 is 28.452.

- 2026-11-18 supervisor decision:
  - **One bounded DQI sprint on the reverse-pass overhead** (+17.5k T on h890).
  - Checkpoint 1 is EXPLANATION, not implementation. For each reverse stage, record:
    - its forward counterpart and the mean-T difference;
    - what the forward pass destroys or measures;
    - which reverse ops reconstruct, clear or repair phase;
    - alternatives, with qubits and full cost.
  - Then choose ONE transformation. Implement it only with a correctness argument and a favourable cost.
  - Stop after one focused day if there is no mechanism.
  - Gains at fixed Q and failure rate:

    | Overhead removed | Gates | Score |
    |---|---|---|
    | 25% | 4,375 | 28.302 |
    | 50% | 8,750 | 28.416 |
    | 100% | 17,500 | 28.650 |

    The top 1% (28.452) needs about 10.1k T, about 58% of the overhead.
  - If checkpoint 1 is negative, go back to maintenance until there is new evidence.
  - Third-root-bit fusion is DEFERRED until a reconstruction formula with a full cost exists.
  - **Final-selection analysis: start now, choose later.**
    - Check whether the salt changes mean T and measurement branches, not only failures.
    - Measure failure OVERLAP between candidates on a shared diagnostic corpus, plus the unchanged verifier.
    - Rank by estimated final-score distributions, separating gate savings, error frequency and shared failure
      modes.
    - A clean public draw is one observation.

- 2026-11-18 **DQI reverse-overhead checkpoint 1 (Agent B), dqi_profile.md §13. NEGATIVE: no profitable
  transformation found within the examined alternatives (not a global lower bound); stopped per the decision rule.** Nothing submitted or committed.
  - **Measured on 5f901c55:** mean T 367,110.7, 0/0 on 8,192 shots. Asymmetry +16.5k: synthesis +8.66k,
    conversion +4.42k, extraction +3.44k.
  - **About 2/3 is value reconstruction:** one GF(2^24) division "closing" per in-place multiply-and-measure pair
    (34 synthesis + ~13 conversion), each at ≈ 330 T, within ~5% of our ESTIMATED floor for this construction (not a proven bound).
  - **About 1/3 is phase repair** (extraction 3.3k, conversion 1.8k) of measurements made inside the reverse's own
    inversions:
    - forward debts are repaid at 0 T;
    - none of the 130 repair clusters' values reappears linearly in any later state.
  - **The only removable redundancy** is 2.2k T of norm re-initialisation (erase then recompute). Every such window
    runs at 889–890 qubits, so keeping the norms costs +6/+12 qubits: net −0.7% to −2.1%.
  - Conversion also holds ~8.5k T per direction of symmetric "temporary in-place update" recomputation, which would
    need hundreds of extra qubits to avoid.
  - Remaining levers are research:
    - a GF(2^24) division below ~300 T;
    - a width-neutral rewrite of the remaining re-init sites, ≤ 0.17%.

- 2026-11-18 supervisor decision: **stay on light maintenance.**
  - Provisional slot 1 is DQI 5f901c55. Slot 2 is NOT locked; 4b350932 is the backup.
  - Reopen research only for a new circuit, formula or measured bottleneck, not because the rank moved.
  - Selection model revised (briefs/final_selection.md):
    - shared-rate and separate-rate scenarios;
    - census inputs counted once in shared pooling;
    - Jeffreys propagation of the rate;
    - OVERALL-score expectations with credible intervals, kept separate from future-draw quantiles;
    - the pair adds +0.0013 to +0.0027 overall in every scenario.
  - Wording rules:
    - 7/7 cross-replay = shared failures on those 7 inputs, NOT identical failure sets;
    - Fisher p = 0.45 means not demonstrated, NOT proven noise;
    - independence of different-hash draws is a modelling assumption.

- 2026-11-19 **Selection CLOSED for these two candidates** (supervisor):
  - Slot 1 (provisional): DQI 5f901c55 + invsqrt 864f81cd + chem 4d63be3d.
  - Slot-2 fallback: DQI 4b350932.
  - No further analysis cycle for these files. Reopen only for a materially better candidate.
  - Evidence rules:
    - official-only scenarios are the PRIMARY evidence; census-inclusive runs are sensitivity checks;
    - prior Jeffreys Beta(1/2, 1/2);
    - MC with 20,000 posterior draws, seed 11; MC s.e. of the pair gain ≤ 1e-5;
    - wording: "All 2,252,800 official inputs were distinct. We model the official draws as independent under the
      verifier's pseudorandom sampling assumptions."
  - Artifacts and diagnostics are pinned in quantum-kaggle/PINS.md and tools/dqi/finalsel/.
  - Mode: LIGHT MAINTENANCE.

- 2026-11-19 (evening) **Selection REOPENED: a materially better public set appeared.**
  - Public board moved: we fell to rank 705 (28.18965 shared by 43 teams). Top 100 at 28.23945, rank 26 at 28.593,
    #1 31.740; 3,399 teams.
  - Frontier public set (goodpjw2008 / ozertuu notebooks):
    - invsqrt `acc7b9c8`: 74,361.78, ratio 27.92798, 44 qubits, worst error 0.99946 of tolerance;
    - DQI `f56b04c7`: 4471b493 plus 2 swap-collapse sites, −24 Toffolis/shot, T 365,848, zero-failure ratio 70.795;
    - chemistry npz `6ef06081`: ratio 11.388728, essentially the same as ours; same 15 loaders.
  - Local unmodified verifier, salt nov19-a: all PASS. DQI drew K=1 there; GM at K=0 is 28.2384.
  - Submitted as mix11 (ref 58572455).
  - goodpjw2008 reports 6 failures / 1,638,400 shots for f56b04c7, same rate class as 5f901c55.
  - Kernel outputs (www.kaggleusercontent.com) are blocked by the proxy; get files from datasets instead.
  - **mix11 scored 28.23837 public, exactly as predicted; rank 123 of 3,402** (106 above, 18 tied). Top 100 is at
    28.23945.
  - Official Fsel-00…09 sweeps:
    - f56b04c7: 4 / 1,024,000, T 365,848.04;
    - 4471b493: 4 / 1,024,000, T 365,871.96.
  - Model (tools/dqi/finalsel/model_output_2026-11-19_frontier.txt):
    - best pair f56b04c7 + 4471b493, E[max] 28.232;
    - gain over the best single +0.009 to +0.012;
    - it beats f56b04c7 + 5f901c55 (+0.005 to +0.007).
  - Slot-2 hedge mix12 (ref 58573441) = mix11 with DQI 4471b493: public 28.23775, a K=0 draw.
  - Provisional pair: mix11 + mix12, pending supervisor review. The brief is final_selection.md §5.
  - Proposed to the supervisor: a bounded DQI product-retention scan (identical products with a free qubit across the
    interval). About 42 Toffolis/shot are needed for the top 100. Awaiting a decision.
  - Levers to reach the top 100 (+0.00106 GM):
    - 1 invsqrt Toffoli per input ≈ +0.0056 GM;
    - 24 DQI Toffolis per shot ≈ +0.0006 GM.

- 2026-11-22 **DQI product-retention scan (funded for one day): STOPPED at checkpoint 1, net saving 0.**
  - Brief: briefs/dqi_retention_scan.md. Tool: tools/dqi/retain_scan.cc.
  - Funnel:
    - 164,185 identical-product pairs (131,933 consecutive);
    - 131,411 with the same factors;
    - width-feasible at Q=890: 11 with certain-zero wires, 121 with sample-zero wires;
    - after the 17-set stress validation (278,528 shots, including weights 32–35): 110;
    - jointly ≤ 4, because of capacity-1 bottlenecks;
    - the bottleneck wire q889 holds a rare AND flag → 0.
  - Extra width does not pay: Q=891 gives ≤ 116 Toffolis/shot against ≈ 823 cost.
  - Side classes excluded:
    - "product equals one factor" downgrades are zero-test chain tails;
    - never-firing gates.
    - For both, the break-even needs q < 6e-9 per shot; only a proof could show that, and sampling cannot.
  - Invsqrt angle wording corrected to "tested refit found no improvement" (supervisor, 2026-11-22).
  - Provisional pair still mix11 + mix12. Back to light maintenance.

- 2026-11-24 **Frontier jumped to 33.17; we were rank 1,221.** Reproduced the public 33.17 portfolio with the
  unmodified verifiers (brief: briefs/frontier_33_17.md):
  - invsqrt bb676b95: 37 qubits, 60,927.6, ratio 34.086; +22.1% vs mix11.
  - DQI a931fcfe / dbb2ada3: 900 qubits, about 316,130 T, ratio about 80.12 at K=0; +13.2%.
  - chemistry: 405 qubits, T 13,214, ratio 13.364; +17.3%.
  - GM at K=0: 33.170.
  - Submitted mix18 (ref 58818853: bb676b95 + a931fcfe + chemistry 17a76582) and mix19 (ref 58818871: with DQI
    dbb2ada3).
  - The 900-qubit DQI line fails about once per run, and carries approximate expected-value rewrites (goodpjw2008,
    Atakan). Allowing that class is a policy question for the supervisor.
  - Folded-residual invsqrt idea priced (briefs/fusion_folded_pricing.md): it LOSES even at the most generous lower
    bound (Q=51, lookup + rotations only: +5.6%). The 1,024-row lookup consumed the advantage through width (≥ 29-bit
    word) plus about 1,023 Toffolis at narrow width. Closed.
  - New standing rule (supervisor): a negative result closes that experiment only. Keep the public submission
    competitive and keep one structural idea under active investigation.

## Repo layout
- explainer/: the HTML explainer page, published as an artifact
- notebooks/: Kaggle notebooks we push (private by default)
- PINS.md: sha256 pins of the current submission's files and the selection candidates
- PLAN.md: reading guide and phased plan
- briefs/: three expert briefs plus three debate rebuttals
- tools/chem_cost_model/: Agent C's numpy reimplementation of the chemistry metric and costs (stress.py reproduces the public 11.199×). It was written against scratchpad paths; set the data paths before use.
