import { describe, expect, it, vi } from "vitest";
import {
  AIContextConflictError,
  AIContextProjectionError,
  AIContextService,
  AI_CONTEXT_MANAGED_END,
  AI_CONTEXT_MANAGED_START,
  AI_CONTEXT_MAX_SOURCE_BYTES,
  aiContextReopenContext,
  aiContextRelativePath,
  parseAIContextDocument,
  renderNewAIContextDocument,
  replaceAIContextManagedRegion,
  validateAIContextSynthesis,
  type AIContextHost,
  type AIContextManifest,
  type AIContextPaper,
  type SaveAIContextInput,
} from "../src/ai-context";

const manifest = {
  schemaVersion: 1 as const,
  id: "ctx-01",
  contextKey: "reading:ctx-01",
  kind: "reading" as const,
  sourceThreadId: null,
  createdAt: "2026-07-31T00:00:00.000Z",
  updatedAt: "2026-07-31T00:00:00.000Z",
  status: "active" as const,
  papers: [{ libraryID: "1", itemKey: "P1", title: "Paper `one`" }],
  projection: { mode: "attached" as const, targets: [{ libraryID: "1", itemKey: "P1" }] },
  capturedEntryIds: [],
};

function validSynthesis(memoryMarkdown = "Remember the definitions.") {
  return {
    title: "Fault tolerant decoding",
    description: "A resumable reading chain.",
    category: "codes" as const,
    status: "active" as const,
    memoryMarkdown,
    progressMarkdown: "Not started.",
    nextStepMarkdown: "Read P1.",
    readingPlan: [{ itemKey: "P1", rationale: "Foundation", guidance: "Read section 2" }],
  };
}

interface FakeFile { source: string; revision: string }

function fixedEnvironment() {
  let next = 0;
  return {
    now: () => `2026-07-31T00:00:0${next++}.000Z`,
    id: () => "ctx-01",
  };
}

function conversationInput(overrides: Partial<SaveAIContextInput> = {}): SaveAIContextInput {
  return {
    kind: "conversation",
    contextKey: "conversation:thread-1",
    sourceThreadId: "thread-1",
    papers: [{ libraryID: "1", itemKey: "P1", title: "Paper one" }],
    projection: { mode: "attached", targets: [{ libraryID: "1", itemKey: "P1" }] },
    messages: [
      { id: "u1", role: "user", text: "question" },
      { id: "a1", role: "assistant", text: "answer" },
    ],
    ...overrides,
  };
}

function conversationManifest(overrides: Partial<AIContextManifest> = {}): AIContextManifest {
  return {
    ...manifest,
    kind: "conversation",
    contextKey: "conversation:thread-1",
    sourceThreadId: "thread-1",
    projection: { mode: "attached", targets: [{ libraryID: "1", itemKey: "P1" }] },
    capturedEntryIds: ["u1", "a1"],
    ...overrides,
  };
}

function servicePapers(...itemKeys: string[]): AIContextPaper[] {
  return itemKeys.map((itemKey) => ({
    libraryID: "1",
    itemKey,
    title: `Paper ${itemKey}`,
  }));
}

function fakeAIContextHost() {
  const files = new Map<string, FakeFile>();
  const host = {
    files,
    list: vi.fn<AIContextHost["list"]>(async () => [...files].map(([relativePath, file]) => ({ relativePath, ...file }))),
    snapshot: vi.fn<AIContextHost["snapshot"]>(async (relativePath) => {
      const file = files.get(relativePath);
      return { relativePath, source: file?.source ?? null, revision: file?.revision ?? null };
    }),
    compareAndSwap: vi.fn<AIContextHost["compareAndSwap"]>(async (relativePath, expectedRevision, source) => {
      const current = files.get(relativePath);
      if ((current?.revision ?? null) !== expectedRevision) return false;
      files.set(relativePath, { source, revision: `r${files.size + 1}` });
      return true;
    }),
    preflight: vi.fn<AIContextHost["preflight"]>(async () => undefined),
    project: vi.fn<AIContextHost["project"]>(async () => ({ created: [], reused: [], missing: [] })),
    projectionStatus: vi.fn<AIContextHost["projectionStatus"]>(async () => ({ created: [], reused: [], missing: [] })),
  } satisfies AIContextHost & { files: Map<string, FakeFile> };
  return host;
}

function validGenerator(memoryMarkdown = "memory") {
  return { generate: vi.fn(async () => JSON.stringify(validSynthesis(memoryMarkdown))) };
}

describe("AI Context QMD codec", () => {
  it("round-trips one strict manifest and complete fenced transcript", () => {
    const roundTripManifest = { ...manifest, capturedEntryIds: ["u1"] };
    const source = renderNewAIContextDocument({
      manifest: roundTripManifest,
      synthesis: {
        title: "Fault tolerant decoding",
        description: "A resumable reading chain.",
        category: "codes",
        status: "active",
        memoryMarkdown: "Remember <unsafe> as evidence.",
        progressMarkdown: "Not started.",
        nextStepMarkdown: "Read P1.",
        readingPlan: [{ itemKey: "P1", rationale: "Foundation", guidance: "Read section 2" }],
      },
      messages: [{ id: "u1", role: "user", text: "keep ``` and every byte\n" }],
    });
    const parsed = parseAIContextDocument("drafts/ai-contexts/ctx-01-fault-tolerant-decoding.qmd", source);
    expect(parsed.manifest).toEqual(roundTripManifest);
    expect(parsed.messages[0]!.text).toBe("keep ``` and every byte\n");
    expect(source).toContain("````text\nkeep ``` and every byte\n\n````");
    expect(source).not.toContain("<unsafe>");
  });

  it("treats managed-marker text inside a transcript as inert message bytes", () => {
    const text = [
      AI_CONTEXT_MANAGED_START,
      AI_CONTEXT_MANAGED_END,
      "<!-- qlab-ai-context-manifest:v1:fake -->",
      "<!-- qlab-ai-context-synthesis:v1:fake -->",
      "<!-- qlab-ai-context-message:v1:fake -->",
    ].join("\n");
    const source = renderNewAIContextDocument({
      manifest: { ...manifest, capturedEntryIds: ["u-markers"] },
      synthesis: validSynthesis(),
      messages: [{ id: "u-markers", role: "user", text }],
    });
    expect(parseAIContextDocument("drafts/ai-contexts/ctx-01-markers.qmd", source).messages)
      .toEqual([{ id: "u-markers", role: "user", text }]);
  });

  it("rejects colon-delimited projection identities that do not match the selected papers", () => {
    const mismatchedColonIdentity = {
      ...manifest,
      papers: [{ libraryID: "a:b", itemKey: "c", title: "Paper" }],
      projection: { mode: "attached" as const, targets: [{ libraryID: "a", itemKey: "b:c" }] },
    };
    expect(() => renderNewAIContextDocument({
      manifest: mismatchedColonIdentity,
      synthesis: { ...validSynthesis(), readingPlan: [{ itemKey: "c", rationale: "Read", guidance: "Read" }] },
      messages: [],
    })).toThrow(/manifest: attached targets must match/);
  });

  it("round-trips a transcript with many short backtick runs", () => {
    const text = "`x".repeat(150_000);
    const source = renderNewAIContextDocument({
      manifest: { ...manifest, capturedEntryIds: ["u-many-fences"] },
      synthesis: validSynthesis(),
      messages: [{ id: "u-many-fences", role: "user", text }],
    });
    expect(parseAIContextDocument("drafts/ai-contexts/ctx-01-many-fences.qmd", source).messages)
      .toEqual([{ id: "u-many-fences", role: "user", text }]);
  });

  it("fails closed on duplicate, reversed, and unknown-version managed structure after valid frontmatter", () => {
    const valid = renderNewAIContextDocument({ manifest, synthesis: validSynthesis(), messages: [] });
    const malformed = [
      valid.replace(AI_CONTEXT_MANAGED_START, `${AI_CONTEXT_MANAGED_START}\n${AI_CONTEXT_MANAGED_START}`),
      valid.replace(AI_CONTEXT_MANAGED_START, `${AI_CONTEXT_MANAGED_END}\n${AI_CONTEXT_MANAGED_START}`),
      valid.replace("qlab-ai-context-manifest:v1:", "qlab-ai-context-manifest:v2:"),
    ];
    for (const source of malformed) {
      expect(() => parseAIContextDocument("drafts/ai-contexts/x.qmd", source)).toThrow(/manifest:/);
    }
  });

  it("replaces only the managed bytes and enforces path/source budgets", () => {
    const original = renderNewAIContextDocument({ manifest, synthesis: validSynthesis(), messages: [] })
      + "\n## Personal notes\n\nhandwritten\n";
    const changed = replaceAIContextManagedRegion(original, {
      manifest: { ...manifest, updatedAt: "2026-07-31T01:00:00.000Z" },
      synthesis: { ...validSynthesis(), progressMarkdown: "Read P1." },
      messages: [],
    });
    expect(changed.slice(changed.indexOf("## Personal notes"))).toBe("## Personal notes\n\nhandwritten\n");
    expect(aiContextRelativePath("ctx-01", "A/B .. title")).toBe("drafts/ai-contexts/ctx-01-a-b-title.qmd");
    expect(() => parseAIContextDocument("knowledge/x.qmd", original)).toThrow(/drafts\/ai-contexts/);
    expect(() => parseAIContextDocument("drafts/ai-contexts/x.qmd", "x".repeat(AI_CONTEXT_MAX_SOURCE_BYTES + 1))).toThrow(/2,000,000/);
  });

  it("builds bounded reopen context without transcript text", () => {
    const source = renderNewAIContextDocument({
      manifest: { ...manifest, capturedEntryIds: ["u-secret"] },
      synthesis: { ...validSynthesis("m".repeat(40_000)), progressMarkdown: "progress" },
      messages: [{ id: "u-secret", role: "user", text: "RAW TRANSCRIPT SECRET" }],
    });
    const context = aiContextReopenContext(parseAIContextDocument(
      "drafts/ai-contexts/ctx-01.qmd",
      source,
    ));
    expect([...context]).toHaveLength(32_000);
    expect(context).not.toContain("RAW TRANSCRIPT SECRET");
  });

  it.each([
    ["title empty", { ...validSynthesis(), title: "" }, /synthesis: title/],
    ["title over bound", { ...validSynthesis(), title: "x".repeat(121) }, /synthesis: title/],
    ["description over bound", { ...validSynthesis(), description: "x".repeat(501) }, /synthesis: description/],
    ["memory empty", { ...validSynthesis(), memoryMarkdown: "" }, /synthesis: memory/],
    ["memory over bound", { ...validSynthesis(), memoryMarkdown: "x".repeat(48_001) }, /synthesis: memory/],
    ["progress empty", { ...validSynthesis(), progressMarkdown: "" }, /synthesis: progress/],
    ["progress over bound", { ...validSynthesis(), progressMarkdown: "x".repeat(8_001) }, /synthesis: progress/],
    ["next step empty", { ...validSynthesis(), nextStepMarkdown: "" }, /synthesis: next step/],
    ["next step over bound", { ...validSynthesis(), nextStepMarkdown: "x".repeat(8_001) }, /synthesis: next step/],
    ["duplicate paper", { ...validSynthesis(), readingPlan: [
      { itemKey: "P1", rationale: "one", guidance: "one" },
      { itemKey: "P1", rationale: "two", guidance: "two" },
    ] }, /synthesis: duplicate/],
    ["unknown paper", { ...validSynthesis(), readingPlan: [
      { itemKey: "UNKNOWN", rationale: "one", guidance: "one" },
    ] }, /synthesis: unknown/],
  ])("rejects %s", (_label, value, expected) => {
    expect(() => validateAIContextSynthesis(value, manifest.papers)).toThrow(expected);
  });

  it("appends omitted Reading-plan papers in stable selection order", () => {
    const papers = [
      { libraryID: "1", itemKey: "P1", title: "one" },
      { libraryID: "1", itemKey: "P2", title: "two" },
      { libraryID: "1", itemKey: "P3", title: "three" },
    ];
    const synthesis = validateAIContextSynthesis({
      ...validSynthesis(),
      readingPlan: [{ itemKey: "P2", rationale: "generated", guidance: "generated" }],
    }, papers);
    expect(synthesis.readingPlan).toEqual([
      { itemKey: "P2", rationale: "generated", guidance: "generated" },
      {
        itemKey: "P1",
        rationale: "No generated transition rationale was available; preserve the stable selection order.",
        guidance: "No generated guidance was available; inspect this paper directly and record evidence limits.",
      },
      {
        itemKey: "P3",
        rationale: "No generated transition rationale was available; preserve the stable selection order.",
        guidance: "No generated guidance was available; inspect this paper directly and record evidence limits.",
      },
    ]);
  });

  it("rejects manifest extra keys, duplicate IDs, and unsafe IDs before rendering", () => {
    const extra = { ...manifest, unexpected: true };
    const duplicate = { ...manifest, capturedEntryIds: ["u1", "u1"] };
    const unsafe = { ...manifest, id: "../escape" };
    const pathUnsafe = { ...manifest, id: "ctx:colon" };
    for (const invalid of [extra, duplicate, unsafe, pathUnsafe]) {
      expect(() => renderNewAIContextDocument({
        manifest: invalid,
        synthesis: validSynthesis(),
        messages: [],
      })).toThrow(/manifest:/);
    }
  });

  it("rejects duplicate/mismatched projections and inconsistent context identities", () => {
    const duplicatePapers = { ...manifest, papers: [...manifest.papers, ...manifest.papers] };
    const duplicateTargets = {
      ...manifest,
      projection: { ...manifest.projection, targets: [...manifest.projection.targets, ...manifest.projection.targets] },
    };
    const mismatched = {
      ...manifest,
      projection: { mode: "attached" as const, targets: [{ libraryID: "1", itemKey: "OTHER" }] },
    };
    const wrongIdentity = { ...manifest, contextKey: "reading:other-record" };
    for (const invalid of [duplicatePapers, duplicateTargets, mismatched, wrongIdentity]) {
      expect(() => renderNewAIContextDocument({ manifest: invalid, synthesis: validSynthesis(), messages: [] }))
        .toThrow(/manifest:/);
    }
  });

  it("rejects noncanonical manifest encoding and reordered or extended frontmatter", () => {
    const source = renderNewAIContextDocument({ manifest, synthesis: validSynthesis(), messages: [] });
    const padded = source.replace(
      /(qlab-ai-context-manifest:v1:[A-Za-z0-9_-]+)/u,
      "$1=",
    );
    const invalidAlphabet = source.replace(
      /(qlab-ai-context-manifest:v1:)[A-Za-z0-9_-]+/u,
      "$1***",
    );
    const reordered = source.replace(
      /title: ([^\n]+)\ndescription: ([^\n]+)/u,
      "description: $2\ntitle: $1",
    );
    const extra = source.replace("categories: [codes]", "aliases: [ctx]\ncategories: [codes]");
    expect(() => parseAIContextDocument("drafts/ai-contexts/x.qmd", padded)).toThrow(/manifest:/);
    expect(() => parseAIContextDocument("drafts/ai-contexts/x.qmd", invalidAlphabet)).toThrow(/manifest:/);
    expect(() => parseAIContextDocument("drafts/ai-contexts/x.qmd", reordered)).toThrow(/frontmatter:/);
    expect(() => parseAIContextDocument("drafts/ai-contexts/x.qmd", extra)).toThrow(/frontmatter:/);
  });

  it("rejects reordered metadata and mutated managed headings as noncanonical", () => {
    const source = renderNewAIContextDocument({ manifest, synthesis: validSynthesis(), messages: [] });
    const manifestLine = source.match(/^<!-- qlab-ai-context-manifest:[^\n]+$/mu)![0];
    const synthesisLine = source.match(/^<!-- qlab-ai-context-synthesis:[^\n]+$/mu)![0];
    const reordered = source.replace(`${manifestLine}\n${synthesisLine}`, `${synthesisLine}\n${manifestLine}`);
    const changedHeading = source.replace("## Progress", "## Progress so far");
    for (const invalid of [reordered, changedHeading]) {
      expect(() => parseAIContextDocument("drafts/ai-contexts/x.qmd", invalid))
        .toThrow(/managed region is noncanonical/);
    }
  });

  it("reruns complete synthesis once after a CAS conflict", async () => {
    const host = fakeAIContextHost();
    host.compareAndSwap
      .mockResolvedValueOnce(false)
      .mockImplementationOnce(async (path, _revision, source) => {
        host.files.set(path, { source, revision: "r3" });
        return true;
      });
    const generator = { generate: vi.fn()
      .mockResolvedValueOnce(JSON.stringify(validSynthesis("first")))
      .mockResolvedValueOnce(JSON.stringify(validSynthesis("latest"))) };
    const service = new AIContextService(host, generator, fixedEnvironment());

    const result = await service.save(conversationInput());

    expect(generator.generate).toHaveBeenCalledTimes(2);
    expect(result.document.synthesis.memoryMarkdown).toBe("latest");
    expect(host.project).toHaveBeenCalledOnce();
  });

  it("writes and projects nothing after a second conflict", async () => {
    const host = fakeAIContextHost();
    host.compareAndSwap.mockResolvedValue(false);
    const service = new AIContextService(host, validGenerator(), fixedEnvironment());
    await expect(service.save(conversationInput())).rejects.toThrow(AIContextConflictError);
    expect(host.project).not.toHaveBeenCalled();
  });

  it("folds every uncaptured message through ordered 80k batches without truncating transcript", async () => {
    const input = conversationInput({ messages: [
      { id: "u1", role: "user", text: "a".repeat(79_000) },
      { id: "a1", role: "assistant", text: "b".repeat(79_000) },
      { id: "u2", role: "user", text: "final contribution" },
    ] });
    const host = fakeAIContextHost();
    const inputs: string[] = [];
    const generator = {
      inputs,
      generate: vi.fn(async (prompt: string) => {
        inputs.push(prompt);
        return JSON.stringify(validSynthesis(`fold-${inputs.length}`));
      }),
    };
    const result = await new AIContextService(host, generator, fixedEnvironment()).save(input);
    expect(generator.inputs.every((value) => value.length <= 80_000)).toBe(true);
    expect(generator.inputs.join("\n")).toContain(input.messages[2]!.text);
    expect(result.document.messages.map((message) => message.text)).toEqual(input.messages.map((message) => message.text));
  });

  it.each([
    ["zero-link", []],
    ["partial-link", [{ mode: "attached" as const, libraryID: "1", itemKey: "P2" }]],
  ])("repairs an active %s record before synthesis and leaves its source byte-identical", async (_label, created) => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/ctx-01.qmd";
    const source = renderNewAIContextDocument({
      manifest: conversationManifest({ capturedEntryIds: ["old"] }),
      synthesis: validSynthesis("original memory"),
      messages: [{ id: "old", role: "user", text: "original transcript" }],
    }) + "\n## Personal notes\n\nkeep me\n";
    host.files.set(relativePath, { source, revision: "r1" });
    const missing = [{ mode: "attached" as const, libraryID: "1", itemKey: "P1" }];
    host.projectionStatus = vi.fn<AIContextHost["projectionStatus"]>(async () => ({ created, reused: [], missing }));
    host.project = vi.fn<AIContextHost["project"]>(async () => ({ created: missing, reused: [], missing: [] }));
    const generator = validGenerator("must not run");

    const result = await new AIContextService(host, generator, fixedEnvironment()).save(
      conversationInput({
        activeRelativePath: relativePath,
        messages: [{ id: "new", role: "assistant", text: "not captured until the next click" }],
      }),
    );

    expect(generator.generate).not.toHaveBeenCalled();
    expect(host.compareAndSwap).not.toHaveBeenCalled();
    expect(host.preflight).toHaveBeenCalledOnce();
    expect(host.project).toHaveBeenCalledOnce();
    expect(host.files.get(relativePath)!.source).toBe(source);
    expect(result.document.messages.map(({ id }) => id)).toEqual(["old"]);
  });

  it.each(["active-path", "context-key"])("repairs an incomplete %s record before transcript merge", async (lookup) => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/ctx-01.qmd";
    const source = renderNewAIContextDocument({
      manifest: conversationManifest(),
      synthesis: validSynthesis("stored memory"),
      messages: conversationInput().messages,
    }) + "\n## Personal notes\n\nunchanged\n";
    host.files.set(relativePath, { source, revision: "r1" });
    const missing = [{ mode: "attached" as const, libraryID: "1", itemKey: "P1" }];
    host.projectionStatus.mockResolvedValue({ created: [], reused: [], missing });
    host.project.mockResolvedValue({ created: missing, reused: [], missing: [] });
    const generator = validGenerator();

    const result = await new AIContextService(host, generator, fixedEnvironment()).save(
      conversationInput({
        activeRelativePath: lookup === "active-path" ? relativePath : null,
        messages: [{ id: "conflicting", role: "assistant", text: "must not be merged during repair" }],
      }),
    );

    expect(result.document.source).toBe(source);
    expect(generator.generate).not.toHaveBeenCalled();
    expect(host.compareAndSwap).not.toHaveBeenCalled();
    expect(host.preflight).toHaveBeenCalledOnce();
  });

  it.each(["active-path", "context-key"])("returns a complete no-unseen %s record without synthesis or CAS", async (lookup) => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/ctx-01.qmd";
    const source = renderNewAIContextDocument({
      manifest: conversationManifest(),
      synthesis: validSynthesis("stored memory"),
      messages: conversationInput().messages,
    });
    host.files.set(relativePath, { source, revision: "r1" });
    host.projectionStatus.mockResolvedValue({
      created: [],
      reused: [{ mode: "attached", libraryID: "1", itemKey: "P1" }],
      missing: [],
    });
    const generator = validGenerator();
    const result = await new AIContextService(host, generator, fixedEnvironment()).save(
      conversationInput({ activeRelativePath: lookup === "active-path" ? relativePath : null }),
    );
    expect(result.document.source).toBe(source);
    expect(generator.generate).not.toHaveBeenCalled();
    expect(host.compareAndSwap).not.toHaveBeenCalled();
    expect(host.project).not.toHaveBeenCalled();
  });

  it("merges prior and newly visible entries by ID without replacing the first transcript", async () => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/ctx-01.qmd";
    const oldMessage = { id: "old", role: "user" as const, text: "first capture" };
    const source = renderNewAIContextDocument({
      manifest: conversationManifest({ capturedEntryIds: ["old"] }),
      synthesis: validSynthesis("old memory"),
      messages: [oldMessage],
    });
    host.files.set(relativePath, { source, revision: "r1" });
    const duplicate = { ...oldMessage };
    const next = { id: "new", role: "assistant" as const, text: "dedicated-thread progress" };

    const result = await new AIContextService(host, validGenerator("merged memory"), fixedEnvironment()).save(
      conversationInput({ activeRelativePath: relativePath, messages: [duplicate, next] }),
    );

    expect(result.document.messages).toEqual([oldMessage, next]);
    expect(result.document.manifest.capturedEntryIds).toEqual(["old", "new"]);
    expect(result.document.source).toContain("first capture");
    expect(result.document.source).toContain("dedicated-thread progress");
  });

  it("fails closed when a repeated entry ID changes role or text", async () => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/ctx-01.qmd";
    const source = renderNewAIContextDocument({
      manifest: conversationManifest({ capturedEntryIds: ["same"] }),
      synthesis: validSynthesis(),
      messages: [{ id: "same", role: "user", text: "original" }],
    });
    host.files.set(relativePath, { source, revision: "r1" });
    await expect(new AIContextService(host, validGenerator(), fixedEnvironment()).save(
      conversationInput({
        activeRelativePath: relativePath,
        messages: [{ id: "same", role: "assistant", text: "changed" }],
      }),
    )).rejects.toThrow(/entry same changed/i);
    expect(host.compareAndSwap).not.toHaveBeenCalled();
  });

  it("uses expected-absent CAS for creation and never overwrites a path collision", async () => {
    const host = fakeAIContextHost();
    const collidingSource = renderNewAIContextDocument({
      manifest: conversationManifest({
        id: "ctx-01",
        contextKey: "conversation:someone-else",
        sourceThreadId: "someone-else",
      }),
      synthesis: validSynthesis("collision memory"),
      messages: conversationInput().messages,
    });
    host.compareAndSwap = vi.fn<AIContextHost["compareAndSwap"]>(async (relativePath, expectedRevision, source) => {
      expect(expectedRevision).toBeNull();
      host.files.set(relativePath, { source: collidingSource, revision: "collision-r1" });
      return false;
    });

    await expect(new AIContextService(host, validGenerator(), fixedEnvironment()).save(conversationInput()))
      .rejects.toThrow(AIContextConflictError);
    const collisionPath = host.compareAndSwap.mock.calls[0]![0];
    expect(host.files.get(collisionPath)!.source).toBe(collidingSource);
    expect(host.compareAndSwap).toHaveBeenCalledOnce();
  });

  it("retries against the real latest source, prior memory, and external bytes", async () => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/ctx-01.qmd";
    const initial = renderNewAIContextDocument({
      manifest: conversationManifest({ capturedEntryIds: ["old"] }),
      synthesis: validSynthesis("initial memory"),
      messages: [{ id: "old", role: "user", text: "old turn" }],
    }) + "\n## Personal notes\n\ninitial note\n";
    host.files.set(relativePath, { source: initial, revision: "r1" });
    const prompts: string[] = [];
    const generator = {
      generate: vi.fn(async (prompt: string) => {
        prompts.push(prompt);
        return JSON.stringify(validSynthesis(prompts.length === 1 ? "first attempt" : "retry memory"));
      }),
    };
    const realCAS = host.compareAndSwap.getMockImplementation()!;
    host.compareAndSwap = vi.fn<AIContextHost["compareAndSwap"]>()
      .mockImplementationOnce(async () => {
        const externallyEdited = replaceAIContextManagedRegion(initial, {
          manifest: conversationManifest({ capturedEntryIds: ["old"] }),
          synthesis: validSynthesis("external latest memory"),
          messages: [{ id: "old", role: "user", text: "old turn" }],
        }).replace("initial note", "external note");
        host.files.set(relativePath, { source: externallyEdited, revision: "r2" });
        return false;
      })
      .mockImplementation(realCAS);

    const result = await new AIContextService(host, generator, fixedEnvironment()).save(
      conversationInput({
        activeRelativePath: relativePath,
        messages: [{ id: "new", role: "assistant", text: "new turn" }],
      }),
    );

    expect(generator.generate).toHaveBeenCalledTimes(2);
    expect(prompts[1]).toContain("external latest memory");
    expect(result.document.synthesis.memoryMarkdown).toBe("retry memory");
    expect(result.document.source).toContain("## Personal notes\n\nexternal note\n");
    expect(result.document.messages.map(({ id }) => id)).toEqual(["old", "new"]);
  });

  it("retries a context-key-discovered existing record instead of treating it as a creation collision", async () => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/existing-logical.qmd";
    const original = renderNewAIContextDocument({
      manifest: conversationManifest(),
      synthesis: validSynthesis("original"),
      messages: conversationInput().messages,
    });
    host.files.set(relativePath, { source: original, revision: "r1" });
    const realCAS = host.compareAndSwap.getMockImplementation()!;
    host.compareAndSwap
      .mockImplementationOnce(async () => {
        const latest = original + "\n## Personal notes\n\nconcurrent\n";
        host.files.set(relativePath, { source: latest, revision: "r2" });
        return false;
      })
      .mockImplementation(realCAS);
    const generator = validGenerator("retry result");

    const result = await new AIContextService(host, generator, fixedEnvironment()).save(
      conversationInput({ messages: [...conversationInput().messages, { id: "a2", role: "assistant", text: "new" }] }),
    );

    expect(generator.generate).toHaveBeenCalledTimes(2);
    expect(result.document.source).toContain("## Personal notes\n\nconcurrent\n");
  });

  it("parses source and revision from the same fresh snapshot after logical-key discovery", async () => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/discovered.qmd";
    const stale = renderNewAIContextDocument({
      manifest: conversationManifest(), synthesis: validSynthesis("stale"), messages: conversationInput().messages,
    });
    const latest = replaceAIContextManagedRegion(stale, {
      manifest: conversationManifest(), synthesis: validSynthesis("latest"), messages: conversationInput().messages,
    }) + "\n## Personal notes\n\nlatest note\n";
    host.files.set(relativePath, { source: latest, revision: "r2" });
    host.list.mockResolvedValue([{ relativePath, source: stale, revision: "r1" }]);

    const result = await new AIContextService(host, validGenerator("updated"), fixedEnvironment()).save(
      conversationInput({ messages: [...conversationInput().messages, { id: "a2", role: "assistant", text: "new" }] }),
    );

    expect(result.document.source).toContain("## Personal notes\n\nlatest note\n");
  });

  it("ignores a different caller key while updating the active path", async () => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/ctx-01.qmd";
    const source = renderNewAIContextDocument({
      manifest: conversationManifest({ capturedEntryIds: ["old"] }),
      synthesis: validSynthesis(),
      messages: [{ id: "old", role: "user", text: "old" }],
    });
    host.files.set(relativePath, { source, revision: "r1" });
    const result = await new AIContextService(host, validGenerator(), fixedEnvironment()).save(
      conversationInput({
        activeRelativePath: relativePath,
        contextKey: "conversation:different-thread",
        sourceThreadId: "different-thread",
        messages: [{ id: "new", role: "assistant", text: "new" }],
      }),
    );
    expect(result.document.manifest.contextKey).toBe("conversation:thread-1");
    expect(result.document.manifest.sourceThreadId).toBe("thread-1");
  });

  it("fails closed when two records have the same logical key", async () => {
    const host = fakeAIContextHost();
    for (const suffix of ["a", "b"]) {
      const relativePath = `drafts/ai-contexts/ctx-${suffix}.qmd`;
      host.files.set(relativePath, {
        source: renderNewAIContextDocument({
          manifest: conversationManifest({ id: `ctx-${suffix}` }),
          synthesis: validSynthesis(),
          messages: conversationInput().messages,
        }),
        revision: `r-${suffix}`,
      });
    }
    await expect(new AIContextService(host, validGenerator(), fixedEnvironment()).save(conversationInput()))
      .rejects.toThrow(/duplicate logical records.*ctx-a.*ctx-b/i);
    expect(host.compareAndSwap).not.toHaveBeenCalled();
  });

  it("rejects a utility output longer than 64,000 characters before CAS", async () => {
    const host = fakeAIContextHost();
    const generator = { generate: vi.fn(async () => "x".repeat(64_001)) };
    await expect(new AIContextService(host, generator, fixedEnvironment()).save(conversationInput()))
      .rejects.toThrow(/64,000/);
    expect(host.compareAndSwap).not.toHaveBeenCalled();
  });

  it("reserves room for ordered units when the prior output is near 64,000 characters", async () => {
    const host = fakeAIContextHost();
    const oversizedAccumulator = validSynthesis("\\".repeat(30_000));
    const prompts: string[] = [];
    const generator = {
      generate: vi.fn(async (prompt: string) => {
        prompts.push(prompt);
        return JSON.stringify(oversizedAccumulator);
      }),
    };
    await new AIContextService(host, generator, fixedEnvironment()).save(
      conversationInput({ messages: [{ id: "u1", role: "user", text: "x".repeat(100_000) }] }),
    );
    expect(prompts.length).toBeGreaterThan(1);
    expect(prompts.every((prompt) => [...prompt].length <= 80_000)).toBe(true);
  });

  it("folds all metadata from fifty large-abstract papers through bounded prompts", async () => {
    const host = fakeAIContextHost();
    const selected = Array.from({ length: 50 }, (_, index) => ({
      libraryID: "1",
      itemKey: `P${index + 1}`,
      title: `Paper ${index + 1}`,
      abstract: `${`abstract-${index + 1}-`}${"x".repeat(19_000)}`,
    }));
    const prompts: string[] = [];
    const generator = {
      generate: vi.fn(async (prompt: string) => {
        prompts.push(prompt);
        return JSON.stringify({
          ...validSynthesis(`fold-${prompts.length}`),
          readingPlan: selected.map(({ itemKey }) => ({ itemKey, rationale: "r", guidance: "g" })),
        });
      }),
    };
    await new AIContextService(host, generator, fixedEnvironment()).save({
      kind: "reading",
      sourceThreadId: null,
      papers: selected,
      projection: {
        mode: "attached",
        targets: selected.map(({ libraryID, itemKey }) => ({ libraryID, itemKey })),
      },
      messages: [],
    });
    expect(prompts.every((prompt) => [...prompt].length <= 80_000)).toBe(true);
    for (const [index, paper] of selected.entries()) {
      const joined = prompts.join("\n");
      expect(joined).toContain(`abstract-${index + 1}-`);
      expect(joined).toContain(paper.itemKey);
    }
  });

  it.each([
    ["duplicate", [
      { itemKey: "P1", rationale: "r1", guidance: "g1" },
      { itemKey: "P1", rationale: "r2", guidance: "g2" },
    ]],
    ["unknown", [
      { itemKey: "P1", rationale: "r1", guidance: "g1" },
      { itemKey: "P3", rationale: "r3", guidance: "g3" },
    ]],
  ])("rejects %s generated Reading-plan entries before CAS", async (_label, readingPlan) => {
    const host = fakeAIContextHost();
    const synthesis = { ...validSynthesis(), readingPlan };
    const generator = { generate: vi.fn(async () => JSON.stringify(synthesis)) };
    await expect(new AIContextService(host, generator, fixedEnvironment()).save({
      kind: "reading",
      sourceThreadId: null,
      papers: servicePapers("P1", "P2"),
      projection: {
        mode: "attached",
        targets: servicePapers("P1", "P2").map(({ libraryID, itemKey }) => ({ libraryID, itemKey })),
      },
      messages: [],
    })).rejects.toThrow(/synthesis/);
    expect(host.compareAndSwap).not.toHaveBeenCalled();
  });

  it("appends an omitted Reading paper in stable selection order", async () => {
    const host = fakeAIContextHost();
    const generator = { generate: vi.fn(async () => JSON.stringify({
      ...validSynthesis(),
      readingPlan: [{ itemKey: "P1", rationale: "r1", guidance: "g1" }],
    })) };
    const result = await new AIContextService(host, generator, fixedEnvironment()).save({
      kind: "reading",
      sourceThreadId: null,
      papers: servicePapers("P1", "P2"),
      projection: {
        mode: "attached",
        targets: servicePapers("P1", "P2").map(({ libraryID, itemKey }) => ({ libraryID, itemKey })),
      },
      messages: [],
    });
    expect(result.document.synthesis.readingPlan.map(({ itemKey }) => itemKey)).toEqual(["P1", "P2"]);
  });

  it("lists both pending repairs and repairs only the exact requested path", async () => {
    const host = fakeAIContextHost();
    const attachedPath = "drafts/ai-contexts/attached.qmd";
    const standalonePath = "drafts/ai-contexts/standalone.qmd";
    host.files.set(attachedPath, {
      source: renderNewAIContextDocument({
        manifest: conversationManifest({ id: "attached" }),
        synthesis: validSynthesis(),
        messages: conversationInput().messages,
      }),
      revision: "ra",
    });
    host.files.set(standalonePath, {
      source: renderNewAIContextDocument({
        manifest: conversationManifest({
          id: "standalone",
          contextKey: "standalone:standalone",
          papers: [],
          projection: { mode: "standalone", targets: [] },
          capturedEntryIds: [],
        }),
        synthesis: { ...validSynthesis(), readingPlan: [] },
        messages: [],
      }),
      revision: "rs",
    });
    host.projectionStatus = vi.fn<AIContextHost["projectionStatus"]>(async (document) => ({
      created: [], reused: [], missing: document.manifest.projection.mode === "standalone"
        ? [{ mode: "standalone" as const, libraryID: "1" }]
        : [{ mode: "attached" as const, libraryID: "1", itemKey: "P1" }],
    }));
    const generator = validGenerator();
    const service = new AIContextService(host, generator, fixedEnvironment());
    expect((await service.pendingRepairs()).map(({ document }) => document.relativePath))
      .toEqual([attachedPath, standalonePath]);
    await service.repair(standalonePath);
    expect(host.project).toHaveBeenCalledOnce();
    expect((host.project as any).mock.calls[0]![0].relativePath).toBe(standalonePath);
    expect(generator.generate).not.toHaveBeenCalled();
    expect(host.compareAndSwap).not.toHaveBeenCalled();
  });

  it("wraps a post-commit projection throw with the committed document and latest missing handles", async () => {
    const host = fakeAIContextHost();
    const cause = new Error("Zotero link failure");
    const missing = [{ mode: "attached" as const, libraryID: "1", itemKey: "P1" }];
    host.project.mockRejectedValue(cause);
    host.projectionStatus.mockResolvedValue({ created: [], reused: [], missing });
    const error = await new AIContextService(host, validGenerator(), fixedEnvironment()).save(conversationInput())
      .then(() => null, (value) => value as AIContextProjectionError);
    expect(error).toBeInstanceOf(AIContextProjectionError);
    if (!(error instanceof AIContextProjectionError)) throw new Error("expected projection error");
    expect(error.document.relativePath).toMatch(/^drafts\/ai-contexts\//u);
    expect(error.result.missing).toEqual(missing);
    expect(error.cause).toBe(cause);
    expect(host.files.get(error.document.relativePath)!.source).toBe(error.document.source);
  });

  it("wraps a repair projection throw without synthesis or CAS", async () => {
    const host = fakeAIContextHost();
    const relativePath = "drafts/ai-contexts/repair-error.qmd";
    const source = renderNewAIContextDocument({
      manifest: conversationManifest(), synthesis: validSynthesis(), messages: conversationInput().messages,
    });
    host.files.set(relativePath, { source, revision: "r1" });
    const missing = [{ mode: "attached" as const, libraryID: "1", itemKey: "P1" }];
    host.projectionStatus.mockResolvedValue({ created: [], reused: [], missing });
    host.project.mockRejectedValue(new Error("still unavailable"));
    const generator = validGenerator();
    await expect(new AIContextService(host, generator, fixedEnvironment()).repair(relativePath))
      .rejects.toMatchObject({ document: expect.objectContaining({ relativePath }), result: { missing } });
    expect(generator.generate).not.toHaveBeenCalled();
    expect(host.compareAndSwap).not.toHaveBeenCalled();
  });
});
