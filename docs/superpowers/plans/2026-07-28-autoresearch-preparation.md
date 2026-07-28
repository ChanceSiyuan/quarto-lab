# Autoresearch Preparation and Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the local background service and problem-page control that prepare, validate, and publish immutable autoresearch infrastructure revisions without starting research attempts.

**Architecture:** `make dev` starts a token-protected loopback autoresearch service beside vinext. A persistent two-slot scheduler runs preparation jobs in `.generated/autoresearch-jobs/`; a fresh Codex process may write only its staging workspace, and host-owned validators plus preflight publish a ready `problems/<id>/infrastructure/INF-NNN/` revision manifest-last. A client panel polls the service and renders the approved Research Loop visual language through a CSS module.

**Tech Stack:** Node.js >=22.13.0 ESM, native `node:test`, Next 16.2.6 App Router, React 19.2.6, Vite 8 development proxy, Codex CLI `exec`, native `node:http`, no new npm dependencies.

## Global Constraints

- Work only in the current `research-loop` checkout; external `quantum.harness` repositories are read-only migration input.
- Use test-first commits and do not combine unrelated repository repairs.
- Preserve `app/page.tsx`, `app/globals.css`, and `app/layout.tsx`; style the new detail-page surface with a focused CSS module.
- Keep `knowledge/**/*.qmd` as the only trusted content authority; preparation artifacts and problem records are never research-answer sources.
- Never publish `drafts/`, `literature/`, private evaluation data, raw Codex events, or local diagnostics to static Pages.
- Keep Sites project ID `appgprj_6a66e89526a88191a9e969c6f441086c` unchanged.
- Listen only on `127.0.0.1`; the development proxy injects a random capability token that is never returned to browser JavaScript.
- Global active preparation/campaign concurrency is exactly 2; one problem may have only one queued, running, needs-input, or stopping job.
- `needs_input` releases its execution slot while retaining the per-problem reservation.
- Preparation never edits `problem.json` and never creates an attempt or batch.
- Infrastructure IDs match `INF-\d{3}`, are never reused, and publish only after every preflight check passes.
- Spawn commands with argument arrays and `shell: false`; API callers cannot choose commands, paths, prompts, models, or environment variables.
- Every Codex render/preview or repository build remains outside candidate/infrastructure execution; ordinary indexing and rendering never execute generated source.

---

## File Structure

### New production files

- `schemas/autoresearch-preparation-output.schema.json` — strict final-message schema supplied to preparation Codex runs.
- `skills/prepare-autoresearch/SKILL.md` — staging-only preparation policy and structured-output contract.
- `lib/autoresearch/ids.mjs` — job/infrastructure ID validation and next-ID allocation.
- `lib/autoresearch/paths.mjs` — canonical roots and containment checks.
- `lib/autoresearch/preparation-contract.mjs` — host validation for preparation envelopes, questions, commands, data manifests, file hashes, and infrastructure manifests.
- `lib/autoresearch/process.mjs` — fakeable `spawn` runner with timeout, bounded termination, stdout/stderr capture, and `shell: false`.
- `lib/autoresearch/codex-preparation.mjs` — Codex preflight, prompt construction, invocation, JSONL parsing, and final-message validation.
- `lib/autoresearch/preflight.mjs` — host-owned infrastructure integrity, baseline, negative-candidate, isolation, and clean-rebuild checks.
- `lib/autoresearch/artifact-store.mjs` — job staging, immutable events, atomic state files, manifest-last infrastructure publication, and revision listing.
- `lib/autoresearch/job-store.mjs` — persistent job records, transitions, startup interruption recovery, and lineage.
- `lib/autoresearch/scheduler.mjs` — FIFO two-slot scheduler and per-problem reservation.
- `lib/autoresearch/preparation-worker.mjs` — scaffold → benchmark → datasets → preflight orchestration.
- `lib/autoresearch/local-service.mjs` — capability-protected loopback HTTP API.
- `lib/autoresearch/view-model.mjs` — pure preparation-panel state and copy projection.
- `scripts/local-autoresearch-service.mjs` — standalone local service entrypoint.
- `app/problems/[id]/autoresearch-panel.tsx` — client polling, prepare, input, retry, and unavailable UI.
- `app/problems/[id]/autoresearch-panel.module.css` — approved detail-page styling without global CSS changes.
- `docs/local-autoresearch.md` — operator setup, private-root contract, troubleshooting, and static limitation.

### Modified production files

- `scripts/dev-problem-index.mjs` — supervise the local service and vinext together.
- `vite.config.ts` — conditional `/__local/autoresearch/*` proxy with capability injection.
- `app/problems/[id]/page.tsx` — place the panel after every eligible local problem header.
- `package.json` — service and focused test scripts.
- `Makefile` — stable manual service command and help text.
- `README.md` — local preparation workflow and new local-only backend phase.
- `AGENTS.md` — replace the obsolete no-autonomous-backend statement with the narrow approved local authority.
- `docs/skills.md` — document the new local skill and command ownership.
- `tests/agent/skill-contracts.test.ts` — enforce the skill's staging, trust, structured-output, and no-fabrication clauses.

### New tests

- `tests/autoresearch-preparation-contract.test.mjs`
- `tests/autoresearch-paths.test.mjs`
- `tests/autoresearch-process.test.mjs`
- `tests/autoresearch-codex-preparation.test.mjs`
- `tests/autoresearch-preflight.test.mjs`
- `tests/autoresearch-artifact-store.test.mjs`
- `tests/autoresearch-job-store.test.mjs`
- `tests/autoresearch-scheduler.test.mjs`
- `tests/autoresearch-preparation-worker.test.mjs`
- `tests/autoresearch-local-service.test.mjs`
- `tests/autoresearch-view-model.test.mjs`
- `tests/e2e/local-autoresearch-preparation.spec.ts`
- `playwright.autoresearch.config.ts`

---

### Task 1: Preparation Skill and Structured Output Schema

**Files:**
- Create: `skills/prepare-autoresearch/SKILL.md`
- Create: `schemas/autoresearch-preparation-output.schema.json`
- Modify: `tests/agent/skill-contracts.test.ts`
- Test: `tests/autoresearch-preparation-contract.test.mjs`

**Interfaces:**
- Produces schema outcomes `prepared` and `needs_input`.
- Produces one blocking question shape `{ id, prompt, answerType, choices }` where `answerType` is `text` or `choice` and `choices` is non-empty only for `choice`.
- Produces prepared metadata `{ summary, manifestPath: "infrastructure.json" }`; files themselves are written only inside the supplied staging root.

- [ ] **Step 1: Add failing skill-contract assertions**

Add `prepare-autoresearch` to the existing skill-name table and require these body clauses:

```ts
const PREPARE_AUTORESEARCH: readonly Clause[] = [
  { requirement: "writes only staging", in: "body", pattern: /write only[^.]*staging/i },
  { requirement: "does not create attempts", in: "body", pattern: /never create[^.]*attempt/i },
  { requirement: "does not fabricate domain authority", in: "body", pattern: /never fabricate[^.]*metric|correctness rule|private dataset/i },
  { requirement: "uses one blocking question", in: "body", pattern: /exactly one blocking question/i },
  { requirement: "returns structured output", in: "body", pattern: /structured output schema/i },
  { requirement: "keeps private data outside the candidate tree", in: "body", pattern: /private[^.]*outside[^.]*candidate/i },
];
```

- [ ] **Step 2: Run the skill tests and verify failure**

Run:

```bash
npm run test:unit
```

Expected: FAIL because `skills/prepare-autoresearch/SKILL.md` and its contract entry do not exist.

- [ ] **Step 3: Add the strict output schema**

Create a draft-2020-12 JSON schema with `additionalProperties: false` at every object level and this required envelope:

```json
{
  "outcome": "prepared",
  "summary": "Prepared an executable benchmark campaign.",
  "manifestPath": "infrastructure.json",
  "question": null
}
```

For `needs_input`, require `manifestPath: null` and exactly one question:

```json
{
  "outcome": "needs_input",
  "summary": "A domain decision is required.",
  "manifestPath": null,
  "question": {
    "id": "primary-metric",
    "prompt": "Which independently verifiable metric should rank candidates?",
    "answerType": "text",
    "choices": []
  }
}
```

Use `oneOf` to make these two shapes mutually exclusive. IDs match `^[a-z][a-z0-9-]{0,63}$`; prompts and summaries have `minLength: 1`; choice questions require 2–8 distinct non-empty choices.

- [ ] **Step 4: Write the skill**

The skill must state, verbatim in substance:

```md
Run only inside the host-provided autoresearch staging directory. Write only
staging files. Never edit `problems/`, `knowledge/`, `drafts/`, `literature/`,
or repository configuration. Never create a batch or attempt.

Build the candidate contract, public checks, independent verifier, scoring,
baseline, dataset manifests, resource policy, environment lock, and focused
anti-gaming tests. Never fabricate a domain-valid metric, correctness rule, or
private dataset. When one material decision is missing, return `needs_input`
with exactly one blocking question.

Raw development and blind cases remain outside the candidate workspace. Store
only safe manifests and digests in staging. When invoked with the structured
output schema, return exactly one matching JSON object.
```

- [ ] **Step 5: Add schema-shape tests and run them**

In `tests/autoresearch-preparation-contract.test.mjs`, load the JSON schema and statically assert its required fields, mutually exclusive outcomes, ID patterns, choice bounds, and `additionalProperties: false` recursively. Task 2 extends this same file with host-side validation cases after the host validator exists.

Run:

```bash
node --test tests/autoresearch-preparation-contract.test.mjs
npm run test:unit
```

Expected: the static schema and skill tests PASS.

- [ ] **Step 6: Commit the skill and schema**

```bash
git add skills/prepare-autoresearch/SKILL.md schemas/autoresearch-preparation-output.schema.json tests/agent/skill-contracts.test.ts tests/autoresearch-preparation-contract.test.mjs
git commit -m "feat: define autoresearch preparation contract"
```

---

### Task 2: IDs, Paths, and Host Contracts

**Files:**
- Create: `lib/autoresearch/ids.mjs`
- Create: `lib/autoresearch/paths.mjs`
- Create: `lib/autoresearch/preparation-contract.mjs`
- Test: `tests/autoresearch-paths.test.mjs`
- Modify: `tests/autoresearch-preparation-contract.test.mjs`

**Interfaces:**
- Produces `JOB_ID_PATTERN`, `INFRASTRUCTURE_ID_PATTERN`, `isProblemId`, `nextInfrastructureId(existingNames)`.
- Produces `createAutoresearchPaths(rootDir)` with `jobsRoot`, `workspacesRoot`, `problemRoot(id)`, `infrastructureRoot(id)`, `revisionRoot(id, revisionId)` and `assertContained(path, root)`.
- Produces `PreparationContractError { code, errors }`.
- Produces `validatePreparationEnvelope(value)` and `validateInfrastructureManifest(value, context)`.

- [ ] **Step 1: Write failing path and ID tests**

Cover:

```js
assert.equal(nextInfrastructureId(["INF-001", "broken", "INF-003"]), "INF-004");
assert.equal(paths.revisionRoot("Prob-007", "INF-004"), join(root, "problems", "Prob-007", "infrastructure", "INF-004"));
assert.throws(() => paths.revisionRoot("../escape", "INF-001"), /problem ID/i);
assert.throws(() => assertContained(join(root, "outside"), paths.jobsRoot), /outside/i);
```

Also create a symlink from a nominal job path to an outside directory and require canonical containment to reject it.

- [ ] **Step 2: Run path tests and verify failure**

```bash
node --test tests/autoresearch-paths.test.mjs
```

Expected: FAIL with missing `lib/autoresearch/ids.mjs`.

- [ ] **Step 3: Implement IDs and canonical path helpers**

Use exact patterns:

```js
export const JOB_ID_PATTERN = /^ARJ-\d{8}T\d{6}Z-[a-f0-9]{8}$/;
export const INFRASTRUCTURE_ID_PATTERN = /^INF-(\d{3})$/;
export const PROBLEM_ID_PATTERN = /^Prob-\d{3}$/;
```

Resolve roots with `realpath` for existing parents and `resolve` plus `relative` for not-yet-created children. Reject absolute user fragments, `..`, symlinks, non-directory parents, and mismatched IDs before reads or writes.

- [ ] **Step 4: Add failing host-contract cases**

Test a valid infrastructure manifest shaped as:

```js
const manifest = {
  schemaVersion: 1,
  kind: "autoresearch-infrastructure",
  problemId: "Prob-007",
  id: "INF-001",
  status: "ready",
  candidate: { templatePath: "candidate-template/candidate.py", writablePaths: ["candidate.py"] },
  objective: { metricId: "normalized-quality", label: "Normalized quality", direction: "maximize", acceptanceThreshold: 0.7 },
  commands: {
    publicCheck: ["python3", "public/check.py"],
    containmentCheck: ["python3", "tests/containment.py"],
    evaluateDevelopment: ["python3", "evaluator/development.py"],
    reproduceBaseline: ["python3", "baselines/run.py"]
  },
  datasets: {
    public: { manifestPath: "datasets/public.json", digest: "a".repeat(64) },
    development: { manifestPath: "datasets/development.json", digest: "b".repeat(64) },
    blind: { manifestPath: "datasets/blind.json", digest: "c".repeat(64) }
  },
  resources: { attemptTimeoutSeconds: 300, terminationGraceSeconds: 5, memoryMb: 4096, network: "denied" },
  files: [{ path: "candidate-template/candidate.py", sha256: "d".repeat(64), size: 12, executable: false }],
  createdAt: "2026-07-28T08:00:00.000Z"
};
```

Reject unknown fields, unsafe/duplicate paths, writable paths outside the candidate workspace, invalid metric IDs, direction outside `maximize|minimize`, non-finite thresholds, empty command arrays, command arguments containing NUL, bad digests, non-positive limits, `network` outside `denied|restricted`, duplicate files, missing manifest-listed entrypoints, and a manifest whose IDs disagree with context.

- [ ] **Step 5: Implement strict manual validation**

Implement field allowlists and cross-field checks without adding a validation dependency. Return a frozen normalized clone on success; throw `PreparationContractError` containing every diagnostic on failure. `validatePreparationEnvelope` enforces the same `prepared`/`needs_input` exclusivity as the JSON schema.

- [ ] **Step 6: Run focused tests**

```bash
node --test tests/autoresearch-paths.test.mjs tests/autoresearch-preparation-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit IDs, paths, and contracts**

```bash
git add lib/autoresearch/ids.mjs lib/autoresearch/paths.mjs lib/autoresearch/preparation-contract.mjs tests/autoresearch-paths.test.mjs tests/autoresearch-preparation-contract.test.mjs
git commit -m "feat: validate autoresearch infrastructure contracts"
```

---

### Task 3: Process Runner and Preparation Codex Adapter

**Files:**
- Create: `lib/autoresearch/process.mjs`
- Create: `lib/autoresearch/codex-preparation.mjs`
- Test: `tests/autoresearch-process.test.mjs`
- Test: `tests/autoresearch-codex-preparation.test.mjs`

**Interfaces:**
- Produces `runProcess({ command, args, cwd, env, timeoutMs, graceMs, onStdoutLine, spawnFn, killFn }): Promise<ProcessResult>`.
- Produces `preflightPreparationCodex({ codexPath, skillPath, schemaPath, processRunner })`.
- Produces `buildPreparationPrompt({ problem, problemMarkdown, answers })`.
- Produces `runPreparationCodex({ codexPath, stageDir, problem, problemMarkdown, answers, schemaPath, processRunner }): Promise<PreparationEnvelope>`.

- [ ] **Step 1: Write process-runner failure tests**

Use fake `EventEmitter` children to prove:

- `shell` is exactly `false`;
- stdout and stderr are captured separately with byte limits;
- JSONL callbacks receive complete lines across chunk boundaries;
- nonzero exit returns a typed `ProcessExecutionError`;
- timeout sends `SIGTERM`, waits exactly `graceMs`, then sends `SIGKILL`;
- caller-supplied environment is copied from an allowlist rather than inheriting request data.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-process.test.mjs
```

Expected: FAIL with missing process module.

- [ ] **Step 3: Implement the bounded process runner**

Set fixed defaults:

```js
export const MAX_STDOUT_BYTES = 4 * 1024 * 1024;
export const MAX_STDERR_BYTES = 1 * 1024 * 1024;
export const DEFAULT_TERMINATION_GRACE_MS = 5_000;
```

Use `spawn(command, args, { cwd, env, shell: false, stdio: ["ignore", "pipe", "pipe"] })`. Reject output-limit overflow, preserve the exit code and signal, and clear every timer/listener in `finally`.

- [ ] **Step 4: Write failing Codex-adapter tests**

Assert the exact invocation:

```js
[
  "exec",
  "--sandbox", "workspace-write",
  "--ephemeral",
  "--json",
  "--output-schema", schemaPath,
  "--output-last-message", join(stageDir, ".preparation-result.json"),
  prompt
]
```

Require `cwd === stageDir`; reject absent `codex`, failed `codex login status`, malformed JSONL, missing final message, invalid envelope, and a final message larger than 256 KiB. Verify that problem text is delimited as untrusted input and that answers are serialized as JSON, not interpolated as instructions.

- [ ] **Step 5: Implement Codex preflight and adapter**

`preflightPreparationCodex` runs `<codex> --version` and `<codex> login status` with a 15-second timeout. `runPreparationCodex` reads only the host-owned last-message file, parses it once, validates it with `validatePreparationEnvelope`, and returns the normalized value. JSONL is retained only as diagnostic events, never as authoritative output.

- [ ] **Step 6: Run focused tests**

```bash
node --test tests/autoresearch-process.test.mjs tests/autoresearch-codex-preparation.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit the adapter**

```bash
git add lib/autoresearch/process.mjs lib/autoresearch/codex-preparation.mjs tests/autoresearch-process.test.mjs tests/autoresearch-codex-preparation.test.mjs
git commit -m "feat: run isolated autoresearch preparation jobs"
```

---

### Task 4: Staging and Manifest-Last Infrastructure Publication

**Files:**
- Create: `lib/autoresearch/artifact-store.mjs`
- Test: `tests/autoresearch-artifact-store.test.mjs`

**Interfaces:**
- Produces `createPreparationStage({ rootDir, jobId, problemId })`.
- Produces `appendEvent({ stageDir, event })` and `writeAtomicJson(path, value)`.
- Produces `publishInfrastructureRevision({ rootDir, stageDir, problemId, expectedRevisionId, validateManifest, rebuildIndex })`.
- Produces `listInfrastructureRevisions({ rootDir, problemId })` and `readLatestReadyInfrastructure(...)`.

- [ ] **Step 1: Write failing artifact tests**

Test that `createPreparationStage` creates only:

```text
.generated/autoresearch-jobs/<job-id>/
  job.json
  events.jsonl
  stderr.log
  workspace/
```

Test exclusive creation, 0600 state/log files where supported, newline-delimited event append, atomic JSON replacement, sorted revision listing, and refusal of symlinked roots.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-artifact-store.test.mjs
```

Expected: FAIL with missing artifact-store module.

- [ ] **Step 3: Add manifest-last publication tests**

Inject file-operation failures and assert this order:

1. exclusive target `problems/Prob-007/infrastructure/INF-001`;
2. copy all regular files except `infrastructure.json`;
3. copy the validated manifest as `.infrastructure.json.tmp`;
4. rename it to `infrastructure.json` last;
5. return `published-index-stale` rather than deleting a published revision if index refresh fails.

Refuse existing targets, missing manifest-listed files, extra unlisted executable files, symlinks, special files, changed hashes, files over 16 MiB, total revisions over 512 MiB, and any source outside the job workspace.

- [ ] **Step 4: Implement the artifact store**

Reuse the behavioral pattern of `lib/problems/draft-publisher.mjs` but keep the module independent. Copy with explicit safe relative paths; never recurse through unvalidated directory entries. Cleanup only a target this call exclusively created and only before manifest publication.

- [ ] **Step 5: Run focused tests**

```bash
node --test tests/autoresearch-artifact-store.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit publication support**

```bash
git add lib/autoresearch/artifact-store.mjs tests/autoresearch-artifact-store.test.mjs
git commit -m "feat: publish frozen autoresearch infrastructure"
```

---

### Task 5: Host-Owned Preflight

**Files:**
- Create: `lib/autoresearch/preflight.mjs`
- Test: `tests/autoresearch-preflight.test.mjs`

**Interfaces:**
- Produces `PREFLIGHT_CHECK_IDS` as a stable ordered array.
- Produces `runInfrastructurePreflight({ stageDir, manifest, privateDataRoot, processRunner, now }): Promise<PreflightReport>`.
- Produces report `{ schemaVersion: 1, problemId, infrastructureId, status, startedAt, completedAt, attemptRuntimeUpperBoundSeconds, checks }`.

- [ ] **Step 1: Write failing preflight tests**

Require these stable check IDs in order:

```js
[
  "manifest-integrity",
  "clean-environment",
  "candidate-api",
  "public-smoke",
  "correctness-negative",
  "hard-code-negative",
  "crash-negative",
  "timeout-negative",
  "containment",
  "private-data-isolation",
  "baseline-reproduction",
  "score-arithmetic",
  "reproducibility"
]
```

Use fixture commands that write deterministic JSON. Assert that every command uses `shell: false`, the stage workspace as cwd, a fixed environment, and the manifest timeout. Missing development/blind roots, digest mismatch, candidate access to a canary, score mismatch, successful hard-coded candidate, or baseline drift makes status `failed`.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-preflight.test.mjs
```

Expected: FAIL with missing preflight module.

- [ ] **Step 3: Implement deterministic check execution**

Each check returns:

```js
{ id, status: "passed" | "failed", durationMs, summary, diagnostics: [] }
```

Stop after an integrity or containment failure; run all safe semantic checks so one report exposes multiple benchmark defects. Escape and length-limit diagnostics. Compute `attemptRuntimeUpperBoundSeconds` only from the validated resource limit plus fixed evaluator overhead; use `null` when no trustworthy bound exists.

- [ ] **Step 4: Prove private material stays outside artifacts**

Add a fixture whose private data contains a unique canary. After preflight, recursively read the staged publishable tree and report JSON and assert the canary is absent. Assert the candidate command receives no private-root path or environment variable while the evaluator receives one read-only path through the host runner API.

- [ ] **Step 5: Run focused tests**

```bash
node --test tests/autoresearch-preflight.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit preflight**

```bash
git add lib/autoresearch/preflight.mjs tests/autoresearch-preflight.test.mjs
git commit -m "feat: preflight autoresearch benchmarks"
```

---

### Task 6: Persistent Job Store and Two-Slot Scheduler

**Files:**
- Create: `lib/autoresearch/job-store.mjs`
- Create: `lib/autoresearch/scheduler.mjs`
- Test: `tests/autoresearch-job-store.test.mjs`
- Test: `tests/autoresearch-scheduler.test.mjs`

**Interfaces:**
- Produces `PREPARATION_STATES` and transition validation.
- Produces `createJobStore({ rootDir, now, randomBytes })` with `create`, `read`, `transition`, `appendEvent`, `list`, and `recoverInterrupted`.
- Produces `createScheduler({ concurrency: 2, runJob })` with `enqueue`, `resumeAfterInput`, `snapshot`, and `shutdown`.

- [ ] **Step 1: Write failing job-store tests**

Use the exact state set:

```js
["queued", "scaffolding", "building_benchmark", "preparing_datasets", "preflight", "needs_input", "ready", "failed", "interrupted"]
```

Test valid transitions, rejection of skipped/backward transitions, immutable lineage, atomic `job.json`, monotonic sequence numbers in `events.jsonl`, and startup conversion of nonterminal executing states to `interrupted`. `ready`, `failed`, and `interrupted` are terminal; `needs_input` is suspended.

- [ ] **Step 2: Write failing scheduler tests**

With controllable promises, assert:

- only two different problems run simultaneously;
- a third waits FIFO;
- the same problem deduplicates to its active job;
- `needs_input` releases one slot but keeps the problem reserved;
- answering queues a child execution behind already queued work;
- shutdown starts no new work and waits for the worker termination hook.

- [ ] **Step 3: Run and verify failure**

```bash
node --test tests/autoresearch-job-store.test.mjs tests/autoresearch-scheduler.test.mjs
```

Expected: FAIL with missing modules.

- [ ] **Step 4: Implement persistence and scheduling**

Use explicit per-problem maps and a FIFO array; do not infer ownership from promises. `snapshot()` returns only JSON-safe public state:

```js
{
  concurrency: 2,
  active: [{ jobId, problemId, kind, state }],
  queued: [{ jobId, problemId, position }]
}
```

Never expose filesystem paths, prompts, tokens, stderr content, or environment values.

- [ ] **Step 5: Run focused tests**

```bash
node --test tests/autoresearch-job-store.test.mjs tests/autoresearch-scheduler.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit job persistence and scheduling**

```bash
git add lib/autoresearch/job-store.mjs lib/autoresearch/scheduler.mjs tests/autoresearch-job-store.test.mjs tests/autoresearch-scheduler.test.mjs
git commit -m "feat: schedule local autoresearch preparation"
```

---

### Task 7: Preparation Worker Orchestration

**Files:**
- Create: `lib/autoresearch/preparation-worker.mjs`
- Test: `tests/autoresearch-preparation-worker.test.mjs`

**Interfaces:**
- Produces `createPreparationWorker({ rootDir, privateDataRoot, codexAdapter, preflightRunner, artifactStore, jobStore, rebuildIndex })`.
- Worker consumes `{ jobId, problemId, answers }` and returns `{ state, infrastructureId?, question? }`.

- [ ] **Step 1: Write failing orchestration tests**

Build fakes for each dependency and assert the exact successful order:

```text
read and validate problem
create staging workspace
scaffolding
building_benchmark
preparing_datasets
run Codex
validate manifest
preflight
write preflight-report.json
publish INF-NNN
ready
```

Assert that a Codex `needs_input` envelope stores exactly one question, releases through scheduler state, publishes no infrastructure, and a child answer retains lineage and reuses only the same validated staging snapshot. Reject `draft`, `rejected`, `archived`, `solved`, `publishing`, and `published` problems; allow `qualifying` and `accepted`.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-preparation-worker.test.mjs
```

Expected: FAIL with missing worker.

- [ ] **Step 3: Implement the worker**

Read `problem.json` and `problem.md` through `createProblemRepository` inputs, then revalidate with `validateProblemManifest`. Allocate the next infrastructure ID from directory names before Codex runs and re-check immediately before exclusive publication. A collision fails this job with an actionable diagnostic; it never silently changes the previewed revision.

- [ ] **Step 4: Add failure and recovery coverage**

Cover Codex preflight failure, invalid output, invalid manifest, failed host preflight, revision collision, publication copy failure, and stale index. A stale index still returns state `ready` and exposes the published revision, while adding only a bounded internal diagnostic `{ code: "ready-index-stale" }`; it is not a ninth preparation state. No failure path edits `problem.json` or creates `attempts/` or `batches/`.

- [ ] **Step 5: Run focused tests**

```bash
node --test tests/autoresearch-preparation-worker.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit the preparation worker**

```bash
git add lib/autoresearch/preparation-worker.mjs tests/autoresearch-preparation-worker.test.mjs
git commit -m "feat: orchestrate autoresearch preparation"
```

---

### Task 8: Loopback Service, Proxy, and Development Supervision

**Files:**
- Create: `lib/autoresearch/local-service.mjs`
- Create: `scripts/local-autoresearch-service.mjs`
- Modify: `scripts/dev-problem-index.mjs`
- Modify: `vite.config.ts`
- Modify: `package.json`
- Modify: `Makefile`
- Test: `tests/autoresearch-local-service.test.mjs`
- Modify: `tests/dev-problem-index.test.mjs`

**Interfaces:**
- Produces `startLocalAutoresearchService({ rootDir, host: "127.0.0.1", port: 0, token, scheduler, jobStore }): Promise<{ origin, token, close }>`.
- Exposes preparation routes from the design and `GET /health` internally.
- `scripts/dev-problem-index.mjs` passes `AUTORESEARCH_SERVICE_ORIGIN` and `AUTORESEARCH_CAPABILITY_TOKEN` only to the vinext child process.

- [ ] **Step 1: Write failing HTTP tests**

Start the service on port 0 and assert:

- non-loopback host input is rejected;
- missing/wrong `x-research-loop-capability` returns 403;
- unknown routes return JSON 404;
- bodies over 16 KiB return 413;
- malformed JSON returns 400;
- IDs and answer IDs are validated before worker calls;
- duplicate prepare returns the same active job;
- status responses omit token, paths, prompts beyond the active public question, raw events, and stderr;
- log download uses `text/plain; charset=utf-8` plus attachment headers.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-local-service.test.mjs
```

Expected: FAIL with missing service.

- [ ] **Step 3: Implement routes and error envelopes**

Use this stable error shape:

```json
{ "error": { "code": "INVALID_REQUEST", "message": "problemId must match Prob-###." } }
```

Implement:

```text
POST /__local/autoresearch/problems/{id}/prepare
GET  /__local/autoresearch/problems/{id}
POST /__local/autoresearch/jobs/{job-id}/input
GET  /__local/autoresearch/jobs/{job-id}
GET  /__local/autoresearch/logs/{problem-id}/{job-id}
```

Use exact-method checks and `Cache-Control: no-store` on every response.

- [ ] **Step 4: Add failing supervisor and proxy tests**

Extend `tests/dev-problem-index.test.mjs` with injected `startService` and `spawnFn`. Assert service starts before vinext, environment includes only origin/token additions, both children close on SIGINT/SIGTERM, and service-start failure prevents vinext from launching.

Export a pure `buildAutoresearchProxy({ origin, token })` from `vite.config.ts` or a new focused `build/autoresearch-vite-proxy.ts` so a test can assert only `/__local/autoresearch` is proxied and the capability header is overwritten, never forwarded from the browser.

- [ ] **Step 5: Implement supervision and proxy wiring**

Keep `main()` dependency-injectable. In build/static environments where origin/token are absent, return no proxy config. Add:

```json
"autoresearch:service": "node scripts/local-autoresearch-service.mjs"
```

and a `make autoresearch-service` target for manual local diagnostics. Do not add a production start hook.

- [ ] **Step 6: Run focused tests**

```bash
node --test tests/autoresearch-local-service.test.mjs tests/dev-problem-index.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit service integration**

```bash
git add lib/autoresearch/local-service.mjs scripts/local-autoresearch-service.mjs scripts/dev-problem-index.mjs vite.config.ts package.json Makefile tests/autoresearch-local-service.test.mjs tests/dev-problem-index.test.mjs
git commit -m "feat: serve local autoresearch preparation jobs"
```

---

### Task 9: Preparation Panel and Approved Visual States

**Files:**
- Create: `lib/autoresearch/view-model.mjs`
- Create: `app/problems/[id]/autoresearch-panel.tsx`
- Create: `app/problems/[id]/autoresearch-panel.module.css`
- Modify: `app/problems/[id]/page.tsx`
- Test: `tests/autoresearch-view-model.test.mjs`
- Modify: `tests/problem-routes-research.test.mjs`

**Interfaces:**
- Produces `buildPreparationPanelState({ problem, serviceState, localMode })`.
- Produces `<AutoresearchPanel problemId initialEligibility staticMode />`.
- Panel polls `GET /__local/autoresearch/problems/{id}` and posts only fixed actions.

- [ ] **Step 1: Write failing view-model tests**

Assert exact primary labels for `not_prepared`, `queued`, executing states, `needs_input`, `failed`, `ready`, `interrupted`, and `unavailable`. Assert `qualifying` and `accepted` are eligible, synthetic `Prob-000` and solved/rejected/archived/published records are unavailable, and no state exposes hidden diagnostics or private paths.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-view-model.test.mjs
```

Expected: FAIL with missing view model.

- [ ] **Step 3: Implement the pure view model**

Return a stable shape:

```js
{
  kind: "ready",
  eyebrow: "AUTORESEARCH INFRASTRUCTURE",
  title: "Ready to start",
  body: "INF-003 passed all preflight checks.",
  primary: { label: "Start autoresearch", action: "start", disabled: true },
  metadata: [{ label: "Revision", value: "INF-003" }],
  pollAfterMs: null
}
```

Use 1,000 ms polling for queued/executing state, 5,000 ms for unavailable retry, and no polling for ready/failed/needs-input/interrupted until user action.

- [ ] **Step 4: Add component route assertions**

Extend route-source tests to require the panel after each real problem header and before `research-metric-strip` or `detail-panel`. Require static example props to disable active calls. Assert imports use the CSS module and that `app/globals.css`, `app/page.tsx`, and `app/layout.tsx` remain unchanged from the task's starting commit.

- [ ] **Step 5: Implement the client panel**

Use native buttons, a `<form>` for one text/choice question, `AbortController` on unmount, request sequence IDs to ignore stale polls, `aria-live="polite"` for status, and existing focus behavior. The CSS module copies existing variables and geometry through `var(--paper)`, `var(--surface)`, `var(--line)`, `var(--green)`, and mono font variables; use square borders and no shadows or radii.

In PR 1, the ready state's `Start autoresearch` is visible but disabled with supporting copy `Campaign execution is added in the next implementation phase.` This makes prepared infrastructure independently inspectable without pretending PR 2 exists.

- [ ] **Step 6: Run focused UI tests**

```bash
node --test tests/autoresearch-view-model.test.mjs tests/problem-routes-research.test.mjs
npm run lint
```

Expected: PASS.

- [ ] **Step 7: Commit the preparation UI**

```bash
git add lib/autoresearch/view-model.mjs 'app/problems/[id]/autoresearch-panel.tsx' 'app/problems/[id]/autoresearch-panel.module.css' 'app/problems/[id]/page.tsx' tests/autoresearch-view-model.test.mjs tests/problem-routes-research.test.mjs
git commit -m "feat: add autoresearch preparation control"
```

---

### Task 10: Documentation, Phase Boundary, and Static Safety

**Files:**
- Create: `docs/local-autoresearch.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/skills.md`
- Modify: `package.json`
- Modify: `tests/pages-showcase.test.mjs`
- Modify: `tests/built-static-assets.test.mjs`

**Interfaces:**
- Documents `AUTORESEARCH_PRIVATE_ROOT` as an operator-owned absolute directory used only by the evaluator/preflight host.
- Documents `make dev` and `make autoresearch-service`; no production or Pages execution command is added.

- [ ] **Step 1: Add failing static-safety tests**

After `npm run pages:build`, recursively scan `out/` and assert absence of:

```text
/__local/autoresearch
AUTORESEARCH_CAPABILITY_TOKEN
AUTORESEARCH_PRIVATE_ROOT
infrastructure.json
preflight-report.json
events.jsonl
stderr.log
```

Allow only the literal noninteractive copy `Available in local mode`. Assert `examples/showcase/problems/Prob-000` remains the only problem source copied into Pages.

- [ ] **Step 2: Run and verify failure before documentation/wiring completion**

```bash
npm run test:pages
```

Expected: FAIL if active panel markup or service configuration leaks into the snapshot; otherwise the new explicit assertions should initially fail because their expected unavailable copy is absent.

- [ ] **Step 3: Write operator documentation**

Document:

- local-only architecture and loopback token;
- preparation states and one-question needs-input behavior;
- private root ownership and permissions;
- public/development/blind separation;
- where staging and ready revisions live;
- preflight checks and failure recovery;
- how to inspect logs without publishing them;
- how shutdown marks interrupted work;
- static Pages limitation; and
- that PR 1 prepares but does not start attempts.

- [ ] **Step 4: Update the agent and skill boundaries explicitly**

Replace only the obsolete autonomous-backend sentence in `AGENTS.md` with:

```md
- The only autonomous backend is the local loopback autoresearch sidecar.
  It may write `.generated/autoresearch-*` staging and, after host validation,
  `problems/<id>/infrastructure/`. It must not write trusted knowledge, publish
  private data, expose a deployed execution route, or start a campaign without
  the user's separate problem-page confirmation.
```

Add the `prepare-autoresearch` skill ownership and prohibit it from writing official problem records directly. Update README's `Not in this phase` section to say there is no remote/cloud queue, D1/R2 model, or deployed autonomous service.

- [ ] **Step 5: Register focused tests**

Add every PR 1 `.mjs` test to `test:unit:problems` and add:

```json
"test:autoresearch:preparation": "node --test tests/autoresearch-preparation-contract.test.mjs tests/autoresearch-paths.test.mjs tests/autoresearch-process.test.mjs tests/autoresearch-codex-preparation.test.mjs tests/autoresearch-preflight.test.mjs tests/autoresearch-artifact-store.test.mjs tests/autoresearch-job-store.test.mjs tests/autoresearch-scheduler.test.mjs tests/autoresearch-preparation-worker.test.mjs tests/autoresearch-local-service.test.mjs tests/autoresearch-view-model.test.mjs"
```

Keep existing scripts unchanged except for the appended focused coverage.

- [ ] **Step 6: Run documentation and static gates**

```bash
npm run test:unit
npm run test:unit:problems
npm run test:pages
git diff --check
```

Expected: PASS.

- [ ] **Step 7: Commit docs and static safety**

```bash
git add docs/local-autoresearch.md README.md AGENTS.md docs/skills.md package.json tests/pages-showcase.test.mjs tests/built-static-assets.test.mjs
git commit -m "docs: define local autoresearch preparation boundary"
```

---

### Task 11: Fake End-to-End Preparation Flow and Full Verification

**Files:**
- Create: `playwright.autoresearch.config.ts`
- Create: `tests/e2e/local-autoresearch-preparation.spec.ts`
- Create: `tests/fixtures/autoresearch/fake-codex.mjs`
- Create: `tests/fixtures/autoresearch/fake-private/README.fixture`
- Modify: `package.json`

**Interfaces:**
- Produces `npm run test:e2e:autoresearch` using an isolated temporary fixture root, fake Codex path, fake private root, and the real loopback service/UI.

- [ ] **Step 1: Write the failing browser scenario**

The scenario must:

1. create one qualifying `Prob-001` fixture;
2. open its local problem page;
3. click `Prepare autoresearch`;
4. observe queued/executing status;
5. receive one `needs_input` metric question;
6. submit a concrete fixture answer;
7. observe preflight reach `Ready`;
8. assert `INF-001/infrastructure.json` exists and validates;
9. assert no `attempts/`, `batches/`, or `problem.json` mutation occurred;
10. reload and confirm ready state is reconstructed from disk; and
11. assert the ready `Start autoresearch` action is disabled in PR 1.

- [ ] **Step 2: Run and verify failure**

```bash
npx playwright test -c playwright.autoresearch.config.ts
```

Expected: FAIL until the fake Codex fixture and test service wiring exist.

- [ ] **Step 3: Implement deterministic fake Codex behavior**

The executable accepts the adapter's exact arguments, writes JSONL progress, returns `needs_input` on the first lineage execution, and on the child execution creates a minimal valid infrastructure workspace plus the prepared final envelope. It must fail if cwd is outside the supplied staging root or if unexpected arguments/env keys appear.

- [ ] **Step 4: Add the focused script and run browser verification**

Add:

```json
"test:e2e:autoresearch": "playwright test -c playwright.autoresearch.config.ts"
```

Run:

```bash
npm run test:e2e:autoresearch
```

Expected: PASS.

- [ ] **Step 5: Run full repository verification**

```bash
make build
make test
git diff --check
git status --short
```

Expected: build and all tests PASS. `git status` contains only intentional PR 1 changes; pre-existing user changes are reported and left untouched.

- [ ] **Step 6: Commit end-to-end coverage**

```bash
git add playwright.autoresearch.config.ts tests/e2e/local-autoresearch-preparation.spec.ts tests/fixtures/autoresearch/fake-codex.mjs tests/fixtures/autoresearch/fake-private/README.fixture package.json
git commit -m "test: verify autoresearch preparation end to end"
```

- [ ] **Step 7: Request code review before PR 1 handoff**

Invoke `superpowers:requesting-code-review`, address findings through the original task implementers, rerun `make test`, and only then use `superpowers:finishing-a-development-branch` to choose commit/push/PR handling.
