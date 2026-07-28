from __future__ import annotations

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "read-knowledge" / "SKILL.md"


class ReadKnowledgeSkillContractTest(unittest.TestCase):
    def test_resolver_first_trust_contract_is_explicit(self):
        source = SKILL.read_text(encoding="utf-8")
        _, frontmatter, body = source.split("---", maxsplit=2)
        metadata = yaml.safe_load(frontmatter)

        self.assertEqual(metadata["name"], "read-knowledge")
        self.assertIn("research fact", metadata["description"])
        for required in (
            'make knowledge-resolve QUERY="<the user\'s research question>"',
            "bundle.orderedFiles",
            "match",
            "ambiguous",
            "no-match",
            "external-research/source-audit",
            "read every path",
            "does not write",
        ):
            self.assertIn(required, body)
        for forbidden_fallback in (
            "`drafts/` as",
            "`conference/` as",
            "literature as a trusted fallback",
        ):
            self.assertIn(forbidden_fallback, body)


if __name__ == "__main__":
    unittest.main()
