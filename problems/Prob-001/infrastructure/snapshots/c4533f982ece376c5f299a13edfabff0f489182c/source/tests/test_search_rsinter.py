from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tomllib

import pytest

from autoqec_search import rsinter as rsinter_module
from autoqec_search.load import SearchIntegrityError
from autoqec_search.rsinter import (
    build_completed_manifest,
    parse_decoder_filter,
    parse_p_filter,
    parse_results_jsonl,
    require_rsinter,
    rounds_for_task,
    run_rsinter,
    validate_selected_decoders,
    validate_selected_p_values,
    wilson_interval,
    write_css_matrix_wrapper,
    write_css_spec_toml,
    write_spec_toml,
)


def _result_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "benchmark": "autoqec-rotated-memory-x-cdep-v1",
        "runner": "rmatching-default-v1",
        "language": "rust",
        "status": "ok",
        "params": {"distance": 3, "rounds": 3, "p": 0.005},
        "case_summary": {"num_dets": 8, "num_obs": 1},
        "metrics": {
            "shots_used": 1000,
            "logical_errors": 5,
            "logical_error_rate": 0.005,
            "decode_us_per_shot": 1.25,
        },
        "artifacts": {},
        "error": None,
    }
    missing = object()
    for key in ("params", "metrics"):
        value = overrides.pop(key, missing)
        if value is missing:
            continue
        if isinstance(value, dict) and isinstance(record[key], dict):
            record[key] = {**record[key], **value}
        else:
            record[key] = value
    record.update(overrides)
    return record


def test_parse_decoder_filter_accepts_repeated_and_comma_separated_values() -> None:
    assert parse_decoder_filter(["rmatching-default-v1,rbposd-default-v1"]) == [
        "rmatching-default-v1",
        "rbposd-default-v1",
    ]
    assert parse_decoder_filter(["rmatching-default-v1", "rbposd-default-v1"]) == [
        "rmatching-default-v1",
        "rbposd-default-v1",
    ]


def test_parse_decoder_filter_rejects_duplicate_values() -> None:
    with pytest.raises(SearchIntegrityError, match="duplicate decoder filter"):
        parse_decoder_filter(
            ["rmatching-default-v1,rbposd-default-v1", "rmatching-default-v1"]
        )


def test_decoder_schema_accepts_bb72_paper_rbposd_parameters() -> None:
    from jsonschema import Draft202012Validator

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "benchmarks" / "schemas" / "decoder-config.schema.json").read_text()
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        {
            "id": "rbposd-bb72-osd1-v1",
            "title": "BB72 BP+OSD OSD1 via rsinter",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {
                "bp_algorithm": "min_sum",
                "bp_iters": 50,
                "early_stop": True,
                "osd_method": "combination_sweep",
                "osd_order": 1,
            },
            "execution_status": "real",
        }
    )


def test_parse_decoder_filter_rejects_empty_explicit_values() -> None:
    with pytest.raises(SearchIntegrityError, match="decoder filter is empty"):
        parse_decoder_filter([""])


def test_validate_selected_decoders_rejects_duplicate_values() -> None:
    suite = {"decoder_ids": ["rmatching-default-v1", "rbposd-default-v1"]}

    with pytest.raises(SearchIntegrityError, match="duplicate decoder filter"):
        validate_selected_decoders(
            suite,
            ["rmatching-default-v1", "rbposd-default-v1", "rmatching-default-v1"],
        )


def test_parse_p_filter_accepts_repeated_and_comma_separated_values() -> None:
    assert parse_p_filter(["0.005,0.01"]) == [0.005, 0.01]
    assert parse_p_filter(["0.005", "0.01"]) == [0.005, 0.01]


def test_parse_p_filter_rejects_invalid_numbers() -> None:
    with pytest.raises(SearchIntegrityError, match="invalid p filter"):
        parse_p_filter(["0.005,not-a-number"])


def test_parse_p_filter_rejects_empty_explicit_values() -> None:
    with pytest.raises(SearchIntegrityError, match="p filter is empty"):
        parse_p_filter([""])


@pytest.mark.parametrize("value", ["nan", "inf", "-0.1", "0", "1", "1.1"])
def test_parse_p_filter_rejects_non_finite_and_out_of_domain_values(
    value: str,
) -> None:
    with pytest.raises(SearchIntegrityError, match="p must satisfy 0 < p < 1"):
        parse_p_filter([value])


def test_parse_p_filter_rejects_duplicate_values() -> None:
    with pytest.raises(SearchIntegrityError, match="duplicate p filter"):
        parse_p_filter(["0.005,0.01", "0.005"])


def test_validate_selected_p_values_rejects_duplicate_values() -> None:
    task = {"p_list": [0.005, 0.01]}

    with pytest.raises(SearchIntegrityError, match="duplicate p filter"):
        validate_selected_p_values(task, [0.005, 0.01, 0.005])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 0, 1, 1.1])
def test_validate_selected_p_values_rejects_invalid_task_p_list_values(
    value: float,
) -> None:
    task = {"p_list": [0.005, value]}

    with pytest.raises(SearchIntegrityError, match="p must satisfy 0 < p < 1"):
        validate_selected_p_values(task, None)


def test_rounds_for_distance_scaled_task() -> None:
    task = {
        "rounds_policy": {"kind": "distance-scaled", "multiplier": 1, "minimum": 3}
    }

    assert rounds_for_task(task, distance=3) == 3
    assert rounds_for_task(task, distance=5) == 5


def test_rounds_for_distance_scaled_task_reports_upper_bound_context() -> None:
    task = {
        "rounds_policy": {"kind": "distance-scaled", "multiplier": 1, "minimum": 3}
    }

    with pytest.raises(
        SearchIntegrityError,
        match=(
            "distance-scaled rounds require exact distance "
            r".*method=random-window-upper-bound.*bound_type=upper.*upper_bound=7"
        ),
    ):
        rounds_for_task(
            task,
            distance=None,
            distance_context={
                "method": "random-window-upper-bound",
                "bound_type": "upper",
                "upper_bound": 7,
            },
        )


def test_wilson_interval_matches_catalog_fixture_band() -> None:
    low, high = wilson_interval(errors=1000, shots=76533)

    assert low == pytest.approx(0.012285801778695208)
    assert high == pytest.approx(0.013895597376401364)


def test_parse_results_jsonl_builds_points(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(json.dumps(_result_record(), sort_keys=True) + "\n")

    points = parse_results_jsonl(
        path,
        expected_decoder_id="rmatching-default-v1",
        expected_task_id="rotated-memory-x-cdep-v1",
        expected_distance=3,
        expected_p_values=[0.005],
    )

    assert points == [
        {
            "p": 0.005,
            "rounds": 3,
            "shots": 1000,
            "errors": 5,
            "ler": 0.005,
            "ci_low": pytest.approx(0.00214, abs=0.00001),
            "ci_high": pytest.approx(0.01165, abs=0.00001),
            "seconds": 0.00125,
        }
    ]


def test_parse_results_jsonl_accepts_integral_float_metrics(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _result_record(
                metrics={
                    "shots_used": 1000.0,
                    "logical_errors": 5.0,
                    "logical_error_rate": 0.005,
                }
            ),
            sort_keys=True,
        )
        + "\n"
    )

    points = parse_results_jsonl(
        path,
        expected_decoder_id="rmatching-default-v1",
        expected_task_id="rotated-memory-x-cdep-v1",
        expected_distance=3,
        expected_p_values=[0.005],
    )

    assert points[0]["shots"] == 1000
    assert points[0]["errors"] == 5


def test_parse_results_jsonl_rejects_errors_exceeding_shots(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(_result_record(metrics={"logical_errors": 1001}), sort_keys=True)
        + "\n"
    )

    with pytest.raises(
        SearchIntegrityError, match="results.jsonl:1: errors exceed shots: 1001 > 1000"
    ):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_distance=3,
            expected_p_values=[0.005],
        )


def test_parse_results_jsonl_rejects_zero_shots_with_record_context(
    tmp_path: Path,
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(_result_record(metrics={"shots_used": 0}), sort_keys=True) + "\n"
    )

    with pytest.raises(
        SearchIntegrityError, match="results.jsonl:1: invalid shots: 0"
    ):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_distance=3,
            expected_p_values=[0.005],
        )


def test_parse_results_jsonl_rejects_duplicate_p_records(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    record = _result_record()
    path.write_text(
        "\n".join(
            [
                json.dumps(record, sort_keys=True),
                json.dumps(record, sort_keys=True),
            ]
        )
        + "\n"
    )

    with pytest.raises(SearchIntegrityError, match="line 2: duplicate p"):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_distance=3,
            expected_p_values=[0.005],
        )


def test_parse_results_jsonl_rejects_non_object_records(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text("[]\n")

    with pytest.raises(SearchIntegrityError, match="result record must be an object"):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_distance=3,
            expected_p_values=[0.005],
        )


@pytest.mark.parametrize("decode_us_per_shot", ["NaN", "Infinity"])
def test_parse_results_jsonl_rejects_non_finite_decode_time_constants(
    tmp_path: Path, decode_us_per_shot: str
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        "{"
        '"benchmark": "autoqec-rotated-memory-x-cdep-v1", '
        '"runner": "rmatching-default-v1", '
        '"language": "rust", '
        '"status": "ok", '
        '"params": {"distance": 3, "rounds": 3, "p": 0.005}, '
        '"case_summary": {"num_dets": 8, "num_obs": 1}, '
        '"metrics": {'
        '"shots_used": 1000, '
        '"logical_errors": 5, '
        '"logical_error_rate": 0.005, '
        f'"decode_us_per_shot": {decode_us_per_shot}'
        "}, "
        '"artifacts": {}, '
        '"error": null'
        "}\n"
    )

    with pytest.raises(
        SearchIntegrityError, match="invalid JSON constant|invalid decode_us_per_shot"
    ):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_distance=3,
            expected_p_values=[0.005],
        )


@pytest.mark.parametrize(
    ("contents", "match"),
    [
        ("not-json\n", "invalid JSONL record"),
        ("", "no result records"),
    ],
)
def test_parse_results_jsonl_rejects_malformed_or_empty_output(
    tmp_path: Path, contents: str, match: str
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(contents)

    with pytest.raises(SearchIntegrityError, match=match):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_distance=3,
            expected_p_values=[0.005],
        )


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"metrics": {"shots_used": "1000"}}, "missing numeric metric shots_used"),
        ({"metrics": {"logical_errors": None}}, "missing numeric metric logical_errors"),
        ({"runner": "unexpected"}, "unexpected runner"),
        ({"status": "failed"}, "rsinter row status is not ok"),
        ({"params": None}, "missing params object"),
        ({"metrics": None}, "missing metrics object"),
        ({"params": {"p": 0.01}}, "unexpected p"),
    ],
)
def test_parse_results_jsonl_rejects_invalid_records(
    tmp_path: Path, overrides: dict[str, object], match: str
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(json.dumps(_result_record(**overrides), sort_keys=True) + "\n")

    with pytest.raises(SearchIntegrityError, match=match):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_distance=3,
            expected_p_values=[0.005],
        )


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"params": {"rounds": 1.9}}, "missing integer param rounds"),
        ({"metrics": {"shots_used": 1000.7}}, "missing integer metric shots_used"),
        ({"metrics": {"logical_errors": 2.8}}, "missing integer metric logical_errors"),
        ({"params": {"rounds": 0}}, "invalid rounds"),
        ({"params": {"distance": "3"}}, "missing integer param distance"),
        ({"params": {"distance": 5}}, "unexpected distance"),
        ({"metrics": {"decode_us_per_shot": -1}}, "invalid decode_us_per_shot"),
        (
            {"metrics": {"logical_error_rate": 0.25}},
            "logical_error_rate does not match counts",
        ),
    ],
)
def test_parse_results_jsonl_rejects_invalid_integer_and_timing_fields(
    tmp_path: Path, overrides: dict[str, object], match: str
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(json.dumps(_result_record(**overrides), sort_keys=True) + "\n")

    with pytest.raises(SearchIntegrityError, match=match):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_distance=3,
            expected_p_values=[0.005],
        )


def test_build_completed_manifest_returns_status_completed_and_points() -> None:
    points = [
        {
            "p": 0.005,
            "rounds": 3,
            "shots": 1000,
            "errors": 5,
            "ler": 0.005,
            "ci_low": 0.00214,
            "ci_high": 0.01165,
            "seconds": 1.25,
        }
    ]

    manifest = build_completed_manifest(
        campaign_id="rotated-surface-baseline",
        run_id="test-eval",
        candidate_id="rotated-surface-d3-example",
        task_id="rotated-memory-x-cdep-v1",
        decoder_id="rmatching-default-v1",
        created_at="2026-06-13T10:20:39Z",
        tool_revisions={
            "rsinter": "rsinter git main abc123",
            "autoqec_search": "0.1.0",
        },
        points=points,
    )

    assert manifest["status"] == "completed"
    assert manifest["points"] == points


def test_build_completed_manifest_requires_observable_run_metadata() -> None:
    with pytest.raises(SearchIntegrityError, match="missing run metadata"):
        build_completed_manifest(
            campaign_id="bb72-qldpc-campaign",
            run_id="bb72-observables",
            candidate_id="bivariate-bicycle-code-m6-n6",
            task_id="bb-css-memory-x-cdep-v1",
            decoder_id="rbposd-bb72-osd1-v1",
            created_at="2026-06-18T00:00:00Z",
            tool_revisions={"autoqec_search": "0.1.0", "rsinter": "fake"},
            points=[
                {
                    "p": 0.003,
                    "rounds": 3,
                    "shots": 64,
                    "errors": 0,
                    "ler": 0.0,
                    "ci_low": 0.0,
                    "ci_high": 0.1,
                    "seconds": 0.0,
                }
            ],
            require_observable_run_metadata=True,
        )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("seed", 54321),
        ("decoder_impl", "wrong-impl"),
        ("logical_failure_aggregation", "wrong-aggregation"),
    ],
)
def test_build_completed_manifest_rejects_unexpected_observable_run_metadata(
    field: str,
    bad_value: object,
) -> None:
    run_metadata = {
        "decoder_impl": "rbposd",
        "logical_failure_aggregation": "any_logical",
        "logical_observable_basis": "x",
        "logical_observable_count": 12,
        "logical_observable_source": "explicit",
        "seed": 12345,
    }
    run_metadata[field] = bad_value

    with pytest.raises(SearchIntegrityError, match=f"unexpected {field}"):
        build_completed_manifest(
            campaign_id="bb72-qldpc-campaign",
            run_id="bb72-observables",
            candidate_id="bivariate-bicycle-code-m6-n6",
            task_id="bb-css-memory-x-cdep-v1",
            decoder_id="rbposd-bb72-osd1-v1",
            created_at="2026-06-18T00:00:00Z",
            tool_revisions={"autoqec_search": "0.1.0", "rsinter": "fake"},
            points=[
                {
                    "p": 0.003,
                    "rounds": 3,
                    "shots": 64,
                    "errors": 0,
                    "ler": 0.0,
                    "ci_low": 0.0,
                    "ci_high": 0.1,
                    "seconds": 0.0,
                }
            ],
            run_metadata=run_metadata,
            expected_observable_run_metadata={
                "decoder_impl": "rbposd",
                "logical_failure_aggregation": "any_logical",
                "logical_observable_source": "explicit",
                "logical_observable_basis": "x",
                "logical_observable_count": 12,
                "seed": 12345,
            },
        )


def test_write_spec_toml_writes_current_rsinter_benchmark_spec(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "rotated-memory-x-cdep-v1",
        "input_type": "memory-z",
        "p_list": [0.005],
        "collection": {"max_shots": 1000, "max_errors": 50},
    }
    decoders = {
        "rmatching-default-v1": {
            "id": "rmatching-default-v1",
            "impl_key": "rmatching",
            "language": "rust",
        }
    }

    write_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rmatching-default-v1"],
        distance=3,
        rounds=3,
        p_values=[0.005],
    )

    parsed = tomllib.loads(spec_path.read_text())
    assert parsed["name"] == "autoqec-rotated-memory-x-cdep-v1"
    assert parsed["version"] == 1
    assert parsed["mode"] == "independent"
    assert parsed["plot"]["title"] == "AutoQEC rotated-memory-x-cdep-v1"
    assert parsed["plot"]["x"] == {
        "field": "params.p",
        "scale": "log",
        "label": "Physical Error Rate",
    }
    assert parsed["plot"]["series"] == {
        "group_by": ["runner", "params.distance"],
        "label_template": "{runner} d={params.distance}",
    }
    assert parsed["plot"]["panel"] == [
        {
            "metric": "metrics.logical_error_rate",
            "scale": "log",
            "label": "Logical Error Rate",
        }
    ]
    assert parsed["runner"] == [
        {
            "name": "rmatching-default-v1",
            "language": "rust",
            "impl_key": "rmatching",
            "params": {
                "distance": [3],
                "rounds": [3],
                "p": [0.005],
                "max_shots": 1000,
                "max_errors": 50,
                "batch_size": 256,
                "input_type": "memory-z",
            },
        }
    ]


def test_write_spec_toml_escapes_scalar_strings_as_valid_toml(tmp_path: Path) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    decoder_id = 'rmatching "quoted" \\ id\nnext'
    impl_key = 'impl "key" \\ value\nnext'
    task_id = 'task "id" \\ value\nnext'
    language = 'rust "lang" \\ value\nnext'
    task = {
        "id": task_id,
        "input_type": "memory-z",
        "p_list": [0.005],
        "collection": {"max_shots": 1000, "max_errors": 50, "batch_size": 16},
    }
    decoders = {
        decoder_id: {
            "id": decoder_id,
            "impl_key": impl_key,
            "language": language,
        }
    }

    write_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=[decoder_id],
        distance=3,
        rounds=3,
        p_values=[0.005],
    )

    parsed = tomllib.loads(spec_path.read_text())
    runner = parsed["runner"][0]
    assert parsed["name"] == f"autoqec-{task_id}"
    assert runner["name"] == decoder_id
    assert runner["impl_key"] == impl_key
    assert runner["language"] == language
    assert runner["params"]["batch_size"] == 16


@pytest.mark.parametrize("batch_size", [0, -1])
def test_write_spec_toml_rejects_invalid_batch_size(
    tmp_path: Path,
    batch_size: int,
) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "rotated-memory-x-cdep-v1",
        "p_list": [0.005],
        "collection": {
            "max_shots": 1000,
            "max_errors": 50,
            "batch_size": batch_size,
        },
    }
    decoders = {
        "rmatching-default-v1": {
            "id": "rmatching-default-v1",
            "impl_key": "rmatching",
            "language": "rust",
        }
    }

    with pytest.raises(
        SearchIntegrityError, match=f"invalid rsinter batch_size: {batch_size}"
    ):
        write_spec_toml(
            spec_path,
            task=task,
            decoders=decoders,
            selected_decoder_ids=["rmatching-default-v1"],
            distance=3,
            rounds=3,
            p_values=[0.005],
        )


def test_write_css_matrix_wrapper_converts_autoqec_dense_matrix(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "rsinter" / "input" / "hx.css.json"
    source = {
        "format": "dense_binary_matrix",
        "n_rows": 2,
        "n_cols": 3,
        "data": [[1, 0, 1], [0, 1, 0]],
    }

    write_css_matrix_wrapper(output_path, source)

    assert json.loads(output_path.read_text()) == {
        "format": "dense",
        "rows": [[1, 0, 1], [0, 1, 0]],
    }


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"format": "dense", "n_rows": 1, "n_cols": 1, "data": [[1]]}, "format"),
        (
            {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 2, "data": [[1]]},
            "row width",
        ),
        (
            {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 1, "data": [[2]]},
            "binary",
        ),
        (
            {
                "format": "dense_binary_matrix",
                "n_rows": 1,
                "n_cols": 1,
                "data": [[True]],
            },
            "binary",
        ),
        (
            {
                "format": "dense_binary_matrix",
                "n_rows": 1,
                "n_cols": 1,
                "data": [[False]],
            },
            "binary",
        ),
        (
            {
                "format": "dense_binary_matrix",
                "n_rows": 1,
                "n_cols": 1,
                "data": [[1.0]],
            },
            "binary",
        ),
        (
            {
                "format": "dense_binary_matrix",
                "n_rows": 1,
                "n_cols": 1,
                "data": [[0.0]],
            },
            "binary",
        ),
    ],
)
def test_write_css_matrix_wrapper_rejects_invalid_payloads(
    tmp_path: Path,
    payload: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(SearchIntegrityError, match=match):
        write_css_matrix_wrapper(tmp_path / "bad.css.json", payload)


def test_write_css_spec_toml_writes_general_css_runner_params(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "rotated-memory-x-cdep-v1",
        "observable": "logical_x",
        "p_list": [0.005],
        "collection": {"max_shots": 100000, "max_errors": 1000},
    }
    decoders = {
        "rmatching-default-v1": {
            "id": "rmatching-default-v1",
            "impl_key": "rmatching",
            "language": "rust",
        }
    }

    write_css_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rmatching-default-v1"],
        code_id="rotated-surface-code",
        hx_path=Path("input/hx.css.json"),
        hz_path=Path("input/hz.css.json"),
        rounds=3,
        p_values=[0.005],
    )

    parsed = tomllib.loads(spec_path.read_text())
    assert parsed["name"] == "autoqec-rotated-memory-x-cdep-v1"
    assert parsed["plot"]["series"] == {
        "group_by": ["runner", "params.code_id"],
        "label_template": "{runner} {params.code_id}",
    }
    assert parsed["runner"] == [
        {
            "name": "rmatching-default-v1",
            "language": "rust",
            "impl_key": "rmatching",
            "params": {
                "input_type": "css",
                "code_id": "rotated-surface-code",
                "hx": "input/hx.css.json",
                "hz": "input/hz.css.json",
                "basis": "x",
                "schedule": "greedy",
                "rounds": [3],
                "p": [0.005],
                "max_shots": 100000,
                "max_errors": 1000,
                "batch_size": 256,
            },
        }
    ]
    assert "distance" not in parsed["runner"][0]["params"]


def test_write_css_spec_toml_maps_logical_z_to_basis_z(tmp_path: Path) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "rotated-memory-z-cdep-v1",
        "observable": "logical_z",
        "p_list": [0.008],
        "collection": {"max_shots": 1000, "max_errors": 50},
    }
    decoders = {
        "rmatching-default-v1": {
            "id": "rmatching-default-v1",
            "impl_key": "rmatching",
            "language": "rust",
        }
    }

    write_css_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rmatching-default-v1"],
        code_id="rotated-surface-code",
        hx_path=Path("input/hx.css.json"),
        hz_path=Path("input/hz.css.json"),
        rounds=9,
        p_values=[0.008],
    )

    assert tomllib.loads(spec_path.read_text())["runner"][0]["params"]["basis"] == "z"


def test_write_css_spec_toml_rejects_unsupported_observable(tmp_path: Path) -> None:
    task = {
        "id": "unsupported-task",
        "observable": "logical_y",
        "p_list": [0.005],
        "collection": {"max_shots": 1000, "max_errors": 50},
    }
    decoders = {
        "rmatching-default-v1": {
            "id": "rmatching-default-v1",
            "impl_key": "rmatching",
            "language": "rust",
        }
    }

    with pytest.raises(SearchIntegrityError, match="unsupported task observable"):
        write_css_spec_toml(
            tmp_path / "spec.toml",
            task=task,
            decoders=decoders,
            selected_decoder_ids=["rmatching-default-v1"],
            code_id="rotated-surface-code",
            hx_path=Path("input/hx.css.json"),
            hz_path=Path("input/hz.css.json"),
            rounds=3,
            p_values=[0.005],
        )


def test_write_css_spec_toml_writes_observables_seed_and_bb72_params(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "observable": "logical_x",
        "p_list": [0.003],
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "required",
        },
    }
    decoders = {
        "rbposd-bb72-osd1-v1": {
            "id": "rbposd-bb72-osd1-v1",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {
                "bp_algorithm": "min_sum",
                "bp_iters": 50,
                "early_stop": True,
                "osd_method": "combination_sweep",
                "osd_order": 1,
            },
        }
    }

    write_css_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rbposd-bb72-osd1-v1"],
        code_id="bivariate-bicycle-code-m6-n6",
        hx_path=Path("input/hx.css.json"),
        hz_path=Path("input/hz.css.json"),
        observables_path=Path("input/observables.css.json"),
        rounds=3,
        p_values=[0.003],
    )

    params = tomllib.loads(spec_path.read_text())["runner"][0]["params"]
    assert params["observables"] == "input/observables.css.json"
    assert params["seed"] == 12345
    assert params["bp_algorithm"] == "min_sum"
    assert params["osd_method"] == "combination_sweep"
    assert "distance" not in params


def test_parse_results_jsonl_accepts_css_rows_without_distance(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    record = _result_record(params={"distance": None})
    del record["params"]["distance"]
    path.write_text(json.dumps(record, sort_keys=True) + "\n")

    points = parse_results_jsonl(
        path,
        expected_decoder_id="rmatching-default-v1",
        expected_task_id="rotated-memory-x-cdep-v1",
        expected_distance=3,
        expected_p_values=[0.005],
    )

    assert points[0]["p"] == 0.005
    assert points[0]["rounds"] == 3


def test_parse_results_jsonl_preserves_bb72_observable_metadata(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _result_record(
                runner="rbposd-bb72-osd1-v1",
                params={
                    "input_type": "css",
                    "code_id": "bivariate-bicycle-code-m6-n6",
                    "hx": "input/hx.css.json",
                    "hz": "input/hz.css.json",
                    "observables": "input/observables.css.json",
                    "basis": "x",
                    "schedule": "greedy",
                    "rounds": 3,
                    "p": 0.003,
                    "seed": 12345,
                    "decoder_impl": "rbposd",
                    "logical_observable_source": "explicit",
                    "logical_observable_basis": "x",
                    "logical_failure_aggregation": "any_logical",
                    "bp_algorithm": "min_sum",
                    "bp_iters": 50,
                    "early_stop": True,
                    "osd_method": "combination_sweep",
                    "osd_order": 1,
                },
                case_summary={
                    "logical_observable_count": 12,
                    "num_dets": 216,
                    "num_obs": 12,
                },
                metrics={
                    "shots_used": 64,
                    "logical_errors": 0,
                    "logical_error_rate": 0.0,
                },
            ),
            sort_keys=True,
        )
        + "\n"
    )

    parsed = parse_results_jsonl(
        path,
        expected_decoder_id="rbposd-bb72-osd1-v1",
        expected_task_id="bb-css-memory-x-cdep-v1",
        expected_distance=None,
        expected_p_values=[0.003],
        expected_decoder_parameters={
            "bp_algorithm": "min_sum",
            "bp_iters": 50,
            "early_stop": True,
            "osd_method": "combination_sweep",
            "osd_order": 1,
        },
        expected_impl_key="rbposd",
    )

    assert parsed.decoder_parameters == {
        "bp_algorithm": "min_sum",
        "bp_iters": 50,
        "early_stop": True,
        "osd_method": "combination_sweep",
        "osd_order": 1,
    }
    assert parsed.run_metadata == {
        "decoder_impl": "rbposd",
        "logical_failure_aggregation": "any_logical",
        "logical_observable_basis": "x",
        "logical_observable_count": 12,
        "logical_observable_source": "explicit",
        "seed": 12345,
    }


def _rbposd_result_only_defaults_record(
    *, extra_params: dict[str, object] | None = None
) -> dict[str, object]:
    params: dict[str, object] = {
        "input_type": "css",
        "code_id": "quantum-tanner-css-memory-x",
        "hx": "input/hx.css.json",
        "hz": "input/hz.css.json",
        "observables": "input/observables.css.json",
        "basis": "x",
        "schedule": "greedy",
        "rounds": 9,
        "p": 0.001,
        "seed": 12345,
        "decoder_impl": "rbposd",
        "logical_observable_source": "explicit",
        "logical_observable_basis": "x",
        "logical_failure_aggregation": "any_logical",
        "logical_observable_count": 4,
        "bp_algorithm": "min_sum",
        "bp_iters": 50,
        "early_stop": True,
        "osd_method": "combination_sweep",
        "osd_order": 10,
        "bp_method": "minimum_sum",
        "bp_schedule": "parallel",
    }
    if extra_params:
        params.update(extra_params)
    return _result_record(
        runner="rbposd-osd10-v1",
        params=params,
        case_summary={"num_dets": 216, "num_obs": 4},
        metrics={
            "shots_used": 64,
            "logical_errors": 0,
            "logical_error_rate": 0.0,
        },
    )


def test_parse_results_jsonl_accepts_rbposd_result_only_defaults(
    tmp_path: Path,
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(_rbposd_result_only_defaults_record(), sort_keys=True) + "\n"
    )

    parsed = parse_results_jsonl(
        path,
        expected_decoder_id="rbposd-osd10-v1",
        expected_task_id="quantum-tanner-css-memory-x-rbposd-p001-v1",
        expected_distance=None,
        expected_p_values=[0.001],
        expected_decoder_parameters={
            "bp_algorithm": "min_sum",
            "bp_iters": 50,
            "early_stop": True,
            "osd_method": "combination_sweep",
            "osd_order": 10,
        },
        expected_impl_key="rbposd",
    )

    assert parsed.decoder_parameters == {
        "bp_algorithm": "min_sum",
        "bp_iters": 50,
        "early_stop": True,
        "osd_method": "combination_sweep",
        "osd_order": 10,
    }
    assert "bp_method" not in parsed.decoder_parameters
    assert "bp_schedule" not in parsed.decoder_parameters
    assert parsed.run_metadata["logical_failure_aggregation"] == "any_logical"
    assert parsed.run_metadata["logical_observable_source"] == "explicit"
    assert parsed.run_metadata["logical_observable_count"] == 4


def test_parse_results_jsonl_rejects_unapproved_rbposd_decoder_param(
    tmp_path: Path,
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _rbposd_result_only_defaults_record(
                extra_params={"mystery_decoder_knob": 1}
            ),
            sort_keys=True,
        )
        + "\n"
    )

    with pytest.raises(
        SearchIntegrityError,
        match="unexpected decoder parameters",
    ):
        parse_results_jsonl(
            path,
            expected_decoder_id="rbposd-osd10-v1",
            expected_task_id="quantum-tanner-css-memory-x-rbposd-p001-v1",
            expected_distance=None,
            expected_p_values=[0.001],
            expected_decoder_parameters={
                "bp_algorithm": "min_sum",
                "bp_iters": 50,
                "early_stop": True,
                "osd_method": "combination_sweep",
                "osd_order": 10,
            },
            expected_impl_key="rbposd",
        )


@pytest.mark.parametrize(
    ("field", "bad_value", "expected_message"),
    [
        ("logical_observable_basis", "z", "logical_observable_basis"),
        ("seed", 54321, "seed"),
        ("logical_observable_count", 11, "logical_observable_count"),
        ("logical_observable_source", "generated", "logical_observable_source"),
        ("decoder_impl", "wrong-impl", "decoder_impl"),
        (
            "logical_failure_aggregation",
            "wrong-aggregation",
            "logical_failure_aggregation",
        ),
    ],
)
def test_parse_results_jsonl_rejects_unexpected_bb72_observable_metadata(
    tmp_path: Path,
    field: str,
    bad_value: object,
    expected_message: str,
) -> None:
    path = tmp_path / "results.jsonl"
    params = {
        "input_type": "css",
        "code_id": "bivariate-bicycle-code-m6-n6",
        "hx": "input/hx.css.json",
        "hz": "input/hz.css.json",
        "observables": "input/observables.css.json",
        "basis": "x",
        "schedule": "greedy",
        "rounds": 3,
        "p": 0.003,
        "seed": 12345,
        "decoder_impl": "rbposd",
        "logical_observable_source": "explicit",
        "logical_observable_basis": "x",
        "logical_failure_aggregation": "any_logical",
        "logical_observable_count": 12,
        "bp_algorithm": "min_sum",
        "bp_iters": 50,
        "early_stop": True,
        "osd_method": "combination_sweep",
        "osd_order": 1,
    }
    params[field] = bad_value
    path.write_text(
        json.dumps(
            _result_record(
                runner="rbposd-bb72-osd1-v1",
                params=params,
                metrics={
                    "shots_used": 64,
                    "logical_errors": 0,
                    "logical_error_rate": 0.0,
                },
            ),
            sort_keys=True,
        )
        + "\n"
    )

    with pytest.raises(SearchIntegrityError, match=expected_message):
        parse_results_jsonl(
            path,
            expected_decoder_id="rbposd-bb72-osd1-v1",
            expected_task_id="bb-css-memory-x-cdep-v1",
            expected_distance=None,
            expected_p_values=[0.003],
            expected_decoder_parameters={
                "bp_algorithm": "min_sum",
                "bp_iters": 50,
                "early_stop": True,
                "osd_method": "combination_sweep",
                "osd_order": 1,
            },
            expected_impl_key="rbposd",
            expected_observable_run_metadata={
                "decoder_impl": "rbposd",
                "logical_failure_aggregation": "any_logical",
                "logical_observable_source": "explicit",
                "logical_observable_basis": "x",
                "logical_observable_count": 12,
                "seed": 12345,
            },
        )


def test_parse_results_jsonl_requires_bb72_observable_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _result_record(
                runner="rbposd-bb72-osd1-v1",
                params={
                    "input_type": "css",
                    "code_id": "bivariate-bicycle-code-m6-n6",
                    "hx": "input/hx.css.json",
                    "hz": "input/hz.css.json",
                    "observables": "input/observables.css.json",
                    "basis": "x",
                    "schedule": "greedy",
                    "rounds": 3,
                    "p": 0.003,
                    "bp_iters": 50,
                    "early_stop": True,
                    "osd_order": 1,
                },
                metrics={
                    "shots_used": 64,
                    "logical_errors": 0,
                    "logical_error_rate": 0.0,
                },
            ),
            sort_keys=True,
        )
        + "\n"
    )

    with pytest.raises(SearchIntegrityError, match="missing run metadata"):
        parse_results_jsonl(
            path,
            expected_decoder_id="rbposd-bb72-osd1-v1",
            expected_task_id="bb-css-memory-x-cdep-v1",
            expected_distance=None,
            expected_p_values=[0.003],
            expected_decoder_parameters={
                "bp_iters": 50,
                "early_stop": True,
                "osd_order": 1,
            },
            expected_impl_key="rbposd",
            require_observable_run_metadata=True,
        )


def test_parse_results_jsonl_rejects_malformed_observable_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _result_record(
                runner="rbposd-bb72-osd1-v1",
                params={
                    "input_type": "css",
                    "code_id": "bivariate-bicycle-code-m6-n6",
                    "hx": "input/hx.css.json",
                    "hz": "input/hz.css.json",
                    "observables": "input/observables.css.json",
                    "basis": "x",
                    "schedule": "greedy",
                    "rounds": 3,
                    "p": 0.003,
                    "seed": "12345",
                    "decoder_impl": "rbposd",
                    "logical_observable_source": "explicit",
                    "logical_observable_basis": "x",
                    "logical_failure_aggregation": "any_logical",
                    "logical_observable_count": 12,
                    "bp_iters": 50,
                    "early_stop": True,
                    "osd_order": 1,
                },
                metrics={
                    "shots_used": 64,
                    "logical_errors": 0,
                    "logical_error_rate": 0.0,
                },
            ),
            sort_keys=True,
        )
        + "\n"
    )

    with pytest.raises(SearchIntegrityError, match="seed must be a nonnegative integer"):
        parse_results_jsonl(
            path,
            expected_decoder_id="rbposd-bb72-osd1-v1",
            expected_task_id="bb-css-memory-x-cdep-v1",
            expected_distance=None,
            expected_p_values=[0.003],
            expected_decoder_parameters={
                "bp_iters": 50,
                "early_stop": True,
                "osd_order": 1,
            },
            expected_impl_key="rbposd",
            require_observable_run_metadata=True,
        )


def test_require_rsinter_normalizes_version_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rsinter_module.shutil, "which", lambda name: "/bin/rsinter")

    def fake_run(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd=["/bin/rsinter", "--version"], timeout=5)

    monkeypatch.setattr(rsinter_module.subprocess, "run", fake_run)

    with pytest.raises(SearchIntegrityError, match="rsinter --version timed out"):
        require_rsinter()


def test_require_rsinter_normalizes_version_os_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rsinter_module.shutil, "which", lambda name: "/bin/rsinter")

    def fake_run(*args: object, **kwargs: object) -> object:
        raise OSError("permission denied")

    monkeypatch.setattr(rsinter_module.subprocess, "run", fake_run)

    with pytest.raises(SearchIntegrityError, match="rsinter --version failed"):
        require_rsinter()


def test_require_rsinter_accepts_github_build_version_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rsinter_module.shutil, "which", lambda name: "/bin/rsinter")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["/bin/rsinter", "--version"],
            returncode=0,
            stdout="rsinter git main abc123\n",
            stderr="",
        )

    monkeypatch.setattr(rsinter_module.subprocess, "run", fake_run)

    assert require_rsinter() == ("/bin/rsinter", "rsinter git main abc123")


def test_require_rsinter_rejects_empty_version_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rsinter_module.shutil, "which", lambda name: "/bin/rsinter")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["/bin/rsinter", "--version"],
            returncode=0,
            stdout="\n",
            stderr="",
        )

    monkeypatch.setattr(rsinter_module.subprocess, "run", fake_run)

    with pytest.raises(SearchIntegrityError, match="returned empty output"):
        require_rsinter()


def test_require_rsinter_accepts_unparseable_dev_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rsinter_module.shutil, "which", lambda name: "/bin/rsinter")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["/bin/rsinter", "--version"],
            returncode=0,
            stdout="rsinter dev build\n",
            stderr="",
        )

    monkeypatch.setattr(rsinter_module.subprocess, "run", fake_run)

    assert require_rsinter() == ("/bin/rsinter", "rsinter dev build")


def test_run_rsinter_normalizes_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(*args: object, **kwargs: object) -> object:
        raise OSError("permission denied")

    monkeypatch.setattr(rsinter_module.subprocess, "run", fake_run)

    with pytest.raises(SearchIntegrityError, match="rsinter bench run failed"):
        run_rsinter(tmp_path / "spec.toml", tmp_path / "out", executable="/bin/rsinter")


def test_run_rsinter_normalizes_missing_general_css_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["/bin/rsinter", "bench", "run"],
            returncode=7,
            stdout="",
            stderr="unknown field `input_type` in runner params",
        )

    monkeypatch.setattr(rsinter_module.subprocess, "run", fake_run)

    with pytest.raises(SearchIntegrityError, match="upstream rstim general CSS support"):
        run_rsinter(
            tmp_path / "spec.toml",
            tmp_path / "out",
            executable="/bin/rsinter",
            requires_general_css_support=True,
        )


def test_run_rsinter_normalizes_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd=["/bin/rsinter", "bench"], timeout=3600)

    monkeypatch.setattr(rsinter_module.subprocess, "run", fake_run)

    with pytest.raises(SearchIntegrityError, match="rsinter bench run timed out"):
        run_rsinter(tmp_path / "spec.toml", tmp_path / "out", executable="/bin/rsinter")
