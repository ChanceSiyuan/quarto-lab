from __future__ import annotations

import json
from math import exp, isclose, isfinite
from pathlib import Path
from typing import Any

from autoqec_search.load import SearchIntegrityError


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} must be an object: {path}")
    return payload


def _finite_probability(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SearchIntegrityError(f"{label} must be a probability")
    numeric = float(value)
    if not isfinite(numeric) or not 0 < numeric < 1:
        raise SearchIntegrityError(f"{label} must be a probability")
    return numeric


def _finite_rate(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SearchIntegrityError(f"{label} must be a rate")
    numeric = float(value)
    if not isfinite(numeric) or not 0 <= numeric <= 1:
        raise SearchIntegrityError(f"{label} must be a rate")
    return numeric


def expected_ler_from_table6(
    p: float,
    *,
    d_circ: int,
    c0: float,
    c1: float,
    c2: float,
) -> float:
    return p ** (d_circ / 2) * exp(c0 + c1 * p + c2 * p * p)


def _manifest_path(run_root: Path, fixture: dict[str, Any]) -> Path:
    return (
        run_root
        / "candidates"
        / str(fixture["candidate_id"])
        / "evaluations"
        / str(fixture["task_id"])
        / str(fixture["decoder_id"])
        / "manifest.json"
    )


def _completed_manifest(run_root: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    path = _manifest_path(run_root, fixture)
    manifest = _load_json(path, "reference manifest")
    for key in ("candidate_id", "task_id", "decoder_id"):
        if manifest.get(key) != fixture.get(key):
            raise SearchIntegrityError(f"reference manifest {key} mismatch: {path}")
    if manifest.get("status") != "completed":
        raise SearchIntegrityError(f"reference manifest is not completed: {path}")
    return manifest


def _point_by_p(manifest: dict[str, Any], p: float) -> dict[str, Any]:
    points = manifest.get("points")
    if not isinstance(points, list):
        raise SearchIntegrityError("reference manifest points must be a list")
    for point in points:
        if isinstance(point, dict) and point.get("p") == p:
            return point
    raise SearchIntegrityError(f"missing reference p point: {p:g}")


def _check_point(observed: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    p = _finite_probability(expected.get("p"), label="reference p")
    expected_ler = _finite_probability(
        expected.get("expected_ler"),
        label="expected_ler",
    )
    shots = observed.get("shots")
    if type(shots) is not int or shots <= 0:
        raise SearchIntegrityError("reference check requires positive shots")
    ci_low = _finite_rate(observed.get("ci_low"), label="ci_low")
    ci_high = _finite_rate(observed.get("ci_high"), label="ci_high")
    if ci_low > ci_high:
        raise SearchIntegrityError("reference CI lower bound exceeds upper bound")
    observed_ler = _finite_rate(observed.get("ler"), label="observed ler")
    errors = observed.get("errors")
    if type(errors) is not int or errors < 0 or errors > shots:
        raise SearchIntegrityError("reference observed errors must be valid")
    if not ci_low <= observed_ler <= ci_high:
        raise SearchIntegrityError("reference observed ler outside CI interval")
    computed_ler = errors / shots
    if not isclose(observed_ler, computed_ler, rel_tol=1e-9, abs_tol=1e-12):
        raise SearchIntegrityError(
            f"reference observed ler {observed_ler} != errors/shots {computed_ler}"
        )
    status = "pass" if ci_low <= expected_ler <= ci_high else "fail"
    return {
        "p": p,
        "status": status,
        "expected_ler": expected_ler,
        "observed_ler": observed_ler,
        "observed_ci": {"low": ci_low, "high": ci_high},
        "ci_low": ci_low,
        "ci_high": ci_high,
        "shots": shots,
        "errors": errors,
    }


def evaluate_reference_check(run_root: Path, fixture_path: Path) -> dict[str, Any]:
    run_root = run_root.resolve()
    fixture_path = fixture_path.resolve()
    fixture = _load_json(fixture_path, "reference fixture")
    manifest = _completed_manifest(run_root, fixture)
    fixture_points = fixture.get("points")
    if not isinstance(fixture_points, list) or not fixture_points:
        raise SearchIntegrityError("reference fixture points must be nonempty")
    points = []
    for expected in fixture_points:
        if not isinstance(expected, dict):
            raise SearchIntegrityError("reference fixture point must be an object")
        p = _finite_probability(expected.get("p"), label="reference p")
        points.append(_check_point(_point_by_p(manifest, p), expected))
    status = "pass" if all(point["status"] == "pass" for point in points) else "fail"
    return {
        "status": status,
        "run_root": str(run_root),
        "candidate_id": fixture.get("candidate_id"),
        "task_id": fixture.get("task_id"),
        "decoder_id": fixture.get("decoder_id"),
        "paper_id": fixture.get("paper_id"),
        "distance": fixture.get("distance"),
        "fixture_path": str(fixture_path),
        "reference_formula": fixture.get("reference_formula", {}),
        "source": fixture.get("source", {}),
        "fixture": {
            "path": str(fixture_path),
            "paper_id": fixture.get("paper_id"),
            "reference_formula": fixture.get("reference_formula", {}),
            "source": fixture.get("source", {}),
        },
        "points": points,
    }


def write_reference_check(
    run_root: Path,
    fixture_path: Path,
    output_path: Path | None,
) -> Path:
    payload = evaluate_reference_check(run_root, fixture_path)
    path = output_path or run_root / "reference_check.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path
