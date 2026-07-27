import assert from "node:assert/strict";
import test from "node:test";

import { buildAddProblemPrompt, buildCodexLaunch } from "../lib/problems/codex-launch.mjs";

test("builds a strict issue 133 prompt with the repo path and next ID", () => {
  const prompt = buildAddProblemPrompt({
    workspacePath: "/Users/nzy/mcode/research-loop",
    nextProblemId: "QMB-007",
  });

  assert.match(prompt, /QuantumBFS\/quantum\.harness issue #133/);
  assert.match(prompt, /QMB-007/);
  assert.match(prompt, /one question at a time/i);
  assert.match(prompt, /ungameable executable gate/i);
  assert.match(prompt, /Only write files after I explicitly confirm/i);
  assert.match(prompt, /problems\/QMB-007\/problem\.json/);
});

test("builds a Codex deep link and matching fallback", () => {
  const launch = buildCodexLaunch({
    workspacePath: "/Users/nzy/mcode/research-loop",
    nextProblemId: "QMB-007",
  });

  const parsed = new URL(launch.href);
  assert.equal(parsed.protocol, "codex:");
  assert.equal(parsed.hostname, "threads");
  assert.equal(parsed.pathname, "/new");
  assert.equal(parsed.searchParams.get("path"), "/Users/nzy/mcode/research-loop");
  assert.equal(parsed.searchParams.get("prompt"), launch.prompt);
  assert.match(launch.fallbackText, /\/Users\/nzy\/mcode\/research-loop/);
  assert.match(launch.fallbackText, /QMB-007/);
});
