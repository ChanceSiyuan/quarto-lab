from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.distance_methods import DistanceMethodOptions
from autoqec_search.eval_candidates import CandidateInput, ResolvedCandidate
from autoqec_search.eval_run import evaluate_resolved_candidate_into_run
from autoqec_search.load import SearchIntegrityError, SearchWorkspace


def _matrix_payload() -> dict[str, object]:
    return {
        "format": "dense_binary_matrix",
        "n_rows": 0,
        "n_cols": 1,
        "data": [],
    }


def _candidate(*, distance: int | None) -> ResolvedCandidate:
    derived_properties = {} if distance is None else {"distance": distance}
    return ResolvedCandidate(
        spec=CandidateInput(
            candidate_id="bb-css-candidate",
            campaign_id="bb-css-campaign",
            code_family="bivariate-bicycle-code",
            parameters={},
            provenance={"kind": "test", "label": "synthetic"},
        ),
        artifact_root=Path("zoo/codes/bb/instances/bb-css-candidate"),
        instance={
            "id": "bivariate-bicycle-code-m6-n6",
            "code_id": "bivariate-bicycle-code",
            "parameters": {},
            "derived_properties": derived_properties,
        },
        hx=_matrix_payload(),
        hz=_matrix_payload(),
        source_kind="explicit-zoo-instance",
    )


def _k2_candidate() -> ResolvedCandidate:
    return ResolvedCandidate(
        spec=CandidateInput(
            candidate_id="qt-k2-candidate",
            campaign_id="quantum-tanner-autoresearch",
            code_family="quantum-tanner-code",
            parameters={},
            provenance={"kind": "test", "label": "synthetic"},
        ),
        artifact_root=Path("fixtures/qt-k2-candidate"),
        instance={
            "id": "qt-k2-candidate",
            "code_id": "quantum-tanner-code",
            "parameters": {},
            "derived_properties": {"distance": 4},
        },
        hx={
            "format": "dense_binary_matrix",
            "n_rows": 2,
            "n_cols": 4,
            "data": [[0, 0, 1, 0], [0, 0, 0, 1]],
        },
        hz={
            "format": "dense_binary_matrix",
            "n_rows": 0,
            "n_cols": 4,
            "data": [],
        },
        source_kind="explicit-zoo-instance",
    )


def _workspace() -> SearchWorkspace:
    return SearchWorkspace(
        campaigns={},
        search_spaces={},
        tasks={},
        decoders={
            "rmatching-default-v1": {
                "id": "rmatching-default-v1",
                "impl_key": "rmatching",
                "language": "rust",
            }
        },
        suites={},
        runs={},
    )


def test_css_eval_parses_no_distance_results_when_instance_has_recorded_distance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "input_type": "css",
        "p_list": [0.01],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 2000, "max_errors": 200},
        "css_memory": {"basis": "x", "schedule": "greedy"},
    }

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        spec_text = spec_path.read_text()
        assert "distance = [" not in spec_text
        assert 'hx = "../artifacts/hx.sparse_rows.json"' in spec_text
        assert 'hz = "../artifacts/hz.sparse_rows.json"' in spec_text
        hx_sparse = json.loads(
            (spec_path.parent.parent / "artifacts" / "hx.sparse_rows.json").read_text()
        )
        hz_sparse = json.loads(
            (spec_path.parent.parent / "artifacts" / "hz.sparse_rows.json").read_text()
        )
        assert hx_sparse == {"format": "sparse_rows", "num_cols": 1, "rows": []}
        assert hz_sparse == {"format": "sparse_rows", "num_cols": 1, "rows": []}
        result_path = out_dir / "rmatching-default-v1" / "test-run" / "results.jsonl"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "benchmark": "autoqec-bb-css-memory-x-cdep-v1",
                    "runner": "rmatching-default-v1",
                    "language": "rust",
                    "status": "ok",
                    "params": {
                        "input_type": "css",
                        "code_id": "bivariate-bicycle-code-m6-n6",
                        "hx": "../artifacts/hx.sparse_rows.json",
                        "hz": "../artifacts/hz.sparse_rows.json",
                        "basis": "x",
                        "schedule": "greedy",
                        "rounds": 3,
                        "p": 0.01,
                    },
                    "case_summary": {},
                    "metrics": {
                        "shots_used": 2000,
                        "logical_errors": 40,
                        "logical_error_rate": 0.02,
                    },
                    "artifacts": {},
                    "error": None,
                },
                sort_keys=True,
            )
            + "\n"
        )

    monkeypatch.setattr(
        "autoqec_search.eval_run.run_rsinter",
        fake_run_rsinter,
    )

    result = evaluate_resolved_candidate_into_run(
        run_root=tmp_path / "run",
        run_id="css-recorded-distance",
        campaign_id="bb-css-campaign",
        candidate=_candidate(distance=5),
        workspace=_workspace(),
        suite={"decoder_ids": ["rmatching-default-v1"]},
        task=task,
        selected_decoder_ids=["rmatching-default-v1"],
        selected_p_values=[0.01],
        created_at="2026-06-17T00:00:00Z",
        rsinter_executable="/bin/rsinter",
        rsinter_version="rsinter test",
    )

    assert result.distance == 5
    assert result.completed_manifests[0]["points"][0]["ler"] == 0.02
    assert json.loads((result.candidate_root / "distance.json").read_text())[
        "distance"
    ] == 5
    assert "distance=5" in (result.candidate_root / "candidate-plot.svg").read_text()


def test_css_eval_rejects_incomplete_explicit_x_observables_for_k2_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "id": "quantum-tanner-css-memory-x-rbposd-p001-v1",
        "input_type": "css",
        "observable": "logical_x",
        "p_list": [0.001],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 16, "batch_size": 16},
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "optional",
        },
    }

    def fail_run_rsinter(*args: object, **kwargs: object) -> None:
        raise AssertionError("rsinter should not run with incomplete observables")

    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fail_run_rsinter)

    with pytest.raises(
        SearchIntegrityError,
        match="explicit X observables define 1 rows, expected k = 2",
    ):
        evaluate_resolved_candidate_into_run(
            run_root=tmp_path / "run",
            run_id="bad-observables",
            campaign_id="quantum-tanner-autoresearch",
            candidate=_k2_candidate(),
            workspace=_workspace(),
            suite={"decoder_ids": ["rmatching-default-v1"]},
            task=task,
            selected_decoder_ids=["rmatching-default-v1"],
            selected_p_values=[0.001],
            created_at="2026-07-09T00:00:00Z",
            rsinter_executable="/bin/rsinter",
            rsinter_version="rsinter test",
            distance_payload_override={
                "status": "completed",
                "method": "css-upper-bound-witness",
                "bound_type": "upper",
                "upper_bound": 4,
                "basis": "x",
            },
            observables_x_override={
                "format": "sparse_rows",
                "num_cols": 4,
                "rows": [[0, 2, 3]],
            },
        )


def test_css_eval_does_not_emit_observables_without_explicit_task_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "input_type": "css",
        "p_list": [0.003],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {"basis": "x", "schedule": "greedy"},
    }
    candidate = _candidate(distance=6)
    object.__setattr__(
        candidate,
        "observables_x",
        {"format": "sparse_rows", "num_cols": 1, "rows": [[0]]},
    )

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        spec_text = spec_path.read_text()
        assert "observables =" not in spec_text
        assert "seed =" not in spec_text
        assert not (spec_path.parent / "input" / "observables.css.json").exists()
        result_path = out_dir / "rmatching-default-v1" / "test-run" / "results.jsonl"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "benchmark": "autoqec-bb-css-memory-x-cdep-v1",
                    "runner": "rmatching-default-v1",
                    "language": "rust",
                    "status": "ok",
                    "params": {
                        "input_type": "css",
                        "code_id": "bivariate-bicycle-code-m6-n6",
                        "hx": "../artifacts/hx.sparse_rows.json",
                        "hz": "../artifacts/hz.sparse_rows.json",
                        "basis": "x",
                        "schedule": "greedy",
                        "rounds": 3,
                        "p": 0.003,
                    },
                    "case_summary": {},
                    "metrics": {
                        "shots_used": 64,
                        "logical_errors": 1,
                        "logical_error_rate": 1 / 64,
                    },
                    "artifacts": {},
                    "error": None,
                },
                sort_keys=True,
            )
            + "\n"
        )

    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fake_run_rsinter)

    result = evaluate_resolved_candidate_into_run(
        run_root=tmp_path / "run",
        run_id="bb-smoke-implicit-observables",
        campaign_id="decoder-registry-css-bb-smoke",
        candidate=candidate,
        workspace=_workspace(),
        suite={"decoder_ids": ["rmatching-default-v1"]},
        task=task,
        selected_decoder_ids=["rmatching-default-v1"],
        selected_p_values=[0.003],
        created_at="2026-06-18T00:00:00Z",
        rsinter_executable="/bin/rsinter",
        rsinter_version="rsinter test",
    )

    assert "run_metadata" not in result.completed_manifests[0]


def test_css_eval_writes_required_bb72_observables_and_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "input_type": "css",
        "observable": "logical_x",
        "p_list": [0.003],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "required",
        },
    }
    candidate = _candidate(distance=6)
    object.__setattr__(
        candidate,
        "observables_x",
        {"format": "sparse_rows", "num_cols": 1, "rows": [[0]]},
    )
    workspace = _workspace()
    workspace.decoders["rbposd-bb72-osd1-v1"] = {
        "id": "rbposd-bb72-osd1-v1",
        "impl_key": "rbposd",
        "language": "rust",
        "parameters": {
            "bp_algorithm": "min_sum",
            "bp_iters": 50,
            "early_stop": True,
            "osd_method": "combination_sweep",
            "osd_order": 1,
        },
    }

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        spec_text = spec_path.read_text()
        assert 'observables = "input/observables.css.json"' in spec_text
        assert "seed = 12345" in spec_text
        assert json.loads(
            (spec_path.parent / "input" / "observables.css.json").read_text()
        ) == {
            "format": "sparse_rows",
            "num_cols": 1,
            "rows": [[0]],
        }
        result_path = out_dir / "rbposd-bb72-osd1-v1" / "test-run" / "results.jsonl"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "benchmark": "autoqec-bb-css-memory-x-cdep-v1",
                    "runner": "rbposd-bb72-osd1-v1",
                    "language": "rust",
                    "status": "ok",
                    "params": {
                        "input_type": "css",
                        "code_id": "bivariate-bicycle-code-m6-n6",
                        "hx": "input/hx.css.json",
                        "hz": "input/hz.css.json",
                        "observables": "input/observables.css.json",
                        "basis": "x",
                        "schedule": "greedy",
                        "rounds": 3,
                        "p": 0.003,
                        "seed": 12345,
                        "decoder_impl": "rbposd",
                        "logical_observable_source": "explicit",
                        "logical_observable_basis": "x",
                        "logical_failure_aggregation": "any_logical",
                        "logical_observable_count": 1,
                        "bp_algorithm": "min_sum",
                        "bp_iters": 50,
                        "early_stop": True,
                        "osd_method": "combination_sweep",
                        "osd_order": 1,
                    },
                    "case_summary": {},
                    "metrics": {
                        "shots_used": 64,
                        "logical_errors": 0,
                        "logical_error_rate": 0.0,
                    },
                    "artifacts": {},
                    "error": None,
                },
                sort_keys=True,
            )
            + "\n"
        )

    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fake_run_rsinter)

    result = evaluate_resolved_candidate_into_run(
        run_root=tmp_path / "run",
        run_id="bb72-observables",
        campaign_id="bb72-qldpc-campaign",
        candidate=candidate,
        workspace=workspace,
        suite={"decoder_ids": ["rbposd-bb72-osd1-v1"]},
        task=task,
        selected_decoder_ids=["rbposd-bb72-osd1-v1"],
        selected_p_values=[0.003],
        created_at="2026-06-18T00:00:00Z",
        rsinter_executable="/bin/rsinter",
        rsinter_version="rsinter test",
        general_css=True,
    )

    manifest = result.completed_manifests[0]
    assert manifest["run_metadata"]["logical_observable_source"] == "explicit"
    assert manifest["decoder_parameters"]["osd_method"] == "combination_sweep"


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("logical_observable_basis", "z"),
        ("seed", 54321),
        ("logical_observable_count", 2),
        ("logical_observable_source", "generated"),
        ("decoder_impl", "wrong-impl"),
        ("logical_failure_aggregation", "wrong-aggregation"),
    ],
)
def test_css_eval_rejects_unexpected_bb72_observable_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    bad_value: object,
) -> None:
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "input_type": "css",
        "observable": "logical_x",
        "p_list": [0.003],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "required",
        },
    }
    candidate = _candidate(distance=6)
    object.__setattr__(
        candidate,
        "observables_x",
        {"format": "sparse_rows", "num_cols": 1, "rows": [[0]]},
    )
    workspace = _workspace()
    workspace.decoders["rbposd-bb72-osd1-v1"] = {
        "id": "rbposd-bb72-osd1-v1",
        "impl_key": "rbposd",
        "language": "rust",
        "parameters": {
            "bp_algorithm": "min_sum",
            "bp_iters": 50,
            "early_stop": True,
            "osd_method": "combination_sweep",
            "osd_order": 1,
        },
    }

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        params = {
            "input_type": "css",
            "code_id": "bivariate-bicycle-code-m6-n6",
            "hx": "input/hx.css.json",
            "hz": "input/hz.css.json",
            "observables": "input/observables.css.json",
            "basis": "x",
            "schedule": "greedy",
            "rounds": 3,
            "p": 0.003,
            "seed": 12345,
            "decoder_impl": "rbposd",
            "logical_observable_source": "explicit",
            "logical_observable_basis": "x",
            "logical_failure_aggregation": "any_logical",
            "logical_observable_count": 1,
            "bp_algorithm": "min_sum",
            "bp_iters": 50,
            "early_stop": True,
            "osd_method": "combination_sweep",
            "osd_order": 1,
        }
        params[field] = bad_value
        result_path = out_dir / "rbposd-bb72-osd1-v1" / "test-run" / "results.jsonl"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "benchmark": "autoqec-bb-css-memory-x-cdep-v1",
                    "runner": "rbposd-bb72-osd1-v1",
                    "language": "rust",
                    "status": "ok",
                    "params": params,
                    "case_summary": {},
                    "metrics": {
                        "shots_used": 64,
                        "logical_errors": 0,
                        "logical_error_rate": 0.0,
                    },
                    "artifacts": {},
                    "error": None,
                },
                sort_keys=True,
            )
            + "\n"
        )

    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fake_run_rsinter)

    with pytest.raises(SearchIntegrityError, match=field):
        evaluate_resolved_candidate_into_run(
            run_root=tmp_path / "run",
            run_id="bb72-observables",
            campaign_id="bb72-qldpc-campaign",
            candidate=candidate,
            workspace=workspace,
            suite={"decoder_ids": ["rbposd-bb72-osd1-v1"]},
            task=task,
            selected_decoder_ids=["rbposd-bb72-osd1-v1"],
            selected_p_values=[0.003],
            created_at="2026-06-18T00:00:00Z",
            rsinter_executable="/bin/rsinter",
            rsinter_version="rsinter test",
            general_css=True,
        )


def test_css_eval_requires_seed_when_explicit_observables_are_emitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "input_type": "css",
        "observable": "logical_x",
        "p_list": [0.003],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "observables": "required",
        },
    }
    candidate = _candidate(distance=6)
    object.__setattr__(
        candidate,
        "observables_x",
        {"format": "sparse_rows", "num_cols": 1, "rows": [[0]]},
    )

    def fail_run_rsinter(*args: object, **kwargs: object) -> None:
        raise AssertionError("rsinter should not run without an expected seed")

    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fail_run_rsinter)

    with pytest.raises(SearchIntegrityError, match="explicit CSS observables.*seed"):
        evaluate_resolved_candidate_into_run(
            run_root=tmp_path / "run",
            run_id="bb72-observables",
            campaign_id="bb72-qldpc-campaign",
            candidate=candidate,
            workspace=_workspace(),
            suite={"decoder_ids": ["rmatching-default-v1"]},
            task=task,
            selected_decoder_ids=["rmatching-default-v1"],
            selected_p_values=[0.003],
            created_at="2026-06-18T00:00:00Z",
            rsinter_executable="/bin/rsinter",
            rsinter_version="rsinter test",
        )


def test_css_eval_writes_required_bb72_observables_without_general_css(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "input_type": "css",
        "observable": "logical_x",
        "p_list": [0.003],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "required",
        },
    }
    candidate = _candidate(distance=6)
    object.__setattr__(
        candidate,
        "observables_x",
        {"format": "sparse_rows", "num_cols": 1, "rows": [[0]]},
    )
    workspace = _workspace()

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        spec_text = spec_path.read_text()
        assert 'observables = "input/observables.css.json"' in spec_text
        assert 'hx = "../artifacts/hx.sparse_rows.json"' in spec_text
        result_path = out_dir / "rmatching-default-v1" / "test-run" / "results.jsonl"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "benchmark": "autoqec-bb-css-memory-x-cdep-v1",
                    "runner": "rmatching-default-v1",
                    "language": "rust",
                    "status": "ok",
                    "params": {
                        "input_type": "css",
                        "code_id": "bivariate-bicycle-code-m6-n6",
                        "hx": "../artifacts/hx.sparse_rows.json",
                        "hz": "../artifacts/hz.sparse_rows.json",
                        "observables": "input/observables.css.json",
                        "basis": "x",
                        "schedule": "greedy",
                        "rounds": 3,
                        "p": 0.003,
                        "seed": 12345,
                        "decoder_impl": "rmatching",
                        "logical_observable_source": "explicit",
                        "logical_observable_basis": "x",
                        "logical_failure_aggregation": "any_logical",
                        "logical_observable_count": 1,
                    },
                    "case_summary": {},
                    "metrics": {
                        "shots_used": 64,
                        "logical_errors": 0,
                        "logical_error_rate": 0.0,
                    },
                    "artifacts": {},
                    "error": None,
                },
                sort_keys=True,
            )
            + "\n"
        )

    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fake_run_rsinter)

    result = evaluate_resolved_candidate_into_run(
        run_root=tmp_path / "run",
        run_id="bb72-observables",
        campaign_id="bb72-qldpc-campaign",
        candidate=candidate,
        workspace=workspace,
        suite={"decoder_ids": ["rmatching-default-v1"]},
        task=task,
        selected_decoder_ids=["rmatching-default-v1"],
        selected_p_values=[0.003],
        created_at="2026-06-18T00:00:00Z",
        rsinter_executable="/bin/rsinter",
        rsinter_version="rsinter test",
    )

    assert result.completed_manifests[0]["run_metadata"]["seed"] == 12345


def test_css_eval_rejects_x_observables_for_z_basis_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "id": "bb-css-memory-z-cdep-v1",
        "input_type": "css",
        "observable": "logical_z",
        "p_list": [0.003],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {
            "basis": "z",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "required",
        },
    }
    candidate = _candidate(distance=6)
    object.__setattr__(
        candidate,
        "observables_x",
        {"format": "sparse_rows", "num_cols": 1, "rows": [[0]]},
    )

    def fail_run_rsinter(*args: object, **kwargs: object) -> None:
        raise AssertionError("rsinter should not run with X observables for basis z")

    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fail_run_rsinter)

    with pytest.raises(SearchIntegrityError, match="logical-X observables.*basis z"):
        evaluate_resolved_candidate_into_run(
            run_root=tmp_path / "run",
            run_id="bb72-observables",
            campaign_id="bb72-qldpc-campaign",
            candidate=candidate,
            workspace=_workspace(),
            suite={"decoder_ids": ["rmatching-default-v1"]},
            task=task,
            selected_decoder_ids=["rmatching-default-v1"],
            selected_p_values=[0.003],
            created_at="2026-06-18T00:00:00Z",
            rsinter_executable="/bin/rsinter",
            rsinter_version="rsinter test",
        )


def test_non_css_eval_rejects_missing_copied_instance_distance(
    tmp_path: Path,
) -> None:
    task = {
        "id": "rotated-memory-x-cdep-v1",
        "input_type": "stim-detector-error-model",
        "p_list": [0.005],
        "rounds_policy": {"kind": "distance-scaled", "minimum": 3, "multiplier": 3},
        "collection": {"max_shots": 1000, "max_errors": 50},
    }

    with pytest.raises(
        SearchIntegrityError,
        match="copied instance distance must be a positive integer",
    ):
        evaluate_resolved_candidate_into_run(
            run_root=tmp_path / "run",
            run_id="non-css-missing-distance",
            campaign_id="bb-css-campaign",
            candidate=_candidate(distance=None),
            workspace=_workspace(),
            suite={"decoder_ids": ["rmatching-default-v1"]},
            task=task,
            selected_decoder_ids=["rmatching-default-v1"],
            selected_p_values=[0.005],
            created_at="2026-06-17T00:00:00Z",
            rsinter_executable="/bin/rsinter",
            rsinter_version="rsinter test",
        )


def test_css_upper_bound_eval_rejects_missing_recorded_distance_before_rsinter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "input_type": "css",
        "p_list": [0.003],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {"basis": "x", "schedule": "greedy"},
    }

    def fail_run_rsinter(*args: object, **kwargs: object) -> None:
        raise AssertionError("rsinter should not run without an upper-bound payload")

    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fail_run_rsinter)

    with pytest.raises(
        SearchIntegrityError,
        match="random-window-upper-bound requires instance derived_properties.distance",
    ):
        evaluate_resolved_candidate_into_run(
            run_root=tmp_path / "run",
            run_id="css-upper-missing-distance",
            campaign_id="bb-css-campaign",
            candidate=_candidate(distance=None),
            workspace=_workspace(),
            suite={"decoder_ids": ["rmatching-default-v1"]},
            task=task,
            selected_decoder_ids=["rmatching-default-v1"],
            selected_p_values=[0.003],
            created_at="2026-06-18T00:00:00Z",
            rsinter_executable="/bin/rsinter",
            rsinter_version="rsinter test",
            distance_method_options=DistanceMethodOptions(
                method="random-window-upper-bound",
                qec_code_bin="qec-code",
            ),
        )


def test_non_css_upper_bound_eval_reports_exact_distance_requirement(
    tmp_path: Path,
) -> None:
    task = {
        "id": "rotated-memory-x-cdep-v1",
        "input_type": "stim-detector-error-model",
        "p_list": [0.005],
        "rounds_policy": {"kind": "distance-scaled", "minimum": 3, "multiplier": 3},
        "collection": {"max_shots": 1000, "max_errors": 50},
    }

    with pytest.raises(
        SearchIntegrityError,
        match=(
            "non-CSS evaluation requires exact distance "
            r".*method=random-window-upper-bound.*bound_type=upper.*upper_bound=6"
        ),
    ):
        evaluate_resolved_candidate_into_run(
            run_root=tmp_path / "run",
            run_id="non-css-upper-bound",
            campaign_id="bb-css-campaign",
            candidate=_candidate(distance=6),
            workspace=_workspace(),
            suite={"decoder_ids": ["rmatching-default-v1"]},
            task=task,
            selected_decoder_ids=["rmatching-default-v1"],
            selected_p_values=[0.005],
            created_at="2026-06-18T00:00:00Z",
            rsinter_executable="/bin/rsinter",
            rsinter_version="rsinter test",
            distance_method_options=DistanceMethodOptions(
                method="random-window-upper-bound",
                qec_code_bin="qec-code",
            ),
        )
