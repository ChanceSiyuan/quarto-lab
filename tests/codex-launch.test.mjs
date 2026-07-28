import assert from "node:assert/strict";
import test from "node:test";

import { buildAddProblemPrompt, buildCodexLaunch } from "../lib/problems/codex-launch.mjs";

test("builds a short discussion-to-draft hand-off prompt", () => {
  const prompt = buildAddProblemPrompt({ nextProblemId: "Prob-007" });
  assert.match(prompt, /sci-brain:brainstorm-ideas/);
  assert.match(prompt, /If that skill is unavailable, stop and report it/);
  assert.match(prompt, /skills\/add-problem\/SKILL\.md/);
  assert.match(prompt, /draft/i);
  assert.match(prompt, /Do not assess it as accepted or rejected/i);
  assert.match(prompt, /Do not write files until I explicitly confirm/i);
  assert.match(prompt, /Candidate ID hint: Prob-007/);
  assert.ok(prompt.length < 400, `prompt is ${prompt.length} characters`);
});

test("keeps owned contracts out of the browser prompt", () => {
  const prompt = buildAddProblemPrompt({ nextProblemId: "Prob-007" });
  assert.doesNotMatch(prompt, /QuantumBFS|issue #133/i);
  assert.doesNotMatch(prompt, /schemaVersion|provenance|lastActivity/i);
  assert.doesNotMatch(prompt, /ungameable|literature basis|fresh evaluation/i);
  assert.doesNotMatch(prompt, /atomic rename|problem\.json.*last/is);
  assert.doesNotMatch(prompt, /generation\/initial-prompt\.md/);
});

test("builds a Codex deep link and matching fallback", () => {
  const launch = buildCodexLaunch({
    workspacePath: "/Users/nzy/mcode/research-loop",
    nextProblemId: "Prob-007",
  });

  const parsed = new URL(launch.href);
  assert.equal(parsed.protocol, "codex:");
  assert.equal(parsed.hostname, "threads");
  assert.equal(parsed.pathname, "/new");
  assert.equal(parsed.searchParams.get("path"), "/Users/nzy/mcode/research-loop");
  assert.equal(parsed.searchParams.get("prompt"), launch.prompt);
  assert.match(launch.fallbackText, /\/Users\/nzy\/mcode\/research-loop/);
  assert.match(launch.fallbackText, /Prob-007/);
});
