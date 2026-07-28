# Random Window Upper Bound Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `random-window-upper-bound` as a first-class search distance method that records an upper bound without claiming exact distance.

**Architecture:** Keep distance method validation and payload loading centralized in `src/autoqec_search/distance_methods.py`. Reuse existing eval artifact, report, run metadata, and promotion paths so upper-bound status flows through artifacts while promotion remains exact-only.

**Tech Stack:** Python 3, pytest, existing `autoqec_search` CLI/report/promote modules.

## Global Constraints

- Canonical method name: `random-window-upper-bound`.
- Upper-bound payloads must use `bound_type: "upper"` and a positive `upper_bound`.
- Upper-bound payloads must not imply an exact distance unless an exact method was used.
- `env.json` and run metadata must record the selected method and upper-bound status.
- Promotion must continue to reject upper-bound payloads.
- `randomized-upper-bound` payload compatibility must preserve `bound_type: "upper"`.
- Unknown upper-bound method names such as `some-upper-bound` must be rejected.
- For fixed-round CSS tasks, `distance` may be absent when `upper_bound` is present.

---

## File Structure

- Modify `src/autoqec_search/distance_methods.py`: register the canonical upper-bound method, generate upper-bound payloads, and validate supported upper-bound payload names.
- Modify `src/autoqec_search/run_loop.py`, `src/autoqec_search/run_render.py`, `src/autoqec_search/eval_run.py`, and `src/autoqec_search/rsinter.py` as needed for review-driven bound-aware run finalization, human report labels, and exact-distance-required errors.
- Create `tests/test_search_upper_bound_distance_method.py`: cover the six issue acceptance behaviors in one focused test module.
- `src/autoqec_search/promote.py` remains exact-only; automatic `run` finalization skips promotion for non-exact distance methods instead of changing explicit promotion acceptance.

### Task 1: Failing Acceptance Tests

**Files:**
- Create: `tests/test_search_upper_bound_distance_method.py`

**Interfaces:**
- Consumes: `normalize_distance_method_options`, `distance_method_metadata`, `compute_distance_payload`, `load_distance_payload_from_dict`, `evaluate_resolved_candidate_into_run`, `build_report_model`, and `evaluate_promotions`.
- Produces: Six failing tests that describe the new upper-bound method behavior.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path

import pytest

from autoqec_search.distance_methods import (
    compute_distance_payload,
    distance_method_metadata,
    load_distance_payload_from_dict,
    normalize_distance_method_options,
)
from autoqec_search.eval_candidates import CandidateInput, ResolvedCandidate
from autoqec_search.eval_run import evaluate_resolved_candidate_into_run
from autoqec_search.load import SearchIntegrityError, SearchWorkspace
from autoqec_search.promote import evaluate_promotions
from autoqec_search.report import build_report_model
from autoqec_search.run_loop import build_env


REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD = "random-window-upper-bound"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
```

Add helpers for a copied candidate, a CSS task, a fake workspace, CSV/TSV writing, a report fixture, and a promotion fixture. The tests should assert the exact expected payloads and error messages from the issue.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest -q tests/test_search_upper_bound_distance_method.py`

Expected: FAIL, with failures showing `unknown distance method: random-window-upper-bound` or unsupported `random-window-upper-bound` upper-bound payload.

### Task 2: Register and Generate Upper-Bound Payloads

**Files:**
- Modify: `src/autoqec_search/distance_methods.py`
- Test: `tests/test_search_upper_bound_distance_method.py`

**Interfaces:**
- Consumes: existing `DistanceMethodOptions`, `_recorded_instance_distance`, and `_source_instance_id`.
- Produces: `RANDOM_WINDOW_UPPER_BOUND`, upper-bound method metadata, `random_window_upper_bound_payload`, and loader support for the canonical method.

- [ ] **Step 1: Add the upper-bound method constant and supported method sets**

```python
RANDOM_WINDOW_UPPER_BOUND = "random-window-upper-bound"
EXACT_DISTANCE_METHODS = {COPIED_ZOO_EXACT, RSTIM_ILP_EXACT}
UPPER_BOUND_DISTANCE_METHODS = {RANDOM_WINDOW_UPPER_BOUND}
UPPER_BOUND_PAYLOAD_METHODS = UPPER_BOUND_DISTANCE_METHODS | {RANDOMIZED_UPPER_BOUND}
```

- [ ] **Step 2: Accept only supported methods during normalization**

```python
if selected_method not in EXACT_DISTANCE_METHODS | UPPER_BOUND_DISTANCE_METHODS:
    raise SearchIntegrityError(f"unknown distance method: {selected_method}")
```

- [ ] **Step 3: Record the correct method metadata bound type**

```python
bound_type = (
    UPPER_BOUND
    if options.method in UPPER_BOUND_DISTANCE_METHODS
    else EXACT_BOUND
)
return {
    "method": options.method,
    "bound_type": bound_type,
    "qec_code_bin": options.qec_code_bin,
}
```

- [ ] **Step 4: Add payload generation**

```python
def random_window_upper_bound_payload(
    candidate,
    options: DistanceMethodOptions,
) -> dict[str, Any]:
    source_instance_id = _source_instance_id(candidate)
    source_instance_path = str(candidate.artifact_root)
    upper_bound = _recorded_instance_distance(candidate)
    return {
        "status": "completed",
        "upper_bound": upper_bound,
        "method": RANDOM_WINDOW_UPPER_BOUND,
        "bound_type": UPPER_BOUND,
        "options": {"method": RANDOM_WINDOW_UPPER_BOUND},
        "provenance": {
            "source": "zoo-instance",
            "source_instance_id": source_instance_id,
            "source_instance_path": source_instance_path,
        },
        "source_instance_id": source_instance_id,
        "source_instance_path": source_instance_path,
    }
```

- [ ] **Step 5: Dispatch from `compute_distance_payload`**

```python
if options.method == RANDOM_WINDOW_UPPER_BOUND:
    return random_window_upper_bound_payload(candidate, options)
```

- [ ] **Step 6: Allow only supported upper-bound payload names**

```python
if bound_type == UPPER_BOUND:
    if method not in UPPER_BOUND_PAYLOAD_METHODS:
        raise SearchIntegrityError(
            f"unsupported upper-bound distance payload in {label}"
        )
    return UPPER_BOUND
```

- [ ] **Step 7: Run focused tests**

Run: `PYTHONPATH=src pytest -q tests/test_search_upper_bound_distance_method.py`

Expected: `6 passed`.

### Task 3: Regression Verification and Commit

**Files:**
- Modify: all changed files from Tasks 1 and 2

**Interfaces:**
- Consumes: focused issue tests and full repository pytest suite.
- Produces: committed branch ready for PR.

- [ ] **Step 1: Run issue verification**

Run: `PYTHONPATH=src pytest -q tests/test_search_upper_bound_distance_method.py`

Expected: `6 passed`.

- [ ] **Step 2: Run required repository verification**

Run: `PYTHONPATH=src python3 -m pytest`

Expected: all tests pass.

- [ ] **Step 3: Review git diff**

Run: `git diff -- src/autoqec_search/distance_methods.py tests/test_search_upper_bound_distance_method.py`

Expected: diff is scoped to method registration, payload generation, and tests.

- [ ] **Step 4: Commit implementation**

```bash
git add src/autoqec_search/distance_methods.py tests/test_search_upper_bound_distance_method.py docs/superpowers/plans/2026-07-06-random-window-upper-bound.md
git commit -m "feat: add random-window upper-bound distance method"
```
