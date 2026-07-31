# QLab Remote Terminal, Preview, and Main Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run interactive terminals, closed repository processes, QMD previews, and the Main Site on the selected SSH repository host, exposing HTTP only through target-owned loopback forwards and releasing every process on cancellation, disconnect, or target change.

**Architecture:** This is Slice 4 and consumes the landed target runtime, SSH master, helper envelope, `QLabRepository`, and repository identity from Slices 1-3. A single typed long-process protocol carries PTY/process lifecycle events. Terminals adapt it to xterm; previews and Main Site use helper-owned remote loopback leases plus exact OpenSSH forwards; local adapters preserve existing NativeBridge behavior. No caller can send a shell string or argv over the protocol.

**Tech Stack:** TypeScript 7, Vitest 4, Zotero 9/Gecko, xterm, OpenSSH, C17 PTY/process/TCP APIs, Quarto, npm/Vinext, Python `unittest`.

## Global Constraints

- Complete the Local Target, Remote Chat, and Remote Draft Repository plans first. Reuse `RepositoryTargetSnapshot`, `TargetSwitchRuntime`, `RepositoryTargetCapabilities`, `SshMaster`, common helper envelopes, `QLabRepository`, target epoch, host instance ID, and repository ID. Do not create a second target controller, SSH master, repository channel, or identity type.
- The remote process surface is closed. Accepted kinds are exactly `terminal`, `git-diff`, `knowledge-check`, `draft-check`, `knowledge-preview`, `draft-preview`, and `main-site`; accepted controls are exactly start, terminal input, terminal resize, and cancel. There is no arbitrary `run`, argv, environment, cwd, executable, or shell-script field.
- A terminal is an explicit user action and starts at the canonical remote repository root. Preview and Main Site servers bind remote loopback only. Zotero loads only a dynamically forwarded local `127.0.0.1` URL; it never loads a remote hostname/address.
- The outer preview commands are exactly the repository's supported npm CLIs. Do **not** add `--no-execute` to `npm run knowledge:preview` or `npm run draft:preview`; those CLIs reject/own their arguments. Security tests must inspect the actual inner Quarto argv in `.research-loop/tooling/scripts`, where `--no-execute` is mandatory.
- Every process request/event includes the common protocol/helper/target/epoch/host/repository context and a bounded session ID. Sequence numbers are contiguous per output stream. A stale or mismatched frame is a protocol error and cannot update xterm, preview URL, progress, or UI state.
- Cancel is idempotent: stop accepting input, send SIGTERM to the process group, wait a bounded grace period, send SIGKILL if needed, reap, close PTY/TCP leases, emit one exit, and release the channel. Target disposal never waits forever on an unreachable remote helper.
- SSH External Editor, remote initialization of empty/partial repositories, and remote Draft-to-Knowledge promotion remain disabled in Slice 4. Their handlers never fall through to local adapters.
- Slice-1 Task 0's PATH-resolved archive and portable PTY changes are prerequisites. Linux gates run TypeScript, `npm run native:test`, and the static remote helper, but never signed universal/XPI assembly. Final native/XPI gates run on macOS only after `native:remote:stage` verifies both Slice-2 artifacts; never reintroduce `/usr/bin/zip` as application logic.
- Preserve the controller transaction exactly: `stage → persist → synchronous publish → disposeOld`. Slice-4 staging may validate a fixed process channel/capability set and register B-owned factories, but starts no terminal, preview, Main Site process, port lease, or forward and never stops A. Prepublication cleanup is `disposeStaged(B)` only; A's live graph is touched only by post-publication `disposeOld(A)`. Do not add `prepareForPublish` or `rollbackPrepared` hooks.

---

### Task 1: Define the long-process protocol and drive a real remote PTY

**Files:**
- Create: `integrations/zotero/src/remote-process-protocol.ts`
- Create: `integrations/zotero/src/target-process-connection.ts`
- Create: `integrations/zotero/src/ssh-terminal-connection.ts`
- Create: `integrations/zotero/test/remote-process-protocol.test.ts`
- Create: `integrations/zotero/test/ssh-terminal-connection.test.ts`
- Modify: `integrations/zotero/src/remote-helper-protocol.ts`
- Modify: `integrations/zotero/test/remote-helper-protocol.test.ts`
- Modify: `integrations/zotero/src/ssh-target-transport.ts`
- Modify: `integrations/zotero/test/ssh-target-transport.test.ts`
- Modify: `integrations/zotero/src/terminal-panel.ts`
- Modify: `integrations/zotero/test/terminal-panel.test.ts`
- Modify: `integrations/zotero/native/include/qlab_remote_protocol.h`
- Modify: `integrations/zotero/native/src/qlab_remote_helper.c`
- Modify: `integrations/zotero/native/tests/test_remote_helper.py`
- Modify: `integrations/zotero/native/Makefile`

**Interfaces:**
- Produces a validated `ProcessSessionId` of 1-64 ASCII alphanumerics/`._:-`, unique for the entire lifetime of one helper channel. Closed IDs remain tombstoned and cannot be reused until a new channel/generation exists.
- Extends the bound helper mode union with exactly `"process"` and adds fixed `SshMaster.openProcess(snapshot): Promise<SshChannel>`. It launches only `/usr/bin/ssh -T -S <control> -o BatchMode=yes -- <literal-alias> "$HOME/.qlab/bin/current/qlab-remote" process`, then sends the snapshot's canonical root and expected host/raw repository UUID/opaque repository ID in the bound hello. The helper performs Remote Chat's no-follow root/UUID validation and returns root/raw UUID; the client recomputes fingerprint-bound endpoint/repository/target identity before accepting the channel. It accepts no mode, command, argv, cwd, environment, or caller-provided remote text; generic `open(mode,args)` remains forbidden.
- Extends the common request union with these exact controls:

```ts
export type ProcessStartParams =
  | Readonly<{ sessionId:ProcessSessionId; kind:"terminal"; rows:number; cols:number; program:"login-shell"|"codex" }>
  | Readonly<{ sessionId:ProcessSessionId; kind:"git-diff"; path:KnowledgeQmdPath|DraftQmdPath|WorkingCopyQmdPath }>
  | Readonly<{ sessionId:ProcessSessionId; kind:"knowledge-check" }>
  | Readonly<{ sessionId:ProcessSessionId; kind:"draft-check"; path:DraftQmdPath|WorkingCopyQmdPath }>
  | Readonly<{ sessionId:ProcessSessionId; kind:"knowledge-preview"; path:KnowledgeQmdPath }>
  | Readonly<{ sessionId:ProcessSessionId; kind:"draft-preview"; path:DraftQmdPath|WorkingCopyQmdPath|PreviewQmdPath }>
  | Readonly<{ sessionId:ProcessSessionId; kind:"main-site" }>;

export type ProcessRequest =
  | (HelperRequest & { method:"process.start"; params:ProcessStartParams })
  | (HelperRequest & { method:"process.input"; params:{ sessionId:ProcessSessionId; processGeneration:number; dataBase64:string } })
  | (HelperRequest & { method:"process.resize"; params:{ sessionId:ProcessSessionId; processGeneration:number; rows:number; cols:number } })
  | (HelperRequest & { method:"process.cancel"; params:{ sessionId:ProcessSessionId; processGeneration:number|null; reason:"user"|"target-switch"|"disconnect"|"shutdown" } });

export type ProcessErrorCode =
  | "INVALID_REQUEST" | "IDENTITY_MISMATCH" | "SESSION_EXISTS" | "SESSION_NOT_FOUND"
  | "SESSION_CLOSED" | "INVALID_CONTROL" | "OUTPUT_BACKPRESSURE" | "SPAWN_FAILED"
  | "MISSING_NPM" | "MISSING_QUARTO" | "INSTALL_FAILED" | "BUILD_FAILED"
  | "READINESS_FAILED" | "CANCEL_FAILED" | "INTERNAL";
export type ProcessEvent =
  | (HelperEvent & { event:"process.started"; params:{ sessionId:ProcessSessionId; processGeneration:number } })
  | (HelperEvent & { event:"process.output"; params:{ sessionId:ProcessSessionId; processGeneration:number; seq:number; stream:"pty"|"stdout"|"stderr"; dataBase64:string } })
  | (HelperEvent & { event:"process.ready"; params:{ sessionId:ProcessSessionId; processGeneration:number; remotePort:number } })
  | (HelperEvent & { event:"process.error"; params:{ sessionId:ProcessSessionId; processGeneration:number; code:ProcessErrorCode; message:string } })
  | (HelperEvent & { event:"process.exit"; params:{ sessionId:ProcessSessionId; processGeneration:number; exitCode:number|null; signal:number|null } });

export type ProcessSessionIdentity = Readonly<BoundFrameContext & {
  helperInstanceId:string; channelGeneration:number;
  sessionId:ProcessSessionId; processGeneration:number;
}>;
```

- Produces `TargetProcessConnection.start(snapshot, params): Promise<TargetProcessSession>`. A started session exposes its complete `ProcessSessionIdentity`, ordered events, `input`/`resize` only for terminal kind, idempotent `cancel(reason)`, and `closed`. Before `process.started`, its pending cancel sends `processGeneration:null`; the helper accepts that only for the still-pending, never-reusable session ID. Once started, every control and event must exactly match `(helperInstanceId, channelGeneration, targetId, targetEpoch, hostInstanceId, repositoryId, sessionId, processGeneration)`. Calling terminal-only controls on another kind fails locally without a wire frame.
- `ProcessRequest`/`ProcessEvent` are the closed refinements of the common helper envelope: every frame retains the complete `BoundFrameContext` (`protocolVersion`, `helperVersion`, target ID/epoch, host instance ID, repository ID, negotiated capabilities), bounded request/event ID, and session ID. The connection also captures the bound hello's `helperInstanceId`; a new helper instance or channel generation invalidates every old session. Strict codecs reject extra fields and never expose the common envelope's `unknown` payload members to callers.
- The helper chooses the canonical root as cwd. `login-shell` resolves the current account's absolute passwd shell and executes `[shell, "-l"]`; `codex` executes fixed `['codex']`. No client cwd/PATH/env/argv crosses the wire. PTY resize uses `TIOCSWINSZ` and SIGWINCH; output is base64 so arbitrary terminal bytes do not corrupt JSONL.

- [ ] **Step 1: Write exhaustive codec and actual PTY red tests**

The TypeScript test round-trips every start kind, all three controls, and all five events; rejects duplicate session IDs, invalid base64, zero/oversized dimensions, output sequence gaps, input/resize on non-terminal sessions, wrong identity, and event-after-exit. Transport tests assert the exact fixed `openProcess` argv, bound snapshot hello, rejection after master loss, and absence of any generic opener. The Python test starts the actual helper terminal, waits for `process.started`, sends `printf 'PTY_SENTINEL\\n'; stty size; exit 7` through `process.input`, resizes to 41x113, and asserts decoded PTY output contains sentinel and `41 113`, followed by exactly one exit code 7.

Also reject a reused tombstoned ID and inject late output/ready/error/exit/cancel from process generation N while a different session or generation N+1 is active on the same target; none may reach or stop the newer process. Half-close the helper input and simulate channel HUP with terminal, preview, and Main Site sessions live; native tests must observe bounded TERM/KILL, every process group reaped, every PTY/listener/proxy lease closed, and exactly-once session finalization.

- [ ] **Step 2: Run focused tests and verify the concrete red state**

Run: `cd integrations/zotero && npx vitest run test/remote-process-protocol.test.ts test/ssh-target-transport.test.ts test/ssh-terminal-connection.test.ts test/terminal-panel.test.ts && make -C native remote-test`

Expected: the process codec/SSH terminal adapter are absent and the real helper rejects `process.start`; existing local TerminalPanel behavior remains green.

- [ ] **Step 3: Implement the dispatcher, PTY lifecycle, and connection adapter**

The C helper validates the full start request before `forkpty`, reserves a never-reusable channel-local session ID and monotonic process generation, creates a process group, sends one `started`, emits contiguous base64 `output`, applies only generation-matched input/resize/cancel, and reaps into exactly one `exit`. On cancel, close input first, TERM the group, wait 2 seconds, KILL if still live, reap, and reject later controls with `SESSION_CLOSED`. On JSONL input EOF, parse failure, channel HUP, or peer disconnect, it runs that same bounded cancel/reap path for every session owned by the channel, closes all PTYs/listeners/proxy leases, and finalizes each session exactly once even if it can no longer deliver the exit frame. Bound queued input/output to 128 KiB/8 MiB respectively and surface backpressure/errors rather than dropping bytes silently.

Adapt `TerminalPanel` to a `TerminalConnection` backed by local NativeBridge or `TargetProcessConnection`. Preserve xterm, multi-session, idle cleanup, math preview, and local Reader behavior. For SSH, omit local PDF/profile/library paths and label the header `SSH <profile> · <canonicalRoot>`.

- [ ] **Step 4: Run protocol, native PTY, and terminal UI tests green**

Run: `cd integrations/zotero && npx vitest run test/remote-process-protocol.test.ts test/ssh-target-transport.test.ts test/ssh-terminal-connection.test.ts test/terminal-panel.test.ts && make -C native remote-test`

Expected: PASS for real PTY input, resize, exit, TERM/KILL cancellation, fragmented output, sequence errors, complete session-identity rejection, helper EOF/HUP cleanup, and local TerminalPanel regressions.

- [ ] **Step 5: Run the full TypeScript gate**

Run: `cd integrations/zotero && npm run check && npm test`

Expected: PASS.

- [ ] **Step 6: Commit long-process and terminal support**

```bash
git add integrations/zotero/src/remote-helper-protocol.ts integrations/zotero/src/remote-process-protocol.ts integrations/zotero/src/target-process-connection.ts integrations/zotero/src/ssh-target-transport.ts integrations/zotero/src/ssh-terminal-connection.ts integrations/zotero/src/terminal-panel.ts integrations/zotero/test/remote-helper-protocol.test.ts integrations/zotero/test/remote-process-protocol.test.ts integrations/zotero/test/ssh-target-transport.test.ts integrations/zotero/test/ssh-terminal-connection.test.ts integrations/zotero/test/terminal-panel.test.ts integrations/zotero/native/include/qlab_remote_protocol.h integrations/zotero/native/src/qlab_remote_helper.c integrations/zotero/native/tests/test_remote_helper.py integrations/zotero/native/Makefile
git commit -m "feat(zotero): run target-owned remote PTYs"
```

### Task 2: Map closed process kinds to fixed argv and prove inner Quarto safety

**Files:**
- Create: `integrations/zotero/src/closed-repository-process.ts`
- Create: `integrations/zotero/test/closed-repository-process.test.ts`
- Create: `integrations/zotero/src/ssh-qmd-render-runtime.ts`
- Create: `integrations/zotero/test/ssh-qmd-render-runtime.test.ts`
- Modify: `integrations/zotero/src/qmd-render.ts`
- Modify: `integrations/zotero/test/qmd-render.test.ts`
- Modify: `integrations/zotero/src/qlab-commands.ts`
- Modify: `integrations/zotero/test/qlab-commands.test.ts`
- Modify: `integrations/zotero/native/src/qlab_remote_helper.c`
- Modify: `integrations/zotero/native/tests/test_remote_helper.py`
- Modify: `.research-loop/tests/knowledge/quarto-build.integration.test.ts`
- Modify: `.research-loop/tests/drafts/preview.test.ts`

**Interfaces:**
- Produces one transport-neutral `ClosedRepositoryProcess` adapter over Task 1 sessions. It exposes start/result/cancel for `git-diff`, both checks, and both previews; callers pass only a branded path where the kind permits it.
- The helper builds these argv arrays itself, always with cwd equal to canonical root and no shell:

| Kind | Fixed argv |
|---|---|
| `git-diff` | `git -C <canonicalRoot> --no-pager diff --no-color -- <validatedPath>` |
| `knowledge-check` | `npm run knowledge:check` |
| `draft-check` | `npm run draft:check -- --file <validatedPath> --json` |
| `knowledge-preview` | `npm run knowledge:preview -- --port <helperInternalPort> --watch-source <validatedPath>` |
| `draft-preview` | `npm run draft:preview -- --file <validatedPath> --port <helperInternalPort>` |

The two outer preview argv arrays deliberately contain no `--no-execute`. The repository scripts remain the security authority: `previewKnowledgeSite` must spawn Quarto as `['preview','.', '--no-browser','--no-execute', '--host','127.0.0.1','--port',port]`; `previewDraft` must spawn `['preview',relativeWithinDrafts,'--no-browser','--no-execute','--host','127.0.0.1','--port',port]`, always `shell:false`.

- [ ] **Step 1: Add exact outer/inner argv red tests**

In native tests, intercept `execvp` and assert each complete argv above, including that neither outer npm preview has `--no-execute`. Reject unknown kind, a request containing `argv`, shell metacharacters in paths, cross-tree paths, and extra params before fork. In the two repository-level tests, intercept the actual Quarto runner and assert `--no-execute` exactly once, loopback host/selected port, array argv, and `shell:false`.

Run from repository root:

```bash
node --import tsx --test .research-loop/tests/knowledge/quarto-build.integration.test.ts .research-loop/tests/drafts/preview.test.ts
```

Expected before any helper changes: existing inner-script assertions pass; the new port/path variants identify any missing exact assertion. The remote native argv tests remain red because those process kinds are unimplemented.

- [ ] **Step 2: Add SSH render tests against Task-1 process events**

Test validation failure, output/error propagation, nonzero check exit, cancel before `started`, cancel after `started`, preview `ready`, old epoch output, and exit-before-ready. Assert `QmdRenderService` receives no remote shell string and does not start NativeBridge for SSH.

Run: `cd integrations/zotero && npx vitest run test/closed-repository-process.test.ts test/ssh-qmd-render-runtime.test.ts test/qmd-render.test.ts test/qlab-commands.test.ts && make -C native remote-test`

Expected: FAIL because the closed adapter/runtime and native mappings do not exist.

- [ ] **Step 3: Implement fixed C argv builders and SSH render adapter**

Use distinct typed C parameter structs and builder functions per kind; do not concatenate a command line. Preserve current `QmdRenderService` caching, diagnostics, and generation behavior above the new local/SSH runtime seam. Visible validation/diff actions choose a kind from code and capture the active snapshot; they never interpolate a remote command.

- [ ] **Step 4: Run both repository script tests and Zotero/native tests green**

Run:

```bash
node --import tsx --test .research-loop/tests/knowledge/quarto-build.integration.test.ts .research-loop/tests/drafts/preview.test.ts
cd integrations/zotero
npx vitest run test/closed-repository-process.test.ts test/ssh-qmd-render-runtime.test.ts test/qmd-render.test.ts test/qlab-commands.test.ts
make -C native remote-test
```

Expected: PASS; outer npm argv omit `--no-execute`, actual inner Quarto argv include it exactly once, and no invalid request reaches fork/exec.

- [ ] **Step 5: Prove no freeform process seam exists**

Run:

```bash
cd integrations/zotero
! rg -n 'argv:|shell:|runCommand|commandLine' src/remote-process-protocol.ts src/closed-repository-process.ts src/ssh-qmd-render-runtime.ts
! rg -n 'params.*(argv|shell|command)|json_.*(argv|shell|command)|system\(|popen\(' native/src/qlab_remote_helper.c
```

Expected: no client/protocol freeform argv or shell field and no native parser/dispatcher route from request parameters to an executable/shell seam. The fixed helper-owned login-shell resolution from Task 1 is unaffected.

- [ ] **Step 6: Commit closed repository processes**

```bash
git add integrations/zotero/src/closed-repository-process.ts integrations/zotero/src/ssh-qmd-render-runtime.ts integrations/zotero/src/qmd-render.ts integrations/zotero/src/qlab-commands.ts integrations/zotero/test/closed-repository-process.test.ts integrations/zotero/test/ssh-qmd-render-runtime.test.ts integrations/zotero/test/qmd-render.test.ts integrations/zotero/test/qlab-commands.test.ts integrations/zotero/native/src/qlab_remote_helper.c integrations/zotero/native/tests/test_remote_helper.py .research-loop/tests/knowledge/quarto-build.integration.test.ts .research-loop/tests/drafts/preview.test.ts
git commit -m "feat(zotero): run closed repository processes remotely"
```

### Task 3: Allocate race-safe remote leases and exact SSH loopback forwards

**Files:**
- Create: `integrations/zotero/src/ssh-loopback-forward.ts`
- Create: `integrations/zotero/test/ssh-loopback-forward.test.ts`
- Create: `integrations/zotero/src/ssh-preview-connection.ts`
- Create: `integrations/zotero/test/ssh-preview-connection.test.ts`
- Modify: `integrations/zotero/src/ssh-target-transport.ts`
- Modify: `integrations/zotero/src/qmd-render.ts`
- Modify: `integrations/zotero/src/qmd-workspace.ts`
- Modify: `integrations/zotero/native/src/qlab_remote_helper.c`
- Modify: `integrations/zotero/native/tests/test_remote_helper.py`

**Interfaces:**
- Produces `RemoteLoopbackReady = { identity:ProcessSessionIdentity; remotePort:number }` only after the helper owns the returned port and the child endpoint is healthy. The helper binds a loopback TCP lease to port 0 and keeps that listener open for the session as a small TCP proxy; it starts the Quarto child on a separate internal candidate, retries internal `EADDRINUSE`, health-checks the expected path, and only then emits a generation-bound `process.ready` with the still-bound proxy port. It never returns an unbound guessed port.
- Produces `SshLoopbackForward.start(identity, master, remotePort): Promise<SshForward>` and `SshForward = { identity:ProcessSessionIdentity; localPort:number; remotePort:number; url:string; close():Promise<void> }`. Forward creation, readiness, publication, and close require an exact identity match, not merely the same target ID/epoch.
- Each forward spawns this exact argv array:

```text
/usr/bin/ssh -N -T -o BatchMode=yes -o ExitOnForwardFailure=yes
  -S <private-control-path>
  -L 127.0.0.1:<localPort>:127.0.0.1:<remotePort>
  -- <literal-profile-alias>
```

The adapter chooses a local loopback candidate by binding port 0, releases immediately before spawn, and treats an OpenSSH forward-bind error/exit 255 as a collision: allocate a new candidate and retry at most five times. A local URL is not published until OpenSSH stays alive and an HTTP readiness probe through the forward succeeds.

- [ ] **Step 1: Write exact argv, collision, and remote lease tests**

Native tests prove the returned remote port is already bound throughout ready state, two simultaneous previews get distinct leases, internal child collision retries without publishing, child exit closes the lease, and cancel closes proxy/child. TypeScript tests assert the exact SSH argv/order above, `BatchMode=yes`, `ExitOnForwardFailure=yes`, private master path, literal alias, five-collision limit, and that no profile/root value is concatenated into an option. Run two previews for one target/epoch and inject one session's late generation-N ready/exit/cancel after the other is published; exact `ProcessSessionIdentity` matching must prevent cross-publication and cross-cleanup.

- [ ] **Step 2: Add full preview failure/cleanup tests and run red**

Cover remote error before ready, remote exit before ready, forward spawn failure, local bind collision, HTTP health timeout, user cancel during each phase, normal stop, target supersede, process-channel EOF/HUP, master loss followed by Remote Chat's whole-target reconnect, and window shutdown. At each point assert remote process/lease and local forward are closed once, URL is never published early, old-generation identity callbacks are ignored, helper-side EOF cleanup reaps the remote child/lease, and the replacement target does not silently restart or republish the old preview.

Run: `cd integrations/zotero && npx vitest run test/ssh-loopback-forward.test.ts test/ssh-preview-connection.test.ts test/qmd-render.test.ts test/qmd-workspace.test.ts && make -C native remote-test`

Expected: FAIL because the loopback lease/forward and preview connection do not exist.

- [ ] **Step 3: Implement forward readiness and preview ownership**

Start the remote preview first; upon an exact-identity `process.ready`, start an identity-owned forward; probe only the local forwarded URL and expected preview path, then recheck the same identity before publication. `stop()` cancels that exact remote session/lease before closing only its matching forward. If master is already lost, rely on the helper's channel-EOF cleanup for remote reaping, mark the cancellation acknowledgement unreachable, close/reap the exact local forward, and finish disposal without hanging. Every close method is idempotent; a mismatched late callback is ignored and can never close another session's forward.

- [ ] **Step 4: Run preview/forward/native tests green**

Run: `cd integrations/zotero && npx vitest run test/ssh-loopback-forward.test.ts test/ssh-preview-connection.test.ts test/qmd-render.test.ts test/qmd-workspace.test.ts && make -C native remote-test`

Expected: PASS for exact argv, remote port ownership, collision retries, all failures, and all cleanup phases.

- [ ] **Step 5: Refactor local/SSH preview construction behind one interface**

Run: `cd integrations/zotero && npm run check && npm test`

Expected: PASS; local previews preserve existing behavior and SSH never calls local NativeBridge.

- [ ] **Step 6: Commit loopback-only remote previews**

```bash
git add integrations/zotero/src/ssh-loopback-forward.ts integrations/zotero/src/ssh-preview-connection.ts integrations/zotero/src/ssh-target-transport.ts integrations/zotero/src/qmd-render.ts integrations/zotero/src/qmd-workspace.ts integrations/zotero/test/ssh-loopback-forward.test.ts integrations/zotero/test/ssh-preview-connection.test.ts integrations/zotero/test/qmd-render.test.ts integrations/zotero/test/qmd-workspace.test.ts integrations/zotero/native/src/qlab_remote_helper.c integrations/zotero/native/tests/test_remote_helper.py
git commit -m "feat(zotero): forward remote previews over loopback"
```

### Task 4: Start a fixed, on-demand Main Site process and forward it locally

**Files:**
- Create: `integrations/zotero/src/main-site-connection.ts`
- Create: `integrations/zotero/src/ssh-main-site-connection.ts`
- Create: `integrations/zotero/test/ssh-main-site-connection.test.ts`
- Modify: `integrations/zotero/src/research-loop-site.ts`
- Modify: `integrations/zotero/test/research-loop-site.test.ts`
- Modify: `integrations/zotero/src/plugin.ts`
- Modify: `integrations/zotero/src/sidebar.ts`
- Modify: `integrations/zotero/native/src/qlab_remote_helper.c`
- Modify: `integrations/zotero/native/tests/test_remote_helper.py`

**Interfaces:**
- Produces `MainSiteState = stopped | starting | ready | error`, each non-stopped variant carrying the exact `ProcessSessionIdentity`; ready also carries the identity-owned local URL. `MainSiteSession.stop()` is idempotent and can close only the forward bearing that same identity.
- SSH activation performs no dependency probe, install, build, server start, or forward. Only the user's Main Site action sends `process.start { kind:"main-site" }`.
- The helper owns this fixed sequence at canonical root; no caller text participates:

1. Resolve `npm` and `quarto` with the helper's fixed PATH search equivalent of `command -v`; emit typed `MISSING_NPM`/`MISSING_QUARTO` before any install.
2. If `node_modules/.package-lock.json` is absent or its lockfile digest differs from `package-lock.json`, execute `['npm','ci']`, require exit 0, and record the digest.
3. If `dist/server/index.js` is absent or the stored build-input digest differs from the closed input set (`package-lock.json`, `package.json`, `knowledge/**`, `src/**`, `.research-loop/tooling/**` metadata), execute `['npm','run','build']`, require exit 0, and atomically record the digest.
4. Acquire the Task-3 remote loopback proxy/internal port and execute `['npm','run','start','--','--hostname','127.0.0.1','--port',<internalPort>]` with `execvp`, cwd canonical root.
5. Poll the inner loopback endpoint; emit one generation-bound `process.ready { sessionId, processGeneration, remotePort:<ownedProxyPort> }`, or same-generation `process.error` then `process.exit` on probe/child failure.

- [ ] **Step 1: Write exact preflight/condition/argv and event tests**

Native tests cover missing npm, missing Quarto, `npm ci` required/skipped, build required/skipped, ci/build nonzero exits, dynamic distinct ports, ready, server exit after ready, cancel during ci/build/start, TERM escalation, and cleanup. Intercept exec to assert the arrays above and prove target activation alone executes none of them.

- [ ] **Step 2: Write Main Site state/forward red tests**

Test stopped after SSH activation; explicit click yields starting then ready; local URL uses only `http://127.0.0.1:<dynamic>/`; double click coalesces one session; error is retryable; cancel/switch/process-channel EOF/master loss/window shutdown close process lease before its exact-identity forward; an old or same-target/different-session ready/error/exit cannot mutate current state or close its forward.

Run: `cd integrations/zotero && npx vitest run test/ssh-main-site-connection.test.ts test/research-loop-site.test.ts test/plugin-state.test.ts && make -C native remote-test`

Expected: FAIL because Main Site still uses one fixed local service/port and the helper has no fixed main-site sequence.

- [ ] **Step 3: Implement transport-neutral Main Site sessions**

Wrap current local `ResearchLoopSiteService` in `LocalMainSiteConnection`; make the view consume session `localUrl` instead of global `RESEARCH_LOOP_SITE_URL`. `SshMainSiteConnection` composes Task-1 process events with Task-3 forward ownership and parses progress without relying on transport-specific shell output. Remote empty/partial repository state remains unsupported and never calls local initialization.

- [ ] **Step 4: Run Main Site and native tests green**

Run: `cd integrations/zotero && npx vitest run test/ssh-main-site-connection.test.ts test/research-loop-site.test.ts test/plugin-state.test.ts && make -C native remote-test`

Expected: PASS for exact argv/conditions, dynamic port, ready/error/cancel, on-demand start, retry, stale events, and cleanup ordering.

- [ ] **Step 5: Run the full TypeScript gate**

Run: `cd integrations/zotero && npm run check && npm test`

Expected: PASS.

- [ ] **Step 6: Commit remote Main Site sessions**

```bash
git add integrations/zotero/src/main-site-connection.ts integrations/zotero/src/ssh-main-site-connection.ts integrations/zotero/src/research-loop-site.ts integrations/zotero/src/plugin.ts integrations/zotero/src/sidebar.ts integrations/zotero/test/ssh-main-site-connection.test.ts integrations/zotero/test/research-loop-site.test.ts integrations/zotero/test/plugin-state.test.ts integrations/zotero/native/src/qlab_remote_helper.c integrations/zotero/native/tests/test_remote_helper.py
git commit -m "feat(zotero): run Main Site on SSH targets"
```

### Task 5: Publish Slice-4 capabilities and prove whole-target disposal

**Files:**
- Modify: `integrations/zotero/src/repository-target.ts`
- Modify: `integrations/zotero/src/repository-target-controller.ts`
- Modify: `integrations/zotero/test/repository-target.test.ts`
- Modify: `integrations/zotero/test/repository-target-controller.test.ts`
- Create: `integrations/zotero/test/remote-capabilities.test.ts`
- Modify: `integrations/zotero/src/plugin.ts`
- Modify: `integrations/zotero/src/sidebar.ts`
- Modify: `integrations/zotero/test/plugin-state.test.ts`
- Modify: `integrations/zotero/test/sidebar.test.ts`

**Interfaces:**
- Slice-4 SSH capabilities are exactly `{ chat:true, qmdRead:true, qmdWrite:true, terminal:true, preview:true, mainSiteSupported:true, externalEditor:false, promoteDraft:false }`, published only after B's staged fixed process channel advertises the complete process capability set and agrees with the already-bound Agent/repository identity. The process stage performs no dependency check, install, build, child spawn, port allocation, or forward.
- `TargetSwitchRuntime` owns one target resource graph. Stage registers B's process connection/factories and carries forward the held Codex/Note barriers from Slices 2-3 without mutating A. Persist follows. One synchronous publish swaps target/adapters/capabilities/sidebar state and releases the barriers. Only then may `disposeOld(A)` cancel/reap terminal/check/preview/Main Site remote processes and remote port leases; close local SSH forwards; close QLab repository/watch, process, and Agent channels; close the multiplexing master and remove its private runtime directory. `disposeStaged(B)` releases B's barriers and closes only staged B resources. Each node is idempotent and late callbacks check captured identity.
- Produces one `capabilityMessage(key, target)` map used by menu, toolbar, sidebar, and Workbench. Disabled controls remain focusable with `aria-disabled="true"` and explanatory copy; handlers return before obtaining any local adapter.
- Reuse Remote Chat's `SidebarState.repositoryTarget`, `onChooseRepositoryTarget`, lazy `attachWorkspace`, `setWorkspaceOpen`, history/ensure-open behavior, and `mainSiteSupported` key. Do not revive `qlabRoot`, `onChooseQLabRoot`, an eager workspace, or an alternate `mainSite` capability.

- [ ] **Step 1: Write capability publication and unsupported-action red tests**

Assert terminal/preview/Main Site stay disabled if any advertised process capability is absent; all three enable together only in the synchronous publication after a complete staged handshake. Assert activation and stage start zero processes/leases/forwards. SSH External Editor, initialization, and promotion clicks invoke neither remote process nor local adapter. Assert `mainSiteSupported` is used consistently—no alternate `mainSite` capability key exists.

- [ ] **Step 2: Write disposal-order tests at every lifecycle boundary**

Cover switch before process `started`, switch during preview ready, switch after URL publication, master loss, helper error, user cancellation, window shutdown, and controller supersede by a newer activation. Add persistence failure while A has a live terminal/preview/Main Site, successful publication, `disposeStaged(B)`, and an A close timeout/error. Record calls and assert exact `stage.resolve, persist.resolve, publish.sync, disposeOld` transaction order and, inside old disposal, process/lease → forward → repository/process/Agent channel → master order exactly once. A persistence failure leaves A and its UI/live processes untouched; a post-publication A cleanup failure leaves B published and degraded; old output/ready/error/exit callbacks produce no UI writes. For a published master loss, assert Remote Chat's coordinator performs one same-target/new-generation transaction, increments target epoch, and publishes B with terminal/preview/Main Site stopped—none of A's interactive/on-demand processes auto-restart.

Run: `cd integrations/zotero && npx vitest run test/remote-capabilities.test.ts test/repository-target.test.ts test/repository-target-controller.test.ts test/plugin-state.test.ts test/sidebar.test.ts`

Expected: FAIL because Slice-3 capabilities do not enable process features and the complete resource graph/disposal order is not registered.

- [ ] **Step 3: Update capabilities, register resource ownership, and gate handlers**

Extend the existing immutable capability snapshot; do not mutate it after publication. Target stage registers only B's fixed process connection/factories and capability proof. On-demand handlers create sessions/leases/forwards only after the matching snapshot is published, register them in that target's graph before they can emit UI events, and recheck identity before rendering. The existing Main Site `stageTarget(B)` remains side-effect-free and does not close A; its old session is stopped only from `disposeOld(A)`. On master loss, mark the published target disconnected synchronously, fence callbacks by helper generation/target epoch, stop/reap its process graph, and let Remote Chat's sole reconnect coordinator stage a fresh graph. The replacement publication exposes stopped terminal/preview/Main Site state and requires a new explicit user action to spawn anything. Do not introduce a second reconnect owner or prepublish prepare/rollback lifecycle methods.

- [ ] **Step 4: Run focused lifecycle regressions green**

Run: `cd integrations/zotero && npx vitest run test/remote-capabilities.test.ts test/repository-target.test.ts test/repository-target-controller.test.ts test/plugin-state.test.ts test/sidebar.test.ts test/terminal-panel.test.ts test/qmd-render.test.ts test/research-loop-site.test.ts`

Expected: PASS; no unsupported local fallback and no stale callback survives target disposal.

- [ ] **Step 5: Run placeholder/type/security scans and platform-correct final gates**

Run on Linux:

```bash
cd integrations/zotero
! rg -n '\b(TODO|TBD|FIXME|placeholder)\b|as any|Record<string, unknown>' src/remote-process-protocol.ts src/target-process-connection.ts src/ssh-terminal-connection.ts src/closed-repository-process.ts src/ssh-loopback-forward.ts src/ssh-preview-connection.ts src/main-site-connection.ts src/ssh-main-site-connection.ts
! rg -n 'runCommand|commandLine|remoteHostUrl|0\.0\.0\.0' src native/src/qlab_remote_helper.c
! rg -n 'prepareForPublish|rollbackPrepared|onChooseQLabRoot|\bqlabRoot\b' src test
command -v zip
npm run check
npm test
npm run native:test
make -C native remote-test
```

Expected: all scans return no prohibited placeholder/untyped/freeform/public-bind/legacy-lifecycle surface; supported Linux gates pass after Slice-1 Task 0. Do not run signed universal/XPI assembly on Linux.

Run on macOS with both verified static helper artifacts staged:

```bash
cd integrations/zotero
test "$(uname -s)" = Darwin
command -v zip
npm run native:remote:stage -- --x86 "$RUNNER_TEMP/remote-x86" --arm64 "$RUNNER_TEMP/remote-arm64"
npm run native:test
npm run build
```

Expected: PASS; staging verifies both static tuples and provenance before macOS-only signed universal/XPI assembly, and the XPI contains both helpers plus the generated manifest.

- [ ] **Step 6: Commit Slice-4 capability/lifecycle completion**

```bash
git add integrations/zotero/src/repository-target.ts integrations/zotero/src/repository-target-controller.ts integrations/zotero/src/plugin.ts integrations/zotero/src/sidebar.ts integrations/zotero/test/repository-target.test.ts integrations/zotero/test/repository-target-controller.test.ts integrations/zotero/test/remote-capabilities.test.ts integrations/zotero/test/plugin-state.test.ts integrations/zotero/test/sidebar.test.ts
git commit -m "feat(zotero): complete remote process capabilities and disposal"
```

## Spec Coverage Review

- Task 1 defines start/input/resize/cancel and started/output/ready/error/exit with a session ID, then tests real C PTY input, resize, cancellation, and exit.
- Task 2 closes all process mappings and tests the outer npm argv separately from the actual inner Quarto argv that must contain `--no-execute`.
- Task 3 returns only helper-owned remote ports, uses the full BatchMode/ExitOnForwardFailure OpenSSH argv, retries local collisions, and tests every failure/cleanup phase.
- Task 4 specifies fixed Main Site preflight/install/build/start argv, dynamic remote readiness, explicit on-demand lifecycle, errors, and cancellation.
- Task 5 publishes terminal/preview/`mainSiteSupported` only in Slice 4, preserves `stage → persist → synchronous publish → disposeOld`, and proves process → forward → repository/process/Agent → master cleanup with unsupported actions still closed.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-31-qlab-remote-terminal-preview-main-site.md`. Execute only after Slices 1-3, using Subagent-Driven Development (recommended) or `superpowers:executing-plans`.
