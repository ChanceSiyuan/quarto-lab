from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MakefileContractTest(unittest.TestCase):
    def test_human_and_agent_commands_are_discoverable(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        for target in (
            "knowledge-check:",
            "knowledge-resolve:",
            "knowledge-build:",
            "knowledge-preview:",
            "build:",
            "test:",
        ):
            self.assertIn(target, makefile)

    def test_resolve_requires_an_explicit_query(self):
        completed = subprocess.run(
            ["make", "--silent", "knowledge-resolve"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertTrue(
            completed.stderr.startswith(
            'Usage: make knowledge-resolve QUERY="research question"\n',
            ),
            completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
