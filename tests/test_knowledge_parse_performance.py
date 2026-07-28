from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from lib.knowledge import load_knowledge, validate_knowledge
from lib.knowledge import parser


def _write_page(path: Path, *, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: {title}\n---\n\n{body}",
        encoding="utf-8",
    )


def _write_counted_tree(repo_root: Path) -> tuple[str, ...]:
    identifiers = ("root", "topic", "note")
    _write_page(
        repo_root / "theory" / "index.qmd",
        title="Knowledge",
        body=(
            "<!-- PARSE-ID: root -->\n\n"
            "## Reading map\n\n"
            "- [Topic](topic/index.qmd)\n"
        ),
    )
    _write_page(
        repo_root / "theory" / "topic" / "index.qmd",
        title="Topic",
        body=(
            "<!-- PARSE-ID: topic -->\n\n"
            "## Reading map\n\n"
            "- [Note](note.qmd)\n"
        ),
    )
    _write_page(
        repo_root / "theory" / "topic" / "note.qmd",
        title="Note",
        body=(
            "<!-- PARSE-ID: note -->\n\n"
            "`{{< rejected-even-in-code >}}`\n\n"
            "[Unsafe scheme remains visible](file:secret.txt)\n"
        ),
    )
    return identifiers


def _count_markdown_parses(
    repo_root: Path,
    operation,
) -> tuple[Counter[str], object]:
    original = parser._parse_markdown
    counts: Counter[str] = Counter()

    def counted(body: str):
        match = re.search(r"PARSE-ID: ([a-z]+)", body)
        if match is not None:
            counts[match.group(1)] += 1
        return original(body)

    with patch.object(parser, "_parse_markdown", side_effect=counted):
        result = operation(repo_root)
    return counts, result


class KnowledgeParsePerformanceTest(unittest.TestCase):
    def test_load_parses_each_page_at_most_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            identifiers = _write_counted_tree(repo_root)

            counts, graph = _count_markdown_parses(repo_root, load_knowledge)

        self.assertEqual(len(graph.pages), len(identifiers))
        self.assertEqual(counts, Counter({identifier: 1 for identifier in identifiers}))

    def test_validation_parses_once_without_hiding_unsafe_constructs(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            identifiers = _write_counted_tree(repo_root)

            counts, report = _count_markdown_parses(repo_root, validate_knowledge)

        self.assertEqual(counts, Counter({identifier: 1 for identifier in identifiers}))
        self.assertEqual(
            [diagnostic.code for diagnostic in report.diagnostics],
            [
                "QUARTO_SHORTCODE_FORBIDDEN",
                "LINK_SCHEME_UNSUPPORTED",
            ],
        )

    def test_a_later_validation_reads_same_size_same_mtime_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            root_index = repo_root / "theory" / "index.qmd"
            _write_page(
                root_index,
                title="Knowledge",
                body="## Reading map\n\nSafe text 1234\n",
            )
            before = validate_knowledge(repo_root)
            original_stat = root_index.stat()
            original_source = root_index.read_text(encoding="utf-8")
            changed_source = original_source.replace(
                "Safe text 1234",
                "{{< danger >}}",
            )
            self.assertEqual(len(changed_source), len(original_source))
            root_index.write_text(changed_source, encoding="utf-8")
            os.utime(
                root_index,
                ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
            )

            after = validate_knowledge(repo_root)

        self.assertTrue(before.ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in after.diagnostics],
            ["QUARTO_SHORTCODE_FORBIDDEN"],
        )


if __name__ == "__main__":
    unittest.main()
