from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time

import pytest

import autoqec_search.css_distance_eval as css_eval
from autoqec_search.css_distance_container import CssDistanceInfrastructureError
from autoqec_search.css_distance_eval import (
    DEFAULT_TIMEOUT_SECONDS,
    CssDistanceEvalError,
    _load_json_nofollow,
    materialize_private_holdout,
    run_candidate_case,
    run_private_phase,
    sanitize_log_summary,
    score_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LADDER = REPO_ROOT / "benchmarks" / "distance_ladders" / "surface-toric-bb-kasai-tanner-v2.json"

HX = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[1, 1, 0, 0]],
}
HZ = {
    "format": "dense_binary_matrix",
    "n_rows": 1,
    "n_cols": 4,
    "data": [[0, 0, 1, 1]],
}
SELECTED_IDS = [
    "surface-rotated-d21",
    "toric-d17",
    "toric-d21",
    "bb72",
    "bb144",
    "bb288-same-shifts",
    "bb432-same-shifts",
    "apm-kasai-p96",
    "apm-kasai-p192",
    "quantum-tanner-toric-d8",
]


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n")


def _tiny_case(tmp_path: Path) -> dict:
    case = tmp_path / "case"
    case.mkdir()
    _write_json(case / "hx.json", HX)
    _write_json(case / "hz.json", HZ)
    return {"case_id": "case-0001", "hx_path": case / "hx.json", "hz_path": case / "hz.json"}


def _tiny_ladder(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    entries = []
    for source_id in SELECTED_IDS:
        case = source / source_id
        case.mkdir(parents=True)
        _write_json(case / "hx.json", HX)
        _write_json(case / "hz.json", HZ)
        entries.append(
            {
                "instance_id": source_id,
                "expected_distance": 2,
                "expected_bound_type": "exact",
            }
        )
    ladder_path = tmp_path / "ladder.json"
    _write_json(ladder_path, {"artifact_root": "source", "entries": entries})
    return ladder_path, source


def test_load_json_nofollow_rejects_digest_mismatch_before_parsing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "matrix.json"
    original = b'{"value":1}'
    rewritten = b'{"value":x}'
    assert len(original) == len(rewritten)
    path.write_bytes(original)
    original_digest = hashlib.sha256(original).hexdigest()
    with path.open("r+b") as stream:
        stream.write(rewritten)
        stream.truncate()
    metadata = os.stat(path, follow_symlinks=False)
    expected_identity = (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        original_digest,
    )

    with pytest.raises(CssDistanceInfrastructureError) as error:
        _load_json_nofollow(path, expected_identity=expected_identity)

    assert str(error.value) == "development matrix identity changed"
    assert str(path) not in str(error.value)
    assert original_digest not in str(error.value)


def test_load_json_nofollow_bounds_descriptor_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "oversized.json"
    path.write_bytes(b'{"payload":"' + b"x" * 64 + b'"}')
    monkeypatch.setattr(css_eval, "_MAX_JSON_INPUT_BYTES", 32, raising=False)

    with pytest.raises(CssDistanceEvalError, match="unsafe JSON input"):
        _load_json_nofollow(path)


def test_public_smoke_snapshot_supports_stable_repeated_evaluation(
    tmp_path: Path,
) -> None:
    loader = getattr(css_eval, "load_public_smoke_snapshot", None)
    case_input = getattr(css_eval, "public_smoke_case_input", None)
    assert callable(loader)
    assert callable(case_input)
    source_case = _tiny_case(tmp_path)
    case_root = Path(source_case["hx_path"]).parent

    snapshot = loader(case_root)
    first = case_input(snapshot)
    second = case_input(snapshot)
    script = (
        "import json; "
        "print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],"
        "'upper_bound':2}))"
    )
    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=second,
        seed=7,
        timeout_seconds=1,
    )

    assert first == second
    assert first["hx_identity"] == snapshot.hx.identity
    assert first["hz_identity"] == snapshot.hz.identity
    assert result["status"] == "completed"
    assert str(case_root) not in repr(snapshot)
    assert snapshot.hx.identity[7] not in repr(snapshot)


@pytest.mark.parametrize("drift", ["content", "symlink", "hardlink"])
def test_public_smoke_snapshot_rejects_input_drift(
    tmp_path: Path,
    drift: str,
) -> None:
    loader = getattr(css_eval, "load_public_smoke_snapshot", None)
    validator = getattr(css_eval, "validate_public_smoke_snapshot", None)
    assert callable(loader)
    assert callable(validator)
    source_case = _tiny_case(tmp_path)
    case_root = Path(source_case["hx_path"]).parent
    snapshot = loader(case_root)
    matrix = snapshot.hx.path
    replacement = tmp_path / "public-replacement.json"
    replacement.write_text(matrix.read_text(encoding="utf-8"), encoding="utf-8")
    if drift == "content":
        matrix.write_text(
            matrix.read_text(encoding="utf-8").replace("[1, 1, 0, 0]", "[1, 0, 0, 0]"),
            encoding="utf-8",
        )
    elif drift == "symlink":
        matrix.unlink()
        os.symlink(replacement, matrix)
    else:
        os.link(matrix, tmp_path / "additional-public-link.json")

    with pytest.raises(CssDistanceInfrastructureError) as error:
        validator(snapshot)

    assert str(error.value) == "public smoke snapshot changed"
    assert str(matrix) not in str(error.value)
    assert snapshot.hx.identity[7] not in str(error.value)


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink"])
def test_public_smoke_snapshot_loader_rejects_unsafe_filesystem_entries(
    tmp_path: Path,
    unsafe: str,
) -> None:
    loader = getattr(css_eval, "load_public_smoke_snapshot", None)
    assert callable(loader)
    source_case = _tiny_case(tmp_path)
    matrix = Path(source_case["hx_path"])
    target = tmp_path / "public-target.json"
    target.write_text(matrix.read_text(encoding="utf-8"), encoding="utf-8")
    if unsafe == "symlink":
        matrix.unlink()
        os.symlink(target, matrix)
    else:
        os.link(matrix, tmp_path / "public-hardlink.json")

    with pytest.raises(CssDistanceEvalError, match="unsafe public smoke input"):
        loader(matrix.parent)


def test_public_smoke_snapshot_loader_bounds_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = getattr(css_eval, "load_public_smoke_snapshot", None)
    assert callable(loader)
    source_case = _tiny_case(tmp_path)
    matrix = Path(source_case["hx_path"])
    matrix.write_bytes(b'{"payload":"' + b"x" * 64 + b'"}')
    monkeypatch.setattr(css_eval, "_MAX_JSON_INPUT_BYTES", 32)

    with pytest.raises(CssDistanceEvalError, match="unsafe public smoke input"):
        loader(matrix.parent)


def test_public_smoke_snapshot_rejects_post_open_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = getattr(css_eval, "load_public_smoke_snapshot", None)
    validator = getattr(css_eval, "validate_public_smoke_snapshot", None)
    assert callable(loader)
    assert callable(validator)
    source_case = _tiny_case(tmp_path)
    snapshot = loader(Path(source_case["hx_path"]).parent)
    replacement = tmp_path / "public-post-open.json"
    replacement.write_text(
        snapshot.hx.path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    real_read = css_eval.os.read
    swapped = False

    def swap_after_open(descriptor: int, size: int) -> bytes:
        nonlocal swapped
        metadata = os.fstat(descriptor)
        if not swapped and (
            metadata.st_dev,
            metadata.st_ino,
        ) == snapshot.hx.identity[:2]:
            os.replace(replacement, snapshot.hx.path)
            swapped = True
        return real_read(descriptor, size)

    monkeypatch.setattr(css_eval.os, "read", swap_after_open)

    with pytest.raises(CssDistanceInfrastructureError) as error:
        validator(snapshot)

    assert swapped is True
    assert str(error.value) == "public smoke snapshot changed"
    assert str(snapshot.hx.path) not in str(error.value)


def test_materializes_exact_selection_tiers_and_private_answers(tmp_path: Path) -> None:
    holdout = materialize_private_holdout(
        ladder_path=LADDER,
        work_root=tmp_path,
    )

    assert [case["case_id"] for case in holdout["cases"]] == [
        f"case-{number:04d}" for number in range(1, 11)
    ]
    assert [case["tier"] for case in holdout["cases"]] == [
        "regression",
        "discrimination",
        "discrimination",
        "regression",
        "regression",
        "discrimination",
        "discrimination",
        "stress",
        "stress",
        "regression",
    ]
    assert [case["weight"] for case in holdout["cases"]] == [1, 2, 2, 1, 1, 2, 2, 3, 3, 1]
    assert all(set(case) == {"case_id", "tier", "weight", "hx_path", "hz_path"} for case in holdout["cases"])

    private = tmp_path / "private" / "holdout"
    answer = json.loads((private / "answers.json").read_text())
    assert [item["source_id"] for item in answer["cases"]] == [
        "surface-rotated-d21",
        "toric-d17",
        "toric-d21",
        "bb72",
        "bb144",
        "bb288-same-shifts",
        "bb432-same-shifts",
        "apm-kasai-p96",
        "apm-kasai-p192",
        "quantum-tanner-toric-d8",
    ]
    assert answer["screening_seed"] != answer["finalist_seeds"][0]
    assert len(set(answer["finalist_seeds"])) == 3
    assert all((private / case["case_id"] / "hx.json").is_file() for case in holdout["cases"])
    assert DEFAULT_TIMEOUT_SECONDS == 300


def test_materialization_rejects_symlink_and_escaping_artifact_roots(tmp_path: Path) -> None:
    ladder_path, source = _tiny_ladder(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    matrix = source / SELECTED_IDS[0] / "hx.json"
    matrix.unlink()
    os.symlink(outside / "hx.json", matrix)

    with pytest.raises(CssDistanceEvalError, match="unsafe"):
        materialize_private_holdout(ladder_path=ladder_path, work_root=tmp_path / "work")

    payload = json.loads(ladder_path.read_text())
    payload["artifact_root"] = "../source"
    _write_json(ladder_path, payload)
    with pytest.raises(CssDistanceEvalError, match="unsafe"):
        materialize_private_holdout(ladder_path=ladder_path, work_root=tmp_path / "work")


def test_source_swap_to_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ladder_path, source = _tiny_ladder(tmp_path)
    matrix = source / SELECTED_IDS[0] / "hx.json"
    outside = tmp_path / "outside.json"
    _write_json(outside, HX)
    real_open = os.open
    swapped = False

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == "hx.json" and dir_fd is not None and not swapped:
            swapped = True
            matrix.unlink()
            os.symlink(outside, matrix)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swapping_open)

    with pytest.raises(CssDistanceEvalError, match="unsafe"):
        materialize_private_holdout(ladder_path=ladder_path, work_root=tmp_path / "work")


def test_completed_candidate_is_independently_verified(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    script = (
        "import json,sys; "
        "print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],"
        "'upper_bound':2}))"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "completed"
    assert result["verified_weight"] == 2


def test_deeply_nested_candidate_json_is_an_invalid_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _tiny_case(tmp_path)
    script = "import sys; sys.stdout.write('[' * 2000 + '0' + ']' * 2000)"
    real_loads = json.loads

    def depth_limited_loads(payload: str, *args: object, **kwargs: object) -> object:
        if payload.startswith("[[["):
            raise RecursionError("synthetic decoder nesting limit")
        return real_loads(payload, *args, **kwargs)

    monkeypatch.setattr(css_eval.json, "loads", depth_limited_loads)

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "invalid"
    assert result["reason"] == "invalid_json_contract"
    assert "synthetic decoder nesting limit" not in str(result)


def test_oversized_integer_candidate_json_is_an_invalid_contract(
    tmp_path: Path,
) -> None:
    case = _tiny_case(tmp_path)
    script = (
        "import sys; "
        "sys.stdout.write('{\"status\":\"completed\",\"basis\":\"x\","
        "\"vector\":[0,0,1,1],\"upper_bound\":' + '9' * 5000 + '}')"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "invalid"
    assert result["reason"] == "invalid_json_contract"
    assert "integer string conversion" not in str(result)


def test_malformed_candidate_json_is_an_invalid_contract(tmp_path: Path) -> None:
    result = run_candidate_case(
        command=[sys.executable, "-c", "import sys; sys.stdout.write('{')"],
        case=_tiny_case(tmp_path),
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "invalid"
    assert result["reason"] == "invalid_json_contract"


def test_valid_candidate_json_remains_accepted(tmp_path: Path) -> None:
    script = (
        "import sys; "
        "sys.stdout.write('{\"status\":\"completed\",\"basis\":\"x\","
        "\"vector\":[0,0,1,1],\"upper_bound\":2}')"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=_tiny_case(tmp_path),
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "completed"
    assert result["verified_weight"] == 2


def test_candidate_sees_only_ephemeral_read_only_matrices(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    script = (
        "import json,pathlib,stat,sys; "
        "hx=pathlib.Path(sys.argv[sys.argv.index('--hx')+1]); "
        "hz=pathlib.Path(sys.argv[sys.argv.index('--hz')+1]); "
        "sys.stderr.write(json.dumps({"
        "'siblings':sorted(p.name for p in hx.parent.iterdir()),"
        "'hx_mode':stat.S_IMODE(hx.stat().st_mode),"
        "'hz_mode':stat.S_IMODE(hz.stat().st_mode),"
        "'hx_path':str(hx)})); "
        "print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],"
        "'upper_bound':2}))"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=1,
    )

    exposure = json.loads(result["stderr"])
    assert result["status"] == "completed"
    assert exposure["siblings"] == ["hx.json", "hz.json"]
    assert exposure["hx_mode"] == 0o400
    assert exposure["hz_mode"] == 0o400
    assert "private/holdout" not in exposure["hx_path"]
    assert not Path(exposure["hx_path"]).parent.exists()


def test_candidate_matrix_tampering_cannot_change_verification(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    script = (
        "import json,os,pathlib,sys; "
        "hz=pathlib.Path(sys.argv[sys.argv.index('--hz')+1]); "
        "os.chmod(hz,0o600); "
        "hz.write_text(json.dumps({'format':'dense_binary_matrix','n_rows':1,"
        "'n_cols':4,'data':[[0,0,1,0]]})); "
        "print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],"
        "'upper_bound':2}))"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "completed"
    assert result["verified_weight"] == 2
    assert json.loads(Path(case["hz_path"]).read_text()) == HZ


def test_claimed_weight_mismatch_is_invalid(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    script = (
        "import json; "
        "print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],"
        "'upper_bound':3}))"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "invalid"
    assert result["reason"] == "claimed_weight_mismatch"


def test_invalid_witness_is_not_accepted_as_completed(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    script = (
        "import json; "
        "print(json.dumps({'status':'completed','basis':'x','vector':[1,0,1,0],"
        "'upper_bound':2}))"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "invalid"
    assert result["reason"] == "not_in_kernel"


@pytest.mark.parametrize(
    ("observed_at", "return_code", "expected_timeout"),
    [
        (9.999, 0, False),
        (10.0, 0, False),
        (10.001, 0, True),
        (10.001, None, True),
    ],
    ids=(
        "completed-before-deadline",
        "completed-at-deadline",
        "completed-after-deadline",
        "running-after-deadline",
    ),
)
def test_capture_process_applies_deadline_before_accepting_late_completion(
    monkeypatch: pytest.MonkeyPatch,
    observed_at: float,
    return_code: int | None,
    expected_timeout: bool,
) -> None:
    class ObservedProcess:
        def __init__(self, initial_return_code: int | None) -> None:
            stdout_read, stdout_write = os.pipe()
            stderr_read, stderr_write = os.pipe()
            os.close(stdout_write)
            os.close(stderr_write)
            self.stdout = os.fdopen(stdout_read, "rb", buffering=0)
            self.stderr = os.fdopen(stderr_read, "rb", buffering=0)
            self.return_code = initial_return_code

        def poll(self) -> int | None:
            return self.return_code

    process = ObservedProcess(return_code)
    terminated: list[ObservedProcess] = []

    def terminate(candidate: ObservedProcess) -> None:
        terminated.append(candidate)
        if candidate.return_code is None:
            candidate.return_code = -15

    monkeypatch.setattr(css_eval.time, "monotonic", lambda: observed_at)
    monkeypatch.setattr(css_eval, "_terminate_process_group", terminate)

    captured_return_code, timed_out, stdout, stderr = (
        css_eval._capture_process(
            process,  # type: ignore[arg-type]
            hard_deadline=10.0,
            output_limit_bytes=64,
        )
    )

    assert timed_out is expected_timeout
    assert captured_return_code == (return_code if return_code is not None else -15)
    assert stdout.text() == ""
    assert stderr.text() == ""
    assert terminated == [process]
    assert process.stdout.closed
    assert process.stderr.closed


@pytest.mark.parametrize(
    "first_observation",
    [9.999, 10.0],
    ids=("pipes-drain-before-late-completion", "running-at-deadline"),
)
def test_capture_process_classifies_completion_seen_outside_loop_body(
    monkeypatch: pytest.MonkeyPatch,
    first_observation: float,
) -> None:
    clock = {"now": first_observation}

    class LateProcess:
        def __init__(self) -> None:
            stdout_read, stdout_write = os.pipe()
            stderr_read, stderr_write = os.pipe()
            os.close(stdout_write)
            os.close(stderr_write)
            self.stdout = os.fdopen(stdout_read, "rb", buffering=0)
            self.stderr = os.fdopen(stderr_read, "rb", buffering=0)
            self.poll_calls = 0

        def poll(self) -> int | None:
            self.poll_calls += 1
            if self.poll_calls == 1:
                return None
            clock["now"] = 10.001
            return 0

    process = LateProcess()
    terminated: list[LateProcess] = []
    monkeypatch.setattr(
        css_eval.time,
        "monotonic",
        lambda: clock["now"],
    )
    monkeypatch.setattr(
        css_eval,
        "_terminate_process_group",
        lambda candidate: terminated.append(candidate),
    )

    return_code, timed_out, _, _ = css_eval._capture_process(
        process,  # type: ignore[arg-type]
        hard_deadline=10.0,
        output_limit_bytes=64,
    )

    assert return_code == 0
    assert timed_out is True
    assert terminated == [process]
    assert process.stdout.closed
    assert process.stderr.closed


def test_candidate_crash_and_timeout_kill_its_process_group(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    crash = run_candidate_case(
        command=[sys.executable, "-c", "raise SystemExit(2)"],
        case=case,
        seed=7,
        timeout_seconds=1,
    )
    pid_path = tmp_path / "child.pid"
    sleeper = (
        "import pathlib,subprocess,sys,time; "
        f"pathlib.Path({str(pid_path)!r}).write_text(str(subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']).pid)); "
        "time.sleep(30)"
    )
    timeout = run_candidate_case(
        command=[sys.executable, "-c", sleeper],
        case=case,
        seed=7,
        timeout_seconds=1,
    )

    assert crash["status"] == "crash"
    assert timeout["status"] == "timeout"
    child_pid = int(pid_path.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def test_timeout_invokes_transport_cleanup(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)

    class CleanupTransport:
        def __init__(self) -> None:
            self.cleaned: list[list[str]] = []

        def __call__(self, *, exposure_dir: Path, seed: int, command: tuple[str, ...]) -> list[str]:
            return [sys.executable, "-c", "import time; time.sleep(30)"]

        def cleanup(self, command: list[str]) -> None:
            self.cleaned.append(command)

    transport = CleanupTransport()
    result = run_candidate_case(
        command=["candidate-entrypoint"],
        command_builder=transport,
        case=case,
        seed=7,
        timeout_seconds=0.05,
    )

    assert result["status"] == "timeout"
    assert transport.cleaned == [
        [sys.executable, "-c", "import time; time.sleep(30)"]
    ]


def test_transport_cleanup_failure_still_removes_case_exposure(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    captured: dict[str, Path] = {}

    class FailingCleanupTransport:
        def __call__(
            self,
            *,
            exposure_dir: Path,
            seed: int,
            command: tuple[str, ...],
        ) -> list[str]:
            captured["exposure_dir"] = exposure_dir
            return [
                sys.executable,
                "-c",
                "import json; print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],'upper_bound':2}))",
            ]

        def cleanup(self, command: list[str]) -> None:
            raise RuntimeError("simulated transport cleanup failure")

    with pytest.raises(RuntimeError, match="simulated transport cleanup failure"):
        run_candidate_case(
            command=["candidate-entrypoint"],
            command_builder=FailingCleanupTransport(),
            case=case,
            seed=7,
            timeout_seconds=1,
        )

    assert not captured["exposure_dir"].exists()


def test_case_exposure_creation_oserror_is_infrastructure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _tiny_case(tmp_path)
    builder_called = False

    class NeverCalledTransport:
        def __call__(
            self,
            *,
            exposure_dir: Path,
            seed: int,
            command: tuple[str, ...],
        ) -> list[str]:
            nonlocal builder_called
            builder_called = True
            return [sys.executable, "-c", "raise AssertionError"]

    monkeypatch.setattr(
        "autoqec_search.css_distance_eval._create_case_exposure",
        lambda hx_payload, hz_payload: (_ for _ in ()).throw(
            OSError("temporary filesystem unavailable")
        ),
    )

    with pytest.raises(CssDistanceInfrastructureError, match="exposure.*creation"):
        run_candidate_case(
            command=["candidate-entrypoint"],
            command_builder=NeverCalledTransport(),
            case=case,
            seed=7,
            timeout_seconds=1,
        )

    assert builder_called is False


def test_case_exposure_teardown_oserror_is_infrastructure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autoqec_search.css_distance_eval as css_eval

    case = _tiny_case(tmp_path)
    original_cleanup = css_eval._cleanup_case_exposure

    class CompletingTransport:
        def __call__(
            self,
            *,
            exposure_dir: Path,
            seed: int,
            command: tuple[str, ...],
        ) -> list[str]:
            return [
                sys.executable,
                "-c",
                "import json; print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],'upper_bound':2}))",
            ]

        def cleanup(self, command: list[str]) -> None:
            pass

    def fail_after_real_cleanup(root: Path, root_fd: int, parent_fd: int) -> None:
        original_cleanup(root, root_fd, parent_fd)
        raise OSError("temporary filesystem teardown failed")

    monkeypatch.setattr(css_eval, "_cleanup_case_exposure", fail_after_real_cleanup)

    with pytest.raises(CssDistanceInfrastructureError, match="exposure.*teardown"):
        run_candidate_case(
            command=["candidate-entrypoint"],
            command_builder=CompletingTransport(),
            case=case,
            seed=7,
            timeout_seconds=1,
        )


@pytest.mark.parametrize("failure", ["builder", "popen"])
def test_container_transport_setup_oserror_is_infrastructure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    case = _tiny_case(tmp_path)
    captured: dict[str, Path] = {}

    class FailingTransport:
        def __call__(
            self,
            *,
            exposure_dir: Path,
            seed: int,
            command: tuple[str, ...],
        ) -> list[str]:
            captured["exposure_dir"] = exposure_dir
            if failure == "builder":
                raise OSError("builder filesystem failure")
            return ["docker", "run"]

        def cleanup(self, command: list[str]) -> None:
            pass

    if failure == "popen":
        monkeypatch.setattr(
            "autoqec_search.css_distance_eval.subprocess.Popen",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                OSError("docker executable unavailable")
            ),
        )

    with pytest.raises(CssDistanceInfrastructureError):
        run_candidate_case(
            command=["candidate-entrypoint"],
            command_builder=FailingTransport(),
            case=case,
            seed=7,
            timeout_seconds=1,
        )

    assert not captured["exposure_dir"].exists()


@pytest.mark.parametrize("return_code", [125, 126, 127])
def test_docker_transport_exit_codes_are_infrastructure(
    tmp_path: Path,
    return_code: int,
) -> None:
    case = _tiny_case(tmp_path)

    class DockerExitTransport:
        def __call__(
            self,
            *,
            exposure_dir: Path,
            seed: int,
            command: tuple[str, ...],
        ) -> list[str]:
            return [sys.executable, "-c", f"raise SystemExit({return_code})"]

        def cleanup(self, command: list[str]) -> None:
            pass

    with pytest.raises(CssDistanceInfrastructureError, match=str(return_code)):
        run_candidate_case(
            command=["candidate-entrypoint"],
            command_builder=DockerExitTransport(),
            case=case,
            seed=7,
            timeout_seconds=1,
        )


def test_phase_orchestration_runs_exact_screening_and_finalist_pairs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    materialize_private_holdout(ladder_path=LADDER, work_root=tmp_path)
    calls: list[tuple[str, int]] = []

    def fake_run_candidate_case(*, command, case, seed, timeout_seconds):
        calls.append((case["case_id"], seed))
        return {
            "case_id": case["case_id"],
            "seed": seed,
            "status": "timeout",
            "runtime_seconds": 0.01,
        }

    monkeypatch.setattr(
        "autoqec_search.css_distance_eval.run_candidate_case",
        fake_run_candidate_case,
    )

    screening = run_private_phase(
        command=["candidate"],
        work_root=tmp_path,
        phase="screening",
        timeout_seconds=0.1,
    )
    assert len(screening) == 10
    assert len({seed for _, seed in calls}) == 1
    calls.clear()
    finalists = run_private_phase(
        command=["candidate"],
        work_root=tmp_path,
        phase="finalists",
        timeout_seconds=0.1,
    )
    assert len(finalists) == 30
    assert len({seed for _, seed in calls}) == 3
    assert len(set(calls)) == 30
    assert (tmp_path / "private" / "holdout" / "results" / "screening.json").is_file()
    assert (tmp_path / "private" / "holdout" / "results" / "finalists.json").is_file()


def test_phase_materializes_one_shot_command_only_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    materialize_private_holdout(ladder_path=LADDER, work_root=tmp_path)

    class OneShotCommand:
        def __init__(self) -> None:
            self.used = False

        def __iter__(self):
            if self.used:
                raise AssertionError("command iterable consumed more than once")
            self.used = True
            return iter(["candidate"])

    seen_commands = []

    def fake_run_candidate_case(*, command, case, seed, timeout_seconds):
        seen_commands.append(tuple(command))
        return {
            "case_id": case["case_id"],
            "seed": seed,
            "status": "timeout",
            "runtime_seconds": 0.01,
        }

    monkeypatch.setattr(
        "autoqec_search.css_distance_eval.run_candidate_case",
        fake_run_candidate_case,
    )

    run_private_phase(
        command=OneShotCommand(),
        work_root=tmp_path,
        phase="screening",
        timeout_seconds=0.1,
    )

    assert seen_commands == [("candidate",)] * 10


def _score_cases() -> list[dict]:
    return [
        {
            "case_id": "case-0001",
            "tier": "regression",
            "weight": 1,
            "target": 4,
            "bound_type": "exact",
        },
        {
            "case_id": "case-0002",
            "tier": "stress",
            "weight": 3,
            "target": 8,
            "bound_type": "exact",
        },
    ]


def _score_results(seed: int = 11) -> list[dict]:
    return [
        {
            "case_id": "case-0001",
            "seed": seed,
            "status": "completed",
            "verified_weight": 4,
            "runtime_seconds": 2,
        },
        {
            "case_id": "case-0002",
            "seed": seed,
            "status": "completed",
            "verified_weight": 8,
            "runtime_seconds": 2,
        },
    ]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown"])
def test_scoring_disqualifies_incomplete_or_repeated_phase_pairs(mutation: str) -> None:
    results = _score_results()
    if mutation == "missing":
        results.pop()
    elif mutation == "duplicate":
        results.append(dict(results[0]))
    else:
        results[-1]["case_id"] = "case-9999"

    score = score_candidate(results, _score_cases(), expected_seeds=[11])

    assert score["disqualified"] is True
    assert score["ranking_key"][0] == 0
    assert score["weighted_target_hits"] == 0


def test_scoring_prioritizes_validity_then_hits_quality_and_runtime() -> None:
    cases = _score_cases()
    valid_fast = _score_results()
    invalid_better = [
        {"case_id": "case-0001", "seed": 11, "status": "invalid", "runtime_seconds": 0.1},
        {
            "case_id": "case-0002",
            "seed": 11,
            "status": "completed",
            "verified_weight": 1,
            "runtime_seconds": 0.1,
        },
    ]
    valid_lower_quality = [
        {
            "case_id": "case-0001",
            "seed": 11,
            "status": "completed",
            "verified_weight": 4,
            "runtime_seconds": 1,
        },
        {"case_id": "case-0002", "seed": 11, "status": "timeout", "runtime_seconds": 1},
    ]

    best = score_candidate(valid_fast, cases, expected_seeds=[11])
    invalid = score_candidate(invalid_better, cases, expected_seeds=[11])
    lower = score_candidate(valid_lower_quality, cases, expected_seeds=[11])
    assert best["ranking_key"] > invalid["ranking_key"]
    assert best["ranking_key"] > lower["ranking_key"]
    assert best["weighted_target_hits"] == 4
    assert best["normalized_quality"] == 1.0
    assert lower["normalized_quality"] == 0.25


def test_scoring_disqualifies_unknown_result_status() -> None:
    results = _score_results()
    results[0]["status"] = "secret-case-0001"

    score = score_candidate(results, _score_cases(), expected_seeds=[11])

    assert score["disqualified"] is True
    assert score["ranking_key"][0] == 0
    assert score["weighted_target_hits"] == 0


def test_oversized_streams_are_drained_and_truncated(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    script = (
        "import json,sys; "
        "sys.stderr.write('e' * 200000); "
        "print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],"
        "'upper_bound':2}))"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=2,
        output_limit_bytes=1024,
    )

    assert result["status"] == "completed"
    assert len(result["stderr"].encode()) <= 1024
    assert result["stderr_truncated"] is True
    assert result["stdout_truncated"] is False


def test_truncated_stdout_cannot_pass_the_single_object_contract(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    script = (
        "import json,sys; "
        "sys.stdout.write(json.dumps({'status':'completed','basis':'x',"
        "'vector':[0,0,1,1],'upper_bound':2}) + ' ' * 200000)"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=2,
        output_limit_bytes=1024,
    )

    assert result["stdout_truncated"] is True
    assert result["status"] == "invalid"
    assert result["reason"] == "stdout_truncated"


@pytest.mark.parametrize("command", [[], ["/definitely/missing/candidate"]])
def test_launch_failure_is_a_typed_crash(tmp_path: Path, command: list[str]) -> None:
    result = run_candidate_case(
        command=command,
        case=_tiny_case(tmp_path),
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "crash"
    assert result["reason"] == "launch_failed"


def test_normal_parent_completion_kills_orphaned_descendant(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    pid_path = tmp_path / "orphan.pid"
    script = (
        "import json,pathlib,subprocess,sys; "
        f"pathlib.Path({str(pid_path)!r}).write_text(str(subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']).pid)); "
        "print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],"
        "'upper_bound':2}))"
    )

    result = run_candidate_case(
        command=[sys.executable, "-c", script],
        case=case,
        seed=7,
        timeout_seconds=2,
    )

    assert result["status"] == "completed"
    child_pid = int(pid_path.read_text())
    for _ in range(50):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.01)
    else:
        pytest.fail("candidate descendant survived normal parent completion")


def test_escaped_session_child_cannot_hold_output_drain_open(tmp_path: Path) -> None:
    case = _tiny_case(tmp_path)
    pid_path = tmp_path / "escaped.pid"
    script = (
        "import json,pathlib,subprocess,sys; "
        f"p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(3)'],start_new_session=True); "
        f"pathlib.Path({str(pid_path)!r}).write_text(str(p.pid)); "
        "print(json.dumps({'status':'completed','basis':'x','vector':[0,0,1,1],"
        "'upper_bound':2}))"
    )
    started = time.monotonic()
    child_pid = None
    try:
        result = run_candidate_case(
            command=[sys.executable, "-c", script],
            case=case,
            seed=7,
            timeout_seconds=1,
        )
        child_pid = int(pid_path.read_text())
        assert result["status"] == "completed"
        assert time.monotonic() - started < 1
    finally:
        if child_pid is not None:
            try:
                os.kill(child_pid, 9)
            except ProcessLookupError:
                pass


def test_materialization_rejects_symlinked_destination_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    os.symlink(outside, work / "private")

    with pytest.raises(CssDistanceEvalError, match="unsafe"):
        materialize_private_holdout(ladder_path=LADDER, work_root=work)


def test_descriptor_walk_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    ladder_path, _ = _tiny_ladder(real)
    linked = tmp_path / "linked"
    os.symlink(real, linked)

    with pytest.raises(CssDistanceEvalError, match="unsafe"):
        materialize_private_holdout(
            ladder_path=linked / ladder_path.name,
            work_root=tmp_path / "work",
        )


def test_sanitizer_never_leaks_private_holdout_data() -> None:
    unsafe = {
        "runs": 4,
        "verified_witnesses": 2,
        "target_hits": 1,
        "timeouts": 1,
        "crashes": 0,
        "invalid_claims": 0,
        "weighted_target_hits": 3,
        "normalized_quality": 0.5,
        "runtime_seconds": 1.2,
        "average_seconds": 0.3,
        "median_seconds": 0.4,
        "p95_seconds": 0.9,
        "accepted": True,
        "decision": "accepted",
        "case_id": "case-0001",
        "source_id": "bb72",
        "n": 72,
        "target": 6,
        "vector": [1, 0],
        "seed": 123,
    }

    assert sanitize_log_summary(unsafe) == {
        key: unsafe[key]
        for key in (
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
        )
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runs", {"source_id": "bb72"}),
        ("runtime_seconds", [1.2, {"seed": 123}]),
        ("average_seconds", float("nan")),
        ("median_seconds", -0.1),
        ("p95_seconds", float("inf")),
        ("accepted", {"case_id": "case-0001"}),
        ("decision", ["advance", {"target": 6}]),
    ],
)
def test_sanitizer_rejects_nested_values(field: str, value: object) -> None:
    with pytest.raises(CssDistanceEvalError, match="scalar"):
        sanitize_log_summary({field: value})


@pytest.mark.parametrize("decision", ["bb72", "case-0001", "advance", "accepted:seed=7"])
def test_sanitizer_rejects_decision_leakage(decision: str) -> None:
    with pytest.raises(CssDistanceEvalError, match="decision"):
        sanitize_log_summary({"decision": decision})
