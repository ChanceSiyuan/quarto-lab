from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

import autoqec_search.quantum_tanner_aggregate as aggregate_module
from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_aggregate import (
    aggregate_paths,
    append_attempt_records,
    collect_attempt_records,
    initialize_aggregate,
    install_terminal_attempt,
    load_aggregate_records,
    reconcile_terminal_attempts,
)


def _record(
    candidate_id: str, fingerprint: str, candidate_ordinal: int = 0
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "proposal_fingerprint": fingerprint,
        "candidate_ordinal": candidate_ordinal,
        "status": "evaluated",
    }


def _full_record(
    candidate_id: str,
    fingerprint: str,
    *,
    candidate_ordinal: int,
    status: str,
    reason: str | None = None,
    round_number: int = 1,
    attempt_number: int = 1,
    source_run_frontier: bool = False,
    h_a: list[list[int]] | None = None,
    h_b: list[list[int]] | None = None,
    artifacts: dict[str, object] | None = None,
    benchmark: dict[str, object] | None = None,
    code: dict[str, object] | None = None,
    screening: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "proposal_fingerprint": fingerprint,
        "candidate_ordinal": candidate_ordinal,
        "round": round_number,
        "attempt": attempt_number,
        "source_commit": "abc123",
        "recorded_at": "2026-07-10T12:00:00Z",
        "status": status,
        "stage": "completed",
        "reason": reason,
        "construction": {
            "base_group": {"name": "D4", "order": 8},
            "a_generator_indices": [1, 3],
            "b_generator_indices": [2, 4],
            "h_a": h_a if h_a is not None else [[1, 1]],
            "h_b": h_b if h_b is not None else [[1, 0], [0, 1]],
            "local_code_a": {"label": "Rep(2) [2,1,2]"},
            "local_code_b": {"label": "Identity(2) [2,0,1]"},
        },
        "code": code if code is not None else {"n": 8, "k": 2, "rate": 0.25},
        "screening": screening
        if screening is not None
        else {
            "status": "admitted",
            "reason": "verified_upper_bound_witness",
            "x_upper_bound": 2,
        },
        "benchmark": benchmark,
        "source_run_frontier": source_run_frontier,
        "artifacts": artifacts if artifacts is not None else {},
    }


def _completed_benchmark_record() -> dict[str, object]:
    return {
        "task_id": "task-a",
        "decoder_id": "decoder-a",
        "p": 0.001,
        "rounds": 3,
        "errors": 0,
        "shots": 64,
        "ler": 0.0,
        "ci_low": 0.0,
        "ci_high": 0.056626,
        "seconds": 1.25,
    }


def _write_accepted_attempt(
    attempt_dir: Path,
    *,
    terminal_status: str,
    stage: str,
    candidate_id: str = "candidate-a",
) -> None:
    accepted = attempt_dir / "ingested" / "accepted"
    accepted.mkdir(parents=True)
    proposal = {
        "schema_version": 1,
        "proposal_id": candidate_id,
        "base_group": {"name": "D4", "order": 8},
        "a_generator_indices": [4, 6],
        "b_generator_indices": [5, 7],
        "local_codes": {
            "field": "GF(2)",
            "matrix_role": "parity_check",
            "h_a": [[1, 1]],
            "h_b": [[1, 1]],
        },
    }
    proposal_path = accepted / f"000-{candidate_id}.json"
    proposal_path.write_text(json.dumps(proposal))
    summary_path = attempt_dir / "ingested" / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "accepted": 1,
                "accepted_fingerprints": ["fp-a"],
                "accepted_records": [
                    {
                        "fingerprint": "fp-a",
                        "path": f"accepted/000-{candidate_id}.json",
                        "proposal_id": candidate_id,
                        "proposal_index": 0,
                    }
                ],
                "rejected": 0,
            }
        )
    )
    (attempt_dir / "status.json").write_text(
        json.dumps(
            {
                "accepted": 1,
                "accepted_fingerprints": ["fp-a"],
                "attempt": 1,
                "attempt_dir": str(attempt_dir),
                "proposal_summary_path": str(summary_path),
                "round": 1,
                "run_root": None,
                "source_commit": "abc123",
                "stage": stage,
                "status": terminal_status,
            }
        )
    )


def _append_accepted_candidate(
    attempt_dir: Path,
    *,
    candidate_id: str,
    fingerprint: str,
    proposal_index: int,
) -> None:
    summary_path = attempt_dir / "ingested" / "summary.json"
    summary = json.loads(summary_path.read_text())
    first_record = summary["accepted_records"][0]
    first_proposal_path = summary_path.parent / first_record["path"]
    proposal = json.loads(first_proposal_path.read_text())
    proposal["proposal_id"] = candidate_id
    proposal_path = (
        summary_path.parent / "accepted" / f"{proposal_index:03d}-{candidate_id}.json"
    )
    proposal_path.write_text(json.dumps(proposal))
    summary["accepted"] += 1
    summary["accepted_fingerprints"].append(fingerprint)
    summary["accepted_records"].append(
        {
            "fingerprint": fingerprint,
            "path": f"accepted/{proposal_path.name}",
            "proposal_id": candidate_id,
            "proposal_index": proposal_index,
        }
    )
    summary_path.write_text(json.dumps(summary))
    status_path = attempt_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["accepted"] = summary["accepted"]
    status["accepted_fingerprints"] = summary["accepted_fingerprints"]
    status_path.write_text(json.dumps(status))


def _write_run_candidate(
    attempt_dir: Path,
    *,
    screening_status: str,
    screening_reason: str,
    manifest_status: str | None,
    candidate_id: str = "candidate-a",
) -> Path:
    run_root = (
        attempt_dir
        / "checkout"
        / ".worktrees"
        / "run"
        / "results"
        / "search"
        / "quantum-tanner-autoresearch"
        / "run"
    )
    candidate = run_root / "candidates" / candidate_id
    artifacts = candidate / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "instance.json").write_text(
        json.dumps(
            {
                "candidate_id": candidate_id,
                "derived_properties": {"n": 8},
                "instance_id": candidate_id,
                "k": 2,
                "n": 8,
                "proposal_id": candidate_id,
            }
        )
    )
    (candidate / "screening.json").write_text(
        json.dumps(
            {
                "screening_status": screening_status,
                "distance_bound_type": "upper",
                "distance_upper_bound": 2 if screening_status == "admitted" else None,
                "reason": screening_reason,
            }
        )
    )
    if manifest_status is not None:
        manifest = candidate / "evaluations" / "task-a" / "decoder-a" / "manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest_payload: dict[str, object] = {
            "campaign_id": "quantum-tanner-autoresearch",
            "candidate_id": candidate_id,
            "created_at": "2026-07-10T12:00:00Z",
            "decoder_id": "decoder-a",
            "run_id": "run",
            "status": manifest_status,
            "task_id": "task-a",
        }
        if manifest_status == "completed":
            manifest_payload.update(
                {
                    "decoder_parameters": {},
                    "points": [
                        {
                            "ci_high": 0.056626,
                            "ci_low": 0.0,
                            "errors": 0,
                            "ler": 0.0,
                            "p": 0.001,
                            "rounds": 3,
                            "seconds": 1.25,
                            "shots": 64,
                        }
                    ],
                    "tool_revisions": {
                        "autoqec_search": "0.1.0",
                        "rsinter": "rsinter test",
                    },
                }
            )
        elif manifest_status == "placeholder":
            manifest_payload["metrics"] = {"logical_error_rate": None}
        elif manifest_status == "crash":
            manifest_payload["error"] = "rsinter exited before completion"
        manifest.write_text(json.dumps(manifest_payload))
    (run_root / "frontier.json").write_text(
        json.dumps(
            {
                "campaign_id": "quantum-tanner-autoresearch",
                "items": [{"candidate_id": candidate_id}],
                "run_id": "run",
            }
        )
    )
    (run_root / "report.html").write_text("<html>report</html>")
    (run_root / "construction-definitions.html").write_text("<html>definitions</html>")
    status_path = attempt_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["run_root"] = str(run_root)
    status_path.write_text(json.dumps(status))
    return run_root


def test_initialize_aggregate_writes_empty_durable_files(tmp_path: Path) -> None:
    update = initialize_aggregate(tmp_path)
    paths = aggregate_paths(tmp_path)

    assert update.appended_records == 0
    assert paths.ledger.read_text() == ""
    assert json.loads(paths.state.read_text()) == {
        "installed_attempts": {},
        "next_sequence": 1,
        "schema_version": 1,
    }
    assert paths.report.is_file()


def test_append_preserves_order_and_matching_visible_content(tmp_path: Path) -> None:
    initialize_aggregate(tmp_path)
    append_attempt_records(
        tmp_path, "round-0001/attempt-001",
        [_record("same-visible-code", "fp-a")],
    )
    append_attempt_records(
        tmp_path, "round-0002/attempt-001",
        [_record("same-visible-code", "fp-b")],
    )

    records = load_aggregate_records(tmp_path)
    assert [record["sequence"] for record in records] == [1, 2]
    assert [record["proposal_fingerprint"] for record in records] == ["fp-a", "fp-b"]


def test_replaying_installed_attempt_is_operational_noop(tmp_path: Path) -> None:
    initialize_aggregate(tmp_path)
    first = append_attempt_records(
        tmp_path, "round-0001/attempt-001", [_record("candidate-a", "fp-a")]
    )
    replay = append_attempt_records(
        tmp_path, "round-0001/attempt-001", [_record("candidate-a", "fp-a")]
    )

    assert first.appended_records == 1
    assert replay.appended_records == 0
    assert len(load_aggregate_records(tmp_path)) == 1


def test_initialize_rejects_symlinked_aggregate_without_touching_target(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_text("keep\n")
    (tmp_path / "aggregate").symlink_to(external, target_is_directory=True)

    with pytest.raises(SearchIntegrityError, match="unsafe aggregate directory"):
        initialize_aggregate(tmp_path)

    assert sentinel.read_text() == "keep\n"
    assert sorted(path.name for path in external.iterdir()) == ["sentinel.txt"]


@pytest.mark.parametrize("replay_ordinals", [[], [1], [0, 1]])
def test_replaying_attempt_with_mismatched_ordinals_is_rejected(
    tmp_path: Path, replay_ordinals: list[int]
) -> None:
    initialize_aggregate(tmp_path)
    append_attempt_records(
        tmp_path,
        "round-0001/attempt-001",
        [_record("candidate-0", "fp-0", 0)],
    )

    with pytest.raises(SearchIntegrityError, match="candidate_ordinal set mismatch"):
        append_attempt_records(
            tmp_path,
            "round-0001/attempt-001",
            [
                _record(f"candidate-{ordinal}", f"fp-{ordinal}", ordinal)
                for ordinal in replay_ordinals
            ],
        )

    assert [
        record["candidate_ordinal"] for record in load_aggregate_records(tmp_path)
    ] == [0]


def test_empty_attempt_is_installed_and_replays_as_noop(tmp_path: Path) -> None:
    initialize_aggregate(tmp_path)
    first = append_attempt_records(tmp_path, "round-0001/attempt-001", [])
    replay = append_attempt_records(tmp_path, "round-0001/attempt-001", [])

    assert first.appended_records == 0
    assert replay.appended_records == 0
    assert load_aggregate_records(tmp_path) == []
    assert json.loads(aggregate_paths(tmp_path).state.read_text()) == {
        "installed_attempts": {"round-0001/attempt-001": []},
        "next_sequence": 1,
        "schema_version": 1,
    }


def test_stale_state_is_repaired_from_ledger_while_preserving_empty_attempt(
    tmp_path: Path,
) -> None:
    initialize_aggregate(tmp_path)
    append_attempt_records(
        tmp_path,
        "round-0001/attempt-001",
        [
            _record("candidate-2", "fp-2", 2),
            _record("candidate-0", "fp-0", 0),
        ],
    )
    paths = aggregate_paths(tmp_path)
    paths.state.write_text(
        json.dumps(
            {
                "installed_attempts": {"round-0000/attempt-001": []},
                "next_sequence": 1,
                "schema_version": 1,
            }
        )
    )

    replay = append_attempt_records(
        tmp_path,
        "round-0001/attempt-001",
        [
            _record("candidate-0", "fp-0", 0),
            _record("candidate-2", "fp-2", 2),
        ],
    )

    assert replay.appended_records == 0
    assert json.loads(paths.state.read_text()) == {
        "installed_attempts": {
            "round-0000/attempt-001": [],
            "round-0001/attempt-001": [0, 2],
        },
        "next_sequence": 3,
        "schema_version": 1,
    }


def test_aggregate_report_renders_all_terminal_rows_and_summary_cards(
    tmp_path: Path,
) -> None:
    source_report = tmp_path / "runs" / "source-run" / "report.html"
    source_definitions = (
        tmp_path
        / "runs"
        / "source-run"
        / "construction-definitions.html#candidate-1"
    )
    initialize_aggregate(tmp_path)
    append_attempt_records(
        tmp_path,
        "round-0001/attempt-001",
        [
            _full_record(
                'candidate-<tag> & "quote"',
                "fp-evaluated",
                candidate_ordinal=0,
                status="evaluated",
                source_run_frontier=True,
                benchmark=_completed_benchmark_record(),
                artifacts={
                    "report": str(source_report),
                    "definitions": str(source_definitions),
                },
            ),
            _full_record(
                "skipped-code",
                "fp-skipped",
                candidate_ordinal=1,
                status="skipped",
                reason="missing_upper_bound_payload",
                benchmark=None,
                code={"n": None, "k": None, "rate": None},
                screening={
                    "status": "skipped",
                    "reason": "missing_upper_bound_payload",
                    "x_upper_bound": None,
                },
            ),
            _full_record(
                "failed-code",
                "fp-failed",
                candidate_ordinal=2,
                status="failed",
                reason="rsinter exited before completion",
                benchmark=None,
            ),
            _full_record(
                "interrupted-code",
                "fp-interrupted",
                candidate_ordinal=3,
                status="interrupted",
                reason="SIGTERM",
                benchmark=None,
            ),
        ],
    )

    html = aggregate_paths(tmp_path).report.read_text()

    assert html.count('data-candidate-row="true"') == 4
    for heading in (
        "Round / attempt",
        "Finite code / candidate",
        "Status / reason",
        "Base group",
        "A / B generators",
        "Local classical code",
        "CSS parameters",
        "Code rate",
        "X upper bound",
        "Screening",
        "errors / shots",
        "LER",
        "95% CI",
        "Decoding time",
        "Source artifacts",
    ):
        assert heading in html
    for status in ("evaluated", "skipped", "failed", "interrupted"):
        assert f'class="badge {status}"' in html
    assert (
        "Zero observed errors do not prove a zero logical error rate; use the "
        "recorded 95% confidence interval. X upper bounds are randomized "
        "screening evidence, not exact code distances."
    ) in html
    assert not re.search(r"[\u3400-\u9fff，。；：！？【】（）]", html)
    assert ">—<" in html
    assert "candidate-&lt;tag&gt; &amp; &quot;quote&quot;" in html
    assert 'candidate-<tag> & "quote"' not in html
    assert 'href="../runs/source-run/report.html"' in html
    assert (
        'href="../runs/source-run/construction-definitions.html#candidate-1"'
        in html
    )
    assert f'href="{source_report}"' not in html
    assert f'href="{source_definitions}"' not in html
    assert "Source-run frontier" in html
    assert not re.search(r"\b(winner|ranking|rank|best)\b", html, re.IGNORECASE)
    for label, value in (
        ("Completed rounds", "1"),
        ("Total codes", "4"),
        ("Evaluated", "1"),
        ("Skipped", "1"),
        ("Failed / interrupted", "2"),
        ("Source-run frontier", "1"),
    ):
        assert f'<span class="card-label">{label}</span>' in html
        assert f'<span class="card-value">{value}</span>' in html


def test_candidate_history_prompt_compacts_matrices_and_keeps_all_statuses(
    tmp_path: Path,
) -> None:
    initialize_aggregate(tmp_path)
    append_attempt_records(
        tmp_path,
        "round-0001/attempt-001",
        [
            _full_record(
                "small-code",
                "fp-small",
                candidate_ordinal=0,
                status="failed",
                reason="witness search failed",
                h_a=[[1, 1]],
                benchmark=None,
            ),
            _full_record(
                "large-code",
                "fp-large",
                candidate_ordinal=1,
                status="skipped",
                reason="missing_upper_bound_payload",
                h_a=[[1] * 65],
                benchmark=None,
            ),
        ],
    )

    history = aggregate_module.candidate_history_prompt(tmp_path)

    assert "small-code" in history
    assert "large-code" in history
    assert "fp-small" in history
    assert "fp-large" in history
    assert "failed" in history
    assert "skipped" in history
    assert '"h_a": [[1, 1]]' in history
    assert '"h_a_dimensions": [1, 65]' in history
    assert '"h_a_sha256":' in history
    assert aggregate_module.historical_fingerprints(tmp_path) == {
        "fp-small",
        "fp-large",
    }


def test_reconcile_terminal_attempts_installs_failed_and_interrupted_batches(
    tmp_path: Path,
) -> None:
    initialize_aggregate(tmp_path)
    failed = tmp_path / "rounds" / "round-0001" / "attempt-001"
    interrupted = tmp_path / "rounds" / "round-0001" / "attempt-002"
    _write_accepted_attempt(failed, terminal_status="failed", stage="failed")
    _write_accepted_attempt(
        interrupted, terminal_status="interrupted", stage="prompted"
    )
    interrupted_status_path = interrupted / "status.json"
    interrupted_status = json.loads(interrupted_status_path.read_text())
    interrupted_status["attempt"] = 2
    interrupted_status_path.write_text(json.dumps(interrupted_status))

    update = reconcile_terminal_attempts(tmp_path)

    assert update.appended_records == 2
    assert [record["status"] for record in load_aggregate_records(tmp_path)] == [
        "failed",
        "interrupted",
    ]


def test_malformed_installed_attempt_metadata_is_rejected(tmp_path: Path) -> None:
    initialize_aggregate(tmp_path)
    paths = aggregate_paths(tmp_path)
    paths.state.write_text(
        json.dumps(
            {
                "installed_attempts": {"round-0001/attempt-001": [1, 1]},
                "next_sequence": 1,
                "schema_version": 1,
            }
        )
    )

    with pytest.raises(SearchIntegrityError, match="invalid installed_attempts"):
        append_attempt_records(tmp_path, "round-0002/attempt-001", [])


def test_state_nonempty_attempt_absent_from_ledger_is_rejected(tmp_path: Path) -> None:
    initialize_aggregate(tmp_path)
    paths = aggregate_paths(tmp_path)
    paths.state.write_text(
        json.dumps(
            {
                "installed_attempts": {"round-0001/attempt-001": [0]},
                "next_sequence": 1,
                "schema_version": 1,
            }
        )
    )

    with pytest.raises(SearchIntegrityError, match="installed_attempts.*ledger"):
        append_attempt_records(tmp_path, "round-0002/attempt-001", [])


def test_collector_keeps_ingested_candidate_after_materialization_failure(
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")

    record = collect_attempt_records(attempt)[0]

    assert record["candidate_id"] == "candidate-a"
    assert record["proposal_fingerprint"] == "fp-a"
    assert record["status"] == "failed"
    assert record["construction"]["base_group"] == {"name": "D4", "order": 8}
    assert record["construction"]["local_code_a"]["label"] == "Rep(2) [2,1,2]"
    assert record["code"]["n"] is None
    assert record["recorded_at"].endswith("Z")


def test_collector_overlays_completed_evaluation_and_frontier(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )

    record = collect_attempt_records(attempt)[0]

    assert record["status"] == "evaluated"
    assert record["reason"] is None
    assert record["code"] == {"n": 8, "k": 2, "rate": 0.25}
    assert record["screening"] == {
        "status": "admitted",
        "reason": "verified_upper_bound_witness",
        "x_upper_bound": 2,
    }
    assert record["benchmark"]["shots"] == 64
    assert record["benchmark"]["errors"] == 0
    assert record["benchmark"]["ci_high"] == 0.056626
    assert record["benchmark"]["seconds"] == 1.25
    assert record["source_run_frontier"] is True
    assert record["artifacts"] == {
        "report": str(run_root / "report.html"),
        "definitions": f"{run_root / 'construction-definitions.html'}#candidate-1",
    }


def test_collector_keeps_screening_skip_with_placeholder_manifest(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    _write_run_candidate(
        attempt,
        screening_status="skipped",
        screening_reason="missing_upper_bound_payload",
        manifest_status="placeholder",
    )

    record = collect_attempt_records(attempt)[0]

    assert record["status"] == "skipped"
    assert record["reason"] == "missing_upper_bound_payload"
    assert record["benchmark"] is None


def test_collector_keeps_candidate_specific_witness_failure(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")
    witness_summary = (
        attempt
        / "checkout"
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "witnesses"
        / "witness_finder_summary.json"
    )
    witness_summary.parent.mkdir(parents=True)
    witness_summary.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "counts": {"attached": 0, "failed": 1},
                "candidates": [
                    {
                        "candidate_id": "candidate-a",
                        "reason": "witness search failed",
                        "status": "failed",
                    }
                ],
            }
        )
    )
    status_path = attempt / "status.json"
    status = json.loads(status_path.read_text())
    status["message"] = "no proposal candidates produced compatible X witnesses"
    status_path.write_text(json.dumps(status))

    record = collect_attempt_records(attempt)[0]

    assert record["status"] == "failed"
    assert record["reason"] == "witness search failed"


def test_collector_marks_noncompleted_rsinter_manifest_failed(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="crash",
    )

    record = collect_attempt_records(attempt)[0]

    assert record["status"] == "failed"
    assert record["reason"] == "rsinter exited before completion"
    assert record["benchmark"] is None


def test_collector_keeps_terminal_interruption(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="interrupted", stage="prompted")
    status_path = attempt / "status.json"
    status = json.loads(status_path.read_text())
    status["signal"] = "SIGTERM"
    status_path.write_text(json.dumps(status))

    record = collect_attempt_records(attempt)[0]

    assert record["status"] == "interrupted"
    assert record["stage"] == "prompted"


def test_collector_preserves_evaluated_outcome_after_attempt_interruption(
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="interrupted", stage="completed")
    _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )

    record = collect_attempt_records(attempt)[0]

    assert record["status"] == "evaluated"
    assert record["reason"] is None


def test_collector_preserves_screening_skip_after_attempt_failure(
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")
    _write_run_candidate(
        attempt,
        screening_status="skipped",
        screening_reason="missing_upper_bound_payload",
        manifest_status="placeholder",
    )

    record = collect_attempt_records(attempt)[0]

    assert record["status"] == "skipped"
    assert record["reason"] == "missing_upper_bound_payload"


def test_collector_returns_no_rows_for_rejected_only_attempt(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    ingested = attempt / "ingested"
    ingested.mkdir(parents=True)
    summary_path = ingested / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "accepted": 0,
                "accepted_fingerprints": [],
                "accepted_records": [],
                "rejected": 1,
            }
        )
    )
    (attempt / "status.json").write_text(
        json.dumps(
            {
                "accepted": 0,
                "attempt": 1,
                "proposal_summary_path": str(summary_path),
                "round": 1,
                "source_commit": "abc123",
                "stage": "completed_without_numerical_run",
                "status": "completed",
            }
        )
    )

    assert collect_attempt_records(attempt) == []


def test_collector_rejects_present_malformed_optional_artifact(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    screening_path = run_root / "candidates" / "candidate-a" / "screening.json"
    screening_path.write_text("[]")

    with pytest.raises(SearchIntegrityError, match=r"screening.*screening\.json"):
        collect_attempt_records(attempt)


def test_collector_rejects_unknown_screening_status(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    screening_path = run_root / "candidates" / "candidate-a" / "screening.json"
    screening = json.loads(screening_path.read_text())
    screening["screening_status"] = "unknown"
    screening_path.write_text(json.dumps(screening))

    with pytest.raises(SearchIntegrityError, match=r"screening.*screening\.json"):
        collect_attempt_records(attempt)


def test_collector_rejects_skipped_screening_with_upper_bound(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="skipped",
        screening_reason="missing_upper_bound_payload",
        manifest_status="placeholder",
    )
    screening_path = run_root / "candidates" / "candidate-a" / "screening.json"
    screening = json.loads(screening_path.read_text())
    screening["distance_upper_bound"] = 2
    screening_path.write_text(json.dumps(screening))

    with pytest.raises(SearchIntegrityError, match=r"screening.*screening\.json"):
        collect_attempt_records(attempt)


def test_collector_rejects_incomplete_completed_manifest(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    manifest_path = (
        run_root
        / "candidates"
        / "candidate-a"
        / "evaluations"
        / "task-a"
        / "decoder-a"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    del manifest["task_id"]
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(SearchIntegrityError, match=r"manifest.*manifest\.json"):
        collect_attempt_records(attempt)


@pytest.mark.parametrize(
    ("field", "value"),
    [("decoder_parameters", []), ("run_metadata", {})],
)
def test_collector_rejects_malformed_completed_manifest_metadata(
    tmp_path: Path, field: str, value: object
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    manifest_path = (
        run_root
        / "candidates"
        / "candidate-a"
        / "evaluations"
        / "task-a"
        / "decoder-a"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(SearchIntegrityError, match=r"manifest.*manifest\.json"):
        collect_attempt_records(attempt)


def test_collector_rejects_unknown_witness_status(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")
    witness_summary = (
        attempt
        / "checkout"
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "witnesses"
        / "witness_finder_summary.json"
    )
    witness_summary.parent.mkdir(parents=True)
    witness_summary.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_id": "candidate-a",
                        "reason": "unexpected witness state",
                        "status": "unknown",
                    }
                ]
            }
        )
    )

    with pytest.raises(SearchIntegrityError, match=r"witness.*summary\.json"):
        collect_attempt_records(attempt)


def test_collector_rejects_frontier_item_without_candidate_id(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    frontier_path = run_root / "frontier.json"
    frontier = json.loads(frontier_path.read_text())
    frontier["items"] = [{}]
    frontier_path.write_text(json.dumps(frontier))

    with pytest.raises(SearchIntegrityError, match=r"frontier.*frontier\.json"):
        collect_attempt_records(attempt)


def test_collector_rejects_missing_required_attempt_metadata(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")
    status_path = attempt / "status.json"
    status = json.loads(status_path.read_text())
    del status["source_commit"]
    status_path.write_text(json.dumps(status))

    with pytest.raises(SearchIntegrityError, match=r"attempt status.*status\.json"):
        collect_attempt_records(attempt)


def test_collector_preserves_witness_failure_over_later_skip_in_mixed_batch(
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    _append_accepted_candidate(
        attempt,
        candidate_id="candidate-b",
        fingerprint="fp-b",
        proposal_index=1,
    )
    _write_run_candidate(
        attempt,
        candidate_id="candidate-a",
        screening_status="skipped",
        screening_reason="missing_upper_bound_payload",
        manifest_status="placeholder",
    )
    _write_run_candidate(
        attempt,
        candidate_id="candidate-b",
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    witness_summary = (
        attempt
        / "checkout"
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "witnesses"
        / "witness_finder_summary.json"
    )
    witness_summary.parent.mkdir(parents=True)
    witness_summary.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "counts": {"attached": 1, "failed": 1},
                "candidates": [
                    {
                        "candidate_id": "candidate-a",
                        "log_path": "logs/witness-candidate-a.log",
                        "reason": "witness search failed for candidate-a",
                        "status": "failed",
                        "witness_path": None,
                    },
                    {
                        "candidate_id": "candidate-b",
                        "log_path": "logs/witness-candidate-b.log",
                        "reason": "verified_upper_bound_witness",
                        "status": "attached",
                        "witness_path": "witnesses/candidate-b.json",
                    },
                ],
            }
        )
    )

    records = {
        record["candidate_id"]: record for record in collect_attempt_records(attempt)
    }

    assert records["candidate-a"]["status"] == "failed"
    assert records["candidate-a"]["reason"] == "witness search failed for candidate-a"
    assert records["candidate-b"]["status"] == "evaluated"


@pytest.mark.parametrize(
    ("field", "value"),
    [("campaign_id", "wrong-campaign"), ("run_id", "wrong-run")],
)
def test_collector_rejects_manifest_source_run_identity_mismatch(
    tmp_path: Path, field: str, value: str
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    manifest_path = (
        run_root
        / "candidates"
        / "candidate-a"
        / "evaluations"
        / "task-a"
        / "decoder-a"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(SearchIntegrityError, match=r"manifest.*manifest\.json"):
        collect_attempt_records(attempt)


@pytest.mark.parametrize(
    ("field", "value"),
    [("campaign_id", "wrong-campaign"), ("run_id", "wrong-run")],
)
def test_collector_rejects_frontier_source_run_identity_mismatch(
    tmp_path: Path, field: str, value: str
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    frontier_path = run_root / "frontier.json"
    frontier = json.loads(frontier_path.read_text())
    frontier[field] = value
    frontier_path.write_text(json.dumps(frontier))

    with pytest.raises(SearchIntegrityError, match=r"frontier.*frontier\.json"):
        collect_attempt_records(attempt)


@pytest.mark.parametrize("path_kind", ["absolute", "parent-segment", "empty-segment"])
def test_collector_rejects_unsafe_accepted_record_path(
    tmp_path: Path, path_kind: str
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")
    summary_path = attempt / "ingested" / "summary.json"
    summary = json.loads(summary_path.read_text())
    proposal_name = Path(summary["accepted_records"][0]["path"]).name
    summary["accepted_records"][0]["path"] = (
        str(attempt / "ingested" / "accepted" / proposal_name)
        if path_kind == "absolute"
        else (
            f"accepted/../accepted/{proposal_name}"
            if path_kind == "parent-segment"
            else "."
        )
    )
    summary_path.write_text(json.dumps(summary))

    with pytest.raises(SearchIntegrityError, match=r"ingestion summary.*summary\.json"):
        collect_attempt_records(attempt)


def test_collector_rejects_duplicate_accepted_record_paths(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")
    _append_accepted_candidate(
        attempt,
        candidate_id="candidate-b",
        fingerprint="fp-b",
        proposal_index=1,
    )
    summary_path = attempt / "ingested" / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["accepted_records"][1]["path"] = summary["accepted_records"][0]["path"]
    summary_path.write_text(json.dumps(summary))

    with pytest.raises(SearchIntegrityError, match=r"ingestion summary.*summary\.json"):
        collect_attempt_records(attempt)


def test_collector_rejects_duplicate_accepted_proposal_ids(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")
    _append_accepted_candidate(
        attempt,
        candidate_id="candidate-b",
        fingerprint="fp-b",
        proposal_index=1,
    )
    summary_path = attempt / "ingested" / "summary.json"
    summary = json.loads(summary_path.read_text())
    second_record = summary["accepted_records"][1]
    second_record["proposal_id"] = "candidate-a"
    second_proposal_path = summary_path.parent / second_record["path"]
    second_proposal = json.loads(second_proposal_path.read_text())
    second_proposal["proposal_id"] = "candidate-a"
    second_proposal_path.write_text(json.dumps(second_proposal))
    summary_path.write_text(json.dumps(summary))

    with pytest.raises(SearchIntegrityError, match=r"ingestion summary.*summary\.json"):
        collect_attempt_records(attempt)


def test_collector_rejects_proposal_id_disagreement_with_accepted_record(
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")
    proposal_path = attempt / "ingested" / "accepted" / "000-candidate-a.json"
    proposal = json.loads(proposal_path.read_text())
    proposal["proposal_id"] = "different-candidate"
    proposal_path.write_text(json.dumps(proposal))

    with pytest.raises(SearchIntegrityError, match=r"accepted proposal.*candidate-a"):
        collect_attempt_records(attempt)


@pytest.mark.parametrize("field", ["candidate_id", "instance_id", "proposal_id"])
def test_collector_rejects_instance_identity_mismatch(
    tmp_path: Path, field: str
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    instance_path = run_root / "candidates" / "candidate-a" / "artifacts" / "instance.json"
    instance = json.loads(instance_path.read_text())
    instance[field] = "different-candidate"
    instance_path.write_text(json.dumps(instance))

    with pytest.raises(SearchIntegrityError, match=r"instance.*instance\.json"):
        collect_attempt_records(attempt)


@pytest.mark.parametrize(
    ("top_level", "derived"),
    [
        ({"n": 9}, {"n": 8}),
        ({"k": 2}, {"n": 8, "k": 3}),
        ({"n": 8}, {"n": None}),
        ({"k": 2}, {"n": 8, "k": None}),
    ],
)
def test_collector_rejects_inconsistent_duplicate_instance_dimensions(
    tmp_path: Path,
    top_level: dict[str, object],
    derived: dict[str, object],
) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="completed", stage="completed")
    run_root = _write_run_candidate(
        attempt,
        screening_status="admitted",
        screening_reason="verified_upper_bound_witness",
        manifest_status="completed",
    )
    instance_path = run_root / "candidates" / "candidate-a" / "artifacts" / "instance.json"
    instance = json.loads(instance_path.read_text())
    instance.update(top_level)
    instance["derived_properties"] = derived
    instance_path.write_text(json.dumps(instance))

    with pytest.raises(SearchIntegrityError, match=r"instance.*instance\.json"):
        collect_attempt_records(attempt)


def test_install_terminal_attempt_appends_with_stable_attempt_key(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")

    update = install_terminal_attempt(tmp_path, attempt)

    assert update.appended_records == 1
    [record] = load_aggregate_records(tmp_path)
    assert record["attempt_key"] == "round-0001/attempt-001"
    assert record["candidate_id"] == "candidate-a"


def test_install_terminal_attempt_rejects_nonterminal_status(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="running", stage="materialized")

    with pytest.raises(SearchIntegrityError, match="attempt is not terminal"):
        install_terminal_attempt(tmp_path, attempt)
