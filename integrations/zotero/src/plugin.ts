import { NativeBridge } from "./native-bridge";
import readerToolbarIcon from "../assets/icon.svg";
import {
  CodexService,
  type CodexInteractionContextEntry,
  type CodexPendingApproval,
} from "./codex-service";
import {
  ReaderContextService,
  createGeckoProfileAdapter,
  createZotero9ReadAdapter,
  isStaleReaderCaptureError,
  type ReaderContext,
  type ReaderHook,
} from "./reader-context";
import {
  SidebarView,
  type CheckpointOption,
  type ChatEntry,
  type DiffReview,
  type PendingApproval,
  type ResearchContextChip,
  type ResearchContextSuggestion,
  type ResearchPlan,
  type SidebarPhase,
} from "./sidebar";
import { FloatPanelView, latestExchange } from "./float-panel";
import {
  QLAB_WORKBENCH_TAB_TYPE,
  QLAB_WORKBENCH_TAB_ICON,
  WorkbenchTabManager,
  type WorkbenchTabData,
} from "./workbench-tab";
import {
  createResearchLoopSiteRuntime,
  ResearchLoopSiteService,
} from "./research-loop-site";
import { createQmdRenderRuntime, QmdRenderService } from "./qmd-render";
import { QmdWorkspaceView } from "./qmd-workspace";
import { buildQmdIndex, geckoScanner } from "./qmd-index";
import {
  createExternalEditorRuntime,
  installedEditors,
  openInExternalEditor,
  preferredEditor,
  type ExternalEditorApp,
} from "./external-editor";
import { TerminalPanel, type TerminalPaperOptions } from "./terminal-panel";
import { loadSettings, saveQLabRoot, type ZoteroChatSettings } from "./settings";
import {
  buildQLabCommandPrompt,
  buildCaptureChatDraftPrompt,
  commandDefinition,
  type QLabCommandID,
} from "./qlab-commands";
import {
  createGeckoQLabPathHost,
  isQLabRepositoryShape,
  normalizeQLabRoot,
} from "./qlab-workspace";
import { QLabLiteratureService } from "./qlab-library";
import {
  createQLabZoteroSyncRuntime,
  QLabZoteroSyncService,
} from "./qlab-zotero-sync";
import { defaultSelectableModel } from "./model-menu";
import { shouldAutoOpenFloat } from "./plugin-helpers";
import {
  ZoteroMutationApplyError,
  ZoteroMutationService,
  createZoteroMutationHost,
  type MutationResolution,
} from "./zotero-mutations";
import {
  PaperTrailService,
  createZoteroAnchorHost,
  ANCHOR_TAG,
  type AnchorHost,
  type AnchorRecord,
  type PaperTrailConsent,
} from "./paper-trail";
import {
  NotingService,
  createZoteroNotingHost,
  countMathErrors,
  type NotingAnchorInput,
  type NotingSnapshot,
} from "./noting";
import { buildQaFromEntries } from "./exchanges";
import { sha256File } from "./hashing";
import {
  debug,
  logError,
  PANE_ID,
  PLUGIN_ID,
  prefString,
  profilePath,
  randomID,
  setPrefString,
} from "./platform";

interface PluginStartupData {
  id: string;
  version: string;
  rootURI: string;
}

/** Timing/model metadata recorded once a turn completes, keyed by its opening user entry. */
interface TurnMeta {
  elapsedMs: number;
  completedAt: string;
  model: string;
}

export const MAX_SELECTION_PROMPT_CHARACTERS = 32_000;

/** Keep the historical class name as a source-level compatibility shim. */
export class ZoteroChatPlugin {
  private settings!: ZoteroChatSettings;
  private readerContext!: ReaderContextService;
  private bridge!: NativeBridge;
  private mainSite!: ResearchLoopSiteService;
  private qmdRender!: QmdRenderService;
  private terminal!: TerminalPanel;
  private codex!: CodexService;
  private literature!: QLabLiteratureService;
  private zoteroSync!: QLabZoteroSyncService;
  private mutations!: ZoteroMutationService;
  private paperTrail!: PaperTrailService;
  private noting!: NotingService;
  private workbenchTabs!: WorkbenchTabManager;
  private anchorHost!: AnchorHost;
  private views = new Set<HTMLElement>();
  private chatViews = new Map<HTMLElement, SidebarView>();
  private floatPanels = new Map<
    Window,
    { host: HTMLElement; view: FloatPanelView; focusReturn: HTMLElement | null }
  >();
  private shortcutWindows = new Set<Window>();
  private context: ReaderContext | null = null;
  private notifierID: string | null = null;
  private registeredPaneID: string | null = null;
  private pageRefreshTimer: ReturnType<typeof setTimeout> | null = null;
  private tabRefreshTimer: ReturnType<typeof setTimeout> | null = null;
  private terminalOpenPromise: Promise<void> | null = null;
  private chatOpenPromise: Promise<void> | null = null;
  private chatRenderTimer: ReturnType<typeof setTimeout> | null = null;
  private paneMode: "chat" | "terminal" = "chat";
  private chatPhase: SidebarPhase = "connecting";
  private chatError = "";
  private selectedModel = "";
  private selectedEffort = "medium";
  private floatOpacity = 100;
  private addedContextIDs = new Set<string>();
  private mutationCheckpoints: CheckpointOption[] = [];
  private contextRequestSequence = 0;
  private destroyed = false;
  private readonly turnStartedAt = new Map<string, number>();
  private readonly turnMeta = new Map<string, Map<string, TurnMeta>>();
  // Bug-triage #2: keep a running turn visible even when the sidebar has no
  // connected body (section collapsed/closed) by force-opening the float
  // panel -- see maybeAutoOpenFloatForRunningTurn(). `currentTurnId` is a
  // plugin-local id (not codex's own turnId, which is briefly null right as
  // a turn starts) that changes exactly once per rising edge of
  // codex.state.running, so a steered follow-up mid-turn keeps the same id.
  private turnGeneration = 0;
  private currentTurnId: string | null = null;
  private wasCodexRunning = false;
  private autoOpenedFloatTurnId: string | null = null;
  private floatDismissedTurnId: string | null = null;

  async startup(data: PluginStartupData): Promise<void> {
    this.settings = await loadSettings();
    await IOUtils.makeDirectory(profilePath(), {
      createAncestors: true,
      ignoreExisting: true,
      permissions: 0o700,
    });

    const readAdapter = createZotero9ReadAdapter(Zotero, {
      readUtf8: (path) => IOUtils.readUTF8(path),
      fileExists: (path) => IOUtils.exists(path),
    });
    const hostAdapter = createGeckoProfileAdapter({
      IOUtils,
      PathUtils: {
        profileDir: Zotero.Profile.dir,
        join: (...parts: string[]) => PathUtils.join(...parts),
        filename: (path: string) => PathUtils.filename(path),
      },
    }, { pluginDirectoryName: "zotkit" });
    this.readerContext = new ReaderContextService(readAdapter, hostAdapter, {
      libraryRoot: this.settings.libraryRoot || null,
    });
    this.workbenchTabs = new WorkbenchTabManager({
      createView: (host, win, tabID) => this.createWorkbenchView(host, win, tabID),
      openNewWindow: (source) => this.openWorkbenchWindow(source),
      onMoveError: (error) => this.reportError(error),
    });
    this.bridge = new NativeBridge(data.rootURI, data.version);
    this.mainSite = new ResearchLoopSiteService(createResearchLoopSiteRuntime(this.bridge));
    this.qmdRender = new QmdRenderService(createQmdRenderRuntime(this.bridge));
    this.literature = new QLabLiteratureService();
    this.zoteroSync = new QLabZoteroSyncService(createQLabZoteroSyncRuntime(this.bridge));
    this.terminal = new TerminalPanel(this.bridge, this.settings.terminalHeight, {
      onPasteSelection: () => void this.pasteSelectionToTerminal(),
      onRefreshContext: () => void this.refreshAndSwitch().catch((error) => this.reportError(error)),
      onOpenChat: () => this.closeWorkbenchTerminal(),
    });
    this.selectedModel = this.settings.defaultModel;
    this.selectedEffort = this.settings.reasoningEffort;
    this.floatOpacity = clampFloatOpacity(prefString("floatOpacity", "100"));
    this.mutations = new ZoteroMutationService(
      createZoteroMutationHost(Zotero, IOUtils, PathUtils),
      {
        getContext: () => this.context,
        onState: () => {
          this.renderChatViews();
          void this.refreshMutationCheckpoints();
        },
      },
    );
    this.codex = new CodexService(
      this.bridge,
      this.readerContext,
      data.version,
      {
        onState: () => this.handleCodexState(),
        onError: (error) => this.reportError(error),
        onFallbackRequested: (error) => {
          this.chatPhase = "unavailable";
          this.chatError = `${error.message}. You can still open the Advanced Terminal from the top bar.`;
          this.renderChatViews();
        },
      },
      {
        tools: this.mutations.tools,
        invokeTool: (name, argumentsValue) => this.mutations.invokeTool(name, argumentsValue),
      },
    );
    this.anchorHost = createZoteroAnchorHost(Zotero);
    this.paperTrail = new PaperTrailService(
      this.anchorHost,
      {
        onState: () => this.scheduleChatRender(),
        // Same pipeline Noting's buildNotingSnapshot uses to slice a thread
        // by turnRange -- paper-trail reuses it to build/rewrite the
        // full-transcript annotation comment (see paper-trail.ts's
        // transcriptExchangesFor). No LLM round-trip on the write path
        // anymore: the old `summarize()` callback (a 10s-capped
        // runUtilityTurn call feeding the deprecated "Q + summary" comment
        // format) is gone -- answerSummary is now the free, synchronous
        // summaryFallback() digest instead.
        readThreadTurns: (threadId) => this.codex.readThreadTurns(threadId),
        getAnchors: (context) => this.codex.getAnchors(context),
        recordAnchor: (context, anchor) => this.codex.recordAnchor(context, anchor),
        updateAnchor: (context, id, patch) => this.codex.updateAnchor(context, id, patch),
        removeAnchor: (context, id) => this.codex.removeAnchor(context, id),
        consent: () => (prefString("paperTrail", "unset") as PaperTrailConsent),
        setConsent: (value) => setPrefString("paperTrail", value),
      },
    );
    this.noting = new NotingService({
      host: createZoteroNotingHost(Zotero, IOUtils, PathUtils),
      generate: (prompt) => this.codex.runUtilityTurn(prompt, { timeoutMs: 300_000, model: this.selectedModel }),
      buildSnapshot: () => this.buildNotingSnapshot(),
      countMath: (markdown) => this.countNotingMathErrors(markdown),
      onState: () => this.scheduleChatRender(),
      model: () => this.selectedModel,
    });

    for (const win of Zotero.getMainWindows()) await this.onMainWindowLoad(win);
    this.registerReaderHooks();
    this.registerPageObserver();
    debug("QLab Local Codex startup complete", { version: data.version });
  }

  async shutdown(): Promise<void> {
    this.destroyed = true;
    this.contextRequestSequence += 1;
    if (this.pageRefreshTimer) clearTimeout(this.pageRefreshTimer);
    this.pageRefreshTimer = null;
    if (this.tabRefreshTimer) clearTimeout(this.tabRefreshTimer);
    this.tabRefreshTimer = null;
    if (this.chatRenderTimer) clearTimeout(this.chatRenderTimer);
    this.chatRenderTimer = null;
    if (this.notifierID) {
      Zotero.Notifier.unregisterObserver(this.notifierID);
      this.notifierID = null;
    }
    for (const view of this.chatViews.values()) view.destroy();
    this.chatViews.clear();
    for (const entry of this.floatPanels.values()) {
      entry.view.destroy();
      entry.host.remove();
    }
    this.floatPanels.clear();
    this.views.clear();
    this.codex?.stop();
    this.terminal?.destroy();
    await this.bridge?.stop();
    try {
      if (this.registeredPaneID) {
        Zotero.ItemPaneManager.unregisterSection(this.registeredPaneID);
        this.registeredPaneID = null;
      }
    }
    catch { /* automatically removed by plugin ID */ }
    for (const win of [...this.shortcutWindows]) this.removeShortcutHandler(win);
    for (const win of Zotero.getMainWindows()) {
      this.workbenchTabs?.uninstall(win, true);
      this.removeWindowAssets(win);
    }
    debug("Zotkit Research Chat shutdown complete");
  }

  async onMainWindowLoad(win: Window): Promise<void> {
    if (this.destroyed) return;
    this.injectWindowAssets(win);
    this.workbenchTabs?.install(win);
    this.installQLabMenu(win);
    this.installShortcutHandler(win);
  }

  async onMainWindowUnload(win: Window): Promise<void> {
    const floatEntry = this.floatPanels.get(win);
    if (floatEntry) {
      floatEntry.view.destroy();
      floatEntry.host.remove();
      this.floatPanels.delete(win);
    }
    this.workbenchTabs?.uninstall(win);
    this.removeQLabMenu(win);
    this.removeWindowAssets(win);
  }

  private installShortcutHandler(win: Window | null | undefined): void {
    if (!win || this.shortcutWindows.has(win)) return;
    const previousHandler = (win as any).__zoteroChatKeyHandler;
    if (previousHandler) win.removeEventListener("keydown", previousHandler, true);
    const keyHandler = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" && !event.metaKey && !event.ctrlKey && !event.altKey
        && !event.isComposing && !isEditableEventTarget(event.target)
      ) {
        const main = typeof Zotero === "undefined" ? win : (Zotero.getMainWindow?.() || win);
        const entry = main ? this.floatPanels.get(main) : undefined;
        if (entry?.view.isVisible()) {
          event.preventDefault();
          event.stopPropagation();
          this.hideFloatPanel(main!);
        }
        return;
      }
      if (!event.metaKey || event.ctrlKey || event.altKey || event.isComposing) return;
      if (isEditableEventTarget(event.target)) return;
      const key = event.key.toLowerCase();
      if (!event.shiftKey && key === "i") {
        event.preventDefault();
        event.stopPropagation();
        void this.openWorkbenchTab(win).catch((error) => this.reportError(error));
        return;
      }
      if (!event.shiftKey && key === "l") {
        event.preventDefault();
        event.stopPropagation();
        void this.openChatWithSelection(true).catch((error) => this.reportError(error));
        return;
      }
      if (event.shiftKey && key === "l") {
        event.preventDefault();
        event.stopPropagation();
        void this.openChatWithSelection(false).catch((error) => this.reportError(error));
        return;
      }
      if (!event.shiftKey && key === "k") {
        event.preventDefault();
        event.stopPropagation();
        void this.toggleFloatPanel().catch((error) => this.reportError(error));
        return;
      }
      if (event.shiftKey && key === "j") {
        event.preventDefault();
        event.stopPropagation();
        void this.openWorkbenchTerminal(win).catch((error) => this.reportError(error));
      }
    };
    (win as any).__zoteroChatKeyHandler = keyHandler;
    win.addEventListener("keydown", keyHandler, true);
    this.shortcutWindows.add(win);
  }

  private registerSection(): void {
    const paneID = Zotero.ItemPaneManager.registerSection({
      paneID: PANE_ID,
      pluginID: PLUGIN_ID,
      header: {
        l10nID: "zotkit-pane-header",
        icon: "chrome://zotkit/content/icons/icon16.svg",
      },
      sidenav: {
        l10nID: "zotkit-pane-sidenav",
        icon: "chrome://zotkit/content/icons/icon20.svg",
      },
      sectionButtons: [
        {
          type: "zotkit-paste-selection",
          icon: "chrome://zotkit/content/icons/chat.svg",
          l10nID: "zotkit-section-new-chat",
          onClick: () => {
            this.openSidebar();
            void this.openChatWithSelection(true).catch((error) => this.reportError(error));
          },
        },
        {
          type: "zotkit-focus-terminal",
          icon: "chrome://zotkit/content/icons/terminal.svg",
          l10nID: "zotkit-section-terminal",
          onClick: () => {
            this.openSidebar();
            void this.openTerminal()
              .then(() => this.terminal.focus())
              .catch((error) => this.reportError(error));
          },
        },
      ],
      onDestroy: ({ body }: { body: HTMLElement }) => {
        this.terminal.unmount(body);
        this.chatViews.get(body)?.destroy();
        this.chatViews.delete(body);
        this.views.delete(body);
      },
      onItemChange: ({ body, item, tabType, setEnabled }: any) => {
        this.views.add(body);
        const isReader = tabType === "reader";
        const isPdf = Boolean(item?.isPDFAttachment?.())
          || item?.attachmentContentType === "application/pdf";
        setEnabled(isReader || isPdf);
        if (isReader || isPdf) this.signalReaderBodyReady(body);
      },
      onRender: ({ body }: { body: HTMLElement }) => {
        this.views.add(body);
        // DOM-only render. Codex/helper startup remains behind explicit pane expansion.
        if (this.paneMode === "chat") this.mountChat(body);
        else this.terminal.mount(body);
        this.signalReaderBodyReady(body);
      },
      onToggle: ({ body, event }: { body: HTMLElement; event: Event }) => {
        const expanded = Boolean((event.target as HTMLElement | null)?.hasAttribute("open"));
        if (!expanded) {
          this.terminal.setVisible(false);
          return;
        }
        this.views.add(body);
        if (this.paneMode === "terminal") {
          this.terminal.mount(body);
          void this.openTerminal(body).catch((error) => this.reportError(error));
        }
        else {
          this.mountChat(body);
          void this.openResearchChat(body, false).catch((error) => this.reportError(error));
        }
      },
      onAsyncRender: async ({ body }: { body: HTMLElement }) => {
        // Zotero may render collapsed sections while scrolling the Item Pane.
        // Keep this branch process-free unless the user has expanded it.
        if (!body.closest("collapsible-section")?.hasAttribute("open")) return;
        this.views.add(body);
        if (this.paneMode === "terminal") {
          this.terminal.mount(body);
          await this.openTerminal(body).catch((error) => this.reportError(error));
        }
        else {
          this.mountChat(body);
          await this.openResearchChat(body, false).catch((error) => this.reportError(error));
        }
      },
    });
    if (!paneID) throw new Error("Unable to register the Zotkit sidebar");
    this.registeredPaneID = paneID;
  }

  private registerReaderHooks(): void {
    Zotero.Reader.registerEventListener("renderToolbar", (event: any) => {
      const { doc, append } = event;
      this.installShortcutHandler(doc.defaultView);
      const button = doc.createElement("button");
      button.type = "button";
      button.title = "Open QLab Local Codex (⌘I)";
      button.setAttribute("aria-label", button.title);
      button.style.cssText = "display:grid;place-items:center;width:32px;height:32px;border:0;border-radius:8px;background:transparent;cursor:pointer;padding:5px";
      const icon = doc.createElement("img");
      // Reader documents use a resource:// origin and cannot load privileged
      // chrome:// images. Bundle this icon as a data URL so the toolbar button
      // remains visible without widening Reader content privileges.
      icon.src = readerToolbarIcon;
      icon.alt = "";
      icon.style.cssText = "width:22px;height:22px;border-radius:6px";
      button.appendChild(icon);
      button.addEventListener("click", () => {
        void this.acceptReaderHook(event).then(async () => {
          await this.openWorkbenchTab();
        }).catch((error) => this.reportError(error));
      });
      append(button);
    }, PLUGIN_ID);

    Zotero.Reader.registerEventListener("renderTextSelectionPopup", (event: any) => {
      const { doc, append } = event;
      this.installShortcutHandler(doc.defaultView);
      // Capture selection immediately so Cursor-compatible ⌘L / ⌘⇧L shortcuts
      // work even when the popup button itself is not clicked.
      void this.acceptReaderHook(event).catch((error) => this.reportError(error));
      const group = doc.createElement("div");
      group.style.cssText = "display:flex;gap:5px;padding:5px 4px 2px";
      const ask = this.readerPopupButton(doc, "Ask in Zotkit", () => {
        void this.acceptReaderHook(event).then(async () => {
          await this.openChatWithSelection(false);
        }).catch((error) => this.reportError(error));
      });
      group.append(ask);
      append(group);
    }, PLUGIN_ID);

  }

  private registerPageObserver(): void {
    this.notifierID = Zotero.Notifier.registerObserver({
      notify: (
        event: string,
        type: string,
        ids: Array<string | number>,
        extraData?: Record<string, { type?: string }>,
      ) => {
        if (type === "file" && event === "pageChange") {
          const hasWorkbench = (this.workbenchTabs?.entries().length || 0) > 0;
          const hasFloat = [...this.floatPanels.values()].some((entry) => entry.view.isVisible());
          if (!hasWorkbench && !hasFloat && !this.hasOpenSidebar()) return;
          if (this.paneMode === "terminal" && !this.terminal.isOpen) return;
          if (this.pageRefreshTimer) clearTimeout(this.pageRefreshTimer);
          this.pageRefreshTimer = setTimeout(() => {
            this.pageRefreshTimer = null;
            void this.refreshContext(true).catch(() => {});
          }, 800);
          return;
        }
        if (type !== "tab" || !["select", "load"].includes(event)) return;
        if (
          !this.terminal.hasLiveSessions
          && !this.terminalOpenPromise
          && !this.codex?.state.connected
          && !this.chatOpenPromise
        ) return;
        const tabID = String(ids?.[0] ?? "");
        if (!tabID || this.selectedTabID() !== tabID) return;
        const tabType = extraData?.[tabID]?.type || this.selectedTabType();
        if (tabType === QLAB_WORKBENCH_TAB_TYPE) {
          // A workbench tab intentionally keeps the last accepted Reader
          // context instead of clearing it just because no PDF iframe is the
          // selected deck panel.
          this.renderChatViews();
          return;
        }
        this.scheduleTabRefresh(tabID, this.isReaderTabType(tabType), 0, 0);
      },
    }, ["file", "tab"], PLUGIN_ID, 40);
  }

  private hasOpenSidebar(): boolean {
    const body = this.activeSidebarBody();
    return Boolean(body?.closest("collapsible-section")?.hasAttribute("open"));
  }

  private signalReaderBodyReady(body: HTMLElement): void {
    if (
      !this.terminal.hasLiveSessions
      && !this.terminalOpenPromise
      && !this.codex?.state.connected
      && !this.chatOpenPromise
    ) return;
    if (!body.closest("collapsible-section")?.hasAttribute("open")) return;
    const tabID = this.sidebarTabID(body);
    if (!tabID || this.selectedTabID() !== tabID) return;
    this.scheduleTabRefresh(tabID, true, 0, 0);
  }

  private scheduleTabRefresh(
    tabID: string,
    isReader: boolean,
    attempt: number,
    delay: number,
  ): void {
    if (this.tabRefreshTimer) clearTimeout(this.tabRefreshTimer);
    this.tabRefreshTimer = setTimeout(() => {
      this.tabRefreshTimer = null;
      void this.refreshSelectedReaderTab(tabID, isReader, attempt)
        .catch((error) => this.reportError(error));
    }, delay);
  }

  private async refreshSelectedReaderTab(
    tabID: string,
    isReader = true,
    attempt = 0,
  ): Promise<void> {
    const pending = this.paneMode === "terminal"
      ? this.terminalOpenPromise
      : this.chatOpenPromise;
    if (pending) {
      try { await pending; }
      catch { return; }
    }
    if (this.destroyed || this.selectedTabID() !== tabID) return;
    if (!isReader) {
      this.terminal.setVisible(false);
      return;
    }
    const host = this.activeSidebarBody(tabID);
    if (!host) {
      await this.refreshContext(false);
      return;
    }
    if (!host?.closest("collapsible-section")?.hasAttribute("open")) {
      if (this.paneMode === "terminal") this.terminal.setVisible(false);
      return;
    }
    if (this.paneMode === "terminal") this.terminal.mount(host);
    else this.mountChat(host);
    await this.refreshContext(false, host);
  }

  private async acceptReaderHook(event: any): Promise<void> {
    const requestSequence = ++this.contextRequestSequence;
    try {
      const context = await this.readerContext.acceptReaderHook({
        reader: event.reader,
        item: event.item,
        params: event.params,
        selectionAnnotation: event.params?.annotation,
      } as ReaderHook);
      if (requestSequence !== this.contextRequestSequence || this.destroyed) return;
      await this.applyContext(context, requestSequence);
    }
    catch (error) {
      if (!isStaleReaderCaptureError(error)) throw error;
    }
  }

  private async refreshContext(pageChange = false, preferredHost?: HTMLElement): Promise<void> {
    if (pageChange) {
      const requestSequence = ++this.contextRequestSequence;
      const selectedTabID = this.selectedTabID();
      try {
        const context = await this.readerContext.refreshForPageChange();
        if (
          !context
          || this.destroyed
          || requestSequence !== this.contextRequestSequence
          || selectedTabID !== this.selectedTabID()
        ) return;
        await this.applyContext(context, requestSequence, preferredHost);
      }
      catch (error) {
        if (!isStaleReaderCaptureError(error)) throw error;
      }
      return;
    }
    const requestSequence = ++this.contextRequestSequence;
    try {
      const context = await this.readerContext.refresh();
      if (requestSequence !== this.contextRequestSequence || this.destroyed) return;
      await this.applyContext(context, requestSequence, preferredHost);
    }
    catch (error) {
      if (!isStaleReaderCaptureError(error)) throw error;
    }
  }

  private async refreshAndSwitch(): Promise<void> {
    await this.refreshContext();
    if (this.paneMode === "terminal") {
      await this.readerContext.ensureZotkitLibrarySnapshot(true);
      if (this.terminal.hasLiveSessions) await this.switchTerminalToContext();
    }
  }

  private async applyContext(
    context: ReaderContext,
    requestSequence: number,
    preferredHost?: HTMLElement,
  ): Promise<void> {
    if (requestSequence !== this.contextRequestSequence || this.destroyed) return;
    const previousLibraryID = this.context?.attachment.libraryID;
    this.context = context;
    for (const win of Zotero.getMainWindows?.() || []) {
      for (const entry of this.workbenchTabs?.entries(win) || []) {
        this.workbenchTabs.update(win, entry.id, {
          itemID: context.attachment.id,
          icon: QLAB_WORKBENCH_TAB_ICON,
          title: `QLab · ${paperTitle(context)}`,
        }, false);
      }
    }
    this.mutations?.clearPaperReviews(context);
    this.updateInteractionContext();
    this.renderChatViews();
    if (this.codex?.state.connected && this.codex.isSignedIn()) {
      await this.codex.setPaper(context);
    }
    const drawer = this.activeWorkbenchEntry()?.view;
    const drawerHost = drawer instanceof SidebarView && drawer.isTerminalOpen()
      ? drawer.terminalHost()
      : undefined;
    if ((this.paneMode === "terminal" || drawerHost) && this.terminal.hasLiveSessions) {
      await this.switchTerminalToContext(
        String(previousLibraryID ?? "") !== String(context.attachment.libraryID ?? ""),
        drawerHost || preferredHost,
        requestSequence,
      );
    }
  }

  private mountChat(body: HTMLElement): SidebarView {
    this.terminal.unmount(body);
    body.classList.add("zc-pane-host");
    let view = this.chatViews.get(body);
    if (view) return view;
    view = new SidebarView(body, {
      onSend: (text) => void this.sendChat(text).catch((error) => this.reportError(error)),
      onStop: () => void this.codex.interrupt().catch((error) => this.reportError(error)),
      onNewThread: () => void this.newChat(view!).catch((error) => this.reportError(error)),
      onSelectThread: (threadID) => void this.selectThread(view!, threadID),
      onDeleteThread: (threadID) => void this.codex.deleteThread(threadID).catch((error) => this.reportError(error)),
      onLogin: () => void this.codex.login().catch((error) => this.reportError(error)),
      onLogout: () => void this.codex.logout().catch((error) => this.reportError(error)),
      onOpenTerminal: () => void this.openTerminal().then(() => this.terminal.focus()).catch((error) => this.reportError(error)),
      onOpenWorkbench: () => void this.openWorkbenchTab().catch((error) => this.reportError(error)),
      onRefreshContext: () => void this.retryResearchChat(body).catch((error) => this.reportError(error)),
      onInsertSelection: () => void this.attachSelection(false),
      onModelChange: (model) => { void this.handleModelSelection(model); },
      onChooseQLabRoot: () => {
        void this.chooseQLabRoot(body.ownerDocument.defaultView || undefined)
          .catch((error) => this.reportError(error));
      },
      onCaptureChatDraft: () => {
        void this.captureChatDraft().catch((error) => this.reportError(error));
      },
      onEffortChange: (effort) => {
        this.selectedEffort = effort;
        setPrefString("reasoningEffort", effort);
        this.renderChatViews();
      },
      onAddContext: (suggestion) => this.addInteractionContext(suggestion),
      onRemoveContext: (contextID) => this.removeInteractionContext(contextID),
      onReviewDecision: (reviewID, decision) => {
        void this.resolveMutationReview(reviewID, decision);
      },
      onApprovalDecision: (approvalID, decision) => {
        if (!this.codex.resolveApproval(approvalID, decision)) {
          this.reportError(new Error("This approval request has expired"));
        }
      },
      onRestoreCheckpoint: (checkpointID) => {
        void this.restoreCheckpoint(checkpointID).catch((error) => this.reportError(error));
      },
      onPaperTrailConsent: (decision) => {
        const context = this.context;
        if (!context) return;
        void this.paperTrail.resolveConsent(context, decision);
      },
      onNotingStart: () => { void this.noting.run(); },
      onNotingDecision: (decision) => { void this.noting.decide(decision); },
      onNotingApply: (mode) => { void this.noting.apply(mode).catch(() => { /* failure is already visible via view() */ }); },
      onNotingCancel: () => { this.noting.cancel(); },
    });
    this.chatViews.set(body, view);
    this.renderChatViews();
    return view;
  }

  private async openResearchChat(_body?: HTMLElement, focus = true): Promise<void> {
    this.paneMode = "chat";
    this.terminal.setVisible(false);
    const win = Zotero.getMainWindow();
    const existing = win ? this.activeWorkbenchEntry(win) : null;
    if (existing?.view instanceof SidebarView) {
      existing.view.setTerminalOpen(false);
    }
    else if (existing?.host.querySelector(".zc-terminal-sidebar")) {
      this.terminal.unmount(existing.host);
      existing.view = this.createWorkbenchView(existing.host, win!, existing.id);
      existing.view.show();
      this.renderChatViews();
    }
    await this.openWorkbenchTab(win);
    if (focus) this.activeWorkbenchEntry(win!)?.view.focusComposer();
  }

  private ensureChatSession(): Promise<void> {
    if (this.chatOpenPromise) return this.chatOpenPromise;
    const pending = this.ensureChatSessionInternal();
    this.chatOpenPromise = pending;
    const clear = () => {
      if (this.chatOpenPromise === pending) this.chatOpenPromise = null;
    };
    void pending.then(clear, clear);
    return pending;
  }

  private async ensureChatSessionInternal(): Promise<void> {
    this.chatPhase = "connecting";
    this.chatError = "";
    this.renderChatViews();
    try {
      // Bug-triage #2 (edge 3): was awaited outside this try, so a non-stale
      // reader-capture rejection here escaped as an unhandled rejection
      // instead of surfacing through the catch below -- leaving chatPhase
      // stuck at "connecting" (composer disabled) until the next retry.
      if (this.isReaderTabType(this.selectedTabType())) await this.refreshContext();
      await this.codex.start();
      if (!this.codex.isSignedIn()) {
        this.chatPhase = "signed-out";
      }
      else {
        this.chatPhase = "ready";
        if (this.context) await this.codex.setPaper(this.context);
      }
      const models = this.codex.state.models;
      const fallbackModel = defaultSelectableModel(models);
      if (!this.selectedModel && fallbackModel) {
        this.selectedModel = fallbackModel;
      }
      else if (this.selectedModel
          && !models.some((model) => model.id === this.selectedModel)) {
        this.selectedModel = fallbackModel;
        setPrefString("defaultModel", this.selectedModel);
      }
      await this.refreshMutationCheckpoints();
    }
    catch (error) {
      const value = error instanceof Error ? error : new Error(String(error));
      this.chatPhase = value.message.includes("Codex CLI Not Found") ? "unavailable" : "error";
      this.chatError = value.message;
      throw value;
    }
    finally {
      this.renderChatViews();
    }
  }

  private async retryResearchChat(body?: HTMLElement): Promise<void> {
    await this.refreshContext();
    await this.openResearchChat(body, true);
  }

  private async sendChat(text: string): Promise<void> {
    if (!this.codex.state.connected) await this.ensureChatSession();
    if (!this.codex.isSignedIn()) {
      throw new Error("Sign in to the local Codex with ChatGPT first");
    }
    this.chatPhase = "ready";
    const context = this.context;
    await this.codex.send(text, this.selectedModel, this.selectedEffort);
    const threadId = this.codex.state.activeThreadId;
    if (threadId && context?.selection?.text && this.addedContextIDs.has("current-selection")) {
      this.paperTrail.beginPendingAnchor(context, text, threadId);
    }
  }

  private async newChat(preferredView?: SidebarView): Promise<void> {
    await this.openResearchChat(undefined, false);
    if (!this.codex.isSignedIn()) {
      throw new Error("Sign in to the local Codex with ChatGPT first");
    }
    await this.codex.newThread();
    (preferredView || this.activeWorkbenchEntry()?.view)?.focusComposer();
  }

  private async selectThread(view: SidebarView, threadID: string): Promise<void> {
    try {
      await this.codex.switchThread(threadID);
      this.chatError = "";
      this.renderChatViews();
      view.focusComposer();
    }
    catch (error) {
      this.reportError(error);
    }
  }

  private async openChatWithSelection(newThread: boolean): Promise<void> {
    await this.openResearchChat(undefined, false);
    if (newThread && this.codex.isSignedIn() && this.context) await this.codex.newThread();
    this.attachSelection(true);
  }

  private async handleModelSelection(model: string): Promise<void> {
    this.selectedModel = model;
    setPrefString("defaultModel", model);
    this.renderChatViews();
  }

  private mountFloatPanel(
    win: Window,
  ): { host: HTMLElement; view: FloatPanelView; focusReturn: HTMLElement | null } {
    let entry = this.floatPanels.get(win);
    if (entry) return entry;
    const host = win.document.createElement("div");
    host.className = "zc-float-host";
    win.document.documentElement.appendChild(host);
    const view = new FloatPanelView(host, {
      onSend: (text) => void this.sendChat(text).catch((error) => this.reportError(error)),
      onStop: () => void this.codex.interrupt().catch((error) => this.reportError(error)),
      onClose: () => this.hideFloatPanel(win),
      onRemoveSelection: () => this.removeInteractionContext("current-selection"),
      onLogin: () => void this.codex.login().catch((error) => this.reportError(error)),
      onModelChange: (model) => { void this.handleModelSelection(model); },
      onOpacityChange: (value) => {
        this.floatOpacity = value;
        setPrefString("floatOpacity", String(value));
        this.renderChatViews();
      },
      onPanelResize: (width, height) => {
        const clamped = clampFloatSize(width, height);
        setPrefString("floatSize", `${clamped.width}x${clamped.height}`);
      },
      onUndoAnchor: (anchorId) => {
        const context = this.context;
        if (!context) return;
        void this.paperTrail.undoAnchor(context, anchorId);
      },
      onMarkUnderstood: () => {
        const context = this.context;
        const anchor = context ? this.latestOpenAnchor() : null;
        if (context && anchor) void this.paperTrail.resolveAnchor(context, anchor.anchorId);
        this.hideFloatPanel(win);
      },
      onPaperTrailConsent: (decision) => {
        const context = this.context;
        if (!context) return;
        void this.paperTrail.resolveConsent(context, decision);
      },
      onChooseQLabRoot: () => {
        void this.chooseQLabRoot(win).catch((error) => this.reportError(error));
      },
      onQLabCommand: (command) => {
        void this.insertQLabCommand(view, command).catch((error) => this.reportError(error));
      },
      onCaptureChatDraft: () => {
        void this.captureChatDraft().catch((error) => this.reportError(error));
      },
      onOpenWorkbench: () => {
        void this.openWorkbenchTab(win).catch((error) => this.reportError(error));
      },
    });
    const storedSize = /^(\d+)x(\d+)$/.exec(prefString("floatSize", ""));
    if (storedSize) {
      const width = Number(storedSize[1]);
      const height = Number(storedSize[2]);
      if (width > 0 && height > 0) view.restoreSize(width, height);
    }
    entry = { host, view, focusReturn: null };
    this.floatPanels.set(win, entry);
    return entry;
  }

  private createWorkbenchView(host: HTMLElement, win: Window, tabID: string): SidebarView {
    let view!: SidebarView;
    view = new SidebarView(host, {
      onSend: (text) => void this.sendChat(text).catch((error) => this.reportError(error)),
      onStop: () => void this.codex.interrupt().catch((error) => this.reportError(error)),
      onNewThread: () => void this.newChat(view).catch((error) => this.reportError(error)),
      onSelectThread: (threadID) => void this.selectThread(view, threadID),
      onDeleteThread: (threadID) => void this.codex.deleteThread(threadID).catch((error) => this.reportError(error)),
      onLogin: () => void this.codex.login().catch((error) => this.reportError(error)),
      onLogout: () => void this.codex.logout().catch((error) => this.reportError(error)),
      onOpenTerminal: () => {
        void this.toggleWorkbenchTerminal(view, win).catch((error) => this.reportError(error));
      },
      onOpenWorkbench: () => win.Zotero_Tabs?.select?.(tabID),
      onRefreshContext: () => void this.refreshContext().catch((error) => this.reportError(error)),
      onInsertSelection: () => void this.attachSelection(false),
      onModelChange: (model) => { void this.handleModelSelection(model); },
      onEffortChange: (effort) => {
        this.selectedEffort = effort;
        setPrefString("reasoningEffort", effort);
        this.renderChatViews();
      },
      onAddContext: (suggestion) => this.addInteractionContext(suggestion),
      onRemoveContext: (contextID) => this.removeInteractionContext(contextID),
      onReviewDecision: (reviewID, decision) => {
        void this.resolveMutationReview(reviewID, decision);
      },
      onApprovalDecision: (approvalID, decision) => {
        if (!this.codex.resolveApproval(approvalID, decision)) {
          this.reportError(new Error("This approval request has expired"));
        }
      },
      onRestoreCheckpoint: (checkpointID) => {
        void this.restoreCheckpoint(checkpointID).catch((error) => this.reportError(error));
      },
      onPaperTrailConsent: (decision) => {
        const context = this.context;
        if (context) void this.paperTrail.resolveConsent(context, decision);
      },
      onNotingStart: () => { void this.noting.run(); },
      onNotingDecision: (decision) => { void this.noting.decide(decision); },
      onNotingApply: (mode) => { void this.noting.apply(mode).catch(() => {}); },
      onNotingCancel: () => { this.noting.cancel(); },
      onChooseQLabRoot: () => {
        void this.chooseQLabRoot(win).catch((error) => this.reportError(error));
      },
      onCaptureChatDraft: () => {
        void this.captureChatDraft().catch((error) => this.reportError(error));
      },
      onChoosePaper: () => {
        void this.chooseWorkbenchPaper(win, tabID).catch((error) => this.reportError(error));
      },
      onOpenPaper: () => {
        void this.openContextPDF().catch((error) => this.reportError(error));
      },
      onCheckMainSite: () => this.mainSite.isAvailable(),
      onDeployMainSite: async (onProgress) => {
        let root = this.settings?.qlabRoot || "";
        if (!root) root = await this.chooseQLabRoot(win) || "";
        await this.mainSite.deploy(root, onProgress);
      },
      onOpenDocument: (relativePath) => void this.openQmdDocument(view, relativePath, win),
    }, { surface: "workbench" });
    return view;
  }

  /**
   * Previews one QMD, and offers to hand it to a real editor.
   *
   * The workspace is created on first use rather than with the sidebar,
   * because most sessions never open one.
   */
  private async openQmdDocument(
    sidebar: SidebarView,
    relativePath: string,
    win = Zotero.getMainWindow(),
  ): Promise<void> {
    let root = this.settings?.qlabRoot || "";
    if (!root) root = await this.chooseQLabRoot(win) || "";
    if (!root) return;

    const workspace = sidebar.attachWorkspace((host: HTMLElement) => new QmdWorkspaceView(host, {
      onBack: () => sidebar.setWorkspaceOpen(false),
      renderService: this.qmdRender,
      index: () => buildQmdIndex(geckoScanner, this.settings?.qlabRoot || ""),
      editors: () => this.availableEditors(),
      openExternally: (editor, path) => openInExternalEditor(
        this.externalEditorRuntime(),
        editor,
        this.settings?.qlabRoot || "",
        path,
      ),
      onEditorChosen: (editorId) => setPrefString("externalEditor", editorId),
      onActiveDocument: (path) => this.codex.setActiveDocument(path ? { relativePath: path } : null),
    }));
    if (!workspace) return;
    workspace.repoRootHint = root;
    sidebar.setWorkspaceOpen(true);
    await workspace.open(relativePath);
  }

  /** Spawns a launcher through the native bridge, with no shell in between. */
  private externalEditorRuntime(): ReturnType<typeof createExternalEditorRuntime> {
    return createExternalEditorRuntime(async (argv) => {
      await this.bridge.start();
      await this.bridge.spawnPipe(`open-editor-${Date.now()}`, {
        argv: [...argv],
        cwd: this.settings?.qlabRoot || "/",
        env: { PATH: "/usr/bin:/bin:/usr/sbin:/sbin" },
      });
    });
  }

  /** The installed editors, with the remembered one first. */
  private async availableEditors(): Promise<ExternalEditorApp[]> {
    const installed = await installedEditors(this.externalEditorRuntime());
    const remembered = preferredEditor(installed, prefString("externalEditor", ""));
    if (!remembered) return installed;
    return [remembered, ...installed.filter((editor) => editor.id !== remembered.id)];
  }

  private async openWorkbenchTab(win = Zotero.getMainWindow()): Promise<void> {
    if (!win) throw new Error("The Zotero main window is unavailable");
    const selectedType = String(win.Zotero_Tabs?.selectedType || "");
    const selectedIsReader = this.isReaderTabType(selectedType);
    const existing = this.workbenchTabs.entries(win)[0];
    if (existing && !selectedIsReader) {
      win.Zotero_Tabs?.select?.(existing.id);
      this.renderChatViews();
      existing.view.focusComposer();
      if (!this.codex.state.connected) await this.ensureChatSession();
      return;
    }
    if (selectedIsReader) {
      await this.refreshContext().catch((error) => {
        if (!isStaleReaderCaptureError(error)) throw error;
      });
    }
    else if (selectedType !== QLAB_WORKBENCH_TAB_TYPE) {
      this.context = null;
      this.addedContextIDs.delete("current-selection");
      this.updateInteractionContext();
    }
    const context = selectedIsReader || selectedType === QLAB_WORKBENCH_TAB_TYPE
      ? this.context
      : null;
    const data: WorkbenchTabData = {
      ...(this.context?.attachment.id ? { itemID: this.context.attachment.id } : {}),
      icon: QLAB_WORKBENCH_TAB_ICON,
      title: context ? `QLab · ${paperTitle(context)}` : "QLab Workbench",
    };
    const entry = this.workbenchTabs.open(win, data);
    Zotero.Session?.debounceSave?.();
    this.renderChatViews();
    entry.view.focusComposer();
    if (!this.codex.state.connected) {
      await this.ensureChatSession();
      entry.view.focusComposer();
    }
  }

  private async chooseWorkbenchPaper(win: Window, tabID: string): Promise<void> {
    const deferred = Zotero.Promise.defer();
    const io: any = {
      dataIn: null,
      dataOut: null,
      deferred,
      itemTreeID: "qlab-workbench-select-paper",
      singleSelection: true,
      hideCollections: ["duplicates", "trash", "feeds"],
    };
    (win as any).openDialog(
      "chrome://zotero/content/selectItemsDialog.xhtml",
      "",
      "chrome,dialog=no,centerscreen,resizable=yes",
      io,
    );
    await deferred.promise;
    const selectedID = Array.isArray(io.dataOut) ? io.dataOut[0] : null;
    if (!selectedID) return;

    const selected = await Zotero.Items.getAsync(selectedID);
    if (!selected) throw new Error("The selected Zotero item does not exist");
    let attachment = selected;
    if (!selected.isPDFAttachment?.()) {
      attachment = selected.isRegularItem?.() ? await selected.getBestAttachment?.() : null;
    }
    const isPDF = Boolean(attachment?.isPDFAttachment?.())
      || attachment?.attachmentContentType === "application/pdf";
    if (!attachment?.id || !isPDF) {
      throw new Error("This Zotero item has no readable PDF attachment");
    }

    const opened = await Zotero.Reader.open(attachment.id, null, {
      allowDuplicate: false,
      openInBackground: true,
      preventJumpback: true,
    });
    let accepted: ReaderContext | null = null;
    let lastError: unknown = null;
    for (let attempt = 0; attempt < 80 && !accepted; attempt++) {
      const reader = opened || Zotero.Reader?._readers?.find(
        (candidate: any) => String(candidate?.itemID) === String(attachment.id),
      );
      if (reader) {
        try {
          accepted = await this.readerContext.acceptReaderHook({
            reader,
            item: attachment,
            params: {},
          });
        }
        catch (error) {
          lastError = error;
        }
      }
      if (!accepted) await new Promise<void>((resolve) => win.setTimeout(resolve, 75));
    }
    if (!accepted) {
      throw lastError instanceof Error
        ? lastError
        : new Error("Zotero Reader has not prepared this paper yet; try again shortly");
    }

    this.addedContextIDs.delete("current-selection");
    const requestSequence = ++this.contextRequestSequence;
    await this.applyContext(accepted, requestSequence);
    this.workbenchTabs.update(win, tabID, {
      itemID: attachment.id,
      icon: QLAB_WORKBENCH_TAB_ICON,
      title: `QLab · ${paperTitle(accepted)}`,
    });
    Zotero.Session?.debounceSave?.();
    this.renderChatViews();
    this.workbenchTabs.entries(win).find((entry) => entry.id === tabID)?.view.focusComposer();
  }

  private async openWorkbenchWindow(source: Window): Promise<Window> {
    const existing = new Set<Window>(Zotero.getMainWindows?.() || []);
    Zotero.openMainWindow?.();
    for (let attempt = 0; attempt < 200; attempt++) {
      await new Promise<void>((resolve) => setTimeout(resolve, 50));
      const target = (Zotero.getMainWindows?.() || []).find(
        (candidate: Window) => candidate !== source && !existing.has(candidate) && !candidate.closed,
      );
      if (!target) continue;
      // Window enumeration happens before Zotero has necessarily installed
      // its native tab deck. Returning in that gap makes moveToNewWindow try
      // Zotero_Tabs.add too early and silently strands an empty window.
      if (!target.document?.documentElement || typeof target.Zotero_Tabs?.add !== "function") {
        continue;
      }
      if (!this.shortcutWindows.has(target)) await this.onMainWindowLoad(target);
      if (typeof target.Zotero_Tabs?.add !== "function") continue;
      return target;
    }
    throw new Error("The new Zotero window could not prepare a native tab");
  }

  private async toggleFloatPanel(): Promise<void> {
    const win = Zotero.getMainWindow();
    if (!win) return;
    const existing = this.floatPanels.get(win);
    if (existing?.view.isVisible()) {
      this.hideFloatPanel(win);
      return;
    }
    await this.openFloatPanel(win);
  }

  /**
   * Ensure-open semantics for callers (like resumeAnchorChat) that must
   * never close an already-visible panel -- unlike toggleFloatPanel (⌘K),
   * which is meant to toggle. No-ops when the panel is already visible;
   * otherwise opens it via the same path toggleFloatPanel uses.
   */
  private async ensureFloatPanelOpen(): Promise<void> {
    const win = Zotero.getMainWindow();
    if (!win) return;
    if (this.floatPanels.get(win)?.view.isVisible()) return;
    await this.openFloatPanel(win);
  }

  private async openFloatPanel(win: Window): Promise<void> {
    const entry = this.mountFloatPanel(win);
    const active = win.document.activeElement;
    entry.focusReturn = active && active !== win.document.body
      ? active as HTMLElement
      : null;
    // The selection-popup hook keeps this.context.selection fresh, so the
    // cached value is what the user just highlighted (mirrors ⌘L).
    if (this.context?.selection?.text) {
      this.addedContextIDs.add("current-selection");
      this.chatError = "";
      this.updateInteractionContext();
    }
    entry.view.show();
    this.renderChatViews();
    entry.view.focusComposer();
    if (this.codex.state.connected) {
      // Session already live: refresh context in the background without
      // flipping chatPhase, so the composer stays enabled and focused.
      void this.refreshContext()
        .then(() => this.renderChatViews())
        .catch(() => { /* stale reader capture is non-fatal here */ });
    }
    else {
      void this.ensureChatSession()
        .then(() => entry.view.focusComposer())
        .catch((error) => this.reportError(error));
    }
  }

  private hideFloatPanel(win: Window): void {
    const entry = this.floatPanels.get(win);
    if (!entry?.view.isVisible()) return;
    entry.view.hide();
    // Every user-facing "close" (close button, Escape, ⌘K toggle, Mark
    // Understood) funnels through here. If a turn is running when this
    // fires, remember it so maybeAutoOpenFloatForRunningTurn() doesn't
    // immediately force the panel back open and fight the user (bug-triage
    // #2's "at most once per turn, respect an explicit dismissal" rule).
    if (this.codex?.state.running && this.currentTurnId) {
      this.floatDismissedTurnId = this.currentTurnId;
    }
    const target = entry.focusReturn;
    entry.focusReturn = null;
    if (target?.isConnected) {
      try { target.focus(); }
      catch { /* previously focused node may be gone */ }
    }
  }

  private renderFloatPanels(): void {
    const context = this.context;
    for (const [win, entry] of this.floatPanels) {
      if (win.closed || !entry.host.isConnected) {
        entry.view.destroy();
        entry.host.remove();
        this.floatPanels.delete(win);
        continue;
      }
      entry.view.setState({
        phase: this.chatPhase,
        running: this.codex.state.running,
        error: this.chatError || this.codex.state.fallbackReason || undefined,
        entries: latestExchange(this.codex.getChatEntries()),
        paperTitle: context ? paperTitle(context) : "Paper Assistant",
        models: this.codex.state.models,
        selectedModel: this.selectedModel,
        capabilities: {
          supportsAgentMode: this.codex.state.capabilities?.supportsAgentMode !== false,
          supportsLogin: this.codex.state.capabilities?.supportsLogin !== false,
        },
        selection: this.addedContextIDs.has("current-selection") && context?.selection?.text
          ? {
            text: context.selection.text,
            pageNumber: context.selection.pageNumber ?? context.page.pageNumber,
          }
          : null,
        turnStartedAt: this.codex.state.running
          ? this.turnStartedAt.get(this.codex.state.activeThreadId ?? "") ?? null
          : null,
        turnDurations: this.turnDurationsForActiveThread(),
        opacity: this.floatOpacity,
        anchorConfirmation: this.paperTrail?.lastConfirmation() ?? null,
        canResolveAnchor: Boolean(this.paperTrail && this.latestOpenAnchor()),
        paperTrailConsent: this.paperTrail?.consentRequest() ?? null,
        qlabRoot: this.settings?.qlabRoot || "",
      });
    }
  }

  private renderWorkbenchTabs(): void {
    const context = this.context;
    const plan = normalizePlan(this.codex.getActivePlan());
    const mutationReviews = this.mutations?.getReviews() || [];
    const workspaceDiffs: DiffReview[] = this.codex.getActiveDiffs().map((diff) => ({
      id: `workspace:${diff.turnId}`,
      title: "Agent workspace diff",
      summary: "Applied only inside Zotkit's private staging workspace. Zotero and the original PDF are unchanged until a separate reviewed Apply.",
      diff: diff.diff,
      state: "accepted",
    }));
    const pending = this.codex.getPendingApprovals()[0];
    const pendingApproval: PendingApproval | null = pending ? {
      id: pending.id,
      title: pending.title,
      description: formatPendingApprovalDescription(pending),
      command: pending.command,
      kind: pending.kind === "commandExecution" ? "command"
        : pending.kind === "permissions" ? "permission" : "tool",
      risk: pending.kind === "permissions" ? "high" : "medium",
    } : null;
    const conversationCheckpoints: CheckpointOption[] = this.codex.getCheckpoints().map((checkpoint) => ({
      id: `conversation:${checkpoint.id}`,
      label: `Conversation · ${checkpoint.label}`,
      createdAt: checkpoint.createdAt,
    }));
    const checkpoints = [
      ...this.mutationCheckpoints.map((checkpoint) => ({ ...checkpoint, id: `zotero:${checkpoint.id}` })),
      ...conversationCheckpoints,
    ].sort((a, b) => String(b.createdAt || "").localeCompare(String(a.createdAt || "")));
    for (const entry of this.workbenchTabs?.entries() || []) {
      entry.view.setState({
        phase: this.chatPhase,
        accountLabel: this.codex.state.connected ? this.codex.accountLabel() : undefined,
        error: this.chatError || this.codex.state.fallbackReason || undefined,
        capabilities: {
          supportsAgentMode: this.codex.state.capabilities?.supportsAgentMode !== false,
          supportsLogin: this.codex.state.capabilities?.supportsLogin !== false,
        },
        qlabRoot: this.settings?.qlabRoot || "",
        context: context ? {
          key: `${context.attachment.libraryID ?? "0"}-${context.attachment.key}`,
          title: paperTitle(context),
          authors: contextCreators(context),
          pageLabel: context.page.pageLabel || String(context.page.pageNumber),
          pageIndex: context.page.pageIndex,
          pagesCount: context.page.pageCount,
          selectionText: context.selection?.text,
          pdfPath: context.pdfPath || undefined,
        } : null,
        entries: this.codex.getChatEntries(),
        models: this.codex.state.models,
        threads: this.codex.getThreadOptions().map((thread) => ({
          ...thread,
          status: thread.id === this.codex.state.switchingThreadId ? "switching"
            : thread.active && this.codex.state.running ? "running"
            : pendingApproval && thread.active ? "attention" : "idle",
        })),
        selectedModel: this.selectedModel,
        effort: this.selectedEffort,
        running: this.codex.state.running,
        creatingThread: this.codex.state.creatingThread,
        threadTitle: context
          ? paperTitle(context)
          : entry.data.title.replace(/^QLab\s*·\s*/, "") || "Paper Assistant",
        mode: this.codex.state.mode,
        contextChips: this.contextChips(),
        contextSuggestions: this.contextSuggestions(),
        plan,
        reviews: [...mutationReviews, ...workspaceDiffs],
        pendingApproval,
        checkpoints,
        turnStartedAt: this.codex.state.running
          ? this.turnStartedAt.get(this.codex.state.activeThreadId ?? "") ?? null
          : null,
        turnDurations: this.turnDurationsForActiveThread(),
        paperTrailConsent: this.paperTrail?.consentRequest() ?? null,
        noting: this.noting?.view() ?? null,
      });
    }
  }

  private attachSelection(focus: boolean): void {
    if (!this.context?.selection?.text) {
      this.chatError = "Select text in the PDF first";
      this.renderChatViews();
      if (focus) this.activeChatView()?.focusComposer();
      return;
    }
    this.addedContextIDs.add("current-selection");
    this.chatError = "";
    this.updateInteractionContext();
    this.renderChatViews();
    if (focus) this.activeChatView()?.focusComposer();
  }

  private addInteractionContext(suggestion: ResearchContextSuggestion): void {
    this.addedContextIDs.add(suggestion.id);
    this.updateInteractionContext();
    this.renderChatViews();
  }

  private removeInteractionContext(contextID: string): void {
    this.addedContextIDs.delete(contextID);
    this.updateInteractionContext();
    this.renderChatViews();
  }

  private updateInteractionContext(): void {
    const context = this.context;
    const interaction: Record<string, CodexInteractionContextEntry> = {};
    if (this.settings?.qlabRoot) {
      interaction["QLab repository"] = {
        kind: "application",
        value: [
          `The user selected this QLab repository: ${this.settings.qlabRoot}`,
          "Read and obey its AGENTS.md before repository work.",
          "literature/ is external evidence, drafts/ is untrusted work, and knowledge/ is trusted only after a user-reviewed promotion.",
          "Use only local files and stable repository commands. Never deploy previews.",
        ].join("\n"),
      };
    }
    if (this.addedContextIDs.has("active-annotations")) {
      interaction["Requested Zotero annotations"] = {
        kind: "application",
        value: "The user attached this paper's annotations. Call zotero_list_annotations before answering when relevant.",
      };
    }
    if (this.addedContextIDs.has("zotero-library")) {
      interaction["Requested Zotero library"] = {
        kind: "application",
        value: "The user attached their Zotero library. Use the Zotero library search tools when useful.",
      };
    }
    if (this.addedContextIDs.has("current-selection") && context?.selection?.text) {
      interaction["Pinned Reader selection"] = {
        kind: "untrusted",
        value: context.selection.text.slice(0, 12_000),
      };
    }
    this.codex?.setInteractionContext(interaction);
  }

  turnDurationsForActiveThread(): Record<string, number> {
    const threadId = this.codex?.state.activeThreadId;
    const meta = threadId ? this.turnMeta.get(threadId) : undefined;
    const out: Record<string, number> = {};
    if (meta) for (const [id, value] of meta) out[id] = value.elapsedMs;
    return out;
  }

  /** Starts the clock when a turn begins running and records its duration once it stops. */
  private trackTurnTiming(): void {
    const threadId = this.codex?.state.activeThreadId;
    if (!threadId) return;
    const running = Boolean(this.codex?.state.running);
    const started = this.turnStartedAt.get(threadId);
    if (running && started === undefined) {
      this.turnStartedAt.set(threadId, Date.now());
      return;
    }
    if (!running) {
      if (started !== undefined) {
        const entries = this.codex?.getChatEntries() ?? [];
        let lastUserId: string | null = null;
        for (let i = entries.length - 1; i >= 0; i--) {
          if (entries[i]!.kind === "user") { lastUserId = entries[i]!.id; break; }
        }
        if (lastUserId) {
          const perThread = this.turnMeta.get(threadId) ?? new Map<string, TurnMeta>();
          perThread.set(lastUserId, {
            elapsedMs: Date.now() - started,
            completedAt: new Date().toISOString(),
            model: this.selectedModel,
          });
          this.turnMeta.set(threadId, perThread);
          if (this.paperTrail && this.context) {
            void this.paperTrail.completeTurn(
              this.context,
              threadId,
              this.codex?.getChatEntries() ?? [],
              Math.max(0, this.codex.activeThreadTurnCount() - 1),
            ).catch((error) => Zotero?.debug?.(`[Zotkit] paper-trail completeTurn failed: ${String(error)}`));
          }
        }
      }
      // `running` is service-wide: once nothing is running, every remaining start
      // timestamp (for threads other than the active one, or left over from an
      // interrupted switch) is stale by definition. Drop them all so reopening an
      // idle thread later can't fabricate a completed turn from a stale timer.
      this.turnStartedAt.clear();
    }
  }

  /** Resolves the current reader attachment to a live Zotero item. */
  private readerContextItem(): any {
    const attachment = this.context?.attachment;
    if (!attachment?.id) return null;
    return Zotero.Items?.get?.(attachment.id)
      ?? Zotero.Items?.getByLibraryAndKey?.(attachment.libraryID, attachment.key)
      ?? null;
  }

  private renderChatViews(): void {
    this.trackTurnTiming();
    if (!this.codex) return;
    this.updateTurnTracking();
    const context = this.context;
    const plan = normalizePlan(this.codex.getActivePlan());
    const mutationReviews = this.mutations?.getReviews() || [];
    const workspaceDiffs: DiffReview[] = this.codex.getActiveDiffs().map((diff) => ({
      id: `workspace:${diff.turnId}`,
      title: "Agent workspace diff",
      summary: "Applied only inside Zotkit's private staging workspace. Zotero and the original PDF are unchanged until a separate reviewed Apply.",
      diff: diff.diff,
      state: "accepted",
    }));
    const pending = this.codex.getPendingApprovals()[0];
    const pendingApproval: PendingApproval | null = pending ? {
      id: pending.id,
      title: pending.title,
      description: formatPendingApprovalDescription(pending),
      command: pending.command,
      kind: pending.kind === "commandExecution" ? "command"
        : pending.kind === "permissions" ? "permission" : "tool",
      risk: pending.kind === "permissions" ? "high" : "medium",
    } : null;
    const conversationCheckpoints: CheckpointOption[] = this.codex.getCheckpoints().map((checkpoint) => ({
      id: `conversation:${checkpoint.id}`,
      label: `Conversation · ${checkpoint.label}`,
      createdAt: checkpoint.createdAt,
    }));
    const checkpoints = [
      ...this.mutationCheckpoints.map((checkpoint) => ({ ...checkpoint, id: `zotero:${checkpoint.id}` })),
      ...conversationCheckpoints,
    ].sort((a, b) => String(b.createdAt || "").localeCompare(String(a.createdAt || "")));
    for (const [body, view] of this.chatViews) {
      if (!body.isConnected) {
        view.destroy();
        this.chatViews.delete(body);
        continue;
      }
      view.setState({
        phase: this.chatPhase,
        accountLabel: this.codex.state.connected ? this.codex.accountLabel() : undefined,
        error: this.chatError || this.codex.state.fallbackReason || undefined,
        capabilities: {
          supportsAgentMode: this.codex.state.capabilities?.supportsAgentMode !== false,
          supportsLogin: this.codex.state.capabilities?.supportsLogin !== false,
        },
        qlabRoot: this.settings?.qlabRoot || "",
        context: context ? {
          key: `${context.attachment.libraryID ?? "0"}-${context.attachment.key}`,
          title: paperTitle(context),
          authors: contextCreators(context),
          pageLabel: context.page.pageLabel || String(context.page.pageNumber),
          pageIndex: context.page.pageIndex,
          pagesCount: context.page.pageCount,
          selectionText: context.selection?.text,
          pdfPath: context.pdfPath || undefined,
        } : null,
        entries: this.codex.getChatEntries(),
        models: this.codex.state.models,
        threads: this.codex.getThreadOptions().map((thread) => ({
          ...thread,
          status: thread.id === this.codex.state.switchingThreadId ? "switching"
            : thread.active && this.codex.state.running ? "running"
            : pendingApproval && thread.active ? "attention" : "idle",
        })),
        selectedModel: this.selectedModel,
        effort: this.selectedEffort,
        running: this.codex.state.running,
        creatingThread: this.codex.state.creatingThread,
        threadTitle: context ? paperTitle(context) : "Paper Assistant",
        mode: this.codex.state.mode,
        contextChips: this.contextChips(),
        contextSuggestions: this.contextSuggestions(),
        plan,
        reviews: [...mutationReviews, ...workspaceDiffs],
        pendingApproval,
        checkpoints,
        turnStartedAt: this.codex.state.running
          ? this.turnStartedAt.get(this.codex.state.activeThreadId ?? "") ?? null
          : null,
        turnDurations: this.turnDurationsForActiveThread(),
        paperTrailConsent: this.paperTrail?.consentRequest() ?? null,
        noting: this.noting?.view() ?? null,
      });
    }
    // `this.chatViews` is now pruned to connected bodies only -- this is the
    // right point to decide whether a running turn needs the float panel
    // forced open (bug-triage #2).
    this.maybeAutoOpenFloatForRunningTurn();
    this.renderFloatPanels();
    this.renderWorkbenchTabs();
  }

  /**
   * Advances the plugin-local turn identity on every false→true edge of
   * codex.state.running (a genuinely new turn -- not a mid-turn steer, which
   * leaves `running` continuously true), and resets the auto-open/dismissal
   * trackers for that new turn. Called on every renderChatViews() pass, so
   * `currentTurnId` is always current by the time it's read elsewhere.
   */
  private updateTurnTracking(): void {
    const running = Boolean(this.codex?.state.running);
    if (running && !this.wasCodexRunning) {
      this.turnGeneration += 1;
      this.autoOpenedFloatTurnId = null;
      this.floatDismissedTurnId = null;
    }
    this.currentTurnId = running ? `turn-${this.turnGeneration}` : null;
    this.wasCodexRunning = running;
  }

  /**
   * Bug-triage #2: a running turn has no visible surface once the sidebar's
   * chat views all disconnect (section collapsed/closed) -- streaming
   * continues into the store, but nothing shows it, and the user reads that
   * as "AI stopped". Force the float panel open in that case, reusing the
   * ensure-open path resumeAnchorChat() uses so an already-open panel is
   * never closed.
   */
  private maybeAutoOpenFloatForRunningTurn(): void {
    if (!this.codex.state.running) return;
    // Some plugin-state tests exercise renderChatViews() against a plugin
    // instance without a full Zotero stub -- mirror the same defensive
    // access installShortcutHandler's Escape handler uses.
    const win = typeof Zotero === "undefined" ? null : Zotero.getMainWindow?.();
    if (!win) return;
    const floatVisible = Boolean(this.floatPanels.get(win)?.view.isVisible());
    const shouldOpen = shouldAutoOpenFloat({
      running: this.codex.state.running,
      hasConnectedViews: this.chatViews.size > 0 || (this.workbenchTabs?.entries().length || 0) > 0,
      floatVisible,
      autoOpenedTurnId: this.autoOpenedFloatTurnId,
      dismissedTurnId: this.floatDismissedTurnId,
      activeTurnId: this.currentTurnId,
    });
    if (!shouldOpen) return;
    this.autoOpenedFloatTurnId = this.currentTurnId;
    void this.ensureFloatPanelOpen().catch((error) => this.reportError(error));
  }

  /** The active thread's most recently opened (unresolved) paper-trail anchor, if any. */
  private latestOpenAnchor(): AnchorRecord | null {
    return this.context
      ? [...this.codex.getAnchors(this.context)].reverse().find(
        (anchor) => anchor.threadId === this.codex.state.activeThreadId && anchor.status === "open",
      ) ?? null
      : null;
  }

  /** Looks up a paper-trail anchor for the current paper by id -- null when there is no active context or no match. */
  private findAnchor(anchorId: string): AnchorRecord | null {
    const context = this.context;
    if (!context) return null;
    return this.codex.getAnchors(context).find((anchor) => anchor.anchorId === anchorId) ?? null;
  }

  /**
   * Assembles the data NotingService.run() needs to draft a reading note:
   * every anchor's Q/A history (read per-turn, closed-range sliced by the
   * anchor's `turnRange`), the user's own annotations (with the ones
   * paper-trail itself wrote -- identified by `annotationKey` -- excluded,
   * since those are already covered by the anchor Q/A), and whether the PDF
   * on disk still matches the hash any anchor was created against.
   */
  private async buildNotingSnapshot(): Promise<NotingSnapshot> {
    const context = this.context;
    if (!context) throw new Error("No paper context is available");

    const anchors = this.codex.getAnchors(context);
    const threadIds = [...new Set(anchors.map((anchor) => anchor.threadId))];
    const turnsByThread = new Map<string, ChatEntry[][]>();
    for (const threadId of threadIds) {
      try {
        turnsByThread.set(threadId, await this.codex.readThreadTurns(threadId));
      }
      catch {
        turnsByThread.set(threadId, []);
      }
    }
    const notingAnchors: NotingAnchorInput[] = anchors.map((anchor) => {
      const turns = turnsByThread.get(anchor.threadId) ?? [];
      const [start, end] = anchor.turnRange;
      const qa = turns.slice(start, end + 1)
        .flatMap((turnEntries) => buildQaFromEntries(turnEntries, undefined));
      return {
        anchorId: anchor.anchorId,
        pageNumber: anchor.pageNumber,
        status: anchor.status,
        question: anchor.question,
        answerSummary: anchor.answerSummary,
        qa,
      };
    });

    const annotatedByAnchor = new Set(
      anchors.map((anchor) => anchor.annotationKey).filter((key): key is string => Boolean(key)),
    );
    let userAnnotations: NotingSnapshot["userAnnotations"] = [];
    try {
      const { annotations } = await this.readerContext.listAnnotations();
      userAnnotations = annotations
        .filter((annotation) => !annotatedByAnchor.has(annotation.key))
        .map((annotation) => ({
          pageNumber: annotation.pageNumber,
          type: annotation.type,
          text: annotation.text,
          comment: annotation.comment,
        }));
    }
    catch {
      userAnnotations = [];
    }

    const pdfSha256Now = await this.notingPdfSha256Now(context);
    const hashMismatch = anchors.some((anchor) => anchor.pdfSha256 !== null && anchor.pdfSha256 !== pdfSha256Now);

    return {
      paperTitle: paperTitle(context),
      itemKey: context.parent?.key ?? null,
      attachmentKey: context.attachment.key,
      libraryID: context.attachment.libraryID ?? "0",
      pdfSha256Now,
      hashMismatch,
      anchors: notingAnchors,
      userAnnotations,
      createdAt: new Date().toISOString(),
    };
  }

  private async notingPdfSha256Now(context: ReaderContext): Promise<string | null> {
    try {
      const file = await this.anchorHost.attachmentFile(context.attachment.libraryID ?? "0", context.attachment.key);
      if (!file) return null;
      return sha256File(file.path, file.size);
    }
    catch {
      return null;
    }
  }

  /** Any already-mounted chat pane's document -- KaTeX rendering needs a real Document to build DOM into. */
  private mainDocument(): Document | null {
    const mounted = this.chatViews.keys().next().value;
    return mounted ? mounted.ownerDocument : (Zotero.getMainWindow()?.document ?? null);
  }

  private countNotingMathErrors(markdown: string): number {
    const doc = this.mainDocument();
    if (!doc) return 0;
    try {
      return countMathErrors(doc, markdown);
    }
    catch {
      return 0;
    }
  }

  /** Opens the Reader at the anchor's annotation (or raw position, when the highlight write never landed). */
  private async jumpToAnchor(anchor: AnchorRecord): Promise<void> {
    const attachment = Zotero.Items?.getByLibraryAndKey?.(anchor.libraryID, anchor.attachmentKey);
    if (!attachment?.id) return;
    const location = anchor.annotationKey
      ? { annotationID: anchor.annotationKey }
      : anchor.position
        ? { position: anchor.position }
        : undefined;
    await Zotero.Reader?.open?.(attachment.id, location, { allowDuplicate: false });
  }

  /**
   * "Continue Conversation" from a batch-written annotation: switches to the anchor's
   * thread (via the same codex.switchThread() path onSelectThread uses) when
   * it isn't already active, then opens the float panel. When no anchor
   * matches the annotation, just opens the panel as-is. Uses
   * ensureFloatPanelOpen() rather than toggleFloatPanel() -- this action
   * always means "open" (per the plan's "open popup"), so it must never close
   * a panel the user already has open.
   */
  private async resumeAnchorChat(annotationKey: string): Promise<void> {
    const context = this.context;
    const anchor = context
      ? this.codex.getAnchors(context).find((entry) => entry.annotationKey === annotationKey)
      : undefined;
    if (anchor && anchor.threadId !== this.codex.state.activeThreadId) {
      await this.codex.switchThread(anchor.threadId);
    }
    await this.ensureFloatPanelOpen();
  }

  private handleCodexState(): void {
    if (this.codex.state.connected) {
      this.chatPhase = this.codex.isSignedIn() ? "ready" : "signed-out";
      if (this.codex.isSignedIn()) this.chatError = "";
    }
    else if (this.chatPhase === "ready") {
      this.chatPhase = "error";
      this.chatError ||= "The Codex connection was lost. Retry; the advanced Terminal remains available.";
    }
    this.scheduleChatRender();
  }

  private scheduleChatRender(): void {
    if (this.chatRenderTimer || this.destroyed) return;
    this.chatRenderTimer = setTimeout(() => {
      this.chatRenderTimer = null;
      this.renderChatViews();
    }, 50);
  }

  private contextChips(): ResearchContextChip[] {
    const context = this.context;
    if (!context) return [];
    const chips: ResearchContextChip[] = [{
      id: "active-paper",
      kind: "paper",
      label: "Current Paper",
      detail: paperTitle(context),
      removable: false,
    }, {
      id: "current-page",
      kind: "page",
      label: `Page ${context.page.pageLabel || context.page.pageNumber}`,
      detail: "Updates automatically with Reader",
      removable: false,
    }];
    if (context.selection?.text) chips.push({
      id: "current-selection",
      kind: "selection",
      label: `Selection · ${context.selection.text.length} characters`,
      detail: "Updates automatically with the Reader selection",
      removable: false,
    });
    if (this.addedContextIDs.has("active-annotations")) chips.push({
      id: "active-annotations",
      kind: "annotation",
      label: "Paper Annotations",
      removable: true,
    });
    if (this.addedContextIDs.has("zotero-library")) chips.push({
      id: "zotero-library",
      kind: "library",
      label: "Zotero Library",
      removable: true,
    });
    return chips;
  }

  private contextSuggestions(): ResearchContextSuggestion[] {
    const context = this.context;
    return [{
      id: "active-paper",
      kind: "paper",
      label: "Current Paper",
      detail: context ? paperTitle(context) : "Open a PDF first",
      disabled: !context,
    }, {
      id: "current-page",
      kind: "page",
      label: "Current Page",
      detail: context ? `PDF page ${context.page.pageNumber}` : "Open a PDF first",
      disabled: !context,
    }, {
      id: "current-selection",
      kind: "selection",
      label: "Current Selection",
      detail: context?.selection?.text ? `${context.selection.text.length} characters` : "Select PDF text first",
      disabled: !context?.selection?.text,
    }, {
      id: "active-annotations",
      kind: "annotation",
      label: "Annotations for this paper",
      detail: "Highlights, comments, and page numbers",
      disabled: !context || this.addedContextIDs.has("active-annotations"),
    }, {
      id: "zotero-library",
      kind: "library",
      label: "Zotero Library",
      detail: "Search other papers, collections, and tags",
      disabled: this.addedContextIDs.has("zotero-library"),
    }];
  }

  private async refreshMutationCheckpoints(): Promise<void> {
    if (!this.mutations) return;
    this.mutationCheckpoints = await this.mutations.getCheckpoints();
    this.renderChatViews();
  }

  private async restoreCheckpoint(checkpointID: string): Promise<void> {
    if (checkpointID.startsWith("zotero:")) {
      const result = await this.mutations.restoreCheckpoint(checkpointID.slice("zotero:".length));
      await this.refreshAfterMutation(result);
      return;
    }
    if (!checkpointID.startsWith("conversation:")) throw new Error("Unknown checkpoint");
    const result = await this.codex.restoreCheckpoint(checkpointID.slice("conversation:".length));
    if (!result.filesystemRestored && result.turnDiff) {
      this.chatError = "The conversation branch was restored. The Codex protocol does not roll files back automatically; use the corresponding Zotero checkpoint to restore Zotero or PDF state.";
    }
    this.renderChatViews();
  }

  private async resolveMutationReview(
    reviewID: string,
    decision: "accept" | "reject",
  ): Promise<void> {
    try {
      const result = await this.mutations.resolveReview(reviewID, decision);
      if (result.decision === "accepted") await this.refreshAfterMutation(result);
    }
    catch (error) {
      if (error instanceof ZoteroMutationApplyError) {
        await this.refreshAfterMutation({
          decision: "accepted",
          effects: error.effects,
          checkpointID: error.checkpointID,
        }).catch((refreshError) => logError(refreshError));
      }
      this.reportError(error);
    }
  }

  private async refreshAfterMutation(result?: MutationResolution): Promise<void> {
    let reloadError: unknown = null;
    if (result?.effects.attachmentContentChanged) {
      await this.readerContext.invalidateAttachmentCaches({
        key: result.effects.attachmentKey,
        libraryID: result.effects.attachmentLibraryID,
      });
      try {
        await this.reloadReadersForAttachment(result.effects.attachmentID);
      }
      catch (error) {
        reloadError = error;
      }
    }
    await this.refreshContext();
    await this.readerContext.ensureZotkitLibrarySnapshot(true).catch(() => null);
    await this.refreshMutationCheckpoints();
    if (reloadError) throw reloadError;
  }

  private async reloadReadersForAttachment(attachmentID: number | string): Promise<void> {
    const readers = new Set<any>();
    const loaded = Zotero.Reader?._readers;
    if (Array.isArray(loaded)) {
      for (const reader of loaded) {
        if (String(reader?.itemID) === String(attachmentID)) readers.add(reader);
      }
    }
    const tabID = this.selectedTabID();
    const active = tabID ? Zotero.Reader?.getByTabID?.(tabID) : null;
    if (active && String(active.itemID) === String(attachmentID)) readers.add(active);
    const failures: string[] = [];
    for (const reader of readers) {
      try {
        await reader.reload?.();
      }
      catch (error) {
        failures.push(error instanceof Error ? error.message : String(error));
      }
    }
    if (failures.length) {
      throw new Error(`The PDF was updated, but ${failures.length} Zotero Reader view(s) failed to reload: ${failures[0]}`);
    }
  }

  private activeChatView(): SidebarView | null {
    const workbench = this.activeWorkbenchEntry()?.view;
    if (workbench instanceof SidebarView) return workbench;
    const body = this.activeSidebarBody();
    return body ? this.chatViews.get(body) || null : null;
  }

  private activeWorkbenchEntry(win = Zotero.getMainWindow()): ReturnType<WorkbenchTabManager["entries"]>[number] | null {
    if (!win) return null;
    const entries = this.workbenchTabs?.entries(win) || [];
    const selectedID = String(win.Zotero_Tabs?.selectedID || "");
    return entries.find((entry) => entry.id === selectedID) || entries[0] || null;
  }

  private openTerminal(body?: HTMLElement): Promise<void> {
    if (this.terminalOpenPromise) return this.terminalOpenPromise;
    const pending = this.openTerminalInternal(body);
    this.terminalOpenPromise = pending;
    const clearPending = () => {
      if (this.terminalOpenPromise === pending) this.terminalOpenPromise = null;
    };
    // Supplying both branches avoids the rejected promise returned by finally()
    // becoming an unhandled rejection after the original caller handles it.
    void pending.then(clearPending, clearPending);
    return pending;
  }

  private async openWorkbenchTerminal(win = Zotero.getMainWindow()): Promise<void> {
    if (!win) throw new Error("The Zotero main window is unavailable");
    await this.openWorkbenchTab(win);
    const entry = this.activeWorkbenchEntry(win);
    if (!entry) throw new Error("Unable to create the QLab Workbench");
    if (!(entry.view instanceof SidebarView)) throw new Error("The QLab Workbench is not ready");
    if (!entry.view.isTerminalOpen()) {
      await this.openWorkbenchTerminalDrawer(entry.view, win);
    }
    this.terminal.focus();
  }

  private async toggleWorkbenchTerminal(view: SidebarView, win: Window): Promise<void> {
    if (view.isTerminalOpen()) {
      view.setTerminalOpen(false);
      this.terminal.setVisible(false);
      view.focusComposer();
      return;
    }
    await this.openWorkbenchTerminalDrawer(view, win);
    this.terminal.focus();
  }

  private async openWorkbenchTerminalDrawer(view: SidebarView, win: Window): Promise<void> {
    let root = this.settings?.qlabRoot || "";
    if (!root) root = await this.chooseQLabRoot(win) || "";
    if (!root) return;
    const host = view.terminalHost();
    view.setTerminalOpen(true);
    try {
      this.terminal.mount(host);
      await this.readerContext.ensureZotkitLibrarySnapshot();
      await this.terminal.open(await this.terminalOptions(host));
    }
    catch (error) {
      view.setTerminalOpen(false);
      this.terminal.setVisible(false);
      throw error;
    }
  }

  private closeWorkbenchTerminal(win = Zotero.getMainWindow()): void {
    const entry = win ? this.activeWorkbenchEntry(win) : null;
    if (entry?.view instanceof SidebarView) {
      entry.view.setTerminalOpen(false);
      entry.view.focusComposer();
    }
    this.terminal.setVisible(false);
  }

  private async openTerminalInternal(body?: HTMLElement): Promise<void> {
    const workbenchEntry = this.workbenchTabs?.entries().find((entry) => entry.host === body)
      || (!body ? this.activeWorkbenchEntry() : null);
    if (workbenchEntry?.view instanceof SidebarView) {
      const win = workbenchEntry.host.ownerDocument.defaultView;
      if (!win) throw new Error("The Zotero main window is unavailable");
      await this.openWorkbenchTerminalDrawer(workbenchEntry.view, win);
      return;
    }
    const host = body || workbenchEntry?.host || this.activeSidebarBody();
    if (!host) throw new Error("Open the QLab Workbench first");
    this.paneMode = "terminal";
    if (workbenchEntry) {
      workbenchEntry.view.destroy();
      workbenchEntry.view = {
        show: () => this.terminal.setVisible(true),
        destroy: () => this.terminal.unmount(host),
        focusComposer: () => this.terminal.focus(),
        setState: () => {},
      };
    }
    else {
      this.chatViews.get(host)?.destroy();
      this.chatViews.delete(host);
    }
    this.terminal.mount(host);
    await this.refreshContext();
    await this.readerContext.ensureZotkitLibrarySnapshot();
    const options = await this.terminalOptions(host);
    await this.terminal.open(options);
  }

  private async switchTerminalToContext(
    ensureLibrarySnapshot = false,
    preferredHost?: HTMLElement,
    requestSequence = this.contextRequestSequence,
  ): Promise<void> {
    const host = preferredHost?.isConnected ? preferredHost : this.activeSidebarBody();
    if (!host || !this.context?.workspace) return;
    const tabID = this.sidebarTabID(host);
    if (ensureLibrarySnapshot) await this.readerContext.ensureZotkitLibrarySnapshot();
    if (
      requestSequence !== this.contextRequestSequence
      || this.destroyed
      || !host.isConnected
      || (tabID && this.selectedTabID() !== tabID)
    ) return;
    const options = await this.terminalOptions(host);
    if (
      requestSequence !== this.contextRequestSequence
      || this.destroyed
      || !host.isConnected
      || (tabID && this.selectedTabID() !== tabID)
    ) return;
    await this.terminal.switchPaper(options);
  }

  private async terminalOptions(host: HTMLElement): Promise<TerminalPaperOptions> {
    // Prepare a read-only whole-document source for the terminal MCP. This
    // references Zotero's existing index in place and only creates one bounded,
    // private fallback when that index is unavailable.
    const context = this.context;
    const root = this.settings?.qlabRoot || "";
    if (!root) throw new Error("Choose a QLab repository first");
    if (context?.workspace) await this.readerContext.ensureCurrentPdfTextReference();
    return {
      host,
      paperKey: context
        ? `${context.attachment.libraryID ?? "0"}-${context.attachment.key}`
        : `qlab-${root}`,
      paperTitle: context ? paperTitle(context) : "QLab Repository",
      workspace: context?.workspace?.root || root,
      workingDirectory: root,
      pdfPath: context?.pdfPath || null,
      librarySnapshotPath:
        this.readerContext.getCachedZotkitLibrarySnapshotReference()?.path ?? null,
      pageLabel: context ? context.page.pageLabel || String(context.page.pageNumber) : undefined,
      agent: "shell",
    };
  }

  private async openContextPDF(): Promise<void> {
    const attachment = this.readerContextItem();
    if (!attachment?.id) throw new Error("Choose a paper in the QLab tab first");
    await Zotero.Reader.open(attachment.id, null, {
      allowDuplicate: false,
      openInBackground: false,
      preventJumpback: false,
    });
  }

  private async pasteSelectionToTerminal(): Promise<void> {
    try {
      this.openSidebar();
      await this.openTerminal();
      this.insertSelectionPrompt();
    }
    catch (error) {
      this.reportError(error);
    }
  }

  private insertSelectionPrompt(): void {
    const context = this.context;
    if (!context?.selection?.text) {
      this.terminal.showError("Select text in the PDF first");
      return;
    }
    this.terminal.insert(buildSelectionPrompt(context), false);
  }

  private openSidebar(): void {
    const win = Zotero.getMainWindow();
    try {
      if (win.ZoteroContextPane?.collapsed) win.ZoteroContextPane.togglePane();
    }
    catch { /* context pane API changed */ }
    const paneID = this.registeredPaneID || PANE_ID;
    const candidates = win.document.querySelectorAll(
      "item-pane-custom-section, item-pane-section, collapsible-section",
    );
    const section = Array.from(candidates).find(
      (candidate: any) => candidate.dataset?.pane === paneID,
    ) as any;
    if (section) {
      section.open = true;
      section.scrollIntoView({ block: "nearest" });
    }
  }

  private selectedTabID(): string | null {
    try {
      return String(Zotero.getMainWindow()?.Zotero_Tabs?.selectedID ?? "") || null;
    }
    catch { return null; }
  }

  private selectedTabType(): string {
    try {
      return String(Zotero.getMainWindow()?.Zotero_Tabs?.selectedType ?? "");
    }
    catch { return ""; }
  }

  private isReaderTabType(tabType: string): boolean {
    if (tabType === "reader") return true;
    try {
      return Zotero.getMainWindow()?.Zotero_Tabs?.parseTabType?.(tabType)?.tabContentType
        === "reader";
    }
    catch { return false; }
  }

  private sidebarTabID(body: HTMLElement): string | null {
    return body.closest("item-details")?.getAttribute("data-tab-id") || null;
  }

  private activeSidebarBody(tabID = this.selectedTabID()): HTMLElement | null {
    const connected = [...this.views].filter((body) => body.isConnected);
    const matching = tabID
      ? connected.filter(
        (body) => this.sidebarTabID(body) === tabID,
      )
      : connected;
    const open = matching.find(
      (body) => body.closest("collapsible-section")?.hasAttribute("open"),
    );
    return open || matching[0] || null;
  }

  private async chooseQLabRoot(preferredWindow?: Window): Promise<string | null> {
    const { FilePicker } = ChromeUtils.importESModule(
      "chrome://zotero/content/modules/filePicker.mjs",
    );
    const picker = new FilePicker();
    const owner = preferredWindow || Zotero.getMainWindow();
    picker.init(owner, "Choose the QLab repository", picker.modeGetFolder);
    const result = await picker.show();
    if (result !== picker.returnOK || !picker.file?.path) return null;
    const host = createGeckoQLabPathHost();
    const root = await normalizeQLabRoot(String(picker.file.path), host);
    if (!await isQLabRepositoryShape(root, host)) {
      throw new Error("The selected folder is not a QLab repository: AGENTS.md, qlab, literature/, drafts/, and knowledge/ are required");
    }
    saveQLabRoot(root);
    this.settings = { ...this.settings, qlabRoot: root };
    this.updateInteractionContext();
    this.renderChatViews();
    return root;
  }

  private async insertQLabCommand(
    view: Pick<SidebarView, "focusComposer">,
    commandID: QLabCommandID,
  ): Promise<void> {
    let root = this.settings?.qlabRoot || "";
    if (!root) root = await this.chooseQLabRoot() || "";
    if (!root) return;
    commandDefinition(commandID);
    const itemKey = this.context?.parent?.key || this.context?.attachment.key || null;
    view.focusComposer(buildQLabCommandPrompt(commandID, {
      qlabRoot: root,
      zoteroItemKey: itemKey,
    }));
  }

  private async captureChatDraft(): Promise<void> {
    let root = this.settings?.qlabRoot || "";
    if (!root) root = await this.chooseQLabRoot() || "";
    if (!root) return;
    const entries = this.codex.getChatEntries();
    if (!entries.some((entry) => entry.kind === "assistant")) {
      throw new Error("Complete at least one paper conversation before organizing it into a Draft");
    }
    const itemKey = this.context?.parent?.key || this.context?.attachment.key || null;
    await this.openWorkbenchTab();
    await this.sendChat(buildCaptureChatDraftPrompt({
      qlabRoot: root,
      zoteroItemKey: itemKey,
    }));
  }

  private reportError(error: unknown): void {
    const value = error instanceof Error ? error : new Error(String(error));
    logError(value);
    if (this.paneMode === "terminal") this.terminal?.showError(value);
    else {
      this.chatError = value.message;
      if (this.chatPhase === "connecting") this.chatPhase = "error";
      this.renderChatViews();
    }
  }

  private installQLabMenu(win: Window): void {
    const doc = win.document as any;
    if (doc.getElementById("qlab-zotero-choose-root")) return;
    const popup = doc.getElementById("menu_ToolsPopup") || doc.getElementById("menuToolsPopup");
    if (!popup) return;
    const separator = doc.createXULElement("menuseparator");
    separator.id = "qlab-zotero-separator";
    const workbench = doc.createXULElement("menuitem");
    workbench.id = "qlab-zotero-open-workbench";
    workbench.setAttribute("label", "Open QLab Workbench");
    workbench.addEventListener("command", () => {
      void this.openWorkbenchTab(win).catch((error) => this.reportError(error));
    });
    const choose = doc.createXULElement("menuitem");
    choose.id = "qlab-zotero-choose-root";
    choose.setAttribute("label", "Choose QLab Repository…");
    choose.addEventListener("command", () => {
      void this.chooseQLabRoot(win).catch((error) => this.reportError(error));
    });
    const importItem = doc.createXULElement("menuitem");
    importItem.id = "qlab-zotero-import-literature";
    importItem.setAttribute("label", "Sync Zotero ↔ QLab Literature");
    importItem.addEventListener("command", () => {
      void this.importQLabLiterature(win).catch((error) => this.reportError(error));
    });
    popup.append(separator, workbench, choose, importItem);
  }

  private removeQLabMenu(win: Window): void {
    for (const id of [
      "qlab-zotero-separator",
      "qlab-zotero-open-workbench",
      "qlab-zotero-choose-root",
      "qlab-zotero-import-literature",
    ]) {
      win.document.getElementById(id)?.remove();
    }
  }

  private async importQLabLiterature(win: Window): Promise<void> {
    let root = this.settings?.qlabRoot || "";
    if (!root) root = await this.chooseQLabRoot(win) || "";
    if (!root) return;
    const imported = await this.zoteroSync.sync(root);
    const result = await this.literature.sync(root);
    Services.prompt.alert(
      win,
      "QLab Literature",
      `${imported}\n\nQLab → Zotero: scanned ${result.scanned}; created ${result.created}; refreshed ${result.updated}.`,
    );
  }

  private injectWindowAssets(win: Window): void {
    const doc = win.document;
    if (!doc.getElementById("zotkit-styles")) {
      const link = doc.createElement("link");
      link.id = "zotkit-styles";
      link.rel = "stylesheet";
      link.href = "chrome://zotkit/content/zoterochat.css";
      doc.documentElement.appendChild(link);
    }
    try { win.MozXULElement?.insertFTLIfNeeded("zoterochat.ftl"); }
    catch { /* header falls back to l10n id */ }
  }

  private removeWindowAssets(win: Window): void {
    this.removeShortcutHandler(win);
    win.document.getElementById("zotkit-styles")?.remove();
  }

  private removeShortcutHandler(win: Window): void {
    const handler = (win as any).__zoteroChatKeyHandler;
    if (handler) win.removeEventListener("keydown", handler, true);
    delete (win as any).__zoteroChatKeyHandler;
    this.shortcutWindows.delete(win);
  }

  private readerPopupButton(doc: Document, label: string, callback: () => void): HTMLButtonElement {
    const button = doc.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.style.cssText = "min-height:28px;padding:4px 10px;border:1px solid rgba(0,122,255,.3);border-radius:8px;background:rgba(0,122,255,.12);color:inherit;font:600 11px -apple-system;cursor:pointer";
    button.addEventListener("click", callback);
    return button;
  }
}

export function formatPendingApprovalDescription(
  pending: Pick<CodexPendingApproval, "description" | "cwd" | "requestedPermissions">,
): string | undefined {
  const details = [pending.description || pending.cwd || ""];
  if (pending.requestedPermissions) {
    let rendered = "";
    try {
      rendered = JSON.stringify(pending.requestedPermissions);
    }
    catch {
      rendered = "(unable to display malformed permission request)";
    }
    const maximum = 6_000;
    details.push(`Requested permissions: ${rendered.length > maximum ? `${rendered.slice(0, maximum)}…` : rendered}`);
  }
  const value = details.filter(Boolean).join("\n");
  return value || undefined;
}

function normalizePlan(value: ReturnType<CodexService["getActivePlan"]>): ResearchPlan | null {
  if (!value) return null;
  return {
    id: value.turnId,
    title: "Research plan",
    explanation: value.explanation || undefined,
    steps: value.steps.map((step, index) => {
      const rawStatus = String(step.status || "pending").toLowerCase();
      const status = rawStatus === "completed" || rawStatus === "complete"
        ? "complete" as const
        : rawStatus === "in_progress" || rawStatus === "inprogress" || rawStatus === "running"
          ? "running" as const
          : rawStatus === "failed" ? "failed" as const : "pending" as const;
      return {
        id: String(step.id || `${value.turnId}:${index}`),
        title: String(step.step || step.title || `Step ${index + 1}`),
        status,
      };
    }),
  };
}

function contextCreators(context: ReaderContext): string {
  return (context.parent?.creators?.length ? context.parent.creators : context.attachment.creators)
    .map((creator) => creator.name || [creator.firstName, creator.lastName].filter(Boolean).join(" "))
    .filter(Boolean)
    .join(", ");
}

function isEditableEventTarget(target: EventTarget | null): boolean {
  const element = target && (target as Node).nodeType === 1 ? target as Element : null;
  if (!element) return false;
  const localName = element.localName?.toLowerCase();
  if (["input", "textarea", "select"].includes(localName)) return true;
  return Boolean(element.closest?.('[contenteditable="true"], [contenteditable="plaintext-only"]'));
}

/**
 * Clamps a raw `floatOpacity` pref value to the slider's [60, 100] range.
 * Only a genuine parse failure (NaN) falls back to 100 -- unlike the old
 * `Number(pref) || 100`, a valid-but-falsy 0 is not silently promoted to
 * 100; it clamps to the 60 floor like any other too-low value.
 */
export function clampFloatOpacity(raw: string): number {
  const parsed = Number(raw);
  if (Number.isNaN(parsed)) return 100;
  return Math.min(100, Math.max(60, parsed));
}

/** Clamps a panel size before it is persisted, so outliers never round-trip. */
export function clampFloatSize(width: number, height: number): { width: number; height: number } {
  return {
    width: Math.min(760, Math.max(380, width)),
    height: Math.min(2000, Math.max(220, height)),
  };
}

export function pdfDirectory(pdfPath: string | null | undefined): string | null {
  const path = pdfPath?.trim();
  if (!path?.startsWith("/")) return null;
  const slash = path.lastIndexOf("/");
  if (slash < 0) return null;
  return slash === 0 ? "/" : path.slice(0, slash);
}

export async function resolveReaderWorkingDirectory(context: ReaderContext): Promise<string> {
  const directory = pdfDirectory(context.pdfPath);
  if (directory) {
    try {
      const stat = await IOUtils.stat(directory);
      if (stat?.type === "directory") return directory;
    }
    catch { /* linked PDF may be temporarily unavailable */ }
  }
  if (!context.workspace?.root) throw new Error("Reader context workspace is unavailable");
  return context.workspace.root;
}

export function buildSelectionPrompt(context: ReaderContext): string {
  const parent = context.parent;
  const creators = parent?.creators?.length ? parent.creators : context.attachment.creators;
  const authors = creators
    .map((creator) => creator.name || [creator.firstName, creator.lastName].filter(Boolean).join(" "))
    .filter(Boolean)
    .join(", ");
  const page = context.selection?.pageNumber
    || context.page.pageNumber;
  const directory = pdfDirectory(context.pdfPath);
  const metadata = [
    `Paper: ${safeTerminalText(paperTitle(context))}`,
    authors ? `Authors: ${safeTerminalText(authors)}` : "",
    parent?.year ? `Year: ${safeTerminalText(parent.year)}` : "",
    parent?.doi ? `DOI: ${safeTerminalText(parent.doi)}` : "",
    context.pdfPath ? `PDF: ${safeTerminalText(context.pdfPath)}` : "",
    directory ? `Directory: ${safeTerminalText(directory)}` : "",
    `PDF page: ${page}`,
  ].filter(Boolean).join("; ");
  const rawSelection = safeTerminalText(context.selection?.text || "");
  const selection = rawSelection.length <= MAX_SELECTION_PROMPT_CHARACTERS
    ? rawSelection
    : `${rawSelection.slice(0, MAX_SELECTION_PROMPT_CHARACTERS)}… [selection truncated; the full text remains available through zotero_reader]`;
  // There is deliberately no CR/LF in this value: it is visible in the TUI
  // and cannot submit itself. The user types the question and presses Enter.
  return `[Zotero Reader context | ${metadata}] Selection: “${selection}” Question: `;
}

function paperTitle(context: ReaderContext): string {
  return context.parent?.title
    || context.attachment.title
    || context.attachment.filename
    || "Current PDF";
}

function safeTerminalText(value: string): string {
  return value
    .replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
