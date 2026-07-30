# QEC Scientific Demand Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace raw citation totals for all 21 QEC problems with a reproducible, evidence-weighted Scientific Demand Score and remove misleading zero-citation presentation from the local portfolio and reports.

**Architecture:** Extend the existing OpenAlex normalization boundary so frozen paper records contain the metadata needed for a canonical problem literature set. Derive one versioned score in `lib/valuations/citations.mjs`, carry it through immutable valuation snapshots and assessment summaries, and keep the existing `scientificAttention` machine key for schema compatibility while changing its semantics, provenance, unit, and user-facing label. Refreshing the portfolio creates new snapshots and assessment runs instead of modifying older artifacts.

**Tech Stack:** Node.js ESM, TypeScript/React, Next.js, OpenAlex REST data, `node:test`, Playwright, immutable JSON valuation and assessment artifacts.

## Global Constraints

- The feature applies only to the 21 approved quantum error correction problems.
- The formula identifier is exactly `qec-scientific-demand-v1`.
- First-phase coefficients are influence `0.45`, momentum `0.30`, and breadth `0.15`; available coefficients are renormalized and network weight `0.10` remains reserved for phase two.
- Scientific demand measures scholarly attention and demand, not novelty, correctness, technical feasibility, social value, or economic value.
- Missing citation records never contribute numeric zero.
- No user-facing surface renders `0 citations`, `Anchor papers`, or a numeric range for the demand score.
- Application UI and generated reports remain English-only.
- Old valuation snapshots and assessment runs remain readable and immutable.
- Preserve `app/page.tsx`, `app/globals.css`, `app/layout.tsx`, and `.openai/hosting.json`.
- Do not publish `drafts/`, external literature full text, private valuation inputs, or generated local problem artifacts.

---

### Task 1: Canonical OpenAlex problem literature records

**Files:**
- Modify: `lib/valuations/openalex-client.mjs`
- Test: `tests/valuation-openalex.test.mjs`

**Interfaces:**
- Consumes: `createOpenAlexClient({ fetchFn, apiKey, maxWorks, now }).expand({ anchors, topicIds, normalizedProblem })`.
- Produces: each returned paper adds `fwci`, `authorIds`, `institutionIds`, and `matchConfidence`; duplicate DOI or normalized-title records collapse to one canonical paper.

- [ ] **Step 1: Write failing metadata and deduplication tests**

Add complete OpenAlex fixtures containing `fwci`, `authorships`, duplicate DOI/title variants, annual counts, and topics. Assert literal outputs:

```js
assert.equal(papers[0].fwci, 2.4);
assert.deepEqual(papers[0].authorIds, ["A1", "A2"]);
assert.deepEqual(papers[0].institutionIds, ["I1", "I2"]);
assert.equal(papers[0].matchConfidence, 1);
assert.equal(papers.filter((paper) => paper.doi === "10.1000/qec").length, 1);
```

The production regressions these tests catch are dropped FWCI/authorship metadata and duplicate preprint/journal contributions.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
node --test tests/valuation-openalex.test.mjs
```

Expected: FAIL because the new properties are absent and duplicate records remain.

- [ ] **Step 3: Implement canonical metadata normalization**

Add stable identifier helpers for authors and institutions, a normalized-title key, and a canonical preference comparison. Extend `normalizeWork()` with:

```js
fwci: Number.isFinite(work.fwci) ? Math.max(0, work.fwci) : null,
authorIds,
institutionIds,
matchConfidence: inclusionReason === "confirmed-anchor"
  ? (doi ? 1 : 0.95)
  : (doi ? 0.9 : 0.7),
```

Deduplicate first by DOI and then by normalized title. Prefer DOI-bearing records, then records with more complete annual counts, then higher citation counts, with OpenAlex ID as the deterministic tie-breaker.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
node --test tests/valuation-openalex.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit the canonical corpus boundary**

```bash
git add lib/valuations/openalex-client.mjs tests/valuation-openalex.test.mjs
git commit -m "feat: canonicalize QEC literature records"
```

---

### Task 2: Versioned Scientific Demand Score calculation

**Files:**
- Modify: `lib/valuations/citations.mjs`
- Modify: `tests/valuation-citations.test.mjs`

**Interfaces:**
- Consumes: canonical frozen paper records from Task 1 and `{ currentYear: integer }`.
- Produces: `calculateCitationMetrics(papers, options)` with `formulaId`, `scientificDemand`, compatibility alias `scientificAttention`, component values, evidence confidence, coverage, paper count, warnings, and raw audit totals.

- [ ] **Step 1: Write failing component and score tests**

Create literal fixtures that independently exercise:

```js
const result = calculateCitationMetrics(papers, { currentYear: 2026 });
assert.equal(result.formulaId, "qec-scientific-demand-v1");
assert.equal(result.components.influence.weight, 0.45);
assert.equal(result.components.momentum.weight, 0.30);
assert.equal(result.components.breadth.weight, 0.15);
assert.equal(result.scientificDemand.unit, "score-100");
assert.equal(result.scientificAttention, result.scientificDemand);
assert.equal(result.evidenceConfidence, "high");
```

Add separate cases proving a missing `citedByCount` is excluded, missing momentum renormalizes available weights, one paper yields low confidence, three yield medium, and five papers with at least 80% normalized coverage yield high confidence. Hand-calculate and assert exact one-decimal score values.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
node --test tests/valuation-citations.test.mjs
```

Expected: FAIL because `scientificDemand`, component records, and confidence do not exist.

- [ ] **Step 3: Implement pure component helpers**

Implement:

```js
export const SCIENTIFIC_DEMAND_FORMULA_ID = "qec-scientific-demand-v1";
```

Use evidence weight `relevance * matchConfidence * independenceDiscount`, with a confirmed-reference relevance floor. Calculate:

```text
influence = weighted median(citationNormalizedPercentile)
momentum = logistic(weighted median(log((latest + 1) / (prior + 1))))
paper breadth = min(1, log(1 + canonicalPaperCount) / log(21))
institution breadth = min(1, log(1 + independentInstitutionCount) / log(21))
breadth = 0.6 * paper breadth + 0.4 * institution breadth
score = 100 * weighted available component sum / available weight sum
```

Round the score to one decimal. Influence is mandatory; if unavailable return `unknownValue("Citation evidence insufficient.")`. Preserve explicit zero counts only in raw audit data, and never substitute zero for missing counts.

- [ ] **Step 4: Run focused and neighboring tests**

Run:

```bash
node --test tests/valuation-citations.test.mjs tests/valuation-job-manager.test.mjs
```

Expected: the citation tests pass; update only assertions whose intended metric contract changed.

- [ ] **Step 5: Commit the calculation model**

```bash
git add lib/valuations/citations.mjs tests/valuation-citations.test.mjs tests/valuation-job-manager.test.mjs
git commit -m "feat: calculate QEC scientific demand"
```

---

### Task 3: Snapshot provenance and assessment integration

**Files:**
- Modify: `lib/valuations/job-manager.mjs`
- Modify: `lib/assessments/point-estimates.mjs`
- Modify: `lib/assessments/contract.mjs`
- Modify: `schemas/research-problem-assessment.schema.json`
- Test: `tests/valuation-job-manager.test.mjs`
- Test: `tests/assessment-point-estimates.test.mjs`
- Test: `tests/assessment-contract.test.mjs`
- Test: `tests/assessment-job-manager.test.mjs`

**Interfaces:**
- Consumes: `calculateCitationMetrics()` from Task 2 and frozen valuation inputs.
- Produces: public quantitative key `scientificAttention` carrying a `score-100` point value, `estimateKind: "scientific-demand-model"`, `formulaId`, component audit data, and evidence confidence.

- [ ] **Step 1: Write failing provenance and compatibility tests**

Assert a new valuation snapshot contains:

```js
assert.equal(snapshot.manifest.citation.formulaId, "qec-scientific-demand-v1");
assert.equal(snapshot.manifest.scientificAttention.unit, "score-100");
assert.equal(snapshot.manifest.scientificAttention.estimateKind, "scientific-demand-model");
```

Update the point-estimate fixture so a missing raw citation count cannot create a known zero. Assert old snapshots with valid normalized percentiles derive the new score from frozen papers, while a snapshot without normalized evidence returns an evidence-gap state rather than zero.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
node --test tests/valuation-job-manager.test.mjs tests/assessment-point-estimates.test.mjs tests/assessment-contract.test.mjs tests/assessment-job-manager.test.mjs
```

Expected: FAIL on the old citation-total semantics and missing formula provenance.

- [ ] **Step 3: Carry the versioned metric through snapshots**

Change `valuationOutputs()` to expose `scientificDemand` as the existing `scientificAttention` contract field, with atomic evidence and all source IDs. Add `formulaId`, components, evidence confidence, paper count, and coverage under `manifest.citation`.

Replace `citationSummary()` in `point-estimates.mjs` with a helper that:

1. uses the frozen versioned demand metric when present;
2. otherwise calls `calculateCitationMetrics()` on frozen papers for backward-readable old inputs;
3. never constructs a count-valued point from `rawCitationTotal`.

- [ ] **Step 4: Validate the assessment contract**

Allow the explicit optional audit fields required by `scientific-demand-model` without weakening existing visibility, source, interval, or evidence graph checks. Keep the public summary key `quantitative.scientificAttention` for compatibility.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run:

```bash
node --test tests/valuation-job-manager.test.mjs tests/assessment-point-estimates.test.mjs tests/assessment-contract.test.mjs tests/assessment-job-manager.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit snapshot and assessment integration**

```bash
git add lib/valuations/job-manager.mjs lib/assessments/point-estimates.mjs lib/assessments/contract.mjs schemas/research-problem-assessment.schema.json tests/valuation-job-manager.test.mjs tests/assessment-point-estimates.test.mjs tests/assessment-contract.test.mjs tests/assessment-job-manager.test.mjs
git commit -m "feat: persist scientific demand provenance"
```

---

### Task 4: Clear English-only presentation with no zero citations

**Files:**
- Modify: `lib/assessments/view-model.mjs`
- Modify: `lib/assessments/html-report.mjs`
- Modify: `app/qec-portfolio/portfolio-panel.tsx`
- Modify: `app/problems/[id]/assessment-panel.tsx`
- Test: `tests/assessment-view-model.test.mjs`
- Test: `tests/assessment-report.test.mjs`
- Test: `tests/qec-portfolio-page.test.mjs`
- Test: `tests/e2e/local-assessment.spec.ts`

**Interfaces:**
- Consumes: the compatibility key `scientificAttention` containing a demand-score quantitative value.
- Produces: `Scientific Demand Score`, one `/ 100` value, evidence-confidence copy, method notes, and explicit nonnumeric citation-data states.

- [ ] **Step 1: Write failing formatter and report tests**

Assert literal behavior:

```js
assert.equal(formatScientificAttention({
  state: "known",
  interval: { low: 68.4, base: 68.4, high: 68.4 },
  unit: "score-100",
  evidenceConfidence: "high",
}), "68.4 / 100 · High evidence confidence");
```

Add report fixtures with explicit zero and missing paper citation counts. Assert the HTML contains `No matched citations` and `Not reported`, and does not contain `0 citations`, `>0</td>`, `Anchor papers`, or `Scientific Attention`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
node --test tests/assessment-view-model.test.mjs tests/assessment-report.test.mjs tests/qec-portfolio-page.test.mjs
```

Expected: FAIL on old labels and raw zero rendering.

- [ ] **Step 3: Implement shared display semantics**

Update `formatScientificAttention()` and the portfolio `quantitativeText()` path for `unit === "score-100"`. Rename visible labels to `Scientific Demand Score`, `Selected Reference Papers`, and `Problem Literature Set`. In the HTML report, format paper citation cells as:

```js
paper.citedByCount === 0
  ? "No matched citations"
  : Number.isFinite(paper.citedByCount)
    ? String(paper.citedByCount)
    : "Not reported"
```

Add the three-component method note and keep raw totals in the audit section only.

- [ ] **Step 4: Run unit and component tests**

Run:

```bash
node --test tests/assessment-view-model.test.mjs tests/assessment-report.test.mjs tests/qec-portfolio-page.test.mjs
```

Expected: PASS with no visible Chinese or old citation-total labels.

- [ ] **Step 5: Commit the presentation change**

```bash
git add lib/assessments/view-model.mjs lib/assessments/html-report.mjs app/qec-portfolio/portfolio-panel.tsx 'app/problems/[id]/assessment-panel.tsx' tests/assessment-view-model.test.mjs tests/assessment-report.test.mjs tests/qec-portfolio-page.test.mjs tests/e2e/local-assessment.spec.ts
git commit -m "feat: present scientific demand scores"
```

---

### Task 5: Immutable portfolio refresh for the new formula

**Files:**
- Modify: `lib/qec-portfolio/batch-runner.mjs`
- Modify: `scripts/run-qec-portfolio.mjs`
- Modify: `scripts/verify-qec-portfolio.mjs`
- Test: `tests/qec-portfolio-batch.test.mjs`
- Test: `tests/qec-portfolio-reader.test.mjs`

**Interfaces:**
- Consumes: latest verified snapshots, `SCIENTIFIC_DEMAND_FORMULA_ID`, and CLI flag `--refresh-scientific-demand`.
- Produces: new immutable snapshots and assessments whenever the latest reusable artifact does not use `qec-scientific-demand-v1`.

- [ ] **Step 1: Write failing snapshot-reuse tests**

Create stores containing a complete old snapshot without the formula ID and a complete new snapshot with it. Assert:

```js
assert.equal(oldResult.problems[0].valuation, "completed");
assert.equal(currentResult.problems[0].valuation, "verified-existing");
```

Also assert the refresh flag forces a new valuation even if a current-formula snapshot exists, while no previous snapshot directory is modified or removed.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
node --test tests/qec-portfolio-batch.test.mjs tests/qec-portfolio-reader.test.mjs
```

Expected: FAIL because snapshot reuse ignores citation formula version.

- [ ] **Step 3: Implement version-aware reuse and refresh**

Add `requiredCitationFormulaId` and `forceValuationRefresh` options to `createQecPortfolioBatchRunner()`. A reusable snapshot must satisfy:

```js
snapshot.manifest.complete === true
  && snapshot.manifest.citation?.formulaId === requiredCitationFormulaId
```

Parse `--refresh-scientific-demand` in `scripts/run-qec-portfolio.mjs`, pass the options through, and include the formula ID in verification diagnostics.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
node --test tests/qec-portfolio-batch.test.mjs tests/qec-portfolio-reader.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit immutable refresh support**

```bash
git add lib/qec-portfolio/batch-runner.mjs scripts/run-qec-portfolio.mjs scripts/verify-qec-portfolio.mjs tests/qec-portfolio-batch.test.mjs tests/qec-portfolio-reader.test.mjs
git commit -m "feat: refresh versioned QEC demand evidence"
```

---

### Task 6: Refresh all 21 local reports and verify the product

**Files:**
- Generated locally, gitignored: `problems/Prob-*/valuation/`
- Generated locally, gitignored: `problems/Prob-*/assessments/`
- Generated locally, gitignored: `.generated/`
- Verify: `tests/e2e/local-assessment.spec.ts`

**Interfaces:**
- Consumes: `OPENALEX_API_KEY`, the local Codex assessment runtime, and Tasks 1--5.
- Produces: 21 current-formula valuation snapshots, 21 bound completed assessments, new HTML reports, and a healthy local portfolio response.

- [ ] **Step 1: Run the complete unit suite**

Run:

```bash
make test
```

Expected: PASS with no failures.

- [ ] **Step 2: Run the production build**

Run:

```bash
make build
```

Expected: trusted knowledge validation, no-execute render, and application build all pass.

- [ ] **Step 3: Refresh immutable QEC evidence and assessments**

Run:

```bash
node scripts/run-qec-portfolio.mjs --refresh-scientific-demand
```

Expected: JSON status `complete`, all 21 problems complete, and each latest snapshot records `qec-scientific-demand-v1`.

- [ ] **Step 4: Verify every portfolio artifact**

Run:

```bash
node scripts/verify-qec-portfolio.mjs
```

Expected: `ok: true`, exactly Prob-001 through Prob-021, with latest assessment IDs bound to current-formula snapshot IDs.

- [ ] **Step 5: Run local end-to-end checks**

Run:

```bash
npx playwright test --config playwright.assessment.config.ts tests/e2e/local-assessment.spec.ts
```

Expected: PASS for the portfolio and detailed report flows; no visible `0 citations`, `Anchor papers`, ranges, pending evaluation copy, or Chinese UI text.

- [ ] **Step 6: Inspect the live local endpoints**

Check the existing local service at `http://localhost:5175/qec-portfolio` and one latest detailed report. Confirm a positive `/ 100` Scientific Demand Score or an explicit evidence-insufficient state, selected-reference terminology, confidence, and method note.

- [ ] **Step 7: Commit any final test-only corrections**

```bash
git add tests/e2e/local-assessment.spec.ts
git commit -m "test: verify QEC scientific demand reports"
```

Skip this commit when no tracked correction remains.
