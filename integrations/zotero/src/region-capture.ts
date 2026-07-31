/**
 * Region-screenshot geometry and drag overlay (Fix Pack A, Design 3).
 *
 * The geometry half is pure so crop math unit-tests without a DOM: the
 * overlay reports a drag rect in CSS pixels relative to the PDF.js page
 * view, and the Zotero adapter converts it to device pixels on the page
 * canvas it renders (scale 1.5, clamped to 2400x3200 — see capturePdfPage
 * in reader-context.ts).
 */

export interface RegionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface RegionSize {
  width: number;
  height: number;
}

/** A completed drag: CSS-pixel rect relative to the page view, plus that view's CSS size. */
export interface RegionSelection {
  rect: RegionRect;
  view: RegionSize;
}

/** Drags smaller than this on either axis (CSS px) are discarded as accidental clicks. */
export const MIN_REGION_CSS_PX = 8;

/** Order two drag corners into a rect with non-negative width and height. */
export function normalizeRegionRect(x1: number, y1: number, x2: number, y2: number): RegionRect {
  return {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    width: Math.abs(x2 - x1),
    height: Math.abs(y2 - y1),
  };
}

export function meetsMinimumRegionSize(rect: RegionRect, minimum = MIN_REGION_CSS_PX): boolean {
  return rect.width >= minimum && rect.height >= minimum;
}

/**
 * Convert a CSS-pixel selection on the page view into device pixels on the
 * rendered page canvas, clamped to the canvas bounds. Returns null when the
 * view is degenerate or the clamped selection has no visible pixels.
 */
export function cssRegionToCanvasRegion(
  selection: RegionSelection,
  canvas: RegionSize,
): RegionRect | null {
  const { rect, view } = selection;
  if (!(view.width > 0) || !(view.height > 0)) return null;
  if (!(canvas.width > 0) || !(canvas.height > 0)) return null;
  const scaleX = canvas.width / view.width;
  const scaleY = canvas.height / view.height;
  const left = Math.max(0, Math.round(rect.x * scaleX));
  const top = Math.max(0, Math.round(rect.y * scaleY));
  const right = Math.min(canvas.width, Math.round((rect.x + rect.width) * scaleX));
  const bottom = Math.min(canvas.height, Math.round((rect.y + rect.height) * scaleY));
  const width = right - left;
  const height = bottom - top;
  if (width < 1 || height < 1) return null;
  return { x: left, y: top, width, height };
}
