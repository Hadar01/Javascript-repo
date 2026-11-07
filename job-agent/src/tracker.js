import fs from 'node:fs';
import path from 'node:path';

export const STATUSES = ['new', 'shortlisted', 'applied', 'referral-asked', 'oa', 'interview', 'offer', 'rejected', 'skipped'];

export class Tracker {
  constructor(file) {
    this.file = file;
    this.jobs = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
  }

  upsert(job, result, now = new Date().toISOString()) {
    const prev = this.jobs[job.id];
    const isNew = !prev;
    this.jobs[job.id] = {
      ...prev,
      ...job,
      description: job.description?.slice(0, 4000),
      score: result.score,
      reasons: result.reasons,
      matchedSkills: result.matchedSkills || [],
      status: prev?.status || 'new',
      firstSeen: prev?.firstSeen || now,
      lastSeen: now,
      history: prev?.history || [],
    };
    return isNew;
  }

  find(idOrPrefix) {
    if (this.jobs[idOrPrefix]) return this.jobs[idOrPrefix];
    const q = String(idOrPrefix).toLowerCase();
    const hits = q ? Object.values(this.jobs).filter((j) => j.id.toLowerCase().includes(q) || String(j.company).toLowerCase().includes(q)) : [];
    if (hits.length === 1) return hits[0];
    if (hits.length > 1) throw new Error(`"${idOrPrefix}" matches ${hits.length} jobs; be more specific`);
    throw new Error(`No job matching "${idOrPrefix}"`);
  }

  setStatus(idOrPrefix, status, note = '') {
    if (!STATUSES.includes(status)) throw new Error(`Unknown status "${status}". Use one of: ${STATUSES.join(', ')}`);
    const job = this.find(idOrPrefix);
    job.history.push({ at: new Date().toISOString(), from: job.status, to: status, note });
    job.status = status;
    return job;
  }

  list({ status, minScore = 0, limit = 50 } = {}) {
    return Object.values(this.jobs)
      .filter((j) => (!status || j.status === status) && j.score >= minScore)
      .sort((a, b) => b.score - a.score || String(b.postedAt).localeCompare(String(a.postedAt)))
      .slice(0, limit);
  }

  save() {
    fs.mkdirSync(path.dirname(this.file), { recursive: true });
    fs.writeFileSync(this.file, JSON.stringify(this.jobs, null, 2));
  }
}
