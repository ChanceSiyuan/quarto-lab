import { EDITOR_TREES, treeForPath, type EditorTree } from "./editor-tree";
import { externalEditorIconUrl, type ExternalEditorApp } from "./external-editor";
import {
  QMD_INLINE_CONFIGURE_TOPIC,
  QMD_INLINE_CONFIGURED_TOPIC,
  QMD_INLINE_EDIT_TOPIC,
  QMD_INLINE_READY_TOPIC,
  QMD_INLINE_RESULT_TOPIC,
  qmdInlineFrameScript,
  type QmdEditableBlock,
  type QmdInlineConfiguredMessage,
  type QmdInlineEditMessage,
  type QmdInlineResultMessage,
} from "./qmd-inline-edit";
import { filterQmdIndex, groupIntoTree, type QmdIndexEntry, type QmdTreeNode } from "./qmd-index";
import type { QmdRenderService } from "./qmd-render";

export interface QmdPreparedChange {
  changePath: string;
  previewPath: string;
  changed: boolean;
  /** Content fingerprint of the one latest cumulative AI version. */
  revision: string;
}

export interface QmdWorkspaceOptions {
  onBack(): void;
  renderService: Pick<QmdRenderService, "open" | "stop" | "diagnostic" | "checkDraft">;
  changeRenderService: Pick<QmdRenderService, "open" | "stop" | "diagnostic">;
  /** Every previewable QMD in the repository. */
  index(): Promise<QmdIndexEntry[]>;
  /** The editors installed on this machine, best first. */
  editors(): Promise<ExternalEditorApp[]>;
  /** Hands one file to an external editor, with the repository as workspace. */
  openExternally(editor: ExternalEditorApp, relativePath: string): Promise<void>;
  /** Remembers which editor was used last. */
  onEditorChosen?(editorId: string): void;
  /** Tells the assistant which file is visible and which private copy it may edit. */
  onActiveDocument?(relativePath: string | null, changePath?: string | null): void;
  /** Starts the Add-to-Knowledge workflow; its first Agent turn is review-only. */
  onReviewDraft?(relativePath: string): Promise<void> | void;
  /** Creates or resumes the private Agent working copy without touching the Draft. */
  prepareChange?(relativePath: string): Promise<QmdPreparedChange>;
  /** Mirrors the private working copy into a renderer-only file beside the Draft. */
  refreshChangePreview?(relativePath: string, changePath: string, previewPath: string): Promise<void>;
  /** Replaces the Draft with its reviewed copy after adopting direct editor saves as the new baseline. */
  keepChange?(relativePath: string, changePath: string): Promise<QmdPreparedChange>;
  /** Editable source regions mapped from one QMD to its compiled HTML. */
  editableBlocks?(relativePath: string): Promise<QmdEditableBlock[]>;
  /** Atomically saves one in-preview human edit to the original Draft. */
  applyManualEdit?(
    relativePath: string,
    block: QmdEditableBlock,
    text: string,
  ): Promise<QmdPreparedChange>;
}

interface QmdRemoteMessage {
  data?: unknown;
}

interface QmdRemoteMessageManager {
  loadFrameScript(uri: string, allowDelayedLoad: boolean): void;
  addMessageListener(topic: string, listener: (message: QmdRemoteMessage) => void): void;
  removeMessageListener(topic: string, listener: (message: QmdRemoteMessage) => void): void;
  sendAsyncMessage(topic: string, data: unknown): void;
}

export interface QmdAgentDiff {
  turnId: string;
  diff: string;
}

export interface QmdAgentState {
  activeTurnId: string | null;
  diffs: readonly QmdAgentDiff[];
}

function normalizedDiffPath(value: string): string {
  return value.trim().replace(/^['"]|['"]$/g, "").replace(/^[ab]\//, "");
}

/** Returns only the unified/custom-patch section that belongs to one QMD. */
export function qmdDiffForPath(diff: string, relativePath: string): string | null {
  const lines = diff.split(/\r?\n/);
  const selected: string[] = [];
  let active = false;
  let found = false;
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]!;
    const git = /^diff --git\s+(\S+)\s+(\S+)/.exec(line);
    const patch = /^\*\*\* (?:Update|Add|Delete) File:\s+(.+)$/.exec(line);
    if (git) {
      active = [git[1], git[2]].some((path) => normalizedDiffPath(path!) === relativePath);
      if (active) found = true;
    }
    else if (patch) {
      active = normalizedDiffPath(patch[1]!) === relativePath;
      if (active) found = true;
    }
    else if (line.startsWith("--- ") && index + 1 < lines.length && lines[index + 1]!.startsWith("+++ ")) {
      const before = normalizedDiffPath(line.slice(4).split("\t", 1)[0]!);
      const after = normalizedDiffPath(lines[index + 1]!.slice(4).split("\t", 1)[0]!);
      active = before === relativePath || after === relativePath;
      if (active) found = true;
    }
    if (active) selected.push(line);
  }
  return found ? selected.join("\n").trim() : null;
}

/**
 * The QMD preview workspace.
 *
 * It keeps the compiled Quarto page as the default reading surface. A toolbar
 * button explicitly switches that same page into inline edit mode: plain prose
 * edits in place, formulas expose only their LaTeX, and rich Markdown or a
 * complete thm/lem/def block temporarily exposes its QMD source. Human preview
 * edits save to the original Draft,
 * just like Cursor; Agent edits remain in the private working copy. The eye
 * switches between the compiled original and working copy, and Keep is the
 * only promotion from the Agent copy back to the user's Draft. Cursor and VS
 * Code remain available for full-document source work.
 *
 * Both trees are previewable. `drafts/` is rendered as a single file and stays
 * out of the published site, which is the whole reason it has no URL to reach
 * it by and needs this list to be reachable at all.
 */
export class QmdWorkspaceView {
  readonly root: HTMLElement;
  /** Set by the host before opening: the render process needs a directory. */
  repoRootHint = "";

  private readonly doc: Document;
  private readonly pathLabel: HTMLElement;
  private readonly treeBadge: HTMLElement;
  private readonly complianceButton: HTMLButtonElement;
  private readonly reviewButton: HTMLButtonElement;
  private readonly complianceDetails: HTMLElement;
  private readonly editButton: HTMLButtonElement;
  private readonly editorPicker: HTMLSelectElement;
  private readonly status: HTMLElement;
  private readonly fileColumn: HTMLElement;
  private readonly fileToggle: HTMLButtonElement;
  private readonly renderPane: HTMLElement;
  private readonly compareButton: HTMLButtonElement;
  private readonly keepChangesButton: HTMLButtonElement;
  private readonly editPreviewButton: HTMLButtonElement;
  private readonly quickOpen: HTMLElement;
  private readonly quickOpenInput: HTMLInputElement;
  private readonly quickOpenList: HTMLElement;

  private renderBrowser: HTMLElement | null = null;
  private inlineMessageManager: QmdRemoteMessageManager | null = null;
  private readonly inlineBlocks = new Map<string, QmdEditableBlock>();
  private inlineSave: Promise<void> = Promise.resolve();
  private renderedUrl = "";
  private changedUrl = "";
  private changePath: string | null = null;
  private changePreviewPath: string | null = null;
  private changeRevision = "";
  private hasAgentChange = false;
  private showingAgentChange = false;
  private inlineEditingEnabled = false;
  private current: { relativePath: string; tree: EditorTree } | null = null;
  private entries: QmdIndexEntry[] = [];
  private available: ExternalEditorApp[] = [];
  private expanded = new Set<string>(["knowledge", "drafts"]);
  private destroyed = false;
  private openGeneration = 0;
  private complianceGeneration = 0;
  private readonly knownDiffs = new Map<string, string>();
  private readonly onInlineReadyMessage = (_message: QmdRemoteMessage): void => {
    void this.configureInlineEditing();
  };
  private readonly onInlineConfiguredMessage = (message: QmdRemoteMessage): void => {
    const data = message.data as Partial<QmdInlineConfiguredMessage> | undefined;
    if (!data?.enabled || !this.inlineEditingEnabled || this.showingAgentChange) return;
    const mapped = Number(data.mapped ?? 0);
    const total = Number(data.total ?? 0);
    if (mapped > 0) {
      this.setStatus(
        `Inline edit mode · ${mapped} editable regions ready · changes save on blur`,
        "valid",
      );
    }
    else {
      this.setStatus(
        `Inline edit mode could not map this compiled page (${mapped}/${total} regions)`,
        "error",
      );
    }
  };
  private readonly onInlineEditMessage = (message: QmdRemoteMessage): void => {
    const data = message.data as Partial<QmdInlineEditMessage> | undefined;
    if (!data || typeof data.id !== "string" || typeof data.text !== "string") return;
    const generation = this.openGeneration;
    this.inlineSave = this.inlineSave
      .then(() => this.applyInlineEdit({ id: data.id!, text: data.text! }, generation))
      .catch((error) => {
        if (generation !== this.openGeneration || this.destroyed) return;
        this.setStatus(error instanceof Error ? error.message : String(error), "error");
      });
  };

  constructor(host: HTMLElement, private readonly options: QmdWorkspaceOptions) {
    this.doc = host.ownerDocument;
    const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className: string) => {
      const element = this.doc.createElement(tag);
      element.className = className;
      return element;
    };

    this.root = make("section", "zc-qmd-workspace");
    this.root.hidden = true;
    this.root.setAttribute("aria-label", "QMD Preview");

    const toolbar = make("header", "zc-qmd-toolbar");
    const back = this.iconButton("zc-qmd-back", "←", "Back to AI", () => this.options.onBack());
    const quickOpenButton = this.iconButton(
      "zc-qmd-quickopen-button",
      "⌕",
      "Open a QMD (Cmd+P)",
      () => void this.openQuickOpen(),
    );
    this.pathLabel = make("strong", "zc-qmd-path");
    this.pathLabel.textContent = "No file open";
    this.treeBadge = make("span", "zc-qmd-tree-badge");

    this.complianceButton = this.iconButton("zc-qmd-compliance", "…", "Checking Draft…", () => {
      const expanded = this.complianceDetails.hidden;
      this.complianceDetails.hidden = !expanded;
      this.complianceButton.setAttribute("aria-expanded", String(expanded));
    });
    this.complianceButton.hidden = true;
    this.complianceButton.disabled = true;
    this.complianceButton.setAttribute("aria-expanded", "false");
    this.reviewButton = this.iconButton(
      "zc-qmd-review",
      "↑",
      "Add to Knowledge…",
      () => void this.reviewCurrentDraft(),
    );
    this.reviewButton.hidden = true;
    this.compareButton = this.iconButton(
      "zc-qmd-compare",
      "◉",
      "No AI version to compare",
      () => void this.toggleAgentPreview(),
    );
    this.compareButton.hidden = true;
    this.compareButton.disabled = true;
    this.compareButton.setAttribute("aria-pressed", "false");
    this.keepChangesButton = this.iconButton(
      "zc-qmd-change-keep",
      "⤓",
      "No AI changes to keep",
      () => void this.keepAgentChanges(),
    );
    this.keepChangesButton.hidden = true;
    this.keepChangesButton.disabled = true;
    this.editPreviewButton = this.iconButton(
      "zc-qmd-edit-preview",
      "✐",
      "Edit directly in Preview",
      () => void this.toggleInlineEditing(),
    );
    this.editPreviewButton.hidden = true;
    this.editPreviewButton.setAttribute("aria-pressed", "false");

    this.editorPicker = this.doc.createElement("select");
    this.editorPicker.className = "zc-qmd-editor-picker";
    this.editorPicker.title = "Choose an editor";
    this.editorPicker.hidden = true;
    this.editorPicker.addEventListener("change", () => {
      this.updateEditorLabel();
      this.options.onEditorChosen?.(this.editorPicker.value);
    });
    this.editButton = this.iconButton(
      "zc-qmd-edit-external",
      "✎",
      "Edit in External Editor",
      () => void this.openExternally(),
    );
    this.editButton.disabled = true;

    const refresh = this.iconButton("zc-qmd-refresh", "↻", "Refresh Preview", () => void this.reloadRender());
    toolbar.append(back, quickOpenButton, this.pathLabel, this.treeBadge,
      this.complianceButton, this.reviewButton, this.compareButton, this.keepChangesButton,
      this.editPreviewButton, this.editorPicker, this.editButton, refresh);

    this.status = make("div", "zc-qmd-status");
    this.status.textContent = "Choose a QMD page to preview";
    this.complianceDetails = make("div", "zc-qmd-compliance-details");
    this.complianceDetails.hidden = true;

    const body = make("div", "zc-qmd-body");
    this.fileColumn = make("nav", "zc-qmd-filecolumn");
    this.fileColumn.setAttribute("aria-label", "QMD Files");
    this.fileToggle = this.button("zc-qmd-file-toggle", "‹", () => this.toggleFileColumn());
    this.fileToggle.title = "Collapse File List";
    this.fileToggle.setAttribute("aria-label", "Collapse File List");
    this.fileToggle.setAttribute("aria-expanded", "true");
    this.renderPane = make("div", "zc-qmd-render");
    body.append(this.fileColumn, this.fileToggle, this.renderPane);

    this.quickOpen = make("div", "zc-qmd-quickopen");
    this.quickOpen.hidden = true;
    this.quickOpenInput = this.doc.createElement("input");
    this.quickOpenInput.className = "zc-qmd-quickopen-input";
    this.quickOpenInput.type = "text";
    this.quickOpenInput.placeholder = "Type a file name…";
    this.quickOpenInput.addEventListener("input", () => this.renderQuickOpen());
    this.quickOpenInput.addEventListener("keydown", (event) => this.onQuickOpenKey(event));
    this.quickOpenList = make("div", "zc-qmd-quickopen-list");
    this.quickOpen.append(this.quickOpenInput, this.quickOpenList);

    this.root.append(toolbar, this.status, this.complianceDetails, body, this.quickOpen);
    this.root.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "p") {
        event.preventDefault();
        void this.openQuickOpen();
      }
    });
    host.appendChild(this.root);
  }

  isVisible(): boolean {
    return !this.root.hidden;
  }

  show(): void {
    this.root.hidden = false;
    if (this.current) this.options.onActiveDocument?.(this.current.relativePath, this.changePath);
  }

  hide(): void {
    this.root.hidden = true;
    this.options.onActiveDocument?.(null);
  }

  /**
   * Connects app-server turn diffs to the Draft currently visible on the right.
   * Calls are serialized so the snapshot taken at turn start always precedes
   * the later diff notification, even when filesystem reads are asynchronous.
   */
  syncAgentChanges(state: QmdAgentState): void {
    const generation = this.openGeneration;
    const snapshot: QmdAgentState = {
      activeTurnId: state.activeTurnId,
      diffs: state.diffs.map((entry) => ({ ...entry })),
    };
    this.agentSync = this.agentSync
      .then(() => this.applyAgentState(snapshot, generation))
      .catch((error) => {
        if (generation !== this.openGeneration || this.destroyed) return;
        this.setStatus(error instanceof Error ? error.message : String(error), "error");
      });
  }

  /** Previews one QMD, starting or reusing its render process. */
  async open(relativePath: string): Promise<void> {
    const generation = ++this.openGeneration;
    this.disableInlineEditing();
    const tree = treeForPath(relativePath);
    if (!tree) {
      this.setStatus("Only QMD files in knowledge/ or drafts/ can be previewed", "error");
      return;
    }
    if (this.current?.relativePath !== relativePath) this.resetAgentChange();
    this.current = { relativePath, tree };
    this.pathLabel.textContent = relativePath;
    this.pathLabel.title = relativePath;
    this.treeBadge.textContent = tree.label;
    this.treeBadge.dataset.tree = tree.id;
    this.configureReviewControls(tree);

    let prepareError = "";
    if (!tree.published && this.options.prepareChange) {
      try {
        const prepared = await this.options.prepareChange(relativePath);
        if (generation !== this.openGeneration || this.destroyed) return;
        this.changePath = prepared.changePath;
        this.changePreviewPath = prepared.previewPath;
        this.hasAgentChange = prepared.changed;
        this.changeRevision = prepared.revision;
        this.setPendingEntry(relativePath, prepared.changed);
        this.updateChangeControls();
      }
      catch (error) {
        prepareError = error instanceof Error ? error.message : String(error);
        this.changePath = null;
        this.changePreviewPath = null;
        this.hasAgentChange = false;
        this.updateChangeControls();
      }
    }

    const draftCheck = tree.published
      ? Promise.resolve()
      : this.updateDraftCompliance(relativePath, generation);

    await this.refreshEditors();
    if (!this.entries.length) await this.refreshIndex();
    this.renderFileColumn();

    this.setStatus(
      tree.published ? "Rendering trusted Knowledge page…" : "Rendering draft (it will not be published)…",
      "checking",
    );
    let url: string;
    try {
      url = await this.options.renderService.open(tree, this.repoRootHint, relativePath);
    }
    catch (error) {
      if (generation !== this.openGeneration || this.destroyed) return;
      this.setStatus(error instanceof Error ? error.message : String(error), "error");
      return;
    }
    if (this.destroyed || generation !== this.openGeneration) return;
    if (!this.root.hidden) this.options.onActiveDocument?.(relativePath, this.changePath);

    this.ensureRenderBrowser();
    this.renderedUrl = url;
    this.showingAgentChange = false;
    this.showBrowserUrl(url, true);
    if (this.hasAgentChange) void this.ensureChangedPreview(generation);
    const diagnostic = this.options.renderService.diagnostic();
    this.setStatus(
      prepareError
        ? `${prepareError} The original Draft is read-only to the Agent until this is resolved.`
        : diagnostic
        ? `Preview is showing the last successful result: ${diagnostic}`
        : tree.published ? "Preview ready · refreshes automatically after save"
          : this.hasAgentChange ? "Website view · Original Draft preview · an AI version is available"
            : "Website view · Original Draft preview · AI edits are kept in a separate working copy",
      prepareError || diagnostic ? "error" : "valid",
    );
    await draftCheck;
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.openGeneration += 1;
    this.options.renderService.stop();
    this.options.changeRenderService.stop();
    this.detachInlineEditor();
    this.options.onActiveDocument?.(null);
    this.root.remove();
  }

  // -- internals ------------------------------------------------------------

  private agentSync: Promise<void> = Promise.resolve();

  private resetAgentChange(): void {
    this.knownDiffs.clear();
    this.options.changeRenderService.stop();
    this.changePath = null;
    this.changePreviewPath = null;
    this.changeRevision = "";
    this.changedUrl = "";
    this.hasAgentChange = false;
    this.showingAgentChange = false;
    this.inlineBlocks.clear();
    this.updateChangeControls();
  }

  private async applyAgentState(state: QmdAgentState, generation: number): Promise<void> {
    const current = this.current;
    const changePath = this.changePath;
    if (!current || current.tree.published || !changePath
        || generation !== this.openGeneration || this.destroyed) return;

    let diffChanged = false;
    for (const entry of state.diffs) {
      const previous = this.knownDiffs.get(entry.turnId);
      this.knownDiffs.set(entry.turnId, entry.diff);
      if (previous === entry.diff) continue;
      if (qmdDiffForPath(entry.diff, changePath)) diffChanged = true;
    }
    // The private working copy is intentionally Git-ignored, so some app-
    // server versions do not include it in workspace diffs. Its fingerprint
    // is the authoritative signal and also catches repeated edits in one turn.
    const prepared = await this.options.prepareChange?.(current.relativePath);
    if (generation !== this.openGeneration || this.destroyed) return;
    const revisionChanged = Boolean(prepared && prepared.revision !== this.changeRevision);
    if (prepared) {
      this.changePath = prepared.changePath;
      this.changePreviewPath = prepared.previewPath;
      this.changeRevision = prepared.revision;
      this.hasAgentChange = prepared.changed;
    }
    else if (diffChanged) {
      this.hasAgentChange = true;
    }
    if (!diffChanged && !revisionChanged) return;
    this.setPendingEntry(current.relativePath, true);
    this.renderFileColumn();
    this.updateChangeControls();
    await this.ensureChangedPreview(generation);
  }

  private async ensureChangedPreview(generation = this.openGeneration): Promise<string | null> {
    if (!this.current || this.current.tree.published || !this.changePath
        || !this.changePreviewPath || !this.hasAgentChange) return null;
    try {
      await this.options.refreshChangePreview?.(
        this.current.relativePath,
        this.changePath,
        this.changePreviewPath,
      );
      if (this.changedUrl) return this.changedUrl;
      const drafts = EDITOR_TREES.find((tree) => tree.id === "drafts")!;
      const url = await this.options.changeRenderService.open(
        drafts,
        this.repoRootHint,
        this.changePreviewPath,
      );
      if (generation !== this.openGeneration || this.destroyed) return null;
      this.changedUrl = url;
      this.updateChangeControls();
      if (this.showingAgentChange) this.showBrowserUrl(url, false);
      return url;
    }
    catch (error) {
      if (generation === this.openGeneration && !this.destroyed) {
        this.setStatus(
          `The AI version could not be rendered: ${error instanceof Error ? error.message : String(error)}`,
          "error",
        );
      }
      return null;
    }
  }

  private async toggleAgentPreview(): Promise<void> {
    if (!this.hasAgentChange || !this.current || this.current.tree.published) return;
    this.disableInlineEditing();
    if (!this.showingAgentChange) {
      const url = await this.ensureChangedPreview();
      if (!url) return;
      this.showingAgentChange = true;
      this.showBrowserUrl(url, false);
      this.setStatus("AI-modified Draft preview · Keep applies this version to the original", "valid");
    }
    else {
      this.showingAgentChange = false;
      this.showBrowserUrl(this.renderedUrl, false);
      this.setStatus("Original Draft preview · the AI version remains unchanged", "valid");
    }
    this.updateChangeControls();
  }

  private async keepAgentChanges(): Promise<void> {
    const current = this.current;
    const changePath = this.changePath;
    if (!current || current.tree.published || !changePath || !this.hasAgentChange || !this.options.keepChange) return;
    this.keepChangesButton.disabled = true;
    try {
      const prepared = await this.options.keepChange(current.relativePath, changePath);
      this.options.changeRenderService.stop();
      this.changePath = prepared.changePath;
      this.changePreviewPath = prepared.previewPath;
      this.changeRevision = prepared.revision;
      this.changedUrl = "";
      this.hasAgentChange = prepared.changed;
      this.setPendingEntry(current.relativePath, prepared.changed);
      this.showingAgentChange = false;
      this.disableInlineEditing();
      this.renderFileColumn();
      this.updateChangeControls();
      this.options.onActiveDocument?.(current.relativePath, this.changePath);
      this.showBrowserUrl(`${this.renderedUrl}${this.renderedUrl.includes("?") ? "&" : "?"}qlab=${Date.now()}`, false);
      this.setStatus("AI version kept as the original Draft · waiting for the preview to refresh", "valid");
      void this.updateDraftCompliance(current.relativePath, this.openGeneration);
    }
    catch (error) {
      this.keepChangesButton.disabled = false;
      this.setStatus(
        `${error instanceof Error ? error.message : String(error)} No file was overwritten.`,
        "conflict",
      );
    }
  }

  private showBrowserUrl(url: string, reload: boolean): void {
    if (!this.renderBrowser || !url) return;
    const current = this.renderBrowser.getAttribute("src") || "";
    if (current !== url) {
      this.renderBrowser.setAttribute("src", url);
      return;
    }
    if (!reload) return;
    const browser = this.renderBrowser as HTMLElement & { reload?(): void };
    if (typeof browser.reload === "function") browser.reload();
    else browser.setAttribute("src", url);
  }

  private updateChangeControls(): void {
    const isDraft = Boolean(this.current && !this.current.tree.published);
    this.compareButton.hidden = !isDraft;
    this.keepChangesButton.hidden = !isDraft;
    this.editPreviewButton.hidden = !isDraft;
    this.compareButton.disabled = !this.hasAgentChange;
    this.keepChangesButton.disabled = !this.hasAgentChange;
    this.editPreviewButton.disabled = !isDraft || this.showingAgentChange;
    this.editPreviewButton.setAttribute(
      "aria-pressed",
      String(this.inlineEditingEnabled && !this.showingAgentChange),
    );
    this.presentIcon(
      this.editPreviewButton,
      "✐",
      this.showingAgentChange
        ? "Inline editing is available on the original Draft"
        : this.inlineEditingEnabled ? "Return to website view" : "Edit directly in Preview",
    );
    this.compareButton.setAttribute("aria-pressed", String(this.showingAgentChange));
    this.presentIcon(
      this.compareButton,
      "◉",
      !this.hasAgentChange
        ? "No AI version to compare"
        : this.showingAgentChange ? "Show original Draft preview" : "Show AI-modified Draft preview",
    );
    this.presentIcon(
      this.keepChangesButton,
      "⤓",
      this.hasAgentChange ? "Keep AI version as the original Draft" : "No AI changes to keep",
    );
  }

  private button(className: string, label: string, onClick: () => void): HTMLButtonElement {
    const button = this.doc.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  private iconButton(
    className: string,
    glyph: string,
    label: string,
    onClick: () => void,
  ): HTMLButtonElement {
    const button = this.button(className, glyph, onClick);
    this.presentIcon(button, glyph, label);
    return button;
  }

  private presentIcon(button: HTMLButtonElement, glyph: string, label: string): void {
    button.textContent = glyph;
    button.title = label;
    button.setAttribute("aria-label", label);
  }

  private setStatus(message: string, state: string): void {
    this.status.textContent = message;
    this.status.dataset.state = state;
  }

  private configureReviewControls(tree: EditorTree): void {
    const isDraft = !tree.published;
    this.complianceButton.hidden = !isDraft;
    this.reviewButton.hidden = !isDraft;
    this.compareButton.hidden = !isDraft;
    this.keepChangesButton.hidden = !isDraft;
    this.reviewButton.disabled = false;
    this.presentIcon(this.reviewButton, "↑", "Add to Knowledge…");
    this.complianceDetails.hidden = true;
    this.complianceDetails.replaceChildren();
    this.complianceButton.setAttribute("aria-expanded", "false");
    if (isDraft) {
      this.presentIcon(this.complianceButton, "…", "Checking Draft…");
      this.complianceButton.dataset.state = "checking";
      this.complianceButton.disabled = true;
    }
    this.updateChangeControls();
  }

  private async updateDraftCompliance(relativePath: string, generation: number): Promise<void> {
    const complianceGeneration = ++this.complianceGeneration;
    if (generation === this.openGeneration && this.current?.relativePath === relativePath) {
      this.complianceButton.disabled = true;
      this.complianceButton.dataset.state = "checking";
      this.presentIcon(this.complianceButton, "…", "Checking Draft…");
    }
    let result;
    try {
      result = await this.options.renderService.checkDraft(this.repoRootHint, relativePath);
    }
    catch (error) {
      result = {
        ok: false,
        diagnostics: [{
          code: "DRAFT_CHECK_FAILED",
          message: error instanceof Error ? error.message : String(error),
          line: 1,
        }],
      };
    }
    if (generation !== this.openGeneration
        || complianceGeneration !== this.complianceGeneration
        || this.destroyed
        || this.current?.relativePath !== relativePath) return;

    this.complianceButton.disabled = false;
    this.complianceButton.dataset.state = result.ok ? "valid" : "error";
    const complianceLabel = result.ok
      ? "Draft checks passed — click for details"
      : `${result.diagnostics.length} ${result.diagnostics.length === 1 ? "issue" : "issues"} in Draft — click for details`;
    this.presentIcon(this.complianceButton, result.ok ? "✓" : "!", complianceLabel);
    this.complianceDetails.replaceChildren();
    if (result.ok) {
      const message = this.doc.createElement("p");
      message.textContent = "This Draft meets the automatic promotion-readiness checks. Human review is still required.";
      this.complianceDetails.appendChild(message);
      return;
    }
    const list = this.doc.createElement("ul");
    for (const diagnostic of result.diagnostics) {
      const item = this.doc.createElement("li");
      item.textContent = `${diagnostic.code} · line ${diagnostic.line} · ${diagnostic.message}`;
      list.appendChild(item);
    }
    this.complianceDetails.appendChild(list);
  }

  private async reviewCurrentDraft(): Promise<void> {
    if (!this.current || this.current.tree.published || !this.options.onReviewDraft) return;
    this.reviewButton.disabled = true;
    this.presentIcon(this.reviewButton, "…", "Starting Knowledge review…");
    try {
      await this.options.onReviewDraft(this.current.relativePath);
      this.presentIcon(this.reviewButton, "✓", "Knowledge review started");
    }
    catch (error) {
      this.presentIcon(this.reviewButton, "↑", "Add to Knowledge…");
      this.setStatus(error instanceof Error ? error.message : String(error), "error");
    }
    finally {
      this.reviewButton.disabled = false;
    }
  }

  private async refreshEditors(): Promise<void> {
    if (this.available.length) {
      this.editButton.disabled = !this.current;
      this.updateEditorLabel();
      return;
    }
    this.available = await this.options.editors();
    if (this.destroyed) return;
    this.editorPicker.replaceChildren();
    for (const editor of this.available) {
      const option = this.doc.createElement("option");
      option.value = editor.id;
      option.textContent = editor.label;
      this.editorPicker.appendChild(option);
    }
    // A picker for one editor is a control with nothing to decide.
    this.editorPicker.hidden = this.available.length < 2;
    this.editButton.disabled = !this.available.length || !this.current;
    this.updateEditorLabel();
  }

  private updateEditorLabel(): void {
    const editor = this.available.find((candidate) => candidate.id === this.editorPicker.value)
      ?? this.available[0];
    if (!editor) {
      this.presentIcon(this.editButton, "∅", "No Editor Found");
      this.editButton.title = "No Editor Found — install Cursor, VS Code, Zed, or Sublime Text";
      return;
    }
    const label = `Edit in ${editor.label}`;
    const iconUrl = externalEditorIconUrl(editor);
    if (!iconUrl) {
      this.presentIcon(this.editButton, "✎", label);
      return;
    }
    const icon = this.doc.createElement("img");
    icon.className = "zc-qmd-editor-icon";
    icon.src = iconUrl;
    icon.alt = "";
    icon.setAttribute("aria-hidden", "true");
    this.editButton.replaceChildren(icon);
    this.editButton.title = label;
    this.editButton.setAttribute("aria-label", label);
  }

  private async openExternally(): Promise<void> {
    if (!this.current || !this.available.length) return;
    const chosen = this.available.find((editor) => editor.id === this.editorPicker.value)
      ?? this.available[0]!;
    try {
      await this.options.openExternally(chosen, this.current.relativePath);
      this.setStatus(`Opened in ${chosen.label} · the preview refreshes automatically after save`, "valid");
    }
    catch (error) {
      this.setStatus(error instanceof Error ? error.message : String(error), "error");
    }
  }

  private async reloadRender(): Promise<void> {
    if (!this.current) return;
    if (this.showingAgentChange && this.changePath && this.hasAgentChange) {
      this.changedUrl = "";
      const url = await this.ensureChangedPreview();
      if (url) this.showBrowserUrl(url, true);
      return;
    }
    const url = await this.options.renderService.open(
      this.current.tree,
      this.repoRootHint,
      this.current.relativePath,
    );
    this.renderedUrl = url;
    this.showBrowserUrl(url, true);
  }

  private ensureRenderBrowser(): void {
    if (this.renderBrowser || this.renderPane.childElementCount) return;
    const createXULElement = (this.doc as unknown as {
      createXULElement?: (name: string) => HTMLElement;
    }).createXULElement;
    if (typeof createXULElement !== "function") {
      const unavailable = this.doc.createElement("div");
      unavailable.className = "zc-qmd-render-unavailable";
      unavailable.textContent = "The native Zotero preview container is unavailable";
      this.renderPane.appendChild(unavailable);
      return;
    }
    const browser = createXULElement.call(this.doc, "browser");
    browser.classList.add("zc-qmd-render-browser");
    browser.setAttribute("type", "content");
    browser.setAttribute("remote", "true");
    browser.setAttribute("maychangeremoteness", "true");
    browser.addEventListener("load", () => {
      const active = this.current;
      if (!active || this.destroyed) return;
      // A remote XUL browser often creates its message manager only after the
      // first navigation. Attaching solely at construction makes the toolbar
      // switch modes while leaving the compiled page completely read-only.
      this.attachInlineEditor(browser);
      if (!active.tree.published) {
        void this.updateDraftCompliance(active.relativePath, this.openGeneration);
      }
      void this.configureInlineEditing();
    });
    this.renderBrowser = browser;
    this.renderPane.appendChild(browser);
    this.attachInlineEditor(browser);
  }

  private attachInlineEditor(browser: HTMLElement): void {
    const manager = (browser as HTMLElement & {
      messageManager?: QmdRemoteMessageManager;
    }).messageManager;
    if (!manager) return;
    if (this.inlineMessageManager === manager) return;
    if (this.inlineMessageManager) this.detachInlineEditor();
    this.inlineMessageManager = manager;
    manager.addMessageListener(QMD_INLINE_READY_TOPIC, this.onInlineReadyMessage);
    manager.addMessageListener(QMD_INLINE_CONFIGURED_TOPIC, this.onInlineConfiguredMessage);
    manager.addMessageListener(QMD_INLINE_EDIT_TOPIC, this.onInlineEditMessage);
    const source = qmdInlineFrameScript();
    manager.loadFrameScript(
      `data:application/javascript;charset=UTF-8,${encodeURIComponent(source)}`,
      true,
    );
  }

  private detachInlineEditor(): void {
    const manager = this.inlineMessageManager;
    if (!manager) return;
    manager.removeMessageListener(QMD_INLINE_READY_TOPIC, this.onInlineReadyMessage);
    manager.removeMessageListener(QMD_INLINE_CONFIGURED_TOPIC, this.onInlineConfiguredMessage);
    manager.removeMessageListener(QMD_INLINE_EDIT_TOPIC, this.onInlineEditMessage);
    this.inlineMessageManager = null;
    this.inlineBlocks.clear();
  }

  private disableInlineEditing(): void {
    this.inlineBlocks.clear();
    this.inlineMessageManager?.sendAsyncMessage(QMD_INLINE_CONFIGURE_TOPIC, {
      enabled: false,
      blocks: [],
    });
  }

  private async configureInlineEditing(): Promise<void> {
    const manager = this.inlineMessageManager;
    const current = this.current;
    const generation = this.openGeneration;
    const editable = Boolean(
      manager
      && current
      && !current.tree.published
      && this.changePath
      && this.options.editableBlocks
      && this.options.applyManualEdit
      && this.inlineEditingEnabled
      && !this.showingAgentChange,
    );
    if (!editable || !manager || !current) {
      this.disableInlineEditing();
      return;
    }

    const sourcePath = current.relativePath;
    let blocks: QmdEditableBlock[];
    try {
      blocks = await this.options.editableBlocks!(sourcePath);
    }
    catch (error) {
      if (generation === this.openGeneration && !this.destroyed) {
        this.disableInlineEditing();
        this.setStatus(
          `Inline Draft editing is unavailable: ${error instanceof Error ? error.message : String(error)}`,
          "error",
        );
      }
      return;
    }
    if (generation !== this.openGeneration || this.destroyed || current !== this.current) return;
    this.inlineBlocks.clear();
    for (const candidate of blocks) this.inlineBlocks.set(candidate.id, candidate);
    manager.sendAsyncMessage(QMD_INLINE_CONFIGURE_TOPIC, {
      enabled: true,
      blocks: blocks.map(({ id, kind, text, domId, domKind, ordinal }) => ({
        id,
        kind,
        text,
        domId,
        domKind,
        ordinal,
      })),
    });
  }

  private async applyInlineEdit(message: QmdInlineEditMessage, generation: number): Promise<void> {
    const current = this.current;
    const changePath = this.changePath;
    const block = this.inlineBlocks.get(message.id);
    const canEdit = Boolean(
      current
      && !current.tree.published
      && changePath
      && block
      && this.options.applyManualEdit
      && this.inlineEditingEnabled
      && !this.showingAgentChange,
    );
    if (!canEdit || !current || !changePath || !block || !this.options.applyManualEdit) {
      this.sendInlineResult({
        id: message.id,
        ok: false,
        text: block?.text ?? "",
        error: "This preview version is read-only. Switch to the edited version before changing it.",
      });
      return;
    }

    try {
      const prepared = await this.options.applyManualEdit(
        current.relativePath,
        block,
        message.text,
      );
      if (generation !== this.openGeneration || this.destroyed || current !== this.current) return;
      this.changePath = prepared.changePath;
      this.changePreviewPath = prepared.previewPath;
      this.changeRevision = prepared.revision;
      this.hasAgentChange = prepared.changed;
      this.showingAgentChange = false;
      this.setPendingEntry(current.relativePath, prepared.changed);
      this.renderFileColumn();
      this.updateChangeControls();
      this.options.onActiveDocument?.(current.relativePath, this.changePath);
      this.sendInlineResult({ id: message.id, ok: true, text: message.text });
      this.setStatus(
        "Draft saved · the compiled preview is updating automatically",
        "saved",
      );
      await this.configureInlineEditing();
      void this.updateDraftCompliance(current.relativePath, generation);
    }
    catch (error) {
      this.sendInlineResult({
        id: message.id,
        ok: false,
        text: block.text,
        error: error instanceof Error ? error.message : String(error),
      });
      if (generation === this.openGeneration && !this.destroyed) {
        this.setStatus(
          `${error instanceof Error ? error.message : String(error)} No Draft file was changed.`,
          "error",
        );
      }
    }
  }

  private sendInlineResult(result: QmdInlineResultMessage): void {
    this.inlineMessageManager?.sendAsyncMessage(QMD_INLINE_RESULT_TOPIC, result);
  }

  private async toggleInlineEditing(): Promise<void> {
    if (!this.current || this.current.tree.published || this.showingAgentChange) return;
    this.inlineEditingEnabled = !this.inlineEditingEnabled;
    this.updateChangeControls();
    if (this.inlineEditingEnabled) {
      this.setStatus(
        "Inline edit mode · click text, formulas, or thm/lem/def blocks · changes save on blur",
        "valid",
      );
      await this.configureInlineEditing();
    }
    else {
      this.disableInlineEditing();
      this.setStatus("Website view · showing the compiled Quarto page", "valid");
    }
  }

  private toggleFileColumn(): void {
    const collapsed = this.root.classList.toggle("is-files-collapsed");
    const label = collapsed ? "Expand File List" : "Collapse File List";
    this.fileToggle.textContent = collapsed ? "›" : "‹";
    this.fileToggle.title = label;
    this.fileToggle.setAttribute("aria-label", label);
    this.fileToggle.setAttribute("aria-expanded", String(!collapsed));
  }

  private async refreshIndex(): Promise<void> {
    try {
      this.entries = await this.options.index();
    }
    catch {
      this.entries = [];
    }
  }

  private renderFileColumn(): void {
    this.fileColumn.replaceChildren();
    for (const root of groupIntoTree(this.entries)) {
      const tree = EDITOR_TREES.find((candidate) => candidate.id === root.treeId);
      this.fileColumn.appendChild(this.renderNode(root, tree?.label ?? root.name, 0));
    }
  }

  private renderNode(node: QmdTreeNode, label: string, depth: number): HTMLElement {
    const wrapper = this.doc.createElement("div");
    wrapper.className = node.entry ? "zc-qmd-file" : "zc-qmd-folder";
    const row = this.doc.createElement("button");
    row.type = "button";
    row.className = "zc-qmd-file-row";
    row.dataset.path = node.path;
    row.dataset.tree = node.treeId;
    row.style.paddingInlineStart = `${6 + depth * 11}px`;
    const open = this.expanded.has(node.path);
    const pending = node.entry?.pendingChange
      || node.children.some((child) => this.nodeHasPendingChange(child));
    const text = this.doc.createElement("span");
    text.textContent = node.entry ? label : `${open ? "▾" : "▸"} ${label}`;
    row.appendChild(text);
    if (pending && node.treeId === "drafts") {
      const dot = this.doc.createElement("span");
      dot.className = "zc-qmd-pending-dot";
      dot.title = "AI changes waiting for review";
      dot.setAttribute("aria-label", "AI changes waiting for review");
      dot.textContent = "●";
      row.appendChild(dot);
    }
    if (node.entry) {
      const path = node.entry.relativePath;
      row.classList.toggle("is-active", this.current?.relativePath === path);
      row.addEventListener("click", () => void this.open(path));
    }
    else {
      row.addEventListener("click", () => {
        if (this.expanded.has(node.path)) this.expanded.delete(node.path);
        else this.expanded.add(node.path);
        this.renderFileColumn();
      });
    }
    wrapper.appendChild(row);
    if (!node.entry && open) {
      for (const child of node.children) {
        wrapper.appendChild(this.renderNode(child, child.name, depth + 1));
      }
    }
    return wrapper;
  }

  private nodeHasPendingChange(node: QmdTreeNode): boolean {
    return Boolean(node.entry?.pendingChange || node.children.some((child) => this.nodeHasPendingChange(child)));
  }

  private setPendingEntry(relativePath: string, pending: boolean): void {
    const entry = this.entries.find((candidate) => candidate.relativePath === relativePath);
    if (entry) entry.pendingChange = pending;
  }

  private async openQuickOpen(): Promise<void> {
    await this.refreshIndex();
    if (this.destroyed) return;
    this.renderFileColumn();
    this.quickOpenInput.value = "";
    this.quickOpen.hidden = false;
    this.renderQuickOpen();
    this.quickOpenInput.focus();
  }

  private closeQuickOpen(): void {
    this.quickOpen.hidden = true;
  }

  private renderQuickOpen(): void {
    const matches = filterQmdIndex(this.entries, this.quickOpenInput.value).slice(0, 40);
    this.quickOpenList.replaceChildren();
    if (!matches.length) {
      const empty = this.doc.createElement("div");
      empty.className = "zc-qmd-quickopen-empty";
      empty.textContent = "No matching files";
      this.quickOpenList.appendChild(empty);
      return;
    }
    for (const [index, entry] of matches.entries()) {
      const row = this.doc.createElement("button");
      row.type = "button";
      row.className = "zc-qmd-quickopen-row";
      row.dataset.path = entry.relativePath;
      row.classList.toggle("is-selected", index === 0);
      const mark = this.doc.createElement("span");
      mark.className = "zc-qmd-quickopen-mark";
      mark.dataset.tree = entry.treeId;
      mark.textContent = entry.treeId === "knowledge" ? "●" : "✎";
      const label = this.doc.createElement("span");
      label.textContent = entry.relativePath;
      row.append(mark, label);
      row.addEventListener("click", () => {
        this.closeQuickOpen();
        void this.open(entry.relativePath);
      });
      this.quickOpenList.appendChild(row);
    }
  }

  private onQuickOpenKey(event: KeyboardEvent): void {
    const rows = [...this.quickOpenList.querySelectorAll<HTMLButtonElement>(".zc-qmd-quickopen-row")];
    if (event.key === "Escape") {
      event.preventDefault();
      this.closeQuickOpen();
      return;
    }
    if (!rows.length) return;
    const current = rows.findIndex((row) => row.classList.contains("is-selected"));
    if (event.key === "Enter") {
      event.preventDefault();
      rows[Math.max(0, current)]!.click();
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const next = event.key === "ArrowDown"
      ? Math.min(rows.length - 1, current + 1)
      : Math.max(0, current - 1);
    rows.forEach((row, index) => row.classList.toggle("is-selected", index === next));
  }
}
