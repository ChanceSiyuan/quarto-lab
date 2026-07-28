"""Private CSS-distance holdout materialization and candidate evaluation."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import tempfile
import time
from typing import Callable, Iterable
from uuid import uuid4

from autoqec_search.css_distance_container import CssDistanceInfrastructureError
from autoqec_search.structure import verify_css_upper_bound_witness


DEFAULT_TIMEOUT_SECONDS = 300
_OUTPUT_LIMIT_BYTES = 64 * 1024
_MAX_JSON_INPUT_BYTES = 64 * 1024 * 1024
JsonFileIdentity = tuple[int, int, int, int, int, int, int, str]
_SELECTED = (
    ("surface-rotated-d21", "regression", 1),
    ("toric-d17", "discrimination", 2),
    ("toric-d21", "discrimination", 2),
    ("bb72", "regression", 1),
    ("bb144", "regression", 1),
    ("bb288-same-shifts", "discrimination", 2),
    ("bb432-same-shifts", "discrimination", 2),
    ("apm-kasai-p96", "stress", 3),
    ("apm-kasai-p192", "stress", 3),
    ("quantum-tanner-toric-d8", "regression", 1),
)
_SCREENING_SEED = 731_917
_FINALIST_SEEDS = (104_729, 130_363, 155_921)
_DECISIONS = {"accepted", "rejected", "baseline", "failed"}
_PIPE_GRACE_SECONDS = 0.2
_SAFE_LOG_FIELDS = {
    "runs",
    "verified_witnesses",
    "target_hits",
    "timeouts",
    "crashes",
    "invalid_claims",
    "weighted_target_hits",
    "normalized_quality",
    "runtime_seconds",
    "average_seconds",
    "median_seconds",
    "p95_seconds",
    "accepted",
    "decision",
}
CandidateCommandBuilder = Callable[..., list[str]]


@dataclass(frozen=True)
class JsonFileSnapshot:
    path: Path = field(repr=False)
    identity: JsonFileIdentity = field(repr=False)


@dataclass(frozen=True)
class MatrixPairSnapshot:
    hx: JsonFileSnapshot = field(repr=False)
    hz: JsonFileSnapshot = field(repr=False)


class CssDistanceEvalError(ValueError):
    """Raised when a holdout input cannot be materialized safely."""


def _safe_relative_path(value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CssDistanceEvalError(f"unsafe {label}")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise CssDistanceEvalError(f"unsafe {label}")
    return path


def _open_directory(path: Path, *, create: bool = False) -> int:
    """Walk every path component descriptor-relatively without following links."""

    if ".." in path.parts:
        raise CssDistanceEvalError("unsafe directory")
    absolute = path.absolute()
    anchor = Path(absolute.anchor)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(anchor, flags)
    except OSError as error:
        raise CssDistanceEvalError("unsafe directory") from error
    try:
        for component in absolute.parts[1:]:
            next_descriptor = _open_directory_at(
                descriptor,
                component,
                create=create,
            )
            os.close(descriptor)
            descriptor = next_descriptor
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _open_directory_at(parent_fd: int, name: str, *, create: bool = False) -> int:
    if create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise CssDistanceEvalError("unsafe directory") from error
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise CssDistanceEvalError("unsafe directory")
    return descriptor


def _open_regular_at(root_fd: int, relative: Path) -> int:
    descriptor = os.dup(root_fd)
    try:
        for component in relative.parts[:-1]:
            next_descriptor = _open_directory_at(descriptor, component)
            os.close(descriptor)
            descriptor = next_descriptor
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        file_descriptor = os.open(relative.name, flags, dir_fd=descriptor)
        if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
            os.close(file_descriptor)
            raise CssDistanceEvalError("unsafe holdout artifact")
        return file_descriptor
    except OSError as error:
        raise CssDistanceEvalError("unsafe holdout artifact") from error
    finally:
        os.close(descriptor)


def _atomic_bytes_at(directory_fd: int, name: str, chunks: Iterable[bytes]) -> None:
    temporary = f".{name}.{uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600, dir_fd=directory_fd)
    try:
        for chunk in chunks:
            view = memoryview(chunk)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
        os.fsync(descriptor)
    except Exception:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(descriptor)
    os.replace(
        temporary,
        name,
        src_dir_fd=directory_fd,
        dst_dir_fd=directory_fd,
    )


def _copy_fd_atomic(source_fd: int, destination_fd: int, name: str) -> None:
    def chunks() -> Iterable[bytes]:
        while True:
            chunk = os.read(source_fd, 64 * 1024)
            if not chunk:
                break
            yield chunk

    _atomic_bytes_at(destination_fd, name, chunks())


def _remove_tree_at(parent_fd: int, name: str) -> None:
    try:
        directory_fd = _open_directory_at(parent_fd, name)
    except CssDistanceEvalError:
        try:
            os.unlink(name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        return
    try:
        for child in os.listdir(directory_fd):
            metadata = os.stat(child, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                _remove_tree_at(directory_fd, child)
            else:
                os.unlink(child, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)
    os.rmdir(name, dir_fd=parent_fd)


def _load_json_nofollow(
    path: Path,
    *,
    expected_identity: object | None = None,
) -> dict:
    payload, _ = _read_json_nofollow(
        path,
        expected_identity=expected_identity,
    )
    return payload


def _read_json_nofollow(
    path: Path,
    *,
    expected_identity: object | None = None,
) -> tuple[dict, JsonFileIdentity]:
    if ".." in path.parts:
        _raise_json_input_error(expected_identity)
    identity = _validate_expected_identity(expected_identity)
    try:
        parent_fd = _open_directory(path.absolute().parent)
    except (OSError, CssDistanceEvalError) as error:
        _raise_json_input_error(expected_identity, error=error)
    descriptor = -1
    try:
        descriptor = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > _MAX_JSON_INPUT_BYTES
        ):
            _raise_json_input_error(expected_identity)
        if identity is not None and _json_metadata_identity(before) != identity[:7]:
            _raise_json_input_error(expected_identity)
        chunks: list[bytes] = []
        digest = hashlib.sha256()
        total_bytes = 0
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > _MAX_JSON_INPUT_BYTES:
                _raise_json_input_error(expected_identity)
            chunks.append(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
        current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            any(
                getattr(before, field) != getattr(after, field)
                for field in stable_fields
            )
            or any(
                getattr(after, field) != getattr(current, field)
                for field in stable_fields
            )
            or not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or current.st_size > _MAX_JSON_INPUT_BYTES
        ):
            _raise_json_input_error(expected_identity)
        if identity is not None:
            if any(
                _json_metadata_identity(metadata) != identity[:7]
                for metadata in (after, current)
            ) or not hmac.compare_digest(digest.hexdigest(), identity[7]):
                _raise_json_input_error(expected_identity)
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except CssDistanceInfrastructureError:
        raise
    except (OSError, CssDistanceEvalError) as error:
        _raise_json_input_error(expected_identity, error=error)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)
    if not isinstance(payload, dict):
        raise CssDistanceEvalError("invalid JSON input")
    return payload, _json_file_identity(after, digest.hexdigest())


def load_public_smoke_snapshot(case_root: Path) -> MatrixPairSnapshot:
    """Load and pin the checked-in public smoke matrix pair."""

    root = Path(os.path.abspath(case_root))
    try:
        _, hx_identity = _read_json_nofollow(root / "hx.json")
        _, hz_identity = _read_json_nofollow(root / "hz.json")
        snapshot = MatrixPairSnapshot(
            hx=JsonFileSnapshot(path=root / "hx.json", identity=hx_identity),
            hz=JsonFileSnapshot(path=root / "hz.json", identity=hz_identity),
        )
        validate_public_smoke_snapshot(snapshot)
        return snapshot
    except Exception:
        raise CssDistanceEvalError("unsafe public smoke input") from None


def validate_public_smoke_snapshot(snapshot: MatrixPairSnapshot) -> None:
    """Reject public smoke path, metadata, or byte drift."""

    try:
        if type(snapshot) is not MatrixPairSnapshot:
            raise ValueError("invalid public smoke snapshot")
        if (
            type(snapshot.hx) is not JsonFileSnapshot
            or type(snapshot.hz) is not JsonFileSnapshot
            or not isinstance(snapshot.hx.path, Path)
            or not isinstance(snapshot.hz.path, Path)
            or not snapshot.hx.path.is_absolute()
            or not snapshot.hz.path.is_absolute()
            or ".." in snapshot.hx.path.parts
            or ".." in snapshot.hz.path.parts
            or snapshot.hx.path.name != "hx.json"
            or snapshot.hz.path.name != "hz.json"
            or snapshot.hx.path.parent != snapshot.hz.path.parent
            or snapshot.hx.path == snapshot.hz.path
        ):
            raise ValueError("invalid public smoke snapshot")
        _load_json_nofollow(
            snapshot.hx.path,
            expected_identity=snapshot.hx.identity,
        )
        _load_json_nofollow(
            snapshot.hz.path,
            expected_identity=snapshot.hz.identity,
        )
    except Exception:
        raise CssDistanceInfrastructureError(
            "public smoke snapshot changed"
        ) from None


def public_smoke_case_input(snapshot: MatrixPairSnapshot) -> dict:
    """Return evaluator input only after revalidating the pinned pair."""

    validate_public_smoke_snapshot(snapshot)
    return {
        "hx_path": snapshot.hx.path,
        "hz_path": snapshot.hz.path,
        "hx_identity": snapshot.hx.identity,
        "hz_identity": snapshot.hz.identity,
    }


def _validate_expected_identity(
    expected_identity: object | None,
) -> JsonFileIdentity | None:
    if expected_identity is None:
        return None
    if (
        not isinstance(expected_identity, tuple)
        or len(expected_identity) != 8
        or any(type(value) is not int for value in expected_identity[:7])
        or not isinstance(expected_identity[7], str)
        or len(expected_identity[7]) != 64
        or any(character not in "0123456789abcdef" for character in expected_identity[7])
    ):
        raise CssDistanceInfrastructureError(
            "development matrix identity is invalid"
        )
    return expected_identity


def _json_metadata_identity(
    metadata: os.stat_result,
) -> tuple[int, int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _json_file_identity(
    metadata: os.stat_result,
    digest: str,
) -> JsonFileIdentity:
    return (*_json_metadata_identity(metadata), digest)


def _raise_json_input_error(
    expected_identity: object | None,
    *,
    error: BaseException | None = None,
) -> None:
    if expected_identity is not None:
        exception = CssDistanceInfrastructureError(
            "development matrix identity changed"
        )
    else:
        exception = CssDistanceEvalError("unsafe JSON input")
    if error is None:
        raise exception
    raise exception from error


def materialize_private_holdout(*, ladder_path: Path, work_root: Path) -> dict:
    """Copy the fixed, opaque ten-case holdout into ``work_root/private``.

    Returned metadata deliberately excludes source identities and answer keys.
    The private ``answers.json`` contains those data and must never be logged.
    """

    ladder_path = ladder_path.absolute()
    payload = _load_json_nofollow(ladder_path)
    artifact_root = _safe_relative_path(payload.get("artifact_root"), label="artifact root")

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise CssDistanceEvalError("invalid distance ladder entries")
    by_id = {
        entry.get("instance_id"): entry for entry in entries if isinstance(entry, dict)
    }
    if set(source_id for source_id, _, _ in _SELECTED) - set(by_id):
        raise CssDistanceEvalError("distance ladder is missing required holdout cases")

    work_root = work_root.absolute()
    work_fd = _open_directory(work_root, create=True)
    try:
        private_fd = _open_directory_at(work_fd, "private", create=True)
    finally:
        os.close(work_fd)
    private_parent = work_root / "private"
    destination = private_parent / "holdout"
    try:
        os.stat("holdout", dir_fd=private_fd, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        os.close(private_fd)
        raise CssDistanceEvalError("private holdout already exists")
    staging_name = f".holdout-{uuid4().hex}"
    os.mkdir(staging_name, mode=0o700, dir_fd=private_fd)
    staging_fd = _open_directory_at(private_fd, staging_name)
    ladder_parent_fd = _open_directory(ladder_path.parent)
    source_root_fd = ladder_parent_fd
    try:
        for component in artifact_root.parts:
            next_fd = _open_directory_at(source_root_fd, component)
            if source_root_fd != ladder_parent_fd:
                os.close(source_root_fd)
            source_root_fd = next_fd
    except Exception:
        if source_root_fd != ladder_parent_fd:
            os.close(source_root_fd)
        os.close(ladder_parent_fd)
        os.close(staging_fd)
        _remove_tree_at(private_fd, staging_name)
        os.close(private_fd)
        raise
    answers: list[dict] = []
    public_cases: list[dict] = []
    try:
        for index, (source_id, tier, weight) in enumerate(_SELECTED, start=1):
            entry = by_id[source_id]
            case_id = f"case-{index:04d}"
            hx_source_fd = _open_regular_at(source_root_fd, Path(source_id) / "hx.json")
            try:
                hz_source_fd = _open_regular_at(source_root_fd, Path(source_id) / "hz.json")
            except Exception:
                os.close(hx_source_fd)
                raise
            target = entry.get("expected_distance")
            bound_type = entry.get("expected_bound_type")
            if type(target) is not int or target <= 0 or bound_type not in {"exact", "upper"}:
                os.close(hx_source_fd)
                os.close(hz_source_fd)
                raise CssDistanceEvalError("invalid required holdout answer")
            os.mkdir(case_id, mode=0o700, dir_fd=staging_fd)
            case_fd = _open_directory_at(staging_fd, case_id)
            try:
                _copy_fd_atomic(hx_source_fd, case_fd, "hx.json")
                _copy_fd_atomic(hz_source_fd, case_fd, "hz.json")
            finally:
                os.close(case_fd)
                os.close(hx_source_fd)
                os.close(hz_source_fd)
            public_cases.append(
                {
                    "case_id": case_id,
                    "tier": tier,
                    "weight": weight,
                    "hx_path": destination / case_id / "hx.json",
                    "hz_path": destination / case_id / "hz.json",
                }
            )
            answers.append(
                {
                    "case_id": case_id,
                    "source_id": source_id,
                    "target": target,
                    "bound_type": bound_type,
                    "tier": tier,
                    "weight": weight,
                }
            )
        answer_payload = {
            "screening_seed": _SCREENING_SEED,
            "finalist_seeds": list(_FINALIST_SEEDS),
            "cases": answers,
        }
        _atomic_bytes_at(
            staging_fd,
            "answers.json",
            [(json.dumps(answer_payload, sort_keys=True, indent=2) + "\n").encode()],
        )
        os.replace(
            staging_name,
            "holdout",
            src_dir_fd=private_fd,
            dst_dir_fd=private_fd,
        )
    except Exception:
        _remove_tree_at(private_fd, staging_name)
        raise
    finally:
        if source_root_fd != ladder_parent_fd:
            os.close(source_root_fd)
        os.close(ladder_parent_fd)
        os.close(staging_fd)
        os.close(private_fd)
    return {"cases": public_cases}


class _BoundedCapture:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._data = bytearray()
        self.truncated = False

    def add(self, chunk: bytes) -> None:
        remaining = self._limit - len(self._data)
        if remaining > 0:
            self._data.extend(chunk[:remaining])
        if len(chunk) > max(remaining, 0):
            self.truncated = True

    def text(self) -> str:
        return bytes(self._data).decode("utf-8", errors="replace")


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except (ProcessLookupError, PermissionError):
            break
        time.sleep(0.01)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            if process.poll() is None:
                process.kill()
    if process.poll() is None:
        try:
            process.wait(timeout=_PIPE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=_PIPE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                pass


def _create_case_exposure(hx_payload: dict, hz_payload: dict) -> tuple[Path, int, int]:
    trusted_temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    root = Path(
        tempfile.mkdtemp(
            prefix="autoqec-css-case-",
            dir=trusted_temp_root,
        )
    )
    parent_fd = _open_directory(root.parent)
    root_fd = _open_directory_at(parent_fd, root.name)
    try:
        for name, payload in (("hx.json", hx_payload), ("hz.json", hz_payload)):
            encoded = (json.dumps(payload, sort_keys=True) + "\n").encode()
            _atomic_bytes_at(root_fd, name, [encoded])
            os.chmod(name, 0o400, dir_fd=root_fd)
        os.fchmod(root_fd, 0o500)
    except Exception:
        os.fchmod(root_fd, 0o700)
        _remove_tree_at(parent_fd, root.name)
        os.close(root_fd)
        os.close(parent_fd)
        raise
    return root, root_fd, parent_fd


def _cleanup_case_exposure(root: Path, root_fd: int, parent_fd: int) -> None:
    try:
        os.fchmod(root_fd, 0o700)
        for name in os.listdir(root_fd):
            metadata = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                _remove_tree_at(root_fd, name)
            else:
                os.unlink(name, dir_fd=root_fd)
    finally:
        os.close(root_fd)
    try:
        os.rmdir(root.name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass
    finally:
        os.close(parent_fd)


def _capture_process(
    process: subprocess.Popen[bytes],
    *,
    hard_deadline: float,
    output_limit_bytes: int,
) -> tuple[int | None, bool, _BoundedCapture, _BoundedCapture]:
    captures = {
        process.stdout: _BoundedCapture(output_limit_bytes),
        process.stderr: _BoundedCapture(output_limit_bytes),
    }
    selector = selectors.DefaultSelector()
    for stream in captures:
        assert stream is not None
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)

    timed_out = False
    return_code: int | None = None
    drain_deadline: float | None = None
    group_terminated = False
    try:
        while True:
            polled = process.poll()
            now = time.monotonic()
            if drain_deadline is None:
                if polled is not None and now <= hard_deadline:
                    return_code = polled
                    _terminate_process_group(process)
                    group_terminated = True
                    drain_deadline = now + _PIPE_GRACE_SECONDS
                elif now >= hard_deadline:
                    timed_out = True
                    _terminate_process_group(process)
                    group_terminated = True
                    return_code = (
                        polled if polled is not None else process.poll()
                    )
                    drain_deadline = (
                        time.monotonic() + _PIPE_GRACE_SECONDS
                    )

            if not selector.get_map() and polled is not None:
                break

            active_deadline = (
                drain_deadline if drain_deadline is not None else hard_deadline
            )
            remaining = active_deadline - time.monotonic()
            if remaining <= 0:
                if drain_deadline is not None:
                    break
                timed_out = True
                _terminate_process_group(process)
                group_terminated = True
                return_code = process.poll()
                drain_deadline = time.monotonic() + _PIPE_GRACE_SECONDS
                continue
            if selector.get_map():
                events = selector.select(timeout=min(0.05, remaining))
            else:
                time.sleep(min(0.01, remaining))
                events = []
            for key, _ in events:
                stream = key.fileobj
                try:
                    chunk = os.read(stream.fileno(), 64 * 1024)
                except BlockingIOError:
                    continue
                if chunk:
                    captures[stream].add(chunk)
                else:
                    selector.unregister(stream)
                    stream.close()
        if process.poll() is None:
            timed_out = True
    finally:
        if not group_terminated:
            _terminate_process_group(process)
        for key in list(selector.get_map().values()):
            stream = key.fileobj
            selector.unregister(stream)
            stream.close()
        selector.close()
    return (
        return_code if return_code is not None else process.poll(),
        timed_out,
        captures[process.stdout],
        captures[process.stderr],
    )


def run_candidate_case(
    *,
    command: Iterable[str],
    command_builder: CandidateCommandBuilder | None = None,
    case: dict,
    seed: int,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output_limit_bytes: int = _OUTPUT_LIMIT_BYTES,
) -> dict:
    """Run one candidate process and verify its claimed upper-bound witness.

    Direct subprocess execution is a local/test transport only. The task-3
    container is the hard isolation boundary; this function exposes only one
    case's read-only matrices in preparation for that mount contract.
    """

    hx_path = Path(case["hx_path"])
    hz_path = Path(case["hz_path"])
    started = time.monotonic()
    base = {"case_id": case.get("case_id"), "seed": seed}
    candidate_command = list(command)
    if not candidate_command:
        return {
            **base,
            "status": "crash",
            "reason": "launch_failed",
            "runtime_seconds": time.monotonic() - started,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    try:
        hx_payload = _load_json_nofollow(
            hx_path,
            expected_identity=case.get("hx_identity"),
        )
        hz_payload = _load_json_nofollow(
            hz_path,
            expected_identity=case.get("hz_identity"),
        )
    except CssDistanceInfrastructureError:
        raise
    except (CssDistanceEvalError, ValueError, json.JSONDecodeError):
        return {
            **base,
            "status": "invalid",
            "reason": "invalid_matrix_input",
            "runtime_seconds": time.monotonic() - started,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    try:
        exposure_root, exposure_fd, exposure_parent_fd = _create_case_exposure(
            hx_payload,
            hz_payload,
        )
    except (OSError, CssDistanceEvalError) as error:
        raise CssDistanceInfrastructureError(
            "candidate case exposure creation failed"
        ) from error
    argv: list[str] | None = None
    try:
        try:
            argv = (
                command_builder(
                    exposure_dir=exposure_root,
                    seed=seed,
                    command=tuple(candidate_command),
                )
                if command_builder is not None
                else [
                    *candidate_command,
                    "--hx",
                    str(exposure_root / "hx.json"),
                    "--hz",
                    str(exposure_root / "hz.json"),
                    "--seed",
                    str(seed),
                ]
            )
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as error:
            if command_builder is not None:
                raise CssDistanceInfrastructureError(
                    "candidate container transport could not start"
                ) from error
            return {
                **base,
                "status": "crash",
                "reason": "launch_failed",
                "runtime_seconds": time.monotonic() - started,
                "stdout": "",
                "stderr": str(error)[:output_limit_bytes],
                "stdout_truncated": False,
                "stderr_truncated": len(str(error).encode()) > output_limit_bytes,
            }
        assert process.stdout is not None and process.stderr is not None
        return_code, timed_out, stdout_capture, stderr_capture = _capture_process(
            process,
            hard_deadline=started + timeout_seconds,
            output_limit_bytes=output_limit_bytes,
        )
        stdout_text = stdout_capture.text()
        stderr_text = stderr_capture.text()
        runtime = time.monotonic() - started
    finally:
        transport_cleanup_error: Exception | None = None
        try:
            cleanup = getattr(command_builder, "cleanup", None)
            if argv is not None and callable(cleanup):
                cleanup(argv)
        except Exception as error:
            transport_cleanup_error = error
        try:
            _cleanup_case_exposure(
                exposure_root,
                exposure_fd,
                exposure_parent_fd,
            )
        except (OSError, CssDistanceEvalError) as error:
            raise CssDistanceInfrastructureError(
                "candidate case exposure teardown failed"
            ) from error
        if transport_cleanup_error is not None:
            raise transport_cleanup_error
    base = {
        **base,
        "runtime_seconds": runtime,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "stdout_truncated": stdout_capture.truncated,
        "stderr_truncated": stderr_capture.truncated,
    }
    if timed_out:
        return {**base, "status": "timeout"}
    if command_builder is not None and return_code in {125, 126, 127}:
        raise CssDistanceInfrastructureError(
            f"candidate container transport exited with code {return_code}"
        )
    if return_code:
        return {**base, "status": "crash", "return_code": return_code}
    if stdout_capture.truncated:
        return {**base, "status": "invalid", "reason": "stdout_truncated"}
    try:
        candidate = json.loads(stdout_text)
    except (RecursionError, ValueError):
        return {**base, "status": "invalid", "reason": "invalid_json_contract"}
    if not isinstance(candidate, dict) or set(candidate) != {
        "status",
        "basis",
        "vector",
        "upper_bound",
    }:
        return {**base, "status": "invalid", "reason": "invalid_json_contract"}
    if candidate["status"] != "completed":
        return {**base, "status": "invalid", "reason": "invalid_status"}
    verification = verify_css_upper_bound_witness(
        hx_payload,
        hz_payload,
        candidate,
    )
    if verification["status"] != "pass":
        return {**base, "status": "invalid", "reason": verification["reason"]}
    if type(candidate["upper_bound"]) is not int or candidate["upper_bound"] != verification["weight"]:
        return {**base, "status": "invalid", "reason": "claimed_weight_mismatch"}
    return {
        **base,
        "status": "completed",
        "verified_weight": verification["weight"],
    }


def run_private_phase(
    *,
    command: Iterable[str],
    command_builder: CandidateCommandBuilder | None = None,
    work_root: Path,
    phase: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict]:
    """Run the complete private screening or finalist case/seed matrix."""

    if phase not in {"screening", "finalists"}:
        raise CssDistanceEvalError("invalid evaluation phase")
    candidate_command = tuple(command)
    holdout_root = work_root.absolute() / "private" / "holdout"
    holdout_fd = _open_directory(holdout_root)
    try:
        answers = _load_json_nofollow(holdout_root / "answers.json")
        private_cases = answers.get("cases")
        if not isinstance(private_cases, list) or len(private_cases) != len(_SELECTED):
            raise CssDistanceEvalError("invalid private holdout answers")
        seeds = (
            [answers.get("screening_seed")]
            if phase == "screening"
            else answers.get("finalist_seeds")
        )
        expected_seed_count = 1 if phase == "screening" else 3
        if (
            not isinstance(seeds, list)
            or len(seeds) != expected_seed_count
            or len(set(seeds)) != expected_seed_count
            or any(type(seed) is not int for seed in seeds)
        ):
            raise CssDistanceEvalError("invalid private phase seeds")
        public_cases = []
        expected_case_ids = {
            f"case-{number:04d}" for number in range(1, len(_SELECTED) + 1)
        }
        observed_case_ids = {
            private_case.get("case_id")
            for private_case in private_cases
            if isinstance(private_case, dict)
        }
        if observed_case_ids != expected_case_ids:
            raise CssDistanceEvalError("invalid private case")
        for private_case in private_cases:
            case_id = private_case["case_id"]
            case_root = holdout_root / case_id
            case_fd = _open_directory_at(holdout_fd, case_id)
            os.close(case_fd)
            public_cases.append(
                {
                    "case_id": case_id,
                    "hx_path": case_root / "hx.json",
                    "hz_path": case_root / "hz.json",
                }
            )
        candidate_options = {"command_builder": command_builder} if command_builder else {}
        results = [
            run_candidate_case(
                command=candidate_command,
                case=case,
                seed=seed,
                timeout_seconds=timeout_seconds,
                **candidate_options,
            )
            for seed in seeds
            for case in public_cases
        ]
        results_fd = _open_directory_at(holdout_fd, "results", create=True)
        try:
            encoded = (json.dumps(results, sort_keys=True, indent=2) + "\n").encode()
            _atomic_bytes_at(results_fd, f"{phase}.json", [encoded])
        finally:
            os.close(results_fd)
    finally:
        os.close(holdout_fd)
    return results


def score_candidate(
    results: list[dict],
    private_cases: list[dict],
    *,
    expected_seeds: Iterable[int],
) -> dict:
    """Return aggregate lexicographic score; input case answers stay private."""

    cases = {case["case_id"]: case for case in private_cases}
    seeds = tuple(expected_seeds)
    expected_pairs = {(case_id, seed) for case_id in cases for seed in seeds}
    result_pairs = [
        (result.get("case_id"), result.get("seed")) for result in results
    ]
    observed_pairs = set(result_pairs)
    malformed_pairs = (
        len(cases) != len(private_cases)
        or not seeds
        or len(set(seeds)) != len(seeds)
        or len(result_pairs) != len(observed_pairs)
        or observed_pairs != expected_pairs
        or any(
            result.get("status")
            not in {"completed", "timeout", "crash", "invalid"}
            for result in results
        )
    )
    aggregate = {
        "runs": len(results),
        "verified_witnesses": 0,
        "target_hits": 0,
        "timeouts": 0,
        "crashes": 0,
        "invalid_claims": 0,
        "weighted_target_hits": 0,
        "normalized_quality": 0.0,
        "runtime_seconds": sum(float(item.get("runtime_seconds", 0)) for item in results),
        "disqualified": malformed_pairs,
    }
    if malformed_pairs:
        aggregate["ranking_key"] = (0, 0, 0.0, -aggregate["runtime_seconds"])
        return aggregate
    quality_numerator = 0.0
    quality_denominator = sum(case["weight"] for case in private_cases) * len(seeds)
    for result in results:
        status = result.get("status")
        if status == "timeout":
            aggregate["timeouts"] += 1
        elif status == "crash":
            aggregate["crashes"] += 1
        elif status == "invalid":
            aggregate["invalid_claims"] += 1
        if status != "completed":
            continue
        case = cases.get(result.get("case_id"))
        if (
            case is None
            or type(result.get("verified_weight")) is not int
            or result["verified_weight"] <= 0
        ):
            aggregate["invalid_claims"] += 1
            continue
        aggregate["verified_witnesses"] += 1
        target = case["target"]
        hit = (
            result["verified_weight"] == target
            if case.get("bound_type", "exact") == "exact"
            else result["verified_weight"] <= target
        )
        if hit:
            aggregate["target_hits"] += 1
            aggregate["weighted_target_hits"] += case["weight"]
        quality_numerator += case["weight"] * min(1.0, target / result["verified_weight"])
    aggregate["normalized_quality"] = (
        quality_numerator / quality_denominator if quality_denominator else 0.0
    )
    aggregate["disqualified"] = aggregate["invalid_claims"] != 0
    aggregate["ranking_key"] = (
        int(not aggregate["disqualified"]),
        aggregate["weighted_target_hits"],
        aggregate["normalized_quality"],
        -aggregate["runtime_seconds"],
    )
    return aggregate


def sanitize_log_summary(summary: dict) -> dict:
    """Strip a private evaluation summary to the fixed LOG.md-safe fields."""

    sanitized = {}
    integer_fields = {
        "runs",
        "verified_witnesses",
        "target_hits",
        "timeouts",
        "crashes",
        "invalid_claims",
        "weighted_target_hits",
    }
    numeric_fields = {
        "normalized_quality",
        "runtime_seconds",
        "average_seconds",
        "median_seconds",
        "p95_seconds",
    }
    for key in _SAFE_LOG_FIELDS:
        if key not in summary:
            continue
        value = summary[key]
        valid = False
        if key in integer_fields:
            valid = type(value) is int and value >= 0
        elif key in numeric_fields:
            valid = (
                type(value) in {int, float}
                and math.isfinite(value)
                and value >= 0
            )
        elif key == "accepted":
            valid = type(value) is bool
        elif key == "decision":
            valid = isinstance(value, str) and value in _DECISIONS
        if not valid:
            raise CssDistanceEvalError(f"{key} must be a safe scalar")
        sanitized[key] = value
    return sanitized
