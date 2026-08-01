# QLab VS Code Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the QMD Workspace's bespoke file list with a target-scoped, accessible VS Code-style Explorer without changing the Knowledge/Draft trust boundary.

**Architecture:** A shared explorer model makes repository indexing able to return explicit directories, an explicitly injected digest-backed cursor, and QMD leaves. The indexer itself remains Gecko/Chromium-neutral; only the production plugin injects the Gecko digest adapter. An explicit `ExplorerTargetStateOwner` stages, commits, or rolls back whole per-target Explorer snapshots. `QmdFileExplorer` is a controlled DOM-only component: the workspace supplies a complete target-tagged snapshot and owns all repository IO, preview, review, Keep, Visual Edit, and refresh policy. The completed local component consumes the already-landed local `RepositoryTarget` snapshot; the later SSH repository adapter supplies the same entries and cursor without changing the component.

**Tech Stack:** TypeScript; Zotero/Gecko DOM; Vitest 4 + happy-dom; CSS custom properties; esbuild; Playwright Chromium with `node:test`; bundled SVG assets; `pixelmatch` + `pngjs` as dev-only visual-diff dependencies.

**Spec:** `docs/superpowers/specs/2026-07-31-qlab-vscode-explorer-design.md` and `docs/superpowers/specs/2026-07-31-qlab-repository-targets-design.md` (user-approved). Implement exactly; do not add general filesystem mutations.

## Global Constraints

- This plan begins only after Repository Targets Slice 1 has landed a local immutable active snapshot containing `targetId: string`, monotonic `targetEpoch: number`, canonical local root, and target-switch rejection of stale `(targetId, targetEpoch)` callbacks. Do not create a second root-identity scheme in Explorer code.
- Test-first in every task: write and run the named red test before implementation; preserve its asserted behavior rather than weakening it.
- Run commands from `/home/chance/workers/1/quarto-lab/integrations/zotero`. The focused gate is `npx vitest run <files> && npm run check`; the browser gate is `npm run test:visual`; the complete local gate is `npm run verify`. `npm run verify` packages native macOS helpers, so run it on a macOS release environment; on Linux record the expected native-toolchain limitation after the TypeScript/Vitest/browser gates pass.
- Commit from `/home/chance/workers/1/quarto-lab`; each task has one conventional `<type>(zotero): ...` commit and stages only its listed files. Tasks 1--6 use `feat`; Task 7 uses `test`. No commit edits `knowledge/**/*.qmd`, `drafts/`, `literature/`, or generated `public/knowledge/`.
- Only `knowledge/` is trusted. The Explorer must keep Knowledge read-only, must not add a direct trusted-Knowledge write path, and may expose creation only through explicit Draft repository capabilities.
- Rows are 22px high, indentation is 8px, twisty/resource boxes are 16px, Explorer header is 35px, initial width is 240px, minimum width is 170px, and at a body width below 411px the side-by-side Explorer is auto-hidden. Geometry tolerance in browser tests is at most 1 CSS pixel.
- Use the approved 1440x900/DPR-1 light reference `.superdesign/references/qlab-vscode-explorer-approved-light-1440x900.png` (SHA-256 `989f92f65b27634f10df36013d0b677183e8ea5452cbc5d9f9004c69843324f5`) only as design authority. The committed regression golden is a capture of the real component, not a copy of this design input.
- Do not fetch icons, fonts, CSS, or screenshots at runtime. Codicon and Seti-derived bundled material retains upstream MIT attribution in `integrations/zotero/THIRD_PARTY_NOTICES.txt`.
- Do not alter preview, Visual Edit, Quick Open result ranking, Draft compliance, review, AI compare, Keep, external-editor semantics, or the existing 2-second local coalesced refresh policy in this delivery. SSH promotion and external editor remain unavailable according to Repository Target capabilities.

---

## Files and interfaces

All paths below are relative to `/home/chance/workers/1/quarto-lab`.

| File | Responsibility |
| --- | --- |
| Create `integrations/zotero/src/qmd-explorer-model.ts` | Repository-independent entry, index snapshot, controlled state, capability, callback, and target-key types shared by indexer, workspace, and DOM component. |
| Create `integrations/zotero/src/qmd-explorer-state.ts` | Sole owner of staged, committed, and rollback-safe per-target Explorer snapshots. |
| Create `integrations/zotero/src/qmd-file-icon-theme.ts` | Injectable FileIconTheme mapping with the bundled Seti default and no fabricated folder glyph fallback. |
| Modify `integrations/zotero/src/qmd-index.ts` | Return explicit `knowledge`/`drafts` directory entries (including empty Draft directories) and preserve QMD filtering. |
| Create `integrations/zotero/src/qmd-file-explorer.ts` | The DOM-only controlled Explorer, visible-row projection, tree keyboard model, inline Draft creation, availability behavior, sash, and narrow overlay. |
| Modify `integrations/zotero/src/qmd-workspace.ts` | Remove bespoke tree DOM/state; retain all IO and pass target-tagged snapshots/callbacks to one Explorer instance. |
| Create `integrations/zotero/src/qmd-explorer-preferences.ts` | Versioned per-`targetId` persistence for width, `userHidden`, and descendant expansion only. |
| Modify `integrations/zotero/src/plugin.ts` | Adapt the local `buildQmdIndex` result plus pending manifest to a target snapshot; persist Explorer callbacks; reject stale index completion. |
| Modify `integrations/zotero/src/styles.css` | Replace the old `176px + 18px` list/toggle CSS with Explorer token, tree, sash, overlay, and toolbar-Show styles, preserving Fix Pack B visual-parity rules. |
| Create `integrations/zotero/assets/codicon-chevron-down.svg`, `codicon-new-file.svg`, `codicon-new-folder.svg`, `codicon-refresh.svg`, `codicon-collapse-all.svg`, `codicon-more.svg`, `seti-qmd.svg`, `seti-folder.svg` | Offline per-icon SVG sources for only title actions, twisties, roots, folders, and `.qmd` files. |
| Modify `integrations/zotero/THIRD_PARTY_NOTICES.txt`, `integrations/zotero/test/build-assets.test.ts` | Preserve MIT attribution and prove the Explorer-only browser bundle emits inline assets/no old collapse strip assertion. |
| Create `integrations/zotero/test/qmd-file-explorer.test.ts`, `integrations/zotero/test/qmd-explorer-preferences.test.ts`, `integrations/zotero/test/qmd-explorer-state.test.ts` | Happy-dom component, persistence, and transactional target-state tests. |
| Modify `integrations/zotero/test/qmd-index.test.ts`, `integrations/zotero/test/qmd-workspace.test.ts` | Index and workspace integration/regression tests. |
| Create `integrations/zotero/test/visual/qmd-explorer-fixture.ts`, `integrations/zotero/test/visual/qmd-explorer.test.mjs`, `integrations/zotero/test/visual/goldens/qmd-explorer-light-1440x900.png` | Bundle/mount the real component in Chromium and compare its capture/geometry against a committed golden. |
| Modify `integrations/zotero/test/visual/render-harness.mjs`, `integrations/zotero/package.json`, `integrations/zotero/package-lock.json` | Extend Fix Pack B's shared Chromium harness (without replacing its Draft-parity route/asset ledger) with Explorer fixture bundling, local preview routing, deterministic PNG comparison, and dev-only dependencies. |

The shared model introduced in Task 1 is the exact contract for the rest of the plan:

```ts
import type { RepositoryTargetSnapshot } from "./repository-target";

export type QmdExplorerTree = "knowledge" | "drafts";
export type QmdExplorerAvailability = "ready" | "connecting" | "disconnected" | "error";

export interface QmdExplorerEntry {
  relativePath: string;
  parentPath: string | null;
  name: string;
  fullName: string;
  kind: "directory" | "qmd";
  tree: QmdExplorerTree;
  pending: boolean;
  readOnly: boolean;
}

export interface QmdExplorerIndexSnapshot {
  cursor: string;
  entries: readonly QmdExplorerEntry[];
}

export interface QmdExplorerIndexOptions {
  digest(bytes: Uint8Array): string;
}

export interface QmdFileExplorerState {
  targetId: string;
  targetEpoch: number;
  indexCursor: string;
  entries: readonly QmdExplorerEntry[];
  activeFilePath: string | null;
  selectedPaths: ReadonlySet<string>;
  focusedPath: string | null;
  expandedPaths: ReadonlySet<string>;
  width: number;
  userHidden: boolean;
  availability: QmdExplorerAvailability;
  availabilityMessage: string | null;
  refreshing: boolean;
  capabilities: { createDraftFile: boolean; createDraftFolder: boolean };
}

export interface QmdFileExplorerCallbacks {
  onOpen(relativePath: string): Promise<void> | void;
  onRefresh(): Promise<void> | void;
  onSelectedPathsChange(paths: ReadonlySet<string>): void;
  onFocusedPathChange(path: string | null): void;
  onExpandedPathsChange(paths: ReadonlySet<string>): void;
  onWidthChange(width: number): void;
  onUserHiddenChange(hidden: boolean): void;
  onCreateDraftFile?(request: { parentPath: string; name: string }): Promise<{ relativePath: string }>;
  onCreateDraftFolder?(request: { parentPath: string; name: string }): Promise<{ relativePath: string }>;
}

export interface ExplorerTargetSnapshot {
  /** The complete Slice-1 identity; never duplicate its root or ID fields. */
  repositoryTarget: RepositoryTargetSnapshot;
  indexCursor: string;
  entries: readonly QmdExplorerEntry[];
  activeFilePath: string | null;
  selectedPaths: ReadonlySet<string>;
  focusedPath: string | null;
  expandedPaths: ReadonlySet<string>;
  width: number;
  userHidden: boolean;
  availability: QmdExplorerAvailability;
  availabilityMessage: string | null;
  refreshing: boolean;
  capabilities: { createDraftFile: boolean; createDraftFolder: boolean };
  lastUsefulIndex: QmdExplorerIndexSnapshot | null;
}
```

### Task 1: Make the index snapshot represent directories and a cursor

**Files:**
- Create: `integrations/zotero/src/qmd-explorer-model.ts`
- Modify: `integrations/zotero/src/qmd-index.ts:1-140`
- Modify: `integrations/zotero/test/qmd-index.test.ts:1-90`
- Modify: `integrations/zotero/test/build-assets.test.ts:1-126`

**Interfaces:**
- Consumes: `QmdIndexScanner.list(absoluteDirectory)` and `EDITOR_TREES`/`treeForPath` from the existing indexer.
- Produces: `buildQmdExplorerIndex(scanner, repoRoot, { digest }): Promise<QmdExplorerIndexSnapshot>`, where `digest(bytes: Uint8Array): string` is injected by the caller; `filterQmdExplorerEntries(entries, query): QmdExplorerEntry[]`; existing `buildQmdIndex` and `filterQmdIndex` remain exported as compatibility adapters until Task 5 removes their workspace use.

- [ ] **Step 1: Write the failing explicit-directory/cursor tests.** Add these cases to `test/qmd-index.test.ts`, using the existing fake scanner plus one empty `drafts/Empty/` directory:

  ```ts
  const deterministicDigest = (bytes: Uint8Array) => `fixture-${bytes.length}-${bytes[0] ?? 0}`;

  it("returns both semantic roots, explicit empty Draft directories, and its injected cursor", async () => {
    const snapshot = await buildQmdExplorerIndex(scanner({
      "/repo/knowledge": ["index.qmd"],
      "/repo/drafts": ["Empty/", "Topic/"],
      "/repo/drafts/Empty": [],
      "/repo/drafts/Topic": ["note.qmd"],
    }), "/repo", { digest: deterministicDigest });
    expect(snapshot.entries.map(({ relativePath, kind }) => [relativePath, kind])).toEqual([
      ["knowledge", "directory"], ["knowledge/index.qmd", "qmd"],
      ["drafts", "directory"], ["drafts/Empty", "directory"],
      ["drafts/Topic", "directory"], ["drafts/Topic/note.qmd", "qmd"],
    ]);
    expect(snapshot.entries.find((entry) => entry.relativePath === "drafts/Empty"))
      .toMatchObject({ parentPath: "drafts", tree: "drafts", readOnly: false, pending: false });
    expect(snapshot.cursor).toBe(deterministicDigest(new TextEncoder().encode([
      "knowledge\tdirectory\t0", "knowledge/index.qmd\tqmd\t0",
      "drafts\tdirectory\t0", "drafts/Empty\tdirectory\t0",
      "drafts/Topic\tdirectory\t0", "drafts/Topic/note.qmd\tqmd\t0",
    ].join("\n"))));
  });

  it("sorts folders before QMD files, hides QMD extensions, and filters only QMD leaves", async () => {
    const snapshot = await buildQmdExplorerIndex(FIXTURE, "/repo", { digest: deterministicDigest });
    expect(snapshot.entries.filter((entry) => entry.parentPath === "knowledge").map((entry) => entry.name))
      .toEqual(["Magic", "index"]);
    expect(snapshot.entries.find((entry) => entry.relativePath.endsWith("Bell_magic.qmd")))
      .toMatchObject({ name: "Bell_magic", fullName: "Bell_magic.qmd" });
    expect(filterQmdExplorerEntries(snapshot.entries, "magic/bell").map((entry) => entry.relativePath))
      .toEqual(["knowledge/Magic/Bell_magic.qmd"]);
  });
  ```

- [ ] **Step 2: Run the red test.**

  ```bash
  npx vitest run test/qmd-index.test.ts
  ```

  Expected: TypeScript/Vitest fails because `buildQmdExplorerIndex` and `filterQmdExplorerEntries` do not exist. Do not change the assertions to use `groupIntoTree`; it cannot represent `drafts/Empty`.

- [ ] **Step 3: Add the shared types and the minimal scanner projection.** Create `src/qmd-explorer-model.ts` with the model block above. In `qmd-index.ts`, walk every allowed directory before its children, emit root entries even when `scanner.list` fails, and construct a cursor from the sorted structural fields so identical scans are stable:

  ```ts
  const sortedEntries = sortExplorerEntries(entries);
  const cursorMaterial = sortedEntries
    .map((entry) => [entry.relativePath, entry.kind, entry.pending ? "1" : "0"].join("\t"))
    .join("\n");
  const cursor = options.digest(new TextEncoder().encode(cursorMaterial));
  return { cursor, entries: sortedEntries };
  ```

  Define `QmdExplorerIndexOptions { digest(bytes: Uint8Array): string }` in the explorer model and accept it as the required third argument. `qmd-index.ts` imports neither `src/hashing.ts` nor any `node:*` module. Its old compatibility adapter remains cursor-free; the plugin's local production call supplies `{ digest: sha256Bytes }` from its existing Gecko-only `src/hashing.ts` import. Tests and the Chromium fixture supply the pure deterministic `deterministicDigest` above. For every directory use `kind: "directory"`, `fullName: name`, `readOnly: tree === "knowledge"`; for a QMD use the extensionless `name`, full filename, `kind: "qmd"`, and the same trust-derived `readOnly`. Preserve all current skipped-directory and preview-file exclusions. `filterQmdExplorerEntries` must return only `kind === "qmd"`, use the current contiguous case-insensitive path match/ranking, and never return a directory to Quick Open.

  Add a browser-build execution gate in `test/build-assets.test.ts` that bundles the real `src/qmd-index.ts` with esbuild `platform: "browser"`, `format: "iife"`, `globalName: "QmdIndexBundle"`, and `write: false`; evaluate that emitted IIFE in the happy-dom window and invoke `QmdIndexBundle.buildQmdExplorerIndex` with the fake scanner and a pure in-window `deterministicDigest`. Assert the returned entries and exact injected cursor match the direct invocation. This red test proves the browser IIFE actually executes without Gecko `Components`, not merely that it bundles, and it must not scan source text for imports.

- [ ] **Step 4: Run focused tests and typecheck.**

  ```bash
  npx vitest run test/qmd-index.test.ts test/build-assets.test.ts && npm run check
  ```

  Expected: PASS; old `buildQmdIndex`/`groupIntoTree` tests continue passing through compatibility adapters, and the new snapshot test proves an empty Draft directory has not disappeared.

- [ ] **Step 5: Commit the data boundary.**

  ```bash
  git add integrations/zotero/src/qmd-explorer-model.ts integrations/zotero/src/qmd-index.ts integrations/zotero/test/qmd-index.test.ts integrations/zotero/test/build-assets.test.ts && git commit -m "feat(zotero): index explicit QMD Explorer directories"
  ```

### Task 2: Build the controlled tree DOM, navigation, and ARIA contract

**Files:**
- Create: `integrations/zotero/src/qmd-file-explorer.ts`
- Create: `integrations/zotero/src/qmd-file-icon-theme.ts`
- Create: `integrations/zotero/assets/seti-qmd.svg`, `integrations/zotero/assets/seti-folder.svg`
- Create: `integrations/zotero/assets/codicon-chevron-down.svg`
- Create: `integrations/zotero/test/qmd-file-explorer.test.ts`

**Interfaces:**
- Consumes: all Task 1 model interfaces and `FileIconTheme`. Constructor is `new QmdFileExplorer(host: HTMLElement, callbacks: QmdFileExplorerCallbacks, options?: { fileIconTheme?: FileIconTheme })`; controlled updates use `setState(state: QmdFileExplorerState): void`; cleanup is `destroy(): void`.
- Produces: a root with `data-qmd-explorer-target="<targetId>"`; a `role="tree"` named `QMD Files Explorer` with `aria-multiselectable="true"`; visible rows with `role="treeitem"`; no filesystem imports or calls.

  `src/qmd-file-icon-theme.ts` exports this injected seam and default:

  ```ts
  export interface FileIconTheme {
    readonly id: string;
    iconFor(entry: Pick<QmdExplorerEntry, "relativePath" | "parentPath" | "kind" | "tree" | "fullName">): string | null;
  }
  export const DEFAULT_SETI_FILE_ICON_THEME: FileIconTheme;
  ```

  `DEFAULT_SETI_FILE_ICON_THEME` recognizes a semantic root only when `parentPath === null`, then maps roots, descendant folders, and `.qmd` entries to bundled Seti data URLs. A `null` result means render no resource-icon element: `QmdFileExplorer` must never invent a folder glyph, emoji, or text fallback.

- [ ] **Step 1: Write the red component DOM tests.** Create `test/qmd-file-explorer.test.ts` with `// @vitest-environment happy-dom`, a `state(overrides)` helper with two roots, `knowledge/Magic/Bell_magic.qmd`, a collapsed `drafts/Topic`, and a pending `drafts/Topic/note.qmd`. Add these assertions against a real `QmdFileExplorer`:

  ```ts
  it("projects ordered extensionless rows with complete tree ARIA", () => {
    const { host } = mountExplorer();
    const tree = host.querySelector<HTMLElement>('[role="tree"]')!;
    expect(tree.hasAttribute("aria-label")).toBe(true);
    expect(tree.getAttribute("aria-multiselectable")).toBe("true");
    const rows = [...host.querySelectorAll<HTMLElement>('[role="treeitem"]')];
    expect(rows.map((row) => row.dataset.path)).toEqual([
      "knowledge", "knowledge/Magic", "knowledge/Magic/Bell_magic.qmd", "drafts", "drafts/Topic",
    ]);
    expect(rows[2]!.getAttribute("data-qmd-explorer-display-name")).toBe("Bell_magic");
    expect(rows[2]!.getAttribute("data-qmd-explorer-full-name")).toBe("Bell_magic.qmd");
    expect(rows[0]!.getAttribute("aria-level")).toBe("1");
    expect(rows[1]!.getAttribute("aria-level")).toBe("2");
    expect(rows[1]!.getAttribute("aria-setsize")).toBe("2");
    expect(rows[1]!.getAttribute("aria-posinset")).toBe("1");
    expect(rows[4]!.getAttribute("aria-expanded")).toBe("false");
  });

  it("keeps active document, selection, and roving keyboard focus separate", () => {
    const { host, callbacks, setState } = mountExplorer({
      activeFilePath: "knowledge/Magic/Bell_magic.qmd",
      selectedPaths: new Set(["drafts/Topic"]), focusedPath: "drafts/Topic",
    });
    const active = host.querySelector<HTMLElement>('[data-path="knowledge/Magic/Bell_magic.qmd"]')!;
    const focused = host.querySelector<HTMLElement>('[data-path="drafts/Topic"]')!;
    expect(active.dataset.active).toBe("true");
    expect(active.getAttribute("aria-selected")).toBe("false");
    expect(focused.getAttribute("tabindex")).toBe("0");
    focused.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    expect(callbacks.onExpandedPathsChange).toHaveBeenCalledWith(new Set(["knowledge", "knowledge/Magic", "drafts", "drafts/Topic"]));
    setState({ expandedPaths: new Set(["knowledge", "knowledge/Magic", "drafts", "drafts/Topic"]), focusedPath: "drafts/Topic" });
    expect(document.activeElement).toBe(host.querySelector('[data-path="drafts/Topic"]'));
  });

  it("implements range selection, type-ahead, collapse-all focus fallback, and spoken pending text", () => {
    const { host, callbacks } = mountExplorer({ focusedPath: "knowledge", selectedPaths: new Set(["knowledge"]) });
    const tree = host.querySelector<HTMLElement>('[role="tree"]')!;
    tree.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", shiftKey: true, bubbles: true }));
    expect(callbacks.onSelectedPathsChange).toHaveBeenCalledWith(new Set(["knowledge", "knowledge/Magic"]));
    tree.dispatchEvent(new KeyboardEvent("keydown", { key: "t", bubbles: true }));
    expect(callbacks.onFocusedPathChange).toHaveBeenLastCalledWith("drafts/Topic");
    host.querySelector<HTMLButtonElement>('[data-qmd-explorer-action="collapse-all"]')!.click();
    expect(callbacks.onExpandedPathsChange).toHaveBeenLastCalledWith(new Set(["knowledge", "drafts"]));
    const pending = host.querySelector<HTMLElement>('[data-path="drafts/Topic/note.qmd"]')!;
    const pendingAncestor = host.querySelector<HTMLElement>('[data-path="drafts/Topic"]')!;
    expect(pending.getAttribute("data-qmd-explorer-pending")).toBe("true");
    expect(pending.getAttribute("aria-label")).toContain("Pending changes");
    expect(pendingAncestor.getAttribute("aria-label")).toContain("Pending changes");
    expect(host.querySelector('[data-path="knowledge"]')!.getAttribute("aria-label")).not.toContain("Pending changes");
  });

  it("announces connecting state through a polite live region", () => {
    const { host } = mountExplorer({ availability: "connecting", availabilityMessage: "Connecting to repository" });
    const status = host.querySelector<HTMLElement>('[role="status"]')!;
    expect(status.getAttribute("aria-live")).toBe("polite");
    expect(status.textContent).toContain("Connecting");
    expect(host.querySelector('[role="tree"]')!.getAttribute("aria-busy")).toBe("true");
  });
  ```

  Add a theme-injection test that mounts with `{ fileIconTheme: { id: "no-folder", iconFor: (entry) => entry.kind === "directory" && entry.parentPath !== null ? null : QMD_DATA_URL } }` and asserts the descendant folder row has no `[data-qmd-explorer-resource-icon]`, while the QMD row has an `<img>` with a `data:image/svg+xml` `src`. Add a second default-theme test that distinguishes a root (`parentPath === null`) from a nested folder and from a QMD entry. These tests must check rendered elements/URLs, not source text or user-facing prose.

  Add separate tests for click/twisty semantics, Ctrl/Cmd toggle, Ctrl/Cmd+A, Home/End/PageUp/PageDown, Left parent focus, Enter/Space activation, and an inactive selected row after focus moves to a title button. Each must dispatch an actual DOM event and assert a callback/ARIA change, not inspect source text.

- [ ] **Step 2: Run the red test.**

  ```bash
  npx vitest run test/qmd-file-explorer.test.ts
  ```

  Expected: module-resolution failure for `../src/qmd-file-explorer`; none of the new tree behavior exists yet.

- [ ] **Step 3: Implement the smallest controlled projection and event router.** Build the component around one `visibleRows()` projection ordered as roots `knowledge`, then `drafts`, with directory-first locale ordering. Render no mutable business state inside the class: every selection/focus/expansion transition copies the corresponding `Set` and invokes its callback. The critical renderer shape is:

  ```ts
  const item = this.doc.createElement("div");
  item.id = escapeExplorerDomId(entry.relativePath);
  item.setAttribute("role", "treeitem");
  item.dataset.path = entry.relativePath;
  item.dataset.qmdExplorerDisplayName = entry.name;
  item.dataset.qmdExplorerFullName = entry.fullName;
  item.setAttribute("aria-level", String(row.level));
  item.setAttribute("aria-setsize", String(row.setSize));
  item.setAttribute("aria-posinset", String(row.posInSet));
  item.setAttribute("aria-selected", String(state.selectedPaths.has(entry.relativePath)));
  item.tabIndex = state.focusedPath === entry.relativePath ? 0 : -1;
  if (entry.kind === "directory") item.setAttribute("aria-expanded", String(row.expanded));
  ```

  Define and export `escapeExplorerDomId(relativePath: string): string` as a deterministic DOM-id encoder (for example UTF-8 bytes encoded as lowercase hex prefixed by `qmd-explorer-`); do not rely on `CSS.escape`, which is not guaranteed by happy-dom. Add a unit case with `/`, spaces, `#`, and non-ASCII characters and assert the result is an id-safe stable string. Render `aria-multiselectable="true"` on the tree. When availability is `connecting`, render its message in a real `role="status" aria-live="polite"` region and set the tree `aria-busy="true"`; the real-DOM test above is the acceptance proof. Add stable machine selectors (`data-qmd-explorer-action`, `data-qmd-explorer-pending`, and the row display/full-name attributes above) alongside the required ARIA labels so tests do not couple to human-facing copy. A pending Draft file and every pending Draft ancestor receives an explicit spoken `aria-label` suffix `Pending changes`; Knowledge never does. On controlled focus updates, call `.focus({ preventScroll: true })` on the new row after render and assert `document.activeElement` after an actual keyboard transition. Place selection anchor and one-second type-ahead buffer in the component's ephemeral state. On any different `(targetId, targetEpoch)`, clear anchor/type-ahead/hover/drag/inline input and render only the new controlled snapshot. Do not call `onOpen` for arrow navigation; call it only for file click, Enter, or Space when availability is `ready`.

- [ ] **Step 4: Run component and existing index suites.**

  ```bash
  npx vitest run test/qmd-file-explorer.test.ts test/qmd-index.test.ts && npm run check
  ```

  Expected: PASS. The real DOM proves `aria-multiselectable`, polite connecting status, and the pending spoken label on the file and each Draft ancestor; Knowledge receives no pending decoration.

- [ ] **Step 5: Commit the component core.**

  ```bash
  git add integrations/zotero/src/qmd-file-explorer.ts integrations/zotero/src/qmd-file-icon-theme.ts integrations/zotero/assets/seti-qmd.svg integrations/zotero/assets/seti-folder.svg integrations/zotero/assets/codicon-chevron-down.svg integrations/zotero/test/qmd-file-explorer.test.ts && git commit -m "feat(zotero): add controlled accessible QMD Explorer"
  ```

### Task 3: Add availability and safe inline Draft creation to the component

**Files:**
- Modify: `integrations/zotero/src/qmd-file-explorer.ts`
- Modify: `integrations/zotero/test/qmd-file-explorer.test.ts`
- Create: `integrations/zotero/assets/codicon-new-file.svg`, `codicon-new-folder.svg`, `codicon-refresh.svg`, `codicon-collapse-all.svg`, `codicon-more.svg`

**Interfaces:**
- Consumes: Task 2 class plus `availability`, `capabilities`, and optional creation callbacks from Task 1.
- Produces: title actions in fixed order New File, New Folder, Refresh Explorer, Collapse All; a keyboard-accessible overflow menu containing Hide Explorer; `resolveDraftParent(state): { parentPath: string; reason: string | null }`; no creation callback is reached except for ready/capable/unambiguous Draft selection.

- [ ] **Step 1: Write red tests for action gating, creation, and failures.** Add real-DOM tests covering: no selection resolves to `drafts`; one Draft directory resolves to itself; one Draft file resolves to its parent; Knowledge and multi-selection show focusable `aria-disabled="true"` New File/New Folder with `aria-describedby` reason; connecting sets tree `aria-busy`, exposes its exact connecting message via `role="status" aria-live="polite"`, and coalesces Refresh; disconnected says Reconnect and blocks open/create; error says Retry and renders `role="alert"`.

  Add an inline creation test with these concrete assertions:

  ```ts
  it("creates only a valid Draft QMD and keeps typed failures editable", async () => {
    const createDraftFile = vi.fn(async () => ({ relativePath: "drafts/Topic/new-note.qmd" }));
    const { host, callbacks, setState } = mountExplorer({ selectedPaths: new Set(["drafts/Topic"]), focusedPath: "drafts/Topic" }, { createDraftFile });
    host.querySelector<HTMLButtonElement>('[data-qmd-explorer-action="new-file"]')!.click();
    const input = host.querySelector<HTMLInputElement>('[data-qmd-explorer-create="file"]')!;
    expect(input.closest('[role="treeitem"]')!.previousElementSibling?.getAttribute("data-path")).toBe("drafts/Topic");
    input.value = "bad/name.qmd";
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(host.querySelector('[role="alert"]')!.getAttribute("data-qmd-explorer-error-code")).toBe("INVALID_FILE_NAME");
    input.value = "new-note.qmd";
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await Promise.resolve();
    expect(createDraftFile).toHaveBeenCalledWith({ parentPath: "drafts/Topic", name: "new-note.qmd" });
    expect(callbacks.onSelectedPathsChange).toHaveBeenLastCalledWith(new Set(["drafts/Topic/new-note.qmd"]));
    expect(callbacks.onOpen).toHaveBeenCalledWith("drafts/Topic/new-note.qmd");
    setState({ targetId: "target-b", targetEpoch: 2 });
    expect(host.querySelector('[data-qmd-explorer-create]')).toBeNull();
  });
  ```

  Add overflow tests: the `data-qmd-explorer-action="overflow"` control becomes visible on Explorer-header hover or focus-within, opens a `role="menu"` with a `role="menuitem"` carrying `data-qmd-explorer-action="hide"`, exposes the required accessible label, closes on Escape/outside click/Hide activation, and restores focus to the overflow button after Escape. Also test Escape/blur cancellation without a callback, folder name rejection of NUL `/` `\\` `.` `..`, `aria-busy` while the promise is pending, duplicate/typed error retaining input and focus, and ignoring a resolve after the target epoch changes. Error assertions use the stable `data-qmd-explorer-error-code` machine value, never the human-readable alert copy.

- [ ] **Step 2: Run the red test.**

  ```bash
  npx vitest run test/qmd-file-explorer.test.ts
  ```

  Expected: title actions and `[data-qmd-explorer-create]` do not exist, so the new cases fail before a repository callback is invoked.

- [ ] **Step 3: Add only validated request dispatch.** Render 22px title buttons in the required order. Never set native `disabled`; set `aria-disabled`, intercept click/Enter/Space, and point `aria-describedby` to a visible-or-screen-reader reason. Insert the input as the first child of the selected Draft parent; validate before request:

  ```ts
  const invalidSegment = (name: string) => !name || name.includes("\0") || /[\\/]/.test(name) || name === "." || name === "..";
  const valid = kind === "file" ? !invalidSegment(name) && name.endsWith(".qmd") : !invalidSegment(name);
  ```

  Render the primary action icons from five independent SVG module imports (`codicon-new-file.svg`, `codicon-new-folder.svg`, `codicon-refresh.svg`, `codicon-collapse-all.svg`, `codicon-more.svg`); the twisty uses `codicon-chevron-down.svg`. Each import is one esbuild data URL, so no sprite fragment or runtime asset lookup is required. During a request set input read-only plus `aria-busy="true"`; failures set a documented machine-readable `data-qmd-explorer-error-code` while retaining editable focus. After success issue controlled focus/selection callbacks and `onOpen` only for files. Refresh calls a single in-flight promise; its label is `Refresh Explorer`, `Reconnect`, or `Retry` exactly as availability demands. Cached orientation rows remain selectable but cannot activate while non-ready.

- [ ] **Step 4: Run focused tests and typecheck.**

  ```bash
  npx vitest run test/qmd-file-explorer.test.ts && npm run check
  ```

  Expected: PASS; tests prove no Knowledge or unavailable path reaches `onCreateDraftFile`/`onCreateDraftFolder`.

- [ ] **Step 5: Commit inline creation and availability.**

  ```bash
  git add integrations/zotero/src/qmd-file-explorer.ts integrations/zotero/test/qmd-file-explorer.test.ts integrations/zotero/assets/codicon-new-file.svg integrations/zotero/assets/codicon-new-folder.svg integrations/zotero/assets/codicon-refresh.svg integrations/zotero/assets/codicon-collapse-all.svg integrations/zotero/assets/codicon-more.svg && git commit -m "feat(zotero): gate Explorer Draft creation by capability"
  ```

### Task 4: Transactionally own per-target Explorer state, then persist sash/hide/overlay preferences

**Files:**
- Create: `integrations/zotero/src/qmd-explorer-state.ts`
- Create: `integrations/zotero/src/qmd-explorer-preferences.ts`
- Create: `integrations/zotero/test/qmd-explorer-state.test.ts`
- Create: `integrations/zotero/test/qmd-explorer-preferences.test.ts`
- Modify: `integrations/zotero/src/qmd-file-explorer.ts`
- Modify: `integrations/zotero/test/qmd-file-explorer.test.ts`
- Modify: `integrations/zotero/test/repository-target-controller.test.ts`

**Interfaces:**
- Consumes: `prefString`/`setPrefString` from `src/platform.ts`, the complete Slice-1 `RepositoryTargetSnapshot`, Task 2 component callbacks, and the landed Slice-1 `TargetSwitchRuntime` contract.
- Produces: `ExplorerTargetStateOwner` as a staged owner registered inside the plugin's one `TargetSwitchRuntime`, plus `readQmdExplorerPreferences(targetId): { width: number; userHidden: boolean; expandedPaths: Set<string> }` and `writeQmdExplorerPreferences(targetId, value): void`; preference key is exactly `qmdExplorer.v1` and serialized JSON is `{ version: 1, targets: Record<string, { width: number; userHidden: boolean; expandedPaths: string[] }> }`.

  `ExplorerTargetStateOwner` is the only owner of a target's rendered Explorer snapshot. Its exact operations are `stage(repositoryTarget, incomingIndex, persisted): StagedExplorerTarget`, `commit(staged): ExplorerTargetSnapshot`, `rollback(staged): ExplorerTargetSnapshot | null`, `dispose(staged): void`, `current(): ExplorerTargetSnapshot | null`, and `updateCurrent(patch): ExplorerTargetSnapshot`. `repositoryTarget` is the complete Slice-1 snapshot, so implementation derives its key only through `repositoryTarget.target.targetId` and captures its epoch only through `repositoryTarget.targetEpoch`; it never accepts or stores an unqualified root/ID tuple. `stage` is side-effect-free: it creates or restores a full target snapshot but never publishes it. `commit` atomically makes that staged snapshot current. `rollback` and `dispose` leave the previous committed snapshot unchanged. The owner retains `entries`, `indexCursor`, `activeFilePath`, `selectedPaths`, `focusedPath`, `expandedPaths`, `width`, `userHidden`, `availability`, `availabilityMessage`, `refreshing`, `capabilities`, and `lastUsefulIndex` per target. A new `(targetId, targetEpoch)` resets component-ephemeral anchor/type-ahead/hover/drag/create state in Task 2, but never leaks a previous target's controlled values.

- [ ] **Step 1: Write red target-transaction, preference, and layout tests.** In `test/qmd-explorer-state.test.ts`, construct complete Slice-1 snapshots A/B (including `target.canonicalRoot`, `target.targetId`, and `targetEpoch`) and give A a nonempty index/cursor, active file, selected/focused/expanded paths, width, hidden setting, and `lastUsefulIndex`; then perform a complete A → stage B → commit B → stage A → commit A sequence. Assert that staged B does not change `current()`, A's exact `entries`, cursor, active/selected/focused/expanded values, width, and `lastUsefulIndex` return on A's commit, and B receives only B state. Add a failed B index stage followed by `rollback(stagedB)` and assert the still-rendered A snapshot is byte-for-byte equivalent by structural fields. Include an epoch change for the same target ID and assert only component-ephemeral state is reset.

  In `test/repository-target-controller.test.ts`, register a real `ExplorerTargetStateOwner` in the controller harness's staged runtime. Add controller-level tests that (a) stage B, make a pre-commit operation/persistence fail, and prove A remains both the controller's active snapshot and the Explorer owner's `current()` while B is rolled back/disposed without any transient empty tree; and (b) defer B staging, request C, settle B late, and prove B never commits while C becomes the sole committed Explorer snapshot. Both tests must exercise `RepositoryTargetController.switchTo()`, not call `owner.commit()` directly.

  In `test/qmd-explorer-preferences.test.ts`, stub `Services.prefs`, write different values for `local:a` and `ssh:profile:b`, and assert each reads only its own width/hidden/expansion set; malformed JSON and a non-v1 payload return `{ width: 240, userHidden: false, expandedPaths: new Set(["knowledge", "drafts"]) }` without throwing. In component tests assert a 500px body clamps a 480px saved width to 200px, 411--424px uses 170px, and 410px yields `autoHidden` without calling `onUserHiddenChange`.

  Add actual DOM keyboard/pointer assertions:

  ```ts
  it("uses an accessible sash and restores a hidden Explorer in narrow overlay mode", () => {
    const { host, callbacks, resizeBody, setState } = mountExplorer({}, { bodyWidth: 760 });
    const sash = host.querySelector<HTMLElement>('[role="separator"]')!;
    expect(sash.getAttribute("aria-orientation")).toBe("vertical");
    expect(sash.getAttribute("aria-valuemin")).toBe("170");
    expect(sash.getAttribute("aria-valuemax")).toBe("304");
    expect(sash.getAttribute("aria-valuenow")).toBe("240");
    sash.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    expect(callbacks.onWidthChange).toHaveBeenCalledWith(248);
    setState({ width: 248 });
    expect(host.querySelector('[role="separator"]')!.getAttribute("aria-valuenow")).toBe("248");
    sash.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(callbacks.onWidthChange).toHaveBeenLastCalledWith(240);
    host.querySelector<HTMLButtonElement>('[data-qmd-explorer-action="overflow"]')!.click();
    const hide = host.querySelector<HTMLButtonElement>('[role="menuitem"][data-qmd-explorer-action="hide"]')!;
    hide.click();
    expect(callbacks.onUserHiddenChange).toHaveBeenCalledWith(true);
    resizeBody(410);
    host.querySelector<HTMLButtonElement>('[data-qmd-explorer-action="show"]')!.click();
    expect(callbacks.onUserHiddenChange).toHaveBeenLastCalledWith(false);
    expect(host.querySelector('[data-qmd-explorer-overlay]')).not.toBeNull();
  });
  ```

  Add cases for Shift+arrow 32px, Home/End min/max, outside/Escape/file-activation overlay dismissal, Cmd/Ctrl+B, width retained across hide/restore, and target switch clearing overlay/drag state. The test helper must install a controllable fake `ResizeObserver` (happy-dom does not deliver resize callbacks) and expose `resizeBody`; no test may rely on a native happy-dom resize delivery.

- [ ] **Step 2: Run red tests.**

  ```bash
  npx vitest run test/qmd-explorer-state.test.ts test/qmd-explorer-preferences.test.ts test/qmd-file-explorer.test.ts
  ```

  Expected: module resolution failure for preferences and missing separator/overlay elements; the old component has neither persistent target state nor a sash.

- [ ] **Step 3: Implement atomic target ownership, then persistence and layout-derived state.** Implement `ExplorerTargetStateOwner` in `qmd-explorer-state.ts` with copied arrays/Sets on each stage/commit/update so callers cannot mutate a committed snapshot. Define it as the Explorer portion of the plugin's `TargetSwitchRuntime` (Task 5 performs the production registration): that runtime's `stage(next, signal)` captures the complete `next: RepositoryTargetSnapshot`, builds/stages the Explorer state, and never touches A or publishes B; the controller then persists B, executes its single synchronous `publish(next, staged)` by invoking `owner.commit(staged.explorer)` exactly once, and only then disposes old resources. If persistence or any other pre-commit step fails, the controller calls only `TargetSwitchRuntime.disposeStaged(staged)`; its Explorer implementation rolls back/disposes `staged.explorer` and leaves A as `owner.current()` without a transient empty tree. No workspace refresh or resource callback may call `commit` independently. `stage` uses only `repositoryTarget.target.targetId` to retrieve saved state, captures `repositoryTarget.targetEpoch` in the staged value, and preserves the prior committed snapshot until controller publication; an index rejection must call the owner rollback/dispose path, not construct an empty current tree. Save per-target `lastUsefulIndex` only after a successful index commit. Parse only the defined preference JSON shape, discard unknown target records, and serialize only after `onWidthChange`, `onUserHiddenChange`, or `onExpandedPathsChange` reaches the workspace. In the component measure body width with `ResizeObserver` (with a window resize fallback for happy-dom); calculate:

  ```ts
  const maxWidth = Math.max(170, Math.floor(bodyWidth * 0.4));
  const sideBySide = bodyWidth >= 411;
  const width = bodyWidth >= 425 ? clamp(savedWidth, 170, maxWidth) : 170;
  ```

  At `<411`, do not mutate `userHidden`; Show clears it through the callback and opens the 170px overlay. Use one focusable vertical `role="separator"` with `aria-orientation="vertical"`, current `aria-valuemin`, `aria-valuemax`, and `aria-valuenow`, plus a 4px hit target/1px divider. On pointerdown save pre-drag width, on pointermove clamp and callback, on pointerup commit; Escape restores saved width. The root keydown handler handles Cmd/Ctrl+B only when the Quick Open input is not active.

- [ ] **Step 4: Run focused tests and typecheck.**

  ```bash
  npx vitest run test/qmd-explorer-state.test.ts test/qmd-explorer-preferences.test.ts test/qmd-file-explorer.test.ts && npm run check
  ```

  Expected: PASS; an A → B → A return restores every committed A controlled field, a controller pre-commit failure and superseded B leave A/B never transiently rendered, and only the controller's synchronous publish commits the selected target.

- [ ] **Step 5: Commit target-scoped persistence and responsive Explorer shell.**

  ```bash
  git add integrations/zotero/src/qmd-explorer-state.ts integrations/zotero/test/qmd-explorer-state.test.ts integrations/zotero/src/qmd-explorer-preferences.ts integrations/zotero/test/qmd-explorer-preferences.test.ts integrations/zotero/src/qmd-file-explorer.ts integrations/zotero/test/qmd-file-explorer.test.ts integrations/zotero/test/repository-target-controller.test.ts && git commit -m "feat(zotero): transact target-scoped Explorer state"
  ```

### Task 5: Replace the workspace tree and wire target-tagged local snapshots

**Files:**
- Modify: `integrations/zotero/src/qmd-workspace.ts:1-155,244-275,282-405,913-1017`
- Modify: `integrations/zotero/src/plugin.ts:1390-1460`
- Modify: `integrations/zotero/test/qmd-workspace.test.ts:29-206,409-430,609-628`

**Interfaces:**
- Consumes: `QmdFileExplorer`, Task 1 index snapshot, Task 4 `ExplorerTargetStateOwner`/preferences, and the complete Slice-1 `RepositoryTargetSnapshot` supplied by the plugin target controller.
- Produces: `QmdWorkspaceOptions.index` changes from `(): Promise<QmdIndexEntry[]>` to `(): Promise<QmdExplorerIndexSnapshot>`; it gains `target(): RepositoryTargetSnapshot` (the complete Slice-1 value, never a hand-built root/ID subset); workspace owns `applyExplorerIndex(snapshot, requested: RepositoryTargetSnapshot)` and discards any index result whose `(requested.target.targetId, requested.targetEpoch)` is no longer active. Availability/message/refreshing/capabilities remain controlled Explorer state supplied by the owner, not fields copied onto a mutable root object. Quick Open receives `filterQmdExplorerEntries(snapshot.entries, query)` and therefore retains its QMD-leaf-only behavior.

- [ ] **Step 1: Write red workspace integration tests.** Replace the old collapse-strip test at `test/qmd-workspace.test.ts:157-177` with tests that mount the actual Explorer and assert there is no `.zc-qmd-file-toggle`, a toolbar `[data-qmd-explorer-action="show"]` appears only while user-hidden, and Cmd/Ctrl+B changes the controlled hidden callback. Rename the workspace test helper to `mountWorkspace` (the component suite owns `mountExplorer`) and update it to return a complete `RepositoryTargetSnapshot` from `target()`, for example `{ target: { kind: "local", root: "/repo", canonicalRoot: "/repo", repositoryId: "…64 hex…", targetId: "local:repo-a" }, targetEpoch: 1 }`. Add an assertion that index, render/check, preview, Quick Open, and save/edit callbacks each receive/use that same captured snapshot and derive their root only as `requested.target.canonicalRoot`; no test may set a `repoRootHint` or a parallel mutable root field.

  Add a deferred-index race test:

  ```ts
  it("discards a late old-target index instead of replacing the new Explorer", async () => {
    let resolveOld!: (value: QmdExplorerIndexSnapshot) => void;
    const index = vi.fn(() => new Promise<QmdExplorerIndexSnapshot>((resolve) => { resolveOld = resolve; }));
    const { host, view, setTarget } = mountWorkspace({ index });
    view.show();
    setTarget({ target: localTarget("local:repo-b", "/repo-b"), targetEpoch: 2 });
    resolveOld(snapshot("old", [entry("drafts/old.qmd")]));
    await settle();
    expect(host.querySelector('[data-path="drafts/old.qmd"]')).toBeNull();
    expect(host.querySelector('[data-qmd-explorer-target="local:repo-b"]')).not.toBeNull();
  });
  ```

  Add a workspace-level A → B → A test using the target owner: set every A controlled field (entries, cursor, active, selected, focused, expanded, width, availability/message, refreshing, capabilities, and last useful index), commit B with distinct values, then commit A again and assert the Explorer DOM receives exactly the original A snapshot. Add a rejected B refresh after A is committed and assert `rollback` retains A rows/cursor instead of rendering a temporary empty tree. Keep the existing stale-callback test and make it assert `(targetId, targetEpoch)` is checked before staging and immediately before commit.

  Preserve and adapt the existing tests for roots, Quick Open, pending ancestor decoration, Preview, Draft review/Keep, Visual Edit, and periodic local refresh. Add a test that a transient index rejection retains old Explorer rows and reports status, and that an active deleted file clears preview/selection rather than selecting a sibling.

- [ ] **Step 2: Run red integration tests.**

  ```bash
  npx vitest run test/qmd-workspace.test.ts
  ```

  Expected: failures because `QmdWorkspaceOptions.target`, the Explorer component, target-tagged snapshot application, and toolbar Show control do not exist; the prior `.zc-qmd-file-toggle` assertion must no longer be present.

- [ ] **Step 3: Move DOM rendering, not repository ownership.** In `QmdWorkspaceView`, delete `fileColumn`, `fileToggle`, `expanded`, `renderFileColumn`, `renderNode`, `nodeHasPendingChange`, and any mutable `repoRootHint`/parallel root cache. Create a body container for `QmdFileExplorer`; `onOpen` delegates to existing `open`; `onRefresh` delegates to existing coalesced `refreshVisibleIndex`; other callbacks update immutable owner-controlled Explorer state and Task-4 preference store. Keep `refreshIndex` as the single local request coalescer and retain its catch behavior that preserves `this.entries`.

  In `plugin.ts`, make the sole `QmdWorkspaceOptions.index` provider capture `const requested = this.requireActiveTargetSnapshot()` synchronously, then call `buildQmdExplorerIndex(scanner, requested.target.canonicalRoot, { digest: sha256Bytes })` and immutably mark matching pending entries before returning the snapshot. Every path-sensitive workspace operation—index, render, `checkDraft`, preview URL/request, Quick Open, read/save, Visual Edit, Keep, and refresh—captures `const requested = options.target()` before its async boundary and reads its root only as `requested.target.canonicalRoot`; it must reject/ignore completion unless `requested.target.targetId` and `requested.targetEpoch` still match the active snapshot. There is no mutable `repoRootHint`, `settings?.qlabRoot`, or re-read of a global root after an async boundary. `sha256Bytes` remains at this Gecko production boundary only and must not move into the indexer or browser fixture. The plugin's `TargetSwitchRuntime.stage(next, signal)` obtains B's index and calls `ExplorerTargetStateOwner.stage(next, index, preferences)`; only the controller's synchronous `publish` may commit that staged B snapshot. In `QmdWorkspaceView.refreshIndex`, pass the returned snapshot plus the complete captured `requested` to `applyExplorerIndex`; after the same pair check, a refresh of the already-published target uses only `owner.updateCurrent(...)`, never `stage`/`commit`. On index rejection preserve the last committed rows without publishing an empty state. Derive the Quick Open leaf cache solely with `filterQmdExplorerEntries(snapshot.entries, query)`. Keep the existing Draft review callback for local targets; set creation capability false until the repository adapter exposes the exact safe create operations.

- [ ] **Step 4: Run workspace, index, visual-editor, and type gates.**

  ```bash
  npx vitest run test/qmd-index.test.ts test/qmd-file-explorer.test.ts test/qmd-explorer-state.test.ts test/qmd-explorer-preferences.test.ts test/qmd-workspace.test.ts test/qmd-visual-editor.test.ts test/qmd-source-model.test.ts && npm run check
  ```

  Expected: PASS. No old-target entry appears, no stale or rejected index empties the current tree, A → B → A restores its whole controlled snapshot, and index/render/check/preview callbacks all use only their captured `requested.target.canonicalRoot` while the preview/Keep/Visual Edit regressions remain green.

- [ ] **Step 5: Commit the workspace integration.**

  ```bash
  git add integrations/zotero/src/qmd-workspace.ts integrations/zotero/src/plugin.ts integrations/zotero/test/qmd-workspace.test.ts && git commit -m "feat(zotero): mount Explorer from target snapshots"
  ```

### Task 6: Apply offline VS Code visual language and legal attribution

**Files:**
- Modify: `integrations/zotero/src/styles.css:1099-1436` (with the old file-tree sub-block at `1236-1300` replaced)
- Modify: `integrations/zotero/THIRD_PARTY_NOTICES.txt`
- Modify: `integrations/zotero/test/build-assets.test.ts:31-126`

**Interfaces:**
- Consumes: the class/data/ARIA hooks emitted by Tasks 2--5 and the existing esbuild `.svg: dataurl` loader in `scripts/build.mjs`.
- Produces: `--zc-explorer-*` semantic CSS tokens with light/dark mappings; no `.zc-qmd-file-toggle` selector; SVG assets imported by `qmd-file-icon-theme.ts` and bundled as Explorer-local data URLs.

- [ ] **Step 1: Write red Explorer-asset behavior tests.** Replace the old `build-assets.test.ts:117` collapse-strip assertion with an esbuild browser bundle of the real `src/qmd-file-icon-theme.ts`. Execute its exported default mapping and assert root, folder, and QMD values are inline `data:image/svg+xml` URLs. Do not scan the complete JavaScript bundle for URL-looking text and do not inspect CSS or legal-notice prose. The Chromium fixture in Task 7 records requests made after the Explorer mounts and asserts that no request originates from an Explorer resource icon; this is the network-behavior proof and is intentionally scoped to Explorer assets rather than unrelated application URLs.

- [ ] **Step 2: Run red tests.**

  ```bash
  npx vitest run test/build-assets.test.ts
  ```

  Expected: the new Explorer icon theme/assets are absent; the obsolete toggle assertion is removed before this command.

- [ ] **Step 3: Replace the old list CSS and bundle the exact asset subset.** Verify Tasks 2--3's eight independent SVG modules contain only the licensed upstream-derived chevron-down, new-file, new-folder, refresh, collapse-all, more, folder/root, and QMD paths. `qmd-file-icon-theme.ts` imports the Seti resource modules and `qmd-file-explorer.ts` imports each Codicon action/twisty module, so esbuild's existing `.svg: dataurl` loader emits one self-contained data URL per icon. Do not reference `chrome://`, a sprite fragment, or a network URL for Explorer icons.

  Replace the QMD workspace CSS block currently at `styles.css:1099-1436` (including the old tree rules at `1236-1300`) with Explorer-specific rules. Define light token values `#F8F8F8`, `#E5E5E5`, `#3B3B3B`, `#E8E8E8`, `#000000`, `#F2F2F2`, `#005FB8` and dark mappings `#181818`, `#2B2B2B`, `#CCCCCC`, `#37373D`, `#FFFFFF`, `#2A2D2E`, `#007FD4`; use them through CSS variables. Preserve the Fix Pack B visual-editor parity selectors and KaTeX font behavior outside the Explorer replacement. Implement 35px header, 22px rows, 8px indentation, 16px icon slots, 10px overlay scrollbar, active/inactive selection, independent focus outline, pending decoration, 1px visible sash/4px hit area, and a 170px overlay. Keep the render/visual panes in their existing layout frame and use the new Explorer column variables instead of hard-coded grid column 3/old collapsed classes.

  Append full upstream MIT notices and source URLs for the copied Codicon and Seti material to `THIRD_PARTY_NOTICES.txt`; preserve existing KaTeX/xterm notices verbatim.

- [ ] **Step 4: Run bundle tests and focused DOM tests.**

  ```bash
  npx vitest run test/build-assets.test.ts test/qmd-file-explorer.test.ts test/qmd-workspace.test.ts && npm run check
  ```

  Expected: PASS; default Explorer icon values are data URLs, Chromium covers icon-request behavior in Task 7, and no CSS rule can recreate the visible 18px collapse strip.

- [ ] **Step 5: Commit visual assets, CSS, and notices.**

  ```bash
  git add integrations/zotero/src/styles.css integrations/zotero/THIRD_PARTY_NOTICES.txt integrations/zotero/test/build-assets.test.ts && git commit -m "feat(zotero): style Explorer with offline VS Code assets"
  ```

### Task 7: Capture the real component in Chromium and commit the pixel golden

**Files:**
- Create: `integrations/zotero/test/visual/qmd-explorer-fixture.ts`
- Create: `integrations/zotero/test/visual/qmd-explorer.test.mjs`
- Create: `integrations/zotero/test/visual/goldens/qmd-explorer-light-1440x900.png`
- Modify: `integrations/zotero/test/visual/render-harness.mjs` (extend its existing Fix Pack B `sharedBrowser`, `closeHarness`, esbuild, and route helpers; do not rewrite or duplicate them)
- Modify: `integrations/zotero/package.json`
- Modify: `integrations/zotero/package-lock.json`

**Interfaces:**
- Consumes: the actual exported `QmdWorkspaceView`, `QmdFileExplorer`, CSS, and deterministic repository/index/preview fakes from Tasks 1--6.
- Produces: `bundleBrowserFixture(entryPoint): Promise<string>`, the shared harness esbuild API used to bundle `qmd-explorer-fixture.ts` for browser injection; `renderExplorerWorkspaceFixture({ width, height, colorScheme })` that uses the existing shared Chromium lifecycle and mounts a real `QmdWorkspaceView` containing Explorer and a shimmed real preview browser, returns geometry (including element `src`), post-mount Explorer-icon requests, and a PNG buffer; `comparePng(actual, golden): { differingPixelRatio: number }` using `PNG.sync.read` and `pixelmatch`.

- [ ] **Step 1: Write the red Chromium visual test.** Create `qmd-explorer.test.mjs` using `node:test`. At 1440x900/DPR 1 mount literal entries with both roots, expanded `knowledge/Magic`, collapsed `drafts/Topic`, selected `knowledge/Magic/Bell_magic.qmd`, and pending `drafts/Topic/note.qmd`. Assert header 35px, rows 22px, 8px nested inset, 240px Explorer width, sash position, selected/pending/action/preview elements, and a golden path that does not yet exist:

  ```js
  test("real workspace Explorer and preview match the committed light golden", async () => {
    const { measurements, explorerIconRequests, screenshot } = await renderExplorerWorkspaceFixture({ width: 1440, height: 900, colorScheme: "light" });
    assert.equal(measurements[".zc-qmd-explorer-header"].height, 35);
    assert.equal(measurements["[role=treeitem]"].height, 22);
    assert.equal(measurements[".zc-qmd-explorer"].width, 240);
    assert.ok(Math.abs(measurements[".zc-qmd-explorer-sash"].left - 240) <= 1);
    assert.equal(measurements["[data-path='knowledge/Magic/Bell_magic.qmd']"].found, true);
    assert.equal(measurements["[data-qmd-explorer-pending='true']"].found, true);
    assert.equal(measurements[".zc-qmd-render"].found, true);
    assert.equal(measurements[".zc-qmd-render-browser"].src, "https://preview.fixture/knowledge/Magic/Bell_magic.html");
    assert.deepEqual(explorerIconRequests, []);
    assert.ok(comparePng(screenshot, GOLDEN).differingPixelRatio <= 0.005);
  });
  ```

  Add a 760x720 structural capture test (no clipping of either Explorer or preview), plus dark-mode computed-style assertions for the sidebar and focus border. The test must inject the browser bundle of the real workspace fixture, not recreate Explorer HTML in `surfaces.mjs` or assert CSS source strings.

- [ ] **Step 2: Run the red browser test.**

  ```bash
  node --test test/visual/qmd-explorer.test.mjs
  ```

  Expected: failure because `renderExplorerWorkspaceFixture`, the PNG diff dependencies, and the committed golden do not exist. If Chromium is absent, first run `npx playwright install chromium`, then rerun; do not mark a missing browser as a passing visual test.

- [ ] **Step 3: Bundle/mount the real workspace shell and add deterministic diffing.** Add dev dependencies exactly with:

  ```bash
  npm install --save-dev pixelmatch@7.1.0 pngjs@7.0.0
  ```

  Pin `pixelmatch@7.1.0` and `pngjs@7.0.0` because these Node 20-compatible ESM/CommonJS APIs are the exact deterministic decoder/diff APIs used by the harness; keep both `devDependencies` so neither is shipped in the XPI.

  `qmd-explorer-fixture.ts` imports and mounts `QmdWorkspaceView`, first installs `(document as Document & { createXULElement(name: string): HTMLElement }).createXULElement = (name) => { if (name !== "browser") throw new Error("unexpected XUL element"); return document.createElement("iframe"); }`, then supplies a complete real `QmdWorkspaceOptions`: `onBack`, `target`, `index`, `editors`, `openExternally`, `renderService { open, stop, diagnostic, checkDraft }`, `changeRenderService { open, stop, diagnostic }`, `prepareChange`, `refreshChangePreview`, `keepChange`, `readSource`, and `saveSource`. Its `target()` returns one complete Slice-1 `RepositoryTargetSnapshot`, including `target: { kind: "local", root, canonicalRoot, repositoryId, targetId }` and `targetEpoch`; fixture `root` is the single authority for every index/render/check/preview callback, read only as `requested.target.canonicalRoot`. `index` returns the literal `QmdExplorerIndexSnapshot`; the fixture injects the same pure `deterministicDigest` when it exercises `buildQmdExplorerIndex`. `renderService.open` first asserts/records that it received the captured fixture snapshot/root and returns exactly `https://preview.fixture/knowledge/Magic/Bell_magic.html`; the fixture calls `view.show()`, then awaits `view.open("knowledge/Magic/Bell_magic.qmd")`, verifies the iframe's `src`, and exports `window.mountQmdExplorerWorkspaceFixture`. The fixture owns the real workspace shell (toolbar, Explorer column, and render-preview pane); it must not mount `QmdFileExplorer` directly or hand-build a preview placeholder.

  Extend the existing Fix Pack B `render-harness.mjs`; reuse its module-private `PLUGIN_ROOT`, `sharedBrowser()`, `closeHarness()`, `esbuild` import, and Playwright lifecycle rather than starting a second browser or duplicating `renderSurface`, `renderDraftParity`, `routeDraftParityRequest`, or the KaTeX asset ledger. Add a small generic `bundleBrowserFixture(entryPoint)` helper next to the existing `visualEditorBundle`; it uses `platform: "browser"`, `format: "iife"`, `target: ["firefox140"]`, `write: false`, the fixture directory as `absWorkingDir`, and `loader: { ".svg": "dataurl" }` so the planned Explorer's imported icon modules are executable in the injected browser bundle. Implement `renderExplorerWorkspaceFixture` beside `renderSurface`. It creates a DPR-1 context through `sharedBrowser()`, reads the plugin CSS once from `PLUGIN_ROOT`, injects CSS plus the browser bundle with `page.setContent`, and closes only its own page/context in `finally`; the existing shared browser remains owned by `closeHarness`.

  The Explorer renderer installs a dedicated context route only for `https://preview.fixture/**`, fulfilling the iframe document with deterministic local HTML. It must not call or alter Fix Pack B's Draft-parity route/asset-ledger functions. It waits for `[data-qmd-explorer-target]` and `.zc-qmd-render-browser[src]`, returns every measured element's `src` attribute as well as geometry, and records requests after mount. Obtain all `img[data-qmd-explorer-resource-icon]` `src` values from the page and return only requests whose URL equals one of those resource URLs as `explorerIconRequests`; the test requires that scoped set to be empty. It must not make a global assertion about unrelated bundle URLs. `comparePng` decodes both images with `PNG.sync.read`, asserts equal dimensions, counts only pixelmatch differences, and divides by `width * height`. Add `after(() => closeHarness())` to `qmd-explorer.test.mjs`, matching the existing visual suites, so this fixture participates in the shared browser lifecycle.

  Run the test once with `UPDATE_QMD_EXPLORER_GOLDEN=1`; in that mode write exactly `test/visual/goldens/qmd-explorer-light-1440x900.png`, print its SHA-256, and make the test fail if this environment variable is absent and the golden is missing. Manually compare the emitted image side-by-side with `.superdesign/references/qlab-vscode-explorer-approved-light-1440x900.png`; only after the comparison is accepted rerun without the variable to enforce the 0.5% threshold.

- [ ] **Step 4: Run visual and all relevant non-packaging gates.**

  ```bash
  npm run test:visual && npx vitest run test/qmd-index.test.ts test/qmd-file-explorer.test.ts test/qmd-explorer-state.test.ts test/qmd-explorer-preferences.test.ts test/qmd-workspace.test.ts test/qmd-visual-editor.test.ts test/qmd-source-model.test.ts test/build-assets.test.ts && npm run check
  ```

  Expected: all tests PASS; the light golden differing-pixel ratio is `<= 0.005`, both viewport fixtures have no clipped Explorer/preview controls, and dark mode verifies token mapping without a second golden.

- [ ] **Step 5: Commit the visual regression fixture and golden.**

  ```bash
  git add integrations/zotero/test/visual/qmd-explorer-fixture.ts integrations/zotero/test/visual/qmd-explorer.test.mjs integrations/zotero/test/visual/goldens/qmd-explorer-light-1440x900.png integrations/zotero/test/visual/render-harness.mjs integrations/zotero/package.json integrations/zotero/package-lock.json && git commit -m "test(zotero): lock QMD Explorer Chromium regression"
  ```

**Release follow-up (not a Linux/Chromium acceptance claim):** On a macOS Zotero 9 host, manually verify the real workspace at 1440x900 and 760x720: row/twisty focus, roving tab stop, title action tooltips, sash pointer and keyboard behavior, Cmd+B, narrow overlay dismissal, selected Knowledge read-only behavior, Draft pending labels, and Quick Open/Preview/Visual Edit/Keep. Record the outcome in the release PR or tracking issue. The Linux Chromium harness cannot claim this Gecko check has run.

## Final verification and delivery check

- [ ] Run the complete release gate on macOS:

  ```bash
  cd /home/chance/workers/1/quarto-lab/integrations/zotero && npm run verify && npm run test:visual
  ```

  Expected: TypeScript clean, all Vitest suites pass, XPI build succeeds with bundled offline assets/notices, and Chromium visual tests pass. The build must not contact an icon/font CDN.

- [ ] Confirm the implementation has no old explorer remnants and no forbidden source writes:

  ```bash
  cd /home/chance/workers/1/quarto-lab && rg -n 'zc-qmd-file-toggle|is-files-collapsed|groupIntoTree\(this\.entries\)' integrations/zotero/src integrations/zotero/test && git diff --check && git status --short
  ```

  Expected: `rg` exits 1 (no obsolete bespoke-collapse renderer references); `git diff --check` has no whitespace error; status contains only the seven reviewed commits or is clean after integration.

- [ ] Verify scope against the approved specs before merge: local/SSH component parity uses the same `QmdFileExplorer`; `targetId/targetEpoch` rejects stale data; empty Draft directories render; remote disconnected cached rows cannot mutate; all create operations are Draft capability-gated; Knowledge never becomes writable; external editor and Draft promotion stay disabled for SSH; no generated or trusted knowledge source changed.
