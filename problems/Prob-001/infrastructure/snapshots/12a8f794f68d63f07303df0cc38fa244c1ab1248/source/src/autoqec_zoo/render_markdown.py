from __future__ import annotations


def render_card_markdown(
    card: dict, evidence_records: list[dict], instance_records: list[dict]
) -> str:
    lines = [
        f"# {card['title']}",
        "",
        card["summary"],
        "",
        "## Family, Aliases, and Kind",
        "",
        f"- `family`: `{card['family']}`" if card.get("family") else "- `family`: None",
        f"- `aliases`: {', '.join(card['aliases'])}" if card["aliases"] else "- `aliases`: None",
        f"- `kind`: `{card['kind']}`",
    ]

    lines.extend(
        [
            "",
            "## Construction",
            "",
            f"- `type`: `{card['construction']['type']}`",
            f"- {card['construction']['description']}",
            "",
            "## Parameter Formulas",
            "",
        ]
    )
    lines.extend(f"- `{key}`: {value}" for key, value in card["parameters"].items())

    lines.extend(["", "## Assumptions", ""])
    lines.extend(f"- {item}" for item in card["assumptions"])

    lines.extend(["", "## Known Decoders", ""])
    lines.extend(f"- {item}" for item in card["known_decoders"])

    lines.extend(["", "## Distance Methods", ""])
    lines.extend(f"- {item}" for item in card["distance_methods"])

    lines.extend(["", "## Relations", ""])
    if card["relations"]:
        lines.extend(f"- `{rel['type']}` -> `{rel['target']}`" for rel in card["relations"])
    else:
        lines.append("- None")

    lines.extend(["", "## Linked Evidence", ""])
    if evidence_records:
        for evidence in evidence_records:
            lines.extend(
                [
                    f"### {evidence['title']}",
                    "",
                    f"- `paper_id`: `{evidence['paper_id']}`",
                    f"- `claim_type`: `{evidence['claim_type']}`",
                    f"- `statement`: {evidence['claim']['statement']}",
                    f"- `quote_ref`: `{evidence['provenance']['quote_ref']}`",
                    "",
                ]
            )
    else:
        lines.extend(["No linked evidence yet.", ""])

    lines.extend(["## Generated Instances", ""])
    if instance_records:
        for instance in instance_records:
            derived = instance["derived_properties"]
            summary = f"- `{instance['id']}` — n={derived['n']}, mx={derived['mx']}, mz={derived['mz']}"
            if derived["distance"] is not None:
                summary += f", distance={derived['distance']}"
            lines.append(summary)
    else:
        lines.append("- None")

    lines.extend(["", "## Source Papers", ""])
    if card["source_refs"]:
        lines.extend(f"- `{paper_id}`" for paper_id in card["source_refs"])
    else:
        lines.append("- None")

    return "\n".join(lines).rstrip() + "\n"
