import { renderMarkdown, type PdfPageReference } from "./markdown";
import { renderModelOptions } from "./model-menu";
import { copyToClipboard } from "./platform";
import { QLAB_COMMANDS, type QLabCommandID } from "./qlab-commands";
import {
  appendUserMessage,
  createSidebarIcon,
  compactPath,
  type ChatEntry,
  type ModelOption,
  type SidebarPhase,
} from "./sidebar";
import {
  activityLabel,
  contentEntries,
  formatElapsed,
  groupEntries,
  processEntries,
  type Exchange,
} from "./exchanges";

export interface FloatSelectionInfo {
  text: string;
  pageNumber?: number;
}

export interface FloatPanelState {
  phase: SidebarPhase;
  running: boolean;
  error?: string;
  entries: ChatEntry[];
  paperTitle: string;
  selection: FloatSelectionInfo | null;
  models: ModelOption[];
  selectedModel: string;
  turnStartedAt: number | null;
  turnDurations: Record<string, number>;
  opacity: number;
  anchorConfirmation: { anchorId: string; pageNumber?: number } | null;
  canResolveAnchor: boolean;
  paperTrailConsent: { question: string; pageNumber?: number } | null;
  qlabRoot: string;
  /** Feature flags for the active backend; an absent flag defaults to `true`. */
  capabilities?: { supportsAgentMode: boolean; supportsLogin: boolean };
}

export interface FloatPanelCallbacks {
  onSend(text: string): void;
  onStop(): void;
  onClose(): void;
  onRemoveSelection(): void;
  onLogin(): void;
  onModelChange(model: string): void;
  onOpacityChange(value: number): void;
  onPanelResize(width: number, height: number): void;
  onUndoAnchor(anchorId: string): void;
  onMarkUnderstood(): void;
  onPaperTrailConsent(decision: "accept" | "decline"): void;
  onChooseQLabRoot(): void;
  onQLabCommand(command: QLabCommandID): void;
  onCaptureChatDraft(): void;
  onOpenWorkbench(): void;
  canOpenPdfPage?(reference: PdfPageReference): boolean;
  onOpenPdfPage?(reference: PdfPageReference): void;
}

export interface FloatPanelOptions {
  surface?: "float" | "workbench";
}

/** Joins an inline width/height style pair into a single comparable key. */
function inlineSizeKey(width: string, height: string): string {
  return `${width}|${height}`;
}

/** Entries belonging to the latest question: from the last user entry onward. */
export function latestExchange(entries: ChatEntry[]): ChatEntry[] {
  for (let index = entries.length - 1; index >= 0; index--) {
    if (entries[index]!.kind === "user") return entries.slice(index);
  }
  return [];
}

export class FloatPanelView {
  private readonly doc: Document;
  private readonly root: HTMLElement;
  private bar!: HTMLElement;
  private title!: HTMLElement;
  private qlabRootLabel!: HTMLElement;
  private qlabCommandButtons: HTMLButtonElement[] = [];
  private alphaSlider!: HTMLInputElement;
  private chip!: HTMLElement;
  private chipLabel!: HTMLElement;
  private anchorChip!: HTMLElement;
  private anchorChipLabel!: HTMLElement;
  private understoodButton!: HTMLButtonElement;
  private consentBlock!: HTMLElement;
  private consentText!: HTMLElement;
  private textarea!: HTMLTextAreaElement;
  private sendButton!: HTMLButtonElement;
  private stopButton!: HTMLButtonElement;
  private modelSelect!: HTMLSelectElement;
  private note!: HTMLElement;
  private transcript!: HTMLElement;
  private state: FloatPanelState = {
    phase: "connecting",
    running: false,
    entries: [],
    paperTitle: "Paper Assistant",
    selection: null,
    models: [],
    selectedModel: "",
    turnStartedAt: null,
    turnDurations: {},
    opacity: 100,
    anchorConfirmation: null,
    canResolveAnchor: false,
    paperTrailConsent: null,
    qlabRoot: "",
  };
  private position: { left: number; top: number } | null = null;
  private readonly expandedTurns = new Set<string>();
  private readonly expandedUserMessages = new Set<string>();
  private activityTimer: number | null = null;
  private activityNode: HTMLElement | null = null;
  private activityLabelEl: HTMLElement | null = null;
  private activityElapsedEl: HTMLElement | null = null;
  private pinnedToBottom = true;
  private resizeObserver: ResizeObserver | null = null;
  private resizeDebounceTimer: number | null = null;
  /**
   * Snapshot of the panel's own inline `style.width`+`style.height` pair.
   * Gecko's native `resize: both` grip writes those inline styles directly
   * on the element when the user drags the corner; a window resize (or any
   * other reflow of the CSS `min()`/`max()` bounds) never touches them.
   * Comparing the current inline pair against this snapshot -- instead of
   * just skipping the ResizeObserver's first callback -- is what lets a real
   * user resize be told apart from incidental reflow.
   */
  private lastInlineSize = inlineSizeKey("", "");
  /**
   * The last known-good inline height, from a persisted restore or a user
   * drag. Reapplied once the transcript regains entries after its height was
   * cleared for the empty state (see `applyHeightForEmptyState`).
   */
  private persistedHeight: string | null = null;
  /**
   * The in-flight value while the opacity slider is being dragged. `input`
   * fires continuously and only previews locally; `state.opacity` stays
   * stale until the settled `change` callback round-trips through the
   * plugin. Renders fire constantly via `onState` in between, and without
   * tracking this separately `renderOpacity` would reset the slider (and
   * its live preview) to that stale value mid-drag -- a visible jump while
   * the user is still holding the thumb. Cleared once `change` fires.
   */
  private pendingOpacity: number | null = null;
  private readonly surface: "float" | "workbench";
  /**
   * True only while the panel's current inline height was put there by
   * `restoreSize()` and has not since been superseded by a genuine grip
   * drag. `applyHeightForEmptyState` may only clear a height while this flag
   * is set -- otherwise a user who drags the resize grip on a freshly empty
   * panel would have that live resize silently reverted by the next
   * unrelated render. Cleared the moment `handlePanelResize` sees a real
   * grip-driven inline change, so a grip resize made while empty is never
   * mistaken for a restore.
   */
  private restoredHeightPending = false;
  private readonly handleResize = () => {
    if (this.root.hidden) return;
    if (this.position) this.applyPosition(this.position.left, this.position.top);
  };

  constructor(
    host: HTMLElement,
    private readonly callbacks: FloatPanelCallbacks,
    options: FloatPanelOptions = {},
  ) {
    this.surface = options.surface || "float";
    this.doc = host.ownerDocument;
    this.root = this.doc.createElement("section");
    this.root.className = this.surface === "workbench"
      ? "zc-float zc-workbench-tab-content"
      : "zc-float zc-chat-float";
    this.root.hidden = true;
    this.root.setAttribute("role", this.surface === "workbench" ? "main" : "dialog");
    this.root.setAttribute("aria-label", this.surface === "workbench" ? "QLab Workbench" : "QLab Compact Chat");
    host.replaceChildren(this.root);
    this.build();
    this.render();
    if (this.surface === "float") this.doc.defaultView?.addEventListener("resize", this.handleResize);
    if (this.surface === "float" && typeof ResizeObserver !== "undefined") {
      this.resizeObserver = new ResizeObserver((entries) => this.handlePanelResize(entries));
      this.resizeObserver.observe(this.root);
    }
  }

  destroy(): void {
    if (this.activityTimer !== null) {
      this.doc.defaultView?.clearInterval(this.activityTimer);
      this.activityTimer = null;
    }
    if (this.surface === "float") this.doc.defaultView?.removeEventListener("resize", this.handleResize);
    if (this.resizeDebounceTimer !== null) {
      this.doc.defaultView?.clearTimeout(this.resizeDebounceTimer);
      this.resizeDebounceTimer = null;
    }
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.root.remove();
  }

  /** Applies a previously persisted lightweight panel size (`floatSize` pref). */
  restoreSize(width: number, height: number): void {
    if (this.surface !== "float") return;
    this.root.style.width = `${width}px`;
    this.root.style.height = `${height}px`;
    this.persistedHeight = this.root.style.height;
    this.lastInlineSize = this.currentInlineSize();
    this.restoredHeightPending = true;
  }

  private currentInlineSize(): string {
    return inlineSizeKey(this.root.style.width, this.root.style.height);
  }

  /**
   * Gecko's native `resize: both` grip writes inline `style.width`/
   * `style.height` directly on the panel when the user drags the corner.
   * Window-driven responsive reflow (the CSS `min()`/`max()` bounds
   * recomputing against the viewport) changes the observed content box too,
   * but never touches those inline properties. Only a change in the inline
   * pair -- never a bare content-box change -- is treated as a user resize
   * and persisted.
   */
  private handlePanelResize(entries: ResizeObserverEntry[]): void {
    const entry = entries[0];
    if (!entry) return;
    const inlineSize = this.currentInlineSize();
    if (inlineSize === this.lastInlineSize) return;
    this.lastInlineSize = inlineSize;
    // A genuine grip-driven inline change supersedes any pending restored
    // height: from now on this height is the user's own, and must never be
    // cleared just because the transcript happens to be empty.
    this.restoredHeightPending = false;
    const width = Math.round(entry.contentRect.width);
    const height = Math.round(entry.contentRect.height);
    const win = this.doc.defaultView;
    if (this.resizeDebounceTimer !== null) win?.clearTimeout(this.resizeDebounceTimer);
    this.resizeDebounceTimer = win?.setTimeout(() => {
      this.resizeDebounceTimer = null;
      this.callbacks.onPanelResize(width, height);
    }, 500) ?? null;
  }

  setState(next: Partial<FloatPanelState>): void {
    this.state = { ...this.state, ...next };
    this.render();
  }

  show(): void {
    this.pinnedToBottom = true;
    this.root.hidden = false;
    if (this.surface === "float" && this.position) this.applyPosition(this.position.left, this.position.top);
  }

  hide(): void {
    this.root.hidden = true;
  }

  isVisible(): boolean {
    return !this.root.hidden;
  }

  focusComposer(text?: string): void {
    if (text !== undefined) {
      const prefix = this.textarea.value.trim() ? `${this.textarea.value.trim()}\n\n` : "";
      this.textarea.value = prefix + text;
      this.autoSize();
    }
    this.textarea.focus();
  }

  private build(): void {
    this.bar = this.doc.createElement("header");
    this.bar.className = "zc-float-bar";
    if (this.surface === "float") {
      this.bar.addEventListener("mousedown", (event) => this.beginDrag(event));
    }
    const grip = this.doc.createElement("span");
    grip.className = "zc-float-grip";
    grip.setAttribute("aria-hidden", "true");
    grip.hidden = this.surface !== "float";
    this.title = this.doc.createElement("span");
    this.title.className = "zc-float-title";
    this.alphaSlider = this.doc.createElement("input");
    this.alphaSlider.type = "range";
    this.alphaSlider.className = "zc-float-alpha";
    this.alphaSlider.min = "60";
    this.alphaSlider.max = "100";
    this.alphaSlider.step = "5";
    this.alphaSlider.title = "Background Opacity";
    this.alphaSlider.setAttribute("aria-label", this.alphaSlider.title);
    this.alphaSlider.hidden = this.surface !== "float";
    // `input` fires continuously while dragging: only preview it locally (no
    // callback into the plugin, which would re-render every listening view
    // on every tick) and forward the settled value to the plugin on `change`.
    this.alphaSlider.addEventListener("input", () => {
      this.pendingOpacity = Number(this.alphaSlider.value);
      this.root.style.setProperty("--zc-float-alpha", String(this.pendingOpacity / 100));
    });
    this.alphaSlider.addEventListener("change", () => {
      this.callbacks.onOpacityChange(Number(this.alphaSlider.value));
      this.pendingOpacity = null;
    });
    const close = this.doc.createElement("button");
    close.type = "button";
    close.className = "zc-float-close";
    close.title = "Close (Esc)";
    close.setAttribute("aria-label", close.title);
    close.replaceChildren(createSidebarIcon(this.doc, "close"));
    close.addEventListener("click", () => this.callbacks.onClose());
    close.hidden = this.surface !== "float";
    const openWorkbench = this.doc.createElement("button");
    openWorkbench.type = "button";
    openWorkbench.className = "zc-float-open-workbench";
    openWorkbench.textContent = "Open in Tab";
    openWorkbench.title = "Open the full QLab Workbench in a Zotero tab";
    openWorkbench.hidden = this.surface !== "float";
    openWorkbench.addEventListener("click", () => this.callbacks.onOpenWorkbench());
    this.bar.append(grip, this.title);
    if (this.surface === "float") this.bar.append(openWorkbench, this.alphaSlider, close);

    const tools = this.doc.createElement("section");
    tools.className = "zc-workbench-tools";
    tools.hidden = this.surface !== "workbench";
    const toolsHeader = this.doc.createElement("header");
    toolsHeader.className = "zc-workbench-tools-header";
    const repository = this.doc.createElement("button");
    repository.type = "button";
    repository.className = "zc-workbench-root";
    repository.title = "Choose QLab Repository";
    const repositoryMark = this.doc.createElement("strong");
    repositoryMark.textContent = "QLab Repository";
    this.qlabRootLabel = this.doc.createElement("span");
    repository.append(repositoryMark, this.qlabRootLabel);
    repository.addEventListener("click", () => this.callbacks.onChooseQLabRoot());
    toolsHeader.append(repository);
    const commandGrid = this.doc.createElement("div");
    commandGrid.className = "zc-workbench-command-grid";
    for (const command of QLAB_COMMANDS) {
      const button = this.doc.createElement("button");
      button.type = "button";
      button.className = "zc-workbench-command";
      button.dataset.commandId = command.id;
      const label = this.doc.createElement("strong");
      label.textContent = command.label;
      const description = this.doc.createElement("span");
      description.textContent = command.description;
      button.append(label, description);
      button.addEventListener("click", () => this.callbacks.onQLabCommand(command.id));
      this.qlabCommandButtons.push(button);
      commandGrid.appendChild(button);
    }
    tools.append(toolsHeader, commandGrid);

    this.chip = this.doc.createElement("div");
    this.chip.className = "zc-float-chip";
    this.chip.hidden = true;
    const glyph = this.doc.createElement("span");
    glyph.className = "zc-float-chip-glyph";
    glyph.textContent = "“";
    glyph.setAttribute("aria-hidden", "true");
    this.chipLabel = this.doc.createElement("span");
    this.chipLabel.className = "zc-float-chip-label";
    const remove = this.doc.createElement("button");
    remove.type = "button";
    remove.className = "zc-float-chip-remove";
    remove.title = "Remove selection context";
    remove.setAttribute("aria-label", remove.title);
    remove.replaceChildren(createSidebarIcon(this.doc, "close"));
    remove.addEventListener("click", () => this.callbacks.onRemoveSelection());
    this.chip.append(glyph, this.chipLabel, remove);

    this.anchorChip = this.doc.createElement("div");
    this.anchorChip.className = "zc-float-chip zc-float-anchor-chip";
    this.anchorChip.hidden = true;
    const anchorGlyph = this.doc.createElement("span");
    anchorGlyph.className = "zc-float-chip-glyph";
    anchorGlyph.textContent = "✓";
    anchorGlyph.setAttribute("aria-hidden", "true");
    this.anchorChipLabel = this.doc.createElement("span");
    this.anchorChipLabel.className = "zc-float-chip-label";
    const undo = this.doc.createElement("button");
    undo.type = "button";
    undo.className = "zc-float-chip-undo";
    undo.textContent = "Undo";
    undo.title = "Undo Highlight Annotation";
    undo.setAttribute("aria-label", undo.title);
    undo.addEventListener("click", () => {
      const anchorId = this.state.anchorConfirmation?.anchorId;
      if (anchorId) this.callbacks.onUndoAnchor(anchorId);
    });
    this.anchorChip.append(anchorGlyph, this.anchorChipLabel, undo);

    this.understoodButton = this.doc.createElement("button");
    this.understoodButton.type = "button";
    this.understoodButton.className = "zc-float-understood";
    this.understoodButton.textContent = "Understood ✓";
    this.understoodButton.hidden = true;
    this.understoodButton.addEventListener("click", () => this.callbacks.onMarkUnderstood());

    this.consentBlock = this.doc.createElement("div");
    this.consentBlock.className = "zc-float-consent";
    this.consentBlock.hidden = true;
    this.consentText = this.doc.createElement("span");
    this.consentText.className = "zc-float-consent-text";
    const consentActions = this.doc.createElement("div");
    consentActions.className = "zc-float-consent-actions";
    const consentDecline = this.doc.createElement("button");
    consentDecline.type = "button";
    consentDecline.className = "zc-float-consent-decline";
    consentDecline.textContent = "Do Not Annotate";
    consentDecline.addEventListener("click", () => this.callbacks.onPaperTrailConsent("decline"));
    const consentAccept = this.doc.createElement("button");
    consentAccept.type = "button";
    consentAccept.className = "zc-float-consent-accept";
    consentAccept.textContent = "Allow";
    consentAccept.addEventListener("click", () => this.callbacks.onPaperTrailConsent("accept"));
    consentActions.append(consentDecline, consentAccept);
    this.consentBlock.append(this.consentText, consentActions);

    const composer = this.doc.createElement("div");
    composer.className = "zc-float-composer";
    this.textarea = this.doc.createElement("textarea");
    this.textarea.className = "zc-float-input";
    this.textarea.rows = 1;
    this.textarea.placeholder = "Ask about this paper…";
    this.textarea.addEventListener("input", () => this.autoSize());
    this.textarea.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        this.submit();
      }
    });
    this.sendButton = this.doc.createElement("button");
    this.sendButton.type = "button";
    this.sendButton.className = "zc-float-send";
    this.sendButton.title = "Send";
    this.sendButton.setAttribute("aria-label", this.sendButton.title);
    this.sendButton.replaceChildren(createSidebarIcon(this.doc, "send"));
    this.sendButton.addEventListener("click", () => this.submit());
    this.stopButton = this.doc.createElement("button");
    this.stopButton.type = "button";
    this.stopButton.className = "zc-float-stop";
    this.stopButton.title = "Stop Generating";
    this.stopButton.setAttribute("aria-label", this.stopButton.title);
    this.stopButton.replaceChildren(createSidebarIcon(this.doc, "stop"));
    this.stopButton.addEventListener("click", () => this.callbacks.onStop());
    this.modelSelect = this.doc.createElement("select");
    this.modelSelect.className = "zc-float-model";
    this.modelSelect.title = "Model";
    this.modelSelect.hidden = true;
    this.modelSelect.addEventListener("change", () => {
      this.callbacks.onModelChange(this.modelSelect.value);
    });
    composer.append(this.textarea, this.stopButton, this.sendButton, this.modelSelect);

    this.note = this.doc.createElement("div");
    this.note.className = "zc-float-note";

    this.transcript = this.doc.createElement("main");
    this.transcript.className = "zc-float-transcript";
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

    this.root.addEventListener("keydown", (event) => {
      if (this.surface !== "float") return;
      if (event.isComposing) return;
      if (event.key === "Escape") {
        event.preventDefault();
        this.callbacks.onClose();
        return;
      }
      if (
        event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey
        && event.key.toLowerCase() === "k"
      ) {
        event.preventDefault();
        event.stopPropagation();
        this.callbacks.onClose();
      }
    });

    this.root.append(this.bar);
    if (this.surface === "workbench") this.root.append(tools);
    this.root.append(
      this.chip, this.anchorChip, this.understoodButton, this.consentBlock,
      this.transcript, composer, this.note,
    );
  }

  private render(): void {
    this.title.textContent = this.surface === "workbench"
      ? `QLab Workbench · ${this.state.paperTitle || "Paper Assistant"}`
      : `QLab · ${this.state.paperTitle || "Paper Assistant"}`;
    if (this.surface === "workbench") this.renderQLabTools();
    this.renderChip();
    this.renderAnchorChip();
    this.renderUnderstoodButton();
    this.renderConsent();
    this.textarea.disabled = this.state.phase !== "ready";
    this.stopButton.hidden = !this.state.running;
    this.stopButton.style.display = this.state.running ? "grid" : "none";
    this.renderModels();
    this.renderNote();
    this.renderTranscript();
    if (this.surface === "float") {
      this.applyHeightForEmptyState();
      this.renderOpacity();
    }
  }

  private renderQLabTools(): void {
    this.qlabRootLabel.textContent = this.state.qlabRoot
      ? compactPath(this.state.qlabRoot)
      : "Choose repository…";
    this.qlabRootLabel.title = this.state.qlabRoot || "QLab repository is not configured";
    for (const button of this.qlabCommandButtons) {
      button.disabled = !this.state.qlabRoot || this.state.phase !== "ready";
    }
  }

  /**
   * A tall persisted/restored height next to an empty transcript (a fresh
   * thread, or one that was just cleared) leaves a mostly-empty panel
   * towering over the composer. Clear the inline height while there's
   * nothing to show, remembering it so it comes back once the transcript
   * has entries again. The width is never touched either way, and the
   * ResizeObserver snapshot is kept in sync so this bookkeeping is never
   * mistaken for a user resize.
   *
   * Only a height that came from `restoreSize()` (tracked by
   * `restoredHeightPending`) is eligible to be cleared here. Renders fire
   * constantly via `onState`, so without that guard a user who drags the
   * resize grip on a freshly empty panel would have their live resize
   * silently reverted by the very next unrelated render.
   */
  private applyHeightForEmptyState(): void {
    const hasEntries = this.state.entries.length > 0;
    if (!hasEntries) {
      if (!this.restoredHeightPending || this.root.style.height === "") return;
      this.persistedHeight = this.root.style.height;
      this.root.style.height = "";
      this.lastInlineSize = this.currentInlineSize();
      return;
    }
    if (this.root.style.height === "" && this.persistedHeight) {
      this.root.style.height = this.persistedHeight;
      this.lastInlineSize = this.currentInlineSize();
    }
  }

  private renderOpacity(): void {
    const opacity = this.pendingOpacity ?? this.state.opacity;
    if (this.alphaSlider.value !== String(opacity)) this.alphaSlider.value = String(opacity);
    this.root.style.setProperty("--zc-float-alpha", String(opacity / 100));
  }

  private renderModels(): void {
    const models = this.state.models;
    this.modelSelect.hidden = models.length === 0;
    if (!models.length) {
      this.modelSelect.replaceChildren();
      return;
    }
    const previous = this.modelSelect.value;
    renderModelOptions(this.modelSelect, models, this.state.selectedModel || previous || models[0]!.id);
  }

  private renderChip(): void {
    const selection = this.state.selection;
    this.chip.hidden = !selection;
    if (!selection) return;
    this.chipLabel.textContent = selection.pageNumber
      ? `Selected ${selection.text.length} characters · page ${selection.pageNumber}`
      : `Selected ${selection.text.length} characters`;
  }

  private renderAnchorChip(): void {
    const confirmation = this.state.anchorConfirmation;
    this.anchorChip.hidden = !confirmation;
    if (!confirmation) return;
    this.anchorChipLabel.textContent = confirmation.pageNumber
      ? `Trail saved · page ${confirmation.pageNumber}`
      : "Trail saved";
  }

  private renderUnderstoodButton(): void {
    this.understoodButton.hidden = !this.state.canResolveAnchor;
  }

  private renderConsent(): void {
    const consent = this.state.paperTrailConsent;
    this.consentBlock.hidden = !consent;
    if (!consent) return;
    this.consentText.textContent = "QLab will create a highlight annotation at the question location";
  }

  private renderNote(): void {
    this.note.replaceChildren();
    this.note.hidden = false;
    this.note.classList.toggle("is-error", Boolean(this.state.error));
    if (this.state.phase === "connecting") {
      this.note.textContent = "Connecting to Codex…";
      return;
    }
    if (this.state.phase === "signed-out") {
      const text = this.doc.createElement("span");
      text.textContent = "Sign in with ChatGPT to ask questions.";
      this.note.appendChild(text);
      if (this.state.capabilities?.supportsLogin !== false) {
        const login = this.doc.createElement("button");
        login.type = "button";
        login.className = "zc-float-login";
        login.textContent = "Sign In with ChatGPT";
        login.addEventListener("click", () => this.callbacks.onLogin());
        this.note.appendChild(login);
      }
      return;
    }
    if (this.state.error) {
      this.note.textContent = this.state.error;
      return;
    }
    this.note.textContent = this.state.running ? "Agent is working · Enter sends a follow-up" : "";
    this.note.hidden = !this.note.textContent;
  }

  private renderTranscript(): void {
    this.transcript.replaceChildren();
    this.transcript.hidden = this.state.entries.length === 0;

    let activityGroup: Exchange | null = null;
    const groups = groupEntries(this.state.entries);
    groups.forEach((group, index) => {
      for (const entry of contentEntries(group)) {
        this.transcript.appendChild(this.renderEntry(entry));
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
      this.transcript.appendChild(this.renderTurnSummary(group, steps, elapsed));
      if (this.expandedTurns.has(group.id)) {
        this.transcript.appendChild(this.renderTurnDetail(processEntries(group)));
      }
    });
    const groupIds = new Set(groups.map((group) => group.id));
    for (const id of this.expandedTurns) {
      if (!groupIds.has(id)) this.expandedTurns.delete(id);
    }
    if (activityGroup) this.transcript.appendChild(this.renderActivityLine(activityGroup));

    if (this.pinnedToBottom) {
      this.transcript.scrollTop = this.transcript.scrollHeight;
    }
    this.syncActivityTimer();
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
   * node's lifetime. `renderTranscript` wipes and rebuilds the whole
   * transcript on every render, so a freshly created node here would reset
   * those animations to frame 0 on each of the ~20/s streaming renders. This
   * node is created once and reused across renders (only its label/elapsed
   * text is patched in place) so the same element re-enters the transcript
   * each time instead of a brand-new one.
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

  private renderEntry(entry: ChatEntry): HTMLElement {
    const article = this.doc.createElement("article");
    article.className = `zc-float-entry zc-entry-${entry.kind}`;
    article.dataset.entryId = entry.id;
    if (entry.kind === "user") {
      appendUserMessage(this.doc, article, entry, this.expandedUserMessages);
      return article;
    }
    if (entry.kind === "tool" || entry.kind === "command" || entry.kind === "reasoning") {
      const details = this.doc.createElement("details");
      details.className = "zc-tool-card";
      const summary = this.doc.createElement("summary");
      summary.textContent = entry.title || (entry.kind === "reasoning" ? "Reasoning" : "Tool");
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
    const content = this.doc.createElement("div");
    content.className = "zc-entry-content";
    const markdownBody = this.doc.createElement("div");
    markdownBody.className = "zc-markdown";
    markdownBody.appendChild(renderMarkdown(this.doc, entry.text, this.markdownOptions()));
    content.appendChild(markdownBody);
    if (entry.kind === "assistant") {
      content.appendChild(this.createCopyAnswerButton(entry.text));
    }
    article.appendChild(content);
    return article;
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

  private submit(): void {
    const text = this.textarea.value.trim();
    if (!text || this.state.phase !== "ready") return;
    this.textarea.value = "";
    this.autoSize();
    this.callbacks.onSend(text);
  }

  private autoSize(): void {
    this.textarea.style.height = "auto";
    this.textarea.style.height = `${Math.min(this.textarea.scrollHeight, 120)}px`;
  }

  private beginDrag(event: MouseEvent): void {
    if ((event.target as Element | null)?.closest?.(".zc-float-close, .zc-float-alpha")) return;
    if (event.button !== 0) return;
    const rect = this.root.getBoundingClientRect();
    const offsetX = event.clientX - rect.left;
    const offsetY = event.clientY - rect.top;
    const onMove = (move: MouseEvent) => {
      this.root.classList.add("is-dragged");
      this.applyPosition(move.clientX - offsetX, move.clientY - offsetY);
    };
    const onUp = () => {
      this.doc.removeEventListener("mousemove", onMove, true);
      this.doc.removeEventListener("mouseup", onUp, true);
    };
    this.doc.addEventListener("mousemove", onMove, true);
    this.doc.addEventListener("mouseup", onUp, true);
    event.preventDefault();
  }

  private applyPosition(left: number, top: number): void {
    const win = this.doc.defaultView;
    if (!win) return;
    const margin = 8;
    const maxLeft = Math.max(margin, win.innerWidth - this.root.offsetWidth - margin);
    const maxTop = Math.max(margin, win.innerHeight - this.root.offsetHeight - margin);
    this.position = {
      left: Math.min(Math.max(left, margin), maxLeft),
      top: Math.min(Math.max(top, margin), maxTop),
    };
    this.root.style.left = `${this.position.left}px`;
    this.root.style.top = `${this.position.top}px`;
  }
}
