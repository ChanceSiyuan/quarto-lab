export function buildAddProblemPrompt({ workspacePath, nextProblemId }) {
  return `You are helping create one new Research Loop problem for QuantumBFS/quantum.harness issue #133.
Work inside this repository path:
${workspacePath}

Use candidate ID ${nextProblemId}.
Ask me one question at a time.
Reject candidates that cannot be expressed as an ungameable executable gate.
Check literature basis, research value, novelty, executable gate, and fresh evaluation before recommending acceptance.
Before writing files, show the final summary, rubric result, and exact file list.
Only write files after I explicitly confirm.
If the candidate is accepted, write:
problems/${nextProblemId}/problem.json
problems/${nextProblemId}/problem.md
problems/${nextProblemId}/generation/initial-prompt.md
problems/${nextProblemId}/generation/transcript.md
problems/${nextProblemId}/generation/decision.md
If the candidate is rejected, still write the same directory with status rejected, rejection.kind, rejection.reason, and the generation record after I confirm saving the rejection.
After writing, run the manifest validation from this repo and report the result.`;
}

export function buildCodexLaunch({ workspacePath, nextProblemId }) {
  const prompt = buildAddProblemPrompt({ workspacePath, nextProblemId });
  const params = new URLSearchParams({ prompt, path: workspacePath });
  const href = `codex://threads/new?${params.toString()}`;
  const fallbackText = `Open a new Codex task in ${workspacePath} and paste this prompt:\n\n${prompt}`;

  return { href, prompt, fallbackText };
}
