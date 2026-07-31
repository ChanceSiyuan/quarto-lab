// @vitest-environment happy-dom

import { describe, expect, it } from "vitest";

import {
  MIN_REGION_CSS_PX,
  cssRegionToCanvasRegion,
  meetsMinimumRegionSize,
  normalizeRegionRect,
} from "../src/region-capture";

describe("region crop geometry", () => {
  it("normalizes any two drag corners into a positive rect", () => {
    expect(normalizeRegionRect(110, 90, 10, 20)).toEqual({ x: 10, y: 20, width: 100, height: 70 });
    expect(normalizeRegionRect(10, 20, 110, 90)).toEqual({ x: 10, y: 20, width: 100, height: 70 });
    expect(normalizeRegionRect(5, 5, 5, 5)).toEqual({ x: 5, y: 5, width: 0, height: 0 });
  });

  it("rejects drags below the minimum size on either axis", () => {
    expect(meetsMinimumRegionSize({ x: 0, y: 0, width: MIN_REGION_CSS_PX, height: MIN_REGION_CSS_PX })).toBe(true);
    expect(meetsMinimumRegionSize({ x: 0, y: 0, width: MIN_REGION_CSS_PX - 1, height: 100 })).toBe(false);
    expect(meetsMinimumRegionSize({ x: 0, y: 0, width: 100, height: MIN_REGION_CSS_PX - 1 })).toBe(false);
  });

  it("scales a CSS-pixel selection to canvas device pixels", () => {
    expect(cssRegionToCanvasRegion(
      { rect: { x: 30, y: 40, width: 120, height: 60 }, view: { width: 300, height: 400 } },
      { width: 600, height: 800 },
    )).toEqual({ x: 60, y: 80, width: 240, height: 120 });
  });

  it("clamps a selection that overhangs the page to the canvas bounds", () => {
    expect(cssRegionToCanvasRegion(
      { rect: { x: -20, y: -10, width: 340, height: 430 }, view: { width: 300, height: 400 } },
      { width: 600, height: 800 },
    )).toEqual({ x: 0, y: 0, width: 600, height: 800 });
  });

  it("returns null for selections fully outside the page", () => {
    expect(cssRegionToCanvasRegion(
      { rect: { x: 400, y: 500, width: 50, height: 50 }, view: { width: 300, height: 400 } },
      { width: 600, height: 800 },
    )).toBeNull();
  });

  it("returns null for degenerate views and sub-pixel selections", () => {
    expect(cssRegionToCanvasRegion(
      { rect: { x: 0, y: 0, width: 10, height: 10 }, view: { width: 0, height: 0 } },
      { width: 600, height: 800 },
    )).toBeNull();
    expect(cssRegionToCanvasRegion(
      { rect: { x: 10, y: 10, width: 0.1, height: 0.1 }, view: { width: 300, height: 400 } },
      { width: 600, height: 800 },
    )).toBeNull();
  });
});
