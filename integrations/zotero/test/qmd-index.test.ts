// @vitest-environment happy-dom

import { describe, expect, it } from "vitest";
import {
  buildQmdIndex,
  filterQmdIndex,
  groupIntoTree,
  type QmdIndexScanner,
} from "../src/qmd-index";

function scanner(tree: Record<string, string[]>): QmdIndexScanner {
  return {
    async list(directory) {
      const names = tree[directory];
      if (names === undefined) throw new Error(`no such directory ${directory}`);
      return names.map((name) => ({
        name: name.replace(/\/$/, ""),
        directory: name.endsWith("/"),
      }));
    },
  };
}

const FIXTURE = scanner({
  "/repo/knowledge": ["Magic/", "index.qmd", "_quarto.yml", "styles.css"],
  "/repo/knowledge/Magic": ["Bell_magic.qmd", "Bell_table.svg"],
  "/repo/drafts": ["Dynamics/", "_quarto.yml"],
  "/repo/drafts/Dynamics": [
    "floquet.qmd",
    "floquet.qlab-preview-aaaaaaaaaaaa.qmd",
    ".preview/",
  ],
  "/repo/drafts/Dynamics/.preview": ["floquet.html"],
});

describe("buildQmdIndex", () => {
  it("indexes QMD files under both trees and nothing else", async () => {
    const entries = await buildQmdIndex(FIXTURE, "/repo");
    // Locale ordering, so the list reads the way a person would sort it.
    expect(entries.map((entry) => entry.relativePath)).toEqual([
      "drafts/Dynamics/floquet.qmd",
      "knowledge/index.qmd",
      "knowledge/Magic/Bell_magic.qmd",
    ]);
    expect(entries.find((entry) => entry.treeId === "drafts")?.name).toBe("floquet");
  });

  it("skips generated preview output", async () => {
    const entries = await buildQmdIndex(FIXTURE, "/repo");
    expect(entries.some((entry) => entry.relativePath.includes(".preview"))).toBe(false);
    expect(entries.some((entry) => entry.relativePath.includes(".qlab-preview-"))).toBe(false);
  });

  it("treats a missing tree as empty rather than as a failure", async () => {
    const entries = await buildQmdIndex(scanner({ "/repo/knowledge": ["a.qmd"] }), "/repo");
    expect(entries.map((entry) => entry.relativePath)).toEqual(["knowledge/a.qmd"]);
  });
});

describe("filterQmdIndex", () => {
  it("matches on the path and ranks name hits first", async () => {
    const entries = await buildQmdIndex(FIXTURE, "/repo");
    expect(filterQmdIndex(entries, "bell").map((entry) => entry.name)).toEqual(["Bell_magic"]);
    expect(filterQmdIndex(entries, "magbel")).toEqual([]);
    expect(filterQmdIndex(entries, "magic/bell").map((entry) => entry.name)).toEqual(["Bell_magic"]);
    expect(filterQmdIndex(entries, "").length).toBe(3);
  });

  it("is case-insensitive", async () => {
    const entries = await buildQmdIndex(FIXTURE, "/repo");
    expect(filterQmdIndex(entries, "BELL").length).toBe(1);
  });
});

describe("groupIntoTree", () => {
  it("nests entries under one node per tree, directories before files", async () => {
    const roots = groupIntoTree(await buildQmdIndex(FIXTURE, "/repo"));
    expect(roots.map((node) => node.name)).toEqual(["knowledge", "drafts"]);
    const knowledge = roots[0]!;
    expect(knowledge.children.map((node) => node.name)).toEqual(["Magic", "index"]);
    expect(knowledge.children[0]!.children[0]!.entry?.relativePath)
      .toBe("knowledge/Magic/Bell_magic.qmd");
    expect(roots[1]!.children[0]!.name).toBe("Dynamics");
  });

  it("keeps both roots even when one tree is empty", () => {
    const roots = groupIntoTree([]);
    expect(roots.map((node) => node.name)).toEqual(["knowledge", "drafts"]);
    expect(roots.every((node) => node.children.length === 0)).toBe(true);
  });
});
