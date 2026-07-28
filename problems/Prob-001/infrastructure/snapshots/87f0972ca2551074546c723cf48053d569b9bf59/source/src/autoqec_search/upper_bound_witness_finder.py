from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from math import isfinite
import json
from pathlib import Path
import shlex
import subprocess
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.structure import verify_css_upper_bound_witness


METHOD = "random-window-upper-bound"
BOUND_TYPE = "upper"
LOGICAL_CLASS_TO_BASIS = {
    "x_like": "x",
    "z_like": "z",
}
REQUIRED_KEYS = {
    "status",
    "method",
    "bound_type",
    "upper_bound",
    "logical_class",
    "witness",
    "options",
    "provenance",
}


def _is_plain_int(value: object) -> bool:
    return type(value) is int


def _require_nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"{label} must be a nonempty string")
    return value


def _require_positive_int(value: object, label: str) -> int:
    if not _is_plain_int(value) or value <= 0:
        raise SearchIntegrityError(f"{label} must be a positive integer")
    return value


def _require_nonnegative_int(value: object, label: str) -> int:
    if not _is_plain_int(value) or value < 0:
        raise SearchIntegrityError(f"{label} must be a nonnegative integer")
    return value


def _require_positive_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise SearchIntegrityError("timeout_seconds must be a positive number")
    if value <= 0:
        raise SearchIntegrityError("timeout_seconds must be a positive number")
    return float(value)


def _clip_backend_text(value: object, *, limit: int = 2048) -> str:
    if value is None:
        text = "<none>"
    elif isinstance(value, str):
        text = value
    else:
        text = repr(value)
    text = text.rstrip("\n")
    if len(text) > limit:
        return text[:limit] + "...<truncated>"
    return text


def _backend_context(
    command: Sequence[str],
    *,
    stdout: object = None,
    stderr: object = None,
) -> str:
    return (
        f"command: {shlex.join(list(command))}; "
        f"stdout: {_clip_backend_text(stdout)}; "
        f"stderr: {_clip_backend_text(stderr)}"
    )


def _require_keys(payload: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_KEYS - payload.keys())
    if not missing:
        return
    if missing == ["witness"]:
        raise SearchIntegrityError("missing_witness")
    if len(missing) == 1:
        raise SearchIntegrityError(f"missing_required_key: {missing[0]}")
    raise SearchIntegrityError(f"missing_required_keys: {', '.join(missing)}")


def _validate_witness_vector(value: object, *, label: str) -> list[int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SearchIntegrityError(f"invalid_witness_vector: {label}")
    vector = list(value)
    if any(not _is_plain_int(bit) or bit not in {0, 1} for bit in vector):
        raise SearchIntegrityError("non_binary_witness_entry")
    return [int(bit) for bit in vector]


def _require_matching_matrix_payload(
    matrix_path: str | Path,
    matrix_payload: dict,
    *,
    label: str,
) -> None:
    try:
        path_payload = json.loads(Path(matrix_path).read_text())
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(
            f"{label}_path malformed JSON: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise SearchIntegrityError(f"{label}_path read failed: {exc}") from exc
    if path_payload != matrix_payload:
        raise SearchIntegrityError(f"{label}_payload_path_mismatch")


def _validate_witness(payload: dict[str, Any]) -> dict[str, Any]:
    witness = payload.get("witness")
    if not isinstance(witness, dict):
        raise SearchIntegrityError("missing_witness")
    if set(witness) != {"x", "z", "weight"}:
        raise SearchIntegrityError("invalid_witness_keys")

    x_vector = _validate_witness_vector(witness["x"], label="witness.x")
    z_vector = _validate_witness_vector(witness["z"], label="witness.z")
    if len(x_vector) != len(z_vector):
        raise SearchIntegrityError("x_z_width_mismatch")

    weight = witness["weight"]
    if not _is_plain_int(weight) or weight <= 0:
        raise SearchIntegrityError("invalid_witness_weight")

    if sum(x_vector) + sum(z_vector) != weight:
        raise SearchIntegrityError("witness_weight_mismatch")

    logical_class = payload["logical_class"]
    basis = LOGICAL_CLASS_TO_BASIS.get(logical_class)
    if basis is None:
        raise SearchIntegrityError("unsupported_logical_class")
    if basis == "x":
        selected_vector = x_vector
        other_vector = z_vector
    else:
        selected_vector = z_vector
        other_vector = x_vector

    if not any(bit != 0 for bit in selected_vector):
        raise SearchIntegrityError("selected_witness_vector_zero")
    if any(bit != 0 for bit in other_vector):
        raise SearchIntegrityError("nonzero_complementary_pauli_support")
    if sum(selected_vector) != weight:
        raise SearchIntegrityError("upper_bound_weight_mismatch")

    return {
        "x": x_vector,
        "z": z_vector,
        "weight": int(weight),
    }


def validate_qec_code_random_window_upper_bound_result(payload: object) -> None:
    if not isinstance(payload, dict):
        raise SearchIntegrityError("qec-code random-window-upper-bound result must be an object")
    _require_keys(payload)

    if payload["status"] != "completed":
        raise SearchIntegrityError("invalid_status")
    if payload["method"] != METHOD:
        raise SearchIntegrityError("invalid_method")
    if payload["bound_type"] != BOUND_TYPE:
        raise SearchIntegrityError("invalid_bound_type")
    if not _is_plain_int(payload["upper_bound"]) or payload["upper_bound"] <= 0:
        raise SearchIntegrityError("invalid_upper_bound")
    if not isinstance(payload["logical_class"], str):
        raise SearchIntegrityError("unsupported_logical_class")
    if not isinstance(payload["options"], dict):
        raise SearchIntegrityError("invalid_options")
    if not isinstance(payload["provenance"], dict):
        raise SearchIntegrityError("invalid_provenance")

    witness = _validate_witness(payload)
    if payload["upper_bound"] != witness["weight"]:
        raise SearchIntegrityError("upper_bound_weight_mismatch")


def convert_qec_code_random_window_upper_bound_result(
    payload: object,
    hx_payload: dict,
    hz_payload: dict,
) -> dict[str, Any]:
    validate_qec_code_random_window_upper_bound_result(payload)
    assert isinstance(payload, dict)
    witness = payload["witness"]
    assert isinstance(witness, dict)
    basis = LOGICAL_CLASS_TO_BASIS[payload["logical_class"]]
    vector = [int(bit) for bit in witness[basis]]
    witness_payload = {"basis": basis, "vector": vector}
    verification = verify_css_upper_bound_witness(hx_payload, hz_payload, witness_payload)
    if verification.get("status") != "pass":
        reason = verification.get("reason", "invalid_upper_bound_witness")
        raise SearchIntegrityError(f"invalid_css_upper_bound_witness: {reason}")
    return {
        "status": "completed",
        "witness_payload": witness_payload,
        "distance_payload": verification["distance_payload"],
        "verification": verification,
        "qec_code_result": deepcopy(payload),
    }


def run_qec_code_random_window_upper_bound(
    hx_path: str | Path,
    hz_path: str | Path,
    *,
    qec_code_bin: str,
    iterations: int,
    restarts: int,
    seed: int,
    target_weight: int | None = None,
    timeout_seconds: float = 300,
) -> dict[str, Any]:
    _require_nonempty_string(qec_code_bin, "qec_code_bin")
    _require_positive_int(iterations, "iterations")
    _require_positive_int(restarts, "restarts")
    _require_nonnegative_int(seed, "seed")
    if target_weight is not None:
        _require_positive_int(target_weight, "target_weight")
    timeout_seconds = _require_positive_timeout(timeout_seconds)

    command = [
        qec_code_bin,
        "code",
        "css-distance",
        METHOD,
        "--hx",
        str(hx_path),
        "--hz",
        str(hz_path),
        "--iterations",
        str(iterations),
        "--restarts",
        str(restarts),
        "--seed",
        str(seed),
    ]
    if target_weight is not None:
        command.extend(["--target-weight", str(target_weight)])
    command.append("--json")

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SearchIntegrityError(
            "qec-code random-window-upper-bound timed out after "
            f"{timeout_seconds:g}s: "
            + _backend_context(command, stdout=exc.stdout, stderr=exc.stderr)
        ) from exc
    except OSError as exc:
        raise SearchIntegrityError(
            "qec-code random-window-upper-bound failed to start: "
            f"{exc}; {_backend_context(command)}"
        ) from exc

    if completed.returncode != 0:
        raise SearchIntegrityError(
            "qec-code random-window-upper-bound exited "
            f"{completed.returncode}: "
            + _backend_context(
                command,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(
            "qec-code random-window-upper-bound returned malformed JSON: "
            f"{exc.msg}; "
            + _backend_context(
                command,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        ) from exc

    try:
        validate_qec_code_random_window_upper_bound_result(payload)
    except SearchIntegrityError as exc:
        raise SearchIntegrityError(
            "qec-code random-window-upper-bound returned invalid result: "
            f"{exc}; "
            + _backend_context(
                command,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        ) from exc
    return payload


def run_qec_code_random_window_upper_bound_css_witness(
    hx_path: str | Path,
    hz_path: str | Path,
    *,
    hx_payload: dict,
    hz_payload: dict,
    qec_code_bin: str,
    iterations: int,
    restarts: int,
    seed: int,
    target_weight: int | None = None,
    timeout_seconds: float = 300,
) -> dict[str, Any]:
    _require_matching_matrix_payload(hx_path, hx_payload, label="hx")
    _require_matching_matrix_payload(hz_path, hz_payload, label="hz")
    result = run_qec_code_random_window_upper_bound(
        hx_path,
        hz_path,
        qec_code_bin=qec_code_bin,
        iterations=iterations,
        restarts=restarts,
        seed=seed,
        target_weight=target_weight,
        timeout_seconds=timeout_seconds,
    )
    return convert_qec_code_random_window_upper_bound_result(
        result,
        hx_payload,
        hz_payload,
    )
