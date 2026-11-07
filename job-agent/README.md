# Job Hunt Agent: 15+ LPA, remote or Delhi NCR first, plus every other growth lane

**Not just jobs:** `node src/index.js opps` ranks freelancing (Mercor, Upwork…), live Kaggle competitions, funded PhDs, research fellowships, open source and certifications by deadline and fit. See `GROWTH-PLAN.md`.

A small Node.js agent (no dependencies, Node 18+) that:

1. **Finds jobs.** Pulls live postings from ~30 companies that pay well, using their public Greenhouse, Lever and Ashby job-board APIs (`companies.json`).
2. **Filters and ranks them for you.** It drops intern, staff, principal and manager roles, roles that are US/EU-only, roles asking for far more experience than you have, and roles that post pay below 15 LPA. It scores the rest on skill match (C++, Python, AWS, PyTorch, RAG, LangGraph…), remote/NCR location and seniority (`src/score.js`, `profile.json`).
3. **Tracks your pipeline.** Each job moves through `new → shortlisted → applied → referral-asked → oa → interview → offer/rejected`.
4. **Drafts your outreach.** For each job it writes a cover note, a LinkedIn referral DM and a recruiter cold email.

> **Why it doesn't press "Submit" for you:** auto-submitting breaks the terms of service of LinkedIn, Naukri, Indeed and most applicant tracking systems (ATS). It can get your accounts banned, and recruiters spot spray-and-pray applications. Here the agent does the slow parts (finding, filtering, drafting). You spend about 2 minutes per job reviewing and clicking apply. Referrals convert 5–10× better than cold applications, so the DM draft matters most.

## Use

```bash
cd job-agent
node src/index.js scan                  # fetch + score → data/report.md
node src/index.js list --limit 20       # best matches in terminal
node src/index.js draft <id|company>    # outreach drafts → data/drafts/
node src/index.js mark <id|company> applied --note "referral from X"
node src/index.js add --title "SDE 1" --company Flipkart --url https://... --location Bengaluru \
     --description "paste JD here" --salary "20-30 LPA"   # jobs from LinkedIn/Naukri/Wellfound/Instahyre
node src/index.js report
node src/index.js opps                  # all growth opportunities → data/opportunities.md
node src/index.js opps --category phd   # or freelance | competition | fellowship | open-source | certification
node src/index.js opps mark mercor applied
npm test
```

**Kaggle live data** needs your API token: put `kaggle.json` in `~/.kaggle/`, or set `KAGGLE_API_TOKEN`. Without a token, `opps` uses only the curated list. If you're behind a corporate proxy, run with `NODE_USE_ENV_PROXY=1`.

**Run it daily.** For example, add this with `crontab -e`:
`0 9 * * * cd ~/Javascript-repo/job-agent && node src/index.js scan`. New postings are marked 🆕 in the report.

**Tune it.** Edit `profile.json` to change skills, target CTC, locations, excluded titles and maximum years required. Edit `companies.json` to add companies. If a slug returns 404, the report lists it. You can find the correct slug in the company's careers URL: `boards.greenhouse.io/<slug>`, `jobs.lever.co/<slug>` or `jobs.ashbyhq.com/<slug>`.

## The plan: 15–20+ LPA in roughly 3–4 months

Your strongest angle isn't "C++ fresher". It's **IIT Delhi research + GenAI (RAG, LangGraph, QLoRA/DPO) + C++/DSA + cloud**. That combination fits three tracks that pay 15+ LPA:

| Track | Roles | Typical band (approx.) | What clears it |
|---|---|---|---|
| A. Product SDE-1 | Microsoft, Amazon, Google, Atlassian, Uber, Flipkart, Adobe | 18–45 LPA | DSA (LeetCode medium in 25 min) + 1 round of low-level design (LLD)/basic system design |
| B. ML/GenAI engineer | AI startups (Sarvam, Krutrim, Glean, etc.), BCG X, Fractal, remote US startups | 15–35 LPA | 2 shipped GenAI projects with evals + Python + AWS deploy |
| C. C++ systems / quant dev | Qualcomm, NVIDIA, Samsung R&D, Tower, Graviton, Quadeye | 20–80 LPA | Modern C++ (move semantics, templates, concurrency), OS basics, hard DSA |

Apply to **A and B in parallel**. Treat C as a stretch while your C++ matures.

### Weekly grind (about 4 h/day alongside your GRF work)
- **DSA, 2 h/day.** Work through the NeetCode 150 / Striver SDE sheet by pattern. Track your time to solve. Hold 1 timed contest each week (LeetCode weekly).
- **C++, 30 min/day.** Read *Effective Modern C++*. Use STL fluently in all DSA work. Write one concurrency exercise per week (thread pool, producer–consumer).
- **AWS, 30 min/day.** Aim for **AWS Solutions Architect Associate** in 6–8 weeks. Deploy one of your GenAI projects on AWS: Lambda/ECS, S3, API Gateway, Bedrock or SageMaker.
- **Apply, 1 h/day.** Run `scan`, apply to 5–8 high-score jobs, send 5 referral DMs and make 2 follow-ups. Target **40+ quality applications per month**.
- **Weekend.** Do 1 system design topic and 1 mock interview (Pramp/peers). Improve one project.

### Fix these first (your Indeed profile is thin)
1. **Add the IIT Delhi GRF role** to your resume and Indeed/LinkedIn profiles. Right now Indeed only shows the HCLTech internship, and IIT Delhi is your biggest credibility signal.
2. Write each project as a single line with a measurable result. Example: "RAG over 50k docs, ChromaDB + Mistral-7B, recall@5 0.82, p95 900 ms on AWS".
3. Keep the resume to one page. Order sections Skills → Experience (GRF, HCLTech) → Projects → Education → Certifications.
4. Set your Indeed preferences (https://profile.indeed.com/preferences): remote, 15 LPA minimum.
5. Turn on LinkedIn "Open to work" with recruiters only, and set titles to SDE / ML Engineer / GenAI Engineer.

See `SHORTLIST-2026-11-07.md` for jobs found today.
