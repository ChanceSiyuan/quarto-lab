import { describe, expect, it } from "vitest";
import {
  applyQmdEditableBlock,
  editableQmdBlocks,
} from "../src/qmd-inline-edit";

const SOURCE = `---
title: A Draft
description: "tbc"
categories: theory
---

# Plain heading

This paragraph can be edited directly in the preview.

This paragraph contains $E = mc^2$ and stays protected.

- A plain list item
- A citation [@example_2026] stays protected

::: {#thm-example}
## A theorem title

The theorem prose is editable.

$$
x^2 \\ge 0
$$
:::

After the theorem, $z$ is editable too.
`;

describe("QMD inline preview edits", () => {
  it("maps plain prose directly and complex Markdown as one source-backed block", () => {
    const blocks = editableQmdBlocks(SOURCE);

    expect(blocks
      .filter((block) => ["heading", "paragraph", "list-item", "blockquote"].includes(block.kind))
      .map((block) => [block.kind, block.text])).toEqual([
      ["heading", "Plain heading"],
      ["paragraph", "This paragraph can be edited directly in the preview."],
      ["list-item", "A plain list item"],
    ]);
    expect(blocks.filter((block) => block.kind === "rich-block").map((block) => block.text))
      .toEqual([
        "This paragraph contains $E = mc^2$ and stays protected.",
        "A citation [@example_2026] stays protected",
        "After the theorem, $z$ is editable too.",
      ]);
    expect(blocks.filter((block) => block.kind.endsWith("math")).map((block) => block.text))
      .toEqual(["E = mc^2", "z"]);
    expect(blocks.find((block) => block.kind === "theorem-block")).toMatchObject({
      domId: "thm-example",
      text: expect.stringContaining("The theorem prose is editable."),
    });
  });

  it("writes a rich paragraph as QMD while preserving its formula and citation syntax", () => {
    const block = editableQmdBlocks(SOURCE)
      .find((candidate) => candidate.kind === "rich-block" && candidate.text.includes("mc^2"))!;
    const result = applyQmdEditableBlock(
      SOURCE,
      block,
      "A revised *rich* paragraph keeps $E = mc^2$ and cites [@example_2026].",
    );

    expect(result.source).toContain(
      "A revised *rich* paragraph keeps $E = mc^2$ and cites [@example_2026].",
    );
  });

  it("writes one mapped block without changing frontmatter, callouts, or formulas", () => {
    const block = editableQmdBlocks(SOURCE)
      .find((candidate) => candidate.kind === "theorem-block")!;
    const result = applyQmdEditableBlock(
      SOURCE,
      block,
      block.text.replace(
        "The theorem prose is editable.",
        "The theorem prose is now clearer and still belongs to the theorem.",
      ),
    );

    expect(result.changed).toBe(true);
    expect(result.source).toContain("title: A Draft");
    expect(result.source).toContain("::: {#thm-example}");
    expect(result.source).toContain("x^2 \\ge 0");
    expect(result.source).toContain(
      "The theorem prose is now clearer and still belongs to the theorem.",
    );
    expect(result.source).not.toContain("The theorem prose is editable.");
  });

  it("keeps a mapping usable after another block changes its source offsets", () => {
    const blocks = editableQmdBlocks(SOURCE);
    const first = blocks.find((block) => block.text === "Plain heading")!;
    const later = blocks.find((block) => block.kind === "theorem-block")!;
    const firstResult = applyQmdEditableBlock(SOURCE, first, "A much longer plain heading");
    const laterResult = applyQmdEditableBlock(
      firstResult.source,
      later,
      later.text.replace("The theorem prose is editable.", "The later edit still lands in the right block."),
    );

    expect(laterResult.source).toContain("# A much longer plain heading");
    expect(laterResult.source).toContain("The later edit still lands in the right block.");
  });

  it("refuses stale or ambiguous blocks instead of guessing where to write", () => {
    const duplicate = `${SOURCE}\nRepeated prose.\n\nRepeated prose.\n`;
    expect(editableQmdBlocks(duplicate).some((block) => block.text === "Repeated prose."))
      .toBe(false);

    const block = editableQmdBlocks(SOURCE)[0]!;
    expect(() => applyQmdEditableBlock(SOURCE.replace("Plain heading", "Changed elsewhere"), block, "New"))
      .toThrow(/changed before this edit/i);
  });

  it("normalizes pasted line breaks and escapes new Markdown syntax as text", () => {
    const block = editableQmdBlocks(SOURCE)
      .find((candidate) => candidate.text === "A plain list item")!;
    const result = applyQmdEditableBlock(
      SOURCE,
      block,
      "A *literal* value with $money and\nno new list",
    );

    expect(result.source).toContain("- A \\*literal\\* value with \\$money and no new list");
    const edited = editableQmdBlocks(result.source)
      .find((candidate) => candidate.kind === "list-item");
    expect(edited?.text).toBe("A *literal* value with $money and no new list");
  });

  it("edits LaTeX inside its existing delimiters", () => {
    const inline = editableQmdBlocks(SOURCE)
      .find((candidate) => candidate.kind === "inline-math")!;
    const standalone = `${SOURCE}\n$$\na+b\n$$\n`;
    const display = editableQmdBlocks(standalone)
      .find((candidate) => candidate.kind === "display-math")!;
    const inlineResult = applyQmdEditableBlock(standalone, inline, "E = \\gamma mc^2");
    const displayResult = applyQmdEditableBlock(
      inlineResult.source,
      display,
      "a+b+c",
    );

    expect(displayResult.source).toContain("$E = \\gamma mc^2$");
    expect(displayResult.source).toContain("$$\na+b+c\n$$");
  });
});
