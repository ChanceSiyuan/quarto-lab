# Autoresearch Campaigns and Attempts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend preflight-passed infrastructure with bounded campaign execution that runs fresh isolated Codex attempts, evaluates them through the frozen host benchmark, and publishes each complete attempt as one live research-ledger row.

**Architecture:** The PR 1 sidecar and two-slot scheduler gain campaign jobs bound to one immutable infrastructure revision. Each attempt uses a clean `.generated/autoresearch-workspaces/<batch>/<attempt>/` directory and a new ephemeral Codex process; the host then runs frozen public, containment, and development evaluation commands, recomputes the decision, and publishes an immutable native attempt manifest-last. The existing problem and research indexes gain a native autoresearch union without changing imported AutoQEC records.

**Tech Stack:** Node.js >=22.13.0 ESM, native `node:test`, Next 16.2.6 App Router, React 19.2.6, Vite 8 local proxy, Codex CLI `exec`, native filesystem/process/HTTP APIs, no new npm dependencies.

## Global Constraints

- Begin only after the preparation/preflight plan is merged and its full test suite passes.
- Work only in the current `research-loop` checkout; preserve unrelated user changes.
- Use test-first commits and keep campaign work separate from unrelated assessment, knowledge, literature, and import changes.
- Preserve `app/page.tsx`, `app/globals.css`, and `app/layout.tsx`; extend only the focused autoresearch component/CSS module and problem routes.
- Keep `knowledge/**/*.qmd` as the only trusted answer source. Native attempts are experimental records, never trusted conclusions.
- Use a user-confirmed bounded count: default 20, minimum 1, maximum 200.
- Different problems may use both global slots; one problem may have only one active job. Attempts inside one batch are sequential.
- Every attempt uses a new ephemeral Codex run and a temporary non-Git workspace.
- API callers cannot choose commands, prompts, paths, models, environments, infrastructure contents, or private-data roots.
- Candidate processes cannot read repository internals, evaluator source outside the frozen revision, development/blind raw data, answer keys, salts, selection rules, credentials, or other attempt workspaces.
- Spawn with argument arrays and `shell: false`; enforce fixed timeouts, bounded output, and graceful then forced termination.
- Publish no partial attempt. Candidate failures become rejected attempts only when host evaluation remains trustworthy; infrastructure/evaluator integrity failures stop the batch.
- Graceful stop completes the active attempt and starts no next attempt. Restart recovery never silently resumes model execution.
- Completing a batch never marks a problem `solved`; it remains `solving` until a separate user decision.
- Static Pages never calls the local API and never contains native local attempts, candidates, infrastructure, batch logs, or private manifests.

---

## File Structure

### New production files

- `schemas/autoresearch-candidate-output.schema.json` — strict non-metric Codex final message for one candidate proposal.
- `lib/autoresearch/campaign-contract.mjs` — strict native research, batch, candidate-output, evaluation-output, and native-attempt validation.
- `lib/autoresearch/attempt-allocation.mjs` — safe native attempt and batch ID allocation from directories plus parseable manifests.
- `lib/autoresearch/attempt-workspace.mjs` — clean workspace creation, seed copying, before/after manifests, allowed-write enforcement, and cleanup.
- `lib/autoresearch/codex-attempt.mjs` — fixed attempt prompt and fresh ephemeral Codex invocation.
- `lib/autoresearch/evaluator.mjs` — frozen command runner, gate/result parsing, score verification, and host decision.
- `lib/autoresearch/attempt-publisher.mjs` — native research bootstrap and manifest-last attempt publication.
- `lib/autoresearch/campaign-store.mjs` — atomic batch state, events, stop requests, lifecycle start journal, and recovery.
- `lib/autoresearch/campaign-worker.mjs` — sequential bounded loop, best-candidate selection, compact learning summaries, stop, and resume.
- `lib/problems/native-research-presentation.mjs` — native ledger cards, rows, and attempt dossiers.
- `app/problems/[id]/autoresearch-start-dialog.tsx` — accessible count confirmation dialog.

### Modified production files

- `lib/autoresearch/ids.mjs` — batch/native-attempt IDs.
- `lib/autoresearch/local-service.mjs` — batch start/stop/resume/status routes.
- `lib/autoresearch/view-model.mjs` — campaign states and actions.
- `lib/problems/research-schema.mjs` — native-record union without weakening imported contracts.
- `lib/problems/research-indexer.mjs` — native research discovery, validation, and deterministic indexing.
- `lib/problems/research-presentation.mjs` — dispatch imported versus native presentation.
- `lib/problems/research-route-data.mjs` — native problem/attempt state dispatch.
- `scripts/dev-problem-index.mjs` — watch `research.json`, batch manifests, native attempt manifests, and infrastructure revisions.
- `app/problems/[id]/autoresearch-panel.tsx` — start dialog, progress, stop, resume, batch history, and route refresh.
- `app/problems/[id]/autoresearch-panel.module.css` — dialog and progress states in the approved style.
- `app/problems/[id]/page.tsx` — native ledger rendering through existing route state.
- `app/problems/[id]/attempts/[attemptId]/page.tsx` — native attempt dossier rendering.
- `package.json`, `README.md`, `docs/local-autoresearch.md` — scripts and operator workflow.

### New tests

- `tests/autoresearch-campaign-contract.test.mjs`
- `tests/autoresearch-attempt-allocation.test.mjs`
- `tests/autoresearch-attempt-workspace.test.mjs`
- `tests/autoresearch-codex-attempt.test.mjs`
- `tests/autoresearch-evaluator.test.mjs`
- `tests/autoresearch-attempt-publisher.test.mjs`
- `tests/autoresearch-campaign-store.test.mjs`
- `tests/autoresearch-campaign-worker.test.mjs`
- `tests/autoresearch-campaign-service.test.mjs`
- `tests/autoresearch-campaign-view-model.test.mjs`
- `tests/native-research-indexer.test.mjs`
- `tests/native-research-presentation.test.mjs`
- `tests/e2e/local-autoresearch-campaign.spec.ts`

---

### Task 1: Native Campaign, Candidate, Evaluation, and Attempt Contracts

**Files:**
- Create: `schemas/autoresearch-candidate-output.schema.json`
- Create: `lib/autoresearch/campaign-contract.mjs`
- Modify: `lib/autoresearch/ids.mjs`
- Test: `tests/autoresearch-campaign-contract.test.mjs`

**Interfaces:**
- Produces `BATCH_ID_PATTERN = /^BATCH-(\d{3,6})$/` and `NATIVE_ATTEMPT_ID_PATTERN = /^ATT-(\d{3,6})$/`.
- Produces `validateCandidateEnvelope`, `validateEvaluationOutput`, `validateBatchManifest`, `validateNativeResearchManifest`, and `validateNativeAttempt`.
- `validateBatchManifest(value, { problemId, knownBatchIds })` receives the store-owned parent-ID set needed for resume lineage checks; pure shape validation never scans the filesystem.
- Produces `CampaignContractError { code, errors }` with all cross-field diagnostics.

- [ ] **Step 1: Write failing contract tests**

Test this immutable native `research.json` shape:

```js
{
  schemaVersion: 1,
  kind: "native-autoresearch-record",
  problemId: "Prob-007",
  disclaimer: "Autoresearch experimental record - not reviewed knowledge.",
  createdAt: "2026-07-28T08:00:00.000Z"
}
```

Test this batch manifest shape:

```js
{
  schemaVersion: 1,
  kind: "autoresearch-batch",
  problemId: "Prob-007",
  id: "BATCH-001",
  infrastructureId: "INF-003",
  requestedAttempts: 20,
  completedAttemptIds: [],
  state: "queued",
  parentBatchId: null,
  stopRequestedAt: null,
  createdAt: "2026-07-28T08:01:00.000Z",
  updatedAt: "2026-07-28T08:01:00.000Z"
}
```

Reject attempt counts outside 1–200, duplicate completed IDs, completed counts above requested, invalid state/timestamp combinations, mismatched problem IDs, unknown fields, and a resume child whose parent is absent from `knownBatchIds`.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-campaign-contract.test.mjs
```

Expected: FAIL with missing campaign-contract module.

- [ ] **Step 3: Define the candidate output schema**

Use mutually exclusive outcomes:

```json
{
  "outcome": "candidate",
  "title": "Residual-guided search",
  "summary": "Uses residual structure to choose restarts.",
  "method": { "description": "Concrete method description.", "learnedFrom": "ATT-003" },
  "candidateFiles": ["candidate.py"]
}
```

and:

```json
{
  "outcome": "no_candidate",
  "title": "Proposal failed",
  "summary": "No valid candidate was produced.",
  "method": { "description": "The attempted direction and failure.", "learnedFrom": null },
  "candidateFiles": []
}
```

Use `additionalProperties: false`, safe relative paths, 1–32 unique candidate files, and no metric, decision, gate, or evaluator fields.

- [ ] **Step 4: Add evaluation and native-attempt tests**

The evaluator's host-read JSON shape is:

```js
{
  schemaVersion: 1,
  valid: true,
  primaryMetric: { id: "normalized-quality", value: 0.74, unit: null },
  runtimeSeconds: 51.3,
  timeouts: 0,
  crashes: 0,
  invalidClaims: 0,
  diagnostics: []
}
```

For a trustworthy development evaluation, `valid: true` requires a primary metric object. A candidate-level rejection that never reaches development uses `valid: false`, `primaryMetric: null`, and a bounded diagnostic. The normalized attempt requires `kind: "native-autoresearch-attempt"`, problem/attempt IDs, sequence, title, summary, stage `development`, decision `accepted|rejected`, three gate states, method, the evaluation metrics, provenance `{ batchId, infrastructureId, model, promptSha256, inputCandidateSha256 }`, candidate files with hashes, artifacts with hashes, and `createdAt`.

Reject non-finite metrics, negative counts, accepted attempts with failed gates or `valid: false`, primary metric ID mismatch with infrastructure objective, candidate/artifact path collisions, and `learnedFrom` at or after the current sequence.

- [ ] **Step 5: Implement strict validators**

Use exact field allowlists, safe path helpers from PR 1, deep normalized clones, and cross-field checks. Keep imported AutoQEC validation untouched; native validation lives in this new module until the indexer dispatch task.

- [ ] **Step 6: Run focused tests**

```bash
node --test tests/autoresearch-campaign-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit the campaign contracts**

```bash
git add schemas/autoresearch-candidate-output.schema.json lib/autoresearch/campaign-contract.mjs lib/autoresearch/ids.mjs tests/autoresearch-campaign-contract.test.mjs
git commit -m "feat: define native autoresearch campaign contracts"
```

---

### Task 2: Attempt and Batch Allocation

**Files:**
- Create: `lib/autoresearch/attempt-allocation.mjs`
- Test: `tests/autoresearch-attempt-allocation.test.mjs`

**Interfaces:**
- Produces `scanReservedAttemptIds({ rootDir, problemId })`, `nextAttemptId(reserved)`, `scanReservedBatchIds`, and `nextBatchId`.
- Directory names and parseable manifest IDs both reserve identifiers, including damaged records.

- [ ] **Step 1: Write failing allocation tests**

Create fixtures containing valid directories, damaged JSON, mismatched manifest IDs, unrelated files, `ATT-999`, and `ATT-1000`. Assert:

```js
assert.equal(nextAttemptId(["ATT-001", "ATT-003"]), "ATT-004");
assert.equal(nextAttemptId(["ATT-999"]), "ATT-1000");
assert.equal(nextBatchId(["BATCH-001", "BATCH-003"]), "BATCH-004");
```

Reject exhaustion at 999999, unsafe problem IDs, symlinked attempts/batches roots, and parseable IDs belonging to another problem.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-attempt-allocation.test.mjs
```

Expected: FAIL with missing allocation module.

- [ ] **Step 3: Implement allocation**

Follow `scanReservedProblemIds` semantics: reserve every safe directory name first, then add every parseable manifest ID without trusting the rest of that manifest. Sort numerically, pad IDs to at least three digits, and never fill gaps below the maximum.

- [ ] **Step 4: Run focused tests**

```bash
node --test tests/autoresearch-attempt-allocation.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit allocation**

```bash
git add lib/autoresearch/attempt-allocation.mjs tests/autoresearch-attempt-allocation.test.mjs
git commit -m "feat: allocate native autoresearch IDs"
```

---

### Task 3: Isolated Attempt Workspaces and Write Enforcement

**Files:**
- Create: `lib/autoresearch/attempt-workspace.mjs`
- Test: `tests/autoresearch-attempt-workspace.test.mjs`

**Interfaces:**
- Produces `createAttemptWorkspace({ rootDir, batchId, attemptId, infrastructureDir, seedCandidateDir, writablePaths })`.
- Produces `snapshotWorkspaceFiles(workspaceDir)` and `assertOnlyAllowedWrites({ before, after, writablePaths })`.
- Produces `cleanupAttemptWorkspace({ workspaceDir })` restricted to the canonical `.generated/autoresearch-workspaces/` root.

- [ ] **Step 1: Write failing workspace tests**

Assert exclusive creation and this logical layout:

```text
<workspace>/
  campaign-brief.md
  infrastructure.json
  prior-attempts.json
  candidate/
```

Copy template or best-candidate files as regular files, not symlinks/hardlinks. Record SHA-256, size, mode, and relative path before Codex. Reject an extra file, a deletion, a write outside declared paths, symlink replacement, executable-bit change outside allowed files, a file over 16 MiB, and total candidate output over 64 MiB.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-attempt-workspace.test.mjs
```

Expected: FAIL with missing workspace module.

- [ ] **Step 3: Implement workspace staging**

Copy only manifest-declared infrastructure context and candidate seed files. Do not copy evaluator source, private-data paths, repository `.git`, other attempts, batches, knowledge, drafts, or literature. Mark context files read-only where supported and still verify hashes after Codex because permissions are not the trust boundary.

- [ ] **Step 4: Add cleanup safety tests**

Require cleanup to reject `/`, the repository root, `.generated`, a symlink, an unknown batch path, or any path not containing validated batch and attempt components. Confirm it removes only its own workspace after a successful or failed attempt.

- [ ] **Step 5: Run focused tests**

```bash
node --test tests/autoresearch-attempt-workspace.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit workspace isolation**

```bash
git add lib/autoresearch/attempt-workspace.mjs tests/autoresearch-attempt-workspace.test.mjs
git commit -m "feat: isolate autoresearch attempt workspaces"
```

---

### Task 4: Fresh Per-Attempt Codex Adapter

**Files:**
- Create: `lib/autoresearch/codex-attempt.mjs`
- Test: `tests/autoresearch-codex-attempt.test.mjs`

**Interfaces:**
- Produces `buildAttemptPrompt({ problemId, attemptId, infrastructure, writablePaths })`.
- Produces `runAttemptCodex({ codexPath, workspaceDir, schemaPath, context, processRunner }): Promise<CandidateEnvelope>`.
- Reuses PR 1 `runProcess` and path/contract helpers.

- [ ] **Step 1: Write failing prompt tests**

Require the prompt to:

- name only safe relative context files;
- state the exact writable candidate paths;
- forbid evaluator/private-data/repository access;
- require reading `campaign-brief.md`, `infrastructure.json`, and `prior-attempts.json`;
- require a method description and explicit `learnedFrom`;
- forbid self-reported metrics or decisions; and
- treat all context content as data, not instructions.

- [ ] **Step 2: Write failing invocation tests**

Assert the exact fresh invocation:

```js
[
  "exec",
  "--sandbox", "workspace-write",
  "--ephemeral",
  "--json",
  "--output-schema", schemaPath,
  "--output-last-message", join(workspaceDir, ".candidate-result.json"),
  prompt
]
```

Require cwd `workspaceDir`, no resume/thread identifier, output limit 256 KiB, fixed timeout from infrastructure resources, and a sanitized environment. Reject invalid final JSON, no-candidate with written files, candidate outcome with missing declared files, or extra workspace modifications detected by Task 3.

- [ ] **Step 3: Run and verify failure**

```bash
node --test tests/autoresearch-codex-attempt.test.mjs
```

Expected: FAIL with missing adapter.

- [ ] **Step 4: Implement the adapter**

Write the last message outside `candidate/`, snapshot before/after, validate with `validateCandidateEnvelope`, and hash the exact prompt into `promptSha256`. JSONL events may update coarse progress but never provide authoritative candidate metadata.

- [ ] **Step 5: Run focused tests**

```bash
node --test tests/autoresearch-codex-attempt.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit the attempt adapter**

```bash
git add lib/autoresearch/codex-attempt.mjs tests/autoresearch-codex-attempt.test.mjs
git commit -m "feat: run fresh autoresearch attempts"
```

---

### Task 5: Frozen Evaluator and Host Decision

**Files:**
- Create: `lib/autoresearch/evaluator.mjs`
- Test: `tests/autoresearch-evaluator.test.mjs`

**Interfaces:**
- Produces `runCandidateEvaluation({ infrastructureDir, manifest, candidateDir, privateDataRoot, processRunner }): Promise<HostEvaluation>`.
- Produces `deriveAttemptDecision({ objective, gates, evaluation }): "accepted" | "rejected"`.
- Produces gate states `passed|failed|not-run` for containment, public contract, and development.

- [ ] **Step 1: Write failing gate-order tests**

Assert execution order:

```text
containment -> publicCheck -> evaluateDevelopment
```

Containment/public failure skips development and yields a complete rejected evaluation with primary metric `null`. Candidate crash, timeout, malformed output, invalid claim, and no-candidate produce rejected candidate-level results. Missing command, changed infrastructure hash, private manifest mismatch, evaluator crash, or evaluator output arithmetic inconsistency throws `InfrastructureEvaluationError` and stops the batch.

- [ ] **Step 2: Write failing decision tests**

For `maximize`, accept only valid all-pass values `>= acceptanceThreshold`; for `minimize`, accept only values `<= acceptanceThreshold`. Reject NaN/Infinity, wrong metric ID, wrong unit contract, negative runtime/counts, and any accepted decision with a failed/not-run gate.

- [ ] **Step 3: Run and verify failure**

```bash
node --test tests/autoresearch-evaluator.test.mjs
```

Expected: FAIL with missing evaluator.

- [ ] **Step 4: Implement isolated command execution**

Resolve every manifest command entrypoint under the frozen infrastructure directory, use `shell: false`, fixed cwd, fixed resource timeout, and explicit environment. Candidate-visible commands receive only the candidate path and public fixture root. Development evaluation receives the candidate path plus evaluator-only private root. Capture case-level output in private staging and normalize only aggregate schema fields into the attempt.

- [ ] **Step 5: Add leakage tests**

Put a unique canary in private data, evaluator stderr, and case-level JSON. Recursively scan normalized results, attempt staging, candidate workspace, and public logs; assert the canary is absent. Verify diagnostics are bounded and redact absolute roots.

- [ ] **Step 6: Run focused tests**

```bash
node --test tests/autoresearch-evaluator.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit evaluator support**

```bash
git add lib/autoresearch/evaluator.mjs tests/autoresearch-evaluator.test.mjs
git commit -m "feat: evaluate autoresearch candidates"
```

---

### Task 6: Manifest-Last Native Attempt Publication and Indexing

**Files:**
- Create: `lib/autoresearch/attempt-publisher.mjs`
- Modify: `lib/problems/research-schema.mjs`
- Modify: `lib/problems/research-indexer.mjs`
- Test: `tests/autoresearch-attempt-publisher.test.mjs`
- Test: `tests/native-research-indexer.test.mjs`

**Interfaces:**
- Produces `ensureNativeResearchManifest({ rootDir, problemId, now })`.
- Produces `publishNativeAttempt({ rootDir, stageDir, expectedAttemptId, expectedProblemId, rebuildIndex })`.
- `buildResearchIndex` dispatches `imported-research-record` to existing validation and `native-autoresearch-record` to native validation.

- [ ] **Step 1: Write failing publisher tests**

Require exclusive native `research.json` creation without changing an imported record. For attempts, copy candidate/method/log/report artifacts first, write `.attempt.json.tmp`, and rename `attempt.json` last. Reject ID collisions, unlisted files, symlinks, hash changes, missing required artifacts, candidate paths outside the attempt, and a native attempt under an imported record.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-attempt-publisher.test.mjs
```

Expected: FAIL with missing publisher.

- [ ] **Step 3: Implement native publication**

Reuse explicit file-operation injection from `draft-publisher.mjs`. Preserve a published attempt if index rebuild fails and return `published-index-stale`. Cleanup only a newly created incomplete target and retain staging for diagnosis.

- [ ] **Step 4: Write failing native index tests**

Cover deterministic numeric ordering through `ATT-1000`, mixed repositories containing imported and native records, full-record exclusion when one native attempt is invalid, all validator diagnostics, repository immutability, and no execution/read of candidate or report content during indexing.

- [ ] **Step 5: Extend the research-schema union and indexer**

Do not weaken `validateResearchAttempt` or the exact AutoQEC 200-attempt rules. Add explicit native dispatch based on `research.json.kind`; unknown kinds produce diagnostics. Generated index records include `kind` so presentation dispatch is deterministic.

- [ ] **Step 6: Run focused tests**

```bash
node --test tests/autoresearch-attempt-publisher.test.mjs tests/native-research-indexer.test.mjs tests/imported-research-schema.test.mjs tests/research-indexer.test.mjs
```

Expected: PASS for native and unchanged imported contracts.

- [ ] **Step 7: Commit publication and indexing**

```bash
git add lib/autoresearch/attempt-publisher.mjs lib/problems/research-schema.mjs lib/problems/research-indexer.mjs tests/autoresearch-attempt-publisher.test.mjs tests/native-research-indexer.test.mjs
git commit -m "feat: index native autoresearch attempts"
```

---

### Task 7: Campaign Store, Lifecycle Start Journal, Stop, and Recovery

**Files:**
- Create: `lib/autoresearch/campaign-store.mjs`
- Test: `tests/autoresearch-campaign-store.test.mjs`

**Interfaces:**
- Produces `createCampaignStore({ rootDir, jobStore, now })` with `start`, `read`, `transition`, `recordAttempt`, `requestStop`, `createResume`, `listForProblem`, and `recoverStartJournals`.
- Reuses the PR 1 scheduler reservation and artifact-store atomic JSON helper.

- [ ] **Step 1: Write failing batch-state tests**

Allow only:

```text
queued -> running -> completed
running -> stopping -> stopped
queued|running|stopping -> interrupted
queued|running|stopping -> failed
stopped|interrupted -> child queued resume
```

Test atomic `batch.json`, append-only events, completed ID ordering, no count above requested, idempotent stop, parent/child lineage, and resume remaining count.

- [ ] **Step 2: Write failing lifecycle-journal tests**

Starting a first campaign must:

1. validate problem status `qualifying|accepted|solving` and ready infrastructure;
2. stage `BATCH-NNN` and native `research.json` if absent;
3. write a start journal containing hashes and the original `problem.json`;
4. atomically replace `problem.json` with gate readiness `executable`, status `solving`, and updated activity;
5. publish research/batch manifests;
6. mark the journal complete; and
7. expose the queued batch only after all prior steps succeed.

Inject failure at every boundary. Before the batch is visible, rollback the problem from the journal. After the batch is visible, recovery completes the operation rather than deleting durable records. A lifecycle write failure creates no accepted campaign.

- [ ] **Step 3: Run and verify failure**

```bash
node --test tests/autoresearch-campaign-store.test.mjs
```

Expected: FAIL with missing store.

- [ ] **Step 4: Implement per-problem serialized operations**

Use an in-process per-problem promise mutex plus exclusive filesystem journals under `.generated/autoresearch-jobs/start-journals/`. Revalidate hashes immediately before each rename. Reject external edits instead of overwriting them. `problem.json` receives no new top-level fields; selected infrastructure is authoritative in `batch.json`.

- [ ] **Step 5: Implement restart recovery**

`recoverStartJournals` runs before scheduler acceptance. It validates every journal path and hash, then either restores the original problem when no batch manifest exists or completes the visible batch operation. Ambiguous external changes become a diagnostic requiring manual repair; the service starts read-only for that problem.

- [ ] **Step 6: Run focused tests**

```bash
node --test tests/autoresearch-campaign-store.test.mjs tests/problem-schema.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit campaign persistence**

```bash
git add lib/autoresearch/campaign-store.mjs tests/autoresearch-campaign-store.test.mjs
git commit -m "feat: persist autoresearch campaign lifecycle"
```

---

### Task 8: Sequential Campaign Worker and Best-Candidate Learning

**Files:**
- Create: `lib/autoresearch/campaign-worker.mjs`
- Test: `tests/autoresearch-campaign-worker.test.mjs`

**Interfaces:**
- Produces `createCampaignWorker({ rootDir, privateDataRoot, workspaceManager, codexAdapter, evaluator, publisher, campaignStore, rebuildIndex })`.
- Worker consumes `{ batchId, problemId }` and returns one terminal batch state.

- [ ] **Step 1: Write failing successful-loop tests**

For a three-attempt batch, assert strictly sequential calls and one fresh workspace/Codex invocation each. First seed is the infrastructure template; later seed is the best accepted candidate. Best means highest primary value for `maximize` and lowest for `minimize`, with earlier attempt ID as deterministic tie-breaker.

`prior-attempts.json` contains the current best plus at most the 20 most recent normalized summaries:

```js
{ id, decision, primaryMetric, methodSummary, failureClass }
```

No raw logs, prompts, private diagnostics, or hidden model events are carried forward.

- [ ] **Step 2: Write candidate/system failure tests**

Candidate no-output, invalid output, crash, timeout, containment failure, public failure, and invalid claim publish complete rejected attempts and continue. Changed infrastructure hash, missing private root, evaluator crash, invalid evaluator schema, or publication integrity failure transitions the batch to `failed` and starts no later attempt.

- [ ] **Step 3: Write stop/resume tests**

Request stop while attempt 2 is active: attempt 2 finishes and publishes, attempt 3 never starts, state becomes `stopped`. Resume creates a child batch bound to the same infrastructure and original total, starts at the next unallocated attempt ID, and completes only the remaining count. An interrupted batch follows the same explicit resume path.

- [ ] **Step 4: Run and verify failure**

```bash
node --test tests/autoresearch-campaign-worker.test.mjs
```

Expected: FAIL with missing worker.

- [ ] **Step 5: Implement the campaign loop**

Revalidate infrastructure manifest/files before every attempt. Allocate the attempt ID immediately before exclusive staging. Always cleanup the temporary workspace in `finally`; retain batch diagnostics. After publication, call `recordAttempt`, trigger index rebuild, and check stop before allocating the next ID.

- [ ] **Step 6: Run focused tests**

```bash
node --test tests/autoresearch-campaign-worker.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit the campaign worker**

```bash
git add lib/autoresearch/campaign-worker.mjs tests/autoresearch-campaign-worker.test.mjs
git commit -m "feat: run bounded autoresearch campaigns"
```

---

### Task 9: Campaign API and Scheduler Integration

**Files:**
- Modify: `lib/autoresearch/local-service.mjs`
- Modify: `lib/autoresearch/scheduler.mjs`
- Test: `tests/autoresearch-campaign-service.test.mjs`
- Modify: `tests/autoresearch-scheduler.test.mjs`

**Interfaces:**
- Adds batch start, status, stop, and resume endpoints from the approved design.
- Scheduler jobs use `kind: "preparation" | "campaign"` under the same two global slots.

- [ ] **Step 1: Write failing endpoint tests**

Cover:

```text
POST /__local/autoresearch/problems/{id}/batches
POST /__local/autoresearch/batches/{batch-id}/stop
POST /__local/autoresearch/batches/{batch-id}/resume
GET  /__local/autoresearch/batches/{batch-id}
```

Start accepts exactly `{ "attempts": 20, "infrastructureId": "INF-003" }`. Reject unknown fields, counts outside 1–200, non-ready/stale revisions, problem ID mismatch, active same-problem jobs, stale stop/resume states, parent mismatch, and unavailable private manifests. Duplicate start with the same idempotency key returns the existing batch; a different request while reserved returns 409.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/autoresearch-campaign-service.test.mjs
```

Expected: FAIL because campaign routes do not exist.

- [ ] **Step 3: Extend scheduler dispatch**

Preserve PR 1 preparation behavior. Campaign jobs count as one active slot for their entire sequential loop. `needs_input` applies only to preparation. Stopped/completed/failed/interrupted campaign states release problem reservation; a resume request reacquires it through a child queued job.

- [ ] **Step 4: Implement safe API projections**

Return batch progress:

```js
{
  batchId: "BATCH-001",
  problemId: "Prob-007",
  state: "running",
  infrastructureId: "INF-003",
  requestedAttempts: 20,
  completedAttempts: 7,
  currentAttemptId: "ATT-008",
  stopRequested: false,
  queuePosition: null
}
```

Do not expose candidate source, private paths, prompts, token, raw events, environment, or case-level results through status routes.

- [ ] **Step 5: Run focused service tests**

```bash
node --test tests/autoresearch-campaign-service.test.mjs tests/autoresearch-local-service.test.mjs tests/autoresearch-scheduler.test.mjs
```

Expected: PASS for preparation and campaign routes.

- [ ] **Step 6: Commit API integration**

```bash
git add lib/autoresearch/local-service.mjs lib/autoresearch/scheduler.mjs tests/autoresearch-campaign-service.test.mjs tests/autoresearch-scheduler.test.mjs
git commit -m "feat: expose local autoresearch campaign controls"
```

---

### Task 10: Native Ledger, Attempt Dossier, and Live Campaign UI

**Files:**
- Create: `lib/problems/native-research-presentation.mjs`
- Create: `app/problems/[id]/autoresearch-start-dialog.tsx`
- Modify: `lib/problems/research-presentation.mjs`
- Modify: `lib/problems/research-route-data.mjs`
- Modify: `lib/autoresearch/view-model.mjs`
- Modify: `app/problems/[id]/autoresearch-panel.tsx`
- Modify: `app/problems/[id]/autoresearch-panel.module.css`
- Modify: `app/problems/[id]/page.tsx`
- Modify: `app/problems/[id]/attempts/[attemptId]/page.tsx`
- Test: `tests/native-research-presentation.test.mjs`
- Test: `tests/autoresearch-campaign-view-model.test.mjs`
- Modify: `tests/problem-routes-research.test.mjs`

**Interfaces:**
- Produces `buildNativeResearchLedger(record)` and `buildNativeAttemptDossier(attempt, recordManifest)`.
- Extends panel actions with `start`, `stop`, `resume`, and `start_another`.
- Uses `router.refresh()` only when the completed-attempt count increases so server-rendered ledger rows update.

- [ ] **Step 1: Write failing presentation tests**

Require native aggregate cards for attempts, accepted, best primary metric, and active batch. Require rows with attempt, method, decision, public contract, primary metric label/value, runtime, candidate, infrastructure, and open link. Preserve imported ledger columns and formatting exactly.

Native dossiers show method, evaluation path, generic primary metric, candidate file hashes, predecessor, batch, infrastructure, model, prompt hash, timestamps, and the experimental-record disclaimer. They never render candidate code or raw report Markdown as HTML.

- [ ] **Step 2: Write failing view-model/dialog tests**

Assert exact labels `Start autoresearch`, `Queued`, `Stop after current attempt`, `Stopping…`, `Resume remaining attempts`, and `Start another batch`. Validate default 20 and integer 1–200. Compute runtime upper bound as `attempts * attemptRuntimeUpperBoundSeconds`; display unavailable when null. Start is impossible without a ready revision.

- [ ] **Step 3: Run and verify failure**

```bash
node --test tests/native-research-presentation.test.mjs tests/autoresearch-campaign-view-model.test.mjs tests/problem-routes-research.test.mjs
```

Expected: FAIL for missing native presentation and campaign UI states.

- [ ] **Step 4: Implement native presentation dispatch**

Dispatch on generated record `kind`; never guess from fields. Keep imported presentation helpers unchanged and route unknown kinds to diagnostics. Add native ledger and dossier branches beside current example/imported branches.

- [ ] **Step 5: Implement the accessible start dialog and panel actions**

Use a native `<dialog>` or accessible equivalent with labelled integer input, summary definition list, cancel, and primary start. Keep one main action per state. Poll running/queued at 1 second, stopping at 500 ms, terminal states not at all. Abort stale requests, disable duplicate submissions, and announce state changes with `aria-live`.

When `completedAttempts` increases, call `router.refresh()` once after the generated research index reports the attempt; retry with bounded backoff if the service says published but the route index is stale.

- [ ] **Step 6: Preserve the approved style**

Extend only `autoresearch-panel.module.css`. Use existing CSS variables, square 1px borders, green primary action, mono labels, paper/surface backgrounds, no shadow, no rounded cards, and responsive stacking. Assert `app/globals.css`, `app/page.tsx`, and `app/layout.tsx` are byte-identical to their task-start versions.

- [ ] **Step 7: Run focused UI tests**

```bash
node --test tests/native-research-presentation.test.mjs tests/autoresearch-campaign-view-model.test.mjs tests/problem-routes-research.test.mjs tests/research-presentation.test.mjs
npm run lint
```

Expected: PASS.

- [ ] **Step 8: Commit native UI and routes**

```bash
git add lib/problems/native-research-presentation.mjs lib/problems/research-presentation.mjs lib/problems/research-route-data.mjs lib/autoresearch/view-model.mjs 'app/problems/[id]/autoresearch-start-dialog.tsx' 'app/problems/[id]/autoresearch-panel.tsx' 'app/problems/[id]/autoresearch-panel.module.css' 'app/problems/[id]/page.tsx' 'app/problems/[id]/attempts/[attemptId]/page.tsx' tests/native-research-presentation.test.mjs tests/autoresearch-campaign-view-model.test.mjs tests/problem-routes-research.test.mjs
git commit -m "feat: present live autoresearch campaigns"
```

---

### Task 11: Watcher, Documentation, Static Safety, and Test Registration

**Files:**
- Modify: `scripts/dev-problem-index.mjs`
- Modify: `tests/dev-problem-index.test.mjs`
- Modify: `README.md`
- Modify: `docs/local-autoresearch.md`
- Modify: `package.json`
- Modify: `tests/pages-showcase.test.mjs`
- Modify: `tests/built-static-assets.test.mjs`

**Interfaces:**
- Watcher rebuilds for native `research.json`, `attempt.json`, and completed manifest publication, but ignores candidate/log/report changes.
- Documents start, stop, resume, batch completion, and experimental-record review.

- [ ] **Step 1: Write failing watcher tests**

Create a native fixture with `batches/BATCH-001` and `attempts/ATT-001`. Assert watchers register these directories, rebuild only for `research.json`, `batch.json`, and `attempt.json`, and do not rebuild for `candidate.py`, `LOG.md`, `REPORT.md`, `events.jsonl`, or `stderr.log`. A new attempt directory triggers watcher reconciliation before its manifest event.

- [ ] **Step 2: Run and verify failure**

```bash
node --test tests/dev-problem-index.test.mjs
```

Expected: FAIL until batches/native manifests are included.

- [ ] **Step 3: Implement focused watch rules**

Add batch manifest and native infrastructure directory watching without recursive repo-wide watchers. Preserve debounce and existing imported cohort behavior.

- [ ] **Step 4: Extend static leak tests**

After `npm run pages:build`, assert `out/` contains no `BATCH-`, native attempt disclaimer, candidate source, local API path, runtime status, stop/resume controls, batch logs, infrastructure manifest, or private-root text. `Prob-000` remains the only showcase record.

- [ ] **Step 5: Update operator docs**

Document bounded count/default/range, two global slots, sequential attempts, fresh Codex runs, best-candidate carry-forward, graceful stop, interruption, explicit resume, candidate versus infrastructure failures, artifacts, Git review, and why batch completion does not imply solved.

- [ ] **Step 6: Register all PR 2 focused tests**

Add the new tests to `test:unit:problems` and add:

```json
"test:autoresearch:campaigns": "node --test tests/autoresearch-campaign-*.test.mjs tests/autoresearch-attempt-*.test.mjs tests/autoresearch-codex-attempt.test.mjs tests/autoresearch-evaluator.test.mjs tests/native-research-*.test.mjs"
```

- [ ] **Step 7: Run focused and static tests**

```bash
npm run test:autoresearch:campaigns
npm run test:unit:problems
npm run test:pages
git diff --check
```

Expected: PASS.

- [ ] **Step 8: Commit integration docs and watchers**

```bash
git add scripts/dev-problem-index.mjs tests/dev-problem-index.test.mjs README.md docs/local-autoresearch.md package.json tests/pages-showcase.test.mjs tests/built-static-assets.test.mjs
git commit -m "docs: complete local autoresearch campaign workflow"
```

---

### Task 12: Fake End-to-End Campaign, Stop/Resume, and Full Verification

**Files:**
- Create: `tests/e2e/local-autoresearch-campaign.spec.ts`
- Create: `tests/fixtures/autoresearch/fake-attempt-codex.mjs`
- Create: `tests/fixtures/autoresearch/fake-infrastructure/fixture-manifest.json`
- Modify: `playwright.autoresearch.config.ts`
- Modify: `package.json`

**Interfaces:**
- Extends `npm run test:e2e:autoresearch` to run both preparation and campaign browser scenarios against fake processes and a temporary repository fixture.

- [ ] **Step 1: Write the failing bounded-campaign scenario**

The browser test must:

1. open a ready qualifying problem;
2. click `Start autoresearch`;
3. verify default 20, change it to 3, and confirm;
4. observe queued then running state;
5. observe each of three complete rows appear without a browser reload;
6. open one native attempt dossier;
7. assert the problem is `solving`, the batch is completed, and it is not `solved`;
8. start a second two-attempt batch and verify ID continuation; and
9. reload and reconstruct history from disk.

- [ ] **Step 2: Write the failing parallelism and stop/resume scenario**

Create three problems. Start two two-attempt batches and assert both run while the third queues. Request stop on one during its first attempt; assert that attempt publishes, no second starts, and `Resume remaining attempts` creates a child that completes one remaining attempt with the same infrastructure.

- [ ] **Step 3: Run and verify failure**

```bash
npm run test:e2e:autoresearch
```

Expected: FAIL until fake attempt Codex/evaluator wiring and campaign test config exist.

- [ ] **Step 4: Implement deterministic fake processes**

The fake Codex validates exact arguments/cwd and writes one allowed candidate plus the strict candidate envelope. The fake infrastructure commands emit deterministic containment/public/evaluation JSON, sleep only through controllable test barriers, and fail if private canaries enter candidate-visible paths. Do not call real Codex, Docker, network, or private datasets.

- [ ] **Step 5: Run browser and full repository verification**

```bash
npm run test:e2e:autoresearch
make build
make test
git diff --check
git status --short
```

Expected: all commands PASS. The worktree contains only intentional PR 2 changes plus any pre-existing user changes, which remain untouched and are reported separately.

- [ ] **Step 6: Commit end-to-end campaign coverage**

```bash
git add tests/e2e/local-autoresearch-campaign.spec.ts tests/fixtures/autoresearch/fake-attempt-codex.mjs tests/fixtures/autoresearch/fake-infrastructure/fixture-manifest.json playwright.autoresearch.config.ts package.json
git commit -m "test: verify autoresearch campaigns end to end"
```

- [ ] **Step 7: Request code review before PR 2 handoff**

Invoke `superpowers:requesting-code-review`, address findings through the original task implementers, rerun `make test`, and only then use `superpowers:finishing-a-development-branch` to choose commit/push/PR handling.
