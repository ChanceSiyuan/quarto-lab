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

test("encodes the complete problem creation safety contract", () => {
  const prompt = buildAddProblemPrompt({
    workspacePath: "/repo/research-loop",
    nextProblemId: "QMB-007",
  });

  assert.match(prompt, /success target (?:is|of) five problems/i);
  assert.match(prompt, /schemaVersion.*exactly 1/i);
  assert.match(prompt, /id.*exactly QMB-007/i);
  assert.match(prompt, /title.*summary.*status.*gate.*provenance.*lastActivity.*createdAt.*updatedAt/is);
  assert.match(prompt, /draft.*qualifying.*accepted.*solving.*solved.*publishing.*published.*rejected.*archived/is);
  assert.match(prompt, /rejection\.kind.*automatic.*human/is);
  assert.match(prompt, /rejection\.reason/i);
  assert.match(prompt, /no unknown top-level fields/i);
  assert.match(prompt, /scan every existing problems\/QMB-NNN directory.*parseable manifest ID/is);
  assert.match(prompt, /if QMB-007 is already reserved.*stop.*do not write or overwrite/is);
  assert.match(prompt, /immediately before.*re-check.*problems\/QMB-007.*does not exist/is);
  assert.match(prompt, /prepare and validate all five files.*temporary staging/is);
  assert.match(prompt, /problem\.json.*last/is);
  assert.match(prompt, /atomic rename/i);
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
