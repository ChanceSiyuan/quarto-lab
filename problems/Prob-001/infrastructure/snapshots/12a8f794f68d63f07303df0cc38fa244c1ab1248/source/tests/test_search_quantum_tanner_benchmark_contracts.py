from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.quantum_tanner_catalog import (
    load_quantum_tanner_fixture_catalog,
    resolve_quantum_tanner_fixture_entry,
)
from autoqec_search.rsinter import (
    rounds_for_task,
    task_requires_explicit_css_observables,
    validate_selected_p_values,
    write_css_spec_toml,
)
from autoqec_search.structure import summarize_css_structure


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "quantum-tanner-css-memory-x-rbposd-p001-v1"
SUITE_ID = "quantum-tanner-rbposd-p001-v1"
DECODER_ID = "rbposd-osd10-v1"


def _suite_task_decoder() -> tuple[dict, dict, dict, dict]:
    workspace = load_search_workspace(REPO_ROOT)
    suite = workspace.suites[SUITE_ID]
    assert suite["task_ids"] == [TASK_ID]
    task = workspace.tasks[TASK_ID]
    decoder = workspace.decoders[DECODER_ID]
    return workspace.decoders, suite, task, decoder


def _copied_workspace(tmp_path: Path, name: str) -> Path:
    work_root = tmp_path / name
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    return work_root


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def test_quantum_tanner_suite_contains_exactly_p001() -> None:
    _, suite, task, _ = _suite_task_decoder()

    assert suite["task_ids"] == [TASK_ID]
    assert task["p_list"] == [0.001]
    assert validate_selected_p_values(task, None) == [0.001]


def test_quantum_tanner_suite_pins_one_rbposd_decoder(tmp_path: Path) -> None:
    _, suite, _, decoder = _suite_task_decoder()

    assert suite["decoder_ids"] == [DECODER_ID]
    assert decoder["impl_key"] == "rbposd"
    assert decoder["parameters"]["osd_order"] == 10
    assert "predict-zero-v1" not in suite["decoder_ids"]

    work_root = _copied_workspace(tmp_path, "predict-zero-suite")
    suite_path = work_root / "benchmarks" / "suites" / f"{SUITE_ID}.json"
    suite_payload = _load_json(suite_path)
    suite_payload["decoder_ids"] = ["predict-zero-v1"]
    _write_json(suite_path, suite_payload)
    with pytest.raises(SearchIntegrityError, match="decoder_ids.*rbposd-osd10-v1"):
        load_search_workspace(work_root)

    work_root = _copied_workspace(tmp_path, "rmatching-suite")
    suite_path = work_root / "benchmarks" / "suites" / f"{SUITE_ID}.json"
    suite_payload = _load_json(suite_path)
    suite_payload["decoder_ids"] = ["rmatching-default-v1"]
    _write_json(suite_path, suite_payload)
    with pytest.raises(SearchIntegrityError, match="decoder_ids.*rbposd-osd10-v1"):
        load_search_workspace(work_root)


def test_quantum_tanner_task_routes_through_general_css_memory_path(
    tmp_path: Path,
) -> None:
    decoders, suite, task, _ = _suite_task_decoder()
    catalog = load_quantum_tanner_fixture_catalog(REPO_ROOT)
    entries_by_id = {entry["candidate_id"]: entry for entry in catalog["entries"]}
    candidate = resolve_quantum_tanner_fixture_entry(
        REPO_ROOT, entries_by_id["quantum-tanner-toric-d4"]
    )

    assert task["input_type"] == "css"
    assert task["observable"] == "logical_x"
    assert task["css_memory"] == {
        "basis": "x",
        "observables": "optional",
        "schedule": "greedy",
        "seed": 12345,
    }
    assert task_requires_explicit_css_observables(task) is False
    assert candidate.observables_x is None
    assert summarize_css_structure(candidate.hx, candidate.hz)["css_commute"] is True

    spec_path = tmp_path / "spec.toml"
    write_css_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=suite["decoder_ids"],
        code_id=candidate.spec.code_family,
        hx_path=Path("input/hx.css.json"),
        hz_path=Path("input/hz.css.json"),
        rounds=rounds_for_task(task, distance=None),
        p_values=validate_selected_p_values(task, None),
    )

    spec = spec_path.read_text()
    assert 'input_type = "css"' in spec
    assert 'impl_key = "rbposd"' in spec
    assert "p = [0.001]" in spec
    assert "observables =" not in spec


def test_quantum_tanner_contract_rejects_copied_bad_p001_records(tmp_path: Path) -> None:
    work_root = _copied_workspace(tmp_path, "bad-task-p")
    task_path = work_root / "benchmarks" / "tasks" / f"{TASK_ID}.json"
    suite_path = work_root / "benchmarks" / "suites" / f"{SUITE_ID}.json"

    task_payload = _load_json(task_path)
    task_payload["p_list"] = [0.001, 0.01]
    _write_json(task_path, task_payload)
    with pytest.raises(SearchIntegrityError, match="p=0.01"):
        load_search_workspace(work_root)

    task_payload["p_list"] = [0.001]
    _write_json(task_path, task_payload)
    suite_payload = _load_json(suite_path)
    suite_payload["shared_settings"]["default_p"] = 0.01
    _write_json(suite_path, suite_payload)
    with pytest.raises(SearchIntegrityError, match="p=0.01"):
        load_search_workspace(work_root)

    work_root = _copied_workspace(tmp_path, "bad-suite-p")
    suite_path = work_root / "benchmarks" / "suites" / f"{SUITE_ID}.json"
    suite_payload = _load_json(suite_path)
    suite_payload["shared_settings"]["p"] = 0.01
    _write_json(suite_path, suite_payload)
    with pytest.raises(SearchIntegrityError, match="p=0.01"):
        load_search_workspace(work_root)
