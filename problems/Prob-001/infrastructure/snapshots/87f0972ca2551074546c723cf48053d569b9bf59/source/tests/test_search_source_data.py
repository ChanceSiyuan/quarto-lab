from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_search_example_source_files_validate_against_checked_in_schemas() -> None:
    schema_root = REPO_ROOT / "benchmarks" / "schemas"
    campaign_validator = Draft202012Validator(
        _load_json(schema_root / "campaign.schema.json")
    )
    search_space_validator = Draft202012Validator(
        _load_json(schema_root / "search-space.schema.json")
    )
    task_validator = Draft202012Validator(
        _load_json(schema_root / "benchmark-task.schema.json")
    )
    decoder_validator = Draft202012Validator(
        _load_json(schema_root / "decoder-config.schema.json")
    )
    suite_validator = Draft202012Validator(
        _load_json(schema_root / "benchmark-suite.schema.json")
    )

    example_root = REPO_ROOT / "campaigns" / "examples" / "rotated-surface-baseline"
    campaign_validator.validate(_load_json(example_root / "campaign.json"))
    search_space_validator.validate(_load_json(example_root / "search_space.json"))
    task_validator.validate(
        _load_json(REPO_ROOT / "benchmarks" / "tasks" / "rotated-memory-z-cdep-v1.json")
    )
    decoder_ids = []
    for decoder_path in sorted((REPO_ROOT / "benchmarks" / "decoders").glob("*.json")):
        decoder = _load_json(decoder_path)
        decoder_validator.validate(decoder)
        decoder_ids.append(decoder["id"])

    assert decoder_ids == [
        "predict-zero-v1",
        "rbposd-bb72-osd1-v1",
        "rbposd-bb72-osd10-v1",
        "rbposd-default-v1",
        "rbposd-osd0-v1",
        "rbposd-osd10-v1",
        "rilpqec-default-v1",
        "rmatching-default-v1",
    ]
    assert all("placeholder" not in decoder_id for decoder_id in decoder_ids)
    suite_validator.validate(
        _load_json(
            REPO_ROOT / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
        )
    )

    search_space = _load_json(example_root / "search_space.json")
    candidate_ids = [
        candidate["candidate_id"] for candidate in search_space["candidate_specs"]
    ]
    assert candidate_ids == [
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ]
    assert [
        candidate["parameters"]["distance"]
        for candidate in search_space["candidate_specs"]
    ] == [3, 5, 7]

    suite = _load_json(REPO_ROOT / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json")
    assert suite["task_ids"] == ["rotated-memory-z-cdep-v1"]

    task = _load_json(REPO_ROOT / "benchmarks" / "tasks" / "rotated-memory-z-cdep-v1.json")
    assert task["id"] == "rotated-memory-z-cdep-v1"
    assert task["title"] == "Rotated Memory Z under circuit depolarizing noise"
    assert task["observable"] == "logical_z"
    assert task["p_list"] == [0.008, 0.009, 0.01, 0.011, 0.012]
    assert task["rounds_policy"] == {
        "kind": "distance-scaled",
        "multiplier": 3,
        "minimum": 3,
    }

    campaign = _load_json(example_root / "campaign.json")
    assert campaign["budget"]["max_candidates"] == 3
    assert campaign["stop_conditions"]["max_candidates"] == 3

    assert (REPO_ROOT / "campaigns" / "README.md").is_file()
    assert (REPO_ROOT / "benchmarks" / "README.md").is_file()
    assert (REPO_ROOT / "results" / "search" / "README.md").is_file()
