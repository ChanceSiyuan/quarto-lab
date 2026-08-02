import { afterEach, describe, expect, it, vi } from "vitest";
import {
  bindPendingLegacyThreads,
  classifyLegacyRoot,
  decodeStoredTargetPreferences,
  deriveRepositoryId,
  deriveSshEndpointId,
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
  version: 2,
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

function resolvedSshRecord() {
  return {
    kind: "ssh" as const,
    sshProfile: "qlab-gpu",
    root: "/srv/research-loop",
    canonicalRoot: "/srv/research-loop",
    acceptedHostKeyFingerprint: "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    endpointId: "e".repeat(64),
    hostInstanceId: "22222222-2222-4222-8222-222222222222",
    repositoryUuid: "11111111-1111-4111-8111-111111111111",
    repositoryId: "a".repeat(64),
    targetId: "b".repeat(64),
  };
}

it("derives an SSH endpoint only from the authenticated host key and helper host UUID", () => {
  let source = "";
  const endpointId = deriveSshEndpointId(
    "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "22222222-2222-4222-8222-222222222222",
    (bytes) => {
      source = new TextDecoder().decode(bytes);
      return "e".repeat(64);
    },
  );
  expect(endpointId).toBe("e".repeat(64));
  expect(source).toBe(
    [
      "ssh",
      "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
      "22222222-2222-4222-8222-222222222222",
    ].join("\0"),
  );
});

function validV1(overrides: Record<string, unknown> = {}): string {
  const activeOverrides = {
    repositoryId: overrides.repositoryId,
    targetId: overrides.targetId,
  };
  const { repositoryId: _repositoryId, targetId: _targetId, ...preferenceOverrides } = overrides;
  return JSON.stringify({
    version: 1,
    active: {
      kind: "local",
      root: "/local/research-loop",
      canonicalRoot: "/local/research-loop",
      repositoryId: activeOverrides.repositoryId ?? "c".repeat(64),
      targetId: activeOverrides.targetId ?? "d".repeat(64),
    },
    pendingCandidate: null,
    legacyUnassigned: [],
    migratedLegacy: false,
    ...preferenceOverrides,
  });
}

function candidate(canonicalRoot: string) {
  return { kind: "candidate", canonicalRoot, state: "partial" };
}

function legacy(threadId: string) {
  return { threadId, recordedCwd: "/gone", reason: "missing" };
}

function badSshId(): string {
  return JSON.stringify({
    version: 2,
    active: { ...resolvedSshRecord(), repositoryId: "not-an-id" },
    pendingCandidate: null,
    legacyUnassigned: [],
    migratedLegacy: false,
  });
}

function badSshFingerprint(): string {
  return JSON.stringify({
    version: 2,
    active: { ...resolvedSshRecord(), acceptedHostKeyFingerprint: "SHA256:padded=" },
    pendingCandidate: null,
    legacyUnassigned: [],
    migratedLegacy: false,
  });
}

function noncanonicalSshFingerprint(): string {
  return JSON.stringify({
    version: 2,
    active: { ...resolvedSshRecord(), acceptedHostKeyFingerprint: `SHA256:${"A".repeat(42)}z` },
    pendingCandidate: null,
    legacyUnassigned: [],
    migratedLegacy: false,
  });
}

function badSshUuid(): string {
  return JSON.stringify({
    version: 2,
    active: { ...resolvedSshRecord(), repositoryUuid: "not-a-uuid" },
    pendingCandidate: null,
    legacyUnassigned: [],
    migratedLegacy: false,
  });
}

function credentialBearingSshRecord(): string {
  return JSON.stringify({
    version: 2,
    active: { ...resolvedSshRecord(), password: "secret" },
    pendingCandidate: null,
    legacyUnassigned: [],
    migratedLegacy: false,
  });
}

function badPendingCandidate(): string {
  return JSON.stringify({
    version: 2,
    active: null,
    pendingCandidate: { kind: "candidate", canonicalRoot: "/local/new", state: "unknown" },
    legacyUnassigned: [],
    migratedLegacy: false,
  });
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

  it("restores a pending initialization folder as the display-safe QLab root", async () => {
    vi.stubGlobal("Services", {
      prefs: {
        getStringPref: (name: string, fallback: string) =>
          name.endsWith("libraryRoot") ? "/library" : fallback,
        getIntPref: (_name: string, fallback: number) => fallback,
        getBoolPref: (_name: string, fallback: boolean) => fallback,
      },
    });
    vi.stubGlobal("IOUtils", {
      exists: vi.fn(async (path: string) => path === "/pending"),
    });
    vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
    vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });
    const repositoryTargets: StoredTargetPreferences = {
      ...EMPTY_PREFERENCES,
      pendingCandidate: {
        kind: "candidate",
        canonicalRoot: "/pending",
        state: "empty",
        eligibleLegacyThreads: [],
      },
      migratedLegacy: true,
    };

    const settings = await loadSettings({
      legacyQLabRoot: "/stale",
      repositoryTargetsRaw: JSON.stringify(repositoryTargets),
    });

    expect(settings.qlabRoot).toBe("/pending");
    expect(settings.repositoryTargets.pendingCandidate?.canonicalRoot).toBe("/pending");
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

  it("round-trips one resolved SSH target while preserving migration fields", () => {
    const stored = decodeStoredTargetPreferences(JSON.stringify({
      version: 2,
      active: resolvedSshRecord(),
      pendingCandidate: { kind: "candidate", canonicalRoot: "/local/new", state: "partial" },
      legacyUnassigned: [{ threadId: "t", recordedCwd: "/gone", reason: "missing" }],
      migratedLegacy: true,
    }));

    expect(stored).toMatchObject({ rewrite: null, preferences: {
      active: {
        kind: "ssh",
        sshProfile: "qlab-gpu",
        canonicalRoot: "/srv/research-loop",
        acceptedHostKeyFingerprint: "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
      },
      pendingCandidate: { canonicalRoot: "/local/new", state: "partial" },
      legacyUnassigned: [{ threadId: "t", reason: "missing" }],
      migratedLegacy: true,
    }});
  });

  it("migrates a valid v1 record without changing identity or legacy state", () => {
    const decoded = decodeStoredTargetPreferences(validV1({
      repositoryId: "a".repeat(64),
      targetId: "b".repeat(64),
      pendingCandidate: candidate("/empty"),
      legacyUnassigned: [legacy("thread-1")],
      migratedLegacy: true,
    }));

    expect(decoded.rewrite).toBe("v1-to-v2");
    expect(decoded.preferences).toMatchObject({ version: 2, active: {
      repositoryId: "a".repeat(64),
      targetId: "b".repeat(64),
    }, pendingCandidate: { canonicalRoot: "/empty" },
    legacyUnassigned: [{ threadId: "thread-1" }], migratedLegacy: true });
  });

  it("persists a v1-to-v2 rewrite once before the next startup read", async () => {
    const writes: Array<readonly [string, string]> = [];
    vi.stubGlobal("Services", {
      prefs: {
        getStringPref: (name: string, fallback: string) => name.endsWith("libraryRoot") ? "/library" : fallback,
        getIntPref: (_name: string, fallback: number) => fallback,
        getBoolPref: (_name: string, fallback: boolean) => fallback,
        setStringPref: (name: string, value: string) => writes.push([name, value]),
      },
    });
    vi.stubGlobal("IOUtils", { exists: vi.fn(async (path: string) => path === "/library") });
    vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
    vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });

    const first = await loadSettings({ legacyQLabRoot: "/legacy", repositoryTargetsRaw: validV1() });
    expect(first.repositoryTargets.version).toBe(2);
    expect(writes).toEqual([["extensions.zotkit.repositoryTargets", expect.any(String)]]);
    expect(JSON.parse(writes[0]![1])).toMatchObject({ version: 2, active: {
      repositoryId: "c".repeat(64), targetId: "d".repeat(64),
    }});

    await loadSettings({ legacyQLabRoot: "/legacy", repositoryTargetsRaw: writes[0]![1] });
    expect(writes).toHaveLength(1);
  });

  it("does not probe an SSH root through local settings path checks", async () => {
    const checkedPaths: string[] = [];
    vi.stubGlobal("Services", {
      prefs: {
        getStringPref: (name: string, fallback: string) => name.endsWith("libraryRoot") ? "/library" : fallback,
        getIntPref: (_name: string, fallback: number) => fallback,
        getBoolPref: (_name: string, fallback: boolean) => fallback,
        setStringPref: vi.fn(),
      },
    });
    vi.stubGlobal("IOUtils", {
      exists: vi.fn(async (path: string) => {
        checkedPaths.push(path);
        return path === "/library";
      }),
    });
    vi.stubGlobal("Zotero", { Profile: { dir: "/profile" } });
    vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });

    const settings = await loadSettings({
      legacyQLabRoot: "/legacy",
      repositoryTargetsRaw: JSON.stringify({
        version: 2,
        active: resolvedSshRecord(),
        pendingCandidate: null,
        legacyUnassigned: [],
        migratedLegacy: true,
      }),
    });

    expect(settings.repositoryTargets.active?.kind).toBe("ssh");
    expect(settings.qlabRoot).toBe("");
    expect(checkedPaths).toEqual(["/library"]);
  });

  it.each([
    "{}", '{"version":3}', badSshId(), badSshFingerprint(), noncanonicalSshFingerprint(),
    badSshUuid(), credentialBearingSshRecord(), validV1({ password: "secret" }), badPendingCandidate(),
  ])("fails closed for %s", (raw) => {
    expect(decodeStoredTargetPreferences(raw)).toEqual({
      preferences: { version: 2, active: null, pendingCandidate: null, legacyUnassigned: [], migratedLegacy: false },
      rewrite: null,
    });
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
