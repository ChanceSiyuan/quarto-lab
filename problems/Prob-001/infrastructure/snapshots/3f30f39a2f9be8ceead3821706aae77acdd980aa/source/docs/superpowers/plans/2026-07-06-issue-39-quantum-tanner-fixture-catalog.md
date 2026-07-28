# Issue 39 Quantum Tanner Fixture Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pinned M1 quantum Tanner fixture catalog and a focused adapter that normalizes search-ready entries into finite CSS candidate views.

**Architecture:** The committed catalog is data under `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json`. A new `autoqec_search.quantum_tanner_catalog` module validates catalog entries, validates sparse-row matrix artifacts, converts source matrices to dense search-layer payloads, and resolves entries to `ResolvedCandidate` objects without changing the distance-ladder fixtures.

**Tech Stack:** Python 3, pytest, JSON fixture data, existing `autoqec_search.load.SearchIntegrityError`, existing `autoqec_search.eval_candidates.CandidateInput` and `ResolvedCandidate`.

## Global Constraints

- Catalog path is exactly `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json`.
- Catalog entries are exactly `quantum-tanner-toric-d4`, `quantum-tanner-toric-d6`, and `quantum-tanner-toric-d8`.
- Each catalog entry includes `candidate_id`, `code_id`, `n`, `k`, `distance`, `hx`, `hz`, `source_fixture_path`, `source_instance`, `provenance`, `search_ready`, and `adaptation`.
- `search_ready: true` means the adapter can produce a normalized search-layer candidate view; the raw source fixture still requires catalog adaptation.
- Do not modify the distance-ladder fixture `instance.json`, `hx.json`, or `hz.json` files.
- Do not add an open-ended quantum Tanner generator.
- Do not compute new distance or logical-error-rate results.
- Focused verification command must print `5 passed`: `PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_catalog.py`.
- Workspace validation command must exit 0 and print `validated search workspace`: `PYTHONPATH=src python3 -m autoqec_search.cli validate --root .`.

---

## File Structure

- Create `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json`: pinned catalog data for the three M1 smoke fixtures.
- Create `src/autoqec_search/quantum_tanner_catalog.py`: catalog loading, validation, matrix normalization, and `ResolvedCandidate` adapter.
- Create `tests/test_search_quantum_tanner_catalog.py`: exactly five tests covering the issue's required behaviors.

---

### Task 1: Pinned Catalog Data And Shape Tests

**Files:**
- Create: `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json`
- Create: `tests/test_search_quantum_tanner_catalog.py`

**Interfaces:**
- Consumes: existing repo fixture files under `benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-*`.
- Produces: catalog JSON structure consumed by Task 2 loader functions.

- [ ] **Step 1: Write failing catalog shape and matrix tests**

Create `tests/test_search_quantum_tanner_catalog.py` with these initial imports and helpers:

```python
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = (
    REPO_ROOT
    / "campaigns"
    / "examples"
    / "quantum-tanner-autoresearch"
    / "fixture_catalog.json"
)
EXPECTED_CANDIDATES = [
    "quantum-tanner-toric-d4",
    "quantum-tanner-toric-d6",
    "quantum-tanner-toric-d8",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _catalog() -> dict:
    return _load_json(CATALOG_PATH)


def _entry_by_id() -> dict[str, dict]:
    return {entry["candidate_id"]: entry for entry in _catalog()["entries"]}


def _matrix_num_cols(path: Path) -> int:
    payload = _load_json(path)
    assert payload["format"] == "sparse_rows"
    num_cols = payload["num_cols"]
    assert type(num_cols) is int and num_cols > 0
    rows = payload["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, list)
        previous = -1
        for column in row:
            assert type(column) is int
            assert 0 <= column < num_cols
            assert column > previous
            previous = column
    return num_cols


def test_catalog_contains_exact_pinned_m1_smoke_entries() -> None:
    catalog = _catalog()

    assert catalog["catalog_id"] == "quantum-tanner-autoresearch-m1-fixtures"
    assert catalog["schema_version"] == 1
    assert [entry["candidate_id"] for entry in catalog["entries"]] == EXPECTED_CANDIDATES

    expected = {
        "quantum-tanner-toric-d4": {"n": 16, "k": 2, "distance": 4},
        "quantum-tanner-toric-d6": {"n": 36, "k": 2, "distance": 6},
        "quantum-tanner-toric-d8": {"n": 64, "k": 2, "distance": 8},
    }
    for candidate_id, fields in expected.items():
        entry = _entry_by_id()[candidate_id]
        for key, value in fields.items():
            assert entry[key] == value
        for required in (
            "candidate_id",
            "code_id",
            "n",
            "k",
            "hx",
            "hz",
            "source_fixture_path",
            "source_instance",
            "provenance",
            "search_ready",
        ):
            assert required in entry
        assert entry["code_id"] == "quantum-tanner-code"
        assert entry["source_fixture_path"].endswith(f"/instances/{candidate_id}")
        assert entry["hx"].endswith(f"/instances/{candidate_id}/hx.json")
        assert entry["hz"].endswith(f"/instances/{candidate_id}/hz.json")
        assert entry["source_instance"].endswith(f"/instances/{candidate_id}/instance.json")
        assert entry["provenance"]["kind"] == "distance-ladder-fixture"
        assert entry["provenance"]["label"] == candidate_id
        assert entry["provenance"]["quantum_tanner_spec"].endswith(
            f"/quantum_tanner_specs/toric-d{entry['distance']}.json"
        )
        assert entry["search_ready"] is True
        assert entry["adaptation"] == "catalog-normalized-finite-css-instance"


def test_catalog_matrix_artifacts_exist_with_matching_binary_columns() -> None:
    for entry in _catalog()["entries"]:
        hx_path = REPO_ROOT / entry["hx"]
        hz_path = REPO_ROOT / entry["hz"]

        assert hx_path.is_file()
        assert hz_path.is_file()
        assert _matrix_num_cols(hx_path) == entry["n"]
        assert _matrix_num_cols(hz_path) == entry["n"]
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_catalog.py
```

Expected: FAIL because `fixture_catalog.json` does not exist.

- [ ] **Step 3: Add the pinned catalog JSON**

Create `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json` with this structure and exactly three entries. Keep all paths repo-relative and ASCII.

```json
{
  "catalog_id": "quantum-tanner-autoresearch-m1-fixtures",
  "schema_version": 1,
  "entries": [
    {
      "candidate_id": "quantum-tanner-toric-d4",
      "code_id": "quantum-tanner-code",
      "n": 16,
      "k": 2,
      "distance": 4,
      "hx": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d4/hx.json",
      "hz": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d4/hz.json",
      "source_fixture_path": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d4",
      "source_instance": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d4/instance.json",
      "provenance": {
        "kind": "distance-ladder-fixture",
        "label": "quantum-tanner-toric-d4",
        "distance_ladder": "surface-toric-bb-kasai-tanner-v2",
        "qec_code_spec": "quantum_tanner:toric_d4",
        "quantum_tanner_spec": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/quantum_tanner_specs/toric-d4.json",
        "generator": "qec-code",
        "construction_mode": "lr_cayley_no_cover_v1",
        "base_group": "Z4xZ4"
      },
      "search_ready": true,
      "adaptation": "catalog-normalized-finite-css-instance"
    },
    {
      "candidate_id": "quantum-tanner-toric-d6",
      "code_id": "quantum-tanner-code",
      "n": 36,
      "k": 2,
      "distance": 6,
      "hx": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d6/hx.json",
      "hz": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d6/hz.json",
      "source_fixture_path": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d6",
      "source_instance": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d6/instance.json",
      "provenance": {
        "kind": "distance-ladder-fixture",
        "label": "quantum-tanner-toric-d6",
        "distance_ladder": "surface-toric-bb-kasai-tanner-v2",
        "qec_code_spec": "quantum_tanner:toric_d6",
        "quantum_tanner_spec": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/quantum_tanner_specs/toric-d6.json",
        "generator": "qec-code",
        "construction_mode": "lr_cayley_no_cover_v1",
        "base_group": "Z6xZ6"
      },
      "search_ready": true,
      "adaptation": "catalog-normalized-finite-css-instance"
    },
    {
      "candidate_id": "quantum-tanner-toric-d8",
      "code_id": "quantum-tanner-code",
      "n": 64,
      "k": 2,
      "distance": 8,
      "hx": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d8/hx.json",
      "hz": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d8/hz.json",
      "source_fixture_path": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d8",
      "source_instance": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d8/instance.json",
      "provenance": {
        "kind": "distance-ladder-fixture",
        "label": "quantum-tanner-toric-d8",
        "distance_ladder": "surface-toric-bb-kasai-tanner-v2",
        "qec_code_spec": "quantum_tanner:toric_d8",
        "quantum_tanner_spec": "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/quantum_tanner_specs/toric-d8.json",
        "generator": "qec-code",
        "construction_mode": "lr_cayley_no_cover_v1",
        "base_group": "Z8xZ8"
      },
      "search_ready": true,
      "adaptation": "catalog-normalized-finite-css-instance"
    }
  ]
}
```

- [ ] **Step 4: Run tests to verify GREEN for Task 1**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_catalog.py
```

Expected: PASS with `2 passed`.

- [ ] **Step 5: Commit Task 1**

```bash
git add campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json tests/test_search_quantum_tanner_catalog.py
git commit -m "test: pin quantum Tanner fixture catalog"
```

---

### Task 2: Catalog Adapter And Corruption Validation

**Files:**
- Modify: `tests/test_search_quantum_tanner_catalog.py`
- Create: `src/autoqec_search/quantum_tanner_catalog.py`

**Interfaces:**
- Consumes: `fixture_catalog.json` from Task 1.
- Produces:
  - `DEFAULT_CATALOG_PATH: Path`
  - `load_quantum_tanner_fixture_catalog(root: Path, catalog_path: str | Path = DEFAULT_CATALOG_PATH) -> dict[str, Any]`
  - `validate_quantum_tanner_fixture_catalog(root: Path, catalog_path: str | Path = DEFAULT_CATALOG_PATH) -> None`
  - `normalize_quantum_tanner_fixture_entry(root: Path, entry: dict[str, Any]) -> dict[str, Any]`
  - `resolve_quantum_tanner_fixture_entry(root: Path, entry: dict[str, Any], *, campaign_id: str = "quantum-tanner-autoresearch") -> ResolvedCandidate`

- [ ] **Step 1: Extend tests before implementation**

Add these imports to `tests/test_search_quantum_tanner_catalog.py`:

```python
import shutil

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_catalog import (
    load_quantum_tanner_fixture_catalog,
    normalize_quantum_tanner_fixture_entry,
    resolve_quantum_tanner_fixture_entry,
    validate_quantum_tanner_fixture_catalog,
)
```

Add these helper functions:

```python
def _copy_catalog_repo(tmp_path: Path) -> Path:
    work_root = tmp_path / "repo"
    catalog_relative = CATALOG_PATH.relative_to(REPO_ROOT)
    (work_root / catalog_relative.parent).mkdir(parents=True)
    shutil.copyfile(CATALOG_PATH, work_root / catalog_relative)
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    return work_root


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
```

Add the three new tests:

```python
def test_search_ready_entries_normalize_to_search_layer_candidate_fields() -> None:
    catalog = load_quantum_tanner_fixture_catalog(REPO_ROOT)
    search_ready_entries = [
        entry for entry in catalog["entries"] if entry["search_ready"] is True
    ]
    assert [entry["candidate_id"] for entry in search_ready_entries] == EXPECTED_CANDIDATES

    for entry in search_ready_entries:
        normalized = normalize_quantum_tanner_fixture_entry(REPO_ROOT, entry)
        assert normalized["id"] == entry["candidate_id"]
        assert normalized["code_id"] == entry["code_id"]
        assert normalized["instance_kind"] == "finite_css_instance"
        assert normalized["matrix_format"] == "dense_binary_json"
        assert normalized["parameters"]["distance"] == entry["distance"]
        assert normalized["parameters"]["source_fixture_id"] == entry["candidate_id"]
        assert normalized["derived_properties"]["n"] == entry["n"]
        assert normalized["derived_properties"]["k"] == entry["k"]
        assert normalized["derived_properties"]["distance"] == entry["distance"]
        assert normalized["artifacts"] == {"hx": "hx.json", "hz": "hz.json"}

        candidate = resolve_quantum_tanner_fixture_entry(REPO_ROOT, entry)
        assert candidate.spec.candidate_id == entry["candidate_id"]
        assert candidate.spec.code_family == entry["code_id"]
        assert candidate.spec.parameters == normalized["parameters"]
        assert candidate.instance == normalized
        assert candidate.source_kind == "quantum-tanner-fixture-catalog"
        assert candidate.hx["format"] == "dense_binary_matrix"
        assert candidate.hz["format"] == "dense_binary_matrix"
        assert candidate.hx["n_cols"] == entry["n"]
        assert candidate.hz["n_cols"] == entry["n"]


def test_catalog_validation_rejects_duplicate_candidate_ids(tmp_path: Path) -> None:
    work_root = _copy_catalog_repo(tmp_path)
    catalog_path = (
        work_root
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "fixture_catalog.json"
    )
    payload = _load_json(catalog_path)
    payload["entries"][1]["candidate_id"] = payload["entries"][0]["candidate_id"]
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="duplicate candidate_id"):
        validate_quantum_tanner_fixture_catalog(work_root)


def test_catalog_validation_rejects_missing_hx_path(tmp_path: Path) -> None:
    work_root = _copy_catalog_repo(tmp_path)
    catalog_path = (
        work_root
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "fixture_catalog.json"
    )
    payload = _load_json(catalog_path)
    payload["entries"][0]["hx"] = (
        "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/"
        "instances/quantum-tanner-toric-d4/missing-hx.json"
    )
    _write_json(catalog_path, payload)

    with pytest.raises(SearchIntegrityError, match="missing hx artifact"):
        validate_quantum_tanner_fixture_catalog(work_root)
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_catalog.py
```

Expected: FAIL because `autoqec_search.quantum_tanner_catalog` does not exist.

- [ ] **Step 3: Implement the adapter module**

Create `src/autoqec_search/quantum_tanner_catalog.py` implementing the interfaces above. Required behavior:

```python
DEFAULT_CATALOG_PATH = Path(
    "campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json"
)
```

Validation requirements:

- catalog payload must be a dict with `entries` as a non-empty list.
- candidate ids must be non-empty strings and unique.
- required entry fields are exactly checked for presence, and extra fields may be allowed only at the top-level entry if they are already in the catalog data.
- `hx`, `hz`, `source_fixture_path`, `source_instance`, and `provenance.quantum_tanner_spec` must be safe repo-relative paths.
- `hx`, `hz`, `source_instance`, and `provenance.quantum_tanner_spec` must exist.
- source fixture path must exist as a directory.
- sparse-row matrices must have `format == "sparse_rows"`, positive integer `num_cols`, list `rows`, sorted integer column indices, no duplicate columns inside a row, and column indices within `[0, num_cols)`.
- `hx` and `hz` must have matching `num_cols`, and that width must equal catalog `n`.
- `search_ready: true` entries must normalize; `search_ready: false` entries should raise `SearchIntegrityError` from `normalize_quantum_tanner_fixture_entry`.

Normalization requirements:

```python
{
    "id": entry["candidate_id"],
    "code_id": entry["code_id"],
    "family_id": "quantum-tanner-code",
    "title": f"Quantum Tanner Toric Fixture d={entry['distance']}",
    "instance_kind": "finite_css_instance",
    "matrix_format": "dense_binary_json",
    "parameters": {
        "distance": entry["distance"],
        "construction": "quantum-tanner-toric",
        "source_fixture_id": entry["candidate_id"],
        "qec_code_spec": entry["provenance"]["qec_code_spec"],
        "quantum_tanner_spec": entry["provenance"]["quantum_tanner_spec"],
        "base_group": entry["provenance"]["base_group"],
    },
    "derived_properties": {
        "n": entry["n"],
        "k": entry["k"],
        "distance": entry["distance"],
        "bound_type": "exact",
        "mx": len(hx_sparse["rows"]),
        "mz": len(hz_sparse["rows"]),
    },
    "artifacts": {"hx": "hx.json", "hz": "hz.json"},
    "provenance": {
        "source": "quantum-tanner-fixture-catalog",
        "catalog": "campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json",
        "source_fixture_path": entry["source_fixture_path"],
        "source_instance": entry["source_instance"],
        "adaptation": entry["adaptation"],
        "fixture_provenance": entry["provenance"],
    },
}
```

`resolve_quantum_tanner_fixture_entry` must create:

```python
CandidateInput(
    candidate_id=entry["candidate_id"],
    campaign_id=campaign_id,
    code_family=entry["code_id"],
    parameters=normalized["parameters"],
    provenance={
        "kind": entry["provenance"]["kind"],
        "label": entry["candidate_id"],
    },
)
```

and return `ResolvedCandidate` with `artifact_root=root / entry["source_fixture_path"]`, `instance=normalized`, dense `hx` and `hz`, and `source_kind="quantum-tanner-fixture-catalog"`.

- [ ] **Step 4: Run tests to verify GREEN for Task 2**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_catalog.py
```

Expected: PASS with `5 passed`.

- [ ] **Step 5: Run workspace validation**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: exit 0 with `validated search workspace`.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/autoqec_search/quantum_tanner_catalog.py tests/test_search_quantum_tanner_catalog.py
git commit -m "feat: add quantum Tanner fixture catalog adapter"
```
