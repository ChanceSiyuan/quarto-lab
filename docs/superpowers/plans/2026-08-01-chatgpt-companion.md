# Zotero ChatGPT Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe ChatGPT web handoff to the Zotero Workbench and a tunnel-ready, strictly read-only QLab MCP `search`/`fetch` server, so ChatGPT can discuss the same explicit paper/Knowledge/Draft context without sharing Codex usage.

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
- No MCP shell, file-write, render, Git, Zotero mutation, assessment, or autoresearch tools.
- Bind MCP to `127.0.0.1` by default; no automatic tunnel or deployment.
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

- exact question, paper, page, selection, secondary-paper, Draft, and screenshot
  provenance mapping;
- deep immutability after mutating every source object;
- Unicode-aware caps and explicit truncation warnings;
- `authority: "unreviewed_draft"`;
- absence of `pdfPath`, workspace roots, PDF text references, raw images/data
  URLs, abstract/full-text fields, environment values, and hidden instructions;
- opaque ID shape, timestamp, bounds, and deterministic content hash.

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

Normalize strings with NFKC, replace null/control characters, count Unicode
code points, clone all nested data, freeze recursively, and hash canonical JSON
that excludes `contentHash`. Reject blank/over-limit questions rather than
silently producing an unusable handoff.

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
schema/hash verification on load, unknown/path-shaped IDs, tamper rejection,
30-day expiry, explicit delete, and no mutation of returned values.

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
profile-relative target, and never accepts a caller-provided path.

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
- local provenance entry conversion.

- [ ] **Step 1: Write failing prompt tests**

Assert:

- exact user question appears once and first;
- capsule ID/hash and every included source have visible provenance;
- reviewed Knowledge, external Literature, open Problems, and unreviewed Drafts
  have distinct instructions;
- prompt asks for `search` then `fetch` and says when no reviewed match exists;
- no absolute path, raw image, hidden prompt, or unsupported claim that the MCP
  can fetch a Zotero capsule;
- final prompt remains below 48,000 characters with explicit truncation.

- [ ] **Step 2: Write failing import tests**

Reject blank text and text above 64,000 characters. A valid import yields one
status/provenance entry and one assistant entry with stable IDs derived from the
capsule/import identity; it must not look like a Codex tool result.

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
}

interface SidebarState {
  companionStatus?: { kind: "idle" | "success" | "error"; message: string };
}
```

- [ ] **Step 1: Write failing DOM tests**

For `surface: "workbench"` assert:

- `Ask in ChatGPT ↗` renders beside model/effort controls;
- it is absent from the compact Reader sidebar unless explicitly enabled;
- it is disabled for blank text, non-ready phase, running turns, and imported
  read-only history;
- click passes trimmed composer text without clearing it;
- `Import copied answer` emits only its explicit callback;
- success/error feedback is accessible and does not replace unrelated status;
- existing Enter-to-Codex, Send, history `Open ChatGPT`, tags/actions, and
  model menu still work.

- [ ] **Step 2: Run RED**

```bash
cd integrations/zotero
npx vitest run test/sidebar.test.ts
```

- [ ] **Step 3: Implement semantic controls and Apple-like CSS**

Use an actual button with a full accessible name. At narrow container widths,
hide only the visible label, retaining the tooltip/aria label. Do not add a
modal, sidebar, or iframe.

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
- Modify: `integrations/zotero/src/conversation-papers.ts` only if a safe
  public metadata snapshot helper is required
- Test: `integrations/zotero/test/plugin-state.test.ts`
- Test: `integrations/zotero/test/plugin-helpers.test.ts`
- Test: `integrations/zotero/test/plugin-research-actions.test.ts`

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

Use injected store/clipboard/launcher/readDraft seams. Assert ordering and
failure rules:

- persistence completes before copy;
- copy succeeds before launch;
- copy failure never launches;
- launch failure leaves a success message that the prompt is copied;
- Reader/Draft changes after click cannot retarget the capsule;
- active Draft is read through the existing safe repository path and capped;
- an unreadable Draft adds a warning without leaking a path;
- no active paper and no Draft still produces a question-only capsule;
- import reads the clipboard only on click and appends provenance-labelled local
  entries;
- imported entries are scoped to the current live paper/thread and do not
  contaminate imported-history or another paper.

- [ ] **Step 2: Run RED**

```bash
cd integrations/zotero
npx vitest run test/plugin-state.test.ts test/plugin-helpers.test.ts test/plugin-research-actions.test.ts
```

- [ ] **Step 3: Implement minimal orchestration**

Construct the store once at plugin startup. Reuse `ReaderContext`,
`ConversationPaperRegistry`, `activeDraftPath`, `safeRepositoryPath()`,
`copyToClipboard()`, and `launchURL()`; do not add a second Reader capture
or arbitrary file reader.

Merge imported Companion entries only at render time. Keep them separate from
Codex app-server entries and attach explicit provenance.

- [ ] **Step 4: Run GREEN and integration checks**

```bash
cd integrations/zotero
npx vitest run test/chatgpt-companion*.test.ts test/plugin-state.test.ts test/plugin-helpers.test.ts test/plugin-research-actions.test.ts test/sidebar.test.ts
npm run check
npm run build
```

- [ ] **Step 5: Commit**

```bash
git add integrations/zotero/src/plugin.ts integrations/zotero/src/conversation-papers.ts integrations/zotero/test/plugin-state.test.ts integrations/zotero/test/plugin-helpers.test.ts integrations/zotero/test/plugin-research-actions.test.ts
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

Test versioned base64url round-trip and rejection of unknown namespace/version,
malformed JSON/base64, over-limit IDs, path separators/traversal, invalid
problem IDs/citekeys, and tampered Knowledge selections.

- [ ] **Step 2: Write failing domain tests using a temporary repository**

Cover:

- Knowledge match returns a candidate whose fetch reruns the resolver and
  concatenates every `bundle.orderedFiles` in order;
- ambiguous Knowledge returns every candidate and requires a validated
  selection;
- no-match never falls back to Draft/Literature;
- any query cannot search `drafts/`;
- Problems hide rejected/archived and return clone-safe public manifest fields;
- Literature searches validated title/author/year/DOI/arXiv/method metadata,
  carries `authority: external_evidence`, and contains no raw/figure/full-text
  paths or bodies;
- search/fetch leave a before/after repository hash unchanged.

- [ ] **Step 3: Run RED**

```bash
node --import tsx --test .research-loop/tests/agent/companion-context.test.ts
```

- [ ] **Step 4: Implement retrieval behind injected existing domain functions**

Validate `repoRoot`, bibliography location, result caps, query size, and
`PUBLIC_BASE_URL`. A Knowledge fetch may read only the ordered paths returned
by a fresh successful resolver call and must confirm containment below
`knowledge/`.

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
- only `POST /mcp`/required protocol methods;
- JSON/body/query/result limits;
- invalid content type and unknown path;
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
  openWorldHint: false,
}
```

Default host is `127.0.0.1`; reject a non-loopback bind unless an explicit
unsafe-development acknowledgement is present. Require a valid
`QLAB_COMPANION_PUBLIC_BASE_URL` before serving canonical results.

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
- Developer Mode connector setup at `https://<host>/mcp`;
- HTTPS and authentication/reverse-proxy requirement;
- `reviewed != literature != problem != draft`;
- no Draft search via MCP;
- loopback launch command and required public base URL;
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
trust separation, and protocol compliance. Fix every Important/Critical issue
with a new failing test first.

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
