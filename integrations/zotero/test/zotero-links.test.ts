import { describe, expect, it } from "vitest";

import { parseZoteroLink } from "../src/zotero-links";

describe("parseZoteroLink", () => {
  it("parses a user-library open-pdf link with a page", () => {
    expect(parseZoteroLink("zotero://open-pdf/library/items/AB12CD34?page=12")).toEqual({
      action: "open-pdf",
      library: { kind: "user" },
      objectKind: "items",
      key: "AB12CD34",
      page: 12,
    });
  });

  it("parses a group-library open-pdf link", () => {
    expect(parseZoteroLink("zotero://open-pdf/groups/451/items/K7?page=3")).toEqual({
      action: "open-pdf",
      library: { kind: "group", groupID: 451 },
      objectKind: "items",
      key: "K7",
      page: 3,
    });
  });

  it("parses a select link without a page", () => {
    expect(parseZoteroLink("zotero://select/library/collections/C1")).toEqual({
      action: "select",
      library: { kind: "user" },
      objectKind: "collections",
      key: "C1",
    });
  });

  it("rejects everything else", () => {
    expect(parseZoteroLink("zotero://weird/thing")).toBeNull();
    expect(parseZoteroLink("https://example.com")).toBeNull();
    expect(parseZoteroLink("zotero://open-pdf/library/items/")).toBeNull();
    expect(parseZoteroLink("zotero://open-pdf/library/items/K?page=abc")).toBeNull();
    expect(parseZoteroLink("zotero://open-pdf/groups/notanumber/items/K")).toBeNull();
  });
});
