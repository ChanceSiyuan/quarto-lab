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

import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = path.resolve(HERE, "..", "..");

let browser;

async function sharedBrowser() {
  browser ??= await chromium.launch();
  return browser;
}

export async function closeHarness() {
  await browser?.close();
  browser = undefined;
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
