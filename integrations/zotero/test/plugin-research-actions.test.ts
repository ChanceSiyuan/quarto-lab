// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";

import { ZoteroChatPlugin } from "../src/plugin";

const ACTION_IDS = ["summarize", "evidence-qa", "compare-papers"] as const;

function configuredPlugin(): any {
  const plugin = new ZoteroChatPlugin() as any;
  plugin.context = {
    attachment: {
      key: "PRIMARY-PDF",
      libraryID: 1,
      title: "Primary Paper.pdf",
      creators: [],
    },
    parent: {
      key: "PRIMARY",
      title: "Primary Paper",
      creators: [],
      tags: [],
    },
    page: { pageIndex: 2, pageNumber: 3, pageLabel: "3" },
  };
  plugin.settings = { qlabRoot: "/research-loop" };
  plugin.codex = {
    state: { activeThreadId: "thread-primary" },
    getActiveReaderContext: () => plugin.context,
  };
  plugin.conversationPapers.add("thread-primary", {
    id: "1-COMPARISON-PDF",
    libraryID: "1",
    attachmentKey: "COMPARISON-PDF",
    itemKey: "COMPARISON",
    title: "Comparison Paper",
    pdfPath: "/papers/comparison.pdf",
    mode: "retrieval",
  });
  plugin.sendChat = vi.fn(async () => {});
  return plugin;
}

function renderNamedActions(plugin: any, view: any, win: Window): void {
  const state = plugin.researchActionViewState(win);
  view.setState({
    phase: "ready",
    researchObject: state.researchObject,
    researchActions: state.researchActions.filter(
      (action: { id: string }) => ACTION_IDS.includes(action.id as typeof ACTION_IDS[number]),
    ),
  });
}

// createWorkbenchView is the shared factory behind the native Workbench tab
// and standalone window. These tests drive its real SidebarView buttons and
// keep runResearchAction real, so losing the factory callback makes both
// surfaces silently no-op and fails at the user-visible entry point.
describe("Workbench Research Action wiring", () => {
  afterEach(() => {
    document.body.replaceChildren();
  });

  it("sends action-specific prompts from all three named Workbench buttons", async () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const plugin = configuredPlugin();
    const workbenchWindow = {
      document,
      Zotero_Tabs: { selectedType: "qlab" },
    } as unknown as Window;

    const view = plugin.createWorkbenchView(host, workbenchWindow, "qlab-tab");
    renderNamedActions(plugin, view, workbenchWindow);

    for (const actionID of ACTION_IDS) {
      host.querySelector<HTMLButtonElement>(
        `.zc-research-action[data-action-id="${actionID}"]`,
      )!.click();
    }

    await vi.waitFor(() => expect(plugin.sendChat).toHaveBeenCalledTimes(3));

    const sent = plugin.sendChat.mock.calls;
    expect(sent.map(([prompt]: [string]) => prompt.trim().length > 0))
      .toEqual([true, true, true]);
    expect(sent[0]![0]).toContain("Research Loop Action: summarize");
    expect(sent[0]![1]).toEqual({ readOnly: true });
    expect(sent[1]![0]).toContain("Research Loop Action: evidence-qa");
    expect(sent[1]![1]).toEqual({ readOnly: true });
    expect(sent[2]![0]).toContain("Research Loop Action: compare-papers");
    expect(sent[2]![1]).toEqual({ readOnly: true });

    view.destroy();
  });

  it("sends a Research Action from a standalone view made by the same factory", async () => {
    const plugin = configuredPlugin();
    const standaloneDocument = document.implementation.createHTMLDocument("QLab standalone");
    standaloneDocument.documentElement.setAttribute("windowtype", "qlab:standalone-workbench");
    const standaloneHost = standaloneDocument.createElement("div");
    standaloneDocument.body.appendChild(standaloneHost);
    const standaloneWindow = {
      document: standaloneDocument,
      Zotero_Tabs: { selectedType: "qlab" },
    } as unknown as Window;

    const view = plugin.createWorkbenchView(standaloneHost, standaloneWindow, "standalone-window");
    renderNamedActions(plugin, view, standaloneWindow);

    standaloneHost.querySelector<HTMLButtonElement>(
      '.zc-research-action[data-action-id="evidence-qa"]',
    )!.click();

    await vi.waitFor(() => expect(plugin.sendChat).toHaveBeenCalledTimes(1));
    expect(plugin.sendChat.mock.calls[0]![0]).toContain("Research Loop Action: evidence-qa");
    expect(plugin.sendChat.mock.calls[0]![1]).toEqual({ readOnly: true });

    view.destroy();
  });

});
