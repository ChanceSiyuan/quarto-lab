from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import tempfile
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_aggregate import (
    aggregate_paths,
    candidate_history_prompt,
    historical_fingerprints,
    initialize_aggregate,
    install_terminal_attempt,
    reconcile_terminal_attempts,
)


_DURATION_RE = re.compile(r"^([1-9][0-9]*)([smh]?)$")
_STATE_FILENAME = "state.json"
_LOCK_FILENAME = ".launcher.lock"
_PRESTATE_ENTRY_NAMES = frozenset({_LOCK_FILENAME, "toolchain", "tool-shims"})
_VERSION_LOG_FILENAMES = frozenset(
    {"codex-version.log", "qec-code-version.log", "rsinter-version.log"}
)
_TERMINAL_ATTEMPT_STATUSES = frozenset({"completed", "failed", "interrupted"})
_CAMPAIGN_ID = "quantum-tanner-autoresearch"
_CAMPAIGN_RELATIVE_ROOT = Path("campaigns/examples") / _CAMPAIGN_ID
_BASELINE_RELATIVE_PATH = Path(
    "benchmarks/baselines/rotated-surface-single-logical-p001.json"
)


@dataclass(frozen=True)
class Toolchain:
    codex: str
    qec_code: str
    rsinter: str


def _validate_positive_integer(value: object, *, name: str) -> None:
    if type(value) is not int or value < 1:
        raise SearchIntegrityError(f"{name} must be a positive integer: {value}")


def _validate_run_wall_clock(value: object) -> None:
    if not isinstance(value, str) or _DURATION_RE.fullmatch(value) is None:
        raise SearchIntegrityError(f"invalid wall-clock duration: {value}")


@dataclass(frozen=True)
class LauncherConfig:
    rounds: int
    proposals_per_round: int
    max_group_order: int
    max_physical_qubits: int
    run_wall_clock: str
    model: str | None

    def __post_init__(self) -> None:
        for name in (
            "rounds",
            "proposals_per_round",
            "max_group_order",
            "max_physical_qubits",
        ):
            _validate_positive_integer(getattr(self, name), name=name)
        _validate_run_wall_clock(self.run_wall_clock)

    def scientific_dict(self) -> dict[str, object]:
        return {
            "proposals_per_round": self.proposals_per_round,
            "max_group_order": self.max_group_order,
            "max_physical_qubits": self.max_physical_qubits,
            "run_wall_clock": self.run_wall_clock,
            "model": self.model,
        }


def _lstat_optional(path: Path, *, label: str) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SearchIntegrityError(f"cannot inspect {label}: {path}") from exc


def _is_same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _require_real_directory(
    path: Path,
    *,
    label: str,
    create: bool = False,
) -> os.stat_result:
    path = Path(path)
    path_stat = _lstat_optional(path, label=label)
    if path_stat is None and create:
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise SearchIntegrityError(f"cannot create {label}: {path}") from exc
        path_stat = _lstat_optional(path, label=label)
    if path_stat is None or not stat.S_ISDIR(path_stat.st_mode):
        raise SearchIntegrityError(f"unsafe {label}: {path}")
    return path_stat


def _require_single_link_regular(
    path: Path,
    *,
    label: str,
) -> os.stat_result:
    path_stat = _lstat_optional(Path(path), label=label)
    if (
        path_stat is None
        or not stat.S_ISREG(path_stat.st_mode)
        or path_stat.st_nlink != 1
    ):
        raise SearchIntegrityError(f"unsafe {label}: {path}")
    return path_stat


def _open_flags(*base_flags: int) -> int:
    flags = 0
    for base_flag in base_flags:
        flags |= base_flag
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return flags


@contextmanager
def _open_new_log_file(path: Path) -> Iterator[Any]:
    path = Path(path)
    _require_real_directory(path.parent, label="log directory", create=True)
    existing = _lstat_optional(path, label="log path")
    if existing is not None:
        _require_single_link_regular(path, label="log path")
        try:
            os.unlink(path)
        except OSError as exc:
            raise SearchIntegrityError(f"cannot replace log path: {path}") from exc

    file_descriptor: int | None = None
    opened_stat: os.stat_result | None = None
    try:
        try:
            file_descriptor = os.open(
                path,
                _open_flags(os.O_WRONLY, os.O_CREAT, os.O_EXCL),
                0o600,
            )
        except OSError as exc:
            raise SearchIntegrityError(f"cannot create log path: {path}") from exc
        opened_stat = os.fstat(file_descriptor)
        current_stat = _lstat_optional(path, label="log path")
        if (
            not stat.S_ISREG(opened_stat.st_mode)
            or opened_stat.st_nlink != 1
            or current_stat is None
            or not _is_same_inode(opened_stat, current_stat)
        ):
            raise SearchIntegrityError(f"unsafe log path: {path}")
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            file_descriptor = None
            yield handle
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if opened_stat is not None:
            current_stat = _lstat_optional(path, label="log path")
            if (
                current_stat is not None
                and _is_same_inode(opened_stat, current_stat)
                and not stat.S_ISREG(opened_stat.st_mode)
            ):
                os.unlink(path)


def _read_single_link_regular_text(path: Path, *, label: str) -> str:
    expected_stat = _require_single_link_regular(path, label=label)
    try:
        file_descriptor = os.open(path, _open_flags(os.O_RDONLY))
    except OSError as exc:
        raise SearchIntegrityError(f"cannot open {label}: {path}") from exc
    try:
        opened_stat = os.fstat(file_descriptor)
        current_stat = _lstat_optional(path, label=label)
        if (
            not stat.S_ISREG(opened_stat.st_mode)
            or opened_stat.st_nlink != 1
            or current_stat is None
            or not _is_same_inode(expected_stat, opened_stat)
            or not _is_same_inode(opened_stat, current_stat)
        ):
            raise SearchIntegrityError(f"unsafe {label}: {path}")
        with os.fdopen(file_descriptor, "r", encoding="utf-8") as handle:
            file_descriptor = -1
            return handle.read()
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)


def atomic_write_json(path: Path, payload: object) -> None:
    """Persist JSON through a flushed sibling temporary file and replacement."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        tmp_path.unlink(missing_ok=True)


@contextmanager
def work_root_lock(work_root: Path) -> Iterator[None]:
    work_root = Path(work_root)
    try:
        work_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SearchIntegrityError(f"cannot create work root: {work_root}") from exc
    _require_real_directory(work_root, label="work root")

    lock_path = work_root / _LOCK_FILENAME
    existing_lock = _lstat_optional(lock_path, label="launcher lock")
    if existing_lock is not None and (
        not stat.S_ISREG(existing_lock.st_mode) or existing_lock.st_nlink != 1
    ):
        raise SearchIntegrityError(f"unsafe launcher lock: {lock_path}")
    try:
        lock_descriptor = os.open(
            lock_path,
            _open_flags(
                os.O_RDWR,
                os.O_CREAT,
                getattr(os, "O_NONBLOCK", 0),
            ),
            0o600,
        )
    except OSError as exc:
        raise SearchIntegrityError(f"cannot open launcher lock: {lock_path}") from exc
    lock_acquired = False
    try:
        opened_lock = os.fstat(lock_descriptor)
        if (
            not stat.S_ISREG(opened_lock.st_mode)
            or opened_lock.st_nlink != 1
        ):
            raise SearchIntegrityError(f"unsafe launcher lock: {lock_path}")
        try:
            fcntl.flock(lock_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_acquired = True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise SearchIntegrityError(
                    f"work root is locked by another launcher: {work_root}"
                ) from exc
            raise SearchIntegrityError(f"cannot lock work root: {work_root}") from exc
        current_lock = _lstat_optional(lock_path, label="launcher lock")
        if (
            current_lock is None
            or not stat.S_ISREG(current_lock.st_mode)
            or current_lock.st_nlink != 1
            or not _is_same_inode(opened_lock, current_lock)
        ):
            raise SearchIntegrityError(f"unsafe launcher lock: {lock_path}")
        yield
    finally:
        if lock_acquired:
            fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        os.close(lock_descriptor)


def initialize_state(
    root: Path,
    *,
    source_root: Path,
    source_commit: str,
    config: LauncherConfig,
) -> dict[str, object]:
    aggregate = initialize_aggregate(root)
    state: dict[str, object] = {
        "schema_version": 1,
        "source_root": str(Path(source_root).resolve()),
        "source_commit": source_commit,
        "configuration": config.scientific_dict(),
        "target_rounds": config.rounds,
        "aggregate_ledger": str(aggregate.ledger_path),
        "aggregate_report": str(aggregate.report_path),
        "completed_rounds": [],
        "next_round": 1,
        "accepted_fingerprints": [],
        "rejection_kinds": {},
        "status": "running",
    }
    atomic_write_json(Path(root) / _STATE_FILENAME, state)
    return state


def load_resume_state(root: Path, *, config: LauncherConfig) -> dict[str, object]:
    state_path = Path(root) / _STATE_FILENAME
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SearchIntegrityError(f"invalid launcher state: {state_path}") from exc
    if not isinstance(state, dict):
        raise SearchIntegrityError(f"invalid launcher state: {state_path}")
    if state.get("schema_version") != 1:
        raise SearchIntegrityError("unsupported launcher state schema_version")

    persisted_configuration = state.get("configuration")
    if not isinstance(persisted_configuration, dict):
        raise SearchIntegrityError("invalid launcher state configuration")
    for key, expected in config.scientific_dict().items():
        if persisted_configuration.get(key) != expected:
            raise SearchIntegrityError(f"configuration drift: {key}")

    completed_rounds = state.get("completed_rounds")
    if not isinstance(completed_rounds, list):
        raise SearchIntegrityError("invalid completed_rounds in launcher state")
    if config.rounds < len(completed_rounds):
        raise SearchIntegrityError(
            "target rounds cannot be lower than completed rounds"
        )

    state["target_rounds"] = config.rounds
    return state


def _feedback_history(feedback: dict) -> tuple[list[object], dict[object, object]]:
    accepted_fingerprints = feedback.get("accepted_fingerprints")
    rejection_kinds = feedback.get("rejection_kinds")
    next_prompt_context = feedback.get("next_prompt_context")
    if isinstance(next_prompt_context, dict):
        if not isinstance(accepted_fingerprints, list):
            accepted_fingerprints = next_prompt_context.get(
                "accepted_proposal_fingerprints"
            )
        if not isinstance(rejection_kinds, dict):
            rejection_kinds = next_prompt_context.get("rejection_kinds")
    return (
        accepted_fingerprints if isinstance(accepted_fingerprints, list) else [],
        rejection_kinds if isinstance(rejection_kinds, dict) else {},
    )


def merge_feedback(existing: dict, feedback: dict) -> dict[str, object]:
    accepted_fingerprints, rejection_kinds = _feedback_history(feedback)
    accepted_fingerprints = sorted(
        set(existing.get("accepted_fingerprints", []))
        | set(accepted_fingerprints)
    )
    merged_rejection_kinds: dict[str, int] = {}
    for source in (existing.get("rejection_kinds", {}), rejection_kinds):
        for kind, count in source.items():
            merged_rejection_kinds[kind] = merged_rejection_kinds.get(kind, 0) + count
    return {
        "accepted_fingerprints": accepted_fingerprints,
        "rejection_kinds": dict(sorted(merged_rejection_kinds.items())),
    }


def reject_historical_fingerprints(
    fingerprints: list[str], historical_fingerprints: set[str]
) -> list[str]:
    duplicates = sorted(set(fingerprints) & set(historical_fingerprints))
    if duplicates:
        raise SearchIntegrityError(
            f"historical proposal fingerprint(s): {duplicates}"
        )
    return duplicates


def _sync_aggregate_state(work_root: Path, state: dict[str, Any]) -> None:
    initialize_aggregate(work_root)
    paths = aggregate_paths(work_root)
    state["aggregate_ledger"] = str(paths.ledger)
    state["aggregate_report"] = str(paths.report)


def _print_aggregate_paths(work_root: Path) -> None:
    paths = aggregate_paths(work_root)
    print(f"aggregate_ledger={paths.ledger}")
    print(f"aggregate_report={paths.report}")


def _record_aggregate_error(
    attempt_dir: Path,
    *,
    round_number: int,
    attempt_number: int,
    aggregate_exc: BaseException,
) -> None:
    try:
        atomic_write_json(
            attempt_dir / "aggregate-error.json",
            {
                "attempt_key": _completed_attempt_id(round_number, attempt_number),
                "error_kind": type(aggregate_exc).__name__,
                "message": str(aggregate_exc),
            },
        )
    except BaseException:
        pass


def _try_install_terminal_attempt_after_error(
    work_root: Path,
    attempt_dir: Path,
    *,
    round_number: int,
    attempt_number: int,
) -> None:
    try:
        install_terminal_attempt(work_root, attempt_dir)
    except BaseException as aggregate_exc:
        _record_aggregate_error(
            attempt_dir,
            round_number=round_number,
            attempt_number=attempt_number,
            aggregate_exc=aggregate_exc,
        )


def allocate_attempt_dir(root: Path, *, round_number: int) -> Path:
    _validate_positive_integer(round_number, name="round_number")
    round_dir = Path(root) / "rounds" / f"round-{round_number:04d}"
    round_dir.mkdir(parents=True, exist_ok=True)
    attempt_number = 1
    while True:
        attempt_dir = round_dir / f"attempt-{attempt_number:03d}"
        try:
            attempt_dir.mkdir()
        except FileExistsError:
            attempt_number += 1
        else:
            return attempt_dir


def resolve_executable(configured: str, *, label: str) -> str:
    if not configured:
        raise SearchIntegrityError(f"{label} executable is empty")
    if "/" in configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise SearchIntegrityError(
                f"{label} executable is not executable: {configured}"
            )
        return str(candidate.resolve())
    resolved = shutil.which(configured)
    if resolved is None:
        raise SearchIntegrityError(f"{label} executable not found on PATH: {configured}")
    return str(Path(resolved).resolve())


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    stdin_text: str | None = None,
) -> None:
    with _open_new_log_file(log_path) as log_handle:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            input=stdin_text,
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if completed.returncode != 0:
        raise SearchIntegrityError(
            f"command failed ({completed.returncode}): {' '.join(command)}; log: {log_path}"
        )


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SearchIntegrityError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}: {path}")
    return payload


def mark_attempt_interrupted(status_path: Path, signal_name: str) -> None:
    status = _read_json_object(Path(status_path), label="attempt status")
    if status.get("status") in _TERMINAL_ATTEMPT_STATUSES:
        return
    status["status"] = "interrupted"
    status["signal"] = signal_name
    atomic_write_json(Path(status_path), status)


def _install_attempt_signal_handlers(
    status_path: Path,
) -> dict[signal.Signals, Any]:
    def handle_attempt_signal(signum: int, _frame: Any) -> None:
        signal_name = signal.Signals(signum).name
        mark_attempt_interrupted(status_path, signal_name)
        raise KeyboardInterrupt(f"received {signal_name}")

    previous_handlers: dict[signal.Signals, Any] = {}
    for attempt_signal in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[attempt_signal] = signal.getsignal(attempt_signal)
        signal.signal(attempt_signal, handle_attempt_signal)
    return previous_handlers


def _restore_attempt_signal_handlers(
    previous_handlers: dict[signal.Signals, Any],
) -> None:
    for attempt_signal, previous_handler in previous_handlers.items():
        signal.signal(attempt_signal, previous_handler)


@contextmanager
def attempt_signal_handlers(status_path: Path) -> Iterator[None]:
    previous_handlers = _install_attempt_signal_handlers(Path(status_path))
    try:
        yield
    finally:
        _restore_attempt_signal_handlers(previous_handlers)


def _top_level_feedback(payload: dict[str, Any], *, label: str) -> dict[str, object]:
    accepted_fingerprints = payload.get("accepted_fingerprints")
    rejection_kinds = payload.get("rejection_kinds")
    if not isinstance(accepted_fingerprints, list) or not all(
        isinstance(value, str) for value in accepted_fingerprints
    ):
        raise SearchIntegrityError(f"invalid accepted_fingerprints in {label}")
    if len(set(accepted_fingerprints)) != len(accepted_fingerprints):
        raise SearchIntegrityError(f"duplicate accepted_fingerprints in {label}")
    if not isinstance(rejection_kinds, dict) or not all(
        isinstance(kind, str)
        and type(count) is int
        and count >= 0
        for kind, count in rejection_kinds.items()
    ):
        raise SearchIntegrityError(f"invalid rejection_kinds in {label}")
    return {
        "accepted_fingerprints": sorted(accepted_fingerprints),
        "rejection_kinds": dict(sorted(rejection_kinds.items())),
    }


def _round_feedback(payload: dict[str, Any], *, label: str) -> dict[str, object]:
    accepted_fingerprints, rejection_kinds = _feedback_history(payload)
    return _top_level_feedback(
        {
            "accepted_fingerprints": accepted_fingerprints,
            "rejection_kinds": rejection_kinds,
        },
        label=label,
    )


def _combined_feedback_history(
    state_feedback: dict[str, object],
    cumulative_feedback: dict[str, object],
) -> dict[str, object]:
    state_rejections = dict(state_feedback["rejection_kinds"])
    cumulative_rejections = dict(cumulative_feedback["rejection_kinds"])

    def dominates(left: dict[str, int], right: dict[str, int]) -> bool:
        return all(left.get(kind, 0) >= count for kind, count in right.items())

    if dominates(state_rejections, cumulative_rejections):
        rejection_kinds = state_rejections
    elif dominates(cumulative_rejections, state_rejections):
        rejection_kinds = cumulative_rejections
    else:
        raise SearchIntegrityError(
            "ambiguous rejection history between state and cumulative feedback"
        )
    return {
        "accepted_fingerprints": sorted(
            set(state_feedback["accepted_fingerprints"])
            | set(cumulative_feedback["accepted_fingerprints"])
        ),
        "rejection_kinds": dict(sorted(rejection_kinds.items())),
    }


def _completed_attempt_id(round_number: int, attempt_number: int) -> str:
    return f"round-{round_number:04d}/attempt-{attempt_number:03d}"


def _completed_attempt_ids(payload: dict[str, Any]) -> set[str]:
    values = payload.get("completed_attempts", [])
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise SearchIntegrityError("invalid completed_attempts in cumulative feedback")
    if len(set(values)) != len(values):
        raise SearchIntegrityError("duplicate completed_attempts in cumulative feedback")
    return set(values)


def _attempt_env(checkout: Path, work_root: Path, tools: Toolchain) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": (
            f"{work_root / 'tool-shims'}:{Path(tools.qec_code).parent}:"
            f"{os.environ.get('PATH', '')}"
        ),
        "PYTHONPATH": str(checkout / "src"),
    }


def _run_cli(
    args: list[str],
    *,
    checkout: Path,
    work_root: Path,
    tools: Toolchain,
    log_path: Path,
) -> None:
    run_command(
        ["python3", "-m", "autoqec_search.cli", *args],
        cwd=checkout,
        env=_attempt_env(checkout, work_root, tools),
        log_path=log_path,
    )


def _update_status(path: Path, status: dict[str, Any], *, stage: str) -> None:
    if path.exists():
        persisted = _read_json_object(path, label="attempt status")
        persisted_status = persisted.get("status")
        if (
            persisted_status in _TERMINAL_ATTEMPT_STATUSES
            and status.get("status") != persisted_status
        ):
            raise SearchIntegrityError(
                f"cannot change terminal attempt status {persisted_status!r}"
            )
    status["stage"] = stage
    atomic_write_json(path, status)


def _state_completed_attempt_ids(state: dict[str, Any]) -> set[str]:
    completed_rounds = state.get("completed_rounds")
    if not isinstance(completed_rounds, list):
        raise SearchIntegrityError("invalid completed_rounds in launcher state")
    completed_attempts: set[str] = set()
    completed_round_numbers: set[int] = set()
    for record in completed_rounds:
        if not isinstance(record, dict):
            raise SearchIntegrityError("invalid completed round record")
        round_number = record.get("round")
        attempt_number = record.get("attempt")
        if type(round_number) is not int or type(attempt_number) is not int:
            raise SearchIntegrityError("completed round is missing attempt identity")
        if round_number in completed_round_numbers:
            raise SearchIntegrityError(f"duplicate completed round: {round_number}")
        completed_round_numbers.add(round_number)
        completed_attempts.add(_completed_attempt_id(round_number, attempt_number))
    return completed_attempts


def _attempt_number(attempt_dir: Path) -> int:
    match = re.fullmatch(r"attempt-([0-9]{3,})", attempt_dir.name)
    if match is None:
        raise SearchIntegrityError(f"malformed attempt directory: {attempt_dir}")
    attempt_number = int(match.group(1))
    if attempt_number < 1 or attempt_dir.name != f"attempt-{attempt_number:03d}":
        raise SearchIntegrityError(f"malformed attempt directory: {attempt_dir}")
    return attempt_number


def _validate_completed_attempt(
    attempt_dir: Path,
    state: dict[str, Any],
    status: dict[str, Any],
) -> dict[str, Any]:
    round_number = int(state["next_round"])
    attempt_number = _attempt_number(attempt_dir)
    attempt_status = status.get("status")
    attempt_stage = status.get("stage")
    if not (
        attempt_status == "completed"
        or (attempt_status == "running" and attempt_stage == "feedback_completed")
    ):
        raise SearchIntegrityError(f"attempt is not completed: {attempt_dir}")
    if status.get("round") != round_number or status.get("attempt") != attempt_number:
        raise SearchIntegrityError(f"completed attempt identity mismatch: {attempt_dir}")
    if status.get("source_commit") != state.get("source_commit"):
        raise SearchIntegrityError(f"completed attempt source commit mismatch: {attempt_dir}")
    attempt_dir_value = status.get("attempt_dir")
    if (
        not isinstance(attempt_dir_value, str)
        or Path(attempt_dir_value).resolve() != attempt_dir.resolve()
    ):
        raise SearchIntegrityError(f"completed attempt path mismatch: {attempt_dir}")
    if attempt_stage not in {
        "completed",
        "completed_without_numerical_run",
        "feedback_completed",
    }:
        raise SearchIntegrityError(f"completed attempt has invalid stage: {attempt_dir}")

    accepted = status.get("accepted")
    rejected = status.get("rejected")
    accepted_fingerprints = status.get("accepted_fingerprints")
    if type(accepted) is not int or accepted < 0:
        raise SearchIntegrityError(f"completed attempt has invalid accepted count: {attempt_dir}")
    if type(rejected) is not int or rejected < 0:
        raise SearchIntegrityError(f"completed attempt has invalid rejected count: {attempt_dir}")
    if not isinstance(accepted_fingerprints, list) or not all(
        isinstance(value, str) for value in accepted_fingerprints
    ):
        raise SearchIntegrityError(
            f"completed attempt has invalid accepted fingerprints: {attempt_dir}"
        )
    if len(accepted_fingerprints) != accepted:
        raise SearchIntegrityError(
            f"completed attempt accepted count does not match fingerprints: {attempt_dir}"
        )
    if accepted == 0 and attempt_stage != "completed_without_numerical_run":
        raise SearchIntegrityError(
            f"proposal-only completed attempt has invalid stage: {attempt_dir}"
        )
    if accepted > 0 and attempt_stage == "completed_without_numerical_run":
        raise SearchIntegrityError(
            f"completed numerical attempt has invalid stage: {attempt_dir}"
        )

    proposal_summary_value = status.get("proposal_summary_path")
    if not isinstance(proposal_summary_value, str):
        raise SearchIntegrityError(
            f"completed attempt is missing proposal summary: {attempt_dir}"
        )
    proposal_summary_path = Path(proposal_summary_value).resolve()
    if not proposal_summary_path.is_file() or not proposal_summary_path.is_relative_to(
        attempt_dir.resolve()
    ):
        raise SearchIntegrityError(
            f"completed attempt has invalid proposal summary path: {attempt_dir}"
        )
    proposal_summary = _read_json_object(
        proposal_summary_path, label="completed attempt proposal summary"
    )
    if (
        proposal_summary.get("accepted") != accepted
        or proposal_summary.get("rejected") != rejected
        or proposal_summary.get("accepted_fingerprints") != accepted_fingerprints
    ):
        raise SearchIntegrityError(
            f"completed attempt disagrees with proposal summary: {attempt_dir}"
        )

    run_root_value = status.get("run_root")
    feedback_value = status.get("feedback_json")
    surface_value = status.get("surface_copy_json")
    if accepted == 0:
        if any(value is not None for value in (run_root_value, feedback_value, surface_value)):
            raise SearchIntegrityError(
                f"proposal-only completed attempt has numerical artifacts: {attempt_dir}"
            )
    else:
        if not all(
            isinstance(value, str)
            for value in (run_root_value, feedback_value, surface_value)
        ):
            raise SearchIntegrityError(
                f"completed numerical attempt is missing artifacts: {attempt_dir}"
            )
        run_root = Path(run_root_value).resolve()
        feedback_path = Path(feedback_value).resolve()
        surface_path = Path(surface_value).resolve()
        if (
            not run_root.is_dir()
            or not feedback_path.is_file()
            or not surface_path.is_file()
            or not run_root.is_relative_to(attempt_dir.resolve())
            or not feedback_path.is_relative_to(run_root)
            or not surface_path.is_relative_to(run_root)
        ):
            raise SearchIntegrityError(
                f"completed numerical attempt has invalid artifacts: {attempt_dir}"
            )
        status_fingerprints = _top_level_feedback(
            {
                "accepted_fingerprints": accepted_fingerprints,
                "rejection_kinds": {},
            },
            label="completed attempt status",
        )["accepted_fingerprints"]
        feedback_fingerprints = _round_feedback(
            _read_json_object(feedback_path, label="completed attempt feedback"),
            label="completed attempt feedback",
        )["accepted_fingerprints"]
        if feedback_fingerprints != status_fingerprints:
            raise SearchIntegrityError(
                f"completed attempt feedback fingerprint mismatch: {attempt_dir}"
            )
    validated_status = dict(status)
    validated_status["status"] = "completed"
    return validated_status


def complete_round(
    work_root: Path,
    state: dict[str, Any],
    attempt_result: dict[str, Any],
    *,
    recovering: bool = False,
    recovered_status_path: Path | None = None,
) -> dict[str, Any]:
    round_number = attempt_result.get("round")
    attempt_number = attempt_result.get("attempt")
    if type(round_number) is not int or round_number != state.get("next_round"):
        raise SearchIntegrityError("completed attempt does not match next_round")
    if type(attempt_number) is not int or attempt_number < 1:
        raise SearchIntegrityError("completed attempt has invalid attempt number")
    proposal_summary_path = attempt_result.get("proposal_summary_path")
    if not isinstance(proposal_summary_path, str):
        raise SearchIntegrityError("completed attempt is missing proposal summary path")
    feedback_path_value = attempt_result.get("feedback_json")
    feedback_path = (
        Path(feedback_path_value)
        if isinstance(feedback_path_value, str)
        else Path(proposal_summary_path)
    )
    _state_completed_attempt_ids(state)
    completed_rounds = state["completed_rounds"]
    completed_rounds = list(completed_rounds)
    completed_record = {
        "accepted": attempt_result["accepted"],
        "accepted_fingerprints": attempt_result["accepted_fingerprints"],
        "attempt": attempt_result["attempt"],
        "feedback_json": attempt_result["feedback_json"],
        "proposal_summary_path": proposal_summary_path,
        "rejected": attempt_result["rejected"],
        "round": attempt_result["round"],
        "run_root": attempt_result["run_root"],
        "surface_copy_json": attempt_result["surface_copy_json"],
    }
    completed_rounds.append(completed_record)

    feedback = _round_feedback(
        _read_json_object(feedback_path, label="round feedback"),
        label="round feedback",
    )
    cumulative_path = Path(work_root) / "cumulative-feedback.json"
    state_feedback = _top_level_feedback(state, label="launcher state")
    if cumulative_path.exists():
        cumulative = _read_json_object(cumulative_path, label="cumulative feedback")
    elif recovering:
        cumulative = {
            **state_feedback,
            "completed_attempts": sorted(_state_completed_attempt_ids(state)),
        }
    else:
        raise SearchIntegrityError(f"invalid cumulative feedback: {cumulative_path}")
    cumulative_feedback = _top_level_feedback(
        cumulative, label="cumulative feedback"
    )
    completed_attempt = _completed_attempt_id(round_number, attempt_number)
    applied_attempts = _completed_attempt_ids(cumulative)
    applied_attempts.update(_state_completed_attempt_ids(state))
    expected_from_state = merge_feedback(state_feedback, feedback)

    if recovering:
        if completed_attempt in applied_attempts:
            if cumulative_feedback != expected_from_state:
                raise SearchIntegrityError(
                    f"ambiguous recovery feedback for {completed_attempt}"
                )
            merged = cumulative_feedback
        elif cumulative_feedback == state_feedback:
            merged = expected_from_state
        elif cumulative_feedback == expected_from_state:
            merged = cumulative_feedback
        else:
            raise SearchIntegrityError(
                f"ambiguous recovery feedback for {completed_attempt}"
            )
    else:
        if completed_attempt in applied_attempts:
            raise SearchIntegrityError(
                f"attempt feedback is already applied: {completed_attempt}"
            )
        merged = merge_feedback(
            _combined_feedback_history(state_feedback, cumulative_feedback),
            feedback,
        )

    applied_attempts.add(completed_attempt)
    cumulative_update = {
        **merged,
        "completed_attempts": sorted(applied_attempts),
    }
    updated_state = {
        **state,
        "accepted_fingerprints": merged["accepted_fingerprints"],
        "completed_rounds": completed_rounds,
        "next_round": round_number + 1,
        "rejection_kinds": merged["rejection_kinds"],
        "status": "running",
    }
    if recovered_status_path is not None:
        atomic_write_json(recovered_status_path, attempt_result)
    atomic_write_json(cumulative_path, cumulative_update)
    atomic_write_json(Path(work_root) / _STATE_FILENAME, updated_state)
    return updated_state


def reconcile_completed_attempt(
    work_root: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    round_number = state.get("next_round")
    _validate_positive_integer(round_number, name="next_round")
    round_dir = Path(work_root) / "rounds" / f"round-{round_number:04d}"
    if not round_dir.exists():
        return state
    if not round_dir.is_dir():
        raise SearchIntegrityError(f"malformed round recovery path: {round_dir}")

    completed_attempts: list[tuple[Path, dict[str, Any]]] = []
    for attempt_dir in sorted(round_dir.iterdir()):
        if not attempt_dir.is_dir():
            raise SearchIntegrityError(f"malformed attempt recovery path: {attempt_dir}")
        attempt_number = _attempt_number(attempt_dir)
        status_path = attempt_dir / "status.json"
        if not status_path.exists():
            continue
        status = _read_json_object(status_path, label="attempt status")
        if status.get("round") != round_number or status.get("attempt") != attempt_number:
            raise SearchIntegrityError(f"attempt recovery identity mismatch: {attempt_dir}")
        attempt_status = status.get("status")
        if attempt_status not in {"running", "failed", "interrupted", "completed"}:
            raise SearchIntegrityError(f"invalid attempt recovery status: {attempt_dir}")
        feedback_complete = status.get("stage") == "feedback_completed"
        if feedback_complete and attempt_status in {"failed", "interrupted"}:
            raise SearchIntegrityError(
                f"contradictory completion evidence: {attempt_dir}"
            )
        if attempt_status == "completed" or (
            attempt_status == "running" and feedback_complete
        ):
            completed_attempts.append((attempt_dir, status))

    if len(completed_attempts) > 1:
        raise SearchIntegrityError(
            f"ambiguous completed attempts for round {round_number}"
        )
    if not completed_attempts:
        return state
    attempt_dir, status = completed_attempts[0]
    validated_status = _validate_completed_attempt(attempt_dir, state, status)
    return complete_round(
        Path(work_root),
        state,
        validated_status,
        recovering=True,
        recovered_status_path=(
            attempt_dir / "status.json"
            if status.get("status") != "completed"
            else None
        ),
    )


def _commit_generated_inputs(
    *,
    checkout: Path,
    work_root: Path,
    tools: Toolchain,
    logs_dir: Path,
) -> None:
    _run_command = lambda command, log_name: run_command(
        command,
        cwd=checkout,
        env=_attempt_env(checkout, work_root, tools),
        log_path=logs_dir / log_name,
    )
    _run_command(["git", "add", "-A"], "git-add.log")
    _run_command(
        ["git", "commit", "-m", "prepare quantum Tanner long-run inputs"],
        "git-commit.log",
    )


def _set_attempt_candidate_budget(checkout: Path, accepted_count: int) -> None:
    _validate_positive_integer(accepted_count, name="accepted_count")
    campaign_path = checkout / _CAMPAIGN_RELATIVE_ROOT / "campaign.json"
    campaign = _read_json_object(campaign_path, label="campaign")
    budget = campaign.get("budget")
    stop_conditions = campaign.get("stop_conditions")
    if not isinstance(budget, dict):
        raise SearchIntegrityError("campaign is missing budget")
    if not isinstance(stop_conditions, dict):
        raise SearchIntegrityError("campaign is missing stop_conditions")
    budget["max_candidates"] = accepted_count
    stop_conditions["max_candidates"] = accepted_count
    atomic_write_json(campaign_path, campaign)


def attach_candidate_witnesses(
    candidate_specs: list[Any],
    *,
    checkout: Path,
    work_root: Path,
    tools: Toolchain,
    logs_dir: Path,
    witnesses_dir: Path,
    summary_path: Path,
) -> dict[str, Any]:
    witnesses_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    attached = 0
    failed = 0
    for candidate in candidate_specs:
        if not isinstance(candidate, dict):
            raise SearchIntegrityError("invalid candidate spec")
        candidate_id = candidate.get("candidate_id")
        instance_path = candidate.get("instance_path")
        if not isinstance(candidate_id, str) or not isinstance(instance_path, str):
            raise SearchIntegrityError("proposal candidate is missing instance metadata")
        instance_dir = checkout / instance_path
        witness_path = witnesses_dir / f"{candidate_id}-upper-bound-witness.json"
        log_path = logs_dir / f"witness-{candidate_id}.log"
        try:
            _run_cli(
                [
                    "find-upper-bound-witness",
                    "--hx", str(instance_dir / "hx.json"),
                    "--hz", str(instance_dir / "hz.json"),
                    "--basis", "x",
                    "--out", str(witness_path),
                    "--qec-code-bin", tools.qec_code,
                    "--iterations", "1000",
                    "--restarts", "8",
                    "--seed", "12345",
                    "--timeout-seconds", "300",
                ],
                checkout=checkout,
                work_root=work_root,
                tools=tools,
                log_path=log_path,
            )
        except SearchIntegrityError as exc:
            failed += 1
            records.append(
                {
                    "candidate_id": candidate_id,
                    "log_path": str(log_path),
                    "reason": str(exc),
                    "status": "failed",
                    "witness_path": None,
                }
            )
            continue
        witness_relative_path = str(witness_path.relative_to(checkout))
        candidate["upper_bound_witness_path"] = witness_relative_path
        attached += 1
        records.append(
            {
                "candidate_id": candidate_id,
                "log_path": str(log_path),
                "reason": "verified_upper_bound_witness",
                "status": "attached",
                "witness_path": witness_relative_path,
            }
        )

    summary = {
        "schema_version": 1,
        "counts": {"attached": attached, "failed": failed},
        "candidates": records,
    }
    atomic_write_json(summary_path, summary)
    if attached == 0:
        raise SearchIntegrityError(
            "no proposal candidates produced compatible X witnesses; "
            f"summary: {summary_path}"
        )
    return summary


def run_attempt(
    source_root: Path,
    work_root: Path,
    state: dict[str, Any],
    config: LauncherConfig,
    tools: Toolchain,
) -> dict[str, Any]:
    round_number = state.get("next_round")
    _validate_positive_integer(round_number, name="next_round")
    attempt_dir = allocate_attempt_dir(work_root, round_number=round_number)
    checkout = attempt_dir / "checkout"
    request_dir = attempt_dir / "request"
    ingested_dir = attempt_dir / "ingested"
    logs_dir = attempt_dir / "logs"
    status_path = attempt_dir / "status.json"
    attempt_number = int(attempt_dir.name.removeprefix("attempt-"))
    status: dict[str, Any] = {
        "accepted": None,
        "accepted_fingerprints": [],
        "attempt": attempt_number,
        "attempt_dir": str(attempt_dir),
        "feedback_json": None,
        "proposal_summary_path": None,
        "rejected": None,
        "round": round_number,
        "run_root": None,
        "source_commit": state["source_commit"],
        "status": "running",
        "surface_copy_json": None,
        "tool_versions": state.get("tool_versions", {}),
    }
    _update_status(status_path, status, stage="allocated")

    previous_signal_handlers: dict[signal.Signals, Any] = {}
    try:
        previous_signal_handlers = _install_attempt_signal_handlers(status_path)

        clone_env = {**os.environ}
        run_command(
            ["git", "clone", "--quiet", "--local", str(source_root), str(checkout)],
            cwd=attempt_dir,
            env=clone_env,
            log_path=logs_dir / "clone.log",
        )
        run_command(
            ["git", "checkout", str(state["source_commit"])],
            cwd=checkout,
            env=clone_env,
            log_path=logs_dir / "checkout.log",
        )
        run_command(
            ["git", "config", "user.email", "autoqec@example.com"],
            cwd=checkout,
            env=clone_env,
            log_path=logs_dir / "git-email.log",
        )
        run_command(
            ["git", "config", "user.name", "AutoQEC Long Run"],
            cwd=checkout,
            env=clone_env,
            log_path=logs_dir / "git-name.log",
        )
        _update_status(status_path, status, stage="cloned")

        _run_cli(
            [
                "prepare-quantum-tanner-ai-batch",
                "--root", str(checkout),
                "--campaign", _CAMPAIGN_ID,
                "--out", str(request_dir),
                "--count", str(config.proposals_per_round),
                "--max-group-order", str(config.max_group_order),
                "--max-physical-qubits", str(config.max_physical_qubits),
                "--feedback", str(work_root / "cumulative-feedback.json"),
            ],
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            log_path=logs_dir / "prepare.log",
        )
        _update_status(status_path, status, stage="prepared")

        prompt = (request_dir / "prompt.md").read_text(encoding="utf-8")
        prompt += "\n" + candidate_history_prompt(work_root)
        prompt += (
            f"\n## round {round_number} requirements\n\n"
            "Provide non-toric proposals only.\n"
            "Use inverse-closed generator sets.\n"
            "Use local parity-check matrices over GF(2).\n"
            "Use unique proposal IDs.\n"
            "Do not repeat historical fingerprints from the feedback.\n"
        )
        prompt_path = attempt_dir / "agent-prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        _update_status(status_path, status, stage="prompted")

        codex_command = [
            tools.codex,
            "exec",
            "--ephemeral",
            "--sandbox", "read-only",
            "-C", str(checkout),
            "--output-schema", str(request_dir / "response_schema.json"),
            "--output-last-message", str(attempt_dir / "response.json"),
        ]
        if config.model is not None:
            codex_command.extend(["--model", config.model])
        codex_command.append("-")
        run_command(
            codex_command,
            cwd=checkout,
            env=_attempt_env(checkout, work_root, tools),
            log_path=logs_dir / "codex.log",
            stdin_text=prompt,
        )
        _update_status(status_path, status, stage="codex_completed")

        _run_cli(
            [
                "ingest-quantum-tanner-ai-batch",
                "--root", str(checkout),
                "--response", str(attempt_dir / "response.json"),
                "--out", str(ingested_dir),
                "--max-group-order", str(config.max_group_order),
                "--max-physical-qubits", str(config.max_physical_qubits),
            ],
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            log_path=logs_dir / "ingest.log",
        )
        summary = _read_json_object(ingested_dir / "summary.json", label="ingestion summary")
        accepted = summary.get("accepted")
        if type(accepted) is not int or accepted < 0:
            raise SearchIntegrityError("invalid accepted count in ingestion summary")
        rejected = summary.get("rejected")
        if type(rejected) is not int or rejected < 0:
            raise SearchIntegrityError("invalid rejected count in ingestion summary")
        accepted_fingerprints = summary.get("accepted_fingerprints")
        if not isinstance(accepted_fingerprints, list) or not all(
            isinstance(value, str) for value in accepted_fingerprints
        ):
            raise SearchIntegrityError(
                "invalid accepted_fingerprints in ingestion summary"
            )
        state_feedback = _top_level_feedback(state, label="launcher state")
        cumulative_feedback = _top_level_feedback(
            _read_json_object(
                Path(work_root) / "cumulative-feedback.json",
                label="cumulative feedback",
            ),
            label="cumulative feedback",
        )
        reject_historical_fingerprints(
            accepted_fingerprints,
            set(state_feedback["accepted_fingerprints"])
            | set(cumulative_feedback["accepted_fingerprints"])
            | historical_fingerprints(work_root),
        )
        status["accepted"] = accepted
        status["accepted_fingerprints"] = accepted_fingerprints
        status["proposal_summary_path"] = str(ingested_dir / "summary.json")
        status["rejected"] = rejected
        _update_status(status_path, status, stage="ingested")

        if accepted == 0:
            status["status"] = "completed"
            _update_status(status_path, status, stage="completed_without_numerical_run")
            install_terminal_attempt(work_root, attempt_dir)
            return status

        search_space_path = checkout / _CAMPAIGN_RELATIVE_ROOT / "search_space.json"
        search_space_path.unlink()
        proposal_args: list[str] = []
        accepted_records = summary.get("accepted_records", [])
        if not isinstance(accepted_records, list):
            raise SearchIntegrityError("invalid accepted_records in ingestion summary")
        for record in accepted_records:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                raise SearchIntegrityError("invalid accepted proposal record")
            proposal_args.extend(["--proposal", str(ingested_dir / record["path"])])
        _run_cli(
            [
                "materialize-quantum-tanner-proposals",
                "--root", str(checkout),
                "--out-root", str(_CAMPAIGN_RELATIVE_ROOT / "proposal-instances"),
                "--qec-code-bin", tools.qec_code,
                "--max-group-order", str(config.max_group_order),
                "--force",
                *proposal_args,
            ],
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            log_path=logs_dir / "materialize.log",
        )
        _update_status(status_path, status, stage="materialized")

        _run_cli(
            [
                "import-quantum-tanner-proposal-instances",
                "--root", str(checkout),
                "--campaign", _CAMPAIGN_ID,
                "--instance-root", str(_CAMPAIGN_RELATIVE_ROOT / "proposal-instances"),
                "--search-space", str(_CAMPAIGN_RELATIVE_ROOT / "search_space.json"),
            ],
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            log_path=logs_dir / "import.log",
        )
        _update_status(status_path, status, stage="imported")

        search_space = _read_json_object(search_space_path, label="search space")
        candidate_specs = search_space.get("candidate_specs")
        if not isinstance(candidate_specs, list) or not candidate_specs:
            raise SearchIntegrityError("proposal import created no candidate specs")
        if len(candidate_specs) != accepted:
            raise SearchIntegrityError(
                "proposal import candidate count does not match accepted proposals"
            )
        _set_attempt_candidate_budget(checkout, accepted)
        witnesses_dir = checkout / _CAMPAIGN_RELATIVE_ROOT / "witnesses"
        witness_summary_path = witnesses_dir / "witness_finder_summary.json"
        witness_summary = attach_candidate_witnesses(
            candidate_specs,
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            logs_dir=logs_dir,
            witnesses_dir=witnesses_dir,
            summary_path=witness_summary_path,
        )
        status["witness_summary_path"] = str(witness_summary_path)
        status["witness_attached"] = witness_summary["counts"]["attached"]
        status["witness_failed"] = witness_summary["counts"]["failed"]
        atomic_write_json(search_space_path, search_space)
        _update_status(status_path, status, stage="witnesses_completed")

        _run_cli(
            [
                "complete-quantum-tanner-proposal-observables",
                "--root", str(checkout),
                "--search-space", str(_CAMPAIGN_RELATIVE_ROOT / "search_space.json"),
                "--basis", "x",
                "--qec-code-bin", tools.qec_code,
                "--force",
            ],
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            log_path=logs_dir / "observables.log",
        )
        _update_status(status_path, status, stage="observables_completed")

        _run_cli(
            ["validate", "--root", str(checkout)],
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            log_path=logs_dir / "validate.log",
        )
        _commit_generated_inputs(
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            logs_dir=logs_dir,
        )
        _update_status(status_path, status, stage="inputs_committed")

        run_id = f"qt-long-r{round_number:04d}-a{attempt_dir.name[-3:]}"
        _run_cli(
            [
                "run",
                "--root", str(checkout),
                "--campaign", _CAMPAIGN_ID,
                "--wall-clock", config.run_wall_clock,
                "--run-id", run_id,
                "--distance-method", "random-window-upper-bound",
                "--qec-code-bin", tools.qec_code,
            ],
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            log_path=logs_dir / "run.log",
        )
        run_worktree = checkout / ".worktrees" / run_id
        run_root = run_worktree / "results/search" / _CAMPAIGN_ID / run_id
        status["run_root"] = str(run_root)
        _update_status(status_path, status, stage="numerical_run_completed")

        surface_html = run_root / "surface-copy-comparison.html"
        _run_cli(
            [
                "compare-surface-copy",
                "--root", str(run_worktree),
                "--run", str(Path("results/search") / _CAMPAIGN_ID / run_id),
                "--baseline", str(_BASELINE_RELATIVE_PATH),
                "--out", str(surface_html),
            ],
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            log_path=logs_dir / "surface-copy.log",
        )
        surface_json = run_root / "surface-copy-comparison.json"
        feedback_json = run_root / "quantum-tanner-ai-feedback.json"
        _run_cli(
            [
                "summarize-quantum-tanner-ai-feedback",
                "--root", str(run_worktree),
                "--run", str(Path("results/search") / _CAMPAIGN_ID / run_id),
                "--proposal-summary", str(ingested_dir / "summary.json"),
                "--surface-copy", str(surface_json),
                "--out-json", str(feedback_json),
                "--out-html", str(run_root / "quantum-tanner-ai-feedback.html"),
            ],
            checkout=checkout,
            work_root=work_root,
            tools=tools,
            log_path=logs_dir / "feedback.log",
        )
        status["surface_copy_json"] = str(surface_json)
        status["feedback_json"] = str(feedback_json)
        status["status"] = "completed"
        _update_status(status_path, status, stage="completed")
        install_terminal_attempt(work_root, attempt_dir)
        return status
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            mark_attempt_interrupted(status_path, "KeyboardInterrupt")
        else:
            persisted_status = _read_json_object(status_path, label="attempt status")
            if persisted_status.get("status") not in _TERMINAL_ATTEMPT_STATUSES:
                status["error_kind"] = type(exc).__name__
                status["failed_stage"] = status.get("stage")
                status["message"] = str(exc)
                status["status"] = "failed"
                _update_status(status_path, status, stage="failed")
        _try_install_terminal_attempt_after_error(
            work_root,
            attempt_dir,
            round_number=round_number,
            attempt_number=attempt_number,
        )
        raise
    finally:
        _restore_attempt_signal_handlers(previous_signal_handlers)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run quantum Tanner Codex proposal and numerical-search rounds",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source-root",
        default=".",
        help="caller source checkout",
    )
    parser.add_argument("--source-commit", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--work-root", required=True, help="persistent launcher work root")
    parser.add_argument("--rounds", required=True, type=int, help="target round count")
    parser.add_argument(
        "--proposals-per-round",
        default=4,
        type=int,
        help="requested proposals in each round",
    )
    parser.add_argument(
        "--max-group-order",
        default=64,
        type=int,
        help="maximum accepted base-group order",
    )
    parser.add_argument(
        "--max-physical-qubits",
        default=512,
        type=int,
        help="physical-qubit limit",
    )
    parser.add_argument(
        "--run-wall-clock",
        default="30m",
        help="wall-clock limit for each numerical run",
    )
    parser.add_argument("--model", default=None, help="optional Codex model override")
    parser.add_argument("--resume", action="store_true", help="resume an existing run")
    return parser


def _source_commit(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise SearchIntegrityError(f"cannot resolve source commit: {source_root}")
    return completed.stdout.strip()


def _source_is_dirty(source_root: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "status", "--porcelain"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise SearchIntegrityError(f"cannot inspect source checkout: {source_root}")
    return bool(completed.stdout.strip())


def _validate_toolchain_directory(path: Path, *, create: bool) -> None:
    _require_real_directory(path, label="toolchain directory", create=create)
    for child in path.iterdir():
        if child.name not in _VERSION_LOG_FILENAMES:
            raise SearchIntegrityError(f"unsafe toolchain entry: {child}")
        _require_single_link_regular(child, label="tool version log")


def _validate_tool_shim_directory(path: Path, *, create: bool) -> None:
    _require_real_directory(path, label="tool-shims directory", create=create)
    for child in path.iterdir():
        child_stat = _lstat_optional(child, label="tool shim")
        if (
            child.name != "rsinter"
            or child_stat is None
            or not stat.S_ISLNK(child_stat.st_mode)
        ):
            raise SearchIntegrityError(f"unsafe tool shim: {child}")


def _replace_rsinter_shim(shim_dir: Path, target: str) -> None:
    _validate_tool_shim_directory(shim_dir, create=True)
    shim_path = shim_dir / "rsinter"
    shim_stat = _lstat_optional(shim_path, label="rsinter shim")
    if shim_stat is not None:
        if not stat.S_ISLNK(shim_stat.st_mode):
            raise SearchIntegrityError(f"unsafe rsinter shim: {shim_path}")
        try:
            os.unlink(shim_path)
        except OSError as exc:
            raise SearchIntegrityError(
                f"cannot replace rsinter shim: {shim_path}"
            ) from exc
    try:
        os.symlink(target, shim_path)
    except OSError as exc:
        raise SearchIntegrityError(f"cannot create rsinter shim: {shim_path}") from exc


def _preflight_tools(source_root: Path, work_root: Path) -> tuple[Toolchain, dict[str, str]]:
    tools = Toolchain(
        codex=resolve_executable(os.environ.get("CODEX_BIN", "codex"), label="codex"),
        qec_code=resolve_executable(
            os.environ.get("QEC_CODE_BIN", "qec-code"), label="qec-code"
        ),
        rsinter=resolve_executable(os.environ.get("RSINTER_BIN", "rsinter"), label="rsinter"),
    )
    _require_real_directory(work_root, label="work root")
    version_dir = work_root / "toolchain"
    _validate_toolchain_directory(version_dir, create=True)
    versions: dict[str, str] = {}
    for label, executable, probe_args in (
        ("codex", tools.codex, ("--version",)),
        ("qec-code", tools.qec_code, ("--help",)),
        ("rsinter", tools.rsinter, ("--version",)),
    ):
        log_path = version_dir / f"{label}-version.log"
        run_command(
            [executable, *probe_args],
            cwd=source_root,
            env={**os.environ},
            log_path=log_path,
        )
        versions[label] = _read_single_link_regular_text(
            log_path,
            label=f"{label} version log",
        ).strip()
    shim_dir = work_root / "tool-shims"
    _replace_rsinter_shim(shim_dir, tools.rsinter)
    return tools, versions


def _validate_prestate_work_root(work_root: Path) -> None:
    entries = {entry.name: entry for entry in work_root.iterdir()}
    if set(entries) - _PRESTATE_ENTRY_NAMES:
        raise SearchIntegrityError("work root must be empty for a new run")

    lock_path = entries.get(_LOCK_FILENAME)
    if lock_path is not None:
        _require_single_link_regular(lock_path, label="launcher lock")

    toolchain_dir = entries.get("toolchain")
    if toolchain_dir is not None:
        _validate_toolchain_directory(toolchain_dir, create=False)

    shim_dir = entries.get("tool-shims")
    if shim_dir is not None:
        _validate_tool_shim_directory(shim_dir, create=False)


def _run_locked_launcher(
    args: argparse.Namespace,
    config: LauncherConfig,
    caller_source_root: Path,
    work_root: Path,
) -> int:
    source_root = caller_source_root
    state_path = work_root / _STATE_FILENAME
    cumulative_path = work_root / "cumulative-feedback.json"
    source_commit: str

    if args.resume:
        if not state_path.is_file():
            raise SearchIntegrityError("resume requires existing state.json")
        state = load_resume_state(work_root, config=config)
        _sync_aggregate_state(work_root, state)
        pinned_source_root = state.get("source_root")
        if not isinstance(pinned_source_root, str):
            raise SearchIntegrityError("invalid source_root in launcher state")
        source_root = Path(pinned_source_root).resolve()
        if source_root != caller_source_root:
            raise SearchIntegrityError(
                "resume source root differs from pinned source_root"
            )
        if not source_root.is_dir():
            raise SearchIntegrityError(
                f"pinned source root does not exist: {source_root}"
            )
        source_commit_value = state.get("source_commit")
        if not isinstance(source_commit_value, str) or not source_commit_value:
            raise SearchIntegrityError("invalid source_commit in launcher state")
        source_commit = source_commit_value
        current_source_commit = _source_commit(source_root)
        if current_source_commit != source_commit or (
            args.source_commit is not None and args.source_commit != source_commit
        ):
            raise SearchIntegrityError(
                "source HEAD differs from pinned source_commit"
            )

        if cumulative_path.exists():
            cumulative = _read_json_object(
                cumulative_path, label="cumulative feedback"
            )
            _top_level_feedback(cumulative, label="cumulative feedback")
            _completed_attempt_ids(cumulative)
        reconcile_terminal_attempts(work_root)

        while True:
            previous_round = int(state["next_round"])
            state = reconcile_completed_attempt(work_root, state)
            if int(state["next_round"]) == previous_round:
                break

        if not cumulative_path.exists():
            state_feedback = _top_level_feedback(state, label="launcher state")
            atomic_write_json(
                cumulative_path,
                {
                    **state_feedback,
                    "completed_attempts": sorted(
                        _state_completed_attempt_ids(state)
                    ),
                },
            )
        if int(state["next_round"]) > int(state["target_rounds"]):
            state["status"] = "completed"
            atomic_write_json(state_path, state)
            _print_aggregate_paths(work_root)
            return 0
    else:
        _validate_prestate_work_root(work_root)
        current_source_commit = _source_commit(source_root)
        if (
            args.source_commit is not None
            and args.source_commit != current_source_commit
        ):
            raise SearchIntegrityError(
                "source HEAD changed during launcher bootstrap"
            )
        source_commit = current_source_commit

    tools, versions = _preflight_tools(source_root, work_root)
    if _source_is_dirty(source_root):
        print(
            "source checkout is dirty; uncommitted changes are excluded",
            file=os.sys.stderr,
        )

    if not args.resume:
        state = initialize_state(
            work_root,
            source_root=source_root,
            source_commit=source_commit,
            config=config,
        )
        atomic_write_json(
            cumulative_path,
            {
                "accepted_fingerprints": [],
                "completed_attempts": [],
                "rejection_kinds": {},
            },
        )
    state["tool_versions"] = versions
    if int(state["next_round"]) <= int(state["target_rounds"]):
        state["status"] = "running"
    atomic_write_json(state_path, state)

    while int(state["next_round"]) <= int(state["target_rounds"]):
        attempt_result = run_attempt(source_root, work_root, state, config, tools)
        state = complete_round(work_root, state, attempt_result)
    state["status"] = "completed"
    atomic_write_json(state_path, state)
    _print_aggregate_paths(work_root)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = LauncherConfig(
            rounds=args.rounds,
            proposals_per_round=args.proposals_per_round,
            max_group_order=args.max_group_order,
            max_physical_qubits=args.max_physical_qubits,
            run_wall_clock=args.run_wall_clock,
            model=args.model,
        )
        source_root = Path(args.source_root).resolve()
        work_root = Path(args.work_root).resolve()
        if not source_root.is_dir():
            raise SearchIntegrityError(f"source root does not exist: {source_root}")
        if work_root.exists() and not work_root.is_dir():
            raise SearchIntegrityError(f"work root is not a directory: {work_root}")
        try:
            work_root.relative_to(source_root)
        except ValueError:
            pass
        else:
            raise SearchIntegrityError("--work-root must be outside the caller checkout")

        with work_root_lock(work_root):
            return _run_locked_launcher(
                args,
                config,
                source_root,
                work_root,
            )
    except SearchIntegrityError as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=os.sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
