from __future__ import annotations

import json
import shutil
from pathlib import Path

from autoqec_zoo.build import build_zoo


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_writes_indexes_markdown_and_browse_page(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-27")

    code_index = json.loads((work_root / "views" / "code-index.json").read_text())
    family_index = json.loads((work_root / "views" / "family-index.json").read_text())
    relation_index = json.loads((work_root / "views" / "relation-index.json").read_text())
    evidence_index = json.loads((work_root / "views" / "evidence-index.json").read_text())
    card_md = (work_root / "codes" / "bivariate-bicycle-code" / "card.md").read_text()
    browse_md = (work_root / "views" / "browse.md").read_text()

    assert code_index["generated_at"] == "2026-05-27"
    assert [item["id"] for item in code_index["items"]] == [
        "bivariate-bicycle-code",
        "rotated-surface-code",
        "surface-code",
    ]
    code_items = {item["id"]: item for item in code_index["items"]}
    assert code_items["bivariate-bicycle-code"]["instance_count"] == 1
    assert code_items["rotated-surface-code"]["instance_count"] == 6
    assert code_items["surface-code"]["instance_count"] == 0
    family_items = {item["id"]: item for item in family_index["items"]}
    assert family_items["surface-code"]["variant_ids"] == ["rotated-surface-code"]
    assert relation_index["items"][0] == {
        "source_id": "rotated-surface-code",
        "type": "variant_of",
        "target_id": "surface-code",
    }
    assert evidence_index["items"][0]["id"] == "2308.07915:bivariate-bicycle-code.construction"
    assert "## Family, Aliases, and Kind" in card_md
    assert "## Construction" in card_md
    assert "## Parameter Formulas" in card_md
    assert "## Assumptions" in card_md
    assert "## Known Decoders" in card_md
    assert "## Distance Methods" in card_md
    assert "## Relations" in card_md
    assert "## Linked Evidence" in card_md
    assert "## Source Papers" in card_md
    assert card_md.index("## Family, Aliases, and Kind") < card_md.index("## Construction")
    assert card_md.index("## Construction") < card_md.index("## Parameter Formulas")
    assert card_md.index("## Parameter Formulas") < card_md.index("## Assumptions")
    assert card_md.index("## Assumptions") < card_md.index("## Known Decoders")
    assert card_md.index("## Known Decoders") < card_md.index("## Distance Methods")
    assert card_md.index("## Distance Methods") < card_md.index("## Relations")
    assert card_md.index("## Relations") < card_md.index("## Linked Evidence")
    assert card_md.index("## Linked Evidence") < card_md.index("## Source Papers")
    assert (
        "The paper defines BB codes as CSS LDPC codes QC(A,B)"
        in card_md.split("## Linked Evidence", 1)[1]
    )
    assert "# QEC Zoo Browse" in browse_md
    assert "## Generated Instances" in browse_md
    assert "`bivariate-bicycle-code-m6-n6`" in browse_md
    assert "`rotated-surface-code-d3`" in browse_md
    assert "`rotated-surface-code-d5`" in browse_md
    assert "`rotated-surface-code-d7`" in browse_md
    assert "`rotated-surface-d3-example`" in browse_md
    assert "`rotated-surface-d5-example`" in browse_md
    assert "`rotated-surface-d7-example`" in browse_md


def test_build_writes_instance_index(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-28")

    instance_index = json.loads((work_root / "views" / "instance-index.json").read_text())
    assert instance_index["generated_at"] == "2026-05-28"
    assert instance_index["items"] == [
        {
            "id": "bivariate-bicycle-code-m6-n6",
            "code_id": "bivariate-bicycle-code",
            "family_id": "bivariate-bicycle-code",
            "title": "Bivariate Bicycle Code [[72,12,6]]",
            "distance": 6,
            "n": 72,
            "mx": 36,
            "mz": 36,
        },
        {
            "id": "rotated-surface-code-d3",
            "code_id": "rotated-surface-code",
            "family_id": "surface-code",
            "title": "Rotated Surface Code d=3",
            "distance": 3,
            "n": 9,
            "mx": 4,
            "mz": 4,
        },
        {
            "id": "rotated-surface-code-d5",
            "code_id": "rotated-surface-code",
            "family_id": "surface-code",
            "title": "Rotated Surface Code d=5",
            "distance": 5,
            "n": 25,
            "mx": 12,
            "mz": 12,
        },
        {
            "id": "rotated-surface-code-d7",
            "code_id": "rotated-surface-code",
            "family_id": "surface-code",
            "title": "Rotated Surface Code d=7",
            "distance": 7,
            "n": 49,
            "mx": 24,
            "mz": 24,
        },
        {
            "id": "rotated-surface-d3-example",
            "code_id": "rotated-surface-code",
            "family_id": "surface-code",
            "title": "Rotated Surface Code d=3",
            "distance": 3,
            "n": 9,
            "mx": 4,
            "mz": 4,
        },
        {
            "id": "rotated-surface-d5-example",
            "code_id": "rotated-surface-code",
            "family_id": "surface-code",
            "title": "Rotated Surface Code d=5",
            "distance": 5,
            "n": 25,
            "mx": 12,
            "mz": 12,
        },
        {
            "id": "rotated-surface-d7-example",
            "code_id": "rotated-surface-code",
            "family_id": "surface-code",
            "title": "Rotated Surface Code d=7",
            "distance": 7,
            "n": 49,
            "mx": 24,
            "mz": 24,
        },
    ]


def test_build_card_markdown_includes_instance_summary(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-28")

    card_md = (work_root / "codes" / "rotated-surface-code" / "card.md").read_text()
    assert "## Generated Instances" in card_md
    assert "`rotated-surface-code-d3`" in card_md
    assert "`rotated-surface-code-d5`" in card_md
    assert "`rotated-surface-code-d7`" in card_md
    assert "`rotated-surface-d3-example`" in card_md


def test_build_card_markdown_includes_instance_distance_when_present(tmp_path: Path) -> None:
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
    instance_payload = json.loads(instance_path.read_text())
    instance_payload["derived_properties"]["distance"] = 3
    instance_path.write_text(json.dumps(instance_payload, indent=2) + "\n")

    build_zoo(work_root, generated_at="2026-05-28")

    card_md = (work_root / "codes" / "rotated-surface-code" / "card.md").read_text()
    instance_index = json.loads((work_root / "views" / "instance-index.json").read_text())

    assert "distance=3" in card_md
    indexed = {item["id"]: item for item in instance_index["items"]}
    assert indexed["rotated-surface-code-d3"]["distance"] == 3


def test_build_aggregates_multiple_evidence_records_for_one_code(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    extra_evidence = {
        "id": "2408.10001:bivariate-bicycle-code.decoder",
        "paper_id": "2408.10001",
        "code_id": "bivariate-bicycle-code",
        "claim_type": "decoder_claim",
        "title": "Decoder note for finite-length BB codes",
        "context": {
            "noise_model": "depolarizing noise",
            "decoder": "belief propagation",
            "distance_method": None,
            "assumptions": ["finite-length numerical study"],
            "parameter_point": {"instance_keys": ["L18-K8-D4"]},
        },
        "claim": {
            "statement": "The paper discusses decoder behavior for representative finite-length instances.",
            "value": None,
            "unit": None,
            "qualifiers": ["paper-local decoder evidence"],
        },
        "provenance": {
            "section": "Decoder discussion",
            "quote_ref": "decoder:p6:para1",
            "confidence": "medium",
        },
        "uncertainty_flags": [],
    }
    (work_root / "evidence" / "2408.10001" / "bivariate-bicycle-code.decoder.json").write_text(
        json.dumps(extra_evidence, indent=2) + "\n"
    )

    card_path = work_root / "codes" / "bivariate-bicycle-code" / "card.json"
    card = json.loads(card_path.read_text())
    card["evidence_refs"].append("2408.10001:bivariate-bicycle-code.decoder")
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    build_zoo(work_root, generated_at="2026-05-27")

    code_index = json.loads((work_root / "views" / "code-index.json").read_text())
    code_items = {item["id"]: item for item in code_index["items"]}
    assert code_items["bivariate-bicycle-code"]["evidence_count"] == 8


def test_build_ignores_draft_evidence_files(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    draft_evidence = {
        "id": "2408.10001:bivariate-bicycle-code.threshold-draft",
        "paper_id": "2408.10001",
        "code_id": "bivariate-bicycle-code",
        "claim_type": "threshold_evidence",
        "title": "Draft threshold note",
        "context": {
            "noise_model": "phenomenological noise",
            "decoder": "belief propagation",
            "distance_method": None,
            "assumptions": ["draft only"],
            "parameter_point": {"distance_values": [8, 10, 12]},
        },
        "claim": {
            "statement": "Draft threshold claim.",
            "value": 0.008,
            "unit": "physical_error_rate",
            "qualifiers": ["draft only"],
        },
        "provenance": {
            "section": "Draft section",
            "quote_ref": "draft:p2:para1",
            "confidence": "low",
        },
        "uncertainty_flags": [],
        "approval_notes": "do not include in build",
    }
    (
        work_root
        / "evidence"
        / "2408.10001"
        / "bivariate-bicycle-code.threshold-evidence.01.draft.json"
    ).write_text(json.dumps(draft_evidence, indent=2) + "\n")

    build_zoo(work_root, generated_at="2026-05-27")

    evidence_index = json.loads((work_root / "views" / "evidence-index.json").read_text())
    ids = [item["id"] for item in evidence_index["items"]]

    assert "2408.10001:bivariate-bicycle-code.threshold-draft" not in ids


def test_build_is_deterministic_for_same_input(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-27")
    first_code_index = (work_root / "views" / "code-index.json").read_text()
    first_browse = (work_root / "views" / "browse.md").read_text()

    build_zoo(work_root, generated_at="2026-05-27")
    second_code_index = (work_root / "views" / "code-index.json").read_text()
    second_browse = (work_root / "views" / "browse.md").read_text()

    assert second_code_index == first_code_index
    assert second_browse == first_browse


def test_conflicting_claims_stay_out_of_canonical_facts(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    conflict_evidence = {
        "id": "2408.10001:bivariate-bicycle-code.threshold-conflict",
        "paper_id": "2408.10001",
        "code_id": "bivariate-bicycle-code",
        "claim_type": "threshold_evidence",
        "title": "Conflicting threshold estimate",
        "context": {
            "noise_model": "phenomenological noise",
            "decoder": "belief propagation",
            "distance_method": None,
            "assumptions": ["finite-size scaling fit"],
            "parameter_point": {"distance_values": [8, 10, 12]},
        },
        "claim": {
            "statement": "Threshold is reported around 0.8% under a paper-specific fit.",
            "value": 0.008,
            "unit": "physical_error_rate",
            "qualifiers": ["conflicting threshold estimate"],
        },
        "provenance": {
            "section": "Threshold results",
            "quote_ref": "threshold:p7:para2",
            "confidence": "medium",
        },
        "uncertainty_flags": ["conflicting_claims"],
    }
    (
        work_root
        / "evidence"
        / "2408.10001"
        / "bivariate-bicycle-code.threshold-conflict.json"
    ).write_text(json.dumps(conflict_evidence, indent=2) + "\n")

    card_path = work_root / "codes" / "bivariate-bicycle-code" / "card.json"
    card = json.loads(card_path.read_text())
    card["evidence_refs"].append("2408.10001:bivariate-bicycle-code.threshold-conflict")
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    build_zoo(work_root, generated_at="2026-05-27")

    card_md = (work_root / "codes" / "bivariate-bicycle-code" / "card.md").read_text()
    canonical_section, evidence_section = card_md.split("## Linked Evidence", 1)

    assert "Threshold is reported around 0.8% under a paper-specific fit." not in canonical_section
    assert "Threshold is reported around 0.8% under a paper-specific fit." in evidence_section
