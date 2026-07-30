import { describe, expect, it } from "vitest";
import {
  isQLabRepositoryShape,
  normalizeQLabRoot,
  qlabRepositoryState,
  type QLabPathHost,
} from "../src/qlab-workspace";

function host(existing: string[]): QLabPathHost {
  return {
    exists: async (path) => existing.includes(path),
    realPath: async (path) => path.replace("/alias", "/real"),
    entries: async (path) => existing.filter((entry) => entry.startsWith(`${path}/`) && !entry.slice(path.length + 1).includes("/")),
    join: (...parts) => parts.join("/").replace(/\/+/g, "/"),
    filename: (path) => path.split("/").at(-1) || "",
  };
}

describe("QLab workspace selection", () => {
  it("accepts only a repository root with the trusted workspace boundaries", async () => {
    const paths = [
      "/repo/AGENTS.md",
      "/repo/qlab",
      "/repo/literature",
      "/repo/drafts",
      "/repo/knowledge",
    ];
    expect(await isQLabRepositoryShape("/repo", host(paths))).toBe(true);
    expect(await isQLabRepositoryShape("/other", host(paths))).toBe(false);
  });

  it("canonicalizes a selected root before saving it", async () => {
    const value = await normalizeQLabRoot("  /alias/qlab/  ", host([]));
    expect(value).toBe("/real/qlab");
  });

  it("accepts an empty first-run folder and an interrupted starter, but rejects unrelated files", async () => {
    expect(await qlabRepositoryState("", host([]))).toBe("missing");
    expect(await qlabRepositoryState("/empty", host([]))).toBe("empty");
    expect(await qlabRepositoryState("/finder", host(["/finder/.DS_Store", "/finder/.git"])))
      .toBe("empty");
    expect(await qlabRepositoryState("/partial", host(["/partial/.research-loop/starter.json"])))
      .toBe("partial");
    expect(await qlabRepositoryState("/notes", host([
      "/notes/knowledge",
      "/notes/drafts",
      "/notes/literature",
    ]))).toBe("partial");
    expect(await qlabRepositoryState("/documents", host(["/documents/notes.txt"])))
      .toBe("incompatible");
  });
});
