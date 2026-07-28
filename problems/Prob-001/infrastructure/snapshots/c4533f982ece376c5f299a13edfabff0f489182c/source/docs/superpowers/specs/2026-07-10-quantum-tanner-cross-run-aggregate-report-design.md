# Quantum Tanner Cross-Run Aggregate Report Design

Date: 2026-07-10

## Goal

Extend the Quantum Tanner long-running autoresearch launcher so one durable,
human-readable table grows across all attempts in the same `--work-root`.
Every accepted finite-code proposal becomes one row in creation order, including
codes that later evaluate successfully, are skipped, or fail during witness,
distance, observable, or decoder processing.

The aggregate is an append-only research ledger. It does not collapse or merge
rows with similar code content. Duplicate prevention happens before a new AI
proposal is accepted: the next Codex prompt receives the prior candidate history,
and the launcher retains a fingerprint check as an enforcement boundary.

## Scope

The aggregation boundary is one Quantum Tanner launcher `--work-root`.
Continuing that campaign with `--resume` appends to the same aggregate. A new
work root starts a new aggregate and does not depend on machine-global state.

The feature applies to `scripts/run_quantum_tanner_autoresearch.sh` and the
`autoqec_search.quantum_tanner_long_run` workflow. It does not change the
generic `autoqec-search run` report contract or combine unrelated campaigns.

## User-Visible Files

The launcher maintains:

```text
<work-root>/
  aggregate/
    results.jsonl
    report.html
    state.json
  state.json
  cumulative-feedback.json
  rounds/
    ...
```

`aggregate/results.jsonl` is the machine-readable ordered ledger. Each line is
one accepted candidate. New records are appended conceptually and existing
records are never edited, reordered, grouped, or content-deduplicated.

`aggregate/report.html` is regenerated after every aggregate update from the
ledger. Regeneration makes the HTML crash-safe and keeps it valid without
mutating markup in place. The report is self-contained, offline-safe, and
English-only.

`aggregate/state.json` records installed attempt batches and the next append
sequence. It is recovery metadata, not a second source of candidate results.

The launcher prints the aggregate report path when it finishes. The top-level
`state.json` also records the absolute aggregate ledger and report paths so
callers do not need to discover nested run directories.

## Aggregate Row Model

Every JSONL record has `schema_version: 1` and includes:

- append sequence number;
- round number, attempt number, candidate ordinal, and a stable attempt key;
- source commit and record timestamp;
- candidate ID and accepted proposal fingerprint;
- terminal candidate status: `evaluated`, `skipped`, `failed`, or
  `interrupted`;
- the last completed stage and a typed reason when the candidate did not
  evaluate;
- base group name and order;
- A and B generator indices;
- local classical parity-check matrices plus their human-readable code labels;
- CSS `n`, `k`, and rate when available;
- X-distance upper-bound evidence and screening status when available;
- benchmark task, decoder, physical error rate, rounds, errors, shots, LER,
  95% confidence interval, and runtime when available;
- whether the candidate belonged to the frontier of its source run;
- links to the per-run report and construction-definition anchor when those
  artifacts exist.

Missing downstream values remain empty rather than blocking a row. This lets a
proposal that fails after acceptance remain visible with the construction data
known at its last successful stage.

Input proposals rejected during schema or scientific validation are not rows:
they never became accepted finite-code candidates. Their rejection counts stay
in the existing cumulative feedback and attempt diagnostics.

## Collection Boundaries

Candidate collection is a separate module from HTML rendering and from the
launcher state machine:

1. A collector reads the accepted ingestion records, witness summary,
   imported search space, materialized instance artifacts, candidate
   directories, screening records, and benchmark manifests that exist for an
   attempt.
2. It produces one normalized aggregate record for each accepted proposal, in
   the accepted proposal order.
3. An append operation adds the attempt batch after all existing ledger rows.
4. The renderer reads the complete ledger and atomically replaces
   `aggregate/report.html`.

The collector is stage-tolerant. For example, a materialization failure can
still produce a failed row from the ingested proposal, while an rsinter failure
can retain the full construction and screening columns.

An attempt with zero accepted proposals adds no candidate rows. It still
completes normally under the existing launcher semantics.

## Append And Recovery Semantics

The launcher already holds an exclusive lock for the whole work root. Aggregate
updates occur under that lock.

Each row carries its attempt key and candidate ordinal. The independent
`aggregate/state.json` checkpoint records that an attempt batch was installed.
This checkpoint prevents launcher recovery from installing the same attempt
batch twice without mutating a terminal attempt status. It is operational replay
protection, not code-content deduplication: two distinct accepted proposals
remain two rows even if their visible parameters happen to match.

The ledger update uses a sibling temporary file, copies the existing complete
JSONL records, appends the new batch, flushes and fsyncs it, and atomically
replaces `results.jsonl`. The report uses the same write-then-replace pattern.
If interruption occurs between ledger replacement and checkpoint update,
recovery recognizes the already installed attempt key and candidate ordinals,
repairs the checkpoint, and does not append a second operational copy.

Normal exceptions update the attempt to a terminal failure state, collect all
accepted candidates known at that point, refresh the aggregate, and then
propagate the original launcher error. SIGINT and SIGTERM use the existing
signal-safe status update; the next launcher resume reconciles and aggregates
that terminal attempt before creating a new attempt. A hard process kill that
cannot persist terminal state remains visible through existing attempt files
but cannot be classified until an operator resumes or inspects it.

An aggregate failure after an otherwise successful attempt stops the launcher;
resume retries aggregate reconciliation before any new Codex invocation. When
the numerical attempt and aggregate refresh both fail, the launcher preserves
the numerical failure as the primary diagnostic and records the aggregate
failure separately for resume. Aggregate problems therefore cannot silently
drop rows or cause the AI to run with incomplete history.

## AI Duplicate Avoidance

Before each Codex proposal invocation, the launcher derives a compact candidate
history from all aggregate rows. The prompt lists, for each prior accepted
candidate:

- candidate ID and fingerprint;
- base group;
- A and B generator indices;
- local parity-check matrices when each matrix contains at most 64 binary
  entries; otherwise its dimensions and canonical SHA-256 hash;
- final status, including failed and skipped candidates.

The prompt explicitly instructs Codex to inspect this history and propose new
constructions. Failed candidates remain in history because the user requested
that future AI rounds not repeat them.

Prompt guidance is not the enforcement boundary. After ingestion and before
`qec-code` or `rsinter` execution, the launcher compares accepted fingerprints
against all historical aggregate fingerprints. A repeat fails the attempt with
a typed historical-duplicate diagnostic. The aggregate does not append the
rejected repeat because it was not accepted past this boundary.

## HTML Report

The report starts with summary cards for completed rounds, total accepted codes,
evaluated codes, skipped codes, failed/interrupted codes, and source-run
frontier rows. A source-run frontier marker preserves recorded evidence without
performing a new cross-run ranking. The master table has one finite code per row
and retains ledger order.

The columns are:

1. sequence and round/attempt;
2. finite code / candidate;
3. status and reason;
4. base group;
5. A / B generators;
6. local classical code;
7. CSS parameters;
8. code rate;
9. X upper bound;
10. screening;
11. errors / shots;
12. LER;
13. 95% confidence interval;
14. decoding time;
15. source artifacts.

Unavailable values display an em dash. Status badges distinguish evaluated,
skipped, failed, and interrupted rows. A source link opens the corresponding
single-run report; construction links target the relevant definition section
when present. Notes retain the scientific warning that zero observed errors do
not prove a zero logical error rate.

## Integration Point

`quantum_tanner_long_run.run_attempt` remains responsible for stage execution
and status updates. Aggregate collection is invoked at terminal boundaries and
during resume reconciliation, rather than being embedded in individual
materialization or benchmark operations.

The top-level loop refreshes the report after each completed round. Its failure
path refreshes the report after persisting the failure status. Resume performs
aggregate reconciliation before preparing the next AI request, ensuring both
the human report and AI history include every earlier terminal attempt.

The per-run `report.html` and `construction-definitions.html` remain unchanged.
They provide detailed evidence for one numerical run; the aggregate report is
the campaign-level entry point.

## Testing

Unit tests cover:

- normalized rows at ingestion-only, materialized, screened, evaluated,
  skipped, failed, and interrupted stages;
- missing optional artifacts without loss of the accepted candidate row;
- append order across multiple rounds and attempts;
- two distinct rows with matching visible parameters remaining separate;
- replay recovery installing one operational copy of an attempt batch;
- atomic ledger and HTML replacement behavior;
- English-only HTML, required columns, status badges, summary counts, and
  relative artifact links;
- AI history containing evaluated, skipped, and failed fingerprints;
- a historical duplicate failing before `qec-code` and `rsinter` are invoked.

Launcher integration tests use fake Codex, qec-code, and rsinter executables to
prove that:

1. two successful rounds produce one ordered cross-run report;
2. a failed accepted candidate is appended and visible before the launcher
   returns nonzero;
3. resume appends after existing rows without replaying a prior attempt;
4. the next Codex prompt contains the aggregate history;
5. a new work root starts with an empty aggregate;
6. the launcher prints and records the stable aggregate report path.

Documentation tests keep the copy-paste launch and resume commands aligned with
the aggregate output layout.

## Non-Goals

- aggregating across different work roots or machines;
- modifying or deleting earlier candidate rows;
- ranking candidates from incomparable benchmark configurations;
- treating an upper distance bound as an exact code distance;
- including proposals rejected before acceptance as finite-code rows;
- replacing the detailed per-run report or construction-definition pages.
