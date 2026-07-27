import unittest

import yaml

from scripts import update_theory_nav as nav


def find_section(contents, title):
    for item in contents:
        if isinstance(item, dict) and item.get("section") == title:
            return item
    return None


class SidebarGenerationTest(unittest.TestCase):
    def test_auto_block_replacement_preserves_latex_backslashes(self):
        begin = "<!-- BEGIN -->"
        end = "<!-- END -->"
        source = f"Before\n{begin}\nold\n{end}\nAfter\n"
        block = "\n".join(
            [
                begin,
                r"| [Application to $\text{tr}(O \rho^k)$](note.qmd) |",
                end,
            ]
        )

        updated = nav.replace_or_append_block(source, begin, end, block)

        self.assertIn(r"$\text{tr}(O \rho^k)$", updated)
        self.assertNotIn("\t", updated)
        self.assertNotIn("\r", updated)

    def test_only_outer_topic_directories_get_local_sidebar_files(self):
        section = nav.SECTIONS[0]

        self.assertTrue(
            nav.should_write_sidebar_file(
                nav.ROOT / "theory" / "quantum_complexity", section
            )
        )
        self.assertFalse(
            nav.should_write_sidebar_file(
                nav.ROOT / "theory" / "quantum_complexity" / "supermacy",
                section,
            )
        )
        self.assertFalse(
            nav.should_write_sidebar_file(
                nav.ROOT
                / "theory"
                / "quantum_complexity"
                / "supermacy"
                / "IQPs"
                / "simulations",
                section,
            )
        )

    def test_nested_topic_directories_are_nested_sidebar_sections(self):
        topic_dir = nav.ROOT / "theory" / "quantum_complexity"
        block = nav.build_sidebar_block(
            topic_dir,
            nav.SECTIONS[0],
            nav.sidebar_id(topic_dir),
            nav.topic_title(topic_dir),
        )
        data = yaml.safe_load(block)

        supremacy_section = find_section(
            data["contents"], "IQP Circuit Supremacy"
        )
        self.assertIsNotNone(supremacy_section)

        iqp_section = find_section(supremacy_section["contents"], "IQP Circuits")
        self.assertIsNotNone(iqp_section)

        simulations_section = find_section(
            iqp_section["contents"], "IQP Simulation Algorithms"
        )
        self.assertIsNotNone(simulations_section)
        self.assertIn(
            "theory/quantum_complexity/supermacy/IQPs/simulations/noisy_iqp.qmd",
            simulations_section["contents"],
        )
        self.assertNotIn(
            "theory/quantum_complexity/supermacy/IQPs/simulations/noisy_iqp.qmd",
            [item for item in iqp_section["contents"] if isinstance(item, str)],
        )

    def test_condensed_matter_uses_one_parent_sidebar(self):
        section = nav.SECTIONS[0]
        topic_dir = nav.ROOT / "theory" / "Condensed_matter"

        self.assertTrue(nav.should_write_sidebar_file(topic_dir, section))
        for child in ("Fermi-Hubbard", "TFIM", "topo_matter"):
            self.assertFalse(
                nav.should_write_sidebar_file(topic_dir / child, section)
            )

        block = nav.build_sidebar_block(
            topic_dir,
            section,
            nav.sidebar_id(topic_dir),
            nav.topic_title(topic_dir),
        )
        data = yaml.safe_load(block)
        titles = {
            item["section"]
            for item in data["contents"]
            if isinstance(item, dict) and "section" in item
        }
        self.assertEqual(
            titles,
            {"Fermi-Hubbard Model", "Spin Liquids", "Topological Matter"},
        )


if __name__ == "__main__":
    unittest.main()
