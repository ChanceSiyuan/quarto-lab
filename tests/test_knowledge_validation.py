from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from lib.knowledge import validate_knowledge


def write_page(path: Path, *, frontmatter: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n{frontmatter}---\n\n{body}",
        encoding="utf-8",
    )


def write_valid_nested_tree(repo_root: Path) -> None:
    write_page(
        repo_root / "theory" / "index.qmd",
        frontmatter="title: Knowledge\n",
        body="## Reading map\n\n- [Topic](topic/index.qmd)\n",
    )
    write_page(
        repo_root / "theory" / "topic" / "index.qmd",
        frontmatter="title: Topic\n",
        body=(
            "## Reading map\n\n"
            "- [Direct](direct.qmd)\n"
            "- [Child](child/index.qmd)\n"
        ),
    )
    write_page(
        repo_root / "theory" / "topic" / "direct.qmd",
        frontmatter="title: Direct\n",
        body="A direct content page.\n",
    )
    write_page(
        repo_root / "theory" / "topic" / "child" / "index.qmd",
        frontmatter="title: Child\n",
        body="## Reading map\n\n- [Deep](deep.qmd)\n",
    )
    write_page(
        repo_root / "theory" / "topic" / "child" / "deep.qmd",
        frontmatter="title: Deep\n",
        body="A nested content page.\n",
    )


class KnowledgeValidationTest(unittest.TestCase):
    def test_forbidden_frontmatter_is_a_structured_diagnostic(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_page(
                repo_root / "theory" / "index.qmd",
                frontmatter="title: Knowledge\nstatus: draft\n",
                body="## Reading map\n\nNo children yet.\n",
            )

            report = validate_knowledge(repo_root)

        self.assertFalse(report.ok)
        self.assertEqual(len(report.diagnostics), 1)
        diagnostic = report.diagnostics[0]
        self.assertEqual(diagnostic.file, "theory/index.qmd")
        self.assertEqual(diagnostic.line, 3)
        self.assertEqual(diagnostic.column, 1)
        self.assertEqual(diagnostic.code, "FRONTMATTER_KEY_FORBIDDEN")
        self.assertEqual(
            str(diagnostic),
            "theory/index.qmd:3:1 [FRONTMATTER_KEY_FORBIDDEN] "
            "Frontmatter key is not allowed in trusted knowledge: status",
        )

    def test_duplicate_yaml_key_is_rejected_at_the_second_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_page(
                repo_root / "theory" / "index.qmd",
                frontmatter="title: First\ntitle: Second\n",
                body="## Reading map\n\nNo children yet.\n",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [("FRONTMATTER_DUPLICATE_KEY", 3, 1)],
        )

    def test_frontmatter_and_nonempty_title_are_required_but_description_is_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            root_index = repo_root / "theory" / "index.qmd"
            root_index.parent.mkdir(parents=True)
            root_index.write_text(
                "## Reading map\n\nNo children yet.\n",
                encoding="utf-8",
            )

            missing_report = validate_knowledge(repo_root)

            write_page(
                root_index,
                frontmatter="title: '  '\n",
                body="## Reading map\n\nNo children yet.\n",
            )
            blank_title_report = validate_knowledge(repo_root)

            write_page(
                root_index,
                frontmatter="title: Knowledge\n",
                body="## Reading map\n\nNo children yet.\n",
            )
            title_only_report = validate_knowledge(repo_root)

        self.assertEqual(
            [item.code for item in missing_report.diagnostics],
            ["FRONTMATTER_MISSING"],
        )
        self.assertEqual(
            [item.code for item in blank_title_report.diagnostics],
            ["TITLE_REQUIRED"],
        )
        self.assertTrue(title_only_report.ok)

    def test_unclosed_or_invalid_yaml_frontmatter_is_rejected_without_cascades(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            root_index = repo_root / "theory" / "index.qmd"
            root_index.parent.mkdir(parents=True)
            root_index.write_text(
                "---\ntitle: Knowledge\n\n## Reading map\n",
                encoding="utf-8",
            )

            unclosed_report = validate_knowledge(repo_root)

            root_index.write_text(
                "---\ntitle: [broken\n---\n\n## Reading map\n",
                encoding="utf-8",
            )
            invalid_report = validate_knowledge(repo_root)

        self.assertEqual(
            [item.code for item in unclosed_report.diagnostics],
            ["FRONTMATTER_INVALID"],
        )
        self.assertEqual(
            [item.code for item in invalid_report.diagnostics],
            ["FRONTMATTER_INVALID"],
        )

    def test_frontmatter_allowlist_applies_to_quoted_top_level_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_page(
                repo_root / "theory" / "index.qmd",
                frontmatter=(
                    "title: Knowledge\n"
                    "description: Optional\n"
                    "aliases: [KB]\n"
                    "date: 2026-07-28\n"
                    "lang: en\n"
                    "categories: [theory]\n"
                    "subtitle: Notes\n"
                    "abstract: Summary\n"
                    "tags: [fixture]\n"
                    "bibliography: refs.bib\n"
                    '"execute": false\n'
                ),
                body="## Reading map\n\nNo children yet.\n",
            )
            (repo_root / "theory" / "refs.bib").write_text(
                "@misc{fixture, title={Fixture}}\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("FRONTMATTER_KEY_FORBIDDEN", 12)],
        )

    def test_every_directory_with_qmd_descendants_requires_a_direct_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_page(
                repo_root / "theory" / "index.qmd",
                frontmatter="title: Knowledge\n",
                body="## Reading map\n\nNo children yet.\n",
            )
            write_page(
                repo_root / "theory" / "topic" / "nested" / "page.qmd",
                frontmatter="title: Nested page\n",
                body="Body.\n",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.file, item.code) for item in report.diagnostics],
            [
                ("theory/topic", "TOPIC_INDEX_MISSING"),
                ("theory/topic/nested", "TOPIC_INDEX_MISSING"),
            ],
        )

    def test_reading_map_rejects_an_existing_non_direct_descendant(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            index = repo_root / "theory" / "topic" / "index.qmd"
            index.write_text(
                index.read_text(encoding="utf-8")
                + "- [Too deep](child/deep.qmd)\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("NON_DIRECT_CHILD", 9)],
        )

    def test_reading_map_rejects_duplicate_direct_child_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            index = repo_root / "theory" / "topic" / "index.qmd"
            index.write_text(
                index.read_text(encoding="utf-8")
                + "- [Direct again](./direct.qmd#statement)\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("DUPLICATE_CHILD", 9)],
        )

    def test_related_topics_are_optional_but_may_only_link_to_indexes(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            child_index = repo_root / "theory" / "topic" / "child" / "index.qmd"
            child_index.write_text(
                child_index.read_text(encoding="utf-8")
                + "\n## Related topics\n\n"
                "- [Parent topic](../index.qmd)\n"
                "- [Not a topic](../direct.qmd)\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("RELATED_TARGET_NOT_INDEX", 12)],
        )

    def test_related_topics_heading_cannot_be_duplicated(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            root_index = repo_root / "theory" / "index.qmd"
            root_index.write_text(
                root_index.read_text(encoding="utf-8")
                + "\n## Related topics\n\nNone.\n"
                + "\n## Related topics\n\nStill none.\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [item.code for item in report.diagnostics],
            ["RELATED_TOPICS_DUPLICATE"],
        )

    def test_ordinary_local_links_and_images_must_exist_but_code_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n[Missing note](missing.qmd)\n"
                + "\n![Missing image](diagram.svg)\n"
                + "\n`[Ignored](also-missing.qmd)`\n"
                + "\n```markdown\n[Ignored](fenced-missing.qmd)\n```\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("LINK_MISSING", 7), ("IMAGE_MISSING", 9)],
        )

    def test_local_links_reject_absolute_paths_and_lexical_escapes(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            draft = repo_root / "drafts" / "secret.qmd"
            draft.parent.mkdir()
            draft.write_text("untrusted", encoding="utf-8")
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n[Absolute](/theory/index.qmd)\n"
                + "\n[Escape](../../../drafts/secret.qmd)\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("LINK_ABSOLUTE", 7), ("LINK_OUTSIDE_KNOWLEDGE", 9)],
        )

    def test_local_link_rejects_a_symlink_without_reading_its_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            secret = repo_root / "drafts" / "secret.txt"
            secret.parent.mkdir()
            secret.write_text("untrusted", encoding="utf-8")
            linked = repo_root / "theory" / "topic" / "evidence.txt"
            linked.symlink_to(secret)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n[Symlinked evidence](evidence.txt)\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.file, item.code, item.line) for item in report.diagnostics],
            [("theory/topic/evidence.txt", "SYMLINK_FORBIDDEN", 1)],
        )

    def test_symlinked_qmd_is_rejected_without_becoming_a_knowledge_page(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            secret = repo_root / "drafts" / "secret.qmd"
            secret.parent.mkdir()
            secret.write_text("no trusted frontmatter", encoding="utf-8")
            linked = repo_root / "theory" / "topic" / "linked.qmd"
            linked.symlink_to(secret)

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.file, item.code) for item in report.diagnostics],
            [("theory/topic/linked.qmd", "SYMLINK_FORBIDDEN")],
        )
        self.assertNotIn(linked, report.graph.pages)

    def test_active_html_is_rejected_while_code_examples_are_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n<script>alert('x')</script>\n"
                + '\n<span onclick="run()">unsafe</span>\n'
                + '\n<iframe src="frame.html"></iframe>\n'
                + "\n<object></object>\n"
                + "\n<embed />\n"
                + "\n`<script>ignored()</script>`\n"
                + "\n```html\n<iframe></iframe>\n```\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [item.code for item in report.diagnostics],
            [
                "SCRIPT_FORBIDDEN",
                "INLINE_HANDLER_FORBIDDEN",
                "IFRAME_FORBIDDEN",
                "OBJECT_FORBIDDEN",
                "EMBED_FORBIDDEN",
            ],
        )

    def test_reading_map_uses_all_and_only_links_in_direct_list_items(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            index = repo_root / "theory" / "topic" / "index.qmd"
            write_page(
                index,
                frontmatter="title: Topic\n",
                body=(
                    "## Reading map\n\n"
                    "A prose [link](child/deep.qmd) is not a map entry.\n\n"
                    "- [Direct](direct.qmd) and "
                    "[too deep](child/deep.qmd)\n"
                    "- [Child](child/index.qmd)\n"
                    "  - [Nested](child/deep.qmd)\n\n"
                    "### Notes\n\n"
                    "- [Below a nested heading](child/deep.qmd)\n"
                ),
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("NON_DIRECT_CHILD", 9)],
        )

    def test_reading_map_rejects_external_or_fragment_only_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            index = repo_root / "theory" / "topic" / "index.qmd"
            index.write_text(
                index.read_text(encoding="utf-8")
                + "- [External](https://example.com)\n"
                + "- [This page](#reading-map)\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [item.code for item in report.diagnostics],
            ["NON_DIRECT_CHILD", "NON_DIRECT_CHILD"],
        )

    def test_related_topic_entries_must_be_existing_local_indexes(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            root_index = repo_root / "theory" / "index.qmd"
            root_index.write_text(
                root_index.read_text(encoding="utf-8")
                + "\n## Related topics\n\n"
                + "- [External](https://example.com)\n"
                + "- [Missing](missing/index.qmd)\n"
                + "- [Outside](../drafts/index.qmd)\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [item.code for item in report.diagnostics],
            [
                "RELATED_TARGET_NOT_INDEX",
                "LINK_MISSING",
                "LINK_OUTSIDE_KNOWLEDGE",
            ],
        )

    def test_backslash_traversal_is_rejected_as_an_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n[Escape](..\\\\..\\\\drafts\\\\secret.qmd)\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [item.code for item in report.diagnostics],
            ["LINK_OUTSIDE_KNOWLEDGE"],
        )

    def test_non_scalar_yaml_key_is_reported_as_invalid_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_page(
                repo_root / "theory" / "index.qmd",
                frontmatter="? [unsafe]\n: value\n",
                body="## Reading map\n\nNo children yet.\n",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [item.code for item in report.diagnostics],
            ["FRONTMATTER_INVALID"],
        )

    def test_latex_math_is_not_misclassified_as_markdown_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\nInline $[M+M_N](x,u)$ is mathematics.\n"
                + "\n$$\\left[\\frac{I}{d}\\right](C^\\dagger)$$\n"
                + "\nBut [this note](missing.qmd) is a link.\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.message.rsplit(': ', 1)[-1]) for item in report.diagnostics],
            [("LINK_MISSING", "missing.qmd")],
        )

    def test_passive_raw_html_images_participate_in_local_asset_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            (page.parent / "present.png").write_bytes(b"fixture")
            page.write_text(
                page.read_text(encoding="utf-8")
                + '\n<img src="present.png" style="width:60%" />\n'
                + '\n<img src="missing.png" alt="missing" />\n',
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("IMAGE_MISSING", 9)],
        )
        links = dict(report.graph.all_links)[page]
        self.assertIn(
            ("image", "present.png"),
            [(link.kind, link.target) for link in links],
        )

    def test_raw_html_anchors_participate_in_local_link_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + '\n<a class="reference" href="child/deep.qmd">Deep</a>\n'
                + '\n<a href="missing.qmd">Missing</a>\n'
                + '\n<a href="../../../drafts/secret.qmd">Escape</a>\n',
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [
                ("LINK_MISSING", 9, 1),
                ("LINK_OUTSIDE_KNOWLEDGE", 11, 1),
            ],
        )
        links = dict(report.graph.all_links)[page]
        self.assertEqual(
            [
                ("link", "child/deep.qmd"),
                ("link", "missing.qmd"),
                ("link", "../../../drafts/secret.qmd"),
            ],
            [
                (link.kind, link.target)
                for link in links
                if link.line in {7, 9, 11}
            ],
        )

    def test_active_raw_html_navigation_and_forms_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + '\n<a href="JaVaScRiPt:alert(1)">unsafe</a>\n'
                + '\n<img src="&#x6a;avascript:alert(2)" alt="unsafe" />\n'
                + '\n<meta http-equiv="refresh" content="0;url=/elsewhere">\n'
                + '\n<form action="submit"><input name="value"></form>\n',
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [
                ("JAVASCRIPT_URL_FORBIDDEN", 7, 1),
                ("JAVASCRIPT_URL_FORBIDDEN", 9, 1),
                ("META_REFRESH_FORBIDDEN", 11, 1),
                ("FORM_FORBIDDEN", 13, 1),
            ],
        )

    def test_static_raw_html_and_safe_external_links_remain_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            (page.parent / "figure.png").write_bytes(b"fixture")
            page.write_text(
                page.read_text(encoding="utf-8")
                + '\n<div class="layout"><span style="font-weight:bold">'
                + "Static layout</span></div>\n"
                + '\n<a href="https://example.com/paper">External source</a>\n'
                + '\n<img src="figure.png" alt="safe figure" />\n',
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertTrue(report.ok, "\n".join(report.diagnostics))

    def test_quarto_shortcodes_are_rejected_everywhere_in_the_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n{{< include /tmp/untrusted.qmd >}}\n"
                + "\nInline {{% embed ../../../drafts/note.qmd %}} text.\n"
                + "\n`{{< include harmless-example.qmd >}}`\n"
                + "\n```markdown\n"
                + "{{< include harmless-example.qmd >}}\n"
                + "```\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [
                ("QUARTO_SHORTCODE_FORBIDDEN", 7, 1),
                ("QUARTO_SHORTCODE_FORBIDDEN", 9, 8),
                ("QUARTO_SHORTCODE_FORBIDDEN", 11, 2),
                ("QUARTO_SHORTCODE_FORBIDDEN", 14, 1),
            ],
        )

    def test_quarto_shortcodes_in_frontmatter_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8").replace(
                    "title: Direct",
                    'title: "{{< env HOME >}}"',
                ),
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [("QUARTO_SHORTCODE_FORBIDDEN", 2, 9)],
        )

    def test_yaml_decoded_quarto_shortcodes_in_frontmatter_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8").replace(
                    "title: Direct",
                    (
                        'title: "\\u007b\\u007b< env '
                        'REVIEW_SHORTCODE_SECRET >}}"'
                    ),
                ),
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [("QUARTO_SHORTCODE_FORBIDDEN", 2, 8)],
        )

    def test_decoded_frontmatter_html_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8").replace(
                    "title: Direct",
                    (
                        "title: Direct\n"
                        'abstract: "\\u003cscript id=\\"metadata-active\\">'
                        "unsafe\\u003c/script>\""
                    ),
                ),
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [("FRONTMATTER_HTML_FORBIDDEN", 3, 11)],
        )

    def test_quarto_shortcodes_inside_raw_html_blocks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n<div class=\"layout\">\n"
                + "{{< include /tmp/untrusted.qmd >}}\n"
                + "</div>\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [("QUARTO_SHORTCODE_FORBIDDEN", 8, 1)],
        )

    def test_raw_html_resource_urls_use_the_same_link_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + '\n<video src="file:///etc/passwd"></video>\n'
                + '\n<audio src="../../../drafts/secret.mp3"></audio>\n'
                + '\n<video poster="missing.png"></video>\n'
                + '\n<source src="https://example.com/audio.mp3">\n',
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [
                (item.code, item.line, item.message.rsplit(": ", 1)[-1])
                for item in report.diagnostics
            ],
            [
                ("LINK_SCHEME_UNSUPPORTED", 7, "file:///etc/passwd"),
                (
                    "LINK_OUTSIDE_KNOWLEDGE",
                    9,
                    "../../../drafts/secret.mp3",
                ),
                ("ASSET_MISSING", 11, "missing.png"),
            ],
        )

    def test_raw_html_css_network_loads_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + '\n<style>@import url("https://evil.invalid/x.css");</style>\n'
                + '\n<div style="background-image: url(https://evil.invalid/x.png)">'
                + "unsafe</div>\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [
                ("STYLE_FORBIDDEN", 7, 1),
                ("STYLE_URL_FORBIDDEN", 9, 1),
            ],
        )

    def test_css_escaped_network_loads_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + '\n<div style="background-image: \\75rl('
                + "https://evil.invalid/x.png)\">unsafe</div>\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line, item.column) for item in report.diagnostics],
            [("STYLE_URL_FORBIDDEN", 7, 1)],
        )

    def test_only_supported_external_schemes_and_same_page_targets_are_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n[HTTP](http://example.com/source)\n"
                + "[HTTPS](https://example.com/source)\n"
                + "[Email](mailto:researcher@example.com)\n"
                + "[Fragment](#result)\n"
                + "[Query](?view=compact)\n"
                + "[FTP](ftp://example.com/source)\n"
                + "[File](file:///etc/passwd)\n"
                + "[Data](data:text/plain,untrusted)\n"
                + "[JavaScript](javascript:alert(1))\n"
                + "[VBScript](vbscript:msgbox(1))\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [
                (item.code, item.line, item.message.rsplit(": ", 1)[-1])
                for item in report.diagnostics
            ],
            [
                ("LINK_SCHEME_UNSUPPORTED", 12, "ftp://example.com/source"),
                ("LINK_SCHEME_UNSUPPORTED", 13, "file:///etc/passwd"),
                ("LINK_SCHEME_UNSUPPORTED", 14, "data:text/plain,untrusted"),
                ("LINK_SCHEME_UNSUPPORTED", 15, "javascript:alert(1)"),
                ("LINK_SCHEME_UNSUPPORTED", 16, "vbscript:msgbox(1)"),
            ],
        )

    def test_local_dependency_must_be_a_publishable_regular_asset(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            page = repo_root / "theory" / "topic" / "direct.qmd"
            (page.parent / "helper.py").write_text(
                "print('not publishable')\n",
                encoding="utf-8",
            )
            (page.parent / "folder").mkdir()
            page.write_text(
                page.read_text(encoding="utf-8")
                + "\n[Executable](helper.py)\n"
                + "\n[Directory](folder)\n",
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [item.code for item in report.diagnostics],
            ["ASSET_TYPE_FORBIDDEN", "ASSET_NOT_FILE"],
        )

    def test_bibliographies_must_exist_within_the_approved_authorities(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            direct = repo_root / "theory" / "topic" / "direct.qmd"
            direct.write_text(
                direct.read_text(encoding="utf-8").replace(
                    "title: Direct\n",
                    "title: Direct\nbibliography: ../../drafts/ref.bib\n",
                ),
                encoding="utf-8",
            )
            deep = repo_root / "theory" / "topic" / "child" / "deep.qmd"
            deep.write_text(
                deep.read_text(encoding="utf-8").replace(
                    "title: Deep\n",
                    "title: Deep\nbibliography: refs.bib\n",
                ),
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.file, item.code, item.line) for item in report.diagnostics],
            [
                (
                    "theory/topic/child/deep.qmd",
                    "BIBLIOGRAPHY_MISSING",
                    3,
                ),
                (
                    "theory/topic/direct.qmd",
                    "BIBLIOGRAPHY_OUTSIDE_KNOWLEDGE",
                    3,
                ),
            ],
        )

    def test_bibliography_uri_schemes_receive_a_bibliography_diagnostic(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            direct = repo_root / "theory" / "topic" / "direct.qmd"
            direct.write_text(
                direct.read_text(encoding="utf-8").replace(
                    "title: Direct\n",
                    "title: Direct\nbibliography: ftp://example.com/ref.bib\n",
                ),
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("BIBLIOGRAPHY_OUTSIDE_KNOWLEDGE", 3)],
        )

    def test_bibliography_paths_cannot_use_link_query_or_fragment_syntax(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            direct = repo_root / "theory" / "topic" / "direct.qmd"
            (direct.parent / "refs.bib").write_text(
                "@article{fixture, title={Fixture}}",
                encoding="utf-8",
            )
            direct.write_text(
                direct.read_text(encoding="utf-8").replace(
                    "title: Direct\n",
                    "title: Direct\nbibliography: refs.bib#entry\n",
                ),
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("BIBLIOGRAPHY_INVALID", 3)],
        )

    def test_bibliography_frontmatter_has_a_stable_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            direct = repo_root / "theory" / "topic" / "direct.qmd"
            direct.write_text(
                direct.read_text(encoding="utf-8").replace(
                    "title: Direct\n",
                    "title: Direct\nbibliography: {path: refs.bib}\n",
                ),
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("BIBLIOGRAPHY_INVALID", 3)],
        )

    def test_aliases_must_be_a_list_of_nonempty_strings(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            write_valid_nested_tree(repo_root)
            direct = repo_root / "theory" / "topic" / "direct.qmd"
            direct.write_text(
                direct.read_text(encoding="utf-8").replace(
                    "title: Direct\n",
                    "title: Direct\naliases: direct result\n",
                ),
                encoding="utf-8",
            )

            report = validate_knowledge(repo_root)

        self.assertEqual(
            [(item.code, item.line) for item in report.diagnostics],
            [("ALIASES_INVALID", 3)],
        )


if __name__ == "__main__":
    unittest.main()
