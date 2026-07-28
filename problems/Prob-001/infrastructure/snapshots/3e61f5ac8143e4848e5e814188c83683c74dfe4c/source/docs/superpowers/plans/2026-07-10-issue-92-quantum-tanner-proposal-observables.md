# Issue 92 Quantum Tanner Proposal Observables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a proposal-derived quantum Tanner observable completion command that writes valid `observables_x.json` artifacts and provenance for imported explicit candidates.

**Architecture:** Add one focused module that loads proposal-derived explicit candidates from a search space, verifies each candidate's X witness, reuses `complete_logical_observable_basis`, validates the completed rows, and writes the observable/provenance artifacts. Wire it through the existing CLI and search-space schema while keeping exact distance unknown.

**Tech Stack:** Python 3.14, `autoqec_search` CLI modules, JSON schema, pytest, existing GF(2) helpers in `src/autoqec_search/structure.py`.

## Global Constraints

- Command name: `complete-quantum-tanner-proposal-observables`.
- Input command supports `--root`, `--search-space`, `--basis x`, `--qec-code-bin`, and `--force`.
- Accepted candidates are proposal-derived explicit instances with `provenance.kind == "proposal-derived"` and an `instance_path`.
- Each accepted candidate must have `upper_bound_witness_path`; the command does not complete from upper-bound payloads because they do not contain the witness vector.
- Only basis `x` is supported for this issue.
- Reuse `complete_logical_observable_basis`; do not implement a second GF(2) quotient-basis algorithm.
- Completed rows must be in `ker(HZ)`, independent modulo `rowspan(HX)`, and exactly `k = n - rank(HX) - rank(HZ)`.
- `observables_x.json` shape must be `{"format": "sparse_rows", "num_cols": n, "rows": [...]}`.
- `instance.json.artifacts.observables_x` must equal `observables_x.json` after successful completion.
- Write deterministic sidecar `observables_x_provenance.json`.
- Upper-bound witnesses remain upper-bound evidence only; do not write exact distance fields.
- Incomplete existing observables must fail with `explicit X observables define 1 rows, expected k = 2`.

---

### Task 1: Proposal Observable Completion Command

**Files:**
- Create: `src/autoqec_search/quantum_tanner_proposal_observables.py`
- Create: `tests/test_search_quantum_tanner_proposal_observables.py`
- Modify: `src/autoqec_search/structure.py`
- Modify: `src/autoqec_search/cli.py`
- Modify: `benchmarks/schemas/search-space.schema.json`

**Interfaces:**
- Consumes: `resolve_campaign_candidate_spec(root, candidate_spec, campaign_id=...)`, `verify_css_upper_bound_witness(hx_payload, hz_payload, witness_payload)`, `complete_logical_observable_basis(kernel_rows=..., stabilizer_rows=..., preferred_vector=...)`, `gf2_rank`, `gf2_vector_in_kernel`, `gf2_vector_in_row_space`, and `SearchIntegrityError`.
- Produces:
  - `complete_quantum_tanner_proposal_observables(root: Path, search_space_path: Path, *, basis: str = "x", qec_code_bin: str | None = None, force: bool = False) -> ProposalObservablesCompletionSummary`
  - CLI command `complete-quantum-tanner-proposal-observables`
  - `matrix_data(...)` support for existing `sparse_rows` matrix artifacts in addition to `dense_binary_matrix`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_search_quantum_tanner_proposal_observables.py` with temporary-workspace helpers and the three issue-required tests:

```python
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from autoqec_search.eval_candidates import resolve_campaign_candidate_spec
from autoqec_search.structure import gf2_rank, gf2_vector_in_kernel, matrix_data


REPO_ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ID = "quantum-tanner-autoresearch"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _cli_env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}


def _proposal_payload(candidate_id: str) -> dict:
    return {
        "candidate_fingerprint": f"{candidate_id}-candidate-fingerprint",
        "exact_distance_status": "unknown",
        "materialization_manifest": f"proposal-instances/{candidate_id}/materialization_manifest.json",
        "materialization_run": {"qec_code": {"bin": "/unused/qec-code"}},
        "materializer_version": "test-materializer",
        "output_hashes": {
            "hx.json": f"{candidate_id}-hx",
            "hz.json": f"{candidate_id}-hz",
            "instance.json": f"{candidate_id}-instance",
            "qec_code_quantum_tanner_spec.json": f"{candidate_id}-spec",
        },
        "proposal_fingerprint": f"{candidate_id}-proposal-fingerprint",
        "proposal_id": candidate_id,
        "qec_code_spec_path": f"proposal-instances/{candidate_id}/qec_code_quantum_tanner_spec.json",
        "validator_fingerprint": f"{candidate_id}-validator-fingerprint",
    }


def _make_workspace(
    work_root: Path,
    *,
    candidate_id: str = "proposal-k2",
    witness_basis: str = "x",
    existing_observables: dict | None = None,
) -> tuple[Path, Path, Path]:
    campaign_root = work_root / "campaigns" / "examples" / CAMPAIGN_ID
    campaign_root.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copyfile(
        REPO_ROOT / "campaigns" / "examples" / CAMPAIGN_ID / "campaign.json",
        campaign_root / "campaign.json",
    )
    (work_root / "results" / "search").mkdir(parents=True)

    instance_dir = work_root / "proposal-instances" / candidate_id
    _write_json(
        instance_dir / "hx.json",
        {"format": "sparse_rows", "num_cols": 4, "rows": [[2]]},
    )
    _write_json(
        instance_dir / "hz.json",
        {"format": "sparse_rows", "num_cols": 4, "rows": [[3]]},
    )
    artifacts = {"hx": "hx.json", "hz": "hz.json"}
    if existing_observables is not None:
        artifacts["observables_x"] = "observables_x.json"
        _write_json(instance_dir / "observables_x.json", existing_observables)
    _write_json(
        instance_dir / "instance.json",
        {
            "artifacts": artifacts,
            "candidate_id": candidate_id,
            "code_id": "quantum-tanner-code",
            "derived_properties": {
                "distance": None,
                "kx": None,
                "kz": None,
                "mx": 1,
                "mz": 1,
                "n": 4,
            },
            "instance_id": candidate_id,
            "instance_kind": "finite_css_instance",
            "k": 2,
            "matrix_format": "sparse_rows_json",
            "n": 4,
            "parameters": {"distance": None},
            "proposal_id": candidate_id,
            "provenance": {"materializer": {"version": "test-materializer"}},
            "quantum_tanner_spec": "qec_code_quantum_tanner_spec.json",
        },
    )
    _write_json(instance_dir / "qec_code_quantum_tanner_spec.json", {"fixture_id": candidate_id})
    _write_json(
        instance_dir / "materialization_manifest.json",
        {
            "candidate_id": candidate_id,
            "exact_distance_status": "unknown",
            "materializer_version": "test-materializer",
            "output_hashes": _proposal_payload(candidate_id)["output_hashes"],
            "proposal_fingerprint": _proposal_payload(candidate_id)["proposal_fingerprint"],
            "proposal_id": candidate_id,
            "qec_code": {"bin": "/unused/qec-code"},
            "validator": {
                "fingerprint": _proposal_payload(candidate_id)["validator_fingerprint"],
                "version": "test-validator",
            },
        },
    )

    witness_path = campaign_root / "witnesses" / f"{candidate_id}-{witness_basis}-witness.json"
    _write_json(witness_path, {"basis": witness_basis, "vector": [1, 0, 0, 0]})
    search_space_path = campaign_root / "search_space.json"
    _write_json(
        search_space_path,
        {
            "campaign_id": CAMPAIGN_ID,
            "mode": "explicit_list",
            "candidate_specs": [
                {
                    "candidate_id": candidate_id,
                    "code_family": "quantum-tanner-code",
                    "instance_path": f"proposal-instances/{candidate_id}",
                    "upper_bound_witness_path": str(witness_path.relative_to(work_root)),
                    "provenance": {
                        "kind": "proposal-derived",
                        "label": candidate_id,
                        "proposal": _proposal_payload(candidate_id),
                    },
                }
            ],
        },
    )
    return work_root, search_space_path, instance_dir


def _run_complete(work_root: Path, search_space_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "complete-quantum-tanner-proposal-observables",
            "--root",
            str(work_root),
            "--search-space",
            str(search_space_path),
            "--basis",
            "x",
            "--qec-code-bin",
            "/unused/qec-code",
            "--force",
        ],
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=REPO_ROOT,
    )


def _run_complete_without_force(
    work_root: Path,
    search_space_path: Path,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        "-m",
        "autoqec_search.cli",
        "complete-quantum-tanner-proposal-observables",
        "--root",
        str(work_root),
        "--search-space",
        str(search_space_path),
        "--basis",
        "x",
    ]
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=REPO_ROOT,
    )


def _run_validate(work_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate",
            "--root",
            str(work_root),
        ],
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=REPO_ROOT,
    )


def _sparse_rows_to_dense_rows(payload: dict) -> list[list[int]]:
    rows = []
    for sparse_row in payload["rows"]:
        dense_row = [0] * payload["num_cols"]
        for column in sparse_row:
            dense_row[column] = 1
        rows.append(dense_row)
    return rows


def _assert_valid_x_observables(instance_dir: Path, expected_rows: int) -> None:
    hx = matrix_data(_load_json(instance_dir / "hx.json"), "hx.json")
    hz = matrix_data(_load_json(instance_dir / "hz.json"), "hz.json")
    observables = _load_json(instance_dir / "observables_x.json")
    assert observables["format"] == "sparse_rows"
    assert observables["num_cols"] == 4
    assert len(observables["rows"]) == expected_rows
    dense_rows = _sparse_rows_to_dense_rows(observables)
    for row in dense_rows:
        assert gf2_vector_in_kernel(hz, row)
    assert gf2_rank([*hx, *dense_rows]) == gf2_rank(hx) + expected_rows


def test_complete_proposal_observables_writes_exactly_k_valid_x_rows(
    tmp_path: Path,
) -> None:
    work_root, search_space_path, instance_dir = _make_workspace(tmp_path / "workspace")

    result = _run_complete(work_root, search_space_path)

    assert result.returncode == 0, result.stderr
    assert "completed=1" in result.stdout
    _assert_valid_x_observables(instance_dir, expected_rows=2)
    instance = _load_json(instance_dir / "instance.json")
    assert instance["artifacts"]["observables_x"] == "observables_x.json"
    provenance = _load_json(instance_dir / "observables_x_provenance.json")
    assert provenance["method"] == "complete_logical_observable_basis"
    assert provenance["basis"] == "x"
    assert provenance["input_witness"]["path"].endswith("proposal-k2-x-witness.json")

    validated = _run_validate(work_root)
    assert validated.returncode == 0, validated.stderr

    search_space = _load_json(search_space_path)
    candidate = resolve_campaign_candidate_spec(
        work_root,
        search_space["candidate_specs"][0],
        campaign_id=CAMPAIGN_ID,
    )
    assert candidate.observables_x == _load_json(instance_dir / "observables_x.json")


def test_complete_proposal_observables_rejects_incomplete_x_rows(
    tmp_path: Path,
) -> None:
    incomplete = {"format": "sparse_rows", "num_cols": 4, "rows": [[0]]}
    work_root, search_space_path, _instance_dir = _make_workspace(
        tmp_path / "workspace",
        existing_observables=incomplete,
    )

    result = _run_complete_without_force(work_root, search_space_path)

    assert result.returncode != 0
    assert "explicit X observables define 1 rows, expected k = 2" in result.stderr


def test_complete_proposal_observables_rejects_z_like_witness_for_memory_x(
    tmp_path: Path,
) -> None:
    work_root, search_space_path, instance_dir = _make_workspace(
        tmp_path / "workspace",
        witness_basis="z",
    )

    result = _run_complete(work_root, search_space_path)

    assert result.returncode != 0
    assert "incompatible" in result.stderr
    assert not (instance_dir / "observables_x.json").exists()
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_observables.py::test_complete_proposal_observables_writes_exactly_k_valid_x_rows \
  tests/test_search_quantum_tanner_proposal_observables.py::test_complete_proposal_observables_rejects_incomplete_x_rows \
  tests/test_search_quantum_tanner_proposal_observables.py::test_complete_proposal_observables_rejects_z_like_witness_for_memory_x \
  -q
```

Expected: FAIL because the test file or CLI command is not implemented yet.

- [ ] **Step 3: Extend matrix parsing for sparse-row CSS artifacts**

Modify `src/autoqec_search/structure.py` so `matrix_data` accepts both current
`dense_binary_matrix` payloads and existing `sparse_rows` proposal artifacts.
Keep the dense validation behavior unchanged. For `sparse_rows`, require
`num_cols` as a positive integer, `rows` as a list, each row as strictly
increasing integer column indices in range, and return dense binary rows.

Use this implementation shape:

```python
def _sparse_rows_matrix_data(payload: dict, label: str) -> DenseMatrix:
    if payload.get("format") != "sparse_rows":
        raise SearchIntegrityError(f"unsupported matrix format: {label}")
    num_cols = payload.get("num_cols")
    if not _is_plain_int(num_cols) or num_cols <= 0:
        raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, list):
        raise SearchIntegrityError(f"invalid matrix data: {label}")
    rows: DenseMatrix = []
    for row_index, sparse_row in enumerate(rows_payload):
        if not isinstance(sparse_row, list):
            raise SearchIntegrityError(f"invalid matrix row: {label}")
        dense_row = [0] * int(num_cols)
        previous = -1
        for column in sparse_row:
            if not _is_plain_int(column):
                raise SearchIntegrityError(f"matrix contains non-binary entries: {label}")
            if column < 0 or column >= num_cols:
                raise SearchIntegrityError(f"matrix column mismatch: {label}")
            if column <= previous:
                raise SearchIntegrityError(f"matrix row {row_index} columns must be strictly increasing: {label}")
            dense_row[int(column)] = 1
            previous = int(column)
        rows.append(dense_row)
    return rows
```

Then route `matrix_data` by `payload["format"]`.

- [ ] **Step 4: Add the completion module**

Create `src/autoqec_search/quantum_tanner_proposal_observables.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from autoqec_search.eval_candidates import ResolvedCandidate, resolve_campaign_candidate_spec
from autoqec_search.load import SearchIntegrityError
from autoqec_search.structure import (
    complete_logical_observable_basis,
    gf2_rank,
    gf2_vector_in_kernel,
    matrix_data,
    verify_css_upper_bound_witness,
)


OBSERVABLES_X_FILENAME = "observables_x.json"
OBSERVABLES_X_PROVENANCE_FILENAME = "observables_x_provenance.json"
PROPOSAL_OBSERVABLE_COMPLETION_VERSION = "quantum-tanner-proposal-observables-v1"


@dataclass(frozen=True)
class CompletedProposalObservables:
    candidate_id: str
    instance_dir: Path
    observables_path: Path
    provenance_path: Path
    row_count: int


@dataclass(frozen=True)
class ProposalObservablesCompletionSummary:
    completed: int
    skipped: int
    search_space_path: Path
    completions: tuple[CompletedProposalObservables, ...]
```

Implement helpers with these exact contracts:

```python
def complete_quantum_tanner_proposal_observables(
    root: Path,
    search_space_path: Path,
    *,
    basis: str = "x",
    qec_code_bin: str | None = None,
    force: bool = False,
) -> ProposalObservablesCompletionSummary:
    ...
```

```python
def _validate_x_observables_payload(
    *,
    candidate_id: str,
    hx_rows: list[list[int]],
    hz_rows: list[list[int]],
    observables_x: dict[str, Any],
) -> list[list[int]]:
    ...
```

`_validate_x_observables_payload` must compute `expected_k =
num_cols - gf2_rank(hx_rows) - gf2_rank(hz_rows)`, check the sparse payload
shape, convert rows to dense rows, raise
`SearchIntegrityError(f"explicit X observables define {row_count} rows, expected k = {expected_k}")`
for row-count mismatch, verify every row with `gf2_vector_in_kernel(hz_rows,
row)`, and verify `gf2_rank([*hx_rows, *dense_rows]) == gf2_rank(hx_rows) +
expected_k`.

The public function must:

1. Resolve `search_space_path` under `root`.
2. Validate the search space with `benchmarks/schemas/search-space.schema.json`.
3. Select proposal-derived explicit candidates.
4. Build all completion plans before writing any file.
5. Validate existing `candidate.observables_x` first when present, so incomplete
   existing data fails with the existing row-count text before overwrite logic.
6. Require `upper_bound_witness_path` and load it safely under `root`.
7. Verify the witness with `verify_css_upper_bound_witness`.
8. Reject verified witnesses whose basis is not the requested basis with an
   error containing `incompatible`.
9. Complete rows with `complete_logical_observable_basis(kernel_rows=hz_rows,
   stabilizer_rows=hx_rows, preferred_vector=witness["vector"])`.
10. Write `observables_x.json`, updated `instance.json`, and
    `observables_x_provenance.json` atomically.

- [ ] **Step 5: Wire schema and CLI**

Modify `benchmarks/schemas/search-space.schema.json` under
`explicitInstanceCandidate.properties` to add:

```json
"upper_bound_witness_path": { "type": "string", "minLength": 1 },
```

Modify `src/autoqec_search/cli.py` imports:

```python
from autoqec_search.quantum_tanner_proposal_observables import (
    complete_quantum_tanner_proposal_observables,
)
```

Add a parser before the generation commands:

```python
complete_qt_proposal_observables_parser = subparsers.add_parser(
    "complete-quantum-tanner-proposal-observables",
    help="Complete logical-X observables for proposal-derived quantum Tanner instances",
)
complete_qt_proposal_observables_parser.add_argument("--root", default=".")
complete_qt_proposal_observables_parser.add_argument("--search-space", required=True)
complete_qt_proposal_observables_parser.add_argument("--basis", choices=["x"], required=True)
complete_qt_proposal_observables_parser.add_argument("--qec-code-bin", default=None)
complete_qt_proposal_observables_parser.add_argument("--force", action="store_true")
```

Add a branch in `main`:

```python
if args.command == "complete-quantum-tanner-proposal-observables":
    root = Path(args.root)
    if not root.exists():
        parser.error(f"repository root does not exist: {root}")
    summary = complete_quantum_tanner_proposal_observables(
        root,
        Path(args.search_space),
        basis=args.basis,
        qec_code_bin=args.qec_code_bin,
        force=args.force,
    )
    print(
        f"completed={summary.completed} "
        f"skipped={summary.skipped} "
        f"search_space={summary.search_space_path}"
    )
    for completion in summary.completions:
        print(f"- {completion.candidate_id}: {completion.observables_path}")
    return 0
```

- [ ] **Step 6: Run the focused tests and verify GREEN**

Run the issue-required command:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_observables.py::test_complete_proposal_observables_writes_exactly_k_valid_x_rows \
  tests/test_search_quantum_tanner_proposal_observables.py::test_complete_proposal_observables_rejects_incomplete_x_rows \
  tests/test_search_quantum_tanner_proposal_observables.py::test_complete_proposal_observables_rejects_z_like_witness_for_memory_x \
  -q
```

Expected: PASS.

- [ ] **Step 7: Run related regression tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_import.py \
  tests/test_search_screening.py \
  tests/test_search_eval_run.py::test_css_eval_rejects_incomplete_explicit_x_observables_for_k2_candidate \
  -q
```

Expected: PASS.

- [ ] **Step 8: Run workspace validation smoke**

Use the positive test's helper path if available through pytest, or manually
create a temporary workspace with the same fixture shape, run completion, then:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root /tmp/autoqec-qt-proposal-observables-workspace
```

Expected: exit code 0.

- [ ] **Step 9: Run full verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: PASS.

- [ ] **Step 10: Commit**

Commit all implementation files:

```bash
git add \
  benchmarks/schemas/search-space.schema.json \
  docs/superpowers/plans/2026-07-10-issue-92-quantum-tanner-proposal-observables.md \
  src/autoqec_search/cli.py \
  src/autoqec_search/quantum_tanner_proposal_observables.py \
  src/autoqec_search/structure.py \
  tests/test_search_quantum_tanner_proposal_observables.py
git commit -m "Fix #92: complete proposal logical-X observables"
```

## Self-Review

- Spec coverage: the command, provenance sidecar, exact `k` validation,
  witness-basis rejection, row-count rejection, resolver validation, and
  temporary-workspace validation are all assigned to Task 1.
- Placeholder scan: no `TBD`, `TODO`, or undefined helper names remain.
- Type consistency: the public function returns
  `ProposalObservablesCompletionSummary`, and the CLI only reads fields defined
  on that dataclass.
