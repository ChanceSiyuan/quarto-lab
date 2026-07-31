// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  MAX_SELECTION_PROMPT_CHARACTERS,
  ZoteroChatPlugin,
  buildSelectionPrompt,
  clampFloatOpacity,
  clampFloatSize,
  draftChangeRebaseAction,
  formatPendingApprovalDescription,
  pdfDirectory,
  pdfSourceMatchesConversationPaper,
  pdfSourceMatchesReaderContext,
} from "../src/plugin";
import type { ReaderContext } from "../src/reader-context";

describe("Zotkit Reader terminal state", () => {
  it("matches only PDF links that identify the conversation paper", () => {
    const context = {
      parent: { url: "https://arxiv.org/abs/2306.13123v2" },
      attachment: {},
    } as ReaderContext;

    expect(pdfSourceMatchesReaderContext(
      "https://arxiv.org/pdf/2306.13123v2.pdf#page=6",
      context,
    )).toBe(true);
    expect(pdfSourceMatchesReaderContext(
      "https://example.org/another-paper.pdf#page=6",
      context,
    )).toBe(false);
  });

  it("matches page links to an explicitly attached secondary paper", () => {
    expect(pdfSourceMatchesConversationPaper(
      "https://arxiv.org/pdf/2401.01234.pdf#page=9",
      { sourceUrls: ["https://arxiv.org/abs/2401.01234"], dois: [] },
    )).toBe(true);
    expect(pdfSourceMatchesConversationPaper(
      "https://example.org/unrelated.pdf#page=9",
      { sourceUrls: ["https://arxiv.org/abs/2401.01234"], dois: [] },
    )).toBe(false);
  });

  it("treats a Cursor save as the new Draft baseline without discarding a real AI version", () => {
    expect(draftChangeRebaseAction("old-original", "cursor-save", "ai-version"))
      .toBe("preserve-ai-version");
  });

  it("moves an untouched AI working copy forward when Cursor saves the original Draft", () => {
    expect(draftChangeRebaseAction("old-original", "cursor-save", "old-original"))
      .toBe("refresh-working-copy");
    expect(draftChangeRebaseAction("same", "same", "ai-version"))
      .toBe("already-current");
  });

  it("creates every legal Draft staging parent without rejecting intermediate work directories", async () => {
    const originalComponents = (globalThis as any).Components;
    const originalIOUtils = (globalThis as any).IOUtils;
    const originalPathUtils = (globalThis as any).PathUtils;
    const directories = new Set(["/repo"]);
    const makeDirectory = vi.fn(async (path: string) => {
      const parent = path.slice(0, path.lastIndexOf("/")) || "/";
      if (!directories.has(parent)) throw new Error(`missing parent ${parent}`);
      directories.add(path);
    });
    (globalThis as any).PathUtils = { join: (...parts: string[]) => parts.join("/").replace(/\/{2,}/g, "/") };
    (globalThis as any).IOUtils = {
      exists: async (path: string) => directories.has(path),
      makeDirectory,
    };
    (globalThis as any).Components = {
      interfaces: { nsIFile: {} },
      classes: {
        "@mozilla.org/file/local;1": {
          createInstance: () => {
            let path = "";
            return {
              initWithPath(value: string) { path = value; },
              exists: () => directories.has(path),
              isSymlink: () => false,
              isDirectory: () => directories.has(path),
              normalize: () => {},
              get path() { return path; },
            };
          },
        },
      },
    };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.settings = { qlabRoot: "/repo" };

    try {
      await plugin.ensureSafeChangeDirectory(
        `work/qlab-zotero/draft-changes/${"a".repeat(64)}`,
      );
      expect([...directories]).toEqual([
        "/repo",
        "/repo/work",
        "/repo/work/qlab-zotero",
        "/repo/work/qlab-zotero/draft-changes",
        `/repo/work/qlab-zotero/draft-changes/${"a".repeat(64)}`,
      ]);
      expect(makeDirectory).toHaveBeenCalledTimes(4);
    }
    finally {
      (globalThis as any).Components = originalComponents;
      (globalThis as any).IOUtils = originalIOUtils;
      (globalThis as any).PathUtils = originalPathUtils;
    }
  });

  it("toggles the current-paper and current-page chips and the model context together", () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = {
      attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
      parent: { title: "Paper", creators: [], tags: [] },
      page: { pageNumber: 5, pageLabel: "5" },
    };
    plugin.codex = {
      setReaderContextSelection: vi.fn(),
      setInteractionContext: vi.fn(),
    };
    plugin.renderChatViews = vi.fn();

    plugin.removeInteractionContext("active-paper");
    expect(plugin.contextChips().map((chip: { id: string }) => chip.id)).toEqual(["current-page"]);
    expect(plugin.contextSuggestions().find((item: { id: string }) => item.id === "active-paper").disabled).toBe(false);
    expect(plugin.codex.setReaderContextSelection).toHaveBeenLastCalledWith({
      paper: false,
      page: true,
      selection: false,
    });

    plugin.removeInteractionContext("current-page");
    expect(plugin.contextChips()).toEqual([]);
    expect(plugin.codex.setReaderContextSelection).toHaveBeenLastCalledWith({
      paper: false,
      page: false,
      selection: false,
    });

    plugin.addInteractionContext({ id: "active-paper", kind: "paper", label: "Current Paper" });
    expect(plugin.contextChips().map((chip: { id: string }) => chip.id)).toEqual(["active-paper"]);
    expect(plugin.codex.setReaderContextSelection).toHaveBeenLastCalledWith({
      paper: true,
      page: false,
      selection: false,
    });
  });

  it("waits for a new Zotero window's native tab deck before migrating Workbench", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const source = { closed: false } as Window;
    const targetDocument = document.implementation.createHTMLDocument("Dedicated QLab");
    const target = { closed: false, document: targetDocument } as unknown as Window & { Zotero_Tabs?: any };
    let windows: Window[] = [source];
    (globalThis as any).Zotero = {
      getMainWindows: () => windows,
      openMainWindow: () => { windows = [source, target]; },
    };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.shortcutWindows = new Set([target]);
    let settled = false;

    try {
      const pending = plugin.openWorkbenchWindow(source).then((value: Window) => {
        settled = true;
        return value;
      });
      await new Promise((resolve) => setTimeout(resolve, 70));
      expect(settled).toBe(false);
      target.Zotero_Tabs = {
        add: vi.fn(),
        close: vi.fn(),
        tabHooks: {},
        _tabs: [
          { id: "zotero-pane", type: "library" },
          { id: "restored-reader", type: "reader" },
        ],
      };
      await expect(pending).resolves.toBe(target);
      expect(targetDocument.documentElement.getAttribute("data-qlab-workbench-window")).toBe("true");
      expect(target.Zotero_Tabs.close).toHaveBeenCalledWith(["restored-reader"]);
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("opens the paper bound to the QLab tab as a normal Zotero PDF tab", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const open = vi.fn(async () => ({}));
    (globalThis as any).Zotero = { Reader: { open } };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContextItem = vi.fn(() => ({ id: 42 }));

    try {
      await plugin.openContextPDF();
      expect(open).toHaveBeenCalledWith(42, null, {
        allowDuplicate: false,
        openInBackground: false,
        preventJumpback: false,
      });
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("opens a QLab-only window's paper in a standalone Reader window", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const open = vi.fn(async () => ({}));
    (globalThis as any).Zotero = { Reader: { open } };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContextItem = vi.fn(() => ({ id: 42 }));

    try {
      await plugin.openContextPDF(true);
      expect(open).toHaveBeenCalledWith(42, null, {
        allowDuplicate: false,
        openInBackground: false,
        preventJumpback: false,
        openInWindow: true,
      });
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("keeps Change Paper from adding a PDF tab to a QLab-only window", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let resolveSelection!: () => void;
    const deferred = {
      promise: new Promise<void>((resolve) => { resolveSelection = resolve; }),
      resolve: () => resolveSelection(),
    };
    const attachment = {
      id: 42,
      key: "PAPER",
      libraryID: 1,
      title: "Dedicated Paper",
      creators: [],
      isPDFAttachment: () => true,
    };
    const reader = { itemID: 42 };
    const open = vi.fn(async () => reader);
    (globalThis as any).Zotero = {
      Promise: { defer: () => deferred },
      Items: { getAsync: vi.fn(async () => attachment) },
      Reader: { open },
      Session: { debounceSave: vi.fn() },
    };
    const targetDocument = document.implementation.createHTMLDocument("Dedicated QLab");
    targetDocument.documentElement.setAttribute("data-qlab-workbench-window", "true");
    const target = {
      document: targetDocument,
      setTimeout,
      openDialog: vi.fn((_url: string, _name: string, _features: string, io: any) => {
        io.dataOut = [42];
        io.deferred.resolve();
      }),
    } as unknown as Window;
    const accepted = { attachment, parent: { title: "Dedicated Paper", creators: [] } };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContext = { acceptReaderHook: vi.fn(async () => accepted) };
    plugin.addedContextIDs = new Set();
    plugin.contextRequestSequence = 0;
    plugin.applyContext = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();
    plugin.workbenchTabs = {
      update: vi.fn(),
      entries: vi.fn(() => []),
    };

    try {
      await plugin.chooseWorkbenchPaper(target, "qlab-tab");
      expect(open).toHaveBeenCalledWith(42, null, {
        allowDuplicate: false,
        openInBackground: true,
        preventJumpback: true,
        openInWindow: true,
      });
      expect(plugin.applyContext).toHaveBeenCalledWith(accepted, 1);
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("opens page citations in the selected conversation PDF without changing or interrupting chat state", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const open = vi.fn(async () => ({}));
    const conversationAttachment = { id: 42, key: "PAPER-A" };
    const focusedAttachment = { id: 84, key: "PAPER-B" };
    const getByLibraryAndKey = vi.fn((_libraryID: number, key: string) => (
      key === "PAPER-A" ? conversationAttachment : focusedAttachment
    ));
    (globalThis as any).Zotero = { Reader: { open }, Items: { getByLibraryAndKey } };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = { attachment: { id: 84, libraryID: 1, key: "PAPER-B" } };
    plugin.codex = {
      getActiveReaderContext: vi.fn(() => ({
        attachment: { id: 42, libraryID: 1, key: "PAPER-A" },
      })),
      interrupt: vi.fn(),
    };

    try {
      await plugin.openConversationPDFPage(6, true);
      expect(getByLibraryAndKey).toHaveBeenCalledWith(1, "PAPER-A");
      expect(open).toHaveBeenCalledWith(42, { pageIndex: 5 }, {
        allowDuplicate: false,
        openInBackground: false,
        preventJumpback: false,
        openInWindow: true,
      });
      expect(plugin.codex.interrupt).not.toHaveBeenCalled();
      expect(plugin.context.attachment.key).toBe("PAPER-B");
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("starts an empty Workbench terminal at the configured QLab root", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const host = document.createElement("div");
    plugin.settings = { qlabRoot: "/research/quarto-lab" };
    plugin.context = null;
    plugin.readerContext = {
      getCachedZotkitLibrarySnapshotReference: vi.fn(() => null),
      ensureCurrentPdfTextReference: vi.fn(),
    };

    const options = await plugin.terminalOptions(host);

    expect(options).toMatchObject({
      host,
      paperTitle: "QLab Repository",
      workspace: "/research/quarto-lab",
      workingDirectory: "/research/quarto-lab",
      pdfPath: null,
      agent: "shell",
    });
    expect(plugin.readerContext.ensureCurrentPdfTextReference).not.toHaveBeenCalled();
  });

  it("shows exact requested permissions in the approval description", () => {
    const description = formatPendingApprovalDescription({
      description: "Stage a generated PDF",
      cwd: "/profile/papers/1-ATTACH",
      requestedPermissions: {
        network: { enabled: true },
        fileSystem: {
          entries: [{
            access: "write",
            path: { type: "path", path: "/profile/papers/1-ATTACH/staging" },
          }],
        },
      },
    });

    expect(description).toContain("Stage a generated PDF");
    expect(description).toContain('"network":{"enabled":true}');
    expect(description).toContain("/profile/papers/1-ATTACH/staging");
  });

  it("matches Cursor's Reader shortcuts while leaving editable controls alone", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.openWorkbenchTab = vi.fn(async () => {});
    plugin.openChatWithSelection = vi.fn(async () => {});
    plugin.openWorkbenchTerminal = vi.fn(async () => {});
    plugin.installShortcutHandler(window);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "i", metaKey: true, bubbles: true }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "l", metaKey: true, bubbles: true }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "L", metaKey: true, shiftKey: true, bubbles: true }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "j", metaKey: true, shiftKey: true, bubbles: true }));
    await Promise.resolve();

    expect(plugin.openWorkbenchTab).toHaveBeenCalledWith(window);
    expect(plugin.openChatWithSelection).toHaveBeenNthCalledWith(1, true);
    expect(plugin.openChatWithSelection).toHaveBeenNthCalledWith(2, false);
    expect(plugin.openWorkbenchTerminal).toHaveBeenCalledWith(window);

    const input = document.createElement("input");
    document.body.appendChild(input);
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "i", metaKey: true, bubbles: true }));
    expect(plugin.openWorkbenchTab).toHaveBeenCalledOnce();
    plugin.removeShortcutHandler(window);
    input.remove();
  });

  it("adds ⌘K to the Reader shortcuts and leaves editable controls alone", () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.toggleFloatPanel = vi.fn(async () => {});
    plugin.installShortcutHandler(window);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
    expect(plugin.toggleFloatPanel).toHaveBeenCalledOnce();

    const input = document.createElement("input");
    document.body.appendChild(input);
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
    expect(plugin.toggleFloatPanel).toHaveBeenCalledOnce();
    plugin.removeShortcutHandler(window);
    input.remove();
  });

  it("toggleFloatPanel opens with the cached selection attached, then closes and restores focus", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const focusTarget = document.createElement("button");
    document.body.appendChild(focusTarget);
    focusTarget.focus();
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = { setInteractionContext: vi.fn(), state: { connected: false } };
    plugin.context = {
      selection: { text: "chosen theorem", pageNumber: 3 },
      page: { pageNumber: 3 },
    };
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();
    plugin.reportError = vi.fn();

    await plugin.toggleFloatPanel();
    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.hidden).toBe(false);
    expect(plugin.addedContextIDs.has("current-selection")).toBe(true);
    expect(plugin.ensureChatSession).toHaveBeenCalledOnce();
    expect(plugin.renderChatViews).toHaveBeenCalled();

    await plugin.toggleFloatPanel();
    expect(root.hidden).toBe(true);
    expect(document.activeElement).toBe(focusTarget);

    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    focusTarget.remove();
    (globalThis as any).Zotero = previousZotero;
  });

  it("toggleFloatPanel opens without a chip when nothing is selected", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = { setInteractionContext: vi.fn(), state: { connected: false } };
    plugin.context = null;
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.toggleFloatPanel();
    expect(document.querySelector<HTMLElement>(".zc-float")!.hidden).toBe(false);
    expect(plugin.addedContextIDs.has("current-selection")).toBe(false);

    plugin.hideFloatPanel(window);
    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    (globalThis as any).Zotero = previousZotero;
  });

  it("renderFloatPanels keeps the floating chat compact by showing only the latest exchange", () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = {
      setInteractionContext: vi.fn(),
      state: {
        running: true,
        fallbackReason: null,
        models: [{ id: "gpt-5", label: "GPT-5" }, { id: "gpt-5-codex", label: "GPT-5 Codex" }],
        capabilities: { supportsAgentMode: true, supportsLogin: true },
      },
      getChatEntries: () => [
        { id: "u1", kind: "user", text: "old question" },
        { id: "a1", kind: "assistant", text: "old answer" },
        { id: "u2", kind: "user", text: "latest question" },
        { id: "a2", kind: "assistant", text: "latest answer" },
      ],
    };
    plugin.selectedModel = "gpt-5-codex";
    plugin.context = {
      selection: { text: "chosen theorem", pageNumber: 3 },
      page: { pageNumber: 3 },
      attachment: { title: "A Test Paper", creators: [] },
    };
    plugin.addedContextIDs.add("current-selection");
    plugin.chatPhase = "ready";
    const entry = plugin.mountFloatPanel(window);
    entry.view.show();

    plugin.renderFloatPanels();

    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.textContent).toContain("latest question");
    expect(root.textContent).not.toContain("old question");
    expect(root.textContent).toContain("Selected 14 characters");
    expect(root.querySelector<HTMLElement>(".zc-float-stop")!.hidden).toBe(false);
    expect(root.querySelector(".zc-float-title")?.textContent).toBe("QLab · A Test Paper");
    const modelSelect = root.querySelector<HTMLSelectElement>(".zc-float-model")!;
    expect(modelSelect.hidden).toBe(false);
    expect(modelSelect.value).toBe("gpt-5-codex");

    entry.view.destroy();
    entry.host.remove();
    plugin.floatPanels.clear();
    (globalThis as any).Zotero = previousZotero;
  });

  describe("float panel size persistence", () => {
    afterEach(() => {
      vi.unstubAllGlobals();
      vi.useRealTimers();
      // Defensive: a mid-assertion failure would otherwise skip the inline
      // `entry.host.remove()` cleanup below and leave a stale `.zc-float`
      // node in `document`, corrupting the next test's querySelector.
      document.querySelectorAll(".zc-float-host").forEach((node) => node.remove());
    });

    it("restores the persisted floatSize onto the panel as an inline style when mounting", () => {
      vi.stubGlobal("Services", {
        prefs: {
          getStringPref: (key: string, fallback: string) =>
            key === "extensions.zotkit.floatSize" ? "540x480" : fallback,
          setStringPref: () => {},
        },
      });

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;

      expect(root.style.width).toBe("540px");
      expect(root.style.height).toBe("480px");

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    it("ignores an unparsable persisted floatSize", () => {
      vi.stubGlobal("Services", {
        prefs: {
          getStringPref: (key: string, fallback: string) =>
            key === "extensions.zotkit.floatSize" ? "not-a-size" : fallback,
          setStringPref: () => {},
        },
      });

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;

      expect(root.style.width).toBe("");
      expect(root.style.height).toBe("");

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    function stubFakeResizeObserver(setStringPref = vi.fn(), getStringPref?: (key: string, fallback: string) => string): {
      setStringPref: ReturnType<typeof vi.fn>;
      getObservedCallback: () => ResizeObserverCallback;
    } {
      vi.stubGlobal("Services", {
        prefs: {
          getStringPref: getStringPref ?? ((_key: string, fallback: string) => fallback),
          setStringPref,
        },
      });
      let observedCallback: ResizeObserverCallback | null = null;
      class FakeResizeObserver {
        constructor(callback: ResizeObserverCallback) {
          observedCallback = callback;
        }
        observe(): void {}
        disconnect(): void {}
      }
      vi.stubGlobal("ResizeObserver", FakeResizeObserver);
      return { setStringPref, getObservedCallback: () => observedCallback! };
    }

    it("persists a grip-driven resize: the observer fires after the native `resize: both` grip writes inline style", () => {
      vi.useFakeTimers();
      const { setStringPref, getObservedCallback } = stubFakeResizeObserver();

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;
      const observedCallback = getObservedCallback();
      expect(observedCallback).not.toBeUndefined();

      // The initial notification reflects the panel's starting size (no
      // inline style change yet) and must not be persisted.
      observedCallback([{ contentRect: { width: 620, height: 400 } } as ResizeObserverEntry], {} as ResizeObserver);
      expect(setStringPref).not.toHaveBeenCalled();

      // Gecko's native `resize: both` grip writes inline style.width/height
      // directly on the element -- simulate the grip drag, then the
      // observer notification it triggers.
      root.style.width = "700px";
      root.style.height = "500px";
      observedCallback([{ contentRect: { width: 700, height: 500 } } as ResizeObserverEntry], {} as ResizeObserver);
      expect(setStringPref).not.toHaveBeenCalled();
      vi.advanceTimersByTime(499);
      expect(setStringPref).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1);
      expect(setStringPref).toHaveBeenCalledWith("extensions.zotkit.floatSize", "700x500");

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    it("does not persist a window-driven reflow that never touches the inline style", () => {
      vi.useFakeTimers();
      const { setStringPref, getObservedCallback } = stubFakeResizeObserver();

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const observedCallback = getObservedCallback();
      expect(observedCallback).not.toBeUndefined();

      observedCallback([{ contentRect: { width: 620, height: 400 } } as ResizeObserverEntry], {} as ResizeObserver);
      // A responsive reflow (e.g. the window shrinking so the CSS
      // `min(620px, 100vw - 48px)` bound recomputes) changes the observed
      // content box without ever writing to `style.width`/`style.height`.
      observedCallback([{ contentRect: { width: 500, height: 400 } } as ResizeObserverEntry], {} as ResizeObserver);
      vi.advanceTimersByTime(1000);
      expect(setStringPref).not.toHaveBeenCalled();

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    it("does not mistake clearing the inline height for an empty transcript as a user resize", () => {
      vi.useFakeTimers();
      const { setStringPref, getObservedCallback } = stubFakeResizeObserver(
        vi.fn(),
        (key, fallback) => (key === "extensions.zotkit.floatSize" ? "620x480" : fallback),
      );

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;
      expect(root.style.height).toBe("480px");
      const observedCallback = getObservedCallback();

      observedCallback([{ contentRect: { width: 620, height: 480 } } as ResizeObserverEntry], {} as ResizeObserver);

      entry.view.setState({ phase: "ready", entries: [] });
      expect(root.style.height).toBe("");

      // happy-dom never actually fires ResizeObserver callbacks, but a real
      // browser would notify it of the resulting content-box change; that
      // notification must not be mistaken for a user resize.
      observedCallback([{ contentRect: { width: 620, height: 220 } } as ResizeObserverEntry], {} as ResizeObserver);
      vi.advanceTimersByTime(1000);
      expect(setStringPref).not.toHaveBeenCalled();

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });

    it("clamps outlier resized dimensions before persisting them", () => {
      vi.useFakeTimers();
      const { setStringPref, getObservedCallback } = stubFakeResizeObserver();

      const plugin = new ZoteroChatPlugin() as any;
      const entry = plugin.mountFloatPanel(window);
      const root = document.querySelector<HTMLElement>(".zc-float")!;
      const observedCallback = getObservedCallback();

      observedCallback([{ contentRect: { width: 620, height: 400 } } as ResizeObserverEntry], {} as ResizeObserver);

      root.style.width = "50px";
      root.style.height = "5000px";
      observedCallback([{ contentRect: { width: 50, height: 5000 } } as ResizeObserverEntry], {} as ResizeObserver);
      vi.advanceTimersByTime(500);
      expect(setStringPref).toHaveBeenCalledWith("extensions.zotkit.floatSize", "380x2000");

      entry.view.destroy();
      entry.host.remove();
      plugin.floatPanels.clear();
    });
  });

  it("records turn duration keyed by the opening user entry when running flips off", () => {
    vi.useFakeTimers();
    try {
      const plugin = new ZoteroChatPlugin() as any;
      plugin.codex = {
        setInteractionContext: vi.fn(),
        state: {
          activeThreadId: "th1",
          running: true,
          fallbackReason: null,
          models: [],
          mode: "agent",
        },
        getChatEntries: () => [
          { id: "u1", kind: "user", text: "问" },
          { id: "a1", kind: "assistant", text: "答" },
        ],
        getActivePlan: () => null,
        getActiveDiffs: () => [],
        getPendingApprovals: () => [],
        getCheckpoints: () => [],
        getThreadOptions: () => [],
        isSignedIn: () => false,
      };

      vi.setSystemTime(new Date("2026-07-23T10:00:00Z"));
      plugin.renderChatViews();

      vi.setSystemTime(new Date("2026-07-23T10:00:28Z"));
      plugin.codex.state.running = false;
      plugin.renderChatViews();

      expect(plugin.turnDurationsForActiveThread()).toEqual({ u1: 28_000 });
    }
    finally {
      vi.useRealTimers();
    }
  });

  it("keeps a background thread timer alive across tab switches and completes it on return", () => {
    vi.useFakeTimers();
    try {
      const plugin = new ZoteroChatPlugin() as any;
      plugin.onTurnCompleted = vi.fn();
      plugin.codex = {
        setInteractionContext: vi.fn(),
        state: {
          activeThreadId: "A",
          running: true,
          fallbackReason: null,
          models: [],
          mode: "agent",
        },
        getChatEntries: () => [
          { id: "u1", kind: "user", text: "问 A" },
        ],
        getActivePlan: () => null,
        getActiveDiffs: () => [],
        getPendingApprovals: () => [],
        getCheckpoints: () => [],
        getThreadOptions: () => [],
        isSignedIn: () => false,
      };

      vi.setSystemTime(new Date("2026-07-23T10:00:00Z"));
      plugin.renderChatViews(); // Thread A starts running.

      // The user switches to idle thread B mid-turn; A continues in the background.
      vi.setSystemTime(new Date("2026-07-23T10:05:00Z"));
      plugin.codex.state.activeThreadId = "B";
      plugin.codex.state.running = false;
      plugin.codex.getChatEntries = () => [];
      plugin.renderChatViews();

      expect(plugin.turnDurationsForActiveThread()).toEqual({});
      expect(plugin.onTurnCompleted).not.toHaveBeenCalled();

      // Reopening A while it is still running resumes the same visible clock.
      plugin.codex.state.activeThreadId = "A";
      plugin.codex.state.running = true;
      plugin.codex.getChatEntries = () => [
        { id: "u1", kind: "user", text: "问 A" },
      ];
      plugin.renderChatViews();

      expect(plugin.turnDurationsForActiveThread()).toEqual({});
      expect(plugin.onTurnCompleted).not.toHaveBeenCalled();

      vi.setSystemTime(new Date("2026-07-23T10:06:00Z"));
      plugin.codex.state.running = false;
      plugin.renderChatViews();
      expect(plugin.turnDurationsForActiveThread()).toEqual({ u1: 360_000 });
    }
    finally {
      vi.useRealTimers();
    }
  });

  it("onMainWindowUnload destroys the window's float panel", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = { setInteractionContext: vi.fn(), state: { connected: false } };
    plugin.context = null;
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.toggleFloatPanel();
    expect(document.querySelector(".zc-float")).not.toBeNull();

    await plugin.onMainWindowUnload(window);
    expect(document.querySelector(".zc-float")).toBeNull();
    expect(plugin.floatPanels.size).toBe(0);

    (globalThis as any).Zotero = previousZotero;
  });

  it("Escape closes the float panel from anywhere and restores focus", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.codex = { setInteractionContext: vi.fn(), state: { connected: false } };
    plugin.context = null;
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.toggleFloatPanel();
    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.hidden).toBe(false);

    plugin.installShortcutHandler(window);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(root.hidden).toBe(true);

    plugin.removeShortcutHandler(window);
    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    plugin.floatPanels.clear();
    (globalThis as any).Zotero = previousZotero;
  });

  it("treats only an expanded, connected custom section as active", () => {
    const plugin = new ZoteroChatPlugin() as any;
    const collapsed = document.createElement("collapsible-section");
    const body = document.createElement("div");
    collapsed.appendChild(body);
    document.body.appendChild(collapsed);
    plugin.views = new Set([body]);

    expect(plugin.hasOpenSidebar()).toBe(false);
    collapsed.setAttribute("open", "");
    expect(plugin.hasOpenSidebar()).toBe(true);
    collapsed.remove();
    expect(plugin.hasOpenSidebar()).toBe(false);
  });

  it("coalesces concurrent first expansion into one lazy terminal startup", async () => {
    let release!: () => void;
    const startup = new Promise<void>((resolve) => { release = resolve; });
    const plugin = new ZoteroChatPlugin() as any;
    plugin.openTerminalInternal = vi.fn(() => startup);

    const first = plugin.openTerminal();
    const second = plugin.openTerminal();
    expect(plugin.openTerminalInternal).toHaveBeenCalledOnce();

    release();
    await Promise.all([first, second]);
    expect(plugin.terminalOpenPromise).toBeNull();
  });

  it("clears a failed lazy startup without creating an unhandled finally rejection", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.openTerminalInternal = vi.fn(async () => { throw new Error("startup failed"); });

    await expect(plugin.openTerminal()).rejects.toThrow("startup failed");
    await Promise.resolve();

    expect(plugin.terminalOpenPromise).toBeNull();
  });

  it("captures context before the first terminal open can start the helper", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const host = document.createElement("div");
    const calls: string[] = [];
    plugin.terminal = {
      mount: vi.fn(() => calls.push("mount")),
      open: vi.fn(async () => { calls.push("open"); }),
    };
    plugin.refreshContext = vi.fn(async () => { calls.push("context"); });
    plugin.readerContext = {
      ensureZotkitLibrarySnapshot: vi.fn(async () => { calls.push("snapshot"); }),
    };
    plugin.terminalOptions = vi.fn(async () => {
      calls.push("options");
      return { host };
    });

    await plugin.openTerminalInternal(host);

    expect(calls).toEqual(["mount", "context", "snapshot", "options", "open"]);
  });

  it("invalidates Reader text caches and reloads every matching Reader after a PDF mutation", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const matchingA = { itemID: 7, reload: vi.fn(async () => {}) };
    const matchingB = { itemID: 7, reload: vi.fn(async () => {}) };
    const unrelated = { itemID: 8, reload: vi.fn(async () => {}) };
    (globalThis as any).Zotero = {
      Reader: {
        _readers: [matchingA, unrelated, matchingB],
        getByTabID: vi.fn(() => matchingA),
      },
    };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContext = {
      invalidateAttachmentCaches: vi.fn(async () => {}),
      ensureZotkitLibrarySnapshot: vi.fn(async () => null),
    };
    plugin.selectedTabID = vi.fn(() => "reader-a");
    plugin.refreshContext = vi.fn(async () => {});
    plugin.refreshMutationCheckpoints = vi.fn(async () => {});

    try {
      await plugin.refreshAfterMutation({
        decision: "accepted",
        effects: {
          attachmentID: 7,
          attachmentKey: "ATTACH",
          attachmentLibraryID: 1,
          attachmentContentChanged: true,
          attachmentRelinked: false,
          pdfReplaced: true,
        },
      });

      expect(plugin.readerContext.invalidateAttachmentCaches).toHaveBeenCalledWith({
        key: "ATTACH",
        libraryID: 1,
      });
      expect(matchingA.reload).toHaveBeenCalledOnce();
      expect(matchingB.reload).toHaveBeenCalledOnce();
      expect(unrelated.reload).not.toHaveBeenCalled();
      expect(plugin.refreshContext).toHaveBeenCalledOnce();
    }
    finally {
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });

  it("mounts and switches the terminal on the selected Reader body across A to B to A", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let selectedID = "reader-a";
    (globalThis as any).Zotero = {
      getMainWindow: () => ({ Zotero_Tabs: { selectedID } }),
    };

    const createReaderBody = (tabID: string): HTMLElement => {
      const details = document.createElement("item-details");
      details.setAttribute("data-tab-id", tabID);
      const section = document.createElement("collapsible-section");
      section.setAttribute("open", "");
      const body = document.createElement("div");
      section.append(body);
      details.append(section);
      document.body.append(details);
      return body;
    };

    const bodyA = createReaderBody("reader-a");
    const bodyB = createReaderBody("reader-b");
    const plugin = new ZoteroChatPlugin() as any;
    plugin.paneMode = "terminal";
    plugin.views = new Set([bodyB, bodyA]);
    plugin.context = { workspace: { root: "/profile/zotkit/a" } };
    plugin.terminal = {
      isOpen: true,
      hasLiveSessions: true,
      mount: vi.fn(),
      setVisible: vi.fn(),
      switchPaper: vi.fn(async () => {}),
    };
    plugin.terminalOptions = vi.fn(async (host: HTMLElement) => ({ host }));
    plugin.refreshContext = vi.fn(async (_pageChange: boolean, host: HTMLElement) => {
      await plugin.switchTerminalToContext(false, host);
    });

    try {
      for (const [tabID, body] of [
        ["reader-a", bodyA],
        ["reader-b", bodyB],
        ["reader-a", bodyA],
      ] as const) {
        selectedID = tabID;
        expect(plugin.activeSidebarBody()).toBe(body);
        await plugin.refreshSelectedReaderTab(tabID);
      }

      expect(plugin.terminal.mount.mock.calls.map(([host]: [HTMLElement]) => host))
        .toEqual([bodyA, bodyB, bodyA]);
      expect(plugin.terminal.switchPaper.mock.calls.map(([options]: [{ host: HTMLElement }]) => options.host))
        .toEqual([bodyA, bodyB, bodyA]);
    }
    finally {
      bodyA.closest("item-details")?.remove();
      bodyB.closest("item-details")?.remove();
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });

  it("restores a live Reader terminal after visiting the library tab", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let selectedID = "reader-a";
    (globalThis as any).Zotero = {
      getMainWindow: () => ({ Zotero_Tabs: { selectedID } }),
    };
    const details = document.createElement("item-details");
    details.setAttribute("data-tab-id", "reader-a");
    const section = document.createElement("collapsible-section");
    section.setAttribute("open", "");
    const body = document.createElement("div");
    section.append(body);
    details.append(section);
    document.body.append(details);

    const plugin = new ZoteroChatPlugin() as any;
    plugin.paneMode = "terminal";
    plugin.views = new Set([body]);
    plugin.terminal = {
      isOpen: false,
      hasLiveSessions: true,
      mount: vi.fn(),
      setVisible: vi.fn(),
    };
    plugin.refreshContext = vi.fn(async () => {});

    try {
      selectedID = "zotero-pane";
      await plugin.refreshSelectedReaderTab("zotero-pane", false);
      expect(plugin.terminal.setVisible).toHaveBeenCalledWith(false);

      selectedID = "reader-a";
      await plugin.refreshSelectedReaderTab("reader-a", true);
      expect(plugin.terminal.mount).toHaveBeenCalledWith(body);
      expect(plugin.refreshContext).toHaveBeenCalledWith(false, body);
    }
    finally {
      details.remove();
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });

  it("drops an older tab switch when terminal options finish after a newer switch", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let selectedID = "reader-b";
    (globalThis as any).Zotero = {
      getMainWindow: () => ({ Zotero_Tabs: { selectedID } }),
    };
    const makeBody = (tabID: string): HTMLElement => {
      const details = document.createElement("item-details");
      details.setAttribute("data-tab-id", tabID);
      const body = document.createElement("div");
      details.append(body);
      document.body.append(details);
      return body;
    };
    const bodyA = makeBody("reader-a");
    const bodyB = makeBody("reader-b");
    let releaseB!: (options: { host: HTMLElement; paperKey: string }) => void;
    const optionsB = new Promise<{ host: HTMLElement; paperKey: string }>((resolve) => {
      releaseB = resolve;
    });
    const plugin = new ZoteroChatPlugin() as any;
    plugin.destroyed = false;
    plugin.context = { workspace: { root: "/profile/zotkit" } };
    plugin.terminal = {
      hasLiveSessions: true,
      switchPaper: vi.fn(async () => {}),
    };
    plugin.readerContext = { ensureZotkitLibrarySnapshot: vi.fn(async () => {}) };
    plugin.terminalOptions = vi.fn((host: HTMLElement) => (
      host === bodyB ? optionsB : Promise.resolve({ host, paperKey: "A" })
    ));

    try {
      plugin.contextRequestSequence = 1;
      const stale = plugin.switchTerminalToContext(false, bodyB, 1);
      await Promise.resolve();

      selectedID = "reader-a";
      plugin.contextRequestSequence = 2;
      await plugin.switchTerminalToContext(false, bodyA, 2);
      releaseB({ host: bodyB, paperKey: "B" });
      await stale;

      expect(plugin.terminal.switchPaper).toHaveBeenCalledOnce();
      expect(plugin.terminal.switchPaper).toHaveBeenCalledWith(
        expect.objectContaining({ host: bodyA, paperKey: "A" }),
      );
    }
    finally {
      bodyA.closest("item-details")?.remove();
      bodyB.closest("item-details")?.remove();
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });

  it("does not let an older page refresh overwrite a newer Reader tab context", async () => {
    const originalZotero = (globalThis as any).Zotero;
    let selectedID = "reader-a";
    (globalThis as any).Zotero = {
      getMainWindow: () => ({ Zotero_Tabs: { selectedID } }),
    };
    const contextA = {
      attachment: { key: "A", libraryID: 1 },
      workspace: { root: "/profile/a" },
    };
    const contextB = {
      attachment: { key: "B", libraryID: 1 },
      workspace: { root: "/profile/b" },
    };
    let releasePageA!: (context: typeof contextA) => void;
    const pageA = new Promise<typeof contextA>((resolve) => { releasePageA = resolve; });
    const plugin = new ZoteroChatPlugin() as any;
    plugin.destroyed = false;
    plugin.terminal = { hasLiveSessions: false };
    plugin.readerContext = {
      refreshForPageChange: vi.fn(() => pageA),
      refresh: vi.fn(async () => contextB),
    };

    try {
      const stalePageRefresh = plugin.refreshContext(true);
      await Promise.resolve();
      selectedID = "reader-b";
      await plugin.refreshContext(false);
      releasePageA(contextA);
      await stalePageRefresh;

      expect(plugin.context).toBe(contextB);
      expect(plugin.context.attachment.key).toBe("B");
    }
    finally {
      if (originalZotero === undefined) delete (globalThis as any).Zotero;
      else (globalThis as any).Zotero = originalZotero;
    }
  });
});

describe("Reader context copied into the terminal", () => {
  it("uses the original PDF directory when the path is absolute", () => {
    expect(pdfDirectory("/workspace/fixtures/papers/example.pdf")).toBe("/workspace/fixtures/papers");
    expect(pdfDirectory("relative/example.pdf")).toBeNull();
    expect(pdfDirectory(null)).toBeNull();
  });

  it("inserts metadata, page, path, and literal selection without submitting", () => {
    const context = {
      schemaVersion: 1,
      attachment: {
        id: 2,
        key: "PDFKEY",
        title: "Attachment",
        creators: [],
        tags: [],
      },
      parent: {
        id: 1,
        key: "ITEMKEY",
        title: "Quantum Control",
        creators: [{ firstName: "Ada", lastName: "Lovelace" }],
        year: "2026",
        doi: "10.1/example",
        tags: [],
      },
      pdfPath: "/workspace/fixtures/papers/quantum.pdf",
      page: {
        pageIndex: 6,
        pageNumber: 7,
        text: "page",
        source: "pdfjs",
        warnings: [],
      },
      selection: {
        text: "first line\nsecond line\u001b[31m",
        pageNumber: 7,
        capturedAt: "2026-07-22T00:00:00Z",
      },
      fullText: { source: "deferred", characters: 0 },
      capturedAt: "2026-07-22T00:00:00Z",
      warnings: [],
    } as ReaderContext;

    const prompt = buildSelectionPrompt(context);
    expect(prompt).toContain("Quantum Control");
    expect(prompt).toContain("Ada Lovelace");
    expect(prompt).toContain("10.1/example");
    expect(prompt).toContain("/workspace/fixtures/papers/quantum.pdf");
    expect(prompt).toContain("PDF page: 7");
    expect(prompt).toContain("first line second line [31m");
    expect(prompt).toMatch(/Question: $/);
    expect(prompt).not.toMatch(/[\r\n\u001b]/);
  });

  it("bounds a pasted selection while leaving the complete live MCP copy available", () => {
    const context = {
      schemaVersion: 1,
      attachment: { id: 2, key: "PDFKEY", creators: [], tags: [] },
      parent: null,
      pdfPath: "/papers/long.pdf",
      page: { pageIndex: 0, pageNumber: 1, text: "", source: "none", warnings: [] },
      selection: {
        text: "x".repeat(MAX_SELECTION_PROMPT_CHARACTERS + 500),
        pageNumber: 1,
        capturedAt: "2026-07-22T00:00:00Z",
      },
      fullText: { source: "deferred", characters: 0 },
      capturedAt: "2026-07-22T00:00:00Z",
      warnings: [],
    } as ReaderContext;

    const prompt = buildSelectionPrompt(context);
    expect(prompt).toContain("full text remains available through zotero_reader");
    expect(prompt.length).toBeLessThan(MAX_SELECTION_PROMPT_CHARACTERS + 500);
  });
});

describe("clampFloatOpacity", () => {
  it("clamps parsed values to the 60-100 slider range", () => {
    expect(clampFloatOpacity("100")).toBe(100);
    expect(clampFloatOpacity("85")).toBe(85);
    expect(clampFloatOpacity("40")).toBe(60);
    expect(clampFloatOpacity("250")).toBe(100);
  });

  it("clamps a valid-but-falsy 0 to the 60 floor instead of the old `|| 100` trap promoting it to 100", () => {
    // `Number("0")` is a legitimate (if out-of-range) 0, not NaN -- the old
    // `Number(pref) || 100` fallback silently turned it into 100 by treating
    // falsy-but-valid 0 the same as "missing". It should now simply clamp to
    // the 60 floor like any other too-low value.
    expect(clampFloatOpacity("0")).toBe(60);
  });

  it("falls back to 100 only for genuinely unparsable (NaN) values, not merely falsy/empty ones", () => {
    expect(clampFloatOpacity("not-a-number")).toBe(100);
    // `Number("")` is 0, not NaN, so this clamps like any other 0 -- it must
    // not be confused with the NaN fallback case.
    expect(clampFloatOpacity("")).toBe(60);
  });
});

describe("paper-trail wiring", () => {
  it("begins a pending anchor on sendChat only when the selection chip is attached", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = { selection: { text: "s", position: { pageIndex: 1, rects: [[0, 0, 1, 1]] }, pageNumber: 2 }, attachment: { key: "A", libraryID: 1 } };
    plugin.codex = {
      state: { connected: true, activeThreadId: "th1" },
      isSignedIn: () => true,
      send: vi.fn(async () => {}),
      getChatEntries: () => [],
    };
    plugin.paperTrail = { beginPendingAnchor: vi.fn() };
    plugin.addedContextIDs = new Set(["current-selection"]);
    await plugin.sendChat("为什么?");
    expect(plugin.paperTrail.beginPendingAnchor).toHaveBeenCalledWith(plugin.context, "为什么?", "th1");
    plugin.addedContextIDs = new Set();
    await plugin.sendChat("再问");
    expect(plugin.paperTrail.beginPendingAnchor).toHaveBeenCalledTimes(1);
  });

  it("model tool registry stays write-free (static guarantee)", async () => {
    const { ZOTERO_MUTATION_TOOL } = await import("../src/zotero-mutations");
    expect(ZOTERO_MUTATION_TOOL).toBe("zotero_propose_changes");
    const source = readFileSync(join(__dirname, "../src/paper-trail.ts"), "utf8");
    expect(source).not.toMatch(/tools\s*[:=]/);   // paper-trail 永不注册Model工具
  });

  it("jumpToAnchor opens the reader at the annotation", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const open = vi.fn(async () => {});
    (globalThis as any).Zotero = { Items: { getByLibraryAndKey: () => ({ id: 42 }) }, Reader: { open } };
    const plugin = new ZoteroChatPlugin() as any;
    await plugin.jumpToAnchor({ libraryID: 1, attachmentKey: "A", annotationKey: "ANN1", anchorId: "a1" });
    expect(open).toHaveBeenCalledWith(42, { annotationID: "ANN1" }, { allowDuplicate: false });
    (globalThis as any).Zotero = previousZotero;
  });

  it("resumeAnchorChat switches to the anchor's thread and opens the panel when it wasn't already open", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = { attachment: { key: "A", libraryID: 1 } };
    plugin.codex = {
      state: { connected: false, activeThreadId: "th-old" },
      getAnchors: () => [{ anchorId: "a1", annotationKey: "ANN1", threadId: "th-new" }],
      switchThread: vi.fn(async () => {}),
    };
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.resumeAnchorChat("ANN1");

    expect(plugin.codex.switchThread).toHaveBeenCalledWith("th-new");
    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.hidden).toBe(false);

    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    (globalThis as any).Zotero = previousZotero;
  });

  it("resumeAnchorChat keeps an already-open panel open (does not toggle it closed), and no-ops the thread switch when the annotation has no matching anchor", async () => {
    const previousZotero = (globalThis as any).Zotero;
    (globalThis as any).Zotero = { getMainWindow: () => window };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = { attachment: { key: "A", libraryID: 1 } };
    plugin.codex = {
      state: { connected: false, activeThreadId: "th1" },
      getAnchors: () => [],
      switchThread: vi.fn(async () => {}),
    };
    plugin.ensureChatSession = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    // Simulate the user already having the panel open before "继续对话" is clicked.
    await plugin.toggleFloatPanel();
    const root = document.querySelector<HTMLElement>(".zc-float")!;
    expect(root.hidden).toBe(false);

    const hideSpy = vi.spyOn(plugin, "hideFloatPanel");
    await plugin.resumeAnchorChat("ANN-missing");

    expect(hideSpy).not.toHaveBeenCalled();
    expect(root.hidden).toBe(false);
    expect(plugin.codex.switchThread).not.toHaveBeenCalled();

    plugin.floatPanels.get(window)?.view.destroy();
    plugin.floatPanels.get(window)?.host.remove();
    (globalThis as any).Zotero = previousZotero;
  });
});

describe("clampFloatSize", () => {
  it("clamps width to [380, 760] and height to [220, 2000]", () => {
    expect(clampFloatSize(620, 480)).toEqual({ width: 620, height: 480 });
    expect(clampFloatSize(50, 5000)).toEqual({ width: 380, height: 2000 });
    expect(clampFloatSize(10_000, 10)).toEqual({ width: 760, height: 220 });
  });
});

describe("Region screenshots (Design 3)", () => {
  const paperContext = () => ({
    attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
    parent: { title: "Paper", creators: [], tags: [] },
    page: { pageNumber: 5, pageLabel: "5" },
  });

  it("offers Screenshot Region in the Add-Context menu only while a reader is active", () => {
    const plugin = new ZoteroChatPlugin() as any;

    const withoutReader = plugin.contextSuggestions()
      .find((item: { id: string }) => item.id === "capture-region");
    expect(withoutReader).toMatchObject({
      label: "Screenshot Region",
      kind: "selection",
      disabled: true,
    });

    plugin.context = paperContext();
    const withReader = plugin.contextSuggestions()
      .find((item: { id: string }) => item.id === "capture-region");
    expect(withReader?.disabled).toBe(false);

    plugin.pendingScreenshots = Array.from({ length: 10 }, (_, index) => ({
      image: `data:image/png;base64,${index}`,
      kind: "page" as const,
    }));
    expect(plugin.contextSuggestions()
      .find((item: { id: string }) => item.id === "capture-region")?.disabled).toBe(true);
  });

  it("starts the region flow from the Add-Context menu entry", () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.startRegionScreenshot = vi.fn(async () => {});
    plugin.updateInteractionContext = vi.fn();
    plugin.renderChatViews = vi.fn();

    plugin.addInteractionContext({ id: "capture-region", kind: "selection", label: "Screenshot Region" });

    expect(plugin.startRegionScreenshot).toHaveBeenCalledOnce();
    expect(plugin.updateInteractionContext).not.toHaveBeenCalled();
  });

  it("labels pending page and region screenshots independently", () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = paperContext();
    plugin.pendingScreenshots = [
      { image: "data:image/png;base64,a", kind: "page" },
      { image: "data:image/png;base64,b", kind: "region" },
      { image: "data:image/png;base64,c", kind: "page" },
    ];

    const labels = plugin.contextChips().map((chip: { label: string }) => chip.label);

    expect(labels).toContain("PDF Screenshot 1");
    expect(labels).toContain("Region Screenshot 1");
    expect(labels).toContain("PDF Screenshot 2");
    expect(plugin.contextChips().map((chip: { id: string }) => chip.id))
      .toEqual(expect.arrayContaining(["screenshot:0", "screenshot:1", "screenshot:2"]));
  });

  it("sends pending screenshots as bare data URIs and clears them after the send", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const send = vi.fn(async () => {});
    plugin.codex = {
      state: { connected: true, activeThreadId: null },
      isSignedIn: () => true,
      send,
      getActiveReaderContext: () => null,
    };
    plugin.pendingScreenshots = [
      { image: "data:image/png;base64,a", kind: "page" },
      { image: "data:image/png;base64,b", kind: "region" },
    ];

    await plugin.sendChat("what is in this figure?");

    expect(send).toHaveBeenCalledWith(
      "what is in this figure?",
      "",
      "medium",
      ["data:image/png;base64,a", "data:image/png;base64,b"],
      {},
    );
    expect(plugin.pendingScreenshots).toEqual([]);
  });

  it("injects a region-capture button beside the workbench button in the reader toolbar", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const listeners = new Map<string, (event: any) => void>();
    (globalThis as any).Zotero = {
      Reader: {
        registerEventListener: vi.fn((type: string, handler: (event: any) => void) => {
          listeners.set(type, handler);
        }),
      },
    };
    try {
      const plugin = new ZoteroChatPlugin() as any;
      plugin.installShortcutHandler = vi.fn();
      plugin.acceptReaderHook = vi.fn(async () => {});
      plugin.startRegionScreenshot = vi.fn(async () => {});
      plugin.registerReaderHooks();

      const appended: HTMLElement[] = [];
      listeners.get("renderToolbar")!({
        doc: document,
        append: (element: HTMLElement) => appended.push(element),
        reader: { id: "reader-1" },
      });

      expect(appended).toHaveLength(2);
      const regionButton = appended[1] as HTMLButtonElement;
      expect(regionButton.title).toBe("Capture Region Screenshot (QLab)");
      regionButton.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(plugin.acceptReaderHook).toHaveBeenCalledOnce();
      expect(plugin.startRegionScreenshot).toHaveBeenCalledOnce();
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("attaches a Region Screenshot chip after a completed overlay drag", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const pageElement = document.createElement("div");
    document.body.appendChild(pageElement);
    pageElement.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 400, height: 600,
      right: 400, bottom: 600, x: 0, y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
    plugin.context = paperContext();
    plugin.codex = { getActiveReaderContext: () => plugin.context };
    plugin.readerContext = {
      getCurrentPageViewElement: vi.fn(async () => pageElement),
      captureCurrentPageRegionImage: vi.fn(async () => "data:image/png;base64,region"),
    };
    plugin.activeChatView = vi.fn(() => null);
    plugin.openResearchChat = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.startRegionScreenshot();
    const overlay = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
    expect(overlay).not.toBeNull();
    overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 40, clientY: 60, bubbles: true }));
    document.dispatchEvent(new MouseEvent("mouseup", { clientX: 140, clientY: 160, bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(plugin.readerContext.captureCurrentPageRegionImage).toHaveBeenCalledWith(
      { rect: { x: 40, y: 60, width: 100, height: 100 }, view: { width: 400, height: 600 } },
      plugin.context,
    );
    expect(plugin.pendingScreenshots).toEqual([
      { image: "data:image/png;base64,region", kind: "region" },
    ]);
    expect(plugin.openResearchChat).toHaveBeenCalledWith(undefined, false);
    pageElement.remove();
  });
});
