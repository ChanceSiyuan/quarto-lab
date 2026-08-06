/**
 * Pure layout state for the tabbed workbench: which tabs exist, which of the
 * (at most two) panes each lives in, and which tab is active per pane.
 *
 * The model is DOM-free so every rule — singleton reuse, pane dissolution,
 * arrangement idempotence, tolerant session restore — is unit-testable
 * without a Zotero window. The DOM shell subscribes through `onChange`.
 */

export type TabKind = "chat" | "editor" | "site" | "pdf";
export type PaneId = "left" | "right";

export interface PdfTabPayload {
  itemID: number;
  attachmentKey: string;
  page?: number;
}

export interface TabDescriptor {
  id: string;
  kind: TabKind;
  title: string;
  payload?: PdfTabPayload;
}

export type TabRequest =
  | { kind: "chat" | "editor" | "site"; title?: string }
  | { kind: "pdf"; title: string; payload: PdfTabPayload };

export interface PaneSnapshot {
  tabIds: string[];
  activeTabId: string | null;
}

export interface LayoutSnapshot {
  panes: { left: PaneSnapshot; right: PaneSnapshot | null };
  focusedPane: PaneId;
}

export interface SerializedLayout {
  version: 1;
  tabs: Array<{ id: string; kind: string; title: string; payload?: unknown }>;
  panes: { left: PaneSnapshot; right: PaneSnapshot | null };
  focusedPane: PaneId;
}

const SINGLETON_KINDS = new Set<TabKind>(["chat", "editor", "site"]);
const ALL_KINDS = new Set<TabKind>(["chat", "editor", "site", "pdf"]);

const DEFAULT_TITLES: Record<"chat" | "editor" | "site", string> = {
  chat: "Chat",
  editor: "Editor",
  site: "Main Site",
};

export function tabIdFor(request: TabRequest): string {
  return request.kind === "pdf" ? `pdf:${request.payload.attachmentKey}` : request.kind;
}

interface Pane {
  tabIds: string[];
  activeTabId: string | null;
}

export class WorkbenchLayout {
  private tabMap = new Map<string, TabDescriptor>();
  private left: Pane = { tabIds: [], activeTabId: null };
  private right: Pane | null = null;
  private focused: PaneId = "left";

  constructor(private readonly onChange: () => void) {}

  snapshot(): LayoutSnapshot {
    return {
      panes: {
        left: { tabIds: [...this.left.tabIds], activeTabId: this.left.activeTabId },
        right: this.right
          ? { tabIds: [...this.right.tabIds], activeTabId: this.right.activeTabId }
          : null,
      },
      focusedPane: this.focused,
    };
  }

  tabs(): TabDescriptor[] {
    return [...this.tabMap.values()];
  }

  tab(id: string): TabDescriptor | null {
    return this.tabMap.get(id) || null;
  }

  paneOf(id: string): PaneId | null {
    if (this.left.tabIds.includes(id)) return "left";
    if (this.right?.tabIds.includes(id)) return "right";
    return null;
  }

  openTab(request: TabRequest, pane?: PaneId): string {
    const id = tabIdFor(request);
    this.mutate(() => {
      const existing = this.tabMap.get(id);
      if (existing) {
        this.applyRequest(existing, request);
        this.activateInPlace(id);
        return;
      }
      const descriptor: TabDescriptor = {
        id,
        kind: request.kind,
        title: request.kind === "pdf"
          ? request.title
          : request.title || DEFAULT_TITLES[request.kind],
        ...(request.kind === "pdf" ? { payload: { ...request.payload } } : {}),
      };
      this.tabMap.set(id, descriptor);
      const target = this.paneFor(pane ?? this.focused);
      target.tabIds.push(id);
      target.activeTabId = id;
      this.focused = target === this.left ? "left" : "right";
    });
    return id;
  }

  closeTab(id: string): void {
    this.mutate(() => {
      if (!this.tabMap.has(id)) return;
      this.tabMap.delete(id);
      this.removeFromPanes(id);
      this.normalize();
    });
  }

  activateTab(id: string): void {
    this.mutate(() => {
      if (!this.tabMap.has(id)) return;
      this.activateInPlace(id);
    });
  }

  moveTab(id: string, pane: PaneId, index?: number): void {
    this.mutate(() => {
      if (!this.tabMap.has(id)) return;
      this.removeFromPanes(id);
      if (pane === "right" && !this.right) this.right = { tabIds: [], activeTabId: null };
      const target = this.paneFor(pane);
      const at = index === undefined
        ? target.tabIds.length
        : Math.max(0, Math.min(index, target.tabIds.length));
      target.tabIds.splice(at, 0, id);
      target.activeTabId = id;
      this.focused = pane === "right" && this.right ? "right" : "left";
      this.normalize();
    });
  }

  arrange(left: TabRequest, right: TabRequest): void {
    this.mutate(() => {
      const leftId = this.ensureTab(left);
      const rightId = this.ensureTab(right);
      if (leftId === rightId) {
        this.activateInPlace(leftId);
        this.focused = "left";
        return;
      }
      if (this.paneOf(leftId) !== "left") {
        this.removeFromPanes(leftId);
        this.left.tabIds.push(leftId);
      }
      if (!this.right) this.right = { tabIds: [], activeTabId: null };
      if (this.paneOf(rightId) !== "right") {
        this.removeFromPanes(rightId);
        this.right.tabIds.push(rightId);
      }
      this.left.activeTabId = leftId;
      this.right.activeTabId = rightId;
      this.focused = "left";
      this.normalize();
    });
  }

  updatePdfPage(id: string, page: number): void {
    this.mutate(() => {
      const tab = this.tabMap.get(id);
      if (tab?.kind !== "pdf" || !tab.payload) return;
      tab.payload.page = page;
    });
  }

  serialize(): SerializedLayout {
    return {
      version: 1,
      tabs: this.tabs().map((tab) => ({
        id: tab.id,
        kind: tab.kind,
        title: tab.title,
        ...(tab.payload ? { payload: { ...tab.payload } } : {}),
      })),
      ...this.snapshot(),
    };
  }

  restore(data: unknown): void {
    this.mutate(() => {
      this.tabMap = new Map();
      this.left = { tabIds: [], activeTabId: null };
      this.right = null;
      this.focused = "left";
      const raw = data as Partial<SerializedLayout> | null;
      if (!raw || typeof raw !== "object" || !Array.isArray(raw.tabs)) return;
      for (const entry of raw.tabs) {
        const tab = this.reviveTab(entry);
        if (tab && !this.tabMap.has(tab.id)) this.tabMap.set(tab.id, tab);
      }
      const panes = raw.panes;
      this.left = this.revivePane(panes?.left) || { tabIds: [], activeTabId: null };
      this.right = this.revivePane(panes?.right ?? null);
      // A tab the panes forgot would be unreachable; give it a home instead.
      for (const id of this.tabMap.keys()) {
        if (!this.paneOf(id)) this.left.tabIds.push(id);
      }
      if (raw.focusedPane === "right" || raw.focusedPane === "left") this.focused = raw.focusedPane;
      this.normalize();
    });
  }

  private reviveTab(entry: unknown): TabDescriptor | null {
    const raw = entry as { id?: unknown; kind?: unknown; title?: unknown; payload?: unknown } | null;
    if (!raw || typeof raw !== "object") return null;
    const kind = raw.kind as TabKind;
    if (!ALL_KINDS.has(kind)) return null;
    const title = typeof raw.title === "string" && raw.title ? raw.title : null;
    if (kind !== "pdf") {
      return { id: kind, kind, title: title || DEFAULT_TITLES[kind] };
    }
    const payload = raw.payload as Partial<PdfTabPayload> | null;
    if (!payload || typeof payload !== "object") return null;
    const attachmentKey = typeof payload.attachmentKey === "string" ? payload.attachmentKey : "";
    const itemID = typeof payload.itemID === "number" && Number.isFinite(payload.itemID)
      ? payload.itemID
      : null;
    if (!attachmentKey || itemID === null || !title) return null;
    const page = typeof payload.page === "number" && Number.isFinite(payload.page)
      ? payload.page
      : undefined;
    return {
      id: `pdf:${attachmentKey}`,
      kind,
      title,
      payload: { itemID, attachmentKey, ...(page === undefined ? {} : { page }) },
    };
  }

  private revivePane(raw: unknown): Pane | null {
    const pane = raw as Partial<PaneSnapshot> | null;
    if (!pane || typeof pane !== "object" || !Array.isArray(pane.tabIds)) return null;
    const tabIds = pane.tabIds.filter((id): id is string =>
      typeof id === "string" && this.tabMap.has(id) && !this.paneOf(id));
    const activeTabId = typeof pane.activeTabId === "string" && tabIds.includes(pane.activeTabId)
      ? pane.activeTabId
      : tabIds.at(-1) ?? null;
    return { tabIds, activeTabId };
  }

  private applyRequest(tab: TabDescriptor, request: TabRequest): void {
    if (request.kind === "pdf") {
      tab.title = request.title;
      tab.payload = { ...request.payload };
    }
    else if (request.title) {
      tab.title = request.title;
    }
  }

  private ensureTab(request: TabRequest): string {
    const id = tabIdFor(request);
    const existing = this.tabMap.get(id);
    if (existing) {
      this.applyRequest(existing, request);
      return id;
    }
    const descriptor: TabDescriptor = {
      id,
      kind: request.kind,
      title: request.kind === "pdf"
        ? request.title
        : request.title || DEFAULT_TITLES[request.kind],
      ...(request.kind === "pdf" ? { payload: { ...request.payload } } : {}),
    };
    this.tabMap.set(id, descriptor);
    this.left.tabIds.push(id);
    return id;
  }

  private activateInPlace(id: string): void {
    const pane = this.paneOf(id);
    if (!pane) return;
    this.paneFor(pane).activeTabId = id;
    this.focused = pane;
  }

  private paneFor(pane: PaneId): Pane {
    return pane === "right" && this.right ? this.right : this.left;
  }

  private removeFromPanes(id: string): void {
    for (const pane of [this.left, this.right]) {
      if (!pane) continue;
      const index = pane.tabIds.indexOf(id);
      if (index < 0) continue;
      pane.tabIds.splice(index, 1);
      if (pane.activeTabId === id) pane.activeTabId = pane.tabIds.at(-1) ?? null;
    }
  }

  /** Dissolves empty panes: right collapses away, an empty left adopts right. */
  private normalize(): void {
    if (this.right && !this.right.tabIds.length) this.right = null;
    if (!this.left.tabIds.length && this.right) {
      this.left = this.right;
      this.right = null;
    }
    for (const pane of [this.left, this.right]) {
      if (!pane) continue;
      if (pane.activeTabId && !pane.tabIds.includes(pane.activeTabId)) {
        pane.activeTabId = pane.tabIds.at(-1) ?? null;
      }
      if (!pane.activeTabId && pane.tabIds.length) pane.activeTabId = pane.tabIds.at(-1)!;
    }
    if (this.focused === "right" && !this.right) this.focused = "left";
  }

  /** Runs a mutation and fires onChange exactly once, only on real change. */
  private mutate(apply: () => void): void {
    const before = JSON.stringify(this.serialize());
    apply();
    if (JSON.stringify(this.serialize()) !== before) this.onChange();
  }
}
