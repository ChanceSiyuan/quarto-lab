from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from jsonschema import Draft202012Validator

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_proposals import (
    QuantumTannerProposalSummary,
    validate_quantum_tanner_proposal,
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
    resolved_root = root.resolve()
    resolved_proposal_path = proposal_path.resolve()
    proposal = _load_json_object(resolved_proposal_path, "proposal")
    _validate_proposal_schema(resolved_root, proposal)
    summary = validate_quantum_tanner_proposal(
        proposal,
        max_group_order=max_group_order,
    )
    _require_explicit_tool_path(qec_code_bin)
    candidate_id = _candidate_id(summary.proposal_id)
    resolved_out_root = out_root if out_root.is_absolute() else resolved_root / out_root
    final_dir = resolved_out_root / candidate_id
    if final_dir.exists() and not force:
        raise SearchIntegrityError(f"{final_dir} already exists; rerun with --force")
    resolved_out_root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{candidate_id}.",
            suffix=".staging",
            dir=resolved_out_root,
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
        n = int(hx["num_cols"])
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
        manifest_path = staging_dir / MANIFEST_FILENAME
        _write_json(manifest_path, manifest)
        _promote_staging_dir(staging_dir, final_dir)
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


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as err:
        raise SearchIntegrityError(f"invalid {label} JSON: {path}") from err
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} must contain a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _validate_proposal_schema(root: Path, proposal: dict[str, Any]) -> None:
    schema_path = root / "benchmarks" / "schemas" / "quantum-tanner-proposal.schema.json"
    schema = _load_json_object(schema_path, "quantum Tanner proposal schema")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(proposal)


def _require_explicit_tool_path(value: str) -> None:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError("qec_code_bin must be a non-empty string")
    path = Path(value)
    if path.is_absolute():
        return
    separators = {os.sep}
    if os.altsep is not None:
        separators.add(os.altsep)
    if any(separator in value for separator in separators):
        return
    raise SearchIntegrityError(
        "qec_code_bin must be an explicit path; PATH lookup is disabled"
    )


def _candidate_id(proposal_id: str) -> str:
    path = Path(proposal_id)
    if (
        not proposal_id
        or "/" in proposal_id
        or "\\" in proposal_id
        or proposal_id in {".", ".."}
        or path.name != proposal_id
        or path != Path(path.name)
    ):
        raise SearchIntegrityError(f"proposal_id must be a safe candidate id: {proposal_id}")
    return proposal_id


def _run_qec_code_matrix(
    qec_code_bin: str,
    spec_path: Path,
    matrix_name: str,
) -> QecCodeCommandRecord:
    command = (
        qec_code_bin,
        "code",
        "css",
        "quantum-tanner",
        "--spec",
        str(spec_path),
        matrix_name,
    )
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as err:
        raise SearchIntegrityError(
            f"failed to execute qec-code command {' '.join(command)}: {err}"
        ) from err
    if completed.returncode != 0:
        raise SearchIntegrityError(
            f"qec-code {matrix_name} command failed with exit code {completed.returncode}: "
            f"{' '.join(command)}"
            + (
                f"\nstderr:\n{completed.stderr.rstrip()}"
                if completed.stderr.strip()
                else ""
            )
            + (
                f"\nstdout:\n{completed.stdout.rstrip()}"
                if completed.stdout.strip()
                else ""
            )
        )
    return QecCodeCommandRecord(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _qec_code_version(qec_code_bin: str) -> str | None:
    try:
        completed = subprocess.run(
            (qec_code_bin, "--version"),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    version = completed.stdout.strip() or completed.stderr.strip()
    return version or None


def _parse_sparse_rows_matrix(text: str, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as err:
        raise SearchIntegrityError(f"{label} qec-code output must be valid JSON") from err
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} qec-code output must be a JSON object")
    if payload.get("format") != "sparse_rows":
        raise SearchIntegrityError(f"{label} format must be sparse_rows")
    num_cols = payload.get("num_cols")
    rows = payload.get("rows")
    if not _is_plain_int(num_cols) or num_cols <= 0:
        raise SearchIntegrityError(f"{label} num_cols must be a positive integer")
    if not isinstance(rows, list):
        raise SearchIntegrityError(f"{label} rows must be a list")
    normalized_rows: list[list[int]] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, list):
            raise SearchIntegrityError(f"{label} row {row_index} must be a list")
        normalized_row: list[int] = []
        previous = -1
        for column in row:
            if not _is_plain_int(column):
                raise SearchIntegrityError(f"{label} row {row_index} has invalid column")
            if column < 0 or column >= num_cols:
                raise SearchIntegrityError(
                    f"{label} row {row_index} has out-of-range column {column}"
                )
            if column == previous:
                raise SearchIntegrityError(
                    f"{label} row {row_index} has duplicate support at column {column}"
                )
            if column < previous:
                raise SearchIntegrityError(
                    f"{label} row {row_index} columns must be strictly increasing"
                )
            previous = column
            normalized_row.append(int(column))
        normalized_rows.append(normalized_row)
    return {"format": "sparse_rows", "num_cols": int(num_cols), "rows": normalized_rows}


def _validate_css_matrices(hx: dict[str, Any], hz: dict[str, Any]) -> None:
    num_cols = int(hx["num_cols"])
    if num_cols != int(hz["num_cols"]):
        raise SearchIntegrityError("matrix column mismatch: hx.json vs hz.json")
    hx_dense = _dense_rows_from_sparse(num_cols, hx["rows"])
    hz_dense = _dense_rows_from_sparse(num_cols, hz["rows"])
    for hx_index, hx_row in enumerate(hx_dense):
        for hz_index, hz_row in enumerate(hz_dense):
            overlap = sum(left & right for left, right in zip(hx_row, hz_row, strict=True))
            if overlap % 2:
                raise SearchIntegrityError(
                    "quantum Tanner proposal CSS checks do not commute: "
                    f"hx row {hx_index} with hz row {hz_index}"
                )


def _css_dimension(n: int, hx_rows: list[list[int]], hz_rows: list[list[int]]) -> int:
    rank_hx = _gf2_rank(_dense_rows_from_sparse(n, hx_rows))
    rank_hz = _gf2_rank(_dense_rows_from_sparse(n, hz_rows))
    dimension = n - rank_hx - rank_hz
    if dimension < 0:
        raise SearchIntegrityError("computed CSS dimension is negative")
    return dimension


def _gf2_rank(matrix: list[list[int]]) -> int:
    rows = [row[:] for row in matrix if any(row)]
    if not rows:
        return 0
    rank = 0
    for column in range(len(rows[0])):
        pivot_index = next(
            (index for index in range(rank, len(rows)) if rows[index][column] == 1),
            None,
        )
        if pivot_index is None:
            continue
        rows[rank], rows[pivot_index] = rows[pivot_index], rows[rank]
        for index in range(len(rows)):
            if index != rank and rows[index][column] == 1:
                rows[index] = [
                    left ^ right for left, right in zip(rows[index], rows[rank], strict=True)
                ]
        rank += 1
        if rank == len(rows):
            break
    return rank


def _hash_outputs(root: Path, filenames: tuple[str, ...]) -> dict[str, str]:
    return {name: _sha256_file(root / name) for name in filenames}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _repo_relative_or_absolute(root: Path, path: Path) -> str:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_root or resolved_root in resolved_path.parents:
        return resolved_path.relative_to(resolved_root).as_posix()
    return str(resolved_path)


def _build_instance_payload(
    *,
    root: Path,
    proposal_path: Path,
    proposal: dict[str, Any],
    summary: QuantumTannerProposalSummary,
    candidate_id: str,
    n: int,
    k: int,
    hx: dict[str, Any],
    hz: dict[str, Any],
    hx_record: QecCodeCommandRecord,
    hz_record: QecCodeCommandRecord,
    qec_code_bin: str,
    qec_code_version: str | None,
) -> dict[str, Any]:
    proposal_provenance = proposal.get("provenance")
    return {
        "artifacts": {"hx": "hx.json", "hz": "hz.json"},
        "candidate_id": candidate_id,
        "code_id": "quantum-tanner-code",
        "derived_properties": {
            "distance": None,
            "kx": None,
            "kz": None,
            "mx": len(hx["rows"]),
            "mz": len(hz["rows"]),
            "n": n,
        },
        "instance_id": candidate_id,
        "instance_kind": "finite_css_instance",
        "k": k,
        "matrix_format": "sparse_rows_json",
        "n": n,
        "parameters": {
            "base_group": proposal["base_group"]["name"],
            "construction_mode": proposal["construction_mode"],
            "distance": None,
        },
        "proposal_id": summary.proposal_id,
        "provenance": {
            "materializer": {"version": PROPOSAL_MATERIALIZER_VERSION},
            "proposal": {
                "fingerprint": summary.fingerprint,
                "path": _repo_relative_or_absolute(root, proposal_path),
                "provenance": (
                    dict(proposal_provenance)
                    if isinstance(proposal_provenance, dict)
                    else None
                ),
            },
            "qec_code": {
                "bin": qec_code_bin,
                "hx_command": hx_record.to_dict(),
                "hz_command": hz_record.to_dict(),
                "version": qec_code_version,
            },
            "validator": summary.to_dict(),
        },
        "quantum_tanner_spec": SPEC_FILENAME,
    }


def _build_manifest_payload(
    *,
    proposal_path: Path,
    summary: QuantumTannerProposalSummary,
    candidate_id: str,
    hx_record: QecCodeCommandRecord,
    hz_record: QecCodeCommandRecord,
    qec_code_bin: str,
    qec_code_version: str | None,
    output_hashes: dict[str, str],
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "exact_distance_status": "unknown",
        "materializer_version": PROPOSAL_MATERIALIZER_VERSION,
        "output_hashes": dict(output_hashes),
        "proposal_fingerprint": summary.fingerprint,
        "proposal_id": summary.proposal_id,
        "proposal_path": str(proposal_path),
        "qec_code": {
            "bin": qec_code_bin,
            "hx_command": hx_record.to_dict(),
            "hz_command": hz_record.to_dict(),
            "version": qec_code_version,
        },
        "validator": {
            "fingerprint": summary.fingerprint,
            "summary": summary.to_dict(),
            "version": summary.validator_version,
        },
    }


def _promote_staging_dir(staging_dir: Path, final_dir: Path) -> None:
    backup_dir: Path | None = None
    try:
        if final_dir.exists():
            backup_dir = final_dir.with_name(final_dir.name + ".backup")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            final_dir.replace(backup_dir)
        staging_dir.replace(final_dir)
    except Exception:
        if backup_dir is not None and backup_dir.exists() and not final_dir.exists():
            backup_dir.replace(final_dir)
        raise
    finally:
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir)


def _dense_rows_from_sparse(num_cols: int, rows: list[list[int]]) -> list[list[int]]:
    dense_rows: list[list[int]] = []
    for sparse_row in rows:
        dense_row = [0] * num_cols
        for column in sparse_row:
            dense_row[column] = 1
        dense_rows.append(dense_row)
    return dense_rows


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
