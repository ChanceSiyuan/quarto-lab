export function buildAddProblemPrompt({ nextProblemId }) {
  return `Use sci-brain:brainstorm-ideas to help me shape one research problem.
If that skill is unavailable, stop and report it.

When I decide the candidate is ready to save, follow skills/add-problem/SKILL.md to add it to this repository as a draft.
Do not assess it as accepted or rejected. Do not write files until I explicitly confirm.

Candidate ID hint: ${nextProblemId}`;
}

export function buildCodexLaunch({ workspacePath, nextProblemId }) {
  const prompt = buildAddProblemPrompt({ nextProblemId });
  const params = new URLSearchParams({ prompt, path: workspacePath });
  const href = `codex://threads/new?${params.toString()}`;
  const fallbackText = `Open a new Codex task in ${workspacePath} and paste this prompt:\n\n${prompt}`;

  return { href, prompt, fallbackText };
}
