import { describe, expect, it } from "vitest";
import {
  AI_CONTEXT_MANAGED_END,
  AI_CONTEXT_MANAGED_START,
  AI_CONTEXT_MAX_SOURCE_BYTES,
  aiContextReopenContext,
  aiContextRelativePath,
  parseAIContextDocument,
  renderNewAIContextDocument,
  replaceAIContextManagedRegion,
  validateAIContextSynthesis,
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
});
