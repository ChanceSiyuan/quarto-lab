from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

from lib.knowledge.graph import load_knowledge
from lib.knowledge.quarto import materialize_quarto_project
from lib.knowledge.validate import (
    KnowledgeValidationError,
    validate_knowledge,
)


ROOT = Path(__file__).resolve().parents[1]
VALID_FIXTURE = ROOT / "tests" / "fixtures" / "knowledge" / "valid"


class QuartoProjectionTest(unittest.TestCase):
    def test_projection_refuses_an_unvalidated_knowledge_graph(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            proof = repo_root / "theory" / "ising" / "proof.qmd"
            proof.write_text(
                proof.read_text(encoding="utf-8").replace(
                    "title: A Verified Statement",
                    "title: A Verified Statement\nexecute: true",
                ),
                encoding="utf-8",
            )
            graph = load_knowledge(repo_root)
            workspace = repo_root / "work" / "fixture"

            with self.assertRaises(KnowledgeValidationError) as raised:
                materialize_quarto_project(
                    graph=graph,
                    workspace=workspace,
                )

            self.assertIn(
                "FRONTMATTER_KEY_FORBIDDEN",
                {diagnostic.code for diagnostic in raised.exception.diagnostics},
            )
            self.assertFalse((workspace / "project").exists())

    def test_projection_refuses_a_tampered_graph_for_a_valid_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)
            tampered = replace(
                report.graph,
                pages=report.graph.pages[:-1],
            )

            with self.assertRaisesRegex(
                ValueError,
                "does not match freshly validated repository state",
            ):
                materialize_quarto_project(
                    graph=tampered,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_active_html_in_the_root_homepage(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            (repo_root / "index.qmd").write_text(
                """\
---
title: Fixture Home
---

# Fixture Home

<script>alert("unreviewed root code")</script>
""",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)
            workspace = repo_root / "work" / "fixture"

            with self.assertRaisesRegex(
                ValueError,
                "homepage contains active HTML",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=workspace,
                )
            self.assertFalse((workspace / "project").exists())

    def test_projection_rejects_quarto_overrides_in_the_root_homepage(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            (repo_root / "index.qmd").write_text(
                """\
---
title: Fixture Home
execute:
  enabled: true
---

# Fixture Home
""",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "homepage has unsupported frontmatter key: execute",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_untrusted_local_homepage_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            (repo_root / "index.qmd").write_text(
                """\
---
title: Fixture Home
---

# Fixture Home

[Untrusted draft](drafts/secret.qmd)
""",
                encoding="utf-8",
            )
            draft = repo_root / "drafts" / "secret.qmd"
            draft.parent.mkdir()
            draft.write_text("DO NOT PUBLISH", encoding="utf-8")
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "homepage local target is not trusted",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_quarto_shortcodes_in_the_root_homepage(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            (repo_root / "index.qmd").write_text(
                """\
---
title: Fixture Home
---

# Fixture Home

{{< include /tmp/untrusted-draft.qmd >}}
""",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "homepage Quarto shortcodes are forbidden",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_yaml_decoded_homepage_shortcodes(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            (repo_root / "index.qmd").write_text(
                """\
---
title: "\\u007b\\u007b< env REVIEW_SHORTCODE_SECRET >}}"
---

# Fixture Home
""",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "homepage Quarto shortcodes are forbidden",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_decoded_html_in_homepage_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            (repo_root / "index.qmd").write_text(
                """\
---
title: "\\u003cscript id=\\"root-active\\">unsafe\\u003c/script>"
---

# Fixture Home
""",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "homepage metadata may not contain HTML",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_contains_only_validated_pages_and_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            proof = repo_root / "theory" / "ising" / "proof.qmd"
            proof.write_text(
                """\
---
title: A Verified Statement
description: A fixture statement about an Ising model.
aliases:
  - fixture proof
bibliography:
  - refs.bib
  - ../../references.bib
---

# A Verified Statement

![Validated diagram](diagram.svg)

The transverse-field Ising model is the body-search fixture [@fixture2026].
""",
                encoding="utf-8",
            )
            (proof.parent / "diagram.svg").write_bytes(b"<svg>trusted</svg>")
            (proof.parent / "unreferenced.png").write_bytes(b"do-not-copy")
            (proof.parent / "refs.bib").write_bytes(
                b"@article{fixture2026, title={Fixture}, year={2026}}\n"
            )
            (repo_root / "references.bib").write_bytes(b"% shared\n")
            (repo_root / "aps.csl").write_bytes(b"<style/>")
            (repo_root / "styles.css").write_bytes(b"body { color: black; }\n")
            include = repo_root / "_includes" / "comment-github-link.html"
            include.parent.mkdir()
            include.write_bytes(b"<p>fixed include</p>\n")
            (repo_root / "_quarto.yml").write_text(
                """\
project:
  type: website
  output-dir: _site
website:
  title: Fixture Knowledge
format:
  html:
    css: styles.css
    include-after-body: _includes/comment-github-link.html
bibliography: references.bib
csl: aps.csl
execute:
  enabled: false
""",
                encoding="utf-8",
            )
            draft = repo_root / "drafts" / "secret.qmd"
            draft.parent.mkdir()
            draft.write_text("DO NOT PUBLISH", encoding="utf-8")
            conference = repo_root / "conference" / "secret.qmd"
            conference.parent.mkdir()
            conference.write_text("DO NOT PUBLISH", encoding="utf-8")
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)
            workspace = repo_root / "work" / "fixture"

            project = materialize_quarto_project(
                graph=report.graph,
                workspace=workspace,
            )

            project_dir = project.project_dir
            for source in [
                repo_root / "theory" / "index.qmd",
                repo_root / "theory" / "ising" / "index.qmd",
                proof,
                proof.parent / "diagram.svg",
                proof.parent / "refs.bib",
                repo_root / "references.bib",
                repo_root / "aps.csl",
                repo_root / "styles.css",
                include,
            ]:
                projected = project_dir / source.relative_to(repo_root)
                self.assertEqual(projected.read_bytes(), source.read_bytes())

            self.assertFalse(
                (project_dir / "theory" / "ising" / "unreferenced.png").exists()
            )
            self.assertFalse((project_dir / "drafts").exists())
            self.assertFalse((project_dir / "conference").exists())
            config = yaml.safe_load(
                (project_dir / "_quarto.yml").read_text(encoding="utf-8")
            )
            self.assertEqual(config["project"]["output-dir"], "_site")
            self.assertEqual(
                config["project"]["render"],
                ["index.qmd", "theory/**/*.qmd"],
            )
            self.assertEqual(config["execute"], {"enabled": False})
            self.assertNotIn("pre-render", config["project"])
            self.assertEqual(
                config["website"]["sidebar"]["contents"],
                [
                    {
                        "section": "Research Knowledge",
                        "href": "theory/index.qmd",
                        "contents": [
                            {
                                "section": "Ising Models",
                                "href": "theory/ising/index.qmd",
                                "contents": [
                                    {
                                        "text": "A Verified Statement",
                                        "href": "theory/ising/proof.qmd",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            )

    def test_projection_rejects_an_unsafe_base_execution_setting(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            config = repo_root / "_quarto.yml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "enabled: false",
                    "enabled: true",
                ),
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "base configuration must disable execution",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_unknown_base_configuration_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            config = repo_root / "_quarto.yml"
            config.write_text(
                config.read_text(encoding="utf-8")
                + "metadata-files: drafts/untrusted.yml\n",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "unsupported top-level key: metadata-files",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_quarto_shortcodes_in_base_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            config = repo_root / "_quarto.yml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "title: Fixture Knowledge",
                    'title: "{{< env HOME >}}"',
                ),
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "Quarto shortcodes are forbidden in base configuration",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_decoded_html_in_base_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            config = repo_root / "_quarto.yml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "title: Fixture Knowledge",
                    (
                        'title: "\\u003cscript id=\\"config-active\\">'
                        "unsafe\\u003c/script>\""
                    ),
                ),
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "HTML is forbidden in base configuration",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_nested_pandoc_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            (repo_root / "_quarto.yml").write_text(
                """\
project:
  type: website
website:
  title: Fixture Knowledge
format:
  html:
    toc: true
    pandoc-args:
      - --lua-filter=evil.lua
execute:
  enabled: false
""",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                (
                    "unsupported Quarto base configuration key: "
                    r"format\.html\.pandoc-args"
                ),
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_arbitrary_quarto_include_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            (repo_root / "unsafe.html").write_text(
                "<script>alert('include')</script>",
                encoding="utf-8",
            )
            config = repo_root / "_quarto.yml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "    toc: true",
                    "    toc: true\n    include-after-body: unsafe.html",
                ),
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)
            workspace = repo_root / "work" / "fixture"

            with self.assertRaisesRegex(
                ValueError,
                "include-after-body may only be "
                "_includes/comment-github-link.html",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=workspace,
                )
            self.assertFalse((workspace / "project").exists())

    def test_projection_audits_the_fixed_quarto_include(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            include = repo_root / "_includes" / "comment-github-link.html"
            include.parent.mkdir()
            include.write_text(
                "<script>alert('fixed path is not sufficient')</script>",
                encoding="utf-8",
            )
            config = repo_root / "_quarto.yml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "    toc: true",
                    (
                        "    toc: true\n"
                        "    include-after-body: "
                        "_includes/comment-github-link.html"
                    ),
                ),
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "unsafe fixed Quarto HTML include",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_css_escaped_fixed_stylesheet_urls(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            (repo_root / "styles.css").write_text(
                "body { background-image: \\75rl("
                "https://evil.invalid/track.png); }\n",
                encoding="utf-8",
            )
            config = repo_root / "_quarto.yml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "    toc: true",
                    "    toc: true\n    css: styles.css",
                ),
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "unsafe fixed Quarto stylesheet",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_resource_loading_in_the_fixed_include(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            include = repo_root / "_includes" / "comment-github-link.html"
            include.parent.mkdir()
            include.write_text(
                '<video src="../../../drafts/untrusted.mp4"></video>',
                encoding="utf-8",
            )
            config = repo_root / "_quarto.yml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "    toc: true",
                    (
                        "    toc: true\n"
                        "    include-after-body: "
                        "_includes/comment-github-link.html"
                    ),
                ),
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            with self.assertRaisesRegex(
                ValueError,
                "unsafe fixed Quarto HTML include",
            ):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_omits_authoring_and_network_preview_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            config = repo_root / "_quarto.yml"
            config.write_text(
                config.read_text(encoding="utf-8")
                + "editor: visual\n"
                + "preview:\n"
                + "  host: 0.0.0.0\n"
                + "  port: 4200\n",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertTrue(report.ok, report.diagnostics)

            project = materialize_quarto_project(
                graph=report.graph,
                workspace=repo_root / "work" / "fixture",
            )

            generated = yaml.safe_load(
                (project.project_dir / "_quarto.yml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("editor", generated)
            self.assertNotIn("preview", generated)

    def test_complete_validation_rejects_an_executable_link_dependency(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            proof = repo_root / "theory" / "ising" / "proof.qmd"
            proof.write_text(
                proof.read_text(encoding="utf-8")
                + "\n[Executable helper](helper.py)\n",
                encoding="utf-8",
            )
            (proof.parent / "helper.py").write_text(
                "print('must not publish')\n",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertEqual(
                [item.code for item in report.diagnostics],
                ["ASSET_TYPE_FORBIDDEN"],
            )

            with self.assertRaises(KnowledgeValidationError):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_active_svg_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            proof = repo_root / "theory" / "ising" / "proof.qmd"
            proof.write_text(
                proof.read_text(encoding="utf-8")
                + "\n![Unsafe diagram](diagram.svg)\n",
                encoding="utf-8",
            )
            (proof.parent / "diagram.svg").write_text(
                "<svg xmlns='http://www.w3.org/2000/svg'>"
                "<script>alert(1)</script></svg>",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertEqual(
                [item.code for item in report.diagnostics],
                ["ASSET_UNSAFE"],
            )

            with self.assertRaises(KnowledgeValidationError):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )

    def test_projection_rejects_css_escaped_svg_resource_urls(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            shutil.copytree(VALID_FIXTURE, repo_root)
            proof = repo_root / "theory" / "ising" / "proof.qmd"
            proof.write_text(
                proof.read_text(encoding="utf-8")
                + "\n![Unsafe diagram](diagram.svg)\n",
                encoding="utf-8",
            )
            (proof.parent / "diagram.svg").write_text(
                "<svg xmlns='http://www.w3.org/2000/svg'>"
                "<rect style='fill: \\75rl(https://evil.invalid/x.png)'/>"
                "</svg>",
                encoding="utf-8",
            )
            report = validate_knowledge(repo_root)
            self.assertEqual(
                [item.code for item in report.diagnostics],
                ["ASSET_UNSAFE"],
            )

            with self.assertRaises(KnowledgeValidationError):
                materialize_quarto_project(
                    graph=report.graph,
                    workspace=repo_root / "work" / "fixture",
                )


if __name__ == "__main__":
    unittest.main()
