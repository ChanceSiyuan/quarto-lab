from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from autoqec_zoo.kb_migration import migrate_repo


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"

    _write(
        repo / ".knowledge" / "NOTES.md",
        """# High-distance codes with transversal logical operations

Updated 2026-05-26 from the survey pass on high-distance QEC codes with strong transversal logical structure.
""",
    )
    _write(repo / ".knowledge" / "paper-a.md", "# Paper A\n")
    _write(repo / ".knowledge" / "paper-b.md", "# Paper B\n")

    _write(
        repo / "ref.bib",
        """@article{paper_a,
  title = {Paper A},
  doi = {10.1000/paper-a},
  year = {2026}
}
""",
    )

    _write(
        repo
        / ".claude"
        / "survey"
        / "high-distance-codes-with-transversal-logical-operations"
        / "summary.md",
        """# High-distance codes with transversal logical operations

Selected directions: already absorbed.
""",
    )
    _write(
        repo
        / ".claude"
        / "survey"
        / "high-distance-codes-with-transversal-logical-operations"
        / "references.bib",
        """@article{legacy_high_distance,
  title = {Paper A},
  doi = {10.1000/paper-a},
  year = {2026}
}
""",
    )

    _write(
        repo / ".claude" / "survey" / "finite-code-transversal-gates" / "summary.md",
        """# Finite-code transversal gates

- [Paper A](../../../.knowledge/paper-a.md) [@legacy_paper_a]
- [Paper B](../../../.knowledge/paper-b.md)
""",
    )
    _write(
        repo / ".claude" / "survey" / "finite-code-transversal-gates" / "references.bib",
        """@article{legacy_paper_a,
  title = {Paper A},
  doi = {10.1000/paper-a},
  year = {2026}
}
""",
    )

    _write(
        repo / ".claude" / "survey" / "qec-code-discovery-patterns" / "summary.md",
        """# QEC Code Discovery Patterns

- [@Rains1997] showed that representation matters.
""",
    )
    _write(
        repo / ".claude" / "survey" / "qec-code-discovery-patterns" / "references.bib",
        """@article{Rains1997,
  title = {A Nonadditive Quantum Code},
  doi = {10.1103/PhysRevLett.79.953},
  eprint = {quant-ph/9703002},
  year = {1997}
}
""",
    )

    return repo


def test_migrate_repo_merges_legacy_notes_and_bibliography(tmp_path: Path) -> None:
    repo = _build_sample_repo(tmp_path)

    report = migrate_repo(repo)

    notes = (repo / ".knowledge" / "NOTES.md").read_text()
    bibliography = (repo / "ref.bib").read_text()

    assert set(report.imported_titles) == {
        "Finite-code transversal gates",
        "QEC Code Discovery Patterns",
    }
    assert set(report.skipped_titles) == {
        "High-distance codes with transversal logical operations",
    }
    assert (
        "Imported from legacy survey `.claude/survey/finite-code-transversal-gates/summary.md`."
        in notes
    )
    assert (
        "Imported from legacy survey `.claude/survey/qec-code-discovery-patterns/summary.md`."
        in notes
    )
    assert "[Paper A](paper-a.md) [@paper_a]" in notes
    assert "[Paper B](paper-b.md)" in notes
    assert "[@Rains1997] showed that representation matters." in notes
    assert notes.count("High-distance codes with transversal logical operations") == 1
    assert "@article{paper_a," in bibliography
    assert bibliography.count("10.1000/paper-a") == 1
    assert "@article{Rains1997," in bibliography
    assert not (repo / ".claude" / "survey").exists()


def test_migrate_repo_is_idempotent(tmp_path: Path) -> None:
    repo = _build_sample_repo(tmp_path)

    first = migrate_repo(repo)
    first_bibliography = (repo / "ref.bib").read_text()
    second = migrate_repo(repo)
    notes = (repo / ".knowledge" / "NOTES.md").read_text()
    second_bibliography = (repo / "ref.bib").read_text()

    assert set(first.imported_titles) == {
        "Finite-code transversal gates",
        "QEC Code Discovery Patterns",
    }
    assert second.imported_titles == []
    assert notes.count("## Finite-code transversal gates") == 1
    assert notes.count("## QEC Code Discovery Patterns") == 1
    assert first_bibliography == second_bibliography
    assert second_bibliography.count("@article{paper_a,") == 1
    assert second_bibliography.count("@article{Rains1997,") == 1
    assert second_bibliography.count("10.1000/paper-a") == 1


def test_migrate_repo_deduplicates_same_title_when_canonical_lacks_eprint(
    tmp_path: Path,
) -> None:
    repo = _build_sample_repo(tmp_path)

    _write(
        repo / "ref.bib",
        """@article{guemard_2025_moderate,
  title = {Moderate-Length Lifted Quantum Tanner Codes},
  year = {2025}
}
""",
    )
    _write(
        repo / ".claude" / "survey" / "qec-code-discovery-patterns" / "summary.md",
        """# QEC Code Discovery Patterns

- [@Guemard2025] discusses moderate-length lifted Tanner codes.
""",
    )
    _write(
        repo / ".claude" / "survey" / "qec-code-discovery-patterns" / "references.bib",
        """@misc{Guemard2025,
  title = {Moderate-Length Lifted Quantum Tanner Codes},
  eprint = {2502.20297},
  year = {2025}
}
""",
    )

    report = migrate_repo(repo)
    notes = (repo / ".knowledge" / "NOTES.md").read_text()
    bibliography = (repo / "ref.bib").read_text()

    assert "QEC Code Discovery Patterns" in report.imported_titles
    assert "[@guemard_2025_moderate]" in notes
    assert "@misc{Guemard2025," not in bibliography
    assert bibliography.count("Moderate-Length Lifted Quantum Tanner Codes") == 1


def test_migrate_repo_only_skips_when_matching_heading_exists(tmp_path: Path) -> None:
    repo = _build_sample_repo(tmp_path)

    _write(
        repo / ".knowledge" / "NOTES.md",
        """# High-distance codes with transversal logical operations

Updated 2026-05-26 from the survey pass on high-distance QEC codes with strong transversal logical structure.

This paragraph mentions ## QEC Code Discovery Patterns as plain text, not a heading.
""",
    )

    report = migrate_repo(repo)
    notes = (repo / ".knowledge" / "NOTES.md").read_text()

    assert "QEC Code Discovery Patterns" in report.imported_titles
    assert "## QEC Code Discovery Patterns" in notes


def test_migrate_repo_parses_bibtex_titles_with_nested_braces(tmp_path: Path) -> None:
    repo = _build_sample_repo(tmp_path)

    _write(
        repo / "ref.bib",
        """@article{raveendran_2025_minimum,
  title = {On the Minimum Distances of Finite-Length Lifted Product Quantum LDPC Codes},
  year = {2025}
}
""",
    )
    _write(
        repo / ".claude" / "survey" / "qec-code-discovery-patterns" / "summary.md",
        """# QEC Code Discovery Patterns

- [@Raveendran2025] studies finite-length LP codes.
""",
    )
    _write(
        repo / ".claude" / "survey" / "qec-code-discovery-patterns" / "references.bib",
        """@misc{Raveendran2025,
  title = {On the Minimum Distances of Finite-Length Lifted Product Quantum {LDPC} Codes},
  year = {2025}
}
""",
    )

    notes = (repo / ".knowledge" / "NOTES.md").read_text()
    migrate_repo(repo)
    notes = (repo / ".knowledge" / "NOTES.md").read_text()
    bibliography = (repo / "ref.bib").read_text()

    assert "[@raveendran_2025_minimum]" in notes
    assert "@misc{Raveendran2025," not in bibliography
    assert bibliography.count(
        "On the Minimum Distances of Finite-Length Lifted Product Quantum LDPC Codes"
    ) == 1
