export function buildAddProblemPrompt({ workspacePath, nextProblemId }) {
  return `You are helping create one new Research Loop problem for QuantumBFS/quantum.harness issue #133.
The overall success target is five problems that pass the approved qualification contract.
Work inside this repository path:
${workspacePath}

Use candidate ID ${nextProblemId}.
Before discussing or writing the candidate, scan every existing problems/QMB-NNN directory and every parseable manifest ID. Treat both sources as reserved IDs, including damaged or otherwise invalid records. If ${nextProblemId} is already reserved, stop and do not write or overwrite anything; report that a fresh index and candidate ID are required.
Ask me one question at a time.
Reject candidates that cannot be expressed as an ungameable executable gate.
Check literature basis, research value, novelty, executable gate, and fresh evaluation before recommending acceptance.

Obey this exact problem.json manifest schema:
- schemaVersion: exactly 1.
- id: exactly ${nextProblemId} and matching the directory name.
- title and summary: non-empty strings.
- status: exactly one of draft, qualifying, accepted, solving, solved, publishing, published, rejected, archived.
- gate: an object with non-empty string type and readiness exactly one of missing, specified, executable, passed. accepted and later active statuses require executable or passed.
- provenance: an object with sourceCount as a non-negative integer.
- lastActivity: an object with a non-empty summary and valid date string at.
- createdAt and updatedAt: valid date strings.
- rejection is forbidden unless status is rejected; rejected records require rejection.kind exactly automatic or human and a non-empty rejection.reason.
- Allow no unknown top-level fields.
For accepted and later active statuses, problem.md must contain all required headings from lib/problems/schema.mjs.

Before writing files, show the final summary, rubric result, and exact file list.
Only write files after I explicitly confirm.
For an accepted or rejected candidate, the exact final directory contract is:
problems/${nextProblemId}/problem.json
problems/${nextProblemId}/problem.md
problems/${nextProblemId}/generation/initial-prompt.md
problems/${nextProblemId}/generation/transcript.md
problems/${nextProblemId}/generation/decision.md
If the candidate is rejected, use status rejected, rejection.kind, rejection.reason, and preserve the complete generation record after I confirm saving the rejection.

Prepare and validate all five files in a temporary staging location outside problems/${nextProblemId}; do not make a draft problem.json visible to the indexer. Validate the staged manifest and problem.md with this repository's schema before publishing anything.
Immediately before any final-directory write, re-check every reserved ID and confirm problems/${nextProblemId} does not exist. Create that directory with an exclusive operation that fails on collision. If the re-check or exclusive create fails, stop and do not write or overwrite anything.
Copy the four non-manifest files into the new directory first. Publish problem.json last using an atomic rename from the staged, already validated manifest. Never expose problem.json while problem.md or generation audit records are incomplete.
After problem.json is published last, run the manifest validation and index build from this repo and report the result.`;
}

export function buildCodexLaunch({ workspacePath, nextProblemId }) {
  const prompt = buildAddProblemPrompt({ workspacePath, nextProblemId });
  const params = new URLSearchParams({ prompt, path: workspacePath });
  const href = `codex://threads/new?${params.toString()}`;
  const fallbackText = `Open a new Codex task in ${workspacePath} and paste this prompt:\n\n${prompt}`;

  return { href, prompt, fallbackText };
}
