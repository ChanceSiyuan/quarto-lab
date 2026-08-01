import {
  COMPANION_CAPSULE_BOUNDS,
  type ChatGPTCompanionCapsule,
  verifyCompanionCapsule,
} from "./chatgpt-companion-capsule";
import { profilePath } from "./platform";

const OPAQUE_ID = /^[A-Za-z0-9_-]{16,128}$/;
const DAY_MS = 24 * 60 * 60 * 1000;
const MAX_SERIALIZED_BYTES = 256 * 1024;
const CONTEXT_KINDS = new Set(["paper", "page", "selection", "annotation", "library", "external-paper", "screenshot", "draft"]);
const AUTHORITIES = new Set(["external_evidence", "unreviewed_draft", "unsupported"]);

export interface CompanionCapsuleFilesystem {
  write(id: string, value: unknown): Promise<void>;
  read(id: string): Promise<unknown | null>;
  remove(id: string): Promise<void>;
  list(): Promise<string[]>;
}

export interface CompanionCapsuleStorage {
  save(capsule: ChatGPTCompanionCapsule): Promise<void>;
  load(id: string): Promise<ChatGPTCompanionCapsule | null>;
  delete(id: string): Promise<boolean>;
  pruneExpired(): Promise<number>;
}

export interface CompanionCapsuleStoreDependencies {
  filesystem: CompanionCapsuleFilesystem;
  hash: (canonicalJson: string) => string;
  now: () => Date;
}

interface GeckoCompanionCapsuleIo {
  makeDirectory?(path: string, options?: {
    createAncestors?: boolean;
    ignoreExisting?: boolean;
    permissions?: number;
  }): Promise<void>;
  writeJSON?(path: string, value: unknown): Promise<void>;
  readJSON?(path: string): Promise<unknown>;
  move?(source: string, destination: string, options?: { noOverwrite?: boolean }): Promise<void>;
  remove?(path: string, options?: { ignoreAbsent?: boolean }): Promise<void>;
  getChildren?(path: string): Promise<string[]>;
  setPermissions?(path: string, permissions: number, honorUmask?: boolean): Promise<void>;
}

function validId(value: unknown): value is string {
  return typeof value === "string" && OPAQUE_ID.test(value);
}

function requireId(value: unknown): asserts value is string {
  if (!validId(value)) throw new Error("Companion capsule IDs must be opaque identifiers");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function exactRecord(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  return isRecord(value)
    && Object.keys(value).length === keys.length
    && keys.every((key) => Object.hasOwn(value, key));
}

function stringAtMost(value: unknown, maximum: number): value is string {
  return typeof value === "string" && Array.from(value).length <= maximum;
}

function optionalString(value: unknown, maximum: number): boolean {
  return value === null || stringAtMost(value, maximum);
}

function positiveInteger(value: unknown): boolean {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function sameBounds(value: unknown): boolean {
  const keys = Object.keys(COMPANION_CAPSULE_BOUNDS);
  return exactRecord(value, keys)
    && keys.every((key) => value[key] === COMPANION_CAPSULE_BOUNDS[key as keyof typeof COMPANION_CAPSULE_BOUNDS]);
}

function canonicalDate(value: unknown): value is string {
  if (!stringAtMost(value, COMPANION_CAPSULE_BOUNDS.timestamp)) return false;
  const date = new Date(value);
  return !Number.isNaN(date.getTime()) && value.endsWith("Z") && date.toISOString() === value;
}

function externalCitationFields(value: unknown): value is Record<string, unknown> {
  return isRecord(value)
    && value.authority === "external_evidence"
    && stringAtMost(value.title, COMPANION_CAPSULE_BOUNDS.citationTitle)
    && stringAtMost(value.creators, COMPANION_CAPSULE_BOUNDS.citationCreators)
    && stringAtMost(value.year, COMPANION_CAPSULE_BOUNDS.citationYear)
    && stringAtMost(value.doi, COMPANION_CAPSULE_BOUNDS.citationDoi)
    && stringAtMost(value.url, COMPANION_CAPSULE_BOUNDS.citationUrl);
}

function externalCitation(value: unknown): boolean {
  return exactRecord(value, ["authority", "title", "creators", "year", "doi", "url"])
    && externalCitationFields(value);
}

function exactCapsule(value: unknown): value is ChatGPTCompanionCapsule {
  if (!exactRecord(value, [
    "schemaVersion", "id", "createdAt", "subject", "question", "contextItems", "paper", "page", "selection",
    "secondaryPapers", "draft", "screenshotProvenance", "warnings", "bounds", "contentHash",
  ]) || value.schemaVersion !== 1 || !validId(value.id) || !canonicalDate(value.createdAt)
    || !stringAtMost(value.question, COMPANION_CAPSULE_BOUNDS.question)
    || !stringAtMost(value.contentHash, COMPANION_CAPSULE_BOUNDS.contentHash)
    || !exactRecord(value.subject, ["paperKey", "draftPath"])
    || !optionalString(value.subject.paperKey, COMPANION_CAPSULE_BOUNDS.paperKey)
    || !optionalString(value.subject.draftPath, COMPANION_CAPSULE_BOUNDS.draftPath)
    || !sameBounds(value.bounds)
    || !Array.isArray(value.contextItems) || value.contextItems.length > COMPANION_CAPSULE_BOUNDS.contextItems
    || !Array.isArray(value.secondaryPapers) || value.secondaryPapers.length > COMPANION_CAPSULE_BOUNDS.secondaryPapers
    || !Array.isArray(value.screenshotProvenance) || value.screenshotProvenance.length > COMPANION_CAPSULE_BOUNDS.screenshotProvenance
    || !Array.isArray(value.warnings) || value.warnings.some((warning) => !stringAtMost(warning, 2_048))) return false;

  if (!value.contextItems.every((item) => exactRecord(item, ["id", "kind", "included", "supported", "sourceIdentity", "mode", "authority", "warning"])
    && stringAtMost(item.id, COMPANION_CAPSULE_BOUNDS.chipId)
    && typeof item.kind === "string" && CONTEXT_KINDS.has(item.kind)
    && typeof item.included === "boolean" && typeof item.supported === "boolean"
    && stringAtMost(item.sourceIdentity, COMPANION_CAPSULE_BOUNDS.sourceIdentity)
    && (item.mode === null || item.mode === "retrieval" || item.mode === "full")
    && typeof item.authority === "string" && AUTHORITIES.has(item.authority)
    && (item.warning === null || stringAtMost(item.warning, 2_048)))) return false;

  if (value.paper !== null && !externalCitation(value.paper)) return false;
  if (value.page !== null && (!exactRecord(value.page, ["authority", "pageNumber", "pageLabel", "excerpt", "source"])
    || value.page.authority !== "external_evidence" || !positiveInteger(value.page.pageNumber)
    || !stringAtMost(value.page.pageLabel, COMPANION_CAPSULE_BOUNDS.pageLabel)
    || !stringAtMost(value.page.excerpt, COMPANION_CAPSULE_BOUNDS.pageExcerpt)
    || !stringAtMost(value.page.source, COMPANION_CAPSULE_BOUNDS.pageSource))) return false;
  if (value.selection !== null && (!exactRecord(value.selection, ["authority", "text", "pageNumber"])
    || value.selection.authority !== "external_evidence" || !stringAtMost(value.selection.text, COMPANION_CAPSULE_BOUNDS.selection)
    || (value.selection.pageNumber !== null && !positiveInteger(value.selection.pageNumber)))) return false;
  if (!value.secondaryPapers.every((paper) => exactRecord(paper, ["authority", "title", "creators", "year", "doi", "url", "mode"])
    && externalCitationFields(paper)
    && (paper.mode === "retrieval" || paper.mode === "full"))) return false;
  if (value.draft !== null && (!exactRecord(value.draft, ["relativePath", "authority", "excerpt", "truncated"])
    || !stringAtMost(value.draft.relativePath, COMPANION_CAPSULE_BOUNDS.draftPath)
    || value.draft.authority !== "unreviewed_draft" || !stringAtMost(value.draft.excerpt, COMPANION_CAPSULE_BOUNDS.draftExcerpt)
    || typeof value.draft.truncated !== "boolean")) return false;
  return value.screenshotProvenance.every((entry) => exactRecord(entry, ["authority", "kind", "paperTitle", "pageNumber"])
    && entry.authority === "external_evidence" && (entry.kind === "page" || entry.kind === "region")
    && stringAtMost(entry.paperTitle, COMPANION_CAPSULE_BOUNDS.screenshotTitle)
    && (entry.pageNumber === null || positiveInteger(entry.pageNumber)));
}

function cloneAndFreeze(capsule: ChatGPTCompanionCapsule): ChatGPTCompanionCapsule {
  const clone = JSON.parse(JSON.stringify(capsule)) as ChatGPTCompanionCapsule;
  const freeze = (value: unknown): void => {
    if (!value || typeof value !== "object" || Object.isFrozen(value)) return;
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  };
  freeze(clone);
  return clone;
}

function serializedWithinBound(value: unknown): boolean {
  try {
    return new TextEncoder().encode(JSON.stringify(value)).byteLength <= MAX_SERIALIZED_BYTES;
  }
  catch {
    return false;
  }
}

function expired(capsule: ChatGPTCompanionCapsule, now: Date): boolean {
  return now.getTime() - new Date(capsule.createdAt).getTime() > 30 * DAY_MS;
}

function usableCapsule(value: unknown, hash: CompanionCapsuleStoreDependencies["hash"]): value is ChatGPTCompanionCapsule {
  return serializedWithinBound(value) && exactCapsule(value) && verifyCompanionCapsule(value, hash);
}

/** Pure persistence policy; its filesystem has no caller-controlled paths. */
export function createCompanionCapsuleStorage(dependencies: CompanionCapsuleStoreDependencies): CompanionCapsuleStorage {
  const loadStored = async (id: string): Promise<ChatGPTCompanionCapsule | null> => {
    const stored = await dependencies.filesystem.read(id);
    return usableCapsule(stored, dependencies.hash) ? stored : null;
  };

  return {
    async save(capsule) {
      requireId(capsule?.id);
      if (!usableCapsule(capsule, dependencies.hash)) throw new Error("Refusing to persist an invalid companion capsule");
      await dependencies.filesystem.write(capsule.id, cloneAndFreeze(capsule));
    },
    async load(id) {
      if (!validId(id)) return null;
      const stored = await loadStored(id);
      if (!stored || expired(stored, dependencies.now())) return null;
      return cloneAndFreeze(stored);
    },
    async delete(id) {
      if (!validId(id)) return false;
      await dependencies.filesystem.remove(id);
      return true;
    },
    async pruneExpired() {
      let count = 0;
      for (const id of await dependencies.filesystem.list()) {
        if (!validId(id)) continue;
        const stored = await loadStored(id);
        if (stored && expired(stored, dependencies.now())) {
          await dependencies.filesystem.remove(id);
          count += 1;
        }
      }
      return count;
    },
  };
}

/** Gecko adapter. Every filename is derived from an already-validated opaque ID. */
export function createGeckoCompanionCapsuleFilesystem(io: GeckoCompanionCapsuleIo): CompanionCapsuleFilesystem {
  if (!io.makeDirectory || !io.writeJSON || !io.readJSON || !io.move || !io.remove || !io.getChildren || !io.setPermissions) {
    throw new Error("Gecko companion capsule storage is unavailable");
  }
  const root = profilePath("companion-capsules");
  const target = (id: string): string => {
    requireId(id);
    return PathUtils.join(root, `${id}.json`);
  };
  const temporary = (id: string): string => {
    requireId(id);
    return PathUtils.join(root, `${id}.tmp`);
  };
  const ensureDirectory = async (): Promise<void> => {
    await io.makeDirectory!(root, { createAncestors: true, ignoreExisting: true, permissions: 0o700 });
    await io.setPermissions!(root, 0o700, false);
  };
  return {
    async write(id, value) {
      requireId(id);
      await ensureDirectory();
      const tmp = temporary(id);
      const final = target(id);
      await io.writeJSON!(tmp, value);
      await io.setPermissions!(tmp, 0o600, false);
      await io.move!(tmp, final, { noOverwrite: false });
      await io.setPermissions!(final, 0o600, false);
    },
    async read(id) {
      requireId(id);
      try { return await io.readJSON!(target(id)); }
      catch { return null; }
    },
    async remove(id) {
      requireId(id);
      await io.remove!(target(id), { ignoreAbsent: true });
    },
    async list() {
      try {
        const children = await io.getChildren!(root);
        return children
          .map((path) => path.split(/[\\/]/u).at(-1) || "")
          .filter((name) => name.endsWith(".json"))
          .map((name) => name.slice(0, -".json".length));
      }
      catch { return []; }
    },
  };
}
