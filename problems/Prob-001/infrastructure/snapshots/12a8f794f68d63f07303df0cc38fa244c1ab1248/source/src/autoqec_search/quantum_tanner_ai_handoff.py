from __future__ import annotations

import json
import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.quantum_tanner_proposals import (
    VALIDATOR_VERSION,
    QuantumTannerProposalValidationError,
    validate_quantum_tanner_proposal,
)


PROPOSAL_SCHEMA_RELATIVE_PATH = Path(
    "benchmarks/schemas/quantum-tanner-proposal.schema.json"
)
AI_BATCH_SCHEMA_ID = (
    "https://autoqec.local/schemas/quantum-tanner-ai-batch-response.schema.json"
)
_SAFE_PROPOSAL_ID_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_INGEST_COMMAND_OUTPUTS = (
    "accepted",
    "rejected",
    "duplicates",
    "summary.json",
    "constraints.json",
    "response_schema.json",
)
_UNSUPPORTED_STRUCTURED_OUTPUT_KEYWORDS = frozenset(
    {
        "allOf",
        "contains",
        "dependentRequired",
        "dependentSchemas",
        "else",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "if",
        "maxContains",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minContains",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "multipleOf",
        "not",
        "pattern",
        "patternProperties",
        "propertyNames",
        "then",
        "unevaluatedProperties",
        "uniqueItems",
    }
)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} must contain a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _compact_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    next_prompt_context = payload.get("next_prompt_context")
    if isinstance(next_prompt_context, dict):
        accepted_fingerprints = next_prompt_context.get(
            "accepted_proposal_fingerprints"
        )
        rejection_kinds = next_prompt_context.get("rejection_kinds")
    else:
        accepted_fingerprints = payload.get("accepted_fingerprints")
        rejection_kinds = payload.get("rejection_kinds")

    if not isinstance(accepted_fingerprints, list):
        accepted_fingerprints = [
            str(record["fingerprint"])
            for record in payload.get("accepted_records", [])
            if isinstance(record, dict) and isinstance(record.get("fingerprint"), str)
        ]

    if not isinstance(rejection_kinds, dict):
        counts: Counter[str] = Counter()
        for key in ("rejected_records", "duplicate_records"):
            for record in payload.get(key, []):
                if isinstance(record, dict) and isinstance(record.get("error_kind"), str):
                    counts[str(record["error_kind"])] += 1
        rejection_kinds = dict(sorted(counts.items()))

    return {
        "accepted_fingerprints": [str(value) for value in accepted_fingerprints],
        "rejection_kinds": {
            str(key): int(value)
            for key, value in sorted(rejection_kinds.items())
            if isinstance(value, int)
        },
    }


def _to_structured_output_schema(schema: object) -> object:
    if isinstance(schema, list):
        return [_to_structured_output_schema(value) for value in schema]
    if not isinstance(schema, dict):
        return schema

    normalized = {
        key: _to_structured_output_schema(value)
        for key, value in schema.items()
        if key not in _UNSUPPORTED_STRUCTURED_OUTPUT_KEYWORDS
    }
    if "type" not in normalized:
        literal_types: set[str] = set()
        if "const" in normalized:
            literal_types.add(_json_schema_type(normalized["const"]))
        enum_values = normalized.get("enum")
        if isinstance(enum_values, list) and enum_values:
            literal_types.update(_json_schema_type(value) for value in enum_values)
        if len(literal_types) == 1:
            normalized["type"] = literal_types.pop()
    properties = normalized.get("properties")
    if isinstance(properties, dict):
        required = normalized.get("required")
        required_order = required if isinstance(required, list) else []
        required_names = set(required_order)
        normalized["properties"] = {
            key: value for key, value in properties.items() if key in required_names
        }
        normalized["required"] = [
            key for key in required_order if key in normalized["properties"]
        ]
        normalized["additionalProperties"] = False
    return normalized


def _json_schema_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _build_response_schema(proposal_schema: dict[str, Any]) -> dict[str, Any]:
    proposal_item = deepcopy(proposal_schema)
    definitions = proposal_item.pop("$defs", {})
    proposal_item.pop("$id", None)
    proposal_item.pop("$schema", None)
    response_schema = {
        "$id": AI_BATCH_SCHEMA_ID,
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": _to_structured_output_schema(definitions),
        "additionalProperties": False,
        "properties": {
            "response_metadata": {
                "additionalProperties": False,
                "properties": {
                    "generated_at": {"type": "string"},
                    "model": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["source", "model", "generated_at"],
                "type": "object",
            },
            "proposals": {
                "items": _to_structured_output_schema(proposal_item),
                "type": "array",
            }
        },
        "required": ["response_metadata", "proposals"],
        "title": "Quantum Tanner AI Batch Response",
        "type": "object",
    }
    return response_schema


def _validate_response_envelope(
    response: dict[str, Any],
    response_schema: dict[str, Any],
) -> None:
    def is_proposal_item_error(error: Any) -> bool:
        path = tuple(error.absolute_path)
        return len(path) >= 2 and path[0] == "proposals" and isinstance(path[1], int)

    schema_errors = sorted(
        (
            error
            for error in Draft202012Validator(response_schema).iter_errors(response)
            if not is_proposal_item_error(error)
        ),
        key=lambda error: (
            not (
                error.validator == "required"
                and "proposals" in error.validator_value
            ),
            tuple(error.absolute_path),
            str(error.message),
        ),
    )
    if not schema_errors:
        return

    schema_error = schema_errors[0]
    message = (
        "AI response schema validation failed at "
        f"{_json_pointer(tuple(schema_error.absolute_path))}: {schema_error.message}"
    )
    if (
        schema_error.validator == "required"
        and "proposals" in schema_error.validator_value
    ):
        message += "; AI response must contain a proposal list"
    raise SearchIntegrityError(message)


def _render_prompt(
    *,
    campaign: dict[str, Any],
    constraints: dict[str, Any],
    feedback: dict[str, Any],
) -> str:
    lines = [
        "# Quantum Tanner AI batch request",
        "",
        f"Campaign id: {campaign['id']}",
        f"Objective: {campaign['objective']}",
        f"Requested proposal count: {constraints['proposal_count']}",
        "",
        "Constraints:",
        json.dumps(constraints, indent=2, sort_keys=True),
        "",
        "Prior feedback:",
        json.dumps(feedback, indent=2, sort_keys=True),
        "",
        "Construction requirement:",
        "Require the combined left-right Cayley graph with neighbors a*g and g*b "
        "to be bipartite.",
        "",
        "Return only JSON",
    ]
    return "\n".join(lines) + "\n"


def _json_pointer(parts: tuple[Any, ...]) -> str:
    if not parts:
        return "/"
    escaped = [
        str(part).replace("~", "~0").replace("/", "~1")
        for part in parts
    ]
    return "/" + "/".join(escaped)


def _sanitize_proposal_id(proposal_id: Any) -> str:
    raw = proposal_id if isinstance(proposal_id, str) else ""
    sanitized = _SAFE_PROPOSAL_ID_PATTERN.sub("-", raw).strip(".-_")
    return sanitized or "proposal"


def _proposal_record_path(
    out_dir: Path,
    *,
    category: str,
    proposal_id: Any,
    proposal_index: int,
    width: int,
) -> tuple[Path, str]:
    relative_path = Path(category) / (
        f"{proposal_index:0{width}d}-{_sanitize_proposal_id(proposal_id)}.json"
    )
    return out_dir / relative_path, str(relative_path)


def _existing_ingest_outputs(out_dir: Path) -> tuple[str, ...]:
    return tuple(
        name for name in _INGEST_COMMAND_OUTPUTS if (out_dir / name).exists()
    )


def ingest_quantum_tanner_ai_batch(
    root: Path,
    *,
    response_path: Path,
    out_dir: Path,
    max_group_order: int = 32,
    max_physical_qubits: int | None = None,
) -> dict[str, Any]:
    if max_group_order <= 0:
        raise SearchIntegrityError("max_group_order must be positive")
    if max_physical_qubits is not None and max_physical_qubits <= 0:
        raise SearchIntegrityError("max_physical_qubits must be positive when provided")

    load_search_workspace(root)
    response = _load_json_object(response_path, label="AI response")
    proposal_schema = _load_json_object(
        root / PROPOSAL_SCHEMA_RELATIVE_PATH,
        label="quantum Tanner proposal schema",
    )
    response_schema = _build_response_schema(proposal_schema)
    _validate_response_envelope(response, response_schema)
    proposals = response["proposals"]
    validator = Draft202012Validator(proposal_schema)
    constraints = {
        "max_group_order": max_group_order,
        "max_physical_qubits": max_physical_qubits,
        "proposal_schema_path": str(PROPOSAL_SCHEMA_RELATIVE_PATH),
        "response_path": str(response_path),
        "response_schema_id": AI_BATCH_SCHEMA_ID,
        "validator_version": VALIDATOR_VERSION,
    }

    existing_outputs = _existing_ingest_outputs(out_dir)
    if existing_outputs:
        raise SearchIntegrityError(
            "ingest output already exists under --out; choose a fresh output directory "
            f"or remove the command-owned paths first: {', '.join(existing_outputs)}"
        )

    accepted_dir = out_dir / "accepted"
    rejected_dir = out_dir / "rejected"
    duplicates_dir = out_dir / "duplicates"
    accepted_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)
    duplicates_dir.mkdir(parents=True, exist_ok=True)

    accepted_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    duplicate_records: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    record_index_width = max(3, len(str(max(0, len(proposals) - 1))))

    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            record_path, record_relative_path = _proposal_record_path(
                out_dir,
                category="rejected",
                proposal_id=None,
                proposal_index=index,
                width=record_index_width,
            )
            record = {
                "error_kind": "SchemaValidationError",
                "json_pointer": "/",
                "message": "proposal must be an object",
                "path": record_relative_path,
                "proposal_id": None,
                "proposal_index": index,
            }
            rejected_records.append(record)
            _write_json(record_path, record)
            continue

        proposal_id = proposal.get("proposal_id")

        schema_error = next(validator.iter_errors(proposal), None)
        if schema_error is not None:
            record_path, record_relative_path = _proposal_record_path(
                out_dir,
                category="rejected",
                proposal_id=proposal_id,
                proposal_index=index,
                width=record_index_width,
            )
            record = {
                "error_kind": "SchemaValidationError",
                "json_pointer": _json_pointer(tuple(schema_error.absolute_path)),
                "message": schema_error.message,
                "path": record_relative_path,
                "proposal_id": proposal_id,
                "proposal_index": index,
            }
            rejected_records.append(record)
            _write_json(record_path, record)
            continue

        try:
            summary = validate_quantum_tanner_proposal(
                proposal,
                max_group_order=max_group_order,
            )
        except QuantumTannerProposalValidationError as exc:
            record_path, record_relative_path = _proposal_record_path(
                out_dir,
                category="rejected",
                proposal_id=proposal_id,
                proposal_index=index,
                width=record_index_width,
            )
            record = {
                "error_kind": exc.kind,
                "message": exc.message,
                "path": record_relative_path,
                "proposal_id": proposal_id,
                "proposal_index": index,
            }
            rejected_records.append(record)
            _write_json(record_path, record)
            continue

        if (
            max_physical_qubits is not None
            and proposal.get("construction_mode") == "lr_cayley_no_cover_v1"
            and summary.group_order > max_physical_qubits
        ):
            record_path, record_relative_path = _proposal_record_path(
                out_dir,
                category="rejected",
                proposal_id=summary.proposal_id,
                proposal_index=index,
                width=record_index_width,
            )
            record = {
                "error_kind": "PhysicalQubitLimitExceeded",
                "message": (
                    "validated_summary.group_order "
                    f"{summary.group_order} exceeds max_physical_qubits "
                    f"{max_physical_qubits} for lr_cayley_no_cover_v1"
                ),
                "path": record_relative_path,
                "proposal_id": summary.proposal_id,
                "proposal_index": index,
            }
            rejected_records.append(record)
            _write_json(record_path, record)
            continue

        accepted_record = summary.to_dict()
        accepted_record["proposal_index"] = index
        accepted_path, accepted_relative_path = _proposal_record_path(
            out_dir,
            category="accepted",
            proposal_id=summary.proposal_id,
            proposal_index=index,
            width=record_index_width,
        )
        accepted_record["path"] = accepted_relative_path
        if summary.fingerprint in seen_fingerprints:
            duplicate_path, duplicate_relative_path = _proposal_record_path(
                out_dir,
                category="duplicates",
                proposal_id=summary.proposal_id,
                proposal_index=index,
                width=record_index_width,
            )
            duplicate_record = {
                "error_kind": "DuplicateProposal",
                "fingerprint": summary.fingerprint,
                "message": "proposal fingerprint already accepted in this batch",
                "path": duplicate_relative_path,
                "proposal_id": summary.proposal_id,
                "proposal_index": index,
            }
            duplicate_records.append(duplicate_record)
            _write_json(duplicate_path, duplicate_record)
            continue

        seen_fingerprints.add(summary.fingerprint)
        accepted_records.append(accepted_record)
        _write_json(accepted_path, proposal)

    summary = {
        "accepted": len(accepted_records),
        "rejected": len(rejected_records),
        "duplicate": len(duplicate_records),
        "accepted_fingerprints": [record["fingerprint"] for record in accepted_records],
        "accepted_records": accepted_records,
        "constraints": constraints,
        "duplicate_records": duplicate_records,
        "rejected_records": rejected_records,
        "rejection_kinds": {
            str(key): int(value)
            for key, value in sorted(
                Counter(record["error_kind"] for record in rejected_records + duplicate_records).items()
            )
        },
        "response_path": str(response_path),
    }
    _write_json(out_dir / "constraints.json", constraints)
    _write_json(out_dir / "response_schema.json", response_schema)
    _write_json(out_dir / "summary.json", summary)
    return summary


def prepare_quantum_tanner_ai_batch(
    root: Path,
    *,
    campaign_id: str,
    out_dir: Path,
    count: int,
    max_group_order: int,
    max_physical_qubits: int | None = None,
    feedback_path: Path | None = None,
) -> dict[str, Path]:
    if count <= 0:
        raise SearchIntegrityError("count must be positive")
    if max_group_order <= 0:
        raise SearchIntegrityError("max_group_order must be positive")
    if max_physical_qubits is not None and max_physical_qubits <= 0:
        raise SearchIntegrityError("max_physical_qubits must be positive when provided")

    workspace = load_search_workspace(root)
    if campaign_id not in workspace.campaigns:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")
    campaign = workspace.campaigns[campaign_id]

    proposal_schema = _load_json_object(
        root / PROPOSAL_SCHEMA_RELATIVE_PATH,
        label="quantum Tanner proposal schema",
    )
    response_schema = _build_response_schema(proposal_schema)
    feedback = (
        _compact_feedback(_load_json_object(feedback_path, label="feedback"))
        if feedback_path is not None
        else {"accepted_fingerprints": [], "rejection_kinds": {}}
    )
    constraints = {
        "campaign": {
            "id": campaign["id"],
            "objective": campaign["objective"],
            "title": campaign.get("title"),
        },
        "max_group_order": max_group_order,
        "max_physical_qubits": max_physical_qubits,
        "proposal_count": count,
        "proposal_schema_path": str(PROPOSAL_SCHEMA_RELATIVE_PATH),
        "response_schema_id": AI_BATCH_SCHEMA_ID,
        "validator_version": VALIDATOR_VERSION,
    }
    provenance = {
        "campaign_id": campaign_id,
        "feedback_path": str(feedback_path) if feedback_path is not None else None,
        "out_dir": str(out_dir),
        "proposal_schema_path": str(PROPOSAL_SCHEMA_RELATIVE_PATH),
        "response_schema_id": AI_BATCH_SCHEMA_ID,
        "root": str(root),
        "validator_version": VALIDATOR_VERSION,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = out_dir / "prompt.md"
    response_schema_path = out_dir / "response_schema.json"
    constraints_path = out_dir / "constraints.json"
    feedback_out_path = out_dir / "feedback.json"
    provenance_path = out_dir / "provenance.json"

    prompt_path.write_text(
        _render_prompt(
            campaign=campaign,
            constraints=constraints,
            feedback=feedback,
        )
    )
    _write_json(response_schema_path, response_schema)
    _write_json(constraints_path, constraints)
    _write_json(feedback_out_path, feedback)
    _write_json(provenance_path, provenance)

    return {
        "constraints": constraints_path,
        "feedback": feedback_out_path,
        "prompt": prompt_path,
        "provenance": provenance_path,
        "response_schema": response_schema_path,
    }
