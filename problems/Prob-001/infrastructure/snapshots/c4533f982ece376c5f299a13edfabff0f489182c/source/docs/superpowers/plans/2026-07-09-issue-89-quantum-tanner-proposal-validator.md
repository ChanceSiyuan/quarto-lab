# Quantum Tanner Proposal Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic validator and CLI for schema-valid quantum Tanner AI proposal JSON files.

**Architecture:** Add a focused `autoqec_search.quantum_tanner_proposals` module with typed rejection classes, pure-Python semantic checks, normalized summaries, and stable fingerprints. Keep `autoqec_search.cli` as a thin adapter that delegates to the module and maps typed rejections to nonzero CLI output.

**Tech Stack:** Python 3.11, standard library `json`, `hashlib`, `dataclasses`, `pathlib`, existing `jsonschema` dependency, and `pytest`.

## Global Constraints

- Validate one proposal JSON file that conforms to `benchmarks/schemas/quantum-tanner-proposal.schema.json`.
- Keep the validator independent of `qec-code`, `rsinter`, GAP, Oscar, qLDPC, Julia, and network access.
- Enforce the configured group-order limit before associativity checks.
- Reject typed errors named `GroupOrderLimitExceeded`, `InvalidGroupTable`, `NonSymmetricGeneratorSet`, `InvalidLocalCodeMatrix`, `LocalCodeWidthMismatch`, and `KnownToricTemplateDuplicate`.
- Derive the stable fingerprint from canonical validated proposal content, not file paths, timestamps outside the proposal content, or output directories.

---

## File Structure

- Create `src/autoqec_search/quantum_tanner_proposals.py`: typed errors, validation functions, summary dataclass, canonical fingerprinting, and toric duplicate detection.
- Modify `src/autoqec_search/cli.py`: add the `validate-quantum-tanner-proposal` parser and command branch.
- Modify `tests/test_search_quantum_tanner_proposals.py`: add semantic validator tests beside the existing schema and fixture-catalog tests.
- Modify `tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json`: make the schema-valid positive fixture semantically valid by using inverse-symmetric generator coordinates with matching local-code widths.
- Create semantic rejection fixtures under `tests/fixtures/quantum_tanner_proposals/`: bad group table, nonsymmetric generators, bad local-code width, known toric duplicate, and oversized group.

---

### Task 1: Core Group Validator and Typed Errors

**Files:**
- Create: `src/autoqec_search/quantum_tanner_proposals.py`
- Modify: `tests/test_search_quantum_tanner_proposals.py`
- Create: `tests/fixtures/quantum_tanner_proposals/invalid-bad-group-table.json`
- Create: `tests/fixtures/quantum_tanner_proposals/invalid-oversized-bad-associativity.json`

**Interfaces:**
- Consumes: schema-valid proposal dictionaries from issue 88 fixtures.
- Produces:
  - `class QuantumTannerProposalValidationError(ValueError)`
  - `class GroupOrderLimitExceeded(QuantumTannerProposalValidationError)`
  - `class InvalidGroupTable(QuantumTannerProposalValidationError)`
  - `def validate_quantum_tanner_proposal(payload: dict[str, Any], *, max_group_order: int = 32) -> QuantumTannerProposalSummary`

- [ ] **Step 1: Write failing tests for bad group table and order guard**

Add this import block near the top of `tests/test_search_quantum_tanner_proposals.py`:

```python
from autoqec_search.quantum_tanner_proposals import (
    GroupOrderLimitExceeded,
    InvalidGroupTable,
    validate_quantum_tanner_proposal_file,
)
```

Add fixture constants after `CATALOG_PATH`:

```python
BAD_GROUP_TABLE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-bad-group-table.json"
)
OVERSIZED_GROUP_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-oversized-bad-associativity.json"
)
```

Add these tests near the semantic validator section at the end of the file:

```python
def test_deterministic_proposal_validator_rejects_bad_group_table() -> None:
    with pytest.raises(InvalidGroupTable) as exc_info:
        validate_quantum_tanner_proposal_file(BAD_GROUP_TABLE_PATH, max_group_order=32)

    assert exc_info.value.kind == "InvalidGroupTable"


def test_deterministic_proposal_validator_rejects_group_order_over_limit_before_associativity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autoqec_search.quantum_tanner_proposals as proposals

    def fail_if_called(table: list[list[int]]) -> None:
        raise AssertionError("associativity check should not run")

    monkeypatch.setattr(proposals, "_validate_associativity", fail_if_called)

    with pytest.raises(GroupOrderLimitExceeded) as exc_info:
        validate_quantum_tanner_proposal_file(OVERSIZED_GROUP_PATH, max_group_order=8)

    assert exc_info.value.kind == "GroupOrderLimitExceeded"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_bad_group_table \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_group_order_over_limit_before_associativity \
  -q
```

Expected: collection fails with `ModuleNotFoundError` or the new fixture paths are missing.

- [ ] **Step 3: Add semantic group fixtures**

Create `tests/fixtures/quantum_tanner_proposals/invalid-bad-group-table.json` as a copy of the D3 proposal structure with a malformed first row:

```json
{
  "proposal_id": "dihedral-d3-bad-group-table-v1",
  "schema_version": 1,
  "construction_mode": "lr_cayley_no_cover_v1",
  "base_group": {
    "name": "D3",
    "element_order": "id = i + 3*j for r^i s^j with i in Z3 and j in Z2",
    "order": 6,
    "identity": 0,
    "multiplication_table": [
      [0, 1, 2, 3, 4],
      [1, 2, 0, 4, 5, 3],
      [2, 0, 1, 5, 3, 4],
      [3, 5, 4, 0, 2, 1],
      [4, 3, 5, 1, 0, 2],
      [5, 4, 3, 2, 1, 0]
    ]
  },
  "a_generator_indices": [1, 2, 3],
  "b_generator_indices": [1, 2, 4],
  "local_codes": {
    "matrix_role": "parity_check",
    "field": "GF(2)",
    "h_a": [[1, 0, 1], [0, 1, 1]],
    "h_b": [[1, 1, 0], [1, 0, 1]]
  },
  "search_hints": {
    "target_distance": 3,
    "max_group_order": 12,
    "tags": ["invalid-fixture", "bad-group-table"]
  },
  "provenance": {
    "source": "test-fixture",
    "model": "fixture-author",
    "generated_at": "2026-07-09T00:00:00Z",
    "prompt_summary": "Malformed group table negative control."
  }
}
```

Create `tests/fixtures/quantum_tanner_proposals/invalid-oversized-bad-associativity.json` with a schema-valid order-9 table whose order exceeds the test limit:

```json
{
  "proposal_id": "oversized-z9-bad-associativity-v1",
  "schema_version": 1,
  "construction_mode": "lr_cayley_no_cover_v1",
  "base_group": {
    "name": "Z9-mutated",
    "element_order": "id = i for i in Z9",
    "order": 9,
    "identity": 0,
    "multiplication_table": [
      [0, 1, 2, 3, 4, 5, 6, 7, 8],
      [1, 2, 3, 4, 5, 6, 7, 8, 0],
      [2, 3, 4, 5, 6, 7, 8, 0, 1],
      [3, 4, 5, 6, 7, 8, 0, 1, 2],
      [4, 5, 6, 7, 8, 0, 1, 2, 3],
      [5, 6, 7, 8, 0, 1, 2, 3, 4],
      [6, 7, 8, 0, 1, 2, 3, 4, 5],
      [7, 8, 0, 1, 2, 3, 4, 5, 6],
      [8, 0, 1, 2, 3, 4, 5, 6, 1]
    ]
  },
  "a_generator_indices": [1, 8],
  "b_generator_indices": [2, 7],
  "local_codes": {
    "matrix_role": "parity_check",
    "field": "GF(2)",
    "h_a": [[1, 1]],
    "h_b": [[1, 1]]
  },
  "search_hints": {
    "target_distance": 3,
    "max_group_order": 9,
    "tags": ["invalid-fixture", "oversized"]
  },
  "provenance": {
    "source": "test-fixture",
    "model": "fixture-author",
    "generated_at": "2026-07-09T00:00:00Z",
    "prompt_summary": "Oversized proposal used to prove the order guard runs first."
  }
}
```

- [ ] **Step 4: Implement group validation**

Create `src/autoqec_search/quantum_tanner_proposals.py` with:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json


VALIDATOR_VERSION = "quantum-tanner-proposal-validator-v1"


class QuantumTannerProposalValidationError(ValueError):
    kind = "QuantumTannerProposalValidationError"

    def __init__(self, message: str):
        super().__init__(f"{self.kind}: {message}")
        self.message = message


class GroupOrderLimitExceeded(QuantumTannerProposalValidationError):
    kind = "GroupOrderLimitExceeded"


class InvalidGroupTable(QuantumTannerProposalValidationError):
    kind = "InvalidGroupTable"


@dataclass(frozen=True)
class QuantumTannerProposalSummary:
    proposal_id: str
    group_order: int
    a_generator_count: int
    b_generator_count: int
    h_a_dimensions: tuple[int, int]
    h_b_dimensions: tuple[int, int]
    validator_version: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["h_a_dimensions"] = list(self.h_a_dimensions)
        payload["h_b_dimensions"] = list(self.h_b_dimensions)
        return payload


def validate_quantum_tanner_proposal_file(
    path: Path,
    *,
    max_group_order: int = 32,
) -> QuantumTannerProposalSummary:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise InvalidGroupTable("proposal payload must be a JSON object")
    return validate_quantum_tanner_proposal(payload, max_group_order=max_group_order)


def validate_quantum_tanner_proposal(
    payload: dict[str, Any],
    *,
    max_group_order: int = 32,
) -> QuantumTannerProposalSummary:
    table = _validate_group_table(payload, max_group_order=max_group_order)
    _validate_associativity(table)
    return QuantumTannerProposalSummary(
        proposal_id=str(payload["proposal_id"]),
        group_order=len(table),
        a_generator_count=len(payload["a_generator_indices"]),
        b_generator_count=len(payload["b_generator_indices"]),
        h_a_dimensions=(len(payload["local_codes"]["h_a"]), len(payload["local_codes"]["h_a"][0])),
        h_b_dimensions=(len(payload["local_codes"]["h_b"]), len(payload["local_codes"]["h_b"][0])),
        validator_version=VALIDATOR_VERSION,
        fingerprint="",
    )


def _validate_group_table(
    payload: dict[str, Any],
    *,
    max_group_order: int,
) -> list[list[int]]:
    group = payload.get("base_group")
    if not isinstance(group, dict):
        raise InvalidGroupTable("base_group must be an object")
    order = group.get("order")
    identity = group.get("identity")
    table = group.get("multiplication_table")
    if type(order) is not int or order <= 0:
        raise InvalidGroupTable("base_group.order must be a positive integer")
    if order > max_group_order:
        raise GroupOrderLimitExceeded(
            f"group order {order} exceeds max_group_order {max_group_order}"
        )
    if type(identity) is not int or identity < 0 or identity >= order:
        raise InvalidGroupTable("base_group.identity must be in range")
    if not isinstance(table, list) or len(table) != order:
        raise InvalidGroupTable("multiplication_table must have order rows")
    normalized: list[list[int]] = []
    for row_index, row in enumerate(table):
        if not isinstance(row, list) or len(row) != order:
            raise InvalidGroupTable(
                f"multiplication_table row {row_index} must have width {order}"
            )
        normalized_row: list[int] = []
        for column_index, value in enumerate(row):
            if type(value) is not int or value < 0 or value >= order:
                raise InvalidGroupTable(
                    f"multiplication_table[{row_index}][{column_index}] is out of range"
                )
            normalized_row.append(value)
        normalized.append(normalized_row)
    for element in range(order):
        if normalized[identity][element] != element or normalized[element][identity] != element:
            raise InvalidGroupTable("identity laws failed")
        has_left_inverse = any(normalized[candidate][element] == identity for candidate in range(order))
        has_right_inverse = any(normalized[element][candidate] == identity for candidate in range(order))
        if not has_left_inverse or not has_right_inverse:
            raise InvalidGroupTable(f"element {element} does not have two-sided inverses")
    return normalized


def _validate_associativity(table: list[list[int]]) -> None:
    order = len(table)
    for left in range(order):
        for middle in range(order):
            left_middle = table[left][middle]
            for right in range(order):
                if table[left_middle][right] != table[left][table[middle][right]]:
                    raise InvalidGroupTable(
                        f"associativity failed at ({left}, {middle}, {right})"
                    )
```

- [ ] **Step 5: Run tests for Task 1**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_bad_group_table \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_group_order_over_limit_before_associativity \
  -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add src/autoqec_search/quantum_tanner_proposals.py tests/test_search_quantum_tanner_proposals.py tests/fixtures/quantum_tanner_proposals/invalid-bad-group-table.json tests/fixtures/quantum_tanner_proposals/invalid-oversized-bad-associativity.json
git commit -m "feat: add quantum tanner group validator"
```

---

### Task 2: Generator and Local-Code Validation

**Files:**
- Modify: `src/autoqec_search/quantum_tanner_proposals.py`
- Modify: `tests/test_search_quantum_tanner_proposals.py`
- Modify: `tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json`
- Create: `tests/fixtures/quantum_tanner_proposals/invalid-nonsymmetric-generators.json`
- Create: `tests/fixtures/quantum_tanner_proposals/invalid-local-code-width.json`

**Interfaces:**
- Consumes: `validate_quantum_tanner_proposal_file(path, max_group_order=32)` from Task 1.
- Produces:
  - `class NonSymmetricGeneratorSet(QuantumTannerProposalValidationError)`
  - `class InvalidLocalCodeMatrix(QuantumTannerProposalValidationError)`
  - `class LocalCodeWidthMismatch(QuantumTannerProposalValidationError)`
  - Summary values with correct generator counts and local-code dimensions.

- [ ] **Step 1: Write failing tests for valid, nonsymmetric, and width mismatch**

Extend the import block in `tests/test_search_quantum_tanner_proposals.py`:

```python
from autoqec_search.quantum_tanner_proposals import (
    GroupOrderLimitExceeded,
    InvalidGroupTable,
    LocalCodeWidthMismatch,
    NonSymmetricGeneratorSet,
    validate_quantum_tanner_proposal_file,
)
```

Add constants:

```python
VALID_D3_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "valid-dihedral-d3.json"
)
NONSYMMETRIC_GENERATORS_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-nonsymmetric-generators.json"
)
BAD_LOCAL_CODE_WIDTH_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-local-code-width.json"
)
```

Add tests:

```python
def test_deterministic_proposal_validator_accepts_valid_non_toric_fixture() -> None:
    summary = validate_quantum_tanner_proposal_file(VALID_D3_PATH, max_group_order=32)

    assert summary.proposal_id == "valid-dihedral-d3"
    assert summary.group_order == 6
    assert summary.a_generator_count == 3
    assert summary.b_generator_count == 3
    assert summary.h_a_dimensions == (2, 3)
    assert summary.h_b_dimensions == (2, 3)
    assert summary.validator_version == "quantum-tanner-proposal-validator-v1"
    assert len(summary.fingerprint) == 64


def test_deterministic_proposal_validator_rejects_nonsymmetric_generators() -> None:
    with pytest.raises(NonSymmetricGeneratorSet) as exc_info:
        validate_quantum_tanner_proposal_file(NONSYMMETRIC_GENERATORS_PATH, max_group_order=32)

    assert exc_info.value.kind == "NonSymmetricGeneratorSet"


def test_deterministic_proposal_validator_rejects_bad_local_code_width() -> None:
    with pytest.raises(LocalCodeWidthMismatch) as exc_info:
        validate_quantum_tanner_proposal_file(BAD_LOCAL_CODE_WIDTH_PATH, max_group_order=32)

    assert exc_info.value.kind == "LocalCodeWidthMismatch"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_accepts_valid_non_toric_fixture \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_nonsymmetric_generators \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_bad_local_code_width \
  -q
```

Expected: imports or assertions fail until the semantic checks and fixtures exist.

- [ ] **Step 3: Update and add local semantic fixtures**

Modify `tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json`:

```json
{
  "proposal_id": "valid-dihedral-d3",
  "a_generator_indices": [1, 2, 3],
  "b_generator_indices": [1, 2, 4],
  "search_hints": {
    "target_distance": 3,
    "max_group_order": 12,
    "tags": ["non-toric", "dihedral", "catalog-fixture"]
  }
}
```

Keep all unchanged fields from the existing file, including the D3 multiplication table, local-code matrices, and provenance.

Create `tests/fixtures/quantum_tanner_proposals/invalid-nonsymmetric-generators.json` as the same proposal with:

```json
{
  "proposal_id": "dihedral-d3-nonsymmetric-generators-v1",
  "a_generator_indices": [1, 3],
  "b_generator_indices": [1, 2, 4],
  "local_codes": {
    "matrix_role": "parity_check",
    "field": "GF(2)",
    "h_a": [[1, 1], [0, 1]],
    "h_b": [[1, 1, 0], [1, 0, 1]]
  }
}
```

Create `tests/fixtures/quantum_tanner_proposals/invalid-local-code-width.json` as the valid D3 proposal with:

```json
{
  "proposal_id": "dihedral-d3-local-code-width-v1",
  "a_generator_indices": [1, 2, 3],
  "b_generator_indices": [1, 2, 4],
  "local_codes": {
    "matrix_role": "parity_check",
    "field": "GF(2)",
    "h_a": [[1, 0], [0, 1]],
    "h_b": [[1, 1, 0], [1, 0, 1]]
  }
}
```

Keep the D3 group table, schema version, construction mode, search hints, and provenance schema-valid.

- [ ] **Step 4: Implement generator and matrix validation**

Add classes and helpers to `src/autoqec_search/quantum_tanner_proposals.py`:

```python
class NonSymmetricGeneratorSet(QuantumTannerProposalValidationError):
    kind = "NonSymmetricGeneratorSet"


class InvalidLocalCodeMatrix(QuantumTannerProposalValidationError):
    kind = "InvalidLocalCodeMatrix"


class LocalCodeWidthMismatch(QuantumTannerProposalValidationError):
    kind = "LocalCodeWidthMismatch"


def _inverse_map(table: list[list[int]], identity: int) -> dict[int, int]:
    inverses: dict[int, int] = {}
    for element in range(len(table)):
        for candidate in range(len(table)):
            if table[element][candidate] == identity and table[candidate][element] == identity:
                inverses[element] = candidate
                break
        if element not in inverses:
            raise InvalidGroupTable(f"element {element} does not have a two-sided inverse")
    return inverses


def _validate_generator_set(
    payload: dict[str, Any],
    *,
    key: str,
    order: int,
    inverses: dict[int, int],
) -> tuple[int, ...]:
    raw = payload.get(key)
    if not isinstance(raw, list) or not raw:
        raise NonSymmetricGeneratorSet(f"{key} must be a nonempty list")
    seen: set[int] = set()
    generators: list[int] = []
    for index, value in enumerate(raw):
        if type(value) is not int or value < 0 or value >= order:
            raise NonSymmetricGeneratorSet(f"{key}[{index}] is out of range")
        if value in seen:
            raise NonSymmetricGeneratorSet(f"{key} contains duplicate generator {value}")
        seen.add(value)
        generators.append(value)
    missing = sorted(inverses[value] for value in generators if inverses[value] not in seen)
    if missing:
        raise NonSymmetricGeneratorSet(f"{key} is not closed under inverses: missing {missing}")
    return tuple(generators)


def _validate_binary_matrix(payload: dict[str, Any], *, key: str) -> tuple[tuple[int, ...], ...]:
    local_codes = payload.get("local_codes")
    if not isinstance(local_codes, dict):
        raise InvalidLocalCodeMatrix("local_codes must be an object")
    matrix = local_codes.get(key)
    if not isinstance(matrix, list) or not matrix:
        raise InvalidLocalCodeMatrix(f"{key} must be a nonempty matrix")
    width: int | None = None
    rows: list[tuple[int, ...]] = []
    for row_index, row in enumerate(matrix):
        if not isinstance(row, list) or not row:
            raise InvalidLocalCodeMatrix(f"{key} row {row_index} must be nonempty")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise InvalidLocalCodeMatrix(f"{key} rows must have equal width")
        normalized_row: list[int] = []
        for column_index, value in enumerate(row):
            if value not in (0, 1):
                raise InvalidLocalCodeMatrix(
                    f"{key}[{row_index}][{column_index}] must be 0 or 1"
                )
            normalized_row.append(int(value))
        rows.append(tuple(normalized_row))
    return tuple(rows)
```

Update `validate_quantum_tanner_proposal` to compute `identity`, `inverses`, generator tuples, matrices, and width checks before returning:

```python
    group = payload["base_group"]
    identity = int(group["identity"])
    inverses = _inverse_map(table, identity)
    a_generators = _validate_generator_set(
        payload,
        key="a_generator_indices",
        order=len(table),
        inverses=inverses,
    )
    b_generators = _validate_generator_set(
        payload,
        key="b_generator_indices",
        order=len(table),
        inverses=inverses,
    )
    h_a = _validate_binary_matrix(payload, key="h_a")
    h_b = _validate_binary_matrix(payload, key="h_b")
    if len(h_a[0]) != len(a_generators):
        raise LocalCodeWidthMismatch(
            f"h_a width {len(h_a[0])} does not match |A| {len(a_generators)}"
        )
    if len(h_b[0]) != len(b_generators):
        raise LocalCodeWidthMismatch(
            f"h_b width {len(h_b[0])} does not match |B| {len(b_generators)}"
        )
```

Use `a_generators`, `b_generators`, `h_a`, and `h_b` when filling the summary dimensions.

- [ ] **Step 5: Run tests for Task 2**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_accepts_valid_non_toric_fixture \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_nonsymmetric_generators \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_bad_local_code_width \
  -q
```

Expected: all three tests pass.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add src/autoqec_search/quantum_tanner_proposals.py tests/test_search_quantum_tanner_proposals.py tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json tests/fixtures/quantum_tanner_proposals/invalid-nonsymmetric-generators.json tests/fixtures/quantum_tanner_proposals/invalid-local-code-width.json
git commit -m "feat: validate quantum tanner generators and local codes"
```

---

### Task 3: Fingerprint, Toric Duplicate Detection, and CLI

**Files:**
- Modify: `src/autoqec_search/quantum_tanner_proposals.py`
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_quantum_tanner_proposals.py`
- Create: `tests/fixtures/quantum_tanner_proposals/known-toric-template-duplicate.json`

**Interfaces:**
- Consumes: successful semantic validation from Task 2.
- Produces:
  - `class KnownToricTemplateDuplicate(QuantumTannerProposalValidationError)`
  - Summary `fingerprint` based on canonical validated content.
  - CLI command `autoqec-search validate-quantum-tanner-proposal --proposal <path> --max-group-order <int>`.

- [ ] **Step 1: Write failing fingerprint, toric duplicate, and CLI tests**

Extend the import block:

```python
from autoqec_search.quantum_tanner_proposals import (
    GroupOrderLimitExceeded,
    InvalidGroupTable,
    KnownToricTemplateDuplicate,
    LocalCodeWidthMismatch,
    NonSymmetricGeneratorSet,
    validate_quantum_tanner_proposal_file,
)
```

Add constant:

```python
KNOWN_TORIC_DUPLICATE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "known-toric-template-duplicate.json"
)
```

Leave the positive test's `assert len(summary.fingerprint) == 64` in place until
Step 6 computes the exact fingerprint from the completed canonicalization code.

Add rejection and CLI tests:

```python
def test_deterministic_proposal_validator_rejects_known_toric_template_duplicate() -> None:
    with pytest.raises(KnownToricTemplateDuplicate) as exc_info:
        validate_quantum_tanner_proposal_file(KNOWN_TORIC_DUPLICATE_PATH, max_group_order=32)

    assert exc_info.value.kind == "KnownToricTemplateDuplicate"


def test_validate_quantum_tanner_proposal_cli_reports_pass_and_typed_failures() -> None:
    import os
    import subprocess
    import sys

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    valid = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate-quantum-tanner-proposal",
            "--proposal",
            str(VALID_D3_PATH),
            "--max-group-order",
            "32",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert valid.returncode == 0, valid.stderr
    assert "PASS quantum_tanner_proposal proposal_id=valid-dihedral-d3" in valid.stdout

    toric = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate-quantum-tanner-proposal",
            "--proposal",
            str(KNOWN_TORIC_DUPLICATE_PATH),
            "--max-group-order",
            "32",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert toric.returncode == 1
    assert "KnownToricTemplateDuplicate" in toric.stderr

    oversized = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate-quantum-tanner-proposal",
            "--proposal",
            str(OVERSIZED_GROUP_PATH),
            "--max-group-order",
            "8",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert oversized.returncode == 1
    assert "GroupOrderLimitExceeded" in oversized.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_accepts_valid_non_toric_fixture \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_known_toric_template_duplicate \
  tests/test_search_quantum_tanner_proposals.py::test_validate_quantum_tanner_proposal_cli_reports_pass_and_typed_failures \
  -q
```

Expected: toric fixture missing and CLI command missing.

- [ ] **Step 3: Add known toric duplicate fixture**

Create `tests/fixtures/quantum_tanner_proposals/known-toric-template-duplicate.json`
from the committed `toric-d4` construction by copying its `base_group`,
`a_generator_indices`, `b_generator_indices`, and `local_codes` fields into this
proposal envelope:

```python
from pathlib import Path
import json

root = Path(".")
source = json.loads(
    (
        root
        / "benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/quantum_tanner_specs/toric-d4.json"
    ).read_text()
)
proposal = {
    "proposal_id": "known-toric-template-duplicate-d4",
    "schema_version": 1,
    "construction_mode": source["construction_mode"],
    "base_group": source["base_group"],
    "a_generator_indices": source["a_generator_indices"],
    "b_generator_indices": source["b_generator_indices"],
    "local_codes": source["local_codes"],
    "search_hints": {
        "target_distance": 4,
        "max_group_order": 16,
        "tags": ["toric-template-duplicate"],
    },
    "provenance": {
        "source": "test-fixture",
        "model": "fixture-author",
        "generated_at": "2026-07-09T00:00:00Z",
        "prompt_summary": "Known toric quantum Tanner duplicate negative control.",
    },
}
target = root / "tests/fixtures/quantum_tanner_proposals/known-toric-template-duplicate.json"
target.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Implement canonical fingerprint and toric detection**

Add imports:

```python
import hashlib
```

Add error class:

```python
class KnownToricTemplateDuplicate(QuantumTannerProposalValidationError):
    kind = "KnownToricTemplateDuplicate"
```

Add canonical helpers:

```python
def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _fingerprint(canonical_payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(canonical_payload).encode("utf-8")).hexdigest()


def _is_known_toric_template_duplicate(
    *,
    payload: dict[str, Any],
    a_generators: tuple[int, ...],
    b_generators: tuple[int, ...],
    h_a: tuple[tuple[int, ...], ...],
    h_b: tuple[tuple[int, ...], ...],
) -> bool:
    group = payload["base_group"]
    order = int(group["order"])
    root = int(order**0.5)
    if root * root != order or root < 2:
        return False
    if group.get("identity") != 0:
        return False
    if a_generators != (root, root * (root - 1)):
        return False
    if b_generators != (1, root - 1):
        return False
    if h_a != ((1, 1),) or h_b != ((1, 1),):
        return False
    table = group["multiplication_table"]
    for left in range(order):
        lx, ly = divmod(left, root)
        for right in range(order):
            rx, ry = divmod(right, root)
            expected = root * ((lx + rx) % root) + ((ly + ry) % root)
            if table[left][right] != expected:
                return False
    return True
```

Before summary creation, call the duplicate check:

```python
    if _is_known_toric_template_duplicate(
        payload=payload,
        a_generators=a_generators,
        b_generators=b_generators,
        h_a=h_a,
        h_b=h_b,
    ):
        raise KnownToricTemplateDuplicate(
            "proposal matches the committed Zm x Zm toric Tanner template"
        )
```

Build canonical content and fingerprint:

```python
    canonical = {
        "proposal_id": payload["proposal_id"],
        "schema_version": payload["schema_version"],
        "construction_mode": payload["construction_mode"],
        "base_group": {
            "name": group["name"],
            "element_order": group["element_order"],
            "order": len(table),
            "identity": identity,
            "multiplication_table": table,
        },
        "a_generator_indices": list(a_generators),
        "b_generator_indices": list(b_generators),
        "local_codes": {
            "matrix_role": payload["local_codes"]["matrix_role"],
            "field": payload["local_codes"]["field"],
            "h_a": [list(row) for row in h_a],
            "h_b": [list(row) for row in h_b],
        },
    }
    stable_fingerprint = _fingerprint(canonical)
```

Use `stable_fingerprint` in the summary.

- [ ] **Step 5: Implement CLI command**

Modify imports in `src/autoqec_search/cli.py`:

```python
from autoqec_search.quantum_tanner_proposals import (
    QuantumTannerProposalValidationError,
    validate_quantum_tanner_proposal_file,
)
```

Add parser after `validate-quantum-tanner-sweep`:

```python
    validate_qt_proposal_parser = subparsers.add_parser(
        "validate-quantum-tanner-proposal",
        help="Validate a quantum Tanner AI proposal JSON file",
    )
    validate_qt_proposal_parser.add_argument("--proposal", required=True)
    validate_qt_proposal_parser.add_argument("--max-group-order", type=int, default=32)
```

Add command branch after the sweep validation branch:

```python
        if args.command == "validate-quantum-tanner-proposal":
            summary = validate_quantum_tanner_proposal_file(
                Path(args.proposal),
                max_group_order=args.max_group_order,
            )
            print(
                "PASS quantum_tanner_proposal "
                f"proposal_id={summary.proposal_id} "
                f"group_order={summary.group_order} "
                f"fingerprint={summary.fingerprint}"
            )
            print(json.dumps(summary.to_dict(), sort_keys=True))
            return 0
```

Extend the `except` tuple with `QuantumTannerProposalValidationError`.

- [ ] **Step 6: Compute and pin the stable fingerprint**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-proposal \
  --proposal tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json \
  --max-group-order 32
```

Expected: output starts with `PASS quantum_tanner_proposal proposal_id=valid-dihedral-d3`.

Replace the positive test's `assert len(summary.fingerprint) == 64` with an
exact assertion using the full 64-character fingerprint printed by the command.

- [ ] **Step 7: Run tests for Task 3**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_accepts_valid_non_toric_fixture \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_known_toric_template_duplicate \
  tests/test_search_quantum_tanner_proposals.py::test_validate_quantum_tanner_proposal_cli_reports_pass_and_typed_failures \
  -q
```

Expected: all three tests pass.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add src/autoqec_search/quantum_tanner_proposals.py src/autoqec_search/cli.py tests/test_search_quantum_tanner_proposals.py tests/fixtures/quantum_tanner_proposals/known-toric-template-duplicate.json
git commit -m "feat: add quantum tanner proposal CLI validator"
```

---

### Task 4: Required Verification and PR Preparation

**Files:**
- Verify: all touched files.
- Modify only if verification reveals a defect in Task 1-3 behavior.

**Interfaces:**
- Consumes: completed validator module and CLI.
- Produces: passing issue-specific tests, passing full pytest command, manual CLI evidence, final implementation commit if fixes are needed.

- [ ] **Step 1: Run the issue-specific pytest command**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_accepts_valid_non_toric_fixture \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_bad_group_table \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_nonsymmetric_generators \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_bad_local_code_width \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_known_toric_template_duplicate \
  tests/test_search_quantum_tanner_proposals.py::test_deterministic_proposal_validator_rejects_group_order_over_limit_before_associativity \
  -q
```

Expected: all six tests pass.

- [ ] **Step 2: Run manual CLI success check**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-proposal \
  --proposal tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json \
  --max-group-order 32
```

Expected: stdout includes `PASS quantum_tanner_proposal proposal_id=valid-dihedral-d3`.

- [ ] **Step 3: Run manual CLI toric rejection check**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-proposal \
  --proposal tests/fixtures/quantum_tanner_proposals/known-toric-template-duplicate.json \
  --max-group-order 32
```

Expected: exit code 1 and stderr includes `KnownToricTemplateDuplicate`.

- [ ] **Step 4: Run manual CLI oversized rejection check**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-proposal \
  --proposal tests/fixtures/quantum_tanner_proposals/invalid-oversized-bad-associativity.json \
  --max-group-order 8
```

Expected: exit code 1 and stderr includes `GroupOrderLimitExceeded`.

- [ ] **Step 5: Run the full required repository test command**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: all tests pass.

- [ ] **Step 6: Inspect git status and diff**

Run:

```bash
git status --short
git diff --stat main...HEAD
```

Expected: only issue 89 spec, plan, validator, CLI, tests, and fixture files changed.

- [ ] **Step 7: Commit verification fixes if any files changed**

If verification required edits, run:

```bash
git add src/autoqec_search/quantum_tanner_proposals.py src/autoqec_search/cli.py tests/test_search_quantum_tanner_proposals.py tests/fixtures/quantum_tanner_proposals
git commit -m "test: cover quantum tanner proposal validator"
```

If no files changed, skip this step.
