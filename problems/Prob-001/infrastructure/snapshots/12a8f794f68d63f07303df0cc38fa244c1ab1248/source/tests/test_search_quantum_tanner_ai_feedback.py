from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from autoqec_search import quantum_tanner_ai_feedback


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "quantum-tanner-css-memory-x-rbposd-p001-v1"
DECODER_ID = "rbposd-osd10-v1"
SUITE_ID = "quantum-tanner-rbposd-p001-v1"
CAMPAIGN_ID = "quantum-tanner-autoresearch"
RUN_ID = "feedback-fixture-run"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _run_cli(
    root: Path,
    run_root: Path,
    proposal_summary: Path,
    surface_copy: Path,
    out_json: Path,
    out_html: Path,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "summarize-quantum-tanner-ai-feedback",
            "--root",
            str(root),
            "--run",
            str(run_root.relative_to(root)),
            "--proposal-summary",
            str(proposal_summary.relative_to(root)),
            "--surface-copy",
            str(surface_copy.relative_to(root)),
            "--out-json",
            str(out_json),
            "--out-html",
            str(out_html),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def _completed_manifest(candidate_id: str) -> dict:
    return {
        "campaign_id": CAMPAIGN_ID,
        "run_id": RUN_ID,
        "candidate_id": candidate_id,
        "task_id": TASK_ID,
        "decoder_id": DECODER_ID,
        "status": "completed",
        "created_at": "2026-07-10T00:00:00Z",
        "decoder_parameters": {},
        "points": [
            {
                "p": 0.001,
                "rounds": 9,
                "shots": 10000,
                "errors": 12,
                "ler": 0.0012,
                "ci_low": 0.0007,
                "ci_high": 0.0018,
                "seconds": 2.5,
            }
        ],
        "run_metadata": {
            "decoder_impl": "rbposd",
            "logical_observable_source": "explicit",
            "logical_observable_basis": "x",
            "logical_failure_aggregation": "any_logical",
            "logical_observable_count": 2,
            "seed": 7,
        },
        "tool_revisions": {"autoqec_search": "0.1.0", "rsinter": "rsinter 0.1.1"},
    }


def _placeholder_manifest(candidate_id: str) -> dict:
    return {
        "campaign_id": CAMPAIGN_ID,
        "run_id": RUN_ID,
        "candidate_id": candidate_id,
        "task_id": TASK_ID,
        "decoder_id": DECODER_ID,
        "status": "placeholder",
        "metrics": {"logical_error_rate": None},
        "created_at": "2026-07-10T00:00:00Z",
    }


def _write_candidate(
    run_root: Path,
    candidate_id: str,
    *,
    n: int,
    k: int,
    screening_status: str,
    upper_bound: int,
    manifest: dict,
) -> None:
    candidate_root = run_root / "candidates" / candidate_id
    _write_json(
        candidate_root / "candidate.json",
        {
            "candidate_id": candidate_id,
            "campaign_id": CAMPAIGN_ID,
            "run_id": RUN_ID,
            "code_family": "quantum-tanner-code",
            "parameters": {"label": candidate_id},
            "provenance": {
                "kind": "proposal-derived",
                "label": candidate_id,
                "proposal": {
                    "proposal_id": candidate_id,
                    "proposal_fingerprint": f"fp-{candidate_id}",
                    "validator_fingerprint": "validator-fixture",
                    "candidate_fingerprint": f"candidate-fp-{candidate_id}",
                    "materialization_manifest": (
                        f"proposal-instances/{candidate_id}"
                        "/materialization_manifest.json"
                    ),
                    "qec_code_spec_path": (
                        f"proposal-instances/{candidate_id}"
                        "/qec_code_quantum_tanner_spec.json"
                    ),
                    "output_hashes": {
                        "instance.json": "instance-hash",
                        "hx.json": "hx-hash",
                        "hz.json": "hz-hash",
                        "qec_code_quantum_tanner_spec.json": "spec-hash",
                    },
                    "materializer_version": "fixture",
                    "exact_distance_status": "unknown",
                    "materialization_run": {"source": "fixture"},
                },
            },
            "status": "evaluated" if screening_status == "admitted" else "placeholder",
        },
    )
    _write_json(
        candidate_root / "structure.json",
        {
            "status": "completed",
            "n": n,
            "k": k,
            "mx": n - k,
            "mz": n - k,
            "rank_hx": n - k,
            "rank_hz": n - k,
            "css_commute": True,
            "commutation_failures": [],
        },
    )
    _write_json(
        candidate_root / "screening.json",
        {
            "screening_status": screening_status,
            "distance_bound_type": "upper",
            "distance_upper_bound": upper_bound
            if screening_status == "admitted"
            else None,
            "reason": "verified_upper_bound_witness"
            if screening_status == "admitted"
            else "screening_skipped_fixture",
        },
    )
    _write_json(
        candidate_root / "distance.json",
        {
            "status": "completed",
            "method": "css-upper-bound-witness",
            "bound_type": "upper",
            "upper_bound": upper_bound,
        },
    )
    _write_json(
        candidate_root / "evaluations" / TASK_ID / DECODER_ID / "manifest.json",
        manifest,
    )


def _feedback_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, dict]:
    root = tmp_path / "work"
    shutil.copytree(
        REPO_ROOT / "benchmarks" / "schemas",
        root / "benchmarks" / "schemas",
    )

    _write_json(root / "benchmarks" / "tasks" / f"{TASK_ID}.json", _benchmark_task())
    _write_json(
        root / "benchmarks" / "decoders" / f"{DECODER_ID}.json",
        _decoder_config(),
    )
    _write_json(root / "benchmarks" / "suites" / f"{SUITE_ID}.json", _suite())
    _write_json(
        root / "campaigns" / "examples" / CAMPAIGN_ID / "campaign.json",
        _campaign(),
    )
    _write_json(
        root / "campaigns" / "examples" / CAMPAIGN_ID / "search_space.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "mode": "explicit_list",
            "candidate_specs": [
                _candidate_spec("ai-valid-dihedral-d3"),
                _candidate_spec("ai-skipped-dihedral-d5"),
            ],
        },
    )

    run_root = root / "results" / "search" / CAMPAIGN_ID / RUN_ID
    _write_json(
        run_root / "run_spec.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "run_id": RUN_ID,
            "suite_id": SUITE_ID,
            "task_ids": [TASK_ID],
            "decoder_ids": [DECODER_ID],
            "candidate_ids": ["ai-valid-dihedral-d3", "ai-skipped-dihedral-d5"],
            "created_at": "2026-07-10T00:00:00Z",
            "mode": "autoresearch",
            "tag": RUN_ID,
            "wall_clock_seconds": 120,
            "seed": 7,
        },
    )
    _write_json(run_root / "env.json", {"mode": "fixture"})
    _write_json(
        run_root / "frontier.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "run_id": RUN_ID,
            "items": [
                {
                    "candidate_id": "ai-valid-dihedral-d3",
                    "distance": 3,
                    "decoder_id": DECODER_ID,
                    "p": 0.001,
                    "ler": 0.0012,
                }
            ]
        },
    )
    (run_root / "leaderboard.csv").parent.mkdir(parents=True, exist_ok=True)
    (run_root / "leaderboard.csv").write_text(
        "candidate_id,task_id,decoder_id,p,ler,status\n"
        f"ai-valid-dihedral-d3,{TASK_ID},{DECODER_ID},0.001,0.0012,completed\n"
        f"ai-skipped-dihedral-d5,{TASK_ID},{DECODER_ID},,,placeholder\n"
    )
    (run_root / "summary.md").write_text("# Feedback fixture run\n")
    (run_root / "experiment-log.tsv").write_text(
        "candidate_id\tler\tstatus\tdescription\n"
        "ai-valid-dihedral-d3\t0.0012\tcompleted\tfixture\n"
        "ai-skipped-dihedral-d5\t\tplaceholder\tfixture\n"
    )
    _write_json(
        run_root / "run_status.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "run_id": RUN_ID,
            "tag": RUN_ID,
            "status": "finalized",
            "finalized_at": "2026-07-10T00:02:00Z",
            "candidates_attempted": 2,
            "frontier_size": 1,
        },
    )
    (run_root / "run-summary.html").write_text("<!doctype html><title>fixture</title>\n")

    _write_candidate(
        run_root,
        "ai-valid-dihedral-d3",
        n=36,
        k=2,
        screening_status="admitted",
        upper_bound=3,
        manifest=_completed_manifest("ai-valid-dihedral-d3"),
    )
    _write_candidate(
        run_root,
        "ai-skipped-dihedral-d5",
        n=64,
        k=2,
        screening_status="skipped",
        upper_bound=5,
        manifest=_placeholder_manifest("ai-skipped-dihedral-d5"),
    )

    summary = {
        "accepted": 1,
        "rejected": 1,
        "duplicate": 1,
        "accepted_fingerprints": ["fp-valid"],
        "accepted_records": [
            {
                "proposal_id": "ai-valid-dihedral-d3",
                "candidate_id": "ai-valid-dihedral-d3",
                "fingerprint": "fp-valid",
                "proposal_fingerprint": "fp-valid",
                "path": "accepted/000-ai-valid-dihedral-d3.json",
            }
        ],
        "rejected_records": [
            {
                "proposal_id": "ai-invalid-nonsymmetric-generators",
                "error_kind": "NonSymmetricGeneratorSet",
                "path": "rejected/001-ai-invalid-nonsymmetric-generators.json",
            }
        ],
        "duplicate_records": [
            {
                "proposal_id": "ai-duplicate-dihedral-d3",
                "error_kind": "DuplicateProposal",
                "path": "duplicates/002-ai-duplicate-dihedral-d3.json",
            }
        ],
    }
    proposal_summary = run_root / "proposal-summary.json"
    _write_json(proposal_summary, summary)

    surface_copy = run_root / "surface-copy-comparison.json"
    _write_json(
        surface_copy,
        {
            "rows": [
                {
                    "status": "accepted",
                    "candidate_id": "ai-valid-dihedral-d3",
                    "surface_distance": 3,
                    "surface_block_ler": 0.001999,
                    "surface_copied_total_physical": 18,
                    "unused_physical_budget": 18,
                }
            ]
        },
    )
    return root, run_root, proposal_summary, surface_copy, summary


def _benchmark_task() -> dict:
    return {
        "id": TASK_ID,
        "title": "Quantum Tanner CSS Memory X at p=0.001 via RBP-OSD OSD10",
        "observable": "logical_x",
        "noise_model": "circuit_depolarizing",
        "input_type": "css",
        "p_list": [0.001],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 10000, "max_errors": 100},
        "result_metrics": ["logical_error_rate"],
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "optional",
        },
        "execution_status": "real",
    }


def _decoder_config() -> dict:
    return {
        "id": DECODER_ID,
        "title": "RBP-OSD OSD Order 10 via rsinter",
        "backend": "rsinter",
        "impl_key": "rbposd",
        "language": "rust",
        "parameters": {
            "bp_algorithm": "min_sum",
            "bp_iters": 50,
            "early_stop": True,
            "osd_method": "combination_sweep",
            "osd_order": 10,
        },
        "execution_status": "real",
    }


def _suite() -> dict:
    return {
        "id": SUITE_ID,
        "title": "Quantum Tanner RBP-OSD p=0.001 v1",
        "task_ids": [TASK_ID],
        "decoder_ids": [DECODER_ID],
        "shared_settings": {"runner": "rsinter"},
    }


def _campaign() -> dict:
    return {
        "id": CAMPAIGN_ID,
        "title": "Quantum Tanner autoresearch",
        "objective": "Fixture campaign for quantum Tanner AI feedback tests.",
        "family_id": "quantum-tanner-code",
        "default_suite_id": SUITE_ID,
        "budget": {"wall_clock_seconds": 3600, "max_candidates": 2},
        "stop_conditions": {"max_candidates": 2, "max_wall_clock_seconds": 3600},
        "random_seed_policy": {"mode": "fixed", "seed": 7},
    }


def _candidate_spec(candidate_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "code_family": "quantum-tanner-code",
        "parameters": {"label": candidate_id},
        "provenance": {
            "kind": "proposal-derived",
            "label": candidate_id,
            "proposal": {
                "proposal_id": candidate_id,
                "proposal_fingerprint": f"fp-{candidate_id}",
                "validator_fingerprint": "validator-fixture",
                "candidate_fingerprint": f"candidate-fp-{candidate_id}",
                "materialization_manifest": (
                    f"proposal-instances/{candidate_id}/materialization_manifest.json"
                ),
                "qec_code_spec_path": (
                    f"proposal-instances/{candidate_id}"
                    "/qec_code_quantum_tanner_spec.json"
                ),
                "output_hashes": {
                    "instance.json": "instance-hash",
                    "hx.json": "hx-hash",
                    "hz.json": "hz-hash",
                    "qec_code_quantum_tanner_spec.json": "spec-hash",
                },
                "materializer_version": "fixture",
                "exact_distance_status": "unknown",
                "materialization_run": {"source": "fixture"},
            },
        },
    }


def test_feedback_report_summarizes_completed_proposal_run(tmp_path: Path) -> None:
    root, run_root, proposal_summary, surface_copy, _summary = _feedback_fixture(tmp_path)
    json_path = tmp_path / "custom-feedback.json"
    html_path = tmp_path / "custom-feedback.html"

    result = _run_cli(root, run_root, proposal_summary, surface_copy, json_path, html_path)

    assert result.returncode == 0, result.stderr
    report = json.loads(json_path.read_text())
    candidates = {
        candidate["candidate_id"]: candidate for candidate in report["candidates"]
    }
    candidate = candidates["ai-valid-dihedral-d3"]
    assert candidate["proposal_id"] == "ai-valid-dihedral-d3"
    assert candidate["proposal_fingerprint"] == "fp-valid"
    assert candidate["validation_status"] == "accepted"
    assert candidate["materialization_status"] == "present"
    assert candidate["screening_status"] == "admitted"
    assert candidate["upper_bound"] == 3
    assert candidate["n"] == 36
    assert candidate["k"] == 2
    point = candidate["ler_points"][0]
    assert point["p"] == 0.001
    assert point["logical_error_rate"] == 0.0012
    assert point["shots"] == 10000
    assert point["errors"] == 12
    assert candidate["surface_copy"]["status"] == "accepted"
    assert candidate["surface_copy"]["surface_distance"] == 3
    assert candidate["surface_copy"]["surface_block_ler"] == 0.001999
    assert candidate["surface_copy"]["surface_copied_total_physical"] == 18
    assert candidate["surface_copy"]["unused_physical_budget"] == 18
    skipped = candidates["ai-skipped-dihedral-d5"]
    assert skipped["materialization_status"] == "present"
    assert skipped["screening_status"] == "skipped"
    assert skipped["upper_bound"] == 5
    assert skipped["ler_points"] == []
    rejected_by_id = {
        proposal["proposal_id"]: proposal for proposal in report["rejected_proposals"]
    }
    assert (
        rejected_by_id["ai-invalid-nonsymmetric-generators"]["error_kind"]
        == "NonSymmetricGeneratorSet"
    )
    assert rejected_by_id["ai-duplicate-dihedral-d3"]["error_kind"] == "DuplicateProposal"
    assert "ai-valid-dihedral-d3" in report["next_prompt_context"][
        "candidate_ids_with_p001_ler"
    ]
    html = html_path.read_text()
    assert "ai-valid-dihedral-d3" in html
    for forbidden in ("http://", "https://", "//cdn", "src=", "href="):
        assert forbidden not in html


def test_feedback_report_rejects_inconsistent_candidate_ids(tmp_path: Path) -> None:
    root, run_root, proposal_summary, surface_copy, summary = _feedback_fixture(tmp_path)
    broken_summary = copy.deepcopy(summary)
    broken_summary["accepted_records"][0]["candidate_id"] = "missing-candidate"
    _write_json(proposal_summary, broken_summary)
    json_path = tmp_path / "feedback.json"
    html_path = tmp_path / "feedback.html"

    result = _run_cli(root, run_root, proposal_summary, surface_copy, json_path, html_path)

    assert result.returncode != 0
    assert "proposal feedback candidate mismatch" in result.stderr


def test_feedback_report_counts_all_p001_ler_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "work"
    run_root = root / "results" / "search" / CAMPAIGN_ID / RUN_ID
    candidate_root = run_root / "candidates" / "candidate-with-two-rows"
    _write_json(
        candidate_root / "candidate.json",
        {
            "candidate_id": "candidate-with-two-rows",
            "campaign_id": CAMPAIGN_ID,
            "run_id": RUN_ID,
            "code_family": "quantum-tanner-code",
            "parameters": {"label": "candidate-with-two-rows"},
            "provenance": {
                "kind": "proposal-derived",
                "label": "candidate-with-two-rows",
                "proposal": {
                    "proposal_id": "proposal-with-two-rows",
                    "proposal_fingerprint": "fp-two-rows",
                    "candidate_fingerprint": "candidate-fp-two-rows",
                },
            },
            "status": "evaluated",
        },
    )
    _write_json(
        candidate_root / "distance.json",
        {
            "status": "completed",
            "method": "css-upper-bound-witness",
            "bound_type": "upper",
            "upper_bound": 4,
        },
    )
    fake_report_model = {
        "provenance": {
            "campaign_id": CAMPAIGN_ID,
            "run_id": RUN_ID,
            "mode": "autoresearch",
        },
        "candidates": [
            {
                "candidate_id": "candidate-with-two-rows",
                "n": 40,
                "k": 2,
                "distance_bound_type": "upper",
                "screening": {
                    "screening_status": "admitted",
                    "reason": "verified_upper_bound_witness",
                },
            }
        ],
        "points": [
            {
                "candidate_id": "candidate-with-two-rows",
                "task_id": TASK_ID,
                "decoder_id": DECODER_ID,
                "p": 0.001,
                "rounds": 9,
                "shots": 1000,
                "errors": 1,
                "ler": 0.001,
                "ci_low": 0.0,
                "ci_high": 0.002,
            },
            {
                "candidate_id": "candidate-with-two-rows",
                "task_id": TASK_ID,
                "decoder_id": "second-decoder",
                "p": 0.001,
                "rounds": 9,
                "shots": 2000,
                "errors": 3,
                "ler": 0.0015,
                "ci_low": 0.0005,
                "ci_high": 0.0025,
            },
        ],
    }
    monkeypatch.setattr(
        quantum_tanner_ai_feedback,
        "build_report_model",
        lambda _root, _run_root: fake_report_model,
    )

    report = quantum_tanner_ai_feedback.build_quantum_tanner_ai_feedback(root, run_root)

    assert report["counts"]["candidates_with_p001_ler"] == 1
    assert report["counts"]["p001_ler_rows"] == 2
