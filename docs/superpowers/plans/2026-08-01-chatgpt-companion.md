# Zotero ChatGPT Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe ChatGPT web handoff to the Zotero Workbench and a tunnel-ready, strictly read-only QLab MCP `search`/`fetch` server, so ChatGPT can discuss the same explicit paper/live-Knowledge/Draft context without making a Codex request or consuming a Codex turn.

**Architecture:** The Zotero plugin freezes one bounded, trust-labelled context capsule in its private profile, copies an inline handoff prompt, and opens ChatGPT only after clipboard success. It never automates the browser. A separate repository process exposes only read-only MCP `search` and `fetch`, backed by the existing Knowledge resolver, Problem repository, and Literature parser. Draft excerpts travel only through the explicit clipboard handoff and are never searchable through MCP.

**Tech Stack:** TypeScript 5.9/7, Zotero 9 privileged Gecko APIs, Node 22, `@modelcontextprotocol/sdk@1.30.0`, `zod@4.4.3`, Streamable HTTP, Node test runner, Vitest 4, Happy DOM, esbuild.

## Global constraints

- Work only in `/home/chance/quarto-lab/.worktrees/zotero-fix-pack-b` on `fix/zotero-fix-pack-b`.
- Never touch or commit the dirty `main` checkout.
- Every source change starts with a failing focused test.
- Preserve `knowledge/ != drafts/ != literature/ != problems/` physically and semantically.
- Never expose Drafts through MCP. A visible Draft excerpt may appear only in the explicit clipboard prompt and must be labelled unreviewed.
- Never include absolute paths, PDF full text, raw screenshots, cookies, environment values, hidden prompts, or full conversation history in a capsule.
- Never read ChatGPT cookies, automate its DOM, scrape streams, or claim ChatGPT Pro is an API model.
- ChatGPT is a separate handoff action, not an entry in the local Codex model picker.
- Companion input/handoff/import remain available when Codex is signed out,
  disconnected, unavailable, or has no thread, and never call a Codex
  login/thread/turn/send API.
- No MCP shell, file-write, render, Git, Zotero mutation, assessment, or autoresearch tools.
- Bind MCP to `127.0.0.1` by default; no automatic tunnel or deployment.
- Remote startup requires an access token and an OS-level read-only repository
  mirror/mount; a named writable-root override exists for tests only.
- MCP endpoint configuration and canonical content-base configuration are
  separate; token material never enters results, clipboard prompts, or logs.
- The Zotero capsule is frozen, while MCP Knowledge is explicitly live at
  retrieval time and reports the revision/hashes it used.
- Use existing QLab tokens/system fonts and keep the Workbench transcript and composer unobscured.
- Linux deterministic verification is required; macOS/native Zotero visual verification remains deferred.

---

## Task 1: Pure immutable Companion capsule

**Files:**
- Create: `integrations/zotero/src/chatgpt-companion-capsule.ts`
- Test: `integrations/zotero/test/chatgpt-companion-capsule.test.ts`

**Produces:**
- `CompanionCapsuleInput`
- `ChatGPTCompanionCapsule`
- `buildCompanionCapsule()`
- `verifyCompanionCapsule()`
- exported deterministic bounds

- [ ] **Step 1: Write failing builder tests**

Cover:

- an exact, non-normalized question and an ordered snapshot of every effective context chip,
  including included/supported/omitted state and source identity;
- removed paper/page suppression, opt-in selection, annotation/library omission
  warnings, secondary-paper retrieval/full mode, Draft, and screenshot
  provenance mapping;
- `authority: "external_evidence"` on paper/page/selection/secondary/screenshot
  material and `authority: "unsupported"` on omitted chip requests;
- deep immutability after mutating every source object;
- Unicode-aware caps and explicit truncation warnings;
- `authority: "unreviewed_draft"`;
- absence of `pdfPath`, workspace roots, PDF text references, raw images/data
  URLs, abstract/full-text fields, environment values, and hidden instructions;
- opaque ID shape, timestamp, bounds, and deterministic corruption checksum
  over canonical JSON.

Use injected `id`, `now`, and `hash` functions so the test has no Gecko
dependency.

- [ ] **Step 2: Run RED**

Run:

```bash
cd integrations/zotero
npx vitest run test/chatgpt-companion-capsule.test.ts
```

Expected: FAIL because the capsule module does not exist.

- [ ] **Step 3: Implement the smallest pure builder**

Preserve an accepted question exactly: validate but never trim, NFKC-normalize,
or truncate it, and reject blank-only text, NUL/disallowed controls, or more
than 8,000 Unicode code points. Normalize bounded context metadata with NFKC,
replace its null/control characters, clone all nested data, freeze recursively
before asynchronous work, and checksum canonical JSON that excludes
`contentHash`.

- [ ] **Step 4: Run GREEN**

Run the focused test and `npm run check` in `integrations/zotero`.

- [ ] **Step 5: Commit**

```bash
git add integrations/zotero/src/chatgpt-companion-capsule.ts integrations/zotero/test/chatgpt-companion-capsule.test.ts
git commit -m "feat(zotero): freeze ChatGPT companion context"
```

---

## Task 2: Private capsule store and explicit clipboard import

**Files:**
- Create: `integrations/zotero/src/chatgpt-companion-store.ts`
- Modify: `integrations/zotero/src/platform.ts`
- Test: `integrations/zotero/test/chatgpt-companion-store.test.ts`
- Test: `integrations/zotero/test/platform.test.ts`

**Produces:**
- injected `CompanionCapsuleStorage` interface;
- Gecko profile adapter under
  `profilePath("companion-capsules")`;
- `save/load/delete/pruneExpired`;
- synchronous privileged clipboard read helper used only by a user click.

- [ ] **Step 1: Write failing store tests**

Test atomic temp-to-final writes, `0700` directory/`0600` file requests,
schema/checksum verification on load, unknown/path-shaped IDs, checksum
mismatch rejection, 30-day expiry, explicit delete, and no mutation of
returned values. Treat the checksum only as corruption detection, never as an
authentication MAC.

- [ ] **Step 2: Write failing clipboard tests**

Test privileged `nsIClipboard` Unicode reads, an unavailable fallback, and
that no clipboard read happens until the helper is explicitly called.

- [ ] **Step 3: Run RED**

```bash
cd integrations/zotero
npx vitest run test/chatgpt-companion-store.test.ts test/platform.test.ts
```

- [ ] **Step 4: Implement store and clipboard seam**

The store receives all filesystem operations by injection. The Gecko adapter
uses `IOUtils.writeJSON`/move semantics where available, validates the exact
profile-relative target, and never accepts a caller-provided path. Persist only
capsules: imported ChatGPT answers remain a session-local UI overlay and are
never written by this store.

- [ ] **Step 5: Run GREEN and commit**

```bash
cd integrations/zotero
npx vitest run test/chatgpt-companion-store.test.ts test/platform.test.ts
npm run check
git add src/chatgpt-companion-store.ts src/platform.ts test/chatgpt-companion-store.test.ts test/platform.test.ts
git commit -m "feat(zotero): persist companion handoffs privately"
```

---

## Task 3: Handoff prompt and imported-answer model

**Files:**
- Create: `integrations/zotero/src/chatgpt-companion.ts`
- Test: `integrations/zotero/test/chatgpt-companion.test.ts`

**Produces:**
- `buildChatGPTCompanionPrompt(capsule)`;
- `importCompanionAnswer(text, capsule)`;
- local provenance entry conversion with explicit
  `origin: "chatgpt-companion"`.

- [ ] **Step 1: Write failing prompt tests**

Assert:

- fixed safety/trust instructions precede all delimited user-controlled data;
- the exact accepted user question appears once, is never truncated, and is
  rejected by the capsule builder rather than shortened when over 8,000 Unicode
  code points;
- capsule ID/checksum and every included source have visible provenance;
- current-paper context/external Literature, reviewed Knowledge, open Problems,
  and unreviewed Drafts have distinct instructions;
- prompt asks for `search` then `fetch` and says when no reviewed match exists;
- paper, page, selection, Draft, warning, and future MCP content are delimited as
  untrusted data whose embedded instructions must never be executed;
- no absolute path, raw image, hidden prompt, or unsupported claim that the MCP
  can fetch a Zotero capsule;
- the deterministic 48,000-character budget first reserves safety text, the
  exact question, capsule/checksum, primary-paper metadata, all provenance, and
  all bounded omission/truncation warnings; only the remainder is allocated to
  selection, current page, Draft, and secondary-paper identities, so optional
  bodies can never crowd out a warning.

- [ ] **Step 2: Write failing import tests**

Reject blank text and text above 64,000 characters. A valid import yields one
status/provenance entry and one assistant entry with stable IDs derived from the
capsule ID/checksum and import identity; it must not look like a Codex tool
result. The assistant entry itself carries the visible label `Imported from
ChatGPT · user copied`, capsule ID/checksum, and a non-Codex origin/avatar
contract. The returned entries are explicitly session-only and contain no
serialization/persistence instruction.

- [ ] **Step 3: Run RED**

```bash
cd integrations/zotero
npx vitest run test/chatgpt-companion.test.ts
```

- [ ] **Step 4: Implement and run GREEN**

Keep prompt construction pure; do not read files, clipboard, or globals in this
module.

- [ ] **Step 5: Commit**

```bash
git add integrations/zotero/src/chatgpt-companion.ts integrations/zotero/test/chatgpt-companion.test.ts
git commit -m "feat(zotero): build safe ChatGPT handoffs"
```

---

## Task 4: Workbench Companion UI contract

**Files:**
- Modify: `integrations/zotero/src/sidebar.ts`
- Modify: `integrations/zotero/src/styles.css`
- Test: `integrations/zotero/test/sidebar.test.ts`

**Interface additions:**

```ts
interface SidebarCallbacks {
  onOpenChatGPTCompanion?(question: string): void;
  onImportChatGPTCompanionAnswer?(): void;
  onSelectChatGPTCompanionHandoff?(capsuleId: string): void;
}

interface SidebarState {
  companionStatus?: { kind: "idle" | "success" | "error"; message: string };
  pendingCompanionHandoffs?: Array<{
    capsuleId: string;
    questionPreview: string;
    createdAt: string;
    selected: boolean;
  }>;
}

interface ChatEntry {
  origin?: "codex" | "chatgpt-companion";
  originLabel?: string;
  companionProvenance?: { capsuleId: string; capsuleChecksum: string };
}
```

- [ ] **Step 1: Write failing DOM tests**

For `surface: "workbench"` assert:

- `Ask in ChatGPT ↗` renders beside model/effort controls;
- it is absent from the compact Reader sidebar unless explicitly enabled;
- it remains enabled for a valid question when Codex is signed out,
  disconnected, unavailable, or has no active thread;
- in those states the textarea remains reachable while the Codex model, effort,
  Send, and turn-only controls stay disabled, and Enter never emits a Codex
  send;
- it is disabled for blank text, running handoffs, and imported read-only
  history;
- click validates blankness but passes the original composer text without
  trimming, normalization, or clearing it;
- `Import copied answer` is disabled with no selected pending handoff and emits
  only its explicit callback when enabled;
- each pending choice visibly identifies question/time/short capsule ID, the
  newest defaults selected, and selecting an older handoff emits only the
  explicit selection callback;
- an imported assistant entry with `origin: "chatgpt-companion"` displays
  `Imported from ChatGPT · user copied` on that row and never renders the Codex
  avatar or `alt="Codex"`;
- success/error feedback is accessible and does not replace unrelated status;
- Companion click/import never emits login, start-thread, new-thread,
  switch-thread, or Codex send callbacks;
- existing Enter-to-Codex, Send, history `Open ChatGPT`, tags/actions, and
  model menu still work when Codex is ready.

- [ ] **Step 2: Run RED**

```bash
cd integrations/zotero
npx vitest run test/sidebar.test.ts
```

- [ ] **Step 3: Implement semantic controls and Apple-like CSS**

Use an actual button with a full accessible name. Make the Codex login/unready
layer leave the Companion composer reachable while guarding every Codex-only
control. At narrow container widths, hide only the visible label, retaining the
tooltip/aria label. Do not add a modal, sidebar, or iframe.

- [ ] **Step 4: Run GREEN plus visual fixture test**

```bash
cd integrations/zotero
npx vitest run test/sidebar.test.ts
npm run test:visual
npm run check
```

- [ ] **Step 5: Commit**

```bash
git add integrations/zotero/src/sidebar.ts integrations/zotero/src/styles.css integrations/zotero/test/sidebar.test.ts
git commit -m "feat(zotero): add ChatGPT companion controls"
```

---

## Task 5: Plugin orchestration and frozen source capture

**Files:**
- Modify: `integrations/zotero/src/plugin.ts`
- Modify: `integrations/zotero/src/qmd-workspace.ts` only if exposing the
  already-loaded `{source, revision}` snapshot is required
- Modify: `integrations/zotero/src/conversation-papers.ts` only if a safe
  public metadata snapshot helper is required
- Test: `integrations/zotero/test/plugin-state.test.ts`
- Test: `integrations/zotero/test/plugin-helpers.test.ts`
- Test: `integrations/zotero/test/plugin-research-actions.test.ts`
- Test: `integrations/zotero/test/qmd-workspace.test.ts` only if the workspace
  snapshot seam changes

**Flow:**

```text
explicit click
  -> snapshot current Reader/context chips/visible Draft
  -> build + persist capsule
  -> build prompt
  -> copy prompt
  -> launch https://chatgpt.com/
  -> render success/error
```

- [ ] **Step 1: Write failing orchestration tests**

Use injected store/clipboard/launcher/cached-Draft/revalidation seams. Assert
ordering and failure rules:

- the exact ordered `contextChips()` set, its backing values, and the
  last-known active Draft `{relativePath, revision, source}` are deep-cloned
  synchronously before persistence, clipboard, launch, or any other await;
- Draft inclusion rereads only the same safe repository-relative path and
  compares its revision to the click-time snapshot; missing snapshots, path
  changes, or revision mismatches omit the body with an explicit warning rather
  than substituting later content;
- removed paper/page chips suppress payloads, selection is opt-in, requested
  annotations/library become explicit unsupported warnings, secondary papers
  preserve retrieval/full mode with metadata only, and screenshots include
  region provenance but no pixels;
- persistence completes before copy;
- copy succeeds before launch;
- copy failure never launches;
- launch failure leaves a success message that the prompt is copied;
- Reader/Draft changes after click cannot retarget the capsule;
- the active Draft snapshot is maintained on workspace open/reload/save, read
  through the existing safe repository path, revision-checked, and capped;
- an unreadable Draft adds a warning without leaking a path;
- no active paper and no Draft still produces a question-only capsule;
- handoff/import in signed-out, disconnected, unavailable, and no-thread states
  invoke no Codex login/start/send/new/switch callback or API;
- success feedback says `Context copied · paste in a ChatGPT chat with the QLab
  app enabled`;
- every successful handoff appends a bounded pending record for its captured
  subject, newest-selected by default; two handoffs can coexist and the older
  one can be selected explicitly before import;
- import reads the clipboard only on click and appends provenance-labelled
  session-local entries linked to the capsule ID/checksum;
- successful import consumes only its selected pending record and leaves other
  pending handoffs selectable;
- imported entries are kept in a plugin-owned overlay scoped to their captured
  paper/Draft/question-only subject, merge only at render time, never mutate a
  Codex thread, never contaminate imported history or another subject, and are
  not restored after plugin restart.

- [ ] **Step 2: Run RED**

```bash
cd integrations/zotero
npx vitest run test/plugin-state.test.ts test/plugin-helpers.test.ts test/plugin-research-actions.test.ts test/qmd-workspace.test.ts
```

- [ ] **Step 3: Implement minimal orchestration**

Construct the store once at plugin startup. Maintain the active Draft's
last-known source/revision through existing workspace read/save seams. Snapshot
effective chip order, backing values, and that cached Draft before the first
asynchronous operation; then revalidate the Draft revision and fail closed to a
warning on mismatch. Reuse `ReaderContext`, `ConversationPaperRegistry`,
`activeDraftPath`, `safeRepositoryPath()`, `copyToClipboard()`, and
`launchURL()`; do not add a second Reader capture or arbitrary file reader.

Merge imported Companion entries only at render time. Keep them separate from
Codex app-server entries and attach explicit provenance.

- [ ] **Step 4: Run GREEN and integration checks**

```bash
cd integrations/zotero
npx vitest run test/chatgpt-companion*.test.ts test/plugin-state.test.ts test/plugin-helpers.test.ts test/plugin-research-actions.test.ts test/qmd-workspace.test.ts test/sidebar.test.ts
npm run check
npm run build
```

- [ ] **Step 5: Commit**

```bash
git add integrations/zotero/src/plugin.ts integrations/zotero/src/qmd-workspace.ts integrations/zotero/src/conversation-papers.ts integrations/zotero/test/plugin-state.test.ts integrations/zotero/test/plugin-helpers.test.ts integrations/zotero/test/plugin-research-actions.test.ts integrations/zotero/test/qmd-workspace.test.ts
git commit -m "feat(zotero): connect frozen context to ChatGPT"
```

---

## Task 6: Versioned read-only MCP IDs and retrieval module

**Files:**
- Create: `src/lib/companion/ids.ts`
- Create: `src/lib/companion/context.ts`
- Test: `.research-loop/tests/agent/companion-context.test.ts`

**Public interface:**

```ts
export interface CompanionContext {
  search(query: string): Promise<readonly CompanionSearchResult[]>;
  fetch(id: string): Promise<CompanionDocument>;
}
```

- [ ] **Step 1: Write failing ID/security tests**

Test versioned base64url round-trip whose decoded Knowledge payload contains
only `{version, namespace, query, selectionDigest}` and never a selected page or
repository path. Reject unknown namespace/version, malformed JSON/base64,
over-limit IDs, path separators/traversal in direct namespaces, invalid problem
IDs/citekeys, stale/unknown digests, digest collisions, and modified Knowledge
selections.

- [ ] **Step 2: Write failing domain tests using a temporary repository**

Cover:

- Knowledge match returns a candidate whose fetch reruns the resolver and
  concatenates every `bundle.orderedFiles` in order;
- ambiguous Knowledge returns every candidate with a digest-only selection and
  fetch reruns resolution to require one unique currently valid digest match;
- no-match never falls back to Draft/Literature;
- any query cannot search `drafts/`;
- Problems hide rejected/archived and return clone-safe public manifest fields;
- a guessed ID for a rejected/archived Problem is denied by the same shared
  visibility predicate and produces the same not-found result as an unknown ID;
- Literature searches validated title/author/year/DOI/arXiv/method metadata,
  carries `authority: external_evidence`, and contains no raw/figure/full-text
  paths or bodies;
- each Knowledge fetch reports the live repository revision plus hashes for the
  exact ordered files read, and a repository edit after capsule creation is
  reflected as a new live retrieval rather than a frozen-snapshot claim;
- search/fetch leave a before/after repository hash unchanged as regression
  evidence, not as a proof against every possible write path.

- [ ] **Step 3: Run RED**

```bash
node --import tsx --test .research-loop/tests/agent/companion-context.test.ts
```

- [ ] **Step 4: Implement retrieval behind injected existing domain functions**

Validate `repoRoot`, bibliography location, result caps, query size, and the
credential-free `QLAB_COMPANION_PUBLIC_BASE_URL`. Reject userinfo, query,
fragment, access-token text, and capability paths in the content base. Use one
`isCompanionVisibleProblem` predicate for both
search and fetch. Knowledge IDs encode the bounded query plus only a digest of
candidate identity; fetch reruns resolution and matches that digest before it
may read the ordered paths returned by the fresh successful resolver call. It
must confirm containment below `knowledge/` and compute revision/file hashes
from the content it actually returns.

- [ ] **Step 5: Run GREEN, lint, and type-check**

```bash
node --import tsx --test .research-loop/tests/agent/companion-context.test.ts
npx tsc --noEmit
npx eslint src/lib/companion .research-loop/tests/agent/companion-context.test.ts
```

- [ ] **Step 6: Commit**

```bash
git add src/lib/companion .research-loop/tests/agent/companion-context.test.ts
git commit -m "feat(mcp): add trust-aware read-only context"
```

---

## Task 7: Streamable HTTP MCP server

**Files:**
- Create: `src/lib/companion/server.ts`
- Create: `.research-loop/tooling/scripts/companion-mcp.ts`
- Create: `.research-loop/tests/agent/companion-mcp.test.ts`
- Modify: `package.json`
- Modify: `package-lock.json`

- [ ] **Step 1: Install exact dependencies**

```bash
npm install --save-exact @modelcontextprotocol/sdk@1.30.0 zod@4.4.3
```

Confirm the lockfile contains exactly those direct versions.

- [ ] **Step 2: Write failing in-memory MCP tests**

Assert server instructions, `tools/list`, exact input/output schemas, tool
annotations, error conversion, and identical JSON in `structuredContent` and
the text content block.

- [ ] **Step 3: Write failing loopback Streamable HTTP tests**

Start on an ephemeral `127.0.0.1` port and use the SDK client to cover:

- `initialize`;
- `tools/list`;
- `search`;
- `fetch`;
- only the token-bearing MCP path and required protocol methods;
- missing, short, or incorrect tokens return the same not-found response as an
  unknown path and reveal no tool/document state;
- endpoint base and public content base are separately required and validated;
  token text never appears in structured/text results, canonical URLs, copied
  prompt fixtures, or captured logger calls;
- JSON/body/query/result limits;
- invalid content type and unknown path;
- production startup refuses a repository root writable by the service user;
- the named writable-root developer override is accepted only when explicitly
  enabled for tests/local development;
- a simulated remote client can initialize and call both tools through the
  authenticated loopback route, including explicit trusted-tunnel mode;
- graceful shutdown and abandoned-session cleanup;
- no mutation of the repository fixture.

- [ ] **Step 4: Run RED**

```bash
node --import tsx --test .research-loop/tests/agent/companion-mcp.test.ts
```

- [ ] **Step 5: Implement server and executable**

Use `McpServer` and `StreamableHTTPServerTransport`. Register exactly
`search` and `fetch` with:

```ts
{
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: false,
}
```

Default host is `127.0.0.1`; reject a non-loopback bind unless an explicit
unsafe-development acknowledgement is present. Require distinct validated
`QLAB_COMPANION_ENDPOINT_BASE_URL` and
`QLAB_COMPANION_PUBLIC_BASE_URL` values; neither may contain userinfo, query,
fragment, or the access token, and only the public content base may construct
result URLs. Derive the route from a minimum-32-byte
`QLAB_COMPANION_ACCESS_TOKEN`, compare it without leaking mismatch detail, and
never log a token-bearing request target. Require an injected OS-level
read-only-root check in production; permit a clearly named developer-only
writable-root override for tests. Trusted-tunnel mode requires an explicit
opt-in and still binds the origin service to loopback.

- [ ] **Step 6: Add scripts and run GREEN**

Add:

```json
"companion:mcp": "node --import tsx .research-loop/tooling/scripts/companion-mcp.ts"
```

Run focused tests, `npm run lint`, and `npm run build:app`.

- [ ] **Step 7: Commit**

```bash
git add src/lib/companion/server.ts .research-loop/tooling/scripts/companion-mcp.ts .research-loop/tests/agent/companion-mcp.test.ts package.json package-lock.json
git commit -m "feat(mcp): serve QLab context over read-only HTTP"
```

---

## Task 8: Operator and user documentation

**Files:**
- Modify: `integrations/zotero/README.md`
- Modify: `integrations/zotero/CHANGELOG.md`
- Modify: `integrations/zotero/manifest.json`
- Modify: `integrations/zotero/package.json`
- Modify: `integrations/zotero/package-lock.json`
- Create: `docs/chatgpt-companion.md`
- Modify: `README.md` only for a short discoverability link

- [ ] **Step 1: Write documentation assertions first**

Add or extend a lightweight test that checks the docs contain:

- the no-cookie/no-DOM boundary;
- `Ask in ChatGPT ↗` and explicit paste/import steps;
- signed-out/unavailable Companion behavior and the guarantee that it makes no
  Codex request or turn;
- Developer Mode QLab app setup at a token-bearing
  `https://<host>/<capability-path>` endpoint, plus the requirement to enable
  the app in the destination chat;
- separate endpoint-base and credential-free public-content-base variables,
  with the guarantee that token material never enters citations, prompts, or
  logs;
- the fact that localhost cannot be connected directly, with OpenAI Secure MCP
  Tunnel when available or a user-managed authenticated HTTPS reverse tunnel
  as supported operator paths;
- HTTPS, minimum token, rotation, request-target logging, trusted-tunnel, and
  reverse-proxy requirements;
- production read-only mirror/mount requirements and writable-root refusal;
- `reviewed != literature != problem != draft`;
- no Draft search via MCP;
- the frozen Zotero capsule versus live Knowledge retrieval distinction,
  including returned revision/file hashes;
- loopback launch command and required endpoint base, public content base, and
  access token;
- Linux completion/macOS verification boundary.

- [ ] **Step 2: Run RED, then write docs**

Document both sides of the flow and a troubleshooting table. Do not claim that
the implementation deploys a public endpoint or bypasses ChatGPT product
limits.

- [ ] **Step 3: Version the Zotero plugin**

Raise the plugin to the next feature version consistently in package and
manifest metadata. Regenerate only its lockfile through npm.

- [ ] **Step 4: Run focused docs/version checks and commit**

```bash
git add README.md docs/chatgpt-companion.md integrations/zotero/README.md integrations/zotero/CHANGELOG.md integrations/zotero/manifest.json integrations/zotero/package.json integrations/zotero/package-lock.json
git commit -m "docs: explain the ChatGPT companion boundary"
```

---

## Task 9: Review and verification

- [ ] **Step 1: Run focused Zotero suite**

```bash
cd integrations/zotero
npx vitest run test/chatgpt-companion-capsule.test.ts test/chatgpt-companion-store.test.ts test/chatgpt-companion.test.ts test/platform.test.ts test/sidebar.test.ts test/plugin-state.test.ts test/plugin-helpers.test.ts test/plugin-research-actions.test.ts
npm run check
npm run build
```

- [ ] **Step 2: Run focused MCP suite**

```bash
cd /home/chance/quarto-lab/.worktrees/zotero-fix-pack-b
node --import tsx --test .research-loop/tests/agent/companion-context.test.ts .research-loop/tests/agent/companion-mcp.test.ts
npx tsc --noEmit
```

- [ ] **Step 3: Run full available suites**

```bash
cd integrations/zotero
npm test
npm run test:visual

cd /home/chance/quarto-lab/.worktrees/zotero-fix-pack-b
make knowledge-check
npm run lint
npm run test:unit
npm run test:unit:problems
npm run build
```

Record the already observed Linux-only `/usr/bin/zip ENOENT` starter-template
failure separately if it remains the sole failure; do not misreport it as a
Companion regression.

- [ ] **Step 4: Request two independent reviews**

One review checks the design/spec and Zotero UX; the other checks MCP security,
trust separation, authorization not-found parity, production writable-root
refusal, exact tool annotations, and protocol compliance. Both reviews verify
that signed-out Companion flows call no Codex API and that frozen Zotero context
is not confused with live Knowledge retrieval. Fix every Important/Critical
issue with a new failing test first.

- [ ] **Step 5: Inspect final diff and working tree**

```bash
git status --short
git diff --check
git log --oneline origin/fix/zotero-fix-pack-b..HEAD
```

Ensure no `.superdesign/` scratch, generated build output, Draft preview,
Knowledge output, secret, token, or unrelated main-worktree change is staged.

- [ ] **Step 6: Final integration commit only if needed**

Do not squash the test-first task commits. A final commit may contain only
version/docs/integration corrections found during verification.

- [ ] **Step 7: Push the current feature branch**

```bash
git push origin fix/zotero-fix-pack-b
```

Do not push or merge `main`. Report the remote branch, final commit IDs,
supported test evidence, Superdesign TLS limitation, and deferred macOS/native
verification.
