# Local Research-Problem Assessment Reports — Design

## Summary

Research Loop will let a user assess an existing problem from its local problem
page. Pressing one button starts a background Codex CLI job that uses the
repository's `assess-research-problem` skill, evaluates research value and
autoresearch suitability separately, and produces a schema-validated result.
The problem page shows a concise recommendation and links to an immutable,
self-contained HTML report with every dimension score and its evidence.

This feature is deliberately local-only. The deployed static showcase does not
run Codex, access the user's checkout, or expose assessment artifacts. An
assessment recommendation never changes `problem.json`; acceptance and
rejection remain human lifecycle decisions.

## Need and success criteria

The current skill returns a conversational Markdown assessment. That is useful
inside a Codex task but cannot drive a durable problem-page summary, a stable
report, or a background-job state machine. The local Problem Console needs to
turn the same judgment into an auditable product workflow without weakening the
repository's knowledge trust boundary.

The feature is successful when a local user can:

1. open a problem page and start one assessment;
2. see queued, running, clarification, completed, failed, interrupted, and stale
   states without opening a terminal;
3. receive a clear autoresearch recommendation plus `V`, `A`, and `S` scores;
4. open a standalone HTML report containing every weighted dimension, score
   interval, evidence state, rationale, and source reference;
5. rerun an assessment without overwriting any earlier run; and
6. inspect enough local provenance to reproduce or audit the judgment.

## Constraints and non-goals

- The application is a local single-user workspace. There is no remote queue,
  multi-user authorization system, or cloud execution service.
- The feature invokes the user's installed and authenticated Codex CLI. It does
  not use a separate API key.
- The Codex job is read-only and must not modify `problems/`, `knowledge/`,
  `drafts/`, or `literature/`. The host service alone writes assessment
  artifacts after validating output.
- A verdict is advisory. It never updates the problem lifecycle or writes a
  rejection block.
- The first version has no manual cancellation, live command stream, automatic
  retries, or multi-job parallelism.
- Assessment reports use a deterministic HTML template and do not require
  Quarto. Quarto remains necessary only for the knowledge site.
- Static Pages output shows the local assessment control as unavailable and
  does not publish local assessment artifacts.

## Prior art and reusable tools

The installed Codex CLI and current official Codex manual establish two useful
integration levels:

- `codex exec` is the lightweight automation surface. It supports a read-only
  sandbox, ephemeral sessions, JSONL events, a JSON output schema, and writing
  the final response separately. This matches a bounded one-shot assessment.
- Codex App Server supplies long-lived threads, approvals, cancellation, and
  rich streamed events. Those capabilities are valuable for a future
  interactive agent console but are unnecessary for this first version.

The repository already supplies the remaining building blocks: a Node process
supervisor in `scripts/dev-problem-index.mjs`, deterministic problem IDs and
filesystem validation, a generated problem index, a local-only development
path, and immutable problem-side audit records. The implementation should reuse
Node's `child_process`, HTTP, filesystem, and crypto modules rather than add a
queue or report-rendering dependency.

## Selected feature set and effort

Rough effort assumes agent-assisted implementation and review.

| Feature | Effort | Decision |
|---|---:|---|
| Versioned assessment JSON contract and skill integration | 0.5–1 day | Build |
| Local loopback job service and `codex exec` adapter | 1–2 days | Build |
| CLI, authentication, skill, and problem preflight | 0.5 day | Build |
| Queued/running/clarification/completed/failed state API | 1 day | Build |
| Immutable atomic artifact storage | 1 day | Build |
| Problem-page summary and polling | 1–1.5 days | Build |
| Deterministic standalone HTML report | 1 day | Build |
| Staleness detection | 0.5–1 day | Build |
| Reruns and immutable run history | 0.5–1 day | Build |
| Resolver ambiguity selection | 0.5–1 day | Build |
| Manual cancellation | 0.5–1 day | Defer |
| Full live event stream | 1–2 days | Defer |
| Automatic lifecycle mutation | ~1 day | Drop |

The selected first version is roughly 7–10 working days after overlap between
the service, persistence, and UI work. The ambiguity path is required by the
trust boundary rather than optional polish.

## Architecture

Use a local loopback sidecar supervised by `make dev`:

```text
problem-page client
  -> Vite development proxy
  -> local assessment service on 127.0.0.1
  -> FIFO job manager
  -> codex exec adapter
  -> schema validation
  -> deterministic report renderer
  -> problems/{id}/assessments/{run-id}/
```

The Vite proxy injects a random per-process capability token. The browser never
receives that token, and the sidecar rejects direct requests that do not carry
it. Node-only process execution stays outside the vinext/Cloudflare runtime and
cannot accidentally enter a deployed Worker bundle.

Only one Codex job runs globally at a time. Other jobs wait in FIFO order. A
duplicate start for a problem that is already queued, running, or awaiting a
selection returns the existing active run rather than enqueueing another.

### Alternatives considered

1. A Next route handler would provide a simple same-origin API but cannot
   reliably use `child_process` in the repository's Worker-oriented runtime.
2. Codex App Server would provide richer progress and cancellation, but its
   persistent JSON-RPC session model is disproportionate for one-shot reports.
3. Writing assessment state into `problem.json` would simplify page loading but
   would couple an advisory result to the problem lifecycle and cause core
   manifest churn.

## Modules

### Assessment contract

Own the JSON Schema, cross-field validation, score arithmetic, verdict rules,
and stable IDs for each dimension. Human-readable text follows the primary
language of `problem.md`; keys, IDs, and verdict enums remain English.

The `assess-research-problem` skill currently lives on the separate skill PR and
must be merged before implementation. Its interactive Markdown output remains
useful for direct conversations. When the runner supplies the assessment output
schema, the skill must instead return the structured contract described here.

### Codex adapter

Spawn Codex using an argument array and `shell: false`, with the repository root
as `cwd`. The fixed invocation uses `codex exec`, `--sandbox read-only`,
`--ephemeral`, `--json`, and `--output-schema`. The service owns the prompt,
schema path, timeout, and model defaults; API callers cannot supply command
arguments, paths, prompts, or model names.

Capture JSONL stdout and diagnostic stderr separately. A run has a 30-minute
execution limit; queue wait does not count. On timeout send `SIGTERM`, wait five
seconds, then force termination if necessary.

### Local job service

Manage preflight, the FIFO queue, child processes, status transitions, and
shutdown. Preflight verifies the problem, assessment skill, schema, Codex
binary, and `codex login status` before accepting a job. Preflight failures do
not create a formal assessment run.

On service shutdown, terminate the active child. At startup, any unfinished
staging record becomes an immutable `interrupted` run.

### Artifact store

Each accepted run receives a sortable UTC timestamp plus random suffix:

```text
problems/Prob-001/assessments/
└── 20260728T143012Z-a1b2c3/
    ├── run.json
    ├── input.json
    ├── assessment.json       # completed runs only
    ├── clarification.json    # needs-input runs only
    ├── selection.json        # child run after user choice
    ├── report.html           # completed runs only
    ├── events.jsonl
    └── stderr.log
```

Active work lives under `.generated/assessment-runs/{run-id}/`. The host writes
and validates the complete terminal artifact set there, fsyncs where supported,
and publishes it by an atomic directory rename. No mutable `latest` file is
authoritative; the service derives the newest completed run from immutable
metadata.

The service never stages or commits these files. They appear as ordinary local
repository changes for the user to review and preserve deliberately.

### Report renderer

Render `report.html` from validated JSON, not model-generated markup. Escape all
text, permit no scripts or remote resources, and include a restrictive Content
Security Policy. The report is self-contained and printable.

The chosen layout contains:

1. run identity, assessment policy version, and input digest;
2. verdict, autoresearch recommendation, confidence, and `V/A/S` summary;
3. largest bottleneck and bounded reframe;
4. one audit table for research-value dimensions;
5. one audit table for autoresearch-suitability dimensions;
6. information gaps; and
7. an evidence appendix with trusted paths, locators, problem excerpts, and the
   score formula.

### Assessment reader

The problem page queries the local service directly. The service scans and
caches assessment directories, while immutable files remain the source of
truth. Losing the in-memory cache only causes a rescan.

This avoids a second generated index and makes state changes immediately
visible. When the local endpoint is absent, as in the static showcase, the
client renders an unavailable state rather than repeatedly retrying.

### Problem-page UI

Place one full-width qualification panel after the problem header and before
attempts. It is visually important but separate from the lifecycle badge.

The panel supports:

- never assessed: explanation and `Run assessment`;
- queued: queue position;
- running: elapsed time and a coarse current stage;
- needs input: every resolver alternative, with no preselected choice;
- completed: verdict, recommendation, confidence, `V/A/S`, bottleneck, rerun,
  and detailed-report link;
- failed or interrupted: concise reason, diagnostic-log link, and retry; and
- stale: old result remains readable but the primary action requests a new run.

Polling is sufficient for the first version. No hidden reasoning or raw command
stream is rendered in the page.

## Structured result contract

Codex returns one strict envelope with all fields required:

```json
{
  "outcome": "assessment",
  "language": "en",
  "knowledgeResolution": {
    "query": "...",
    "status": "match",
    "topic": "knowledge/example/index.qmd",
    "orderedFiles": ["knowledge/index.qmd", "knowledge/example/index.qmd"]
  },
  "assessment": {},
  "clarification": null
}
```

`outcome` is `assessment` or `needs_input`. Cross-field validation requires
exactly one of `assessment` and `clarification` to be non-null.

An assessment contains:

- one normalized problem sentence;
- verdict label (`DO_NOW`, `REFRAME`, `NOT_AUTORESEARCH`, or `DEFER`);
- autoresearch recommendation (`proceed`, `reframe`, `reject`, or `defer`);
- provisional flag and possible verdict labels;
- research-value, autoresearch-suitability, and harmonic-combined score
  intervals, each with `min`, `estimate`, and `max`;
- confidence level and rationale;
- every weighted dimension with stable ID, 0–5 score interval, evidence state
  (`supported`, `inferred`, or `unknown`), rationale, and evidence references;
- exactly one largest bottleneck;
- exactly one bounded reframe or explicit absence; and
- only information gaps capable of changing the verdict.

Unknown scores remain intervals rather than becoming zero. The host recomputes
weighted totals, harmonic score, bands, and verdict consistency instead of
trusting model arithmetic.

For `needs_input`, clarification contains the original resolver query and every
alternative's page, topic, title, and match kind. The page requires an explicit
choice. That choice creates a new child run whose `selection.json` points to the
clarification run. The child prompt names the user's chosen candidate, reruns
the resolver using the exact selected title, and reads the returned complete
bundle before scoring.

## Local API

All endpoints are exposed only through the development proxy:

| Method and path | Purpose |
|---|---|
| `POST /__local/assessments/jobs` | Start or return the active job for one problem ID. |
| `GET /__local/assessments/problems/{id}` | Return current job, latest summary, staleness, and run history. |
| `GET /__local/assessments/jobs/{run-id}` | Poll one run's status and coarse stage. |
| `POST /__local/assessments/jobs/{run-id}/selection` | Select one exact advertised resolver alternative and create a child job. |
| `GET /__local/assessments/reports/{problem-id}/{run-id}` | Serve one validated stored report. |
| `GET /__local/assessments/logs/{problem-id}/{run-id}` | Serve local diagnostics for failed or interrupted jobs. |

Request bodies have small fixed limits. IDs are validated before filesystem
resolution, canonical paths must remain under the expected problem, staging, or
schema roots, and a selection must exactly match an alternative recorded in the
parent run. Diagnostic logs are returned as plain-text attachments, never
interpreted as HTML.

## Lifecycle and failure handling

```text
preflight -> queued -> running -> completed
                              -> needs-input -> selected child run
                              -> failed
                 shutdown    -> interrupted
completed + changed input    -> stale presentation
```

- Missing CLI, missing authentication, missing skill, or invalid problem files
  fail preflight with an actionable message.
- Nonzero exit, timeout, malformed JSONL, missing final response, invalid schema,
  invalid arithmetic, or report-render failure creates a failed diagnostic run
  without a formal assessment or HTML report.
- There is no automatic model retry. The user explicitly starts a fresh run.
- A completed report is never deleted or overwritten by a rerun.
- A `NOT_AUTORESEARCH` recommendation is still a completed assessment, not a
  failed job and not a lifecycle rejection.

## Staleness

`input.json` records hashes of `problem.json`, `problem.md`, the assessment
skill, and the output schema, plus the resolver query and result used for the
assessment. For a matched result it records the ordered bundle paths and hashes.

When reading a report, the service:

1. compares the problem and policy hashes;
2. reruns the same resolver query;
3. compares status, topic, and ordered paths; and
4. for a match, compares every bundle file hash.

Any difference marks the report stale. An unrelated knowledge-tree change that
does not alter the resolver result or selected bundle does not.

## Security and trust boundary

- Listen only on loopback and require the proxy-injected capability token.
- Spawn with `shell: false`; never interpolate request data into a command.
- Give Codex a read-only sandbox and an ephemeral session.
- Treat `knowledge/**/*.qmd` as the only trusted research authority. A match
  must include the full ordered bundle; ambiguity requires user selection;
  no-match leaves evidence-dependent fields unknown.
- Never fall back to `drafts/` or treat `literature/` as learned knowledge.
- Validate every model result before it reaches storage or rendering.
- Escape report content and serve no model-authored HTML.
- Do not publish problem assessments in the static showcase or knowledge site.
- Keep raw events and diagnostics local to the problem record; never expose them
  through a deployed route.

## Verification

### Unit tests

- JSON Schema acceptance and cross-field rejection.
- Score intervals, weighted totals, harmonic score, bands, and verdict checks.
- Stable dimension IDs and evidence-source validation.
- Problem and run ID validation, canonical containment, and selection matching.
- HTML escaping, CSP, required sections, and absence of executable markup.
- Resolver/bundle and policy staleness calculations.

### Runner and service tests

- A fake Codex executable verifies the exact argument array, fixed working
  directory, read-only sandbox, environment handling, JSONL parsing, and
  30-minute timeout behavior without calling real Codex.
- Queue tests cover FIFO order, global concurrency one, duplicate suppression,
  clarification child runs, and cleanup on signals.
- Artifact tests cover atomic publication, completed/failed/interrupted shapes,
  immutable history, and restart recovery.
- API tests cover capability authentication, size limits, path traversal,
  unknown IDs, invalid transitions, and missing local service behavior.

### UI and end-to-end tests

- Component/render tests cover every panel state, advisory wording, rerun, and
  static-unavailable presentation.
- A browser test starts the local service with a fake Codex executable, presses
  the problem-page button, observes polling, and opens the final HTML report.
- A second browser path exercises resolver clarification and explicit choice.
- Normal automated tests never invoke real Codex or consume account quota. One
  documented manual smoke test uses the installed authenticated CLI.

## Dependencies and delivery order

Implementation depends on the `assess-research-problem` skill from PR #3 being
available in the branch. The implementation should land in this order:

1. merge or rebase onto the skill and current problem-page work;
2. implement and test the structured assessment contract;
3. implement artifact storage and deterministic report rendering;
4. implement the Codex adapter and job manager;
5. expose the loopback API and development proxy;
6. add the problem-page client panel; and
7. complete fake-CLI integration, browser, and manual smoke verification.

No unresolved product decisions remain in this design.
