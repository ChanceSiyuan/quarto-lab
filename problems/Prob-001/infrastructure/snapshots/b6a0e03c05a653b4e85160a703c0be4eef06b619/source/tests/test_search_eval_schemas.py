from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _completed_result_manifest() -> dict:
    return {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "candidate_id": "rotated-surface-d3-example",
        "task_id": "rotated-memory-z-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "completed",
        "created_at": "2026-06-13T10:20:39Z",
        "tool_revisions": {
            "rsinter": "rsinter git main abc123",
            "autoqec_search": "0.1.0",
        },
        "points": [
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
        ],
    }


def test_benchmark_task_schema_accepts_collection_batch_size() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "benchmark-task.schema.json"
    )
    task = {
        "id": "rotated-memory-z-cdep-v1",
        "title": "Rotated Memory X under circuit depolarizing noise",
        "observable": "logical_x",
        "noise_model": "circuit_depolarizing",
        "input_type": "memory-z",
        "p_list": [0.005],
        "rounds_policy": {
            "kind": "distance-scaled",
            "multiplier": 1,
            "minimum": 3,
        },
        "collection": {
            "max_shots": 1000,
            "max_errors": 50,
            "batch_size": 16,
            "decoder_overrides": {
                "rbposd-osd10-v1": {
                    "max_shots": 1,
                    "max_errors": 1,
                    "batch_size": 1,
                }
            },
        },
        "result_metrics": ["logical_error_rate"],
        "execution_status": "real",
    }

    Draft202012Validator(schema).validate(task)


def test_benchmark_task_schema_accepts_css_memory_seed_and_observables() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "benchmark-task.schema.json"
    )
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "title": "BB72 CSS memory X",
        "observable": "logical_x",
        "noise_model": "circuit_depolarizing",
        "input_type": "css",
        "p_list": [0.003],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "result_metrics": ["logical_error_rate"],
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "required",
        },
        "execution_status": "real",
    }

    Draft202012Validator(schema).validate(task)


def test_eval_schemas_accept_completed_records() -> None:
    schema_root = REPO_ROOT / "benchmarks" / "schemas"

    run_spec = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "suite_id": "rotated-surface-baseline-v1",
        "task_ids": ["rotated-memory-z-cdep-v1"],
        "decoder_ids": ["rmatching-default-v1"],
        "candidate_ids": ["rotated-surface-d3-example"],
        "created_at": "2026-06-13T10:20:39Z",
        "mode": "eval",
    }
    candidate = {
        "candidate_id": "rotated-surface-d3-example",
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "code_family": "rotated-surface-code",
        "parameters": {"distance": 3, "layout": "rotated"},
        "provenance": {"kind": "seed", "label": "repo-example"},
        "status": "evaluated",
    }
    manifest = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "candidate_id": "rotated-surface-d3-example",
        "task_id": "rotated-memory-z-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "completed",
        "created_at": "2026-06-13T10:20:39Z",
        "tool_revisions": {
            "rsinter": "rsinter git main abc123",
            "autoqec_search": "0.1.0",
        },
        "points": [
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
        ],
    }

    Draft202012Validator(_load_json(schema_root / "run-spec.schema.json")).validate(
        run_spec
    )
    Draft202012Validator(_load_json(schema_root / "candidate.schema.json")).validate(
        candidate
    )
    Draft202012Validator(
        _load_json(schema_root / "result-manifest.schema.json")
    ).validate(manifest)


def test_completed_result_manifest_accepts_missing_decoder_parameters() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )

    Draft202012Validator(schema).validate(_completed_result_manifest())


def test_completed_result_manifest_accepts_scalar_decoder_parameters() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )
    manifest = _completed_result_manifest()
    manifest["decoder_parameters"] = {
        "backend": "highs",
        "osd_order": 10,
        "mip_gap": 0.05,
        "early_stop": True,
        "time_limit_s": None,
    }

    Draft202012Validator(schema).validate(manifest)


def test_completed_result_manifest_accepts_scalar_run_metadata() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )
    manifest = _completed_result_manifest()
    manifest["run_metadata"] = {
        "decoder_impl": "rbposd",
        "logical_observable_source": "explicit",
        "logical_observable_basis": "x",
        "logical_failure_aggregation": "any_logical",
        "logical_observable_count": 12,
        "seed": 12345,
    }

    Draft202012Validator(schema).validate(manifest)


def test_completed_result_manifest_requires_bb72_run_metadata() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )
    manifest = _completed_result_manifest()
    manifest["task_id"] = "bb-css-memory-x-cdep-v1"
    manifest["decoder_id"] = "rbposd-bb72-osd1-v1"

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(manifest)


def test_completed_result_manifest_rejects_incomplete_observable_run_metadata() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )
    manifest = _completed_result_manifest()
    manifest["run_metadata"] = {
        "decoder_impl": "rbposd",
        "logical_observable_source": "explicit",
        "logical_observable_basis": "x",
        "logical_failure_aggregation": "any_logical",
        "seed": 12345,
    }

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(manifest)


@pytest.mark.parametrize("bad_value", ["12", 12.5, True, None])
def test_completed_result_manifest_rejects_bad_observable_count_metadata(
    bad_value: object,
) -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )
    manifest = _completed_result_manifest()
    manifest["run_metadata"] = {
        "decoder_impl": "rbposd",
        "logical_observable_source": "explicit",
        "logical_observable_basis": "x",
        "logical_failure_aggregation": "any_logical",
        "logical_observable_count": bad_value,
        "seed": 12345,
    }

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(manifest)


@pytest.mark.parametrize("bad_value", [{"nested": 1}, [1, 2]])
def test_completed_result_manifest_rejects_nested_decoder_parameters(
    bad_value: object,
) -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )
    manifest = _completed_result_manifest()
    manifest["decoder_parameters"] = {"bad": bad_value}

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(manifest)


def test_autoresearch_schemas_accept_run_and_crash_records() -> None:
    schema_root = REPO_ROOT / "benchmarks" / "schemas"
    run_spec = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "suite_id": "rotated-surface-baseline-v1",
        "task_ids": ["rotated-memory-z-cdep-v1"],
        "decoder_ids": [
            "rmatching-default-v1",
            "rbposd-default-v1",
            "rilpqec-default-v1",
        ],
        "candidate_ids": [
            "rotated-surface-d3-example",
            "rotated-surface-d3-repeat",
        ],
        "created_at": "2026-06-14T03:11:22Z",
        "mode": "autoresearch",
        "tag": "fixed-check",
        "wall_clock_seconds": 90,
        "seed": 7,
    }
    crashed_candidate = {
        "candidate_id": "rotated-surface-invalid-d1",
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "code_family": "rotated-surface-code",
        "parameters": {"distance": 1, "layout": "rotated"},
        "provenance": {"kind": "test", "label": "invalid-distance"},
        "status": "crashed",
    }
    crash_manifest = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "candidate_id": "rotated-surface-invalid-d1",
        "task_id": "rotated-memory-z-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "crash",
        "created_at": "2026-06-14T03:11:22Z",
        "error": "no matching Zoo instance",
    }

    Draft202012Validator(_load_json(schema_root / "run-spec.schema.json")).validate(
        run_spec
    )
    Draft202012Validator(_load_json(schema_root / "candidate.schema.json")).validate(
        crashed_candidate
    )
    Draft202012Validator(
        _load_json(schema_root / "result-manifest.schema.json")
    ).validate(crash_manifest)


def test_result_manifest_schema_still_accepts_existing_placeholder_manifest() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json")
    manifest = _load_json(
        REPO_ROOT
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
        / "candidates"
        / "rotated-surface-d3-example"
        / "evaluations"
        / "rotated-memory-z-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )

    Draft202012Validator(schema).validate(manifest)


def test_completed_result_manifest_rejects_probability_at_one() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )
    manifest = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "candidate_id": "rotated-surface-d3-example",
        "task_id": "rotated-memory-z-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "completed",
        "created_at": "2026-06-13T10:20:39Z",
        "tool_revisions": {
            "rsinter": "rsinter git main abc123",
            "autoqec_search": "0.1.0",
        },
        "points": [
            {
                "p": 1.0,
                "rounds": 3,
                "shots": 1000,
                "errors": 5,
                "ler": 0.005,
                "ci_low": 0.00214,
                "ci_high": 0.01165,
                "seconds": 1.25,
            }
        ],
    }

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(manifest)


def test_run_spec_schema_accepts_empty_candidate_report_fixture() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "run-spec.schema.json")
    run_spec = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "empty-run",
        "suite_id": "rotated-surface-baseline-v1",
        "task_ids": ["rotated-memory-z-cdep-v1"],
        "decoder_ids": ["rmatching-default-v1"],
        "candidate_ids": [],
        "created_at": "2026-06-14T00:00:00Z",
        "mode": "eval",
    }

    Draft202012Validator(schema).validate(run_spec)


def test_decoder_config_schema_accepts_backend_specific_parameters() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "decoder-config.schema.json")
    validator = Draft202012Validator(schema)

    validator.validate(
        {
            "id": "rmatching-default-v1",
            "title": "RMatching Default via rsinter",
            "backend": "rsinter",
            "impl_key": "rmatching",
            "language": "rust",
            "parameters": {},
            "execution_status": "real",
        }
    )
    validator.validate(
        {
            "id": "rbposd-osd10-v1",
            "title": "RBP-OSD OSD Order 10 via rsinter",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {
                "bp_iters": 50,
                "early_stop": True,
                "osd_order": 10,
            },
            "execution_status": "real",
        }
    )
    validator.validate(
        {
            "id": "rilpqec-highs-fast-v1",
            "title": "RILP-QEC HiGHS Fast via rsinter",
            "backend": "rsinter",
            "impl_key": "rilpqec",
            "language": "rust",
            "parameters": {
                "backend": "highs",
                "time_limit_s": 5.0,
                "mip_gap": 0.05,
                "threads": 2,
                "verbose": False,
            },
            "execution_status": "real",
        }
    )


@pytest.mark.parametrize(
    "decoder",
    [
        {
            "id": "rbposd-bogus-v1",
            "title": "Bad RBP-OSD",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {"bogus": 1},
            "execution_status": "real",
        },
        {
            "id": "rmatching-osd-v1",
            "title": "Bad RMatching",
            "backend": "rsinter",
            "impl_key": "rmatching",
            "language": "rust",
            "parameters": {"osd_order": 10},
            "execution_status": "real",
        },
        {
            "id": "rbposd-conflict-v1",
            "title": "Bad RBP-OSD Alias Conflict",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {"bp_iters": 50, "max_bp_iterations": 60},
            "execution_status": "real",
        },
        {
            "id": "rbposd-negative-v1",
            "title": "Bad RBP-OSD Negative",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {"osd_order": -1},
            "execution_status": "real",
        },
        {
            "id": "rilpqec-time-v1",
            "title": "Bad RILP-QEC Time",
            "backend": "rsinter",
            "impl_key": "rilpqec",
            "language": "rust",
            "parameters": {"time_limit_s": 0},
            "execution_status": "real",
        },
    ],
)
def test_decoder_config_schema_rejects_invalid_backend_parameters(
    decoder: dict,
) -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "decoder-config.schema.json")

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(decoder)


def test_benchmark_task_schema_accepts_css_fixed_rounds_task() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "benchmark-task.schema.json")
    Draft202012Validator(schema).validate(
        {
            "id": "bb-css-memory-x-cdep-v1",
            "title": "BB CSS Memory X under circuit depolarizing noise",
            "observable": "logical_x",
            "noise_model": "circuit_depolarizing",
            "input_type": "css",
            "p_list": [0.01],
            "rounds_policy": {"kind": "fixed", "rounds": 3},
            "collection": {"max_shots": 2000, "max_errors": 200, "batch_size": 256},
            "css_memory": {"basis": "x", "schedule": "greedy"},
            "result_metrics": ["logical_error_rate"],
            "execution_status": "real",
        }
    )


def test_search_space_schema_accepts_explicit_instance_candidate() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "search-space.schema.json")
    Draft202012Validator(schema).validate(
        {
            "campaign_id": "decoder-registry-css-bb-smoke",
            "mode": "explicit_list",
            "candidate_specs": [
                {
                    "candidate_id": "bivariate-bicycle-code-m6-n6",
                    "code_family": "bivariate-bicycle-code",
                    "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
                    "provenance": {
                        "kind": "zoo-instance",
                        "label": "fixed BB CSS decoder-registry validation instance",
                    },
                }
            ],
        }
    )


def test_candidate_schema_accepts_nested_instance_parameters() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "candidate.schema.json")
    Draft202012Validator(schema).validate(
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "campaign_id": "decoder-registry-css-bb-smoke",
            "run_id": "issue16-bb-css-validation",
            "code_family": "bivariate-bicycle-code",
            "parameters": {
                "m": 6,
                "n": 6,
                "vc": [[1, 0], [0, 1]],
                "hd": [[1, 1], [0, 2]],
            },
            "provenance": {
                "kind": "zoo-instance",
                "label": "fixed BB CSS decoder-registry validation instance",
            },
            "status": "evaluated",
        }
    )


def test_decoder_config_schema_accepts_predict_zero() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "decoder-config.schema.json")
    Draft202012Validator(schema).validate(
        {
            "id": "predict-zero-v1",
            "title": "Predict Zero via rsinter",
            "backend": "rsinter",
            "impl_key": "predict-zero",
            "language": "rust",
            "parameters": {},
            "execution_status": "real",
        }
    )


def test_css_bb_smoke_registry_fixtures_validate_against_schemas() -> None:
    fixture_checks = [
        (
            REPO_ROOT / "benchmarks" / "schemas" / "campaign.schema.json",
            REPO_ROOT / "campaigns" / "examples" / "decoder-registry-css-bb-smoke" / "campaign.json",
        ),
        (
            REPO_ROOT / "benchmarks" / "schemas" / "search-space.schema.json",
            REPO_ROOT / "campaigns" / "examples" / "decoder-registry-css-bb-smoke" / "search_space.json",
        ),
        (
            REPO_ROOT / "benchmarks" / "schemas" / "benchmark-task.schema.json",
            REPO_ROOT / "benchmarks" / "tasks" / "bb-css-memory-x-cdep-v1.json",
        ),
        (
            REPO_ROOT / "benchmarks" / "schemas" / "decoder-config.schema.json",
            REPO_ROOT / "benchmarks" / "decoders" / "predict-zero-v1.json",
        ),
        (
            REPO_ROOT / "benchmarks" / "schemas" / "benchmark-suite.schema.json",
            REPO_ROOT / "benchmarks" / "suites" / "decoder-registry-css-bb-smoke-v1.json",
        ),
    ]

    for schema_path, fixture_path in fixture_checks:
        Draft202012Validator(_load_json(schema_path)).validate(_load_json(fixture_path))
