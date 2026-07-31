// @vitest-environment happy-dom
import { describe, expect, it, vi } from "vitest";
import {
  NOTE_FROM_QMD_TOOL,
  NoteDraftBridgeService,
  buildQmdDraftFromNote,
  classifyNoteDraftSync,
  noteHtmlToQmdBody,
  parseQmdAuthorityMarker,
  qmdToSafeNoteHtml,
  type NoteDraftBridgeHost,
  type NoteDraftLink,
} from "../src/note-draft-bridge";

const qmd = `---
title: "A useful paper"
description: "Reviewed reading notes"
categories: [theory]
---

# Main result

The bound is **quadratic** and $E = mc^2$.
`;

function link(overrides: Partial<NoteDraftLink> = {}): NoteDraftLink {
  return {
    schemaVersion: 1,
    authority: "qmd",
    qmdPath: "drafts/reading-notes/a-useful-paper.qmd",
    qmdSha256: "old-qmd",
    zotero: {
      libraryID: 1,
      noteKey: "NOTE1",
      parentItemKey: "PARENT",
      version: 7,
      contentSha256: "old-note",
    },
    syncedAt: "2026-07-31T00:00:00.000Z",
    ...overrides,
  };
}

function harness(options: {
  linked?: NoteDraftLink;
  source?: string;
  sha?: string;
  noteVersion?: number;
  noteContentSha256?: string;
  noteHtml?: string;
  noteTitle?: string;
  noteParentItemKey?: string;
} = {}) {
  let qmdSource = options.source ?? qmd;
  let qmdSha = options.sha ?? "new-qmd";
  let currentLink = options.linked ?? null;
  let note = {
    html: options.noteHtml ?? "<p>Old note</p>",
    title: options.noteTitle ?? "Old note",
    parentItemKey: options.noteParentItemKey ?? "PARENT",
    version: options.noteVersion ?? 7,
    contentSha256: options.noteContentSha256 ?? "old-note",
  };
  const host: NoteDraftBridgeHost = {
    readQmd: vi.fn(async () => ({ source: qmdSource, sha256: qmdSha })),
    readNote: vi.fn(async () => structuredClone(note)),
    readLink: vi.fn(async () => currentLink),
    writeLink: vi.fn(async (next) => { currentLink = structuredClone(next); }),
    createNote: vi.fn(async (input) => {
      note = {
        html: input.html,
        title: input.title,
        parentItemKey: input.parentItemKey,
        version: 1,
        contentSha256: "created-note",
      };
      return { noteKey: "NEWNOTE", version: 1 };
    }),
    updateNote: vi.fn(async (input) => {
      note = {
        html: input.html,
        title: input.title,
        parentItemKey: input.parentItemKey,
        version: input.expectedVersion + 1,
        contentSha256: "written-note",
      };
      return { noteKey: input.noteKey, version: input.expectedVersion + 1 };
    }),
    restoreNote: vi.fn(async (input) => {
      note = {
        html: input.html,
        title: input.title,
        parentItemKey: input.parentItemKey,
        version: input.expectedVersion + 1,
        contentSha256: "restored-note",
      };
      return { noteKey: input.noteKey, version: input.expectedVersion + 1 };
    }),
    deleteNote: vi.fn(async () => {}),
  };
  let sequence = 0;
  const service = new NoteDraftBridgeService(host, { onState: vi.fn() },
    () => new Date("2026-07-31T00:00:00.000Z"),
    (prefix) => `${prefix}-${++sequence}`);
  return {
    service,
    host,
    link: () => currentLink,
    setQmd(source: string, sha: string) { qmdSource = source; qmdSha = sha; },
    setNoteVersion(version: number) { note.version = version; },
    setNoteContentSha256(contentSha256: string) { note.contentSha256 = contentSha256; },
  };
}

describe("safe Zotero Note and QMD conversion", () => {
  it("removes active HTML, event handlers, and unsafe links while retaining readable text", () => {
    const body = noteHtmlToQmdBody(`
      <style>body { display:none }</style><script>alert(1)</script>
      <h2 onclick="steal()">Result</h2>
      <p>The <strong>bound</strong> holds <img src=x onerror="steal()" alt="plot"></p>
      <p><a href="javascript:steal()">bad link</a> <a href="https://example.org/paper">paper</a></p>
    `);

    expect(body).toContain("## Result");
    expect(body).toContain("**bound**");
    expect(body).toContain("plot");
    expect(body).toContain("[paper](https://example.org/paper)");
    expect(body).not.toMatch(/script|style|onclick|onerror|javascript|alert\(/i);
  });

  it("builds a Draft with only the strict trusted keys and a recoverable QMD-authority marker", () => {
    const source = buildQmdDraftFromNote({
      title: "Imported note",
      description: "Imported from a Zotero Note",
      category: "experiment",
      noteHtml: "<p>Observation <em>one</em>.</p>",
      identity: { libraryID: 1, noteKey: "NOTE1", parentItemKey: "PARENT" },
    });

    const yaml = source.slice(4, source.indexOf("\n---", 4));
    expect(yaml.split("\n").map((line) => line.split(":", 1)[0])).toEqual([
      "title", "description", "categories",
    ]);
    expect(source).toContain("categories: [experiment]");
    expect(source).toContain("Observation *one*.");
    expect(parseQmdAuthorityMarker(source)).toEqual({
      authority: "qmd", libraryID: 1, noteKey: "NOTE1", parentItemKey: "PARENT",
    });
  });

  it("renders QMD to inert Note HTML and preserves an authority backlink", () => {
    const html = qmdToSafeNoteHtml(`${qmd}\n<script>alert(1)</script>`, {
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd",
    });

    expect(html).toContain("<h1>Main result</h1>");
    expect(html).toContain("<strong>quadratic</strong>");
    expect(html).toContain("$E = mc^2$");
    expect(html).toContain("qlab-qmd-draft:");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
  });

  it("accepts the repository's compliant block-list category spelling", () => {
    const source = qmd.replace("categories: [theory]", "categories:\n  - theory");
    expect(qmdToSafeNoteHtml(source, {
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd",
    })).toContain("<h1>Main result</h1>");
  });
});

describe("classifyNoteDraftSync", () => {
  it.each([
    [null, "q1", 1, "n1", "unlinked"],
    [link({ qmdSha256: "q1", zotero: { libraryID: 1, noteKey: "NOTE1", parentItemKey: "PARENT", version: 1, contentSha256: "n1" } }), "q1", 1, "n1", "in-sync"],
    [link({ qmdSha256: "q1", zotero: { libraryID: 1, noteKey: "NOTE1", parentItemKey: "PARENT", version: 1, contentSha256: "n1" } }), "q2", 1, "n1", "qmd-changed"],
    [link({ qmdSha256: "q1", zotero: { libraryID: 1, noteKey: "NOTE1", parentItemKey: "PARENT", version: 1, contentSha256: "n1" } }), "q1", 1, "n2", "note-changed"],
    [link({ qmdSha256: "q1", zotero: { libraryID: 1, noteKey: "NOTE1", parentItemKey: "PARENT", version: 1, contentSha256: "n1" } }), "q2", 1, "n2", "both-changed"],
  ] as const)("classifies independent revisions using both version and content", (baseline, currentQmd, currentVersion, currentContent, expected) => {
    expect(classifyNoteDraftSync(baseline, currentQmd, currentVersion, currentContent)).toBe(expected);
  });
});

describe("NoteDraftBridgeService", () => {
  it("proposes a new native Zotero Note without writing before review", async () => {
    const { service, host } = harness({ linked: undefined });

    expect(service.tools[0]?.name).toBe(NOTE_FROM_QMD_TOOL);
    const result = await service.invokeTool(NOTE_FROM_QMD_TOOL, {
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd",
      libraryID: 1,
      parentItemKey: "PARENT",
    });

    expect(result).toMatchObject({ status: "awaiting_user_review", reviewId: "note-review-1" });
    expect(host.createNote).not.toHaveBeenCalled();
    expect(service.getReviews()[0]).toMatchObject({ state: "pending" });
    expect(service.getReviews()[0]!.diff).toContain("drafts/reading-notes/a-useful-paper.qmd");
  });

  it("creates the Note once after acceptance and records a QMD-authoritative link", async () => {
    const { service, host, link: currentLink } = harness();
    await service.invokeTool(NOTE_FROM_QMD_TOOL, {
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd",
      libraryID: 1,
      parentItemKey: "PARENT",
    });

    await expect(service.resolveReview("note-review-1", "accept")).resolves.toEqual({
      decision: "accepted", noteKey: "NEWNOTE", version: 1,
    });
    expect(host.createNote).toHaveBeenCalledWith(expect.objectContaining({
      libraryID: 1,
      parentItemKey: "PARENT",
      html: expect.stringContaining("qlab-qmd-draft:"),
    }));
    expect(currentLink()).toMatchObject({
      authority: "qmd",
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd",
      qmdSha256: "new-qmd",
      zotero: { noteKey: "NEWNOTE", version: 1, contentSha256: "created-note" },
    });
  });

  it("claims a Note review synchronously so a double acceptance cannot create two Notes", async () => {
    const { service, host } = harness();
    let release!: (value: { noteKey: string; version: number }) => void;
    const gate = new Promise<{ noteKey: string; version: number }>((resolve) => { release = resolve; });
    vi.mocked(host.createNote).mockImplementationOnce(() => gate);
    await service.invokeTool(NOTE_FROM_QMD_TOOL, {
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd", libraryID: 1, parentItemKey: "PARENT",
    });

    const first = service.resolveReview("note-review-1", "accept");
    const second = service.resolveReview("note-review-1", "accept");
    await expect(second).rejects.toThrow(/already resolved|being applied/i);
    vi.mocked(host.readNote).mockResolvedValueOnce({
      html: "<h1>A useful paper</h1><p>Created note</p>",
      title: "A useful paper",
      parentItemKey: "PARENT",
      version: 1,
      contentSha256: "created-note",
    });
    release({ noteKey: "NEWNOTE", version: 1 });
    await first;
    expect(host.createNote).toHaveBeenCalledTimes(1);
  });

  it("deletes a newly-created Note if the recoverable link cannot be persisted", async () => {
    const { service, host } = harness();
    vi.mocked(host.writeLink).mockRejectedValueOnce(new Error("link disk full"));
    await service.invokeTool(NOTE_FROM_QMD_TOOL, {
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd", libraryID: 1, parentItemKey: "PARENT",
    });

    await expect(service.resolveReview("note-review-1", "accept"))
      .rejects.toThrow("link disk full");
    expect(host.deleteNote).toHaveBeenCalledWith(1, "NEWNOTE");
    expect(service.getReviews()[0]?.state).toBe("failed");
  });

  it("updates a linked Note only when the QMD changed and the Note did not", async () => {
    const existing = link();
    const { service, host } = harness({ linked: existing, sha: "new-qmd", noteVersion: 7 });
    await service.invokeTool(NOTE_FROM_QMD_TOOL, { qmdPath: existing.qmdPath });
    await service.resolveReview("note-review-1", "accept");

    expect(host.updateNote).toHaveBeenCalledWith(expect.objectContaining({
      libraryID: 1, noteKey: "NOTE1", expectedVersion: 7,
    }));
    expect(host.createNote).not.toHaveBeenCalled();
  });

  it("restores the previous Note body, title, and parent if an update succeeds but link persistence fails", async () => {
    const existing = link();
    const { service, host } = harness({
      linked: existing,
      sha: "new-qmd",
      noteHtml: "<p>Before</p>",
      noteTitle: "Before title",
      noteParentItemKey: "PARENT",
    });
    vi.mocked(host.writeLink).mockRejectedValueOnce(new Error("link disk full"));
    await service.invokeTool(NOTE_FROM_QMD_TOOL, { qmdPath: existing.qmdPath });

    await expect(service.resolveReview("note-review-1", "accept"))
      .rejects.toThrow("link disk full");
    expect(host.restoreNote).toHaveBeenCalledWith({
      libraryID: 1,
      noteKey: "NOTE1",
      expectedVersion: 8,
      html: "<p>Before</p>",
      title: "Before title",
      parentItemKey: "PARENT",
    });
    expect(service.getReviews()[0]?.state).toBe("failed");
  });

  it("refuses to overwrite a Note changed since the last QMD-authoritative export", async () => {
    const existing = link();
    const noteChanged = harness({ linked: existing, sha: "old-qmd", noteVersion: 8 });
    await expect(noteChanged.service.invokeTool(NOTE_FROM_QMD_TOOL, { qmdPath: existing.qmdPath }))
      .rejects.toThrow(/Note changed/i);
    expect(noteChanged.host.updateNote).not.toHaveBeenCalled();

    const bothChanged = harness({ linked: existing, sha: "new-qmd", noteVersion: 8 });
    await expect(bothChanged.service.invokeTool(NOTE_FROM_QMD_TOOL, { qmdPath: existing.qmdPath }))
      .rejects.toThrow(/both.*changed/i);

    const sameVersionDifferentContent = harness({
      linked: existing,
      sha: "old-qmd",
      noteVersion: 7,
      noteContentSha256: "externally-edited-without-version-change",
    });
    await expect(sameVersionDifferentContent.service.invokeTool(NOTE_FROM_QMD_TOOL, { qmdPath: existing.qmdPath }))
      .rejects.toThrow(/Note changed/i);
    expect(sameVersionDifferentContent.host.updateNote).not.toHaveBeenCalled();
  });

  it("offers a reviewed binding to the existing source Note when its marker survives but the link cache is missing", async () => {
    const marked = buildQmdDraftFromNote({
      title: "Imported note",
      description: "Imported from Zotero",
      category: "theory",
      noteHtml: "<p>Body</p>",
      identity: { libraryID: 1, noteKey: "NOTE1", parentItemKey: "PARENT" },
    });
    const { service, host, link: currentLink, setQmd } = harness({ source: marked, sha: "marked-qmd" });

    await expect(service.invokeTool(NOTE_FROM_QMD_TOOL, {
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd", libraryID: 1, parentItemKey: "PARENT",
    })).resolves.toMatchObject({ status: "awaiting_user_review", reviewId: "note-review-1" });
    expect(host.createNote).not.toHaveBeenCalled();
    expect(host.updateNote).not.toHaveBeenCalled();

    await service.resolveReview("note-review-1", "accept");
    expect(currentLink()).toMatchObject({
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd",
      qmdSha256: "marked-qmd",
      zotero: {
        libraryID: 1,
        noteKey: "NOTE1",
        parentItemKey: "PARENT",
        version: 7,
        contentSha256: "old-note",
      },
    });
    expect(host.createNote).not.toHaveBeenCalled();
    expect(host.updateNote).not.toHaveBeenCalled();

    setQmd(`${marked}\nEdited in the authoritative Draft.\n`, "edited-qmd");
    await service.invokeTool(NOTE_FROM_QMD_TOOL, {
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd",
    });
    await service.resolveReview("note-review-2", "accept");
    expect(host.updateNote).toHaveBeenCalledTimes(1);
    expect(host.createNote).not.toHaveBeenCalled();
  });

  it("revalidates QMD and Note content at Apply time even when the Note version is unchanged", async () => {
    const existing = link();
    const { service, host, setNoteContentSha256 } = harness({ linked: existing, sha: "new-qmd", noteVersion: 7 });
    await service.invokeTool(NOTE_FROM_QMD_TOOL, { qmdPath: existing.qmdPath });
    setNoteContentSha256("changed-with-the-same-version");

    await expect(service.resolveReview("note-review-1", "accept"))
      .rejects.toThrow(/changed after this review/i);
    expect(host.updateNote).not.toHaveBeenCalled();
  });

  it("rejects traversal and Knowledge paths before reading anything", async () => {
    const { service, host } = harness();
    await expect(service.invokeTool(NOTE_FROM_QMD_TOOL, {
      qmdPath: "drafts/../knowledge/secret.qmd", libraryID: 1, parentItemKey: "PARENT",
    })).rejects.toThrow(/safe Draft/i);
    await expect(service.invokeTool(NOTE_FROM_QMD_TOOL, {
      qmdPath: "knowledge/index.qmd", libraryID: 1, parentItemKey: "PARENT",
    })).rejects.toThrow(/safe Draft/i);
    expect(host.readQmd).not.toHaveBeenCalled();
  });

  it("rejects a proposal without creating or updating a Note", async () => {
    const { service, host } = harness();
    await service.invokeTool(NOTE_FROM_QMD_TOOL, {
      qmdPath: "drafts/reading-notes/a-useful-paper.qmd", libraryID: 1, parentItemKey: "PARENT",
    });
    await expect(service.resolveReview("note-review-1", "reject"))
      .resolves.toEqual({ decision: "rejected" });
    expect(host.createNote).not.toHaveBeenCalled();
    expect(host.updateNote).not.toHaveBeenCalled();
  });
});
