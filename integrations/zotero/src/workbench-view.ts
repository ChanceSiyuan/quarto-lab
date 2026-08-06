/**
 * Composes the tabbed workbench: a WorkbenchShell whose four tab kinds wrap
 * the existing views — the chat column (SidebarView), the QMD workspace, the
 * Research Loop site, and per-paper PDF readers.
 *
 * This class is what Zotero's deck-tab plumbing (workbench-tab.ts) and the
 * standalone window host: it satisfies their show/destroy/focusComposer/
 * setState contract and adds layout (de)serialization plus the arrangement
 * commands behind the reader-toolbar buttons.
 */

import type { QmdWorkspaceView } from "./qmd-workspace";
import type { SidebarState, SidebarView } from "./sidebar";
import { SiteTabView, type SiteTabCallbacks } from "./site-tab";
import type { SerializedLayout, TabDescriptor, TabRequest } from "./workbench-layout";
import { WorkbenchShell, type TabContentProvider } from "./workbench-shell";

export interface WorkbenchPdfTarget {
  itemID: number;
  attachmentKey: string;
  title: string;
  page?: number;
}

export type WorkbenchArrangement = "pdf-chat" | "pdf-editor";

export interface WorkbenchViewCallbacks {
  /** Builds the chat column into its tab host (called once, lazily). */
  createChat(host: HTMLElement): SidebarView;
  siteCallbacks: SiteTabCallbacks;
  createWorkspace(host: HTMLElement): QmdWorkspaceView;
  createPdfProvider(tab: TabDescriptor): TabContentProvider;
  initialSplitRatio: number;
  onSplitRatioChange(ratio: number): void;
  onLayoutChanged(): void;
}

export class WorkbenchView {
  readonly shell: WorkbenchShell;
  private chatView: SidebarView | null = null;
  private workspaceView: QmdWorkspaceView | null = null;
  private lastState: Partial<SidebarState> | null = null;

  constructor(host: HTMLElement, private readonly callbacks: WorkbenchViewCallbacks) {
    const doc = host.ownerDocument;
    this.shell = new WorkbenchShell(host, doc, {
      initialSplitRatio: callbacks.initialSplitRatio,
      onSplitRatioChange: callbacks.onSplitRatioChange,
      onLayoutChange: () => this.callbacks.onLayoutChanged(),
      onCloseRequested: (tab) => this.confirmClose(tab),
    });
    this.shell.registerFactory("chat", () => this.chatProvider(), { retainOnClose: true });
    this.shell.registerFactory("editor", () => this.editorProvider());
    this.shell.registerFactory(
      "site",
      () => new SiteTabView(doc, this.callbacks.siteCallbacks),
    );
    this.shell.registerFactory("pdf", (tab) => this.callbacks.createPdfProvider(tab));
    this.shell.layout.openTab({ kind: "chat" });
  }

  // ---- WorkbenchTabView / StandaloneWorkbenchView contract ----

  show(): void {
    this.shell.sync();
  }

  destroy(): void {
    this.shell.dispose();
    this.chatView = null;
    this.workspaceView = null;
  }

  focusComposer(text?: string): void {
    this.chatView?.focusComposer(text);
  }

  setState(next: Partial<SidebarState>): void {
    this.lastState = next;
    this.chatView?.setState(next);
  }

  workspace(): QmdWorkspaceView | null {
    return this.workspaceView;
  }

  setDetached(active: boolean, handlers: Parameters<SidebarView["setDetached"]>[1]): void {
    this.chatView?.setDetached(active, handlers);
  }

  chat(): SidebarView | null {
    return this.chatView;
  }

  layoutData(): SerializedLayout {
    return this.shell.layout.serialize();
  }

  setLayoutData(data: unknown): void {
    this.shell.layout.restore(data);
    this.shell.sync();
  }

  // ---- Arrangement commands (reader-toolbar buttons A and C) ----

  arrange(kind: WorkbenchArrangement, pdf: WorkbenchPdfTarget | null): void {
    const right: TabRequest = kind === "pdf-chat" ? { kind: "chat" } : { kind: "editor" };
    if (!pdf) {
      this.shell.layout.openTab(right);
      return;
    }
    this.shell.layout.arrange(
      {
        kind: "pdf",
        title: pdf.title,
        payload: {
          itemID: pdf.itemID,
          attachmentKey: pdf.attachmentKey,
          ...(pdf.page === undefined ? {} : { page: pdf.page }),
        },
      },
      right,
    );
  }

  /** Ensures the editor tab exists and is active; the workspace mounts lazily. */
  openEditorTab(): QmdWorkspaceView | null {
    this.shell.layout.openTab({ kind: "editor" });
    return this.workspaceView;
  }

  // ---- Terminal drawer delegation (drawer lives in the chat pane) ----

  isTerminalOpen(): boolean {
    return this.chatView?.isTerminalOpen() ?? false;
  }

  setTerminalOpen(open: boolean): void {
    if (open) this.ensureChatTab();
    this.chatView?.setTerminalOpen(open);
  }

  terminalHost(): HTMLElement {
    this.ensureChatTab();
    const host = this.chatView?.terminalHost();
    if (!host) throw new Error("The workbench chat pane is unavailable");
    return host;
  }

  /**
   * The terminal overlays the chat pane, so opening it with the chat tab
   * closed first reopens chat in the focused pane.
   */
  private ensureChatTab(): void {
    this.shell.layout.openTab({ kind: "chat" });
  }

  // ---- Providers ----

  private chatProvider(): TabContentProvider {
    return {
      mount: (host) => {
        this.chatView = this.callbacks.createChat(host);
        const dock = this.chatView.dockContents();
        if (dock) this.shell.dock().appendChild(dock);
        if (this.lastState) this.chatView.setState(this.lastState);
      },
      show: () => this.chatView?.show(),
      hide: () => {},
      dispose: () => {
        this.chatView?.destroy();
        this.chatView = null;
      },
      focus: () => this.chatView?.focusComposer(),
    };
  }

  private editorProvider(): TabContentProvider {
    return {
      mount: (host) => {
        this.workspaceView = this.callbacks.createWorkspace(host);
      },
      show: () => this.workspaceView?.show(),
      hide: () => this.workspaceView?.hide(),
      dispose: () => {
        this.workspaceView?.destroy();
        this.workspaceView = null;
      },
    };
  }

  private confirmClose(tab: TabDescriptor): boolean {
    if (tab.kind !== "editor" || !this.workspaceView?.hasActiveEdit()) return true;
    const view = this.shell.root.ownerDocument.defaultView;
    return view?.confirm?.("A visual edit is still open. Close the editor anyway?") ?? true;
  }
}
