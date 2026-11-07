import { getJson, stripHtml } from '../http.js';

// Public API: https://github.com/lever/postings-api
export async function fetchLever(slug) {
  const data = await getJson(`https://api.lever.co/v0/postings/${slug}?mode=json`);
  return (Array.isArray(data) ? data : []).map((j) => ({
    id: `lv:${slug}:${j.id}`,
    source: 'lever',
    company: slug,
    title: j.text,
    location: [j.categories?.location, j.workplaceType].filter(Boolean).join(' / '),
    url: j.hostedUrl,
    postedAt: j.createdAt ? new Date(j.createdAt).toISOString() : null,
    description: stripHtml(j.descriptionPlain || j.description || '') + ' ' +
      (j.lists || []).map((l) => `${l.text} ${stripHtml(l.content)}`).join(' '),
    salary: j.salaryRange ? `${j.salaryRange.min}-${j.salaryRange.max} ${j.salaryRange.currency}/${j.salaryRange.interval}` : null,
  }));
}
