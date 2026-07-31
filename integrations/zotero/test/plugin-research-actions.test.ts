// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";

import { ZoteroChatPlugin } from "../src/plugin";

// createWorkbenchView is the factory behind every live chat surface (the
// Workbench tab and the standalone window). test/sidebar.test.ts:119-141
// proves SidebarView forwards chip clicks WHEN a callback is supplied; this
// file proves the plugin actually supplies one. Without the wiring, the
// chip click resolves to `this.callbacks.onResearchAction?.(...)` on
// undefined — a silent no-op (src/sidebar.ts:1055).
describe("Workbench Research Action wiring", () => {
  afterEach(() => {
    document.body.replaceChildren();
  });

  it("dispatches runResearchAction when a chip is clicked in a Workbench view", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const plugin = new ZoteroChatPlugin() as any;
    plugin.runResearchAction = vi.fn(async () => {});

    const view = plugin.createWorkbenchView(host, window, "qlab-tab");
    view.setState({
      phase: "ready",
      researchObject: { kind: "pdf", label: "A Test Paper" },
      researchActions: [{
        id: "summarize",
        label: "Summarize",
        description: "Summarize the selected object with traceable evidence.",
        icon: "≡",
      }],
    });

    host.querySelector<HTMLButtonElement>(".zc-research-action")!.click();

    expect(plugin.runResearchAction).toHaveBeenCalledWith(view, "summarize", window);

    view.destroy();
  });
});
