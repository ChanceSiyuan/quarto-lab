from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

import pytest

from autoqec_search import quantum_tanner_long_run
from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_long_run import (
    LauncherConfig,
    allocate_attempt_dir,
    initialize_state,
    load_resume_state,
    merge_feedback,
    reject_historical_fingerprints,
)


def _config(*, rounds: int = 2) -> LauncherConfig:
    return LauncherConfig(
        rounds=rounds,
        proposals_per_round=2,
        max_group_order=32,
        max_physical_qubits=64,
        run_wall_clock="90s",
        model=None,
    )


def test_initialize_state_records_pinned_source_and_scientific_config(tmp_path: Path) -> None:
    state = initialize_state(tmp_path, source_root=tmp_path / "repo", source_commit="abc123", config=_config())
    persisted = json.loads((tmp_path / "state.json").read_text())
    assert state == persisted
    assert persisted["schema_version"] == 1
    assert persisted["source_commit"] == "abc123"
    assert persisted["configuration"]["run_wall_clock"] == "90s"
    assert persisted["next_round"] == 1
    assert persisted["accepted_fingerprints"] == []


def test_resume_allows_round_target_growth_but_rejects_scientific_drift(tmp_path: Path) -> None:
    initialize_state(tmp_path, source_root=tmp_path / "repo", source_commit="abc123", config=_config())
    resumed = load_resume_state(tmp_path, config=_config(rounds=5))
    assert resumed["target_rounds"] == 5
    with pytest.raises(SearchIntegrityError, match="configuration drift: max_group_order"):
        load_resume_state(
            tmp_path,
            config=LauncherConfig(5, 2, 48, 64, "90s", None),
        )


def test_launcher_parser_uses_conservative_optional_defaults() -> None:
    args = quantum_tanner_long_run.build_parser().parse_args(
        ["--work-root", "/tmp/qt-long-run", "--rounds", "2"]
    )

    assert args.source_root == "."
    assert args.proposals_per_round == 4
    assert args.max_group_order == 64
    assert args.max_physical_qubits == 512
    assert args.run_wall_clock == "30m"

    help_text = quantum_tanner_long_run.build_parser().format_help()
    for expected in (
        "--proposals-per-round",
        "default: 4",
        "--max-group-order",
        "default: 64",
        "--max-physical-qubits",
        "default: 512",
        "--run-wall-clock",
        "default: 30m",
    ):
        assert expected in help_text


def test_attempt_allocation_preserves_previous_attempts(tmp_path: Path) -> None:
    first = allocate_attempt_dir(tmp_path, round_number=1)
    second = allocate_attempt_dir(tmp_path, round_number=1)
    assert first.name == "attempt-001"
    assert second.name == "attempt-002"
    assert first.is_dir() and second.is_dir()


def test_mark_attempt_interrupted_preserves_existing_status_keys(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    existing = {
        "accepted": None,
        "attempt_dir": str(tmp_path),
        "round": 2,
        "stage": "prompted",
        "status": "running",
        "tool_versions": {"codex": "fake-codex 1.0"},
    }
    status_path.write_text(json.dumps(existing))

    quantum_tanner_long_run.mark_attempt_interrupted(status_path, "SIGINT")

    interrupted = json.loads(status_path.read_text())
    assert {key: interrupted[key] for key in existing} == {
        **existing,
        "status": "interrupted",
    }
    assert interrupted["signal"] == "SIGINT"


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "interrupted"])
def test_mark_attempt_interrupted_never_overwrites_terminal_status(
    tmp_path: Path,
    terminal_status: str,
) -> None:
    status_path = tmp_path / "status.json"
    existing = {
        "round": 1,
        "stage": "completed" if terminal_status == "completed" else terminal_status,
        "status": terminal_status,
    }
    status_path.write_text(json.dumps(existing, sort_keys=True))
    before = status_path.read_bytes()

    quantum_tanner_long_run.mark_attempt_interrupted(status_path, "SIGTERM")

    assert status_path.read_bytes() == before


def test_run_attempt_preserves_primary_error_when_aggregate_hook_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    work_root = tmp_path / "work"
    state = {
        "next_round": 1,
        "source_commit": "abc123",
        "tool_versions": {},
    }
    tools = quantum_tanner_long_run.Toolchain(
        codex="codex",
        qec_code="qec-code",
        rsinter="rsinter",
    )

    def broken_run_command(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("backend broke")

    def broken_install(*_args: object, **_kwargs: object) -> None:
        raise SearchIntegrityError("aggregate broke")

    monkeypatch.setattr(quantum_tanner_long_run, "run_command", broken_run_command)
    monkeypatch.setattr(
        quantum_tanner_long_run,
        "install_terminal_attempt",
        broken_install,
    )

    with pytest.raises(RuntimeError, match="backend broke"):
        quantum_tanner_long_run.run_attempt(
            source_root,
            work_root,
            state,
            _config(rounds=1),
            tools,
        )

    attempt_dir = work_root / "rounds" / "round-0001" / "attempt-001"
    status = json.loads((attempt_dir / "status.json").read_text())
    assert status["status"] == "failed"
    assert status["message"] == "backend broke"
    aggregate_error = json.loads((attempt_dir / "aggregate-error.json").read_text())
    assert aggregate_error == {
        "attempt_key": "round-0001/attempt-001",
        "error_kind": "SearchIntegrityError",
        "message": "aggregate broke",
    }


def test_attempt_signal_handlers_restore_previous_handlers(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps({"stage": "allocated", "status": "running"}))
    original_handlers = {
        attempt_signal: signal.getsignal(attempt_signal)
        for attempt_signal in (signal.SIGINT, signal.SIGTERM)
    }

    def previous_sigint(_signum: int, _frame: object) -> None:
        pass

    def previous_sigterm(_signum: int, _frame: object) -> None:
        pass

    previous_handlers = {
        signal.SIGINT: previous_sigint,
        signal.SIGTERM: previous_sigterm,
    }
    try:
        for attempt_signal, previous_handler in previous_handlers.items():
            signal.signal(attempt_signal, previous_handler)

        with quantum_tanner_long_run.attempt_signal_handlers(status_path):
            for attempt_signal, previous_handler in previous_handlers.items():
                assert signal.getsignal(attempt_signal) is not previous_handler

        for attempt_signal, previous_handler in previous_handlers.items():
            assert signal.getsignal(attempt_signal) is previous_handler
    finally:
        for attempt_signal, original_handler in original_handlers.items():
            signal.signal(attempt_signal, original_handler)


def test_reconcile_completed_attempt_rejects_ambiguous_evidence(tmp_path: Path) -> None:
    for attempt_number in (1, 2):
        attempt_dir = (
            tmp_path
            / "rounds"
            / "round-0001"
            / f"attempt-{attempt_number:03d}"
        )
        attempt_dir.mkdir(parents=True)
        (attempt_dir / "status.json").write_text(
            json.dumps(
                {
                    "attempt": attempt_number,
                    "round": 1,
                    "status": "completed",
                }
            )
        )

    with pytest.raises(SearchIntegrityError, match="ambiguous completed attempts"):
        quantum_tanner_long_run.reconcile_completed_attempt(
            tmp_path,
            {
                "accepted_fingerprints": [],
                "completed_rounds": [],
                "next_round": 1,
                "rejection_kinds": {},
                "source_commit": "abc123",
            },
        )


def test_reconcile_completed_attempt_rejects_feedback_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "rounds" / "round-0001" / "attempt-001"
    run_root = attempt_dir / "checkout" / ".worktrees" / "run" / "results"
    ingested_dir = attempt_dir / "ingested"
    run_root.mkdir(parents=True)
    ingested_dir.mkdir()
    proposal_summary_path = ingested_dir / "summary.json"
    proposal_summary_path.write_text(
        json.dumps(
            {
                "accepted": 1,
                "accepted_fingerprints": ["fp-a"],
                "rejected": 0,
            }
        )
    )
    feedback_path = run_root / "quantum-tanner-ai-feedback.json"
    feedback_path.write_text(
        json.dumps(
            {
                "accepted_fingerprints": ["fp-b"],
                "rejection_kinds": {},
            }
        )
    )
    surface_path = run_root / "surface-copy-comparison.json"
    surface_path.write_text("{}")
    (attempt_dir / "status.json").write_text(
        json.dumps(
            {
                "accepted": 1,
                "accepted_fingerprints": ["fp-a"],
                "attempt": 1,
                "attempt_dir": str(attempt_dir),
                "feedback_json": str(feedback_path),
                "proposal_summary_path": str(proposal_summary_path),
                "rejected": 0,
                "round": 1,
                "run_root": str(run_root),
                "source_commit": "abc123",
                "stage": "completed",
                "status": "completed",
                "surface_copy_json": str(surface_path),
            }
        )
    )
    state = {
        "accepted_fingerprints": [],
        "completed_rounds": [],
        "next_round": 1,
        "rejection_kinds": {},
        "source_commit": "abc123",
    }
    state_path = tmp_path / "state.json"
    cumulative_path = tmp_path / "cumulative-feedback.json"
    state_path.write_text(json.dumps(state, sort_keys=True))
    cumulative_path.write_text(
        json.dumps(
            {
                "accepted_fingerprints": [],
                "completed_attempts": [],
                "rejection_kinds": {},
            },
            sort_keys=True,
        )
    )
    state_before = state_path.read_bytes()
    cumulative_before = cumulative_path.read_bytes()

    with pytest.raises(SearchIntegrityError, match="feedback fingerprint mismatch"):
        quantum_tanner_long_run.reconcile_completed_attempt(tmp_path, state)

    assert state_path.read_bytes() == state_before
    assert cumulative_path.read_bytes() == cumulative_before


def test_reconcile_feedback_completed_crash_window_without_new_attempt(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "rounds" / "round-0001" / "attempt-001"
    run_root = attempt_dir / "checkout" / ".worktrees" / "run" / "results"
    ingested_dir = attempt_dir / "ingested"
    run_root.mkdir(parents=True)
    ingested_dir.mkdir()
    proposal_summary_path = ingested_dir / "summary.json"
    proposal_summary_path.write_text(
        json.dumps(
            {
                "accepted": 1,
                "accepted_fingerprints": ["fp-a"],
                "rejected": 0,
            }
        )
    )
    feedback_path = run_root / "quantum-tanner-ai-feedback.json"
    feedback_path.write_text(
        json.dumps(
            {
                "accepted_fingerprints": ["fp-a"],
                "rejection_kinds": {},
            }
        )
    )
    surface_path = run_root / "surface-copy-comparison.json"
    surface_path.write_text("{}")
    status_path = attempt_dir / "status.json"
    status_path.write_text(
        json.dumps(
            {
                "accepted": 1,
                "accepted_fingerprints": ["fp-a"],
                "attempt": 1,
                "attempt_dir": str(attempt_dir),
                "feedback_json": str(feedback_path),
                "proposal_summary_path": str(proposal_summary_path),
                "rejected": 0,
                "round": 1,
                "run_root": str(run_root),
                "source_commit": "abc123",
                "stage": "feedback_completed",
                "status": "running",
                "surface_copy_json": str(surface_path),
            }
        )
    )
    state = {
        "accepted_fingerprints": [],
        "completed_rounds": [],
        "next_round": 1,
        "rejection_kinds": {},
        "source_commit": "abc123",
    }
    (tmp_path / "state.json").write_text(json.dumps(state, sort_keys=True))
    (tmp_path / "cumulative-feedback.json").write_text(
        json.dumps(
            {
                "accepted_fingerprints": [],
                "completed_attempts": [],
                "rejection_kinds": {},
            },
            sort_keys=True,
        )
    )

    reconciled = quantum_tanner_long_run.reconcile_completed_attempt(tmp_path, state)

    assert reconciled["next_round"] == 2
    assert reconciled["accepted_fingerprints"] == ["fp-a"]
    assert not (attempt_dir.parent / "attempt-002").exists()
    assert json.loads(status_path.read_text())["status"] == "completed"


def test_reconcile_rejects_contradictory_feedback_completion_before_state_writes(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "rounds" / "round-0001" / "attempt-001"
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "status.json").write_text(
        json.dumps(
            {
                "attempt": 1,
                "round": 1,
                "stage": "feedback_completed",
                "status": "failed",
            }
        )
    )
    state = {
        "accepted_fingerprints": [],
        "completed_rounds": [],
        "next_round": 1,
        "rejection_kinds": {},
        "source_commit": "abc123",
    }
    state_path = tmp_path / "state.json"
    cumulative_path = tmp_path / "cumulative-feedback.json"
    state_path.write_text(json.dumps(state, sort_keys=True))
    cumulative_path.write_text(
        json.dumps(
            {
                "accepted_fingerprints": [],
                "completed_attempts": [],
                "rejection_kinds": {},
            },
            sort_keys=True,
        )
    )
    state_before = state_path.read_bytes()
    cumulative_before = cumulative_path.read_bytes()

    with pytest.raises(SearchIntegrityError, match="contradictory completion evidence"):
        quantum_tanner_long_run.reconcile_completed_attempt(tmp_path, state)

    assert state_path.read_bytes() == state_before
    assert cumulative_path.read_bytes() == cumulative_before


def test_atomic_write_json_does_not_reuse_fixed_sibling_temp(tmp_path: Path) -> None:
    fixed_temp = tmp_path / ".state.json.tmp"
    fixed_temp.write_text("unrelated temp\n")

    quantum_tanner_long_run.atomic_write_json(
        tmp_path / "state.json",
        {"status": "running"},
    )

    assert fixed_temp.read_text() == "unrelated temp\n"


def test_atomic_write_json_fsyncs_file_and_containing_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fsync_modes: list[int] = []
    real_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        fsync_modes.append(os.fstat(fd).st_mode)
        real_fsync(fd)

    monkeypatch.setattr(quantum_tanner_long_run.os, "fsync", recording_fsync)

    quantum_tanner_long_run.atomic_write_json(
        tmp_path / "state.json",
        {"status": "running"},
    )

    assert any(stat.S_ISREG(mode) for mode in fsync_modes)
    assert any(stat.S_ISDIR(mode) for mode in fsync_modes)


def test_run_command_streams_output_to_log_and_keeps_failure_concise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_run = subprocess.run
    observed_stdout: list[object] = []

    def recording_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed_stdout.append(kwargs.get("stdout"))
        return real_run(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(quantum_tanner_long_run.subprocess, "run", recording_run)
    log_path = tmp_path / "backend.log"

    with pytest.raises(SearchIntegrityError) as exc_info:
        quantum_tanner_long_run.run_command(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ['BACKEND_LINE'] * 10000); raise SystemExit(7)",
            ],
            cwd=tmp_path,
            env={**os.environ, "BACKEND_LINE": "backend-output-"},
            log_path=log_path,
        )

    assert observed_stdout and observed_stdout[0] is not subprocess.PIPE
    assert "backend-output-" in log_path.read_text()
    assert "backend-output-" not in str(exc_info.value)
    assert "command failed (7)" in str(exc_info.value)


def test_attach_candidate_witnesses_continues_after_candidate_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout = tmp_path / "checkout"
    work_root = tmp_path / "work"
    logs_dir = tmp_path / "logs"
    witnesses_dir = checkout / "campaign" / "witnesses"
    for candidate_id in ("candidate-a", "candidate-b", "candidate-c"):
        (checkout / "instances" / candidate_id).mkdir(parents=True)
    candidate_specs = [
        {
            "candidate_id": candidate_id,
            "instance_path": f"instances/{candidate_id}",
        }
        for candidate_id in ("candidate-a", "candidate-b", "candidate-c")
    ]
    attempted: list[str] = []

    def fake_run_cli(
        args: list[str],
        *,
        checkout: Path,
        work_root: Path,
        tools: quantum_tanner_long_run.Toolchain,
        log_path: Path,
    ) -> None:
        del checkout, work_root, tools, log_path
        witness_path = Path(args[args.index("--out") + 1])
        candidate_id = witness_path.name.removesuffix("-upper-bound-witness.json")
        attempted.append(candidate_id)
        if candidate_id == "candidate-b":
            raise SearchIntegrityError("incompatible witness basis: requested x, found z")
        witness_path.parent.mkdir(parents=True, exist_ok=True)
        witness_path.write_text(json.dumps({"basis": "x", "vector": [1]}))

    monkeypatch.setattr(quantum_tanner_long_run, "_run_cli", fake_run_cli)
    summary_path = witnesses_dir / "witness_finder_summary.json"

    summary = quantum_tanner_long_run.attach_candidate_witnesses(
        candidate_specs,
        checkout=checkout,
        work_root=work_root,
        tools=quantum_tanner_long_run.Toolchain(
            codex="codex",
            qec_code="qec-code",
            rsinter="rsinter",
        ),
        logs_dir=logs_dir,
        witnesses_dir=witnesses_dir,
        summary_path=summary_path,
    )

    assert attempted == ["candidate-a", "candidate-b", "candidate-c"]
    assert [candidate.get("upper_bound_witness_path") for candidate in candidate_specs] == [
        "campaign/witnesses/candidate-a-upper-bound-witness.json",
        None,
        "campaign/witnesses/candidate-c-upper-bound-witness.json",
    ]
    assert summary["counts"] == {"attached": 2, "failed": 1}
    assert [record["status"] for record in summary["candidates"]] == [
        "attached",
        "failed",
        "attached",
    ]
    assert summary["candidates"][1]["reason"] == (
        "incompatible witness basis: requested x, found z"
    )
    assert json.loads(summary_path.read_text()) == summary


def test_attach_candidate_witnesses_fails_when_none_are_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout = tmp_path / "checkout"
    work_root = tmp_path / "work"
    logs_dir = tmp_path / "logs"
    witnesses_dir = checkout / "campaign" / "witnesses"
    candidate_specs = [
        {
            "candidate_id": candidate_id,
            "instance_path": f"instances/{candidate_id}",
        }
        for candidate_id in ("candidate-a", "candidate-b")
    ]

    def failing_run_cli(*_args: object, **_kwargs: object) -> None:
        raise SearchIntegrityError("witness not found")

    monkeypatch.setattr(quantum_tanner_long_run, "_run_cli", failing_run_cli)
    summary_path = witnesses_dir / "witness_finder_summary.json"

    with pytest.raises(
        SearchIntegrityError,
        match="no proposal candidates produced compatible X witnesses",
    ):
        quantum_tanner_long_run.attach_candidate_witnesses(
            candidate_specs,
            checkout=checkout,
            work_root=work_root,
            tools=quantum_tanner_long_run.Toolchain(
                codex="codex",
                qec_code="qec-code",
                rsinter="rsinter",
            ),
            logs_dir=logs_dir,
            witnesses_dir=witnesses_dir,
            summary_path=summary_path,
        )

    summary = json.loads(summary_path.read_text())
    assert summary["counts"] == {"attached": 0, "failed": 2}
    assert [record["status"] for record in summary["candidates"]] == [
        "failed",
        "failed",
    ]


def test_feedback_merge_is_cumulative_and_historical_duplicates_fail() -> None:
    merged = merge_feedback(
        {"accepted_fingerprints": ["fp-a"], "rejection_kinds": {"BadGroup": 1}},
        {"accepted_fingerprints": ["fp-b"], "rejection_kinds": {"BadGroup": 2, "BadCode": 1}},
    )
    assert merged == {
        "accepted_fingerprints": ["fp-a", "fp-b"],
        "rejection_kinds": {"BadCode": 1, "BadGroup": 3},
    }
    with pytest.raises(SearchIntegrityError, match="historical proposal fingerprint"):
        reject_historical_fingerprints(["fp-a", "fp-c"], {"fp-a"})
