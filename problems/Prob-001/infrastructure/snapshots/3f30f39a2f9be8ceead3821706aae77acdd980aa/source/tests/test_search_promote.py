from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from autoqec_search.load import SearchIntegrityError
from autoqec_search.promote import load_promote_rules


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_promote_rules_schema() -> dict:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "promote-rules.schema.json")
    Draft202012Validator.check_schema(schema)
    return schema


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _copy_search_tree(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    shutil.copytree(REPO_ROOT / "zoo", work_root / "zoo")
    return work_root


def test_promote_rules_schema_accepts_documented_shape() -> None:
    schema = _load_promote_rules_schema()
    Draft202012Validator(schema).validate(
        {
            "min_distance": 3,
            "max_ler_at_p": {"p": 0.01, "ler": 0.5},
            "require_distance_verified": True,
            "require_reference_check": False,
        }
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"min_distance": 0},
        {"max_ler_at_p": {"p": 0.0, "ler": 0.5}},
        {"max_ler_at_p": {"p": 0.01, "ler": 1.5}},
        {"require_distance_verified": "yes"},
        {"require_reference_check": "yes"},
        {"unexpected": True},
    ],
)
def test_promote_rules_schema_rejects_invalid_payloads(payload: dict) -> None:
    schema = _load_promote_rules_schema()
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_load_promote_rules_uses_campaign_sibling_file(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"

    loaded = load_promote_rules(work_root, run_root, rules_path=None)

    assert loaded is not None
    assert loaded.path == (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    )
    assert loaded.rules["min_distance"] == 3
    assert loaded.rules["max_ler_at_p"] == {"p": 0.01, "ler": 0.5}
    assert loaded.rules["require_distance_verified"] is True


def test_load_promote_rules_accepts_explicit_override(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"
    override = tmp_path / "strict-rules.json"
    _write_json(override, {"min_distance": 5})

    loaded = load_promote_rules(work_root, run_root, rules_path=override)

    assert loaded is not None
    assert loaded.path == override
    assert loaded.rules == {
        "min_distance": 5,
        "require_distance_verified": True,
        "require_reference_check": False,
    }


def test_load_promote_rules_returns_none_when_campaign_has_no_rules(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.unlink()
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"

    assert load_promote_rules(work_root, run_root, rules_path=None) is None


def test_load_promote_rules_rejects_invalid_rules_file(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    _write_json(rules, {"min_distance": 0})
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"

    with pytest.raises(SearchIntegrityError, match="invalid promote rules"):
        load_promote_rules(work_root, run_root, rules_path=None)


def test_load_promote_rules_rejects_malformed_rules_json(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.write_text("{")
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"

    with pytest.raises(SearchIntegrityError, match=r"invalid promote rules JSON.*promote_rules\.json"):
        load_promote_rules(work_root, run_root, rules_path=None)


def test_load_promote_rules_rejects_nonfinite_rules_json(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.write_text('{"max_ler_at_p": {"p": 0.01, "ler": NaN}}\n')
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"

    with pytest.raises(SearchIntegrityError, match=r"invalid promote rules JSON.*NaN"):
        load_promote_rules(work_root, run_root, rules_path=None)


def _make_finished_run(tmp_path: Path, *, ler: float = 0.013) -> tuple[Path, Path]:
    work_root = _copy_search_tree(tmp_path)
    promoted_demo_target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    shutil.rmtree(promoted_demo_target, ignore_errors=True)
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "finished"
    candidate_root = run_root / "candidates" / "rotated-surface-d3-example"
    artifact_source = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    artifact_root = candidate_root / "artifacts"
    artifact_root.mkdir(parents=True)
    for name in ("instance.json", "hx.json", "hz.json"):
        shutil.copyfile(artifact_source / name, artifact_root / name)

    _write_json(
        run_root / "run_spec.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "finished",
            "suite_id": "rotated-surface-baseline-v1",
            "task_ids": ["rotated-memory-z-cdep-v1"],
            "decoder_ids": ["rmatching-default-v1"],
            "candidate_ids": ["rotated-surface-d3-example"],
            "created_at": "2026-06-14T03:11:22Z",
            "mode": "autoresearch",
            "tag": "finished",
            "wall_clock_seconds": 90,
            "seed": 7,
        },
    )
    _write_json(
        run_root / "frontier.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "finished",
            "items": [
                {
                    "candidate_id": "rotated-surface-d3-example",
                    "distance": 3,
                    "decoder_id": "rmatching-default-v1",
                    "p": 0.01,
                    "ler": ler,
                    "manifest_path": (
                        "candidates/rotated-surface-d3-example/evaluations/"
                        "rotated-memory-z-cdep-v1/rmatching-default-v1/manifest.json"
                    ),
                }
            ],
        },
    )
    _write_json(
        candidate_root / "candidate.json",
        {
            "candidate_id": "rotated-surface-d3-example",
            "campaign_id": "rotated-surface-baseline",
            "run_id": "finished",
            "code_family": "rotated-surface-code",
            "parameters": {"distance": 3, "layout": "rotated"},
            "provenance": {"kind": "seed", "label": "repo-example"},
            "status": "evaluated",
        },
    )
    _write_json(
        candidate_root / "distance.json",
        {
            "status": "completed",
            "distance": 3,
            "method": "copied-from-zoo-instance",
            "source_instance_id": "rotated-surface-code-d3",
            "source_instance_path": str(artifact_source),
        },
    )
    _write_json(
        candidate_root / "evaluations" / "rotated-memory-z-cdep-v1" / "rmatching-default-v1" / "manifest.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "finished",
            "candidate_id": "rotated-surface-d3-example",
            "task_id": "rotated-memory-z-cdep-v1",
            "decoder_id": "rmatching-default-v1",
            "status": "completed",
            "created_at": "2026-06-14T03:11:22Z",
            "tool_revisions": {"autoqec_search": "0.1.0", "rsinter": "fake"},
            "points": [
                {
                    "p": 0.01,
                    "rounds": 3,
                    "shots": 1000,
                    "errors": int(round(ler * 1000)),
                    "ler": ler,
                    "ci_low": max(0.0, ler / 2),
                    "ci_high": min(1.0, ler * 2),
                    "seconds": 0.01,
                }
            ],
        },
    )
    return work_root, run_root


def test_evaluate_promotions_accepts_frontier_candidate_under_rules(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)

    decisions = evaluate_promotions(
        run_root,
        {
            "min_distance": 3,
            "max_ler_at_p": {"p": 0.01, "ler": 0.5},
            "require_distance_verified": True,
        },
    )

    assert [decision.status for decision in decisions] == ["promote"]
    assert decisions[0].candidate_id == "rotated-surface-d3-example"
    assert decisions[0].code_id == "rotated-surface-code"
    assert decisions[0].instance_payload["id"] == "rotated-surface-d3-example"
    assert decisions[0].instance_payload["derived_properties"]["distance"] == 3
    assert decisions[0].source_manifest_path.endswith("manifest.json")


def test_evaluate_promotions_skips_candidate_below_min_distance(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)

    decisions = evaluate_promotions(run_root, {"min_distance": 5, "require_distance_verified": True})

    assert [decision.status for decision in decisions] == ["skipped"]
    assert decisions[0].reason == "distance 3 is below min_distance 5"


def test_evaluate_promotions_skips_candidate_above_ler_limit(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path, ler=0.75)

    decisions = evaluate_promotions(
        run_root,
        {"max_ler_at_p": {"p": 0.01, "ler": 0.5}, "require_distance_verified": True},
    )

    assert [decision.status for decision in decisions] == ["skipped"]
    assert decisions[0].reason == "LER 0.75 at p=0.01 exceeds limit 0.5"


def test_evaluate_promotions_skips_when_ler_point_is_absent(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)

    decisions = evaluate_promotions(
        run_root,
        {"max_ler_at_p": {"p": 0.001, "ler": 0.5}, "require_distance_verified": True},
    )

    assert [decision.status for decision in decisions] == ["skipped"]
    assert decisions[0].reason == "missing LER point at p=0.001"


def test_evaluate_promotions_rejects_unverified_distance_when_required(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    distance_path = run_root / "candidates" / "rotated-surface-d3-example" / "distance.json"
    distance = _load_json(distance_path)
    distance["status"] = "not-computed"
    _write_json(distance_path, distance)

    with pytest.raises(SearchIntegrityError, match="distance is not verified"):
        evaluate_promotions(run_root, {"min_distance": 3, "require_distance_verified": True})


def test_evaluate_promotions_requires_passing_reference_check_when_configured(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    _write_json(
        run_root / "reference_check.json",
        {
            "status": "fail",
            "candidate_id": "rotated-surface-d3-example",
            "task_id": "rotated-memory-z-cdep-v1",
            "decoder_id": "rmatching-default-v1",
            "points": [],
        },
    )

    with pytest.raises(SearchIntegrityError, match="reference check failed"):
        evaluate_promotions(
            run_root,
            {"require_reference_check": True, "require_distance_verified": True},
        )

    reference = _load_json(run_root / "reference_check.json")
    reference["status"] = "pass"
    _write_json(run_root / "reference_check.json", reference)

    decisions = evaluate_promotions(
        run_root,
        {"require_reference_check": True, "require_distance_verified": True},
    )
    assert decisions[0].status == "promote"


def _frontier_path(run_root: Path) -> Path:
    return run_root / "frontier.json"


def _frontier_manifest_path(run_root: Path) -> Path:
    frontier = _load_json(_frontier_path(run_root))
    return run_root / frontier["items"][0]["manifest_path"]


def _mutate_first_frontier_item(run_root: Path, mutation) -> None:
    frontier_path = _frontier_path(run_root)
    frontier = _load_json(frontier_path)
    mutation(frontier["items"][0])
    _write_json(frontier_path, frontier)


def test_evaluate_promotions_rejects_manifest_identity_mismatch(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    manifest_path = _frontier_manifest_path(run_root)
    manifest = _load_json(manifest_path)
    manifest["candidate_id"] = "other-candidate"
    _write_json(manifest_path, manifest)

    with pytest.raises(SearchIntegrityError, match="frontier manifest identity mismatch"):
        evaluate_promotions(run_root, {"require_distance_verified": True})


def test_evaluate_promotions_rejects_distance_mismatch(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    distance_path = run_root / "candidates" / "rotated-surface-d3-example" / "distance.json"
    distance = _load_json(distance_path)
    distance["distance"] = 5
    _write_json(distance_path, distance)

    with pytest.raises(SearchIntegrityError, match="distance mismatch"):
        evaluate_promotions(run_root, {"min_distance": 5, "require_distance_verified": True})


def test_evaluate_promotions_rejects_upper_bound_distance_when_verified(
    tmp_path: Path,
) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    distance_path = run_root / "candidates" / "rotated-surface-d3-example" / "distance.json"
    distance = _load_json(distance_path)
    distance["method"] = "randomized-upper-bound"
    distance["bound_type"] = "upper"
    distance["upper_bound"] = distance["distance"]
    _write_json(distance_path, distance)

    with pytest.raises(SearchIntegrityError, match="requires an exact distance"):
        evaluate_promotions(run_root, {"min_distance": 3, "require_distance_verified": True})


def test_evaluate_promotions_rejects_upper_bound_distance_when_not_verified(
    tmp_path: Path,
) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    distance_path = run_root / "candidates" / "rotated-surface-d3-example" / "distance.json"
    distance = _load_json(distance_path)
    distance["method"] = "randomized-upper-bound"
    distance["bound_type"] = "upper"
    distance["upper_bound"] = distance["distance"]
    _write_json(distance_path, distance)

    with pytest.raises(SearchIntegrityError, match="requires an exact distance"):
        evaluate_promotions(run_root, {"min_distance": 3, "require_distance_verified": False})


def test_evaluate_promotions_rejects_randomized_distance_without_bound_type(
    tmp_path: Path,
) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    distance_path = run_root / "candidates" / "rotated-surface-d3-example" / "distance.json"
    distance = _load_json(distance_path)
    distance["method"] = "randomized-upper-bound"
    distance["upper_bound"] = distance["distance"]
    distance.pop("bound_type", None)
    _write_json(distance_path, distance)

    with pytest.raises(SearchIntegrityError, match="randomized-upper-bound.*bound_type upper"):
        evaluate_promotions(run_root, {"min_distance": 3, "require_distance_verified": True})


@pytest.mark.parametrize("field", ["distance", "decoder_id", "p", "ler", "manifest_path"])
def test_evaluate_promotions_rejects_frontier_item_missing_required_field(
    tmp_path: Path, field: str
) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    _mutate_first_frontier_item(run_root, lambda item: item.pop(field))

    with pytest.raises(SearchIntegrityError, match=f"frontier item {field}"):
        evaluate_promotions(run_root, {"require_distance_verified": True})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("distance", True),
        ("distance", 0),
        ("decoder_id", ""),
        ("p", "0.01"),
        ("p", 0),
        ("p", 1),
        ("ler", -0.1),
        ("ler", 1.1),
        ("manifest_path", "../manifest.json"),
    ],
)
def test_evaluate_promotions_rejects_invalid_frontier_item_field(
    tmp_path: Path, field: str, value
) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    _mutate_first_frontier_item(run_root, lambda item: item.__setitem__(field, value))

    with pytest.raises(SearchIntegrityError, match=f"frontier item {field}"):
        evaluate_promotions(run_root, {"require_distance_verified": True})


def test_evaluate_promotions_rejects_malformed_completed_manifest_point(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    manifest_path = _frontier_manifest_path(run_root)
    manifest = _load_json(manifest_path)
    manifest["points"][0] = {"p": "0.01", "ler": 0.013}
    _write_json(manifest_path, manifest)

    with pytest.raises(SearchIntegrityError, match="completed manifest point"):
        evaluate_promotions(
            run_root,
            {"max_ler_at_p": {"p": 0.01, "ler": 0.5}, "require_distance_verified": True},
        )


def test_evaluate_promotions_rewrites_schema_valid_instance_payload(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)

    decisions = evaluate_promotions(run_root, {"require_distance_verified": True})

    schema = _load_json(REPO_ROOT / "zoo" / "schemas" / "code-instance.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(decisions[0].instance_payload)
    provenance = decisions[0].instance_payload["provenance"]
    assert provenance["promoted_by"] == "autoqec-search promote"
    assert provenance["source_run"] == "rotated-surface-baseline/finished"
    assert provenance["source_candidate_id"] == "rotated-surface-d3-example"
    assert provenance["source_manifest_path"].endswith("manifest.json")
    assert provenance["promote_rules"] == {
        "require_distance_verified": True,
        "require_reference_check": False,
    }


def test_evaluate_promotions_deep_copies_rules_into_provenance(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    rules = {"max_ler_at_p": {"p": 0.01, "ler": 0.5}, "require_distance_verified": True}

    decisions = evaluate_promotions(run_root, rules)
    rules["max_ler_at_p"]["ler"] = 0.25
    rules["unexpected"] = True

    assert decisions[0].instance_payload["provenance"]["promote_rules"] == {
        "max_ler_at_p": {"p": 0.01, "ler": 0.5},
        "require_distance_verified": True,
        "require_reference_check": False,
    }


def test_promote_run_copies_instance_and_rebuilds_zoo(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)

    summary = promote_run(work_root, run_root, rules_path=None, force=False)

    target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    assert summary["status"] == "completed"
    assert summary["rules"] == {
        "min_distance": 3,
        "max_ler_at_p": {"p": 0.01, "ler": 0.5},
        "require_distance_verified": True,
        "require_reference_check": False,
    }
    assert summary["force"] is False
    assert [item["candidate_id"] for item in summary["promoted"]] == ["rotated-surface-d3-example"]
    assert summary["rules_path"] == "campaigns/examples/rotated-surface-baseline/promote_rules.json"
    assert summary["promoted"][0]["target"] == (
        "zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example"
    )
    assert target.is_dir()
    instance = _load_json(target / "instance.json")
    assert instance["id"] == "rotated-surface-d3-example"
    assert instance["provenance"]["promoted_by"] == "autoqec-search promote"
    assert instance["provenance"]["source_run"] == "rotated-surface-baseline/finished"
    instance_index = _load_json(work_root / "zoo" / "views" / "instance-index.json")
    assert "rotated-surface-d3-example" in [item["id"] for item in instance_index["items"]]
    card_md = (work_root / "zoo" / "codes" / "rotated-surface-code" / "card.md").read_text()
    assert "`rotated-surface-d3-example`" in card_md
    persisted = _load_json(run_root / "promotion_summary.json")
    assert persisted == summary


def test_promote_run_tight_rules_do_not_copy_instance(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    strict_rules = tmp_path / "strict-rules.json"
    _write_json(strict_rules, {"min_distance": 5})

    summary = promote_run(work_root, run_root, rules_path=strict_rules, force=False)

    target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    assert summary["status"] == "completed"
    assert summary["promoted"] == []
    assert summary["skipped"][0]["reason"] == "distance 3 is below min_distance 5"
    assert not target.exists()


def test_promote_run_tight_rules_does_not_rebuild_zoo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import autoqec_search.promote as promote_module

    work_root, run_root = _make_finished_run(tmp_path)
    strict_rules = tmp_path / "strict-rules.json"
    _write_json(strict_rules, {"min_distance": 5})

    def fail_build_zoo(*_args, **_kwargs) -> None:
        raise AssertionError("build_zoo should not be called without promoted candidates")

    monkeypatch.setattr(promote_module, "build_zoo", fail_build_zoo)

    summary = promote_module.promote_run(work_root, run_root, rules_path=strict_rules, force=False)

    assert summary["status"] == "completed"
    assert summary["promoted"] == []
    assert summary["skipped"][0]["reason"] == "distance 3 is below min_distance 5"


def test_promote_run_without_rules_writes_skip_summary(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.unlink()

    summary = promote_run(work_root, run_root, rules_path=None, force=False)

    assert summary["status"] == "skipped_no_rules"
    assert summary["rules"] is None
    assert summary["force"] is False
    assert summary["promoted"] == []
    assert summary["skipped"] == []
    assert _load_json(run_root / "promotion_summary.json") == summary


def test_promote_run_invalid_rules_write_failed_summary(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    _write_json(rules, {"min_distance": 0})

    with pytest.raises(SearchIntegrityError, match="invalid promote rules"):
        promote_run(work_root, run_root, rules_path=None, force=False)

    summary = _load_json(run_root / "promotion_summary.json")
    assert summary["status"] == "failed"
    assert summary["rules_path"] == "campaigns/examples/rotated-surface-baseline/promote_rules.json"
    assert summary["rules"] is None
    assert summary["force"] is False
    assert summary["promoted"] == []
    assert summary["skipped"] == []
    assert "invalid promote rules" in summary["failures"][0]["reason"]


def test_promote_run_reuses_identical_existing_target_without_force(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)

    first = promote_run(work_root, run_root, rules_path=None, force=False)
    second = promote_run(work_root, run_root, rules_path=None, force=False)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert [item["candidate_id"] for item in second["promoted"]] == ["rotated-surface-d3-example"]


def test_promote_run_reuses_same_instance_with_different_source_run_without_force(
    tmp_path: Path,
) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    first = promote_run(work_root, run_root, rules_path=None, force=False)

    rerun_root = work_root / "results" / "search" / "rotated-surface-baseline" / "rerun"
    shutil.copytree(run_root, rerun_root)
    run_spec = _load_json(rerun_root / "run_spec.json")
    run_spec["run_id"] = "rerun"
    run_spec["tag"] = "rerun"
    _write_json(rerun_root / "run_spec.json", run_spec)
    candidate_path = (
        rerun_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "candidate.json"
    )
    candidate = _load_json(candidate_path)
    candidate["run_id"] = "rerun"
    _write_json(candidate_path, candidate)
    frontier = _load_json(rerun_root / "frontier.json")
    frontier["run_id"] = "rerun"
    _write_json(rerun_root / "frontier.json", frontier)
    manifest = _load_json(
        rerun_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "evaluations"
        / "rotated-memory-z-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    manifest["run_id"] = "rerun"
    _write_json(
        rerun_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "evaluations"
        / "rotated-memory-z-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json",
        manifest,
    )

    second = promote_run(work_root, rerun_root, rules_path=None, force=False)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert [item["candidate_id"] for item in second["promoted"]] == ["rotated-surface-d3-example"]


def test_promote_run_refuses_different_existing_target_without_force(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    promote_run(work_root, run_root, rules_path=None, force=False)
    target_instance = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
        / "instance.json"
    )
    payload = _load_json(target_instance)
    payload["title"] = "Manual local edit"
    _write_json(target_instance, payload)

    with pytest.raises(SearchIntegrityError, match="target instance already exists"):
        promote_run(work_root, run_root, rules_path=None, force=False)


def test_promote_run_refuses_existing_instance_id_under_other_code(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    source = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    duplicate = (
        work_root
        / "zoo"
        / "codes"
        / "surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    shutil.copytree(source, duplicate)
    instance = _load_json(duplicate / "instance.json")
    instance["id"] = "rotated-surface-d3-example"
    instance["code_id"] = "surface-code"
    _write_json(duplicate / "instance.json", instance)

    with pytest.raises(SearchIntegrityError, match="instance id already exists"):
        promote_run(work_root, run_root, rules_path=None, force=False)

    target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    assert not target.exists()


def test_promote_run_force_replaces_existing_target(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    promote_run(work_root, run_root, rules_path=None, force=False)
    artifact_instance_path = (
        run_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "artifacts"
        / "instance.json"
    )
    artifact_instance = _load_json(artifact_instance_path)
    artifact_instance["title"] = "Replacement Rotated Surface Code d=3"
    _write_json(artifact_instance_path, artifact_instance)

    summary = promote_run(work_root, run_root, rules_path=None, force=True)

    assert summary["status"] == "completed"
    assert summary["force"] is True
    assert [item["candidate_id"] for item in summary["promoted"]] == ["rotated-surface-d3-example"]
    target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
        / "instance.json"
    )
    assert _load_json(target)["title"] == "Replacement Rotated Surface Code d=3"


def test_promote_run_force_staging_failure_preserves_existing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import autoqec_search.promote as promote_module

    work_root, run_root = _make_finished_run(tmp_path)
    promote_module.promote_run(work_root, run_root, rules_path=None, force=False)
    target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    original_instance = _load_json(target / "instance.json")
    original_write_json = promote_module._write_json

    def fail_first_staging_write(path: Path, payload: dict) -> None:
        if path.name == "instance.json" and "promote-tmp" in path.parent.name:
            raise RuntimeError("staging write failed")
        original_write_json(path, payload)

    monkeypatch.setattr(promote_module, "_write_json", fail_first_staging_write)

    with pytest.raises(SearchIntegrityError, match="staging write failed"):
        promote_module.promote_run(work_root, run_root, rules_path=None, force=True)

    assert target.is_dir()
    assert _load_json(target / "instance.json") == original_instance


def test_promote_run_build_failure_restores_generated_zoo_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import autoqec_search.promote as promote_module

    work_root, run_root = _make_finished_run(tmp_path)
    instance_index_path = work_root / "zoo" / "views" / "instance-index.json"
    original_instance_index = instance_index_path.read_text()

    def corrupt_index_then_fail(zoo_root: Path, *, generated_at: str) -> None:
        instance_index_path.write_text('{"generated_at": "broken", "items": []}\n')
        raise RuntimeError(f"boom while rebuilding {zoo_root.name} at {generated_at}")

    monkeypatch.setattr(promote_module, "build_zoo", corrupt_index_then_fail)

    with pytest.raises(SearchIntegrityError, match="Zoo rebuild failed"):
        promote_module.promote_run(work_root, run_root, rules_path=None, force=False)

    target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    assert not target.exists()
    assert instance_index_path.read_text() == original_instance_index
    summary = _load_json(run_root / "promotion_summary.json")
    assert summary["status"] == "failed"
    assert summary["rules"] == {
        "min_distance": 3,
        "max_ler_at_p": {"p": 0.01, "ler": 0.5},
        "require_distance_verified": True,
        "require_reference_check": False,
    }
    assert summary["force"] is False
    assert "boom while rebuilding zoo" in summary["failures"][0]["reason"]


def test_promote_run_force_build_failure_restores_target_and_generated_zoo_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import autoqec_search.promote as promote_module

    work_root, run_root = _make_finished_run(tmp_path)
    promote_module.promote_run(work_root, run_root, rules_path=None, force=False)

    target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    target_instance_path = target / "instance.json"
    instance_index_path = work_root / "zoo" / "views" / "instance-index.json"
    card_path = work_root / "zoo" / "codes" / "rotated-surface-code" / "card.md"
    app_js_path = work_root / "zoo" / "views" / "site" / "assets" / "app.js"

    original_target_instance = _load_json(target_instance_path)
    original_instance_index = instance_index_path.read_text()
    original_card = card_path.read_text()
    original_app_js = app_js_path.read_text()

    artifact_instance_path = (
        run_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "artifacts"
        / "instance.json"
    )
    artifact_instance = _load_json(artifact_instance_path)
    artifact_instance["title"] = "Replacement before failed rebuild"
    _write_json(artifact_instance_path, artifact_instance)

    def corrupt_generated_outputs_then_fail(zoo_root: Path, *, generated_at: str) -> None:
        instance_index_path.write_text('{"generated_at": "broken", "items": []}\n')
        card_path.write_text("# Broken card\n")
        app_js_path.write_text(f"throw new Error('broken {zoo_root.name} {generated_at}');\n")
        raise RuntimeError("boom")

    monkeypatch.setattr(promote_module, "build_zoo", corrupt_generated_outputs_then_fail)

    with pytest.raises(SearchIntegrityError, match="Zoo rebuild failed"):
        promote_module.promote_run(work_root, run_root, rules_path=None, force=True)

    assert _load_json(target_instance_path) == original_target_instance
    assert instance_index_path.read_text() == original_instance_index
    assert card_path.read_text() == original_card
    assert app_js_path.read_text() == original_app_js
    assert not list(work_root.glob(".zoo.generated-snapshot-*"))
    assert not list((work_root / "zoo").glob(".zoo.generated-snapshot-*"))

    summary = _load_json(run_root / "promotion_summary.json")
    assert summary["status"] == "failed"
    assert summary["force"] is True
    assert summary["rules"] == {
        "min_distance": 3,
        "max_ler_at_p": {"p": 0.01, "ler": 0.5},
        "require_distance_verified": True,
        "require_reference_check": False,
    }
    assert "boom" in summary["failures"][0]["reason"]
    assert summary["promoted"] == []
    assert summary["skipped"] == []


def test_promote_cli_copies_instance(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    work_root, run_root = _make_finished_run(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "promote",
            "--root",
            str(work_root),
            "--run",
            str(run_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "promotion complete for rotated-surface-baseline/finished: 1 promoted, 0 skipped" in result.stdout


def test_promote_cli_resolves_relative_run_under_root_from_other_cwd(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    work_root, _run_root = _make_finished_run(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "promote",
            "--root",
            str(work_root),
            "--run",
            "results/search/rotated-surface-baseline/finished",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "promotion complete for rotated-surface-baseline/finished: 1 promoted, 0 skipped" in result.stdout
