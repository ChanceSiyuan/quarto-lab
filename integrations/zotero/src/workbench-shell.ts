/**
 * DOM shell for the tabbed workbench: renders one tab bar per pane, hosts tab
 * content, and owns the split handle.
 *
 * Content hosts are created once and never moved in the DOM afterwards — a
 * XUL <browser> (main site, Quarto previews) or an embedded reader reloads
 * from scratch when reparented, so pane membership and visibility are
 * expressed purely through CSS classes on stable sibling elements.
 */

import {
  WorkbenchLayout,
  type PaneId,
  type TabDescriptor,
  type TabKind,
} from "./workbench-layout";

export interface TabContentProvider {
  /** Called once, lazily, the first time the tab becomes active. */
  mount(host: HTMLElement): void;
  show(): void;
  hide(): void;
  dispose(): void;
  focus?(): void;
}

export type ProviderFactory = (tab: TabDescriptor) => TabContentProvider;

/**
 * Where a dragged tab would land: a bar slot (`pane` + `index`), a pane's
 * content area (`pane` alone, appended), or a new right pane (`split`).
 */
export type DropTarget = { pane: PaneId; index?: number } | { split: "right" };

const DRAG_THRESHOLD_PX = 4;
/** Fraction of the single-pane content width that acts as a split edge. */
const SPLIT_EDGE_FRACTION = 0.2;

export interface WorkbenchShellOptions {
  initialSplitRatio: number;
  onSplitRatioChange(ratio: number): void;
  onLayoutChange(): void;
  /** Returning false vetoes the close (e.g. a dirty editor). */
  onCloseRequested?(tab: TabDescriptor): boolean;
}

/** The left pane never shrinks past a quarter or grows past two thirds. */
export function clampSplitRatio(percent: number): number {
  if (!Number.isFinite(percent)) return 40;
  return Math.round(Math.min(68, Math.max(25, percent)));
}

interface TabEntry {
  provider: TabContentProvider;
  host: HTMLElement;
  mounted: boolean;
  visible: boolean;
  retain: boolean;
}

export class WorkbenchShell {
  readonly root: HTMLElement;
  readonly layout: WorkbenchLayout;

  private readonly doc: Document;
  private readonly options: WorkbenchShellOptions;
  private readonly factories = new Map<TabKind, { factory: ProviderFactory; retainOnClose: boolean }>();
  private readonly entries = new Map<string, TabEntry>();
  private readonly bars: Record<PaneId, HTMLElement>;
  private readonly emptyState: HTMLElement;
  private readonly dockEl: HTMLElement;
  private readonly dropIndicator: HTMLElement;
  private readonly splitHandle: HTMLButtonElement;
  private splitRatio: number;
  private syncing = false;
  private suppressClick = false;

  constructor(host: HTMLElement, doc: Document, options: WorkbenchShellOptions) {
    this.doc = doc;
    this.options = options;
    this.splitRatio = clampSplitRatio(options.initialSplitRatio);
    this.layout = new WorkbenchLayout(() => {
      this.sync();
      this.options.onLayoutChange();
    });

    this.root = doc.createElement("section");
    this.root.className = "zc-workbench-shell";
    this.root.setAttribute("data-split", "false");
    this.root.style.setProperty("--zc-split-ratio", `${this.splitRatio}%`);

    this.bars = {
      left: this.buildBar("left"),
      right: this.buildBar("right"),
    };
    this.bars.right.hidden = true;

    this.splitHandle = doc.createElement("button");
    this.splitHandle.type = "button";
    this.splitHandle.className = "zc-split-handle";
    this.splitHandle.setAttribute("aria-label", "Resize the workbench panes");
    this.splitHandle.addEventListener("mousedown", (event) => this.beginSplitDrag(event));

    this.emptyState = doc.createElement("div");
    this.emptyState.className = "zc-shell-empty";
    this.emptyState.textContent = "All tabs are closed — open a paper or press ⌘I to start a chat.";

    this.dockEl = doc.createElement("div");
    this.dockEl.className = "zc-top-actions zc-workbench-dock";
    this.dockEl.setAttribute("aria-label", "Workbench tools");

    this.dropIndicator = doc.createElement("div");
    this.dropIndicator.className = "zc-drop-indicator";
    this.dropIndicator.hidden = true;

    this.root.append(
      this.bars.left,
      this.bars.right,
      this.splitHandle,
      this.emptyState,
      this.dockEl,
      this.dropIndicator,
    );
    host.appendChild(this.root);
  }

  registerFactory(
    kind: TabKind,
    factory: ProviderFactory,
    opts: { retainOnClose?: boolean } = {},
  ): void {
    this.factories.set(kind, { factory, retainOnClose: Boolean(opts.retainOnClose) });
  }

  contentHost(tabId: string): HTMLElement | null {
    const entry = this.entries.get(tabId);
    if (!entry) return null;
    // A retained entry whose tab is closed still exists but is not reachable
    // as content; expose it anyway only while its tab is open.
    return this.layout.tab(tabId) ? entry.host : entry.retain ? entry.host : null;
  }

  provider(tabId: string): TabContentProvider | null {
    return this.entries.get(tabId)?.provider || null;
  }

  dock(): HTMLElement {
    return this.dockEl;
  }

  /** Reconciles the DOM with the current layout snapshot. Idempotent. */
  sync(): void {
    if (this.syncing) return;
    this.syncing = true;
    try {
      const snapshot = this.layout.snapshot();
      const split = snapshot.panes.right !== null;
      this.root.setAttribute("data-split", String(split));
      this.bars.right.hidden = !split;

      this.renderBar("left", snapshot.panes.left.tabIds, snapshot.panes.left.activeTabId);
      this.renderBar(
        "right",
        snapshot.panes.right?.tabIds || [],
        snapshot.panes.right?.activeTabId || null,
      );

      const openIds = new Set([
        ...snapshot.panes.left.tabIds,
        ...(snapshot.panes.right?.tabIds || []),
      ]);

      // Retire entries whose tabs are gone.
      for (const [id, entry] of [...this.entries]) {
        if (openIds.has(id)) continue;
        if (entry.retain) {
          this.setEntryVisible(id, entry, false);
        }
        else {
          entry.provider.dispose();
          entry.host.remove();
          this.entries.delete(id);
        }
      }

      // Create/mount/show the active tab of each pane; hide the rest.
      for (const id of openIds) {
        const tab = this.layout.tab(id);
        if (!tab) continue;
        const pane = this.layout.paneOf(id);
        const isActive = pane !== null
          && (pane === "left"
            ? snapshot.panes.left.activeTabId === id
            : snapshot.panes.right?.activeTabId === id);
        let entry = this.entries.get(id);
        if (!entry && isActive) entry = this.createEntry(tab);
        if (!entry) continue;
        entry.host.classList.toggle("is-right", pane === "right");
        if (isActive && !entry.mounted) {
          entry.provider.mount(entry.host);
          entry.mounted = true;
        }
        this.setEntryVisible(id, entry, Boolean(isActive));
      }

      this.emptyState.hidden = openIds.size > 0;
    }
    finally {
      this.syncing = false;
    }
  }

  dispose(): void {
    for (const entry of this.entries.values()) {
      entry.provider.dispose();
      entry.host.remove();
    }
    this.entries.clear();
    this.root.remove();
  }

  private createEntry(tab: TabDescriptor): TabEntry {
    const host = this.doc.createElement("section");
    host.className = "zc-tab-content";
    host.setAttribute("data-tab-id", tab.id);
    // Insert before the dock so overlay children stay on top in DOM order.
    this.root.insertBefore(host, this.dockEl);
    const registration = this.factories.get(tab.kind);
    if (!registration) throw new Error(`No content factory for tab kind "${tab.kind}"`);
    const entry: TabEntry = {
      provider: registration.factory(tab),
      host,
      mounted: false,
      visible: false,
      retain: registration.retainOnClose,
    };
    this.entries.set(tab.id, entry);
    return entry;
  }

  private setEntryVisible(id: string, entry: TabEntry, visible: boolean): void {
    if (entry.visible === visible) return;
    entry.visible = visible;
    entry.host.classList.toggle("is-active", visible);
    if (!entry.mounted) return;
    if (visible) entry.provider.show();
    else entry.provider.hide();
  }

  private buildBar(pane: PaneId): HTMLElement {
    const bar = this.doc.createElement("div");
    bar.className = "zc-pane-bar";
    bar.setAttribute("data-pane", pane);
    bar.setAttribute("role", "tablist");
    return bar;
  }

  private renderBar(pane: PaneId, tabIds: string[], activeTabId: string | null): void {
    const bar = this.bars[pane];
    bar.textContent = "";
    for (const id of tabIds) {
      const tab = this.layout.tab(id);
      if (!tab) continue;
      const button = this.doc.createElement("button");
      button.type = "button";
      button.className = "zc-shell-tab";
      button.setAttribute("data-tab-id", id);
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", String(id === activeTabId));
      button.classList.toggle("is-active", id === activeTabId);
      button.title = tab.title;
      const label = this.doc.createElement("span");
      label.className = "zc-shell-tab-label";
      label.textContent = tab.title;
      const close = this.doc.createElement("span");
      close.className = "zc-shell-tab-close";
      close.setAttribute("role", "button");
      close.setAttribute("aria-label", `Close ${tab.title}`);
      close.textContent = "×";
      close.addEventListener("click", (event) => {
        event.stopPropagation();
        this.requestClose(id);
      });
      button.append(label, close);
      button.addEventListener("click", () => {
        if (this.suppressClick) {
          this.suppressClick = false;
          return;
        }
        this.layout.activateTab(id);
      });
      this.installDragHandlers(button, id);
      bar.appendChild(button);
    }
  }

  private requestClose(id: string): void {
    const tab = this.layout.tab(id);
    if (!tab) return;
    if (this.options.onCloseRequested && !this.options.onCloseRequested(tab)) return;
    this.layout.closeTab(id);
  }

  /**
   * Resolves pointer coordinates to a drop target. Bars win over content;
   * in single-pane mode the right 20% of the content area creates the split,
   * the left 20% reorders to the front, and the middle appends in place.
   */
  dropTargetAt(x: number, y: number): DropTarget | null {
    const rootRect = this.root.getBoundingClientRect();
    if (x < rootRect.left || x > rootRect.right || y < rootRect.top || y > rootRect.bottom) {
      return null;
    }
    const split = this.layout.snapshot().panes.right !== null;
    for (const pane of ["left", "right"] as const) {
      if (pane === "right" && !split) continue;
      const rect = this.bars[pane].getBoundingClientRect();
      if (rect.width > 0 && y >= rect.top && y <= rect.bottom
        && x >= rect.left && x <= rect.right) {
        return { pane, index: this.insertionIndex(this.bars[pane], x) };
      }
    }
    if (split) {
      const boundary = rootRect.left + (rootRect.width * this.splitRatio) / 100;
      return { pane: x < boundary ? "left" : "right" };
    }
    if (x >= rootRect.left + rootRect.width * (1 - SPLIT_EDGE_FRACTION)) return { split: "right" };
    if (x <= rootRect.left + rootRect.width * SPLIT_EDGE_FRACTION) return { pane: "left", index: 0 };
    return { pane: "left" };
  }

  private insertionIndex(bar: HTMLElement, x: number): number {
    let index = 0;
    for (const button of bar.querySelectorAll(".zc-shell-tab")) {
      const rect = (button as HTMLElement).getBoundingClientRect();
      if (x > rect.left + rect.width / 2) index++;
    }
    return index;
  }

  private installDragHandlers(button: HTMLButtonElement, tabId: string): void {
    button.addEventListener("pointerdown", (event) => {
      if ((event.target as HTMLElement | null)?.closest?.(".zc-shell-tab-close")) return;
      this.armDrag(button, tabId, event as PointerEvent);
    });
  }

  private armDrag(button: HTMLButtonElement, tabId: string, down: PointerEvent): void {
    const view = this.doc.defaultView;
    if (!view) return;
    if (typeof down.pointerId === "number" && typeof button.setPointerCapture === "function") {
      try { button.setPointerCapture(down.pointerId); }
      catch { /* capture is an optimization, not a requirement */ }
    }
    const startX = down.clientX;
    const startY = down.clientY;
    let dragging = false;
    const onMove = (event: PointerEvent) => {
      if (!dragging
        && Math.hypot(event.clientX - startX, event.clientY - startY) <= DRAG_THRESHOLD_PX) {
        return;
      }
      dragging = true;
      button.classList.add("is-dragging");
      this.showDropIndicator(this.dropTargetAt(event.clientX, event.clientY));
    };
    const cleanup = () => {
      dragging = false;
      button.classList.remove("is-dragging");
      this.dropIndicator.hidden = true;
      view.removeEventListener("pointermove", onMove as EventListener, true);
      view.removeEventListener("pointerup", onUp as EventListener, true);
      view.removeEventListener("pointercancel", onCancel, true);
      view.removeEventListener("keydown", onKey as EventListener, true);
    };
    const onUp = (event: PointerEvent) => {
      const completed = dragging;
      cleanup();
      if (!completed) return;
      this.suppressClick = true;
      const target = this.dropTargetAt(event.clientX, event.clientY);
      if (!target) return;
      if ("split" in target) this.layout.moveTab(tabId, "right");
      else this.layout.moveTab(tabId, target.pane, target.index);
    };
    const onCancel = () => cleanup();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") cleanup();
    };
    view.addEventListener("pointermove", onMove as EventListener, true);
    view.addEventListener("pointerup", onUp as EventListener, true);
    view.addEventListener("pointercancel", onCancel, true);
    view.addEventListener("keydown", onKey as EventListener, true);
  }

  private showDropIndicator(target: DropTarget | null): void {
    if (!target) {
      this.dropIndicator.hidden = true;
      return;
    }
    const rootRect = this.root.getBoundingClientRect();
    const barBottom = Math.max(0, this.bars.left.getBoundingClientRect().bottom - rootRect.top);
    let left = 0;
    let top = barBottom;
    let width = rootRect.width;
    let height = Math.max(0, rootRect.height - barBottom);
    if ("split" in target) {
      left = rootRect.width / 2;
      width = rootRect.width / 2;
    }
    else if (target.index !== undefined) {
      // Thin insertion slot inside the bar at the insertion point.
      const bar = this.bars[target.pane];
      const barRect = bar.getBoundingClientRect();
      const buttons = bar.querySelectorAll(".zc-shell-tab");
      const at = buttons[target.index] as HTMLElement | undefined;
      const slotX = at
        ? at.getBoundingClientRect().left - rootRect.left
        : (buttons.length
          ? (buttons[buttons.length - 1] as HTMLElement).getBoundingClientRect().right - rootRect.left
          : barRect.left - rootRect.left + 4);
      left = Math.max(0, slotX - 1.5);
      top = Math.max(0, barRect.top - rootRect.top);
      width = 3;
      height = Math.max(0, barRect.height);
    }
    else if (this.layout.snapshot().panes.right !== null) {
      const boundary = (rootRect.width * this.splitRatio) / 100;
      left = target.pane === "left" ? 0 : boundary;
      width = target.pane === "left" ? boundary : rootRect.width - boundary;
    }
    this.dropIndicator.style.left = `${left}px`;
    this.dropIndicator.style.top = `${top}px`;
    this.dropIndicator.style.width = `${width}px`;
    this.dropIndicator.style.height = `${height}px`;
    this.dropIndicator.hidden = false;
  }

  private beginSplitDrag(event: MouseEvent): void {
    event.preventDefault();
    const view = this.doc.defaultView;
    if (!view) return;
    this.splitHandle.classList.add("is-dragging");
    const onMove = (moved: MouseEvent) => {
      const bounds = this.root.getBoundingClientRect();
      if (bounds.width <= 0) return;
      this.applySplitRatio(((moved.clientX - bounds.left) / bounds.width) * 100);
    };
    const onUp = () => {
      this.splitHandle.classList.remove("is-dragging");
      view.removeEventListener("mousemove", onMove, true);
      view.removeEventListener("mouseup", onUp, true);
      this.options.onSplitRatioChange(this.splitRatio);
    };
    view.addEventListener("mousemove", onMove, true);
    view.addEventListener("mouseup", onUp, true);
  }

  private applySplitRatio(percent: number): void {
    this.splitRatio = clampSplitRatio(percent);
    this.root.style.setProperty("--zc-split-ratio", `${this.splitRatio}%`);
  }
}
