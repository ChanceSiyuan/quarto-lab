// @vitest-environment happy-dom

import { describe, expect, it } from "vitest";
import {
  EDITOR_TREES,
  isEditablePath,
  knowledgeUrlToQmdPath,
  previewPathFor,
  resolveEditablePath,
  treeForPath,
} from "../src/editor-tree";

const KNOWLEDGE = EDITOR_TREES.find((tree) => tree.id === "knowledge")!;
const DRAFTS = EDITOR_TREES.find((tree) => tree.id === "drafts")!;

describe("treeForPath", () => {
  it("routes each tree by its own prefix and refuses everything else", () => {
    expect(treeForPath("knowledge/Magic/Bell_magic.qmd")?.id).toBe("knowledge");
    expect(treeForPath("drafts/Dynamics/note.qmd")?.id).toBe("drafts");
    expect(treeForPath("literature/ref.bib")).toBeNull();
    expect(treeForPath("knowledge/Magic/Bell_magic.md")).toBeNull();
    expect(treeForPath("Bell_magic.qmd")).toBeNull();
  });

  it("refuses traversal, empty, current-directory and option-like components", () => {
    expect(isEditablePath("knowledge/../literature/ref.qmd")).toBe(false);
    expect(isEditablePath("knowledge/./a.qmd")).toBe(false);
    expect(isEditablePath("knowledge//a.qmd")).toBe(false);
    expect(isEditablePath("drafts/a/../../knowledge/b.qmd")).toBe(false);
    expect(isEditablePath("drafts/--output-dir=/a.qmd")).toBe(false);
  });
});

describe("tree policy", () => {
  it("gives knowledge a validation gate and drafts none, and publishes only knowledge", () => {
    expect(KNOWLEDGE.published).toBe(true);
    expect(KNOWLEDGE.validateCommand).toBe("npm run knowledge:check");
    expect(DRAFTS.published).toBe(false);
    expect(DRAFTS.validateCommand).toBeNull();
  });
});

describe("resolveEditablePath", () => {
  it("joins a containable path and refuses one that leaves its tree", () => {
    expect(resolveEditablePath("/repo", "knowledge/a/b.qmd")).toBe("/repo/knowledge/a/b.qmd");
    expect(resolveEditablePath("/repo/", "drafts/x.qmd")).toBe("/repo/drafts/x.qmd");
    expect(() => resolveEditablePath("/repo", "knowledge/../../etc/passwd.qmd")).toThrow();
    expect(() => resolveEditablePath("/repo", "literature/x.qmd")).toThrow();
    expect(() => resolveEditablePath("", "knowledge/a.qmd")).toThrow();
  });
});

describe("knowledgeUrlToQmdPath", () => {
  it("maps published knowledge pages but refuses generated and non-knowledge routes", () => {
    expect(knowledgeUrlToQmdPath("http://127.0.0.1:4180/knowledge/")).toBe("knowledge/index.qmd");
    expect(knowledgeUrlToQmdPath("http://127.0.0.1:4180/knowledge/models/hubbard/MODEL.html"))
      .toBe("knowledge/models/hubbard/MODEL.qmd");
    expect(knowledgeUrlToQmdPath("http://127.0.0.1:4180/knowledge/categories/theory.html")).toBeNull();
    expect(knowledgeUrlToQmdPath("http://127.0.0.1:4180/knowledge/search.html")).toBeNull();
    expect(knowledgeUrlToQmdPath("http://127.0.0.1:4180/")).toBeNull();
    expect(knowledgeUrlToQmdPath("http://example.com/knowledge/a.html")).toBeNull();
    expect(knowledgeUrlToQmdPath("not a url")).toBeNull();
  });
});

describe("previewPathFor", () => {
  it("maps a knowledge page onto its served route and a draft onto its own file", () => {
    expect(previewPathFor(KNOWLEDGE, "knowledge/index.qmd")).toBe("/");
    expect(previewPathFor(KNOWLEDGE, "knowledge/a/index.qmd")).toBe("/a/");
    expect(previewPathFor(KNOWLEDGE, "knowledge/a/b.qmd")).toBe("/a/b.html");
    expect(previewPathFor(DRAFTS, "drafts/a/b.qmd")).toBe("/a/b.html");
  });
});
