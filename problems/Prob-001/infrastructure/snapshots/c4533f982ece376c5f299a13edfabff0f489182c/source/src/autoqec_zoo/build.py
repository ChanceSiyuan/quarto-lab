from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from autoqec_zoo.load import ZooDataset, load_zoo
from autoqec_zoo.render_markdown import render_card_markdown
from autoqec_zoo.render_site import render_site_assets


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def _build_code_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        instance_count = sum(
            1
            for instance in dataset.instances.values()
            if instance.payload["code_id"] == card["id"]
        )
        items.append(
            {
                "id": card["id"],
                "title": card["title"],
                "kind": card["kind"],
                "family": card.get("family"),
                "summary": card["summary"],
                "source_count": len(card["source_refs"]),
                "evidence_count": len(card["evidence_refs"]),
                "instance_count": instance_count,
                "known_decoders": card["known_decoders"],
            }
        )
    return {"generated_at": generated_at, "items": items}


def _build_family_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        if card["kind"] != "code_family":
            continue
        variants = sorted(
            variant["id"]
            for variant in dataset.cards.values()
            if variant.get("family") == card["id"]
        )
        items.append({"id": card["id"], "title": card["title"], "variant_ids": variants})
    return {"generated_at": generated_at, "items": items}


def _build_relation_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        for relation in card["relations"]:
            if relation["type"] == "has_variant":
                continue
            items.append(
                {
                    "source_id": card["id"],
                    "type": relation["type"],
                    "target_id": relation["target"],
                }
            )
    return {"generated_at": generated_at, "items": items}


def _build_evidence_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for evidence in sorted(dataset.evidence.values(), key=lambda item: item["id"]):
        items.append(
            {
                "id": evidence["id"],
                "paper_id": evidence["paper_id"],
                "code_id": evidence["code_id"],
                "claim_type": evidence["claim_type"],
                "title": evidence["title"],
                "uncertainty_flags": evidence["uncertainty_flags"],
            }
        )
    return {"generated_at": generated_at, "items": items}


def _build_instance_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for instance in sorted(dataset.instances.values(), key=lambda item: item.payload["id"]):
        payload = instance.payload
        derived = payload["derived_properties"]
        items.append(
            {
                "id": payload["id"],
                "code_id": payload["code_id"],
                "family_id": payload["family_id"],
                "title": payload["title"],
                "distance": derived["distance"],
                "n": derived["n"],
                "mx": derived["mx"],
                "mz": derived["mz"],
            }
        )
    return {"generated_at": generated_at, "items": items}


def _render_browse_markdown(dataset: ZooDataset) -> str:
    lines = ["# QEC Zoo Browse", "", "## By Code", ""]
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        lines.append(f"- `{card['id']}` — {card['summary']}")
    lines.extend(["", "## Generated Instances", ""])
    instance_items = _build_instance_index(dataset, generated_at="")["items"]
    if instance_items:
        for item in instance_items:
            lines.append(
                "- "
                f"`{item['id']}` — `{item['code_id']}`, "
                f"distance={item['distance']}, n={item['n']}"
            )
    else:
        lines.append("- No generated instances recorded.")
    lines.extend(["", "## By Paper", ""])
    for evidence in sorted(dataset.evidence.values(), key=lambda item: item["id"]):
        lines.append(f"- `{evidence['paper_id']}` -> `{evidence['code_id']}` ({evidence['claim_type']})")
    return "\n".join(lines).rstrip() + "\n"


def _build_site_state(dataset: ZooDataset, generated_at: str) -> dict:
    code_index = _build_code_index(dataset, generated_at)
    instance_items_by_code: dict[str, list[dict]] = {}
    for item in _build_instance_index(dataset, generated_at)["items"]:
        instance_items_by_code.setdefault(item["code_id"], []).append(item)
    family_map = {
        card["id"]: card["title"]
        for card in dataset.cards.values()
        if card["kind"] == "code_family"
    }
    codes = []

    for index_item in code_index["items"]:
        card = dataset.cards[index_item["id"]]
        family_id = card.get("family") or (card["id"] if card["kind"] == "code_family" else None)
        evidence = []
        for evidence_ref in card["evidence_refs"]:
            record = dataset.evidence[evidence_ref]
            evidence.append(
                {
                    "id": record["id"],
                    "paper_id": record["paper_id"],
                    "claim_type": record["claim_type"],
                    "title": record["title"],
                    "statement": record["claim"]["statement"],
                    "decoder": record["context"]["decoder"],
                    "noise_model": record["context"]["noise_model"],
                    "distance_method": record["context"]["distance_method"],
                    "quote_ref": record["provenance"]["quote_ref"],
                    "uncertainty_flags": record["uncertainty_flags"],
                }
            )

        codes.append(
            {
                **index_item,
                "aliases": card["aliases"],
                "construction": card["construction"],
                "parameters": card["parameters"],
                "assumptions": card["assumptions"],
                "distance_methods": card["distance_methods"],
                "relations": card["relations"],
                "source_refs": card["source_refs"],
                "family_id": family_id,
                "family_title": family_map.get(family_id),
                "evidence": evidence,
                "instances": instance_items_by_code.get(card["id"], []),
            }
        )

    families = [
        {"id": family_id, "title": family_map[family_id]}
        for family_id in sorted(family_map)
    ]

    return {"generated_at": generated_at, "families": families, "codes": codes}


def build_zoo(root: Path, generated_at: str) -> None:
    dataset = load_zoo(root)
    view_schema = json.loads((root / "schemas" / "view-index.schema.json").read_text())
    validator = Draft202012Validator(view_schema)

    views = {
        "code-index.json": _build_code_index(dataset, generated_at),
        "family-index.json": _build_family_index(dataset, generated_at),
        "relation-index.json": _build_relation_index(dataset, generated_at),
        "evidence-index.json": _build_evidence_index(dataset, generated_at),
        "instance-index.json": _build_instance_index(dataset, generated_at),
    }

    for filename, payload in views.items():
        validator.validate(payload)
        _write_json(root / "views" / filename, payload)

    for card in dataset.cards.values():
        evidence_records = [dataset.evidence[item] for item in card["evidence_refs"]]
        instance_records = [
            instance.payload
            for instance in dataset.instances.values()
            if instance.payload["code_id"] == card["id"]
        ]
        (root / "codes" / card["id"] / "card.md").write_text(
            render_card_markdown(card, evidence_records, instance_records)
        )

    (root / "views" / "browse.md").write_text(_render_browse_markdown(dataset))

    site_root = root / "views" / "site"
    html, js, css = render_site_assets(_build_site_state(dataset, generated_at))
    _write_text(site_root / "index.html", html)
    _write_text(site_root / "assets" / "app.js", js)
    _write_text(site_root / "assets" / "styles.css", css)
