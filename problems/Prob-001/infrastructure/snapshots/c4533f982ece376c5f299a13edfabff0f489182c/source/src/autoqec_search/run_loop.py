from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import socket
import subprocess
import time
from typing import Any

from autoqec_search import __version__
from autoqec_search.distance_methods import (
    DistanceMethodOptions,
    EXACT_BOUND,
    UPPER_BOUND,
    distance_method_metadata,
    load_distance_payload,
    normalize_distance_method_options,
)
from autoqec_search.eval_candidates import resolve_campaign_candidate_spec
from autoqec_search.eval_run import (
    _load_eval_workspace,
    _single_task,
    evaluate_resolved_candidate_into_run,
)
from autoqec_search.load import QUANTUM_TANNER_P001_SUITE_ID, SearchIntegrityError
from autoqec_search.promote import promote_run
from autoqec_search.reference_check import write_reference_check
from autoqec_search.report import write_report_html
from autoqec_search.rsinter import (
    RSINTER_RUN_TIMEOUT_SECONDS,
    expected_observable_run_metadata_for_completed_manifest,
    require_rsinter,
    validate_observable_run_metadata,
)
from autoqec_search.run_render import (
    ExperimentRow,
    FrontierItem,
    render_autoresearch_leaderboard,
    render_autoresearch_summary,
    render_experiment_log,
    render_frontier,
    render_run_summary_html,
)
from autoqec_search.screening import (
    load_screening_json,
    resolve_catalog_backed_candidate,
    resolve_catalog_backed_candidate_spec,
    screen_upper_bound_candidate,
    write_screening_json,
)
from autoqec_search.strategies import (
    StrategyState,
    frontier_quality,
    get_strategy,
    normalize_strategy_config,
    with_strategy_provenance,
)


DURATION_RE = re.compile(r"^([1-9][0-9]*)([smh]?)$")
CREATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
COMPLETED_POINT_KEYS = {
    "p",
    "rounds",
    "shots",
    "errors",
    "ler",
    "ci_low",
    "ci_high",
    "seconds",
}
STRATEGY_EVENT_ACTIONS = {"deduped", "evaluated", "exhausted"}
STRATEGY_EVENT_VERDICTS = {"crash", "discard", "keep", "skip", "fail"}


@dataclass(frozen=True)
class RunConfig:
    campaign_id: str
    run_id: str
    tag: str
    wall_clock_seconds: int
    seed: int
    task_id: str
    primary_decoder_id: str
    representative_p: float


@dataclass(frozen=True)
class CandidateRecord:
    candidate_id: str
    distance: int | None
    completed_manifests: list[dict]
    distance_bound_type: str | None = EXACT_BOUND
    upper_bound: int | None = None


@dataclass(frozen=True)
class StrategyEvent:
    candidate_id: str | None
    reason: str
    action: str
    verdict: str | None
    frontier_quality: tuple[int, float] | None


def parse_wall_clock_seconds(value: str) -> int:
    match = DURATION_RE.fullmatch(value)
    if match is None:
        raise SearchIntegrityError(f"invalid wall-clock duration: {value}")
    amount = int(match.group(1))
    suffix = match.group(2)
    multiplier = {"": 1, "s": 1, "m": 60, "h": 3600}[suffix]
    return amount * multiplier


def choose_seed(cli_seed: int | None, campaign: dict[str, Any]) -> int:
    if cli_seed is not None:
        if not isinstance(cli_seed, int) or isinstance(cli_seed, bool):
            raise SearchIntegrityError(f"invalid CLI seed: {cli_seed}")
        return cli_seed
    policy = campaign.get("random_seed_policy")
    if isinstance(policy, dict) and policy.get("mode") == "fixed":
        seed = policy.get("seed")
        if isinstance(seed, int) and not isinstance(seed, bool):
            return seed
    return 0


def default_tag(*, campaign_id: str, created_at: str, seed: int) -> str:
    stamp = created_at.replace("-", "").replace(":", "")
    return f"{campaign_id}-{stamp}-seed{seed}"


def validate_path_segment(value: str, *, label: str = "path segment") -> None:
    value_path = Path(value)
    if (
        not value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or "/" in value
        or "\\" in value
        or value_path.name != value
        or value_path != Path(value_path.name)
        or value in {".", ".."}
    ):
        raise SearchIntegrityError(f"{label} must be a single path segment: {value}")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def render_strategy_trace(
    campaign_id: str,
    run_id: str,
    strategy: dict,
    events: list[StrategyEvent],
) -> dict:
    return {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "strategy": {
            "name": strategy["name"],
            "params": dict(strategy.get("params", {})),
        },
        "events": [
            {
                "candidate_id": event.candidate_id,
                "reason": event.reason,
                "action": event.action,
                "verdict": event.verdict,
                "frontier_quality": (
                    {
                        "max_distance": event.frontier_quality[0],
                        "negative_ler": event.frontier_quality[1],
                    }
                    if event.frontier_quality is not None
                    else None
                ),
            }
            for event in events
        ],
    }


def write_strategy_trace(
    run_root: Path,
    config: RunConfig,
    strategy: dict,
    events: list[StrategyEvent],
) -> None:
    _write_json(
        run_root / "strategy_trace.json",
        render_strategy_trace(config.campaign_id, config.run_id, strategy, events),
    )


def suite_reference_fixture_path(worktree_root: Path, suite: dict[str, Any]) -> Path | None:
    shared_settings = suite.get("shared_settings")
    if not isinstance(shared_settings, dict):
        return None
    value = shared_settings.get("reference_fixture")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(
            "suite shared_settings.reference_fixture must be a nonempty string"
        )
    fixture_path = Path(value)
    if fixture_path.is_absolute():
        return fixture_path
    return worktree_root / fixture_path


def _strategy_trace_error(path: Path, detail: str) -> SearchIntegrityError:
    return SearchIntegrityError(f"invalid strategy_trace.json: {path}: {detail}")


def load_strategy_events(
    run_root: Path,
    *,
    config: RunConfig,
    strategy: dict,
) -> list[StrategyEvent]:
    path = run_root / "strategy_trace.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise _strategy_trace_error(path, "invalid JSON") from exc
    if not isinstance(payload, dict):
        raise _strategy_trace_error(path, "trace must be an object")
    expected_strategy = {
        "name": strategy["name"],
        "params": dict(strategy.get("params", {})),
    }
    expected = {
        "campaign_id": config.campaign_id,
        "run_id": config.run_id,
        "strategy": expected_strategy,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise _strategy_trace_error(
                path,
                f"{key} mismatch: {payload.get(key)!r} != {expected_value!r}",
            )
    if set(payload) != {"campaign_id", "run_id", "strategy", "events"}:
        raise _strategy_trace_error(path, "trace keys mismatch")
    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raise _strategy_trace_error(path, "events must be a list")
    events: list[StrategyEvent] = []
    for index, raw_event in enumerate(raw_events):
        if not isinstance(raw_event, dict):
            raise _strategy_trace_error(path, f"event {index} must be an object")
        expected_event_keys = {
            "candidate_id",
            "reason",
            "action",
            "verdict",
            "frontier_quality",
        }
        if set(raw_event) != expected_event_keys:
            raise _strategy_trace_error(path, f"event {index} keys mismatch")
        candidate_id = raw_event.get("candidate_id")
        if candidate_id is not None:
            if not isinstance(candidate_id, str):
                raise _strategy_trace_error(
                    path,
                    f"event {index} candidate_id must be a string or null",
                )
            try:
                validate_path_segment(candidate_id, label="candidate_id")
            except SearchIntegrityError as exc:
                raise _strategy_trace_error(
                    path,
                    f"event {index} candidate_id is invalid",
                ) from exc
        reason = raw_event.get("reason")
        if not isinstance(reason, str):
            raise _strategy_trace_error(path, f"event {index} reason must be a string")
        action = raw_event.get("action")
        if not isinstance(action, str):
            raise _strategy_trace_error(path, f"event {index} action must be a string")
        if action not in STRATEGY_EVENT_ACTIONS:
            raise _strategy_trace_error(path, f"event {index} action is invalid")
        verdict = raw_event.get("verdict")
        if verdict is not None and not isinstance(verdict, str):
            raise _strategy_trace_error(
                path,
                f"event {index} verdict must be a string or null",
            )
        if action == "evaluated":
            if verdict not in STRATEGY_EVENT_VERDICTS:
                raise _strategy_trace_error(
                    path,
                    f"event {index} evaluated verdict is invalid",
                )
        elif verdict is not None:
            raise _strategy_trace_error(
                path,
                f"event {index} verdict must be null for {action}",
            )
        raw_frontier_quality = raw_event.get("frontier_quality")
        if raw_frontier_quality is None:
            quality = None
        elif isinstance(raw_frontier_quality, dict):
            if set(raw_frontier_quality) != {"max_distance", "negative_ler"}:
                raise _strategy_trace_error(
                    path,
                    f"event {index} frontier_quality keys mismatch",
                )
            max_distance = raw_frontier_quality.get("max_distance")
            negative_ler = raw_frontier_quality.get("negative_ler")
            if (
                not isinstance(max_distance, int)
                or isinstance(max_distance, bool)
                or max_distance < 0
            ):
                raise _strategy_trace_error(
                    path,
                    f"event {index} max_distance must be a nonnegative integer",
                )
            if not _is_json_number(negative_ler):
                raise _strategy_trace_error(
                    path,
                    f"event {index} negative_ler must be a finite number",
                )
            if not -1.0 <= float(negative_ler) <= 0.0:
                raise _strategy_trace_error(
                    path,
                    f"event {index} negative_ler is out of range",
                )
            quality = (max_distance, float(negative_ler))
        else:
            raise _strategy_trace_error(
                path,
                f"event {index} frontier_quality must be an object or null",
            )
        events.append(
            StrategyEvent(
                candidate_id=candidate_id,
                reason=reason,
                action=action,
                verdict=verdict,
                frontier_quality=quality,
            )
        )
    return events


def resume_strategy_config(run_root: Path) -> dict:
    path = run_root / "run_spec.json"
    payload = _read_json_dict_if_possible(path)
    if payload is None:
        raise SearchIntegrityError(f"invalid resume run_spec.json: {path}")
    if "strategy" not in payload:
        return {"name": "grid", "params": {}}
    return normalize_strategy_config({"strategy": payload["strategy"]})


def ensure_resume_strategy_metadata(
    run_root: Path,
    *,
    strategy: dict,
) -> None:
    run_spec_path = run_root / "run_spec.json"
    run_spec = _read_json_dict_if_possible(run_spec_path)
    if run_spec is None:
        raise SearchIntegrityError(f"invalid resume run_spec.json: {run_spec_path}")
    expected_strategy = {
        "name": strategy["name"],
        "params": dict(strategy.get("params", {})),
    }
    if run_spec.get("strategy") != expected_strategy:
        run_spec["strategy"] = expected_strategy
        _write_json(run_spec_path, run_spec)

    env_path = run_root / "env.json"
    env = _read_json_dict_if_possible(env_path)
    if env is None:
        raise SearchIntegrityError(f"invalid resume env.json: {env_path}")
    changed = False
    if env.get("strategy_name") != strategy["name"]:
        env["strategy_name"] = strategy["name"]
        changed = True
    strategy_params = dict(strategy.get("params", {}))
    if env.get("strategy_params") != strategy_params:
        env["strategy_params"] = strategy_params
        changed = True
    if changed:
        _write_json(env_path, env)


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or (
            f"exit code {result.returncode}"
        )
        raise SearchIntegrityError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def git_status_porcelain(root: Path) -> str:
    return run_git(root, "status", "--porcelain")


def git_head_sha(root: Path) -> str:
    return run_git(root, "rev-parse", "HEAD")


def git_branch_exists(root: Path, branch: str) -> bool:
    if run_git(root, "rev-parse", "--is-inside-work-tree") != "true":
        raise SearchIntegrityError(f"git rev-parse failed: not a work tree: {root}")
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1 and not result.stderr.strip():
        return False
    detail = result.stderr.strip() or result.stdout.strip() or (
        f"exit code {result.returncode}"
    )
    raise SearchIntegrityError(f"git rev-parse --verify --quiet failed: {detail}")


def git_commit_all(root: Path, message: str) -> bool:
    run_git(root, "add", "-A")
    if git_status_porcelain(root) == "":
        return False
    run_git(root, "commit", "-m", message)
    return True


def registered_worktree_paths(root: Path) -> set[Path]:
    paths: set[Path] = set()
    for line in run_git(root, "worktree", "list", "--porcelain").splitlines():
        if not line.startswith("worktree "):
            continue
        path = Path(line.removeprefix("worktree "))
        if not path.is_absolute():
            path = root / path
        paths.add(path.resolve())
    return paths


def git_common_dir(root: Path) -> Path:
    path = Path(run_git(root, "rev-parse", "--git-common-dir"))
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def write_run_skeleton(
    run_root: Path,
    *,
    campaign_id: str,
    run_id: str,
    tag: str,
    suite: dict,
    candidate_ids: list[str],
    created_at: str,
    wall_clock_seconds: int,
    seed: int,
    env: dict,
    candidate_specs: list[dict] | None = None,
    tasks: dict[str, dict] | None = None,
    strategy: dict | None = None,
) -> dict:
    run_spec = {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "suite_id": suite["id"],
        "task_ids": list(suite["task_ids"]),
        "decoder_ids": list(suite["decoder_ids"]),
        "candidate_ids": list(candidate_ids),
        "created_at": created_at,
        "mode": "autoresearch",
        "tag": tag,
        "wall_clock_seconds": wall_clock_seconds,
        "seed": seed,
    }
    if strategy is not None:
        run_spec["strategy"] = {
            "name": strategy["name"],
            "params": dict(strategy.get("params", {})),
        }
    _write_json(run_root / "run_spec.json", run_spec)
    _write_json(run_root / "env.json", env)
    if candidate_specs is not None and tasks is not None:
        write_placeholder_candidates(
            run_root,
            campaign_id=campaign_id,
            run_id=run_id,
            suite=suite,
            tasks=tasks,
            candidate_specs=candidate_specs,
            created_at=created_at,
        )
    return run_spec


def write_placeholder_candidates(
    run_root: Path,
    *,
    campaign_id: str,
    run_id: str,
    suite: dict,
    tasks: dict[str, dict],
    candidate_specs: list[dict],
    created_at: str,
) -> None:
    for candidate_spec in candidate_specs:
        candidate_id = candidate_spec["candidate_id"]
        validate_path_segment(candidate_id, label="candidate_id")
        candidate_root = run_root / "candidates" / candidate_id
        _write_json(
            candidate_root / "candidate.json",
            {
                "candidate_id": candidate_id,
                "campaign_id": campaign_id,
                "run_id": run_id,
                "code_family": candidate_spec["code_family"],
                "parameters": candidate_spec["parameters"],
                "provenance": candidate_spec["provenance"],
                "status": "placeholder",
            },
        )
        _write_json(
            candidate_root / "structure.json",
            {"status": "not-computed", "n": None, "mx": None, "mz": None},
        )
        _write_json(
            candidate_root / "distance.json",
            {"status": "not-computed", "distance": None},
        )

        for task_id in suite["task_ids"]:
            validate_path_segment(task_id, label="task_id")
            task = tasks[task_id]
            for decoder_id in suite["decoder_ids"]:
                validate_path_segment(decoder_id, label="decoder_id")
                _write_json(
                    candidate_root
                    / "evaluations"
                    / task_id
                    / decoder_id
                    / "manifest.json",
                    {
                        "campaign_id": campaign_id,
                        "run_id": run_id,
                        "candidate_id": candidate_id,
                        "task_id": task_id,
                        "decoder_id": decoder_id,
                        "status": "placeholder",
                        "metrics": {
                            metric_name: None
                            for metric_name in task["result_metrics"]
                        },
                        "created_at": created_at,
                    },
                )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def representative_ler(
    completed_manifests: list[dict],
    *,
    decoder_id: str,
    p: float,
) -> float:
    for manifest in completed_manifests:
        if manifest.get("status") != "completed":
            continue
        if manifest.get("decoder_id") != decoder_id:
            continue
        for point in manifest.get("points", []):
            if point.get("p") != p:
                continue
            ler = point.get("ler")
            if (
                isinstance(ler, (int, float))
                and not isinstance(ler, bool)
                and math.isfinite(float(ler))
                and 0 <= float(ler) <= 1
            ):
                return float(ler)
            raise SearchIntegrityError(
                f"invalid representative LER for decoder {decoder_id} at p={p}: {ler}"
            )
    raise SearchIntegrityError(
        f"missing representative LER for decoder {decoder_id} at p={p}"
    )


def _manifest_path(candidate_id: str, task_id: str, decoder_id: str) -> str:
    validate_path_segment(candidate_id, label="candidate_id")
    validate_path_segment(task_id, label="task_id")
    validate_path_segment(decoder_id, label="decoder_id")
    return (
        f"candidates/{candidate_id}/evaluations/"
        f"{task_id}/{decoder_id}/manifest.json"
    )


def _candidate_frontier_distance(candidate: CandidateRecord) -> int:
    if candidate.distance_bound_type == UPPER_BOUND:
        if type(candidate.upper_bound) is int and candidate.upper_bound > 0:
            return candidate.upper_bound
        raise SearchIntegrityError(
            f"upper-bound candidate {candidate.candidate_id} is missing upper_bound"
        )
    if candidate.distance_bound_type in {EXACT_BOUND, None}:
        if type(candidate.distance) is int and candidate.distance > 0:
            return candidate.distance
        raise SearchIntegrityError(
            f"exact candidate {candidate.candidate_id} is missing distance"
        )
    raise SearchIntegrityError(
        f"candidate {candidate.candidate_id} has unsupported distance bound_type "
        f"{candidate.distance_bound_type}"
    )


def _frontier_distance_description(*, bound_type: str | None, distance: int) -> str:
    if bound_type == UPPER_BOUND:
        return f"upper-bound distance {distance}"
    return f"distance {distance}"


def update_frontier(
    config: RunConfig,
    frontier: list[FrontierItem],
    candidate: CandidateRecord,
) -> tuple[list[FrontierItem], ExperimentRow]:
    by_distance: dict[int, FrontierItem] = {}
    for item in frontier:
        if item.distance in by_distance:
            raise SearchIntegrityError(f"duplicate frontier distance: {item.distance}")
        by_distance[item.distance] = item

    frontier_distance = _candidate_frontier_distance(candidate)
    distance_description = _frontier_distance_description(
        bound_type=candidate.distance_bound_type,
        distance=frontier_distance,
    )
    ler = representative_ler(
        candidate.completed_manifests,
        decoder_id=config.primary_decoder_id,
        p=config.representative_p,
    )
    new_item = FrontierItem(
        candidate_id=candidate.candidate_id,
        distance=frontier_distance,
        decoder_id=config.primary_decoder_id,
        p=config.representative_p,
        ler=ler,
        manifest_path=_manifest_path(
            candidate.candidate_id,
            config.task_id,
            config.primary_decoder_id,
        ),
        distance_bound_type=candidate.distance_bound_type or EXACT_BOUND,
        upper_bound=candidate.upper_bound,
    )

    existing = by_distance.get(frontier_distance)
    if existing is not None and ler >= existing.ler:
        row = ExperimentRow(
            candidate_id=candidate.candidate_id,
            ler=ler,
            status="discard",
            description=f"did not improve {distance_description} frontier",
        )
        return sorted(frontier, key=lambda value: (value.distance, value.candidate_id)), row

    by_distance[frontier_distance] = new_item
    row = ExperimentRow(
        candidate_id=candidate.candidate_id,
        ler=ler,
        status="keep",
        description=f"entered frontier for {distance_description}",
    )
    return (
        sorted(by_distance.values(), key=lambda value: (value.distance, value.candidate_id)),
        row,
    )


def _is_json_number_or_null(value: object) -> bool:
    return value is None or _is_json_number(value)


def _is_json_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        return False
    return math.isfinite(number)


def _is_rate(value: object) -> bool:
    return _is_json_number(value) and 0 <= float(value) <= 1


def _is_probability(value: object) -> bool:
    return _is_json_number(value) and 0 < float(value) < 1


def _is_nonnegative_number(value: object) -> bool:
    return _is_json_number(value) and float(value) >= 0


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _has_exact_keys(payload: dict, keys: set[str]) -> bool:
    return set(payload) == keys


def _has_valid_created_at(payload: dict) -> bool:
    created_at = payload.get("created_at")
    if not isinstance(created_at, str) or CREATED_AT_RE.fullmatch(created_at) is None:
        return False
    try:
        datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _manifest_has_expected_identity(
    payload: dict,
    *,
    candidate_id: str,
    task_id: str,
    decoder_id: str,
    campaign_id: str | None,
    run_id: str | None,
) -> bool:
    manifest_campaign_id = payload.get("campaign_id")
    manifest_run_id = payload.get("run_id")
    if not isinstance(manifest_campaign_id, str) or not manifest_campaign_id:
        return False
    if not isinstance(manifest_run_id, str) or not manifest_run_id:
        return False
    try:
        validate_path_segment(manifest_campaign_id, label="campaign_id")
        validate_path_segment(manifest_run_id, label="run_id")
    except SearchIntegrityError:
        return False
    if payload.get("candidate_id") != candidate_id:
        return False
    if payload.get("task_id") != task_id:
        return False
    if payload.get("decoder_id") != decoder_id:
        return False
    if campaign_id is not None and manifest_campaign_id != campaign_id:
        return False
    if run_id is not None and manifest_run_id != run_id:
        return False
    return True


def _path_has_traversal(path: Path) -> bool:
    return any(part == ".." for part in path.parts)


def _completed_manifest_is_complete(payload: dict) -> bool:
    allowed_keys = {
        "campaign_id",
        "run_id",
        "candidate_id",
        "task_id",
        "decoder_id",
        "status",
        "created_at",
        "tool_revisions",
        "decoder_parameters",
        "points",
        "run_metadata",
    }
    required_keys = allowed_keys - {"run_metadata"}
    if not _has_exact_keys(payload, required_keys) and not _has_exact_keys(
        payload, allowed_keys
    ):
        return False
    if not _has_valid_created_at(payload):
        return False
    decoder_parameters = payload.get("decoder_parameters")
    if not isinstance(decoder_parameters, dict):
        return False
    tool_revisions = payload.get("tool_revisions")
    if not isinstance(tool_revisions, dict) or not tool_revisions:
        return False
    if not all(isinstance(value, str) and value for value in tool_revisions.values()):
        return False
    run_metadata = payload.get("run_metadata")
    if run_metadata is None:
        if _completed_manifest_requires_observable_metadata(payload):
            return False
    else:
        result_for_frontier = None
        try:
            validate_observable_run_metadata(
                run_metadata,
                expected=expected_observable_run_metadata_for_completed_manifest(
                    payload
                ),
            )
        except SearchIntegrityError:
            return False
    points = payload.get("points")
    return (
        isinstance(points, list)
        and bool(points)
        and all(_completed_point_is_complete(point) for point in points)
    )


def _completed_manifest_requires_observable_metadata(payload: dict) -> bool:
    decoder_id = payload.get("decoder_id")
    return (
        payload.get("task_id") == "bb-css-memory-x-cdep-v1"
        and isinstance(decoder_id, str)
        and "bb72" in decoder_id
    )


def _completed_point_is_complete(point: object) -> bool:
    if not isinstance(point, dict) or not _has_exact_keys(point, COMPLETED_POINT_KEYS):
        return False
    if not (
        _is_nonnegative_int(point.get("errors"))
        and _is_positive_int(point.get("shots"))
        and point["errors"] <= point["shots"]
    ):
        return False
    if not (
        _is_rate(point.get("ci_low"))
        and _is_rate(point.get("ci_high"))
        and _is_rate(point.get("ler"))
        and point["ci_low"] <= point["ci_high"]
        and point["ci_low"] <= point["ler"] <= point["ci_high"]
    ):
        return False
    return (
        _is_probability(point.get("p"))
        and _is_positive_int(point.get("rounds"))
        and _is_nonnegative_number(point.get("seconds"))
    )


def _placeholder_manifest_is_complete(payload: dict) -> bool:
    if not _has_exact_keys(
        payload,
        {
            "campaign_id",
            "run_id",
            "candidate_id",
            "task_id",
            "decoder_id",
            "status",
            "metrics",
            "created_at",
        },
    ):
        return False
    if not _has_valid_created_at(payload):
        return False
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        return False
    return all(_is_json_number_or_null(value) for value in metrics.values())


def _crash_manifest_is_complete(payload: dict) -> bool:
    if not _has_exact_keys(
        payload,
        {
            "campaign_id",
            "run_id",
            "candidate_id",
            "task_id",
            "decoder_id",
            "status",
            "created_at",
            "error",
        },
    ):
        return False
    if not _has_valid_created_at(payload):
        return False
    error = payload.get("error")
    return isinstance(error, str) and bool(error)


def _manifest_is_complete(
    payload: dict,
    *,
    candidate_id: str,
    task_id: str,
    decoder_id: str,
    campaign_id: str | None,
    run_id: str | None,
) -> bool:
    if not _manifest_has_expected_identity(
        payload,
        candidate_id=candidate_id,
        task_id=task_id,
        decoder_id=decoder_id,
        campaign_id=campaign_id,
        run_id=run_id,
    ):
        return False
    status = payload.get("status")
    if status == "completed":
        return _completed_manifest_is_complete(payload)
    if status == "placeholder":
        return _placeholder_manifest_is_complete(payload)
    if status == "crash":
        return _crash_manifest_is_complete(payload)
    return False


def candidate_is_complete(
    candidate_root: Path,
    *,
    task_ids: list[str],
    decoder_ids: list[str],
    campaign_id: str | None = None,
    run_id: str | None = None,
) -> bool:
    if _path_has_traversal(candidate_root):
        return False
    try:
        validate_path_segment(candidate_root.name, label="candidate_id")
    except SearchIntegrityError:
        return False
    for task_id in task_ids:
        try:
            validate_path_segment(task_id, label="task_id")
        except SearchIntegrityError:
            return False
        for decoder_id in decoder_ids:
            try:
                validate_path_segment(decoder_id, label="decoder_id")
            except SearchIntegrityError:
                return False
            manifest_path = (
                candidate_root
                / "evaluations"
                / task_id
                / decoder_id
                / "manifest.json"
            )
            if not manifest_path.is_file():
                return False
            try:
                payload = json.loads(manifest_path.read_text())
            except (OSError, UnicodeDecodeError, ValueError):
                return False
            if not isinstance(payload, dict):
                return False
            if not _manifest_is_complete(
                payload,
                candidate_id=candidate_root.name,
                task_id=task_id,
                decoder_id=decoder_id,
                campaign_id=campaign_id,
                run_id=run_id,
            ):
                return False
    return True


def candidate_has_terminal_outcome(
    candidate_root: Path,
    *,
    task_id: str,
    primary_decoder_id: str,
    required_p_values: list[float],
    task_ids: list[str],
    decoder_ids: list[str],
    campaign_id: str,
    run_id: str,
) -> bool:
    if not candidate_is_complete(
        candidate_root,
        task_ids=task_ids,
        decoder_ids=decoder_ids,
        campaign_id=campaign_id,
        run_id=run_id,
    ):
        return False
    manifest_path = (
        candidate_root
        / "evaluations"
        / task_id
        / primary_decoder_id
        / "manifest.json"
    )
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    status = payload.get("status")
    if status == "crash":
        return True
    if status == "placeholder":
        screening = load_screening_json(candidate_root / "screening.json")
        return (
            screening is not None
            and screening.get("screening_status") == "skipped"
        )
    if status != "completed":
        return False
    return _completed_manifest_has_p_values(payload, required_p_values)


def _completed_manifest_has_p_values(payload: dict, required_p_values: list[float]) -> bool:
    points = payload.get("points")
    if not isinstance(points, list):
        return False
    present: list[float] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        p_value = point.get("p")
        if not isinstance(p_value, (int, float)) or isinstance(p_value, bool):
            continue
        try:
            p_float = float(p_value)
        except (OverflowError, ValueError):
            continue
        if math.isfinite(p_float):
            present.append(p_float)
    return all(
        any(math.isclose(actual, required, rel_tol=0.0, abs_tol=1e-15) for actual in present)
        for required in required_p_values
    )


def effective_wall_clock_seconds(campaign: dict, cli_value: str | None) -> int:
    if cli_value is not None:
        return parse_wall_clock_seconds(cli_value)

    budget = campaign.get("budget")
    if isinstance(budget, dict):
        value = budget.get("wall_clock_seconds")
        if type(value) is int and value >= 1:
            return value

    stop_conditions = campaign.get("stop_conditions")
    if isinstance(stop_conditions, dict):
        value = stop_conditions.get("max_wall_clock_seconds")
        if type(value) is int and value >= 1:
            return value

    raise SearchIntegrityError("missing wall-clock budget")


def resume_distance_method_options(run_root: Path) -> DistanceMethodOptions:
    env_path = run_root / "env.json"
    if not env_path.is_file():
        return normalize_distance_method_options(method=None)
    try:
        env = json.loads(env_path.read_text())
    except (OSError, ValueError):
        return normalize_distance_method_options(method=None)
    metadata = env.get("distance_method") if isinstance(env, dict) else None
    if not isinstance(metadata, dict):
        return normalize_distance_method_options(method=None)
    return normalize_distance_method_options(
        method=metadata.get("method") if isinstance(metadata.get("method"), str) else None,
        qec_code_bin=metadata.get("qec_code_bin", "qec-code"),
    )


def _is_budget_timeout(exc: SearchIntegrityError, timeout_seconds: int) -> bool:
    return (
        timeout_seconds < RSINTER_RUN_TIMEOUT_SECONDS
        and f"rsinter bench run timed out after {timeout_seconds}s" in str(exc)
    )


def create_or_resume_worktree(
    root: Path,
    tag: str,
    resume: bool,
    allow_dirty_root: bool,
) -> tuple[Path, str]:
    root = root.resolve()
    validate_path_segment(tag, label="run_id")
    branch = f"autoresearch/{tag}"
    worktree_root = root / ".worktrees" / tag

    if resume:
        if not git_branch_exists(root, branch):
            raise SearchIntegrityError(f"missing branch for resume: {branch}")
        registered_paths = registered_worktree_paths(root)
        if not worktree_root.exists():
            if worktree_root.resolve() in registered_paths:
                raise SearchIntegrityError(
                    "registered worktree path is missing: "
                    f"{worktree_root}; run `git worktree prune` or "
                    "`git worktree remove` before resuming"
                )
            worktree_root.parent.mkdir(parents=True, exist_ok=True)
            run_git(root, "worktree", "add", str(worktree_root), branch)
        elif not worktree_root.is_dir():
            raise SearchIntegrityError(
                f"resume worktree is not a directory: {worktree_root}"
            )
        else:
            if worktree_root.resolve() not in registered_paths:
                raise SearchIntegrityError(
                    f"resume worktree is not registered by parent root: {worktree_root}"
                )
            if run_git(worktree_root, "rev-parse", "--is-inside-work-tree") != "true":
                raise SearchIntegrityError(
                    f"resume path is not a git worktree: {worktree_root}"
                )
            git_dir = Path(run_git(worktree_root, "rev-parse", "--git-dir"))
            if not git_dir.is_absolute():
                git_dir = worktree_root / git_dir
            common_dir = git_common_dir(worktree_root)
            if git_dir.resolve() == common_dir.resolve():
                raise SearchIntegrityError(
                    f"resume path is not a linked git worktree: {worktree_root}"
                )
            if common_dir != git_common_dir(root):
                raise SearchIntegrityError(
                    f"resume worktree does not share parent git directory: {worktree_root}"
                )
            current_branch = run_git(worktree_root, "rev-parse", "--abbrev-ref", "HEAD")
            if current_branch != branch:
                raise SearchIntegrityError(
                    f"resume worktree expected {branch}, found {current_branch}"
                )
            if git_status_porcelain(worktree_root):
                raise SearchIntegrityError(f"resume worktree is dirty: {worktree_root}")
        return worktree_root, branch

    if git_branch_exists(root, branch):
        raise SearchIntegrityError(f"branch already exists: {branch}")
    if not allow_dirty_root and git_status_porcelain(root):
        raise SearchIntegrityError("root working tree is dirty")
    if worktree_root.exists():
        raise SearchIntegrityError(f"worktree already exists: {worktree_root}")

    worktree_root.parent.mkdir(parents=True, exist_ok=True)
    run_git(root, "worktree", "add", "-b", branch, str(worktree_root), "HEAD")
    return worktree_root, branch


def build_env(
    root: Path,
    branch: str,
    created_at: str,
    seed: int,
    wall_clock_seconds: int,
    rsinter_version: str,
    strategy: dict | None = None,
    distance_method: dict | None = None,
) -> dict:
    env = {
        "tool": "autoqec-search",
        "version": __version__,
        "generated_at": created_at,
        "mode": "autoresearch",
        "git_sha": git_head_sha(root),
        "branch": branch,
        "host": socket.gethostname(),
        "seed": seed,
        "wall_clock_seconds": wall_clock_seconds,
        "rsinter": rsinter_version,
    }
    if strategy is not None:
        env["strategy_name"] = strategy["name"]
        env["strategy_params"] = dict(strategy.get("params", {}))
    if distance_method is not None:
        env["distance_method"] = dict(distance_method)
    return env


def write_non_exact_promotion_summary(
    run_root: Path,
    *,
    distance_method: dict,
) -> dict:
    run_spec = json.loads((run_root / "run_spec.json").read_text())
    campaign_id = run_spec.get("campaign_id")
    run_id = run_spec.get("run_id")
    summary = {
        "status": "skipped_non_exact_distance",
        "generated_at": utc_now(),
        "run": f"{campaign_id}/{run_id}",
        "rules_path": None,
        "rules": None,
        "force": False,
        "distance_method": dict(distance_method),
        "promoted": [],
        "skipped": [],
        "failures": [],
    }
    _write_json(run_root / "promotion_summary.json", summary)
    return summary


def auto_promote_run_or_skip_non_exact(
    worktree_root: Path,
    run_root: Path,
    *,
    distance_method: dict,
) -> None:
    if distance_method.get("bound_type") != EXACT_BOUND:
        write_non_exact_promotion_summary(run_root, distance_method=distance_method)
        return
    promote_run(worktree_root, run_root, rules_path=None, force=False)


def write_aggregates(
    run_root: Path,
    config: RunConfig,
    rows: list[ExperimentRow],
    frontier: list[FrontierItem],
    strategy: dict | None = None,
    stop_reason: str | None = None,
) -> None:
    _write_text(run_root / "experiment-log.tsv", render_experiment_log(rows))
    _write_text(
        run_root / "leaderboard.csv",
        render_autoresearch_leaderboard(rows, frontier),
    )
    _write_json(
        run_root / "frontier.json",
        render_frontier(
            campaign_id=config.campaign_id,
            run_id=config.run_id,
            items=frontier,
        ),
    )
    _write_text(
        run_root / "summary.md",
        render_autoresearch_summary(
            campaign_id=config.campaign_id,
            run_id=config.run_id,
            tag=config.tag,
            wall_clock_seconds=config.wall_clock_seconds,
            seed=config.seed,
            rows=rows,
            frontier=frontier,
            strategy=strategy,
            stop_reason=stop_reason,
        ),
    )
    _write_text(
        run_root / "run-summary.html",
        render_run_summary_html(
            campaign_id=config.campaign_id,
            run_id=config.run_id,
            tag=config.tag,
            wall_clock_seconds=config.wall_clock_seconds,
            seed=config.seed,
            rows=rows,
            frontier=frontier,
            strategy=strategy,
            stop_reason=stop_reason,
        ),
    )


def write_final_status(
    run_root: Path,
    config: RunConfig,
    rows: list[ExperimentRow],
    frontier: list[FrontierItem],
    finalized_at: str,
    stop_reason: str,
) -> None:
    _write_json(
        run_root / "run_status.json",
        {
            "campaign_id": config.campaign_id,
            "run_id": config.run_id,
            "tag": config.tag,
            "status": "finalized",
            "finalized_at": finalized_at,
            "stop_reason": stop_reason,
            "candidates_attempted": len(rows),
            "frontier_size": len(frontier),
        },
    )


def load_existing_candidate_outcome(
    config: RunConfig,
    candidate_root: Path,
    decoder_ids: list[str],
) -> tuple[ExperimentRow, CandidateRecord | None]:
    primary_manifest_path = (
        candidate_root
        / "evaluations"
        / config.task_id
        / config.primary_decoder_id
        / "manifest.json"
    )
    primary_manifest = json.loads(primary_manifest_path.read_text())
    candidate_id = primary_manifest["candidate_id"]
    screening = load_screening_json(candidate_root / "screening.json")
    if primary_manifest.get("status") == "crash":
        status = "fail" if screening and screening["screening_status"] == "failed" else "crash"
        return (
            ExperimentRow(
                candidate_id=candidate_id,
                ler=None,
                status=status,
                description=(
                    str(screening["reason"])
                    if status == "fail"
                    else str(primary_manifest.get("error", "candidate crashed"))
                ),
            ),
            None,
        )
    if (
        primary_manifest.get("status") == "placeholder"
        and screening is not None
        and screening["screening_status"] == "skipped"
    ):
        return (
            ExperimentRow(
                candidate_id=candidate_id,
                ler=None,
                status="skip",
                description=str(screening["reason"]),
            ),
            None,
        )

    distance_payload = load_distance_payload(candidate_root / "distance.json")
    distance = distance_payload.distance
    if distance_payload.bound_type == UPPER_BOUND:
        if (
            type(distance_payload.upper_bound) is not int
            or distance_payload.upper_bound <= 0
        ):
            raise SearchIntegrityError(f"invalid completed upper_bound for {candidate_id}")
    elif type(distance) is not int or distance <= 0:
        raise SearchIntegrityError(f"invalid completed distance for {candidate_id}")

    completed_manifests: list[dict] = []
    for decoder_id in decoder_ids:
        manifest_path = (
            candidate_root
            / "evaluations"
            / config.task_id
            / decoder_id
            / "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") == "completed":
            completed_manifests.append(manifest)
    if not completed_manifests:
        raise SearchIntegrityError(
            f"completed candidate has no completed manifests: {candidate_id}"
        )

    return (
        ExperimentRow(
            candidate_id=candidate_id,
            ler=representative_ler(
                completed_manifests,
                decoder_id=config.primary_decoder_id,
                p=config.representative_p,
            ),
            status="keep",
            description=f"reloaded completed candidate {candidate_id}",
        ),
        CandidateRecord(
            candidate_id=candidate_id,
            distance=distance,
            completed_manifests=completed_manifests,
            distance_bound_type=distance_payload.bound_type,
            upper_bound=distance_payload.upper_bound,
        ),
    )


def _resume_ordered_candidate_specs(
    selected_specs: list[dict],
    strategy_events: list[StrategyEvent] | None,
) -> list[dict]:
    specs_by_id = {
        candidate_spec["candidate_id"]: candidate_spec
        for candidate_spec in selected_specs
    }
    seen_candidate_ids: set[str] = set()
    ordered_specs: list[dict] = []
    if strategy_events is not None:
        for event in strategy_events:
            if event.action != "evaluated" or event.candidate_id is None:
                continue
            candidate_spec = specs_by_id.get(event.candidate_id)
            if candidate_spec is None or event.candidate_id in seen_candidate_ids:
                continue
            ordered_specs.append(candidate_spec)
            seen_candidate_ids.add(event.candidate_id)
    for candidate_spec in selected_specs:
        candidate_id = candidate_spec["candidate_id"]
        if candidate_id in seen_candidate_ids:
            continue
        ordered_specs.append(candidate_spec)
    return ordered_specs


def rebuild_resume_state(
    run_root: Path,
    config: RunConfig,
    selected_specs: list[dict],
    suite: dict,
    selected_p_values: list[float],
    strategy_events: list[StrategyEvent] | None = None,
    run_decoder_ids: list[str] | None = None,
) -> tuple[list[ExperimentRow], list[FrontierItem], set[str], list[StrategyEvent]]:
    rows: list[ExperimentRow] = []
    frontier: list[FrontierItem] = []
    attempted_candidate_ids: set[str] = set()
    terminal_events: list[StrategyEvent] = []
    terminal_decoder_ids = run_decoder_ids or suite["decoder_ids"]
    for candidate_spec in _resume_ordered_candidate_specs(selected_specs, strategy_events):
        candidate_id = candidate_spec["candidate_id"]
        candidate_root = run_root / "candidates" / candidate_id
        if not candidate_has_terminal_outcome(
            candidate_root,
            task_id=config.task_id,
            primary_decoder_id=config.primary_decoder_id,
            required_p_values=selected_p_values,
            task_ids=suite["task_ids"],
            decoder_ids=terminal_decoder_ids,
            campaign_id=config.campaign_id,
            run_id=config.run_id,
        ):
            continue
        existing_row, existing_record = load_existing_candidate_outcome(
            config,
            candidate_root,
            terminal_decoder_ids,
        )
        if existing_record is None:
            terminal_row = existing_row
        else:
            frontier, terminal_row = update_frontier(config, frontier, existing_record)
        rows.append(terminal_row)
        attempted_candidate_ids.add(candidate_id)
        terminal_events.append(
            StrategyEvent(
                candidate_id=candidate_id,
                reason="resume-terminal-candidate",
                action="evaluated",
                verdict=terminal_row.status,
                frontier_quality=frontier_quality(frontier),
            )
        )
    return rows, frontier, attempted_candidate_ids, terminal_events


def _safe_crash_candidate_id(candidate_spec: dict) -> str:
    raw_candidate_id = candidate_spec.get("candidate_id")
    candidate_id = raw_candidate_id if isinstance(raw_candidate_id, str) else "unknown"
    try:
        validate_path_segment(candidate_id, label="candidate_id")
    except SearchIntegrityError:
        return "unknown-candidate"
    return candidate_id


def write_crash_candidate(
    run_root: Path,
    campaign_id: str,
    run_id: str,
    candidate_spec: dict,
    task_ids: list[str],
    decoder_ids: list[str],
    created_at: str,
    error: str,
) -> None:
    candidate_id = _safe_crash_candidate_id(candidate_spec)
    candidate_root = run_root / "candidates" / candidate_id
    parameters = candidate_spec.get("parameters")
    provenance = candidate_spec.get("provenance")
    payload = {
        "candidate_id": candidate_id,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "code_family": str(candidate_spec.get("code_family", "unknown-code-family")),
        "parameters": parameters if isinstance(parameters, dict) else {"invalid": True},
        "provenance": (
            provenance
            if isinstance(provenance, dict)
            else {"kind": "invalid", "label": "invalid-candidate"}
        ),
        "status": "crashed",
    }
    _write_json(candidate_root / "candidate.json", payload)
    _write_json(candidate_root / "structure.json", {"status": "crash", "error": error})
    _write_json(
        candidate_root / "distance.json",
        {"status": "crash", "distance": None, "error": error},
    )
    for task_id in task_ids:
        validate_path_segment(task_id, label="task_id")
        for decoder_id in decoder_ids:
            validate_path_segment(decoder_id, label="decoder_id")
            _write_json(
                candidate_root / "evaluations" / task_id / decoder_id / "manifest.json",
                {
                    "campaign_id": campaign_id,
                    "run_id": run_id,
                    "candidate_id": candidate_id,
                    "task_id": task_id,
                    "decoder_id": decoder_id,
                    "status": "crash",
                    "created_at": created_at,
                    "error": error,
                },
            )


def _max_candidates(campaign: dict) -> int:
    stop_conditions = campaign.get("stop_conditions")
    value = (
        stop_conditions.get("max_candidates")
        if isinstance(stop_conditions, dict)
        else None
    )
    if type(value) is not int or value < 1:
        raise SearchIntegrityError("missing max_candidates stop condition")
    return value


def _strategy_candidate_spec(
    root: Path,
    campaign_id: str,
    candidate_spec: dict,
) -> dict:
    normalized = dict(candidate_spec)
    resolved_catalog_spec = resolve_catalog_backed_candidate_spec(
        root,
        candidate_spec,
        campaign_id=campaign_id,
    )
    if resolved_catalog_spec is not None:
        normalized["parameters"] = dict(resolved_catalog_spec["parameters"])
        return normalized
    if "instance_path" not in candidate_spec:
        return normalized
    resolved = resolve_campaign_candidate_spec(
        root,
        candidate_spec,
        campaign_id=campaign_id,
    )
    normalized["parameters"] = dict(resolved.spec.parameters)
    return normalized


def _resolve_run_candidate(
    root: Path,
    *,
    campaign_id: str,
    candidate_spec: dict[str, Any],
):
    resolved_catalog_candidate = resolve_catalog_backed_candidate(
        root,
        candidate_spec,
        campaign_id=campaign_id,
    )
    if resolved_catalog_candidate is not None:
        return resolved_catalog_candidate
    return resolve_campaign_candidate_spec(
        root,
        candidate_spec,
        campaign_id=campaign_id,
    )


def _selected_candidate_specs(
    root: Path,
    workspace,
    campaign_id: str,
    campaign: dict,
) -> list[dict]:
    if campaign_id not in workspace.search_spaces:
        raise SearchIntegrityError(f"unknown search space campaign_id: {campaign_id}")
    candidate_specs = workspace.search_spaces[campaign_id]["candidate_specs"]
    selected = [
        _strategy_candidate_spec(root, campaign_id, candidate_spec)
        for candidate_spec in candidate_specs
    ]
    if not selected:
        raise SearchIntegrityError(f"campaign has no candidate specs: {campaign_id}")
    for spec in selected:
        candidate_id = spec.get("candidate_id")
        if not isinstance(candidate_id, str):
            raise SearchIntegrityError("candidate_id must be a string")
        validate_path_segment(candidate_id, label="candidate_id")
    return selected


def _validate_run_path_ids(
    *,
    campaign_id: str,
    suite: dict,
    task: dict,
) -> None:
    validate_path_segment(campaign_id, label="campaign_id")
    validate_path_segment(task["id"], label="task_id")
    for task_id in suite["task_ids"]:
        validate_path_segment(task_id, label="task_id")
    for decoder_id in suite["decoder_ids"]:
        validate_path_segment(decoder_id, label="decoder_id")


def _run_plan_from_workspace(root: Path, workspace, campaign_id: str) -> tuple[
    dict,
    dict,
    dict,
    list[dict],
    list[str],
    str,
    float,
]:
    if campaign_id not in workspace.campaigns:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")
    campaign = workspace.campaigns[campaign_id]
    suite = workspace.suites[campaign["default_suite_id"]]
    task = _single_task(suite, workspace.tasks)
    _validate_run_path_ids(campaign_id=campaign_id, suite=suite, task=task)
    selected_specs = _selected_candidate_specs(root, workspace, campaign_id, campaign)
    candidate_ids = [spec["candidate_id"] for spec in selected_specs]
    primary_decoder_id = suite["decoder_ids"][0]
    representative_p = float(task["p_list"][0])
    return (
        campaign,
        suite,
        task,
        selected_specs,
        candidate_ids,
        primary_decoder_id,
        representative_p,
    )


def autoresearch_evaluation_p_values(
    worktree_root: Path,
    run_root: Path,
    task_p_list: list[float],
) -> list[float]:
    p_values = list(task_p_list)
    rule_p = _promotion_rule_p_without_validation(worktree_root, run_root)
    if rule_p is not None and rule_p not in p_values:
        p_values.append(rule_p)
    return p_values


def _promotion_rule_p_without_validation(worktree_root: Path, run_root: Path) -> float | None:
    run_spec = _read_json_dict_if_possible(run_root / "run_spec.json")
    campaign_id = run_spec.get("campaign_id") if run_spec is not None else None
    if not isinstance(campaign_id, str) or not campaign_id:
        return None

    rules_path = None
    for campaign_path in sorted((worktree_root / "campaigns").glob("**/campaign.json")):
        payload = _read_json_dict_if_possible(campaign_path)
        if payload is not None and payload.get("id") == campaign_id:
            rules_path = campaign_path.parent / "promote_rules.json"
            break
    if rules_path is None or not rules_path.is_file():
        return None

    rules = _read_json_dict_if_possible(rules_path)
    if rules is None:
        return None
    max_ler = rules.get("max_ler_at_p")
    if not isinstance(max_ler, dict):
        return None
    rule_p = max_ler.get("p")
    if not isinstance(rule_p, (int, float)) or isinstance(rule_p, bool):
        return None
    rule_p = float(rule_p)
    if not math.isfinite(rule_p) or not 0 < rule_p < 1:
        return None
    return rule_p


def _read_json_dict_if_possible(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _duplicate_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _validate_resume_decoder_ids(
    payload: dict,
    *,
    suite: dict,
    primary_decoder_id: str,
) -> list[str]:
    decoder_ids = payload.get("decoder_ids")
    if (
        not isinstance(decoder_ids, list)
        or not decoder_ids
        or any(not isinstance(decoder_id, str) for decoder_id in decoder_ids)
    ):
        raise SearchIntegrityError("resume run_spec decoder_ids is invalid")

    duplicates = _duplicate_strings(decoder_ids)
    if duplicates:
        raise SearchIntegrityError(
            f"resume run_spec decoder_ids duplicate: {', '.join(duplicates)}"
        )

    unknown = sorted(set(decoder_ids) - set(suite["decoder_ids"]))
    if unknown:
        raise SearchIntegrityError(
            f"resume run_spec decoder_ids unknown: {', '.join(unknown)}"
        )

    if primary_decoder_id not in decoder_ids:
        raise SearchIntegrityError(
            f"resume run_spec missing primary decoder_id: {primary_decoder_id}"
        )

    return list(decoder_ids)


def validate_resume_run_skeleton(
    run_root: Path,
    *,
    config: RunConfig,
    suite: dict,
    candidate_ids: list[str],
    strategy: dict | None = None,
) -> list[str]:
    path = run_root / "run_spec.json"
    if not path.is_file():
        raise SearchIntegrityError(f"missing resume run_spec.json: {path}")
    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise SearchIntegrityError(f"invalid resume run_spec.json: {path}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid resume run_spec.json: {path}")

    expected_keys = {
        "campaign_id",
        "run_id",
        "suite_id",
        "task_ids",
        "decoder_ids",
        "candidate_ids",
        "created_at",
        "mode",
        "tag",
        "wall_clock_seconds",
        "seed",
    }
    if strategy is not None:
        if "strategy" in payload:
            expected_keys.add("strategy")
    if set(payload) != expected_keys:
        raise SearchIntegrityError(
            f"resume run_spec keys mismatch: {sorted(payload)} != {sorted(expected_keys)}"
        )
    if not _has_valid_created_at(payload):
        raise SearchIntegrityError("resume run_spec created_at is invalid")

    run_decoder_ids = _validate_resume_decoder_ids(
        payload,
        suite=suite,
        primary_decoder_id=config.primary_decoder_id,
    )

    expected = {
        "mode": "autoresearch",
        "campaign_id": config.campaign_id,
        "run_id": config.run_id,
        "tag": config.tag,
        "wall_clock_seconds": config.wall_clock_seconds,
        "seed": config.seed,
        "suite_id": suite["id"],
        "task_ids": list(suite["task_ids"]),
        "candidate_ids": list(candidate_ids),
    }
    if strategy is not None and "strategy" in payload:
        expected["strategy"] = {
            "name": strategy["name"],
            "params": dict(strategy.get("params", {})),
        }
    for key, expected_value in expected.items():
        actual_value = payload.get(key)
        if key == "strategy":
            actual_value = normalize_strategy_config({"strategy": actual_value})
        if actual_value != expected_value:
            raise SearchIntegrityError(
                f"resume run_spec {key} mismatch: "
                f"{actual_value!r} != {expected_value!r}"
            )
    return run_decoder_ids


def run_autoresearch(
    root: Path,
    *,
    campaign_id: str,
    wall_clock: str | None,
    seed: int | None,
    run_id: str | None,
    resume: bool,
    cleanup_worktree: bool,
    allow_dirty_root: bool,
    distance_method: str | None = None,
    qec_code_bin: str = "qec-code",
) -> Path:
    root = root.resolve()
    validate_path_segment(campaign_id, label="campaign_id")
    if wall_clock is not None:
        parse_wall_clock_seconds(wall_clock)
    created_at = utc_now()

    if resume:
        if run_id is None:
            raise SearchIntegrityError("resume requires run_id")
        tag = run_id
    else:
        root_is_dirty = bool(git_status_porcelain(root))
        if root_is_dirty:
            if not allow_dirty_root:
                raise SearchIntegrityError("root working tree is dirty")
            if run_id is None:
                raise SearchIntegrityError(
                    "dirty root runs require an explicit run_id for reproducible branches"
                )
            tag = run_id
        else:
            root_workspace = _load_eval_workspace(root)
            if campaign_id not in root_workspace.campaigns:
                raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")
            root_campaign = root_workspace.campaigns[campaign_id]
            actual_seed = choose_seed(seed, root_campaign)
            tag = run_id or default_tag(
                campaign_id=campaign_id,
                created_at=created_at,
                seed=actual_seed,
            )
            _run_plan_from_workspace(root, root_workspace, campaign_id)
            normalize_strategy_config(root_workspace.search_spaces[campaign_id])

    validate_path_segment(tag, label="run_id")
    actual_run_id = tag
    rsinter_executable, rsinter_version = require_rsinter()

    worktree_root, branch = create_or_resume_worktree(
        root,
        tag,
        resume,
        allow_dirty_root,
    )
    workspace = _load_eval_workspace(worktree_root)
    if campaign_id not in workspace.campaigns:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")
    campaign = workspace.campaigns[campaign_id]
    actual_seed = choose_seed(seed, campaign)
    wall_clock_seconds = effective_wall_clock_seconds(campaign, wall_clock)
    (
        campaign,
        suite,
        task,
        selected_specs,
        candidate_ids,
        primary_decoder_id,
        representative_p,
    ) = _run_plan_from_workspace(worktree_root, workspace, campaign_id)
    max_candidate_count = _max_candidates(campaign)

    run_root = worktree_root / "results" / "search" / campaign_id / actual_run_id
    if not resume and run_root.exists():
        raise SearchIntegrityError(f"run already exists: {run_root}")
    if resume and not run_root.is_dir():
        raise SearchIntegrityError(f"missing run for resume: {run_root}")
    if resume and distance_method is None:
        distance_method_options = resume_distance_method_options(run_root)
    else:
        distance_method_options = normalize_distance_method_options(
            method=distance_method,
            qec_code_bin=qec_code_bin,
        )
    distance_metadata = distance_method_metadata(distance_method_options)
    strategy_config = (
        resume_strategy_config(run_root)
        if resume
        else normalize_strategy_config(workspace.search_spaces[campaign_id])
    )
    strategy = get_strategy(strategy_config["name"])
    strategy_specs = [
        with_strategy_provenance(candidate_spec, strategy_config["name"])
        for candidate_spec in selected_specs
    ]

    config = RunConfig(
        campaign_id=campaign_id,
        run_id=actual_run_id,
        tag=tag,
        wall_clock_seconds=wall_clock_seconds,
        seed=actual_seed,
        task_id=task["id"],
        primary_decoder_id=primary_decoder_id,
        representative_p=representative_p,
    )
    resume_decoder_ids: list[str] | None = None
    if resume:
        resume_decoder_ids = validate_resume_run_skeleton(
            run_root,
            config=config,
            suite=suite,
            candidate_ids=candidate_ids,
            strategy=strategy_config,
        )
        ensure_resume_strategy_metadata(run_root, strategy=strategy_config)

    if not resume:
        env = build_env(
            worktree_root,
            branch,
            created_at,
            actual_seed,
            wall_clock_seconds,
            rsinter_version,
            strategy=strategy_config,
            distance_method=distance_metadata,
        )
        write_run_skeleton(
            run_root,
            campaign_id=campaign_id,
            run_id=actual_run_id,
            tag=tag,
            suite=suite,
            candidate_ids=candidate_ids,
            created_at=created_at,
            wall_clock_seconds=wall_clock_seconds,
            seed=actual_seed,
            env=env,
            candidate_specs=strategy_specs,
            tasks=workspace.tasks,
            strategy=strategy_config,
        )
        write_aggregates(
            run_root,
            config,
            rows=[],
            frontier=[],
            strategy=strategy_config,
        )
        write_strategy_trace(run_root, config, strategy_config, [])
        git_commit_all(worktree_root, f"start autoresearch run {actual_run_id}")

    selected_p_values = autoresearch_evaluation_p_values(
        worktree_root,
        run_root,
        [float(value) for value in task["p_list"]],
    )

    if resume:
        events = load_strategy_events(
            run_root,
            config=config,
            strategy=strategy_config,
        )
        rows, frontier, attempted_candidate_ids, terminal_events = rebuild_resume_state(
            run_root,
            config,
            strategy_specs,
            suite,
            selected_p_values,
            strategy_events=events,
            run_decoder_ids=resume_decoder_ids,
        )
        traced_evaluated_candidate_ids = {
            event.candidate_id
            for event in events
            if event.action == "evaluated" and event.candidate_id is not None
        }
        events.extend(
            event
            for event in terminal_events
            if event.candidate_id not in traced_evaluated_candidate_ids
        )
    else:
        rows = []
        frontier = []
        attempted_candidate_ids = set()
        events = []

    stop_reason = "completed"
    started = time.monotonic()
    while len(rows) < max_candidate_count:
        remaining_seconds = wall_clock_seconds - (time.monotonic() - started)
        if remaining_seconds <= 0:
            stop_reason = "wall-clock"
            break

        deduped_candidate_ids = {
            event.candidate_id
            for event in events
            if event.action == "deduped" and event.candidate_id is not None
        }
        state = StrategyState(
            candidate_specs=strategy_specs,
            frontier=frontier,
            attempted_candidate_ids=set(attempted_candidate_ids),
            deduped_candidate_ids=deduped_candidate_ids,
            seed=actual_seed,
            max_candidates=max_candidate_count,
            evaluations_completed=len(rows),
        )
        proposals = strategy.propose(state)
        if not proposals:
            events.append(
                StrategyEvent(
                    candidate_id=None,
                    reason="strategy returned no proposals",
                    action="exhausted",
                    verdict=None,
                    frontier_quality=frontier_quality(frontier),
                )
            )
            stop_reason = "search-space-exhausted"
            break

        proposal = None
        proposal_seen_candidate_ids: set[str] = set()
        for candidate_proposal in proposals:
            candidate_id = candidate_proposal.candidate_id
            validate_path_segment(candidate_id, label="candidate_id")
            if (
                candidate_id in attempted_candidate_ids
                or candidate_id in proposal_seen_candidate_ids
            ):
                events.append(
                    StrategyEvent(
                        candidate_id=candidate_id,
                        reason=candidate_proposal.reason,
                        action="deduped",
                        verdict=None,
                        frontier_quality=frontier_quality(frontier),
                    )
                )
                continue
            proposal_seen_candidate_ids.add(candidate_id)
            proposal = candidate_proposal
            break

        if proposal is None:
            events.append(
                StrategyEvent(
                    candidate_id=None,
                    reason="strategy returned no fresh candidates",
                    action="exhausted",
                    verdict=None,
                    frontier_quality=frontier_quality(frontier),
                )
            )
            stop_reason = "search-space-exhausted"
            break

        candidate_spec = proposal.candidate_spec
        candidate_id = proposal.candidate_id
        rsinter_timeout_seconds = max(
            1,
            min(RSINTER_RUN_TIMEOUT_SECONDS, math.ceil(remaining_seconds)),
        )

        result_for_frontier = None
        try:
            candidate = _resolve_run_candidate(
                worktree_root,
                campaign_id=campaign_id,
                candidate_spec=candidate_spec,
            )
            screening_decision = None
            if suite["id"] == QUANTUM_TANNER_P001_SUITE_ID:
                screening_decision = screen_upper_bound_candidate(
                    worktree_root,
                    candidate=candidate,
                    candidate_spec=candidate_spec,
                    benchmark_task=task,
                )
                write_screening_json(
                    run_root / "candidates" / candidate_id,
                    screening_decision,
                )
            if screening_decision is not None:
                if screening_decision.screening_status == "skipped":
                    row = ExperimentRow(
                        candidate_id=candidate_id,
                        ler=None,
                        status="skip",
                        description=screening_decision.reason,
                    )
                elif screening_decision.screening_status == "failed":
                    write_crash_candidate(
                        run_root,
                        campaign_id,
                        actual_run_id,
                        candidate_spec,
                        suite["task_ids"],
                        suite["decoder_ids"],
                        utc_now(),
                        screening_decision.reason,
                    )
                    row = ExperimentRow(
                        candidate_id=candidate_id,
                        ler=None,
                        status="fail",
                        description=screening_decision.reason,
                    )
                else:
                    result_for_frontier = evaluate_resolved_candidate_into_run(
                        run_root=run_root,
                        run_id=actual_run_id,
                        campaign_id=campaign_id,
                        candidate=candidate,
                        workspace=workspace,
                        suite=suite,
                        task=task,
                        selected_decoder_ids=[primary_decoder_id],
                        selected_p_values=selected_p_values,
                        created_at=utc_now(),
                        rsinter_executable=rsinter_executable,
                        rsinter_version=rsinter_version,
                        distance_method_options=distance_method_options,
                        rsinter_timeout_seconds=rsinter_timeout_seconds,
                        distance_payload_override=screening_decision.distance_payload_override,
                        observables_x_override=screening_decision.observables_x_override,
                    )
            else:
                result_for_frontier = evaluate_resolved_candidate_into_run(
                    run_root=run_root,
                    run_id=actual_run_id,
                    campaign_id=campaign_id,
                    candidate=candidate,
                    workspace=workspace,
                    suite=suite,
                    task=task,
                    selected_decoder_ids=[primary_decoder_id],
                    selected_p_values=selected_p_values,
                    created_at=utc_now(),
                    rsinter_executable=rsinter_executable,
                    rsinter_version=rsinter_version,
                    distance_method_options=distance_method_options,
                    rsinter_timeout_seconds=rsinter_timeout_seconds,
                )
        except SearchIntegrityError as exc:
            if _is_budget_timeout(exc, rsinter_timeout_seconds):
                stop_reason = "wall-clock"
                break
            message = str(exc)
            write_crash_candidate(
                run_root,
                campaign_id,
                actual_run_id,
                candidate_spec,
                suite["task_ids"],
                suite["decoder_ids"],
                utc_now(),
                message,
            )
            row = ExperimentRow(
                candidate_id=candidate_id,
                ler=None,
                status="crash",
                description=message,
            )
        if result_for_frontier is not None:
            frontier, row = update_frontier(
                config,
                frontier,
                CandidateRecord(
                    candidate_id=result_for_frontier.candidate_id,
                    distance=result_for_frontier.distance,
                    completed_manifests=result_for_frontier.completed_manifests,
                    distance_bound_type=result_for_frontier.distance_bound_type,
                    upper_bound=result_for_frontier.upper_bound,
                ),
            )

        attempted_candidate_ids.add(candidate_id)
        rows.append(row)
        events.append(
            StrategyEvent(
                candidate_id=candidate_id,
                reason=proposal.reason,
                action="evaluated",
                verdict=row.status,
                frontier_quality=frontier_quality(frontier),
            )
        )
        write_aggregates(
            run_root,
            config,
            rows,
            frontier,
            strategy=strategy_config,
        )
        write_strategy_trace(run_root, config, strategy_config, events)
        git_commit_all(worktree_root, f"evaluate {candidate_id}")

    if len(rows) >= max_candidate_count and stop_reason == "completed":
        stop_reason = "max-candidates"

    write_aggregates(
        run_root,
        config,
        rows,
        frontier,
        strategy=strategy_config,
        stop_reason=stop_reason,
    )
    write_strategy_trace(run_root, config, strategy_config, events)
    write_final_status(run_root, config, rows, frontier, utc_now(), stop_reason)
    reference_fixture_path = suite_reference_fixture_path(worktree_root, suite)
    if reference_fixture_path is not None:
        write_reference_check(run_root, reference_fixture_path, None)
    write_report_html(worktree_root, run_root)
    auto_promote_run_or_skip_non_exact(
        worktree_root,
        run_root,
        distance_method=distance_metadata,
    )
    git_commit_all(worktree_root, f"finalize autoresearch run {actual_run_id}")
    if cleanup_worktree:
        run_git(root, "worktree", "remove", str(worktree_root))
    return run_root
