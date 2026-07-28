# Quantum Tanner Proposal Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a strict v1 JSON Schema and fixtures/tests for untrusted quantum Tanner AI proposal objects.

**Architecture:** Keep the feature schema-only. Tests load the schema directly with `jsonschema.Draft202012Validator`, validate one non-toric dihedral fixture, and exercise rejection paths for required fields and unsupported modes.

**Tech Stack:** JSON Schema Draft 2020-12, Python 3.11+, `jsonschema`, `pytest`.

## Global Constraints

- Add `benchmarks/schemas/quantum-tanner-proposal.schema.json`.
- Add focused tests under `tests/test_search_quantum_tanner_proposals.py`.
- Add fixtures under `tests/fixtures/quantum_tanner_proposals/`.
- Allow only `construction_mode: "lr_cayley_no_cover_v1"`.
- Allow only `local_codes.field: "GF(2)"`.
- Allow only `local_codes.matrix_role: "parity_check"`.
- Reject unknown top-level fields.
- Keep this issue to schema-level validation only; do not implement group laws, generator symmetry, local-code width checks, toric-template duplicate rejection, qec-code materialization, API calls, benchmark execution, or search strategy changes.
- Verification commands:
  - `PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_schema_accepts_non_toric_fixture tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_schema_rejects_missing_required_fields -q`
  - `PYTHONPATH=src python3 -m autoqec_search.cli validate --root .`

---

### Task 1: Proposal Schema Contract

**Files:**
- Create: `tests/fixtures/quantum_tanner_proposals/dihedral-d4-proposal.json`
- Create: `tests/test_search_quantum_tanner_proposals.py`
- Create: `benchmarks/schemas/quantum-tanner-proposal.schema.json`

**Interfaces:**
- Consumes: repository-local `jsonschema` dependency and the fixture path under `tests/fixtures/quantum_tanner_proposals/`.
- Produces: `benchmarks/schemas/quantum-tanner-proposal.schema.json`, a Draft 2020-12 schema validated by focused tests.

- [ ] **Step 1: Write the failing fixture and tests**

Create `tests/fixtures/quantum_tanner_proposals/dihedral-d4-proposal.json` with a structurally valid non-toric dihedral group proposal:

```json
{
  "proposal_id": "dihedral-d4-ai-proposal-v1",
  "schema_version": 1,
  "construction_mode": "lr_cayley_no_cover_v1",
  "base_group": {
    "name": "D4",
    "element_order": "id = i + 4*j for r^i s^j with i in Z4 and j in Z2",
    "order": 8,
    "identity": 0,
    "multiplication_table": [
      [0, 1, 2, 3, 4, 5, 6, 7],
      [1, 2, 3, 0, 5, 6, 7, 4],
      [2, 3, 0, 1, 6, 7, 4, 5],
      [3, 0, 1, 2, 7, 4, 5, 6],
      [4, 7, 6, 5, 0, 3, 2, 1],
      [5, 4, 7, 6, 1, 0, 3, 2],
      [6, 5, 4, 7, 2, 1, 0, 3],
      [7, 6, 5, 4, 3, 2, 1, 0]
    ]
  },
  "a_generator_indices": [1, 4],
  "b_generator_indices": [2, 5],
  "local_codes": {
    "matrix_role": "parity_check",
    "field": "GF(2)",
    "h_a": [
      [1, 0, 1],
      [0, 1, 1]
    ],
    "h_b": [
      [1, 1, 0],
      [0, 1, 1]
    ]
  },
  "search_hints": {
    "target_distance": 3,
    "max_group_order": 16,
    "tags": ["non-toric", "dihedral"]
  },
  "provenance": {
    "source": "test-fixture",
    "model": "fixture-author",
    "generated_at": "2026-07-09T00:00:00Z",
    "prompt_summary": "Small non-toric dihedral proposal for schema validation."
  }
}
```

Create `tests/test_search_quantum_tanner_proposals.py`:

```python
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "benchmarks" / "schemas" / "quantum-tanner-proposal.schema.json"
FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "dihedral-d4-proposal.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _validator() -> Draft202012Validator:
    schema = _load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _fixture() -> dict:
    return _load_json(FIXTURE_PATH)


def _json_pointer(error: ValidationError) -> str:
    if not error.path:
        return "/"
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in error.path]
    return "/" + "/".join(escaped)


def test_quantum_tanner_proposal_schema_accepts_non_toric_fixture() -> None:
    _validator().validate(_fixture())


def test_quantum_tanner_proposal_schema_rejects_missing_required_fields() -> None:
    proposal = _fixture()
    del proposal["local_codes"]["field"]

    with pytest.raises(ValidationError) as exc_info:
        _validator().validate(proposal)

    assert _json_pointer(exc_info.value) == "/local_codes"
    assert exc_info.value.validator == "required"
    assert "'field' is a required property" in exc_info.value.message


def test_quantum_tanner_proposal_schema_rejects_unknown_top_level_fields() -> None:
    proposal = _fixture()
    proposal["unexpected"] = True

    with pytest.raises(ValidationError) as exc_info:
        _validator().validate(proposal)

    assert _json_pointer(exc_info.value) == "/"
    assert exc_info.value.validator == "additionalProperties"


@pytest.mark.parametrize(
    ("path", "value", "expected_pointer"),
    [
        (("construction_mode",), "covered_left_right_v1", "/construction_mode"),
        (("local_codes", "field"), "GF(4)", "/local_codes/field"),
        (("local_codes", "matrix_role"), "generator", "/local_codes/matrix_role"),
    ],
)
def test_quantum_tanner_proposal_schema_rejects_unsupported_modes(
    path: tuple[str, ...], value: object, expected_pointer: str
) -> None:
    proposal = copy.deepcopy(_fixture())
    target = proposal
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError) as exc_info:
        _validator().validate(proposal)

    assert _json_pointer(exc_info.value) == expected_pointer
```

- [ ] **Step 2: Run the focused tests to verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_schema_accepts_non_toric_fixture tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_schema_rejects_missing_required_fields -q
```

Expected: FAIL because `benchmarks/schemas/quantum-tanner-proposal.schema.json` does not exist yet.

- [ ] **Step 3: Add the minimal schema**

Create `benchmarks/schemas/quantum-tanner-proposal.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://autoqec.local/schemas/quantum-tanner-proposal.schema.json",
  "title": "Quantum Tanner AI Proposal",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "proposal_id",
    "schema_version",
    "construction_mode",
    "base_group",
    "a_generator_indices",
    "b_generator_indices",
    "local_codes",
    "provenance"
  ],
  "$defs": {
    "generatorIndex": {
      "type": "integer",
      "minimum": 0
    },
    "generatorIndexSet": {
      "type": "array",
      "minItems": 1,
      "uniqueItems": true,
      "items": { "$ref": "#/$defs/generatorIndex" }
    },
    "binaryMatrix": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "array",
        "minItems": 1,
        "items": { "enum": [0, 1] }
      }
    }
  },
  "properties": {
    "proposal_id": { "type": "string", "minLength": 1 },
    "schema_version": { "const": 1 },
    "construction_mode": { "const": "lr_cayley_no_cover_v1" },
    "base_group": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "element_order", "order", "identity", "multiplication_table"],
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "element_order": { "type": "string", "minLength": 1 },
        "order": { "type": "integer", "minimum": 1 },
        "identity": { "type": "integer", "minimum": 0 },
        "multiplication_table": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "array",
            "minItems": 1,
            "items": { "type": "integer", "minimum": 0 }
          }
        }
      }
    },
    "a_generator_indices": { "$ref": "#/$defs/generatorIndexSet" },
    "b_generator_indices": { "$ref": "#/$defs/generatorIndexSet" },
    "local_codes": {
      "type": "object",
      "additionalProperties": false,
      "required": ["matrix_role", "field", "h_a", "h_b"],
      "properties": {
        "matrix_role": { "const": "parity_check" },
        "field": { "const": "GF(2)" },
        "h_a": { "$ref": "#/$defs/binaryMatrix" },
        "h_b": { "$ref": "#/$defs/binaryMatrix" }
      }
    },
    "search_hints": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "target_distance": { "type": "integer", "minimum": 1 },
        "target_rate": {
          "type": "number",
          "exclusiveMinimum": 0,
          "exclusiveMaximum": 1
        },
        "max_group_order": { "type": "integer", "minimum": 1 },
        "tags": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 },
          "uniqueItems": true
        },
        "notes": { "type": "string" }
      }
    },
    "provenance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["source", "model", "generated_at"],
      "properties": {
        "source": { "type": "string", "minLength": 1 },
        "model": { "type": "string", "minLength": 1 },
        "generated_at": {
          "type": "string",
          "pattern": "^\\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
        },
        "prompt_summary": { "type": "string", "minLength": 1 }
      }
    }
  }
}
```

- [ ] **Step 4: Run focused tests to verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_proposals.py -q
```

Expected: PASS.

- [ ] **Step 5: Run required verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_schema_accepts_non_toric_fixture tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_schema_rejects_missing_required_fields -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

Run:

```bash
git add docs/superpowers/specs/2026-07-09-quantum-tanner-proposal-schema-design.md docs/superpowers/plans/2026-07-09-quantum-tanner-proposal-schema.md benchmarks/schemas/quantum-tanner-proposal.schema.json tests/fixtures/quantum_tanner_proposals/dihedral-d4-proposal.json tests/test_search_quantum_tanner_proposals.py
git commit -m "feat: add quantum tanner proposal schema"
```
