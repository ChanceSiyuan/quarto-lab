# Upper-Bound Witness Fixtures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compact, committed fixture catalog for CSS upper-bound witness known answers.

**Architecture:** Store shared tiny `hx.json` and `hz.json` matrices plus AutoQEC witness payloads and qec-code result payloads under `benchmarks/fixtures/upper-bound-witness/`. Extend the existing witness verifier tests so the catalog is loaded from disk, verified against `verify_css_upper_bound_witness()`, and checked for qec-code result contract shape without adding conversion production code.

**Tech Stack:** Python 3, pytest, JSON fixture files, existing `autoqec_search.structure.verify_css_upper_bound_witness()`.

## Global Constraints

- Use `verify_css_upper_bound_witness()` in `src/autoqec_search/structure.py` as the source of truth for AutoQEC witness validation.
- Fixture root must be `benchmarks/fixtures/upper-bound-witness/`.
- Keep matrices tiny: use the 4-column dense binary CSS matrices `hx = [[1, 1, 0, 0]]` and `hz = [[0, 0, 1, 1]]`.
- Include at least one valid X-like witness and one valid Z-like witness.
- Include at least one stabilizer-row-space witness and one vector-length mismatch witness.
- Include at least one qec-code-style completed `random-window-upper-bound` JSON payload with `status`, `method`, `bound_type`, `upper_bound`, `logical_class`, `witness.x`, `witness.z`, `witness.weight`, `options`, and `provenance`.
- Include negative qec-code-style payloads for `logical_class == "mixed"`, `upper_bound != witness.weight`, x/z width mismatch, non-binary witness entries, and one malformed missing-witness result.
- Add a manifest that records fixture id, basis, expected weight, expected verifier status, and whether the fixture is an AutoQEC witness payload or qec-code result payload.
- Do not run qec-code, search for witnesses, or add qec-code conversion production code.

---

### Task 1: Catalog Fixtures And Tests

**Files:**
- Create: `benchmarks/fixtures/upper-bound-witness/hx.json`
- Create: `benchmarks/fixtures/upper-bound-witness/hz.json`
- Create: `benchmarks/fixtures/upper-bound-witness/manifest.json`
- Create: `benchmarks/fixtures/upper-bound-witness/autoqec/x-logical-witness.json`
- Create: `benchmarks/fixtures/upper-bound-witness/autoqec/z-logical-witness.json`
- Create: `benchmarks/fixtures/upper-bound-witness/autoqec/x-stabilizer-row-space.json`
- Create: `benchmarks/fixtures/upper-bound-witness/autoqec/x-length-mismatch.json`
- Create: `benchmarks/fixtures/upper-bound-witness/qec-code/random-window-x-completed.json`
- Create: `benchmarks/fixtures/upper-bound-witness/qec-code/random-window-z-completed.json`
- Create: `benchmarks/fixtures/upper-bound-witness/qec-code/mixed-logical-class.json`
- Create: `benchmarks/fixtures/upper-bound-witness/qec-code/upper-bound-weight-mismatch.json`
- Create: `benchmarks/fixtures/upper-bound-witness/qec-code/x-z-width-mismatch.json`
- Create: `benchmarks/fixtures/upper-bound-witness/qec-code/non-binary-witness-entry.json`
- Create: `benchmarks/fixtures/upper-bound-witness/qec-code/malformed-missing-witness.json`
- Modify: `tests/test_search_upper_bound_witness.py`

**Interfaces:**
- Consumes: `verify_css_upper_bound_witness(hx_payload: dict, hz_payload: dict, witness_payload: dict) -> dict`.
- Produces: a committed fixture manifest at `benchmarks/fixtures/upper-bound-witness/manifest.json` and pytest coverage proving valid/invalid fixtures match their expected verifier or contract status.

- [ ] **Step 1: Write the failing catalog tests**

Append this code to `tests/test_search_upper_bound_witness.py` after the existing tests:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
WITNESS_FIXTURE_ROOT = REPO_ROOT / "benchmarks" / "fixtures" / "upper-bound-witness"
QEC_CODE_REQUIRED_KEYS = {
    "status",
    "method",
    "bound_type",
    "upper_bound",
    "logical_class",
    "witness",
    "options",
    "provenance",
}


def _load_fixture_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_witness_fixture_manifest() -> dict:
    return _load_fixture_json(WITNESS_FIXTURE_ROOT / "manifest.json")


def _fixture_entries(payload_kind: str) -> list[dict]:
    manifest = _load_witness_fixture_manifest()
    return [
        entry
        for entry in manifest["fixtures"]
        if entry["payload_kind"] == payload_kind
    ]


def _validate_qec_code_random_window_contract(payload: dict) -> str | None:
    missing = sorted(QEC_CODE_REQUIRED_KEYS - payload.keys())
    if missing:
        if missing == ["witness"]:
            return "missing_witness"
        return "missing_required_key"
    if payload["status"] != "completed":
        return "invalid_status"
    if payload["method"] != "random-window-upper-bound":
        return "invalid_method"
    if payload["bound_type"] != "upper":
        return "invalid_bound_type"
    if type(payload["upper_bound"]) is not int or payload["upper_bound"] <= 0:
        return "invalid_upper_bound"
    if payload["logical_class"] not in {"x", "z"}:
        return "unsupported_logical_class"
    witness = payload["witness"]
    if not isinstance(witness, dict):
        return "missing_witness"
    if set(witness) != {"x", "z", "weight"}:
        return "invalid_witness_keys"
    x_vector = witness["x"]
    z_vector = witness["z"]
    if not isinstance(x_vector, list) or not isinstance(z_vector, list):
        return "invalid_witness_vector"
    if len(x_vector) != len(z_vector):
        return "x_z_width_mismatch"
    entries = [*x_vector, *z_vector]
    if any(type(bit) is not int or bit not in {0, 1} for bit in entries):
        return "non_binary_witness_entry"
    if type(witness["weight"]) is not int or witness["weight"] <= 0:
        return "invalid_witness_weight"
    if payload["upper_bound"] != witness["weight"]:
        return "upper_bound_weight_mismatch"
    if sum(entries) != witness["weight"]:
        return "witness_weight_mismatch"
    if not isinstance(payload["options"], dict):
        return "invalid_options"
    if not isinstance(payload["provenance"], dict):
        return "invalid_provenance"
    return None


def test_upper_bound_witness_catalog_manifest_entries_resolve() -> None:
    manifest = _load_witness_fixture_manifest()

    assert manifest["catalog_id"] == "upper-bound-witness-known-answer-v1"
    assert manifest["hx_path"] == "hx.json"
    assert manifest["hz_path"] == "hz.json"
    assert _load_fixture_json(WITNESS_FIXTURE_ROOT / manifest["hx_path"]) == HX
    assert _load_fixture_json(WITNESS_FIXTURE_ROOT / manifest["hz_path"]) == HZ

    fixture_ids = {entry["id"] for entry in manifest["fixtures"]}
    assert fixture_ids == {
        "autoqec-x-logical",
        "autoqec-z-logical",
        "autoqec-x-stabilizer-row-space",
        "autoqec-x-length-mismatch",
        "qec-code-random-window-x-completed",
        "qec-code-random-window-z-completed",
        "qec-code-mixed-logical-class",
        "qec-code-upper-bound-weight-mismatch",
        "qec-code-x-z-width-mismatch",
        "qec-code-non-binary-witness-entry",
        "qec-code-malformed-missing-witness",
    }
    for entry in manifest["fixtures"]:
        assert entry["payload_kind"] in {"autoqec-witness", "qec-code-result"}
        assert entry["basis"] in {"x", "z", "mixed"}
        assert type(entry["expected_weight"]) is int
        assert entry["expected_verifier_status"] in {"pass", "fail", "not_applicable"}
        assert (WITNESS_FIXTURE_ROOT / entry["path"]).is_file()


def test_upper_bound_witness_catalog_autoqec_entries_match_verifier() -> None:
    manifest = _load_witness_fixture_manifest()
    hx_payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / manifest["hx_path"])
    hz_payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / manifest["hz_path"])
    results_by_id = {}

    for entry in _fixture_entries("autoqec-witness"):
        witness_payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / entry["path"])
        result = verify_css_upper_bound_witness(
            hx_payload,
            hz_payload,
            witness_payload,
        )
        results_by_id[entry["id"]] = result
        assert result["status"] == entry["expected_verifier_status"]
        if entry["expected_verifier_status"] == "pass":
            assert result["basis"] == entry["basis"]
            assert result["weight"] == entry["expected_weight"]
            assert result["distance_payload"] == {
                "status": "completed",
                "method": "css-upper-bound-witness",
                "bound_type": "upper",
                "upper_bound": entry["expected_weight"],
                "basis": entry["basis"],
            }
        else:
            assert result["reason"] == entry["expected_reason"]

    assert results_by_id["autoqec-x-logical"]["weight"] == 2
    assert results_by_id["autoqec-z-logical"]["weight"] == 2
    assert results_by_id["autoqec-x-stabilizer-row-space"] == {
        "status": "fail",
        "reason": "in_stabilizer_row_space",
    }
    assert results_by_id["autoqec-x-length-mismatch"] == {
        "status": "fail",
        "reason": "length_mismatch",
    }


def test_qec_code_random_window_upper_bound_fixtures_match_contract() -> None:
    valid_ids = set()
    rejection_reasons = {}

    for entry in _fixture_entries("qec-code-result"):
        payload = _load_fixture_json(WITNESS_FIXTURE_ROOT / entry["path"])
        rejection_reason = _validate_qec_code_random_window_contract(payload)
        if entry["expected_contract_status"] == "valid":
            valid_ids.add(entry["id"])
            assert rejection_reason is None
            assert payload["status"] == "completed"
            assert payload["method"] == "random-window-upper-bound"
            assert payload["bound_type"] == "upper"
            assert payload["upper_bound"] == entry["expected_weight"]
            assert payload["logical_class"] == entry["basis"]
            assert payload["witness"]["weight"] == entry["expected_weight"]
            assert set(payload["witness"]) == {"x", "z", "weight"}
            assert isinstance(payload["options"], dict)
            assert isinstance(payload["provenance"], dict)
        else:
            rejection_reasons[entry["id"]] = rejection_reason
            assert rejection_reason == entry["expected_rejection_reason"]

    assert valid_ids == {
        "qec-code-random-window-x-completed",
        "qec-code-random-window-z-completed",
    }
    assert rejection_reasons == {
        "qec-code-mixed-logical-class": "unsupported_logical_class",
        "qec-code-upper-bound-weight-mismatch": "upper_bound_weight_mismatch",
        "qec-code-x-z-width-mismatch": "x_z_width_mismatch",
        "qec-code-non-binary-witness-entry": "non_binary_witness_entry",
        "qec-code-malformed-missing-witness": "missing_witness",
    }
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness.py -q
```

Expected: FAIL because `benchmarks/fixtures/upper-bound-witness/manifest.json` does not exist yet.

- [ ] **Step 3: Create the fixture catalog files**

Create `benchmarks/fixtures/upper-bound-witness/hx.json`:

```json
{
  "data": [
    [
      1,
      1,
      0,
      0
    ]
  ],
  "format": "dense_binary_matrix",
  "n_cols": 4,
  "n_rows": 1
}
```

Create `benchmarks/fixtures/upper-bound-witness/hz.json`:

```json
{
  "data": [
    [
      0,
      0,
      1,
      1
    ]
  ],
  "format": "dense_binary_matrix",
  "n_cols": 4,
  "n_rows": 1
}
```

Create `benchmarks/fixtures/upper-bound-witness/autoqec/x-logical-witness.json`:

```json
{
  "basis": "x",
  "vector": [
    0,
    0,
    1,
    1
  ]
}
```

Create `benchmarks/fixtures/upper-bound-witness/autoqec/z-logical-witness.json`:

```json
{
  "basis": "z",
  "vector": [
    1,
    1,
    0,
    0
  ]
}
```

Create `benchmarks/fixtures/upper-bound-witness/autoqec/x-stabilizer-row-space.json`:

```json
{
  "basis": "x",
  "vector": [
    1,
    1,
    0,
    0
  ]
}
```

Create `benchmarks/fixtures/upper-bound-witness/autoqec/x-length-mismatch.json`:

```json
{
  "basis": "x",
  "vector": [
    0,
    0,
    1
  ]
}
```

Create `benchmarks/fixtures/upper-bound-witness/qec-code/random-window-x-completed.json`:

```json
{
  "bound_type": "upper",
  "logical_class": "x",
  "method": "random-window-upper-bound",
  "options": {
    "iterations": 16,
    "method": "random-window-upper-bound",
    "seed": 61
  },
  "provenance": {
    "catalog_id": "upper-bound-witness-known-answer-v1",
    "generated_by": "AutoQEC fixture",
    "source": "known-answer-toy-css"
  },
  "status": "completed",
  "upper_bound": 2,
  "witness": {
    "weight": 2,
    "x": [
      0,
      0,
      1,
      1
    ],
    "z": [
      0,
      0,
      0,
      0
    ]
  }
}
```

Create `benchmarks/fixtures/upper-bound-witness/qec-code/random-window-z-completed.json`:

```json
{
  "bound_type": "upper",
  "logical_class": "z",
  "method": "random-window-upper-bound",
  "options": {
    "iterations": 16,
    "method": "random-window-upper-bound",
    "seed": 62
  },
  "provenance": {
    "catalog_id": "upper-bound-witness-known-answer-v1",
    "generated_by": "AutoQEC fixture",
    "source": "known-answer-toy-css"
  },
  "status": "completed",
  "upper_bound": 2,
  "witness": {
    "weight": 2,
    "x": [
      0,
      0,
      0,
      0
    ],
    "z": [
      1,
      1,
      0,
      0
    ]
  }
}
```

Create `benchmarks/fixtures/upper-bound-witness/qec-code/mixed-logical-class.json`:

```json
{
  "bound_type": "upper",
  "logical_class": "mixed",
  "method": "random-window-upper-bound",
  "options": {
    "iterations": 16,
    "method": "random-window-upper-bound",
    "seed": 63
  },
  "provenance": {
    "catalog_id": "upper-bound-witness-known-answer-v1",
    "generated_by": "AutoQEC fixture",
    "source": "known-answer-toy-css"
  },
  "status": "completed",
  "upper_bound": 2,
  "witness": {
    "weight": 2,
    "x": [
      0,
      0,
      1,
      1
    ],
    "z": [
      0,
      0,
      0,
      0
    ]
  }
}
```

Create `benchmarks/fixtures/upper-bound-witness/qec-code/upper-bound-weight-mismatch.json`:

```json
{
  "bound_type": "upper",
  "logical_class": "x",
  "method": "random-window-upper-bound",
  "options": {
    "iterations": 16,
    "method": "random-window-upper-bound",
    "seed": 64
  },
  "provenance": {
    "catalog_id": "upper-bound-witness-known-answer-v1",
    "generated_by": "AutoQEC fixture",
    "source": "known-answer-toy-css"
  },
  "status": "completed",
  "upper_bound": 3,
  "witness": {
    "weight": 2,
    "x": [
      0,
      0,
      1,
      1
    ],
    "z": [
      0,
      0,
      0,
      0
    ]
  }
}
```

Create `benchmarks/fixtures/upper-bound-witness/qec-code/x-z-width-mismatch.json`:

```json
{
  "bound_type": "upper",
  "logical_class": "x",
  "method": "random-window-upper-bound",
  "options": {
    "iterations": 16,
    "method": "random-window-upper-bound",
    "seed": 65
  },
  "provenance": {
    "catalog_id": "upper-bound-witness-known-answer-v1",
    "generated_by": "AutoQEC fixture",
    "source": "known-answer-toy-css"
  },
  "status": "completed",
  "upper_bound": 2,
  "witness": {
    "weight": 2,
    "x": [
      0,
      0,
      1,
      1
    ],
    "z": [
      0,
      0,
      0
    ]
  }
}
```

Create `benchmarks/fixtures/upper-bound-witness/qec-code/non-binary-witness-entry.json`:

```json
{
  "bound_type": "upper",
  "logical_class": "x",
  "method": "random-window-upper-bound",
  "options": {
    "iterations": 16,
    "method": "random-window-upper-bound",
    "seed": 66
  },
  "provenance": {
    "catalog_id": "upper-bound-witness-known-answer-v1",
    "generated_by": "AutoQEC fixture",
    "source": "known-answer-toy-css"
  },
  "status": "completed",
  "upper_bound": 2,
  "witness": {
    "weight": 2,
    "x": [
      0,
      0,
      1,
      2
    ],
    "z": [
      0,
      0,
      0,
      0
    ]
  }
}
```

Create `benchmarks/fixtures/upper-bound-witness/qec-code/malformed-missing-witness.json`:

```json
{
  "bound_type": "upper",
  "logical_class": "x",
  "method": "random-window-upper-bound",
  "options": {
    "iterations": 16,
    "method": "random-window-upper-bound",
    "seed": 67
  },
  "provenance": {
    "catalog_id": "upper-bound-witness-known-answer-v1",
    "generated_by": "AutoQEC fixture",
    "source": "known-answer-toy-css"
  },
  "status": "completed",
  "upper_bound": 2
}
```

Create `benchmarks/fixtures/upper-bound-witness/manifest.json`:

```json
{
  "catalog_id": "upper-bound-witness-known-answer-v1",
  "description": "Tiny known-answer CSS upper-bound witness fixtures for AutoQEC verifier and qec-code random-window result conversion tests.",
  "hx_path": "hx.json",
  "hz_path": "hz.json",
  "fixtures": [
    {
      "basis": "x",
      "expected_verifier_status": "pass",
      "expected_weight": 2,
      "id": "autoqec-x-logical",
      "path": "autoqec/x-logical-witness.json",
      "payload_kind": "autoqec-witness"
    },
    {
      "basis": "z",
      "expected_verifier_status": "pass",
      "expected_weight": 2,
      "id": "autoqec-z-logical",
      "path": "autoqec/z-logical-witness.json",
      "payload_kind": "autoqec-witness"
    },
    {
      "basis": "x",
      "expected_reason": "in_stabilizer_row_space",
      "expected_verifier_status": "fail",
      "expected_weight": 2,
      "id": "autoqec-x-stabilizer-row-space",
      "path": "autoqec/x-stabilizer-row-space.json",
      "payload_kind": "autoqec-witness"
    },
    {
      "basis": "x",
      "expected_reason": "length_mismatch",
      "expected_verifier_status": "fail",
      "expected_weight": 1,
      "id": "autoqec-x-length-mismatch",
      "path": "autoqec/x-length-mismatch.json",
      "payload_kind": "autoqec-witness"
    },
    {
      "basis": "x",
      "expected_contract_status": "valid",
      "expected_verifier_status": "not_applicable",
      "expected_weight": 2,
      "id": "qec-code-random-window-x-completed",
      "path": "qec-code/random-window-x-completed.json",
      "payload_kind": "qec-code-result"
    },
    {
      "basis": "z",
      "expected_contract_status": "valid",
      "expected_verifier_status": "not_applicable",
      "expected_weight": 2,
      "id": "qec-code-random-window-z-completed",
      "path": "qec-code/random-window-z-completed.json",
      "payload_kind": "qec-code-result"
    },
    {
      "basis": "mixed",
      "expected_contract_status": "invalid",
      "expected_rejection_reason": "unsupported_logical_class",
      "expected_verifier_status": "not_applicable",
      "expected_weight": 2,
      "id": "qec-code-mixed-logical-class",
      "path": "qec-code/mixed-logical-class.json",
      "payload_kind": "qec-code-result"
    },
    {
      "basis": "x",
      "expected_contract_status": "invalid",
      "expected_rejection_reason": "upper_bound_weight_mismatch",
      "expected_verifier_status": "not_applicable",
      "expected_weight": 2,
      "id": "qec-code-upper-bound-weight-mismatch",
      "path": "qec-code/upper-bound-weight-mismatch.json",
      "payload_kind": "qec-code-result"
    },
    {
      "basis": "x",
      "expected_contract_status": "invalid",
      "expected_rejection_reason": "x_z_width_mismatch",
      "expected_verifier_status": "not_applicable",
      "expected_weight": 2,
      "id": "qec-code-x-z-width-mismatch",
      "path": "qec-code/x-z-width-mismatch.json",
      "payload_kind": "qec-code-result"
    },
    {
      "basis": "x",
      "expected_contract_status": "invalid",
      "expected_rejection_reason": "non_binary_witness_entry",
      "expected_verifier_status": "not_applicable",
      "expected_weight": 2,
      "id": "qec-code-non-binary-witness-entry",
      "path": "qec-code/non-binary-witness-entry.json",
      "payload_kind": "qec-code-result"
    },
    {
      "basis": "x",
      "expected_contract_status": "invalid",
      "expected_rejection_reason": "missing_witness",
      "expected_verifier_status": "not_applicable",
      "expected_weight": 2,
      "id": "qec-code-malformed-missing-witness",
      "path": "qec-code/malformed-missing-witness.json",
      "payload_kind": "qec-code-result"
    }
  ]
}
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness.py -q
```

Expected: PASS with 11 tests passing.

- [ ] **Step 5: Run the requested full verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add benchmarks/fixtures/upper-bound-witness tests/test_search_upper_bound_witness.py docs/superpowers/plans/2026-07-08-issue-61-upper-bound-witness-fixtures.md
git commit -m "test: add upper-bound witness fixtures"
```
