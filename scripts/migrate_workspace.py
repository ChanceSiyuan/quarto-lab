#!/usr/bin/env python3
"""Migrate Quarto workspace projects to GitHub repositories with issue tracking.

Usage:
    # Dry run (parse files, print output, execute nothing)
    python scripts/migrate_workspace.py --owner YOUR_GH_USER --dry-run

    # Migrate a single project
    python scripts/migrate_workspace.py --owner YOUR_GH_USER --projects Multi-shadow

    # Migrate all projects
    python scripts/migrate_workspace.py --owner YOUR_GH_USER

    # Skip repo creation, only migrate issues
    python scripts/migrate_workspace.py --owner YOUR_GH_USER --skip-repo-setup
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SKIP_DIRS = {"decoders"}

# Labels that GitHub creates by default on new repos
DEFAULT_GH_LABELS = {
    "bug", "enhancement", "documentation", "duplicate",
    "good first issue", "help wanted", "invalid", "question", "wontfix",
}

LABEL_COLORS = {
    "theory": "0075ca",
    "resource-theory": "0e8a16",
    "priority: high": "b60205",
}

GITIGNORE = """\
# LaTeX
*.aux
*.log
*.out
*.pdf
*.gz
*.fls
*.fdb_latexmk

# Python
__pycache__/
*.pyc
.ipynb_checkpoints/
.env
"""

SITE_DOMAIN = "https://chanceqlab.com"

# ── Regex patterns ─────────────────────────────────────────────────────────────

RE_YAML = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
RE_LABEL = re.compile(r"\[([^\]]+)\]\{\.label\s+\.label-\w+\}")
RE_ISSUE_POST = re.compile(r"^::: \{\.issue-post\}", re.MULTILINE)
RE_AUTHOR_LINE = re.compile(r"\*\*(.+?)\*\*\s+\w+(?:\s+\w+)*?\s+on\s+(.+)")

# Cleaning patterns (applied in order)
RE_TITLE_H1 = re.compile(
    r"^#\s+\[.*?\]\{\.status-\w+\}\s+.*?\[#\d+\]\{\.issue-number\}\s*$",
    re.MULTILINE,
)
RE_DIV_FENCE = re.compile(r"^:::\s*(?:\{[^}]*\})?\s*$", re.MULTILINE)
RE_STATUS_SPAN = re.compile(r"\[[^\]]*?\]\{\.status-\w+\}")
RE_ISSUE_NUM_SPAN = re.compile(r"\[#\d+\]\{\.issue-number\}")
RE_LABEL_SPAN = re.compile(r"\[[^\]]*?\]\{\.label\s+\.label-\w+\}")
RE_CITATION = re.compile(r"\[(@[^\]]+)\]")
RE_INTERNAL_LINK = re.compile(r"\[([^\]]+)\]\((/[^)]+)\)")
RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
RE_AVATAR_IMG = re.compile(
    r"!\[[^\]]*\]\(https://ui-avatars\.com[^)]*\)(?:\{[^}]*\})?"
)
RE_BLANK_LINES = re.compile(r"\n{3,}")


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class IssueComment:
    author: str
    date: str
    body: str


@dataclass
class ParsedIssue:
    number: int
    title: str
    status: str
    labels: list[str]
    body: str
    comments: list[IssueComment] = field(default_factory=list)


# ── Markdown cleaning ─────────────────────────────────────────────────────────

def _strip_citations(text: str) -> str:
    """Convert [@Key] -> [Key], [@K1; @K2] -> [K1; K2]."""
    def repl(m):
        return "[" + m.group(1).replace("@", "") + "]"
    return RE_CITATION.sub(repl, text)


def clean_markdown(text: str) -> str:
    """Strip Quarto-specific syntax while preserving standard markdown."""
    text = RE_TITLE_H1.sub("", text)
    text = RE_STATUS_SPAN.sub("", text)
    text = RE_ISSUE_NUM_SPAN.sub("", text)
    text = RE_LABEL_SPAN.sub("", text)
    text = RE_DIV_FENCE.sub("", text)
    text = _strip_citations(text)
    text = RE_INTERNAL_LINK.sub(
        lambda m: f"[{m.group(1)}]({SITE_DOMAIN}{m.group(2).replace('.qmd', '.html')})",
        text,
    )
    text = RE_HTML_COMMENT.sub("", text)
    text = RE_AVATAR_IMG.sub("", text)
    text = RE_BLANK_LINES.sub("\n\n", text)
    return text.strip()


# ── Issue parsing ──────────────────────────────────────────────────────────────

def parse_issue_qmd(filepath: Path) -> ParsedIssue:
    """Parse a .qmd issue file into structured data."""
    raw = filepath.read_text(encoding="utf-8")

    # Extract YAML frontmatter
    m = RE_YAML.match(raw)
    if not m:
        raise ValueError(f"No YAML frontmatter found in {filepath}")
    meta = yaml.safe_load(m.group(1))
    body_raw = raw[m.end():]

    title = meta["title"]
    status = meta.get("status", "Open")
    number = int(meta["number"])

    # Extract labels from {.issue-meta} spans in the body
    labels = RE_LABEL.findall(body_raw)

    # Segment into main body + comment blocks
    segments = RE_ISSUE_POST.split(body_raw)
    main_body = clean_markdown(segments[0])

    # Parse comments from remaining segments
    comments: list[IssueComment] = []
    for seg in segments[1:]:
        author, date = "Unknown", "Unknown"
        am = RE_AUTHOR_LINE.search(seg)
        if am:
            author = am.group(1)
            date = am.group(2).strip()

        comment_body = clean_markdown(seg)

        # Remove the author attribution line from the cleaned body
        if am:
            pattern = (
                r"\*\*" + re.escape(author) + r"\*\*"
                r"\s+\w+(?:\s+\w+)*?\s+on\s+"
                + re.escape(date)
            )
            comment_body = re.sub(pattern, "", comment_body, count=1).strip()

        if comment_body:
            comments.append(IssueComment(author=author, date=date, body=comment_body))

    return ParsedIssue(
        number=number, title=title, status=status,
        labels=labels, body=main_body, comments=comments,
    )


# ── Subprocess helper ──────────────────────────────────────────────────────────

def run_cmd(
    cmd: list[str],
    dry_run: bool = False,
    check: bool = True,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess | None:
    """Run a command, or log it in dry-run mode."""
    display = " ".join(cmd)
    if len(display) > 200:
        display = display[:200] + "..."
    log.info("  $ %s", display)

    if dry_run:
        return None

    result = subprocess.run(
        cmd, check=check, capture_output=True, text=True, cwd=cwd,
    )
    if result.stdout.strip():
        log.info("    -> %s", result.stdout.strip())
    if result.returncode != 0 and result.stderr.strip():
        log.warning("    stderr: %s", result.stderr.strip())
    return result


# ── Repo setup ─────────────────────────────────────────────────────────────────

def _scaffold_project(work_dir: Path, project_dir: Path, project_name: str) -> None:
    """Create the standard project file structure inside work_dir."""
    # .gitignore
    (work_dir / ".gitignore").write_text(GITIGNORE)

    # README.md
    (work_dir / "README.md").write_text(
        f"# {project_name}\n\n"
        f"Research project migrated from quarto-lab workspace.\n",
    )

    # paper/ directory
    paper_dir = work_dir / "paper"
    paper_dir.mkdir()
    (paper_dir / "figures").mkdir()
    (paper_dir / "sections").mkdir()

    # Copy refs.bib into paper/
    refs = project_dir / "refs.bib"
    if refs.exists():
        shutil.copy2(refs, paper_dir / "refs.bib")
    else:
        (paper_dir / "refs.bib").write_text("% Bibliography\n")

    # paper/main.tex scaffold
    (paper_dir / "main.tex").write_text(
        r"""\documentclass[aps,prl,twocolumn,superscriptaddress]{revtex4-2}

\usepackage{amsmath,amssymb,physics}
\usepackage{graphicx}
\usepackage{hyperref}

\begin{document}

\title{""" + project_name.replace("_", " ").replace("-", " ") + r"""}
\author{Chance}

\begin{abstract}
% TODO
\end{abstract}

\maketitle

% \input{sections/introduction}

\bibliography{refs}

\end{document}
""",
    )

    # src/ directory
    src_dir = work_dir / "src"
    src_dir.mkdir()
    (src_dir / "simulation.py").write_text(
        f'"""Simulation code for {project_name}."""\n',
    )
    (src_dir / "utils.py").write_text(
        f'"""Utility functions for {project_name}."""\n',
    )


def setup_repo(
    project_dir: Path, project_name: str, gh_owner: str, dry_run: bool,
) -> str:
    """Create a GitHub repo from the project directory. Returns 'owner/repo'."""
    repo_name = f"{gh_owner}/{project_name}"
    log.info("Setting up repo: %s", repo_name)

    work_dir = Path(tempfile.mkdtemp(prefix=f"migrate-{project_name}-"))
    log.info("  Temp dir: %s", work_dir)

    if not dry_run:
        _scaffold_project(work_dir, project_dir, project_name)

    run_cmd(["git", "init"], dry_run=dry_run, cwd=work_dir)
    run_cmd(["git", "add", "-A"], dry_run=dry_run, cwd=work_dir)
    run_cmd(
        ["git", "commit", "-m", "Initial commit: migrate from quarto-lab workspace"],
        dry_run=dry_run, cwd=work_dir,
    )
    run_cmd(
        ["gh", "repo", "create", repo_name, "--private", "--source=.", "--push"],
        dry_run=dry_run, cwd=work_dir,
    )

    if not dry_run:
        shutil.rmtree(work_dir)

    return repo_name


def ensure_labels(repo_name: str, labels: set[str], dry_run: bool) -> None:
    """Create custom labels on the GitHub repo (skips default ones)."""
    for label in sorted(labels):
        if label.lower() not in DEFAULT_GH_LABELS:
            color = LABEL_COLORS.get(label, "ededed")
            run_cmd(
                ["gh", "label", "create", label, "--repo", repo_name,
                 "--color", color, "--force"],
                dry_run=dry_run, check=False,
            )


# ── Issue migration ────────────────────────────────────────────────────────────

def _write_temp_md(content: str) -> str:
    """Write content to a temp .md file, return path."""
    fd, path = tempfile.mkstemp(suffix=".md", prefix="gh-body-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def migrate_issues(project_dir: Path, repo_name: str, dry_run: bool) -> None:
    """Parse all issue files and create them as GitHub Issues."""
    issues_dir = project_dir / "issues"
    if not issues_dir.is_dir():
        log.warning("No issues/ directory in %s", project_dir)
        return

    issue_files = sorted(issues_dir.glob("issue*.qmd"))
    if not issue_files:
        log.warning("No issue files found in %s", issues_dir)
        return

    # Parse all issues
    parsed: list[ParsedIssue] = []
    all_labels: set[str] = set()

    for f in issue_files:
        try:
            issue = parse_issue_qmd(f)
            parsed.append(issue)
            all_labels.update(issue.labels)
            log.info(
                "  Parsed: #%d %s [%d comments, labels: %s]",
                issue.number, issue.title, len(issue.comments),
                ", ".join(issue.labels) or "(none)",
            )
        except Exception as e:
            log.error("  Failed to parse %s: %s", f, e)

    parsed.sort(key=lambda i: i.number)

    # Create labels before issues
    ensure_labels(repo_name, all_labels, dry_run)

    # Create issues sequentially (preserves numbering)
    for issue in parsed:
        log.info("Creating issue #%d: %s", issue.number, issue.title)

        if dry_run:
            print(f"\n{'='*70}")
            print(f"ISSUE #{issue.number}: {issue.title}")
            print(f"Labels: {', '.join(issue.labels) or '(none)'}")
            print(f"Status: {issue.status}")
            print(f"{'─'*70}")
            print(issue.body)
            for i, c in enumerate(issue.comments, 1):
                print(f"\n{'─'*50}")
                print(f"COMMENT {i} by {c.author} on {c.date}:")
                print(c.body)
            print(f"{'='*70}\n")
            continue

        # Create the issue (use --body-file to avoid shell escaping of $ and \)
        body_file = _write_temp_md(issue.body)
        try:
            cmd = [
                "gh", "issue", "create",
                "--repo", repo_name,
                "--title", issue.title,
                "--body-file", body_file,
            ]
            if issue.labels:
                cmd.extend(["--label", ",".join(issue.labels)])

            result = run_cmd(cmd)

            # Parse the created issue number from the URL output
            gh_num = issue.number
            if result and result.stdout.strip():
                url_match = re.search(r"/issues/(\d+)", result.stdout.strip())
                if url_match:
                    gh_num = int(url_match.group(1))

            time.sleep(1)

            # Add comments with author attribution
            for comment in issue.comments:
                comment_text = (
                    f"> **{comment.author}** on {comment.date}\n\n"
                    f"{comment.body}"
                )
                comment_file = _write_temp_md(comment_text)
                try:
                    run_cmd([
                        "gh", "issue", "comment", str(gh_num),
                        "--repo", repo_name, "--body-file", comment_file,
                    ])
                finally:
                    os.unlink(comment_file)
                time.sleep(1)

            # Close if status indicates closed
            if issue.status.lower() not in ("open", "reopened"):
                run_cmd([
                    "gh", "issue", "close", str(gh_num), "--repo", repo_name,
                ])

        finally:
            os.unlink(body_file)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate Quarto workspace projects to GitHub repos with issues.",
    )
    parser.add_argument(
        "--workspace", type=Path, default=Path("workspace"),
        help="Path to workspace directory (default: workspace/)",
    )
    parser.add_argument(
        "--owner", required=True,
        help="GitHub username or org for created repos",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse files and print commands/output without executing",
    )
    parser.add_argument(
        "--projects", nargs="*",
        help="Only migrate these project names (default: all)",
    )
    parser.add_argument(
        "--skip-repo-setup", action="store_true",
        help="Skip repo creation; only migrate issues to existing repos",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Verify gh authentication
    auth = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True,
    )
    if auth.returncode != 0:
        log.error("Not authenticated with GitHub CLI. Run: gh auth login")
        raise SystemExit(1)
    log.info("GitHub CLI: authenticated")

    workspace = args.workspace
    if not workspace.is_dir():
        log.error("Workspace directory not found: %s", workspace)
        raise SystemExit(1)

    for entry in sorted(workspace.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in SKIP_DIRS:
            log.info("Skipping: %s (in skip list)", entry.name)
            continue
        if not (entry / "issues").is_dir():
            log.info("Skipping: %s (no issues/ directory)", entry.name)
            continue
        if args.projects and entry.name not in args.projects:
            continue

        log.info("")
        log.info("=" * 60)
        log.info("Project: %s", entry.name)
        log.info("=" * 60)

        if not args.skip_repo_setup:
            repo_name = setup_repo(entry, entry.name, args.owner, args.dry_run)
        else:
            repo_name = f"{args.owner}/{entry.name}"

        migrate_issues(entry, repo_name, args.dry_run)

    log.info("\nMigration complete.")


if __name__ == "__main__":
    main()
