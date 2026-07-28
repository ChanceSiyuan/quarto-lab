from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from autoqec_search.load import SearchIntegrityError


COPIED_ZOO_EXACT = "copied-zoo-exact"
LEGACY_COPIED_ZOO_EXACT = "copied-from-zoo-instance"
RSTIM_ILP_EXACT = "rstim-ilp-exact"
RANDOMIZED_UPPER_BOUND = "randomized-upper-bound"
RANDOM_WINDOW_UPPER_BOUND = "random-window-upper-bound"
CSS_UPPER_BOUND_WITNESS = "css-upper-bound-witness"
EXACT_DISTANCE_METHODS = {COPIED_ZOO_EXACT, RSTIM_ILP_EXACT}
UPPER_BOUND_DISTANCE_METHODS = {RANDOM_WINDOW_UPPER_BOUND}
UPPER_BOUND_PAYLOAD_METHODS = UPPER_BOUND_DISTANCE_METHODS | {
    RANDOMIZED_UPPER_BOUND,
    CSS_UPPER_BOUND_WITNESS,
}
EXACT_BOUND = "exact"
UPPER_BOUND = "upper"


@dataclass(frozen=True)
class DistanceMethodOptions:
    method: str = COPIED_ZOO_EXACT
    qec_code_bin: str = "qec-code"


@dataclass(frozen=True)
class LoadedDistancePayload:
    payload: dict[str, Any]
    distance: int | None
    upper_bound: int | None
    method: str | None
    bound_type: str | None


def normalize_distance_method_options(
    *,
    method: str | None,
    qec_code_bin: str = "qec-code",
    **unused_options: object,
) -> DistanceMethodOptions:
    selected_method = method or COPIED_ZOO_EXACT
    if selected_method not in EXACT_DISTANCE_METHODS | UPPER_BOUND_DISTANCE_METHODS:
        raise SearchIntegrityError(f"unknown distance method: {selected_method}")
    if not isinstance(qec_code_bin, str) or not qec_code_bin:
        raise SearchIntegrityError("qec-code executable must be a nonempty string")
    return DistanceMethodOptions(
        method=selected_method,
        qec_code_bin=qec_code_bin,
    )


def distance_method_metadata(options: DistanceMethodOptions) -> dict[str, Any]:
    bound_type = (
        UPPER_BOUND if options.method in UPPER_BOUND_DISTANCE_METHODS else EXACT_BOUND
    )
    return {
        "method": options.method,
        "bound_type": bound_type,
        "qec_code_bin": options.qec_code_bin,
    }


def _positive_int(value: object, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise SearchIntegrityError(f"{label} must be a positive integer")
    return value


def _nonnegative_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        raise SearchIntegrityError(f"{label} must be a nonnegative integer")
    return value


def _recorded_instance_distance(candidate, *, method: str) -> int:
    derived_properties = candidate.instance.get("derived_properties")
    if not isinstance(derived_properties, dict):
        raise SearchIntegrityError(f"{method} requires instance derived_properties.distance")
    try:
        return _positive_int(derived_properties.get("distance"), label="recorded distance")
    except SearchIntegrityError as exc:
        raise SearchIntegrityError(
            f"{method} requires instance derived_properties.distance"
        ) from exc


def _source_instance_id(candidate) -> str:
    source_instance_id = candidate.instance.get("id")
    if not isinstance(source_instance_id, str) or not source_instance_id:
        raise SearchIntegrityError("missing source instance id")
    return source_instance_id


def copied_zoo_exact_payload(
    candidate,
    options: DistanceMethodOptions,
) -> dict[str, Any]:
    source_instance_id = _source_instance_id(candidate)
    source_instance_path = str(candidate.artifact_root)
    return {
        "status": "completed",
        "distance": _recorded_instance_distance(candidate, method=COPIED_ZOO_EXACT),
        "method": COPIED_ZOO_EXACT,
        "bound_type": EXACT_BOUND,
        "options": {
            "method": COPIED_ZOO_EXACT,
            "qec_code_bin": options.qec_code_bin,
        },
        "provenance": {
            "source": "zoo-instance",
            "source_instance_id": source_instance_id,
            "source_instance_path": source_instance_path,
        },
        "source_instance_id": source_instance_id,
        "source_instance_path": source_instance_path,
    }


def random_window_upper_bound_payload(
    candidate,
    options: DistanceMethodOptions,
) -> dict[str, Any]:
    source_instance_id = _source_instance_id(candidate)
    source_instance_path = str(candidate.artifact_root)
    upper_bound = _recorded_instance_distance(
        candidate,
        method=RANDOM_WINDOW_UPPER_BOUND,
    )
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


def dense_binary_matrix_to_sparse_rows(matrix: dict[str, Any]) -> dict[str, Any]:
    if matrix.get("format") != "dense_binary_matrix":
        raise SearchIntegrityError("matrix format must be dense_binary_matrix")
    n_rows = _nonnegative_int(matrix.get("n_rows"), label="matrix n_rows")
    n_cols = _positive_int(matrix.get("n_cols"), label="matrix n_cols")
    rows = matrix.get("data")
    if not isinstance(rows, list) or len(rows) != n_rows:
        raise SearchIntegrityError("matrix data row count mismatch")

    sparse_rows: list[list[int]] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != n_cols:
            raise SearchIntegrityError(f"matrix row {row_index} width mismatch")
        sparse_row: list[int] = []
        for col_index, value in enumerate(row):
            if type(value) is not int or value not in {0, 1}:
                raise SearchIntegrityError("matrix entries must be 0 or 1")
            if value == 1:
                sparse_row.append(col_index)
        sparse_rows.append(sparse_row)
    return {"format": "sparse_rows", "num_cols": n_cols, "rows": sparse_rows}


def rstim_ilp_exact_payload(
    candidate,
    options: DistanceMethodOptions,
) -> dict[str, Any]:
    dense_binary_matrix_to_sparse_rows(candidate.hx)
    dense_binary_matrix_to_sparse_rows(candidate.hz)
    raise SearchIntegrityError(
        "rstim exact CSS distance backend is not available; "
        "use copied-zoo-exact for recorded instances or install a qec-code build "
        "with exact CSS distance"
    )


def compute_distance_payload(
    candidate,
    options: DistanceMethodOptions,
) -> dict[str, Any]:
    if options.method == COPIED_ZOO_EXACT:
        return copied_zoo_exact_payload(candidate, options)
    if options.method == RSTIM_ILP_EXACT:
        return rstim_ilp_exact_payload(candidate, options)
    if options.method == RANDOM_WINDOW_UPPER_BOUND:
        return random_window_upper_bound_payload(candidate, options)
    raise SearchIntegrityError(f"unknown distance method: {options.method}")


def _normalize_legacy_bound_type(payload: dict[str, Any], *, label: str) -> str | None:
    bound_type = payload.get("bound_type")
    method = payload.get("method")
    if bound_type == EXACT_BOUND:
        if method == RANDOMIZED_UPPER_BOUND or (
            isinstance(method, str) and "upper" in method
        ):
            raise SearchIntegrityError(
                f"{method} distance payload must use bound_type upper in {label}"
            )
        return EXACT_BOUND
    if bound_type == UPPER_BOUND:
        if method not in UPPER_BOUND_PAYLOAD_METHODS:
            raise SearchIntegrityError(
                f"unsupported upper-bound distance payload in {label}"
            )
        return UPPER_BOUND
    if bound_type is not None:
        raise SearchIntegrityError(f"invalid distance bound_type in {label}")
    if method in UPPER_BOUND_PAYLOAD_METHODS:
        raise SearchIntegrityError(
            f"{method} distance payload must use "
            f"bound_type upper in {label}"
        )
    if isinstance(method, str) and "upper" in method:
        raise SearchIntegrityError(
            f"unsupported upper-bound distance payload in {label}"
        )
    if method in {LEGACY_COPIED_ZOO_EXACT, COPIED_ZOO_EXACT, RSTIM_ILP_EXACT}:
        return EXACT_BOUND
    if (
        method is None
        and
        payload.get("status") in {"completed", "computed"}
        and type(payload.get("distance")) is int
    ):
        return EXACT_BOUND
    return None


def load_distance_payload_from_dict(
    payload: dict[str, Any],
    *,
    label: str,
) -> LoadedDistancePayload:
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} must be an object")
    distance = payload.get("distance")
    if distance is not None and (type(distance) is not int or distance <= 0):
        raise SearchIntegrityError(f"invalid distance in {label}")
    method = payload.get("method")
    if method is not None and not isinstance(method, str):
        raise SearchIntegrityError(f"invalid distance method in {label}")
    bound_type = _normalize_legacy_bound_type(payload, label=label)
    upper_bound = None
    if bound_type == UPPER_BOUND:
        raw_upper_bound = payload.get("upper_bound")
        if type(raw_upper_bound) is not int or raw_upper_bound <= 0:
            raise SearchIntegrityError(f"invalid upper_bound in {label}")
        upper_bound = raw_upper_bound
        if distance is not None and upper_bound != distance:
            raise SearchIntegrityError(
                f"upper_bound mismatch in {label}: {upper_bound} != {distance}"
            )
    return LoadedDistancePayload(
        payload=payload,
        distance=distance,
        upper_bound=upper_bound,
        method=method,
        bound_type=bound_type,
    )


def load_distance_payload(path: Path) -> LoadedDistancePayload:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(f"invalid distance JSON at {path}: {exc.msg}") from exc
    return load_distance_payload_from_dict(payload, label=str(path))
