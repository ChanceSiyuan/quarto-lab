/**
 * Read-only Zotero metadata import for the external literature tree.
 *
 * Zotero item keys identify records; BibTeX citekeys remain the identity used
 * by trusted QMD citations. Import never edits `ref.bib`, copies attachments,
 * or deletes a record that disappeared from a later Zotero snapshot.
 */

import { createHash } from "node:crypto";
import {
  mkdir,
  readFile,
  readdir,
  rename,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import { parse, stringify } from "yaml";

const IGNORED_ITEM_TYPES = new Set(["attachment", "note", "annotation"]);
const ARXIV_PATTERN = /(?:arXiv\s*:\s*|arXiv\.org\/abs\/)([\w.-]+(?:\/\d{7})?(?:v\d+)?)/i;

export interface ZoteroCollection {
  key: string;
  data: { name?: string; parentCollection?: string | false | null };
}

export interface ZoteroCreator {
  creatorType?: string;
  name?: string;
  firstName?: string;
  lastName?: string;
}

export interface ZoteroItem {
  key: string;
  version?: number;
  data: {
    version?: number;
    itemType?: string;
    title?: string;
    creators?: ZoteroCreator[];
    date?: string;
    abstractNote?: string;
    DOI?: string;
    extra?: string;
    ISBN?: string;
    tags?: Array<{ tag?: string }>;
    collections?: string[];
  };
}

interface CollectionPath {
  key: string;
  name: string;
  path: string;
  parentKey: string | null;
  rootKey: string;
  rootName: string;
}

interface CollectionMapping {
  name: string;
  path: string;
  topic: string;
  priority: number;
  parent_key: string | null;
  root_key: string;
}

interface ZoteroConfig {
  schema_version: number;
  mapping_strategy: string;
  default_topic: string;
  collection_map: Record<string, CollectionMapping>;
  ignored_collections: string[];
}

interface LiteratureRecord {
  schema_version: number;
  origin: string;
  materialization: string;
  zotero_import?: {
    library?: string;
    item_key?: string;
    item_version?: number;
    imported_at?: string;
    collections?: Array<{ key: string; name: string; path: string }>;
  };
  qlab?: {
    primary_collection?: string | null;
    indexed_collections?: string[];
    primary_topic?: string;
    indexed_topics?: string[];
  };
  item_type?: string;
  title?: string;
  authors?: Array<{ name?: string; first?: string; last?: string }>;
  year?: number | null;
  abstract?: string;
  tags?: string[];
  identifiers?: Record<string, string>;
  latex?: { entrypoint?: string };
  [key: string]: unknown;
}

export interface ZoteroImportReport {
  /** Number of records present in this incoming snapshot. */
  imported: number;
  /** Every retained record, including records absent from this refresh. */
  records: string[];
  duplicateCandidates: Record<string, string[]>;
}

export interface ZoteroClientOptions {
  baseUrl?: string;
  library?: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}

export class ZoteroClient {
  readonly baseUrl: string;
  readonly library: string;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;

  constructor(options: ZoteroClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:23119/api").replace(/\/+$/u, "");
    this.library = (options.library ?? "users/0").replace(/^\/+|\/+$/gu, "");
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.timeoutMs = options.timeoutMs ?? 30_000;
  }

  private async request(endpoint: string, query: Record<string, string | number> = {}): Promise<Buffer> {
    const url = new URL(`${this.baseUrl}/${this.library}/${endpoint.replace(/^\/+/, "")}`);
    for (const [name, value] of Object.entries(query)) url.searchParams.set(name, String(value));
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetchImpl(url, {
        headers: { "Zotero-API-Version": "3", "User-Agent": "research-loop-literature/0.1" },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return Buffer.from(await response.arrayBuffer());
    } catch (error) {
      throw new Error(
        "Cannot reach Zotero's local API at 127.0.0.1:23119. Open Zotero and enable its local API before retrying.",
        { cause: error },
      );
    } finally {
      clearTimeout(timeout);
    }
  }

  private async paged(endpoint: string): Promise<Array<Record<string, unknown>>> {
    const results: Array<Record<string, unknown>> = [];
    const limit = 100;
    for (let start = 0; ; start += limit) {
      const parsed: unknown = JSON.parse((await this.request(endpoint, { start, limit })).toString("utf8"));
      if (!Array.isArray(parsed)) throw new Error(`Unexpected Zotero response for ${endpoint}`);
      results.push(...(parsed as Array<Record<string, unknown>>));
      if (parsed.length < limit) return results;
    }
  }

  async collections(): Promise<ZoteroCollection[]> {
    return (await this.paged("collections")) as unknown as ZoteroCollection[];
  }

  async topItems(): Promise<ZoteroItem[]> {
    return (await this.paged("items/top")) as unknown as ZoteroItem[];
  }

  async bibtex(): Promise<string> {
    return (await this.request("items", { format: "bibtex", limit: 100_000 })).toString("utf8");
  }
}

function now(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/u, "Z");
}

export function slugify(value: string, fallback = "untitled", maxLength = 80): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/gu, "-")
    .replace(/^-+|-+$/gu, "")
    .slice(0, maxLength)
    .replace(/-+$/u, "") || fallback;
}

async function exists(target: string): Promise<boolean> {
  try {
    await stat(target);
    return true;
  } catch {
    return false;
  }
}

async function writeAtomic(target: string, contents: string): Promise<void> {
  await mkdir(path.dirname(target), { recursive: true });
  const temporary = `${target}.tmp-${process.pid}`;
  await writeFile(temporary, contents, "utf8");
  await rename(temporary, target);
}

async function sha256File(target: string): Promise<string> {
  return createHash("sha256").update(await readFile(target)).digest("hex");
}

async function walkFiles(root: string): Promise<string[]> {
  const found: string[] = [];
  const visit = async (directory: string): Promise<void> => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) await visit(target);
      else if (entry.isFile()) found.push(target);
    }
  };
  if (await exists(root)) await visit(root);
  return found.sort();
}

async function recordPaths(root: string): Promise<string[]> {
  return (await walkFiles(root)).filter((target) => path.basename(target) === "record.yml");
}

async function readRecord(target: string): Promise<LiteratureRecord> {
  return (parse(await readFile(target, "utf8")) ?? {}) as LiteratureRecord;
}

function collectionPaths(collections: readonly ZoteroCollection[]): Record<string, CollectionPath> {
  const nodes = new Map<string, { name: string; parent: string | null }>();
  for (const collection of collections) {
    if (!collection.key) continue;
    nodes.set(collection.key, {
      name: String(collection.data?.name ?? "Untitled"),
      parent: typeof collection.data?.parentCollection === "string"
        ? collection.data.parentCollection
        : null,
    });
  }
  const pathFor = (key: string, seen = new Set<string>()): string => {
    const node = nodes.get(key);
    if (node === undefined) return "Untitled";
    if (seen.has(key)) return node.name;
    const next = new Set(seen).add(key);
    return node.parent !== null && nodes.has(node.parent)
      ? `${pathFor(node.parent, next)}/${node.name}`
      : node.name;
  };
  const rootFor = (key: string, seen = new Set<string>()): string => {
    const node = nodes.get(key);
    if (node === undefined || seen.has(key) || node.parent === null || !nodes.has(node.parent)) return key;
    return rootFor(node.parent, new Set(seen).add(key));
  };
  return Object.fromEntries(
    [...nodes].map(([key, node]) => {
      const rootKey = rootFor(key);
      return [key, {
        key,
        name: node.name,
        path: pathFor(key),
        parentKey: node.parent,
        rootKey,
        rootName: nodes.get(rootKey)?.name ?? node.name,
      } satisfies CollectionPath];
    }),
  );
}

async function loadConfig(
  literatureRoot: string,
  paths: Record<string, CollectionPath>,
  connected: boolean,
): Promise<ZoteroConfig> {
  const target = path.join(literatureRoot, "zotero.yml");
  let config: ZoteroConfig;
  if (await exists(target)) {
    config = (parse(await readFile(target, "utf8")) ?? {}) as ZoteroConfig;
  } else if (!connected) {
    throw new Error("literature/zotero.yml is missing; run `./qlab literature connect zotero` first");
  } else {
    config = {
      schema_version: 1,
      mapping_strategy: "top-level-collection",
      default_topic: "inbox",
      collection_map: {},
      ignored_collections: [],
    };
  }
  config.schema_version ??= 1;
  config.default_topic ??= "inbox";
  config.collection_map ??= {};
  config.ignored_collections ??= [];
  for (const [key, collection] of Object.entries(paths)) {
    const automaticTopic = slugify(collection.rootName, `zotero-${collection.rootKey.toLowerCase()}`);
    const mapped = config.collection_map[key] ?? {
      name: collection.name,
      path: collection.path,
      topic: automaticTopic,
      priority: 0,
      parent_key: collection.parentKey,
      root_key: collection.rootKey,
    };
    mapped.name = collection.name;
    mapped.path = collection.path;
    mapped.topic ||= automaticTopic;
    mapped.priority ??= 0;
    mapped.parent_key = collection.parentKey;
    mapped.root_key = collection.rootKey;
    config.collection_map[key] = mapped;
  }
  config.mapping_strategy = "top-level-collection";
  await writeAtomic(target, stringify(config, { sortMapEntries: false }));
  return config;
}

function collectionDirectories(
  root: string,
  paths: Record<string, CollectionPath>,
): Record<string, string> {
  const siblings = new Map<string | null, string[]>();
  const segments: Record<string, string> = {};
  for (const collection of Object.values(paths)) {
    const group = siblings.get(collection.parentKey) ?? [];
    group.push(collection.key);
    siblings.set(collection.parentKey, group);
    segments[collection.key] = slugify(collection.name, `collection-${collection.key.toLowerCase()}`);
  }
  for (const group of siblings.values()) {
    const counts = new Map<string, number>();
    for (const key of group) counts.set(segments[key], (counts.get(segments[key]) ?? 0) + 1);
    for (const key of group) if ((counts.get(segments[key]) ?? 0) > 1) segments[key] += `--${key.toLowerCase()}`;
  }
  const resolved: Record<string, string> = {};
  const resolve = (key: string, seen = new Set<string>()): string => {
    if (resolved[key] !== undefined) return resolved[key];
    if (seen.has(key)) return path.join(root, `${segments[key]}--${key.toLowerCase()}`);
    const collection = paths[key];
    const parent = collection.parentKey;
    const directory = parent !== null && paths[parent] !== undefined
      ? path.join(resolve(parent, new Set(seen).add(key)), segments[key])
      : path.join(root, segments[key]);
    resolved[key] = directory;
    return directory;
  };
  for (const key of Object.keys(paths)) resolve(key);
  return resolved;
}

async function ensureCollectionRoot(literatureRoot: string): Promise<void> {
  const root = path.join(literatureRoot, "collections");
  const marker = path.join(root, ".qlab-generated");
  if ((await exists(root)) && !(await exists(marker))) {
    throw new Error(`Refusing to manage an unmarked collection tree at ${root}`);
  }
  await mkdir(root, { recursive: true });
  await writeAtomic(
    marker,
    "Managed incrementally by `qlab literature import zotero`; paper assets are never deleted during refresh.\n",
  );
}

function authors(
  data: ZoteroItem["data"],
): Array<{ name?: string; first?: string; last?: string }> {
  return (data.creators ?? [])
    .filter((creator) => creator.creatorType === "author")
    .map((creator) => creator.name
      ? { name: creator.name }
      : { first: creator.firstName ?? "", last: creator.lastName ?? "" });
}

function year(value: string | undefined): number | null {
  const match = /(?:19|20)\d{2}/u.exec(value ?? "");
  return match === null ? null : Number(match[0]);
}

function identifiers(data: ZoteroItem["data"]): Record<string, string> {
  const result: Record<string, string> = {};
  const doi = (data.DOI ?? "").trim().toLowerCase();
  if (doi !== "") result.doi = doi;
  const arxiv = ARXIV_PATTERN.exec(data.extra ?? "");
  if (arxiv !== null) result.arxiv = arxiv[1];
  const isbn = (data.ISBN ?? "").trim();
  if (isbn !== "") result.isbn = isbn;
  return result;
}

function membershipsOf(
  itemCollections: readonly string[],
  paths: Record<string, CollectionPath>,
  config: ZoteroConfig,
): {
  memberships: Array<{ key: string; name: string; path: string }>;
  indexedCollections: string[];
  indexedTopics: string[];
  primaryCollection: string | null;
  primaryTopic: string;
} {
  const ignored = new Set(config.ignored_collections);
  const memberships = itemCollections
    .filter((key) => paths[key] !== undefined)
    .map((key) => ({ key, name: paths[key].name, path: paths[key].path }));
  const candidates = itemCollections
    .map((key, position) => ({ key, position, mapped: config.collection_map[key] }))
    .filter((entry) => entry.mapped !== undefined && !ignored.has(entry.key));
  if (candidates.length === 0) {
    return {
      memberships,
      indexedCollections: [],
      indexedTopics: [config.default_topic],
      primaryCollection: null,
      primaryTopic: config.default_topic,
    };
  }
  candidates.sort((a, b) => b.mapped.priority - a.mapped.priority || a.position - b.position);
  return {
    memberships,
    indexedCollections: [...new Set(candidates.map((entry) => entry.key))].sort(),
    indexedTopics: [...new Set(candidates.map((entry) => entry.mapped.topic))].sort(),
    primaryCollection: candidates[0].key,
    primaryTopic: candidates[0].mapped.topic,
  };
}

function paperParent(
  literatureRoot: string,
  primaryCollection: string | null,
  directories: Record<string, string>,
): string {
  return primaryCollection !== null && directories[primaryCollection] !== undefined
    ? path.join(directories[primaryCollection], "papers")
    : path.join(literatureRoot, "inbox", "papers");
}

async function movePaper(recordPath: string, destinationParent: string): Promise<string> {
  const destination = path.join(destinationParent, path.basename(path.dirname(recordPath)));
  if (destination === path.dirname(recordPath)) return recordPath;
  if (await exists(destination)) throw new Error(`Cannot move paper: destination exists at ${destination}`);
  await mkdir(destinationParent, { recursive: true });
  await rename(path.dirname(recordPath), destination);
  return path.join(destination, "record.yml");
}

function roleOf(relative: string, entrypoint?: string): string {
  if (relative === "paper.pdf") return "primary-pdf";
  if (relative === "extracted.md") return "derived-text";
  if (relative === "record.yml") return "metadata";
  if (entrypoint !== undefined && relative === entrypoint) return "latex-entrypoint";
  if (relative.startsWith("source/")) return "latex-source";
  if (relative.startsWith("figures/")) return "figure";
  return "metadata";
}

export async function writeZoteroManifest(
  recordPath: string,
  record: LiteratureRecord,
  generatedAt: string,
): Promise<void> {
  const paperRoot = path.dirname(recordPath);
  const files = [];
  for (const target of await walkFiles(paperRoot)) {
    if (path.basename(target) === "manifest.json") continue;
    const relative = path.relative(paperRoot, target).split(path.sep).join("/");
    const details = await stat(target);
    files.push({
      path: relative,
      role: roleOf(relative, record.latex?.entrypoint),
      sha256: await sha256File(target),
      size: details.size,
    });
  }
  const manifest = {
    schema_version: 2,
    generated_at: generatedAt,
    paper: {
      title: record.title ?? "",
      authors: record.authors ?? [],
      year: record.year ?? null,
      identifiers: record.identifiers ?? {},
      primary_collection: record.qlab?.primary_collection ?? null,
      indexed_collections: record.qlab?.indexed_collections ?? [],
      primary_topic: record.qlab?.primary_topic ?? "inbox",
      indexed_topics: record.qlab?.indexed_topics ?? [],
      zotero_item_key: record.zotero_import?.item_key ?? null,
      collections: record.zotero_import?.collections ?? [],
    },
    files,
  };
  await writeAtomic(path.join(paperRoot, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
}

function authorText(record: LiteratureRecord): string {
  return (record.authors ?? []).map((author) =>
    author.name ?? [author.first, author.last].filter(Boolean).join(" "),
  ).join(", ");
}

async function writeIndexes(
  literatureRoot: string,
  paths: Record<string, CollectionPath>,
  directories: Record<string, string>,
  config: ZoteroConfig,
  records: readonly string[],
): Promise<void> {
  const loaded = await Promise.all(records.map(async (recordPath) => ({ recordPath, record: await readRecord(recordPath) })));
  const byCollection = new Map<string, Array<{ recordPath: string; record: LiteratureRecord }>>();
  for (const entry of loaded) {
    for (const membership of entry.record.zotero_import?.collections ?? []) {
      const group = byCollection.get(membership.key) ?? [];
      group.push(entry);
      byCollection.set(membership.key, group);
    }
  }
  for (const directory of Object.values(directories)) await mkdir(path.join(directory, "papers"), { recursive: true });

  const collectionRoot = path.join(literatureRoot, "collections");
  const top = Object.values(paths).filter((collection) => collection.parentKey === null || paths[collection.parentKey] === undefined);
  await writeAtomic(path.join(collectionRoot, "INDEX.md"), [
    "# Zotero collections",
    "",
    "This hierarchy is managed incrementally from Zotero. Each paper directory lives",
    "once under its primary collection's `papers/`; refresh never deletes paper assets.",
    "",
    ...top.map((collection) =>
      `- [${collection.name}](${path.relative(collectionRoot, directories[collection.key]).split(path.sep).join("/")}/INDEX.md)`,
    ),
    "",
  ].join("\n"));

  for (const collection of Object.values(paths)) {
    const directory = directories[collection.key];
    const children = Object.values(paths).filter((candidate) => candidate.parentKey === collection.key);
    const mapped = config.collection_map[collection.key];
    await writeAtomic(path.join(directory, "collection.yml"), stringify({
      schema_version: 1,
      source: "zotero",
      key: collection.key,
      name: collection.name,
      parent_key: collection.parentKey,
      root_key: collection.rootKey,
      path: collection.path,
      topic: mapped?.topic ?? config.default_topic,
      ignored: config.ignored_collections.includes(collection.key),
    }, { sortMapEntries: false }));
    const lines = [
      `# ${collection.name}`,
      "",
      `Zotero path: \`${collection.path}\`  `,
      `Collection key: \`${collection.key}\``,
    ];
    if (children.length > 0) {
      lines.push("", "## Subcollections", "");
      for (const child of children) {
        lines.push(`- [${child.name}](${path.relative(directory, directories[child.key]).split(path.sep).join("/")}/INDEX.md)`);
      }
    }
    lines.push("", "## Direct papers", "");
    const entries = (byCollection.get(collection.key) ?? []).sort((a, b) =>
      (a.record.title ?? "").localeCompare(b.record.title ?? ""),
    );
    if (entries.length === 0) lines.push("No papers are assigned directly to this collection.");
    else {
      lines.push("| Item | Title | Authors | Year |", "|---|---|---|---:|");
      for (const entry of entries) {
        const relative = path.relative(directory, entry.recordPath).split(path.sep).join("/");
        lines.push(`| [${entry.record.zotero_import?.item_key ?? ""}](${relative}) | ${entry.record.title ?? ""} | ${authorText(entry.record)} | ${entry.record.year ?? ""} |`);
      }
    }
    await writeAtomic(path.join(directory, "INDEX.md"), `${lines.join("\n").trimEnd()}\n`);
  }

  const inbox = path.join(literatureRoot, "inbox");
  await mkdir(path.join(inbox, "papers"), { recursive: true });
  const uncollected = loaded
    .filter((entry) => entry.record.qlab?.primary_collection == null)
    .sort((a, b) => (a.record.title ?? "").localeCompare(b.record.title ?? ""));
  const inboxLines = [
    "# Uncollected literature",
    "",
    "Papers without a Zotero collection live once in `papers/`.",
    "",
    "| Item | Title | Authors | Year |",
    "|---|---|---|---:|",
  ];
  for (const entry of uncollected) {
    const relative = path.relative(inbox, entry.recordPath).split(path.sep).join("/");
    inboxLines.push(`| [${entry.record.zotero_import?.item_key ?? ""}](${relative}) | ${entry.record.title ?? ""} | ${authorText(entry.record)} | ${entry.record.year ?? ""} |`);
  }
  await writeAtomic(path.join(inbox, "INDEX.md"), `${inboxLines.join("\n").trimEnd()}\n`);
}

export async function importZoteroSnapshot(options: {
  literatureRoot: string;
  collections: readonly ZoteroCollection[];
  items: readonly ZoteroItem[];
  library: string;
  connected?: boolean;
  importedAt?: string;
  rehomeMetadataOnly?: boolean;
}): Promise<ZoteroImportReport> {
  const literatureRoot = path.resolve(options.literatureRoot);
  await mkdir(literatureRoot, { recursive: true });
  const importedAt = options.importedAt ?? now();
  const paths = collectionPaths(options.collections);
  const config = await loadConfig(literatureRoot, paths, options.connected ?? false);
  await ensureCollectionRoot(literatureRoot);
  const directories = collectionDirectories(path.join(literatureRoot, "collections"), paths);
  const existing = new Map<string, string>();
  for (const recordPath of await recordPaths(literatureRoot)) {
    const key = (await readRecord(recordPath)).zotero_import?.item_key;
    if (key !== undefined) existing.set(key, recordPath);
  }
  const touched = new Map(existing);
  const dois = new Map<string, string[]>();
  let imported = 0;

  for (const item of options.items) {
    if (!item.key || IGNORED_ITEM_TYPES.has(item.data.itemType ?? "")) continue;
    imported += 1;
    const suggested = membershipsOf(item.data.collections ?? [], paths, config);
    const oldPath = existing.get(item.key);
    const old: LiteratureRecord = oldPath === undefined
      ? { schema_version: 2, origin: "zotero-import", materialization: "metadata-only" }
      : await readRecord(oldPath);
    const oldPrimary = old.qlab?.primary_collection ?? null;
    const oldTopic = old.qlab?.primary_topic ??
      (oldPrimary === null ? config.default_topic : config.collection_map[oldPrimary]?.topic ?? config.default_topic);
    let primaryCollection = oldPath === undefined ? suggested.primaryCollection : oldPrimary;
    let primaryTopic = oldPath === undefined ? suggested.primaryTopic : oldTopic;
    let recordPath: string;

    if (oldPath === undefined) {
      recordPath = path.join(
        paperParent(literatureRoot, primaryCollection, directories),
        `${item.key}_${slugify(item.data.title ?? "")}`,
        "record.yml",
      );
    } else {
      recordPath = oldPath;
      if (oldPrimary === null || directories[oldPrimary] !== undefined) {
        const expected = paperParent(literatureRoot, oldPrimary, directories);
        if (path.dirname(path.dirname(recordPath)) !== expected) recordPath = await movePaper(recordPath, expected);
      }
      if (
        options.rehomeMetadataOnly === true &&
        (old.materialization ?? "metadata-only") === "metadata-only" &&
        oldPrimary !== suggested.primaryCollection
      ) {
        recordPath = await movePaper(recordPath, paperParent(literatureRoot, suggested.primaryCollection, directories));
        primaryCollection = suggested.primaryCollection;
        primaryTopic = suggested.primaryTopic;
      }
    }

    await mkdir(path.dirname(recordPath), { recursive: true });
    const itemIdentifiers = identifiers(item.data);
    const record: LiteratureRecord = {
      schema_version: 2,
      origin: String(old.origin ?? "zotero-import"),
      materialization: String(old.materialization ?? "metadata-only"),
      zotero_import: {
        library: options.library,
        item_key: item.key,
        item_version: item.version ?? item.data.version,
        imported_at: importedAt,
        collections: suggested.memberships,
      },
      qlab: {
        primary_collection: primaryCollection,
        indexed_collections: suggested.indexedCollections,
        primary_topic: primaryTopic,
        indexed_topics: suggested.indexedTopics,
      },
      item_type: item.data.itemType,
      title: item.data.title ?? "",
      authors: authors(item.data),
      year: year(item.data.date),
      abstract: item.data.abstractNote ?? "",
      tags: [...new Set((item.data.tags ?? []).map((tag) => tag.tag ?? "").filter(Boolean))].sort(),
      identifiers: itemIdentifiers,
    };
    for (const field of [
      "evidence_mode",
      "source_url",
      "pdf_url",
      "retrieved_at",
      "source_archive_sha256",
      "paper_pdf_sha256",
      "latex",
    ]) {
      if (old[field] !== undefined) record[field] = old[field];
    }
    await writeAtomic(recordPath, stringify(record, { sortMapEntries: false }));
    await writeZoteroManifest(recordPath, record, importedAt);
    touched.set(item.key, recordPath);
    if (itemIdentifiers.doi !== undefined) {
      const group = dois.get(itemIdentifiers.doi) ?? [];
      group.push(item.key);
      dois.set(itemIdentifiers.doi, group);
    }
  }

  const records = [...new Set(touched.values())].sort();
  await writeIndexes(literatureRoot, paths, directories, config, records);
  await writeAtomic(path.join(literatureRoot, "zotero-snapshot.json"), `${JSON.stringify({
    schema_version: 1,
    library: options.library,
    imported_at: importedAt,
    item_count: records.length,
    imported_item_count: imported,
    collection_count: Object.keys(paths).length,
    deletion_policy: "retain-local-records",
  }, null, 2)}\n`);
  return {
    imported,
    records,
    duplicateCandidates: Object.fromEntries([...dois].filter(([, keys]) => keys.length > 1)),
  };
}
