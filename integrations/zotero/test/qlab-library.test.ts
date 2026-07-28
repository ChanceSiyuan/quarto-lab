import { describe, expect, it } from "vitest";
import { buildLiteratureImportPlan, normalizeLiteratureRecord } from "../src/qlab-library";

function fixture(overrides: Record<string, unknown> = {}) {
  return {
    topic: "dynamics",
    paperDir: "/repo/literature/collections/dynamics/papers/ITEM0001_paper",
    manifest: {
      schema_version: 2,
      paper: {
        title: "Paper",
        authors: [{ first: "Ada", last: "Lovelace" }],
        year: 2024,
        identifiers: { doi: "10.1234/EXAMPLE" },
        primary_topic: "dynamics",
        indexed_topics: ["dynamics", "algorithms"],
        zotero_item_key: "ITEM0001",
        collections: [
          { key: "C-DYN", name: "Dynamics", path: "Dynamics" },
          { key: "C-SHOR", name: "Shor", path: "Algorithms/Shor" },
        ],
      },
      files: [
        { path: "paper.pdf", role: "primary-pdf" },
        { path: "source/main.tex", role: "latex-entrypoint" },
        { path: "figures/plot.png", role: "figure" },
      ],
    },
    ...overrides,
  };
}

describe("QLab literature import", () => {
  it("links only the paper PDF and LaTeX entrypoint", () => {
    expect(normalizeLiteratureRecord(fixture() as any).attachments).toEqual([
      { path: "paper.pdf", role: "primary-pdf", title: "QLab · Paper PDF" },
      { path: "source/main.tex", role: "latex-entrypoint", title: "QLab · LaTeX Source" },
    ]);
  });

  it("keeps one item in every source collection without duplicating the paper", () => {
    const plan = buildLiteratureImportPlan([fixture(), fixture({ topic: "algorithms" })] as any);
    expect(plan).toHaveLength(1);
    expect(plan[0]!.collectionPaths).toEqual(["Algorithms/Shor", "Dynamics"]);
  });

  it("fails closed for unknown manifests", () => {
    const value = fixture() as any;
    value.manifest.schema_version = 1;
    expect(() => normalizeLiteratureRecord(value)).toThrow(/Unsupported QLab manifest/);
  });
});
