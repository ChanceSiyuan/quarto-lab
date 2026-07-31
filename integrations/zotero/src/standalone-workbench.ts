export interface StandaloneWorkbenchView {
  show(): void;
  destroy(): void;
  focusComposer(text?: string): void;
  setState(next: unknown): void;
  workspace?(): unknown;
}

interface StandaloneWorkbenchCallbacks {
  openWindow(source: Window): Promise<Window>;
  createView(host: HTMLElement, win: Window): StandaloneWorkbenchView;
  onActiveChange(active: boolean): void;
  onReturn?(): void;
}

/**
 * Owns the one real QLab chrome window. The view is created by the plugin so
 * it keeps using the same CodexService, history store, paper bindings, and
 * running turns as every embedded surface.
 */
export class StandaloneWorkbenchManager {
  private win: Window | null = null;
  private view: StandaloneWorkbenchView | null = null;
  private opening: Promise<Window> | null = null;

  constructor(private readonly callbacks: StandaloneWorkbenchCallbacks) {}

  isActive(): boolean {
    return Boolean(this.win && !this.win.closed && this.view);
  }

  window(): Window | null {
    return this.isActive() ? this.win : null;
  }

  currentView(): StandaloneWorkbenchView | null {
    return this.isActive() ? this.view : null;
  }

  async open(source: Window): Promise<Window> {
    if (this.isActive()) {
      this.win!.focus?.();
      this.view!.focusComposer();
      return this.win!;
    }
    if (this.opening) return this.opening;
    const pending = this.openInternal(source);
    this.opening = pending;
    try {
      return await pending;
    }
    finally {
      if (this.opening === pending) this.opening = null;
    }
  }

  focus(): void {
    if (!this.isActive()) return;
    this.win!.focus?.();
    this.view!.focusComposer();
  }

  close(): void {
    const win = this.win;
    if (!win) return;
    win.close?.();
    // Test and unusual Gecko windows may not emit unload synchronously.
    if (this.win === win && win.closed) this.release();
  }

  returnToEmbedded(): void {
    this.callbacks.onReturn?.();
    this.close();
  }

  destroy(): void {
    this.close();
    this.release();
  }

  private async openInternal(source: Window): Promise<Window> {
    const win = await this.callbacks.openWindow(source);
    const host = win.document.getElementById("qlab-standalone-workbench-host") as HTMLElement | null;
    if (!host) {
      win.close?.();
      throw new Error("The standalone QLab window did not provide its Workbench host");
    }
    this.win = win;
    this.view = this.callbacks.createView(host, win);
    win.addEventListener("unload", () => this.release(), { once: true });
    this.view.show();
    this.view.focusComposer();
    this.callbacks.onActiveChange(true);
    return win;
  }

  private release(): void {
    if (!this.win && !this.view) return;
    const view = this.view;
    this.view = null;
    this.win = null;
    view?.destroy();
    this.callbacks.onActiveChange(false);
  }
}
