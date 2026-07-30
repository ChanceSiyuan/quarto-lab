import { describe, expect, it } from "vitest";
import {
  QLAB_COMMANDS,
  buildCaptureChatDraftPrompt,
  buildQLabCommandPrompt,
  buildReviewDraftPrompt,
  qlabWritableRoots,
} from "../src/qlab-commands";

describe("QLab command palette", () => {
  it("exposes the six user-facing QLab commands in a stable order", () => {
    expect(QLAB_COMMANDS.map((command) => command.id)).toEqual([
      "qlab_get_paper",
      "qlab_search_literature",
      "qlab_propose_patch",
      "qlab_propose_promotion",
      "qlab_validate",
      "qlab_preview",
    ]);
  });

  it("binds the configured repository and active Zotero item to a command", () => {
    const prompt = buildQLabCommandPrompt("qlab_get_paper", {
      qlabRoot: "/Users/research/qlab",
      zoteroItemKey: "ABCD1234",
    });

    expect(prompt).toContain("/Users/research/qlab");
    expect(prompt).toContain("ABCD1234");
    expect(prompt).toContain("literature/");
    expect(prompt).toContain("read-only");
  });

  it("keeps promotion review-only until the user explicitly approves it", () => {
    const prompt = buildQLabCommandPrompt("qlab_propose_promotion", {
      qlabRoot: "/repo",
      zoteroItemKey: "ITEM0001",
    });

    expect(prompt).toContain("do not write to knowledge/");
    expect(prompt).toContain("explicitly approves");
    expect(prompt).toContain("make knowledge-check");
  });

  it("binds the reading-note action to the repository chat-capture skill", () => {
    const prompt = buildCaptureChatDraftPrompt({
      qlabRoot: "/repo",
      zoteroItemKey: "ITEM0001",
    });

    expect(prompt).toContain("$capture-chat-draft");
    expect(prompt).toContain("skills/capture-chat-draft/SKILL.md");
    expect(prompt).toContain("drafts/reading-notes/");
    expect(prompt).toContain("ITEM0001");
    expect(prompt).toContain("Never write to knowledge/");
  });

  it("limits Agent writes to untrusted content and generated work trees", () => {
    expect(qlabWritableRoots("/repo")).toEqual([
      "/repo/drafts",
      "/repo/literature",
      "/repo/work",
    ]);
    expect(qlabWritableRoots("/repo")).not.toContain("/repo/knowledge");
  });

  it("binds Draft Preview review to one file without granting promotion permission", () => {
    const prompt = buildReviewDraftPrompt({
      qlabRoot: "/repo",
      zoteroItemKey: "ITEM0001",
    }, "drafts/topic/note.qmd");

    expect(prompt).toContain("skills/review-draft/SKILL.md");
    expect(prompt).toContain("drafts/topic/note.qmd");
    expect(prompt).toContain("ITEM0001");
    expect(prompt).toContain("review-only");
    expect(prompt).toContain("publish intent");
    expect(prompt).toContain(`npm run draft:check -- --file "drafts/topic/note.qmd"`);
    expect(prompt).toContain("do not modify");
    expect(prompt).toContain("does not approve final promotion");
    expect(prompt).toContain("current Zotero PDF");
  });
});
