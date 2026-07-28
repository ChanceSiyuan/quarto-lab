from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from autoqec_search.css_distance_suite import (
    FAMILY_COUNTS,
    GEOMETRIC_KIND_COUNTS,
    load_and_validate_source_pool,
    prepare_blind_suite,
    verify_suite_commitment,
)
from autoqec_search.structure import verify_css_upper_bound_witness


REPO_ROOT = Path(__file__).resolve().parents[1]
POOL_ROOT = REPO_ROOT / "benchmarks" / "css_distance_paper_validation"
SOURCE_POOL = POOL_ROOT / "source_pool.json"
SEEDS = POOL_ROOT / "seeds.json"
CURATION = POOL_ROOT / "curation.json"
COMMITMENT = POOL_ROOT / "commitment.json"
COMMITMENT_SCHEMA = (
    REPO_ROOT / "benchmarks" / "schemas" / "css-distance-suite-commitment.schema.json"
)
PROPOSAL_DOCS = (
    REPO_ROOT / "LOG.md",
    REPO_ROOT / "campaigns" / "examples" / "css-distance-autoresearch" / "README.md",
    REPO_ROOT
    / "campaigns"
    / "examples"
    / "css-distance-autoresearch"
    / "proposal-prompt.txt",
)


def _walk_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(_walk_strings(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(_walk_strings(item))
        return strings
    return []


def test_css_distance_paper_pool_has_required_counts_and_safe_paths() -> None:
    cases = load_and_validate_source_pool(
        root=REPO_ROOT,
        path=SOURCE_POOL.relative_to(REPO_ROOT),
    )

    assert len(cases) == 36
    assert Counter(case.record["family"] for case in cases) == {
        "geometric": 12,
        "bivariate-bicycle": 9,
        "apm-kasai": 6,
        "quantum-tanner": 9,
    }
    assert Counter(
        case.record["construction_kind"]
        for case in cases
        if case.record["family"] == "geometric"
    ) == {"surface": 6, "toric": 6}
    assert all(
        case.record["provenance"]["license_status"] == "redistribution-approved"
        for case in cases
    )
    assert all(
        not Path(text).is_absolute()
        for case in cases
        for text in _walk_strings(case.record)
    )


def test_css_distance_paper_pool_seeds_are_committed_and_fixed() -> None:
    seeds = json.loads(SEEDS.read_text())

    assert seeds == {
        "schema_version": 1,
        "time_limit_seconds": 300,
        "seeds": [
            104729,
            130363,
            155921,
            196613,
            262147,
            327673,
            393241,
            458789,
            524309,
            589867,
            655373,
            720899,
            786433,
            851971,
            917519,
            983063,
            1048583,
            1114129,
            1179661,
            1245187,
        ],
    }
    assert len(seeds["seeds"]) == len(set(seeds["seeds"])) == 20
    assert all(type(seed) is int for seed in seeds["seeds"])


def test_css_distance_paper_pool_curation_matches_source_pool() -> None:
    source_pool = json.loads(SOURCE_POOL.read_text())
    curation = json.loads(CURATION.read_text())
    source_ids = {case["case_id"] for case in source_pool["cases"]}
    curation_ids = {case["case_id"] for case in curation["cases"]}

    assert curation["schema_version"] == 1
    assert curation_ids == source_ids
    assert all(
        set(case) == {
            "case_id",
            "source_pin",
            "generator_command",
            "evidence_key",
            "redistribution_decision",
            "reference_type",
        }
        for case in curation["cases"]
    )
    assert all(
        case["redistribution_decision"] == "redistribution-approved"
        for case in curation["cases"]
    )


def test_css_distance_paper_pool_upper_witnesses_verify() -> None:
    cases = load_and_validate_source_pool(
        root=REPO_ROOT,
        path=SOURCE_POOL.relative_to(REPO_ROOT),
    )

    upper_cases = [
        case for case in cases if case.record["reference"]["bound_type"] == "upper"
    ]
    assert len(upper_cases) >= 9
    for case in upper_cases:
        result = verify_css_upper_bound_witness(
            case.hx_payload,
            case.hz_payload,
            case.record["reference"]["witness"],
        )
        assert result["status"] == "pass"
        assert result["weight"] == case.record["reference"]["value"]


def test_css_distance_paper_pool_prepares_required_blind_split(tmp_path: Path) -> None:
    _assert_pool_prepares_required_blind_split(
        tmp_path,
        secret=bytes(range(32)),
        salt=bytes(range(32, 64)),
    )


def test_css_distance_paper_pool_prepares_large_holdout_for_zero_secret(
    tmp_path: Path,
) -> None:
    _assert_pool_prepares_required_blind_split(
        tmp_path,
        secret=bytes(32),
        salt=bytes([255 - index for index in range(32)]),
    )


def _assert_pool_prepares_required_blind_split(
    tmp_path: Path,
    *,
    secret: bytes,
    salt: bytes,
) -> None:
    commitment = prepare_blind_suite(
        root=REPO_ROOT,
        source_pool_path=SOURCE_POOL.relative_to(REPO_ROOT),
        work_root=tmp_path / "operator",
        commitment_path=tmp_path / "commitment.json",
        created_at="2026-07-21T00:00:00Z",
        secret=secret,
        salt=salt,
    )

    assert commitment["counts"] == {"development": 24, "final": 12}
    assert commitment["family_counts"] == FAMILY_COUNTS
    assert commitment["geometric_kind_counts"] == GEOMETRIC_KIND_COUNTS
    assert verify_suite_commitment(
        private_root=tmp_path / "operator" / "private" / "css-distance-paper-suite",
        commitment=commitment,
    ) == {"status": "pass", "development": 24, "final": 12}


def test_css_distance_paper_commitment_is_public_and_schema_valid() -> None:
    commitment = json.loads(COMMITMENT.read_text())
    schema = json.loads(COMMITMENT_SCHEMA.read_text())
    Draft202012Validator(schema).validate(commitment)

    assert commitment["counts"] == {"development": 24, "final": 12}
    assert commitment["family_counts"] == FAMILY_COUNTS
    assert commitment["geometric_kind_counts"] == GEOMETRIC_KIND_COUNTS
    safe_text = json.dumps(commitment, sort_keys=True)
    for marker in [
        "case_id",
        "construction",
        "hx_path",
        "hz_path",
        "reference",
        "witness",
        "target",
        "development-000",
        "final-000",
    ]:
        assert marker not in safe_text


def test_css_distance_paper_public_docs_do_not_leak_source_case_ids() -> None:
    source_pool = json.loads(SOURCE_POOL.read_text())
    source_ids = {case["case_id"] for case in source_pool["cases"]}
    proposal_text = "\n".join(path.read_text() for path in PROPOSAL_DOCS)

    for marker in [*sorted(source_ids), "development-000", "final-000"]:
        assert marker not in proposal_text
