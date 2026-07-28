from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from autoqec_search import __version__
from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.render import render_leaderboard, render_summary


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def _resolve_timestamp(timestamp: str | None) -> str:
    if timestamp is not None:
        try:
            datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise SearchIntegrityError(f"invalid timestamp: {timestamp}") from exc
        return timestamp
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _validate_run_id(run_id: str) -> None:
    run_path = Path(run_id)
    if (
        not run_id
        or "/" in run_id
        or "\\" in run_id
        or run_path.name != run_id
        or run_path != Path(run_path.name)
        or run_id in {".", ".."}
    ):
        raise SearchIntegrityError(
            f"run_id must be a single path segment: {run_id}"
        )


def _candidate_ids(search_space: dict) -> list[str]:
    candidate_ids = [
        candidate_spec["candidate_id"]
        for candidate_spec in search_space["candidate_specs"]
    ]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for candidate_id in candidate_ids:
        if candidate_id in seen:
            duplicates.add(candidate_id)
        seen.add(candidate_id)
    if duplicates:
        raise SearchIntegrityError(
            "duplicate candidate_id in search space: "
            + ", ".join(sorted(duplicates))
        )
    return candidate_ids


def init_placeholder_run(
    root: Path,
    campaign_id: str,
    run_id: str,
    *,
    timestamp: str | None = None,
    force: bool = False,
) -> Path:
    workspace = load_search_workspace(root)
    if campaign_id not in workspace.campaigns:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")

    _validate_run_id(run_id)
    campaign = workspace.campaigns[campaign_id]
    search_space = workspace.search_spaces[campaign_id]
    suite = workspace.suites[campaign["default_suite_id"]]
    created_at = _resolve_timestamp(timestamp)
    run_root = root / "results" / "search" / campaign_id / run_id

    if run_root.exists():
        if not force:
            raise SearchIntegrityError(f"run already exists: {run_root}")
        shutil.rmtree(run_root)

    candidate_ids = _candidate_ids(search_space)
    run_spec = {
        "campaign_id": campaign["id"],
        "run_id": run_id,
        "suite_id": suite["id"],
        "task_ids": suite["task_ids"],
        "decoder_ids": suite["decoder_ids"],
        "candidate_ids": candidate_ids,
        "created_at": created_at,
        "mode": "placeholder",
    }

    _write_json(run_root / "run_spec.json", run_spec)
    _write_json(
        run_root / "env.json",
        {
            "tool": "autoqec-search",
            "version": __version__,
            "generated_at": created_at,
            "mode": "placeholder",
        },
    )
    _write_json(
        run_root / "frontier.json",
        {
            "campaign_id": campaign["id"],
            "run_id": run_id,
            "items": [],
        },
    )

    manifests_for_csv: list[dict] = []
    for candidate_spec in search_space["candidate_specs"]:
        candidate_root = run_root / "candidates" / candidate_spec["candidate_id"]
        candidate_payload = {
            "candidate_id": candidate_spec["candidate_id"],
            "campaign_id": campaign["id"],
            "run_id": run_id,
            "code_family": candidate_spec["code_family"],
            "parameters": candidate_spec["parameters"],
            "provenance": candidate_spec["provenance"],
            "status": "placeholder",
        }
        _write_json(candidate_root / "candidate.json", candidate_payload)
        _write_json(
            candidate_root / "structure.json",
            {"status": "not-computed", "n": None, "mx": None, "mz": None},
        )
        _write_json(
            candidate_root / "distance.json",
            {"status": "not-computed", "distance": None},
        )

        for task_id in suite["task_ids"]:
            task = workspace.tasks[task_id]
            for decoder_id in suite["decoder_ids"]:
                manifest = {
                    "campaign_id": campaign["id"],
                    "run_id": run_id,
                    "candidate_id": candidate_spec["candidate_id"],
                    "task_id": task_id,
                    "decoder_id": decoder_id,
                    "status": "placeholder",
                    "metrics": {
                        metric_name: None for metric_name in task["result_metrics"]
                    },
                    "created_at": created_at,
                }
                _write_json(
                    candidate_root
                    / "evaluations"
                    / task_id
                    / decoder_id
                    / "manifest.json",
                    manifest,
                )
                manifests_for_csv.append(manifest)

    _write_text(run_root / "leaderboard.csv", render_leaderboard(manifests_for_csv))
    _write_text(run_root / "summary.md", render_summary(campaign, suite, run_spec))
    return run_root
