/**
 * Renders a plugin surface in a real browser.
 *
 * Nothing else in this repository lays `src/styles.css` out. Clipping,
 * overflow, and menu placement are layout facts, not DOM facts, so happy-dom
 * cannot see them — every one of those bugs reached the user because the tests
 * that ran had no geometry. Chromium is not Gecko, but a box that overflows its
 * container overflows it in both, which is the class of bug this catches.
 *
 * What this cannot check is on the macOS checklist instead: XUL browsers,
 * chrome `user-select`, and caret painting in a chrome window.
 */

import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { fileURLToPath, pathToFileURL } from "node:url";

import { build } from "esbuild";
import { chromium } from "playwright";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = path.resolve(HERE, "..", "..");
const KATEX_DIST = path.join(PLUGIN_ROOT, "node_modules", "katex", "dist");
const KATEX_FONTS = path.join(KATEX_DIST, "fonts");
const VISUAL_ORIGIN = "https://visual-parity.test";
const execFileAsync = promisify(execFile);

let browser;

async function sharedBrowser() {
  browser ??= await chromium.launch();
  return browser;
}

export async function closeHarness() {
  await browser?.close();
  browser = undefined;
}

function isBelow(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative !== "" && !relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative);
}

function contentType(filePath) {
  switch (path.extname(filePath).toLowerCase()) {
    case ".css": return "text/css";
    case ".js": return "text/javascript";
    case ".woff2": return "font/woff2";
    case ".woff": return "font/woff";
    case ".ttf": return "font/ttf";
    default: return "application/octet-stream";
  }
}

function assetFailureMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

export function assertAssetLedgerComplete({ attempted, fulfilled, failures }) {
  const missing = [...attempted].filter((asset) => !fulfilled.has(asset));
  if (failures.size === 0 && missing.length === 0) return;
  const details = [...new Set([
    ...missing.map((asset) => `${asset}${failures.has(asset) ? ` (${failures.get(asset)})` : " (not fulfilled)"}`),
    ...[...failures].filter(([asset]) => !missing.includes(asset)).map(([asset, reason]) => `${asset} (${reason})`),
  ])];
  assert.fail(`KaTeX asset fulfillment failed: ${details.join("; ")}`);
}

async function failLocalAsset(route, ledger, key, reason, errorCode = "failed") {
  ledger.attempted.add(key);
  ledger.failures.set(key, reason);
  await route.abort(errorCode);
  return false;
}

async function localAsset(route, root, requestPath, { ledger, key, basenameOnly = false }) {
  ledger.attempted.add(key);
  let decoded;
  try {
    decoded = decodeURIComponent(requestPath);
  }
  catch (error) {
    return failLocalAsset(route, ledger, key, `invalid URL encoding: ${assetFailureMessage(error)}`, "blockedbyclient");
  }
  if (basenameOnly && decoded !== path.basename(decoded)) {
    return failLocalAsset(route, ledger, key, "font path is not a basename", "blockedbyclient");
  }
  const candidate = path.resolve(root, decoded);
  if (!isBelow(root, candidate)) {
    return failLocalAsset(route, ledger, key, "path escapes the installed KaTeX directory", "blockedbyclient");
  }
  try {
    await route.fulfill({
      body: await readFile(candidate),
      contentType: contentType(candidate),
    });
    ledger.fulfilled.add(key);
    return true;
  }
  catch (error) {
    return failLocalAsset(route, ledger, key, assetFailureMessage(error));
  }
}

async function visualEditorBundle() {
  const result = await build({
    bundle: true,
    platform: "browser",
    format: "iife",
    target: ["firefox140"],
    write: false,
    stdin: {
      loader: "ts",
      resolveDir: PLUGIN_ROOT,
      sourcefile: "visual-parity-entry.ts",
      contents: [
        'import { QmdVisualEditor } from "./src/qmd-visual-editor";',
        "globalThis.__zoteroVisualParity = { QmdVisualEditor };",
      ].join("\n"),
    },
  });
  assert.equal(result.outputFiles.length, 1, "visual parity bundle must have one in-memory output");
  return result.outputFiles[0].text;
}

function parityShell() {
  return `<!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <link rel="stylesheet" href="/plugin.css">
        <link rel="stylesheet" href="/katex/katex.min.css">
      </head>
      <body><div id="visual-host"></div></body>
    </html>`;
}

export async function routeDraftParityRequest(route, {
  assetLedger,
  pluginStyles,
  katexStyles,
}) {
  const url = new URL(route.request().url());
  const katexMatch = /^\/npm\/katex@[^/]+\/dist\/(.+)$/.exec(url.pathname);
  if (url.hostname === "cdn.jsdelivr.net" && katexMatch) {
    await localAsset(route, KATEX_DIST, katexMatch[1], {
      ledger: assetLedger,
      key: `preview:${url.href}`,
    });
    return;
  }
  if (url.origin === VISUAL_ORIGIN) {
    if (url.pathname === "/index.html") {
      await route.fulfill({ body: parityShell(), contentType: "text/html" });
      return;
    }
    if (url.pathname === "/plugin.css") {
      await route.fulfill({ body: pluginStyles, contentType: "text/css" });
      return;
    }
    if (url.pathname === "/katex/katex.min.css") {
      await route.fulfill({ body: katexStyles, contentType: "text/css" });
      return;
    }
    if (url.pathname.startsWith("/katex/fonts/")) {
      const requested = url.pathname.slice("/katex/fonts/".length);
      await localAsset(route, KATEX_FONTS, requested, {
        ledger: assetLedger,
        key: `visual:${url.href}`,
        basenameOnly: true,
      });
      return;
    }
    await failLocalAsset(
      route,
      assetLedger,
      `visual:${url.href}`,
      `unexpected virtual-origin asset: ${url.pathname}`,
      "blockedbyclient",
    );
    return;
  }
  if (url.protocol === "http:" || url.protocol === "https:") {
    const scope = url.hostname === "cdn.jsdelivr.net" ? "preview" : "external";
    await failLocalAsset(
      route,
      assetLedger,
      `${scope}:${url.href}`,
      "unexpected HTTP(S) asset request blocked by the offline parity harness",
      "blockedbyclient",
    );
    return;
  }
  await route.continue();
}

async function measureDraftSurface(page, selectors) {
  return page.evaluate(({ paragraphSelector, inlineMathSelector, displayMathSelector }) => {
    const normalize = (value) => value.replace(/\s+/g, " ").trim();
    const byPrefix = (prefix) => {
      const element = [...document.querySelectorAll(paragraphSelector)]
        .find((candidate) => normalize(candidate.textContent || "").startsWith(prefix));
      if (!element) throw new Error(`parity paragraph not found: ${prefix}`);
      return element;
    };
    const proseText = (element) => {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      const parts = [];
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (node.parentElement?.closest(".katex")) continue;
        if (node.textContent?.trim()) parts.push(node.textContent);
      }
      return normalize(parts.join(" "));
    };
    const lineCount = (element) => {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      const tops = new Set();
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (node.parentElement?.closest(".katex") || !node.textContent?.trim()) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        for (const rect of range.getClientRects()) {
          if (rect.width > 0 && rect.height > 0) tops.add(Math.round(rect.top));
        }
      }
      return tops.size;
    };

    const soft = byPrefix("A soft-wrapped sentence");
    const natural = byPrefix("This deliberately long paragraph");
    const inlineMath = document.querySelector(inlineMathSelector);
    const displayMath = document.querySelector(displayMathSelector);
    if (!inlineMath || !displayMath) throw new Error("parity formula was not rendered");
    const style = getComputedStyle(soft);

    return {
      bodyFontSize: Number.parseFloat(style.fontSize),
      lineHeight: Number.parseFloat(style.lineHeight),
      contentWidth: soft.getBoundingClientRect().width,
      inlineMathHeight: inlineMath.getBoundingClientRect().height,
      displayMathHeight: displayMath.getBoundingClientRect().height,
      softBreakContainsBr: Boolean(soft.querySelector("br")),
      softBreakText: proseText(soft),
      softBreakLineCount: lineCount(soft),
      naturalWrapText: proseText(natural),
      naturalWrapLineCount: lineCount(natural),
    };
  }, selectors);
}

export function collectKatexFontReport(formulaSelectors, environment) {
  const pageDocument = environment?.document ?? document;
  const styleFor = environment?.getComputedStyle ?? getComputedStyle;
  const unquote = (family) => family.trim().replace(/^['"]|['"]$/g, "");
  const directlyPaintsGlyphs = (element) => [...element.childNodes].some((node) => {
    if (node.nodeType !== 3) return false;
    // KaTeX emits U+200B in .vlist-s as a layout strut. String#trim does not
    // remove it, but it has no painted glyph and must not claim a font face.
    return (node.textContent || "").replace(/\u200b/g, "").trim() !== "";
  });
  const used = new Map();
  for (const selector of formulaSelectors) {
    const formula = pageDocument.querySelector(selector);
    if (!formula) continue;
    for (const element of formula.querySelectorAll(".katex-html, .katex-html *")) {
      if (!directlyPaintsGlyphs(element)) continue;
      const style = styleFor(element);
      const family = unquote(style.fontFamily.split(",")[0] || "");
      if (!family.startsWith("KaTeX_")) continue;
      const signature = `${family}|${style.fontStyle}|${style.fontWeight}`;
      used.set(signature, { family, style: style.fontStyle, weight: style.fontWeight });
    }
  }
  const faces = [...pageDocument.fonts].map((face) => ({
    family: unquote(face.family),
    style: face.style,
    weight: face.weight,
    status: face.status,
  }));
  const unloaded = [...used.values()].filter((signature) => !faces.some((face) =>
    face.family === signature.family
    && face.style === signature.style
    && face.weight === signature.weight
    && face.status === "loaded"));
  return { used: [...used.values()], unloaded, faces };
}

async function assertKatexFontsLoaded(page, selectors, surface) {
  const result = await page.evaluate(collectKatexFontReport, selectors);
  assert.ok(result.used.length > 0, `${surface} fixture formulas did not use a KaTeX font face`);
  assert.deepEqual(
    result.unloaded,
    [],
    `${surface} fixture formulas used KaTeX font faces that were not loaded: ${JSON.stringify(result)}`,
  );
}

/**
 * Renders the controlled fixture through real Quarto and the production
 * QmdVisualEditor, then returns independent browser geometry for both.
 */
export async function renderDraftParity({ source, width = 1200 }) {
  const tempRoot = await mkdtemp(path.join(tmpdir(), "zotero-visual-parity-"));
  const sourcePath = path.join(tempRoot, "visual-edit-parity.qmd");
  const outputRoot = path.join(tempRoot, "out");
  let context;
  let preview;
  let visual;
  try {
    await writeFile(sourcePath, source, "utf8");
    await execFileAsync("quarto", [
      "render", sourcePath, "--no-execute", "--output-dir", outputRoot,
    ], {
      cwd: PLUGIN_ROOT,
      env: { ...process.env, XDG_CACHE_HOME: path.join(tempRoot, "cache") },
      maxBuffer: 8 * 1024 * 1024,
    });

    const [pluginStyles, katexStyles, editorBundle] = await Promise.all([
      readFile(path.join(PLUGIN_ROOT, "src", "styles.css")),
      readFile(path.join(KATEX_DIST, "katex.min.css")),
      visualEditorBundle(),
    ]);
    const assetLedger = {
      attempted: new Set(),
      fulfilled: new Set(),
      failures: new Map(),
    };

    context = await (await sharedBrowser()).newContext({ viewport: { width, height: 900 } });
    await context.route("**/*", (route) => routeDraftParityRequest(route, {
      assetLedger,
      pluginStyles,
      katexStyles,
    }));

    preview = await context.newPage();
    await preview.goto(pathToFileURL(path.join(outputRoot, "visual-edit-parity.html")).href, {
      waitUntil: "load",
    });
    visual = await context.newPage();
    await visual.goto(`${VISUAL_ORIGIN}/index.html`, { waitUntil: "load" });
    await visual.addScriptTag({ content: editorBundle });
    await visual.evaluate((documentSource) => {
      const editor = new globalThis.__zoteroVisualParity.QmdVisualEditor(document, {
        save: async () => { throw new Error("parity harness is read-only"); },
      });
      document.querySelector("#visual-host").append(editor.root);
      editor.setDocument({ source: documentSource, revision: "fixture" }, false);
    }, source);

    await Promise.all([
      preview.waitForSelector(".math.inline .katex"),
      preview.waitForSelector(".math.display .katex"),
      visual.waitForSelector(".zc-math-inline .katex"),
      visual.waitForSelector(".zc-math-display .katex"),
    ]);
    await Promise.all([
      preview.evaluate(async () => { await document.fonts.ready; }),
      visual.evaluate(async () => { await document.fonts.ready; }),
    ]);

    assertAssetLedgerComplete(assetLedger);
    assert.ok([...assetLedger.fulfilled].some((key) => key.startsWith("preview:") && key.endsWith("/katex.min.js")), "Quarto KaTeX JavaScript was not fulfilled locally");
    assert.ok([...assetLedger.fulfilled].some((key) => key.startsWith("preview:") && key.endsWith("/katex.min.css")), "Quarto KaTeX stylesheet was not fulfilled locally");
    assert.ok([...assetLedger.fulfilled].some((key) => key.startsWith("preview:") && key.includes("/fonts/")), "Quarto KaTeX font was not fulfilled locally");
    assert.ok([...assetLedger.fulfilled].some((key) => key.startsWith("visual:") && key.includes("/katex/fonts/")), "Visual Edit KaTeX font was not fulfilled locally");
    await Promise.all([
      assertKatexFontsLoaded(preview, [".math.inline .katex", ".math.display .katex"], "Preview"),
      assertKatexFontsLoaded(visual, [".zc-math-inline .katex", ".zc-math-display .katex"], "Visual Edit"),
    ]);

    const [previewMeasurements, visualMeasurements] = await Promise.all([
      measureDraftSurface(preview, {
        paragraphSelector: "#quarto-document-content > p",
        inlineMathSelector: ".math.inline .katex",
        displayMathSelector: ".math.display .katex",
      }),
      measureDraftSurface(visual, {
        paragraphSelector: ".zc-qmd-visual-block.is-paragraph > p",
        inlineMathSelector: ".zc-math-inline .katex",
        displayMathSelector: ".zc-math-display .katex",
      }),
    ]);
    return { preview: previewMeasurements, visual: visualMeasurements };
  }
  finally {
    await Promise.allSettled([
      preview?.close(),
      visual?.close(),
      context?.close(),
    ].filter(Boolean));
    await rm(tempRoot, { recursive: true, force: true });
  }
}

/**
 * Lays out `html` inside the plugin's own stylesheet and measures it.
 *
 * `measure` names elements whose geometry comes back, with two distinct
 * questions about each:
 *
 * - `clipped` — is any part of it outside what its container can *ever* show,
 *   even after scrolling? That is content the user cannot reach at all.
 * - `sliced` — at rest, is it cut through rather than either fully shown or
 *   fully out of view? A container capped at a height that is not a whole
 *   number of rows leaves half a row of text sitting there, which reads as
 *   text that has been covered up.
 */
export async function renderSurface({ html, width = 420, height = 640, measure = [] }) {
  const styles = await readFile(path.join(PLUGIN_ROOT, "src", "styles.css"), "utf8");
  const context = await (await sharedBrowser()).newContext({ viewport: { width, height } });
  const page = await context.newPage();
  await page.setContent(
    `<!doctype html><meta charset="utf-8"><style>
       html, body { margin: 0; height: 100%; }
       ${styles}
     </style><body>${html}</body>`,
    { waitUntil: "load" },
  );

  const selectors = Array.isArray(measure) ? measure : [measure];
  const measurements = await page.evaluate((wanted) => {
    const scrollParent = (element) => {
      for (let node = element.parentElement; node; node = node.parentElement) {
        const overflow = getComputedStyle(node).overflow + getComputedStyle(node).overflowY;
        if (/auto|scroll|hidden/.test(overflow)) return node;
      }
      return document.documentElement;
    };
    const result = {};
    for (const selector of wanted) {
      const element = document.querySelector(selector);
      if (!element) {
        result[selector] = { found: false };
        continue;
      }
      const container = scrollParent(element);
      const box = element.getBoundingClientRect();
      const bounds = container.getBoundingClientRect();
      // Reachable by scrolling, or already visible: either way, not clipped.
      const reachableBottom = bounds.top + container.scrollHeight;
      const reachableRight = bounds.left + container.scrollWidth;
      const visibleTop = bounds.top + container.scrollTop - container.scrollTop;
      const visibleBottom = bounds.top + container.clientHeight;
      const intersects = box.bottom > visibleTop && box.top < visibleBottom;
      result[selector] = {
        found: true,
        width: Math.round(box.width),
        height: Math.round(box.height),
        clippedBelow: box.bottom > reachableBottom + 0.5,
        clippedRight: box.right > reachableRight + 0.5,
        clipped: box.bottom > reachableBottom + 0.5 || box.right > reachableRight + 0.5,
        sliced: intersects && box.bottom > visibleBottom + 0.5,
        container: container.className || container.tagName,
      };
    }
    return result;
  }, selectors);

  const screenshot = await page.screenshot();
  await context.close();
  return { measurements, screenshot };
}
