import { build } from "esbuild";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

describe("browser style bundle", () => {
  it("ships an English-only user interface", async () => {
    const result = await build({
      entryPoints: [join(process.cwd(), "src/index.ts")],
      bundle: true,
      platform: "browser",
      format: "iife",
      target: ["firefox140"],
      write: false,
      outdir: "out",
      loader: {
        ".svg": "dataurl",
        ".woff2": "file",
        ".woff": "file",
        ".ttf": "file",
      },
    });

    const javascript = result.outputFiles
      .filter((file) => file.path.endsWith(".js"))
      .map((file) => file.text)
      .join("\n");
    expect(javascript).not.toMatch(/[\u3400-\u9fff]/u);
  });

  it("includes KaTeX CSS and emits its local fonts", async () => {
    const result = await build({
      entryPoints: [join(process.cwd(), "src/index.ts")],
      bundle: true,
      platform: "browser",
      format: "iife",
      target: ["firefox140"],
      write: false,
      outdir: "out",
      assetNames: "fonts/[name]-[hash]",
      loader: {
        ".svg": "dataurl",
        ".woff2": "file",
        ".woff": "file",
        ".ttf": "file",
      },
    });

    const css = result.outputFiles.find((file) => file.path.endsWith(".css"))?.text || "";
    const assets = result.outputFiles.map((file) => file.path.replaceAll("\\", "/"));
    expect(css).toContain(".katex");
    expect(css).toContain("@font-face");
    expect(css).toContain("KaTeX_Main-Regular");
    expect(assets.some((path) => /\/fonts\/KaTeX_[^/]+\.woff2$/.test(path))).toBe(true);
  });

  it("keeps float entries out of the sidebar's avatar grid", async () => {
    const result = await build({
      entryPoints: [join(process.cwd(), "src/index.ts")],
      bundle: true,
      platform: "browser",
      format: "iife",
      target: ["firefox140"],
      write: false,
      outdir: "out",
      assetNames: "fonts/[name]-[hash]",
      loader: {
        ".svg": "dataurl",
        ".woff2": "file",
        ".woff": "file",
        ".ttf": "file",
      },
    });

    const css = result.outputFiles.find((file) => file.path.endsWith(".css"))?.text || "";
    // The sidebar lays `.zc-entry-assistant` out as an avatar (22px) + content
    // grid. Float entries share the kind classes but render no avatar, so
    // without this override the answer text collapses into the 22px column.
    expect(css).toMatch(
      /\.zc-float-entry\.zc-entry-assistant,\s*\.zc-float-entry\.zc-entry-error\s*\{\s*display:\s*block;\s*\}/,
    );
  });

  it("declares the float transcript selectable and the float panel user-resizable", async () => {
    const result = await build({
      entryPoints: [join(process.cwd(), "src/index.ts")],
      bundle: true,
      platform: "browser",
      format: "iife",
      target: ["firefox140"],
      write: false,
      outdir: "out",
      assetNames: "fonts/[name]-[hash]",
      loader: {
        ".svg": "dataurl",
        ".woff2": "file",
        ".woff": "file",
        ".ttf": "file",
      },
    });

    const css = result.outputFiles.find((file) => file.path.endsWith(".css"))?.text || "";
    // XUL hosts don't allow text selection unless explicitly declared, so the
    // float transcript needs an explicit user-select: text rule (bug fix for
    // "can't select/copy the answer text").
    expect(css).toMatch(
      /\.zc-float-transcript,\s*\.zc-float-transcript \*\s*\{[^}]*user-select:\s*text;[^}]*\}/,
    );
    // The panel itself must be user-resizable via the native corner grip.
    expect(css).toMatch(/\.zc-float\s*\{[^}]*resize:\s*both;[^}]*\}/);
    // The full chat application is hosted by Zotero's native tab deck, so it
    // fills the document area without floating-panel chrome.
    expect(css).toMatch(
      /\.zc-workbench-chat\s*\{[^}]*width:\s*100%;[^}]*height:\s*100%;[^}]*border:\s*0;[^}]*\}/,
    );
    expect(css).not.toContain(".zc-qlab-command-grid");
    expect(css).toMatch(/\.zc-qmd-file-toggle\s*\{[^}]*width:\s*18px;[^}]*cursor:\s*pointer;/);
    expect(css).toContain(".zc-choose-paper");
    // The blanket `cursor: auto` on every transcript descendant (needed so
    // selectable prose doesn't show a pointer) must not beat `cursor: pointer`
    // on the transcript's actually-clickable elements -- it only wins if this
    // rule comes later in the stylesheet.
    expect(css).toMatch(
      /\.zc-float-transcript \.zc-math-copy,\s*\.zc-float-transcript \.zc-copy-answer,\s*\.zc-float-transcript \.zc-turn-summary\s*\{[^}]*cursor:\s*pointer;[^}]*\}/,
    );
  });

  it("scopes the 1.04em chat KaTeX override away from the visual editor", async () => {
    const result = await build({
      entryPoints: [join(process.cwd(), "src/index.ts")],
      bundle: true,
      platform: "browser",
      format: "iife",
      target: ["firefox140"],
      write: false,
      outdir: "out",
      assetNames: "fonts/[name]-[hash]",
      loader: {
        ".svg": "dataurl",
        ".woff2": "file",
        ".woff": "file",
        ".ttf": "file",
      },
    });

    const css = result.outputFiles.find((file) => file.path.endsWith(".css"))?.text || "";
    // Chat entries keep the 1.04em tuning (12.5px chat font)…
    expect(css).toMatch(
      /\.zc-entry-content \.zc-math-inline \.katex,\s*\.zc-entry-content \.zc-math-display \.katex\s*\{\s*font-size:\s*1\.04em;\s*\}/,
    );
    // …and no unscoped rule reaches the 17px visual editor, whose math must
    // fall back to KaTeX's stock 1.21em like Quarto's own KaTeX output.
    const withoutScoped = css
      .replaceAll(".zc-entry-content .zc-math-inline .katex", "")
      .replaceAll(".zc-entry-content .zc-math-display .katex", "");
    expect(withoutScoped).not.toContain(".zc-math-inline .katex");
    expect(withoutScoped).not.toContain(".zc-math-display .katex");
  });

  it("pins Visual Edit typography to the compiled draft preview theme", async () => {
    const result = await build({
      entryPoints: [join(process.cwd(), "src/index.ts")],
      bundle: true,
      platform: "browser",
      format: "iife",
      target: ["firefox140"],
      write: false,
      outdir: "out",
      assetNames: "fonts/[name]-[hash]",
      loader: {
        ".svg": "dataurl",
        ".woff2": "file",
        ".woff": "file",
        ".ttf": "file",
      },
    });

    const css = result.outputFiles.find((file) => file.path.endsWith(".css"))?.text || "";
    // Body: 17px/1.5 weight-400 #212529, 799px reading measure — measured from
    // drafts/.preview/…/bootstrap-e00a8cfd035d61cbe5d8da7afa12324c.min.css.
    expect(css).toMatch(
      /\.zc-qmd-visual-editor\s*\{[^}]*width:\s*min\(850px,\s*calc\(100%\s*-\s*44px\)\);[^}]*\}/,
    );
    expect(css).toMatch(
      /\.zc-qmd-visual-editor\s*\{[^}]*font:\s*400\s+17px\/1\.5\s+system-ui,[^}]*\}/,
    );
    expect(css).toMatch(/\.zc-qmd-visual-editor\s*\{[^}]*color:\s*#212529;[^}]*\}/);
    // Heading scale: h1 2rem / h2 1.65rem / h3 1.45rem / h4 1.25rem at the
    // 17px base (rem ≡ em because body size equals the root size).
    expect(css).toMatch(/\.zc-qmd-visual-block h1\s*\{[^}]*font-size:\s*2em;[^}]*\}/);
    expect(css).toMatch(/\.zc-qmd-visual-block h2\s*\{[^}]*font-size:\s*1\.65em;[^}]*\}/);
    expect(css).toMatch(/\.zc-qmd-visual-block h3\s*\{[^}]*font-size:\s*1\.45em;[^}]*\}/);
    expect(css).toMatch(/\.zc-qmd-visual-block h4\s*\{[^}]*font-size:\s*1\.25em;[^}]*\}/);
  });
});
