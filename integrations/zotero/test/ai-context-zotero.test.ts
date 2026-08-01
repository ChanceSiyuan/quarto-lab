import { readFileSync } from "node:fs";
import { expect, it, vi } from "vitest";
import {
  AIContextProjectionError,
  AIContextService,
  parseAIContextDocument,
  renderNewAIContextDocument,
  type AIContextDocument,
  type AIContextGenerator,
  type AIContextManifest,
  type AIContextPaper,
  type AIContextSynthesis,
} from "../src/ai-context";
import {
  AIContextRecoveryRequiredError,
  createGeckoZoteroAIContextRuntime,
  createZoteroAIContextHost,
  isQuickAIContextAttachmentCandidate,
  normalizeAIContextTargets,
  resolveAIContextAttachment,
  type ZoteroAIContextRuntime,
} from "../src/ai-context-zotero";

function regular(itemKey: string, libraryID: number, id = itemKey === "P1" ? 11 : 12) {
  return {
    id, key: itemKey, libraryID, itemType: "journalArticle",
    isRegularItem: () => true,
    isEditable: () => true,
    getField: (name: string) => name === "title" ? `Title ${itemKey}` : "",
    getCreators: () => [],
    getAttachments: () => [],
  };
}

function papers(...itemKeys: string[]): AIContextPaper[] {
  return itemKeys.map((itemKey) => ({ libraryID: "1", itemKey, title: `Title ${itemKey}` }));
}

function manifestFor(overrides: Partial<AIContextManifest> = {}): AIContextManifest {
  return {
    schemaVersion: 1,
    id: "ctx-1",
    contextKey: "conversation:thread-1",
    kind: "conversation",
    sourceThreadId: "thread-1",
    createdAt: "2026-07-31T00:00:00.000Z",
    updatedAt: "2026-07-31T00:00:00.000Z",
    status: "active",
    papers: papers("P1"),
    projection: { mode: "attached", targets: [{ libraryID: "1", itemKey: "P1" }] },
    capturedEntryIds: [],
    ...overrides,
  };
}

function validReadingSynthesis(itemKeys: string[]): AIContextSynthesis {
  return {
    title: "Shared reading",
    description: "A resumable reading plan.",
    category: "theory",
    status: "active",
    memoryMarkdown: "memory",
    progressMarkdown: "not started",
    nextStepMarkdown: `read ${itemKeys[0] ?? "the first source"}`,
    readingPlan: itemKeys.map((itemKey) => ({
      itemKey,
      rationale: `read ${itemKey} next`,
      guidance: `inspect ${itemKey}`,
    })),
  };
}

function attachedDocument(...itemKeys: string[]): AIContextDocument {
  const selected = papers(...itemKeys);
  const source = renderNewAIContextDocument({
    manifest: manifestFor({
      id: "ctx-shared",
      contextKey: "reading:ctx-shared",
      kind: "reading",
      sourceThreadId: null,
      papers: selected,
      projection: { mode: "attached", targets: selected.map(({ libraryID, itemKey }) => ({ libraryID, itemKey })) },
    }),
    synthesis: validReadingSynthesis(itemKeys),
    messages: [],
  });
  return parseAIContextDocument("drafts/ai-contexts/ctx-shared.qmd", source);
}

function standaloneDocument(id: string): AIContextDocument {
  const manifest = manifestFor({
    id,
    contextKey: `standalone:${id}`,
    papers: [],
    projection: { mode: "standalone", targets: [] },
  });
  const synthesis = { ...validReadingSynthesis([]), title: "Open questions", readingPlan: [], nextStepMarkdown: "Start a conversation." };
  const relativePath = `drafts/ai-contexts/${id}.qmd`;
  return parseAIContextDocument(relativePath, renderNewAIContextDocument({ manifest, synthesis, messages: [] }));
}

function neverGenerator(): AIContextGenerator {
  return {
    generate: vi.fn(async () => {
      throw new Error("repair must not synthesize");
    }),
  };
}

const fixedEnvironment = () => ({
  now: () => "2026-07-31T00:00:00.000Z",
  id: () => "unused-during-repair",
});

function zoteroRuntime(options: {
  userLibraryID: number;
  items?: any[];
  existingDrafts?: string[];
}) {
  const root = "/repo";
  const files = new Map<string, string>();
  for (const [index, source] of (options.existingDrafts ?? []).entries()) {
    const parsed = parseAIContextDocument(`drafts/ai-contexts/existing-${index}.qmd`, source);
    files.set(`${root}/${parsed.relativePath}`, source);
  }
  const items = options.items ?? [];
  const attachments: any[] = [];
  const symlinks = new Set<string>();
  let token = 0;
  const sha256 = vi.fn(async (source: string) => `sha256:${source}`);
  const linkFromFile = vi.fn(async ({ file, parentItemID }: { file: string; parentItemID?: number }) => {
    const attachment = {
      id: 100 + attachments.length,
      key: `LINK${attachments.length}`,
      libraryID: options.userLibraryID,
      parentID: parentItemID ?? null,
      path: file,
      title: "",
    };
    attachments.push(attachment);
    return attachment;
  });
  return {
    files,
    linkFromFile,
    root: () => root,
    userLibraryID: () => options.userLibraryID,
    listChildren: vi.fn(async (path: string) => [...files.keys()].filter((value) => value.startsWith(`${path}/`))),
    exists: vi.fn(async (path: string) => path === root || path === `${root}/drafts` || path === `${root}/drafts/ai-contexts` || files.has(path)),
    makeDirectory: vi.fn(async (_path: string, options: { createAncestors: false }) => {
      expect(options).toEqual({ createAncestors: false });
    }),
    readUTF8: vi.fn(async (path: string) => files.get(path) ?? ""),
    sha256,
    uniqueToken: () => `token-${token++}`,
    recoverCASArtifacts: vi.fn(async () => undefined),
    writeAtomic: vi.fn(async (path: string, source: string, expectedRevision: string | null) => {
      const current = files.get(path);
      const revision = current === undefined ? null : await sha256(current);
      if (revision !== expectedRevision) return false;
      files.set(path, source);
      return true;
    }),
    canonical: vi.fn((path: string, allowMissingFinal = false) => {
      const components = path.split("/").filter(Boolean);
      let current = "";
      for (const component of components) {
        current += `/${component}`;
        if (symlinks.has(current)) throw new Error(`symlink component: ${current}`);
      }
      if (!allowMissingFinal && !files.has(path) && path !== root
        && path !== `${root}/drafts` && path !== `${root}/drafts/ai-contexts`) {
        throw new Error(`missing path: ${path}`);
      }
      return path;
    }),
    itemByID: vi.fn(async (id: number) => items.find((item) => item.id === id)),
    itemByLibraryAndKey: vi.fn(async (libraryID: number | string, itemKey: string) => items.find(
      (item) => String(item.libraryID) === String(libraryID) && item.key === itemKey,
    )),
    attachmentsFor: vi.fn(async (parent: any) => attachments.filter((item) => item.parentID === parent.id)),
    topLevelAttachments: async (libraryID: number | string) => attachments.filter(
      (item) => item.parentID === null && String(item.libraryID) === String(libraryID),
    ),
    attachmentPath: (attachment: any) => attachment.path ?? attachment.getFilePath?.() ?? null,
    attachmentTitle: (attachment: any) => attachment.title ?? attachment.getField?.("title") ?? "",
    saveAttachmentTitle: vi.fn(async (attachment: any, title: string) => { attachment.title = title; }),
    attachments,
    symlinks,
  } satisfies ZoteroAIContextRuntime & {
    files: Map<string, string>;
    attachments: any[];
    symlinks: Set<string>;
  };
}

function fakeDigest(source: string): string {
  let hash = 2_166_136_261;
  for (const character of source) hash = Math.imul(hash ^ character.codePointAt(0)!, 16_777_619) >>> 0;
  return hash.toString(16).padStart(8, "0").repeat(8);
}

function geckoCASHarness(race: "none" | "concurrent-target" | "pre-linearization") {
  const files = new Map<string, string>();
  const directories = new Set(["/", "/repo", "/repo/drafts", "/repo/drafts/ai-contexts"]);
  class FakeFile {
    path = "";
    initWithPath(path: string) { this.path = path; }
    clone() { const copy = new FakeFile(); copy.path = this.path; return copy; }
    exists() { return directories.has(this.path) || files.has(this.path); }
    isSymlink() { return false; }
    normalize() {}
    get leafName() { return this.path.split("/").filter(Boolean).at(-1) ?? ""; }
    get parent() {
      const parent = new FakeFile();
      parent.path = this.path === "/" ? "/" : this.path.slice(0, this.path.lastIndexOf("/")) || "/";
      return parent;
    }
  }
  const IOUtils = {
    exists: async (path: string) => directories.has(path) || files.has(path),
    readUTF8: async (path: string) => files.get(path)!,
    writeUTF8: async (path: string, source: string) => { files.set(path, source); },
    setPermissions: vi.fn(async () => undefined),
    remove: async (path: string) => { files.delete(path); },
    getChildren: async (path: string) => [...files.keys()].filter((entry) => entry.startsWith(`${path}/`)),
    makeDirectory: async (path: string) => { directories.add(path); },
    move: async (source: string, target: string, options: { noOverwrite: true }) => {
      expect(options).toEqual({ noOverwrite: true });
      if (files.has(target)) throw new Error("target exists");
      if (race === "pre-linearization" && source.endsWith("/ctx.qmd")
        && target.includes(".qlab-cas-backup-")) {
        files.set(source, "pre-linearization bytes");
      }
      const bytes = files.get(source);
      if (bytes === undefined) throw new Error("source missing");
      files.delete(source);
      files.set(target, bytes);
      if (source.endsWith("/ctx.qmd") && target.includes(".qlab-cas-backup-")) {
        if (race === "concurrent-target") files.set(source, "concurrent bytes");
      }
    },
  };
  const Zotero: any = {
    Libraries: { userLibraryID: 1 },
    Utilities: { randomString: () => "TOKEN" },
    Items: {}, Attachments: {},
  };
  const runtime = createGeckoZoteroAIContextRuntime({
    Zotero,
    IOUtils,
    PathUtils: { join: (...parts: string[]) => parts.join("/").replace(/\/+/gu, "/") },
    Components: {
      classes: { "@mozilla.org/file/local;1": { createInstance: () => new FakeFile() } },
      interfaces: { nsIFile: {} },
    },
    root: () => "/repo",
    hashBytes: (bytes) => fakeDigest(new TextDecoder().decode(bytes)),
  });
  return { directories, files, runtime, Zotero };
}

it("rejects every target before a utility turn when one parent is outside the user library", async () => {
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [regular("P1", 1), regular("P2", 2)] });
  const host = createZoteroAIContextHost(runtime);
  await expect(host.preflight({
    mode: "attached",
    targets: [{ libraryID: "1", itemKey: "P1" }, { libraryID: "2", itemKey: "P2" }],
  }, papers("P1", "P2"))).rejects.toThrow(/P2.*local user library/i);
  expect(runtime.linkFromFile).not.toHaveBeenCalled();
});

it("projects the same canonical qmd path once beneath each parent and reuses it on rerun", async () => {
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [regular("P1", 1), regular("P2", 1)] });
  const host = createZoteroAIContextHost(runtime);
  const document = attachedDocument("P1", "P2");
  await host.project(document);
  await host.project(document);
  expect(runtime.linkFromFile).toHaveBeenCalledTimes(2);
  expect(runtime.linkFromFile.mock.calls.map(([value]) => value.parentItemID)).toEqual([11, 12]);
  expect(new Set(runtime.linkFromFile.mock.calls.map(([value]) => value.file)).size).toBe(1);
});

it("creates and repairs a top-level standalone projection after restart", async () => {
  const standalone = standaloneDocument("standalone-1");
  const runtime = zoteroRuntime({ userLibraryID: 1, existingDrafts: [standalone.source] });
  const host = createZoteroAIContextHost(runtime);
  const pending = await new AIContextService(host, neverGenerator(), fixedEnvironment()).pendingRepairs();
  expect(pending.map(({ document }) => document.manifest.id)).toEqual(["standalone-1"]);
  await host.project(pending[0]!.document);
  expect(runtime.linkFromFile).toHaveBeenCalledWith({ file: expect.stringMatching(/\.qmd$/) });
});

it.each([
  [0, false],
  [1, true],
  [50, true],
  [51, false],
])("normalizes %i selected regular parents with the 1..50 boundary", async (count, valid) => {
  const items = Array.from({ length: count }, (_, index) => regular(`P${index + 1}`, 1, index + 1));
  const runtime = zoteroRuntime({ userLibraryID: 1, items });
  const operation = normalizeAIContextTargets(runtime, items);
  if (valid) await expect(operation).resolves.toHaveLength(count);
  else await expect(operation).rejects.toThrow(/1\.\.50/);
});

it("collapses duplicate parents and resolves an unloaded PDF child through Items.getAsync", async () => {
  const parent = regular("P1", 1, 11);
  const pdf = {
    id: 21, key: "PDF1", libraryID: 1, parentID: 11,
    isAttachment: () => true,
    isPDFAttachment: () => true,
  };
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [parent, pdf] });
  runtime.itemByID = vi.fn(async () => parent);
  await expect(normalizeAIContextTargets(runtime, [pdf, parent])).resolves.toEqual([
    expect.objectContaining({ itemKey: "P1" }),
  ]);
  expect(runtime.itemByID).toHaveBeenCalledWith(11);
});

it.each([
  ["missing", undefined],
  ["non-regular", { ...regular("P1", 1), isRegularItem: () => false }],
  ["non-editable", { ...regular("P1", 1), isEditable: () => false }],
  ["group", regular("P1", 2)],
  ["non-PDF attachment", {
    id: 21, key: "A1", libraryID: 1, parentID: 11,
    isAttachment: () => true, isPDFAttachment: () => false,
  }],
])("rejects a %s target", async (_label, selected) => {
  const runtime = zoteroRuntime({ userLibraryID: 1, items: selected ? [selected] : [] });
  await expect(normalizeAIContextTargets(runtime, [selected])).rejects.toThrow();
});

it("rejects a mixed local/group selection as one preflight transaction", async () => {
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [regular("P1", 1), regular("P2", 2)] });
  await expect(createZoteroAIContextHost(runtime).preflight({
    mode: "attached",
    targets: [{ libraryID: "1", itemKey: "P1" }, { libraryID: "2", itemKey: "P2" }],
  }, papers("P1", "P2"))).rejects.toThrow(/P2.*local user library/i);
  expect(runtime.linkFromFile).not.toHaveBeenCalled();
});

it("implements expected-absent and stale-revision CAS without overwriting", async () => {
  const runtime = zoteroRuntime({ userLibraryID: 1 });
  const host = createZoteroAIContextHost(runtime);
  const document = standaloneDocument("cas-1");
  expect(await host.compareAndSwap(document.relativePath, null, document.source)).toBe(true);
  const committed = runtime.files.get(`/repo/${document.relativePath}`)!;
  expect(await host.compareAndSwap(document.relativePath, "stale", `${document.source}\nchanged`)).toBe(false);
  expect(runtime.files.get(`/repo/${document.relativePath}`)).toBe(committed);
});

it("quarantine CAS retains its recovery backup after a successful replacement", async () => {
  const { files, runtime } = geckoCASHarness("none");
  const target = "/repo/drafts/ai-contexts/ctx.qmd";
  files.set(target, "old bytes");
  await expect(runtime.writeAtomic(target, "agent bytes", fakeDigest("old bytes"))).resolves.toBe(true);
  expect(files.get(target)).toBe("agent bytes");
  const backups = [...files].filter(([path]) => path.includes(".qlab-cas-backup-"));
  expect(backups).toEqual([[expect.stringContaining(".qlab-cas-backup-"), "old bytes"]]);
});

it("restores an unchanged orphan after a crash between quarantine and publish", async () => {
  const { files, runtime } = geckoCASHarness("none");
  const document = standaloneDocument("ctx");
  const target = "/repo/drafts/ai-contexts/ctx.qmd";
  const revision = fakeDigest(document.source);
  const replacementRevision = fakeDigest(`${document.source}\nplanned replacement`);
  const artifact = `${target}.qlab-cas-backup-${revision}-${replacementRevision}-CRASH`;
  files.set(artifact, document.source);

  await expect(createZoteroAIContextHost(runtime).snapshot("drafts/ai-contexts/ctx.qmd"))
    .resolves.toEqual(expect.objectContaining({ source: document.source, revision }));
  expect(files.get(target)).toBe(document.source);
  expect(files.has(artifact)).toBe(false);
});

it("preserves a post-linearization open-FD write and surfaces it on the next operation", async () => {
  const { files, runtime } = geckoCASHarness("none");
  const target = "/repo/drafts/ai-contexts/ctx.qmd";
  files.set(target, "old bytes");
  await expect(runtime.writeAtomic(target, "agent bytes", fakeDigest("old bytes"))).resolves.toBe(true);
  const artifact = [...files.keys()].find((path) => path.includes(".qlab-cas-backup-"))!;

  // This models a descriptor opened before rename writing its now-quarantined
  // inode after writeAtomic already returned success.
  files.set(artifact, "late open-FD bytes");
  const error = await runtime.recoverCASArtifacts("/repo/drafts/ai-contexts")
    .catch((caught) => caught);
  expect(error).toBeInstanceOf(AIContextRecoveryRequiredError);
  expect(error).toMatchObject({
    name: "AIContextRecoveryRequiredError",
    artifactPath: artifact,
  });
  expect(files.get(target)).toBe("agent bytes");
  expect(files.get(artifact)).toBe("late open-FD bytes");
});

it("preserves concurrent target bytes and quarantine when a target appears after quarantine", async () => {
  const { files, runtime } = geckoCASHarness("concurrent-target");
  const target = "/repo/drafts/ai-contexts/ctx.qmd";
  files.set(target, "old bytes");
  await expect(runtime.writeAtomic(target, "agent bytes", fakeDigest("old bytes"))).resolves.toBe(false);
  expect(files.get(target)).toBe("concurrent bytes");
  expect([...files.values()]).toContain("old bytes");
  expect([...files.values()]).not.toContain("agent bytes");
});

it("rolls back a mutation racing before the target-to-quarantine linearization point", async () => {
  const { files, runtime } = geckoCASHarness("pre-linearization");
  const target = "/repo/drafts/ai-contexts/ctx.qmd";
  files.set(target, "old bytes");
  await expect(runtime.writeAtomic(target, "agent bytes", fakeDigest("old bytes"))).resolves.toBe(false);
  expect(files.get(target)).toBe("pre-linearization bytes");
  expect([...files.values()]).not.toContain("agent bytes");
});

it("expected-absent CAS publishes with noOverwrite and preserves a concurrent creator", async () => {
  const { files, runtime } = geckoCASHarness("none");
  const target = "/repo/drafts/ai-contexts/ctx.qmd";
  files.set(target, "concurrent creator bytes");
  await expect(runtime.writeAtomic(target, "agent bytes", null)).resolves.toBe(false);
  expect(files.get(target)).toBe("concurrent creator bytes");
});

it("returns an absent snapshot when both safe trailing directories do not exist", async () => {
  const { directories, runtime } = geckoCASHarness("none");
  directories.delete("/repo/drafts/ai-contexts");
  directories.delete("/repo/drafts");
  await expect(createZoteroAIContextHost(runtime).snapshot("drafts/ai-contexts/new.qmd"))
    .resolves.toEqual({
      relativePath: "drafts/ai-contexts/new.qmd",
      source: null,
      revision: null,
    });
});

it("prefers and awaits Zotero.Items.getByLibraryAndKeyAsync", async () => {
  const { runtime, Zotero } = geckoCASHarness("none");
  const expected = regular("P1", 1, 11);
  Zotero.Items.getByLibraryAndKeyAsync = vi.fn(async () => expected);
  Zotero.Items.getByLibraryAndKey = vi.fn(() => { throw new Error("sync fallback must not run"); });
  await expect(runtime.itemByLibraryAndKey("1", "P1")).resolves.toBe(expected);
  expect(Zotero.Items.getByLibraryAndKeyAsync).toHaveBeenCalledWith("1", "P1");
  expect(Zotero.Items.getByLibraryAndKey).not.toHaveBeenCalled();
});

it("loads uncached attachment children through Zotero.Items.getAsync", async () => {
  const { runtime, Zotero } = geckoCASHarness("none");
  const attachment = { key: "A1" };
  Zotero.Items.getAsync = vi.fn(async (ids: number[]) => {
    expect(ids).toEqual([101]);
    return [attachment];
  });
  await expect(runtime.attachmentsFor({ getAttachments: () => [101] }))
    .resolves.toEqual([attachment]);
  expect(Zotero.Items.getAsync).toHaveBeenCalledOnce();
});

it("gitignores only AI Context CAS recovery artifacts", () => {
  const ignore = readFileSync(new URL("../../../.gitignore", import.meta.url), "utf8");
  expect(ignore.split(/\r?\n/gu)).toContain("/drafts/ai-contexts/*.qlab-cas-*");
});

it.each([
  ["root", "/repo"],
  ["intermediate", "/repo/drafts"],
])("rejects a %s symlink before reading or writing", async (_label, symlink) => {
  const runtime = zoteroRuntime({ userLibraryID: 1 });
  runtime.symlinks.add(symlink);
  await expect(createZoteroAIContextHost(runtime).snapshot("drafts/ai-contexts/x.qmd"))
    .rejects.toThrow(/symlink/);
});

it.each([
  ["root", "/repo"],
  ["drafts", "/repo/drafts"],
])("CAS performs zero directory creation and zero writes for an unsafe %s symlink", async (_label, symlink) => {
  const runtime = zoteroRuntime({ userLibraryID: 1 });
  runtime.symlinks.add(symlink);
  const document = standaloneDocument("unsafe-cas");
  await expect(createZoteroAIContextHost(runtime).compareAndSwap(
    document.relativePath, null, document.source,
  )).rejects.toThrow(/symlink/);
  expect(runtime.makeDirectory).not.toHaveBeenCalled();
  expect(runtime.writeAtomic).not.toHaveBeenCalled();
});

it("validates an unsafe root before list exists/listChildren/read or any mutation", async () => {
  const runtime = zoteroRuntime({ userLibraryID: 1 });
  runtime.symlinks.add("/repo");
  await expect(createZoteroAIContextHost(runtime).list()).rejects.toThrow(/symlink/);
  expect(runtime.exists).not.toHaveBeenCalled();
  expect(runtime.listChildren).not.toHaveBeenCalled();
  expect(runtime.readUTF8).not.toHaveBeenCalled();
  expect(runtime.makeDirectory).not.toHaveBeenCalled();
  expect(runtime.writeAtomic).not.toHaveBeenCalled();
});

it("rejects a relative traversal before runtime I/O", async () => {
  const runtime = zoteroRuntime({ userLibraryID: 1 });
  await expect(createZoteroAIContextHost(runtime).snapshot("drafts/ai-contexts/../outside.qmd"))
    .rejects.toThrow(/path/);
  expect(runtime.readUTF8).not.toHaveBeenCalled();
});

it("retitles and reuses a canonical matching child", async () => {
  const parent = regular("P1", 1, 11);
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [parent] });
  runtime.attachments.push({
    id: 100, key: "LINK0", libraryID: 1, parentID: 11,
    path: "/repo/drafts/ai-contexts/ctx-shared.qmd", title: "Old title",
  });
  const result = await createZoteroAIContextHost(runtime).project(attachedDocument("P1"));
  expect(result.reused).toEqual([{ mode: "attached", libraryID: "1", itemKey: "P1" }]);
  expect(runtime.linkFromFile).not.toHaveBeenCalled();
  expect(runtime.saveAttachmentTitle).toHaveBeenCalledWith(runtime.attachments[0], "Reading Context · Shared reading");
});

it("treats a new link whose title save fails as missing and repairs the same record", async () => {
  const parent = regular("P1", 1, 11);
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [parent] });
  const host = createZoteroAIContextHost(runtime);
  const document = attachedDocument("P1");
  runtime.saveAttachmentTitle.mockRejectedValueOnce(new Error("title save failed"));

  const first = await host.project(document);
  expect(first.created).toEqual([]);
  expect(first.missing).toEqual([{ mode: "attached", libraryID: "1", itemKey: "P1" }]);
  expect(runtime.linkFromFile).toHaveBeenCalledOnce();
  expect(runtime.attachments).toHaveLength(1);
  expect((await host.projectionStatus(document)).missing).toHaveLength(1);

  const repaired = await host.project(document);
  expect(repaired.reused).toEqual([{ mode: "attached", libraryID: "1", itemKey: "P1" }]);
  expect(runtime.linkFromFile).toHaveBeenCalledOnce();
  expect(runtime.attachments[0]!.title).toBe(document.title);
});

it("rolls back a Gecko attachment's cached title when saveTx rejects", async () => {
  const { files, runtime, Zotero } = geckoCASHarness("none");
  const document = attachedDocument("P1");
  const absolutePath = `/repo/${document.relativePath}`;
  files.set(absolutePath, document.source);

  const attachmentIDs: number[] = [];
  const parent = { ...regular("P1", 1, 11), getAttachments: () => attachmentIDs };
  let cachedTitle = "";
  const attachment = {
    id: 101,
    key: "LINK1",
    libraryID: 1,
    parentID: parent.id,
    isAttachment: () => true,
    getFilePath: () => absolutePath,
    getField: (name: string) => name === "title" ? cachedTitle : "",
    setField: (name: string, value: string) => {
      if (name === "title") cachedTitle = value;
    },
    saveTx: vi.fn()
      .mockRejectedValueOnce(new Error("title save failed"))
      .mockResolvedValueOnce(undefined),
  };
  Zotero.Items.getByLibraryAndKeyAsync = vi.fn(async () => parent);
  Zotero.Items.getAsync = vi.fn(async (ids: number[]) => ids.map((id) => {
    if (id !== attachment.id) throw new Error(`unexpected attachment ID: ${id}`);
    return attachment;
  }));
  Zotero.Attachments.linkFromFile = vi.fn(async ({ file, parentItemID }: {
    file: string;
    parentItemID?: number;
  }) => {
    expect({ file, parentItemID }).toEqual({ file: absolutePath, parentItemID: parent.id });
    attachmentIDs.push(attachment.id);
    return attachment;
  });

  const host = createZoteroAIContextHost(runtime);
  expect((await host.project(document)).missing).toEqual([
    { mode: "attached", libraryID: "1", itemKey: "P1" },
  ]);
  expect((await host.projectionStatus(document)).missing).toEqual([
    { mode: "attached", libraryID: "1", itemKey: "P1" },
  ]);

  expect((await host.project(document)).reused).toEqual([
    { mode: "attached", libraryID: "1", itemKey: "P1" },
  ]);
  expect(cachedTitle).toBe(document.title);
  expect(Zotero.Attachments.linkFromFile).toHaveBeenCalledOnce();
  expect(attachment.saveTx).toHaveBeenCalledTimes(2);
});

it("treats a wrong-title existing link and a retitle failure as missing", async () => {
  const parent = regular("P1", 1, 11);
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [parent] });
  const document = attachedDocument("P1");
  runtime.attachments.push({
    id: 100, key: "LINK0", libraryID: 1, parentID: 11,
    path: "/repo/drafts/ai-contexts/ctx-shared.qmd", title: "Wrong title",
  });
  const host = createZoteroAIContextHost(runtime);
  expect((await host.projectionStatus(document)).missing).toEqual([
    { mode: "attached", libraryID: "1", itemKey: "P1" },
  ]);
  runtime.saveAttachmentTitle.mockRejectedValueOnce(new Error("retitle failed"));
  expect((await host.project(document)).missing).toHaveLength(1);
  expect(runtime.linkFromFile).not.toHaveBeenCalled();
});

it("repairs a wrong-title attachment after restart without creating a duplicate", async () => {
  const document = attachedDocument("P1");
  const runtime = zoteroRuntime({
    userLibraryID: 1,
    items: [regular("P1", 1, 11)],
    existingDrafts: [document.source],
  });
  runtime.attachments.push({
    id: 100, key: "LINK0", libraryID: 1, parentID: 11,
    path: "/repo/drafts/ai-contexts/existing-0.qmd", title: "Wrong title",
  });
  const service = new AIContextService(
    createZoteroAIContextHost(runtime), neverGenerator(), fixedEnvironment(),
  );
  const [pending] = await service.pendingRepairs();
  expect(pending!.status.missing).toHaveLength(1);
  await service.repair(pending!.document.relativePath);
  expect(runtime.attachments[0]!.title).toBe(pending!.document.title);
  expect(runtime.linkFromFile).not.toHaveBeenCalled();
});

it.each([
  ["zero links", [new Error("P1"), new Error("P2")], 0, 2],
  ["one of two links", [undefined, new Error("P2")], 1, 1],
])("returns recoverable projection status for %s", async (_label, outcomes, created, missing) => {
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [regular("P1", 1), regular("P2", 1)] });
  for (const outcome of outcomes) {
    if (outcome) runtime.linkFromFile.mockRejectedValueOnce(outcome);
    else runtime.linkFromFile.mockImplementationOnce(async ({ file, parentItemID }) => ({
      id: 100, key: "LINK", libraryID: 1, parentID: parentItemID ?? null, path: file, title: "",
    }));
  }
  const result = await createZoteroAIContextHost(runtime).project(attachedDocument("P1", "P2"));
  expect(result.created).toHaveLength(created);
  expect(result.missing).toHaveLength(missing);
});

it("finds reading and standalone repairs after restart and preserves ambiguity", async () => {
  const reading = attachedDocument("P1");
  const standalone = standaloneDocument("standalone-restart");
  const runtime = zoteroRuntime({
    userLibraryID: 1,
    items: [regular("P1", 1)],
    existingDrafts: [reading.source, standalone.source],
  });
  const pending = await new AIContextService(
    createZoteroAIContextHost(runtime), neverGenerator(), fixedEnvironment(),
  ).pendingRepairs();
  expect(pending.map(({ document }) => document.manifest.id))
    .toEqual(["ctx-shared", "standalone-restart"]);
});

it("keeps a committed QMD repairable when a preflighted parent disappears after CAS", async () => {
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [regular("P1", 1)] });
  const host = createZoteroAIContextHost(runtime);
  const writeAtomic = runtime.writeAtomic.getMockImplementation()!;
  runtime.writeAtomic = vi.fn<ZoteroAIContextRuntime["writeAtomic"]>(async (path, source, expectedRevision) => {
    const committed = await writeAtomic(path, source, expectedRevision);
    if (committed) runtime.itemByLibraryAndKey.mockResolvedValue(undefined);
    return committed;
  });
  const generator: AIContextGenerator = {
    generate: vi.fn(async () => JSON.stringify(validReadingSynthesis(["P1"]))),
  };
  const service = new AIContextService(host, generator, fixedEnvironment());

  const error = await service.save({
    kind: "reading",
    sourceThreadId: null,
    papers: papers("P1"),
    projection: { mode: "attached", targets: [{ libraryID: "1", itemKey: "P1" }] },
    messages: [],
  }).then(() => null, (value) => value as AIContextProjectionError);

  expect(error).toBeInstanceOf(AIContextProjectionError);
  if (!(error instanceof AIContextProjectionError)) throw new Error("expected projection error");
  expect(runtime.files.get(`/repo/${error.document.relativePath}`)).toBe(error.document.source);
  expect(error.result.missing).toEqual([{ mode: "attached", libraryID: "1", itemKey: "P1" }]);
  expect(error.cause).toBeInstanceOf(Error);
  await expect(service.pendingRepairs()).resolves.toEqual([
    expect.objectContaining({
      document: expect.objectContaining({ relativePath: error.document.relativePath }),
      status: { created: [], reused: [], missing: [{ mode: "attached", libraryID: "1", itemKey: "P1" }] },
    }),
  ]);
});

it("reports an unavailable status target as missing without discarding another parent’s valid projection", async () => {
  const runtime = zoteroRuntime({ userLibraryID: 1, items: [regular("P1", 1)] });
  const document = attachedDocument("P1", "P2");
  runtime.attachments.push({
    id: 100,
    key: "LINK0",
    libraryID: 1,
    parentID: 11,
    path: `/repo/${document.relativePath}`,
    title: document.title,
  });

  const status = await createZoteroAIContextHost(runtime).projectionStatus(document);

  expect(status.reused).toEqual([{ mode: "attached", libraryID: "1", itemKey: "P1" }]);
  expect(status.missing).toEqual([{ mode: "attached", libraryID: "1", itemKey: "P2" }]);
});

it.each([
  ["stored file", { linked: false, path: "/repo/drafts/ai-contexts/x.qmd", title: "AI Context · X" }],
  ["wrong suffix", { linked: true, path: "/repo/drafts/ai-contexts/x.pdf", title: "AI Context · X" }],
  ["wrong title", { linked: true, path: "/repo/drafts/ai-contexts/x.qmd", title: "Ordinary note" }],
])("quick candidate rejects %s", (_label, value) => {
  const candidate = {
    isLinkedFileAttachment: () => value.linked,
    getFilePath: () => value.path,
    getField: () => value.title,
  };
  expect(isQuickAIContextAttachmentCandidate(candidate)).toBe(false);
});

it("strict attachment resolution rejects a malformed manifest", async () => {
  const runtime = zoteroRuntime({ userLibraryID: 1 });
  const path = "/repo/drafts/ai-contexts/bad.qmd";
  runtime.files.set(path, "---\ntitle: bad\n---\n");
  const candidate = {
    isLinkedFileAttachment: () => true,
    getFilePath: () => path,
    getField: () => "AI Context · Bad",
  };
  await expect(resolveAIContextAttachment(runtime, candidate)).rejects.toThrow(/frontmatter|manifest/);
});
