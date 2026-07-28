from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from lib.knowledge.site import build_knowledge_site
from lib.knowledge.validate import KnowledgeValidationError


ROOT = Path(__file__).resolve().parents[1]
RENDER_FIXTURE = ROOT / "tests" / "fixtures" / "knowledge" / "render"


class KnowledgeQuartoIntegrationTest(unittest.TestCase):
    def test_code_examples_cannot_expand_environment_shortcodes(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(RENDER_FIXTURE, repo_root)
            page = repo_root / "theory" / "nested" / "index.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\nInline `{{< env REVIEW_CODE_SECRET >}}`.\n"
                + "\n```text\n"
                + "{{< env REVIEW_CODE_SECRET >}}\n"
                + "```\n",
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {"REVIEW_CODE_SECRET": "REVIEW_CODE_LEAK_728"},
            ):
                with self.assertRaises(KnowledgeValidationError) as raised:
                    build_knowledge_site(repo_root=repo_root)

            self.assertEqual(
                [
                    diagnostic.code
                    for diagnostic in raised.exception.diagnostics
                ],
                [
                    "QUARTO_SHORTCODE_FORBIDDEN",
                    "QUARTO_SHORTCODE_FORBIDDEN",
                ],
            )
            self.assertFalse((repo_root / "_site").exists())

    def test_real_quarto_renders_only_trusted_static_knowledge(self):
        version = subprocess.run(
            ["quarto", "--version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(version, "1.9.38")

        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(RENDER_FIXTURE, repo_root, dirs_exist_ok=True)

            with mock.patch.dict(
                os.environ,
                {"XDG_CACHE_HOME": str(repo_root / ".cache")},
            ):
                output = build_knowledge_site(repo_root=repo_root)

            root_html = (output / "index.html").read_text(encoding="utf-8")
            theory_html = (output / "theory" / "index.html").read_text(
                encoding="utf-8"
            )
            nested_html = (
                output / "theory" / "nested" / "index.html"
            ).read_text(encoding="utf-8")
            rendered_paths = [
                path.relative_to(output).as_posix()
                for path in output.rglob("*")
                if path.is_file()
            ]

            self.assertIn("Render Fixture Home", root_html)
            self.assertIn("Rendered Research Knowledge", theory_html)
            self.assertIn('class="math inline"', nested_html)
            self.assertIn('class="math display"', nested_html)
            self.assertIn('id="ref-fixture2026"', nested_html)
            self.assertIn("Noether", nested_html)
            self.assertIn('src="diagram.svg"', nested_html)
            self.assertEqual(
                (output / "theory" / "nested" / "diagram.svg").read_bytes(),
                (
                    RENDER_FIXTURE
                    / "theory"
                    / "nested"
                    / "diagram.svg"
                ).read_bytes(),
            )
            self.assertNotIn("EXECUTED_SENTINEL_OUTPUT", nested_html)
            self.assertFalse(
                any(
                    path.endswith((".qmd", ".bib"))
                    or "drafts" in Path(path).parts
                    or "conference" in Path(path).parts
                    for path in rendered_paths
                ),
                rendered_paths,
            )


if __name__ == "__main__":
    unittest.main()
