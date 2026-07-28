# Local Assessment Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only problem-page assessment workflow that runs Codex CLI in the background, stores immutable structured results, and renders a concise page summary plus a standalone HTML report.

**Architecture:** `make dev` starts a Node loopback assessment service beside the existing problem-index watcher and `vinext dev`. The browser talks only to `/__local/assessments/*`; Vite injects a per-process capability token and proxies to the loopback service. The service runs one read-only `codex exec` job at a time, validates the schema output, writes immutable artifacts under `problems/<id>/assessments/<run-id>/`, and serves summaries and reports from those artifacts.

**Tech Stack:** Node >=22.13.0 ESM, native `node:test`, Next 16.2.6 App Router, React 19.2.6 client components, Vite dev proxy, Codex CLI `codex exec`, no new npm dependencies.

## Global Constraints

- The application is a local single-user workspace. There is no remote queue, multi-user authorization system, or cloud execution service.
- The feature invokes the user's installed and authenticated Codex CLI. It does not use a separate API key.
- The fixed Codex invocation uses `codex exec`, `--sandbox read-only`, `--ephemeral`, `--json`, `--output-schema`, and `--output-last-message`.
- The Codex job has a 30-minute execution limit; queue wait does not count.
- The Codex job is read-only and must not modify `problems/`, `knowledge/`, `drafts/`, or `literature/`.
- The host service alone writes assessment artifacts after validating output.
- A verdict is advisory. It never updates the problem lifecycle or writes a rejection block.
- The first version has no manual cancellation, live command stream, automatic retries, or multi-job parallelism.
- Only one Codex job runs globally at a time. Other jobs wait in FIFO order.
- A duplicate start for a problem that is already queued, running, or awaiting a selection returns the existing active run.
- Assessment reports use a deterministic HTML template and do not require Quarto.
- Static Pages output shows the local assessment control as unavailable and does not publish local assessment artifacts.
- Human-readable report content follows the primary language of `problem.md`; keys, IDs, and verdict enums remain English.
- `outcome` is `assessment` or `needs_input`.
- Verdict labels are `DO_NOW`, `REFRAME`, `NOT_AUTORESEARCH`, and `DEFER`.
- Autoresearch recommendations are `proceed`, `reframe`, `reject`, and `defer`.
- Evidence states are `supported`, `inferred`, and `unknown`.
- Problem IDs match `Prob-###`.
- Run IDs use sortable UTC timestamp plus random suffix: `YYYYMMDDTHHMMSSZ-abcdef`.
- Active work lives under `.generated/assessment-runs/{run-id}/`.
- Completed artifacts live under `problems/{id}/assessments/{run-id}/`.
- Completed, failed, interrupted, and needs-input runs are immutable.
- The service never stages or commits assessment artifacts.
- Treat `knowledge/**/*.qmd` as the only trusted research authority.
- Ambiguous resolver results require explicit user selection; the service never chooses silently.
- Never fall back to `drafts/` or treat `literature/` as learned knowledge.
- Escape report content and serve no model-authored HTML.
- Raw events and diagnostics stay local and are never exposed through a deployed route.

---

## Scope Check

The approved design covers one connected local subsystem: assessment contract, local runner, artifacts, report renderer, API, and problem-page presentation. A single plan is appropriate because every task builds a piece consumed by the next task, and the completed feature is not useful until the contract, service, and panel all agree. The implementation must begin from a branch that contains the `assess-research-problem` skill from PR #3, then keep this assessment feature in its own focused branch.

## File Structure

- Modify `skills/assess-research-problem/SKILL.md`: preserve conversational Markdown output and add structured-output behavior when Codex is invoked with the assessment schema.
- Modify `tests/agent/skill-contracts.test.ts`: add static clauses for the new assessment skill, especially read-only behavior, resolver ambiguity, no fallback, and schema mode.
- Create `schemas/research-problem-assessment.schema.json`: strict JSON Schema passed to `codex exec --output-schema`.
- Create `lib/assessments/policy.mjs`: policy version, dimension IDs, weights, runtime scoring, weighted totals, harmonic score, banding, and verdict consistency rules.
- Create `lib/assessments/contract.mjs`: host-side validation of the strict envelope, cross-field constraints, dimension references, evidence references, and computed score comparison.
- Create `lib/assessments/paths.mjs`: problem ID and run ID validation, canonical containment checks, and stable artifact paths.
- Create `lib/assessments/artifact-store.mjs`: staging directory creation, event/log writes, atomic publication, immutable run listing, and summary projection.
- Create `lib/assessments/input-snapshot.mjs`: problem, skill, schema, resolver, and bundle hashing for accepted runs.
- Create `lib/assessments/staleness.mjs`: compare stored input snapshots against current files and resolver output.
- Create `lib/assessments/html-report.mjs`: deterministic standalone report renderer with escaping and restrictive CSP.
- Create `lib/assessments/codex-adapter.mjs`: preflight checks and `codex exec` runner with fakeable process APIs.
- Create `lib/assessments/job-manager.mjs`: FIFO queue, global concurrency one, duplicate suppression, state transitions, selection child runs, timeout, and shutdown recovery.
- Create `lib/assessments/local-service.mjs`: token-protected loopback HTTP API.
- Create `scripts/local-assessment-service.mjs`: standalone entrypoint for manual service debugging.
- Modify `scripts/dev-problem-index.mjs`: start the assessment service before `vinext dev`, pass proxy env vars, and terminate the active child on shutdown.
- Modify `vite.config.ts`: add a conditional dev proxy for `/__local/assessments/*` that injects the capability token.
- Create `lib/assessments/view-model.mjs`: pure UI formatting for verdicts, score intervals, stale labels, and button states.
- Create `app/problems/[id]/assessment-panel.tsx`: client component for local service fetches, polling, run/rerun, clarification selection, links, and unavailable state.
- Modify `app/problems/[id]/page.tsx`: place the qualification panel after the problem header and before attempts or the ordinary detail panel.
- Modify `app/globals.css`: add detail-page assessment panel styles consistent with the existing console surface.
- Create `tests/assessment-policy.test.mjs`, `tests/assessment-contract.test.mjs`, `tests/assessment-artifacts.test.mjs`, `tests/assessment-staleness.test.mjs`, `tests/assessment-report.test.mjs`, `tests/assessment-codex-adapter.test.mjs`, `tests/assessment-job-manager.test.mjs`, `tests/assessment-local-service.test.mjs`, and `tests/assessment-view-model.test.mjs`.
- Create `playwright.assessment.config.ts`: local-dev browser test config using a fake Codex executable.
- Create `tests/e2e/local-assessment.spec.ts`: browser test for run, poll, report link, and resolver selection.
- Modify `package.json`: include assessment unit tests in `test:unit:problems` and add `test:e2e:assessment`.
- Create `docs/local-assessments.md`: operator notes, artifact layout, manual smoke test, and static showcase limitation.

---

### Task 1: Merge Skill Dependency and Pin Skill Contract

**Files:**
- Modify: `skills/assess-research-problem/SKILL.md`
- Modify: `tests/agent/skill-contracts.test.ts`

**Interfaces:**
- Consumes: PR #3 branch `origin/codex/knowledge-style-unify` containing `skills/assess-research-problem/SKILL.md`.
- Produces: a local `assess-research-problem` skill that keeps Markdown mode and adds schema mode.
- Produces: `tests/agent/skill-contracts.test.ts` coverage for the new skill.

- [ ] **Step 1: Bring the skill into the implementation branch**

Run from a clean implementation worktree:

```bash
git fetch origin codex/knowledge-style-unify
git merge --no-ff origin/codex/knowledge-style-unify
```

Expected: the branch now contains `skills/assess-research-problem/SKILL.md`. If Git reports conflicts, resolve only files touched by the skill PR and this feature, then run `git diff --check`.

- [ ] **Step 2: Write failing static skill-contract tests**

Modify `tests/agent/skill-contracts.test.ts` so `SKILL_NAMES` includes the new skill:

```ts
const SKILL_NAMES = [
  "download-ref",
  "read-knowledge",
  "review-draft",
  "assess-research-problem",
] as const;
```

Add this clause table near the existing skill clause tables:

```ts
const ASSESS_RESEARCH_PROBLEM: readonly Clause[] = [
  {
    requirement: "triggers when judging whether a research problem is worth doing",
    in: "description",
    pattern: /worth doing/i,
  },
  {
    requirement: "keeps the skill read-only",
    in: "body",
    pattern: /read-only/i,
  },
  {
    requirement: "runs the repository resolver before evidence-dependent claims",
    in: "body",
    pattern: /make knowledge-resolve QUERY="<the candidate research question>"/,
  },
  {
    requirement: "on ambiguous resolver output, returns needs_input in structured mode",
    in: "body",
    pattern: /`needs_input`[^.\n]*ambiguous/i,
  },
  {
    requirement: "on no-match, marks evidence-dependent dimensions unknown",
    in: "body",
    pattern: /no-match[^.\n]*unknown/i,
  },
  {
    requirement: "never uses drafts or literature as learned knowledge fallback",
    in: "body",
    pattern: /Never use `drafts\/`[^.\n]*Never use `literature\/`/i,
  },
  {
    requirement: "supports structured output when Codex receives the schema",
    in: "body",
    pattern: /structured output schema/i,
  },
  {
    requirement: "keeps Markdown sections for normal conversation mode",
    in: "body",
    pattern: /Markdown sections/i,
  },
  {
    requirement: "keeps P equals NP as a scoring outcome rather than a blacklist",
    in: "body",
    pattern: /P = NP[^.\n]*not[^.\n]*blacklist/i,
  },
  {
    requirement: "keeps the 5 minute runtime target soft",
    in: "body",
    pattern: /5 minutes[^.\n]*not a hard limit/i,
  },
];
```

Add it to the existing clause test map:

```ts
const SKILL_CLAUSES: Record<SkillName, readonly Clause[]> = {
  "read-knowledge": READ_KNOWLEDGE,
  "review-draft": REVIEW_DRAFT,
  "download-ref": DOWNLOAD_REF,
  "assess-research-problem": ASSESS_RESEARCH_PROBLEM,
};
```

- [ ] **Step 3: Run the test and confirm it fails for missing clauses**

Run:

```bash
npm run test:unit
```

Expected: fail in `tests/agent/skill-contracts.test.ts` until the skill body contains the structured-output clauses.

- [ ] **Step 4: Update the skill body**

Modify `skills/assess-research-problem/SKILL.md` by adding this section before `## Output`:

```md
## Structured output mode

When Codex is invoked with the repository's structured output schema, return
one JSON object matching that schema instead of Markdown sections. Use
`outcome: "assessment"` only after the resolver path has produced enough
information to score the problem. Use `outcome: "needs_input"` when the
resolver result is ambiguous and include every alternative exactly as reported.

The JSON keys, dimension IDs, evidence states, verdict labels, and
recommendation enums are English. Human-readable rationales should follow the
primary language of the candidate `problem.md`.

For `match`, include the resolver query, topic, and every ordered bundle path
that was read. For `no-match`, include the resolver query and mark
evidence-dependent dimensions as `unknown`. For `ambiguous`, do not score the
problem and do not choose among alternatives.

Keep Markdown sections for normal conversation mode when no structured output
schema is supplied.
```

Also adjust the trust-boundary paragraph so the consecutive sentence needed by the static test appears exactly:

```md
Never use `drafts/` as learned knowledge. Never use `literature/` as learned
knowledge.
```

- [ ] **Step 5: Run the skill contract tests**

Run:

```bash
npm run test:unit
```

Expected: pass for `tests/agent/skill-contracts.test.ts`.

- [ ] **Step 6: Commit the skill integration**

Run:

```bash
git add skills/assess-research-problem/SKILL.md tests/agent/skill-contracts.test.ts
git commit -m "feat: add structured assessment skill contract"
```

---

### Task 2: Assessment Policy and Codex Output Schema

**Files:**
- Create: `schemas/research-problem-assessment.schema.json`
- Create: `lib/assessments/policy.mjs`
- Test: `tests/assessment-policy.test.mjs`

**Interfaces:**
- Produces: `ASSESSMENT_POLICY_VERSION: 1`
- Produces: `RESEARCH_VALUE_DIMENSIONS: Array<{ id: string, label: string, weight: number }>`
- Produces: `AUTORESEARCH_DIMENSIONS: Array<{ id: string, label: string, weight: number }>`
- Produces: `runtimeScore(minutes: number): number`
- Produces: `weightedInterval(dimensions: Array<{ score: ScoreInterval, weight: number }>): ScoreInterval`
- Produces: `harmonicInterval(value: ScoreInterval, fit: ScoreInterval): ScoreInterval`
- Produces: `band(score: number): "strong" | "mixed" | "weak"`
- Produces: `deriveVerdict({ valueScore, fitScore, hasBoundedReframe }): "DO_NOW" | "REFRAME" | "NOT_AUTORESEARCH" | "DEFER"`
- Produces: `ASSESSMENT_SCHEMA_PATH_SEGMENTS: ["schemas", "research-problem-assessment.schema.json"]`

- [ ] **Step 1: Write failing policy tests**

Create `tests/assessment-policy.test.mjs`:

```js
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import {
  ASSESSMENT_POLICY_VERSION,
  AUTORESEARCH_DIMENSIONS,
  RESEARCH_VALUE_DIMENSIONS,
  band,
  deriveVerdict,
  harmonicInterval,
  runtimeScore,
  weightedInterval,
} from "../lib/assessments/policy.mjs";

test("assessment policy exposes stable version one and dimension weights", () => {
  assert.equal(ASSESSMENT_POLICY_VERSION, 1);
  assert.deepEqual(RESEARCH_VALUE_DIMENSIONS.map((item) => item.id), [
    "importance",
    "gap_and_novelty",
    "plausibility",
    "learning_from_failure",
    "generality_and_publication",
    "expected_value_relative_to_cost",
  ]);
  assert.deepEqual(AUTORESEARCH_DIMENSIONS.map((item) => item.id), [
    "modifiable_search_object",
    "executable_objective",
    "correctness_and_anti_gaming",
    "incremental_feedback",
    "fresh_evaluation",
    "reproducibility_and_auditability",
    "attempt_runtime",
  ]);
  assert.equal(RESEARCH_VALUE_DIMENSIONS.reduce((sum, item) => sum + item.weight, 0), 100);
  assert.equal(AUTORESEARCH_DIMENSIONS.reduce((sum, item) => sum + item.weight, 0), 100);
});

test("runtime target is soft with five minutes scoring five", () => {
  assert.equal(runtimeScore(5), 5);
  assert.equal(runtimeScore(10), 4);
  assert.equal(runtimeScore(20), 3);
  assert.equal(runtimeScore(160), 0);
  assert.equal(runtimeScore(1), 5);
});

test("weighted and harmonic intervals use host arithmetic", () => {
  const value = weightedInterval([
    { weight: 50, score: { min: 4, estimate: 5, max: 5 } },
    { weight: 50, score: { min: 2, estimate: 3, max: 4 } },
  ]);
  assert.deepEqual(value, { min: 60, estimate: 80, max: 90 });
  assert.deepEqual(harmonicInterval(value, { min: 50, estimate: 60, max: 70 }), {
    min: 54.55,
    estimate: 68.57,
    max: 78.75,
  });
});

test("banding and verdict rules match the design", () => {
  assert.equal(band(70), "strong");
  assert.equal(band(40), "mixed");
  assert.equal(band(39.99), "weak");
  assert.equal(deriveVerdict({ valueScore: 75, fitScore: 72, hasBoundedReframe: false }), "DO_NOW");
  assert.equal(deriveVerdict({ valueScore: 75, fitScore: 55, hasBoundedReframe: true }), "REFRAME");
  assert.equal(deriveVerdict({ valueScore: 75, fitScore: 35, hasBoundedReframe: false }), "NOT_AUTORESEARCH");
  assert.equal(deriveVerdict({ valueScore: 55, fitScore: 80, hasBoundedReframe: true }), "DEFER");
});

test("codex output schema is strict at the envelope boundary", async () => {
  const schema = JSON.parse(await readFile(join(process.cwd(), "schemas/research-problem-assessment.schema.json"), "utf8"));
  assert.equal(schema.type, "object");
  assert.equal(schema.additionalProperties, false);
  assert.deepEqual(schema.required, [
    "outcome",
    "language",
    "knowledgeResolution",
    "assessment",
    "clarification",
  ]);
});
```

- [ ] **Step 2: Run the policy test and confirm the missing-module failure**

Run:

```bash
node --test tests/assessment-policy.test.mjs
```

Expected: fail because `lib/assessments/policy.mjs` and the schema file do not exist.

- [ ] **Step 3: Implement the policy module**

Create `lib/assessments/policy.mjs` with these exported constants and helper shapes:

```js
export const ASSESSMENT_POLICY_VERSION = 1;

export const RESEARCH_VALUE_DIMENSIONS = Object.freeze([
  { id: "importance", label: "Importance", weight: 20 },
  { id: "gap_and_novelty", label: "Gap and novelty", weight: 20 },
  { id: "plausibility", label: "Plausibility", weight: 15 },
  { id: "learning_from_failure", label: "Learning from failure", weight: 15 },
  { id: "generality_and_publication", label: "Generality and publication potential", weight: 15 },
  { id: "expected_value_relative_to_cost", label: "Expected value relative to cost", weight: 15 },
]);

export const AUTORESEARCH_DIMENSIONS = Object.freeze([
  { id: "modifiable_search_object", label: "Modifiable search object", weight: 20 },
  { id: "executable_objective", label: "Executable objective", weight: 20 },
  { id: "correctness_and_anti_gaming", label: "Correctness and anti-gaming", weight: 15 },
  { id: "incremental_feedback", label: "Incremental feedback", weight: 15 },
  { id: "fresh_evaluation", label: "Fresh evaluation", weight: 10 },
  { id: "reproducibility_and_auditability", label: "Reproducibility and auditability", weight: 10 },
  { id: "attempt_runtime", label: "Attempt runtime", weight: 10 },
]);

export const VERDICT_LABELS = Object.freeze(["DO_NOW", "REFRAME", "NOT_AUTORESEARCH", "DEFER"]);
export const RECOMMENDATIONS = Object.freeze(["proceed", "reframe", "reject", "defer"]);
export const EVIDENCE_STATES = Object.freeze(["supported", "inferred", "unknown"]);
export const CONFIDENCE_LEVELS = Object.freeze(["high", "medium", "low"]);
export const ASSESSMENT_SCHEMA_PATH_SEGMENTS = Object.freeze(["schemas", "research-problem-assessment.schema.json"]);
```

Implement arithmetic with two-decimal rounding:

```js
function round2(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function runtimeScore(minutes) {
  const numeric = Number(minutes);
  if (!Number.isFinite(numeric) || numeric <= 0) return 0;
  return Math.max(0, Math.min(5, round2(5 - Math.log2(Math.max(numeric, 5) / 5))));
}

export function weightedInterval(dimensions) {
  const totalWeight = dimensions.reduce((sum, item) => sum + item.weight, 0);
  const score = (key) => round2(dimensions.reduce((sum, item) => sum + item.score[key] * item.weight, 0) / totalWeight / 5 * 100);
  return { min: score("min"), estimate: score("estimate"), max: score("max") };
}

function harmonic(left, right) {
  return left + right === 0 ? 0 : round2((2 * left * right) / (left + right));
}

export function harmonicInterval(value, fit) {
  return {
    min: harmonic(value.min, fit.min),
    estimate: harmonic(value.estimate, fit.estimate),
    max: harmonic(value.max, fit.max),
  };
}

export function band(score) {
  if (score >= 70) return "strong";
  if (score >= 40) return "mixed";
  return "weak";
}

export function deriveVerdict({ valueScore, fitScore, hasBoundedReframe }) {
  const valueBand = band(valueScore);
  const fitBand = band(fitScore);
  if (valueBand === "strong" && fitBand === "strong") return "DO_NOW";
  if (valueBand === "strong" && fitBand !== "strong" && hasBoundedReframe) return "REFRAME";
  if (valueBand === "strong" && fitBand === "weak" && !hasBoundedReframe) return "NOT_AUTORESEARCH";
  return "DEFER";
}
```

- [ ] **Step 4: Add the strict JSON Schema**

Create `schemas/research-problem-assessment.schema.json` with this envelope boundary:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://research-loop.local/schemas/research-problem-assessment.schema.json",
  "title": "Research Loop Research Problem Assessment Output",
  "type": "object",
  "additionalProperties": false,
  "required": ["outcome", "language", "knowledgeResolution", "assessment", "clarification"],
  "properties": {
    "outcome": { "enum": ["assessment", "needs_input"] },
    "language": { "type": "string", "minLength": 2 },
    "knowledgeResolution": { "$ref": "#/$defs/knowledgeResolution" },
    "assessment": {
      "anyOf": [{ "$ref": "#/$defs/assessment" }, { "type": "null" }]
    },
    "clarification": {
      "anyOf": [{ "$ref": "#/$defs/clarification" }, { "type": "null" }]
    }
  },
  "$defs": {
    "scoreInterval": {
      "type": "object",
      "additionalProperties": false,
      "required": ["min", "estimate", "max"],
      "properties": {
        "min": { "type": "number", "minimum": 0, "maximum": 100 },
        "estimate": { "type": "number", "minimum": 0, "maximum": 100 },
        "max": { "type": "number", "minimum": 0, "maximum": 100 }
      }
    },
    "dimensionScoreInterval": {
      "type": "object",
      "additionalProperties": false,
      "required": ["min", "estimate", "max"],
      "properties": {
        "min": { "type": "number", "minimum": 0, "maximum": 5 },
        "estimate": { "type": "number", "minimum": 0, "maximum": 5 },
        "max": { "type": "number", "minimum": 0, "maximum": 5 }
      }
    },
    "knowledgeResolution": {
      "type": "object",
      "additionalProperties": false,
      "required": ["query", "status", "topic", "orderedFiles"],
      "properties": {
        "query": { "type": "string", "minLength": 1 },
        "status": { "enum": ["match", "no-match", "ambiguous"] },
        "topic": { "anyOf": [{ "type": "string" }, { "type": "null" }] },
        "orderedFiles": { "type": "array", "items": { "type": "string" } }
      }
    },
    "evidenceRef": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "path", "locator", "summary"],
      "properties": {
        "id": { "type": "string", "minLength": 1 },
        "kind": { "enum": ["knowledge", "problem", "resolver", "unknown"] },
        "path": { "anyOf": [{ "type": "string" }, { "type": "null" }] },
        "locator": { "anyOf": [{ "type": "string" }, { "type": "null" }] },
        "summary": { "type": "string" }
      }
    },
    "dimension": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "label", "weight", "score", "evidenceState", "rationale", "evidenceRefs"],
      "properties": {
        "id": { "type": "string" },
        "label": { "type": "string" },
        "weight": { "type": "number" },
        "score": { "$ref": "#/$defs/dimensionScoreInterval" },
        "evidenceState": { "enum": ["supported", "inferred", "unknown"] },
        "rationale": { "type": "string" },
        "evidenceRefs": { "type": "array", "items": { "type": "string" } }
      }
    },
    "assessment": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schemaVersion",
        "normalizedProblem",
        "verdict",
        "recommendation",
        "scores",
        "confidence",
        "dimensions",
        "largestBottleneck",
        "recommendedReframe",
        "informationGaps",
        "evidence"
      ],
      "properties": {
        "schemaVersion": { "const": 1 },
        "normalizedProblem": { "type": "string", "minLength": 1 },
        "verdict": {
          "type": "object",
          "additionalProperties": false,
          "required": ["label", "provisional", "possibleLabels"],
          "properties": {
            "label": { "enum": ["DO_NOW", "REFRAME", "NOT_AUTORESEARCH", "DEFER"] },
            "provisional": { "type": "boolean" },
            "possibleLabels": {
              "type": "array",
              "items": { "enum": ["DO_NOW", "REFRAME", "NOT_AUTORESEARCH", "DEFER"] },
              "minItems": 1,
              "uniqueItems": true
            }
          }
        },
        "recommendation": { "enum": ["proceed", "reframe", "reject", "defer"] },
        "scores": {
          "type": "object",
          "additionalProperties": false,
          "required": ["researchValue", "autoresearchSuitability", "combined"],
          "properties": {
            "researchValue": { "$ref": "#/$defs/scoreInterval" },
            "autoresearchSuitability": { "$ref": "#/$defs/scoreInterval" },
            "combined": { "$ref": "#/$defs/scoreInterval" }
          }
        },
        "confidence": {
          "type": "object",
          "additionalProperties": false,
          "required": ["level", "rationale"],
          "properties": {
            "level": { "enum": ["high", "medium", "low"] },
            "rationale": { "type": "string" }
          }
        },
        "dimensions": {
          "type": "object",
          "additionalProperties": false,
          "required": ["researchValue", "autoresearchSuitability"],
          "properties": {
            "researchValue": { "type": "array", "items": { "$ref": "#/$defs/dimension" } },
            "autoresearchSuitability": { "type": "array", "items": { "$ref": "#/$defs/dimension" } }
          }
        },
        "largestBottleneck": { "type": "string", "minLength": 1 },
        "recommendedReframe": {
          "type": "object",
          "additionalProperties": false,
          "required": ["kind", "text"],
          "properties": {
            "kind": { "enum": ["bounded", "none"] },
            "text": { "type": "string" }
          }
        },
        "informationGaps": { "type": "array", "items": { "type": "string" } },
        "evidence": { "type": "array", "items": { "$ref": "#/$defs/evidenceRef" } }
      }
    },
    "clarification": {
      "type": "object",
      "additionalProperties": false,
      "required": ["query", "reason", "alternatives"],
      "properties": {
        "query": { "type": "string", "minLength": 1 },
        "reason": { "type": "string" },
        "alternatives": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["page", "topic", "title", "matchKind"],
            "properties": {
              "page": { "type": "string", "minLength": 1 },
              "topic": { "type": "string", "minLength": 1 },
              "title": { "type": "string", "minLength": 1 },
              "matchKind": { "type": "string", "minLength": 1 }
            }
          }
        }
      }
    }
  }
}
```

- [ ] **Step 5: Run the policy tests**

Run:

```bash
node --test tests/assessment-policy.test.mjs
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add schemas/research-problem-assessment.schema.json lib/assessments/policy.mjs tests/assessment-policy.test.mjs
git commit -m "feat: add assessment policy contract"
```

---

### Task 3: Host-Side Contract Validation

**Files:**
- Create: `lib/assessments/contract.mjs`
- Test: `tests/assessment-contract.test.mjs`

**Interfaces:**
- Consumes: policy helpers from `lib/assessments/policy.mjs`.
- Produces: `validateAssessmentEnvelope(value: unknown): { ok: true, value: object, computed: object } | { ok: false, errors: string[] }`
- Produces: `parseAssessmentFinalMessage(text: string): { ok: true, value: object, computed: object } | { ok: false, errors: string[] }`
- Produces: `summarizeCompletedAssessment({ run, envelope, computed }): object`

- [ ] **Step 1: Write failing validation tests**

Create `tests/assessment-contract.test.mjs` with helper fixtures:

```js
import assert from "node:assert/strict";
import test from "node:test";

import {
  parseAssessmentFinalMessage,
  summarizeCompletedAssessment,
  validateAssessmentEnvelope,
} from "../lib/assessments/contract.mjs";

function dimension(id, weight, estimate, evidenceState = "supported") {
  return {
    id,
    label: id,
    weight,
    score: { min: estimate, estimate, max: estimate },
    evidenceState,
    rationale: `${id} rationale`,
    evidenceRefs: evidenceState === "unknown" ? [] : ["k1"],
  };
}

function validEnvelope(overrides = {}) {
  return {
    outcome: "assessment",
    language: "en",
    knowledgeResolution: {
      query: "fresh evaluation for a solver problem",
      status: "match",
      topic: "knowledge/example/index.qmd",
      orderedFiles: ["knowledge/index.qmd", "knowledge/example/index.qmd"],
    },
    assessment: {
      schemaVersion: 1,
      normalizedProblem: "Find a fresh, executable benchmark for the solver.",
      verdict: { label: "DO_NOW", provisional: false, possibleLabels: ["DO_NOW"] },
      recommendation: "proceed",
      scores: {
        researchValue: { min: 80, estimate: 80, max: 80 },
        autoresearchSuitability: { min: 80, estimate: 80, max: 80 },
        combined: { min: 80, estimate: 80, max: 80 },
      },
      confidence: { level: "high", rationale: "Every key claim cites trusted knowledge." },
      dimensions: {
        researchValue: [
          dimension("importance", 20, 4),
          dimension("gap_and_novelty", 20, 4),
          dimension("plausibility", 15, 4),
          dimension("learning_from_failure", 15, 4),
          dimension("generality_and_publication", 15, 4),
          dimension("expected_value_relative_to_cost", 15, 4),
        ],
        autoresearchSuitability: [
          dimension("modifiable_search_object", 20, 4),
          dimension("executable_objective", 20, 4),
          dimension("correctness_and_anti_gaming", 15, 4),
          dimension("incremental_feedback", 15, 4),
          dimension("fresh_evaluation", 10, 4),
          dimension("reproducibility_and_auditability", 10, 4),
          dimension("attempt_runtime", 10, 4),
        ],
      },
      largestBottleneck: "The anti-gaming gate needs careful fixture separation.",
      recommendedReframe: { kind: "none", text: "No bounded reframe is needed." },
      informationGaps: [],
      evidence: [{
        id: "k1",
        kind: "knowledge",
        path: "knowledge/example/index.qmd",
        locator: "section: Fresh Evaluation Plan",
        summary: "Trusted page describes the gate.",
      }],
    },
    clarification: null,
    ...overrides,
  };
}

test("accepts a valid assessment and recomputes scores", () => {
  const result = validateAssessmentEnvelope(validEnvelope());
  assert.equal(result.ok, true);
  assert.deepEqual(result.computed.scores.combined, { min: 80, estimate: 80, max: 80 });
  assert.equal(result.computed.verdict.label, "DO_NOW");
});

test("rejects envelopes that contain both assessment and clarification", () => {
  const result = validateAssessmentEnvelope(validEnvelope({
    clarification: { query: "x", reason: "ambiguous", alternatives: [] },
  }));
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /exactly one/);
});

test("accepts resolver ambiguity only as needs_input", () => {
  const result = validateAssessmentEnvelope({
    outcome: "needs_input",
    language: "en",
    knowledgeResolution: {
      query: "Hamiltonian benchmark",
      status: "ambiguous",
      topic: null,
      orderedFiles: [],
    },
    assessment: null,
    clarification: {
      query: "Hamiltonian benchmark",
      reason: "Resolver returned multiple candidates.",
      alternatives: [
        { page: "knowledge/a/index.qmd", topic: "a", title: "A", matchKind: "title" },
        { page: "knowledge/b/index.qmd", topic: "b", title: "B", matchKind: "title" },
      ],
    },
  });
  assert.equal(result.ok, true);
});

test("keeps no-match assessment dimensions evidence-dependent unknown", () => {
  const envelope = validEnvelope({
    knowledgeResolution: {
      query: "unknown candidate",
      status: "no-match",
      topic: null,
      orderedFiles: [],
    },
  });
  envelope.assessment.dimensions.researchValue[1] = dimension("gap_and_novelty", 20, 2, "unknown");
  envelope.assessment.scores.researchValue = { min: 72, estimate: 76, max: 80 };
  const result = validateAssessmentEnvelope(envelope);
  assert.equal(result.ok, false);
  assert.match(result.errors.join("\n"), /model arithmetic/);
});

test("parses Codex final message as the same strict envelope", () => {
  const result = parseAssessmentFinalMessage(JSON.stringify(validEnvelope()));
  assert.equal(result.ok, true);
});

test("summary exposes advisory verdict fields without lifecycle mutation", () => {
  const validation = validateAssessmentEnvelope(validEnvelope());
  const summary = summarizeCompletedAssessment({
    run: { runId: "20260728T010203Z-a1b2c3", problemId: "Prob-001", createdAt: "2026-07-28T01:02:03.000Z" },
    envelope: validation.value,
    computed: validation.computed,
  });
  assert.equal(summary.runId, "20260728T010203Z-a1b2c3");
  assert.equal(summary.verdict, "DO_NOW");
  assert.equal(summary.recommendation, "proceed");
  assert.equal(summary.lifecycleMutation, false);
});
```

- [ ] **Step 2: Run the contract tests and confirm missing-module failure**

Run:

```bash
node --test tests/assessment-contract.test.mjs
```

Expected: fail because `lib/assessments/contract.mjs` does not exist.

- [ ] **Step 3: Implement contract validation**

Create `lib/assessments/contract.mjs` with these validation utilities:

```js
import {
  AUTORESEARCH_DIMENSIONS,
  CONFIDENCE_LEVELS,
  EVIDENCE_STATES,
  RECOMMENDATIONS,
  RESEARCH_VALUE_DIMENSIONS,
  VERDICT_LABELS,
  deriveVerdict,
  harmonicInterval,
  weightedInterval,
} from "./policy.mjs";

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function intervalOk(interval, max) {
  return isRecord(interval)
    && Number.isFinite(interval.min)
    && Number.isFinite(interval.estimate)
    && Number.isFinite(interval.max)
    && interval.min >= 0
    && interval.estimate >= interval.min
    && interval.max >= interval.estimate
    && interval.max <= max;
}

function sameInterval(left, right) {
  return Math.abs(left.min - right.min) <= 0.01
    && Math.abs(left.estimate - right.estimate) <= 0.01
    && Math.abs(left.max - right.max) <= 0.01;
}
```

Then implement:

```js
export function validateAssessmentEnvelope(value) {
  const errors = [];
  if (!isRecord(value)) return { ok: false, errors: ["Envelope must be an object."] };
  if (!["assessment", "needs_input"].includes(value.outcome)) errors.push("outcome must be assessment or needs_input.");
  if (typeof value.language !== "string" || value.language.trim().length < 2) errors.push("language must be a string.");
  if (!isRecord(value.knowledgeResolution)) errors.push("knowledgeResolution must be an object.");

  const hasAssessment = value.assessment !== null && value.assessment !== undefined;
  const hasClarification = value.clarification !== null && value.clarification !== undefined;
  if (Number(hasAssessment) + Number(hasClarification) !== 1) {
    errors.push("Envelope must contain exactly one of assessment or clarification.");
  }

  if (value.outcome === "assessment" && !hasAssessment) errors.push("assessment outcome requires assessment.");
  if (value.outcome === "needs_input" && !hasClarification) errors.push("needs_input outcome requires clarification.");

  const computed = hasAssessment
    ? validateAssessmentObject(value.assessment, value.knowledgeResolution, errors)
    : validateClarificationObject(value.clarification, value.knowledgeResolution, errors);

  return errors.length ? { ok: false, errors } : { ok: true, value, computed };
}
```

`validateAssessmentObject` must verify the exact dimension IDs and weights from `policy.mjs`, all score intervals, evidence states, evidence reference IDs, confidence enum, recommendation enum, one largest bottleneck, one reframe object, and host recomputed totals:

```js
const computedResearch = weightedInterval(assessment.dimensions.researchValue);
const computedFit = weightedInterval(assessment.dimensions.autoresearchSuitability);
const computedCombined = harmonicInterval(computedResearch, computedFit);
const computedVerdict = deriveVerdict({
  valueScore: computedResearch.estimate,
  fitScore: computedFit.estimate,
  hasBoundedReframe: assessment.recommendedReframe.kind === "bounded",
});
```

The function must add these specific error strings when relevant:

```js
errors.push("researchValue model arithmetic does not match host arithmetic.");
errors.push("autoresearchSuitability model arithmetic does not match host arithmetic.");
errors.push("combined model arithmetic does not match host arithmetic.");
errors.push("verdict label does not match host verdict rule.");
errors.push("unknown dimensions must use nonzero intervals when uncertainty remains.");
errors.push("no-match assessments must not cite knowledge evidence.");
```

- [ ] **Step 4: Implement parsing and summary projection**

Add:

```js
export function parseAssessmentFinalMessage(text) {
  try {
    return validateAssessmentEnvelope(JSON.parse(text));
  } catch (error) {
    return { ok: false, errors: [`Final message is not valid JSON: ${error.message}`] };
  }
}

export function summarizeCompletedAssessment({ run, envelope, computed }) {
  const assessment = envelope.assessment;
  return {
    runId: run.runId,
    problemId: run.problemId,
    createdAt: run.createdAt,
    verdict: assessment.verdict.label,
    recommendation: assessment.recommendation,
    confidence: assessment.confidence.level,
    scores: computed.scores,
    largestBottleneck: assessment.largestBottleneck,
    provisional: assessment.verdict.provisional,
    reportHref: `/__local/assessments/reports/${run.problemId}/${run.runId}`,
    lifecycleMutation: false,
  };
}
```

- [ ] **Step 5: Run tests**

Run:

```bash
node --test tests/assessment-policy.test.mjs tests/assessment-contract.test.mjs
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add lib/assessments/contract.mjs tests/assessment-contract.test.mjs
git commit -m "feat: validate assessment envelopes"
```

---

### Task 4: Safe Paths and Immutable Artifact Store

**Files:**
- Create: `lib/assessments/paths.mjs`
- Create: `lib/assessments/artifact-store.mjs`
- Test: `tests/assessment-artifacts.test.mjs`

**Interfaces:**
- Produces: `RUN_ID_PATTERN: RegExp`
- Produces: `createRunId(now?: Date, randomBytesFn?: Function): string`
- Produces: `resolveProblemDir(rootDir: string, problemId: string): Promise<string>`
- Produces: `resolveRunDir(rootDir: string, problemId: string, runId: string): Promise<string>`
- Produces: `createArtifactStore({ rootDir, generatedDir?: string }): ArtifactStore`
- Produces: `ArtifactStore.createAcceptedRun({ problemId, parentRunId?: string }): Promise<RunRecord>`
- Produces: `ArtifactStore.appendEvent(run, event): Promise<void>`
- Produces: `ArtifactStore.writeTerminalArtifacts(run, artifacts): Promise<RunRecord>`
- Produces: `ArtifactStore.listRuns(problemId): Promise<RunRecord[]>`
- Produces: `ArtifactStore.readRun(problemId, runId): Promise<object>`

- [ ] **Step 1: Write failing artifact tests**

Create `tests/assessment-artifacts.test.mjs`:

```js
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  RUN_ID_PATTERN,
  createRunId,
  resolveProblemDir,
  resolveRunDir,
} from "../lib/assessments/paths.mjs";
import { createArtifactStore } from "../lib/assessments/artifact-store.mjs";

test("creates sortable run IDs with fixed timestamp and random suffix", () => {
  const runId = createRunId(new Date("2026-07-28T01:02:03.000Z"), () => Buffer.from("a1b2c3", "hex"));
  assert.equal(runId, "20260728T010203Z-a1b2c3");
  assert.match(runId, RUN_ID_PATTERN);
});

test("rejects traversal in problem and run IDs", async () => {
  const root = await mkdtemp(join(tmpdir(), "assessment-paths-"));
  await assert.rejects(() => resolveProblemDir(root, "../Prob-001"), /Invalid problem ID/);
  await assert.rejects(() => resolveRunDir(root, "Prob-001", "../x"), /Invalid run ID/);
});

test("publishes completed artifacts atomically under the problem", async () => {
  const root = await mkdtemp(join(tmpdir(), "assessment-store-"));
  await mkdir(join(root, "problems", "Prob-001"), { recursive: true });
  const store = createArtifactStore({
    rootDir: root,
    now: () => new Date("2026-07-28T01:02:03.000Z"),
    randomBytes: () => Buffer.from("a1b2c3", "hex"),
  });
  const run = await store.createAcceptedRun({ problemId: "Prob-001" });
  await store.appendEvent(run, { type: "stage", stage: "running" });
  const terminal = await store.writeTerminalArtifacts(run, {
    status: "completed",
    input: { schemaVersion: 1, problemId: "Prob-001" },
    assessment: { accepted: true },
    reportHtml: "<!doctype html><title>Report</title>",
    stderr: "",
  });

  assert.equal(terminal.status, "completed");
  const finalDir = join(root, "problems", "Prob-001", "assessments", "20260728T010203Z-a1b2c3");
  assert.equal((await stat(finalDir)).isDirectory(), true);
  assert.deepEqual(JSON.parse(await readFile(join(finalDir, "run.json"), "utf8")).status, "completed");
  assert.equal(await readFile(join(finalDir, "report.html"), "utf8"), "<!doctype html><title>Report</title>");
});

test("writes failed runs without assessment or report files", async () => {
  const root = await mkdtemp(join(tmpdir(), "assessment-store-"));
  await mkdir(join(root, "problems", "Prob-001"), { recursive: true });
  const store = createArtifactStore({
    rootDir: root,
    now: () => new Date("2026-07-28T02:03:04.000Z"),
    randomBytes: () => Buffer.from("d4e5f6", "hex"),
  });
  const run = await store.createAcceptedRun({ problemId: "Prob-001" });
  await store.writeTerminalArtifacts(run, {
    status: "failed",
    input: { schemaVersion: 1, problemId: "Prob-001" },
    error: { code: "CODEX_EXIT", message: "Codex exited with status 1." },
    stderr: "diagnostic text",
  });

  const finalDir = join(root, "problems", "Prob-001", "assessments", "20260728T020304Z-d4e5f6");
  await assert.rejects(() => readFile(join(finalDir, "assessment.json"), "utf8"), /ENOENT/);
  await assert.rejects(() => readFile(join(finalDir, "report.html"), "utf8"), /ENOENT/);
  assert.match(await readFile(join(finalDir, "stderr.log"), "utf8"), /diagnostic text/);
});
```

- [ ] **Step 2: Run artifact tests and confirm missing-module failure**

Run:

```bash
node --test tests/assessment-artifacts.test.mjs
```

Expected: fail because `lib/assessments/paths.mjs` does not exist.

- [ ] **Step 3: Implement path validation**

Create `lib/assessments/paths.mjs`:

```js
import { randomBytes as nodeRandomBytes } from "node:crypto";
import { mkdir, realpath } from "node:fs/promises";
import { join, resolve } from "node:path";

import { PROBLEM_ID_PATTERN } from "../problems/schema.mjs";

export const RUN_ID_PATTERN = /^\d{8}T\d{6}Z-[a-f0-9]{6}$/;

export function createRunId(now = new Date(), randomBytesFn = nodeRandomBytes) {
  const timestamp = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  return `${timestamp}-${randomBytesFn(3).toString("hex")}`;
}

export async function assertContained(parent, child) {
  const parentReal = await realpath(parent);
  const childResolved = resolve(child);
  if (childResolved !== parentReal && !childResolved.startsWith(`${parentReal}/`)) {
    throw new Error(`Path escapes expected root: ${child}`);
  }
  return childResolved;
}

export async function resolveProblemDir(rootDir, problemId) {
  if (!PROBLEM_ID_PATTERN.test(problemId)) throw new Error(`Invalid problem ID: ${problemId}`);
  const problemsRoot = resolve(rootDir, "problems");
  await mkdir(problemsRoot, { recursive: true });
  return assertContained(problemsRoot, join(problemsRoot, problemId));
}

export async function resolveRunDir(rootDir, problemId, runId) {
  if (!RUN_ID_PATTERN.test(runId)) throw new Error(`Invalid run ID: ${runId}`);
  const problemDir = await resolveProblemDir(rootDir, problemId);
  return assertContained(problemDir, join(problemDir, "assessments", runId));
}
```

- [ ] **Step 4: Implement artifact store**

Create `lib/assessments/artifact-store.mjs` with:

```js
import { mkdir, readFile, readdir, rename, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";

import { createRunId, resolveProblemDir, resolveRunDir } from "./paths.mjs";

async function writeJson(path, value) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
}

export function createArtifactStore({ rootDir, generatedDir = ".generated/assessment-runs", now = () => new Date(), randomBytes } = {}) {
  const workspaceRoot = resolve(rootDir ?? process.cwd());
  const stagingRoot = resolve(workspaceRoot, generatedDir);
  return {
    async createAcceptedRun({ problemId, parentRunId = null }) {
      const problemDir = await resolveProblemDir(workspaceRoot, problemId);
      const runId = createRunId(now(), randomBytes);
      const createdAt = now().toISOString();
      const stagingDir = join(stagingRoot, runId);
      const run = { schemaVersion: 1, runId, problemId, parentRunId, status: "queued", createdAt, updatedAt: createdAt };
      await mkdir(problemDir, { recursive: true });
      await mkdir(stagingDir, { recursive: true });
      await writeJson(join(stagingDir, "run.json"), run);
      await writeFile(join(stagingDir, "events.jsonl"), "");
      await writeFile(join(stagingDir, "stderr.log"), "");
      return { ...run, stagingDir };
    },
    async appendEvent(run, event) {
      await writeFile(join(run.stagingDir, "events.jsonl"), `${JSON.stringify({ at: now().toISOString(), ...event })}\n`, { flag: "a" });
    },
    async writeTerminalArtifacts(run, artifacts) {
      const finalRun = { ...run, status: artifacts.status, updatedAt: now().toISOString(), error: artifacts.error ?? null };
      await writeJson(join(run.stagingDir, "run.json"), finalRun);
      await writeJson(join(run.stagingDir, "input.json"), artifacts.input);
      if (artifacts.assessment) await writeJson(join(run.stagingDir, "assessment.json"), artifacts.assessment);
      if (artifacts.clarification) await writeJson(join(run.stagingDir, "clarification.json"), artifacts.clarification);
      if (artifacts.selection) await writeJson(join(run.stagingDir, "selection.json"), artifacts.selection);
      if (artifacts.reportHtml) await writeFile(join(run.stagingDir, "report.html"), artifacts.reportHtml);
      await writeFile(join(run.stagingDir, "stderr.log"), artifacts.stderr ?? "");
      const finalDir = await resolveRunDir(workspaceRoot, run.problemId, run.runId);
      await mkdir(dirname(finalDir), { recursive: true });
      await rename(run.stagingDir, finalDir);
      return { ...finalRun, finalDir };
    },
    async listRuns(problemId) {
      const problemDir = await resolveProblemDir(workspaceRoot, problemId);
      const assessmentsDir = join(problemDir, "assessments");
      let entries = [];
      try {
        entries = await readdir(assessmentsDir, { withFileTypes: true });
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
      const runs = [];
      for (const entry of entries.filter((item) => item.isDirectory()).sort((a, b) => b.name.localeCompare(a.name))) {
        const text = await readFile(join(assessmentsDir, entry.name, "run.json"), "utf8");
        runs.push(JSON.parse(text));
      }
      return runs;
    },
    async readRun(problemId, runId) {
      const runDir = await resolveRunDir(workspaceRoot, problemId, runId);
      return JSON.parse(await readFile(join(runDir, "run.json"), "utf8"));
    },
  };
}
```

Use `fsync` on platforms where the final implementation can do it without breaking tests; keep tests focused on the immutable published shape.

- [ ] **Step 5: Run artifact tests**

Run:

```bash
node --test tests/assessment-artifacts.test.mjs
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add lib/assessments/paths.mjs lib/assessments/artifact-store.mjs tests/assessment-artifacts.test.mjs
git commit -m "feat: store immutable assessment artifacts"
```

---

### Task 5: Input Snapshot and Staleness Detection

**Files:**
- Create: `lib/assessments/input-snapshot.mjs`
- Create: `lib/assessments/staleness.mjs`
- Test: `tests/assessment-staleness.test.mjs`

**Interfaces:**
- Produces: `sha256Text(text: string): string`
- Produces: `hashFile(path: string): Promise<string | null>`
- Produces: `buildInputSnapshot({ rootDir, problem, envelope, skillPath, schemaPath }): Promise<object>`
- Produces: `evaluateAssessmentStaleness({ rootDir, input, resolveKnowledge }): Promise<{ stale: boolean, reasons: string[] }>`

- [ ] **Step 1: Write failing staleness tests**

Create `tests/assessment-staleness.test.mjs`:

```js
import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { buildInputSnapshot, sha256Text } from "../lib/assessments/input-snapshot.mjs";
import { evaluateAssessmentStaleness } from "../lib/assessments/staleness.mjs";

test("hashes text with sha256", () => {
  assert.equal(sha256Text("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
});

test("builds input snapshot from problem, skill, schema, and matched bundle", async () => {
  const root = await mkdtemp(join(tmpdir(), "assessment-input-"));
  await mkdir(join(root, "problems", "Prob-001"), { recursive: true });
  await mkdir(join(root, "knowledge", "example"), { recursive: true });
  await mkdir(join(root, "skills", "assess-research-problem"), { recursive: true });
  await mkdir(join(root, "schemas"), { recursive: true });
  await writeFile(join(root, "problems", "Prob-001", "problem.json"), "{\"id\":\"Prob-001\"}\n");
  await writeFile(join(root, "problems", "Prob-001", "problem.md"), "Problem markdown.");
  await writeFile(join(root, "knowledge", "example", "index.qmd"), "Trusted bundle.");
  await writeFile(join(root, "skills", "assess-research-problem", "SKILL.md"), "Skill text.");
  await writeFile(join(root, "schemas", "research-problem-assessment.schema.json"), "{}");

  const input = await buildInputSnapshot({
    rootDir: root,
    problem: { id: "Prob-001", title: "Fixture", summary: "Summary" },
    envelope: {
      knowledgeResolution: {
        query: "Fixture",
        status: "match",
        topic: "knowledge/example/index.qmd",
        orderedFiles: ["knowledge/example/index.qmd"],
      },
    },
    skillPath: join(root, "skills", "assess-research-problem", "SKILL.md"),
    schemaPath: join(root, "schemas", "research-problem-assessment.schema.json"),
  });

  assert.equal(input.problemId, "Prob-001");
  assert.equal(input.resolver.status, "match");
  assert.equal(input.bundle[0].path, "knowledge/example/index.qmd");
  assert.match(input.problemJsonHash, /^[a-f0-9]{64}$/);
  assert.match(input.skillHash, /^[a-f0-9]{64}$/);
});

test("marks stale when resolver bundle path changes", async () => {
  const input = {
    problemId: "Prob-001",
    problemJsonHash: "same",
    problemMdHash: "same",
    skillHash: "same",
    schemaHash: "same",
    resolver: { query: "Fixture", status: "match", topic: "knowledge/a.qmd", orderedFiles: ["knowledge/a.qmd"] },
    bundle: [{ path: "knowledge/a.qmd", hash: "same" }],
  };
  const result = await evaluateAssessmentStaleness({
    rootDir: "/tmp/not-read",
    input,
    currentHashes: {
      problemJsonHash: "same",
      problemMdHash: "same",
      skillHash: "same",
      schemaHash: "same",
      bundle: [{ path: "knowledge/a.qmd", hash: "same" }],
    },
    resolveKnowledge: async () => ({
      status: "match",
      topic: "knowledge/b.qmd",
      orderedFiles: ["knowledge/b.qmd"],
    }),
  });
  assert.equal(result.stale, true);
  assert.match(result.reasons.join("\n"), /resolver result changed/);
});
```

- [ ] **Step 2: Run staleness tests and confirm missing-module failure**

Run:

```bash
node --test tests/assessment-staleness.test.mjs
```

Expected: fail because `lib/assessments/input-snapshot.mjs` does not exist.

- [ ] **Step 3: Implement input snapshot hashing**

Create `lib/assessments/input-snapshot.mjs`:

```js
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";

import { ASSESSMENT_POLICY_VERSION } from "./policy.mjs";

export function sha256Text(text) {
  return createHash("sha256").update(text).digest("hex");
}

export async function hashFile(path) {
  try {
    return sha256Text(await readFile(path, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

export async function buildInputSnapshot({ rootDir, problem, envelope, skillPath, schemaPath }) {
  const root = resolve(rootDir);
  const problemDir = join(root, "problems", problem.id);
  const resolver = envelope.knowledgeResolution;
  const bundle = [];
  for (const orderedPath of resolver.orderedFiles ?? []) {
    bundle.push({
      path: orderedPath,
      hash: await hashFile(join(root, orderedPath)),
    });
  }
  return {
    schemaVersion: 1,
    policyVersion: ASSESSMENT_POLICY_VERSION,
    problemId: problem.id,
    problemTitle: problem.title,
    problemSummary: problem.summary,
    problemJsonHash: await hashFile(join(problemDir, "problem.json")),
    problemMdHash: await hashFile(join(problemDir, "problem.md")),
    skillPath: relative(root, skillPath),
    skillHash: await hashFile(skillPath),
    schemaPath: relative(root, schemaPath),
    schemaHash: await hashFile(schemaPath),
    resolver: {
      query: resolver.query,
      status: resolver.status,
      topic: resolver.topic,
      orderedFiles: [...(resolver.orderedFiles ?? [])],
    },
    bundle,
  };
}
```

- [ ] **Step 4: Implement staleness comparison**

Create `lib/assessments/staleness.mjs`:

```js
import { join } from "node:path";

import { hashFile } from "./input-snapshot.mjs";

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

export async function evaluateAssessmentStaleness({ rootDir, input, resolveKnowledge, currentHashes = null }) {
  const reasons = [];
  const hashes = currentHashes ?? {
    problemJsonHash: await hashFile(join(rootDir, "problems", input.problemId, "problem.json")),
    problemMdHash: await hashFile(join(rootDir, "problems", input.problemId, "problem.md")),
    skillHash: await hashFile(join(rootDir, input.skillPath)),
    schemaHash: await hashFile(join(rootDir, input.schemaPath)),
    bundle: await Promise.all((input.bundle ?? []).map(async (item) => ({
      path: item.path,
      hash: await hashFile(join(rootDir, item.path)),
    }))),
  };
  for (const key of ["problemJsonHash", "problemMdHash", "skillHash", "schemaHash"]) {
    if (hashes[key] !== input[key]) reasons.push(`${key} changed`);
  }
  const resolverNow = await resolveKnowledge(input.resolver.query);
  const storedResolver = {
    status: input.resolver.status,
    topic: input.resolver.topic,
    orderedFiles: input.resolver.orderedFiles,
  };
  const currentResolver = {
    status: resolverNow.status,
    topic: resolverNow.topic ?? null,
    orderedFiles: resolverNow.orderedFiles ?? [],
  };
  if (!sameJson(storedResolver, currentResolver)) reasons.push("resolver result changed");
  if (!sameJson(input.bundle ?? [], hashes.bundle ?? [])) reasons.push("resolver bundle hash changed");
  return { stale: reasons.length > 0, reasons };
}
```

- [ ] **Step 5: Run tests**

Run:

```bash
node --test tests/assessment-staleness.test.mjs
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add lib/assessments/input-snapshot.mjs lib/assessments/staleness.mjs tests/assessment-staleness.test.mjs
git commit -m "feat: detect stale assessment inputs"
```

---

### Task 6: Deterministic HTML Report Renderer

**Files:**
- Create: `lib/assessments/html-report.mjs`
- Test: `tests/assessment-report.test.mjs`

**Interfaces:**
- Consumes: validated envelope and computed values from `contract.mjs`.
- Produces: `escapeHtml(value: unknown): string`
- Produces: `renderAssessmentReport({ run, input, envelope, computed }): string`

- [ ] **Step 1: Write failing report tests**

Create `tests/assessment-report.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import { escapeHtml, renderAssessmentReport } from "../lib/assessments/html-report.mjs";

test("escapes HTML-sensitive model text", () => {
  assert.equal(escapeHtml("<script>alert('x')</script>"), "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt;");
});

test("renders a standalone report with required audit sections and no scripts", () => {
  const html = renderAssessmentReport({
    run: {
      runId: "20260728T010203Z-a1b2c3",
      problemId: "Prob-001",
      createdAt: "2026-07-28T01:02:03.000Z",
      updatedAt: "2026-07-28T01:05:00.000Z",
    },
    input: {
      policyVersion: 1,
      problemId: "Prob-001",
      problemTitle: "Fixture problem",
      problemJsonHash: "a".repeat(64),
      problemMdHash: "b".repeat(64),
      skillHash: "c".repeat(64),
      schemaHash: "d".repeat(64),
      resolver: { query: "Fixture", status: "match", topic: "knowledge/example/index.qmd", orderedFiles: ["knowledge/example/index.qmd"] },
      bundle: [{ path: "knowledge/example/index.qmd", hash: "e".repeat(64) }],
    },
    envelope: {
      language: "en",
      assessment: {
        normalizedProblem: "Fixture <problem>",
        verdict: { label: "REFRAME", provisional: true, possibleLabels: ["REFRAME", "DEFER"] },
        recommendation: "reframe",
        confidence: { level: "low", rationale: "One input is uncertain." },
        dimensions: {
          researchValue: [{
            id: "importance",
            label: "Importance",
            weight: 20,
            score: { min: 3, estimate: 4, max: 5 },
            evidenceState: "supported",
            rationale: "Important.",
            evidenceRefs: ["k1"],
          }],
          autoresearchSuitability: [{
            id: "attempt_runtime",
            label: "Attempt runtime",
            weight: 10,
            score: { min: 2, estimate: 3, max: 4 },
            evidenceState: "inferred",
            rationale: "Runtime may exceed the target.",
            evidenceRefs: [],
          }],
        },
        largestBottleneck: "Runtime uncertainty.",
        recommendedReframe: { kind: "bounded", text: "Use a smaller benchmark." },
        informationGaps: ["Need one measured run time."],
        evidence: [{
          id: "k1",
          kind: "knowledge",
          path: "knowledge/example/index.qmd",
          locator: "section",
          summary: "Trusted basis.",
        }],
      },
    },
    computed: {
      scores: {
        researchValue: { min: 60, estimate: 80, max: 100 },
        autoresearchSuitability: { min: 40, estimate: 60, max: 80 },
        combined: { min: 48, estimate: 68.57, max: 88.89 },
      },
      verdict: { label: "REFRAME" },
    },
  });
  assert.match(html, /^<!doctype html>/);
  assert.match(html, /Content-Security-Policy/);
  assert.match(html, /Research Value Audit/);
  assert.match(html, /Autoresearch Fit Audit/);
  assert.match(html, /Evidence Appendix/);
  assert.match(html, /Fixture &lt;problem&gt;/);
  assert.doesNotMatch(html, /<script/i);
  assert.doesNotMatch(html, /https?:\/\//i);
});
```

- [ ] **Step 2: Run report tests and confirm missing-module failure**

Run:

```bash
node --test tests/assessment-report.test.mjs
```

Expected: fail because `lib/assessments/html-report.mjs` does not exist.

- [ ] **Step 3: Implement escaping and document shell**

Create `lib/assessments/html-report.mjs`:

```js
export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");
}

function scoreText(interval) {
  return `${interval.estimate} (${interval.min}-${interval.max})`;
}

function dimensionRows(dimensions) {
  return dimensions.map((item) => `
    <tr>
      <th scope="row">${escapeHtml(item.label)}</th>
      <td>${escapeHtml(item.id)}</td>
      <td>${escapeHtml(item.weight)}</td>
      <td>${escapeHtml(scoreText(item.score))}</td>
      <td>${escapeHtml(item.evidenceState)}</td>
      <td>${escapeHtml(item.rationale)}</td>
      <td>${escapeHtml(item.evidenceRefs.join(", "))}</td>
    </tr>`).join("");
}
```

Then implement `renderAssessmentReport` with exactly these section headings:

```js
export function renderAssessmentReport({ run, input, envelope, computed }) {
  const assessment = envelope.assessment;
  return `<!doctype html>
<html lang="${escapeHtml(envelope.language)}">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(input.problemId)} Assessment Report</title>
  <style>
    body { margin: 0; background: #f3f0e8; color: #17211d; font: 14px/1.55 system-ui, sans-serif; }
    main { width: min(1040px, calc(100% - 48px)); margin: 0 auto; padding: 42px 0 72px; }
    h1 { margin: 0 0 8px; font-size: 32px; line-height: 1.1; }
    h2 { margin: 28px 0 10px; font-size: 18px; }
    table { width: 100%; border-collapse: collapse; background: #fbfaf6; }
    th, td { border: 1px solid #d9d7ce; padding: 8px 10px; text-align: left; vertical-align: top; }
    th { background: #e9e6dc; }
    code { overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 18px 0; }
    .summary div { border: 1px solid #d9d7ce; background: #fbfaf6; padding: 12px; }
    .muted { color: #65716c; }
    @media print { main { width: auto; padding: 0; } }
  </style>
</head>
<body>
<main>
  <p class="muted">${escapeHtml(run.runId)} · policy ${escapeHtml(input.policyVersion)}</p>
  <h1>${escapeHtml(input.problemId)} Research Problem Assessment</h1>
  <p>${escapeHtml(input.problemTitle)}</p>
  <section class="summary" aria-label="Assessment summary">
    <div><strong>Verdict</strong><br>${escapeHtml(assessment.verdict.label)}</div>
    <div><strong>Recommendation</strong><br>${escapeHtml(assessment.recommendation)}</div>
    <div><strong>Confidence</strong><br>${escapeHtml(assessment.confidence.level)}</div>
    <div><strong>Combined</strong><br>${escapeHtml(scoreText(computed.scores.combined))}</div>
  </section>
  <h2>Input Digest</h2>
  <table><tbody>
    <tr><th scope="row">problem.json</th><td><code>${escapeHtml(input.problemJsonHash)}</code></td></tr>
    <tr><th scope="row">problem.md</th><td><code>${escapeHtml(input.problemMdHash)}</code></td></tr>
    <tr><th scope="row">skill</th><td><code>${escapeHtml(input.skillHash)}</code></td></tr>
    <tr><th scope="row">schema</th><td><code>${escapeHtml(input.schemaHash)}</code></td></tr>
  </tbody></table>
  <h2>Bottleneck and Reframe</h2>
  <p><strong>Largest bottleneck:</strong> ${escapeHtml(assessment.largestBottleneck)}</p>
  <p><strong>Recommended reframe:</strong> ${escapeHtml(assessment.recommendedReframe.text)}</p>
  <h2>Research Value Audit</h2>
  <table><thead><tr><th>Dimension</th><th>ID</th><th>Weight</th><th>Score</th><th>Evidence</th><th>Rationale</th><th>Refs</th></tr></thead><tbody>${dimensionRows(assessment.dimensions.researchValue)}</tbody></table>
  <h2>Autoresearch Fit Audit</h2>
  <table><thead><tr><th>Dimension</th><th>ID</th><th>Weight</th><th>Score</th><th>Evidence</th><th>Rationale</th><th>Refs</th></tr></thead><tbody>${dimensionRows(assessment.dimensions.autoresearchSuitability)}</tbody></table>
  <h2>Information Gaps</h2>
  <ul>${assessment.informationGaps.map((gap) => `<li>${escapeHtml(gap)}</li>`).join("") || "<li>None recorded.</li>"}</ul>
  <h2>Evidence Appendix</h2>
  <table><thead><tr><th>ID</th><th>Kind</th><th>Path</th><th>Locator</th><th>Summary</th></tr></thead><tbody>${assessment.evidence.map((item) => `<tr><th scope="row">${escapeHtml(item.id)}</th><td>${escapeHtml(item.kind)}</td><td><code>${escapeHtml(item.path)}</code></td><td>${escapeHtml(item.locator)}</td><td>${escapeHtml(item.summary)}</td></tr>`).join("")}</tbody></table>
</main>
</body>
</html>`;
}
```

- [ ] **Step 4: Run report tests**

Run:

```bash
node --test tests/assessment-report.test.mjs
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add lib/assessments/html-report.mjs tests/assessment-report.test.mjs
git commit -m "feat: render assessment reports"
```

---

### Task 7: Codex Adapter and Preflight

**Files:**
- Create: `lib/assessments/codex-adapter.mjs`
- Test: `tests/assessment-codex-adapter.test.mjs`

**Interfaces:**
- Consumes: schema path from `policy.mjs`.
- Consumes: final-message parser from `contract.mjs`.
- Produces: `checkCodexPreflight({ rootDir, codexCommand?: string, execFileFn?: Function, skillPath?: string, schemaPath?: string }): Promise<{ ok: true, version: string } | { ok: false, code: string, message: string }>`
- Produces: `buildAssessmentPrompt({ problem, problemMarkdown, selectedAlternative?: object }): string`
- Produces: `runCodexAssessment({ rootDir, problem, problemMarkdown, runDir, schemaPath, codexCommand?: string, spawnFn?: Function, timeoutMs?: number, selectedAlternative?: object }): Promise<{ ok: true, envelope: object, computed: object, eventsText: string, stderr: string } | { ok: false, code: string, message: string, eventsText: string, stderr: string }>`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/assessment-codex-adapter.test.mjs`:

```js
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  buildAssessmentPrompt,
  checkCodexPreflight,
  runCodexAssessment,
} from "../lib/assessments/codex-adapter.mjs";

function fakeEnvelopeText() {
  const dimsV = [
    ["importance", 20], ["gap_and_novelty", 20], ["plausibility", 15],
    ["learning_from_failure", 15], ["generality_and_publication", 15],
    ["expected_value_relative_to_cost", 15],
  ].map(([id, weight]) => ({ id, label: id, weight, score: { min: 4, estimate: 4, max: 4 }, evidenceState: "supported", rationale: id, evidenceRefs: ["p1"] }));
  const dimsA = [
    ["modifiable_search_object", 20], ["executable_objective", 20],
    ["correctness_and_anti_gaming", 15], ["incremental_feedback", 15],
    ["fresh_evaluation", 10], ["reproducibility_and_auditability", 10],
    ["attempt_runtime", 10],
  ].map(([id, weight]) => ({ id, label: id, weight, score: { min: 4, estimate: 4, max: 4 }, evidenceState: "supported", rationale: id, evidenceRefs: ["p1"] }));
  return JSON.stringify({
    outcome: "assessment",
    language: "en",
    knowledgeResolution: { query: "Fixture", status: "match", topic: "knowledge/x.qmd", orderedFiles: ["knowledge/x.qmd"] },
    assessment: {
      schemaVersion: 1,
      normalizedProblem: "Fixture",
      verdict: { label: "DO_NOW", provisional: false, possibleLabels: ["DO_NOW"] },
      recommendation: "proceed",
      scores: {
        researchValue: { min: 80, estimate: 80, max: 80 },
        autoresearchSuitability: { min: 80, estimate: 80, max: 80 },
        combined: { min: 80, estimate: 80, max: 80 },
      },
      confidence: { level: "high", rationale: "Supported." },
      dimensions: { researchValue: dimsV, autoresearchSuitability: dimsA },
      largestBottleneck: "None.",
      recommendedReframe: { kind: "none", text: "No bounded reframe is needed." },
      informationGaps: [],
      evidence: [{ id: "p1", kind: "problem", path: "problems/Prob-001/problem.md", locator: null, summary: "Problem text." }],
    },
    clarification: null,
  });
}

test("preflight checks version and login status with fixed commands", async () => {
  const calls = [];
  const result = await checkCodexPreflight({
    rootDir: "/repo",
    skillPath: "/repo/skills/assess-research-problem/SKILL.md",
    schemaPath: "/repo/schemas/research-problem-assessment.schema.json",
    execFileFn(command, args, options, callback) {
      calls.push({ command, args, cwd: options.cwd });
      callback(null, args.includes("--version") ? "codex-cli 0.145.0\n" : "Logged in\n", "");
    },
    fileExists: async () => true,
  });
  assert.equal(result.ok, true);
  assert.deepEqual(calls.map((call) => call.args), [["--version"], ["login", "status"]]);
  assert.deepEqual(calls.map((call) => call.cwd), ["/repo", "/repo"]);
});

test("prompt names the repo skill and forbids lifecycle mutation", () => {
  const prompt = buildAssessmentPrompt({
    problem: { id: "Prob-001", title: "Fixture", summary: "Summary" },
    problemMarkdown: "## Background and Gap\nText.",
  });
  assert.match(prompt, /assess-research-problem/);
  assert.match(prompt, /Do not modify problem\.json/);
  assert.match(prompt, /Return only the structured schema response/);
});

test("codex runner uses safe argv, read-only sandbox, ephemeral mode, JSONL, schema, and output-last-message", async () => {
  const root = await mkdtemp(join(tmpdir(), "assessment-codex-"));
  const runDir = join(root, ".generated", "assessment-runs", "run");
  await mkdir(runDir, { recursive: true });
  const calls = [];
  function spawnFn(command, args, options) {
    calls.push({ command, args, options });
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    child.kill = () => {};
    queueMicrotask(async () => {
      await writeFile(join(runDir, "final-message.json"), fakeEnvelopeText());
      child.stdout.emit("data", Buffer.from("{\"type\":\"stage\",\"stage\":\"done\"}\n"));
      child.emit("exit", 0, null);
    });
    return child;
  }
  const result = await runCodexAssessment({
    rootDir: root,
    problem: { id: "Prob-001", title: "Fixture", summary: "Summary" },
    problemMarkdown: "Problem markdown.",
    runDir,
    schemaPath: join(root, "schemas", "research-problem-assessment.schema.json"),
    spawnFn,
    timeoutMs: 5000,
  });
  assert.equal(result.ok, true);
  assert.equal(calls[0].command, "codex");
  assert.deepEqual(calls[0].args.slice(0, 9), [
    "exec",
    "--sandbox", "read-only",
    "--ephemeral",
    "--json",
    "--output-schema", join(root, "schemas", "research-problem-assessment.schema.json"),
    "--output-last-message",
  ]);
  assert.equal(calls[0].options.cwd, root);
  assert.equal(calls[0].options.shell, false);
});
```

- [ ] **Step 2: Run adapter tests and confirm missing-module failure**

Run:

```bash
node --test tests/assessment-codex-adapter.test.mjs
```

Expected: fail because `lib/assessments/codex-adapter.mjs` does not exist.

- [ ] **Step 3: Implement preflight and prompt builder**

Create `lib/assessments/codex-adapter.mjs`:

```js
import { spawn } from "node:child_process";
import { access, readFile } from "node:fs/promises";
import { join } from "node:path";
import { promisify } from "node:util";
import { execFile } from "node:child_process";

import { parseAssessmentFinalMessage } from "./contract.mjs";

const execFileAsync = promisify(execFile);
export const DEFAULT_CODEX_TIMEOUT_MS = 30 * 60 * 1000;

export async function checkCodexPreflight({
  rootDir,
  codexCommand = "codex",
  execFileFn = execFileAsync,
  skillPath = join(rootDir, "skills", "assess-research-problem", "SKILL.md"),
  schemaPath = join(rootDir, "schemas", "research-problem-assessment.schema.json"),
  fileExists = async (path) => access(path).then(() => true, () => false),
}) {
  if (!await fileExists(skillPath)) return { ok: false, code: "MISSING_SKILL", message: "Assessment skill is missing." };
  if (!await fileExists(schemaPath)) return { ok: false, code: "MISSING_SCHEMA", message: "Assessment output schema is missing." };
  try {
    const version = await execFileFn(codexCommand, ["--version"], { cwd: rootDir });
    await execFileFn(codexCommand, ["login", "status"], { cwd: rootDir });
    return { ok: true, version: String(version.stdout ?? version[0] ?? "").trim() };
  } catch (error) {
    return { ok: false, code: "CODEX_PREFLIGHT", message: error.message };
  }
}

export function buildAssessmentPrompt({ problem, problemMarkdown, selectedAlternative = null }) {
  const selectionText = selectedAlternative
    ? `\nUser selected resolver alternative title: ${selectedAlternative.title}\nPage: ${selectedAlternative.page}\nTopic: ${selectedAlternative.topic}\n`
    : "";
  return [
    "Use the repo-local assess-research-problem skill.",
    "Return only the structured schema response.",
    "Do not modify problem.json, problem.md, knowledge, drafts, literature, or assessments.",
    "If the resolver is ambiguous, return outcome needs_input with every alternative.",
    selectionText,
    `Problem ID: ${problem.id}`,
    `Problem title: ${problem.title}`,
    `Problem summary: ${problem.summary}`,
    "problem.md:",
    problemMarkdown,
  ].join("\n\n");
}
```

- [ ] **Step 4: Implement Codex execution with output-last-message**

Add `runCodexAssessment`:

```js
export function runCodexAssessment({
  rootDir,
  problem,
  problemMarkdown,
  runDir,
  schemaPath,
  codexCommand = "codex",
  spawnFn = spawn,
  timeoutMs = DEFAULT_CODEX_TIMEOUT_MS,
  selectedAlternative = null,
}) {
  return new Promise((resolve) => {
    const finalMessagePath = join(runDir, "final-message.json");
    const prompt = buildAssessmentPrompt({ problem, problemMarkdown, selectedAlternative });
    const args = [
      "exec",
      "--sandbox", "read-only",
      "--ephemeral",
      "--json",
      "--output-schema", schemaPath,
      "--output-last-message", finalMessagePath,
      prompt,
    ];
    const child = spawnFn(codexCommand, args, { cwd: rootDir, shell: false, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
      setTimeout(() => child.kill("SIGKILL"), 5000).unref();
    }, timeoutMs);
    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("error", (error) => {
      clearTimeout(timer);
      resolve({ ok: false, code: "CODEX_SPAWN", message: error.message, eventsText: stdout, stderr });
    });
    child.on("exit", async (code) => {
      clearTimeout(timer);
      if (timedOut) {
        resolve({ ok: false, code: "CODEX_TIMEOUT", message: "Codex assessment exceeded 30 minutes.", eventsText: stdout, stderr });
        return;
      }
      if (code !== 0) {
        resolve({ ok: false, code: "CODEX_EXIT", message: `Codex exited with status ${code}.`, eventsText: stdout, stderr });
        return;
      }
      const text = await readFile(finalMessagePath, "utf8").catch((error) => {
        resolve({ ok: false, code: "MISSING_FINAL", message: error.message, eventsText: stdout, stderr });
        return null;
      });
      if (text === null) return;
      const parsed = parseAssessmentFinalMessage(text);
      if (!parsed.ok) {
        resolve({ ok: false, code: "INVALID_FINAL", message: parsed.errors.join("\n"), eventsText: stdout, stderr });
        return;
      }
      resolve({ ok: true, envelope: parsed.value, computed: parsed.computed, eventsText: stdout, stderr });
    });
  });
}
```

- [ ] **Step 5: Run adapter tests**

Run:

```bash
node --test tests/assessment-codex-adapter.test.mjs
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add lib/assessments/codex-adapter.mjs tests/assessment-codex-adapter.test.mjs
git commit -m "feat: run codex assessment jobs"
```

---

### Task 8: FIFO Job Manager

**Files:**
- Create: `lib/assessments/job-manager.mjs`
- Test: `tests/assessment-job-manager.test.mjs`

**Interfaces:**
- Consumes: `createArtifactStore`, `runCodexAssessment`, `buildInputSnapshot`, `renderAssessmentReport`.
- Produces: `createAssessmentJobManager({ rootDir, repository, store, codex, snapshot, reportRenderer, now }): AssessmentJobManager`
- Produces: `manager.start(problemId): Promise<{ accepted: true, runId: string, status: string } | { accepted: false, code: string, message: string }>`
- Produces: `manager.select(runId, alternative): Promise<object>`
- Produces: `manager.getProblemState(problemId): Promise<object>`
- Produces: `manager.getJob(runId): object | null`
- Produces: `manager.shutdown(): Promise<void>`

- [ ] **Step 1: Write failing job-manager tests**

Create `tests/assessment-job-manager.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import { createAssessmentJobManager } from "../lib/assessments/job-manager.mjs";

function fakeRepository() {
  return {
    getProblem(id) {
      return id === "Prob-001"
        ? { id, title: "Fixture", summary: "Summary" }
        : null;
    },
    async readProblemMarkdown(id) {
      return `# ${id}\n\nProblem body.`;
    },
  };
}

function fakeStore() {
  const runs = [];
  return {
    runs,
    async createAcceptedRun({ problemId, parentRunId = null }) {
      const run = { schemaVersion: 1, runId: `20260728T01020${runs.length}Z-a1b2c3`, problemId, parentRunId, status: "queued", stagingDir: `/tmp/${runs.length}` };
      runs.push(run);
      return run;
    },
    async appendEvent() {},
    async writeTerminalArtifacts(run, artifacts) {
      run.status = artifacts.status;
      run.artifacts = artifacts;
      return run;
    },
    async listRuns(problemId) {
      return runs.filter((run) => run.problemId === problemId);
    },
  };
}

test("rejects unknown problem IDs before accepting a run", async () => {
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store: fakeStore(),
    codex: { preflight: async () => ({ ok: true }), run: async () => ({ ok: true }) },
  });
  const result = await manager.start("Prob-999");
  assert.equal(result.accepted, false);
  assert.equal(result.code, "UNKNOWN_PROBLEM");
});

test("returns the active run for duplicate starts", async () => {
  let release;
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => new Promise((resolve) => { release = () => resolve({ ok: false, code: "CODEX_EXIT", message: "done", eventsText: "", stderr: "" }); }),
    },
  });
  const first = await manager.start("Prob-001");
  const second = await manager.start("Prob-001");
  assert.equal(second.runId, first.runId);
  release();
});

test("runs jobs one at a time in FIFO order", async () => {
  const order = [];
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ problem }) => {
        order.push(problem.id);
        return { ok: false, code: "CODEX_EXIT", message: "forced failure", eventsText: "", stderr: "" };
      },
    },
  });
  await manager.start("Prob-001");
  await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.deepEqual(order, ["Prob-001"]);
  assert.equal(store.runs.length, 1);
});
```

- [ ] **Step 2: Run job-manager tests and confirm missing-module failure**

Run:

```bash
node --test tests/assessment-job-manager.test.mjs
```

Expected: fail because `lib/assessments/job-manager.mjs` does not exist.

- [ ] **Step 3: Implement queue and duplicate suppression**

Create `lib/assessments/job-manager.mjs` with these state constants:

```js
const ACTIVE_STATUSES = new Set(["queued", "running", "needs-input"]);

export function createAssessmentJobManager({ rootDir, repository, store, codex, snapshot, reportRenderer }) {
  const queue = [];
  const jobs = new Map();
  let active = null;

  async function start(problemId) {
    const problem = repository.getProblem(problemId);
    if (!problem) return { accepted: false, code: "UNKNOWN_PROBLEM", message: `Problem ${problemId} was not found.` };
    for (const job of jobs.values()) {
      if (job.problemId === problemId && ACTIVE_STATUSES.has(job.status)) {
        return { accepted: true, runId: job.runId, status: job.status };
      }
    }
    const preflight = await codex.preflight({ rootDir });
    if (!preflight.ok) return { accepted: false, code: preflight.code, message: preflight.message };
    const run = await store.createAcceptedRun({ problemId });
    const job = { runId: run.runId, problemId, status: "queued", queuePosition: queue.length + 1, run };
    jobs.set(job.runId, job);
    queue.push(job);
    pump();
    return { accepted: true, runId: job.runId, status: job.status };
  }
```

Add `pump` so only one job becomes active:

```js
  async function pump() {
    if (active || queue.length === 0) return;
    active = queue.shift();
    active.status = "running";
    active.queuePosition = 0;
    try {
      await execute(active);
    } finally {
      active = null;
      pump();
    }
  }
```

- [ ] **Step 4: Implement terminal transitions**

`execute(job)` must read `problem.md`, run Codex, then write exactly one terminal artifact set:

```js
  async function execute(job) {
    const problem = repository.getProblem(job.problemId);
    const problemMarkdown = await repository.readProblemMarkdown(job.problemId);
    const result = await codex.run({ rootDir, problem, problemMarkdown, runDir: job.run.stagingDir });
    if (!result.ok) {
      job.status = "failed";
      await store.writeTerminalArtifacts(job.run, {
        status: "failed",
        input: { schemaVersion: 1, problemId: job.problemId },
        error: { code: result.code, message: result.message },
        stderr: result.stderr,
      });
      return;
    }
    if (result.envelope.outcome === "needs_input") {
      job.status = "needs-input";
      await store.writeTerminalArtifacts(job.run, {
        status: "needs-input",
        input: { schemaVersion: 1, problemId: job.problemId },
        clarification: result.envelope,
        stderr: result.stderr,
      });
      return;
    }
    const input = await snapshot.build({ rootDir, problem, envelope: result.envelope });
    const reportHtml = reportRenderer.render({ run: job.run, input, envelope: result.envelope, computed: result.computed });
    job.status = "completed";
    await store.writeTerminalArtifacts(job.run, {
      status: "completed",
      input,
      assessment: { envelope: result.envelope, computed: result.computed },
      reportHtml,
      stderr: result.stderr,
    });
  }
```

When the real implementation writes `needs-input`, keep the job queryable by reading immutable artifacts rather than leaving an in-memory-only lock.

- [ ] **Step 5: Implement state reads, selection, and shutdown**

Add methods:

```js
  async function getProblemState(problemId) {
    const runs = await store.listRuns(problemId);
    const activeJob = [...jobs.values()].find((job) => job.problemId === problemId && ACTIVE_STATUSES.has(job.status)) ?? null;
    return { service: "available", problemId, activeJob, runs };
  }

  async function select(runId, alternative) {
    const parent = [...jobs.values()].find((job) => job.runId === runId && job.status === "needs-input");
    if (!parent) return { accepted: false, code: "INVALID_SELECTION_PARENT", message: "Selection parent is not awaiting input." };
    const childRun = await store.createAcceptedRun({ problemId: parent.problemId, parentRunId: runId });
    const child = { runId: childRun.runId, problemId: parent.problemId, status: "queued", queuePosition: queue.length + 1, run: childRun, selectedAlternative: alternative };
    jobs.set(child.runId, child);
    queue.push(child);
    pump();
    return { accepted: true, runId: child.runId, status: child.status };
  }

  async function shutdown() {
    if (active?.child?.kill) active.child.kill("SIGTERM");
  }
```

Return `{ start, select, getProblemState, getJob: (runId) => jobs.get(runId) ?? null, shutdown }`.

- [ ] **Step 6: Run job-manager tests**

Run:

```bash
node --test tests/assessment-job-manager.test.mjs
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add lib/assessments/job-manager.mjs tests/assessment-job-manager.test.mjs
git commit -m "feat: manage local assessment jobs"
```

---

### Task 9: Token-Protected Local HTTP Service

**Files:**
- Create: `lib/assessments/local-service.mjs`
- Create: `scripts/local-assessment-service.mjs`
- Test: `tests/assessment-local-service.test.mjs`

**Interfaces:**
- Consumes: `createAssessmentJobManager`.
- Produces: `createAssessmentService({ rootDir, token, manager }): http.Server`
- Produces: `startAssessmentService({ rootDir, token, port?: number, host?: "127.0.0.1" }): Promise<{ server, url, close }>`

- [ ] **Step 1: Write failing local service tests**

Create `tests/assessment-local-service.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import { createAssessmentService } from "../lib/assessments/local-service.mjs";

async function request(server, path, options = {}) {
  const listener = await new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server.address()));
  });
  try {
    return fetch(`http://127.0.0.1:${listener.port}${path}`, options);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

test("rejects requests missing the capability token", async () => {
  const server = createAssessmentService({ token: "secret", manager: {} });
  const response = await request(server, "/__local/assessments/problems/Prob-001");
  assert.equal(response.status, 401);
});

test("starts jobs through the POST endpoint", async () => {
  const calls = [];
  const server = createAssessmentService({
    token: "secret",
    manager: {
      start: async (problemId) => {
        calls.push(problemId);
        return { accepted: true, runId: "20260728T010203Z-a1b2c3", status: "queued" };
      },
    },
  });
  const response = await request(server, "/__local/assessments/jobs", {
    method: "POST",
    headers: { "x-local-assessment-token": "secret", "content-type": "application/json" },
    body: JSON.stringify({ problemId: "Prob-001" }),
  });
  assert.equal(response.status, 202);
  assert.deepEqual(calls, ["Prob-001"]);
  assert.equal((await response.json()).runId, "20260728T010203Z-a1b2c3");
});

test("rejects traversal IDs before manager calls", async () => {
  const server = createAssessmentService({
    token: "secret",
    manager: {
      getProblemState: async () => assert.fail("manager should not be called"),
    },
  });
  const response = await request(server, "/__local/assessments/problems/../x", {
    headers: { "x-local-assessment-token": "secret" },
  });
  assert.equal(response.status, 400);
});
```

- [ ] **Step 2: Run local-service tests and confirm missing-module failure**

Run:

```bash
node --test tests/assessment-local-service.test.mjs
```

Expected: fail because `lib/assessments/local-service.mjs` does not exist.

- [ ] **Step 3: Implement request parsing and token gate**

Create `lib/assessments/local-service.mjs`:

```js
import http from "node:http";

import { PROBLEM_ID_PATTERN } from "../problems/schema.mjs";
import { RUN_ID_PATTERN } from "./paths.mjs";

const MAX_BODY_BYTES = 16 * 1024;

async function readJsonBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw Object.assign(new Error("Request body too large."), { status: 413 });
    chunks.push(chunk);
  }
  const text = Buffer.concat(chunks).toString("utf8") || "{}";
  return JSON.parse(text);
}

function send(response, status, body, headers = {}) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", ...headers });
  response.end(JSON.stringify(body));
}

function validProblemId(id) {
  return PROBLEM_ID_PATTERN.test(id);
}

function validRunId(id) {
  return RUN_ID_PATTERN.test(id);
}
```

- [ ] **Step 4: Implement endpoints**

Implement `createAssessmentService` with these routes:

```js
export function createAssessmentService({ token, manager }) {
  return http.createServer(async (request, response) => {
    try {
      if (request.headers["x-local-assessment-token"] !== token) {
        send(response, 401, { error: "UNAUTHORIZED" });
        return;
      }
      const url = new URL(request.url, "http://127.0.0.1");
      if (request.method === "POST" && url.pathname === "/__local/assessments/jobs") {
        const body = await readJsonBody(request);
        if (!validProblemId(body.problemId)) return send(response, 400, { error: "INVALID_PROBLEM_ID" });
        const result = await manager.start(body.problemId);
        return send(response, result.accepted ? 202 : 400, result);
      }
      const problemMatch = url.pathname.match(/^\/__local\/assessments\/problems\/([^/]+)$/);
      if (request.method === "GET" && problemMatch) {
        const problemId = decodeURIComponent(problemMatch[1]);
        if (!validProblemId(problemId)) return send(response, 400, { error: "INVALID_PROBLEM_ID" });
        return send(response, 200, await manager.getProblemState(problemId));
      }
      const jobMatch = url.pathname.match(/^\/__local\/assessments\/jobs\/([^/]+)$/);
      if (request.method === "GET" && jobMatch) {
        const runId = decodeURIComponent(jobMatch[1]);
        if (!validRunId(runId)) return send(response, 400, { error: "INVALID_RUN_ID" });
        const job = manager.getJob(runId);
        return job ? send(response, 200, job) : send(response, 404, { error: "UNKNOWN_RUN" });
      }
      send(response, 404, { error: "NOT_FOUND" });
    } catch (error) {
      send(response, error.status ?? 500, { error: "LOCAL_ASSESSMENT_ERROR", message: error.message });
    }
  });
}
```

After this base passes, add `POST /jobs/{run-id}/selection`, `GET /reports/{problem-id}/{run-id}`, and `GET /logs/{problem-id}/{run-id}` with the same validation. Reports must serve `text/html; charset=utf-8`; logs must serve `text/plain; charset=utf-8` with `content-disposition: attachment`.

- [ ] **Step 5: Add standalone service entrypoint**

Create `scripts/local-assessment-service.mjs`:

```js
import { randomBytes } from "node:crypto";
import { resolve } from "node:path";

import generatedIndex from "../.generated/problem-index.json" with { type: "json" };
import { createAssessmentJobManager } from "../lib/assessments/job-manager.mjs";
import { createAssessmentService } from "../lib/assessments/local-service.mjs";
import { createProblemRepository } from "../lib/problems/repository.mjs";

const rootDir = resolve(process.cwd());
const token = process.env.LOCAL_ASSESSMENT_TOKEN ?? randomBytes(16).toString("hex");
const repository = createProblemRepository(generatedIndex);
const manager = createAssessmentJobManager({ rootDir, repository });
const server = createAssessmentService({ token, manager });

server.listen(0, "127.0.0.1", () => {
  const address = server.address();
  console.log(JSON.stringify({ url: `http://127.0.0.1:${address.port}`, token }));
});
```

- [ ] **Step 6: Run local-service tests**

Run:

```bash
node --test tests/assessment-local-service.test.mjs
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add lib/assessments/local-service.mjs scripts/local-assessment-service.mjs tests/assessment-local-service.test.mjs
git commit -m "feat: expose local assessment service"
```

---

### Task 10: Dev Supervisor and Vite Proxy

**Files:**
- Modify: `scripts/dev-problem-index.mjs`
- Modify: `vite.config.ts`
- Modify: `tests/dev-problem-index.test.mjs`

**Interfaces:**
- Consumes: `startAssessmentService`.
- Produces: env vars passed to `vinext dev`: `LOCAL_ASSESSMENT_SERVICE_URL` and `LOCAL_ASSESSMENT_PROXY_TOKEN`.
- Produces: Vite dev proxy for `/__local/assessments`.

- [ ] **Step 1: Add failing supervisor tests**

Modify `tests/dev-problem-index.test.mjs` to add:

```js
test("dev wrapper starts the local assessment service and passes proxy env to vinext", async () => {
  const { main } = await import("../scripts/dev-problem-index.mjs");
  const spawnCalls = [];
  const child = new EventEmitter();
  child.kill = () => {};
  function spawnFn(command, args, options) {
    spawnCalls.push({ command, args, options });
    queueMicrotask(() => child.emit("exit", 0));
    return child;
  }
  const service = {
    url: "http://127.0.0.1:39001",
    token: "token-123",
    close: async () => {},
  };
  await main({
    rootDir: "/tmp/research-loop-dev-root",
    spawnFn,
    runIndexBuildFn: async () => {},
    watchProblemFilesFn: async () => ({ close() {} }),
    startAssessmentServiceFn: async () => service,
  });
  const vinext = spawnCalls.find((call) => call.command === "vinext");
  assert.equal(vinext.options.env.LOCAL_ASSESSMENT_SERVICE_URL, service.url);
  assert.equal(vinext.options.env.LOCAL_ASSESSMENT_PROXY_TOKEN, service.token);
});
```

The real test may need a small `main` return hook so it does not call `process.exitCode` before assertions. Keep the injected `spawnFn`, `runIndexBuildFn`, `watchProblemFilesFn`, and `startAssessmentServiceFn` names stable.

- [ ] **Step 2: Run the dev wrapper test and confirm failure**

Run:

```bash
node --test tests/dev-problem-index.test.mjs
```

Expected: fail because `main` does not accept the new injected service function.

- [ ] **Step 3: Update `scripts/dev-problem-index.mjs`**

Modify imports:

```js
import { randomBytes } from "node:crypto";
import { startAssessmentService } from "../lib/assessments/local-service.mjs";
```

Change `main` signature:

```js
export async function main({
  rootDir = process.cwd(),
  spawnFn = spawn,
  runIndexBuildFn = runIndexBuild,
  watchProblemFilesFn = watchProblemFiles,
  startAssessmentServiceFn = startAssessmentService,
} = {}) {
```

Start the service after the first index build:

```js
await runIndexBuildFn(resolvedRootDir);
const assessmentToken = randomBytes(16).toString("hex");
const assessmentService = await startAssessmentServiceFn({
  rootDir: resolvedRootDir,
  token: assessmentToken,
});
```

Pass proxy env vars to `vinext`:

```js
const child = spawnFn("vinext", ["dev"], {
  cwd: resolvedRootDir,
  env: {
    ...process.env,
    WRANGLER_LOG_PATH: ".wrangler/wrangler.log",
    LOCAL_ASSESSMENT_SERVICE_URL: assessmentService.url,
    LOCAL_ASSESSMENT_PROXY_TOKEN: assessmentService.token ?? assessmentToken,
  },
  stdio: "inherit",
});
```

Close the service in `child.on("exit")`:

```js
child.on("exit", async (code, signal) => {
  watcher.close();
  clearTimeout(timer);
  await assessmentService.close();
  process.exitCode = code ?? (signal ? 1 : 0);
});
```

- [ ] **Step 4: Add Vite proxy config**

Modify `vite.config.ts` inside the returned config object:

```ts
const localAssessmentTarget = process.env.LOCAL_ASSESSMENT_SERVICE_URL;
const localAssessmentToken = process.env.LOCAL_ASSESSMENT_PROXY_TOKEN;
```

Then set `server` so it preserves the current watch override and adds a proxy only when both env vars exist:

```ts
const server = {
  ...(isCodexSeatbeltSandbox ? { watch: { useFsEvents: false, usePolling: true } } : {}),
  ...(localAssessmentTarget && localAssessmentToken
    ? {
        proxy: {
          "/__local/assessments": {
            target: localAssessmentTarget,
            changeOrigin: false,
            headers: { "x-local-assessment-token": localAssessmentToken },
          },
        },
      }
    : {}),
};
```

Use `server: Object.keys(server).length ? server : undefined` in the returned config.

- [ ] **Step 5: Run tests**

Run:

```bash
node --test tests/dev-problem-index.test.mjs
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/dev-problem-index.mjs vite.config.ts tests/dev-problem-index.test.mjs
git commit -m "feat: proxy local assessment service in dev"
```

---

### Task 11: UI View Model

**Files:**
- Create: `lib/assessments/view-model.mjs`
- Test: `tests/assessment-view-model.test.mjs`

**Interfaces:**
- Produces: `formatScoreInterval(interval): string`
- Produces: `assessmentStatusCopy(state): { heading: string, body: string, actionLabel: string | null }`
- Produces: `latestAssessmentSummary(problemState): object | null`
- Produces: `isLocalAssessmentUnavailable(errorOrResponse): boolean`

- [ ] **Step 1: Write failing view-model tests**

Create `tests/assessment-view-model.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import {
  assessmentStatusCopy,
  formatScoreInterval,
  isLocalAssessmentUnavailable,
  latestAssessmentSummary,
} from "../lib/assessments/view-model.mjs";

test("formats score intervals compactly", () => {
  assert.equal(formatScoreInterval({ min: 60, estimate: 72.5, max: 80 }), "72.5 (60-80)");
});

test("provides copy for every panel state", () => {
  assert.equal(assessmentStatusCopy({ kind: "never" }).actionLabel, "Run assessment");
  assert.equal(assessmentStatusCopy({ kind: "queued", queuePosition: 2 }).heading, "Assessment queued");
  assert.equal(assessmentStatusCopy({ kind: "running", elapsedSeconds: 42 }).heading, "Assessment running");
  assert.equal(assessmentStatusCopy({ kind: "needs-input" }).heading, "Knowledge match needs input");
  assert.equal(assessmentStatusCopy({ kind: "completed" }).heading, "Assessment complete");
  assert.equal(assessmentStatusCopy({ kind: "failed" }).actionLabel, "Retry");
  assert.equal(assessmentStatusCopy({ kind: "stale" }).actionLabel, "Run new assessment");
  assert.equal(assessmentStatusCopy({ kind: "unavailable" }).heading, "Local assessment unavailable");
});

test("selects latest completed summary without mutating lifecycle", () => {
  const summary = latestAssessmentSummary({
    runs: [
      { runId: "20260728T010203Z-a1b2c3", status: "failed" },
      { runId: "20260728T010204Z-a1b2c3", status: "completed", summary: { verdict: "DEFER", lifecycleMutation: false } },
    ],
  });
  assert.equal(summary.verdict, "DEFER");
  assert.equal(summary.lifecycleMutation, false);
});

test("treats 404 and fetch failure as local-unavailable for static output", () => {
  assert.equal(isLocalAssessmentUnavailable({ status: 404 }), true);
  assert.equal(isLocalAssessmentUnavailable(new TypeError("fetch failed")), true);
});
```

- [ ] **Step 2: Run view-model tests and confirm missing-module failure**

Run:

```bash
node --test tests/assessment-view-model.test.mjs
```

Expected: fail because `lib/assessments/view-model.mjs` does not exist.

- [ ] **Step 3: Implement view-model helpers**

Create `lib/assessments/view-model.mjs`:

```js
export function formatScoreInterval(interval) {
  return `${interval.estimate} (${interval.min}-${interval.max})`;
}

export function assessmentStatusCopy(state) {
  switch (state.kind) {
    case "never":
      return { heading: "No assessment yet", body: "Run a local Codex assessment for this problem.", actionLabel: "Run assessment" };
    case "queued":
      return { heading: "Assessment queued", body: `Queue position ${state.queuePosition}.`, actionLabel: null };
    case "running":
      return { heading: "Assessment running", body: `Elapsed ${state.elapsedSeconds ?? 0}s.`, actionLabel: null };
    case "needs-input":
      return { heading: "Knowledge match needs input", body: "Choose the exact trusted knowledge match to continue.", actionLabel: null };
    case "completed":
      return { heading: "Assessment complete", body: "Recommendation is advisory and does not change lifecycle status.", actionLabel: "Rerun" };
    case "failed":
      return { heading: "Assessment failed", body: state.reason ?? "Open diagnostics for details.", actionLabel: "Retry" };
    case "stale":
      return { heading: "Assessment may be stale", body: "Inputs changed since this report was generated.", actionLabel: "Run new assessment" };
    default:
      return { heading: "Local assessment unavailable", body: "Start the local development server to run assessments.", actionLabel: null };
  }
}

export function latestAssessmentSummary(problemState) {
  return (problemState.runs ?? []).find((run) => run.status === "completed" && run.summary) ?.summary ?? null;
}

export function isLocalAssessmentUnavailable(errorOrResponse) {
  return errorOrResponse instanceof TypeError || errorOrResponse?.status === 404;
}
```

- [ ] **Step 4: Run view-model tests**

Run:

```bash
node --test tests/assessment-view-model.test.mjs
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add lib/assessments/view-model.mjs tests/assessment-view-model.test.mjs
git commit -m "feat: add assessment panel view model"
```

---

### Task 12: Problem-Page Assessment Panel

**Files:**
- Create: `app/problems/[id]/assessment-panel.tsx`
- Modify: `app/problems/[id]/page.tsx`
- Modify: `app/globals.css`
- Modify: `tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: local API endpoints from Task 9.
- Consumes: view-model helpers from Task 11.
- Produces: a client-side `AssessmentPanel({ problemId }: { problemId: string })` component.

- [ ] **Step 1: Add failing server-render assertions**

Modify the existing `server-renders the generic problem detail shell for non-example problems` test in `tests/rendered-html.test.mjs`:

```js
assert.match(html, /<section class="assessment-panel assessment-unavailable" aria-labelledby="assessment-heading">/);
assert.match(html, /Local assessment unavailable/);
assert.match(html, /The detailed problem workspace will be designed next/);
```

Add the same unavailable assertion to the static example detail test when that route is built by the pages showcase:

```js
assert.match(html, /Local assessment unavailable/);
```

- [ ] **Step 2: Run rendered test and confirm failure**

Run:

```bash
npm run build && node --test tests/rendered-html.test.mjs
```

Expected: fail because the detail page does not render an assessment panel.

- [ ] **Step 3: Create the client panel**

Create `app/problems/[id]/assessment-panel.tsx`:

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  assessmentStatusCopy,
  formatScoreInterval,
  isLocalAssessmentUnavailable,
  latestAssessmentSummary,
} from "@/lib/assessments/view-model.mjs";

type Props = { problemId: string };

export function AssessmentPanel({ problemId }: Props) {
  const [state, setState] = useState<any>({ kind: "unavailable" });
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const response = await fetch(`/__local/assessments/problems/${encodeURIComponent(problemId)}`, { cache: "no-store" });
      if (!response.ok) {
        if (isLocalAssessmentUnavailable(response)) setState({ kind: "unavailable" });
        else setState({ kind: "failed", reason: `Local service returned ${response.status}.` });
        return;
      }
      const body = await response.json();
      if (body.activeJob) setState({ kind: body.activeJob.status === "queued" ? "queued" : body.activeJob.status, ...body.activeJob });
      else if (body.stale) setState({ kind: "stale", latest: body.latest });
      else if (body.latest) setState({ kind: "completed", latest: body.latest });
      else setState({ kind: "never" });
    } catch (error) {
      setState(isLocalAssessmentUnavailable(error) ? { kind: "unavailable" } : { kind: "failed", reason: String(error) });
    }
  }

  useEffect(() => {
    refresh();
  }, [problemId]);

  useEffect(() => {
    if (!["queued", "running"].includes(state.kind)) return;
    const timer = window.setInterval(refresh, 2500);
    return () => window.clearInterval(timer);
  }, [state.kind, problemId]);

  async function start() {
    setBusy(true);
    try {
      const response = await fetch("/__local/assessments/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ problemId }),
      });
      if (response.ok) await refresh();
      else setState({ kind: "failed", reason: `Local service returned ${response.status}.` });
    } finally {
      setBusy(false);
    }
  }

  const copy = assessmentStatusCopy(state);
  const latest = state.latest ?? latestAssessmentSummary(state);

  return (
    <section className={`assessment-panel assessment-${state.kind}`} aria-labelledby="assessment-heading">
      <div className="assessment-panel-head">
        <div>
          <p className="eyebrow">QUALIFICATION</p>
          <h2 id="assessment-heading">{copy.heading}</h2>
          <p>{copy.body}</p>
        </div>
        {copy.actionLabel && (
          <button className="state-action" type="button" onClick={start} disabled={busy}>
            {busy ? "Starting" : copy.actionLabel}
          </button>
        )}
      </div>
      {latest && (
        <dl className="assessment-summary-grid">
          <div><dt>Verdict</dt><dd>{latest.verdict}</dd></div>
          <div><dt>Recommendation</dt><dd>{latest.recommendation}</dd></div>
          <div><dt>Confidence</dt><dd>{latest.confidence}</dd></div>
          <div><dt>V</dt><dd>{formatScoreInterval(latest.scores.researchValue)}</dd></div>
          <div><dt>A</dt><dd>{formatScoreInterval(latest.scores.autoresearchSuitability)}</dd></div>
          <div><dt>S</dt><dd>{formatScoreInterval(latest.scores.combined)}</dd></div>
        </dl>
      )}
      {latest?.largestBottleneck && <p className="assessment-bottleneck">{latest.largestBottleneck}</p>}
      {latest?.reportHref && <a className="open-affordance" href={latest.reportHref}>Open detailed report <span aria-hidden="true">→</span></a>}
    </section>
  );
}
```

After this passes the first rendered test, add the `needs-input` branch with radio buttons for `state.clarification.alternatives` and a `POST /jobs/{runId}/selection` call. The selection payload must be the exact `{ page, topic, title, matchKind }` object from the parent response.

- [ ] **Step 4: Add server fallback markup and import panel**

Modify `app/problems/[id]/page.tsx`:

```tsx
import { AssessmentPanel } from "./assessment-panel";
```

In the ordinary problem branch, insert the panel after summary:

```tsx
<p className="detail-summary">{problem.summary}</p>
<AssessmentPanel problemId={problem.id} />
<section className="detail-panel" aria-labelledby="detail-status-heading">
```

In the static example branch, insert after `example-disclaimer` and before metrics:

```tsx
<p className="example-disclaimer">{example.manifest.disclaimer}</p>
<AssessmentPanel problemId={problem.id} />
<dl className="research-metric-strip" aria-label="Research metrics">
```

The client component's first render must be the unavailable state so static HTML has deterministic unavailable copy before hydration.

- [ ] **Step 5: Add scoped CSS**

Append to `app/globals.css` near `.detail-panel`:

```css
.assessment-panel {
  margin: 0 0 24px;
  border: 1px solid var(--line);
  background: var(--surface);
  padding: 18px;
}

.assessment-panel-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 18px;
}

.assessment-panel h2 {
  margin: 0;
  font-size: 16px;
}

.assessment-panel p {
  margin: 7px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.assessment-summary-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  margin: 16px 0 0;
  border: 1px solid var(--line);
}

.assessment-summary-grid > div {
  min-width: 0;
  border-right: 1px solid var(--line);
  padding: 10px;
}

.assessment-summary-grid > div:last-child {
  border-right: 0;
}

.assessment-summary-grid dt {
  color: var(--muted);
  font: 10px var(--font-geist-mono);
}

.assessment-summary-grid dd {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
  font-size: 13px;
  font-weight: 650;
}

.assessment-bottleneck {
  border-top: 1px solid var(--line);
  padding-top: 12px;
}

@media (max-width: 760px) {
  .assessment-panel-head {
    display: block;
  }
  .assessment-summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .assessment-summary-grid > div {
    border-bottom: 1px solid var(--line);
  }
  .assessment-summary-grid > div:nth-child(2n) {
    border-right: 0;
  }
}
```

- [ ] **Step 6: Run rendered tests**

Run:

```bash
npm run build && node --test tests/rendered-html.test.mjs
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add 'app/problems/[id]/assessment-panel.tsx' 'app/problems/[id]/page.tsx' app/globals.css tests/rendered-html.test.mjs
git commit -m "feat: show local assessment panel"
```

---

### Task 13: Browser E2E with Fake Codex

**Files:**
- Create: `playwright.assessment.config.ts`
- Create: `tests/e2e/local-assessment.spec.ts`
- Modify: `package.json`

**Interfaces:**
- Consumes: local service and panel from earlier tasks.
- Produces: `npm run test:e2e:assessment`.

- [ ] **Step 1: Add the package script**

Modify `package.json`:

```json
"test:e2e:assessment": "playwright test --config playwright.assessment.config.ts"
```

Keep `test:e2e` unchanged so the existing built-app suite still runs against `playwright.config.ts`.

- [ ] **Step 2: Create local assessment Playwright config**

Create `playwright.assessment.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

const PORT = 4174;
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "tests/e2e",
  testMatch: /local-assessment\.spec\.ts/,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `PORT=${PORT} npm run dev`,
    url: BASE_URL,
    reuseExistingServer: false,
    timeout: 300_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
```

If `vinext dev` uses a different port environment variable in this repo version, replace `PORT=${PORT}` with the exact variable verified by `vinext dev --help` during this task and record it in the commit message body.

- [ ] **Step 3: Write the browser test**

Create `tests/e2e/local-assessment.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("runs local assessment and opens generated report", async ({ page }) => {
  await page.goto("/problems/Prob-001");
  await expect(page.getByRole("heading", { name: "No assessment yet" })).toBeVisible();
  await page.getByRole("button", { name: "Run assessment" }).click();
  await expect(page.getByRole("heading", { name: /Assessment queued|Assessment running|Assessment complete/ })).toBeVisible();
  await expect(page.getByText("Recommendation")).toBeVisible({ timeout: 120_000 });
  const reportLink = page.getByRole("link", { name: /Open detailed report/ });
  await expect(reportLink).toBeVisible();
  const report = await page.context().newPage();
  await report.goto(await reportLink.getAttribute("href") ?? "");
  await expect(report.getByRole("heading", { name: /Research Problem Assessment/ })).toBeVisible();
  await expect(report.getByRole("heading", { name: "Research Value Audit" })).toBeVisible();
});

test("requires explicit resolver selection for ambiguous knowledge", async ({ page }) => {
  await page.goto("/problems/Prob-001?fakeAssessment=ambiguous");
  await page.getByRole("button", { name: "Run assessment" }).click();
  await expect(page.getByRole("heading", { name: "Knowledge match needs input" })).toBeVisible({ timeout: 120_000 });
  await page.getByLabel(/knowledge\/a\/index\.qmd/).check();
  await page.getByRole("button", { name: "Continue assessment" }).click();
  await expect(page.getByRole("heading", { name: "Assessment complete" })).toBeVisible({ timeout: 120_000 });
});
```

Before this test can pass, create a fixture problem for the dev index in the test setup or reuse a committed non-showcase fixture if one exists after the current problem-page work lands. The setup must restore `.generated/problem-index.json` after the test run, using the same backup-and-restore pattern already present in `tests/rendered-html.test.mjs`.

- [ ] **Step 4: Add fake Codex support without real quota**

Extend `scripts/dev-problem-index.mjs` or the Playwright config so tests can put a fake `codex` executable first on `PATH`. The fake executable must write a schema-valid final response to the path received after `--output-last-message` and exit zero. The ambiguous path must write an envelope with `outcome: "needs_input"` and two alternatives.

Use this executable behavior in the test setup:

```js
const outputPath = args[args.indexOf("--output-last-message") + 1];
await writeFile(outputPath, process.env.FAKE_ASSESSMENT_MODE === "ambiguous"
  ? JSON.stringify(ambiguousEnvelope)
  : JSON.stringify(completedEnvelope));
process.stdout.write("{\"type\":\"stage\",\"stage\":\"fake-complete\"}\n");
process.exit(0);
```

- [ ] **Step 5: Run browser assessment tests**

Run:

```bash
npm run test:e2e:assessment
```

Expected: pass without invoking the real Codex CLI.

- [ ] **Step 6: Commit**

Run:

```bash
git add playwright.assessment.config.ts tests/e2e/local-assessment.spec.ts package.json
git commit -m "test: cover local assessment workflow"
```

---

### Task 14: Package Scripts and Documentation

**Files:**
- Modify: `package.json`
- Create: `docs/local-assessments.md`
- Modify: `README.md`

**Interfaces:**
- Produces: documented local workflow.
- Produces: unit-test script coverage for new `tests/assessment-*.test.mjs`.

- [ ] **Step 1: Add assessment unit tests to package scripts**

Modify `package.json` so `test:unit:problems` includes the new Node tests:

```json
"test:unit:problems": "node --test tests/static-example-content.test.mjs tests/example-research.test.mjs tests/problem-schema.test.mjs tests/problem-indexer.test.mjs tests/dev-problem-index.test.mjs tests/problem-repository.test.mjs tests/codex-launch.test.mjs tests/problem-presentation.test.mjs tests/problem-view-state.test.mjs tests/imported-research-schema.test.mjs tests/research-indexer.test.mjs tests/assessment-policy.test.mjs tests/assessment-contract.test.mjs tests/assessment-artifacts.test.mjs tests/assessment-staleness.test.mjs tests/assessment-report.test.mjs tests/assessment-codex-adapter.test.mjs tests/assessment-job-manager.test.mjs tests/assessment-local-service.test.mjs tests/assessment-view-model.test.mjs"
```

- [ ] **Step 2: Write local operator documentation**

Create `docs/local-assessments.md`:

```md
# Local Assessment Reports

Local assessment reports are generated only when the app is running through
`make dev` or `npm run dev`. The deployed static showcase cannot start Codex
and does not publish assessment artifacts.

## Running an assessment

1. Start the local app with `make dev`.
2. Open a problem page under `/problems/Prob-###`.
3. Press `Run assessment`.
4. Wait for the panel to show the advisory verdict, recommendation, confidence,
   and V/A/S scores.
5. Open the detailed report link for the full audit table and evidence
   appendix.

## Artifacts

Each accepted run is stored under
`problems/Prob-###/assessments/YYYYMMDDTHHMMSSZ-abcdef/`.

Completed runs include `run.json`, `input.json`, `assessment.json`,
`report.html`, `events.jsonl`, and `stderr.log`. Clarification runs include
`clarification.json`. Failed and interrupted runs include diagnostics but no
formal assessment and no report.

The service never stages or commits these files. Review them as ordinary local
repository changes.

## Manual smoke test with real Codex

Run this only when you are willing to consume local Codex quota:

```bash
codex login status
make dev
```

Then run one assessment from the browser and verify that:

- the Codex command is read-only;
- the panel shows an advisory recommendation;
- `problem.json` is unchanged;
- `report.html` opens locally; and
- `events.jsonl` and `stderr.log` stay under the problem's assessment run.
```

- [ ] **Step 3: Link the documentation from README**

Add one short section to `README.md`:

```md
## Local assessment reports

When running the app locally, a problem page can start a read-only Codex CLI
assessment and write immutable local artifacts under the problem directory. See
`docs/local-assessments.md` for the workflow, artifact layout, and manual smoke
test.
```

- [ ] **Step 4: Run documentation-adjacent tests**

Run:

```bash
npm run test:unit:problems
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add package.json docs/local-assessments.md README.md
git commit -m "docs: document local assessment reports"
```

---

### Task 15: Final Verification and Manual Smoke

**Files:**
- No new files.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: verified feature branch ready for review.

- [ ] **Step 1: Run focused assessment unit tests**

Run:

```bash
node --test tests/assessment-policy.test.mjs tests/assessment-contract.test.mjs tests/assessment-artifacts.test.mjs tests/assessment-staleness.test.mjs tests/assessment-report.test.mjs tests/assessment-codex-adapter.test.mjs tests/assessment-job-manager.test.mjs tests/assessment-local-service.test.mjs tests/assessment-view-model.test.mjs
```

Expected: pass.

- [ ] **Step 2: Run problem unit tests**

Run:

```bash
npm run test:unit:problems
```

Expected: pass.

- [ ] **Step 3: Run TypeScript and agent tests**

Run:

```bash
npm run test:unit
```

Expected: pass.

- [ ] **Step 4: Run the build**

Run:

```bash
npm run build
```

Expected: pass. Confirm `public/knowledge/` remains generated output and is not staged.

- [ ] **Step 5: Run browser tests**

Run:

```bash
npm run test:e2e
npm run test:e2e:assessment
```

Expected: both pass. `test:e2e:assessment` must use fake Codex and must not consume real Codex quota.

- [ ] **Step 6: Run repository-wide whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 7: Run one explicit manual smoke test with real Codex**

Only run this after the user confirms they are comfortable spending local Codex quota:

```bash
codex login status
make dev
```

Open a real local problem page, press `Run assessment`, wait up to 30 minutes, and verify that `problem.json` is unchanged, `assessment.json` validates, and `report.html` opens from the panel link.

- [ ] **Step 8: Commit final verification notes if documentation changed**

If the manual smoke test updates `docs/local-assessments.md` with a dated note, commit only that file:

```bash
git add docs/local-assessments.md
git commit -m "docs: record assessment smoke test"
```

---

## Self-Review Checklist

- Spec coverage: Tasks 1-3 cover skill integration, schema, structured output, scoring, verdicts, and cross-field validation. Tasks 4-6 cover immutable artifacts, input hashes, staleness, and deterministic HTML. Tasks 7-10 cover Codex CLI, preflight, FIFO service, token proxy, timeouts, and local-only execution. Tasks 11-13 cover page states, polling, rerun, report link, unavailable static output, and resolver selection. Tasks 14-15 cover documentation and verification.
- Placeholder scan: completed with zero matches for the forbidden planning patterns from `superpowers:writing-plans`.
- Type consistency: `runId`, `problemId`, `assessment`, `clarification`, `knowledgeResolution`, `computed.scores`, and `latest.reportHref` names are used consistently across service, store, contract, and UI tasks.
- Dependency note: implementation starts by merging PR #3's `assess-research-problem` skill before code tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-28-local-assessment-reports.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
