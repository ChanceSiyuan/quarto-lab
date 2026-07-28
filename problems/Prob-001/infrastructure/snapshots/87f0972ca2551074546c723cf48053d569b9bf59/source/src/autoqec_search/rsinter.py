from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite, isclose, sqrt
from pathlib import Path
import shutil
import subprocess
from typing import Any

from autoqec_search.decoder_parameters import (
    DecoderParameterError,
    canonical_decoder_config,
    canonical_decoder_parameters,
)
from autoqec_search.load import SearchIntegrityError

RSINTER_RUN_TIMEOUT_SECONDS = 3600
RSINTER_DEFAULT_BATCH_SIZE = 256
GENERIC_RESULT_PARAM_KEYS = {
    "input_type",
    "distance",
    "rounds",
    "p",
    "max_shots",
    "max_errors",
    "max_wall_seconds",
    "batch_size",
    "basis",
    "schedule",
    "hx",
    "hz",
    "observables",
    "code_id",
}
RESULT_METADATA_PARAM_KEYS = {
    "decoder_impl",
    "logical_failure_aggregation",
    "logical_observable_basis",
    "logical_observable_count",
    "logical_observable_source",
    "seed",
}
RBPOSD_RESULT_ONLY_PARAM_KEYS = frozenset({"bp_method", "bp_schedule"})
OBSERVABLE_RUN_METADATA_KEYS = frozenset(RESULT_METADATA_PARAM_KEYS)
LOGICAL_FAILURE_AGGREGATION_ANY_LOGICAL = "any_logical"
BB72_EXPLICIT_OBSERVABLE_RUN_METADATA = {
    "decoder_impl": "rbposd",
    "logical_failure_aggregation": LOGICAL_FAILURE_AGGREGATION_ANY_LOGICAL,
    "logical_observable_source": "explicit",
    "logical_observable_basis": "x",
    "logical_observable_count": 12,
    "seed": 12345,
}


@dataclass(frozen=True)
class ParsedResults:
    points: list[dict]
    decoder_parameters: dict[str, Any]
    run_metadata: dict[str, Any]

    def __iter__(self):
        return iter(self.points)

    def __len__(self) -> int:
        return len(self.points)

    def __getitem__(self, index):
        return self.points[index]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return self.points == other
        return super().__eq__(other)


def _reject_duplicate_decoder_ids(decoder_ids: list[str]) -> None:
    seen: set[str] = set()
    for decoder_id in decoder_ids:
        if decoder_id in seen:
            raise SearchIntegrityError(f"duplicate decoder filter: {decoder_id}")
        seen.add(decoder_id)


def _validate_probability(p: float) -> float:
    if not isfinite(p) or not 0 < p < 1:
        raise SearchIntegrityError(f"p must satisfy 0 < p < 1: {p}")
    return p


def parse_decoder_filter(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    decoder_ids: list[str] = []
    for value in values:
        for item in value.split(","):
            decoder_id = item.strip()
            if not decoder_id:
                raise SearchIntegrityError("decoder filter is empty")
            decoder_ids.append(decoder_id)
    _reject_duplicate_decoder_ids(decoder_ids)
    return decoder_ids


def parse_p_filter(values: list[str] | None) -> list[float] | None:
    if not values:
        return None
    parsed: list[float] = []
    seen: set[float] = set()
    for value in values:
        for item in value.split(","):
            text = item.strip()
            if not text:
                raise SearchIntegrityError("p filter is empty")
            try:
                numeric = float(text)
            except ValueError as exc:
                raise SearchIntegrityError(f"invalid p filter: {text}") from exc
            p = _validate_probability(numeric)
            if p in seen:
                raise SearchIntegrityError(f"duplicate p filter: {p}")
            seen.add(p)
            parsed.append(p)
    return parsed


def validate_selected_decoders(suite: dict, selected: list[str] | None) -> list[str]:
    suite_decoders = suite["decoder_ids"]
    _reject_duplicate_decoder_ids(suite_decoders)
    if selected is None:
        return suite_decoders
    _reject_duplicate_decoder_ids(selected)
    unknown = sorted(set(selected) - set(suite_decoders))
    if unknown:
        raise SearchIntegrityError(f"decoder filter not in suite: {', '.join(unknown)}")
    return selected


def validate_selected_p_values(task: dict, selected: list[float] | None) -> list[float]:
    task_values = [_validate_probability(float(value)) for value in task["p_list"]]
    seen_task_values: set[float] = set()
    for value in task_values:
        if value in seen_task_values:
            raise SearchIntegrityError(f"duplicate p filter: {value}")
        seen_task_values.add(value)
    if selected is None:
        return task_values
    seen: set[float] = set()
    for value in selected:
        _validate_probability(value)
        if value in seen:
            raise SearchIntegrityError(f"duplicate p filter: {value}")
        seen.add(value)
    unknown = [value for value in selected if value not in task_values]
    if unknown:
        raise SearchIntegrityError(f"p filter not in task p_list: {unknown}")
    return selected


def _require_positive_distance_value(value: Any, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise SearchIntegrityError(f"{label} must be a positive integer distance")
    return value


def _distance_context_text(distance_context: dict[str, Any] | None) -> str:
    if not distance_context:
        return ""
    parts: list[str] = []
    for key in ("method", "bound_type", "upper_bound"):
        value = distance_context.get(key)
        if value is not None:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def exact_distance_required_message(
    subject: str,
    *,
    verb: str = "requires",
    distance_context: dict[str, Any] | None = None,
) -> str:
    message = f"{subject} {verb} exact distance"
    context = _distance_context_text(distance_context)
    if context:
        return f"{message} ({context})"
    return message


def rounds_for_task(
    task: dict,
    *,
    distance: int | None,
    distance_context: dict[str, Any] | None = None,
) -> int:
    policy = task["rounds_policy"]
    if policy["kind"] == "fixed":
        rounds = int(policy["rounds"])
        if rounds < 1:
            raise SearchIntegrityError(f"invalid fixed rounds: {rounds}")
        return rounds
    if policy["kind"] != "distance-scaled":
        raise SearchIntegrityError(f"unsupported rounds policy: {policy['kind']}")
    if distance is None:
        raise SearchIntegrityError(
            exact_distance_required_message(
                "distance-scaled rounds",
                verb="require",
                distance_context=distance_context,
            )
        )
    return max(int(policy["minimum"]), int(policy["multiplier"]) * distance)


def wilson_interval(*, errors: int, shots: int, z: float = 1.96) -> tuple[float, float]:
    if shots <= 0:
        raise SearchIntegrityError(f"invalid shots: {shots}")
    if errors < 0:
        raise SearchIntegrityError(f"invalid errors: {errors}")
    if errors > shots:
        raise SearchIntegrityError(f"errors exceed shots: {errors} > {shots}")

    phat = errors / shots
    denominator = 1 + z * z / shots
    center = (phat + z * z / (2 * shots)) / denominator
    margin = (
        z
        * sqrt((phat * (1 - phat) + z * z / (4 * shots)) / shots)
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _require_object(record: dict, key: str, path: Path, line_number: int) -> dict:
    value = record.get(key)
    if not isinstance(value, dict):
        raise SearchIntegrityError(f"{path}:{line_number}: missing {key} object")
    return value


def _require_number(
    record: dict, key: str, path: Path, line_number: int, label: str
) -> int | float:
    value = record.get(key)
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise SearchIntegrityError(
            f"{path}:{line_number}: missing numeric {label} {key}"
        )
    return value


def _require_int(
    record: dict,
    key: str,
    path: Path,
    line_number: int,
    label: str,
    *,
    require_numeric: bool = False,
    allow_integral_float: bool = False,
) -> int:
    value = record.get(key)
    if require_numeric:
        _require_number(record, key, path, line_number, label)
    if (
        allow_integral_float
        and isinstance(value, float)
        and isfinite(value)
        and value.is_integer()
    ):
        return int(value)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SearchIntegrityError(
            f"{path}:{line_number}: missing integer {label} {key}"
        )
    return value


def _optional_metric_number(
    record: dict, key: str, path: Path, line_number: int
) -> float | None:
    if key not in record:
        return None
    value = record[key]
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise SearchIntegrityError(f"{path}:{line_number}: invalid {key}")
    return float(value)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _result_only_decoder_param_keys(*, impl_key: str | None) -> frozenset[str]:
    if impl_key == "rbposd":
        return RBPOSD_RESULT_ONLY_PARAM_KEYS
    return frozenset()


def validate_observable_run_metadata(
    metadata: dict[str, Any] | None,
    *,
    context: str = "run metadata",
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(metadata, dict) or not metadata:
        raise SearchIntegrityError(f"{context}: missing run metadata")
    keys = set(metadata)
    missing = sorted(OBSERVABLE_RUN_METADATA_KEYS - keys)
    if missing:
        raise SearchIntegrityError(
            f"{context}: missing run metadata fields: {', '.join(missing)}"
        )
    extra = sorted(keys - OBSERVABLE_RUN_METADATA_KEYS)
    if extra:
        raise SearchIntegrityError(
            f"{context}: unexpected run metadata fields: {', '.join(extra)}"
        )

    normalized: dict[str, Any] = {}
    for key in (
        "decoder_impl",
        "logical_failure_aggregation",
        "logical_observable_source",
    ):
        value = metadata[key]
        if not isinstance(value, str) or not value:
            raise SearchIntegrityError(f"{context}: {key} must be a nonempty string")
        normalized[key] = value

    basis = metadata["logical_observable_basis"]
    if basis not in {"x", "z"}:
        raise SearchIntegrityError(
            f"{context}: logical_observable_basis must be x or z"
        )
    normalized["logical_observable_basis"] = basis

    count = metadata["logical_observable_count"]
    if type(count) is not int or count <= 0:
        raise SearchIntegrityError(
            f"{context}: logical_observable_count must be a positive integer"
        )
    normalized["logical_observable_count"] = count

    seed = metadata["seed"]
    if type(seed) is not int or seed < 0:
        raise SearchIntegrityError(f"{context}: seed must be a nonnegative integer")
    normalized["seed"] = seed

    expected_metadata = _validate_expected_observable_run_metadata(
        expected,
        context=f"{context}: expected run metadata",
    )
    if expected_metadata is not None:
        for key, expected_value in expected_metadata.items():
            actual_value = normalized[key]
            if actual_value != expected_value:
                raise SearchIntegrityError(
                    f"{context}: unexpected {key}: "
                    f"{actual_value!r} != {expected_value!r}"
                )
    return dict(sorted(normalized.items()))


def _validate_expected_observable_run_metadata(
    expected: dict[str, Any] | None,
    *,
    context: str,
) -> dict[str, Any] | None:
    if expected is None:
        return None
    if not isinstance(expected, dict) or not expected:
        raise SearchIntegrityError(f"{context}: missing expected run metadata")
    keys = set(expected)
    extra = sorted(keys - OBSERVABLE_RUN_METADATA_KEYS)
    if extra:
        raise SearchIntegrityError(
            f"{context}: unexpected run metadata fields: {', '.join(extra)}"
        )

    normalized: dict[str, Any] = {}
    for key, value in expected.items():
        if key == "logical_observable_basis":
            if value not in {"x", "z"}:
                raise SearchIntegrityError(
                    f"{context}: logical_observable_basis must be x or z"
                )
            normalized[key] = value
        elif key == "logical_observable_count":
            if type(value) is not int or value <= 0:
                raise SearchIntegrityError(
                    f"{context}: logical_observable_count must be a positive integer"
                )
            normalized[key] = value
        elif key == "seed":
            if type(value) is not int or value < 0:
                raise SearchIntegrityError(
                    f"{context}: seed must be a nonnegative integer"
                )
            normalized[key] = value
        else:
            if not isinstance(value, str) or not value:
                raise SearchIntegrityError(f"{context}: {key} must be a nonempty string")
            normalized[key] = value
    return dict(sorted(normalized.items()))


def parse_results_jsonl(
    path: str | Path,
    *,
    expected_decoder_id: str,
    expected_task_id: str,
    expected_distance: int | None,
    expected_p_values: list[float],
    expected_decoder_parameters: dict[str, Any] | None = None,
    expected_impl_key: str | None = None,
    require_observable_run_metadata: bool = False,
    expected_observable_run_metadata: dict[str, Any] | None = None,
) -> ParsedResults:
    results_path = Path(path)
    if expected_distance is not None:
        expected_distance = _require_positive_distance_value(
            expected_distance, label="expected_distance"
        )
    expected_decoder_parameters = canonical_decoder_parameters(
        expected_decoder_parameters or {},
        impl_key=expected_impl_key,
    )
    # Current rsinter BenchmarkResultRow records do not include a task id.
    # Keep expected_task_id so AutoQEC call sites retain context and future rows
    # can validate it without changing this parser API again.
    points: list[dict] = []
    seen_p: set[float] = set()
    decoder_parameters: dict[str, Any] | None = None
    run_metadata: dict[str, Any] | None = None
    expected_observable_run_metadata = _validate_expected_observable_run_metadata(
        expected_observable_run_metadata,
        context=f"{results_path}: expected run metadata",
    )

    def _param_int(record: dict[str, Any], key: str, line_number: int) -> int:
        value = record.get(key)
        if isinstance(value, list) and len(value) == 1:
            singleton = value[0]
            if type(singleton) is int:
                return singleton
        return _require_int(record, key, results_path, line_number, "param")

    for line_number, line in enumerate(results_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line, parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: invalid JSONL record: {exc}"
            ) from exc
        if not isinstance(record, dict):
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: result record must be an object"
            )
        if record.get("runner") != expected_decoder_id:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: unexpected runner"
            )
        if record.get("status") != "ok":
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: rsinter row status is not ok"
            )

        params = _require_object(record, "params", results_path, line_number)
        metrics = _require_object(record, "metrics", results_path, line_number)
        case_summary = _require_object(record, "case_summary", results_path, line_number)

        p = float(_require_number(params, "p", results_path, line_number, "param"))
        if p not in expected_p_values:
            raise SearchIntegrityError(f"{results_path}:{line_number}: unexpected p: {p}")
        if p in seen_p:
            raise SearchIntegrityError(
                f"{results_path}: line {line_number}: duplicate p: {p}"
            )
        seen_p.add(p)
        rounds = _param_int(params, "rounds", line_number)
        if rounds < 1:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: invalid rounds: {rounds}"
            )
        if "distance" in params:
            distance = _param_int(params, "distance", line_number)
            if expected_distance is not None and distance != expected_distance:
                raise SearchIntegrityError(
                    f"{results_path}:{line_number}: unexpected distance: {distance}"
                )

        row_run_metadata = {
            key: params[key]
            for key in sorted(RESULT_METADATA_PARAM_KEYS)
            if key in params
        }
        if (
            "logical_observable_count" not in row_run_metadata
            and "logical_observable_count" in case_summary
        ):
            row_run_metadata["logical_observable_count"] = _require_int(
                case_summary,
                "logical_observable_count",
                results_path,
                line_number,
                "case_summary",
            )
        if (
            "decoder_impl" not in row_run_metadata
            and isinstance(expected_impl_key, str)
            and expected_impl_key
            and (
                row_run_metadata
                or require_observable_run_metadata
                or expected_observable_run_metadata is not None
            )
        ):
            row_run_metadata["decoder_impl"] = expected_impl_key
        if (
            row_run_metadata
            or require_observable_run_metadata
            or expected_observable_run_metadata is not None
        ):
            row_run_metadata = validate_observable_run_metadata(
                row_run_metadata,
                context=f"{results_path}:{line_number}: run metadata",
                expected=expected_observable_run_metadata,
            )
        result_only_decoder_param_keys = _result_only_decoder_param_keys(
            impl_key=expected_impl_key
        )
        row_decoder_parameters = canonical_decoder_parameters(
            {
                key: value
                for key, value in params.items()
                if key not in GENERIC_RESULT_PARAM_KEYS
                and key not in RESULT_METADATA_PARAM_KEYS
                and key not in result_only_decoder_param_keys
            },
            impl_key=expected_impl_key,
        )
        if row_decoder_parameters != expected_decoder_parameters:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: unexpected decoder parameters"
            )
        if decoder_parameters is None:
            decoder_parameters = row_decoder_parameters
        elif row_decoder_parameters != decoder_parameters:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: inconsistent decoder parameters"
            )
        if run_metadata is None:
            run_metadata = row_run_metadata
        elif row_run_metadata != run_metadata:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: inconsistent run metadata"
            )

        shots = _require_int(
            metrics,
            "shots_used",
            results_path,
            line_number,
            "metric",
            require_numeric=True,
            allow_integral_float=True,
        )
        errors = _require_int(
            metrics,
            "logical_errors",
            results_path,
            line_number,
            "metric",
            require_numeric=True,
            allow_integral_float=True,
        )
        if shots < 1:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: invalid shots: {shots}"
            )
        if errors < 0:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: invalid errors: {errors}"
            )
        if errors > shots:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: errors exceed shots: {errors} > {shots}"
            )
        ci_low, ci_high = wilson_interval(errors=errors, shots=shots)
        decode_us_per_shot = _optional_metric_number(
            metrics, "decode_us_per_shot", results_path, line_number
        )
        if decode_us_per_shot is not None and decode_us_per_shot < 0:
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: invalid decode_us_per_shot"
            )
        seconds = 0.0
        if decode_us_per_shot is not None:
            seconds = decode_us_per_shot * shots / 1_000_000
        logical_error_rate = _optional_metric_number(
            metrics, "logical_error_rate", results_path, line_number
        )
        if logical_error_rate is not None and not isclose(
            logical_error_rate, errors / shots, rel_tol=1e-9, abs_tol=1e-12
        ):
            raise SearchIntegrityError(
                f"{results_path}:{line_number}: logical_error_rate does not match counts"
            )
        points.append(
            {
                "p": p,
                "rounds": rounds,
                "shots": shots,
                "errors": errors,
                "ler": errors / shots,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "seconds": seconds,
            }
        )

    if not points:
        raise SearchIntegrityError(f"{results_path}: no result records")

    expected_set = set(expected_p_values)
    actual_set = {point["p"] for point in points}
    if actual_set != expected_set:
        missing = sorted(expected_set - actual_set)
        raise SearchIntegrityError(f"{results_path}: missing p results: {missing}")
    return ParsedResults(
        points=sorted(points, key=lambda point: point["p"]),
        decoder_parameters=decoder_parameters or {},
        run_metadata=run_metadata or {},
    )


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _collection_positive_int(collection: dict[str, Any], key: str) -> int:
    value = collection.get(key)
    if key == "batch_size" and value is None:
        value = RSINTER_DEFAULT_BATCH_SIZE
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise SearchIntegrityError(f"invalid rsinter {key}: {value}")
    return value


def _collection_for_decoder(collection: dict[str, Any], decoder_id: str) -> dict[str, int]:
    overrides = collection.get("decoder_overrides", {})
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise SearchIntegrityError("invalid rsinter decoder_overrides")
    decoder_override = overrides.get(decoder_id, {})
    if decoder_override is None:
        decoder_override = {}
    if not isinstance(decoder_override, dict):
        raise SearchIntegrityError(f"invalid rsinter decoder override: {decoder_id}")
    merged = {**collection, **decoder_override}
    return {
        "max_shots": _collection_positive_int(merged, "max_shots"),
        "max_errors": _collection_positive_int(merged, "max_errors"),
        "batch_size": _collection_positive_int(merged, "batch_size"),
    }


def _p_list_text(p_values: list[float]) -> str:
    return ", ".join(str(value) for value in p_values)


def _benchmark_header_lines(task: dict) -> list[str]:
    benchmark_name = f"autoqec-{task['id']}"
    return [
        f"name = {_toml_string(benchmark_name)}",
        "version = 1",
        'mode = "independent"',
        "",
    ]


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if not isfinite(value):
            raise SearchIntegrityError(f"invalid rsinter parameter: {value}")
        return repr(value)
    if isinstance(value, str):
        return _toml_string(value)
    raise SearchIntegrityError(f"unsupported rsinter parameter value: {value!r}")


def _plot_lines(task: dict, *, css: bool) -> list[str]:
    plot_title = f"AutoQEC {task['id']}"
    group_by = '["runner", "params.code_id"]' if css else '["runner", "params.distance"]'
    label_template = "{runner} {params.code_id}" if css else "{runner} d={params.distance}"
    return [
        "[plot]",
        f"title = {_toml_string(plot_title)}",
        "[plot.x]",
        'field = "params.p"',
        'scale = "log"',
        'label = "Physical Error Rate"',
        "[plot.series]",
        f"group_by = {group_by}",
        f"label_template = {_toml_string(label_template)}",
        "[[plot.panel]]",
        'metric = "metrics.logical_error_rate"',
        'scale = "log"',
        'label = "Logical Error Rate"',
        "",
    ]


def _require_dense_binary_matrix(payload: dict[str, Any]) -> list[list[int]]:
    if payload.get("format") != "dense_binary_matrix":
        raise SearchIntegrityError("CSS matrix format must be dense_binary_matrix")
    n_rows = payload.get("n_rows")
    n_cols = payload.get("n_cols")
    data = payload.get("data")
    if type(n_rows) is not int or n_rows < 0:
        raise SearchIntegrityError("CSS matrix n_rows must be a nonnegative integer")
    if type(n_cols) is not int or n_cols < 0:
        raise SearchIntegrityError("CSS matrix n_cols must be a nonnegative integer")
    if not isinstance(data, list) or len(data) != n_rows:
        raise SearchIntegrityError("CSS matrix data row count does not match n_rows")
    rows: list[list[int]] = []
    for row_index, row in enumerate(data):
        if not isinstance(row, list) or len(row) != n_cols:
            raise SearchIntegrityError(f"CSS matrix row width mismatch at row {row_index}")
        converted_row: list[int] = []
        for col_index, value in enumerate(row):
            if type(value) is not int or value not in (0, 1):
                raise SearchIntegrityError(
                    f"CSS matrix entries must be binary at row {row_index}, col {col_index}"
                )
            converted_row.append(int(value))
        rows.append(converted_row)
    return rows


def write_css_matrix_wrapper(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = _require_dense_binary_matrix(payload)
    output_path.write_text(
        json.dumps({"format": "dense", "rows": rows}, indent=2, sort_keys=True) + "\n"
    )


def write_css_observables_wrapper(path: str | Path, payload: dict[str, Any]) -> None:
    if payload.get("format") != "sparse_rows":
        raise SearchIntegrityError("CSS observables format must be sparse_rows")
    num_cols = payload.get("num_cols")
    rows = payload.get("rows")
    if type(num_cols) is not int or num_cols <= 0:
        raise SearchIntegrityError("CSS observables num_cols must be a positive integer")
    if not isinstance(rows, list) or not rows:
        raise SearchIntegrityError("CSS observables rows must be a nonempty list")
    normalized_rows: list[list[int]] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, list):
            raise SearchIntegrityError(f"CSS observables row {row_index} must be a list")
        normalized_row: list[int] = []
        previous = -1
        for col in row:
            if type(col) is not int or col < 0 or col >= num_cols:
                raise SearchIntegrityError(
                    f"CSS observables row {row_index} has invalid column"
                )
            if col <= previous:
                raise SearchIntegrityError(
                    f"CSS observables row {row_index} columns must be strictly increasing"
                )
            previous = col
            normalized_row.append(col)
        normalized_rows.append(normalized_row)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {"format": "sparse_rows", "num_cols": num_cols, "rows": normalized_rows},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _basis_for_task(task: dict) -> str:
    css_memory = task.get("css_memory")
    if isinstance(css_memory, dict) and css_memory.get("basis") in {"x", "z"}:
        return str(css_memory["basis"])
    observable = task.get("observable")
    if observable == "logical_x":
        return "x"
    if observable == "logical_z":
        return "z"
    raise SearchIntegrityError(f"unsupported task observable for CSS eval: {observable}")


def css_observables_policy(task: dict) -> str | None:
    css_memory = task.get("css_memory")
    policy = css_memory.get("observables") if isinstance(css_memory, dict) else None
    if policy is None:
        return None
    if policy not in {"required", "optional"}:
        raise SearchIntegrityError(f"invalid CSS observables policy: {policy}")
    return str(policy)


def task_requires_explicit_css_observables(task: dict) -> bool:
    return css_observables_policy(task) == "required"


def expected_explicit_observable_run_metadata(
    *,
    task: dict,
    decoder: dict[str, Any],
    basis: str | None,
    observable_count: int,
) -> dict[str, object]:
    if basis not in {"x", "z"}:
        raise SearchIntegrityError(f"invalid CSS observable basis: {basis}")
    if type(observable_count) is not int or observable_count <= 0:
        raise SearchIntegrityError("explicit CSS observables rows must be nonempty")
    css_memory = task.get("css_memory")
    seed = css_memory.get("seed") if isinstance(css_memory, dict) else None
    if type(seed) is not int or seed < 0:
        raise SearchIntegrityError(
            f"task {task['id']} explicit CSS observables require css_memory.seed"
        )
    try:
        canonical_decoder = canonical_decoder_config(decoder)
    except DecoderParameterError as exc:
        raise SearchIntegrityError(str(exc)) from exc
    decoder_impl = canonical_decoder.get("impl_key")
    if not isinstance(decoder_impl, str) or not decoder_impl:
        raise SearchIntegrityError(
            f"task {task['id']} explicit CSS observables require decoder impl_key"
        )
    return {
        "decoder_impl": decoder_impl,
        "logical_failure_aggregation": LOGICAL_FAILURE_AGGREGATION_ANY_LOGICAL,
        "logical_observable_source": "explicit",
        "logical_observable_basis": basis,
        "logical_observable_count": observable_count,
        "seed": seed,
    }


def expected_observable_run_metadata_for_completed_manifest(
    payload: dict,
) -> dict[str, object] | None:
    if (
        payload.get("candidate_id") == "bivariate-bicycle-code-m6-n6"
        and payload.get("task_id") == "bb-css-memory-x-cdep-v1"
    ):
        return dict(BB72_EXPLICIT_OBSERVABLE_RUN_METADATA)
    return None


def build_completed_manifest(
    *,
    campaign_id: str,
    run_id: str,
    candidate_id: str,
    task_id: str,
    decoder_id: str,
    created_at: str,
    tool_revisions: dict[str, str],
    points: list[dict],
    decoder_parameters: dict[str, Any] | None = None,
    run_metadata: dict[str, Any] | None = None,
    require_observable_run_metadata: bool = False,
    expected_observable_run_metadata: dict[str, Any] | None = None,
) -> dict:
    manifest = {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "decoder_id": decoder_id,
        "decoder_parameters": canonical_decoder_parameters(
            dict(decoder_parameters or {})
        ),
        "status": "completed",
        "created_at": created_at,
        "tool_revisions": tool_revisions,
        "points": points,
    }
    if (
        run_metadata
        or require_observable_run_metadata
        or expected_observable_run_metadata is not None
    ):
        manifest["run_metadata"] = validate_observable_run_metadata(
            run_metadata,
            expected=expected_observable_run_metadata,
        )
    return manifest


def write_spec_toml(
    spec_path: str | Path,
    *,
    task: dict,
    decoders: dict[str, dict],
    selected_decoder_ids: list[str],
    distance: int,
    rounds: int,
    p_values: list[float],
) -> None:
    write_surface_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=selected_decoder_ids,
        distance=distance,
        rounds=rounds,
        p_values=p_values,
    )


def write_surface_spec_toml(
    spec_path: str | Path,
    *,
    task: dict,
    decoders: dict[str, dict],
    selected_decoder_ids: list[str],
    distance: int,
    rounds: int,
    p_values: list[float],
) -> None:
    output_path = Path(spec_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    p_list = _p_list_text(p_values)
    collection = task["collection"]
    _collection_positive_int(collection, "batch_size")
    input_type = task.get("input_type")
    if not isinstance(input_type, str) or not input_type:
        raise SearchIntegrityError("task input_type must be a nonempty string")

    lines = _benchmark_header_lines(task)
    for decoder_id in selected_decoder_ids:
        try:
            decoder = canonical_decoder_config(decoders[decoder_id])
        except DecoderParameterError as exc:
            raise SearchIntegrityError(str(exc)) from exc
        runner_collection = _collection_for_decoder(collection, decoder_id)
        lines.extend(
            [
                "[[runner]]",
                f"name = {_toml_string(decoder_id)}",
                f"language = {_toml_string(decoder.get('language', 'rust'))}",
                f"impl_key = {_toml_string(decoder['impl_key'])}",
                "[runner.params]",
                f"distance = [{distance}]",
                f"rounds = [{rounds}]",
                f"p = [{p_list}]",
                f'max_shots = {runner_collection["max_shots"]}',
                f'max_errors = {runner_collection["max_errors"]}',
                f'batch_size = {runner_collection["batch_size"]}',
                f"input_type = {_toml_string(input_type)}",
            ]
        )
        for key, value in decoder["parameters"].items():
            lines.append(f"{key} = {_toml_scalar(value)}")
        lines.append("")
    lines.extend(_plot_lines(task, css=False))
    output_path.write_text("\n".join(lines))


def write_css_spec_toml(
    spec_path: str | Path,
    *,
    task: dict,
    decoders: dict[str, dict],
    selected_decoder_ids: list[str],
    code_id: str,
    hx_path: str | Path,
    hz_path: str | Path,
    observables_path: str | Path | None = None,
    rounds: int,
    p_values: list[float],
    schedule: str = "greedy",
) -> None:
    output_path = Path(spec_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    p_list = _p_list_text(p_values)
    collection = task["collection"]
    basis = _basis_for_task(task)

    lines = _benchmark_header_lines(task)
    for decoder_id in selected_decoder_ids:
        try:
            decoder = canonical_decoder_config(decoders[decoder_id])
        except DecoderParameterError as exc:
            raise SearchIntegrityError(str(exc)) from exc
        runner_collection = _collection_for_decoder(collection, decoder_id)
        lines.extend(
            [
                "[[runner]]",
                f"name = {_toml_string(decoder_id)}",
                f"language = {_toml_string(decoder.get('language', 'rust'))}",
                f"impl_key = {_toml_string(decoder['impl_key'])}",
                "[runner.params]",
                'input_type = "css"',
                f"code_id = {_toml_string(code_id)}",
                f"hx = {_toml_string(Path(hx_path).as_posix())}",
                f"hz = {_toml_string(Path(hz_path).as_posix())}",
                *(
                    [
                        f"observables = {_toml_string(Path(observables_path).as_posix())}"
                    ]
                    if observables_path is not None
                    else []
                ),
                f"basis = {_toml_string(basis)}",
                f"schedule = {_toml_string(schedule)}",
                f"rounds = [{rounds}]",
                f"p = [{p_list}]",
                f'max_shots = {runner_collection["max_shots"]}',
                f'max_errors = {runner_collection["max_errors"]}',
                f'batch_size = {runner_collection["batch_size"]}',
            ]
        )
        css_memory = task.get("css_memory")
        seed = css_memory.get("seed") if isinstance(css_memory, dict) else None
        if seed is not None:
            if type(seed) is not int or seed < 0:
                raise SearchIntegrityError(f"invalid CSS memory seed: {seed}")
            lines.append(f"seed = {seed}")
        for key, value in decoder["parameters"].items():
            lines.append(f"{key} = {_toml_scalar(value)}")
        lines.append("")
    lines.extend(_plot_lines(task, css=True))
    output_path.write_text("\n".join(lines))


def require_rsinter() -> tuple[str, str]:
    executable = shutil.which("rsinter")
    if executable is None:
        raise SearchIntegrityError("rsinter not found on PATH")
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SearchIntegrityError("rsinter --version timed out") from exc
    except OSError as exc:
        raise SearchIntegrityError(f"rsinter --version failed: {exc}") from exc
    version_text = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        raise SearchIntegrityError(
            f"rsinter --version exited {result.returncode}: {version_text}"
        )
    if not version_text:
        raise SearchIntegrityError("rsinter --version returned empty output")
    return executable, version_text


def _requires_general_css_support(message: str) -> bool:
    lowered = message.lower()
    css_markers = ("input_type", "css", "hx", "hz", "basis")
    old_backend_markers = ("unknown field", "unknown variant", "unknown input", "invalid type")
    return any(marker in lowered for marker in css_markers) and any(
        marker in lowered for marker in old_backend_markers
    )


def _rsinter_failure_message(
    result: subprocess.CompletedProcess[str],
    *,
    requires_general_css_support: bool = False,
) -> str:
    combined = "\n".join(part.strip() for part in (result.stderr, result.stdout) if part.strip())
    if requires_general_css_support and _requires_general_css_support(combined):
        return (
            "upstream rstim general CSS support from #46 / #51 is required: "
            f"{combined}"
        )
    return combined


def run_rsinter(
    spec_path: str | Path,
    out_dir: str | Path,
    *,
    executable: str,
    timeout_seconds: int = RSINTER_RUN_TIMEOUT_SECONDS,
    requires_general_css_support: bool = False,
) -> None:
    try:
        result = subprocess.run(
            [
                executable,
                "bench",
                "run",
                "--spec",
                str(spec_path),
                "--language",
                "rust",
                "--out",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SearchIntegrityError(
            f"rsinter bench run timed out after {timeout_seconds}s"
        ) from exc
    except OSError as exc:
        raise SearchIntegrityError(f"rsinter bench run failed: {exc}") from exc
    if result.returncode != 0:
        failure_message = _rsinter_failure_message(
            result,
            requires_general_css_support=requires_general_css_support,
        )
        raise SearchIntegrityError(
            f"rsinter bench run exited {result.returncode}: {failure_message}"
        )
