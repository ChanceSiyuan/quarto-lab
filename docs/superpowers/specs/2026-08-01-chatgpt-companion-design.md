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
and a separately configured, strictly read-only QLab MCP connector. Codex and
ChatGPT therefore do not share a usage pool.

The first release deliberately does not embed, scrape, or automate the ChatGPT
website. QLab copies an inspectable prompt and opens `https://chatgpt.com/`.
The user pastes/sends it in ChatGPT. A second explicit action can import text
that the user copied from ChatGPT back into the Workbench with provenance.

The repository side exposes a tunnel-ready Streamable HTTP `/mcp` endpoint
with only `search` and `fetch`. It can read reviewed Knowledge, visible
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
7. Show `Context copied · paste in ChatGPT` without obscuring reading.

The composer text is not cleared. Failure to copy prevents the browser launch,
so the user is never sent to an empty handoff with false success feedback.

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

Imported text is local evidence from another chat, not trusted Knowledge.

### ChatGPT connector

The connector follows the standard read-only search/fetch shape:

```text
search({ query })
  -> candidates with stable id, title, canonical URL, authority and review state

fetch({ id })
  -> complete model-facing text plus the same provenance fields
```

Both tools carry read-only/destructive/open-world annotations. Tool results
return the same JSON in `structuredContent` and a text content block.

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
  paper: {
    title: string;
    creators: string;
    year: string;
    doi: string;
    url: string;
  } | null;
  page: {
    pageNumber: number;
    pageLabel: string;
    excerpt: string;
    source: string;
  } | null;
  selection: {
    text: string;
    pageNumber: number | null;
  } | null;
  secondaryPapers: Array<{
    title: string;
    creators: string;
    year: string;
    doi: string;
    url: string;
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

### Persistence

Capsules are stored below:

```text
<Zotero profile>/zotkit/companion-capsules/<opaque-id>.json
```

The directory is private (`0700`) and files are private (`0600`) where the
host supports POSIX permissions. Writes are atomic. A stored hash is verified
on load. Invalid schema, tampering, oversized data, and path-shaped IDs fail
closed. Capsules expire after 30 days and can be explicitly deleted.

No capsule ID grants MCP access to the Zotero profile. The bounded capsule
content is placed directly in the clipboard prompt; the repository MCP remains
physically unable to read Zotero-private files.

## Prompt format

The copied prompt has four visible parts:

1. the user's exact question;
2. frozen paper/page/selection/secondary-paper/Draft context;
3. trust labels and truncation warnings;
4. MCP retrieval instructions.

It tells ChatGPT to search reviewed Knowledge first, use Literature only as
external evidence, identify open Problems separately, and never substitute a
Draft for a reviewed conclusion. It includes the capsule ID and content hash
for provenance, but makes no claim that ChatGPT can fetch the capsule by ID.

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

- `knowledge:<versioned opaque resolver selection>`
- `problem:<validated problem id>`
- `literature:<validated citekey>`

Knowledge IDs never encode a directly readable repository path. `fetch`
decodes the versioned resolver selection and reruns the resolver, including its
ambiguity validation. A match returns every file in
`bundle.orderedFiles`, in resolver order, so inherited trusted context is not
lost.

Problem search hides rejected and archived records. Literature returns only
validated bibliographic metadata and labels it
`authority: external_evidence`; it does not expose `.raw/`, `.figures/`,
attachment paths, abstracts from private Zotero data, or paper full text.

### URLs and deployment boundary

Every result has a canonical URL derived from a validated
`QLAB_COMPANION_PUBLIC_BASE_URL`. The local server binds to
`127.0.0.1` by default and exposes `POST /mcp`. It is not added to the
existing public Worker because current domain modules depend on the local
repository filesystem.

The implementation is tunnel-ready, not silently deployed. The README requires
HTTPS, authentication at the tunnel/reverse-proxy boundary, and an explicitly
read-only repository mirror or filesystem permissions before remote use. The
server registers no shell, write, render, Git, or arbitrary-file tools.

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

The action is available only on a live Workbench conversation, not on imported
read-only ChatGPT history. It remains disabled when no question is present.

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
- opaque IDs, schema/hash/tamper validation, atomic/private persistence,
  expiry and delete;
- prompt contains exact question and provenance, never hidden state;
- copy succeeds before URL launch;
- failed copy prevents launch;
- explicit clipboard import labels provenance and rejects blank/oversized text;
- Workbench composer action renders, disables, and emits the correct callback;
- existing plain `Open ChatGPT` and imported-history behavior remain intact.

### MCP

- initialize, `tools/list`, `search`, and `fetch` over Streamable HTTP;
- tool schemas, annotations, structured/text result parity;
- full ordered Knowledge bundle, ambiguity, no-match, and invalid selection;
- hidden Problem states and immutable returned objects;
- Literature metadata-only result with external authority;
- invalid/oversized/tampered IDs and traversal attempts;
- canonical URL validation;
- before/after repository tree hash proving the service is read-only.

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
- No automatic deployment, tunnel creation, OAuth server, or secret storage in
  this slice.
- No macOS-native completion claim from the Linux development host.

## Acceptance criteria

1. From a live Workbench, one explicit action persists a frozen safe capsule,
   copies a trust-labelled prompt, and opens ChatGPT only after the copy.
2. A changed Reader selection, page, paper, or Draft does not change the saved
   capsule or copied prompt.
3. The user can explicitly import copied ChatGPT text and sees unambiguous
   provenance.
4. The local MCP server offers only read-only `search` and `fetch`, with
   reviewed Knowledge, visible Problems, and external Literature kept distinct.
5. Draft content appears only in the explicit clipboard handoff, labelled
   unreviewed; it never enters MCP search/fetch.
6. Focused tests, TypeScript checks, build, and all environment-supported tests
   pass on Linux; macOS/native Zotero visual validation is reported as deferred.
