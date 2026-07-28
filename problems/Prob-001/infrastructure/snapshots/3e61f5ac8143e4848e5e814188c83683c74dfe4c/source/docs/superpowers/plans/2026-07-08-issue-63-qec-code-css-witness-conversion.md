# Issue 63 qec-code CSS Witness Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert qec-code random-window upper-bound witness payloads into verified AutoQEC CSS upper-bound witness JSON payloads.

**Architecture:** Keep qec-code result contract checks and conversion in `autoqec_search.upper_bound_witness_finder`, because that module already owns qec-code command execution and result validation. Add a pure converter that returns AutoQEC witness, distance payload, verifier result, and qec-code sidecar provenance, plus a convenience runner that invokes qec-code and converts the result.

**Tech Stack:** Python 3, pytest, AutoQEC `SearchIntegrityError`, `verify_css_upper_bound_witness()`, JSON fixture files under `benchmarks/fixtures/upper-bound-witness/`.

## Global Constraints

- Accept qec-code `logical_class == "x_like"` with nonzero `witness.x` as AutoQEC basis `x`.
- Accept qec-code `logical_class == "z_like"` with nonzero `witness.z` as AutoQEC basis `z`.
- Reject `mixed` witnesses and any qec-code result that requires a mixed Pauli observable.
- Reject payloads where `upper_bound != witness.weight`, x/z widths disagree, entries are non-binary, selected vector is zero, complementary Pauli support is nonzero, or CSS verifier fails.
- Preserve optional fields such as `search_stats` in an optional sidecar result.
- Do not edit campaign search spaces or choose a quantum Tanner benchmark basis.

---

## File Structure

- Modify `benchmarks/fixtures/upper-bound-witness/qec-code/random-window-x-completed.json`: change `logical_class` from `x` to `x_like`.
- Modify `benchmarks/fixtures/upper-bound-witness/qec-code/random-window-z-completed.json`: change `logical_class` from `z` to `z_like`.
- Modify `benchmarks/fixtures/upper-bound-witness/qec-code/mixed-logical-class.json`: ensure `logical_class` is `mixed`.
- Modify `tests/test_search_upper_bound_witness.py`: update fixture contract expectations for qec-code logical classes.
- Modify `tests/test_search_upper_bound_witness_finder.py`: add converter and convenience runner tests.
- Modify `src/autoqec_search/upper_bound_witness_finder.py`: add class normalization, conversion, re-verification, sidecar output, and convenience runner.

---

### Task 1: Fixture Contract Uses qec-code Logical Class Names

**Files:**
- Modify: `benchmarks/fixtures/upper-bound-witness/qec-code/random-window-x-completed.json`
- Modify: `benchmarks/fixtures/upper-bound-witness/qec-code/random-window-z-completed.json`
- Modify: `tests/test_search_upper_bound_witness.py`

**Interfaces:**
- Consumes: existing fixture manifest entries with basis `x` and `z`.
- Produces: qec-code fixture payloads whose `logical_class` values are `x_like` and `z_like`.

- [ ] **Step 1: Write the failing test update**

In `tests/test_search_upper_bound_witness.py`, add this helper near `_validate_qec_code_random_window_contract()`:

```python
def _qec_code_logical_class_to_basis(logical_class: str) -> str | None:
    return {
        "x_like": "x",
        "z_like": "z",
    }.get(logical_class)
```

Then update the valid-fixture assertions:

```python
basis = _qec_code_logical_class_to_basis(payload["logical_class"])
assert basis == entry["basis"]
selected_vector = payload["witness"][basis]
non_selected_component = (
    payload["witness"]["z"] if basis == "x" else payload["witness"]["x"]
)
verify_result = verify_css_upper_bound_witness(
    hx_payload,
    hz_payload,
    {
        "basis": basis,
        "vector": selected_vector,
    },
)
```

Also update `_validate_qec_code_random_window_contract()` so it rejects anything outside `{"x_like", "z_like"}` and uses the mapped basis when checking the selected vector.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness.py::test_qec_code_random_window_upper_bound_fixtures_match_contract -q
```

Expected: FAIL because the existing fixtures still use `logical_class` values `x` and `z`.

- [ ] **Step 3: Update fixture JSON**

Change the completed qec-code fixtures:

```json
"logical_class": "x_like"
```

and:

```json
"logical_class": "z_like"
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness.py::test_qec_code_random_window_upper_bound_fixtures_match_contract -q
```

Expected: PASS.

---

### Task 2: Converter API

**Files:**
- Modify: `tests/test_search_upper_bound_witness_finder.py`
- Modify: `src/autoqec_search/upper_bound_witness_finder.py`

**Interfaces:**
- Produces: `convert_qec_code_random_window_upper_bound_result(payload: object, hx_payload: dict, hz_payload: dict) -> dict[str, Any]`.
- Produces: converter result keys `status`, `witness_payload`, `distance_payload`, `verification`, and `qec_code_result`.

- [ ] **Step 1: Write failing conversion tests**

Import the converter:

```python
from autoqec_search.upper_bound_witness_finder import (
    convert_qec_code_random_window_upper_bound_result,
    run_qec_code_random_window_upper_bound,
)
```

Add tests:

```python
def test_convert_qec_code_random_window_upper_bound_result_converts_x_like_fixture() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    result = convert_qec_code_random_window_upper_bound_result(
        payload,
        _load_json(FIXTURE_ROOT / "hx.json"),
        _load_json(FIXTURE_ROOT / "hz.json"),
    )

    assert result["status"] == "completed"
    assert result["witness_payload"] == {"basis": "x", "vector": [0, 0, 1, 1]}
    assert result["distance_payload"] == {
        "status": "completed",
        "method": "css-upper-bound-witness",
        "bound_type": "upper",
        "upper_bound": 2,
        "basis": "x",
    }
    assert result["verification"]["status"] == "pass"
    assert result["qec_code_result"] == payload


def test_convert_qec_code_random_window_upper_bound_result_converts_z_like_fixture() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-z-completed.json")
    result = convert_qec_code_random_window_upper_bound_result(
        payload,
        _load_json(FIXTURE_ROOT / "hx.json"),
        _load_json(FIXTURE_ROOT / "hz.json"),
    )

    assert result["witness_payload"] == {"basis": "z", "vector": [1, 1, 0, 0]}
    assert result["distance_payload"]["upper_bound"] == 2
    assert result["distance_payload"]["basis"] == "z"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness_finder.py::test_convert_qec_code_random_window_upper_bound_result_converts_x_like_fixture tests/test_search_upper_bound_witness_finder.py::test_convert_qec_code_random_window_upper_bound_result_converts_z_like_fixture -q
```

Expected: FAIL with import error because the converter is not implemented.

- [ ] **Step 3: Implement converter**

In `src/autoqec_search/upper_bound_witness_finder.py`, import the verifier:

```python
from autoqec_search.structure import verify_css_upper_bound_witness
```

Add:

```python
LOGICAL_CLASS_TO_BASIS = {
    "x_like": "x",
    "z_like": "z",
}
```

Update `_validate_witness()` to map `logical_class` through `LOGICAL_CLASS_TO_BASIS`, select the vector by basis, reject nonzero complementary support with `nonzero_complementary_pauli_support`, reject zero selected vector with `selected_witness_vector_zero`, and keep the existing width, binary, and weight checks.

Add:

```python
def convert_qec_code_random_window_upper_bound_result(
    payload: object,
    hx_payload: dict,
    hz_payload: dict,
) -> dict[str, Any]:
    validate_qec_code_random_window_upper_bound_result(payload)
    assert isinstance(payload, dict)
    witness = payload["witness"]
    basis = LOGICAL_CLASS_TO_BASIS[payload["logical_class"]]
    vector = [int(bit) for bit in witness[basis]]
    witness_payload = {"basis": basis, "vector": vector}
    verification = verify_css_upper_bound_witness(hx_payload, hz_payload, witness_payload)
    if verification.get("status") != "pass":
        reason = verification.get("reason", "invalid_upper_bound_witness")
        raise SearchIntegrityError(f"invalid_css_upper_bound_witness: {reason}")
    return {
        "status": "completed",
        "witness_payload": witness_payload,
        "distance_payload": verification["distance_payload"],
        "verification": verification,
        "qec_code_result": payload,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness_finder.py::test_convert_qec_code_random_window_upper_bound_result_converts_x_like_fixture tests/test_search_upper_bound_witness_finder.py::test_convert_qec_code_random_window_upper_bound_result_converts_z_like_fixture -q
```

Expected: PASS.

---

### Task 3: Negative Controls and Sidecar Preservation

**Files:**
- Modify: `tests/test_search_upper_bound_witness_finder.py`
- Modify: `src/autoqec_search/upper_bound_witness_finder.py`

**Interfaces:**
- Consumes: `convert_qec_code_random_window_upper_bound_result()`.
- Produces: rejection behavior for mixed, malformed, mixed-support, zero selected vector, and verifier-failing payloads.

- [ ] **Step 1: Write failing rejection tests**

Add tests:

```python
@pytest.mark.parametrize(
    ("fixture_name", "expected_error"),
    [
        ("mixed-logical-class.json", "unsupported_logical_class"),
        ("upper-bound-weight-mismatch.json", "upper_bound_weight_mismatch"),
        ("x-z-width-mismatch.json", "x_z_width_mismatch"),
        ("non-binary-witness-entry.json", "non_binary_witness_entry"),
        ("malformed-missing-witness.json", "missing_witness"),
    ],
)
def test_convert_qec_code_random_window_upper_bound_result_rejects_invalid_fixtures(
    fixture_name: str,
    expected_error: str,
) -> None:
    with pytest.raises(SearchIntegrityError, match=expected_error):
        convert_qec_code_random_window_upper_bound_result(
            _load_json(QEC_CODE_FIXTURE_ROOT / fixture_name),
            _load_json(FIXTURE_ROOT / "hx.json"),
            _load_json(FIXTURE_ROOT / "hz.json"),
        )


def test_convert_qec_code_random_window_upper_bound_result_rejects_nonzero_complement() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["witness"]["z"] = [1, 0, 0, 0]
    payload["witness"]["weight"] = 3
    payload["upper_bound"] = 3

    with pytest.raises(SearchIntegrityError, match="nonzero_complementary_pauli_support"):
        convert_qec_code_random_window_upper_bound_result(
            payload,
            _load_json(FIXTURE_ROOT / "hx.json"),
            _load_json(FIXTURE_ROOT / "hz.json"),
        )


def test_convert_qec_code_random_window_upper_bound_result_rejects_zero_selected_vector() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["witness"]["x"] = [0, 0, 0, 0]
    payload["witness"]["z"] = [1, 1, 0, 0]

    with pytest.raises(SearchIntegrityError, match="selected_witness_vector_zero"):
        convert_qec_code_random_window_upper_bound_result(
            payload,
            _load_json(FIXTURE_ROOT / "hx.json"),
            _load_json(FIXTURE_ROOT / "hz.json"),
        )


def test_convert_qec_code_random_window_upper_bound_result_rejects_css_verifier_failure() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["witness"]["x"] = [1, 1, 0, 0]

    with pytest.raises(SearchIntegrityError, match="invalid_css_upper_bound_witness: in_stabilizer_row_space"):
        convert_qec_code_random_window_upper_bound_result(
            payload,
            _load_json(FIXTURE_ROOT / "hx.json"),
            _load_json(FIXTURE_ROOT / "hz.json"),
        )


def test_convert_qec_code_random_window_upper_bound_result_preserves_search_stats_sidecar() -> None:
    payload = _load_json(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json")
    payload["search_stats"] = {"attempts": 4, "frontier_size": 2}

    result = convert_qec_code_random_window_upper_bound_result(
        payload,
        _load_json(FIXTURE_ROOT / "hx.json"),
        _load_json(FIXTURE_ROOT / "hz.json"),
    )

    assert result["qec_code_result"]["search_stats"] == {"attempts": 4, "frontier_size": 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness_finder.py -q
```

Expected: FAIL for the not-yet-complete rejection details.

- [ ] **Step 3: Finish validation details**

Ensure `_validate_witness()` checks selected-vector nonzero before comparing selected weight and checks complementary support before returning witness data.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness_finder.py -q
```

Expected: PASS.

---

### Task 4: Convenience Runner and Full Verification

**Files:**
- Modify: `tests/test_search_upper_bound_witness_finder.py`
- Modify: `src/autoqec_search/upper_bound_witness_finder.py`

**Interfaces:**
- Produces: `run_qec_code_random_window_upper_bound_css_witness(...) -> dict[str, Any]` with the same command arguments as `run_qec_code_random_window_upper_bound()` plus `hx_payload` and `hz_payload`.

- [ ] **Step 1: Write failing convenience runner test**

Add:

```python
def test_run_qec_code_random_window_upper_bound_css_witness_converts_completed_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    monkeypatch.setenv(
        "AUTOQEC_FAKE_QEC_CODE_PAYLOAD",
        str(QEC_CODE_FIXTURE_ROOT / "random-window-x-completed.json"),
    )

    result = run_qec_code_random_window_upper_bound_css_witness(
        FIXTURE_ROOT / "hx.json",
        FIXTURE_ROOT / "hz.json",
        hx_payload=_load_json(FIXTURE_ROOT / "hx.json"),
        hz_payload=_load_json(FIXTURE_ROOT / "hz.json"),
        qec_code_bin=str(fake_qec_code),
        iterations=16,
        restarts=3,
        seed=61,
        target_weight=2,
        timeout_seconds=5,
    )

    assert result["witness_payload"] == {"basis": "x", "vector": [0, 0, 1, 1]}
    assert result["distance_payload"]["method"] == "css-upper-bound-witness"
    assert result["qec_code_result"]["method"] == "random-window-upper-bound"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness_finder.py::test_run_qec_code_random_window_upper_bound_css_witness_converts_completed_payload -q
```

Expected: FAIL with import or name error.

- [ ] **Step 3: Implement convenience runner**

Add:

```python
def run_qec_code_random_window_upper_bound_css_witness(
    hx_path: str | Path,
    hz_path: str | Path,
    *,
    hx_payload: dict,
    hz_payload: dict,
    qec_code_bin: str,
    iterations: int,
    restarts: int,
    seed: int,
    target_weight: int | None = None,
    timeout_seconds: float = 300,
) -> dict[str, Any]:
    result = run_qec_code_random_window_upper_bound(
        hx_path,
        hz_path,
        qec_code_bin=qec_code_bin,
        iterations=iterations,
        restarts=restarts,
        seed=seed,
        target_weight=target_weight,
        timeout_seconds=timeout_seconds,
    )
    return convert_qec_code_random_window_upper_bound_result(
        result,
        hx_payload,
        hz_payload,
    )
```

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness_finder.py tests/test_search_upper_bound_witness.py -q
PYTHONPATH=src python3 -m pytest
```

Expected: both commands PASS.
