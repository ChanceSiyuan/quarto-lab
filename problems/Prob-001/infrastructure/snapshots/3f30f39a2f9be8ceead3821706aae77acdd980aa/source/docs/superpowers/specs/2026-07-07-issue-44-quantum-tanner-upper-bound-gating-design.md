# Issue 44 Quantum Tanner Upper-Bound Gating Design

Issue: #44, "[M3] Gate quantum Tanner candidates by upper-bound witnesses before rbposd LER runs"

## Context

The repository has the pieces this issue depends on:

- #39 added the pinned quantum Tanner fixture catalog and a normalizer that can resolve catalog entries into `ResolvedCandidate` objects.
- #40 added the quantum Tanner rbposd suite `quantum-tanner-rbposd-p001-v1`, whose task has exactly `p_list: [0.001]`.
- #42 added upper-bound distance payload support through run artifacts, reports, frontiers, and promotion guards.
- #43 added `verify_css_upper_bound_witness`, which validates CSS upper-bound witnesses and returns a `bound_type: "upper"` distance payload.

What is missing is the runnable campaign/search-space wiring and the run-loop gate that records screening outcomes before spending rsinter/rbposd time.

## Non-Interactive Decisions

This Agent Desk run is non-interactive, so the standing policy resolves choices from the issue text and repository context.

1. Add a real `quantum-tanner-autoresearch` campaign and explicit search space backed by the fixture catalog. The current catalog alone is not loaded by `autoqec-search run`.
2. Keep `candidate.json` schema unchanged. Screening state lives in `screening.json`.
3. Admit candidates with a verified valid upper-bound witness or valid upper-bound payload. Skip candidates with no upper-bound input. Mark invalid witnesses/payloads failed with the verifier/loader reason.
4. For the M1 smoke campaign, use the d4 candidate as the admitted path, d6 as missing-payload skipped, and d8 as invalid-witness failed.
5. Attach the admitted X witness as an explicit logical observable for the CSS X task, so the existing rsinter parser records `logical_failure_aggregation: "any_logical"`.
6. Treat only the quantum Tanner p001 suite as gated. Existing campaigns continue to evaluate as before.

## Approaches Considered

Recommended: integrate screening into `run_autoresearch` for the quantum Tanner suite. Add a small screening helper that reads candidate witness/payload inputs, writes `screening.json`, and passes the upper-bound distance payload into evaluation for admitted candidates. This reuses the current run, report, manifest, and validation conventions.

Alternative: add a separate screening CLI. This would be easier to isolate, but it would split run state across two workflows and contradict the issue guidance to reuse existing run/report conventions.

Alternative: add new `candidate.json` statuses for skipped/failed screening. This would make status visible in one file, but it requires schema and loader changes with little benefit because the issue explicitly allows a separate `screening.json`.

## Architecture

Add a catalog-backed candidate kind to `search-space.schema.json`:

- `candidate_id`
- `code_family`
- `fixture_catalog_path`
- `provenance`
- optional `upper_bound_witness_path`
- optional `upper_bound_payload`
- optional `upper_bound_payload_path`

`run_loop` gets a resolver wrapper that detects `fixture_catalog_path`, loads the matching catalog entry via `resolve_quantum_tanner_fixture_entry`, and preserves the candidate spec's screening inputs for the gate. Standard Zoo and explicit-instance candidates keep the existing resolver.

Add `autoqec_search.screening` for the screening boundary:

- `is_quantum_tanner_screened_run(suite) -> bool`
- `screen_upper_bound_candidate(root, candidate, candidate_spec, task) -> ScreeningDecision`
- `write_screening(candidate_root, decision) -> None`

The decision carries the required JSON fields:

- `screening_status`: `admitted`, `skipped`, or `failed`
- `distance_bound_type`
- `distance_upper_bound`
- `reason`

For admitted candidates, the verifier's upper-bound distance payload is passed into `evaluate_resolved_candidate_into_run` through a new optional `distance_payload_override` argument. That keeps `distance.json` upper-bound typed even when the normalized catalog instance contains an exact fixture distance.

For skipped or failed candidates, the run leaves existing placeholder/crash manifests schema-valid, writes `screening.json`, appends a visible experiment-log row, and records a strategy event. Resume logic treats `screening_status` of `skipped` or `failed` as terminal.

## Data Flow

1. The run skeleton creates placeholder candidate directories for all quantum Tanner candidates.
2. For each proposed candidate in a screened quantum Tanner run, the run loop resolves the catalog candidate.
3. The screening helper loads and verifies the candidate's witness or upper-bound payload.
4. The run loop writes `screening.json`.
5. If admitted, evaluation runs rsinter only at the suite's selected p value, exactly `0.001`, with the upper-bound distance payload.
6. If skipped or failed, no rsinter evaluation is invoked for that candidate.
7. Aggregates, strategy trace, run summary, report model, and workspace validation keep the candidate visible.

## Error Handling

Missing screening input is a non-crashing skipped candidate with reason `missing_upper_bound_payload`.

Verifier failures are failed screening candidates with the machine-readable reason from #43, such as `not_in_kernel`.

Malformed upper-bound payloads are failed screening candidates with the loader error message.

Suite drift to `p=0.01` remains a search-integrity error before the run uses the suite.

## Testing

Add `tests/test_search_quantum_tanner_run_gating.py` with five issue-level tests:

1. A valid upper-bound witness admits d4 and writes a fake rbposd manifest at exactly `p=0.001`.
2. The admitted manifest records `logical_failure_aggregation: "any_logical"`.
3. A missing upper-bound input skips d6 and exposes the reason through `screening.json` and the report model.
4. An invalid witness fails d8 with the verifier reason and does not call rsinter for that candidate.
5. A corrupted quantum Tanner suite containing `p=0.01` is rejected, and the resulting valid run artifacts pass `autoqec-search validate`.

Required verification:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_run_gating.py
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m pytest
```

## Out of Scope

No SLURM execution, no new decoders, no Zoo promotion of upper-bound-screened candidates, and no heuristic witness search are added.
