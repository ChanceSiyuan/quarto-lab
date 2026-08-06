/**
 * The PDF tab: reads a Zotero attachment inside the workbench.
 *
 * Loading runs a strategy chain on first show. A native embedded Zotero
 * reader is attempted first (annotations, outline — supplied by the plugin
 * side and absent when the spike's APIs are unavailable); the fallback is a
 * XUL content browser pointed at the attachment's file:// URI, where
 * Firefox's built-in pdf.js provides read-only paging, zoom, and search.
 * Every failure lands on an in-tab error card instead of breaking the shell.
 */

import type { PdfTabPayload } from "./workbench-layout";
import type { TabContentProvider } from "./workbench-shell";

export interface PdfEmbedHandle {
  goToPage(page: number): void;
  dispose(): void;
}

export interface PdfTabDeps {
  /** file:// URI of the attachment, or null when the file is missing. */
  resolveFileURI(itemID: number): Promise<string | null>;
  /** The spike: a real embedded Zotero reader. Absent or null → fallback. */
  createNativeEmbed?(host: HTMLElement, itemID: number, page?: number): Promise<PdfEmbedHandle | null>;
  createBrowserViewer(host: HTMLElement, fileURI: string, page?: number): PdfEmbedHandle;
  onRequestChoosePaper(): void;
  /** Reported so the layout payload persists the last page. */
  onPageChange?(page: number): void;
}

/**
 * Fallback viewer: a XUL content browser at the attachment's file:// URI.
 * Firefox's built-in pdf.js supplies read-only paging, zoom, and search;
 * `#page=N` navigation reuses the document when only the fragment changes.
 */
export function createPdfBrowserViewer(
  host: HTMLElement,
  fileURI: string,
  page?: number,
): PdfEmbedHandle {
  const doc = host.ownerDocument;
  const createXULElement = (doc as unknown as {
    createXULElement?: (name: string) => HTMLElement;
  }).createXULElement;
  if (typeof createXULElement !== "function") {
    throw new Error("The native Zotero browser is unavailable");
  }
  const browser = createXULElement.call(doc, "browser");
  browser.classList.add("zc-pdf-browser");
  browser.setAttribute("type", "content");
  browser.setAttribute("remote", "true");
  browser.setAttribute("maychangeremoteness", "true");
  browser.setAttribute("src", pdfViewerURL(fileURI, page));
  host.appendChild(browser);
  return {
    goToPage: (target) => browser.setAttribute("src", pdfViewerURL(fileURI, target)),
    dispose: () => browser.remove(),
  };
}

function pdfViewerURL(fileURI: string, page?: number): string {
  return page ? `${fileURI}#page=${page}` : fileURI;
}

export class PdfReaderView implements TabContentProvider {
  private host: HTMLElement | null = null;
  private surface: HTMLElement | null = null;
  private handle: PdfEmbedHandle | null = null;
  private loading = false;
  private disposed = false;

  constructor(
    private readonly doc: Document,
    private readonly payload: PdfTabPayload,
    private readonly deps: PdfTabDeps,
  ) {}

  mount(host: HTMLElement): void {
    this.host = host;
  }

  show(): void {
    if (this.handle || this.loading) return;
    void this.load();
  }

  hide(): void {}

  dispose(): void {
    this.disposed = true;
    this.handle?.dispose();
    this.handle = null;
    this.surface?.remove();
    this.surface = null;
    this.host = null;
  }

  goToPage(page: number): void {
    if (!this.handle) {
      this.payload.page = page;
      return;
    }
    try {
      this.handle.goToPage(page);
      this.payload.page = page;
      this.deps.onPageChange?.(page);
    }
    catch (error) {
      this.failViewer(error);
    }
  }

  private async load(): Promise<void> {
    if (!this.host || this.loading) return;
    this.loading = true;
    this.resetSurface("zc-pdf-loading", "Loading PDF…");
    try {
      const fileURI = await this.deps.resolveFileURI(this.payload.itemID);
      if (this.disposed) return;
      if (!fileURI) {
        this.presentError(
          "The attachment file for this paper is missing or was moved.",
          { choosePaper: true },
        );
        return;
      }
      if (this.deps.createNativeEmbed) {
        const surface = this.resetSurface("zc-pdf-surface");
        try {
          const native = await this.deps.createNativeEmbed(
            surface,
            this.payload.itemID,
            this.payload.page,
          );
          if (this.disposed) {
            native?.dispose();
            return;
          }
          if (native) {
            this.handle = native;
            return;
          }
        }
        catch {
          // The embedded reader is best-effort; fall through to the browser.
        }
      }
      const surface = this.resetSurface("zc-pdf-surface");
      this.handle = this.deps.createBrowserViewer(surface, fileURI, this.payload.page);
    }
    catch (error) {
      if (!this.disposed) this.failViewer(error);
    }
    finally {
      this.loading = false;
    }
  }

  private failViewer(error: unknown): void {
    try { this.handle?.dispose(); }
    catch { /* the viewer is already broken */ }
    this.handle = null;
    this.presentError(
      `The PDF viewer stopped working: ${error instanceof Error ? error.message : String(error)}`,
      { reload: true },
    );
  }

  private resetSurface(className: string, text = ""): HTMLElement {
    this.surface?.remove();
    this.surface = this.doc.createElement("div");
    this.surface.className = className;
    if (text) this.surface.textContent = text;
    this.host?.appendChild(this.surface);
    return this.surface;
  }

  private presentError(
    detail: string,
    actions: { choosePaper?: boolean; reload?: boolean },
  ): void {
    const card = this.resetSurface("zc-pdf-error-card");
    const message = this.doc.createElement("p");
    message.className = "zc-pdf-error-detail";
    message.textContent = detail;
    card.appendChild(message);
    if (actions.choosePaper) {
      const choose = this.doc.createElement("button");
      choose.type = "button";
      choose.className = "zc-pdf-error-action";
      choose.textContent = "Choose Paper";
      choose.addEventListener("click", () => this.deps.onRequestChoosePaper());
      card.appendChild(choose);
    }
    if (actions.reload) {
      const reload = this.doc.createElement("button");
      reload.type = "button";
      reload.className = "zc-pdf-error-reload";
      reload.textContent = "Reload";
      reload.addEventListener("click", () => void this.load());
      card.appendChild(reload);
    }
  }
}
