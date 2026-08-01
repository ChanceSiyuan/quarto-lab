import { describe, expect, it, vi } from "vitest";

import { buildCompanionCapsule, canonicalCompanionCapsuleJson } from "../src/chatgpt-companion-capsule";
import {
  createCompanionCapsuleStorage,
  createGeckoCompanionCapsuleFilesystem,
  type CompanionCapsuleFilesystem,
} from "../src/chatgpt-companion-store";

const hash = (value: string) => `checksum:${value.length}:${value.slice(0, 12)}`;
const now = () => new Date("2026-08-01T12:00:00.000Z");

function capsule(createdAt = "2026-08-01T11:00:00.000Z") {
  return buildCompanionCapsule({
    question: "Explain this result.",
    contextItems: [{ id: "paper", kind: "paper", sourceIdentity: "zotero:ABCD1234" }],
    paper: { title: "A paper" },
  }, {
    id: () => "capsule_0123456789abcdef",
    now: () => createdAt,
    hash,
  });
}

function memoryFilesystem(): CompanionCapsuleFilesystem & { files: Map<string, unknown> } {
  const files = new Map<string, unknown>();
  return {
    files,
    write: async (id, value) => { files.set(id, structuredClone(value)); },
    read: async (id) => structuredClone(files.get(id) ?? null),
    remove: async (id) => { files.delete(id); },
    list: async () => [...files.keys()],
  };
}

describe("Companion capsule storage", () => {
  it("rejects a path-shaped ID before any storage operation", async () => {
    const filesystem = memoryFilesystem();
    const store = createCompanionCapsuleStorage({ filesystem, hash, now });

    await expect(store.load("../private")).resolves.toBeNull();
    await expect(store.delete("/private")).resolves.toBe(false);
    await expect(store.save({ ...capsule(), id: "../private" })).rejects.toThrow(/opaque identifier/i);
    expect(filesystem.files).toEqual(new Map());
  });

  it("rejects malformed and checksum-corrupted stored capsules", async () => {
    const filesystem = memoryFilesystem();
    const store = createCompanionCapsuleStorage({ filesystem, hash, now });
    const valid = capsule();
    filesystem.files.set(valid.id, { ...valid, extra: "not part of the capsule schema" });
    await expect(store.load(valid.id)).resolves.toBeNull();

    filesystem.files.set(valid.id, { ...valid, question: "corrupted" });
    await expect(store.load(valid.id)).resolves.toBeNull();

    const oversized = {
      ...valid,
      warnings: Array.from({ length: 160 }, () => "w".repeat(2_048)),
    };
    const { contentHash: _oldChecksum, ...unsigned } = oversized;
    filesystem.files.set(valid.id, { ...unsigned, contentHash: hash(canonicalCompanionCapsuleJson(unsigned)) });
    await expect(store.load(valid.id)).resolves.toBeNull();
  });

  it("does not return expired capsules and prunes only valid expired IDs", async () => {
    const filesystem = memoryFilesystem();
    const store = createCompanionCapsuleStorage({ filesystem, hash, now });
    const expired = capsule("2026-06-30T11:59:59.999Z");
    const current = { ...capsule(), id: "capsule_0123456789abcdeg" };
    const signedCurrent = buildCompanionCapsule({
      question: "Explain this result.",
      contextItems: [{ id: "paper", kind: "paper", sourceIdentity: "zotero:ABCD1234" }],
      paper: { title: "A paper" },
    }, { id: () => current.id, now: () => "2026-08-01T11:00:00.000Z", hash });
    filesystem.files.set(expired.id, expired);
    filesystem.files.set(signedCurrent.id, signedCurrent);
    filesystem.files.set("../untrusted", expired);

    await expect(store.load(expired.id)).resolves.toBeNull();
    await expect(store.pruneExpired()).resolves.toBe(1);
    expect(filesystem.files.has(expired.id)).toBe(false);
    expect(filesystem.files.has(signedCurrent.id)).toBe(true);
    expect(filesystem.files.has("../untrusted")).toBe(true);
  });

  it("returns deep-frozen clones and deletes an explicit valid capsule", async () => {
    const filesystem = memoryFilesystem();
    const store = createCompanionCapsuleStorage({ filesystem, hash, now });
    const stored = capsule();
    await store.save(stored);
    const loaded = await store.load(stored.id);

    expect(loaded).not.toBe(stored);
    expect(loaded).toEqual(stored);
    expect(Object.isFrozen(loaded)).toBe(true);
    expect(Object.isFrozen(loaded?.contextItems)).toBe(true);
    expect(Object.isFrozen(loaded?.contextItems[0])).toBe(true);
    expect(() => { (loaded as any).contextItems[0].id = "changed"; }).toThrow(TypeError);
    await expect(store.delete(stored.id)).resolves.toBe(true);
    await expect(store.load(stored.id)).resolves.toBeNull();
  });

  it("round-trips a valid capsule with an external secondary-paper citation", async () => {
    const filesystem = memoryFilesystem();
    const store = createCompanionCapsuleStorage({ filesystem, hash, now });
    const stored = buildCompanionCapsule({
      question: "Compare these papers.",
      contextItems: [{ id: "secondary", kind: "external-paper", sourceIdentity: "paper-2", mode: "full" }],
      secondaryPapers: [{ id: "paper-2", title: "Second paper", mode: "full" }],
    }, { id: () => "capsule_0123456789abcdef", now: () => "2026-08-01T11:00:00.000Z", hash });

    await store.save(stored);
    await expect(store.load(stored.id)).resolves.toEqual(stored);
  });
});

describe("Gecko companion capsule filesystem", () => {
  it("uses a private directory and temp-to-final JSON move", async () => {
    const makeDirectory = vi.fn(async () => {});
    const writeJSON = vi.fn(async () => {});
    const move = vi.fn(async () => {});
    const setPermissions = vi.fn(async () => {});
    const ioUtils = {
      makeDirectory,
      writeJSON,
      move,
      setPermissions,
      readJSON: vi.fn(async () => null),
      remove: vi.fn(async () => {}),
      getChildren: vi.fn(async () => []),
    };
    vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
    vi.stubGlobal("PathUtils", {
      join: (...parts: string[]) => parts.join("/"),
      filename: (path: string) => path.split("/").at(-1),
    });
    const filesystem = createGeckoCompanionCapsuleFilesystem(ioUtils);

    await filesystem.write("capsule_0123456789abcdef", { schemaVersion: 1 });

    expect(makeDirectory).toHaveBeenCalledWith("/profile/zotkit/companion-capsules", {
      createAncestors: true,
      ignoreExisting: true,
      permissions: 0o700,
    });
    expect(setPermissions).toHaveBeenCalledWith("/profile/zotkit/companion-capsules", 0o700, false);
    expect(writeJSON).toHaveBeenCalledWith(
      "/profile/zotkit/companion-capsules/capsule_0123456789abcdef.tmp",
      { schemaVersion: 1 },
    );
    expect(setPermissions).toHaveBeenCalledWith(
      "/profile/zotkit/companion-capsules/capsule_0123456789abcdef.tmp",
      0o600,
      false,
    );
    expect(move).toHaveBeenCalledWith(
      "/profile/zotkit/companion-capsules/capsule_0123456789abcdef.tmp",
      "/profile/zotkit/companion-capsules/capsule_0123456789abcdef.json",
      { noOverwrite: false },
    );
    expect(setPermissions).toHaveBeenCalledWith(
      "/profile/zotkit/companion-capsules/capsule_0123456789abcdef.json",
      0o600,
      false,
    );
    vi.unstubAllGlobals();
  });
});
