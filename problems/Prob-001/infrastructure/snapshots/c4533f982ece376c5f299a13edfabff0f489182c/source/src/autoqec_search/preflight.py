from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from math import isfinite
from pathlib import Path
import shutil
import subprocess

from autoqec_search.load import SearchIntegrityError, load_search_workspace


@dataclass(frozen=True)
class PreflightRow:
    status: str
    check: str
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    rows: list[PreflightRow]

    @property
    def is_all_green(self) -> bool:
        return bool(self.rows) and all(row.status == "PASS" for row in self.rows)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _check_workspace(root: Path) -> PreflightRow:
    try:
        workspace = load_search_workspace(root)
    except Exception as exc:
        return PreflightRow("FAIL", "workspace contracts", str(exc))

    return PreflightRow(
        "PASS",
        "workspace contracts",
        (
            f"{len(workspace.campaigns)} campaign(s), "
            f"{len(workspace.tasks)} task(s), "
            f"{len(workspace.decoders)} decoder(s), "
            f"{len(workspace.suites)} suite(s), "
            f"{len(workspace.runs)} run(s)"
        ),
    )


def _check_rsinter() -> PreflightRow:
    rsinter = shutil.which("rsinter")
    if rsinter is None:
        return PreflightRow("FAIL", "rsinter available", "rsinter not found on PATH")

    try:
        result = subprocess.run(
            [rsinter, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError as exc:
        return PreflightRow("FAIL", "rsinter available", str(exc))
    except subprocess.TimeoutExpired:
        return PreflightRow("FAIL", "rsinter available", "rsinter --version timed out")

    version_text = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        return PreflightRow(
            "FAIL",
            "rsinter available",
            f"{rsinter} --version exited {result.returncode}: {version_text}",
        )
    if not version_text:
        return PreflightRow(
            "FAIL",
            "rsinter available",
            "rsinter --version returned empty output",
        )

    return PreflightRow(
        "PASS",
        "rsinter available",
        f"{version_text} at {rsinter}",
    )


def _read_results_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SearchIntegrityError(
                f"{path}:{line_number}: invalid JSONL record: {exc}"
            ) from exc
    if not records:
        raise SearchIntegrityError(f"{path}: no result records")
    return records


def _require_object(record: dict, key: str) -> dict:
    value = record.get(key)
    if not isinstance(value, dict):
        raise SearchIntegrityError(f"invalid {key}: {value}")
    return value


def _require_number(record: dict, key: str) -> float:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SearchIntegrityError(f"invalid {key}: {value}")
    number = float(value)
    if not isfinite(number):
        raise SearchIntegrityError(f"invalid {key}: {value}")
    return number


def _require_integral_number(record: dict, key: str) -> int:
    value = _require_number(record, key)
    if not value.is_integer():
        raise SearchIntegrityError(f"invalid {key}: {record.get(key)}")
    return int(value)


def _verify_fixture_record(record: dict, expected: dict) -> None:
    expected_benchmark = f"autoqec-{expected['task_id']}"
    if record.get("benchmark") != expected_benchmark:
        raise SearchIntegrityError(
            f"benchmark mismatch: {record.get('benchmark')} != {expected_benchmark}"
        )
    if record.get("runner") != expected["decoder_id"]:
        raise SearchIntegrityError(
            f"runner mismatch: {record.get('runner')} != {expected['decoder_id']}"
        )
    if record.get("status") != "ok":
        raise SearchIntegrityError(
            f"fixture result status is not ok: {record.get('status')}"
        )

    params = _require_object(record, "params")
    metrics = _require_object(record, "metrics")
    if params.get("distance") != expected["distance"]:
        raise SearchIntegrityError(
            f"distance mismatch: {params.get('distance')} != {expected['distance']}"
        )
    if params.get("rounds") != expected["rounds"]:
        raise SearchIntegrityError(
            f"rounds mismatch: {params.get('rounds')} != {expected['rounds']}"
        )
    p = _require_number(params, "p")
    if abs(p - expected["p"]) > 1e-15:
        raise SearchIntegrityError(f"p mismatch: {p} != {expected['p']}")

    shots = _require_integral_number(metrics, "shots_used")
    errors = _require_integral_number(metrics, "logical_errors")
    if shots <= 0:
        raise SearchIntegrityError(f"invalid shots: {shots}")
    if errors < 0:
        raise SearchIntegrityError(f"invalid errors: {errors}")
    if errors > shots:
        raise SearchIntegrityError(f"errors exceed shots: {errors} > {shots}")

    if shots != expected["shots"] or errors != expected["errors"]:
        raise SearchIntegrityError(
            f"shot/error mismatch: {shots}/{errors} != "
            f"{expected['shots']}/{expected['errors']}"
        )

    recorded_ler = metrics.get("logical_error_rate")
    expected_ler = expected["logical_error_rate"]
    computed_ler = errors / shots
    if isinstance(recorded_ler, bool) or not isinstance(recorded_ler, int | float):
        raise SearchIntegrityError(f"invalid logical_error_rate: {recorded_ler}")
    if abs(recorded_ler - computed_ler) > 1e-12:
        raise SearchIntegrityError(
            f"recorded LER {recorded_ler} != errors/shots {computed_ler}"
        )
    if abs(recorded_ler - expected_ler) > 1e-12:
        raise SearchIntegrityError(
            f"recorded LER {recorded_ler} != expected {expected_ler}"
        )

    ci = expected["binomial_ci_95"]
    lower = ci["lower"]
    upper = ci["upper"]
    if not lower <= recorded_ler <= upper:
        raise SearchIntegrityError(
            f"recorded LER {recorded_ler} outside CI [{lower}, {upper}]"
        )


def _check_one_fixture(root: Path, entry: dict) -> PreflightRow:
    fixture_id = entry.get("id", "<missing>")
    try:
        fixture_root = root / "benchmarks" / "fixtures"
        results_path = fixture_root / entry["results"]
        expected_path = fixture_root / entry["expected"]
        dem_path = fixture_root / entry["input"]["dem"]

        for label, path in (
            ("results", results_path),
            ("expected", expected_path),
            ("DEM", dem_path),
        ):
            if not path.is_file():
                raise SearchIntegrityError(f"missing {label}: {path}")

        expected = _load_json(expected_path)
        records = _read_results_jsonl(results_path)
        for record in records:
            _verify_fixture_record(record, expected)

    except Exception as exc:
        return PreflightRow("FAIL", f"fixture {fixture_id}", str(exc))

    return PreflightRow(
        "PASS",
        f"fixture {fixture_id}",
        (
            f"{len(records)} result record(s), "
            f"LER={expected['logical_error_rate']}, "
            f"CI=[{expected['binomial_ci_95']['lower']}, "
            f"{expected['binomial_ci_95']['upper']}]"
        ),
    )


def _check_fixtures(root: Path) -> list[PreflightRow]:
    manifest_path = root / "benchmarks" / "fixtures" / "manifest.json"
    if not manifest_path.is_file():
        return [
            PreflightRow(
                "FAIL",
                "fixture manifest",
                f"missing fixture manifest: {manifest_path}",
            )
        ]

    try:
        manifest = _load_json(manifest_path)
        fixtures = manifest["fixtures"]
        if not isinstance(fixtures, list) or not fixtures:
            raise SearchIntegrityError("fixture manifest has no fixtures")
    except Exception as exc:
        return [PreflightRow("FAIL", "fixture manifest", str(exc))]

    rows = [
        PreflightRow("PASS", "fixture manifest", f"{len(fixtures)} fixture(s) declared")
    ]
    rows.extend(_check_one_fixture(root, entry) for entry in fixtures)
    return rows


def run_preflight(root: Path) -> PreflightReport:
    rows = [_check_workspace(root), _check_rsinter()]
    rows.extend(_check_fixtures(root))
    return PreflightReport(rows)


def render_preflight_table(report: PreflightReport) -> str:
    headers = ("STATUS", "CHECK", "DETAIL")
    rows = [(row.status, row.check, row.detail) for row in report.rows]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(3)
    ]
    lines = [
        "  ".join(headers[index].ljust(widths[index]) for index in range(3)),
        "  ".join("-" * width for width in widths),
    ]
    for row in rows:
        lines.append("  ".join(row[index].ljust(widths[index]) for index in range(3)))
    return "\n".join(lines) + "\n"


def write_preflight_html(report: PreflightReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        "<tr>"
        f"<td class='{escape(row.status.lower())}'>{escape(row.status)}</td>"
        f"<td>{escape(row.check)}</td>"
        f"<td>{escape(row.detail)}</td>"
        "</tr>"
        for row in report.rows
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>autoqec-search preflight</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1100px; }}
    th, td {{ border: 1px solid #c7d0d9; padding: 0.55rem 0.7rem; text-align: left; }}
    th {{ background: #eef2f6; }}
    .pass {{ color: #0f6b3d; font-weight: 700; }}
    .warn {{ color: #8a5a00; font-weight: 700; }}
    .fail {{ color: #a51d2d; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>autoqec-search preflight</h1>
  <table>
    <thead><tr><th>Status</th><th>Check</th><th>Detail</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>
</body>
</html>
"""
    output_path.write_text(html)
