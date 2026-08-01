import { describe, expect, it } from "vitest";

import {
  COMPANION_CAPSULE_BOUNDS,
  buildCompanionCapsule,
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
    expect(capsule.screenshotProvenance).toEqual([{ kind: "region", paperTitle: "Primary Paper", pageNumber: 7 }]);

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
      { id: "draft", kind: "draft", sourceIdentity: "draft" },
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
});
