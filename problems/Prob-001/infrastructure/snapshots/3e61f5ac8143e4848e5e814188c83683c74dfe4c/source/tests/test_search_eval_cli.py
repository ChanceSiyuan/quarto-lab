from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import csv
import io
import pytest

from autoqec_search import eval_run as eval_run_module
from autoqec_search.load import load_search_workspace
from autoqec_search.render import render_eval_leaderboard


REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_search_tree(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    shutil.copytree(REPO_ROOT / "zoo", work_root / "zoo")
    return work_root


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_fake_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import json
import sys
from pathlib import Path
import tomllib

if sys.argv[1:] == ["--version"]:
    print("rsinter git main abc123")
    raise SystemExit(0)

args = sys.argv[1:]
if args[:2] != ["bench", "run"]:
    raise SystemExit(2)

spec_path = Path(args[args.index("--spec") + 1])
out_dir = Path(args[args.index("--out") + 1])
spec = tomllib.loads(spec_path.read_text())
for runner in spec.get("runner", []):
    decoder_id = runner["name"]
    params = runner["params"]
    results_dir = out_dir / decoder_id / "test-run"
    results_dir.mkdir(parents=True, exist_ok=True)
    records = []
    rounds = int(params["rounds"][0])
    input_type = params.get("input_type")
    is_css = input_type == "css"
    if is_css:
        hx_path = spec_path.parent / params["hx"]
        hz_path = spec_path.parent / params["hz"]
        hx_wrapper = json.loads(hx_path.read_text())
        hz_wrapper = json.loads(hz_path.read_text())
        assert hx_wrapper["format"] == "dense"
        assert hz_wrapper["format"] == "dense"
        assert "distance" not in params
    else:
        distance = int(params["distance"][0])
    for index, p in enumerate(params["p"]):
        p = float(p)
        row_params = dict(params)
        row_params["rounds"] = rounds
        row_params["p"] = p
        if not is_css:
            row_params["distance"] = distance
        if is_css and p == 0.005:
            shots = 82329
            errors = 1000
            decode_us_per_shot = 0.304844225
            num_shots_generated = 82336
        elif p in (0.005, 0.01):
            shots = 76533
            errors = 1000
            decode_us_per_shot = 0.29047292017822396
            num_shots_generated = 76544
        else:
            shots = 1000
            errors = max(1, round(p * shots))
            decode_us_per_shot = 250.0 + index
            num_shots_generated = shots
        records.append(
            json.dumps(
                {{
                    "benchmark": spec["name"],
                    "runner": decoder_id,
                    "language": runner["language"],
                    "status": "ok",
                    "params": row_params,
                    "case_summary": {{
                        "num_dets": 8,
                        "num_obs": 1,
                        "num_shots_generated": num_shots_generated,
                    }},
                    "metrics": {{
                        "shots_used": shots,
                        "logical_errors": errors,
                        "logical_error_rate": errors / shots,
                        "decode_us_per_shot": decode_us_per_shot,
                    }},
                    "artifacts": {{}},
                    "error": None,
                }},
                sort_keys=True,
            )
        )
    (results_dir / "results.jsonl").write_text("\\n".join(records) + "\\n")
raise SystemExit(0)
"""
    )
    executable.chmod(0o755)
    return bin_dir


def _write_failing_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "failing-bin"
    bin_dir.mkdir()
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import sys

if sys.argv[1:] == ["--version"]:
    print("rsinter git main abc123")
    raise SystemExit(0)

print("backend failed", file=sys.stderr)
raise SystemExit(7)
"""
    )
    executable.chmod(0o755)
    return bin_dir


def _write_old_css_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "old-css-bin"
    bin_dir.mkdir()
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import sys

if sys.argv[1:] == ["--version"]:
    print("rsinter git main oldcss")
    raise SystemExit(0)

print("unknown field `input_type` in runner params", file=sys.stderr)
raise SystemExit(7)
"""
    )
    executable.chmod(0o755)
    return bin_dir


def _env_with_rsinter(bin_dir: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }


def _env_without_rsinter(tmp_path: Path) -> dict[str, str]:
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    return {
        **os.environ,
        "PATH": str(empty_bin),
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }


def _run_eval(work_root: Path, env: dict[str, str], *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "eval",
            "--root",
            str(work_root),
            *extra,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def test_render_eval_leaderboard_quotes_csv_fields_with_commas() -> None:
    csv_text = render_eval_leaderboard(
        [
            {
                "candidate_id": "candidate,comma",
                "task_id": "task,comma",
                "decoder_id": "decoder,comma",
                "status": "completed",
                "points": [
                    {
                        "p": 0.005,
                        "rounds": 3,
                        "shots": 1000,
                        "errors": 5,
                        "seconds": 0.25,
                        "ler": 0.005,
                        "ci_low": 0.002,
                        "ci_high": 0.011,
                    }
                ],
            }
        ]
    )

    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[0] == [
        "candidate_id",
        "task_id",
        "decoder_id",
        "decoder_parameters",
        "p",
        "shots",
        "errors",
        "ler",
        "ci_low",
        "ci_high",
        "status",
    ]
    assert rows[1] == [
        "candidate,comma",
        "task,comma",
        "decoder,comma",
        "{}",
        "0.005",
        "1000",
        "5",
        "0.005",
        "0.002",
        "0.011",
        "completed",
    ]


def test_eval_campaign_candidate_writes_completed_selected_manifest_and_plot(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "test-eval",
    )

    assert result.returncode == 0, result.stderr
    assert "evaluated candidate rotated-surface-d3-example" in result.stdout

    run_root = (
        work_root / "results" / "search" / "rotated-surface-baseline" / "test-eval"
    )
    candidate_root = run_root / "candidates" / "rotated-surface-d3-example"
    assert sorted(path.name for path in run_root.iterdir()) == [
        "candidates",
        "env.json",
        "frontier.json",
        "leaderboard.csv",
        "run_spec.json",
        "summary.md",
    ]
    assert sorted(path.name for path in candidate_root.iterdir()) == [
        "artifacts",
        "candidate-plot.svg",
        "candidate.json",
        "distance.json",
        "evaluations",
        "rsinter",
        "structure.json",
    ]
    assert sorted(path.name for path in (candidate_root / "artifacts").iterdir()) == [
        "hx.json",
        "hz.json",
        "instance.json",
    ]

    run_spec = _load_json(run_root / "run_spec.json")
    assert run_spec["mode"] == "eval"
    assert run_spec["candidate_ids"] == ["rotated-surface-d3-example"]
    assert run_spec["task_ids"] == ["rotated-memory-z-cdep-v1"]
    assert run_spec["decoder_ids"] == [
        "rmatching-default-v1",
        "rbposd-default-v1",
        "rbposd-osd0-v1",
        "rbposd-osd10-v1",
        "rilpqec-default-v1",
    ]

    structure = _load_json(candidate_root / "structure.json")
    assert structure["status"] == "completed"
    assert structure["css_commute"] is True
    assert structure["k"] == 1

    distance = _load_json(candidate_root / "distance.json")
    assert distance["distance"] == 3
    assert distance["method"] == "copied-zoo-exact"
    assert distance["bound_type"] == "exact"
    assert distance["options"] == {
        "method": "copied-zoo-exact",
        "qec_code_bin": "qec-code",
    }
    assert distance["provenance"] == {
        "source": "zoo-instance",
        "source_instance_id": "rotated-surface-code-d3",
        "source_instance_path": str(
            work_root
            / "zoo"
            / "codes"
            / "rotated-surface-code"
            / "instances"
            / "rotated-surface-code-d3"
        ),
    }

    summary = (run_root / "summary.md").read_text()
    assert "# Search Eval Summary" in summary
    assert "- candidate: `rotated-surface-d3-example`" in summary
    assert "- distance: `3`" in summary
    assert "- n: `9`" in summary
    assert "- k: `1`" in summary
    assert "- css_commute: `true`" in summary

    completed_manifest = _load_json(
        candidate_root
        / "evaluations"
        / "rotated-memory-z-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    assert completed_manifest["status"] == "completed"
    point = completed_manifest["points"][0]
    assert point["p"] == 0.01
    assert point["shots"] == 76533
    assert point["errors"] == 1000
    assert point["ler"] == pytest.approx(1000 / 76533)
    assert point["seconds"] == pytest.approx(0.022230764000000014)

    expected = _load_json(
        work_root / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json"
    )
    assert expected["binomial_ci_95"]["lower"] <= point["ler"]
    assert point["ler"] <= expected["binomial_ci_95"]["upper"]

    for decoder_id in ("rbposd-default-v1", "rilpqec-default-v1"):
        manifest = _load_json(
            candidate_root
            / "evaluations"
            / "rotated-memory-z-cdep-v1"
            / decoder_id
            / "manifest.json"
        )
        assert manifest["status"] == "placeholder"
        assert manifest["metrics"] == {"logical_error_rate": None}

    spec_text = (candidate_root / "rsinter" / "spec.toml").read_text()
    assert 'name = "autoqec-rotated-memory-z-cdep-v1"' in spec_text
    assert 'name = "rmatching-default-v1"' in spec_text
    assert 'name = "rbposd-default-v1"' not in spec_text
    assert "batch_size = 256" in spec_text
    assert "[plot]" in spec_text
    assert "p = [0.01]" in spec_text
    leaderboard = (run_root / "leaderboard.csv").read_text()
    assert leaderboard.splitlines()[0] == (
        "candidate_id,task_id,decoder_id,decoder_parameters,p,shots,errors,ler,ci_low,ci_high,status"
    )
    assert (
        "rotated-surface-d3-example,rotated-memory-z-cdep-v1,"
        "rmatching-default-v1,{},0.01,76533,1000,0.013066258999385886,"
    ) in leaderboard
    assert (
        candidate_root
        / "rsinter"
        / "out"
        / "rmatching-default-v1"
        / "test-run"
        / "results.jsonl"
    ).is_file()

    plot = (candidate_root / "candidate-plot.svg").read_text()
    assert "rmatching-default-v1" in plot
    assert "rbposd-default-v1" not in plot
    assert plot.endswith("</svg>\n")

    workspace = load_search_workspace(work_root)
    loaded = workspace.runs["rotated-surface-baseline/test-eval"]
    assert loaded.payload["mode"] == "eval"
    assert loaded.candidates["rotated-surface-d3-example"].manifests[
        ("rotated-memory-z-cdep-v1", "rmatching-default-v1")
    ]["status"] == "completed"


def test_eval_general_css_fixture_statistically_matches_rotated_d3_golden(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-css-fixture",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.005",
        "--run-id",
        "css-fixture",
        "--general-css",
    )

    assert result.returncode == 0, result.stderr

    candidate_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-css-fixture"
        / "css-fixture"
        / "candidates"
        / "rotated-surface-d3-example"
    )
    input_dir = candidate_root / "rsinter" / "input"
    assert sorted(path.name for path in input_dir.iterdir()) == [
        "hx.css.json",
        "hz.css.json",
    ]
    assert _load_json(input_dir / "hx.css.json")["format"] == "dense"
    assert _load_json(input_dir / "hz.css.json")["format"] == "dense"

    spec_text = (candidate_root / "rsinter" / "spec.toml").read_text()
    assert 'input_type = "css"' in spec_text
    assert 'code_id = "rotated-surface-code"' in spec_text
    assert 'hx = "input/hx.css.json"' in spec_text
    assert 'hz = "input/hz.css.json"' in spec_text
    assert 'basis = "x"' in spec_text
    assert 'schedule = "greedy"' in spec_text
    assert "distance = [" not in spec_text

    completed_manifest = _load_json(
        candidate_root
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    expected = _load_json(
        work_root / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json"
    )
    point = completed_manifest["points"][0]
    expected_ci = expected["binomial_ci_95"]
    assert completed_manifest["task_id"] == expected["task_id"]
    assert point["p"] == expected["p"]
    assert point["ci_high"] >= expected_ci["lower"]
    assert point["ci_low"] <= expected_ci["upper"]


def test_eval_general_css_baseline_uses_task_observable_for_basis_z(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.008",
        "--run-id",
        "css-baseline",
        "--general-css",
    )

    assert result.returncode == 0, result.stderr

    spec_text = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "css-baseline"
        / "candidates"
        / "rotated-surface-d3-example"
        / "rsinter"
        / "spec.toml"
    ).read_text()
    assert 'input_type = "css"' in spec_text
    assert 'basis = "z"' in spec_text


def test_eval_general_css_old_backend_reports_required_upstream_support(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)

    result = _run_eval(
        work_root,
        _env_with_rsinter(_write_old_css_rsinter(tmp_path)),
        "--campaign",
        "rotated-surface-css-fixture",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.005",
        "--run-id",
        "old-css-backend",
        "--general-css",
    )

    assert result.returncode == 1
    assert "upstream rstim general CSS support from #46 / #51 is required" in result.stderr


def test_eval_css_fixture_without_general_css_preserves_backend_input_type_error(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)

    result = _run_eval(
        work_root,
        _env_with_rsinter(_write_old_css_rsinter(tmp_path)),
        "--campaign",
        "rotated-surface-css-fixture",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.005",
        "--run-id",
        "old-backend-no-css-flag",
    )

    assert result.returncode == 1
    assert "unknown field `input_type` in runner params" in result.stderr
    assert "upstream rstim general CSS support" not in result.stderr


def test_eval_missing_rsinter_fails_without_creating_run(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)

    result = _run_eval(
        work_root,
        _env_without_rsinter(tmp_path),
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "missing-rsinter",
    )

    assert result.returncode == 1
    assert "rsinter not found on PATH" in result.stderr
    assert not (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "missing-rsinter"
    ).exists()


def test_eval_invalid_decoder_filter_fails_before_rsinter(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)

    result = _run_eval(
        work_root,
        _env_without_rsinter(tmp_path),
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "missing-decoder",
        "--p",
        "0.01",
        "--run-id",
        "bad-decoder",
    )

    assert result.returncode == 1
    assert "decoder filter not in suite: missing-decoder" in result.stderr
    assert not (
        work_root / "results" / "search" / "rotated-surface-baseline" / "bad-decoder"
    ).exists()


def test_eval_invalid_p_filter_fails_before_rsinter(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)

    result = _run_eval(
        work_root,
        _env_without_rsinter(tmp_path),
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.123",
        "--run-id",
        "bad-p",
    )

    assert result.returncode == 1
    assert "p filter not in task p_list" in result.stderr
    assert not (
        work_root / "results" / "search" / "rotated-surface-baseline" / "bad-p"
    ).exists()


def test_eval_directory_candidate_uses_external_id_and_zoo_artifacts(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    source = tmp_path / "external-candidate"
    _write_json(
        source / "candidate.json",
        {
            "candidate_id": "external-d3",
            "campaign_id": "rotated-surface-baseline",
            "run_id": "source-run",
            "code_family": "rotated-surface-code",
            "parameters": {"distance": 3, "layout": "rotated"},
            "provenance": {"kind": "external", "label": "tmp"},
            "status": "evaluated",
        },
    )
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-baseline",
        "--candidate",
        str(source),
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "external-eval",
    )

    assert result.returncode == 0, result.stderr
    assert "evaluated candidate external-d3" in result.stdout

    candidate_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "external-eval"
        / "candidates"
        / "external-d3"
    )
    candidate = _load_json(candidate_root / "candidate.json")
    assert candidate["candidate_id"] == "external-d3"
    assert candidate["status"] == "evaluated"
    assert (candidate_root / "artifacts" / "instance.json").is_file()
    distance = _load_json(candidate_root / "distance.json")
    assert distance["source_instance_id"] == "rotated-surface-code-d3"


def test_eval_rstim_exact_backend_unavailable_is_clear(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "missing-rstim-exact",
        "--distance-method",
        "rstim-ilp-exact",
        "--qec-code-bin",
        "/definitely/missing/qec-code",
    )

    assert result.returncode == 1
    assert "rstim exact CSS distance backend is not available" in result.stderr
    assert not (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "missing-rstim-exact"
    ).exists()


def test_eval_noncommuting_candidate_fails_before_requiring_rsinter(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    source = tmp_path / "noncommuting-candidate"
    _write_json(
        source / "candidate.json",
        {
            "candidate_id": "noncommuting-d3",
            "campaign_id": "rotated-surface-baseline",
            "run_id": "source-run",
            "code_family": "rotated-surface-code",
            "parameters": {"distance": 3, "layout": "rotated"},
            "provenance": {"kind": "external", "label": "tmp"},
            "status": "evaluated",
        },
    )
    shutil.copytree(
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3",
        source / "artifacts",
    )
    hz = _load_json(source / "artifacts" / "hz.json")
    hz["data"][0][2] = 1
    _write_json(source / "artifacts" / "hz.json", hz)

    result = _run_eval(
        work_root,
        _env_without_rsinter(tmp_path),
        "--campaign",
        "rotated-surface-baseline",
        "--candidate",
        str(source),
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "noncommuting-no-rsinter",
    )

    assert result.returncode == 1
    assert "candidate CSS checks do not commute: noncommuting-d3" in result.stderr
    assert "rsinter not found on PATH" not in result.stderr
    structure_path = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "noncommuting-no-rsinter"
        / "candidates"
        / "noncommuting-d3"
        / "structure.json"
    )
    assert structure_path.is_file()
    assert _load_json(structure_path)["css_commute"] is False


def test_eval_rejects_existing_run_id_unless_forced(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))
    run_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "replace-me"
    )
    run_root.mkdir(parents=True)
    (run_root / "sentinel.txt").write_text("old\n")

    rejected = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "replace-me",
    )

    assert rejected.returncode == 1
    assert "run already exists" in rejected.stderr
    assert (run_root / "sentinel.txt").is_file()

    forced = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "replace-me",
        "--force",
    )

    assert forced.returncode == 0, forced.stderr
    assert "evaluated candidate rotated-surface-d3-example" in forced.stdout
    assert not (run_root / "sentinel.txt").exists()
    assert (run_root / "run_spec.json").is_file()


def test_eval_uses_copied_instance_distance_for_rsinter_and_plot(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    instance_path = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "instance.json"
    )
    instance = _load_json(instance_path)
    instance["derived_properties"]["distance"] = 5
    _write_json(instance_path, instance)
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "copied-distance",
    )

    assert result.returncode == 0, result.stderr
    candidate_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "copied-distance"
        / "candidates"
        / "rotated-surface-d3-example"
    )
    assert _load_json(candidate_root / "distance.json")["distance"] == 5
    spec_text = (candidate_root / "rsinter" / "spec.toml").read_text()
    assert "distance = [5]" in spec_text
    assert "rounds = [15]" in spec_text
    assert "distance=5" in (candidate_root / "candidate-plot.svg").read_text()


def test_eval_rejects_candidate_id_that_is_not_path_segment(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    source = tmp_path / "external-candidate"
    _write_json(
        source / "candidate.json",
        {
            "candidate_id": "../../escaped-candidate",
            "campaign_id": "rotated-surface-baseline",
            "run_id": "source-run",
            "code_family": "rotated-surface-code",
            "parameters": {"distance": 3, "layout": "rotated"},
            "provenance": {"kind": "external", "label": "tmp"},
            "status": "evaluated",
        },
    )

    result = _run_eval(
        work_root,
        _env_with_rsinter(_write_fake_rsinter(tmp_path)),
        "--campaign",
        "rotated-surface-baseline",
        "--candidate",
        str(source),
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "bad-candidate-id",
    )

    assert result.returncode == 1
    assert "candidate_id must be a single path segment" in result.stderr
    assert not (
        work_root / "results" / "search" / "rotated-surface-baseline" / "escaped-candidate"
    ).exists()


def test_eval_rejects_candidate_id_with_control_character(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    source = tmp_path / "external-candidate"
    _write_json(
        source / "candidate.json",
        {
            "candidate_id": "bad\u0000id",
            "campaign_id": "rotated-surface-baseline",
            "run_id": "source-run",
            "code_family": "rotated-surface-code",
            "parameters": {"distance": 3, "layout": "rotated"},
            "provenance": {"kind": "external", "label": "tmp"},
            "status": "evaluated",
        },
    )

    result = _run_eval(
        work_root,
        _env_with_rsinter(_write_fake_rsinter(tmp_path)),
        "--campaign",
        "rotated-surface-baseline",
        "--candidate",
        str(source),
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "bad-control-id",
    )

    assert result.returncode == 1
    assert "candidate_id must be a single path segment" in result.stderr
    assert "Traceback" not in result.stderr


def test_eval_rejects_campaign_id_that_is_not_path_segment(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    campaign_path = (
        work_root
        / "campaigns"
        / "examples"
        / "rotated-surface-baseline"
        / "campaign.json"
    )
    search_space_path = campaign_path.with_name("search_space.json")
    campaign = _load_json(campaign_path)
    campaign["id"] = "../../../escaped-campaign"
    _write_json(campaign_path, campaign)
    search_space = _load_json(search_space_path)
    search_space["campaign_id"] = "../../../escaped-campaign"
    _write_json(search_space_path, search_space)

    result = _run_eval(
        work_root,
        _env_with_rsinter(_write_fake_rsinter(tmp_path)),
        "--campaign",
        "../../../escaped-campaign",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "bad-campaign-id",
    )

    assert result.returncode == 1
    assert "campaign_id must be a single path segment" in result.stderr
    assert not (work_root.parent / "escaped-campaign").exists()


def test_eval_rejects_task_id_that_is_not_path_segment(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    task_path = work_root / "benchmarks" / "tasks" / "rotated-memory-z-cdep-v1.json"
    task = _load_json(task_path)
    task["id"] = "../../../../escaped-task"
    _write_json(task_path, task)

    suite_path = work_root / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
    suite = _load_json(suite_path)
    suite["task_ids"] = ["../../../../escaped-task"]
    _write_json(suite_path, suite)

    result = _run_eval(
        work_root,
        _env_with_rsinter(_write_fake_rsinter(tmp_path)),
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "bad-task-id",
    )

    assert result.returncode == 1
    assert "task_id must be a single path segment" in result.stderr
    assert not (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "bad-task-id"
        / "candidates"
        / "rotated-surface-d3-example"
        / "escaped-task"
    ).exists()


def test_eval_rejects_decoder_id_that_is_not_path_segment(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    decoder_path = work_root / "benchmarks" / "decoders" / "rmatching-default-v1.json"
    decoder = _load_json(decoder_path)
    decoder["id"] = "../../../../escaped-decoder"
    _write_json(decoder_path, decoder)

    suite_path = work_root / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
    suite = _load_json(suite_path)
    suite["decoder_ids"][0] = "../../../../escaped-decoder"
    _write_json(suite_path, suite)

    css_suite_path = (
        work_root / "benchmarks" / "suites" / "rotated-surface-css-fixture-v1.json"
    )
    css_suite = _load_json(css_suite_path)
    css_suite["decoder_ids"][0] = "../../../../escaped-decoder"
    _write_json(css_suite_path, css_suite)

    result = _run_eval(
        work_root,
        _env_with_rsinter(_write_fake_rsinter(tmp_path)),
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "../../../../escaped-decoder",
        "--p",
        "0.01",
        "--run-id",
        "bad-decoder-id",
    )

    assert result.returncode == 1
    assert "decoder_id must be a single path segment" in result.stderr
    assert not (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "bad-decoder-id"
        / "candidates"
        / "rotated-surface-d3-example"
        / "escaped-decoder"
    ).exists()


def test_install_staged_run_restores_existing_run_when_final_rename_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    sentinel = run_root / "sentinel.txt"
    sentinel.write_text("old\n")
    stage_root = tmp_path / ".run.tmp"
    stage_root.mkdir()
    (stage_root / "run_spec.json").write_text('{"mode": "eval"}\n')

    monkeypatch.setattr(eval_run_module, "_exchange_directories", lambda *_: False)
    original_rename = Path.rename

    def rename_with_final_failure(self: Path, target: Path) -> Path:
        if self == stage_root and Path(target) == run_root:
            raise OSError("simulated final rename failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", rename_with_final_failure)

    with pytest.raises(OSError, match="simulated final rename failure"):
        eval_run_module._install_staged_run(stage_root, run_root)

    assert sentinel.read_text() == "old\n"
    assert stage_root.exists()


def test_eval_force_preserves_existing_run_when_backend_fails(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    success_env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    created = _run_eval(
        work_root,
        success_env,
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "stable-run",
    )
    assert created.returncode == 0, created.stderr

    run_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "stable-run"
    )
    sentinel = run_root / "sentinel.txt"
    sentinel.write_text("old\n")

    failed = _run_eval(
        work_root,
        _env_with_rsinter(_write_failing_rsinter(tmp_path)),
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "stable-run",
        "--force",
    )

    assert failed.returncode == 1
    assert "rsinter bench run exited 7" in failed.stderr
    assert sentinel.read_text() == "old\n"
    assert _load_json(run_root / "run_spec.json")["mode"] == "eval"


def test_eval_force_replaces_malformed_existing_run(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "malformed-run"
    )
    run_root.mkdir(parents=True)
    (run_root / "run_spec.json").write_text('{"not": "a valid run"}\n')

    result = _run_eval(
        work_root,
        _env_with_rsinter(_write_fake_rsinter(tmp_path)),
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "malformed-run",
        "--force",
    )

    assert result.returncode == 0, result.stderr
    assert _load_json(run_root / "run_spec.json")["mode"] == "eval"
