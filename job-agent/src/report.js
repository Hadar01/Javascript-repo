export function renderReport(tracker, { minScore, newIds = new Set(), failures = [], companies } = {}) {
  const today = new Date().toISOString().slice(0, 10);
  const top = tracker.list({ minScore, limit: 40 }).filter((j) => ['new', 'shortlisted'].includes(j.status));
  const pipeline = tracker.list({ limit: 1000 }).filter((j) => !['new', 'shortlisted', 'skipped'].includes(j.status));

  const row = (j) => `| ${newIds.has(j.id) ? '🆕 ' : ''}[${j.title.replace(/\|/g, '/')}](${j.url}) | ${j.company} | ${j.location || ''} | ${j.score} | ${(j.reasons || []).slice(1).join('; ').replace(/\|/g, '/')} | \`${j.id}\` |`;

  let md = `# Job hunt report — ${today}\n\n`;
  md += `## Top matches to act on (score ≥ ${minScore})\n\n`;
  md += top.length
    ? `| Role | Company | Location | Score | Why | ID |\n|---|---|---|---|---|---|\n${top.map(row).join('\n')}\n`
    : '_No new matches. Lower --min-score or add companies._\n';

  md += `\n## Pipeline\n\n`;
  md += pipeline.length
    ? `| Role | Company | Status | Last update |\n|---|---|---|---|\n${pipeline.map((j) => `| [${j.title}](${j.url}) | ${j.company} | ${j.status} | ${(j.history.at(-1)?.at || '').slice(0, 10)} |`).join('\n')}\n`
    : '_Nothing applied yet — pick 5 from the table above today._\n';

  if (companies?.directApply?.length) {
    md += `\n## Check these careers pages directly (not on public job-board APIs)\n\n`;
    md += companies.directApply.map((c) => `- [${c.name}](${c.url}) — ${c.why}`).join('\n') + '\n';
  }
  if (failures.length) {
    md += `\n## Sources that failed (fix slug in companies.json)\n\n${failures.map((f) => `- ${f}`).join('\n')}\n`;
  }
  return md;
}
