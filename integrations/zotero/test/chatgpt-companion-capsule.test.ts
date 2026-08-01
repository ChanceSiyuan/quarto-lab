import { describe, expect, it } from "vitest";

import {
  COMPANION_CAPSULE_BOUNDS,
  COMPANION_CAPSULE_WARNING_BOUND,
  buildCompanionCapsule,
  canonicalCompanionCapsuleJson,
  verifyCompanionCapsule,
} from "../src/chatgpt-companion-capsule";

const dependencies = {
  id: () => "capsule_0123456789abcdef",
  now: () => "2026-08-01T12:34:56.000Z",
  hash: (value: string) => `hash:${value.length}:${value.slice(0, 18)}`,
};

function input() {
  return {
    subject: { paperKey: "ABCD1234", draftPath: "drafts/notes/visible.qmd" },
    question: "  Explain e\u0301 exactly?  ",
    contextItems: [
      { id: "paper", kind: "paper", sourceIdentity: "zotero:ABCD1234" },
      { id: "page", kind: "page", sourceIdentity: "zotero:ABCD1234:p7" },
      { id: "selection", kind: "selection", sourceIdentity: "zotero:ABCD1234:p7" },
      { id: "annotations", kind: "annotation", sourceIdentity: "zotero:ABCD1234" },
      { id: "library", kind: "library", sourceIdentity: "zotero:library" },
      { id: "secondary", kind: "external-paper", sourceIdentity: "secondary-1", mode: "full" },
      { id: "draft", kind: "draft", sourceIdentity: "drafts/notes/visible.qmd" },
      { id: "screenshot", kind: "screenshot", sourceIdentity: "shot-1" },
    ],
    paper: {
      title: "Primary\u0000 Paper",
      creators: "Ada Lovelace",
      year: "2026",
      doi: "10.1234/example",
      url: "https://example.test/paper",
      pdfPath: "/private/paper.pdf",
      abstract: "never copied",
    },
    page: {
      pageNumber: 7,
      pageLabel: "7",
      excerpt: "Visible page",
      source: "pdfjs",
      pdfText: { path: "/private/full-text.txt" },
    },
    selection: { text: "Selected", pageNumber: 7 },
    secondaryPapers: [{
      id: "secondary-1",
      title: "Secondary paper",
      creators: "Grace Hopper",
      year: "2025",
      doi: "10.1234/secondary",
      url: "https://example.test/secondary",
      mode: "retrieval" as const,
      pdfPath: "/private/secondary.pdf",
      fullText: "never copied",
    }],
    draft: {
      relativePath: "drafts/notes/visible.qmd",
      excerpt: "Unreviewed body",
      revision: "revision-1",
      source: "/workspace/drafts/notes/visible.qmd",
    },
    screenshotProvenance: [{
      id: "shot-1",
      kind: "region" as const,
      paperTitle: "Primary Paper",
      pageNumber: 7,
      image: "data:image/png;base64,secret",
    }],
    environment: { token: "never copied" },
    hiddenInstructions: "never copied",
  };
}

describe("ChatGPT companion capsule", () => {
  it("freezes the exact question and ordered effective chip snapshot with safe provenance", () => {
    const source = input();
    const capsule = buildCompanionCapsule(source, dependencies);

    expect(capsule.question).toBe("  Explain e\u0301 exactly?  ");
    expect(capsule.contextItems).toEqual([
      expect.objectContaining({ id: "paper", included: true, supported: true, authority: "external_evidence" }),
      expect.objectContaining({ id: "page", included: true, supported: true, authority: "external_evidence" }),
      expect.objectContaining({ id: "selection", included: true, supported: true, authority: "external_evidence" }),
      expect.objectContaining({ id: "annotations", included: false, supported: false, authority: "unsupported" }),
      expect.objectContaining({ id: "library", included: false, supported: false, authority: "unsupported" }),
      expect.objectContaining({ id: "secondary", included: true, supported: true, mode: "full", authority: "external_evidence" }),
      expect.objectContaining({ id: "draft", included: true, supported: true, authority: "unreviewed_draft" }),
      expect.objectContaining({ id: "screenshot", included: true, supported: true, authority: "external_evidence" }),
    ]);
    expect(capsule.contextItems[3]?.warning).toMatch(/cannot access the Zotero database/i);
    expect(capsule.contextItems[4]?.warning).toMatch(/cannot access the Zotero database/i);
    expect(capsule.secondaryPapers).toEqual([expect.objectContaining({
      authority: "external_evidence",
      mode: "full",
      title: "Secondary paper",
    })]);
    expect(capsule.draft).toMatchObject({ authority: "unreviewed_draft", relativePath: "drafts/notes/visible.qmd" });
    expect(capsule.contextItems[6]?.sourceIdentity).toBe("drafts/notes/visible.qmd");
    expect(capsule.screenshotProvenance).toEqual([{
      authority: "external_evidence",
      kind: "region",
      paperTitle: "Primary Paper",
      pageNumber: 7,
    }]);

    source.paper.title = "Changed";
    source.page.excerpt = "Changed";
    source.selection.text = "Changed";
    source.secondaryPapers[0]!.title = "Changed";
    source.draft.excerpt = "Changed";
    source.screenshotProvenance[0]!.paperTitle = "Changed";
    source.contextItems[0]!.sourceIdentity = "Changed";
    source.subject.paperKey = "Changed";
    expect(capsule.paper?.title).toBe("Primary� Paper");
    expect(capsule.page?.excerpt).toBe("Visible page");
    expect(capsule.selection?.text).toBe("Selected");
    expect(capsule.secondaryPapers[0]?.title).toBe("Secondary paper");
    expect(capsule.draft?.excerpt).toBe("Unreviewed body");
    expect(capsule.screenshotProvenance[0]?.paperTitle).toBe("Primary Paper");
    expect(capsule.contextItems[0]?.sourceIdentity).toBe("zotero:ABCD1234");
    expect(capsule.subject.paperKey).toBe("ABCD1234");
    expect(Object.isFrozen(capsule)).toBe(true);
    expect(Object.isFrozen(capsule.contextItems)).toBe(true);
    expect(Object.isFrozen(capsule.contextItems[0])).toBe(true);
  });

  it("suppresses removed paper and page payloads, bounds Unicode metadata, and warns explicitly", () => {
    const source = input();
    source.contextItems = [
      { id: "selection", kind: "selection", sourceIdentity: "selection" },
      { id: "draft", kind: "draft", sourceIdentity: "drafts/notes/visible.qmd" },
    ];
    source.selection.text = "🧪".repeat(COMPANION_CAPSULE_BOUNDS.selection + 1);
    source.draft.excerpt = "é".repeat(COMPANION_CAPSULE_BOUNDS.draftExcerpt + 1);
    const capsule = buildCompanionCapsule(source, dependencies);

    expect(capsule.paper).toBeNull();
    expect(capsule.page).toBeNull();
    expect([...capsule.selection!.text]).toHaveLength(COMPANION_CAPSULE_BOUNDS.selection);
    expect(capsule.draft).toMatchObject({ truncated: true });
    expect(capsule.warnings.join("\n")).toMatch(/selection.*truncated/i);
    expect(capsule.warnings.join("\n")).toMatch(/draft.*truncated/i);
  });

  it("rejects an unsafe question without rewriting it", () => {
    const source = input();
    source.question = " \t ";
    expect(() => buildCompanionCapsule(source, dependencies)).toThrow(/question/i);

    source.question = "ok\u0000";
    expect(() => buildCompanionCapsule(source, dependencies)).toThrow(/control/i);

    source.question = "🧪".repeat(COMPANION_CAPSULE_BOUNDS.question + 1);
    expect(() => buildCompanionCapsule(source, dependencies)).toThrow(/8,000/i);
  });

  it("contains only allowlisted data and verifies a deterministic canonical checksum", () => {
    const capsule = buildCompanionCapsule(input(), dependencies);
    const serialized = JSON.stringify(capsule);

    expect(capsule).toMatchObject({
      schemaVersion: 1,
      id: "capsule_0123456789abcdef",
      createdAt: "2026-08-01T12:34:56.000Z",
      bounds: COMPANION_CAPSULE_BOUNDS,
    });
    expect(serialized).not.toMatch(/pdfPath|workspace|fullText|data:image|secret|environment|hiddenInstructions|abstract/);
    expect(verifyCompanionCapsule(capsule, dependencies.hash)).toBe(true);
    expect(verifyCompanionCapsule({ ...capsule, question: "corrupted" }, dependencies.hash)).toBe(false);
  });

  it("fails closed on filesystem-shaped values in safe citation metadata", () => {
    const source = input();
    source.paper.url = "file:///workspace/private-paper.pdf";
    source.page.source = "/workspace/private-page.txt";
    source.secondaryPapers[0]!.url = "file:///workspace/private-secondary.pdf";

    const serialized = JSON.stringify(buildCompanionCapsule(source, dependencies));
    expect(serialized).not.toMatch(/file:|workspace|private-(paper|page|secondary)/);
  });

  it("rejects unsafe exact identifiers without normalizing accepted identifiers", () => {
    const exactIdentity = "secondary-e\u0301";
    const source = input();
    source.contextItems[5]!.id = "chip-e\u0301";
    source.contextItems[5]!.sourceIdentity = exactIdentity;
    source.secondaryPapers[0]!.id = exactIdentity;
    const capsule = buildCompanionCapsule(source, dependencies);

    expect(capsule.contextItems[5]).toMatchObject({
      id: "chip-e\u0301",
      sourceIdentity: exactIdentity,
      included: true,
    });

    for (const invalid of [
      "\\\\server\\share\\paper.pdf",
      "/workspace/paper.pdf",
      "C:\\workspace\\paper.pdf",
      "data:image/png;base64,secret",
      "file:///workspace/paper.pdf",
    ]) {
      const unsafe = input();
      unsafe.contextItems[0]!.sourceIdentity = invalid;
      expect(() => buildCompanionCapsule(unsafe, dependencies)).toThrow(/source identity/i);
    }

    const overlong = input();
    overlong.contextItems[0]!.id = "i".repeat(129);
    expect(() => buildCompanionCapsule(overlong, dependencies)).toThrow(/chip id/i);
    overlong.contextItems[0]!.id = "paper";
    overlong.contextItems[0]!.sourceIdentity = "s".repeat(513);
    expect(() => buildCompanionCapsule(overlong, dependencies)).toThrow(/source identity/i);
  });

  it("accepts Draft paths only below the untrusted drafts tree", () => {
    for (const invalid of [
      "knowledge/reviewed.qmd",
      "literature/paper.qmd",
      "drafts\\note.qmd",
      "\\\\server\\share\\drafts\\note.qmd",
      "/drafts/note.qmd",
      "C:\\drafts\\note.qmd",
      "drafts/../knowledge/reviewed.qmd",
      "data:text/plain,draft",
    ]) {
      const source = input();
      source.subject.draftPath = invalid;
      source.draft.relativePath = invalid;
      const capsule = buildCompanionCapsule(source, dependencies);
      expect(capsule.subject.draftPath, invalid).toBeNull();
      expect(capsule.draft, invalid).toBeNull();
    }
  });

  it("omits unsafe page sources including UNC paths and data URLs", () => {
    for (const unsafeSource of [
      "\\\\server\\share\\page.txt",
      "data:image/png;base64,secret",
      "file:///workspace/page.txt",
    ]) {
      const source = input();
      source.page.source = unsafeSource;
      const capsule = buildCompanionCapsule(source, dependencies);
      expect(capsule.page?.source, unsafeSource).toBe("");
      expect(capsule.warnings.join("\n"), unsafeSource).toMatch(/page source.*omitted/i);
    }
  });

  it("bounds all input arrays before searching them", () => {
    const tooManyChips = input();
    tooManyChips.contextItems = Array.from({ length: 65 }, (_, index) => ({
      id: `chip-${index}`,
      kind: "paper",
      sourceIdentity: `paper-${index}`,
    }));
    expect(() => buildCompanionCapsule(tooManyChips, dependencies)).toThrow(/context items/i);

    const tooManyPapers = input();
    tooManyPapers.secondaryPapers = Array.from({ length: 21 }, (_, index) => ({
      ...tooManyPapers.secondaryPapers[0]!,
      id: `secondary-${index}`,
    }));
    expect(() => buildCompanionCapsule(tooManyPapers, dependencies)).toThrow(/secondary papers/i);

    const tooManyScreenshots = input();
    tooManyScreenshots.screenshotProvenance = Array.from({ length: 9 }, (_, index) => ({
      ...tooManyScreenshots.screenshotProvenance[0]!,
      id: `shot-${index}`,
    }));
    expect(() => buildCompanionCapsule(tooManyScreenshots, dependencies)).toThrow(/screenshot provenance/i);
  });

  it("omits secondary and screenshot candidates with invalid runtime union values", () => {
    const source = input();
    delete source.contextItems[5]!.mode;
    (source.secondaryPapers[0] as unknown as { mode: unknown }).mode = {
      nested: "data:image/png;base64,secret",
    };
    (source.screenshotProvenance[0] as unknown as { kind: unknown }).kind = "region".repeat(1_000);

    const capsule = buildCompanionCapsule(source, dependencies);
    expect(capsule.secondaryPapers).toEqual([]);
    expect(capsule.screenshotProvenance).toEqual([]);
    expect(capsule.contextItems[5]).toMatchObject({ included: false, warning: expect.stringMatching(/mode/i) });
    expect(capsule.contextItems[7]).toMatchObject({ included: false, warning: expect.stringMatching(/kind/i) });
    expect(JSON.stringify(capsule)).not.toMatch(/nested|data:image|regionregion/);
  });

  it("exports and applies deterministic bounds to every accepted metadata class", () => {
    const source = input();
    source.paper.title = "🧪".repeat(1_025);
    source.paper.creators = "c".repeat(2_049);
    source.paper.year = "y".repeat(33);
    source.paper.doi = "d".repeat(513);
    source.paper.url = `https://example.test/${"u".repeat(2_049)}`;
    source.page.pageLabel = "p".repeat(129);
    source.screenshotProvenance[0]!.paperTitle = "s".repeat(1_025);
    source.subject.paperKey = "k".repeat(129);

    expect(() => buildCompanionCapsule(source, dependencies)).toThrow(/paper key/i);
    source.subject.paperKey = "ABCD1234";
    const capsule = buildCompanionCapsule(source, dependencies);

    expect(COMPANION_CAPSULE_BOUNDS).toMatchObject({
      contextItems: 34,
      capsuleId: 64,
      chipId: 64,
      sourceIdentity: 64,
      paperKey: 64,
      draftPath: 256,
      contextMode: 32,
      citationTitle: 256,
      citationCreators: 256,
      citationYear: 32,
      citationDoi: 128,
      citationUrl: 256,
      pageLabel: 128,
      pageSource: 32,
      screenshotTitle: 128,
      timestamp: 32,
      contentHash: 64,
    });
    expect([...capsule.paper!.title]).toHaveLength(256);
    expect([...capsule.paper!.creators]).toHaveLength(256);
    expect([...capsule.paper!.year]).toHaveLength(32);
    expect(capsule.paper!.doi).toBe("");
    expect(capsule.paper!.url).toBe("");
    expect([...capsule.page!.pageLabel]).toHaveLength(128);
    expect([...capsule.screenshotProvenance[0]!.paperTitle]).toHaveLength(128);
    expect(capsule.warnings.join("\n")).toMatch(/title.*truncated/i);
    expect(capsule.warnings.join("\n")).toMatch(/creators.*truncated/i);
    expect(capsule.warnings.join("\n")).toMatch(/year.*truncated/i);
    expect(capsule.warnings.join("\n")).toMatch(/doi.*omitted/i);
    expect(capsule.warnings.join("\n")).toMatch(/url.*omitted/i);
    expect(capsule.warnings.join("\n")).toMatch(/page label.*truncated/i);
    expect(capsule.warnings.join("\n")).toMatch(/screenshot title.*truncated/i);
  });

  it("accepts Date or canonical UTC timestamps and rejects ambient-timezone parsing", () => {
    const fromDate = buildCompanionCapsule(input(), {
      ...dependencies,
      now: () => new Date("2026-08-01T12:34:56.000Z"),
    });
    expect(fromDate.createdAt).toBe("2026-08-01T12:34:56.000Z");

    for (const noncanonical of [
      "2026-08-01T12:34:56",
      "2026-08-01T12:34:56+08:00",
      "2026-08-01T12:34:56Z",
      "2026-08-01",
    ]) {
      expect(() => buildCompanionCapsule(input(), {
        ...dependencies,
        now: () => noncanonical,
      }), noncanonical).toThrow(/timestamp/i);
    }

    expect(() => buildCompanionCapsule(input(), {
      ...dependencies,
      now: () => `${"2".repeat(33)}Z`,
    })).toThrow(/timestamp/i);
  });

  it("rejects checksum-valid records that violate handoff trust and path invariants", () => {
    const valid = buildCompanionCapsule(input(), dependencies);
    const signed = (change: (value: any) => void) => {
      const candidate = structuredClone(valid) as any;
      change(candidate);
      const { contentHash: _previous, ...unsigned } = candidate;
      return { ...unsigned, contentHash: dependencies.hash(canonicalCompanionCapsuleJson(unsigned)) };
    };

    for (const candidate of [
      signed((value) => { value.question = " \t "; }),
      signed((value) => { value.question = "question\u0000"; }),
      signed((value) => { value.draft.relativePath = "knowledge/reviewed.qmd"; }),
      signed((value) => { value.subject.draftPath = "literature/paper.qmd"; }),
      signed((value) => { value.paper.url = "file:///private/paper.pdf"; }),
      signed((value) => { value.paper.url = "data:text/plain,private"; }),
      signed((value) => { value.contextItems[0].sourceIdentity = "file:///private/item"; }),
      signed((value) => { value.page.source = "file:///private/page.txt"; }),
      signed((value) => { value.contextItems[0].authority = "unreviewed_draft"; }),
      signed((value) => { value.contextItems[0].included = false; }),
      signed((value) => { value.draft.truncated = true; }),
      signed((value) => { value.contextItems[5].mode = "full"; value.secondaryPapers[0].mode = "retrieval"; }),
    ]) {
      expect(verifyCompanionCapsule(candidate, dependencies.hash)).toBe(false);
    }
  });

  it("deduplicates repeated global metadata warnings so maximum-context capsules remain verifiable", () => {
    const source = input();
    source.contextItems = Array.from({ length: COMPANION_CAPSULE_BOUNDS.contextItems }, (_, index) => ({
      id: `paper-${index}`,
      kind: "paper",
      sourceIdentity: `zotero:paper-${index}`,
    }));
    source.paper = {
      title: "t".repeat(COMPANION_CAPSULE_BOUNDS.citationTitle + 1),
      creators: "c".repeat(COMPANION_CAPSULE_BOUNDS.citationCreators + 1),
      year: "y".repeat(COMPANION_CAPSULE_BOUNDS.citationYear + 1),
      doi: "d".repeat(COMPANION_CAPSULE_BOUNDS.citationDoi + 1),
      url: `https://example.test/${"u".repeat(COMPANION_CAPSULE_BOUNDS.citationUrl + 1)}`,
      pdfPath: "/private/paper.pdf",
      abstract: "never copied",
    };

    const capsule = buildCompanionCapsule(source, dependencies);

    expect(capsule.warnings).toHaveLength(5);
    expect(COMPANION_CAPSULE_WARNING_BOUND).toBe(32);
    expect(capsule.bounds).not.toHaveProperty("warnings");
    expect(verifyCompanionCapsule(capsule, dependencies.hash)).toBe(true);
  });
});
