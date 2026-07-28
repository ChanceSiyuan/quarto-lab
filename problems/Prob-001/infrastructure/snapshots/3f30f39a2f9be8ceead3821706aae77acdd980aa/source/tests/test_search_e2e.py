from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from autoqec_search.load import load_search_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_RUN_ID = "m1-demo"
CAMPAIGN_ID = "rotated-surface-baseline"
CANDIDATE_ID = "rotated-surface-d3-example"
CANDIDATE_IDS = [
    "rotated-surface-d3-example",
    "rotated-surface-d5-example",
    "rotated-surface-d7-example",
]
EXPECTED_DISTANCES = [3, 5, 7]
EXPECTED_P_VALUES = [0.008, 0.009, 0.01, 0.011, 0.012]
TASK_ID = "rotated-memory-z-cdep-v1"
DECODER_ID = "rmatching-default-v1"
DEMO_RUN_ROOT = REPO_ROOT / "results" / "search" / CAMPAIGN_ID / DEMO_RUN_ID


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _candidate_manifest(candidate_id: str) -> dict[str, Any]:
    return _load_json(
        DEMO_RUN_ROOT
        / "candidates"
        / candidate_id
        / "evaluations"
        / TASK_ID
        / DECODER_ID
        / "manifest.json"
    )


def _demo_manifest() -> dict[str, Any]:
    return _candidate_manifest(CANDIDATE_ID)


def _point_at_p(manifest: dict[str, Any], p_value: float) -> dict[str, Any]:
    for point in manifest["points"]:
        if math.isclose(
            float(point["p"]),
            float(p_value),
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            return point
    raise AssertionError(f"missing p={p_value} point in M1 demo manifest")


def _leaderboard_rows() -> list[dict[str, str]]:
    with (DEMO_RUN_ROOT / "leaderboard.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def _assert_no_local_workspace_paths(root: Path) -> None:
    forbidden_fragments = (
        "/Users/",
        "issue-13-m1-showcase",
        ".worktrees/m1-demo",
        "nzydeMac-mini.local",
    )
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        for fragment in forbidden_fragments:
            assert fragment not in text, f"{path} contains local path fragment {fragment}"


def test_search_campaign_skill_has_approval_gate_and_example_transcript() -> None:
    skill_path = REPO_ROOT / "skills" / "search-campaign" / "SKILL.md"
    transcript_path = (
        REPO_ROOT
        / "skills"
        / "search-campaign"
        / "examples"
        / "rotated-surface-baseline-intake.md"
    )

    skill = skill_path.read_text()
    transcript = transcript_path.read_text()

    assert "search-campaign" in skill
    assert "explicit approval" in skill
    assert "must not write" in skill
    assert "campaign.json" in skill
    assert "search_space.json" in skill
    assert "promote_rules.json" in skill
    assert "autoqec_search.cli validate" in skill
    assert "rotated-surface-code" in skill
    assert "default_suite_id" in skill
    assert "family_id" in skill
    assert "surface-code" in skill
    assert "code_family" in skill
    assert "benchmarks/suites/*.json" in skill
    assert "benchmark task defaults" in skill

    assert "wait, do not write anything yet" in transcript
    assert "No campaign files are written." in transcript
    assert "Approved. Write the campaign files." in transcript
    assert "validation passes" in transcript
    assert "family_id: surface-code" in transcript
    assert "code_family: rotated-surface-code" in transcript
    assert "family_id: rotated-surface-code" not in transcript
    assert "family: rotated-surface-code" not in transcript.replace(
        "code_family: rotated-surface-code",
        "",
    )
    assert "suite defaults" in transcript

    wait_index = transcript.index("wait, do not write anything yet")
    no_write_index = transcript.index("No campaign files are written.")
    approval_index = transcript.index("Approved. Write the campaign files.")
    validation_index = transcript.index("validation passes")
    assert wait_index < no_write_index < approval_index < validation_index


def test_m1_demo_run_loads_and_matches_parameter_sweep() -> None:
    workspace = load_search_workspace(REPO_ROOT)
    run_key = f"{CAMPAIGN_ID}/{DEMO_RUN_ID}"
    assert run_key in workspace.runs, f"missing committed M1 demo run at {DEMO_RUN_ROOT}"
    run = workspace.runs[run_key]

    assert run.payload["mode"] == "autoresearch"
    assert run.payload["run_id"] == DEMO_RUN_ID
    assert run.payload["candidate_ids"] == CANDIDATE_IDS

    run_status = _load_json(DEMO_RUN_ROOT / "run_status.json")
    assert run_status["status"] == "finalized"
    assert run_status["run_id"] == DEMO_RUN_ID
    assert run_status["frontier_size"] == 3

    for candidate_id, distance in zip(CANDIDATE_IDS, EXPECTED_DISTANCES, strict=True):
        candidate_root = DEMO_RUN_ROOT / "candidates" / candidate_id
        for artifact_name in ("instance.json", "hx.json", "hz.json"):
            assert (candidate_root / "artifacts" / artifact_name).is_file()
        assert _load_json(candidate_root / "distance.json")["distance"] == distance
        candidate_manifest = _candidate_manifest(candidate_id)
        assert candidate_manifest["status"] == "completed"
        assert candidate_manifest["candidate_id"] == candidate_id
        assert candidate_manifest["task_id"] == TASK_ID
        assert candidate_manifest["decoder_id"] == DECODER_ID
        assert [point["p"] for point in candidate_manifest["points"]] == EXPECTED_P_VALUES
        assert [point["rounds"] for point in candidate_manifest["points"]] == [
            distance * 3
        ] * len(EXPECTED_P_VALUES)

    manifest = _demo_manifest()
    assert manifest["status"] == "completed"
    assert manifest["candidate_id"] == CANDIDATE_ID
    assert manifest["task_id"] == TASK_ID
    assert manifest["decoder_id"] == DECODER_ID

    frontier = _load_json(DEMO_RUN_ROOT / "frontier.json")
    assert frontier["campaign_id"] == CAMPAIGN_ID
    assert frontier["run_id"] == DEMO_RUN_ID
    frontier_by_candidate = {item["candidate_id"]: item for item in frontier["items"]}
    assert set(frontier_by_candidate) == set(CANDIDATE_IDS)

    rows = _leaderboard_rows()
    rows_by_candidate = {row["candidate_id"]: row for row in rows}
    assert set(CANDIDATE_IDS).issubset(rows_by_candidate)
    for candidate_id in CANDIDATE_IDS:
        keep_row = rows_by_candidate[candidate_id]
        frontier_item = frontier_by_candidate[candidate_id]
        assert keep_row["status"] == "keep"
        assert keep_row["decoder_id"] == DECODER_ID
        assert keep_row["manifest_path"] == frontier_item["manifest_path"]
        assert TASK_ID in keep_row["manifest_path"]
        assert DECODER_ID in keep_row["manifest_path"]
        assert math.isclose(float(keep_row["p"]), frontier_item["p"], rel_tol=0.0, abs_tol=1e-15)
        frontier_point = _point_at_p(_candidate_manifest(candidate_id), frontier_item["p"])
        assert math.isclose(float(keep_row["ler"]), frontier_point["ler"], rel_tol=1e-10, abs_tol=1e-15)


def test_m1_demo_report_and_promotion_are_visible() -> None:
    report_path = DEMO_RUN_ROOT / "report.html"
    assert report_path.is_file()
    report = report_path.read_text()

    assert "AutoQEC Search Report" in report
    for candidate_id in CANDIDATE_IDS:
        assert candidate_id in report
    for p_value in EXPECTED_P_VALUES:
        assert str(p_value) in report
    assert "http://" not in report
    assert "https://" not in report
    _assert_no_local_workspace_paths(DEMO_RUN_ROOT)
    assert _load_json(DEMO_RUN_ROOT / "env.json")["host"] == "committed-m1-demo"

    promotion_summary = _load_json(DEMO_RUN_ROOT / "promotion_summary.json")
    assert promotion_summary["status"] == "completed"
    promoted_ids = {item["candidate_id"] for item in promotion_summary["promoted"]}
    assert set(CANDIDATE_IDS).issubset(promoted_ids)

    for candidate_id in CANDIDATE_IDS:
        instance_root = (
            REPO_ROOT
            / "zoo"
            / "codes"
            / "rotated-surface-code"
            / "instances"
            / candidate_id
        )
        for artifact_name in ("instance.json", "hx.json", "hz.json"):
            assert (instance_root / artifact_name).is_file()

    instance_path = instance_root / "instance.json"
    promoted_instance = _load_json(instance_path)
    assert promoted_instance["id"] in CANDIDATE_IDS
    assert promoted_instance["provenance"]["source_run"] == f"{CAMPAIGN_ID}/{DEMO_RUN_ID}"

    instance_index = _load_json(REPO_ROOT / "zoo" / "views" / "instance-index.json")
    indexed_ids = {item["id"] for item in instance_index["items"]}
    assert set(CANDIDATE_IDS).issubset(indexed_ids)

    browse = (REPO_ROOT / "zoo" / "views" / "browse.md").read_text()
    for candidate_id in CANDIDATE_IDS:
        assert candidate_id in browse


def test_issue16_bb_css_validation_artifact_records_deferred_osd10_gap() -> None:
    run_root = (
        REPO_ROOT
        / "results"
        / "search"
        / "decoder-registry-css-bb-smoke"
        / "issue16-bb-css-validation"
    )
    candidate_root = run_root / "candidates" / "bivariate-bicycle-code-m6-n6"
    task_id = "bb-css-memory-x-cdep-v1"

    osd0 = _load_json(
        candidate_root / "evaluations" / task_id / "rbposd-osd0-v1" / "manifest.json"
    )
    osd10 = _load_json(
        candidate_root / "evaluations" / task_id / "rbposd-osd10-v1" / "manifest.json"
    )
    zero = _load_json(
        candidate_root / "evaluations" / task_id / "predict-zero-v1" / "manifest.json"
    )

    assert osd0["status"] == "completed"
    assert osd10["status"] == "placeholder"
    assert zero["status"] == "completed"
    assert osd0["decoder_parameters"]["osd_order"] == 0
    assert osd10.get("points") is None
    assert 0.35 <= zero["points"][0]["ler"] <= 0.65

    for decoder_id in ("rbposd-osd0-v1", "predict-zero-v1"):
        row_path = candidate_root / "rsinter" / "out" / decoder_id / "test-run" / "results.jsonl"
        assert row_path.is_file()
        row = json.loads(row_path.read_text().splitlines()[0])
        assert row["params"]["input_type"] == "css"
        assert row["params"]["code_id"] == "bivariate-bicycle-code-m6-n6"
        assert row["params"]["hx"] == "../artifacts/hx.sparse_rows.json"
        assert row["params"]["hz"] == "../artifacts/hz.sparse_rows.json"
    assert not (
        candidate_root
        / "rsinter"
        / "out"
        / "rbposd-osd10-v1"
        / "test-run"
        / "results.jsonl"
    ).exists()


def test_bb72_campaign_fake_light_e2e(tmp_path: Path, monkeypatch) -> None:
    import shutil

    from autoqec_search.cli import main

    root = tmp_path / "work"
    for name in ("benchmarks", "campaigns", "zoo"):
        shutil.copytree(Path(__file__).resolve().parents[1] / name, root / name)
    (root / "results" / "search").mkdir(parents=True)

    def fake_require_rsinter() -> tuple[str, str]:
        return "/bin/rsinter", "rsinter fake bb72"

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        spec_text = spec_path.read_text()
        assert 'observables = "input/observables.css.json"' in spec_text
        assert "seed = 12345" in spec_text
        for runner, errors in [
            ("rbposd-bb72-osd1-v1", 0),
            ("predict-zero-v1", 48),
        ]:
            result_path = out_dir / runner / "test-run" / "results.jsonl"
            result_path.parent.mkdir(parents=True)
            rows = []
            for p in [0.003, 0.01]:
                rows.append(
                    {
                        "benchmark": "autoqec-bb-css-memory-x-cdep-v1",
                        "runner": runner,
                        "language": "rust",
                        "status": "ok",
                        "params": {
                            "input_type": "css",
                            "code_id": "bivariate-bicycle-code-m6-n6",
                            "hx": "input/hx.css.json",
                            "hz": "input/hz.css.json",
                            "observables": "input/observables.css.json",
                            "basis": "x",
                            "schedule": "greedy",
                            "rounds": 3,
                            "p": p,
                            "seed": 12345,
                            "decoder_impl": (
                                "rbposd" if runner.startswith("rbposd") else "predict-zero"
                            ),
                            "logical_observable_source": "explicit",
                            "logical_observable_basis": "x",
                            "logical_failure_aggregation": "any_logical",
                            "logical_observable_count": 12,
                            **(
                                {
                                    "bp_algorithm": "min_sum",
                                    "bp_iters": 50,
                                    "early_stop": True,
                                    "osd_method": "combination_sweep",
                                    "osd_order": 1,
                                }
                                if runner.startswith("rbposd")
                                else {}
                            ),
                        },
                        "case_summary": {},
                        "metrics": {
                            "shots_used": 64,
                            "logical_errors": (
                                0
                                if runner.startswith("rbposd") and p == 0.003
                                else 32
                                if runner.startswith("rbposd")
                                else errors
                            ),
                            "logical_error_rate": (
                                0
                                if runner.startswith("rbposd") and p == 0.003
                                else 32 / 64
                                if runner.startswith("rbposd")
                                else errors / 64
                            ),
                        },
                        "artifacts": {},
                        "error": None,
                    }
                )
            result_path.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
            )

    monkeypatch.setattr("autoqec_search.run_loop.require_rsinter", fake_require_rsinter)
    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fake_run_rsinter)
    monkeypatch.setattr("autoqec_search.run_loop.git_status_porcelain", lambda _root: " M fake")
    monkeypatch.setattr(
        "autoqec_search.run_loop.create_or_resume_worktree",
        lambda root, tag, resume, allow_dirty_root: (root, f"autoresearch/{tag}"),
    )
    monkeypatch.setattr("autoqec_search.run_loop.git_commit_all", lambda _root, _message: False)
    monkeypatch.setattr("autoqec_search.run_loop.git_head_sha", lambda _root: "0" * 40)

    assert (
        main(
            [
                "run",
                "--root",
                str(root),
                "--campaign",
                "bb72-qldpc-campaign",
                "--run-id",
                "fake-bb72",
                "--allow-dirty-root",
            ]
        )
        == 0
    )
    run_root = root / "results" / "search" / "bb72-qldpc-campaign" / "fake-bb72"
    assert (run_root / "leaderboard.csv").is_file()
    assert json.loads((run_root / "frontier.json").read_text())["items"][0]["distance"] == 6
    assert not (run_root / "reference_check.json").exists()

    assert main(["report", "--root", str(root), "--run", str(run_root)]) == 0
    assert "Reference check" in (run_root / "report.html").read_text()

    assert main(["promote", "--root", str(root), "--run", str(run_root), "--force"]) == 0
    target = (
        root
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    assert (target / "observables_x.json").is_file()
    assert "bivariate-bicycle-code-m6-n6" in (root / "zoo" / "views" / "browse.md").read_text()
