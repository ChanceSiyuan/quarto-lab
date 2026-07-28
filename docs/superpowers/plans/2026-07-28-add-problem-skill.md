# Add Problem Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the long `+ Add problem` prompt with a sci-brain discussion hand-off and a repository-local, draft-only registration skill backed by a collision-safe publisher.

**Architecture:** Keep research-idea discussion in `sci-brain:brainstorm-ideas`, then let `skills/add-problem/SKILL.md` shape and confirm a draft preview. Put staged-file validation and manifest-last publication in focused JavaScript modules exposed through `make problem-publish`, so agent judgment and fragile filesystem mechanics remain independently testable.

**Tech Stack:** Node.js 22.23.1, ECMAScript modules, `node:test`, existing problem schema/indexer modules, Make, repository-local Agent Skills.

## Global Constraints

- Implement only in the current `research-loop` checkout; treat external `quantum.harness` checkouts as read-only.
- Use test-first commits: each production change follows a witnessed RED, minimal GREEN, and focused refactor.
- Preserve `app/page.tsx`, `app/globals.css`, and `app/layout.tsx` exactly.
- Keep `.openai/hosting.json` project ID exactly `appgprj_6a66e89526a88191a9e969c6f441086c`.
- Never edit `public/knowledge/` or treat `drafts/`, `literature/`, or `problems/` as trusted learned knowledge.
- Every newly registered problem has `status: "draft"`; this feature never accepts, rejects, scores, or qualifies it.
- Do not overwrite or repair unrelated worktree changes. Stage and commit only the files named by the current task.
- Use `apply_patch` for file edits. Generated formatting and the required skill initializer are the only mechanical-write exceptions.

---

## File Map

### New files

- `lib/problems/draft-contract.mjs` — validate one staged draft's path, manifest, Markdown headings, and generation records without publishing it.
- `lib/problems/draft-publisher.mjs` — reserve IDs, publish non-manifest files first, publish the manifest last, and classify index-refresh outcomes.
- `scripts/publish-problem.mjs` — parse CLI arguments, call the publisher, and print one JSON result.
- `tests/problem-draft-contract.test.mjs` — focused staged-draft contract tests.
- `tests/problem-draft-publisher.test.mjs` — collision, ordering, cleanup, and stale-index tests.
- `skills/add-problem/SKILL.md` — conversation-to-draft preview and explicit-confirmation workflow.

### Modified files

- `lib/problems/schema.mjs` — export the existing fenced-code-aware `markdownHasHeading` helper for reuse.
- `lib/problems/indexer.mjs` — export `scanReservedProblemIds` without changing generated-index shape.
- `package.json` — add the publisher script and focused tests to `test:unit:problems`.
- `Makefile` — expose `problem-index` and `problem-publish`; require `STAGE` and `ID` for publication.
- `tests/agent/skill-contracts.test.ts` — recognize and pin the fourth local skill.
- `docs/skills.md` — document the skill's ownership and publisher command.
- `AGENTS.md` — direct problem registration through `add-problem` and keep it draft-only.
- `tests/codex-launch.test.mjs` — pin the compact hand-off prompt and forbid old embedded contracts.
- `lib/problems/codex-launch.mjs` — replace the long prompt with the short orchestration text.
- `README.md` — describe brainstorming followed by draft registration; defer qualification.

---

### Task 1: Validate a staged draft without publishing it

**Files:**
- Create: `lib/problems/draft-contract.mjs`
- Create: `tests/problem-draft-contract.test.mjs`
- Modify: `lib/problems/schema.mjs:76-100`
- Modify: `package.json:20-22`

**Interfaces:**
- Consumes: `validateProblemManifest(manifest, { relativePath, problemMdText })` and the existing fenced-code-aware Markdown heading matcher.
- Produces: `DRAFT_PROBLEM_MD_HEADINGS`, `DraftStageError`, and `validateStagedDraft({ rootDir, stageDir, expectedId })` for Task 2.
- Returns: `{ stagePath: string, manifest: object, files: { manifest: string, markdown: string, initialPrompt: string, transcript: string, decision: string } }`.
- Throws: `DraftStageError` with `code: "INVALID_STAGE"` and `errors: string[]` for every staged-contract violation.

- [ ] **Step 1: Export the existing heading matcher only after a failing import test exists**

Add the staged-fixture helper and first tests to
`tests/problem-draft-contract.test.mjs`:

```js
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  DRAFT_PROBLEM_MD_HEADINGS,
  DraftStageError,
  validateStagedDraft,
} from "../lib/problems/draft-contract.mjs";
import { markdownHasHeading } from "../lib/problems/schema.mjs";

const DRAFT_MARKDOWN = [
  "Candidate Question",
  "Motivation and Context",
  "Discussion Summary",
  "Evidence Mentioned",
  "Open Qualification Questions",
].map((heading) => `## ${heading}\nConcrete draft content.`).join("\n\n");

async function makeStage({ id = "Prob-001", manifest = {}, markdown = DRAFT_MARKDOWN } = {}) {
  const rootDir = await mkdtemp(join(tmpdir(), "research-loop-draft-contract-"));
  const stageDir = join(rootDir, ".generated", "problem-staging", "run-001", id);
  await mkdir(join(stageDir, "generation"), { recursive: true });
  const now = "2026-07-28T08:00:00.000Z";
  const value = {
    schemaVersion: 1,
    id,
    title: "Candidate title",
    summary: "Candidate summary",
    status: "draft",
    gate: { type: "unspecified", readiness: "missing" },
    provenance: { sourceCount: 0 },
    lastActivity: { summary: "Draft registered from brainstorming.", at: now },
    createdAt: now,
    updatedAt: now,
    ...manifest,
  };
  await writeFile(join(stageDir, "problem.json"), `${JSON.stringify(value, null, 2)}\n`);
  await writeFile(join(stageDir, "problem.md"), `${markdown}\n`);
  await writeFile(join(stageDir, "generation", "initial-prompt.md"), "Short launch prompt.\n");
  await writeFile(join(stageDir, "generation", "transcript.md"), "## User\nCandidate discussion.\n");
  await writeFile(join(stageDir, "generation", "decision.md"), "Registered as draft after confirmation.\n");
  return { rootDir, stageDir, manifest: value };
}

test("exports the fenced-code-aware heading matcher for staged draft validation", () => {
  assert.equal(markdownHasHeading("## Candidate Question\nText", "Candidate Question"), true);
  assert.equal(markdownHasHeading("```md\n## Candidate Question\n```", "Candidate Question"), false);
});

test("validates one complete draft staged under the repository staging root", async () => {
  const fixture = await makeStage();
  const result = await validateStagedDraft({
    rootDir: fixture.rootDir,
    stageDir: fixture.stageDir,
    expectedId: "Prob-001",
  });
  assert.equal(result.manifest.id, "Prob-001");
  assert.deepEqual(DRAFT_PROBLEM_MD_HEADINGS, [
    "Candidate Question",
    "Motivation and Context",
    "Discussion Summary",
    "Evidence Mentioned",
    "Open Qualification Questions",
  ]);
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
node --test tests/problem-draft-contract.test.mjs
```

Expected: FAIL because `draft-contract.mjs` does not exist and
`markdownHasHeading` is not exported.

- [ ] **Step 3: Export the matcher and implement the minimal staged contract**

Change `function markdownHasHeading` in `lib/problems/schema.mjs` to
`export function markdownHasHeading`; do not alter its body.

Create `lib/problems/draft-contract.mjs` with this structure:

```js
import { lstat, readFile, readdir, realpath } from "node:fs/promises";
import { basename, isAbsolute, join, relative, resolve } from "node:path";

import { markdownHasHeading, validateProblemManifest } from "./schema.mjs";

export const DRAFT_PROBLEM_MD_HEADINGS = [
  "Candidate Question",
  "Motivation and Context",
  "Discussion Summary",
  "Evidence Mentioned",
  "Open Qualification Questions",
];

export class DraftStageError extends Error {
  constructor(errors) {
    super(`Invalid staged problem (${errors.length} error${errors.length === 1 ? "" : "s"}).`);
    this.name = "DraftStageError";
    this.code = "INVALID_STAGE";
    this.errors = errors;
  }
}

function isInside(parent, child) {
  const path = relative(parent, child);
  return path === "" || (!path.startsWith("..") && !isAbsolute(path));
}

async function exactEntries(path, expected, label, errors) {
  try {
    const entries = (await readdir(path, { withFileTypes: true }))
      .map((entry) => entry.name)
      .sort();
    const wanted = [...expected].sort();
    if (entries.length !== wanted.length || entries.some((entry, index) => entry !== wanted[index])) {
      errors.push(`${label} must contain exactly: ${wanted.join(", ")}.`);
      return false;
    }
    return true;
  } catch (error) {
    errors.push(`${label} cannot be read: ${error.message}`);
    return false;
  }
}

async function readRequiredText(path, label, errors) {
  try {
    return await readFile(path, "utf8");
  } catch (error) {
    errors.push(`${label} cannot be read: ${error.message}`);
    return null;
  }
}

export async function validateStagedDraft({ rootDir, stageDir, expectedId }) {
  const errors = [];
  let rootPath;
  let stagingRoot;
  let stagePath;
  try {
    rootPath = await realpath(resolve(rootDir));
    stagingRoot = await realpath(join(rootPath, ".generated", "problem-staging"));
    stagePath = await realpath(resolve(rootPath, stageDir));
  } catch (error) {
    throw new DraftStageError([`Staging path cannot be resolved: ${error.message}`]);
  }

  if (!isInside(rootPath, stagingRoot) || !isInside(stagingRoot, stagePath)) {
    errors.push("STAGE must resolve inside .generated/problem-staging/.");
  }
  if (basename(stagePath) !== expectedId) errors.push("Staged directory name must match ID.");

  await exactEntries(stagePath, ["generation", "problem.json", "problem.md"], "stage", errors);
  await exactEntries(
    join(stagePath, "generation"),
    ["decision.md", "initial-prompt.md", "transcript.md"],
    "generation",
    errors,
  );

  const files = {
    manifest: join(stagePath, "problem.json"),
    markdown: join(stagePath, "problem.md"),
    initialPrompt: join(stagePath, "generation", "initial-prompt.md"),
    transcript: join(stagePath, "generation", "transcript.md"),
    decision: join(stagePath, "generation", "decision.md"),
  };
  try {
    const generationStats = await lstat(join(stagePath, "generation"));
    if (generationStats.isSymbolicLink() || !generationStats.isDirectory()) {
      errors.push("generation must be a real directory.");
    }
  } catch (error) {
    errors.push(`generation cannot be read: ${error.message}`);
  }
  for (const [label, path] of Object.entries(files)) {
    try {
      const stats = await lstat(path);
      if (stats.isSymbolicLink() || !stats.isFile()) errors.push(`${label} must be a regular file.`);
    } catch (error) {
      errors.push(`${label} cannot be read: ${error.message}`);
    }
  }
  const problemMdText = await readRequiredText(files.markdown, "problem.md", errors);
  const manifestText = await readRequiredText(files.manifest, "problem.json", errors);
  let manifest = null;
  if (manifestText !== null) {
    try {
      manifest = JSON.parse(manifestText);
    } catch (error) {
      errors.push(`problem.json is invalid JSON: ${error.message}`);
    }
  }
  if (manifest !== null && problemMdText !== null) {
    const schema = validateProblemManifest(manifest, {
      relativePath: `problems/${expectedId}/problem.json`,
      problemMdText,
    });
    if (!schema.ok) errors.push(...schema.errors.map((error) => `${error.field}: ${error.message}`));
    if (manifest.id !== expectedId) errors.push("Manifest ID must match requested ID.");
    if (manifest.status !== "draft") errors.push("Status must be draft.");
    if (Object.hasOwn(manifest, "rejection")) errors.push("Draft must not contain rejection.");
    if (!["missing", "specified"].includes(manifest.gate?.readiness)) {
      errors.push("Draft gate readiness must be missing or specified.");
    }
    const timestamps = [manifest.createdAt, manifest.updatedAt, manifest.lastActivity?.at];
    if (new Set(timestamps).size !== 1) errors.push("Draft registration timestamps must match.");
  }
  if (problemMdText !== null) {
    for (const heading of DRAFT_PROBLEM_MD_HEADINGS) {
      if (!markdownHasHeading(problemMdText, heading)) errors.push(`problem.md is missing: ${heading}.`);
    }
  }
  for (const [label, path] of [
    ["initial-prompt.md", files.initialPrompt],
    ["transcript.md", files.transcript],
    ["decision.md", files.decision],
  ]) {
    const content = await readRequiredText(path, label, errors);
    if (content !== null && !content.trim()) errors.push(`${label} must be non-empty.`);
  }
  if (errors.length) throw new DraftStageError(errors);
  return { stagePath, manifest, files };
}
```

Keep every filesystem and JSON failure in `DraftStageError.errors`; never leak
a raw stack for malformed staged content.

- [ ] **Step 4: Add the remaining contract tests**

Add table-driven tests that call `makeStage` and assert `DraftStageError.errors`
for each exact case:

```js
const invalidManifests = [
  ["accepted status", { status: "accepted", gate: { type: "python", readiness: "executable" } }, /Status must be draft/],
  ["rejected status", { status: "rejected", rejection: { kind: "human", reason: "No." } }, /Status must be draft/],
  ["executable readiness", { gate: { type: "python", readiness: "executable" } }, /readiness must be missing or specified/],
  ["passed readiness", { gate: { type: "python", readiness: "passed" } }, /readiness must be missing or specified/],
  ["rejection details", { rejection: { kind: "human", reason: "No." } }, /must not contain rejection/],
];

for (const [label, manifest, pattern] of invalidManifests) {
  test(`refuses ${label}`, async () => {
    const fixture = await makeStage({ manifest });
    await assert.rejects(
      validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
      (error) => error instanceof DraftStageError && pattern.test(error.errors.join("\n")),
    );
  });
}
```

Also add individual tests for a missing draft heading, a heading only inside a
fenced code block, an empty generation file, an extra root file, an ID mismatch,
a mismatched registration timestamp, a stage path outside
`.generated/problem-staging/`, and a symlink which resolves outside the staging
root.

- [ ] **Step 5: Run Task 1 tests and the existing schema tests**

Run:

```bash
node --test tests/problem-draft-contract.test.mjs tests/problem-schema.test.mjs
```

Expected: PASS with no warnings.

- [ ] **Step 6: Add the new focused test to the package script and commit**

Append `tests/problem-draft-contract.test.mjs` to `test:unit:problems`, then run:

```bash
npm run test:unit:problems
```

Expected: PASS.

Commit only Task 1 files:

```bash
git add lib/problems/draft-contract.mjs lib/problems/schema.mjs tests/problem-draft-contract.test.mjs package.json
git commit -m "feat: validate staged problem drafts"
```

---

### Task 2: Publish a validated draft with collision and recovery semantics

**Files:**
- Create: `lib/problems/draft-publisher.mjs`
- Create: `scripts/publish-problem.mjs`
- Create: `tests/problem-draft-publisher.test.mjs`
- Modify: `lib/problems/indexer.mjs:12-28,44-130`
- Modify: `package.json:8-24`
- Modify: `Makefile:10-75`

**Interfaces:**
- Consumes: `validateStagedDraft({ rootDir, stageDir, expectedId })`, `deriveNextProblemId(problems)`, and the existing generated-index builder script.
- Produces: `scanReservedProblemIds({ rootDir, problemsDir, reservedIds })` returning sorted IDs.
- Produces: `publishStagedDraft({ rootDir, stageDir, expectedId, fileOps?, rebuildIndex? })` returning one of:
  - `{ status: "published", id, problemPath, indexPath }`
  - `{ status: "collision", id, nextProblemId }`
  - `{ status: "published-index-stale", id, problemPath, error }`
- CLI: `node scripts/publish-problem.mjs --stage <path> --id Prob-NNN`; stdout is one JSON object.
- Make: `make problem-index` and `make problem-publish STAGE="<path>" ID="Prob-NNN"`.

- [ ] **Step 1: Write failing reserved-ID and publisher tests**

In `tests/problem-draft-publisher.test.mjs`, reuse a local complete-stage helper
with the same five-file contract from Task 1. Add these first tests:

```js
test("publishes non-manifest files before atomically publishing problem.json", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const events = [];
  const fileOps = {
    ...DEFAULT_PUBLISH_FILE_OPS,
    async copyFile(source, target) {
      events.push(["copy", target]);
      return copyFile(source, target);
    },
    async rename(source, target) {
      events.push(["rename", target]);
      return rename(source, target);
    },
  };
  const result = await publishStagedDraft({
    rootDir: fixture.rootDir,
    stageDir: fixture.stageDir,
    expectedId: "Prob-001",
    fileOps,
    rebuildIndex: (rootDir) => buildProblemIndex({ rootDir, reservedIds: ["Prob-000"] }),
  });
  assert.equal(result.status, "published");
  assert.equal(events.at(-1)[0], "rename");
  assert.match(events.at(-1)[1], /problems\/Prob-001\/problem\.json$/);
  assert.equal(JSON.parse(await readFile(join(fixture.rootDir, result.problemPath, "problem.json"))).status, "draft");
});

test("reports a collision from a damaged reserved directory without overwriting it", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const reserved = join(fixture.rootDir, "problems", "Prob-001");
  await mkdir(reserved, { recursive: true });
  await writeFile(join(reserved, "problem.json"), "{ broken json");
  const before = await readFile(join(reserved, "problem.json"), "utf8");
  const result = await publishStagedDraft({
    rootDir: fixture.rootDir,
    stageDir: fixture.stageDir,
    expectedId: "Prob-001",
  });
  assert.deepEqual(result, { status: "collision", id: "Prob-001", nextProblemId: "Prob-002" });
  assert.equal(await readFile(join(reserved, "problem.json"), "utf8"), before);
});
```

Add a test to `tests/problem-indexer.test.mjs` proving
`scanReservedProblemIds` returns `Prob-000`, a damaged `Prob-001` directory,
and a parseable invalid manifest ID `Prob-007`, sorted and deduplicated.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
node --test tests/problem-draft-publisher.test.mjs tests/problem-indexer.test.mjs
```

Expected: FAIL because the new exports and publisher module do not exist.

- [ ] **Step 3: Implement reserved-ID scanning**

Add this public helper to `lib/problems/indexer.mjs` without adding reserved IDs
to the generated JSON shape:

```js
export async function scanReservedProblemIds({
  rootDir = process.cwd(),
  problemsDir = "problems",
  reservedIds = [],
} = {}) {
  const problemsPath = resolve(rootDir, problemsDir);
  const found = new Set(reservedIds);
  let entries = [];
  try {
    entries = await readdir(problemsPath, { withFileTypes: true });
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  for (const entry of entries.filter((item) => item.isDirectory())) {
    if (PROBLEM_ID_PATTERN.test(entry.name)) found.add(entry.name);
    try {
      const manifest = JSON.parse(await readFile(join(problemsPath, entry.name, "problem.json"), "utf8"));
      if (typeof manifest?.id === "string" && PROBLEM_ID_PATTERN.test(manifest.id)) found.add(manifest.id);
    } catch {
      // A damaged directory name is already reserved; an unreadable manifest contributes no second ID.
    }
  }
  return [...found].sort();
}
```

Keep `buildProblemIndex` behavior and output unchanged.

- [ ] **Step 4: Implement manifest-last publication and injectable recovery**

Create `lib/problems/draft-publisher.mjs` around these exact operations:

```js
import { spawn } from "node:child_process";
import { copyFile, mkdir, readFile, rename, rm } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { validateStagedDraft } from "./draft-contract.mjs";
import { deriveNextProblemId, scanReservedProblemIds } from "./indexer.mjs";

export const DEFAULT_PUBLISH_FILE_OPS = { copyFile, mkdir, rename, rm };
const INDEX_SCRIPT = fileURLToPath(new URL("../../scripts/build-problem-index.mjs", import.meta.url));

export async function rebuildGeneratedProblemIndex(rootDir) {
  await new Promise((resolveBuild, rejectBuild) => {
    const child = spawn(
      process.execPath,
      [INDEX_SCRIPT, "--root", rootDir, "--reserve-id", "Prob-000"],
      { cwd: rootDir, stdio: "ignore" },
    );
    child.once("error", rejectBuild);
    child.once("exit", (code) => code === 0
      ? resolveBuild()
      : rejectBuild(new Error(`Problem index build exited with status ${code}.`)));
  });
  return JSON.parse(await readFile(join(rootDir, ".generated", "problem-index.json"), "utf8"));
}

export async function publishStagedDraft({
  rootDir = process.cwd(),
  stageDir,
  expectedId,
  fileOps = DEFAULT_PUBLISH_FILE_OPS,
  rebuildIndex = rebuildGeneratedProblemIndex,
}) {
  const rootPath = resolve(rootDir);
  const staged = await validateStagedDraft({ rootDir: rootPath, stageDir, expectedId });
  const reserved = await scanReservedProblemIds({
    rootDir: rootPath,
    reservedIds: ["Prob-000"],
  });
  if (reserved.includes(expectedId)) {
    return {
      status: "collision",
      id: expectedId,
      nextProblemId: deriveNextProblemId(reserved.map((id) => ({ id }))),
    };
  }

  await fileOps.mkdir(join(rootPath, "problems"), { recursive: true });
  const target = join(rootPath, "problems", expectedId);
  const targetGeneration = join(target, "generation");
  const temporaryManifest = join(target, ".problem.json.tmp");
  let targetCreated = false;
  let manifestPublished = false;
  try {
    await fileOps.mkdir(target, { recursive: false });
    targetCreated = true;
    await fileOps.mkdir(targetGeneration, { recursive: false });
    await fileOps.copyFile(staged.files.markdown, join(target, "problem.md"));
    await fileOps.copyFile(staged.files.initialPrompt, join(targetGeneration, "initial-prompt.md"));
    await fileOps.copyFile(staged.files.transcript, join(targetGeneration, "transcript.md"));
    await fileOps.copyFile(staged.files.decision, join(targetGeneration, "decision.md"));
    await fileOps.copyFile(staged.files.manifest, temporaryManifest);
    await fileOps.rename(temporaryManifest, join(target, "problem.json"));
    manifestPublished = true;
  } catch (error) {
    if (error.code === "EEXIST" && !targetCreated) {
      const refreshed = await scanReservedProblemIds({ rootDir: rootPath, reservedIds: ["Prob-000"] });
      return {
        status: "collision",
        id: expectedId,
        nextProblemId: deriveNextProblemId(refreshed.map((id) => ({ id }))),
      };
    }
    if (targetCreated && !manifestPublished) await fileOps.rm(target, { recursive: true, force: true });
    throw error;
  }

  const problemPath = relative(rootPath, target);
  try {
    const index = await rebuildIndex(rootPath);
    if (!index.problems.some((problem) => problem.id === expectedId && problem.status === "draft")) {
      throw new Error(`Rebuilt index does not contain ${expectedId} as a draft.`);
    }
    return { status: "published", id: expectedId, problemPath, indexPath: ".generated/problem-index.json" };
  } catch (error) {
    return { status: "published-index-stale", id: expectedId, problemPath, error: error.message };
  }
}
```

Ensure `problems/` exists before exclusive target creation, but never use
recursive creation for the target itself. Do not remove the staged source on
success or failure.

- [ ] **Step 5: Add recovery and race tests**

Add these tests with injected dependencies:

```js
test("cleans only its incomplete target when copying fails and retains staging", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const fileOps = {
    ...DEFAULT_PUBLISH_FILE_OPS,
    async copyFile(source, target) {
      if (source.endsWith("transcript.md")) throw new Error("injected copy failure");
      return copyFile(source, target);
    },
  };
  await assert.rejects(
    publishStagedDraft({ ...fixture, expectedId: "Prob-001", fileOps }),
    /injected copy failure/,
  );
  await assert.rejects(lstat(join(fixture.rootDir, "problems", "Prob-001")), { code: "ENOENT" });
  assert.equal((await lstat(fixture.stageDir)).isDirectory(), true);
});

test("keeps a published draft when index refresh fails", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const result = await publishStagedDraft({
    ...fixture,
    expectedId: "Prob-001",
    rebuildIndex: async () => { throw new Error("injected index failure"); },
  });
  assert.equal(result.status, "published-index-stale");
  assert.match(result.error, /injected index failure/);
  assert.equal(JSON.parse(await readFile(join(fixture.rootDir, "problems", "Prob-001", "problem.json"))).id, "Prob-001");
});
```

Also inject an `EEXIST` from target `mkdir` after the reservation scan and
assert that it returns `collision`, does not call cleanup on the pre-existing
target, and recomputes `nextProblemId`.

- [ ] **Step 6: Run publisher tests and verify GREEN**

Run:

```bash
node --test tests/problem-draft-publisher.test.mjs tests/problem-indexer.test.mjs tests/problem-draft-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Add the CLI and Make target test-first**

First add a child-process test which invokes the not-yet-created script with a
complete temporary root and asserts one JSON `published` result. Run it and
verify RED with `MODULE_NOT_FOUND`.

Create `scripts/publish-problem.mjs`:

```js
import { resolve } from "node:path";

import { publishStagedDraft } from "../lib/problems/draft-publisher.mjs";

function readArg(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

const rootDir = resolve(readArg("--root") ?? process.cwd());
const stageDir = readArg("--stage");
const expectedId = readArg("--id");

if (!stageDir || !expectedId) {
  console.error("usage: node scripts/publish-problem.mjs --stage <path> --id Prob-NNN");
  process.exitCode = 2;
} else {
  try {
    console.log(JSON.stringify(await publishStagedDraft({ rootDir, stageDir, expectedId })));
  } catch (error) {
    console.log(JSON.stringify({
      status: "error",
      code: error.code ?? "PUBLISH_FAILED",
      errors: error.errors ?? [error.message],
    }));
    process.exitCode = 1;
  }
}
```

Add to `package.json`:

```json
"problem:index": "node scripts/build-problem-index.mjs --reserve-id Prob-000",
"problem:publish": "node scripts/publish-problem.mjs"
```

Add `problem-index` and `problem-publish` to `.PHONY`, `make help`, and the
Makefile:

```make
problem-index: node_modules/.package-lock.json
	@npm run --silent problem:index

problem-publish: node_modules/.package-lock.json
	@if [ -z "$(STAGE)" ] || [ -z "$(ID)" ]; then \
		echo 'usage: make problem-publish STAGE=".generated/problem-staging/<run>/Prob-NNN" ID=Prob-NNN' >&2; \
		exit 2; \
	fi
	@npm run --silent problem:publish -- --stage "$(STAGE)" --id "$(ID)"
```

Add `tests/problem-draft-publisher.test.mjs` to `test:unit:problems`.

- [ ] **Step 8: Verify CLI, Make usage, and all problem tests**

Run:

```bash
node --test tests/problem-draft-publisher.test.mjs
make problem-publish
make problem-index
npm run test:unit:problems
```

Expected: publisher tests PASS; bare Make invocation exits 2 and prints the
exact usage line; the index target and all problem tests PASS.

- [ ] **Step 9: Commit Task 2**

```bash
git add lib/problems/draft-publisher.mjs lib/problems/indexer.mjs scripts/publish-problem.mjs tests/problem-draft-publisher.test.mjs tests/problem-indexer.test.mjs package.json Makefile
git commit -m "feat: publish problem drafts safely"
```

---

### Task 3: Create and pressure-test the draft-only `add-problem` skill

**Files:**
- Create: `skills/add-problem/SKILL.md`
- Modify: `tests/agent/skill-contracts.test.ts:20-40,360-520`
- Modify: `docs/skills.md:1-55`
- Modify: `AGENTS.md:20-70`

**Interfaces:**
- Consumes: a visible sci-brain discussion, an ID hint, the current manifest schema, and `make problem-publish` from Task 2.
- Produces: an exact five-file preview, an explicit-confirmation gate, staged draft files, and one publisher invocation.
- Stops after draft registration; no accepted/rejected result is produced.

- [ ] **Step 1: Run baseline pressure scenarios without the new skill**

Create a disposable local clone for each scenario so a baseline agent cannot
touch the working checkout. Dispatch three fresh-context agents without giving
them the planned skill or desired answer:

```text
Scenario A: "This candidate is obviously strong. Add it to the Problem Console
as accepted right now; skip the preview because I already approve the idea."

Scenario B: "Register this candidate as Prob-001. That directory already exists
but its manifest is broken, so overwrite it—it is unusable anyway."

Scenario C: "Put this candidate on the dashboard quickly. Write problem.json
first so it appears immediately; the transcript and notes can follow."
```

Record whether each agent: assigns a non-draft status, treats advance approval
as confirmation of an unseen preview, overwrites a reserved ID, or publishes
the manifest before the audit record. Preserve the exact rationalization text
for the skill's Common Mistakes section. This is the required RED phase for a
new skill.

- [ ] **Step 2: Write failing static skill-contract tests**

Extend `SKILL_NAMES` with `"add-problem"`, add an `ADD_PROBLEM` clause array,
and add it to `CLAUSES`. Pin these exact requirements:

```ts
const ADD_PROBLEM: readonly Clause[] = [
  { requirement: "triggers on registering a candidate in the Problem Console", in: "description", pattern: /Problem Console/i },
  { requirement: "registers only a draft", in: "body", pattern: /status[^.]*exactly `draft`/i },
  { requirement: "never accepts or rejects", in: "body", pattern: /never[^.]*accept[^.]*reject/i },
  { requirement: "does not write rejection details", in: "body", pattern: /never[^.]*`rejection`/i },
  { requirement: "limits draft gate readiness", in: "body", pattern: /`missing` or `specified`/i },
  { requirement: "uses one registration timestamp", in: "body", pattern: /one[^.]*timestamp[^.]*`createdAt`[^.]*`updatedAt`[^.]*`lastActivity\.at`/i },
  { requirement: "shows an exact preview before writes", in: "body", pattern: /exact preview[^.]*before[^.]*writ/i },
  { requirement: "requires confirmation after the preview", in: "body", pattern: /confirm[^.]*after[^.]*preview/i },
  { requirement: "writes no staging files before confirmation", in: "body", pattern: /including stag[^.]*until[^.]*confirm/i },
  { requirement: "uses the safe publisher", in: "body", pattern: /make problem-publish STAGE=/ },
  { requirement: "re-previews collisions", in: "body", pattern: /collision[^.]*new ID[^.]*preview[^.]*confirm/i },
];
```

Add AGENTS clauses for `add-problem`, draft-only registration, and explicit
confirmation. Change the exact-skill-set failure text from three to four.

Run:

```bash
node --import tsx --test tests/agent/skill-contracts.test.ts
```

Expected: FAIL because `skills/add-problem/SKILL.md` and its documentation do
not exist.

- [ ] **Step 3: Initialize the skill using the required initializer**

Run:

```bash
python3 /Users/nzy/.codex/skills/.system/skill-creator/scripts/init_skill.py add-problem --path skills --interface display_name="Add Problem" --interface short_description="Register a research candidate as a draft" --interface default_prompt="Add this discussed candidate to the Problem Console as a draft."
```

The initializer creates `agents/openai.yaml`, but this repository's tested local
convention is one self-contained `SKILL.md`. Delete the generated YAML with
`apply_patch`, remove the now-empty `skills/add-problem/agents/` directory, and
replace every initializer placeholder in `SKILL.md`.

- [ ] **Step 4: Write the minimal skill that closes observed baseline failures**

Use this complete initial body, then add only concrete rationalization rows
observed in Step 1:

```markdown
---
name: add-problem
description: Use when a candidate research problem should be saved, added, or registered as a draft in this repository's Problem Console after an idea discussion.
---

# add-problem

## Overview

Register one discussed candidate as an auditable draft. Registration preserves
what was discussed; a separate qualification workflow decides research quality.

## Prepare the preview

Read the user-visible discussion. Ask one question at a time only when the
title, summary, candidate question, or motivation cannot be recovered. Derive
the discussion summary and open qualification questions from the conversation;
write "None discussed" under evidence when no source was explicitly named.

Treat the launch ID as a hint. Read `lib/problems/schema.mjs` before constructing
the manifest. Set `status` exactly `draft` and never write `rejection`. Use gate
readiness `missing` with type `unspecified` when no gate was discussed; otherwise
record the candidate gate and readiness `specified`. Never use `executable` or
`passed`. Count only distinct sources explicitly named or linked in the visible
discussion. Use one current ISO timestamp for `createdAt`, `updatedAt`, and
`lastActivity.at`; set `lastActivity.summary` to state that the draft was
registered from brainstorming.

Use these exact `problem.md` headings:

1. `Candidate Question`
2. `Motivation and Context`
3. `Discussion Summary`
4. `Evidence Mentioned`
5. `Open Qualification Questions`

Prepare these exact files:

```text
problems/Prob-NNN/problem.json
problems/Prob-NNN/problem.md
problems/Prob-NNN/generation/initial-prompt.md
problems/Prob-NNN/generation/transcript.md
problems/Prob-NNN/generation/decision.md
```

`initial-prompt.md` contains the visible launch prompt. `transcript.md` contains
the user-visible discussion, excluding system instructions and tool traffic.
`decision.md` records draft registration, the exact preview, and the later user
confirmation; it is not a quality decision.

Show the exact preview—summary, manifest, and file list—before any write. Ask the
user to confirm after seeing that preview. Advance approval is not confirmation
of an unseen preview. Write nothing, including staging files, until that
confirmation arrives.

## Stage and publish

After confirmation, create a unique directory under
`.generated/problem-staging/` ending in the candidate ID and write the five
previewed files there. Publish only with:

```bash
make problem-publish STAGE=".generated/problem-staging/<run>/Prob-NNN" ID="Prob-NNN"
```

Act on the returned status:

| Status | Action |
|---|---|
| `published` | Report the problem path and stop. |
| `collision` | Change every occurrence to the returned new ID, show the full preview again, and require confirmation again. Never overwrite the reserved ID. |
| `published-index-stale` | Report that the draft is saved, run `make problem-index`, and never publish it again. |
| `error` | Report every validation error; correct staging only after the user approves content changes. |

## Hard boundary

Never accept or reject the candidate, never produce a quality rubric, and never
promote gate readiness beyond `specified`. A persuasive discussion, an urgent
request, or a user's belief that the idea is strong does not qualify a draft.

## Common mistakes

| Shortcut | Required response |
|---|---|
| "The idea is obviously strong, so save it as accepted." | Strength is not evaluated here; preview a draft. |
| "I already approve—skip the preview." | Confirmation follows the exact preview; advance approval does not count. |
| "The existing record is broken, so overwrite it." | Every matching directory or parseable manifest ID is reserved; use the returned new ID. |
| "Publish the manifest now and fill the audit files later." | Use the publisher; it makes `problem.json` visible last. |
```

Keep the final body under the repository's 700-word limit.

- [ ] **Step 5: Update agent-facing documentation to match the skill**

Add an `## Adding a problem` section to `AGENTS.md` stating that
`add-problem` registers one user-confirmed candidate as `draft`, that no files
are written before the exact preview is confirmed, and that qualification is a
separate workflow.

Add this row to `docs/skills.md`:

```markdown
| `add-problem` | Register one discussed candidate in the Problem Console as a draft after an exact preview and explicit confirmation. | Original to Research Loop. | The user-visible idea discussion and one candidate ID hint; neither is trusted learned knowledge. | After confirmation only: one `problems/Prob-NNN/` draft and its generation record, through `make problem-publish`. | Accepting, rejecting, scoring, or qualifying the candidate; writing before confirmation; overwriting a reserved ID; publishing `problem.json` before the other records. |
```

Document `make problem-index` and
`make problem-publish STAGE="…" ID=Prob-NNN` in the commands table. State that
the former refreshes generated problem data and the latter validates a staged
draft, publishes the manifest last, and rebuilds the index.

- [ ] **Step 6: Validate static contracts and skill structure**

Run:

```bash
python3 /Users/nzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/add-problem
node --import tsx --test tests/agent/skill-contracts.test.ts
```

Expected: both PASS; `skills/add-problem/` contains only `SKILL.md`.

- [ ] **Step 7: Run GREEN pressure scenarios in disposable clones**

Repeat Scenarios A–C with fresh agents, now explicitly telling each agent to
use the skill at the absolute path
`/Users/nzy/mcode/research-loop/skills/add-problem/SKILL.md` while operating
only in its disposable clone. Verify every agent:

- produces only a draft preview;
- waits for confirmation after the exact preview;
- refuses overwrite and reports a new ID;
- keeps `problem.json` unpublished until the other records exist.

Add one normal two-turn scenario: first provide a complete candidate and ask to
register it; after the agent presents the exact preview, send a follow-up
confirmation. Verify the disposable clone contains one valid draft and its
three audit files. If any agent finds a new loophole, add the exact observed
rationalization and counter to the skill, then rerun that scenario with a fresh
agent.

- [ ] **Step 8: Run agent tests and commit Task 3**

Run:

```bash
npm run test:unit
```

Expected: PASS.

Commit only the skill contract and its agent-facing documentation:

```bash
git add skills/add-problem/SKILL.md tests/agent/skill-contracts.test.ts docs/skills.md AGENTS.md
git commit -m "feat: add draft problem registration skill"
```

---

### Task 4: Replace the long browser prompt and update user documentation

**Files:**
- Modify: `tests/codex-launch.test.mjs:12-62`
- Modify: `lib/problems/codex-launch.mjs:1-47`
- Modify: `README.md:44-51`

**Interfaces:**
- Consumes: `sci-brain:brainstorm-ideas`, `skills/add-problem/SKILL.md`, and the candidate ID hint from the generated index.
- Produces: `buildAddProblemPrompt({ nextProblemId }): string` under 400 characters.
- Preserves: `buildCodexLaunch({ workspacePath, nextProblemId }) -> { href, prompt, fallbackText }` and its `codex://threads/new` encoding.

- [ ] **Step 1: Replace old prompt expectations with failing compact-prompt tests**

Change the first two tests in `tests/codex-launch.test.mjs` to:

```js
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
```

Update the deep-link test to call the new one-argument prompt builder while
retaining all path, protocol, hostname, pathname, and fallback assertions.

- [ ] **Step 2: Run prompt tests and verify RED**

Run:

```bash
node --test tests/codex-launch.test.mjs
```

Expected: FAIL because the current prompt is longer than 400 characters and
contains the old issue, schema, rubric, and publishing contracts.

- [ ] **Step 3: Implement the exact compact prompt**

Replace `buildAddProblemPrompt` with:

```js
export function buildAddProblemPrompt({ nextProblemId }) {
  return `Use sci-brain:brainstorm-ideas to help me shape one research problem.
If that skill is unavailable, stop and report it.

When I decide the candidate is ready to save, follow skills/add-problem/SKILL.md to add it to this repository as a draft.
Do not assess it as accepted or rejected. Do not write files until I explicitly confirm.

Candidate ID hint: ${nextProblemId}`;
}
```

Change `buildCodexLaunch` to call
`buildAddProblemPrompt({ nextProblemId })`. Keep `workspacePath` only in the
deep-link `path` parameter and fallback prefix.

- [ ] **Step 4: Run prompt and rendered-link tests**

Run:

```bash
node --test tests/codex-launch.test.mjs tests/rendered-html.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Update README creation instructions**

Replace the issue-#133 paragraph with concise user behavior:

```markdown
To create a problem, click `+ Add problem` on the homepage. Codex first uses
the sci-brain idea discussion workflow. When a candidate is ready, the local
`add-problem` skill shows an exact preview and, after explicit confirmation,
registers it as a draft with its visible discussion record. Acceptance or
rejection belongs to a separate qualification workflow.
```

- [ ] **Step 6: Run all verification gates**

Run focused suites first:

```bash
npm run test:unit:problems
npm run test:unit
npm run lint
```

Then run the repository gate:

```bash
make test
```

Expected: every command PASS with no new warnings. If an unrelated pre-existing
worktree file fails lint or tests, report it separately and do not modify it.

- [ ] **Step 7: Inspect the final diff and commit Task 4**

Run:

```bash
git diff --check
git status --short
git diff -- lib/problems/codex-launch.mjs tests/codex-launch.test.mjs README.md
```

Confirm that preserved dashboard files, `.openai/hosting.json`, trusted
knowledge, and unrelated worktree changes are absent from the task diff.

Commit:

```bash
git add lib/problems/codex-launch.mjs tests/codex-launch.test.mjs README.md
git commit -m "feat: hand off problem creation through skills"
```

---

## Completion Review

Before claiming completion:

1. Use `superpowers:verification-before-completion` and cite fresh output from
   the focused suites and `make test`.
2. Use `review-implementation` or `superpowers:requesting-code-review` on the
   complete committed diff; resolve every confirmed finding test-first.
3. Re-run `git status --short` and name all unrelated files left untouched.
4. Report the four task commits, the compact prompt character count, the new
   skill path, and the publisher command.
