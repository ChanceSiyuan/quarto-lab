// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";

import { WorkbenchShell, type TabContentProvider } from "../src/workbench-shell";

type RecordedProvider = TabContentProvider & { hostSeen: HTMLElement | null };

function makeProvider(): RecordedProvider {
  const provider: RecordedProvider = {
    hostSeen: null,
    mount: vi.fn((host: HTMLElement) => { provider.hostSeen = host; }),
    show: vi.fn(),
    hide: vi.fn(),
    dispose: vi.fn(),
  };
  return provider;
}

function makeShell() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const providers = new Map<string, RecordedProvider>();
  const shell = new WorkbenchShell(host, document, {
    initialSplitRatio: 40,
    onSplitRatioChange: vi.fn(),
    onLayoutChange: vi.fn(),
  });
  for (const kind of ["chat", "editor", "site", "pdf"] as const) {
    shell.registerFactory(kind, (tab) => {
      const provider = makeProvider();
      providers.set(tab.id, provider);
      return provider;
    }, kind === "chat" ? { retainOnClose: true } : undefined);
  }
  return { shell, providers };
}

describe("WorkbenchShell", () => {
  it("renders one tab bar entry per tab and marks the active one", () => {
    const { shell } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.sync();
    const bar = shell.root.querySelector('[data-pane="left"]')!;
    const labels = [...bar.querySelectorAll(".zc-shell-tab")].map((b) => b.getAttribute("data-tab-id"));
    expect(labels).toEqual(["chat", "editor"]);
    expect(bar.querySelector(".zc-shell-tab.is-active")?.getAttribute("data-tab-id")).toBe("editor");
  });

  it("mounts providers lazily on restore, only when a tab first becomes active", () => {
    const { shell, providers } = makeShell();
    shell.layout.restore({
      version: 1,
      tabs: [
        { id: "editor", kind: "editor", title: "Editor" },
        { id: "site", kind: "site", title: "Main Site" },
      ],
      panes: { left: { tabIds: ["editor", "site"], activeTabId: "site" }, right: null },
      focusedPane: "left",
    });
    shell.sync();
    expect(providers.get("site")?.mount).toHaveBeenCalledOnce();
    expect(providers.get("editor")).toBeUndefined();
    shell.layout.activateTab("editor");
    shell.sync();
    expect(providers.get("editor")?.mount).toHaveBeenCalledOnce();
    shell.layout.activateTab("site");
    shell.layout.activateTab("editor");
    expect(providers.get("editor")?.mount).toHaveBeenCalledOnce(); // mounted once, ever
  });

  it("keeps the same content host node when a tab moves between panes", () => {
    const { shell } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.sync();
    const before = shell.contentHost("editor")!;
    shell.layout.moveTab("editor", "right");
    shell.sync();
    const after = shell.contentHost("editor")!;
    expect(after).toBe(before);
    expect(after.classList.contains("is-right")).toBe(true);
    expect(shell.root.getAttribute("data-split")).toBe("true");
  });

  it("collapses the grid and hides the right bar when the right pane dissolves", () => {
    const { shell } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.layout.moveTab("editor", "right");
    shell.sync();
    expect((shell.root.querySelector('[data-pane="right"]') as HTMLElement).hidden).toBe(false);
    shell.layout.closeTab("editor");
    shell.sync();
    expect(shell.root.getAttribute("data-split")).toBe("false");
    expect((shell.root.querySelector('[data-pane="right"]') as HTMLElement).hidden).toBe(true);
  });

  it("disposes providers on close but retains chat", () => {
    const { shell, providers } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.sync();
    shell.layout.openTab({ kind: "editor" });
    shell.sync();
    const closeEditor = shell.root.querySelector('[data-tab-id="editor"] .zc-shell-tab-close') as HTMLElement;
    closeEditor.click();
    shell.sync();
    expect(providers.get("editor")?.dispose).toHaveBeenCalledOnce();
    expect(shell.contentHost("editor")).toBeNull();
    const closeChat = shell.root.querySelector('[data-tab-id="chat"] .zc-shell-tab-close') as HTMLElement;
    closeChat.click();
    shell.sync();
    expect(providers.get("chat")?.dispose).not.toHaveBeenCalled();
    expect(providers.get("chat")?.hide).toHaveBeenCalled();
    expect(shell.root.querySelector(".zc-shell-empty")?.hasAttribute("hidden")).toBe(false);
  });

  it("reuses the retained chat provider when the chat tab reopens", () => {
    const { shell, providers } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.sync();
    const host = shell.contentHost("chat");
    shell.layout.closeTab("chat");
    shell.sync();
    shell.layout.openTab({ kind: "chat" });
    shell.sync();
    expect(providers.get("chat")?.mount).toHaveBeenCalledOnce();
    expect(shell.contentHost("chat")).toBe(host);
  });

  it("activates a tab when its bar button is clicked", () => {
    const { shell } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.sync();
    (shell.root.querySelector('.zc-shell-tab[data-tab-id="chat"]') as HTMLElement).click();
    expect(shell.layout.snapshot().panes.left.activeTabId).toBe("chat");
  });

  it("honors a close veto", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const shell = new WorkbenchShell(host, document, {
      initialSplitRatio: 40,
      onSplitRatioChange: vi.fn(),
      onLayoutChange: vi.fn(),
      onCloseRequested: (tab) => tab.id !== "editor",
    });
    shell.registerFactory("editor", () => makeProvider());
    shell.layout.openTab({ kind: "editor" });
    shell.sync();
    (shell.root.querySelector('[data-tab-id="editor"] .zc-shell-tab-close') as HTMLElement).click();
    shell.sync();
    expect(shell.layout.tab("editor")).not.toBeNull();
  });

  it("reports layout changes outward", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const onLayoutChange = vi.fn();
    const shell = new WorkbenchShell(host, document, {
      initialSplitRatio: 40,
      onSplitRatioChange: vi.fn(),
      onLayoutChange,
    });
    shell.registerFactory("chat", () => makeProvider());
    shell.layout.openTab({ kind: "chat" });
    expect(onLayoutChange).toHaveBeenCalledOnce();
    // sync happened implicitly through onChange:
    expect(shell.root.querySelector('.zc-shell-tab[data-tab-id="chat"]')).not.toBeNull();
  });
});
