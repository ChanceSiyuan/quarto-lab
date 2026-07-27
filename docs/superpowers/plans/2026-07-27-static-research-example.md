# Static Research Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one repository-backed static research example for `QMB-001` with five synthetic CSS code-distance attempts, a dense problem ledger page, and audit-style attempt detail pages.

**Architecture:** Durable example files live under `problems/QMB-001`. A small fixture module explicitly imports `example.json` and the five known `attempt.json` files, validates their display contract at module load, and exposes immutable lookup functions. Presentation helpers derive aggregate cards and formatted rows for the existing Next/vinext routes without adding a database, live runner, worktree process, or AutoQEC importer.

**Tech Stack:** Next 16, React 19, vinext, Node 22 native `node:test`, JSON import attributes, existing problem indexer and repository modules.

## Global Constraints

- Static display only: no algorithm run, agent start, worktree creation, private dataset read, stream, or AutoQEC runtime dependency.
- Example content uses the AutoQEC-like record shape and research process, but every metric, method result, commit, and conclusion is synthetic demonstration data.
- Every result page must label the data as `Example data - synthetic results for interface demonstration only.`
- App UI remains English.
- The homepage remains the problem library; only `QMB-001` receives the static research ledger.
- Non-example problem detail routes retain the existing generic detail page.
- Unknown problem IDs and unknown attempt IDs return 404.
- Attempt artifacts display repository-relative paths only.
- Use existing project patterns and no new npm dependencies.
- Do not stage `.superpowers/brainstorm/`.

---

## File Structure

- `problems/QMB-001/problem.json`: valid problem manifest indexed by the existing problem indexer.
- `problems/QMB-001/problem.md`: required research problem headings and example problem body.
- `problems/QMB-001/example.json`: page-level static example disclaimer and synthetic baseline.
- `problems/QMB-001/generation/*.md`: short generation provenance records saying this is a static example.
- `problems/QMB-001/attempts/ATT-001/attempt.json` through `ATT-005/attempt.json`: synthetic attempt records.
- `problems/QMB-001/attempts/ATT-001/LOG.md` through `ATT-005/LOG.md`: durable audit-shaped logs for display artifacts.
- `lib/problems/example-research.mjs`: explicit fixture imports, validation, immutable lookup.
- `lib/problems/example-presentation.mjs`: aggregate cards, attempt row formatting, attempt dossier formatting.
- `app/problems/[id]/page.tsx`: branch `QMB-001` to the ledger page and keep the existing generic detail page for other problems.
- `app/problems/[id]/attempts/[attemptId]/page.tsx`: audit dossier route for example attempts.
- `app/globals.css`: ledger table, narrow stacked rows, metric strip variation, and audit dossier layout.
- `tests/static-example-content.test.mjs`: repository content and index acceptance tests.
- `tests/example-research.test.mjs`: fixture lookup, validation, immutability, predecessor chain, and aggregate tests.
- `tests/rendered-html.test.mjs`: rendered homepage, example ledger, attempt detail, 404, and non-example generic detail coverage.
- `package.json`: add the two new focused Node tests to the `npm test` command.

---

### Task 1: Example Problem Content

**Files:**
- Create: `tests/static-example-content.test.mjs`
- Create: `problems/QMB-001/problem.json`
- Create: `problems/QMB-001/problem.md`
- Create: `problems/QMB-001/example.json`
- Create: `problems/QMB-001/generation/initial-prompt.md`
- Create: `problems/QMB-001/generation/transcript.md`
- Create: `problems/QMB-001/generation/decision.md`
- Modify: `package.json`

**Interfaces:**
- Consumes: existing `scripts/build-problem-index.mjs` problem validation behavior.
- Produces: an indexed `QMB-001` problem with status `solving`, gate `{ type: "python-benchmark", readiness: "executable" }`, and a static example manifest at `example.json`.

- [ ] **Step 1: Write the failing content/index test**

Create `tests/static-example-content.test.mjs`:

```js
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const execFileAsync = promisify(execFile);
const workspaceRoot = fileURLToPath(new URL("../", import.meta.url));

test("QMB-001 static example is accepted by the problem index", async () => {
  const tempRoot = await mkdtemp(join(tmpdir(), "research-loop-index-"));
  const outPath = join(tempRoot, "problem-index.json");
  try {
    await execFileAsync(
      process.execPath,
      ["scripts/build-problem-index.mjs", "--root", workspaceRoot, "--out", outPath],
      { cwd: workspaceRoot, maxBuffer: 10 * 1024 * 1024 },
    );
    const index = JSON.parse(await readFile(outPath, "utf8"));
    const problem = index.problems.find((item) => item.id === "QMB-001");
    assert.ok(problem);
    assert.equal(problem.title, "CSS code-distance algorithm search");
    assert.equal(problem.status, "solving");
    assert.deepEqual(problem.gate, {
      type: "python-benchmark",
      readiness: "executable",
    });
    assert.equal(problem.provenance.sourceCount, 3);
    assert.equal(problem.lastActivity.summary, "Static example ledger prepared");
  } finally {
    await rm(tempRoot, { recursive: true, force: true });
  }
});

test("QMB-001 static example records are labeled as synthetic display data", async () => {
  const example = JSON.parse(
    await readFile(new URL("../problems/QMB-001/example.json", import.meta.url), "utf8"),
  );
  assert.equal(example.kind, "static-research-example");
  assert.equal(
    example.disclaimer,
    "Example data - synthetic results for interface demonstration only.",
  );
  assert.equal(example.baseline.label, "Synthetic SOTA baseline");
  assert.equal(example.baseline.suiteRuntimeSeconds, 1820.4);

  for (const name of ["initial-prompt.md", "transcript.md", "decision.md"]) {
    const text = await readFile(
      new URL(`../problems/QMB-001/generation/${name}`, import.meta.url),
      "utf8",
    );
    assert.match(text, /static example/i);
    assert.match(text, /synthetic/i);
  }
});
```

Add `tests/static-example-content.test.mjs` to the explicit `npm test` command before `tests/problem-schema.test.mjs`:

```json
"test": "node --test tests/static-example-content.test.mjs tests/problem-schema.test.mjs tests/problem-indexer.test.mjs tests/dev-problem-index.test.mjs tests/problem-repository.test.mjs tests/codex-launch.test.mjs tests/problem-presentation.test.mjs tests/problem-view-state.test.mjs && npm run build && node --test tests/rendered-html.test.mjs"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `node --test tests/static-example-content.test.mjs`

Expected: FAIL because `problems/QMB-001/example.json` or `QMB-001` is not present yet.

- [ ] **Step 3: Create the example problem files**

Create `problems/QMB-001/problem.json`:

```json
{
  "schemaVersion": 1,
  "id": "QMB-001",
  "title": "CSS code-distance algorithm search",
  "summary": "Find a publishable algorithm for CSS code distance that improves hard-timeout scaling under blind evaluation.",
  "status": "solving",
  "gate": {
    "type": "python-benchmark",
    "readiness": "executable"
  },
  "provenance": {
    "sourceCount": 3
  },
  "lastActivity": {
    "summary": "Static example ledger prepared",
    "at": "2026-07-27T02:40:00.000Z"
  },
  "createdAt": "2026-07-27T01:00:00.000Z",
  "updatedAt": "2026-07-27T02:40:00.000Z"
}
```

Create `problems/QMB-001/problem.md`:

```markdown
# CSS code-distance algorithm search

## Background and Gap

CSS quantum error-correcting codes need fast code-distance estimation for design loops, screening, and benchmark comparison. Exact search can be reliable but expensive, while aggressive heuristics need clear verification before their claims are useful.

## Research Objective

Use an autoresearch-style loop to search for a code-distance computing algorithm for CSS codes. The target is a publishable algorithm that is either 100x faster than the synthetic baseline in this static example or demonstrates better scaling under a hard five-minute run limit.

## Publication Threshold

A candidate must return verified witnesses on the blind evaluation suite, preserve containment between proposal and evaluation data, and show a synthetic speedup or scaling advantage large enough to justify follow-up research.

## Executable Gate

Each attempt is evaluated as if it had a Python benchmark gate with a 300 second limit per run, public smoke checks, containment checks, and a development suite summary. These values are static example data only.

## Novelty Evidence

The example mirrors a workflow that first surveys SOTA algorithms and builds a held-out dataset before proposing new algorithms. The displayed numbers are fictional and are included to exercise the interface.

## Provenance

The static example is derived from the shape of a local AutoQEC-style research process. It does not copy real benchmark values, private datasets, real commits, or real scientific conclusions.

## Fresh Evaluation Plan

Future real runs should keep benchmark datasets hidden from proposal agents, record a durable `LOG.md` in each worktree, and compare every accepted attempt against a frozen SOTA baseline under the same five-minute run budget.
```

Create `problems/QMB-001/example.json`:

```json
{
  "schemaVersion": 1,
  "kind": "static-research-example",
  "disclaimer": "Example data - synthetic results for interface demonstration only.",
  "baseline": {
    "label": "Synthetic SOTA baseline",
    "suiteRuntimeSeconds": 1820.4
  }
}
```

Create `problems/QMB-001/generation/initial-prompt.md`:

```markdown
# Static example initial prompt

Create a display-only example for an automated research loop that searches for CSS code-distance algorithms under a five-minute run limit.

This record is synthetic and exists to demonstrate the interface. It does not start an agent, run an algorithm, read a private dataset, or import AutoQEC results.
```

Create `problems/QMB-001/generation/transcript.md`:

```markdown
# Static example transcript

The user selected a compact problem research page with a dense attempt ledger and audit-style attempt detail pages.

The example keeps the real research-loop structure: problem manifest, generation records, attempt manifests, and per-attempt `LOG.md` files. All metrics and conclusions are synthetic display data.
```

Create `problems/QMB-001/generation/decision.md`:

```markdown
# Static example decision

Use a single CSS code-distance example problem and five synthetic attempts. Present the research as a static repository fixture so the product shape can be evaluated without rerunning any experiment.
```

- [ ] **Step 4: Run the focused content test**

Run: `node --test tests/static-example-content.test.mjs`

Expected: PASS.

- [ ] **Step 5: Rebuild the generated problem index**

Run: `node scripts/build-problem-index.mjs`

Expected: `.generated/problem-index.json` includes `QMB-001` and reports no diagnostics for it.

- [ ] **Step 6: Commit**

```bash
git add package.json tests/static-example-content.test.mjs problems/QMB-001 .generated/problem-index.json
git commit -m "feat: add static research example problem"
```

---

### Task 2: Attempt Fixtures and Research Helpers

**Files:**
- Create: `problems/QMB-001/attempts/ATT-001/attempt.json`
- Create: `problems/QMB-001/attempts/ATT-001/LOG.md`
- Create: `problems/QMB-001/attempts/ATT-002/attempt.json`
- Create: `problems/QMB-001/attempts/ATT-002/LOG.md`
- Create: `problems/QMB-001/attempts/ATT-003/attempt.json`
- Create: `problems/QMB-001/attempts/ATT-003/LOG.md`
- Create: `problems/QMB-001/attempts/ATT-004/attempt.json`
- Create: `problems/QMB-001/attempts/ATT-004/LOG.md`
- Create: `problems/QMB-001/attempts/ATT-005/attempt.json`
- Create: `problems/QMB-001/attempts/ATT-005/LOG.md`
- Create: `lib/problems/example-research.mjs`
- Create: `lib/problems/example-presentation.mjs`
- Create: `tests/example-research.test.mjs`
- Modify: `package.json`

**Interfaces:**
- Consumes: `problems/QMB-001/example.json` and the five attempt JSON files.
- Produces:
  - `EXAMPLE_RESEARCH_PROBLEM_ID: "QMB-001"`
  - `isStaticResearchExampleProblem(problemId: string): boolean`
  - `getStaticResearchExample(problemId: string): null | { manifest: object, attempts: object[] }`
  - `listStaticResearchAttempts(problemId: string): object[]`
  - `getStaticResearchAttempt(problemId: string, attemptId: string): null | object`
  - `getStaticResearchArtifactPath(problemId: string, attemptId: string, artifact: string): string`
  - `buildExampleResearchLedger(example: { manifest: object, attempts: object[] }): { cards: object[], rows: object[] }`
  - `buildAttemptDossier(attempt: object, exampleManifest: object): object`

- [ ] **Step 1: Write the failing helper test**

Create `tests/example-research.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";
import {
  EXAMPLE_RESEARCH_PROBLEM_ID,
  getStaticResearchArtifactPath,
  getStaticResearchAttempt,
  getStaticResearchExample,
  isStaticResearchExampleProblem,
  listStaticResearchAttempts,
} from "../lib/problems/example-research.mjs";
import {
  buildAttemptDossier,
  buildExampleResearchLedger,
  formatQuality,
  formatSeconds,
  formatSpeedup,
  formatVerified,
} from "../lib/problems/example-presentation.mjs";

test("static example exposes five ordered immutable attempts", () => {
  assert.equal(EXAMPLE_RESEARCH_PROBLEM_ID, "QMB-001");
  assert.equal(isStaticResearchExampleProblem("QMB-001"), true);
  assert.equal(isStaticResearchExampleProblem("QMB-999"), false);

  const example = getStaticResearchExample("QMB-001");
  assert.ok(example);
  assert.equal(
    example.manifest.disclaimer,
    "Example data - synthetic results for interface demonstration only.",
  );
  assert.deepEqual(example.attempts.map((attempt) => attempt.id), [
    "ATT-001",
    "ATT-002",
    "ATT-003",
    "ATT-004",
    "ATT-005",
  ]);

  example.attempts[0].id = "MUTATED";
  assert.equal(listStaticResearchAttempts("QMB-001")[0].id, "ATT-001");
});

test("static example attempts form the declared predecessor chain", () => {
  const attempts = listStaticResearchAttempts("QMB-001");
  assert.equal(attempts[0].method.learnedFrom, null);
  for (let index = 1; index < attempts.length; index += 1) {
    assert.equal(attempts[index].method.learnedFrom, attempts[index - 1].id);
  }
  assert.equal(getStaticResearchAttempt("QMB-001", "ATT-005").promoted, true);
  assert.equal(getStaticResearchAttempt("QMB-001", "ATT-999"), null);
  assert.equal(getStaticResearchExample("QMB-999"), null);
});

test("static example presentation derives synthetic aggregate cards", () => {
  const example = getStaticResearchExample("QMB-001");
  const ledger = buildExampleResearchLedger(example);
  assert.deepEqual(ledger.cards, [
    { label: "Attempts", value: "5" },
    { label: "Accepted", value: "3" },
    { label: "Best hits", value: "24/24" },
    { label: "Best speedup", value: "118.2x" },
  ]);
  assert.equal(ledger.rows[0].method, "Exact meet-in-the-middle baseline");
  assert.equal(ledger.rows[1].decision, "Rejected");
  assert.equal(ledger.rows[4].href, "/problems/QMB-001/attempts/ATT-005");
});

test("static example formatting is stable for route rendering", () => {
  assert.equal(formatVerified({ verifiedWitnesses: 18, runs: 24 }), "18/24");
  assert.equal(formatQuality(0.54), "0.540");
  assert.equal(formatSeconds(1.24), "1.24 s");
  assert.equal(formatSeconds(39.8), "39.8 s");
  assert.equal(formatSpeedup(118.2), "118.2x");
  assert.equal(
    getStaticResearchArtifactPath("QMB-001", "ATT-003", "LOG.md"),
    "problems/QMB-001/attempts/ATT-003/LOG.md",
  );
});

test("attempt dossier includes audit metadata and display sections", () => {
  const example = getStaticResearchExample("QMB-001");
  const attempt = getStaticResearchAttempt("QMB-001", "ATT-004");
  const dossier = buildAttemptDossier(attempt, example.manifest);
  assert.equal(dossier.title, "Residual-seeded local search");
  assert.equal(dossier.metrics[2].label, "Quality");
  assert.equal(dossier.metrics[2].value, "0.970");
  assert.deepEqual(dossier.evaluationPath.map((item) => item.label), [
    "Containment",
    "Public smoke",
    "Development",
    "Decision",
  ]);
  assert.deepEqual(dossier.artifacts, [
    "problems/QMB-001/attempts/ATT-004/attempt.json",
    "problems/QMB-001/attempts/ATT-004/LOG.md",
  ]);
});
```

Add `tests/example-research.test.mjs` after `tests/static-example-content.test.mjs` in `package.json`:

```json
"test": "node --test tests/static-example-content.test.mjs tests/example-research.test.mjs tests/problem-schema.test.mjs tests/problem-indexer.test.mjs tests/dev-problem-index.test.mjs tests/problem-repository.test.mjs tests/codex-launch.test.mjs tests/problem-presentation.test.mjs tests/problem-view-state.test.mjs && npm run build && node --test tests/rendered-html.test.mjs"
```

- [ ] **Step 2: Run the focused helper test to verify it fails**

Run: `node --test tests/example-research.test.mjs`

Expected: FAIL because `lib/problems/example-research.mjs` does not exist.

- [ ] **Step 3: Create the five attempt records and logs**

Create each `attempt.json` with these exact records:

```js
const attempts = [
  {
    schemaVersion: 1,
    problemId: "QMB-001",
    id: "ATT-001",
    sequence: 1,
    title: "Exact meet-in-the-middle baseline",
    summary: "Establish a correctness-first baseline under the hard timeout.",
    stage: "development",
    decision: "rejected",
    promoted: false,
    gate: { publicSmoke: "passed", containment: "passed", development: "failed" },
    method: {
      hypothesis: "A bounded exact meet-in-the-middle search should provide a reliable lower-bound baseline before more speculative heuristics are compared.",
      changes: [
        "Split candidate logical operators by support weight and combine compatible halves.",
        "Verify every returned witness against the CSS parity checks before scoring.",
        "Record timeout cases separately from verified misses."
      ],
      learnedFrom: null
    },
    metrics: {
      runs: 24,
      verifiedWitnesses: 18,
      targetHits: 11,
      timeouts: 6,
      crashes: 0,
      invalidClaims: 0,
      normalizedQuality: 0.54,
      runtimeSeconds: 1820.4,
      medianSeconds: 38.4,
      p95Seconds: 298.7,
      speedup: 1.0
    },
    interpretation: "The baseline is useful as a correctness reference, but it exhausts the five-minute cap on larger synthetic instances and cannot be the promoted strategy.",
    learnings: [
      "Keep the final witness verifier in every future attempt.",
      "Treat timeout rate as a first-class rejection signal.",
      "Use this runtime as the synthetic baseline for speedup display."
    ],
    provenance: {
      branch: "example/css-distance/att-001",
      commit: "e100001",
      worktreeState: "example",
      model: "example-agent"
    },
    artifacts: ["attempt.json", "LOG.md"],
    createdAt: "2026-07-27T01:00:00.000Z"
  },
  {
    schemaVersion: 1,
    problemId: "QMB-001",
    id: "ATT-002",
    sequence: 2,
    title: "Random kernel sampling",
    summary: "Try a very fast randomized kernel sampler and measure how much verification rejects.",
    stage: "development",
    decision: "rejected",
    promoted: false,
    gate: { publicSmoke: "passed", containment: "passed", development: "failed" },
    method: {
      hypothesis: "Sampling sparse vectors from the kernel of the CSS checks may locate low-weight logical operators much faster than exact enumeration.",
      changes: [
        "Replace meet-in-the-middle enumeration with random kernel basis combinations.",
        "Cap each restart by elapsed time rather than candidate count.",
        "Keep ATT-001 witness verification after every proposed hit."
      ],
      learnedFrom: "ATT-001"
    },
    metrics: {
      runs: 24,
      verifiedWitnesses: 15,
      targetHits: 12,
      timeouts: 0,
      crashes: 0,
      invalidClaims: 4,
      normalizedQuality: 0.5,
      runtimeSeconds: 42.6,
      medianSeconds: 1.4,
      p95Seconds: 2.9,
      speedup: 42.7
    },
    interpretation: "The sampler is fast, but invalid witness claims make the apparent hit count unreliable. Verification prevents a false promotion.",
    learnings: [
      "A fast proposal stage needs a stronger quotient-space constraint.",
      "Display invalid claims separately from crashes and misses.",
      "Do not rank candidates by speed alone."
    ],
    provenance: {
      branch: "example/css-distance/att-002",
      commit: "e100002",
      worktreeState: "example",
      model: "example-agent"
    },
    artifacts: ["attempt.json", "LOG.md"],
    createdAt: "2026-07-27T01:18:00.000Z"
  },
  {
    schemaVersion: 1,
    problemId: "QMB-001",
    id: "ATT-003",
    sequence: 3,
    title: "Verified quotient-coset descent",
    summary: "Constrain the search in quotient-coset space so fast proposals remain verifiable.",
    stage: "development",
    decision: "accepted",
    promoted: false,
    gate: { publicSmoke: "passed", containment: "passed", development: "passed" },
    method: {
      hypothesis: "Descending over quotient-coset representatives can preserve the speed of sampling while eliminating most invalid witness proposals.",
      changes: [
        "Represent candidates as quotient-coset states before local descent.",
        "Reject vectors that collapse to stabilizers before expensive scoring.",
        "Reuse ATT-002 restart scheduling with a verified acceptance filter."
      ],
      learnedFrom: "ATT-002"
    },
    metrics: {
      runs: 24,
      verifiedWitnesses: 24,
      targetHits: 19,
      timeouts: 0,
      crashes: 0,
      invalidClaims: 0,
      normalizedQuality: 0.9,
      runtimeSeconds: 183.2,
      medianSeconds: 5.9,
      p95Seconds: 21.8,
      speedup: 9.9
    },
    interpretation: "Correctness recovers across the synthetic suite, with enough speedup to keep the approach alive but not enough to satisfy the desired 100x story.",
    learnings: [
      "The quotient representation is the first accepted core.",
      "Initialization quality now dominates runtime variance.",
      "A stronger seed policy should target the remaining missed instances."
    ],
    provenance: {
      branch: "example/css-distance/att-003",
      commit: "e100003",
      worktreeState: "example",
      model: "example-agent"
    },
    artifacts: ["attempt.json", "LOG.md"],
    createdAt: "2026-07-27T01:42:00.000Z"
  },
  {
    schemaVersion: 1,
    problemId: "QMB-001",
    id: "ATT-004",
    sequence: 4,
    title: "Residual-seeded local search",
    summary: "Improve quotient-coset descent by seeding from residual syndromes.",
    stage: "development",
    decision: "accepted",
    promoted: false,
    gate: { publicSmoke: "passed", containment: "passed", development: "passed" },
    method: {
      hypothesis: "Residual syndrome features can seed quotient-coset descent close to low-weight witnesses and reduce restart waste.",
      changes: [
        "Rank initial states by residual syndrome sparsity.",
        "Carry the ATT-003 quotient verifier unchanged.",
        "Stop early once a verified target-distance witness is found."
      ],
      learnedFrom: "ATT-003"
    },
    metrics: {
      runs: 24,
      verifiedWitnesses: 24,
      targetHits: 22,
      timeouts: 0,
      crashes: 0,
      invalidClaims: 0,
      normalizedQuality: 0.97,
      runtimeSeconds: 39.8,
      medianSeconds: 1.6,
      p95Seconds: 3.8,
      speedup: 45.7
    },
    interpretation: "Residual seeding sharply improves speed and hit rate while preserving verification, but the synthetic speedup is still below the headline target.",
    learnings: [
      "Seeding is more valuable than adding more restarts.",
      "The accepted core can be wrapped in a portfolio scheduler.",
      "Promotion should require perfect synthetic target hits."
    ],
    provenance: {
      branch: "example/css-distance/att-004",
      commit: "e100004",
      worktreeState: "example",
      model: "example-agent"
    },
    artifacts: ["attempt.json", "LOG.md"],
    createdAt: "2026-07-27T02:06:00.000Z"
  },
  {
    schemaVersion: 1,
    problemId: "QMB-001",
    id: "ATT-005",
    sequence: 5,
    title: "Adaptive verified portfolio",
    summary: "Combine the exact baseline, quotient descent, and residual seeding under a verified adaptive scheduler.",
    stage: "development",
    decision: "accepted",
    promoted: true,
    gate: { publicSmoke: "passed", containment: "passed", development: "passed" },
    method: {
      hypothesis: "An adaptive portfolio can spend a tiny exact budget for calibration, then switch between verified quotient descent and residual-seeded search based on instance features.",
      changes: [
        "Run a short exact calibration pass inspired by ATT-001.",
        "Use ATT-004 residual seeding as the default worker.",
        "Fallback to ATT-003 quotient descent when the residual score is ambiguous."
      ],
      learnedFrom: "ATT-004"
    },
    metrics: {
      runs: 24,
      verifiedWitnesses: 24,
      targetHits: 24,
      timeouts: 0,
      crashes: 0,
      invalidClaims: 0,
      normalizedQuality: 1.0,
      runtimeSeconds: 15.4,
      medianSeconds: 0.62,
      p95Seconds: 1.24,
      speedup: 118.2
    },
    interpretation: "The synthetic portfolio reaches every target instance, preserves verification, and crosses the 100x display threshold against the synthetic baseline.",
    learnings: [
      "Promotion came from combining accepted components rather than replacing them.",
      "The verifier is the invariant across the whole story.",
      "A real project would now freeze this candidate for hidden evaluation."
    ],
    provenance: {
      branch: "example/css-distance/att-005",
      commit: "e100005",
      worktreeState: "example",
      model: "example-agent"
    },
    artifacts: ["attempt.json", "LOG.md"],
    createdAt: "2026-07-27T02:32:00.000Z"
  }
];
```

For each `LOG.md`, use this exact section shape with the corresponding attempt title, decision, metrics, and lessons from its `attempt.json`:

```markdown
# ATT-001 - Exact meet-in-the-middle baseline

Example data - synthetic results for interface demonstration only.

## Public Contract Smoke

passed

## Containment

passed

## Development Metrics

- runs: 24
- verified witnesses: 18/24
- target hits: 11
- timeouts: 6
- crashes: 0
- invalid claims: 0
- normalized quality: 0.540
- runtime: 1820.4 s
- p95: 298.7 s
- speedup: 1.0x

## Decision

rejected

## Learning Carried Forward

- Keep the final witness verifier in every future attempt.
- Treat timeout rate as a first-class rejection signal.
- Use this runtime as the synthetic baseline for speedup display.
```

- [ ] **Step 4: Create the research fixture module**

Create `lib/problems/example-research.mjs`:

```js
import exampleManifest from "../../problems/QMB-001/example.json" with { type: "json" };
import attempt001 from "../../problems/QMB-001/attempts/ATT-001/attempt.json" with { type: "json" };
import attempt002 from "../../problems/QMB-001/attempts/ATT-002/attempt.json" with { type: "json" };
import attempt003 from "../../problems/QMB-001/attempts/ATT-003/attempt.json" with { type: "json" };
import attempt004 from "../../problems/QMB-001/attempts/ATT-004/attempt.json" with { type: "json" };
import attempt005 from "../../problems/QMB-001/attempts/ATT-005/attempt.json" with { type: "json" };

export const EXAMPLE_RESEARCH_PROBLEM_ID = "QMB-001";

const rawAttempts = [attempt001, attempt002, attempt003, attempt004, attempt005]
  .toSorted((left, right) => left.sequence - right.sequence);
const attemptById = new Map(rawAttempts.map((attempt) => [attempt.id, attempt]));

function clone(value) {
  return structuredClone(value);
}

function validateStaticExample() {
  const seen = new Set();
  for (const [index, attempt] of rawAttempts.entries()) {
    if (attempt.problemId !== EXAMPLE_RESEARCH_PROBLEM_ID) {
      throw new Error(`Static example attempt ${attempt.id} has mismatched problemId.`);
    }
    if (seen.has(attempt.id)) {
      throw new Error(`Static example attempt ${attempt.id} is duplicated.`);
    }
    seen.add(attempt.id);
    if (attempt.sequence !== index + 1) {
      throw new Error(`Static example attempt ${attempt.id} has a non-contiguous sequence.`);
    }
    const expectedPredecessor = index === 0 ? null : rawAttempts[index - 1].id;
    if (attempt.method.learnedFrom !== expectedPredecessor) {
      throw new Error(`Static example attempt ${attempt.id} has an invalid predecessor.`);
    }
  }
}

validateStaticExample();

export function isStaticResearchExampleProblem(problemId) {
  return problemId === EXAMPLE_RESEARCH_PROBLEM_ID;
}

export function getStaticResearchExample(problemId) {
  if (!isStaticResearchExampleProblem(problemId)) {
    return null;
  }
  return {
    manifest: clone(exampleManifest),
    attempts: clone(rawAttempts),
  };
}

export function listStaticResearchAttempts(problemId) {
  return getStaticResearchExample(problemId)?.attempts ?? [];
}

export function getStaticResearchAttempt(problemId, attemptId) {
  if (!isStaticResearchExampleProblem(problemId)) {
    return null;
  }
  const attempt = attemptById.get(attemptId);
  return attempt ? clone(attempt) : null;
}

export function getStaticResearchArtifactPath(problemId, attemptId, artifact) {
  return `problems/${problemId}/attempts/${attemptId}/${artifact}`;
}
```

- [ ] **Step 5: Create presentation helpers**

Create `lib/problems/example-presentation.mjs`:

```js
import { getStaticResearchArtifactPath } from "./example-research.mjs";

const titleCase = (value) => `${value.slice(0, 1).toUpperCase()}${value.slice(1)}`;

export function formatSeconds(value) {
  const digits = value < 10 && !Number.isInteger(value) ? 2 : 1;
  return `${value.toFixed(digits)} s`;
}

export function formatQuality(value) {
  return value.toFixed(3);
}

export function formatSpeedup(value) {
  return `${value.toFixed(1)}x`;
}

export function formatVerified(metrics) {
  return `${metrics.verifiedWitnesses}/${metrics.runs}`;
}

function formatGate(gate) {
  return [
    { label: "Containment", value: gate.containment },
    { label: "Public smoke", value: gate.publicSmoke },
    { label: "Development", value: gate.development },
  ];
}

function decisionLabel(attempt) {
  return attempt.promoted ? "Accepted, promoted" : titleCase(attempt.decision);
}

export function buildExampleResearchLedger(example) {
  const attempts = example.attempts;
  const acceptedCount = attempts.filter((attempt) => attempt.decision === "accepted").length;
  const bestHits = attempts.reduce((best, attempt) => Math.max(best, attempt.metrics.targetHits), 0);
  const bestRuns = attempts.reduce((best, attempt) => Math.max(best, attempt.metrics.runs), 0);
  const bestSpeedup = attempts.reduce((best, attempt) => Math.max(best, attempt.metrics.speedup), 0);

  return {
    cards: [
      { label: "Attempts", value: String(attempts.length) },
      { label: "Accepted", value: String(acceptedCount) },
      { label: "Best hits", value: `${bestHits}/${bestRuns}` },
      { label: "Best speedup", value: formatSpeedup(bestSpeedup) },
    ],
    rows: attempts.map((attempt) => ({
      id: attempt.id,
      title: attempt.title,
      method: attempt.title,
      summary: attempt.summary,
      stage: titleCase(attempt.stage),
      decision: decisionLabel(attempt),
      gate: formatGate(attempt.gate),
      verified: formatVerified(attempt.metrics),
      hits: String(attempt.metrics.targetHits),
      quality: formatQuality(attempt.metrics.normalizedQuality),
      runtime: formatSeconds(attempt.metrics.runtimeSeconds),
      p95: formatSeconds(attempt.metrics.p95Seconds),
      speedup: formatSpeedup(attempt.metrics.speedup),
      href: `/problems/${attempt.problemId}/attempts/${attempt.id}`,
    })),
  };
}

export function buildAttemptDossier(attempt, exampleManifest) {
  return {
    id: attempt.id,
    title: attempt.title,
    summary: attempt.summary,
    disclaimer: exampleManifest.disclaimer,
    stage: titleCase(attempt.stage),
    decision: decisionLabel(attempt),
    metrics: [
      { label: "Verified", value: formatVerified(attempt.metrics) },
      { label: "Target hits", value: String(attempt.metrics.targetHits) },
      { label: "Quality", value: formatQuality(attempt.metrics.normalizedQuality) },
      { label: "Runtime", value: formatSeconds(attempt.metrics.runtimeSeconds) },
      { label: "P95", value: formatSeconds(attempt.metrics.p95Seconds) },
      { label: "Speedup", value: formatSpeedup(attempt.metrics.speedup) },
    ],
    method: attempt.method,
    interpretation: attempt.interpretation,
    learnings: attempt.learnings,
    evaluationPath: [
      { label: "Containment", value: titleCase(attempt.gate.containment) },
      { label: "Public smoke", value: titleCase(attempt.gate.publicSmoke) },
      { label: "Development", value: titleCase(attempt.gate.development) },
      { label: "Decision", value: decisionLabel(attempt) },
    ],
    provenance: attempt.provenance,
    createdAt: attempt.createdAt,
    artifacts: attempt.artifacts.map((artifact) =>
      getStaticResearchArtifactPath(attempt.problemId, attempt.id, artifact),
    ),
  };
}
```

- [ ] **Step 6: Run the focused helper test**

Run: `node --test tests/example-research.test.mjs`

Expected: PASS.

- [ ] **Step 7: Run the full Node unit suite before build**

Run: `node --test tests/static-example-content.test.mjs tests/example-research.test.mjs tests/problem-schema.test.mjs tests/problem-indexer.test.mjs tests/dev-problem-index.test.mjs tests/problem-repository.test.mjs tests/codex-launch.test.mjs tests/problem-presentation.test.mjs tests/problem-view-state.test.mjs`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add package.json tests/example-research.test.mjs lib/problems/example-research.mjs lib/problems/example-presentation.mjs problems/QMB-001/attempts
git commit -m "feat: add static research attempt fixtures"
```

---

### Task 3: Problem Ledger Page

**Files:**
- Modify: `app/problems/[id]/page.tsx`
- Modify: `app/globals.css`
- Modify: `tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: `getStaticResearchExample(problem.id)` and `buildExampleResearchLedger(example)`.
- Produces: `/problems/QMB-001` ledger page with cards, table, narrow stacked rows, five attempt links, and persistent synthetic disclaimer.

- [ ] **Step 1: Update rendered tests for the real example homepage and ledger**

In `tests/rendered-html.test.mjs`, update `server-renders the problem console shell` so it expects the real `QMB-001` row instead of an empty first-problem action:

```js
assert.match(html, /CSS code-distance algorithm search/);
assert.match(html, /href="\/problems\/QMB-001"/);
assert.doesNotMatch(html, />\+ Add first problem<\/a>/);
```

Add this test after the unknown problem test:

```js
test("server-renders the static research ledger for QMB-001", async () => {
  const response = await render("/problems/QMB-001");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<a href="\/" class="back-link">← Back to problems<\/a>/);
  assert.match(html, /<p class="eyebrow">QMB-001<\/p>/);
  assert.match(html, /<h1>CSS code-distance algorithm search<\/h1>/);
  assert.match(html, /Example data - synthetic results for interface demonstration only\./);
  assert.match(html, /Blind evaluation/);
  assert.match(html, /300 s \/ run/);
  assert.match(html, /<dt>Attempts<\/dt><dd>5<\/dd>/);
  assert.match(html, /<dt>Best speedup<\/dt><dd>118\.2x<\/dd>/);
  assert.match(html, /<th scope="col">Attempt<\/th><th scope="col">Method<\/th><th scope="col">Stage<\/th><th scope="col">Decision<\/th><th scope="col">Gate<\/th><th scope="col">Verified<\/th><th scope="col">Hits<\/th><th scope="col">Quality<\/th><th scope="col">Runtime<\/th><th scope="col">P95<\/th><th scope="col">Speedup<\/th><th scope="col">Open<\/th>/);
  for (const attemptId of ["ATT-001", "ATT-002", "ATT-003", "ATT-004", "ATT-005"]) {
    assert.match(html, new RegExp(`href="\\/problems\\/QMB-001\\/attempts\\/${attemptId}"`));
  }
  assert.match(html, /Adaptive verified portfolio/);
  assert.match(html, /118\.2x/);
  assert.doesNotMatch(html, /The detailed problem workspace will be designed next/);
  assert.doesNotMatch(html, /[\u3400-\u9FFF]/u);
});
```

Keep the existing fixture detail test for `QMB-017` and rename its description to `server-renders the generic problem detail shell for non-example problems`.

- [ ] **Step 2: Run the rendered test to verify it fails**

Run: `npm run build && node --test tests/rendered-html.test.mjs`

Expected: FAIL because `/problems/QMB-001` still renders the generic detail shell.

- [ ] **Step 3: Implement the ledger branch**

Modify `app/problems/[id]/page.tsx` to import the helpers:

```ts
import {
  getStaticResearchExample,
  isStaticResearchExampleProblem,
} from "@/lib/problems/example-research.mjs";
import { buildExampleResearchLedger } from "@/lib/problems/example-presentation.mjs";
```

After the `problem` lookup and 404 branch, add:

```ts
  if (isStaticResearchExampleProblem(problem.id)) {
    const example = getStaticResearchExample(problem.id);
    const ledger = buildExampleResearchLedger(example);

    return (
      <main className="detail-shell research-shell">
        <Link className="back-link" href="/">← Back to problems</Link>
        <header className="research-header">
          <div>
            <p className="eyebrow">{problem.id}</p>
            <h1>{problem.title}</h1>
            <p className="detail-summary">{problem.summary}</p>
          </div>
          <div className="research-badges" aria-label="Research metadata">
            <span>Solving</span>
            <span>Example data</span>
            <span>Blind evaluation</span>
            <span>300 s / run</span>
          </div>
        </header>

        <p className="example-disclaimer">{example.manifest.disclaimer}</p>

        <dl className="research-metric-strip" aria-label="Research metrics">
          {ledger.cards.map((card) => (
            <div key={card.label}>
              <dt>{card.label}</dt>
              <dd>{card.value}</dd>
            </div>
          ))}
        </dl>

        <section className="attempt-ledger" aria-labelledby="attempt-ledger-heading">
          <div className="section-heading-row">
            <h2 id="attempt-ledger-heading">Attempts</h2>
            <p>{ledger.rows.length} synthetic runs</p>
          </div>
          <div className="attempt-table-wrap">
            <table className="attempt-table">
              <thead>
                <tr>
                  <th scope="col">Attempt</th><th scope="col">Method</th><th scope="col">Stage</th><th scope="col">Decision</th><th scope="col">Gate</th><th scope="col">Verified</th><th scope="col">Hits</th><th scope="col">Quality</th><th scope="col">Runtime</th><th scope="col">P95</th><th scope="col">Speedup</th><th scope="col">Open</th>
                </tr>
              </thead>
              <tbody>
                {ledger.rows.map((row) => (
                  <tr key={row.id}>
                    <th scope="row"><Link href={row.href}>{row.id}</Link></th>
                    <td><strong>{row.method}</strong><span>{row.summary}</span></td>
                    <td>{row.stage}</td>
                    <td>{row.decision}</td>
                    <td>{row.gate.map((item) => <span key={item.label}>{item.label}: {item.value}</span>)}</td>
                    <td>{row.verified}</td>
                    <td>{row.hits}</td>
                    <td>{row.quality}</td>
                    <td>{row.runtime}</td>
                    <td>{row.p95}</td>
                    <td>{row.speedup}</td>
                    <td><Link href={row.href}>Open</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="attempt-card-list" aria-label="Attempt cards">
            {ledger.rows.map((row) => (
              <Link className="attempt-card" href={row.href} key={row.id}>
                <span>{row.id}</span>
                <strong>{row.method}</strong>
                <small>{row.decision} · {row.verified} verified · {row.speedup}</small>
              </Link>
            ))}
          </div>
        </section>
      </main>
    );
  }
```

- [ ] **Step 4: Add ledger CSS**

Extend `app/globals.css` with classes for:

```css
.research-shell { width: min(1360px, calc(100% - 48px)); }
.research-header { display: flex; align-items: start; justify-content: space-between; gap: 24px; }
.research-badges { display: flex; flex-wrap: wrap; gap: 6px; justify-content: end; }
.research-badges span,
.example-disclaimer {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--muted);
  font: 11px var(--font-geist-mono);
}
.research-badges span { padding: 6px 8px; }
.example-disclaimer { margin: 18px 0; padding: 10px 12px; color: var(--amber); }
.research-metric-strip { display: grid; grid-template-columns: repeat(4, 1fr); margin: 0 0 22px; border: 1px solid var(--line); background: var(--surface); }
.research-metric-strip > div { padding: 14px 16px; border-right: 1px solid var(--line); }
.research-metric-strip > div:last-child { border-right: 0; }
.research-metric-strip dt { color: var(--muted); font: 11px var(--font-geist-mono); }
.research-metric-strip dd { margin: 6px 0 0; font-size: 28px; font-weight: 590; letter-spacing: -.04em; }
.section-heading-row { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 10px; }
.section-heading-row h2 { margin: 0; font-size: 20px; }
.section-heading-row p { margin: 0; color: var(--muted); font: 11px var(--font-geist-mono); }
.attempt-table-wrap { overflow-x: auto; border: 1px solid var(--line); background: var(--surface); }
.attempt-table { width: 100%; min-width: 1120px; border-collapse: collapse; font-size: 12px; }
.attempt-table th,
.attempt-table td { padding: 11px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
.attempt-table thead th { color: var(--muted); font: 10px var(--font-geist-mono); text-transform: uppercase; }
.attempt-table tbody tr:last-child th,
.attempt-table tbody tr:last-child td { border-bottom: 0; }
.attempt-table td strong,
.attempt-table td span { display: block; }
.attempt-table td span { margin-top: 3px; color: var(--muted); }
.attempt-table a { color: var(--green); font-weight: 650; }
.attempt-card-list { display: none; }
@media (max-width: 780px) {
  .research-shell { width: min(100% - 28px, 1360px); }
  .research-header { display: block; }
  .research-badges { justify-content: start; margin-top: 14px; }
  .research-metric-strip { grid-template-columns: repeat(2, 1fr); }
  .research-metric-strip > div:nth-child(2) { border-right: 0; }
  .research-metric-strip > div:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
  .attempt-table-wrap { display: none; }
  .attempt-card-list { display: grid; gap: 8px; }
  .attempt-card { display: grid; gap: 4px; border: 1px solid var(--line); background: var(--surface); padding: 12px; }
  .attempt-card span { color: var(--green); font: 11px var(--font-geist-mono); }
  .attempt-card strong { font-size: 14px; }
  .attempt-card small { color: var(--muted); font-size: 12px; }
}
```

Keep text sizing fixed or `clamp`-based only where the existing detail page already does so. Do not add decorative background imagery.

- [ ] **Step 5: Run rendered tests**

Run: `npm run build && node --test tests/rendered-html.test.mjs`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/problems/[id]/page.tsx app/globals.css tests/rendered-html.test.mjs
git commit -m "feat: render static research ledger"
```

---

### Task 4: Attempt Audit Detail Route

**Files:**
- Create: `app/problems/[id]/attempts/[attemptId]/page.tsx`
- Modify: `app/globals.css`
- Modify: `tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: `getStaticResearchExample(problem.id)`, `getStaticResearchAttempt(problem.id, attemptId)`, and `buildAttemptDossier(attempt, example.manifest)`.
- Produces: `/problems/QMB-001/attempts/<attemptId>` pages for all five example attempts and 404 for unknown attempt IDs or non-example problem IDs.

- [ ] **Step 1: Add failing rendered route tests**

Add these tests to `tests/rendered-html.test.mjs`:

```js
test("server-renders static attempt audit dossiers", async () => {
  for (const [attemptId, title] of [
    ["ATT-001", "Exact meet-in-the-middle baseline"],
    ["ATT-002", "Random kernel sampling"],
    ["ATT-003", "Verified quotient-coset descent"],
    ["ATT-004", "Residual-seeded local search"],
    ["ATT-005", "Adaptive verified portfolio"],
  ]) {
    const response = await render(`/problems/QMB-001/attempts/${attemptId}`);
    assert.equal(response.status, 200);
    const html = await response.text();
    assert.match(html, new RegExp(`<p class="eyebrow">QMB-001 / ${attemptId}<\\/p>`));
    assert.match(html, new RegExp(`<h1>${title}<\\/h1>`));
    assert.match(html, /Example data - synthetic results for interface demonstration only\./);
    assert.match(html, /Hypothesis/);
    assert.match(html, /Evaluation path/);
    assert.match(html, /Result interpretation/);
    assert.match(html, /Learning carried forward/);
    assert.match(html, /problems\/QMB-001\/attempts\//);
    assert.match(html, /attempt\.json/);
    assert.match(html, /LOG\.md/);
    assert.doesNotMatch(html, /[\u3400-\u9FFF]/u);
  }
});

test("returns 404 for unknown static attempt IDs", async () => {
  const response = await render("/problems/QMB-001/attempts/ATT-999");
  assert.equal(response.status, 404);
});

test("returns 404 for attempt routes on non-example problems", async () => {
  const response = await renderFilesystemFixture(
    { manifests: [acceptedFixture] },
    "/problems/QMB-017/attempts/ATT-001?fixture=filesystem",
  );
  assert.equal(response.status, 404);
});
```

- [ ] **Step 2: Run rendered tests to verify the new route fails**

Run: `npm run build && node --test tests/rendered-html.test.mjs`

Expected: FAIL because `app/problems/[id]/attempts/[attemptId]/page.tsx` does not exist.

- [ ] **Step 3: Create the attempt audit route**

Create `app/problems/[id]/attempts/[attemptId]/page.tsx`:

```tsx
import generatedIndex from "../../../../../.generated/problem-index.json";
import { buildAttemptDossier } from "@/lib/problems/example-presentation.mjs";
import {
  getStaticResearchAttempt,
  getStaticResearchExample,
  isStaticResearchExampleProblem,
} from "@/lib/problems/example-research.mjs";
import { createProblemRepository } from "@/lib/problems/repository.mjs";
import Link from "next/link";
import { notFound } from "next/navigation";

export default async function AttemptDetailPage({
  params,
}: {
  params: Promise<{ id: string; attemptId: string }>;
}) {
  const { id, attemptId } = await params;
  const repository = createProblemRepository(generatedIndex);
  const problem = repository.getProblem(id);

  if (!problem || !isStaticResearchExampleProblem(problem.id)) {
    notFound();
  }

  const example = getStaticResearchExample(problem.id);
  const attempt = getStaticResearchAttempt(problem.id, attemptId);

  if (!attempt) {
    notFound();
  }

  const dossier = buildAttemptDossier(attempt, example.manifest);

  return (
    <main className="detail-shell attempt-shell">
      <div className="breadcrumb-row">
        <Link className="back-link" href={`/problems/${problem.id}`}>← Back to research ledger</Link>
        <Link className="back-link muted-back-link" href="/">Problem library</Link>
      </div>

      <header className="attempt-header">
        <div>
          <p className="eyebrow">{problem.id} / {dossier.id}</p>
          <h1>{dossier.title}</h1>
          <p className="detail-summary">{dossier.summary}</p>
        </div>
        <div className="research-badges" aria-label="Attempt metadata">
          <span>{dossier.stage}</span>
          <span>{dossier.decision}</span>
          <span>Example data</span>
        </div>
      </header>

      <p className="example-disclaimer">{dossier.disclaimer}</p>

      <dl className="attempt-metric-strip" aria-label="Attempt metrics">
        {dossier.metrics.map((metric) => (
          <div key={metric.label}>
            <dt>{metric.label}</dt>
            <dd>{metric.value}</dd>
          </div>
        ))}
      </dl>

      <div className="attempt-layout">
        <section className="attempt-main" aria-label="Attempt research record">
          <article>
            <h2>Hypothesis</h2>
            <p>{dossier.method.hypothesis}</p>
            <h3>Method changes</h3>
            <ul>{dossier.method.changes.map((item) => <li key={item}>{item}</li>)}</ul>
          </article>
          <article>
            <h2>Evaluation path</h2>
            <ol className="evaluation-path">
              {dossier.evaluationPath.map((item) => (
                <li key={item.label}><span>{item.label}</span><strong>{item.value}</strong></li>
              ))}
            </ol>
          </article>
          <article>
            <h2>Result interpretation</h2>
            <p>{dossier.interpretation}</p>
          </article>
          <article>
            <h2>Learning carried forward</h2>
            <ul>{dossier.learnings.map((item) => <li key={item}>{item}</li>)}</ul>
          </article>
        </section>

        <aside className="attempt-audit" aria-label="Attempt audit metadata">
          <section>
            <h2>Provenance</h2>
            <dl>
              <div><dt>Branch</dt><dd>{dossier.provenance.branch}</dd></div>
              <div><dt>Commit</dt><dd>{dossier.provenance.commit}</dd></div>
              <div><dt>Worktree</dt><dd>{dossier.provenance.worktreeState}</dd></div>
              <div><dt>Model</dt><dd>{dossier.provenance.model}</dd></div>
              <div><dt>Created</dt><dd>{dossier.createdAt}</dd></div>
            </dl>
          </section>
          <section>
            <h2>Artifacts</h2>
            <ul>{dossier.artifacts.map((artifact) => <li key={artifact}><code>{artifact}</code></li>)}</ul>
          </section>
        </aside>
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Add audit dossier CSS**

Extend `app/globals.css` with:

```css
.attempt-shell { width: min(1180px, calc(100% - 48px)); }
.breadcrumb-row { display: flex; justify-content: space-between; gap: 14px; }
.muted-back-link { color: var(--muted); }
.attempt-header { display: flex; justify-content: space-between; gap: 24px; align-items: start; }
.attempt-metric-strip { display: grid; grid-template-columns: repeat(6, 1fr); margin: 0 0 22px; border: 1px solid var(--line); background: var(--surface); }
.attempt-metric-strip > div { padding: 13px 14px; border-right: 1px solid var(--line); }
.attempt-metric-strip > div:last-child { border-right: 0; }
.attempt-metric-strip dt { color: var(--muted); font: 10px var(--font-geist-mono); text-transform: uppercase; }
.attempt-metric-strip dd { margin: 6px 0 0; font-size: 22px; font-weight: 590; letter-spacing: -.035em; }
.attempt-layout { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(280px, .8fr); gap: 22px; align-items: start; }
.attempt-main,
.attempt-audit { display: grid; gap: 14px; }
.attempt-main article,
.attempt-audit section { border: 1px solid var(--line); background: var(--surface); padding: 18px; }
.attempt-main h2,
.attempt-audit h2 { margin: 0 0 10px; font-size: 16px; }
.attempt-main h3 { margin: 16px 0 8px; font-size: 13px; color: var(--muted); }
.attempt-main p,
.attempt-main li { color: var(--ink); line-height: 1.55; }
.attempt-main ul,
.attempt-audit ul { margin: 0; padding-left: 18px; }
.evaluation-path { margin: 0; padding-left: 18px; }
.evaluation-path li { margin-bottom: 7px; }
.evaluation-path span { color: var(--muted); margin-right: 8px; }
.attempt-audit dl { margin: 0; display: grid; gap: 10px; }
.attempt-audit dl div { min-width: 0; }
.attempt-audit dt { color: var(--muted); font: 10px var(--font-geist-mono); text-transform: uppercase; }
.attempt-audit dd { margin: 3px 0 0; overflow-wrap: anywhere; font: 12px var(--font-geist-mono); }
.attempt-audit code { overflow-wrap: anywhere; font: 12px var(--font-geist-mono); }
@media (max-width: 860px) {
  .attempt-shell { width: min(100% - 28px, 1180px); }
  .breadcrumb-row,
  .attempt-header { display: block; }
  .muted-back-link { display: inline-block; margin-top: 8px; }
  .attempt-metric-strip { grid-template-columns: repeat(2, 1fr); }
  .attempt-metric-strip > div { border-bottom: 1px solid var(--line); }
  .attempt-metric-strip > div:nth-child(2n) { border-right: 0; }
  .attempt-metric-strip > div:nth-last-child(-n+2) { border-bottom: 0; }
  .attempt-layout { grid-template-columns: 1fr; }
}
```

- [ ] **Step 5: Run rendered route tests**

Run: `npm run build && node --test tests/rendered-html.test.mjs`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/problems/[id]/attempts/[attemptId]/page.tsx app/globals.css tests/rendered-html.test.mjs
git commit -m "feat: render static attempt dossiers"
```

---

### Task 5: Final Verification and Handoff

**Files:**
- Modify only if verification exposes a real defect in the files changed by Tasks 1-4.

**Interfaces:**
- Consumes: all files created or modified by Tasks 1-4.
- Produces: passing checks, clean staged product changes, and a concise handoff.

- [ ] **Step 1: Run the full test suite**

Run: `npm test`

Expected: PASS.

- [ ] **Step 2: Run lint**

Run: `npm run lint`

Expected: PASS.

- [ ] **Step 3: Inspect git status**

Run: `git status --short`

Expected: changed product files are committed, and `.superpowers/brainstorm/` remains untracked if it is still present.

- [ ] **Step 4: Confirm no forbidden runtime work was added**

Run:

```bash
rg -n "AutoQEC|worktree|spawn|dataset|benchmark" app lib problems/QMB-001 tests
```

Expected: matches are only static explanatory text, synthetic benchmark labels, route/content names, or tests. There must be no code that starts a process, creates a worktree, imports `/Users/nzy/mcode/AutoQEC`, or reads private datasets.

- [ ] **Step 5: Confirm all user-facing result pages label synthetic data**

Run:

```bash
rg -n "Example data - synthetic results for interface demonstration only\\." problems/QMB-001 app lib tests
```

Expected: matches appear in `example.json`, helper tests, rendered tests, and route-rendered output sources.

- [ ] **Step 6: Commit verification fixes only when needed**

If Steps 1-5 expose a defect and a code change is made, run:

```bash
git add <changed-files>
git commit -m "fix: stabilize static research example"
```

If Steps 1-5 pass without new edits, do not create an empty commit.

---

## Self-Review

- Spec coverage: Task 1 covers the problem manifest, required markdown headings, generation records, and static disclaimer. Task 2 covers five synthetic attempts, durable logs, explicit fixture imports, validation, immutability, predecessor chain, aggregates, and artifact paths. Task 3 covers the dense problem ledger and non-example generic detail preservation. Task 4 covers attempt audit pages and 404 behavior. Task 5 covers full verification, no runtime research work, and synthetic labeling.
- Red-flag scan: the plan contains concrete file paths, code snippets, exact commands, expected outcomes, and commit scopes.
- Type consistency: helper names and return shapes used in route tasks match the interfaces produced in Task 2. `buildExampleResearchLedger()` returns `cards` and `rows`; `buildAttemptDossier()` returns `metrics`, `evaluationPath`, `provenance`, and `artifacts`.
