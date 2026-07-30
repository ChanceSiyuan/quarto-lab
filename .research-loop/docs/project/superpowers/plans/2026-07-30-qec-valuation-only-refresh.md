# QEC Valuation-Only Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic local workflow that publishes completed QEC assessment revisions by retaining the latest completed qualitative assessment and refreshing only the quantitative valuation packet from a verified `qec-scientific-demand-v1` snapshot.

**Architecture:** Add a small host-owned valuation-only refresh module that reads old immutable assessment artifacts, creates or reuses verified valuation snapshots, derives a new valid assessment envelope, and publishes a new immutable run through the existing artifact store and report renderer. Keep Codex CLI out of this path, record derivation provenance beside the new run, and let the existing portfolio verifier select the newest completed bound report.

**Tech Stack:** Node.js ESM, `node:test`, existing assessment artifact store, existing valuation snapshot store, OpenAlex-backed valuation manager, existing HTML report renderer.

## Global Constraints

- Scope is exactly `Prob-001` through `Prob-021`.
- Old snapshots, assessment runs, generated reports, trusted knowledge, and lifecycle state are immutable inputs.
- Formula ID must be exactly `qec-scientific-demand-v1`.
- Missing citation evidence is a refresh error and must not be converted to numeric zero.
- Output reports and portfolio rows must be English-only.
- Output reports must not visibly contain `Unknown`, `Pending`, score ranges such as `72.5 (52-88.75)`, or Chinese text.
- Qualitative assessment fields are retained from the newest completed public English version-2 source run.
- Score anchors are empty in valuation-only revisions.
- Provenance must record the source run ID and source snapshot ID in a dedicated local derivation artifact.
- Rerunning the refresher reuses an already completed report bound to the same snapshot and source run.
- No Codex CLI qualitative assessment is invoked by the valuation-only workflow.
- Implementation is test-first.

---

### Task 1: Store Derivation Provenance Atomically

**Files:**
- Modify: `lib/assessments/artifact-store.mjs`
- Test: `tests/assessment-artifacts.test.mjs`

**Interfaces:**
- Consumes: `createArtifactStore({ rootDir, now, randomBytes }).writeTerminalArtifacts(run, artifacts)`
- Produces: optional `artifacts.derivation` JSON written as `derivation.json` before the staging directory is renamed into `problems/<id>/assessments/<runId>/`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/assessment-artifacts.test.mjs`:

```js
test("publishes derivation provenance with terminal artifacts", async () => {
  const root = await mkdtemp(join(tmpdir(), "assessment-store-derivation-"));
  await mkdir(join(root, "problems", "Prob-001"), { recursive: true });
  const store = createArtifactStore({
    rootDir: root,
    now: () => new Date("2026-07-30T01:02:03.000Z"),
    randomBytes: () => Buffer.from("abc123", "hex"),
  });
  const run = await store.createAcceptedRun({ problemId: "Prob-001" });
  const derivation = {
    schemaVersion: 1,
    kind: "qec-valuation-only-refresh",
    problemId: "Prob-001",
    runId: "20260730T010203Z-abc123",
    sourceRunId: "20260729T010203Z-source",
    sourceSnapshotId: "20260729T010203Z-111111111111",
    refreshedSnapshotId: "20260730T010203Z-222222222222",
    notice: "Qualitative assessment retained from a prior completed run; quantitative valuation refreshed from the bound Scientific Demand snapshot.",
  };

  await store.writeTerminalArtifacts(run, {
    status: "completed",
    input: { schemaVersion: 2, problemId: "Prob-001" },
    assessment: { accepted: true },
    summary: { runId: "20260730T010203Z-abc123", problemId: "Prob-001" },
    reportHtml: "<!doctype html><title>Derived</title>",
    derivation,
  });

  const text = await readFile(join(root, "problems", "Prob-001", "assessments", "20260730T010203Z-abc123", "derivation.json"), "utf8");
  assert.deepEqual(JSON.parse(text), derivation);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/assessment-artifacts.test.mjs`

Expected: FAIL with `ENOENT` for `derivation.json`.

- [ ] **Step 3: Write minimal implementation**

In `lib/assessments/artifact-store.mjs`, inside `writeTerminalArtifacts()` after the optional `selection.json` write and before the optional `report.html` write, add:

```js
if (artifacts.derivation) await writeJson(join(run.stagingDir, "derivation.json"), artifacts.derivation);
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test tests/assessment-artifacts.test.mjs`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/assessments/artifact-store.mjs tests/assessment-artifacts.test.mjs
git commit -m "feat: store assessment derivation provenance"
```

### Task 2: Pure Valuation-Only Rebase

**Files:**
- Create: `lib/qec-portfolio/valuation-only-refresh.mjs`
- Create: `tests/qec-valuation-only-refresh.test.mjs`

**Interfaces:**
- Consumes: source artifact `{ run, input, assessment }`, verified valuation snapshot, and valuation input from `buildValuationInput(snapshot)`
- Produces:
  - `VALUATION_ONLY_NOTICE`
  - `sourceAssessmentQualifies({ run, input, assessment, report }) -> boolean`
  - `createValuationOnlyEnvelope({ sourceEnvelope, valuationSnapshot }) -> envelope`
  - `createValuationOnlyDerivation({ problemId, run, sourceRun, sourceInput, valuationSnapshot }) -> object`
  - `assertValuationOnlyVisibleReport(html) -> void`

- [ ] **Step 1: Write the failing tests**

Create `tests/qec-valuation-only-refresh.test.mjs` with tests that construct a valid source envelope using real policy dimension IDs, a valid snapshot with `qec-scientific-demand-v1`, and assert:

```js
assert.equal(derived.assessment.normalizedProblem, sourceEnvelope.assessment.normalizedProblem);
assert.deepEqual(derived.assessment.dimensions, sourceEnvelope.assessment.dimensions);
assert.deepEqual(derived.assessment.evidence, sourceEnvelope.assessment.evidence);
assert.equal(derived.assessment.quantitativeEvidence.snapshot.snapshotId, "20260730T010203Z-222222222222");
assert.equal(derived.assessment.quantitativeEvidence.scientificAttention.value.interval.base, 73.2);
assert.equal(derived.assessment.quantitativeEvidence.scientificAttention.formulaId, SCIENTIFIC_DEMAND_FORMULA_ID);
assert.deepEqual(derived.assessment.quantitativeEvidence.scoreAnchors, []);
```

Add one rejection test:

```js
assert.throws(
  () => createValuationOnlyEnvelope({ sourceEnvelope, valuationSnapshot: incompleteSnapshot }),
  /complete verified qec-scientific-demand-v1/
);
```

Add one source qualification test:

```js
assert.equal(sourceAssessmentQualifies({ run, input, assessment: { envelope: sourceEnvelope }, report: "<html>English</html>" }), true);
assert.equal(sourceAssessmentQualifies({ run, input, assessment: { envelope: { ...sourceEnvelope, language: "zh" } }, report: "<html>English</html>" }), false);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/qec-valuation-only-refresh.test.mjs`

Expected: FAIL with module not found or missing exported functions.

- [ ] **Step 3: Write minimal implementation**

Create `lib/qec-portfolio/valuation-only-refresh.mjs` with:

```js
export const VALUATION_ONLY_NOTICE = "Qualitative assessment retained from a prior completed run; quantitative valuation refreshed from the bound Scientific Demand snapshot.";
```

Implement `sourceAssessmentQualifies()` to accept only completed runs with `summary`, `input.schemaVersion === 2`, `assessment.envelope.language === "en"`, `assessment.envelope.assessment.schemaVersion === 2`, `assessment.envelope.assessment.visibility === "public"`, and no CJK in the run summary, assessment JSON, or report HTML.

Implement `createValuationOnlyEnvelope()` by structured-cloning `sourceEnvelope`, requiring `valuationSnapshot.manifest.complete === true`, `valuationSnapshot.manifest.citation.formulaId === SCIENTIFIC_DEMAND_FORMULA_ID`, and known `citation.scientificDemand` or `citation.scientificAttention`. Replace only:

```js
assessment.quantitativeEvidence = {
  domain: "quantum-computing",
  quantumArea: "error-correction-and-fault-tolerance",
  snapshot: {
    snapshotId: manifest.snapshotId,
    contentHash: manifest.contentHash,
    createdAt: manifest.createdAt,
    freshness: "fresh",
    visibility: manifest.visibility ?? "public",
  },
  scientificAttention: {
    value: structuredClone(citation.scientificDemand ?? citation.scientificAttention),
    momentum: structuredClone(citation.momentum),
    coverage: citation.coverage,
    concentration: citation.concentration ?? null,
    warnings: [...(citation.warnings ?? [])],
    formulaId: SCIENTIFIC_DEMAND_FORMULA_ID,
    components: structuredClone(citation.components),
    evidenceConfidence: citation.evidenceConfidence,
    paperCount: citation.paperCount,
  },
  technicalFeasibility: structuredClone(manifest.feasibility),
  socialValue: structuredClone(manifest.value),
  capturableValue: structuredClone(manifest.value),
  informationValue: { state: "unknown", reason: "No problem-specific sample-information value model has been identified." },
  scoreAnchors: [],
  sensitivity: [],
  assumptions: [VALUATION_ONLY_NOTICE],
  warnings: [...(manifest.confirmedCandidate?.warnings ?? []), ...(citation.warnings ?? [])],
};
```

Use the existing `validateAssessmentEnvelope()` in the function and throw `INVALID_VALUATION_ONLY_ENVELOPE` with joined validation errors if validation fails.

Implement `createValuationOnlyDerivation()` with `schemaVersion: 1`, `kind: "qec-valuation-only-refresh"`, `problemId`, `runId`, `sourceRunId`, `sourceSnapshotId: sourceInput.valuation.snapshotId`, `refreshedSnapshotId: valuationSnapshot.manifest.snapshotId`, `notice: VALUATION_ONLY_NOTICE`, and `createdAt: run.createdAt`.

Implement `assertValuationOnlyVisibleReport(html)` with regex checks for CJK, `Unknown`, `Pending`, and parenthesized ranges after a number.

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test tests/qec-valuation-only-refresh.test.mjs`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/qec-portfolio/valuation-only-refresh.mjs tests/qec-valuation-only-refresh.test.mjs
git commit -m "feat: derive valuation-only QEC assessments"
```

### Task 3: Publish Valuation-Only Runs

**Files:**
- Modify: `lib/qec-portfolio/valuation-only-refresh.mjs`
- Create: `scripts/refresh-qec-valuation-only.mjs`
- Test: `tests/qec-valuation-only-refresh.test.mjs`

**Interfaces:**
- Consumes:
  - `createArtifactStore({ rootDir })`
  - `createValuationSnapshotStore({ rootDir })`
  - `buildInputSnapshot({ rootDir, problem, envelope, skillPath, schemaPath, valuationSnapshot })`
  - `renderAssessmentReport({ run, input, envelope, computed })`
  - `summarizeCompletedAssessment({ run, envelope, computed, input })`
- Produces:
  - `findLatestCompletedSourceRun({ rootDir, store, problemId, excludeSnapshotId }) -> { run, input, assessment, report }`
  - `refreshValuationOnlyProblem({ rootDir, repository, store, valuationStore, problemId, snapshot }) -> { status, runId, sourceRunId, snapshotId }`
  - CLI that processes all 21 QEC IDs and prints JSON

- [ ] **Step 1: Write the failing tests**

Add tests that create a temp problem directory, write an old completed source run, call `refreshValuationOnlyProblem()`, and assert:

```js
assert.equal(result.status, "completed");
assert.equal(result.sourceRunId, "20260729T010203Z-source1");
const finalDir = join(rootDir, "problems", "Prob-001", "assessments", result.runId);
const derivation = JSON.parse(await readFile(join(finalDir, "derivation.json"), "utf8"));
assert.equal(derivation.sourceRunId, "20260729T010203Z-source1");
assert.equal(derivation.refreshedSnapshotId, "20260730T010203Z-222222222222");
const run = JSON.parse(await readFile(join(finalDir, "run.json"), "utf8"));
assert.equal(run.status, "completed");
assert.equal(run.summary.quantitative.snapshotId, "20260730T010203Z-222222222222");
assert.equal(run.summary.quantitative.scientificAttention.interval.base, 73.2);
assert.equal(run.summary.quantitative.technicalSuccess.interval.low, run.summary.quantitative.technicalSuccess.interval.base);
assert.equal(run.summary.quantitative.technicalSuccess.interval.high, run.summary.quantitative.technicalSuccess.interval.base);
assert.match(await readFile(join(finalDir, "report.html"), "utf8"), /Qualitative assessment retained/);
```

Add an idempotency test that calls the function twice with the same source run and snapshot and asserts the second result is:

```js
assert.deepEqual(second, {
  status: "verified-existing",
  problemId: "Prob-001",
  runId: first.runId,
  sourceRunId: "20260729T010203Z-source1",
  snapshotId: "20260730T010203Z-222222222222",
});
```

Add an immutability test that reads the source run's `run.json`, `assessment.json`, `input.json`, and `report.html` before refresh and asserts byte equality afterward.

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/qec-valuation-only-refresh.test.mjs`

Expected: FAIL with missing `refreshValuationOnlyProblem`.

- [ ] **Step 3: Write minimal implementation**

In `lib/qec-portfolio/valuation-only-refresh.mjs`, implement:

```js
export async function findLatestCompletedSourceRun({ rootDir, store, problemId, excludeSnapshotId }) { ... }
export async function refreshValuationOnlyProblem({ rootDir, repository, store, valuationStore, problemId, snapshot, now = () => new Date() }) { ... }
```

`findLatestCompletedSourceRun()` lists runs newest first, reads `input.json`, `assessment.json`, and `report.html` with `resolveExistingRunDir()`, skips failed runs, skips reports bound to `excludeSnapshotId`, and returns the first `sourceAssessmentQualifies()` result.

`refreshValuationOnlyProblem()` first looks for an existing completed run whose `derivation.json` has `kind === "qec-valuation-only-refresh"`, the same source run ID, and the same refreshed snapshot ID. If found, return `verified-existing`. Otherwise create an accepted run, build the derived envelope, validate it, build an input snapshot, render the report, prepend the provenance notice in the report body, assert visible safety, summarize it, and publish through `writeTerminalArtifacts()` with `derivation`.

Create `scripts/refresh-qec-valuation-only.mjs` that accepts `--root`, iterates `QEC_PORTFOLIO_BATCH_IDS`, verifies the latest current-formula snapshot from `createValuationSnapshotStore()`, calls `refreshValuationOnlyProblem()`, prints JSON, and exits nonzero if any problem fails.

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test tests/qec-valuation-only-refresh.test.mjs`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/qec-portfolio/valuation-only-refresh.mjs scripts/refresh-qec-valuation-only.mjs tests/qec-valuation-only-refresh.test.mjs
git commit -m "feat: publish valuation-only QEC revisions"
```

### Task 4: Ensure Portfolio Verification Selects Derived Reports

**Files:**
- Modify: `lib/qec-portfolio/batch-runner.mjs`
- Test: `tests/qec-portfolio-batch.test.mjs`

**Interfaces:**
- Consumes: existing `verifyQecPortfolio({ rootDir })`
- Produces: verifier acceptance only when completed English reports are bound to current formula snapshots and, if valuation-only, have valid derivation provenance

- [ ] **Step 1: Write the failing test**

Add a verifier-level unit test with a fake completed bound report whose `derivation.json` is malformed and assert the verifier reports an error. Then add valid derivation JSON and assert the verifier accepts it.

The expected malformed error should include:

```js
assert.match(result.errors.join("\n"), /invalid valuation-only derivation provenance/);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/qec-portfolio-batch.test.mjs`

Expected: FAIL because the verifier ignores `derivation.json`.

- [ ] **Step 3: Write minimal implementation**

In `lib/qec-portfolio/batch-runner.mjs`, add a `readDerivationIfPresent(rootDir, problemId, runId)` helper. In `verifyQecPortfolio()`, after `reusableAssessment()` returns a run, read derivation if present. If present, require:

```js
derivation.schemaVersion === 1
derivation.kind === "qec-valuation-only-refresh"
derivation.problemId === id
derivation.runId === reusable.runId
derivation.refreshedSnapshotId === snapshot.manifest.snapshotId
typeof derivation.sourceRunId === "string"
typeof derivation.sourceSnapshotId === "string"
derivation.notice === VALUATION_ONLY_NOTICE
```

Import `VALUATION_ONLY_NOTICE` from `lib/qec-portfolio/valuation-only-refresh.mjs`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test tests/qec-portfolio-batch.test.mjs`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/qec-portfolio/batch-runner.mjs tests/qec-portfolio-batch.test.mjs
git commit -m "test: verify valuation-only QEC provenance"
```

### Task 5: Run the Real Local Refresh

**Files:**
- Runtime writes only: `problems/Prob-*/valuation/snapshots/*`, `problems/Prob-*/assessments/*`, `.generated/*`

**Interfaces:**
- Consumes: user-provided OpenAlex API key from process environment only
- Produces: 21 completed English local reports bound to verified current-formula snapshots

- [ ] **Step 1: Generate or reuse missing current-formula snapshots**

Run:

```bash
OPENALEX_API_KEY=<process-env-only> node scripts/run-qec-portfolio.mjs --refresh-scientific-demand
```

Expected: This may stop at Codex usage limit after snapshots are generated. If Codex usage fails, do not retry qualitative assessment through Codex; proceed with valuation-only refresh for snapshots that were completed.

- [ ] **Step 2: Fill remaining snapshots if the batch stops early**

If any `Prob-009` through `Prob-021` still lacks a complete verified `qec-scientific-demand-v1` snapshot, run a snapshot-only helper through the valuation manager or add `--snapshots-only` to the new CLI under TDD before using it.

Expected: all 21 problem IDs have a verified complete current-formula snapshot.

- [ ] **Step 3: Publish valuation-only revisions**

Run:

```bash
node scripts/refresh-qec-valuation-only.mjs
```

Expected: JSON summary with 21 rows whose status is `completed` or `verified-existing`.

- [ ] **Step 4: Verify the portfolio**

Run:

```bash
node scripts/verify-qec-portfolio.mjs
```

Expected: `ok: true`, exactly 21 `snapshotIds`, exactly 21 `assessmentRunIds`, and every `citationFormulaIds` entry equal to `qec-scientific-demand-v1`.

- [ ] **Step 5: Commit runtime-manifest code only**

Do not commit ignored generated artifacts. Commit source/test changes only if this task required script changes:

```bash
git status --short
git add <source-and-test-files-only>
git commit -m "feat: refresh QEC portfolio valuation reports"
```

### Task 6: Final Verification and Local Web Smoke Test

**Files:**
- Read/validate: generated local reports
- No source changes unless verification exposes a defect

**Interfaces:**
- Consumes: `npm run build:app`, `node scripts/verify-qec-portfolio.mjs`, local HTTP server on port `5175`
- Produces: user-visible local portfolio and report URLs

- [ ] **Step 1: Run targeted unit tests**

Run:

```bash
node --test tests/assessment-artifacts.test.mjs tests/qec-valuation-only-refresh.test.mjs tests/qec-portfolio-batch.test.mjs
```

Expected: PASS.

- [ ] **Step 2: Run broader app tests**

Run:

```bash
npm run test:app
```

Expected: PASS.

- [ ] **Step 3: Build the local app**

Run:

```bash
npm run build:app
```

Expected: PASS.

- [ ] **Step 4: Start or restart the local server**

Run:

```bash
npm run dev -- --port 5175
```

Expected: server listens on `http://localhost:5175`.

- [ ] **Step 5: Smoke-test portfolio and one report**

Run HTTP checks for:

```text
http://localhost:5175/qec-portfolio
http://localhost:5175/__local/assessments/reports/Prob-001/<latest-run-id>
```

Expected: responses are HTTP 200 and visible HTML contains no Chinese text, `Unknown`, `Pending`, or score-range display.

- [ ] **Step 6: Final commit if any verification fixes were needed**

```bash
git status --short
git add <verified-source-and-test-files-only>
git commit -m "fix: harden QEC valuation-only refresh"
```
