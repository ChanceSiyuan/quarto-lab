# Issue 90 Quantum Tanner Proposal Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize validator-passing quantum Tanner proposal JSON files into deterministic proposal-derived CSS instance bundles with null exact distance.

**Architecture:** Add a focused Python materialization module that validates proposals, writes a normalized qec-code quantum Tanner spec, invokes qec-code for `hx` and `hz`, validates sparse-row matrices, and atomically commits a proposal-derived instance bundle. Add a thin CLI command that routes to the module and prints materialization counts.

**Tech Stack:** Python 3, stdlib `dataclasses`, `hashlib`, `json`, `pathlib`, `shutil`, `subprocess`, `tempfile`, existing `autoqec_search.quantum_tanner_proposals` validator, pytest fake qec-code scripts.

## Global Constraints

- Reuse the issue 89 deterministic proposal validator before invoking `qec-code`.
- Require an explicit `--qec-code-bin` path; do not silently resolve through `PATH`.
- Keep this bridge local/offline; do not add GAP, Oscar, qLDPC, Julia, rsinter, rbposd, or live model calls.
- Materialized proposal bundles are search artifacts, not curated Zoo source-of-truth records.
- Do not force `zoo/schemas/code-instance.schema.json` compatibility for proposal-derived bundles.
- Do not copy `search_hints.target_distance`, qec-code output, or any upper bound into an exact-distance field.
- `instance.json` must set `parameters.distance` to `null` and `derived_properties.distance` to `null`.
- Use atomic staging; validation, qec-code, or malformed-matrix failures must leave no completed candidate directory for the failed proposal.
- Required issue verification includes the three tests in `tests/test_search_quantum_tanner_proposal_materialization.py`.
- Required Agent Desk verification includes `PYTHONPATH=src python3 -m pytest`.

---

## File Structure

- Create `tests/test_search_quantum_tanner_proposal_materialization.py`: CLI-level RED tests with fake qec-code scripts for valid, invalid, and malformed backend cases.
- Create `src/autoqec_search/quantum_tanner_proposal_materialization.py`: materialization API, qec-code command runner, matrix validation, artifact writing, staging cleanup, and summary dataclasses.
- Modify `src/autoqec_search/cli.py`: import the materialization function, add the `materialize-quantum-tanner-proposals` parser, and route command execution.

### Task 1: RED Tests For Proposal Materialization CLI

**Files:**
- Create: `tests/test_search_quantum_tanner_proposal_materialization.py`

**Interfaces:**
- Consumes existing fixtures:
  `tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json`
  and `tests/fixtures/quantum_tanner_proposals/invalid-bad-group-table.json`.
- Produces expected CLI:
  `python3 -m autoqec_search.cli materialize-quantum-tanner-proposals --root . --proposal <path> --out-root <path> --qec-code-bin <path> --force`.

- [ ] **Step 1: Write the failing test module**

Create `tests/test_search_quantum_tanner_proposal_materialization.py` with:

```python
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_PROPOSAL = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "valid-dihedral-d3.json"
)
INVALID_PROPOSAL = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "invalid-bad-group-table.json"
)


def _write_fake_qec_code(path: Path, *, malformed: bool = False) -> Path:
    if malformed:
        hx_payload = '{"format":"sparse_rows","num_cols":6,"rows":[[0,0]]}'
    else:
        hx_payload = '{"format":"sparse_rows","num_cols":6,"rows":[[0,1],[2,3]]}'
    hz_payload = '{"format":"sparse_rows","num_cols":6,"rows":[[4,5]]}'
    path.write_text(
        f"""#!/bin/sh
set -eu
if [ "${{1:-}}" = "--version" ]; then
  printf 'fake-qec-code 1.0\\n'
  exit 0
fi
if [ "$1" != "code" ] || [ "$2" != "css" ] || [ "$3" != "quantum-tanner" ]; then
  echo "unexpected args: $*" >&2
  exit 9
fi
if [ "$4" != "--spec" ]; then
  echo "missing --spec" >&2
  exit 9
fi
if [ "$6" = "hx" ]; then
  printf '%s\\n' '{hx_payload}'
elif [ "$6" = "hz" ]; then
  printf '%s\\n' '{hz_payload}'
else
  echo "unexpected matrix: $6" >&2
  exit 9
fi
""",
    )
    path.chmod(0o755)
    return path


def _run_materialize(
    *,
    proposal: Path,
    out_root: Path,
    qec_code_bin: Path,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "materialize-quantum-tanner-proposals",
            "--root",
            str(REPO_ROOT),
            "--proposal",
            str(proposal),
            "--out-root",
            str(out_root),
            "--qec-code-bin",
            str(qec_code_bin),
            "--force",
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def _candidate_dirs(out_root: Path) -> list[Path]:
    if not out_root.exists():
        return []
    return [path for path in out_root.iterdir() if path.is_dir()]


def test_materialize_validated_proposal_writes_instance_bundle_with_null_distance(
    tmp_path: Path,
) -> None:
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    out_root = tmp_path / "instances"

    result = _run_materialize(
        proposal=VALID_PROPOSAL,
        out_root=out_root,
        qec_code_bin=qec_code,
    )

    assert result.returncode == 0, result.stderr
    assert "materialized=1 failed=0" in result.stdout
    candidate_dirs = _candidate_dirs(out_root)
    assert len(candidate_dirs) == 1
    candidate_dir = candidate_dirs[0]
    for name in (
        "instance.json",
        "hx.json",
        "hz.json",
        "qec_code_quantum_tanner_spec.json",
        "materialization_manifest.json",
    ):
        assert (candidate_dir / name).is_file()
    instance = json.loads((candidate_dir / "instance.json").read_text())
    manifest = json.loads((candidate_dir / "materialization_manifest.json").read_text())
    assert instance["proposal_id"] == "valid-dihedral-d3"
    assert instance["artifacts"]["hx"] == "hx.json"
    assert instance["artifacts"]["hz"] == "hz.json"
    assert instance["parameters"].get("distance") is None
    assert instance["derived_properties"]["distance"] is None
    assert instance["provenance"]["validator"]["fingerprint"] == manifest["proposal_fingerprint"]
    assert instance["provenance"]["qec_code"]["version"] == "fake-qec-code 1.0"
    assert manifest["exact_distance_status"] == "unknown"
    assert set(manifest["output_hashes"]) >= {
        "instance.json",
        "hx.json",
        "hz.json",
        "qec_code_quantum_tanner_spec.json",
    }


def test_materialize_invalid_proposal_leaves_no_partial_instance(tmp_path: Path) -> None:
    qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    out_root = tmp_path / "instances"

    result = _run_materialize(
        proposal=INVALID_PROPOSAL,
        out_root=out_root,
        qec_code_bin=qec_code,
    )

    assert result.returncode != 0
    assert "InvalidGroupTable" in result.stderr
    assert _candidate_dirs(out_root) == []


def test_materialize_malformed_qec_code_output_leaves_no_partial_instance(
    tmp_path: Path,
) -> None:
    qec_code = _write_fake_qec_code(tmp_path / "bad-qec-code", malformed=True)
    out_root = tmp_path / "instances"

    result = _run_materialize(
        proposal=VALID_PROPOSAL,
        out_root=out_root,
        qec_code_bin=qec_code,
    )

    assert result.returncode != 0
    assert "duplicate support" in result.stderr
    assert _candidate_dirs(out_root) == []
```

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_materialization.py::test_materialize_validated_proposal_writes_instance_bundle_with_null_distance \
  tests/test_search_quantum_tanner_proposal_materialization.py::test_materialize_invalid_proposal_leaves_no_partial_instance \
  tests/test_search_quantum_tanner_proposal_materialization.py::test_materialize_malformed_qec_code_output_leaves_no_partial_instance \
  -q
```

Expected: FAIL during collection or CLI execution because the test file or
`materialize-quantum-tanner-proposals` command does not exist yet.

### Task 2: Implement Proposal Materialization API

**Files:**
- Create: `src/autoqec_search/quantum_tanner_proposal_materialization.py`

**Interfaces:**
- Produces:
  `materialize_quantum_tanner_proposal_file(root: Path, proposal_path: Path, out_root: Path, qec_code_bin: str, max_group_order: int = 32, force: bool = False) -> MaterializedProposalInstance`
- Produces:
  `materialize_quantum_tanner_proposal_files(root: Path, proposal_paths: tuple[Path, ...], out_root: Path, qec_code_bin: str, max_group_order: int = 32, force: bool = False) -> ProposalMaterializationSummary`
- Uses existing:
  `validate_quantum_tanner_proposal_file(path, max_group_order=...)`.

- [ ] **Step 1: Add the implementation module**

Create `src/autoqec_search/quantum_tanner_proposal_materialization.py` with:

```python
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_proposals import (
    QuantumTannerProposalSummary,
    validate_quantum_tanner_proposal_file,
)


SPEC_FILENAME = "qec_code_quantum_tanner_spec.json"
MANIFEST_FILENAME = "materialization_manifest.json"
PROPOSAL_MATERIALIZER_VERSION = "quantum-tanner-proposal-materializer-v1"


@dataclass(frozen=True)
class QecCodeCommandRecord:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": list(self.command),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class MaterializedProposalInstance:
    proposal_id: str
    candidate_id: str
    instance_dir: Path
    instance_path: Path
    hx_path: Path
    hz_path: Path
    normalized_spec_path: Path
    manifest_path: Path
    proposal_fingerprint: str


@dataclass(frozen=True)
class ProposalMaterializationSummary:
    materialized: int
    failed: int
    instances: tuple[MaterializedProposalInstance, ...]


def materialize_quantum_tanner_proposal_files(
    root: Path,
    proposal_paths: tuple[Path, ...],
    out_root: Path,
    *,
    qec_code_bin: str,
    max_group_order: int = 32,
    force: bool = False,
) -> ProposalMaterializationSummary:
    if not proposal_paths:
        raise SearchIntegrityError("at least one --proposal is required")
    instances: list[MaterializedProposalInstance] = []
    for proposal_path in proposal_paths:
        instances.append(
            materialize_quantum_tanner_proposal_file(
                root,
                proposal_path,
                out_root,
                qec_code_bin=qec_code_bin,
                max_group_order=max_group_order,
                force=force,
            )
        )
    return ProposalMaterializationSummary(
        materialized=len(instances),
        failed=0,
        instances=tuple(instances),
    )


def materialize_quantum_tanner_proposal_file(
    root: Path,
    proposal_path: Path,
    out_root: Path,
    *,
    qec_code_bin: str,
    max_group_order: int = 32,
    force: bool = False,
) -> MaterializedProposalInstance:
    _require_explicit_tool_path(qec_code_bin)
    resolved_root = root.resolve()
    resolved_proposal_path = proposal_path.resolve()
    summary = validate_quantum_tanner_proposal_file(
        resolved_proposal_path,
        max_group_order=max_group_order,
    )
    proposal = _load_json_object(resolved_proposal_path, "proposal")
    candidate_id = _candidate_id(summary.proposal_id)
    final_dir = out_root / candidate_id
    if final_dir.exists() and not force:
        raise SearchIntegrityError(f"{final_dir} already exists; rerun with --force")
    out_root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{candidate_id}.",
            suffix=".staging",
            dir=out_root,
        )
    )
    try:
        normalized_spec = normalize_proposal_for_qec_code(proposal)
        normalized_spec_path = staging_dir / SPEC_FILENAME
        _write_json(normalized_spec_path, normalized_spec)
        hx_record = _run_qec_code_matrix(qec_code_bin, normalized_spec_path, "hx")
        hz_record = _run_qec_code_matrix(qec_code_bin, normalized_spec_path, "hz")
        hx = _parse_sparse_rows_matrix(hx_record.stdout, label="hx")
        hz = _parse_sparse_rows_matrix(hz_record.stdout, label="hz")
        _validate_css_matrices(hx, hz)
        n = hx["num_cols"]
        k = _css_dimension(n, hx["rows"], hz["rows"])
        hx_path = staging_dir / "hx.json"
        hz_path = staging_dir / "hz.json"
        _write_json(hx_path, hx)
        _write_json(hz_path, hz)
        qec_code_version = _qec_code_version(qec_code_bin)
        instance = _build_instance_payload(
            root=resolved_root,
            proposal_path=resolved_proposal_path,
            proposal=proposal,
            summary=summary,
            candidate_id=candidate_id,
            n=n,
            k=k,
            hx=hx,
            hz=hz,
            hx_record=hx_record,
            hz_record=hz_record,
            qec_code_bin=qec_code_bin,
            qec_code_version=qec_code_version,
        )
        instance_path = staging_dir / "instance.json"
        _write_json(instance_path, instance)
        manifest_path = staging_dir / MANIFEST_FILENAME
        output_hashes = _hash_outputs(
            staging_dir,
            (
                "instance.json",
                "hx.json",
                "hz.json",
                SPEC_FILENAME,
            ),
        )
        manifest = _build_manifest_payload(
            proposal_path=resolved_proposal_path,
            summary=summary,
            candidate_id=candidate_id,
            hx_record=hx_record,
            hz_record=hz_record,
            qec_code_bin=qec_code_bin,
            qec_code_version=qec_code_version,
            output_hashes=output_hashes,
        )
        _write_json(manifest_path, manifest)
        output_hashes[MANIFEST_FILENAME] = _sha256_file(manifest_path)
        manifest["output_hashes"] = output_hashes
        _write_json(manifest_path, manifest)
        if final_dir.exists():
            shutil.rmtree(final_dir)
        staging_dir.replace(final_dir)
        return MaterializedProposalInstance(
            proposal_id=summary.proposal_id,
            candidate_id=candidate_id,
            instance_dir=final_dir,
            instance_path=final_dir / "instance.json",
            hx_path=final_dir / "hx.json",
            hz_path=final_dir / "hz.json",
            normalized_spec_path=final_dir / SPEC_FILENAME,
            manifest_path=final_dir / MANIFEST_FILENAME,
            proposal_fingerprint=summary.fingerprint,
        )
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def normalize_proposal_for_qec_code(proposal: dict[str, Any]) -> dict[str, Any]:
    group = proposal["base_group"]
    local_codes = proposal["local_codes"]
    return {
        "fixture_id": proposal["proposal_id"],
        "construction_mode": proposal["construction_mode"],
        "base_group": {
            "name": group["name"],
            "element_order": group["element_order"],
            "order": group["order"],
            "identity": group["identity"],
            "multiplication_table": group["multiplication_table"],
        },
        "a_generator_indices": proposal["a_generator_indices"],
        "b_generator_indices": proposal["b_generator_indices"],
        "local_codes": {
            "matrix_role": local_codes["matrix_role"],
            "field": local_codes["field"],
            "h_a": local_codes["h_a"],
            "h_b": local_codes["h_b"],
        },
    }
```

Add helpers in the same module for `_load_json_object`, `_write_json`,
`_require_explicit_tool_path`, `_candidate_id`, `_run_qec_code_matrix`,
`_qec_code_version`, `_parse_sparse_rows_matrix`, `_validate_css_matrices`,
`_css_dimension`, `_gf2_rank`, `_hash_outputs`, `_sha256_file`,
`_repo_relative_or_absolute`, `_build_instance_payload`, and
`_build_manifest_payload`. The helper behavior must match the design:
explicit path enforcement, sparse-row validation, commutation validation,
stable JSON writes, SHA-256 hashes, and null exact-distance fields.

- [ ] **Step 2: Run focused tests to verify GREEN is not reached until CLI is wired**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_proposal_materialization.py -q
```

Expected: still FAIL because the CLI command is not yet registered.

### Task 3: Wire CLI Command And Complete GREEN

**Files:**
- Modify: `src/autoqec_search/cli.py`

**Interfaces:**
- Consumes:
  `materialize_quantum_tanner_proposal_files(root, proposal_paths, out_root, qec_code_bin=..., max_group_order=..., force=...)`.
- Produces success output:
  `materialized=<count> failed=0`.

- [ ] **Step 1: Add CLI imports and parser**

In `src/autoqec_search/cli.py`, import:

```python
from autoqec_search.quantum_tanner_proposal_materialization import (
    materialize_quantum_tanner_proposal_files,
)
```

In `build_parser`, add:

```python
    materialize_qt_proposals_parser = subparsers.add_parser(
        "materialize-quantum-tanner-proposals",
        help="Materialize validated quantum Tanner proposals through qec-code",
    )
    materialize_qt_proposals_parser.add_argument("--root", default=".")
    materialize_qt_proposals_parser.add_argument(
        "--proposal",
        action="append",
        required=True,
    )
    materialize_qt_proposals_parser.add_argument("--out-root", required=True)
    materialize_qt_proposals_parser.add_argument("--qec-code-bin", required=True)
    materialize_qt_proposals_parser.add_argument("--max-group-order", type=int, default=32)
    materialize_qt_proposals_parser.add_argument("--force", action="store_true")
```

- [ ] **Step 2: Add CLI execution branch**

In `main`, before the generated-sweep command branch, add:

```python
        if args.command == "materialize-quantum-tanner-proposals":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            summary = materialize_quantum_tanner_proposal_files(
                root,
                tuple(Path(path) for path in args.proposal),
                Path(args.out_root),
                qec_code_bin=args.qec_code_bin,
                max_group_order=args.max_group_order,
                force=args.force,
            )
            print(f"materialized={summary.materialized} failed={summary.failed}")
            for instance in summary.instances:
                print(f"- {instance.candidate_id}: {instance.instance_dir}")
            return 0
```

- [ ] **Step 3: Run focused tests to verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_materialization.py::test_materialize_validated_proposal_writes_instance_bundle_with_null_distance \
  tests/test_search_quantum_tanner_proposal_materialization.py::test_materialize_invalid_proposal_leaves_no_partial_instance \
  tests/test_search_quantum_tanner_proposal_materialization.py::test_materialize_malformed_qec_code_output_leaves_no_partial_instance \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run related validator regression tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_proposals.py -q
```

Expected: PASS.

### Task 4: Final Verification And PR Prep

**Files:**
- Verify only; no intended edits.

**Interfaces:**
- Consumes the complete implementation from Tasks 1-3.
- Produces final test evidence and a PR-ready branch.

- [ ] **Step 1: Run issue verification command**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposal_materialization.py::test_materialize_validated_proposal_writes_instance_bundle_with_null_distance \
  tests/test_search_quantum_tanner_proposal_materialization.py::test_materialize_invalid_proposal_leaves_no_partial_instance \
  tests/test_search_quantum_tanner_proposal_materialization.py::test_materialize_malformed_qec_code_output_leaves_no_partial_instance \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full repository pytest gate**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: PASS.

- [ ] **Step 3: Run a manual CLI smoke with fake qec-code**

Create a temporary fake qec-code binary equivalent to the test helper and run:

```bash
WORK_ROOT=/tmp/autoqec-qt-proposal-materialize
rm -rf "$WORK_ROOT"
mkdir -p "$WORK_ROOT"
PYTHONPATH=src python3 -m autoqec_search.cli materialize-quantum-tanner-proposals \
  --root . \
  --proposal tests/fixtures/quantum_tanner_proposals/valid-dihedral-d3.json \
  --out-root "$WORK_ROOT/instances" \
  --qec-code-bin "$WORK_ROOT/qec-code" \
  --force
```

Expected stdout includes `materialized=1 failed=0` and the instance directory
contains `instance.json`, `hx.json`, `hz.json`, and
`materialization_manifest.json`.

- [ ] **Step 4: Commit and open PR**

Run:

```bash
git status --short
git add src/autoqec_search/quantum_tanner_proposal_materialization.py src/autoqec_search/cli.py tests/test_search_quantum_tanner_proposal_materialization.py docs/superpowers/plans/2026-07-10-issue-90-quantum-tanner-proposal-materialization.md
git commit -m "feat: materialize quantum Tanner proposals"
git push -u origin agent/issue-90-materialize-validated-quantum-tanner-proposals-t-run-1
gh pr create --repo nzy1997/AutoQEC --base main --head agent/issue-90-materialize-validated-quantum-tanner-proposals-t-run-1 --title "Materialize validated quantum Tanner proposals" --body-file /tmp/issue-90-pr-body.md
```

Expected: branch pushed and PR URL printed.
