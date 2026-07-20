#!/usr/bin/env python3
"""Build a combined ref.bib from rendered reference markdown frontmatter.

Walks `.knowledge/literature/<method>/*.md` (skipping INDEX.md and README.md),
parses each file's YAML frontmatter, and emits one BibTeX entry per unique
canonical reference. References appearing under multiple methods are merged
into one entry whose `keywords` field lists each method.

The intent: ref.bib becomes the human-edited source of truth for the
methodology library, while the per-method JSON manifests are recoverable
from it via bibtex_to_manifest.py.

Usage:
    python3 skills/download-ref/helpers/md_to_bibtex.py [--lit-root .knowledge/literature] [--out ref.bib]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Default location relative to the repo root.
DEFAULT_LIT_ROOT = Path(".knowledge/literature")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if not kv:
            continue
        k, v = kv.group(1), kv.group(2).strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        fields[k] = v
    return fields


def normalize_authors(raw: str) -> list[str]:
    """Split a single 'authors' string into individual names.

    Frontmatter stores authors as a comma-separated string; BibTeX wants
    `Family, Given and Family, Given and ...`. We keep the rendered ordering
    (already 'Given Family') and join with ' and '.
    """
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def propose_key(authors: list[str], year: str, title: str, fallback: str = "") -> str:
    if authors:
        last = authors[0].split()[-1].lower()
        last = re.sub(r"[^a-z]", "", last) or "anon"
    elif fallback:
        last = re.sub(r"[^a-z]", "", fallback.lower()) or "anon"
    else:
        last = "anon"
    year = (year or "nd").strip() or "nd"
    stop = {"a", "an", "the", "of", "on", "for", "and", "to", "is", "in", "with", "via"}
    words = [w for w in re.findall(r"[a-z]+", (title or "").lower()) if w not in stop]
    kw = words[0] if words else "ref"
    return f"{last}_{year}_{kw}"


def escape_braces(value: str) -> str:
    return value.replace("{", "\\{").replace("}", "\\}")


def build_bibtex(entry_type: str, key: str, fields: list[tuple[str, str]]) -> str:
    """Render a BibTeX entry with stable field order and brace-quoted values."""
    lines = [f"@{entry_type}{{{key},"]
    for name, value in fields:
        if value is None or value == "":
            continue
        lines.append(f"  {name} = {{{escape_braces(value)}}},")
    # Strip the trailing comma from the last field for cosmetic cleanliness.
    if len(lines) > 1 and lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
    lines.append("}")
    return "\n".join(lines)


def canonical_id(fm: dict[str, str]) -> str:
    """Pick a stable identifier that groups duplicates across method dirs."""
    if fm.get("arxiv_id"):
        return f"arxiv:{fm['arxiv_id']}"
    if fm.get("doi"):
        return f"doi:{fm['doi'].lower()}"
    cid = fm.get("canonical_id") or ""
    return f"id:{cid}"


def collect(lit_root: Path) -> dict[str, dict]:
    """Group frontmatter dicts by canonical id, accumulating methods."""
    groups: dict[str, dict] = {}
    for path in sorted(lit_root.glob("*/*.md")):
        if path.name in {"INDEX.md", "README.md"}:
            continue
        fm = parse_frontmatter(path)
        if not fm.get("title"):
            print(f"warn: no frontmatter in {path}", file=sys.stderr)
            continue
        method = path.parent.name
        cid = canonical_id(fm)
        slot = groups.setdefault(cid, {"fm": fm, "methods": [], "paths": []})
        if method not in slot["methods"]:
            slot["methods"].append(method)
        slot["paths"].append(path)
        # Prefer richer frontmatter (more fields filled in) when duplicates differ.
        if len([v for v in fm.values() if v]) > len([v for v in slot["fm"].values() if v]):
            slot["fm"] = fm
    return groups


def render_entry(fm: dict[str, str], methods: list[str]) -> str:
    """Translate a frontmatter dict + method tags into one BibTeX entry."""
    authors = normalize_authors(fm.get("authors", ""))
    rtype = fm.get("type", "")
    canonical = fm.get("canonical_id") or ""
    if rtype in {"stub", "github"} and canonical:
        # Preserve the canonical_id as the cite key so the rendered .md filename
        # (which is the slug = cite key for stubs) stays stable across regeneration.
        key = canonical.replace("/", "-")
    else:
        slug_fallback = canonical.split("/")[-1]
        key = propose_key(authors, fm.get("year", ""), fm.get("title", ""), fallback=slug_fallback)
    has_arxiv = bool(fm.get("arxiv_id"))
    has_doi = bool(fm.get("doi"))
    has_venue = bool(fm.get("venue"))

    if rtype == "stub":
        entry_type = "book" if "book" in (fm.get("note") or "").lower() else "misc"
    elif rtype == "github":
        entry_type = "software"
    elif has_venue and (has_arxiv or has_doi):
        entry_type = "article"
    elif has_arxiv:
        entry_type = "misc"  # arXiv preprint without a journal
    elif has_doi:
        entry_type = "article"
    else:
        entry_type = "misc"

    author_field = " and ".join(authors) if authors else ""

    fields: list[tuple[str, str]] = [
        ("author", author_field),
        ("title", fm.get("title", "")),
        ("year", fm.get("year", "")),
        ("journal" if entry_type == "article" else "howpublished", fm.get("venue", "")),
    ]
    if has_arxiv:
        fields += [
            ("eprint", fm["arxiv_id"]),
            ("archivePrefix", "arXiv"),
        ]
    if has_doi:
        fields.append(("doi", fm["doi"]))
    if rtype == "github" and canonical:
        # Preserve the owner/repo identity so bibtex_to_manifest.py can route
        # the entry back to the github bucket on re-derivation.
        fields.append(("repository", canonical))
    src = fm.get("source") or ""
    if src and not src.startswith("(none") and not has_arxiv and not has_doi:
        fields.append(("url", src))
    if fm.get("note"):
        fields.append(("note", fm["note"]))
    fields.append(("keywords", ", ".join(sorted(methods))))

    return build_bibtex(entry_type, key, fields)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lit-root", type=Path, default=DEFAULT_LIT_ROOT,
                   help="Directory containing per-method subdirs (default: .knowledge/literature)")
    p.add_argument("--out", type=Path, default=None,
                   help="Output ref.bib path (default: <lit-root>/ref.bib)")
    args = p.parse_args(argv)

    lit_root = args.lit_root
    if not lit_root.is_dir():
        print(f"missing: {lit_root}", file=sys.stderr)
        return 1
    out = args.out or (lit_root / "ref.bib")

    groups = collect(lit_root)
    if not groups:
        print(f"no .md frontmatter found under {lit_root}", file=sys.stderr)
        return 1

    # Sort by cite key for stable diffs.
    entries: list[tuple[str, str]] = []
    for cid, slot in groups.items():
        bib = render_entry(slot["fm"], slot["methods"])
        key = re.match(r"@\w+\{([^,]+),", bib).group(1)
        entries.append((key, bib))
    entries.sort(key=lambda kv: kv[0])

    header = (
        "% ref.bib — methodology references for quantum.harness.\n"
        "% Generated by skills/download-ref/helpers/md_to_bibtex.py from the\n"
        "% rendered frontmatter under .knowledge/literature/<method>/*.md.\n"
        "% Hand-edits are expected; re-running the migration only fills missing\n"
        "% entries. Method assignment is carried in `keywords = {<method>, ...}`.\n\n"
    )
    body = "\n\n".join(bib for _, bib in entries) + "\n"
    out.write_text(header + body)
    print(f"wrote {len(entries)} entries -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
