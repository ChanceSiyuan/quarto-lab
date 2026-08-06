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
      button.addEventListener("click", () => this.layout.activateTab(id));
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

  /** Drag support arrives in the next task; the hook keeps renderBar stable. */
  protected installDragHandlers(_button: HTMLButtonElement, _tabId: string): void {}

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
