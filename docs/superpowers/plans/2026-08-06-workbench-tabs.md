# QLab Workbench Tabs & Split Panes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the workbench's fixed "chat left / one exclusive right pane" layout with a VS Code-style system of four closable, draggable tab kinds (chat, qmd editor, Zotero PDF, main site) across at most two side-by-side panes, driven by reader-toolbar buttons A (PDF+chat) and C (PDF+editor).

**Architecture:** A pure `WorkbenchLayout` state machine plus a DOM `WorkbenchShell` own tabs, panes, and drag interactions. Existing views (`SidebarView` chat column, `QmdWorkspaceView`, `ResearchLoopSiteView`) are wrapped as `TabContentProvider`s and never reparented after mount (XUL `<browser>` elements reload when moved in the DOM — pane membership is expressed only through CSS classes). A new `WorkbenchView` composes shell + providers and implements the existing `WorkbenchTabView` contract so Zotero deck-tab plumbing (`workbench-tab.ts`) and the standalone window keep working.

**Tech Stack:** TypeScript, esbuild bundle (Zotero 9 XPI), vitest + happy-dom, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-06-workbench-tabs-design.md`

## Global Constraints

- All work in `integrations/zotero/` (plus this plan/spec under `docs/superpowers/`). Do not touch `src/app/page.tsx`, `src/app/globals.css`, `src/app/layout.tsx`, or the knowledge trust boundary.
- Gate for every task: `cd integrations/zotero && npm run verify` (tsc → vitest → build). Run at least `npx vitest run <changed tests>` + `npm run check` per task; full `verify` in the final task.
- **No-reparent rule:** after a tab's content host is appended to the shell, it is never moved in the DOM. Pane assignment/visibility = CSS classes only. A test asserts node identity across moves.
- Singletons: `chat`, `editor`, `site` (fixed tab ids equal to kind). `pdf` tabs multiply, id = `pdf:<attachmentKey>`.
- Max two panes (`left`, `right`), horizontal only. Zero-tab layout is legal (shell shows an empty state).
- All new UI copy, code, and comments in English.
- Commits on branch `feat/issue-10-remote-ssh`, one per task, message ending with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Editor write authority (`drafts/**.qmd` + change working copies) and `safeRepositoryPath` are untouched.
- CSS custom property `--zc-split-ratio` and pref `splitRatio` (int percent, clamp 25–68) remain the single source of truth for split width.

---

### Task 1: `WorkbenchLayout` pure state machine

**Files:**
- Create: `integrations/zotero/src/workbench-layout.ts`
- Test: `integrations/zotero/test/workbench-layout.test.ts`

**Interfaces:**
- Consumes: nothing (pure module).
- Produces (used by Tasks 2, 3, 6, 8):

```typescript
export type TabKind = "chat" | "editor" | "site" | "pdf";
export type PaneId = "left" | "right";

export interface PdfTabPayload { itemID: number; attachmentKey: string; page?: number }

export interface TabDescriptor {
  id: string;                // "chat" | "editor" | "site" | `pdf:${attachmentKey}`
  kind: TabKind;
  title: string;
  payload?: PdfTabPayload;   // pdf only
}

export type TabRequest =
  | { kind: "chat" | "editor" | "site"; title?: string }
  | { kind: "pdf"; title: string; payload: PdfTabPayload };

export interface PaneSnapshot { tabIds: string[]; activeTabId: string | null }
export interface LayoutSnapshot {
  panes: { left: PaneSnapshot; right: PaneSnapshot | null };
  focusedPane: PaneId;
}
export interface SerializedLayout {
  version: 1;
  tabs: Array<{ id: string; kind: string; title: string; payload?: unknown }>;
  panes: { left: PaneSnapshot; right: PaneSnapshot | null };
  focusedPane: PaneId;
}

export function tabIdFor(request: TabRequest): string;

export class WorkbenchLayout {
  constructor(onChange: () => void);
  snapshot(): LayoutSnapshot;
  tabs(): TabDescriptor[];
  tab(id: string): TabDescriptor | null;
  paneOf(id: string): PaneId | null;
  openTab(request: TabRequest, pane?: PaneId): string;  // reuse singleton / same pdf id
  closeTab(id: string): void;
  activateTab(id: string): void;
  moveTab(id: string, pane: PaneId, index?: number): void;
  arrange(left: TabRequest, right: TabRequest): void;   // idempotent
  updatePdfPage(id: string, page: number): void;
  serialize(): SerializedLayout;
  restore(data: unknown): void;                          // tolerant, drops junk
}
```

Behavioral rules (each is a test):
- `openTab` on an existing id updates title (and pdf `page`), activates it **in the pane it already occupies**, and returns the id. New tabs append to `pane ?? focusedPane` and become active; that pane becomes focused.
- `closeTab` removes the tab. A pane left empty is dissolved: an empty `right` becomes `null`; an empty `left` adopts `right`'s contents (and `right` becomes `null`). The closed pane's new active tab is its last tab. `focusedPane` always points at an existing pane.
- `moveTab` to `"right"` with no right pane creates it — unless the tab is the left pane's only tab (net no-op after normalization; return with no change event). After a move the moved tab is active in its target and the target is focused.
- `arrange(left, right)` ensures both tabs exist, moves them into their panes (creating `right`), makes each active, sets `focusedPane = "left"`. Calling it twice produces identical serialized state. Tabs not named by the spec stay where they are.
- `restore` accepts `unknown`: non-objects → default empty layout `{left: [], right: null}`; entries with unknown `kind`, duplicate ids, or pane refs to missing tabs are dropped; a pdf tab without a valid `payload.attachmentKey` (non-empty string) or numeric `itemID` is dropped.
- Every mutating call that changes state fires `onChange` exactly once.

**Steps:**

- [ ] **Step 1: Write the failing tests** — `test/workbench-layout.test.ts` covering, at minimum:

```typescript
import { describe, expect, it, vi } from "vitest";
import { WorkbenchLayout, tabIdFor } from "../src/workbench-layout";

const pdfReq = (key = "KEY1", page = 3) =>
  ({ kind: "pdf", title: `Paper ${key}`, payload: { itemID: 11, attachmentKey: key, page } }) as const;

describe("WorkbenchLayout", () => {
  it("opens singleton tabs once and reactivates on reopen", () => {
    const layout = new WorkbenchLayout(vi.fn());
    expect(layout.openTab({ kind: "chat" })).toBe("chat");
    layout.openTab({ kind: "editor" });
    expect(layout.openTab({ kind: "chat" })).toBe("chat");
    expect(layout.tabs()).toHaveLength(2);
    expect(layout.snapshot().panes.left.activeTabId).toBe("chat");
  });

  it("gives pdf tabs one id per attachment", () => {
    const layout = new WorkbenchLayout(vi.fn());
    expect(tabIdFor(pdfReq("A"))).toBe("pdf:A");
    layout.openTab(pdfReq("A"));
    layout.openTab(pdfReq("B"));
    layout.openTab(pdfReq("A", 9));
    expect(layout.tabs()).toHaveLength(2);
    expect(layout.tab("pdf:A")?.payload?.page).toBe(9);
  });

  it("collapses to a single pane when the last right tab closes", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab({ kind: "chat" });
    layout.openTab({ kind: "editor" });
    layout.moveTab("editor", "right");
    expect(layout.snapshot().panes.right?.tabIds).toEqual(["editor"]);
    layout.closeTab("editor");
    expect(layout.snapshot().panes.right).toBeNull();
    expect(layout.snapshot().focusedPane).toBe("left");
  });

  it("adopts the right pane when the left pane empties", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab({ kind: "chat" });
    layout.openTab({ kind: "editor" });
    layout.moveTab("editor", "right");
    layout.closeTab("chat");
    const snap = layout.snapshot();
    expect(snap.panes.left.tabIds).toEqual(["editor"]);
    expect(snap.panes.right).toBeNull();
  });

  it("treats moving a lone tab to the right as a no-op", () => {
    const onChange = vi.fn();
    const layout = new WorkbenchLayout(onChange);
    layout.openTab({ kind: "chat" });
    onChange.mockClear();
    layout.moveTab("chat", "right");
    expect(layout.snapshot().panes.right).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("arrange is idempotent and leaves bystander tabs alone", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab({ kind: "site" });
    layout.arrange(pdfReq("A"), { kind: "chat" });
    const first = JSON.stringify(layout.serialize());
    layout.arrange(pdfReq("A"), { kind: "chat" });
    expect(JSON.stringify(layout.serialize())).toBe(first);
    expect(layout.paneOf("site")).toBe("left");
    expect(layout.snapshot().panes.left.activeTabId).toBe("pdf:A");
    expect(layout.snapshot().panes.right?.activeTabId).toBe("chat");
  });

  it("round-trips through serialize/restore", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.openTab({ kind: "chat" });
    layout.openTab(pdfReq("A"));
    layout.moveTab("pdf:A", "right");
    const data = layout.serialize();
    const restored = new WorkbenchLayout(vi.fn());
    restored.restore(data);
    expect(restored.serialize()).toEqual(data);
  });

  it("drops unknown kinds and broken pdf payloads on restore", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.restore({
      version: 1,
      tabs: [
        { id: "chat", kind: "chat", title: "Chat" },
        { id: "x", kind: "mystery", title: "?" },
        { id: "pdf:", kind: "pdf", title: "broken", payload: { attachmentKey: "" } },
      ],
      panes: { left: { tabIds: ["chat", "x", "pdf:"], activeTabId: "x" }, right: null },
      focusedPane: "left",
    });
    expect(layout.tabs().map((t) => t.id)).toEqual(["chat"]);
    expect(layout.snapshot().panes.left.activeTabId).toBe("chat");
  });

  it("restores a default empty layout from garbage", () => {
    const layout = new WorkbenchLayout(vi.fn());
    layout.restore("nonsense");
    expect(layout.tabs()).toEqual([]);
    expect(layout.snapshot().panes.left.tabIds).toEqual([]);
    expect(layout.snapshot().panes.right).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests, confirm they fail** — `cd integrations/zotero && npx vitest run test/workbench-layout.test.ts`. Expected: module not found.
- [ ] **Step 3: Implement `src/workbench-layout.ts`** — the interface above. Keep it DOM-free. Internal normalization helper `normalize()` applies pane-dissolution rules after every mutation; mutations compare pre/post `JSON.stringify(serialize())` to decide whether to fire `onChange` (guarantees the exactly-once rule and makes no-op moves silent).
- [ ] **Step 4: Run tests, confirm pass** — same command. Expected: PASS.
- [ ] **Step 5: Commit** — `git add integrations/zotero/src/workbench-layout.ts integrations/zotero/test/workbench-layout.test.ts && git commit` message `feat(zotero): add workbench pane layout model`.

---

### Task 2: `WorkbenchShell` DOM (tab bars, content hosts, split handle, lazy mount)

**Files:**
- Create: `integrations/zotero/src/workbench-shell.ts`
- Modify: `integrations/zotero/src/styles.css` (append shell styles; removals happen in Task 4)
- Test: `integrations/zotero/test/workbench-shell.test.ts`

**Interfaces:**
- Consumes: `WorkbenchLayout`, `TabDescriptor`, `TabKind`, `PaneId` from Task 1.
- Produces (used by Tasks 3, 5, 6, 7):

```typescript
export interface TabContentProvider {
  mount(host: HTMLElement): void;  // called once, lazily, on first activation
  show(): void;
  hide(): void;
  dispose(): void;
  focus?(): void;
}
export type ProviderFactory = (tab: TabDescriptor) => TabContentProvider;

export interface WorkbenchShellOptions {
  initialSplitRatio: number;
  onSplitRatioChange(ratio: number): void;
  onLayoutChange(): void;
  onCloseRequested?(tab: TabDescriptor): boolean; // false vetoes the close
}

export function clampSplitRatio(percent: number): number; // moved here from sidebar.ts

export class WorkbenchShell {
  readonly root: HTMLElement;          // <section class="zc-workbench-shell">
  readonly layout: WorkbenchLayout;
  constructor(host: HTMLElement, doc: Document, options: WorkbenchShellOptions);
  registerFactory(kind: TabKind, factory: ProviderFactory, opts?: { retainOnClose?: boolean }): void;
  contentHost(tabId: string): HTMLElement | null;   // stable node, for tests & providers
  provider(tabId: string): TabContentProvider | null;
  sync(): void;                        // reconcile DOM with layout.snapshot()
  dock(): HTMLElement;                 // bottom-left dock container for existing buttons
  dispose(): void;
}
```

DOM contract (all children of `root`, fixed order, never re-ordered):

```
section.zc-workbench-shell[data-split="false|true"]
├─ div.zc-pane-bar[data-pane="left"]     grid r1 c1 — tab buttons
├─ div.zc-pane-bar[data-pane="right"]    grid r1 c3 — hidden when single pane
├─ button.zc-split-handle                grid r1/-1 c2 — reuses existing class + drag
├─ div.zc-shell-empty                    grid r2 c1/-1 — "Open a paper or press ⌘I" hint
├─ section.zc-tab-content[data-tab-id]   grid r2, c1 or c3 via .is-right; .is-active shows
│    (one per tab, created on demand, NEVER moved or re-appended)
├─ div.zc-workbench-dock                 absolute bottom-left (existing styles.css:210 rules)
└─ div.zc-drop-indicator[hidden]         absolute overlay (used by Task 3)
```

Tab button DOM: `button.zc-shell-tab[data-tab-id]` containing `span.zc-shell-tab-label` and `span.zc-shell-tab-close` (an `×` with `role="button"`, `aria-label="Close <title>"`). Active tab gets `.is-active`.

**Steps:**

- [ ] **Step 1: Write failing tests** — `test/workbench-shell.test.ts` with `// @vitest-environment happy-dom`:

```typescript
// @vitest-environment happy-dom
import { describe, expect, it, vi } from "vitest";
import { WorkbenchShell, type TabContentProvider } from "../src/workbench-shell";

function makeProvider(): TabContentProvider & { hostSeen: HTMLElement | null } {
  const provider = {
    hostSeen: null as HTMLElement | null,
    mount: vi.fn(function (this: any, host: HTMLElement) { provider.hostSeen = host; }),
    show: vi.fn(), hide: vi.fn(), dispose: vi.fn(),
  };
  return provider;
}

function makeShell() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const providers = new Map<string, ReturnType<typeof makeProvider>>();
  const shell = new WorkbenchShell(host, document, {
    initialSplitRatio: 40,
    onSplitRatioChange: vi.fn(),
    onLayoutChange: vi.fn(),
  });
  for (const kind of ["chat", "editor", "site", "pdf"] as const) {
    shell.registerFactory(kind, (tab) => {
      const provider = makeProvider();
      providers.set(tab.id, provider);
      return provider;
    }, kind === "chat" ? { retainOnClose: true } : undefined);
  }
  return { shell, providers };
}

describe("WorkbenchShell", () => {
  it("renders one tab bar entry per tab and marks the active one", () => {
    const { shell } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.sync();
    const bar = shell.root.querySelector('[data-pane="left"]')!;
    const labels = [...bar.querySelectorAll(".zc-shell-tab")].map((b) => b.getAttribute("data-tab-id"));
    expect(labels).toEqual(["chat", "editor"]);
    expect(bar.querySelector('.zc-shell-tab.is-active')?.getAttribute("data-tab-id")).toBe("editor");
  });

  it("mounts providers lazily, only when a tab first becomes active", () => {
    const { shell, providers } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });  // editor active, chat backgrounded
    shell.sync();
    expect(providers.get("editor")?.mount).toHaveBeenCalledOnce();
    expect(providers.get("chat")).toBeUndefined();  // never activated after sync
    shell.layout.activateTab("chat");
    shell.sync();
    expect(providers.get("chat")?.mount).toHaveBeenCalledOnce();
  });

  it("keeps the same content host node when a tab moves between panes", () => {
    const { shell } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.sync();
    const before = shell.contentHost("editor")!;
    shell.layout.moveTab("editor", "right");
    shell.sync();
    const after = shell.contentHost("editor")!;
    expect(after).toBe(before);
    expect(after.classList.contains("is-right")).toBe(true);
    expect(shell.root.getAttribute("data-split")).toBe("true");
  });

  it("collapses the grid and hides the right bar when the right pane dissolves", () => {
    const { shell } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.layout.openTab({ kind: "editor" });
    shell.layout.moveTab("editor", "right");
    shell.sync();
    shell.layout.closeTab("editor");
    shell.sync();
    expect(shell.root.getAttribute("data-split")).toBe("false");
    expect((shell.root.querySelector('[data-pane="right"]') as HTMLElement).hidden).toBe(true);
  });

  it("disposes providers on close but retains chat", () => {
    const { shell, providers } = makeShell();
    shell.layout.openTab({ kind: "chat" });
    shell.sync();
    shell.layout.openTab({ kind: "editor" });
    shell.sync();
    const closeEditor = shell.root.querySelector('[data-tab-id="editor"] .zc-shell-tab-close') as HTMLElement;
    closeEditor.click();
    shell.sync();
    expect(providers.get("editor")?.dispose).toHaveBeenCalledOnce();
    const closeChat = shell.root.querySelector('[data-tab-id="chat"] .zc-shell-tab-close') as HTMLElement;
    closeChat.click();
    shell.sync();
    expect(providers.get("chat")?.dispose).not.toHaveBeenCalled();
    expect(providers.get("chat")?.hide).toHaveBeenCalled();
    expect(shell.root.querySelector(".zc-shell-empty")?.hasAttribute("hidden")).toBe(false);
  });

  it("honors a close veto", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const shell = new WorkbenchShell(host, document, {
      initialSplitRatio: 40,
      onSplitRatioChange: vi.fn(),
      onLayoutChange: vi.fn(),
      onCloseRequested: (tab) => tab.id !== "editor",
    });
    shell.registerFactory("editor", () => makeProvider());
    shell.layout.openTab({ kind: "editor" });
    shell.sync();
    (shell.root.querySelector('[data-tab-id="editor"] .zc-shell-tab-close') as HTMLElement).click();
    shell.sync();
    expect(shell.layout.tab("editor")).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run tests, confirm fail** — `npx vitest run test/workbench-shell.test.ts`.
- [ ] **Step 3: Implement `src/workbench-shell.ts`.** Key mechanics:
  - Constructor builds the fixed DOM skeleton, appends to `host`, applies `--zc-split-ratio` from `initialSplitRatio`, wires split-handle drag (port `beginSplitDrag`/`applySplitRatio`/`clampSplitRatio` from `sidebar.ts:968-991`, persisting via `options.onSplitRatioChange` on mouseup).
  - `sync()` reconciles: tab bar buttons re-rendered from scratch (cheap); content hosts created once per tab id (`section.zc-tab-content`, appended once); classes `.is-active`/`.is-right`, `data-split`, right-bar `hidden`, and empty-state visibility updated in place. When a tab is gone from the layout: `retainOnClose` → `hide()` + keep host (also keep its layout-independent registry entry so reopening the same id reuses it); otherwise `provider.dispose()` + host removed (a disposed pdf tab that reopens gets a fresh host — allowed; the rule forbids *moving*, not removing).
  - Tab button click → `layout.activateTab`; close span click → optional veto → `layout.closeTab` (stopPropagation so it doesn't also activate).
  - `layout` is constructed with `onChange = () => { this.sync(); options.onLayoutChange(); }` so external `layout` calls are self-syncing; explicit `sync()` stays idempotent (tests call it defensively).
- [ ] **Step 4: Append shell CSS to `styles.css`** (new section at the end; the old grid rules are untouched until Task 4):

```css
/* ---- Workbench shell (tabbed panes) ---- */
.zc-workbench-shell {
  position: relative;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  grid-template-columns: minmax(0, 1fr);
  width: 100%;
  height: 100%;
  background: var(--zc-bg);
}
.zc-workbench-shell[data-split="true"] {
  grid-template-columns: minmax(280px, var(--zc-split-ratio, 50%)) 6px minmax(300px, 1fr);
}
.zc-pane-bar {
  display: flex;
  gap: 2px;
  align-items: stretch;
  min-height: 30px;
  padding: 3px 6px 0;
  overflow-x: auto;
  border-bottom: 1px solid var(--zc-border);
  background: var(--zc-bg-subtle);
  grid-row: 1;
}
.zc-pane-bar[data-pane="left"] { grid-column: 1; }
.zc-pane-bar[data-pane="right"] { grid-column: 3; }
.zc-shell-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 220px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-bottom: 0;
  border-radius: 7px 7px 0 0;
  color: var(--zc-muted);
  background: transparent;
  font: inherit;
  font-size: 11px;
  white-space: nowrap;
  cursor: pointer;
}
.zc-shell-tab.is-active {
  color: var(--zc-text);
  border-color: var(--zc-border);
  background: var(--zc-bg);
}
.zc-shell-tab-label { overflow: hidden; text-overflow: ellipsis; }
.zc-shell-tab-close { padding: 0 2px; border-radius: 4px; opacity: 0.6; }
.zc-shell-tab-close:hover { background: var(--zc-bg-hover); opacity: 1; }
.zc-shell-tab.is-dragging { opacity: 0.4; }
.zc-tab-content { display: none; grid-row: 2; grid-column: 1; min-width: 0; min-height: 0; overflow: hidden; }
.zc-workbench-shell[data-split="true"] .zc-tab-content.is-right { grid-column: 3; }
.zc-tab-content.is-active { display: block; }
.zc-workbench-shell > .zc-split-handle { grid-row: 1 / -1; grid-column: 2; display: none; }
.zc-workbench-shell[data-split="true"] > .zc-split-handle { display: block; }
.zc-shell-empty {
  display: grid;
  place-items: center;
  grid-row: 2;
  grid-column: 1 / -1;
  color: var(--zc-muted);
  font-size: 13px;
}
.zc-shell-empty[hidden] { display: none; }
.zc-drop-indicator {
  position: absolute;
  z-index: 30;
  border: 2px solid var(--zc-accent, #4a90d9);
  border-radius: 6px;
  background: color-mix(in srgb, var(--zc-accent, #4a90d9) 12%, transparent);
  pointer-events: none;
}
.zc-drop-indicator[hidden] { display: none; }
```

- [ ] **Step 5: Run tests + typecheck** — `npx vitest run test/workbench-shell.test.ts && npm run check`. Expected: PASS (check may flag unused exports — fine to leave until wired).
- [ ] **Step 6: Commit** — `feat(zotero): add workbench shell with tabbed panes`.

---

### Task 3: Pointer-based tab drag (reorder, cross-pane move, edge split)

**Files:**
- Modify: `integrations/zotero/src/workbench-shell.ts`
- Test: `integrations/zotero/test/workbench-shell-drag.test.ts`

**Interfaces:**
- Consumes: shell internals from Task 2.
- Produces: no new public API. Drag behavior contract:
  - `pointerdown` on `.zc-shell-tab` (not on the close span) arms a drag; it starts after the pointer moves > 4 px (plain clicks still activate).
  - While dragging: the source button gets `.is-dragging`; the shell computes a drop target from `elementFromPoint`-independent geometry (use `getBoundingClientRect` of bars/content region — happy-dom friendly):
    - over a pane bar → insertion index from button midpoints; indicator = thin vertical slot in the bar;
    - over the content region in split mode → that pane (append); indicator covers the pane;
    - over the content region in single-pane mode within the left/right 20% edge → split-to-that-side; indicator covers that half; the middle 60% targets the current pane (reorder-to-end).
  - `pointerup` applies exactly one `layout.moveTab(id, pane, index)` (or nothing for a same-place drop). `Escape` or `pointercancel` aborts cleanly.
  - Implemented with `setPointerCapture` on the tab button; all listeners removed on drop/abort.

**Steps:**

- [ ] **Step 1: Write failing tests** — `test/workbench-shell-drag.test.ts` (happy-dom). Synthesize `PointerEvent`s (happy-dom supports constructing them; fall back to `new MouseEvent` with `pointerId` assigned if needed — mirror whatever `qmd-workspace.test.ts` does for events). Stub `getBoundingClientRect` on bars/hosts to give the shell a 1000×600 geometry. Cover:
  - drag editor tab from left bar to right 20% edge in single-pane mode → `data-split="true"`, editor in right pane;
  - drag it back onto the left bar → split collapses (last right tab left the pane);
  - a 2 px jitter press-release still activates the tab and moves nothing;
  - during drag the indicator is unhidden and positioned; after drop it is hidden.
- [ ] **Step 2: Run, confirm fail.**
- [ ] **Step 3: Implement drag in `workbench-shell.ts`** per the contract above. Keep geometry pure: `private dropTargetAt(x: number, y: number): { pane: PaneId; index?: number; split?: PaneId } | null` so tests can also call it directly if event synthesis proves flaky in happy-dom.
- [ ] **Step 4: Run tests + `npm run check`. Expected: PASS.**
- [ ] **Step 5: Commit** — `feat(zotero): drag workbench tabs between panes`.

---

### Task 4: Extract the chat column; delete the exclusive right-pane interlock

**Files:**
- Modify: `integrations/zotero/src/sidebar.ts`
- Modify: `integrations/zotero/src/styles.css` (rewrite the `1033–1135` region; delete `is-main-site-open` / `is-workspace-open` rules)
- Modify: `integrations/zotero/src/research-loop-site.ts` (make `onBack` optional; no back button when absent)
- Test: existing suite must stay green; adjust affected tests.

**Interfaces:**
- Consumes: nothing new.
- Produces (used by Tasks 5–6): `SidebarView` in workbench surface renders **only the chat column** inside a `div.zc-chat-pane` wrapper (history rail, thread tabs, context card, transcript, composer, login layer, terminal drawer all inside it). Public API removed: `activateMainSite`, `refreshMainSiteStatus`, `isMainSiteOpen`, `setMainSiteOpen`, `setWorkspaceOpen`, `attachWorkspace`, `workspace`. `SidebarCallbacks` loses `onCheckMainSite`, `onCheckMainSiteRepository`, `onDeployMainSite`, `onOpenDocument` (they move to the site tab in Task 5; grep confirms and updates every reference). The split handle, `clampSplitRatio`, `beginSplitDrag`, `applySplitRatio`, and the `splitRatio` field leave `sidebar.ts` (now owned by the shell). `ResearchLoopSiteViewOptions.onBack` becomes optional; when omitted the "← Back to AI" button is not created.

**Steps:**

- [ ] **Step 1: Map every affected call site**:

```bash
cd integrations/zotero
grep -n "setMainSiteOpen\|isMainSiteOpen\|setWorkspaceOpen\|attachWorkspace\|refreshMainSiteStatus\|mainSiteOpen\|activateMainSite\|onDeployMainSite\|onCheckMainSite\|splitHandle\|beginSplitDrag\|clampSplitRatio\|onBack" src/*.ts test/*.ts | tee /tmp/claude-interlock-sites.txt
```

Fix every hit as part of this task (plugin.ts references get temporary stubs only if unavoidable; prefer landing Task 6's wiring for `plugin.ts` in the same commit if the tree can't compile otherwise — in that case merge Task 4 and Task 6 commits and say so in the commit body).
- [ ] **Step 2: Restructure `SidebarView.build()`** (`sidebar.ts:574-845`): create `const chatPane = this.doc.createElement("div"); chatPane.className = "zc-chat-pane";` and append `historyRail?`, `threadTabs`, `contextCard`, `transcript`, `composerWrap`, `loginLayer`, `terminalDrawer` into it; `root` now receives `topbar` (sidebar surface only), `chatPane`, and `topActions` (workbench surface only — until Task 6 relocates the dock to the shell). Delete `splitHandle` creation (819-823) and the `mainSiteButton` block (605-614), `mainSiteView` construction (838-844), and the methods listed above (890-1006 region). Keep `setTerminalOpen` (drawer is inside `zc-chat-pane` now).
- [ ] **Step 3: Rewrite the CSS region** (`styles.css` 1033-1135): `.zc-chat-pane` becomes the chat grid —

```css
.zc-chat-pane {
  position: relative;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  grid-template-columns: minmax(0, 1fr);
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
}
.zc-workbench-chat.is-history-open .zc-chat-pane {
  grid-template-columns: 224px minmax(0, 1fr);
}
.zc-chat-pane > .zc-history-rail { grid-column: 1; grid-row: 1 / 5; }
.zc-workbench-chat.is-history-open .zc-chat-pane > :is(.zc-thread-tabs, .zc-context-card, .zc-transcript, .zc-composer-wrap) { grid-column: 2; }
.zc-chat-pane > .zc-login-layer,
.zc-chat-pane > .zc-terminal-drawer { position: absolute; inset: 0; }
.zc-workbench-chat.is-history-open .zc-chat-pane > :is(.zc-login-layer, .zc-terminal-drawer) { left: 224px; }
```

Delete every `.is-main-site-open` / `.is-workspace-open` selector (including `styles.css:1839-1849`'s handle-visibility variant — the shell rules from Task 2 replace it). `.zc-main-site-view` and `.zc-qmd-workspace` keep their internal rules but lose `grid-column: 3; grid-row: 1 / -1` placement (their tab content host handles that); give both `width: 100%; height: 100%`.
- [ ] **Step 4: `research-loop-site.ts`** — `onBack?: () => void`; wrap back-button creation (412-416, 435) in `if (this.options.onBack)`.
- [ ] **Step 5: Run the full plugin suite** — `npx vitest run`. Fix fallout listed in `/tmp/claude-interlock-sites.txt` (notably `workbench-tab.ts`'s `isMainSiteOpen`/`setMainSiteOpen` uses at lines 24-25, 107, 167-169, 197 — if Task 6 is not merged in, temporarily keep those interface members as optional no-ops and delete them in Task 6). `npm run check` clean.
- [ ] **Step 6: Commit** — `refactor(zotero): extract chat pane, drop right-pane interlock`.

---

### Task 5: Site tab (`SiteTabView`) with the deploy state machine as its empty state

**Files:**
- Create: `integrations/zotero/src/site-tab.ts`
- Test: `integrations/zotero/test/site-tab.test.ts`

**Interfaces:**
- Consumes: `TabContentProvider` (Task 2), `ResearchLoopSiteView` and `QLabRepositoryState`.
- Produces (used by Task 6):

```typescript
export interface SiteTabCallbacks {
  checkSite(): Promise<boolean>;
  checkRepository(): Promise<QLabRepositoryState>;
  deploy(onProgress: (message: string) => void): Promise<void>;
  chooseRepository(): Promise<void>;
  onOpenDocument(relativePath: string): void;
}
export class SiteTabView implements TabContentProvider {
  constructor(doc: Document, callbacks: SiteTabCallbacks);
  mount(host: HTMLElement): void;
  show(): void; hide(): void; dispose(): void;
}
```

Behavior (ported from `sidebar.ts` `refreshMainSiteStatus`/`activateMainSite`, `sidebar.ts:847-930`, rendered as a status card instead of button classes):
- `show()` runs the status check. Repository `missing`/`incompatible` → card with explanation + **Choose Repository** button (`chooseRepository` then re-check). `empty`/`partial` → card + **Initialize** wording routed through `deploy`. Repository `ready` but site down → card + **Build & Start** button; while deploying the button is disabled and shows `onProgress` messages. Site available → hide the card, show `ResearchLoopSiteView` (constructed lazily on first success, with `onBack` omitted and `onOpenDocument` forwarded).
- Deploy failure → card shows `Retry Main Site: <message>` and stays actionable. `dispose()` destroys the site view (browser discarded per spec close semantics).

**Steps:**

- [ ] **Step 1: Write failing tests** — happy-dom; fake callbacks with controllable promises. Cover: ready+available shows the site view and no card; site-down click runs `deploy` with progress text reaching the DOM and then reveals the site view; `missing` renders Choose Repository and re-checks after it resolves; deploy rejection renders the retry label. (`ResearchLoopSiteView.ensureBrowser` already degrades in happy-dom via its `createXULElement` guard — assert on `.zc-main-site-view` presence, not on a live browser.)
- [ ] **Step 2: Run, confirm fail.**
- [ ] **Step 3: Implement `src/site-tab.ts`** and add card styles to `styles.css` (`.zc-site-status-card` — reuse the muted card look of `.zc-main-site-unavailable`).
- [ ] **Step 4: Run tests + `npm run check`. Expected: PASS.**
- [ ] **Step 5: Commit** — `feat(zotero): move main-site status flow into a site tab`.

---

### Task 6: `WorkbenchView` composition, plugin wiring, session persistence

**Files:**
- Create: `integrations/zotero/src/workbench-view.ts`
- Modify: `integrations/zotero/src/workbench-tab.ts`
- Modify: `integrations/zotero/src/plugin.ts` (`createWorkbenchView` 1870-1972, `openQmdDocument` 1980-2039, `openWorkbenchTab` 2441-2489)
- Modify: `integrations/zotero/src/standalone-workbench.ts` (type only, if its `StandaloneWorkbenchView` needs the new members)
- Test: `integrations/zotero/test/workbench-view.test.ts`; update `test/standalone-workbench.test.ts` and any test from the Task 4 grep still referencing `mainSiteOpen`.

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces:

```typescript
// workbench-view.ts
export interface WorkbenchViewCallbacks {
  chatCallbacks: SidebarCallbacks;                       // pass-through to SidebarView
  siteCallbacks: SiteTabCallbacks;
  createWorkspace(host: HTMLElement): QmdWorkspaceView;  // plugin's existing option bundle
  createPdfProvider(tab: TabDescriptor): TabContentProvider; // Task 7 (stub here: error card)
  initialSplitRatio: number;
  onSplitRatioChange(ratio: number): void;
  onLayoutChanged(): void;                               // plugin calls Zotero.Session.debounceSave
}
export class WorkbenchView {
  constructor(host: HTMLElement, callbacks: WorkbenchViewCallbacks);
  // WorkbenchTabView contract:
  show(): void; destroy(): void; focusComposer(text?: string): void; setState(next: any): void;
  layoutData(): SerializedLayout;
  setLayoutData(data: unknown): void;
  workspace(): QmdWorkspaceView | null;
  // arrangement API (Task 8 uses it):
  arrange(kind: "pdf-chat" | "pdf-editor", pdf: { itemID: number; attachmentKey: string; title: string; page?: number } | null): void;
  openEditorDocument(relativePath: string, options?: QmdWorkspaceOpenOptions): Promise<boolean>;
  chat(): SidebarView;
  shell: WorkbenchShell;
}
```

```typescript
// workbench-tab.ts
export interface WorkbenchTabData {
  itemID?: number | string;
  icon?: string;
  title: string;
  layout?: unknown;            // replaces mainSiteOpen
}
export interface WorkbenchTabView {
  show(): void; destroy(): void; focusComposer(text?: string): void; setState(next: any): void;
  layoutData?(): unknown;
  setLayoutData?(data: unknown): void;
  workspace?(): QmdWorkspaceView | null;
}
```

Wiring rules:
- `WorkbenchView` constructor: builds `WorkbenchShell`, registers factories — `chat` (retainOnClose, wraps a `SidebarView` mounted into the tab host; the workbench dock moves to `shell.dock()`: append the standalone/terminal/account buttons there via a small `SidebarView.dockButtons()` accessor added in this task), `editor` (provider wrapping `callbacks.createWorkspace(host)`, dirty-close veto via the workspace's existing unsaved state — expose `QmdWorkspaceView.hasUnsavedChanges(): boolean` if not present, veto with a `window.confirm` in the shell's `onCloseRequested`), `site` (`new SiteTabView(...)`), `pdf` (`callbacks.createPdfProvider`). Default fresh layout: chat tab alone in the left pane.
- `workbench-tab.ts`: `zoteroData` writes `qlabLayout: JSON.stringify(data.layout)` when present; `dataFromTab` parses it (`try/catch` → `undefined`) and maps legacy `raw.qlabMainSiteOpen === true` to the preset `{version:1, tabs:[{id:"chat",kind:"chat",title:"Chat"},{id:"site",kind:"site",title:"Main Site"}], panes:{left:{tabIds:["chat"],activeTabId:"chat"}, right:{tabIds:["site"],activeTabId:"site"}}, focusedPane:"left"}`. `open()` line 197 becomes `if (data.layout !== undefined) view.setLayoutData?.(data.layout);`; `moveToNewWindow` line 107 carries `layout: sourceEntry?.view.layoutData?.() ?? tabData.layout`.
- `plugin.ts createWorkbenchView` returns `WorkbenchView`; the former `SidebarCallbacks` members `onCheckMainSite`/`onCheckMainSiteRepository`/`onDeployMainSite` become `siteCallbacks` (`deploy` also keeps the `activateRepositoryTarget` call, `plugin.ts:1963-1968`); `onOpenDocument` becomes `siteCallbacks.onOpenDocument = (path) => void workbenchView.openEditorDocument(path)`. `openQmdDocument(view: WorkbenchView, ...)` drops `attachWorkspace`/`setWorkspaceOpen` and instead: `view.shell.layout.openTab({kind:"editor"})` (shell mounts the workspace via the factory), then `view.workspace()!.open(relativePath, options)` — same option bundle as today (`plugin.ts:1990-2028`). `onLayoutChanged` → `Zotero.Session?.debounceSave?.()` plus `this.workbenchTabs.update(win, tabID, {...entry.data, layout: view.layoutData()}, false)` so the deck tab's stored data stays fresh.
- Lazy mount on restore is free: `setLayoutData` → `layout.restore` → `sync()` mounts only active tabs (Task 2 behavior).

**Steps:**

- [ ] **Step 1: Write failing tests** — `test/workbench-view.test.ts` (happy-dom): fresh view exposes a chat tab in the left pane; `setLayoutData` with a chat+editor split creates hosts only for active tabs; `layoutData()` round-trips; `workspace()` is null before the editor tab first activates and non-null after; legacy-mainSiteOpen mapping test lives in `test/workbench-tab.test.ts`-style assertions on `dataFromTab` (add to the existing workbench-tab test file if present, else create `test/workbench-tab-data.test.ts`).
- [ ] **Step 2: Run, confirm fail.**
- [ ] **Step 3: Implement** `workbench-view.ts`, `workbench-tab.ts` changes, `plugin.ts` rewiring, `standalone-workbench.ts` type updates. Remove any temporary stubs left by Task 4.
- [ ] **Step 4: Run the full suite** — `npx vitest run && npm run check`. Expected: PASS, no remaining references to `mainSiteOpen` outside the legacy-mapping code (`grep -rn "mainSiteOpen" src/ | grep -v qlabMainSiteOpen` → empty).
- [ ] **Step 5: Commit** — `feat(zotero): compose workbench tabs behind WorkbenchView`.

---

### Task 7: `PdfReaderView` — embedded reader with graceful fallback

**Files:**
- Create: `integrations/zotero/src/pdf-tab.ts`
- Modify: `integrations/zotero/src/plugin.ts` (implement `createPdfProvider`)
- Test: `integrations/zotero/test/pdf-tab.test.ts`
- Create: `docs/superpowers/2026-08-06-pdf-embed-spike.md` (findings template + manual validation steps)

**Interfaces:**
- Consumes: `TabContentProvider`, `PdfTabPayload`.
- Produces:

```typescript
export interface PdfTabDeps {
  resolveFileURI(itemID: number): Promise<string | null>; // plugin: item.getFilePathAsync → Zotero.File.pathToFileURI
  createNativeEmbed?(host: HTMLElement, itemID: number, page?: number): Promise<PdfEmbedHandle | null>;
  createBrowserViewer(host: HTMLElement, fileURI: string, page?: number): PdfEmbedHandle;
  onRequestChoosePaper(): void;
  onPageChange?(page: number): void;   // updates layout payload for persistence
}
export interface PdfEmbedHandle { goToPage(page: number): void; dispose(): void }
export class PdfReaderView implements TabContentProvider {
  constructor(doc: Document, payload: PdfTabPayload, deps: PdfTabDeps);
  goToPage(page: number): void;        // Task 8 uses this for chat page links
  mount/show/hide/dispose;
}
```

Strategy chain on first `show()` (async, with an in-tab "Loading PDF…" placeholder):
1. `deps.createNativeEmbed` (when provided) — the **spike**: plugin-side implementation tries, in order, Zotero 7's item-pane `attachment-preview` custom element, then manual `ReaderInstance` construction; each attempt in try/catch with `Zotero.debug` logging. Returns `null` on any failure.
2. `deps.createBrowserViewer` — plugin-side: a XUL content browser whose `src` is the attachment `file://` URI plus `#page=N`; Firefox's built-in pdf.js provides paging/zoom/search read-only. `goToPage` re-sets `src` only when the page differs.
3. `resolveFileURI` returning `null` (missing/moved attachment) → error card: title, explanation, and a **Choose Paper** button calling `onRequestChoosePaper`.

Any embed handle failure after creation (thrown from `goToPage` etc.) is caught and swaps in the error card with a **Reload** button that reruns the chain — the tab-level error boundary from the spec.

**Steps:**

- [ ] **Step 1: Write failing tests** — happy-dom, fake deps: native embed success short-circuits the browser fallback; native `null` → browser viewer created with `#page=`; `resolveFileURI` null → error card with Choose Paper wired; `goToPage` delegates to the active handle and reports `onPageChange`; a handle that throws flips to the error card and Reload reruns the chain.
- [ ] **Step 2: Run, confirm fail.**
- [ ] **Step 3: Implement `src/pdf-tab.ts`** + error-card styles (`.zc-pdf-error-card`).
- [ ] **Step 4: Implement the plugin side of `createPdfProvider`** in `plugin.ts`: `resolveFileURI` via `Zotero.Items.get(itemID)?.getFilePathAsync()` + `Zotero.File.pathToFileURI`; `createBrowserViewer` mirroring `ResearchLoopSiteView.ensureBrowser` (`research-loop-site.ts:463-485`) but `src = fileURI#page=N` and no remote-location tracking; `createNativeEmbed` implementing the two spike attempts behind try/catch (this code is the spike — keep each attempt ≤ ~40 lines and heavily logged).
- [ ] **Step 5: Write `docs/superpowers/2026-08-06-pdf-embed-spike.md`** — what was attempted, what compiled, and a numbered manual validation checklist for live Zotero (open paper → button A → does the PDF tab show the native reader or the pdf.js fallback; annotations; page sync), with a Findings section left for results from the live run.
- [ ] **Step 6: Run tests + `npm run check`. Expected: PASS.**
- [ ] **Step 7: Commit** — `feat(zotero): embed pdf reading in a workbench tab`.

---

### Task 8: Buttons A and C, ⌘I, and chat page-link routing

**Files:**
- Modify: `integrations/zotero/src/plugin.ts` (`registerReaderHooks` 999-1058, shortcut handler ~852-880, `openWorkbenchTab` 2441-2489, `openConversationPDFPage` — locate via grep)
- Test: `integrations/zotero/test/workbench-view.test.ts` (arrange coverage); plugin-level tests only where existing plugin tests already fake `Zotero` (follow `test/plugin-ai-context.test.ts` patterns; otherwise cover via `WorkbenchView.arrange` unit tests).

**Interfaces:**
- Consumes: `WorkbenchView.arrange` (Task 6), `PdfReaderView.goToPage` (Task 7).
- Produces: `openWorkbenchTab(win?, options?: { arrangement?: "pdf-chat" | "pdf-editor" })`.

Wiring:
- `openWorkbenchTab` gains the options parameter. After the entry exists (both the existing-entry path at 2447-2457 and the fresh-open path at 2478-2488): when `options?.arrangement` is set and `this.context` holds an attachment, call `entry.view.arrange(options.arrangement, { itemID, attachmentKey, title: paperTitle(context), page })` — pull the exact context field names with `grep -n "attachment" src/reader-context.ts | head -30` before coding (`context.attachment.id` is confirmed at `plugin.ts:2473`; find the key and current-page fields the same way). With no attachment context, `arrange` is skipped (workbench opens as today).
- **Button A** (`plugin.ts:1015-1019`): click handler passes `{ arrangement: "pdf-chat" }`. Title stays "Open QLab Local Codex (⌘I)".
- **Button C**: duplicate the button-A block after it — `button.title = "Open PDF beside the QMD editor"`, a distinct bundled data-URL SVG icon (add `readerEditorIcon` next to the existing `readerToolbarIcon` import at `plugin.ts:2`; a simple split-rectangle glyph), click → `acceptReaderHook(event)` then `openWorkbenchTab(win, { arrangement: "pdf-editor" })`.
- **⌘I** (`plugin.ts:875`): pass `{ arrangement: "pdf-chat" }` when the selected tab is a reader tab (the surrounding handler already knows; otherwise no arrangement).
- **Chat page links**: in `openConversationPDFPage`, before the native-reader path: find the active window's workbench entry (`this.workbenchTabs.entries(win)`), and if its layout has tab `pdf:<attachmentKey>` for the reference, activate that tab (`view.shell.layout.activateTab`) + `(provider as PdfReaderView).goToPage(reference.page)` + select the workbench deck tab; else fall through to the existing behavior.

**Steps:**

- [ ] **Step 1: Extend `workbench-view.test.ts`** with failing arrange cases: `arrange("pdf-chat", pdf)` from a fresh view yields left=`pdf:KEY` active / right=`chat` active; `arrange("pdf-editor", pdf)` flips right to editor while chat stays open in the right pane's tab list only if it was already there (it was: singleton stays where it lives — assert it remains in its pane, editor becomes the right-active tab); repeated arrange is stable.
- [ ] **Step 2: Run, confirm fail.**
- [ ] **Step 3: Implement** `WorkbenchView.arrange` (thin: translate to `layout.arrange` requests) and the `plugin.ts` wiring above.
- [ ] **Step 4: Run full suite + `npm run check`. Expected: PASS.**
- [ ] **Step 5: Commit** — `feat(zotero): reader buttons arrange pdf/chat and pdf/editor splits`.

---

### Task 9: Full verification, docs, and live-Zotero QA handoff

**Files:**
- Modify: `integrations/zotero/CHANGELOG.md` (entry under the next version)
- Modify: `docs/superpowers/2026-08-06-pdf-embed-spike.md` (finalize checklist)
- Modify: `docs/superpowers/specs/2026-08-06-workbench-tabs-design.md` (record the two approved deviations: ① the spike ships as a runtime strategy chain instead of blocking implementation; ② with the chat tab closed, the terminal button reopens chat in the focused pane and then opens the drawer, which keeps the drawer inside the chat DOM)

**Steps:**

- [ ] **Step 1: Terminal-with-chat-closed behavior** — in `WorkbenchView`, the dock terminal button callback first ensures the chat tab exists/is active in the focused pane (`layout.openTab({kind:"chat"}, focusedPane)`), then toggles the drawer. Add a unit test.
- [ ] **Step 2: Full gate** — `cd integrations/zotero && npm run verify`. Expected: tsc clean, all vitest suites pass, esbuild bundle succeeds. Fix anything that surfaces.
- [ ] **Step 3: Repo-level sanity** — `git status` shows only intended files; `grep -rn "is-main-site-open\|is-workspace-open" integrations/zotero/src` → empty.
- [ ] **Step 4: Update CHANGELOG + spec deviations + finalize the spike QA checklist** (numbered steps for the user to run in live Zotero: install XPI, button A/C flows, drag between panes, close semantics, restart-restore, legacy-session restore).
- [ ] **Step 5: Commit** — `docs(zotero): record workbench tabs verification and QA handoff`.

---

## Self-Review Notes

- Spec coverage: goals 1–6 map to Tasks 1–3 (tabs/panes/drag), 4–6 (independence + interlock removal + persistence), 7 (native reader + fallback + error boundaries), 8 (buttons A/C/⌘I/page links), 9 (terminal edge case, verification). Site-tab deploy state machine: Task 5. Lazy mount: Tasks 2/6.
- Deviations from the spec are deliberate and recorded in Task 9: runtime strategy chain instead of a blocking spike (the agent cannot run live Zotero; the user validates via the QA checklist), and the terminal-drawer simplification.
- Type consistency: `TabContentProvider`, `TabDescriptor`, `SerializedLayout`, `SiteTabCallbacks`, `PdfTabDeps`, `WorkbenchViewCallbacks` are each defined once (Tasks 1, 2, 5, 6, 7) and consumed by name elsewhere.
