const ATTACHMENT_TITLES = {
  "primary-pdf": "QLab · Paper PDF",
  "latex-entrypoint": "QLab · LaTeX Source",
} as const;

interface RawLiteratureRecord {
  topic: string;
  paperDir: string;
  manifest: any;
}

export interface LiteratureImportRecord {
  identity: string;
  paperDir: string;
  title: string;
  authors: Array<Record<string, string>>;
  year: number | string | null;
  identifiers: Record<string, string>;
  zoteroItemKey: string | null;
  topics: string[];
  collectionPaths: string[];
  attachments: Array<{ path: string; role: string; title: string }>;
}

function literatureIdentity(record: RawLiteratureRecord): string {
  const paper = record.manifest.paper || {};
  const identifiers = paper.identifiers || {};
  if (paper.zotero_item_key) return `zotero:${paper.zotero_item_key}`;
  if (identifiers.doi) return `doi:${String(identifiers.doi).toLowerCase()}`;
  if (identifiers.arxiv) return `arxiv:${identifiers.arxiv}`;
  return `path:${record.paperDir}`;
}

export function normalizeLiteratureRecord(record: RawLiteratureRecord): LiteratureImportRecord {
  if (!record?.manifest || record.manifest.schema_version !== 2) {
    throw new Error(`Unsupported QLab manifest at ${record?.paperDir || "unknown path"}`);
  }
  const paper = record.manifest.paper || {};
  const topics = [...new Set<string>(paper.indexed_topics || [record.topic])].sort();
  const collectionPaths = [...new Set<string>(
    (paper.collections || []).map((collection: any) => collection.path).filter(Boolean),
  )].sort();
  const attachments = (record.manifest.files || [])
    .filter((file: any) => Object.hasOwn(ATTACHMENT_TITLES, file.role))
    .map((file: any) => ({
      path: String(file.path),
      role: String(file.role),
      title: ATTACHMENT_TITLES[file.role as keyof typeof ATTACHMENT_TITLES],
    }));
  return {
    identity: literatureIdentity(record),
    paperDir: record.paperDir,
    title: paper.title || "Untitled QLab paper",
    authors: paper.authors || [],
    year: paper.year || null,
    identifiers: paper.identifiers || {},
    zoteroItemKey: paper.zotero_item_key || null,
    topics,
    collectionPaths,
    attachments,
  };
}

export function buildLiteratureImportPlan(records: RawLiteratureRecord[]): LiteratureImportRecord[] {
  const plan = new Map<string, LiteratureImportRecord>();
  for (const raw of records) {
    const record = normalizeLiteratureRecord(raw);
    const current = plan.get(record.identity);
    if (!current) {
      plan.set(record.identity, record);
      continue;
    }
    current.topics = [...new Set([...current.topics, ...record.topics])].sort();
    current.collectionPaths = [...new Set([
      ...current.collectionPaths,
      ...record.collectionPaths,
    ])].sort();
    const paths = new Set(current.attachments.map((item) => item.path));
    current.attachments.push(...record.attachments.filter((item) => !paths.has(item.path)));
  }
  return [...plan.values()];
}

export class QLabLiteratureService {
  private readonly statePref = "extensions.zotkit.qlabLiteratureState";
  private readonly topCollection = "QLab Literature";

  async sync(repositoryRoot: string): Promise<{ scanned: number; created: number; updated: number }> {
    const literatureRoot = PathUtils.join(repositoryRoot, "literature");
    if (!await IOUtils.exists(literatureRoot)) throw new Error("QLab literature/ directory is unavailable");
    const plan = buildLiteratureImportPlan(await this.readRecords(literatureRoot));
    const top = await this.getOrCreateCollection(this.topCollection);
    const collectionCache = new Map<string, any>();
    const state = JSON.parse(Services.prefs.getStringPref(this.statePref, "{}") || "{}");
    const items = await Zotero.Items.getAll(Zotero.Libraries.userLibraryID, true);
    let created = 0;
    let updated = 0;
    for (const record of plan) {
      let item = await this.findItem(record, state, items);
      if (!item) {
        item = await this.createItem(record);
        items.push(item);
        created += 1;
      }
      else {
        updated += 1;
      }
      state[record.identity] = item.key;
      const collectionPaths = record.collectionPaths.length ? record.collectionPaths : record.topics;
      for (const collectionPath of collectionPaths) {
        let parent = top;
        let accumulated = "";
        for (const name of collectionPath.split("/").filter(Boolean)) {
          accumulated = accumulated ? `${accumulated}/${name}` : name;
          if (!collectionCache.has(accumulated)) {
            collectionCache.set(accumulated, await this.getOrCreateCollection(name, parent.id));
          }
          parent = collectionCache.get(accumulated);
        }
        if (!parent.hasItem(item.id)) await parent.addItem(item.id);
      }
      for (const attachment of record.attachments) await this.ensureAttachment(item, record, attachment);
    }
    Services.prefs.setStringPref(this.statePref, JSON.stringify(state));
    return { scanned: plan.length, created, updated };
  }

  private async readRecords(root: string): Promise<RawLiteratureRecord[]> {
    const records: RawLiteratureRecord[] = [];
    const visit = async (directory: string): Promise<void> => {
      for (const child of await IOUtils.getChildren(directory)) {
        const stat = await IOUtils.stat(child);
        if (stat.type !== "directory") continue;
        const manifestPath = PathUtils.join(child, "manifest.json");
        if (await IOUtils.exists(manifestPath)) {
          records.push({
            topic: "inbox",
            paperDir: child,
            manifest: JSON.parse(await IOUtils.readUTF8(manifestPath)),
          });
        }
        else {
          await visit(child);
        }
      }
    };
    await visit(root);
    return records;
  }

  private async getOrCreateCollection(name: string, parentID: number | null = null): Promise<any> {
    const libraryID = Zotero.Libraries.userLibraryID;
    const found = Zotero.Collections.getByLibrary(libraryID, true).find((collection: any) => (
      collection.name === name && (collection.parentID || null) === parentID
    ));
    if (found) return found;
    const collection = new Zotero.Collection();
    collection.libraryID = libraryID;
    collection.name = name;
    collection.parentID = parentID;
    await collection.saveTx();
    return collection;
  }

  private async findItem(record: LiteratureImportRecord, state: Record<string, string>, items: any[]): Promise<any> {
    for (const key of [record.zoteroItemKey, state[record.identity]]) {
      if (!key) continue;
      const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, key);
      if (item && !item.isAttachment()) return item;
    }
    const doi = String(record.identifiers.doi || "").trim().toLowerCase();
    if (!doi) return null;
    return items.find((item) => !item.isAttachment()
      && String(item.getField("DOI") || "").trim().toLowerCase() === doi) || null;
  }

  private async createItem(record: LiteratureImportRecord): Promise<any> {
    const item = new Zotero.Item("journalArticle");
    item.libraryID = Zotero.Libraries.userLibraryID;
    item.setField("title", record.title);
    if (record.year) item.setField("date", String(record.year));
    if (record.identifiers.doi) item.setField("DOI", record.identifiers.doi);
    if (record.identifiers.arxiv) item.setField("archive", "arXiv");
    const creators = record.authors.map((author) => author.name
      ? { creatorType: "author", name: author.name, fieldMode: 1 }
      : { creatorType: "author", firstName: author.first || "", lastName: author.last || "" });
    if (creators.length) item.setCreators(creators);
    await item.saveTx();
    return item;
  }

  private async ensureAttachment(
    item: any,
    record: LiteratureImportRecord,
    attachment: LiteratureImportRecord["attachments"][number],
  ): Promise<void> {
    const path = PathUtils.join(record.paperDir, ...attachment.path.split("/"));
    if (!await IOUtils.exists(path)) return;
    for (const attachmentID of item.getAttachments()) {
      if (Zotero.Items.get(attachmentID)?.getFilePath() === path) return;
    }
    const linked = await Zotero.Attachments.linkFromFile({ file: path, parentItemID: item.id });
    linked.setField("title", attachment.title);
    await linked.saveTx();
  }
}
