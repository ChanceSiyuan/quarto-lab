import { describe, expect, it, vi } from "vitest";

import { WorkbenchLayout, tabIdFor } from "../src/workbench-layout";

const pdfReq = (key = "KEY1", page = 3) =>
  ({ kind: "pdf", title: `Paper ${key}`, payload: { itemID: 11, attachmentKey: key, page } }) as const;

describe("WorkbenchLayout", () => {
  it("opens singleton tabs once and reactivates on reopen", () => {
    const layout = new WorkbenchLayout(vi.fn());
    expect(layout.openTab({ kind: "chat" })).toBe("chat");
    layout.openTab({ kind: "editor" });
    expect(layout.openTab({ kind: "chat" })).toBe("chat");
    expect(layout.tabs()).toHaveLength(2);
    expect(layout.snapshot().panes.left.activeTabId).toBe("chat");
  });

  it("gives pdf tabs one id per attachment", () => {
    const layout = new WorkbenchLayout(vi.fn());
    expect(tabIdFor(pdfReq("A"))).toBe("pdf:A");
    layout.openTab(pdfReq("A"));
    layout.openTab(pdfReq("B"));
    layout.openTab(pdfReq("A", 9));
    expect(layout.tabs()).toHaveLength(2);
    expect(layout.tab("pdf:A")?.payload?.page).toBe(9);
  });

  it("collapses to a single pane when the last right tab closes", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab({ kind: "chat" });
    layout.openTab({ kind: "editor" });
    layout.moveTab("editor", "right");
    expect(layout.snapshot().panes.right?.tabIds).toEqual(["editor"]);
    layout.closeTab("editor");
    expect(layout.snapshot().panes.right).toBeNull();
    expect(layout.snapshot().focusedPane).toBe("left");
  });

  it("adopts the right pane when the left pane empties", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab({ kind: "chat" });
    layout.openTab({ kind: "editor" });
    layout.moveTab("editor", "right");
    layout.closeTab("chat");
    const snap = layout.snapshot();
    expect(snap.panes.left.tabIds).toEqual(["editor"]);
    expect(snap.panes.right).toBeNull();
  });

  it("treats moving a lone tab to the right as a no-op", () => {
    const onChange = vi.fn();
    const layout = new WorkbenchLayout(onChange);
    layout.openTab({ kind: "chat" });
    onChange.mockClear();
    layout.moveTab("chat", "right");
    expect(layout.snapshot().panes.right).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("fires onChange exactly once per mutating call", () => {
    const onChange = vi.fn();
    const layout = new WorkbenchLayout(onChange);
    layout.openTab({ kind: "chat" });
    expect(onChange).toHaveBeenCalledTimes(1);
    layout.openTab({ kind: "editor" });
    expect(onChange).toHaveBeenCalledTimes(2);
    layout.moveTab("editor", "right");
    expect(onChange).toHaveBeenCalledTimes(3);
    layout.activateTab("editor");
    expect(onChange).toHaveBeenCalledTimes(3); // already active + focused: no change
    layout.activateTab("chat");
    expect(onChange).toHaveBeenCalledTimes(4);
  });

  it("arrange is idempotent and leaves bystander tabs alone", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab({ kind: "site" });
    layout.arrange(pdfReq("A"), { kind: "chat" });
    const first = JSON.stringify(layout.serialize());
    layout.arrange(pdfReq("A"), { kind: "chat" });
    expect(JSON.stringify(layout.serialize())).toBe(first);
    expect(layout.paneOf("site")).toBe("left");
    expect(layout.snapshot().panes.left.activeTabId).toBe("pdf:A");
    expect(layout.snapshot().panes.right?.activeTabId).toBe("chat");
    expect(layout.snapshot().focusedPane).toBe("left");
  });

  it("arrange pulls an existing tab across panes when the sides demand it", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab({ kind: "chat" });
    layout.openTab({ kind: "editor" });
    layout.moveTab("chat", "right");
    layout.arrange(pdfReq("A"), { kind: "editor" });
    expect(layout.paneOf("pdf:A")).toBe("left");
    expect(layout.paneOf("editor")).toBe("right");
    expect(layout.snapshot().panes.right?.activeTabId).toBe("editor");
  });

  it("updates a pdf tab page for persistence", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab(pdfReq("A", 1));
    layout.updatePdfPage("pdf:A", 42);
    expect(layout.tab("pdf:A")?.payload?.page).toBe(42);
  });

  it("round-trips through serialize/restore", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab({ kind: "chat" });
    layout.openTab(pdfReq("A"));
    layout.moveTab("pdf:A", "right");
    const data = layout.serialize();
    const restored = new WorkbenchLayout(vi.fn());
    restored.restore(data);
    expect(restored.serialize()).toEqual(data);
  });

  it("drops unknown kinds and broken pdf payloads on restore", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.restore({
      version: 1,
      tabs: [
        { id: "chat", kind: "chat", title: "Chat" },
        { id: "x", kind: "mystery", title: "?" },
        { id: "pdf:", kind: "pdf", title: "broken", payload: { attachmentKey: "" } },
      ],
      panes: { left: { tabIds: ["chat", "x", "pdf:"], activeTabId: "x" }, right: null },
      focusedPane: "left",
    });
    expect(layout.tabs().map((t) => t.id)).toEqual(["chat"]);
    expect(layout.snapshot().panes.left.activeTabId).toBe("chat");
  });

  it("restores a default empty layout from garbage", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.restore("nonsense");
    expect(layout.tabs()).toEqual([]);
    expect(layout.snapshot().panes.left.tabIds).toEqual([]);
    expect(layout.snapshot().panes.right).toBeNull();
  });
});
