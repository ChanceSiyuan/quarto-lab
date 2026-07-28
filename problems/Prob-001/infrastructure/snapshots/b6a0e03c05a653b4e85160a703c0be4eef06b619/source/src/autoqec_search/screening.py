from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal

from autoqec_search.distance_methods import load_distance_payload_from_dict
from autoqec_search.eval_candidates import ResolvedCandidate
from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_catalog import (
    load_quantum_tanner_fixture_catalog,
    resolve_quantum_tanner_fixture_entry,
)
from autoqec_search.structure import (
    _matrix_num_cols,
    complete_logical_observable_basis,
    matrix_data,
    verify_css_upper_bound_witness,
)


ScreeningStatus = Literal["admitted", "skipped", "failed"]
INCOMPATIBLE_UPPER_BOUND_WITNESS_BASIS = "incompatible_upper_bound_witness_basis"


@dataclass(frozen=True)
class ScreeningDecision:
    screening_status: ScreeningStatus
    distance_bound_type: str
    distance_upper_bound: int | None
    reason: str
    distance_payload_override: dict[str, Any] | None = None
    observables_x_override: dict[str, Any] | None = None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _safe_relative_repo_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts) or not path.parts:
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    return path


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


def _load_repo_json(root: Path, value: Any, *, label: str) -> dict[str, Any]:
    repo_path = _safe_relative_repo_path(value, label=label)
    return _load_json(root / repo_path, label=label)


def _catalog_entry_for_candidate(
    root: Path,
    candidate_spec: dict[str, Any],
) -> dict[str, Any] | None:
    catalog_path = candidate_spec.get("fixture_catalog_path")
    if catalog_path is None:
        return None
    if not isinstance(catalog_path, str) or not catalog_path:
        raise SearchIntegrityError("fixture_catalog_path must be a nonempty string")
    catalog = load_quantum_tanner_fixture_catalog(root, catalog_path)
    candidate_id = candidate_spec.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise SearchIntegrityError("candidate_id must be a nonempty string")
    for entry in catalog["entries"]:
        if entry.get("candidate_id") == candidate_id:
            return entry
    raise SearchIntegrityError(
        f"fixture catalog is missing candidate_id {candidate_id}: {catalog_path}"
    )


def resolve_catalog_backed_candidate(
    root: Path,
    candidate_spec: dict[str, Any],
    *,
    campaign_id: str,
) -> ResolvedCandidate | None:
    catalog_path = candidate_spec.get("fixture_catalog_path")
    entry = _catalog_entry_for_candidate(root, candidate_spec)
    if entry is None:
        return None
    expected_code_family = candidate_spec.get("code_family")
    if expected_code_family != entry["code_id"]:
        raise SearchIntegrityError(
            "catalog-backed candidate code_family mismatch: "
            f"{expected_code_family!r} != {entry['code_id']!r}"
        )
    return resolve_quantum_tanner_fixture_entry(
        root,
        entry,
        campaign_id=campaign_id,
        catalog_path=catalog_path,
    )


def resolve_catalog_backed_candidate_spec(
    root: Path,
    candidate_spec: dict[str, Any],
    *,
    campaign_id: str,
) -> dict[str, Any] | None:
    resolved = resolve_catalog_backed_candidate(
        root,
        candidate_spec,
        campaign_id=campaign_id,
    )
    if resolved is None:
        return None
    normalized = dict(candidate_spec)
    normalized["parameters"] = dict(resolved.spec.parameters)
    return normalized


def _sparse_rows_from_dense_rows(rows: list[list[int]], *, num_cols: int) -> dict[str, Any]:
    return {
        "format": "sparse_rows",
        "num_cols": num_cols,
        "rows": [
            [index for index, value in enumerate(row) if value == 1]
            for row in rows
        ],
    }


def _logical_x_observables_from_verified_witness(
    hx_payload: dict[str, Any],
    hz_payload: dict[str, Any],
    witness_payload: dict[str, Any],
) -> dict[str, Any]:
    vector = witness_payload.get("vector")
    if not isinstance(vector, list):
        raise SearchIntegrityError("upper-bound witness vector must be a list")
    hx = matrix_data(hx_payload, "hx.json")
    hz = matrix_data(hz_payload, "hz.json")
    hx_num_cols = _matrix_num_cols(hx_payload, hx, "hx.json")
    hz_num_cols = _matrix_num_cols(hz_payload, hz, "hz.json")
    if hx_num_cols != hz_num_cols:
        raise SearchIntegrityError("matrix column mismatch: hx.json vs hz.json")
    rows = complete_logical_observable_basis(
        kernel_rows=hz,
        stabilizer_rows=hx,
        preferred_vector=vector,
    )
    return _sparse_rows_from_dense_rows(rows, num_cols=hx_num_cols)


def _expected_upper_bound_witness_basis(
    benchmark_task: dict[str, Any] | None,
) -> str | None:
    if not isinstance(benchmark_task, dict):
        return None
    css_memory = benchmark_task.get("css_memory")
    if not isinstance(css_memory, dict):
        return None
    basis = css_memory.get("basis")
    if basis in {"x", "z"}:
        return str(basis)
    return None


def _basis_compatible_with_task(
    supplied_basis: object,
    *,
    expected_basis: str | None,
) -> bool:
    if expected_basis is None or supplied_basis is None:
        return True
    return supplied_basis == expected_basis


def _loaded_upper_bound_payload(
    payload: dict[str, Any],
    *,
    label: str,
) -> tuple[dict[str, Any], int]:
    if payload.get("status") != "completed":
        raise SearchIntegrityError(f"{label} must have status completed")
    loaded = load_distance_payload_from_dict(payload, label=label)
    if loaded.bound_type != "upper" or loaded.upper_bound is None:
        raise SearchIntegrityError(f"{label} must be an upper-bound distance payload")
    return dict(payload), loaded.upper_bound


def _failed_screening_decision(reason: str) -> ScreeningDecision:
    return ScreeningDecision(
        screening_status="failed",
        distance_bound_type="upper",
        distance_upper_bound=None,
        reason=reason,
    )


def _payload_screening_decision(
    payload: dict[str, Any],
    *,
    candidate: ResolvedCandidate,
    label: str,
    expected_basis: str | None,
) -> ScreeningDecision:
    distance_payload, upper_bound = _loaded_upper_bound_payload(payload, label=label)
    if not _basis_compatible_with_task(
        distance_payload.get("basis"),
        expected_basis=expected_basis,
    ):
        return _failed_screening_decision(INCOMPATIBLE_UPPER_BOUND_WITNESS_BASIS)
    if candidate.observables_x is None:
        return _failed_screening_decision("missing_explicit_logical_observables")
    return ScreeningDecision(
        screening_status="admitted",
        distance_bound_type="upper",
        distance_upper_bound=upper_bound,
        reason="loaded_upper_bound_payload",
        distance_payload_override=distance_payload,
        observables_x_override=candidate.observables_x,
    )


def screening_payload(decision: ScreeningDecision) -> dict[str, Any]:
    return {
        "screening_status": decision.screening_status,
        "distance_bound_type": decision.distance_bound_type,
        "distance_upper_bound": decision.distance_upper_bound,
        "reason": decision.reason,
    }


def write_screening_json(candidate_root: Path, decision: ScreeningDecision) -> None:
    _write_json(candidate_root / "screening.json", screening_payload(decision))


def load_screening_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = _load_json(path, label="screening artifact")
    expected_keys = {
        "screening_status",
        "distance_bound_type",
        "distance_upper_bound",
        "reason",
    }
    if set(payload) != expected_keys:
        raise SearchIntegrityError(f"invalid screening artifact: {path}")
    if payload["screening_status"] not in {"admitted", "skipped", "failed"}:
        raise SearchIntegrityError(f"invalid screening status in {path}")
    if payload["distance_bound_type"] != "upper":
        raise SearchIntegrityError(f"invalid screening distance_bound_type in {path}")
    upper_bound = payload["distance_upper_bound"]
    if upper_bound is not None and (type(upper_bound) is not int or upper_bound <= 0):
        raise SearchIntegrityError(f"invalid screening distance_upper_bound in {path}")
    reason = payload["reason"]
    if not isinstance(reason, str) or not reason:
        raise SearchIntegrityError(f"invalid screening reason in {path}")
    return payload


def screen_upper_bound_candidate(
    root: Path,
    *,
    candidate: ResolvedCandidate,
    candidate_spec: dict[str, Any],
    benchmark_task: dict[str, Any] | None = None,
) -> ScreeningDecision:
    try:
        expected_basis = _expected_upper_bound_witness_basis(benchmark_task)
        return _screen_upper_bound_candidate(
            root,
            candidate=candidate,
            candidate_spec=candidate_spec,
            expected_basis=expected_basis,
        )
    except SearchIntegrityError as exc:
        return _failed_screening_decision(str(exc))


def _screen_upper_bound_candidate(
    root: Path,
    *,
    candidate: ResolvedCandidate,
    candidate_spec: dict[str, Any],
    expected_basis: str | None,
) -> ScreeningDecision:
    witness_path = candidate_spec.get("upper_bound_witness_path")
    inline_payload = candidate_spec.get("upper_bound_payload")
    payload_path = candidate_spec.get("upper_bound_payload_path")
    supplied_inputs = [
        value is not None for value in (witness_path, inline_payload, payload_path)
    ]
    if sum(supplied_inputs) > 1:
        raise SearchIntegrityError("candidate has multiple upper-bound inputs")
    if inline_payload is not None:
        if not isinstance(inline_payload, dict):
            raise SearchIntegrityError("upper_bound_payload must be an object")
        return _payload_screening_decision(
            inline_payload,
            candidate=candidate,
            label="upper_bound_payload",
            expected_basis=expected_basis,
        )
    if payload_path is not None:
        return _payload_screening_decision(
            _load_repo_json(root, payload_path, label="upper_bound_payload_path"),
            candidate=candidate,
            label="upper_bound_payload_path",
            expected_basis=expected_basis,
        )
    if witness_path is None:
        return ScreeningDecision(
            screening_status="skipped",
            distance_bound_type="upper",
            distance_upper_bound=None,
            reason="missing_upper_bound_payload",
        )
    witness_payload = _load_json(
        root / _safe_relative_repo_path(witness_path, label="upper_bound_witness_path"),
        label="upper_bound_witness_path",
    )
    verification = verify_css_upper_bound_witness(candidate.hx, candidate.hz, witness_payload)
    if verification.get("status") != "pass":
        return ScreeningDecision(
            screening_status="failed",
            distance_bound_type="upper",
            distance_upper_bound=None,
            reason=str(verification.get("reason", "invalid_upper_bound_witness")),
        )
    distance_payload = verification.get("distance_payload")
    if not isinstance(distance_payload, dict):
        raise SearchIntegrityError("upper-bound witness is missing distance_payload")
    if not _basis_compatible_with_task(
        verification.get("basis"),
        expected_basis=expected_basis,
    ):
        return _failed_screening_decision(INCOMPATIBLE_UPPER_BOUND_WITNESS_BASIS)
    upper_bound = distance_payload.get("upper_bound")
    if type(upper_bound) is not int or upper_bound <= 0:
        raise SearchIntegrityError("upper-bound witness has invalid upper_bound")
    observables_x_override = (
        _logical_x_observables_from_verified_witness(
            candidate.hx,
            candidate.hz,
            witness_payload,
        )
        if verification.get("basis") == "x"
        else None
    )
    return ScreeningDecision(
        screening_status="admitted",
        distance_bound_type="upper",
        distance_upper_bound=upper_bound,
        reason="verified_upper_bound_witness",
        distance_payload_override=dict(distance_payload),
        observables_x_override=observables_x_override,
    )
