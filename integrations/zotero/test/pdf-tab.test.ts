// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";

import { PdfReaderView, type PdfEmbedHandle, type PdfTabDeps } from "../src/pdf-tab";

function makeHandle() {
  return { goToPage: vi.fn(), dispose: vi.fn() } satisfies PdfEmbedHandle;
}

function makeDeps(overrides: Partial<PdfTabDeps> = {}): PdfTabDeps {
  return {
    resolveFileURI: vi.fn(async () => "file:///papers/a.pdf"),
    createBrowserViewer: vi.fn(() => makeHandle()),
    onRequestChoosePaper: vi.fn(),
    onPageChange: vi.fn(),
    ...overrides,
  };
}

function mountView(deps: PdfTabDeps, page = 3) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const view = new PdfReaderView(
    document,
    { itemID: 9, attachmentKey: "K9", page },
    deps,
  );
  view.mount(host);
  view.show();
  return { view, host };
}

async function settle(): Promise<void> {
  for (let index = 0; index < 4; index += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

describe("PdfReaderView", () => {
  it("prefers a native embed and skips the browser fallback", async () => {
    const native = makeHandle();
    const deps = makeDeps({
      createNativeEmbed: vi.fn(async () => native),
    });
    mountView(deps);
    await settle();
    expect(deps.createNativeEmbed).toHaveBeenCalledOnce();
    expect(deps.createBrowserViewer).not.toHaveBeenCalled();
  });

  it("falls back to the browser viewer with the stored page", async () => {
    const deps = makeDeps({
      createNativeEmbed: vi.fn(async () => null),
    });
    const { host } = mountView(deps, 7);
    await settle();
    expect(deps.createBrowserViewer).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      "file:///papers/a.pdf",
      7,
    );
    expect(host.querySelector(".zc-pdf-error-card")).toBeNull();
  });

  it("shows an actionable error card when the attachment file is missing", async () => {
    const deps = makeDeps({
      resolveFileURI: vi.fn(async () => null),
    });
    const { host } = mountView(deps);
    await settle();
    const card = host.querySelector(".zc-pdf-error-card")!;
    expect(card).not.toBeNull();
    (card.querySelector(".zc-pdf-error-action") as HTMLElement).click();
    expect(deps.onRequestChoosePaper).toHaveBeenCalledOnce();
  });

  it("delegates goToPage to the active handle and reports the page", async () => {
    const handle = makeHandle();
    const deps = makeDeps({ createBrowserViewer: vi.fn(() => handle) });
    const { view } = mountView(deps);
    await settle();
    view.goToPage(12);
    expect(handle.goToPage).toHaveBeenCalledWith(12);
    expect(deps.onPageChange).toHaveBeenCalledWith(12);
  });

  it("swaps in the error card when the handle throws and reloads on demand", async () => {
    const broken = makeHandle();
    broken.goToPage.mockImplementation(() => { throw new Error("viewer gone"); });
    const healthy = makeHandle();
    const createBrowserViewer = vi.fn()
      .mockReturnValueOnce(broken)
      .mockReturnValueOnce(healthy);
    const deps = makeDeps({ createBrowserViewer });
    const { view, host } = mountView(deps);
    await settle();
    view.goToPage(2);
    const card = host.querySelector(".zc-pdf-error-card")!;
    expect(card).not.toBeNull();
    (card.querySelector(".zc-pdf-error-reload") as HTMLElement).click();
    await settle();
    expect(createBrowserViewer).toHaveBeenCalledTimes(2);
    expect(host.querySelector(".zc-pdf-error-card")).toBeNull();
  });

  it("disposes the active handle", async () => {
    const handle = makeHandle();
    const deps = makeDeps({ createBrowserViewer: vi.fn(() => handle) });
    const { view } = mountView(deps);
    await settle();
    view.dispose();
    expect(handle.dispose).toHaveBeenCalledOnce();
  });
});
