from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.run_loop import (
    CandidateRecord,
    RunConfig,
    StrategyEvent,
    autoresearch_evaluation_p_values,
    candidate_is_complete,
    choose_seed,
    default_tag,
    load_strategy_events,
    parse_wall_clock_seconds,
    rebuild_resume_state,
    representative_ler,
    render_strategy_trace,
    update_frontier,
    validate_path_segment,
)
from autoqec_search.run_render import FrontierItem


REPO_ROOT = Path(__file__).resolve().parents[1]


def _completed_manifest(candidate_id: str, ler: float = 0.013) -> dict:
    return {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "candidate_id": candidate_id,
        "task_id": "rotated-memory-x-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "completed",
        "created_at": "2026-06-14T03:11:22Z",
        "tool_revisions": {"autoqec_search": "0.1.0", "rsinter": "fake"},
        "decoder_parameters": {},
        "points": [
            {
                "p": 0.005,
                "rounds": 3,
                "shots": 1000,
                "errors": int(round(ler * 1000)),
                "ler": ler,
                "ci_low": max(0.0, ler / 2),
                "ci_high": min(1.0, ler * 2),
                "seconds": 0.01,
            }
        ],
    }


def _placeholder_manifest(candidate_id: str) -> dict:
    return {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "candidate_id": candidate_id,
        "task_id": "rotated-memory-x-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "placeholder",
        "metrics": {"logical_error_rate": None},
        "created_at": "2026-06-14T03:11:22Z",
    }


def _crash_manifest(candidate_id: str) -> dict:
    return {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "candidate_id": candidate_id,
        "task_id": "rotated-memory-x-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "crash",
        "created_at": "2026-06-14T03:11:22Z",
        "error": "no matching Zoo instance",
    }


def _run_config() -> RunConfig:
    return RunConfig(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        task_id="rotated-memory-x-cdep-v1",
        primary_decoder_id="rmatching-default-v1",
        representative_p=0.005,
    )


def _frontier_item(candidate_id: str, distance: int, ler: float) -> FrontierItem:
    return FrontierItem(
        candidate_id=candidate_id,
        distance=distance,
        decoder_id="rmatching-default-v1",
        p=0.005,
        ler=ler,
        manifest_path=(
            f"candidates/{candidate_id}/evaluations/"
            "rotated-memory-x-cdep-v1/rmatching-default-v1/manifest.json"
        ),
    )


def _write_manifest(
    candidate_root: Path,
    manifest: dict,
    *,
    path_task_id: str | None = None,
    path_decoder_id: str | None = None,
) -> None:
    manifest_path = (
        candidate_root
        / "evaluations"
        / (path_task_id or manifest["task_id"])
        / (path_decoder_id or manifest["decoder_id"])
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest) + "\n")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("90", 90), ("90s", 90), ("5m", 300), ("1h", 3600)],
)
def test_parse_wall_clock_seconds_accepts_supported_forms(
    value: str, expected: int
) -> None:
    assert parse_wall_clock_seconds(value) == expected


@pytest.mark.parametrize("value", ["0", "-1", "1d", "abc", "1.5m", ""])
def test_parse_wall_clock_seconds_rejects_invalid_forms(value: str) -> None:
    with pytest.raises(SearchIntegrityError):
        parse_wall_clock_seconds(value)


def test_choose_seed_prefers_cli_then_campaign_fixed_seed_then_zero() -> None:
    assert choose_seed(11, {"random_seed_policy": {"mode": "fixed", "seed": 7}}) == 11
    assert choose_seed(None, {"random_seed_policy": {"mode": "fixed", "seed": 7}}) == 7
    assert choose_seed(None, {"random_seed_policy": {"mode": "none", "seed": None}}) == 0


def test_default_tag_uses_campaign_timestamp_and_seed() -> None:
    assert (
        default_tag(
            campaign_id="rotated-surface-baseline",
            created_at="2026-06-14T03:11:22Z",
            seed=7,
        )
        == "rotated-surface-baseline-20260614T031122Z-seed7"
    )


def test_build_env_records_distance_method_metadata() -> None:
    from autoqec_search.run_loop import build_env

    env = build_env(
        Path(__file__).resolve().parents[1],
        "autoresearch/run",
        "2026-06-16T00:00:00Z",
        7,
        90,
        "rsinter fake",
        strategy={"name": "grid", "params": {}},
        distance_method={
            "method": "rstim-ilp-exact",
            "qec_code_bin": "qec-code",
            "bound_type": "exact",
        },
    )

    assert env["distance_method"]["method"] == "rstim-ilp-exact"
    assert env["distance_method"]["bound_type"] == "exact"
    assert env["distance_method"]["qec_code_bin"] == "qec-code"


def test_run_cli_accepts_exact_distance_method_flags() -> None:
    from autoqec_search.cli import build_parser

    args = build_parser().parse_args(
        [
            "run",
            "--root",
            ".",
            "--campaign",
            "rotated-surface-baseline",
            "--distance-method",
            "rstim-ilp-exact",
            "--qec-code-bin",
            "/tmp/qec-code",
        ]
    )

    assert args.distance_method == "rstim-ilp-exact"
    assert args.qec_code_bin == "/tmp/qec-code"


def test_run_cli_rejects_obsolete_randomized_distance_flags() -> None:
    from autoqec_search.cli import build_parser

    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "run",
                "--root",
                ".",
                "--campaign",
                "rotated-surface-baseline",
                "--distance-iterations",
                "25",
            ]
        )


@pytest.mark.parametrize("value", ["", ".", "..", "bad/name", "bad\\name", "bad\nname"])
def test_validate_path_segment_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(SearchIntegrityError):
        validate_path_segment(value, label="run_id")


def test_representative_ler_reads_primary_decoder_and_p() -> None:
    assert representative_ler(
        [_completed_manifest("candidate-a", ler=0.013)],
        decoder_id="rmatching-default-v1",
        p=0.005,
    ) == pytest.approx(0.013)


@pytest.mark.parametrize("ler", [math.nan, math.inf, -0.1, 1.1, True])
def test_representative_ler_rejects_invalid_ler_values(ler: float | bool) -> None:
    manifest = _completed_manifest("candidate-a", ler=0.013)
    manifest["points"][0]["ler"] = ler

    with pytest.raises(SearchIntegrityError):
        representative_ler(
            [manifest],
            decoder_id="rmatching-default-v1",
            p=0.005,
        )


def _write_campaign_with_promote_rule(
    worktree_root: Path,
    run_root: Path,
    *,
    rule_p: float,
) -> None:
    campaign_dir = worktree_root / "campaigns" / "examples" / "rotated-surface-baseline"
    campaign_dir.mkdir(parents=True)
    (campaign_dir / "campaign.json").write_text(
        json.dumps({"id": "rotated-surface-baseline"}) + "\n"
    )
    (campaign_dir / "promote_rules.json").write_text(
        json.dumps({"max_ler_at_p": {"p": rule_p, "ler": 0.5}}) + "\n"
    )
    run_root.mkdir(parents=True)
    (run_root / "run_spec.json").write_text(
        json.dumps({"campaign_id": "rotated-surface-baseline"}) + "\n"
    )


def test_autoresearch_evaluation_p_values_uses_task_p_list(tmp_path: Path) -> None:
    worktree_root = tmp_path / "worktree"
    run_root = tmp_path / "run"
    task_p_list = [0.001, 0.002, 0.005, 0.01, 0.02]
    _write_campaign_with_promote_rule(worktree_root, run_root, rule_p=0.005)

    assert autoresearch_evaluation_p_values(
        worktree_root,
        run_root,
        task_p_list,
    ) == task_p_list


def test_autoresearch_evaluation_p_values_appends_extra_promotion_p(
    tmp_path: Path,
) -> None:
    worktree_root = tmp_path / "worktree"
    run_root = tmp_path / "run"
    _write_campaign_with_promote_rule(worktree_root, run_root, rule_p=0.005)

    assert autoresearch_evaluation_p_values(
        worktree_root,
        run_root,
        [0.001, 0.002],
    ) == [0.001, 0.002, 0.005]


def test_update_frontier_keeps_first_and_discards_worse_same_distance() -> None:
    config = _run_config()
    first = CandidateRecord(
        candidate_id="rotated-surface-d3-example",
        distance=3,
        completed_manifests=[_completed_manifest("rotated-surface-d3-example", 0.013)],
    )
    second = CandidateRecord(
        candidate_id="rotated-surface-d3-repeat",
        distance=3,
        completed_manifests=[_completed_manifest("rotated-surface-d3-repeat", 0.02)],
    )

    frontier, first_row = update_frontier(config, [], first)
    frontier, second_row = update_frontier(config, frontier, second)

    assert first_row.status == "keep"
    assert first_row.description == "entered frontier for distance 3"
    assert second_row.status == "discard"
    assert second_row.description == "did not improve distance 3 frontier"
    assert [item.candidate_id for item in frontier] == ["rotated-surface-d3-example"]


def test_update_frontier_discard_preserves_other_distances() -> None:
    existing = [
        _frontier_item("rotated-surface-d3-example", 3, 0.013),
        _frontier_item("rotated-surface-d5-example", 5, 0.01),
    ]
    candidate = CandidateRecord(
        candidate_id="rotated-surface-d3-repeat",
        distance=3,
        completed_manifests=[_completed_manifest("rotated-surface-d3-repeat", 0.02)],
    )

    frontier, row = update_frontier(_run_config(), existing, candidate)

    assert row.status == "discard"
    assert [item.candidate_id for item in frontier] == [
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
    ]


def test_update_frontier_better_replacement_preserves_other_distances() -> None:
    existing = [
        _frontier_item("rotated-surface-d3-repeat", 3, 0.02),
        _frontier_item("rotated-surface-d5-example", 5, 0.01),
    ]
    candidate = CandidateRecord(
        candidate_id="rotated-surface-d3-example",
        distance=3,
        completed_manifests=[_completed_manifest("rotated-surface-d3-example", 0.013)],
    )

    frontier, row = update_frontier(_run_config(), existing, candidate)

    assert row.status == "keep"
    assert [item.candidate_id for item in frontier] == [
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
    ]


def test_update_frontier_rejects_duplicate_frontier_distance() -> None:
    duplicate_frontier = [
        _frontier_item("rotated-surface-d3-example", 3, 0.013),
        _frontier_item("rotated-surface-d3-repeat", 3, 0.02),
    ]
    candidate = CandidateRecord(
        candidate_id="rotated-surface-d5-example",
        distance=5,
        completed_manifests=[_completed_manifest("rotated-surface-d5-example", 0.01)],
    )

    with pytest.raises(SearchIntegrityError, match="duplicate frontier distance"):
        update_frontier(_run_config(), duplicate_frontier, candidate)


def test_update_frontier_accepts_bb72_distance_from_resolved_candidate() -> None:
    config = RunConfig(
        campaign_id="bb72-qldpc-campaign",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        task_id="bb-css-memory-x-cdep-v1",
        primary_decoder_id="rbposd-bb72-osd1-v1",
        representative_p=0.003,
    )
    manifest = _completed_manifest("bivariate-bicycle-code-m6-n6", ler=0.01)
    manifest["campaign_id"] = "bb72-qldpc-campaign"
    manifest["task_id"] = "bb-css-memory-x-cdep-v1"
    manifest["decoder_id"] = "rbposd-bb72-osd1-v1"
    manifest["points"][0]["p"] = 0.003

    frontier, row = update_frontier(
        config,
        [],
        CandidateRecord(
            candidate_id="bivariate-bicycle-code-m6-n6",
            distance=6,
            completed_manifests=[manifest],
        ),
    )

    assert row.status == "keep"
    assert frontier[0].distance == 6


def test_update_frontier_uses_upper_bound_screening_key_without_exact_distance() -> None:
    candidate_id = "upper-bound-candidate"
    frontier, row = update_frontier(
        _run_config(),
        [],
        CandidateRecord(
            candidate_id=candidate_id,
            distance=None,
            completed_manifests=[_completed_manifest(candidate_id, 0.01)],
            distance_bound_type="upper",
            upper_bound=7,
        ),
    )

    assert row.status == "keep"
    assert row.description == "entered frontier for upper-bound distance 7"
    assert frontier[0].candidate_id == candidate_id
    assert frontier[0].distance == 7
    assert frontier[0].distance_bound_type == "upper"
    assert frontier[0].upper_bound == 7


@pytest.mark.parametrize(
    "manifest_factory", [_completed_manifest, _placeholder_manifest, _crash_manifest]
)
def test_candidate_is_complete_accepts_finished_manifest_statuses(
    tmp_path: Path, manifest_factory
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    _write_manifest(candidate_root, manifest_factory("rotated-surface-d3-example"))

    assert candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.__setitem__("candidate_id", "other-candidate"),
        lambda payload: payload.__setitem__("task_id", "other-task"),
        lambda payload: payload.__setitem__("decoder_id", "other-decoder"),
        lambda payload: payload.__setitem__("status", "placeholder"),
        lambda payload: payload.__setitem__("points", []),
    ],
)
def test_candidate_is_complete_rejects_malformed_completed_manifest(
    tmp_path: Path, mutation
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest = _completed_manifest("rotated-surface-d3-example")
    mutation(manifest)
    _write_manifest(
        candidate_root,
        manifest,
        path_task_id="rotated-memory-x-cdep-v1",
        path_decoder_id="rmatching-default-v1",
    )

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


def test_candidate_is_complete_rejects_bb72_manifest_without_run_metadata(
    tmp_path: Path,
) -> None:
    candidate_root = tmp_path / "candidates" / "bivariate-bicycle-code-m6-n6"
    manifest = _completed_manifest("bivariate-bicycle-code-m6-n6")
    manifest["campaign_id"] = "bb72-qldpc-campaign"
    manifest["task_id"] = "bb-css-memory-x-cdep-v1"
    manifest["decoder_id"] = "rbposd-bb72-osd1-v1"
    manifest["points"][0]["p"] = 0.003
    _write_manifest(candidate_root, manifest)

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["bb-css-memory-x-cdep-v1"],
        decoder_ids=["rbposd-bb72-osd1-v1"],
        campaign_id="bb72-qldpc-campaign",
        run_id="fixed-check",
    )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("logical_observable_source", "generated"),
        ("logical_observable_basis", "z"),
        ("logical_observable_count", 999),
        ("seed", 0),
        ("decoder_impl", "wrong-impl"),
        ("logical_failure_aggregation", "wrong-aggregation"),
    ],
)
def test_candidate_is_complete_rejects_bb72_manifest_with_wrong_observable_metadata(
    tmp_path: Path,
    field: str,
    bad_value: object,
) -> None:
    candidate_root = tmp_path / "candidates" / "bivariate-bicycle-code-m6-n6"
    manifest = _completed_manifest("bivariate-bicycle-code-m6-n6")
    manifest["campaign_id"] = "bb72-qldpc-campaign"
    manifest["task_id"] = "bb-css-memory-x-cdep-v1"
    manifest["decoder_id"] = "rbposd-bb72-osd1-v1"
    manifest["points"][0]["p"] = 0.003
    manifest["run_metadata"] = {
        "decoder_impl": "rbposd",
        "logical_failure_aggregation": "any_logical",
        "logical_observable_source": "explicit",
        "logical_observable_basis": "x",
        "logical_observable_count": 12,
        "seed": 12345,
    }
    manifest["run_metadata"][field] = bad_value
    _write_manifest(candidate_root, manifest)

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["bb-css-memory-x-cdep-v1"],
        decoder_ids=["rbposd-bb72-osd1-v1"],
        campaign_id="bb72-qldpc-campaign",
        run_id="fixed-check",
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.__setitem__("created_at", "2026-6-14T03:11:22Z"),
        lambda payload: payload.__setitem__("tool_revisions", {}),
        lambda payload: payload.__setitem__(
            "tool_revisions", {"autoqec_search": "", "rsinter": "fake"}
        ),
        lambda payload: payload.__setitem__(
            "tool_revisions", {"autoqec_search": 123}
        ),
        lambda payload: payload.__setitem__("points", [{}]),
        lambda payload: payload["points"][0].__setitem__("ler", math.nan),
        lambda payload: payload["points"][0].__setitem__("ler", math.inf),
        lambda payload: payload["points"][0].__setitem__("ler", -0.1),
        lambda payload: payload["points"][0].__setitem__("ler", 1.1),
        lambda payload: payload["points"][0].__setitem__("p", 0),
        lambda payload: payload["points"][0].__setitem__("p", 1),
        lambda payload: payload["points"][0].__setitem__("p", math.nan),
        lambda payload: payload["points"][0].__setitem__("rounds", 0),
        lambda payload: payload["points"][0].__setitem__("shots", 0),
        lambda payload: payload["points"][0].__setitem__("errors", -1),
        lambda payload: payload["points"][0].__setitem__("rounds", True),
        lambda payload: payload["points"][0].__setitem__("shots", 1.5),
        lambda payload: payload["points"][0].__setitem__("errors", 1.5),
        lambda payload: payload["points"][0].__setitem__("seconds", -0.1),
        lambda payload: payload["points"][0].__setitem__("seconds", math.inf),
        lambda payload: payload["points"][0].__setitem__("errors", 1001),
        lambda payload: payload["points"][0].__setitem__("ci_low", 0.02),
        lambda payload: payload["points"][0].__setitem__("ci_high", 0.001),
        lambda payload: payload["points"][0].update({"ler": 0.001, "ci_low": 0.002}),
        lambda payload: payload["points"][0].update({"ler": 0.02, "ci_high": 0.01}),
        lambda payload: payload["points"][0].__setitem__("ler", 10**4000),
    ],
)
def test_candidate_is_complete_rejects_schema_bad_completed_manifest(
    tmp_path: Path, mutation
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest = _completed_manifest("rotated-surface-d3-example")
    mutation(manifest)
    _write_manifest(candidate_root, manifest)

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


def test_candidate_is_complete_rejects_huge_float_point_payload(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest = _completed_manifest("rotated-surface-d3-example")
    manifest_path = (
        candidate_root
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    text = json.dumps(manifest).replace('"ler": 0.013', '"ler": 1e10000')
    manifest_path.write_text(text + "\n")

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


def test_candidate_is_complete_rejects_parser_level_huge_int_payload(
    tmp_path: Path,
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest = _completed_manifest("rotated-surface-d3-example")
    manifest_path = (
        candidate_root
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    text = json.dumps(manifest).replace('"errors": 13', f'"errors": {"1" * 5000}')
    manifest_path.write_text(text + "\n")

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.__setitem__("candidate_id", "other-candidate"),
        lambda payload: payload.__setitem__("task_id", "other-task"),
        lambda payload: payload.__setitem__("decoder_id", "other-decoder"),
        lambda payload: payload.__setitem__("created_at", "not-a-timestamp"),
        lambda payload: payload.__setitem__("metrics", {}),
        lambda payload: payload["metrics"].__setitem__("logical_error_rate", math.nan),
        lambda payload: payload.__setitem__("points", [{"p": 0.005, "ler": 0.01}]),
    ],
)
def test_candidate_is_complete_rejects_malformed_placeholder_manifest(
    tmp_path: Path, mutation
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest = _placeholder_manifest("rotated-surface-d3-example")
    mutation(manifest)
    _write_manifest(
        candidate_root,
        manifest,
        path_task_id="rotated-memory-x-cdep-v1",
        path_decoder_id="rmatching-default-v1",
    )

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.__setitem__("candidate_id", "other-candidate"),
        lambda payload: payload.__setitem__("task_id", "other-task"),
        lambda payload: payload.__setitem__("decoder_id", "other-decoder"),
        lambda payload: payload.__setitem__("created_at", "not-a-timestamp"),
        lambda payload: payload.__setitem__("error", ""),
        lambda payload: payload.__setitem__("error", 123),
    ],
)
def test_candidate_is_complete_rejects_malformed_crash_manifest(
    tmp_path: Path, mutation
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest = _crash_manifest("rotated-surface-d3-example")
    mutation(manifest)
    _write_manifest(
        candidate_root,
        manifest,
        path_task_id="rotated-memory-x-cdep-v1",
        path_decoder_id="rmatching-default-v1",
    )

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


@pytest.mark.parametrize(
    ("task_ids", "decoder_ids"),
    [
        (["../../escape-task"], ["rmatching-default-v1"]),
        (["rotated-memory-x-cdep-v1"], ["../../../escape-decoder"]),
    ],
)
def test_candidate_is_complete_rejects_unsafe_task_and_decoder_paths(
    tmp_path: Path, task_ids: list[str], decoder_ids: list[str]
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest = _completed_manifest("rotated-surface-d3-example")
    manifest["task_id"] = task_ids[0]
    manifest["decoder_id"] = decoder_ids[0]
    manifest_path = (
        candidate_root
        / "evaluations"
        / task_ids[0]
        / decoder_ids[0]
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest) + "\n")

    assert manifest_path.resolve().is_file()
    assert candidate_root.resolve() not in manifest_path.resolve().parents
    assert not candidate_is_complete(
        candidate_root,
        task_ids=task_ids,
        decoder_ids=decoder_ids,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.__setitem__("campaign_id", ""),
        lambda payload: payload.__setitem__("campaign_id", 123),
        lambda payload: payload.__setitem__("campaign_id", "bad/campaign"),
        lambda payload: payload.__setitem__("campaign_id", "bad\\campaign"),
        lambda payload: payload.__setitem__("campaign_id", "bad\ncampaign"),
        lambda payload: payload.__setitem__("campaign_id", "."),
        lambda payload: payload.__setitem__("campaign_id", ".."),
        lambda payload: payload.__setitem__("run_id", ""),
        lambda payload: payload.__setitem__("run_id", 123),
        lambda payload: payload.__setitem__("run_id", "bad/run"),
        lambda payload: payload.__setitem__("run_id", "bad\\run"),
        lambda payload: payload.__setitem__("run_id", "bad\nrun"),
        lambda payload: payload.__setitem__("run_id", "."),
        lambda payload: payload.__setitem__("run_id", ".."),
    ],
)
def test_candidate_is_complete_rejects_bad_campaign_and_run_ids_without_expected_args(
    tmp_path: Path, mutation
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest = _completed_manifest("rotated-surface-d3-example")
    mutation(manifest)
    _write_manifest(candidate_root, manifest)

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


def test_candidate_is_complete_accepts_expected_campaign_and_run_ids(
    tmp_path: Path,
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    _write_manifest(candidate_root, _completed_manifest("rotated-surface-d3-example"))

    assert candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
    )


def test_candidate_is_complete_rejects_expected_campaign_and_run_mismatch(
    tmp_path: Path,
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    _write_manifest(candidate_root, _completed_manifest("rotated-surface-d3-example"))

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
        campaign_id="other-campaign",
        run_id="fixed-check",
    )
    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
        campaign_id="rotated-surface-baseline",
        run_id="other-run",
    )


@pytest.mark.parametrize(
    "manifest_factory", [_completed_manifest, _placeholder_manifest, _crash_manifest]
)
def test_candidate_is_complete_rejects_calendar_invalid_created_at(
    tmp_path: Path, manifest_factory
) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest = manifest_factory("rotated-surface-d3-example")
    manifest["created_at"] = "2026-99-99T99:99:99Z"
    _write_manifest(candidate_root, manifest)

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


def test_candidate_is_complete_rejects_non_utf8_manifest_bytes(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest_path = (
        candidate_root
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(b"\xff\xfe\x00")

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


def test_candidate_is_complete_rejects_candidate_root_with_traversal_parts(
    tmp_path: Path,
) -> None:
    candidate_root = (
        tmp_path
        / "run"
        / "candidates"
        / ".."
        / ".."
        / "escaped-candidate"
    )
    _write_manifest(candidate_root, _completed_manifest("escaped-candidate"))

    assert candidate_root.resolve().is_dir()
    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


def test_candidate_is_complete_rejects_unsafe_candidate_root_name(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidates" / "bad\ncandidate"
    _write_manifest(candidate_root, _completed_manifest("bad\ncandidate"))

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


def test_candidate_is_complete_requires_all_expected_manifests(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"

    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )


def test_git_status_porcelain_reports_clean_and_dirty_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "autoqec@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AutoQEC"],
        cwd=tmp_path,
        check=True,
    )
    tracked_path = tmp_path / "tracked.txt"
    tracked_path.write_text("initial\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True)

    from autoqec_search.run_loop import git_status_porcelain

    assert git_status_porcelain(tmp_path) == ""

    tracked_path.write_text("changed\n")

    assert "tracked.txt" in git_status_porcelain(tmp_path)


def test_git_branch_exists_checks_local_branch_not_tag(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "autoqec@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AutoQEC"],
        cwd=tmp_path,
        check=True,
    )
    tracked_path = tmp_path / "tracked.txt"
    tracked_path.write_text("initial\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True)
    subprocess.run(["git", "tag", "autoresearch/example"], cwd=tmp_path, check=True)

    from autoqec_search.run_loop import git_branch_exists

    assert not git_branch_exists(tmp_path, "missing-branch")
    assert not git_branch_exists(tmp_path, "autoresearch/example")

    subprocess.run(["git", "branch", "autoresearch/example"], cwd=tmp_path, check=True)

    assert git_branch_exists(tmp_path, "autoresearch/example")


def test_git_branch_exists_raises_on_non_git_directory(tmp_path: Path) -> None:
    from autoqec_search.run_loop import git_branch_exists

    with pytest.raises(SearchIntegrityError):
        git_branch_exists(tmp_path, "autoresearch/example")


def test_write_run_skeleton_writes_autoresearch_metadata(tmp_path: Path) -> None:
    from autoqec_search.run_loop import write_run_skeleton

    run_root = (
        tmp_path
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "fixed-check"
    )
    env = {
        "tool": "autoqec-search",
        "version": "0.1.0",
        "generated_at": "2026-06-14T03:11:22Z",
        "mode": "autoresearch",
    }
    suite = {
        "id": "rotated-surface-baseline-v1",
        "task_ids": ["rotated-memory-x-cdep-v1"],
        "decoder_ids": ["rmatching-default-v1"],
    }

    run_spec = write_run_skeleton(
        run_root,
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        suite=suite,
        candidate_ids=["rotated-surface-d3-example"],
        created_at="2026-06-14T03:11:22Z",
        wall_clock_seconds=90,
        seed=7,
        env=env,
    )

    assert run_spec["mode"] == "autoresearch"
    assert run_spec["tag"] == "fixed-check"
    assert run_spec["suite_id"] == suite["id"]
    assert run_spec["task_ids"] == suite["task_ids"]
    assert run_spec["decoder_ids"] == suite["decoder_ids"]
    assert json.loads((run_root / "run_spec.json").read_text()) == run_spec
    assert json.loads((run_root / "env.json").read_text()) == env


def test_render_strategy_trace_encodes_events_and_frontier_quality() -> None:
    trace = render_strategy_trace(
        "rotated-surface-baseline",
        "fixed-check",
        {"name": "adaptive", "params": {}},
        [
            StrategyEvent(
                candidate_id="rotated-surface-d3-example",
                reason="cold-start:smallest-distance:d3",
                action="evaluated",
                verdict="keep",
                frontier_quality=(3, -0.013),
            ),
            StrategyEvent(
                candidate_id=None,
                reason="strategy returned no fresh candidates",
                action="exhausted",
                verdict=None,
                frontier_quality=None,
            ),
        ],
    )

    assert trace == {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "strategy": {"name": "adaptive", "params": {}},
        "events": [
            {
                "candidate_id": "rotated-surface-d3-example",
                "reason": "cold-start:smallest-distance:d3",
                "action": "evaluated",
                "verdict": "keep",
                "frontier_quality": {
                    "max_distance": 3,
                    "negative_ler": -0.013,
                },
            },
            {
                "candidate_id": None,
                "reason": "strategy returned no fresh candidates",
                "action": "exhausted",
                "verdict": None,
                "frontier_quality": None,
            },
        ],
    }


def test_write_run_skeleton_writes_strategy_metadata(tmp_path: Path) -> None:
    from autoqec_search.run_loop import write_run_skeleton

    run_root = (
        tmp_path
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "fixed-check"
    )
    suite = {
        "id": "rotated-surface-baseline-v1",
        "task_ids": ["rotated-memory-x-cdep-v1"],
        "decoder_ids": ["rmatching-default-v1"],
    }
    strategy = {"name": "grid", "params": {}}

    run_spec = write_run_skeleton(
        run_root,
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        suite=suite,
        candidate_ids=["rotated-surface-d3-example"],
        created_at="2026-06-14T03:11:22Z",
        wall_clock_seconds=90,
        seed=7,
        env={"tool": "autoqec-search"},
        strategy=strategy,
    )

    assert run_spec["strategy"] == strategy
    assert json.loads((run_root / "run_spec.json").read_text())["strategy"] == strategy


def test_selected_candidate_specs_returns_full_search_space_despite_budget() -> None:
    from autoqec_search.run_loop import _selected_candidate_specs

    class Workspace:
        search_spaces = {
            "rotated-surface-baseline": {
                "candidate_specs": [
                    {
                        "candidate_id": "candidate-a",
                        "code_family": "rotated-surface-code",
                        "parameters": {"distance": 3},
                        "provenance": {"kind": "fixture", "label": "a"},
                    },
                    {
                        "candidate_id": "candidate-b",
                        "code_family": "rotated-surface-code",
                        "parameters": {"distance": 5},
                        "provenance": {"kind": "fixture", "label": "b"},
                    },
                ]
            }
        }

    selected = _selected_candidate_specs(
        REPO_ROOT,
        Workspace(),
        "rotated-surface-baseline",
        {"stop_conditions": {"max_candidates": 1}},
    )

    assert [spec["candidate_id"] for spec in selected] == [
        "candidate-a",
        "candidate-b",
    ]


def test_selected_candidate_specs_resolves_explicit_instance_parameters() -> None:
    from autoqec_search.run_loop import _selected_candidate_specs

    workspace = load_search_workspace(REPO_ROOT)

    selected = _selected_candidate_specs(
        REPO_ROOT,
        workspace,
        "decoder-registry-css-bb-smoke",
        workspace.campaigns["decoder-registry-css-bb-smoke"],
    )

    assert selected == [
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "code_family": "bivariate-bicycle-code",
            "parameters": {
                "distance": 6,
                "paper": {
                    "A": "x^3 + y + y^2",
                    "B": "y^3 + x + x^2",
                    "l": 6,
                    "m": 6,
                    "paper_ref": "2308.07915",
                },
                "generator": {
                    "hd": [[0, 3], [1, 0], [2, 0]],
                    "m": 6,
                    "n": 6,
                    "source_convention": "autoqec-bivariate-bicycle-fallback",
                    "vc": [[3, 0], [0, 1], [0, 2]],
                },
            },
            "provenance": {
                "kind": "zoo-instance",
                "label": "fixed BB CSS decoder-registry validation instance",
            },
            "instance_path": (
                "zoo/codes/bivariate-bicycle-code/instances/"
                "bivariate-bicycle-code-m6-n6"
            ),
        }
    ]


def test_rebuild_resume_state_creates_terminal_event_for_crash(
    tmp_path: Path,
) -> None:
    config = _run_config()
    candidate_id = "crashed-candidate"
    candidate_root = tmp_path / "candidates" / candidate_id
    _write_manifest(candidate_root, _crash_manifest(candidate_id))

    rows, frontier, attempted_ids, events = rebuild_resume_state(
        tmp_path,
        config,
        [
            {
                "candidate_id": candidate_id,
                "code_family": "rotated-surface-code",
                "parameters": {"distance": 3},
                "provenance": {"kind": "fixture", "label": candidate_id},
            }
        ],
        {
            "task_ids": ["rotated-memory-x-cdep-v1"],
            "decoder_ids": ["rmatching-default-v1"],
        },
        selected_p_values=[0.005],
    )

    assert rows[0].candidate_id == candidate_id
    assert rows[0].status == "crash"
    assert frontier == []
    assert attempted_ids == {candidate_id}
    assert events == [
        StrategyEvent(
            candidate_id=candidate_id,
            reason="resume-terminal-candidate",
            action="evaluated",
            verdict="crash",
            frontier_quality=(0, 0.0),
        )
    ]


def test_rebuild_resume_state_uses_trace_evaluated_order_for_frontier(
    tmp_path: Path,
) -> None:
    config = _run_config()
    higher_ler_id = "same-distance-higher-ler"
    lower_ler_id = "same-distance-lower-ler"
    for candidate_id, ler in (
        (higher_ler_id, 0.02),
        (lower_ler_id, 0.01),
    ):
        candidate_root = tmp_path / "candidates" / candidate_id
        _write_manifest(candidate_root, _completed_manifest(candidate_id, ler=ler))
        (candidate_root / "distance.json").write_text(
            json.dumps({"status": "completed", "distance": 3}) + "\n"
        )

    rows, frontier, attempted_ids, events = rebuild_resume_state(
        tmp_path,
        config,
        [
            {
                "candidate_id": higher_ler_id,
                "code_family": "rotated-surface-code",
                "parameters": {"distance": 3},
                "provenance": {"kind": "fixture", "label": higher_ler_id},
            },
            {
                "candidate_id": lower_ler_id,
                "code_family": "rotated-surface-code",
                "parameters": {"distance": 3},
                "provenance": {"kind": "fixture", "label": lower_ler_id},
            },
        ],
        {
            "task_ids": ["rotated-memory-x-cdep-v1"],
            "decoder_ids": ["rmatching-default-v1"],
        },
        selected_p_values=[0.005],
        strategy_events=[
            StrategyEvent(
                candidate_id=lower_ler_id,
                reason="original-first",
                action="evaluated",
                verdict="keep",
                frontier_quality=(3, -0.01),
            ),
            StrategyEvent(
                candidate_id=higher_ler_id,
                reason="original-second",
                action="evaluated",
                verdict="discard",
                frontier_quality=(3, -0.01),
            ),
        ],
    )

    assert [(row.candidate_id, row.status) for row in rows] == [
        (lower_ler_id, "keep"),
        (higher_ler_id, "discard"),
    ]
    assert [item.candidate_id for item in frontier] == [lower_ler_id]
    assert attempted_ids == {higher_ler_id, lower_ler_id}
    assert [event.candidate_id for event in events] == [lower_ler_id, higher_ler_id]


def test_rebuild_resume_state_uses_historical_run_decoders_for_terminal_check(
    tmp_path: Path,
) -> None:
    config = _run_config()
    candidate_id = "legacy-decoder-subset-candidate"
    candidate_root = tmp_path / "candidates" / candidate_id
    manifest = _completed_manifest(candidate_id, ler=0.012)
    manifest["decoder_parameters"] = {}
    _write_manifest(candidate_root, manifest)
    (candidate_root / "distance.json").write_text(
        json.dumps({"status": "completed", "distance": 3}) + "\n"
    )

    rows, frontier, attempted_ids, events = rebuild_resume_state(
        tmp_path,
        config,
        [
            {
                "candidate_id": candidate_id,
                "code_family": "rotated-surface-code",
                "parameters": {"distance": 3},
                "provenance": {"kind": "fixture", "label": candidate_id},
            }
        ],
        {
            "task_ids": ["rotated-memory-x-cdep-v1"],
            "decoder_ids": [
                "rmatching-default-v1",
                "rbposd-default-v1",
                "rbposd-osd0-v1",
                "rbposd-osd10-v1",
                "rilpqec-default-v1",
            ],
        },
        selected_p_values=[0.005],
        run_decoder_ids=["rmatching-default-v1"],
    )

    assert [row.candidate_id for row in rows] == [candidate_id]
    assert [item.candidate_id for item in frontier] == [candidate_id]
    assert attempted_ids == {candidate_id}
    assert [event.candidate_id for event in events] == [candidate_id]


@pytest.mark.parametrize(
    "event_update",
    [
        {"action": "unknown"},
        {"action": "deduped", "verdict": "keep"},
        {"action": "evaluated", "verdict": None},
        {"action": "evaluated", "verdict": "winner"},
        {"frontier_quality": {"max_distance": -1, "negative_ler": 0.0}},
        {"frontier_quality": {"max_distance": 3, "negative_ler": -1.5}},
    ],
)
def test_load_strategy_events_rejects_invalid_event_fields(
    tmp_path: Path,
    event_update: dict,
) -> None:
    config = _run_config()
    event = {
        "candidate_id": "candidate-a",
        "reason": "file-order",
        "action": "evaluated",
        "verdict": "keep",
        "frontier_quality": {"max_distance": 3, "negative_ler": -0.01},
    }
    event.update(event_update)
    (tmp_path / "strategy_trace.json").write_text(
        json.dumps(
            {
                "campaign_id": config.campaign_id,
                "run_id": config.run_id,
                "strategy": {"name": "grid", "params": {}},
                "events": [event],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    with pytest.raises(SearchIntegrityError, match="strategy_trace"):
        load_strategy_events(
            tmp_path,
            config=config,
            strategy={"name": "grid", "params": {}},
        )
