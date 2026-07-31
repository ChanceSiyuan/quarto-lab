import { afterEach, describe, expect, it, vi } from "vitest";
import {
  bindPendingLegacyThreads,
  classifyLegacyRoot,
  deriveRepositoryId,
  deriveTargetId,
  migrateLegacy,
  parseStoredTargetPreferences,
  type LocalRepositoryInspection,
  type LegacyMigrationResolver,
  type ResolvedLocalRepositoryTarget,
  type StoredTargetPreferences,
} from "../src/repository-target";
import {
  loadSettings,
  readRawTargetMigrationInput,
} from "../src/settings";

afterEach(() => vi.unstubAllGlobals());

const EMPTY_PREFERENCES: StoredTargetPreferences = {
  version: 1,
  active: null,
  pendingCandidate: null,
  legacyUnassigned: [],
  migratedLegacy: false,
};

function emptyPreferences(): StoredTargetPreferences {
  return EMPTY_PREFERENCES;
}

function resolved(canonicalRoot: string): ResolvedLocalRepositoryTarget {
  return {
    kind: "local",
    root: canonicalRoot,
    canonicalRoot,
    repositoryId: "a".repeat(64),
    targetId: "b".repeat(64),
  };
}

function fakeMigrationResolver(state: "ready" | "empty" | "partial" | "missing" | "incompatible"): LegacyMigrationResolver & { inspect: ReturnType<typeof vi.fn> } {
  const inspection: LocalRepositoryInspection = state === "ready"
    ? resolved("/ready")
    : state === "empty" || state === "partial"
      ? { kind: "candidate", canonicalRoot: `/${state}`, state }
      : { kind: "unavailable", reason: state };
  return {
    inspect: vi.fn(async () => inspection),
    canonicalize: vi.fn(async (path: string) => path),
  };
}

describe("repository target identity", () => {
  it("reads raw legacy and malformed target preferences before path normalization", async () => {
    const preferenceReads: string[] = [];
    vi.stubGlobal("Services", {
      prefs: {
        getStringPref: (name: string, fallback: string) => {
          preferenceReads.push(name);
          if (name.endsWith("qlabRoot")) return "/missing-legacy";
          if (name.endsWith("repositoryTargets")) return "{malformed";
          if (name.endsWith("libraryRoot")) return "/library";
          return fallback;
        },
        getIntPref: (_name: string, fallback: number) => fallback,
        getBoolPref: (_name: string, fallback: boolean) => fallback,
      },
    });
    vi.stubGlobal("IOUtils", {
      exists: vi.fn(async (path: string) => path === "/library"),
    });
    vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
    vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });

    const raw = readRawTargetMigrationInput();
    expect(raw).toEqual({
      legacyQLabRoot: "/missing-legacy",
      repositoryTargetsRaw: "{malformed",
    });
    expect((globalThis as any).IOUtils.exists).not.toHaveBeenCalled();

    const settings = await loadSettings(raw);
    expect(settings.repositoryTargets).toEqual(emptyPreferences());
    expect(settings.qlabRoot).toBe("");
    expect(preferenceReads.filter((name) => name.endsWith("qlabRoot"))).toHaveLength(1);
    expect(preferenceReads.filter((name) => name.endsWith("repositoryTargets"))).toHaveLength(1);
  });

  it("derives IDs from exact NUL-delimited UTF-8 bytes through an injected digest", () => {
    const seen: Uint8Array[] = [];
    const digest = (bytes: Uint8Array) => { seen.push(bytes); return `d${seen.length}`.padEnd(64, "0"); };
    const repositoryId = deriveRepositoryId("local", "11111111-1111-4111-8111-111111111111", digest);
    const expectedRepositoryId = "d1".padEnd(64, "0");
    expect(repositoryId).toMatch(/^[a-f0-9]{64}$/);
    expect(deriveTargetId("local", "/real/A", repositoryId, digest))
      .not.toBe(deriveTargetId("local", "/real/B", repositoryId, digest));
    expect(seen.map((x) => new TextDecoder().decode(x))).toEqual([
      "local\u000011111111-1111-4111-8111-111111111111",
      `local\u0000/real/A\u0000${expectedRepositoryId}`,
      `local\u0000/real/B\u0000${expectedRepositoryId}`,
    ]);
  });

  it.each([
    ["ready", "bind"], ["empty", "candidate"], ["partial", "candidate"],
    ["missing", "unassigned"], ["incompatible", "unassigned"],
  ] as const)("classifies legacy %s roots as %s", (state, expected) => {
    expect(classifyLegacyRoot(state)).toBe(expected);
  });

  it("retains a pending candidate and Legacy/unassigned thread bindings without inventing an active target", () => {
    expect(parseStoredTargetPreferences('{"version":1,"active":null,"pendingCandidate":{"kind":"candidate","canonicalRoot":"/empty","state":"empty"},"legacyUnassigned":[{"threadId":"thread-1","recordedCwd":"/gone","reason":"missing"}],"migratedLegacy":true}'))
      .toMatchObject({ pendingCandidate: { canonicalRoot: "/empty", state: "empty" }, legacyUnassigned: [{ threadId: "thread-1", reason: "missing" }] });
  });

  it("rejects malformed and future persisted values as the empty preference shape", () => {
    const fallback = emptyPreferences();
    expect(parseStoredTargetPreferences("not json")).toEqual(fallback);
    expect(parseStoredTargetPreferences('{"version":2}')).toEqual(fallback);
    expect(parseStoredTargetPreferences('{"version":1,"active":{"kind":"remote","canonicalRoot":"/repo","repositoryId":"a"},"pendingCandidate":null,"legacyUnassigned":[],"migratedLegacy":false}')).toEqual(fallback);
    expect(parseStoredTargetPreferences(JSON.stringify({
      version: 1,
      active: { kind: "local", root: "/repo", canonicalRoot: "", repositoryId: "a".repeat(64), targetId: "b".repeat(64) },
      pendingCandidate: null,
      legacyUnassigned: [],
      migratedLegacy: false,
    }))).toEqual(fallback);
  });

  it("returns ready session assignments and defers candidate bindings until activation", async () => {
    const ready = await migrateLegacy(emptyPreferences(), { legacyRoot: "/ready", sessions: [{ threadId: "active", recordedCwd: null }], activeThreadId: "active" }, fakeMigrationResolver("ready"));
    expect(ready.preferences).toMatchObject({ active: { canonicalRoot: "/ready" }, legacyUnassigned: [] });
    expect(ready.sessions).toContainEqual(expect.objectContaining({ threadId: "active", targetId: expect.any(String) }));
    const candidate = await migrateLegacy(emptyPreferences(), { legacyRoot: "/partial", sessions: [{ threadId: "inside", recordedCwd: "/partial/drafts/a.qmd" }, { threadId: "outside", recordedCwd: "/elsewhere/a.qmd" }], activeThreadId: null }, fakeMigrationResolver("partial"));
    expect(candidate.preferences.pendingCandidate).toMatchObject({ eligibleLegacyThreads: [{ threadId: "inside" }] });
    expect(candidate.sessions).not.toContainEqual(expect.objectContaining({ threadId: "inside", targetId: expect.anything() }));
    expect(await bindPendingLegacyThreads(candidate.preferences, candidate.sessions, resolved("/partial"), fakeMigrationResolver("ready")))
      .toMatchObject({ preferences: { active: { canonicalRoot: "/partial" }, legacyUnassigned: [{ threadId: "outside", reason: "different-root" }] }, sessions: expect.arrayContaining([expect.objectContaining({ threadId: "inside", targetId: expect.any(String) })]) });
  });

  it("migrates ready, candidate, and unassigned roots once without calling the resolver again", async () => {
    expect(await migrateLegacy(emptyPreferences(), { legacyRoot: "/ready", sessions: [{ threadId: "t", recordedCwd: "/ready/drafts/a.qmd" }], activeThreadId: null }, fakeMigrationResolver("ready")))
      .toMatchObject({ preferences: { active: { canonicalRoot: "/ready" }, pendingCandidate: null, legacyUnassigned: [] }, sessions: [expect.objectContaining({ threadId: "t", targetId: expect.any(String) })] });
    expect(await migrateLegacy(emptyPreferences(), { legacyRoot: "/partial", sessions: [], activeThreadId: null }, fakeMigrationResolver("partial")))
      .toMatchObject({ preferences: { active: null, pendingCandidate: { canonicalRoot: "/partial", state: "partial" } }, sessions: [] });
    const first = await migrateLegacy(emptyPreferences(), { legacyRoot: "/gone", sessions: [{ threadId: "t", recordedCwd: "/gone/a.qmd" }], activeThreadId: null }, fakeMigrationResolver("missing"));
    const resolver = fakeMigrationResolver("missing");
    expect(await migrateLegacy(first.preferences, { legacyRoot: "/gone", sessions: first.sessions, activeThreadId: null }, resolver)).toEqual(first);
    expect(resolver.inspect).not.toHaveBeenCalled();
  });

  it("preserves generic session data and marks nonmatching ready sessions once", async () => {
    const outcome = await migrateLegacy(emptyPreferences(), {
      legacyRoot: "/ready",
      sessions: [
        { threadId: "inside", recordedCwd: "/ready/knowledge/a.qmd", label: "keep me" },
        { threadId: "outside", recordedCwd: "/ready-too/f.qmd", label: "different" },
      ],
      activeThreadId: null,
    }, fakeMigrationResolver("ready"));
    expect(outcome.sessions).toContainEqual(expect.objectContaining({ threadId: "inside", label: "keep me", targetId: "b".repeat(64) }));
    expect(outcome.sessions).toContainEqual(expect.objectContaining({ threadId: "outside", label: "different" }));
    expect(outcome.preferences.legacyUnassigned).toEqual([{ threadId: "outside", recordedCwd: "/ready-too/f.qmd", reason: "different-root" }]);
  });
});
