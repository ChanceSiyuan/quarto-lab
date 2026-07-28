from __future__ import annotations

import csv
from dataclasses import dataclass
from html import escape
import io
from typing import Literal
from urllib.parse import unquote


Verdict = Literal["keep", "discard", "crash", "skip", "fail"]


@dataclass(frozen=True)
class ExperimentRow:
    candidate_id: str
    ler: float | None
    status: Verdict
    description: str


@dataclass(frozen=True)
class FrontierItem:
    candidate_id: str
    distance: int
    decoder_id: str
    p: float
    ler: float
    manifest_path: str
    distance_bound_type: str = "exact"
    upper_bound: int | None = None


def _format_ler(value: float | None) -> str:
    if value is None:
        return ""
    return format(value, ".12g")


def _safe_relative_href(value: str) -> str | None:
    for candidate in (value, unquote(value)):
        if any(
            character.isspace() or ord(character) < 32 or ord(character) == 127
            for character in candidate
        ):
            return None
        if "\\" in candidate:
            return None
        if candidate.startswith(("/", "//")):
            return None
        if ":" in candidate.split("/", 1)[0]:
            return None
        if ".." in candidate.split("/"):
            return None
    return value


def _md_inline(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = escape(text.replace("`", "'"), quote=False)
    for character in r"\[]()!*_{}#+-.|~>:":
        text = text.replace(character, f"\\{character}")
    return text


def _frontier_distance_label(item: FrontierItem) -> str:
    if item.distance_bound_type == "upper":
        value = item.upper_bound if item.upper_bound is not None else item.distance
        return f"upper_bound={value}"
    return f"d={item.distance}"


def render_experiment_log(rows: list[ExperimentRow]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(["candidate", "ler", "status", "description"])
    for row in rows:
        writer.writerow(
            [row.candidate_id, _format_ler(row.ler), row.status, row.description]
        )
    return output.getvalue()


def render_autoresearch_leaderboard(
    rows: list[ExperimentRow],
    frontier: list[FrontierItem],
) -> str:
    keep_ids = {row.candidate_id for row in rows if row.status == "keep"}
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "candidate_id",
            "distance",
            "distance_bound_type",
            "upper_bound",
            "decoder_id",
            "p",
            "ler",
            "status",
            "manifest_path",
        ]
    )
    for item in sorted(frontier, key=lambda value: (value.distance, value.candidate_id)):
        if item.candidate_id not in keep_ids:
            continue
        writer.writerow(
            [
                item.candidate_id,
                item.distance,
                item.distance_bound_type,
                item.upper_bound if item.upper_bound is not None else "",
                item.decoder_id,
                item.p,
                _format_ler(item.ler),
                "keep",
                item.manifest_path,
            ]
        )
    return output.getvalue()


def render_frontier(
    *,
    campaign_id: str,
    run_id: str,
    items: list[FrontierItem],
) -> dict:
    def item_payload(item: FrontierItem) -> dict[str, object]:
        payload: dict[str, object] = {
            "candidate_id": item.candidate_id,
            "distance": item.distance,
            "decoder_id": item.decoder_id,
            "p": item.p,
            "ler": item.ler,
            "manifest_path": item.manifest_path,
        }
        if item.distance_bound_type != "exact":
            payload["distance_bound_type"] = item.distance_bound_type
        if item.upper_bound is not None:
            payload["upper_bound"] = item.upper_bound
        return payload

    return {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "items": [
            item_payload(item)
            for item in sorted(items, key=lambda value: (value.distance, value.candidate_id))
        ],
    }


def _counts(rows: list[ExperimentRow]) -> dict[str, int]:
    return {
        "keep": sum(1 for row in rows if row.status == "keep"),
        "discard": sum(1 for row in rows if row.status == "discard"),
        "crash": sum(1 for row in rows if row.status == "crash"),
        "skip": sum(1 for row in rows if row.status == "skip"),
        "fail": sum(1 for row in rows if row.status == "fail"),
    }


def render_autoresearch_summary(
    *,
    campaign_id: str,
    run_id: str,
    tag: str,
    wall_clock_seconds: int,
    seed: int,
    rows: list[ExperimentRow],
    frontier: list[FrontierItem],
    strategy: dict | None = None,
    stop_reason: str | None = None,
) -> str:
    counts = _counts(rows)
    lines = [
        "# Autoresearch Run Summary",
        "",
        f"- campaign: `{_md_inline(campaign_id)}`",
        f"- run: `{_md_inline(run_id)}`",
        f"- branch tag: `{_md_inline(tag)}`",
        f"- wall_clock_seconds: `{wall_clock_seconds}`",
        f"- seed: `{seed}`",
    ]
    if strategy is not None:
        lines.append(f"- strategy: `{_md_inline(strategy.get('name', 'unknown'))}`")
        lines.append(f"- strategy_params: `{_md_inline(strategy.get('params', {}))}`")
    if stop_reason is not None:
        lines.append(f"- stop_reason: `{_md_inline(stop_reason)}`")
    lines.extend(
        [
            f"- candidates attempted: `{len(rows)}`",
            f"- keeps: `{counts['keep']}`",
            f"- discards: `{counts['discard']}`",
            f"- crashes: `{counts['crash']}`",
            f"- skips: `{counts['skip']}`",
            f"- fails: `{counts['fail']}`",
            "",
            "## Frontier",
            "",
        ]
    )
    if not frontier:
        lines.append("- empty")
    else:
        for item in sorted(frontier, key=lambda value: (value.distance, value.candidate_id)):
            lines.append(
                "- "
                f"`{_md_inline(item.candidate_id)}` {_frontier_distance_label(item)} "
                f"{_md_inline(item.decoder_id)} p={item.p} LER={_format_ler(item.ler)}"
            )
    lines.extend(["", "## Experiment Log", ""])
    for row in rows:
        ler = _format_ler(row.ler) if row.ler is not None else "n/a"
        lines.append(
            f"- `{_md_inline(row.status)}` `{_md_inline(row.candidate_id)}` "
            f"LER={ler}: {_md_inline(row.description)}"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_run_summary_html(
    *,
    campaign_id: str,
    run_id: str,
    tag: str,
    wall_clock_seconds: int,
    seed: int,
    rows: list[ExperimentRow],
    frontier: list[FrontierItem],
    strategy: dict | None = None,
    stop_reason: str | None = None,
) -> str:
    counts = _counts(rows)

    def manifest_cell(item: FrontierItem) -> str:
        href = _safe_relative_href(item.manifest_path)
        if href is None:
            return f"<span>{escape(item.manifest_path)}</span>"
        return f"<a href='{escape(href, quote=True)}'>manifest</a>"

    timeline = "\n".join(
        "<tr>"
        f"<td>{escape(row.candidate_id)}</td>"
        f"<td class='{escape(row.status)}'>{escape(row.status)}</td>"
        f"<td>{escape(_format_ler(row.ler))}</td>"
        f"<td>{escape(row.description)}</td>"
        "</tr>"
        for row in rows
    )
    frontier_rows = "\n".join(
        "<tr>"
        f"<td>{escape(item.candidate_id)}</td>"
        f"<td>{item.distance}</td>"
        f"<td>{escape(item.distance_bound_type)}</td>"
        f"<td>{item.upper_bound if item.upper_bound is not None else ''}</td>"
        f"<td>{escape(item.decoder_id)}</td>"
        f"<td>{item.p}</td>"
        f"<td>{escape(_format_ler(item.ler))}</td>"
        f"<td>{manifest_cell(item)}</td>"
        "</tr>"
        for item in sorted(frontier, key=lambda value: (value.distance, value.candidate_id))
    )
    if not timeline:
        timeline = "<tr><td colspan='4'>No candidates attempted.</td></tr>"
    if not frontier_rows:
        frontier_rows = "<tr><td colspan='8'>No kept candidates.</td></tr>"
    strategy_rows = ""
    if strategy is not None:
        strategy_rows += (
            f"    <strong>Strategy</strong><span>{escape(str(strategy.get('name', 'unknown')))}</span>\n"
            f"    <strong>Strategy params</strong><span>{escape(str(strategy.get('params', {})))}</span>\n"
        )
    if stop_reason is not None:
        strategy_rows += (
            f"    <strong>Stop reason</strong><span>{escape(stop_reason)}</span>\n"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC autoresearch run {escape(run_id)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1200px; margin: 1rem 0; }}
    th, td {{ border: 1px solid #c7d0d9; padding: 0.45rem 0.6rem; text-align: left; }}
    th {{ background: #eef2f6; }}
    .keep {{ color: #0f6b3d; font-weight: 700; }}
    .discard {{ color: #8a5a00; font-weight: 700; }}
    .crash {{ color: #a51d2d; font-weight: 700; }}
    .skip {{ color: #4b5563; font-weight: 700; }}
    .fail {{ color: #a51d2d; font-weight: 700; }}
    .meta {{ display: grid; grid-template-columns: max-content 1fr; gap: 0.35rem 0.8rem; }}
  </style>
</head>
<body>
  <h1>AutoQEC Autoresearch Run</h1>
  <section class="meta">
    <strong>Campaign</strong><span>{escape(campaign_id)}</span>
    <strong>Run</strong><span>{escape(run_id)}</span>
    <strong>Branch tag</strong><span>{escape(tag)}</span>
    <strong>Wall clock seconds</strong><span>{wall_clock_seconds}</span>
    <strong>Seed</strong><span>{seed}</span>
{strategy_rows.rstrip()}
    <strong>Verdicts</strong><span>{counts['keep']} keep, {counts['discard']} discard, {counts['crash']} crash, {counts['skip']} skip, {counts['fail']} fail</span>
  </section>
  <h2>Timeline</h2>
  <table>
    <thead><tr><th>Candidate</th><th>Status</th><th>LER</th><th>Description</th></tr></thead>
    <tbody>
{timeline}
    </tbody>
  </table>
  <h2>Running Leaderboard</h2>
  <table>
    <thead><tr><th>Candidate</th><th>Screening value</th><th>Bound type</th><th>Upper bound</th><th>Decoder</th><th>p</th><th>LER</th><th>Manifest</th></tr></thead>
    <tbody>
{frontier_rows}
    </tbody>
  </table>
</body>
</html>
"""
