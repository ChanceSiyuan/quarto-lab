# Expanded Surface Demo Design

## Goal

Update the M1 rotated surface-code showcase so the committed final result covers distances `3`, `5`, and `7` across physical error rates `0.001`, `0.002`, `0.005`, `0.01`, and `0.02`.

## Context

The current M1 demo proves the search loop, report generation, and Zoo promotion path, but the committed `m1-demo` run only evaluates d=3 at two physical error rates. The benchmark task already contains more rates, but autoresearch currently selects only the representative p value plus the promotion-rule p value. That makes the final report too small to inspect distance scaling.

## Design

Use the existing `rotated-surface-baseline` campaign as the M1 final showcase and replace its committed demo artifacts with an expanded matrix:

- Candidate distances: one primary candidate each for d=3, d=5, and d=7.
- Error rates: `0.001`, `0.002`, `0.005`, `0.01`, `0.02`.
- Decoder and task: keep the existing suite and primary decoder contract, so the result remains an M1 search-layer demonstration rather than a decoder comparison.
- Run identity: keep `m1-demo` as the final committed showcase path so docs and PR review point to one canonical result.

Autoresearch should evaluate the full task `p_list` for each candidate. Promotion rules may still add a p value if it is not already in the task, but they should no longer narrow the evaluation to only representative and promotion points.

## Source Records

Update source JSON records rather than only hand-editing artifacts:

- `benchmarks/tasks/rotated-memory-x-cdep-v1.json` gets the full five-rate `p_list`.
- `campaigns/examples/rotated-surface-baseline/search_space.json` includes d=3, d=5, and d=7 showcase candidates.
- Zoo instance records are present for d=5 and d=7 if the evaluation path needs curated finite-size artifacts.

## Tests

Follow TDD for behavior changes:

- Add a failing unit test that shows autoresearch p selection includes every task p value and still preserves a promotion-rule p value only when it is extra.
- Add source-data tests that pin the example campaign to distances `3`, `5`, `7` and task p values `0.001`, `0.002`, `0.005`, `0.01`, `0.02`.
- Update run CLI fake `rsinter` expectations so the expanded matrix is exercised without needing the real decoder binary in unit tests.

## Verification

The final verification should include:

- Focused tests touched by the behavior and source-record changes.
- Full `PYTHONPATH=src python3 -m pytest -q`.
- `PYTHONPATH=src python3 -m autoqec_search.cli validate --root .`.
- A sanity check that the committed M1 report contains d=3, d=5, d=7 and all five p values.

## Non-Goals

This update does not add decoder comparisons, new search algorithms, threshold fitting, or a new report UI. The goal is a larger and more informative M1 final result using the existing pipeline.
