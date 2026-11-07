import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { getJson } from './http.js';

const RELEVANT = { quantum: 25, llm: 15, agent: 15, gemma: 10, language: 8, vision: 10, image: 8, 'c++': 10, optimization: 8, compil: 10, fraud: 3 };

// Kaggle auth: KAGGLE_API_TOKEN (new bearer tokens) or ~/.kaggle/kaggle.json / KAGGLE_USERNAME+KAGGLE_KEY (basic).
export function kaggleAuthHeader(env = process.env) {
  if (env.KAGGLE_API_TOKEN) return `Bearer ${env.KAGGLE_API_TOKEN}`;
  let user = env.KAGGLE_USERNAME, key = env.KAGGLE_KEY;
  const file = path.join(os.homedir(), '.kaggle', 'kaggle.json');
  if ((!user || !key) && fs.existsSync(file)) ({ username: user, key } = JSON.parse(fs.readFileSync(file, 'utf8')));
  return user && key ? `Basic ${Buffer.from(`${user}:${key}`).toString('base64')}` : null;
}

export function kaggleToOpportunity(c) {
  const text = `${c.title} ${c.description}`.toLowerCase();
  let fit = 40;
  for (const [k, w] of Object.entries(RELEVANT)) if (text.includes(k)) fit += w;
  if (c.category === 'Featured' || c.category === 'Research') fit += 10;
  if (c.category === 'Getting Started') fit -= 25;
  return {
    id: `comp:kaggle:${c.ref?.split('/').pop() || c.id}`,
    category: 'competition',
    title: `Kaggle: ${c.title} (${c.reward})`,
    url: c.url || c.ref,
    deadline: (c.deadline || '').slice(0, 10) || 'rolling',
    payoff: `${c.reward} — ${c.description}`,
    fit: Math.min(99, fit),
    action: 'Join, run the starter notebook, publish one public notebook to build Kaggle profile.',
    live: true,
  };
}

export async function fetchKaggle(fetchImpl = getJson) {
  const auth = kaggleAuthHeader();
  if (!auth) throw new Error('no Kaggle credentials (set KAGGLE_API_TOKEN or ~/.kaggle/kaggle.json)');
  const all = [];
  for (let page = 1; page <= 3; page++) {
    const batch = await fetchImpl(`https://www.kaggle.com/api/v1/competitions/list?page=${page}`, { headers: { authorization: auth } });
    if (!Array.isArray(batch) || !batch.length) break;
    all.push(...batch);
  }
  return all.map(kaggleToOpportunity);
}

export function daysUntil(deadline, now = new Date()) {
  const m = /^(?:expected:)?(\d{4}-\d{2})(-\d{2})?$/.exec(deadline || '');
  if (!m) return null; // rolling
  const d = new Date(`${m[1]}${m[2] || '-01'}T23:59:59Z`);
  return Math.ceil((d - now) / 86400000);
}

// Lower = do sooner. Closing soon & high fit float to the top; rolling items sit mid-pack.
export function urgency(o, now = new Date()) {
  const days = daysUntil(o.deadline, now);
  const timeScore = days == null ? 45 : Math.min(Math.max(0, days), 120) * 0.5;
  return timeScore - o.fit * 0.6;
}

export function selectOpportunities(items, { now = new Date(), horizonDays = 180, category, minFit = 50, minDaysLeftLive = 7 } = {}) {
  const seen = new Set();
  return items
    .filter((o) => {
      const key = String(o.url || o.id).toLowerCase().replace(/\/+$/, '');
      return seen.has(key) || seen.has(o.id) ? false : (seen.add(key), seen.add(o.id), true);
    })
    .filter((o) => !category || o.category === category)
    .filter((o) => o.fit >= minFit)
    .filter((o) => { const d = daysUntil(o.deadline, now); return d == null || (d >= (o.live ? minDaysLeftLive : 0) && d <= horizonDays); })
    .sort((a, b) => urgency(a, now) - urgency(b, now));
}

export function renderOpportunities(list, statuses = {}, now = new Date()) {
  const when = (o) => {
    const d = daysUntil(o.deadline, now);
    if (d == null) return 'rolling';
    const label = o.deadline.startsWith('expected:') ? `~${o.deadline.slice(9)} (expected)` : o.deadline;
    return d <= 14 ? `**${label} — ${d}d left**` : `${label} (${d}d)`;
  };
  const byCat = {};
  for (const o of list) (byCat[o.category] ||= []).push(o);
  let md = `# Growth opportunities — ${now.toISOString().slice(0, 10)}\n\nSorted by urgency × fit. Confirm every deadline on the official link.\n`;
  md += `\n## Do next (top 6)\n\n${list.slice(0, 6).map((o, i) => `${i + 1}. [${o.title}](${o.url}) — ${when(o)}. ${o.action}`).join('\n')}\n`;
  for (const [cat, items] of Object.entries(byCat)) {
    md += `\n## ${cat[0].toUpperCase()}${cat.slice(1)}\n\n| Opportunity | Deadline | Fit | Payoff | Status | ID |\n|---|---|---|---|---|---|\n`;
    md += items.map((o) => `| [${o.title.replace(/\|/g, '/')}](${o.url}) | ${when(o)} | ${o.fit} | ${String(o.payoff).replace(/\|/g, '/').slice(0, 140)} | ${statuses[o.id] || 'todo'} | \`${o.id}\` |`).join('\n') + '\n';
  }
  return md;
}
