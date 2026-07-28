from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from jsonschema import Draft202012Validator


class IntegrityError(ValueError):
    """Raised when source-of-truth files disagree with each other."""


@dataclass(frozen=True)
class ZooDataset:
    cards: dict[str, dict]
    evidence: dict[str, dict]
    instances: dict[str, LoadedInstance]


@dataclass(frozen=True)
class LoadedInstance:
    payload: dict
    hx_matrix: dict
    hz_matrix: dict


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _validator(schema_path: Path) -> Draft202012Validator:
    return Draft202012Validator(_load_json(schema_path))


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _load_matrix(path: Path) -> dict:
    payload = _load_json(path)
    required_keys = {"format", "n_rows", "n_cols", "data"}
    if not isinstance(payload, dict) or not required_keys.issubset(payload):
        raise IntegrityError(f"invalid matrix payload: {path}")
    if payload["format"] != "dense_binary_matrix":
        raise IntegrityError(f"unsupported matrix format: {path}")
    if not _is_plain_int(payload["n_rows"]) or not _is_plain_int(payload["n_cols"]):
        raise IntegrityError(f"invalid matrix payload: {path}")
    if not isinstance(payload["data"], list):
        raise IntegrityError(f"invalid matrix payload: {path}")
    if payload["n_rows"] != len(payload["data"]):
        raise IntegrityError(f"matrix row count mismatch: {path}")

    for row in payload["data"]:
        if not isinstance(row, list):
            raise IntegrityError(f"invalid matrix payload: {path}")
        if len(row) != payload["n_cols"]:
            raise IntegrityError(f"matrix column mismatch: {path}")
        if any(not _is_plain_int(bit) or bit not in (0, 1) for bit in row):
            raise IntegrityError(f"matrix contains non-binary entries: {path}")

    return payload


def load_zoo(root: Path) -> ZooDataset:
    schema_root = root / "schemas"
    card_validator = _validator(schema_root / "code-card.schema.json")
    evidence_validator = _validator(schema_root / "evidence.schema.json")
    instance_validator = _validator(schema_root / "code-instance.schema.json")

    cards: dict[str, dict] = {}
    evidence_by_id: dict[str, dict] = {}
    instances_by_id: dict[str, dict] = {}

    for card_path in sorted((root / "codes").glob("*/card.json")):
        card = _load_json(card_path)
        if card.get("kind") == "code_variant" and not card.get("family"):
            raise IntegrityError(f"variant card missing family: {card['id']}")
        card_validator.validate(card)
        cards[card["id"]] = card

    for evidence_path in sorted((root / "evidence").glob("*/*.json")):
        if evidence_path.name.endswith(".draft.json"):
            continue
        evidence = _load_json(evidence_path)
        evidence_validator.validate(evidence)

        parent_paper_id = evidence_path.parent.name
        if evidence["paper_id"] != parent_paper_id:
            raise IntegrityError(
                f"paper_id mismatch for {evidence_path}: "
                f"{evidence['paper_id']} != {parent_paper_id}"
            )

        evidence_by_id[evidence["id"]] = evidence

    for instance_path in sorted((root / "codes").glob("*/instances/*/instance.json")):
        instance = _load_json(instance_path)
        instance_validator.validate(instance)

        code_dir = instance_path.parents[2].name
        instance_dir = instance_path.parent.name
        if instance["code_id"] != code_dir:
            raise IntegrityError(
                f"instance code_id mismatch for {instance_path}: "
                f"{instance['code_id']} != {code_dir}"
            )
        if instance["id"] != instance_dir:
            raise IntegrityError(
                f"instance id mismatch for {instance_path}: "
                f"{instance['id']} != {instance_dir}"
            )

        artifact_root = instance_path.parent
        hx_path = artifact_root / instance["artifacts"]["hx"]
        hz_path = artifact_root / instance["artifacts"]["hz"]
        if not hx_path.exists():
            raise IntegrityError(f"missing hx artifact: {hx_path}")
        if not hz_path.exists():
            raise IntegrityError(f"missing hz artifact: {hz_path}")

        hx = _load_matrix(hx_path)
        hz = _load_matrix(hz_path)
        if hx["n_cols"] != hz["n_cols"]:
            raise IntegrityError(f"matrix column mismatch: {hx_path} vs {hz_path}")
        if instance["derived_properties"]["n"] != hx["n_cols"]:
            raise IntegrityError(f"instance n mismatch: {instance_path}")
        if instance["derived_properties"]["mx"] != hx["n_rows"]:
            raise IntegrityError(f"instance mx mismatch: {instance_path}")
        if instance["derived_properties"]["mz"] != hz["n_rows"]:
            raise IntegrityError(f"instance mz mismatch: {instance_path}")

        instances_by_id[instance["id"]] = LoadedInstance(
            payload=instance,
            hx_matrix=hx,
            hz_matrix=hz,
        )

    for card_id, card in cards.items():
        if card.get("family"):
            if card["family"] not in cards:
                raise IntegrityError(f"unknown family for {card_id}: {card['family']}")
            if card["kind"] == "code_variant" and cards[card["family"]]["kind"] != "code_family":
                raise IntegrityError(f"family must reference code_family: {card_id}")

        for evidence_ref in card["evidence_refs"]:
            if evidence_ref not in evidence_by_id:
                raise IntegrityError(f"missing evidence_ref on {card_id}: {evidence_ref}")
            if evidence_by_id[evidence_ref]["paper_id"] not in card["source_refs"]:
                raise IntegrityError(
                    f"source_refs missing paper for {card_id}: "
                    f"{evidence_by_id[evidence_ref]['paper_id']}"
                )

    for evidence_id, evidence in evidence_by_id.items():
        if evidence["code_id"] not in cards:
            raise IntegrityError(f"unknown code_id on {evidence_id}: {evidence['code_id']}")

    for instance_id, instance in instances_by_id.items():
        if instance.payload["code_id"] not in cards:
            raise IntegrityError(
                f"unknown instance code_id on {instance_id}: {instance.payload['code_id']}"
            )

        expected_family_id = (
            cards[instance.payload["code_id"]].get("family") or instance.payload["code_id"]
        )
        if instance.payload["family_id"] != expected_family_id:
            raise IntegrityError(
                f"instance family_id mismatch on {instance_id}: {instance.payload['family_id']}"
            )

    return ZooDataset(cards=cards, evidence=evidence_by_id, instances=instances_by_id)
