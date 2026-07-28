from __future__ import annotations

import json
import math
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from autoqec_search.distance_methods import load_distance_payload
from autoqec_search.load import SearchIntegrityError
from autoqec_search.report import build_report_model


FEEDBACK_SCHEMA_VERSION = 1
REPORT_KIND = "quantum-tanner-ai-feedback"
TARGET_P = 0.001


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(f"invalid {label}: {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} must contain a JSON object: {path}")
    return payload


def _resolve_under_root(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _record_list(payload: dict[str, Any], key: str, *, label: str) -> list[dict[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise SearchIntegrityError(f"{label} {key} must be a list")
    records: list[dict[str, Any]] = []
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise SearchIntegrityError(f"{label} {key}[{index}] must be an object")
        records.append(record)
    return records


def _compact_rejected_proposal(
    record: dict[str, Any],
    *,
    record_kind: str,
) -> dict[str, Any]:
    compact = {"record_kind": record_kind}
    for field in ("proposal_id", "proposal_index", "error_kind", "message", "path"):
        if field in record:
            compact[field] = record[field]
    return compact


def _proposal_summary(
    root: Path,
    path: Path | None,
    candidate_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    if path is None:
        return {}, [], {}

    summary_path = _resolve_under_root(root, path)
    summary = _load_json_object(summary_path, label="proposal summary")
    accepted_by_candidate: dict[str, dict[str, Any]] = {}

    for record in _record_list(
        summary,
        "accepted_records",
        label="proposal summary",
    ):
        mapped_candidate = record.get("candidate_id")
        if mapped_candidate is None:
            proposal_id = record.get("proposal_id")
            if isinstance(proposal_id, str) and proposal_id in candidate_ids:
                mapped_candidate = proposal_id
        if not isinstance(mapped_candidate, str) or mapped_candidate not in candidate_ids:
            raise SearchIntegrityError(
                "proposal feedback candidate mismatch: "
                f"{mapped_candidate!r} is absent from run candidates"
            )
        accepted_by_candidate[mapped_candidate] = record

    rejected_proposals = [
        _compact_rejected_proposal(record, record_kind="rejected")
        for record in _record_list(
            summary,
            "rejected_records",
            label="proposal summary",
        )
    ]
    rejected_proposals.extend(
        _compact_rejected_proposal(record, record_kind="duplicate")
        for record in _record_list(
            summary,
            "duplicate_records",
            label="proposal summary",
        )
    )

    rejection_kinds = Counter(
        str(record["error_kind"])
        for record in rejected_proposals
        if isinstance(record.get("error_kind"), str)
    )
    return accepted_by_candidate, rejected_proposals, dict(sorted(rejection_kinds.items()))


def _candidate_proposal(candidate_payload: dict[str, Any]) -> dict[str, Any]:
    provenance = candidate_payload.get("provenance")
    if not isinstance(provenance, dict):
        return {}
    proposal = provenance.get("proposal")
    return dict(proposal) if isinstance(proposal, dict) else {}


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _validation_status(
    accepted_record: dict[str, Any] | None,
    *,
    proposal_summary_path: Path | None,
) -> str:
    if accepted_record is not None:
        return "accepted"
    if proposal_summary_path is None:
        return "not_provided"
    return "not_in_accepted_summary"


def _target_ler_points(
    report_points: list[dict[str, Any]],
    *,
    candidate_id: str,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for point in report_points:
        if point.get("candidate_id") != candidate_id:
            continue
        p_value = point.get("p")
        if not isinstance(p_value, int | float) or isinstance(p_value, bool):
            continue
        if not math.isclose(float(p_value), TARGET_P, rel_tol=0.0, abs_tol=1e-15):
            continue
        payload: dict[str, Any] = {
            "task_id": point.get("task_id"),
            "decoder_id": point.get("decoder_id"),
            "p": point.get("p"),
            "logical_error_rate": point.get("ler"),
            "shots": point.get("shots"),
            "errors": point.get("errors"),
        }
        for optional_field in ("rounds", "ci_low", "ci_high"):
            if optional_field in point:
                payload[optional_field] = point[optional_field]
        points.append(payload)
    return points


def _surface_rows_by_candidate(
    root: Path,
    surface_copy_path: Path | None,
    candidate_ids: set[str],
) -> dict[str, list[dict[str, Any]]] | None:
    if surface_copy_path is None:
        return None

    payload = _load_json_object(
        _resolve_under_root(root, surface_copy_path),
        label="surface-copy comparison",
    )
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise SearchIntegrityError("surface-copy comparison rows must be a list")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SearchIntegrityError(
                f"surface-copy comparison rows[{index}] must be an object"
            )
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id not in candidate_ids:
            continue
        grouped.setdefault(candidate_id, []).append(row)
    return grouped


def _compact_surface_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "candidate_id"}


def _surface_copy_payload(
    grouped_rows: dict[str, list[dict[str, Any]]] | None,
    *,
    candidate_id: str,
) -> dict[str, Any]:
    if grouped_rows is None:
        return {"status": "not_provided"}
    rows = grouped_rows.get(candidate_id, [])
    if not rows:
        return {"status": "not_found"}
    if len(rows) == 1:
        return _compact_surface_row(rows[0])
    return {
        "status": "multiple",
        "rows": [_compact_surface_row(row) for row in rows],
    }


def _candidate_rejection_reasons(
    *,
    validation_status: str,
    screening_status: Any,
    screening_reason: Any,
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    if validation_status == "not_in_accepted_summary":
        reasons.append(
            {
                "stage": "validation",
                "error_kind": "NotInAcceptedProposalSummary",
                "message": "candidate is absent from accepted proposal summary records",
            }
        )
    if screening_status in {"skipped", "failed"}:
        error_kind = (
            "ScreeningSkipped" if screening_status == "skipped" else "ScreeningFailed"
        )
        reasons.append(
            {
                "stage": "screening",
                "error_kind": error_kind,
                "message": screening_reason,
            }
        )
    return reasons


def _json_for_script(payload: dict[str, Any]) -> str:
    return (
        json.dumps(payload, indent=2, sort_keys=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("=", "\\u003d")
        .replace("/", "\\/")
    )


def _html_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict | list):
        return escape(json.dumps(value, sort_keys=True), quote=True)
    return escape(str(value), quote=True)


def _display_ler(candidate: dict[str, Any]) -> Any:
    points = candidate.get("ler_points")
    if not isinstance(points, list) or not points:
        return None
    first = points[0]
    if not isinstance(first, dict):
        return None
    return first.get("logical_error_rate")


def build_quantum_tanner_ai_feedback(
    root: Path,
    run_root: Path,
    *,
    proposal_summary_path: Path | None = None,
    surface_copy_path: Path | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    run_root = _resolve_under_root(root, Path(run_root)).resolve()

    report_model = build_report_model(root, run_root)
    report_candidates = [
        candidate
        for candidate in report_model.get("candidates", [])
        if isinstance(candidate, dict)
    ]
    candidate_ids = {
        str(candidate["candidate_id"])
        for candidate in report_candidates
        if isinstance(candidate.get("candidate_id"), str)
    }
    accepted_by_candidate, rejected_proposals, rejection_kinds = _proposal_summary(
        root,
        proposal_summary_path,
        candidate_ids,
    )
    surface_rows = _surface_rows_by_candidate(root, surface_copy_path, candidate_ids)

    report_points = [
        point for point in report_model.get("points", []) if isinstance(point, dict)
    ]
    candidates: list[dict[str, Any]] = []
    for report_candidate in report_candidates:
        candidate_id = str(report_candidate["candidate_id"])
        candidate_root = run_root / "candidates" / candidate_id
        candidate_payload = _load_json_object(
            candidate_root / "candidate.json",
            label="candidate",
        )
        proposal = _candidate_proposal(candidate_payload)
        accepted_record = accepted_by_candidate.get(candidate_id)

        validation_status = _validation_status(
            accepted_record,
            proposal_summary_path=proposal_summary_path,
        )
        screening = report_candidate.get("screening")
        if not isinstance(screening, dict):
            screening = {}
        screening_status = screening.get("screening_status")
        screening_reason = screening.get("reason")
        distance_payload = load_distance_payload(candidate_root / "distance.json")
        upper_bound = (
            distance_payload.upper_bound
            if distance_payload.upper_bound is not None
            else distance_payload.distance
        )
        ler_points = _target_ler_points(report_points, candidate_id=candidate_id)
        surface_copy = _surface_copy_payload(surface_rows, candidate_id=candidate_id)

        candidates.append(
            {
                "candidate_id": candidate_id,
                "proposal_id": _first_string(
                    accepted_record.get("proposal_id") if accepted_record else None,
                    proposal.get("proposal_id"),
                    candidate_id,
                ),
                "proposal_fingerprint": _first_string(
                    accepted_record.get("proposal_fingerprint")
                    if accepted_record
                    else None,
                    accepted_record.get("fingerprint") if accepted_record else None,
                    proposal.get("proposal_fingerprint"),
                ),
                "candidate_fingerprint": _first_string(
                    accepted_record.get("candidate_fingerprint")
                    if accepted_record
                    else None,
                    proposal.get("candidate_fingerprint"),
                ),
                "validation_status": validation_status,
                "materialization_status": "present",
                "screening_status": screening_status,
                "screening_reason": screening_reason,
                "n": report_candidate.get("n"),
                "k": report_candidate.get("k"),
                "upper_bound": upper_bound,
                "distance_bound_type": (
                    distance_payload.bound_type
                    if distance_payload.bound_type is not None
                    else report_candidate.get("distance_bound_type")
                ),
                "ler_points": ler_points,
                "surface_copy": surface_copy,
                "rejection_reasons": _candidate_rejection_reasons(
                    validation_status=validation_status,
                    screening_status=screening_status,
                    screening_reason=screening_reason,
                ),
            }
        )

    surface_status_counts = Counter(
        str(candidate["surface_copy"].get("status", "unknown"))
        for candidate in candidates
        if isinstance(candidate.get("surface_copy"), dict)
    )
    validation_status_counts = Counter(
        str(candidate.get("validation_status", "unknown")) for candidate in candidates
    )
    screening_status_counts = Counter(
        str(candidate.get("screening_status", "unknown")) for candidate in candidates
    )
    candidate_ids_with_ler = [
        str(candidate["candidate_id"])
        for candidate in candidates
        if candidate.get("ler_points")
    ]
    p001_ler_rows = sum(
        len(candidate["ler_points"])
        for candidate in candidates
        if isinstance(candidate.get("ler_points"), list)
    )
    candidate_ids_without_ler = [
        str(candidate["candidate_id"])
        for candidate in candidates
        if not candidate.get("ler_points")
    ]

    provenance = report_model.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}

    return {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "run": {
            "campaign_id": provenance.get("campaign_id"),
            "run_id": provenance.get("run_id"),
            "mode": provenance.get("mode"),
            "generated_at": provenance.get("generated_at"),
            "autoqec_version": provenance.get("autoqec_version"),
            "git_sha": provenance.get("git_sha"),
            "branch": provenance.get("branch"),
            "seed": provenance.get("seed"),
            "wall_clock_seconds": provenance.get("wall_clock_seconds"),
        },
        "counts": {
            "candidates": len(candidates),
            "candidates_with_p001_ler": len(candidate_ids_with_ler),
            "p001_ler_rows": p001_ler_rows,
            "rejected_proposals": len(rejected_proposals),
            "surface_copy_status": dict(sorted(surface_status_counts.items())),
            "validation_status": dict(sorted(validation_status_counts.items())),
            "screening_status": dict(sorted(screening_status_counts.items())),
        },
        "candidates": candidates,
        "rejected_proposals": rejected_proposals,
        "next_prompt_context": {
            "target_p": TARGET_P,
            "candidate_ids_with_p001_ler": candidate_ids_with_ler,
            "candidate_ids_without_p001_ler": candidate_ids_without_ler,
            "accepted_proposal_fingerprints": [
                value
                for value in (
                    _first_string(
                        record.get("proposal_fingerprint"),
                        record.get("fingerprint"),
                    )
                    for record in accepted_by_candidate.values()
                )
                if value is not None
            ],
            "rejection_kinds": rejection_kinds,
        },
    }


def render_quantum_tanner_ai_feedback_html(model: dict[str, Any]) -> str:
    json_payload = _json_for_script(model)
    row_lines: list[str] = []
    for candidate in model.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        surface_copy = candidate.get("surface_copy")
        surface_status = (
            surface_copy.get("status")
            if isinstance(surface_copy, dict)
            else "unknown"
        )
        row_lines.append(
            "<tr>"
            f"<td>{_html_cell(candidate.get('candidate_id'))}</td>"
            f"<td>{_html_cell(candidate.get('validation_status'))}</td>"
            f"<td>{_html_cell(candidate.get('screening_status'))}</td>"
            f"<td>{_html_cell(candidate.get('upper_bound'))}</td>"
            f"<td>{_html_cell(_display_ler(candidate))}</td>"
            f"<td>{_html_cell(surface_status)}</td>"
            "</tr>"
        )
    body_rows = "".join(row_lines)
    counts = model.get("counts")
    if not isinstance(counts, dict):
        counts = {}

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC Quantum Tanner AI Feedback</title>
  <style>
    body {{ color: #1f2933; font-family: system-ui, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0 2rem; width: 100%; }}
    th, td {{ border: 1px solid #c7d0d9; padding: 0.4rem 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f6; }}
    code, pre {{ background: #f6f8fa; }}
    pre {{ padding: 1rem; overflow: auto; }}
  </style>
</head>
<body>
  <h1>AutoQEC Quantum Tanner AI Feedback</h1>
  <p>Candidates: <strong>{_html_cell(counts.get('candidates'))}</strong>;
     p=0.001 LER rows: <strong>{_html_cell(counts.get('p001_ler_rows'))}</strong>;
     rejected proposals: <strong>{_html_cell(counts.get('rejected_proposals'))}</strong></p>
  <table>
    <thead>
      <tr>
        <th>Candidate ID</th>
        <th>Validation Status</th>
        <th>Screening Status</th>
        <th>Upper Bound</th>
        <th>p=0.001 Logical Error Rate</th>
        <th>Surface-Copy Status</th>
      </tr>
    </thead>
    <tbody>{body_rows}</tbody>
  </table>
  <h2>Feedback JSON</h2>
  <script type="application/json" id="quantum-tanner-ai-feedback-data">{json_payload}</script>
  <pre>{escape(json_payload)}</pre>
</body>
</html>
"""


def write_quantum_tanner_ai_feedback(
    model: dict[str, Any],
    *,
    out_json: Path,
    out_html: Path,
) -> dict[str, Path]:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    out_html.write_text(render_quantum_tanner_ai_feedback_html(model))
    return {"json": out_json, "html": out_html}
