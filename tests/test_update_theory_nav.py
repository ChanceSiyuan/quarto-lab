import unittest

import yaml

from scripts import update_theory_nav as nav


def find_section(contents, title):
    for item in contents:
        if isinstance(item, dict) and item.get("section") == title:
            return item
    return None


class SidebarGenerationTest(unittest.TestCase):
    def test_only_outer_topic_directories_get_local_sidebar_files(self):
        section = nav.SECTIONS[0]

        self.assertTrue(
            nav.should_write_sidebar_file(nav.ROOT / "theory" / "supermacy", section)
        )
        self.assertFalse(
            nav.should_write_sidebar_file(
                nav.ROOT / "theory" / "supermacy" / "IQPs", section
            )
        )
        self.assertFalse(
            nav.should_write_sidebar_file(
                nav.ROOT
                / "theory"
                / "supermacy"
                / "IQPs"
                / "simulations",
                section,
            )
        )

    def test_nested_topic_directories_are_nested_sidebar_sections(self):
        topic_dir = nav.ROOT / "theory" / "supermacy"
        block = nav.build_sidebar_block(
            topic_dir,
            nav.SECTIONS[0],
            nav.sidebar_id(topic_dir),
            nav.topic_title(topic_dir),
        )
        data = yaml.safe_load(block)

        iqp_section = find_section(data["contents"], "IQP Circuits")
        self.assertIsNotNone(iqp_section)

        simulations_section = find_section(
            iqp_section["contents"], "IQP Simulation Algorithms"
        )
        self.assertIsNotNone(simulations_section)
        self.assertIn(
            "theory/supermacy/IQPs/simulations/noisy_iqp.qmd",
            simulations_section["contents"],
        )
        self.assertNotIn(
            "theory/supermacy/IQPs/simulations/noisy_iqp.qmd",
            [item for item in iqp_section["contents"] if isinstance(item, str)],
        )


if __name__ == "__main__":
    unittest.main()
