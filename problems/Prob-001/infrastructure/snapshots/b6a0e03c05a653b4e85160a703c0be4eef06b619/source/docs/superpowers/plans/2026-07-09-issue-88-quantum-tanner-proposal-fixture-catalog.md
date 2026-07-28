# Issue 88 Quantum Tanner Proposal Fixture Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable quantum Tanner proposal fixture catalog with schema-valid and schema-invalid known-answer proposals.

**Architecture:** Keep the catalog under `tests/fixtures/quantum_tanner_proposals/` and validate it from the existing proposal schema test module. The checker loads the committed catalog, resolves repo-relative fixture paths, validates each proposal against `benchmarks/schemas/quantum-tanner-proposal.schema.json`, and compares actual schema verdicts with expected catalog verdicts.

**Tech Stack:** Python 3.11+, pytest, JSON Schema Draft 2020-12, `jsonschema`.

## Global Constraints

- Catalog path is exactly `tests/fixtures/quantum_tanner_proposals/catalog.json`.
- Add at least one schema-valid non-toric proposal fixture.
- Add at least two intentionally schema-invalid proposal fixtures.
- Catalog entries must list proposal fixture paths, provenance, expected status, and expected error kind for invalid cases.
- The checker must verify the catalog is internally consistent, all files exist, and each fixture's schema-level verdict matches the expectation.
- The negative control must mutate one fixture catalog entry's expected verdict inside the test and assert the checker fails with a message containing `fixture verdict mismatch`.
- Do not implement finite-group law validation, proposal materialization, rbposd evaluation, live AI calls, or workspace CLI proposal registration.
- Focused verification command:
  - `PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_fixture_catalog_is_complete tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_fixture_catalog_detects_bad_expected_verdict -q`
- Workspace validation command:
  - `PYTHONPATH=src python3 -m autoqec_search.cli validate --root .`
- Branch verification command:
  - `PYTHONPATH=src python3 -m pytest`

---

## File Structure

- Create `tests/fixtures/quantum_tanner_proposals/catalog.json`: the known-answer proposal fixture catalog.
- Create `tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json`: schema-valid non-toric proposal.
- Create `tests/fixtures/quantum_tanner_proposals/invalid-missing-local-codes.json`: schema-invalid proposal missing the required `local_codes` field.
- Create `tests/fixtures/quantum_tanner_proposals/invalid-bad-field.json`: schema-invalid proposal using unsupported `local_codes.field: "GF(4)"`.
- Modify `tests/test_search_quantum_tanner_proposals.py`: add catalog loading/checking helpers and the two issue-required tests.

---

### Task 1: Proposal Fixture Catalog And Checker

**Files:**
- Create: `tests/fixtures/quantum_tanner_proposals/catalog.json`
- Create: `tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json`
- Create: `tests/fixtures/quantum_tanner_proposals/invalid-missing-local-codes.json`
- Create: `tests/fixtures/quantum_tanner_proposals/invalid-bad-field.json`
- Modify: `tests/test_search_quantum_tanner_proposals.py`

**Interfaces:**
- Consumes: `benchmarks/schemas/quantum-tanner-proposal.schema.json`, existing `_json_pointer(error: ValidationError) -> str`, and repository-root constants in `tests/test_search_quantum_tanner_proposals.py`.
- Produces: `_check_quantum_tanner_proposal_fixture_catalog(catalog: dict | None = None) -> dict[str, int]`, returning counts with keys `valid`, `invalid`, and `valid_non_toric`.

- [ ] **Step 1: Write the failing tests**

Append this test code to `tests/test_search_quantum_tanner_proposals.py` before creating the catalog or new helper:

```python
CATALOG_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "catalog.json"
)


def _proposal_fixture_catalog() -> dict:
    return _load_json(CATALOG_PATH)


def test_quantum_tanner_proposal_fixture_catalog_is_complete() -> None:
    counts = _check_quantum_tanner_proposal_fixture_catalog()

    assert counts["valid_non_toric"] >= 1
    assert counts["invalid"] >= 2


def test_quantum_tanner_proposal_fixture_catalog_detects_bad_expected_verdict() -> None:
    catalog = copy.deepcopy(_proposal_fixture_catalog())
    catalog["entries"][0]["expected_status"] = "invalid"
    catalog["entries"][0]["expected_error_kind"] = "required"

    with pytest.raises(AssertionError, match="fixture verdict mismatch"):
        _check_quantum_tanner_proposal_fixture_catalog(catalog)
```

- [ ] **Step 2: Run the focused tests to verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_fixture_catalog_is_complete \
  tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_fixture_catalog_detects_bad_expected_verdict \
  -q
```

Expected: FAIL because `_check_quantum_tanner_proposal_fixture_catalog` is not defined yet.

- [ ] **Step 3: Add the catalog checker helper**

In `tests/test_search_quantum_tanner_proposals.py`, add this helper code after `_validator()` and before `_fixture()`:

```python
def _validator_for_schema(schema_path: Path) -> Draft202012Validator:
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _resolve_repo_file(value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AssertionError(f"{label} must be a non-empty repo-relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise AssertionError(f"{label} must be a safe repo-relative path: {value}")
    resolved = (REPO_ROOT / path).resolve()
    root = REPO_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise AssertionError(f"{label} must resolve inside repository root: {value}")
    if not resolved.is_file():
        raise AssertionError(f"missing {label}: {value}")
    return resolved


def _first_schema_error(
    validator: Draft202012Validator, proposal: dict
) -> ValidationError | None:
    errors = sorted(validator.iter_errors(proposal), key=lambda error: list(error.path))
    return errors[0] if errors else None


def _check_quantum_tanner_proposal_fixture_catalog(
    catalog: dict | None = None,
) -> dict[str, int]:
    catalog = _proposal_fixture_catalog() if catalog is None else catalog

    if catalog.get("catalog_id") != "quantum-tanner-proposal-fixtures-v1":
        raise AssertionError("catalog_id mismatch in proposal fixture catalog")
    if catalog.get("schema_version") != 1:
        raise AssertionError("schema_version mismatch in proposal fixture catalog")
    schema_path = _resolve_repo_file(catalog.get("schema_path"), label="schema_path")
    if schema_path.resolve() != SCHEMA_PATH.resolve():
        raise AssertionError("schema_path mismatch in proposal fixture catalog")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or not entries:
        raise AssertionError("proposal fixture catalog entries must be a non-empty list")

    validator = _validator_for_schema(schema_path)
    counts = {"valid": 0, "invalid": 0, "valid_non_toric": 0}
    seen_fixture_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise AssertionError("proposal fixture catalog entry must be an object")
        fixture_id = entry.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id:
            raise AssertionError("proposal fixture catalog entry fixture_id must be non-empty")
        if fixture_id in seen_fixture_ids:
            raise AssertionError(f"duplicate proposal fixture id: {fixture_id}")
        seen_fixture_ids.add(fixture_id)
        provenance = entry.get("provenance")
        if not isinstance(provenance, dict) or not provenance:
            raise AssertionError(f"{fixture_id} provenance must be a non-empty object")
        expected_status = entry.get("expected_status")
        if expected_status not in {"valid", "invalid"}:
            raise AssertionError(f"{fixture_id} expected_status must be valid or invalid")
        expected_error_kind = entry.get("expected_error_kind")
        if expected_status == "valid" and expected_error_kind is not None:
            raise AssertionError(f"{fixture_id} valid fixtures must not expect an error kind")
        if expected_status == "invalid" and not isinstance(expected_error_kind, str):
            raise AssertionError(f"{fixture_id} invalid fixtures must expect an error kind")

        proposal = _load_json(_resolve_repo_file(entry.get("path"), label=fixture_id))
        error = _first_schema_error(validator, proposal)
        actual_status = "invalid" if error is not None else "valid"
        if actual_status != expected_status:
            raise AssertionError(
                f"fixture verdict mismatch: {fixture_id} expected "
                f"{expected_status} got {actual_status}"
            )
        if error is not None:
            if error.validator != expected_error_kind:
                raise AssertionError(
                    f"fixture verdict mismatch: {fixture_id} expected "
                    f"{expected_error_kind} got {error.validator}"
                )
            expected_pointer = entry.get("expected_error_pointer")
            actual_pointer = _json_pointer(error)
            if expected_pointer is not None and expected_pointer != actual_pointer:
                raise AssertionError(
                    f"fixture verdict mismatch: {fixture_id} expected "
                    f"{expected_pointer} got {actual_pointer}"
                )
            counts["invalid"] += 1
        else:
            counts["valid"] += 1
            tags = proposal.get("search_hints", {}).get("tags", [])
            if isinstance(tags, list) and "non-toric" in tags:
                counts["valid_non_toric"] += 1

    if counts["valid_non_toric"] < 1:
        raise AssertionError("expected at least one schema-valid non-toric proposal")
    if counts["invalid"] < 2:
        raise AssertionError("expected at least two schema-invalid fixtures")
    return counts
```

Then simplify the existing `_validator()` to:

```python
def _validator() -> Draft202012Validator:
    return _validator_for_schema(SCHEMA_PATH)
```

- [ ] **Step 4: Add the fixture catalog and JSON fixtures**

Create `tests/fixtures/quantum_tanner_proposals/catalog.json`:

```json
{
  "catalog_id": "quantum-tanner-proposal-fixtures-v1",
  "schema_version": 1,
  "schema_path": "benchmarks/schemas/quantum-tanner-proposal.schema.json",
  "entries": [
    {
      "fixture_id": "valid-dihedral-d3",
      "path": "tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json",
      "provenance": {
        "kind": "hand-authored-test-fixture",
        "source_issue": "https://github.com/nzy1997/AutoQEC/issues/88",
        "purpose": "schema-valid non-toric proposal"
      },
      "expected_status": "valid",
      "expected_error_kind": null
    },
    {
      "fixture_id": "invalid-missing-local-codes",
      "path": "tests/fixtures/quantum_tanner_proposals/invalid-missing-local-codes.json",
      "provenance": {
        "kind": "hand-authored-test-fixture",
        "source_issue": "https://github.com/nzy1997/AutoQEC/issues/88",
        "purpose": "schema-invalid proposal missing required local_codes"
      },
      "expected_status": "invalid",
      "expected_error_kind": "required",
      "expected_error_pointer": "/"
    },
    {
      "fixture_id": "invalid-bad-field",
      "path": "tests/fixtures/quantum_tanner_proposals/invalid-bad-field.json",
      "provenance": {
        "kind": "hand-authored-test-fixture",
        "source_issue": "https://github.com/nzy1997/AutoQEC/issues/88",
        "purpose": "schema-invalid proposal with unsupported local code field"
      },
      "expected_status": "invalid",
      "expected_error_kind": "const",
      "expected_error_pointer": "/local_codes/field"
    }
  ]
}
```

Create `tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json`:

```json
{
  "proposal_id": "dihedral-d3-ai-proposal-v1",
  "schema_version": 1,
  "construction_mode": "lr_cayley_no_cover_v1",
  "base_group": {
    "name": "D3",
    "element_order": "id = i + 3*j for r^i s^j with i in Z3 and j in Z2",
    "order": 6,
    "identity": 0,
    "multiplication_table": [
      [0, 1, 2, 3, 4, 5],
      [1, 2, 0, 4, 5, 3],
      [2, 0, 1, 5, 3, 4],
      [3, 5, 4, 0, 2, 1],
      [4, 3, 5, 1, 0, 2],
      [5, 4, 3, 2, 1, 0]
    ]
  },
  "a_generator_indices": [1, 3],
  "b_generator_indices": [2, 4],
  "local_codes": {
    "matrix_role": "parity_check",
    "field": "GF(2)",
    "h_a": [
      [1, 0, 1],
      [0, 1, 1]
    ],
    "h_b": [
      [1, 1, 0],
      [1, 0, 1]
    ]
  },
  "search_hints": {
    "target_distance": 3,
    "max_group_order": 12,
    "tags": ["non-toric", "dihedral", "catalog-fixture"]
  },
  "provenance": {
    "source": "test-fixture",
    "model": "fixture-author",
    "generated_at": "2026-07-09T00:00:00Z",
    "prompt_summary": "Small non-toric dihedral proposal for fixture catalog validation."
  }
}
```

Create `tests/fixtures/quantum_tanner_proposals/invalid-missing-local-codes.json`:

```json
{
  "proposal_id": "dihedral-d3-missing-local-codes-v1",
  "schema_version": 1,
  "construction_mode": "lr_cayley_no_cover_v1",
  "base_group": {
    "name": "D3",
    "element_order": "id = i + 3*j for r^i s^j with i in Z3 and j in Z2",
    "order": 6,
    "identity": 0,
    "multiplication_table": [
      [0, 1, 2, 3, 4, 5],
      [1, 2, 0, 4, 5, 3],
      [2, 0, 1, 5, 3, 4],
      [3, 5, 4, 0, 2, 1],
      [4, 3, 5, 1, 0, 2],
      [5, 4, 3, 2, 1, 0]
    ]
  },
  "a_generator_indices": [1, 3],
  "b_generator_indices": [2, 4],
  "search_hints": {
    "target_distance": 3,
    "max_group_order": 12,
    "tags": ["invalid-fixture", "missing-local-codes"]
  },
  "provenance": {
    "source": "test-fixture",
    "model": "fixture-author",
    "generated_at": "2026-07-09T00:00:00Z",
    "prompt_summary": "Invalid proposal missing local_codes for fixture catalog validation."
  }
}
```

Create `tests/fixtures/quantum_tanner_proposals/invalid-bad-field.json`:

```json
{
  "proposal_id": "dihedral-d3-bad-field-v1",
  "schema_version": 1,
  "construction_mode": "lr_cayley_no_cover_v1",
  "base_group": {
    "name": "D3",
    "element_order": "id = i + 3*j for r^i s^j with i in Z3 and j in Z2",
    "order": 6,
    "identity": 0,
    "multiplication_table": [
      [0, 1, 2, 3, 4, 5],
      [1, 2, 0, 4, 5, 3],
      [2, 0, 1, 5, 3, 4],
      [3, 5, 4, 0, 2, 1],
      [4, 3, 5, 1, 0, 2],
      [5, 4, 3, 2, 1, 0]
    ]
  },
  "a_generator_indices": [1, 3],
  "b_generator_indices": [2, 4],
  "local_codes": {
    "matrix_role": "parity_check",
    "field": "GF(4)",
    "h_a": [
      [1, 0, 1],
      [0, 1, 1]
    ],
    "h_b": [
      [1, 1, 0],
      [1, 0, 1]
    ]
  },
  "search_hints": {
    "target_distance": 3,
    "max_group_order": 12,
    "tags": ["invalid-fixture", "bad-field"]
  },
  "provenance": {
    "source": "test-fixture",
    "model": "fixture-author",
    "generated_at": "2026-07-09T00:00:00Z",
    "prompt_summary": "Invalid proposal with unsupported local code field for fixture catalog validation."
  }
}
```

- [ ] **Step 5: Run the focused tests to verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_fixture_catalog_is_complete \
  tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_fixture_catalog_detects_bad_expected_verdict \
  -q
```

Expected: PASS with `2 passed`.

- [ ] **Step 6: Run the proposal test module**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_proposals.py -q
```

Expected: PASS with all tests in the module passing.

- [ ] **Step 7: Commit**

Run:

```bash
git add tests/test_search_quantum_tanner_proposals.py tests/fixtures/quantum_tanner_proposals/catalog.json tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json tests/fixtures/quantum_tanner_proposals/invalid-missing-local-codes.json tests/fixtures/quantum_tanner_proposals/invalid-bad-field.json docs/superpowers/plans/2026-07-09-issue-88-quantum-tanner-proposal-fixture-catalog.md
git commit -m "Fix #88: add quantum Tanner proposal fixture catalog"
```
