from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from autoqec_search.load import SearchIntegrityError


SCHEMA_FILENAME = "surface-single-logical-baseline.schema.json"
SURFACE_SINGLE_LOGICAL_P = 0.001


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(
            f"invalid surface single-logical baseline JSON at {path}: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(
            f"surface single-logical baseline must be an object: {path}"
        )
    return payload


def _schema_path_for(baseline_path: Path) -> Path:
    local_schema = baseline_path.parent.parent / "schemas" / SCHEMA_FILENAME
    if not local_schema.is_file():
        raise SearchIntegrityError(
            f"missing surface single-logical baseline schema: {local_schema}"
        )
    return local_schema


def _validate_schema(payload: dict, *, baseline_path: Path) -> None:
    schema_path = _schema_path_for(baseline_path)
    try:
        schema = json.loads(schema_path.read_text())
        Draft202012Validator(schema).validate(payload)
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(
            f"invalid surface single-logical baseline schema JSON at {schema_path}: "
            f"{exc.msg}"
        ) from exc
    except OSError as exc:
        raise SearchIntegrityError(
            f"unable to read surface single-logical baseline schema at {schema_path}: {exc}"
        ) from exc
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path)
        suffix = f" at {location}" if location else ""
        raise SearchIntegrityError(
            f"invalid surface single-logical baseline schema{suffix}: {exc.message}"
        ) from exc


def _row_label(index: int) -> str:
    return f"surface single-logical baseline row {index}"


def _require_plain_int(row: dict[str, Any], key: str, *, index: int) -> int:
    value = row[key]
    if type(value) is not int:
        raise SearchIntegrityError(f"{_row_label(index)} {key} must be an integer")
    return value


def _require_probability(row: dict[str, Any], key: str, *, index: int) -> float:
    value = row[key]
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise SearchIntegrityError(f"{_row_label(index)} {key} must be finite")
    probability = float(value)
    if probability < 0.0 or probability > 1.0:
        raise SearchIntegrityError(f"{_row_label(index)} {key} must be in [0, 1]")
    return probability


def _validate_row(row: dict[str, Any], *, index: int) -> None:
    p = _require_probability(row, "p", index=index)
    if not math.isclose(p, SURFACE_SINGLE_LOGICAL_P, rel_tol=0.0, abs_tol=1e-15):
        raise SearchIntegrityError(f"{_row_label(index)} must use p=0.001")

    distance = _require_plain_int(row, "distance", index=index)
    logical_qubits = _require_plain_int(row, "logical_qubits", index=index)
    physical_qubits = _require_plain_int(row, "physical_qubits", index=index)
    shots = _require_plain_int(row, "shots", index=index)
    failures = _require_plain_int(row, "failures", index=index)

    if logical_qubits != 1:
        raise SearchIntegrityError(f"{_row_label(index)} logical_qubits must equal 1")
    if physical_qubits != distance**2:
        raise SearchIntegrityError(
            f"{_row_label(index)} physical_qubits must equal distance ** 2"
        )
    if failures > shots:
        raise SearchIntegrityError(f"{_row_label(index)} failures must not exceed shots")

    ler = _require_probability(row, "ler", index=index)
    expected_ler = failures / shots
    if not math.isclose(ler, expected_ler, rel_tol=0.0, abs_tol=1e-15):
        raise SearchIntegrityError(f"{_row_label(index)} ler must equal failures / shots")

    ci_low = _require_probability(row, "ci_low", index=index)
    ci_high = _require_probability(row, "ci_high", index=index)
    if ci_low > ci_high:
        raise SearchIntegrityError(f"{_row_label(index)} CI interval is inverted")
    if not ci_low <= ler <= ci_high:
        raise SearchIntegrityError(f"{_row_label(index)} ler must lie inside the CI")


def load_surface_single_logical_baseline(path: Path | str) -> dict:
    """Load and validate a rotated-surface p001 single-logical baseline manifest."""

    baseline_path = Path(path)
    payload = _load_json(baseline_path)
    _validate_schema(payload, baseline_path=baseline_path)

    if payload.get("baseline_id") != "rotated-surface-single-logical-p001":
        raise SearchIntegrityError(
            "surface single-logical baseline id must be "
            "rotated-surface-single-logical-p001"
        )
    if payload.get("code_id") != "rotated-surface-code" or payload.get("layout") != "rotated":
        raise SearchIntegrityError(
            "surface single-logical baseline must record rotated-surface-code layout rotated"
        )

    for index, row in enumerate(payload["rows"]):
        _validate_row(row, index=index)

    return payload
