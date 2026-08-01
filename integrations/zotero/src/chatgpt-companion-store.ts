import { type ChatGPTCompanionCapsule, verifyCompanionCapsule } from "./chatgpt-companion-capsule";
import { profilePath } from "./platform";

const OPAQUE_ID = /^[A-Za-z0-9_-]{16,128}$/;
const DAY_MS = 24 * 60 * 60 * 1000;
const MAX_SERIALIZED_BYTES = 256 * 1024;

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
  return serializedWithinBound(value) && verifyCompanionCapsule(value, hash);
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
