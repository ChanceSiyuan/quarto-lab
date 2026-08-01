# Zotero ChatGPT Companion — Read-only Handoff Design

- **Date:** 2026-08-01
- **Status:** Approved by user (“按照你的计划” / “continue”)
- **Target branch:** `fix/zotero-fix-pack-b`
- **Development host:** Linux; native Zotero and macOS visual verification are deferred
- **Visual baseline:** the approved Apple-like QLab Floating Palette and the existing Workbench composer
- **Superdesign:** [QLab ChatGPT Companion canvas](https://superdesign.dev/teams/7623f2af-92ca-422d-8eea-cb9900e4f24c/projects/ebecd964-4fcf-4023-bc2d-44924138d6e1)

## Outcome

A researcher reading a paper in Zotero can hand the current question and a
frozen, bounded copy of the visible research context to ChatGPT in one action.
ChatGPT remains the real chat host and uses the user's own ChatGPT subscription
and a separately configured, strictly read-only QLab MCP connector. The
Companion path makes no Codex request, starts no Codex thread, and consumes no
Codex turn.

The first release deliberately does not embed, scrape, or automate the ChatGPT
website. QLab copies an inspectable prompt and opens `https://chatgpt.com/`.
The user pastes/sends it in ChatGPT. A second explicit action can import text
that the user copied from ChatGPT back into the Workbench with provenance.

The repository side exposes a tunnel-ready authenticated Streamable HTTP MCP
endpoint with only `search` and `fetch`. It can read reviewed Knowledge, visible
Problem records, and validated Literature metadata. It cannot write, run
commands, access Zotero, or search Drafts.

## Product contract

### Companion handoff

The Workbench composer gains a quiet `Ask in ChatGPT ↗` action beside the
local model controls. It is a handoff action, not a fake model entry:

1. Take the unsent composer question.
2. Freeze the current Zotero/QLab context into an immutable capsule.
3. Persist that capsule in the plugin-private Zotero profile.
4. Build a bounded, trust-labelled prompt from the capsule.
5. Copy the prompt.
6. Only after a successful copy, open ChatGPT.
7. Show `Context copied · paste in a ChatGPT chat with the QLab app enabled`
   without obscuring reading.

The composer text is not cleared. Failure to copy prevents the browser launch,
so the user is never sent to an empty handoff with false success feedback.

Companion input remains usable when Codex is signed out, disconnected,
unavailable, or has no active thread. In those states the Workbench leaves its
composer reachable, enables text entry and the Companion control, and keeps the
Codex model/effort/Send controls disabled. Enter never falls through to a Codex
send while Codex is unavailable. Handoff and import never call Codex login,
thread, turn, or send operations.

The existing history-rail `Open ChatGPT` control remains a plain open action.
It does not silently capture context. The primary Companion action belongs to
the composer, where the user can see the question and context chips being sent.

### Explicit answer import

`Import copied answer` reads the clipboard only in response to the user's
click. It rejects blank or over-limit text, appends a local transcript entry,
and labels it `Imported from ChatGPT · user copied`. It never:

- observes the browser;
- reads cookies or login state;
- injects JavaScript into ChatGPT;
- polls or scrapes the DOM;
- intercepts response streams; or
- presents imported text as a Codex result.

Imported text is local evidence from another chat, not trusted Knowledge. V1
imports are session-local Workbench entries. They reference the capsule ID and
checksum, stay in a plugin-owned overlay separate from app-server entries,
never mutate a Codex thread, and disappear on Zotero restart. Durable ChatGPT
memory belongs to the later AI Context attachment feature.

Each successful handoff adds a bounded session-local pending record under its
captured subject. The composer shows exactly one selected pending association
at a time, identified by question preview, creation time, and shortened capsule
ID; the newest is selected by default, and an accessible selector can choose an
older pending handoff. `Import copied answer` is disabled when the current
subject has no selected pending handoff. A successful import consumes that
pending record, while other pending handoffs remain selectable.

Imported transcript rows carry `origin: "chatgpt-companion"`, the capsule ID
and checksum, and the visible label `Imported from ChatGPT · user copied` on
the assistant row itself. They never reuse the Codex avatar or `alt="Codex"`.

### ChatGPT connector

The connector follows the standard read-only search/fetch shape:

```text
search({ query })
  -> candidates with stable id, title, canonical URL, authority and review state

fetch({ id })
  -> complete model-facing text plus the same provenance fields
```

Both tools carry exact annotations `readOnlyHint: true`,
`destructiveHint: false`, `idempotentHint: true`, and
`openWorldHint: false`. Tool results return the same JSON in
`structuredContent` and a text content block.

The top-level server instructions enforce:

```text
reviewed knowledge != external literature != open problem != unreviewed draft
```

The connector never claims that it modified files, Zotero, experiments,
builds, or Git state.

## Context capsule

### Why a capsule exists

Reader focus, selection, page, secondary papers, and the visible Draft can all
change while ChatGPT is opening. A capsule binds one handoff to exactly what
the user saw at click time. Later UI changes cannot mutate an old handoff.

### Safe schema

```ts
interface ChatGPTCompanionCapsule {
  schemaVersion: 1;
  id: string;                 // opaque random capability-free identifier
  createdAt: string;
  subject: {
    paperKey: string | null;
    draftPath: string | null; // repository-relative only
  };
  question: string;
  contextItems: Array<{
    id: string;
    kind: "paper" | "page" | "selection" | "annotation" | "library"
      | "external-paper" | "screenshot" | "draft";
    included: boolean;
    supported: boolean;
    sourceIdentity: string;
    mode: string | null;
    authority: "external_evidence" | "unreviewed_draft" | "unsupported";
    warning: string | null;
  }>;
  paper: {
    authority: "external_evidence";
    title: string;
    creators: string;
    year: string;
    doi: string;
    url: string;
  } | null;
  page: {
    authority: "external_evidence";
    pageNumber: number;
    pageLabel: string;
    excerpt: string;
    source: string;
  } | null;
  selection: {
    authority: "external_evidence";
    text: string;
    pageNumber: number | null;
  } | null;
  secondaryPapers: Array<{
    authority: "external_evidence";
    title: string;
    creators: string;
    year: string;
    doi: string;
    url: string;
    mode: "retrieval" | "full";
  }>;
  draft: {
    relativePath: string;
    authority: "unreviewed_draft";
    excerpt: string;
    truncated: boolean;
  } | null;
  screenshotProvenance: Array<{
    kind: "page" | "region";
    paperTitle: string;
    pageNumber: number | null;
  }>;
  warnings: string[];
  bounds: Record<string, number>;
  contentHash: string;
}
```

### Bounds and exclusions

The builder uses deterministic Unicode-aware caps:

- question: 8,000 characters;
- selection: 8,000 characters;
- current page excerpt: 12,000 characters;
- active Draft excerpt: 20,000 characters;
- secondary papers: 20;
- screenshot provenance entries: 8;
- final prompt: 48,000 characters;
- imported answer: 64,000 characters.

Truncation is explicit in the capsule and prompt. The capsule and prompt never
contain:

- an absolute PDF or repository path;
- whole-PDF text or indexed full-text references;
- raw screenshot bytes/data URLs;
- cookies, tokens, environment variables, or browser state;
- Codex system prompts, hidden tool instructions, or whole chat history;
- Zotero database IDs when a stable item key or citation identity suffices.

The active Draft excerpt is included only because the user explicitly invokes
the handoff while it is visible. It is always labelled
`authority: unreviewed_draft`. Drafts remain absent from MCP search/fetch.

### Effective context snapshot

The capsule is built from one ordered snapshot of the exact context chips
effective at click time, not from the Reader context alone. It records every
supported and intentionally omitted item:

- removed `Current Paper` or `Current Page` chips suppress those payloads;
- `Current Selection` is included only when its chip is present;
- annotations and Zotero Library chips are recorded as requested but omitted
  with an explicit warning because the remote repository MCP cannot access the
  Zotero database;
- secondary papers preserve their retrieval/full mode and transfer only safe
  citation identity in v1, with a warning that local PDF/full text was not
  transferred;
- screenshots preserve paper/page/region provenance but omit pixels, with a
  visible warning;
- the visible Draft is a separate `draft` context item and is labelled
  unreviewed.

Current-paper metadata, page excerpts, selections, secondary papers, and
screenshot provenance are all labelled `external_evidence`; none is presented
as repository-reviewed Knowledge.

The workspace keeps a last-known Draft `{relativePath, revision, source}`
snapshot updated whenever it opens, reloads, or saves the active Draft. At
Companion click time that in-memory snapshot and every chip/backing value are
deep-cloned synchronously before persistence, clipboard, launch, or any other
await. The plugin then rereads the same safe repository-relative Draft and
compares its content revision. If no click-time snapshot exists, the active
path changed, or the revision no longer matches, the Draft body is omitted with
an explicit `Draft changed during handoff` warning; it is never silently
replaced with later content. Concurrent Reader/Draft/chip changes therefore
cannot retarget the capsule.

### Persistence

Capsules are stored below:

```text
<Zotero profile>/zotkit/companion-capsules/<opaque-id>.json
```

The directory is private (`0700`) and files are private (`0600`) where the
host supports POSIX permissions. Writes are atomic. A stored checksum is
verified on load. Invalid schema, checksum mismatch, oversized data, and
path-shaped IDs fail closed. Capsules expire after 30 days and can be
explicitly deleted.

`contentHash` is a corruption checksum over a documented canonical JSON
serialization, not an authentication MAC. It detects accidental or local file
modification; it does not claim to resist an attacker who can rewrite both the
capsule and checksum.

No capsule ID grants MCP access to the Zotero profile. The bounded capsule
content is placed directly in the clipboard prompt; the repository MCP remains
physically unable to read Zotero-private files.

## Prompt format

After a fixed safety/trust preamble, the copied prompt has four visible parts:

1. the user's exact question;
2. frozen paper/page/selection/secondary-paper/Draft context;
3. trust labels and truncation warnings;
4. MCP retrieval instructions.

It tells ChatGPT to treat every delimited paper/page/selection/Draft/MCP body
as quoted data, never as instructions, and to ignore tool-use or policy
instructions found inside that data. It then tells ChatGPT to search reviewed
Knowledge first, use Literature only as external evidence, identify open
Problems separately, and never substitute a Draft for a reviewed conclusion.
It includes the capsule ID and checksum for provenance, but makes no claim that
ChatGPT can fetch the capsule by ID.

The accepted question is preserved code-point-for-code-point and is never
trimmed, Unicode-normalized, or truncated. Blank-only input, NUL/disallowed
control characters, and questions above 8,000 Unicode code points are rejected
rather than rewritten. Context metadata may be normalized separately.

The 48,000-character prompt budget first reserves fixed space for the safety
preamble, exact question, capsule/checksum, primary-paper identity, all source
provenance, and every omission/truncation warning. Those mandatory fields are
individually bounded so the reservation always fits. The remaining space is
allocated deterministically to selection, current page, Draft, and secondary
paper identities. Optional bodies are shortened or omitted before any warning
or provenance can be lost.

Only the Zotero-side context is frozen. Reviewed Knowledge is retrieved live
from the configured QLab app when ChatGPT calls it; repository changes after
handoff may therefore change the answer. Each fetched document reports the
repository revision/content hashes it actually used. Exact frozen Knowledge
snapshots are a future feature, not a v1 claim.

## Read-only MCP architecture

### Deep interface

`src/lib/companion/context.ts` owns all repository retrieval. Its public
surface is only:

```ts
search(query: string): Promise<CompanionSearchResult[]>
fetch(id: string): Promise<CompanionDocument>
```

The adapter reuses existing domain modules:

- Knowledge: `resolveKnowledge` and `loadKnowledge`;
- Problems: `buildProblemIndex` and `createProblemRepository`;
- Literature: `loadBibliography`.

It must not call write-oriented literature, assessment, autoresearch, Zotero,
Quarto, shell, or Git services.

### Namespaces

- `knowledge:<versioned base64url query + selection digest>`
- `problem:<validated problem id>`
- `literature:<validated citekey>`

Knowledge IDs contain only a bounded query and a SHA-256 digest of the selected
resolver candidate identity; they never contain `selectedPage`, an ordered file
path, or any other repository path, even after base64url decoding. `fetch`
decodes the versioned query/digest, reruns the resolver, hashes each currently
valid candidate identity, and accepts only the unique digest match. Unknown,
stale, ambiguous, or modified digests fail closed. A match returns every file in
`bundle.orderedFiles`, in resolver order, so inherited trusted context is not
lost.

One `isCompanionVisibleProblem` predicate hides rejected and archived records
in both search and direct fetch. Guessing a predictable hidden Problem ID
returns the same not-found response as an unknown ID, without revealing state
or metadata. Literature returns only validated bibliographic metadata and labels it
`authority: external_evidence`; it does not expose `.raw/`, `.figures/`,
attachment paths, abstracts from private Zotero data, or paper full text.

### URLs, authentication, and deployment boundary

Endpoint identity and cited-content identity are separate configuration:

- `QLAB_COMPANION_ENDPOINT_BASE_URL` is the external HTTPS MCP origin used only
  to configure the ChatGPT app;
- `QLAB_COMPANION_PUBLIC_BASE_URL` is the credential-free public QLab content
  origin used only to construct canonical Knowledge/Problem/Literature links;
- `QLAB_COMPANION_ACCESS_TOKEN` is a minimum-32-byte capability used only in the
  MCP request path.

Both base URLs reject userinfo, query strings, fragments, and capability-token
path segments; production requires HTTPS. The content base must not contain
the access token and is never derived from the endpoint URL. Results, copied
prompts, and logs must never contain the token or token-bearing request target.

The local server binds to `127.0.0.1` by default and exposes a token-bearing MCP
path derived from the access token. Wrong or missing tokens return an
indistinguishable not-found response. It is not added to the existing public
Worker because current domain modules depend on the local repository filesystem.

The implementation is tunnel-ready, not silently deployed. ChatGPT cannot
connect directly to localhost. Before handoff, the user must:

1. expose the loopback service through OpenAI Secure MCP Tunnel when available,
   or a user-managed authenticated HTTPS reverse tunnel;
2. configure the resulting remote endpoint as a read-only QLab app in ChatGPT
   Developer Mode; and
3. enable that app in the target chat.

For the user-managed path the documented connector URL combines the separate
endpoint base with the rotated capability-token route; the reverse proxy must
not strip it and must avoid request-target logging. The server itself logs only
redacted route categories. It also accepts a trusted-tunnel mode only when the
operator explicitly opts in and the listener remains loopback.

Production startup requires an OS-level read-only repository mirror/mount.
The server checks write access without creating a file and fails closed when
the root is writable. A named developer-only override exists for local tests
and is never the documented remote command. The server registers no shell,
write, render, Git, or arbitrary-file tools.

## Search semantics

Search is trust-domain aware rather than one undifferentiated full-text index:

1. resolve reviewed Knowledge;
2. search visible Problems;
3. search validated Literature metadata;
4. merge bounded results while preserving authority;
5. never search `drafts/`.

`ambiguous` Knowledge results are returned as separate candidates and never
silently chosen. `no-match` does not fall back to Drafts or Literature as if
they were learned Knowledge.

The first implementation may use current title/frontmatter/metadata matching.
No vector database is required. Caching is allowed only behind a repository
fingerprint/mtime invalidation boundary.

## UI behavior

The Companion action reuses existing Workbench material and typography:

- system font and existing `--zc-*` tokens only;
- a compact bordered control in the composer footer;
- system blue for confirmation, not permanent emphasis;
- no sidebar, modal, embedded browser, new brand palette, or decorative
  gradient;
- compact-width icon/tooltip fallback;
- keyboard and screen-reader names for handoff and import;
- reduced-transparency behavior inherited from the Workbench.

The action is available in the Workbench even without a live Codex
conversation, including signed-out/disconnected/unavailable phases. It is not
available while browsing imported read-only ChatGPT history and remains
disabled when no question is present. The Codex login layer leaves the
Workbench composer reachable while still protecting Codex-only controls.

## Failure behavior

- Clipboard copy fails: show an actionable error and do not open ChatGPT.
- Capsule persistence fails: fail the handoff; do not claim the context was
  frozen.
- Draft read fails: continue only with an explicit warning and no Draft body.
- ChatGPT cannot be opened: keep the copied prompt and say it is ready to paste.
- MCP has no reviewed match: report that gap explicitly.
- MCP receives an invalid ID, path traversal, oversized query/body, or unknown
  namespace: return a structured error without reading a file.
- Connector loses its client: release the session; never retain write state
  because none exists.

## Test strategy

### Zotero integration

- immutable snapshot remains unchanged after Reader/Draft focus changes;
- bounds, trust labels, no absolute paths/full text/raw images/secrets;
- opaque IDs, schema/checksum-mismatch validation, atomic/private persistence,
  expiry and delete;
- prompt contains exact question and provenance, never hidden state;
- copy succeeds before URL launch;
- failed copy prevents launch;
- explicit clipboard import labels provenance and rejects blank/oversized text;
- two pending handoffs can be distinguished and an older one explicitly
  selected before import;
- the imported assistant row itself is labelled ChatGPT and never renders a
  Codex avatar/label;
- Workbench composer action renders, disables, and emits the correct callback;
- signed-out/unavailable handoff and import make no Codex login/thread/turn/send
  calls;
- every effective context chip is frozen with included/supported/omitted state;
- malicious instructions in paper/page/Draft text remain delimited data;
- existing plain `Open ChatGPT` and imported-history behavior remain intact.

### MCP

- initialize, `tools/list`, `search`, and `fetch` over Streamable HTTP;
- tool schemas, annotations, structured/text result parity;
- full ordered Knowledge bundle, ambiguity, no-match, and invalid selection;
- hidden Problem states in both search and guessed direct fetch, plus immutable
  returned objects;
- Literature metadata-only result with external authority;
- invalid/oversized/tampered IDs and traversal attempts;
- separate endpoint/content-base and access-token validation, including tests
  that token material never appears in results, prompts, or captured logs;
- unauthorized remote-style requests and writable-root startup refusal;
- before/after repository tree hash as regression evidence that the tested
  operations made no writes.

## Non-goals

- No ChatGPT Cookie reuse or login extraction.
- No ChatGPT DOM control, extension injection, response-stream interception,
  or background scraping.
- No iframe or embedded ChatGPT webview.
- No claim that ChatGPT Pro is callable as an API model.
- No mixing ChatGPT into the local Codex model selector.
- No browser-generated response written directly into a Draft or Knowledge.
- No MCP write tools, proposal queue, remote executor, shell, Quarto render, or
  Git control.
- No automatic deployment, tunnel creation, OAuth server, or persistent secret
  storage in this slice. The operator supplies the process token at launch.
- No macOS-native completion claim from the Linux development host.

## Acceptance criteria

1. From the Workbench, including when Codex is signed out or unavailable, one
   explicit action persists a frozen safe capsule, copies a trust-labelled
   prompt, and opens ChatGPT only after the copy without making a Codex request.
2. The capsule honors every effective context chip. A changed Reader selection,
   page, paper, Draft, or chip set does not change the saved capsule or copied
   prompt.
3. The user can explicitly import copied ChatGPT text and sees unambiguous
   provenance.
4. The authenticated, tunnel-ready MCP server offers only read-only `search`
   and `fetch`, with reviewed Knowledge, visible Problems, and external
   Literature kept distinct. Remote use requires that the QLab app is already
   configured and enabled in the ChatGPT chat.
5. Draft content appears only in the explicit clipboard handoff, labelled
   unreviewed; it never enters MCP search/fetch.
6. Production startup refuses a writable repository root; remote operation uses
   a read-only mirror/mount and unauthorized requests reveal no document state.
7. Focused tests, TypeScript checks, build, and all environment-supported tests
   pass on Linux; macOS/native Zotero visual validation is reported as deferred.
