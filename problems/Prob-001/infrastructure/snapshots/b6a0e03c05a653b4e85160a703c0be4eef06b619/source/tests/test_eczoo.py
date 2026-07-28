import json
from pathlib import Path

from autoqec_zoo.eczoo import (
    build_eczoo_index,
    build_relations,
    load_eczoo_codes,
    parse_code_file,
    build_eczoo,
    render_eczoo_browse,
)
from autoqec_zoo.eczoo_site import render_eczoo_site

FIXTURES = Path(__file__).parent / "fixtures" / "eczoo"
SCHEMA_ROOT = Path(__file__).parents[1] / "zoo" / "schemas"


def test_parse_code_file_extracts_record():
    raw_codes = FIXTURES / "codes"
    record = parse_code_file(raw_codes / "topo" / "surface.yml", raw_codes)

    assert record["code_id"] == "surface"
    assert record["name"] == "Kitaev surface code"
    assert record["short_name"] == "Surface"
    assert record["family_path"] == ["topo"]
    assert record["introduced"] == r"\cite{arXiv:quant-ph/9707021}"
    assert record["description_excerpt"].startswith("A family of topological CSS")
    assert record["features"]["decoders"] == ["MWPM", "Union-Find"]
    assert record["parents"] == ["qubit_css"]
    assert record["cousins"] == ["toric"]
    assert record["source_path"] == "codes/topo/surface.yml"


def test_load_eczoo_codes_loads_all_and_reports_skips():
    raw_codes = FIXTURES / "codes"
    records, skipped = load_eczoo_codes(raw_codes)

    ids = {r["code_id"] for r in records}
    assert {"surface", "bivariate_bicycle"} <= ids
    assert any("bad.yml" in s for s in skipped)
    total_yml = len(list(raw_codes.rglob("*.yml")))
    assert len(records) + len(skipped) == total_yml


def test_build_relations_adds_inverse_edges():
    records = [
        {"code_id": "surface", "parents": ["qubit_css"], "cousins": ["toric"]},
        {"code_id": "qubit_css", "parents": [], "cousins": []},
        {"code_id": "toric", "parents": [], "cousins": []},
    ]
    edges, unresolved = build_relations(records)

    assert {"source": "surface", "target": "qubit_css", "type": "parent"} in edges
    assert {"source": "qubit_css", "target": "surface", "type": "child"} in edges
    assert {"source": "surface", "target": "toric", "type": "cousin"} in edges
    assert {"source": "toric", "target": "surface", "type": "cousin"} in edges
    assert unresolved == []


def test_build_relations_flags_unresolved_targets():
    records = [{"code_id": "surface", "parents": ["ghost"], "cousins": []}]
    edges, unresolved = build_relations(records)

    assert {"source": "surface", "target": "ghost", "type": "parent"} in edges
    assert "ghost" in unresolved


def test_build_eczoo_index_writes_validated_artifacts(tmp_path):
    out = tmp_path / "index"
    result = build_eczoo_index(
        raw_codes_root=FIXTURES / "codes",
        index_root=out,
        schema_root=SCHEMA_ROOT,
        generated_at="2026-05-29",
    )

    codes = json.loads((out / "eczoo-codes.json").read_text())
    relations = json.loads((out / "eczoo-relations.json").read_text())

    assert codes["generated_at"] == "2026-05-29"
    code_ids = {item["code_id"] for item in codes["items"]}
    assert "surface" in code_ids
    assert any(e["type"] == "child" for e in relations["items"])
    # reconciliation surfaced, not hidden
    assert result["indexed_count"] + result["skipped_count"] == result["input_count"]
    assert result["skipped_count"] >= 1


def test_render_eczoo_browse_groups_by_top_family():
    records = [
        {"code_id": "surface", "name": "Surface", "short_name": "Surface",
         "family_path": ["quantum", "topo"], "description_excerpt": "topological code",
         "parents": ["qubit_css"], "cousins": []},
        {"code_id": "rep", "name": "Repetition", "short_name": None,
         "family_path": ["classical"], "description_excerpt": "repeat bits",
         "parents": [], "cousins": []},
    ]
    md = render_eczoo_browse(records)

    assert "# Error Correction Zoo (mirror)" in md
    assert "## quantum" in md
    assert "## classical" in md
    assert "`surface`" in md
    assert "Surface" in md


def test_render_eczoo_site_embeds_data():
    codes_doc = {"generated_at": "2026-05-29", "items": [
        {"code_id": "surface", "name": "Surface", "short_name": "Surface",
         "family_path": ["quantum"], "introduced": None,
         "description_excerpt": "x", "features": {}, "parents": [], "cousins": [],
         "source_path": "codes/quantum/surface.yml"}
    ]}
    relations_doc = {"generated_at": "2026-05-29", "items": []}
    html, js, css = render_eczoo_site(codes_doc, relations_doc)

    assert "<!doctype html>" in html.lower()
    assert "eczoo" in html.lower()
    assert "EMBEDDED_STATE" in js
    assert "surface" in js  # embedded data
    assert "</script" not in js  # closing tags escaped so the embed can't break out
    assert len(css) > 0


def test_build_eczoo_writes_index_and_views(tmp_path):
    # Arrange a fake zoo root: external/eczoo/raw/codes + schemas.
    zoo_root = tmp_path / "zoo"
    raw_codes = zoo_root / "external" / "eczoo" / "raw" / "codes"
    raw_codes.mkdir(parents=True)
    (raw_codes / "topo").mkdir()
    (raw_codes / "topo" / "surface.yml").write_text(
        (FIXTURES / "codes" / "topo" / "surface.yml").read_text()
    )
    # Copy schemas next to the fake root.
    schemas = zoo_root / "schemas"
    schemas.mkdir()
    for name in ("eczoo-code.schema.json", "eczoo-relation.schema.json"):
        (schemas / name).write_text((SCHEMA_ROOT / name).read_text())

    result = build_eczoo(zoo_root, generated_at="2026-05-29")

    base = zoo_root / "external" / "eczoo"
    assert (base / "index" / "eczoo-codes.json").exists()
    assert (base / "index" / "eczoo-relations.json").exists()
    assert (base / "views" / "browse.md").exists()
    assert (base / "views" / "site" / "index.html").exists()
    assert (base / "views" / "site" / "assets" / "app.js").exists()
    assert (base / "views" / "site" / "assets" / "styles.css").exists()
    assert result["indexed_count"] == 1


def test_code_card_schema_allows_optional_eczoo_ref():
    from jsonschema import Draft202012Validator

    schema = json.loads((SCHEMA_ROOT / "code-card.schema.json").read_text())
    validator = Draft202012Validator(schema)

    base = json.loads((SCHEMA_ROOT.parent / "codes" / "surface-code" / "card.json").read_text())
    # eczoo_ref is optional: present is valid
    with_ref = {**base, "eczoo_ref": "surface"}
    validator.validate(with_ref)
    # absent is still valid
    validator.validate(base)
