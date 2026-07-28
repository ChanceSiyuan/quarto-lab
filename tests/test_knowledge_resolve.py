from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from lib.knowledge.resolve import resolve_knowledge
from lib.knowledge.validate import KnowledgeValidationError


ROOT = Path(__file__).resolve().parents[1]
VALID_FIXTURE = ROOT / "tests" / "fixtures" / "knowledge" / "valid"


def _frontmatter(
    *,
    title: str,
    description: str,
    aliases: tuple[str, ...] = (),
) -> str:
    alias_lines = "".join(
        f"  - {json.dumps(alias, ensure_ascii=False)}\n" for alias in aliases
    )
    aliases_yaml = f"aliases:\n{alias_lines}" if aliases else ""
    return (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        f"{aliases_yaml}"
        "---\n\n"
    )


def _write_fixture(
    repo_root: Path,
    topics: tuple[
        tuple[
            str,
            str,
            tuple[
                tuple[str, str, str, tuple[str, ...], str],
                ...,
            ],
        ],
        ...,
    ],
) -> None:
    theory = repo_root / "theory"
    theory.mkdir()
    root_links = "".join(
        f"- [{title}]({directory}/index.qmd)\n"
        for directory, title, _pages in topics
    )
    (theory / "index.qmd").write_text(
        _frontmatter(title="Research Knowledge", description="Fixture root.")
        + "# Research Knowledge\n\n"
        + "## Reading map\n\n"
        + root_links,
        encoding="utf-8",
    )
    for directory, topic_title, pages in topics:
        topic = theory / directory
        topic.mkdir()
        page_links = "".join(
            f"- [{title}]({filename})\n"
            for filename, title, _description, _aliases, _body in pages
        )
        (topic / "index.qmd").write_text(
            _frontmatter(title=topic_title, description=f"{topic_title} fixture.")
            + f"# {topic_title}\n\n"
            + "## Reading map\n\n"
            + (page_links or "No content pages.\n"),
            encoding="utf-8",
        )
        for filename, title, description, aliases, body in pages:
            (topic / filename).write_text(
                _frontmatter(
                    title=title,
                    description=description,
                    aliases=aliases,
                )
                + f"# {title}\n\n"
                + body,
                encoding="utf-8",
            )


class KnowledgeResolveTest(unittest.TestCase):
    def test_query_without_unicode_letter_or_number_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Knowledge query must contain at least one letter or number",
        ):
            resolve_knowledge("　— !!!", VALID_FIXTURE)

    def test_nfkc_casefold_exact_index_title_expands_its_reading_map(self):
        result = resolve_knowledge("ＩＳＩＮＧ　ＭＯＤＥＬＳ", VALID_FIXTURE)

        self.assertEqual(
            result,
            {
                "schemaVersion": 1,
                "query": "ＩＳＩＮＧ　ＭＯＤＥＬＳ",
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

    def test_reading_bundle_strips_query_and_fragment_from_curated_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            shutil.copytree(VALID_FIXTURE, repo_root, dirs_exist_ok=True)
            root_index = repo_root / "theory" / "index.qmd"
            root_index.write_text(
                root_index.read_text(encoding="utf-8").replace(
                    "(ising/index.qmd)",
                    "(ising/index.qmd?from=root#topic)",
                ),
                encoding="utf-8",
            )
            topic_index = repo_root / "theory" / "ising" / "index.qmd"
            topic_index.write_text(
                topic_index.read_text(encoding="utf-8").replace(
                    "(proof.qmd)",
                    "(proof.qmd?view=full#statement)",
                ),
                encoding="utf-8",
            )

            result = resolve_knowledge("Ising Models", repo_root)

        self.assertEqual(result["status"], "match")
        self.assertEqual(
            result["bundle"]["orderedFiles"],
            [
                "theory/index.qmd",
                "theory/ising/index.qmd",
                "theory/ising/proof.qmd",
            ],
        )

    def test_body_terms_select_the_matching_content_page(self):
        result = resolve_knowledge("body search", VALID_FIXTURE)

        self.assertEqual(result["status"], "match")
        self.assertEqual(
            result["bundle"],
            {
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
        )

    def test_title_terms_outrank_the_same_terms_in_body_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(
                repo_root,
                (
                    (
                        "titles",
                        "Title Matches",
                        (
                            (
                                "target.qmd",
                                "Spectral Tensor Study",
                                "A title-level candidate.",
                                (),
                                "No fallback words here.",
                            ),
                        ),
                    ),
                    (
                        "bodies",
                        "Body Matches",
                        (
                            (
                                "fallback.qmd",
                                "Unrelated Study",
                                "A body-level candidate.",
                                (),
                                "The spectral tensor appears only in this body.",
                            ),
                        ),
                    ),
                ),
            )

            result = resolve_knowledge("spectral tensor", repo_root)

        self.assertEqual(result["status"], "match")
        self.assertEqual(result["bundle"]["topic"], "theory/titles/index.qmd")
        self.assertEqual(
            result["bundle"]["contentPages"],
            ["theory/titles/target.qmd"],
        )

    def test_exact_title_outranks_an_exact_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(
                repo_root,
                (
                    (
                        "title",
                        "Title Topic",
                        (
                            (
                                "target.qmd",
                                "Golden Answer",
                                "Exact title candidate.",
                                (),
                                "Title result.",
                            ),
                        ),
                    ),
                    (
                        "alias",
                        "Alias Topic",
                        (
                            (
                                "fallback.qmd",
                                "Different Name",
                                "Exact alias candidate.",
                                ("Golden Answer",),
                                "Alias result.",
                            ),
                        ),
                    ),
                ),
            )

            result = resolve_knowledge("golden answer", repo_root)

        self.assertEqual(
            result["bundle"]["contentPages"],
            ["theory/title/target.qmd"],
        )

    def test_exact_alias_outranks_title_terms(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(
                repo_root,
                (
                    (
                        "alias",
                        "Alias Topic",
                        (
                            (
                                "target.qmd",
                                "Different Name",
                                "Exact alias candidate.",
                                ("Spectral",),
                                "Alias result.",
                            ),
                        ),
                    ),
                    (
                        "title",
                        "Title Topic",
                        (
                            (
                                "fallback.qmd",
                                "Spectral Study",
                                "Title-term candidate.",
                                (),
                                "Title result.",
                            ),
                        ),
                    ),
                ),
            )

            result = resolve_knowledge("spectral", repo_root)

        self.assertEqual(
            result["bundle"]["contentPages"],
            ["theory/alias/target.qmd"],
        )

    def test_alias_terms_outrank_description_and_body_terms(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(
                repo_root,
                (
                    (
                        "aliases",
                        "Alias Matches",
                        (
                            (
                                "target.qmd",
                                "Unrelated Alias Page",
                                "No fallback terms.",
                                ("Spectral Tensor Archive",),
                                "No fallback terms.",
                            ),
                        ),
                    ),
                    (
                        "fallback",
                        "Fallback Matches",
                        (
                            (
                                "candidate.qmd",
                                "Unrelated Fallback Page",
                                "A spectral tensor description.",
                                (),
                                "A spectral tensor body.",
                            ),
                        ),
                    ),
                ),
            )

            result = resolve_knowledge("spectral tensor unknown", repo_root)

        self.assertEqual(result["status"], "match")
        self.assertEqual(result["bundle"]["topic"], "theory/aliases/index.qmd")
        self.assertEqual(
            result["bundle"]["contentPages"],
            ["theory/aliases/target.qmd"],
        )

    def test_description_terms_outrank_body_terms(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(
                repo_root,
                (
                    (
                        "descriptions",
                        "Description Matches",
                        (
                            (
                                "target.qmd",
                                "Unrelated Description Page",
                                "A phase boundary description.",
                                (),
                                "No fallback terms.",
                            ),
                        ),
                    ),
                    (
                        "bodies",
                        "Body Matches",
                        (
                            (
                                "fallback.qmd",
                                "Unrelated Body Page",
                                "No fallback terms.",
                                (),
                                "The phase boundary appears in this body.",
                            ),
                        ),
                    ),
                ),
            )

            result = resolve_knowledge("phase boundary unknown", repo_root)

        self.assertEqual(result["status"], "match")
        self.assertEqual(
            result["bundle"]["contentPages"],
            ["theory/descriptions/target.qmd"],
        )

    def test_more_matched_terms_win_within_a_tier(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(
                repo_root,
                (
                    (
                        "aaa-fewer",
                        "Fewer Terms",
                        (
                            (
                                "candidate.qmd",
                                "Spectral Notes",
                                "One matching title term.",
                                (),
                                "No fallback terms.",
                            ),
                        ),
                    ),
                    (
                        "zzz-more",
                        "More Terms",
                        (
                            (
                                "candidate.qmd",
                                "Tensor Phase Study",
                                "Two matching title terms.",
                                (),
                                "No fallback terms.",
                            ),
                        ),
                    ),
                ),
            )

            result = resolve_knowledge("spectral tensor phase", repo_root)

        self.assertEqual(result["status"], "match")
        self.assertEqual(
            result["bundle"]["contentPages"],
            ["theory/zzz-more/candidate.qmd"],
        )

    def test_equally_best_content_in_one_topic_is_bundled_in_curated_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(
                repo_root,
                (
                    (
                        "paired",
                        "Paired Topic",
                        (
                            (
                                "z-first.qmd",
                                "Paired Result",
                                "First by the Reading map.",
                                (),
                                "First result.",
                            ),
                            (
                                "a-second.qmd",
                                "Paired Result",
                                "Second by the Reading map.",
                                (),
                                "Second result.",
                            ),
                        ),
                    ),
                ),
            )

            result = resolve_knowledge("paired result", repo_root)

        self.assertEqual(result["status"], "match")
        self.assertEqual(
            result["bundle"]["contentPages"],
            [
                "theory/paired/z-first.qmd",
                "theory/paired/a-second.qmd",
            ],
        )
        self.assertEqual(
            result["bundle"]["orderedFiles"],
            [
                "theory/index.qmd",
                "theory/paired/index.qmd",
                "theory/paired/z-first.qmd",
                "theory/paired/a-second.qmd",
            ],
        )

    def test_equally_best_candidates_in_different_topics_are_ambiguous(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(
                repo_root,
                (
                    (
                        "zzz-first",
                        "First Topic",
                        (
                            (
                                "candidate.qmd",
                                "Cross Topic Result",
                                "First by the root Reading map.",
                                (),
                                "First result.",
                            ),
                        ),
                    ),
                    (
                        "aaa-second",
                        "Second Topic",
                        (
                            (
                                "candidate.qmd",
                                "Cross Topic Result",
                                "Second by the root Reading map.",
                                (),
                                "Second result.",
                            ),
                        ),
                    ),
                ),
            )

            result = resolve_knowledge("cross topic result", repo_root)

        self.assertEqual(
            result,
            {
                "schemaVersion": 1,
                "query": "cross topic result",
                "status": "ambiguous",
                "bundle": None,
                "alternatives": [
                    {
                        "page": "theory/zzz-first/candidate.qmd",
                        "topic": "theory/zzz-first/index.qmd",
                        "title": "Cross Topic Result",
                        "matchKind": "exact-title",
                        "tier": 0,
                        "matchedTerms": 3,
                    },
                    {
                        "page": "theory/aaa-second/candidate.qmd",
                        "topic": "theory/aaa-second/index.qmd",
                        "title": "Cross Topic Result",
                        "matchKind": "exact-title",
                        "tier": 0,
                        "matchedTerms": 3,
                    },
                ],
            },
        )

    def test_no_match_never_falls_back_to_untrusted_or_external_trees(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(repo_root, ())
            for untrusted_root in ("drafts", "conference", "literature"):
                directory = repo_root / untrusted_root
                directory.mkdir()
                (directory / "secret.qmd").write_text(
                    _frontmatter(
                        title="Secret Candidate",
                        description="Only outside trusted theory.",
                    )
                    + "# Secret Candidate\n\n"
                    + "unique-untrusted-needle\n",
                    encoding="utf-8",
                )

            result = resolve_knowledge("unique untrusted needle", repo_root)

        self.assertEqual(
            result,
            {
                "schemaVersion": 1,
                "query": "unique untrusted needle",
                "status": "no-match",
                "bundle": None,
                "alternatives": [],
            },
        )

    def test_invalid_trusted_graph_is_rejected_before_resolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            _write_fixture(repo_root, ())
            root_index = repo_root / "theory" / "index.qmd"
            root_index.write_text(
                root_index.read_text(encoding="utf-8").replace(
                    "## Reading map",
                    "## Uncurated pages",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                KnowledgeValidationError,
                r"\[INDEX_READING_MAP_REQUIRED\]",
            ):
                resolve_knowledge("research knowledge", repo_root)

    def test_nested_content_bundle_prepends_every_ancestor_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            theory = repo_root / "theory"
            ising = theory / "physics" / "ising"
            ising.mkdir(parents=True)
            (theory / "index.qmd").write_text(
                _frontmatter(
                    title="Research Knowledge",
                    description="Fixture root.",
                )
                + "# Research Knowledge\n\n"
                + "## Reading map\n\n"
                + "- [Physics](physics/index.qmd)\n",
                encoding="utf-8",
            )
            (theory / "physics" / "index.qmd").write_text(
                _frontmatter(title="Physics", description="Parent topic.")
                + "# Physics\n\n"
                + "## Reading map\n\n"
                + "- [Overview](overview.qmd)\n"
                + "- [Ising](ising/index.qmd)\n",
                encoding="utf-8",
            )
            (theory / "physics" / "overview.qmd").write_text(
                _frontmatter(title="Overview", description="Parent content.")
                + "# Overview\n",
                encoding="utf-8",
            )
            (ising / "index.qmd").write_text(
                _frontmatter(title="Ising", description="Nested topic.")
                + "# Ising\n\n"
                + "## Reading map\n\n"
                + "- [Proof](proof.qmd)\n",
                encoding="utf-8",
            )
            (ising / "proof.qmd").write_text(
                _frontmatter(
                    title="Nested Proof",
                    description="Nested content.",
                )
                + "# Nested Proof\n",
                encoding="utf-8",
            )

            result = resolve_knowledge("nested proof", repo_root)

        self.assertEqual(
            result["bundle"],
            {
                "topic": "theory/physics/ising/index.qmd",
                "ancestorIndexes": [
                    "theory/index.qmd",
                    "theory/physics/index.qmd",
                    "theory/physics/ising/index.qmd",
                ],
                "contentPages": ["theory/physics/ising/proof.qmd"],
                "orderedFiles": [
                    "theory/index.qmd",
                    "theory/physics/index.qmd",
                    "theory/physics/ising/index.qmd",
                    "theory/physics/ising/proof.qmd",
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
