# Issue 66 Quantum Tanner Witness Attachment Design

## Context

Issue #66 builds on the generated quantum Tanner candidate flow from issues
#55-#60 and the single-candidate `find-upper-bound-witness` command from
#65. Generated quantum Tanner search spaces currently include catalog-backed
candidate specs, but candidates without an `upper_bound_witness_path` are
skipped by the autoresearch screening gate.

## Chosen Approach

Add a batch witness attachment command that reads either a campaign id or an
explicit search-space path, loads the supplied fixture catalog, runs the
existing qec-code random-window upper-bound wrapper for each catalog-backed
candidate, verifies the converted CSS witness against the normalized finite
CSS matrices, writes deterministic witness files, and atomically emits an
updated search-space file plus `witness_finder_summary.json`.

This keeps the batch step separate from candidate generation and autoresearch
runs. It also reuses the existing qec-code result validation and CSS witness
verification path so upper-bound witnesses remain upper-bound screening inputs,
not exact distance evidence.

## Alternatives Considered

1. Inline witness finding into `generate-quantum-tanner-candidates`. This would
   make one command convenient, but it couples candidate generation to a slower
   and more failure-prone qec-code search stage.
2. Shell out to the single-candidate CLI for each candidate. This reuses the
   operator interface, but it makes error classification and atomic search-space
   updates harder to test.
3. Add a Python batch module behind a new CLI command. This is the selected
   design because it shares the same lower-level conversion functions while
   giving deterministic per-candidate summary records.

## Interface

Command:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli attach-quantum-tanner-witnesses \
  --root . \
  --campaign quantum-tanner-autoresearch \
  --fixture-catalog campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json \
  --witness-dir campaigns/examples/quantum-tanner-autoresearch/witnesses \
  --basis x \
  --qec-code-bin /path/to/qec-code \
  --iterations 1000 \
  --restarts 8 \
  --seed 12345 \
  --timeout-seconds 300
```

`--search-space` may be used instead of `--campaign`. `--out-search-space`
and `--summary-out` are optional; without them the command updates the input
search space and writes `witness_finder_summary.json` under `--witness-dir`.
`--require-all` and `--fail-on-skipped` are equivalent strict modes that return
nonzero if any candidate is skipped or failed. `--force` allows overwriting an
existing search-space witness path with the deterministic batch path.

## Data Flow

The batch step loads the search space and fixture catalog from safe
repository-relative paths. It indexes catalog entries by `candidate_id`, then
processes candidate specs in search-space order. For each catalog-backed
candidate, it resolves and validates the catalog entry, runs qec-code against
the entry's `hx.json` and `hz.json`, converts the qec-code payload with the
existing CSS upper-bound witness conversion function, verifies the requested
basis, writes `witnesses/<candidate-id>-upper-bound-witness.json`, and only
then adds `upper_bound_witness_path` to the output search-space candidate spec.

Candidates with an existing `upper_bound_witness_path` are skipped unless
`--force` is set. Candidates with missing artifacts, incompatible basis, qec-code
failures, malformed output, or verification failures are recorded in the
summary and are not updated in the emitted search space.

## Summary Contract

The summary is deterministic JSON:

```json
{
  "schema_version": 1,
  "campaign_id": "quantum-tanner-autoresearch",
  "basis": "x",
  "counts": {"attached": 2, "skipped": 0, "failed": 0},
  "candidates": [
    {
      "candidate_id": "quantum-tanner-toric-d4",
      "status": "attached",
      "reason": "verified_upper_bound_witness",
      "basis": "x",
      "weight": 4,
      "witness_path": "campaigns/examples/quantum-tanner-autoresearch/witnesses/quantum-tanner-toric-d4-upper-bound-witness.json",
      "search_space_updated": true
    }
  ]
}
```

Skipped and failed records have `weight: null`, `witness_path: null` unless an
existing witness path was deliberately preserved, and `search_space_updated:
false`.

## Error Handling

Default mode writes the summary and updated search space even when individual
candidates are skipped or failed. Strict mode returns nonzero for any skipped
or failed candidate after writing the summary. Unexpected command-level input
errors still return nonzero immediately.

Witness and search-space writes use temporary files followed by rename. The
search-space entry is updated only after witness conversion, verification, and
the witness file write have all succeeded.

## Verification

Add regression coverage for:

- two generated `[4, 6]` candidates receiving deterministic witness files and
  `upper_bound_witness_path` fields;
- `validate --root /tmp/autoqec-generated-qt-root` passing after attachment;
- missing `hz.json` producing a failed or skipped summary record without a
  search-space witness update;
- incompatible Z-like qec-code output for `--basis x` producing a failed
  summary record and strict-mode nonzero exit.
