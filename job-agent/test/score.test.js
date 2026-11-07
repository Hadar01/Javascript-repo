import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { scoreJob, classifyLocation, yearsRequired, parseInrLpa } from '../src/score.js';

const profile = JSON.parse(fs.readFileSync(new URL('../profile.json', import.meta.url)));

test('location classification', () => {
  assert.equal(classifyLocation('Bengaluru, India'), 'india');
  assert.equal(classifyLocation('Remote - India'), 'remote-india');
  assert.equal(classifyLocation('Remote (US)'), 'remote-restricted');
  assert.equal(classifyLocation('Remote', 'Candidates must reside in the United States'), 'remote-restricted');
  assert.equal(classifyLocation('Remote, Worldwide'), 'remote-global');
  assert.equal(classifyLocation('San Francisco, CA'), 'abroad');
});

test('years required and salary parsing', () => {
  assert.equal(yearsRequired('Minimum 5 years of professional experience; 3+ years with C++'), 5);
  assert.equal(yearsRequired('0-2 years of experience'), null); // 0 lower bound → treated as entry level
  assert.equal(yearsRequired('We were founded 10 years ago'), null);
  assert.deepEqual(parseInrLpa('CTC: 18 - 25 LPA'), { min: 18, max: 25 });
  assert.deepEqual(parseInrLpa('INR 1,800,000 - 2,400,000'), { min: 18, max: 24 });
});

test('good entry-level ML job in NCR scores high', () => {
  const r = scoreJob({
    title: 'Machine Learning Engineer I', location: 'Gurugram, India',
    description: 'Python, PyTorch, LLM, RAG, AWS, Docker. 1+ years of experience. CTC 18-28 LPA',
  }, profile);
  assert.equal(r.rejected, null);
  assert.ok(r.score >= 80, `score ${r.score}`);
});

test('filters out senior, intern, abroad roles but keeps "International"', () => {
  assert.ok(scoreJob({ title: 'Staff Software Engineer', location: 'Bengaluru' }, profile).rejected);
  assert.ok(scoreJob({ title: 'Software Engineer Intern', location: 'Remote' }, profile).rejected);
  assert.ok(scoreJob({ title: 'Software Engineer', location: 'London, UK' }, profile).rejected);
  assert.equal(scoreJob({ title: 'Applied Scientist, International ML', location: 'Gurugram, India' }, profile).rejected, null);
});

test('heavy experience requirement and low pay are penalised', () => {
  const base = { title: 'Software Engineer', location: 'Remote - India', description: 'C++ python aws' };
  const ok = scoreJob(base, profile).score;
  const senior = scoreJob({ ...base, description: base.description + ' 7+ years of experience' }, profile).score;
  const lowPay = scoreJob({ ...base, description: base.description + ' salary 6-9 LPA' }, profile).score;
  assert.ok(senior < ok && lowPay < ok);
});
