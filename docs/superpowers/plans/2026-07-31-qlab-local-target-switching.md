# QLab Local Target Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mutable local `qlabRoot` setting with an identity-backed local repository target and make a root change an atomic switch of every QLab-owned surface.

**Architecture:** A small target domain owns canonical local roots, private repository identity, persistence, and legacy migration. `RepositoryTargetController` stages a complete target snapshot behind a monotonic attempt ID and epoch, persists it before one synchronous publication, then disposes old target resources. Codex, terminal, QMD, and Main Site receive an explicit target binding rather than reading a global root preference during asynchronous work.

**Tech Stack:** TypeScript 7, Vitest 4, Zotero/Gecko APIs (`IOUtils`, `PathUtils`, `Services`), existing `NativeBridge`, Node/npm, Git, Quarto.

## Global Constraints

- Implement only in `integrations/zotero`; do not modify the preserved dashboard source or generated `public/knowledge/` output.
- Slice 1 supports local targets only; it must not introduce SSH selection, remote filesystem access, Remote-SSH editor launch, or remote process execution.
- A selectable active target is a valid local Research Loop Git repository; an empty or partial folder is a pre-target candidate and never becomes active before confirmed initialization and identity creation.
- Resolve a repository UUID through `git rev-parse --git-path qlab/repository-id`; store it in Git-private state mode `0600`, never in the work tree, Git index, Zotero preference, logs, or prompts.
- `repositoryId` is the SHA-256 digest of the local endpoint ID and repository UUID; `targetId` additionally includes canonical root. Path strings and UI labels are not identities.
- Migrate legacy `qlabRoot` exactly once: ready Git repository binds eligible sessions; empty/partial becomes a pending candidate; missing/inaccessible/incompatible produces no active target and leaves sessions Legacy / unassigned.
- Target selection is atomic: pre-commit failures retain the complete old active snapshot; post-commit surface failures remain on the new target and are marked degraded; late callbacks must reject mismatched `(targetId, targetEpoch)`.
- Never retarget a running Codex turn with `turn/steer`; switching requires Stop response and switch or Cancel. An unsaved QMD source or pending Keep blocks the switch.
- `knowledge/**/*.qmd` remains trusted-only; Draft changes stay in the existing working-copy/Keep flow, and every Quarto invocation retains `--no-execute`.
- Main Site remains on-demand. Switching stops an old local Main Site session; activating a target must not install dependencies, build, start a server, or allocate a port.
- Use test-first commits. On Linux, run `npm run check && npm test && npm run native:test` only after Task 0 has removed the known `/usr/bin/zip` and `<util.h>` portability failures. `npm run build` and `npm run verify` remain macOS release gates because `native/scripts/build-universal.sh` requires `xcrun`, `lipo`, and `codesign`; do not report either as passing on Linux.

---

## File Structure

- `integrations/zotero/src/repository-target.ts`: local target value types, stable ID derivation, versioned preference codec, and pure legacy classification.
- `integrations/zotero/src/local-repository-target-resolver.ts`: canonical local-root validation, Git-private UUID lifecycle, and confirmed candidate initialization.
- `integrations/zotero/src/repository-target-controller.ts`: serializable attempt/epoch switch transaction and target-resource lifecycle contract.
- `integrations/zotero/src/settings.ts`, `prefs.js`: versioned target preference and one-time legacy migration storage; remove business use of a naked root setting.
- `integrations/zotero/src/codex-service.ts`: target-bound threads, workspace objects, turns, and writable roots.
- `integrations/zotero/src/terminal-panel.ts`: target-tagged PTY sessions and explicit target disposal.
- `integrations/zotero/src/qmd-workspace.ts`, `qmd-visual-editor.ts`: switch blockers, target-tagged workspace callbacks, and reset/flush behavior.
- `integrations/zotero/src/research-loop-site.ts`, `sidebar.ts`: target-tagged, stop-capable Main Site sessions and views.
- `integrations/zotero/src/plugin.ts`: one controller-owned selection path and all local UI/resource bindings.
- `integrations/zotero/test/repository-target.test.ts`, `local-repository-target-resolver.test.ts`, `repository-target-controller.test.ts`: new focused unit coverage.
- Existing `codex-service.test.ts`, `terminal-panel.test.ts`, `qmd-workspace.test.ts`, `research-loop-site.test.ts`, and `plugin-state.test.ts`: regression and integration coverage.

### Task 0: Remove known Linux headless build and native-test blockers

**Files:**
- Modify: `integrations/zotero/scripts/build.mjs:1-108`
- Create: `integrations/zotero/scripts/archive-tools.mjs`
- Modify: `integrations/zotero/native/src/zoterochat_helper.c:1-32`
- Modify: `integrations/zotero/native/Makefile:1-22`
- Modify: `integrations/zotero/src/research-loop-site.ts:25-43,45-143`
- Modify: `integrations/zotero/test/starter-template.test.mjs`
- Modify: `integrations/zotero/test/research-loop-site.test.ts`
- Modify: `integrations/zotero/native/tests/test_helper.py`

**Interfaces:**
- Consumes: the existing package build script, starter-template archive round-trip, Main Site initializer, and local-helper `forkpty` implementation.
- Produces: PATH-resolved `zip`/`unzip` archive behavior, a Linux-compilable local helper that links `libutil` when required, and an explicit split between Linux behavior gates and macOS XPI packaging gates for every later task.

- [ ] **Step 1: Write failing portability tests before changing scripts or C source**

```js
async function writeExecutable(file, body) {
  await writeFile(file, body, { mode: 0o700 });
}

it("round-trips a staged starter through the archive helper using PATH zip and unzip", async () => {
  const researchLoopRoot = path.resolve(process.cwd(), "..", "..");
  const staged = await temporaryDirectory("research-loop-staged");
  const destination = await temporaryDirectory("research-loop-destination");
  const bin = await temporaryDirectory("qlab-path-tools");
  const zipCalled = path.join(bin, "zip.called");
  const unzipCalled = path.join(bin, "unzip.called");
  await writeExecutable(path.join(bin, "zip"), "#!/bin/sh\n[ \"$1,$2,$3,$5\" = \"-X,-q,-r,.\" ] || exit 64\n: > \"$ZIP_CALLED\"\nexec /usr/bin/tar -cf \"$4\" .\n");
  await writeExecutable(path.join(bin, "unzip"), "#!/bin/sh\n[ \"$1,$2,$4\" = \"-n,-q,-d\" ] || exit 64\n: > \"$UNZIP_CALLED\"\nmkdir -p \"$5\" && exec /usr/bin/tar -xf \"$3\" -C \"$5\"\n");
  const archive = path.join(await temporaryDirectory("qlab-starter-archive"), "starter.zip");
  await stageStarterTemplate(researchLoopRoot, staged);
  const env = { PATH: `${bin}:${process.env.PATH}`, ZIP_CALLED: zipCalled, UNZIP_CALLED: unzipCalled };
  await createZipArchive(staged, archive, env);
  await extractZipArchive(archive, destination, env);
  await expect(stat(zipCalled)).resolves.toBeTruthy();
  await expect(stat(unzipCalled)).resolves.toBeTruthy();
  await expect(stat(path.join(destination, "knowledge", "index.qmd"))).resolves.toBeTruthy();
});
```

Add this behavioral test to `starter-template.test.mjs`, including a local `writeExecutable(path, body)` helper implemented with existing `writeFile(path, body, { mode: 0o700 })`. Import `createZipArchive` and `extractZipArchive` from the production archive helper, then invoke both paths through executable shims named only `zip` and `unzip`; never inspect `build.mjs` source text. Change the Main Site initialization argv to call the same PATH-resolved `unzip` executable with fixed args. Add a Python `unittest` that runs `make -C native clean all` with `CC=cc` on Linux and skips only when `sys.platform == "darwin"`; assert the resulting executable exists. It must not stub compilation or shell out to `xcrun`.

Add a `research-loop-site.test.ts` runtime-spawn assertion that calls the initializer through its fake bridge and verifies its fixed argv contains `unzip` (not `/usr/bin/unzip`) while preserving archive/destination positional arguments. The test must inspect the structured spawned argv, not source text or a shell string.

- [ ] **Step 2: Run the tests to verify the current failures**

Run: `cd integrations/zotero && npx vitest run test/starter-template.test.mjs test/research-loop-site.test.ts && CC=cc make -C native clean all`

Expected: the starter test fails because `archive-tools.mjs`/its exported production seam does not exist, the Main Site argv assertion sees the hard-coded unzip path, and the Linux compile fails because `zoterochat_helper.c` includes `<util.h>`.

- [ ] **Step 3: Implement the smallest portable seams**

```c
#if defined(__APPLE__)
#include <util.h>
#elif defined(__linux__)
#include <pty.h>
#else
#error "The local Zotero helper supports only macOS and Linux test builds"
#endif
```

```make
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
PTY_LIBS := -lutil
endif
$(TARGET): $(SOURCE)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SOURCE) $(PTY_LIBS) -o $(TARGET)
```

Create `archive-tools.mjs` with `createZipArchive(root, archive, env)`, which calls `execFileSync("zip", ["-X", "-q", "-r", archive, "."], { cwd: root, env })`, and `extractZipArchive(archive, destination, env)`, which calls `execFileSync("unzip", ["-n", "-q", archive, "-d", destination], { env })`. Have `build.mjs` call `createZipArchive` for the starter and XPI archives. In the initializer use `unzip` from `PATH` (no `/usr/bin/zip` or `/usr/bin/unzip`), with the existing fixed argv and no shell interpolation. Keep `build-universal.sh` unchanged and macOS-only; this task deliberately does not make the signed universal XPI build run on Linux.

- [ ] **Step 4: Run Linux behavior gates**

Run: `cd integrations/zotero && npx vitest run test/starter-template.test.mjs test/research-loop-site.test.ts && CC=cc make -C native clean test && npm run check && npm test`

Expected: PASS on Linux. Do not run or claim `npm run build` here.

- [ ] **Step 5: Commit the portability prerequisite**

```bash
git add integrations/zotero/scripts/build.mjs integrations/zotero/scripts/archive-tools.mjs integrations/zotero/native/src/zoterochat_helper.c integrations/zotero/native/Makefile integrations/zotero/src/research-loop-site.ts integrations/zotero/test/starter-template.test.mjs integrations/zotero/test/research-loop-site.test.ts integrations/zotero/native/tests/test_helper.py
git commit -m "fix(zotero): make local test tooling Linux-portable"
```

### Task 1: Define local target identity and preference codec

**Files:**
- Create: `integrations/zotero/src/repository-target.ts`
- Create: `integrations/zotero/test/repository-target.test.ts`
- Modify: `integrations/zotero/prefs.js:1-8`

**Interfaces:**
- Consumes: canonical local root strings returned by `normalizeQLabRoot()` in `qlab-workspace.ts`.
- Produces: `LocalRepositoryTarget`, `ResolvedLocalRepositoryTarget`, `RepositoryTargetSnapshot`, `StoredTargetPreferences`, `LegacyMigrationOutcome`, `PendingLocalRepositoryCandidate`, `LegacyThreadBinding`, `deriveRepositoryId()`, `deriveTargetId()`, `parseStoredTargetPreferences()`, `classifyLegacyRoot()`, and `migrateLegacy()` for Tasks 2-7.

- [ ] **Step 1: Write the failing target identity and migration tests**

```ts
import { describe, expect, it } from "vitest";
import {
  classifyLegacyRoot,
  bindPendingLegacyThreads,
  deriveRepositoryId,
  deriveTargetId,
  migrateLegacy,
  parseStoredTargetPreferences,
} from "../src/repository-target";

describe("repository target identity", () => {
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

  it("returns ready session assignments and defers candidate bindings until activation", async () => {
    const ready = await migrateLegacy(emptyPreferences(), { legacyRoot: "/ready", sessions: [{ threadId: "active", recordedCwd: null }], activeThreadId: "active" }, fakeMigrationResolver("ready"));
    expect(ready.preferences).toMatchObject({ active: { canonicalRoot: "/ready" }, legacyUnassigned: [] });
    expect(ready.sessions).toContainEqual(expect.objectContaining({ threadId: "active", targetId: expect.any(String) }));
    const candidate = await migrateLegacy(emptyPreferences(), { legacyRoot: "/partial", sessions: [{ threadId: "inside", recordedCwd: "/partial/drafts/a.qmd" }, { threadId: "outside", recordedCwd: "/elsewhere/a.qmd" }], activeThreadId: null }, fakeMigrationResolver("partial"));
    expect(candidate.preferences.pendingCandidate).toMatchObject({ eligibleLegacyThreads: [{ threadId: "inside" }] });
    expect(candidate.sessions).not.toContainEqual(expect.objectContaining({ threadId: "inside", targetId: expect.anything() }));
    expect(await bindPendingLegacyThreads(candidate.preferences, candidate.sessions, resolved("/partial"), fakeMigrationResolver("ready")))
      .toMatchObject({ preferences: { active: { canonicalRoot: "/partial" }, legacyUnassigned: [{ threadId: "outside", reason: "different-root" }] }, sessions: [expect.objectContaining({ threadId: "inside", targetId: expect.any(String) })] });
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
});
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `cd integrations/zotero && npx vitest run test/repository-target.test.ts`

Expected: FAIL because `../src/repository-target` does not exist.

- [ ] **Step 3: Implement immutable local target types and strict codec**

```ts
import type { QLabRepositoryState } from "./qlab-workspace";

export type LocalRepositoryTarget = Readonly<{ kind: "local"; root: string }>;
export type ResolvedLocalRepositoryTarget = Readonly<LocalRepositoryTarget & {
  canonicalRoot: string;
  repositoryId: string;
  targetId: string;
}>;
export type RepositoryTargetSnapshot = Readonly<{
  target: ResolvedLocalRepositoryTarget;
  targetEpoch: number;
}>;
export type LegacyRootDisposition = "bind" | "candidate" | "unassigned";
export type StoredTargetPreferences = Readonly<{
  version: 1;
  active: ResolvedLocalRepositoryTarget | null;
  pendingCandidate: PendingLocalRepositoryCandidate | null;
  legacyUnassigned: readonly LegacyThreadBinding[];
  migratedLegacy: boolean;
}>;

export type LocalRepositoryCandidate = Readonly<{
  kind: "candidate";
  canonicalRoot: string;
  state: "empty" | "partial";
}>;
export type PendingLocalRepositoryCandidate = Readonly<LocalRepositoryCandidate & {
  eligibleLegacyThreads: readonly PendingLegacyThreadBinding[];
}>;
export type LocalRepositoryUnavailable = Readonly<{
  kind: "unavailable";
  reason: "missing" | "incompatible" | "identity-unavailable";
}>;
export type LocalRepositoryInspection =
  | ResolvedLocalRepositoryTarget
  | LocalRepositoryCandidate
  | LocalRepositoryUnavailable;
export type LegacyUnassignedReason = LocalRepositoryUnavailable["reason"] | "different-root" | "pending-candidate";
export type LegacyThreadBinding = Readonly<{
  threadId: string;
  recordedCwd: string | null;
  reason: LegacyUnassignedReason;
}>;
export type PendingLegacyThreadBinding = Readonly<{ threadId: string; recordedCwd: string | null; activeWithoutCwd: boolean }>;
export type TargetableSessionRecord = Readonly<{
  threadId: string;
  recordedCwd: string | null;
  targetId?: string;
}>;
export type TargetAssignedSession<TSession extends TargetableSessionRecord> = Readonly<
  Omit<TSession, "targetId"> & { targetId?: string }
>;
export type LegacyMigrationOutcome<TSession extends TargetableSessionRecord = TargetableSessionRecord> = Readonly<{
  preferences: StoredTargetPreferences;
  sessions: readonly TargetAssignedSession<TSession>[];
}>;
export interface LegacyMigrationInput<TSession extends TargetableSessionRecord = TargetableSessionRecord> {
  legacyRoot: string;
  sessions: readonly TSession[];
  activeThreadId: string | null;
}
export interface LegacyMigrationResolver {
  inspect(root: string): Promise<LocalRepositoryInspection>;
  canonicalize(path: string): Promise<string | null>;
}
export type TargetDigest = (bytes: Uint8Array) => string;
export function deriveRepositoryId(endpointId: string, repositoryUuid: string, digest: TargetDigest): string;
export function deriveTargetId(endpointId: string, canonicalRoot: string, repositoryId: string, digest: TargetDigest): string;
export async function migrateLegacy<TSession extends TargetableSessionRecord>(
  stored: StoredTargetPreferences,
  input: LegacyMigrationInput<TSession>,
  resolver: LegacyMigrationResolver,
): Promise<LegacyMigrationOutcome<TSession>>;
export async function bindPendingLegacyThreads<TSession extends TargetableSessionRecord>(
  stored: StoredTargetPreferences,
  sessions: readonly TargetAssignedSession<TSession>[],
  target: ResolvedLocalRepositoryTarget,
  resolver: LegacyMigrationResolver,
): Promise<LegacyMigrationOutcome<TSession>>;

export function classifyLegacyRoot(state: QLabRepositoryState): LegacyRootDisposition {
  return state === "ready" ? "bind" : state === "empty" || state === "partial" ? "candidate" : "unassigned";
}
```

Production creates `const geckoTargetDigest: TargetDigest = (bytes) => sha256Bytes(bytes)` and passes it only at the resolver boundary. Tests use an in-memory digest seam, never Gecko globals, and assert byte-for-byte UTF-8 payloads `endpointId + "\0" + repositoryUuid` and `endpointId + "\0" + canonicalRoot + "\0" + repositoryId`. Parse only `version: 1`, an exact `kind: "local"`, non-empty canonical root, and 64-hex identities; a malformed/future value returns exactly `{ version: 1, active: null, pendingCandidate: null, legacyUnassigned: [], migratedLegacy: false }`. Migration returns the closed `LegacyMigrationOutcome`, so a ready-root binding changes both `preferences` and the original typed `sessions` records (`targetId` is assigned without losing the rest of each record). If `migratedLegacy` is already true, `migrateLegacy` is a no-op: it calls neither `resolver.inspect` nor `resolver.canonicalize`, returns the supplied session records byte-for-byte unchanged, and startup writes neither sessions nor preferences. Otherwise the single shared `LocalRepositoryInspection` ADT is a ready target, `{ kind:"candidate", state }`, or `{ kind:"unavailable", reason }`. A ready target binds records whose canonical cwd is inside that target, plus the explicitly supplied `activeThreadId` when its cwd is null; every other record receives deduplicated `different-root`. A candidate stores—not binds—its potentially eligible records in `pendingCandidate.eligibleLegacyThreads` and returns its input sessions unchanged; `bindPendingLegacyThreads(stored, sessions, target, resolver)` runs only after candidate confirmation and target activation, rechecks root containment, then returns a new outcome that binds only those eligible records and marks all others `different-root`. An unavailable result leaves active/pending null and session assignments unchanged while recording its exact reason. In every non-idempotent path set `preferences.migratedLegacy: true`. Add `pref("extensions.zotkit.repositoryTargets", "");` while retaining `qlabRoot` solely for Task 4 migration.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `cd integrations/zotero && npx vitest run test/repository-target.test.ts`

Expected: PASS with exact-byte identity, active-thread migration, pending-candidate binding, idempotency, and strict-codec coverage.

- [ ] **Step 5: Type-check the target module**

Run: `cd integrations/zotero && npm run check`

Expected: PASS.

- [ ] **Step 6: Commit the target value layer**

```bash
git add integrations/zotero/src/repository-target.ts integrations/zotero/test/repository-target.test.ts integrations/zotero/prefs.js
git commit -m "feat(zotero): define local repository target identity"
```

### Task 2: Resolve valid local repositories and initialize candidates before activation

**Files:**
- Create: `integrations/zotero/src/local-repository-target-resolver.ts`
- Create: `integrations/zotero/test/local-repository-target-resolver.test.ts`
- Modify: `integrations/zotero/src/qlab-workspace.ts:1-72`
- Modify: `integrations/zotero/src/research-loop-site.ts:45-143,181-212`

**Interfaces:**
- Consumes: Task 1 `LocalRepositoryTarget`, `ResolvedLocalRepositoryTarget`, and `classifyLegacyRoot`; existing `QLabPathHost`, `qlabRepositoryState`, and starter extraction runtime.
- Produces: `LocalRepositoryTargetResolver.inspect(root): Promise<LocalRepositoryInspection>` and `confirm(candidate)` for Task 3; candidate/unavailable states are the Task 1 ADT, and each resolved result has a Git-private UUID-derived identity. No other resolver method is public.

- [ ] **Step 1: Write failing resolver tests with a fake process/runtime**

```ts
it("creates the private UUID only after a ready Git repository passes validation", async () => {
  const runtime = fakeRuntime({ state: "ready", gitPath: "/repo/.git/qlab/repository-id", uuidFile: null });
  const inspected = await new LocalRepositoryTargetResolver(runtime).inspect("/alias/repo");
  expect(inspected.kind).toBe("local");
  const target = inspected as ResolvedLocalRepositoryTarget;
  expect(runtime.createPrivateIfAbsent).toHaveBeenCalledWith("/repo/.git/qlab/repository-id", expect.stringMatching(/^[0-9a-f-]{36}\n$/), 0o600);
  expect(target.canonicalRoot).toBe("/repo");
});

it("canonicalizes trimmed relative git paths and converges concurrent UUID creators", async () => {
  const runtime = fakeRuntime({ state: "ready", gitPath: "  .git/qlab/repository-id\n", createConflictThenRead: "11111111-1111-4111-8111-111111111111\n" });
  const resolver = new LocalRepositoryTargetResolver(runtime);
  const [first, second] = await Promise.all([resolver.inspect("/repo"), resolver.inspect("/repo")]);
  expect(first).toMatchObject({ canonicalRoot: "/repo" });
  expect(second).toEqual(first);
  expect(runtime.createPrivateIfAbsent).toHaveBeenCalledWith("/repo/.git/qlab/repository-id", expect.any(String), 0o600);
});

it("does not persist or activate an empty candidate before confirmation", async () => {
  const runtime = fakeRuntime({ state: "empty" });
  const resolver = new LocalRepositoryTargetResolver(runtime);
  const inspected = await resolver.inspect("/new");
  expect(inspected).toMatchObject({ kind: "candidate", state: "empty" });
  expect(runtime.initialize).not.toHaveBeenCalled();
  await resolver.confirm(inspected as LocalRepositoryCandidate);
  expect(runtime.initialize).toHaveBeenCalledWith("/new");
});

it.each(["missing", "incompatible"] as const)("returns unavailable for %s without activation", async (state) => {
  await expect(new LocalRepositoryTargetResolver(fakeRuntime({ state })).inspect("/bad"))
    .resolves.toEqual({ kind: "unavailable", reason: state });
});
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `cd integrations/zotero && npx vitest run test/local-repository-target-resolver.test.ts`

Expected: FAIL because `LocalRepositoryTargetResolver` does not exist.

- [ ] **Step 3: Implement resolver and candidate contract without active-target writes**

```ts
export interface LocalRepositoryTargetRuntime {
  canonicalize(root: string): Promise<string>;
  state(root: string): Promise<QLabRepositoryState>;
  initialize(root: string): Promise<void>;
  gitPrivatePath(root: string): Promise<string>; // raw `git rev-parse --git-path` stdout
  readPrivate(path: string): Promise<string | null>;
  createPrivateIfAbsent(path: string, value: string, mode: number): Promise<"created" | "exists">;
  resolvePath(root: string, path: string): string;
  isPathInside(root: string, candidate: string): boolean;
  digest: TargetDigest;
}

export class LocalRepositoryTargetResolver {
  async inspect(root: string): Promise<LocalRepositoryInspection> {
    const canonicalRoot = await this.runtime.canonicalize(root);
    const state = await this.runtime.state(canonicalRoot);
    if (state === "ready") return this.resolveReady(canonicalRoot);
    if (state === "empty" || state === "partial") return { kind: "candidate", canonicalRoot, state };
    return { kind: "unavailable", reason: state === "missing" ? "missing" : "incompatible" };
  }
  async confirm(candidate: LocalRepositoryCandidate): Promise<ResolvedLocalRepositoryTarget> {
    await this.runtime.initialize(candidate.canonicalRoot);
    return this.resolveReady(candidate.canonicalRoot);
  }
  private async resolveReady(root: string): Promise<ResolvedLocalRepositoryTarget> {
    const canonicalRoot = await this.runtime.canonicalize(root);
    if (await this.runtime.state(canonicalRoot) !== "ready") throw new Error("Choose a valid local Research Loop Git repository");
    return this.resolveIdentity(canonicalRoot);
  }
}
```

Import `LocalRepositoryCandidate`, `LocalRepositoryInspection`, and `QLabRepositoryState` explicitly (`QLabRepositoryState` from `qlab-workspace.ts`); do not redeclare a look-alike state union. Implement `gitPrivatePath(root)` through structured `NativeBridge.spawnPipe` arguments that run `git -C <root> rev-parse --git-path qlab/repository-id`; do not interpolate root into a shell string. Trim stdout, resolve a relative Git path against the canonical root, and reject an absolute/relative result unless `isPathInside(canonicalRoot, resolvedPath)` is true. Generate a UUID with `Services.uuid.generateUUID()`, normalize it to lowercase RFC-4122 text, reject non-UUID file content, then call `createPrivateIfAbsent(path, uuid + "\n", 0o600)`, whose Gecko implementation uses exclusive creation (`O_CREAT|O_EXCL`). On `exists`/conflict, immediately re-read and validate the winner; never overwrite it. This makes concurrent `inspect` calls converge on one repository ID. `confirm` calls the existing safe initializer only for `empty`/`partial`, rechecks ready shape and Git availability, then resolves identity. An identity-resolution failure returns `{ kind:"unavailable", reason:"identity-unavailable" }`; plugin selection turns any unavailable inspection into the fixed “Choose a valid local Research Loop Git repository” UI error and never calls the controller.

- [ ] **Step 4: Run resolver and existing repository-state tests**

Run: `cd integrations/zotero && npx vitest run test/local-repository-target-resolver.test.ts test/qlab-workspace.test.ts test/research-loop-site.test.ts`

Expected: PASS. Existing Main Site tests may require its initializer runtime to implement the new candidate-only adapter methods.

- [ ] **Step 5: Type-check the resolver boundary**

Run: `cd integrations/zotero && npm run check`

Expected: PASS.

- [ ] **Step 6: Commit candidate resolution**

```bash
git add integrations/zotero/src/local-repository-target-resolver.ts integrations/zotero/test/local-repository-target-resolver.test.ts integrations/zotero/src/qlab-workspace.ts integrations/zotero/src/research-loop-site.ts
git commit -m "feat(zotero): resolve identity-backed local repository targets"
```

### Task 3: Add the atomic target-switch controller

**Files:**
- Create: `integrations/zotero/src/repository-target-controller.ts`
- Create: `integrations/zotero/test/repository-target-controller.test.ts`

**Interfaces:**
- Consumes: Task 1 `RepositoryTargetSnapshot`, Task 2 resolver results, and target IDs/epochs.
- Produces: `RepositoryTargetController.switchTo()`, `activeSnapshot()`, `isCurrent()`, `TargetSwitchBlocker`, and `TargetSwitchRuntime`; Tasks 4-7 register concrete owners.

- [ ] **Step 1: Write the failing transaction tests**

```ts
it("disposes only staged B when preference persistence fails, leaving A live", async () => {
  const h = harness({ activeRoot: "/old", persistError: new Error("disk full") });
  await expect(h.controller.switchTo(resolved("/new"))).rejects.toThrow("disk full");
  expect(h.published.map((x) => x.target.canonicalRoot)).toEqual(["/old"]);
  expect(h.stagedNew.dispose).toHaveBeenCalledOnce();
  expect(h.old.dispose).not.toHaveBeenCalled();
  expect(h.events).toEqual(["stage:/new", "persist:/new", "dispose-staged:/new"]);
});

it("publishes each committed snapshot exactly once and does not restart a user-stopped turn", async () => {
  const h = harness({ activeRoot: "/old", blocker: { kind: "running-turn" } });
  await h.controller.switchTo(resolved("/new"));
  expect(h.publish).toHaveBeenCalledTimes(1);
  expect(h.stopTurn).toHaveBeenCalledOnce();
  expect(h.restartTurn).not.toHaveBeenCalled();
});

it("rechecks blockers after a user resolution before staging", async () => {
  const h = harness({ activeRoot: "/old", blockers: [{ kind: "running-turn" }], blockersAfterResolution: [{ kind: "unsaved-qmd", path: "drafts/a.qmd" }] });
  await expect(h.controller.switchTo(resolved("/new"))).rejects.toThrow("Resolve new switch blockers");
  expect(h.stage).not.toHaveBeenCalled();
  expect(h.persist).not.toHaveBeenCalled();
});

it("persists and synchronously publishes B before disposing A", async () => {
  const h = harness({ activeRoot: "/A" });
  await h.controller.switchTo(resolved("/B"));
  expect(h.events).toEqual(["stage:/B", "persist:/B", "publish:/B", "dispose-old:/A"]);
  expect(h.controller.activeSnapshot()!.target.canonicalRoot).toBe("/B");
});

it("keeps B published and records a degraded resource when post-commit disposal fails", async () => {
  const h = harness({ activeRoot: "/A", disposeOldError: new Error("terminal close failed") });
  await expect(h.controller.switchTo(resolved("/B"))).resolves.toMatchObject({ target: { canonicalRoot: "/B" } });
  expect(h.controller.activeSnapshot()!.target.canonicalRoot).toBe("/B");
  expect(h.degrade).toHaveBeenCalledWith(expect.objectContaining({ target: expect.objectContaining({ canonicalRoot: "/B" }) }), expect.any(Error));
});

it("cancels a stale preparing B and allows only C to commit", async () => {
  const h = harness({ activeRoot: "/A", deferredRoots: ["/B"] });
  const b = h.controller.switchTo(resolved("/B"));
  await h.controller.switchTo(resolved("/C"));
  h.resolve("/B");
  await expect(b).rejects.toThrow("superseded");
  expect(h.controller.activeSnapshot()!.target.canonicalRoot).toBe("/C");
});

it("rejects a late old-epoch callback after a successful switch", async () => {
  const h = harness({ activeRoot: "/old" });
  const old = h.controller.activeSnapshot()!;
  await h.controller.switchTo(resolved("/new"));
  expect(h.controller.isCurrent(old.target.targetId, old.targetEpoch)).toBe(false);
});
```

- [ ] **Step 2: Run the controller test to verify it fails**

Run: `cd integrations/zotero && npx vitest run test/repository-target-controller.test.ts`

Expected: FAIL because `RepositoryTargetController` does not exist.

- [ ] **Step 3: Implement one publish point and staged-owner contract**

```ts
export type TargetSwitchBlocker =
  | { kind: "running-turn" }
  | { kind: "unsaved-qmd"; path: string }
  | { kind: "pending-keep"; path: string }
  | { kind: "unknown-operation" };

export interface TargetSwitchRuntime<Staged> {
  checkBlockers(): Promise<readonly TargetSwitchBlocker[]>;
  resolveBlockers(blockers: readonly TargetSwitchBlocker[]): Promise<"continue" | "cancel">;
  stage(snapshot: RepositoryTargetSnapshot, signal: AbortSignal): Promise<Staged>;
  persist(snapshot: RepositoryTargetSnapshot): Promise<void>;
  publish(snapshot: RepositoryTargetSnapshot, staged: Staged): void;
  disposeStaged(staged: Staged): Promise<void>;
  disposeOld(previous: RepositoryTargetSnapshot | null): Promise<void>;
  markDegraded(snapshot: RepositoryTargetSnapshot, error: Error): void;
}

export class RepositoryTargetController {
  async switchTo(target: ResolvedLocalRepositoryTarget): Promise<RepositoryTargetSnapshot> {
    return this.enqueueOrStart(target);
  }
  activeSnapshot(): RepositoryTargetSnapshot | null { return this.active; }
  isCurrent(targetId: string, targetEpoch: number): boolean {
    return this.active?.target.targetId === targetId && this.active.targetEpoch === targetEpoch;
  }
}
```

Allocate `switchAttemptId` before resolution. Run `checkBlockers`, call `resolveBlockers`, then run `checkBlockers` again; only an empty second result may stage. While staging, a newer request aborts the resolver/staging `AbortController`; while committing, queue the newest request and execute it after publication. Check attempt ID before every irreversible operation. The required commit order is `stage(B)` while every A process remains active and visible, `persist(B)`, exactly one synchronous `publish(B, staged)`, then `disposeOld(A)`. `TargetSwitchRuntime.publish(next, staged)` is the controller's only publication point; individual resources must not publish independently. If persistence fails, call only `disposeStaged(B)`; the stored preference and active snapshot remain A, and A's process is not closed. Any other pre-publication failure likewise disposes only B's staged resources. If `resolveBlockers` stopped a turn, that user-approved turn remains stopped even though the old snapshot remains active; do not claim all old activity is untouched. After synchronous publication, catch `disposeOld(previous)` errors, call `markDegraded(B, error)`, and resolve the switch with B still active—never restore the old root.

- [ ] **Step 4: Run controller test to verify it passes**

Run: `cd integrations/zotero && npx vitest run test/repository-target-controller.test.ts`

Expected: PASS with persistence-failure, supersession, epoch, blocker, and post-commit-degraded cases passing.

- [ ] **Step 5: Commit the transaction seam**

```bash
git add integrations/zotero/src/repository-target-controller.ts integrations/zotero/test/repository-target-controller.test.ts
git commit -m "feat(zotero): add atomic repository target switching"
```

### Task 4: Migrate preferences and bind Codex conversations to a target

**Files:**
- Modify: `integrations/zotero/src/settings.ts:20-52`
- Modify: `integrations/zotero/src/plugin.ts:183-240,1306-1341`
- Modify: `integrations/zotero/src/codex-service.ts:119-160,237-458,510-690,930-1065,1629-1680,1877-1941,2030-2083`
- Modify: `integrations/zotero/test/codex-service.test.ts:733-753`
- Test: `integrations/zotero/test/stored-conversation-resume.test.ts` (existing missing-thread/error classification remains unchanged)
- Modify: `integrations/zotero/test/repository-target.test.ts`
- Modify: `integrations/zotero/test/plugin-state.test.ts`

**Interfaces:**
- Consumes: Tasks 1-3 `RepositoryTargetSnapshot` and target preference codec.
- Produces: `loadSettings()` returning target preference state, ordered `saveSessionRecords()` then `saveRepositoryTargets()` migration persistence, an idempotent startup migration before any target-bound service restore, `CodexService.stageRepositoryTarget()` / synchronous `commitRepositoryTarget()`, and target-scoped session/workspace-object records for Tasks 5 and 7.

- [ ] **Step 1: Write failing migration and Codex isolation tests**

```ts
it.each([
  ["ready", { active: { canonicalRoot: "/legacy" }, pendingCandidate: null, legacyUnassigned: [] }],
  ["empty", { active: null, pendingCandidate: { canonicalRoot: "/legacy", state: "empty" } }],
  ["partial", { active: null, pendingCandidate: { canonicalRoot: "/legacy", state: "partial" } }],
  ["missing", { active: null, pendingCandidate: null, legacyUnassigned: [{ reason: "missing" }] }],
  ["incompatible", { active: null, pendingCandidate: null, legacyUnassigned: [{ reason: "incompatible" }] }],
] as const)("migrates legacy %s roots without inventing a live target", async (state, expected) => {
  expect(await migrateLegacy(emptyPreferences(), { legacyRoot: "/legacy", sessions: legacySessions, activeThreadId: null }, fakeMigrationResolver(state)))
    .toMatchObject({ preferences: { ...expected, migratedLegacy: true } });
});

it("persists migration before restoring target-bound services and is idempotent on the next startup", async () => {
  const h = startupHarness({ legacyRoot: "/legacy", state: "ready" });
  await h.plugin.onStartup();
  expect(h.calls).toEqual(["migrate", "saveSessionRecords", "saveRepositoryTargets", "hydrate", "publish", "codex.restore", "terminal.restore", "mainSite.restore"]);
  const persisted = h.savedMigrationState();
  await h.plugin.onStartup();
  expect(h.savedMigrationState()).toEqual(persisted);
  expect(h.migrateLegacy).toHaveBeenCalledTimes(1);
  expect(h.calls.filter((x) => x === "saveSessionRecords")).toHaveLength(1);
  expect(h.calls.filter((x) => x === "saveRepositoryTargets")).toHaveLength(1);
});

it("writes migrated session assignments before preferences and retries safely after preference failure", async () => {
  const h = startupHarness({ legacyRoot: "/legacy", state: "ready", saveRepositoryTargetsError: new Error("disk full") });
  await expect(h.plugin.onStartup()).rejects.toThrow("disk full");
  expect(h.calls).toEqual(["migrate", "saveSessionRecords", "saveRepositoryTargets"]);
  expect(h.savedSessionRecords()).toContainEqual(expect.objectContaining({ targetId: expect.any(String) }));
  expect(h.savedPreferences().migratedLegacy).toBe(false);
  const firstSavedSessions = h.savedSessionRecords();
  h.saveRepositoryTargetsError = null;
  await h.plugin.onStartup();
  expect(h.savedPreferences().migratedLegacy).toBe(true);
  expect(h.savedSessionRecords()).toEqual(firstSavedSessions); // repeated assignment is idempotent
});

it("reads the raw missing legacy preference before loadSettings can normalize it away", async () => {
  const h = startupHarness({ rawLegacyRoot: "/missing", state: "missing" });
  await h.plugin.onStartup();
  expect(h.migrateLegacy).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
    legacyRoot: "/missing", sessions: expect.any(Array), activeThreadId: expect.anything(),
  }), expect.anything());
  expect(h.savedPreferences()).toMatchObject({ active: null, pendingCandidate: null, legacyUnassigned: [{ reason: "missing" }], migratedLegacy: true });
});

it("records only eligible pending legacy threads and binds them only after candidate confirmation publishes", async () => {
  const migrated = await migrateLegacy(emptyPreferences(), {
    legacyRoot: "/legacy",
    sessions: [
      { threadId: "inside", recordedCwd: "/legacy/drafts" },
      { threadId: "outside", recordedCwd: "/other" },
    ],
    activeThreadId: null,
  }, fakeMigrationResolver("partial"));
  expect(migrated.preferences.pendingCandidate).toMatchObject({
    eligibleLegacyThreads: [{ threadId: "inside" }],
  });
  expect(migrated.sessions).not.toContainEqual(expect.objectContaining({ threadId: "inside", targetId: expect.anything() }));
  const published = snapshot("target-B", "/legacy", 2);
  expect(await bindPendingLegacyThreads(migrated.preferences, migrated.sessions, published.target, fakeMigrationResolver("ready")))
    .toMatchObject({ preferences: { active: expect.anything() }, sessions: [expect.objectContaining({ threadId: "inside", targetId: "target-B" })] });
});

it("binds a ready legacy active thread with no cwd only when activeThreadId explicitly identifies it", async () => {
  const migrated = await migrateLegacy(emptyPreferences(), {
    legacyRoot: "/legacy",
    sessions: [{ threadId: "active", recordedCwd: null }],
    activeThreadId: "active",
  }, fakeMigrationResolver("ready"));
  expect(migrated.sessions).toContainEqual(expect.objectContaining({ threadId: "active", targetId: expect.any(String) }));
});

it("starts a new target thread instead of retargeting the old workspace object", async () => {
  service.commitRepositoryTarget(await service.stageRepositoryTarget(snapshot("target-A", "/A", 1)));
  await service.setWorkspaceObject({ kind: "draft", key: "drafts/a.qmd", title: "A" });
  service.commitRepositoryTarget(await service.stageRepositoryTarget(snapshot("target-B", "/B", 2)));
  await service.send("write a draft", "gpt-5.6-sol", "high");
  expect(client.turnSteer).not.toHaveBeenCalled();
  expect(client.threadStart).toHaveBeenLastCalledWith(expect.objectContaining({ cwd: "/B" }));
});

it("stages B only after queued A resume, and exposes B binding synchronously at publication", async () => {
  service.commitRepositoryTarget(await service.stageRepositoryTarget(snapshot("target-A", "/A", 1)));
  const pendingResume = service.openConversationForPaper("paper-1");
  const switching = controller.switchTo(resolved("/B"));
  expect(controller.activeSnapshot()!.target.canonicalRoot).toBe("/A");
  resolveStoredResume("A-thread");
  await pendingResume;
  await switching;
  expect(service.repositoryBinding()).toEqual({ targetId: expect.any(String), targetEpoch: 2, root: "/B" });
  await service.setWorkspaceObject({ kind: "draft", key: "drafts/b.qmd", title: "B" });
  await service.send("write", "gpt-5.6-sol", "high");
  expect(client.threadResume).toHaveBeenCalledTimes(1);
  expect(client.threadStart).toHaveBeenLastCalledWith(expect.objectContaining({ cwd: "/B" }));
});

it("uses only the active target untrusted trees as writable roots", async () => {
  service.commitRepositoryTarget(await service.stageRepositoryTarget(snapshot("target-B", "/B", 2)));
  await service.send("Edit the untrusted Draft.", "gpt-5.6-sol", "high");
  expect(client.turnStart).toHaveBeenCalledWith(expect.objectContaining({
    sandboxPolicy: expect.objectContaining({ writableRoots: ["/B/drafts", "/B/literature", "/B/work"] }),
  }));
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd integrations/zotero && npx vitest run test/repository-target.test.ts test/codex-service.test.ts test/stored-conversation-resume.test.ts`

Expected: FAIL because `migrateLegacy`, `stageRepositoryTarget`, and `commitRepositoryTarget` do not exist, and existing service still reads `qlabRoot` directly.

- [ ] **Step 3: Implement preference migration and target-scoped Codex state**

```ts
export interface ZoteroChatSettings {
  libraryRoot: string;
  repositoryTargets: StoredTargetPreferences;
  // retain remaining unrelated settings unchanged
}

export interface RawTargetMigrationInput {
  legacyQLabRoot: string;
  repositoryTargetsRaw: string;
}

export interface CodexRepositoryBinding {
  targetId: string;
  targetEpoch: number;
  root: string;
}

export interface StagedCodexBinding {
  readonly snapshot: RepositoryTargetSnapshot | null;
  readonly binding: CodexRepositoryBinding | null;
  readonly activeDocument: null;
}

drainPaperTransitions(): Promise<void> {
  return this.paperTransition;
}

async stageRepositoryTarget(snapshot: RepositoryTargetSnapshot | null): Promise<StagedCodexBinding> {
  await this.drainPaperTransitions();
  return {
    snapshot,
    binding: snapshot && {
      targetId: snapshot.target.targetId,
      targetEpoch: snapshot.targetEpoch,
      root: snapshot.target.canonicalRoot,
    },
    activeDocument: null,
  };
}

commitRepositoryTarget(staged: StagedCodexBinding): void {
  this.repositoryTarget = staged.binding;
  this.activeDocument = staged.activeDocument;
  this.clearActiveConversationForDifferentTarget();
}

repositoryBinding(): CodexRepositoryBinding | null {
  return this.repositoryTarget;
}
```

Add persisted `recordedCwd` and optional `targetId` to `SessionRecord`; preserve all other record fields while replacing only the target assignment. `migrateLegacy` receives `{ legacyRoot, sessions, activeThreadId }` and returns `LegacyMigrationOutcome`: it binds a ready-root session when its canonicalized cwd lies inside the root, and additionally binds the one no-cwd record only when its `threadId === activeThreadId`. For an empty/partial candidate it stores (but does not bind) only the eligible session records in `pendingCandidate.eligibleLegacyThreads` and returns the input session records unchanged; `bindPendingLegacyThreads(stored, sessions, target, resolver)` runs only after candidate confirmation and target publication, then returns a new outcome that binds only those eligible records. All others stay explicitly unassigned. Save each outcome idempotently in one recoverable order: `saveSessionRecords(outcome.sessions)` completes before `saveRepositoryTargets(outcome.preferences)`; never write the preference first, because a preference-only success would lose ready-thread target assignments. If the preference save fails after the session save, retain the session write, leave `migratedLegacy:false`, and retry the same idempotent outcome on next startup. Require `CodexWorkspaceObject` input to omit `workspaceRoot`; build it only from the active binding. Replace `configuredQLabRoot()` and global `contextRoots()` with binding-aware functions that reject absent target. The landed service serializes paper/conversation operations through `enqueuePaperTransition`; `stageRepositoryTarget(next)` must await the existing transition queue completely, then construct and return `StagedCodexBinding` without mutating the live binding. The controller's synchronous `publish(next, staged)` calls only `commitRepositoryTarget(staged.codex)`; it must never call an async/Promise-returning target setter. `commitRepositoryTarget` performs no async work, so the test asserts B's binding immediately after `switchTo` resolves, without a microtask flush. Before calling the landed `resumeStoredThread`, reject a stored record whose `targetId` differs from the active binding; do not weaken `stored-conversation-resume.ts`'s missing-thread/error classification. Records without a target ID remain Legacy/unassigned and never reach `threadResume`. Before requesting a switch, expose a `running-turn` blocker; after user-confirmed stop, call the existing turn interrupt path and wait for terminal state before staging the new target.

`loadSettings()` may continue to normalize its display-safe `qlabRoot`, but it must not be the migration input. Add `readRawTargetMigrationInput(): RawTargetMigrationInput`, which reads `prefString("qlabRoot", "")` and `prefString("repositoryTargets", "")` without `pathExists` filtering. At the top of the landed plugin `startup(data)` run this exact sequence: `(1)` read raw migration input, including the complete persisted `sessionRecords` and `activeThreadId`; `(2)` parse target preferences and load ordinary settings; `(3)` when raw `legacyQLabRoot` is non-empty and parsed preferences are not migrated, call `migrateLegacy(settings.repositoryTargets, { legacyRoot: raw.legacyQLabRoot, sessions: sessionRecords, activeThreadId }, resolver)`; `(4)` synchronously persist `outcome.sessions` with `saveSessionRecords`; `(5)` only after that succeeds, persist `outcome.preferences` with `saveRepositoryTargets`; `(6)` hydrate and publish its active snapshot, if any; only then `(7)` construct `ResearchLoopSiteService`, `TerminalPanel`, and `CodexService`, and allow `ensureChatSession`/stored-conversation resume. A migration whose preferences are already `migratedLegacy:true` does not call the resolver, does not alter the loaded sessions, and writes neither store. Candidate confirmation calls `bindPendingLegacyThreads(currentPreferences, currentSessionRecords, published.target, resolver)` only after its confirmed target has been published; it saves that returned outcome in the same session-then-preference order and is idempotent if confirmation/startup is retried. Construction may be targetless, but no target-bound process, thread resume, terminal PTY, or Main Site session may be restored before publication. For ready migration, publish the restored snapshot before those services restore. For empty/partial/missing/incompatible states, hydrate no active target and restore no target-scoped resource. The legacy `qlabRoot` is not removed until both persistence writes succeed.

- [ ] **Step 4: Run Codex tests and type check**

Run: `cd integrations/zotero && npx vitest run test/codex-service.test.ts test/stored-conversation-resume.test.ts test/repository-target.test.ts && npm run check`

Expected: PASS; the old writable-root assertion is updated to set an explicit target instead of stubbing `qlabRoot`.

- [ ] **Step 5: Commit migration and Codex ownership**

```bash
git add integrations/zotero/src/settings.ts integrations/zotero/src/plugin.ts integrations/zotero/src/codex-service.ts integrations/zotero/test/codex-service.test.ts integrations/zotero/test/stored-conversation-resume.test.ts integrations/zotero/test/repository-target.test.ts integrations/zotero/test/plugin-state.test.ts
git commit -m "feat(zotero): scope Codex sessions to repository targets"
```

### Task 5: Make terminal and QMD workspaces switch-safe

**Files:**
- Modify: `integrations/zotero/src/terminal-panel.ts:34-112,371-477,904-924`
- Modify: `integrations/zotero/src/qmd-workspace.ts:17-45,103-153,278-405,424-483`
- Modify: `integrations/zotero/src/qmd-visual-editor.ts:76-110,257-312`
- Modify: `integrations/zotero/src/plugin.ts:2167-2232`
- Modify: `integrations/zotero/test/terminal-panel.test.ts`
- Modify: `integrations/zotero/test/qmd-workspace.test.ts:442-470`

**Interfaces:**
- Consumes: Task 3 `RepositoryTargetSnapshot` and `TargetSwitchBlocker`; Task 4 `CodexRepositoryBinding`.
- Produces: `TerminalPanel.disposeTarget(targetId, epoch)`, `QmdWorkspaceView.switchBlocker()`, `resolveSwitchBlocker("save" | "discard" | "cancel")`, `bindTarget(snapshot)`, and epoch-checked async callbacks for Task 7. These are production switch APIs used by the controller; no test-only state setters or getters are introduced.

- [ ] **Step 1: Write failing terminal and QMD switch tests**

```ts
it("disposes the old target PTY only when called after B has been published", async () => {
  await panel.open({ ...options, targetId: "A", targetEpoch: 1, workingDirectory: "/old" });
  await panel.disposeTarget("A", 1);
  expect(bridge.closeSession).toHaveBeenCalledWith(expect.any(String));
  await panel.open({ ...options, targetId: "B", targetEpoch: 2, workingDirectory: "/new" });
  expect(spawnCwd()).toBe("/new");
});

it("blocks target switching for a real unsaved Visual Edit and resolves Save, Discard, and Cancel", async () => {
  const { host, view, saveSource } = mount();
  await view.open(DRAFT);
  host.querySelector<HTMLButtonElement>(".zc-qmd-mode")!.click();
  host.querySelector<HTMLElement>(".zc-qmd-visual-block")!.click();
  const input = host.querySelector<HTMLTextAreaElement>(".zc-qmd-visual-editor textarea")!;
  input.value = "Changed from the DOM";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  expect(view.switchBlocker()).toEqual({ kind: "unsaved-qmd", path: DRAFT });
  await expect(view.resolveSwitchBlocker("cancel")).resolves.toBe("cancelled");
  expect(view.switchBlocker()).toEqual({ kind: "unsaved-qmd", path: DRAFT });
  await expect(view.resolveSwitchBlocker("save")).resolves.toBe("cleared");
  expect(saveSource).toHaveBeenCalledOnce();
  expect(view.switchBlocker()).toBeNull();

  view.syncAgentChanges({ activeTurnId: "turn-1", diffs: [{ turnId: "turn-1", diff: `diff --git a/${DRAFT} b/${DRAFT}\n+changed` }] });
  await settle();
  expect(view.switchBlocker()).toEqual({ kind: "pending-keep", path: DRAFT });
  await expect(view.resolveSwitchBlocker("discard")).resolves.toBe("cleared");
  expect(view.switchBlocker()).toBeNull();
});

it("keeps B's XUL browser URL and status when an A render callback settles late", async () => {
  const { host, view, renderService } = mountWithXulBrowserStub();
  view.bindTarget(snapshot("A", "/old", 1));
  const opening = view.open(DRAFT);
  view.bindTarget(snapshot("B", "/new", 2));
  await view.open(DRAFT);
  resolveRender(renderService, "http://new");
  await settle();
  const browser = host.querySelector<XulBrowserStub>("browser")!;
  expect(browser.getAttribute("src")).toBe("http://new");
  const statusBeforeOld = host.querySelector(".zc-qmd-status")!.textContent;
  resolveRender(renderService, "http://old");
  await opening;
  expect(browser.getAttribute("src")).toBe("http://new");
  expect(host.querySelector(".zc-qmd-status")!.textContent).toBe(statusBeforeOld);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd integrations/zotero && npx vitest run test/terminal-panel.test.ts test/qmd-workspace.test.ts`

Expected: FAIL because terminal options have no target identity and QMD view has no switch blocker/binding API.

- [ ] **Step 3: Implement target-tagged sessions and QMD blockers**

```ts
export interface TerminalPaperOptions {
  targetId: string;
  targetEpoch: number;
  // retain host, paper, workspace, and workingDirectory fields
}

async disposeTarget(targetId: string, targetEpoch: number): Promise<void> {
  for (const session of [...this.sessions.values()]) {
    if (session.targetId === targetId && session.targetEpoch === targetEpoch) this.disposeSession(session, true);
  }
}

switchBlocker(): TargetSwitchBlocker | null {
  if (this.visualEditor?.hasUnsavedSource()) return { kind: "unsaved-qmd", path: this.current!.relativePath };
  if (this.hasAgentChange) return { kind: "pending-keep", path: this.current!.relativePath };
  return null;
}

async resolveSwitchBlocker(decision: "save" | "discard" | "cancel"): Promise<"cleared" | "cancelled" | "blocked"> {
  const blocker = this.switchBlocker();
  if (!blocker) return "cleared";
  if (decision === "cancel") return "cancelled";
  if (blocker.kind === "unsaved-qmd") {
    return decision === "save" && await this.visualEditor?.flushForSwitch() ? "cleared"
      : decision === "discard" && this.visualEditor?.discardForSwitch() ? "cleared" : "blocked";
  }
  return decision === "discard" && await this.discardPendingChange() ? "cleared" : "blocked";
}
```

Add `targetId`/`targetEpoch` to `TerminalSession` and include them in the session key, so an equal paper key cannot revive an old-root PTY. Add `QmdVisualEditor.hasUnsavedSource()`, `flushForSwitch()`, and `discardForSwitch()`; save flushes through the existing revision-checked `saveSource`, discard restores the saved source, and cancel never mutates source, revision, or UI. Add a `discardChange(relativePath, changePath)` callback to `QmdWorkspaceOptions`, implemented by the plugin to remove/reset only the private working copy and renderer preview; it never touches the Draft. `resolveSwitchBlocker` accepts Save only for unsaved source, Discard for unsaved source or pending Keep, and Cancel for either. It returns `cleared` only after the relevant operation completes, `cancelled` with no mutation, or `blocked` on a failed/inapplicable decision. The test harness supplies an explicit XUL-browser stub implementing `setAttribute/getAttribute` and captures `.zc-qmd-status`; it must settle B's render first, then settle A's deferred callback and prove neither browser `src` nor status changed. Give `QmdWorkspaceView` a stored snapshot, increment its generation in `bindTarget`, stop both render services, clear active document/agent changes, and require target/epoch equality before mutating DOM from index/render/change-preview promises. Keep existing `destroy()` semantics for final shutdown.

- [ ] **Step 4: Run targeted tests and the plugin-state terminal regression**

Run: `cd integrations/zotero && npx vitest run test/terminal-panel.test.ts test/qmd-workspace.test.ts test/plugin-state.test.ts`

Expected: PASS. Update the existing configured-root terminal test to provide an explicit active target snapshot.

- [ ] **Step 5: Commit terminal and QMD ownership**

```bash
git add integrations/zotero/src/terminal-panel.ts integrations/zotero/src/qmd-workspace.ts integrations/zotero/src/qmd-visual-editor.ts integrations/zotero/src/plugin.ts integrations/zotero/test/terminal-panel.test.ts integrations/zotero/test/qmd-workspace.test.ts integrations/zotero/test/plugin-state.test.ts
git commit -m "feat(zotero): bind terminal and QMD state to repository targets"
```

### Task 6: Turn Main Site into a target-owned, stoppable session

**Files:**
- Modify: `integrations/zotero/src/research-loop-site.ts:45-143,214-279`
- Modify: `integrations/zotero/src/sidebar.ts:822-912`
- Modify: `integrations/zotero/test/research-loop-site.test.ts:123-243`
- Modify: `integrations/zotero/test/repository-target-controller.test.ts`

**Interfaces:**
- Consumes: Task 1 `RepositoryTargetSnapshot` and Task 3 epoch matching.
- Produces: a target/session/url/unsubscribe/generation-aware `ResearchLoopSiteService` adapter, `MainSiteSession`, `MainSiteTargetStage`, and a controller-owned Main Site lifecycle for Task 7. Do not introduce a parallel generic connection abstraction.

- [ ] **Step 1: Write failing Main Site lifecycle tests**

```ts
it("persists and publishes B before closing A's subscribed process and port", async () => {
  const h = mainSiteControllerHarness({
    onPersist: () => h.events.push("persist:B"),
    onPublish: () => {
      expect(h.events).toEqual(["persist:B"]);
      h.events.push("publish:B");
    },
  });
  h.service.bindTarget(snapshot("A", "/old", 1));
  await h.service.start(snapshot("A", "/old", 1));
  await h.controller.switchTo(resolved("/new"));
  expect(h.events).toEqual(["persist:B", "publish:B", "close:A", "exit:A"]);
  expect(h.service.sessionState()).toEqual({ status: "stopped", targetId: h.controller.activeSnapshot()!.target.targetId, targetEpoch: 2 });
  expect(h.runtime.spawn).toHaveBeenCalledTimes(1); // B remains on-demand
});

it("keeps B active and marks it degraded when post-commit A close times out", async () => {
  const h = mainSiteControllerHarness({ neverExitOnClose: true });
  await expect(h.controller.switchTo(resolved("/new"))).resolves.toMatchObject({ target: { canonicalRoot: "/new" } });
  expect(h.persistedRoots).toEqual(["/new"]);
  expect(h.controller.activeSnapshot()!.target.canonicalRoot).toBe("/new");
  expect(h.markDegraded).toHaveBeenCalledWith(expect.objectContaining({ target: expect.objectContaining({ canonicalRoot: "/new" }) }), expect.any(Error));
  expect(h.unsubscribe).toHaveBeenCalledOnce();
});

it("does not start a server merely because a target became active", async () => {
  const service = new ResearchLoopSiteService(runtime);
  service.bindTarget(snapshot("B", "/new", 2));
  expect(runtime.spawn).not.toHaveBeenCalled();
});

it("ignores output, readiness, and exit callbacks from a replaced generation", async () => {
  const service = new ResearchLoopSiteService(runtime);
  service.bindTarget(snapshot("A", "/old", 1));
  const starting = service.start(snapshot("A", "/old", 1));
  service.bindTarget(snapshot("B", "/new", 2));
  runtime.emit("site-a", { type: "output", text: "Build complete." });
  runtime.resolveCheck("http://127.0.0.1:4180/", true);
  await expect(starting).rejects.toThrow("no longer active");
  expect(service.sessionState()).toEqual({ status: "stopped", targetId: "B", targetEpoch: 2 });
});

it("keeps A running when B persistence fails, and leaves B published when B later fails to start", async () => {
  const h = mainSiteSwitchHarness();
  await expect(h.switchWithPersistFailure()).rejects.toThrow();
  expect(h.controller.activeSnapshot()!.target.targetId).toBe("A");
  expect(h.oldSessionStillLive()).toBe(true);
  await h.switchToB();
  await expect(h.service.start(snapshot("B", "/new", 2))).rejects.toThrow();
  expect(h.controller.activeSnapshot()!.target.targetId).toBe("B");
  expect(h.service.sessionState()).toMatchObject({ status: "error", targetId: "B", targetEpoch: 2 });
});
```

- [ ] **Step 2: Run the Main Site test to verify it fails**

Run: `cd integrations/zotero && npx vitest run test/research-loop-site.test.ts`

Expected: FAIL because the current fixed `SITE_SESSION_ID` / `deploy(repositoryRoot)` service has no target snapshot, retained unsubscribe, generation guard, lifecycle stage, or post-publication disposal seam.

- [ ] **Step 3: Adapt the existing `ResearchLoopSiteService` to an explicit target session**

```ts
export type MainSiteSessionState =
  | { status: "stopped"; targetId: string; targetEpoch: number }
  | { status: "starting"; targetId: string; targetEpoch: number; generation: number }
  | { status: "ready"; targetId: string; targetEpoch: number; generation: number; sessionId: string; localUrl: string }
  | { status: "error"; targetId: string; targetEpoch: number; generation: number; error: Error };

export interface MainSiteSession {
  targetId: string;
  targetEpoch: number;
  generation: number;
  sessionId: string;
  localUrl: string;
  stop(): Promise<void>;
}
export interface MainSiteTargetStage {
  readonly snapshot: RepositoryTargetSnapshot;
  readonly generation: number;
}

export class ResearchLoopSiteService {
  private boundTarget: RepositoryTargetSnapshot | null = null;
  private generation = 0;
  private state: MainSiteSessionState | null = null;
  private readonly sessions = new Map<string, MainSiteSession & { unsubscribe: () => void; exited: Promise<void> }>();

  bindTarget(snapshot: RepositoryTargetSnapshot): void {
    this.generation += 1;
    this.boundTarget = snapshot;
    this.state = { status: "stopped", targetId: snapshot.target.targetId, targetEpoch: snapshot.targetEpoch };
  }
  async stageTarget(snapshot: RepositoryTargetSnapshot): Promise<MainSiteTargetStage> {
    return { snapshot, generation: this.generation + 1 };
  }
  commitTarget(stage: MainSiteTargetStage): void {
    this.generation = stage.generation;
    this.boundTarget = stage.snapshot;
    this.state = { status: "stopped", targetId: stage.snapshot.target.targetId, targetEpoch: stage.snapshot.targetEpoch };
  }
  async disposeTarget(targetId: string, targetEpoch: number): Promise<void> {
    const session = this.sessions.get(`${targetId}:${targetEpoch}`);
    if (session) await this.stopSession(session);
  }
  sessionState(): MainSiteSessionState | null { return this.state; }
  async start(snapshot: RepositoryTargetSnapshot, onProgress = () => {}): Promise<MainSiteSession> {
    // Capture targetId/epoch/generation; retain the listener until stop/exit.
    // Every callback first checks this.matches(snapshot, generation).
  }
}
```

Extend the existing `ResearchLoopSiteRuntime` adapter with `closeSession(sessionId): void`, implemented by `NativeBridge.closeSession`; retain its existing `check`, `spawn`, `listen`, and `sleep` rather than creating another runtime or generic connection. Generate an opaque, bounded session ID such as `site-${sha256(targetId).slice(0, 20)}-${targetEpoch}-${generation}`; do not put a full digest in the native session ID. The service keeps each live record by its target pair, including session ID, local URL, retained `unsubscribe`, and exit promise. `stageTarget(B)` is side-effect-free: it does not close, unsubscribe, or otherwise alter A. `commitTarget(B)` synchronously changes only B's bound/display state and deliberately retains A's captured session record. Only the controller's post-publication `disposeOld(A)` calls `mainSite.disposeTarget(A.targetId, A.targetEpoch)`. `stopSession` first marks that captured session closing (so its output cannot update B), calls `runtime.closeSession(sessionId)`, and races its exit promise against a bounded `runtime.sleep(MAIN_SITE_CLOSE_TIMEOUT_MS)`. It calls `unsubscribe()` in `finally` on both exit and timeout. A timeout throws `Main Site did not exit` after B is already published; Task 3 catches it, marks B degraded, and never restores A. On A exit, clear displayed state only if the captured pair and generation still match—an A callback must never replace B's state. The controller's one synchronous `publish(next, staged)` calls `commitTarget(staged.mainSite)` exactly once and never starts B.

`start` is still invoked only by the existing sidebar Main Site button after the target snapshot has been published. It creates the listener before spawn, stores `starting`, polls only the captured session's local URL, and changes to `ready` only when `(targetId, targetEpoch, generation)` is still current. Output, readiness, timeout, and exit callbacks from any previous generation do nothing. A B persistence failure disposes only staged B state and leaves A's live session untouched. A post-publication A disposal failure marks B degraded; a post-publication B start failure changes only B's session state to `error`. Neither case rolls back to A. Replace global `isAvailable()`/fixed `SITE_SESSION_ID` behavior with `sessionState()` and the target-owned session URL. Sidebar renders/opens that URL only from the current `ready` state.

- [ ] **Step 4: Run the Main Site test to verify it passes**

Run: `cd integrations/zotero && npx vitest run test/research-loop-site.test.ts`

Expected: PASS, including existing ready/empty/partial/error coverage updated to target-tagged `start(snapshot, progress)`, exact `persist:B,publish:B,close:A,exit:A` ordering, late callback isolation, and post-commit degradation.

- [ ] **Step 5: Commit Main Site ownership**

```bash
git add integrations/zotero/src/research-loop-site.ts integrations/zotero/src/sidebar.ts integrations/zotero/test/research-loop-site.test.ts integrations/zotero/test/repository-target-controller.test.ts
git commit -m "feat(zotero): scope Main Site sessions to repository targets"
```

### Task 7: Integrate the controller in the plugin and remove naked-root reads

**Files:**
- Modify: `integrations/zotero/src/plugin.ts:54-83,183-240,923-925,1210-1212,1306-1341,1351-1800,2167-2232,2377-2386,3211-3316,3454-3474,3586-3822`
- Modify: `integrations/zotero/src/research-actions.ts`, `qlab-commands.ts`, `float-panel.ts`, `sidebar.ts`
- Modify: `integrations/zotero/test/plugin-state.test.ts`
- Modify: `integrations/zotero/test/float-panel.test.ts`
- Modify: `integrations/zotero/test/sidebar.test.ts`
- Modify: `integrations/zotero/test/research-actions.test.ts`, `qlab-commands.test.ts`

**Interfaces:**
- Consumes: Tasks 2-6 resolver/controller and all target-resource owner methods.
- Produces: the sole plugin `selectLocalRepository()` action, immutable active target propagation, and UI state derived from the active target snapshot.

- [ ] **Step 1: Inventory every current root consumer before replacing it**

Run: `cd integrations/zotero && rg -n "qlabRoot|configuredQLabRoot\(|saveQLabRoot" src/plugin.ts src/research-actions.ts src/qlab-commands.ts src/float-panel.ts src/sidebar.ts src/codex-service.ts src/terminal-panel.ts src/qmd-workspace.ts src/research-loop-site.ts --glob '*.ts'`

Expected: enumerate the existing plugin callbacks, research-action prompt builder, qlab command cwd builder, Float Panel/Sidebar labels and actions, Codex/terminal/QMD/Main Site callers. Copy the resulting file:line inventory into the implementation PR checklist; every entry must be converted to a captured snapshot or explicitly removed in this task.

- [ ] **Step 2: Write the failing end-to-end local switch regression**

```ts
it("atomically switches /old to /new without retaining old terminal, Codex, QMD, or Main Site state", async () => {
  const plugin = mountedPluginWithTarget("/old", { terminalOpen: true, mainSiteRunning: true, workspaceOpen: true });
  const old = plugin.activeSnapshot()!;
  await plugin.selectLocalRepository("/new");
  const next = plugin.activeSnapshot()!;
  expect(next.target.canonicalRoot).toBe("/new");
  expect(plugin.terminal.disposeTarget).toHaveBeenCalledWith(old.target.targetId, old.targetEpoch);
  expect(plugin.codex.stageRepositoryTarget).toHaveBeenCalledWith(expect.objectContaining({ target: expect.objectContaining({ canonicalRoot: "/new" }) }));
  expect(plugin.codex.commitRepositoryTarget).toHaveBeenCalledWith(expect.objectContaining({ binding: expect.objectContaining({ root: "/new" }) }));
  expect(plugin.qmdWorkspace.bindTarget).toHaveBeenLastCalledWith(next);
  expect(plugin.mainSite.commitTarget).toHaveBeenCalledWith(expect.anything());
  expect(plugin.mainSite.disposeTarget).toHaveBeenCalledWith(old.target.targetId, old.targetEpoch);
  expect(pref("repositoryTargets")).toContain("/new");
});

it("leaves /old active when /new validation fails", async () => {
  const plugin = mountedPluginWithTarget("/old");
  await expect(plugin.selectLocalRepository("/invalid")).rejects.toThrow();
  expect(plugin.activeSnapshot()!.target.canonicalRoot).toBe("/old");
  expect(plugin.terminal.disposeTarget).not.toHaveBeenCalled();
});
```

- [ ] **Step 3: Run plugin/surface tests to verify they fail**

Run: `cd integrations/zotero && npx vitest run test/plugin-state.test.ts test/sidebar.test.ts test/float-panel.test.ts`

Expected: FAIL because the plugin has only `chooseQLabRoot()` and direct `settings.qlabRoot` reads.

- [ ] **Step 4: Replace `chooseQLabRoot` with controller-owned selection**

```ts
private async selectLocalRepository(preferredWindow?: Window): Promise<ResolvedLocalRepositoryTarget | null> {
  const picked = await this.pickLocalFolder(preferredWindow);
  if (!picked) return null;
  const candidateOrTarget = await this.localTargetResolver.inspect(picked);
  if (candidateOrTarget.kind === "unavailable") {
    throw new Error("Choose a valid local Research Loop Git repository");
  }
  const target = candidateOrTarget.kind === "candidate"
    ? await this.confirmLocalCandidate(preferredWindow, candidateOrTarget)
    : candidateOrTarget;
  await this.targetController.switchTo(target);
  return this.targetController.activeSnapshot()!.target;
}
```

Construct owners in plugin startup: `stage(next, signal)` awaits `codex.stageRepositoryTarget(next)` (which first drains the existing transition queue) and stages terminal, QMD, and `mainSite.stageTarget(next)` without touching A; terminal does not spawn an unopened terminal and Main Site stays stopped. In the controller's one synchronous `publish(next, staged)` callback, assign immutable `this.activeTarget = next`, call only synchronous owner commits—`codex.commitRepositoryTarget(staged.codex)`, `mainSite.commitTarget(staged.mainSite)`, and terminal/QMD bindings—from that same `next`, then call `updateInteractionContext()` and render all surfaces once. It must not invoke an async Codex target setter. In `disposeOld(previous)`, after B is published, call `terminal.disposeTarget(previous.target.targetId, previous.targetEpoch)` and `mainSite.disposeTarget(previous.target.targetId, previous.targetEpoch)`; a Main Site close failure propagates to Task 3's post-commit degradation handler while B remains active. No owner may assign an active snapshot itself. Replace every runtime root read with a captured `RepositoryTargetSnapshot`: plugin callbacks, `research-actions.ts` prompt context, `qlab-commands.ts` cwd construction, Float Panel and Sidebar root labels/actions, external-editor cwd, QMD index/edit/save, terminal options, and Main Site callbacks. Each consumer reads `snapshot.target.canonicalRoot`, never a settings root string. Keep external editor local-only and invoke it with that captured root. Delete direct `saveQLabRoot` use and make all choose-root UI callbacks call `selectLocalRepository`.

- [ ] **Step 5: Run plugin and focused target integration tests**

Run: `cd integrations/zotero && npx vitest run test/plugin-state.test.ts test/sidebar.test.ts test/float-panel.test.ts test/repository-target-controller.test.ts`

Expected: PASS. No test stubs `qlabRoot` to control a live target after migration.

- [ ] **Step 6: Prove the inventory has no remaining runtime root consumer**

Run: `cd integrations/zotero && rg -n "qlabRoot|saveQLabRoot|configuredQLabRoot\(" src/plugin.ts src/research-actions.ts src/qlab-commands.ts src/float-panel.ts src/sidebar.ts src/codex-service.ts src/terminal-panel.ts src/qmd-workspace.ts src/research-loop-site.ts --glob '*.ts'`

Expected: no runtime root-setting matches. `qlabRoot` may appear only in `settings.ts` raw migration input and target-focused tests; each listed consumer has a test proving it receives a snapshot and derives `snapshot.target.canonicalRoot`.

- [ ] **Step 7: Commit plugin integration**

```bash
git add integrations/zotero/src/plugin.ts integrations/zotero/src/research-actions.ts integrations/zotero/src/qlab-commands.ts integrations/zotero/src/float-panel.ts integrations/zotero/src/sidebar.ts integrations/zotero/test/plugin-state.test.ts integrations/zotero/test/sidebar.test.ts integrations/zotero/test/float-panel.test.ts integrations/zotero/test/research-actions.test.ts integrations/zotero/test/qlab-commands.test.ts
git commit -m "feat(zotero): switch local repository targets atomically"
```

### Task 8: Run the Slice 1 behavioral regression gate

**Files:**
- Test: `integrations/zotero/test/repository-target-controller.test.ts`, `test/plugin-state.test.ts`, `test/codex-service.test.ts`, `test/terminal-panel.test.ts`, `test/qmd-workspace.test.ts`, `test/research-loop-site.test.ts`, `test/research-actions.test.ts`, `test/qlab-commands.test.ts`, `test/float-panel.test.ts`, `test/sidebar.test.ts`

**Interfaces:**
- Consumes: completed Tasks 1-7.
- Produces: evidence that the actual target-switch behavior preserves the atomic-switch and trust-boundary invariants.

- [ ] **Step 1: Run the focused behavioral suite**

Run: `cd integrations/zotero && npx vitest run test/repository-target.test.ts test/local-repository-target-resolver.test.ts test/repository-target-controller.test.ts test/codex-service.test.ts test/stored-conversation-resume.test.ts test/terminal-panel.test.ts test/qmd-workspace.test.ts test/research-loop-site.test.ts test/plugin-state.test.ts test/sidebar.test.ts test/float-panel.test.ts test/research-actions.test.ts test/qlab-commands.test.ts`

Expected: PASS. This suite includes exact NUL-byte identity inputs; ready/empty/partial/missing/incompatible migration; raw missing legacy-pref startup; idempotent no-resolver/no-write migration; blocker recheck; B staging/persistence/publish before A disposal; persistence failure that leaves A live; post-commit degradation; DOM-backed Save/Discard/Cancel blockers; XUL-browser stale callback isolation; exact Main Site `persist:B,publish:B,close:A,exit:A` ordering; and snapshot-derived root behavior in plugin, research actions, commands, Float Panel, and Sidebar.

- [ ] **Step 2: Run the Linux behavior gate**

Run: `cd integrations/zotero && CC=cc make -C native clean test && npm run check && npm test`

Expected: PASS on Linux after Task 0. Do not run `npm run build` or `npm run verify` on Linux.

- [ ] **Step 3: Run the macOS release gate when on macOS**

Run: `cd integrations/zotero && npm run verify`

Expected: PASS on macOS, including the signed/universal packaging path. This step is skipped, not reported as passing, on Linux.

- [ ] **Step 4: Commit only behavioral implementation and tests**

```bash
git status --short
# Confirm that no generated public/knowledge output or unrelated changes are staged.
git commit -m "test(zotero): verify local target switching behavior"
```

## Spec Coverage Review

- Local target model, canonical root, UUID-backed repository identity, and target ID are implemented in Tasks 1-2.
- Ready/empty/partial/missing/incompatible legacy migration behavior is tested in Tasks 1 and 4; empty/partial remain candidates until Task 2 confirmation succeeds.
- Attempt ID, epoch, staged-B-only pre-commit disposal, queued/superseded selection, and post-commit degradation are implemented and tested in Task 3.
- Codex conversation/workspace-object isolation and no-steering rule are implemented in Task 4.
- Terminal PTY, QMD state, unsaved source, pending Keep, and late callbacks are handled in Task 5.
- On-demand Main Site session ownership and old-process stop are implemented in Task 6.
- All root-consuming plugin entry points are moved to the controller-owned active snapshot in Task 7.
- Behavioral validation is completed in Task 8; the macOS packaging command is deliberately not claimed on Linux.

## Type Consistency Review

- `RepositoryTargetSnapshot` is the only cross-owner binding and always contains `target.targetId`, `target.canonicalRoot`, and `targetEpoch`.
- `TargetSwitchBlocker` uses the same four variants in controller, Codex, and QMD interfaces.
- `TerminalPaperOptions`, `MainSiteSession`, and QMD bindings all carry the exact `targetId` and `targetEpoch` pair used by `RepositoryTargetController.isCurrent()`.
