export function buildAddProblemPrompt({ nextProblemId }) {
  return `First run \`npm run skills:ensure-sci-brain\`. If it installs sci-brain during this task, read the installed \`brainstorm-ideas/SKILL.md\`, then continue in this task; do not stop after installation.

Use the \`brainstorm-ideas\` skill to help me shape one research problem.

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
