from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _skill_text(name: str) -> str:
    return (REPO_ROOT / "skills" / name / "SKILL.md").read_text()


def test_benchmark_code_skill_documents_approval_and_dispatch() -> None:
    text = _skill_text("benchmark-code")

    assert "benchmark-code" in text
    assert "explicit approval" in text
    assert "autoqec-search preflight" in text
    assert "bench-runner-distance" in text
    assert "bench-runner-mc-ler" in text
    assert "must not run" in text
    assert "distance" in text
    assert "mc-ler" in text


def test_bench_runner_distance_skill_documents_exact_distance_contract() -> None:
    text = _skill_text("bench-runner-distance")

    assert "bench-runner-distance" in text
    assert "distance.json" in text
    assert 'bound_type: "exact"' in text
    assert "rotated surface" in text
    assert "distance 3" in text
    assert "not promotion-safe" in text
    assert "missing backend" in text


def test_bench_runner_mc_ler_skill_documents_existing_cli_path() -> None:
    text = _skill_text("bench-runner-mc-ler")

    assert "bench-runner-mc-ler" in text
    assert "autoqec-search eval" in text
    assert "autoqec-search run" in text
    assert "autoqec-search report" in text
    assert "autoqec-search preflight" in text
    assert "BB72 OSD1 smoke" in text
    assert "OSD10" in text
    assert "missing-dependency" in text


def test_compare_candidates_skill_documents_incomparable_refusal() -> None:
    text = _skill_text("compare-candidates")

    assert "compare-candidates" in text
    assert "autoqec-search compare-candidates" in text
    assert "two or more run directories" in text
    assert "task/decoder/p" in text
    assert "incomparable runs" in text
    assert "must not summarize" in text
    assert "Overall winner reporting is strong-only" in text
    assert "/tmp/compare.json" in text
