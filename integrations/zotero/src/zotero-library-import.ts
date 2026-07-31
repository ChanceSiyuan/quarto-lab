import {
  canonicalArxivID,
  canonicalDOI,
  type BibliographicMetadata,
  type CitationQuery,
  type CitationResolver,
  type ResolvedCitation,
  type SupportedBibliographicItemType,
} from "./library-citations";
import { sha256Bytes } from "./hashing";
import type { ReaderContextService } from "./reader-context";
import {
  LibraryApplyFailure,
  type BoundLibraryImportPlan,
  type LibraryApplyReceipt,
  type LibraryImportPreflight,
  type LibraryMutationHost,
  type LibraryMutationSurvivor,
  type LibraryRollbackResult,
  type ValidatedLibraryImportPlan,
} from "./reviewed-library-import";

type LibraryID = number | string;
type UnknownRecord = Record<string, unknown>;

const SUPPORTED_ITEM_TYPES = new Set<SupportedBibliographicItemType>([
  "journalArticle",
  "conferencePaper",
  "book",
  "bookSection",
  "report",
  "thesis",
  "preprint",
]);
const ITEM_DATA_TYPES = ["creators", "itemData", "collections"] as const;
const SAFE_ITEM_FIELDS = [
  "title",
  "date",
  "DOI",
  "url",
  "publicationTitle",
  "archive",
  "archiveLocation",
] as const;
const NATIVE_READ_FIELDS = [...SAFE_ITEM_FIELDS, "extra"] as const;
const MAX_ERROR_CODE_POINTS = 240;
const ZOTERO_TRANSLATE_NO_RESULTS = "No items returned from any translator";

export interface ZoteroLibraryImportRuntime {
  DB?: {
    executeTransaction?: (callback: () => Promise<void>) => Promise<void>;
  };
  Libraries?: {
    userLibraryID?: LibraryID;
    get?: (libraryID: LibraryID) => unknown;
    getAsync?: (libraryID: LibraryID) => Promise<unknown>;
  };
  Items?: {
    get?: (id: number | string) => unknown;
    getAsync?: (id: number | string) => Promise<unknown>;
    getAll?: (
      libraryID: LibraryID,
      onlyTopLevel?: boolean,
      includeDeleted?: boolean,
      asIDs?: boolean,
    ) => Promise<unknown[]>;
    loadDataTypes?: (items: unknown[], dataTypes?: string[]) => Promise<void>;
    getByLibraryAndKey?: (libraryID: LibraryID, key: string) => unknown;
    getByLibraryAndKeyAsync?: (libraryID: LibraryID, key: string) => Promise<unknown>;
  };
  Collections?: {
    get?: (id: number | string) => unknown;
    getAsync?: (id: number | string) => Promise<unknown>;
    getByLibrary?: (
      libraryID: LibraryID,
      recursive?: boolean,
      includeTrashed?: boolean,
    ) => unknown[] | Promise<unknown[]>;
    getByLibraryAndKey?: (libraryID: LibraryID, key: string) => unknown;
    getByLibraryAndKeyAsync?: (libraryID: LibraryID, key: string) => Promise<unknown>;
  };
  Translate?: {
    Search?: new () => {
      setIdentifier(identifier: Record<string, string>): void;
      getTranslators(): unknown[] | Promise<unknown[]>;
      setTranslator(translators: unknown): void;
      translate(options: { libraryID: false; saveAttachments: false }): unknown;
      getItems?: () => unknown;
    };
  };
  Item?: new (itemType: string) => unknown;
  Collection?: new () => unknown;
}

export interface ZoteroCitationResolverOptions {
  createChoiceId?: () => string;
}

export interface ZotkitLibrarySnapshotInvalidator {
  invalidateZotkitLibrarySnapshot(libraryID: LibraryID): void | Promise<void>;
}

interface StoredCandidate {
  choiceId: string;
  libraryID: LibraryID;
  metadata: BibliographicMetadata | null;
  localItemKey: string | null;
  localItemVersion: number | null;
}

interface RuntimeCandidateState {
  candidates: Map<string, StoredCandidate>;
}

interface NativeInspection {
  preflight: LibraryImportPreflight;
  itemsByKey: Map<string, unknown>;
  itemIDs: Set<number | string>;
  collectionKeys: Set<string>;
  collectionIDs: Set<number | string>;
  sibling: unknown | null;
  parent: unknown | null;
}

class ManualInspectionRequiredError extends Error {
  constructor(message: string) {
    super(`Manual inspection required: ${message}`);
    this.name = "ManualInspectionRequiredError";
  }
}

const runtimeCandidateStates = new WeakMap<object, RuntimeCandidateState>();

function candidateState(zotero: ZoteroLibraryImportRuntime): RuntimeCandidateState {
  const key = zotero as object;
  let state = runtimeCandidateStates.get(key);
  if (!state) {
    state = { candidates: new Map() };
    runtimeCandidateStates.set(key, state);
  }
  return state;
}

async function executeZoteroTransaction(
  zotero: ZoteroLibraryImportRuntime,
  callback: () => Promise<void>,
): Promise<void> {
  const db = zotero.DB;
  if (!db?.executeTransaction) throw new Error("Zotero database transaction writer is unavailable");
  await db.executeTransaction(callback);
}

/**
 * Create the lookup-only Zotero resolver. Identifier translation is used as
 * an unsaved metadata source; all write constructors remain outside this path.
 */
export function createZoteroCitationResolver(
  zotero: ZoteroLibraryImportRuntime = Zotero as ZoteroLibraryImportRuntime,
  options: ZoteroCitationResolverOptions = {},
): CitationResolver {
  const state = candidateState(zotero);
  const createChoiceId = options.createChoiceId ?? secureChoiceId;

  const bindCandidate = (
    libraryID: LibraryID,
    candidate: Omit<StoredCandidate, "choiceId" | "libraryID">,
  ): ResolvedCitation["candidates"][number] => {
    let choiceId = "";
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const proposed = createChoiceId();
      if (typeof proposed === "string" && proposed.trim() && !state.candidates.has(proposed)) {
        choiceId = proposed;
        break;
      }
    }
    if (!choiceId) throw new Error("Zotero citation choice ID factory produced duplicate or blank IDs");
    const stored: StoredCandidate = {
      choiceId,
      libraryID,
      metadata: candidate.metadata === null ? null : cloneMetadata(candidate.metadata),
      localItemKey: candidate.localItemKey,
      localItemVersion: candidate.localItemVersion,
    };
    state.candidates.set(choiceId, stored);
    return {
      choiceId,
      metadata: stored.metadata === null ? null : cloneMetadata(stored.metadata),
      localItemKey: stored.localItemKey,
      localItemVersion: stored.localItemVersion,
      provenance: stored.localItemKey === null
        ? "Zotero identifier translation (metadata only)"
        : "Exact local Zotero match",
    };
  };

  const localCandidates = async (libraryID: LibraryID): Promise<unknown[]> =>
    loadCompleteNativeItems(zotero, libraryID);

  const localResolution = (
    request: CitationQuery,
    libraryID: LibraryID,
    matches: readonly unknown[],
    reason: string,
  ): ResolvedCitation => {
    const candidates = matches.map((item) => bindCandidate(libraryID, {
      metadata: metadataFromNativeItem(item),
      localItemKey: nativeKey(item, "Zotero item"),
      localItemVersion: nativeVersion(item, "Zotero item"),
    }));
    return {
      clientRef: request.clientRef,
      status: candidates.length === 1 ? "reuse" : "ambiguous",
      candidates,
      reason,
    };
  };

  const translateIdentifier = async (
    request: CitationQuery,
    libraryID: LibraryID,
    identifier: { DOI: string } | { arXiv: string },
  ): Promise<ResolvedCitation | null> => {
    const Search = zotero.Translate?.Search;
    if (!Search) return null;
    const search = new Search();
    search.setIdentifier({ ...identifier });
    const translators = await search.getTranslators();
    if (!Array.isArray(translators) || translators.length === 0) return null;
    search.setTranslator(translators);
    let rawResult: unknown;
    try {
      rawResult = await search.translate({ libraryID: false, saveAttachments: false });
    }
    catch (error) {
      const message = error instanceof Error ? error.message : error;
      if (message === ZOTERO_TRANSLATE_NO_RESULTS) return null;
      throw new Error(boundedError(error));
    }
    const translatedItems = Array.isArray(rawResult) ? rawResult : search.getItems?.();
    const rawItems = Array.isArray(rawResult)
      ? rawResult
      : Array.isArray(translatedItems)
        ? translatedItems
        : [];
    const metadata = (rawItems as unknown[])
      .map(metadataFromTranslatedItem)
      .filter((entry): entry is BibliographicMetadata => entry !== null)
      .filter((entry) => "DOI" in identifier
        ? canonicalDOI(entry.DOI) === identifier.DOI
        : metadataArxivID(entry) === identifier.arXiv);
    if (metadata.length === 0) return null;
    const candidates = metadata.map((entry) => bindCandidate(libraryID, {
      metadata: entry,
      localItemKey: null,
      localItemVersion: null,
    }));
    return {
      clientRef: request.clientRef,
      status: candidates.length === 1 ? "create" : "ambiguous",
      candidates,
      reason: candidates.length === 1
        ? "Resolved from Zotero identifier metadata without importing"
        : "Multiple exact identifier metadata records require user selection",
    };
  };

  return {
    async resolve(scope, requests) {
      const libraryID = scope.libraryID;
      const items = await localCandidates(libraryID);
      const results: ResolvedCitation[] = [];
      for (const request of requests) {
        const doi = request.doi ? canonicalDOI(request.doi) : null;
        if (doi) {
          const exactDOI = items.filter((item) => canonicalDOI(nativeField(item, "DOI")) === doi);
          if (exactDOI.length) {
            results.push(localResolution(
              request,
              libraryID,
              exactDOI,
              exactDOI.length === 1 ? "Exact local DOI match" : "Multiple exact local DOI matches",
            ));
            continue;
          }
        }

        const arxiv = request.arxiv ? canonicalArxivID(request.arxiv) : null;
        if (arxiv) {
          const exactArxiv = items.filter((item) => nativeArxivID(item) === arxiv);
          if (exactArxiv.length) {
            results.push(localResolution(
              request,
              libraryID,
              exactArxiv,
              exactArxiv.length === 1 ? "Exact local arXiv match" : "Multiple exact local arXiv matches",
            ));
            continue;
          }
        }

        let translated: ResolvedCitation | null = null;
        if (doi) translated = await translateIdentifier(request, libraryID, { DOI: doi });
        if (!translated && arxiv) {
          translated = await translateIdentifier(request, libraryID, { arXiv: arxiv });
        }
        if (translated) {
          results.push(translated);
          continue;
        }

        const titleMatches = request.title
          ? items.filter((item) => exactTitleCandidate(item, request))
          : [];
        if (titleMatches.length) {
          results.push(localResolution(
            request,
            libraryID,
            titleMatches,
            titleMatches.length === 1
              ? "Exact normalized local title, year, and creator match"
              : "Multiple exact normalized local title, year, and creator matches",
          ));
          continue;
        }

        results.push({
          clientRef: request.clientRef,
          status: "unresolved",
          candidates: [],
          reason: request.title && !doi && !arxiv
            ? "No exact local match; title-only input cannot authorize invented create metadata"
            : "No exact local or identifier metadata match",
        });
      }
      return results;
    },
  };
}

/** Create the Zotero-native preflight, Apply, compensation, and cache host. */
export function createZoteroLibraryMutationHost(
  zotero: ZoteroLibraryImportRuntime = Zotero as ZoteroLibraryImportRuntime,
  snapshotInvalidator?: ZotkitLibrarySnapshotInvalidator
    | Pick<ReaderContextService<unknown, unknown>, "invalidateZotkitLibrarySnapshot">,
): LibraryMutationHost {
  const state = candidateState(zotero);

  const inspect = async (plan: BoundLibraryImportPlan): Promise<NativeInspection> => {
    const libraryID = plan.scope.libraryID;
    const [items, collections, editableResult] = await Promise.all([
      loadCompleteNativeItems(zotero, libraryID),
      loadCompleteNativeCollections(zotero, libraryID),
      libraryIsEditable(zotero, libraryID),
    ]);
    const itemsByKey = uniqueNativeObjectsByKey(items, libraryID, "item");
    const collectionsByKey = uniqueNativeObjectsByKey(collections, libraryID, "collection");
    const itemIDs = uniqueNativeIDs(items, "item");
    const collectionIDs = uniqueNativeIDs(collections, "collection");
    const parentKey = plan.target.parentCollectionKey;
    const parent = parentKey === null ? null : collectionsByKey.get(parentKey) ?? null;
    const parentValid = parentKey === null || Boolean(parent && !nativeDeleted(parent));
    const parentVersion = parentValid && parent ? nativeVersion(parent, "Parent collection") : null;
    const parentID = parent ? nativeID(parent, "Parent collection") : null;
    const siblings = collections.filter((collection) => {
      if (nativeDeleted(collection) || !sameLibrary(collection, libraryID)) return false;
      if (normalizedName(nativeStringProperty(collection, "name")) !== normalizedName(plan.target.collectionName)) {
        return false;
      }
      return collectionParentIdentity(collection, collectionsByKey) === parentKey;
    });
    if (siblings.length > 1) {
      throw new Error("Multiple exact sibling collections have the reviewed normalized name");
    }
    const sibling = siblings[0] ?? null;
    if (sibling) {
      nativeKey(sibling, "Sibling collection");
      nativeVersion(sibling, "Sibling collection");
    }

    const createIdentityCounts = new Map<string, number>();
    for (const row of plan.rows) {
      if (row.omit || row.choiceId === null) continue;
      const candidate = state.candidates.get(row.choiceId);
      if (!candidate || candidate.libraryID !== libraryID || candidate.localItemKey !== null || !candidate.metadata) {
        continue;
      }
      const identity = metadataDuplicateIdentity(candidate.metadata);
      if (identity) createIdentityCounts.set(identity, (createIdentityCounts.get(identity) ?? 0) + 1);
    }

    const dispositions: LibraryImportPreflight["dispositions"][number][] = plan.rows.map((row) => {
      if (row.omit) return emptyDisposition(row.rowId, "omit");
      if (row.choiceId === null) return emptyDisposition(row.rowId, "conflict");
      const candidate = state.candidates.get(row.choiceId);
      if (!candidate || candidate.libraryID !== libraryID) {
        return emptyDisposition(row.rowId, "conflict");
      }
      if (candidate.localItemKey !== null) {
        const item = itemsByKey.get(candidate.localItemKey);
        if (!item || nativeDeleted(item)) return emptyDisposition(row.rowId, "conflict");
        const version = nativeVersion(item, "Reused Zotero item");
        if (candidate.localItemVersion !== version) return emptyDisposition(row.rowId, "conflict");
        return {
          rowId: row.rowId,
          effect: "reuse",
          itemKey: candidate.localItemKey,
          itemVersion: version,
          membershipExists: sibling ? nativeMembershipExists(sibling, item) : false,
        };
      }
      if (!candidate.metadata) return emptyDisposition(row.rowId, "conflict");
      const identity = metadataDuplicateIdentity(candidate.metadata);
      const plannedDuplicate = identity !== null && (createIdentityCounts.get(identity) ?? 0) > 1;
      const nativeDuplicate = items.some((item) => exactMetadataDuplicate(item, candidate.metadata!));
      if (plannedDuplicate || nativeDuplicate) return emptyDisposition(row.rowId, "conflict");
      return emptyDisposition(row.rowId, "create");
    });
    const editable = editableResult && parentValid;
    const digest = await preflightDigest({
      libraryID,
      editable,
      parentKey,
      parentID,
      parentVersion,
      siblingKey: sibling ? nativeKey(sibling, "Sibling collection") : null,
      siblingVersion: sibling ? nativeVersion(sibling, "Sibling collection") : null,
      dispositions,
      rows: plan.rows.map((row) => ({ ...row })),
    });
    return {
      preflight: {
        digest,
        editable,
        parentVersion,
        siblingCollectionKey: sibling ? nativeKey(sibling, "Sibling collection") : null,
        dispositions,
      },
      itemsByKey,
      itemIDs,
      collectionKeys: new Set(collectionsByKey.keys()),
      collectionIDs,
      sibling,
      parent,
    };
  };

  const preflight = async (plan: BoundLibraryImportPlan): Promise<LibraryImportPreflight> =>
    clonePreflight((await inspect(plan)).preflight);

  return {
    preflight,

    async apply(plan: ValidatedLibraryImportPlan): Promise<LibraryApplyReceipt> {
      const basePlan: BoundLibraryImportPlan = {
        scope: { ...plan.scope },
        target: { ...plan.target },
        rows: plan.rows.map((row) => ({ ...row })),
      };
      const inspection = await inspect(basePlan);
      if (!samePreflight(inspection.preflight, plan.preflight)) {
        throw new Error("Zotero native preflight changed before Apply; no writes were attempted");
      }
      if (!inspection.preflight.editable) {
        throw new Error("The reviewed Zotero library or parent collection is not editable");
      }
      if (inspection.preflight.dispositions.some((entry) => entry.effect === "conflict")) {
        throw new Error("Zotero native preflight contains a duplicate or stale conflict");
      }

      const receipt: LibraryApplyReceipt = {
        libraryID: plan.scope.libraryID,
        createdCollectionKey: null,
        createdItemKeys: [],
        addedMemberships: [],
      };
      let writePhase = false;
      try {
        let collection = inspection.sibling;
        if (!collection) {
          writePhase = true;
          const Collection = zotero.Collection;
          if (!Collection) throw new Error("Zotero Collection constructor is unavailable");
          collection = new Collection();
          setNativeProperty(collection, "libraryID", plan.scope.libraryID);
          setNativeProperty(collection, "name", plan.target.collectionName);
          setNativeProperty(
            collection,
            "parentID",
            inspection.parent ? nativeID(inspection.parent, "Parent collection") : null,
          );
          const savedCollectionID = await nativeMethod(
            collection,
            "saveTx",
            "Zotero collection save",
          )();
          const createdCollection = await validateSavedNativeObject(
            zotero,
            "collection",
            collection,
            savedCollectionID,
            plan.scope.libraryID,
            inspection.collectionIDs,
            inspection.collectionKeys,
          );
          const createdCollectionKey = createdCollection.key;
          receipt.createdCollectionKey = createdCollectionKey;
        }
        const collectionKey = nativeKey(collection, "Target collection");
        const addItem = nativeMethod(collection, "addItem", "Zotero collection membership writer");
        const hasItem = nativeMethod(collection, "hasItem", "Zotero collection membership reader");
        const recordedMemberships = new Set<string>();
        const recordedCreatedItems = new Set<string>();
        for (const row of plan.rows) {
          if (row.omit) continue;
          const disposition = inspection.preflight.dispositions.find((entry) => entry.rowId === row.rowId);
          if (!disposition || row.choiceId === null) throw new Error("Validated Apply row lost its native disposition");
          const candidate = state.candidates.get(row.choiceId);
          if (!candidate || candidate.libraryID !== plan.scope.libraryID) {
            throw new Error("Validated Apply row lost its bound Zotero candidate");
          }
          let item: unknown;
          let itemID: number | string;
          let created = false;
          if (disposition.effect === "create") {
            writePhase = true;
            const Item = zotero.Item;
            if (!Item || !candidate.metadata) throw new Error("Zotero Item constructor or create metadata is unavailable");
            item = new Item(candidate.metadata.itemType);
            setNativeProperty(item, "libraryID", plan.scope.libraryID);
            const setField = nativeMethod(item, "setField", "Zotero item field writer");
            for (const field of SAFE_ITEM_FIELDS) {
              const value = candidate.metadata[field];
              if (value) setField(field, value);
            }
            nativeMethod(item, "setCreators", "Zotero item creator writer")(
              candidate.metadata.creators.map((creator) => ({ ...creator })),
            );
            const savedItemID = await nativeMethod(item, "saveTx", "Zotero item save")();
            const createdItem = await validateSavedNativeObject(
              zotero,
              "item",
              item,
              savedItemID,
              plan.scope.libraryID,
              inspection.itemIDs,
              new Set([...inspection.itemsByKey.keys(), ...recordedCreatedItems]),
            );
            const createdItemKey = createdItem.key;
            itemID = createdItem.id;
            recordedCreatedItems.add(createdItemKey);
            (receipt.createdItemKeys as string[]).push(createdItemKey);
            created = true;
          }
          else if (disposition.effect === "reuse" && disposition.itemKey !== null) {
            item = inspection.itemsByKey.get(disposition.itemKey);
            if (!item) throw new Error("Reused Zotero item disappeared after native preflight");
            itemID = nativeID(item, "Reused Zotero item");
          }
          else {
            throw new Error("Validated Apply contains a non-applicable native disposition");
          }

          const itemKey = nativeKey(item, created ? "Created Zotero item" : "Reused Zotero item");
          const membershipIdentity = `${itemKey}\u0000${collectionKey}`;
          if (recordedMemberships.has(membershipIdentity) || (!created && disposition.membershipExists)) {
            continue;
          }
          writePhase = true;
          const recordMembership = () => {
            recordedMemberships.add(membershipIdentity);
            (receipt.addedMemberships as Array<{ itemKey: string; collectionKey: string }>).push({
              itemKey,
              collectionKey,
            });
          };
          try {
            await executeZoteroTransaction(zotero, async () => {
              await addItem(itemID);
              if (!nativeMembershipState(hasItem, itemID)) {
                throw new Error("Zotero collection membership write did not apply");
              }
            });
          }
          catch (error) {
            let applied: boolean;
            try {
              applied = nativeMembershipState(hasItem, itemID);
            }
            catch (verificationError) {
              throw new ManualInspectionRequiredError(
                `could not verify membership ${itemKey} in ${collectionKey}: ${boundedError(verificationError)}`,
              );
            }
            if (applied) recordMembership();
            throw error;
          }
          recordMembership();
        }
        return cloneReceipt(receipt);
      }
      catch (error) {
        if (error instanceof ManualInspectionRequiredError) throw error;
        if (!writePhase) throw error;
        throw new LibraryApplyFailure(boundedError(error), cloneReceipt(receipt));
      }
    },

    async compensate(rawReceipt: LibraryApplyReceipt): Promise<LibraryRollbackResult> {
      const receipt = normalizeCompensationReceipt(rawReceipt);
      const createdItems = new Set(receipt.createdItemKeys);
      const membershipErrors = new Map<string, string>();
      const itemErrors = new Map<string, string>();
      let collectionError: string | null = null;
      const membershipIdentity = (itemKey: string, collectionKey: string) =>
        `${itemKey}\u0000${collectionKey}`;

      for (const membership of receipt.addedMemberships) {
        if (createdItems.has(membership.itemKey)) continue;
        try {
          const [collection, item] = await Promise.all([
            getNativeCollection(zotero, receipt.libraryID, membership.collectionKey),
            getNativeItem(zotero, receipt.libraryID, membership.itemKey),
          ]);
          if (!collection || !item) continue;
          assertNativeIdentity(collection, receipt.libraryID, membership.collectionKey, "Compensation collection");
          assertNativeIdentity(item, receipt.libraryID, membership.itemKey, "Compensation item");
          await executeZoteroTransaction(zotero, async () => {
            await nativeMethod(collection, "removeItem", "Zotero collection membership remover")(
              nativeID(item, "Compensation item"),
            );
          });
        }
        catch (error) {
          membershipErrors.set(
            membershipIdentity(membership.itemKey, membership.collectionKey),
            boundedError(error),
          );
        }
      }

      for (const itemKey of receipt.createdItemKeys) {
        try {
          const item = await getNativeItem(zotero, receipt.libraryID, itemKey);
          if (!item) continue;
          assertNativeIdentity(item, receipt.libraryID, itemKey, "Created compensation item");
          await nativeMethod(item, "eraseTx", "Zotero item eraser")();
        }
        catch (error) {
          itemErrors.set(itemKey, boundedError(error));
        }
      }

      if (receipt.createdCollectionKey !== null) {
        try {
          const collection = await getNativeCollection(
            zotero,
            receipt.libraryID,
            receipt.createdCollectionKey,
          );
          if (collection) {
            assertNativeIdentity(
              collection,
              receipt.libraryID,
              receipt.createdCollectionKey,
              "Created compensation collection",
            );
            await nativeMethod(collection, "eraseTx", "Zotero collection eraser")();
          }
        }
        catch (error) {
          collectionError = boundedError(error);
        }
      }

      const survivors: LibraryMutationSurvivor[] = [];
      for (const membership of receipt.addedMemberships) {
        const identity = membershipIdentity(membership.itemKey, membership.collectionKey);
        try {
          const collection = await getNativeCollection(
            zotero,
            receipt.libraryID,
            membership.collectionKey,
          );
          if (!collection) continue;
          assertNativeIdentity(
            collection,
            receipt.libraryID,
            membership.collectionKey,
            "Compensation verification collection",
          );
          const item = await getNativeItem(zotero, receipt.libraryID, membership.itemKey);
          if (!item) continue;
          assertNativeIdentity(
            item,
            receipt.libraryID,
            membership.itemKey,
            "Compensation verification item",
          );
          const stillExists = nativeMembershipState(
            nativeMethod(collection, "hasItem", "Zotero collection membership verifier"),
            nativeID(item, "Compensation verification item"),
          );
          if (!stillExists) continue;
          survivors.push({
            kind: "membership",
            itemKey: membership.itemKey,
            collectionKey: membership.collectionKey,
            error: membershipErrors.get(identity) ?? "Membership still exists after compensation",
          });
        }
        catch (error) {
          survivors.push({
            kind: "membership",
            itemKey: membership.itemKey,
            collectionKey: membership.collectionKey,
            error: boundedError(error),
          });
        }
      }

      for (const itemKey of receipt.createdItemKeys) {
        try {
          const item = await getNativeItem(zotero, receipt.libraryID, itemKey);
          if (!item) continue;
          assertNativeIdentity(item, receipt.libraryID, itemKey, "Created item verification");
          survivors.push({
            kind: "created-item",
            itemKey,
            error: itemErrors.get(itemKey) ?? "Created item still exists after compensation",
          });
        }
        catch (error) {
          survivors.push({ kind: "created-item", itemKey, error: boundedError(error) });
        }
      }

      if (receipt.createdCollectionKey !== null) {
        try {
          const collection = await getNativeCollection(
            zotero,
            receipt.libraryID,
            receipt.createdCollectionKey,
          );
          if (collection) {
            assertNativeIdentity(
              collection,
              receipt.libraryID,
              receipt.createdCollectionKey,
              "Created collection verification",
            );
            survivors.push({
              kind: "collection",
              collectionKey: receipt.createdCollectionKey,
              error: collectionError ?? "Created collection still exists after compensation",
            });
          }
        }
        catch (error) {
          survivors.push({
            kind: "collection",
            collectionKey: receipt.createdCollectionKey,
            error: boundedError(error),
          });
        }
      }
      return { complete: survivors.length === 0, survivors };
    },

    async invalidateLibrary(libraryID: LibraryID): Promise<void> {
      if (!snapshotInvalidator) return;
      await snapshotInvalidator.invalidateZotkitLibrarySnapshot(libraryID);
    },
  };
}

async function loadCompleteNativeItems(
  zotero: ZoteroLibraryImportRuntime,
  libraryID: LibraryID,
): Promise<unknown[]> {
  const getAll = zotero.Items?.getAll;
  const loadDataTypes = zotero.Items?.loadDataTypes;
  if (!getAll || !loadDataTypes) {
    throw new Error("Complete Zotero item enumeration with loaded fields is unavailable");
  }
  const raw = await getAll(libraryID, true, false, false);
  if (!isDenseArray(raw)) throw new Error("Complete Zotero item enumeration returned an invalid result");
  const items = [...raw];
  await loadDataTypes(items, [...ITEM_DATA_TYPES]);
  const regularItems: unknown[] = [];
  for (const item of items) {
    if (!isObject(item)) throw new Error("Complete Zotero item enumeration returned a non-object");
    if (!sameLibrary(item, libraryID)) {
      throw new Error("Complete Zotero item enumeration crossed the target library boundary");
    }
    if (nativeDeleted(item)) continue;
    const isTopLevel = optionalMethod(item, "isTopLevelItem");
    if (isTopLevel && !isTopLevel()) {
      throw new Error("Complete top-level Zotero enumeration returned a child item");
    }
    const isRegularItem = nativeMethod(
      item,
      "isRegularItem",
      "Regular Zotero item classifier",
    );
    if (isRegularItem() !== true) continue;
    const itemType = nativeStringProperty(item, "itemType");
    if (!SUPPORTED_ITEM_TYPES.has(itemType as SupportedBibliographicItemType)) continue;
    nativeKey(item, "Enumerated Zotero item");
    nativeVersion(item, "Enumerated Zotero item");
    const getField = nativeMethod(item, "getField", "Loaded Zotero item field reader");
    for (const field of NATIVE_READ_FIELDS) {
      if (getField(field) === undefined) {
        throw new Error(`Loaded Zotero item field ${field} is unavailable`);
      }
    }
    nativeMethod(item, "getCreators", "Loaded Zotero item creator reader")();
    nativeMethod(item, "getCollections", "Loaded Zotero item membership reader")();
    regularItems.push(item);
  }
  return regularItems;
}

async function loadCompleteNativeCollections(
  zotero: ZoteroLibraryImportRuntime,
  libraryID: LibraryID,
): Promise<unknown[]> {
  const getByLibrary = zotero.Collections?.getByLibrary;
  if (!getByLibrary) throw new Error("Complete Zotero collection enumeration is unavailable");
  const raw = await getByLibrary(libraryID, true, false);
  if (!isDenseArray(raw)) throw new Error("Complete Zotero collection enumeration returned an invalid result");
  const collections = [...raw];
  for (const collection of collections) {
    if (!isObject(collection) || !sameLibrary(collection, libraryID)) {
      throw new Error("Complete Zotero collection enumeration crossed the target library boundary");
    }
    nativeKey(collection, "Enumerated Zotero collection");
    nativeVersion(collection, "Enumerated Zotero collection");
    nativeStringProperty(collection, "name");
  }
  return collections;
}

async function libraryIsEditable(
  zotero: ZoteroLibraryImportRuntime,
  libraryID: LibraryID,
): Promise<boolean> {
  let library: unknown = null;
  if (zotero.Libraries?.getAsync) library = await zotero.Libraries.getAsync(libraryID);
  else if (zotero.Libraries?.get) library = zotero.Libraries.get(libraryID);
  if (library) {
    if (!sameLibrary(library, libraryID)) return false;
    const editable = safeProperty(library, "editable");
    if (editable === true) return true;
    if (editable === false) return false;
    const check = optionalMethod(library, "isEditable");
    if (check) return check() === true;
    return false;
  }
  return zotero.Libraries?.userLibraryID === libraryID;
}

function uniqueNativeObjectsByKey(
  objects: readonly unknown[],
  libraryID: LibraryID,
  label: "item" | "collection",
): Map<string, unknown> {
  const result = new Map<string, unknown>();
  for (const object of objects) {
    if (!sameLibrary(object, libraryID)) {
      throw new Error(`Native Zotero ${label} enumeration crossed the target library boundary`);
    }
    const key = nativeKey(object, `Native Zotero ${label}`);
    if (result.has(key)) throw new Error(`Native Zotero ${label} enumeration returned duplicate keys`);
    result.set(key, object);
  }
  return result;
}

function uniqueNativeIDs(
  objects: readonly unknown[],
  label: "item" | "collection",
): Set<number | string> {
  const result = new Set<number | string>();
  for (const object of objects) {
    const id = nativeID(object, `Native Zotero ${label}`);
    if (result.has(id)) throw new Error(`Native Zotero ${label} enumeration returned duplicate IDs`);
    result.add(id);
  }
  return result;
}

function collectionParentIdentity(
  collection: unknown,
  collectionsByKey: ReadonlyMap<string, unknown>,
): string | null {
  const parentKey = safeProperty(collection, "parentKey");
  if (typeof parentKey === "string" && parentKey) return parentKey;
  const parentID = safeProperty(collection, "parentID");
  if (parentID === null || parentID === undefined || parentID === false || parentID === 0) return null;
  for (const [key, candidate] of collectionsByKey) {
    if (safeProperty(candidate, "id") === parentID || safeProperty(candidate, "collectionID") === parentID) {
      return key;
    }
  }
  throw new Error("Zotero collection parent is absent from complete enumeration");
}

function metadataFromNativeItem(item: unknown): BibliographicMetadata | null {
  const itemType = nativeStringProperty(item, "itemType");
  if (!SUPPORTED_ITEM_TYPES.has(itemType as SupportedBibliographicItemType)) return null;
  const title = cleanText(nativeField(item, "title"));
  if (!title) return null;
  return {
    itemType: itemType as SupportedBibliographicItemType,
    title,
    creators: nativeCreators(item),
    date: cleanText(nativeField(item, "date")),
    DOI: canonicalDOI(nativeField(item, "DOI")) ?? "",
    url: cleanText(nativeField(item, "url")),
    publicationTitle: cleanText(nativeField(item, "publicationTitle")),
    archive: cleanText(nativeField(item, "archive")),
    archiveLocation: canonicalArxivID(nativeField(item, "archiveLocation"))
      ?? cleanText(nativeField(item, "archiveLocation")),
  };
}

function metadataFromTranslatedItem(item: unknown): BibliographicMetadata | null {
  if (!isObject(item)) return null;
  const itemType = typeof item.itemType === "string" ? item.itemType : "";
  if (!SUPPORTED_ITEM_TYPES.has(itemType as SupportedBibliographicItemType)) return null;
  const title = cleanText(item.title);
  if (!title) return null;
  const rawCreators = Array.isArray(item.creators) ? item.creators : [];
  const creators = rawCreators.flatMap((creator): BibliographicMetadata["creators"][number][] => {
    if (!isObject(creator) || creator.creatorType !== "author") return [];
    const firstName = cleanText(creator.firstName);
    const lastName = cleanText(creator.lastName);
    const name = cleanText(creator.name);
    if (!firstName && !lastName && !name) return [];
    return [{
      creatorType: "author",
      ...(firstName ? { firstName } : {}),
      ...(lastName ? { lastName } : {}),
      ...(name ? { name } : {}),
    }];
  });
  const DOI = canonicalDOI(cleanText(item.DOI)) ?? "";
  const rawArchiveLocation = cleanText(item.archiveLocation);
  return {
    itemType: itemType as SupportedBibliographicItemType,
    title,
    creators,
    date: cleanText(item.date),
    DOI,
    url: cleanText(item.url),
    publicationTitle: cleanText(item.publicationTitle),
    archive: cleanText(item.archive),
    archiveLocation: canonicalArxivID(rawArchiveLocation) ?? rawArchiveLocation,
  };
}

function cloneMetadata(metadata: BibliographicMetadata): BibliographicMetadata {
  return {
    ...metadata,
    creators: metadata.creators.map((creator) => ({ ...creator })),
  };
}

function nativeCreators(item: unknown): BibliographicMetadata["creators"] {
  const raw = nativeMethod(item, "getCreators", "Loaded Zotero item creator reader")();
  if (!Array.isArray(raw)) throw new Error("Loaded Zotero creators are incomplete");
  return raw.flatMap((creator): BibliographicMetadata["creators"][number][] => {
    if (!isObject(creator) || creator.creatorType !== "author") return [];
    const firstName = cleanText(creator.firstName);
    const lastName = cleanText(creator.lastName);
    const name = cleanText(creator.name);
    if (!firstName && !lastName && !name) return [];
    return [{
      creatorType: "author",
      ...(firstName ? { firstName } : {}),
      ...(lastName ? { lastName } : {}),
      ...(name ? { name } : {}),
    }];
  });
}

function nativeArxivID(item: unknown): string | null {
  for (const value of [
    normalizedText(nativeField(item, "archive")) === "arxiv"
      ? nativeField(item, "archiveLocation")
      : "",
    nativeField(item, "url"),
    arxivFromExtra(nativeField(item, "extra")),
  ]) {
    const canonical = canonicalArxivID(value);
    if (canonical) return canonical;
  }
  return null;
}

function metadataArxivID(metadata: BibliographicMetadata): string | null {
  const archiveLocation = normalizedText(metadata.archive) === "arxiv"
    ? canonicalArxivID(metadata.archiveLocation)
    : null;
  return archiveLocation ?? canonicalArxivID(metadata.url);
}

function arxivFromExtra(extra: string): string {
  return /(?:^|\n)\s*arxiv\s*:\s*([^\s]+)/iu.exec(extra)?.[1] ?? "";
}

function exactTitleCandidate(item: unknown, query: CitationQuery): boolean {
  if (!query.title || normalizedText(nativeField(item, "title")) !== normalizedText(query.title)) return false;
  if (query.year !== undefined && nativeYear(nativeField(item, "date")) !== String(query.year)) return false;
  if (query.creators?.length) {
    const local = nativeCreators(item).map(creatorName).map(normalizedText);
    if (!query.creators.every((creator) => local.includes(normalizedText(creator)))) return false;
  }
  return true;
}

function creatorName(creator: BibliographicMetadata["creators"][number]): string {
  return creator.name ?? [creator.firstName, creator.lastName].filter(Boolean).join(" ");
}

function nativeYear(date: string): string {
  return /(?:^|\D)(\d{4})(?:\D|$)/u.exec(date)?.[1] ?? "";
}

function metadataDuplicateIdentity(metadata: BibliographicMetadata): string | null {
  const doi = canonicalDOI(metadata.DOI);
  if (doi) return `doi:${doi}`;
  const arxiv = metadataArxivID(metadata);
  if (arxiv) return `arxiv:${arxiv}`;
  const title = normalizedText(metadata.title);
  const year = nativeYear(metadata.date);
  const creators = metadata.creators.map(creatorName).map(normalizedText).filter(Boolean).sort();
  return title && year && creators.length ? `work:${title}\u0000${year}\u0000${creators.join("\u0001")}` : null;
}

function exactMetadataDuplicate(item: unknown, metadata: BibliographicMetadata): boolean {
  const doi = canonicalDOI(metadata.DOI);
  if (doi) return canonicalDOI(nativeField(item, "DOI")) === doi;
  const arxiv = metadataArxivID(metadata);
  if (arxiv) return nativeArxivID(item) === arxiv;
  const identity = metadataDuplicateIdentity(metadata);
  const nativeMetadata = metadataFromNativeItem(item);
  return identity !== null && nativeMetadata !== null && metadataDuplicateIdentity(nativeMetadata) === identity;
}

function nativeMembershipExists(collection: unknown, item: unknown): boolean {
  const collectionID = nativeID(collection, "Target collection");
  const memberships = nativeMethod(item, "getCollections", "Loaded Zotero item membership reader")();
  if (!Array.isArray(memberships)) throw new Error("Loaded Zotero item memberships are incomplete");
  return memberships.some((id) => id === collectionID);
}

function nativeMembershipState(
  hasItem: (...args: unknown[]) => unknown,
  itemID: number | string,
): boolean {
  const value = hasItem(itemID);
  if (typeof value !== "boolean") {
    throw new Error("Zotero collection membership state is unavailable or non-boolean");
  }
  return value;
}

function emptyDisposition(
  rowId: string,
  effect: "create" | "omit" | "conflict",
): LibraryImportPreflight["dispositions"][number] {
  return { rowId, effect, itemKey: null, itemVersion: null, membershipExists: false };
}

function clonePreflight(preflight: LibraryImportPreflight): LibraryImportPreflight {
  return {
    digest: preflight.digest,
    editable: preflight.editable,
    parentVersion: preflight.parentVersion,
    siblingCollectionKey: preflight.siblingCollectionKey,
    dispositions: preflight.dispositions.map((entry) => ({ ...entry })),
  };
}

function samePreflight(left: LibraryImportPreflight, right: LibraryImportPreflight): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function cloneReceipt(receipt: LibraryApplyReceipt): LibraryApplyReceipt {
  return {
    libraryID: receipt.libraryID,
    createdCollectionKey: receipt.createdCollectionKey,
    createdItemKeys: [...receipt.createdItemKeys],
    addedMemberships: receipt.addedMemberships.map((membership) => ({ ...membership })),
  };
}

function normalizeCompensationReceipt(receipt: LibraryApplyReceipt): LibraryApplyReceipt {
  if (!isPlainObject(receipt)) throw new TypeError("Library compensation receipt must be a plain object");
  const keys = Object.keys(receipt);
  const expected = ["libraryID", "createdCollectionKey", "createdItemKeys", "addedMemberships"];
  if (keys.length !== expected.length || expected.some((key) => !keys.includes(key))) {
    throw new TypeError("Library compensation receipt has an unexpected shape");
  }
  const libraryID = receipt.libraryID;
  if (!validLibraryID(libraryID)) throw new TypeError("Library compensation receipt has an invalid library ID");
  const createdCollectionKey = receipt.createdCollectionKey === null
    ? null
    : exactOpaqueKey(receipt.createdCollectionKey, "created collection key");
  if (!isDenseArray(receipt.createdItemKeys) || !isDenseArray(receipt.addedMemberships)) {
    throw new TypeError("Library compensation receipt arrays must be dense");
  }
  const createdItemKeys = receipt.createdItemKeys.map((key) => exactOpaqueKey(key, "created item key"));
  if (new Set(createdItemKeys).size !== createdItemKeys.length) {
    throw new Error("Library compensation receipt has duplicate created item keys");
  }
  const addedMemberships = receipt.addedMemberships.map((membership) => {
    if (!isPlainObject(membership)) throw new TypeError("Library compensation membership must be a plain object");
    const membershipKeys = Object.keys(membership);
    if (membershipKeys.length !== 2 || !membershipKeys.includes("itemKey") || !membershipKeys.includes("collectionKey")) {
      throw new TypeError("Library compensation membership has an unexpected shape");
    }
    return {
      itemKey: exactOpaqueKey(membership.itemKey, "membership item key"),
      collectionKey: exactOpaqueKey(membership.collectionKey, "membership collection key"),
    };
  });
  const identities = addedMemberships.map(({ itemKey, collectionKey }) => `${itemKey}\u0000${collectionKey}`);
  if (new Set(identities).size !== identities.length) {
    throw new Error("Library compensation receipt has duplicate memberships");
  }
  if (createdCollectionKey !== null
    && addedMemberships.some(({ collectionKey }) => collectionKey !== createdCollectionKey)) {
    throw new Error("Library compensation receipt memberships target an unexpected collection");
  }
  return { libraryID, createdCollectionKey, createdItemKeys, addedMemberships };
}

async function validateSavedNativeObject(
  zotero: ZoteroLibraryImportRuntime,
  kind: "item" | "collection",
  object: unknown,
  saveResult: unknown,
  libraryID: LibraryID,
  existingIDs: Set<number | string>,
  existingKeys: ReadonlySet<string>,
): Promise<{ id: number | string; key: string }> {
  const label = kind === "item" ? "Created Zotero item" : "Created Zotero collection";
  let id: number | string;
  if (validNativeID(saveResult)) {
    id = saveResult;
  }
  else {
    try {
      id = nativeID(object, label);
    }
    catch (error) {
      throw new ManualInspectionRequiredError(
        `could not recover ${label} native ID after save: ${boundedError(error)}`,
      );
    }
  }
  if (existingIDs.has(id)) {
    throw new ManualInspectionRequiredError(
      `${label} reused pre-existing native ID ${String(id)}; automatic cleanup is unsafe`,
    );
  }
  try {
    const key = nativeKey(object, label);
    if (!sameLibrary(object, libraryID)) {
      throw new Error(`${label} does not belong to the reviewed library`);
    }
    if (existingKeys.has(key)) throw new Error(`Zotero returned a duplicate created ${kind} key`);
    existingIDs.add(id);
    return { id, key };
  }
  catch (validationError) {
    await cleanupInvalidSavedNativeObject(zotero, kind, object, id, validationError);
    throw validationError;
  }
}

async function cleanupInvalidSavedNativeObject(
  zotero: ZoteroLibraryImportRuntime,
  kind: "item" | "collection",
  object: unknown,
  id: number | string,
  validationError: unknown,
): Promise<void> {
  const label = kind === "item" ? "created item" : "created collection";
  let before: unknown;
  try {
    before = await getNativeObjectByID(zotero, kind, id);
  }
  catch (error) {
    throw new ManualInspectionRequiredError(
      `could not prove exact ${label} identity before cleanup: ${boundedError(error)}`,
    );
  }
  if (before !== object) {
    throw new ManualInspectionRequiredError(
      `native ID ${String(id)} did not resolve to the exact invalid ${label}; no erase was attempted`,
    );
  }

  let eraseError: unknown = null;
  try {
    await nativeMethod(object, "eraseTx", `Invalid Zotero ${label} eraser`)();
  }
  catch (error) {
    eraseError = error;
  }

  let after: unknown;
  try {
    after = await getNativeObjectByID(zotero, kind, id);
  }
  catch (error) {
    throw new ManualInspectionRequiredError(
      `could not verify invalid ${label} cleanup: ${boundedError(error)}`,
    );
  }
  if (after !== null && after !== undefined) {
    throw new ManualInspectionRequiredError(
      `invalid ${label} still exists after cleanup (${boundedError(eraseError ?? validationError)})`,
    );
  }
}

async function getNativeObjectByID(
  zotero: ZoteroLibraryImportRuntime,
  kind: "item" | "collection",
  id: number | string,
): Promise<unknown | null> {
  const store = kind === "item" ? zotero.Items : zotero.Collections;
  if (store?.getAsync) return (await store.getAsync.call(store, id)) ?? null;
  if (store?.get) return store.get.call(store, id) ?? null;
  throw new Error(`Zotero ${kind} numeric identity lookup is unavailable`);
}

async function getNativeItem(
  zotero: ZoteroLibraryImportRuntime,
  libraryID: LibraryID,
  key: string,
): Promise<unknown | null> {
  const items = zotero.Items;
  if (items?.getByLibraryAndKeyAsync) {
    return (await items.getByLibraryAndKeyAsync.call(items, libraryID, key)) ?? null;
  }
  if (items?.getByLibraryAndKey) {
    return items.getByLibraryAndKey.call(items, libraryID, key) ?? null;
  }
  throw new Error("Zotero item lookup is unavailable for compensation");
}

async function getNativeCollection(
  zotero: ZoteroLibraryImportRuntime,
  libraryID: LibraryID,
  key: string,
): Promise<unknown | null> {
  const collections = zotero.Collections;
  if (collections?.getByLibraryAndKeyAsync) {
    return (await collections.getByLibraryAndKeyAsync.call(collections, libraryID, key)) ?? null;
  }
  if (collections?.getByLibraryAndKey) {
    return collections.getByLibraryAndKey.call(collections, libraryID, key) ?? null;
  }
  throw new Error("Zotero collection lookup is unavailable for compensation");
}

function assertNativeIdentity(
  object: unknown,
  libraryID: LibraryID,
  key: string,
  label: string,
): void {
  if (!sameLibrary(object, libraryID) || nativeKey(object, label) !== key) {
    throw new Error(`${label} did not exactly match the compensation receipt`);
  }
}

function nativeField(item: unknown, field: string): string {
  const value = nativeMethod(item, "getField", "Loaded Zotero item field reader")(field);
  return typeof value === "string" ? value : value === null || value === undefined ? "" : String(value);
}

function nativeKey(object: unknown, label: string): string {
  const key = safeProperty(object, "key");
  return exactOpaqueKey(key, `${label} key`);
}

function nativeVersion(object: unknown, label: string): number {
  const version = safeProperty(object, "version");
  if (typeof version !== "number" || !Number.isSafeInteger(version) || version < 0) {
    throw new Error(`${label} version is unavailable or invalid`);
  }
  return version;
}

function nativeID(object: unknown, label: string): number | string {
  const id = safeProperty(object, "id") ?? safeProperty(object, "itemID")
    ?? safeProperty(object, "collectionID");
  if (!validNativeID(id)) {
    throw new Error(`${label} native ID is unavailable`);
  }
  return id;
}

function validNativeID(value: unknown): value is number | string {
  return (typeof value === "number" && Number.isSafeInteger(value))
    || (typeof value === "string" && Boolean(value));
}

function nativeDeleted(object: unknown): boolean {
  return safeProperty(object, "deleted") === true;
}

function sameLibrary(object: unknown, libraryID: LibraryID): boolean {
  return safeProperty(object, "libraryID") === libraryID;
}

function nativeStringProperty(object: unknown, key: string): string {
  const value = safeProperty(object, key);
  if (typeof value !== "string") throw new Error(`Zotero ${key} is unavailable`);
  return value;
}

function setNativeProperty(object: unknown, key: string, value: unknown): void {
  if (!isObject(object)) throw new Error(`Zotero object is unavailable while setting ${key}`);
  object[key] = value;
}

function nativeMethod(
  object: unknown,
  name: string,
  label: string,
): (...args: unknown[]) => any {
  if (!isObject(object) && typeof object !== "function") throw new Error(`${label} is unavailable`);
  const candidate = (object as UnknownRecord)[name];
  if (typeof candidate !== "function") throw new Error(`${label} is unavailable`);
  return candidate.bind(object);
}

function optionalMethod(object: unknown, name: string): ((...args: unknown[]) => any) | null {
  if (!isObject(object) && typeof object !== "function") return null;
  const candidate = (object as UnknownRecord)[name];
  return typeof candidate === "function" ? candidate.bind(object) : null;
}

function safeProperty(object: unknown, key: string): unknown {
  if (!isObject(object) && typeof object !== "function") return undefined;
  return (object as UnknownRecord)[key];
}

function isObject(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null;
}

function isPlainObject(value: unknown): value is UnknownRecord {
  if (!isObject(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function isDenseArray(value: unknown): value is unknown[] {
  if (!Array.isArray(value)) return false;
  for (let index = 0; index < value.length; index += 1) {
    if (!Object.prototype.hasOwnProperty.call(value, index)) return false;
  }
  return true;
}

function exactOpaqueKey(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()
    || /[\p{Cc}\p{Cf}\u2028\u2029]/u.test(value)
    || [...value].length > 1_000) {
    throw new Error(`${label} is unavailable or invalid`);
  }
  return value;
}

function validLibraryID(value: unknown): value is LibraryID {
  return (typeof value === "number" && Number.isSafeInteger(value))
    || (typeof value === "string" && Boolean(value.trim())
      && !/[\p{Cc}\p{Cf}\u2028\u2029]/u.test(value)
      && [...value].length <= 1_000);
}

function cleanText(value: unknown): string {
  return typeof value === "string" ? value.normalize("NFC").trim() : "";
}

function normalizedText(value: string): string {
  return value.normalize("NFKC").trim().replace(/\s+/gu, " ").toLowerCase();
}

function normalizedName(value: string): string {
  return value.normalize("NFC").trim();
}

function boundedError(error: unknown): string {
  let message = "Zotero operation failed";
  try {
    if (error instanceof Error && error.message) message = error.message;
    else if (typeof error === "string" && error) message = error;
    else if (error !== null && error !== undefined) message = String(error);
  }
  catch {
    // Keep the static fallback for hostile host values.
  }
  return [...message.replace(/[\p{Cc}\p{Cf}\u2028\u2029]/gu, "�").normalize("NFC").trim()]
    .slice(0, MAX_ERROR_CODE_POINTS)
    .join("") || "Zotero operation failed";
}

async function preflightDigest(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const subtle = globalThis.crypto?.subtle;
  if (subtle) {
    const digest = new Uint8Array(await subtle.digest("SHA-256", bytes));
    return `zotero-native-${[...digest].map((byte) => byte.toString(16).padStart(2, "0")).join("")}`;
  }
  try {
    return `zotero-native-${sha256Bytes(bytes)}`;
  }
  catch {
    throw new Error("Secure Zotero preflight digest capability is unavailable");
  }
}

function secureChoiceId(): string {
  const crypto = globalThis.crypto;
  if (!crypto?.getRandomValues) throw new Error("Secure random capability is unavailable");
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return `zotero-choice-${[...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("")}`;
}
