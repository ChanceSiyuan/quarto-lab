"""Validated aggregate inputs for the CSS distance results page."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import re
import stat
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path


BASELINE_COLUMNS = (
    (
        "random-window-upper-bound",
        "random_window",
        "random_window_ms",
        "Fast on easy cases; four public-ladder timeouts.",
    ),
    (
        "codedistance/QDistRndMW",
        "codedistance_QDistRndMW",
        "codedistance_QDistRndMW_ms",
        "Random information-set baseline.",
    ),
    (
        "codedistance/QDistEvol",
        "codedistance_QDistEvol",
        "codedistance_QDistEvol_ms",
        "Evolutionary randomized baseline.",
    ),
    (
        "codedistance/decoderDist",
        "codedistance_decoderDist",
        "codedistance_decoderDist_ms",
        "BP-OSD quality-first baseline.",
    ),
)

_DISTANCE_VALUE = re.compile(r"d=(\d+)")
_REPORT_TITLE = re.compile(r"^# CSS Distance Proposal (\d{3}) Report$", re.MULTILINE)
_REPORT_METHOD = re.compile(
    r"^The assigned exploration direction was \*\*(.+?)\*\*\.", re.MULTILINE
)
_REPORT_METRIC = re.compile(r"^\| ([^|]+) \| ([^|]+) \|$", re.MULTILINE)
_PUBLIC_METHOD = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ()+,';\-–—]*")
_MAX_PUBLIC_METHOD_LENGTH = 160
_IMMUTABLE_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_PROPOSAL_DIRECTORY = re.compile(r"css-distance-(?:run100|run200)-proposal-\d{3}")

FORBIDDEN_OUTPUT_MARKERS = (
    "source_case_id",
    "hx_path",
    "hz_path",
    "selection-secret",
    "salt.bin",
    "AutoQEC-private",
    "/Users/",
)

_FORBIDDEN_OUTPUT_PATTERNS = (
    re.compile(r"\b(?:source_)?case(?:[_ -]?(?:id|identifier))?\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(?:split|holdout)(?:[_ -]?(?:id|identifier))?\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(
        r"\bmatrix(?:[_ -]?(?:dimensions?|shape|size))?\s*(?:[:=]\s*|\s+)"
        r"(?:[nmk]\s*=\s*)?\d+(?:\s*(?:x|×|by)\s*\d+)?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bseed(?:s)?(?:[_ -]?(?:id|value))?\s*(?:[:=]\s*|\s+\d+\b)", re.IGNORECASE),
    re.compile(r"\b(?:witness|manifest)(?:[_ -]?(?:path|file|row|id|identifier))\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bwitness\s*(?:[:=]\s*|\[[01]+\])", re.IGNORECASE),
    re.compile(r"\btarget(?:[_ -]?(?:value|distance))?\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(?:private|sealed)[-_A-Za-z0-9]*\.(?:csv|jsonl?|tsv|md|txt|npy|npz|mtx|bin)\b", re.IGNORECASE),
    re.compile(r"(?:^|[\s\"'=])(?:[A-Za-z]:[\\/]|/(?:Users|home|private|tmp|var)/)[^\s\"'<>]*"),
    re.compile(r"\bh[\s_-]?[xz](?:[_ -]?(?:path|file))?\s*[:=]\s*\S+", re.IGNORECASE),
)


@dataclass(frozen=True)
class BaselineRow:
    key: str
    cases: int
    completed: int
    target_hits: int
    timeouts: int
    total_seconds: float
    average_seconds: float
    median_seconds: float
    interpretation: str


@dataclass(frozen=True)
class TrialRow:
    proposal: int
    method: str
    decision: str
    runs: int
    verified: int
    target_hits: int
    timeouts: int
    crashes: int
    invalid_claims: int
    total_seconds: float
    average_seconds: float | None
    median_seconds: float | None
    p95_seconds: float | None
    quality: float
    proposal_image_id: str | None = None
    evaluator_image_id: str | None = None


def load_baseline_rows(csv_path: Path) -> list[BaselineRow]:
    """Aggregate each public baseline method from a validated comparison CSV."""
    with csv_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        required = {"expected"} | {
            column for _, result_column, duration_column, _ in BASELINE_COLUMNS
            for column in (result_column, duration_column)
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("baseline CSV is missing required columns")
        cases = list(reader)

    if not cases:
        raise ValueError("baseline CSV must contain at least one row")

    rows: list[BaselineRow] = []
    for key, result_column, duration_column, interpretation in BASELINE_COLUMNS:
        durations: list[float] = []
        completed = 0
        target_hits = 0
        timeouts = 0
        for case in cases:
            expected = _parse_nonnegative_integer(case["expected"], "expected")
            result = case[result_column]
            duration = _parse_nonnegative_float(case[duration_column], duration_column)
            durations.append(duration / 1000)
            if result == "timeout":
                timeouts += 1
                continue
            match = _DISTANCE_VALUE.fullmatch(result)
            if match is None:
                raise ValueError(f"invalid {result_column} value: {result!r}")
            completed += 1
            if int(match.group(1)) <= expected:
                target_hits += 1
        total_seconds = sum(durations)
        rows.append(
            BaselineRow(
                key=key,
                cases=len(cases),
                completed=completed,
                target_hits=target_hits,
                timeouts=timeouts,
                total_seconds=total_seconds,
                average_seconds=statistics.mean(durations),
                median_seconds=statistics.median(durations),
                interpretation=interpretation,
            )
        )
    return rows


def load_baseline_aggregate_rows(json_path: Path) -> list[BaselineRow]:
    """Load aggregate-only 24-case blinded development baseline rows."""

    return parse_baseline_aggregate_rows_text(
        json_path.read_text(encoding="utf-8")
    )


def parse_baseline_aggregate_rows_text(contents: str) -> list[BaselineRow]:
    """Parse aggregate-only development baseline rows from validated text."""

    if not isinstance(contents, str):
        raise ValueError("baseline aggregate contents must be text")
    payload = json.loads(contents)
    if not isinstance(payload, dict):
        raise ValueError("baseline aggregate must be an object")
    if payload.get("schema_version") != 1:
        raise ValueError("baseline aggregate schema version is unsupported")
    if payload.get("suite") != "css-distance-paper-development":
        raise ValueError("baseline aggregate must target the development suite")
    if payload.get("case_count") != 24:
        raise ValueError("baseline aggregate must contain 24 cases")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("baseline aggregate rows are required")

    by_key = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("baseline aggregate row must be an object")
        key = _require_baseline_key(row.get("key"))
        if key in by_key:
            raise ValueError("duplicate baseline aggregate row")
        cases = _parse_json_nonnegative_integer(row.get("cases"), "cases")
        if cases != 24:
            raise ValueError("baseline aggregate row must contain 24 cases")
        by_key[key] = BaselineRow(
            key=key,
            cases=cases,
            completed=_parse_json_nonnegative_integer(row.get("completed"), "completed"),
            target_hits=_parse_json_nonnegative_integer(row.get("target_hits"), "target_hits"),
            timeouts=_parse_json_nonnegative_integer(row.get("timeouts"), "timeouts"),
            total_seconds=_parse_json_nonnegative_float(row.get("total_seconds"), "total_seconds"),
            average_seconds=_parse_json_nonnegative_float(row.get("average_seconds"), "average_seconds"),
            median_seconds=_parse_json_nonnegative_float(row.get("median_seconds"), "median_seconds"),
            interpretation=_parse_json_text(row.get("interpretation"), "interpretation"),
        )

    expected = [column[0] for column in BASELINE_COLUMNS]
    if set(by_key) != set(expected):
        raise ValueError("baseline aggregate must contain the fixed method set")
    return [by_key[key] for key in expected]


def parse_trial_report(report_path: Path, proposal: int) -> TrialRow:
    """Parse one proposal's aggregate-only Markdown report."""
    try:
        metadata = os.lstat(report_path)
    except OSError as error:
        raise ValueError("report is unavailable or unsafe") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise ValueError("report must be a regular single-link file")
    contents = report_path.read_text(encoding="utf-8")
    return parse_trial_report_text(contents, proposal)


def parse_trial_report_text(contents: str, proposal: int) -> TrialRow:
    """Parse one proposal report from already bounded text input."""

    if not isinstance(contents, str):
        raise ValueError("report contents must be text")
    forbidden = _find_forbidden_output_detail(contents)
    if forbidden is not None:
        raise ValueError(f"forbidden report detail: {forbidden}")
    title = _single_match(_REPORT_TITLE, contents, "numbered report title")
    if int(title.group(1)) != proposal:
        raise ValueError("report proposal number does not match its directory")
    method = _single_match(_REPORT_METHOD, contents, "assigned method").group(1)
    if (
        not method
        or method != method.strip()
        or len(method) > _MAX_PUBLIC_METHOD_LENGTH
        or _PUBLIC_METHOD.fullmatch(method) is None
    ):
        raise ValueError("assigned method is not public-safe")

    metrics: dict[str, str] = {}
    for metric in _REPORT_METRIC.finditer(contents):
        name, value = (part.strip() for part in metric.groups())
        if name in {"Metric", "Field", "---"}:
            continue
        if name in metrics:
            raise ValueError(f"duplicate report metric: {name}")
        metrics[name] = value

    required_metrics = {
        "Decision",
        "Runs",
        "Verified witnesses",
        "Target hits",
        "Timeouts",
        "Crashes",
        "Invalid claims",
        "Normalized quality",
        "Runtime seconds",
    }
    missing = required_metrics - metrics.keys()
    if missing:
        raise ValueError(f"report is missing metrics: {', '.join(sorted(missing))}")

    decision = metrics["Decision"]
    if decision not in {"accepted", "rejected"}:
        raise ValueError("decision must be accepted or rejected")
    runs = _parse_nonnegative_integer(metrics["Runs"], "Runs")
    verified = _parse_nonnegative_integer(metrics["Verified witnesses"], "Verified witnesses")
    target_hits = _parse_nonnegative_integer(metrics["Target hits"], "Target hits")
    timeouts = _parse_nonnegative_integer(metrics["Timeouts"], "Timeouts")
    crashes = _parse_nonnegative_integer(metrics["Crashes"], "Crashes")
    invalid_claims = _parse_nonnegative_integer(metrics["Invalid claims"], "Invalid claims")
    quality = _parse_nonnegative_float(metrics["Normalized quality"], "Normalized quality")
    total_seconds = _parse_nonnegative_float(metrics["Runtime seconds"], "Runtime seconds")
    proposal_image_id: str | None = None
    evaluator_image_id: str | None = None
    if proposal > 100:
        required_metrics.update(
            {
                "Proposal total",
                "Branch",
                "Public contract status",
                "Timeout seconds",
                "Proposal image ID",
                "Evaluator image ID",
            }
        )
        missing = required_metrics - metrics.keys()
        if missing:
            raise ValueError(f"report is missing metrics: {', '.join(sorted(missing))}")
        if _parse_nonnegative_integer(metrics["Proposal total"], "Proposal total") != 200:
            raise ValueError("new report proposal total must be exactly 200")
        if _parse_nonnegative_integer(metrics["Timeout seconds"], "Timeout seconds") != 300:
            raise ValueError("new report timeout seconds must be exactly 300")
        expected_branch = f"autoresearch/css-distance/run200-proposal-{proposal:03d}"
        if metrics["Branch"] != expected_branch:
            raise ValueError("new report branch is invalid")
        if metrics["Public contract status"] not in {"passed", "failed"}:
            raise ValueError("new report public contract status is invalid")
        proposal_image_id = metrics["Proposal image ID"]
        evaluator_image_id = metrics["Evaluator image ID"]
        if (
            _IMMUTABLE_IMAGE_ID.fullmatch(proposal_image_id) is None
            or _IMMUTABLE_IMAGE_ID.fullmatch(evaluator_image_id) is None
            or proposal_image_id == evaluator_image_id
        ):
            raise ValueError("new report image evidence is invalid")
        timing_metrics = ("Average seconds", "Median seconds", "P95 seconds")
        missing_timing = set(timing_metrics) - metrics.keys()
        if missing_timing:
            raise ValueError(f"new report is missing timing metrics: {', '.join(sorted(missing_timing))}")
        if runs == 0:
            if any(metrics[name] != "not run" for name in timing_metrics):
                raise ValueError("zero-run new report timing metrics must be literal not run")
            average_seconds = None
            median_seconds = None
            p95_seconds = None
        else:
            average_seconds = _parse_nonnegative_float(metrics["Average seconds"], "Average seconds")
            median_seconds = _parse_nonnegative_float(metrics["Median seconds"], "Median seconds")
            p95_seconds = _parse_nonnegative_float(metrics["P95 seconds"], "P95 seconds")
    else:
        average_seconds = total_seconds / runs if runs else None
        median_seconds = None
        p95_seconds = None

    row = TrialRow(
        proposal=proposal,
        method=method,
        decision=decision,
        runs=runs,
        verified=verified,
        target_hits=target_hits,
        timeouts=timeouts,
        crashes=crashes,
        invalid_claims=invalid_claims,
        total_seconds=total_seconds,
        average_seconds=average_seconds,
        median_seconds=median_seconds,
        p95_seconds=p95_seconds,
        quality=quality,
        proposal_image_id=proposal_image_id,
        evaluator_image_id=evaluator_image_id,
    )
    if proposal > 100:
        _validate_new_trial_row(row)
    return row


def proposal_directory_name(proposal: int) -> str:
    """Return the public worktree name for a numbered CSS distance proposal."""
    prefix = "run100" if proposal <= 100 else "run200"
    return f"css-distance-{prefix}-proposal-{proposal:03d}"


def load_trial_rows(reports_root: Path, *, target_proposals: int = 200) -> list[TrialRow]:
    """Require 001–100 and a contiguous prefix of 101–target_proposals."""
    if not 100 <= target_proposals <= 999:
        raise ValueError("target proposals must be between 100 and 999")
    legacy = {proposal_directory_name(proposal) for proposal in range(1, 101)}
    found = {
        entry.name
        for entry in reports_root.iterdir()
        if entry.is_dir() and _PROPOSAL_DIRECTORY.fullmatch(entry.name)
    }
    new_proposals = [
        proposal
        for proposal in range(101, target_proposals + 1)
        if proposal_directory_name(proposal) in found
    ]
    completed_proposals = max(new_proposals, default=100)
    expected = legacy | {
        proposal_directory_name(proposal) for proposal in range(101, completed_proposals + 1)
    }
    if found != expected:
        missing = sorted(expected - found)
        extra = sorted(found - expected)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"extra: {', '.join(extra)}")
        raise ValueError(
            "proposal worktrees must contain 001 through 100 and a contiguous new prefix "
            f"({'; '.join(details)})"
        )

    rows = []
    for proposal in range(1, completed_proposals + 1):
        directory = reports_root / proposal_directory_name(proposal)
        rows.append(parse_trial_report(directory / "REPORT.md", proposal))
    return rows


def render_results_page(baselines: list[BaselineRow], trials: list[TrialRow]) -> str:
    """Render the aggregate-only, standalone CSS distance results page."""
    _validate_render_rows(baselines, trials)
    baseline_rows = "\n".join(_render_baseline_row(row) for row in baselines)
    new_leader = _new_batch_leader(trials)
    trial_rows = "\n".join(
        _render_trial_row(
            row,
            badge=(
                "001–100 fastest perfect"
                if row.proposal == 20
                else _new_leader_badge(row, new_leader, trials)
            ),
        )
        for row in trials
    )
    baseline_case_count = baselines[0].cases
    completed_trials = len(trials)
    refresh_tag = '<meta http-equiv="refresh" content="15">\n' if completed_trials < 200 else ""
    baseline_note = (
        "Blinded 24-instance development split. Timeout durations are included in total, average, and median runtime."
        if baseline_case_count == 24
        else "Public 19-instance ladder. Timeout durations are included in total, average, and median runtime."
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{refresh_tag}<title>CSS distance autoresearch results</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #14233b; background: #f4f1ea; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f4f1ea; color: #14233b; line-height: 1.5; }}
main {{ max-width: 1440px; margin: 0 auto; padding: 2.5rem clamp(1rem, 3vw, 3rem); }}
.report-header {{ max-width: 55rem; margin-bottom: 2.5rem; }}
.eyebrow {{ margin: 0; color: #24766c; font-size: .82rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }}
h1, h2 {{ color: #14233b; line-height: 1.15; }}
h1 {{ margin: .35rem 0 .75rem; font-size: clamp(2rem, 4vw, 3.25rem); }}
h2 {{ margin: 0; font-size: 1.35rem; }}
.lede {{ margin: 0; font-size: 1.05rem; }}
section {{ margin-top: 2.5rem; }}
.section-note {{ margin: .45rem 0 1rem; color: #43536a; }}
.section-heading {{ display: flex; align-items: end; justify-content: space-between; gap: 1rem; }}
#visible-count {{ color: #43536a; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.toolbar {{ display: flex; flex-wrap: wrap; align-items: center; gap: .65rem; margin: 1rem 0; }}
input, button {{ font: inherit; }}
input {{ min-width: min(20rem, 100%); padding: .45rem .6rem; border: 1px solid #9ba8b7; border-radius: .2rem; background: #fff; color: #14233b; }}
button {{ padding: .42rem .7rem; border: 1px solid #708096; border-radius: .2rem; background: #fff; color: #14233b; cursor: pointer; }}
button[aria-pressed="true"] {{ border-color: #24766c; background: #24766c; color: #fff; }}
:focus-visible {{ outline: 3px solid #24766c; outline-offset: 2px; }}
.table-shell {{ overflow-x: auto; border: 1px solid #d5d8dc; border-radius: .35rem; background: #fff; box-shadow: 0 1px 2px rgb(20 35 59 / 8%); }}
table {{ width: 100%; min-width: 880px; border-collapse: collapse; background: #fff; font-variant-numeric: tabular-nums; }}
#trials-table {{ min-width: 1280px; }}
th, td {{ padding: .65rem .75rem; border-bottom: 1px solid #e2e5e8; text-align: left; vertical-align: top; }}
thead th {{ position: sticky; top: 0; z-index: 1; background: #14233b; color: #fff; font-size: .82rem; font-weight: 700; letter-spacing: .02em; white-space: nowrap; }}
thead th button {{ display: block; width: 100%; padding: 0; border: 0; background: transparent; color: inherit; font: inherit; font-weight: inherit; letter-spacing: inherit; text-align: inherit; cursor: pointer; }}
tbody tr:last-child td {{ border-bottom: 0; }}
.numeric {{ text-align: right; }}
.decision-accepted {{ color: #24766c; font-weight: 700; }}
.decision-rejected {{ color: #a04444; font-weight: 700; }}
tr:has(.winner-badge) td {{ background: #fff8e8; }}
tr:has(.winner-badge) td:first-child {{ border-left: .35rem solid #c58a18; }}
.winner-badge {{ display: inline-block; margin-top: .2rem; padding: .12rem .4rem; border-radius: 999px; background: #c58a18; color: #14233b; font-size: .72rem; font-weight: 800; white-space: nowrap; }}
footer {{ margin-top: 2.5rem; color: #43536a; font-size: .9rem; }}
@media (max-width: 640px) {{ main {{ padding: 1.5rem 1rem; }} .section-heading {{ align-items: start; flex-direction: column; }} input {{ min-width: 0; width: 100%; }} }}
</style>
</head>
<body>
<main>
<header class="report-header">
  <p class="eyebrow">AutoQEC · CSS distance autoresearch</p>
  <h1>Randomized upper-bound benchmark results</h1>
  <p class="lede">Verified logical operators certify upper bounds only. They do not establish exact code distance.</p>
</header>
<section aria-labelledby="baseline-title">
  <h2 id="baseline-title">Open-source implementation comparison</h2>
  <p class="section-note">{baseline_note}</p>
  <div class="table-shell">
    <table id="baseline-table">
      <thead><tr>{_header_cells(("Implementation", "Cases", "Completed", "Target hits", "Timed out", "Total", "Average", "Median", "Interpretation"), ("text", "number", "number", "number", "number", "number", "number", "number", "text"))}</tr></thead>
      <tbody>{baseline_rows}</tbody>
    </table>
  </div>
</section>
<section aria-labelledby="trials-title">
  <div class="section-heading">
    <div><h2 id="trials-title">All 200 proposal trials</h2><p class="section-note">Legacy trials did not retain per-invocation quantiles. New evaluated trials include median and P95; new zero-run trials are marked not run.</p></div>
    <output id="visible-count">{completed_trials} / 200 trials completed</output>
  </div>
  <div class="toolbar">
    <label for="trial-search">Search</label>
    <input id="trial-search" type="search" autocomplete="off">
    <div role="group" aria-label="Filter by decision">
      <button type="button" data-decision-filter="all" aria-pressed="true">All</button>
      <button type="button" data-decision-filter="accepted" aria-pressed="false">Accepted</button>
      <button type="button" data-decision-filter="rejected" aria-pressed="false">Rejected</button>
    </div>
  </div>
  <div class="table-shell trial-shell">
    <table id="trials-table">
      <thead><tr>{_header_cells(("Proposal", "Method", "Decision", "Runs", "Verified", "Hits", "Timeouts", "Crashes", "Invalid", "Total", "Average", "Median", "P95", "Quality"), ("number", "text", "text", "number", "number", "number", "number", "number", "number", "number", "number", "number", "number", "number"))}</tr></thead>
      <tbody>{trial_rows}</tbody>
    </table>
  </div>
</section>
<footer>Aggregate baseline and proposal-report results. Each invocation has a 300-second limit. The sealed final holdout was not evaluated.</footer>
</main>
<script>
(() => {{
  const sortableTables = document.querySelectorAll("table");
  sortableTables.forEach((table) => {{
    const headers = table.querySelectorAll("thead th");
    const buttons = table.querySelectorAll("thead th > button");
    const sort = (header) => {{
      const index = Number(header.dataset.column);
      const type = header.dataset.type;
      const nextDirection = header.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
      headers.forEach((item) => item.setAttribute("aria-sort", item === header ? nextDirection : "none"));
      const rows = Array.from(table.tBodies[0].rows);
      rows.sort((left, right) => {{
        const a = left.cells[index].dataset.sortValue || left.cells[index].textContent.trim();
        const b = right.cells[index].dataset.sortValue || right.cells[index].textContent.trim();
        const compared = type === "number" ? Number(a) - Number(b) : a.localeCompare(b);
        return nextDirection === "ascending" ? compared : -compared;
      }});
      rows.forEach((row) => table.tBodies[0].append(row));
    }};
    buttons.forEach((button) => button.addEventListener("click", () => sort(button.parentElement)));
  }});
  const search = document.getElementById("trial-search");
  const filterButtons = document.querySelectorAll("[data-decision-filter]");
  const count = document.getElementById("visible-count");
  const trialRows = document.querySelectorAll(".trial-row");
  const completedTrials = {completed_trials};
  let decision = "all";
  const updateRows = () => {{
    const query = search.value.trim().toLowerCase();
    let visible = 0;
    trialRows.forEach((row) => {{
      const matchesQuery = row.dataset.proposal.includes(query) || row.dataset.method.includes(query);
      const matchesDecision = decision === "all" || row.dataset.decision === decision;
      const show = matchesQuery && matchesDecision;
      row.hidden = !show;
      if (show) visible += 1;
    }});
    count.textContent = `${{visible}} of ${{completedTrials}} / 200 trials completed`;
  }};
  search.addEventListener("input", updateRows);
  filterButtons.forEach((button) => button.addEventListener("click", () => {{
    decision = button.dataset.decisionFilter;
    filterButtons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
    updateRows();
  }}));
}})();
</script>
</body>
</html>
"""


def write_results_page(
    baselines: list[BaselineRow], trials: list[TrialRow], output_path: Path
) -> Path:
    """Atomically write a privacy-scanned standalone results page."""
    rendered = render_results_page(baselines, trials)
    forbidden_detail = _find_forbidden_output_detail(rendered)
    if forbidden_detail is not None:
        raise ValueError(f"forbidden output marker: {forbidden_detail}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary.write(rendered)
            temporary_path = Path(temporary.name)
        temporary_path.replace(output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return output_path


def _validate_render_rows(baselines: list[BaselineRow], trials: list[TrialRow]) -> None:
    expected_baseline_keys = tuple(column[0] for column in BASELINE_COLUMNS)
    if tuple(row.key for row in baselines) != expected_baseline_keys:
        raise ValueError("results page requires the fixed baseline key sequence")
    case_counts = {row.cases for row in baselines}
    if case_counts not in ({19}, {24}):
        raise ValueError("results page requires a complete 24-case development baseline or 19-case public ladder")
    if case_counts == {19} and baselines[0].timeouts != 4:
        raise ValueError("random-window narrative requires exactly four timeouts")
    expected_proposals = list(range(1, len(trials) + 1))
    if not 100 <= len(trials) <= 200:
        raise ValueError("results page requires between 100 and 200 proposals")
    if sorted(row.proposal for row in trials) != expected_proposals:
        raise ValueError("results page requires a contiguous proposal range starting at 001")
    if any(row.decision not in {"accepted", "rejected"} for row in trials):
        raise ValueError("trial decision must be accepted or rejected")
    if any(_PUBLIC_METHOD.fullmatch(row.method) is None for row in trials):
        raise ValueError("trial method contains forbidden source-like text")
    legacy_rows = [row for row in trials if row.proposal <= 100]
    if any(row.median_seconds is not None or row.p95_seconds is not None for row in legacy_rows):
        raise ValueError("legacy trial quantiles must remain unavailable")
    for row in (row for row in trials if row.proposal > 100):
        _validate_new_trial_row(row)

    proposal_020 = next(row for row in trials if row.proposal == 20)
    if not _is_expected_winner(proposal_020):
        raise ValueError("proposal 020 does not support its fastest-perfect badge")


def _is_expected_winner(row: TrialRow) -> bool:
    return (
        row.decision == "accepted"
        and row.runs == 24
        and row.verified == 24
        and row.target_hits == 24
        and row.timeouts == 0
        and row.crashes == 0
        and row.invalid_claims == 0
    )


def _is_perfect_trial(row: TrialRow) -> bool:
    return (
        row.runs == 24
        and row.verified == 24
        and row.target_hits == 24
        and row.timeouts == 0
        and row.crashes == 0
        and row.invalid_claims == 0
    )


def _validate_new_trial_row(row: TrialRow) -> None:
    if row.runs == 0:
        if row.decision != "rejected":
            raise ValueError("zero-run new trial must be rejected")
        if any(value != 0 for value in (row.verified, row.target_hits, row.timeouts, row.crashes)):
            raise ValueError("zero-run new trial counts must be zero")
        if row.invalid_claims < 1:
            raise ValueError("zero-run new trial must record an invalid claim")
        if row.total_seconds != 0 or row.quality != 0:
            raise ValueError("zero-run new trial aggregate values must be zero")
        if any(value is not None for value in (row.average_seconds, row.median_seconds, row.p95_seconds)):
            raise ValueError("zero-run new trial timing values must be unavailable")
        return
    if row.runs != 24:
        raise ValueError("new trial runs must be exactly 24 or zero")
    if any(type(value) is not int or value < 0 for value in (
        row.verified,
        row.target_hits,
        row.timeouts,
        row.crashes,
        row.invalid_claims,
    )):
        raise ValueError("new trial counts must be nonnegative integers")
    if row.verified + row.timeouts + row.crashes + row.invalid_claims != 24:
        raise ValueError("new trial outcomes must account for all 24 runs")
    if not row.target_hits <= row.verified <= 24:
        raise ValueError("new trial hits and verified counts are inconsistent")
    accepted = row.invalid_claims == 0 and row.target_hits > 0
    if row.decision != ("accepted" if accepted else "rejected"):
        raise ValueError("new trial decision is inconsistent with its aggregate")
    timing_values = (row.average_seconds, row.median_seconds, row.p95_seconds)
    if any(value is None for value in timing_values):
        raise ValueError("evaluated new trial timing values are required")
    average_seconds, median_seconds, p95_seconds = timing_values
    numeric_values = (row.total_seconds, row.quality, average_seconds, median_seconds, p95_seconds)
    if any(
        type(value) not in {int, float} or not math.isfinite(value) or value < 0
        for value in numeric_values
    ):
        raise ValueError("new trial aggregate values must be finite and nonnegative")
    if row.quality > 1:
        raise ValueError("new trial quality must not exceed one")
    if not math.isclose(average_seconds, row.total_seconds / row.runs, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("new trial average seconds is inconsistent with total runtime")
    if row.total_seconds > row.runs * 300:
        raise ValueError("new trial total runtime exceeds the fixed timeout budget")
    if row.total_seconds < 300 * row.timeouts:
        raise ValueError("new trial total runtime is shorter than its timeouts")
    if not median_seconds <= p95_seconds <= row.total_seconds:
        raise ValueError("new trial timing quantiles are inconsistent")
    if median_seconds > 300 or p95_seconds > 300:
        raise ValueError("new trial timing quantiles exceed the fixed timeout")
    if row.timeouts >= 2 and not math.isclose(p95_seconds, 300, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("new trial P95 must equal the timeout with two or more timeouts")


def _new_batch_leader(trials: list[TrialRow]) -> TrialRow | None:
    new_rows = [
        row for row in trials if row.proposal > 100 and row.decision == "accepted" and row.runs == 24
    ]
    if not new_rows:
        return None
    return max(
        new_rows,
        key=lambda row: (
            row.target_hits,
            row.quality,
            row.verified,
            -row.total_seconds,
            -row.proposal,
        ),
    )


def _new_leader_badge(
    row: TrialRow, new_leader: TrialRow | None, trials: list[TrialRow]
) -> str | None:
    if row != new_leader:
        return None
    proposal_020 = next(trial for trial in trials if trial.proposal == 20)
    if _is_perfect_trial(row) and row.total_seconds < proposal_020.total_seconds:
        return "new overall leader"
    return "101–200 leader"


def _render_baseline_row(row: BaselineRow) -> str:
    cells = (
        _text_cell(row.key),
        _number_cell(row.cases),
        _number_cell(row.completed),
        _number_cell(row.target_hits),
        _number_cell(row.timeouts),
        _seconds_cell(row.total_seconds),
        _seconds_cell(row.average_seconds),
        _seconds_cell(row.median_seconds),
        _text_cell(row.interpretation),
    )
    return f'<tr class="baseline-row">{"".join(cells)}</tr>'


def _render_trial_row(row: TrialRow, *, badge: str | None) -> str:
    proposal = f"{row.proposal:03d}"
    highlight = badge is not None
    row_class = "trial-row trial-highlight" if highlight else "trial-row"
    badge_html = f'<span class="winner-badge">{html.escape(badge)}</span>' if badge else ""
    missing_timing_label = "legacy not recorded" if row.proposal <= 100 else "not run"
    cells = (
        f'<td data-sort-value="{row.proposal}">{proposal}{badge_html}</td>',
        _text_cell(row.method),
        _text_cell(row.decision, class_name=f"decision-{row.decision}"),
        _number_cell(row.runs),
        _number_cell(row.verified),
        _number_cell(row.target_hits),
        _number_cell(row.timeouts),
        _number_cell(row.crashes),
        _number_cell(row.invalid_claims),
        _seconds_cell(row.total_seconds),
        _seconds_cell(row.average_seconds, missing_label=missing_timing_label),
        _seconds_cell(row.median_seconds, missing_label=missing_timing_label),
        _seconds_cell(row.p95_seconds, missing_label=missing_timing_label),
        _number_cell(row.quality, decimals=3),
    )
    return (
        f'<tr class="{row_class}" data-proposal="{proposal}" '
        f'data-method="{html.escape(row.method, quote=True).lower()}" '
        f'data-decision="{html.escape(row.decision, quote=True)}">{"".join(cells)}</tr>'
    )


def _header_cells(labels: tuple[str, ...], types: tuple[str, ...]) -> str:
    return "".join(
        f'<th scope="col" data-column="{index}" data-type="{sort_type}" '
        f'aria-sort="none"><button type="button">{html.escape(label)}</button></th>'
        for index, (label, sort_type) in enumerate(zip(labels, types, strict=True))
    )


def _text_cell(value: str, *, class_name: str = "") -> str:
    class_attribute = f' class="{html.escape(class_name, quote=True)}"' if class_name else ""
    return f"<td{class_attribute}>{html.escape(value)}</td>"


def _number_cell(value: int | float, *, decimals: int = 0) -> str:
    formatted = f"{value:.{decimals}f}" if decimals else str(value)
    return f'<td class="numeric" data-sort-value="{value}">{formatted}</td>'


def _seconds_cell(value: float | None, *, missing_label: str = "—") -> str:
    if value is None:
        return f'<td class="numeric" data-sort-value="-Infinity">{html.escape(missing_label)}</td>'
    return f'<td class="numeric" data-sort-value="{value}">{value:.3f} s</td>'


def _find_forbidden_output_detail(rendered: str) -> str | None:
    normalized = rendered.casefold()
    for marker in (*FORBIDDEN_OUTPUT_MARKERS, "http://", "https://"):
        if marker.casefold() in normalized:
            return "literal privacy marker"
    for pattern in _FORBIDDEN_OUTPUT_PATTERNS:
        match = pattern.search(rendered)
        if match is not None:
            return "structured private detail"
    return None


def _single_match(pattern: re.Pattern[str], contents: str, description: str) -> re.Match[str]:
    matches = list(pattern.finditer(contents))
    if len(matches) != 1:
        raise ValueError(f"report must contain exactly one {description}")
    return matches[0]


def _parse_nonnegative_integer(value: str, label: str) -> int:
    if not re.fullmatch(r"\d+", value):
        raise ValueError(f"{label} must be a nonnegative integer")
    return int(value)


def _parse_nonnegative_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a nonnegative number") from error
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{label} must be a nonnegative number")
    return parsed


def _require_baseline_key(value: object) -> str:
    if not isinstance(value, str) or value not in {column[0] for column in BASELINE_COLUMNS}:
        raise ValueError("invalid baseline aggregate key")
    return value


def _parse_json_nonnegative_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return int(value)


def _parse_json_nonnegative_float(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be a nonnegative number")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{label} must be a nonnegative number")
    return parsed


def _parse_json_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty string")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the standalone page generator."""
    parser = argparse.ArgumentParser(description="Generate CSS distance results page")
    baseline_source = parser.add_mutually_exclusive_group(required=True)
    baseline_source.add_argument("--baseline-csv", type=Path)
    baseline_source.add_argument("--baseline-aggregate", type=Path)
    parser.add_argument("--reports-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Generate the validated, offline CSS distance results page."""
    args = build_parser().parse_args(argv)
    baselines = (
        load_baseline_aggregate_rows(args.baseline_aggregate)
        if args.baseline_aggregate is not None
        else load_baseline_rows(args.baseline_csv)
    )
    trials = load_trial_rows(args.reports_root)
    write_results_page(baselines, trials, args.output)
    print("wrote CSS distance results page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
