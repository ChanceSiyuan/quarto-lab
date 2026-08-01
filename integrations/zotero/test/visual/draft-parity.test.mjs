import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test, { after } from "node:test";
import { fileURLToPath } from "node:url";

import {
  assertAssetLedgerComplete,
  closeHarness,
  collectKatexFontReport,
  renderDraftParity,
  routeDraftParityRequest,
} from "./render-harness.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = path.resolve(HERE, "..", "fixtures", "visual-edit-parity.qmd");

const SOFT_BREAK_TEXT =
  "A soft-wrapped sentence keeps the transition amplitude on one flowing paragraph even though its source uses a newline.";
const NATURAL_WRAP_TEXT =
  "This deliberately long paragraph checks that equal content widths produce the same natural wrapping across both draft surfaces without inserting an authored hard break into the prose.";

after(() => closeHarness());

test("asset ledger rejects any attempted KaTeX asset that was not fulfilled", () => {
  assert.throws(
    () => assertAssetLedgerComplete({
      attempted: new Set([
        "preview:https://cdn.jsdelivr.net/npm/katex@latest/dist/katex.min.css",
        "preview:https://cdn.jsdelivr.net/npm/katex@latest/dist/fonts/KaTeX_Main-Regular.woff2",
      ]),
      fulfilled: new Set([
        "preview:https://cdn.jsdelivr.net/npm/katex@latest/dist/katex.min.css",
      ]),
      failures: new Map([
        [
          "preview:https://cdn.jsdelivr.net/npm/katex@latest/dist/fonts/KaTeX_Main-Regular.woff2",
          "injected read failure",
        ],
      ]),
    }),
    /KaTeX asset fulfillment failed.*KaTeX_Main-Regular\.woff2.*injected read failure/,
  );
});

test("asset router records every blocked virtual and HTTP(S) request as failed", async () => {
  const blockedRequests = [
    {
      url: "https://visual-parity.test/unexpected.css",
      key: "visual:https://visual-parity.test/unexpected.css",
    },
    {
      url: "https://cdn.jsdelivr.net/npm/katex@latest/contrib/auto-render.min.js",
      key: "preview:https://cdn.jsdelivr.net/npm/katex@latest/contrib/auto-render.min.js",
    },
    {
      url: "http://unplanned-assets.test/KaTeX_Main-Regular.woff2",
      key: "external:http://unplanned-assets.test/KaTeX_Main-Regular.woff2",
    },
  ];

  for (const { url, key } of blockedRequests) {
    const ledger = {
      attempted: new Set(),
      fulfilled: new Set(),
      failures: new Map(),
    };
    await routeDraftParityRequest({
      request: () => ({ url: () => url }),
      abort: async () => {},
      fulfill: async () => assert.fail(`blocked request was unexpectedly fulfilled: ${url}`),
      continue: async () => assert.fail(`blocked request was unexpectedly continued: ${url}`),
    }, {
      assetLedger: ledger,
      pluginStyles: "",
      katexStyles: "",
    });

    assert.deepEqual([...ledger.attempted], [key]);
    assert.equal(ledger.failures.has(key), true);
    assert.throws(
      () => assertAssetLedgerComplete(ledger),
      (error) => error.message.includes(url),
    );
  }
});

test("KaTeX font signatures come only from nodes with direct painted glyph text", () => {
  const textNode = (textContent) => ({ nodeType: 3, textContent });
  const paintedGlyph = { childNodes: [textNode("  "), textNode("Ω")] };
  const inheritedLayout = { childNodes: [{ nodeType: 1, childNodes: [paintedGlyph] }] };
  const emptyLayout = { childNodes: [] };
  const zeroWidthLayout = { childNodes: [textNode(" \u200b ")] };
  const styles = new Map([
    [paintedGlyph, {
      fontFamily: '"KaTeX_Math", serif',
      fontStyle: "italic",
      fontWeight: "400",
    }],
    [inheritedLayout, {
      fontFamily: '"KaTeX_Main", serif',
      fontStyle: "italic",
      fontWeight: "700",
    }],
    [emptyLayout, {
      fontFamily: '"KaTeX_Main", serif',
      fontStyle: "normal",
      fontWeight: "400",
    }],
    [zeroWidthLayout, {
      fontFamily: '"KaTeX_Size1", serif',
      fontStyle: "normal",
      fontWeight: "400",
    }],
  ]);
  const formula = {
    querySelectorAll: () => [
      inheritedLayout,
      emptyLayout,
      zeroWidthLayout,
      paintedGlyph,
    ],
  };

  const report = collectKatexFontReport([".fixture-formula"], {
    document: {
      querySelector: () => formula,
      fonts: [{
        family: '"KaTeX_Math"',
        style: "italic",
        weight: "400",
        status: "loaded",
      }],
    },
    getComputedStyle: (element) => styles.get(element),
  });

  assert.deepEqual(report.used, [{
    family: "KaTeX_Math",
    style: "italic",
    weight: "400",
  }]);
  assert.deepEqual(report.unloaded, []);
});

test("Preview and Visual Edit preserve production draft parity", async () => {
  const source = await readFile(FIXTURE_PATH, "utf8");
  const { preview, visual } = await renderDraftParity({ source, width: 1200 });

  assert.ok(Math.abs(preview.bodyFontSize - visual.bodyFontSize) <= 1);
  assert.ok(Math.abs(preview.lineHeight - visual.lineHeight) <= 1);
  assert.ok(Math.abs(preview.contentWidth - visual.contentWidth) <= 1);
  assert.ok(Math.abs(preview.inlineMathHeight - visual.inlineMathHeight) <= 1);
  assert.ok(Math.abs(preview.displayMathHeight - visual.displayMathHeight) <= 1);
  assert.equal(preview.softBreakText, SOFT_BREAK_TEXT);
  assert.equal(visual.softBreakText, SOFT_BREAK_TEXT);
  assert.equal(preview.naturalWrapText, NATURAL_WRAP_TEXT);
  assert.equal(visual.naturalWrapText, NATURAL_WRAP_TEXT);
  assert.equal(visual.softBreakContainsBr, false);
  assert.equal(preview.softBreakText, visual.softBreakText);
  assert.equal(preview.softBreakLineCount, visual.softBreakLineCount);
  assert.equal(preview.naturalWrapLineCount, visual.naturalWrapLineCount);
});
