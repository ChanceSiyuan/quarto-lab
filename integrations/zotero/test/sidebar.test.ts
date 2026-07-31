// @vitest-environment happy-dom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const storedPrefs = new Map<string, number>();
vi.mock("../src/platform", () => ({
  copyToClipboard: vi.fn(() => true),
  prefInt: vi.fn((name: string, fallback: number) => storedPrefs.get(name) ?? fallback),
  setPrefInt: vi.fn((name: string, value: number) => { storedPrefs.set(name, value); }),
}));

import { SidebarView, type SidebarCallbacks, type SidebarState } from "../src/sidebar";
import { renderMarkdown } from "../src/markdown";
import { copyToClipboard } from "../src/platform";

// Minimal Partial<SidebarState> merged into setState() calls that only care
// about one slice of state (mirrors the `phase: "ready"` seed the other
// tests in this file set inline) -- kept `as any` at the call site since a
// real SidebarState has many unrelated required fields.
function baseState(): Partial<SidebarState> {
  return { phase: "ready" };
}

function callbacks(): SidebarCallbacks {
  return {
    onSend: vi.fn(),
    onStop: vi.fn(),
    onNewThread: vi.fn(),
    onSelectThread: vi.fn(),
    onLogin: vi.fn(),
    onLogout: vi.fn(),
    onOpenTerminal: vi.fn(),
    onOpenWorkbench: vi.fn(),
    onRefreshContext: vi.fn(),
    onInsertSelection: vi.fn(),
    onModelChange: vi.fn(),
    onEffortChange: vi.fn()
  };
}

describe("SidebarView", () => {
  beforeEach(() => {
    document.body.replaceChildren();
    delete (document as any).createXULElement;
  });

  it("keeps the advanced Terminal reachable when app-server is unavailable", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = callbacks();
    const view = new SidebarView(body, handlers);
    view.setState({ phase: "unavailable", error: "app-server is unavailable" });

    const button = [...body.querySelectorAll<HTMLButtonElement>("button")]
      .find((candidate) => candidate.textContent === "Open Advanced Terminal")!;
    button.click();

    expect(handlers.onOpenTerminal).toHaveBeenCalledOnce();
  });

  it.each(["unavailable", "error", "signed-out"] as const)(
    "keeps settings reachable from the %s phase card (lockout fix)",
    (phase) => {
      const body = document.createElement("div");
      document.body.appendChild(body);
      const handlers = { ...callbacks(), onChooseQLabRoot: vi.fn() };
      const view = new SidebarView(body, handlers);
      view.setState({ phase, error: "app-server is unavailable" });

      const settings = body.querySelector<HTMLButtonElement>(".zc-error-settings");
      expect(settings).not.toBeNull();
      expect(settings!.textContent).toBe("Choose QLab Repository");
      settings!.click();

      expect(handlers.onChooseQLabRoot).toHaveBeenCalledOnce();
    }
  );

  it("renders the current paper, streamed answer, tools, and safe controls", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState({
      phase: "ready",
      accountLabel: "ChatGPT",
      context: {
        key: "ABC123",
        title: "A Test Paper",
        pageLabel: "7",
        pagesCount: 20,
        selectionText: "selected theorem"
      },
      entries: [
        { id: "u1", kind: "user", text: "Explain this" },
        { id: "t1", kind: "tool", title: "zotero_get_current_page", text: "page 7", state: "complete" },
        { id: "a1", kind: "assistant", text: "**Result:** page 7" }
      ],
      models: [{ id: "gpt-5", label: "GPT-5" }],
      threads: [],
      selectedModel: "gpt-5",
      effort: "high",
      running: false
    });

    expect(body.textContent).toContain("A Test Paper");
    expect(body.textContent).toContain("Selection: 16 characters");
    body.querySelector<HTMLButtonElement>(".zc-turn-summary")?.click();
    expect(body.textContent).toContain("zotero_get_current_page");
    expect(body.querySelector("strong")?.textContent).toBe("Result:");
    expect(body.querySelector<HTMLButtonElement>('button[title="Open Terminal"]')?.textContent).toBe("");
    expect(body.textContent).toContain("Research Loop · Local Codex");
    for (const title of ["Conversation History", "New Conversation", "Open Terminal", "Account", "Refresh Reader Context", "Send"]) {
      expect(body.querySelector(`button[title="${title}"] svg.zc-button-icon`)).not.toBeNull();
    }
  });

  it("renders only the Actions supplied for the current research object", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = { ...callbacks(), onResearchAction: vi.fn() };
    const view = new SidebarView(body, handlers);
    view.setState({
      phase: "ready",
      researchObject: { kind: "pdf", label: "A Test Paper" },
      researchActions: [
        { id: "summarize", label: "Summarize", description: "Summarize with evidence", icon: "≡" },
        { id: "analyze-figure", label: "Analyze Figure", description: "Analyze the current page image", icon: "▧" },
      ],
    });

    const actions = [...body.querySelectorAll<HTMLButtonElement>(".zc-research-action")];
    expect(actions.map((button) => button.title)).toEqual([
      "Summarize with evidence",
      "Analyze the current page image",
    ]);
    expect(body.querySelector(".zc-action-object")?.textContent).toContain("A Test Paper");
    actions[1]!.click();
    expect(handlers.onResearchAction).toHaveBeenCalledWith("analyze-figure");
  });

  it("keeps chip buttons alive across re-renders with unchanged Actions and rebuilds on change", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = { ...callbacks(), onResearchAction: vi.fn() };
    const view = new SidebarView(body, handlers);
    const freshActions = () => [
      { id: "summarize", label: "Summarize", description: "Summarize the selected object with traceable evidence.", icon: "≡" },
      { id: "evidence-qa", label: "Evidence QA", description: "Answer a question and audit each material claim against the source.", icon: "✓" },
    ];
    view.setState({
      phase: "ready",
      researchObject: { kind: "pdf", label: "A Test Paper" },
      researchActions: freshActions(),
    });
    const before = [...body.querySelectorAll<HTMLButtonElement>(".zc-research-action")];
    expect(before).toHaveLength(2);

    // Streaming turns call setState with fresh-but-equal state objects; the
    // strip must keep the same button nodes so an in-flight click (mousedown
    // before the re-render, mouseup after) still lands on a live element.
    view.setState({
      running: true,
      researchObject: { kind: "pdf", label: "A Test Paper" },
      researchActions: freshActions(),
    });
    const after = [...body.querySelectorAll<HTMLButtonElement>(".zc-research-action")];
    expect(after[0]).toBe(before[0]);
    expect(after[1]).toBe(before[1]);
    after[1]!.click();
    expect(handlers.onResearchAction).toHaveBeenCalledWith("evidence-qa");

    // A genuinely different action set rebuilds the chips.
    view.setState({
      researchActions: [
        { id: "summarize", label: "Summarize", description: "Summarize the selected object with traceable evidence.", icon: "≡" },
      ],
    });
    const changed = [...body.querySelectorAll<HTMLButtonElement>(".zc-research-action")];
    expect(changed).toHaveLength(1);
    expect(changed[0]).not.toBe(before[0]);

    // Clearing the research object still hides the strip (the derived
    // hidden state participates in the comparison, so this must not skip).
    view.setState({ researchObject: null, researchActions: [] });
    expect(body.querySelector<HTMLElement>(".zc-action-strip")!.hidden).toBe(true);
  });

  it("forwards assistant PDF citations to Zotero page navigation", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = {
      ...callbacks(),
      canOpenPdfPage: vi.fn(() => true),
      onOpenPdfPage: vi.fn(),
    };
    const view = new SidebarView(body, handlers);
    view.setState({
      phase: "ready",
      entries: [{
        id: "a1",
        kind: "assistant",
        text: "See [PDF 第6–7页](https://arxiv.org/pdf/2306.13123#page=6)",
      }],
    });

    body.querySelector<HTMLAnchorElement>(".zc-pdf-page-link")!.click();
    expect(handlers.onOpenPdfPage).toHaveBeenCalledWith({
      page: 6,
      endPage: 7,
      sourceUrl: "https://arxiv.org/pdf/2306.13123#page=6",
    });
  });

  it("keeps the repository selector without the QLab shortcut grid", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = { ...callbacks(), onChooseQLabRoot: vi.fn() };
    const view = new SidebarView(body, handlers);
    view.setState({
      phase: "ready",
      qlabRoot: "/Users/research/qlab",
      context: { key: "ITEM0001", title: "Paper" },
    });

    expect(body.querySelector(".zc-qlab-command-grid")).toBeNull();
    expect(body.querySelector(".zc-qlab-command-button")).toBeNull();

    body.querySelector<HTMLButtonElement>(".zc-qlab-root-button")!.click();
    expect(handlers.onChooseQLabRoot).toHaveBeenCalledOnce();
  });

  it("uses an explicit repository button and has no misleading settings gear", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = { ...callbacks(), onChooseQLabRoot: vi.fn() };
    const view = new SidebarView(body, handlers);
    view.setState({
      phase: "ready",
      models: [{ id: "gpt-5", label: "GPT-5" }],
      selectedModel: "gpt-5",
    });

    expect(body.querySelector(".zc-model-settings")).toBeNull();
    const repository = body.querySelector<HTMLButtonElement>(".zc-qlab-root-button")!;
    expect(repository.textContent).toContain("Choose repository");
    repository.click();

    expect(handlers.onChooseQLabRoot).toHaveBeenCalledOnce();
  });

  it("provides thread tabs, fixed Agent mode, context chips, and an @ context menu", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = callbacks();
    handlers.onAddContext = vi.fn();
    handlers.onRemoveContext = vi.fn();
    const view = new SidebarView(body, handlers);
    view.setState({
      phase: "ready",
      mode: "agent",
      context: {
        key: "ABC123",
        title: "A Test Paper",
        pageLabel: "7",
        selectionText: "selected theorem",
      },
      contextChips: [
        { id: "paper", kind: "paper", label: "Current Paper", removable: true },
        { id: "selection", kind: "selection", label: "选区 · 16 characters", removable: true },
      ],
      contextSuggestions: [
        { id: "annotations", kind: "annotation", label: "Annotations", detail: "12 notes" },
        { id: "library", kind: "library", label: "Library", detail: "All papers" },
      ],
      threads: [
        { id: "thread-a", title: "Main theorem", updatedAt: "2026-07-22", active: true, status: "running" },
        { id: "thread-b", title: "Methods", updatedAt: "2026-07-21", active: false },
      ],
    });

    expect(body.querySelector('.zc-sidebar')?.getAttribute("data-mode")).toBe("agent");
    // The composer no longer advertises an approval mode: it is fixed, so the
    // chip only ever restated what the mode already is.
    expect(body.textContent).not.toContain("需审批");
    expect(body.querySelector(".zc-safety-chip")).toBeNull();
    expect(body.querySelectorAll(".zc-thread-tab")).toHaveLength(2);
    body.querySelector<HTMLButtonElement>('[data-thread-id="thread-b"]')?.click();
    expect(handlers.onSelectThread).toHaveBeenCalledWith("thread-b");

    expect(body.querySelector('select[title="研究模式"]')).toBeNull();

    body.querySelector<HTMLButtonElement>('[data-context-id="paper"]')?.click();
    expect(handlers.onRemoveContext).toHaveBeenCalledWith("paper");

    body.querySelector<HTMLButtonElement>('button[title="Remove context: 选区 · 16 characters"]')?.click();
    expect(handlers.onRemoveContext).toHaveBeenCalledWith("selection");

    const input = body.querySelector<HTMLTextAreaElement>("textarea")!;
    input.value = "Compare @anno";
    input.setSelectionRange(input.value.length, input.value.length);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    const menu = body.querySelector<HTMLElement>(".zc-context-menu")!;
    expect(menu.hidden).toBe(false);
    expect(menu.textContent).toContain("Annotations");
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(handlers.onAddContext).toHaveBeenCalledWith(expect.objectContaining({ id: "annotations" }));
    expect(input.value).toBe("Compare ");
    expect(menu.hidden).toBe(true);
  });

  it("keeps an explicitly empty chip list empty after every selected context is removed", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState({
      phase: "ready",
      context: {
        key: "ABC123",
        title: "A Test Paper",
        pageLabel: "5",
      },
      contextChips: [],
    });

    expect(body.querySelector(".zc-context-chip")).toBeNull();
    expect(body.querySelector(".zc-add-context-button")).not.toBeNull();
  });

  it("renders a collapsible searchable Workbench history rail for Codex and imported ChatGPT", () => {
    vi.useFakeTimers();
    try {
      const body = document.createElement("div");
      document.body.appendChild(body);
      const handlers = {
        ...callbacks(),
        onHistorySearch: vi.fn(),
        onHistoryLoadMore: vi.fn(),
        onSelectHistoryConversation: vi.fn(),
        onToggleHistoryPin: vi.fn(),
        onOpenChatGPT: vi.fn(),
        onImportChatGPTHistory: vi.fn(),
        onReturnToLiveConversation: vi.fn(),
      };
      const view = new SidebarView(body, handlers, { surface: "workbench" });
      view.setState({
        phase: "ready",
        historyConversations: [{
          id: "codex-a",
          title: "Pinned Codex task",
          updatedAt: "2026-07-30T00:00:00.000Z",
          source: "codex",
          sourceLabel: "Codex App",
          pinned: true,
        }, {
          id: "chatgpt-a",
          title: "Imported physics chat",
          updatedAt: "2026-07-29T00:00:00.000Z",
          source: "chatgpt",
          sourceLabel: "Imported ChatGPT",
          readOnly: true,
          active: true,
        }],
        historyHasMore: true,
        readOnlyConversation: true,
      });

      const rail = body.querySelector<HTMLElement>(".zc-history-rail")!;
      const dock = body.querySelector<HTMLElement>(".zc-workbench-dock")!;
      const historyButton = body.querySelector<HTMLButtonElement>('[title="Conversation History"]')!;
      expect(body.querySelector(".zc-topbar")).toBeNull();
      expect(body.querySelector(".zc-thread-tabs")?.firstElementChild).toBe(historyButton);
      expect(historyButton.textContent).toBe("");
      expect(dock.parentElement).toBe(body.querySelector(".zc-workbench-chat"));
      expect(dock.querySelector('[title="Summarize this chat into a Draft"]')).toBeNull();
      expect(rail.hidden).toBe(false);
      expect(rail.textContent).toContain("Pinned Codex task");
      expect(rail.textContent).toContain("Imported physics chat");
      expect(body.querySelector<HTMLTextAreaElement>(".zc-composer-input")!.disabled).toBe(true);

      body.querySelector<HTMLButtonElement>('.zc-history-pin[title="Unpin Conversation"]')!.click();
      expect(handlers.onToggleHistoryPin).toHaveBeenCalledWith("codex-a", false);
      [...body.querySelectorAll<HTMLButtonElement>(".zc-history-open")]
        .find((button) => button.textContent?.includes("Imported physics chat"))!.click();
      expect(handlers.onSelectHistoryConversation).toHaveBeenCalledWith(
        expect.objectContaining({ id: "chatgpt-a", source: "chatgpt" }),
      );
      body.querySelector<HTMLButtonElement>(".zc-history-return-live")!.click();
      expect(handlers.onReturnToLiveConversation).toHaveBeenCalledOnce();
      body.querySelector<HTMLButtonElement>(".zc-history-load-more")!.click();
      expect(handlers.onHistoryLoadMore).toHaveBeenCalledOnce();

      const search = body.querySelector<HTMLInputElement>(".zc-history-search")!;
      search.value = "physics";
      search.dispatchEvent(new Event("input", { bubbles: true }));
      expect(rail.textContent).not.toContain("Pinned Codex task");
      expect(rail.textContent).toContain("Imported physics chat");
      vi.advanceTimersByTime(250);
      expect(handlers.onHistorySearch).toHaveBeenCalledWith("physics");

      body.querySelector<HTMLButtonElement>('[title="Open your live ChatGPT account history"]')!.click();
      body.querySelector<HTMLButtonElement>('[title*="Import conversations.json"]')!.click();
      expect(handlers.onOpenChatGPT).toHaveBeenCalledOnce();
      expect(handlers.onImportChatGPTHistory).toHaveBeenCalledOnce();

      body.querySelector<HTMLButtonElement>('[title="Conversation History"]')!.click();
      expect(rail.hidden).toBe(true);
      expect(dock.isConnected).toBe(true);
      dock.querySelector<HTMLButtonElement>('[title="Account"]')!.click();
      expect(dock.querySelector(".zc-account-menu")).not.toBeNull();
    }
    finally {
      vi.useRealTimers();
    }
  });

  it("gives every open conversation tab a close button without switching to it", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = callbacks();
    handlers.onDeleteThread = vi.fn();
    const view = new SidebarView(body, handlers);
    view.setState({
      phase: "ready",
      threads: [
        { id: "thread-a", title: "Main theorem", updatedAt: "2026-07-22", active: true, status: "idle" },
        { id: "thread-b", title: "Methods", updatedAt: "2026-07-21", active: false },
      ],
    });

    const deleteButtons = body.querySelectorAll<HTMLButtonElement>(".zc-thread-delete");
    // One per row, including the active thread's row -- deleting the active
    // thread is allowed; codex-service falls back per its own semantics.
    expect(deleteButtons).toHaveLength(2);
    for (const button of deleteButtons) {
      expect(button.textContent).toBe("×");
      expect(button.title).toBe("Close Tab");
    }

    deleteButtons[1]!.click();
    expect(handlers.onDeleteThread).toHaveBeenCalledWith("thread-b");
    expect(handlers.onDeleteThread).toHaveBeenCalledOnce();
    expect(handlers.onSelectThread).not.toHaveBeenCalled();
  });

  it("immediately marks a requested conversation and shows new-conversation progress", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState({
      phase: "ready",
      creatingThread: true,
      threads: [
        { id: "thread-a", title: "A", updatedAt: "2026-07-28", active: true },
        { id: "thread-b", title: "B", updatedAt: "2026-07-27", active: false, status: "switching" },
      ],
    });

    const switching = body.querySelector<HTMLButtonElement>('[data-thread-id="thread-b"]')!;
    expect(switching.classList.contains("is-switching")).toBe(true);
    expect(switching.getAttribute("aria-busy")).toBe("true");
    expect(body.querySelector<HTMLButtonElement>('.zc-thread-tab-add')!.disabled).toBe(true);
    expect(body.querySelector<HTMLButtonElement>('button[title="Creating a new conversation…"]')).not.toBeNull();
  });

  it("gives every row in the compact conversation picker a close button", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = callbacks();
    handlers.onDeleteThread = vi.fn();
    const view = new SidebarView(body, handlers);
    view.setState({
      phase: "ready",
      threads: [
        { id: "thread-a", title: "Main theorem", updatedAt: "2026-07-22", active: true },
        { id: "thread-b", title: "Methods", updatedAt: "2026-07-21", active: false },
      ],
    });

    body.querySelector<HTMLButtonElement>('button[title="Conversation History"]')!.click();
    const menu = body.querySelector<HTMLElement>(".zc-history-menu")!;
    expect(menu).not.toBeNull();
    const deleteButtons = menu.querySelectorAll<HTMLButtonElement>(".zc-thread-delete");
    expect(deleteButtons).toHaveLength(2);

    deleteButtons[1]!.click();
    expect(handlers.onDeleteThread).toHaveBeenCalledWith("thread-b");
    expect(handlers.onDeleteThread).toHaveBeenCalledOnce();
    expect(handlers.onSelectThread).not.toHaveBeenCalled();
    // The menu closes immediately -- the deleted row doesn't linger stale.
    expect(body.querySelector(".zc-history-menu")).toBeNull();
  });

  it("renders plan, diff review, and pending approval without checkpoint history", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = callbacks();
    handlers.onReviewDecision = vi.fn();
    handlers.onApprovalDecision = vi.fn();
    const view = new SidebarView(body, handlers);
    view.setState({
      phase: "ready",
      plan: {
        id: "plan-1",
        title: "Research plan",
        explanation: "Read before comparing.",
        steps: [
          { id: "step-1", title: "Read the abstract", status: "complete" },
          { id: "step-2", title: "Inspect the derivation", status: "running" },
        ],
      },
      reviews: [{
        id: "review-1",
        title: "Proposed note",
        summary: "Review before applying.",
        diff: "@@ note\n-old\n+new",
      }],
      pendingApproval: {
        id: "approval-1",
        title: "Open an external source",
        command: "search_library_pdf",
        kind: "tool",
        risk: "low",
      },
      checkpoints: [{ id: "checkpoint-1", label: "Before comparison", createdAt: "2026-07-22T10:30:00Z" }],
    });

    expect(body.textContent).toContain("Research plan");
    expect(body.textContent).toContain("1/2");
    expect(body.querySelector(".zc-diff-view .is-addition")?.textContent).toBe("+new");
    [...body.querySelectorAll<HTMLButtonElement>("button")]
      .find((button) => button.textContent === "Accept Suggestion")?.click();
    expect(handlers.onReviewDecision).toHaveBeenCalledWith("review-1", "accept");
    [...body.querySelectorAll<HTMLButtonElement>("button")]
      .find((button) => button.textContent === "Allow Once")?.click();
    expect(handlers.onApprovalDecision).toHaveBeenCalledWith("approval-1", "approve-once");
    expect(body.querySelector(".zc-checkpoint-card")).toBeNull();
    expect(body.textContent).not.toContain("Checkpoints");
  });

  it("does not expose stored checkpoints in the transcript", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState({
      phase: "ready",
      checkpoints: [
        { id: "checkpoint-1", label: "Before comparison", createdAt: "2026-07-22T10:30:00Z" },
        { id: "checkpoint-2", label: "Earlier", createdAt: "2026-07-21T10:30:00Z" },
      ],
    });

    expect(body.querySelector(".zc-checkpoint-card")).toBeNull();
    expect([...body.querySelectorAll("button")].some((button) => button.textContent === "Restore")).toBe(false);
  });

  it("removes redundant Agent change reminders after the working copy was applied", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = callbacks();
    handlers.onReviewDecision = vi.fn();
    const view = new SidebarView(body, handlers);
    view.setState({
      phase: "ready",
      reviews: [{
        id: "workspace:turn-1",
        title: "Agent workspace changes",
        summary: "Review the visible Draft on the right.",
        diff: "@@ draft\n-old\n+new",
        state: "applied",
      }],
    });

    expect(body.textContent).not.toContain("Agent workspace changes");
    expect(body.textContent).not.toContain("Applied");
    expect(body.textContent).not.toContain("Accept Suggestion");
    expect(body.textContent).not.toContain("Dismiss");
    expect(handlers.onReviewDecision).not.toHaveBeenCalled();
  });

  it("collapses a long user message and lets the user expand and collapse it", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState({
      phase: "ready",
      entries: [{ id: "long-user", kind: "user", text: "很长的用户消息.".repeat(80) }],
    });

    const bubble = body.querySelector<HTMLElement>(".zc-user-bubble")!;
    const toggle = body.querySelector<HTMLButtonElement>(".zc-user-message-toggle")!;
    expect(bubble.classList.contains("is-collapsed")).toBe(true);
    expect(toggle.textContent).toBe("Show Full Message");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");

    toggle.click();
    expect(bubble.classList.contains("is-collapsed")).toBe(false);
    expect(toggle.textContent).toBe("Collapse");
    expect(toggle.getAttribute("aria-expanded")).toBe("true");

    toggle.click();
    expect(bubble.classList.contains("is-collapsed")).toBe(true);
  });

  it("can reveal the composer when Zotero expands the custom section", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    const input = body.querySelector("textarea")!;
    input.scrollIntoView = vi.fn();

    view.revealComposer();

    expect(input.scrollIntoView).toHaveBeenCalledWith({ block: "nearest", inline: "nearest" });
  });

  it("reconciles streamed entries without collapsing an expanded tool card", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState({
      phase: "ready",
      entries: [
        { id: "u1", kind: "user", text: "问" },
        { id: "tool-1", kind: "reasoning", title: "Reasoning", text: "first", state: "complete" },
        { id: "answer-1", kind: "assistant", text: "stable" }
      ]
    });
    body.querySelector<HTMLButtonElement>(".zc-turn-summary")!.click();
    const details = body.querySelector<HTMLDetailsElement>('[data-entry-id="tool-1"] details')!;
    const stable = body.querySelector<HTMLElement>('[data-entry-id="answer-1"]')!;
    details.open = true;

    view.setState({
      entries: [
        { id: "u1", kind: "user", text: "问" },
        { id: "tool-1", kind: "reasoning", title: "Reasoning", text: "first second", state: "complete" },
        { id: "answer-1", kind: "assistant", text: "stable" }
      ]
    });

    expect(body.querySelector<HTMLDetailsElement>('[data-entry-id="tool-1"] details')?.open).toBe(true);
    expect(body.querySelector<HTMLElement>('[data-entry-id="answer-1"]')).toBe(stable);
  });

  describe("answer copy button", () => {
    beforeEach(() => {
      vi.mocked(copyToClipboard).mockClear();
      vi.mocked(copyToClipboard).mockReturnValue(true);
    });

    it("copies the raw answer text via the privileged clipboard helper and shows a transient confirmation", () => {
      vi.useFakeTimers();
      const body = document.createElement("div");
      document.body.appendChild(body);
      const view = new SidebarView(body, callbacks());
      view.setState({
        phase: "ready",
        entries: [
          { id: "a1", kind: "assistant", text: "**Result:** page 7" }
        ]
      });

      const button = body.querySelector<HTMLButtonElement>(".zc-copy-answer")!;
      expect(button).not.toBeNull();
      expect(button.title).toBe("Copy Answer");

      button.click();

      expect(copyToClipboard).toHaveBeenCalledWith("**Result:** page 7");
      expect(button.classList.contains("is-copied")).toBe(true);
      expect(button.title).toBe("Copied");

      vi.advanceTimersByTime(1500);
      expect(button.classList.contains("is-copied")).toBe(false);
      expect(button.title).toBe("Copy Answer");
      vi.useRealTimers();
    });

    it("does not add the copied state when the clipboard helper reports failure", () => {
      vi.mocked(copyToClipboard).mockReturnValue(false);
      const body = document.createElement("div");
      document.body.appendChild(body);
      const view = new SidebarView(body, callbacks());
      view.setState({
        phase: "ready",
        entries: [{ id: "a1", kind: "assistant", text: "answer" }]
      });

      const button = body.querySelector<HTMLButtonElement>(".zc-copy-answer")!;
      button.click();

      expect(button.classList.contains("is-copied")).toBe(false);
      expect(button.title).toBe("Copy Answer");
    });

    it("does not render a copy button on error entries", () => {
      const body = document.createElement("div");
      document.body.appendChild(body);
      const view = new SidebarView(body, callbacks());
      view.setState({
        phase: "ready",
        entries: [{ id: "e1", kind: "error", text: "boom" }]
      });

      const button = body.querySelector<HTMLButtonElement>(".zc-copy-answer");
      expect(button).toBeNull();
    });
  });

  describe("formula click-to-copy", () => {
    beforeEach(() => {
      vi.mocked(copyToClipboard).mockClear();
      vi.mocked(copyToClipboard).mockReturnValue(true);
    });

    it("copies the bare LaTeX source when a rendered formula is clicked, briefly marking it copied", () => {
      vi.useFakeTimers();
      const body = document.createElement("div");
      document.body.appendChild(body);
      const view = new SidebarView(body, callbacks());
      view.setState({
        phase: "ready",
        entries: [{ id: "a1", kind: "assistant", text: "$$x$$" }],
      });

      const formula = body.querySelector<HTMLElement>(".zc-math-copy")!;
      expect(formula).not.toBeNull();

      formula.click();

      expect(copyToClipboard).toHaveBeenCalledWith("x");
      expect(formula.classList.contains("is-copied")).toBe(true);

      vi.advanceTimersByTime(1200);
      expect(formula.classList.contains("is-copied")).toBe(false);
      vi.useRealTimers();
    });

    it("does not mark the formula copied when the clipboard helper reports failure", () => {
      vi.mocked(copyToClipboard).mockReturnValue(false);
      const body = document.createElement("div");
      document.body.appendChild(body);
      const view = new SidebarView(body, callbacks());
      view.setState({
        phase: "ready",
        entries: [{ id: "a1", kind: "assistant", text: "$$x$$" }],
      });

      const formula = body.querySelector<HTMLElement>(".zc-math-copy")!;
      formula.click();

      expect(formula.classList.contains("is-copied")).toBe(false);
    });

    it("does not trigger formula copy behavior when the answer-copy button is clicked", () => {
      const body = document.createElement("div");
      document.body.appendChild(body);
      const view = new SidebarView(body, callbacks());
      view.setState({
        phase: "ready",
        entries: [{ id: "a1", kind: "assistant", text: "$$x$$ answer" }],
      });

      const answerButton = body.querySelector<HTMLButtonElement>(".zc-copy-answer")!;
      vi.mocked(copyToClipboard).mockClear();
      answerButton.click();

      expect(copyToClipboard).toHaveBeenCalledWith("$$x$$ answer");
      expect(copyToClipboard).toHaveBeenCalledTimes(1);
    });

    it("skips formula click-to-copy while a text selection is active, and copies once it collapses", () => {
      const body = document.createElement("div");
      document.body.appendChild(body);
      const view = new SidebarView(body, callbacks());
      view.setState({
        phase: "ready",
        entries: [{ id: "a1", kind: "assistant", text: "$$x$$" }],
      });

      const formula = body.querySelector<HTMLElement>(".zc-math-copy")!;
      const getSelectionSpy = vi.spyOn(window, "getSelection")
        .mockReturnValue({ isCollapsed: false } as Selection);
      formula.click();
      expect(copyToClipboard).not.toHaveBeenCalled();

      getSelectionSpy.mockReturnValue({ isCollapsed: true } as Selection);
      formula.click();
      expect(copyToClipboard).toHaveBeenCalledWith("x");

      getSelectionSpy.mockRestore();
    });
  });

  it("submits with Enter and keeps Shift+Enter available for multiline input", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = callbacks();
    const view = new SidebarView(body, handlers);
    view.setState({ phase: "ready" });
    const input = body.querySelector("textarea")!;
    input.value = "What is the main theorem?";
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(handlers.onSend).toHaveBeenCalledWith("What is the main theorem?");
  });

  it("sends a follow-up while running and keeps stop as a separate button and Escape action", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = callbacks();
    const view = new SidebarView(body, handlers);
    view.setState({ phase: "ready", running: true });

    const input = body.querySelector("textarea")!;
    expect(input.disabled).toBe(false);
    input.value = "Also compare it with theorem 2.";
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(handlers.onSend).toHaveBeenCalledWith("Also compare it with theorem 2.");
    expect(handlers.onStop).not.toHaveBeenCalled();

    input.value = "And keep the page citations.";
    const followUp = body.querySelector<HTMLButtonElement>('button[title="Send Follow-up"]')!;
    followUp.click();
    expect(handlers.onSend).toHaveBeenLastCalledWith("And keep the page citations.");

    const stop = body.querySelector<HTMLButtonElement>('button[title="Stop Generating (Esc)"]')!;
    expect(stop.hidden).toBe(false);
    stop.click();
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(handlers.onStop).toHaveBeenCalledTimes(2);
  });

  it("renders the selected model's reasoning efforts and uses its advertised default", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState({
      phase: "ready",
      models: [{
        id: "gpt-5.6-sol",
        label: "GPT-5.6 Sol",
        supportedReasoningEfforts: [
          { reasoningEffort: "low" },
          { reasoningEffort: "max" },
          { reasoningEffort: "ultra", description: "Automatic task delegation" }
        ],
        defaultReasoningEffort: "low",
        isDefault: true
      }],
      selectedModel: "gpt-5.6-sol",
      effort: "medium"
    });

    const select = body.querySelector<HTMLSelectElement>('select[title="Reasoning Effort"]')!;
    expect([...select.options].map((option) => option.value)).toEqual(["low", "max", "ultra"]);
    expect(select.value).toBe("low");
    expect([...select.options].map((option) => option.textContent)).toContain("Reasoning: Ultra");
  });

  it("shows ChatGPT login without exposing a token field", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = callbacks();
    const view = new SidebarView(body, handlers);
    view.setState({ phase: "signed-out" });
    const button = [...body.querySelectorAll("button")]
      .find((candidate) => candidate.textContent === "Sign In with ChatGPT")!;
    button.click();
    expect(handlers.onLogin).toHaveBeenCalledOnce();
    expect(body.querySelector('input[type="password"]')).toBeNull();
  });

  it("renders the paper-trail consent card and forwards decisions", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = { ...callbacks(), onPaperTrailConsent: vi.fn() };
    const view = new SidebarView(body, handlers as any);
    view.setState({ phase: "ready", paperTrailConsent: { question: "为什么?", pageNumber: 7 } });
    expect(body.textContent).toContain("Create highlight annotation automatically");
    const buttons = [...body.querySelectorAll(".zc-consent-card button")];
    (buttons.find((b) => b.textContent?.includes("Allow")) as HTMLButtonElement).click();
    expect(handlers.onPaperTrailConsent).toHaveBeenCalledWith("accept");
  });

  it("never renders an Agent/Ask mode toggle", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState({
      ...baseState(),
      capabilities: { supportsAgentMode: false, supportsLogin: false },
    } as any);
    expect(body.querySelector(".zc-mode-picker")).toBeNull();
  });

  it("hides the ChatGPT login button when supportsLogin is false", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState({
      phase: "signed-out",
      capabilities: { supportsAgentMode: true, supportsLogin: false },
    } as any);
    expect(body.querySelector(".zc-login-button")).toBeNull();
  });

  it("does not render question-anchor tags in the chat", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks() as any);
    view.setState({ ...baseState(), anchors: [
      { anchorId: "a1", pageNumber: 3, question: "为什么收敛?", status: "open" },
      { anchorId: "a2", pageNumber: 9, question: "数据集?", status: "resolved" },
    ] } as any);
    expect(body.querySelector(".zc-question-list")).toBeNull();
    expect(body.querySelector(".zc-question-item")).toBeNull();
  });

  it("hides the question list when there are no anchors", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks() as any);
    view.setState({ ...baseState(), anchors: [] } as any);
    expect(body.querySelector(".zc-question-list")).toBeNull();
  });

  it("renders the noting preview card with stats and apply", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = { ...callbacks(), onNotingApply: vi.fn(), onNotingCancel: vi.fn() };
    const view = new SidebarView(body, handlers as any);
    view.setState({ ...baseState(), noting: {
      phase: "preview", markdown: "# Citation\n\n内容", mathErrors: 2,
      anchorCount: 5, openCount: 1, hashMismatch: false,
      versions: [{ key: "OLD", title: "old-notes" }], error: null,
    } } as any);
    const card = body.querySelector(".zc-noting-card")!;
    expect(card.textContent).toContain("5 anchors");
    expect(card.textContent).toContain("2 formulas to verify");
    (card.querySelector(".zc-noting-apply") as HTMLButtonElement).click();
    expect(handlers.onNotingApply).toHaveBeenCalledWith({ kind: "new" });
  });

  it("keeps the Workbench launcher but removes the redundant chat-to-draft button", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = {
      ...callbacks(),
      onOpenWorkbench: vi.fn(),
      onCaptureChatDraft: vi.fn(),
    };
    const view = new SidebarView(body, handlers as any);
    view.setState(baseState() as any);
    (body.querySelector('[title="Open the QLab Workbench in a Zotero tab"]') as HTMLButtonElement).click();
    expect(handlers.onOpenWorkbench).toHaveBeenCalled();
    expect(body.querySelector('[title="Summarize this chat into a Draft"]')).toBeNull();
    expect(handlers.onCaptureChatDraft).not.toHaveBeenCalled();
  });

  it("uses the complete chat UI once in workbench mode and lets an empty tab choose a paper", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = { ...callbacks(), onChoosePaper: vi.fn(), onOpenPaper: vi.fn() };
    const view = new SidebarView(body, handlers, { surface: "workbench" });
    view.show();
    view.setState({ ...baseState(), context: null } as any);

    const root = body.querySelector<HTMLElement>(".zc-sidebar.zc-workbench-chat")!;
    expect(root.getAttribute("role")).toBe("main");
    expect(root.querySelector(".zc-topbar")).toBeNull();
    expect(root.querySelector(":scope > .zc-workbench-dock")).not.toBeNull();
    expect(root.querySelector<HTMLButtonElement>(".zc-workbench-open")!.hidden).toBe(true);
    expect(root.querySelectorAll(".zc-qlab-command-button")).toHaveLength(0);
    const choose = root.querySelector<HTMLButtonElement>(".zc-choose-paper")!;
    expect(choose.textContent).toBe("Choose Paper");
    expect((body.querySelector(".zc-composer-input") as HTMLTextAreaElement).placeholder).toBe("Message QLab…");
    expect(root.querySelector<HTMLButtonElement>(".zc-open-paper")!.hidden).toBe(true);
    const terminal = root.querySelector<HTMLButtonElement>(".zc-terminal-button")!;
    const mainSite = root.querySelector<HTMLButtonElement>(".zc-main-site-button")!;
    const account = root.querySelector<HTMLButtonElement>('button[title="Account"]')!;
    for (const button of [mainSite, terminal, account]) {
      expect(button.querySelector("svg.zc-button-icon")).not.toBeNull();
      expect(button.querySelector(".zc-button-label")).toBeNull();
      expect(button.textContent).toBe("");
      expect(button.title.length).toBeGreaterThan(0);
    }
    terminal.click();
    expect(handlers.onOpenTerminal).toHaveBeenCalledOnce();
    view.setTerminalOpen(true);
    expect(view.isTerminalOpen()).toBe(true);
    expect(view.terminalHost().classList.contains("is-open")).toBe(true);
    expect(terminal.getAttribute("aria-pressed")).toBe("true");
    choose.click();
    expect(handlers.onChoosePaper).toHaveBeenCalledOnce();

    view.setState({ context: { key: "1-A", title: "Paper A" } as any });
    expect(choose.textContent).toBe("Change Paper");
    const openPaper = root.querySelector<HTMLButtonElement>(".zc-open-paper")!;
    expect(openPaper.hidden).toBe(false);
    openPaper.click();
    expect(handlers.onOpenPaper).toHaveBeenCalledOnce();
    expect((body.querySelector(".zc-composer-input") as HTMLTextAreaElement).placeholder).toBe("Ask about this paper…");
  });

  it("checks the main site and opens it from one workbench button", async () => {
    const browser = document.createElement("browser");
    const createXULElement = vi.fn(() => browser);
    (document as any).createXULElement = createXULElement;
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = {
      ...callbacks(),
      onCheckMainSite: vi.fn(async () => true),
      onDeployMainSite: vi.fn(async () => undefined),
    };
    const view = new SidebarView(body, handlers, { surface: "workbench" });
    await vi.waitFor(() => {
      expect(body.querySelector<HTMLButtonElement>(".zc-main-site-button")!.title)
        .toBe("Open the Research Loop main site in Zotero");
    });

    const button = body.querySelector<HTMLButtonElement>(".zc-main-site-button")!;
    button.click();
    await vi.waitFor(() => expect(createXULElement).toHaveBeenCalledWith("browser"));

    expect(handlers.onDeployMainSite).not.toHaveBeenCalled();
    expect(browser.getAttribute("src")).toBe("http://127.0.0.1:4180/");
    expect(body.querySelector(".zc-workbench-chat")!.classList.contains("is-main-site-open")).toBe(true);
    expect(button.getAttribute("aria-pressed")).toBe("true");
    expect((body.querySelector(".zc-transcript") as HTMLElement).hidden).toBe(false);
    expect((body.querySelector(".zc-composer-wrap") as HTMLElement).hidden).toBe(false);

    const styles = readFileSync(join(process.cwd(), "src", "styles.css"), "utf8");
    // The chat column is a draggable share, not a fixed 40%, and the middle
    // track is the handle — so the site view is column 3.
    expect(styles).toContain(
      "grid-template-columns: minmax(280px, var(--zc-split-ratio, 40%)) 6px minmax(300px, 1fr);",
    );
    expect(styles).toContain(
      ".zc-workbench-chat.is-main-site-open > .zc-main-site-view {\n  grid-column: 3;\n  grid-row: 1 / -1;",
    );
    expect(styles).not.toContain(
      ".zc-workbench-chat.is-main-site-open > .zc-transcript,\n.zc-workbench-chat.is-main-site-open > .zc-composer-wrap",
    );

    body.querySelector<HTMLButtonElement>(".zc-main-site-back")!.click();
    expect(body.querySelector(".zc-workbench-chat")!.classList.contains("is-main-site-open")).toBe(false);
    expect(button.getAttribute("aria-pressed")).toBe("false");
    view.destroy();
  });

  it("offers deployment when the main site is offline and opens it after startup", async () => {
    const browser = document.createElement("browser");
    (document as any).createXULElement = vi.fn(() => browser);
    const body = document.createElement("div");
    document.body.appendChild(body);
    const handlers = {
      ...callbacks(),
      onCheckMainSite: vi.fn(async () => false),
      onDeployMainSite: vi.fn(async () => undefined),
    };
    new SidebarView(body, handlers, { surface: "workbench" });
    const button = body.querySelector<HTMLButtonElement>(".zc-main-site-button")!;
    await vi.waitFor(() => expect(button.title).toBe("The main site is not running; click to build and start it"));
    expect(button.classList.contains("is-offline")).toBe(true);

    button.click();
    expect(button.title).toBe("Building and starting the Research Loop main site");
    await vi.waitFor(() => expect(handlers.onDeployMainSite).toHaveBeenCalledOnce());
    await vi.waitFor(() => expect(button.title).toBe("Open the Research Loop main site in Zotero"));
    expect(body.querySelector(".zc-workbench-chat")!.classList.contains("is-main-site-open")).toBe(true);
  });

  it.each(["empty", "partial"] as const)(
    "offers Initialize for a %s Research Loop directory",
    async (repositoryState) => {
      const browser = document.createElement("browser");
      (document as any).createXULElement = vi.fn(() => browser);
      const body = document.createElement("div");
      document.body.appendChild(body);
      const handlers = {
        ...callbacks(),
        onCheckMainSiteRepository: vi.fn(async () => repositoryState),
        onCheckMainSite: vi.fn(async () => true),
        onDeployMainSite: vi.fn(async (progress?: (message: string) => void) => {
          progress?.("Initializing Research Loop…");
        }),
      };
      new SidebarView(body, handlers, { surface: "workbench" });
      const button = body.querySelector<HTMLButtonElement>(".zc-main-site-button")!;

      await vi.waitFor(() => expect(button.title).toContain("Research Loop"));
      expect(button.classList.contains("is-initialize")).toBe(true);
      expect(handlers.onCheckMainSite).not.toHaveBeenCalled();
      button.click();
      await vi.waitFor(() => expect(handlers.onDeployMainSite).toHaveBeenCalledOnce());
      await vi.waitFor(() => expect(button.title).toBe("Open the Research Loop main site in Zotero"));
    },
  );

  it("sends an incompatible directory back to the folder picker without deploying", async () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    let repositoryState: "incompatible" | "empty" = "incompatible";
    const handlers = {
      ...callbacks(),
      onCheckMainSiteRepository: vi.fn(async () => repositoryState),
      onCheckMainSite: vi.fn(async () => false),
      onDeployMainSite: vi.fn(async () => undefined),
      onChooseQLabRoot: vi.fn(async () => { repositoryState = "empty"; }),
    };
    new SidebarView(body, handlers, { surface: "workbench" });
    const button = body.querySelector<HTMLButtonElement>(".zc-main-site-button")!;

    await vi.waitFor(() => expect(button.title).toBe("This folder contains unrelated files; choose an empty folder instead"));
    button.click();
    await vi.waitFor(() => expect(handlers.onChooseQLabRoot).toHaveBeenCalledOnce());
    await vi.waitFor(() => expect(button.classList.contains("is-initialize")).toBe(true));
    expect(handlers.onDeployMainSite).not.toHaveBeenCalled();
  });

  it("does not add a main-site button to the compact sidebar", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    new SidebarView(body, callbacks());
    expect(body.querySelector(".zc-main-site-button")).toBeNull();
  });
});

describe("SidebarView activity line", () => {
  beforeEach(() => {
    document.body.replaceChildren();
  });

  function mountSidebar(): { view: SidebarView; host: HTMLElement } {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const view = new SidebarView(host, callbacks());
    return { view, host };
  }

  it("collapses running process entries into a single activity line", () => {
    const { view, host } = mountSidebar();
    view.setState({
      running: true, turnStartedAt: Date.now(),
      entries: [
        { id: "u1", kind: "user", text: "问" },
        { id: "r1", kind: "reasoning", title: "Reasoning", text: "…", state: "complete" },
        { id: "t1", kind: "tool", title: "zotero_read_pdf_pages", text: "", state: "running" },
      ],
    });
    expect(host.querySelectorAll(".zc-tool-card").length).toBe(0);
    const label = host.querySelector(".zc-activity-label")!;
    expect(label.textContent).toBe("Calling Read Paper Pages");
  });

  it("renders an expandable summary line after completion", () => {
    const { view, host } = mountSidebar();
    view.setState({
      running: false, turnDurations: { u1: 28_000 },
      entries: [
        { id: "u1", kind: "user", text: "问" },
        { id: "t1", kind: "tool", title: "zotero_read_pdf_pages", text: "done", state: "complete" },
        { id: "a1", kind: "assistant", text: "答", state: "complete" },
      ],
    });
    expect(host.querySelector(".zc-activity")).toBeNull();
    const summary = host.querySelector(".zc-turn-summary")!;
    expect(summary.textContent).toContain("28s");
    expect(summary.textContent).toContain("1 steps");
    expect(host.querySelector(".zc-turn-detail")).toBeNull();
    (summary as HTMLElement).click();
    expect(host.querySelectorAll(".zc-turn-detail .zc-tool-card").length).toBe(1);
    (summary as HTMLElement).click();
    expect(host.querySelector(".zc-turn-detail")).toBeNull();
  });

  it("omits the summary line when there is nothing to report", () => {
    const { view, host } = mountSidebar();
    view.setState({ running: false, turnDurations: {}, entries: [
      { id: "u1", kind: "user", text: "问" },
      { id: "a1", kind: "assistant", text: "答", state: "complete" },
    ]});
    expect(host.querySelector(".zc-turn-summary")).toBeNull();
  });

  it("reuses the same .zc-activity DOM node across renders while streaming (I2), only updating its label text", () => {
    const { view, host } = mountSidebar();
    view.setState({
      running: true,
      turnStartedAt: Date.now(),
      entries: [
        { id: "u1", kind: "user", text: "问" },
        { id: "r1", kind: "reasoning", text: "…", state: "running" },
      ],
    });
    const node = host.querySelector(".zc-activity");
    expect(node).not.toBeNull();
    expect(host.querySelector(".zc-activity-label")?.textContent).toBe("Thinking…");

    // A streaming delta re-renders the whole transcript; the spinner/shimmer
    // node identity must be stable so its CSS animation is not restarted.
    view.setState({
      entries: [
        { id: "u1", kind: "user", text: "问" },
        { id: "t1", kind: "tool", title: "zotero_read_pdf_pages", text: "", state: "running" },
      ],
    });

    expect(host.querySelector(".zc-activity")).toBe(node);
    expect(host.querySelector(".zc-activity-label")?.textContent).toBe("Calling Read Paper Pages");
  });

  describe("pinned autoscroll", () => {
    // happy-dom's scrollHeight/clientHeight getters are hardcoded to 0, so a
    // real "is the transcript visually at the bottom" check is unavailable
    // here. We shadow those getters with own properties on the live
    // `.zc-transcript` element to fake realistic geometry, which lets us
    // drive the `scroll` listener's `pinnedToBottom` computation and then
    // observe the resulting `scrollTop` writes the implementation performs.
    function fakeGeometry(transcript: HTMLElement, scrollHeight: number, clientHeight: number): void {
      Object.defineProperty(transcript, "scrollHeight", { value: scrollHeight, configurable: true });
      Object.defineProperty(transcript, "clientHeight", { value: clientHeight, configurable: true });
    }

    it("autoscrolls after every render while pinned, stops once the user scrolls away, and catches up again on a thread switch", () => {
      const { view, host } = mountSidebar();
      const transcript = host.querySelector<HTMLElement>(".zc-transcript")!;
      fakeGeometry(transcript, 500, 100);

      // Default `pinnedToBottom = true`, and autoscroll now fires on every
      // render (not just while `running`).
      view.setState({
        running: false,
        entries: [{ id: "u1", kind: "user", text: "问" }],
      });
      expect(transcript.scrollTop).toBe(500);

      // User scrolls away from the bottom -> the scroll listener unpins.
      transcript.scrollTop = 0;
      transcript.dispatchEvent(new Event("scroll"));

      // A same-thread render must not snap the user back to the bottom.
      view.setState({
        entries: [
          { id: "u1", kind: "user", text: "问" },
          { id: "a1", kind: "assistant", text: "答" },
        ],
      });
      expect(transcript.scrollTop).toBe(0);

      // Switching the active thread id must re-pin and catch up to the
      // bottom even though the user never touched the scrollbar again.
      view.setState({
        threads: [{ id: "thread-a", title: "A", updatedAt: "2026-07-22", active: true }],
      });
      expect(transcript.scrollTop).toBe(500);

      // Scroll away again, then re-render the *same* active thread: still
      // must not be forced back to the bottom (no thread-id change).
      transcript.scrollTop = 0;
      transcript.dispatchEvent(new Event("scroll"));
      view.setState({
        threads: [{ id: "thread-a", title: "A", updatedAt: "2026-07-22", active: true }],
        entries: [
          { id: "u1", kind: "user", text: "问" },
          { id: "a1", kind: "assistant", text: "答 2" },
        ],
      });
      expect(transcript.scrollTop).toBe(0);

      // Switching to a different active thread id catches up again.
      view.setState({
        threads: [
          { id: "thread-a", title: "A", updatedAt: "2026-07-22", active: false },
          { id: "thread-b", title: "B", updatedAt: "2026-07-22", active: true },
        ],
      });
      expect(transcript.scrollTop).toBe(500);
    });
  });

  describe("activity timer lifecycle", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("updates only the elapsed text node once per second while running", () => {
      const { view, host } = mountSidebar();
      // Offset so each 1000ms tick crosses a whole-second rounding boundary
      // (formatElapsed rounds ms/1000), making the text change predictably.
      const startedAt = Date.now() - 700;
      view.setState({
        running: true,
        turnStartedAt: startedAt,
        entries: [{ id: "u1", kind: "user", text: "问" }],
      });
      const label = host.querySelector(".zc-activity-label")!;
      const elapsed = host.querySelector(".zc-activity-elapsed")!;
      expect(elapsed.textContent).toBe("1s");

      vi.advanceTimersByTime(1000);
      expect(host.querySelector(".zc-activity-elapsed")?.textContent).toBe("2s");
      // Only the elapsed text changed; the rest of the activity line (and
      // the DOM node itself) was not touched by a full re-render.
      expect(host.querySelector(".zc-activity-label")).toBe(label);
      expect(host.querySelector(".zc-activity-elapsed")).toBe(elapsed);

      vi.advanceTimersByTime(1000);
      expect(elapsed.textContent).toBe("3s");
      expect(host.querySelector(".zc-activity-elapsed")).toBe(elapsed);
    });

    it("does not start a second interval on repeated setState while running", () => {
      const { view } = mountSidebar();
      const setIntervalSpy = vi.spyOn(window, "setInterval");
      view.setState({
        running: true,
        turnStartedAt: Date.now(),
        entries: [{ id: "u1", kind: "user", text: "问" }],
      });
      expect(setIntervalSpy).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(1);

      view.setState({
        entries: [
          { id: "u1", kind: "user", text: "问" },
          { id: "r1", kind: "reasoning", text: "思考", state: "running" },
        ],
      });
      view.setState({
        entries: [
          { id: "u1", kind: "user", text: "问" },
          { id: "r1", kind: "reasoning", text: "Thinking…", state: "running" },
        ],
      });

      expect(setIntervalSpy).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(1);
    });

    it("clears the interval once running turns false", () => {
      const { view } = mountSidebar();
      view.setState({
        running: true,
        turnStartedAt: Date.now(),
        entries: [{ id: "u1", kind: "user", text: "问" }],
      });
      expect(vi.getTimerCount()).toBe(1);

      const clearIntervalSpy = vi.spyOn(window, "clearInterval");
      view.setState({ running: false });

      expect(clearIntervalSpy).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(0);
    });

    it("clears the interval on destroy", () => {
      const { view } = mountSidebar();
      view.setState({
        running: true,
        turnStartedAt: Date.now(),
        entries: [{ id: "u1", kind: "user", text: "问" }],
      });
      expect(vi.getTimerCount()).toBe(1);

      view.destroy();

      expect(vi.getTimerCount()).toBe(0);
    });
  });
});

describe("Reader pane layout CSS", () => {
  it("uses a bounded compact grid without a transcript minimum that can push the composer below the pane", () => {
    const styles = readFileSync(join(process.cwd(), "src/styles.css"), "utf8");
    expect(styles).toContain("grid-template-rows: auto auto auto minmax(0, 1fr) auto");
    expect(styles).toContain("height: clamp(420px, 72vh, 780px)");
    expect(styles).toContain(".zc-composer-wrap { grid-row: 5; position: sticky; bottom: 0;");
    expect(styles).toContain(".zc-context-menu { position: absolute;");
    expect(styles).toContain("grid-auto-rows: minmax(40px, auto)");
    expect(styles).toContain(".zc-context-option { display: grid;");
    expect(styles).toContain("min-height: 40px");
    // The optional formula rail is hidden by default. Pin the terminal surface
    // to the final flexible row so CSS Grid does not leave xterm at 0px tall.
    expect(styles).toContain(".zc-terminal-surface { grid-row: 4;");
    expect(styles).not.toContain("minmax(320px, 1fr)");
    expect(styles).not.toContain("min-height: 610px");
    expect(styles).not.toContain("min-height: 560px");
  });

  it("responds to the Zotero pane width instead of the application viewport", () => {
    const styles = readFileSync(join(process.cwd(), "src/styles.css"), "utf8");
    expect(styles).toContain("container-name: zotkit-pane");
    expect(styles).toContain("container-type: inline-size");
    expect(styles).toContain("@container zotkit-pane (max-width: 420px)");
    expect(styles).toContain("@container zotkit-pane (max-width: 340px)");
    expect(styles).toContain("grid-template-columns: auto minmax(0, 1fr)");
    expect(styles).not.toContain("@media (max-width: 420px)");
  });

  it("keeps the QLab command bar inside the pane's containing block", () => {
    const styles = readFileSync(join(process.cwd(), "src/styles.css"), "utf8");
    expect(styles).toContain(".zc-pane-host {\n  position: relative;");
    expect(styles).toContain(".zc-qlab-bar {");
  });
});

describe("renderMarkdown", () => {
  it("does not interpret model-provided HTML", () => {
    const host = document.createElement("div");
    host.appendChild(renderMarkdown(document, '<img src=x onerror="alert(1)">'));
    expect(host.querySelector("img")).toBeNull();
    expect(host.textContent).toContain("<img");
  });
});

describe("SidebarView top-bar menus", () => {
  beforeEach(() => {
    document.body.replaceChildren();
    delete (document as any).createXULElement;
  });

  it("opens the account and history menus inside the actions row, not at the window edge", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks());
    view.setState(baseState() as any);

    const actions = body.querySelector(".zc-top-actions")!;
    body.querySelector<HTMLButtonElement>('button[title="Account"]')!.click();
    expect(actions.querySelector(".zc-account-menu")).not.toBeNull();

    body.querySelector<HTMLButtonElement>('button[title="Conversation History"]')!.click();
    expect(actions.querySelector(".zc-history-menu")).not.toBeNull();
    // Anchoring is what keeps them under their button once the workbench
    // layout gives the root a second column.
    expect(body.querySelector(".zc-sidebar > .zc-account-menu")).toBeNull();
    expect(body.querySelector(".zc-sidebar > .zc-history-menu")).toBeNull();
    view.destroy();
  });

  it("remembers the chat/pane ratio a drag produced", () => {
    const body = document.createElement("div");
    document.body.appendChild(body);
    const view = new SidebarView(body, callbacks(), { surface: "workbench" });
    const root = body.querySelector<HTMLElement>(".zc-workbench-chat")!;
    const handle = root.querySelector<HTMLElement>(".zc-split-handle")!;

    // happy-dom performs no layout, so the pane geometry has to be supplied.
    root.getBoundingClientRect = () => ({
      left: 0, right: 1000, top: 0, bottom: 800, width: 1000, height: 800, x: 0, y: 0,
      toJSON: () => ({}),
    }) as DOMRect;

    handle.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, clientX: 400 }));
    window.dispatchEvent(new MouseEvent("mousemove", { bubbles: true, clientX: 550 }));
    window.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));

    expect(root.style.getPropertyValue("--zc-split-ratio")).toBe("55%");

    const secondHost = document.body.appendChild(document.createElement("div"));
    const second = new SidebarView(secondHost, callbacks(), { surface: "workbench" });
    expect(secondHost.querySelector<HTMLElement>(".zc-workbench-chat")!
      .style.getPropertyValue("--zc-split-ratio")).toBe("55%");
    second.destroy();
    view.destroy();
  });
});
