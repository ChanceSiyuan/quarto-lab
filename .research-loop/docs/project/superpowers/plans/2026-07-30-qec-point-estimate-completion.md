# QEC Point-Estimate Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep all 21 QEC portfolio problems while completing every public comparison metric with a reproducible point estimate and removing numeric ranges from user-facing pages and reports.

**Architecture:** Add one pure assessment point-estimate module that derives citation totals and modeled technical-success percentages without changing the validated model envelope. New completed-run summaries and old-artifact backfills consume the same helper. Existing UI and report formatters keep interval-shaped storage for audit compatibility but render only the central value.

**Tech Stack:** Node.js 22 ESM, React 19, Next/vinext, Node test runner, JSON assessment artifacts.

## Global Constraints

- Preserve all 21 QEC portfolio problems.
- A measured sealed-benchmark technical result takes precedence over a modeled estimate.
- Modeled technical success uses Plausibility 35%, Executable Objective 20%, Correctness & Anti-gaming 20%, Incremental Feedback 15%, and Attempt Runtime 10%.
- Scientific Attention is the accepted-anchor OpenAlex citation total.
- User-facing scores, percentages, citation counts, and money values display one central value only.
- Modeled results must be labeled `Model estimate`; broad economic values must remain labeled as proxies.
- Private evidence must remain redacted.
- Preserve interval-shaped machine data for audit and recalculation.
- Do not modify `app/page.tsx`, `app/globals.css`, or `app/layout.tsx`.
- Preserve the Sites project ID in `.openai/hosting.json` exactly.

---

## File Structure

- Create `lib/assessments/point-estimates.mjs`: pure derivation and provenance for citation totals and technical-success estimates.
- Create `tests/assessment-point-estimates.test.mjs`: formula, citation, precedence, error, and privacy coverage.
- Modify `lib/assessments/contract.mjs`: include derived point estimates in new completed-run summaries.
- Modify `lib/assessments/job-manager.mjs`: pass the frozen input into summary creation.
- Modify `tests/assessment-contract.test.mjs` and `tests/assessment-job-manager.test.mjs`: summary integration coverage.
- Modify `lib/assessments/view-model.mjs`: point-only score, quantitative, citation, technical, and money formatting.
- Modify `tests/assessment-view-model.test.mjs`: point-only formatter coverage.
- Modify `app/problems/[id]/assessment-panel.tsx`: label and render the modeled technical-success point.
- Modify `app/qec-portfolio/portfolio-panel.tsx`: point-only portfolio values and model labels.
- Modify `lib/qec-portfolio/reader.mjs`: require complete public summaries and remove pending display substitutions.
- Modify `tests/qec-portfolio-reader.test.mjs` and `tests/qec-portfolio-page.test.mjs`: all-21 completeness and copy coverage.
- Modify `lib/assessments/html-report.mjs`: use derived points, central-value formatting, and technical model method note.
- Modify `tests/assessment-report.test.mjs`: report copy and no-range coverage.
- Create `scripts/backfill-qec-point-estimates.mjs`: atomically update the latest completed artifact for Prob-001 through Prob-021.
- Create `tests/qec-point-estimate-backfill.test.mjs`: temporary-directory backfill coverage.
- Modify `package.json`: expose `qec:backfill:point-estimates` and include new tests in `test:unit:problems`.

---

### Task 1: Pure Point-Estimate Derivation

**Files:**
- Create: `tests/assessment-point-estimates.test.mjs`
- Create: `lib/assessments/point-estimates.mjs`

**Interfaces:**
- Consumes: validated assessment object and frozen assessment input.
- Produces: `deriveAssessmentPointEstimates({ assessment, input })` returning `{ scientificAttention, technicalSuccess, technicalSuccessMethod }`.
- Produces: `TECHNICAL_SUCCESS_DIMENSION_WEIGHTS`, a frozen map whose values sum to 1.

- [ ] **Step 1: Write failing formula and citation tests**

```js
import assert from "node:assert/strict";
import test from "node:test";
import {
  TECHNICAL_SUCCESS_DIMENSION_WEIGHTS,
  deriveAssessmentPointEstimates,
} from "../lib/assessments/point-estimates.mjs";

function dimension(id, estimate) {
  return { id, score: { min: estimate, estimate, max: estimate } };
}

function fixture({ measured = null, visibility = "public", rawCitationTotal = 3 } = {}) {
  return {
    assessment: {
      visibility,
      dimensions: {
        researchValue: [dimension("plausibility", 3.75)],
        autoresearchSuitability: [
          dimension("executable_objective", 3),
          dimension("correctness_and_anti_gaming", 2.5),
          dimension("incremental_feedback", 3.5),
          dimension("attempt_runtime", 3),
        ],
      },
      quantitativeEvidence: { technicalFeasibility: measured },
    },
    input: {
      valuation: {
        recalculationInputs: {
          manifest: { citation: { rawCitationTotal } },
          papers: [{ id: "W1", citedByCount: rawCitationTotal }],
        },
      },
    },
  };
}

test("technical-success weights sum to one", () => {
  assert.equal(Object.values(TECHNICAL_SUCCESS_DIMENSION_WEIGHTS).reduce((a, b) => a + b, 0), 1);
});

test("derives the approved technical-success point formula", () => {
  const result = deriveAssessmentPointEstimates(fixture());
  assert.equal(result.technicalSuccess.interval.base, 64.8);
  assert.deepEqual(result.technicalSuccess.interval, { low: 64.8, base: 64.8, high: 64.8 });
  assert.equal(result.technicalSuccess.unit, "percent");
  assert.equal(result.technicalSuccess.estimateKind, "model");
  assert.equal(result.scientificAttention.interval.base, 3);
  assert.equal(result.scientificAttention.unit, "count");
});

test("preserves a measured technical result", () => {
  const measured = { state: "known", interval: { low: 70, base: 72.5, high: 75 }, unit: "percent", visibility: "public" };
  const result = deriveAssessmentPointEstimates(fixture({ measured }));
  assert.equal(result.technicalSuccess, measured);
  assert.equal(result.technicalSuccessMethod.kind, "measured");
});

test("does not derive public values from a private assessment", () => {
  assert.deepEqual(deriveAssessmentPointEstimates(fixture({ visibility: "private" })), {
    scientificAttention: null,
    technicalSuccess: null,
    technicalSuccessMethod: null,
  });
});

test("identifies each missing required dimension", () => {
  const value = fixture();
  value.assessment.dimensions.autoresearchSuitability = [];
  assert.throws(
    () => deriveAssessmentPointEstimates(value),
    /executable_objective, correctness_and_anti_gaming, incremental_feedback, attempt_runtime/,
  );
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test tests/assessment-point-estimates.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `lib/assessments/point-estimates.mjs`.

- [ ] **Step 3: Implement the pure helper**

```js
export const TECHNICAL_SUCCESS_DIMENSION_WEIGHTS = Object.freeze({
  plausibility: 0.35,
  executable_objective: 0.20,
  correctness_and_anti_gaming: 0.20,
  incremental_feedback: 0.15,
  attempt_runtime: 0.10,
});

function point(value) {
  return { low: value, base: value, high: value };
}

function citationTotal(input) {
  const frozen = input?.valuation?.recalculationInputs;
  const recorded = frozen?.manifest?.citation?.rawCitationTotal;
  if (Number.isFinite(recorded)) return Math.max(0, recorded);
  return (frozen?.papers ?? []).reduce(
    (total, paper) => total + (Number.isFinite(paper?.citedByCount) ? Math.max(0, paper.citedByCount) : 0),
    0,
  );
}

export function deriveAssessmentPointEstimates({ assessment, input }) {
  if (assessment?.visibility === "private") {
    return { scientificAttention: null, technicalSuccess: null, technicalSuccessMethod: null };
  }
  const measured = assessment?.quantitativeEvidence?.technicalFeasibility;
  const scientificAttention = {
    state: "known",
    interval: point(citationTotal(input)),
    unit: "count",
    visibility: "public",
    estimateKind: "citation-total",
  };
  if (measured?.state === "known") {
    return { scientificAttention, technicalSuccess: measured, technicalSuccessMethod: { kind: "measured" } };
  }
  const dimensions = [
    ...(assessment?.dimensions?.researchValue ?? []),
    ...(assessment?.dimensions?.autoresearchSuitability ?? []),
  ];
  const estimates = new Map(dimensions.map((item) => [item.id, item.score?.estimate]));
  const missing = Object.keys(TECHNICAL_SUCCESS_DIMENSION_WEIGHTS).filter((id) => !Number.isFinite(estimates.get(id)));
  if (missing.length) throw new Error(`Missing technical-success dimensions: ${missing.join(", ")}`);
  const weighted = Object.entries(TECHNICAL_SUCCESS_DIMENSION_WEIGHTS)
    .reduce((total, [id, weight]) => total + estimates.get(id) * weight, 0);
  const value = Number(((weighted / 5) * 100).toFixed(1));
  return {
    scientificAttention,
    technicalSuccess: {
      state: "known",
      interval: point(value),
      unit: "percent",
      visibility: "public",
      estimateKind: "model",
    },
    technicalSuccessMethod: {
      kind: "model",
      formulaId: "qec-technical-success-v1",
      weights: TECHNICAL_SUCCESS_DIMENSION_WEIGHTS,
    },
  };
}
```

- [ ] **Step 4: Run the test and verify GREEN**

Run: `node --test tests/assessment-point-estimates.test.mjs`

Expected: 5 tests pass.

- [ ] **Step 5: Commit the isolated helper**

```bash
git add lib/assessments/point-estimates.mjs tests/assessment-point-estimates.test.mjs
git commit -m "feat: derive QEC point estimates"
```

---

### Task 2: Complete New Assessment Summaries

**Files:**
- Modify: `lib/assessments/contract.mjs`
- Modify: `lib/assessments/job-manager.mjs`
- Modify: `tests/assessment-contract.test.mjs`
- Modify: `tests/assessment-job-manager.test.mjs`

**Interfaces:**
- Consumes: `deriveAssessmentPointEstimates({ assessment, input })` from Task 1.
- Changes: `summarizeCompletedAssessment({ run, envelope, computed, input })` requires the frozen input for version-2 assessments.
- Produces: completed summaries with known `scientificAttention`, known `technicalSuccess`, and `technicalSuccessMethod`.

- [ ] **Step 1: Add a failing summary test**

Extend the existing version-2 assessment summary fixture:

```js
const summary = summarizeCompletedAssessment({
  run,
  envelope,
  computed,
  input: { valuation: { recalculationInputs: { manifest: { citation: { rawCitationTotal: 9 } } } } },
});
assert.equal(summary.quantitative.scientificAttention.interval.base, 9);
assert.equal(summary.quantitative.technicalSuccess.state, "known");
assert.equal(summary.quantitative.technicalSuccess.estimateKind, "model");
assert.equal(summary.quantitative.technicalSuccessMethod.formulaId, "qec-technical-success-v1");
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `node --test tests/assessment-contract.test.mjs tests/assessment-job-manager.test.mjs`

Expected: FAIL because summary creation still copies unknown quantitative values and job manager does not pass `input`.

- [ ] **Step 3: Integrate the helper minimally**

In `summarizeCompletedAssessment`, derive the point estimates only for schema version 2 and replace these summary fields:

```js
const points = deriveAssessmentPointEstimates({ assessment, input });
summary.quantitative = {
  scientificAttention: points.scientificAttention,
  technicalSuccess: points.technicalSuccess,
  technicalSuccessMethod: points.technicalSuccessMethod,
  socialValue: quantitative.socialValue,
  capturableValue: quantitative.capturableValue,
  largestSensitivity,
  snapshotId: quantitative.snapshot.snapshotId,
  freshness: quantitative.snapshot.freshness,
};
```

Change the job-manager call to:

```js
const summary = summarizeCompletedAssessment({
  run: job.run,
  envelope: result.envelope,
  computed: result.computed,
  input,
});
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `node --test tests/assessment-contract.test.mjs tests/assessment-job-manager.test.mjs`

Expected: all tests pass.

- [ ] **Step 5: Commit summary integration**

```bash
git add lib/assessments/contract.mjs lib/assessments/job-manager.mjs tests/assessment-contract.test.mjs tests/assessment-job-manager.test.mjs
git commit -m "feat: complete QEC assessment summaries"
```

---

### Task 3: Render Central Values Only

**Files:**
- Modify: `lib/assessments/view-model.mjs`
- Modify: `tests/assessment-view-model.test.mjs`
- Modify: `app/problems/[id]/assessment-panel.tsx`
- Modify: `app/qec-portfolio/portfolio-panel.tsx`
- Modify: `tests/qec-portfolio-page.test.mjs`

**Interfaces:**
- Consumes: interval-shaped score and quantitative values.
- Produces: `formatScoreInterval`, `formatKnownInterval`, `formatMoneyInterval`, `formatScientificAttention`, and `formatTechnicalSuccessEstimate`, all returning point-only display strings.

- [ ] **Step 1: Change formatter expectations first**

```js
assert.equal(formatScoreInterval({ min: 52, estimate: 72.5, max: 88.75 }), "72.5");
assert.equal(formatKnownInterval({ state: "known", interval: { low: 62.5, base: 72.5, high: 82.5 }, unit: "percent" }), "72.5%");
assert.equal(formatScientificAttention({ state: "known", interval: { low: 3, base: 3, high: 3 }, unit: "count" }), "3 citations");
assert.equal(formatTechnicalSuccessEstimate({ state: "known", interval: { low: 64.8, base: 64.8, high: 64.8 }, unit: "percent", estimateKind: "model" }), "64.8% · Model estimate");
assert.equal(formatMoneyInterval({ state: "known", interval: { low: 43e9, base: 57e9, high: 71e9 }, unit: "USD_2035", currency: "USD", priceBaseYear: 2035 }), "$57B · USD 2035");
```

Add source-level assertions to `tests/qec-portfolio-page.test.mjs`:

```js
assert.match(source, /Technical Success Estimate/);
assert.match(source, /Model estimate/);
assert.doesNotMatch(source, /Pending sealed evaluation|Pending measurement/);
assert.doesNotMatch(source, /score\.min|score\.max|interval\.low|interval\.high/);
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `node --test tests/assessment-view-model.test.mjs tests/qec-portfolio-page.test.mjs`

Expected: FAIL with interval strings and pending copy still present.

- [ ] **Step 3: Implement point-only formatters and labels**

Use only `score.estimate` and `value.interval.base`. Change the assessment panel metric label from `Technical gate status` to `Technical Success Estimate`. In the QEC portfolio, change both desktop and card labels and make `quantitativeText` ignore `low` and `high`.

The money formatter must return:

```js
return `${formatMoneyAmount(value.interval.base, currency)}${currency || year ? ` · ${currency}${year ? ` ${year}` : ""}` : ""}`;
```

The technical formatter must return:

```js
export function formatTechnicalSuccessEstimate(value) {
  if (value?.state !== "known") return "—";
  const point = formatKnownInterval(value);
  return value.estimateKind === "model" ? `${point} · Model estimate` : `${point} · Measured`;
}
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `node --test tests/assessment-view-model.test.mjs tests/qec-portfolio-page.test.mjs`

Expected: all tests pass and no source assertion finds pending or range access.

- [ ] **Step 5: Commit presentation changes**

```bash
git add lib/assessments/view-model.mjs tests/assessment-view-model.test.mjs 'app/problems/[id]/assessment-panel.tsx' app/qec-portfolio/portfolio-panel.tsx tests/qec-portfolio-page.test.mjs
git commit -m "feat: display QEC point estimates"
```

---

### Task 4: Require Complete Public Portfolio Rows

**Files:**
- Modify: `lib/qec-portfolio/reader.mjs`
- Modify: `tests/qec-portfolio-reader.test.mjs`

**Interfaces:**
- Consumes: completed run summaries produced by Task 2 or backfilled by Task 6.
- Produces: 21 sorted public rows with known scientific-attention and technical-success points.

- [ ] **Step 1: Write failing all-row completeness assertions**

Update the fixture summaries to include known point values, then assert:

```js
assert.equal(response.count, 21);
assert.equal(response.rows.length, 21);
for (const row of response.rows) {
  assert.equal(row.scientificAttention.state, "known");
  assert.equal(Number.isFinite(row.scientificAttention.interval.base), true);
  assert.equal(row.technicalSuccess.state, "known");
  assert.equal(Number.isFinite(row.technicalSuccess.interval.base), true);
  assert.equal(row.socialValue.state, "known");
  assert.equal(row.capturableValue.state, "known");
}
assert.doesNotMatch(JSON.stringify(response), /pending|not-modeled|Pending sealed evaluation/i);
```

Add one explicit incomplete-summary test:

```js
await assert.rejects(
  () => incompleteReader.read(),
  /Prob-002.*scientificAttention.*technicalSuccess/,
);
```

- [ ] **Step 2: Run the reader test and verify RED**

Run: `node --test tests/qec-portfolio-reader.test.mjs`

Expected: FAIL because the reader currently substitutes pending display gaps and includes unassessed rows.

- [ ] **Step 3: Remove pending substitutions and validate completeness**

Delete `DISPLAY_GAPS.technicalSuccess` and scientific-attention not-modeled substitution. Add a pure `assertCompletePublicRow(row)` that collects missing metric names and throws an error containing the problem ID. Keep the existing public money proxy fallbacks and privacy redaction.

- [ ] **Step 4: Run the reader test and verify GREEN**

Run: `node --test tests/qec-portfolio-reader.test.mjs`

Expected: all tests pass, including all-21 completeness and private redaction.

- [ ] **Step 5: Commit reader rules**

```bash
git add lib/qec-portfolio/reader.mjs tests/qec-portfolio-reader.test.mjs
git commit -m "fix: require complete QEC portfolio estimates"
```

---

### Task 5: Point-Only Detailed Reports

**Files:**
- Modify: `lib/assessments/html-report.mjs`
- Modify: `tests/assessment-report.test.mjs`

**Interfaces:**
- Consumes: `deriveAssessmentPointEstimates({ assessment, input })` and point-only formatters.
- Produces: standalone reports with central values and a reproducible technical model note.

- [ ] **Step 1: Write failing report assertions**

```js
assert.match(html, /<strong>Research Value<\/strong><br>72\.5<\/div>/);
assert.match(html, /Technical Success Estimate/);
assert.match(html, /64\.8%/);
assert.match(html, /Model estimate/);
assert.match(html, /Plausibility 35%/);
assert.match(html, /Executable Objective 20%/);
assert.match(html, /Correctness &amp; Anti-gaming 20%/);
assert.match(html, /Incremental Feedback 15%/);
assert.match(html, /Attempt Runtime 10%/);
assert.doesNotMatch(html, /Pending sealed evaluation|Pending measurement/);
assert.doesNotMatch(html, /72\.5 \(52-88\.75\)/);
assert.doesNotMatch(html, /\$57B \(\$43B-\$71B/);
```

- [ ] **Step 2: Run the report test and verify RED**

Run: `node --test tests/assessment-report.test.mjs`

Expected: FAIL because reports currently render intervals and pending technical copy.

- [ ] **Step 3: Render derived point values and method note**

Change `scoreText` to return `interval.estimate`. At report render time, call the point-estimate helper with `envelope.assessment` and `input`; use its scientific and technical results when the original quantitative values are unknown. Add this method note for modeled results:

```html
<p class="muted"><strong>Technical Success Estimate:</strong> Model estimate calculated from Plausibility 35%, Executable Objective 20%, Correctness &amp; Anti-gaming 20%, Incremental Feedback 15%, and Attempt Runtime 10%. It is not a measured sealed-benchmark result.</p>
```

Use the point-only view-model formatters for quantitative and monetary rows.

- [ ] **Step 4: Run the report test and verify GREEN**

Run: `node --test tests/assessment-report.test.mjs`

Expected: all tests pass and report output contains no range or pending copy.

- [ ] **Step 5: Commit report changes**

```bash
git add lib/assessments/html-report.mjs tests/assessment-report.test.mjs
git commit -m "feat: render point-only QEC reports"
```

---

### Task 6: Backfill the 21 Existing Assessment Artifacts

**Files:**
- Create: `scripts/backfill-qec-point-estimates.mjs`
- Create: `tests/qec-point-estimate-backfill.test.mjs`
- Modify: `package.json`
- Runtime updates: `problems/Prob-001` through `problems/Prob-021`, latest completed `run.json` and `report.html` only.

**Interfaces:**
- Consumes: assessment store artifact layout, `deriveAssessmentPointEstimates`, `summarizeCompletedAssessment`, and `renderAssessmentReport`.
- Produces: `backfillQecPointEstimates({ rootDir, problemIds, dryRun })` returning `{ updated, skipped, errors }`.

- [ ] **Step 1: Write the failing temporary-directory backfill test**

Create one temporary public assessment artifact containing an unknown technical value, interval scores, frozen citation total, and all five dimension estimates. Then assert:

```js
const result = await backfillQecPointEstimates({ rootDir, problemIds: ["Prob-001"] });
assert.deepEqual(result.updated, ["Prob-001"]);
const run = JSON.parse(await readFile(join(rootDir, "problems/Prob-001/assessments/run-1/run.json"), "utf8"));
assert.equal(run.summary.quantitative.scientificAttention.interval.base, 3);
assert.equal(run.summary.quantitative.technicalSuccess.interval.base, 64.8);
assert.equal(run.summary.quantitative.technicalSuccess.estimateKind, "model");
const report = await readFile(join(rootDir, "problems/Prob-001/assessments/run-1/report.html"), "utf8");
assert.match(report, /64\.8%/);
assert.doesNotMatch(report, /Pending sealed evaluation|\(52-88\.75\)/);
```

Add a failure test where `attempt_runtime` is missing and assert the original `run.json` and `report.html` byte contents remain unchanged.

- [ ] **Step 2: Run the backfill test and verify RED**

Run: `node --test tests/qec-point-estimate-backfill.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for the backfill script.

- [ ] **Step 3: Implement staged atomic backfill**

For each problem:

1. Select the newest completed run containing `run.json`, `input.json`, and `assessment.json`.
2. Parse `{ envelope, computed }` from `assessment.json`.
3. Build the new summary with `summarizeCompletedAssessment({ run, envelope, computed, input })`.
4. Build the new report with `renderAssessmentReport({ run, input, envelope, computed })`.
5. Validate both in memory.
6. Write sibling `.tmp` files and rename them over `run.json` and `report.html` only after both writes succeed.
7. On any error, remove only the two explicit `.tmp` files and report the problem ID without modifying original artifacts.

Export the function for tests and run it only when `import.meta.url === pathToFileURL(process.argv[1]).href`. Add:

```json
"qec:backfill:point-estimates": "node scripts/backfill-qec-point-estimates.mjs"
```

Add both new test files to `test:unit:problems`.

- [ ] **Step 4: Run the backfill test and verify GREEN**

Run: `node --test tests/qec-point-estimate-backfill.test.mjs`

Expected: all tests pass and the failure case preserves original bytes.

- [ ] **Step 5: Run a dry run over all 21 local problems**

Run: `npm run qec:backfill:point-estimates -- --dry-run`

Expected: `21 ready, 0 errors`; no artifact timestamps or hashes change.

- [ ] **Step 6: Run the real backfill**

Run: `npm run qec:backfill:point-estimates`

Expected: `21 updated, 0 errors`.

- [ ] **Step 7: Verify all 21 artifact outputs directly**

Run:

```bash
node -e 'const fs=require("fs"),p=require("path");let rows=[];for(let i=1;i<=21;i++){let id=`Prob-${String(i).padStart(3,"0")}`,root=p.join("problems",id,"assessments"),runs=fs.readdirSync(root).sort().reverse();let dir=runs.map(r=>p.join(root,r)).find(d=>JSON.parse(fs.readFileSync(p.join(d,"run.json"))).status==="completed");let run=JSON.parse(fs.readFileSync(p.join(dir,"run.json")));rows.push([id,run.summary.quantitative.scientificAttention.interval.base,run.summary.quantitative.technicalSuccess.interval.base]);}if(rows.length!==21||rows.some(r=>!Number.isFinite(r[1])||!Number.isFinite(r[2])))process.exit(1);console.log(rows);'
```

Expected: 21 rows, each with finite citation and technical-success point values.

- [ ] **Step 8: Commit the reusable backfill implementation only**

```bash
git add scripts/backfill-qec-point-estimates.mjs tests/qec-point-estimate-backfill.test.mjs package.json
git commit -m "feat: backfill QEC point estimates"
```

Do not stage ignored or runtime-generated assessment artifacts unless they were already tracked and intentionally changed by the feature branch.

---

### Task 7: Full Verification and Local Redeployment

**Files:**
- Verify all modified files.
- Do not modify preserved dashboard files.

**Interfaces:**
- Consumes: completed Tasks 1 through 6.
- Produces: verified local pages at `/qec-portfolio` and a detailed report.

- [ ] **Step 1: Run focused feature tests**

Run:

```bash
node --test tests/assessment-point-estimates.test.mjs tests/assessment-contract.test.mjs tests/assessment-job-manager.test.mjs tests/assessment-view-model.test.mjs tests/assessment-report.test.mjs tests/qec-portfolio-reader.test.mjs tests/qec-portfolio-page.test.mjs tests/qec-point-estimate-backfill.test.mjs
```

Expected: zero failures.

- [ ] **Step 2: Run the full problem/assessment unit suite**

Run: `npm run test:unit:problems`

Expected: zero failures.

- [ ] **Step 3: Run repository validation and build**

Run: `npm run lint`

Expected: exit 0 with no lint errors.

Run: `npm run build`

Expected: exit 0; trusted knowledge validation and application build both succeed.

- [ ] **Step 4: Search generated user-facing outputs for forbidden copy**

Run:

```bash
rg -n "Pending sealed evaluation|Pending measurement|[0-9.]+ \([0-9.]+[-–][0-9.]+\)" problems/Prob-*/assessments/*/report.html dist public --glob '*.html'
```

Expected: no matches in the latest report for each of Prob-001 through Prob-021 or in current build output.

- [ ] **Step 5: Restart the local application on its configured port**

Resolve the current listener with `lsof -nP -iTCP -sTCP:LISTEN`, stop only the matching research-loop `vinext` process, then start the existing approved local command. Do not terminate unrelated processes.

- [ ] **Step 6: Browser smoke test**

Verify `/qec-portfolio` shows exactly 21 rows, each with numeric V/A/S, citation count, technical-success estimate, and two economic proxy points. Verify one detailed report displays the model method note and contains no range or pending copy.

- [ ] **Step 7: Inspect the final diff and status**

Run: `git diff --check`

Expected: no whitespace errors.

Run: `git status --short`

Expected: only intentional feature files plus pre-existing unrelated working-tree changes; no temporary backfill files.
