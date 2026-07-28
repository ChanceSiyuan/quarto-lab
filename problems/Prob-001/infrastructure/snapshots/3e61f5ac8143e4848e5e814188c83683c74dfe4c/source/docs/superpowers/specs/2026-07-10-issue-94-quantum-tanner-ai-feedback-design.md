# Issue 94: Quantum Tanner AI Feedback Report Design

## Goal

Add a compact feedback-report command for completed quantum Tanner AI proposal
rounds. The command writes machine-readable JSON and self-contained HTML that
can be handed to a future offline proposal model without copying the full run
directory.

## Scope

The CLI command is `summarize-quantum-tanner-ai-feedback`. It accepts a
repository root, a completed quantum Tanner autoresearch run directory, optional
AI proposal-ingest summary JSON, optional surface-copy comparison JSON, and
explicit JSON/HTML output paths.

The command reads only existing artifacts. It does not generate proposals, call
a model, materialize candidates, compute witnesses, complete observables, run
decoders, or modify the run directory.

## Approaches Considered

1. Build a focused feedback model from `build_report_model(...)`, then enrich
   it with optional ingest and surface-copy artifacts. This is the chosen
   approach because the report model already validates completed run artifacts,
   exposes candidates, screening, upper-bound evidence, and LER points, and
   keeps this feature as a small summarizer.
2. Parse run directories independently. This would duplicate report/loading
   validation and risk drifting from existing `report.html` semantics.
3. Extend `prepare-quantum-tanner-ai-batch` to scan runs directly. This would
   couple prompt-bundle preparation to historical run summarization and make it
   harder to reuse the feedback report as a standalone artifact.

## Data Flow

1. Resolve `--root`, `--run`, `--proposal-summary`, `--surface-copy`,
   `--out-json`, and `--out-html`. Relative paths are resolved the same way as
   neighboring CLI commands: run/proposal/surface inputs are relative to the
   provided root unless already absolute; outputs are written exactly where
   requested.
2. Call `build_report_model(root, run_root)` to load and validate the run. The
   feedback command uses this model as the source for run provenance,
   candidates, manifests, screening status, distance/upper-bound payloads, and
   completed LER points.
3. If a proposal-ingest summary is supplied, read accepted, rejected, and
   duplicate proposal records. Accepted records map to candidates by
   `candidate_id` when present, otherwise by `proposal_id` if it matches a run
   candidate id. Any accepted proposal record that cannot be mapped to the run
   candidates fails with `proposal feedback candidate mismatch`. Rejected and
   duplicate records are included as rejected proposal feedback entries even
   when they never materialized as run candidates.
4. If a surface-copy JSON is supplied, read its `rows` array and group rows by
   `candidate_id`. Each candidate gets a compact `surface_copy` object with
   comparison status, reason, and numeric copied-surface fields from the
   matching p=0.001 row.
5. For every run candidate, emit one candidate feedback object containing:
   candidate id, proposal id/fingerprint when available, validation status,
   materialization status, screening status and reason, `n`, `k`, upper-bound
   evidence, p=0.001 LER rows, surface-copy result, and rejection reasons.
6. For proposal records that failed validation/duplicate screening before
   materialization, emit compact rejected-proposal entries with proposal id,
   proposal index, typed reason, and message.
7. Write JSON first and HTML second. The HTML embeds the same JSON in an
   `application/json` script tag and uses only inline CSS so it is offline-safe.

## JSON Contract

The root object contains:

- `schema_version`: `1`
- `report_kind`: `quantum-tanner-ai-feedback`
- `run`: campaign id, run id, mode, generated-at, git SHA, and run path
- `counts`: candidate, accepted proposal, rejected proposal, duplicate
  proposal, p=0.001 LER row, and surface-copy row counts
- `candidates`: compact per-candidate feedback objects
- `rejected_proposals`: proposal records that did not become run candidates
- `next_prompt_context`: short model-facing guidance with accepted
  fingerprints, rejection kinds, candidate ids with observed p=0.001 LER, and
  surface-copy notes

Per-candidate numeric fields preserve the exact JSON values read from artifacts
where practical: `p`, `logical_error_rate`, `shots`, `errors`, `upper_bound`,
`n`, `k`, and surface-copy numeric fields. Existing report-model `ler` values
are renamed to `logical_error_rate` for this feedback contract.

## Status Semantics

`validation_status` reflects proposal ingest when available: `accepted`,
`rejected`, `duplicate`, or `unknown`. Run candidates without proposal-ingest
records keep `unknown` rather than inventing an ingest outcome.

`materialization_status` is `present` for run candidates with a candidate
artifact. Pre-run rejected proposals use `not_materialized`.

`screening_status` is copied from `screening.json` when present. A missing
screening artifact is represented as `unknown` and carries a rejection reason
instead of crashing the whole report, because proposal summaries may include
records that failed before run materialization.

`surface_copy.status` is copied from the optional comparison row when present;
without a surface-copy input, the field is `{"status": "not_provided"}`.

## Failure Handling

Malformed JSON, non-object inputs, unknown run roots, and invalid run artifacts
reuse `SearchIntegrityError` behavior and produce nonzero CLI exits.

The command fails if supplied proposal feedback claims an accepted/materialized
candidate that does not exist in the completed run. The error text contains:

```text
proposal feedback candidate mismatch
```

Rejected and duplicate proposal records are not required to exist in the run.
They are included precisely because they failed before or during proposal
screening.

## Testing

Add `tests/test_search_quantum_tanner_ai_feedback.py` covering:

- a positive completed-run fixture with one admitted candidate, one rejected or
  skipped candidate, proposal-ingest summary records, and surface-copy rows;
- JSON assertions for at least one candidate containing `p: 0.001`,
  `upper_bound`, `logical_error_rate`, and a `surface_copy` object;
- HTML assertions that the candidate id appears and no network asset
  references such as `http://`, `https://`, `//cdn`, `src=`, or `href=` are
  emitted;
- a negative control where proposal summary accepted records reference a
  candidate id absent from the run and the CLI exits nonzero with
  `proposal feedback candidate mismatch`.

Run the two issue-specified focused tests and the full
`PYTHONPATH=src python3 -m pytest` suite.

## Self-Review

- No placeholders remain.
- The design reuses validated report and surface-copy models instead of
  re-parsing every run artifact independently.
- The command is read-only with respect to completed runs.
- Exact distance remains separate from upper-bound evidence.
- Pre-run rejected proposals are preserved as typed records, while inconsistent
  accepted proposal/run candidate ids fail conservatively.
