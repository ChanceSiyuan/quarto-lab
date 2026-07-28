from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VALID_FIXTURE = ROOT / "tests" / "fixtures" / "knowledge" / "valid"


class KnowledgeCheckCliTest(unittest.TestCase):
    def test_valid_trusted_tree_reports_page_and_topic_counts(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.knowledge",
                "check",
                "--repo-root",
                str(VALID_FIXTURE),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout,
            "Knowledge valid: 3 pages across 2 topics.\n",
        )
        self.assertEqual(completed.stderr, "")

    def test_missing_reading_map_target_reports_stable_source_diagnostic(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE / "theory", repo_root / "theory")
            index = repo_root / "theory" / "ising" / "index.qmd"
            index.write_text(
                index.read_text(encoding="utf-8").replace(
                    "(proof.qmd)",
                    "(missing.qmd)",
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.knowledge",
                    "check",
                    "--repo-root",
                    str(repo_root),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(
            completed.stderr,
            "theory/ising/index.qmd:12:3 [LINK_MISSING] "
            "Reading-map target does not exist: missing.qmd\n",
        )

    def test_topic_without_reading_map_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE / "theory", repo_root / "theory")
            index = repo_root / "theory" / "ising" / "index.qmd"
            index.write_text(
                index.read_text(encoding="utf-8").replace(
                    "## Reading map",
                    "## Pages",
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.knowledge",
                    "check",
                    "--repo-root",
                    str(repo_root),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(
            completed.stderr,
            "theory/ising/index.qmd:1:1 [INDEX_READING_MAP_REQUIRED] "
            "A topic index requires exactly one level-two Reading map.\n",
        )

    def test_direct_child_omitted_from_reading_map_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE / "theory", repo_root / "theory")
            index = repo_root / "theory" / "ising" / "index.qmd"
            index.write_text(
                index.read_text(encoding="utf-8").replace(
                    "- [A verified statement](proof.qmd)\n",
                    "No pages yet.\n",
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.knowledge",
                    "check",
                    "--repo-root",
                    str(repo_root),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(
            completed.stderr,
            "theory/ising/proof.qmd:1:1 [ORPHAN_CHILD] "
            "Direct child is missing from theory/ising/index.qmd Reading map.\n",
        )

    def test_page_cannot_override_quarto_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE / "theory", repo_root / "theory")
            page = repo_root / "theory" / "ising" / "proof.qmd"
            page.write_text(
                page.read_text(encoding="utf-8").replace(
                    "description: A fixture statement about an Ising model.\n",
                    "description: A fixture statement about an Ising model.\n"
                    "execute: true\n",
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.knowledge",
                    "check",
                    "--repo-root",
                    str(repo_root),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(
            completed.stderr,
            "theory/ising/proof.qmd:4:1 [FRONTMATTER_KEY_FORBIDDEN] "
            "Frontmatter key is not allowed in trusted knowledge: execute\n",
        )

    def test_reading_map_cannot_escape_theory(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE / "theory", repo_root / "theory")
            (repo_root / "drafts").mkdir()
            (repo_root / "drafts" / "secret.qmd").write_text(
                "# Untrusted\n",
                encoding="utf-8",
            )
            index = repo_root / "theory" / "ising" / "index.qmd"
            index.write_text(
                index.read_text(encoding="utf-8").replace(
                    "(proof.qmd)",
                    "(../../drafts/secret.qmd)",
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.knowledge",
                    "check",
                    "--repo-root",
                    str(repo_root),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(
            completed.stderr,
            "theory/ising/index.qmd:12:3 [LINK_OUTSIDE_KNOWLEDGE] "
            "Local target escapes theory/: ../../drafts/secret.qmd\n",
        )

    def test_reading_map_accepts_a_commonmark_target_with_spaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE / "theory", repo_root / "theory")
            page = repo_root / "theory" / "ising" / "proof.qmd"
            page.rename(repo_root / "theory" / "ising" / "proof note.qmd")
            index = repo_root / "theory" / "ising" / "index.qmd"
            index.write_text(
                index.read_text(encoding="utf-8").replace(
                    "(proof.qmd)",
                    "(<proof note.qmd>)",
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.knowledge",
                    "check",
                    "--repo-root",
                    str(repo_root),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout,
            "Knowledge valid: 3 pages across 2 topics.\n",
        )


class KnowledgeResolveCliTest(unittest.TestCase):
    def test_exact_alias_returns_the_human_curated_reading_bundle(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.knowledge",
                "resolve",
                "--query",
                "TFIM",
                "--repo-root",
                str(VALID_FIXTURE),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "schemaVersion": 1,
                "query": "TFIM",
                "status": "match",
                "bundle": {
                    "topic": "theory/ising/index.qmd",
                    "ancestorIndexes": [
                        "theory/index.qmd",
                        "theory/ising/index.qmd",
                    ],
                    "contentPages": ["theory/ising/proof.qmd"],
                    "orderedFiles": [
                        "theory/index.qmd",
                        "theory/ising/index.qmd",
                        "theory/ising/proof.qmd",
                    ],
                },
                "alternatives": [],
            },
        )
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
