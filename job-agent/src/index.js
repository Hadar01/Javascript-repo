#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { fetchGreenhouse } from './sources/greenhouse.js';
import { fetchLever } from './sources/lever.js';
import { fetchAshby } from './sources/ashby.js';
import { scoreJob } from './score.js';
import { Tracker, STATUSES } from './tracker.js';
import { renderDraft } from './draft.js';
import { renderReport } from './report.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DATA = path.join(ROOT, 'data');
const readJson = (f) => JSON.parse(fs.readFileSync(path.join(ROOT, f), 'utf8'));

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) args[key] = true;
      else { args[key] = next; i++; }
    } else args._.push(a);
  }
  return args;
}

async function pool(items, size, fn) {
  const out = [];
  let i = 0;
  await Promise.all(Array.from({ length: size }, async () => {
    while (i < items.length) { const idx = i++; out[idx] = await fn(items[idx]); }
  }));
  return out;
}

async function scan(args, profile, companies, tracker) {
  const tasks = [
    ...companies.greenhouse.map((s) => ['greenhouse', s, fetchGreenhouse]),
    ...companies.lever.map((s) => ['lever', s, fetchLever]),
    ...companies.ashby.map((s) => ['ashby', s, fetchAshby]),
  ];
  const failures = [];
  const results = await pool(tasks, 6, async ([src, slug, fn]) => {
    try { const jobs = await fn(slug); process.stderr.write(`✓ ${src}/${slug}: ${jobs.length} jobs\n`); return jobs; }
    catch (e) { failures.push(`${src}/${slug}: ${e.message}`); process.stderr.write(`✗ ${src}/${slug}: ${e.message}\n`); return []; }
  });

  const minScore = Number(args['min-score'] ?? 45);
  const newIds = new Set();
  let kept = 0;
  for (const job of results.flat()) {
    const r = scoreJob(job, profile);
    if (r.rejected) continue;
    kept++;
    if (tracker.upsert(job, r) && r.score >= minScore) newIds.add(job.id);
  }
  tracker.save();

  const report = renderReport(tracker, { minScore, newIds, failures, companies });
  fs.writeFileSync(path.join(DATA, 'report.md'), report);
  console.log(`\nScanned ${results.flat().length} postings → ${kept} relevant, ${newIds.size} new with score ≥ ${minScore}.`);
  console.log(`Report: ${path.join(DATA, 'report.md')}`);
}

function list(args, tracker) {
  const jobs = tracker.list({ status: args.status, minScore: Number(args['min-score'] ?? 0), limit: Number(args.limit ?? 25) });
  if (!jobs.length) return console.log('No jobs. Run: node src/index.js scan');
  for (const j of jobs) {
    console.log(`${String(j.score).padStart(3)}  [${j.status.padEnd(11)}] ${j.title} — ${j.company} (${j.location || 'n/a'})\n     ${j.url}\n     id: ${j.id}`);
  }
}

function add(args, profile, tracker) {
  for (const k of ['title', 'company', 'url']) if (!args[k]) throw new Error(`--${k} is required`);
  const job = {
    id: `manual:${args.company}:${Buffer.from(args.url).toString('base64url').slice(-10)}`.toLowerCase().replace(/\s+/g, '-'),
    source: args.source || 'manual',
    company: args.company, title: args.title, url: args.url,
    location: args.location || '', description: args.description || '', salary: args.salary || null,
    postedAt: new Date().toISOString(),
  };
  const r = scoreJob(job, profile);
  tracker.upsert(job, r.rejected ? { score: 0, reasons: [`filtered: ${r.rejected}`] } : r);
  tracker.save();
  console.log(`Added ${job.id} (score ${r.rejected ? `0 — ${r.rejected}` : r.score})`);
}

const HELP = `job-agent — find, rank and track 15+ LPA jobs

  scan [--min-score 45]            Pull jobs from companies.json, score them, write data/report.md
  list [--status new] [--limit 25] Show tracked jobs, best first
  add --title T --company C --url U [--location L] [--description D] [--salary "18-25 LPA"]
                                   Track a job found on LinkedIn/Naukri/Indeed/Wellfound
  draft <id>                       Write a cover note + referral DM + recruiter email to data/drafts/
  mark <id> <status> [--note "..."] Update status: ${STATUSES.join(', ')}
  report                           Regenerate data/report.md without re-scanning
`;

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const [cmd, ...rest] = args._;
  const profile = readJson('profile.json');
  const companies = readJson('companies.json');
  fs.mkdirSync(DATA, { recursive: true });
  const tracker = new Tracker(path.join(DATA, 'jobs.json'));

  switch (cmd) {
    case 'scan': return scan(args, profile, companies, tracker);
    case 'list': return list(args, tracker);
    case 'add': return add(args, profile, tracker);
    case 'draft': {
      const job = tracker.find(rest[0] || '');
      const dir = path.join(DATA, 'drafts');
      fs.mkdirSync(dir, { recursive: true });
      const file = path.join(dir, `${job.id.replace(/[^a-z0-9]+/gi, '_')}.md`);
      fs.writeFileSync(file, renderDraft(job, profile));
      if (job.status === 'new') tracker.setStatus(job.id, 'shortlisted', 'drafted');
      tracker.save();
      return console.log(`Draft written: ${file}`);
    }
    case 'mark': {
      const job = tracker.setStatus(rest[0] || '', rest[1], args.note || '');
      tracker.save();
      return console.log(`${job.title} — ${job.company}: ${job.status}`);
    }
    case 'report': {
      fs.writeFileSync(path.join(DATA, 'report.md'), renderReport(tracker, { minScore: Number(args['min-score'] ?? 45), companies }));
      return console.log(`Report: ${path.join(DATA, 'report.md')}`);
    }
    default: console.log(HELP);
  }
}

main().catch((e) => { console.error(`Error: ${e.message}`); process.exit(1); });
