/**
 * The main-site tab: hosts the Research Loop site browser, with the former
 * bottom-left button's repository/deploy state machine rendered as the tab's
 * empty state instead of button classes.
 *
 * Status is resolved once per tab lifetime; once the site view is visible the
 * flow never re-runs (hide/show flips visibility only). Closing the tab
 * disposes the browser, so reopening starts from a fresh status check.
 */

import { ResearchLoopSiteView } from "./research-loop-site";
import type { QLabRepositoryState } from "./qlab-workspace";
import type { TabContentProvider } from "./workbench-shell";
import type { ZoteroDeepLink } from "./zotero-links";

export interface SiteTabCallbacks {
  checkSite(): Promise<boolean>;
  checkRepository(): Promise<QLabRepositoryState>;
  deploy(onProgress: (message: string) => void): Promise<void>;
  chooseRepository(): Promise<void>;
  onOpenDocument(relativePath: string): void;
  /** False for chat-only SSH targets: the local main site cannot serve them. */
  supported?(): boolean;
  /** Handles zotero:// deep links clicked inside the embedded site browser. */
  onZoteroLink?(link: ZoteroDeepLink): void;
}

type CardAction = "choose" | "deploy" | null;

export class SiteTabView implements TabContentProvider {
  private host: HTMLElement | null = null;
  private card!: HTMLElement;
  private cardDetail!: HTMLElement;
  private cardButton!: HTMLButtonElement;
  private cardAction: CardAction = null;
  private siteView: ResearchLoopSiteView | null = null;
  private busy = false;
  private disposed = false;

  constructor(
    private readonly doc: Document,
    private readonly callbacks: SiteTabCallbacks,
  ) {}

  mount(host: HTMLElement): void {
    this.host = host;
    this.card = this.doc.createElement("div");
    this.card.className = "zc-site-status-card";
    this.cardDetail = this.doc.createElement("p");
    this.cardDetail.className = "zc-site-status-detail";
    this.cardButton = this.doc.createElement("button");
    this.cardButton.type = "button";
    this.cardButton.className = "zc-site-status-action";
    this.cardButton.addEventListener("click", () => void this.runCardAction());
    this.card.append(this.cardDetail, this.cardButton);
    host.appendChild(this.card);
  }

  show(): void {
    if (this.siteView) {
      this.siteView.show();
      return;
    }
    void this.refresh();
  }

  hide(): void {
    this.siteView?.hide();
  }

  dispose(): void {
    this.disposed = true;
    this.siteView?.destroy();
    this.siteView = null;
    this.host = null;
  }

  private async refresh(): Promise<void> {
    if (this.busy || this.siteView) return;
    if (this.callbacks.supported?.() === false) {
      this.presentCard("Main Site is available only for repositories on this Mac", null);
      return;
    }
    this.presentCard("Checking the Research Loop main site…", null);
    let repositoryState: QLabRepositoryState = "ready";
    let available = false;
    try {
      repositoryState = await this.callbacks.checkRepository() || "ready";
      available = repositoryState === "ready" ? await this.callbacks.checkSite() : false;
    }
    catch {
      available = false;
    }
    if (this.disposed) return;
    if (repositoryState === "missing") {
      this.presentCard("Choose an empty folder or an existing Research Loop repository", "choose");
      return;
    }
    if (repositoryState === "incompatible") {
      this.presentCard("This folder contains unrelated files; choose an empty folder instead", "choose");
      return;
    }
    if (repositoryState === "empty") {
      this.presentCard("Initialize Research Loop in this empty folder", "deploy", "Initialize");
      return;
    }
    if (repositoryState === "partial") {
      this.presentCard(
        "Complete the Research Loop structure without overwriting existing Knowledge, Drafts, or Literature",
        "deploy",
        "Initialize",
      );
      return;
    }
    if (!available) {
      this.presentCard("The main site is not running; build and start it to browse Knowledge here", "deploy");
      return;
    }
    this.showSite();
  }

  private async runCardAction(): Promise<void> {
    if (this.busy) return;
    if (this.cardAction === "choose") {
      this.busy = true;
      try {
        await this.callbacks.chooseRepository();
      }
      finally {
        this.busy = false;
      }
      if (!this.disposed) await this.refresh();
      return;
    }
    if (this.cardAction !== "deploy") return;
    this.busy = true;
    this.cardButton.disabled = true;
    try {
      await this.callbacks.deploy((message) => {
        if (!this.disposed) this.cardDetail.textContent = message;
      });
      if (this.disposed) return;
      this.showSite();
    }
    catch (error) {
      if (this.disposed) return;
      this.cardDetail.textContent =
        `Retry Main Site: ${error instanceof Error ? error.message : String(error)}`;
      this.cardButton.disabled = false;
    }
    finally {
      this.busy = false;
    }
  }

  private presentCard(detail: string, action: CardAction, label?: string): void {
    this.cardAction = action;
    this.card.hidden = false;
    this.cardDetail.textContent = detail;
    this.cardButton.hidden = action === null;
    this.cardButton.disabled = false;
    this.cardButton.textContent = label
      || (action === "choose" ? "Choose Repository" : action === "deploy" ? "Build & Start" : "");
  }

  private showSite(): void {
    if (!this.host) return;
    this.card.hidden = true;
    if (!this.siteView) {
      this.siteView = new ResearchLoopSiteView(this.host, {
        onOpenDocument: this.callbacks.onOpenDocument,
        ...(this.callbacks.onZoteroLink
          ? { onZoteroLink: this.callbacks.onZoteroLink }
          : {}),
      });
    }
    this.siteView.show();
  }
}
