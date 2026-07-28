"""Controller primitives for CSS-distance upper-bound autoresearch."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable

from autoqec_search.css_distance_eval import (
    DEFAULT_TIMEOUT_SECONDS,
    run_private_phase,
    sanitize_log_summary,
    score_candidate,
)
from autoqec_search.css_distance_git_evidence import run_git
from autoqec_search.load import CREATED_AT_RE, SearchIntegrityError
from autoqec_search.run_loop import validate_path_segment


_ALGORITHM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_PRIVATE_HOLDOUT_MARKERS = (
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
    "case-000",
    "answers.json",
    "expected_distance",
    "expected_bound_type",
)
_LOG_FIELD_ORDER = (
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
    "average_seconds",
    "median_seconds",
    "p95_seconds",
)


@dataclass(frozen=True)
class CssDistanceExperiment:
    algorithm_id: str
    worktree_root: Path
    branch: str
    created_at: str
    timeout_seconds: int


@dataclass(frozen=True)
class CssDistanceEvaluationResult:
    algorithm_id: str
    phase: str
    summary: dict


def _validate_algorithm_id(algorithm_id: str) -> None:
    validate_path_segment(algorithm_id, label="algorithm_id")
    if not _ALGORITHM_ID_RE.fullmatch(algorithm_id):
        raise SearchIntegrityError(
            "algorithm_id must contain only letters, numbers, dots, underscores, and hyphens"
        )


def _ensure_public_text(text: str, *, label: str) -> None:
    leaked = [marker for marker in _PRIVATE_HOLDOUT_MARKERS if marker in text]
    if leaked:
        raise SearchIntegrityError(
            f"{label} would leak private holdout marker: {leaked[0]}"
        )


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _load_private_answers(work_root: Path) -> dict:
    answers_path = work_root / "private" / "holdout" / "answers.json"
    payload = json.loads(answers_path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError("private holdout answers must be a JSON object")
    return payload


def _phase_seeds(answers: dict, phase: str) -> list[int]:
    if phase == "screening":
        seeds = [answers.get("screening_seed")]
    elif phase == "finalists":
        seeds = answers.get("finalist_seeds")
    else:
        raise SearchIntegrityError(f"invalid CSS-distance evaluation phase: {phase}")
    if (
        not isinstance(seeds, list)
        or not seeds
        or len(set(seeds)) != len(seeds)
        or any(type(seed) is not int for seed in seeds)
    ):
        raise SearchIntegrityError("invalid private holdout seeds")
    return seeds


def _private_cases(answers: dict) -> list[dict]:
    cases = answers.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SearchIntegrityError("invalid private holdout cases")
    for case in cases:
        if not isinstance(case, dict):
            raise SearchIntegrityError("invalid private holdout case")
    return cases


def write_css_distance_log_header(
    worktree_root: Path,
    *,
    algorithm_id: str,
    branch: str,
    created_at: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Path:
    """Create the per-algorithm log without private holdout identifiers."""

    _validate_algorithm_id(algorithm_id)
    if not CREATED_AT_RE.fullmatch(created_at):
        raise SearchIntegrityError(f"created_at must be an RFC3339 UTC timestamp: {created_at}")
    log_path = worktree_root / "LOG.md"
    text = (
        "# CSS Distance Algorithm Experiment\n\n"
        f"- Algorithm: `{algorithm_id}`\n"
        f"- Branch: `{branch}`\n"
        f"- Created: `{created_at}`\n"
        f"- Per-run timeout: `{timeout_seconds}s`\n"
        "- Dataset: private issue #38 holdout. Proposal agents do not receive "
        "selected case ids, answer keys, hidden targets, or witness vectors.\n"
        "- Objective: randomized CSS-distance upper-bound witness search.\n"
    )
    _ensure_public_text(text, label="algorithm log")
    log_path.write_text(text, encoding="utf-8")
    return log_path


def create_css_distance_algorithm_worktree(
    root: Path,
    *,
    algorithm_id: str,
    created_at: str,
    allow_dirty_root: bool,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> CssDistanceExperiment:
    """Create one git worktree and sanitized log for an algorithm attempt."""

    _validate_algorithm_id(algorithm_id)
    root = root.resolve()
    branch = f"autoresearch/css-distance/{algorithm_id}"
    tag = f"css-distance-{algorithm_id}"
    worktree_root = root / ".worktrees" / tag
    branch_ref = f"refs/heads/{branch}"
    if run_git(
        root,
        "branch",
        "--list",
        "--format=%(refname)",
        branch,
    ) == branch_ref:
        raise SearchIntegrityError(f"branch already exists: {branch}")
    if not allow_dirty_root and run_git(root, "status", "--porcelain"):
        raise SearchIntegrityError("root working tree is dirty")
    if worktree_root.exists():
        raise SearchIntegrityError(f"worktree already exists: {worktree_root}")
    worktree_root.parent.mkdir(parents=True, exist_ok=True)
    run_git(root, "worktree", "add", "-b", branch, str(worktree_root), "HEAD")
    write_css_distance_log_header(
        worktree_root,
        algorithm_id=algorithm_id,
        branch=branch,
        created_at=created_at,
        timeout_seconds=timeout_seconds,
    )
    return CssDistanceExperiment(
        algorithm_id=algorithm_id,
        worktree_root=worktree_root,
        branch=branch,
        created_at=created_at,
        timeout_seconds=timeout_seconds,
    )


def build_public_proposal_prompt(
    *,
    research_brief: str,
    source_pin: dict,
) -> str:
    """Build the prompt shown to algorithm proposal agents.

    The prompt is intentionally survey- and baseline-only. It fails closed if
    caller input contains private holdout markers.
    """

    if not isinstance(research_brief, str) or not research_brief.strip():
        raise SearchIntegrityError("research_brief must be non-empty public text")
    _ensure_public_text(research_brief, label="proposal prompt")
    repository = source_pin.get("repository")
    commit = source_pin.get("commit")
    methods = source_pin.get("baseline_methods")
    if (
        not isinstance(repository, str)
        or not repository
        or not isinstance(commit, str)
        or not commit
        or not isinstance(methods, list)
        or not methods
        or any(not isinstance(method, str) or not method for method in methods)
    ):
        raise SearchIntegrityError("source_pin must include repository, commit, and baseline_methods")
    source_text = (
        f"{repository}\n{commit}\n" + "\n".join(sorted(methods))
    )
    _ensure_public_text(source_text, label="proposal source pin")
    return (
        "You are proposing one randomized upper-bound CSS distance algorithm.\n\n"
        "Constraints:\n"
        "- Focus on heuristic/randomized upper-bound witness search for CSS codes.\n"
        "- Do not use exact SAT, MaxSAT, ILP, MIP, or exhaustive exact-distance methods.\n"
        "- A valid result is a verified logical operator witness, not a claim of exact distance.\n"
        "- Write a single `candidate.py` entrypoint.\n\n"
        "Starting implementation:\n"
        f"- Repository: {repository}\n"
        f"- Commit: {commit}\n"
        "- Baseline methods: " + ", ".join(sorted(methods)) + "\n\n"
        "Candidate contract:\n"
        "- Accept `--hx`, `--hz`, `--seed`, and `--output-dir`.\n"
        "- Print exactly one JSON object with keys "
        "`status`, `basis`, `vector`, and `upper_bound`.\n"
        "- When returning a witness, `status` must be exactly `\"completed\"`.\n"
        "- `basis` is `x` or `z`; `vector` is a binary list over physical qubits.\n\n"
        "Public survey brief:\n"
        f"{research_brief.strip()}\n"
    )


def append_sanitized_evaluation_log(
    worktree_root: Path,
    *,
    phase: str,
    summary: dict,
) -> Path:
    """Append a sanitized aggregate result to the algorithm worktree log."""

    sanitized = sanitize_log_summary(summary)
    log_path = worktree_root / "LOG.md"
    lines = [f"\n## {phase.title()} Result\n\n"]
    for key in _LOG_FIELD_ORDER:
        if key in sanitized:
            lines.append(f"- {key}: {sanitized[key]}\n")
    text = "".join(lines)
    _ensure_public_text(text, label="evaluation log")
    _append_text(log_path, text)
    return log_path


def evaluate_css_distance_algorithm(
    *,
    algorithm_id: str,
    candidate_worktree: Path,
    work_root: Path,
    command: Iterable[str],
    phase: str,
    command_builder=None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> CssDistanceEvaluationResult:
    """Run one private phase and append only aggregate metrics to `LOG.md`."""

    _validate_algorithm_id(algorithm_id)
    answers = _load_private_answers(work_root)
    seeds = _phase_seeds(answers, phase)
    cases = _private_cases(answers)
    results = run_private_phase(
        command=tuple(command),
        command_builder=command_builder,
        work_root=work_root,
        phase=phase,
        timeout_seconds=timeout_seconds,
    )
    summary = score_candidate(results, cases, expected_seeds=seeds)
    accepted = (
        not summary.get("disqualified", True)
        and int(summary.get("weighted_target_hits", 0)) > 0
    )
    safe_summary = {
        **summary,
        "accepted": accepted,
        "decision": "accepted" if accepted else "rejected",
    }
    sanitized = sanitize_log_summary(safe_summary)
    append_sanitized_evaluation_log(
        candidate_worktree,
        phase=phase,
        summary=sanitized,
    )
    return CssDistanceEvaluationResult(
        algorithm_id=algorithm_id,
        phase=phase,
        summary=sanitized,
    )
