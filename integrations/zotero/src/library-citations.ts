const DEFAULT_TTL_MS = 30 * 60 * 1_000;
const MAX_REQUESTS = 50;
const MAX_QUERY_TEXT_CODE_POINTS = 20_000;
const MAX_SHORT_TEXT_CODE_POINTS = 1_000;
const MAX_TITLE_CODE_POINTS = 10_000;
const MAX_CREATORS = 50;
const MAX_CANDIDATES = 50;

const UNSAFE_TEXT = /[\p{Cc}\p{Cf}\u2028\u2029]/u;
const DOI = /^10\.\d{4,9}\/[\-._;()/:a-z0-9]+$/iu;
const ARXIV = /^(\d{4}\.\d{4,5}|[a-z][a-z.-]*\/[0-9]{7})(?:v[0-9]+)?$/iu;

export type SupportedBibliographicItemType =
  | "journalArticle" | "conferencePaper" | "book" | "bookSection"
  | "report" | "thesis" | "preprint";

export interface CitationQuery {
  clientRef: string;
  citation?: string;
  doi?: string;
  arxiv?: string;
  title?: string;
  year?: number;
  creators?: readonly string[];
}

export interface BibliographicMetadata {
  itemType: SupportedBibliographicItemType;
  title: string;
  creators: readonly Readonly<{
    creatorType: "author";
    firstName?: string;
    lastName?: string;
    name?: string;
  }>[];
  date: string;
  DOI: string;
  url: string;
  publicationTitle: string;
  archive: string;
  archiveLocation: string;
}

export interface CitationResolver {
  resolve(
    scope: { libraryID: number | string },
    requests: readonly CitationQuery[],
  ): Promise<readonly ResolvedCitation[]>;
}

export interface ResolvedCitation {
  clientRef: string;
  status: "create" | "reuse" | "ambiguous" | "unresolved";
  candidates: readonly Readonly<{
    choiceId: string;
    metadata: BibliographicMetadata | null;
    localItemKey: string | null;
    localItemVersion: number | null;
    provenance: string;
  }>[];
  reason: string;
}

export interface BoundCitationCapability {
  capabilityId: string;
  batchId: string;
  requestIndex: number;
  libraryID: number | string;
  threadId: string;
  resolverDigest: string;
  expiresAtMs: number;
  resolution: ResolvedCitation;
}

export interface CitationCapabilityScope {
  threadId: string;
  libraryID: number | string;
}

export interface CitationLookupBatch {
  batchId: string;
  scope: CitationCapabilityScope;
  results: readonly Readonly<{
    clientRef: string;
    capabilityId: string;
    resolution: ResolvedCitation;
  }>[];
  expiresAtMs: number;
}

export interface CitationRegistryOptions {
  nowMs?: () => number;
  createId?: () => string;
  ttlMs?: number;
  maxRequests?: number;
}

interface StoredBatch {
  id: string;
  scope: CitationCapabilityScope;
  capabilityIds: readonly string[];
  expiresAtMs: number;
}

type UnknownRecord = Record<string, unknown>;

/**
 * Converts common DOI representations to one case-insensitive identity.
 * Invalid or unsafe input returns null; callers must not treat an arbitrary URL
 * as a DOI.
 */
export function canonicalDOI(value: string): string | null {
  if (typeof value !== "string" || UNSAFE_TEXT.test(value)) return null;
  let candidate = value.trim();
  candidate = candidate.replace(/^doi\s*:\s*/iu, "");
  candidate = candidate.replace(/^(?:(?:https?:)?\/\/)?(?:dx\.)?doi\.org\//iu, "");
  candidate = candidate.replace(/[?#].*$/u, "");
  candidate = candidate.replace(/[\s\]\},;:.]+$/u, "");
  candidate = candidate.toLowerCase();
  return DOI.test(candidate) ? candidate : null;
}

/** Converts old/new arXiv references, URLs, versions, and PDF links to one ID. */
export function canonicalArxivID(value: string): string | null {
  if (typeof value !== "string" || UNSAFE_TEXT.test(value)) return null;
  let candidate = value.trim();
  candidate = candidate.replace(/^(?:(?:https?:)?\/\/)?(?:export\.)?arxiv\.org\/(?:abs|pdf)\//iu, "");
  candidate = candidate.replace(/^arxiv\s*:\s*/iu, "");
  candidate = candidate.replace(/[?#].*$/u, "");
  candidate = candidate.replace(/\.pdf$/iu, "");
  const matched = ARXIV.exec(candidate);
  return matched?.[1]?.toLowerCase() ?? null;
}

/**
 * Computes a stable SHA-256 over the allowlisted bibliographic representation.
 * Metadata is validated and normalized before serializing, so object-key order
 * and mutable caller-owned objects cannot affect a bound candidate later.
 */
export function bibliographicDigest(metadata: BibliographicMetadata): string {
  return digestText(JSON.stringify(digestableMetadata(normalizeMetadata(metadata))));
}

/**
 * In-memory, subject-bound capability registry for citation candidates.
 * It deliberately has no persistence or Zotero host dependency.
 */
export class CitationCandidateRegistry {
  private readonly nowMs: () => number;
  private readonly createId: () => string;
  private readonly ttlMs: number;
  private readonly maxRequests: number;
  private readonly capabilities = new Map<string, BoundCitationCapability>();
  private readonly batches = new Map<string, StoredBatch>();

  constructor(
    private readonly resolver: CitationResolver,
    options: CitationRegistryOptions = {},
  ) {
    this.nowMs = options.nowMs ?? (() => Date.now());
    this.createId = options.createId ?? (() => defaultOpaqueId());
    this.ttlMs = boundedPositiveInteger(options.ttlMs, DEFAULT_TTL_MS, DEFAULT_TTL_MS, "ttlMs");
    this.maxRequests = boundedPositiveInteger(options.maxRequests, MAX_REQUESTS, MAX_REQUESTS, "maxRequests");
  }

  async lookup(
    scope: CitationCapabilityScope,
    requests: readonly CitationQuery[],
  ): Promise<CitationLookupBatch> {
    const normalizedScope = normalizeScope(scope);
    if (!Array.isArray(requests)) throw new TypeError("Citation requests must be an array");
    if (requests.length === 0) throw new RangeError("A citation lookup requires at least 1 request");
    if (requests.length > this.maxRequests) {
      throw new RangeError(`A citation lookup accepts at most ${this.maxRequests} requests`);
    }
    const initialNow = this.currentTime();
    this.sweepExpired(initialNow);
    const normalizedRequests = requests.map((request, index) => normalizeQuery(request, index));
    const rawResolutions = await this.resolver.resolve(
      { libraryID: normalizedScope.libraryID },
      cloneQueries(normalizedRequests),
    );
    if (!Array.isArray(rawResolutions) || rawResolutions.length !== normalizedRequests.length) {
      throw new Error("Citation resolver must return exactly one resolution for every request");
    }
    const resolutions = rawResolutions.map((resolution, index) => (
      normalizeResolution(resolution, normalizedRequests[index]!.clientRef, index)
    ));

    const completionNow = this.currentTime();
    this.sweepExpired(completionNow);
    const reservedIds = new Set<string>();
    const batchId = this.nextOpaqueId(reservedIds);
    reservedIds.add(batchId);
    const expiresAtMs = completionNow + this.ttlMs;
    const capabilityIds: string[] = [];
    const stagedCapabilities = resolutions.map((resolution, requestIndex) => {
      const capabilityId = this.nextOpaqueId(reservedIds);
      reservedIds.add(capabilityId);
      const bound: BoundCitationCapability = {
        capabilityId,
        batchId,
        requestIndex,
        libraryID: normalizedScope.libraryID,
        threadId: normalizedScope.threadId,
        resolverDigest: digestResolution(resolution),
        expiresAtMs,
        resolution,
      };
      capabilityIds.push(capabilityId);
      return bound;
    });
    const stagedBatch: StoredBatch = {
      id: batchId,
      scope: cloneScope(normalizedScope),
      capabilityIds,
      expiresAtMs,
    };
    const results = stagedCapabilities.map((capability) => ({
      clientRef: capability.resolution.clientRef,
      capabilityId: capability.capabilityId,
      resolution: cloneResolution(capability.resolution),
    }));

    for (const capability of stagedCapabilities) {
      this.capabilities.set(capability.capabilityId, capability);
    }
    this.batches.set(batchId, stagedBatch);

    return {
      batchId,
      scope: cloneScope(normalizedScope),
      results,
      expiresAtMs,
    };
  }

  resolveCapability(scope: CitationCapabilityScope, capabilityId: string): BoundCitationCapability {
    const normalizedScope = normalizeScope(scope);
    if (typeof capabilityId !== "string" || !capabilityId) {
      throw new TypeError("Citation capability ID must be a non-empty string");
    }
    const now = this.currentTime();
    const directCapability = this.capabilities.get(capabilityId);
    if (directCapability && now >= directCapability.expiresAtMs) {
      this.deleteBatch(directCapability.batchId);
      this.capabilities.delete(capabilityId);
      throw new Error("Citation capability has expired");
    }
    this.sweepExpired(now);
    const capability = this.capabilities.get(capabilityId);
    if (!capability) throw new Error("Unknown citation capability");
    if (capability.threadId !== normalizedScope.threadId) {
      throw new Error("Citation capability belongs to a different thread");
    }
    if (capability.libraryID !== normalizedScope.libraryID) {
      throw new Error("Citation capability belongs to a different library");
    }
    return cloneCapability(capability);
  }

  resolveCompleteBatch(
    scope: CitationCapabilityScope,
    capabilityIds: readonly string[],
  ): readonly BoundCitationCapability[] {
    if (!Array.isArray(capabilityIds) || capabilityIds.length === 0) {
      throw new Error("A complete citation batch requires capability IDs");
    }
    if (new Set(capabilityIds).size !== capabilityIds.length) {
      throw new Error("Citation capability IDs must be unique; duplicate IDs are not allowed");
    }
    const capabilities = capabilityIds.map((capabilityId) => this.resolveCapability(scope, capabilityId));
    const batchId = capabilities[0]!.batchId;
    if (capabilities.some((capability) => capability.batchId !== batchId)) {
      throw new Error("Citation capabilities must belong to one batch");
    }
    const batch = this.batches.get(batchId);
    if (!batch || this.currentTime() >= batch.expiresAtMs) {
      throw new Error("Citation capability batch has expired");
    }
    if (batch.scope.threadId !== capabilities[0]!.threadId || batch.scope.libraryID !== capabilities[0]!.libraryID) {
      throw new Error("Citation capability batch subject does not match its capabilities");
    }
    if (batch.capabilityIds.length !== capabilityIds.length
      || batch.capabilityIds.some((id) => !capabilityIds.includes(id))) {
      throw new Error("Citation capability IDs must be the exact complete batch");
    }
    return capabilities
      .sort((left, right) => left.requestIndex - right.requestIndex)
      .map(cloneCapability);
  }

  private nextOpaqueId(reservedIds: ReadonlySet<string> = new Set()): string {
    for (let attempts = 0; attempts < 100; attempts += 1) {
      const id = this.createId();
      if (typeof id !== "string" || !id || UNSAFE_TEXT.test(id) || id.length > MAX_SHORT_TEXT_CODE_POINTS) {
        throw new Error("Citation capability ID factory returned an invalid opaque ID");
      }
      if (!reservedIds.has(id) && !this.capabilities.has(id) && !this.batches.has(id)) return id;
    }
    throw new Error("Citation capability ID factory produced duplicate opaque IDs");
  }

  private currentTime(): number {
    const now = this.nowMs();
    if (!Number.isFinite(now)) throw new Error("Citation registry clock returned an invalid time");
    return now;
  }

  private sweepExpired(now: number): void {
    for (const batch of this.batches.values()) {
      if (now >= batch.expiresAtMs) this.deleteBatch(batch.id);
    }
    for (const [capabilityId, capability] of this.capabilities) {
      if (now >= capability.expiresAtMs) this.capabilities.delete(capabilityId);
    }
  }

  private deleteBatch(batchId: string): void {
    const batch = this.batches.get(batchId);
    this.batches.delete(batchId);
    if (!batch) return;
    for (const capabilityId of batch.capabilityIds) this.capabilities.delete(capabilityId);
  }
}

function normalizeScope(scope: CitationCapabilityScope): CitationCapabilityScope {
  if (!isPlainRecord(scope)) throw new TypeError("Citation capability scope must be an object");
  requireExactKeys(scope, ["threadId", "libraryID"], "Citation capability scope");
  requireRequiredKeys(scope, ["threadId", "libraryID"], "Citation capability scope");
  const threadId = normalizeText(scope.threadId, "scope.threadId", MAX_SHORT_TEXT_CODE_POINTS);
  const libraryID = scope.libraryID;
  if (typeof libraryID === "string") {
    return { threadId, libraryID: normalizeText(libraryID, "scope.libraryID", MAX_SHORT_TEXT_CODE_POINTS) };
  }
  if (typeof libraryID !== "number" || !Number.isSafeInteger(libraryID)) {
    throw new TypeError("scope.libraryID must be a string or safe integer");
  }
  return { threadId, libraryID };
}

function normalizeQuery(value: CitationQuery, index: number): CitationQuery {
  if (!isPlainRecord(value)) throw new TypeError(`Citation request ${index} must be an object`);
  requireExactKeys(value, ["clientRef", "citation", "doi", "arxiv", "title", "year", "creators"], `Citation request ${index}`);
  const clientRef = normalizeText(value.clientRef, `Citation request ${index}.clientRef`, MAX_SHORT_TEXT_CODE_POINTS);
  const citation = optionalText(value.citation, `Citation request ${index}.citation`, MAX_QUERY_TEXT_CODE_POINTS);
  const title = optionalText(value.title, `Citation request ${index}.title`, MAX_TITLE_CODE_POINTS);
  const doiInput = optionalText(value.doi, `Citation request ${index}.doi`, MAX_SHORT_TEXT_CODE_POINTS);
  const arxivInput = optionalText(value.arxiv, `Citation request ${index}.arxiv`, MAX_SHORT_TEXT_CODE_POINTS);
  const normalizedDOI = doiInput === undefined ? null : canonicalDOI(doiInput);
  const normalizedArxiv = arxivInput === undefined ? null : canonicalArxivID(arxivInput);
  if (doiInput !== undefined && !normalizedDOI) throw new TypeError(`Citation request ${index}.doi is not a valid DOI`);
  if (arxivInput !== undefined && !normalizedArxiv) throw new TypeError(`Citation request ${index}.arxiv is not a valid arXiv ID`);
  const doi = normalizedDOI ?? undefined;
  const arxiv = normalizedArxiv ?? undefined;
  let year: number | undefined;
  if (value.year !== undefined) {
    if (!Number.isInteger(value.year) || value.year < 1_000 || value.year > 9_999) {
      throw new TypeError(`Citation request ${index}.year must be a four-digit year`);
    }
    year = value.year;
  }
  let creators: readonly string[] | undefined;
  if (value.creators !== undefined) {
    if (!Array.isArray(value.creators) || value.creators.length > MAX_CREATORS) {
      throw new TypeError(`Citation request ${index}.creators must contain at most ${MAX_CREATORS} authors`);
    }
    creators = value.creators.map((creator, creatorIndex) => normalizeText(
      creator,
      `Citation request ${index}.creators[${creatorIndex}]`,
      MAX_SHORT_TEXT_CODE_POINTS,
    ));
  }
  if (citation === undefined && doi === undefined && arxiv === undefined && title === undefined) {
    throw new TypeError(`Citation request ${index} needs a citation, DOI, arXiv ID, or title`);
  }
  return {
    clientRef,
    ...(citation === undefined ? {} : { citation }),
    ...(doi === undefined ? {} : { doi }),
    ...(arxiv === undefined ? {} : { arxiv }),
    ...(title === undefined ? {} : { title }),
    ...(year === undefined ? {} : { year }),
    ...(creators === undefined ? {} : { creators: [...creators] }),
  };
}

function normalizeResolution(value: unknown, expectedClientRef: string, index: number): ResolvedCitation {
  if (!isPlainRecord(value)) throw new TypeError(`Citation resolver result ${index} must be an object`);
  requireExactKeys(value, ["clientRef", "status", "candidates", "reason"], `Citation resolver result ${index}`);
  requireRequiredKeys(value, ["clientRef", "status", "candidates", "reason"], `Citation resolver result ${index}`);
  const clientRef = normalizeText(value.clientRef, `Citation resolver result ${index}.clientRef`, MAX_SHORT_TEXT_CODE_POINTS);
  if (clientRef !== expectedClientRef) {
    throw new Error(`Citation resolver result ${index} has the wrong clientRef`);
  }
  if (value.status !== "create" && value.status !== "reuse" && value.status !== "ambiguous" && value.status !== "unresolved") {
    throw new TypeError(`Citation resolver result ${index}.status is unsupported`);
  }
  if (!Array.isArray(value.candidates) || value.candidates.length > MAX_CANDIDATES) {
    throw new TypeError(`Citation resolver result ${index}.candidates must contain at most ${MAX_CANDIDATES} entries`);
  }
  return {
    clientRef,
    status: value.status,
    candidates: value.candidates.map((candidate, candidateIndex) => normalizeCandidate(candidate, index, candidateIndex)),
    reason: normalizeText(value.reason, `Citation resolver result ${index}.reason`, MAX_QUERY_TEXT_CODE_POINTS),
  };
}

function normalizeCandidate(value: unknown, resultIndex: number, candidateIndex: number): ResolvedCitation["candidates"][number] {
  const label = `Citation resolver result ${resultIndex}.candidates[${candidateIndex}]`;
  if (!isPlainRecord(value)) throw new TypeError(`${label} must be an object`);
  requireExactKeys(value, ["choiceId", "metadata", "localItemKey", "localItemVersion", "provenance"], label);
  requireRequiredKeys(value, ["choiceId", "metadata", "localItemKey", "localItemVersion", "provenance"], label);
  const metadata = value.metadata === null ? null : normalizeMetadata(value.metadata);
  const localItemKey = value.localItemKey === null
    ? null
    : normalizeText(value.localItemKey, `${label}.localItemKey`, MAX_SHORT_TEXT_CODE_POINTS);
  let localItemVersion: number | null;
  if (value.localItemVersion === null) localItemVersion = null;
  else if (typeof value.localItemVersion === "number" && Number.isSafeInteger(value.localItemVersion) && value.localItemVersion >= 0) {
    localItemVersion = value.localItemVersion;
  }
  else throw new TypeError(`${label}.localItemVersion must be a non-negative safe integer or null`);
  return {
    choiceId: normalizeText(value.choiceId, `${label}.choiceId`, MAX_SHORT_TEXT_CODE_POINTS),
    metadata,
    localItemKey,
    localItemVersion,
    provenance: normalizeText(value.provenance, `${label}.provenance`, MAX_SHORT_TEXT_CODE_POINTS),
  };
}

function normalizeMetadata(value: unknown): BibliographicMetadata {
  if (!isPlainRecord(value)) throw new TypeError("Citation metadata must be an object");
  requireExactKeys(value, [
    "itemType", "title", "creators", "date", "DOI", "url", "publicationTitle", "archive", "archiveLocation",
  ], "Citation metadata");
  requireRequiredKeys(value, [
    "itemType", "title", "creators", "date", "DOI", "url", "publicationTitle", "archive", "archiveLocation",
  ], "Citation metadata");
  if (!isSupportedItemType(value.itemType)) throw new TypeError("Citation metadata item type is unsupported");
  if (!Array.isArray(value.creators) || value.creators.length > MAX_CREATORS) {
    throw new TypeError(`Citation metadata creators must contain at most ${MAX_CREATORS} authors`);
  }
  const DOIValue = normalizeOptionalMetadataText(value.DOI, "Citation metadata.DOI", MAX_SHORT_TEXT_CODE_POINTS);
  const archiveLocation = normalizeOptionalMetadataText(
    value.archiveLocation,
    "Citation metadata.archiveLocation",
    MAX_SHORT_TEXT_CODE_POINTS,
  );
  return {
    itemType: value.itemType,
    title: normalizeText(value.title, "Citation metadata.title", MAX_TITLE_CODE_POINTS),
    creators: value.creators.map((creator, index) => normalizeCreator(creator, index)),
    date: normalizeOptionalMetadataText(value.date, "Citation metadata.date", MAX_SHORT_TEXT_CODE_POINTS),
    DOI: DOIValue ? canonicalDOI(DOIValue) ?? DOIValue.toLowerCase() : "",
    url: normalizeOptionalMetadataText(value.url, "Citation metadata.url", MAX_QUERY_TEXT_CODE_POINTS),
    publicationTitle: normalizeOptionalMetadataText(
      value.publicationTitle,
      "Citation metadata.publicationTitle",
      MAX_TITLE_CODE_POINTS,
    ),
    archive: normalizeOptionalMetadataText(value.archive, "Citation metadata.archive", MAX_SHORT_TEXT_CODE_POINTS),
    archiveLocation: archiveLocation ? canonicalArxivID(archiveLocation) ?? archiveLocation : "",
  };
}

function normalizeCreator(value: unknown, index: number): BibliographicMetadata["creators"][number] {
  const label = `Citation metadata.creators[${index}]`;
  if (!isPlainRecord(value)) throw new TypeError(`${label} must be an object`);
  requireExactKeys(value, ["creatorType", "firstName", "lastName", "name"], label);
  requireRequiredKeys(value, ["creatorType"], label);
  if (value.creatorType !== "author") throw new TypeError(`${label} must be an author creator`);
  const firstName = optionalText(value.firstName, `${label}.firstName`, MAX_SHORT_TEXT_CODE_POINTS);
  const lastName = optionalText(value.lastName, `${label}.lastName`, MAX_SHORT_TEXT_CODE_POINTS);
  const name = optionalText(value.name, `${label}.name`, MAX_SHORT_TEXT_CODE_POINTS);
  if (firstName === undefined && lastName === undefined && name === undefined) {
    throw new TypeError(`${label} needs a name`);
  }
  return {
    creatorType: "author",
    ...(firstName === undefined ? {} : { firstName }),
    ...(lastName === undefined ? {} : { lastName }),
    ...(name === undefined ? {} : { name }),
  };
}

function digestableMetadata(metadata: BibliographicMetadata): unknown {
  return {
    itemType: metadata.itemType,
    title: metadata.title,
    creators: metadata.creators.map((creator) => ({
      creatorType: creator.creatorType,
      ...(creator.firstName === undefined ? {} : { firstName: creator.firstName }),
      ...(creator.lastName === undefined ? {} : { lastName: creator.lastName }),
      ...(creator.name === undefined ? {} : { name: creator.name }),
    })),
    date: metadata.date,
    DOI: metadata.DOI,
    url: metadata.url,
    publicationTitle: metadata.publicationTitle,
    archive: metadata.archive,
    archiveLocation: metadata.archiveLocation,
  };
}

function digestResolution(resolution: ResolvedCitation): string {
  return digestText(JSON.stringify({
    clientRef: resolution.clientRef,
    status: resolution.status,
    candidates: resolution.candidates.map((candidate) => ({
      choiceId: candidate.choiceId,
      metadataDigest: candidate.metadata === null ? null : bibliographicDigest(candidate.metadata),
      localItemKey: candidate.localItemKey,
      localItemVersion: candidate.localItemVersion,
      provenance: candidate.provenance,
    })),
    reason: resolution.reason,
  }));
}

function cloneQueries(queries: readonly CitationQuery[]): CitationQuery[] {
  return queries.map((query) => ({
    ...query,
    ...(query.creators === undefined ? {} : { creators: [...query.creators] }),
  }));
}

function cloneScope(scope: CitationCapabilityScope): CitationCapabilityScope {
  return { threadId: scope.threadId, libraryID: scope.libraryID };
}

function cloneMetadata(metadata: BibliographicMetadata): BibliographicMetadata {
  return {
    ...metadata,
    creators: metadata.creators.map((creator) => ({ ...creator })),
  };
}

function cloneResolution(resolution: ResolvedCitation): ResolvedCitation {
  return {
    ...resolution,
    candidates: resolution.candidates.map((candidate) => ({
      ...candidate,
      metadata: candidate.metadata === null ? null : cloneMetadata(candidate.metadata),
    })),
  };
}

function cloneCapability(capability: BoundCitationCapability): BoundCitationCapability {
  return {
    ...capability,
    resolution: cloneResolution(capability.resolution),
  };
}

function normalizeText(value: unknown, label: string, maxCodePoints: number): string {
  if (typeof value !== "string") throw new TypeError(`${label} must be a string`);
  if (UNSAFE_TEXT.test(value)) throw new TypeError(`${label} contains unsafe control or directional text`);
  if ([...value].length > maxCodePoints) throw new RangeError(`${label} is too long`);
  const normalized = value.normalize("NFC").trim();
  if (!normalized) throw new TypeError(`${label} must not be blank`);
  return normalized;
}

function optionalText(value: unknown, label: string, maxCodePoints: number): string | undefined {
  return value === undefined ? undefined : normalizeText(value, label, maxCodePoints);
}

function normalizeOptionalMetadataText(value: unknown, label: string, maxCodePoints: number): string {
  if (typeof value !== "string") throw new TypeError(`${label} must be a string`);
  if (UNSAFE_TEXT.test(value)) throw new TypeError(`${label} contains unsafe control or directional text`);
  if ([...value].length > maxCodePoints) throw new RangeError(`${label} is too long`);
  if (!value.normalize("NFC").trim()) return "";
  return normalizeText(value, label, maxCodePoints);
}

function requireExactKeys(value: UnknownRecord, allowed: readonly string[], label: string): void {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) throw new TypeError(`${label} contains unknown field ${key}`);
  }
}

function requireRequiredKeys(value: UnknownRecord, required: readonly string[], label: string): void {
  for (const key of required) {
    if (!(key in value)) throw new TypeError(`${label} is missing required field ${key}`);
  }
}

function isPlainRecord(value: unknown): value is UnknownRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function isSupportedItemType(value: unknown): value is SupportedBibliographicItemType {
  return value === "journalArticle" || value === "conferencePaper" || value === "book"
    || value === "bookSection" || value === "report" || value === "thesis" || value === "preprint";
}

function boundedPositiveInteger(value: number | undefined, fallback: number, maximum: number, label: string): number {
  if (value === undefined) return fallback;
  if (!Number.isSafeInteger(value) || value <= 0) throw new TypeError(`${label} must be a positive safe integer`);
  return Math.min(value, maximum);
}

function defaultOpaqueId(): string {
  const crypto = globalThis.crypto;
  if (!crypto?.getRandomValues) throw new Error("Secure random capability is unavailable");
  try {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return `citation-${[...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("")}`;
  }
  catch {
    throw new Error("Secure random capability is unavailable");
  }
}

function digestText(value: string): string {
  return sha256Fallback(new TextEncoder().encode(value));
}

function sha256Fallback(bytes: Uint8Array): string {
  const bitLength = bytes.length * 8;
  const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const length = BigInt(bitLength);
  for (let index = 0; index < 8; index += 1) {
    padded[padded.length - 1 - index] = Number((length >> BigInt(index * 8)) & 0xffn);
  }
  const hash = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  const words = new Uint32Array(64);
  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      const base = offset + index * 4;
      words[index] = ((padded[base]! << 24) | (padded[base + 1]! << 16) | (padded[base + 2]! << 8) | padded[base + 3]!) >>> 0;
    }
    for (let index = 16; index < 64; index += 1) {
      const x = words[index - 15]!;
      const y = words[index - 2]!;
      const small0 = rotateRight(x, 7) ^ rotateRight(x, 18) ^ (x >>> 3);
      const small1 = rotateRight(y, 17) ^ rotateRight(y, 19) ^ (y >>> 10);
      words[index] = (words[index - 16]! + small0 + words[index - 7]! + small1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = hash;
    for (let index = 0; index < 64; index += 1) {
      const big1 = rotateRight(e!, 6) ^ rotateRight(e!, 11) ^ rotateRight(e!, 25);
      const choose = (e! & f!) ^ (~e! & g!);
      const temp1 = (h! + big1 + choose + SHA256_CONSTANTS[index]! + words[index]!) >>> 0;
      const big0 = rotateRight(a!, 2) ^ rotateRight(a!, 13) ^ rotateRight(a!, 22);
      const majority = (a! & b!) ^ (a! & c!) ^ (b! & c!);
      const temp2 = (big0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d! + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }
    hash[0] = (hash[0]! + a!) >>> 0;
    hash[1] = (hash[1]! + b!) >>> 0;
    hash[2] = (hash[2]! + c!) >>> 0;
    hash[3] = (hash[3]! + d!) >>> 0;
    hash[4] = (hash[4]! + e!) >>> 0;
    hash[5] = (hash[5]! + f!) >>> 0;
    hash[6] = (hash[6]! + g!) >>> 0;
    hash[7] = (hash[7]! + h!) >>> 0;
  }
  return [...hash].map((part) => part.toString(16).padStart(8, "0")).join("");
}

function rotateRight(value: number, bits: number): number {
  return (value >>> bits) | (value << (32 - bits));
}

const SHA256_CONSTANTS = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);
