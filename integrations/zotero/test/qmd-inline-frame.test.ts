// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  QMD_INLINE_CONFIGURE_TOPIC,
  QMD_INLINE_EDIT_TOPIC,
  QMD_INLINE_NAVIGATE_TOPIC,
  editableQmdBlocks,
  qmdInlineFrameScript,
} from "../src/qmd-inline-edit";

describe("remote QMD inline editor frame", () => {
  afterEach(() => {
    delete (globalThis as Record<string, unknown>).content;
    delete (globalThis as Record<string, unknown>).addMessageListener;
    delete (globalThis as Record<string, unknown>).sendAsyncMessage;
    delete (globalThis as Record<string, unknown>).__researchLoopQmdInlineEdit;
    document.body.replaceChildren();
  });

  it("turns formulas and complete thm blocks into local source editors on click", () => {
    document.body.innerHTML = `
      <nav><a href="/Noisy_complexity/index.qmd">Noisy circuits</a></nav>
      <main class="content">
        <p>Energy <span class="math inline"><span>rendered E</span></span>.</p>
        <div id="thm-energy" class="callout callout-important">
          <div class="callout-header"><div class="callout-title-container">Theorem 1: Energy</div></div>
          <div class="callout-body"><p>Rendered theorem body <span class="math inline">inside</span>.</p></div>
        </div>
        <p>After <span id="after-math" class="math inline">rendered z</span>.</p>
        <p id="rich-reference">See Doe (2026) for context.</p>
      </main>`;
    const source = `Energy $E=mc^2$.\n\n::: {#thm-energy .callout-important}\n## Energy\n\nRendered theorem body $inside$.\n:::\n\nAfter $z$.\n\nSee [@doe_2026] for context.\n`;
    const blocks = editableQmdBlocks(source);
    const listeners = new Map<string, (message: { data: unknown }) => void>();
    const send = vi.fn();
    (globalThis as Record<string, unknown>).content = window;
    (globalThis as Record<string, unknown>).addMessageListener = (
      topic: string,
      listener: (message: { data: unknown }) => void,
    ) => listeners.set(topic, listener);
    (globalThis as Record<string, unknown>).sendAsyncMessage = send;

    expect(() => new Function(qmdInlineFrameScript())()).not.toThrow();
    document.querySelector<HTMLAnchorElement>("a")!.click();
    expect(send).toHaveBeenCalledWith(
      QMD_INLINE_NAVIGATE_TOPIC,
      expect.objectContaining({ href: expect.stringMatching(/Noisy_complexity\/index\.qmd$/) }),
    );
    listeners.get(QMD_INLINE_CONFIGURE_TOPIC)?.({
      data: {
        enabled: true,
        blocks: blocks.map(({ id, kind, text, domId, domKind, ordinal }) => ({
          id,
          kind,
          text,
          domId,
          domKind,
          ordinal,
        })),
      },
    });

    const formula = document.querySelector<HTMLElement>("span.math.inline")!;
    formula.click();
    const latex = formula.querySelector<HTMLInputElement>(".qlab-qmd-latex")!;
    expect(latex.value).toBe("E=mc^2");
    latex.value = "E=\\hbar\\omega";
    latex.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    expect(send).toHaveBeenCalledWith(
      QMD_INLINE_EDIT_TOPIC,
      expect.objectContaining({ text: "E=\\hbar\\omega" }),
    );
    expect(document.querySelector("#after-math")!.hasAttribute("data-qlab-qmd-block")).toBe(true);
    expect(document.querySelector("#thm-energy span.math")!.hasAttribute("data-qlab-qmd-block")).toBe(false);

    const theorem = document.querySelector<HTMLElement>("#thm-energy")!;
    theorem.click();
    const qmd = theorem.querySelector<HTMLTextAreaElement>(".qlab-qmd-block-source")!;
    expect(qmd.value).toContain("::: {#thm-energy");
    expect(qmd.value).toContain("Rendered theorem body $inside$.");
    qmd.value = qmd.value.replace("Rendered theorem body", "Edited theorem body");
    qmd.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    expect(send).toHaveBeenLastCalledWith(
      QMD_INLINE_EDIT_TOPIC,
      expect.objectContaining({ text: expect.stringContaining("Edited theorem body") }),
    );
    expect(theorem.querySelector(".callout-title-container")!.textContent).toContain("Theorem 1");

    const rich = document.querySelector<HTMLElement>("#rich-reference")!;
    rich.click();
    const richQmd = rich.querySelector<HTMLTextAreaElement>(".qlab-qmd-block-source")!;
    expect(richQmd.value).toBe("See [@doe_2026] for context.");
    richQmd.value = "See [@doe_2026] and [@roe_2027] for context.";
    richQmd.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    expect(send).toHaveBeenLastCalledWith(
      QMD_INLINE_EDIT_TOPIC,
      expect.objectContaining({ text: "See [@doe_2026] and [@roe_2027] for context." }),
    );
    expect(rich.textContent).toContain("Doe (2026)");

    theorem.click();
    expect(theorem.querySelector(".qlab-qmd-block-source")).not.toBeNull();
    listeners.get(QMD_INLINE_CONFIGURE_TOPIC)?.({
      data: { enabled: false, blocks: [] },
    });
    expect(theorem.querySelector(".qlab-qmd-block-source")).toBeNull();
    expect(theorem.querySelector(".callout-title-container")!.textContent).toContain("Theorem 1");
    expect(document.querySelector("[data-qlab-qmd-block]")).toBeNull();
  });
});
