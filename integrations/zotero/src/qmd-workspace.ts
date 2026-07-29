import { EDITOR_TREES, treeForPath, type EditorTree } from "./editor-tree";
import type { ExternalEditorApp } from "./external-editor";
import { filterQmdIndex, groupIntoTree, type QmdIndexEntry, type QmdTreeNode } from "./qmd-index";
import type { QmdRenderService } from "./qmd-render";

export interface QmdWorkspaceOptions {
  onBack(): void;
  renderService: Pick<QmdRenderService, "open" | "stop" | "diagnostic">;
  /** Every previewable QMD in the repository. */
  index(): Promise<QmdIndexEntry[]>;
  /** The editors installed on this machine, best first. */
  editors(): Promise<ExternalEditorApp[]>;
  /** Hands one file to an external editor, with the repository as workspace. */
  openExternally(editor: ExternalEditorApp, relativePath: string): Promise<void>;
  /** Remembers which editor was used last. */
  onEditorChosen?(editorId: string): void;
  /** Tells the assistant which file the user is looking at. */
  onActiveDocument?(relativePath: string | null): void;
}

/**
 * The QMD preview workspace.
 *
 * It previews and it does not edit. A pane sharing width with the chat column
 * is a poor place to write in, and a researcher's own editor is better at
 * writing than anything that would fit there — so this shows the rendered page
 * and hands the source to Cursor or VS Code, the same way the dashboard hands
 * a prompt to Codex rather than growing a chat of its own.
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
  private readonly editButton: HTMLButtonElement;
  private readonly editorPicker: HTMLSelectElement;
  private readonly status: HTMLElement;
  private readonly fileColumn: HTMLElement;
  private readonly fileToggle: HTMLButtonElement;
  private readonly renderPane: HTMLElement;
  private readonly quickOpen: HTMLElement;
  private readonly quickOpenInput: HTMLInputElement;
  private readonly quickOpenList: HTMLElement;

  private renderBrowser: HTMLElement | null = null;
  private renderedUrl = "";
  private current: { relativePath: string; tree: EditorTree } | null = null;
  private entries: QmdIndexEntry[] = [];
  private available: ExternalEditorApp[] = [];
  private expanded = new Set<string>(["knowledge", "drafts"]);
  private destroyed = false;
  private openGeneration = 0;

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
    const back = this.button("zc-qmd-back", "← Back to AI", () => this.options.onBack());
    const quickOpenButton = this.button("zc-qmd-quickopen-button", "Open…", () => void this.openQuickOpen());
    quickOpenButton.title = "Preview a QMD from knowledge/ or drafts/ (Cmd+P)";
    this.pathLabel = make("strong", "zc-qmd-path");
    this.pathLabel.textContent = "No file open";
    this.treeBadge = make("span", "zc-qmd-tree-badge");

    this.editorPicker = this.doc.createElement("select");
    this.editorPicker.className = "zc-qmd-editor-picker";
    this.editorPicker.title = "Choose an editor";
    this.editorPicker.hidden = true;
    this.editorPicker.addEventListener("change", () => {
      this.updateEditorLabel();
      this.options.onEditorChosen?.(this.editorPicker.value);
    });
    this.editButton = this.button("zc-qmd-edit-external", "Edit in External Editor", () => void this.openExternally());
    this.editButton.disabled = true;

    const refresh = this.button("zc-qmd-refresh", "Refresh", () => void this.reloadRender());
    refresh.title = "Reload Preview";
    toolbar.append(back, quickOpenButton, this.pathLabel, this.treeBadge,
      this.editorPicker, this.editButton, refresh);

    this.status = make("div", "zc-qmd-status");
    this.status.textContent = "Choose a QMD page to preview";

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

    this.root.append(toolbar, this.status, body, this.quickOpen);
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
    if (this.current) this.options.onActiveDocument?.(this.current.relativePath);
  }

  hide(): void {
    this.root.hidden = true;
    this.options.onActiveDocument?.(null);
  }

  /** Previews one QMD, starting or reusing its render process. */
  async open(relativePath: string): Promise<void> {
    const generation = ++this.openGeneration;
    const tree = treeForPath(relativePath);
    if (!tree) {
      this.setStatus("Only QMD files in knowledge/ or drafts/ can be previewed", "error");
      return;
    }
    this.current = { relativePath, tree };
    this.pathLabel.textContent = relativePath;
    this.pathLabel.title = relativePath;
    this.treeBadge.textContent = tree.label;
    this.treeBadge.dataset.tree = tree.id;

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
    if (!this.root.hidden) this.options.onActiveDocument?.(relativePath);

    this.ensureRenderBrowser();
    if (this.renderBrowser) {
      if (url !== this.renderedUrl) this.renderBrowser.setAttribute("src", url);
      else {
        const browser = this.renderBrowser as HTMLElement & { reload?(): void };
        if (typeof browser.reload === "function") browser.reload();
        else browser.setAttribute("src", url);
      }
      this.renderedUrl = url;
    }
    const diagnostic = this.options.renderService.diagnostic();
    this.setStatus(
      diagnostic
        ? `Preview is showing the last successful result: ${diagnostic}`
        : tree.published ? "Preview ready · refreshes automatically after save" : "Draft preview ready · refreshes automatically after save",
      diagnostic ? "error" : "valid",
    );
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.openGeneration += 1;
    this.options.renderService.stop();
    this.options.onActiveDocument?.(null);
    this.root.remove();
  }

  // -- internals ------------------------------------------------------------

  private button(className: string, label: string, onClick: () => void): HTMLButtonElement {
    const button = this.doc.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  private setStatus(message: string, state: string): void {
    this.status.textContent = message;
    this.status.dataset.state = state;
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
      this.editButton.textContent = "No Editor Found";
      this.editButton.title = "Cursor, VS Code, Zed, or Sublime Text was not found";
      return;
    }
    this.editButton.textContent = `Edit in ${editor.label}`;
    this.editButton.title = "Open the repository as the workspace and reveal this file";
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
    await this.open(this.current.relativePath);
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
    this.renderBrowser = browser;
    this.renderPane.appendChild(browser);
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
    row.textContent = node.entry ? label : `${open ? "▾" : "▸"} ${label}`;
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
