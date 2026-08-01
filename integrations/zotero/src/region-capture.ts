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

export interface RegionSelectionCallbacks {
  /** The drag produced a valid selection; the overlay has already been removed. */
  onComplete(selection: RegionSelection): void;
  /** Escape, or a drag below MIN_REGION_CSS_PX; the overlay has already been removed. */
  onCancel(): void;
}

/**
 * Install a crosshair drag overlay over `host` (the current PDF.js page
 * view). Exactly one callback fires unless the returned disposer runs first:
 * Escape or a too-small drag cancels; mouse-up on a large-enough drag
 * completes with the selection in CSS pixels relative to `host`.
 *
 * The overlay lives inside the Reader's PDF.js iframe document, where the
 * plugin stylesheet is not loaded, so every style must stay inline.
 */
export function startRegionSelection(
  host: HTMLElement,
  callbacks: RegionSelectionCallbacks,
): () => void {
  const doc = host.ownerDocument;
  const overlay = doc.createElement("div");
  overlay.className = "zc-region-overlay";
  overlay.style.cssText =
    "position:absolute;inset:0;z-index:2147483647;cursor:crosshair;background:rgba(0,0,0,0.04)";
  const box = doc.createElement("div");
  box.className = "zc-region-overlay-box";
  box.style.cssText =
    "position:absolute;display:none;border:1px dashed #1a73e8;background:rgba(26,115,232,0.14);pointer-events:none";
  overlay.appendChild(box);
  host.appendChild(overlay);

  let startX = 0;
  let startY = 0;
  let dragging = false;
  let disposed = false;

  const localPoint = (event: MouseEvent): { x: number; y: number } => {
    const bounds = host.getBoundingClientRect();
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
  };

  const paintBox = (rect: RegionRect): void => {
    box.style.display = "block";
    box.style.left = `${rect.x}px`;
    box.style.top = `${rect.y}px`;
    box.style.width = `${rect.width}px`;
    box.style.height = `${rect.height}px`;
  };

  const dispose = (): void => {
    if (disposed) return;
    disposed = true;
    doc.removeEventListener("keydown", onKeyDown, true);
    doc.removeEventListener("mousemove", onMouseMove, true);
    doc.removeEventListener("mouseup", onMouseUp, true);
    overlay.remove();
  };

  const onKeyDown = (event: KeyboardEvent): void => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    dispose();
    callbacks.onCancel();
  };

  const onMouseDown = (event: MouseEvent): void => {
    if (event.button !== 0) return;
    event.preventDefault();
    const point = localPoint(event);
    startX = point.x;
    startY = point.y;
    dragging = true;
    paintBox({ x: startX, y: startY, width: 0, height: 0 });
  };

  const onMouseMove = (event: MouseEvent): void => {
    if (!dragging) return;
    const point = localPoint(event);
    paintBox(normalizeRegionRect(startX, startY, point.x, point.y));
  };

  const onMouseUp = (event: MouseEvent): void => {
    if (!dragging) return;
    dragging = false;
    const point = localPoint(event);
    const rect = normalizeRegionRect(startX, startY, point.x, point.y);
    const bounds = host.getBoundingClientRect();
    dispose();
    if (!meetsMinimumRegionSize(rect)) {
      callbacks.onCancel();
      return;
    }
    callbacks.onComplete({ rect, view: { width: bounds.width, height: bounds.height } });
  };

  overlay.addEventListener("mousedown", onMouseDown);
  doc.addEventListener("keydown", onKeyDown, true);
  doc.addEventListener("mousemove", onMouseMove, true);
  doc.addEventListener("mouseup", onMouseUp, true);
  return dispose;
}
