// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";
import { QmdVisualEditor } from "../src/qmd-visual-editor";

const SOURCE = `---
title: Visual Draft
description: "A visual editing fixture"
categories: theory
---

# Result

The gap is $\\Delta > 0$ in this regime.

::: {#thm-gap}
## Spectral gap

For every size $n$, suppose

$$
H_n \\succeq \\Delta I.
$$
:::
`;

function mount() {
  let source = SOURCE;
  let revision = "r1";
  const save = vi.fn(async (next: string, expected: string) => {
    if (expected !== revision) throw new Error("The QMD revision changed before save");
    source = next;
    revision = `r${Number(revision.slice(1)) + 1}`;
    return { source, revision };
  });
  const onStatus = vi.fn();
  const editor = new QmdVisualEditor(document, { save, onStatus });
  document.body.appendChild(editor.root);
  editor.setDocument({ source, revision }, true);
  return { editor, save, onStatus, source: () => source };
}

async function settle(): Promise<void> {
  for (let index = 0; index < 5; index += 1) await new Promise((resolve) => setTimeout(resolve, 0));
}

describe("QmdVisualEditor", () => {
  afterEach(() => {
    vi.useRealTimers();
    document.body.replaceChildren();
  });

  it("renders theorem, lemma, and definition syntax as Quarto-like semantic cards", () => {
    const { editor } = mount();
    const card = editor.root.querySelector<HTMLElement>(".zc-qmd-visual-card.is-thm")!;

    expect(card.querySelector("header")!.textContent).toBe("Theorem 1: Spectral gap");
    expect(card.querySelectorAll(".katex").length).toBeGreaterThan(0);
    expect(card.textContent).toContain("For every size");
  });

  it("edits one formula inside a theorem without flattening the rest of the card", async () => {
    const { editor, save, source } = mount();
    const card = editor.root.querySelector<HTMLElement>(".zc-qmd-visual-card.is-thm")!;
    const formula = card.querySelector<HTMLElement>(".zc-math-inline")!;
    formula.click();

    const input = card.querySelector<HTMLInputElement>(".zc-qmd-visual-math-editor")!;
    expect(input).not.toBeNull();
    expect(card.querySelector(".zc-qmd-visual-source-editor")).toBeNull();
    input.value = "m";
    input.dispatchEvent(new Event("input"));
    input.blur();
    await settle();

    expect(save).toHaveBeenCalled();
    expect(source()).toContain("For every size $m$");
    expect(editor.root.querySelector(".zc-qmd-visual-card.is-thm .katex")).not.toBeNull();
  });

  it("turns the complete theorem card into fenced QMD when its text is clicked", () => {
    const { editor } = mount();
    const card = editor.root.querySelector<HTMLElement>(".zc-qmd-visual-card.is-thm")!;
    card.querySelector<HTMLElement>("header")!.click();

    const source = card.querySelector<HTMLTextAreaElement>(".zc-qmd-visual-source-editor")!;
    expect(source.value).toContain("::: {#thm-gap}");
    expect(source.value).toContain("H_n \\succeq \\Delta I");
    expect(card.querySelector(".katex")).toBeNull();
  });

  it("autosaves a visual block after a short idle period", async () => {
    vi.useFakeTimers();
    const { editor, save, source } = mount();
    const paragraph = editor.root.querySelector<HTMLElement>('[data-block-kind="paragraph"]')!;
    paragraph.click();
    const textarea = paragraph.querySelector<HTMLTextAreaElement>("textarea")!;
    textarea.value = "The gap remains positive.";
    textarea.dispatchEvent(new Event("input"));

    await vi.advanceTimersByTimeAsync(450);
    await vi.runAllTimersAsync();

    expect(save).toHaveBeenCalledOnce();
    expect(source()).toContain("The gap remains positive.");
  });

  it("flows hard-wrapped source prose as one paragraph like the compiled preview", () => {
    const save = vi.fn(async (next: string) => ({ source: next, revision: "r2" }));
    const editor = new QmdVisualEditor(document, { save });
    document.body.appendChild(editor.root);
    editor.setDocument({
      source: [
        "A first sentence that was",
        "hard-wrapped in the source",
        "across three lines.",
        "",
        "::: {#lem-flow}",
        "## Soft wrap",
        "The lemma statement is",
        "wrapped across lines.",
        ":::",
        "",
      ].join("\n"),
      revision: "r1",
    }, false);

    const paragraph = editor.root.querySelector<HTMLElement>('[data-block-kind="paragraph"]')!;
    expect(paragraph.querySelector("br")).toBeNull();
    expect(paragraph.textContent).toContain(
      "A first sentence that was hard-wrapped in the source across three lines.",
    );

    const cardBody = editor.root.querySelector<HTMLElement>(".zc-qmd-visual-card.is-lem .zc-qmd-visual-card-body")!;
    expect(cardBody.querySelector("br")).toBeNull();
    expect(cardBody.textContent).toContain("The lemma statement is wrapped across lines.");
  });
});
