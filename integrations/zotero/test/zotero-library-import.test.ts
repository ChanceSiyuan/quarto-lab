import { describe, expect, it, vi } from "vitest";

import { CitationCandidateRegistry, type CitationQuery } from "../src/library-citations";
import type {
  BoundLibraryImportPlan,
  LibraryApplyReceipt,
  ValidatedLibraryImportPlan,
} from "../src/reviewed-library-import";
import {
  LibraryApplyFailure,
  LOOKUP_CITATIONS_TOOL,
  PROPOSE_LIBRARY_IMPORT_TOOL,
  ReviewedLibraryImportService,
} from "../src/reviewed-library-import";
import {
  createZoteroCitationResolver,
  createZoteroLibraryMutationHost,
} from "../src/zotero-library-import";

interface FakeItem {
  id: number;
  key: string;
  libraryID: number;
  itemType: string;
  version: number;
  deleted: boolean;
  fields: Record<string, string>;
  creators: Array<Record<string, unknown>>;
  collectionIDs: number[];
  getField: ReturnType<typeof vi.fn>;
  getCreators: ReturnType<typeof vi.fn>;
  getCollections: ReturnType<typeof vi.fn>;
  setField: ReturnType<typeof vi.fn>;
  setCreators: ReturnType<typeof vi.fn>;
  saveTx: ReturnType<typeof vi.fn>;
  eraseTx: ReturnType<typeof vi.fn>;
  isTopLevelItem: ReturnType<typeof vi.fn>;
  isAttachment: ReturnType<typeof vi.fn>;
  isRegularItem: ReturnType<typeof vi.fn>;
}

interface FakeCollection {
  id: number;
  key: string;
  libraryID: number;
  name: string;
  parentID: number | null;
  parentKey: string | null;
  version: number;
  deleted: boolean;
  itemIDs: number[];
  hasItem: ReturnType<typeof vi.fn>;
  addItem: ReturnType<typeof vi.fn>;
  removeItem: ReturnType<typeof vi.fn>;
  saveTx: ReturnType<typeof vi.fn>;
  eraseTx: ReturnType<typeof vi.fn>;
  requireTransaction: () => void;
}

function fakeItem(overrides: Partial<FakeItem> & {
  id: number;
  key: string;
  fields?: Record<string, string>;
}): FakeItem {
  const item = {
    id: overrides.id,
    key: overrides.key,
    libraryID: overrides.libraryID ?? 1,
    itemType: overrides.itemType ?? "journalArticle",
    version: overrides.version ?? 1,
    deleted: overrides.deleted ?? false,
    fields: {
      title: "Existing paper",
      date: "2024",
      DOI: "",
      url: "",
      publicationTitle: "",
      archive: "",
      archiveLocation: "",
      ...overrides.fields,
    },
    creators: overrides.creators ?? [{ creatorType: "author", firstName: "Ada", lastName: "Lovelace" }],
    collectionIDs: overrides.collectionIDs ?? [],
  } as unknown as FakeItem;
  item.getField = vi.fn((field: string) => item.fields[field] ?? "");
  item.getCreators = vi.fn(() => item.creators.map((creator) => ({ ...creator })));
  item.getCollections = vi.fn(() => [...item.collectionIDs]);
  item.setField = vi.fn((field: string, value: string) => { item.fields[field] = value; });
  item.setCreators = vi.fn((creators: Array<Record<string, unknown>>) => {
    item.creators = creators.map((creator) => ({ ...creator }));
  });
  item.saveTx = overrides.saveTx ?? vi.fn(async () => item.id);
  item.eraseTx = overrides.eraseTx ?? vi.fn(async () => undefined);
  item.isTopLevelItem = vi.fn(() => true);
  item.isAttachment = vi.fn(() => false);
  item.isRegularItem = overrides.isRegularItem ?? vi.fn(() => (
    item.itemType !== "attachment" && item.itemType !== "note"
  ));
  return item;
}

function fakeCollection(overrides: Partial<FakeCollection> & {
  id: number;
  key: string;
  name: string;
}): FakeCollection {
  const collection = {
    id: overrides.id,
    key: overrides.key,
    libraryID: overrides.libraryID ?? 1,
    name: overrides.name,
    parentID: overrides.parentID ?? null,
    parentKey: overrides.parentKey ?? null,
    version: overrides.version ?? 1,
    deleted: overrides.deleted ?? false,
    itemIDs: overrides.itemIDs ?? [],
    requireTransaction: overrides.requireTransaction ?? (() => undefined),
  } as FakeCollection;
  collection.hasItem = vi.fn((id: number) => collection.itemIDs.includes(id));
  collection.addItem = overrides.addItem ?? vi.fn(async (id: number) => {
    collection.requireTransaction();
    if (!collection.itemIDs.includes(id)) collection.itemIDs.push(id);
  });
  collection.removeItem = overrides.removeItem ?? vi.fn(async (id: number) => {
    collection.requireTransaction();
    collection.itemIDs = collection.itemIDs.filter((entry) => entry !== id);
  });
  collection.saveTx = overrides.saveTx ?? vi.fn(async () => collection.id);
  collection.eraseTx = overrides.eraseTx ?? vi.fn(async () => undefined);
  return collection;
}

function zoteroHarness(options: {
  items?: FakeItem[];
  collections?: FakeCollection[];
  translatedItems?: Array<Record<string, unknown>>;
  editable?: boolean;
} = {}) {
  const items = [...(options.items ?? [])];
  const collections = [...(options.collections ?? [])];
  const translatedItems = options.translatedItems ?? [];
  let nextItemID = 100;
  let nextCollectionID = 200;
  let transactionDepth = 0;
  const requireTransaction = vi.fn(() => {
    if (transactionDepth === 0) throw new Error("Zotero transaction required");
  });
  let database!: object;
  const executeTransaction = vi.fn(async function(
    this: unknown,
    callback: () => Promise<void>,
  ): Promise<void> {
    if (this !== database) throw new Error("Zotero DB receiver was lost");
    transactionDepth += 1;
    try {
      await callback();
    }
    finally {
      transactionDepth -= 1;
    }
  });
  database = { executeTransaction, requireTransaction };
  for (const collection of collections) collection.requireTransaction = requireTransaction;
  for (const item of items) {
    item.eraseTx.mockImplementation(async () => {
      const index = items.indexOf(item);
      if (index >= 0) items.splice(index, 1);
    });
  }
  for (const collection of collections) {
    collection.eraseTx.mockImplementation(async () => {
      const index = collections.indexOf(collection);
      if (index >= 0) collections.splice(index, 1);
    });
  }

  const translate = {
    setIdentifier: vi.fn(),
    getTranslators: vi.fn(async () => [{ translatorID: "identifier-translator" }]),
    setTranslator: vi.fn(),
    translate: vi.fn(async () => translatedItems.map((item) => structuredClone(item))),
  };
  const Search = vi.fn(function(this: unknown) { return translate; });
  const Item = vi.fn(function(this: unknown, itemType: string) {
    const item = fakeItem({ id: nextItemID++, key: "", itemType, fields: { title: "" }, version: 0 });
    item.saveTx = vi.fn(async () => {
      if (!item.key) {
        item.key = `NEWITEM${item.id}`;
        item.version = 1;
        items.push(item);
      }
      return item.id;
    });
    item.eraseTx.mockImplementation(async () => {
      const index = items.indexOf(item);
      if (index >= 0) items.splice(index, 1);
    });
    return item;
  });
  const Collection = vi.fn(function(this: unknown) {
    const collection = fakeCollection({ id: nextCollectionID++, key: "", name: "", version: 0 });
    collection.requireTransaction = requireTransaction;
    collection.saveTx = vi.fn(async () => {
      if (!collection.key) {
        collection.key = `NEWCOLL${collection.id}`;
        collection.version = 1;
        collections.push(collection);
      }
      return collection.id;
    });
    collection.eraseTx.mockImplementation(async () => {
      const index = collections.indexOf(collection);
      if (index >= 0) collections.splice(index, 1);
    });
    return collection;
  });
  const getAll = vi.fn(async () => [...items]);
  const loadDataTypes = vi.fn(async () => undefined);
  const getByLibrary = vi.fn(async () => [...collections]);
  const libraryGet = vi.fn((libraryID: number | string): {
    libraryID: number | string;
    editable: boolean | undefined;
  } => ({
    libraryID,
    editable: options.editable ?? true,
  }));
  const zotero = {
    DB: database as { executeTransaction: typeof executeTransaction; requireTransaction: typeof requireTransaction },
    Libraries: {
      userLibraryID: 1,
      get: libraryGet,
    },
    Items: {
      getAll,
      loadDataTypes,
      get: vi.fn((id: number | string) => items.find((item) => item.id === id) ?? null),
      getByLibraryAndKey: vi.fn((libraryID: number | string, key: string) =>
        items.find((item) => item.libraryID === libraryID && item.key === key) ?? null),
    },
    Collections: {
      getByLibrary,
      get: vi.fn((id: number | string) =>
        collections.find((collection) => collection.id === id) ?? null),
      getByLibraryAndKey: vi.fn((libraryID: number | string, key: string) =>
        collections.find((collection) => collection.libraryID === libraryID && collection.key === key) ?? null),
    },
    Translate: { Search },
    Item,
    Collection,
  };
  let choiceSequence = 0;
  const resolver = createZoteroCitationResolver(zotero, {
    createChoiceId: () => `choice-${++choiceSequence}`,
  });
  const invalidator = { invalidateZotkitLibrarySnapshot: vi.fn() };
  const host = createZoteroLibraryMutationHost(zotero, invalidator);
  return {
    zotero,
    resolver,
    host,
    invalidator,
    translate,
    items,
    collections,
    Item,
    Collection,
    getAll,
    loadDataTypes,
    getByLibrary,
    executeTransaction,
    requireTransaction,
  };
}

const translatedPaper = (overrides: Record<string, unknown> = {}) => ({
  itemType: "journalArticle",
  title: "A resolved paper",
  creators: [{ creatorType: "author", firstName: "Grace", lastName: "Hopper" }],
  date: "2025",
  DOI: "10.1000/new",
  url: "https://doi.org/10.1000/new",
  publicationTitle: "Journal of Tests",
  archive: "",
  archiveLocation: "",
  ...overrides,
});

const ZOTERO_TRANSLATE_NO_RESULTS = "No items returned from any translator";

function boundPlan(rows: BoundLibraryImportPlan["rows"], overrides: {
  parentCollectionKey?: string | null;
  collectionName?: string;
} = {}): BoundLibraryImportPlan {
  return {
    scope: { threadId: "library-thread", libraryID: 1 },
    target: {
      parentCollectionKey: overrides.parentCollectionKey ?? null,
      collectionName: overrides.collectionName ?? "Reviewed imports",
    },
    rows,
  };
}

async function validatedPlan(
  host: ReturnType<typeof createZoteroLibraryMutationHost>,
  plan: BoundLibraryImportPlan,
): Promise<ValidatedLibraryImportPlan> {
  return { ...plan, preflight: await host.preflight(plan) };
}

describe("createZoteroCitationResolver", () => {
  it("resolves exact local DOI before using the identifier translator", async () => {
    const existing = fakeItem({
      id: 10,
      key: "EXISTING1",
      version: 4,
      fields: { DOI: "10.1000/abc" },
    });
    const { resolver, zotero } = zoteroHarness({ items: [existing] });

    const result = await resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/ABC" }],
    );

    expect(result[0]).toMatchObject({
      clientRef: "r1",
      status: "reuse",
      candidates: [{ localItemKey: "EXISTING1", localItemVersion: 4 }],
    });
    expect(zotero.Translate.Search).not.toHaveBeenCalled();
  });

  it("reports multiple exact local identifiers as ambiguous", async () => {
    const first = fakeItem({ id: 10, key: "DUPLICATE1", fields: { archive: "arXiv", archiveLocation: "2306.13123" } });
    const second = fakeItem({ id: 11, key: "DUPLICATE2", fields: { url: "https://arxiv.org/abs/2306.13123v2" } });
    const { resolver, translate } = zoteroHarness({ items: [first, second] });

    const [result] = await resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", arxiv: "arXiv:2306.13123v3" }],
    );

    expect(result).toMatchObject({ status: "ambiguous" });
    expect(result?.candidates.map((candidate) => candidate.localItemKey)).toEqual([
      "DUPLICATE1",
      "DUPLICATE2",
    ]);
    expect(translate.translate).not.toHaveBeenCalled();
  });

  it("uses identifier translation as metadata only and never imports during lookup", async () => {
    const { resolver, translate, Item, Collection } = zoteroHarness({
      translatedItems: [translatedPaper()],
    });

    const result = await resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );

    expect(translate.setIdentifier).toHaveBeenCalledWith({ DOI: "10.1000/new" });
    expect(translate.translate).toHaveBeenCalledWith({
      libraryID: false,
      saveAttachments: false,
    });
    expect(result[0]).toMatchObject({
      status: "create",
      candidates: [{ metadata: { title: "A resolved paper" }, localItemKey: null }],
    });
    expect(Item).not.toHaveBeenCalled();
    expect(Collection).not.toHaveBeenCalled();
  });

  it("does not invent create metadata for title-only model input", async () => {
    const { resolver, translate } = zoteroHarness();

    const [result] = await resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", title: "A title that is not local", year: 2024 }],
    );

    expect(result).toEqual({
      clientRef: "r1",
      status: "unresolved",
      candidates: [],
      reason: expect.any(String),
    });
    expect(translate.translate).not.toHaveBeenCalled();
  });

  it("reuses only exact normalized local title, year, and creator matches", async () => {
    const exact = fakeItem({
      id: 10,
      key: "TITLEMATCH",
      version: 8,
      fields: { title: "  Quantum\u00a0Control  ", date: "2024-02-01" },
      creators: [{ creatorType: "author", firstName: "Ada", lastName: "Lovelace" }],
    });
    const wrongYear = fakeItem({
      id: 11,
      key: "WRONGYEAR",
      fields: { title: "Quantum Control", date: "2023" },
      creators: [{ creatorType: "author", firstName: "Ada", lastName: "Lovelace" }],
    });
    const { resolver, translate } = zoteroHarness({ items: [exact, wrongYear] });

    const [result] = await resolver.resolve({ libraryID: 1 }, [{
      clientRef: "r1",
      title: "quantum control",
      year: 2024,
      creators: ["Ada Lovelace"],
    }]);

    expect(result).toMatchObject({
      status: "reuse",
      candidates: [{ localItemKey: "TITLEMATCH", localItemVersion: 8 }],
    });
    expect(translate.translate).not.toHaveBeenCalled();
  });

  it("keeps multiple exact translated identifier records ambiguous", async () => {
    const { resolver, translate } = zoteroHarness({
      translatedItems: [
        translatedPaper({ title: "Candidate A" }),
        translatedPaper({ title: "Candidate B" }),
      ],
    });

    const [result] = await resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );

    expect(result).toMatchObject({ status: "ambiguous" });
    expect(result?.candidates.map((candidate) => candidate.metadata?.title)).toEqual([
      "Candidate A",
      "Candidate B",
    ]);
    expect(translate.setTranslator).toHaveBeenCalledWith([{ translatorID: "identifier-translator" }]);
  });

  it("treats Zotero's exact no-results rejection as an empty translation and continues title fallback", async () => {
    const exactTitle = fakeItem({
      id: 10,
      key: "TITLE-FALLBACK",
      fields: { title: "Fallback paper", date: "2024" },
    });
    const { resolver, translate } = zoteroHarness({ items: [exactTitle] });
    translate.translate.mockRejectedValueOnce(new Error(ZOTERO_TRANSLATE_NO_RESULTS));

    const [result] = await resolver.resolve({ libraryID: 1 }, [{
      clientRef: "r1",
      doi: "10.1000/not-found",
      title: "fallback paper",
      year: 2024,
    }]);

    expect(result).toMatchObject({
      status: "reuse",
      candidates: [{ localItemKey: "TITLE-FALLBACK" }],
    });
  });

  it("returns unresolved when Zotero's exact no-results rejection has no local fallback", async () => {
    const { resolver, translate } = zoteroHarness();
    translate.translate.mockRejectedValueOnce(ZOTERO_TRANSLATE_NO_RESULTS);

    await expect(resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/not-found" }],
    )).resolves.toEqual([{
      clientRef: "r1",
      status: "unresolved",
      candidates: [],
      reason: expect.any(String),
    }]);
  });

  it("does not swallow operational identifier-translator failures", async () => {
    const { resolver, translate } = zoteroHarness();
    translate.translate.mockRejectedValueOnce(new Error("translator database unavailable"));

    await expect(resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/not-found", title: "Could be local" }],
    )).rejects.toThrow("translator database unavailable");
  });

  it("bounds and sanitizes operational identifier-translator failures", async () => {
    const { resolver, translate } = zoteroHarness();
    translate.translate.mockRejectedValueOnce(new Error(`translator\u0000${"x".repeat(400)}`));

    const failure = await resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/not-found" }],
    ).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(Error);
    expect((failure as Error).message).not.toMatch(/[\p{Cc}\p{Cf}\u2028\u2029]/u);
    expect([...(failure as Error).message]).toHaveLength(240);
  });

  it("ignores top-level attachments, notes, and unsupported item types even when identifiers match", async () => {
    const attachment = fakeItem({
      id: 10,
      key: "ATTACHMENT",
      itemType: "attachment",
      fields: { DOI: "10.1000/attachment", title: "Attachment title" },
    });
    const note = fakeItem({
      id: 11,
      key: "NOTE",
      itemType: "note",
      fields: { DOI: "10.1000/note", title: "Note title" },
    });
    const unsupported = fakeItem({
      id: 12,
      key: "UNSUPPORTED",
      itemType: "webpage",
      fields: { DOI: "10.1000/unsupported", title: "Unsupported title" },
    });
    const { resolver, translate } = zoteroHarness({ items: [attachment, note, unsupported] });
    translate.translate.mockRejectedValue(new Error(ZOTERO_TRANSLATE_NO_RESULTS));

    const results = await resolver.resolve({ libraryID: 1 }, [
      { clientRef: "attachment", doi: "10.1000/attachment" },
      { clientRef: "note", doi: "10.1000/note" },
      { clientRef: "unsupported", doi: "10.1000/unsupported" },
    ]);

    expect(results.map((result) => result.status)).toEqual([
      "unresolved",
      "unresolved",
      "unresolved",
    ]);
    expect(results.flatMap((result) => result.candidates)).toEqual([]);
  });

  it("trusts archiveLocation as arXiv only when archive is exactly normalized arXiv", async () => {
    const otherArchive = fakeItem({
      id: 10,
      key: "OTHER-ARCHIVE",
      fields: { archive: "PubMed", archiveLocation: "2306.13123" },
    });
    const arxivArchive = fakeItem({
      id: 11,
      key: "ARXIV-ARCHIVE",
      fields: { archive: "  ARXIV  ", archiveLocation: "2306.13124v2" },
    });
    const { resolver, translate } = zoteroHarness({ items: [otherArchive, arxivArchive] });
    translate.translate.mockRejectedValue(new Error(ZOTERO_TRANSLATE_NO_RESULTS));

    const results = await resolver.resolve({ libraryID: 1 }, [
      { clientRef: "other", arxiv: "2306.13123" },
      { clientRef: "arxiv", arxiv: "2306.13124" },
    ]);

    expect(results[0]).toMatchObject({ status: "unresolved", candidates: [] });
    expect(results[1]).toMatchObject({
      status: "reuse",
      candidates: [{ localItemKey: "ARXIV-ARCHIVE" }],
    });
  });

  it("rejects translated archiveLocation as arXiv metadata for a different archive", async () => {
    const { resolver } = zoteroHarness({
      translatedItems: [translatedPaper({
        DOI: "",
        archive: "PubMed",
        archiveLocation: "2306.13123",
      })],
    });

    await expect(resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", arxiv: "2306.13123" }],
    )).resolves.toEqual([{
      clientRef: "r1",
      status: "unresolved",
      candidates: [],
      reason: expect.any(String),
    }]);
  });
});

describe("createZoteroLibraryMutationHost", () => {
  it("uses complete native enumeration and fails closed on unknown editability", async () => {
    const { resolver, host, zotero, getAll, loadDataTypes } = zoteroHarness({
      translatedItems: [translatedPaper()],
    });
    zotero.Libraries.get.mockReturnValueOnce({ libraryID: 1, editable: undefined });
    const [resolution] = await resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);

    const preflight = await host.preflight(plan);

    expect(preflight.editable).toBe(false);
    expect(getAll).toHaveBeenCalledWith(1, true, false, false);
    expect(loadDataTypes).toHaveBeenCalledWith(
      expect.any(Array),
      ["creators", "itemData", "collections"],
    );
  });

  it("creates only reviewed metadata and records each successful effect immediately", async () => {
    const existing = fakeItem({
      id: 10,
      key: "EXISTING1",
      version: 4,
      fields: { DOI: "10.1000/existing" },
    });
    const { resolver, host, collections, Item, executeTransaction } = zoteroHarness({
      items: [existing],
      translatedItems: [translatedPaper()],
    });
    const resolutions = await resolver.resolve(
      { libraryID: 1 },
      [
        { clientRef: "create", doi: "10.1000/new" },
        { clientRef: "reuse", doi: "10.1000/existing" },
      ],
    );
    const plan = boundPlan(resolutions.map((resolution) => ({
      rowId: resolution.clientRef,
      choiceId: resolution.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: `digest-${resolution.clientRef}`,
    })));

    const receipt = await host.apply(await validatedPlan(host, plan));

    const createdItem = Item.mock.results[0]!.value as FakeItem;
    const createdCollection = collections[0]!;
    expect(receipt).toEqual({
      libraryID: 1,
      createdCollectionKey: createdCollection.key,
      createdItemKeys: [createdItem.key],
      addedMemberships: [
        { itemKey: createdItem.key, collectionKey: createdCollection.key },
        { itemKey: "EXISTING1", collectionKey: createdCollection.key },
      ],
    });
    expect(createdItem.setField.mock.calls).toEqual([
      ["title", "A resolved paper"],
      ["date", "2025"],
      ["DOI", "10.1000/new"],
      ["url", "https://doi.org/10.1000/new"],
      ["publicationTitle", "Journal of Tests"],
    ]);
    expect(createdItem.setCreators).toHaveBeenCalledWith([
      { creatorType: "author", firstName: "Grace", lastName: "Hopper" },
    ]);
    expect(createdCollection.addItem).toHaveBeenCalledWith(createdItem.id);
    expect(createdCollection.addItem).toHaveBeenCalledWith(existing.id);
    expect(existing.setField).not.toHaveBeenCalled();
    expect(existing.setCreators).not.toHaveBeenCalled();
    expect(executeTransaction).toHaveBeenCalledTimes(2);
  });

  it("records no membership when its Zotero transaction rejects before applying", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    harness.executeTransaction.mockRejectedValueOnce(new Error("transaction rejected"));

    const failure = await harness.host.apply(validated).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(LibraryApplyFailure);
    expect((failure as LibraryApplyFailure).receipt).toEqual({
      libraryID: 1,
      createdCollectionKey: expect.stringMatching(/^NEWCOLL/u),
      createdItemKeys: [expect.stringMatching(/^NEWITEM/u)],
      addedMemberships: [],
    });
    expect(harness.collections[0]!.itemIDs).toEqual([]);
  });

  it("records an applied membership in the partial receipt when the transaction callback throws afterward", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    harness.Collection.mockImplementationOnce(function(this: unknown) {
      const collection = fakeCollection({ id: 999, key: "", name: "" });
      collection.requireTransaction = harness.requireTransaction;
      collection.saveTx.mockImplementationOnce(async () => {
        collection.key = "PARTIAL-COLLECTION";
        harness.collections.push(collection);
        return collection.id;
      });
      collection.addItem.mockImplementationOnce(async (itemID: number) => {
        collection.requireTransaction();
        collection.itemIDs.push(itemID);
        throw new Error("transaction callback failed after applying");
      });
      return collection;
    });

    const failure = await harness.host.apply(validated).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(LibraryApplyFailure);
    expect((failure as LibraryApplyFailure).receipt).toEqual({
      libraryID: 1,
      createdCollectionKey: "PARTIAL-COLLECTION",
      createdItemKeys: [expect.stringMatching(/^NEWITEM/u)],
      addedMemberships: [{
        itemKey: expect.stringMatching(/^NEWITEM/u),
        collectionKey: "PARTIAL-COLLECTION",
      }],
    });
    expect(harness.collections[0]!.itemIDs).toHaveLength(1);
  });

  it("cleans up the exact newly saved collection when Zotero returns a duplicate key", async () => {
    const existing = fakeCollection({ id: 20, key: "DUPLICATE-COLLECTION", name: "Existing" });
    const harness = zoteroHarness({ collections: [existing], translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    let created!: FakeCollection;
    harness.Collection.mockImplementationOnce(function(this: unknown) {
      created = fakeCollection({ id: 999, key: "", name: "" });
      created.requireTransaction = harness.requireTransaction;
      created.saveTx.mockImplementationOnce(async () => {
        created.key = "DUPLICATE-COLLECTION";
        harness.collections.push(created);
        return created.id;
      });
      created.eraseTx.mockImplementation(async () => {
        const index = harness.collections.indexOf(created);
        if (index >= 0) harness.collections.splice(index, 1);
      });
      return created;
    });

    const failure = await harness.host.apply(validated).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(LibraryApplyFailure);
    expect((failure as LibraryApplyFailure).receipt.createdCollectionKey).toBeNull();
    expect(created.eraseTx).toHaveBeenCalledOnce();
    expect(existing.eraseTx).not.toHaveBeenCalled();
    expect(harness.collections).toEqual([existing]);
  });

  it("cleans up the exact newly saved item on a wrong library or duplicate key", async () => {
    for (const scenario of ["wrong-library", "duplicate-key"] as const) {
      const existing = fakeItem({
        id: 10,
        key: "DUPLICATE-ITEM",
        fields: { DOI: "10.1000/existing" },
      });
      const harness = zoteroHarness({ items: [existing], translatedItems: [translatedPaper()] });
      const [resolution] = await harness.resolver.resolve(
        { libraryID: 1 },
        [{ clientRef: "r1", doi: "10.1000/new" }],
      );
      const plan = boundPlan([{
        rowId: "r1",
        choiceId: resolution!.candidates[0]!.choiceId,
        omit: false,
        resolverDigest: "resolver-digest-r1",
      }]);
      const validated = await validatedPlan(harness.host, plan);
      let created!: FakeItem;
      harness.Item.mockImplementationOnce(function(this: unknown, itemType: string) {
        created = fakeItem({ id: 999, key: "", itemType, fields: { title: "" } });
        created.saveTx.mockImplementationOnce(async () => {
          created.key = scenario === "duplicate-key" ? "DUPLICATE-ITEM" : "WRONG-LIBRARY";
          created.libraryID = scenario === "wrong-library" ? 2 : 1;
          harness.items.push(created);
          return created.id;
        });
        created.eraseTx.mockImplementation(async () => {
          const index = harness.items.indexOf(created);
          if (index >= 0) harness.items.splice(index, 1);
        });
        return created;
      });

      const failure = await harness.host.apply(validated).catch((error: unknown) => error);

      expect(failure).toBeInstanceOf(LibraryApplyFailure);
      expect((failure as LibraryApplyFailure).receipt.createdItemKeys).toEqual([]);
      expect(created.eraseTx).toHaveBeenCalledOnce();
      expect(existing.eraseTx).not.toHaveBeenCalled();
      expect(harness.items).toEqual([existing]);
    }
  });

  it("uses saved numeric identity to clean up when the created key getter becomes hostile", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    let created!: FakeItem;
    harness.Item.mockImplementationOnce(function(this: unknown, itemType: string) {
      created = fakeItem({ id: 999, key: "", itemType, fields: { title: "" } });
      let hostile = false;
      Object.defineProperty(created, "key", {
        configurable: true,
        get: () => {
          if (hostile) throw new Error("hostile key getter");
          return "";
        },
        set: () => undefined,
      });
      created.saveTx.mockImplementationOnce(async () => {
        harness.items.push(created);
        hostile = true;
        return created.id;
      });
      created.eraseTx.mockImplementation(async () => {
        const index = harness.items.indexOf(created);
        if (index >= 0) harness.items.splice(index, 1);
      });
      return created;
    });

    const failure = await harness.host.apply(validated).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(LibraryApplyFailure);
    expect((failure as LibraryApplyFailure).receipt.createdItemKeys).toEqual([]);
    expect(created.eraseTx).toHaveBeenCalledOnce();
    expect(harness.items.includes(created)).toBe(false);
  });

  it("uses saveTx's numeric identity when the created ID getter becomes hostile", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    let created!: FakeItem;
    harness.Item.mockImplementationOnce(function(this: unknown, itemType: string) {
      created = fakeItem({ id: 999, key: "", itemType, fields: { title: "" } });
      let hostile = false;
      Object.defineProperty(created, "id", {
        configurable: true,
        get: () => {
          if (hostile) throw new Error("hostile ID getter");
          return 999;
        },
      });
      created.saveTx.mockImplementationOnce(async () => {
        created.key = "CREATED-WITH-HOSTILE-ID";
        harness.items.push(created);
        hostile = true;
        return 999;
      });
      created.eraseTx.mockImplementation(async () => {
        const index = harness.items.indexOf(created);
        if (index >= 0) harness.items.splice(index, 1);
      });
      harness.zotero.Items.get.mockImplementation((id: number | string) => (
        id === 999 && harness.items.includes(created) ? created : null
      ));
      return created;
    });

    const receipt = await harness.host.apply(validated);

    expect(receipt.createdItemKeys).toEqual(["CREATED-WITH-HOSTILE-ID"]);
    expect(receipt.addedMemberships).toEqual([{
      itemKey: "CREATED-WITH-HOSTILE-ID",
      collectionKey: expect.stringMatching(/^NEWCOLL/u),
    }]);
    expect(created.eraseTx).not.toHaveBeenCalled();
    expect(harness.items.includes(created)).toBe(true);
  });

  it("requires manual inspection when no saved numeric identity can be recovered", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    let created!: FakeItem;
    harness.Item.mockImplementationOnce(function(this: unknown, itemType: string) {
      created = fakeItem({ id: 999, key: "", itemType, fields: { title: "" } });
      let hostile = false;
      Object.defineProperty(created, "id", {
        configurable: true,
        get: () => {
          if (hostile) throw new Error("hostile ID getter");
          return 999;
        },
      });
      created.saveTx.mockImplementationOnce(async () => {
        created.key = "UNRECOVERABLE-ID";
        harness.items.push(created);
        hostile = true;
        return undefined;
      });
      return created;
    });

    const failure = await harness.host.apply(validated).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(Error);
    expect((failure as Error).name).toBe("ManualInspectionRequiredError");
    expect((failure as Error).message).toMatch(/manual inspection.*native ID/i);
    expect(failure).not.toBeInstanceOf(LibraryApplyFailure);
    expect(harness.items.includes(created)).toBe(true);
  });

  it("rejects a create when complete Apply-time enumeration finds an exact duplicate", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    harness.items.push(fakeItem({ id: 12, key: "ARRIVED", fields: { DOI: "10.1000/new" } }));

    await expect(harness.host.apply(validated)).rejects.toThrow(/preflight|changed|duplicate/i);
    expect(harness.Collection).not.toHaveBeenCalled();
    expect(harness.Item).not.toHaveBeenCalled();
  });

  it("reuses the reviewed same-name sibling under the exact parent", async () => {
    const parent = fakeCollection({ id: 20, key: "PARENT", name: "Parent", version: 7 });
    const sibling = fakeCollection({
      id: 21,
      key: "SIBLING",
      name: "Reviewed imports",
      parentID: 20,
      parentKey: "PARENT",
      version: 3,
    });
    const existing = fakeItem({
      id: 10,
      key: "EXISTING1",
      version: 4,
      fields: { DOI: "10.1000/existing" },
    });
    const harness = zoteroHarness({ items: [existing], collections: [parent, sibling] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/existing" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }], { parentCollectionKey: "PARENT" });

    const preflight = await harness.host.preflight(plan);
    const receipt = await harness.host.apply({ ...plan, preflight });

    expect(preflight).toMatchObject({
      editable: true,
      parentVersion: 7,
      siblingCollectionKey: "SIBLING",
    });
    expect(receipt).toEqual({
      libraryID: 1,
      createdCollectionKey: null,
      createdItemKeys: [],
      addedMemberships: [{ itemKey: "EXISTING1", collectionKey: "SIBLING" }],
    });
    expect(harness.Collection).not.toHaveBeenCalled();
    expect(sibling.addItem).toHaveBeenCalledWith(existing.id);
  });

  it("fails closed when a parent is absent or same-name siblings are ambiguous", async () => {
    const missingParentHarness = zoteroHarness();
    await expect(missingParentHarness.host.preflight(boundPlan([], {
      parentCollectionKey: "MISSING",
    }))).resolves.toMatchObject({ editable: false, parentVersion: null });

    const first = fakeCollection({ id: 20, key: "SIBLING1", name: "Reviewed imports" });
    const second = fakeCollection({ id: 21, key: "SIBLING2", name: "Reviewed imports" });
    const duplicateSiblingHarness = zoteroHarness({ collections: [first, second] });
    await expect(duplicateSiblingHarness.host.preflight(boundPlan([])))
      .rejects.toThrow(/multiple exact sibling/i);
  });

  it("fails closed when complete native item enumeration throws or is incomplete", async () => {
    const throwing = zoteroHarness();
    throwing.getAll.mockRejectedValueOnce(new Error("database unavailable"));
    await expect(throwing.host.preflight(boundPlan([]))).rejects.toThrow("database unavailable");

    const incomplete = zoteroHarness();
    (incomplete.zotero.Items as { loadDataTypes?: unknown }).loadDataTypes = undefined;
    const host = createZoteroLibraryMutationHost(incomplete.zotero);
    await expect(host.preflight(boundPlan([]))).rejects.toThrow(/loaded fields is unavailable/i);
  });

  it("invokes every required loaded field and fails preflight before writes when one throws", async () => {
    const incomplete = fakeItem({ id: 10, key: "INCOMPLETE" });
    incomplete.getField.mockImplementation((field: string) => {
      if (field === "publicationTitle") throw new Error("publicationTitle was not loaded");
      return incomplete.fields[field] ?? "";
    });
    const harness = zoteroHarness({ items: [incomplete] });

    await expect(harness.host.preflight(boundPlan([])))
      .rejects.toThrow("publicationTitle was not loaded");
    expect(incomplete.getField).toHaveBeenCalledWith("publicationTitle");
    expect(harness.Collection).not.toHaveBeenCalled();
    expect(harness.Item).not.toHaveBeenCalled();
  });

  it("fails closed when loaded itemData returns undefined instead of a field value", async () => {
    const sparse = fakeItem({ id: 10, key: "SPARSE" });
    sparse.getField.mockReturnValue(undefined);
    const harness = zoteroHarness({ items: [sparse] });

    await expect(harness.host.preflight(boundPlan([])))
      .rejects.toThrow(/loaded Zotero item field.*unavailable/i);
    expect(harness.Collection).not.toHaveBeenCalled();
    expect(harness.Item).not.toHaveBeenCalled();
  });

  it("fails closed when regular-item classification is missing or throws", async () => {
    const missing = fakeItem({ id: 10, key: "MISSING-REGULAR" });
    missing.isRegularItem = undefined as unknown as FakeItem["isRegularItem"];
    const missingHarness = zoteroHarness({ items: [missing] });
    await expect(missingHarness.host.preflight(boundPlan([])))
      .rejects.toThrow(/regular Zotero item classifier/i);

    const throwing = fakeItem({
      id: 11,
      key: "THROWING-REGULAR",
      isRegularItem: vi.fn(() => { throw new Error("classification unavailable"); }),
    });
    const throwingHarness = zoteroHarness({ items: [throwing] });
    await expect(throwingHarness.host.preflight(boundPlan([])))
      .rejects.toThrow("classification unavailable");
    expect(throwingHarness.Collection).not.toHaveBeenCalled();
    expect(throwingHarness.Item).not.toHaveBeenCalled();
  });

  it("rejects a reviewed reuse item that becomes non-regular before Apply", async () => {
    const existing = fakeItem({
      id: 10,
      key: "BECOMES-ATTACHMENT",
      fields: { DOI: "10.1000/existing" },
    });
    const harness = zoteroHarness({ items: [existing] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/existing" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    existing.itemType = "attachment";
    existing.isRegularItem.mockReturnValue(false);

    await expect(harness.host.apply(validated)).rejects.toThrow(/preflight changed|stale/i);
    expect(harness.Collection).not.toHaveBeenCalled();
    expect(harness.Item).not.toHaveBeenCalled();
  });

  it("throws a same-module LibraryApplyFailure with the exact partial receipt", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    harness.Item.mockImplementationOnce(function(this: unknown, itemType: string) {
      const failed = fakeItem({ id: 999, key: "", itemType, fields: { title: "" } });
      failed.saveTx.mockRejectedValueOnce(new Error("item save failed"));
      return failed;
    });

    const failure = await harness.host.apply(validated).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(LibraryApplyFailure);
    expect((failure as LibraryApplyFailure).receipt).toEqual({
      libraryID: 1,
      createdCollectionKey: harness.collections[0]!.key,
      createdItemKeys: [],
      addedMemberships: [],
    });
  });

  it("brands collection-save failure with an empty exact receipt", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    harness.Collection.mockImplementationOnce(function(this: unknown) {
      const failed = fakeCollection({ id: 999, key: "", name: "" });
      failed.saveTx.mockRejectedValueOnce(new Error("collection save failed"));
      return failed;
    });

    const failure = await harness.host.apply(validated).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(LibraryApplyFailure);
    expect((failure as LibraryApplyFailure).receipt).toEqual({
      libraryID: 1,
      createdCollectionKey: null,
      createdItemKeys: [],
      addedMemberships: [],
    });
  });

  it("brands created-item membership failure after recording collection and item", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    const [resolution] = await harness.resolver.resolve(
      { libraryID: 1 },
      [{ clientRef: "r1", doi: "10.1000/new" }],
    );
    const plan = boundPlan([{
      rowId: "r1",
      choiceId: resolution!.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: "resolver-digest-r1",
    }]);
    const validated = await validatedPlan(harness.host, plan);
    harness.Collection.mockImplementationOnce(function(this: unknown) {
      const failed = fakeCollection({ id: 999, key: "", name: "" });
      failed.saveTx.mockImplementationOnce(async () => {
        failed.key = "CREATED-COLLECTION";
        harness.collections.push(failed);
      });
      failed.addItem.mockRejectedValueOnce(new Error("membership save failed"));
      return failed;
    });

    const failure = await harness.host.apply(validated).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(LibraryApplyFailure);
    expect((failure as LibraryApplyFailure).receipt).toEqual({
      libraryID: 1,
      createdCollectionKey: "CREATED-COLLECTION",
      createdItemKeys: [expect.stringMatching(/^NEWITEM/u)],
      addedMemberships: [],
    });
  });

  it("deduplicates repeated new membership effects", async () => {
    const existing = fakeItem({
      id: 10,
      key: "EXISTING1",
      version: 4,
      fields: { DOI: "10.1000/existing" },
    });
    const harness = zoteroHarness({ items: [existing] });
    const resolutions = await harness.resolver.resolve(
      { libraryID: 1 },
      [
        { clientRef: "r1", doi: "10.1000/existing" },
        { clientRef: "r2", doi: "10.1000/existing" },
      ],
    );
    const plan = boundPlan(resolutions.map((resolution) => ({
      rowId: resolution.clientRef,
      choiceId: resolution.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: `digest-${resolution.clientRef}`,
    })));

    const receipt = await harness.host.apply(await validatedPlan(harness.host, plan));

    expect(receipt.addedMemberships).toEqual([
      { itemKey: "EXISTING1", collectionKey: receipt.createdCollectionKey },
    ]);
    expect(harness.collections[0]!.addItem).toHaveBeenCalledOnce();
  });

  it("compensates only objects and pre-existing memberships created by its receipt", async () => {
    const existing = fakeItem({
      id: 10,
      key: "EXISTING1",
      version: 4,
      fields: { DOI: "10.1000/existing" },
    });
    const harness = zoteroHarness({
      items: [existing],
      translatedItems: [translatedPaper()],
    });
    const resolutions = await harness.resolver.resolve(
      { libraryID: 1 },
      [
        { clientRef: "create", doi: "10.1000/new" },
        { clientRef: "reuse", doi: "10.1000/existing" },
      ],
    );
    const plan = boundPlan(resolutions.map((resolution) => ({
      rowId: resolution.clientRef,
      choiceId: resolution.candidates[0]!.choiceId,
      omit: false,
      resolverDigest: `digest-${resolution.clientRef}`,
    })));
    const receipt = await harness.host.apply(await validatedPlan(harness.host, plan));
    const createdItem = harness.Item.mock.results[0]!.value as FakeItem;
    const collection = harness.collections[0]!;

    await expect(harness.host.compensate(receipt)).resolves.toEqual({
      complete: true,
      survivors: [],
    });
    expect(existing.eraseTx).not.toHaveBeenCalled();
    expect(collection.removeItem).toHaveBeenCalledWith(existing.id);
    expect(collection.removeItem).not.toHaveBeenCalledWith(createdItem.id);
    expect(createdItem.eraseTx).toHaveBeenCalledOnce();
    expect(collection.eraseTx).toHaveBeenCalledOnce();
    expect(collection.removeItem.mock.invocationCallOrder[0]).toBeLessThan(
      createdItem.eraseTx.mock.invocationCallOrder[0]!,
    );
    expect(createdItem.eraseTx.mock.invocationCallOrder[0]).toBeLessThan(
      collection.eraseTx.mock.invocationCallOrder[0]!,
    );
  });

  it("continues compensation after failures and reports only exact survivors", async () => {
    const existing = fakeItem({ id: 10, key: "EXISTING1", collectionIDs: [20] });
    const created = fakeItem({ id: 11, key: "CREATED1" });
    const collection = fakeCollection({ id: 20, key: "COLLECTION1", name: "Reviewed imports", itemIDs: [10, 11] });
    collection.removeItem.mockRejectedValueOnce(new Error("membership stayed"));
    created.eraseTx.mockRejectedValueOnce(new Error("item stayed"));
    const { host } = zoteroHarness({ items: [existing, created], collections: [collection] });
    const receipt: LibraryApplyReceipt = {
      libraryID: 1,
      createdCollectionKey: "COLLECTION1",
      createdItemKeys: ["CREATED1"],
      addedMemberships: [
        { itemKey: "CREATED1", collectionKey: "COLLECTION1" },
        { itemKey: "EXISTING1", collectionKey: "COLLECTION1" },
      ],
    };

    const result = await host.compensate(receipt);

    expect(result).toEqual({
      complete: false,
      survivors: [
        { kind: "created-item", itemKey: "CREATED1", error: "item stayed" },
      ],
    });
    expect(collection.eraseTx).toHaveBeenCalledOnce();
  });

  it("reconciles membership state when remove applies and then throws", async () => {
    const existing = fakeItem({ id: 10, key: "EXISTING1" });
    const collection = fakeCollection({
      id: 20,
      key: "COLLECTION1",
      name: "Reviewed imports",
      itemIDs: [10],
    });
    const harness = zoteroHarness({ items: [existing], collections: [collection] });
    collection.removeItem.mockImplementationOnce(async (itemID: number) => {
      collection.requireTransaction();
      collection.itemIDs = collection.itemIDs.filter((id) => id !== itemID);
      throw new Error("remove reported failure after applying");
    });

    await expect(harness.host.compensate({
      libraryID: 1,
      createdCollectionKey: null,
      createdItemKeys: [],
      addedMemberships: [{ itemKey: "EXISTING1", collectionKey: "COLLECTION1" }],
    })).resolves.toEqual({ complete: true, survivors: [] });
    expect(collection.itemIDs).toEqual([]);
    expect(harness.executeTransaction).toHaveBeenCalledOnce();
  });

  it("reports membership as a survivor when remove returns without changing state", async () => {
    const existing = fakeItem({ id: 10, key: "EXISTING1" });
    const collection = fakeCollection({
      id: 20,
      key: "COLLECTION1",
      name: "Reviewed imports",
      itemIDs: [10],
    });
    const harness = zoteroHarness({ items: [existing], collections: [collection] });
    collection.removeItem.mockImplementationOnce(async () => {
      collection.requireTransaction();
      return false;
    });

    const result = await harness.host.compensate({
      libraryID: 1,
      createdCollectionKey: null,
      createdItemKeys: [],
      addedMemberships: [{ itemKey: "EXISTING1", collectionKey: "COLLECTION1" }],
    });

    expect(result).toEqual({
      complete: false,
      survivors: [{
        kind: "membership",
        itemKey: "EXISTING1",
        collectionKey: "COLLECTION1",
        error: expect.stringMatching(/still exists|remains/i),
      }],
    });
    expect(collection.itemIDs).toEqual([10]);
  });

  it("reports membership as unverifiable when Zotero returns a non-boolean membership state", async () => {
    const existing = fakeItem({ id: 10, key: "EXISTING1" });
    const collection = fakeCollection({
      id: 20,
      key: "COLLECTION1",
      name: "Reviewed imports",
      itemIDs: [10],
    });
    const harness = zoteroHarness({ items: [existing], collections: [collection] });
    collection.removeItem.mockImplementationOnce(async () => {
      collection.requireTransaction();
      return false;
    });
    collection.hasItem.mockReturnValue(undefined);

    const result = await harness.host.compensate({
      libraryID: 1,
      createdCollectionKey: null,
      createdItemKeys: [],
      addedMemberships: [{ itemKey: "EXISTING1", collectionKey: "COLLECTION1" }],
    });

    expect(result).toEqual({
      complete: false,
      survivors: [{
        kind: "membership",
        itemKey: "EXISTING1",
        collectionKey: "COLLECTION1",
        error: expect.stringMatching(/membership.*unavailable|boolean/i),
      }],
    });
  });

  it("does not treat deleted reused objects as proof that membership was removed", async () => {
    const existing = fakeItem({ id: 10, key: "EXISTING1", deleted: true });
    const collection = fakeCollection({
      id: 20,
      key: "COLLECTION1",
      name: "Reviewed imports",
      itemIDs: [10],
      deleted: true,
    });
    const harness = zoteroHarness({ items: [existing], collections: [collection] });
    collection.removeItem.mockImplementationOnce(async () => {
      collection.requireTransaction();
      return false;
    });

    const result = await harness.host.compensate({
      libraryID: 1,
      createdCollectionKey: null,
      createdItemKeys: [],
      addedMemberships: [{ itemKey: "EXISTING1", collectionKey: "COLLECTION1" }],
    });

    expect(result).toEqual({
      complete: false,
      survivors: [{
        kind: "membership",
        itemKey: "EXISTING1",
        collectionKey: "COLLECTION1",
        error: expect.stringMatching(/still exists|remains/i),
      }],
    });
  });

  it("omits a created-item survivor when erase applies and then throws", async () => {
    const created = fakeItem({ id: 11, key: "CREATED1" });
    const harness = zoteroHarness({ items: [created] });
    created.eraseTx.mockImplementationOnce(async () => {
      const index = harness.items.indexOf(created);
      if (index >= 0) harness.items.splice(index, 1);
      throw new Error("erase reported failure after applying");
    });

    await expect(harness.host.compensate({
      libraryID: 1,
      createdCollectionKey: null,
      createdItemKeys: ["CREATED1"],
      addedMemberships: [],
    })).resolves.toEqual({ complete: true, survivors: [] });
    expect(harness.items).toEqual([]);
  });

  it("reports a created collection when erase is a no-op", async () => {
    const collection = fakeCollection({ id: 20, key: "COLLECTION1", name: "Reviewed imports" });
    const harness = zoteroHarness({ collections: [collection] });
    collection.eraseTx.mockImplementationOnce(async () => false);

    const result = await harness.host.compensate({
      libraryID: 1,
      createdCollectionKey: "COLLECTION1",
      createdItemKeys: [],
      addedMemberships: [],
    });

    expect(result).toEqual({
      complete: false,
      survivors: [{
        kind: "collection",
        collectionKey: "COLLECTION1",
        error: expect.stringMatching(/still exists|remains/i),
      }],
    });
  });

  it("does not treat a merely deleted created object as erased", async () => {
    const created = fakeItem({ id: 11, key: "CREATED1", deleted: true });
    const collection = fakeCollection({
      id: 20,
      key: "COLLECTION1",
      name: "Reviewed imports",
      deleted: true,
    });
    const harness = zoteroHarness({ items: [created], collections: [collection] });
    created.eraseTx.mockImplementationOnce(async () => false);
    collection.eraseTx.mockImplementationOnce(async () => false);

    const result = await harness.host.compensate({
      libraryID: 1,
      createdCollectionKey: "COLLECTION1",
      createdItemKeys: ["CREATED1"],
      addedMemberships: [],
    });

    expect(result).toEqual({
      complete: false,
      survivors: [
        {
          kind: "created-item",
          itemKey: "CREATED1",
          error: expect.stringMatching(/still exists|remains/i),
        },
        {
          kind: "collection",
          collectionKey: "COLLECTION1",
          error: expect.stringMatching(/still exists|remains/i),
        },
      ],
    });
  });

  it("reports conservative survivors when final-state lookup cannot be verified", async () => {
    const created = fakeItem({ id: 11, key: "CREATED1" });
    const harness = zoteroHarness({ items: [created] });
    const lookup = harness.zotero.Items.getByLibraryAndKey;
    lookup.mockImplementationOnce(() => created);
    lookup.mockImplementationOnce(() => { throw new Error("verification lookup failed"); });

    const result = await harness.host.compensate({
      libraryID: 1,
      createdCollectionKey: null,
      createdItemKeys: ["CREATED1"],
      addedMemberships: [],
    });

    expect(result).toEqual({
      complete: false,
      survivors: [{
        kind: "created-item",
        itemKey: "CREATED1",
        error: "verification lookup failed",
      }],
    });
  });

  it("invalidates only the applied library through ReaderContextService", async () => {
    const invalidator = { invalidateZotkitLibrarySnapshot: vi.fn() };
    const { zotero } = zoteroHarness();
    const host = createZoteroLibraryMutationHost(zotero, invalidator);

    await host.invalidateLibrary(7);

    expect(invalidator.invalidateZotkitLibrarySnapshot).toHaveBeenCalledWith(7);
  });

  it("emits receipts accepted by the reviewed Apply coordinator", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    let capabilitySequence = 0;
    const registry = new CitationCandidateRegistry(harness.resolver, {
      createId: () => `capability-${++capabilitySequence}`,
    });
    const service = new ReviewedLibraryImportService(registry, harness.host, {
      onState: vi.fn(),
    }, { createId: () => "review-1" });
    const scope = { threadId: "library-thread", libraryID: 1 };
    const lookup = await service.invokeTool(LOOKUP_CITATIONS_TOOL, {
      requests: [{ client_ref: "r1", doi: "10.1000/new" }],
    }, scope) as { results: Array<{ capability_id: string }> };
    const proposal = await service.invokeTool(PROPOSE_LIBRARY_IMPORT_TOOL, {
      collection_name: "Reviewed imports",
      capability_ids: [lookup.results[0]!.capability_id],
    }, scope) as { review_id: string };

    const result = await service.resolveReview(proposal.review_id, "accept");

    expect(result).toMatchObject({
      decision: "accepted",
      receipt: {
        libraryID: 1,
        createdCollectionKey: expect.stringMatching(/^NEWCOLL/u),
        createdItemKeys: [expect.stringMatching(/^NEWITEM/u)],
        addedMemberships: [{
          itemKey: expect.stringMatching(/^NEWITEM/u),
          collectionKey: expect.stringMatching(/^NEWCOLL/u),
        }],
      },
    });
    expect(harness.invalidator.invalidateZotkitLibrarySnapshot).toHaveBeenCalledWith(1);
  });

  it("gives the reviewed coordinator a trusted partial receipt for compensation", async () => {
    const harness = zoteroHarness({ translatedItems: [translatedPaper()] });
    let capabilitySequence = 0;
    const registry = new CitationCandidateRegistry(harness.resolver, {
      createId: () => `capability-${++capabilitySequence}`,
    });
    const compensate = vi.spyOn(harness.host, "compensate");
    const service = new ReviewedLibraryImportService(registry, harness.host, {
      onState: vi.fn(),
    }, { createId: () => "review-failure" });
    const scope = { threadId: "library-thread", libraryID: 1 };
    const lookup = await service.invokeTool(LOOKUP_CITATIONS_TOOL, {
      requests: [{ client_ref: "r1", doi: "10.1000/new" }],
    }, scope) as { results: Array<{ capability_id: string }> };
    const proposal = await service.invokeTool(PROPOSE_LIBRARY_IMPORT_TOOL, {
      collection_name: "Reviewed imports",
      capability_ids: [lookup.results[0]!.capability_id],
    }, scope) as { review_id: string };
    let failedCollection!: FakeCollection;
    harness.Collection.mockImplementationOnce(function(this: unknown) {
      const failed = fakeCollection({ id: 999, key: "", name: "" });
      failedCollection = failed;
      failed.saveTx.mockImplementationOnce(async () => {
        failed.key = "PARTIAL-COLLECTION";
        harness.collections.push(failed);
      });
      failed.addItem.mockRejectedValueOnce(new Error("membership save failed"));
      failed.eraseTx.mockImplementation(async () => {
        const index = harness.collections.indexOf(failed);
        if (index >= 0) harness.collections.splice(index, 1);
      });
      return failed;
    });

    await expect(service.resolveReview(proposal.review_id, "accept"))
      .rejects.toThrow(/rolled back/i);

    expect(compensate).toHaveBeenCalledWith({
      libraryID: 1,
      createdCollectionKey: "PARTIAL-COLLECTION",
      createdItemKeys: [expect.stringMatching(/^NEWITEM/u)],
      addedMemberships: [],
    });
    expect((harness.Item.mock.results[0]!.value as FakeItem).eraseTx).toHaveBeenCalledOnce();
    expect(failedCollection.eraseTx).toHaveBeenCalledOnce();
    expect(harness.invalidator.invalidateZotkitLibrarySnapshot).toHaveBeenCalledWith(1);
  });
});
