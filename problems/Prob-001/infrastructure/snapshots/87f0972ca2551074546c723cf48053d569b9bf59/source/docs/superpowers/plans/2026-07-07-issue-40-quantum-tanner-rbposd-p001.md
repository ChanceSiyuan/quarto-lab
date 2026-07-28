# Issue 40 Quantum Tanner RBP-OSD p=0.001 Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pinned quantum Tanner CSS memory benchmark suite that evaluates only `p=0.001` with `rbposd-osd10-v1`.

**Architecture:** The contract is benchmark data plus focused tests. A new task under `benchmarks/tasks/` defines the general CSS memory experiment. A new suite under `benchmarks/suites/` binds that task to one existing rbposd decoder. Tests validate the p-list, decoder pin, CSS route, and copied bad p=0.01 records.

**Tech Stack:** JSON benchmark contracts, Python 3, pytest, existing `autoqec_search.load`, `autoqec_search.rsinter`, and `autoqec_search.quantum_tanner_catalog` helpers.

## Global Constraints

- New task id is exactly `quantum-tanner-css-memory-x-rbposd-p001-v1`.
- New suite id is exactly `quantum-tanner-rbposd-p001-v1`.
- Suite decoder ids are exactly `["rbposd-osd10-v1"]`.
- Task `p_list` is exactly `[0.001]`.
- Task `input_type` is exactly `"css"`.
- Task `css_memory.observables` is exactly `"optional"`.
- Do not add `predict-zero-v1` to the quantum Tanner suite.
- Do not add new decoders or run the full quantum Tanner campaign.
- Focused verification command must print `4 passed`: `PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_benchmark_contracts.py`.
- Workspace validation command must exit 0 and print `validated search workspace`: `PYTHONPATH=src python3 -m autoqec_search.cli validate --root .`.
- Full verification command must pass: `PYTHONPATH=src python3 -m pytest`.

---

## File Structure

- Create `tests/test_search_quantum_tanner_benchmark_contracts.py`: four issue-level contract tests.
- Create `benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json`: one-p task.
- Create `benchmarks/suites/quantum-tanner-rbposd-p001-v1.json`: one-decoder rbposd suite.
- Modify `tests/test_search_load.py`: include the new task and suite in the workspace inventory expectation.

---

### Task 1: Contract Tests And Benchmark Records

**Files:**
- Create: `tests/test_search_quantum_tanner_benchmark_contracts.py`
- Create: `benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json`
- Create: `benchmarks/suites/quantum-tanner-rbposd-p001-v1.json`

**Interfaces:**
- Consumes: `load_search_workspace(root) -> SearchWorkspace`, `load_quantum_tanner_fixture_catalog(root) -> dict`, `resolve_quantum_tanner_fixture_entry(root, entry) -> ResolvedCandidate`, `write_css_spec_toml(...) -> None`.
- Produces: a task id and suite id loadable by `load_search_workspace`.

- [ ] **Step 1: Write the failing contract tests**

Create `tests/test_search_quantum_tanner_benchmark_contracts.py`:

```python
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.quantum_tanner_catalog import (
    load_quantum_tanner_fixture_catalog,
    resolve_quantum_tanner_fixture_entry,
)
from autoqec_search.rsinter import (
    rounds_for_task,
    task_requires_explicit_css_observables,
    validate_selected_p_values,
    write_css_spec_toml,
)
from autoqec_search.structure import summarize_css_structure


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "quantum-tanner-css-memory-x-rbposd-p001-v1"
SUITE_ID = "quantum-tanner-rbposd-p001-v1"
DECODER_ID = "rbposd-osd10-v1"


def _suite_task_decoder() -> tuple[dict, dict, dict, dict]:
    workspace = load_search_workspace(REPO_ROOT)
    suite = workspace.suites[SUITE_ID]
    assert suite["task_ids"] == [TASK_ID]
    task = workspace.tasks[TASK_ID]
    decoder = workspace.decoders[DECODER_ID]
    return workspace.decoders, suite, task, decoder


def _contains_probability(payload: object, target: float) -> bool:
    if isinstance(payload, bool):
        return False
    if isinstance(payload, int | float):
        return math.isclose(float(payload), target, rel_tol=0.0, abs_tol=1e-15)
    if isinstance(payload, dict):
        return any(_contains_probability(value, target) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_probability(value, target) for value in payload)
    return False


def _assert_no_bad_probability(payload: object) -> None:
    if _contains_probability(payload, 0.01):
        raise SearchIntegrityError("quantum Tanner benchmark must not contain p=0.01")


def _assert_quantum_tanner_p001_task(task: dict) -> None:
    _assert_no_bad_probability(task)
    if task.get("p_list") != [0.001]:
        raise SearchIntegrityError("quantum Tanner benchmark must use exactly p=0.001")


def _assert_quantum_tanner_suite(suite: dict, decoders: dict[str, dict]) -> None:
    _assert_no_bad_probability(suite)
    if suite.get("decoder_ids") != [DECODER_ID]:
        raise SearchIntegrityError("quantum Tanner suite must pin rbposd-osd10-v1")
    decoder = decoders[DECODER_ID]
    if decoder.get("impl_key") != "rbposd":
        raise SearchIntegrityError("quantum Tanner suite decoder must be rbposd")


def test_quantum_tanner_suite_contains_exactly_p001() -> None:
    _, suite, task, _ = _suite_task_decoder()

    assert suite["task_ids"] == [TASK_ID]
    assert task["p_list"] == [0.001]
    assert validate_selected_p_values(task, None) == [0.001]
    _assert_quantum_tanner_p001_task(task)


def test_quantum_tanner_suite_pins_one_rbposd_decoder() -> None:
    decoders, suite, _, decoder = _suite_task_decoder()

    assert suite["decoder_ids"] == [DECODER_ID]
    assert decoder["impl_key"] == "rbposd"
    assert decoder["parameters"]["osd_order"] == 10
    assert "predict-zero-v1" not in suite["decoder_ids"]
    _assert_quantum_tanner_suite(suite, decoders)

    bad_suite = deepcopy(suite)
    bad_suite["decoder_ids"] = ["predict-zero-v1"]
    with pytest.raises(SearchIntegrityError, match="rbposd-osd10-v1"):
        _assert_quantum_tanner_suite(bad_suite, decoders)

    bad_suite = deepcopy(suite)
    bad_suite["decoder_ids"] = ["rmatching-default-v1"]
    with pytest.raises(SearchIntegrityError, match="rbposd-osd10-v1"):
        _assert_quantum_tanner_suite(bad_suite, decoders)


def test_quantum_tanner_task_routes_through_general_css_memory_path(
    tmp_path: Path,
) -> None:
    decoders, suite, task, _ = _suite_task_decoder()
    catalog = load_quantum_tanner_fixture_catalog(REPO_ROOT)
    candidate = resolve_quantum_tanner_fixture_entry(REPO_ROOT, catalog["entries"][0])

    assert task["input_type"] == "css"
    assert task["observable"] == "logical_x"
    assert task["css_memory"] == {
        "basis": "x",
        "observables": "optional",
        "schedule": "greedy",
        "seed": 12345,
    }
    assert task_requires_explicit_css_observables(task) is False
    assert candidate.observables_x is None
    assert summarize_css_structure(candidate.hx, candidate.hz)["css_commute"] is True

    spec_path = tmp_path / "spec.toml"
    write_css_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=suite["decoder_ids"],
        code_id=candidate.spec.code_family,
        hx_path=Path("input/hx.css.json"),
        hz_path=Path("input/hz.css.json"),
        rounds=rounds_for_task(task, distance=None),
        p_values=validate_selected_p_values(task, None),
    )

    spec = spec_path.read_text()
    assert 'input_type = "css"' in spec
    assert 'impl_key = "rbposd"' in spec
    assert "p = [0.001]" in spec
    assert "observables =" not in spec


def test_quantum_tanner_contract_rejects_copied_bad_p001_records() -> None:
    decoders, suite, task, _ = _suite_task_decoder()

    bad_task = deepcopy(task)
    bad_task["p_list"] = [0.01]
    with pytest.raises(SearchIntegrityError, match="p=0.01"):
        _assert_quantum_tanner_p001_task(bad_task)

    bad_task = deepcopy(task)
    bad_task["p_list"] = [0.001, 0.01]
    with pytest.raises(SearchIntegrityError, match="p=0.01"):
        _assert_quantum_tanner_p001_task(bad_task)

    bad_suite = deepcopy(suite)
    bad_suite["shared_settings"]["default_p"] = 0.01
    with pytest.raises(SearchIntegrityError, match="p=0.01"):
        _assert_quantum_tanner_suite(bad_suite, decoders)
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_benchmark_contracts.py
```

Expected: FAIL with a missing suite/task key for `quantum-tanner-rbposd-p001-v1`.

- [ ] **Step 3: Add the benchmark task JSON**

Create `benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json`:

```json
{
  "collection": {
    "batch_size": 16,
    "max_errors": 16,
    "max_shots": 64
  },
  "css_memory": {
    "basis": "x",
    "observables": "optional",
    "schedule": "greedy",
    "seed": 12345
  },
  "execution_status": "real",
  "id": "quantum-tanner-css-memory-x-rbposd-p001-v1",
  "input_type": "css",
  "noise_model": "circuit_depolarizing",
  "observable": "logical_x",
  "p_list": [
    0.001
  ],
  "result_metrics": [
    "logical_error_rate"
  ],
  "rounds_policy": {
    "kind": "fixed",
    "rounds": 3
  },
  "title": "Quantum Tanner CSS Memory X at p=0.001 via RBP-OSD OSD10"
}
```

- [ ] **Step 4: Add the benchmark suite JSON**

Create `benchmarks/suites/quantum-tanner-rbposd-p001-v1.json`:

```json
{
  "decoder_ids": [
    "rbposd-osd10-v1"
  ],
  "id": "quantum-tanner-rbposd-p001-v1",
  "shared_settings": {
    "runner": "rsinter"
  },
  "task_ids": [
    "quantum-tanner-css-memory-x-rbposd-p001-v1"
  ],
  "title": "Quantum Tanner RBP-OSD p=0.001 v1"
}
```

- [ ] **Step 5: Run the focused test to verify GREEN**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_benchmark_contracts.py
```

Expected: PASS with `4 passed`.

---

### Task 2: Workspace Inventory Expectations

**Files:**
- Modify: `tests/test_search_load.py`

**Interfaces:**
- Consumes: new benchmark task and suite ids from Task 1.
- Produces: updated workspace inventory test that matches the new committed benchmark records.

- [ ] **Step 1: Run the existing workspace-load test to verify RED**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_load.py::test_load_search_workspace_collects_campaigns_and_contracts
```

Expected: FAIL because the expected task and suite id lists do not include the new quantum Tanner records.

- [ ] **Step 2: Update expected task ids**

In `tests/test_search_load.py`, update the sorted task list assertion to:

```python
    assert sorted(workspace.tasks) == [
        "bb-css-memory-x-cdep-v1",
        "quantum-tanner-css-memory-x-rbposd-p001-v1",
        "rotated-memory-x-cdep-v1",
        M1_TASK_ID,
    ]
```

- [ ] **Step 3: Update expected suite ids**

In `tests/test_search_load.py`, update the sorted suite list assertion to:

```python
    assert sorted(workspace.suites) == [
        "bb72-qldpc-campaign-v1",
        "decoder-registry-css-bb-smoke-v1",
        "quantum-tanner-rbposd-p001-v1",
        "rotated-surface-baseline-v1",
        "rotated-surface-css-fixture-v1",
    ]
```

- [ ] **Step 4: Run the workspace-load test to verify GREEN**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_load.py::test_load_search_workspace_collects_campaigns_and_contracts
```

Expected: PASS with `1 passed`.

---

### Task 3: Required Verification And Commit

**Files:**
- No further edits expected.

**Interfaces:**
- Consumes: all Task 1 and Task 2 files.
- Produces: verified branch commit ready for PR.

- [ ] **Step 1: Run focused issue verification**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_benchmark_contracts.py
```

Expected: `4 passed`.

- [ ] **Step 2: Run workspace validation**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: exit 0 and output containing `validated search workspace`.

- [ ] **Step 3: Run full Python suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: all selected tests pass.

- [ ] **Step 4: Review git diff**

Run:

```bash
git diff --check
git status --short
git diff --stat HEAD
```

Expected: no whitespace errors; changed files are only the Superpowers plan/spec, the benchmark task/suite JSON files, and tests.

- [ ] **Step 5: Commit implementation**

Run:

```bash
git add benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json benchmarks/suites/quantum-tanner-rbposd-p001-v1.json tests/test_search_quantum_tanner_benchmark_contracts.py tests/test_search_load.py docs/superpowers/plans/2026-07-07-issue-40-quantum-tanner-rbposd-p001.md
git commit -m "feat: add quantum Tanner rbposd p001 benchmark"
```

Expected: commit succeeds.

---

## Plan Self-Review

- Spec coverage: task, suite, p pin, decoder pin, CSS compatibility, optional observables, bad p=0.01 rejection, validation, and full pytest are each covered.
- Placeholder scan: no placeholder steps are present.
- Type consistency: task id, suite id, and decoder id are identical across files and tests.
