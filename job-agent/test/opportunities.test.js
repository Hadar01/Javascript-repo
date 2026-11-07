import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { daysUntil, selectOpportunities, kaggleToOpportunity, renderOpportunities, kaggleAuthHeader } from '../src/opportunities.js';

const now = new Date('2026-11-07T00:00:00Z');
const catalog = JSON.parse(fs.readFileSync(new URL('../opportunities.json', import.meta.url))).items;

test('deadline parsing', () => {
  assert.equal(daysUntil('2026-11-10', now), 4);
  assert.equal(daysUntil('expected:2027-03', now), 115);
  assert.equal(daysUntil('rolling', now), null);
});

test('catalog is well-formed', () => {
  const ids = new Set();
  for (const o of catalog) {
    for (const k of ['id', 'category', 'title', 'url', 'deadline', 'payoff', 'fit', 'action']) assert.ok(o[k] !== undefined, `${o.id} missing ${k}`);
    assert.ok(!ids.has(o.id), `duplicate ${o.id}`); ids.add(o.id);
    assert.ok(o.deadline === 'rolling' || daysUntil(o.deadline, now) !== null, `${o.id} bad deadline`);
  }
});

test('selection drops expired + far-future, ranks urgent high-fit first', () => {
  const list = selectOpportunities([
    ...catalog,
    { id: 'x:expired', category: 'phd', title: 'old', url: 'u', deadline: '2026-10-01', fit: 99, payoff: '', action: '' },
  ], { now, horizonDays: 180 });
  assert.ok(!list.find((o) => o.id === 'x:expired'));
  assert.ok(!list.find((o) => o.id === 'phd:ellis')); // ~Oct 2027, beyond horizon
  const top3 = list.slice(0, 3).map((o) => o.id);
  assert.ok(top3.includes('comp:kaggle-gemma-agent') || top3.includes('phd:singa'), top3.join());
  assert.match(renderOpportunities(list, {}, now), /Do next/);
});

test('kaggle mapping scores quantum above getting-started', () => {
  const q = kaggleToOpportunity({ title: 'Google Quantum AI - Circuit Compilation', description: 'compile quantum circuits', category: 'Featured', reward: '150,000 Usd', deadline: '2027-01-20T23:59:00Z', ref: 'https://www.kaggle.com/competitions/qc', url: 'https://www.kaggle.com/competitions/qc' });
  const t = kaggleToOpportunity({ title: 'Titanic', description: 'survival', category: 'Getting Started', reward: 'Knowledge', deadline: '2030-01-01', ref: 'titanic' });
  assert.equal(q.id, 'comp:kaggle:qc');
  assert.equal(q.deadline, '2027-01-20');
  assert.ok(q.fit > t.fit + 40);
});

test('kaggle auth header from env', () => {
  assert.equal(kaggleAuthHeader({ KAGGLE_API_TOKEN: 'abc' }), 'Bearer abc');
  assert.equal(kaggleAuthHeader({ KAGGLE_USERNAME: 'u', KAGGLE_KEY: 'k' }), `Basic ${Buffer.from('u:k').toString('base64')}`);
});

test('live entries with same URL as curated ones are deduped (curated wins)', () => {
  const live = { id: 'comp:kaggle:gemma', category: 'competition', title: 'live', url: 'https://www.kaggle.com/competitions/gemma-4-developer-agent/', deadline: '2026-12-02', fit: 90, payoff: '', action: '' };
  const list = selectOpportunities([...catalog, live], { now });
  const hits = list.filter((o) => o.url.includes('gemma-4-developer-agent') && !o.url.includes('paper'));
  assert.equal(hits.length, 1);
  assert.equal(hits[0].id, 'comp:kaggle-gemma-agent');
});
