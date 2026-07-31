// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";

import {
  MIN_REGION_CSS_PX,
  cssRegionToCanvasRegion,
  meetsMinimumRegionSize,
  normalizeRegionRect,
  startRegionSelection,
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

describe("startRegionSelection overlay", () => {
  // happy-dom computes no layout: getBoundingClientRect returns zeros unless
  // stubbed. Stub the page-view host the same way a real 400x600 CSS-pixel
  // PDF.js page at viewport offset (100, 50) would measure.
  function mountHost(): HTMLElement {
    const host = document.createElement("div");
    document.body.appendChild(host);
    host.getBoundingClientRect = () => ({
      left: 100,
      top: 50,
      width: 400,
      height: 600,
      right: 500,
      bottom: 650,
      x: 100,
      y: 50,
      toJSON: () => ({}),
    }) as DOMRect;
    return host;
  }

  it("completes a drag with the selection rect and view size, then removes the overlay", () => {
    const host = mountHost();
    const onComplete = vi.fn();
    const onCancel = vi.fn();
    startRegionSelection(host, { onComplete, onCancel });

    const overlay = host.querySelector<HTMLElement>(".zc-region-overlay")!;
    expect(overlay).not.toBeNull();
    expect(overlay.style.cursor).toBe("crosshair");
    overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 110, clientY: 60, bubbles: true }));
    document.dispatchEvent(new MouseEvent("mousemove", { clientX: 310, clientY: 210, bubbles: true }));
    const box = overlay.querySelector<HTMLElement>(".zc-region-overlay-box")!;
    expect(box.style.display).toBe("block");
    expect(box.style.width).toBe("200px");
    expect(box.style.height).toBe("150px");
    document.dispatchEvent(new MouseEvent("mouseup", { clientX: 310, clientY: 210, bubbles: true }));

    expect(onComplete).toHaveBeenCalledWith({
      rect: { x: 10, y: 10, width: 200, height: 150 },
      view: { width: 400, height: 600 },
    });
    expect(onCancel).not.toHaveBeenCalled();
    expect(host.querySelector(".zc-region-overlay")).toBeNull();
    host.remove();
  });

  it("cancels on Escape without capturing", () => {
    const host = mountHost();
    const onComplete = vi.fn();
    const onCancel = vi.fn();
    startRegionSelection(host, { onComplete, onCancel });
    const overlay = host.querySelector<HTMLElement>(".zc-region-overlay")!;
    overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 120, clientY: 70, bubbles: true }));

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(onComplete).not.toHaveBeenCalled();
    expect(host.querySelector(".zc-region-overlay")).toBeNull();
    host.remove();
  });

  it("discards drags below the minimum size", () => {
    const host = mountHost();
    const onComplete = vi.fn();
    const onCancel = vi.fn();
    startRegionSelection(host, { onComplete, onCancel });
    const overlay = host.querySelector<HTMLElement>(".zc-region-overlay")!;
    overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 110, clientY: 60, bubbles: true }));
    document.dispatchEvent(new MouseEvent("mouseup", { clientX: 114, clientY: 63, bubbles: true }));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(onComplete).not.toHaveBeenCalled();
    expect(host.querySelector(".zc-region-overlay")).toBeNull();
    host.remove();
  });

  it("returns a disposer that removes the overlay without firing callbacks", () => {
    const host = mountHost();
    const onComplete = vi.fn();
    const onCancel = vi.fn();
    const dispose = startRegionSelection(host, { onComplete, onCancel });

    dispose();

    expect(host.querySelector(".zc-region-overlay")).toBeNull();
    expect(onComplete).not.toHaveBeenCalled();
    expect(onCancel).not.toHaveBeenCalled();
    host.remove();
  });
});
