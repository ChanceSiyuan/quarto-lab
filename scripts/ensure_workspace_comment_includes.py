#!/usr/bin/env python3
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "workspace"
COMMENTS_ROOT = WORKSPACE / "comments"

START_MARK = "<!-- COMMENTS-START -->"
END_MARK = "<!-- COMMENTS-END -->"


def build_block(qmd_path: Path) -> str:
    rel_from_root = qmd_path.relative_to(ROOT)
    issue_html = "/" + rel_from_root.with_suffix(".html").as_posix()
    comment_url = "/workspace/comment.html?term=" + issue_html
    rel_from_workspace = qmd_path.relative_to(WORKSPACE)
    comment_path = COMMENTS_ROOT / rel_from_workspace.with_suffix('.md')
    include_rel = os.path.relpath(comment_path, qmd_path.parent).replace(os.sep, "/")
    include_line = "{{< include " + include_rel + " >}}"
    block = (
        "\n\n## Comments\n"
        f"{START_MARK}\n"
        f"[Write a comment]({comment_url})\n"
        f"{include_line}\n"
        f"{END_MARK}\n"
    )
    return block


def ensure_include(qmd_path: Path) -> bool:
    text = qmd_path.read_text(encoding="utf-8")
    changed = False

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            head = parts[1]
            body = parts[2]
            if "comments:" in head:
                head_new = re.sub(r"^comments:\\s*.*$", "comments: false", head, flags=re.M)
            else:
                head_lines = head.rstrip("\n").split("\n")
                head_lines.append("comments: false")
                head_new = "\n".join(head_lines) + "\n"
            new_text = "---" + head_new + "---" + body
            if new_text != text:
                text = new_text
                changed = True
    block = build_block(qmd_path)

    if START_MARK in text and END_MARK in text:
        # Replace the include block content (keep markers)
        pre = text.split(START_MARK)[0]
        post = text.split(END_MARK)[1]
        new_text = pre + START_MARK + "\n" + block.split(START_MARK)[1].split(END_MARK)[0].strip() + "\n" + END_MARK + post
        if new_text != text:
            qmd_path.write_text(new_text, encoding="utf-8")
            return True
        if changed:
            qmd_path.write_text(text, encoding="utf-8")
        return changed

    # Insert before giscus marker if present
    giscus_marker = "<!-- Giscus comments will automatically appear below -->"
    if giscus_marker in text:
        new_text = text.replace(giscus_marker, block + "\n" + giscus_marker)
    else:
        new_text = text.rstrip() + block + "\n"

    qmd_path.write_text(new_text, encoding="utf-8")
    return True


def main():
    issue_files = sorted(WORKSPACE.glob("**/issues/issue*.qmd"))
    if not issue_files:
        print("No issue files found under workspace/**/issues/issue*.qmd")
        return

    changed = 0
    for qmd in issue_files:
        if ensure_include(qmd):
            changed += 1

    print(f"Updated {changed} issue files with comment includes.")


if __name__ == "__main__":
    main()
