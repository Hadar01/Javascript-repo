// Drafts application material you review and send yourself.

export function draftOutreach(job, profile) {
  const skills = (job.matchedSkills || []).slice(0, 5);
  const skillLine = skills.length ? skills.join(', ') : 'C++, Python and ML systems';
  const first = profile.name.split(' ')[0];

  const coverNote = `Hi ${job.company} team,

I'm applying for the ${job.title} role. ${profile.pitch}

What maps directly to this role: ${skillLine}. A few concrete things I've built:
- [Project 1 — one line, with a number: latency/accuracy/scale]
- [Project 2 — GenAI/RAG or C++ systems work, with outcome]
- [Research at IIT Delhi — what problem, what result]

I'm available to join [notice period] and open to ${profile.locations.remote ? 'remote or ' : ''}relocation.

Thanks,
${profile.name}
${profile.email}`;

  const referralDm = `Hi [Name], I'm ${first}, a Graduate Research Fellow at IIT Delhi (C++, ML/GenAI, AWS). I'm applying to ${job.company} for "${job.title}" (${job.url}). My background in ${skillLine} lines up well with it. Would you be open to referring me? Happy to send my resume — it takes 2 minutes to read. Thank you!`;

  const recruiterEmail = `Subject: ${job.title} — ${profile.name} (IIT Delhi GRF, ${skills[0] || 'C++/ML'})

Hi [Recruiter name],

I came across the ${job.title} opening at ${job.company} and I'd love to be considered. ${profile.pitch}

Resume attached. Would you have 15 minutes this week?

Best,
${profile.name}`;

  return { coverNote, referralDm, recruiterEmail };
}

export function renderDraft(job, profile) {
  const d = draftOutreach(job, profile);
  return `# ${job.title} — ${job.company}

- Apply: ${job.url}
- Location: ${job.location || 'n/a'}
- Score: ${job.score} (${(job.reasons || []).join('; ')})

Fill in the [brackets] before sending.

## Cover note / "Why you?" box
${d.coverNote}

## LinkedIn referral request (send to 2-3 engineers at ${job.company})
${d.referralDm}

## Cold email to recruiter
${d.recruiterEmail}
`;
}
