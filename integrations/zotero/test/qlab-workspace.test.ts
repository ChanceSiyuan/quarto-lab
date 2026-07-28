import { describe, expect, it } from "vitest";
import {
  isQLabRepositoryShape,
  normalizeQLabRoot,
  type QLabPathHost,
} from "../src/qlab-workspace";

function host(existing: string[]): QLabPathHost {
  return {
    exists: async (path) => existing.includes(path),
    realPath: async (path) => path.replace("/alias", "/real"),
    join: (...parts) => parts.join("/").replace(/\/+/g, "/"),
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
});
