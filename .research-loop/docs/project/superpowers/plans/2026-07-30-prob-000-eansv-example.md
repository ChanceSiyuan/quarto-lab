# Prob-000 EANSV Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Prob-000's broad industry proxy with one fixture-driven, reproducible Expected Attributable Net Social Value example displayed as `+$180K USD 2026`.

**Architecture:** A reusable pure calculator derives branch present values and EANSV from numeric inputs. A Prob-000-only loader validates and resolves provenance-bearing fixture records into that calculator model, and a presentation adapter supplies the existing static page with a calculated card. The methodology document records the formula, exact arithmetic, evidence boundary, and assumptions.

**Tech Stack:** JavaScript ESM, Node.js built-in test runner, JSON fixtures, Next.js/React TypeScript, existing static Pages showcase builder.

## Global Constraints

- Apply the metric only to the preserved static `Prob-000` showcase.
- Do not change production problem schemas, valuation snapshots, QEC portfolio data, trusted `knowledge/`, or generated `public/knowledge/`.
- Do not derive project value from a total-addressable-market percentage.
- Keep external evidence and synthetic assumptions explicitly distinguishable and traceable.
- Derive the final number from fixture inputs; do not hardcode `+$180K` or USD 181,422.5451662417 in JSX or the fixture.
- Use constant 2026 USD, a 3.5 percent social discount rate, and the approved three mutually exclusive outcome branches.
- Preserve negative EANSV values; never clamp them to zero.
- Remove `Industry / social proxy` and `$57.0B USD 2035` from the rendered Prob-000 page.
- Keep the dashboard layout and styling unchanged.
- Begin every production behavior with a test observed failing for the expected reason.

---

### Task 1: Pure EANSV calculator

**Files:**
- Modify: `.research-loop/tests/valuation-formulas.test.mjs`
- Modify: `src/lib/valuations/formulas.mjs`

**Interfaces:**
- Consumes: `{ socialDiscountRate, outcomes, withoutResearchCounterfactualPresentValue, researchCostPresentValue }`.
- Produces: `calculateExpectedAttributableNetSocialValue(model)` returning `{ outcomes, withResearchPresentValue, withoutResearchCounterfactualPresentValue, researchCostPresentValue, eansv }`.
- An annual outcome result adds `computeSavingPerRun`, `productiveTimeValuePerRun`, `perRunBenefit`, `annualBenefit`, `presentValue`, and `expectedPresentValue`.

- [ ] **Step 1: Add failing calculator tests with hand-derived literals**

Import `calculateExpectedAttributableNetSocialValue` and test this model:

```js
const approvedModel = {
  socialDiscountRate: 0.035,
  outcomes: [
    {
      id: "full-success",
      probability: 0.35,
      valueModel: {
        kind: "annual-per-run",
        teams: 30,
        runsPerTeamPerYear: 1000,
        years: [1, 2, 3, 4, 5],
        compute: { pricePerInstanceHour: 0.403216, instanceHoursAvoided: 0.5 },
        productiveTime: { hoursReleased: 0.5, loadedHourlyValue: 100, recaptureRate: 0.2 },
      },
    },
    {
      id: "partial-success",
      probability: 0.25,
      valueModel: {
        kind: "annual-per-run",
        teams: 10,
        runsPerTeamPerYear: 500,
        years: [1, 2, 3],
        compute: { pricePerInstanceHour: 0.403216, instanceHoursAvoided: 0.25 },
        productiveTime: { hoursReleased: 0.25, loadedHourlyValue: 100, recaptureRate: 0.2 },
      },
    },
    { id: "useful-negative-result", probability: 0.4, valueModel: { kind: "present-value", amount: 75000 } },
  ],
  withoutResearchCounterfactualPresentValue: 100000,
  researchCostPresentValue: 250000,
};

test("calculates the approved Prob-000 branch values and net EANSV", () => {
  const result = calculateExpectedAttributableNetSocialValue(approvedModel);
  assert.equal(result.outcomes[0].computeSavingPerRun, 0.2);
  assert.equal(result.outcomes[0].productiveTimeValuePerRun, 10);
  assert.equal(result.outcomes[0].perRunBenefit, 10.2);
  assert.equal(result.outcomes[0].annualBenefit, 306000);
  assert.ok(Math.abs(result.outcomes[0].presentValue - 1381606.026894049) < 1e-7);
  assert.ok(Math.abs(result.outcomes[1].presentValue - 71441.74301329814) < 1e-7);
  assert.ok(Math.abs(result.withResearchPresentValue - 531422.5451662417) < 1e-7);
  assert.ok(Math.abs(result.eansv - 181422.5451662417) < 1e-7);
});
```

Also test that a zero-benefit model with USD 10 counterfactual and USD 20 cost returns `-30`. Add table cases for out-of-range probabilities, probabilities not summing to one, rate `-1`, negative inputs, duplicate/non-positive years, duplicate outcome IDs, and an unsupported model kind.

- [ ] **Step 2: Verify RED**

Run `node --test .research-loop/tests/valuation-formulas.test.mjs`.

Expected: FAIL because the new function is not exported.

- [ ] **Step 3: Implement the minimal calculator**

Use this calculation order:

```js
computeSavingPerRun = roundToCents(pricePerInstanceHour * instanceHoursAvoided);
productiveTimeValuePerRun = roundToCents(hoursReleased * loadedHourlyValue * recaptureRate);
perRunBenefit = computeSavingPerRun + productiveTimeValuePerRun;
annualBenefit = teams * runsPerTeamPerYear * perRunBenefit;
presentValue = years.reduce((sum, year) => sum + annualBenefit / ((1 + rate) ** year), 0);
expectedPresentValue = probability * presentValue;
withResearchPresentValue = outcomes.reduce((sum, outcome) => sum + outcome.expectedPresentValue, 0);
eansv = withResearchPresentValue - counterfactualPresentValue - researchCostPresentValue;
```

`roundToCents` is `Math.round((value + Number.EPSILON) * 100) / 100`. Validate non-empty unique IDs, finite values, non-negative inputs, positive integer team/run counts, unique positive integer years, probabilities in `[0, 1]` summing to one within `1e-12`, a rate greater than `-1`, and exactly `annual-per-run` or `present-value` model kinds.

- [ ] **Step 4: Verify GREEN and commit**

Run the same test command, then:

```bash
git add .research-loop/tests/valuation-formulas.test.mjs src/lib/valuations/formulas.mjs
git commit -m "feat: calculate expected attributable social value"
```

### Task 2: Prob-000 fixture and presentation model

**Files:**
- Create: `.research-loop/fixtures/showcase/problems/Prob-000/valuation.json`
- Create: `src/lib/problems/example-valuation.mjs`
- Create: `src/lib/problems/example-valuation-presentation.mjs`
- Create: `.research-loop/tests/example-valuation.test.mjs`
- Modify: `package.json`

**Interfaces:**
- Produces: `validateStaticExampleValuationFixture(fixture)`, `getStaticExampleValuation(problemId)`, and `buildStaticExampleEansvCard(example)`.
- The loader returns a defensive clone of `{ metadata, model, evidence, assumptions }`; `model` contains the primitive Task 1 calculator input resolved from typed references.
- The card builder returns `{ label, value, formula, reason }`.

- [ ] **Step 1: Add and register failing fixture tests**

Create the new test file and add it after `example-research.test.mjs` in `test:unit:problems`. Its primary expectations are:

```js
const example = getStaticExampleValuation("Prob-000");
assert.equal(example.metadata.currency, "USD");
assert.equal(example.metadata.constantDollarYear, 2026);
assert.deepEqual(example.model.outcomes.map(({ id, probability }) => ({ id, probability })), [
  { id: "full-success", probability: 0.35 },
  { id: "partial-success", probability: 0.25 },
  { id: "useful-negative-result", probability: 0.4 },
]);
assert.equal(getStaticExampleValuation("Prob-999"), null);

const card = buildStaticExampleEansvCard(example);
assert.equal(card.label, "Expected Attributable Net Social Value");
assert.equal(card.value, "+$180K USD 2026");
assert.match(card.formula.join("\n"), /181,422\.55/);
assert.match(card.reason, /scenario assumptions/i);
```

Add mutation cases for wrong schema/problem/metric IDs, duplicate evidence or assumption IDs, missing/mistyped references, malformed source URL/date, and forbidden stored `eansv` or `headline` keys.

- [ ] **Step 2: Verify RED**

Run `node --test .research-loop/tests/example-valuation.test.mjs`.

Expected: FAIL because `example-valuation.mjs` does not exist.

- [ ] **Step 3: Add the provenance-bearing fixture**

Use metric ID `prob-000-eansv-v1`. The model references uniquely identified assumption/evidence records and contains no final result or display string. Evidence records cover QDistRnd DOI `10.21105/joss.04120`, arXiv `2603.22532`, qLDPC integration, and the externally anchored USD 0.403216 Google Cloud c3-standard-8 price accessed 2026-07-30. Assumptions contain all approved rates, probabilities, adoption/run counts, benefit years, avoided compute time, researcher-time parameters, USD 75,000 negative-result value, USD 100,000 counterfactual, and USD 250,000 research cost. Every assumption includes `id`, `label`, `value`, `unit`, and `rationale`.

- [ ] **Step 4: Implement loader, validator, and presentation**

Validate the fixture at import, reject unknown answer-like top-level keys, resolve typed references, and return defensive clones. Prefix errors with `Static example valuation` and name the field. The card builder calls the calculator and formats:

```js
const roundedThousands = Math.round(result.eansv / 10000) * 10;
const sign = roundedThousands >= 0 ? "+" : "-";
const value = `${sign}$${Math.abs(roundedThousands)}K ${metadata.currency} ${metadata.constantDollarYear}`;
```

Build the formula from calculated two-decimal intermediate values. State that the result uses scenario assumptions and list the external price anchor separately from adoption, productivity, probability, counterfactual, and cost assumptions.

- [ ] **Step 5: Verify GREEN and commit**

Run:

```bash
node --test .research-loop/tests/valuation-formulas.test.mjs .research-loop/tests/example-valuation.test.mjs
git add package.json .research-loop/fixtures/showcase/problems/Prob-000/valuation.json .research-loop/tests/example-valuation.test.mjs src/lib/problems/example-valuation.mjs src/lib/problems/example-valuation-presentation.mjs
git commit -m "feat: add auditable Prob-000 valuation fixture"
```

### Task 3: Static card and methodology integration

**Files:**
- Modify: `src/app/problems/[id]/page.tsx`
- Modify: `src/app/problems/[id]/static-assessment-panel.tsx`
- Modify: `.research-loop/tests/pages-showcase.test.mjs`
- Modify: `.research-loop/tests/rendered-html.test.mjs`
- Modify: `.research-loop/docs/project/assessment-methodology.md`

**Interfaces:**
- `StaticAssessmentPanel` consumes an `eansvCard` with `{ label: string, value: string, formula: string[], reason: string }`.
- The rendered second card is `Expected Attributable Net Social Value` and `+$180K USD 2026`.

- [ ] **Step 1: Change static-output expectations and verify RED**

In both output tests, require the new label/value and forbid the old strings:

```js
assert.match(html, /Expected Attributable Net Social Value/);
assert.match(html, /\+\$180K USD 2026/);
assert.doesNotMatch(html, /Industry \/ social proxy/);
assert.doesNotMatch(html, /\$57\.0B USD 2035/);
```

Use the local variable already present in each test. Run `npm run test:pages` and confirm failure because the old card still renders. If the builder is blocked before the assertion, record that environment blocker and use the existing rendered artifact test to observe the expected failure.

- [ ] **Step 2: Wire the calculated view model into the page**

In the Prob-000 route branch, load the example valuation, return `notFound()` if missing, build the card, and render:

```tsx
<StaticAssessmentPanel eansvCard={eansvCard} />
```

In the panel, type the prop and render `[SCIENTIFIC_DEMAND_CARD, eansvCard, AUTORESEARCH_FIT_CARD]`. Keep the first/third cards and CSS unchanged. Put no monetary inputs or result strings in JSX.

- [ ] **Step 3: Expand assessment methodology documentation**

Add an `Expected Attributable Net Social Value example` section containing:

```text
EANSV = sum_y(probability_y * branch_present_value_y)
        - without_research_counterfactual_PV
        - research_cost_PV
```

Explain that EANSV is a product label for a synthesis, not a formula named by one source. Reproduce USD 531,422.5451662417 with-research value, USD 100,000 counterfactual, USD 250,000 cost, USD 181,422.5451662417 result, and `+$180K USD 2026` rounding. Include direct method/technical references and a parameter table classifying each input as external evidence or scenario assumption. State that the old USD 43-71B forecast is contextual and not allocated to Prob-000.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
node --test .research-loop/tests/valuation-formulas.test.mjs .research-loop/tests/example-valuation.test.mjs
npm run test:pages
git add 'src/app/problems/[id]/page.tsx' 'src/app/problems/[id]/static-assessment-panel.tsx' .research-loop/tests/pages-showcase.test.mjs .research-loop/tests/rendered-html.test.mjs .research-loop/docs/project/assessment-methodology.md
git commit -m "feat: show Prob-000 attributable social value"
```

### Task 4: Verification and Draft PR

**Files:**
- Modify only if verification exposes a defect in files already named above.

**Interfaces:**
- Produces a verified, pushed feature branch and Draft PR, with baseline environment failures separated from regressions.

- [ ] **Step 1: Run focused verification**

Run `npm run lint`, `npm run test:unit:problems`, and `npm run test:pages`.

Expected: PASS with the new example test included in the explicit unit-test list.

- [ ] **Step 2: Run build and rendered verification**

Run `npm run build` and `npm run test:rendered`.

Expected: PASS when Quarto is available. If `spawn quarto ENOENT` recurs, record it as a pre-existing environment blocker and verify every app/Pages path that does not require Quarto.

- [ ] **Step 3: Run full suite and inspect branch state**

Run:

```bash
npm test
git diff --check origin/main...HEAD
git status --short
git diff --stat origin/main...HEAD
```

Expected: no new failures, whitespace errors, or uncommitted files. Report the known baseline Quarto absence and temporary-directory cleanup flake verbatim if either recurs.

- [ ] **Step 4: Push and create a Draft PR**

Push `codex/prob-000-eansv-example`, then create a Draft PR titled `Show problem-specific value for Prob-000`. The body summarizes the calculator, provenance boundary, fixture, static card, documentation, exact verification commands/results, and any environment-only verification gaps.
