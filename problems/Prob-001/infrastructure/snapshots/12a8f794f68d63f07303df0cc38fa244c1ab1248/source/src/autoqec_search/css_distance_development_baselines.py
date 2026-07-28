"""Run aggregate-only open-source baselines on the CSS-distance development split."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import stat
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from autoqec_search.css_distance_container import (
    CssDistanceInfrastructureError,
    DockerCandidateCommandBuilder,
    DockerImage,
)
from autoqec_search.css_distance_eval import (
    JsonFileIdentity,
    JsonFileSnapshot,
    _MAX_JSON_INPUT_BYTES,
    _cleanup_case_exposure,
    _create_case_exposure,
    _json_file_identity,
    _load_json_nofollow,
    run_candidate_case,
)
from autoqec_search.load import SearchIntegrityError
from autoqec_search.upper_bound_witness_finder import (
    run_qec_code_random_window_upper_bound_css_witness,
)


BASELINE_METHODS = (
    "random-window-upper-bound",
    "codedistance/QDistRndMW",
    "codedistance/QDistEvol",
    "codedistance/decoderDist",
)
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_ITERATIONS = 5000
DEFAULT_RESTARTS = 8
DEFAULT_SEED = 20260723
DEFAULT_MAX_PARALLEL = 2
_PRIVATE_MARKERS = (
    "source_case_id",
    "hx_path",
    "hz_path",
    "selection-secret",
    "salt.bin",
    "AutoQEC-private",
    "/Users/",
    "witness",
    "seed",
)
_PRIVATE_PATTERNS = (
    re.compile(r"\b(?:development|final)-\d{3}\b"),
    re.compile(r"\bcase[_ -]?id\s*[:=]", re.IGNORECASE),
    re.compile(r"(?:^|[\s\"'=])(?:[A-Za-z]:[\\/]|/(?:Users|home|private|tmp|var)/)[^\s\"'<>]*"),
)
_ALLOWED_ROW_KEYS = {
    "key",
    "cases",
    "completed",
    "target_hits",
    "timeouts",
    "crashes",
    "invalid_claims",
    "weighted_target_hits",
    "normalized_quality",
    "total_seconds",
    "average_seconds",
    "median_seconds",
    "interpretation",
}
DirectoryIdentity = tuple[int, int, int, int, int, int]


@dataclass(frozen=True)
class DevelopmentCase:
    case_id: str
    hx_path: Path
    hz_path: Path
    target: int
    bound_type: str
    weight: int = 1
    hx_identity: JsonFileIdentity | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    hz_identity: JsonFileIdentity | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class DevelopmentSuiteSnapshot:
    suite_root: Path = field(repr=False)
    split_root: Path = field(repr=False)
    suite_identity: DirectoryIdentity = field(repr=False)
    split_identity: DirectoryIdentity = field(repr=False)
    manifest: JsonFileSnapshot = field(repr=False)
    cases: tuple[DevelopmentCase, ...] = field(repr=False)


def load_development_snapshot(work_root: Path) -> DevelopmentSuiteSnapshot:
    """Load and pin the complete 24-case development suite once."""

    suite_root = Path(os.path.abspath(_resolve_suite_root(work_root)))
    split_root = suite_root / "development"
    suite_fd = _open_directory_nofollow(suite_root, label="development suite")
    try:
        suite_identity = _directory_identity(os.fstat(suite_fd))
        split_fd = _open_directory_at_nofollow(
            suite_fd,
            "development",
            label="development split",
        )
    except Exception:
        os.close(suite_fd)
        raise
    try:
        split_identity = _directory_identity(os.fstat(split_fd))
        manifest, manifest_identity = _read_json_regular_at(
            split_fd,
            "manifest.json",
            label="development manifest",
        )
        if manifest.get("split") != "development":
            raise ValueError("development split manifest is required")
        manifest_cases = manifest.get("cases")
        if not isinstance(manifest_cases, list) or len(manifest_cases) != 24:
            raise ValueError("development split must contain exactly 24 cases")

        cases: list[DevelopmentCase] = []
        seen: set[str] = set()
        for record in manifest_cases:
            if not isinstance(record, dict):
                raise ValueError("invalid development case record")
            case_id = _require_string(record.get("case_id"), "case_id")
            if case_id in seen:
                raise ValueError("duplicate development case")
            seen.add(case_id)
            if not re.fullmatch(r"development-\d{3}", case_id):
                raise ValueError("invalid development case")
            reference = record.get("reference")
            if not isinstance(reference, dict):
                raise ValueError("invalid development reference")
            target = reference.get("value")
            bound_type = reference.get("bound_type")
            if type(target) is not int or target <= 0:
                raise ValueError("invalid development reference")
            if bound_type not in {"exact", "upper"}:
                raise ValueError("invalid development reference")
            hx_path, hx_identity = _validated_split_json_path(
                split_fd,
                split_root,
                record.get("hx_path"),
                label="hx matrix",
            )
            hz_path, hz_identity = _validated_split_json_path(
                split_fd,
                split_root,
                record.get("hz_path"),
                label="hz matrix",
            )
            cases.append(
                DevelopmentCase(
                    case_id=case_id,
                    hx_path=hx_path,
                    hz_path=hz_path,
                    target=int(target),
                    bound_type=str(bound_type),
                    hx_identity=hx_identity,
                    hz_identity=hz_identity,
                )
            )
    finally:
        os.close(split_fd)
        os.close(suite_fd)
    return DevelopmentSuiteSnapshot(
        suite_root=suite_root,
        split_root=split_root,
        suite_identity=suite_identity,
        split_identity=split_identity,
        manifest=JsonFileSnapshot(
            path=split_root / "manifest.json",
            identity=manifest_identity,
        ),
        cases=tuple(cases),
    )


def load_development_cases(work_root: Path) -> list[DevelopmentCase]:
    """Load only the 24-case private development split."""

    return list(load_development_snapshot(work_root).cases)


def validate_development_cases(cases: tuple[DevelopmentCase, ...]) -> None:
    """Reject malformed pinned cases or matrix identity drift."""

    try:
        if type(cases) is not tuple or len(cases) != 24:
            raise ValueError("invalid development cases")
        seen: set[str] = set()
        for case in cases:
            if (
                type(case) is not DevelopmentCase
                or not re.fullmatch(r"development-\d{3}", case.case_id)
                or case.case_id in seen
                or not isinstance(case.hx_path, Path)
                or not isinstance(case.hz_path, Path)
                or not case.hx_path.is_absolute()
                or not case.hz_path.is_absolute()
                or ".." in case.hx_path.parts
                or ".." in case.hz_path.parts
                or type(case.target) is not int
                or case.target <= 0
                or not isinstance(case.bound_type, str)
                or case.bound_type not in {"exact", "upper"}
                or type(case.weight) is not int
                or case.weight != 1
                or case.hx_identity is None
                or case.hz_identity is None
            ):
                raise ValueError("invalid development case")
            seen.add(case.case_id)
            _load_json_nofollow(
                case.hx_path,
                expected_identity=case.hx_identity,
            )
            _load_json_nofollow(
                case.hz_path,
                expected_identity=case.hz_identity,
            )
    except Exception:
        raise CssDistanceInfrastructureError(
            "development suite snapshot changed"
        ) from None


def validate_development_snapshot(snapshot: DevelopmentSuiteSnapshot) -> None:
    """Reject any directory, manifest, target, membership, or matrix drift."""

    try:
        if type(snapshot) is not DevelopmentSuiteSnapshot:
            raise ValueError("invalid development snapshot")
        if (
            not isinstance(snapshot.suite_root, Path)
            or not isinstance(snapshot.split_root, Path)
            or not snapshot.suite_root.is_absolute()
            or not snapshot.split_root.is_absolute()
            or ".." in snapshot.suite_root.parts
            or ".." in snapshot.split_root.parts
            or snapshot.split_root != snapshot.suite_root / "development"
            or type(snapshot.manifest) is not JsonFileSnapshot
            or snapshot.manifest.path != snapshot.split_root / "manifest.json"
            or type(snapshot.cases) is not tuple
            or len(snapshot.cases) != 24
        ):
            raise ValueError("invalid development snapshot")
        suite_fd = _open_directory_nofollow(
            snapshot.suite_root,
            label="development suite",
        )
        try:
            if _directory_identity(os.fstat(suite_fd)) != snapshot.suite_identity:
                raise ValueError("changed development suite")
            split_fd = _open_directory_at_nofollow(
                suite_fd,
                "development",
                label="development split",
            )
        finally:
            os.close(suite_fd)
        try:
            if _directory_identity(os.fstat(split_fd)) != snapshot.split_identity:
                raise ValueError("changed development split")
        finally:
            os.close(split_fd)

        manifest = _load_json_nofollow(
            snapshot.manifest.path,
            expected_identity=snapshot.manifest.identity,
        )
        _validate_snapshot_manifest_contract(snapshot, manifest)
        validate_development_cases(snapshot.cases)
    except Exception:
        raise CssDistanceInfrastructureError(
            "development suite snapshot changed"
        ) from None


def _validate_snapshot_manifest_contract(
    snapshot: DevelopmentSuiteSnapshot,
    manifest: dict[str, Any],
) -> None:
    records = manifest.get("cases")
    if manifest.get("split") != "development" or not isinstance(records, list):
        raise ValueError("invalid development snapshot manifest")
    if len(records) != len(snapshot.cases):
        raise ValueError("invalid development snapshot manifest")
    seen: set[str] = set()
    for record, case in zip(records, snapshot.cases, strict=True):
        if not isinstance(record, dict) or type(case) is not DevelopmentCase:
            raise ValueError("invalid development snapshot case")
        case_id = record.get("case_id")
        reference = record.get("reference")
        if (
            not isinstance(case_id, str)
            or case_id in seen
            or not isinstance(reference, dict)
            or case.case_id != case_id
            or type(reference.get("value")) is not int
            or case.target != reference.get("value")
            or not isinstance(reference.get("bound_type"), str)
            or case.bound_type != reference.get("bound_type")
            or case.weight != 1
        ):
            raise ValueError("invalid development snapshot case")
        seen.add(case_id)
        hx_relative = _snapshot_relative_path(record.get("hx_path"))
        hz_relative = _snapshot_relative_path(record.get("hz_path"))
        if (
            case.hx_path != snapshot.split_root / hx_relative
            or case.hz_path != snapshot.split_root / hz_relative
        ):
            raise ValueError("invalid development snapshot case")


def _snapshot_relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid development snapshot path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("invalid development snapshot path")
    return relative


def aggregate_method_results(
    *,
    key: str,
    interpretation: str,
    cases: list[DevelopmentCase],
    results: list[dict[str, Any]],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return one aggregate-only row from private case-level results."""

    if key not in BASELINE_METHODS:
        raise ValueError("unknown baseline method")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("duplicate development case")
    case_by_id = {case.case_id: case for case in cases}
    durations = [_runtime_for_stats(result, timeout_seconds) for result in results]
    completed = 0
    target_hits = 0
    timeouts = 0
    crashes = 0
    invalid_claims = 0
    weighted_target_hits = 0
    quality_numerator = 0.0
    quality_denominator = sum(case.weight for case in cases) if cases else 0

    for result in results:
        status = result.get("status")
        if status == "timeout":
            timeouts += 1
            continue
        if status == "crash":
            crashes += 1
            continue
        if status == "invalid":
            invalid_claims += 1
            continue
        if status != "completed":
            invalid_claims += 1
            continue
        case = case_by_id.get(result.get("case_id"))
        verified_weight = result.get("verified_weight")
        if case is None or type(verified_weight) is not int or verified_weight <= 0:
            invalid_claims += 1
            continue
        completed += 1
        hit = (
            verified_weight == case.target
            if case.bound_type == "exact"
            else verified_weight <= case.target
        )
        if hit:
            target_hits += 1
            weighted_target_hits += case.weight
        quality_numerator += case.weight * min(1.0, case.target / verified_weight)

    total_seconds = sum(durations)
    return {
        "key": key,
        "cases": len(cases),
        "completed": completed,
        "target_hits": target_hits,
        "timeouts": timeouts,
        "crashes": crashes,
        "invalid_claims": invalid_claims,
        "weighted_target_hits": weighted_target_hits,
        "normalized_quality": (
            quality_numerator / quality_denominator if quality_denominator else 0.0
        ),
        "total_seconds": total_seconds,
        "average_seconds": statistics.mean(durations) if durations else None,
        "median_seconds": statistics.median(durations) if durations else None,
        "interpretation": interpretation,
    }


def write_baseline_aggregate(
    output_path: Path,
    *,
    rows: list[dict[str, Any]],
    timeout_seconds: float,
) -> Path:
    """Write aggregate-only development baseline results."""

    payload = {
        "schema_version": 1,
        "suite": "css-distance-paper-development",
        "case_count": 24,
        "time_limit_seconds": timeout_seconds,
        "rows": [_validated_row(row) for row in rows],
    }
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    forbidden = _private_detail(text)
    if forbidden is not None:
        raise ValueError(f"private aggregate detail: {forbidden}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return output_path


def run_all_baselines(
    *,
    suite_work_root: Path,
    qec_code_bin: Path,
    qdist_rndmw_worktree: Path,
    qdist_evol_worktree: Path,
    decoder_dist_worktree: Path,
    docker_image: DockerImage,
    output_root: Path,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    iterations: int = DEFAULT_ITERATIONS,
    restarts: int = DEFAULT_RESTARTS,
    seed_base: int = DEFAULT_SEED,
    max_parallel: int = DEFAULT_MAX_PARALLEL,
    emit_progress: bool = False,
) -> list[dict[str, Any]]:
    cases = load_development_cases(suite_work_root)
    case_seeds = [seed_base + index for index, _ in enumerate(cases)]
    methods = [
        (
            "random-window-upper-bound",
            "Open-source qec-code randomized window baseline on the 24-case blinded development split.",
            _run_case_jobs(
                cases=cases,
                seeds=case_seeds,
                max_parallel=max_parallel,
                on_complete=_progress_printer(
                    "random-window-upper-bound",
                    enabled=emit_progress,
                ),
                runner=lambda case, seed: _run_random_window_case(
                    case=case,
                    seed=seed,
                    qec_code_bin=qec_code_bin,
                    timeout_seconds=timeout_seconds,
                    iterations=iterations,
                    restarts=restarts,
                ),
            ),
        ),
        (
            "codedistance/QDistRndMW",
            "Open-source codedistance random information-set baseline on the same 24-case split.",
            _run_container_method(
                cases=cases,
                seeds=case_seeds,
                docker_image=docker_image,
                candidate_worktree=qdist_rndmw_worktree,
                output_root=output_root / "qdist-rndmw",
                timeout_seconds=timeout_seconds,
                max_parallel=max_parallel,
                on_complete=_progress_printer(
                    "codedistance/QDistRndMW",
                    enabled=emit_progress,
                ),
            ),
        ),
        (
            "codedistance/QDistEvol",
            "Open-source codedistance evolutionary baseline on the same 24-case split.",
            _run_container_method(
                cases=cases,
                seeds=case_seeds,
                docker_image=docker_image,
                candidate_worktree=qdist_evol_worktree,
                output_root=output_root / "qdist-evol",
                timeout_seconds=timeout_seconds,
                max_parallel=max_parallel,
                on_complete=_progress_printer(
                    "codedistance/QDistEvol",
                    enabled=emit_progress,
                ),
            ),
        ),
        (
            "codedistance/decoderDist",
            "Open-source codedistance BP-OSD baseline on the same 24-case split.",
            _run_container_method(
                cases=cases,
                seeds=case_seeds,
                docker_image=docker_image,
                candidate_worktree=decoder_dist_worktree,
                output_root=output_root / "decoder-dist",
                timeout_seconds=timeout_seconds,
                max_parallel=max_parallel,
                on_complete=_progress_printer(
                    "codedistance/decoderDist",
                    enabled=emit_progress,
                ),
            ),
        ),
    ]
    return [
        aggregate_method_results(
            key=key,
            interpretation=interpretation,
            cases=cases,
            results=results,
            timeout_seconds=timeout_seconds,
        )
        for key, interpretation, results in methods
    ]


def _run_container_method(
    *,
    cases: list[DevelopmentCase],
    seeds: list[int],
    docker_image: DockerImage,
    candidate_worktree: Path,
    output_root: Path,
    timeout_seconds: float,
    max_parallel: int,
    on_complete: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    candidate_runtime = _prepare_candidate_runtime(candidate_worktree, output_root)
    builder = DockerCandidateCommandBuilder(
        image=docker_image,
        candidate_worktree=candidate_runtime,
        output_root=output_root,
    )
    return _run_case_jobs(
        cases=cases,
        seeds=seeds,
        max_parallel=max_parallel,
        on_complete=on_complete,
        runner=lambda case, seed: _strip_result(
            run_candidate_case(
                command=["candidate-entrypoint"],
                command_builder=builder,
                case={
                    "case_id": case.case_id,
                    "hx_path": case.hx_path,
                    "hz_path": case.hz_path,
                    "hx_identity": case.hx_identity,
                    "hz_identity": case.hz_identity,
                },
                seed=seed,
                timeout_seconds=timeout_seconds,
            )
        )
    )


def _run_case_jobs(
    *,
    cases: list[DevelopmentCase],
    seeds: list[int],
    max_parallel: int,
    runner: Callable[[DevelopmentCase, int], dict[str, Any]],
    on_complete: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    if len(cases) != len(seeds):
        raise ValueError("cases and seeds must have the same length")
    if max_parallel < 1:
        raise ValueError("max_parallel must be at least 1")
    if not cases:
        return []
    if max_parallel == 1:
        results = []
        total = len(cases)
        for case, seed in zip(cases, seeds, strict=True):
            results.append(runner(case, seed))
            if on_complete is not None:
                on_complete(len(results), total)
        return results

    results: list[dict[str, Any] | None] = [None] * len(cases)
    completed = 0
    total = len(cases)
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(max_parallel, len(cases))
    ) as executor:
        futures = {
            executor.submit(runner, case, seed): index
            for index, (case, seed) in enumerate(zip(cases, seeds, strict=True))
        }
        for future in concurrent.futures.as_completed(futures):
            results[futures[future]] = future.result()
            completed += 1
            if on_complete is not None:
                on_complete(completed, total)
    return [result for result in results if result is not None]


def _prepare_candidate_runtime(candidate_worktree: Path, output_root: Path) -> Path:
    proposal_workspace = (
        candidate_worktree
        if candidate_worktree.name == "proposal-workspace"
        else candidate_worktree / "proposal-workspace"
    )
    proposal_candidate = proposal_workspace / "candidate.py"
    try:
        proposal_metadata = os.lstat(proposal_candidate)
    except FileNotFoundError:
        pass
    except OSError as error:
        raise ValueError("baseline candidate runtime is unsafe") from error
    else:
        if (
            not stat.S_ISREG(proposal_metadata.st_mode)
            or proposal_metadata.st_nlink != 1
        ):
            raise ValueError("baseline candidate runtime is unsafe")
        return proposal_workspace

    candidate_path = candidate_worktree / "candidate.py"
    try:
        metadata = os.lstat(candidate_path)
    except OSError as error:
        raise ValueError("baseline candidate runtime is missing candidate.py") from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise ValueError("baseline candidate runtime is unsafe")

    runtime = output_root / "candidate-runtime" / "proposal-workspace"
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    for child in runtime.iterdir():
        if child.name != "candidate.py":
            raise ValueError("baseline candidate runtime contains unexpected files")
    shutil.copy2(candidate_path, runtime / "candidate.py")
    return runtime


def _progress_printer(
    method: str,
    *,
    enabled: bool,
) -> Callable[[int, int], None] | None:
    if not enabled:
        return None

    def print_progress(completed: int, total: int) -> None:
        print(f"{method}: {completed}/{total}", file=sys.stderr, flush=True)

    return print_progress


def _run_random_window_case(
    *,
    case: DevelopmentCase,
    seed: int,
    qec_code_bin: Path,
    timeout_seconds: float,
    iterations: int,
    restarts: int,
) -> dict[str, Any]:
    started = time.monotonic()
    hx_payload = _load_json_nofollow(
        case.hx_path,
        expected_identity=case.hx_identity,
    )
    hz_payload = _load_json_nofollow(
        case.hz_path,
        expected_identity=case.hz_identity,
    )
    exposure_root, exposure_fd, exposure_parent_fd = _create_case_exposure(
        hx_payload,
        hz_payload,
    )
    try:
        result = run_qec_code_random_window_upper_bound_css_witness(
            exposure_root / "hx.json",
            exposure_root / "hz.json",
            hx_payload=hx_payload,
            hz_payload=hz_payload,
            qec_code_bin=str(qec_code_bin),
            iterations=iterations,
            restarts=restarts,
            seed=seed,
            target_weight=None,
            timeout_seconds=timeout_seconds,
        )
    except SearchIntegrityError as error:
        elapsed = time.monotonic() - started
        message = str(error)
        if "timed out after" in message:
            return {
                "case_id": case.case_id,
                "seed": seed,
                "status": "timeout",
                "runtime_seconds": max(elapsed, timeout_seconds),
            }
        if "invalid_css_upper_bound_witness" in message:
            return {
                "case_id": case.case_id,
                "seed": seed,
                "status": "invalid",
                "runtime_seconds": elapsed,
            }
        return {
            "case_id": case.case_id,
            "seed": seed,
            "status": "crash",
            "runtime_seconds": elapsed,
        }
    finally:
        _cleanup_case_exposure(
            exposure_root,
            exposure_fd,
            exposure_parent_fd,
        )
    return {
        "case_id": case.case_id,
        "seed": seed,
        "status": "completed",
        "runtime_seconds": time.monotonic() - started,
        "verified_weight": int(result["verification"]["weight"]),
    }


def _strip_result(result: dict[str, Any]) -> dict[str, Any]:
    kept = {
        "case_id",
        "seed",
        "status",
        "runtime_seconds",
        "verified_weight",
    }
    return {key: value for key, value in result.items() if key in kept}


def _validated_row(row: dict[str, Any]) -> dict[str, Any]:
    if set(row) != _ALLOWED_ROW_KEYS:
        raise ValueError("baseline aggregate row has unsafe fields")
    if row["key"] not in BASELINE_METHODS:
        raise ValueError("unknown baseline method")
    for key in ("cases", "completed", "target_hits", "timeouts", "crashes", "invalid_claims"):
        if type(row[key]) is not int or row[key] < 0:
            raise ValueError("invalid baseline aggregate count")
    for key in (
        "weighted_target_hits",
        "normalized_quality",
        "total_seconds",
        "average_seconds",
        "median_seconds",
    ):
        value = row[key]
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
            raise ValueError("invalid baseline aggregate statistic")
    if not isinstance(row["interpretation"], str) or not row["interpretation"]:
        raise ValueError("invalid baseline aggregate interpretation")
    return row


def _runtime_for_stats(result: dict[str, Any], timeout_seconds: float) -> float:
    if result.get("status") == "timeout":
        return float(timeout_seconds)
    runtime = result.get("runtime_seconds", 0.0)
    if not isinstance(runtime, (int, float)) or not math.isfinite(float(runtime)) or runtime < 0:
        return 0.0
    return float(runtime)


def _resolve_suite_root(work_root: Path) -> Path:
    try:
        os.lstat(work_root / "development")
    except FileNotFoundError:
        pass
    except OSError as error:
        raise ValueError("development suite is unavailable") from error
    else:
        return work_root
    return work_root / "private" / "css-distance-paper-suite"


def _open_directory_nofollow(path: Path, *, label: str) -> int:
    if ".." in path.parts:
        raise ValueError(f"unsafe {label}")
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as error:
        raise ValueError(f"unsafe {label}") from error
    try:
        for component in absolute.parts[1:]:
            next_descriptor = _open_directory_at_nofollow(
                descriptor,
                component,
                label=label,
            )
            os.close(descriptor)
            descriptor = next_descriptor
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _open_directory_at_nofollow(parent_fd: int, name: str, *, label: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
        metadata = os.fstat(descriptor)
    except OSError as error:
        if descriptor >= 0:
            os.close(descriptor)
        raise ValueError(f"unsafe {label}") from error
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise ValueError(f"unsafe {label}")
    return descriptor


def _read_json_regular_at(
    parent_fd: int,
    name: str,
    *,
    label: str,
) -> tuple[dict[str, Any], JsonFileIdentity]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise ValueError(f"unsafe {label}") from error
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > _MAX_JSON_INPUT_BYTES
        ):
            raise ValueError(f"unsafe {label}")
        chunks: list[bytes] = []
        digest = hashlib.sha256()
        total_bytes = 0
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > _MAX_JSON_INPUT_BYTES:
                raise ValueError(f"unsafe {label}")
            chunks.append(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
        try:
            current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as error:
            raise ValueError(f"replaced {label}") from error
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
            raise ValueError(f"replaced {label}")
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or current.st_size > _MAX_JSON_INPUT_BYTES
            or any(
                getattr(after, field) != getattr(current, field)
                for field in stable_fields
            )
        ):
            raise ValueError(f"replaced {label}")
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    finally:
        os.close(descriptor)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid {label}")
    return payload, _file_identity(after, digest.hexdigest())


def _file_identity(metadata: os.stat_result, digest: str) -> JsonFileIdentity:
    return _json_file_identity(metadata, digest)


def _directory_identity(metadata: os.stat_result) -> DirectoryIdentity:
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("unsafe development directory")
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _validated_split_json_path(
    split_fd: int,
    split_root: Path,
    value: object,
    *,
    label: str,
) -> tuple[Path, JsonFileIdentity]:
    relative = Path(_require_string(value, label))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"unsafe {label}")
    descriptor = os.dup(split_fd)
    try:
        for component in relative.parts[:-1]:
            next_descriptor = _open_directory_at_nofollow(
                descriptor,
                component,
                label=label,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        _, identity = _read_json_regular_at(
            descriptor,
            relative.parts[-1],
            label=label,
        )
    finally:
        os.close(descriptor)
    root = Path(os.path.abspath(split_root))
    candidate = Path(os.path.abspath(split_root / relative))
    if root not in candidate.parents:
        raise ValueError(f"unsafe {label}")
    return candidate, identity


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid {label}")
    return value


def _private_detail(text: str) -> str | None:
    normalized = text.casefold()
    for marker in _PRIVATE_MARKERS:
        if marker.casefold() in normalized:
            return "literal private marker"
    for pattern in _PRIVATE_PATTERNS:
        if pattern.search(text) is not None:
            return "structured private marker"
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run aggregate-only CSS-distance development baselines"
    )
    parser.add_argument("--suite-work-root", required=True, type=Path)
    parser.add_argument("--qec-code-bin", required=True, type=Path)
    parser.add_argument("--qdist-rndmw-worktree", required=True, type=Path)
    parser.add_argument("--qdist-evol-worktree", required=True, type=Path)
    parser.add_argument("--decoder-dist-worktree", required=True, type=Path)
    parser.add_argument("--docker-image", default="autoqec-css-distance-evaluator:a4afe9c")
    parser.add_argument("--docker-baseline", default="a4afe9c")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", default=DEFAULT_TIMEOUT_SECONDS, type=float)
    parser.add_argument("--iterations", default=DEFAULT_ITERATIONS, type=int)
    parser.add_argument("--restarts", default=DEFAULT_RESTARTS, type=int)
    parser.add_argument("--seed-base", default=DEFAULT_SEED, type=int)
    parser.add_argument("--max-parallel", default=DEFAULT_MAX_PARALLEL, type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = run_all_baselines(
        suite_work_root=args.suite_work_root,
        qec_code_bin=args.qec_code_bin,
        qdist_rndmw_worktree=args.qdist_rndmw_worktree,
        qdist_evol_worktree=args.qdist_evol_worktree,
        decoder_dist_worktree=args.decoder_dist_worktree,
        docker_image=DockerImage(args.docker_image, args.docker_baseline),
        output_root=args.output_root,
        timeout_seconds=args.timeout_seconds,
        iterations=args.iterations,
        restarts=args.restarts,
        seed_base=args.seed_base,
        max_parallel=args.max_parallel,
        emit_progress=True,
    )
    write_baseline_aggregate(args.output, rows=rows, timeout_seconds=args.timeout_seconds)
    print("wrote CSS-distance development baseline aggregate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
