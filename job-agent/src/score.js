// Scores a job (0-100-ish) against the profile and explains why.

const INDIA_RE = /\b(india|bengaluru|bangalore|hyderabad|pune|mumbai|chennai|delhi|gurugram|gurgaon|noida|kolkata|ahmedabad)\b/i;
const GLOBAL_REMOTE_RE = /\b(anywhere|worldwide|global|apac|asia)\b/i;
const NON_INDIA_RE = /\b(us|usa|united states|canada|uk|united kingdom|europe|emea|germany|france|netherlands|ireland|poland|spain|brazil|mexico|latam|australia|singapore|japan|new york|san francisco|london|berlin|seattle|toronto)\b/i;
const US_ONLY_RE = /(must|required to) (be )?(reside|located|based|live) in (the )?(us|u\.s\.|united states|canada|uk|europe)|work authori[sz]ation in the (us|united states)/i;

const norm = (s) => String(s || '').toLowerCase();

export function classifyLocation(location, description = '') {
  const loc = norm(location);
  const isRemote = /remote|work from home|wfh|distributed/.test(loc);
  const inIndia = INDIA_RE.test(loc);
  if (inIndia && isRemote) return 'remote-india';
  if (inIndia) return 'india';
  if (isRemote) {
    if (US_ONLY_RE.test(description)) return 'remote-restricted';
    if (GLOBAL_REMOTE_RE.test(loc)) return 'remote-global';
    if (NON_INDIA_RE.test(loc)) return 'remote-restricted';
    return 'remote-unknown';
  }
  return 'abroad';
}

export function yearsRequired(text) {
  const t = norm(text);
  const re = /(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*\+?\s*)?(?:years?|yrs?)/g;
  let max = 0;
  for (const m of t.matchAll(re)) {
    const ctx = t.slice(Math.max(0, m.index - 60), m.index + m[0].length + 60);
    if (!/experience|exp\b|professional|industry|hands-on|working/.test(ctx)) continue;
    const n = Number(m[1]);
    if (n > 0 && n <= 15) max = Math.max(max, n);
  }
  return max || null;
}

// Parses INR annual salary ranges like "₹15L-25L", "15-25 LPA", "INR 1,800,000 - 2,500,000".
export function parseInrLpa(text) {
  const t = norm(text).replace(/,/g, '');
  let m = t.match(/(\d+(?:\.\d+)?)\s*(?:l|lpa|lakhs?)?\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|l\b)/);
  if (m) return { min: Number(m[1]), max: Number(m[2]) };
  m = t.match(/(?:₹|inr|rs\.?)\s*(\d{6,8})\s*(?:-|–|to)\s*(?:₹|inr|rs\.?)?\s*(\d{6,8})/);
  if (m) return { min: Number(m[1]) / 1e5, max: Number(m[2]) / 1e5 };
  return null;
}

function countHits(text, words) {
  return words.filter((w) => {
    const esc = w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp(`(^|[^a-z])${esc}([^a-z]|$)`, 'i').test(text);
  });
}

export function scoreJob(job, profile) {
  const title = norm(job.title);
  const desc = norm(job.description);
  const reasons = [];
  let score = 0;

  // Hard filters
  const [excluded] = countHits(title, profile.excludeKeywords);
  if (excluded) return { score: 0, rejected: `title contains "${excluded}"`, reasons };

  const loc = classifyLocation(job.location, desc);
  if (loc === 'abroad' || loc === 'remote-restricted') {
    return { score: 0, rejected: `location not open to India (${job.location || 'n/a'})`, reasons };
  }

  const roleHits = countHits(title, profile.roleKeywords);
  if (roleHits.length === 0) return { score: 0, rejected: 'title not a target role', reasons };
  score += 30;
  reasons.push(`role: ${roleHits.join(', ')}`);

  // Location
  const preferred = profile.locations.preferred.some((p) => norm(job.location).includes(norm(p)));
  if (loc.startsWith('remote')) { score += 15; reasons.push(`remote (${loc})`); }
  else if (preferred) { score += 12; reasons.push('Delhi NCR'); }
  else { score += 6; reasons.push('India (relocation)'); }

  // Skills
  const text = `${title} ${desc}`;
  const core = countHits(text, profile.skills.core);
  const strong = countHits(text, profile.skills.strong);
  const bonus = countHits(text, profile.skills.bonus);
  score += Math.min(30, core.length * 6 + strong.length * 4 + bonus.length * 2);
  const matched = [...core, ...strong, ...bonus];
  if (matched.length) reasons.push(`skills: ${matched.join(', ')}`);

  // Seniority
  const yrs = yearsRequired(desc);
  if (yrs != null) {
    if (yrs > profile.maxYearsRequired + 2) { score -= 30; reasons.push(`needs ${yrs}+ yrs (stretch)`); }
    else if (yrs > profile.maxYearsRequired) { score -= 12; reasons.push(`needs ${yrs}+ yrs`); }
    else { score += 10; reasons.push(`${yrs} yrs required — fits`); }
  }
  if (/\b(senior|sr\.?|lead)\b/.test(title)) { score -= 10; reasons.push('senior title'); }
  if (/\b(new grad|graduate|entry|junior|sde[- ]?1|engineer i\b|associate)\b/.test(title)) { score += 10; reasons.push('entry-level title'); }

  // Salary (when posted)
  const sal = parseInrLpa(`${job.salary || ''} ${desc}`);
  if (sal) {
    if (sal.max >= profile.stretchCtcLpa) { score += 15; reasons.push(`pays up to ${sal.max} LPA`); }
    else if (sal.max >= profile.targetCtcLpa) { score += 8; reasons.push(`pays up to ${sal.max} LPA`); }
    else { score -= 25; reasons.push(`pays only up to ${sal.max} LPA`); }
  }

  return { score: Math.max(0, Math.min(100, score)), rejected: null, reasons, matchedSkills: matched, yearsRequired: yrs, location: loc };
}
