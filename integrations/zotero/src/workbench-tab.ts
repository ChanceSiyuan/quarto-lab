import type { QmdWorkspaceView } from "./qmd-workspace";

export const QLAB_WORKBENCH_TAB_TYPE = "qlab";
export const QLAB_WORKBENCH_TAB_ICON = "qlabChat";
export const QLAB_WORKBENCH_WINDOW_ATTRIBUTE = "data-qlab-workbench-window";

/** True for a Zotero main window reserved for a moved QLab Workbench tab. */
export function isDedicatedWorkbenchWindow(win: Window | null | undefined): boolean {
  return win?.document?.documentElement?.getAttribute(QLAB_WORKBENCH_WINDOW_ATTRIBUTE) === "true";
}

export interface WorkbenchTabData {
  itemID?: number | string;
  icon?: string;
  title: string;
  /** Serialized pane/tab layout (see workbench-layout.ts); opaque here. */
  layout?: unknown;
}

export interface WorkbenchTabView {
  show(): void;
  destroy(): void;
  focusComposer(text?: string): void;
  setState(next: any): void;
  layoutData?(): unknown;
  setLayoutData?(data: unknown): void;
  workspace?(): QmdWorkspaceView | null;
}

/** The layout equivalent of the retired `mainSiteOpen` flag: chat | site. */
const LEGACY_MAIN_SITE_LAYOUT = {
  version: 1,
  tabs: [
    { id: "chat", kind: "chat", title: "Chat" },
    { id: "site", kind: "site", title: "Main Site" },
  ],
  panes: {
    left: { tabIds: ["chat"], activeTabId: "chat" },
    right: { tabIds: ["site"], activeTabId: "site" },
  },
  focusedPane: "left",
} as const;

export interface WorkbenchTabEntry {
  id: string;
  host: HTMLElement;
  view: WorkbenchTabView;
  data: WorkbenchTabData;
}

interface WorkbenchTabOptions {
  forceNew?: boolean;
  index?: number;
  select?: boolean;
}

interface WorkbenchTabManagerCallbacks {
  createView(host: HTMLElement, win: Window, tabID: string): WorkbenchTabView;
  openNewWindow(source: Window): Promise<Window>;
  onMoveComplete?(source: Window, target: Window): void;
  onMoveError?(error: Error, source: Window): void;
}

const HOOK_ACTIONS = [
  "focusFirst",
  "refocus",
  "duplicate",
  "restoreState",
  "undoClose",
  "getTitle",
  "moveToNewWindow",
] as const;

type HookAction = (typeof HOOK_ACTIONS)[number];

/**
 * Owns QLab's full-size views inside Zotero's native `Zotero_Tabs` deck.
 * The deck itself supplies tab selection, drag-to-reorder, middle-click close,
 * close-other-tabs, and the standard tab menu. These hooks fill in the
 * content-specific behaviours that Zotero normally supplies for PDF readers.
 */
export class WorkbenchTabManager {
  private readonly windowEntries = new Map<Window, Map<string, WorkbenchTabEntry>>();
  private readonly installedHooks = new Map<Window, Partial<Record<HookAction, Function>>>();

  constructor(private readonly callbacks: WorkbenchTabManagerCallbacks) {}

  install(win: Window): void {
    const tabs = win.Zotero_Tabs;
    if (!tabs?.tabHooks || this.installedHooks.has(win)) return;

    const hooks: Partial<Record<HookAction, Function>> = {
      focusFirst: (tab: { id: string }) => this.entry(win, tab.id)?.view.focusComposer(),
      refocus: (tab: { id: string }) => this.entry(win, tab.id)?.view.focusComposer(),
      duplicate: (tab: any, tabIndex: number) => {
        this.open(win, this.dataFromTab(tab), { forceNew: true, index: tabIndex + 1 });
      },
      restoreState: (tab: any, tabIndex: number) => {
        const data = this.dataFromTab(tab);
        this.open(win, data, {
          forceNew: true,
          index: Math.max(1, tabIndex),
          select: Boolean(tab.selected),
        });
        return data.itemID === undefined ? {} : { itemID: data.itemID };
      },
      undoClose: (tab: any, tabIndex: number) => {
        this.open(win, this.dataFromTab(tab), {
          forceNew: true,
          index: Math.max(1, tabIndex),
          select: true,
        });
        return true;
      },
      getTitle: (tab: any) => this.dataFromTab(tab).title,
      moveToNewWindow: async (tab: any) => {
        try {
          const sourceEntry = this.entry(win, String(tab.id));
          const tabData = this.dataFromTab(tab);
          const data = {
            ...tabData,
            layout: sourceEntry?.view.layoutData?.() ?? tabData.layout,
          };
          const target = await this.callbacks.openNewWindow(win);
          this.install(target);
          this.open(target, data, { forceNew: true, select: true });
          win.Zotero_Tabs?.close?.(tab.id);
          this.callbacks.onMoveComplete?.(win, target);
        }
        catch (error) {
          this.callbacks.onMoveError?.(
            error instanceof Error ? error : new Error(String(error)),
            win,
          );
        }
      },
    };

    for (const action of HOOK_ACTIONS) {
      tabs.tabHooks[action] ||= {};
      tabs.tabHooks[action][QLAB_WORKBENCH_TAB_TYPE] = hooks[action];
    }
    this.installedHooks.set(win, hooks);
  }

  uninstall(win: Window, closeTabs = false): void {
    const tabs = win.Zotero_Tabs;
    const hooks = this.installedHooks.get(win);
    if (hooks && tabs?.tabHooks) {
      for (const action of HOOK_ACTIONS) {
        if (tabs.tabHooks[action]?.[QLAB_WORKBENCH_TAB_TYPE] === hooks[action]) {
          delete tabs.tabHooks[action][QLAB_WORKBENCH_TAB_TYPE];
        }
      }
    }
    this.installedHooks.delete(win);

    const ids = this.entries(win).map((entry) => entry.id);
    if (closeTabs && ids.length && tabs?.close) {
      tabs.close(ids);
    }
    for (const id of ids) this.removeEntry(win, id);
    this.windowEntries.delete(win);
  }

  open(
    win: Window,
    data: WorkbenchTabData,
    options: WorkbenchTabOptions = {},
  ): WorkbenchTabEntry {
    this.install(win);
    const tabs = win.Zotero_Tabs;
    if (!tabs?.add) throw new Error("Zotero native tabs are unavailable");

    const current = !options.forceNew ? this.entries(win)[0] : undefined;
    if (current) {
      current.data = { ...data };
      tabs.setTabData?.(current.id, this.zoteroData(data));
      tabs.rename?.(current.id, data.title);
      tabs.select?.(current.id);
      current.view.focusComposer();
      if (data.layout !== undefined) {
        current.view.setLayoutData?.(data.layout);
      }
      return current;
    }

    const map = this.windowEntries.get(win) || new Map<string, WorkbenchTabEntry>();
    this.windowEntries.set(win, map);
    let tabID = "";
    const added = tabs.add({
      type: QLAB_WORKBENCH_TAB_TYPE,
      title: data.title,
      data: this.zoteroData(data),
      index: options.index,
      select: options.select !== false,
      onClose: () => this.removeEntry(win, tabID),
    });
    tabID = String(added.id);
    const container = added.container as HTMLElement;
    container.classList.add("zc-workbench-tab-container");
    const host = container.ownerDocument.createElement("div");
    host.className = "zc-workbench-tab-host";
    container.appendChild(host);
    const view = this.callbacks.createView(host, win, tabID);
    const entry: WorkbenchTabEntry = { id: tabID, host, view, data: { ...data } };
    map.set(tabID, entry);
    (container as any).onTabSelectionChanged = (selected: boolean) => {
      if (selected) view.focusComposer();
    };
    view.show();
    if (data.layout !== undefined) view.setLayoutData?.(data.layout);
    return entry;
  }

  entries(win?: Window): WorkbenchTabEntry[] {
    if (win) return [...(this.windowEntries.get(win)?.values() || [])];
    return [...this.windowEntries.values()].flatMap((entries) => [...entries.values()]);
  }

  update(win: Window, id: string, data: WorkbenchTabData, select = true): WorkbenchTabEntry | null {
    const entry = this.entry(win, id);
    if (!entry) return null;
    entry.data = { ...data };
    win.Zotero_Tabs?.setTabData?.(id, this.zoteroData(data));
    win.Zotero_Tabs?.rename?.(id, data.title);
    if (select) win.Zotero_Tabs?.select?.(id);
    return entry;
  }

  private entry(win: Window, id: string): WorkbenchTabEntry | undefined {
    return this.windowEntries.get(win)?.get(id);
  }

  private removeEntry(win: Window, id: string): void {
    const map = this.windowEntries.get(win);
    const entry = map?.get(id);
    if (!entry) return;
    map!.delete(id);
    entry.view.destroy();
    entry.host.remove();
    if (!map!.size) this.windowEntries.delete(win);
  }

  private zoteroData(data: WorkbenchTabData): Record<string, unknown> {
    let layout: string | undefined;
    if (data.layout !== undefined) {
      try { layout = JSON.stringify(data.layout); }
      catch { layout = undefined; }
    }
    return {
      ...(data.itemID === undefined ? {} : { itemID: data.itemID }),
      icon: QLAB_WORKBENCH_TAB_ICON,
      qlabWorkbenchTitle: data.title,
      ...(layout === undefined ? {} : { qlabLayout: layout }),
    };
  }

  private dataFromTab(tab: any): WorkbenchTabData {
    const raw = tab?.data || {};
    let layout: unknown;
    if (typeof raw.qlabLayout === "string") {
      try { layout = JSON.parse(raw.qlabLayout); }
      catch { layout = undefined; }
    }
    // Sessions saved before the tabbed workbench carried a boolean instead.
    if (layout === undefined && raw.qlabMainSiteOpen) layout = LEGACY_MAIN_SITE_LAYOUT;
    return {
      itemID: raw.itemID,
      icon: QLAB_WORKBENCH_TAB_ICON,
      title: String(raw.qlabWorkbenchTitle || tab?.title || "QLab Workbench"),
      ...(layout === undefined ? {} : { layout }),
    };
  }
}
