from __future__ import annotations

import csv
import io

from autoqec_search.decoder_parameters import decoder_parameters_json


def render_summary(campaign: dict, suite: dict, run_spec: dict) -> str:
    lines = [
        "# Search Run Summary",
        "",
        f"- campaign: `{campaign['id']}`",
        f"- suite: `{suite['id']}`",
        f"- run: `{run_spec['run_id']}`",
        f"- mode: `{run_spec['mode']}`",
        f"- candidates: `{len(run_spec['candidate_ids'])}`",
        "",
        "## Tasks",
        "",
    ]
    for task_id in run_spec["task_ids"]:
        lines.append(f"- `{task_id}`")
    lines.extend(["", "## Decoders", ""])
    for decoder_id in run_spec["decoder_ids"]:
        lines.append(f"- `{decoder_id}`")
    return "\n".join(lines).rstrip() + "\n"


def render_leaderboard(manifests: list[dict]) -> str:
    lines = ["candidate_id,task_id,decoder_id,status"]
    for manifest in manifests:
        lines.append(
            ",".join(
                [
                    manifest["candidate_id"],
                    manifest["task_id"],
                    manifest["decoder_id"],
                    manifest["status"],
                ]
            )
        )
    return "\n".join(lines) + "\n"


def render_eval_leaderboard(manifests: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "candidate_id",
            "task_id",
            "decoder_id",
            "decoder_parameters",
            "p",
            "shots",
            "errors",
            "ler",
            "ci_low",
            "ci_high",
            "status",
        ]
    )
    for manifest in manifests:
        if manifest["status"] != "completed":
            continue
        for point in manifest["points"]:
            writer.writerow(
                [
                    manifest["candidate_id"],
                    manifest["task_id"],
                    manifest["decoder_id"],
                    decoder_parameters_json(manifest.get("decoder_parameters", {})),
                    point["p"],
                    point["shots"],
                    point["errors"],
                    point["ler"],
                    point["ci_low"],
                    point["ci_high"],
                    manifest["status"],
                ]
            )
    return output.getvalue()


def render_eval_summary(
    *,
    campaign_id: str,
    run_id: str,
    candidate_id: str,
    task_ids: list[str],
    decoder_ids: list[str],
    deferred_decoder_ids: list[str] | None = None,
    structure: dict,
    distance: int | None,
) -> str:
    distance_text = str(distance) if distance is not None else "unavailable"
    lines = [
        "# Search Eval Summary",
        "",
        f"- campaign: `{campaign_id}`",
        f"- run: `{run_id}`",
        f"- candidate: `{candidate_id}`",
        f"- distance: `{distance_text}`",
        f"- n: `{structure['n']}`",
        f"- k: `{structure['k']}`",
        f"- css_commute: `{str(structure['css_commute']).lower()}`",
        "",
        "## Tasks",
        "",
    ]
    lines.extend(f"- `{task_id}`" for task_id in task_ids)
    lines.extend(["", "## Decoders", ""])
    lines.extend(f"- `{decoder_id}`" for decoder_id in decoder_ids)
    if deferred_decoder_ids:
        lines.extend(["", "## Deferred Decoders", ""])
        lines.extend(f"- `{decoder_id}`" for decoder_id in deferred_decoder_ids)
    return "\n".join(lines).rstrip() + "\n"


def render_run_overview(run_spec: dict, placeholder_count: int) -> str:
    return (
        f"campaign: {run_spec['campaign_id']}\n"
        f"run: {run_spec['run_id']}\n"
        f"suite: {run_spec['suite_id']}\n"
        f"candidates: {len(run_spec['candidate_ids'])}\n"
        f"tasks: {', '.join(run_spec['task_ids'])}\n"
        f"decoders: {', '.join(run_spec['decoder_ids'])}\n"
        f"placeholder manifests: {placeholder_count}\n"
    )


def render_eval_success(candidate_id: str, run_root: object) -> str:
    return f"evaluated candidate {candidate_id} at {run_root}\n"
