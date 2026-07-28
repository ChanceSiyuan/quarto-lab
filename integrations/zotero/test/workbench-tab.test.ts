// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  QLAB_WORKBENCH_TAB_ICON,
  QLAB_WORKBENCH_TAB_TYPE,
  WorkbenchTabManager,
  type WorkbenchTabData,
  type WorkbenchTabView,
} from "../src/workbench-tab";

interface FakeTabRecord {
  id: string;
  type: string;
  title: string;
  data: Record<string, unknown>;
  onClose?: () => void;
}

function fakeWindow(name: string): Window & { Zotero_Tabs: any; records: FakeTabRecord[] } {
  const doc = document.implementation.createHTMLDocument(name);
  const records: FakeTabRecord[] = [];
  let sequence = 0;
  const win = { document: doc } as Window & { Zotero_Tabs: any; records: FakeTabRecord[] };
  win.records = records;
  win.Zotero_Tabs = {
    tabHooks: {},
    add: vi.fn((options: FakeTabRecord & { select?: boolean; index?: number }) => {
      const id = options.id || `${name}-tab-${++sequence}`;
      const record = { ...options, id };
      const index = options.index === undefined ? records.length : Math.max(0, options.index - 1);
      records.splice(index, 0, record);
      const container = doc.createElement("section");
      container.id = id;
      doc.body.appendChild(container);
      return { id, container };
    }),
    select: vi.fn(),
    close: vi.fn((id: string) => {
      const index = records.findIndex((record) => record.id === id);
      if (index < 0) return;
      const [record] = records.splice(index, 1);
      record!.onClose?.();
      doc.getElementById(id)?.remove();
    }),
    rename: vi.fn((id: string, title: string) => {
      const record = records.find((entry) => entry.id === id);
      if (record) record.title = title;
    }),
    setTabData: vi.fn((id: string, data: Record<string, unknown>) => {
      const record = records.find((entry) => entry.id === id);
      if (record) Object.assign(record.data, data);
    }),
  };
  return win;
}

function data(title = "QLab · A Paper"): WorkbenchTabData {
  return { itemID: 42, icon: "attachmentPDF", title };
}

function setup() {
  const views: WorkbenchTabView[] = [];
  const createView = vi.fn(() => {
    const view: WorkbenchTabView = {
      show: vi.fn(),
      destroy: vi.fn(),
      focusComposer: vi.fn(),
      setState: vi.fn(),
    };
    views.push(view);
    return view;
  });
  const target = fakeWindow("target");
  const openNewWindow = vi.fn(async () => target);
  const manager = new WorkbenchTabManager({ createView, openNewWindow });
  return { manager, createView, openNewWindow, target, views };
}

describe("WorkbenchTabManager", () => {
  beforeEach(() => document.body.replaceChildren());

  it("adds QLab to Zotero's native tab deck and reuses the primary tab", () => {
    const source = fakeWindow("source");
    const { manager, createView, views } = setup();
    manager.install(source);

    const first = manager.open(source, data());
    const second = manager.open(source, data("QLab · Renamed"));

    expect(first.id).toBe(second.id);
    expect(source.Zotero_Tabs.add).toHaveBeenCalledWith(expect.objectContaining({
      type: QLAB_WORKBENCH_TAB_TYPE,
      title: "QLab · A Paper",
      select: true,
      data: expect.objectContaining({ itemID: 42, icon: QLAB_WORKBENCH_TAB_ICON }),
    }));
    expect(source.Zotero_Tabs.select).toHaveBeenCalledWith(first.id);
    expect(source.Zotero_Tabs.rename).toHaveBeenCalledWith(first.id, "QLab · Renamed");
    expect(createView).toHaveBeenCalledOnce();
    expect(views[0]!.show).toHaveBeenCalledOnce();
    expect(source.document.querySelector(".zc-workbench-tab-host")).not.toBeNull();
  });

  it("creates an empty native tab and later binds it to a selected Zotero paper", () => {
    const source = fakeWindow("source");
    const { manager } = setup();
    const entry = manager.open(source, { icon: "attachmentPDF", title: "QLab 工作台" });

    expect(source.records[0]!.data.itemID).toBeUndefined();
    manager.update(source, entry.id, data("QLab · Selected Paper"));

    expect(entry.data.itemID).toBe(42);
    expect(source.Zotero_Tabs.setTabData).toHaveBeenCalledWith(
      entry.id,
      expect.objectContaining({ itemID: 42, qlabWorkbenchTitle: "QLab · Selected Paper" }),
    );
    expect(source.Zotero_Tabs.rename).toHaveBeenCalledWith(entry.id, "QLab · Selected Paper");
  });

  it("installs PDF-like tab hooks for focus, duplicate, restore, undo-close, and window migration", async () => {
    const source = fakeWindow("source");
    const { manager, openNewWindow, target, views } = setup();
    manager.install(source);
    const entry = manager.open(source, data());
    const hooks = source.Zotero_Tabs.tabHooks;

    for (const action of [
      "focusFirst", "refocus", "duplicate", "restoreState",
      "undoClose", "getTitle", "moveToNewWindow",
    ]) {
      expect(hooks[action]?.[QLAB_WORKBENCH_TAB_TYPE]).toBeTypeOf("function");
    }

    await hooks.focusFirst[QLAB_WORKBENCH_TAB_TYPE]({ id: entry.id });
    expect(views[0]!.focusComposer).toHaveBeenCalledOnce();

    await hooks.duplicate[QLAB_WORKBENCH_TAB_TYPE](source.records[0], 1);
    expect(source.records).toHaveLength(2);

    const restored = await hooks.restoreState[QLAB_WORKBENCH_TAB_TYPE]({
      data: { ...data("QLab · Restored"), qlabWorkbenchTitle: "QLab · Restored" },
      title: "QLab · Restored",
      selected: false,
    }, 2);
    expect(restored).toEqual({ itemID: 42 });
    expect(source.records.some((record) => record.title === "QLab · Restored")).toBe(true);

    await hooks.moveToNewWindow[QLAB_WORKBENCH_TAB_TYPE](source.records[0], 1);
    expect(openNewWindow).toHaveBeenCalledWith(source);
    expect(target.records).toHaveLength(1);
    expect(source.Zotero_Tabs.close).toHaveBeenCalledWith(entry.id);
  });

  it("destroys its view when Zotero closes the tab and removes owned hooks on uninstall", () => {
    const source = fakeWindow("source");
    const { manager, views } = setup();
    manager.install(source);
    const entry = manager.open(source, data());

    source.Zotero_Tabs.close(entry.id);

    expect(views[0]!.destroy).toHaveBeenCalledOnce();
    expect(manager.entries(source)).toHaveLength(0);
    manager.uninstall(source);
    expect(source.Zotero_Tabs.tabHooks.duplicate[QLAB_WORKBENCH_TAB_TYPE]).toBeUndefined();
  });
});
