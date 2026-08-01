import { sha256Bytes as defaultSha256Bytes } from "./hashing";
import {
  parseAIContextDocument,
  type AIContextDocument,
  type AIContextHost,
  type AIContextPaper,
  type AIContextProjectionHandle,
  type AIContextProjectionResult,
} from "./ai-context";

export class AIContextRecoveryRequiredError extends Error {
  constructor(readonly artifactPath: string, detail: string) {
    super(`AI Context recovery required at ${artifactPath}: ${detail}`);
    this.name = "AIContextRecoveryRequiredError";
  }
}

export interface ZoteroAIContextRuntime {
  root(): string;
  userLibraryID(): number | string;
  listChildren(path: string): Promise<string[]>;
  exists(path: string): Promise<boolean>;
  makeDirectory(path: string, options: { createAncestors: false }): Promise<void>;
  readUTF8(path: string): Promise<string>;
  sha256(source: string): Promise<string>;
  uniqueToken(): string;
  recoverCASArtifacts(directory: string): Promise<void>;
  writeAtomic(path: string, source: string, expectedRevision: string | null): Promise<boolean>;
  canonical(path: string, allowMissingFinal?: boolean): string;
  itemByID(id: number | string): Promise<unknown>;
  itemByLibraryAndKey(libraryID: number | string, itemKey: string): Promise<unknown>;
  attachmentsFor(parent: unknown): Promise<unknown[]>;
  topLevelAttachments(libraryID: number | string): Promise<unknown[]>;
  attachmentPath(attachment: unknown): string | null;
  attachmentTitle(attachment: unknown): string;
  linkFromFile(options: { file: string; parentItemID?: number }): Promise<unknown>;
  saveAttachmentTitle(attachment: unknown, title: string): Promise<void>;
}

export interface GeckoZoteroAIContextRuntimeInput {
  Zotero: any;
  IOUtils: any;
  PathUtils: any;
  Components: any;
  root(): string;
  hashBytes?: (bytes: Uint8Array) => string;
}

export interface AIContextAttachmentDescriptor {
  item: unknown;
  relativePath: string;
  document: AIContextDocument;
}

interface AIContextZoteroItem {
  id: number;
  key: string;
  libraryID: number | string;
  parentID?: number | null;
  isRegularItem?(): boolean;
  isEditable?(): boolean;
  isAttachment?(): boolean;
  isPDFAttachment?(): boolean;
  isLinkedFileAttachment?(): boolean;
  getField?(name: string): string;
  getCreators?(): Array<{ firstName?: string; lastName?: string; name?: string }>;
  getAttachments?(): number[];
  getFilePath?(): string | null;
}

function zoteroItem(value: unknown): AIContextZoteroItem {
  if (!value || typeof value !== "object") throw new Error("missing Zotero item");
  return value as AIContextZoteroItem;
}

async function localRegularParent(runtime: ZoteroAIContextRuntime, value: unknown): Promise<AIContextZoteroItem> {
  let candidate = zoteroItem(value);
  if (candidate.isAttachment?.()) {
    if (!candidate.isPDFAttachment?.() || !candidate.parentID) {
      throw new Error(`${candidate.key} is not a PDF child of a regular item`);
    }
    candidate = zoteroItem(await runtime.itemByID(candidate.parentID));
  }
  if (!candidate.isRegularItem?.()) throw new Error(`${candidate.key} is not a regular item`);
  if (!candidate.isEditable?.()) throw new Error(`${candidate.key} is not editable`);
  if (String(candidate.libraryID) !== String(runtime.userLibraryID())) {
    throw new Error(`${candidate.key} is not in the local user library`);
  }
  return candidate;
}

export async function normalizeAIContextTargets(
  runtime: ZoteroAIContextRuntime,
  items: unknown[],
): Promise<AIContextPaper[]> {
  const parents = new Map<string, AIContextZoteroItem>();
  for (const value of items) {
    const parent = await localRegularParent(runtime, value);
    parents.set(`${parent.libraryID}:${parent.key}`, parent);
  }
  if (parents.size < 1 || parents.size > 50) throw new Error("selection must contain 1..50 unique parents");
  return [...parents.values()].map((parent) => ({
    libraryID: String(parent.libraryID),
    itemKey: parent.key,
    title: parent.getField?.("title") || parent.key,
    creators: parent.getCreators?.().map((creator) =>
      creator.name || [creator.firstName, creator.lastName].filter(Boolean).join(" ")).filter(Boolean),
    year: parent.getField?.("date") || undefined,
    abstract: parent.getField?.("abstractNote") || undefined,
  }));
}

function platformJoin(root: string, relativePath: string): string {
  const separator = root.includes("\\") ? "\\" : "/";
  return `${root.replace(/[\\/]+$/u, "")}${separator}${relativePath.replace(/[\\/]/gu, separator)}`;
}

function absoluteAIContextPath(runtime: ZoteroAIContextRuntime, relativePath: string): string {
  if (!/^drafts\/ai-contexts\/[A-Za-z0-9._-]+\.qmd$/u.test(relativePath)) {
    throw new Error("path must be drafts/ai-contexts/*.qmd");
  }
  const root = runtime.canonical(runtime.root());
  const candidate = runtime.canonical(platformJoin(root, relativePath), true);
  const separator = root.includes("\\") ? "\\" : "/";
  if (candidate !== root && !candidate.startsWith(`${root}${separator}`)) {
    throw new Error("path escapes selected Research Loop root");
  }
  return candidate;
}

function blankProjection(): AIContextProjectionResult {
  return { created: [], reused: [], missing: [] };
}

async function canonicalMatch(
  runtime: ZoteroAIContextRuntime,
  attachments: readonly unknown[],
  absolutePath: string,
  expectedTitle: string,
): Promise<unknown | null> {
  let wrongTitleMatch: unknown | null = null;
  for (const attachment of attachments) {
    const path = runtime.attachmentPath(attachment);
    if (path && runtime.canonical(path, true) === absolutePath) {
      if (runtime.attachmentTitle(attachment) === expectedTitle) return attachment;
      wrongTitleMatch ??= attachment;
    }
  }
  return wrongTitleMatch;
}

async function ensureAIContextDirectories(runtime: ZoteroAIContextRuntime): Promise<string> {
  const root = runtime.canonical(runtime.root());
  const directories = [
    runtime.canonical(platformJoin(root, "drafts"), true),
    runtime.canonical(platformJoin(root, "drafts/ai-contexts"), true),
  ];
  let parent = root;
  for (const directory of directories) {
    // Validate the parent immediately before each one-level operation.
    runtime.canonical(parent);
    if (!await runtime.exists(directory)) {
      await runtime.makeDirectory(directory, { createAncestors: false });
      if (!await runtime.exists(directory)) throw new Error(`directory creation failed: ${directory}`);
    }
    const canonical = runtime.canonical(directory);
    const separator = root.includes("\\") ? "\\" : "/";
    if (!canonical.startsWith(`${root}${separator}`)) throw new Error("directory escapes selected root");
    parent = canonical;
  }
  // Revalidate root and every existing/created component after creation. A
  // symlink swap aborts before writeAtomic receives a path.
  runtime.canonical(root);
  for (const directory of directories) runtime.canonical(directory);
  return directories[1]!;
}

function checkedAIContextDirectories(runtime: ZoteroAIContextRuntime): {
  root: string;
  drafts: string;
  contexts: string;
} {
  // These are the first runtime calls. canonical(..., true) validates the
  // nearest existing ancestor and rejects any root/parent symlink without I/O.
  const root = runtime.canonical(runtime.root());
  const drafts = runtime.canonical(platformJoin(root, "drafts"), true);
  const contexts = runtime.canonical(platformJoin(root, "drafts/ai-contexts"), true);
  return { root, drafts, contexts };
}

async function recoverExistingAIContextDirectory(
  runtime: ZoteroAIContextRuntime,
): Promise<{ root: string; contexts: string } | null> {
  const checked = checkedAIContextDirectories(runtime);
  if (!await runtime.exists(checked.contexts)) return null;
  runtime.canonical(checked.root);
  runtime.canonical(checked.drafts);
  runtime.canonical(checked.contexts);
  await runtime.recoverCASArtifacts(checked.contexts);
  runtime.canonical(checked.root);
  runtime.canonical(checked.drafts);
  runtime.canonical(checked.contexts);
  return { root: checked.root, contexts: checked.contexts };
}

async function completeProjectionHandle(
  runtime: ZoteroAIContextRuntime,
  document: AIContextDocument,
  result: AIContextProjectionResult,
  handle: AIContextProjectionHandle,
  matching: unknown | null,
  create: boolean,
  createAttachment: () => Promise<unknown>,
): Promise<void> {
  if (matching && runtime.attachmentTitle(matching) === document.title) {
    result.reused.push(handle);
    return;
  }
  if (!create) {
    result.missing.push(handle);
    return;
  }
  if (matching) {
    try {
      await runtime.saveAttachmentTitle(matching, document.title);
      if (runtime.attachmentTitle(matching) !== document.title) throw new Error("title did not persist");
      result.reused.push(handle);
    }
    catch { result.missing.push(handle); }
    return;
  }
  try {
    const attachment = await createAttachment();
    await runtime.saveAttachmentTitle(attachment, document.title);
    if (runtime.attachmentTitle(attachment) !== document.title) throw new Error("title did not persist");
    result.created.push(handle);
  }
  catch {
    // linkFromFile may already have committed the Zotero record. Retaining it
    // as missing lets repair find the same canonical record and retry retitle.
    result.missing.push(handle);
  }
}

export function createZoteroAIContextHost(runtime: ZoteroAIContextRuntime): AIContextHost {
  async function project(document: AIContextDocument, create: boolean): Promise<AIContextProjectionResult> {
    if (create) await host.preflight(document.manifest.projection, document.manifest.papers);
    const path = absoluteAIContextPath(runtime, document.relativePath);
    const result = blankProjection();
    if (document.manifest.projection.mode === "standalone") {
      const handle = { mode: "standalone" as const, libraryID: String(runtime.userLibraryID()) };
      try {
        const matching = await canonicalMatch(
          runtime, await runtime.topLevelAttachments(runtime.userLibraryID()), path, document.title,
        );
        await completeProjectionHandle(
          runtime, document, result, handle, matching, create,
          () => runtime.linkFromFile({ file: path }),
        );
      }
      catch (cause) {
        if (create) throw cause;
        result.missing.push(handle);
      }
      return result;
    }
    for (const target of document.manifest.projection.targets) {
      const handle = { mode: "attached" as const, ...target };
      try {
        const parent = await localRegularParent(
          runtime, await runtime.itemByLibraryAndKey(target.libraryID, target.itemKey),
        );
        const matching = await canonicalMatch(runtime, await runtime.attachmentsFor(parent), path, document.title);
        await completeProjectionHandle(
          runtime, document, result, handle, matching, create,
          () => runtime.linkFromFile({ file: path, parentItemID: parent.id }),
        );
      }
      catch (cause) {
        if (create) throw cause;
        result.missing.push(handle);
      }
    }
    return result;
  }

  const host: AIContextHost = {
    async list() {
      const recovered = await recoverExistingAIContextDirectory(runtime);
      if (!recovered) return [];
      const root = recovered.root.replace(/[\\/]+$/u, "");
      const children = (await runtime.listChildren(recovered.contexts))
        .filter((path) => /\.qmd$/iu.test(path)).sort();
      return Promise.all(children.map(async (path) => {
        const canonical = runtime.canonical(path);
        const relativePath = canonical.slice(root.length + 1).replace(/\\/gu, "/");
        absoluteAIContextPath(runtime, relativePath);
        const source = await runtime.readUTF8(canonical);
        parseAIContextDocument(relativePath, source);
        return { relativePath, source, revision: await runtime.sha256(source) };
      }));
    },
    async snapshot(relativePath) {
      const path = absoluteAIContextPath(runtime, relativePath);
      const recovered = await recoverExistingAIContextDirectory(runtime);
      if (!recovered) return { relativePath, source: null, revision: null };
      if (!await runtime.exists(path)) return { relativePath, source: null, revision: null };
      const source = await runtime.readUTF8(runtime.canonical(path));
      parseAIContextDocument(relativePath, source);
      return { relativePath, source, revision: await runtime.sha256(source) };
    },
    async compareAndSwap(relativePath, expectedRevision, source) {
      parseAIContextDocument(relativePath, source);
      const directory = await ensureAIContextDirectories(runtime);
      await runtime.recoverCASArtifacts(directory);
      const path = absoluteAIContextPath(runtime, relativePath);
      await ensureAIContextDirectories(runtime);
      return runtime.writeAtomic(path, source, expectedRevision);
    },
    async preflight(intent, papers) {
      if (intent.mode === "standalone") {
        if (intent.targets.length) throw new Error("standalone projection cannot contain parents");
        if (papers.length) throw new Error("standalone projection cannot contain papers");
        return;
      }
      if (intent.targets.length < 1 || intent.targets.length > 50) {
        throw new Error("attached projection requires 1..50 targets");
      }
      const seen = new Set<string>();
      for (const target of intent.targets) {
        const key = `${target.libraryID}:${target.itemKey}`;
        if (seen.has(key)) throw new Error(`duplicate projection target ${key}`);
        seen.add(key);
        await localRegularParent(runtime, await runtime.itemByLibraryAndKey(target.libraryID, target.itemKey));
      }
      const paperKeys = papers.map((paper) => `${paper.libraryID}:${paper.itemKey}`).sort();
      if (new Set(paperKeys).size !== paperKeys.length
        || paperKeys.join("\0") !== [...seen].sort().join("\0")) {
        throw new Error("attached projection targets must match papers exactly");
      }
    },
    project(document) { return project(document, true); },
    projectionStatus(document) { return project(document, false); },
  };
  return host;
}

export function createGeckoZoteroAIContextRuntime(
  input: GeckoZoteroAIContextRuntimeInput,
): ZoteroAIContextRuntime {
  const { Zotero, IOUtils, PathUtils, Components } = input;
  const file = (path: string) => {
    const value = Components.classes["@mozilla.org/file/local;1"]
      .createInstance(Components.interfaces.nsIFile);
    value.initWithPath(path);
    return value;
  };
  const hashBytes = input.hashBytes ?? defaultSha256Bytes;
  const sha256 = async (source: string) => hashBytes(new TextEncoder().encode(source));
  const uniqueToken = () => Zotero.Utilities.randomString(20);
  const canonical = (path: string, allowMissingFinal = false): string => {
    const target = file(path);
    const chain: any[] = [];
    let cursor = target;
    while (cursor) {
      chain.push(cursor.clone());
      const parent = cursor.parent;
      if (!parent || parent.path === cursor.path) break;
      cursor = parent;
    }
    for (const component of chain.reverse()) {
      if (component.exists() && component.isSymlink()) throw new Error(`symlink component: ${component.path}`);
    }
    if (!target.exists()) {
      if (!allowMissingFinal) throw new Error(`missing path: ${path}`);
      const missing: string[] = [];
      let ancestor = target;
      while (!ancestor.exists()) {
        missing.unshift(ancestor.leafName);
        const parent = ancestor.parent;
        if (!parent || parent.path === ancestor.path) throw new Error(`no existing ancestor: ${path}`);
        ancestor = parent;
      }
      return PathUtils.join(canonical(ancestor.path), ...missing);
    }
    target.normalize();
    return target.path;
  };
  const recoverCASArtifacts = async (directory: string): Promise<void> => {
    canonical(input.root());
    canonical(file(directory).parent.path);
    canonical(directory);
    const children: string[] = await IOUtils.getChildren(directory);
    const backupPattern = /^(.*\.qmd)\.qlab-cas-backup-([a-f0-9]{64})-([a-f0-9]{64})-[A-Za-z0-9]+$/u;
    const backups: Array<{
      artifactPath: string;
      targetPath: string;
      expectedRevision: string;
      replacementRevision: string;
    }> = [];
    for (const artifactPath of children.sort()) {
      const match = backupPattern.exec(artifactPath);
      if (!match) continue; // temp and unrelated ignored artifacts are never rendered as Drafts
      const targetPath = match[1]!;
      const expectedRevision = match[2]!;
      const replacementRevision = match[3]!;
      canonical(input.root());
      canonical(directory);
      canonical(artifactPath);
      const artifactRevision = await sha256(await IOUtils.readUTF8(artifactPath));
      if (artifactRevision !== expectedRevision) {
        throw new AIContextRecoveryRequiredError(
          artifactPath,
          "the quarantined inode changed after the pathname CAS linearization point",
        );
      }
      backups.push({ artifactPath, targetPath, expectedRevision, replacementRevision });
    }
    for (const targetPath of new Set(backups.map((backup) => backup.targetPath))) {
      if (await IOUtils.exists(targetPath)) continue;
      const chain = backups.filter((backup) => backup.targetPath === targetPath);
      const expected = new Set(chain.map((backup) => backup.expectedRevision));
      const terminal = chain.filter((backup) => !expected.has(backup.replacementRevision));
      if (terminal.length !== 1) {
        throw new AIContextRecoveryRequiredError(
          chain[0]!.artifactPath,
          "cannot identify one terminal orphan in the quarantine revision chain",
        );
      }
      try { await IOUtils.move(terminal[0]!.artifactPath, targetPath, { noOverwrite: true }); }
      catch {
        if (!await IOUtils.exists(targetPath)) {
          throw new AIContextRecoveryRequiredError(terminal[0]!.artifactPath, "orphan restore failed");
        }
      }
    }
  };
  return {
    root: input.root,
    userLibraryID: () => Zotero.Libraries.userLibraryID,
    listChildren: (path) => IOUtils.getChildren(path),
    exists: (path) => IOUtils.exists(path),
    makeDirectory: async (path, options) => {
      await IOUtils.makeDirectory(path, {
        createAncestors: options.createAncestors,
        ignoreExisting: false,
      });
    },
    readUTF8: (path) => IOUtils.readUTF8(path),
    sha256,
    uniqueToken,
    recoverCASArtifacts,
    async writeAtomic(path, source, expectedRevision) {
      const parent = file(path).parent.path;
      // No exists/list/temp write occurs before root, parent, and directory
      // canonical checks plus recovery of an interrupted previous operation.
      canonical(input.root());
      canonical(parent);
      await recoverCASArtifacts(parent);
      canonical(input.root());
      canonical(parent);
      const token = uniqueToken();
      const replacementRevision = await sha256(source);
      const temporary = `${path}.qlab-cas-temp-${token}`;
      const quarantine = expectedRevision === null
        ? null
        : `${path}.qlab-cas-backup-${expectedRevision}-${replacementRevision}-${token}`;
      await IOUtils.writeUTF8(temporary, source);
      await IOUtils.setPermissions(temporary, 0o600);
      try {
        canonical(input.root());
        canonical(file(path).parent.path);
        canonical(temporary);
        if (expectedRevision === null) {
          try {
            await IOUtils.move(temporary, path, { noOverwrite: true });
            return true;
          }
          catch {
            // A concurrent creator owns target; never overwrite it.
            return false;
          }
        }

        const beforeLinearization = await sha256(await IOUtils.readUTF8(path));
        if (beforeLinearization !== expectedRevision) return false;

        // This successful target -> quarantine rename is the pathname CAS
        // linearization point. Mutations visible before it conflict below.
        try { await IOUtils.move(path, quarantine!, { noOverwrite: true }); }
        catch { return false; }

        const restoreQuarantine = async (): Promise<void> => {
          if (!await IOUtils.exists(quarantine!)) return;
          try { await IOUtils.move(quarantine!, path, { noOverwrite: true }); }
          catch {
            // A concurrent target wins. Keep the non-.qmd quarantine as
            // recovery evidence instead of deleting either byte stream.
          }
        };

        const quarantinedRevision = await sha256(await IOUtils.readUTF8(quarantine!));
        if (quarantinedRevision !== expectedRevision) {
          await restoreQuarantine();
          return false;
        }
        // Rehash immediately before publish: an external descriptor may have
        // written the quarantined inode after the first hash.
        const finalQuarantinedRevision = await sha256(await IOUtils.readUTF8(quarantine!));
        if (finalQuarantinedRevision !== expectedRevision) {
          await restoreQuarantine();
          return false;
        }
        try { await IOUtils.move(temporary, path, { noOverwrite: true }); }
        catch {
          // A concurrent target appeared after quarantine. Preserve it and
          // preserve quarantine; callers receive false and retry from disk.
          return false;
        }
        // Success deliberately retains the ignored quarantine. A write through
        // an old open descriptor after this return cannot synchronously change
        // this call's result; the next list/snapshot/write hashes the artifact
        // and fails closed with its exact path if divergence is observed.
        return true;
      }
      finally {
        if (await IOUtils.exists(temporary)) await IOUtils.remove(temporary);
      }
    },
    canonical,
    itemByID: async (itemID) => {
      const loaded = await Zotero.Items.getAsync(itemID);
      return Array.isArray(loaded) ? loaded[0] : loaded;
    },
    itemByLibraryAndKey: async (libraryID, itemKey) => {
      const asynchronous = Zotero.Items.getByLibraryAndKeyAsync;
      if (typeof asynchronous === "function") return asynchronous.call(Zotero.Items, libraryID, itemKey);
      return Zotero.Items.getByLibraryAndKey(libraryID, itemKey);
    },
    attachmentsFor: async (parent) => {
      const itemIDs = zoteroItem(parent).getAttachments!();
      const loaded = await Zotero.Items.getAsync(itemIDs);
      return Array.isArray(loaded) ? loaded : [loaded];
    },
    topLevelAttachments: async (libraryID) => (await Zotero.Items.getAll(libraryID, true))
      .filter((candidate: any) => candidate.isAttachment() && !candidate.parentID),
    attachmentPath: (attachment) => zoteroItem(attachment).getFilePath?.() ?? null,
    attachmentTitle: (attachment) => zoteroItem(attachment).getField?.("title") ?? "",
    linkFromFile: (options) => Zotero.Attachments.linkFromFile(options),
    saveAttachmentTitle: async (attachment, title) => {
      const candidate = attachment as any;
      const previousTitle = candidate.getField("title");
      candidate.setField("title", title);
      try { await candidate.saveTx(); }
      catch (error) {
        try { candidate.setField("title", previousTitle); }
        finally { throw error; }
      }
    },
  };
}

export function isQuickAIContextAttachmentCandidate(value: unknown): boolean {
  const candidate = zoteroItem(value);
  const path = candidate.getFilePath?.() ?? "";
  const title = candidate.getField?.("title") ?? "";
  return candidate.isLinkedFileAttachment?.() === true
    && /\.qmd$/iu.test(path)
    && /^(AI Context|Reading Context)\s*·\s+/u.test(title);
}

export async function resolveAIContextAttachment(
  runtime: ZoteroAIContextRuntime,
  value: unknown,
): Promise<AIContextAttachmentDescriptor> {
  if (!isQuickAIContextAttachmentCandidate(value)) throw new Error("not an AI Context linked attachment");
  const path = runtime.attachmentPath(value);
  if (!path) throw new Error("attachment has no local file");
  const root = runtime.canonical(runtime.root()).replace(/[\\/]+$/u, "");
  const canonical = runtime.canonical(path);
  const separator = root.includes("\\") ? "\\" : "/";
  if (!canonical.startsWith(`${root}${separator}`)) throw new Error("attachment is outside the selected root");
  const relativePath = canonical.slice(root.length + 1).replace(/\\/gu, "/");
  const safe = absoluteAIContextPath(runtime, relativePath);
  const source = await runtime.readUTF8(safe);
  return { item: value, relativePath, document: parseAIContextDocument(relativePath, source) };
}
