# QLab Repository Targets — Design Spec

- **Date:** 2026-07-31
- **Status:** User-approved architecture, pending written-spec review
- **Target:** `integrations/zotero` — QLab Workbench
- **Companion UI spec:**
  [`2026-07-31-qlab-vscode-explorer-design.md`](./2026-07-31-qlab-vscode-explorer-design.md)

Unless prefixed otherwise, file references below are relative to
`integrations/zotero/`.

## Overview

QLab Workbench will treat a repository as a first-class **Repository Target**,
not as an unqualified local path. A target is either a local repository paired
with the local Codex runtime, or an SSH repository paired with a Codex runtime
on the same remote host. Users can switch among targets from the Workbench;
Codex, terminal, Draft state, repository commands, and previews always follow
the selected target as one coherent unit.

The remote experience follows the VS Code Remote-SSH model: Zotero remains the
local UI, while workspace-aware processes and filesystem operations execute on
the machine that owns the repository. The remote repository is authoritative;
the design does not maintain a local clone, use SSHFS as the product contract,
or repeatedly copy files with `scp`.

This spec defines the common architecture and decomposes delivery into four
independent implementation slices. The first slice fixes the current local
repository-switching bug. Later slices add remote support without weakening the
Research Loop trust boundary.

The first SSH release targets headless Linux hosts with OpenSSH, a POSIX
filesystem, and a compatible authenticated Codex CLI. Its bundled native helper
has exactly two supported remote tuples: `linux-x86_64-static` and
`linux-aarch64-static`. Both artifacts are statically linked, carry independent
digests in the XPI manifest, and support Linux kernel 5.4 or newer. Release CI
executes each artifact in its matching x86_64 or aarch64 Linux 5.4 VM as well as
the current supported image. The bootstrap probe normalizes only Linux `x86_64`
and `aarch64`; every other OS, architecture, too-old kernel, or failed helper
self-test returns a typed **Unsupported remote host** result before any
repository is selected.
There is no glibc-versus-musl runtime branch. The target and transport interfaces
do not assume a remote GUI; adding another tuple, macOS, or Windows SSH hosts
requires its own packaged artifact, release test, and filesystem-safety
validation.

## Goals

1. Allow any number of local repository targets, each using local Codex.
2. Allow any number of SSH repository targets, each using Codex on that SSH
   host.
3. Make a target switch atomic from the user's perspective: UI, Codex, terminal,
   Draft workspace, preview, and repository commands must never disagree about
   the active repository.
4. Let remote Codex write `drafts/`, `literature/`, and generated `work/`
   directly in the remote repository, without repository synchronization.
5. Preserve revision checking and reviewed Draft compare/Keep when QMD editing
   crosses the SSH boundary.
6. Keep all remote control channels private to authenticated SSH sessions.

## Non-goals

- Synchronizing a local repository clone with a remote repository.
- Treating SSHFS, rsync, Git pull/push, or `scp` as the editing transport.
- Publishing an internet-accessible Codex app-server or QLab execution API.
- Sending local filesystem paths to a remote Codex process.
- Allowing either local or remote Agent mode to write trusted `knowledge/`
  directly.
- Adding a generic remote write or shell-command RPC.
- Remote Draft-to-Knowledge promotion in the first four slices. It needs a
  separate design for the `review-draft` confirmation, non-`main` branch,
  exact-diff, and `knowledge-check` gates; until then the action is visibly
  unavailable on SSH targets. Existing local promotion remains unchanged.
- Opening an SSH-target file in an arbitrary local external editor. The current
  external-editor adapter accepts local real paths, so **Edit in External
  Editor** is visibly unavailable for SSH targets in all four slices. A future
  editor-specific Remote-SSH URI/CLI integration requires a separate design.
- Initializing an empty SSH directory as a Research Loop repository. The remote
  folder picker may select only an already-valid repository; remote
  initialization is visibly unavailable rather than falling back to local I/O.
- Shipping all remote capabilities in one change set.

## Repository Target model

The unqualified `qlabRoot: string` setting is replaced at the domain boundary
by the following model:

```ts
type LocalRepositoryTarget = {
  kind: "local";
  root: string;
};

type SshRepositoryTarget = {
  kind: "ssh";
  sshProfile: string;
  root: string;
};

type RepositoryTarget = LocalRepositoryTarget | SshRepositoryTarget;

type ResolvedRepositoryTarget = RepositoryTarget & {
  targetId: string;
  repositoryId: string;
  canonicalRoot: string;
};
```

`sshProfile` is the name of a concrete entry in the user's SSH configuration,
not an arbitrary shell command. Secrets, private keys, passwords, and Codex
tokens are never stored in Zotero preferences.

`targetId` identifies an endpoint and path for local persistence. It is derived
from the target kind, an endpoint ID, the canonical root, and a repository
instance ID. `repositoryId` is returned by the local or remote target resolver
after canonicalization. Display strings and raw root text are not identities.

On first validated selection, QLab atomically creates a random 128-bit repository
instance UUID in Git-private state resolved through
`git rev-parse --git-path qlab/repository-id`. The file is mode `0600`, is never
in the working tree or Git index, and is read through the local or remote
adapter. Repository selection fails rather than falling back to path identity if
this private state cannot be read or safely created. `repositoryId` is a SHA-256
digest over the endpoint ID and that UUID; `targetId` additionally includes the
canonical root, so moving the same repository creates a new target while keeping
its repository identity. Deleting and recreating the repository at the same path
creates a new UUID and cannot restore old sessions. Copying the Git-private QLab
state is an explicit identity-preserving operation.

A selectable target is always a valid Research Loop Git repository. To preserve
the existing local empty/partial-directory setup, **Open Local Repository…** has
a pre-target `LocalRepositoryCandidate` workflow: it canonicalizes and
classifies the directory, shows the existing exact initialization preview, and
writes nothing unless the user confirms. Confirmation initializes the candidate
(including Git when absent), creates the Git-private UUID, validates the final
layout, and only then returns a `ResolvedRepositoryTarget` to the switch
controller. Cancel leaves the candidate untouched. Failure leaves the old target
active and reports any candidate-side files that were created before failure;
the half-initialized candidate is never persisted as a target. SSH selection has
no analogous setup path in these slices and accepts only an already-valid remote
repository. Initialization is therefore not an active-target capability and
cannot be used to break the identity precondition.

The Research Loop layout fingerprint is only validation: it checks the required
project metadata and trusted/untrusted tree shape without hashing Draft or
Knowledge contents, so ordinary edits never change identity. The SSH endpoint
ID includes the accepted host-key fingerprint and a QLab host-instance UUID
returned by the helper. A host-key change is a new endpoint until OpenSSH accepts
it and the user explicitly reselects the target.

The existing `qlabRoot` preference migrates once under a versioned preference
schema, but it is classified before any binding:

- a ready Research Loop Git repository creates or reads its private UUID,
  becomes a local target, and receives the current active thread plus threads
  whose recorded cwd canonicalizes inside that root;
- an empty or partial directory becomes a pending `LocalRepositoryCandidate`.
  Workbench shows the exact initialization preview and waits for confirmation;
  until confirmation succeeds, it is neither the active target nor a thread
  owner;
- a missing, inaccessible, or incompatible directory creates no target. Its
  associated threads remain under **Legacy / unassigned** with remediation
  explaining why migration could not bind them.

Imported read-only history remains global; threads with a different or missing
cwd also stay under **Legacy / unassigned** until the user explicitly associates
them. If ready-target UUID creation fails, migration fails closed into the same
unassigned state rather than using path identity. Candidate confirmation resumes
the ordinary pre-target workflow and binds eligible threads only after target
activation. Re-running an interrupted migration is idempotent and never
duplicates a candidate, target, repository UUID, or thread binding.

## User experience

The Workbench repository control shows both execution location and repository:

```text
Local  · /Users/alice/research-loop
SSH qlab-gpu · /srv/qlab/research-loop
```

The selector contains recent configured targets plus two actions:

- **Open Local Repository…** uses the existing local folder picker and local
  repository validation.
- **Connect to SSH Host…** selects a configured SSH profile, establishes the
  remote helper, and opens a remote folder picker backed by the bootstrap
  host-browser RPC.

QLab discovers concrete aliases from the user's OpenSSH configuration and lets
OpenSSH resolve `Include`, `ProxyJump`, agent, key, port, and username settings.
It does not parse a displayed alias into connection arguments itself. The first
remote release requires `ssh <profile>` to succeed with an SSH key or agent.
Steady-state control sessions use `BatchMode=yes` so they fail instead of
silently waiting for a password, key passphrase, or MFA response. For an unknown
host key, the connection setup opens a one-off, explicitly labeled SSH PTY so
the user can inspect and accept the fingerprint through OpenSSH itself. Password
and keyboard-interactive authentication are a later NativeBridge askpass
capability, never text fields stored in QLab preferences.

After SSH authentication, a host setup check reports these states separately:

1. SSH reachable and host key accepted;
2. compatible QLab remote helper installed;
3. compatible `codex` executable available in the remote login shell;
4. remote Codex authenticated;
5. selected repository valid.

For a headless Linux host, **Authenticate Codex…** opens a setup-only remote PTY
and runs the fixed command `codex login --device-auth`; the user completes the
printed device-code flow in any browser. This small `RemoteSetupSession` ships
with the remote Chat slice and is not the general-purpose terminal planned for
Slice 4. API-key login remains a user-controlled Codex CLI option. QLab never
copies the local Codex auth cache, captures an API key, or stores a remote Codex
token.

The folder picker starts in the remote login home and is served by a bootstrap
helper before a repository root exists. It lists directories only, allows a
path to be entered explicitly, and returns a canonical candidate. Selecting a
folder then starts a repository broker locked to that root. This avoids the
bootstrap cycle in which a root-scoped repository RPC would otherwise be
required to choose its own root.

The product must never infer “local versus remote” from path syntax. All target
badges, confirmation messages, terminal labels, and errors use the explicit
target kind and SSH profile.

Conversations are target-scoped. Switching to another target opens or restores
that target's last conversation; it does not retarget an existing conversation
whose history and workspace object belong to another repository. Historical
conversations remain available under their original target.

If a Codex turn is running, target selection offers **Stop response and
switch** or **Cancel**. It never uses `turn/steer` to pretend that a running turn
has changed working directory. If a QMD editor contains unsaved user changes,
the user must save, discard, or cancel before switching.

## Atomic target-switch transaction

`RepositoryTargetController` owns the transition. No UI surface may update the
active target by writing the preference directly. Its state is
`active | preparing | committing | degraded`, and every active state carries a
monotonic `targetEpoch`. Every transition additionally receives a monotonic
`switchAttemptId` before candidate resolution begins.

Only one transition may commit. Selecting C while A -> B is preparing cancels
B's abortable resolve/staging work and starts A -> C under a new attempt ID;
selecting again after commit has begun is queued until that commit finishes.
Every staged callback checks both attempt ID and active target epoch before it
may persist or publish. A canceled or late B result can therefore never win a
race with C.

The transition stages the new target before replacing the old one:

1. Resolve and validate the candidate through its target resolver, without
   mutating active state.
2. Check blockers: running Codex turn, unsaved QMD source, pending Keep, or a
   target operation whose outcome is unknown after disconnection.
3. Stop or finish user-approved old-target activity while commands that could
   create a new blocker are temporarily disabled.
4. Load the candidate's target-scoped conversation, workspace object, Draft
   manifest, Explorer state, and preview metadata into a staging snapshot.
   Establish any connection needed by a currently visible surface. The old
   target and processes remain active and visible during staging.
5. Persist the candidate as the selected target. Persistence failure disposes
   only staged resources and returns to the still-active old target; activity
   explicitly stopped in step 3 remains stopped.
6. Increment `targetEpoch` and synchronously publish one immutable active-state
   snapshot containing the resolved target and every staged surface. There is no
   separately rendered empty or half-switched state.
7. Dispose old-target terminal, preview, repository, and Agent processes after
   the commit. Late callbacks carry the old `(targetId, targetEpoch)` and are
   discarded by every consumer.

Failure before step 6 leaves the old target active and disposes staged resources;
any old-target turn or mutation the user explicitly approved stopping in step 3
remains stopped. Failure after the commit cannot roll one surface back to the
old target: the new target remains active and the failed new-target surface is
marked stopped or degraded. On process restart, the persisted selected target is
resolved afresh before any target surface is published, so there are no live old
processes to reconcile.

The current implementation in `src/plugin.ts:3454` performs only preference
save, interaction-context update, and rendering. It therefore leaves an open
terminal, Codex workspace-object context, and QMD state bound to the old root.
The first delivery slice implements the transaction for local targets and
closes this split-brain state before remote support is introduced.

## Runtime boundaries

### Local target

The local adapter preserves the current execution model:

```text
Zotero UI
  -> NativeBridge
  -> local codex app-server --stdio
  -> local repository
```

Local filesystem validation, Codex cwd, writable roots, terminal, Quarto, Git,
and Draft operations all use the local target's canonical root.

### SSH target

The local NativeBridge launches a fixed local SSH executable with structured
arguments. The SSH profile selects the endpoint; the remote command is a fixed
QLab wrapper, not user-supplied shell text:

```text
Zotero UI
  -> local NativeBridge
  -> ssh -T <profile> ~/.qlab/bin/<helper-version>/<tuple>/qlab-remote agent
  -> remote codex app-server --stdio
  -> remote repository
```

All agent, repository, setup, terminal, and preview-forward channels for one
target are opened through a target-owned OpenSSH multiplexing master whose
control socket lives in a private `0700` NativeBridge runtime directory. This
keeps channels on the same resolved SSH endpoint even when an alias uses a jump
host or load-balanced hostname. Each root-bound QLab helper channel also returns
the same `hostInstanceId`, `repositoryId`, and helper protocol version during
handshake; the pre-root browser returns only host identity. Any mismatch aborts
target activation. Loss of the master invalidates every channel together and
reconnects them as one target generation.

Codex app-server JSONL remains bidirectional over stdio. Existing dynamic tool
calls can therefore execute against the local Zotero Reader and database while
the Codex process and repository stay remote.

The app-server is not exposed as a TCP or WebSocket service. The remote wrapper
executes as the SSH login user and requires remote Codex to be installed and
authenticated before connection. QLab sends the app-server `initialize` /
`initialized` handshake on every new connection and checks the reported runtime
against the client protocol range before restoring threads.

### Remote helper lifecycle

The remote repository broker is QLab code, so it cannot be assumed to exist on
a new host. NativeBridge manages it like an editor remote-server component:

1. run fixed `uname -s`, `uname -m`, and `uname -r` probes, map the result through the
   allowlisted XPI manifest to `linux-x86_64-static` or
   `linux-aarch64-static`, and reject any other result without uploading;
2. probe the tuple-specific versioned path under `~/.qlab/bin/` through a fixed
   SSH command and require its self-test to report the expected tuple, helper
   version, and protocol major;
3. if absent, stream the matching XPI-bundled, checksummed helper archive over
   that SSH session into a new version directory;
4. verify its digest and executable manifest remotely, then atomically publish
   the version directory;
5. start `browse`, `repository`, or `agent` mode by absolute versioned path;
6. retain the previous helper version for rollback and garbage-collect older
   unused versions only after no session references them.

This is one-time control-plane deployment per helper version, not repository
content synchronization. No Draft, Knowledge, Git state, or Codex credential is
copied. A partially uploaded helper is never executable, and a helper-version
failure leaves the previous version available.

The installed XPI is the local trust root. Its packaged manifest records, for
every supported tuple, the helper version, protocol major, archive digest,
extracted executable digest, and executable relative path. The bootstrap never
chooses an artifact from remote-provided text. After installation it executes
only the manifest-selected absolute path and requires a clean self-test before
starting a protocol channel.

Codex itself is not silently installed or upgraded by QLab. The connection
probe runs fixed `command -v codex`, `codex --version`, and `codex login status`
checks through the remote login shell. Missing, incompatible, or unauthenticated
Codex states produce distinct remediation actions. A remote CLI outside the
app-server protocol compatibility range is blocked instead of being used on a
best-effort basis.

### QLab helper wire contract

The helper broker is a versioned UTF-8 JSONL request/response protocol, separate
from Codex app-server JSONL:

- the first frame in each direction is a handshake containing
  `protocolVersion`, `helperVersion`, `hostInstanceId`, `repositoryId`, and
  advertised capabilities;
- every request has a unique ID, method, parameters, target ID, and target
  epoch; responses echo the ID; events carry a monotonically increasing
  repository cursor;
- stdout contains protocol frames only and stderr contains bounded diagnostic
  text only;
- frames are limited to 8 MiB; QMD bytes use base64 inside a bounded frame, and
  oversized content is rejected with a typed error rather than truncated;
- cancellation is an explicit request; reads have finite timeouts; mutations
  are never inferred to have failed from a timeout alone;
- major protocol mismatch refuses connection; a minor mismatch uses only the
  intersection of advertised capabilities.

NativeBridge treats invalid UTF-8, overlong frames, unknown response IDs,
handshake mismatch, or protocol bytes on stderr as connection failure. Raw
remote output is never interpolated into a shell command or rendered as HTML.

## Component seams

### `AgentConnection`

```ts
interface AgentConnection {
  connect(target: ResolvedRepositoryTarget): Promise<AgentClient>;
  disconnect(): Promise<void>;
}
```

- `LocalAgentConnection` starts the existing local app-server.
- `SshAgentConnection` starts the fixed remote wrapper through NativeBridge and
  SSH.

`CodexAppServerClient` and `NativeSessionSocket` continue to handle app-server
messages; the process-launch decision moves out of `CodexService`.

### `QLabRepository`

```ts
type KnowledgeQmdPath = string & { readonly __kind: "knowledge-qmd" };
type DraftQmdPath = string & { readonly __kind: "draft-qmd" };
type DraftDirectoryPath = string & { readonly __kind: "draft-directory" };
type WorkingCopyQmdPath = string & { readonly __kind: "working-copy-qmd" };
type PreviewQmdPath = string & { readonly __kind: "preview-qmd" };

type RepositoryReadPath =
  | KnowledgeQmdPath
  | DraftQmdPath
  | WorkingCopyQmdPath
  | PreviewQmdPath;

type MutableQmdPath = DraftQmdPath | WorkingCopyQmdPath | PreviewQmdPath;

type RepositoryCommand =
  | { kind: "knowledge-check" }
  | { kind: "draft-check"; path: DraftQmdPath }
  | { kind: "knowledge-preview"; path: KnowledgeQmdPath }
  | { kind: "draft-preview"; path: DraftQmdPath | WorkingCopyQmdPath }
  | { kind: "git-diff"; path: RepositoryReadPath };

interface QLabRepository {
  state(): Promise<RepositoryState>;
  listQmd(afterCursor?: string): Promise<QmdIndexSnapshot>;
  subscribeQmd(
    afterCursor: string,
    onEvent: (event: QmdRepositoryEvent) => void,
  ): RepositorySubscription;
  read(path: RepositoryReadPath): Promise<QmdReadResult>;
  writeIfRevision(request: {
    operationId: string;
    path: MutableQmdPath;
    expectedRevision: string;
    bytes: Uint8Array;
  }): Promise<QmdWriteResult>;
  createDraftFile(request: CreateDraftFileRequest): Promise<QmdWriteResult>;
  createDraftDirectory(request: CreateDraftDirectoryRequest): Promise<void>;
  prepareDraftChange(request: PrepareDraftChangeRequest): Promise<DraftChangeState>;
  keepDraftChange(request: KeepDraftChangeRequest): Promise<KeepResult>;
  removePreview(request: RemovePreviewRequest): Promise<void>;
  mutationStatus(operationId: string): Promise<MutationStatus>;
  run(command: RepositoryCommand): Promise<RepositoryCommandResult>;
}
```

All mutation request types include a caller-generated `operationId`, an exact
target/repository identity, and the expected absent state or revisions. The
TypeScript brands prevent accidental client misuse, but they are not a security
boundary: local and remote implementations parse and enforce the allowed tree
and file kind again for every request. `RepositoryCommand` is a closed union;
it contains no executable, argv, cwd, environment, or shell string supplied by
the caller.

The remote host folder picker uses a separate pre-root interface:

```ts
interface RemoteHostBrowser {
  home(): Promise<CanonicalRemoteDirectory>;
  list(path: CanonicalRemoteDirectory): Promise<RemoteDirectoryEntry[]>;
  resolveCandidate(input: string): Promise<CanonicalRemoteDirectory>;
}
```

It can inspect only directories available to the authenticated SSH user. It
starts at that user's home; an absolute path such as `/srv/research` is visited
only after explicit user entry. Selecting a candidate closes the browser and
creates a root-locked `SshQLabRepository`.

- `LocalQLabRepository` wraps the existing `IOUtils`, path validation, Draft,
  and command implementations.
- `SshQLabRepository` talks to a constrained remote repository broker over a
  second persistent SSH stdio session.

The repository broker is separate from the Codex app-server connection. A
remote app-server can be waiting for a local Zotero dynamic-tool response while
that tool needs to read a remote QMD file; using the app-server connection for
both directions could deadlock.

`listQmd` returns explicit directory and QMD nodes plus a repository cursor, so
empty Draft directories are representable. `subscribeQmd` uses a remote Linux
filesystem watcher and sends target-scoped invalidation events. Watch overflow,
helper restart, or a cursor gap triggers one reconciliatory `listQmd`; reconnect
resubscribes from the last cursor. The local adapter may retain its current
coalesced polling implementation initially. No SSH target performs an
unconditional two-second full-tree poll.

### Target-scoped resource owners

Codex conversations, workspace objects, terminals, previews, QMD workspaces,
Draft manifests, Main Site sessions, and repository command state carry
`targetId`; asynchronous work additionally carries `targetEpoch`. A consumer
rejects state from another target or older epoch instead of silently rebasing
its paths.

Target capabilities are resolved once into the immutable active snapshot. They
are not inferred from path syntax or from whether a button happens to be
visible:

```ts
type RepositoryTargetCapabilities = {
  chat: boolean;
  qmdRead: boolean;
  qmdWrite: boolean;
  terminal: boolean;
  preview: boolean;
  mainSiteSupported: boolean;
  externalEditor: boolean;
  promoteDraft: boolean;
};
```

For local targets, these values preserve existing behavior. For SSH targets,
`externalEditor` and `promoteDraft` remain `false` in all four slices.
`mainSiteSupported` is `false` for SSH targets until Slice 4 and `true`
afterwards; it describes permission and implementation support, not a running
server. Every action checks capability plus `(targetId, targetEpoch)` before
doing work; a disabled SSH action never passes the remote root to local
`IOUtils`, `realPath`, process launch, or the local external-editor adapter.

## Draft and QMD data flow

### Agent writes

For an SSH target, Codex cwd and writable roots are remote absolute paths.
Codex creates new Drafts and edits Agent working copies directly under the
remote repository's `drafts/` and `work/` trees. No Draft is copied to a local
repository.

### Visual Edit save

1. Workbench reads the QMD through `QLabRepository.read` and retains its
   revision.
2. The user edits source locally in the Zotero UI.
3. Save calls `writeIfRevision` with a new operation ID and the expected
   revision.
4. The repository implementation checks the revision, writes a sibling
   temporary file, flushes it, and atomically renames it.
5. Revision mismatch returns a conflict; it never overwrites a newer remote
   version.

### Keep

`keepDraftChange` receives an operation ID plus expected base and working-copy
revisions. The repository implementation revalidates both at the authoritative
repository and performs the replacement there. A lost connection after
submission returns an **outcome unknown** state; Workbench queries
`mutationStatus(operationId)` before offering retry and never creates a new
operation ID for an uncertain overwrite.

The helper keeps an idempotency journal outside the repository under its private
remote state directory. Before changing content it durably records the operation
ID, target identity, expected revisions, and result-content hash; after atomic
rename and parent-directory flush it records the resulting revision. A broker
restart resolves any prepared entry before accepting another mutation for that
path. Reusing an operation ID with different parameters is rejected. Completed
results remain queryable for at least seven days and while a local manifest
still references them; cleanup never removes prepared or outcome-unknown
records.

Local manifests are keyed by `targetId + repositoryId + relativePath`. They may
store UI and revision metadata, but not an authoritative copy of QMD content.

## Preview, terminal, and commands

- Local targets keep the current local PTY and Quarto execution.
- SSH terminals execute through an explicitly labeled SSH PTY and always show
  the SSH profile and canonical remote root.
- Quarto render, Git diff, validation, and repository checks execute on the
  machine that owns the repository.
- Remote HTTP previews bind to remote loopback and are exposed only through an
  explicit SSH local-forward allocation. Closing the preview releases the
  forward.
- Every Quarto render or preview retains `--no-execute`.

The **Main Site** surface follows the same ownership rule. Slice 1 makes the
existing local site process a `MainSiteSession` tagged with target ID and epoch;
switching local roots disposes the old server and its callbacks before the new
root can be shown. Until Slice 4, **Main Site** is disabled on SSH targets with a
remote-capability explanation. Slice 4 runs the site build/server on the remote
host, binds it to remote loopback on a dynamically allocated port, and exposes
it through a target-owned SSH local forward on a dynamically allocated local
port. The forward and remote process are both closed on switch, disconnect, or
window shutdown. No SSH target invokes the current local site starter or reads
the remote path through local filesystem APIs.

```ts
interface MainSiteSession {
  targetId: string;
  targetEpoch: number;
  localUrl: string;
  stop(): Promise<void>;
}

interface MainSiteConnection {
  start(
    target: ResolvedRepositoryTarget,
    targetEpoch: number,
  ): Promise<MainSiteSession>;
}

type MainSiteSessionState =
  | { status: "stopped"; targetId: string; targetEpoch: number }
  | { status: "starting"; targetId: string; targetEpoch: number }
  | { status: "ready"; session: MainSiteSession }
  | { status: "error"; targetId: string; targetEpoch: number; message: string };
```

`LocalMainSiteConnection` wraps the existing local starter.
`SshMainSiteConnection` starts a fixed `main-site` helper mode, receives its
remote loopback port over the helper protocol, and asks NativeBridge for a
structured-argument SSH forward. Neither implementation accepts caller-supplied
shell text, and a session URL is published only after its target and epoch still
match the active snapshot.

`mainSiteSupported` gates the action; `MainSiteSessionState` describes its
runtime. A newly activated target always begins `stopped`. Switching targets
never runs dependency checks, builds, starts a server, or allocates a forward on
its own. The user's **Main Site** action changes `stopped` or `error` to
`starting`; success may publish a URL only from `ready`. This preserves the
existing on-demand start behavior and avoids capability/session deadlock.

**Edit in External Editor** remains available for local targets and keeps its
current local-real-path contract. On SSH targets it is disabled with an explicit
message; Visual Edit inside Workbench remains the supported editor. Repository
initialization exists only inside the pre-target local-candidate workflow; it is
unavailable for SSH candidates and is not an active-target action. The product
must not silently open a local same-named path, create a local repository, or
send a remote path to a local editor.

Terminal commands remain direct user-controlled actions outside the Agent
approval boundary, matching current local behavior.

## Trust and security boundaries

1. `knowledge/**/*.qmd` remains the only trusted content authority. Neither
   local nor remote Agent mode receives direct write access to it.
2. Agent writable roots remain limited to `drafts/`, `literature/`, and
   generated `work/`; promotion remains a separate reviewed workflow followed
   by `make knowledge-check` and is not exposed by the generic repository RPC.
3. The SSH host key is part of target identity. Profiles use the user's SSH
   configuration and `known_hosts`; QLab stores no SSH credentials.
4. Remote helpers bind no public port. NativeBridge remains a local,
   profile-private Unix-socket service and is never forwarded to the remote
   host.
5. The remote repository broker canonicalizes the configured root, rejects
   absolute request paths, NUL, `.`, `..`, and every symlink component, and
   revalidates allowed tree and file kind for every request. Mutation code uses
   descriptor-relative, no-follow opens and an atomic rename within the already
   validated parent directory so a symlink swap cannot redirect a write after
   validation. Local Gecko checks and TypeScript brands are not accepted as
   proof about remote paths.
6. Ordinary write RPCs accept only Draft QMD, the named
   `work/qlab-zotero/draft-changes/` working-copy tree, and its bounded preview
   paths. They always reject `knowledge/**`, unrelated `work/**`, and all
   `literature/**` writes. Repository commands are a closed enum implemented by
   the helper and never execute caller-supplied shell text.
7. The first remote release fails closed on app-server approval requests whose
   remote path cannot be independently validated inside configured roots.
8. Remote Codex context excludes local PDF, attachment, cache, and profile
   paths. Paper content crosses the boundary only through an explicit Zotero
   dynamic tool call or attached content.
9. The UI continuously labels remote targets because a remote Codex can receive
   user-authorized Zotero content through dynamic tools.

## Error handling

- **SSH authentication or host-key failure:** leave the old target active and
  surface the native SSH error without falling back to another host.
- **Remote Codex unavailable:** keep repository browsing available when the
  broker is healthy; disable Chat with a target-specific explanation.
- **Repository broker unavailable:** Chat history remains viewable, but starting
  or steering a remote Agent turn and all QMD, Draft Keep, preview, and
  repository-command mutations are disabled because writable roots cannot be
  revalidated.
- **Unsupported remote helper tuple:** show the probed OS/architecture and the
  two supported tuples; do not upload a fallback artifact or start Codex.
- **Remote Main Site unavailable before Slice 4:** keep the action disabled and
  explain that the site must execute on its repository host. Never start a local
  server against the remote path.
- **Remote external editor or repository initialization requested:** keep the
  action disabled with a target-specific explanation; do not call the local
  adapter.
- **Connection loss during a read:** reconnect and retry once when no mutation
  was submitted.
- **Connection loss during a write:** report outcome unknown and resolve by
  operation ID or current revision before retry.
- **Remote root moved or replaced:** repository identity mismatch invalidates
  target-scoped sessions and requires the user to select the repository again.
- **Target switch validation failure:** retain the complete old target state.

## Testing strategy

### Local switching regression

- Start with an active `/old` target and live terminal, choose `/new`, and
  assert preference, UI, terminal cwd, Codex turn cwd, writable roots, and
  Research object all use `/new`.
- Assert the old PTY is closed and a visible terminal is reopened at `/new`.
- Assert a running Codex turn cannot be moved with `turn/steer`.
- Assert an unsaved QMD workspace blocks switching.
- Assert validation failure leaves every surface on `/old`.
- Inject failure while staging conversation, terminal, QMD state, preference
  persistence, and new-surface startup; assert pre-commit failure leaves every
  surface on `/old`, while post-commit failure leaves every surface tagged `/new`
  with only the failed surface degraded.
- Resolve an old-target index, terminal, preview, and Codex callback after the
  switch and prove every callback is discarded by target epoch.
- Start Main Site on `/old`, switch to `/new`, and prove the old process and
  local port are closed, a late callback cannot reopen it, and any new site
  session is tagged `/new`.
- Select B while A -> B is preparing, then select C; prove B is canceled and
  only C can commit. Select C while A -> B is committing and prove C is queued
  until B reaches a complete active snapshot.

### Target model and session isolation

- Migrate a ready `qlabRoot` preference to a UUID-backed local target without
  losing eligible sessions. Migrate empty/partial roots to one pending candidate
  with no active target or thread binding until confirmation. Migrate missing or
  incompatible roots to no target and keep their sessions Legacy/unassigned.
  Interrupt and rerun each path without duplicate UUIDs, candidates, targets, or
  bindings.
- Switch A -> B -> A and restore each target's conversation without cross-target
  workspace objects or thread IDs.
- Use identical path strings on two SSH profiles and prove their target IDs and
  manifests remain distinct.
- Select an empty or partial local directory and prove cancellation writes
  nothing; after exact confirmation, prove initialization and Git-private UUID
  creation finish before target activation. Inject partial initialization
  failure and prove the old target stays active and the candidate is not saved.
- Recreate a repository at the same canonical path without copying its
  Git-private QLab state and prove the new repository UUID invalidates the saved
  target. Treat a host-key rotation as a new endpoint until the user reselects
  it.

### SSH transport

- Exercise the real argv and JSONL boundaries with a fake SSH executable below
  NativeBridge; do not assert only that a mock was called.
- Parse only concrete OpenSSH aliases, pass the alias as one argv element, and
  prove spaces or shell metacharacters cannot become a remote command.
- Exercise helper probe, checksummed install, atomic activation, version
  rollback, and cleanup without copying repository content.
- Run the actual packaged helper and self-test for both
  `linux-x86_64-static` and `linux-aarch64-static` release artifacts; reject an
  unsupported OS/architecture and a tuple/version/digest mismatch before
  upload or target activation.
- Exercise the bootstrap folder browser before a repository root exists, then
  prove the repository broker cannot escape the selected canonical root.
- Report SSH, helper, Codex availability, Codex compatibility, Codex auth, and
  repository validation failures as different connection states.
- Prove headless authentication launches only the fixed
  `codex login --device-auth` terminal action and never reads or persists its
  output as a credential.
- Force two logical channels to report different host-instance or repository
  IDs and prove target activation fails. Drop the target's multiplexing master
  and prove all channels enter one disconnected generation.
- Verify malformed remote frames, early EOF, nonzero exit, cancellation, and
  reconnection, plus overlong frames, invalid UTF-8, unknown response IDs, and
  incompatible protocol versions.
- Verify no local paths appear in remote turn context.
- Assert SSH External Editor and repository initialization never call local
  path resolution, filesystem, or process adapters.

### Repository broker and Draft consistency

- Reject absolute paths, traversal, and symlink escape using a temporary real
  repository.
- Reject a syntactically valid `knowledge/` mutation, unrelated `work/` path,
  `literature/` broker write, symlink-swap race, and every command value outside
  the closed command union.
- Prove revision compare-and-swap and atomic replacement behavior.
- Disconnect before a complete request frame is written and prove it was not
  submitted. Disconnect after a complete mutation frame but before its response
  and enter outcome-unknown resolution; prove `mutationStatus` resolves the
  operation as absent, prepared, or applied for failures before prepare, before
  commit, and after commit.
- Restart the broker with prepared and completed journal records, reuse the same
  operation ID, and prove the mutation is resolved or deduplicated rather than
  repeated. Reject the same ID with different parameters.
- Prove Keep cannot cross target IDs or repository IDs.
- Overflow the remote file watcher and prove one full reconciliation occurs;
  reconnect from a valid cursor without a full poll, and discard events carrying
  an old target epoch.

### Security and trust

- Assert remote Agent writable roots exclude `knowledge/`.
- Assert remote approval requests fail closed unless remotely canonicalized
  inside configured roots.
- Assert local PDF and Zotero profile paths are absent from remote prompts and
  app-server requests.
- Assert Quarto invocations retain `--no-execute`.
- Start remote Main Site on remote loopback, reach it only through its dynamic
  local SSH forward, then switch targets and prove both the forward and remote
  process are released. Prove a late old-epoch callback cannot publish its URL.
- Activate a never-started SSH target in Slice 4 and prove Main Site is supported
  but stopped: the button can start it, while target activation itself performs
  no dependency check, build, server launch, or port-forward allocation.

## Delivery slices

### Slice 1 — Correct local target switching

Introduce the minimal local `RepositoryTarget`, `targetId`, and `targetEpoch`,
then implement the target-switch transaction for the existing local-root
setting. Dispose or reopen target-scoped terminal state, isolate Codex
conversation and workspace-object state, block unsafe in-flight switching, and
reset QMD state. Move the existing Main Site process under the same target
owner so it cannot survive a local root switch. Add the pre-target local
candidate setup so empty/partial initialization produces a valid Git identity
before activation. This fixes the reported bug without adding SSH behavior.

### Slice 2 — Repository Target model and remote Chat MVP

Expand `RepositoryTarget` with SSH targets, preference migration, target-scoped
sessions, `AgentConnection`, SSH connection diagnostics, versioned helper bootstrap,
headless Codex-auth remediation, bootstrap folder browsing, remote root
resolution/identity, writable-root validation, and remote Codex app-server
stdio. This slice includes the minimal broker handshake required before a remote
turn can start. Remote Codex can directly create Drafts, but Visual Edit, Keep,
preview, Main Site, External Editor, repository initialization, and repository
commands remain visibly disabled for SSH targets.

### Slice 3 — Remote repository and complete Draft workflow

Introduce `QLabRepository`, the constrained remote broker, remote folder
selection, explicit-directory QMD index/read/save, file-change subscription,
working-copy preparation, idempotent mutation journal, Keep, and Note bridge QMD
reads. Remove direct filesystem calls from Workbench Draft operations.

### Slice 4 — Remote terminal, commands, previews, and Main Site

Add labeled SSH PTY sessions, remote Git/validation/Quarto commands, preview
port allocation, remote Main Site execution, and SSH local forwarding. Each
process and forward is target-scoped and disposed by the same switch
transaction. External Editor, repository initialization, and Draft promotion
remain explicit remote non-goals.

Each slice receives its own implementation plan and test-first commits. Slice 1
must ship before remote support so the common target-switch invariant is proven
locally.

## Alternatives rejected

### SSHFS mount

It offers a quick prototype but exposes remote paths as a second local
namespace, makes symlink and canonical-path checks ambiguous, and performs
poorly under repeated indexing and rendering operations. It is not the product
contract.

### Local clone plus Git, rsync, or `scp`

This creates two content authorities and introduces synchronization conflicts
into Draft revision and Keep semantics. It may remain an explicit import/export
operation but is not transparent editing.

### Retarget the existing Codex conversation

A conversation contains repository instructions, workspace objects, tool
results, and historical paths. Mutating only its cwd would preserve stale
cross-repository context. Conversations therefore remain bound to their
original target.

## Official external references

- [Codex remote connections and SSH-host projects](https://learn.chatgpt.com/docs/remote-connections)
- [Codex authentication on headless devices](https://learn.chatgpt.com/docs/auth#login-on-headless-devices)
- [Codex app-server protocol and stdio transport](https://learn.chatgpt.com/docs/app-server#protocol)
- [VS Code Remote Development architecture](https://code.visualstudio.com/api/advanced-topics/remote-extensions)
- [VS Code Remote-SSH](https://code.visualstudio.com/docs/remote/ssh)
