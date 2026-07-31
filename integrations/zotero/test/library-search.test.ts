import { describe, expect, it } from "vitest";

import {
  aggregateLibrarySearchDocuments,
  buildLibraryMetadataIndex,
  searchLibraryMetadata,
  tokenizeLibrarySearch,
  type LibrarySearchItemInput,
} from "../src/library-search";

const item = (
  key: string,
  title: string,
  extra: Partial<LibrarySearchItemInput> = {},
): LibrarySearchItemInput => ({
  _topLevel: true,
  key,
  itemType: "journalArticle",
  title,
  creators: [],
  date: "2025",
  publicationTitle: "",
  DOI: "",
  abstractNote: "",
  tags: [],
  collections: [],
  collectionKeys: [],
  version: 1,
  ...extra,
});

describe("library metadata BM25F", () => {
  it("normalizes compatibility characters and emits overlapping CJK bigrams", () => {
    expect(tokenizeLibrarySearch("Ｑｕａｎｔｕｍ 量子纠错")).toEqual([
      "quantum",
      "量子",
      "子纠",
      "纠错",
    ]);
  });

  it("aggregates PDF attachments into their top-level bibliographic item", () => {
    const documents = aggregateLibrarySearchDocuments([
      item("ITEM0001", "Fault-tolerant quantum memories"),
      item("PDF00001", "", {
        _topLevel: false,
        itemType: "attachment",
        parentItem: "ITEM0001",
        filename: "fault-tolerant-memory.pdf",
        contentType: "application/pdf",
      }),
      item("NOTE0001", "", {
        _topLevel: false,
        itemType: "note",
        parentItem: "ITEM0001",
      }),
    ], []);

    expect(documents).toHaveLength(1);
    expect(documents[0]).toMatchObject({
      itemKey: "ITEM0001",
      attachmentKeys: ["PDF00001"],
      filenames: ["fault-tolerant-memory.pdf"],
    });
  });

  it("weights title matches above abstract-only matches and reports matched fields", () => {
    const index = buildLibraryMetadataIndex([
      item("TITLE001", "Topological decoding threshold"),
      item("ABSTRACT", "A generic decoder", {
        abstractNote: "We derive a topological decoding threshold for noisy syndrome data.",
      }),
    ], []);

    const hits = searchLibraryMetadata(index, "topological decoding threshold");
    expect(hits.map((hit) => hit.itemKey)).toEqual(["TITLE001", "ABSTRACT"]);
    expect(hits[0]?.matchedFields).toContain("title");
    expect(hits[1]?.matchedFields).toContain("abstract");
    expect(hits[0]!.score).toBeGreaterThan(hits[1]!.score);
  });

  it("gives an exact DOI match a deterministic boost", () => {
    const index = buildLibraryMetadataIndex([
      item("DOI00001", "An unrelated title", { DOI: "10.1103/PhysRevA.1.2" }),
      item("TITLE001", "10.1103 PhysRevA 1 2 explained"),
    ], []);

    const hits = searchLibraryMetadata(index, "10.1103/physreva.1.2");
    expect(hits[0]).toMatchObject({ itemKey: "DOI00001" });
    expect(hits[0]?.matchedFields).toContain("doi");
  });

  it("matches CJK queries without requiring whitespace", () => {
    const index = buildLibraryMetadataIndex([
      item("CJK00001", "量子纠错码的容错阈值"),
      item("OTHER001", "量子算法综述"),
    ], []);

    expect(searchLibraryMetadata(index, "量子纠错").map((hit) => hit.itemKey)).toEqual([
      "CJK00001",
    ]);
  });

  it("applies structured tag, collection, type, and year filters before ranking", () => {
    const index = buildLibraryMetadataIndex([
      item("KEEP0001", "Quantum decoder", {
        tags: ["qec", "reviewed"],
        collectionKeys: ["COLLQEC1"],
        date: "2024-03-01",
      }),
      item("OLD00001", "Quantum decoder", {
        tags: ["qec"],
        collectionKeys: ["COLLQEC1"],
        date: "2018",
      }),
      item("WRONGTAG", "Quantum decoder", {
        tags: ["many-body"],
        collectionKeys: ["COLLQEC1"],
        date: "2024",
      }),
    ], [{ key: "COLLQEC1", name: "QEC", path: "Research :: QEC" }]);

    const hits = searchLibraryMetadata(index, "quantum decoder", {
      tags: ["qec"],
      collectionKeys: ["COLLQEC1"],
      itemTypes: ["journalArticle"],
      yearFrom: 2020,
      yearTo: 2026,
    });
    expect(hits.map((hit) => hit.itemKey)).toEqual(["KEEP0001"]);
  });

  it("uses the stable item key to break equal-score ties", () => {
    const index = buildLibraryMetadataIndex([
      item("ZZZZZZZZ", "Quantum sensing"),
      item("AAAAAAAA", "Quantum sensing"),
    ], []);

    expect(searchLibraryMetadata(index, "quantum sensing").map((hit) => hit.itemKey)).toEqual([
      "AAAAAAAA",
      "ZZZZZZZZ",
    ]);
  });
});
