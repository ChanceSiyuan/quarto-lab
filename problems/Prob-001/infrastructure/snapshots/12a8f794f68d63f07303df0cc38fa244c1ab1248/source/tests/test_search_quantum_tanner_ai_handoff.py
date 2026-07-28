from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
MIXED_RESPONSE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_ai_responses"
    / "mixed-valid-invalid.json"
)
MALFORMED_RESPONSE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_ai_responses"
    / "malformed-missing-proposals.json"
)
MALFORMED_NON_OBJECT_RESPONSE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_ai_responses"
    / "malformed-not-object.json"
)
DUPLICATE_RESPONSE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "quantum_tanner_ai_responses"
    / "duplicate-valid.json"
)


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "autoqec_search.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def _assert_prepare_ai_batch_prompt_schema_and_constraints(
    out: Path,
    *,
    campaign_id: str,
    proposal_count: int,
    max_group_order: int,
    max_physical_qubits: int,
) -> None:
    prompt = (out / "prompt.md").read_text()
    assert campaign_id in prompt
    assert "Return only JSON" in prompt
    assert "combined left-right Cayley graph" in prompt
    assert "bipartite" in prompt
    schema = json.loads((out / "response_schema.json").read_text())
    assert schema["required"] == ["response_metadata", "proposals"]
    assert schema["properties"]["proposals"]["type"] == "array"
    constraints = json.loads((out / "constraints.json").read_text())
    assert constraints["campaign"]["id"] == campaign_id
    assert constraints["proposal_count"] == proposal_count
    assert constraints["max_group_order"] == max_group_order
    assert constraints["max_physical_qubits"] == max_physical_qubits
    assert constraints["validator_version"] == "quantum-tanner-proposal-validator-v1"


def _assert_prepare_ai_batch_without_feedback(
    tmp_path: Path,
) -> None:
    out = tmp_path / "batch"

    result = _run_cli(
        "prepare-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--campaign",
        "quantum-tanner-autoresearch",
        "--out",
        str(out),
        "--count",
        "4",
        "--max-group-order",
        "32",
        "--max-physical-qubits",
        "96",
    )

    assert result.returncode == 0, result.stderr
    _assert_prepare_ai_batch_prompt_schema_and_constraints(
        out,
        campaign_id="quantum-tanner-autoresearch",
        proposal_count=4,
        max_group_order=32,
        max_physical_qubits=96,
    )
    feedback = json.loads((out / "feedback.json").read_text())
    assert feedback["accepted_fingerprints"] == []
    assert feedback["rejection_kinds"] == {}


def test_prepare_ai_batch_writes_prompt_schema_and_constraints(tmp_path: Path) -> None:
    _assert_prepare_ai_batch_without_feedback(tmp_path)


def test_prepare_ai_batch_response_schema_is_openai_strict_compatible(
    tmp_path: Path,
) -> None:
    out = tmp_path / "strict-schema"

    result = _run_cli(
        "prepare-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--campaign",
        "quantum-tanner-autoresearch",
        "--out",
        str(out),
        "--count",
        "4",
        "--max-group-order",
        "32",
    )

    assert result.returncode == 0, result.stderr
    schema = json.loads((out / "response_schema.json").read_text())
    assert "$defs" in schema
    proposal_schema = schema["properties"]["proposals"]["items"]
    assert "$defs" not in proposal_schema
    assert "$id" not in proposal_schema
    assert "$schema" not in proposal_schema

    referenced_definitions: set[str] = set()
    unsupported_keywords = {
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

    def check_node(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                check_node(item)
            return
        if not isinstance(node, dict):
            return
        assert not (set(node) & unsupported_keywords)
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            referenced_definitions.add(reference.removeprefix("#/$defs/"))
        properties = node.get("properties")
        if isinstance(properties, dict):
            assert node.get("additionalProperties") is False
            assert set(node.get("required", [])) == set(properties)
        for value in node.values():
            check_node(value)

    check_node(schema)
    assert referenced_definitions <= set(schema["$defs"])

    def check_explicit_types(node: dict[str, object]) -> None:
        if "$ref" not in node:
            assert "type" in node
        definitions = node.get("$defs")
        if isinstance(definitions, dict):
            for definition in definitions.values():
                assert isinstance(definition, dict)
                check_explicit_types(definition)
        properties = node.get("properties")
        if isinstance(properties, dict):
            for property_schema in properties.values():
                assert isinstance(property_schema, dict)
                check_explicit_types(property_schema)
        items = node.get("items")
        if isinstance(items, dict):
            check_explicit_types(items)

    check_explicit_types(schema)
    Draft202012Validator.check_schema(schema)


def test_prepare_ai_batch_writes_prompt_schema_and_constraints_without_feedback(
    tmp_path: Path,
) -> None:
    _assert_prepare_ai_batch_without_feedback(tmp_path)


def test_prepare_ai_batch_writes_prompt_schema_and_constraints_with_feedback(
    tmp_path: Path,
) -> None:
    out = tmp_path / "batch"
    prior_feedback = tmp_path / "prior-feedback.json"
    prior_feedback_payload = {
        "accepted_fingerprints": ["abc123def456"],
        "rejection_kinds": {"NonSymmetricGeneratorSet": 1},
    }
    prior_feedback.write_text(json.dumps(prior_feedback_payload))

    result = _run_cli(
        "prepare-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--campaign",
        "quantum-tanner-autoresearch",
        "--out",
        str(out),
        "--count",
        "4",
        "--max-group-order",
        "32",
        "--max-physical-qubits",
        "96",
        "--feedback",
        str(prior_feedback),
    )

    assert result.returncode == 0, result.stderr
    _assert_prepare_ai_batch_prompt_schema_and_constraints(
        out,
        campaign_id="quantum-tanner-autoresearch",
        proposal_count=4,
        max_group_order=32,
        max_physical_qubits=96,
    )
    feedback = json.loads((out / "feedback.json").read_text())
    assert feedback["accepted_fingerprints"] == ["abc123def456"]
    assert feedback["rejection_kinds"] == {"NonSymmetricGeneratorSet": 1}


def test_prepare_ai_batch_compacts_feedback_report_next_prompt_context(
    tmp_path: Path,
) -> None:
    out = tmp_path / "batch"
    prior_feedback = tmp_path / "quantum-tanner-ai-feedback.json"
    prior_feedback_payload = {
        "schema_version": 1,
        "report_kind": "quantum-tanner-ai-feedback",
        "next_prompt_context": {
            "accepted_proposal_fingerprints": ["fp-from-feedback-report"],
            "rejection_kinds": {"DuplicateProposal": 2},
        },
    }
    prior_feedback.write_text(json.dumps(prior_feedback_payload))

    result = _run_cli(
        "prepare-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--campaign",
        "quantum-tanner-autoresearch",
        "--out",
        str(out),
        "--count",
        "4",
        "--max-group-order",
        "32",
        "--max-physical-qubits",
        "96",
        "--feedback",
        str(prior_feedback),
    )

    assert result.returncode == 0, result.stderr
    feedback = json.loads((out / "feedback.json").read_text())
    assert feedback["accepted_fingerprints"] == ["fp-from-feedback-report"]
    assert feedback["rejection_kinds"] == {"DuplicateProposal": 2}


def test_prepare_ai_batch_response_schema_accepts_required_fixture_projection(
    tmp_path: Path,
) -> None:
    out = tmp_path / "batch"

    result = _run_cli(
        "prepare-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--campaign",
        "quantum-tanner-autoresearch",
        "--out",
        str(out),
        "--count",
        "4",
        "--max-group-order",
        "32",
    )

    assert result.returncode == 0, result.stderr
    schema = json.loads((out / "response_schema.json").read_text())
    response = json.loads(MIXED_RESPONSE.read_text())
    for proposal in response["proposals"]:
        proposal.pop("search_hints", None)
        proposal["provenance"].pop("prompt_summary", None)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(response),
        key=lambda error: tuple(error.absolute_path),
    )
    assert errors == []


def test_ingest_ai_batch_accepts_valid_and_rejects_invalid_fixture_response(
    tmp_path: Path,
) -> None:
    out = tmp_path / "ingested"

    result = _run_cli(
        "ingest-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--response",
        str(MIXED_RESPONSE),
        "--out",
        str(out),
        "--max-group-order",
        "32",
        "--max-physical-qubits",
        "96",
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert summary["duplicate"] == 0
    assert summary["constraints"]["max_physical_qubits"] == 96
    accepted = sorted((out / "accepted").glob("*.json"))
    rejected = sorted((out / "rejected").glob("*.json"))
    assert [path.name for path in accepted] == ["000-ai-valid-dihedral-d3.json"]
    assert len(rejected) == 1
    rejected_payload = json.loads(rejected[0].read_text())
    assert rejected_payload["error_kind"] == "NonSymmetricGeneratorSet"
    assert summary["accepted_records"][0]["proposal_id"] == "ai-valid-dihedral-d3"
    assert summary["accepted_records"][0]["path"] == "accepted/000-ai-valid-dihedral-d3.json"
    assert rejected_payload["proposal_id"] == "ai-invalid-nonsymmetric-generators"
    assert rejected_payload["path"] == "rejected/001-ai-invalid-nonsymmetric-generators.json"
    assert summary["accepted_fingerprints"] == [
        summary["accepted_records"][0]["fingerprint"]
    ]


def test_ingest_ai_batch_rejects_top_level_schema_violation_without_outputs(
    tmp_path: Path,
) -> None:
    response_payload = json.loads(MIXED_RESPONSE.read_text())
    response_payload["unexpected_top_level_field"] = True
    response_path = tmp_path / "top-level-schema-violation.json"
    response_path.write_text(json.dumps(response_payload))
    out = tmp_path / "top-level-schema-violation"

    result = _run_cli(
        "ingest-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--response",
        str(response_path),
        "--out",
        str(out),
        "--max-group-order",
        "32",
        "--max-physical-qubits",
        "96",
    )

    assert result.returncode != 0
    assert "ai response schema validation failed" in result.stderr.lower(), result.stderr
    assert "unexpected_top_level_field" in result.stderr, result.stderr
    assert not (out / "accepted").exists()
    assert not (out / "rejected").exists()
    assert not (out / "summary.json").exists()


def test_ingest_ai_batch_records_proposal_schema_error_without_fatal_reject(
    tmp_path: Path,
) -> None:
    response_payload = json.loads(MIXED_RESPONSE.read_text())
    valid_proposal = response_payload["proposals"][0]
    schema_invalid_proposal = {
        key: value
        for key, value in response_payload["proposals"][1].items()
        if key != "schema_version"
    }
    response_payload["proposals"] = [valid_proposal, schema_invalid_proposal]
    response_path = tmp_path / "mixed-schema-invalid.json"
    response_path.write_text(json.dumps(response_payload))
    out = tmp_path / "mixed-schema-invalid"

    result = _run_cli(
        "ingest-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--response",
        str(response_path),
        "--out",
        str(out),
        "--max-group-order",
        "32",
        "--max-physical-qubits",
        "96",
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert summary["duplicate"] == 0
    rejected = sorted((out / "rejected").glob("*.json"))
    assert len(rejected) == 1
    rejected_payload = json.loads(rejected[0].read_text())
    assert rejected_payload["error_kind"] == "SchemaValidationError"
    assert rejected_payload["proposal_index"] == 1
    assert rejected_payload["proposal_id"] == "ai-invalid-nonsymmetric-generators"
    assert summary["rejected_records"] == [rejected_payload]


@pytest.mark.parametrize(
    ("response_fixture", "stderr_substring"),
    [
        (MALFORMED_RESPONSE, "proposal list"),
        (MALFORMED_NON_OBJECT_RESPONSE, "object"),
    ],
)
def test_ingest_ai_batch_rejects_malformed_response_without_outputs(
    tmp_path: Path,
    response_fixture: Path,
    stderr_substring: str,
) -> None:
    out = tmp_path / "malformed"

    result = _run_cli(
        "ingest-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--response",
        str(response_fixture),
        "--out",
        str(out),
        "--max-group-order",
        "32",
    )

    assert result.returncode != 0
    assert stderr_substring in result.stderr.lower(), result.stderr
    assert not (out / "accepted").exists()
    assert not (out / "summary.json").exists()


def test_ingest_ai_batch_rejects_reusing_existing_output_directory(
    tmp_path: Path,
) -> None:
    out = tmp_path / "reused-output"

    first_result = _run_cli(
        "ingest-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--response",
        str(MIXED_RESPONSE),
        "--out",
        str(out),
        "--max-group-order",
        "32",
        "--max-physical-qubits",
        "96",
    )

    assert first_result.returncode == 0, first_result.stderr
    first_summary = json.loads((out / "summary.json").read_text())
    assert first_summary["accepted"] == 1
    assert first_summary["rejected"] == 1
    assert first_summary["duplicate"] == 0
    assert len(list((out / "accepted").glob("*.json"))) == 1

    second_result = _run_cli(
        "ingest-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--response",
        str(MIXED_RESPONSE),
        "--out",
        str(out),
        "--max-group-order",
        "32",
        "--max-physical-qubits",
        "96",
    )

    assert second_result.returncode != 0
    assert "already exists" in second_result.stderr.lower(), second_result.stderr
    assert "command-owned" in second_result.stderr.lower(), second_result.stderr
    second_summary = json.loads((out / "summary.json").read_text())
    assert second_summary == first_summary
    assert len(list((out / "accepted").glob("*.json"))) == 1


def test_ingest_ai_batch_rejects_proposal_exceeding_max_physical_qubits(
    tmp_path: Path,
) -> None:
    valid_proposal = json.loads(MIXED_RESPONSE.read_text())["proposals"][0]
    response_path = tmp_path / "physical-qubit-limit.json"
    response_path.write_text(
        json.dumps(
            {
                "response_metadata": {
                    "source": "fixture",
                    "model": "offline-fixture",
                    "generated_at": "2026-07-10T00:00:00Z",
                },
                "proposals": [valid_proposal],
            }
        )
    )
    out = tmp_path / "physical-qubit-limit"

    result = _run_cli(
        "ingest-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--response",
        str(response_path),
        "--out",
        str(out),
        "--max-group-order",
        "32",
        "--max-physical-qubits",
        "5",
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["accepted"] == 0
    assert summary["rejected"] == 1
    assert summary["duplicate"] == 0
    rejected = sorted((out / "rejected").glob("*.json"))
    assert [path.name for path in rejected] == ["000-ai-valid-dihedral-d3.json"]
    rejected_payload = json.loads(rejected[0].read_text())
    assert rejected_payload["error_kind"] == "PhysicalQubitLimitExceeded"
    assert "max_physical_qubits 5" in rejected_payload["message"]
    assert rejected_payload["proposal_id"] == "ai-valid-dihedral-d3"
    assert rejected_payload["proposal_index"] == 0
    assert rejected_payload["path"] == "rejected/000-ai-valid-dihedral-d3.json"


def test_ingest_ai_batch_counts_duplicates_and_reports_duplicate_records(
    tmp_path: Path,
) -> None:
    out = tmp_path / "duplicates"

    result = _run_cli(
        "ingest-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--response",
        str(DUPLICATE_RESPONSE),
        "--out",
        str(out),
        "--max-group-order",
        "32",
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["accepted"] == 1
    assert summary["rejected"] == 0
    assert summary["duplicate"] == 1
    accepted = sorted((out / "accepted").glob("*.json"))
    duplicates = sorted((out / "duplicates").glob("*.json"))
    assert len(accepted) == 1
    assert len(duplicates) == 1
    duplicate_payload = json.loads(duplicates[0].read_text())
    assert duplicate_payload["error_kind"] == "DuplicateProposal"
    assert duplicate_payload["proposal_id"] == "ai-duplicate-dihedral-d3"
    assert duplicate_payload["path"] == "duplicates/001-ai-duplicate-dihedral-d3.json"
    assert duplicate_payload["fingerprint"] == summary["accepted_records"][0]["fingerprint"]


def test_ingest_ai_batch_sanitizes_untrusted_and_colliding_proposal_ids(
    tmp_path: Path,
) -> None:
    response_payload = json.loads(MIXED_RESPONSE.read_text())
    valid_proposal = response_payload["proposals"][0]
    response = {
        "response_metadata": {
            "source": "fixture",
            "model": "offline-fixture",
            "generated_at": "2026-07-10T00:00:00Z",
        },
        "proposals": [
            {
                **valid_proposal,
                "proposal_id": "../safe",
            },
            {
                **valid_proposal,
                "proposal_id": "safe",
                "base_group": {
                    **valid_proposal["base_group"],
                    "name": "D3-alt",
                },
            },
        ],
    }
    response_path = tmp_path / "unsafe-colliding-response.json"
    response_path.write_text(json.dumps(response))
    out = tmp_path / "unsafe-colliding"

    result = _run_cli(
        "ingest-quantum-tanner-ai-batch",
        "--root",
        ".",
        "--response",
        str(response_path),
        "--out",
        str(out),
        "--max-group-order",
        "32",
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text())
    accepted = sorted((out / "accepted").glob("*.json"))
    assert summary["accepted"] == 2
    assert len(accepted) == summary["accepted"]
    assert [path.name for path in accepted] == ["000-safe.json", "001-safe.json"]
    assert all(path.is_relative_to(out / "accepted") for path in accepted)
    assert [record["proposal_id"] for record in summary["accepted_records"]] == ["../safe", "safe"]
    assert [record["path"] for record in summary["accepted_records"]] == [
        "accepted/000-safe.json",
        "accepted/001-safe.json",
    ]
