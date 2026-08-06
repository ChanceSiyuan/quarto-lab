// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";

import { SiteTabView, type SiteTabCallbacks } from "../src/site-tab";

function makeCallbacks(overrides: Partial<SiteTabCallbacks> = {}): SiteTabCallbacks {
  return {
    checkSite: vi.fn(async () => true),
    checkRepository: vi.fn(async () => "ready" as const),
    deploy: vi.fn(async () => undefined),
    chooseRepository: vi.fn(async () => undefined),
    onOpenDocument: vi.fn(),
    ...overrides,
  };
}

function mountView(callbacks: SiteTabCallbacks) {
  (document as unknown as { createXULElement?: unknown }).createXULElement =
    vi.fn(() => document.createElement("browser"));
  const host = document.createElement("div");
  document.body.appendChild(host);
  const view = new SiteTabView(document, callbacks);
  view.mount(host);
  view.show();
  return { view, host };
}

describe("SiteTabView", () => {
  it("shows the site view directly when the repository is ready and the site runs", async () => {
    const callbacks = makeCallbacks();
    const { host } = mountView(callbacks);
    await vi.waitFor(() => {
      expect(host.querySelector(".zc-main-site-view")).not.toBeNull();
      expect((host.querySelector(".zc-main-site-view") as HTMLElement).hidden).toBe(false);
    });
    expect((host.querySelector(".zc-site-status-card") as HTMLElement).hidden).toBe(true);
    expect(callbacks.deploy).not.toHaveBeenCalled();
    // No back button: tabs replace the "Back to AI" affordance.
    expect(host.querySelector(".zc-main-site-back")).toBeNull();
  });

  it("offers Build & Start when the site is down, streams progress, then shows the site", async () => {
    let resolveDeploy!: () => void;
    const callbacks = makeCallbacks({
      checkSite: vi.fn(async () => false),
      deploy: vi.fn((onProgress: (message: string) => void) => {
        onProgress("Installing main-site dependencies…");
        return new Promise<void>((resolve) => { resolveDeploy = resolve; });
      }),
    });
    const { host } = mountView(callbacks);
    const button = await vi.waitFor(() => {
      const found = host.querySelector<HTMLButtonElement>(".zc-site-status-action")!;
      expect(found.textContent).toBe("Build & Start");
      return found;
    });
    button.click();
    await vi.waitFor(() => {
      expect(host.querySelector(".zc-site-status-detail")!.textContent)
        .toBe("Installing main-site dependencies…");
    });
    expect(button.disabled).toBe(true);
    resolveDeploy();
    await vi.waitFor(() => {
      expect((host.querySelector(".zc-main-site-view") as HTMLElement).hidden).toBe(false);
    });
    expect((host.querySelector(".zc-site-status-card") as HTMLElement).hidden).toBe(true);
  });

  it("routes a missing repository through the chooser and re-checks", async () => {
    let repositoryState: "missing" | "ready" = "missing";
    const callbacks = makeCallbacks({
      checkRepository: vi.fn(async () => repositoryState),
      chooseRepository: vi.fn(async () => { repositoryState = "ready"; }),
    });
    const { host } = mountView(callbacks);
    const button = await vi.waitFor(() => {
      const found = host.querySelector<HTMLButtonElement>(".zc-site-status-action")!;
      expect(found.textContent).toBe("Choose Repository");
      return found;
    });
    button.click();
    await vi.waitFor(() => expect(callbacks.chooseRepository).toHaveBeenCalledOnce());
    await vi.waitFor(() => {
      expect((host.querySelector(".zc-main-site-view") as HTMLElement).hidden).toBe(false);
    });
    expect(callbacks.checkRepository).toHaveBeenCalledTimes(2);
  });

  it("keeps the card actionable after a deploy failure", async () => {
    const callbacks = makeCallbacks({
      checkSite: vi.fn(async () => false),
      deploy: vi.fn(async () => { throw new Error("npm ci exploded"); }),
    });
    const { host } = mountView(callbacks);
    const button = await vi.waitFor(() => {
      const found = host.querySelector<HTMLButtonElement>(".zc-site-status-action")!;
      expect(found.textContent).toBe("Build & Start");
      return found;
    });
    button.click();
    await vi.waitFor(() => {
      expect(host.querySelector(".zc-site-status-detail")!.textContent)
        .toBe("Retry Main Site: npm ci exploded");
    });
    expect(button.disabled).toBe(false);
    expect(host.querySelector(".zc-main-site-view")).toBeNull();
  });

  it("shows the SSH-unsupported card without running any status check", async () => {
    const callbacks = makeCallbacks({ supported: () => false });
    const { host } = mountView(callbacks);
    await vi.waitFor(() => {
      expect(host.querySelector(".zc-site-status-detail")!.textContent)
        .toBe("Main Site is available only for repositories on this Mac");
    });
    expect((host.querySelector(".zc-site-status-action") as HTMLElement).hidden).toBe(true);
    expect(callbacks.checkRepository).not.toHaveBeenCalled();
    expect(callbacks.checkSite).not.toHaveBeenCalled();
  });

  it("does not re-run the status flow once the site is visible", async () => {
    const callbacks = makeCallbacks();
    const { view } = mountView(callbacks);
    await vi.waitFor(() => expect(callbacks.checkSite).toHaveBeenCalledOnce());
    view.hide();
    view.show();
    expect(callbacks.checkRepository).toHaveBeenCalledOnce();
    expect(callbacks.checkSite).toHaveBeenCalledOnce();
  });
});
