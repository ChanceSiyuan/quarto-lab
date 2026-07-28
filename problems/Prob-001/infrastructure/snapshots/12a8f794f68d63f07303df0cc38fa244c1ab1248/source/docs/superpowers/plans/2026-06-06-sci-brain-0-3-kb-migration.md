# sci-brain 0.3 KB Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate this repo to a single `sci-brain` 0.3 knowledge-base layout by merging legacy `.claude/survey/*` notes and bibliographies into `.knowledge/NOTES.md` and `ref.bib`, updating docs, and deleting the legacy survey tree.

**Architecture:** Put the risky text-rewrite and BibTeX-dedup work in a small Python migration module plus a thin wrapper script. Lock that behavior down first with temp-repo pytest coverage for link rewriting, cite-key normalization, duplicate-title skipping, and bibliography merge precedence. Once the migration logic is proven, run it against the real repo, update the human docs and repo-state tests, then remove `.claude/survey/`.

**Tech Stack:** Python 3.11, `pytest`, stdlib `re`/`dataclasses`/`pathlib`, Markdown docs, existing repo test harness

---

## File Structure

- Create: `src/autoqec_zoo/kb_migration.py`
  - Pure Python migration logic: parse legacy surveys, parse/dedup BibTeX, rewrite citations/links, merge into `.knowledge/NOTES.md`, and remove `.claude/survey/`.
- Create: `scripts/migrate_sci_brain_kb.py`
  - Thin wrapper that runs the migration module against a repo root and prints a short report.
- Create: `tests/test_kb_migration.py`
  - Temp-repo regression tests for migration behavior without depending on the real legacy survey tree.
- Modify: `.knowledge/NOTES.md`
  - Real migrated notes, including imported legacy survey sections and a provenance line for the already-absorbed high-distance survey.
- Modify: `ref.bib`
  - Real merged bibliography with legacy-only entries appended and duplicate entries avoided.
- Modify: `README.md`
  - Document `.knowledge/` plus `ref.bib` as the active literature layout.
- Modify: `CLAUDE.md`
  - Remove stale wording that implies `ref.bib` does not exist yet and tighten the 0.3 KB guidance.
- Modify: `tests/test_source_data.py`
  - Repo-state assertions for single-layout docs, imported note titles, and absence of `.claude/survey/`.
- Delete: `.claude/survey/finite-code-transversal-gates/`
- Delete: `.claude/survey/finite-length-bb-lp-exact-distance-transversal-gates/`
- Delete: `.claude/survey/high-distance-codes-with-transversal-logical-operations/`
- Delete: `.claude/survey/qec-code-discovery-patterns/`

## Task 1: Add Failing Migration Tests Against a Temp Repo

**Files:**
- Create: `tests/test_kb_migration.py`

- [ ] **Step 1: Write the failing migration tests**

```python
from __future__ import annotations

from pathlib import Path

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

- [Rains1997] showed that representation matters.
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

    assert report.imported_titles == [
        "Finite-code transversal gates",
        "QEC Code Discovery Patterns",
    ]
    assert report.skipped_titles == [
        "High-distance codes with transversal logical operations",
    ]
    assert "Imported from legacy survey `.claude/survey/finite-code-transversal-gates/summary.md`." in notes
    assert "Imported from legacy survey `.claude/survey/qec-code-discovery-patterns/summary.md`." in notes
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
    second = migrate_repo(repo)
    notes = (repo / ".knowledge" / "NOTES.md").read_text()

    assert first.imported_titles == [
        "Finite-code transversal gates",
        "QEC Code Discovery Patterns",
    ]
    assert second.imported_titles == []
    assert notes.count("## Finite-code transversal gates") == 1
    assert notes.count("## QEC Code Discovery Patterns") == 1
```

- [ ] **Step 2: Run the new test file to verify it fails**

Run: `python3 -m pytest tests/test_kb_migration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoqec_zoo.kb_migration'`

- [ ] **Step 3: Commit the failing-test checkpoint**

```bash
git add tests/test_kb_migration.py
git commit -m "test: add sci-brain kb migration coverage"
```

## Task 2: Implement the Migration Module and Wrapper Script

**Files:**
- Create: `src/autoqec_zoo/kb_migration.py`
- Create: `scripts/migrate_sci_brain_kb.py`

- [ ] **Step 1: Add the migration module**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


PROVENANCE_TEMPLATE = "Imported from legacy survey `{path}`."


@dataclass(frozen=True)
class BibEntry:
    key: str
    entry_type: str
    raw: str
    fields: dict[str, str]


@dataclass(frozen=True)
class SurveyRecord:
    slug: str
    title: str
    source_path: Path
    body: str
    bib_entries: list[BibEntry]


@dataclass(frozen=True)
class MigrationReport:
    imported_titles: list[str]
    skipped_titles: list[str]
    appended_bib_keys: list[str]


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _split_bib_entries(text: str) -> list[str]:
    entries: list[str] = []
    start = None
    depth = 0
    for index, char in enumerate(text):
        if char == "@" and start is None:
            start = index
            depth = 0
        if start is None:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                entries.append(text[start : index + 1].strip())
                start = None
    return entries


def _parse_bib_entry(raw: str) -> BibEntry:
    header, body = raw.split("{", 1)
    entry_type = header[1:].strip().lower()
    key, rest = body.split(",", 1)
    fields: dict[str, str] = {}
    for match in re.finditer(
        r"(?ms)^\\s*([A-Za-z][A-Za-z0-9_-]*)\\s*=\\s*[{\\\"](.*?)[}\\\"]\\s*,?\\s*$",
        rest,
    ):
        fields[match.group(1).lower()] = " ".join(match.group(2).split())
    return BibEntry(key=key.strip(), entry_type=entry_type, raw=raw.strip(), fields=fields)


def _entry_fingerprint(entry: BibEntry) -> tuple[str, str]:
    if doi := entry.fields.get("doi"):
        return ("doi", _normalize(doi))
    if eprint := entry.fields.get("eprint"):
        return ("eprint", _normalize(eprint))
    return ("title", _normalize(entry.fields["title"]))


def _load_bibliography(path: Path) -> list[BibEntry]:
    text = path.read_text() if path.exists() else ""
    return [_parse_bib_entry(raw) for raw in _split_bib_entries(text)]


def _extract_title_and_body(summary_path: Path) -> tuple[str, str]:
    lines = summary_path.read_text().splitlines()
    title = lines[0].removeprefix("# ").strip()
    body = "\\n".join(lines[1:]).strip()
    return title, body


def _demote_headings(text: str) -> str:
    return re.sub(r"(?m)^(#{2,6})\\s", lambda match: "#" + match.group(1) + " ", text)


def _rewrite_links(text: str) -> str:
    return text.replace("](../../../.knowledge/", "](")


def _rewrite_citations(text: str, key_map: dict[str, str]) -> str:
    for old_key, new_key in sorted(key_map.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(f"[@{old_key}]", f"[@{new_key}]")
        text = re.sub(rf"\\[{re.escape(old_key)}\\](?!\\()", f"[@{new_key}]", text)
    return text


def _load_surveys(legacy_root: Path) -> list[SurveyRecord]:
    surveys: list[SurveyRecord] = []
    for survey_dir in sorted(path for path in legacy_root.iterdir() if path.is_dir()):
        summary_path = survey_dir / "summary.md"
        references_path = survey_dir / "references.bib"
        title, body = _extract_title_and_body(summary_path)
        surveys.append(
            SurveyRecord(
                slug=survey_dir.name,
                title=title,
                source_path=summary_path.relative_to(legacy_root.parent.parent),
                body=body,
                bib_entries=_load_bibliography(references_path),
            )
        )
    return surveys


def migrate_repo(repo_root: Path) -> MigrationReport:
    kb_root = repo_root / ".knowledge"
    notes_path = kb_root / "NOTES.md"
    bibliography_path = repo_root / "ref.bib"
    legacy_root = repo_root / ".claude" / "survey"

    if not legacy_root.exists():
        return MigrationReport(imported_titles=[], skipped_titles=[], appended_bib_keys=[])

    notes_text = notes_path.read_text()
    notes_lines = notes_text.splitlines()
    existing_root_title = notes_lines[0].removeprefix("# ").strip()

    canonical_entries = _load_bibliography(bibliography_path)
    fingerprint_to_key = {_entry_fingerprint(entry): entry.key for entry in canonical_entries}
    key_map: dict[str, str] = {}
    appended_entries: list[BibEntry] = []
    imported_titles: list[str] = []
    skipped_titles: list[str] = []
    appended_sections: list[str] = []

    for survey in _load_surveys(legacy_root):
        for entry in survey.bib_entries:
            fingerprint = _entry_fingerprint(entry)
            canonical_key = fingerprint_to_key.get(fingerprint)
            if canonical_key is None:
                fingerprint_to_key[fingerprint] = entry.key
                appended_entries.append(entry)
                canonical_key = entry.key
            key_map[entry.key] = canonical_key

        provenance = PROVENANCE_TEMPLATE.format(path=survey.source_path.as_posix())
        if survey.title == existing_root_title:
            if provenance not in notes_text:
                notes_lines.insert(2, "")
                notes_lines.insert(3, provenance)
                notes_text = "\\n".join(notes_lines).rstrip() + "\\n"
                notes_lines = notes_text.splitlines()
            skipped_titles.append(survey.title)
            continue

        if f"## {survey.title}" in notes_text:
            skipped_titles.append(survey.title)
            continue

        rewritten_body = _rewrite_citations(_rewrite_links(_demote_headings(survey.body)), key_map)
        appended_sections.append(
            "\\n".join(
                [
                    f"## {survey.title}",
                    "",
                    provenance,
                    "",
                    rewritten_body.strip(),
                ]
            ).rstrip()
        )
        imported_titles.append(survey.title)

    if appended_sections:
        notes_text = notes_text.rstrip() + "\\n\\n" + "\\n\\n".join(appended_sections) + "\\n"
        notes_path.write_text(notes_text)
    else:
        notes_path.write_text(notes_text)

    if appended_entries:
        with bibliography_path.open("a") as handle:
            for entry in appended_entries:
                handle.write("\\n\\n" + entry.raw.strip() + "\\n")

    for child in sorted(legacy_root.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
        else:
            child.rmdir()
    legacy_root.rmdir()

    return MigrationReport(
        imported_titles=imported_titles,
        skipped_titles=skipped_titles,
        appended_bib_keys=[entry.key for entry in appended_entries],
    )
```

- [ ] **Step 2: Add the thin wrapper script**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from autoqec_zoo.kb_migration import migrate_repo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    report = migrate_repo(args.repo_root.resolve())
    print(
        "migrated kb:",
        f"imported={len(report.imported_titles)}",
        f"skipped={len(report.skipped_titles)}",
        f"appended_bib={len(report.appended_bib_keys)}",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the migration tests again**

Run: `python3 -m pytest tests/test_kb_migration.py -v`
Expected: PASS

- [ ] **Step 4: Commit the migration logic**

```bash
git add src/autoqec_zoo/kb_migration.py scripts/migrate_sci_brain_kb.py tests/test_kb_migration.py
git commit -m "feat: add sci-brain kb migration helper"
```

## Task 3: Run the Migration on the Real Repo and Update Docs

**Files:**
- Modify: `.knowledge/NOTES.md`
- Modify: `ref.bib`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_source_data.py`

- [ ] **Step 1: Run the migration script against the repo root**

Run: `python3 scripts/migrate_sci_brain_kb.py --repo-root .`
Expected: one skipped survey (`high-distance-codes-with-transversal-logical-operations`), multiple imported surveys, nonzero appended bibliography entries, and `.claude/survey/` removed

- [ ] **Step 2: Verify the migrated notes and bibliography diff before editing docs**

Run: `git diff -- .knowledge/NOTES.md ref.bib`
Expected: `.knowledge/NOTES.md` gains imported sections for:
- `Finite-code transversal gates: detection, search targets, and an AutoQEC workflow`
- `Finite-length BB and LP codes for exact distance and transversal gates`
- `QEC Code Discovery Patterns`

Expected: `.knowledge/NOTES.md` keeps exactly one top-level `High-distance codes with transversal logical operations` heading and gains a provenance line for the absorbed legacy survey

Expected: `ref.bib` gains legacy-only entries such as:
- `Rains1997`
- `Cross2009`
- `Chuang2009`
- `Crosswhite2011`
- `Cao2022`
- `Olle2024`
- `Haah2021`

- [ ] **Step 3: Update the top-level docs to describe only the 0.3 KB layout**

```markdown
# README.md

## What Lives Here

- `.knowledge/`: local paper library and working notes for literature-grounded discussion
- `ref.bib`: project-level bibliography namespace shared by the KB and any future manuscripts
- `zoo/`: source-of-truth code cards, evidence records, checked-in finite instances, and derived browse artifacts
```

```markdown
# CLAUDE.md

## Knowledge base (`.knowledge/`) — check first

When answering any technical question on this repo's topics, search `.knowledge/` and
consult `ref.bib` before anything else.

- `.knowledge/INDEX.md` — table of contents for downloaded references
- `.knowledge/NOTES.md` — project-level survey notes and imported legacy survey notes
- `ref.bib` — project-level bibliography namespace for the KB
```

```markdown
# CLAUDE.md

## What is not in this repo

- No main implementation code yet
- No LaTeX manuscript draft yet (`main.tex`, article-level build files, etc.)
- No committed Zulip archive; `.zulip/` is per-machine state
```

- [ ] **Step 4: Add repo-state assertions for the migrated layout**

```python
def test_repo_uses_single_project_kb_layout() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()
    notes = (REPO_ROOT / ".knowledge" / "NOTES.md").read_text()
    bibliography = (REPO_ROOT / "ref.bib").read_text()

    assert not (REPO_ROOT / ".claude" / "survey").exists()
    assert "ref.bib" in readme
    assert "ref.bib" in claude
    assert "No LaTeX draft yet (`main.tex`, `ref.bib`, etc.)" not in claude
    assert "Finite-code transversal gates: detection, search targets, and an AutoQEC workflow" in notes
    assert "Finite-length BB and LP codes for exact distance and transversal gates" in notes
    assert "QEC Code Discovery Patterns" in notes
    assert notes.count("High-distance codes with transversal logical operations") == 1
    assert "@article{Rains1997," in bibliography
    assert "@article{Cross2009," in bibliography
```

- [ ] **Step 5: Run the focused migration and repo-state tests**

Run: `python3 -m pytest tests/test_kb_migration.py tests/test_source_data.py -v`
Expected: PASS

- [ ] **Step 6: Commit the migrated repo state**

```bash
git add .knowledge/NOTES.md ref.bib README.md CLAUDE.md tests/test_source_data.py
git commit -m "chore: migrate knowledge base to sci-brain 0.3 layout"
```

## Task 4: Verify Cleanup and Finish the Layout Removal

**Files:**
- Delete: `.claude/survey/finite-code-transversal-gates/summary.md`
- Delete: `.claude/survey/finite-code-transversal-gates/references.bib`
- Delete: `.claude/survey/finite-length-bb-lp-exact-distance-transversal-gates/summary.md`
- Delete: `.claude/survey/finite-length-bb-lp-exact-distance-transversal-gates/references.bib`
- Delete: `.claude/survey/high-distance-codes-with-transversal-logical-operations/summary.md`
- Delete: `.claude/survey/high-distance-codes-with-transversal-logical-operations/references.bib`
- Delete: `.claude/survey/qec-code-discovery-patterns/summary.md`
- Delete: `.claude/survey/qec-code-discovery-patterns/references.bib`

- [ ] **Step 1: Confirm the legacy survey tree is gone from the working tree**

Run: `rg --files .claude | sed -n '1,120p'`
Expected: no `.claude/survey/...` paths remain

- [ ] **Step 2: Run the default test suite**

Run: `python3 -m pytest -v`
Expected: PASS

- [ ] **Step 3: Inspect the final diff for only intended migration changes**

Run: `git diff --stat HEAD~1..HEAD`
Expected: note migration helper, migrated notes/bibliography/docs, repo-state tests, and deletion of `.claude/survey/`

- [ ] **Step 4: Commit the legacy-tree deletion if it was not already included**

```bash
git add -u .claude/survey
git commit -m "chore: remove legacy sci-brain survey registry"
```

## Self-Review

- Spec coverage:
  - note merge: Task 2 + Task 3
  - BibTeX merge and cite-key normalization: Task 2 + Task 3
  - duplicate/high-distance handling: Task 1 + Task 2 + Task 3
  - doc updates: Task 3
  - legacy tree removal: Task 2 + Task 4
  - verification: Task 1, Task 3, Task 4
- Placeholder scan: no `TBD`, no implicit “handle later” instructions, every task includes exact files and commands
- Type consistency:
  - `MigrationReport.imported_titles`, `skipped_titles`, `appended_bib_keys`
  - `migrate_repo(repo_root: Path) -> MigrationReport`
  - provenance marker format is consistent across tests and implementation
