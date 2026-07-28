# Issue 39 Quantum Tanner Fixture Catalog Design

Issue: #39, "[M1] Add a quantum Tanner autoresearch fixture catalog"

## Context

The search layer already has campaign, benchmark, and result validation, and it resolves campaign candidates through Zoo-style finite CSS instance metadata. The quantum Tanner fixtures named in the issue already exist under `benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-*`, but their `instance.json` files are distance-ladder records with fields such as `instance_id`, `n`, `k`, and `expected_distance`. They are not Zoo-style `finite_css_instance` records.

The M1 catalog will pin exactly the smoke fixtures requested by the issue:

- `quantum-tanner-toric-d4`
- `quantum-tanner-toric-d6`
- `quantum-tanner-toric-d8`

The source matrices are sparse-row JSON files, so the adapter must validate that `hx` and `hz` point to binary matrices with matching column counts and must normalize them into the dense matrix payloads expected by current search-layer structure and generic CSS paths.

## Clarifying Decisions

Because this Agent Desk run is non-interactive, these decisions are resolved automatically from the issue text and repository context.

1. The catalog is a pinned explicit fixture list, not a generator.
2. The catalog lives at `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json`.
3. The raw distance-ladder records remain unchanged.
4. `search_ready: true` means the catalog adapter can produce a normalized search-layer candidate view. The source fixture still requires adaptation; this will be recorded explicitly with `adaptation: "catalog-normalized-finite-css-instance"`.
5. No full campaign or search space is added in this issue, because the requested M1 output is the fixture catalog plus loader/adapter.

## Approaches Considered

Recommended: add a focused catalog and adapter module in `src/autoqec_search/quantum_tanner_catalog.py`. This keeps the fixtures pinned, avoids pretending distance-ladder `instance.json` records are Zoo instances, and gives tests a narrow public API for validation and normalization.

Alternative: copy the fixtures into `zoo/codes/.../instances/...` as promoted-style instances. This would make `resolve_campaign_candidate_spec` work directly, but it would blur curated Zoo records with M1 smoke fixtures and create extra source-of-truth files outside the issue scope.

Alternative: mark all fixtures `search_ready: false`. This is safe but underdelivers the adapter requirement and would not prove that the M1 smoke candidates can become search-layer candidates.

## Architecture

`fixture_catalog.json` is the durable pin. Each entry records the stable `candidate_id`, `code_id`, `n`, `k`, `distance`, `hx`, `hz`, `source_fixture_path`, `source_instance`, `provenance`, `search_ready`, and `adaptation`.

`autoqec_search.quantum_tanner_catalog` owns the read/validate/normalize boundary:

- `load_quantum_tanner_fixture_catalog(root, catalog_path=...)` loads and validates the catalog.
- `validate_quantum_tanner_fixture_catalog(root, catalog_path=...)` checks duplicate ids, required fields, safe paths, matrix existence, and matching matrix widths.
- `normalize_quantum_tanner_fixture_entry(root, entry)` returns a Zoo-style finite CSS instance view with `id`, `code_id`, `parameters`, `derived_properties`, and `artifacts`.
- `resolve_quantum_tanner_fixture_entry(root, entry, campaign_id="quantum-tanner-autoresearch")` returns a `ResolvedCandidate` with dense `hx` and `hz` payloads.

The adapter will reject malformed inputs early with `SearchIntegrityError`, matching existing search-layer error handling.

## Data Flow

1. Catalog entry points at a source fixture root plus its `hx.json`, `hz.json`, `instance.json`, and `quantum_tanner_specs/*.json` provenance.
2. Loader validates the entry shape and repo-relative paths.
3. Matrix validation reads sparse-row matrices, checks `format == "sparse_rows"`, positive integer `num_cols`, list rows, integer column indices, and matching `hx`/`hz` column counts.
4. Normalization maps distance-ladder fields into search-layer instance fields:
   - `id`: catalog `candidate_id`
   - `code_id`: catalog `code_id`
   - `instance_kind`: `finite_css_instance`
   - `matrix_format`: `dense_binary_json`
   - `parameters`: distance, construction family, source fixture id, qec-code spec, and quantum Tanner spec path
   - `derived_properties`: `n`, `k`, `distance`, `bound_type`, `mx`, and `mz`
   - `artifacts`: `{"hx": "hx.json", "hz": "hz.json"}`
5. Candidate resolution wraps that normalized instance with `CandidateInput` and dense matrix payloads for search evaluation consumers.

## Error Handling

The loader rejects duplicate `candidate_id` values, missing required fields, unsafe paths, missing matrix files, non-sparse source matrices, non-binary sparse rows, and `hx`/`hz` column mismatches. Errors use concrete path or candidate id context so corrupted catalogs are actionable.

## Testing

Add `tests/test_search_quantum_tanner_catalog.py` with exactly the five behaviors from the issue:

1. The catalog contains exactly the pinned M1 smoke entries and required fields.
2. Every listed `hx` and `hz` exists and has matching binary matrix column counts.
3. Every `search_ready: true` entry normalizes into a search-layer candidate with `id`, `code_id`, `parameters`, `derived_properties`, and `artifacts`.
4. A corrupted catalog with duplicate `candidate_id` values is rejected.
5. A corrupted catalog with a missing `hx` path is rejected.

Verification commands:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_catalog.py
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m pytest
```

## Out of Scope

No open-ended quantum Tanner generator is added. No new distance or LER computation is run. No curated Zoo promotion is performed.
