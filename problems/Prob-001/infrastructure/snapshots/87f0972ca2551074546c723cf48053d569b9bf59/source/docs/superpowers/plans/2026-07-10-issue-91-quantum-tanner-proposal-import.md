# Issue 91 Quantum Tanner Proposal Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import materialized quantum Tanner proposal bundles into explicit-list campaign search spaces while preserving proposal provenance and null exact distance.

**Architecture:** Add a focused importer module that validates #90 materialization bundles, computes stable non-path fingerprints, and writes explicit-instance search-space candidates. Extend search-space/candidate provenance schemas and explicit-instance resolution so proposal-derived instances load with `distance: null`; make workspace validation resolve every explicit `instance_path`.

**Tech Stack:** Python 3 stdlib (`dataclasses`, `hashlib`, `json`, `pathlib`, `tempfile`), existing `autoqec_search` CLI/load/resolver modules, `jsonschema`, pytest subprocess CLI tests with fake qec-code scripts.

## Global Constraints

- Reuse existing explicit-instance candidate semantics; do not introduce a new candidate kind.
- Keep proposal-derived bundles as search artifacts, not curated Zoo source-of-truth records.
- Imported candidates must use `code_family: "quantum-tanner-code"`.
- Unknown exact distance must remain unknown: do not promote upper bounds or hints into `parameters.distance` or `derived_properties.distance`.
- Candidate fingerprints must use proposal/validator fingerprints, CSS dimensions, qec-code spec hash, and output hashes, not transient output paths.
- Reject duplicate proposal fingerprints and duplicate candidate fingerprints by default.
- Preserve existing non-proposal candidates when updating an existing search space.
- `autoqec-search validate --root <workspace>` must schema-validate search spaces and load every explicit `instance_path`.
- Required issue verification includes the three tests in `tests/test_search_quantum_tanner_proposal_import.py`.
- Required Agent Desk verification includes `PYTHONPATH=src python3 -m pytest`.

---

## File Structure

- Create `tests/test_search_quantum_tanner_proposal_import.py`: RED tests for import CLI, resolver null-distance behavior, duplicate fingerprints, schema negative control, and temporary-workspace validation.
- Create `src/autoqec_search/quantum_tanner_proposal_import.py`: importer API, materialized bundle validation, stable fingerprinting, duplicate policy checks, and atomic search-space writes.
- Modify `src/autoqec_search/cli.py`: add `import-quantum-tanner-proposal-instances` parser and command route.
- Modify `benchmarks/schemas/search-space.schema.json`: allow required nested proposal provenance on explicit candidates.
- Modify `benchmarks/schemas/candidate.schema.json`: allow the same nested proposal provenance in emitted candidate payloads.
- Modify `src/autoqec_search/eval_candidates.py`: allow explicit proposal-derived instances with null exact distance to resolve without inventing distance.
- Modify `src/autoqec_search/load.py`: during workspace loading, resolve every candidate spec that has `instance_path`.

### Task 1: RED Import Tests

**Files:**
- Create: `tests/test_search_quantum_tanner_proposal_import.py`

**Interfaces:**
- Consumes #90 CLI:
  `python3 -m autoqec_search.cli materialize-quantum-tanner-proposals ...`
- Produces expected #91 CLI:
  `python3 -m autoqec_search.cli import-quantum-tanner-proposal-instances --root <workspace> --campaign quantum-tanner-autoresearch --instance-root <workspace>/proposal-instances --search-space <workspace>/campaigns/examples/quantum-tanner-autoresearch/search_space.json`
- Uses resolver:
  `resolve_campaign_candidate_spec(root, candidate_spec, campaign_id="quantum-tanner-autoresearch")`.

- [ ] **Step 1: Write the failing test file**

Create tests with these helpers:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_PROPOSAL = REPO_ROOT / "tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json"

def _write_fake_qec_code(path: Path) -> Path:
    path.write_text("""#!/bin/sh
set -eu
if [ "${1:-}" = "--version" ]; then printf 'fake-qec-code 1.0\n'; exit 0; fi
if [ "$6" = "hx" ]; then
  printf '%s\n' '{"format":"sparse_rows","num_cols":6,"rows":[[0,1],[2,3]]}'
elif [ "$6" = "hz" ]; then
  printf '%s\n' '{"format":"sparse_rows","num_cols":6,"rows":[[4,5]]}'
else
  echo "unexpected matrix: $6" >&2
  exit 9
fi
""")
    path.chmod(0o755)
    return path
```

The workspace helper must copy `benchmarks/`, create
`campaigns/examples/quantum-tanner-autoresearch/campaign.json`, create an
initial `search_space.json` with one unrelated parameter candidate, and create
`results/search/`.

- [ ] **Step 2: Add positive import/schema/resolution test**

Implement
`test_import_proposal_instances_writes_schema_valid_explicit_search_space`.
It must materialize the valid proposal into `<workspace>/proposal-instances`,
run the import CLI, assert `imported=1`, assert the existing unrelated
candidate is preserved, validate the generated search space with
`Draft202012Validator`, remove one required nested proposal provenance field and
assert schema validation fails, run
`PYTHONPATH=src python3 -m autoqec_search.cli validate --root <workspace>` with
exit code 0, then resolve the imported candidate and assert:

```python
assert candidate.spec.code_family == "quantum-tanner-code"
assert candidate.spec.parameters["distance"] is None
assert candidate.instance["derived_properties"]["distance"] is None
assert candidate.hx["format"] == "sparse_rows"
assert candidate.hz["format"] == "sparse_rows"
assert candidate.spec.provenance["proposal"]["proposal_id"] == "valid-dihedral-d3"
```

- [ ] **Step 3: Add explicit null-distance resolver test**

Implement
`test_import_proposal_instances_resolves_null_distance_candidate`. It imports one
bundle and calls `resolve_campaign_candidate_spec(...)` directly, asserting that
the returned spec and normalized instance both preserve `distance: None` and the
proposal provenance object.

- [ ] **Step 4: Add duplicate-fingerprint rejection test**

Implement `test_import_proposal_instances_rejects_duplicate_fingerprints`.
Materialize one proposal, copy the candidate directory to a second directory,
change only the second bundle's candidate id fields, refresh the copied
`instance.json` hash in `materialization_manifest.json`, and run the import CLI.
Assert nonzero exit and stderr containing `duplicate proposal fingerprint`.

- [ ] **Step 5: Verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_import.py::test_import_proposal_instances_writes_schema_valid_explicit_search_space \
  tests/test_search_quantum_tanner_proposal_import.py::test_import_proposal_instances_resolves_null_distance_candidate \
  tests/test_search_quantum_tanner_proposal_import.py::test_import_proposal_instances_rejects_duplicate_fingerprints \
  -q
```

Expected: FAIL because `import-quantum-tanner-proposal-instances` does not
exist.

### Task 2: Importer Module And CLI

**Files:**
- Create: `src/autoqec_search/quantum_tanner_proposal_import.py`
- Modify: `src/autoqec_search/cli.py`

**Interfaces:**
- Produce:
  `import_quantum_tanner_proposal_instances(root: Path, campaign_id: str, search_space_path: Path, instance_root: Path | None = None, manifest_path: Path | None = None, duplicate_policy: str = "reject") -> ProposalImportSummary`
- CLI flags:
  `--root`, `--campaign`, mutually exclusive `--instance-root` / `--manifest`,
  `--search-space`, `--duplicate-policy reject`.

- [ ] **Step 1: Implement importer dataclasses and path helpers**

Add immutable dataclasses for `ProposalImportCandidate` and
`ProposalImportSummary`. Path helpers must accept absolute paths only when they
resolve under `root`; search-space paths must be named `search_space.json`.

- [ ] **Step 2: Implement materialized bundle validation**

Load and validate `instance.json`, `hx.json`, `hz.json`,
`qec_code_quantum_tanner_spec.json`, and `materialization_manifest.json`.
Reject missing proposal id/fingerprint, validator fingerprint, qec-code spec
hash, mismatched candidate ids, non-quantum-Tanner code ids, and non-null exact
distance fields. Validate manifest output hashes against file contents.

- [ ] **Step 3: Implement stable fingerprinting and candidate construction**

Build the fingerprint payload from proposal fingerprint, validator fingerprint,
dimensions `{n,mx,mz,kx,kz}`, and sorted output hashes for
`instance.json`, `hx.json`, `hz.json`, and `qec_code_quantum_tanner_spec.json`.
Write candidates as:

```python
{
    "candidate_id": candidate_id,
    "code_family": "quantum-tanner-code",
    "instance_path": instance_dir_relative_to_root,
    "provenance": {
        "kind": "proposal-derived",
        "label": proposal_id,
        "proposal": {
            "proposal_id": proposal_id,
            "proposal_fingerprint": proposal_fingerprint,
            "validator_fingerprint": validator_fingerprint,
            "candidate_fingerprint": candidate_fingerprint,
            "materialization_manifest": manifest_relative_to_root,
            "qec_code_spec_path": spec_relative_to_root,
            "output_hashes": output_hashes,
            "materializer_version": materializer_version,
            "exact_distance_status": "unknown",
            "materialization_run": {"qec_code": manifest["qec_code"]},
        },
    },
}
```

- [ ] **Step 4: Implement duplicate checks and atomic write**

Reject duplicate proposal fingerprints and candidate fingerprints among imports
and against existing proposal-derived candidates with different candidate ids.
Allow idempotent replacement when an existing candidate with the same id has
the same candidate fingerprint. Preserve unrelated existing candidate specs.
Write JSON through a temporary file and `replace()`.

- [ ] **Step 5: Wire CLI**

Import `import_quantum_tanner_proposal_instances`, add the parser, call the API,
print `imported=<n> preserved=<n> search_space=<path>`, and return 0.

- [ ] **Step 6: Run Task 1 tests**

Run the three issue tests. Expected after this task may still fail on schema or
resolver behavior until Tasks 3 and 4 are complete.

### Task 3: Schema Provenance Extension

**Files:**
- Modify: `benchmarks/schemas/search-space.schema.json`
- Modify: `benchmarks/schemas/candidate.schema.json`

**Interfaces:**
- `provenance.proposal` is optional for legacy candidates but, when present,
  requires importer-written proposal provenance fields.

- [ ] **Step 1: Add shared JSON-value and proposal-provenance definitions**

In both schemas, add `$defs.jsonValue`, `$defs.outputHashes`, and
`$defs.proposalProvenance` definitions. `output_hashes` values are strings with
minimum length 1. `materialization_run` is an object whose values are JSON
values.

- [ ] **Step 2: Extend provenance properties**

Add optional `"proposal": { "$ref": "#/$defs/proposalProvenance" }` to the
existing provenance definition while preserving required `kind` and `label`.

- [ ] **Step 3: Run schema-focused tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_import.py::test_import_proposal_instances_writes_schema_valid_explicit_search_space \
  tests/test_search_eval_schemas.py \
  -q
```

Expected: issue schema assertions pass or move to resolver failures; existing
schema tests remain green.

### Task 4: Resolver And Workspace Validation

**Files:**
- Modify: `src/autoqec_search/eval_candidates.py`
- Modify: `src/autoqec_search/load.py`

**Interfaces:**
- Explicit proposal-derived instances with `parameters.distance is None` and
  `derived_properties.distance is None` resolve with `distance: None`.
- `load_search_workspace(root)` resolves each search-space candidate that has
  `instance_path`.

- [ ] **Step 1: Update explicit-instance distance normalization**

Refactor `_resolved_instance_parameters` to return `distance: None` when both
the instance parameter and derived-property exact distance are null. Keep
positive-distance checks and mismatch errors for exact-distance instances.

- [ ] **Step 2: Accept #90 instance identifiers**

In `_resolve_explicit_zoo_instance`, accept `instance["id"]`,
`instance["instance_id"]`, or `instance["candidate_id"]` as the explicit
instance id, requiring whichever exists to match the candidate spec id.

- [ ] **Step 3: Preserve null distance through artifact validation**

Update `_parameters_match`, `_validate_instance_matches_spec`, and
`_directory_candidate_from_payload` so candidate artifacts with matching null
distance can reload, while booleans/floats like `True` or `3.0` still fail with
`candidate distance must be a positive integer`.

- [ ] **Step 4: Validate explicit instance candidates during workspace load**

Add `_validate_explicit_instance_candidate_resolution(root, search_spaces)` in
`load.py`. It imports `resolve_campaign_candidate_spec` locally and resolves
only candidate specs with `instance_path`.

- [ ] **Step 5: Run resolver tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_import.py::test_import_proposal_instances_resolves_null_distance_candidate \
  tests/test_search_eval_candidates.py::test_resolve_explicit_instance_candidate_uses_instance_path \
  tests/test_search_eval_candidates.py::test_explicit_instance_resolution_rejects_parameter_distance_mismatch \
  tests/test_search_eval_candidates.py::test_resolve_directory_candidate_rejects_non_integer_candidate_distance \
  -q
```

Expected: all selected tests pass.

### Task 5: Verification And Manual Workspace Check

**Files:**
- No production files expected beyond prior tasks.

**Interfaces:**
- Required issue command and full-suite command.

- [ ] **Step 1: Run required issue tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_import.py::test_import_proposal_instances_writes_schema_valid_explicit_search_space \
  tests/test_search_quantum_tanner_proposal_import.py::test_import_proposal_instances_resolves_null_distance_candidate \
  tests/test_search_quantum_tanner_proposal_import.py::test_import_proposal_instances_rejects_duplicate_fingerprints \
  -q
```

Expected: all three pass.

- [ ] **Step 2: Run manual check**

Use the test helper workflow or an equivalent temporary workspace at
`/tmp/autoqec-qt-proposal-search-workspace`, import one candidate, then run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root /tmp/autoqec-qt-proposal-search-workspace
```

Expected output includes `validated search workspace` and no schema errors.

- [ ] **Step 3: Run full suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: pass, except any baseline fake-backend timeout failures already
recorded before implementation must be reported exactly if they persist.

- [ ] **Step 4: Commit implementation**

Stage changed files and commit with:

```bash
git add benchmarks/schemas/search-space.schema.json benchmarks/schemas/candidate.schema.json src/autoqec_search/cli.py src/autoqec_search/eval_candidates.py src/autoqec_search/load.py src/autoqec_search/quantum_tanner_proposal_import.py tests/test_search_quantum_tanner_proposal_import.py docs/superpowers/plans/2026-07-10-issue-91-quantum-tanner-proposal-import.md
git commit -m "feat: import proposal-derived quantum tanner instances"
```

## Self-Review

- Spec coverage: every issue #91 requirement maps to importer, schema, resolver,
  validation, duplicate, or verification tasks above.
- Placeholder scan: no `TBD`, `TODO`, `fill in`, or unspecified implementation
  choices remain.
- Type consistency: importer, CLI, schema, and resolver names match across
  tasks.
