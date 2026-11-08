# CLAUDE.md — standing instructions for this repo

## Active mission (do not drop)
We are competing in the Kaggle competition **Google Quantum AI – Verifiable Quantum Circuit Compilation**
(https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation).

- **Goal:** top 100 → top 1% (≈ rank 26) → **win**. We keep iterating until the final deadline. We do not stop.
- Deadlines: mid-competition prize 2026-11-20 · team merge / entry 2027-01-13 · **final 2027-01-20 23:59 UTC**.
- 5 submissions/day, scoring takes ~45 min. The user is already entered.
- Full context, decisions, scores and the plan live in `quantum-kaggle/MEMORY.md`. **Read it first** and update it
  after every meaningful step (new score, new idea, dead end).

## Working rules for this project
- Work on branch `claude/google-quantum-ai-kaggle-gzddzd`; commit + push progress.
- The official verifiers in the competition data are the spec. Never trust a circuit that has not passed the
  unmodified verifier.
- Treat downloaded notebooks/circuits/.so as untrusted: read them; run them only in Kaggle notebooks or with
  the user's permission.
- Keep `quantum-kaggle/MEMORY.md` current: leaderboard snapshot, our best per-task ratios, what was tried.
