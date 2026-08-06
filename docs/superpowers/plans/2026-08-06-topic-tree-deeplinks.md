# Topic Tree Canvas & Zotero Deep Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let knowledge pages deep-link into Zotero (`zotero://open-pdf/...?page=N`) and render `knowledge/index.qmd`'s `qlab-tree` YAML block as a draggable SVG topic tree with per-node PDF/note hover links.

**Architecture:** The parser admits exactly the `zotero:` scheme as external. A new build module (`src/lib/knowledge/tree.ts`) extracts, validates (as `knowledge-check` diagnostics), and compiles the tree block to JSON; the projection (`quarto.ts`) emits a dependency-free ES-module runtime with the JSON substituted in and injects it via the generated `_quarto.yml`'s `header-includes`. The Zotero plugin's embedded site browser intercepts `zotero:` navigations and handles them natively, preferring the workbench PDF tab.

**Tech Stack:** TypeScript (build pipeline, node:test via tsx), plain ES-module JS runtime (no deps), existing `yaml@2.9.0`, vitest+happy-dom in `integrations/zotero`.

**Spec:** `docs/superpowers/specs/2026-08-06-topic-tree-deeplinks-design.md`

## Global Constraints

- Trusted-tree gates stay intact: `SCRIPT_FORBIDDEN`, shortcode refusal, frontmatter allowlist are untouched. Only the `zotero:` scheme is newly admitted — `javascript:` etc. keep failing with `LINK_OUTSIDE_KNOWLEDGE`.
- Knowledge tests run with `npm run test:unit` (node:test via tsx over `.research-loop/tests/**/*.test.ts`); scope runs use `node --import tsx --test .research-loop/tests/knowledge/<file>.test.ts`. Plugin tests: `cd integrations/zotero && npx vitest run`.
- Gate per task: the touched test files pass; final task runs `npm run test:unit`, `make knowledge-check`, and the plugin suite.
- `knowledge/_quarto.yml` must stay byte-equal in meaning to `FIXED_BASE_CONFIG` (`assertSafeBaseConfig` strict equality) — every fixed-config change lands in both places in the same commit.
- All new UI copy, code, comments, and the skill in English. Commits on `main`, message trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- The tree runtime is one dependency-free ES module, importable by node:test (no side effects without a DOM) and executable in the browser.

---

### Task 1: Admit the `zotero:` scheme in the knowledge parser

**Files:**
- Modify: `src/lib/knowledge/parser.ts:68` (and the doc comment at `src/lib/knowledge/types.ts:132-137`)
- Test: `.research-loop/tests/knowledge/parser.test.ts`, `.research-loop/tests/knowledge/graph-validation.test.ts`

**Interfaces:**
- Consumes: `EXTERNAL_TARGET` regex (`/^(?:https?|mailto):/i`).
- Produces: `zotero:` links never enter `page.localLinks`, so validation passes them like https. Later tasks rely on `[x](zotero://…)` being legal in any knowledge page.

**Steps:**

- [ ] **Step 1: Write failing tests.** In `parser.test.ts`, next to the existing external-target coverage (find it with `grep -n "mailto\|EXTERNAL" .research-loop/tests/knowledge/parser.test.ts`), add: a page containing `[p](zotero://open-pdf/library/items/AB12CD34?page=7)` yields no entry for that target in `localLinks`, while `[j](javascript:alert(1))` still does. In `graph-validation.test.ts`, add: a fixture page with a `zotero://select/library/items/KEY` link validates with zero diagnostics; a `vbscript:` link still reports `LINK_OUTSIDE_KNOWLEDGE`. Follow the file's existing fixture-building helpers verbatim.
- [ ] **Step 2: Run to verify failure** — `node --import tsx --test .research-loop/tests/knowledge/parser.test.ts .research-loop/tests/knowledge/graph-validation.test.ts`. Expected: the new zotero assertions fail.
- [ ] **Step 3: Implement.**

```ts
// parser.ts:68 — was /^(?:https?|mailto):/i
/** Link targets the knowledge tree does not own and never resolves on disk. */
const EXTERNAL_TARGET = /^(?:https?|mailto|zotero):/i;
```

Update the `types.ts:132-137` comment to name `zotero:` among the excluded schemes (deep links into the user's Zotero library are a sanctioned exit).
- [ ] **Step 4: Re-run both test files. Expected: PASS.**
- [ ] **Step 5: Commit** — `feat(knowledge): admit zotero: links as external targets`.

---

### Task 2: `tree.ts` — extract, validate, compile the `qlab-tree` block

**Files:**
- Create: `src/lib/knowledge/tree.ts`
- Test: `.research-loop/tests/knowledge/tree.test.ts`

**Interfaces:**
- Consumes: `yaml` package (`parse`), nothing else.
- Produces (used by Tasks 3, 5):

```ts
export interface TreeDiagnostic { code: string; message: string; line: number }
export interface CompiledTreeNode {
  id: string;              // slug of the label path, e.g. "tensor-networks/mps-dmrg"
  label: string;
  noteUrl: string | null;  // "/knowledge/TN_sim/MPS_DMRG.html" | null
  zotero: string | null;
  x: number | null;
  y: number | null;
  children: CompiledTreeNode[];
}
export interface CompiledTree { root: string; nodes: CompiledTreeNode[] }

/** Finds the ```qlab-tree fence; null when the page has none. */
export function extractTreeBlock(source: string): { yamlText: string; startLine: number } | null;

export function compileTree(input: {
  yamlText: string;
  startLine: number;               // 1-based line of the opening fence
  pages: ReadonlySet<string>;      // graph page ids (POSIX, ".qmd")
  sitePath: string;                // "/knowledge/"
}): { tree: CompiledTree | null; diagnostics: TreeDiagnostic[] };
```

Diagnostic codes (each is a test): `TREE_YAML_INVALID` (unparseable / not a mapping / `nodes` not a list), `TREE_LABEL_INVALID` (missing/empty label, or duplicate among siblings), `TREE_NOTE_MISSING` (`note` set but not in `pages`), `TREE_LINK_SCHEME` (`zotero` set but not starting `zotero://`), `TREE_COORD_INVALID` (`x`/`y` present but not finite numbers). `root` missing defaults to `"Research Knowledge"`. Compilation is deterministic: same input → deep-equal output; `noteUrl` = `sitePath + note.replace(/\.qmd$/, ".html")`; id = slugified label path (lowercase, spaces/non-alphanumerics → `-`, joined with `/`). Any diagnostic ⇒ `tree: null`.

**Steps:**

- [ ] **Step 1: Write failing tests** (node:test style — `import { test } from "node:test"; import assert from "node:assert/strict";`, matching the sibling files): extraction finds the fence and its start line; extraction returns null without one; a valid two-level block compiles with correct ids/noteUrls/nulls; each diagnostic code fires on its malformed input with the right line number; deterministic double-compile deep-equality.
- [ ] **Step 2: Run — expected FAIL** (`node --import tsx --test .research-loop/tests/knowledge/tree.test.ts`).
- [ ] **Step 3: Implement `tree.ts`** per the interface. Extraction: scan lines for `` ``` `` fences, matching an info string exactly `qlab-tree`; unclosed fence → treat as absent (the parser's `FENCE_UNCLOSED` already covers it).
- [ ] **Step 4: Run — expected PASS.**
- [ ] **Step 5: Commit** — `feat(knowledge): compile the qlab-tree topic block`.

---

### Task 3: Wire tree diagnostics into `validateGraph`

**Files:**
- Modify: `src/lib/knowledge/validate.ts` (inside `validateGraph`, `:178`)
- Modify: `src/lib/knowledge/index.ts` (re-export the tree module's public surface)
- Test: `.research-loop/tests/knowledge/graph-validation.test.ts`

**Interfaces:**
- Consumes: `extractTreeBlock`, `compileTree` (Task 2); `graph.pages`, `page.absolutePath`, the local `report(code, message, location)` helper.
- Produces: `make knowledge-check` fails on tree problems; a `qlab-tree` block on any page other than `index.qmd` reports `TREE_BLOCK_MISPLACED`. Location objects follow the file's existing `SourceLocation` shape (`{ path, line }` — confirm with `grep -n "SourceLocation" src/lib/knowledge/types.ts` and mirror it).

**Steps:**

- [ ] **Step 1: Write failing tests** in `graph-validation.test.ts`: a fixture tree with a `qlab-tree` block on `index.qmd` referencing a missing note page fails with `TREE_NOTE_MISSING`; a well-formed block validates clean; the same block on a topic page reports `TREE_BLOCK_MISPLACED`.
- [ ] **Step 2: Run — expected FAIL.**
- [ ] **Step 3: Implement.** In `validateGraph`, after the existing per-page loops: for every page, `readFile(page.absolutePath, "utf8")` (the function is already async and already reads sources for other checks — reuse the same read if one exists in scope; otherwise read here), `extractTreeBlock`; block on `id !== "index.qmd"` → `report("TREE_BLOCK_MISPLACED", …)`; block on the root index → `compileTree({...pages: new Set(graph.pages.keys()), sitePath: "/knowledge/"})` and report each diagnostic at its line.
- [ ] **Step 4: Run graph-validation + full knowledge test dir. Expected: PASS.**
- [ ] **Step 5: Commit** — `feat(knowledge): validate the topic tree block in knowledge-check`.

---

### Task 4: Tree runtime ES module

**Files:**
- Create: `src/lib/knowledge/tree-runtime.js`
- Test: `.research-loop/tests/knowledge/tree-runtime.test.ts`

**Interfaces:**
- Consumes: nothing (dependency-free ESM).
- Produces (Task 5 embeds this file verbatim with the data placeholder substituted):

```js
// First line of the file, exactly:
const TREE_DATA = /*__QLAB_TREE_DATA__*/ null;

export function autoLayout(nodes, options = { xGap: 180, yGap: 64 });
  // returns Map<id, {x, y}> — tidy tree: depth → x, subtree-centred y
export function effectivePositions(nodes, stored);
  // priority: stored (localStorage JSON) > authored x/y > autoLayout
export function serializeLayoutYaml(yamlSource, positions);
  // merges {x, y} back into the authored YAML text, returns new YAML text
export function mountTopicTree(doc, data, store);
  // builds the SVG canvas, hover cards, pan/zoom/drag, tool corner
if (typeof document !== "undefined" && TREE_DATA) {
  const ready = () => mountTopicTree(document, TREE_DATA, window.localStorage);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready);
  else ready();
}
```

Behavior contract (from the spec): canvas replaces the hidden `pre` whose class contains `qlab-tree`; hover card shows "Open PDF in Zotero" (`zotero`, grey+inert when null) and "Open note" (`noteUrl`, grey+inert when null); background drag pans, wheel zooms, node pointer-drag moves and saves `{id: {x,y}}` JSON to `store` under key `qlab-tree-layout`; "Copy layout YAML" writes `serializeLayoutYaml` output to the clipboard (fallback: shows it in a selectable `<textarea>`); "Reset layout" removes the store key and re-renders; colors come from the theme's CSS variables (plain `var(--…)` references with fallbacks).

**Steps:**

- [ ] **Step 1: Write failing tests** for the pure functions only (node:test, plain `import` of the `.js` module): `autoLayout` places a parent left of its children and centres it on them; `effectivePositions` priority order (stored beats authored beats auto); `serializeLayoutYaml` inserts `x:`/`y:` for a node that had none and updates one that had them, round-tripping through `yaml.parse` to deep-equal the expected structure.
- [ ] **Step 2: Run — expected FAIL** (module missing).
- [ ] **Step 3: Implement the module** — pure functions first, then `mountTopicTree` (untested by unit tests; exercised by the rendered site and live QA). Keep DOM access exclusively inside `mountTopicTree`.
- [ ] **Step 4: Run — expected PASS.**
- [ ] **Step 5: Commit** — `feat(knowledge): add the topic tree canvas runtime`.

---

### Task 5: Projection injection + `_quarto.yml` + theme CSS

**Files:**
- Modify: `src/lib/knowledge/quarto.ts` (`FIXED_BASE_CONFIG:440-456`, `RESERVED_FILES:92`, `materializeQuartoProject` steps 4–6 at `:855-880`)
- Modify: `knowledge/_quarto.yml` (identical fixed-config addition)
- Modify: the generated stylesheet source (`grep -n "RESEARCH_LOOP_STYLESHEET" src/lib/knowledge -r` to find it) — hide `pre` blocks whose class contains `qlab-tree`, add canvas/hover-card/tool-corner rules
- Test: `.research-loop/tests/knowledge/quarto-project.test.ts`

**Interfaces:**
- Consumes: `extractTreeBlock`/`compileTree` (Task 2), `tree-runtime.js` (Task 4).
- Produces: the projected site contains `research-loop-tree.js` (runtime with `/*__QLAB_TREE_DATA__*/ null` replaced by the compiled JSON) and every page's head loads it via `format.html.header-includes: '<script type="module" src="/knowledge/research-loop-tree.js"></script>'`. `TREE_RUNTIME_FILENAME = "research-loop-tree.js"` joins `RESERVED_FILES`.

**Steps:**

- [ ] **Step 1: Write failing tests** in `quarto-project.test.ts` (follow its existing materialize-fixture helpers): projecting a graph whose index has a valid tree block writes `research-loop-tree.js` containing the compiled JSON (assert a node label appears and the placeholder string does not); the generated `_quarto.yml` contains the `header-includes` script line; a graph **without** a tree block still writes the runtime with data `null` (the runtime no-ops — simpler than conditional injection, one less branch); `assertSafeBaseConfig` accepts the updated committed file and still rejects a stray `pre-render` key.
- [ ] **Step 2: Run — expected FAIL.**
- [ ] **Step 3: Implement.**
  - `FIXED_BASE_CONFIG.format.html` gains `"header-includes": '<script type="module" src="/knowledge/research-loop-tree.js"></script>'`.
  - `knowledge/_quarto.yml` gains the same key under `format.html` (strict equality holds).
  - In `materializeQuartoProject`, after the theme CSS write: read the index page source (already read in step 1's loop — retain it), `extractTreeBlock` + `compileTree` (diagnostics were already enforced by validation; a failure here throws `QuartoProjectionError` as a belt-and-braces guard), then `writeInto(projectDir, TREE_RUNTIME_FILENAME, runtimeSource.replace("/*__QLAB_TREE_DATA__*/ null", JSON.stringify(tree)))` — `runtimeSource` read from `src/lib/knowledge/tree-runtime.js` next to the module (`new URL("./tree-runtime.js", import.meta.url)`).
  - Stylesheet: `pre.qlab-tree, pre[class*="qlab-tree"], div.sourceCode:has(> pre code.qlab-tree) { display: none; }` plus `.qlab-tree-canvas`, `.qlab-tree-card`, `.qlab-tree-tools` rules using the theme variables.
- [ ] **Step 4: Run quarto-project tests + the whole knowledge test dir. Expected: PASS.**
- [ ] **Step 5: Commit** — `feat(knowledge): project the topic tree runtime into the site`.

---

### Task 6: Author the initial tree block in `knowledge/index.qmd`

**Files:**
- Modify: `knowledge/index.qmd` (append a `## Topic tree` section with the `qlab-tree` block after the Reading map)
- Read: `literature/zotero.yml` (collection-key → topic mapping for `zotero:` fields)

**Interfaces:**
- Consumes: the 20 Reading-map topics; `zotero://select/library/collections/<KEY>` for topics mapped in `literature/zotero.yml`; topics without a mapping omit `zotero` (grey link).
- Produces: a `knowledge-check`-clean index page rendering the first tree.

**Steps:**

- [ ] **Step 1: Read `literature/zotero.yml`** and list its collection-key → topic-slug pairs.
- [ ] **Step 2: Append the block** — one top-level node per Reading-map topic, `label` = the Reading map's link text, `note` = the topic's `index.qmd` path, `zotero` filled only for mapped topics, no coordinates (auto-layout).
- [ ] **Step 3: Run `make knowledge-check`. Expected: ok.** Fix any diagnostic it raises (that is the feature working).
- [ ] **Step 4: Render locally** — `make knowledge-preview` (spot-check by fetching the preview URL with curl and confirming the script tag + hidden block are present; interactive behavior is browser QA).
- [ ] **Step 5: Commit** — `feat(knowledge): add the topic tree block to the index`.

---

### Task 7: `edit-topic-tree` skill + contract test

**Files:**
- Create: `skills/edit-topic-tree/SKILL.md`
- Modify: `.research-loop/tests/agent/skill-contracts.test.ts` (add the entry; copy the shape of an existing small skill's contract, e.g. `render-site`)

**Interfaces:**
- Consumes: the block schema (Task 2), link forms (spec).
- Produces: a repo skill with two-key frontmatter (`name`, `description`), body sections `# Edit Topic Tree`, `## Overview`, `## Commands`, `## Workflow` — matching the repo convention.

**Steps:**

- [ ] **Step 1: Add the failing contract entry** asserting the skill file exists and mentions `` ```qlab-tree ``, `zotero://open-pdf`, `make knowledge-check`, and the rule that the Reading map remains the navigation authority.
- [ ] **Step 2: Run the agent contract tests — expected FAIL.**
- [ ] **Step 3: Write `SKILL.md`**: when to use (user asks to change the topic tree, node links, or layout); the full schema with the example block; both `zotero://` forms (`open-pdf/library/items/KEY?page=N`, `select/library/{items,collections}/KEY`, group variant); rules — English labels, `note` must resolve to an existing page or be omitted, run `make knowledge-check` after every edit, preview with `make knowledge-preview`, freeze canvas layouts by pasting the "Copy layout YAML" output over the block, the tree is presentation and the Reading map stays the navigation authority.
- [ ] **Step 4: Run the contract tests — expected PASS.**
- [ ] **Step 5: Commit** — `feat(skills): add edit-topic-tree`.

---

### Task 8: Plugin-side deep-link interception

**Files:**
- Create: `integrations/zotero/src/zotero-links.ts` (pure URI parser)
- Modify: `integrations/zotero/src/research-loop-site.ts` (cancel + delegate `zotero:` navigations)
- Modify: `integrations/zotero/src/plugin.ts` (wire the handler; reuse `focusWorkbenchPdfTab`)
- Test: `integrations/zotero/test/zotero-links.test.ts`, extend `integrations/zotero/test/research-loop-site.test.ts`

**Interfaces:**
- Produces:

```ts
// zotero-links.ts
export interface ZoteroDeepLink {
  action: "open-pdf" | "select";
  library: { kind: "user" } | { kind: "group"; groupID: number };
  objectKind: "items" | "collections";
  key: string;
  page?: number;
}
export function parseZoteroLink(spec: string): ZoteroDeepLink | null;
```

- `ResearchLoopSiteViewOptions` gains `onZoteroLink?(link: ZoteroDeepLink): void`. The view's progress listener implements `onStateChange` (STATE_START): a `zotero:` URI parsed successfully → `request.cancel(Cr.NS_BINDING_ABORTED)` (guarded try/catch — cancel unavailable ⇒ fall through to the OS handler, per the spec's fallback) and calls `onZoteroLink`.
- Plugin handler: resolve the item (`Zotero.Items.getByLibraryAndKey(libraryID, key)`; user library id via `Zotero.Libraries.userLibraryID`, groups via `Zotero.Groups.getLibraryIDFromGroupID(groupID)`), then for `open-pdf` with a page: `this.focusWorkbenchPdfTab(item, page)` first, else `Zotero.Reader.open(item.id, { pageIndex: page - 1 }, {...})`; for `select`: `Zotero.getMainWindow()?.ZoteroPane?.selectItem(item.id)`.

**Steps:**

- [ ] **Step 1: Write failing tests.** `zotero-links.test.ts`: parses `zotero://open-pdf/library/items/AB12CD34?page=12` (user lib, page 12), `zotero://open-pdf/groups/451/items/K?page=3` (group), `zotero://select/library/collections/C1`, rejects `zotero://weird/thing`, `https://…`, missing key, non-numeric page. `research-loop-site.test.ts`: with `onZoteroLink` provided, a synthesized `onStateChange` for `zotero://open-pdf/...` cancels the fake request (spy on `cancel`) and forwards the parsed link; an `http://` state change is untouched.
- [ ] **Step 2: Run — expected FAIL** (`npx vitest run test/zotero-links.test.ts test/research-loop-site.test.ts`).
- [ ] **Step 3: Implement** parser, view listener (extend the existing `trackBrowserLocation` listener object's `onStateChange` — keep the location tracking intact), plugin wiring in `createWorkbenchView`'s `siteCallbacks` construction (pass `onZoteroLink` through a new `ResearchLoopSiteView` option from `SiteTabView` — thread it via `SiteTabCallbacks.onZoteroLink?`).
- [ ] **Step 4: Run the plugin suite — expected PASS** (`npx vitest run`).
- [ ] **Step 5: Commit** — `feat(zotero): handle knowledge-site deep links natively`.

---

### Task 9: Full gates, QA notes, docs

**Steps:**

- [ ] **Step 1: Root gates** — `npm run test:unit` (all knowledge/agent/drafts/literature/migration tests), `make knowledge-check`. Expected: clean.
- [ ] **Step 2: Plugin gate** — `cd integrations/zotero && npm run check && npx vitest run`. Expected: clean (72+ files, all passing).
- [ ] **Step 3: Build smoke** — `npm run knowledge:build` if Quarto is installed locally (skip with a note if the binary is absent); confirm `public/knowledge/research-loop-tree.js` exists and `index.html` loads it.
- [ ] **Step 4: Extend the live-QA checklist** in `docs/superpowers/2026-08-06-pdf-embed-spike.md` (or a sibling QA note): click a `zotero://open-pdf` link in an external browser → desktop Zotero opens the page; click it inside the workbench site tab → PDF tab/reader jumps natively (or OS fallback); drag tree nodes, copy layout YAML, paste, re-render.
- [ ] **Step 5: Commit** — `docs(knowledge): record topic-tree verification and QA handoff`.

---

## Self-Review Notes

- Spec coverage: trust decisions → Tasks 1, 5; deep-link authoring/behavior → Tasks 1, 8; block schema/validation/compilation → Tasks 2–3; runtime/canvas → Tasks 4–5; initial content → Task 6; skill → Task 7; error handling (build diagnostics, runtime no-op, clipboard fallback, interception fallback) → Tasks 2/4/5/8; testing section → mirrored per task.
- Type consistency: `TreeDiagnostic`/`CompiledTree*` defined once (Task 2), consumed by Tasks 3/5; `ZoteroDeepLink` defined in Task 8 only.
- The runtime is always emitted (data `null` when no block) — matches Task 5's test and keeps injection unconditional.
