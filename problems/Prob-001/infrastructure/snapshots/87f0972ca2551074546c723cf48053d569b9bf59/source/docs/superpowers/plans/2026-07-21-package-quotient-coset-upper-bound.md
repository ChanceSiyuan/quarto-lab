# Package Quotient-Coset Upper-Bound Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package proposal 002 as a reusable, experimental CSS upper-bound witness finder, then publish the autoresearch branch as a draft PR and file a paper-validation issue.

**Architecture:** Add a pure-Python `autoqec_search.quotient_coset_upper_bound` module beside the existing external `qec-code` upper-bound wrapper. The module searches verified X/Z CSS logical witnesses in-process and returns AutoQEC's canonical `css-upper-bound-witness` distance payload after independent verification. The CLI writes only verified artifacts and keeps provenance in a distinct sidecar.

**Tech Stack:** Python 3.11, standard library only for the finder, existing `SearchIntegrityError`, existing `structure.matrix_data`, existing `structure.verify_css_upper_bound_witness`, pytest, GitHub CLI.

## Global Constraints

- The method name is exactly `quotient-coset-upper-bound`.
- The method is experimental and must not be registered in `autoqec_search.distance_methods`.
- The method returns `bound_type: "upper"` and must never claim an exact distance.
- The implementation must not depend on `codedistance`.
- Timeout options must be positive and at most 300 seconds.
- Failure to find a verified witness raises `SearchIntegrityError`.
- CLI failures must leave no witness or provenance artifact behind.
- Proposal 002 branch and `LOG.md` remain immutable provenance.
- Private holdout case-level data must not appear in package docs, PR body, or issue body.

---

## File Structure

- Create `src/autoqec_search/quotient_coset_upper_bound.py`: in-process randomized quotient-coset witness finder, option validation, provenance/result assembly.
- Modify `src/autoqec_search/cli.py`: import the finder, add `find-quotient-coset-upper-bound`, validate distinct output paths, write verified witness plus provenance sidecar atomically.
- Create `tests/test_search_quotient_coset_upper_bound.py`: unit, API, and CLI tests for the packaged finder.
- Modify `campaigns/examples/css-distance-autoresearch/README.md`: document the packaged command as the practical proposal 002 reproduction path.
- Modify `campaigns/examples/css-distance-autoresearch/results.md`: record proposal 002 as packaged but still experimental.
- Modify `LOG.md`: add a short branch-level entry for packaging proposal 002.

## Task 1: Finder Units and Python API

**Files:**
- Create: `src/autoqec_search/quotient_coset_upper_bound.py`
- Create: `tests/test_search_quotient_coset_upper_bound.py`

**Interfaces:**
- Consumes: `matrix_data(payload, label) -> list[list[int]]`, `_matrix_num_cols(payload, rows, label) -> int`, `verify_css_upper_bound_witness(hx_payload, hz_payload, witness_payload) -> dict`
- Produces: `find_quotient_coset_upper_bound(hx_payload: dict, hz_payload: dict, *, basis: str = "both", seed: int = 0, max_no_improvement: int = 2500, timeout_seconds: float = 300.0) -> dict[str, Any]`
- Produces helpers used by tests: `_rows_to_ints`, `_vector_to_list`, `_kernel_basis`, `_RowSpace`, `_build_logical_reps`, `_greedy_reduce`

- [ ] **Step 1: Write failing GF(2) and deterministic API tests**

Add these imports and fixture helpers to `tests/test_search_quotient_coset_upper_bound.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quotient_coset_upper_bound import (
    METHOD,
    _RowSpace,
    _build_logical_reps,
    _greedy_reduce,
    _kernel_basis,
    _rows_to_ints,
    _vector_to_list,
    find_quotient_coset_upper_bound,
)
from autoqec_search.structure import verify_css_upper_bound_witness


HX_4 = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[1, 1, 0, 0]],
}
HZ_4 = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[0, 0, 1, 1]],
}
REPO_ROOT = Path(__file__).resolve().parents[1]
D5_INSTANCE = (
    REPO_ROOT
    / "benchmarks"
    / "distance_ladders"
    / "surface-toric-bb-kasai-tanner-v2"
    / "instances"
    / "surface-rotated-d5"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text())
```

Add tests:

```python
def test_rows_to_ints_and_vector_round_trip() -> None:
    rows = _rows_to_ints([[1, 0, 1], [0, 1, 1]], num_cols=3, label="fixture")
    assert rows == [0b101, 0b110]
    assert _vector_to_list(0b101, 3) == [1, 0, 1]


def test_kernel_basis_vectors_have_zero_syndrome() -> None:
    rows = _rows_to_ints([[1, 1, 0], [0, 1, 1]], num_cols=3, label="check")
    kernel = _kernel_basis(rows, 3)
    assert kernel == [0b111]
    assert all((row & kernel[0]).bit_count() % 2 == 0 for row in rows)


def test_row_space_reduction_and_quotient_reps() -> None:
    span = _RowSpace([0b0011])
    assert span.contains(0b0011)
    assert not span.contains(0b1100)
    reps = _build_logical_reps([0b0011, 0b1100], [0b0011], seed=7)
    assert reps == [0b1100]


def test_greedy_reduce_lowers_coset_weight() -> None:
    reduced = _greedy_reduce(0b1111, [0b0011], seed=5, deadline_seconds=1.0, passes=3)
    assert reduced == 0b1100


def test_find_quotient_coset_upper_bound_is_deterministic_and_verified() -> None:
    first = find_quotient_coset_upper_bound(
        HX_4,
        HZ_4,
        basis="both",
        seed=19,
        max_no_improvement=64,
        timeout_seconds=5,
    )
    second = find_quotient_coset_upper_bound(
        HX_4,
        HZ_4,
        basis="both",
        seed=19,
        max_no_improvement=64,
        timeout_seconds=5,
    )
    assert {
        key: value
        for key, value in first.items()
        if key != "provenance"
    } == {
        key: value
        for key, value in second.items()
        if key != "provenance"
    }
    assert first["provenance"]["seed"] == second["provenance"]["seed"] == 19
    assert first["provenance"]["basis_requested"] == second["provenance"]["basis_requested"] == "both"
    assert first["provenance"]["max_no_improvement"] == second["provenance"]["max_no_improvement"] == 64
    assert first["status"] == "completed"
    assert first["method"] == METHOD
    assert first["bound_type"] == "upper"
    assert first["upper_bound"] == 1
    assert first["distance_payload"] == {
        "status": "completed",
        "method": "css-upper-bound-witness",
        "bound_type": "upper",
        "upper_bound": 1,
        "basis": first["basis"],
    }
    assert first["verification"]["status"] == "pass"
    assert verify_css_upper_bound_witness(HX_4, HZ_4, first["witness_payload"])["status"] == "pass"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=src pytest tests/test_search_quotient_coset_upper_bound.py -q
```

Expected: FAIL during import because `autoqec_search.quotient_coset_upper_bound` does not exist.

- [ ] **Step 3: Implement minimal finder API**

Create `src/autoqec_search/quotient_coset_upper_bound.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import random
import time
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.structure import (
    _matrix_num_cols,
    matrix_data,
    verify_css_upper_bound_witness,
)


METHOD = "quotient-coset-upper-bound"
BOUND_TYPE = "upper"
MAX_TIMEOUT_SECONDS = 300.0
DEFAULT_MAX_NO_IMPROVEMENT = 2500


def _is_plain_int(value: object) -> bool:
    return type(value) is int


def _require_basis(value: object) -> str:
    if value not in {"x", "z", "both"}:
        raise SearchIntegrityError("basis must be one of: x, z, both")
    return str(value)


def _require_seed(value: object) -> int:
    if not _is_plain_int(value) or value < 0:
        raise SearchIntegrityError("seed must be a nonnegative integer")
    return int(value)


def _require_positive_int(value: object, label: str) -> int:
    if not _is_plain_int(value) or value <= 0:
        raise SearchIntegrityError(f"{label} must be a positive integer")
    return int(value)


def _require_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise SearchIntegrityError("timeout_seconds must be a positive number no greater than 300")
    timeout = float(value)
    if timeout <= 0 or timeout > MAX_TIMEOUT_SECONDS:
        raise SearchIntegrityError("timeout_seconds must be a positive number no greater than 300")
    return timeout
```

Then implement the proposal 002 primitives as pure functions: `_rows_to_ints`, `_vector_to_list`, `_syndrome_zero`, `_RowSpace`, `_kernel_basis`, `_random_combo`, `_build_logical_reps`, `_greedy_reduce`, `_search_basis`, and `find_quotient_coset_upper_bound`. Use a monotonic deadline, search X as `check_rows=hz_rows, stabilizer_rows=hx_rows`, search Z as `check_rows=hx_rows, stabilizer_rows=hz_rows`, select the lightest verified witness, and return:

```python
{
    "status": "completed",
    "method": METHOD,
    "bound_type": BOUND_TYPE,
    "basis": found_basis,
    "vector": found_vector,
    "upper_bound": found_weight,
    "witness_payload": {"basis": found_basis, "vector": found_vector},
    "distance_payload": verification["distance_payload"],
    "verification": verification,
    "provenance": {
        "method": METHOD,
        "seed": seed,
        "basis_requested": requested_basis,
        "max_no_improvement": max_no_improvement,
        "timeout_seconds": timeout_seconds,
        "attempts": total_attempts,
        "elapsed_seconds": elapsed_seconds,
        "basis_results": basis_results,
    },
}
```

Raise `SearchIntegrityError("no quotient-coset upper-bound witness found")` when no requested basis returns a verified witness. Raise `SearchIntegrityError(f"invalid_css_upper_bound_witness: {reason}")` when independent verification fails.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=src pytest tests/test_search_quotient_coset_upper_bound.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/autoqec_search/quotient_coset_upper_bound.py tests/test_search_quotient_coset_upper_bound.py
git commit -m "feat: add quotient coset upper-bound finder"
```

## Task 2: Validation, Basis Selection, and Public Fixtures

**Files:**
- Modify: `tests/test_search_quotient_coset_upper_bound.py`
- Modify: `src/autoqec_search/quotient_coset_upper_bound.py`

**Interfaces:**
- Consumes: `find_quotient_coset_upper_bound(...)`
- Produces: robust validation errors for malformed matrices, invalid options, no witness, and verifier rejection.

- [ ] **Step 1: Write failing validation and fixture tests**

Append:

```python
def test_basis_x_and_z_requests_return_requested_basis() -> None:
    x_result = find_quotient_coset_upper_bound(HX_4, HZ_4, basis="x", seed=1, max_no_improvement=32, timeout_seconds=5)
    z_result = find_quotient_coset_upper_bound(HX_4, HZ_4, basis="z", seed=1, max_no_improvement=32, timeout_seconds=5)
    assert x_result["basis"] == "x"
    assert z_result["basis"] == "z"


def test_public_rotated_surface_d5_fixture_finds_weight_five_upper_bound() -> None:
    result = find_quotient_coset_upper_bound(
        _load(D5_INSTANCE / "hx.json"),
        _load(D5_INSTANCE / "hz.json"),
        basis="both",
        seed=2026,
        max_no_improvement=128,
        timeout_seconds=10,
    )
    assert result["upper_bound"] == 5
    assert result["distance_payload"]["upper_bound"] == 5
    assert result["verification"]["status"] == "pass"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"basis": "y"}, "basis"),
        ({"seed": -1}, "seed"),
        ({"seed": True}, "seed"),
        ({"max_no_improvement": 0}, "max_no_improvement"),
        ({"timeout_seconds": 0}, "timeout_seconds"),
        ({"timeout_seconds": 300.1}, "timeout_seconds"),
    ],
)
def test_rejects_invalid_options(kwargs: dict, message: str) -> None:
    options = {"basis": "both", "seed": 0, "max_no_improvement": 32, "timeout_seconds": 5}
    options.update(kwargs)
    with pytest.raises(SearchIntegrityError, match=message):
        find_quotient_coset_upper_bound(HX_4, HZ_4, **options)


def test_rejects_width_mismatch() -> None:
    bad_hz = {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 3, "data": [[1, 0, 1]]}
    with pytest.raises(SearchIntegrityError, match="column mismatch"):
        find_quotient_coset_upper_bound(HX_4, bad_hz, timeout_seconds=5)


def test_rejects_ragged_and_nonbinary_matrices() -> None:
    ragged = {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 4, "data": [[1, 0, 1]]}
    nonbinary = {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 4, "data": [[1, 0, 2, 0]]}
    with pytest.raises(SearchIntegrityError, match="matrix column mismatch"):
        find_quotient_coset_upper_bound(ragged, HZ_4, timeout_seconds=5)
    with pytest.raises(SearchIntegrityError, match="non-binary"):
        find_quotient_coset_upper_bound(nonbinary, HZ_4, timeout_seconds=5)


def test_rejects_css_code_with_no_logical_witness() -> None:
    hx = {"format": "dense_binary_matrix", "n_rows": 2, "n_cols": 2, "data": [[1, 0], [0, 1]]}
    hz = {"format": "dense_binary_matrix", "n_rows": 0, "n_cols": 2, "data": []}
    with pytest.raises(SearchIntegrityError, match="no quotient-coset upper-bound witness found"):
        find_quotient_coset_upper_bound(hx, hz, basis="x", seed=0, max_no_improvement=8, timeout_seconds=5)
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=src pytest tests/test_search_quotient_coset_upper_bound.py -q
```

Expected: at least one validation or d5 fixture test fails until the API is hardened.

- [ ] **Step 3: Harden implementation**

Adjust `find_quotient_coset_upper_bound` so it:

```python
requested_basis = _require_basis(basis)
seed = _require_seed(seed)
max_no_improvement = _require_positive_int(max_no_improvement, "max_no_improvement")
timeout_seconds = _require_timeout(timeout_seconds)
hx_rows_dense = matrix_data(hx_payload, "hx.json")
hz_rows_dense = matrix_data(hz_payload, "hz.json")
n_cols = _matrix_num_cols(hx_payload, hx_rows_dense, "hx.json")
if n_cols != _matrix_num_cols(hz_payload, hz_rows_dense, "hz.json"):
    raise SearchIntegrityError("matrix column mismatch: hx.json vs hz.json")
```

Keep `_search_basis` deterministic by deriving per-basis RNG seeds from the user seed. Add a small deterministic seed phase over low-weight quotient reps before the randomized loop, then respect `max_no_improvement` for each requested basis.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=src pytest tests/test_search_quotient_coset_upper_bound.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add src/autoqec_search/quotient_coset_upper_bound.py tests/test_search_quotient_coset_upper_bound.py
git commit -m "test: cover quotient coset finder validation"
```

## Task 3: CLI Command and Artifact Contract

**Files:**
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_quotient_coset_upper_bound.py`

**Interfaces:**
- Consumes: `find_quotient_coset_upper_bound(...)`
- Produces: `autoqec-search find-quotient-coset-upper-bound --hx <hx.json> --hz <hz.json> --basis {x,z,both} --out <witness.json> --seed <int> --max-no-improvement <int> --timeout-seconds <float> [--provenance-out <path>]`

- [ ] **Step 1: Write failing CLI tests**

Append:

```python
from autoqec_search.cli import main


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def test_cli_writes_witness_and_distinct_provenance_sidecar(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    hx_path = tmp_path / "hx.json"
    hz_path = tmp_path / "hz.json"
    out_path = tmp_path / "witness.json"
    _write_json(hx_path, HX_4)
    _write_json(hz_path, HZ_4)

    assert main([
        "find-quotient-coset-upper-bound",
        "--hx",
        str(hx_path),
        "--hz",
        str(hz_path),
        "--basis",
        "both",
        "--out",
        str(out_path),
        "--seed",
        "19",
        "--max-no-improvement",
        "64",
        "--timeout-seconds",
        "5",
    ]) == 0

    witness = json.loads(out_path.read_text())
    provenance = json.loads((tmp_path / "witness.json.provenance.json").read_text())
    assert witness["basis"] in {"x", "z"}
    assert witness["vector"]
    assert provenance["method"] == METHOD
    assert provenance["basis_requested"] == "both"
    assert provenance["distance_payload"]["bound_type"] == "upper"
    assert "found quotient-coset upper-bound witness" in capsys.readouterr().out


def test_cli_rejects_same_witness_and_provenance_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    hx_path = tmp_path / "hx.json"
    hz_path = tmp_path / "hz.json"
    out_path = tmp_path / "witness.json"
    _write_json(hx_path, HX_4)
    _write_json(hz_path, HZ_4)

    assert main([
        "find-quotient-coset-upper-bound",
        "--hx",
        str(hx_path),
        "--hz",
        str(hz_path),
        "--basis",
        "both",
        "--out",
        str(out_path),
        "--provenance-out",
        str(out_path),
    ]) == 1
    assert not out_path.exists()
    assert "provenance output path must be distinct" in capsys.readouterr().err


def test_cli_leaves_no_artifacts_on_search_failure(tmp_path: Path) -> None:
    hx_path = tmp_path / "hx.json"
    hz_path = tmp_path / "hz.json"
    out_path = tmp_path / "witness.json"
    provenance_path = tmp_path / "provenance.json"
    _write_json(hx_path, {"format": "dense_binary_matrix", "n_rows": 2, "n_cols": 2, "data": [[1, 0], [0, 1]]})
    _write_json(hz_path, {"format": "dense_binary_matrix", "n_rows": 0, "n_cols": 2, "data": []})

    assert main([
        "find-quotient-coset-upper-bound",
        "--hx",
        str(hx_path),
        "--hz",
        str(hz_path),
        "--basis",
        "x",
        "--out",
        str(out_path),
        "--provenance-out",
        str(provenance_path),
        "--max-no-improvement",
        "8",
        "--timeout-seconds",
        "5",
    ]) == 1
    assert not out_path.exists()
    assert not provenance_path.exists()
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=src pytest tests/test_search_quotient_coset_upper_bound.py -q
```

Expected: FAIL because the CLI command is not registered.

- [ ] **Step 3: Implement CLI parser and handler**

In `src/autoqec_search/cli.py`, import:

```python
from autoqec_search.quotient_coset_upper_bound import (
    find_quotient_coset_upper_bound,
)
```

Add parser:

```python
    find_quotient_coset_parser = subparsers.add_parser(
        "find-quotient-coset-upper-bound",
        help="Find and write one CSS upper-bound witness using the in-process quotient-coset search",
    )
    find_quotient_coset_parser.add_argument("--hx", required=True)
    find_quotient_coset_parser.add_argument("--hz", required=True)
    find_quotient_coset_parser.add_argument("--basis", choices=["x", "z", "both"], default="both")
    find_quotient_coset_parser.add_argument("--out", required=True)
    find_quotient_coset_parser.add_argument("--seed", type=int, default=0)
    find_quotient_coset_parser.add_argument("--max-no-improvement", type=int, default=2500)
    find_quotient_coset_parser.add_argument("--timeout-seconds", type=float, default=300)
    find_quotient_coset_parser.add_argument("--provenance-out", default=None)
```

Add handler before `verify-witness`:

```python
        if args.command == "find-quotient-coset-upper-bound":
            hx_path = Path(args.hx)
            hz_path = Path(args.hz)
            out_path = Path(args.out)
            provenance_path = (
                Path(args.provenance_out)
                if args.provenance_out is not None
                else _default_provenance_path(out_path)
            )
            if provenance_path.resolve() == out_path.resolve():
                raise SearchIntegrityError(
                    "provenance output path must be distinct from witness output path"
                )
            hx_payload = _load_json_file(hx_path, label="hx")
            hz_payload = _load_json_file(hz_path, label="hz")
            result = find_quotient_coset_upper_bound(
                hx_payload,
                hz_payload,
                basis=args.basis,
                seed=args.seed,
                max_no_improvement=args.max_no_improvement,
                timeout_seconds=args.timeout_seconds,
            )
            provenance = dict(result["provenance"])
            provenance.update(
                {
                    "basis_found": result["basis"],
                    "distance_payload": result["distance_payload"],
                    "hx": str(hx_path),
                    "hz": str(hz_path),
                    "provenance_path": str(provenance_path),
                    "verification": result["verification"],
                    "witness_path": str(out_path),
                }
            )
            _atomic_write_witness_with_provenance(
                out_path,
                result["witness_payload"],
                provenance_path,
                provenance,
            )
            print(
                "found quotient-coset upper-bound witness: "
                f"basis={result['basis']} "
                f"weight={result['upper_bound']} "
                f"method={result['method']} "
                f"out={out_path}"
            )
            print(f"wrote provenance: {provenance_path}")
            return 0
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=src pytest tests/test_search_quotient_coset_upper_bound.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add src/autoqec_search/cli.py tests/test_search_quotient_coset_upper_bound.py
git commit -m "feat: expose quotient coset upper-bound cli"
```

## Task 4: Campaign Docs, Review, PR, and Paper Issue

**Files:**
- Modify: `campaigns/examples/css-distance-autoresearch/README.md`
- Modify: `campaigns/examples/css-distance-autoresearch/results.md`
- Modify: `LOG.md`

**Interfaces:**
- Consumes: packaged command from Task 3.
- Produces: draft PR body and paper-validation issue body that link issue #38 and avoid publication-ready claims.

- [ ] **Step 1: Write failing docs test**

Modify `tests/test_search_docs.py` to add:

```python
CSS_DISTANCE_AUTORESEARCH_DOC = (
    REPO_ROOT / "campaigns" / "examples" / "css-distance-autoresearch" / "README.md"
)


def test_css_distance_autoresearch_docs_describe_packaged_quotient_coset_finder() -> None:
    document = CSS_DISTANCE_AUTORESEARCH_DOC.read_text()
    assert "autoqec-search find-quotient-coset-upper-bound" in document
    assert "quotient-coset-upper-bound" in document
    assert "upper bound" in document.lower()
    assert "not an exact-distance method" in document
```

Run:

```bash
PYTHONPATH=src pytest tests/test_search_docs.py -q
```

Expected: FAIL until the docs reference the packaged command.

- [ ] **Step 2: Update docs and log**

Update the campaign README and results report to state:

```markdown
Practical recommendation: proposal 002 is now packaged as
`autoqec-search find-quotient-coset-upper-bound`. It is an experimental
randomized upper-bound witness finder, not an exact-distance method and not a
Zoo promotion source.
```

Add a `LOG.md` entry:

```markdown
## 2026-07-21

- Packaged proposal 002 as the experimental `quotient-coset-upper-bound`
  in-process CSS witness finder and prepared the draft PR/paper-validation
  handoff.
```

- [ ] **Step 3: Run focused docs and finder tests**

Run:

```bash
PYTHONPATH=src pytest tests/test_search_quotient_coset_upper_bound.py tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
git add campaigns/examples/css-distance-autoresearch/README.md campaigns/examples/css-distance-autoresearch/results.md LOG.md tests/test_search_docs.py
git commit -m "docs: package proposal 002 upper-bound handoff"
```

- [ ] **Step 5: Run full verification before publication**

Run:

```bash
PYTHONPATH=src pytest -q
git diff --check
```

Expected: pytest exits 0 and `git diff --check` exits 0.

- [ ] **Step 6: Request code review**

Use the requesting-code-review skill with base `origin/main` and current `HEAD`. Fix Critical and Important findings before publication.

- [ ] **Step 7: Push branch and open draft PR**

Run:

```bash
git push -u origin codex/css-distance-autoresearch
gh pr create --draft --base main --head codex/css-distance-autoresearch --title "Package CSS distance autoresearch proposal 002" --body-file /tmp/autoqec-css-distance-pr.md
```

PR body must mention issue #38 without closing it, all results are upper bounds, proposal 002 is experimental, private holdouts were blinded, and the external `codedistance` baseline has a metadata/licensing caveat.

- [ ] **Step 8: File paper-validation issue**

Run:

```bash
gh issue create --title "Validate quotient-coset CSS upper-bound finder for paper readiness" --body-file /tmp/autoqec-css-distance-paper-validation.md
```

Issue body must link #38 and the draft PR and include acceptance criteria for public benchmark manifest, at least 20 seeds, baseline comparisons, metrics and confidence intervals, ablations, scaling/Pareto plots, APM/Kasai track, committed artifacts, and novelty assessment.
