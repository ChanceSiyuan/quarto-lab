from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[1]
ZOO_ROOT = REPO_ROOT / "zoo"
SKILLS_ROOT = REPO_ROOT / "skills"
AGENTS_SKILLS_ROOT = REPO_ROOT / ".agents" / "skills"
CLAUDE_SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"
PROJECT_SKILL_NAMES = [
    "onboard",
    "extract-zoo-evidence",
    "setup-tensorqec",
    "generate-code-instance",
    "compute-code-distance",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_instance_matrix_payloads(
    instance_root: Path, artifacts: dict[str, str]
) -> tuple[dict, dict]:
    hx_path = instance_root / artifacts["hx"]
    hz_path = instance_root / artifacts["hz"]

    assert hx_path.is_file()
    assert hz_path.is_file()

    return _load_json(hx_path), _load_json(hz_path)


def _assert_dense_binary_matrix_payload(payload: dict, *, label: str) -> None:
    assert payload["format"] == "dense_binary_matrix", label
    assert payload["n_rows"] == len(payload["data"]), label
    assert all(len(row) == payload["n_cols"] for row in payload["data"]), label
    assert all(bit in [0, 1] for row in payload["data"] for bit in row), label


def test_seed_cards_and_evidence_validate_against_checked_in_schemas() -> None:
    code_schema = _load_json(ZOO_ROOT / "schemas" / "code-card.schema.json")
    evidence_schema = _load_json(ZOO_ROOT / "schemas" / "evidence.schema.json")
    view_index_schema = _load_json(ZOO_ROOT / "schemas" / "view-index.schema.json")

    code_validator = Draft202012Validator(code_schema)
    evidence_validator = Draft202012Validator(evidence_schema)
    view_index_validator = Draft202012Validator(view_index_schema)

    for rel_path in [
        "codes/surface-code/card.json",
        "codes/rotated-surface-code/card.json",
        "codes/bivariate-bicycle-code/card.json",
    ]:
        code_validator.validate(_load_json(ZOO_ROOT / rel_path))

    evidence_validator.validate(
        _load_json(ZOO_ROOT / "evidence/2408.10001/bivariate-bicycle-code.parameters.json")
    )
    for rel_path in [
        "evidence/2308.07915/bivariate-bicycle-code.construction-note.01.json",
        "evidence/2308.07915/bivariate-bicycle-code.decoder-claim.01.json",
        "evidence/2308.07915/bivariate-bicycle-code.distance-claim.01.json",
        "evidence/2308.07915/bivariate-bicycle-code.parameter-claim.01.json",
        "evidence/2308.07915/bivariate-bicycle-code.relation-claim.01.json",
        "evidence/2308.07915/bivariate-bicycle-code.threshold-evidence.01.json",
    ]:
        evidence_validator.validate(_load_json(ZOO_ROOT / rel_path))

    with pytest.raises(ValidationError):
        code_validator.validate(
            {
                "id": "variant-without-family",
                "kind": "code_variant",
                "title": "Variant Without Family",
                "aliases": [],
                "summary": "Intentional negative case for schema coverage.",
                "construction": {
                    "type": "example",
                    "description": "Minimal example payload.",
                },
                "parameters": {},
                "assumptions": [],
                "known_decoders": [],
                "distance_methods": [],
                "relations": [],
                "evidence_refs": [],
                "source_refs": [],
                "updated_at": "2026-05-27",
            }
        )

    view_index_validator.validate(
        {
            "generated_at": "2026-05-27",
            "items": [
                {
                    "id": "surface-code",
                    "label": "Surface Code",
                }
            ],
        }
    )


def test_seed_instance_validates_against_checked_in_instance_schema() -> None:
    instance_schema = _load_json(ZOO_ROOT / "schemas" / "code-instance.schema.json")
    instance_validator = Draft202012Validator(instance_schema)

    instance_root = (
        ZOO_ROOT
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    instance_payload = _load_json(instance_root / "instance.json")
    instance_validator.validate(instance_payload)

    hx_payload, hz_payload = _load_instance_matrix_payloads(
        instance_root, instance_payload["artifacts"]
    )
    _assert_dense_binary_matrix_payload(hx_payload, label="hx")
    _assert_dense_binary_matrix_payload(hz_payload, label="hz")

    derived_properties = instance_payload["derived_properties"]
    assert derived_properties["distance"] == 3
    assert hx_payload["n_cols"] == hz_payload["n_cols"]
    assert derived_properties["n"] == hx_payload["n_cols"]
    assert derived_properties["n"] == hz_payload["n_cols"]
    assert derived_properties["mx"] == hx_payload["n_rows"]
    assert derived_properties["mz"] == hz_payload["n_rows"]


def test_instance_schema_rejects_unknown_generator() -> None:
    instance_schema = _load_json(ZOO_ROOT / "schemas" / "code-instance.schema.json")
    instance_validator = Draft202012Validator(instance_schema)

    instance_root = (
        ZOO_ROOT
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    instance_payload = _load_json(instance_root / "instance.json")
    instance_payload["provenance"]["generator"] = "ad-hoc-manual"

    with pytest.raises(ValidationError):
        instance_validator.validate(instance_payload)


def test_instance_schema_rejects_missing_or_zero_distance() -> None:
    instance_schema = _load_json(ZOO_ROOT / "schemas" / "code-instance.schema.json")
    instance_validator = Draft202012Validator(instance_schema)

    instance_root = (
        ZOO_ROOT
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    instance_payload = _load_json(instance_root / "instance.json")

    missing_distance_payload = json.loads(json.dumps(instance_payload))
    del missing_distance_payload["derived_properties"]["distance"]

    with pytest.raises(ValidationError):
        instance_validator.validate(missing_distance_payload)

    zero_distance_payload = json.loads(json.dumps(instance_payload))
    zero_distance_payload["derived_properties"]["distance"] = 0

    with pytest.raises(ValidationError):
        instance_validator.validate(zero_distance_payload)


def test_tensorqec_environment_files_exist() -> None:
    env_root = REPO_ROOT / "julia" / "tensorqec_env"

    assert (env_root / "Project.toml").is_file()
    assert (env_root / "Manifest.toml").is_file()
    assert (env_root / "scripts" / "compute_distance.jl").is_file()
    assert (env_root / "scripts" / "setup.jl").is_file()
    assert (env_root / "scripts" / "support.jl").is_file()


def test_repo_docs_reference_tensorqec_skills() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()
    agents = (REPO_ROOT / "AGENTS.md").read_text()

    assert "setup-tensorqec" in readme
    assert "generate-code-instance" in readme
    assert "compute-code-distance" in readme
    assert "setup-tensorqec" in claude
    assert "generate-code-instance" in claude
    assert "compute-code-distance" in claude
    assert agents.strip() == "@CLAUDE.md"


def test_readme_documents_onboard_flow() -> None:
    readme = (REPO_ROOT / "README.md").read_text()

    assert "/onboard" in readme
    assert "onboard me" in readme
    assert "zlp-harness:zlp-onboard" in readme


def test_repo_uses_single_project_kb_layout() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()
    notes = (REPO_ROOT / ".knowledge" / "NOTES.md").read_text()
    bibliography = (REPO_ROOT / "ref.bib").read_text()

    assert not (REPO_ROOT / ".claude" / "survey").exists()
    assert "ref.bib" in readme
    assert ".knowledge/NOTES.md" in claude
    assert "ref.bib" in claude
    assert "No LaTeX draft yet (`main.tex`, `ref.bib`, etc.)" not in claude
    assert (
        "Finite-code transversal gates: detection, search targets, and an AutoQEC workflow"
        in notes
    )
    assert "Finite-length BB and LP codes for exact distance and transversal gates" in notes
    assert "QEC Code Discovery Patterns" in notes
    assert notes.count("# High-distance codes with transversal logical operations") == 1
    assert notes.count("Imported from legacy survey `.claude/survey/") == 4
    assert "@article{Rains1997," in bibliography
    assert "@article{Cross2009," in bibliography
    assert "@article{Chuang2009," in bibliography
    assert "@article{Crosswhite2011," in bibliography
    assert "@article{Cao2022," in bibliography
    assert "@article{Olle2024," in bibliography
    assert "@article{Haah2021," in bibliography


def test_generate_code_instance_skill_docs_cover_distance_threshold() -> None:
    skill_doc = (SKILLS_ROOT / "generate-code-instance" / "SKILL.md").read_text()

    assert "derived_properties.n <= 200" in skill_doc
    assert "derived_properties.n > 200" in skill_doc
    assert "compute-code-distance" in skill_doc


def test_project_skills_live_under_root_and_are_exposed_to_agents() -> None:
    for skill_name in PROJECT_SKILL_NAMES:
        skill_dir = SKILLS_ROOT / skill_name
        agents_skill_dir = AGENTS_SKILLS_ROOT / skill_name
        claude_skill_dir = CLAUDE_SKILLS_ROOT / skill_name

        assert (skill_dir / "SKILL.md").is_file()
        assert AGENTS_SKILLS_ROOT.is_symlink()
        assert AGENTS_SKILLS_ROOT.resolve() == SKILLS_ROOT.resolve()
        assert CLAUDE_SKILLS_ROOT.is_symlink()
        assert CLAUDE_SKILLS_ROOT.resolve() == SKILLS_ROOT.resolve()
        assert agents_skill_dir.exists()
        assert claude_skill_dir.exists()
        assert agents_skill_dir.resolve() == skill_dir.resolve()
        assert claude_skill_dir.resolve() == skill_dir.resolve()
