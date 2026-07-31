// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";

import {
  StandaloneWorkbenchManager,
  type StandaloneWorkbenchView,
} from "../src/standalone-workbench";

function popupWindow(): Window {
  const doc = document.implementation.createHTMLDocument("QLab Standalone");
  const host = doc.createElement("div");
  host.id = "qlab-standalone-workbench-host";
  doc.body.appendChild(host);
  const listeners = new Map<string, EventListener[]>();
  const win = {
    document: doc,
    closed: false,
    focus: vi.fn(),
    close: vi.fn(function (this: { closed: boolean }) {
      this.closed = true;
      for (const listener of listeners.get("unload") || []) listener(new Event("unload"));
    }),
    addEventListener: vi.fn((name: string, listener: EventListener) => {
      const values = listeners.get(name) || [];
      values.push(listener);
      listeners.set(name, values);
    }),
    removeEventListener: vi.fn(),
  } as unknown as Window;
  return win;
}

describe("StandaloneWorkbenchManager", () => {
  it("mounts one shared workbench and focuses it on repeated opens", async () => {
    const popup = popupWindow();
    const view: StandaloneWorkbenchView = {
      show: vi.fn(), destroy: vi.fn(), focusComposer: vi.fn(), setState: vi.fn(),
    };
    const onActiveChange = vi.fn();
    const manager = new StandaloneWorkbenchManager({
      openWindow: vi.fn(async () => popup),
      createView: vi.fn(() => view),
      onActiveChange,
    });

    await expect(manager.open({} as Window)).resolves.toBe(popup);
    await expect(manager.open({} as Window)).resolves.toBe(popup);

    expect(view.show).toHaveBeenCalledOnce();
    expect(view.focusComposer).toHaveBeenCalledTimes(2);
    expect(popup.focus).toHaveBeenCalledOnce();
    expect(onActiveChange).toHaveBeenCalledWith(true);
    expect(manager.isActive()).toBe(true);
  });

  it("destroys the mounted view and restores embedded surfaces on close", async () => {
    const popup = popupWindow();
    const view: StandaloneWorkbenchView = {
      show: vi.fn(), destroy: vi.fn(), focusComposer: vi.fn(), setState: vi.fn(),
    };
    const onActiveChange = vi.fn();
    const manager = new StandaloneWorkbenchManager({
      openWindow: vi.fn(async () => popup),
      createView: vi.fn(() => view),
      onActiveChange,
    });
    await manager.open({} as Window);

    manager.close();

    expect(view.destroy).toHaveBeenCalledOnce();
    expect(onActiveChange).toHaveBeenLastCalledWith(false);
    expect(manager.isActive()).toBe(false);
  });

  it("returns the chat to the embedded surface without deleting its conversation", async () => {
    const popup = popupWindow();
    const view: StandaloneWorkbenchView = {
      show: vi.fn(), destroy: vi.fn(), focusComposer: vi.fn(), setState: vi.fn(),
    };
    const onReturn = vi.fn();
    const manager = new StandaloneWorkbenchManager({
      openWindow: vi.fn(async () => popup),
      createView: vi.fn(() => view),
      onActiveChange: vi.fn(),
      onReturn,
    });
    await manager.open({} as Window);

    manager.returnToEmbedded();

    expect(onReturn).toHaveBeenCalledOnce();
    expect(view.destroy).toHaveBeenCalledOnce();
  });
});
