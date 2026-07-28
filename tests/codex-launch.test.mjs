import assert from "node:assert/strict";
import test from "node:test";

import { buildAddProblemPrompt, buildCodexLaunch } from "../lib/problems/codex-launch.mjs";

const fixedTargetCopyPattern = new RegExp([
  "fi" + "ve\\s+problems",
  "success\\s+target",
  "all\\s+fi" + "ve\\s+files",
].join("|"), "i");

test("builds a strict issue 133 prompt with the repo path and next ID", () => {
  const prompt = buildAddProblemPrompt({
    workspacePath: "/Users/nzy/mcode/research-loop",
    nextProblemId: "Prob-007",
  });

  assert.match(prompt, /QuantumBFS\/quantum\.harness issue #133/);
  assert.match(prompt, /Prob-007/);
  assert.match(prompt, /one question at a time/i);
  assert.match(prompt, /ungameable executable gate/i);
  assert.match(prompt, /Only write files after I explicitly confirm/i);
  assert.match(prompt, /problems\/Prob-007\/problem\.json/);
  assert.doesNotMatch(prompt, fixedTargetCopyPattern);
});

test("encodes the complete problem creation safety contract", () => {
  const prompt = buildAddProblemPrompt({
    workspacePath: "/repo/research-loop",
    nextProblemId: "Prob-007",
  });

  assert.match(prompt, /schemaVersion.*exactly 1/i);
  assert.match(prompt, /id.*exactly Prob-007/i);
  assert.match(prompt, /title.*summary.*status.*gate.*provenance.*lastActivity.*createdAt.*updatedAt/is);
  assert.match(prompt, /draft.*qualifying.*accepted.*solving.*solved.*publishing.*published.*rejected.*archived/is);
  assert.match(prompt, /rejection\.kind.*automatic.*human/is);
  assert.match(prompt, /rejection\.reason/i);
  assert.match(prompt, /no unknown top-level fields/i);
  assert.match(prompt, /scan every existing problems\/Prob-NNN directory.*parseable manifest ID/is);
  assert.match(prompt, /if Prob-007 is already reserved.*stop.*do not write or overwrite/is);
  assert.match(prompt, /immediately before.*re-check.*problems\/Prob-007.*does not exist/is);
  assert.match(prompt, /prepare and validate all required problem files.*temporary staging/is);
  assert.match(prompt, /problem\.json.*last/is);
  assert.match(prompt, /atomic rename/i);
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
