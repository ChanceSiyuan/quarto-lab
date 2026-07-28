from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.cli import main
from autoqec_search.load import SearchIntegrityError
from autoqec_search.reference_check import (
    evaluate_reference_check,
    expected_ler_from_table6,
    write_reference_check,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _manifest_root(
    tmp_path: Path,
    *,
    ci_low: float,
    ci_high: float,
    shots: int = 1000,
    point_overrides: dict | None = None,
) -> Path:
    run_root = tmp_path / "run"
    manifest_path = (
        run_root
        / "candidates"
        / "bivariate-bicycle-code-m6-n6"
        / "evaluations"
        / "bb-css-memory-x-cdep-v1"
        / "rbposd-bb72-osd1-v1"
        / "manifest.json"
    )
    point = {
        "p": 0.003,
        "rounds": 3,
        "shots": shots,
        "errors": 5,
        "ler": 0.005,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "seconds": 0.01,
    }
    if point_overrides:
        point.update(point_overrides)
    _write_json(
        manifest_path,
        {
            "campaign_id": "bb72-qldpc-campaign",
            "run_id": "reference-fixture",
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "task_id": "bb-css-memory-x-cdep-v1",
            "decoder_id": "rbposd-bb72-osd1-v1",
            "status": "completed",
            "created_at": "2026-06-18T00:00:00Z",
            "tool_revisions": {"autoqec_search": "0.1.0", "rsinter": "fake"},
            "points": [point],
        },
    )
    return run_root


def _fixture(tmp_path: Path) -> Path:
    path = tmp_path / "expected.json"
    _write_json(
        path,
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "decoder_id": "rbposd-bb72-osd1-v1",
            "task_id": "bb-css-memory-x-cdep-v1",
            "paper_id": "2308.07915",
            "distance": 6,
            "reference_formula": {
                "d_circ": 6,
                "c0": 11.09,
                "c1": 365.6,
                "c2": -16088,
                "form": "p^(d_circ/2) * exp(c0 + c1*p + c2*p^2)",
            },
            "points": [{"p": 0.003, "expected_ler": 0.004582883142537217}],
            "source": {
                "distance_evidence": "zoo/evidence/2308.07915/bivariate-bicycle-code.distance-claim.01.json",
                "parameter_evidence": "zoo/evidence/2308.07915/bivariate-bicycle-code.parameter-claim.01.json",
                "threshold_evidence": "zoo/evidence/2308.07915/bivariate-bicycle-code.threshold-evidence.01.json",
            },
        },
    )
    return path


def test_expected_ler_from_table6_matches_rounded_table6_formula() -> None:
    assert expected_ler_from_table6(
        0.003,
        d_circ=6,
        c0=11.09,
        c1=365.6,
        c2=-16088,
    ) == pytest.approx(0.004582910643888499)
    assert expected_ler_from_table6(
        0.01,
        d_circ=6,
        c0=11.09,
        c1=365.6,
        c2=-16088,
    ) == pytest.approx(0.5074736158125863)


def test_committed_bb72_reference_fixture_records_table6_values() -> None:
    fixture = json.loads(
        (
            REPO_ROOT
            / "benchmarks"
            / "fixtures"
            / "bb72-reference"
            / "expected.json"
        ).read_text()
    )

    assert fixture["candidate_id"] == "bivariate-bicycle-code-m6-n6"
    assert fixture["decoder_id"] == "rbposd-bb72-osd10-v1"
    assert fixture["task_id"] == "bb-css-memory-x-cdep-v1"
    assert fixture["paper_id"] == "2308.07915"
    assert fixture["distance"] == 6
    assert fixture["reference_formula"] == {
        "c0": 11.09,
        "c1": 365.6,
        "c2": -16088,
        "d_circ": 6,
        "form": "p^(d_circ/2) * exp(c0 + c1*p + c2*p^2)",
    }
    assert fixture["points"] == [
        {"expected_ler": 0.004582883142537217, "p": 0.003},
        {"expected_ler": 0.5074729501581476, "p": 0.01},
    ]


def test_reference_check_passes_when_expected_ler_is_inside_ci(tmp_path: Path) -> None:
    run_root = _manifest_root(tmp_path, ci_low=0.001, ci_high=0.01)

    result = evaluate_reference_check(run_root, _fixture(tmp_path))

    assert result["status"] == "pass"
    assert result["candidate_id"] == "bivariate-bicycle-code-m6-n6"
    assert result["decoder_id"] == "rbposd-bb72-osd1-v1"
    assert result["task_id"] == "bb-css-memory-x-cdep-v1"
    assert result["paper_id"] == "2308.07915"
    assert result["points"][0]["status"] == "pass"
    assert result["points"][0]["expected_ler"] == pytest.approx(0.004582883142537217)
    assert result["points"][0]["observed_ci"] == {"low": 0.001, "high": 0.01}
    assert result["fixture"]["source"]["parameter_evidence"].endswith(
        "bivariate-bicycle-code.parameter-claim.01.json"
    )


def test_reference_check_fails_when_expected_ler_is_outside_ci(tmp_path: Path) -> None:
    run_root = _manifest_root(
        tmp_path,
        ci_low=0.01,
        ci_high=0.02,
        point_overrides={"errors": 10, "ler": 0.01},
    )

    result = evaluate_reference_check(run_root, _fixture(tmp_path))

    assert result["status"] == "fail"
    assert result["points"][0]["status"] == "fail"


def test_reference_check_rejects_zero_shot_evidence(tmp_path: Path) -> None:
    run_root = _manifest_root(tmp_path, ci_low=0.0, ci_high=1.0, shots=0)

    with pytest.raises(SearchIntegrityError, match="positive shots"):
        evaluate_reference_check(run_root, _fixture(tmp_path))


@pytest.mark.parametrize("ler", [-0.001, 1.001])
def test_reference_check_rejects_observed_ler_outside_rate_range(
    tmp_path: Path,
    ler: float,
) -> None:
    run_root = _manifest_root(
        tmp_path,
        ci_low=0.0,
        ci_high=1.0,
        point_overrides={"ler": ler},
    )

    with pytest.raises(SearchIntegrityError, match="observed ler must be a rate"):
        evaluate_reference_check(run_root, _fixture(tmp_path))


@pytest.mark.parametrize(
    "point_overrides",
    [
        {"ler": 0.001, "ci_low": 0.002},
        {"ler": 0.02, "ci_high": 0.01},
    ],
)
def test_reference_check_rejects_observed_ler_outside_ci(
    tmp_path: Path,
    point_overrides: dict,
) -> None:
    run_root = _manifest_root(
        tmp_path,
        ci_low=0.0,
        ci_high=1.0,
        point_overrides=point_overrides,
    )

    with pytest.raises(SearchIntegrityError, match="observed ler outside CI"):
        evaluate_reference_check(run_root, _fixture(tmp_path))


@pytest.mark.parametrize(
    "point_overrides",
    [
        {"errors": -1},
        {"errors": 1001},
    ],
)
def test_reference_check_rejects_invalid_observed_errors(
    tmp_path: Path,
    point_overrides: dict,
) -> None:
    run_root = _manifest_root(
        tmp_path,
        ci_low=0.0,
        ci_high=1.0,
        point_overrides=point_overrides,
    )

    with pytest.raises(SearchIntegrityError, match="observed errors must be valid"):
        evaluate_reference_check(run_root, _fixture(tmp_path))


def test_reference_check_rejects_ler_inconsistent_with_errors_per_shot(
    tmp_path: Path,
) -> None:
    run_root = _manifest_root(
        tmp_path,
        ci_low=0.0,
        ci_high=1.0,
        point_overrides={"errors": 6, "ler": 0.005},
    )

    with pytest.raises(SearchIntegrityError, match="observed ler .* errors/shots"):
        evaluate_reference_check(run_root, _fixture(tmp_path))


def test_write_reference_check_persists_json(tmp_path: Path) -> None:
    run_root = _manifest_root(tmp_path, ci_low=0.001, ci_high=0.01)
    output = write_reference_check(run_root, _fixture(tmp_path), None)

    assert output == run_root / "reference_check.json"
    persisted = json.loads(output.read_text())
    assert persisted["status"] == "pass"
    assert persisted["points"][0]["observed_ci"] == {"low": 0.001, "high": 0.01}


def test_reference_check_cli_writes_check_and_returns_status(tmp_path: Path) -> None:
    run_root = _manifest_root(tmp_path, ci_low=0.001, ci_high=0.01)
    fixture_path = _fixture(tmp_path)

    return_code = main(
        [
            "reference-check",
            "--root",
            str(tmp_path),
            "--run",
            "run",
            "--fixture",
            str(fixture_path),
        ]
    )

    assert return_code == 0
    assert json.loads((run_root / "reference_check.json").read_text())["status"] == (
        "pass"
    )


def test_reference_check_cli_returns_failure_for_failed_check(tmp_path: Path) -> None:
    run_root = _manifest_root(
        tmp_path,
        ci_low=0.01,
        ci_high=0.02,
        point_overrides={"errors": 10, "ler": 0.01},
    )
    fixture_path = _fixture(tmp_path)

    return_code = main(
        [
            "reference-check",
            "--root",
            str(tmp_path),
            "--run",
            str(run_root),
            "--fixture",
            str(fixture_path),
        ]
    )

    assert return_code == 1
    assert json.loads((run_root / "reference_check.json").read_text())["status"] == (
        "fail"
    )
