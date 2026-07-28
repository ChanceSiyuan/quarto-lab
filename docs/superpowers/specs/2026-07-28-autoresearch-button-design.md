# Local Autoresearch Preparation and Campaign Button — Design

Date: 2026-07-28  
Status: Approved in conversation

## Purpose

Add one stateful autoresearch control to each eligible local problem page. The
control first starts a background preparation job that creates the campaign
scaffold, builds or connects the benchmark and datasets, and runs preflight.
After preflight passes, the same control becomes a separately confirmed
`Start autoresearch` action. A started campaign runs a user-selected, bounded
number of attempts and publishes each completed attempt as one row in the
existing research ledger.

The feature keeps two concepts visibly separate:

- infrastructure preparation is a prerequisite shared by attempts; and
- attempts are the actual research experiments displayed as `ATT-NNN` rows.

Scaffolding or preflight checks never consume attempt IDs and never appear as
research results.

## Current repository boundary

Research Loop currently indexes local problem records, renders research
ledgers, and preserves imported AutoQEC attempt provenance. It does not have an
autonomous solver backend, queue, or unattended agent. This feature introduces
a local-only background execution phase and therefore deliberately changes the
current phase boundary.

Implementation must update the repository documentation and agent instructions
that currently say no autonomous backend exists. It must describe the new
authority narrowly: a loopback-only local sidecar may prepare and execute
autoresearch jobs only after explicit problem-page actions. It does not create
a cloud service, remote queue, D1/R2 model, or deployed execution endpoint.

The current dashboard appearance remains preserved. Do not rewrite
`app/page.tsx`, `app/globals.css`, or `app/layout.tsx`. The problem-page panel
uses a focused component and CSS module that reproduce the existing paper,
surface, ink, green, mono-label, square-border, and dense-table visual language.

## Approved product decisions

- The feature runs in the background through one local sidecar supervised by
  `make dev`.
- Preparation and campaign execution are distinct job types in the same
  service.
- One problem may have only one active preparation or campaign job.
- Different problems may run concurrently.
- The global active-job limit is two in the first version; excess work queues.
- Preparation automatically continues through scaffold, benchmark and dataset
  setup, and preflight until it either passes, fails, or needs user input.
- The preparation agent never fabricates a domain-valid metric, correctness
  rule, or private dataset when the problem does not supply enough information.
  It enters `needs_input` with one blocking question instead.
- Passing preflight does not automatically start research. The user must press
  `Start autoresearch` separately.
- Campaigns have a bounded attempt count. The default is 20 and the accepted
  range is 1–200.
- A batch executes attempts sequentially so each new attempt may receive a
  compact structured summary of prior attempts and the current best candidate.
- Each attempt uses a fresh ephemeral Codex execution rather than a persistent
  conversation.
- Each attempt uses a temporary isolated workspace under `.generated/`; the
  service does not create one Git branch or worktree per attempt.
- A completed attempt publishes the full candidate and audit artifacts with
  hashes. The user later decides whether to commit those repository changes.
- Stop is graceful: finish the active attempt, then start no additional one.
- Interrupted batches are not resumed automatically after restart. The user may
  resume the remaining bounded attempts explicitly.

## User experience

### Placement

The autoresearch panel appears on an eligible local problem page after the
problem header and before the metric strip and attempts ledger. It is visually
important but remains separate from the lifecycle badge and research results.

The panel contains:

- a small `AUTORESEARCH INFRASTRUCTURE` label;
- the current preparation or campaign status;
- one concise status explanation;
- revision, preflight, queue, or progress metadata appropriate to that state;
- one primary action in a stable location; and
- a diagnostic or history link only when useful.

### Stateful primary action

| State | Primary action | Supporting information |
|---|---|---|
| No infrastructure | `Prepare autoresearch` | Explains that a local background job will prepare benchmark and data infrastructure. |
| Preparation queued | Disabled `Queued` | Queue position and global capacity. |
| Preparing | Disabled `Preparing…` | Coarse current stage and elapsed time. |
| Needs input | `Provide input` | The one blocking question. |
| Preparation failed | `Retry preparation` | Concise failure and diagnostic-log link. |
| Ready | `Start autoresearch` | Frozen infrastructure revision and preflight result. |
| Campaign queued | Disabled `Queued` | Requested attempt count and queue position. |
| Campaign running | `Stop after current attempt` | Completed count, requested count, and current attempt. |
| Stopping | Disabled `Stopping…` | States that the active attempt is finishing. |
| Stopped | `Resume remaining attempts` | Completed and remaining counts. |
| Interrupted | `Resume remaining attempts` | Restart explanation and durable completed count. |
| Completed | `Start another batch` | Completed batch summary and history. |

### Start confirmation

`Start autoresearch` opens a compact confirmation dialog. It contains:

- an integer attempt-count field with default 20 and limits 1–200;
- the exact infrastructure revision;
- current global capacity;
- an upper-bound runtime estimate computed from the preflight per-attempt limit;
- `Cancel`; and
- `Start autoresearch`.

The estimate is arithmetic over recorded limits, not a model-generated guess.
If no trustworthy upper bound exists, the dialog says it is unavailable rather
than inventing one.

### Attempts ledger

Preparation progress stays in the autoresearch panel. Only evaluated candidate
runs become attempts. Every published row includes an attempt ID, method
summary, decision, metrics, batch ID, infrastructure revision, and an `Open`
link. A running attempt is shown in the panel, not as a partial ledger row.

On narrow screens, the new panel follows the existing problem-detail responsive
rules and the attempt table continues to use the existing mobile card form.

### Static output

The GitHub Pages showcase does not call the local API. Its autoresearch control
is absent or rendered as a noninteractive `Available in local mode` message.
No local job, infrastructure artifact, candidate, private manifest, or log is
copied into the static artifact unless an existing explicit synthetic fixture
already owns it.

## Architecture

`make dev` supervises the existing index watcher and development application
plus one loopback autoresearch sidecar:

```text
problem-page client
  -> Vite development proxy
  -> local autoresearch service on 127.0.0.1
  -> job manager, global concurrency 2
       -> prepare worker
       -> campaign worker
  -> validated artifact store
```

The proxy injects a random per-process capability token. The browser never
receives that token, and the sidecar rejects requests without it. Node process
execution stays outside the Worker-oriented application runtime and cannot be
bundled into the deployed site.

The sidecar owns fixed prompts, skill paths, schemas, timeouts, process
arguments, model defaults, canonical roots, and resource policies. API callers
may choose only advertised operations, a validated problem ID, an advertised
answer to a blocking question, and an attempt count within 1–200. They cannot
supply shell commands, executable paths, filesystem roots, arbitrary prompts,
model names, or environment overrides.

## Job model

### Global scheduling

The service owns two active slots shared by preparation and campaign jobs.
Jobs beyond that limit wait in FIFO order. A problem with any queued, running,
needs-input, or stopping job rejects or deduplicates a second start instead of
creating competing work.

`needs_input` is suspended and releases its global execution slot while still
reserving its problem against a competing job. Submitting an answer queues its
child execution normally; it does not jump ahead of older queued work.

Attempt execution inside one campaign is sequential. Different campaigns may
occupy both active slots. Queue and active state are persisted sufficiently for
restart recovery; in-memory state is an acceleration, not the source of truth.

### Preparation states

```text
queued
  -> scaffolding
  -> building_benchmark
  -> preparing_datasets
  -> preflight
  -> ready
```

Terminal or suspended branches are:

- `needs_input`: one material decision cannot be inferred safely;
- `failed`: the worker, generated content, build, or preflight failed; and
- `interrupted`: the service or machine stopped before publication.

One answer to `needs_input` creates a child execution in the same job lineage.
The answer is stored as an immutable event. The worker revalidates all prior
outputs rather than trusting mutable process memory.

### Campaign states

```text
queued -> running -> completed
                  -> stopping -> stopped
                  -> failed
                  -> interrupted
```

A candidate failure, invalid result, timeout, or crash is an evaluated rejected
attempt and does not terminate the batch. An infrastructure integrity failure,
missing private dataset, evaluator failure, containment failure, or frozen hash
change stops the batch because later scores would no longer be comparable.

Graceful stop records the request and allows the active attempt to reach a
validated terminal result. No new attempt starts. A first-version forced kill
is reserved for service shutdown or process timeout, not exposed as the normal
UI action.

On service startup, unfinished staging jobs become `interrupted`. The service
never silently resumes model execution. `Resume remaining attempts` creates a
child run that retains the original requested total, completed attempt list,
infrastructure revision, and lineage, then begins at the next unallocated
attempt ID.

## Preparation worker

The prepare worker runs an ephemeral Codex process inside a dedicated staging
root, not in the repository checkout. It receives read-only copies of the
problem contract and approved repository interfaces plus a writable campaign
staging directory. The fixed instruction asks it to:

1. create the candidate interface and scaffold;
2. implement or connect public contract checks;
3. implement independent correctness verification and scoring;
4. create public fixtures and declare development/blind dataset requirements;
5. generate safe reproducible data only when the problem definition supports
   deterministic generation;
6. request user input instead of inventing missing domain authority;
7. configure resource, containment, and dependency boundaries;
8. create focused benchmark and anti-gaming tests; and
9. return a structured preparation result.

The host validates every generated file before any official publication. Codex
does not write `problems/` directly.

### Scaffold contract

The prepared infrastructure has logical components equivalent to:

```text
candidate-template/
public/
  README.md
  examples/
  smoke test
evaluator/
  evaluation entrypoint
  correctness verifier
  scoring
datasets/
  public data or generator
  development manifest
  blind manifest
baselines/
containers or environment locks/
tests/
campaign manifest
```

This is a contract, not a requirement that every problem use Python or the same
literal filenames. The versioned infrastructure manifest records the concrete
entrypoints and safe paths.

### Dataset boundary

The data model distinguishes:

- public data: visible examples and contract checks available to the candidate;
- development data: private repeated-evaluation data that returns bounded,
  aggregate feedback; and
- blind data: frozen fresh evaluation not used as iterative feedback.

Raw development/blind cases, answers, salts, selection rules, case-level
results, and credentials stay in a configured private evaluation root outside
`problems/` and outside candidate workspaces. The repository records only safe
schema, provenance, version, and digest metadata. The candidate process never
mounts the private root. The evaluator receives only the required read-only
mount and emits schema-validated aggregate output.

### Preflight

Preflight must verify at least:

- candidate API invocation and output schema;
- public smoke behavior;
- independent correctness rejection;
- scoring arithmetic and direction;
- known-correct baseline reproduction in the frozen environment;
- invalid, hard-coded, crashing, and timing-out negative candidates;
- candidate/evaluator filesystem containment;
- absence of candidate access to private data and answer material;
- network and resource policy;
- deterministic seeds or an explicit stochastic reproducibility contract;
- environment and dependency rebuilding from a clean staging root;
- safe paths, file types, symlink refusal, and size limits; and
- complete hashes for every published infrastructure file.

Passing preflight produces an immutable infrastructure revision. Failing checks
produce diagnostics but no revision that may be selected by a campaign.

## Campaign worker and attempt execution

Starting a campaign binds it permanently to one preflight-passed infrastructure
revision and one requested attempt count. The binding never follows a mutable
`latest` pointer.

For each attempt, the worker:

1. allocates the next attempt ID without reusing IDs reserved by directories or
   parseable manifests;
2. creates a clean temporary workspace under
   `.generated/autoresearch-workspaces/<batch-id>/<attempt-id>/`;
3. initializes it from the candidate template or the current best candidate;
4. supplies a fixed campaign brief, frozen infrastructure metadata, the current
   best candidate, and compact structured summaries of prior attempts;
5. starts a fresh ephemeral Codex process with only candidate paths writable;
6. validates the produced candidate and declared method record;
7. runs public contract and containment checks;
8. runs the host evaluator against private development data;
9. independently recomputes or verifies score arithmetic;
10. renders host-owned normalized attempt metadata and reports;
11. validates the complete staged attempt and hashes; and
12. atomically publishes the attempt directory.

The model never authors authoritative `attempt.json` arithmetic or HTML. Its
candidate and method explanation are inputs; the host owns normalized status,
metrics, decisions, provenance, and deterministic presentation.

Each attempt is independent at the process level. Carried learning is explicit
and inspectable through the selected predecessor candidate and structured prior
summaries. Hidden conversational state cannot silently affect a later attempt.

Temporary workspaces are not Git branches. After publication they may be
removed. The durable attempt contains the complete candidate, method record,
log, report, relevant evaluator summary, input/output hashes, predecessor ID,
batch ID, infrastructure revision, model identity when available, timestamps,
and decision.

## Artifact layout

Active work is untrusted staging:

```text
.generated/autoresearch-jobs/<job-id>/
.generated/autoresearch-workspaces/<batch-id>/<attempt-id>/
```

Validated durable records use:

```text
problems/Prob-NNN/
  problem.json
  problem.md
  infrastructure/
    INF-001/
      infrastructure.json
      preflight-report.json
      public/
      evaluator/
      manifests/
      source-manifest.json
  batches/
    BATCH-001/
      batch.json
      events.jsonl
      stderr.log
  attempts/
    ATT-001/
      attempt.json
      candidate files declared by infrastructure.json
      METHOD.txt
      LOG.md
      REPORT.md
```

The exact candidate extension and optional method filename are declared by the
infrastructure contract. The native attempt schema must not pretend every
problem is Python-specific.

Publication is manifest-last. The host writes content and audit records first,
validates them, writes the manifest under a temporary name, and atomically
renames the manifest last. An indexer never observes a plausible partial
attempt. Existing directories are never overwritten.

## Problem lifecycle

Preparation and assessment remain distinct. A positive assessment recommends
work; it does not create infrastructure. A successful preparation proves an
executable gate exists; it does not claim a scientific result.

Preflight publishes a ready infrastructure revision but does not edit
`problem.json`. Research begins only when the user confirms
`Start autoresearch`. That action atomically records the selected
infrastructure, sets gate readiness to `executable`, and changes an eligible
problem to `solving` before the batch is accepted. If the lifecycle write
fails, no campaign starts.

Completing the requested number of attempts does not set the problem to
`solved`. The problem remains `solving` across batches until the user makes an
explicit scientific lifecycle decision through a separate workflow.

## Local API

All routes are available only through the local development proxy:

| Method and path | Purpose |
|---|---|
| `POST /__local/autoresearch/problems/{id}/prepare` | Start or return the active preparation job. |
| `GET /__local/autoresearch/problems/{id}` | Return infrastructure, active job, batches, and latest attempt state. |
| `POST /__local/autoresearch/jobs/{job-id}/input` | Submit one answer to the exact active blocking question. |
| `GET /__local/autoresearch/jobs/{job-id}` | Poll a preparation or campaign job. |
| `POST /__local/autoresearch/problems/{id}/batches` | Validate count and start or queue a campaign. |
| `POST /__local/autoresearch/batches/{batch-id}/stop` | Request graceful stop. |
| `POST /__local/autoresearch/batches/{batch-id}/resume` | Resume the bounded remaining count from stopped/interrupted state. |
| `GET /__local/autoresearch/batches/{batch-id}` | Poll batch progress and coarse stage. |
| `GET /__local/autoresearch/logs/{problem-id}/{job-id}` | Download validated local diagnostics. |

Request bodies have fixed small limits. IDs are validated before path
resolution. Canonical paths must remain under the expected problem, staging,
workspace, infrastructure, batch, or private-evaluator roots. An answer must
refer to the active question and satisfy its advertised schema; stale or
arbitrary answer submissions are rejected.

## Security properties

- Listen only on loopback and require the proxy-injected capability token.
- Spawn every program from a fixed argument array with `shell: false`.
- Do not pass user request data into executable names, command arguments, cwd,
  environment variables, model selection, or arbitrary prompts.
- Run preparation in a staging-only writable root.
- Run candidates without repository, evaluator source, or private-data access.
- Run evaluators separately with the minimum read-only private-data mount.
- Deny network access unless the frozen infrastructure contract explicitly
  requires and preflight validates a narrower policy.
- Reject symlinks, special files, path escapes, uncontrolled archives,
  unexpected executables, and oversized artifacts.
- Treat all model output as untrusted until schema, cross-field, arithmetic,
  containment, and path validation pass.
- Never render model-authored HTML.
- Keep raw events, diagnostic logs, private manifests, and real local records
  out of static Pages output.
- Never execute copied candidate or infrastructure files during ordinary
  indexing, building, previewing, or route rendering.

## Error handling

Preflight failures do not publish a ready revision. Staging remains available
for diagnostics and a retry uses a new immutable job identity.

Candidate-level failures publish rejected attempts only when the host can
produce a complete trustworthy record. If evaluation integrity itself is
unknown, the worker records a batch diagnostic and stops rather than producing
a plausible rejected row.

If publication fails before manifest rename, the host removes only the partial
target that the same operation exclusively created. It never removes an
existing target. If index refresh fails after manifest publication, the
artifact remains durable and the UI reports a stale index rather than deleting
the attempt.

Service shutdown terminates active child processes, records interruption, and
does not fabricate terminal reports. Timeout handling sends graceful
termination first and force-kills after a fixed bounded grace period.

## Verification

### Contract and unit tests

- Preparation, infrastructure, batch, attempt, blocking-question, and API
  schemas accept complete records and reject unknown fields.
- State transition tests cover every allowed transition and reject stale,
  duplicate, and impossible transitions.
- Attempt count accepts exactly 1–200 and defaults to 20 at the UI boundary.
- Scheduler tests enforce global concurrency two and one active job per problem.
- Runtime estimates derive only from recorded limits.
- Lifecycle updates are atomic with campaign acceptance.
- Canonical containment, safe IDs, symlink refusal, file limits, and manifest-
  last publication are covered.

### Worker tests

- A fake Codex executable verifies fresh ephemeral invocation, fixed prompts,
  fixed argument arrays, staging cwd, environment filtering, output schemas,
  timeout, and signal handling without contacting a model.
- Fake candidate and evaluator programs cover correct, invalid, hard-coded,
  crashing, timing-out, malformed, and leaking behaviors.
- Preparation fixtures cover generated public data, externally supplied private
  manifests, needs-input, failed preflight, and successful frozen revisions.
- Attempt tests prove the candidate cannot read evaluator or private-data roots.
- Arithmetic and decision fields are recomputed by the host.

### Service and persistence tests

- FIFO behavior with two active problems and queued overflow.
- Duplicate suppression for one problem.
- Different-problem parallelism with sequential attempts inside each batch.
- Graceful stop, stopped state, and bounded resume lineage.
- Startup conversion of unfinished work to interrupted state.
- Atomic infrastructure and attempt publication.
- Durable history across process restarts.
- Failure after publication produces a stale-index diagnostic without data loss.

### UI and end-to-end tests

- Every button state and transition renders with the approved current style.
- Start confirmation validates 1–200 and shows the frozen revision.
- Polling stops or slows in terminal states and handles an unavailable sidecar.
- Needs-input renders exactly one active question and rejects stale answers.
- A fake end-to-end campaign publishes attempts one at a time and immediately
  adds complete ledger rows.
- Static Pages contains no active local calls or local artifacts.
- Keyboard, focus, dialog, and narrow-screen behavior remain accessible.

### Repository gates

Run focused worker, service, contract, problem, presentation, and browser tests
while implementing. Before each implementation PR is complete, run
`make build` and `make test` and inspect the local problem page against the
preserved visual surface.

## Delivery plan

This end-to-end design is delivered as two focused implementation PRs.

### PR 1 — Preparation and preflight

- versioned preparation and infrastructure contracts;
- repository-local preparation skill with structured output mode;
- loopback sidecar, capability proxy, scheduler, staging, and persistence;
- prepare worker, blocking questions, preflight, and immutable revisions;
- problem-page infrastructure panel through `Ready`;
- static unavailable state; and
- documentation and phase-boundary update.

### PR 2 — Campaigns and attempts

- versioned batch and native-attempt contracts;
- isolated candidate workspace and fresh per-attempt Codex adapter;
- host evaluator, artifact publication, indexing, and presentation;
- bounded start dialog, sequential attempt loop, different-problem parallelism;
- stop, interruption, bounded resume, and batch history; and
- completed ledger integration and end-to-end tests.

PR 2 begins only after PR 1's ready infrastructure is independently usable and
verified. Neither PR rewrites the preserved homepage, global stylesheet, or
layout to make tests pass.

## Completion criteria

- An eligible local problem can prepare autoresearch infrastructure from one
  problem-page action without blocking the browser.
- Preparation reaches ready, failed, interrupted, or one-question needs-input
  states without publishing partial infrastructure.
- Preflight-passed revisions are immutable and contain no private raw data.
- Starting research requires a separate explicit confirmation and a validated
  attempt count from 1–200.
- Different problems can occupy two global slots while one problem cannot run
  competing jobs.
- Every attempt uses a fresh isolated Codex run and becomes exactly one complete
  ledger row only after host validation.
- Candidate failures remain auditable attempts while infrastructure failures
  stop incomparable work.
- Stop and explicit bounded resume preserve already completed attempts.
- Batch completion does not silently declare the research problem solved.
- No local execution surface or real artifact leaks into static deployment.
- The feature matches the current Research Loop visual language and all local
  build and test gates pass.
