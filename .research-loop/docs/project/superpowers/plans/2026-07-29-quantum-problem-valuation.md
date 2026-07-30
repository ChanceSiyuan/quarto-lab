# Quantum Research-Problem Valuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auditable, quantum-computing-only evidence layer that quantifies scientific attention, technical feasibility, dual-track economic value, and information value while preserving the existing V/A/S assessment policy.

**Architecture:** A new `lib/valuations/` boundary owns external-evidence candidates, OpenAlex metadata, deterministic calculations, immutable snapshots, privacy propagation, and refresh jobs. The existing local assessment service exposes the valuation workflow on loopback-only routes and passes one frozen snapshot into assessment schema v2. Existing version-1 assessments and non-quantum problems continue unchanged.

**Tech Stack:** Node.js 22.13+ ESM, built-in `fetch`, JSON Schema draft 2020-12, React 19, TypeScript 5.9, Vite/vinext, Node test runner, Playwright.

## Global Constraints

- Implement only in this Research Loop repository; do not modify or depend on an external `quantum.harness` checkout.
- At execution time, use `superpowers:using-git-worktrees` before editing implementation files. Base the worktree on commit `3a0cf34` or a descendant containing this plan.
- The current checkout has unrelated uncommitted changes in `schemas/research-problem-assessment.schema.json` and `tests/assessment-codex-adapter.test.mjs`. Do not alter, stage, or discard those working-tree files. The isolated implementation must preserve their explicit-Codex-type intent when schema v2 is built.
- Use test-first changes and one focused commit per task.
- Add no runtime dependency; use Node's built-in crypto, filesystem, HTTP, child-process, and fetch APIs.
- Quantitative valuation supports only `domain: quantum-computing`; non-quantum problems keep assessment v1.
- Keep V/A/S dimensions, weights, harmonic combination, and verdict thresholds unchanged.
- Treat external evidence as external; never write it to `knowledge/`, never answer from `drafts/`, and never publish it as trusted knowledge.
- Refresh is explicit, loopback-only, and immutable. It may not start an autoresearch campaign.
- Unknown values use an explicit tagged object; never encode missing data as `0` or ambiguous `null`.
- Preserve `app/page.tsx`, `app/globals.css`, and `app/layout.tsx`. Put new panel styles in a scoped CSS module.
- Keep `.openai/hosting.json` and its existing Sites project ID byte-for-byte unchanged.
- Public-input research is automatic. The user confirms only anchor selection, high-sensitivity assumptions, and private values.
- Any output depending on `visibility: private` is private. Public rendering must redact the value, and public-safe validation must reject an unredacted private value.

## File Structure

### New files

- `lib/valuations/types.mjs` — constants and constructors for known/unknown values, evidence tiers, visibility, areas, and workflow states.
- `lib/valuations/contract.mjs` — strict host validation for inputs, evidence candidates, confirmations, snapshots, and quantitative assessment blocks.
- `lib/valuations/formulas.mjs` — interval arithmetic, stage-tree probability/cost, ENPV, EVSI/ENBS, and one-at-a-time sensitivity.
- `lib/valuations/citations.mjs` — scientific-attention weighted median, momentum, coverage, and concentration.
- `lib/valuations/openalex-client.mjs` — bounded OpenAlex lookups and one-hop cited/citing/topic expansion.
- `lib/valuations/snapshot-store.mjs` — contained paths, canonical JSON, non-recursive SHA-256 identity, atomic freeze, read, and tamper checks.
- `lib/valuations/freshness.mjs` — evidence-class expiry and advisory freshness state.
- `lib/valuations/privacy.mjs` — visibility propagation and public-safe redaction/validation.
- `lib/valuations/codex-research-adapter.mjs` — read-only Codex evidence-research process and structured candidate parsing.
- `lib/valuations/job-manager.mjs` — queued research, exact confirmation, OpenAlex hydration, calculation, and snapshot freeze.
- `schemas/quantum-valuation-research.schema.json` — Codex candidate output schema.
- `schemas/quantum-valuation-snapshot.schema.json` — frozen snapshot schema.
- `tests/valuation-contract.test.mjs`, `tests/valuation-formulas.test.mjs`, `tests/valuation-citations.test.mjs`, `tests/valuation-openalex.test.mjs`, `tests/valuation-snapshot.test.mjs`, `tests/valuation-codex-adapter.test.mjs`, `tests/valuation-job-manager.test.mjs`, and `tests/valuation-privacy.test.mjs` — focused unit tests.
- `app/problems/[id]/assessment-panel.module.css` — progressive valuation panel styling only.

### Modified files

- `lib/problems/schema.mjs` and `tests/problem-schema.test.mjs` — optional quantum scope fields and classification.
- `skills/add-problem/SKILL.md` and `tests/agent/skill-contracts.test.ts` — record confirmed scope on new quantum drafts.
- `lib/assessments/policy.mjs` and `tests/assessment-policy.test.mjs` — policy version 2 constants and score-anchor consistency without changing weights or verdicts.
- `schemas/research-problem-assessment.schema.json`, `lib/assessments/contract.mjs`, and `tests/assessment-contract.test.mjs` — v1/v2 union and quantitative evidence validation.
- `lib/assessments/input-snapshot.mjs`, `lib/assessments/staleness.mjs`, and their tests — valuation snapshot identity and freshness in assessment inputs.
- `lib/assessments/codex-adapter.mjs` and `tests/assessment-codex-adapter.test.mjs` — provide the frozen valuation packet to the read-only evaluator.
- `lib/assessments/job-manager.mjs` and `tests/assessment-job-manager.test.mjs` — quantum assessment readiness and snapshot binding.
- `lib/assessments/local-service.mjs`, `scripts/local-assessment-service.mjs`, and `tests/assessment-local-service.test.mjs` — valuation research/confirmation endpoints and manager wiring.
- `lib/assessments/view-model.mjs`, `lib/assessments/html-report.mjs`, and their tests — versioned summary, state copy, audit sections, and redaction.
- `app/problems/[id]/assessment-panel.tsx` and `tests/e2e/local-assessment.spec.ts` — refresh, confirmation, metric cards, and report flow.
- `tests/e2e/local-assessment-fixture.ts` — deterministic quantum valuation fixture.
- `scripts/build-problem-index.mjs` and `tests/problem-indexer.test.mjs` — explicit public-build private-data gate.
- `docs/local-assessments.md` — environment, workflow, artifacts, freshness, privacy, and smoke test.
- `package.json` — include every new valuation unit test in `test:unit:problems`.

---

### Task 1: Quantum Scope Contract

**Files:**
- Modify: `lib/problems/schema.mjs`
- Modify: `tests/problem-schema.test.mjs`
- Modify: `skills/add-problem/SKILL.md`
- Modify: `tests/agent/skill-contracts.test.ts`

**Interfaces:**
- Produces: `QUANTUM_DOMAIN`, `QUANTUM_AREAS`, and `classifyQuantumScope(problem, { legacyArea } = {})` returning `{ status: "supported" | "unsupported" | "needs_input", domain: string | null, quantumArea: string | null, source: "manifest" | "legacy" }`.
- Consumes: existing `validateProblemManifest(manifest, context)`.

- [ ] **Step 1: Write failing manifest and classification tests**

Add tests that accept a complete quantum pair, reject `quantumArea` without the quantum domain, reject an unknown area, preserve a legacy manifest, and classify missing legacy scope as `needs_input`:

```js
import {
  QUANTUM_AREAS,
  classifyQuantumScope,
} from "../lib/problems/schema.mjs";

test("accepts an explicit quantum-computing scope", () => {
  const candidate = manifest({
    domain: "quantum-computing",
    quantumArea: "algorithms-and-applications",
  });
  assert.equal(validateProblemManifest(candidate).ok, true);
  assert.equal(QUANTUM_AREAS.length, 6);
  assert.deepEqual(classifyQuantumScope(candidate), {
    status: "supported",
    domain: "quantum-computing",
    quantumArea: "algorithms-and-applications",
    source: "manifest",
  });
});

test("does not guess scope for a legacy problem", () => {
  assert.equal(validateProblemManifest(manifest()).ok, true);
  assert.equal(classifyQuantumScope(manifest()).status, "needs_input");
});
```

- [ ] **Step 2: Run the focused tests and confirm the new exports fail**

Run: `node --test tests/problem-schema.test.mjs`

Expected: FAIL because `QUANTUM_AREAS` and `classifyQuantumScope` are not exported.

- [ ] **Step 3: Implement optional scope validation and classification**

Add exact constants and fields without changing `schemaVersion`:

```js
export const QUANTUM_DOMAIN = "quantum-computing";
export const QUANTUM_AREAS = Object.freeze([
  "algorithms-and-applications",
  "error-correction-and-fault-tolerance",
  "compilation-and-architecture",
  "hardware-and-control",
  "resource-estimation-and-benchmarks",
  "classical-simulation-and-verification",
]);

const ALLOWED_FIELDS = new Set([
  ...REQUIRED_FIELDS,
  "rejection",
  "domain",
  "quantumArea",
]);

export function classifyQuantumScope(problem, { legacyArea = null } = {}) {
  if (!Object.hasOwn(problem ?? {}, "domain")) {
    return legacyArea && QUANTUM_AREAS.includes(legacyArea)
      ? { status: "supported", domain: QUANTUM_DOMAIN, quantumArea: legacyArea, source: "legacy" }
      : { status: "needs_input", domain: null, quantumArea: null, source: "legacy" };
  }
  if (problem.domain !== QUANTUM_DOMAIN) {
    return { status: "unsupported", domain: problem.domain, quantumArea: null, source: "manifest" };
  }
  return QUANTUM_AREAS.includes(problem.quantumArea)
    ? { status: "supported", domain: QUANTUM_DOMAIN, quantumArea: problem.quantumArea, source: "manifest" }
    : { status: "needs_input", domain: QUANTUM_DOMAIN, quantumArea: null, source: "manifest" };
}
```

In `validateProblemManifest`, require a non-empty `domain` when supplied; require `quantumArea` exactly when `domain === QUANTUM_DOMAIN`; reject `quantumArea` for every other domain.

- [ ] **Step 4: Update the add-problem contract and its test**

Add this sentence under `Prepare the preview` in `skills/add-problem/SKILL.md`:

```markdown
When the discussed candidate is explicitly a quantum-computing problem, include
`domain: quantum-computing` and one confirmed `quantumArea` from
`lib/problems/schema.mjs`; if the area is ambiguous, ask one question before the
preview. Do not infer or add quantum scope to a non-quantum candidate.
```

Extend the skill-contract test to assert those literals exist in the skill text.

- [ ] **Step 5: Run scope and skill tests**

Run: `node --test tests/problem-schema.test.mjs && node --import tsx --test tests/agent/skill-contracts.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit the scope contract**

```bash
git add lib/problems/schema.mjs tests/problem-schema.test.mjs skills/add-problem/SKILL.md tests/agent/skill-contracts.test.ts
git commit -m "feat: add quantum problem scope contract"
```

### Task 2: Atomic Evidence and Deterministic Valuation Formulas

**Files:**
- Create: `lib/valuations/types.mjs`
- Create: `lib/valuations/contract.mjs`
- Create: `lib/valuations/formulas.mjs`
- Create: `tests/valuation-contract.test.mjs`
- Create: `tests/valuation-formulas.test.mjs`

**Interfaces:**
- Produces: `knownInterval({ low, base, high, unit, visibility, sourceIds })`, `unknownValue(reason)`, `validateAtomicEvidence(value)`, `validateQuantitativeEvidence(value)`, `calculateStageTree(stages)`, `calculateSocialEnpv(model)`, `calculateCapturableEnpv(model)`, `calculateInformationValue(model)`, and `rankOneWaySensitivity({ model, calculate, decisionMetric })`.
- Consumes: no prior valuation code.

- [ ] **Step 1: Write failing tagged-value and provenance tests**

Cover ordered intervals, zero as a legitimate known value, explicit unknowns, supported units, unique source IDs, reported/inferred status, and private visibility propagation:

```js
test("distinguishes a known zero from missing evidence", () => {
  assert.equal(validateAtomicEvidence({
    id: "cost-1",
    state: "known",
    interval: { low: 0, base: 0, high: 0 },
    unit: "USD_2026",
    visibility: "public",
    evidenceState: "reported",
    sourceIds: ["src-1"],
  }).ok, true);
  assert.deepEqual(unknownValue("No public contract price."), {
    state: "unknown",
    reason: "No public contract price.",
  });
});
```

- [ ] **Step 2: Run contract tests and verify missing modules fail**

Run: `node --test tests/valuation-contract.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `lib/valuations/contract.mjs`.

- [ ] **Step 3: Implement the strict tagged-value boundary**

Use these exact enums in `types.mjs`:

```js
export const EVIDENCE_TIERS = Object.freeze(["primary", "authoritative-secondary", "vendor-or-news", "assumption"]);
export const EVIDENCE_STATES = Object.freeze(["reported", "inferred"]);
export const VISIBILITIES = Object.freeze(["public", "private"]);
export const VALUE_STATES = Object.freeze(["known", "unknown"]);
export const SUPPORTED_CURRENCIES = Object.freeze(["USD", "CNY", "EUR", "GBP", "JPY"]);

export function unknownValue(reason) {
  return { state: "unknown", reason };
}

export function knownInterval({ low, base, high, unit, visibility = "public", sourceIds = [] }) {
  return { state: "known", interval: { low, base, high }, unit, visibility, sourceIds };
}
```

`validateAtomicEvidence` must return `{ ok: true, value }` or `{ ok: false, errors: string[] }` and reject extra fields, unordered/non-finite intervals, missing locators, duplicate source IDs, invalid evidence tiers, inferred values without `derivation.formulaId` and `derivation.inputIds`, and currency values without `currency`, `priceBaseYear`, and `conversionSourceId`. A known capture-share input must cite a licensing, contract, usage-price, product-margin, or business-model source. `validateQuantitativeEvidence` validates unique IDs and every cross-reference across stages, sources, inputs, outputs, assumptions, and score anchors.

- [ ] **Step 4: Write failing hand-calculated formula tests**

Use exact fixtures for conditional success, failure-path cost, ENPV, and ENBS:

```js
test("charges stage costs even when the final path fails", () => {
  const result = calculateStageTree([
    { id: "theory", success: { low: 0.5, base: 0.5, high: 0.5 }, cost: { low: 100, base: 100, high: 100 }, year: 0 },
    { id: "validation", success: { low: 0.5, base: 0.5, high: 0.5 }, cost: { low: 80, base: 80, high: 80 }, year: 1 },
  ]);
  assert.deepEqual(result.success, { low: 0.25, base: 0.25, high: 0.25 });
  assert.equal(result.expectedCost.base, 140);
});

test("computes information value separately from deployment value", () => {
  assert.deepEqual(calculateInformationValue({
    valueWithSampleInformation: { low: 90, base: 120, high: 150 },
    valueCurrentInformation: { low: 70, base: 80, high: 90 },
    studyCost: { low: 10, base: 15, high: 20 },
  }), {
    evsi: { low: 0, base: 40, high: 80 },
    enbs: { low: -20, base: 25, high: 70 },
  });
});
```

- [ ] **Step 5: Run formula tests and confirm missing functions fail**

Run: `node --test tests/valuation-formulas.test.mjs`

Expected: FAIL because the formula exports do not exist.

- [ ] **Step 6: Implement interval and valuation arithmetic**

Implement monotone interval operations and charge a stage only when its parent path is reached:

```js
export function calculateStageTree(stages) {
  let reach = { low: 1, base: 1, high: 1 };
  let expectedCost = { low: 0, base: 0, high: 0 };
  for (const stage of stages) {
    expectedCost = addIntervals(expectedCost, multiplyIntervals(reach, stage.cost));
    reach = multiplyIntervals(reach, stage.success);
  }
  return { success: reach, expectedCost };
}

export function calculateInformationValue({ valueWithSampleInformation, valueCurrentInformation, studyCost }) {
  const evsi = clampIntervalFloor(subtractIntervals(valueWithSampleInformation, valueCurrentInformation), 0);
  return { evsi, enbs: subtractIntervals(evsi, studyCost) };
}
```

`calculateSocialEnpv` and `calculateCapturableEnpv` must discount each yearly expected benefit and expected cost separately. `rankOneWaySensitivity` must replace one base input at a time with its low and high values, recompute the named decision metric, and sort by absolute swing then stable input ID.

- [ ] **Step 7: Run the valuation core tests**

Run: `node --test tests/valuation-contract.test.mjs tests/valuation-formulas.test.mjs`

Expected: PASS.

- [ ] **Step 8: Commit the valuation core**

```bash
git add lib/valuations/types.mjs lib/valuations/contract.mjs lib/valuations/formulas.mjs tests/valuation-contract.test.mjs tests/valuation-formulas.test.mjs
git commit -m "feat: add deterministic valuation core"
```

### Task 3: Immutable Snapshot, Freshness, and Privacy Boundary

**Files:**
- Create: `schemas/quantum-valuation-snapshot.schema.json`
- Create: `lib/valuations/snapshot-store.mjs`
- Create: `lib/valuations/freshness.mjs`
- Create: `lib/valuations/privacy.mjs`
- Create: `tests/valuation-snapshot.test.mjs`
- Create: `tests/valuation-privacy.test.mjs`
- Modify: `.gitignore`
- Modify: `scripts/build-problem-index.mjs`
- Modify: `tests/problem-indexer.test.mjs`

**Interfaces:**
- Consumes: `validateAtomicEvidence` and tagged values from Task 2; `assertContained` from `lib/assessments/paths.mjs`.
- Produces: `canonicalJson(value)`, `snapshotDigest({ manifest, papers, marketEvidence })`, `createValuationSnapshotStore({ rootDir, now })`, `evaluateValuationFreshness(snapshot, now)`, `propagateVisibility(inputs)`, `redactPrivate(value)`, and `assertPublicSafeValuation(value)`.

- [ ] **Step 1: Write failing canonical-hash and atomic-freeze tests**

Assert object-key order independence, array-order preservation, exclusion of `manifest.snapshotId` and `manifest.contentHash`, exact paths, atomic rename, and tamper detection:

```js
test("snapshot identity is stable and non-self-referential", () => {
  const left = snapshotDigest({
    manifest: { schemaVersion: 1, snapshotId: "ignored-a", contentHash: "ignored-b", quantumArea: "hardware-and-control" },
    papers: [{ id: "W1" }],
    marketEvidence: [{ id: "src-1" }],
  });
  const right = snapshotDigest({
    marketEvidence: [{ id: "src-1" }],
    papers: [{ id: "W1" }],
    manifest: { quantumArea: "hardware-and-control", contentHash: "changed", snapshotId: "changed", schemaVersion: 1 },
  });
  assert.equal(left, right);
});
```

- [ ] **Step 2: Run snapshot tests and verify failure**

Run: `node --test tests/valuation-snapshot.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement contained snapshot storage**

`createValuationSnapshotStore` must expose:

```js
{
  readInputs(problemId),
  writeInputs(problemId, inputs),
  freeze(problemId, { manifest, papers, marketEvidence }),
  read(problemId, snapshotId),
  list(problemId),
  verify(problemId, snapshotId)
}
```

Freeze into `.generated/valuation-snapshots/<run-id>/`, calculate the digest with identity fields omitted, set `snapshotId` to `<YYYYMMDDTHHMMSSZ>-<first12hex>`, write exactly `manifest.json`, `papers.json`, and `market-evidence.json`, verify the staged bytes, then rename to `problems/<id>/valuation/snapshots/<snapshot-id>/`. Refuse an existing destination, symlink escape, unsupported extra file, or hash mismatch.

- [ ] **Step 4: Write failing freshness and privacy tests**

```js
test("freshness is advisory and class-specific", () => {
  const result = evaluateValuationFreshness({
    manifest: { createdAt: "2026-01-01T00:00:00Z" },
    evidenceDates: {
      citation: "2026-01-01T00:00:00Z",
      hardware: "2026-06-01T00:00:00Z",
      market: "2026-01-01T00:00:00Z",
    },
  }, new Date("2026-07-01T00:00:00Z"));
  assert.deepEqual(result.staleClasses, ["citation", "market"]);
});

test("private input makes a dependent output private", () => {
  assert.equal(propagateVisibility([
    { visibility: "public" },
    { visibility: "private" },
  ]), "private");
  assert.throws(() => assertPublicSafeValuation({ visibility: "private", value: 42 }), /private/i);
  assert.deepEqual(redactPrivate({ visibility: "private", value: 42 }), {
    visibility: "private",
    redacted: true,
  });
});
```

- [ ] **Step 5: Implement freshness and private-data fail-closed behavior**

Use exact default stale windows `{ citation: 90, hardware: 90, classicalBaseline: 90, market: 180, contract: 180, adoption: 180 }` days. Government evidence uses its stored `nextPublicationAt`; private user input has no automatic expiry. Recursive redaction must remove `value`, `interval`, `currency`, and `derivation` from any private subtree.

Add `problems/Prob-*/valuation/inputs.private.json` to `.gitignore`. Public `inputs.json` may hold confirmation IDs and public values; private values must be read from the ignored overlay and must mark the frozen snapshot private.

- [ ] **Step 6: Add the explicit public-build gate**

Teach `scripts/build-problem-index.mjs` to recognize `--public`. Before writing either generated index in public mode, scan each valuation snapshot and assessment summary below a problem with `assertPublicSafeValuation`; abort with the exact problem-relative path on an unredacted private value. The default invocation remains local and permits private artifacts.

Add a `tests/problem-indexer.test.mjs` fixture that succeeds without `--public` and rejects the same private sentinel in public mode. Task 10 will add `--public` to the production `npm run build` command.

- [ ] **Step 7: Run snapshot, privacy, and public-gate tests**

Run: `node --test tests/valuation-snapshot.test.mjs tests/valuation-privacy.test.mjs tests/problem-indexer.test.mjs`

Expected: PASS.

- [ ] **Step 8: Commit snapshot and privacy boundaries**

```bash
git add schemas/quantum-valuation-snapshot.schema.json lib/valuations/snapshot-store.mjs lib/valuations/freshness.mjs lib/valuations/privacy.mjs tests/valuation-snapshot.test.mjs tests/valuation-privacy.test.mjs scripts/build-problem-index.mjs tests/problem-indexer.test.mjs .gitignore
git commit -m "feat: freeze auditable valuation snapshots"
```

### Task 4: OpenAlex Collection and Citation Metrics

**Files:**
- Create: `lib/valuations/openalex-client.mjs`
- Create: `lib/valuations/citations.mjs`
- Create: `tests/valuation-openalex.test.mjs`
- Create: `tests/valuation-citations.test.mjs`

**Interfaces:**
- Consumes: confirmed persistent identifiers and `fetch`.
- Produces: `createOpenAlexClient({ fetchFn, apiKey, baseUrl, maxWorks })`, whose `expand({ anchors, topicIds, normalizedProblem })` returns normalized paper records; `calculatePaperRelevance({ normalizedProblem, anchorTopicIds, paper })`; and `calculateCitationMetrics(papers, { currentYear })` returning `{ scientificAttention, momentum, coverage, concentration, warnings }`.

- [ ] **Step 1: Write failing bounded-client tests**

Use fake `fetchFn` responses to assert DOI normalization, stable-ID dedupe, one-hop references/citations/topic queries, maximum 100 returned works, timeout via `AbortSignal`, non-2xx provider errors, and absence of accidental full-text storage:

```js
test("deduplicates DOI and OpenAlex aliases into one paper", async () => {
  const client = createOpenAlexClient({ fetchFn: fakeOpenAlexFetch(), apiKey: "test-key", maxWorks: 100 });
  const papers = await client.expand({
    anchors: ["https://doi.org/10.1234/example", "W123"],
    topicIds: ["T7"],
  });
  assert.equal(papers.filter((paper) => paper.id === "W123").length, 1);
  assert.equal("fullText" in papers[0], false);
});
```

- [ ] **Step 2: Run OpenAlex tests and verify failure**

Run: `node --test tests/valuation-openalex.test.mjs`

Expected: FAIL because `createOpenAlexClient` does not exist.

- [ ] **Step 3: Implement the OpenAlex adapter**

Normalize each work to these exact fields:

```js
{
  id,
  doi,
  title,
  publicationYear,
  topicIds,
  citedByCount,
  citationNormalizedPercentile,
  countsByYear,
  referencedWorkIds,
  abstractHash,
  matchedProblemTokens,
  relevance,
  inclusionReason,
  accessedAt
}
```

Require `OPENALEX_API_KEY` only for the live client. Missing credentials return provider code `OPENALEX_KEY_REQUIRED`; they do not invent citation values. Apply a 20-second timeout per request, a 100-work final ceiling, and stable sorting by OpenAlex ID. Reconstruct an abstract only in memory for relevance scoring; persist its SHA-256 and matched problem tokens, not the abstract or a full-text body.

`calculatePaperRelevance` lowercases and tokenizes the normalized problem, title, and abstract; removes tokens shorter than three characters; and returns `0.6 * titleJaccard + 0.3 * abstractJaccard + 0.1 * anchorTopicOverlap`. Always include confirmed anchors. Include expanded neighbors at score `>= 0.15`; freeze both the score and inclusion reason so the filter is reproducible.

- [ ] **Step 4: Write failing weighted-median and warning tests**

```js
test("uses relevance-weighted normalized percentiles, not raw citations", () => {
  const result = calculateCitationMetrics([
    paper({ id: "W1", relevance: 1, citationNormalizedPercentile: 0.8, citedByCount: 10 }),
    paper({ id: "W2", relevance: 0.2, citationNormalizedPercentile: 0.2, citedByCount: 10000 }),
  ], { currentYear: 2026 });
  assert.equal(result.scientificAttention.state, "known");
  assert.equal(result.scientificAttention.interval.base, 80);
  assert.equal(result.rawCitationTotal, 10010);
});

test("returns unknown when comparable coverage is insufficient", () => {
  const result = calculateCitationMetrics([paper({ citationNormalizedPercentile: null })], { currentYear: 2026 });
  assert.equal(result.scientificAttention.state, "unknown");
});
```

- [ ] **Step 5: Implement citation calculations**

Scientific attention is `100 * weightedMedian(normalized percentile, relevance weight)`. Fewer than two comparable relevant papers yields explicit unknown. Coverage is the relevant-weight share with a normalized percentile. Concentration is the maximum share of relevance-weighted citation contribution. Momentum uses the log ratio `(latestCompleteYear + 1) / (priorCompleteYear + 1)`, reports a weighted median, and never enters novelty. Raw citation total remains audit-only.

- [ ] **Step 6: Run OpenAlex and citation tests**

Run: `node --test tests/valuation-openalex.test.mjs tests/valuation-citations.test.mjs`

Expected: PASS.

- [ ] **Step 7: Commit the citation provider**

```bash
git add lib/valuations/openalex-client.mjs lib/valuations/citations.mjs tests/valuation-openalex.test.mjs tests/valuation-citations.test.mjs
git commit -m "feat: add normalized quantum citation evidence"
```

### Task 5: Read-only Codex Commercial Research Candidate

**Files:**
- Create: `schemas/quantum-valuation-research.schema.json`
- Create: `lib/valuations/codex-research-adapter.mjs`
- Create: `tests/valuation-codex-adapter.test.mjs`
- Modify: `skills/assess-research-problem/SKILL.md`
- Modify: `tests/agent/skill-contracts.test.ts`

**Interfaces:**
- Consumes: `{ problem, problemMarkdown, quantumScope, currentInputs, priorSnapshotSummary, schemaPath }`.
- Produces: `checkValuationCodexPreflight(options)` and `runValuationResearch(options)` returning `{ ok, candidate, eventsText, stderr }` or `{ ok: false, code, message, stderr }`.

- [ ] **Step 1: Write failing schema and process tests**

Assert that every `enum`/`const` has an explicit type, unsupported Codex schema keywords are absent, the process is `codex exec --sandbox read-only`, the final message is parsed from JSONL, timeouts terminate the child, and stderr is retained:

```js
test("valuation research runs Codex read-only with a strict schema", async () => {
  const calls = [];
  const result = await runValuationResearch({
    rootDir: "/repo",
    problem: { id: "Prob-007", title: "Fixture", summary: "Summary" },
    problemMarkdown: "Candidate question.",
    quantumScope: { status: "supported", domain: "quantum-computing", quantumArea: "hardware-and-control" },
    schemaPath: "/repo/schemas/quantum-valuation-research.schema.json",
    spawnFn: fakeSuccessfulCodex(calls, validResearchCandidate()),
  });
  assert.equal(result.ok, true);
  assert.match(calls[0].args.join(" "), /exec --sandbox read-only/);
});
```

- [ ] **Step 2: Run adapter tests and verify failure**

Run: `node --test tests/valuation-codex-adapter.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Define the exact candidate schema**

Require these top-level fields with `additionalProperties: false`:

```json
{
  "schemaVersion": 1,
  "problemId": "Prob-007",
  "scope": {},
  "anchorCandidates": [],
  "paperInclusionRules": {},
  "technicalStages": [],
  "classicalBaseline": {},
  "marketEvidence": [],
  "atomicInputs": [],
  "materialAssumptions": [],
  "warnings": []
}
```

An anchor candidate requires `id`, `persistentId`, `title`, `relevanceRationale`, and `sourceUrl`; the array has `minItems: 1` and `maxItems: 10`. A market-evidence item requires the atomic provenance fields from Task 2. A material assumption requires `id`, `question`, `proposedValue`, `sensitivityRank`, and `confirmationRequired`.

- [ ] **Step 4: Implement the process adapter**

Follow `lib/assessments/codex-adapter.mjs` process handling, but use a valuation-specific prompt that states:

```text
Research public evidence for this quantum-computing problem. Prefer primary
sources. Return structured candidates only. Do not write files, do not claim
external evidence is trusted knowledge, do not use company valuation or raw TAM
as the problem value, and mark unsupported inputs unknown.
```

Validate the final candidate with both the JSON schema passed to Codex and `lib/valuations/contract.mjs` after parsing.

- [ ] **Step 5: Update the assessment skill boundary**

Add an external-evidence clause to `skills/assess-research-problem/SKILL.md`: version-2 quantum assessment may read only the host-frozen valuation snapshot named in its input; it must not browse during scoring, must not relabel snapshot evidence as trusted knowledge, and must not alter the snapshot.

Extend `tests/agent/skill-contracts.test.ts` to assert the three boundary phrases.

- [ ] **Step 6: Run adapter and skill tests**

Run: `node --test tests/valuation-codex-adapter.test.mjs && node --import tsx --test tests/agent/skill-contracts.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit the research adapter**

```bash
git add schemas/quantum-valuation-research.schema.json lib/valuations/codex-research-adapter.mjs tests/valuation-codex-adapter.test.mjs skills/assess-research-problem/SKILL.md tests/agent/skill-contracts.test.ts
git commit -m "feat: research valuation evidence with read-only Codex"
```

### Task 6: Valuation Research Jobs, Confirmation, and Local Routes

**Files:**
- Create: `lib/valuations/job-manager.mjs`
- Create: `tests/valuation-job-manager.test.mjs`
- Modify: `lib/assessments/local-service.mjs`
- Modify: `scripts/local-assessment-service.mjs`
- Modify: `tests/assessment-local-service.test.mjs`

**Interfaces:**
- Consumes: Tasks 1-5 interfaces.
- Produces: `createValuationJobManager({ rootDir, repository, researcher, openAlex, store, now })` with `start(problemId, { scopeOverride } = {})`, `confirm(runId, confirmation)`, `getJob(runId)`, `getProblemState(problemId)`, and `shutdown()`.
- Produces local routes:
  - `GET /__local/assessments/problems/:problemId/valuation`
  - `POST /__local/assessments/problems/:problemId/valuation/jobs`
  - `POST /__local/assessments/valuation/jobs/:runId/confirmation`

- [ ] **Step 1: Write failing job-state tests**

Test `no_evidence -> researching -> needs_confirmation -> ready`, exact candidate confirmation, rejected altered IDs, provider partial failure, unsupported domain, ambiguous legacy scope, a valid legacy scope override that appears only in the snapshot, duplicate active jobs, shutdown, and old-snapshot preservation.

```js
test("freezes only the exact confirmed candidate", async () => {
  const manager = fixtureManager();
  const started = await manager.start("Prob-007");
  await waitFor(() => manager.getJob(started.runId).status === "needs_confirmation");
  const candidate = manager.getJob(started.runId).candidate;
  const result = await manager.confirm(started.runId, {
    candidateHash: candidate.contentHash,
    acceptedAnchorIds: candidate.anchorCandidates.map((item) => item.id),
    assumptionDecisions: candidate.materialAssumptions.map((item) => ({ id: item.id, decision: "accept" })),
  });
  assert.equal(result.accepted, true);
  await waitFor(() => manager.getJob(started.runId).status === "ready");
});
```

- [ ] **Step 2: Run job-manager tests and verify failure**

Run: `node --test tests/valuation-job-manager.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement the queued two-phase manager**

Research jobs stage under `.generated/valuation-runs/<runId>/`. `start` first calls `classifyQuantumScope`; supported problems run the research adapter, then expose only a public/redacted candidate with a candidate content hash. A legacy problem with no explicit scope returns `needs_input` plus the six supported areas; resubmitting start with one exact `scopeOverride` records the choice only in the candidate and frozen snapshot and never mutates `problem.json`. `confirm` accepts only IDs and decisions present in that exact candidate, hydrates the confirmed anchors through OpenAlex, computes citation/feasibility/value outputs, freezes the snapshot, and records the ready snapshot identity. Only assumptions with `confirmationRequired: true` need a decision; lower-sensitivity, strong-evidence assumptions are accepted automatically and remain visible in the audit. Edited public values must pass the atomic evidence contract; private edits must be written only to `inputs.private.json`.

If OpenAlex fails, freeze an incomplete snapshot with scientific attention unknown and the provider error recorded. If Codex research fails entirely, end in `research_failed` and keep the last ready snapshot.

- [ ] **Step 4: Write failing local-route tests**

Extend the local-service fixture manager and assert token enforcement, JSON content type, same-origin mutation checks, problem/run ID validation, exact `scopeOverride` validation, 202 responses for start/confirmation, and GET state shape:

```js
const started = await request(server, "/__local/assessments/problems/Prob-007/valuation/jobs", {
  method: "POST",
  headers: { ...tokenHeaders, "content-type": "application/json" },
  body: "{}",
});
assert.equal(started.status, 202);
```

- [ ] **Step 5: Add the local-only routes and service wiring**

Extend `createAssessmentService` to accept `valuationManager`. Reuse the existing capability token, origin check, 16 KiB request ceiling, ID regexes, and error response shape. In `startAssessmentService`, create one valuation manager with the local repository, valuation Codex adapter, OpenAlex client, and snapshot store; close it during service shutdown.

- [ ] **Step 6: Run manager and service tests**

Run: `node --test tests/valuation-job-manager.test.mjs tests/assessment-local-service.test.mjs`

Expected: PASS.

- [ ] **Step 7: Commit the local valuation workflow**

```bash
git add lib/valuations/job-manager.mjs tests/valuation-job-manager.test.mjs lib/assessments/local-service.mjs scripts/local-assessment-service.mjs tests/assessment-local-service.test.mjs
git commit -m "feat: add local valuation research workflow"
```

### Task 7: Assessment Schema and Policy Version 2

**Files:**
- Modify: `schemas/research-problem-assessment.schema.json`
- Modify: `lib/assessments/policy.mjs`
- Modify: `lib/assessments/contract.mjs`
- Modify: `tests/assessment-policy.test.mjs`
- Modify: `tests/assessment-contract.test.mjs`
- Modify: `tests/assessment-codex-adapter.test.mjs`

**Interfaces:**
- Consumes: `validateQuantitativeEvidence` from Task 2 and a frozen snapshot identity from Task 3.
- Produces: assessment schema versions 1 and 2; `validateScoreAnchors(assessment)`; extended `summarizeCompletedAssessment` with headline quantitative metrics.

- [ ] **Step 1: Write failing v1/v2 compatibility tests**

Keep the existing valid v1 fixture unchanged. Add a valid v2 fixture with `quantitativeEvidence`, then reject missing snapshot hash, unknown-as-zero, private output without private assessment visibility, an out-of-anchor dimension without an override, raw citation addition to aggregate score, citation or momentum evidence on novelty, coverage used as a score bonus, momentum moving Importance by more than 0.25 points, and any changed A dimension or weight.

```js
test("accepts v1 unchanged and a snapshot-bound v2 quantum assessment", () => {
  assert.equal(validateAssessmentEnvelope(validEnvelope()).ok, true);
  const result = validateAssessmentEnvelope(validQuantumEnvelopeV2());
  assert.equal(result.ok, true);
  assert.equal(result.value.assessment.quantitativeEvidence.snapshot.contentHash.length, 64);
  assert.deepEqual(result.computed.scores.combined, { min: 80, estimate: 80, max: 80 });
});
```

- [ ] **Step 2: Run policy and contract tests and confirm v2 fails**

Run: `node --test tests/assessment-policy.test.mjs tests/assessment-contract.test.mjs`

Expected: FAIL because schemaVersion 2 and `quantitativeEvidence` are unsupported.

- [ ] **Step 3: Add a strict JSON Schema v1/v2 union**

Keep the envelope shape and v1 `$defs` behavior. Define assessment as `oneOf` v1 and v2. V2 retains all v1 fields and requires:

```json
"quantitativeEvidence": {
  "domain": "quantum-computing",
  "quantumArea": "algorithms-and-applications",
  "snapshot": {
    "snapshotId": "20260729T010203Z-0123456789ab",
    "contentHash": "64 lowercase hex characters",
    "createdAt": "ISO timestamp",
    "freshness": "fresh"
  },
  "scientificAttention": {},
  "technicalFeasibility": {},
  "socialValue": {},
  "capturableValue": {},
  "informationValue": {},
  "scoreAnchors": {},
  "sensitivity": {},
  "assumptions": [],
  "warnings": []
}
```

Every `enum` and `const` must include an explicit JSON type, and no array schema may use `uniqueItems`, preserving the current Codex compatibility fix.

- [ ] **Step 4: Implement host v2 validation and anchor consistency**

Set `ASSESSMENT_POLICY_VERSION = 2` while preserving every dimension/weight and verdict function. A score anchor has `{ dimensionId, recommended: { min, estimate, max }, evidenceIds, override }`; `override` is null inside the recommended interval and `{ reason }` outside it. Validate that scientific attention anchors only Importance; momentum may move the Importance recommendation by at most 0.25 points and never supports novelty; coverage changes quantitative confidence only; concentration produces a warning only; quantitative metrics are not included in aggregate arithmetic; and private quantitative evidence marks the assessment summary private.

- [ ] **Step 5: Extend summary output**

For v2, add:

```js
quantitative: {
  scientificAttention,
  technicalSuccess,
  socialValue,
  capturableValue,
  largestSensitivity,
  snapshotId,
  freshness,
}
```

V1 summaries omit `quantitative` so historical JSON comparisons remain stable.

- [ ] **Step 6: Run assessment schema, policy, and adapter tests**

Run: `node --test tests/assessment-policy.test.mjs tests/assessment-contract.test.mjs tests/assessment-codex-adapter.test.mjs`

Expected: PASS.

- [ ] **Step 7: Commit assessment v2**

```bash
git add schemas/research-problem-assessment.schema.json lib/assessments/policy.mjs lib/assessments/contract.mjs tests/assessment-policy.test.mjs tests/assessment-contract.test.mjs tests/assessment-codex-adapter.test.mjs
git commit -m "feat: anchor quantum assessment schema v2"
```

### Task 8: Bind Frozen Valuation Evidence to Assessment Runs

**Files:**
- Modify: `lib/assessments/input-snapshot.mjs`
- Modify: `lib/assessments/staleness.mjs`
- Modify: `lib/assessments/codex-adapter.mjs`
- Modify: `lib/assessments/job-manager.mjs`
- Modify: `tests/assessment-staleness.test.mjs`
- Modify: `tests/assessment-codex-adapter.test.mjs`
- Modify: `tests/assessment-job-manager.test.mjs`

**Interfaces:**
- Consumes: `valuationStore.read/verify`, `classifyQuantumScope`, and assessment v2 contract.
- Produces: `buildInputSnapshot({ ..., valuationSnapshot })` containing immutable valuation identity and full recalculation inputs; assessment start returns `VALUATION_REQUIRED`, `VALUATION_NEEDS_CONFIRMATION`, or `VALUATION_TAMPERED` when appropriate.

- [ ] **Step 1: Write failing snapshot-binding tests**

Assert that non-quantum/legacy v1 input is byte-shape compatible, quantum v2 input contains `snapshotId`, `contentHash`, and a snapshot hash, a mismatched hash blocks start, stale evidence permits start with an advisory warning, and a newer valuation snapshot does not mutate or invalidate an old run.

```js
test("binds the exact frozen valuation snapshot into quantum assessment input", async () => {
  const input = await buildInputSnapshot({
    ...fixtureInputArgs(),
    valuationSnapshot: {
      manifest: { snapshotId: "20260729T010203Z-0123456789ab", contentHash: "a".repeat(64) },
      recalculationInputs: { technicalStages: [] },
    },
  });
  assert.equal(input.valuation.snapshotId, "20260729T010203Z-0123456789ab");
  assert.equal(input.valuation.contentHash, "a".repeat(64));
});
```

- [ ] **Step 2: Run affected assessment tests and verify failure**

Run: `node --test tests/assessment-staleness.test.mjs tests/assessment-job-manager.test.mjs tests/assessment-codex-adapter.test.mjs`

Expected: FAIL because valuation input is not wired.

- [ ] **Step 3: Extend input and staleness without changing old semantics**

Only add `input.valuation` for version-2 quantum runs. Include the verified snapshot identity, evidence-class freshness result, and deterministic formula inputs. Existing `problemJsonHash`, `problemMdHash`, skill/schema hashes, resolver claim, and bundle hashes remain unchanged. Assessment staleness adds `newer valuation snapshot available` as an advisory reason but does not call the old assessment invalid or recompute it.

- [ ] **Step 4: Pass a frozen packet to Codex scoring**

Extend the prompt with:

```text
The host has frozen external valuation evidence in the attached input packet.
Use it only to propose score anchors and rationales. Do not browse, refresh,
rewrite, or relabel it as trusted knowledge. Keep A unchanged and do not add raw
quantitative metrics to V, A, or S arithmetic.
```

The adapter still runs `--sandbox read-only` and the same output-schema boundary.

- [ ] **Step 5: Gate quantum assessment start on snapshot readiness**

In `job-manager.start`, classify scope. For `supported`, load the selected/latest ready snapshot, verify its digest, and build v2 input. If no snapshot exists, return `{ accepted: false, code: "VALUATION_REQUIRED" }`; if confirmation is pending, return `VALUATION_NEEDS_CONFIRMATION`; if verification fails, return `VALUATION_TAMPERED`. Non-quantum and legacy problems retain v1 start behavior.

- [ ] **Step 6: Run assessment integration tests**

Run: `node --test tests/assessment-staleness.test.mjs tests/assessment-job-manager.test.mjs tests/assessment-codex-adapter.test.mjs`

Expected: PASS.

- [ ] **Step 7: Commit snapshot-bound assessment execution**

```bash
git add lib/assessments/input-snapshot.mjs lib/assessments/staleness.mjs lib/assessments/codex-adapter.mjs lib/assessments/job-manager.mjs tests/assessment-staleness.test.mjs tests/assessment-codex-adapter.test.mjs tests/assessment-job-manager.test.mjs
git commit -m "feat: bind valuation snapshots to assessments"
```

### Task 9: Progressive Panel and Detailed Audit Report

**Files:**
- Modify: `lib/assessments/view-model.mjs`
- Modify: `tests/assessment-view-model.test.mjs`
- Modify: `lib/assessments/html-report.mjs`
- Modify: `tests/assessment-report.test.mjs`
- Modify: `app/problems/[id]/assessment-panel.tsx`
- Create: `app/problems/[id]/assessment-panel.module.css`

**Interfaces:**
- Consumes: valuation API state and v2 summary from Tasks 6-8.
- Produces: `valuationStatusCopy`, `formatKnownInterval`, `formatMoneyInterval`, progressive panel actions, and a versioned audit report.

- [ ] **Step 1: Write failing view-model formatting/state tests**

Cover `no_evidence`, `researching`, `needs_confirmation`, `ready`, `stale`, `research_failed`, explicit unknown formatting, scientific attention, probability percentages, money with currency/base year, and private redaction:

```js
test("formats unknown and private quantitative values without fake zeroes", () => {
  assert.equal(formatKnownInterval({ state: "unknown", reason: "No comparable papers." }), "Unknown");
  assert.equal(formatMoneyInterval({ visibility: "private", redacted: true }), "Private");
});
```

- [ ] **Step 2: Run view-model tests and verify failure**

Run: `node --test tests/assessment-view-model.test.mjs`

Expected: FAIL because valuation formatting/state exports do not exist.

- [ ] **Step 3: Implement view-model copy and formatters**

Use these primary actions:

```js
{
  no_evidence: "Research evidence",
  researching: null,
  needs_confirmation: "Review assumptions",
  ready: "Run assessment",
  stale: "Refresh evidence",
  research_failed: "Retry research",
}
```

The assessment state and valuation state remain separate fields so an old completed assessment can be shown while newer evidence is stale or being researched.

- [ ] **Step 4: Write failing report audit/redaction tests**

Assert v1 HTML remains unchanged in required sections. For v2 assert summary cards, snapshot ID/hash, external-evidence banner, paper table, stage tree, classical baseline, atomic assumptions, low/base/high scenarios, score anchors/overrides, sensitivity, stale warnings, safe clickable `https`/DOI sources, no scripts, and no private numeric value.

- [ ] **Step 5: Implement a versioned report renderer**

Keep `renderAssessmentReport` as the public function. Dispatch to existing v1 markup or append v2 sections with `escapeHtml` on every text value and an `externalHref` helper that permits only `https:`. Keep the existing restrictive CSP and scripts disabled; ordinary sanitized anchor navigation does not require weakening `default-src`. Pass all quantitative content through `redactPrivate` before rendering.

- [ ] **Step 6: Implement progressive panel controls**

Import `styles` from `assessment-panel.module.css`. Add functions that call the three Task 6 endpoints, poll research jobs, present the six-area scope chooser only for ambiguous legacy problems, present exact anchor/assumption candidates, submit the candidate hash plus decisions, and then enable the existing assessment action. Keep the existing V/A/S grid and append cards for scientific attention, technical success, industry/social value, capturable value, and largest sensitivity when `latest.quantitative` exists.

Do not modify `app/globals.css`; use module classes for the new evidence-state strip, confirmation list, and expanded metric cards.

- [ ] **Step 7: Run view-model and report tests**

Run: `node --test tests/assessment-view-model.test.mjs tests/assessment-report.test.mjs`

Expected: PASS.

- [ ] **Step 8: Run lint for the React/CSS integration**

Run: `npm run lint`

Expected: PASS with no changes to the preserved dashboard files.

- [ ] **Step 9: Commit the report and panel**

```bash
git add lib/assessments/view-model.mjs tests/assessment-view-model.test.mjs lib/assessments/html-report.mjs tests/assessment-report.test.mjs app/problems/'[id]'/assessment-panel.tsx app/problems/'[id]'/assessment-panel.module.css
git commit -m "feat: show quantum valuation audit in assessment"
```

### Task 10: End-to-End Fixture, Documentation, and Full Verification

**Files:**
- Modify: `tests/e2e/local-assessment-fixture.ts`
- Modify: `tests/e2e/local-assessment.spec.ts`
- Modify: `docs/local-assessments.md`
- Modify: `package.json`

**Interfaces:**
- Consumes: the complete local valuation and assessment flow.
- Produces: one deterministic browser proof and documented operator workflow.

- [ ] **Step 1: Add a deterministic quantum valuation fixture**

Create a temporary quantum problem with:

```json
{
  "domain": "quantum-computing",
  "quantumArea": "resource-estimation-and-benchmarks"
}
```

Inject fake Codex research and OpenAlex adapters through the existing E2E dev-server seam. The candidate must contain two anchor papers, one public market input, one material assumption, a five-stage feasibility tree, known social value, and unknown capturable value. Teardown must restore or remove only fixture-owned paths, retaining the existing traversal guards.

- [ ] **Step 2: Write the failing browser scenario**

Add one Playwright test that performs:

```ts
await page.getByRole("button", { name: "Research evidence" }).click();
await expect(page.getByRole("heading", { name: "Review valuation assumptions" })).toBeVisible();
await page.getByLabel(/Anchor paper/).first().check();
await page.getByRole("button", { name: "Confirm and freeze snapshot" }).click();
await expect(page.getByText("Evidence ready")).toBeVisible();
await page.getByRole("button", { name: "Run assessment" }).click();
await expect(page.getByText("Scientific attention", { exact: true })).toBeVisible();
await expect(page.getByText("Industry / social", { exact: true })).toBeVisible();
```

Open the detailed report and assert the external-evidence banner, snapshot ID, formula audit, and absence of the private fixture sentinel.

- [ ] **Step 3: Run the E2E scenario and verify failure before fixture wiring is complete**

Run: `npm run test:e2e:assessment`

Expected: FAIL on the missing `Research evidence` action before the fixture/service injection is complete.

- [ ] **Step 4: Complete E2E dependency injection and make the browser proof pass**

Add optional `valuationResearcher` and `openAlex` parameters through `startAssessmentService` and the E2E dev server. Production defaults remain the real read-only Codex and OpenAlex clients; tests pass fakes and never use network or Codex quota.

- [ ] **Step 5: Register all new unit tests**

Append these exact files to `test:unit:problems` in `package.json`, and add `--public` to both `scripts.build` and the final post-E2E build invocation inherited through that script:

```text
tests/valuation-contract.test.mjs
tests/valuation-formulas.test.mjs
tests/valuation-snapshot.test.mjs
tests/valuation-privacy.test.mjs
tests/valuation-openalex.test.mjs
tests/valuation-citations.test.mjs
tests/valuation-codex-adapter.test.mjs
tests/valuation-job-manager.test.mjs
```

The resulting build command begins `node scripts/build-problem-index.mjs --public --reserve-id Prob-000`.

- [ ] **Step 6: Document operation and failure modes**

Extend `docs/local-assessments.md` with:

- `OPENALEX_API_KEY` setup and the `OPENALEX_KEY_REQUIRED` degraded state;
- explicit research, anchor/assumption confirmation, snapshot freeze, and assessment steps;
- the `problems/<id>/valuation/` and assessment artifact layouts;
- 90/180-day advisory freshness windows;
- public versus private input rules and redaction;
- incomplete snapshot behavior; and
- a manual smoke test confirming no problem lifecycle mutation and no autoresearch start.

- [ ] **Step 7: Run every focused valuation and assessment test**

Run:

```bash
node --test \
  tests/problem-schema.test.mjs \
  tests/valuation-contract.test.mjs \
  tests/valuation-formulas.test.mjs \
  tests/valuation-snapshot.test.mjs \
  tests/valuation-privacy.test.mjs \
  tests/valuation-openalex.test.mjs \
  tests/valuation-citations.test.mjs \
  tests/valuation-codex-adapter.test.mjs \
  tests/valuation-job-manager.test.mjs \
  tests/assessment-policy.test.mjs \
  tests/assessment-contract.test.mjs \
  tests/assessment-artifacts.test.mjs \
  tests/assessment-staleness.test.mjs \
  tests/assessment-report.test.mjs \
  tests/assessment-codex-adapter.test.mjs \
  tests/assessment-job-manager.test.mjs \
  tests/assessment-local-service.test.mjs \
  tests/assessment-view-model.test.mjs
```

Expected: PASS.

- [ ] **Step 8: Run browser verification**

Run: `npm run test:e2e:assessment`

Expected: PASS without real network access or Codex quota.

- [ ] **Step 9: Run the full repository gate**

Run: `make test`

Expected: lint, unit suites, knowledge validation/render, app build, rendered-output tests, Pages tests, all Playwright suites, and final build PASS. Confirm `git diff -- app/page.tsx app/globals.css app/layout.tsx .openai/hosting.json` is empty.

- [ ] **Step 10: Commit documentation and proof**

```bash
git add tests/e2e/local-assessment-fixture.ts tests/e2e/local-assessment.spec.ts docs/local-assessments.md package.json
git commit -m "test: prove quantum valuation assessment flow"
```

## Completion Criteria

- A supported quantum problem can research public evidence, review material assumptions, freeze an immutable snapshot, and run assessment v2 locally.
- The same snapshot reproduces citation, feasibility, ENPV, and information-value outputs through host arithmetic.
- V/A/S arithmetic and verdict behavior match version 1; quantitative evidence is never counted twice.
- Legacy and non-quantum problems retain the version-1 flow.
- Old assessments remain readable after new evidence is refreshed.
- Missing or weak evidence widens or removes an estimate without manufacturing zero.
- Private inputs never appear in public output.
- External research remains outside trusted knowledge and cannot start autoresearch.
- Focused tests, the browser scenario, `make test`, and the preserved-file diff gate all pass.
