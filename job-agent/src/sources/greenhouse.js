import { getJson, stripHtml } from '../http.js';

// Public API: https://developers.greenhouse.io/job-board.html
export async function fetchGreenhouse(slug) {
  const data = await getJson(`https://boards-api.greenhouse.io/v1/boards/${slug}/jobs?content=true`);
  return (data.jobs || []).map((j) => ({
    id: `gh:${slug}:${j.id}`,
    source: 'greenhouse',
    company: j.company_name || slug,
    title: j.title,
    location: j.location?.name || '',
    url: j.absolute_url,
    postedAt: j.updated_at || j.first_published || null,
    description: stripHtml(j.content),
  }));
}
