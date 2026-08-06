// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";

import { WorkbenchView, type WorkbenchViewCallbacks } from "../src/workbench-view";
import type { SidebarView } from "../src/sidebar";
import type { QmdWorkspaceView } from "../src/qmd-workspace";

function fakeChat(): SidebarView {
  const dock = document.createElement("div");
  dock.className = "zc-top-actions";
  return {
    show: vi.fn(),
    destroy: vi.fn(),
    focusComposer: vi.fn(),
    setState: vi.fn(),
    setDetached: vi.fn(),
    dockContents: vi.fn(() => dock),
    isTerminalOpen: vi.fn(() => false),
    setTerminalOpen: vi.fn(),
    terminalHost: vi.fn(() => document.createElement("aside")),
  } as unknown as SidebarView;
}

function fakeWorkspace(): QmdWorkspaceView {
  return {
    show: vi.fn(),
    hide: vi.fn(),
    destroy: vi.fn(),
    hasActiveEdit: vi.fn(() => false),
  } as unknown as QmdWorkspaceView;
}

function makeView(overrides: Partial<WorkbenchViewCallbacks> = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const chats: SidebarView[] = [];
  const workspaces: QmdWorkspaceView[] = [];
  const callbacks: WorkbenchViewCallbacks = {
    createChat: vi.fn(() => {
      const chat = fakeChat();
      chats.push(chat);
      return chat;
    }),
    siteCallbacks: {
      checkSite: vi.fn(async () => false),
      checkRepository: vi.fn(async () => "ready" as const),
      deploy: vi.fn(async () => undefined),
      chooseRepository: vi.fn(async () => undefined),
      onOpenDocument: vi.fn(),
    },
    createWorkspace: vi.fn(() => {
      const workspace = fakeWorkspace();
      workspaces.push(workspace);
      return workspace;
    }),
    createPdfProvider: vi.fn(() => ({
      mount: vi.fn(), show: vi.fn(), hide: vi.fn(), dispose: vi.fn(),
    })),
    initialSplitRatio: 40,
    onSplitRatioChange: vi.fn(),
    onLayoutChanged: vi.fn(),
    ...overrides,
  };
  const view = new WorkbenchView(host, callbacks);
  return { view, callbacks, chats, workspaces, host };
}

const pdf = { itemID: 7, attachmentKey: "KEY7", title: "Paper 7", page: 2 };

describe("WorkbenchView", () => {
  it("starts with a single chat tab and mounts the chat eagerly", () => {
    const { view, chats } = makeView();
    expect(view.layoutData().panes.left.tabIds).toEqual(["chat"]);
    expect(view.layoutData().panes.right).toBeNull();
    expect(chats).toHaveLength(1);
    view.focusComposer("hello");
    expect(chats[0]!.focusComposer).toHaveBeenCalledWith("hello");
  });

  it("relocates the chat dock strip into the shell dock", () => {
    const { view } = makeView();
    expect(view.shell.dock().querySelector(".zc-top-actions")).not.toBeNull();
  });

  it("round-trips layout data and mounts only active tabs on restore", () => {
    const { view, callbacks } = makeView();
    view.setLayoutData({
      version: 1,
      tabs: [
        { id: "chat", kind: "chat", title: "Chat" },
        { id: "editor", kind: "editor", title: "Editor" },
        { id: "site", kind: "site", title: "Main Site" },
      ],
      panes: {
        left: { tabIds: ["chat"], activeTabId: "chat" },
        right: { tabIds: ["editor", "site"], activeTabId: "site" },
      },
      focusedPane: "left",
    });
    // Editor is backgrounded in the right pane: no workspace yet.
    expect(callbacks.createWorkspace).not.toHaveBeenCalled();
    expect(view.workspace()).toBeNull();
    const data = view.layoutData();
    expect(data.panes.right?.activeTabId).toBe("site");
    const { view: second } = makeView();
    second.setLayoutData(JSON.parse(JSON.stringify(data)));
    expect(second.layoutData()).toEqual(data);
  });

  it("creates the workspace when the editor tab first activates", () => {
    const { view, workspaces } = makeView();
    expect(view.openEditorTab()).not.toBeNull();
    expect(workspaces).toHaveLength(1);
    expect(view.workspace()).toBe(workspaces[0]);
  });

  it("arranges pdf-chat and pdf-editor idempotently", () => {
    const { view } = makeView();
    view.arrange("pdf-chat", pdf);
    let snap = view.layoutData();
    expect(snap.panes.left.activeTabId).toBe("pdf:KEY7");
    expect(snap.panes.right?.activeTabId).toBe("chat");
    const first = JSON.stringify(snap);
    view.arrange("pdf-chat", pdf);
    expect(JSON.stringify(view.layoutData())).toBe(first);

    view.arrange("pdf-editor", pdf);
    snap = view.layoutData();
    expect(snap.panes.left.activeTabId).toBe("pdf:KEY7");
    expect(snap.panes.right?.activeTabId).toBe("editor");
    // Chat stays open in the right pane's tab list; editor is simply active.
    expect(snap.panes.right?.tabIds).toContain("chat");
  });

  it("reopens the chat tab before opening the terminal drawer", () => {
    const { view, chats } = makeView();
    view.shell.layout.closeTab("chat");
    expect(view.layoutData().panes.left.tabIds).toEqual([]);
    view.setTerminalOpen(true);
    expect(view.layoutData().panes.left.tabIds).toEqual(["chat"]);
    expect(chats[0]!.setTerminalOpen).toHaveBeenCalledWith(true);
  });

  it("vetoes an editor close while a visual edit is active", () => {
    const { view, workspaces } = makeView();
    view.openEditorTab();
    (workspaces[0]!.hasActiveEdit as ReturnType<typeof vi.fn>).mockReturnValue(true);
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    try {
      const close = view.shell.root.querySelector(
        '[data-tab-id="editor"] .zc-shell-tab-close',
      ) as HTMLElement;
      close.click();
      expect(view.shell.layout.tab("editor")).not.toBeNull();
      expect(confirm).toHaveBeenCalledOnce();
    }
    finally {
      vi.unstubAllGlobals();
    }
  });
});
