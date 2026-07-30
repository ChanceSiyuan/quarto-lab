/**
 * Layout checks, in a real browser.
 *
 * Run with `npm run test:visual`. Skipped when Chromium is not installed, so a
 * checkout without `npx playwright install chromium` still runs `npm test`.
 */

import assert from "node:assert/strict";
import test, { after } from "node:test";

import { closeHarness, renderSurface } from "./render-harness.mjs";
import { composerWithChips, composerWithContextMenu, workspaceToolbar } from "./surfaces.mjs";

after(() => closeHarness());

const nthOf = (selector, count) =>
  Array.from({ length: count }, (_, index) => `${selector}:nth-of-type(${index + 1})`);

test("every option of a long context menu can be reached by scrolling", async () => {
  const options = nthOf(".zc-context-option", 14);
  const { measurements } = await renderSurface({
    html: composerWithContextMenu(14),
    width: 420,
    height: 620,
    measure: options,
  });

  for (const selector of options) {
    assert.equal(measurements[selector].found, true, `${selector} is missing`);
    assert.equal(
      measurements[selector].clipped,
      false,
      `${selector} cannot be reached even by scrolling; the menu and its list are capping each other`,
    );
  }
});

test("no row of context chips is ever cut through its glyphs", async () => {
  // The reported defect: a raw pixel cap left the last row sliced in half, so
  // its text read as covered up rather than as scrollable.
  for (const count of [3, 11, 16, 24]) {
    const chips = nthOf(".zc-context-chip", count);
    const { measurements } = await renderSurface({
      html: composerWithChips(count),
      width: 420,
      height: 620,
      measure: chips,
    });
    const sliced = chips.filter((selector) => measurements[selector].found && measurements[selector].sliced);
    assert.deepEqual(
      sliced,
      [],
      `with ${count} chips these are cut through: ${sliced.join(", ")}`,
    );
  }
});

test("the preview toolbar keeps every control inside a narrow pane", async () => {
  const { measurements } = await renderSurface({
    html: workspaceToolbar(),
    width: 480,
    height: 640,
    measure: [
      ".zc-qmd-compliance",
      ".zc-qmd-review",
      ".zc-qmd-edit-external",
      ".zc-qmd-refresh",
      ".zc-qmd-tree-badge",
    ],
  });

  for (const selector of [
    ".zc-qmd-compliance",
    ".zc-qmd-review",
    ".zc-qmd-edit-external",
    ".zc-qmd-refresh",
    ".zc-qmd-tree-badge",
  ]) {
    assert.equal(measurements[selector].found, true, `${selector} is missing`);
    assert.equal(
      measurements[selector].clippedRight,
      false,
      `${selector} overflows the toolbar at 480px; the path label must give way first`,
    );
  }
});

test("the preview body consumes the remaining workspace height when compliance details are hidden", async () => {
  const { measurements } = await renderSurface({
    html: workspaceToolbar(),
    width: 760,
    height: 640,
    measure: [".zc-qmd-workspace", ".zc-qmd-toolbar", ".zc-qmd-status", ".zc-qmd-body"],
  });
  const available = measurements[".zc-qmd-workspace"].height
    - measurements[".zc-qmd-toolbar"].height
    - measurements[".zc-qmd-status"].height;
  assert.ok(
    measurements[".zc-qmd-body"].height >= available - 2,
    `preview body leaves ${available - measurements[".zc-qmd-body"].height}px blank below it`,
  );
});
