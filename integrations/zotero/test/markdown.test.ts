// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderMarkdown } from "../src/markdown";

function render(markdown: string): HTMLDivElement {
  const host = document.createElement("div");
  host.appendChild(renderMarkdown(document, markdown));
  return host;
}

describe("safe paper Markdown renderer", () => {
  beforeEach(() => {
    document.body.replaceChildren();
  });

  it("renders Markdown links and bare URLs with external-navigation safeguards", () => {
    const host = render(
      "Read [the paper](https://example.org/paper?q=1) and https://example.org/appendix.",
    );
    const links = [...host.querySelectorAll("a")];

    expect(links).toHaveLength(2);
    expect(links[0]?.textContent).toBe("the paper");
    expect(links[0]?.href).toBe("https://example.org/paper?q=1");
    for (const link of links) {
      expect(link.target).toBe("_blank");
      expect(link.rel).toBe("noopener noreferrer");
      expect(link.referrerPolicy).toBe("no-referrer");
    }
  });

  it("turns Chinese PDF page and range citations into host-reader navigation", () => {
    const onPdfPageLink = vi.fn();
    const host = document.createElement("div");
    host.appendChild(renderMarkdown(document, [
      "[PDF 第5页](https://arxiv.org/pdf/2306.13123#page=5)",
      "[PDF 第6–7页](https://arxiv.org/pdf/2306.13123#page=6)",
    ].join(" "), { onPdfPageLink, canOpenPdfPageLink: () => true }));
    const links = [...host.querySelectorAll<HTMLAnchorElement>(".zc-pdf-page-link")];

    expect(links).toHaveLength(2);
    expect(links[0]?.dataset.pdfPage).toBe("5");
    expect(links[1]?.dataset.pdfPage).toBe("6");
    expect(links[1]?.dataset.pdfEndPage).toBe("7");
    links[0]?.click();
    links[1]?.click();
    expect(onPdfPageLink).toHaveBeenNthCalledWith(1, {
      page: 5,
      sourceUrl: "https://arxiv.org/pdf/2306.13123#page=5",
    });
    expect(onPdfPageLink).toHaveBeenNthCalledWith(2, {
      page: 6,
      endPage: 7,
      sourceUrl: "https://arxiv.org/pdf/2306.13123#page=6",
    });
  });

  it("recognizes English PDF page citations but does not hijack ordinary paginated web links", () => {
    const onPdfPageLink = vi.fn();
    const host = document.createElement("div");
    host.appendChild(renderMarkdown(document, [
      "[PDF pages 12-14](https://example.org/article.pdf?page=12)",
      "[results page](https://example.org/search?page=3)",
    ].join(" "), { onPdfPageLink, canOpenPdfPageLink: () => true }));

    const links = [...host.querySelectorAll<HTMLAnchorElement>("a")];
    expect(links[0]?.classList.contains("zc-pdf-page-link")).toBe(true);
    expect(links[1]?.classList.contains("zc-pdf-page-link")).toBe(false);
    links[0]?.click();
    expect(onPdfPageLink).toHaveBeenCalledWith({
      page: 12,
      endPage: 14,
      sourceUrl: "https://example.org/article.pdf?page=12",
    });
  });

  it("keeps an unmatched external PDF citation as a normal browser link", () => {
    const onPdfPageLink = vi.fn();
    const host = document.createElement("div");
    host.appendChild(renderMarkdown(
      document,
      "[PDF page 8](https://example.org/another-paper.pdf#page=8)",
      { onPdfPageLink, canOpenPdfPageLink: () => false },
    ));

    const link = host.querySelector<HTMLAnchorElement>("a")!;
    expect(link.classList.contains("zc-pdf-page-link")).toBe(false);
    expect(link.target).toBe("_blank");
    link.addEventListener("click", (event) => event.preventDefault(), { once: true });
    link.click();
    expect(onPdfPageLink).not.toHaveBeenCalled();
  });

  it("rejects executable and credential-bearing link destinations without parsing HTML", () => {
    const host = render(
      '[bad](javascript:alert(1)) [creds](https://user:pass@example.org/) <img src=x onerror="alert(1)">',
    );

    expect(host.querySelector("a")).toBeNull();
    expect(host.querySelector("img,script,iframe,object,embed")).toBeNull();
    expect(host.textContent).toContain("[bad](javascript:alert(1))");
    expect(host.textContent).toContain("<img");
  });

  it("renders aligned tables and inline formatting inside cells", () => {
    const host = render([
      "| Symbol | Meaning | Result |",
      "| :--- | :---: | ---: |",
      "| $x \\mid y$ | **conditional** | `true` |",
    ].join("\n"));

    expect(host.querySelectorAll("table")).toHaveLength(1);
    expect(host.querySelectorAll("th")).toHaveLength(3);
    expect(host.querySelector("th:nth-child(2)")?.classList.contains("zc-align-center")).toBe(true);
    expect(host.querySelector("th:nth-child(3)")?.classList.contains("zc-align-right")).toBe(true);
    expect(host.querySelector("td strong")?.textContent).toBe("conditional");
    expect(host.querySelector("td code")?.textContent).toBe("true");
    expect(host.querySelector("td .katex")).not.toBeNull();
  });

  it("renders inline and multiline display LaTeX locally with KaTeX", () => {
    const host = render([
      "Einstein wrote $E = mc^2$.",
      "",
      "$$",
      "\\int_0^1 x^2 \\, dx = \\frac{1}{3}",
      "$$",
      "",
      "And \\(\\alpha + \\beta\\) is inline.",
    ].join("\n"));

    expect(host.querySelectorAll(".zc-math-inline .katex")).toHaveLength(2);
    expect(host.querySelectorAll(".zc-math-display .katex-display")).toHaveLength(1);
    expect(host.querySelector(".zc-math-error")).toBeNull();
  });

  it("keeps code literal and hardens untrusted TeX commands", () => {
    const host = render([
      "`$not_math$`",
      "",
      "$\\href{javascript:alert(1)}{click}$",
      "",
      "```md",
      "[not a link](https://example.org) $not_math$ <script>alert(1)</script>",
      "```",
    ].join("\n"));

    expect(host.querySelectorAll(".zc-math-inline")).toHaveLength(1);
    expect(host.querySelector(".zc-math-inline a, .zc-math-inline img")).toBeNull();
    expect(host.querySelector("script")).toBeNull();
    expect(host.querySelector("pre code")?.textContent).toContain("[not a link]");
    expect(host.querySelector("p > code")?.textContent).toBe("$not_math$");
  });

  it("falls back to visible source text for invalid formulas", () => {
    const host = render("Before $\\notARealCommand{$ after");
    const fallback = host.querySelector(".zc-math-error");

    expect(fallback?.textContent).toBe("$\\notARealCommand{$");
    expect(host.textContent).toContain("after");
  });

  it("wraps math output with a copyable container carrying the LaTeX source", () => {
    const fragment = renderMarkdown(document, "$$E = mc^2$$\n\n行内 $a+b$ 检查");
    const display = document.createElement("div");
    display.appendChild(fragment);
    const block = display.querySelector(".zc-math-display.zc-math-copy")!;
    expect(block.getAttribute("data-latex")).toBe("E = mc^2");
    expect(block.getAttribute("title")).toBe("Click to copy LaTeX");
    const inline = display.querySelector(".zc-math-inline.zc-math-copy")!;
    expect(inline.getAttribute("data-latex")).toBe("a+b");
  });

  it("carries the copy attributes on the KaTeX-error fallback too", () => {
    const host = render("Before $\\notARealCommand{$ after");
    const fallback = host.querySelector(".zc-math-error.zc-math-copy")!;

    expect(fallback.getAttribute("data-latex")).toBe("\\notARealCommand{");
    expect(fallback.getAttribute("title")).toBe("Click to copy LaTeX");
  });
});

describe("newlineAsBreak", () => {
  beforeEach(() => {
    document.body.replaceChildren();
  });

  it("renders single newlines inside paragraphs as hard breaks by default", () => {
    const host = render("first line\nsecond line");
    const paragraph = host.querySelector("p")!;
    expect(paragraph.querySelectorAll("br")).toHaveLength(1);
    expect(paragraph.textContent).toBe("first linesecond line");
  });

  it("renders single newlines as spaces when newlineAsBreak is false", () => {
    const host = document.createElement("div");
    host.appendChild(renderMarkdown(document, "first line\nsecond line", { newlineAsBreak: false }));
    const paragraph = host.querySelector("p")!;
    expect(paragraph.querySelector("br")).toBeNull();
    expect(paragraph.textContent).toBe("first line second line");
  });

  it("applies the same soft-break semantics inside blockquotes", () => {
    const hard = render("> quoted line one\n> quoted line two");
    expect(hard.querySelector("blockquote br")).not.toBeNull();

    const soft = document.createElement("div");
    soft.appendChild(renderMarkdown(document, "> quoted line one\n> quoted line two", { newlineAsBreak: false }));
    expect(soft.querySelector("blockquote br")).toBeNull();
    expect(soft.querySelector("blockquote")!.textContent).toBe("quoted line one quoted line two");
  });
});

describe("list grammar parity with the visual block splitter", () => {
  beforeEach(() => {
    document.body.replaceChildren();
  });

  it("renders + bullets as unordered list items", () => {
    const host = render("+ alpha\n+ beta");
    const items = [...host.querySelectorAll("ul > li")];
    expect(items.map((item) => item.textContent)).toEqual(["alpha", "beta"]);
    expect(host.querySelector("p")).toBeNull();
  });

  it("renders 1) numbering as ordered list items", () => {
    const host = render("1) first\n2) second");
    const items = [...host.querySelectorAll("ol > li")];
    expect(items.map((item) => item.textContent)).toEqual(["first", "second"]);
    expect(host.querySelector("p")).toBeNull();
  });

  it("keeps indented continuation lines inside the previous list item", () => {
    const host = render("- head line\n  continuation line\n- second item");
    const items = [...host.querySelectorAll("ul > li")];
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toContain("head line");
    expect(items[0]?.textContent).toContain("continuation line");
    expect(items[1]?.textContent).toBe("second item");
    expect(host.querySelector("p")).toBeNull();
  });

  it("breaks a paragraph when a + bullet or 1) item follows it", () => {
    const host = render("intro text\n+ bullet item");
    expect(host.querySelector("p")?.textContent).toBe("intro text");
    expect(host.querySelector("ul > li")?.textContent).toBe("bullet item");
  });

  it("ends the list at a blank line like the block splitter does", () => {
    const host = render("- item\n\nparagraph after");
    expect(host.querySelectorAll("ul > li")).toHaveLength(1);
    expect(host.querySelector("p")?.textContent).toBe("paragraph after");
  });
});
