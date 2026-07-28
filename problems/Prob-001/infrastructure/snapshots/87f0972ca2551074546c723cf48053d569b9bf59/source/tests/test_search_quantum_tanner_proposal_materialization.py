from __future__ import annotations

import copy
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


def _write_fake_qec_code(
    path: Path,
    *,
    malformed: bool = False,
    invocation_marker: Path | None = None,
) -> Path:
    if malformed:
        hx_payload = '{"format":"sparse_rows","num_cols":6,"rows":[[0,0]]}'
    else:
        hx_payload = '{"format":"sparse_rows","num_cols":6,"rows":[[0,1],[2,3]]}'
    hz_payload = '{"format":"sparse_rows","num_cols":6,"rows":[[4,5]]}'
    marker_path = str(invocation_marker) if invocation_marker is not None else ""
    path.write_text(
        f"""#!/bin/sh
set -eu
if [ -n "{marker_path}" ]; then
  : > "{marker_path}"
fi
if [ \"${{1:-}}\" = "--version" ]; then
  printf 'fake-qec-code 1.0\\n'
  exit 0
fi
if [ \"$1\" != \"code\" ] || [ \"$2\" != \"css\" ] || [ \"$3\" != \"quantum-tanner\" ]; then
  echo \"unexpected args: $*\" >&2
  exit 9
fi
if [ \"$4\" != \"--spec\" ]; then
  echo \"missing --spec\" >&2
  exit 9
fi
if [ \"$6\" = \"hx\" ]; then
  printf '%s\\n' '{hx_payload}'
elif [ \"$6\" = \"hz\" ]; then
  printf '%s\\n' '{hz_payload}'
else
  echo \"unexpected matrix: $6\" >&2
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
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PATH": "/nonexistent",
    }
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
    assert "distance" in instance["parameters"]
    assert instance["parameters"]["distance"] is None
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
    marker = tmp_path / "qec-code-invoked"
    qec_code = _write_fake_qec_code(
        tmp_path / "qec-code",
        invocation_marker=marker,
    )
    out_root = tmp_path / "instances"

    result = _run_materialize(
        proposal=INVALID_PROPOSAL,
        out_root=out_root,
        qec_code_bin=qec_code,
    )

    assert result.returncode != 0
    assert "InvalidGroupTable" in result.stderr
    assert not marker.exists()
    assert _candidate_dirs(out_root) == []


def test_materialize_schema_invalid_proposal_leaves_no_partial_instance(
    tmp_path: Path,
) -> None:
    proposal = json.loads(VALID_PROPOSAL.read_text())
    proposal["local_codes"] = copy.deepcopy(proposal["local_codes"])
    proposal["local_codes"]["field"] = "GF(4)"
    proposal_path = tmp_path / "schema-invalid-proposal.json"
    proposal_path.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")
    marker = tmp_path / "qec-code-invoked"
    qec_code = _write_fake_qec_code(
        tmp_path / "qec-code",
        invocation_marker=marker,
    )
    out_root = tmp_path / "instances"

    result = _run_materialize(
        proposal=proposal_path,
        out_root=out_root,
        qec_code_bin=qec_code,
    )

    assert result.returncode != 0
    assert "GF(2)" in result.stderr
    assert not marker.exists()
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
