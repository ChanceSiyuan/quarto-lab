// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";

import { WorkbenchShell, type TabContentProvider } from "../src/workbench-shell";

function makeProvider(): TabContentProvider {
  return { mount: vi.fn(), show: vi.fn(), hide: vi.fn(), dispose: vi.fn() };
}

function domRect(x: number, y: number, width: number, height: number): DOMRect {
  return {
    x, y, width, height,
    left: x, top: y, right: x + width, bottom: y + height,
    toJSON: () => ({}),
  } as DOMRect;
}

function makeShell() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const shell = new WorkbenchShell(host, document, {
    initialSplitRatio: 50,
    onSplitRatioChange: vi.fn(),
    onLayoutChange: vi.fn(),
  });
  for (const kind of ["chat", "editor", "site", "pdf"] as const) {
    shell.registerFactory(kind, () => makeProvider());
  }
  stubGeometry(shell);
  return shell;
}

/** 1000×600 shell: bars are the top 30px, content is everything below. */
function stubGeometry(shell: WorkbenchShell): void {
  shell.root.getBoundingClientRect = () => domRect(0, 0, 1000, 600);
  const left = shell.root.querySelector('[data-pane="left"]') as HTMLElement;
  const right = shell.root.querySelector('[data-pane="right"]') as HTMLElement;
  const split = () => shell.root.getAttribute("data-split") === "true";
  left.getBoundingClientRect = () => domRect(0, 0, split() ? 500 : 1000, 30);
  right.getBoundingClientRect = () => (split() ? domRect(506, 0, 494, 30) : domRect(0, 0, 0, 0));
  stubTabRects(shell);
}

/** Lays tab buttons out 120px apart inside their bar. */
function stubTabRects(shell: WorkbenchShell): void {
  for (const bar of shell.root.querySelectorAll(".zc-pane-bar")) {
    const barLeft = bar.getAttribute("data-pane") === "right" ? 506 : 0;
    [...bar.querySelectorAll(".zc-shell-tab")].forEach((button, index) => {
      (button as HTMLElement).getBoundingClientRect =
        () => domRect(barLeft + index * 120, 0, 120, 30);
    });
  }
}

function pointer(type: string, x: number, y: number): Event {
  const event = new MouseEvent(type, { clientX: x, clientY: y, bubbles: true, cancelable: true });
  (event as unknown as { pointerId: number }).pointerId = 1;
  return event;
}

function tabButton(shell: WorkbenchShell, id: string): HTMLElement {
  return shell.root.querySelector(`.zc-shell-tab[data-tab-id="${id}"]`) as HTMLElement;
}

describe("WorkbenchShell drag", () => {
  it("computes drop targets from geometry", () => {
    const shell = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    stubTabRects(shell);
    // Single pane: right 20% edge of the content region splits.
    expect(shell.dropTargetAt(950, 300)).toEqual({ split: "right" });
    // Middle of the content region: current pane, append.
    expect(shell.dropTargetAt(500, 300)).toEqual({ pane: "left" });
    // Left edge in single-pane mode: reorder to the front, no split.
    expect(shell.dropTargetAt(50, 300)).toEqual({ pane: "left", index: 0 });
    // Bar: insertion index from button midpoints.
    expect(shell.dropTargetAt(30, 15)).toEqual({ pane: "left", index: 0 });
    expect(shell.dropTargetAt(130, 15)).toEqual({ pane: "left", index: 1 });
    expect(shell.dropTargetAt(300, 15)).toEqual({ pane: "left", index: 2 });
  });

  it("computes pane targets in split mode", () => {
    const shell = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.layout.moveTab("editor", "right");
    stubTabRects(shell);
    expect(shell.dropTargetAt(250, 300)).toEqual({ pane: "left" });
    expect(shell.dropTargetAt(750, 300)).toEqual({ pane: "right" });
    expect(shell.dropTargetAt(530, 15)).toEqual({ pane: "right", index: 0 });
  });

  it("drags a tab to the right edge and splits", () => {
    const shell = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    stubTabRects(shell);
    const button = tabButton(shell, "editor");
    button.dispatchEvent(pointer("pointerdown", 130, 15));
    button.dispatchEvent(pointer("pointermove", 500, 300));
    const indicator = shell.root.querySelector(".zc-drop-indicator") as HTMLElement;
    expect(indicator.hidden).toBe(false);
    button.dispatchEvent(pointer("pointermove", 950, 300));
    button.dispatchEvent(pointer("pointerup", 950, 300));
    expect(shell.root.getAttribute("data-split")).toBe("true");
    expect(shell.layout.paneOf("editor")).toBe("right");
    expect(indicator.hidden).toBe(true);
  });

  it("drags the last right tab onto the left bar and collapses the split", () => {
    const shell = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.layout.moveTab("editor", "right");
    stubTabRects(shell);
    const button = tabButton(shell, "editor");
    button.dispatchEvent(pointer("pointerdown", 530, 15));
    button.dispatchEvent(pointer("pointermove", 30, 15));
    button.dispatchEvent(pointer("pointerup", 30, 15));
    expect(shell.layout.paneOf("editor")).toBe("left");
    expect(shell.layout.snapshot().panes.right).toBeNull();
    expect(shell.layout.snapshot().panes.left.tabIds).toEqual(["editor", "chat"]);
  });

  it("treats a 2px jitter as a click, not a drag", () => {
    const shell = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.layout.activateTab("editor");
    stubTabRects(shell);
    const button = tabButton(shell, "chat");
    button.dispatchEvent(pointer("pointerdown", 60, 15));
    button.dispatchEvent(pointer("pointermove", 62, 15));
    button.dispatchEvent(pointer("pointerup", 62, 15));
    button.click();
    expect(shell.layout.snapshot().panes.left.activeTabId).toBe("chat");
    expect(shell.layout.snapshot().panes.left.tabIds).toEqual(["chat", "editor"]);
  });

  it("aborts the drag on Escape", () => {
    const shell = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    stubTabRects(shell);
    const button = tabButton(shell, "editor");
    button.dispatchEvent(pointer("pointerdown", 130, 15));
    button.dispatchEvent(pointer("pointermove", 900, 300));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    button.dispatchEvent(pointer("pointerup", 950, 300));
    expect(shell.root.getAttribute("data-split")).toBe("false");
    expect((shell.root.querySelector(".zc-drop-indicator") as HTMLElement).hidden).toBe(true);
  });
});
