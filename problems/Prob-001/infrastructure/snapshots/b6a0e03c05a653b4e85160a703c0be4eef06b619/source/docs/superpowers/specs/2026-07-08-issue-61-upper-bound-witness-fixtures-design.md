# Issue 61 Upper-Bound Witness Fixtures Design

Issue: #61, "[M3] Add upper-bound witness finder known-answer fixtures"

## Context

`verify_css_upper_bound_witness()` in `src/autoqec_search/structure.py` is the source of truth for AutoQEC witness validation. Existing tests already use a compact 4-column CSS example:

- `hx = [[1, 1, 0, 0]]`
- `hz = [[0, 0, 1, 1]]`

This example admits a valid X-like witness `[0, 0, 1, 1]`, a valid Z-like witness `[1, 1, 0, 0]`, stabilizer-row-space negative controls, and vector-length mismatch negative controls without large quantum Tanner matrices.

## Chosen Approach

Create a committed fixture catalog under `benchmarks/fixtures/upper-bound-witness/`.

Other approaches considered:

1. Generate fixtures inside tests. This would keep the repository smaller, but later wrapper and CLI tests would not have stable file paths to reuse.
2. Store only qec-code-style payloads. This would miss the existing AutoQEC verifier contract and force later tests to recreate witness examples.
3. Use a large realistic code family fixture. This would be closer to production data, but it is unnecessary for known-answer unit tests and would make fixtures harder to inspect.

The committed catalog is the best fit because the issue asks for stable shared fixtures, tiny inputs, valid and invalid AutoQEC witnesses, qec-code-style result payloads, and a manifest for later reuse.

## Fixture Layout

The catalog will use these files:

- `benchmarks/fixtures/upper-bound-witness/hx.json`
- `benchmarks/fixtures/upper-bound-witness/hz.json`
- `benchmarks/fixtures/upper-bound-witness/manifest.json`
- `benchmarks/fixtures/upper-bound-witness/autoqec/*.json`
- `benchmarks/fixtures/upper-bound-witness/qec-code/*.json`

The shared `hx.json` and `hz.json` files use `dense_binary_matrix`, matching `matrix_data()` and existing matrix payload conventions. AutoQEC witness files use the current verifier payload shape: `basis` plus `vector`. qec-code result files use the documented random-window upper-bound shape: `status`, `method`, `bound_type`, `upper_bound`, `logical_class`, `witness.x`, `witness.z`, `witness.weight`, `options`, and `provenance`.

## Manifest Contract

Each manifest entry records:

- `id`
- `payload_kind`: `autoqec-witness` or `qec-code-result`
- `path`
- `basis`
- `expected_weight`
- `expected_verifier_status`
- `expected_reason` for invalid AutoQEC witness entries
- `expected_contract_status` and `expected_rejection_reason` for qec-code result entries

The manifest also records the shared `hx_path` and `hz_path` so tests and later wrappers can resolve inputs without hard-coding the catalog shape.

## Required Cases

AutoQEC witness entries:

- Valid X-like witness: basis `x`, vector `[0, 0, 1, 1]`, weight 2.
- Valid Z-like witness: basis `z`, vector `[1, 1, 0, 0]`, weight 2.
- Stabilizer-row-space witness: basis `x`, vector `[1, 1, 0, 0]`, expected verifier reason `in_stabilizer_row_space`.
- Length mismatch witness: basis `x`, vector `[0, 0, 1]`, expected verifier reason `length_mismatch`.

qec-code-style result entries:

- Valid completed X-like random-window upper-bound payload.
- Valid completed Z-like random-window upper-bound payload.
- Invalid payload with `logical_class == "mixed"`.
- Invalid payload where `upper_bound != witness.weight`.
- Invalid payload where `witness.x` and `witness.z` widths differ.
- Invalid payload with non-binary witness entries.
- Malformed payload missing the `witness` object.

## Tests

Extend `tests/test_search_upper_bound_witness.py` so it loads the committed manifest and exercises the fixture catalog:

1. Load shared `hx.json`, `hz.json`, and each manifest entry.
2. Verify all AutoQEC witness entries through `verify_css_upper_bound_witness()`.
3. Assert valid X-like and Z-like witness weights exactly equal 2.
4. Assert negative verifier fixtures return their documented reasons, including `length_mismatch`.
5. Validate the qec-code-style completed payload contract for valid entries.
6. Validate negative qec-code-style entries are classified with their manifest rejection reasons.

The qec-code checks stay test-local. This issue does not add qec-code conversion or witness search production code.

## Out of Scope

- Running qec-code.
- Searching for witnesses.
- Adding qec-code-to-AutoQEC conversion logic.
- Changing `verify_css_upper_bound_witness()` behavior.
