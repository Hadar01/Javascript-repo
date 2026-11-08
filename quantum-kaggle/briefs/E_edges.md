# E — Edge-Finder brief (2026-11-08)

Our position: baseline submitted. It passed all three verifiers under our own salt: invsqrt 21.7479, dqi 65.2181,
dfthcsos 11.1979, geometric mean 25.137. Leaderboard: #1 29.301, #10 27.03, #26 26.25, plateau ≈ 25.09–25.14.
To reach #1 the product of the three ratios must grow ×1.58. Each 1% cut in one task's cost adds about +0.33% to the GM.

**Labels used throughout:**
- **[V]** verified by me from a primary source (file, API response, host post).
- **[I]** inference.
- **[U]** unverified claim from a third party.

Raw material is in the scratchpad (`…/scratchpad/E/`):
- `dl/forum_all.txt`: all 82 forum topics with every comment, author type marked HOST/ADMIN.
- `nb/*.txt`: 22 recent notebooks.
- `dl/sd1/`: the kickmix 1.0.0 sdist source.
- `dl/qualtran/`: Qualtran GF bloqs and kickmix docs.
- `dl/gu/`: the Gu et al. repo files.

---

## 1. Top 10 edges, ranked by expected score impact × probability

The "Expected GM" column is my estimate of impact × probability. It is [I] throughout.

| # | Edge | Expected GM | Confidence |
|---|---|---|---|
| 1 | Team merger to combine best-per-task circuits | +3–8% | medium |
| 2 | Re-open invsqrt: the leaders think it is far from saturated | +2–5% | low–medium |
| 3 | Reuse Gu et al.'s Apache-2.0 repo (profiler, DQI and QROM techniques) | +1–3% | medium–high |
| 4 | Private-split robustness (DQI expected cost, chemistry numeric margins, two different DQI files) | protects 0.2–0.5%; avoids a 0 | high |
| 5 | XOR-aware SAT and XAG multiplicative-complexity tools for loaders and tables | +1.5–3% | medium |
| 6 | GF(2^12) multiplier below 42 ANDs via GF(2)-bilinear or *quadratic* (non-bilinear) algorithms | +0.7% per AND saved | low (10–20%) |
| 7 | A fast evaluation loop (kickmix-engine, cost-only simulation, OpenEvolve) as a force multiplier | indirect, about ×1.5 on iterations | high |
| 8 | Single-task $10k prize as a rank-independent target (chemistry or invsqrt) | $ EV, not score | medium |
| 9 | Mid-competition prize (Nov 20) publish-or-not decision | $ EV, with a trade-off | low |
| 10 | Prize compliance as a moat: own generators, licence lineage, identity verification | protects prizes | high |

### Edge 1 — Team merger to combine best-per-task circuits (GM +3–8%, P ≈ 0.4)

**Evidence:**
- [V] The score is the geometric mean of independent per-task ratios. A merged team keeps the best circuit for each task.
- [V] Rules B.1(b) and C.5(c) allow merges if the combined submission count is ≤ 5 × days elapsed. That cap is about 85 now and about 415 at the merge deadline.
- [V] The merge deadline is 2027-01-13 23:59 UTC (API field `teamMergerExplicitDeadline`). Maximum team size is 5.
- [V] Private code sharing before a merge is forbidden (C.5(d), C.6(a)). Public outreach is fine.
- [V] Several strong specialists sit at ranks 10–40, or are public authors with their own unpublished improvements:
  - 田村さんを囲む会 (#12): includes xolotlmictlan, who wrote the finite-field complexity proofs.
  - iwanttorungemma9b: chemistry loaders −1.66% versus the public frontier, published 11-05.
  - Syed Asad Ali (syed3000): author of the invsqrt line and the C44 chemistry.
  - Atakan Aldemir: affine product-reuse scanner.
  - Ahmed Berat Özer: the 892-qubit DQI.
  - manwithacat: RezOps tooling and the Rust verifier.

**Why it beats solo work [I].** Teams near the top (#7 CroDoc & Pavel, #8 "Thinking…" with 4 members, #1 with 3) are already merged. A partner who is 15% ahead on one task, merged with us 15% ahead on another, gives +10% GM immediately.

**Next action.**
1. Build a per-task profile of candidate teams from their public notebooks, their forum per-task posts (topic 752550) and their LB score history.
2. Approach two or three of them in the forum (Team Up) **before** we have a lead to protect. Merging gets costlier in submissions-used and in bargaining later.
3. Decide by about 2026-12-15, well before 01-13.

### Edge 2 — invsqrt is probably not saturated; the leaders think so too (GM +2–5%, P ≈ 0.35)

**Evidence:**
- [V] pjmathematician (#2, 29.18), 2026-11-07, topic 756863: hit a wall on DQI, has been "enjoying invsqrt the most now… the gains here are still relevant for the GM".
- [V] James Day (#1 team) posted his LLM's ceiling estimate, topic 753404 (screenshot checked): **invsqrt 40–45×, DQI 200–250×, chemistry 18–20×**. That is an LLM guess, not data, but it shows where #1 is looking.
- Our brief A calls invsqrt near-saturated at about 22×. The two views disagree.
- [V] Gu et al.'s Apache-2.0 `coulomb-potential` circuit (spec differs: the distance is computed in-circuit, and output goes to a register at 2^24 scale) uses a different architecture:
  - normalise onto one mantissa interval;
  - **128 quantized lines** looked up by (parity(e), 6 mantissa bits);
  - a 6-bit local coordinate, so multiplication becomes **6 conditional additions**;
  - **measurement-based unlookup with a 17-Toffoli phase repair**;
  - lines **fitted backward from the final output tolerance through the exact rounding pipeline**, accepting a line only if every input lands in band.

  The last point removes separate error budgets for lookup, truncation, multiplication and rounding. Source: `andigu/uncompute/tasks/coulomb-potential/circuits/discovered/README.md`.
- [I] The public invsqrt (62 q, quadratic Horner, error budget 0.9993 used) spends its slack per stage. A single end-to-end exact fit, with rotation count and bit widths co-designed, could free bits, qubits and rotations together.

**Next action.** In week 1, prototype a Gu-style "many lines + exact backward fit" invsqrt generator on the official contract (phase within 2^-24/√x turns, cost Q·(Tof+T/4)). Sweep the number of segments against qubits. Kill it if the model cannot beat 95.5k cost by ≥ 3%.

### Edge 3 — Gu et al. (arXiv:2610.22367) Apache-2.0 repo: tools and techniques (GM +1–3%, P ≈ 0.6)

**Evidence [V].** `github.com/andigu/uncompute` (fetched via raw.githubusercontent; LICENSE is Apache-2.0):
- **Tools:** `tools/liveness_profile.py` and `tools/occupancy_profile.py`. A live-qubit and occupancy profiler is exactly the "#1 missing tool" in our PLAN. The repo's op-stream format differs from kickmix, so it needs an adapter.
- **DQI stage profile of a sibling decoder** (442,397 T, 1,837 q):

  | Stage | Share of T |
  |---|---|
  | bm | 31.9% |
  | sweep (4,024 points × **23 Tof**, versus 80 with a per-point division) | 20.9% |
  | reverse | 19.5% |
  | two Euclidean passes | 20.2% |
  | omega | 6.8% |

  Further tricks in that decoder:
  - Ψ = 1/σ′ mod σ computed once;
  - interpolation moves the syndrome-linear part onto Z gates and drops 71 points;
  - conditional swaps share the retain/replace arithmetic;
  - syndrome words are reused as workspace.

  Some of this was already ported to public lines (manwithacat cites "truncated BM, contracted Forney, Ψ" ports). **Diff our 892-q decoder stage by stage against this table.** Any stage above Gu's per-unit cost is a target.
- **Chemistry QROM (`chemistry-fe2s2`):**
  - "repeated-span pruning" cut an alias-table traversal from 41,050 to 10,271 Toffolis, by choosing an *equivalent alias schedule whose nearby words repeat*;
  - frame blocking of Pauli masks.

  This is data co-design for lookup cost, the same idea as our "soft words" and rounding for the loaders.
- **Lean proofs** of the DQI decoder-error bound. These would be useful if hosts tighten the correctness scope.

**Next action.**
1. Clone the repo (read-only; run only our own adapters).
2. Port the liveness profiler to `.kmb`.
3. Produce the 892-q stage table.
4. Read the chemistry-fe2s2 pruning code for ideas on ANGLE_k word ordering.
5. Attribute under Apache-2.0.

### Edge 4 — Private-split robustness (protects 0.2–0.5% and avoids a catastrophic 0)

**Evidence [V].**
- Metric notebook: "each leaderboard split seeds the simulations with its own secret salt, so every benchmark is verified once per split". All splits are verified before either is scored. A failure on the private split therefore shows up as a submission error, not as a silent private-only zero.
- DQI failures are deterministic per input. A circuit with rare failures redraws them on the private salt.
  - manwithacat (topic 753424): the 877- and 889-qubit decoders drew zero failures only about ⅓ of the time.
  - prvsiyan: two final picks should carry different DQI bytes.
- **Chemistry margins in public files are about 2.4e-10 Ha** on E_gap, and error_1/2 = 19.99999977 mHa (prvsiyan notebook). The hosts also announced they will migrate the metric to the PyPI kickmix. A numpy, BLAS or platform change could flip a 1e-10 margin and reject the submission.

**Next action.**
1. For DQI, rank candidates by **expected** cost over ≥ 8 salts, preferring 0-failure designs.
2. Rebuild chemistry weights with a margin of ≥ 1e-7 Ha / 1e-6 mHa. The cost of that margin is negligible.
3. Re-verify every final candidate under both the dataset `kickmix.so` and the PyPI `kickmix==1.0.0` wheel. The sdist is identical to 0.1.dev0 except the version string.
4. Final picks: A = best expected; B = a different DQI file and/or extra margin.

### Edge 5 — XOR-aware SAT and XAG multiplicative-complexity tools (GM +1.5–3%, P ≈ 0.4)

The chemistry loaders are 8.3k of about 15k Toffolis. invsqrt's 169-AND table decode and the DQI glue are the same problem: minimise ANDs given free XORs. That is the multiplicative complexity of XOR-AND graphs (XAGs).

**Tools (PyPI-checked [V]):**
- `pycryptosat` 5.17 (CryptoMiniSat with **native XOR clauses and Gauss-Jordan**: ideal for GF(2) synthesis);
- `python-sat` 1.9;
- `z3-solver` 5.3;
- `cvc5` 1.4;
- `ortools` 9.15;
- `galois` 0.4.11 (GF(2^m) arithmetic);
- `cirkit` 3.0a2 (Soeken's logic-synthesis framework);
- `yowasp-yosys` (yosys plus ABC as wasm).

**Not on PyPI:** EPFL `mockturtle` (C++, GitHub `lsils/mockturtle`; it has XAG MC-optimal resynthesis with the Calik–Peralta ≤ 6-input databases). **Warning: the PyPI package named `mockturtle` is an unrelated project. Do not install it.**

**Caveat [V].** alexchilton's nulls: the public loader sits on the 262-product GF(2) rank bound, and its output ANF matrices have full rank like random ones. Gains therefore have to come from **changing the data**: loader-aware rounding, alias/word reordering as in Gu, or the row budget. Re-synthesising fixed data will not do it. The one data point so far is iwanttorungemma9b: −3% loader Toffolis from "soft words".

**Next action.** Build a CMS-XOR-based exact synthesiser for windows of ≤ 6–8 inputs. Wire it into a loop that co-optimises rounding and AND count under the 20 mHa gate.

### Edge 6 — GF(2^12) multiplier below 42 ANDs (each AND ≈ −2% DQI cost ≈ +0.7% GM; P ≈ 0.1–0.2)

**What is known [V]:**
- kickmix's own `gen_gf_mul` is in-place Karatsuba: 2·K(⌈n/2⌉)+K(⌊n/2⌋) gives **63 ANDs** at m = 12. Its `del_gf2_mul` and `gf2_phase_by_product` cost 0 Toffolis (HMR plus CZ).
- Qualtran's bloqs offer only Karatsuba, a schoolbook n² multiplier and Itoh–Tsujii inversion. **The organizers' public code is behind the public 42.**
- Forum topic 756476:
  - 42 = 3 × 14 is the GF(4)-tower route;
  - μ₄(6) = 14 is now **proven optimal** for GF(4)-bilinear algorithms, by 田村 and by pjmathematician (#2);
  - Dyst-0 has Lean proofs at `github.com/Dyst-0/mu4-lean-proofs`.

**Still open [I]:**
- (a) direct GF(2)-bilinear rank of GF(2^12) multiplication below 42;
- (b) **quadratic (non-bilinear) algorithms.** A Toffoli can AND two parities that each mix bits of *both* operands, so the relevant measure is the multiplicative complexity of the quadratic map. It is ≤ bilinear rank and ≥ rank/2.

The #2 team clearly searched (a) through GF(4). Whether anyone searched (b) is unknown. The DQI context also allows products where only the phase is needed (free) and fused multiply-accumulate forms (Σ a_i·b_i with a shared accumulator).

**Next action.** Run a background SAT/flip-graph job for quadratic schemes of rank ≤ 41, and for fused 2-product MACs of rank < 84. Check our B brief's multiplier-use census first.

### Edge 7 — The evaluation loop is the force multiplier (indirect, high probability)

**Evidence:**
- [V] Tony Li (#1 team) named "Token, Validation Speed, and Scoring Timeout" as the challenges.
- [V] Zero: "relying on Google's full official validator for every iteration is too slow".
- Available tools:
  - manwithacat's Rust `kickmix-engine` (Apache-2.0; claims a fraction of the time and memory) [U];
  - the kickmix sdist (C++, buildable with AVX/NEON);
  - Qualtran issue #1987: the Kaggle DQI metric can run out of memory on large circuits, a scoring-failure risk;
  - `openevolve` 0.4.1 on PyPI (open AlphaEvolve).

**Next action.**
- Three-tier evaluation:
  1. exact Toffoli and Q from one cost-only simulation;
  2. a correctness subset of about 1% of shots;
  3. the full official verifier only for candidates that improve.
- Run LLM-evolution loops with tier-1 cost as the reward and tier-2 as the gate.
- We may build kickmix from the PyPI sdist ourselves (our own build of public source). We still never execute the dataset `.so` locally without permission.

### Edge 8 — Single-task $10k prizes are rank-independent (dollar EV)

**[V] Prizes page:** "for each of the three tasks, the selected submission with the best score for that specific task". Only *selected* final submissions count, and the private salt is used.

**[I]** Chemistry is everyone's bottleneck (Jack: "dfthcsos, dfthcsos, and dfthcsos"), and it has no salt variance. If our row-budget or loader work lands (14×+), the chemistry prize may be winnable even at an overall rank around 20.

**Next action.** Track our per-task numbers separately. Make sure one of our two finals carries our best chemistry.

### Edge 9 — Mid-competition prize, 2026-11-20 (dollar EV; strategic trade-off)

**[V] Timeline:** "The team with the highest public leaderboard score at this deadline wins, provided its notebook is public." It is unclear whether the prize passes to the best team *with* a public notebook if the leaders keep theirs private.

**[V] The leaders sandbag.** pjmathematician: "Breaking1800 only submits immediately when someone … overtakes … always keeping a better local solution ready". So the leaders' private best is above 29.3.

**[I]** Publishing would hand our work to 2,600 teams 2 months before the end. It is worth it only if we would clearly be the top *publishing* team. Low probability at our current 25.14.

**Next action.** Ask the hosts publicly to clarify the fallback. Decide on 11-18.

### Edge 10 — Prize compliance as a moat (protects all prizes)

**Host statements [V]:**
- Khattar (topic 752010): "a circuit generator that produces the exact circuits must be provided. The requirement applies for all benchmarks and all prizes."
- The jday96314 DQI lineage has no licence. James Day (#1) said he will relicense it under Apache-2.0 "if the hosts are concerned or I rank in gold".
- Byte-patched public binaries without generators carry real winner-verification risk (ADMIN, same topic).
- The competition `requiresIdentityVerification: true` (API) [V].

**Next action.**
- Every circuit we submit must have our own generator that reproduces it byte-for-byte.
- Pin and credit Apache-2.0 inputs.
- Have every member complete Kaggle identity verification now.

---

## 2. Organizers' public code

**Qualtran commits [V]** (WebFetch of github.com/quantumlib/Qualtran/commits/main, PR and issue lists):
- 16 kickmix commits between Sep 30 and Oct 22, mostly by Strilanc (Gidney) and Khattar: API polish, CSWAP and INFO_TAG instructions, ChaCha RNG, wheel CI.
- **No DQI, Reed–Solomon, invsqrt or THC circuits have been released.** The only THC item is `SelectTHC` (Aug 31).
- Since Oct 22 there are no new kickmix commits.
- Open items:
  - #1987: the DQI metric can run out of memory on large circuits;
  - #1993 and PR #1994: manwithacat's reaction_depth streaming;
  - #2001 and #2002: spam-like "ParabolicPosetQROM" and DQI PRs, now closed.

**kickmix on PyPI [V].**
- 0.1.dev0 and 1.0.0 were released 2026-10-27; there are wheels for Linux, Mac and Windows on Python 3.10–3.14.
- The sdist is the **full C++ source** (36.7k lines), identical between versions apart from the version string.
- The hosts say the metric will migrate to the PyPI copy (data page and topic 753307).

**Useful library primitives in kickmix [V]:**
- `init/del_gf2_mul` (del costs 0 Toffolis);
- `gf2_phase_by_product` (0 Toffolis, 0 ancillas);
- `init_gf2_inverse[_with_scaffold]`: Itoh–Tsujii, where keeping the intermediates makes uncomputation free;
- `init/del_lookup`;
- `unary_iteration`;
- `flip_if_*` comparators;
- `iadd` and `isub`.

**Cost semantics [V]** (`operation_statistics.pybind.cc`): Toffoli-like = CCX, CCZ and CSWAP. The instruction set has no macro-instructions, so there is no cost-accounting surface to game. Q is the high-water qubit index + 1.

**Organizers' better circuits [V].**
- The paper (§III and footnote 2) commits to SHA-256 hashes of internal runs:
  - Benchmark I: `4b98f38a…`
  - Benchmark II: `0701f553…`
  - Benchmark III: `9b8d070f…`
- They will be released at the end. The paper says "all three benchmarks can be further improved beyond the circuits reported to date".
- Babbush gave a recorded KITP talk on these benchmarks ([33]). It is public and worth watching for design hints (not reached).
- Khattar et al. arXiv:2510.10967 claims 5.72M Toffolis. That is the competition *reference*, and the public is already about 14× below it.

**Reference implementations in Qualtran bloqs [V]:**
- `GF2MulViaKaratsuba` (n^log2 3);
- `GF2Multiplication` (schoolbook, n² Toffolis);
- `GF2MulK`;
- `GF2Inverse` (Itoh–Tsujii);
- `gf_poly_arithmetic` (add / split / join only).

There are no RS decoder, invsqrt or QROAM-over-THC test vectors beyond what is in the competition data.

---

## 3. Top-competitor intelligence

**Leaderboard leader history** [V, from manwithacat's RezOps briefings, which record observed LB snapshots]:

| Date (UTC) | Top score | Leader | Public plateau |
|---|---|---|---|
| Oct 26 | 23.35 | | |
| Oct 27 | 24.53 | Breaking1800 | ≈ 21.5 |
| Oct 28 | 26.14 | Breaking1800 | 22.70 |
| Oct 30 04:23 | 26.76 | Breaking1800 | 23.14 |
| Nov 1 02:49 | 27.16 | Breaking1800 | |
| Nov 1 21:05 | 27.996 | Breaking1800 | |
| Nov 2 ~20:30 | 28.83 | James & Geremie & Tony | |
| Nov 5 01:24 | 29.06 | James & Geremie & Tony | |
| Nov 6 00:25 | 29.30 | James & Geremie & Tony | 24.94 |
| Nov 8 | 29.30 | James & Geremie & Tony | 25.14 |

- **[I] The top-to-public gap is stable at about 15–17%.** The public creeps up about 0.5–1%/day by copying and patching. The leaders keep a hidden buffer.
- **[I] Longest Leader time so far:** Breaking1800 about 6.6 days, the James team about 5.5 days.

**Top 10 (2026-11-08 snapshot) and what is public about them [V unless marked]:**

| Rank | Team | Score | Public signal |
|---|---|---|---|
| 1 | James & Geremie & Tony (jsday96, yeoyunsianggeremie, tonylica) | 29.30 | James Day wrote the **continued-fraction/Schur DQI decoder** that all public DQI descends from (repo jday96314/QuantumAI, now private; he has kept optimizing privately). Geremie: agentic-AI Kaggle notebooks. Tony Li: NeuroGolf/code-golf specialist. [I] Strongest on DQI. |
| 2 | Schrödinger's cat lived (pjmathematician) | 29.18 | Math optimizer ("Three square packings that beat the records"). Proved μ₄(6) = 14, so he exhausted the GF(4) multiplier route. Says DQI gave big jumps and then a wall, and is now focused on invsqrt. Holds #2 deliberately. |
| 3 | Jack (jackvd) | 29.10 | Fully agent-driven ("not tuning anything myself"). Says chemistry is the hardest. No public code. |
| 4 | taiseiu | 28.44 | No public code. |
| 5 | Breaking1800 | 28.00 | Led Oct 27 – Nov 2. Last submission Nov 1. Keeps a better local solution in reserve. |
| 6 | Diana (dziyanavalenta) | 27.43 | Nothing public. |
| 7 | CroDoc & Pavel | 27.40 | Santa/packing-optimization Grandmaster; ONNX golf. |
| 8 | Thinking... | 27.24 | 4 members. |
| 9 | yicheng guang | 27.08 | Nothing public. |
| 10 | Yan Zhou | 27.03 | Nothing public. |

**[I] Implied per-task mix for #1.** The product is 25,155 versus 15,883 public. A plausible split is invsqrt about 23–24, chemistry about 11.5–12.5 and DQI about 85–95. DQI is where the #1 team's author advantage lies; invsqrt and chemistry are where the next gains will come from.

**Public datasets with circuits [V]:**
- heliosli/qcc-circuits-live
- manwithacat/vqcc-apache-public-circuits (with a provenance table)
- syed3000/vqcc-own-circuit-portfolio
- isabe11am00re/qcc-v88…
- prvsiyan/vqcc-verified-best-of-circuits-1106a
- dmitriigluzdov/vqcc-femoco-public-factorization
- marculera/dfthc-compact-pipeline
- iwanttorungemma9b/vqcc-dfthc-soft-word-loaders
- manwithacat/kickmix-engine-wheels

The newest public frontier is maoxin123's LB 25.14 (chemistry λ_eff 46.8913). Its notebook also reports two nulls:
- (7, 143, 54) reaches only 18.7 mHa before rounding;
- live width is above 867 on 87% of the DQI stages.

---

## 4. Rules and prize strategy

All rule text is from K/pages.json, page "rules", plus host posts.

- **Merging.** Up to 5 members.
  - The combined submissions must be ≤ 5/day × days running.
  - The merge and entry deadline is 2027-01-13. Notebook publishing is also disabled from 01-13 (API `kernelsPublishingDisabledDeadline`).
  - No private code sharing before a merge.
  - → Merge early (Edge 1).
- **External data, tools and LLMs.**
  - Allowed if publicly and reasonably accessible (B.6).
  - Host Ryan Babbush: "You are free to use commercial AI and give whatever code you want to those AIs!"
  - ADMIN: private proprietary tools that others cannot access make a submission ineligible for the leaderboard.
  - Rented GPU: asked in topic 755643, no host answer yet [V]. The data is Apache-2.0; [I] a processor acting for us is low risk, but confirm before relying on it.
- **Compute limits.** This is a file-upload competition (`submission.zip`, up to 20 GB), so there is no notebook runtime cap on generation.
  - Scoring takes 21–60 minutes.
  - 5 submissions/day.
  - Hidden metric checks [V], from topic 751951 and the metric:
    - ids < 699,050 (`MAX_QUBIT_OR_BIT_ID`);
    - exactly one file per task, searched recursively;
    - named registers;
    - npz arrays must be float/int and little-endian.
- **Final selection.** Two final submissions. The private split uses its own secret salt. Ties go to the earlier submission (C.7(b)).
- **Public versus private.** `leaderboardPercentage` = 50, so each split has its own salt. Only DQI (failure draws) and chemistry/invsqrt measurement randomness vary between splits. invsqrt is tested exhaustively, so it is salt-independent apart from phase-kickback checks.
- **Prizes.**
  - 1st–6th: $50k / $25k / $10k / 3 × $5k.
  - Mid-competition, 2026-11-20: highest public LB score, notebook public until the end.
  - Longest Leader: notebook(s) public by 2027-01-04, durations combined across a team's notebooks. Geremie's question about it (topic 753654) is unanswered.
  - 3 × $10k single-task prizes, on selected submissions only.
  - Every prize needs Apache-2.0, generators for the exact circuits on **all** benchmarks, and reproducibility.
- **Declining a prize.** A team that declines need not open-source and keeps its LB place (ADMIN, topic 752085). James Day disputes this, citing the ARC 2024 removal precedent.
- **Licensing of reused public circuits.**
  - Apache-2.0 requires keeping notices and stating changes.
  - The jday96314 lineage is unlicensed. Public DQI lines are claimed to be clean-room (somejoint) [U].
  - Safest: our own generator, plus pinned Apache-2.0 inputs with SHA-256 and credits.
  - Open question (topic 755488): does a generator that transforms a pinned public binary count? Unanswered.
- **ANGLE_k scope (Khattar, HOST, topic 753092):** "The ANGLE_k circuits only need to satisfy the transformation on states reachable in the specified forward and reverse traversals… This is also what the official verifier enforces." → Previous-batch-aware loaders are **explicitly legal**.

---

## 5. Report-don't-exploit list

Nothing below was tested or submitted by me. Each item notes its rule status and whether it is physically valid.

1. **Input-dependent `R` resets in place of uncomputation** (topics 755302 and 755427). No host ruling.
   - Physically invalid: it measures, which collapses a superposition.
   - Syed Asad Ali reports [U] that the verifier already catches it, because `R` randomizes the phase when the qubit is |1⟩; kickmix's op_type.h confirms that semantics [V].
   - **Do not use.**
2. **Measuring the chemistry selection register and branching classically** (brief C).
   - Passes basis-state checks but is physically invalid.
   - Likely "undermining legitimate operation" (C.8(d) and C.16).
   - **Do not use.**
3. **ANGLE_k loaders correct only on reachable word states** (asimandia's reproducer; Zero found that yoyobar v30 fails arbitrary-payload XOR on 761/1,220 addresses).
   - **Host-confirmed legal** (753092) and physically valid for this block encoding (manwithacat's linearity argument).
   - Risk: topic 755427 asks whether the final review will enforce full-domain XOR. No answer yet.
   - Our stance: fine to use, but track the thread. Keep a full-XOR fallback that costs ≤ +1–2%.
4. **Salt re-rolling the public DQI draw.** Trivial byte changes re-seed the tests, so one could fish for a zero-failure public draw.
   - The circuits stay physically valid, and it does not change the private draw.
   - But it inflates **public**-LB-based prizes (Nov 20 milestone, Longest Leader). That could be read as an "unfair playing practice" (C.8(d)).
   - **Do not do it for prize positioning.** Use genuinely low-failure decoders.
5. **Numerical knife-edge chemistry gates** (margins about 2.4e-10 Ha in public files). Not an exploit but a fragility: the result depends on the numerics of a specific verifier build. Keep margins (Edge 4).
6. **Metric versus standalone verifier discrepancies** (id cap, recursive file search, npz dtype). These are pitfalls, not exploits.
7. **invsqrt unreachable inputs** (Legendre gaps; 23.5% of x cannot arise). The verifier tests all x, so there is nothing to exploit (manwithacat measured about 0.08% of rotation slack). Physically, restricting to reachable x would be valid, but the contract requires all x.
8. **Mean-executed Toffoli counting** for gates conditioned on HMR outcomes. Legitimate: classically controlled gates really are skipped. Not a loophole; use freely.

---

## 6. Sources I could not reach

- **arxiv.org:** DNS-blocked for both curl and WebFetch. Not read in full text:
  - Gu et al. 2610.22367 (I used its GitHub repo instead);
  - Khattar et al. 2510.10967;
  - Babbush et al. 2603.28846;
  - Long et al. "record-and-replay arithmetic" (ecdsa.fail tricks);
  - AlphaTensor-Quantum 2402.14396.

  The session's network settings must allow arxiv.org to read them.
- **unite.ai and neoteo.com** (press coverage of the Gu et al. paper): DNS-blocked.
- **api.github.com and github.com via curl:** 403. WebFetch of github.com worked until its usage limit was hit. Not reached:
  - the full Qualtran tree for `gf_arithmetic` and `optimization`;
  - the `kickmix/testdata` contents;
  - the ecdsa.fail repo and write-ups.
- **jday96314/QuantumAI:** private, not attempted.
- **KITP recorded talk** by Babbush, [33]: not located.
- **Kaggle Discord:** not monitored by hosts; not accessed.
- **Forum images:** only James Day's screenshot was viewed. hengck23's DQI tables were not viewed.
- **Leaderboard submission history API:** not used. The leader history was reconstructed from RezOps forum snapshots.
- **Not read in full** because of time: about 25 of the ~50 newest notebooks (I read about 22 headlines). Neither the `harshitsama` LB dataset nor `manwithacat/vqcc-hedge-wizardry` was read in full.
