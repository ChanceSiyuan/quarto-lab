import { describe, expect, it } from "vitest";

import { evidenceRecordFromToolResult } from "../src/codex-service";

describe("evidence ledger", () => {
  it("records page-aware search evidence without preserving an entire PDF", () => {
    const record = evidenceRecordFromToolResult(
      "zotero_search_current_pdf",
      { query: "persistent stochastic gradient" },
      {
        matches: [
          { pageNumber: 5, snippet: "A short result on persistent stochastic gradients." },
          { pageNumber: 7, snippet: "A second supporting passage." },
        ],
      },
      "1-ABC",
    );

    expect(record).toMatchObject({
      tool: "zotero_search_current_pdf",
      paperKey: "1-ABC",
      query: "persistent stochastic gradient",
      pages: [5, 7],
    });
    expect(record?.snippets).toHaveLength(2);
  });

  it("ignores non-evidence mutation tools", () => {
    expect(evidenceRecordFromToolResult("zotero_create_note", {}, {}, "1-ABC")).toBeNull();
  });
});
