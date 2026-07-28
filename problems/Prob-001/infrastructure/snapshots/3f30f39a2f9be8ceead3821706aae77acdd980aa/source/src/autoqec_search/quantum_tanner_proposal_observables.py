from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from autoqec_search.eval_candidates import (
    ResolvedCandidate,
    _validate_resolved_path_under_root,
    resolve_campaign_candidate_spec,
)
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


@dataclass(frozen=True)
class _CompletionPlan:
    completion: CompletedProposalObservables
    observables_payload: dict[str, Any]
    instance_payload: dict[str, Any]
    provenance_payload: dict[str, Any]


def _safe_relative_repo_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts) or not path.parts:
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    return path


def _resolve_under_root(root: Path, path: Path, *, label: str) -> Path:
    if path.is_absolute():
        return path
    return root / _safe_relative_repo_path(str(path), label=label)


def _repo_relative_path(root: Path, path: Path, *, label: str) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise SearchIntegrityError(f"{label} must stay within repository root: {path}") from exc


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}: {path}")
    return payload


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dense_rows_to_sparse_rows(rows: list[list[int]]) -> list[list[int]]:
    return [
        [column for column, bit in enumerate(row) if bit == 1]
        for row in rows
    ]


def _prepare_json_write(path: Path, payload: dict[str, Any], *, label: str) -> Path:
    if path.is_dir():
        raise SearchIntegrityError(f"{label} output path must not be a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(_json_text(payload))
        return Path(tmp.name)


def _reserve_backup_path(path: Path, *, label: str) -> Path:
    if path.is_dir():
        raise SearchIntegrityError(f"{label} backup path must not be a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.backup.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        backup_path = Path(tmp.name)
    backup_path.unlink(missing_ok=True)
    return backup_path


def _write_completion_plan(plan: _CompletionPlan) -> None:
    writes = (
        (plan.completion.observables_path, plan.observables_payload, "observables_x"),
        (plan.completion.provenance_path, plan.provenance_payload, "observables_x provenance"),
        (plan.completion.instance_dir / "instance.json", plan.instance_payload, "instance"),
    )
    staged_paths: dict[Path, Path] = {}
    backup_paths: dict[Path, Path | None] = {}
    installed_targets: list[Path] = []
    try:
        for target_path, payload, label in writes:
            staged_paths[target_path] = _prepare_json_write(target_path, payload, label=label)
        for target_path, _payload, label in writes:
            if target_path.exists():
                backup_path = _reserve_backup_path(target_path, label=label)
                target_path.replace(backup_path)
                backup_paths[target_path] = backup_path
            else:
                backup_paths[target_path] = None
        for target_path, _payload, _label in writes:
            staged_paths[target_path].replace(target_path)
            installed_targets.append(target_path)
    except Exception:
        for target_path in reversed(installed_targets):
            backup_path = backup_paths.get(target_path)
            if backup_path is not None and backup_path.exists():
                backup_path.replace(target_path)
            else:
                target_path.unlink(missing_ok=True)
        for target_path, backup_path in backup_paths.items():
            if target_path in installed_targets:
                continue
            if backup_path is not None and backup_path.exists():
                backup_path.replace(target_path)
        raise
    finally:
        for tmp_path in staged_paths.values():
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        for backup_path in backup_paths.values():
            if backup_path is not None and backup_path.exists():
                backup_path.unlink(missing_ok=True)


def _search_space_validator(root: Path) -> Draft202012Validator:
    schema_path = root / "benchmarks" / "schemas" / "search-space.schema.json"
    schema = _load_json(schema_path, label="search-space schema")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _proposal_candidate_specs(search_space: dict[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for candidate_spec in search_space.get("candidate_specs", []):
        if not isinstance(candidate_spec, dict):
            continue
        if "instance_path" not in candidate_spec:
            continue
        provenance = candidate_spec.get("provenance")
        if isinstance(provenance, dict) and provenance.get("kind") == "proposal-derived":
            selected.append(candidate_spec)
    return selected


def _require_supported_candidate(
    candidate: ResolvedCandidate,
    *,
    candidate_id: str,
) -> None:
    if candidate.spec.code_family != "quantum-tanner-code":
        raise SearchIntegrityError(
            f"proposal-derived candidate must use quantum-tanner-code: {candidate_id}"
        )
    if candidate.source_kind != "explicit-zoo-instance":
        raise SearchIntegrityError(
            f"proposal-derived candidate must resolve to an explicit instance: {candidate_id}"
        )


def _matrix_num_cols_from_payload(matrix_payload: dict[str, Any], *, label: str) -> int:
    matrix_format = matrix_payload.get("format") if isinstance(matrix_payload, dict) else None
    if matrix_format == "dense_binary_matrix":
        num_cols = matrix_payload.get("n_cols")
    elif matrix_format == "sparse_rows":
        num_cols = matrix_payload.get("num_cols")
    else:
        raise SearchIntegrityError(f"unsupported matrix format: {label}")
    if type(num_cols) is not int or num_cols <= 0:
        raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
    return num_cols


def _source_num_cols(
    *,
    candidate_id: str,
    hx_payload: dict[str, Any],
    hz_payload: dict[str, Any],
) -> int:
    hx_num_cols = _matrix_num_cols_from_payload(hx_payload, label="hx.json")
    hz_num_cols = _matrix_num_cols_from_payload(hz_payload, label="hz.json")
    if hx_num_cols != hz_num_cols:
        raise SearchIntegrityError(
            f"HX/HZ column mismatch for candidate {candidate_id}: {hx_num_cols} != {hz_num_cols}"
        )
    return hx_num_cols


def _expected_logical_dimension(num_cols: int, hx_rows: list[list[int]], hz_rows: list[list[int]]) -> int:
    return num_cols - gf2_rank(hx_rows) - gf2_rank(hz_rows)


def _validated_sparse_observables_payload(
    observables_x: dict[str, Any],
) -> tuple[int, list[list[int]]]:
    if observables_x.get("format") != "sparse_rows":
        raise SearchIntegrityError("explicit X observables must use sparse_rows format")
    num_cols = observables_x.get("num_cols")
    if type(num_cols) is not int or num_cols <= 0:
        raise SearchIntegrityError("explicit X observables must declare a positive num_cols")
    rows_payload = observables_x.get("rows")
    if not isinstance(rows_payload, list):
        raise SearchIntegrityError("explicit X observables must define rows")
    dense_rows: list[list[int]] = []
    for row_index, sparse_row in enumerate(rows_payload):
        if not isinstance(sparse_row, list):
            raise SearchIntegrityError("explicit X observables rows must be arrays")
        dense_row = [0] * num_cols
        previous = -1
        for column in sparse_row:
            if type(column) is not int:
                raise SearchIntegrityError("explicit X observables contain non-binary entries")
            if column < 0 or column >= num_cols:
                raise SearchIntegrityError("explicit X observables column mismatch")
            if column <= previous:
                raise SearchIntegrityError(
                    "explicit X observables rows must use strictly increasing columns"
                )
            dense_row[column] = 1
            previous = column
        dense_rows.append(dense_row)
    return num_cols, dense_rows


def _validate_x_observables_payload(
    *,
    candidate_id: str,
    source_num_cols: int,
    hx_rows: list[list[int]],
    hz_rows: list[list[int]],
    observables_x: dict[str, Any],
) -> list[list[int]]:
    num_cols, dense_rows = _validated_sparse_observables_payload(observables_x)
    if num_cols != source_num_cols:
        raise SearchIntegrityError(
            f"explicit X observables column mismatch for candidate {candidate_id}"
        )
    expected_k = num_cols - gf2_rank(hx_rows) - gf2_rank(hz_rows)
    row_count = len(dense_rows)
    if row_count != expected_k:
        raise SearchIntegrityError(
            f"explicit X observables define {row_count} rows, expected k = {expected_k}"
        )
    for row in dense_rows:
        if not gf2_vector_in_kernel(hz_rows, row):
            raise SearchIntegrityError(
                f"explicit X observables are not in ker(HZ) for candidate {candidate_id}"
            )
    if gf2_rank([*hx_rows, *dense_rows]) != gf2_rank(hx_rows) + expected_k:
        raise SearchIntegrityError(
            f"explicit X observables are not independent modulo HX for candidate {candidate_id}"
        )
    return dense_rows


def _verified_witness_payload(
    candidate: ResolvedCandidate,
    witness_payload: dict[str, Any],
    *,
    basis: str,
    candidate_id: str,
) -> dict[str, Any]:
    verification = verify_css_upper_bound_witness(candidate.hx, candidate.hz, witness_payload)
    if verification.get("status") != "pass":
        reason = verification.get("reason", "invalid_upper_bound_witness")
        raise SearchIntegrityError(
            f"candidate {candidate_id} upper-bound witness verification failed: {reason}"
        )
    if verification.get("basis") != basis:
        raise SearchIntegrityError(
            f"incompatible upper-bound witness basis for candidate {candidate_id}: "
            f"expected {basis}, got {verification.get('basis')}"
        )
    return verification


def _completed_payload_and_provenance(
    *,
    candidate: ResolvedCandidate,
    candidate_id: str,
    root_relative_search_space_path: Path,
    witness_relative_path: Path,
    witness_payload: dict[str, Any],
    source_num_cols: int,
    hx_rows: list[list[int]],
    hz_rows: list[list[int]],
    basis: str,
    qec_code_bin: str | None,
    force: bool,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    completed_rows = complete_logical_observable_basis(
        kernel_rows=hz_rows,
        stabilizer_rows=hx_rows,
        preferred_vector=witness_payload["vector"],
    )
    observables_payload = {
        "format": "sparse_rows",
        "num_cols": source_num_cols,
        "rows": _dense_rows_to_sparse_rows(completed_rows),
    }
    dense_rows = _validate_x_observables_payload(
        candidate_id=candidate_id,
        source_num_cols=source_num_cols,
        hx_rows=hx_rows,
        hz_rows=hz_rows,
        observables_x=observables_payload,
    )
    observables_text = _json_text(observables_payload)
    provenance = candidate.spec.provenance
    proposal = provenance.get("proposal") if isinstance(provenance, dict) else None
    expected_k = _expected_logical_dimension(source_num_cols, hx_rows, hz_rows)
    provenance_payload = {
        "basis": basis,
        "candidate_id": candidate_id,
        "command_options": {
            "basis": basis,
            "force": force,
            "qec_code_bin": qec_code_bin,
            "root": ".",
            "search_space_path": str(root_relative_search_space_path),
        },
        "computed_k": expected_k,
        "input_witness": {
            "basis": witness_payload.get("basis"),
            "path": str(witness_relative_path),
        },
        "matrix_dimensions": {
            "k": expected_k,
            "mx": len(hx_rows),
            "mz": len(hz_rows),
            "n": source_num_cols,
        },
        "method": "complete_logical_observable_basis",
        "method_version": PROPOSAL_OBSERVABLE_COMPLETION_VERSION,
        "observables_sha256": _sha256_text(observables_text),
        "proposal_id": proposal.get("proposal_id") if isinstance(proposal, dict) else None,
        "row_count": len(dense_rows),
    }
    return observables_payload, provenance_payload, len(dense_rows)


def complete_quantum_tanner_proposal_observables(
    root: Path,
    search_space_path: Path,
    *,
    basis: str = "x",
    qec_code_bin: str | None = None,
    force: bool = False,
) -> ProposalObservablesCompletionSummary:
    resolved_root = root.resolve()
    resolved_search_space_path = _resolve_under_root(
        resolved_root,
        search_space_path,
        label="search_space_path",
    )
    relative_search_space_path = _repo_relative_path(
        resolved_root,
        resolved_search_space_path,
        label="search_space_path",
    )
    search_space = _load_json(resolved_search_space_path, label="search_space")
    validator = _search_space_validator(resolved_root)
    validator.validate(search_space)
    if basis != "x":
        raise SearchIntegrityError(f"unsupported basis for proposal observable completion: {basis}")

    candidate_specs = search_space.get("candidate_specs")
    if not isinstance(candidate_specs, list):
        raise SearchIntegrityError(f"invalid search space candidate_specs: {resolved_search_space_path}")
    selected_specs = _proposal_candidate_specs(search_space)

    plans: list[_CompletionPlan] = []
    missing_witness_count = 0
    for candidate_spec in selected_specs:
        candidate_id = candidate_spec.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise SearchIntegrityError("proposal-derived candidate must define candidate_id")
        candidate = resolve_campaign_candidate_spec(
            resolved_root,
            candidate_spec,
            campaign_id=search_space["campaign_id"],
        )
        _require_supported_candidate(candidate, candidate_id=candidate_id)

        hx_rows = matrix_data(candidate.hx, "hx.json")
        hz_rows = matrix_data(candidate.hz, "hz.json")
        source_num_cols = _source_num_cols(
            candidate_id=candidate_id,
            hx_payload=candidate.hx,
            hz_payload=candidate.hz,
        )
        if candidate.observables_x is not None:
            _validate_x_observables_payload(
                candidate_id=candidate_id,
                source_num_cols=source_num_cols,
                hx_rows=hx_rows,
                hz_rows=hz_rows,
                observables_x=candidate.observables_x,
            )

        witness_value = candidate_spec.get("upper_bound_witness_path")
        if witness_value is None:
            missing_witness_count += 1
            continue

        instance_dir = candidate.artifact_root
        observables_path = instance_dir / OBSERVABLES_X_FILENAME
        provenance_path = instance_dir / OBSERVABLES_X_PROVENANCE_FILENAME
        if not force and (observables_path.exists() or provenance_path.exists()):
            raise SearchIntegrityError(
                f"proposal observable completion artifacts already exist for candidate {candidate_id}; "
                "rerun with --force to replace them"
            )

        witness_relative_path = _safe_relative_repo_path(
            witness_value,
            label="upper_bound_witness_path",
        )
        witness_repo_path = resolved_root / witness_relative_path
        _validate_resolved_path_under_root(
            resolved_root,
            witness_repo_path,
            label="upper_bound_witness_path",
        )
        witness_payload = _load_json(witness_repo_path, label="upper_bound_witness_path")
        _verified_witness_payload(
            candidate,
            witness_payload,
            basis=basis,
            candidate_id=candidate_id,
        )
        observables_payload, provenance_payload, row_count = _completed_payload_and_provenance(
            candidate=candidate,
            candidate_id=candidate_id,
            root_relative_search_space_path=relative_search_space_path,
            witness_relative_path=witness_relative_path,
            witness_payload=witness_payload,
            source_num_cols=source_num_cols,
            hx_rows=hx_rows,
            hz_rows=hz_rows,
            basis=basis,
            qec_code_bin=qec_code_bin,
            force=force,
        )
        instance_payload = json.loads(json.dumps(candidate.instance))
        artifacts = instance_payload.get("artifacts")
        if not isinstance(artifacts, dict):
            raise SearchIntegrityError(f"instance artifacts must be an object: {instance_dir / 'instance.json'}")
        artifacts["observables_x"] = OBSERVABLES_X_FILENAME
        plans.append(
            _CompletionPlan(
                completion=CompletedProposalObservables(
                    candidate_id=candidate_id,
                    instance_dir=instance_dir,
                    observables_path=observables_path,
                    provenance_path=provenance_path,
                    row_count=row_count,
                ),
                observables_payload=observables_payload,
                instance_payload=instance_payload,
                provenance_payload=provenance_payload,
            )
        )

    for plan in plans:
        _write_completion_plan(plan)

    skipped = len(candidate_specs) - len(selected_specs) + missing_witness_count
    return ProposalObservablesCompletionSummary(
        completed=len(plans),
        skipped=skipped,
        search_space_path=resolved_search_space_path,
        completions=tuple(plan.completion for plan in plans),
    )
