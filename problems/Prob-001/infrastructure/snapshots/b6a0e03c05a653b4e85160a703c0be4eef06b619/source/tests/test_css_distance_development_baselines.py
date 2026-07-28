from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

import pytest

import autoqec_search.css_distance_development_baselines as baselines
from autoqec_search.css_distance_container import (
    CssDistanceInfrastructureError,
    DockerImage,
)
from autoqec_search.css_distance_development_baselines import (
    DevelopmentCase,
    _open_directory_at_nofollow,
    _prepare_candidate_runtime,
    _run_case_jobs,
    _run_container_method,
    aggregate_method_results,
    load_development_cases,
    _run_random_window_case,
    write_baseline_aggregate,
)
from autoqec_search.css_distance_eval import run_candidate_case


def _matrix_pair() -> tuple[dict, dict]:
    return (
        {"format": "sparse_rows", "num_cols": 4, "rows": [[0, 1]]},
        {"format": "sparse_rows", "num_cols": 4, "rows": [[2, 3]]},
    )


def _write_private_split(tmp_path: Path, *, split: str, count: int = 24) -> Path:
    work_root = tmp_path / "private-work-root"
    private_root = work_root / "private" / "css-distance-paper-suite" / split
    private_root.mkdir(parents=True)
    hx, hz = _matrix_pair()
    cases = []
    for index in range(count):
        case_id = f"{split}-{index:03d}"
        case_root = private_root / case_id
        case_root.mkdir()
        (case_root / "hx.json").write_text(json.dumps(hx), encoding="utf-8")
        (case_root / "hz.json").write_text(json.dumps(hz), encoding="utf-8")
        cases.append(
            {
                "case_id": case_id,
                "source_case_id": f"source-{index:03d}",
                "reference": {"bound_type": "exact", "value": 1},
                "hx_path": f"{case_id}/hx.json",
                "hz_path": f"{case_id}/hz.json",
            }
        )
    (private_root / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "split": split, "cases": cases}),
        encoding="utf-8",
    )
    return work_root


def _assert_development_consumer_rejects(
    *,
    case: DevelopmentCase,
    consumer: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autoqec_search.css_distance_development_baselines as baselines
    import autoqec_search.css_distance_eval as evaluation

    launched = False

    def reject_launch(*args: object, **kwargs: object) -> dict:
        nonlocal launched
        launched = True
        raise AssertionError("development consumer must not launch")

    if consumer == "container":
        monkeypatch.setattr(evaluation.subprocess, "Popen", reject_launch)
        candidate = tmp_path / "candidate"
        candidate.mkdir()
        (candidate / "candidate.py").write_text("print('{}')\n", encoding="utf-8")

        def consume() -> object:
            return _run_container_method(
                cases=[case],
                seeds=[7],
                docker_image=DockerImage(
                    "sha256:" + "2" * 64,
                    "synthetic-baseline",
                    role="evaluator",
                ),
                candidate_worktree=candidate,
                output_root=tmp_path / "output",
                timeout_seconds=1,
                max_parallel=1,
            )

    elif consumer == "random-window":
        monkeypatch.setattr(
            baselines,
            "run_qec_code_random_window_upper_bound_css_witness",
            reject_launch,
        )

        def consume() -> object:
            return _run_random_window_case(
                case=case,
                seed=123,
                qec_code_bin=Path("qec-code"),
                timeout_seconds=300,
                iterations=5000,
                restarts=8,
            )

    else:
        raise AssertionError(f"unknown synthetic consumer: {consumer}")

    with pytest.raises(CssDistanceInfrastructureError) as error:
        consume()

    assert str(error.value) == "development matrix identity changed"
    assert str(case.hx_path) not in str(error.value)
    assert str(case.hx_identity) not in str(error.value)
    assert launched is False


def test_load_development_cases_accepts_only_24_case_development_split(
    tmp_path: Path,
) -> None:
    work_root = _write_private_split(tmp_path, split="development")
    cases = load_development_cases(work_root)

    assert len(cases) == 24
    assert cases[0].target == 1
    assert cases[0].bound_type == "exact"
    assert cases[0].weight == 1


def test_load_development_cases_pins_strong_matrix_identity(tmp_path: Path) -> None:
    work_root = _write_private_split(tmp_path, split="development")
    case = load_development_cases(work_root)[0]
    metadata = os.stat(case.hx_path, follow_symlinks=False)
    expected_metadata = (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )

    assert case.hx_identity is not None
    assert case.hx_identity[:7] == expected_metadata
    assert case.hx_identity[7] == hashlib.sha256(case.hx_path.read_bytes()).hexdigest()


def test_development_snapshot_is_immutable_and_pins_suite_contract(
    tmp_path: Path,
) -> None:
    loader = getattr(baselines, "load_development_snapshot", None)
    validator = getattr(baselines, "validate_development_snapshot", None)
    assert callable(loader)
    assert callable(validator)
    work_root = _write_private_split(tmp_path, split="development")

    snapshot = loader(work_root)
    manifest_path = (
        work_root
        / "private"
        / "css-distance-paper-suite"
        / "development"
        / "manifest.json"
    )

    assert type(snapshot.cases) is tuple
    assert len(snapshot.cases) == 24
    assert snapshot.cases[0].target == 1
    assert snapshot.manifest.identity[7] == hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()
    assert len(snapshot.suite_identity) == 6
    assert len(snapshot.split_identity) == 6
    validator(snapshot)
    with pytest.raises(FrozenInstanceError):
        snapshot.cases = ()
    assert str(work_root) not in repr(snapshot)
    assert "development-000" not in repr(snapshot)


@pytest.mark.parametrize("drift", ["target", "membership"])
def test_development_snapshot_rejects_manifest_contract_drift(
    tmp_path: Path,
    drift: str,
) -> None:
    loader = getattr(baselines, "load_development_snapshot", None)
    validator = getattr(baselines, "validate_development_snapshot", None)
    assert callable(loader)
    assert callable(validator)
    work_root = _write_private_split(tmp_path, split="development")
    snapshot = loader(work_root)
    manifest_path = snapshot.manifest.path
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if drift == "target":
        payload["cases"][0]["reference"]["value"] += 1
    else:
        payload["cases"][0]["case_id"] = "development-999"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CssDistanceInfrastructureError) as error:
        validator(snapshot)

    assert str(error.value) == "development suite snapshot changed"
    assert str(manifest_path) not in str(error.value)
    assert "development-000" not in str(error.value)


def test_development_snapshot_rejects_matrix_drift(tmp_path: Path) -> None:
    loader = getattr(baselines, "load_development_snapshot", None)
    validator = getattr(baselines, "validate_development_snapshot", None)
    assert callable(loader)
    assert callable(validator)
    work_root = _write_private_split(tmp_path, split="development")
    snapshot = loader(work_root)
    matrix = snapshot.cases[0].hx_path
    before = os.stat(matrix, follow_symlinks=False)
    original = matrix.read_bytes()
    rewritten = original.replace(b"[[0, 1]]", b"[[0, 2]]", 1)
    assert len(rewritten) == len(original)
    with matrix.open("r+b") as stream:
        stream.write(rewritten)
        stream.truncate()
    os.utime(
        matrix,
        ns=(before.st_atime_ns, before.st_mtime_ns),
        follow_symlinks=False,
    )

    with pytest.raises(CssDistanceInfrastructureError) as error:
        validator(snapshot)

    assert str(error.value) == "development suite snapshot changed"
    assert str(matrix) not in str(error.value)
    assert "development-000" not in str(error.value)


def test_load_development_cases_rejects_final_split(tmp_path: Path) -> None:
    work_root = _write_private_split(tmp_path, split="final", count=12)

    with pytest.raises(ValueError, match="development"):
        load_development_cases(work_root)


@pytest.mark.parametrize(
    "unsafe_entry",
    [
        "manifest-symlink",
        "development-symlink",
        "intermediate-symlink",
        "matrix-symlink",
        "matrix-hardlink",
    ],
)
def test_load_development_cases_rejects_unsafe_filesystem_entries(
    tmp_path: Path,
    unsafe_entry: str,
) -> None:
    work_root = _write_private_split(tmp_path, split="development")
    suite_root = work_root / "private" / "css-distance-paper-suite"
    development = suite_root / "development"
    case_root = development / "development-000"

    if unsafe_entry == "manifest-symlink":
        manifest = development / "manifest.json"
        target = tmp_path / "manifest-target.json"
        manifest.rename(target)
        os.symlink(target, manifest)
    elif unsafe_entry == "development-symlink":
        target = suite_root / "development-real"
        development.rename(target)
        os.symlink(target, development, target_is_directory=True)
    elif unsafe_entry == "intermediate-symlink":
        target = development / "development-000-real"
        case_root.rename(target)
        os.symlink(target, case_root, target_is_directory=True)
    elif unsafe_entry == "matrix-symlink":
        matrix = case_root / "hx.json"
        target = tmp_path / "hx-target.json"
        matrix.rename(target)
        os.symlink(target, matrix)
    else:
        os.link(case_root / "hx.json", tmp_path / "hx-hardlink.json")

    with pytest.raises(ValueError, match="development|unsafe|matrix|manifest"):
        load_development_cases(work_root)


def test_load_development_cases_rejects_matrix_replacement_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autoqec_search.css_distance_development_baselines as baselines

    work_root = _write_private_split(tmp_path, split="development")
    real_stat = baselines.os.stat

    def replaced_stat(path: object, *args: object, **kwargs: object) -> os.stat_result:
        result = real_stat(path, *args, **kwargs)
        if path == "hx.json" and kwargs.get("follow_symlinks") is False:
            fields = list(result)
            fields[1] += 1
            return os.stat_result(fields)
        return result

    monkeypatch.setattr(baselines.os, "stat", replaced_stat)

    with pytest.raises(ValueError, match="replaced|unsafe|matrix"):
        load_development_cases(work_root)


def test_load_development_cases_bounds_descriptor_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autoqec_search.css_distance_development_baselines as baselines

    work_root = _write_private_split(tmp_path, split="development")
    development = (
        work_root / "private" / "css-distance-paper-suite" / "development"
    )
    manifest_size = (development / "manifest.json").stat().st_size
    monkeypatch.setattr(
        baselines,
        "_MAX_JSON_INPUT_BYTES",
        manifest_size + 1,
        raising=False,
    )
    oversized = {
        "format": "sparse_rows",
        "num_cols": 4,
        "rows": [[0, 1]],
        "padding": "x" * (manifest_size + 1),
    }
    (development / "development-000" / "hx.json").write_text(
        json.dumps(oversized),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hx matrix|unsafe"):
        load_development_cases(work_root)


@pytest.mark.parametrize("replacement", ["different-inode", "symlink", "hardlink"])
def test_loaded_development_case_rejects_matrix_replacement_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement: str,
) -> None:
    import autoqec_search.css_distance_eval as evaluation

    work_root = _write_private_split(tmp_path, split="development")
    case = load_development_cases(work_root)[0]
    replacement_path = tmp_path / "replacement-hx.json"
    replacement_path.write_text(case.hx_path.read_text(encoding="utf-8"), encoding="utf-8")
    if replacement == "different-inode":
        os.replace(replacement_path, case.hx_path)
    elif replacement == "symlink":
        case.hx_path.unlink()
        os.symlink(replacement_path, case.hx_path)
    else:
        case.hx_path.unlink()
        os.link(replacement_path, case.hx_path)

    launched = False

    def reject_launch(*args: object, **kwargs: object) -> None:
        nonlocal launched
        launched = True
        raise AssertionError("candidate must not launch after matrix replacement")

    monkeypatch.setattr(evaluation.subprocess, "Popen", reject_launch)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "candidate.py").write_text("print('{}')\n", encoding="utf-8")

    with pytest.raises(CssDistanceInfrastructureError, match="development matrix"):
        _run_container_method(
            cases=[case],
            seeds=[7],
            docker_image=DockerImage(
                "sha256:" + "2" * 64,
                "synthetic-baseline",
                role="evaluator",
            ),
            candidate_worktree=candidate,
            output_root=tmp_path / "output",
            timeout_seconds=1,
            max_parallel=1,
        )

    assert launched is False


def test_loaded_development_case_with_stable_matrices_reaches_candidate(
    tmp_path: Path,
) -> None:
    work_root = _write_private_split(tmp_path, split="development")
    case = load_development_cases(work_root)[0]

    result = run_candidate_case(
        command=[sys.executable, "-c", "print('{}')"],
        case={
            "case_id": case.case_id,
            "hx_path": case.hx_path,
            "hz_path": case.hz_path,
            "hx_identity": case.hx_identity,
            "hz_identity": case.hz_identity,
        },
        seed=7,
        timeout_seconds=1,
    )

    assert result["status"] == "invalid"
    assert not any("identity" in key or "path" in key for key in result)


@pytest.mark.parametrize("consumer", ["container", "random-window"])
def test_development_consumers_reject_same_inode_rewrite_with_restored_mtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    consumer: str,
) -> None:
    work_root = _write_private_split(tmp_path, split="development")
    case = load_development_cases(work_root)[0]
    before = os.stat(case.hx_path, follow_symlinks=False)
    original = case.hx_path.read_bytes()
    rewritten = original.replace(b"[[0, 1]]", b"[[0, 2]]", 1)
    assert rewritten != original
    assert len(rewritten) == len(original)
    with case.hx_path.open("r+b") as stream:
        stream.write(rewritten)
        stream.truncate()
    os.utime(
        case.hx_path,
        ns=(before.st_atime_ns, before.st_mtime_ns),
        follow_symlinks=False,
    )
    after = os.stat(case.hx_path, follow_symlinks=False)
    assert (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) == (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )

    _assert_development_consumer_rejects(
        case=case,
        consumer=consumer,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )


@pytest.mark.parametrize("consumer", ["container", "random-window"])
@pytest.mark.parametrize("drift", ["mode", "link-count"])
def test_development_consumers_reject_matrix_metadata_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    consumer: str,
    drift: str,
) -> None:
    work_root = _write_private_split(tmp_path, split="development")
    case = load_development_cases(work_root)[0]
    if drift == "mode":
        current_mode = stat.S_IMODE(os.stat(case.hx_path).st_mode)
        os.chmod(case.hx_path, current_mode ^ stat.S_IXUSR)
    else:
        os.link(case.hx_path, tmp_path / "additional-hx-link.json")

    _assert_development_consumer_rejects(
        case=case,
        consumer=consumer,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )


def test_open_directory_at_nofollow_closes_descriptor_when_fstat_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autoqec_search.css_distance_development_baselines as baselines

    child = tmp_path / "child"
    child.mkdir()
    parent_fd = os.open(tmp_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    real_fstat = os.fstat
    real_close = os.close
    opened: list[int] = []

    def fail_fstat(descriptor: int) -> os.stat_result:
        opened.append(descriptor)
        raise OSError("synthetic fstat failure")

    monkeypatch.setattr(baselines.os, "fstat", fail_fstat)
    try:
        with pytest.raises(ValueError, match="unsafe child"):
            _open_directory_at_nofollow(parent_fd, "child", label="child")
        assert len(opened) == 1
        with pytest.raises(OSError):
            real_fstat(opened[0])
    finally:
        if opened:
            try:
                real_close(opened[0])
            except OSError:
                pass
        real_close(parent_fd)


def test_load_development_cases_never_reads_final_split(tmp_path: Path) -> None:
    work_root = _write_private_split(tmp_path, split="development")
    final_root = work_root / "private" / "css-distance-paper-suite" / "final"
    final_root.mkdir()
    (final_root / "manifest.json").write_text("not json", encoding="utf-8")

    assert len(load_development_cases(work_root)) == 24


def test_aggregate_method_results_counts_timeouts_as_full_budget() -> None:
    cases = [
        DevelopmentCase(
            case_id="development-000",
            hx_path=Path("hidden/hx.json"),
            hz_path=Path("hidden/hz.json"),
            target=1,
            bound_type="exact",
            weight=1,
        ),
        DevelopmentCase(
            case_id="development-001",
            hx_path=Path("hidden2/hx.json"),
            hz_path=Path("hidden2/hz.json"),
            target=2,
            bound_type="upper",
            weight=1,
        ),
    ]

    row = aggregate_method_results(
        key="codedistance/QDistRndMW",
        interpretation="Development baseline.",
        cases=cases,
        results=[
            {
                "case_id": "development-000",
                "seed": 101,
                "status": "completed",
                "verified_weight": 1,
                "runtime_seconds": 0.5,
            },
            {
                "case_id": "development-001",
                "seed": 102,
                "status": "timeout",
                "runtime_seconds": 0.01,
            },
        ],
        timeout_seconds=300,
    )

    assert row["cases"] == 2
    assert row["completed"] == 1
    assert row["target_hits"] == 1
    assert row["timeouts"] == 1
    assert row["total_seconds"] == pytest.approx(300.5)
    assert row["average_seconds"] == pytest.approx(150.25)
    assert row["median_seconds"] == pytest.approx(150.25)


def test_write_baseline_aggregate_excludes_private_case_material(tmp_path: Path) -> None:
    output = tmp_path / "baseline.json"
    write_baseline_aggregate(
        output,
        rows=[
            {
                "key": "codedistance/QDistRndMW",
                "cases": 24,
                "completed": 24,
                "target_hits": 20,
                "timeouts": 0,
                "crashes": 0,
                "invalid_claims": 0,
                "weighted_target_hits": 20,
                "normalized_quality": 0.9,
                "total_seconds": 12.0,
                "average_seconds": 0.5,
                "median_seconds": 0.5,
                "interpretation": "Blinded development baseline.",
            }
        ],
        timeout_seconds=300,
    )

    payload = output.read_text(encoding="utf-8")
    assert "development-000" not in payload
    assert "source_case_id" not in payload
    assert "hx_path" not in payload
    assert "hz_path" not in payload
    assert "seed" not in payload
    assert "witness" not in payload


def test_write_baseline_aggregate_rejects_private_text(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="private"):
        write_baseline_aggregate(
            tmp_path / "baseline.json",
            rows=[
                {
                    "key": "codedistance/QDistRndMW",
                    "cases": 24,
                    "completed": 24,
                    "target_hits": 20,
                        "timeouts": 0,
                        "crashes": 0,
                        "invalid_claims": 0,
                        "weighted_target_hits": 20,
                        "normalized_quality": 0.9,
                        "total_seconds": 12.0,
                        "average_seconds": 0.5,
                        "median_seconds": 0.5,
                    "interpretation": "case_id=development-000",
                }
            ],
            timeout_seconds=300,
        )


def test_random_window_runner_uses_ephemeral_paths_and_hides_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hx, hz = _matrix_pair()
    private_case_root = tmp_path / "private" / "css-distance-paper-suite" / "development" / "development-000"
    private_case_root.mkdir(parents=True)
    hx_path = private_case_root / "hx.json"
    hz_path = private_case_root / "hz.json"
    hx_path.write_text(json.dumps(hx), encoding="utf-8")
    hz_path.write_text(json.dumps(hz), encoding="utf-8")
    captured = {}

    def fake_qec_code(hx_arg: Path, hz_arg: Path, **kwargs: object) -> dict:
        captured["hx_arg"] = Path(hx_arg)
        captured["hz_arg"] = Path(hz_arg)
        captured["target_weight"] = kwargs["target_weight"]
        assert json.loads(Path(hx_arg).read_text(encoding="utf-8")) == hx
        assert json.loads(Path(hz_arg).read_text(encoding="utf-8")) == hz
        return {"verification": {"weight": 1}}

    monkeypatch.setattr(
        "autoqec_search.css_distance_development_baselines.run_qec_code_random_window_upper_bound_css_witness",
        fake_qec_code,
    )

    result = _run_random_window_case(
        case=DevelopmentCase(
            case_id="development-000",
            hx_path=hx_path,
            hz_path=hz_path,
            target=1,
            bound_type="exact",
        ),
        seed=123,
        qec_code_bin=Path("qec-code"),
        timeout_seconds=300,
        iterations=5000,
        restarts=8,
    )

    assert result["status"] == "completed"
    assert captured["hx_arg"] != hx_path
    assert captured["hz_arg"] != hz_path
    assert "css-distance-paper-suite" not in str(captured["hx_arg"])
    assert captured["target_weight"] is None
    assert not captured["hx_arg"].parent.exists()


@pytest.mark.parametrize("matrix_name", ["hx", "hz"])
@pytest.mark.parametrize("replacement", ["different-inode", "symlink", "hardlink"])
def test_random_window_rejects_loaded_matrix_replacement_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    matrix_name: str,
    replacement: str,
) -> None:
    work_root = _write_private_split(tmp_path, split="development")
    case = load_development_cases(work_root)[0]
    matrix_path = getattr(case, f"{matrix_name}_path")
    matrix_identity = getattr(case, f"{matrix_name}_identity")
    replacement_path = tmp_path / f"replacement-{matrix_name}.json"
    replacement_path.write_text(matrix_path.read_text(encoding="utf-8"), encoding="utf-8")
    if replacement == "different-inode":
        os.replace(replacement_path, matrix_path)
    elif replacement == "symlink":
        matrix_path.unlink()
        os.symlink(replacement_path, matrix_path)
    else:
        matrix_path.unlink()
        os.link(replacement_path, matrix_path)

    launched = False

    def reject_launch(*args: object, **kwargs: object) -> dict:
        nonlocal launched
        launched = True
        raise AssertionError("random-window must not launch after matrix replacement")

    monkeypatch.setattr(
        "autoqec_search.css_distance_development_baselines.run_qec_code_random_window_upper_bound_css_witness",
        reject_launch,
    )

    with pytest.raises(CssDistanceInfrastructureError) as error:
        _run_random_window_case(
            case=case,
            seed=123,
            qec_code_bin=Path("qec-code"),
            timeout_seconds=300,
            iterations=5000,
            restarts=8,
        )

    assert str(error.value) == "development matrix identity changed"
    assert str(matrix_path) not in str(error.value)
    assert str(matrix_identity) not in str(error.value)
    assert launched is False


@pytest.mark.parametrize("consumer", ["container", "random-window"])
def test_development_consumers_reject_post_open_matrix_swap_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    consumer: str,
) -> None:
    import autoqec_search.css_distance_development_baselines as baselines

    work_root = _write_private_split(tmp_path, split="development")
    case = load_development_cases(work_root)[0]
    replacement = tmp_path / "replacement-hx.json"
    replacement.write_text(case.hx_path.read_text(encoding="utf-8"), encoding="utf-8")
    real_read = baselines.os.read
    swapped = False

    def swap_path_after_open(descriptor: int, size: int) -> bytes:
        nonlocal swapped
        metadata = os.fstat(descriptor)
        identity = (
            metadata.st_dev,
            metadata.st_ino,
        )
        if not swapped and identity == case.hx_identity[:2]:
            os.replace(replacement, case.hx_path)
            swapped = True
        return real_read(descriptor, size)

    monkeypatch.setattr(baselines.os, "read", swap_path_after_open)

    _assert_development_consumer_rejects(
        case=case,
        consumer=consumer,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    assert swapped is True


def test_random_window_accepts_loaded_case_with_stable_matrix_identities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = _write_private_split(tmp_path, split="development")
    case = load_development_cases(work_root)[0]
    hx, hz = _matrix_pair()
    launched = False

    def fake_qec_code(hx_arg: Path, hz_arg: Path, **kwargs: object) -> dict:
        nonlocal launched
        launched = True
        assert json.loads(Path(hx_arg).read_text(encoding="utf-8")) == hx
        assert json.loads(Path(hz_arg).read_text(encoding="utf-8")) == hz
        return {"verification": {"weight": 1}}

    monkeypatch.setattr(
        "autoqec_search.css_distance_development_baselines.run_qec_code_random_window_upper_bound_css_witness",
        fake_qec_code,
    )

    result = _run_random_window_case(
        case=case,
        seed=123,
        qec_code_bin=Path("qec-code"),
        timeout_seconds=300,
        iterations=5000,
        restarts=8,
    )

    assert launched is True
    assert result["status"] == "completed"
    assert result["verified_weight"] == 1


def test_run_case_jobs_preserves_case_order_with_parallel_workers() -> None:
    cases = [
        DevelopmentCase(
            case_id=f"development-{index:03d}",
            hx_path=Path("hx.json"),
            hz_path=Path("hz.json"),
            target=1,
            bound_type="exact",
        )
        for index in range(4)
    ]

    results = _run_case_jobs(
        cases=cases,
        seeds=[10, 11, 12, 13],
        max_parallel=2,
        runner=lambda case, seed: {"case_id": case.case_id, "seed": seed},
    )

    assert [result["case_id"] for result in results] == [
        "development-000",
        "development-001",
        "development-002",
        "development-003",
    ]
    assert [result["seed"] for result in results] == [10, 11, 12, 13]


def test_run_case_jobs_reports_only_aggregate_progress() -> None:
    cases = [
        DevelopmentCase(
            case_id=f"development-{index:03d}",
            hx_path=Path("hx.json"),
            hz_path=Path("hz.json"),
            target=1,
            bound_type="exact",
        )
        for index in range(3)
    ]
    progress = []

    _run_case_jobs(
        cases=cases,
        seeds=[10, 11, 12],
        max_parallel=1,
        runner=lambda case, seed: {"case_id": case.case_id, "seed": seed},
        on_complete=lambda completed, total: progress.append((completed, total)),
    )

    assert progress == [(1, 3), (2, 3), (3, 3)]


def test_prepare_candidate_runtime_wraps_root_candidate_py(tmp_path: Path) -> None:
    source = tmp_path / "baseline-source"
    source.mkdir()
    (source / "candidate.py").write_text("print('public candidate')\n", encoding="utf-8")
    runtime = _prepare_candidate_runtime(source, tmp_path / "output")

    assert runtime.name == "proposal-workspace"
    assert runtime.parent.name == "candidate-runtime"
    assert (runtime / "candidate.py").read_text(encoding="utf-8") == "print('public candidate')\n"
