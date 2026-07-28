from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil


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
    start: int | None = None
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
        r'(?ms)^\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*[{"](.*?)[}"]\s*,?\s*$',
        rest,
    ):
        fields[match.group(1).lower()] = " ".join(match.group(2).split())
    return BibEntry(
        key=key.strip(),
        entry_type=entry_type,
        raw=raw.strip(),
        fields=fields,
    )


def _entry_fingerprint(entry: BibEntry) -> tuple[str, str]:
    if doi := entry.fields.get("doi"):
        return ("doi", _normalize(doi))
    if eprint := entry.fields.get("eprint"):
        return ("eprint", _normalize(eprint))
    return ("title", _normalize(entry.fields.get("title", entry.key)))


def _entry_match_identifiers(entry: BibEntry) -> list[tuple[str, str]]:
    identifiers: list[tuple[str, str]] = []
    for field in ("doi", "eprint", "title"):
        value = entry.fields.get(field)
        if value:
            identifiers.append((field, _normalize(value)))
    if not identifiers:
        identifiers.append(("key", _normalize(entry.key)))
    return identifiers


def _find_matching_key(
    entry: BibEntry, identifier_to_key: dict[tuple[str, str], str]
) -> str | None:
    for identifier in _entry_match_identifiers(entry):
        if canonical_key := identifier_to_key.get(identifier):
            return canonical_key
    return None


def _index_entry_identifiers(
    entry: BibEntry, canonical_key: str, identifier_to_key: dict[tuple[str, str], str]
) -> None:
    for identifier in _entry_match_identifiers(entry):
        identifier_to_key.setdefault(identifier, canonical_key)


def _has_markdown_heading(text: str, title: str) -> bool:
    return re.search(rf"(?m)^##+\s+{re.escape(title)}\s*$", text) is not None


def _load_bibliography(path: Path) -> list[BibEntry]:
    text = path.read_text() if path.exists() else ""
    return [_parse_bib_entry(raw) for raw in _split_bib_entries(text)]


def _extract_title_and_body(summary_path: Path) -> tuple[str, str]:
    lines = summary_path.read_text().splitlines()
    title = lines[0].removeprefix("# ").strip()
    body = "\n".join(lines[1:]).strip()
    return title, body


def _demote_headings(text: str) -> str:
    return re.sub(r"(?m)^(#{1,6})\s", lambda match: "#" + match.group(1) + " ", text)


def _rewrite_links(text: str) -> str:
    return text.replace("](../../../.knowledge/", "](")


def _rewrite_citations(text: str, key_map: dict[str, str]) -> str:
    rewritten = text
    for old_key, new_key in sorted(key_map.items(), key=lambda item: len(item[0]), reverse=True):
        rewritten = rewritten.replace(f"[@{old_key}]", f"[@{new_key}]")
        rewritten = re.sub(rf"\[@{re.escape(old_key)}\]", f"[@{new_key}]", rewritten)
        rewritten = re.sub(rf"\[{re.escape(old_key)}\](?!\()", f"[@{new_key}]", rewritten)
    return rewritten


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
    existing_root_title = notes_lines[0].removeprefix("# ").strip() if notes_lines else ""

    canonical_entries = _load_bibliography(bibliography_path)
    identifier_to_key: dict[tuple[str, str], str] = {}
    for entry in canonical_entries:
        _index_entry_identifiers(entry, entry.key, identifier_to_key)
    appended_entries: list[BibEntry] = []
    imported_titles: list[str] = []
    skipped_titles: list[str] = []
    appended_sections: list[str] = []

    for survey in _load_surveys(legacy_root):
        key_map: dict[str, str] = {}
        for entry in survey.bib_entries:
            canonical_key = _find_matching_key(entry, identifier_to_key)
            if canonical_key is None:
                canonical_key = entry.key
                appended_entries.append(entry)
            _index_entry_identifiers(entry, canonical_key, identifier_to_key)
            key_map[entry.key] = canonical_key

        provenance = PROVENANCE_TEMPLATE.format(path=survey.source_path.as_posix())
        if survey.title == existing_root_title:
            if provenance not in notes_text:
                insert_at = 2 if len(notes_lines) >= 2 else len(notes_lines)
                notes_lines[insert_at:insert_at] = ["", provenance]
                notes_text = "\n".join(notes_lines).rstrip() + "\n"
                notes_lines = notes_text.splitlines()
            skipped_titles.append(survey.title)
            continue

        if _has_markdown_heading(notes_text, survey.title):
            skipped_titles.append(survey.title)
            continue

        rewritten_body = _rewrite_citations(_rewrite_links(_demote_headings(survey.body)), key_map)
        appended_sections.append(
            "\n".join(
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
        notes_text = notes_text.rstrip() + "\n\n" + "\n\n".join(appended_sections) + "\n"
    notes_path.write_text(notes_text)

    if appended_entries:
        existing_bibliography = bibliography_path.read_text() if bibliography_path.exists() else ""
        suffix = "".join(f"\n\n{entry.raw.strip()}\n" for entry in appended_entries)
        bibliography_path.write_text(existing_bibliography.rstrip() + suffix + ("\n" if suffix else ""))

    shutil.rmtree(legacy_root)

    return MigrationReport(
        imported_titles=imported_titles,
        skipped_titles=skipped_titles,
        appended_bib_keys=[entry.key for entry in appended_entries],
    )
