import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchGreenhouse } from '../src/sources/greenhouse.js';
import { fetchLever } from '../src/sources/lever.js';
import { fetchAshby } from '../src/sources/ashby.js';

function mockFetch(body, status = 200) {
  globalThis.fetch = async () => ({ ok: status < 400, status, json: async () => body });
}

test('greenhouse mapping', async () => {
  mockFetch({ jobs: [{ id: 1, title: 'SWE', location: { name: 'Bengaluru' }, absolute_url: 'u', content: '&lt;p&gt;C++ &amp; AWS&lt;/p&gt;', company_name: 'Acme' }] });
  const [j] = await fetchGreenhouse('acme');
  assert.equal(j.id, 'gh:acme:1');
  assert.equal(j.description, 'C++ & AWS');
});

test('lever mapping', async () => {
  mockFetch([{ id: 'x', text: 'Backend Engineer', categories: { location: 'Remote' }, hostedUrl: 'u', descriptionPlain: 'Go', lists: [{ text: 'Req', content: '<li>2 years</li>' }] }]);
  const [j] = await fetchLever('acme');
  assert.equal(j.title, 'Backend Engineer');
  assert.match(j.description, /2 years/);
});

test('ashby mapping and 404 handling', async () => {
  mockFetch({ jobs: [{ id: 'a', title: 'AI Engineer', location: 'India', isRemote: true, jobUrl: 'u', descriptionPlain: 'LLM' }] });
  const [j] = await fetchAshby('acme');
  assert.match(j.location, /Remote/);
  mockFetch({}, 404);
  await assert.rejects(fetchAshby('nope'), /404/);
});
