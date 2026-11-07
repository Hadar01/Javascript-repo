import { getJson, stripHtml } from '../http.js';

// Public API: https://developers.ashbyhq.com/docs/public-job-posting-api
export async function fetchAshby(slug) {
  const data = await getJson(`https://api.ashbyhq.com/posting-api/job-board/${slug}?includeCompensation=true`);
  return (data.jobs || []).filter((j) => j.isListed !== false).map((j) => ({
    id: `ab:${slug}:${j.id}`,
    source: 'ashby',
    company: slug,
    title: j.title,
    location: [j.location, j.isRemote ? 'Remote' : null, ...(j.secondaryLocations || []).map((s) => s.location)]
      .filter(Boolean).join(' / '),
    url: j.jobUrl,
    postedAt: j.publishedAt || null,
    description: j.descriptionPlain || stripHtml(j.descriptionHtml),
    salary: j.compensation?.compensationTierSummary || null,
  }));
}
