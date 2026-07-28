from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RenderSiteSkillContractTest(unittest.TestCase):
    def test_skill_uses_only_the_validated_safe_rendering_seams(self):
        skill = (ROOT / "skills" / "render-site" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        for required in (
            "make knowledge-check",
            "make knowledge-build",
            "make knowledge-preview",
            "## Reading map",
            "--no-execute",
            "last verified `_site/`",
        ):
            self.assertIn(required, skill)
        for obsolete in (
            "scripts/update_theory_nav.py",
            "quarto render theory/",
            "quarto render --profile fast",
            "| Preview server | `quarto preview",
            "AUTO NOTES TABLE",
        ):
            self.assertNotIn(obsolete, skill)


if __name__ == "__main__":
    unittest.main()
