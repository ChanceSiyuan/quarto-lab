# QLab Remote Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the already-landed local Repository Target architecture with SSH profiles, a verified Linux remote helper, and a target-owned `AgentConnection` that returns a Codex `AgentClient` running beside the remote repository.

**Architecture:** The existing `RepositoryTargetController` remains the only publisher of active target state. A target-owned OpenSSH multiplexing master supplies setup, browse, repository-handshake, and agent channels; every channel completes the same versioned helper handshake before a remote app-server JSONL stream is handed to the unchanged Codex protocol client. Local and SSH launch details move behind `AgentConnection`, so `CodexService` owns conversations but never decides where a process runs.

**Tech Stack:** TypeScript 7, Vitest 4, Zotero 9/Gecko, OpenSSH, UTF-8 JSONL, C17, Zig 0.14.1 static musl cross-compilation, Python `unittest`, esbuild/XPI packaging.

## Global Constraints

- This is Slice 2. The complete `docs/superpowers/plans/2026-07-31-qlab-local-target-switching.md` Slice 1 is a hard prerequisite; extend its `repository-target.ts`, `repository-target-controller.ts`, settings migration, target resource owners, and tests. Do not recreate those files or write tests that fail merely because Slice 1 symbols are missing.
- SSH targets run Codex on the same host as the canonical remote repository. Do not add a local clone, SSHFS, repository rsync/scp, public app-server port, local execution against a remote path, or local-path fallback.
- First release supports exactly `linux-x86_64-static` and `linux-aarch64-static`, statically linked against musl, Linux kernel 5.4 or newer. Unsupported OS, architecture, kernel, helper version, protocol major, archive digest, executable digest, or self-test fails before repository activation.
- OpenSSH resolves hostname, user, port, keys, `Include`, `ProxyJump`, agent, and known-host behavior. Preferences store only a concrete profile alias and resolved target identity—never passwords, passphrases, private keys, API keys, Codex tokens, or arbitrary SSH arguments.
- All steady-state channels share one target-owned multiplexing master and its private `0700` runtime directory. Master loss increments one connection generation, closes every logical channel, invalidates staged activation, and—only for the still-published matching target—triggers the single reconnect owner defined in Task 6. Old-generation frames stay fenced throughout reconnect.
- Every bound helper frame carries protocol/helper version, target ID/epoch, host/repository identity, negotiated capabilities, and a bounded request/event identifier. Pre-resolution activation frames use only the explicit activation identity defined in Task 3; they never invent target IDs. Root-bound channels must agree or activation fails.
- Remote Chat may write through remote Codex only to remote `drafts/`, `literature/`, and `work/`. Workbench QMD read/write, Visual Edit, Keep, preview, Main Site, repository commands, External Editor, remote initialization, and remote promotion remain visibly disabled until later slices.
- Remote app-server context contains remote cwd/roots only. Local Zotero data crosses the boundary only as explicit dynamic-tool content; local PDF paths, attachment/cache paths, profile paths, and local repository paths never appear in remote prompts or app-server requests.
- Slice-1 Task 0's PATH-resolved zip/unzip and Linux `<pty.h>`/`-lutil` portability fix is a prerequisite. Before it lands, stop with that explicit precondition; after it lands, Linux may run `npm run native:test`, but signed universal/XPI assembly remains macOS-only because it invokes Apple tooling. Never reintroduce `/usr/bin/zip` as application logic.
- Use TDD. Focused TypeScript tests run from `integrations/zotero` with `npx vitest run test/<file>.test.ts`; per-commit gate is `npm run check && npm test`. Remote native tests use `make -C native remote-test`. Do not claim Linux `npm run build` succeeds.

---

### Task 1: Extend the landed target domain and controller for SSH

**Files:**
- Modify: `integrations/zotero/src/repository-target.ts`
- Modify: `integrations/zotero/src/repository-target-controller.ts`
- Modify: `integrations/zotero/src/settings.ts`
- Modify: `integrations/zotero/test/repository-target.test.ts`
- Modify: `integrations/zotero/test/repository-target-controller.test.ts`

**Interfaces:**
- Consumes: landed `LocalRepositoryTarget`, `ResolvedLocalRepositoryTarget`, `RepositoryTargetSnapshot`, `StoredTargetPreferences`, `RepositoryTargetController.switchTo()`, `activeSnapshot()`, and `isCurrent()`.
- Produces: unresolved `SshRepositoryTarget = Readonly<{ kind: "ssh"; sshProfile: string; root: string }>` and resolved `ResolvedSshRepositoryTarget` with `canonicalRoot`, the actual master-authenticated `acceptedHostKeyFingerprint`, `endpointId`, `hostInstanceId`, raw Git-private `repositoryUuid`, derived `repositoryId`, and `targetId`; only Task 5 may construct the resolved form. `AcceptedHostKeyFingerprint` accepts only canonical OpenSSH `SHA256:<unpadded-base64>` text. Produces `RepositoryTarget` and `ResolvedRepositoryTarget` unions and widens the existing `RepositoryTargetSnapshot.target`.
- Produces: `RepositoryTargetCapabilities = Readonly<{ chat: boolean; qmdRead: boolean; qmdWrite: boolean; terminal: boolean; preview: boolean; mainSiteSupported: boolean; externalEditor: boolean; promoteDraft: boolean }>` stored on every snapshot. Slice-2 SSH values are `{ chat:true, qmdRead:false, qmdWrite:false, terminal:false, preview:false, mainSiteSupported:false, externalEditor:false, promoteDraft:false }`.
- Produces strict schema v2 without dropping any v1 state:

```ts
export type StoredTargetPreferencesV2 = Readonly<{
  version: 2;
  active: ResolvedRepositoryTarget | null;
  pendingCandidate: PendingLocalRepositoryCandidate | null;
  legacyUnassigned: readonly LegacyThreadBinding[];
  migratedLegacy: boolean;
}>;
export type DecodedTargetPreferences = Readonly<{
  preferences: StoredTargetPreferencesV2;
  rewrite: "v1-to-v2" | null;
}>;
```

A valid v1 local record maps field-for-field to v2 and retains the exact `repositoryId`/`targetId`, pending candidate, unassigned bindings, and `migratedLegacy`. Startup persists that migration once before target-bound restore. A malformed/future record returns the exact empty v2 value with `rewrite:null`; malformed data is never partially salvaged into an active target. V2 accepts one active local or SSH resolved target, including the non-secret accepted host-key fingerprint and UUIDs needed to revalidate identity, but not credentials, helper paths, control sockets, runtime leases, or an unvalidated candidate SSH root. A stored SSH value is only a complete restoration expectation; it is never authority to publish without Task-5 re-resolution and exact fingerprint/host/repository/derived-ID comparison.

- [ ] **Step 1: Extend the existing tests so they fail on the local-only unions and codec**

```ts
it("round-trips one resolved SSH target while preserving migration fields", () => {
  const stored = decodeStoredTargetPreferences(JSON.stringify({
    version: 2,
    active: resolvedSshRecord(),
    pendingCandidate: { kind: "candidate", canonicalRoot: "/local/new", state: "partial" },
    legacyUnassigned: [{ threadId: "t", recordedCwd: "/gone", reason: "missing" }],
    migratedLegacy: true,
  }));
  expect(stored).toMatchObject({ rewrite: null, preferences: {
    active: { kind: "ssh", sshProfile: "qlab-gpu", canonicalRoot: "/srv/research-loop", acceptedHostKeyFingerprint: "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" },
    pendingCandidate: { canonicalRoot: "/local/new", state: "partial" },
    legacyUnassigned: [{ threadId: "t", reason: "missing" }], migratedLegacy: true,
  }});
});

it("migrates a valid v1 record without changing identity or legacy state", () => {
  const decoded = decodeStoredTargetPreferences(validV1({
    repositoryId: "a".repeat(64), targetId: "b".repeat(64),
    pendingCandidate: candidate("/empty"), legacyUnassigned: [legacy("thread-1")],
    migratedLegacy: true,
  }));
  expect(decoded.rewrite).toBe("v1-to-v2");
  expect(decoded.preferences).toMatchObject({ version: 2, active: {
    repositoryId: "a".repeat(64), targetId: "b".repeat(64),
  }, pendingCandidate: { canonicalRoot: "/empty" },
  legacyUnassigned: [{ threadId: "thread-1" }], migratedLegacy: true });
});

it.each(["{}", '{"version":3}', badSshId(), badSshFingerprint(), badPendingCandidate()])("fails closed for %s", (raw) => {
  expect(decodeStoredTargetPreferences(raw)).toEqual({
    preferences: { version: 2, active: null, pendingCandidate: null, legacyUnassigned: [], migratedLegacy: false },
    rewrite: null,
  });
});

it("publishes Slice-2 SSH capabilities as one immutable snapshot", async () => {
  const controller = harnessWithResolvedSshTarget();
  const snapshot = await controller.switchTo(resolvedSsh("qlab-gpu", "/srv/research-loop"));
  expect(snapshot.capabilities).toEqual({
    chat: true, qmdRead: false, qmdWrite: false, terminal: false, preview: false,
    mainSiteSupported: false, externalEditor: false, promoteDraft: false,
  });
  expect(Object.isFrozen(snapshot.capabilities)).toBe(true);
});
```

- [ ] **Step 2: Run the existing target tests and verify the precise red state**

Run: `cd integrations/zotero && npx vitest run test/repository-target.test.ts test/repository-target-controller.test.ts`

Expected: FAIL because the landed codec returns v1/local-only state, the controller accepts only `ResolvedLocalRepositoryTarget`, and `RepositoryTargetSnapshot` has no capabilities. All v1 migration fixtures still compile, proving the red state is not a missing Slice-1 import.

- [ ] **Step 3: Widen the existing target/controller types without adding a second controller**

```ts
export type RepositoryTarget = LocalRepositoryTarget | SshRepositoryTarget;
export type ResolvedRepositoryTarget = ResolvedLocalRepositoryTarget | ResolvedSshRepositoryTarget;
export type RepositoryTargetSnapshot = Readonly<{
  target: ResolvedRepositoryTarget;
  targetEpoch: number;
  capabilities: RepositoryTargetCapabilities;
}>;

export function capabilitiesFor(target: ResolvedRepositoryTarget): RepositoryTargetCapabilities {
  return Object.freeze(target.kind === "local"
    ? { chat: true, qmdRead: true, qmdWrite: true, terminal: true, preview: true, mainSiteSupported: true, externalEditor: true, promoteDraft: true }
    : { chat: true, qmdRead: false, qmdWrite: false, terminal: false, preview: false, mainSiteSupported: false, externalEditor: false, promoteDraft: false });
}
```

Change only the landed controller's resolved-target parameter/active snapshot union; retain its attempt, epoch, blockers, persistence-before-publish, and owner disposal semantics. Persist the complete v2 value above. When startup decodes `rewrite:"v1-to-v2"`, synchronously save v2 before hydrating/publishing active state; the second load returns `rewrite:null` and performs no write.

- [ ] **Step 4: Run target tests and typecheck green**

Run: `cd integrations/zotero && npx vitest run test/repository-target.test.ts test/repository-target-controller.test.ts && npm run check`

Expected: PASS; all prior local switching and legacy tests remain green, exact v1 identities survive migration, malformed IDs fail closed, and SSH capabilities are frozen.

- [ ] **Step 5: Refactor duplicate local/SSH capability fixtures to `capabilitiesFor()` and run the full TypeScript gate**

Run: `cd integrations/zotero && npm run check && npm test`

Expected: PASS.

- [ ] **Step 6: Commit the Slice-2 target extension**

```bash
git add integrations/zotero/src/repository-target.ts integrations/zotero/src/repository-target-controller.ts integrations/zotero/src/settings.ts integrations/zotero/test/repository-target.test.ts integrations/zotero/test/repository-target-controller.test.ts
git commit -m "feat(zotero): extend repository targets for SSH"
```

### Task 2: Discover concrete OpenSSH aliases and own one multiplexing master

**Files:**
- Create: `integrations/zotero/src/openssh-profiles.ts`
- Create: `integrations/zotero/src/ssh-target-transport.ts`
- Create: `integrations/zotero/test/openssh-profiles.test.ts`
- Create: `integrations/zotero/test/ssh-target-transport.test.ts`
- Modify: `integrations/zotero/src/native-bridge.ts`
- Modify: `integrations/zotero/test/native-bridge.test.ts`

**Interfaces:**
- Produces: `OpenSshProfileProvider.listConcreteAliases(): Promise<OpenSshProfile[]>` and `resolve(alias): Promise<ResolvedOpenSshProfile>`. Parse literal `Host` aliases across recursively expanded user `Include` directives; expand `~`, resolve relative Includes from the OpenSSH user-config base `~/.ssh`, expand globs in lexical order, cap depth, break canonical-file cycles, and deduplicate both files and aliases without changing first-seen alias order. Omit wildcard/negated aliases. `ssh -G -- <alias>` remains authoritative for effective hostname, user, port, identity/proxy settings.
- Produces no generic channel opener. The complete Slice-2 surface is:

```ts
export type VerifiedRemoteHelperPath = string & { readonly __verifiedRemoteHelperPath: unique symbol };
export type VerifiedRemoteHelperCommand = string & { readonly __verifiedRemoteHelperCommand: unique symbol };
export type InstalledHelper = Readonly<{
  helperVersion:string; tuple:"linux-x86_64-static"|"linux-aarch64-static";
  executableSha256:string; absoluteVersionedPath:VerifiedRemoteHelperPath;
}>;
export interface SshMaster {
  readonly profile: ResolvedOpenSshProfile;
  readonly controlPath: string;
  readonly generation: number;
  readonly acceptedHostKeyFingerprint: AcceptedHostKeyFingerprint;
  readonly installedHelper: InstalledHelper | null;
  probeRemotePlatform(): Promise<Readonly<{ os:"linux"; arch:"x86_64"|"aarch64"; kernel:string }>>;
  installVerifiedHelper(input: VerifiedHelperInstall): Promise<InstalledHelper>;
  openBrowse(): Promise<SshChannel>;
  openRepositoryHandshake(): Promise<SshChannel>;
  openAgent(): Promise<SshChannel>;
  openSetupAuth(): Promise<RemoteSetupSession>;
  onLost(listener: (loss: SshMasterLoss) => void): () => void;
  close(): Promise<void>;
}
export interface SshChannel {
  readonly channelId: string;
  readonly generation: number;
  write(bytes: Uint8Array): Promise<void>;
  onBytes(listener: (bytes: Uint8Array) => void): () => void;
  onExit(listener: (exit: { code:number|null; signal:number|null; reason:string }) => void): () => void;
  close(): Promise<void>;
}
```

Each opener constructs one exact argv and accepts no caller args. It rejects until `installVerifiedHelper` has atomically bound an `InstalledHelper` containing the manifest-selected, digest-verified absolute versioned executable path. Browse/repository-handshake/agent use `/usr/bin/ssh -T -S <control> -o BatchMode=yes -- <alias> <bound-versioned-helper> <fixed-mode>`; setup auth uses the same internal binding with `-tt` and fixed mode `setup codex-device-auth`. No opener resolves or executes the mutable `current` symlink, and no caller can supply or alter the helper path. Root/identity travel only in the JSON hello, never the SSH command line. Platform probe is one fixed remote script constant that emits only uname OS/arch/release; install streams a verified artifact to the fixed Task-4 installer and accepts only a typed manifest/artifact, never executable/argv/shell input.

The master runtime directory is `0700`; before spawn, create `<private>/master.log` as a regular owner-only `0600` file and never follow a symlink. The exact master argv is `/usr/bin/ssh -v -E <private>/master.log -MN -o FingerprintHash=sha256 -o ControlMaster=yes -o ControlPersist=600 -o BatchMode=yes -o ControlPath=<private>/master.sock -- <alias>`. Parse authenticated-key diagnostics only from that main-process `-E` file, never inherited/shared stderr: accept one distinct final-target line `Server host key: <algorithm> SHA256:<digest>` (identical repeats are harmless), canonicalize the fingerprint, bound the file, and do not resolve `connect()` until that fingerprint and the control socket are live. ProxyJump/ProxyCommand child stderr is captured separately and is never an identity source. No profile, known-hosts lookup, helper response, proxy diagnostic, or user-supplied string may stand in for the key authenticated by that master.
- Produces: `RemoteSetupSession` for two fixed PTY actions: unknown-host-key acceptance and Codex device auth. It exposes output to xterm, input/resize, exit, and close; it never returns credentials.
- `NativeBridge` gains structured local process sessions sufficient to launch `/usr/bin/ssh` with an argv array; it still rejects non-absolute executables.

- [ ] **Step 1: Write argv-level tests with a real fake SSH executable below NativeBridge**

```ts
it("discovers literal aliases through Include and lets ssh -G resolve them", async () => {
  runtime.write("~/.ssh/config", "Include conf.d/*.conf conf.d/cycle.conf\nHost *.wild\n  User ignored\n");
  runtime.write("~/.ssh/conf.d/a.conf", "Include nested/*.conf\nHost qlab-gpu qlab-gpu\n");
  runtime.write("~/.ssh/nested/profile.conf", "Host qlab-arm\n");
  runtime.write("~/.ssh/conf.d/cycle.conf", "Include conf.d/cycle.conf\nHost qlab-gpu\n");
  runtime.sshG("qlab-gpu", "hostname 10.0.0.8\nuser alice\nport 22\n");
  expect((await provider.listConcreteAliases()).map((x) => x.alias)).toEqual(["qlab-arm", "qlab-gpu"]);
});

it("creates one private master and fans master loss out to every channel", async () => {
  const master = await transport.connect("qlab-gpu", setup);
  const agent = await master.openAgent();
  const browse = await master.openBrowse();
  const exits: unknown[] = [];
  agent.onExit((exit) => exits.push(["agent", exit]));
  browse.onExit((exit) => exits.push(["browse", exit]));
  fakeSsh.killMaster(255, "connection reset");
  expect(exits).toEqual([
    ["agent", expect.objectContaining({ code: 255, reason: "connection reset" })],
    ["browse", expect.objectContaining({ code: 255, reason: "connection reset" })],
  ]);
});
```

Also assert the exact master argv includes `-v -E <private>/master.log -MN -o FingerprintHash=sha256` followed by the fixed control options/order above; assert the log is precreated regular `0600`, and missing/malformed/distinct authenticated-key lines fail closed. Inject a fake fingerprint through ProxyCommand stderr and a jump-host diagnostic alongside the target log: neither may replace or make ambiguous the sole final-target fingerprint from the master log. Assert no merely configured/known-hosts fingerprint is accepted. Assert fixed probe/install and every fixed channel argv, runtime-directory mode `0700`, no log/control path in preferences, and alias rejection before spawn. Before verified install, all helper openers reject; after install, concurrently switch `current` and prove every opener still executes the lease-bound absolute versioned helper. Assert openers reject after loss/close and that no `open(mode,args)` symbol exists.

- [ ] **Step 2: Run focused tests and verify they fail for new symbols, not Slice-1 symbols**

Run: `cd integrations/zotero && npx vitest run test/openssh-profiles.test.ts test/ssh-target-transport.test.ts test/native-bridge.test.ts`

Expected: FAIL with unresolved `openssh-profiles`/`ssh-target-transport` imports; existing NativeBridge tests pass.

- [ ] **Step 3: Implement alias discovery, master generation, and fixed setup PTYs**

```ts
export type SetupAction =
  | { kind: "accept-host-key"; argv: readonly ["/usr/bin/ssh", "-tt", "-o", "BatchMode=no", "-o", "ControlMaster=no", "--", string, "/bin/true"] }
  | { kind: "codex-device-auth"; argv: readonly ["/usr/bin/ssh", "-tt", "-S", string, "-o", "BatchMode=yes", "--", string, VerifiedRemoteHelperCommand] };
```

Unknown-host-key remediation launches only the first action, displays OpenSSH's fingerprint prompt, and closes after `/bin/true`; cancel kills that process and leaves the old target active. Device auth requires the established master and its verified versioned helper binding. Its local `forkpty` is created with a fixed raw/no-echo termios profile before `exec`, so OpenSSH's `-tt` request transmits raw/no-echo tty modes to the remote PTY; this fixed option is unavailable to arbitrary callers. Task 3 verifies/forces raw mode again at helper entry and defines its machine-hello-to-raw-PTY transition before fixed `execvp("codex", {"codex","login","--device-auth",NULL})`.

Master loss calls every channel's `onExit` listeners once, advances the transport's next connection generation, and fences old writes/publication. `close()` is idempotent and ordered: stop new opens; close logical channels/setup PTY; invoke `/usr/bin/ssh -S <control> -O exit -- <alias>`; wait then terminate the master if necessary; unlink the socket; remove only that validated private runtime directory. Natural master loss skips `-O exit` but performs the same channel fanout/socket/directory cleanup exactly once.

- [ ] **Step 4: Run alias/master tests green**

Run: `cd integrations/zotero && npx vitest run test/openssh-profiles.test.ts test/ssh-target-transport.test.ts test/native-bridge.test.ts`

Expected: PASS, including relative/glob Include expansion, lexical order, cycle/depth handling, alias deduplication, wildcard omission, `ssh -G` error, all exact fixed channel argv, setup cancellation, idempotent cleanup order, and master-loss fanout.

- [ ] **Step 5: Refactor all SSH argv creation into `ssh-target-transport.ts` and search for shell-string construction**

Run: `cd integrations/zotero && ! rg -n "ssh .*\$\{|sh -c.*ssh|sshProfile.*split" src test && npm run check && npm test`

Expected: `rg` finds no production shell-string SSH construction; TypeScript gate passes.

- [ ] **Step 6: Commit OpenSSH transport ownership**

```bash
git add integrations/zotero/src/openssh-profiles.ts integrations/zotero/src/ssh-target-transport.ts integrations/zotero/src/native-bridge.ts integrations/zotero/test/openssh-profiles.test.ts integrations/zotero/test/ssh-target-transport.test.ts integrations/zotero/test/native-bridge.test.ts
git commit -m "feat(zotero): own SSH target transport"
```

### Task 3: Define the helper handshake and implement host/repository identity

**Files:**
- Create: `integrations/zotero/src/remote-helper-protocol.ts`
- Create: `integrations/zotero/test/remote-helper-protocol.test.ts`
- Create: `integrations/zotero/native/include/qlab_remote_protocol.h`
- Create: `integrations/zotero/native/src/qlab_remote_helper.c`
- Create: `integrations/zotero/native/tests/test_remote_helper.py`
- Modify: `integrations/zotero/native/Makefile`

**Interfaces:**
- Produces two explicit handshake phases. Pre-resolution frames use a random bounded `activationId` because `targetId` cannot exist until host/repository identity is returned. Bound frames use the complete target identity. Maximum physical JSONL frame is 8 MiB; IDs are 1–128 ASCII alphanumerics/`._:-`; unknown fields are rejected in handshakes and method params.
- Produces helper-private host UUID at `~/.qlab/state/host-instance-id`, directory mode `0700`, file mode `0600`; create with `O_CREAT|O_EXCL`, fsync file and parent, validate RFC-4122 on every read.
- Produces canonical root plus a Git-private raw `repositoryUuid` from fixed `git -C <canonicalRoot> rev-parse --git-path qlab/repository-id`. Accept exactly one bounded UTF-8 path line and remove only its single optional trailing LF—never general whitespace-trim; reject CR, NUL, empty/multiple lines, and extra output. Resolve a relative result against the canonical root, normalize it, obtain the canonical common Git directory with fixed `git -C <canonicalRoot> rev-parse --path-format=absolute --git-common-dir`, and require the identity path's descriptor-relative containment beneath that directory before opening anything. From the verified common-directory descriptor, create the absent private `qlab` parent with `mkdirat`, then open it using `openat(..., O_DIRECTORY|O_NOFOLLOW)`; require current-user ownership and mode `0700`, fsync the common directory after creation, and reject a symlink, non-directory, or permissive existing parent. Task 5 derives endpoint/repository/target IDs client-side using the Slice-1 digest contract. The helper never hashes repository contents or treats path as repository identity.

- [ ] **Step 1: Write protocol codec and real-helper identity tests**

```ts
export type ActivationClientHello = Readonly<{
  kind:"hello"; phase:"activation"; requestId:string; protocolVersion:1; helperVersion:string;
  activationId:string; mode:"browse"|"repository-handshake"|"setup-auth";
  candidateRoot:string|null; expectedHostInstanceId:string|null; requestedCapabilities:readonly string[];
}>;
export type ActivationServerHello = Readonly<{
  kind:"hello"; phase:"activation"; requestId:string; protocolVersion:1; helperVersion:string;
  activationId:string; mode:ActivationClientHello["mode"]; hostInstanceId:string;
  canonicalRoot:string|null; repositoryUuid:string|null; capabilities:readonly string[];
}>;
export type BoundClientHello = Readonly<{
  kind:"hello"; phase:"bound"; requestId:string; protocolVersion:1; helperVersion:string;
  mode:"agent"|"repository"; targetId:string; targetEpoch:number;
  canonicalRoot:string; expectedHostInstanceId:string; expectedRepositoryUuid:string; expectedRepositoryId:string;
  requestedCapabilities:readonly string[];
}>;
export type BoundServerHello = Readonly<{
  kind:"hello"; phase:"bound"; requestId:string; protocolVersion:1; helperVersion:string;
  mode:BoundClientHello["mode"]; targetId:string; targetEpoch:number;
  canonicalRoot:string; hostInstanceId:string; repositoryUuid:string; repositoryId:string;
  helperInstanceId:string; capabilities:readonly string[];
}>;
export type BoundFrameContext = Readonly<{
  protocolVersion:1; helperVersion:string; targetId:string; targetEpoch:number;
  hostInstanceId:string; repositoryId:string; capabilities:readonly string[];
}>;
export type CanonicalRemoteDirectory = string & { readonly __canonicalRemoteDirectory: unique symbol };
export type RemoteDirectoryEntry = Readonly<{ name:string; path:CanonicalRemoteDirectory; kind:"directory" }>;
export type CodexProbeResult =
  | Readonly<{ state:"missing" }>
  | Readonly<{ state:"incompatible"; foundVersion:string; minimumVersion:string }>
  | Readonly<{ state:"unauthenticated"; version:string }>
  | Readonly<{ state:"ready"; version:string }>;
export interface ActivationRpcMap {
  "browse.home": { params:Record<string, never>; result:{ path:CanonicalRemoteDirectory } };
  "browse.listDirectories": { params:{ path:CanonicalRemoteDirectory }; result:{ entries:readonly RemoteDirectoryEntry[] } };
  "browse.canonicalize": { params:{ input:string }; result:{ path:CanonicalRemoteDirectory } };
  "codex.probe": { params:Record<string, never>; result:CodexProbeResult };
}
export type ActivationMethod = keyof ActivationRpcMap;
export type ActivationFrameContext = Readonly<{
  protocolVersion:1; helperVersion:string; activationId:string; hostInstanceId:string; capabilities:readonly string[];
}>;
export type ActivationRequest = { [M in ActivationMethod]:
  ActivationFrameContext & Readonly<{ kind:"request"; id:string; method:M; params:ActivationRpcMap[M]["params"] }>
}[ActivationMethod];
export type ActivationErrorCode =
  | "INVALID_REQUEST" | "METHOD_NOT_ALLOWED" | "PATH_REJECTED" | "NOT_FOUND"
  | "NOT_DIRECTORY" | "IDENTITY_MISMATCH" | "PROBE_FAILED" | "INTERNAL";
export type ActivationResponse = { [M in ActivationMethod]:
  | (ActivationFrameContext & Readonly<{ kind:"response"; id:string; method:M; result:ActivationRpcMap[M]["result"]; error?:never }>)
  | (ActivationFrameContext & Readonly<{ kind:"response"; id:string; method:M; result?:never; error:{ code:ActivationErrorCode; message:string } }>)
}[ActivationMethod];
export type HelperRequest = BoundFrameContext & Readonly<{ kind:"request"; id:string }>;
export type HelperResponse = BoundFrameContext & Readonly<{ kind:"response"; id:string }>;
export type HelperEvent = BoundFrameContext & Readonly<{ kind:"event"; id:string }>;
export type StreamReady = BoundFrameContext & Readonly<{ kind:"stream-ready"; requestId:string; stream:"codex-jsonl" }>;
export type SetupReady = Readonly<{ kind:"setup-ready"; requestId:string; protocolVersion:1; helperVersion:string; activationId:string; hostInstanceId:string; capability:"codex-device-auth-pty" }>;
```

Activation/browse request/response frames use only the closed `ActivationRpcMap` and echo `{ protocolVersion, helperVersion, activationId, hostInstanceId, capabilities }`; the absence of target/repository fields is the documented pre-resolution exception, never silently filled with placeholders. `browse.home` returns the canonical login home, `browse.listDirectories` returns directories only with bounded names/count, and `browse.canonicalize` accepts one bounded absolute UTF-8 input and rejects files, relative paths, NUL, and traversal. `codex.probe` runs only the helper-owned fixed `codex --version` and `codex login status` probes with bounded output/deadlines and maps them to the four-state result; no request can supply a command, argv, environment, or executable. The C dispatcher switches exhaustively over these four methods, rejects unknown/extra/missing fields before side effects, and returns only the closed error codes.

Every fixed root-bound channel receives `canonicalRoot` only in `BoundClientHello`, never argv. The helper canonicalizes it, requires byte equality with the supplied canonical form, resolves the Git-private UUID through the no-follow path below, checks host UUID/raw repository UUID against the expectations, and echoes canonical root/raw UUID plus the client's opaque expected `repositoryId`. It does not know the SSH host key and therefore never claims to derive or attest endpoint/repository/target IDs. The client recomputes endpoint ID from `master.acceptedHostKeyFingerprint + hostInstanceId`, then repository/target IDs from the returned raw UUID/root, and rejects any mismatch before accepting `BoundServerHello` or sending app-server/repository traffic. After that, every machine frame carries the full `BoundFrameContext` plus request/event ID.

Python tests start multiple actual helper processes concurrently against one initially UUID-less state dir/repository and assert exactly one host UUID and one Git-private repository UUID wins and every process reports those same validated values; a copied repository with a different Git-private UUID differs. Cover absent/concurrently-created `qlab` parent, parent symlink/non-directory/permissive mode, absolute/relative Git-path output, leading/trailing whitespace, CR/NUL/multiple-line output, traversal/out-of-Git-dir output, symlink components/final symlink, invalid existing UUID, permissive existing mode, and an `EEXIST` creation race. Exercise all four activation methods against the real helper and reject unknown methods plus missing/extra/wrongly typed fields without filesystem/process side effects. TypeScript/native cross-channel cases vary canonical root, raw UUID, opaque repository ID, target ID/epoch, accepted fingerprint, host UUID, and capabilities one at a time; every mismatch closes the channel before Codex/repository dispatch. Duplicate IDs terminate with a typed protocol error.

- [ ] **Step 2: Run protocol/native tests and verify the expected red state**

Run: `cd integrations/zotero && npx vitest run test/remote-helper-protocol.test.ts && make -C native remote-test`

Expected: TypeScript fails on the missing protocol module; `make` fails because `remote-test` and `qlab_remote_helper.c` do not exist.

- [ ] **Step 3: Implement strict codecs and the helper identity/handshake modes**

```c
typedef enum { MODE_BROWSE, MODE_REPOSITORY_HANDSHAKE, MODE_AGENT, MODE_SETUP_AUTH } HelperMode;
static int run_channel(HelperMode mode);
static bool load_or_create_host_instance_id(const char *state_dir, char out[37]);
static bool resolve_repository_uuid(const char *canonical_root, char out_uuid[37]);
```

The first complete line must be the hello appropriate to the fixed command. `browse` then dispatches only `ActivationRpcMap`; `repository-handshake` canonicalizes/validates the candidate root and returns host UUID/root/repository UUID before any target ID is computed. Every later root-bound mode canonicalizes `BoundClientHello.canonicalRoot` and performs the same descriptor/UUID verification; no fixed SSH command carries a root. Resolve the Git-private path through already-open canonical directory descriptors; reject symlinks and non-regular existing files. Safely create/open/validate/fsync the private `qlab` parent as specified above, then create a fresh RFC-4122 UUID as mode `0600` with `openat(..., O_CREAT|O_EXCL|O_NOFOLLOW)`, write completely, fsync the file and containing directory, and close. On `EEXIST`, discard the candidate and reread through the same no-follow path; every read requires a single canonical UUID line, regular-file ownership, and no group/other permission bits. Concurrent helpers therefore converge on the winner rather than overwriting or reporting different IDs. Root-bound agent mismatch exits 78 before Codex. Agent echoes the client-supplied opaque repository/target binding only after root/host/raw-UUID validation, sends one `BoundServerHello`, forks fixed `codex app-server --stdio`, sends one `StreamReady`, then relays raw Codex JSONL; `SshSessionSocket` never sees the machine frames.

Setup auth is not an implicit protocol exception: the local NativeBridge creates the fixed device-auth `forkpty` with raw/no-echo termios before launching OpenSSH `-tt`; OpenSSH transmits those tty modes, and the remote helper immediately applies/verifies raw/no-echo on stdin before reading a byte. The client sends `ActivationClientHello(mode:"setup-auth")`; the helper emits `ActivationServerHello` then `SetupReady`; only after both validate does each side transition to raw PTY bytes and the helper `execvp`s fixed `codex login --device-auth`. A real nested-PTY test proves the hello is not echoed, LF is not rewritten to CRLF, fragmented JSON survives byte-for-byte, and no machine line reaches xterm before `SetupReady`; afterward raw Codex bytes do. Input is bounded until ready; cancel closes/kills/reaps once. Direct unknown-host-key acceptance is the sole non-helper setup path because OpenSSH itself owns that fingerprint prompt.

- [ ] **Step 4: Run protocol and actual helper tests green**

Run: `cd integrations/zotero && npx vitest run test/remote-helper-protocol.test.ts && make -C native remote-test`

Expected: PASS for the closed activation dispatcher/four Codex states, activation-before-target identity, fragmented UTF-8, overlong frame, early EOF, malformed/extra hello or RPC fields, duplicate/unknown ID/method, version/capability mismatch, persisted host UUID, safely created private Git parent/raw repository UUID, bound cross-channel mismatch, stream transition, and raw/no-echo setup machine-to-PTY transition.

- [ ] **Step 5: Refactor shared bounded JSONL parsing in C and TypeScript, then rerun both suites**

Run: `cd integrations/zotero && npx vitest run test/remote-helper-protocol.test.ts && make -C native remote-test`

Expected: PASS with one codec implementation per language.

- [ ] **Step 6: Commit the helper wire contract**

```bash
git add integrations/zotero/src/remote-helper-protocol.ts integrations/zotero/test/remote-helper-protocol.test.ts integrations/zotero/native/include/qlab_remote_protocol.h integrations/zotero/native/src/qlab_remote_helper.c integrations/zotero/native/tests/test_remote_helper.py integrations/zotero/native/Makefile
git commit -m "feat(zotero): define remote helper protocol"
```

### Task 4: Build, package, bootstrap, verify, and roll back static helper tuples

**Files:**
- Create: `integrations/zotero/native/remote-helper-tuples.json`
- Create: `integrations/zotero/native/remote-helper-toolchain.json`
- Create: `integrations/zotero/native/scripts/build-linux-static.sh`
- Create: `integrations/zotero/native/scripts/package-linux-static.mjs`
- Create: `integrations/zotero/native/scripts/stage-remote-artifacts.mjs`
- Create: `integrations/zotero/src/remote-helper-bootstrap.ts`
- Create: `integrations/zotero/test/remote-helper-bootstrap.test.ts`
- Create: `integrations/zotero/test/remote-helper-package.test.ts`
- Create: `.github/workflows/zotero-remote-helper.yml`
- Modify: `integrations/zotero/native/Makefile`
- Modify: `integrations/zotero/package.json`
- Modify: `integrations/zotero/scripts/build.mjs`
- Modify: `integrations/zotero/.gitignore`

**Interfaces:**
- Source tuple declaration contains only `{ tuple, zigTarget, minimumKernel, executableName }`; it contains no placeholder digests.
- A separate checked-in toolchain declaration pins Zig 0.14.1 official URLs and exact SHA-256 values: Linux x86_64 `24aeeec8af16c381934a6cd7d95c807a8cb2cf7df9fa40d359aa884195c4716c` and Linux aarch64 `f7a654acc967864f7a050ddacfaa778c7504a0eca8d2b678839c21eea47c992b`. CI downloads only the matching `ziglang.org/download/0.14.1/` archive and verifies the checksum before extraction/use.
- Build-generated `RemoteHelperArtifactManifest` contains `{ schemaVersion:1, helperVersion, protocolVersion:1, provenance:{ zigVersion:"0.14.1"; zigArchiveSha256; sourceCommit; sourceTreeSha256 }, artifacts:[{ tuple, minimumKernel, archivePath, archiveSha256, executablePath, executableSha256 }] }` and is the XPI trust root at `native/remote-helpers/manifest.json`.
- Adds explicit scripts: `native:remote:build` compiles; `native:remote:package` reproducibly archives and generates the digest/provenance manifest; `native:remote:stage -- --x86 "$QLAB_X86_ARTIFACT_DIR" --arm64 "$QLAB_ARM64_ARTIFACT_DIR"` verifies tuple metadata/digests and assembles the two CI artifacts into the exact XPI staging tree. `npm run build` never silently invents or downloads missing remote artifacts.
- Produces `RemoteHelperBootstrap.probe(master)`, `ensure(master, probe, artifact): Promise<InstalledHelper>`, and `rollback(master, failedVersion)`. Probe normalizes only Linux/x86_64/aarch64 and compares numeric kernel major/minor. `InstalledHelper.absoluteVersionedPath` is accepted only from the fixed installer after manifest tuple/version plus archive/executable digests revalidate; the activation lease and master keep this immutable binding for their lifetime.

- [ ] **Step 1: Write failing source/generated-manifest and bootstrap transaction tests**

```ts
it("keeps source tuple declarations separate from generated digests", async () => {
  expect(sourceTuples).toEqual([
    { tuple: "linux-x86_64-static", zigTarget: "x86_64-linux-musl", minimumKernel: "5.4", executableName: "qlab-remote" },
    { tuple: "linux-aarch64-static", zigTarget: "aarch64-linux-musl", minimumKernel: "5.4", executableName: "qlab-remote" },
  ]);
  expect(JSON.stringify(sourceTuples)).not.toMatch(/sha256/i);
  expect(toolchain.hosts["x86_64-linux"].sha256).toBe("24aeeec8af16c381934a6cd7d95c807a8cb2cf7df9fa40d359aa884195c4716c");
  expect(toolchain.hosts["aarch64-linux"].sha256).toBe("f7a654acc967864f7a050ddacfaa778c7504a0eca8d2b678839c21eea47c992b");
  expect(generated.artifacts.every((x) => /^[a-f0-9]{64}$/.test(x.archiveSha256) && /^[a-f0-9]{64}$/.test(x.executableSha256))).toBe(true);
  expect(generated.provenance).toMatchObject({ zigVersion: "0.14.1", sourceCommit: expect.stringMatching(/^[a-f0-9]{40}$/) });
});

it("verifies archive and executable before atomic publish and retains the previous version", async () => {
  remote.corruptExtractedExecutable = true;
  await expect(bootstrap.ensure(master, linuxX64Probe(), artifact)).rejects.toThrow("executable digest mismatch");
  expect(remote.activeSymlink()).toBe("1.0.0");
  expect(remote.wasTempExecutable()).toBe(false);
});

it("keeps every channel bound to the verified version when current changes concurrently", async () => {
  const installed = await bootstrap.ensure(master, linuxX64Probe(), artifactV2);
  remote.repointCurrent("9.9.9/unverified");
  await master.openBrowse();
  await master.openAgent();
  expect(remote.executedHelperPaths()).toEqual([
    installed.absoluteVersionedPath, installed.absoluteVersionedPath,
  ]);
});
```

- [ ] **Step 2: Run focused tests and verify they fail because tuple/build/bootstrap files are new**

Run: `cd integrations/zotero && npx vitest run test/remote-helper-bootstrap.test.ts test/remote-helper-package.test.ts`

Expected: FAIL with unresolved bootstrap module and absent tuple declaration.

- [ ] **Step 3: Implement pinned static-musl builds and atomic remote publication**

```sh
zig build-exe -target x86_64-linux-musl -O ReleaseSafe -lc -static \
  -femit-bin="$out_x86/qlab-remote" native/src/qlab_remote_helper.c
zig build-exe -target aarch64-linux-musl -O ReleaseSafe -lc -static \
  -femit-bin="$out_arm/qlab-remote" native/src/qlab_remote_helper.c
```

Verify the pinned Zig archive before invoking it. `native:remote:package` normalizes tar ownership, mode, path order, and timestamp (`SOURCE_DATE_EPOCH`), computes the source-tree digest from the exact helper sources/headers/build declarations, then computes archive and executable SHA-256 into its generated manifest. Bootstrap streams only the selected archive over the authenticated master into `~/.qlab/bin/.staging/<version>-<random>/archive`; a fixed POSIX installer verifies archive digest, extracts, verifies executable digest, chmods `0700`, runs `self-test`, fsyncs, renames to `~/.qlab/bin/<version>/<tuple>`, and atomically updates `current`. It returns the canonical absolute path of that exact regular executable; the client validates its version/tuple suffix and digest-backed install response, brands it as `VerifiedRemoteHelperPath`, and binds it inside the master. All later fixed commands use that stored versioned path even if another client repoints `current`; callers never pass a path. On failure delete staging only and retain the prior version/link. Never upload repository content.

- [ ] **Step 4: Run package/bootstrap tests and both native tuple self-tests**

Run: `cd integrations/zotero && npm run native:remote:build && npm run native:remote:package && npx vitest run test/remote-helper-bootstrap.test.ts test/remote-helper-package.test.ts && make -C native remote-test`

Expected: PASS; `file native/dist/remote/*/qlab-remote` reports statically linked musl executables and generated manifest digests match bytes.

- [ ] **Step 5: Add current-kernel CI, protected release-only Linux 5.4 validation, and explicit macOS staging**

Create `.github/workflows/zotero-remote-helper.yml` with required build/current execution jobs on `ubuntu-24.04` and `ubuntu-24.04-arm`. Each verifies the official Zig checksum, packages one tuple, uploads archive+tuple manifest+provenance, downloads it on the matching architecture, checks `uname -m`, runs `qlab-remote self-test`, and runs the real Python helper suite.

Linux 5.4 is release validation, not an ordinary PR gate. A `workflow_dispatch` input `releaseValidation=true` selects protected environment `remote-helper-release`; a GitHub-hosted preflight requires repository variables `QLAB_LINUX_5_4_X64_ONLINE=true` and `QLAB_LINUX_5_4_ARM64_ONLINE=true` and fails immediately with an availability diagnostic otherwise. Only then schedule protected runners `[self-hosted, linux, x64, kernel-5.4, qlab-release]` and `[self-hosted, linux, arm64, kernel-5.4, qlab-release]`; each asserts kernel `5.4.*`, runner architecture, artifact/provenance digests, self-test, and Python suite. Candidate artifact promotion is conditioned on both protected jobs. Do not make unavailable self-hosted runners hang normal PRs, and do not add/modify a non-existent release workflow.

The final `macos-15` assembly job downloads the two current-kernel job artifacts to `$RUNNER_TEMP/remote-x86` and `$RUNNER_TEMP/remote-arm64`, exports those as `QLAB_X86_ARTIFACT_DIR`/`QLAB_ARM64_ARTIFACT_DIR`, invokes `npm run native:remote:stage -- --x86 "$QLAB_X86_ARTIFACT_DIR" --arm64 "$QLAB_ARM64_ARTIFACT_DIR"`, then verifies the combined manifest before `npm ci`, `npm run check`, `npm test`, `npm run native:test`, and `npm run build`. It checks `zip` through the Local Target plan's PATH-resolved archive seam and asserts both tuple archives/executables plus generated manifest/provenance are inside the XPI. No mac job rebuilds Linux helpers or trusts a workspace-carried digest.

Run: `cd integrations/zotero && npm run check && npm test`

Expected: PASS locally; workflow syntax validates and macOS remains the sole XPI assembly platform.

- [ ] **Step 6: Commit remote helper supply chain**

```bash
git add integrations/zotero/native/remote-helper-tuples.json integrations/zotero/native/remote-helper-toolchain.json integrations/zotero/native/scripts/build-linux-static.sh integrations/zotero/native/scripts/package-linux-static.mjs integrations/zotero/native/scripts/stage-remote-artifacts.mjs integrations/zotero/src/remote-helper-bootstrap.ts integrations/zotero/test/remote-helper-bootstrap.test.ts integrations/zotero/test/remote-helper-package.test.ts integrations/zotero/native/Makefile integrations/zotero/package.json integrations/zotero/scripts/build.mjs integrations/zotero/.gitignore .github/workflows/zotero-remote-helper.yml
git commit -m "feat(zotero): package verified remote helpers"
```

### Task 5: Resolve SSH repository identity without a target-ID cycle

**Files:**
- Create: `integrations/zotero/src/ssh-repository-target-resolver.ts`
- Create: `integrations/zotero/test/ssh-repository-target-resolver.test.ts`
- Modify: `integrations/zotero/src/repository-target.ts`
- Modify: `integrations/zotero/src/repository-target-controller.ts`
- Modify: `integrations/zotero/test/repository-target-controller.test.ts`
- Modify: `integrations/zotero/src/ssh-target-transport.ts`
- Modify: `integrations/zotero/test/ssh-target-transport.test.ts`

**Interfaces:**
- Produces `deriveSshEndpointId(acceptedHostKeyFingerprint, hostInstanceId, digest)`, using exact UTF-8 bytes `ssh + "\0" + acceptedHostKeyFingerprint + "\0" + hostInstanceId`; then reuses Slice-1 `deriveRepositoryId(endpointId, repositoryUuid, digest)` and `deriveTargetId(endpointId, canonicalRoot, repositoryId, digest)`. Alias/hostname text is deliberately absent; both the key authenticated by OpenSSH and the helper-private host instance are required.
- Produces `SshRepositoryTargetResolver.begin(profile, signal): Promise<SshResolutionSession>` and `restore(stored, signal)`. A session has a random pre-resolution `activationId`, `home()`, `listDirectories(path)`, `probeCodex()`, fixed `authenticateCodex()` available only after an `unauthenticated` probe, `resolveRoot(candidateRoot)`, and idempotent `close()`. `authenticateCodex()` owns the fixed raw/no-echo device-auth PTY, and after exit 0 reruns `codex.probe`; only `ready` permits `resolveRoot`. `missing` and `incompatible` are terminal setup diagnostics and never open device auth. `resolveRoot` returns `{ target:ResolvedSshRepositoryTarget; lease:SshActivationLease }`; target data is immutable and contains no process/channel object. The lease owns the private master and exact installed-helper binding until Task 6 atomically adopts it, otherwise `close()` disposes it. `restore` runs the identical noninteractive sequence with stored accepted fingerprint, host UUID, repository UUID, endpoint/repository/target IDs, canonical root, and profile alias as expectations, and requires `codex.probe=ready`. Any mismatch/state failure closes the lease and rejects with a distinct choose-again/host-key-rotation/helper/Codex diagnostic; it never rewrites or publishes a replacement identity.
- Extends the landed controller/runtime without duplicating it: `switchToResolved(target, { activationLease? })` passes the optional lease only to `TargetSwitchRuntime.stage(snapshot, signal, activationLease)`. The controller closes a still-unadopted lease on supersede/prepublication failure. Task 6 is the sole adopter and follows the typed barrier/revalidation sequence below; local calls continue with no lease.
- Adds only fixed bootstrap operations to `SshMaster`: `probeRemotePlatform()` and `installVerifiedHelper(input)`. Their exact commands/data flow belong to Task 4; they expose neither executable nor argv input. The generic `open(mode,args)` seam remains forbidden.

```ts
export interface SshActivationLease {
  readonly targetId:string;
  readonly masterGeneration:number;
  revalidate(expected:ResolvedSshRepositoryTarget, signal:AbortSignal):Promise<void>;
  adopt(expectedTargetId:string):AdoptedSshResources;
  close():Promise<void>;
}
export interface AdoptedSshResources {
  readonly master:SshMaster;
  readonly helper:InstalledHelper;
  readonly targetId:string;
  close():Promise<void>;
}
```

`revalidate` is the only final browse/confirm-race closure: it repeats the fixed repository handshake, rechecks accepted fingerprint/host/raw UUID/canonical root/derived IDs, requires a fresh fixed Codex probe to be `ready`, and is abort-aware. `adopt` is synchronous, one-shot, and succeeds only after a successful revalidation for the same expected target; on mismatch/double use it closes/rejects. It transfers the already-bound master/helper graph and leaves no second owner.

The resolver's sequence is normative and tested by call order:

1. Generate `activationId`; resolve the literal alias through `ssh -G`.
2. Establish the private master, using the explicit unknown-host-key PTY only after user confirmation; capture its actual `acceptedHostKeyFingerprint`.
3. Call fixed platform probe; select a supported tuple; install/verify helper atomically.
4. Open the fixed, versioned-helper browse channel; exchange activation hello; capture `hostInstanceId`, home, helper/protocol versions, and browse capability.
5. Call fixed `codex.probe`. Stop distinctly on `missing`/`incompatible`; for `unauthenticated`, only an explicit user action may run fixed device auth, after which probe must return `ready`.
6. Canonicalize the chosen absolute directory through the closed browse RPC; open the fixed repository-handshake channel with `candidateRoot` in its activation hello.
7. Require the second channel's host UUID/version to equal browse, require ready Research Loop Git shape, and receive canonical root plus raw Git-private `repositoryUuid`.
8. Derive `endpointId` from accepted fingerprint plus host UUID, then `repositoryId`, and finally `targetId` locally; no earlier frame contains a fabricated target ID.
9. Return the immutable target plus activation lease. Immediately before adoption, Task 6 awaits `lease.revalidate(...)`; no implicit asynchronous final check exists outside that method.

- [ ] **Step 1: Write order, derivation, mismatch, and lease-ownership tests**

```ts
it("derives target identity only after both activation channels agree", async () => {
  const session = await resolver.begin(profile("qlab-gpu"), signal);
  const resolved = await session.resolveRoot("/srv/loop");
  expect(runtime.calls).toEqual([
    "ssh-G", "master", "master.accepted-fingerprint", "probe", "install", "browse.hello", "codex.probe", "browse.canonicalize",
    "repository.hello", "derive.endpoint", "derive.repository", "derive.target",
  ]);
  expect(resolved.target).toMatchObject({
    kind:"ssh", endpointId:expectHex64(), repositoryId:expectHex64(), targetId:expectHex64(),
  });
  expect(runtime.hellosBeforeDerive().every((hello) => !("targetId" in hello))).toBe(true);
});

it("binds endpoint identity to both the accepted host key and helper host UUID", async () => {
  const keyA = fp("SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");
  const keyB = fp("SHA256:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB");
  const hostA = uuid("11111111-1111-4111-8111-111111111111");
  const hostB = uuid("22222222-2222-4222-8222-222222222222");
  const endpoint = await deriveSshEndpointId(keyA, hostA, digest);
  expect(digest.bytes()).toEqual(utf8([
    "ssh", "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "11111111-1111-4111-8111-111111111111",
  ].join("\0")));
  expect(await deriveSshEndpointId(keyB, hostA, freshDigest())).not.toBe(endpoint);
  expect(await deriveSshEndpointId(keyA, hostB, freshDigest())).not.toBe(endpoint);
});
```

Also test all four Codex probe states: only `unauthenticated` enables/opens device auth, successful auth must re-probe to `ready`, and missing/incompatible/failed-auth never stage Agent. Test host mismatch between browse/repository, repository UUID change on `lease.revalidate`, invalid/non-Git/empty/partial root, unsupported tuple/kernel, helper mismatch, abort at every ordered step, double close, revalidate-after-close, and one-shot lease adoption. Test that two aliases reaching the same accepted key+host UUID produce the same endpoint, while host-key rotation with the same host UUID produces a different endpoint only after explicit interactive confirmation. `restore` given the old fingerprint or any non-ready Codex state must reject, close its master/lease, retain stored expectations, and publish nothing. Assert a superseded controller attempt closes the unadopted lease and keeps the prior snapshot/preferences.

- [ ] **Step 2: Run focused tests and verify the real red state**

Run: `cd integrations/zotero && npx vitest run test/ssh-repository-target-resolver.test.ts test/repository-target-controller.test.ts test/ssh-target-transport.test.ts`

Expected: FAIL because no SSH resolver/activation lease exists; all existing local controller transaction tests remain green.

- [ ] **Step 3: Implement the ordered resolver and one-shot lease adoption**

All identity bytes pass through injected `TargetDigest`; tests assert exact NUL delimiters, including fingerprint-before-host ordering. Repository candidates are never persisted. The controller keeps the lease controller-owned while Task 6 waits for its Codex transition barrier; the runtime then awaits `revalidate`, rechecks attempt/abort state, synchronously adopts, and immediately registers `AdoptedSshResources` in its staged cleanup graph before constructing or initializing Agent.

- [ ] **Step 4: Run resolver/controller/transport tests green**

Run: `cd integrations/zotero && npx vitest run test/ssh-repository-target-resolver.test.ts test/repository-target-controller.test.ts test/ssh-target-transport.test.ts && npm run check`

Expected: PASS for exact order, no target-ID cycle, final identity recheck, supersession, lease cleanup, and all local target behavior.

- [ ] **Step 5: Scan for premature/fabricated remote IDs**

Run: `cd integrations/zotero && ! rg -n 'targetId.*activation|activation.*targetId|targetId:.*pending|open\(mode|open\(.*args' src/ssh-repository-target-resolver.ts src/ssh-target-transport.ts test/ssh-repository-target-resolver.test.ts`

Expected: no fabricated activation target ID or generic channel opener.

- [ ] **Step 6: Commit SSH target resolution**

```bash
git add integrations/zotero/src/ssh-repository-target-resolver.ts integrations/zotero/src/repository-target.ts integrations/zotero/src/repository-target-controller.ts integrations/zotero/src/ssh-target-transport.ts integrations/zotero/test/ssh-repository-target-resolver.test.ts integrations/zotero/test/repository-target-controller.test.ts integrations/zotero/test/ssh-target-transport.test.ts
git commit -m "feat(zotero): resolve identity-backed SSH targets"
```

### Task 6: Move local and SSH app-server launch behind staged `AgentConnection`

**Files:**
- Create: `integrations/zotero/src/agent-connection.ts`
- Create: `integrations/zotero/src/ssh-session-socket.ts`
- Create: `integrations/zotero/test/agent-connection.test.ts`
- Create: `integrations/zotero/test/ssh-session-socket.test.ts`
- Create: `integrations/zotero/src/ssh-target-reconnect.ts`
- Create: `integrations/zotero/test/ssh-target-reconnect.test.ts`
- Modify: `integrations/zotero/src/codex-service.ts`
- Modify: `integrations/zotero/src/stored-conversation-resume.ts`
- Modify: `integrations/zotero/src/native-session-socket.ts`
- Modify: `integrations/zotero/test/codex-service.test.ts`
- Modify: `integrations/zotero/test/stored-conversation-resume.test.ts`
- Modify: `integrations/zotero/src/repository-target-controller.ts`
- Modify: `integrations/zotero/test/repository-target-controller.test.ts`
- Modify: `integrations/zotero/src/plugin.ts`
- Modify: `integrations/zotero/test/plugin-state.test.ts`

**Interfaces:**
- Produces strict `AgentConnection.connect(target: RepositoryTargetSnapshot, signal: AbortSignal): Promise<AgentClient>` and idempotent `close(): Promise<void>`; a connection instance is bound to one snapshot and cannot reconnect to a different target. Abort is checked before every spawn/channel/hello/initialize boundary and closes any partially constructed client/channel before rejecting.
- `LocalAgentConnection` owns `findExecutable("codex")`, `NativeBridge.start/spawnPipe`, `NativeSessionSocket`, and `CodexAppServerClient` construction.
- `SshAgentConnection` receives already-adopted Task-5 resources, opens their fixed versioned-helper agent channel, performs the bound hello/`StreamReady`, constructs `SshSessionSocket`/`CodexAppServerClient`, and returns the existing `AgentClient` interface. It never receives or adopts an activation lease. Both connection types own their launch/transport and close it.
- `AgentConnectionFactory.forTarget(snapshot, adopted?)` is consumed by the existing `TargetSwitchRuntime`, not by an ad-hoc `CodexService.start()` branch. Runtime `stage` first requests and awaits a cancel-aware Codex transition barrier; it must not revalidate/adopt the lease, call the factory, construct B, open a B channel, or spawn B before that barrier is held. The only SSH sequence is `await barrier.ready → await lease.revalidate(target, signal) → attempt/abort recheck → lease.adopt(targetId) → immediately register adopted cleanup → factory.forTarget(snapshot, adopted) → register connection cleanup → await connect(snapshot, signal)`. Any throw closes exactly the resources already registered. The approved controller sequence remains exactly `stage → persist → synchronous publish → disposeOld`: `publish` swaps snapshot/client and releases the barrier; precommit `disposeStaged` aborts/releases it and closes B; only post-publish `disposeOld` closes A. Do not add `prepareForPublish`/`rollbackPrepared` hooks.
- Fix Pack B's `paperTransition` queue and `resumeStoredThread()` semantics remain authoritative. Add a narrow cancel-aware `CodexTargetTransitionBarrier`: acquisition is enqueued on the same transition tail and signals ready only after all earlier resume/read/save/pin operations settle, while keeping later conversation operations queued. If the activation aborts before reaching the head, its queue node passes through without becoming held; if it aborts after acquisition, `abort()` releases it exactly once. Controller publish or staged disposal releases it. Never add a second queue or call `threadResume` outside it.
- Session/default/history/open/pin records are partitioned by target/repository identity. A queued history/thread action captures the active target identity; if it reaches the queue after a target publish, it rejects as stale before calling the new `AgentClient`. Operational resume failures (disconnect, timeout, auth, read, save) preserve the stored record; only the exact existing missing-thread classification may replace it. A canonical ID returned by `threadRead` is committed before the transition barrier can publish another target.
- `CodexService` owns conversations, Fix Pack B transition state (`switchingThreadId`, creating thread, global history), workspace objects, target roots, and dynamic tools, but no executable lookup, NativeBridge spawn, SSH channel, or app-server transport construction.
- Produces one `SshTargetReconnectCoordinator`, owned once by plugin startup but never allowed to publish directly. The published master-loss listener captures `(targetId, targetEpoch, masterGeneration)`, synchronously marks that exact snapshot disconnected, and asks the coordinator to reconnect. It coalesces all channel/master notifications for one generation, calls `resolver.restore(active.target, signal)` in BatchMode with every stored identity expectation, requires the same target/endpoint/repository IDs and a strictly newer master generation, then invokes the existing controller's `reconnectCurrent(expectedSnapshot, activationLease)`. That controller path increments `targetEpoch` and runs the same barrier-first `stage → persist → synchronous publish → disposeOld` transaction. A target switch aborts reconnect; staged-target loss never starts reconnect; mismatch/failure closes the new lease and leaves the target disconnected with explicit retry/choose-again UI. No reconnect falls back locally or prompts for/accepts a host key.

- [ ] **Step 1: Write failing ownership, isolation, and cross-channel tests**

```ts
it("connects an SSH target to an AgentClient without CodexService spawning a process", async () => {
  const staging = targetRuntime.stage(sshSnapshot("T", "/srv/loop", 4), signal, activationLease);
  expect(factory.forTarget).not.toHaveBeenCalled();
  transitionBarrier.becomeHeld();
  await staging;
  expect(factory.ssh.connect).toHaveBeenCalledWith(sshSnapshot("T", "/srv/loop", 4), signal);
  expect(nativeBridge.spawnPipe).not.toHaveBeenCalled();
  expect(targetRuntime.stageOrder()).toEqual([
    "barrier.ready", "lease.revalidate", "attempt.recheck", "lease.adopt",
    "cleanup.register-adopted", "factory", "cleanup.register-connection", "connect",
  ]);
});

it("rejects agent and repository channels with different identities", async () => {
  repositoryHello({ canonicalRoot:"/srv/loop", hostInstanceId:"host-A", repositoryUuid:"raw-A", repositoryId:"repo-A" });
  agentHello({ canonicalRoot:"/srv/other", hostInstanceId:"host-A", repositoryUuid:"raw-A", repositoryId:"repo-A" });
  await expect(ssh.connect(snapshot, signal)).rejects.toThrow("repository identity mismatch");
  expect(codexWasStarted()).toBe(false);
});

it("never sends local paths in a remote turn", async () => {
  await remoteService.send("Draft this", "gpt-5.6-sol", "high");
  const wire = JSON.stringify(client.turnStart.mock.calls[0]![0]);
  expect(wire).toContain("/srv/loop/drafts");
  expect(wire).not.toMatch(/\/Users\/|\/profile\/|current-pdf|attachment-cache/);
});

it("waits for a Fix Pack B resume commit before publishing another target", async () => {
  const opening = service.openConversationForPaper("paper-A");
  await resumeEntered.promise;
  const switching = controller.switchToResolved(targetB, { activationLease: leaseB });
  expect(runtime.publish).not.toHaveBeenCalled();
  resumeRead.resolve({ thread: { id: "canonical-A" } });
  await opening;
  expect(savedA()).toMatchObject({ threadId: "canonical-A", targetId: "A" });
  await switching;
  expect(runtime.publish).toHaveBeenCalledWith(expect.objectContaining({ target: { targetId: "B" } }), expect.anything());
});

it("rejects an old-target history action queued behind a staged target barrier", async () => {
  const switching = controller.switchToResolved(targetB, { activationLease: leaseB });
  await stagedBarrierHeld.promise;
  const staleOpen = service.switchThread("thread-from-A");
  persistB.resolve();
  await switching;
  await expect(staleOpen).rejects.toThrow("conversation belongs to another repository target");
  expect(clientB.threadResume).not.toHaveBeenCalled();
});

it("reconnects one published target on a newer master generation and fences the old one", async () => {
  publish(sshSnapshot("T", "/srv/loop", 4), masterGeneration(7));
  master7.lose("connection reset");
  master7.emitLate(agentFrame({ targetEpoch: 4 }));
  await reconnect.settled();
  expect(resolver.restore).toHaveBeenCalledOnce();
  expect(controller.reconnectCurrent).toHaveBeenCalledWith(
    expect.objectContaining({ targetEpoch: 4 }), expect.objectContaining({ generation: 8 }),
  );
  expect(activeSnapshot()).toMatchObject({ target: { targetId: "T" }, targetEpoch: 5 });
  expect(renderOldFrame).not.toHaveBeenCalled();
});
```

Add transaction tests for: supersede while barrier acquisition is queued (factory never called, unadopted lease closes); abort during asynchronous `lease.revalidate` (no adopt/factory); supersede immediately after adoption but before factory (registered adopted graph closes); throw during factory construction; supersede while SSH `connect()` is pending (signal aborts and registered partial B closes); staged master loss; `stage` success followed by preference-persist failure; master loss immediately after synchronous publish; and old-connection close failure in `disposeOld`. Assert prepublication cases keep A/client A/session state, call `disposeStaged` once (release barrier then close B), never close A, and never publish; post-publication cases keep B published, mark B degraded/disconnected, fence callbacks, close A only through `disposeOld`, and never resurrect A. Assert success order exactly `barrier.ready, lease.revalidate, attempt.recheck, lease.adopt, cleanup.register-adopted, factory, cleanup.register-connection, connect.resolve, stage.resolve, persist.resolve, publish.sync, barrier.release, disposeOld`.

Reconnect tests separately cover duplicate loss notifications, loss of a staged/noncurrent master, explicit switch racing reconnect, reconnect abort while its barrier is queued, same target with generation `N+1` and epoch increment, non-increasing generation rejection, accepted-fingerprint/host/repository mismatch, failure then explicit retry, loss of the newly published generation, and late bytes/exits from every old channel. Assert one restore/transaction per published generation, no host-key PTY, no local connection, exact identity expectations, and zero old-generation UI/session writes.

- [ ] **Step 2: Run focused tests and verify they fail on launch ownership**

Run: `cd integrations/zotero && npx vitest run test/agent-connection.test.ts test/ssh-session-socket.test.ts test/ssh-target-reconnect.test.ts test/codex-service.test.ts test/repository-target-controller.test.ts test/plugin-state.test.ts`

Expected: FAIL because `AgentConnection`/transition barrier do not exist, `CodexService.startCodexInternal()` still launches local Codex, and Fix Pack B conversation records are not target-partitioned. Existing resume/queue tests must continue to compile and expose behavioral reds, not missing imports.

- [ ] **Step 3: Implement connection-owned launch and bounded JSONL socket adaptation**

```ts
export interface AgentConnection {
  connect(target: RepositoryTargetSnapshot, signal: AbortSignal): Promise<AgentClient>;
  close(): Promise<void>;
}
export interface AgentConnectionFactory {
  forTarget(target: RepositoryTargetSnapshot, adopted?: AdoptedSshResources): AgentConnection;
}
export interface CodexTargetTransitionBarrier {
  readonly previous: RepositoryTargetSnapshot | null;
  readonly ready: Promise<void>;
  publish(next: RepositoryTargetSnapshot, client: AgentClient): void;
  abort(): void;
}
```

Factor line framing from `NativeSessionSocket` into one bounded decoder; retain one newline per send, split UTF-8 correctness, 8 MiB cap, early EOF/nonzero-exit mapping, and per-channel close. `SshAgentConnection` sends the captured snapshot's canonical root and expected raw/derived identity in `BoundClientHello`; after the helper returns root/host/raw UUID, it recomputes endpoint/repository/target identity with the master-authenticated fingerprint and rejects mismatch before exposing stream bytes. It then validates `StreamReady` and performs app-server initialize/initialized and platform/protocol compatibility before returning. Both local and SSH implementations wire the supplied signal before their first side effect and detach it in `close()`.

Implement stage by placing and awaiting the cancel-aware barrier on `paperTransition` before constructing B: earlier work completes; later work remains behind its release promise while B connects. Execute the sole sequence above exactly. `lease.revalidate` happens before adoption; after the attempt/signal recheck, adoption is synchronous and the adopted graph is registered before factory construction, while the connection is registered before awaiting `connect`. `SshAgentConnection` cannot adopt. Return `{ connectionB, clientB, barrier, adoptedGraph }`. Runtime `publish` synchronously swaps snapshot/client, clears old target's active/switching/global-history UI state, installs new target-scoped state, calls `barrier.publish`, and returns before any queued conversation transition resumes. Runtime `disposeStaged` aborts the signal, calls `barrier.abort`, then closes registered partial/full B in reverse ownership order; if the barrier was never held its canceled node simply drains. Disconnect/master loss during an in-flight resume is an operational failure and preserves Fix Pack B's session snapshot. Remote writable roots remain only remote `drafts/literature/work`; no local attachment/profile path crosses.

Wire the reconnect coordinator to the published graph's master-loss callback after publication and unregister it before graph disposal. The coordinator holds no target state of its own: every callback rechecks `controller.activeSnapshot()` plus published master generation, and only `RepositoryTargetController` may publish the replacement epoch. Reconnect is a normal staged B-for-A replacement even though `targetId` is unchanged, so all prior persistence, synchronous publication, degradation, disposal, and barrier rules remain in force.

- [ ] **Step 4: Run connection and Codex tests green**

Run: `cd integrations/zotero && npx vitest run test/agent-connection.test.ts test/ssh-session-socket.test.ts test/ssh-target-reconnect.test.ts test/native-session-socket.test.ts test/codex-app-server.test.ts test/codex-service.test.ts test/repository-target-controller.test.ts test/plugin-state.test.ts`

Expected: PASS, including local behavior, remote platform compatibility, malformed JSONL, path isolation, cross-channel identity, barrier-before-construction, signal cancellation, transition supersede, staged/published master loss, same-target newer-generation reconnect, delayed resume, canonical resume ID, missing-thread replacement, operational resume rollback, queued pin preservation, and stale queued history rejection.

- [ ] **Step 5: Search CodexService for transport/process ownership and run the full gate**

Run: `cd integrations/zotero && ! rg -n "findExecutable\(\"codex\"|spawnPipe\(|NativeSessionSocket|SshSessionSocket" src/codex-service.ts && npm run check && npm test`

Expected: `rg` returns no matches; TypeScript gate passes.

- [ ] **Step 6: Commit `AgentConnection` ownership**

```bash
git add integrations/zotero/src/agent-connection.ts integrations/zotero/src/ssh-session-socket.ts integrations/zotero/src/ssh-target-reconnect.ts integrations/zotero/src/codex-service.ts integrations/zotero/src/stored-conversation-resume.ts integrations/zotero/src/native-session-socket.ts integrations/zotero/src/repository-target-controller.ts integrations/zotero/src/plugin.ts integrations/zotero/test/agent-connection.test.ts integrations/zotero/test/ssh-session-socket.test.ts integrations/zotero/test/ssh-target-reconnect.test.ts integrations/zotero/test/codex-service.test.ts integrations/zotero/test/stored-conversation-resume.test.ts integrations/zotero/test/repository-target-controller.test.ts integrations/zotero/test/plugin-state.test.ts
git commit -m "feat(zotero): connect agents through repository targets"
```

### Task 7: Close the profile picker, setup, and Workbench target UI

**Files:**
- Create: `integrations/zotero/src/repository-target-picker.ts`
- Create: `integrations/zotero/test/repository-target-picker.test.ts`
- Create: `integrations/zotero/src/remote-directory-browser.ts`
- Create: `integrations/zotero/test/remote-directory-browser.test.ts`
- Modify: `integrations/zotero/src/plugin.ts`
- Modify: `integrations/zotero/src/sidebar.ts`
- Modify: `integrations/zotero/test/plugin-state.test.ts`
- Modify: `integrations/zotero/test/sidebar.test.ts`
- Modify: `integrations/zotero/test/agent-connection.test.ts`

**Interfaces:**
- Produces `CanonicalRemoteDirectory` brand, `RemoteDirectoryEntry = Readonly<{ name:string; path:CanonicalRemoteDirectory; kind:"directory" }>` and `RemoteDirectoryBrowser.home/list/resolveCandidate/close`.
- Produces `RepositoryTargetPickerState = closed | profiles | connecting | browsing | authenticating | confirming | error`, with alias list, current canonical directory, selected candidate, progress, and diagnostic. Produces diagnostic union `{ phase:"ssh"|"helper"|"codex"|"auth"|"repository"|"ready"|"error"; message:string; remediation:"accept-host-key"|"install-helper"|"install-codex"|"upgrade-codex"|"authenticate-codex"|"choose-repository"|null }` so the four Codex probe states cannot collapse into one auth error.
- Adapts Fix Pack B's sidebar API atomically. Replace `SidebarState.qlabRoot` with `repositoryTarget?: { kind:"local"|"ssh"; label:string; canonicalRoot:string; targetId:string; capabilities:RepositoryTargetCapabilities }` and `SidebarCallbacks.onChooseQLabRoot` with `onChooseRepositoryTarget`. Update every Workbench/standalone/reader host in the same commit; preserve `SidebarViewOptions.surface`, lazy `attachWorkspace`, `setWorkspaceOpen`, ensure-open float behavior, history callbacks, `switchingThreadId`, and Main Site callbacks. The compact reader sidebar still does not acquire a Main Site/profile-picker surface.
- One plugin-level selection coordinator owns one picker attempt/AbortController. Workbench actions call Tasks 2/5/6; the old target remains published while host-key/device-auth PTYs, browsing, identity resolution, Agent initialization, and stage-held transition-barrier acquisition run. The picker closes only after controller publication or explicit cancel.

- [ ] **Step 1: Write failing browse/setup/UI tests**

```ts
it("starts at remote login home and returns directories only", async () => {
  expect(await browser.home()).toBe("/home/alice" as CanonicalRemoteDirectory);
  expect(await browser.list("/home/alice" as CanonicalRemoteDirectory)).toEqual([
    { name: "research", path: "/home/alice/research", kind: "directory" },
  ]);
});

it("keeps old target active while device auth PTY runs and closes it on cancel", async () => {
  const pending = plugin.authenticateRemoteCodex("qlab-gpu");
  expect(plugin.activeTarget()?.target.targetId).toBe("local-A");
  setup.cancel();
  await expect(pending).rejects.toThrow("Codex authentication canceled");
  expect(setup.close).toHaveBeenCalledOnce();
  expect(plugin.activeTarget()?.target.targetId).toBe("local-A");
});
```

Add DOM tests for this complete picker flow: open from Workbench; show `Local…` plus deduplicated literal aliases; select `qlab-gpu`; accept/cancel unknown key; show helper install progress; run the closed Codex probe; for `unauthenticated` show only the fixed raw/no-echo device-auth PTY and require the post-auth probe to become `ready`; then start at login home, browse directories only, accept manual canonical absolute input, reject incompatible/empty/partial roots, confirm `SSH qlab-gpu · /srv/research-loop`, and publish once. Separate `missing`, `incompatible`, `unauthenticated`, and `ready` DOM cases prove distinct diagnostics/remediation and that missing/incompatible never open device auth or stage Agent. Cancel at every state closes session/master and retains A. Add startup tests for the exact sequence `settings.load → decode → (when rewrite === "v1-to-v2") settings.save(v2) → resolver.restore(stored SSH expectations, including codex.probe=ready) → controller.switchToResolved(restored.target, lease) → runtime barrier/revalidate/adopt/stage → controller publish`. Assert no resolver/stage starts before the migration save settles. The stored resolved SSH object is never passed directly to the controller or rendered active. Fingerprint, host UUID, repository UUID, canonical root, endpoint/repository/target ID, final revalidation, or Codex-ready mismatch closes every restoration channel/master/lease, performs no publication or identity rewrite, and leaves no active target with a specific diagnostic. Assert the selector state is shared across Workbench/standalone renders without breaking Fix Pack B history/resume indicators. Slice-2 disabled actions remain focusable with explanatory `aria-describedby` and never invoke callbacks.

- [ ] **Step 2: Run focused tests and verify they fail on new browser/UI paths**

Run: `cd integrations/zotero && npx vitest run test/repository-target-picker.test.ts test/remote-directory-browser.test.ts test/plugin-state.test.ts test/sidebar.test.ts test/agent-connection.test.ts`

Expected: FAIL because the baseline exposes only `qlabRoot/onChooseQLabRoot`, and picker/browse/setup/SSH capability rendering do not exist. Existing Fix Pack B History/resume/sidebar tests remain green.

- [ ] **Step 3: Implement bootstrap browsing and explicit setup lifecycle**

```ts
export interface RemoteDirectoryBrowser {
  home(): Promise<CanonicalRemoteDirectory>;
  list(path: CanonicalRemoteDirectory): Promise<readonly RemoteDirectoryEntry[]>;
  resolveCandidate(input: string): Promise<CanonicalRemoteDirectory>;
  close(): Promise<void>;
}
```

Browse mode accepts directories only and canonicalizes explicit absolute input; it has no repository mutation methods. Unknown host key opens only Task 2's fixed `accept-host-key` PTY, then reconnects with BatchMode. Before repository confirmation, call only Task 3's closed `codex.probe`: `missing` offers installation guidance, `incompatible` offers upgrade guidance, `unauthenticated` alone enables fixed `openSetupAuth`, and `ready` proceeds. After device-auth exit 0, rerun the fixed probe and proceed only if it is now `ready`; do not infer success from process exit and do not wait for Agent stage to classify auth. Cancel/exit/error closes setup/browser channels and staged master. Task 6 calls `lease.revalidate` immediately before adoption to repeat accepted fingerprint/host/repository/derived identity and Codex-ready checks.

Plugin startup first loads and strictly decodes preferences. If decode requests `v1-to-v2`, await the exact v2 save before any resolver/controller call. A local active value follows Slice 1's local restore. An SSH active value is passed only as expectations to `resolver.restore(stored, startupSignal)`; restore is noninteractive, requires the fixed Codex probe to be `ready`, and returns a fresh target/lease. Pass only those to `controller.switchToResolved`; Task 6 performs the final `lease.revalidate` under its barrier. Restore failure never calls the controller, never trusts or rewrites the stored resolved object, and closes the lease. Published master loss thereafter is handled only by Task 6's coalesced reconnect owner, not by rerunning startup or the picker.

When the picker confirms, call `controller.switchToResolved(resolved.target, { activationLease:resolved.lease })`; do not assign plugin/sidebar active state. The controller's one publish callback updates `this.activeTarget`, Codex gate, target view model, and all surfaces once. Main Site/QMD/Terminal callbacks check the immutable Slice-2 capabilities before touching their existing local services.

- [ ] **Step 4: Run browser/UI integration tests green**

Run: `cd integrations/zotero && npx vitest run test/repository-target-picker.test.ts test/remote-directory-browser.test.ts test/plugin-state.test.ts test/sidebar.test.ts test/agent-connection.test.ts test/codex-service.test.ts`

Expected: PASS; SSH, helper, Codex compatibility, auth, and repository failures retain distinct messages and leave the old target complete.

- [ ] **Step 5: Run Slice-2 gates on their supported platforms**

Run on Linux after Slice-1 Task 0: `cd integrations/zotero && command -v zip && npm run check && npm test && npm run native:test && npm run native:remote:build && npm run native:remote:package && make -C native remote-test`

Expected: PASS; do not run signed universal/XPI `npm run build` on Linux.

Run on macOS with both CI artifacts downloaded to fixed job paths: `cd integrations/zotero && command -v zip && npm run native:remote:stage -- --x86 "$RUNNER_TEMP/remote-x86" --arm64 "$RUNNER_TEMP/remote-arm64" && npm run native:test && npm run build`

Expected: PASS and XPI contains both static tuples plus generated digest manifest.

Run before either platform gate:

```bash
cd integrations/zotero
! rg -n '\b(TODO|TBD|FIXME|placeholder)\b|as any|Record<string, unknown>' src/repository-target-picker.ts src/ssh-repository-target-resolver.ts src/agent-connection.ts src/remote-helper-protocol.ts
! rg -n 'open\(mode|open\(.*args|activeTarget\(\)\.targetId|onChooseQLabRoot' src test
```

Expected: no placeholder/untyped protocol surface, generic SSH opener, wrong snapshot access, or obsolete root-only sidebar callback remains.

- [ ] **Step 6: Commit Remote Chat Workbench integration**

```bash
git add integrations/zotero/src/repository-target-picker.ts integrations/zotero/src/remote-directory-browser.ts integrations/zotero/src/plugin.ts integrations/zotero/src/sidebar.ts integrations/zotero/test/repository-target-picker.test.ts integrations/zotero/test/remote-directory-browser.test.ts integrations/zotero/test/plugin-state.test.ts integrations/zotero/test/sidebar.test.ts integrations/zotero/test/agent-connection.test.ts integrations/zotero/test/codex-service.test.ts
git commit -m "feat(zotero): add remote Chat target workflow"
```

## Spec Coverage Review

- Task 1 extends, rather than recreates, the landed local target/controller model and fixes Slice-2 capabilities/persistence.
- Task 2 covers literal profile discovery, Include expansion, `ssh -G`, authenticated host-key fingerprint capture, private master generation/loss fanout, unknown-host-key setup PTY, and fixed device-auth PTY ownership.
- Task 3 defines every helper handshake/request/response/event identity field, creates host/repository UUIDs race-safely under their private directories, and rejects path/symlink/cross-channel mismatch.
- Task 4 separates tuple/toolchain declarations from generated digest provenance, defines explicit package/stage commands, verifies archive/executable, publishes atomically, runs current-kernel CI, and reserves real Linux 5.4 for availability-checked protected release validation.
- Task 5 resolves alias/authenticated-key/platform/helper/home/root/host/repository in a fixed activation order, derives endpoint identity from fingerprint+host only after both exist, and hands off a one-shot lease.
- Task 6 acquires Fix Pack B's transition barrier before constructing/connecting B, propagates abort, makes `AgentConnection.connect(target, signal) -> AgentClient` a staged resource, and owns one same-target/new-generation reconnect path.
- Task 7 closes the profile picker, explicit decode/migrate/restore/stage startup, home-rooted browsing, setup diagnostics, Fix Pack B sidebar API migration, and visible Slice-2 capability gates.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-31-qlab-remote-chat.md`. Execute with Subagent-Driven development (recommended) or Inline Execution using `superpowers:executing-plans`.
