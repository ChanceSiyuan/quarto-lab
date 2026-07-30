// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";
import { EDITOR_TREES } from "../src/editor-tree";
import {
  QmdRenderService,
  createQmdDiff,
  type QmdRenderProcess,
  type QmdRenderRuntime,
} from "../src/qmd-render";

const KNOWLEDGE = EDITOR_TREES.find((tree) => tree.id === "knowledge")!;
const DRAFTS = EDITOR_TREES.find((tree) => tree.id === "drafts")!;

interface StartCall {
  treeId: string;
  repoRoot: string;
  relativePath: string;
  port: number;
}

function fakeRuntime(): QmdRenderRuntime & {
  started: StartCall[];
  stopped: () => number;
  setReady(ready: boolean): void;
} {
  const started: StartCall[] = [];
  let stopped = 0;
  let ready = true;
  return {
    started,
    stopped: () => stopped,
    setReady(value) { ready = value; },
    async start(tree, repoRoot, relativePath, port): Promise<QmdRenderProcess> {
      started.push({ treeId: tree.id, repoRoot, relativePath, port });
      return {
        url: `http://127.0.0.1:${port}/`,
        stop: () => { stopped += 1; },
        diagnostic: () => null,
        ready: async () => ready,
      };
    },
    async validate() { return { ok: true, output: "knowledge: the trusted tree is valid" }; },
    async checkDraft() { return { ok: true, diagnostics: [] }; },
    async diff() { return "--- a\n+++ b\n"; },
  };
}

describe("QmdRenderService", () => {
  it("starts one process per document and returns the served page URL", async () => {
    const runtime = fakeRuntime();
    const service = new QmdRenderService(runtime, () => 44_100);

    const url = await service.open(KNOWLEDGE, "/repo", "knowledge/Magic/Bell_magic.qmd");

    expect(url).toBe("http://127.0.0.1:44100/Magic/Bell_magic.html");
    expect(runtime.started).toEqual([{
      treeId: "knowledge",
      repoRoot: "/repo",
      relativePath: "knowledge/Magic/Bell_magic.qmd",
      port: 44_100,
    }]);
  });

  it("serves a draft from its own tree", async () => {
    const runtime = fakeRuntime();
    const service = new QmdRenderService(runtime, () => 44_200);
    expect(await service.open(DRAFTS, "/repo", "drafts/Dynamics/floquet.qmd"))
      .toBe("http://127.0.0.1:44200/Dynamics/floquet.html");
  });

  it("reuses the running process when the same document is reopened", async () => {
    const runtime = fakeRuntime();
    const service = new QmdRenderService(runtime, () => 44_300);
    await service.open(KNOWLEDGE, "/repo", "knowledge/a.qmd");
    await service.open(KNOWLEDGE, "/repo", "knowledge/a.qmd");
    expect(runtime.started.length).toBe(1);
    expect(runtime.stopped()).toBe(0);
  });

  it("restarts a cached preview whose loopback server has disappeared", async () => {
    const runtime = fakeRuntime();
    const service = new QmdRenderService(runtime, () => 44_301);
    await service.open(DRAFTS, "/repo", "drafts/a.qmd");
    runtime.setReady(false);

    await service.open(DRAFTS, "/repo", "drafts/a.qmd");

    expect(runtime.stopped()).toBe(1);
    expect(runtime.started).toHaveLength(2);
  });

  it("rejects a cached readiness request superseded by another document", async () => {
    let resolveReadyA!: (ready: boolean) => void;
    const readyA = new Promise<boolean>((resolve) => { resolveReadyA = resolve; });
    let resolveStartB!: (process: QmdRenderProcess) => void;
    const runtime: QmdRenderRuntime = {
      start: vi.fn(async (_tree, _root, relativePath) => {
        if (relativePath === "knowledge/a.qmd") {
          return {
            url: "http://127.0.0.1/a/",
            stop: () => {},
            diagnostic: () => null,
            ready: () => readyA,
          };
        }
        return new Promise<QmdRenderProcess>((resolve) => { resolveStartB = resolve; });
      }),
      async validate() { return { ok: true, output: "ok" }; },
      async checkDraft() { return { ok: true, diagnostics: [] }; },
      async diff() { return ""; },
    };
    const service = new QmdRenderService(runtime, () => 44_301);

    await service.open(KNOWLEDGE, "/repo", "knowledge/a.qmd");
    const stale = service.open(KNOWLEDGE, "/repo", "knowledge/a.qmd");
    const latest = service.open(KNOWLEDGE, "/repo", "knowledge/b.qmd");
    resolveReadyA(true);

    await expect(stale).rejects.toThrow(/superseded/i);
    resolveStartB({
      url: "http://127.0.0.1/b/",
      stop: () => {},
      diagnostic: () => null,
      ready: async () => true,
    });
    await expect(latest).resolves.toContain("/b.html");
  });

  it("stops the previous process before starting another document", async () => {
    const runtime = fakeRuntime();
    const service = new QmdRenderService(runtime, () => 44_300);
    await service.open(KNOWLEDGE, "/repo", "knowledge/a.qmd");
    await service.open(KNOWLEDGE, "/repo", "knowledge/b.qmd");
    expect(runtime.stopped()).toBe(1);
    service.stop();
    expect(runtime.stopped()).toBe(2);
  });

  it("discards a stale process when a newer render finishes first", async () => {
    const resolvers = new Map<string, (process: QmdRenderProcess) => void>();
    const stopped: string[] = [];
    const runtime: QmdRenderRuntime = {
      start: vi.fn(async (_tree, _root, relativePath) =>
        new Promise<QmdRenderProcess>((resolve) => resolvers.set(relativePath, resolve))),
      async validate() { return { ok: true, output: "ok" }; },
      async checkDraft() { return { ok: true, diagnostics: [] }; },
      async diff() { return ""; },
    };
    const processFor = (name: string): QmdRenderProcess => ({
      url: `http://127.0.0.1/${name}/`,
      stop: () => stopped.push(name),
      diagnostic: () => null,
      ready: async () => true,
    });
    const service = new QmdRenderService(runtime, () => 44_302);

    const first = service.open(KNOWLEDGE, "/repo", "knowledge/a.qmd");
    const second = service.open(KNOWLEDGE, "/repo", "knowledge/b.qmd");
    resolvers.get("knowledge/b.qmd")!(processFor("b"));
    await expect(second).resolves.toContain("/b.html");
    resolvers.get("knowledge/a.qmd")!(processFor("a"));
    await expect(first).rejects.toThrow(/superseded/i);

    expect(stopped).toEqual(["a"]);
    service.stop();
    expect(stopped).toEqual(["a", "b"]);
  });

  it("stops nothing when nothing is running, however often it is asked", () => {
    const runtime = fakeRuntime();
    const service = new QmdRenderService(runtime, () => 44_400);
    expect(() => { service.stop(); service.stop(); }).not.toThrow();
    expect(runtime.stopped()).toBe(0);
  });

  it("leaves no process running when a start fails", async () => {
    const runtime = fakeRuntime();
    const failing: QmdRenderRuntime = {
      ...runtime,
      start: vi.fn(async () => { throw new Error("Quarto preview startup timed out"); }),
    };
    const service = new QmdRenderService(failing, () => 44_500);
    await expect(service.open(KNOWLEDGE, "/repo", "knowledge/a.qmd")).rejects.toThrow("timed out");
    expect(service.running()).toBe(false);
  });

  it("runs only the validation command a tree actually has", async () => {
    const runtime = fakeRuntime();
    const validate = vi.spyOn(runtime, "validate");
    const service = new QmdRenderService(runtime, () => 44_600);

    expect(await service.validate(KNOWLEDGE, "/repo")).toEqual({
      ok: true,
      output: "knowledge: the trusted tree is valid",
    });
    expect(validate).toHaveBeenCalledWith("/repo", "npm run knowledge:check");

    expect(await service.validate(DRAFTS, "/repo")).toBeNull();
    expect(validate).toHaveBeenCalledOnce();
  });

  it("checks one draft without coupling the check to the preview process", async () => {
    const runtime = fakeRuntime();
    const checkDraft = vi.spyOn(runtime, "checkDraft").mockResolvedValue({
      ok: false,
      diagnostics: [{ code: "CATEGORY_REQUIRED", message: "category is missing", line: 1 }],
    });
    const service = new QmdRenderService(runtime, () => 44_700);

    await expect(service.checkDraft("/repo", "drafts/a.qmd")).resolves.toEqual({
      ok: false,
      diagnostics: [{ code: "CATEGORY_REQUIRED", message: "category is missing", line: 1 }],
    });
    expect(checkDraft).toHaveBeenCalledWith("/repo", "drafts/a.qmd");
    expect(service.running()).toBe(false);
  });
});

describe("createQmdDiff", () => {
  it("reports no change and otherwise shows the changed lines in context", () => {
    expect(createQmdDiff("a.qmd", "same\n", "same\n")).toBe("No changes in a.qmd.");
    const diff = createQmdDiff("a.qmd", "one\ntwo\n", "one\nTWO\n");
    expect(diff).toContain("--- a/a.qmd");
    expect(diff).toContain("+++ b/a.qmd");
    expect(diff).toContain("-two");
    expect(diff).toContain("+TWO");
  });
});
