import { renderMarkdown, type PdfPageReference } from "./markdown";
import { renderModelOptions } from "./model-menu";
import { copyToClipboard, prefInt, setPrefInt } from "./platform";
import { ResearchLoopSiteView } from "./research-loop-site";
import { QmdWorkspaceView } from "./qmd-workspace";
import {
  activityLabel,
  contentEntries,
  formatElapsed,
  groupEntries,
  processEntries,
  type Exchange,
} from "./exchanges";
import type { NotingPhase, NotingView } from "./noting";
import type { QLabRepositoryState } from "./qlab-workspace";

export type SidebarPhase = "connecting" | "signed-out" | "ready" | "unavailable" | "error";

export interface PaperContextView {
  key: string;
  title: string;
  authors?: string;
  pageLabel?: string;
  pageIndex?: number;
  pagesCount?: number;
  selectionText?: string;
  pdfPath?: string;
}

export interface ChatEntry {
  id: string;
  kind: "user" | "assistant" | "reasoning" | "tool" | "command" | "status" | "error";
  text: string;
  title?: string;
  state?: "running" | "complete" | "failed";
}

export interface ModelOption {
  id: string;
  label: string;
  supportedReasoningEfforts?: ReasoningEffortOption[];
  defaultReasoningEffort?: string;
  isDefault?: boolean;
}

export interface ReasoningEffortOption {
  reasoningEffort: string;
  description?: string;
}

export interface ThreadOption {
  id: string;
  title: string;
  paperTitle?: string;
  updatedAt: string;
  active: boolean;
  source?: "codex";
  readOnly?: boolean;
  status?: "idle" | "running" | "attention" | "switching";
}

export interface HistoryConversationOption {
  id: string;
  title: string;
  preview?: string;
  updatedAt: string;
  source: "codex";
  sourceLabel: string;
  cwd?: string;
  pinned?: boolean;
  active?: boolean;
  readOnly?: boolean;
}

export type ResearchMode = "ask" | "agent";
export type ResearchScope = "paper" | "library";

export type ResearchContextKind =
  | "paper"
  | "page"
  | "selection"
  | "annotation"
  | "library"
  | "collection"
  | "external-paper"
  | "screenshot"
  | "draft";

export interface ResearchContextChip {
  id: string;
  kind: ResearchContextKind;
  label: string;
  detail?: string;
  removable?: boolean;
}

export interface ResearchContextSuggestion extends ResearchContextChip {
  disabled?: boolean;
}

export interface ResearchPlanStep {
  id: string;
  title: string;
  status: "pending" | "running" | "complete" | "failed";
}

export interface ResearchPlan {
  id: string;
  title?: string;
  explanation?: string;
  steps: ResearchPlanStep[];
}

export interface DiffReview {
  id: string;
  title: string;
  summary?: string;
  diff: string;
  state?: "pending" | "resolving" | "applied" | "accepted" | "rejected" | "failed";
}

export interface PendingApproval {
  id: string;
  title: string;
  description?: string;
  command?: string;
  kind?: "tool" | "command" | "permission";
  risk?: "low" | "medium" | "high";
}

export interface CheckpointOption {
  id: string;
  label: string;
  createdAt?: string;
}

export interface ResearchObjectView {
  kind: "pdf" | "note" | "collection" | "draft";
  label: string;
}

export interface ResearchActionView {
  id: string;
  label: string;
  description: string;
  icon: string;
}

export interface SidebarState {
  phase: SidebarPhase;
  accountLabel?: string;
  error?: string;
  context?: PaperContextView | null;
  entries: ChatEntry[];
  models: ModelOption[];
  threads: ThreadOption[];
  historyConversations: HistoryConversationOption[];
  historyLoading: boolean;
  historyHasMore: boolean;
  historyError?: string;
  selectedModel: string;
  effort: string;
  running: boolean;
  creatingThread?: boolean;
  threadTitle?: string;
  mode: ResearchMode;
  scope: ResearchScope;
  contextChips: ResearchContextChip[];
  contextSuggestions: ResearchContextSuggestion[];
  plan: ResearchPlan | null;
  reviews: DiffReview[];
  pendingApproval: PendingApproval | null;
  checkpoints: CheckpointOption[];
  turnStartedAt: number | null;
  turnDurations: Record<string, number>;
  paperTrailConsent: { question: string; pageNumber?: number } | null;
  noting: NotingView | null;
  /** Feature flags for the active backend; an absent flag defaults to `true`. */
  capabilities?: { supportsAgentMode: boolean; supportsLogin: boolean };
  /** Canonical path of the QLab repository selected by the user. */
  qlabRoot?: string;
  /** The object that contextual Actions will operate on. */
  researchObject?: ResearchObjectView | null;
  /** Actions already filtered for `researchObject` by the host registry. */
  researchActions?: ResearchActionView[];
}

export interface SidebarCallbacks {
  onSend(text: string): void;
  onStop(): void;
  onNewThread(): void;
  onSelectThread(threadId: string): void;
  /** Closes a visible tab without deleting the underlying conversation. */
  onCloseThread?(threadId: string): void;
  /** @deprecated Compatibility callback for older sidebar hosts. */
  onDeleteThread?(threadId: string): void;
  onHistorySearch?(query: string): void;
  onHistoryLoadMore?(): void;
  onSelectHistoryConversation?(conversation: HistoryConversationOption): void;
  onToggleHistoryPin?(threadId: string, pinned: boolean): void;
  onLogin(): void;
  onLogout(): void;
  onOpenTerminal(): void;
  onOpenWorkbench(): void;
  onOpenStandalone?(): void;
  onRefreshContext(): void;
  onInsertSelection(): void;
  onModelChange(model: string): void;
  onEffortChange(effort: string): void;
  onScopeChange?(scope: ResearchScope): void;
  onAddContext?(context: ResearchContextSuggestion): void;
  onRemoveContext?(contextId: string): void;
  onReviewDecision?(reviewId: string, decision: "accept" | "reject"): void;
  onApprovalDecision?(approvalId: string, decision: "approve-once" | "reject"): void;
  onRestoreCheckpoint?(checkpointId: string): void;
  onPaperTrailConsent?(decision: "accept" | "decline"): void;
  onNotingStart?(): void;
  onNotingDecision?(decision: "continue" | "cancel"): void;
  onNotingApply?(mode: { kind: "new" } | { kind: "replace"; key: string }): void;
  onNotingCancel?(): void;
  onChooseQLabRoot?(): void | Promise<void>;
  onResearchAction?(actionId: string): void;
  onChoosePaper?(): void;
  onOpenPaper?(): void;
  canOpenPdfPage?(reference: PdfPageReference): boolean;
  onOpenPdfPage?(reference: PdfPageReference): void;
  onCheckMainSite?(): Promise<boolean>;
  onCheckMainSiteRepository?(): Promise<QLabRepositoryState>;
  onDeployMainSite?(onProgress?: (message: string) => void): Promise<void>;
  onOpenDocument?(relativePath: string): void;
}

export interface SidebarViewOptions {
  surface?: "sidebar" | "workbench";
}

export type SidebarIcon = "history" | "new" | "terminal" | "site" | "popout" | "more" | "refresh" | "send" | "stop" | "context" | "close" | "copy" | "note";

const LONG_USER_MESSAGE_CHARACTERS = 420;
const LONG_USER_MESSAGE_LINES = 8;

/** Renders long user prompts compactly without discarding any of their text. */
export function appendUserMessage(
  doc: Document,
  article: HTMLElement,
  entry: Pick<ChatEntry, "id" | "text">,
  expandedMessages: Set<string>,
): void {
  const bubble = doc.createElement("div");
  bubble.className = "zc-user-bubble";
  bubble.textContent = entry.text;
  const isLong = entry.text.length > LONG_USER_MESSAGE_CHARACTERS
    || entry.text.split(/\r?\n/u).length > LONG_USER_MESSAGE_LINES;
  if (!isLong) {
    article.appendChild(bubble);
    return;
  }

  const toggle = doc.createElement("button");
  toggle.type = "button";
  toggle.className = "zc-user-message-toggle";
  const syncExpandedState = () => {
    const expanded = expandedMessages.has(entry.id);
    bubble.classList.toggle("is-collapsed", !expanded);
    toggle.textContent = expanded ? "Collapse" : "Show Full Message";
    toggle.title = expanded ? "Collapse this message" : "Show the complete message";
    toggle.setAttribute("aria-expanded", String(expanded));
  };
  toggle.addEventListener("click", () => {
    if (expandedMessages.has(entry.id)) expandedMessages.delete(entry.id);
    else expandedMessages.add(entry.id);
    syncExpandedState();
  });
  syncExpandedState();
  article.append(bubble, toggle);
}

/** The chat column never shrinks past a quarter or grows past two thirds. */
function clampSplitRatio(percent: number): number {
  if (!Number.isFinite(percent)) return 40;
  return Math.round(Math.min(68, Math.max(25, percent)));
}

/**
 * Rebuilding the Action chips between mousedown and mouseup (frequent while
 * a turn streams re-renders) destroys the button before its click event
 * fires. Equal-by-value chip state therefore keeps the existing buttons.
 * Every field that affects the rendered strip participates: per-action
 * id/label/description/icon plus the object kind/label, from which the
 * strip's hidden state is derived. ResearchActionView carries no disabled
 * flag today; add any future field to this comparison.
 */
function sameResearchActionState(
  previous: { object: ResearchObjectView | null; actions: ResearchActionView[] } | null,
  object: ResearchObjectView | null,
  actions: ResearchActionView[],
): boolean {
  if (!previous) return false;
  if ((previous.object === null) !== (object === null)) return false;
  if (previous.object && object
    && (previous.object.kind !== object.kind || previous.object.label !== object.label)) {
    return false;
  }
  if (previous.actions.length !== actions.length) return false;
  return previous.actions.every((prev, index) => {
    const next = actions[index]!;
    return prev.id === next.id
      && prev.label === next.label
      && prev.description === next.description
      && prev.icon === next.icon;
  });
}

export class SidebarView {
  private readonly doc: Document;
  private readonly root: HTMLElement;
  private readonly surface: "sidebar" | "workbench";
  private transcript!: HTMLElement;
  private textarea!: HTMLTextAreaElement;
  private sendButton!: HTMLButtonElement;
  private stopButton!: HTMLButtonElement;
  private modelSelect!: HTMLSelectElement;
  private effortSelect!: HTMLSelectElement;
  private composerControls!: HTMLElement;
  private qlabRootLabel!: HTMLElement;
  private actionStrip!: HTMLElement;
  private renderedResearchActions: {
    object: ResearchObjectView | null;
    actions: ResearchActionView[];
  } | null = null;
  private contextTitle!: HTMLElement;
  private contextMeta!: HTMLElement;
  private choosePaperButton!: HTMLButtonElement;
  private paperScopeButton: HTMLButtonElement | null = null;
  private libraryScopeButton: HTMLButtonElement | null = null;
  private openPaperButton!: HTMLButtonElement;
  private terminalButton!: HTMLButtonElement;
  private terminalDrawer!: HTMLElement;
  private contextChips!: HTMLElement;
  private contextMenu!: HTMLElement;
  private contextMenuList!: HTMLElement;
  private contextMenuEmpty!: HTMLElement;
  private threadTabs!: HTMLElement;
  private statusArea!: HTMLElement;
  private loginLayer!: HTMLElement;
  private threadTitle!: HTMLElement;
  private accountButton!: HTMLButtonElement;
  private historyButton!: HTMLButtonElement;
  private historyRail: HTMLElement | null = null;
  private historyList: HTMLElement | null = null;
  private historySearch: HTMLInputElement | null = null;
  private historyLoadMore: HTMLButtonElement | null = null;
  private topActions!: HTMLElement;
  private splitHandle!: HTMLButtonElement;
  private splitRatio = clampSplitRatio(prefInt("splitRatio", 40));
  private newThreadButton!: HTMLButtonElement;
  private mainSiteButton: HTMLButtonElement | null = null;
  private mainSiteView: ResearchLoopSiteView | null = null;
  private workspaceView: QmdWorkspaceView | null = null;
  private state: SidebarState;
  private readonly entryNodes = new Map<string, { fingerprint: string; node: HTMLElement }>();
  private emptyState: HTMLElement | null = null;
  private contextMenuOpen = false;
  private contextMenuQuery = "";
  private contextMenuSelection = 0;
  private contextQueryStart: number | null = null;
  private readonly expandedTurns = new Set<string>();
  private readonly expandedUserMessages = new Set<string>();
  private activityTimer: number | null = null;
  private activityNode: HTMLElement | null = null;
  private activityLabelEl: HTMLElement | null = null;
  private activityElapsedEl: HTMLElement | null = null;
  private pinnedToBottom = true;
  private lastActiveThreadId: string | undefined = undefined;
  private contextChipsExplicit = false;
  private historyOpen = true;
  private historyQuery = "";
  private historySearchTimer: number | null = null;
  private detachedLayer: HTMLElement | null = null;

  constructor(
    body: HTMLElement,
    private readonly callbacks: SidebarCallbacks,
    options: SidebarViewOptions = {},
  ) {
    this.surface = options.surface || "sidebar";
    this.historyOpen = this.surface === "workbench" && prefInt("historySidebarOpen", 1) !== 0;
    this.doc = body.ownerDocument;
    this.root = this.doc.createElement("section");
    this.root.className = this.surface === "workbench"
      ? "zc-sidebar zc-workbench-chat"
      : "zc-sidebar";
    this.root.setAttribute("role", this.surface === "workbench" ? "main" : "region");
    this.root.setAttribute("aria-label", this.surface === "workbench" ? "QLab Workbench" : "QLab Assistant");
    body.replaceChildren(this.root);
    this.applySplitRatio(this.splitRatio);
    this.state = {
      phase: "connecting",
      entries: [],
      models: [],
      threads: [],
      historyConversations: [],
      historyLoading: false,
      historyHasMore: false,
      selectedModel: "",
      effort: "medium",
      mode: "agent",
      scope: "paper",
      running: false,
      context: null,
      contextChips: [],
      contextSuggestions: [],
      plan: null,
      reviews: [],
      pendingApproval: null,
      checkpoints: [],
      turnStartedAt: null,
      turnDurations: {},
      paperTrailConsent: null,
      noting: null,
      researchObject: null,
      researchActions: [],
    };
    this.build();
    this.render();
  }

  destroy(): void {
    if (this.activityTimer !== null) {
      this.doc.defaultView?.clearInterval(this.activityTimer);
      this.activityTimer = null;
    }
    if (this.historySearchTimer !== null) {
      this.doc.defaultView?.clearTimeout(this.historySearchTimer);
      this.historySearchTimer = null;
    }
    this.mainSiteView?.destroy();
    this.workspaceView?.destroy();
    this.root.remove();
  }

  show(): void {
    this.root.hidden = false;
  }

  setState(next: Partial<SidebarState>): void {
    if (Object.prototype.hasOwnProperty.call(next, "contextChips")) {
      this.contextChipsExplicit = true;
    }
    this.state = { ...this.state, ...next };
    this.render();
  }

  /** Replaces an embedded Reader surface while the shared chat lives in its standalone window. */
  setDetached(
    detached: boolean,
    callbacks: { onFocus(): void; onReturn(): void },
  ): void {
    if (!detached) {
      this.detachedLayer?.remove();
      this.detachedLayer = null;
      return;
    }
    if (!this.detachedLayer) {
      const layer = this.doc.createElement("div");
      layer.className = "zc-detached-layer";
      const title = this.doc.createElement("strong");
      title.textContent = "Chat is open in a separate window";
      const detail = this.doc.createElement("p");
      detail.textContent = "The conversation and its paper context continue running there.";
      const focus = this.doc.createElement("button");
      focus.type = "button";
      focus.className = "is-primary";
      focus.textContent = "Focus Window";
      focus.addEventListener("click", () => callbacks.onFocus());
      const restore = this.doc.createElement("button");
      restore.type = "button";
      restore.textContent = "Close Window & Return Here";
      restore.addEventListener("click", () => callbacks.onReturn());
      layer.append(title, detail, focus, restore);
      this.root.appendChild(layer);
      this.detachedLayer = layer;
    }
  }

  private setHistoryOpen(open: boolean): void {
    if (!this.historyRail) return;
    this.historyOpen = open;
    this.historyRail.hidden = !open;
    this.root.classList.toggle("is-history-open", open);
    this.historyButton.setAttribute("aria-pressed", String(open));
    this.historyButton.title = open ? "Hide Conversation History" : "Show Conversation History";
    setPrefInt("historySidebarOpen", open ? 1 : 0);
  }

  private buildHistoryRail(): void {
    const rail = this.doc.createElement("aside");
    rail.className = "zc-history-rail";
    rail.setAttribute("aria-label", "All Codex conversations");
    rail.hidden = !this.historyOpen;

    const header = this.doc.createElement("header");
    const title = this.doc.createElement("strong");
    title.textContent = "Conversations";
    const close = this.iconButton("close", "Hide Conversation History", () => this.setHistoryOpen(false));
    header.append(title, close);

    const search = this.doc.createElement("input");
    search.type = "search";
    search.className = "zc-history-search";
    search.placeholder = "Search conversations";
    search.setAttribute("aria-label", "Search conversations");
    search.addEventListener("input", () => {
      this.historyQuery = search.value;
      this.renderHistoryRail();
      if (this.historySearchTimer !== null) {
        this.doc.defaultView?.clearTimeout(this.historySearchTimer);
      }
      this.historySearchTimer = this.doc.defaultView?.setTimeout(() => {
        this.historySearchTimer = null;
        this.callbacks.onHistorySearch?.(this.historyQuery);
      }, 250) ?? null;
    });
    this.historySearch = search;

    const list = this.doc.createElement("div");
    list.className = "zc-history-list";
    this.historyList = list;

    const loadMore = this.doc.createElement("button");
    loadMore.type = "button";
    loadMore.className = "zc-history-load-more";
    loadMore.textContent = "Load More";
    loadMore.addEventListener("click", () => this.callbacks.onHistoryLoadMore?.());
    this.historyLoadMore = loadMore;

    const privacy = this.doc.createElement("small");
    privacy.className = "zc-history-privacy";
    privacy.textContent = "Codex history stays local.";
    rail.append(header, search, list, loadMore, privacy);
    this.historyRail = rail;
  }

  focusComposer(text?: string): void {
    if (this.mainSiteView?.isVisible() || this.workspaceView?.isVisible()) return;
    if (text !== undefined) {
      const prefix = this.textarea.value.trim() ? `${this.textarea.value.trim()}\n\n` : "";
      this.textarea.value = prefix + text;
      this.autoSizeComposer();
    }
    this.textarea.focus();
  }

  terminalHost(): HTMLElement {
    return this.terminalDrawer;
  }

  isTerminalOpen(): boolean {
    return this.terminalDrawer.classList.contains("is-open");
  }

  setTerminalOpen(open: boolean): void {
    this.terminalDrawer.classList.toggle("is-open", open);
    this.terminalDrawer.setAttribute("aria-hidden", String(!open));
    this.root.classList.toggle("is-terminal-open", open);
    this.terminalButton.setAttribute("aria-pressed", String(open));
    this.terminalButton.title = open ? "Collapse Terminal" : "Open Terminal";
  }

  revealComposer(): void {
    this.textarea.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  private build(): void {
    const topbar = this.doc.createElement("header");
    topbar.className = "zc-topbar";

    const identity = this.doc.createElement("div");
    identity.className = "zc-identity";
    const icon = this.doc.createElement("img");
    icon.src = "chrome://zotkit/content/icons/icon.svg";
    icon.alt = "";
    const titles = this.doc.createElement("div");
    const product = this.doc.createElement("div");
    product.className = "zc-product-title";
    product.textContent = "Research Loop · Local Codex";
    this.threadTitle = this.doc.createElement("div");
    this.threadTitle.className = "zc-thread-title";
    this.threadTitle.textContent = "Paper Assistant";
    titles.append(product, this.threadTitle);
    identity.append(icon, titles);

    const actions = this.doc.createElement("div");
    actions.className = this.surface === "workbench"
      ? "zc-top-actions zc-workbench-dock"
      : "zc-top-actions";
    if (this.surface === "workbench") actions.setAttribute("aria-label", "Workbench tools");
    const workbenchButton = this.doc.createElement("button");
    workbenchButton.type = "button";
    workbenchButton.className = "zc-workbench-open";
    workbenchButton.title = "Open the QLab Workbench in a Zotero tab";
    workbenchButton.textContent = "Workbench";
    workbenchButton.hidden = this.surface === "workbench";
    workbenchButton.addEventListener("click", () => this.callbacks.onOpenWorkbench());
    if (this.surface === "workbench") {
      this.mainSiteButton = this.iconButton(
        "site",
        "Check Research Loop main site",
        () => void this.activateMainSite(),
      );
      this.mainSiteButton.classList.add("zc-main-site-button", "is-checking");
      this.mainSiteButton.disabled = true;
      this.mainSiteButton.setAttribute("aria-pressed", "false");
    }
    const standaloneButton = this.surface === "workbench" && this.callbacks.onOpenStandalone
      ? this.iconButton("popout", "Open QLab in a separate window", () => this.callbacks.onOpenStandalone?.())
      : null;
    this.topActions = actions;
    const historyButton = this.iconButton("history", "Conversation History", () => {
      if (this.surface === "workbench") this.setHistoryOpen(!this.historyOpen);
      else this.toggleHistoryMenu();
    });
    historyButton.classList.add("zc-history-toggle");
    this.historyButton = historyButton;
    this.historyButton.setAttribute("aria-pressed", String(this.historyOpen));
    this.newThreadButton = this.iconButton("new", "New Conversation", () => this.callbacks.onNewThread());
    this.terminalButton = this.iconButton(
      "terminal",
      "Open Terminal",
      () => this.callbacks.onOpenTerminal(),
    );
    this.terminalButton.classList.add("zc-terminal-button");
    this.terminalButton.setAttribute("aria-pressed", "false");
    this.accountButton = this.iconButton("more", "Account", () => this.toggleAccountMenu());
    actions.append(
      workbenchButton,
      ...(this.mainSiteButton ? [this.mainSiteButton] : []),
      ...(standaloneButton ? [standaloneButton] : []),
      ...(this.surface === "workbench" ? [] : [this.newThreadButton]),
      this.terminalButton,
      this.accountButton,
    );
    topbar.append(historyButton, identity, actions);

    this.threadTabs = this.doc.createElement("nav");
    this.threadTabs.className = "zc-thread-tabs";
    this.threadTabs.setAttribute("aria-label", "Open conversation tabs");

    if (this.surface === "workbench") this.buildHistoryRail();

    const contextCard = this.doc.createElement("section");
    contextCard.className = "zc-context-card";
    const contextIcon = this.doc.createElement("div");
    contextIcon.className = "zc-pdf-icon";
    contextIcon.textContent = "PDF";
    const contextCopy = this.doc.createElement("div");
    contextCopy.className = "zc-context-copy";
    this.contextTitle = this.doc.createElement("div");
    this.contextTitle.className = "zc-context-title";
    this.contextMeta = this.doc.createElement("div");
    this.contextMeta.className = "zc-context-meta";
    contextCopy.append(this.contextTitle, this.contextMeta);
    const refresh = this.iconButton("refresh", "Refresh Reader Context", () => this.callbacks.onRefreshContext());
    this.choosePaperButton = this.doc.createElement("button");
    this.choosePaperButton.type = "button";
    this.choosePaperButton.className = "zc-choose-paper";
    this.choosePaperButton.addEventListener("click", () => this.callbacks.onChoosePaper?.());
    this.openPaperButton = this.doc.createElement("button");
    this.openPaperButton.type = "button";
    this.openPaperButton.className = "zc-open-paper";
    this.openPaperButton.textContent = "Open PDF";
    this.openPaperButton.title = "Open the current paper in a new Zotero PDF tab";
    this.openPaperButton.addEventListener("click", () => this.callbacks.onOpenPaper?.());
    if (this.surface === "workbench") {
      const scope = this.doc.createElement("div");
      scope.className = "zc-scope-switch";
      this.paperScopeButton = this.doc.createElement("button");
      this.paperScopeButton.type = "button";
      this.paperScopeButton.textContent = "Paper Chat";
      this.paperScopeButton.addEventListener("click", () => this.callbacks.onScopeChange?.("paper"));
      this.libraryScopeButton = this.doc.createElement("button");
      this.libraryScopeButton.type = "button";
      this.libraryScopeButton.textContent = "Library Chat";
      this.libraryScopeButton.addEventListener("click", () => this.callbacks.onScopeChange?.("library"));
      scope.append(this.paperScopeButton, this.libraryScopeButton);
      contextCard.append(scope);
    }
    contextCard.append(contextIcon, contextCopy, this.openPaperButton, this.choosePaperButton, refresh);

    this.transcript = this.doc.createElement("main");
    this.transcript.className = "zc-transcript";
    this.transcript.addEventListener("scroll", () => {
      const { scrollTop, clientHeight, scrollHeight } = this.transcript;
      this.pinnedToBottom = scrollTop + clientHeight >= scrollHeight - 4;
    });
    this.transcript.addEventListener("click", (event) => {
      const target = (event.target as HTMLElement | null)?.closest?.(".zc-math-copy");
      if (!target) return;
      // A selection drag that happens to pass over a rendered formula must
      // not be swallowed into an accidental LaTeX copy.
      if (this.doc.defaultView?.getSelection?.()?.isCollapsed === false) return;
      const latex = target.getAttribute("data-latex");
      if (!latex || !copyToClipboard(latex)) return;
      target.classList.add("is-copied");
      this.doc.defaultView?.setTimeout(() => target.classList.remove("is-copied"), 1200);
    });

    const composerWrap = this.doc.createElement("footer");
    composerWrap.className = "zc-composer-wrap";
    const qlabBar = this.doc.createElement("section");
    qlabBar.className = "zc-qlab-bar";
    const qlabIdentity = this.doc.createElement("button");
    qlabIdentity.type = "button";
    qlabIdentity.className = "zc-qlab-root-button";
    qlabIdentity.title = "Choose QLab Repository";
    qlabIdentity.addEventListener("click", () => this.callbacks.onChooseQLabRoot?.());
    const qlabMark = this.doc.createElement("strong");
    qlabMark.textContent = "QLab";
    this.qlabRootLabel = this.doc.createElement("span");
    this.qlabRootLabel.className = "zc-qlab-root-label";
    qlabIdentity.append(qlabMark, this.qlabRootLabel);
    qlabBar.appendChild(qlabIdentity);
    this.actionStrip = this.doc.createElement("div");
    this.actionStrip.className = "zc-action-strip";
    this.actionStrip.setAttribute("aria-label", "Research Actions");
    qlabBar.appendChild(this.actionStrip);
    const composer = this.doc.createElement("div");
    composer.className = "zc-composer";
    this.contextChips = this.doc.createElement("div");
    this.contextChips.className = "zc-composer-chips";
    const addContext = this.iconButton("context", "Add paper context (@)", () => {
      this.openContextMenu("");
      this.textarea.focus();
    });
    addContext.classList.add("zc-add-context-button");
    this.contextChips.appendChild(addContext);

    this.contextMenu = this.doc.createElement("section");
    this.contextMenu.className = "zc-context-menu";
    this.contextMenu.hidden = true;
    const contextMenuHeader = this.doc.createElement("header");
    contextMenuHeader.textContent = "Add Context";
    const contextMenuHint = this.doc.createElement("span");
    contextMenuHint.textContent = "Type @ to filter";
    contextMenuHeader.appendChild(contextMenuHint);
    this.contextMenuList = this.doc.createElement("div");
    this.contextMenuList.className = "zc-context-menu-list";
    this.contextMenuList.setAttribute("role", "listbox");
    this.contextMenuEmpty = this.doc.createElement("div");
    this.contextMenuEmpty.className = "zc-context-menu-empty";
    this.contextMenuEmpty.textContent = "No matching context";
    this.contextMenu.append(contextMenuHeader, this.contextMenuList, this.contextMenuEmpty);

    this.textarea = this.doc.createElement("textarea");
    this.textarea.className = "zc-composer-input";
    this.textarea.rows = 1;
    this.textarea.placeholder = "Ask about this paper…";
    this.textarea.addEventListener("input", () => {
      this.autoSizeComposer();
      this.updateContextMenuFromComposer();
    });
    this.textarea.addEventListener("keydown", (event) => {
      if (this.handleContextMenuKeydown(event)) return;
      if (event.key === "Escape" && this.state.running && !event.isComposing) {
        event.preventDefault();
        this.callbacks.onStop();
        return;
      }
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        this.submit();
      }
    });
    const composerFooter = this.doc.createElement("div");
    composerFooter.className = "zc-composer-footer";
    const controls = this.doc.createElement("div");
    controls.className = "zc-composer-controls";
    this.composerControls = controls;
    this.modelSelect = this.doc.createElement("select");
    this.modelSelect.className = "zc-compact-select";
    this.modelSelect.title = "Model";
    this.modelSelect.addEventListener("change", () => {
      this.renderEfforts(this.modelSelect.value, true);
      this.callbacks.onModelChange(this.modelSelect.value);
    });
    this.effortSelect = this.doc.createElement("select");
    this.effortSelect.className = "zc-compact-select";
    this.effortSelect.title = "Reasoning Effort";
    this.effortSelect.addEventListener("change", () => this.callbacks.onEffortChange(this.effortSelect.value));
    controls.append(this.modelSelect, this.effortSelect);
    this.sendButton = this.doc.createElement("button");
    this.sendButton.type = "button";
    this.sendButton.className = "zc-send-button";
    this.sendButton.addEventListener("click", () => this.submit());
    this.stopButton = this.doc.createElement("button");
    this.stopButton.type = "button";
    this.stopButton.className = "zc-send-button is-running";
    this.setButtonIcon(this.stopButton, "stop");
    this.stopButton.title = "Stop Generating (Esc)";
    this.stopButton.setAttribute("aria-label", this.stopButton.title);
    this.stopButton.addEventListener("click", () => this.callbacks.onStop());
    const composerActions = this.doc.createElement("div");
    composerActions.style.cssText = "display:flex;align-items:center;gap:6px";
    composerActions.append(this.stopButton, this.sendButton);
    composerFooter.append(controls, composerActions);
    composer.append(this.contextChips, this.contextMenu, this.textarea, composerFooter);
    this.statusArea = this.doc.createElement("div");
    this.statusArea.className = "zc-status-area";
    composerWrap.append(qlabBar, composer, this.statusArea);

    this.loginLayer = this.doc.createElement("div");
    this.loginLayer.className = "zc-login-layer";

    this.terminalDrawer = this.doc.createElement("aside");
    this.terminalDrawer.className = "zc-terminal-drawer";
    this.terminalDrawer.setAttribute("aria-label", "QLab Terminal");
    this.terminalDrawer.setAttribute("aria-hidden", "true");

    this.splitHandle = this.doc.createElement("button");
    this.splitHandle.type = "button";
    this.splitHandle.className = "zc-split-handle";
    this.splitHandle.setAttribute("aria-label", "Resize chat and the right pane");
    this.splitHandle.addEventListener("mousedown", (event) => this.beginSplitDrag(event));

    this.root.append(
      ...(this.surface === "workbench" ? [] : [topbar]),
      ...(this.historyRail ? [this.historyRail] : []),
      this.splitHandle,
      this.threadTabs,
      contextCard,
      this.transcript,
      composerWrap,
      ...(this.surface === "workbench" ? [this.topActions] : []),
      this.loginLayer,
      this.terminalDrawer,
    );
    if (this.surface === "workbench") {
      this.root.classList.toggle("is-history-open", this.historyOpen);
      this.mainSiteView = new ResearchLoopSiteView(this.root, {
        onBack: () => this.setMainSiteOpen(false),
        onOpenDocument: this.callbacks.onOpenDocument,
      });
      void this.refreshMainSiteStatus();
    }
  }

  async refreshMainSiteStatus(): Promise<boolean> {
    const button = this.mainSiteButton;
    if (!button) return false;
    button.disabled = true;
    button.className = "zc-icon-button zc-main-site-button is-checking";
    this.presentMainSiteButton(button, "Check Research Loop main site");
    let available = false;
    let repositoryState: QLabRepositoryState = "ready";
    try {
      repositoryState = await this.callbacks.onCheckMainSiteRepository?.() || "ready";
      available = repositoryState === "ready"
        ? await this.callbacks.onCheckMainSite?.() || false
        : false;
    }
    catch {
      available = false;
    }
    if (!button.isConnected) return available;
    button.dataset.repositoryState = repositoryState;
    button.disabled = false;
    if (repositoryState === "missing" || repositoryState === "incompatible") {
      button.className = "zc-icon-button zc-main-site-button is-invalid";
      this.presentMainSiteButton(button, repositoryState === "missing"
        ? "Choose an empty folder or an existing Research Loop repository"
        : "This folder contains unrelated files; choose an empty folder instead");
      return false;
    }
    if (repositoryState === "empty" || repositoryState === "partial") {
      button.className = "zc-icon-button zc-main-site-button is-initialize";
      this.presentMainSiteButton(button, repositoryState === "empty"
        ? "Initialize Research Loop in this empty folder"
        : "Complete the Research Loop structure without overwriting existing Knowledge, Drafts, or Literature");
      return false;
    }
    button.className = available
      ? "zc-icon-button zc-main-site-button is-available"
      : "zc-icon-button zc-main-site-button is-offline";
    this.presentMainSiteButton(button, available
      ? "Open the Research Loop main site in Zotero"
      : "The main site is not running; click to build and start it");
    return available;
  }

  private async activateMainSite(): Promise<void> {
    if (!this.mainSiteButton || !this.mainSiteView) return;
    if (this.mainSiteView.isVisible()) {
      this.setMainSiteOpen(false);
      return;
    }
    const repositoryState = this.mainSiteButton.dataset.repositoryState as QLabRepositoryState | undefined;
    if (repositoryState === "missing" || repositoryState === "incompatible") {
      await this.callbacks.onChooseQLabRoot?.();
      await this.refreshMainSiteStatus();
      return;
    }
    const available = this.mainSiteButton.classList.contains("is-available");
    if (!available) {
      this.mainSiteButton.disabled = true;
      this.mainSiteButton.className = "zc-icon-button zc-main-site-button is-deploying";
      this.presentMainSiteButton(this.mainSiteButton, "Building and starting the Research Loop main site");
      try {
        if (!this.callbacks.onDeployMainSite) throw new Error("Main-site deployment is unavailable");
        await this.callbacks.onDeployMainSite((message) => {
          if (!this.mainSiteButton?.isConnected) return;
          this.presentMainSiteButton(this.mainSiteButton, message);
        });
      }
      catch (error) {
        if (!this.mainSiteButton.isConnected) return;
        this.mainSiteButton.disabled = false;
        this.mainSiteButton.className = "zc-icon-button zc-main-site-button is-error";
        this.presentMainSiteButton(
          this.mainSiteButton,
          `Retry Main Site: ${error instanceof Error ? error.message : String(error)}`,
        );
        return;
      }
      if (!this.mainSiteButton.isConnected) return;
      this.mainSiteButton.disabled = false;
      this.mainSiteButton.className = "zc-icon-button zc-main-site-button is-available";
      this.presentMainSiteButton(this.mainSiteButton, "Open the Research Loop main site in Zotero");
    }
    this.setMainSiteOpen(true);
  }

  isMainSiteOpen(): boolean {
    return Boolean(this.mainSiteView?.isVisible());
  }

  setMainSiteOpen(open: boolean): void {
    if (!this.mainSiteButton || !this.mainSiteView) return;
    if (open) {
      this.setTerminalOpen(false);
      this.setWorkspaceOpen(false);
      this.mainSiteView.show();
    }
    else {
      this.mainSiteView.hide();
    }
    this.root.classList.toggle("is-main-site-open", open);
    this.mainSiteButton.setAttribute("aria-pressed", String(open));
  }

  /** Hosts the document workspace, which shares the right-hand column. */
  attachWorkspace(build: (host: HTMLElement) => QmdWorkspaceView): QmdWorkspaceView | null {
    if (this.surface !== "workbench") return null;
    this.workspaceView ??= build(this.root);
    return this.workspaceView;
  }

  workspace(): QmdWorkspaceView | null {
    return this.workspaceView;
  }

  /**
   * Drags the boundary between the chat and the right-hand pane.
   *
   * The ratio is a custom property rather than a fixed percentage so that the
   * login layer and the terminal drawer, which are positioned against the same
   * boundary, follow it without a second source of truth.
   */
  private beginSplitDrag(event: MouseEvent): void {
    event.preventDefault();
    const view = this.doc.defaultView;
    if (!view) return;
    this.splitHandle.classList.add("is-dragging");
    const onMove = (moved: MouseEvent) => {
      const bounds = this.root.getBoundingClientRect();
      if (bounds.width <= 0) return;
      this.applySplitRatio(((moved.clientX - bounds.left) / bounds.width) * 100);
    };
    const onUp = () => {
      this.splitHandle.classList.remove("is-dragging");
      view.removeEventListener("mousemove", onMove, true);
      view.removeEventListener("mouseup", onUp, true);
      setPrefInt("splitRatio", this.splitRatio);
    };
    view.addEventListener("mousemove", onMove, true);
    view.addEventListener("mouseup", onUp, true);
  }

  private applySplitRatio(percent: number): void {
    this.splitRatio = clampSplitRatio(percent);
    this.root.style.setProperty("--zc-split-ratio", `${this.splitRatio}%`);
  }

  setWorkspaceOpen(open: boolean): void {
    if (!this.workspaceView) return;
    if (open) {
      this.setTerminalOpen(false);
      this.mainSiteView?.hide();
      this.root.classList.remove("is-main-site-open");
      this.mainSiteButton?.setAttribute("aria-pressed", "false");
      this.workspaceView.show();
    }
    else {
      this.workspaceView.hide();
    }
    this.root.classList.toggle("is-workspace-open", open);
  }

  private render(): void {
    this.threadTitle.textContent = this.state.threadTitle || "Paper Assistant";
    this.root.dataset.mode = "agent";
    this.qlabRootLabel.textContent = this.state.qlabRoot
      ? compactPath(this.state.qlabRoot)
      : "Choose repository…";
    this.qlabRootLabel.title = this.state.qlabRoot || "QLab repository is not configured";
    this.newThreadButton.disabled = Boolean(this.state.creatingThread);
    this.newThreadButton.title = this.state.creatingThread ? "Creating a new conversation…" : "New Conversation";
    this.renderHistoryRail();
    this.renderThreadTabs();
    this.renderContext();
    this.renderContextChips();
    this.renderContextMenu();
    this.renderResearchActions();
    this.renderModels();
    this.renderEfforts();
    this.renderTranscript();
    this.renderLoginLayer();
    this.setButtonIcon(this.sendButton, "send");
    this.sendButton.title = this.state.running ? "Send Follow-up" : "Send";
    this.sendButton.setAttribute("aria-label", this.sendButton.title);
    this.stopButton.hidden = !this.state.running;
    this.stopButton.style.display = this.state.running ? "grid" : "none";
    const canSendCodex = this.canSendCodex();
    this.textarea.disabled = false;
    this.sendButton.disabled = !canSendCodex;
    this.modelSelect.disabled = !canSendCodex || this.state.running;
    this.effortSelect.disabled = !canSendCodex || this.state.running;
    this.statusArea.textContent = this.state.error || (this.state.running
      ? "Enter sends a follow-up · Esc stops generation"
      : "Codex can make mistakes; verify the paper text and page numbers.");
    this.statusArea.classList.toggle("is-error", Boolean(this.state.error));
  }

  private canSendCodex(): boolean {
    // A fresh host can represent its initial active thread with an empty tab
    // list. Once it supplies tabs, an explicit active tab is required.
    const hasActiveThread = this.state.threads.length === 0 || this.state.threads.some((thread) => thread.active);
    return this.state.phase === "ready" && hasActiveThread;
  }

  private renderResearchActions(): void {
    if (!this.actionStrip) return;
    const object = this.state.researchObject ?? null;
    const actions = this.state.researchActions || [];
    if (sameResearchActionState(this.renderedResearchActions, object, actions)) return;
    this.renderedResearchActions = {
      object: object ? { ...object } : null,
      actions: actions.map((action) => ({ ...action })),
    };
    this.actionStrip.replaceChildren();
    this.actionStrip.hidden = !object || actions.length === 0;
    if (!object || !actions.length) return;

    const objectLabel = this.doc.createElement("span");
    objectLabel.className = `zc-action-object is-${object.kind}`;
    objectLabel.textContent = object.label;
    objectLabel.title = `${object.kind[0]!.toUpperCase()}${object.kind.slice(1)} · ${object.label}`;
    this.actionStrip.appendChild(objectLabel);
    for (const action of actions) {
      const button = this.doc.createElement("button");
      button.type = "button";
      button.className = "zc-research-action";
      button.dataset.actionId = action.id;
      button.title = action.description;
      button.setAttribute("aria-label", action.label);
      const icon = this.doc.createElement("span");
      icon.className = "zc-research-action-icon";
      icon.textContent = action.icon;
      icon.setAttribute("aria-hidden", "true");
      const label = this.doc.createElement("span");
      label.textContent = action.label;
      button.append(icon, label);
      button.addEventListener("click", () => this.callbacks.onResearchAction?.(action.id));
      this.actionStrip.appendChild(button);
    }
  }

  private renderHistoryRail(): void {
    if (!this.historyRail || !this.historyList || !this.historyLoadMore) return;
    this.historyRail.hidden = !this.historyOpen;
    if (this.historySearch && this.historySearch.value !== this.historyQuery) {
      this.historySearch.value = this.historyQuery;
    }
    this.historyList.replaceChildren();
    const query = this.historyQuery.trim().toLocaleLowerCase();
    const conversations = this.state.historyConversations.filter((conversation) => {
      if (!query) return true;
      return [conversation.title, conversation.preview, conversation.cwd, conversation.sourceLabel]
        .some((value) => value?.toLocaleLowerCase().includes(query));
    });

    const addGroup = (label: string, items: HistoryConversationOption[]): void => {
      if (!items.length) return;
      const heading = this.doc.createElement("div");
      heading.className = "zc-history-group-heading";
      heading.textContent = label;
      this.historyList!.appendChild(heading);
      for (const conversation of items) {
        const row = this.doc.createElement("div");
        row.className = "zc-history-row";
        row.classList.toggle("is-active", Boolean(conversation.active));
        const open = this.doc.createElement("button");
        open.type = "button";
        open.className = "zc-history-open";
        open.title = [conversation.title, conversation.cwd || conversation.preview || ""]
          .filter(Boolean).join("\n");
        const title = this.doc.createElement("span");
        title.className = "zc-history-row-title";
        title.textContent = conversation.title;
        const meta = this.doc.createElement("span");
        meta.className = "zc-history-row-meta";
        const date = new Date(conversation.updatedAt);
        meta.textContent = [
          conversation.sourceLabel,
          Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString(),
          conversation.readOnly ? "Read-only" : "",
        ].filter(Boolean).join(" · ");
        open.append(title, meta);
        open.addEventListener("click", () => this.callbacks.onSelectHistoryConversation?.(conversation));
        row.appendChild(open);
        const pin = this.doc.createElement("button");
        pin.type = "button";
        pin.className = "zc-history-pin";
        pin.textContent = conversation.pinned ? "★" : "☆";
        pin.title = conversation.pinned ? "Unpin Conversation" : "Pin Conversation";
        pin.setAttribute("aria-label", pin.title);
        pin.addEventListener("click", () => {
          this.callbacks.onToggleHistoryPin?.(conversation.id, !conversation.pinned);
        });
        row.appendChild(pin);
        this.historyList!.appendChild(row);
      }
    };

    addGroup("Pinned", conversations.filter((conversation) => conversation.pinned));
    addGroup("Codex", conversations.filter((conversation) => !conversation.pinned));

    if (!conversations.length && !this.state.historyLoading) {
      const empty = this.doc.createElement("div");
      empty.className = "zc-history-empty";
      empty.textContent = query ? "No matching conversations" : "No conversation history yet";
      this.historyList.appendChild(empty);
    }
    if (this.state.historyError) {
      const error = this.doc.createElement("div");
      error.className = "zc-history-error";
      error.textContent = this.state.historyError;
      this.historyList.appendChild(error);
    }
    if (this.state.historyLoading) {
      const loading = this.doc.createElement("div");
      loading.className = "zc-history-loading";
      loading.textContent = "Loading conversations…";
      this.historyList.appendChild(loading);
    }
    this.historyLoadMore.hidden = !this.state.historyHasMore;
    this.historyLoadMore.disabled = this.state.historyLoading;
  }

  private renderContext(): void {
    const context = this.state.context;
    this.paperScopeButton?.setAttribute("aria-pressed", String(this.state.scope === "paper"));
    this.libraryScopeButton?.setAttribute("aria-pressed", String(this.state.scope === "library"));
    if (this.state.scope === "library") {
      this.textarea.placeholder = "Ask across your Zotero library…";
      this.contextTitle.textContent = "Zotero Library";
      this.contextMeta.textContent = context
        ? `Paper context available · ${this.state.contextChips.filter((chip) => chip.kind === "external-paper").length} additional papers attached`
        : "Search metadata and attach papers for evidence-backed synthesis";
      this.choosePaperButton.textContent = "Attach Paper";
      this.choosePaperButton.title = "Attach a paper as the primary reading context";
      this.openPaperButton.hidden = !context;
      this.openPaperButton.disabled = !context;
      return;
    }
    this.choosePaperButton.textContent = context ? "Change Paper" : "Choose Paper";
    this.choosePaperButton.title = context ? "Choose another paper for this QLab tab" : "Choose a paper to read from the Zotero library";
    this.openPaperButton.hidden = !context;
    this.openPaperButton.disabled = !context;
    this.textarea.placeholder = context ? "Ask about this paper…" : "Message QLab…";
    if (!context) {
      this.contextTitle.textContent = "No paper selected";
      this.contextMeta.textContent = "Start chatting, or choose a paper from your Zotero library";
      return;
    }
    this.contextTitle.textContent = context.title || "Current PDF";
    const pieces = [
      context.pageLabel ? `Page ${context.pageLabel}` : "PDF connected",
      context.pagesCount ? `Total ${context.pagesCount} pages` : "",
      context.selectionText ? `Selection: ${context.selectionText.length} characters` : "No text selected"
    ].filter(Boolean);
    this.contextMeta.textContent = pieces.join(" · ");
  }

  private renderThreadTabs(): void {
    this.threadTabs.replaceChildren();
    this.threadTabs.hidden = this.state.threads.length === 0 && this.surface !== "workbench";
    const scroller = this.doc.createElement("div");
    scroller.className = "zc-thread-tab-scroll";
    for (const thread of this.state.threads) {
      const item = this.doc.createElement("span");
      item.className = "zc-thread-tab-item";
      const button = this.doc.createElement("button");
      button.type = "button";
      button.className = "zc-thread-tab";
      const switching = thread.status === "switching";
      button.classList.toggle("is-active", thread.active || switching);
      button.classList.toggle("is-switching", switching);
      button.dataset.threadId = thread.id;
      const tabLabel = thread.paperTitle || thread.title || "Conversation";
      const conversationDetail = thread.paperTitle && thread.title !== thread.paperTitle
        ? ` · ${thread.title}`
        : "";
      button.title = thread.readOnly
        ? `${tabLabel}${conversationDetail} · Read-only`
        : `${tabLabel}${conversationDetail}`;
      if (thread.active) button.setAttribute("aria-current", "page");
      if (switching) button.setAttribute("aria-busy", "true");
      const state = this.doc.createElement("span");
      state.className = `zc-thread-tab-state is-${thread.status || "idle"}`;
      state.setAttribute("aria-hidden", "true");
      const label = this.doc.createElement("span");
      label.textContent = tabLabel;
      button.append(state, label);
      button.addEventListener("click", () => this.callbacks.onSelectThread(thread.id));
      item.appendChild(button);
      // Closing a tab never deletes its Codex history. The history
      // rail can reopen it later. stopPropagation prevents an accidental
      // switch immediately before the close callback.
      const remove = this.doc.createElement("button");
      remove.type = "button";
      remove.className = "zc-thread-delete";
      remove.title = "Close Tab";
      remove.setAttribute("aria-label", `Close ${thread.title || "Conversation"}`);
      remove.textContent = "×";
      remove.addEventListener("click", (event) => {
        event.stopPropagation();
        (this.callbacks.onCloseThread || this.callbacks.onDeleteThread)?.(thread.id);
      });
      item.appendChild(remove);
      scroller.appendChild(item);
    }
    const add = this.iconButton("new", "New Conversation", () => this.callbacks.onNewThread());
    add.classList.add("zc-thread-tab-add");
    add.disabled = Boolean(this.state.creatingThread);
    add.title = this.state.creatingThread ? "Creating a new conversation…" : "New Conversation";
    if (this.surface === "workbench") {
      this.threadTabs.append(this.historyButton, scroller, add);
    }
    else {
      this.threadTabs.append(scroller, add);
    }
  }

  private renderContextChips(): void {
    this.contextChips.replaceChildren();
    for (const chip of this.effectiveContextChips()) {
      const wrapper = this.doc.createElement(chip.removable ? "button" : "span");
      if (chip.removable) (wrapper as HTMLButtonElement).type = "button";
      wrapper.className = `zc-context-chip is-${chip.kind}`;
      wrapper.dataset.contextId = chip.id;
      wrapper.title = chip.removable
        ? [
          `Remove context: ${chip.label}`,
          chip.detail,
        ].filter(Boolean).join(" · ")
        : chip.detail || chip.label;
      const icon = this.doc.createElement("span");
      icon.className = "zc-context-chip-icon";
      icon.textContent = contextGlyph(chip.kind);
      icon.setAttribute("aria-hidden", "true");
      const label = this.doc.createElement("span");
      label.className = "zc-context-chip-label";
      label.textContent = chip.label;
      wrapper.append(icon, label);
      if (chip.removable) {
        wrapper.classList.add("is-removable");
        wrapper.setAttribute("aria-label", `Remove context: ${chip.label}`);
        wrapper.addEventListener("click", () => this.callbacks.onRemoveContext?.(chip.id));
      }
      this.contextChips.appendChild(wrapper);
    }
    const add = this.iconButton("context", "Add paper context (@)", () => {
      this.openContextMenu("");
      this.textarea.focus();
    });
    add.classList.add("zc-add-context-button");
    this.contextChips.appendChild(add);
  }

  private effectiveContextChips(): ResearchContextChip[] {
    if (this.contextChipsExplicit) return this.state.contextChips;
    const context = this.state.context;
    if (!context) return [];
    const chips: ResearchContextChip[] = [{
      id: "active-paper",
      kind: "paper",
      label: "Current Paper",
      detail: context.title,
      removable: true,
    }];
    if (context.pageLabel) {
      chips.push({
        id: "current-page",
        kind: "page",
        label: `Page ${context.pageLabel}`,
        removable: true,
      });
    }
    if (context.selectionText) {
      chips.push({
        id: "current-selection",
        kind: "selection",
        label: `Selection · ${context.selectionText.length} characters`,
        removable: true,
      });
    }
    return chips;
  }

  private effectiveContextSuggestions(): ResearchContextSuggestion[] {
    if (this.state.contextSuggestions.length) return this.state.contextSuggestions;
    const context = this.state.context;
    const suggestions: ResearchContextSuggestion[] = [
      {
        id: "active-paper",
        kind: "paper",
        label: "Current Paper",
        detail: context?.title || "PDF open in Zotero Reader",
        disabled: !context,
      },
      {
        id: "current-page",
        kind: "page",
        label: context?.pageLabel ? `Current Page · Page ${context.pageLabel}` : "Current Page",
        detail: "Text on the currently visible PDF page",
        disabled: !context,
      },
      {
        id: "current-selection",
        kind: "selection",
        label: "Current Selection",
        detail: context?.selectionText
          ? `${context.selectionText.length} characters`
          : "Select text in the PDF first",
        disabled: !context?.selectionText,
      },
      {
        id: "active-annotations",
        kind: "annotation",
        label: "Annotations for this paper",
        detail: "Read highlights, comments, and page numbers on demand",
        disabled: !context,
      },
      {
        id: "zotero-library",
        kind: "library",
        label: "Zotero Library",
        detail: "Search other papers, collections, and tags",
      },
    ];
    return suggestions;
  }

  private filteredContextSuggestions(): ResearchContextSuggestion[] {
    const query = this.contextMenuQuery.trim().toLocaleLowerCase();
    if (!query) return this.effectiveContextSuggestions();
    return this.effectiveContextSuggestions().filter((suggestion) => [
      suggestion.label,
      suggestion.detail || "",
      suggestion.kind,
    ].join(" ").toLocaleLowerCase().includes(query));
  }

  private renderContextMenu(): void {
    const suggestions = this.filteredContextSuggestions();
    this.contextMenu.hidden = !this.contextMenuOpen;
    this.contextMenuList.replaceChildren();
    this.contextMenuEmpty.hidden = suggestions.length > 0;
    if (!this.contextMenuOpen) return;
    this.contextMenuSelection = Math.min(
      this.contextMenuSelection,
      Math.max(0, suggestions.length - 1),
    );
    if (suggestions[this.contextMenuSelection]?.disabled) {
      const enabledIndex = suggestions.findIndex((suggestion) => !suggestion.disabled);
      if (enabledIndex >= 0) this.contextMenuSelection = enabledIndex;
    }
    suggestions.forEach((suggestion, index) => {
      const button = this.doc.createElement("button");
      button.type = "button";
      button.className = "zc-context-option";
      button.classList.toggle("is-selected", index === this.contextMenuSelection);
      button.disabled = Boolean(suggestion.disabled);
      button.dataset.contextId = suggestion.id;
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", String(index === this.contextMenuSelection));
      const mark = this.doc.createElement("span");
      mark.className = `zc-context-option-mark is-${suggestion.kind}`;
      mark.textContent = contextGlyph(suggestion.kind);
      const copy = this.doc.createElement("span");
      const title = this.doc.createElement("strong");
      title.textContent = suggestion.label;
      const detail = this.doc.createElement("small");
      detail.textContent = suggestion.detail || contextKindLabel(suggestion.kind);
      copy.append(title, detail);
      button.append(mark, copy);
      button.addEventListener("mouseenter", () => {
        this.contextMenuSelection = index;
        for (const [optionIndex, option] of [
          ...this.contextMenuList.querySelectorAll<HTMLElement>(".zc-context-option"),
        ].entries()) {
          const selected = optionIndex === index;
          option.classList.toggle("is-selected", selected);
          option.setAttribute("aria-selected", String(selected));
        }
      });
      button.addEventListener("click", () => this.chooseContextSuggestion(suggestion));
      this.contextMenuList.appendChild(button);
    });
  }

  private openContextMenu(query: string, queryStart: number | null = null): void {
    this.contextMenuOpen = true;
    this.contextMenuQuery = query;
    this.contextQueryStart = queryStart;
    this.contextMenuSelection = 0;
    this.renderContextMenu();
  }

  private closeContextMenu(): void {
    this.contextMenuOpen = false;
    this.contextMenuQuery = "";
    this.contextQueryStart = null;
    this.contextMenuSelection = 0;
    this.renderContextMenu();
  }

  private updateContextMenuFromComposer(): void {
    const cursor = this.textarea.selectionStart ?? this.textarea.value.length;
    const beforeCursor = this.textarea.value.slice(0, cursor);
    const match = /(?:^|\s)@([^\s@]*)$/u.exec(beforeCursor);
    if (!match) {
      if (this.contextQueryStart !== null) this.closeContextMenu();
      return;
    }
    const query = match[1] || "";
    const queryStart = cursor - query.length - 1;
    this.openContextMenu(query, queryStart);
  }

  private handleContextMenuKeydown(event: KeyboardEvent): boolean {
    if (!this.contextMenuOpen || event.isComposing) return false;
    const suggestions = this.filteredContextSuggestions();
    if (event.key === "Escape") {
      event.preventDefault();
      this.closeContextMenu();
      return true;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!suggestions.length) return true;
      const direction = event.key === "ArrowDown" ? 1 : -1;
      let index = this.contextMenuSelection;
      for (let attempts = 0; attempts < suggestions.length; attempts++) {
        index = (index + direction + suggestions.length) % suggestions.length;
        if (!suggestions[index]?.disabled) break;
      }
      this.contextMenuSelection = index;
      this.renderContextMenu();
      return true;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const suggestion = suggestions[this.contextMenuSelection];
      if (!suggestion || suggestion.disabled) {
        this.closeContextMenu();
        return true;
      }
      this.chooseContextSuggestion(suggestion);
      return true;
    }
    return false;
  }

  private chooseContextSuggestion(suggestion: ResearchContextSuggestion): void {
    if (suggestion.disabled) return;
    if (this.contextQueryStart !== null) {
      const cursor = this.textarea.selectionStart ?? this.textarea.value.length;
      const before = this.textarea.value.slice(0, this.contextQueryStart);
      const after = this.textarea.value.slice(cursor);
      const spacer = before && !/\s$/u.test(before) && after && !/^\s/u.test(after) ? " " : "";
      this.textarea.value = before + spacer + after;
      const nextCursor = before.length + spacer.length;
      this.textarea.setSelectionRange(nextCursor, nextCursor);
      this.autoSizeComposer();
    }
    this.callbacks.onAddContext?.(suggestion);
    if (!this.callbacks.onAddContext && suggestion.kind === "selection") {
      this.callbacks.onInsertSelection();
    }
    this.closeContextMenu();
    this.textarea.focus();
  }

  private renderModels(): void {
    const previous = this.modelSelect.value;
    const models = this.state.models.length
      ? this.state.models
      : [{ id: "", label: "Default Model" }];
    renderModelOptions(this.modelSelect, models, this.state.selectedModel || previous || models[0]?.id || "");
  }

  private renderEfforts(modelId = this.modelSelect.value, preferModelDefault = false): void {
    const model = this.state.models.find((candidate) => candidate.id === modelId);
    const efforts = model?.supportedReasoningEfforts?.length
      ? model.supportedReasoningEfforts
      : FALLBACK_REASONING_EFFORTS;
    const supported = new Set(efforts.map((option) => option.reasoningEffort));
    const modelDefault = model?.defaultReasoningEffort;
    const selected = preferModelDefault || !supported.has(this.state.effort)
      ? (modelDefault && supported.has(modelDefault) ? modelDefault : efforts[0]?.reasoningEffort || "medium")
      : this.state.effort;
    this.effortSelect.replaceChildren();
    for (const effort of efforts) {
      const option = this.doc.createElement("option");
      option.value = effort.reasoningEffort;
      option.textContent = `Reasoning: ${effortLabel(effort.reasoningEffort)}`;
      if (effort.description) option.title = effort.description;
      this.effortSelect.appendChild(option);
    }
    this.effortSelect.value = selected;
  }

  private renderTranscript(): void {
    const desired: HTMLElement[] = [];
    const activeIDs = new Set<string>();

    const hasWorkbenchCards = Boolean(
      this.state.plan
      || this.state.reviews.length
      || this.state.pendingApproval
      || this.state.noting,
    );
    if (!this.state.entries.length && !hasWorkbenchCards && this.state.phase === "ready") {
      this.emptyState ||= this.createEmptyState();
      const title = this.emptyState.querySelector("h2");
      const subtitle = this.emptyState.querySelector("p");
      if (title) title.textContent = this.state.context ? "Think with the Current Paper" : "What would you like to research?";
      if (subtitle) {
        subtitle.textContent = this.state.context
          ? "Codex can read the current page, selection, full text, and annotations on demand and cite their locations."
          : "Start chatting directly, or choose a Zotero paper above as context.";
      }
      const prompts = this.state.context
        ? ["Explain the selected passage", "Summarize the main argument on this page", "What are this paper's key assumptions?"]
        : ["Search my Zotero Library", "Help me shape a research question", "Plan a new Draft"];
      [...this.emptyState.querySelectorAll<HTMLButtonElement>(".zc-suggestions button")]
        .forEach((button, index) => { button.textContent = prompts[index] || ""; });
      desired.push(this.emptyState);
    }

    if (this.state.plan) {
      const plan = this.state.plan;
      const id = `research-plan:${plan.id}`;
      const fingerprint = JSON.stringify(plan);
      activeIDs.add(id);
      desired.push(this.cachedEntryNode(id, fingerprint, () => this.renderPlanCard(plan)));
    }

    let activityGroup: Exchange | null = null;
    const groups = groupEntries(this.state.entries);
    groups.forEach((group, index) => {
      for (const entry of contentEntries(group)) {
        activeIDs.add(entry.id);
        const fingerprint = JSON.stringify([
          entry.kind,
          entry.text,
          entry.title || "",
          entry.state || "",
        ]);
        desired.push(this.cachedEntryNode(entry.id, fingerprint, () => this.renderEntry(entry)));
      }
      if (group.id === "preamble") return;
      const isLastGroup = index === groups.length - 1;
      if (isLastGroup && this.state.running) {
        activityGroup = group;
        return;
      }
      const steps = processEntries(group).length;
      const elapsed = this.state.turnDurations[group.id];
      if (steps === 0 && elapsed === undefined) return;
      const summaryId = `turn-summary:${group.id}`;
      const expanded = this.expandedTurns.has(group.id);
      activeIDs.add(summaryId);
      const summaryFingerprint = JSON.stringify([elapsed ?? null, steps, expanded]);
      desired.push(this.cachedEntryNode(
        summaryId,
        summaryFingerprint,
        () => this.renderTurnSummary(group, steps, elapsed),
      ));
      if (expanded) {
        const detailId = `turn-detail:${group.id}`;
        const processes = processEntries(group);
        activeIDs.add(detailId);
        const detailFingerprint = JSON.stringify(
          processes.map((entry) => [entry.id, entry.kind, entry.text, entry.title || "", entry.state || ""]),
        );
        desired.push(this.cachedEntryNode(
          detailId,
          detailFingerprint,
          () => this.renderTurnDetail(processes),
        ));
      }
    });
    const groupIds = new Set(groups.map((group) => group.id));
    for (const id of this.expandedTurns) {
      if (!groupIds.has(id)) this.expandedTurns.delete(id);
    }

    for (const review of this.state.reviews) {
      if (review.state === "applied") continue;
      const id = `diff-review:${review.id}`;
      const fingerprint = JSON.stringify(review);
      activeIDs.add(id);
      desired.push(this.cachedEntryNode(id, fingerprint, () => this.renderDiffReview(review)));
    }

    if (this.state.pendingApproval) {
      const approval = this.state.pendingApproval;
      const id = `approval:${approval.id}`;
      const fingerprint = JSON.stringify(approval);
      activeIDs.add(id);
      desired.push(this.cachedEntryNode(id, fingerprint, () => this.renderApprovalCard(approval)));
    }

    if (this.state.paperTrailConsent) {
      const consent = this.state.paperTrailConsent;
      const id = "consent:paper-trail";
      const fingerprint = JSON.stringify(consent);
      activeIDs.add(id);
      desired.push(this.cachedEntryNode(id, fingerprint, () => this.renderConsentCard(consent)));
    }

    if (this.state.noting) {
      const noting = this.state.noting;
      const id = "noting";
      // The preview body render is the expensive part; truncating markdown
      // in the fingerprint only detects a *change*, it doesn't need to be
      // unique for arbitrarily large notes.
      const fingerprint = JSON.stringify({ ...noting, markdown: (noting.markdown ?? "").slice(0, 200) });
      activeIDs.add(id);
      desired.push(this.cachedEntryNode(id, fingerprint, () => this.renderNotingCard(noting)));
    }
    if (activityGroup) desired.push(this.renderActivityLine(activityGroup));
    for (const id of this.entryNodes.keys()) {
      if (!activeIDs.has(id)) this.entryNodes.delete(id);
    }
    reconcileChildren(this.transcript, desired);
    const activeThreadId = this.state.threads.find((thread) => thread.active)?.id;
    if (activeThreadId !== this.lastActiveThreadId) {
      this.pinnedToBottom = true;
    }
    this.lastActiveThreadId = activeThreadId;
    if (this.pinnedToBottom) {
      this.transcript.scrollTop = this.transcript.scrollHeight;
    }
    this.syncActivityTimer();
  }

  private cachedEntryNode(
    id: string,
    fingerprint: string,
    create: () => HTMLElement,
  ): HTMLElement {
    const existing = this.entryNodes.get(id);
    if (existing?.fingerprint === fingerprint) return existing.node;
    const node = create();
    const previousDetails = existing?.node.querySelector("details");
    const nextDetails = node.querySelector("details");
    if (previousDetails && nextDetails) nextDetails.open = previousDetails.open;
    this.entryNodes.set(id, { fingerprint, node });
    return node;
  }

  private renderTurnSummary(group: Exchange, steps: number, elapsed: number | undefined): HTMLElement {
    const button = this.doc.createElement("button");
    button.type = "button";
    button.className = "zc-turn-summary";
    const parts: string[] = [];
    if (elapsed !== undefined) parts.push(`⏱ ${formatElapsed(elapsed)}`);
    if (steps > 0) parts.push(`${steps} steps`);
    button.textContent = parts.join(" · ");
    button.addEventListener("click", () => {
      if (this.expandedTurns.has(group.id)) this.expandedTurns.delete(group.id);
      else this.expandedTurns.add(group.id);
      this.render();
    });
    return button;
  }

  private renderTurnDetail(processes: ChatEntry[]): HTMLElement {
    const container = this.doc.createElement("div");
    container.className = "zc-turn-detail";
    for (const entry of processes) {
      container.appendChild(this.renderEntry(entry));
    }
    return container;
  }

  /**
   * The activity line's spinner/shimmer are CSS animations keyed to the DOM
   * node's lifetime: recreating the node every render (as every other
   * transcript entry does) resets them to frame 0 on each of the ~20/s
   * streaming renders, so the spinner appears frozen. Instead, this node is
   * created once and reused; each render only patches its label/elapsed
   * text in place, so `reconcileChildren` sees the same node reference and
   * leaves the element (and its running animation) alone.
   */
  private renderActivityLine(group: Exchange): HTMLElement {
    if (!this.activityNode) {
      const line = this.doc.createElement("div");
      line.className = "zc-activity";
      const spinner = this.doc.createElement("span");
      spinner.className = "zc-activity-spinner";
      spinner.setAttribute("aria-hidden", "true");
      const label = this.doc.createElement("span");
      label.className = "zc-activity-label";
      line.append(spinner, label);
      this.activityNode = line;
      this.activityLabelEl = label;
    }
    const line = this.activityNode;
    const nextLabel = activityLabel(group.entries);
    if (this.activityLabelEl!.textContent !== nextLabel) this.activityLabelEl!.textContent = nextLabel;

    if (this.state.turnStartedAt !== null) {
      const nextElapsed = formatElapsed(Date.now() - this.state.turnStartedAt);
      if (!this.activityElapsedEl) {
        const elapsed = this.doc.createElement("span");
        elapsed.className = "zc-activity-elapsed";
        line.appendChild(elapsed);
        this.activityElapsedEl = elapsed;
      }
      if (this.activityElapsedEl.textContent !== nextElapsed) this.activityElapsedEl.textContent = nextElapsed;
    }
    else if (this.activityElapsedEl) {
      this.activityElapsedEl.remove();
      this.activityElapsedEl = null;
    }
    return line;
  }

  private syncActivityTimer(): void {
    if (this.state.running) {
      if (this.activityTimer === null) {
        this.activityTimer = this.doc.defaultView?.setInterval(() => {
          const turnStartedAt = this.state.turnStartedAt;
          if (turnStartedAt === null) return;
          const elapsed = this.transcript.querySelector<HTMLElement>(".zc-activity-elapsed");
          if (elapsed) elapsed.textContent = formatElapsed(Date.now() - turnStartedAt);
        }, 1000) ?? null;
      }
      return;
    }
    if (this.activityTimer !== null) {
      this.doc.defaultView?.clearInterval(this.activityTimer);
      this.activityTimer = null;
    }
  }

  private createEmptyState(): HTMLElement {
    const empty = this.doc.createElement("div");
    empty.className = "zc-empty-state";
    const mark = this.doc.createElement("img");
    mark.src = "chrome://zotkit/content/icons/icon.svg";
    mark.alt = "";
    const title = this.doc.createElement("h2");
    const subtitle = this.doc.createElement("p");
    const suggestions = this.doc.createElement("div");
    suggestions.className = "zc-suggestions";
    for (const prompt of ["", "", ""]) {
      const button = this.doc.createElement("button");
      button.type = "button";
      button.textContent = prompt;
      button.addEventListener("click", () => this.focusComposer(button.textContent || ""));
      suggestions.appendChild(button);
    }
    empty.append(mark, title, subtitle, suggestions);
    return empty;
  }

  private renderPlanCard(plan: ResearchPlan): HTMLElement {
    const article = this.doc.createElement("article");
    article.className = "zc-entry zc-plan-card";
    article.dataset.entryId = `research-plan:${plan.id}`;
    const details = this.doc.createElement("details");
    details.open = true;
    const summary = this.doc.createElement("summary");
    const title = this.doc.createElement("span");
    title.textContent = plan.title || "Research Plan";
    const progress = this.doc.createElement("small");
    const complete = plan.steps.filter((step) => step.status === "complete").length;
    progress.textContent = `${complete}/${plan.steps.length}`;
    summary.append(title, progress);
    const body = this.doc.createElement("div");
    body.className = "zc-plan-body";
    if (plan.explanation) {
      const explanation = this.doc.createElement("p");
      explanation.textContent = plan.explanation;
      body.appendChild(explanation);
    }
    const list = this.doc.createElement("ol");
    for (const step of plan.steps) {
      const item = this.doc.createElement("li");
      item.className = `is-${step.status}`;
      item.dataset.planStepId = step.id;
      const state = this.doc.createElement("span");
      state.className = "zc-plan-step-state";
      state.textContent = step.status === "complete" ? "✓"
        : step.status === "failed" ? "!"
          : step.status === "running" ? "◌" : "";
      const label = this.doc.createElement("span");
      label.textContent = step.title;
      item.append(state, label);
      list.appendChild(item);
    }
    body.appendChild(list);
    details.append(summary, body);
    article.appendChild(details);
    return article;
  }

  private renderDiffReview(review: DiffReview): HTMLElement {
    const article = this.doc.createElement("article");
    article.className = `zc-entry zc-review-card is-${review.state || "pending"}`;
    article.dataset.entryId = `diff-review:${review.id}`;
    const details = this.doc.createElement("details");
    details.open = review.state === undefined || review.state === "pending";
    const summary = this.doc.createElement("summary");
    const identity = this.doc.createElement("span");
    identity.textContent = review.title;
    const badge = this.doc.createElement("small");
    badge.textContent = review.state === "applied" ? "Applied"
      : review.state === "accepted" ? "Accepted"
      : review.state === "rejected" ? "Dismissed"
        : review.state === "failed" ? "Apply Failed" : "Review";
    summary.append(identity, badge);
    if (review.state === "applied") {
      // Draft writes already landed in the isolated AI working copy. The
      // rendered eye/Keep controls are the single human review surface, so a
      // second disabled Accept Suggestion action here would be misleading.
      details.append(summary);
      article.appendChild(details);
      return article;
    }
    const body = this.doc.createElement("div");
    body.className = "zc-review-body";
    if (review.summary) {
      const description = this.doc.createElement("p");
      description.textContent = review.summary;
      body.appendChild(description);
    }
    const diff = this.doc.createElement("pre");
    diff.className = "zc-diff-view";
    for (const line of review.diff.replace(/\r\n?/g, "\n").split("\n")) {
      const row = this.doc.createElement("span");
      row.className = line.startsWith("+") && !line.startsWith("+++") ? "is-addition"
        : line.startsWith("-") && !line.startsWith("---") ? "is-deletion"
          : line.startsWith("@@") ? "is-hunk" : "is-context";
      row.textContent = line || " ";
      diff.append(row, this.doc.createTextNode("\n"));
    }
    const actions = this.doc.createElement("div");
    actions.className = "zc-review-actions";
    const reject = this.doc.createElement("button");
    reject.type = "button";
    reject.textContent = "Dismiss";
    reject.disabled = Boolean(review.state && review.state !== "pending");
    reject.addEventListener("click", () => this.callbacks.onReviewDecision?.(review.id, "reject"));
    const accept = this.doc.createElement("button");
    accept.type = "button";
    accept.className = "is-primary";
    accept.textContent = "Accept Suggestion";
    accept.disabled = Boolean(review.state && review.state !== "pending");
    accept.addEventListener("click", () => this.callbacks.onReviewDecision?.(review.id, "accept"));
    actions.append(reject, accept);
    body.append(diff, actions);
    details.append(summary, body);
    article.appendChild(details);
    return article;
  }

  private renderApprovalCard(approval: PendingApproval): HTMLElement {
    const article = this.doc.createElement("article");
    article.className = `zc-entry zc-approval-card is-${approval.risk || "medium"}`;
    article.dataset.entryId = `approval:${approval.id}`;
    const heading = this.doc.createElement("div");
    heading.className = "zc-approval-heading";
    const badge = this.doc.createElement("span");
    badge.textContent = approval.kind === "command" ? "Command Approval"
      : approval.kind === "tool" ? "Tool Approval" : "Confirmation Required";
    const title = this.doc.createElement("strong");
    title.textContent = approval.title;
    heading.append(badge, title);
    article.appendChild(heading);
    if (approval.description) {
      const description = this.doc.createElement("p");
      description.textContent = approval.description;
      article.appendChild(description);
    }
    if (approval.command) {
      const command = this.doc.createElement("code");
      command.textContent = approval.command;
      article.appendChild(command);
    }
    const actions = this.doc.createElement("div");
    actions.className = "zc-approval-actions";
    const reject = this.doc.createElement("button");
    reject.type = "button";
    reject.textContent = "Reject";
    reject.addEventListener("click", () => {
      this.callbacks.onApprovalDecision?.(approval.id, "reject");
    });
    const approve = this.doc.createElement("button");
    approve.type = "button";
    approve.className = "is-primary";
    approve.textContent = "Allow Once";
    approve.addEventListener("click", () => {
      this.callbacks.onApprovalDecision?.(approval.id, "approve-once");
    });
    actions.append(reject, approve);
    article.appendChild(actions);
    return article;
  }

  private renderConsentCard(consent: { question: string; pageNumber?: number }): HTMLElement {
    const article = this.doc.createElement("article");
    article.className = "zc-entry zc-consent-card";
    article.dataset.entryId = "consent:paper-trail";
    const heading = this.doc.createElement("div");
    heading.className = "zc-approval-heading";
    const badge = this.doc.createElement("span");
    badge.textContent = "Reading Trail";
    const title = this.doc.createElement("strong");
    title.textContent = "Create highlight annotation automatically";
    heading.append(badge, title);
    article.appendChild(heading);
    const description = this.doc.createElement("p");
    const pageLabel = consent.pageNumber !== undefined ? `Page ${consent.pageNumber}` : "Current location";
    description.textContent = `QLab will create a highlight annotation at the question location (question and answer summary). You can disable this at any time. ${pageLabel}: “${consent.question}”`;
    article.appendChild(description);
    const actions = this.doc.createElement("div");
    actions.className = "zc-approval-actions";
    const decline = this.doc.createElement("button");
    decline.type = "button";
    decline.textContent = "Do Not Annotate";
    decline.addEventListener("click", () => {
      this.callbacks.onPaperTrailConsent?.("decline");
    });
    const accept = this.doc.createElement("button");
    accept.type = "button";
    accept.className = "is-primary";
    accept.textContent = "Allow";
    accept.addEventListener("click", () => {
      this.callbacks.onPaperTrailConsent?.("accept");
    });
    actions.append(decline, accept);
    article.appendChild(actions);
    return article;
  }

  private renderNotingCard(noting: NotingView): HTMLElement {
    const article = this.doc.createElement("article");
    article.className = `zc-entry zc-noting-card is-${noting.phase}`;
    article.dataset.entryId = "noting";

    const heading = this.doc.createElement("div");
    heading.className = "zc-approval-heading";
    const badge = this.doc.createElement("span");
    badge.textContent = "Reading Notes";
    const title = this.doc.createElement("strong");
    title.textContent = NOTING_PHASE_TITLES[noting.phase];
    heading.append(badge, title);
    article.appendChild(heading);

    const closeButton = (label: string) => {
      const button = this.doc.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.addEventListener("click", () => this.callbacks.onNotingCancel?.());
      return button;
    };

    if (noting.phase === "confirm-mismatch") {
      const warning = this.doc.createElement("p");
      warning.textContent = "The paper file changed; existing anchors refer to the previous version.";
      const actions = this.doc.createElement("div");
      actions.className = "zc-noting-actions";
      const cancel = this.doc.createElement("button");
      cancel.type = "button";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => this.callbacks.onNotingDecision?.("cancel"));
      const proceed = this.doc.createElement("button");
      proceed.type = "button";
      proceed.className = "is-primary";
      proceed.textContent = "Continue";
      proceed.addEventListener("click", () => this.callbacks.onNotingDecision?.("continue"));
      actions.append(cancel, proceed);
      article.append(warning, actions);
      return article;
    }

    if (noting.phase === "generating" || noting.phase === "applying") {
      const spinner = this.doc.createElement("p");
      spinner.className = "zc-noting-spinner";
      spinner.textContent = noting.phase === "generating" ? "Synthesizing…" : "Writing attachment…";
      article.appendChild(spinner);
      return article;
    }

    if (noting.phase === "failed") {
      const error = this.doc.createElement("p");
      error.className = "zc-noting-error";
      error.textContent = noting.error || "Generation Failed";
      const actions = this.doc.createElement("div");
      actions.className = "zc-noting-actions";
      actions.appendChild(closeButton("Close"));
      article.append(error, actions);
      return article;
    }

    if (noting.phase === "done") {
      const done = this.doc.createElement("p");
      done.textContent = "Written ✓";
      const actions = this.doc.createElement("div");
      actions.className = "zc-noting-actions";
      actions.appendChild(closeButton("Close"));
      article.append(done, actions);
      return article;
    }

    // preview
    const stats = this.doc.createElement("p");
    stats.className = "zc-noting-stats";
    stats.textContent = `${noting.anchorCount} anchors · ${noting.openCount} unresolved · ${noting.mathErrors} formulas to verify`;

    const preview = this.doc.createElement("div");
    preview.className = "zc-noting-preview";
    preview.appendChild(renderMarkdown(this.doc, noting.markdown ?? ""));

    let selectedMode: { kind: "new" } | { kind: "replace"; key: string } = { kind: "new" };
    const versionGroup = this.doc.createElement("div");
    versionGroup.className = "zc-noting-versions";
    const versionName = `zc-noting-version-${Math.random().toString(36).slice(2)}`;
    const addOption = (value: string, label: string, checked: boolean, onPick: () => void) => {
      const option = this.doc.createElement("label");
      option.className = "zc-noting-version-option";
      const input = this.doc.createElement("input");
      input.type = "radio";
      input.name = versionName;
      input.value = value;
      input.checked = checked;
      input.addEventListener("change", onPick);
      const text = this.doc.createElement("span");
      text.textContent = label;
      option.append(input, text);
      versionGroup.appendChild(option);
    };
    addOption("new", "Create New Version", true, () => { selectedMode = { kind: "new" }; });
    for (const version of noting.versions) {
      addOption(version.key, `Replace: ${version.title}`, false, () => { selectedMode = { kind: "replace", key: version.key }; });
    }

    const actions = this.doc.createElement("div");
    actions.className = "zc-noting-actions";
    const cancel = this.doc.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => this.callbacks.onNotingCancel?.());
    const apply = this.doc.createElement("button");
    apply.type = "button";
    apply.className = "zc-noting-apply is-primary";
    apply.textContent = "Apply to Attachment";
    apply.addEventListener("click", () => {
      // Belt-and-suspenders alongside NotingService's own reentrancy guard:
      // disable immediately so a rapid double-click can't even dispatch a
      // second click before the ~50ms debounced re-render swaps this card
      // out for the "applying" phase.
      apply.disabled = true;
      this.callbacks.onNotingApply?.(selectedMode);
    });
    actions.append(cancel, apply);

    article.append(stats, preview, versionGroup, actions);
    return article;
  }

  private renderEntry(entry: ChatEntry): HTMLElement {
    const article = this.doc.createElement("article");
    article.className = `zc-entry zc-entry-${entry.kind}`;
    article.dataset.entryId = entry.id;
    if (entry.kind === "user") {
      appendUserMessage(this.doc, article, entry, this.expandedUserMessages);
      return article;
    }
    if (entry.kind === "tool" || entry.kind === "command" || entry.kind === "reasoning") {
      const details = this.doc.createElement("details");
      details.className = "zc-tool-card";
      if (entry.kind === "reasoning") details.open = false;
      const summary = this.doc.createElement("summary");
      const state = this.doc.createElement("span");
      state.className = `zc-tool-state ${entry.state || "complete"}`;
      state.textContent = entry.state === "running" ? "◌" : entry.state === "failed" ? "!" : "✓";
      const label = this.doc.createElement("span");
      label.textContent = entry.title || (entry.kind === "reasoning" ? "Reasoning" : "Tool");
      summary.append(state, label);
      const content = this.doc.createElement("div");
      content.className = "zc-tool-content";
      content.appendChild(renderMarkdown(this.doc, entry.text, this.markdownOptions()));
      details.append(summary, content);
      article.appendChild(details);
      return article;
    }
    if (entry.kind === "status") {
      article.textContent = entry.text;
      return article;
    }
    const avatar = this.createCodexAvatar();
    const content = this.doc.createElement("div");
    content.className = "zc-entry-content";
    const markdownBody = this.doc.createElement("div");
    markdownBody.className = "zc-markdown";
    markdownBody.appendChild(renderMarkdown(this.doc, entry.text, this.markdownOptions()));
    content.appendChild(markdownBody);
    if (entry.kind === "assistant") {
      content.appendChild(this.createCopyAnswerButton(entry.text));
    }
    article.append(avatar, content);
    return article;
  }

  private createCodexAvatar(): HTMLImageElement {
    const avatar = this.doc.createElement("img");
    avatar.className = "zc-entry-avatar";
    avatar.src = "chrome://zotkit/content/icons/icon.svg";
    avatar.alt = "Codex";
    return avatar;
  }

  private markdownOptions(): {
    onPdfPageLink: (reference: PdfPageReference) => void;
    canOpenPdfPageLink: (reference: PdfPageReference) => boolean;
  } | Record<string, never> {
    return this.callbacks.onOpenPdfPage && this.callbacks.canOpenPdfPage
      ? {
          onPdfPageLink: this.callbacks.onOpenPdfPage,
          canOpenPdfPageLink: this.callbacks.canOpenPdfPage,
        }
      : {};
  }

  private createCopyAnswerButton(text: string): HTMLButtonElement {
    const button = this.doc.createElement("button");
    button.type = "button";
    button.className = "zc-copy-answer";
    button.title = "Copy Answer";
    button.replaceChildren(createSidebarIcon(this.doc, "copy"));
    button.addEventListener("click", () => {
      if (!copyToClipboard(text)) return;
      button.classList.add("is-copied");
      button.title = "Copied";
      this.doc.defaultView?.setTimeout(() => {
        button.classList.remove("is-copied");
        button.title = "Copy Answer";
      }, 1500);
    });
    return button;
  }

  private renderLoginLayer(): void {
    this.loginLayer.replaceChildren();
    this.loginLayer.hidden = this.state.phase === "ready";
    if (this.state.phase === "ready") return;
    const card = this.doc.createElement("div");
    card.className = "zc-login-card";
    const icon = this.doc.createElement("img");
    icon.src = "chrome://zotkit/content/icons/icon.svg";
    icon.alt = "";
    const title = this.doc.createElement("h2");
    const detail = this.doc.createElement("p");
    let button: HTMLButtonElement | null = this.doc.createElement("button");
    button.type = "button";
    button.className = "zc-login-button";
    if (this.state.phase === "connecting") {
      title.textContent = "Connecting to Codex";
      detail.textContent = "Reading the existing Codex CLI sign-in state…";
      button.hidden = true;
    }
    else if (this.state.phase === "signed-out") {
      title.textContent = "Use Codex in Zotero";
      detail.textContent = "Sign in with ChatGPT. The local Codex CLI manages the session; the plugin never reads or stores tokens.";
      if (this.state.capabilities?.supportsLogin !== false) {
        button.textContent = "Sign In with ChatGPT";
        button.addEventListener("click", () => this.callbacks.onLogin());
      }
      else {
        // No Codex-login affordance at all for a backend that doesn't
        // support it (e.g. the built-in engine): omit the button entirely,
        // not merely hide it, so it can't be found or focused.
        button = null;
      }
    }
    else {
      title.textContent = this.state.phase === "unavailable" ? "Codex CLI Not Found" : "Codex is temporarily unavailable";
      detail.textContent = this.state.error || "Confirm that the Codex CLI is installed, then retry.";
      button.textContent = "Retry";
      button.addEventListener("click", () => this.callbacks.onRefreshContext());
    }
    card.append(icon, title, detail, ...(button ? [button] : []));
    if (this.state.phase === "unavailable" || this.state.phase === "error") {
      const terminal = this.doc.createElement("button");
      terminal.type = "button";
      terminal.className = "zc-login-secondary";
      terminal.textContent = "Open Advanced Terminal";
      terminal.addEventListener("click", () => this.callbacks.onOpenTerminal());
      card.appendChild(terminal);
    }
    if (this.state.phase === "unavailable" || this.state.phase === "error" || this.state.phase === "signed-out") {
      // A broken backend/connection must not lock the user out of the
      // settings gear (it lives in the composer, hidden behind this
      // full-pane overlay in every non-ready phase): offer the same
      // escape hatch here.
      const settings = this.doc.createElement("button");
      settings.type = "button";
      settings.className = "zc-login-secondary zc-error-settings";
      settings.textContent = "Choose QLab Repository";
      settings.addEventListener("click", () => this.callbacks.onChooseQLabRoot?.());
      card.appendChild(settings);
    }
    this.loginLayer.appendChild(card);
  }

  private toggleAccountMenu(): void {
    const existing = this.root.querySelector(".zc-account-menu");
    if (existing) {
      existing.remove();
      return;
    }
    const menu = this.doc.createElement("div");
    menu.className = "zc-account-menu";
    const label = this.doc.createElement("div");
    label.textContent = this.state.accountLabel || "Codex";
    const readonly = this.doc.createElement("small");
    readonly.textContent = this.state.mode === "ask"
      ? "Ask: Library is read-only"
      : "Agent: changes require approval";
    menu.append(label, readonly);
    if (this.state.capabilities?.supportsLogin !== false) {
      const logout = this.doc.createElement("button");
      logout.type = "button";
      logout.textContent = "Sign Out of Codex";
      logout.addEventListener("click", () => {
        menu.remove();
        this.callbacks.onLogout();
      });
      menu.appendChild(logout);
    }
    this.placeMenu(menu, this.accountButton);
  }

  private toggleHistoryMenu(): void {
    const existing = this.root.querySelector(".zc-history-menu");
    if (existing) {
      existing.remove();
      return;
    }
    this.root.querySelector(".zc-account-menu")?.remove();
    const menu = this.doc.createElement("div");
    menu.className = "zc-history-menu";
    const heading = this.doc.createElement("div");
    heading.className = "zc-menu-heading";
    heading.textContent = "Open Conversations";
    menu.appendChild(heading);
    if (!this.state.threads.length) {
      const empty = this.doc.createElement("small");
      empty.textContent = "No conversation history yet";
      menu.appendChild(empty);
    }
    for (const thread of this.state.threads) {
      const item = this.doc.createElement("div");
      item.className = "zc-history-menu-item";
      const button = this.doc.createElement("button");
      button.type = "button";
      button.className = thread.active ? "is-active" : "";
      const title = this.doc.createElement("span");
      title.textContent = thread.title || "Paper Conversation";
      const time = this.doc.createElement("small");
      const date = new Date(thread.updatedAt);
      time.textContent = Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
      button.append(title, time);
      button.addEventListener("click", () => {
        menu.remove();
        this.callbacks.onSelectThread(thread.id);
      });
      item.appendChild(button);
      // The compact picker mirrors the Workbench tab strip: closing a row
      // never deletes its underlying conversation history.
      // stopPropagation keeps this from also selecting the thread; closing
      // the whole menu (same as a select click already does) makes the
      // deleted row disappear immediately instead of leaving it stale.
      const remove = this.doc.createElement("button");
      remove.type = "button";
      remove.className = "zc-thread-delete";
      remove.title = "Close Tab";
      remove.setAttribute("aria-label", `Close ${thread.title || "Conversation"}`);
      remove.textContent = "×";
      remove.addEventListener("click", (event) => {
        event.stopPropagation();
        menu.remove();
        (this.callbacks.onCloseThread || this.callbacks.onDeleteThread)?.(thread.id);
      });
      item.appendChild(remove);
      menu.appendChild(item);
    }
    this.placeMenu(menu, this.historyButton);
  }

  /**
   * Opens a menu underneath the button that owns it.
   *
   * These used to be appended to the sidebar root and positioned with a fixed
   * `right` offset, which put them at the window edge as soon as the workbench
   * layout gave the root a second column. Anchoring to the actions row keeps
   * "underneath its button" true whatever the layout does.
   */
  private placeMenu(menu: HTMLElement, anchor: HTMLElement): void {
    this.topActions.appendChild(menu);
    const button = anchor.getBoundingClientRect();
    const container = this.topActions.getBoundingClientRect();
    if (!container.width && !container.height) return; // No layout yet; CSS defaults apply.
    if (this.surface === "workbench") {
      menu.style.top = "auto";
      menu.style.bottom = `${Math.round(container.bottom - button.top + 6)}px`;
      menu.style.left = `${Math.round(Math.max(0, button.left - container.left))}px`;
      menu.style.right = "auto";
      return;
    }
    menu.style.top = `${Math.round(button.bottom - container.top + 6)}px`;
    menu.style.right = `${Math.round(Math.max(0, container.right - button.right))}px`;
  }

  private submit(): void {
    const text = this.textarea.value.trim();
    if (!text || !this.canSendCodex()) return;
    this.closeContextMenu();
    this.textarea.value = "";
    this.autoSizeComposer();
    this.callbacks.onSend(text);
  }

  private autoSizeComposer(): void {
    this.textarea.style.height = "auto";
    this.textarea.style.height = `${Math.min(this.textarea.scrollHeight, 180)}px`;
  }

  private iconButton(
    icon: SidebarIcon,
    title: string,
    onClick: () => void,
    visibleLabel?: string
  ): HTMLButtonElement {
    const button = this.doc.createElement("button");
    button.type = "button";
    button.className = "zc-icon-button";
    button.title = title;
    button.setAttribute("aria-label", title);
    this.setButtonIcon(button, icon);
    if (visibleLabel) {
      const label = this.doc.createElement("span");
      label.className = "zc-button-label";
      label.textContent = visibleLabel;
      button.appendChild(label);
    }
    button.addEventListener("click", onClick);
    return button;
  }

  private presentMainSiteButton(button: HTMLButtonElement, title: string): void {
    this.setButtonIcon(button, "site");
    button.title = title;
    button.setAttribute("aria-label", title);
  }

  private setButtonIcon(button: HTMLButtonElement, icon: SidebarIcon): void {
    button.replaceChildren(createSidebarIcon(this.doc, icon));
  }
}

const SIDEBAR_ICON_PATHS: Record<SidebarIcon, string[]> = {
  history: ["M5 6h14", "M5 12h14", "M5 18h14"],
  new: ["M12 5v14", "M5 12h14"],
  terminal: ["M4 5h16v14H4z", "m7 9 3 3-3 3", "M13 15h4"],
  site: ["M4 10.5 12 4l8 6.5", "M6.5 9.5V20h11V9.5", "M9.5 20v-6h5v6"],
  popout: ["M14 4h6v6", "M20 4l-9 9", "M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6"],
  more: ["M5 12h.01", "M12 12h.01", "M19 12h.01"],
  refresh: ["M20 6v5h-5", "M4 18v-5h5", "M18.2 9a7 7 0 0 0-11.7-2.5L4 11", "M5.8 15a7 7 0 0 0 11.7 2.5L20 13"],
  send: ["M12 19V5", "M6 11l6-6 6 6"],
  stop: ["M8 8h8v8H8z"],
  context: ["M12 5v14", "M5 12h14", "M4 4h16v16H4z"],
  close: ["m7 7 10 10", "m17 7-10 10"],
  copy: ["M9 9h10v12H9z", "M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"],
  note: ["M6 3h8l5 5v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z", "M14 3v5h5", "M8.5 13h7", "M8.5 16.5h5"],
};

export function createSidebarIcon(doc: Document, icon: SidebarIcon): SVGElement {
  const svg = doc.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("zc-button-icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", icon === "more" ? "3" : "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  for (const data of SIDEBAR_ICON_PATHS[icon]) {
    const path = doc.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", data);
    svg.appendChild(path);
  }
  return svg;
}

const NOTING_PHASE_TITLES: Record<NotingPhase, string> = {
  "confirm-mismatch": "PDF Changed",
  generating: "Synthesizing…",
  preview: "Reading-note preview",
  applying: "Writing attachment…",
  done: "Written ✓",
  failed: "Generation Failed",
};

const FALLBACK_REASONING_EFFORTS: ReasoningEffortOption[] = [
  { reasoningEffort: "minimal" },
  { reasoningEffort: "low" },
  { reasoningEffort: "medium" },
  { reasoningEffort: "high" },
  { reasoningEffort: "xhigh" },
  { reasoningEffort: "max" },
  { reasoningEffort: "ultra" }
];

function effortLabel(effort: string): string {
  const labels: Record<string, string> = {
    minimal: "Minimal",
    low: "Low",
    medium: "Medium",
    high: "High",
    xhigh: "Extra High",
    max: "Maximum",
    ultra: "Ultra"
  };
  return labels[effort] || effort;
}

export function compactPath(value: string): string {
  const normalized = value.replace(/\\/g, "/").replace(/\/+$/, "");
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length <= 2) return normalized;
  return `…/${parts.slice(-2).join("/")}`;
}

function contextGlyph(kind: ResearchContextKind): string {
  const glyphs: Record<ResearchContextKind, string> = {
    paper: "P",
    page: "§",
    selection: "“",
    annotation: "✦",
    library: "⌘",
    collection: "#",
    "external-paper": "P",
    screenshot: "▣",
    draft: "D",
  };
  return glyphs[kind];
}

function contextKindLabel(kind: ResearchContextKind): string {
  const labels: Record<ResearchContextKind, string> = {
    paper: "Paper",
    page: "PDF Page",
    selection: "Reader Selection",
    annotation: "Zotero Annotation",
    library: "Library",
    collection: "Collection",
    "external-paper": "Other Paper",
    screenshot: "Screenshot",
    draft: "Draft",
  };
  return labels[kind];
}

function formatDateTime(value: string | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function reconcileChildren(parent: HTMLElement, desired: readonly HTMLElement[]): void {
  let cursor: ChildNode | null = parent.firstChild;
  for (const node of desired) {
    if (node === cursor) {
      cursor = cursor.nextSibling;
      continue;
    }
    parent.insertBefore(node, cursor);
  }
  while (cursor) {
    const next = cursor.nextSibling;
    cursor.remove();
    cursor = next;
  }
}
