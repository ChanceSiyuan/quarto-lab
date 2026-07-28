from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.eval_candidates import CandidateInput, ResolvedCandidate
from autoqec_search.eval_run import evaluate_resolved_candidate_into_run
from autoqec_search.load import SearchWorkspace


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


def test_css_eval_accepts_sparse_row_candidate_matrices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = ResolvedCandidate(
        spec=CandidateInput(
            candidate_id="qt-sparse-rows-candidate",
            campaign_id="quantum-tanner-autoresearch",
            code_family="quantum-tanner-code",
            parameters={},
            provenance={"kind": "test", "label": "synthetic"},
        ),
        artifact_root=Path("fixtures/qt-sparse-rows-candidate"),
        instance={
            "id": "qt-sparse-rows-candidate",
            "code_id": "quantum-tanner-code",
            "parameters": {},
            "derived_properties": {"distance": 4},
        },
        hx={"format": "sparse_rows", "num_cols": 4, "rows": [[0, 2], [1, 3]]},
        hz={"format": "sparse_rows", "num_cols": 4, "rows": []},
        source_kind="proposal-import",
    )
    object.__setattr__(
        candidate,
        "observables_x",
        {"format": "sparse_rows", "num_cols": 4, "rows": [[0, 1], [2, 3]]},
    )
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

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        hx_sparse = json.loads(
            (spec_path.parent.parent / "artifacts" / "hx.sparse_rows.json").read_text()
        )
        hz_sparse = json.loads(
            (spec_path.parent.parent / "artifacts" / "hz.sparse_rows.json").read_text()
        )
        assert hx_sparse == {"format": "sparse_rows", "num_cols": 4, "rows": [[0, 2], [1, 3]]}
        assert hz_sparse == {"format": "sparse_rows", "num_cols": 4, "rows": []}
        result_path = out_dir / "rmatching-default-v1" / "test-run" / "results.jsonl"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "benchmark": "autoqec-quantum-tanner-css-memory-x-rbposd-p001-v1",
                    "runner": "rmatching-default-v1",
                    "language": "rust",
                    "status": "ok",
                    "params": {
                        "input_type": "css",
                        "code_id": "qt-sparse-rows-candidate",
                        "hx": "../artifacts/hx.sparse_rows.json",
                        "hz": "../artifacts/hz.sparse_rows.json",
                        "basis": "x",
                        "schedule": "greedy",
                        "rounds": 3,
                        "p": 0.001,
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
        run_id="sparse-rows",
        campaign_id="quantum-tanner-autoresearch",
        candidate=candidate,
        workspace=_workspace(),
        suite={"decoder_ids": ["rmatching-default-v1"]},
        task=task,
        selected_decoder_ids=["rmatching-default-v1"],
        selected_p_values=[0.001],
        created_at="2026-07-10T00:00:00Z",
        rsinter_executable="/bin/rsinter",
        rsinter_version="rsinter test",
    )

    assert result.completed_manifests[0]["points"][0]["ler"] == 0.0
