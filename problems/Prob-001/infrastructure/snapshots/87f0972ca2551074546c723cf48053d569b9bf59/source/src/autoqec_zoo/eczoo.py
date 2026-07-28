from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from autoqec_zoo.eczoo_site import render_eczoo_site

_FEATURE_KEYS = (
    "rate",
    "encoders",
    "decoders",
    "fault_tolerance",
    "transversal_gates",
    "general_gates",
    "threshold",
    "code_capacity_threshold",
)
_EXCERPT_LEN = 280


def _relation_ids(relations: dict, key: str) -> list[str]:
    entries = (relations or {}).get(key) or []
    ids = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("code_id"):
            ids.append(str(entry["code_id"]))
    return ids


def _excerpt(text) -> str:
    if not text:
        return ""
    flat = " ".join(str(text).split())
    if len(flat) <= _EXCERPT_LEN:
        return flat
    return flat[:_EXCERPT_LEN].rstrip() + "…"


def _features(raw_features) -> dict:
    raw_features = raw_features or {}
    out = {}
    for key in _FEATURE_KEYS:
        if key not in raw_features:
            continue
        value = raw_features[key]
        if isinstance(value, list):
            out[key] = [" ".join(str(item).split()) for item in value]
        elif value is not None:
            out[key] = " ".join(str(value).split())
    return out


def parse_code_file(path: Path, raw_codes_root: Path) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    rel_path = path.relative_to(raw_codes_root)
    family_path = list(rel_path.parts[:-1])
    relations = data.get("relations") or {}
    return {
        "code_id": str(data["code_id"]),
        "name": str(data.get("name") or data["code_id"]),
        "short_name": (str(data["short_name"]) if data.get("short_name") else None),
        "family_path": family_path,
        "introduced": (str(data["introduced"]) if data.get("introduced") else None),
        "description_excerpt": _excerpt(data.get("description")),
        "features": _features(data.get("features")),
        "parents": _relation_ids(relations, "parents"),
        "cousins": _relation_ids(relations, "cousins"),
        "source_path": "codes/" + "/".join(rel_path.parts),
    }


def load_eczoo_codes(raw_codes_root: Path) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    skipped: list[str] = []
    for path in sorted(raw_codes_root.rglob("*.yml")):
        try:
            records.append(parse_code_file(path, raw_codes_root))
        except (KeyError, yaml.YAMLError, ValueError) as exc:
            skipped.append(f"{path}: {exc}")
    return records, skipped


def build_relations(records: list[dict]) -> tuple[list[dict], list[str]]:
    known = {r["code_id"] for r in records}
    edge_set: set[tuple[str, str, str]] = set()
    unresolved: set[str] = set()

    for record in records:
        source = record["code_id"]
        for parent in record.get("parents", []):
            edge_set.add((source, parent, "parent"))
            edge_set.add((parent, source, "child"))
            if parent not in known:
                unresolved.add(parent)
        for cousin in record.get("cousins", []):
            edge_set.add((source, cousin, "cousin"))
            edge_set.add((cousin, source, "cousin"))
            if cousin not in known:
                unresolved.add(cousin)

    edges = [
        {"source": s, "target": t, "type": k}
        for (s, t, k) in sorted(edge_set)
    ]
    return edges, sorted(unresolved)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_eczoo_index(
    raw_codes_root: Path,
    index_root: Path,
    schema_root: Path,
    generated_at: str,
) -> dict:
    records, skipped = load_eczoo_codes(raw_codes_root)
    edges, unresolved = build_relations(records)

    codes_doc = {"generated_at": generated_at, "items": records}
    relations_doc = {"generated_at": generated_at, "items": edges}

    code_validator = Draft202012Validator(
        json.loads((schema_root / "eczoo-code.schema.json").read_text())
    )
    relation_validator = Draft202012Validator(
        json.loads((schema_root / "eczoo-relation.schema.json").read_text())
    )
    code_validator.validate(codes_doc)
    relation_validator.validate(relations_doc)

    _write_json(index_root / "eczoo-codes.json", codes_doc)
    _write_json(index_root / "eczoo-relations.json", relations_doc)

    return {
        "input_count": len(records) + len(skipped),
        "indexed_count": len(records),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "edge_count": len(edges),
        "unresolved": unresolved,
    }


def render_eczoo_browse(records: list[dict]) -> str:
    groups: dict[str, list[dict]] = {}
    for record in records:
        top = record["family_path"][0] if record["family_path"] else "(root)"
        groups.setdefault(top, []).append(record)

    lines = [
        "# Error Correction Zoo (mirror)",
        "",
        "Derived from The Error Correction Zoo (CC-BY-SA 4.0). See `../NOTICE.md`.",
        "",
    ]
    for top in sorted(groups):
        lines.append(f"## {top}")
        lines.append("")
        for record in sorted(groups[top], key=lambda r: r["code_id"]):
            label = record["name"]
            lines.append(f"- `{record['code_id']}` — {label}: {record['description_excerpt']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def build_eczoo(zoo_root: Path, generated_at: str) -> dict:
    base = zoo_root / "external" / "eczoo"
    raw_codes = base / "raw" / "codes"
    if not raw_codes.exists():
        raise FileNotFoundError(
            f"eczoo raw data not found at {raw_codes}; run `make eczoo-fetch` first"
        )

    result = build_eczoo_index(
        raw_codes_root=raw_codes,
        index_root=base / "index",
        schema_root=zoo_root / "schemas",
        generated_at=generated_at,
    )

    codes_doc = json.loads((base / "index" / "eczoo-codes.json").read_text())
    relations_doc = json.loads((base / "index" / "eczoo-relations.json").read_text())

    _write_text(base / "views" / "browse.md", render_eczoo_browse(codes_doc["items"]))

    html, js, css = render_eczoo_site(codes_doc, relations_doc)
    site = base / "views" / "site"
    _write_text(site / "index.html", html)
    _write_text(site / "assets" / "app.js", js)
    _write_text(site / "assets" / "styles.css", css)

    return result
