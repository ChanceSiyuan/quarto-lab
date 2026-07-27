# Local Problem Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the introductory Research Loop demo with a repo-backed local problem console for issue #133.

**Architecture:** Problem directories under `problems/<id>/` remain the only business source of truth. Node ESM modules validate manifests, build a deterministic generated index, and expose a pure `ProblemRepository`; the Next app imports the generated index and renders a compact console plus a stable detail route. The add flow opens a Codex deep link with the approved strict problem-generation prompt and keeps an always-visible fallback prompt.

**Tech Stack:** Next 16.2.6 App Router, React 19.2.6, Node >=22.13.0, native `node:test`, vinext, no new npm dependencies.

## Global Constraints

- Keep the current Next.js/vinext/Cloudflare project structure.
- Do not add a database, multi-user auth, solver controls, gate execution, report viewing, delete actions, or homepage state-transition actions.
- The first version is single-user and local-only; repo files are the source of truth and Git is the audit trail.
- Browser `localStorage` must not store problems or pipeline state.
- Problem IDs use `QMB-NNN`.
- `schemaVersion` is `1`.
- Status values are `draft`, `qualifying`, `accepted`, `solving`, `solved`, `publishing`, `published`, `rejected`, and `archived`.
- `gate.readiness` values are `missing`, `specified`, `executable`, and `passed`.
- `accepted` or later statuses must have `gate.readiness` equal to `executable` or `passed`.
- Only problems with runnable gates count toward issue #133 Tier 1.
- `rejected` manifests must include `rejection.kind` as `automatic` or `human` and a non-empty `rejection.reason`.
- Unknown top-level manifest fields are invalid, except `rejection` on rejected manifests.
- The homepage defaults to hiding `rejected` and `archived`.
- The homepage shows raw Tier counts for accepted, solved, published, and rejected problems without a fixed target denominator.
- The add button uses `codex://threads/new` with URL-encoded `prompt` and absolute `path`; the link only pre-fills the Codex composer.
- Always show a "Cannot open Codex?" fallback with the same prompt and repository path.
- The problem detail route `/problems/<id>` is stable in this pass and only shows the problem identity plus the approved "details will be designed separately" message.
- Tests replace the stale starter skeleton assertions in `tests/rendered-html.test.mjs`.

---

## Scope Check

The approved spec is one local-console subsystem with five connected deliverables: file contract, generated index, repository boundary, homepage, and Codex launch. A single plan is appropriate because each task produces working software that the next task consumes, and no task requires a separate product decision.

## File Structure

- Create `lib/problems/schema.mjs`: manifest constants, status labels, schema validation, problem Markdown completeness checks, and diagnostic formatting.
- Create `lib/problems/indexer.mjs`: filesystem scanner for `problems/*`, deterministic sorting, duplicate detection, summary metrics, next ID derivation, and generated-index shape.
- Create `lib/problems/repository.mjs`: pure read API over a generated index, including search/status filtering.
- Create `lib/problems/codex-launch.mjs`: issue #133 guided prompt builder, Codex deep-link builder, and fallback text builder.
- Create `scripts/build-problem-index.mjs`: CLI that reads `problems/` and writes `.generated/problem-index.json`.
- Create `scripts/dev-problem-index.mjs`: local dev wrapper that builds the index, watches problem files, and runs `vinext dev`.
- Modify `.gitignore`: ignore `.generated/`.
- Modify `package.json`: run the index builder before lint/build/test and route dev through the watcher.
- Modify `app/page.tsx`: server page importing the generated index and rendering the console.
- Create `app/problem-console.tsx`: client component for search, status filters, table/list rendering, add Codex link, fallback prompt, and empty/error states.
- Create `app/problems/[id]/page.tsx`: detail shell route.
- Modify `app/globals.css`: replace marketing/demo styling with compact console styling.
- Modify `app/layout.tsx`: update metadata copy from intro-demo language to local console language.
- Replace `tests/rendered-html.test.mjs`: server-render smoke tests for the console.
- Create `tests/problem-schema.test.mjs`, `tests/problem-indexer.test.mjs`, `tests/problem-repository.test.mjs`, and `tests/codex-launch.test.mjs`.
- Modify `README.md`: document the local problem contract, generation workflow, and verification commands.

---

### Task 1: Manifest Schema and Markdown Gate Tests

**Files:**
- Create: `lib/problems/schema.mjs`
- Test: `tests/problem-schema.test.mjs`

**Interfaces:**
- Produces: `PROBLEM_STATUSES: string[]`
- Produces: `VISIBLE_STATUS_LABELS: Record<string, string>`
- Produces: `GATE_READINESS: string[]`
- Produces: `ACTIVE_WITH_GATE_STATUSES: string[]`
- Produces: `REQUIRED_PROBLEM_MD_HEADINGS: string[]`
- Produces: `validateProblemManifest(manifest: unknown, context?: { relativePath?: string, problemMdText?: string | null }): { ok: true, value: object } | { ok: false, errors: Array<{ relativePath: string, field: string, message: string }> }`
- Produces: `isRunnableGate(readiness: string): boolean`
- Produces: `isAcceptedOrLater(status: string): boolean`

- [ ] **Step 1: Write failing schema tests**

Use `apply_patch` to add `tests/problem-schema.test.mjs` with this content:

```js
import assert from "node:assert/strict";
import test from "node:test";

import {
  ACTIVE_WITH_GATE_STATUSES,
  PROBLEM_STATUSES,
  REQUIRED_PROBLEM_MD_HEADINGS,
  validateProblemManifest,
} from "../lib/problems/schema.mjs";

const completeProblemMd = REQUIRED_PROBLEM_MD_HEADINGS
  .map((heading) => `## ${heading}\nConcrete content for ${heading}.`)
  .join("\n\n");

function manifest(overrides = {}) {
  return {
    schemaVersion: 1,
    id: "QMB-001",
    title: "Certified timestep bounds for 1D lattice dynamics",
    summary: "Tighter machine-checkable bounds for fresh simulation instances.",
    status: "draft",
    gate: {
      type: "interval-arithmetic",
      readiness: "specified",
    },
    provenance: {
      sourceCount: 3,
    },
    lastActivity: {
      summary: "Problem draft created by Codex.",
      at: "2026-07-27T10:00:00Z",
    },
    createdAt: "2026-07-27T10:00:00Z",
    updatedAt: "2026-07-27T10:00:00Z",
    ...overrides,
  };
}

test("accepts every lifecycle status with its required conditional fields", () => {
  for (const status of PROBLEM_STATUSES) {
    const readiness = ACTIVE_WITH_GATE_STATUSES.includes(status)
      ? "executable"
      : "specified";
    const candidate = manifest({
      status,
      gate: { type: "interval-arithmetic", readiness },
      ...(status === "rejected"
        ? { rejection: { kind: "automatic", reason: "No ungameable executable gate." } }
        : {}),
    });

    const result = validateProblemManifest(candidate, {
      relativePath: `problems/${status}/problem.json`,
      problemMdText: ACTIVE_WITH_GATE_STATUSES.includes(status) ? completeProblemMd : null,
    });

    assert.equal(result.ok, true, status);
  }
});

test("rejects unknown top-level manifest fields", () => {
  const result = validateProblemManifest(manifest({ typoStatus: "accepted" }));

  assert.equal(result.ok, false);
  assert.deepEqual(result.errors.map((error) => error.field), ["typoStatus"]);
  assert.match(result.errors[0].message, /Unknown top-level field/);
});

test("requires executable or passed gate readiness for accepted and later statuses", () => {
  const result = validateProblemManifest(
    manifest({
      status: "accepted",
      gate: { type: "interval-arithmetic", readiness: "specified" },
    }),
    { problemMdText: completeProblemMd },
  );

  assert.equal(result.ok, false);
  assert.match(result.errors.map((error) => error.field).join(","), /gate\.readiness/);
});

test("requires rejection kind and reason when status is rejected", () => {
  const result = validateProblemManifest(manifest({ status: "rejected" }));

  assert.equal(result.ok, false);
  assert.match(result.errors.map((error) => error.field).join(","), /rejection/);
});

test("requires complete problem markdown for accepted and later statuses", () => {
  const result = validateProblemManifest(manifest({ status: "solved" }), {
    problemMdText: "## Background and Gap\nOnly one section.",
  });

  assert.equal(result.ok, false);
  assert.match(result.errors.map((error) => error.field).join(","), /problem\.md/);
});
```

- [ ] **Step 2: Run the schema tests to see the intended failure**

Run:

```bash
node --test tests/problem-schema.test.mjs
```

Expected: fail because `../lib/problems/schema.mjs` does not exist.

- [ ] **Step 3: Implement schema validation**

Use `apply_patch` to add `lib/problems/schema.mjs`. Include these constants and validation rules:

```js
export const PROBLEM_STATUSES = [
  "draft",
  "qualifying",
  "accepted",
  "solving",
  "solved",
  "publishing",
  "published",
  "rejected",
  "archived",
];

export const VISIBLE_STATUS_LABELS = {
  draft: "Draft",
  qualifying: "Qualifying",
  accepted: "Accepted",
  solving: "Solving",
  solved: "Solved",
  publishing: "Publishing",
  published: "Published",
  rejected: "Rejected",
  archived: "Archived",
};

export const GATE_READINESS = ["missing", "specified", "executable", "passed"];
export const ACTIVE_WITH_GATE_STATUSES = [
  "accepted",
  "solving",
  "solved",
  "publishing",
  "published",
];
export const SOLVED_OR_LATER_STATUSES = ["solved", "publishing", "published"];
export const PUBLISHED_STATUSES = ["published"];
export const REJECTION_KINDS = ["automatic", "human"];

export const REQUIRED_PROBLEM_MD_HEADINGS = [
  "Background and Gap",
  "Research Objective",
  "Publication Threshold",
  "Executable Gate",
  "Novelty Evidence",
  "Provenance",
  "Fresh Evaluation Plan",
];
```

The implementation must:

- Return every diagnostic as `{ relativePath, field, message }`.
- Validate required top-level fields exactly: `schemaVersion`, `id`, `title`, `summary`, `status`, `gate`, `provenance`, `lastActivity`, `createdAt`, `updatedAt`; allow `rejection` only when `status` is `rejected`.
- Validate `id` with `/^QMB-\d{3}$/`.
- Validate `createdAt`, `updatedAt`, and `lastActivity.at` with `Date.parse`.
- Validate `provenance.sourceCount` as a non-negative integer.
- Validate `gate.type` as a non-empty string and `gate.readiness` as one of `GATE_READINESS`.
- Require `gate.readiness` of `executable` or `passed` for `ACTIVE_WITH_GATE_STATUSES`.
- Require `rejection.kind` and `rejection.reason` for `rejected`.
- Require all `REQUIRED_PROBLEM_MD_HEADINGS` to appear as Markdown headings for `ACTIVE_WITH_GATE_STATUSES`.
- Preserve the manifest object as `value` only when there are no errors.

- [ ] **Step 4: Run the schema tests to verify the contract**

Run:

```bash
node --test tests/problem-schema.test.mjs
```

Expected: pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add lib/problems/schema.mjs tests/problem-schema.test.mjs
git commit -m "feat: add problem manifest schema"
```

---

### Task 2: Deterministic Problem Index Builder

**Files:**
- Create: `lib/problems/indexer.mjs`
- Create: `scripts/build-problem-index.mjs`
- Create: `scripts/dev-problem-index.mjs`
- Modify: `.gitignore`
- Modify: `package.json`
- Test: `tests/problem-indexer.test.mjs`

**Interfaces:**
- Consumes: `validateProblemManifest()`, `ACTIVE_WITH_GATE_STATUSES`, `SOLVED_OR_LATER_STATUSES`, `PUBLISHED_STATUSES`
- Produces: `buildProblemIndex(options?: { rootDir?: string }): Promise<ProblemIndex>`
- Produces: `deriveNextProblemId(problems: Array<{ id: string }>): string`
- Produces: generated JSON at `.generated/problem-index.json`
- `ProblemIndex` shape:

```js
{
  schemaVersion: 1,
  generatedAt: "2026-07-27T10:00:00.000Z",
  workspacePath: "/Users/nzy/mcode/research-loop",
  nextProblemId: "QMB-001",
  problems: [],
  summary: {
    total: 0,
    accepted: 0,
    solved: 0,
    published: 0,
    rejected: 0,
    archived: 0
  },
  diagnostics: []
}
```

- [ ] **Step 1: Write failing indexer tests**

Use `apply_patch` to add `tests/problem-indexer.test.mjs`:

```js
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { buildProblemIndex, deriveNextProblemId } from "../lib/problems/indexer.mjs";
import { REQUIRED_PROBLEM_MD_HEADINGS } from "../lib/problems/schema.mjs";

const completeProblemMd = REQUIRED_PROBLEM_MD_HEADINGS
  .map((heading) => `## ${heading}\nConcrete content.`)
  .join("\n\n");

async function makeRoot() {
  const root = await mkdtempDisposable();
  await mkdir(join(root, "problems"), { recursive: true });
  return root;
}

async function mkdtempDisposable() {
  const { mkdtemp } = await import("node:fs/promises");
  return mkdtemp(join(tmpdir(), "research-loop-index-"));
}

async function writeProblem(root, id, manifestOverrides = {}, problemMd = completeProblemMd) {
  const dir = join(root, "problems", id);
  await mkdir(join(dir, "generation"), { recursive: true });
  const manifest = {
    schemaVersion: 1,
    id,
    title: `${id} title`,
    summary: `${id} summary`,
    status: "draft",
    gate: { type: "interval-arithmetic", readiness: "specified" },
    provenance: { sourceCount: 3 },
    lastActivity: { summary: "Created", at: "2026-07-27T10:00:00Z" },
    createdAt: "2026-07-27T10:00:00Z",
    updatedAt: "2026-07-27T10:00:00Z",
    ...manifestOverrides,
  };
  await writeFile(join(dir, "problem.json"), JSON.stringify(manifest, null, 2));
  await writeFile(join(dir, "problem.md"), problemMd);
}

test("builds a deterministic index and summary from problem directories", async () => {
  const root = await makeRoot();
  await writeProblem(root, "QMB-002", {
    status: "published",
    gate: { type: "python", readiness: "passed" },
    updatedAt: "2026-07-27T12:00:00Z",
  });
  await writeProblem(root, "QMB-001", {
    status: "accepted",
    gate: { type: "interval-arithmetic", readiness: "executable" },
    updatedAt: "2026-07-27T12:00:00Z",
  });
  await writeProblem(root, "QMB-003", {
    status: "rejected",
    rejection: { kind: "human", reason: "Novelty did not survive comparison." },
    updatedAt: "2026-07-27T11:00:00Z",
  }, "## Candidate\nRejected with evidence.");

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems.map((problem) => problem.id), ["QMB-001", "QMB-002", "QMB-003"]);
  assert.deepEqual(index.summary, {
    total: 3,
    accepted: 2,
    solved: 1,
    published: 1,
    rejected: 1,
    archived: 0,
  });
  assert.equal(index.nextProblemId, "QMB-004");
  assert.deepEqual(index.diagnostics, []);
});

test("isolates damaged manifests and duplicate IDs", async () => {
  const root = await makeRoot();
  await writeProblem(root, "QMB-001");
  await writeProblem(root, "QMB-002", { id: "QMB-001" });
  await mkdir(join(root, "problems", "QMB-003"), { recursive: true });
  await writeFile(join(root, "problems", "QMB-003", "problem.json"), "{ broken json");

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems.map((problem) => problem.id), ["QMB-001"]);
  assert.equal(index.diagnostics.length, 2);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Duplicate problem id/);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Invalid JSON/);
});

test("handles an empty repository and derives the first ID", async () => {
  const root = await makeRoot();
  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems, []);
  assert.equal(index.nextProblemId, "QMB-001");
  assert.equal(deriveNextProblemId([{ id: "QMB-009" }, { id: "QMB-011" }]), "QMB-012");
});
```

- [ ] **Step 2: Run the indexer tests to see the intended failure**

Run:

```bash
node --test tests/problem-indexer.test.mjs
```

Expected: fail because `../lib/problems/indexer.mjs` does not exist.

- [ ] **Step 3: Implement the indexer**

Use `apply_patch` to add `lib/problems/indexer.mjs`. The module must:

```js
import { readFile, readdir } from "node:fs/promises";
import { join, relative } from "node:path";
import {
  ACTIVE_WITH_GATE_STATUSES,
  PUBLISHED_STATUSES,
  SOLVED_OR_LATER_STATUSES,
  validateProblemManifest,
} from "./schema.mjs";

export function deriveNextProblemId(problems) {
  const max = problems.reduce((current, problem) => {
    const match = /^QMB-(\d{3})$/.exec(problem.id);
    return match ? Math.max(current, Number(match[1])) : current;
  }, 0);
  return `QMB-${String(max + 1).padStart(3, "0")}`;
}
```

Implement `buildProblemIndex({ rootDir = process.cwd() } = {})` so it:

- Reads `problems/` with `{ withFileTypes: true }`.
- Treats a missing `problems/` directory as an empty problem set.
- Reads each `problem.json` and its sibling `problem.md`.
- Emits diagnostics with repository-relative paths such as `problems/QMB-002/problem.json`.
- Rejects directory-name and manifest-ID mismatches.
- Rejects duplicate manifest IDs and keeps only the first valid problem by sorted directory order.
- Calls `validateProblemManifest(manifest, { relativePath, problemMdText })`.
- Sorts valid problems by `updatedAt` descending, then `id` ascending.
- Computes summary counts with target `5`.
- Returns the `ProblemIndex` shape declared above.

- [ ] **Step 4: Add the generated-index build script**

Use `apply_patch` to add `scripts/build-problem-index.mjs`. It must parse optional `--root` and `--out` arguments, default to the current repository and `.generated/problem-index.json`, call `buildProblemIndex()`, create the output directory, and write pretty JSON ending in a newline.

The CLI parsing contract:

```js
function readArg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index === -1 ? fallback : process.argv[index + 1];
}
```

After writing, print one line:

```text
problem index: wrote .generated/problem-index.json
```

- [ ] **Step 5: Add the dev watcher wrapper**

Use `apply_patch` to add `scripts/dev-problem-index.mjs`. It must:

- Run `node scripts/build-problem-index.mjs` once before starting the dev server.
- Spawn `vinext dev` with `WRANGLER_LOG_PATH=.wrangler/wrangler.log`.
- Watch `problems/` when it exists and the repo root otherwise.
- Debounce rebuilds by 150 ms.
- Forward `SIGINT` and `SIGTERM` to the child process.
- Exit with the child process status.

- [ ] **Step 6: Wire scripts and ignored generated output**

Use `apply_patch` to modify `.gitignore`:

```gitignore
# generated local problem index
/.generated/
```

Use `apply_patch` to modify `package.json` scripts:

```json
{
  "dev": "node scripts/dev-problem-index.mjs",
  "build": "node scripts/build-problem-index.mjs && WRANGLER_LOG_PATH=.wrangler/wrangler.log vinext build",
  "test": "node --test tests/problem-schema.test.mjs tests/problem-indexer.test.mjs tests/problem-repository.test.mjs tests/codex-launch.test.mjs && npm run build && node --test tests/rendered-html.test.mjs",
  "lint": "node scripts/build-problem-index.mjs && eslint . --ignore-pattern dist --ignore-pattern .next --ignore-pattern .generated"
}
```

Do not change dependency versions.

- [ ] **Step 7: Run Task 2 tests**

Run:

```bash
node --test tests/problem-schema.test.mjs tests/problem-indexer.test.mjs
node scripts/build-problem-index.mjs
```

Expected: both test files pass and `.generated/problem-index.json` is created.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add .gitignore package.json lib/problems/indexer.mjs scripts/build-problem-index.mjs scripts/dev-problem-index.mjs tests/problem-indexer.test.mjs
git commit -m "feat: build deterministic problem index"
```

---

### Task 3: Repository Filtering and Codex Launch Contract

**Files:**
- Create: `lib/problems/repository.mjs`
- Create: `lib/problems/codex-launch.mjs`
- Test: `tests/problem-repository.test.mjs`
- Test: `tests/codex-launch.test.mjs`

**Interfaces:**
- Consumes: generated `ProblemIndex`
- Produces: `createProblemRepository(index: ProblemIndex): ProblemRepository`
- Produces: `ProblemRepository.listProblems(filters?: { query?: string, statuses?: string[], includeRejected?: boolean, includeArchived?: boolean }): ProblemView[]`
- Produces: `ProblemRepository.getSummary(): object`
- Produces: `ProblemRepository.getIndexDiagnostics(): object[]`
- Produces: `ProblemRepository.getProblem(id: string): ProblemView | null`
- Produces: `buildAddProblemPrompt(options: { workspacePath: string, nextProblemId: string }): string`
- Produces: `buildCodexLaunch(options: { workspacePath: string, nextProblemId: string }): { href: string, prompt: string, fallbackText: string }`

- [ ] **Step 1: Write failing repository tests**

Use `apply_patch` to add `tests/problem-repository.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import { createProblemRepository } from "../lib/problems/repository.mjs";

const index = {
  schemaVersion: 1,
  generatedAt: "2026-07-27T10:00:00.000Z",
  workspacePath: "/repo/research-loop",
  nextProblemId: "QMB-004",
  summary: { total: 3, accepted: 1, solved: 0, published: 0, rejected: 1, archived: 1 },
  diagnostics: [{ relativePath: "problems/QMB-099/problem.json", field: "status", message: "Invalid status." }],
  problems: [
    { id: "QMB-001", title: "Fresh Hamiltonian gate", summary: "Interval arithmetic gate.", status: "accepted", gate: { type: "interval-arithmetic", readiness: "executable" }, provenance: { sourceCount: 3 }, lastActivity: { summary: "Accepted", at: "2026-07-27T10:00:00Z" }, updatedAt: "2026-07-27T10:00:00Z", createdAt: "2026-07-27T09:00:00Z" },
    { id: "QMB-002", title: "Rejected catalog duplicate", summary: "Novelty failed.", status: "rejected", gate: { type: "python", readiness: "specified" }, provenance: { sourceCount: 2 }, lastActivity: { summary: "Rejected", at: "2026-07-27T11:00:00Z" }, updatedAt: "2026-07-27T11:00:00Z", createdAt: "2026-07-27T09:00:00Z", rejection: { kind: "human", reason: "Duplicate." } },
    { id: "QMB-003", title: "Archived benchmark", summary: "Paused line.", status: "archived", gate: { type: "python", readiness: "missing" }, provenance: { sourceCount: 1 }, lastActivity: { summary: "Archived", at: "2026-07-27T12:00:00Z" }, updatedAt: "2026-07-27T12:00:00Z", createdAt: "2026-07-27T09:00:00Z" },
  ],
};

test("defaults to hiding rejected and archived problems", () => {
  const repository = createProblemRepository(index);

  assert.deepEqual(repository.listProblems().map((problem) => problem.id), ["QMB-001"]);
});

test("filters by query and explicit statuses", () => {
  const repository = createProblemRepository(index);

  assert.deepEqual(repository.listProblems({ query: "duplicate", includeRejected: true }).map((problem) => problem.id), ["QMB-002"]);
  assert.deepEqual(repository.listProblems({ statuses: ["archived"], includeArchived: true }).map((problem) => problem.id), ["QMB-003"]);
});

test("returns summary, diagnostics, and individual problems without mutation", () => {
  const repository = createProblemRepository(index);

  assert.equal(repository.getSummary().accepted, 1);
  assert.equal(repository.getIndexDiagnostics()[0].relativePath, "problems/QMB-099/problem.json");
  assert.equal(repository.getProblem("QMB-001").title, "Fresh Hamiltonian gate");
  assert.equal(repository.getProblem("QMB-404"), null);
});
```

- [ ] **Step 2: Write failing Codex launch tests**

Use `apply_patch` to add `tests/codex-launch.test.mjs`:

```js
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
```

- [ ] **Step 3: Run repository and Codex tests to see the intended failures**

Run:

```bash
node --test tests/problem-repository.test.mjs tests/codex-launch.test.mjs
```

Expected: fail because `repository.mjs` and `codex-launch.mjs` do not exist.

- [ ] **Step 4: Implement repository filtering**

Use `apply_patch` to add `lib/problems/repository.mjs`. The implementation must:

```js
function normalizeQuery(query) {
  return String(query ?? "").trim().toLowerCase();
}

function matchesQuery(problem, query) {
  if (!query) return true;
  return [problem.id, problem.title, problem.summary]
    .join(" ")
    .toLowerCase()
    .includes(query);
}

export function createProblemRepository(index) {
  const problems = Array.isArray(index.problems) ? [...index.problems] : [];
  return {
    listProblems(filters = {}) {
      const query = normalizeQuery(filters.query);
      const statuses = Array.isArray(filters.statuses) ? new Set(filters.statuses) : null;
      return problems.filter((problem) => {
        if (!filters.includeRejected && problem.status === "rejected") return false;
        if (!filters.includeArchived && problem.status === "archived") return false;
        if (statuses && !statuses.has(problem.status)) return false;
        return matchesQuery(problem, query);
      });
    },
    getSummary() {
      return { ...index.summary };
    },
    getIndexDiagnostics() {
      return Array.isArray(index.diagnostics) ? index.diagnostics.map((item) => ({ ...item })) : [];
    },
    getProblem(id) {
      return problems.find((problem) => problem.id === id) ?? null;
    },
  };
}
```

- [ ] **Step 5: Implement the Codex launch helper**

Use `apply_patch` to add `lib/problems/codex-launch.mjs`. The prompt must include these instructions as concrete text:

```text
You are helping create one new Research Loop problem for QuantumBFS/quantum.harness issue #133.
Work inside this repository path:
<workspacePath>

Use candidate ID <nextProblemId>.
Ask me one question at a time.
Reject candidates that cannot be expressed as an ungameable executable gate.
Check literature basis, research value, novelty, executable gate, and fresh evaluation before recommending acceptance.
Before writing files, show the final summary, rubric result, and exact file list.
Only write files after I explicitly confirm.
If the candidate is accepted, write:
problems/<nextProblemId>/problem.json
problems/<nextProblemId>/problem.md
problems/<nextProblemId>/generation/initial-prompt.md
problems/<nextProblemId>/generation/transcript.md
problems/<nextProblemId>/generation/decision.md
If the candidate is rejected, still write the same directory with status rejected, rejection.kind, rejection.reason, and the generation record after I confirm saving the rejection.
After writing, run the manifest validation from this repo and report the result.
```

Build the deep link with:

```js
const params = new URLSearchParams({ prompt, path: workspacePath });
const href = `codex://threads/new?${params.toString()}`;
```

The fallback text must contain the workspace path, the same prompt, and one sentence telling the user to open a new Codex task in that repository and paste the prompt.

- [ ] **Step 6: Run Task 3 tests**

Run:

```bash
node --test tests/problem-repository.test.mjs tests/codex-launch.test.mjs
```

Expected: pass.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add lib/problems/repository.mjs lib/problems/codex-launch.mjs tests/problem-repository.test.mjs tests/codex-launch.test.mjs
git commit -m "feat: add problem repository and codex launch"
```

---

### Task 4: Homepage Problem Console

**Files:**
- Modify: `app/page.tsx`
- Create: `app/problem-console.tsx`
- Modify: `app/globals.css`
- Modify: `app/layout.tsx`
- Test: `tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: `.generated/problem-index.json`
- Consumes: `createProblemRepository(index)`
- Consumes: `buildCodexLaunch({ workspacePath, nextProblemId })`
- Produces: `ProblemConsole(props: { initialProblems, summary, diagnostics, generatedAt, workspacePath, launch })`

- [ ] **Step 1: Replace the stale rendered HTML tests**

Use `apply_patch` to replace `tests/rendered-html.test.mjs`. Keep the existing `render()` helper shape and change assertions to the console:

```js
import assert from "node:assert/strict";
import test from "node:test";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${pathname}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the problem console shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Research Loop/);
  assert.match(html, /Problem Console/);
  assert.match(html, />\+ Add problem<\/a>/);
  assert.match(html, /Cannot open Codex\?/);
  assert.match(html, /codex:\/\/threads\/new/);
  assert.match(html, /Accepted/);
  assert.match(html, /Solved/);
  assert.match(html, /Published/);
  assert.doesNotMatch(html, /Turn open literature into/);
  assert.doesNotMatch(html, /Reset demo/);
  assert.doesNotMatch(html, /localStorage/);
});
```

- [ ] **Step 2: Run the rendered test to see the intended failure**

Run:

```bash
npm run build
node --test tests/rendered-html.test.mjs
```

Expected: fail because the current homepage still renders the old demo.

- [ ] **Step 3: Replace `app/page.tsx` with a server data boundary**

Use `apply_patch` to replace `app/page.tsx` with a server component that imports the generated index and passes serializable props:

```tsx
import generatedIndex from "../.generated/problem-index.json";
import { buildCodexLaunch } from "@/lib/problems/codex-launch.mjs";
import { createProblemRepository } from "@/lib/problems/repository.mjs";
import { ProblemConsole } from "./problem-console";

export default function Home() {
  const repository = createProblemRepository(generatedIndex);
  const launch = buildCodexLaunch({
    workspacePath: generatedIndex.workspacePath,
    nextProblemId: generatedIndex.nextProblemId,
  });

  return (
    <ProblemConsole
      generatedAt={generatedIndex.generatedAt}
      workspacePath={generatedIndex.workspacePath}
      initialProblems={repository.listProblems({ includeRejected: true, includeArchived: true })}
      summary={repository.getSummary()}
      diagnostics={repository.getIndexDiagnostics()}
      launch={launch}
    />
  );
}
```

- [ ] **Step 4: Create `ProblemConsole` client component**

Use `apply_patch` to add `app/problem-console.tsx`. It must:

- Start with `"use client";`.
- Use React state for `query`, `selectedStatuses`, `showRejected`, and `showArchived`.
- Compute visible problems in-memory from `initialProblems`.
- Default-hide `rejected` and `archived`.
- Render a top bar, metric strip, toolbar, diagnostics region, empty state, no-results state, semantic desktop table, and narrow-screen list using the same DOM order.
- Make each row link to `/problems/${problem.id}`.
- Render the primary add control as `<a className="primary-action" href={launch.href}>+ Add problem</a>`.
- Render an always-visible `<details className="codex-fallback">` with summary text `Cannot open Codex?` and a read-only `<textarea>` containing `launch.fallbackText`.

Use this status label helper inside the component:

```tsx
const statusLabels: Record<string, string> = {
  draft: "Draft",
  qualifying: "Qualifying",
  accepted: "Accepted",
  solving: "Solving",
  solved: "Solved",
  publishing: "Publishing",
  published: "Published",
  rejected: "Rejected",
  archived: "Archived",
};
```

The metric strip labels must be `Total`, `Accepted`, `Solved`, `Published`, and `Rejected`.

- [ ] **Step 5: Replace demo CSS with compact console CSS**

Use `apply_patch` to replace `app/globals.css`. Keep the existing variables `--ink`, `--muted`, `--paper`, `--surface`, `--line`, `--green`, and `--lime`, and add status colors that are not only green:

```css
:root {
  --ink: #17211d;
  --muted: #65716c;
  --paper: #f3f0e8;
  --surface: #fbfaf6;
  --line: #d9d7ce;
  --green: #174c3b;
  --lime: #c8f06f;
  --amber: #9a6a18;
  --red: #9f342c;
  --blue: #315b8f;
}
```

The CSS must include:

- `.console-shell` as a full-page layout with constrained content width.
- `.console-topbar` as a compact grid with brand, local mode, and index health.
- `.metric-strip` as a five-column responsive grid.
- `.console-toolbar` with labeled search, checkbox filter chips, and the add action.
- `.problem-table` for desktop with semantic table styling.
- `.problem-list` hidden on desktop and visible under `760px`.
- `.diagnostics` with clear error text and file paths.
- `.empty-state` and `.no-results` states.
- `.codex-fallback textarea` with fixed minimum height and monospace font.
- `:focus-visible` styles and `@media (prefers-reduced-motion: reduce)`.

- [ ] **Step 6: Update metadata copy**

Use `apply_patch` to modify `app/layout.tsx`:

```ts
const description =
  "A local problem console for generating, qualifying, solving, and publishing auditable research problems.";
```

Set Open Graph and Twitter titles to `Research Loop Problem Console`.

- [ ] **Step 7: Run Task 4 verification**

Run:

```bash
npm run build
node --test tests/rendered-html.test.mjs
```

Expected: pass.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add app/page.tsx app/problem-console.tsx app/globals.css app/layout.tsx tests/rendered-html.test.mjs
git commit -m "feat: replace homepage with problem console"
```

---

### Task 5: Problem Detail Shell and README Contract

**Files:**
- Create: `app/problems/[id]/page.tsx`
- Modify: `app/globals.css`
- Modify: `README.md`
- Test: `tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: `.generated/problem-index.json`
- Consumes: `createProblemRepository(index).getProblem(id)`
- Produces: stable route `/problems/<id>`

- [ ] **Step 1: Extend rendered tests for the detail shell**

Use `apply_patch` to add this test to `tests/rendered-html.test.mjs`:

```js
test("returns a stable detail route response for unknown problem IDs", async () => {
  const response = await render("/problems/QMB-999");
  assert.equal(response.status, 404);
});
```

If the repository has no committed problem fixtures, this verifies the route exists and uses Next's not-found behavior for unknown IDs. Detail rendering for valid IDs is covered manually after adding the first real problem.

- [ ] **Step 2: Run the route test to see the intended failure**

Run:

```bash
npm run build
node --test tests/rendered-html.test.mjs
```

Expected: fail because `/problems/[id]` does not exist.

- [ ] **Step 3: Add the detail shell route**

Use `apply_patch` to add `app/problems/[id]/page.tsx`:

```tsx
import generatedIndex from "../../../.generated/problem-index.json";
import { createProblemRepository } from "@/lib/problems/repository.mjs";
import { notFound } from "next/navigation";

export default async function ProblemDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const repository = createProblemRepository(generatedIndex);
  const problem = repository.getProblem(id);

  if (!problem) {
    notFound();
  }

  return (
    <main className="detail-shell">
      <a className="back-link" href="/">← Back to problems</a>
      <p className="eyebrow">{problem.id}</p>
      <h1>{problem.title}</h1>
      <p className="detail-summary">{problem.summary}</p>
      <section className="detail-panel" aria-labelledby="detail-status-heading">
        <h2 id="detail-status-heading">Problem detail</h2>
        <p>The detailed problem workspace will be designed next; this page currently locks the route, identity, and return path.</p>
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Add detail route styles**

Use `apply_patch` to add CSS for `.detail-shell`, `.back-link`, `.detail-summary`, and `.detail-panel`. Keep the shell compact and reuse the console colors.

- [ ] **Step 5: Document the local problem contract**

Use `apply_patch` to update `README.md` with:

````md
## Local Problem Console

Problems live in `problems/<id>/` and are indexed into `.generated/problem-index.json` before dev, lint, build, and test commands. The generated index is ignored by Git; `problem.json`, `problem.md`, and `generation/` records are the durable audit trail.

Run locally:

```bash
npm run dev
```

Validate and build:

```bash
npm run lint
npm test
```

To create a problem, click `+ Add problem` on the homepage. Codex opens a new task with the issue #133 context prefilled; send it, answer one question at a time, and only allow file writes after reviewing the proposed manifest, Markdown, generation record, and rubric decision.
````

- [ ] **Step 6: Run Task 5 verification**

Run:

```bash
npm run build
node --test tests/rendered-html.test.mjs
```

Expected: pass.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
git add app/problems/[id]/page.tsx app/globals.css README.md tests/rendered-html.test.mjs
git commit -m "feat: add problem detail route shell"
```

---

### Task 6: Full Verification and Manual Acceptance Pass

**Files:**
- Modify only if verification exposes a defect in files from Tasks 1-5.

**Interfaces:**
- Consumes: all implemented task outputs.
- Produces: verified local console branch with clean worktree.

- [ ] **Step 1: Run all automated checks**

Run:

```bash
npm run lint
npm test
```

Expected: both commands pass.

- [ ] **Step 2: Start the local dev server**

Run:

```bash
npm run dev
```

Expected: the command prints the local URL for vinext/Next development. Keep this process running until the manual checks below are complete.

- [ ] **Step 3: Manually check the homepage**

In a browser, open the local URL printed by `npm run dev` and verify:

- The first screen is the problem console, not a marketing hero.
- The metric strip shows total, accepted, solved, published, and rejected.
- Empty problem library copy appears when `problems/` has no valid manifests.
- Search input and status filters are keyboard reachable.
- `Cannot open Codex?` expands and shows the fallback prompt.
- The add action points at `codex://threads/new`.

- [ ] **Step 4: Manually check the Codex launch**

Click `+ Add problem` and verify:

- Codex opens a new task.
- The task uses `/Users/nzy/mcode/research-loop` as the repository path.
- The composer is prefilled and not auto-sent.
- The prompt asks one question at a time.
- The prompt requires an ungameable executable gate.
- The prompt requires explicit confirmation before writing.

- [ ] **Step 5: Manually check a fixture problem**

Create a temporary accepted problem directory through the Codex flow or by applying the same schema by hand during verification. Use ID `QMB-001` only if it is unused. After the directory is present, wait for the dev watcher to rebuild `.generated/problem-index.json`, refresh the page, and verify:

- The problem appears in the table.
- The accepted metric increments toward `5`.
- The row links to `/problems/QMB-001`.
- The detail route shows ID, title, summary, and the route-shell message.

- [ ] **Step 6: Manually check a rejected fixture**

Create a rejected problem directory with `rejection.kind` and `rejection.reason`, refresh the page, and verify:

- It is hidden by default.
- It appears after enabling rejected problems.
- The rejected metric increments.
- The rejection is not deleted or hidden from the generated diagnostics.

- [ ] **Step 7: Remove manual fixture directories only if they were created solely for verification**

Use a recoverable or explicit deletion step scoped to the exact verification-only directories. Do not remove any user-created problem directory.

- [ ] **Step 8: Confirm worktree state**

Run:

```bash
git status --short --branch
```

Expected: clean worktree after committed implementation, except for `.generated/problem-index.json` because it is ignored.

- [ ] **Step 9: Commit verification fixes if any were required**

If a defect was found and fixed during Task 6, run:

```bash
git add app lib scripts tests README.md .gitignore package.json
git commit -m "fix: verify local problem console"
```

If no defect was found, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: schema, lifecycle, file contract, deterministic indexing, repository boundary, Codex deep link and fallback, homepage states, detail route shell, accessibility/responsive styling, README, and verification commands are covered by Tasks 1-6.
- Placeholder scan: this plan contains no banned placeholder markers, no omitted task body, and no undefined interfaces.
- Type consistency: `buildProblemIndex`, `createProblemRepository`, `buildCodexLaunch`, `ProblemIndex`, and `ProblemConsole` props are defined before use.
