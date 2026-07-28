from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from scripts import knowledge


class KnowledgeBuildCliTest(unittest.TestCase):
    def test_build_delegates_to_the_safe_public_builder(self):
        output = Path("/fixture/repo/_site")
        stdout = StringIO()

        with mock.patch.object(
            knowledge,
            "build_knowledge_site",
            return_value=output,
            create=True,
        ) as builder, redirect_stdout(stdout):
            status = knowledge.main(
                ["build", "--repo-root", "/fixture/repo"]
            )

        self.assertEqual(status, 0)
        builder.assert_called_once_with(repo_root=Path("/fixture/repo"))
        self.assertEqual(stdout.getvalue(), "Knowledge site built: _site\n")

    def test_render_script_cannot_bypass_the_safe_builder(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "render_site.sh"
        )
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("-m scripts.knowledge build", script)
        self.assertNotIn("quarto render", script)
        completed = subprocess.run(
            ["bash", str(script_path), "--output-dir", "/tmp/unsafe"],
            cwd=script_path.parents[1],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(
            completed.stderr,
            "Usage: ./scripts/render_site.sh\n",
        )

    def test_preview_delegates_to_the_safe_public_previewer(self):
        stdout = StringIO()

        with mock.patch.object(
            knowledge,
            "preview_knowledge_site",
            create=True,
        ) as previewer, redirect_stdout(stdout):
            status = knowledge.main(
                ["preview", "--repo-root", "/fixture/repo"]
            )

        self.assertEqual(status, 0)
        previewer.assert_called_once_with(repo_root=Path("/fixture/repo"))
        self.assertEqual(stdout.getvalue(), "Knowledge preview stopped.\n")

    def test_quarto_process_failure_is_reported_without_a_traceback(self):
        stderr = StringIO()
        failure = subprocess.CalledProcessError(
            1,
            ["quarto", "render", ".", "--no-execute"],
        )

        with mock.patch.object(
            knowledge,
            "build_knowledge_site",
            side_effect=failure,
        ), redirect_stderr(stderr):
            status = knowledge.main(
                ["build", "--repo-root", "/fixture/repo"]
            )

        self.assertEqual(status, 1)
        self.assertIn("returned non-zero exit status 1", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
