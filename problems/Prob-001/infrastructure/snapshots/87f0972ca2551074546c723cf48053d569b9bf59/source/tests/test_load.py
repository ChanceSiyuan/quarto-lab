from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from autoqec_zoo.load import IntegrityError, load_zoo


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_zoo_collects_cards_and_evidence() -> None:
    dataset = load_zoo(REPO_ROOT / "zoo")

    assert sorted(dataset.cards) == [
        "bivariate-bicycle-code",
        "rotated-surface-code",
        "surface-code",
    ]
    assert sorted(dataset.evidence) == [
        "2308.07915:bivariate-bicycle-code.construction",
        "2308.07915:bivariate-bicycle-code.decoder",
        "2308.07915:bivariate-bicycle-code.distance",
        "2308.07915:bivariate-bicycle-code.parameters",
        "2308.07915:bivariate-bicycle-code.pseudo-thresholds",
        "2308.07915:bivariate-bicycle-code.surface-comparison",
        "2408.10001:bivariate-bicycle-code.parameters"
    ]
    assert dataset.cards["rotated-surface-code"]["family"] == "surface-code"


def test_load_zoo_collects_instances() -> None:
    dataset = load_zoo(REPO_ROOT / "zoo")

    assert sorted(dataset.instances) == [
        "bivariate-bicycle-code-m6-n6",
        "rotated-surface-code-d3",
        "rotated-surface-code-d5",
        "rotated-surface-code-d7",
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ]
    instance = dataset.instances["rotated-surface-code-d3"]
    assert instance.payload["code_id"] == "rotated-surface-code"
    assert instance.payload["family_id"] == "surface-code"
    assert instance.payload["derived_properties"]["n"] == 9
    assert "hx_matrix" not in instance.payload
    assert "hz_matrix" not in instance.payload

    assert instance.hx_matrix["n_rows"] == 4
    assert instance.hx_matrix["n_cols"] == 9
    assert instance.hx_matrix["data"][1] == [1, 1, 0, 1, 1, 0, 0, 0, 0]

    assert instance.hz_matrix["n_rows"] == 4
    assert instance.hz_matrix["n_cols"] == 9
    assert instance.hz_matrix["data"][3] == [0, 0, 0, 0, 0, 0, 0, 1, 1]

    bb_instance = dataset.instances["bivariate-bicycle-code-m6-n6"]
    assert bb_instance.payload["code_id"] == "bivariate-bicycle-code"
    assert bb_instance.payload["derived_properties"]["n"] == 72
    assert bb_instance.payload["derived_properties"]["distance"] == 6
    assert bb_instance.hx_matrix["n_rows"] == 36
    assert bb_instance.hz_matrix["n_rows"] == 36
    assert bb_instance.hx_matrix["n_cols"] == 72
    assert bb_instance.hz_matrix["n_cols"] == 72


def test_bb72_instance_is_paper_backed_and_schema_valid() -> None:
    from jsonschema import Draft202012Validator
    from autoqec_search.structure import summarize_css_structure

    root = Path(__file__).resolve().parents[1]
    instance_root = root / "zoo" / "codes" / "bivariate-bicycle-code" / "instances" / "bivariate-bicycle-code-m6-n6"
    schema = json.loads((root / "zoo" / "schemas" / "code-instance.schema.json").read_text())
    instance = json.loads((instance_root / "instance.json").read_text())
    hx = json.loads((instance_root / "hx.json").read_text())
    hz = json.loads((instance_root / "hz.json").read_text())

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(instance)
    structure = summarize_css_structure(hx, hz)

    assert instance["parameters"]["distance"] == 6
    assert instance["parameters"]["paper"]["paper_ref"] == "2308.07915"
    assert instance["derived_properties"]["distance"] == 6
    assert structure["n"] == 72
    assert structure["k"] == 12
    assert structure["css_commute"] is True


def test_load_zoo_rejects_missing_evidence_ref(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    card_path = work_root / "codes" / "surface-code" / "card.json"
    card = json.loads(card_path.read_text())
    card["evidence_refs"].append("missing:surface-code.claim")
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="missing evidence_ref"):
        load_zoo(work_root)


def test_load_zoo_rejects_evidence_with_unknown_code_id(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    evidence_path = (
        work_root / "evidence" / "2408.10001" / "bivariate-bicycle-code.parameters.json"
    )
    evidence = json.loads(evidence_path.read_text())
    evidence["code_id"] = "unknown-code"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="unknown code_id"):
        load_zoo(work_root)


def test_load_zoo_rejects_evidence_paper_id_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    evidence_path = (
        work_root / "evidence" / "2408.10001" / "bivariate-bicycle-code.parameters.json"
    )
    evidence = json.loads(evidence_path.read_text())
    evidence["paper_id"] = "wrong-paper"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="paper_id mismatch"):
        load_zoo(work_root)


def test_load_zoo_rejects_variant_missing_family(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    card_path = work_root / "codes" / "rotated-surface-code" / "card.json"
    card = json.loads(card_path.read_text())
    del card["family"]
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="variant card missing family"):
        load_zoo(work_root)


def test_load_zoo_rejects_missing_source_ref_for_evidence(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    card_path = work_root / "codes" / "bivariate-bicycle-code" / "card.json"
    card = json.loads(card_path.read_text())
    card["source_refs"] = []
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="source_refs missing paper"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_missing_hx(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "hx.json"
    ).unlink()

    with pytest.raises(IntegrityError, match="missing hx artifact"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_code_directory_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    instance_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "instance.json"
    )
    payload = json.loads(instance_path.read_text())
    payload["code_id"] = "surface-code"
    instance_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="instance code_id mismatch"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_id_directory_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    instance_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "instance.json"
    )
    payload = json.loads(instance_path.read_text())
    payload["id"] = "rotated-surface-code-d5"
    instance_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="instance id mismatch"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_dimension_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    hz_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "hz.json"
    )
    payload = json.loads(hz_path.read_text())
    payload["n_cols"] = 8
    payload["data"] = [row[:8] for row in payload["data"]]
    hz_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match=r"matrix column mismatch: .*hx\.json.*hz\.json"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_matrix_format_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    hx_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "hx.json"
    )
    payload = json.loads(hx_path.read_text())
    payload["format"] = "sparse_binary_matrix"
    hx_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="unsupported matrix format"):
        load_zoo(work_root)


def test_bb72_qldpc_campaign_loads() -> None:
    from autoqec_search.load import load_search_workspace

    workspace = load_search_workspace(Path(__file__).resolve().parents[1])

    campaign = workspace.campaigns["bb72-qldpc-campaign"]
    search_space = workspace.search_spaces["bb72-qldpc-campaign"]
    suite = workspace.suites[campaign["default_suite_id"]]
    task = workspace.tasks["bb-css-memory-x-cdep-v1"]
    decoder = workspace.decoders["rbposd-bb72-osd1-v1"]
    reference_decoder = workspace.decoders["rbposd-bb72-osd10-v1"]
    quantum_tanner_decoder = workspace.decoders["rbposd-osd10-v1"]

    assert campaign["family_id"] == "bivariate-bicycle-code"
    assert search_space["candidate_specs"][0]["instance_path"].endswith(
        "bivariate-bicycle-code-m6-n6"
    )
    assert suite["decoder_ids"][0] == "rbposd-bb72-osd1-v1"
    assert "reference_fixture" not in suite["shared_settings"]
    assert task["css_memory"]["observables"] == "required"
    assert task["css_memory"]["seed"] == 12345
    assert task["collection"]["decoder_overrides"]["rbposd-bb72-osd1-v1"] == {
        "batch_size": 16,
        "max_errors": 8,
        "max_shots": 16,
    }
    assert decoder["parameters"]["osd_method"] == "combination_sweep"
    assert decoder["parameters"]["osd_order"] == 1
    assert reference_decoder["parameters"]["osd_order"] == 10
    assert quantum_tanner_decoder["parameters"]["bp_algorithm"] == "min_sum"
    assert quantum_tanner_decoder["parameters"]["osd_method"] == "combination_sweep"
    assert quantum_tanner_decoder["parameters"]["osd_order"] == 10


def test_load_zoo_rejects_instance_matrix_non_binary_entries(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    hz_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "hz.json"
    )
    payload = json.loads(hz_path.read_text())
    payload["data"][0][0] = True
    hz_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="matrix contains non-binary entries"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_matrix_boolean_row_count(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    hx_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "hx.json"
    )
    hx_payload = json.loads(hx_path.read_text())
    hx_payload["n_rows"] = True
    hx_payload["data"] = [hx_payload["data"][0]]
    hx_path.write_text(json.dumps(hx_payload, indent=2) + "\n")

    instance_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "instance.json"
    )
    instance_payload = json.loads(instance_path.read_text())
    instance_payload["derived_properties"]["mx"] = 1
    instance_path.write_text(json.dumps(instance_payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="invalid matrix payload"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_derived_dimension_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    instance_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "instance.json"
    )
    payload = json.loads(instance_path.read_text())
    payload["derived_properties"]["mx"] = 5
    instance_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="instance mx mismatch"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_family_id_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    instance_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "instance.json"
    )
    payload = json.loads(instance_path.read_text())
    payload["family_id"] = "rotated-surface-code"
    instance_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="instance family_id mismatch"):
        load_zoo(work_root)


def test_load_zoo_rejects_variant_family_target_that_is_not_family(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    card_path = work_root / "codes" / "rotated-surface-code" / "card.json"
    card = json.loads(card_path.read_text())
    card["family"] = "rotated-surface-code"
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="family must reference code_family"):
        load_zoo(work_root)


def test_load_zoo_rejects_variant_with_empty_family(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    card_path = work_root / "codes" / "rotated-surface-code" / "card.json"
    card = json.loads(card_path.read_text())
    card["family"] = ""
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="variant card missing family"):
        load_zoo(work_root)


def test_load_zoo_ignores_draft_evidence_files(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    (
        work_root
        / "evidence"
        / "2408.10001"
        / "bivariate-bicycle-code.decoder-claim.01.draft.json"
    ).write_text("{ definitely not valid json }\n")

    dataset = load_zoo(work_root)

    assert "2408.10001:bivariate-bicycle-code.decoder-draft" not in dataset.evidence
    assert sorted(dataset.evidence) == [
        "2308.07915:bivariate-bicycle-code.construction",
        "2308.07915:bivariate-bicycle-code.decoder",
        "2308.07915:bivariate-bicycle-code.distance",
        "2308.07915:bivariate-bicycle-code.parameters",
        "2308.07915:bivariate-bicycle-code.pseudo-thresholds",
        "2308.07915:bivariate-bicycle-code.surface-comparison",
        "2408.10001:bivariate-bicycle-code.parameters",
    ]
