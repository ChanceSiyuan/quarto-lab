"""Aggregate-only CSS-distance development-trial evaluation and reporting."""

from __future__ import annotations

import math
from pathlib import Path
import re
import statistics
import tempfile
from typing import Any

from autoqec_search.css_distance_autoresearch import append_sanitized_evaluation_log
from autoqec_search.css_distance_container import DockerImage
from autoqec_search.css_distance_development_baselines import (
    DevelopmentCase,
    DevelopmentSuiteSnapshot,
    _run_container_method,
    load_development_cases,
    validate_development_cases,
    validate_development_snapshot,
)
from autoqec_search.css_distance_eval import DEFAULT_TIMEOUT_SECONDS, sanitize_log_summary
from autoqec_search.css_distance_results_page import (
    _MAX_PUBLIC_METHOD_LENGTH,
    _PUBLIC_METHOD,
    _find_forbidden_output_detail,
)


_PROPOSAL_RANGE = range(101, 201)
_REQUIRED_SUMMARY_FIELDS = {
    "decision",
    "accepted",
    "runs",
    "verified_witnesses",
    "target_hits",
    "timeouts",
    "crashes",
    "invalid_claims",
    "weighted_target_hits",
    "normalized_quality",
    "runtime_seconds",
}
_TIMING_FIELDS = ("average_seconds", "median_seconds", "p95_seconds")
_IMMUTABLE_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")


def nearest_rank_percentile(values: list[float], percentile: float) -> float:
    if not values or not 0 < percentile <= 1:
        raise ValueError("percentile requires nonempty values and 0 < p <= 1")
    ordered = sorted(_safe_duration(value) for value in values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def aggregate_trial_results(
    *,
    cases: list[DevelopmentCase],
    results: list[dict[str, Any]],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return the fixed aggregate-only summary for one 24-case trial."""

    timeout = _require_fixed_timeout(timeout_seconds)
    if len(cases) != 24:
        raise ValueError("development trial must contain exactly 24 cases")
    case_by_id = {case.case_id: case for case in cases}
    if len(case_by_id) != len(cases):
        raise ValueError("duplicate development case")
    if len(results) != len(cases):
        raise ValueError("missing development case result")

    result_by_id: dict[str, dict[str, Any]] = {}
    for result in results:
        case_id = result.get("case_id")
        if not isinstance(case_id, str) or case_id not in case_by_id:
            raise ValueError("unsafe development case result")
        if case_id in result_by_id:
            raise ValueError("duplicate development case result")
        _safe_duration(result.get("runtime_seconds"))
        result_by_id[case_id] = result
    if set(result_by_id) != set(case_by_id):
        raise ValueError("missing development case result")

    durations: list[float] = []
    verified_witnesses = 0
    target_hits = 0
    timeouts = 0
    crashes = 0
    invalid_claims = 0
    weighted_target_hits = 0
    quality_numerator = 0.0
    quality_denominator = sum(case.weight for case in cases)

    for case in cases:
        result = result_by_id[case.case_id]
        status = result.get("status")
        runtime = _safe_duration(result.get("runtime_seconds"))
        durations.append(timeout if status == "timeout" else runtime)
        if status == "timeout":
            timeouts += 1
            continue
        if status == "crash":
            crashes += 1
            continue
        if status != "completed":
            invalid_claims += 1
            continue

        verified_weight = result.get("verified_weight")
        if type(verified_weight) is not int or verified_weight <= 0:
            invalid_claims += 1
            continue
        verified_witnesses += 1
        hit = (
            verified_weight == case.target
            if case.bound_type == "exact"
            else verified_weight <= case.target
        )
        if hit:
            target_hits += 1
            weighted_target_hits += case.weight
        quality_numerator += case.weight * min(1.0, case.target / verified_weight)

    runtime_seconds = sum(durations)
    accepted = invalid_claims == 0 and weighted_target_hits > 0
    return {
        "decision": "accepted" if accepted else "rejected",
        "accepted": accepted,
        "runs": len(cases),
        "verified_witnesses": verified_witnesses,
        "target_hits": target_hits,
        "timeouts": timeouts,
        "crashes": crashes,
        "invalid_claims": invalid_claims,
        "weighted_target_hits": weighted_target_hits,
        "normalized_quality": (
            quality_numerator / quality_denominator if quality_denominator else 0.0
        ),
        "runtime_seconds": runtime_seconds,
        "average_seconds": statistics.mean(durations),
        "median_seconds": statistics.median(durations),
        "p95_seconds": nearest_rank_percentile(durations, 0.95),
    }


def not_run_trial_summary(*, invalid_claims: int = 1) -> dict[str, Any]:
    """Return a rejected zero-run summary with timing quantiles omitted."""

    if type(invalid_claims) is not int or invalid_claims < 1:
        raise ValueError("invalid_claims must be a positive integer")
    return {
        "decision": "rejected",
        "accepted": False,
        "runs": 0,
        "verified_witnesses": 0,
        "target_hits": 0,
        "timeouts": 0,
        "crashes": 0,
        "invalid_claims": invalid_claims,
        "weighted_target_hits": 0,
        "normalized_quality": 0.0,
        "runtime_seconds": 0.0,
    }


def run_development_trial(
    *,
    proposal: int,
    suite_work_root: Path,
    candidate_worktree: Path,
    docker_image: DockerImage,
    output_root: Path,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_parallel: int = 2,
    development_snapshot: DevelopmentSuiteSnapshot | None = None,
    development_cases: tuple[DevelopmentCase, ...] | None = None,
) -> dict[str, Any]:
    """Evaluate exactly the development split and return no case-level data."""

    _validate_proposal(proposal)
    _require_fixed_timeout(timeout_seconds)
    if development_snapshot is not None and development_cases is not None:
        raise ValueError("development trial input is ambiguous")
    if development_snapshot is not None:
        validate_development_snapshot(development_snapshot)
        cases: list[DevelopmentCase] | tuple[DevelopmentCase, ...] = (
            development_snapshot.cases
        )
    elif development_cases is not None:
        validate_development_cases(development_cases)
        cases = development_cases
    else:
        cases: list[DevelopmentCase] | tuple[DevelopmentCase, ...] = (
            load_development_cases(suite_work_root)
        )
    seeds = [202607230000 + proposal * 100 + index for index in range(len(cases))]
    results = _run_container_method(
        cases=cases,
        seeds=seeds,
        docker_image=docker_image,
        candidate_worktree=candidate_worktree,
        output_root=output_root / f"proposal-{proposal:03d}",
        timeout_seconds=timeout_seconds,
        max_parallel=max_parallel,
    )
    return aggregate_trial_results(
        cases=cases,
        results=results,
        timeout_seconds=timeout_seconds,
    )


def append_trial_result_log(worktree_root: Path, *, summary: dict[str, Any]) -> Path:
    """Append a sanitized aggregate development result to ``LOG.md``."""

    return append_sanitized_evaluation_log(
        worktree_root,
        phase="development",
        summary=summary,
    )


def write_trial_report(
    output_path: Path,
    *,
    proposal: int,
    branch: str,
    method: str,
    public_contract_status: str,
    proposal_image_id: str,
    evaluator_image_id: str,
    summary: dict[str, Any],
    timeout_seconds: float = 300,
) -> Path:
    """Atomically write a privacy-scanned, aggregate-only proposal report."""

    _validate_proposal(proposal)
    expected_branch = f"autoresearch/css-distance/run200-proposal-{proposal:03d}"
    if branch != expected_branch:
        raise ValueError("proposal branch is invalid")
    if public_contract_status not in {"passed", "failed"}:
        raise ValueError("public contract status is invalid")
    if timeout_seconds != 300:
        raise ValueError("timeout_seconds must be exactly 300")
    if (
        _IMMUTABLE_IMAGE_ID.fullmatch(proposal_image_id) is None
        or _IMMUTABLE_IMAGE_ID.fullmatch(evaluator_image_id) is None
        or proposal_image_id == evaluator_image_id
    ):
        raise ValueError("trial image evidence is invalid")
    if (
        not isinstance(method, str)
        or method != method.strip()
        or len(method) > _MAX_PUBLIC_METHOD_LENGTH
        or _PUBLIC_METHOD.fullmatch(method) is None
    ):
        raise ValueError("method description is not public-safe")

    sanitized = sanitize_log_summary(summary)
    missing = _REQUIRED_SUMMARY_FIELDS - set(sanitized)
    if missing:
        raise ValueError("trial summary is missing required aggregate fields")
    runs = sanitized["runs"]
    if runs == 0:
        if any(field in sanitized for field in _TIMING_FIELDS):
            raise ValueError("zero-run trial summary must omit timing quantiles")
        timing_rows = {field: "not run" for field in _TIMING_FIELDS}
    else:
        if any(field not in sanitized for field in _TIMING_FIELDS):
            raise ValueError("trial summary is missing timing quantiles")
        timing_rows = {field: _format_seconds(sanitized[field]) for field in _TIMING_FIELDS}

    text = _render_trial_report(
        proposal=proposal,
        branch=branch,
        method=method,
        public_contract_status=public_contract_status,
        proposal_image_id=proposal_image_id,
        evaluator_image_id=evaluator_image_id,
        timeout_seconds=timeout_seconds,
        summary=sanitized,
        timing_rows=timing_rows,
    )
    forbidden_detail = _find_forbidden_output_detail(text)
    if forbidden_detail is not None:
        raise ValueError(f"forbidden output marker: {forbidden_detail}")
    return _atomic_write_text(output_path, text)


def _safe_duration(value: object) -> float:
    if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
        raise ValueError("duration must be a finite nonnegative number")
    return float(value)


def _require_fixed_timeout(value: object) -> float:
    if type(value) not in {int, float} or value != DEFAULT_TIMEOUT_SECONDS:
        raise ValueError("timeout_seconds must be exactly 300")
    return float(DEFAULT_TIMEOUT_SECONDS)


def _validate_proposal(proposal: int) -> None:
    if type(proposal) is not int or proposal not in _PROPOSAL_RANGE:
        raise ValueError("proposal must be between 101 and 200")


def _format_seconds(value: object) -> str:
    return f"{_safe_duration(value):.15f}"


def _render_trial_report(
    *,
    proposal: int,
    branch: str,
    method: str,
    public_contract_status: str,
    proposal_image_id: str,
    evaluator_image_id: str,
    timeout_seconds: float,
    summary: dict[str, Any],
    timing_rows: dict[str, str],
) -> str:
    return f"""# CSS Distance Proposal {proposal:03d} Report

## Method

The assigned exploration direction was **{method}**.

## Public Contract

| Field | Value |
| --- | ---: |
| Proposal total | 200 |
| Branch | {branch} |
| Public contract status | {public_contract_status} |
| Timeout seconds | {timeout_seconds:.0f} |
| Proposal image ID | {proposal_image_id} |
| Evaluator image ID | {evaluator_image_id} |

## Blinded Development Screening

| Metric | Value |
| --- | ---: |
| Decision | {summary['decision']} |
| Runs | {summary['runs']} |
| Verified witnesses | {summary['verified_witnesses']} |
| Target hits | {summary['target_hits']} |
| Timeouts | {summary['timeouts']} |
| Crashes | {summary['crashes']} |
| Invalid claims | {summary['invalid_claims']} |
| Weighted target hits | {summary['weighted_target_hits']} |
| Normalized quality | {summary['normalized_quality']:.15f} |
| Runtime seconds | {summary['runtime_seconds']:.15f} |
| Average seconds | {timing_rows['average_seconds']} |
| Median seconds | {timing_rows['median_seconds']} |
| P95 seconds | {timing_rows['p95_seconds']} |
"""


def _atomic_write_text(output_path: Path, text: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(text)
            temporary_path = Path(temporary.name)
        temporary_path.replace(output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return output_path
