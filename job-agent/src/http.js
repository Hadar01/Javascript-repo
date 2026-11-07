// Minimal fetch wrapper with timeout + one retry. Uses global fetch (Node 18+).
export async function getJson(url, { timeoutMs = 20000, retries = 1 } = {}) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(url, {
        signal: ctrl.signal,
        headers: { 'user-agent': 'job-hunt-agent/1.0', accept: 'application/json' },
      });
      if (res.status === 404) throw Object.assign(new Error(`404 ${url}`), { notFound: true });
      if (!res.ok) throw new Error(`HTTP ${res.status} ${url}`);
      return await res.json();
    } catch (err) {
      lastErr = err;
      if (err.notFound) break;
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastErr;
}

export function stripHtml(html = '') {
  return String(html)
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
