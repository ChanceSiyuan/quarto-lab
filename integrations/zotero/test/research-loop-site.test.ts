// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  RESEARCH_LOOP_SITE_URL,
  ResearchLoopSiteService,
  ResearchLoopSiteView,
  researchLoopBuildProgress,
} from "../src/research-loop-site";

describe("ResearchLoopSiteView", () => {
  beforeEach(() => {
    document.body.replaceChildren();
    delete (document as any).createXULElement;
  });

  it("lazily loads the deployed site in a native Zotero browser", () => {
    const browser = document.createElement("browser") as HTMLElement & { reload(): void };
    browser.reload = vi.fn();
    const createXULElement = vi.fn(() => browser);
    (document as any).createXULElement = createXULElement;
    const host = document.createElement("div");
    document.body.appendChild(host);
    const onBack = vi.fn();
    const view = new ResearchLoopSiteView(host, { onBack });

    expect(host.querySelector("browser")).toBeNull();
    expect(view.isVisible()).toBe(false);

    view.show();

    expect(createXULElement).toHaveBeenCalledWith("browser");
    expect(browser.getAttribute("type")).toBe("content");
    expect(browser.getAttribute("remote")).toBe("true");
    expect(browser.getAttribute("maychangeremoteness")).toBe("true");
    expect(browser.getAttribute("src")).toBe(RESEARCH_LOOP_SITE_URL);
    expect(view.isVisible()).toBe(true);

    host.querySelector<HTMLButtonElement>(".zc-main-site-refresh")!.click();
    expect(browser.reload).toHaveBeenCalledOnce();
    host.querySelector<HTMLButtonElement>(".zc-main-site-back")!.click();
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("shows a clear fallback when the native browser factory is unavailable", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const view = new ResearchLoopSiteView(host, { onBack: vi.fn() });

    view.show();

    expect(host.textContent).toContain("The native Zotero browser is unavailable");
  });

  it("hands the knowledge page the browser is showing to the workspace", async () => {
    const browser = document.createElement("browser") as any;
    browser.currentURI = {
      spec: "http://127.0.0.1:4180/knowledge/models/hubbard/MODEL.html",
    };
    browser.addProgressListener = vi.fn((listener: any) => {
      listener.onLocationChange(null, null, browser.currentURI);
    });
    (document as any).createXULElement = vi.fn(() => browser);
    const onOpenDocument = vi.fn();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const view = new ResearchLoopSiteView(host, { onBack: vi.fn(), onOpenDocument });

    view.show();
    const source = host.querySelector<HTMLButtonElement>(".zc-main-site-source")!;
    expect(source.disabled).toBe(false);
    source.click();

    expect(onOpenDocument).toHaveBeenCalledWith("knowledge/models/hubbard/MODEL.qmd");
    // This view browses; it never hosts an editor of its own.
    expect(host.querySelector(".cm-content")).toBeNull();
    expect(view.isVisible()).toBe(true);
  });

  it("re-reads currentURI on click when Zotero does not send a location callback", () => {
    const browser = document.createElement("browser") as any;
    browser.currentURI = { spec: RESEARCH_LOOP_SITE_URL };
    browser.addProgressListener = vi.fn();
    (document as any).createXULElement = vi.fn(() => browser);
    const onOpenDocument = vi.fn();
    const host = document.createElement("div");
    document.body.appendChild(host);
    const view = new ResearchLoopSiteView(host, { onBack: vi.fn(), onOpenDocument });

    view.show();
    expect(host.querySelector<HTMLButtonElement>(".zc-main-site-source")!.disabled).toBe(false);

    browser.currentURI = {
      spec: "http://127.0.0.1:4180/knowledge/models/hubbard/MODEL.html",
    };
    host.querySelector<HTMLButtonElement>(".zc-main-site-source")!.click();

    expect(onOpenDocument).toHaveBeenCalledWith("knowledge/models/hubbard/MODEL.qmd");
  });

  it("shows visible feedback when Source is clicked outside Knowledge", () => {
    const browser = document.createElement("browser") as any;
    browser.currentURI = { spec: RESEARCH_LOOP_SITE_URL };
    (document as any).createXULElement = vi.fn(() => browser);
    const host = document.createElement("div");
    document.body.appendChild(host);
    const view = new ResearchLoopSiteView(host, {
      onBack: vi.fn(),
      onOpenDocument: vi.fn(),
    });

    view.show();
    const source = host.querySelector<HTMLButtonElement>(".zc-main-site-source")!;
    source.click();

    expect(source.textContent).toBe("Open a Knowledge page first");
    expect(source.title).toBe("The current page has no corresponding QMD source");
    expect(host.querySelector(".zc-main-site-address")?.textContent)
      .toBe("The current page has no corresponding QMD source");
  });
});

describe("ResearchLoopSiteService", () => {
  it("reuses an already-running site without spawning another process", async () => {
    const runtime = {
      check: vi.fn(async () => true),
      repositoryState: vi.fn(async () => "ready"),
      initialize: vi.fn(),
      startBridge: vi.fn(),
      spawn: vi.fn(),
      sleep: vi.fn(),
    };
    const service = new ResearchLoopSiteService(runtime as any);

    await service.deploy("/Users/research/research-loop");

    expect(runtime.startBridge).not.toHaveBeenCalled();
    expect(runtime.spawn).not.toHaveBeenCalled();
  });

  it("builds, starts, and waits for an unavailable site", async () => {
    const runtime = {
      check: vi.fn()
        .mockResolvedValueOnce(false)
        .mockResolvedValueOnce(false)
        .mockResolvedValueOnce(true),
      startBridge: vi.fn(async () => undefined),
      repositoryState: vi.fn(async () => "ready"),
      initialize: vi.fn(),
      hasBuild: vi.fn(async () => false),
      listen: vi.fn(() => () => {}),
      spawn: vi.fn(async () => undefined),
      sleep: vi.fn(async () => undefined),
    };
    const service = new ResearchLoopSiteService(runtime as any);

    await service.deploy("/Users/research/research-loop");

    expect(runtime.startBridge).toHaveBeenCalledOnce();
    expect(runtime.spawn).toHaveBeenCalledWith(
      "research-loop-site",
      expect.objectContaining({
        argv: expect.arrayContaining(["/bin/zsh", "/Users/research/research-loop"]),
        cwd: "/Users/research/research-loop",
      }),
    );
    expect(runtime.sleep).toHaveBeenCalled();
  });

  it("reuses an existing production build instead of rebuilding 139 knowledge pages", async () => {
    const progress = vi.fn();
    const runtime = {
      check: vi.fn()
        .mockResolvedValueOnce(false)
        .mockResolvedValueOnce(true),
      hasBuild: vi.fn(async () => true),
      repositoryState: vi.fn(async () => "ready"),
      initialize: vi.fn(),
      startBridge: vi.fn(async () => undefined),
      listen: vi.fn(() => () => {}),
      spawn: vi.fn(async () => undefined),
      sleep: vi.fn(async () => undefined),
    };
    const service = new ResearchLoopSiteService(runtime as any);

    await service.deploy("/repo", progress);

    expect(progress).toHaveBeenCalledWith("Starting the existing main site…");
    const script = (runtime.spawn as any).mock.calls[0][1].argv[2] as string;
    expect(script).toContain('if [ ! -f "$1/dist/server/index.js" ]');
    expect(script).toContain('if [ ! -f "$1/node_modules/.package-lock.json" ]');
    expect(script).toContain("Research Loop requires Node.js and npm");
    expect(script).toContain("Research Loop requires Quarto");
    expect(script).toContain("npm ci");
    expect(script).toContain("npm run build");
  });

  it.each(["empty", "partial"] as const)(
    "initializes a %s content directory before installing and starting the site",
    async (repositoryState) => {
      const progress = vi.fn();
      const runtime = {
        check: vi.fn()
          .mockResolvedValueOnce(false)
          .mockResolvedValueOnce(true),
        repositoryState: vi.fn(async () => repositoryState),
        initialize: vi.fn(async () => undefined),
        hasBuild: vi.fn(async () => false),
        startBridge: vi.fn(async () => undefined),
        listen: vi.fn(() => () => {}),
        spawn: vi.fn(async () => undefined),
        sleep: vi.fn(async () => undefined),
      };
      const service = new ResearchLoopSiteService(runtime as any);

      await service.deploy("/repo", progress);

      expect(runtime.initialize).toHaveBeenCalledWith("/repo");
      expect(progress).toHaveBeenCalledWith(repositoryState === "empty"
        ? "Initializing Research Loop…"
        : "Completing the Research Loop structure…");
    },
  );

  it("refuses a non-empty unrelated directory without starting any process", async () => {
    const runtime = {
      repositoryState: vi.fn(async () => "incompatible"),
      initialize: vi.fn(),
      check: vi.fn(async () => false),
      startBridge: vi.fn(),
      spawn: vi.fn(),
    };
    const service = new ResearchLoopSiteService(runtime as any);

    await expect(service.deploy("/documents")).rejects.toThrow("contains files");
    expect(runtime.initialize).not.toHaveBeenCalled();
    expect(runtime.spawn).not.toHaveBeenCalled();
  });

  it("rejects deployment when no repository is selected", async () => {
    const service = new ResearchLoopSiteService({ check: vi.fn(async () => false) } as any);
    await expect(service.deploy("")).rejects.toThrow("Choose a Research Loop repository first");
  });
});

describe("researchLoopBuildProgress", () => {
  it("turns long Quarto and Vinext output into concise user progress", () => {
    expect(researchLoopBuildProgress("[ 42/139] QEC/index.qmd"))
      .toBe("Building Knowledge 42/139…");
    expect(researchLoopBuildProgress("> research-loop@0.1.0 build:app"))
      .toBe("Building the main-site application…");
    expect(researchLoopBuildProgress("[research-loop] installing dependencies"))
      .toBe("Installing main-site dependencies…");
    expect(researchLoopBuildProgress("Build complete. Run `vinext start`"))
      .toBe("Build complete; starting the main site…");
  });
});
