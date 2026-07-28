from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest


def _write_spec(
    root: Path,
    candidate_id: str,
    *,
    group_name: str,
    group_order: int,
    generators_a: list[int],
    generators_b: list[int],
    h_a: list[list[int]],
    h_b: list[list[int]] | None = None,
    css_n: int | None = None,
    css_k: int | None = None,
) -> str:
    relative_path = (
        Path("campaigns")
        / "qt-report-fixture"
        / candidate_id
        / "qec_code_quantum_tanner_spec.json"
    )
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "fixture_id": candidate_id,
                "construction_mode": "lr_cayley_no_cover_v1",
                "base_group": {
                    "name": group_name,
                    "element_order": "id = i + m*j for r^i s^j",
                    "order": group_order,
                    "identity": 0,
                    "multiplication_table": [
                        list(range(group_order)) for _ in range(group_order)
                    ],
                },
                "a_generator_indices": generators_a,
                "b_generator_indices": generators_b,
                "local_codes": {
                    "matrix_role": "parity_check",
                    "field": "GF(2)",
                    "h_a": h_a,
                    "h_b": h_a if h_b is None else h_b,
                },
            }
        )
        + "\n"
    )
    if css_n is not None and css_k is not None:
        (path.parent / "instance.json").write_text(
            json.dumps({"n": css_n, "k": css_k}) + "\n"
        )
    return relative_path.as_posix()


def _report_model(root: Path) -> dict:
    matrices = {
        "D4": [[1, 1]],
        "D8": [[1, 1, 0, 0], [0, 0, 1, 1]],
        "D12": [
            [1, 0, 1, 0, 1, 0],
            [0, 1, 1, 0, 0, 1],
            [0, 0, 0, 1, 1, 1],
        ],
        "D16": [
            [1, 1, 1, 1, 1, 1, 1, 1],
            [0, 0, 0, 0, 1, 1, 1, 1],
            [0, 0, 1, 1, 0, 0, 1, 1],
            [0, 1, 0, 1, 0, 1, 0, 1],
        ],
    }
    dimensions = {
        "D4": (8, 2, 2),
        "D8": (64, 8, 2),
        "D12": (216, 28, 6),
        "D16": (512, 72, None),
    }
    candidates = []
    points = []
    for index, short_name in enumerate(("D4", "D8", "D12", "D16")):
        candidate_id = f"qt-dih-{short_name[1:]}-split-reflections-r1"
        m = int(short_name[1:])
        n, k, upper_bound = dimensions[short_name]
        spec_path = _write_spec(
            root,
            candidate_id,
            group_name=f"D_{m}",
            group_order=2 * m,
            generators_a=list(range(m, 2 * m, 2)),
            generators_b=list(range(m + 1, 2 * m, 2)),
            h_a=matrices[short_name],
            css_n=n,
            css_k=k,
        )
        skipped = short_name == "D16"
        candidates.append(
            {
                "candidate_id": candidate_id,
                "distance": None,
                "upper_bound": upper_bound,
                "distance_method": "random-window-upper-bound",
                "distance_bound_type": "upper" if not skipped else None,
                "status": "skipped" if skipped else "evaluated",
                "screening": {
                    "screening_status": "skipped" if skipped else "admitted",
                    "distance_bound_type": "upper",
                    "distance_upper_bound": upper_bound,
                    "reason": (
                        "missing_upper_bound_payload"
                        if skipped
                        else "loaded_upper_bound_payload"
                    ),
                },
                "n": None if skipped else n,
                "k": None if skipped else k,
                "css_commute": True,
                "parameters": {
                    "base_group": f"D_{m}",
                    "construction_mode": "lr_cayley_no_cover_v1",
                },
                "provenance": {
                    "kind": "proposal-derived",
                    "label": candidate_id,
                    "proposal": {"qec_code_spec_path": spec_path},
                },
            }
        )
        if not skipped:
            errors = (2, 4, 0)[index]
            lers = (0.03125, 0.0625, 0.0)
            ci_lows = (0.0086119577, 0.0245708037, 0.0)
            ci_highs = (0.1069749388, 0.1499769664, 0.0566260230)
            seconds = (0.112604874, 5.350949124, 240.801820333)
            points.append(
                {
                    "candidate_id": candidate_id,
                    "distance": None,
                    "task_id": "quantum-tanner-css-memory-x-rbposd-p001-v1",
                    "decoder_id": "rbposd-osd10-v1",
                    "decoder_parameters": {"osd_order": 10},
                    "p": 0.001,
                    "rounds": 3,
                    "shots": 64,
                    "errors": errors,
                    "ler": lers[index],
                    "ci_low": ci_lows[index],
                    "ci_high": ci_highs[index],
                    "seconds": seconds[index],
                }
            )
    return {
        "schema_version": 1,
        "provenance": {
            "campaign_id": "quantum-tanner-autoresearch",
            "run_id": "qt-long-r0001-a001",
            "mode": "autoresearch",
            "generated_at": "2026-07-10T00:00:00Z",
            "seed": 12345,
        },
        "counts": {
            "candidates": 4,
            "completed": 3,
            "crash": 0,
            "placeholder": 1,
            "frontier": 2,
            "points": 3,
        },
        "candidates": candidates,
        "manifests": [],
        "points": points,
        "leaderboard": [],
        "frontier": [
            {"candidate_id": candidates[0]["candidate_id"]},
            {"candidate_id": candidates[2]["candidate_id"]},
        ],
        "verdicts": [],
        "reference_check": None,
    }


def test_describe_local_code_recognizes_reviewed_codes_and_unnamed_fallback() -> None:
    from autoqec_search.quantum_tanner_report import describe_local_code

    cases = [
        (
            [[1, 1]],
            "Rep(2) [2,1,2]",
            {2: 1},
        ),
        (
            [[1, 1, 0, 0], [0, 0, 1, 1]],
            "Rep(2) direct sum Rep(2) [4,2,2]",
            {2: 2, 4: 1},
        ),
        (
            [
                [1, 0, 1, 0, 1, 0],
                [0, 1, 1, 0, 0, 1],
                [0, 0, 0, 1, 1, 1],
            ],
            "Unnamed [6,3,3]",
            {3: 4, 4: 3},
        ),
        (
            [
                [1, 1, 1, 1, 1, 1, 1, 1],
                [0, 0, 0, 0, 1, 1, 1, 1],
                [0, 0, 1, 1, 0, 0, 1, 1],
                [0, 1, 0, 1, 0, 1, 0, 1],
            ],
            "Extended Hamming / RM(1,3) [8,4,4]",
            {4: 14, 8: 1},
        ),
    ]

    for matrix, expected_label, expected_enumerator in cases:
        description = describe_local_code(matrix)
        assert description["label"] == expected_label
        assert description["weight_enumerator"] == expected_enumerator


def test_describe_local_code_bounds_exact_enumeration() -> None:
    from autoqec_search.quantum_tanner_report import describe_local_code

    description = describe_local_code([[0] * 8], max_codewords=16)

    assert description["n"] == 8
    assert description["k"] == 8
    assert description["d"] is None
    assert description["label"] == "Unnamed [8,8,?]"
    assert description["weight_enumerator"] is None


def test_build_quantum_tanner_view_model_includes_every_candidate(tmp_path: Path) -> None:
    from autoqec_search.quantum_tanner_report import build_quantum_tanner_view_model

    view_model = build_quantum_tanner_view_model(tmp_path, _report_model(tmp_path))

    assert view_model["counts"] == {
        "processed": 4,
        "evaluated": 3,
        "skipped": 1,
        "frontier": 2,
    }
    assert len(view_model["rows"]) == 4
    assert view_model["rows"][0]["base_group_label"] == "D_4 (order 8)"
    assert view_model["rows"][0]["local_code_label"] == "Rep(2) [2,1,2]"
    assert view_model["rows"][2]["local_code_label"] == "Unnamed [6,3,3]"
    assert view_model["rows"][2]["ler"] == 0.0
    assert view_model["rows"][3]["screening_status"] == "skipped"
    assert view_model["rows"][3]["point"] is None
    assert view_model["rows"][3]["css_label"] == "[[512,72]]"
    assert view_model["rows"][3]["rate"] == 72 / 512
    assert view_model["rows"][3]["definition_anchor"] == "candidate-4"


def test_quantum_tanner_html_matches_master_table_and_definitions(tmp_path: Path) -> None:
    from autoqec_search.quantum_tanner_report import (
        build_quantum_tanner_view_model,
        render_quantum_tanner_definitions_html,
        render_quantum_tanner_report_html,
    )

    view_model = build_quantum_tanner_view_model(tmp_path, _report_model(tmp_path))
    html = render_quantum_tanner_report_html(
        view_model,
        ler_svg='<svg aria-label="fixture"></svg>',
        report_json='{"fixture":true}',
    )
    definitions = render_quantum_tanner_definitions_html(view_model)

    for expected in (
        "Quantum Tanner Benchmark Summary",
        "Master Results Table",
        "Base group",
        "A / B generators",
        "Local classical code",
        "D_4 (order 8)",
        "Unnamed [6,3,3]",
        "rsinter not run",
        "construction-definitions.html#candidate-4",
        "Scientific Interpretation",
    ):
        assert expected in html
    assert html.count('data-candidate-row="true"') == 4
    assert "<svg" in html
    assert 'id="autoqec-report-data"' in html
    assert re.search(r"[\u4e00-\u9fff]", html) is None
    assert "http://" not in html
    assert "https://" not in html

    assert definitions.count('class="candidate-definition"') == 4
    assert 'id="candidate-4"' in definitions
    assert "H_A" in definitions
    assert "H_B" in definitions
    assert "Extended Hamming / RM(1,3) [8,4,4]" in definitions
    assert re.search(r"[\u4e00-\u9fff]", definitions) is None


def test_quantum_tanner_report_degrades_when_construction_spec_is_missing(
    tmp_path: Path,
) -> None:
    from autoqec_search.quantum_tanner_report import build_quantum_tanner_view_model

    model = _report_model(tmp_path)
    model["candidates"][0]["provenance"]["proposal"]["qec_code_spec_path"] = (
        "campaigns/qt-report-fixture/missing.json"
    )

    view_model = build_quantum_tanner_view_model(tmp_path, model)

    first = view_model["rows"][0]
    assert first["construction"]["available"] is False
    assert first["base_group_label"] == "Construction metadata unavailable"
    assert "missing construction spec" in first["construction"]["error"]


def test_quantum_tanner_view_model_excludes_never_attempted_placeholders(
    tmp_path: Path,
) -> None:
    from autoqec_search.quantum_tanner_report import build_quantum_tanner_view_model

    model = _report_model(tmp_path)
    placeholder = copy.deepcopy(model["candidates"][0])
    placeholder["candidate_id"] = "never-attempted-placeholder"
    placeholder["status"] = "placeholder"
    placeholder["screening"] = None
    placeholder["n"] = None
    placeholder["k"] = None
    model["candidates"].append(placeholder)

    view_model = build_quantum_tanner_view_model(tmp_path, model)

    assert view_model["counts"]["processed"] == 4
    assert len(view_model["rows"]) == 4
    assert all(
        row["candidate_id"] != "never-attempted-placeholder"
        for row in view_model["rows"]
    )


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (lambda spec: spec["local_codes"].__setitem__("field", "GF(4)"), "GF(2)"),
        (
            lambda spec: spec["local_codes"].__setitem__("matrix_role", "generator"),
            "parity_check",
        ),
        (
            lambda spec: spec.__setitem__("a_generator_indices", [999]),
            "outside base-group order",
        ),
    ],
)
def test_quantum_tanner_report_rejects_semantically_invalid_construction_specs(
    tmp_path: Path,
    mutation,
    expected_error: str,
) -> None:
    from autoqec_search.quantum_tanner_report import build_quantum_tanner_view_model

    model = _report_model(tmp_path)
    reference = model["candidates"][0]["provenance"]["proposal"][
        "qec_code_spec_path"
    ]
    path = tmp_path / reference
    spec = json.loads(path.read_text())
    mutation(spec)
    path.write_text(json.dumps(spec) + "\n")

    view_model = build_quantum_tanner_view_model(tmp_path, model)

    construction = view_model["rows"][0]["construction"]
    assert construction["available"] is False
    assert expected_error in construction["error"]


def test_catalog_candidate_prefers_its_recorded_spec_before_default_catalog(
    tmp_path: Path,
) -> None:
    from autoqec_search.quantum_tanner_report import build_quantum_tanner_view_model

    shutil_source = Path("campaigns/examples/quantum-tanner-autoresearch")
    catalog_path = tmp_path / shutil_source / "fixture_catalog.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "candidate_id": "quantum-tanner-toric-d4",
                        "provenance": {
                            "quantum_tanner_spec": "catalog-default.json"
                        },
                    }
                ]
            }
        )
        + "\n"
    )
    recorded_path = _write_spec(
        tmp_path,
        "recorded-catalog-candidate",
        group_name="RecordedGroup",
        group_order=8,
        generators_a=[1, 7],
        generators_b=[3, 5],
        h_a=[[1, 1]],
        css_n=8,
        css_k=2,
    )
    model = {
        "provenance": {
            "campaign_id": "quantum-tanner-autoresearch",
            "run_id": "catalog-source-precedence",
        },
        "candidates": [
            {
                "candidate_id": "quantum-tanner-toric-d4",
                "status": "evaluated",
                "screening": {"screening_status": "admitted"},
                "n": 8,
                "k": 2,
                "parameters": {"quantum_tanner_spec": recorded_path},
                "provenance": {
                    "kind": "distance-ladder-fixture",
                    "label": "quantum-tanner-toric-d4",
                },
            }
        ],
        "points": [],
        "frontier": [],
    }

    view_model = build_quantum_tanner_view_model(tmp_path, model)

    assert view_model["rows"][0]["base_group_label"] == "RecordedGroup (order 8)"


def test_write_report_html_automatically_writes_quantum_tanner_report_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import autoqec_search.report as report_module

    model = _report_model(tmp_path)
    monkeypatch.setattr(report_module, "build_report_model", lambda _root, _run: model)
    run_root = tmp_path / "run"
    run_root.mkdir()

    output = report_module.write_report_html(tmp_path, run_root)

    definitions = run_root / "construction-definitions.html"
    assert output == run_root / "report.html"
    assert output.is_file()
    assert definitions.is_file()
    assert "Quantum Tanner Benchmark Summary" in output.read_text()
    assert "Quantum Tanner Candidate Construction Definitions" in definitions.read_text()


def test_write_report_html_keeps_generic_campaign_without_definition_companion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import autoqec_search.report as report_module

    model = _report_model(tmp_path)
    model["provenance"]["campaign_id"] = "rotated-surface-baseline"
    monkeypatch.setattr(report_module, "build_report_model", lambda _root, _run: model)
    run_root = tmp_path / "run"
    run_root.mkdir()

    output = report_module.write_report_html(tmp_path, run_root)

    assert "AutoQEC Search Report" in output.read_text()
    assert not (run_root / "construction-definitions.html").exists()
