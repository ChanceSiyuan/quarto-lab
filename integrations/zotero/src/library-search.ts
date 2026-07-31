/** Pure, dependency-free metadata retrieval for bounded Zotero snapshots. */

export interface LibrarySearchCreatorInput {
  firstName?: string;
  lastName?: string;
  name?: string;
}

export interface LibrarySearchItemInput {
  _topLevel: boolean;
  key: string;
  itemType: string;
  title: string;
  creators: LibrarySearchCreatorInput[];
  date: string;
  publicationTitle: string;
  DOI: string;
  abstractNote: string;
  tags: string[];
  collections: string[];
  collectionKeys: string[];
  version: number | null;
  parentItem?: string;
  filename?: string;
  contentType?: string;
}

export interface LibrarySearchCollectionInput {
  key: string;
  name: string;
  path: string;
}

export interface LibrarySearchDocument {
  itemKey: string;
  itemType: string;
  title: string;
  creators: string[];
  date: string;
  year: number | null;
  publicationTitle: string;
  doi: string;
  abstract: string;
  tags: string[];
  collections: string[];
  collectionKeys: string[];
  collectionPaths: string[];
  attachmentKeys: string[];
  filenames: string[];
  version: number | null;
}

export type LibrarySearchField =
  | "key"
  | "title"
  | "creators"
  | "doi"
  | "tags"
  | "collections"
  | "publication"
  | "filename"
  | "year"
  | "abstract";

export interface LibrarySearchFilters {
  tags?: readonly string[];
  collectionKeys?: readonly string[];
  itemTypes?: readonly string[];
  yearFrom?: number;
  yearTo?: number;
}

export interface LibrarySearchOptions extends LibrarySearchFilters {
  limit?: number;
}

export interface LibraryMetadataSearchHit {
  itemKey: string;
  title: string;
  creators: string[];
  date: string;
  year: number | null;
  doi: string;
  itemType: string;
  tags: string[];
  collectionKeys: string[];
  collectionPaths: string[];
  attachmentKeys: string[];
  filenames: string[];
  score: number;
  matchedFields: LibrarySearchField[];
}

interface IndexedDocument {
  document: LibrarySearchDocument;
  fieldTokens: Record<LibrarySearchField, string[]>;
  fieldTermCounts: Record<LibrarySearchField, Map<string, number>>;
  normalized: Record<LibrarySearchField, string>;
}

export interface LibraryMetadataIndex {
  sourceDocuments: LibrarySearchDocument[];
  documents: IndexedDocument[];
  documentFrequency: Map<string, number>;
  averageFieldLengths: Record<LibrarySearchField, number>;
}

const FIELDS: readonly LibrarySearchField[] = [
  "key",
  "title",
  "creators",
  "doi",
  "tags",
  "collections",
  "publication",
  "filename",
  "year",
  "abstract",
];

const FIELD_WEIGHTS: Record<LibrarySearchField, number> = {
  key: 10,
  title: 8,
  creators: 5,
  doi: 12,
  tags: 6,
  collections: 4,
  publication: 3,
  filename: 2,
  year: 2,
  abstract: 1.5,
};

const FIELD_B: Record<LibrarySearchField, number> = {
  key: 0,
  title: 0.5,
  creators: 0.5,
  doi: 0,
  tags: 0.25,
  collections: 0.35,
  publication: 0.5,
  filename: 0.4,
  year: 0,
  abstract: 0.8,
};

function normalize(value: unknown): string {
  return String(value ?? "").normalize("NFKC").toLocaleLowerCase().trim();
}

/**
 * Tokenize Latin/alphanumeric text and overlapping Han bigrams. Overlapping
 * bigrams let an unspaced CJK query match a longer title without a language-
 * specific dictionary, while NFKC makes full-width metadata searchable.
 */
export function tokenizeLibrarySearch(value: unknown): string[] {
  const text = normalize(value);
  const tokens: string[] = [];
  for (const match of text.matchAll(/\p{Script=Han}+|[\p{L}\p{N}]+/gu)) {
    const segment = match[0];
    if (/^\p{Script=Han}+$/u.test(segment)) {
      const characters = [...segment];
      if (characters.length === 1) tokens.push(characters[0]!);
      else {
        for (let index = 0; index < characters.length - 1; index += 1) {
          tokens.push(`${characters[index]}${characters[index + 1]}`);
        }
      }
    }
    else {
      tokens.push(segment);
    }
  }
  return tokens;
}

function creatorName(creator: LibrarySearchCreatorInput): string {
  return creator.name?.trim()
    || [creator.firstName, creator.lastName].filter(Boolean).join(" ").trim();
}

function parseYear(value: string): number | null {
  const match = value.match(/(?:^|\D)(\d{4})(?:\D|$)/u);
  if (!match) return null;
  const year = Number(match[1]);
  return Number.isSafeInteger(year) ? year : null;
}

function isPdfAttachment(item: LibrarySearchItemInput): boolean {
  return normalize(item.contentType) === "application/pdf"
    || normalize(item.filename).endsWith(".pdf");
}

/** Join child PDF attachment identities into their top-level citation item. */
export function aggregateLibrarySearchDocuments(
  items: readonly LibrarySearchItemInput[],
  collections: readonly LibrarySearchCollectionInput[],
): LibrarySearchDocument[] {
  const collectionPaths = new Map(collections.map((collection) => [
    collection.key,
    collection.path || collection.name,
  ]));
  const documents = new Map<string, LibrarySearchDocument>();
  for (const source of items) {
    if (!source._topLevel) continue;
    documents.set(source.key, {
      itemKey: source.key,
      itemType: source.itemType,
      title: source.title,
      creators: source.creators.map(creatorName).filter(Boolean),
      date: source.date,
      year: parseYear(source.date),
      publicationTitle: source.publicationTitle,
      doi: source.DOI,
      abstract: source.abstractNote,
      tags: [...source.tags],
      collections: [...source.collections],
      collectionKeys: [...source.collectionKeys],
      collectionPaths: source.collectionKeys
        .map((key) => collectionPaths.get(key) || "")
        .filter(Boolean),
      attachmentKeys: isPdfAttachment(source) ? [source.key] : [],
      filenames: source.filename ? [source.filename] : [],
      version: source.version,
    });
  }
  for (const source of items) {
    if (source._topLevel || !source.parentItem || !isPdfAttachment(source)) continue;
    const parent = documents.get(source.parentItem);
    if (!parent) continue;
    if (!parent.attachmentKeys.includes(source.key)) parent.attachmentKeys.push(source.key);
    if (source.filename && !parent.filenames.includes(source.filename)) {
      parent.filenames.push(source.filename);
    }
  }
  return [...documents.values()]
    .map((document) => ({
      ...document,
      attachmentKeys: [...document.attachmentKeys].sort(),
      filenames: [...document.filenames].sort((left, right) => left.localeCompare(right)),
    }))
    .sort((left, right) => left.itemKey.localeCompare(right.itemKey));
}

function fieldValues(document: LibrarySearchDocument): Record<LibrarySearchField, string> {
  return {
    key: [document.itemKey, ...document.attachmentKeys].join(" "),
    title: document.title,
    creators: document.creators.join(" "),
    doi: document.doi,
    tags: document.tags.join(" "),
    collections: [...document.collections, ...document.collectionPaths].join(" "),
    publication: document.publicationTitle,
    filename: document.filenames.join(" "),
    year: document.year === null ? "" : String(document.year),
    abstract: document.abstract,
  };
}

function termCounts(tokens: readonly string[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const token of tokens) counts.set(token, (counts.get(token) ?? 0) + 1);
  return counts;
}

export function buildLibraryMetadataIndex(
  items: readonly LibrarySearchItemInput[],
  collections: readonly LibrarySearchCollectionInput[],
): LibraryMetadataIndex {
  const sourceDocuments = aggregateLibrarySearchDocuments(items, collections);
  const documents = sourceDocuments.map((document) => {
    const values = fieldValues(document);
    const fieldTokens = Object.fromEntries(FIELDS.map((field) => [
      field,
      tokenizeLibrarySearch(values[field]),
    ])) as Record<LibrarySearchField, string[]>;
    const fieldTermCounts = Object.fromEntries(FIELDS.map((field) => [
      field,
      termCounts(fieldTokens[field]),
    ])) as Record<LibrarySearchField, Map<string, number>>;
    const normalized = Object.fromEntries(FIELDS.map((field) => [
      field,
      normalize(values[field]),
    ])) as Record<LibrarySearchField, string>;
    return { document, fieldTokens, fieldTermCounts, normalized };
  });
  const documentFrequency = new Map<string, number>();
  const fieldTotals = Object.fromEntries(FIELDS.map((field) => [field, 0])) as Record<
    LibrarySearchField,
    number
  >;
  for (const indexed of documents) {
    const terms = new Set<string>();
    for (const field of FIELDS) {
      fieldTotals[field] += indexed.fieldTokens[field].length;
      for (const token of indexed.fieldTokens[field]) terms.add(token);
    }
    for (const term of terms) {
      documentFrequency.set(term, (documentFrequency.get(term) ?? 0) + 1);
    }
  }
  const divisor = Math.max(1, documents.length);
  const averageFieldLengths = Object.fromEntries(FIELDS.map((field) => [
    field,
    fieldTotals[field] / divisor || 1,
  ])) as Record<LibrarySearchField, number>;
  return { sourceDocuments, documents, documentFrequency, averageFieldLengths };
}

function normalizedSet(values: readonly string[] | undefined): Set<string> | null {
  if (!values?.length) return null;
  return new Set(values.map(normalize).filter(Boolean));
}

export function matchesLibrarySearchFilters(
  document: LibrarySearchDocument,
  filters: LibrarySearchFilters,
): boolean {
  const tags = normalizedSet(filters.tags);
  if (tags) {
    const actual = new Set(document.tags.map(normalize));
    if ([...tags].some((tag) => !actual.has(tag))) return false;
  }
  const collectionKeys = normalizedSet(filters.collectionKeys);
  if (collectionKeys) {
    const actual = new Set(document.collectionKeys.map(normalize));
    if (![...collectionKeys].some((key) => actual.has(key))) return false;
  }
  const itemTypes = normalizedSet(filters.itemTypes);
  if (itemTypes && !itemTypes.has(normalize(document.itemType))) return false;
  if (filters.yearFrom !== undefined && (document.year === null || document.year < filters.yearFrom)) {
    return false;
  }
  if (filters.yearTo !== undefined && (document.year === null || document.year > filters.yearTo)) {
    return false;
  }
  return true;
}

function exactBoost(indexed: IndexedDocument, query: string): number {
  if (!query) return 0;
  if (indexed.normalized.doi === query) return 100;
  if (indexed.normalized.title === query) return 30;
  if (indexed.normalized.title.includes(query)) return 12;
  if (indexed.document.tags.some((tag) => normalize(tag) === query)) return 8;
  if (
    [...indexed.document.collections, ...indexed.document.collectionPaths]
      .some((collection) => normalize(collection) === query)
  ) return 5;
  return 0;
}

export function searchLibraryMetadata(
  index: LibraryMetadataIndex,
  query: string,
  options: LibrarySearchOptions = {},
): LibraryMetadataSearchHit[] {
  const normalizedQuery = normalize(query);
  const queryTerms = [...new Set(tokenizeLibrarySearch(normalizedQuery))];
  if (!normalizedQuery || !queryTerms.length) return [];
  const documentCount = index.documents.length;
  const minimumMatches = queryTerms.length === 1
    ? 1
    : Math.max(2, Math.ceil(queryTerms.length * 0.6));
  const hits: LibraryMetadataSearchHit[] = [];
  for (const indexed of index.documents) {
    const document = indexed.document;
    if (!matchesLibrarySearchFilters(document, options)) continue;
    const matchedTerms = new Set<string>();
    const matchedFields = new Set<LibrarySearchField>();
    let score = 0;
    for (const term of queryTerms) {
      let weightedFrequency = 0;
      for (const field of FIELDS) {
        const count = indexed.fieldTermCounts[field].get(term) ?? 0;
        if (!count) continue;
        matchedFields.add(field);
        const length = indexed.fieldTokens[field].length;
        const average = index.averageFieldLengths[field] || 1;
        const normalization = 1 - FIELD_B[field] + FIELD_B[field] * length / average;
        weightedFrequency += FIELD_WEIGHTS[field] * count / Math.max(0.01, normalization);
      }
      if (!weightedFrequency) continue;
      matchedTerms.add(term);
      const frequency = index.documentFrequency.get(term) ?? 0;
      const inverseDocumentFrequency = Math.log(
        1 + (documentCount - frequency + 0.5) / (frequency + 0.5),
      );
      const k1 = 1.2;
      score += inverseDocumentFrequency
        * (weightedFrequency * (k1 + 1))
        / (weightedFrequency + k1);
    }
    if (matchedTerms.size < minimumMatches) continue;
    score += exactBoost(indexed, normalizedQuery);
    hits.push({
      itemKey: document.itemKey,
      title: document.title,
      creators: [...document.creators],
      date: document.date,
      year: document.year,
      doi: document.doi,
      itemType: document.itemType,
      tags: [...document.tags],
      collectionKeys: [...document.collectionKeys],
      collectionPaths: [...document.collectionPaths],
      attachmentKeys: [...document.attachmentKeys],
      filenames: [...document.filenames],
      score: Number(score.toFixed(6)),
      matchedFields: FIELDS.filter((field) => matchedFields.has(field)),
    });
  }
  const limit = Math.max(1, Math.min(100, Math.trunc(options.limit ?? 20)));
  return hits
    .sort((left, right) => right.score - left.score || left.itemKey.localeCompare(right.itemKey))
    .slice(0, limit);
}
