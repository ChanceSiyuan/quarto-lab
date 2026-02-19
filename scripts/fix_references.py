#!/usr/bin/env python3
"""Replace bare [CitationKey] references in GitHub issues with hyperlinked versions.

Parses refs.bib to build key→URL lookup, then updates every issue body and comment
so each citation becomes a clickable link (DOI, arXiv, or Google Scholar fallback).

  [Gottesman1998]          → [Gottesman1998](https://arxiv.org/abs/quant-ph/9807006)
  [Mermin1990; Peres1990]  → [Mermin1990](url), [Peres1990](url)
  **[Zhao2025]**           → **[Zhao2025](url)**
"""

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

# ── BibTeX parser ─────────────────────────────────────────────────────────────

RE_BIB_ENTRY = re.compile(r"@\w+\{([^,]+),\s*(.*?)\n\}", re.DOTALL)
RE_BIB_FIELD = re.compile(r"(\w+)\s*=\s*\{(.*?)\}(?:\s*,)?", re.DOTALL)


def parse_bib(path: Path) -> dict[str, dict]:
    """Parse .bib file into {key: {field: value}}."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    entries = {}
    for m in RE_BIB_ENTRY.finditer(text):
        key = m.group(1).strip()
        fields = {}
        for fm in RE_BIB_FIELD.finditer(m.group(2)):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        entries[key] = fields
    return entries


def resolve_url(fields: dict) -> str | None:
    """Find the best URL for a bib entry."""
    if "doi" in fields:
        return f"https://doi.org/{fields['doi']}"
    if "url" in fields:
        return fields["url"]
    if "eprint" in fields:
        return f"https://arxiv.org/abs/{fields['eprint']}"
    # ArXiv ID in journal field: "arXiv preprint quant-ph/9807006"
    journal = fields.get("journal", "")
    m = re.search(r"(quant-ph/\d+)", journal)
    if m:
        return f"https://arxiv.org/abs/{m.group(1)}"
    m = re.search(r"arXiv[: ](?:preprint )?(?:arXiv:)?(\S+)", journal, re.IGNORECASE)
    if m:
        return f"https://arxiv.org/abs/{m.group(1)}"
    # Construct DOI for PRL/PRA entries with volume+pages
    vol = fields.get("volume", "")
    pages = fields.get("pages", "").split("--")[0].split("-")[0].strip()
    jl = journal.lower()
    if vol and pages:
        if "physical review letters" in jl:
            return f"https://doi.org/10.1103/PhysRevLett.{vol}.{pages}"
        if "physical review a" in jl:
            return f"https://doi.org/10.1103/PhysRevA.{vol}.{pages}"
        if "physical review x" in jl:
            return f"https://doi.org/10.1103/PhysRevX.{vol}.{pages}"
    # Fallback: Google Scholar
    title = fields.get("title", "")
    author = fields.get("author", "").split(",")[0].split(" and ")[0].strip()
    if title:
        q = f"{author} {title}".replace(" ", "+")
        return f"https://scholar.google.com/scholar?q={q}"
    return None


# ── Reference replacement ─────────────────────────────────────────────────────

# Matches [Key] or [K1; K2] (citation keys) NOT followed by ( (already a link)
RE_CITE = re.compile(
    r"(\*\*)"                                    # group 1: optional bold open
    r"?\[([A-Za-z][\w]*(?:;\s*[A-Za-z][\w]*)*)\]"  # group 2: key(s)
    r"(\*\*)?"                                   # group 3: optional bold close
    r"(?!\()"                                    # NOT followed by (
)


def hyperlink_refs(text: str, lookup: dict[str, str]) -> str:
    """Replace [Key] with [Key](url) for all known citation keys."""

    def repl(m):
        prefix = m.group(1) or ""
        content = m.group(2)
        suffix = m.group(3) or ""
        keys = [k.strip() for k in content.split(";")]

        # Only replace if at least one key is in our lookup
        if not any(k in lookup for k in keys):
            return m.group(0)

        parts = []
        for k in keys:
            if k in lookup:
                parts.append(f"[{k}]({lookup[k]})")
            else:
                parts.append(f"[{k}]")

        joined = ", ".join(parts)
        return f"{prefix}{joined}{suffix}"

    return RE_CITE.sub(repl, text)


# ── GitHub helpers ────────────────────────────────────────────────────────────

def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def gh_json(cmd: list[str]):
    env = {**os.environ, "NO_COLOR": "1", "GH_FORCE_TTY": ""}
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
    return json.loads(strip_ansi(result.stdout))


def write_temp(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def update_issue_body(repo: str, number: int, body: str):
    path = write_temp(body)
    try:
        subprocess.run(
            ["gh", "issue", "edit", str(number), "--repo", repo, "--body-file", path],
            check=True, capture_output=True, text=True,
        )
    finally:
        os.unlink(path)


def update_comment(repo: str, comment_id: int, body: str):
    path = write_temp(json.dumps({"body": body}))
    try:
        subprocess.run(
            ["gh", "api", "-X", "PATCH",
             f"repos/{repo}/issues/comments/{comment_id}",
             "--input", path],
            check=True, capture_output=True, text=True,
        )
    finally:
        os.unlink(path)


# ── Main ──────────────────────────────────────────────────────────────────────

REPOS = {
    "ChanceSiyuan/OSF_research": Path("workspace/OSF_research/refs.bib"),
    "ChanceSiyuan/Early-stage-NA": Path("workspace/Early-stage-NA/refs.bib"),
}
# Multi-shadow has no refs.bib; its references are already inline URLs


def main():
    for repo, bib_path in REPOS.items():
        print(f"\n{'='*60}")
        print(f"  {repo}")
        print(f"{'='*60}")

        entries = parse_bib(bib_path)
        lookup = {}
        for key, fields in entries.items():
            url = resolve_url(fields)
            if url:
                lookup[key] = url

        print(f"  {len(lookup)} citation URLs resolved from {bib_path}")
        for k, u in sorted(lookup.items()):
            print(f"    {k:30s} → {u[:60]}")

        # Fetch issues
        issues = gh_json([
            "gh", "issue", "list", "--repo", repo, "--state", "all",
            "--limit", "100", "--json", "number,title,body",
        ])

        for issue in sorted(issues, key=lambda i: i["number"]):
            num = issue["number"]
            body = issue["body"]
            print(f"\n  Issue #{num}: {issue['title']}")

            # Update body
            new_body = hyperlink_refs(body, lookup)
            if new_body != body:
                print(f"    Updating body")
                update_issue_body(repo, num, new_body)
                time.sleep(1)
            else:
                print(f"    Body: no citation keys found")

            # Fetch and update comments
            comments = gh_json([
                "gh", "api", f"repos/{repo}/issues/{num}/comments",
            ])
            for comment in comments:
                cid = comment["id"]
                cbody = comment["body"]
                new_cbody = hyperlink_refs(cbody, lookup)
                if new_cbody != cbody:
                    print(f"    Updating comment {cid}")
                    update_comment(repo, cid, new_cbody)
                    time.sleep(1)

    print("\nDone!")


if __name__ == "__main__":
    main()
