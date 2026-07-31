# Zotero Fix Pack A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four approved Zotero-plugin issues — dead Research Action chips, Visual Edit / Website Preview visual parity, region screenshots to chat, and reopening a paper's conversation without its PDF open.

**Architecture:** Four independent sections, each a short series of test-first commits that never mix sections. All changes live in `integrations/zotero/` (plus one line in `drafts/_quarto.yml`); each section extends an existing proven pipeline (runResearchAction dispatch, renderMarkdown, pendingScreenshots, chooseWorkbenchPaper background-open) rather than adding new subsystems.

**Tech Stack:** TypeScript Zotero 7 plugin; vitest (`// @vitest-environment happy-dom` pragma + `test/setup-dom.ts` shim); esbuild via `scripts/build.mjs`; Quarto draft preview; KaTeX 0.18.1.

**Spec:** `docs/superpowers/specs/2026-07-31-zotero-fix-pack-design.md` (user-approved). Implement exactly; no extra scope.

## Global Constraints

- Test-first inside every task: the failing test is written and observed to fail before the implementation exists.
- Test commands run from `/home/chance/quarto-lab/integrations/zotero`: `npx vitest run test/<file>.test.ts`; gate before every commit: `npm run verify` (tsc --noEmit + full vitest + build).
- Commits run from `/home/chance/quarto-lab`; messages follow `fix(zotero): ...` / `feat(zotero): ...`; no commit mixes content from two sections.
- Implement sections in order 1 -> 2 -> 3 -> 4 (sections 1, 3, 4 all modify `src/plugin.ts`; ordering keeps each section's edit anchors valid).
- `knowledge/_quarto.yml` (published site) is never touched; only `drafts/_quarto.yml` gains `html-math-method: katex`.
- Chat invariants: chat math sizing stays 1.04em within `.zc-entry-content`; chat newline-as-`<br>` behavior unchanged; the independence contract test `test/codex-service.test.ts:529-598` keeps passing unchanged.

---

## Section 1 — Research Action chips fix

**Spec:** `docs/superpowers/specs/2026-07-31-zotero-fix-pack-design.md`, "Design 1 — Research Action chips fix". All paths below are relative to the repo root `/home/chance/quarto-lab` unless shown absolute.

**Context for the implementer (read this once, then follow the steps literally):** The Summarize / Evidence QA / Compare Papers chips above the chat composer do nothing. `SidebarView.renderResearchActions` (`integrations/zotero/src/sidebar.ts:1028-1058`) wires each chip's click to the *optional* callback `this.callbacks.onResearchAction?.(action.id)` (`sidebar.ts:1055`; declared optional at `sidebar.ts:225`). The only construction that supplies that callback is `mountChat` (`integrations/zotero/src/plugin.ts:930-933`) — a surface that never mounts (its `registerSection` at `plugin.ts:551` has no call site). Every live chat surface (Workbench tab, standalone window) is built by `createWorkbenchView` (`plugin.ts:1238-1343`), which renders the chips but omits `onResearchAction`, so clicks optional-chain to `undefined` — a guaranteed silent no-op. A secondary hazard: `renderResearchActions` calls `this.actionStrip.replaceChildren()` on every `setState` (`sidebar.ts:1030`, render loop at `sidebar.ts:415-421`, `sidebar.ts:1005`), so a re-render landing between mousedown and mouseup (frequent while a turn streams) destroys the button before its click event fires.

Two tasks, two test-first commits. Do not touch `mountChat`, `styles.css`, `research-actions.ts`, or anything belonging to spec Designs 2–4.

**Commands & environment:** tests run from `/home/chance/quarto-lab/integrations/zotero` with `npx vitest run test/<file>.test.ts`; the full gate is `npm run verify` (tsc `--noEmit` + full vitest + build) and must pass before each commit. Commits run from `/home/chance/quarto-lab`. Tests are vitest with happy-dom; every DOM test file starts with the `// @vitest-environment happy-dom` pragma (the vitest default env is node; `integrations/zotero/test/setup-dom.ts` only patches `document.compatMode` and is loaded automatically via `vitest.config.ts` `setupFiles`).

**One spec-vs-code note (verified against source, do not "fix" it):** the spec and task brief say to compare the actions' "disabled flags", but `ResearchActionView` (`integrations/zotero/src/sidebar.ts:140-145`) has no `disabled` field — its exact shape is `{ id: string; label: string; description: string; icon: string }` — and chips are never disabled anywhere in `sidebar.ts`. The comparison therefore covers every field that affects the rendered strip: per-action `id`/`label`/`description`/`icon`, plus the `researchObject`'s `kind`/`label` (the strip renders an object-label span from it, and the strip's `hidden` state is derived entirely from object-presence + action count, so "strip hidden state" is covered by the same comparison). Do NOT add a `disabled` field to `ResearchActionView` — that would be new scope.

### Task 1.1: Wire `onResearchAction` into `createWorkbenchView` (plugin-level)

**Files:**
- Create: `integrations/zotero/test/plugin-research-actions.test.ts`
- Modify: `integrations/zotero/src/plugin.ts:1315-1318` (inside the `createWorkbenchView` callbacks object literal)

**Interfaces:**
- Consumes: `SidebarCallbacks.onResearchAction?(actionId: string): void` (`src/sidebar.ts:225`); `private createWorkbenchView(host: HTMLElement, win: Window, tabID: string): SidebarView` (`src/plugin.ts:1238`); `private async runResearchAction(view: Pick<SidebarView, "focusComposer">, rawActionID: string, win?: Window): Promise<void>` (`src/plugin.ts:3683-3687`); `private reportError(error: unknown): void` (`src/plugin.ts:3761`); `SidebarView.setState(next: Partial<SidebarState>): void` (`src/sidebar.ts:415`); `SidebarView.destroy(): void` (`src/sidebar.ts:397`).
- Produces: no new exports and no new functions — one new property on the existing callbacks object literal in `createWorkbenchView`. Nothing in Task 1.2 or any other section depends on new symbols from this task.

- [ ] **Step 1: Write the failing plugin-level wiring test.** Create `integrations/zotero/test/plugin-research-actions.test.ts` with exactly this content. It follows the `new ZoteroChatPlugin() as any` private-member pattern used throughout `test/plugin-state.test.ts` (e.g. its lines 94, 118) and stubs `runResearchAction` on the instance so no `Zotero` global is needed; the plugin constructor and `SidebarView` both work bare in happy-dom (`prefInt` in `src/platform.ts:43-50` and `refreshMainSiteStatus` in `src/sidebar.ts:830-846` are try/catch-guarded, so missing `Services`/`mainSite` fall back silently — verified):

  ```ts
  // @vitest-environment happy-dom

  import { afterEach, describe, expect, it, vi } from "vitest";

  import { ZoteroChatPlugin } from "../src/plugin";

  // createWorkbenchView is the factory behind every live chat surface (the
  // Workbench tab and the standalone window). test/sidebar.test.ts:119-141
  // proves SidebarView forwards chip clicks WHEN a callback is supplied; this
  // file proves the plugin actually supplies one. Without the wiring, the
  // chip click resolves to `this.callbacks.onResearchAction?.(...)` on
  // undefined — a silent no-op (src/sidebar.ts:1055).
  describe("Workbench Research Action wiring", () => {
    afterEach(() => {
      document.body.replaceChildren();
    });

    it("dispatches runResearchAction when a chip is clicked in a Workbench view", () => {
      const host = document.createElement("div");
      document.body.appendChild(host);
      const plugin = new ZoteroChatPlugin() as any;
      plugin.runResearchAction = vi.fn(async () => {});

      const view = plugin.createWorkbenchView(host, window, "qlab-tab");
      view.setState({
        phase: "ready",
        researchObject: { kind: "pdf", label: "A Test Paper" },
        researchActions: [{
          id: "summarize",
          label: "Summarize",
          description: "Summarize the selected object with traceable evidence.",
          icon: "≡",
        }],
      });

      host.querySelector<HTMLButtonElement>(".zc-research-action")!.click();

      expect(plugin.runResearchAction).toHaveBeenCalledWith(view, "summarize", window);

      view.destroy();
    });
  });
  ```

- [ ] **Step 2: Run the test and confirm it fails on the missing callback.** From `/home/chance/quarto-lab/integrations/zotero` run:

  ```bash
  npx vitest run test/plugin-research-actions.test.ts
  ```

  Expected: 1 test fails with `AssertionError: expected "spy" to be called with arguments: [ …, 'summarize', … ]` and `Number of calls: 0` — the chip renders and the click fires, but `createWorkbenchView` supplies no `onResearchAction`, so the optional chain at `src/sidebar.ts:1055` does nothing. If the failure is anything else (e.g. a crash before the click), stop and diagnose; do not change the test to pass.

- [ ] **Step 3: Add the wiring in `createWorkbenchView`.** In `integrations/zotero/src/plugin.ts`, the three-line `onCaptureChatDraft` block appears twice (mountChat `:927-929` and createWorkbenchView `:1315-1317`), so the edit anchor includes the following `onChoosePaper` line to be unique. Replace this (at `plugin.ts:1315-1318`):

  ```ts
        onCaptureChatDraft: () => {
          void this.captureChatDraft().catch((error) => this.reportError(error));
        },
        onChoosePaper: () => {
  ```

  with this (`view` and `win` are already in scope: `let view!: SidebarView` at `plugin.ts:1239` and the `win: Window` parameter at `plugin.ts:1238`; the `.catch` routing matches the `mountChat` wiring at `plugin.ts:930-933` exactly, so guard errors thrown inside `runResearchAction` — "Compare Papers needs at least one additional paper", etc. — surface in the visible status area via `reportError`, `plugin.ts:3761-3770` → `sidebar.ts:1020-1025`):

  ```ts
        onCaptureChatDraft: () => {
          void this.captureChatDraft().catch((error) => this.reportError(error));
        },
        onResearchAction: (actionID) => {
          void this.runResearchAction(view, actionID, win)
            .catch((error) => this.reportError(error));
        },
        onChoosePaper: () => {
  ```

- [ ] **Step 4: Run the test and confirm it passes.** From `/home/chance/quarto-lab/integrations/zotero`:

  ```bash
  npx vitest run test/plugin-research-actions.test.ts
  ```

  Expected: 1 passed, 0 failed.

- [ ] **Step 5: Run the full gate.** From `/home/chance/quarto-lab/integrations/zotero`:

  ```bash
  npm run verify
  ```

  Expected: `tsc --noEmit` clean, all vitest suites pass, build succeeds. This also confirms the arrow parameter `actionID` type-infers correctly against `onResearchAction?(actionId: string): void`.

- [ ] **Step 6: Commit (wiring only — nothing from Task 1.2 or other spec sections).** From `/home/chance/quarto-lab`:

  ```bash
  git add integrations/zotero/src/plugin.ts integrations/zotero/test/plugin-research-actions.test.ts && git commit -m "fix(zotero): wire Research Action chips on Workbench surfaces" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  ```

### Task 1.2: Skip rebuilding unchanged Research Action chips (`SidebarView`)

**Files:**
- Modify: `integrations/zotero/src/sidebar.ts:281-287` (insert comparison helper above `export class SidebarView`), `integrations/zotero/src/sidebar.ts:299` (add private field after `actionStrip`), `integrations/zotero/src/sidebar.ts:1028-1034` (guard at the top of `renderResearchActions`)
- Test: `integrations/zotero/test/sidebar.test.ts:119-141` (new test inserted immediately after the existing chip test)

**Interfaces:**
- Consumes: `interface ResearchObjectView { kind: "pdf" | "note" | "collection" | "draft"; label: string }` (`src/sidebar.ts:135-138`); `interface ResearchActionView { id: string; label: string; description: string; icon: string }` (`src/sidebar.ts:140-145`); `SidebarView.setState(next: Partial<SidebarState>): void` (`src/sidebar.ts:415-421`); the existing `callbacks()` factory and `// @vitest-environment happy-dom` harness in `test/sidebar.test.ts:1-47`.
- Produces: module-private `function sameResearchActionState(previous: { object: ResearchObjectView | null; actions: ResearchActionView[] } | null, object: ResearchObjectView | null, actions: ResearchActionView[]): boolean` in `src/sidebar.ts` (NOT exported — the behavior is tested through the DOM); private field `SidebarView.renderedResearchActions: { object: ResearchObjectView | null; actions: ResearchActionView[] } | null`. No caller outside `sidebar.ts` relies on either.

- [ ] **Step 1: Write the failing skip-rebuild test.** In `integrations/zotero/test/sidebar.test.ts`, replace the tail of the existing chip test (`test/sidebar.test.ts:138-141`):

  ```ts
      expect(body.querySelector(".zc-action-object")?.textContent).toContain("A Test Paper");
      actions[1]!.click();
      expect(handlers.onResearchAction).toHaveBeenCalledWith("analyze-figure");
    });
  ```

  with the same lines plus the new test appended:

  ```ts
      expect(body.querySelector(".zc-action-object")?.textContent).toContain("A Test Paper");
      actions[1]!.click();
      expect(handlers.onResearchAction).toHaveBeenCalledWith("analyze-figure");
    });

    it("keeps chip buttons alive across re-renders with unchanged Actions and rebuilds on change", () => {
      const body = document.createElement("div");
      document.body.appendChild(body);
      const handlers = { ...callbacks(), onResearchAction: vi.fn() };
      const view = new SidebarView(body, handlers);
      const freshActions = () => [
        { id: "summarize", label: "Summarize", description: "Summarize the selected object with traceable evidence.", icon: "≡" },
        { id: "evidence-qa", label: "Evidence QA", description: "Answer a question and audit each material claim against the source.", icon: "✓" },
      ];
      view.setState({
        phase: "ready",
        researchObject: { kind: "pdf", label: "A Test Paper" },
        researchActions: freshActions(),
      });
      const before = [...body.querySelectorAll<HTMLButtonElement>(".zc-research-action")];
      expect(before).toHaveLength(2);

      // Streaming turns call setState with fresh-but-equal state objects; the
      // strip must keep the same button nodes so an in-flight click (mousedown
      // before the re-render, mouseup after) still lands on a live element.
      view.setState({
        running: true,
        researchObject: { kind: "pdf", label: "A Test Paper" },
        researchActions: freshActions(),
      });
      const after = [...body.querySelectorAll<HTMLButtonElement>(".zc-research-action")];
      expect(after[0]).toBe(before[0]);
      expect(after[1]).toBe(before[1]);
      after[1]!.click();
      expect(handlers.onResearchAction).toHaveBeenCalledWith("evidence-qa");

      // A genuinely different action set rebuilds the chips.
      view.setState({
        researchActions: [
          { id: "summarize", label: "Summarize", description: "Summarize the selected object with traceable evidence.", icon: "≡" },
        ],
      });
      const changed = [...body.querySelectorAll<HTMLButtonElement>(".zc-research-action")];
      expect(changed).toHaveLength(1);
      expect(changed[0]).not.toBe(before[0]);

      // Clearing the research object still hides the strip (the derived
      // hidden state participates in the comparison, so this must not skip).
      view.setState({ researchObject: null, researchActions: [] });
      expect(body.querySelector<HTMLElement>(".zc-action-strip")!.hidden).toBe(true);
    });
  ```

- [ ] **Step 2: Run the test and confirm it fails on node identity.** From `/home/chance/quarto-lab/integrations/zotero`:

  ```bash
  npx vitest run test/sidebar.test.ts
  ```

  Expected: exactly one new failure, `keeps chip buttons alive across re-renders with unchanged Actions and rebuilds on change`, at `expect(after[0]).toBe(before[0])` with `AssertionError: expected HTMLButtonElement … to be HTMLButtonElement … // Object.is equality` — because `renderResearchActions` unconditionally calls `replaceChildren()` and recreates the buttons. All pre-existing tests in the file must still pass.

- [ ] **Step 3: Add the comparison helper.** In `integrations/zotero/src/sidebar.ts`, replace (`sidebar.ts:281-287`):

  ```ts
  /** The chat column never shrinks past a quarter or grows past two thirds. */
  function clampSplitRatio(percent: number): number {
    if (!Number.isFinite(percent)) return 40;
    return Math.round(Math.min(68, Math.max(25, percent)));
  }

  export class SidebarView {
  ```

  with:

  ```ts
  /** The chat column never shrinks past a quarter or grows past two thirds. */
  function clampSplitRatio(percent: number): number {
    if (!Number.isFinite(percent)) return 40;
    return Math.round(Math.min(68, Math.max(25, percent)));
  }

  /**
   * Rebuilding the Action chips between mousedown and mouseup (frequent while
   * a turn streams re-renders) destroys the button before its click event
   * fires. Equal-by-value chip state therefore keeps the existing buttons.
   * Every field that affects the rendered strip participates: per-action
   * id/label/description/icon plus the object kind/label, from which the
   * strip's hidden state is derived. ResearchActionView carries no disabled
   * flag today; add any future field to this comparison.
   */
  function sameResearchActionState(
    previous: { object: ResearchObjectView | null; actions: ResearchActionView[] } | null,
    object: ResearchObjectView | null,
    actions: ResearchActionView[],
  ): boolean {
    if (!previous) return false;
    if ((previous.object === null) !== (object === null)) return false;
    if (previous.object && object
      && (previous.object.kind !== object.kind || previous.object.label !== object.label)) {
      return false;
    }
    if (previous.actions.length !== actions.length) return false;
    return previous.actions.every((prev, index) => {
      const next = actions[index]!;
      return prev.id === next.id
        && prev.label === next.label
        && prev.description === next.description
        && prev.icon === next.icon;
    });
  }

  export class SidebarView {
  ```

- [ ] **Step 4: Add the memo field.** In `integrations/zotero/src/sidebar.ts`, replace (`sidebar.ts:299-300`):

  ```ts
    private actionStrip!: HTMLElement;
    private contextTitle!: HTMLElement;
  ```

  with:

  ```ts
    private actionStrip!: HTMLElement;
    private renderedResearchActions: {
      object: ResearchObjectView | null;
      actions: ResearchActionView[];
    } | null = null;
    private contextTitle!: HTMLElement;
  ```

- [ ] **Step 5: Guard `renderResearchActions`.** In `integrations/zotero/src/sidebar.ts`, replace (`sidebar.ts:1028-1034`; the rest of the method — object label span, button loop, click listeners — stays byte-identical):

  ```ts
    private renderResearchActions(): void {
      if (!this.actionStrip) return;
      this.actionStrip.replaceChildren();
      const object = this.state.researchObject;
      const actions = this.state.researchActions || [];
      this.actionStrip.hidden = !object || actions.length === 0;
      if (!object || !actions.length) return;
  ```

  with:

  ```ts
    private renderResearchActions(): void {
      if (!this.actionStrip) return;
      const object = this.state.researchObject ?? null;
      const actions = this.state.researchActions || [];
      if (sameResearchActionState(this.renderedResearchActions, object, actions)) return;
      this.renderedResearchActions = {
        object: object ? { ...object } : null,
        actions: actions.map((action) => ({ ...action })),
      };
      this.actionStrip.replaceChildren();
      this.actionStrip.hidden = !object || actions.length === 0;
      if (!object || !actions.length) return;
  ```

  The memo stores copies (`{ ...object }`, spread per action) so a caller later mutating the array it passed to `setState` cannot corrupt the comparison baseline. The first render always builds (memo starts `null`), and the hidden→hidden case skips harmlessly (strip is already empty and hidden).

- [ ] **Step 6: Run the sidebar suite and confirm it passes.** From `/home/chance/quarto-lab/integrations/zotero`:

  ```bash
  npx vitest run test/sidebar.test.ts
  ```

  Expected: all tests pass, including the existing `renders only the Actions supplied for the current research object` (its single `setState` still builds the chips) and the new skip-rebuild test.

- [ ] **Step 7: Run the full gate.** From `/home/chance/quarto-lab/integrations/zotero`:

  ```bash
  npm run verify
  ```

  Expected: check + all tests (including Task 1.1's `test/plugin-research-actions.test.ts`) + build all pass.

- [ ] **Step 8: Commit (hardening only).** From `/home/chance/quarto-lab`:

  ```bash
  git add integrations/zotero/src/sidebar.ts integrations/zotero/test/sidebar.test.ts && git commit -m "fix(zotero): keep Research Action chips stable across unchanged re-renders" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  ```

**Section acceptance check (maps to spec "Acceptance criteria — Section 1"):** after both commits, (a) chip clicks on Workbench surfaces dispatch the full existing chain `runResearchAction` → `buildResearchActionPrompt` → `sendChat` → `codex.send` (proved at the wiring seam by Task 1.1's test; the chain itself is pre-existing code, `plugin.ts:3683-3731`); (b) chips survive re-renders with unchanged state so mid-stream clicks register (Task 1.2's test); (c) deleting the `onResearchAction` property from `createWorkbenchView` makes `test/plugin-research-actions.test.ts` fail — it stubs `runResearchAction` on the plugin instance and asserts the click reaches it, which no `SidebarView`-only test can do.

---

## Section 2 — Visual Edit visual parity with Website Preview

**Spec:** `docs/superpowers/specs/2026-07-31-zotero-fix-pack-design.md`, "Design 2 — Visual Edit visual parity with Website Preview". Approved bar: *visually indistinguishable in normal reading*, not pixel-identical. Five components, each its own test-first commit. No commit in this section may touch anything from Designs 1, 3, or 4.

**Prerequisite (once, before Task 2.1):** the plugin checkout has no `node_modules`. Run:

```bash
cd /home/chance/quarto-lab/integrations/zotero && npm install
```

**Chat surfaces that must NOT change behavior** (they call `renderMarkdown` without `newlineAsBreak`, so the default keeps today's `<br>` semantics — do not edit these call sites):
- `integrations/zotero/src/sidebar.ts:2041, 2111, 2128`
- `integrations/zotero/src/float-panel.ts:790, 803`
- `integrations/zotero/src/noting.ts:147`
- `integrations/zotero/src/terminal-panel.ts:783`

**Pinned typography values (Component 4).** Measured from the Bootstrap CSS the draft preview actually compiles and loads. To regenerate it: `cd /home/chance/quarto-lab/drafts && quarto render index.qmd --to html` (writes `drafts/.preview/index_files/libs/bootstrap/bootstrap-e00a8cfd035d61cbe5d8da7afa12324c.min.css`; quarto may exit non-zero on unrelated config warnings — the output file is what matters). Values read out of that file:

| Property | Compiled draft preview | Pinned plugin CSS (`.zc-qmd-visual-editor` is the 17px base, so `1rem` ≡ `1em` there) |
|---|---|---|
| Root/body font size | `--bs-root-font-size: 17px`, `--bs-body-font-size: 1rem` | `17px` |
| Font family | `--bs-body-font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", "Liberation Sans", Arial, sans-serif, …emoji` | same stack (emoji fonts dropped) |
| Line height / weight / color | `--bs-body-line-height: 1.5`, weight `400`, `--bs-body-color: #212529` | `1.5` / `400` / `#212529` |
| Reading column | grid `[body-content] minmax(500px, calc(850px - 3em))` at 17px → max **799px** text, `1.5em` (25.5px) gutters | `width: min(850px, calc(100% - 44px))` + `25.5px` side padding → 799px measure |
| h1 | `2rem` (34px), weight 500, line-height 1.2, margin-bottom `.5rem` | `2em; margin: 0 0 8.5px; font-weight: 500; line-height: 1.2` |
| h2 | `1.65rem`, weight 600, margin `2rem 0 1rem`, padding-bottom `.5rem`, border-bottom `1px solid rgb(221.7,222.3,222.9)` | `1.65em; margin: 34px 0 17px; padding-bottom: 8.5px; border-bottom: 1px solid #dededf; font-weight: 600` |
| h3 | `1.45rem`, weight 600, margin-top `1.5rem`, opacity `.9` | `1.45em; margin: 25.5px 0 8.5px; font-weight: 600; opacity: .9` |
| h4 | `1.25rem`, weight 500, margin-top `1.5rem`, opacity `.9` | `1.25em; margin: 25.5px 0 8.5px; font-weight: 500; opacity: .9` |
| Paragraph spacing | `p { margin-bottom: 1rem }` (17px) | `.zc-qmd-visual-block { margin: 0 0 17px }` |

(`renderMarkdown` emits at most `h4` — `src/markdown.ts:94` clamps with `Math.min(4, …)` — so h1–h4 is the complete heading scale.)

---

### Task 2.1: Math engine unification — `html-math-method: katex` for draft previews

**Files:**
- Modify: `drafts/_quarto.yml:6-8` (this is the ONLY non-test file this task touches; `knowledge/_quarto.yml` stays byte-identical)
- Test: `integrations/zotero/test/draft-preview-math.test.ts` (new)

**Interfaces:**
- Consumes: nothing from the plugin — Quarto CLI reads `format.html.html-math-method`.
- Produces: `format.html.html-math-method: katex` in `drafts/_quarto.yml`, making the compiled draft preview use KaTeX, the engine Visual Edit bundles (`integrations/zotero/src/index.ts` imports `katex/dist/katex.min.css`).

- [ ] **Step 1: Write the failing config test.** Create `integrations/zotero/test/draft-preview-math.test.ts` with exactly:

  ```ts
  import { readFileSync } from "node:fs";
  import { join } from "node:path";

  import { describe, expect, it } from "vitest";

  // Visual Edit renders math with the plugin's bundled KaTeX. The compiled
  // draft preview must use the same engine or formula metrics diverge
  // (spec: Design 2, component 1).
  describe("draft preview math engine", () => {
    it("compiles draft previews with KaTeX, the engine Visual Edit bundles", () => {
      const config = readFileSync(join(process.cwd(), "..", "..", "drafts", "_quarto.yml"), "utf8");
      expect(config).toMatch(/html-math-method:\s*katex/);
    });

    it("leaves the published knowledge site's math pipeline unchanged", () => {
      const config = readFileSync(join(process.cwd(), "..", "..", "knowledge", "_quarto.yml"), "utf8");
      expect(config).not.toMatch(/html-math-method/);
    });
  });
  ```

- [ ] **Step 2: Run it expecting FAIL.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/draft-preview-math.test.ts
  ```
  Expected: 1 failed, 1 passed — the first test fails with `expected 'project:…' to match /html-math-method:\s*katex/`. (The knowledge-config guard already passes; it pins the "published site untouched" requirement.)

- [ ] **Step 3: Add the config line.** In `/home/chance/quarto-lab/drafts/_quarto.yml`, replace:

  ```yaml
  format:
    html:
      toc: true
  ```
  with:
  ```yaml
  format:
    html:
      toc: true
      html-math-method: katex
  ```

- [ ] **Step 4: Run it expecting PASS.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/draft-preview-math.test.ts
  ```
  Expected: 2 passed.

- [ ] **Step 5: Verify against a real compiled draft.** `drafts/NPA.qmd` contains 135 `$…$` formulas:
  ```bash
  cd /home/chance/quarto-lab/drafts && quarto render NPA.qmd --to html; grep -c "katex.min" .preview/NPA.html; grep -ci "tex-chtml-full" .preview/NPA.html
  ```
  Expected: `katex.min` count ≥ 1 (was 0 before this task) and `tex-chtml-full` (the MathJax 3 loader) count 0 (was 1). Ignore quarto's exit code if the HTML was written — this checkout's render prints config warnings.

- [ ] **Step 6: Commit.**
  ```bash
  cd /home/chance/quarto-lab && git add drafts/_quarto.yml integrations/zotero/test/draft-preview-math.test.ts && git commit -m "fix(zotero): compile draft previews with KaTeX for Visual Edit parity" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  ```

---

### Task 2.2: Scope the 1.04em KaTeX size override to chat entries

**Files:**
- Modify: `integrations/zotero/src/styles.css:536-537`
- Test: `integrations/zotero/test/build-assets.test.ts` (append one `it` inside the existing `describe("browser style bundle")`)

**Interfaces:**
- Consumes: the chat entry container class `zc-entry-content` — created at `integrations/zotero/src/sidebar.ts:2124-2126` and `integrations/zotero/src/float-panel.ts:799-801`; both wrap every chat `renderMarkdown` output. The Visual Edit tree (`.zc-qmd-visual-editor`, `src/qmd-visual-editor.ts:82-84`) never sits inside `.zc-entry-content`.
- Produces: CSS selectors `.zc-entry-content .zc-math-inline .katex` and `.zc-entry-content .zc-math-display .katex` (chat keeps 1.04em); Visual Edit math falls back to the bundled stock `katex.min.css` default (`1.21em`), the same stylesheet default Quarto's KaTeX output uses.

- [ ] **Step 1: Write the failing CSS-scoping test.** In `integrations/zotero/test/build-assets.test.ts`, append this `it` inside `describe("browser style bundle", …)` (after the `"declares the float transcript selectable…"` test, before the describe's closing `});`). It follows the file's established esbuild-bundle pattern exactly:

  ```ts
  it("scopes the 1.04em chat KaTeX override away from the visual editor", async () => {
    const result = await build({
      entryPoints: [join(process.cwd(), "src/index.ts")],
      bundle: true,
      platform: "browser",
      format: "iife",
      target: ["firefox140"],
      write: false,
      outdir: "out",
      assetNames: "fonts/[name]-[hash]",
      loader: {
        ".svg": "dataurl",
        ".woff2": "file",
        ".woff": "file",
        ".ttf": "file",
      },
    });

    const css = result.outputFiles.find((file) => file.path.endsWith(".css"))?.text || "";
    // Chat entries keep the 1.04em tuning (12.5px chat font)…
    expect(css).toMatch(
      /\.zc-entry-content \.zc-math-inline \.katex,\s*\.zc-entry-content \.zc-math-display \.katex\s*\{\s*font-size:\s*1\.04em;\s*\}/,
    );
    // …and no unscoped rule reaches the 17px visual editor, whose math must
    // fall back to KaTeX's stock 1.21em like Quarto's own KaTeX output.
    const withoutScoped = css
      .replaceAll(".zc-entry-content .zc-math-inline .katex", "")
      .replaceAll(".zc-entry-content .zc-math-display .katex", "");
    expect(withoutScoped).not.toContain(".zc-math-inline .katex");
    expect(withoutScoped).not.toContain(".zc-math-display .katex");
  });
  ```

- [ ] **Step 2: Run it expecting FAIL.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/build-assets.test.ts
  ```
  Expected: the new test fails on the first `toMatch` (the scoped selector does not exist yet); all pre-existing tests in the file pass.

- [ ] **Step 3: Narrow the selector.** In `integrations/zotero/src/styles.css`, replace lines 536-537:

  ```css
  .zc-math-inline .katex,
  .zc-math-display .katex { font-size: 1.04em; }
  ```
  with:
  ```css
  .zc-entry-content .zc-math-inline .katex,
  .zc-entry-content .zc-math-display .katex { font-size: 1.04em; }
  ```
  Do NOT touch `.zc-math-preview-formula .katex { font-size: .95em; }` at `styles.css:898` — it is a terminal-panel preview rule outside this spec.

- [ ] **Step 4: Run it expecting PASS.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/build-assets.test.ts
  ```
  Expected: all tests pass.

- [ ] **Step 5: Guard the chat and editor suites, then type-check.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/sidebar.test.ts test/float-panel.test.ts test/qmd-visual-editor.test.ts && npm run check
  ```
  Expected: all pass (this task is CSS-only).

- [ ] **Step 6: Commit.**
  ```bash
  cd /home/chance/quarto-lab && git add integrations/zotero/src/styles.css integrations/zotero/test/build-assets.test.ts && git commit -m "fix(zotero): scope the chat KaTeX size override to chat entries" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  ```

---

### Task 2.3: `newlineAsBreak` renderer option; Visual Edit gets Pandoc soft breaks

**Files:**
- Modify: `integrations/zotero/src/markdown.ts:50-55` (options interface), `integrations/zotero/src/markdown.ts:376-381` (newline branch in `appendInline`), `integrations/zotero/src/qmd-visual-editor.ts:156`, `integrations/zotero/src/qmd-visual-editor.ts:170`
- Test: `integrations/zotero/test/markdown.test.ts` (append), `integrations/zotero/test/qmd-visual-editor.test.ts` (append)

**Interfaces:**
- Consumes: `export function renderMarkdown(doc: Document, markdown: string, options: MarkdownRenderOptions = {}): DocumentFragment` (`src/markdown.ts:57-61`); the private `appendInline(doc: Document, parent: Node, text: string, allowLinks = true, options: MarkdownRenderOptions = {})` which already receives `options` from every paragraph (`markdown.ts:145`), blockquote (`:133`), heading (`:96`), list item (`:106, :118`) and table cell call.
- Produces: `MarkdownRenderOptions.newlineAsBreak?: boolean` — `undefined`/`true` = current `<br>` behavior (all chat surfaces); `false` = a single newline renders as one space (Visual Edit only). No other signature changes; later Task 2.5's continuation lines inherit these semantics automatically because list items are rendered through `appendInline`.

- [ ] **Step 1: Write the renderer tests.** Append to the end of `integrations/zotero/test/markdown.test.ts` (after the closing `});` of `describe("safe paper Markdown renderer", …)`; the file-level `render` helper at lines 6-10 stays in scope):

  ```ts
  describe("newlineAsBreak", () => {
    beforeEach(() => {
      document.body.replaceChildren();
    });

    it("renders single newlines inside paragraphs as hard breaks by default", () => {
      const host = render("first line\nsecond line");
      const paragraph = host.querySelector("p")!;
      expect(paragraph.querySelectorAll("br")).toHaveLength(1);
      expect(paragraph.textContent).toBe("first linesecond line");
    });

    it("renders single newlines as spaces when newlineAsBreak is false", () => {
      const host = document.createElement("div");
      host.appendChild(renderMarkdown(document, "first line\nsecond line", { newlineAsBreak: false }));
      const paragraph = host.querySelector("p")!;
      expect(paragraph.querySelector("br")).toBeNull();
      expect(paragraph.textContent).toBe("first line second line");
    });

    it("applies the same soft-break semantics inside blockquotes", () => {
      const hard = render("> quoted line one\n> quoted line two");
      expect(hard.querySelector("blockquote br")).not.toBeNull();

      const soft = document.createElement("div");
      soft.appendChild(renderMarkdown(document, "> quoted line one\n> quoted line two", { newlineAsBreak: false }));
      expect(soft.querySelector("blockquote br")).toBeNull();
      expect(soft.querySelector("blockquote")!.textContent).toBe("quoted line one quoted line two");
    });
  });
  ```

- [ ] **Step 2: Run expecting FAIL.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/markdown.test.ts
  ```
  Expected: TypeScript-level object-literal error or assertion failures on the two `newlineAsBreak: false` tests (`newlineAsBreak` is not yet in `MarkdownRenderOptions`; if vitest transpiles without the type error, the assertions fail because `<br>` elements are still emitted). The default-behavior test passes — it pins current chat behavior.

- [ ] **Step 3: Write the failing Visual Edit test.** In `integrations/zotero/test/qmd-visual-editor.test.ts`, insert after the `"autosaves a visual block after a short idle period"` test (line 106), before the describe's closing `});`:

  ```ts
  it("flows hard-wrapped source prose as one paragraph like the compiled preview", () => {
    const save = vi.fn(async (next: string) => ({ source: next, revision: "r2" }));
    const editor = new QmdVisualEditor(document, { save });
    document.body.appendChild(editor.root);
    editor.setDocument({
      source: [
        "A first sentence that was",
        "hard-wrapped in the source",
        "across three lines.",
        "",
        "::: {#lem-flow}",
        "## Soft wrap",
        "The lemma statement is",
        "wrapped across lines.",
        ":::",
        "",
      ].join("\n"),
      revision: "r1",
    }, false);

    const paragraph = editor.root.querySelector<HTMLElement>('[data-block-kind="paragraph"]')!;
    expect(paragraph.querySelector("br")).toBeNull();
    expect(paragraph.textContent).toContain(
      "A first sentence that was hard-wrapped in the source across three lines.",
    );

    const cardBody = editor.root.querySelector<HTMLElement>(".zc-qmd-visual-card.is-lem .zc-qmd-visual-card-body")!;
    expect(cardBody.querySelector("br")).toBeNull();
    expect(cardBody.textContent).toContain("The lemma statement is wrapped across lines.");
  });
  ```

- [ ] **Step 4: Run expecting FAIL.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/qmd-visual-editor.test.ts
  ```
  Expected: only the new test fails — `paragraph.querySelector("br")` is not null (every source newline currently becomes `<br>`).

- [ ] **Step 5: Implement the option in the renderer.** In `integrations/zotero/src/markdown.ts`, replace the interface at lines 50-55:

  ```ts
  export interface MarkdownRenderOptions {
    /** Opens a PDF citation in the host reader instead of the web browser. */
    onPdfPageLink?: (reference: PdfPageReference) => void;
    /** Confirms that the citation URL identifies the PDF bound to the host reader. */
    canOpenPdfPageLink?: (reference: PdfPageReference) => boolean;
  }
  ```
  with:
  ```ts
  export interface MarkdownRenderOptions {
    /** Opens a PDF citation in the host reader instead of the web browser. */
    onPdfPageLink?: (reference: PdfPageReference) => void;
    /** Confirms that the citation URL identifies the PDF bound to the host reader. */
    canOpenPdfPageLink?: (reference: PdfPageReference) => boolean;
    /**
     * Renders a single source newline as a hard `<br>` (chat transcripts).
     * Pass `false` for Pandoc soft-break semantics — the newline becomes one
     * space — as the Visual Edit surface requires. Defaults to `true`.
     */
    newlineAsBreak?: boolean;
  }
  ```

  Then in `appendInline`, replace the newline branch at lines 376-381:

  ```ts
      if (text[index] === "\n") {
        flushPlain();
        parent.appendChild(doc.createElement("br"));
        index++;
        continue;
      }
  ```
  with:
  ```ts
      if (text[index] === "\n") {
        if (options.newlineAsBreak === false) {
          plain += " ";
        }
        else {
          flushPlain();
          parent.appendChild(doc.createElement("br"));
        }
        index++;
        continue;
      }
  ```

- [ ] **Step 6: Run the renderer tests expecting PASS.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/markdown.test.ts
  ```
  Expected: all pass, including every pre-existing test (the default path is unchanged).

- [ ] **Step 7: Opt the Visual Edit call sites in.** In `integrations/zotero/src/qmd-visual-editor.ts`, replace line 156:

  ```ts
        body.appendChild(renderMarkdown(this.doc, theoremBody(block.source)));
  ```
  with:
  ```ts
        body.appendChild(renderMarkdown(this.doc, theoremBody(block.source), { newlineAsBreak: false }));
  ```
  and replace line 170:
  ```ts
        wrapper.appendChild(renderMarkdown(this.doc, block.source));
  ```
  with:
  ```ts
        wrapper.appendChild(renderMarkdown(this.doc, block.source, { newlineAsBreak: false }));
  ```
  These are the only two call sites that change; the chat call sites listed in the section preamble stay untouched.

- [ ] **Step 8: Run the editor suites expecting PASS, then type-check.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/qmd-visual-editor.test.ts test/qmd-workspace.test.ts test/qmd-source-model.test.ts test/sidebar.test.ts test/float-panel.test.ts test/noting.test.ts && npm run check
  ```
  Expected: all pass.

- [ ] **Step 9: Commit.**
  ```bash
  cd /home/chance/quarto-lab && git add integrations/zotero/src/markdown.ts integrations/zotero/src/qmd-visual-editor.ts integrations/zotero/test/markdown.test.ts integrations/zotero/test/qmd-visual-editor.test.ts && git commit -m "fix(zotero): render soft line breaks as spaces in Visual Edit" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  ```

---

### Task 2.4: Typography alignment with the compiled draft theme

**Files:**
- Modify: `integrations/zotero/src/styles.css:1304-1313` (editor root), `integrations/zotero/src/styles.css:1314-1319` (block spacing), `integrations/zotero/src/styles.css:1326-1328` (heading scale)
- Test: `integrations/zotero/test/build-assets.test.ts` (append one `it`)

**Interfaces:**
- Consumes: class names `zc-qmd-visual-editor` (created `src/qmd-visual-editor.ts:82-84`) and `zc-qmd-visual-block` (`src/qmd-visual-editor.ts:114-116, 140, 147, 163`).
- Produces: the pinned CSS from the section-preamble table. The hard-coded light background (`.zc-qmd-visual-pane`, `styles.css:1303`) is a spec-retained limitation — do not touch it.

- [ ] **Step 1: Write the failing CSS test.** In `integrations/zotero/test/build-assets.test.ts`, append inside `describe("browser style bundle", …)` after the Task 2.2 test:

  ```ts
  it("pins Visual Edit typography to the compiled draft preview theme", async () => {
    const result = await build({
      entryPoints: [join(process.cwd(), "src/index.ts")],
      bundle: true,
      platform: "browser",
      format: "iife",
      target: ["firefox140"],
      write: false,
      outdir: "out",
      assetNames: "fonts/[name]-[hash]",
      loader: {
        ".svg": "dataurl",
        ".woff2": "file",
        ".woff": "file",
        ".ttf": "file",
      },
    });

    const css = result.outputFiles.find((file) => file.path.endsWith(".css"))?.text || "";
    // Body: 17px/1.5 weight-400 #212529, 799px reading measure — measured from
    // drafts/.preview/…/bootstrap-e00a8cfd035d61cbe5d8da7afa12324c.min.css.
    expect(css).toMatch(
      /\.zc-qmd-visual-editor\s*\{[^}]*width:\s*min\(850px,\s*calc\(100%\s*-\s*44px\)\);[^}]*\}/,
    );
    expect(css).toMatch(
      /\.zc-qmd-visual-editor\s*\{[^}]*font:\s*400\s+17px\/1\.5\s+system-ui,[^}]*\}/,
    );
    expect(css).toMatch(/\.zc-qmd-visual-editor\s*\{[^}]*color:\s*#212529;[^}]*\}/);
    // Heading scale: h1 2rem / h2 1.65rem / h3 1.45rem / h4 1.25rem at the
    // 17px base (rem ≡ em because body size equals the root size).
    expect(css).toMatch(/\.zc-qmd-visual-block h1\s*\{[^}]*font-size:\s*2em;[^}]*\}/);
    expect(css).toMatch(/\.zc-qmd-visual-block h2\s*\{[^}]*font-size:\s*1\.65em;[^}]*\}/);
    expect(css).toMatch(/\.zc-qmd-visual-block h3\s*\{[^}]*font-size:\s*1\.45em;[^}]*\}/);
    expect(css).toMatch(/\.zc-qmd-visual-block h4\s*\{[^}]*font-size:\s*1\.25em;[^}]*\}/);
  });
  ```

- [ ] **Step 2: Run expecting FAIL.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/build-assets.test.ts
  ```
  Expected: the new test fails on the first `toMatch` (editor width is still `min(900px, calc(100% - 44px))`, font still `16px/1.65`); everything else passes.

- [ ] **Step 3: Replace the editor root typography.** In `integrations/zotero/src/styles.css`, replace lines 1304-1313:

  ```css
  .zc-qmd-visual-editor {
    box-sizing: border-box;
    width: min(900px, calc(100% - 44px));
    min-height: 100%;
    margin: 0 auto;
    padding: 34px 20px 72px;
    color: #202124;
    background: #fff;
    font: 16px/1.65 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  ```
  with:
  ```css
  /* Typography pinned from the compiled draft preview's Bootstrap theme
     (drafts/.preview/index_files/libs/bootstrap/bootstrap-e00a8cfd….min.css,
     resolved at --bs-root-font-size: 17px): body 1rem/1.5 weight 400 #212529
     on the system-ui stack; content column [body-content] maxes at
     calc(850px - 3em) = 799px with 1.5em (25.5px) gutters. */
  .zc-qmd-visual-editor {
    box-sizing: border-box;
    width: min(850px, calc(100% - 44px));
    min-height: 100%;
    margin: 0 auto;
    padding: 34px 25.5px 72px;
    color: #212529;
    background: #fff;
    font: 400 17px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", "Liberation Sans", Arial, sans-serif;
  }
  ```

- [ ] **Step 4: Pin block spacing to the theme's paragraph rhythm.** In the block rule directly below (lines 1314-1319), replace:

  ```css
  .zc-qmd-visual-block {
    position: relative;
    margin: 0 0 16px;
    border-radius: 6px;
    transition: box-shadow .14s ease, background-color .14s ease;
  }
  ```
  with:
  ```css
  .zc-qmd-visual-block {
    position: relative;
    margin: 0 0 17px; /* p { margin-bottom: 1rem } at 17px root */
    border-radius: 6px;
    transition: box-shadow .14s ease, background-color .14s ease;
  }
  ```

- [ ] **Step 5: Replace the heading scale.** Replace lines 1326-1328:

  ```css
  .zc-qmd-visual-block h1 { margin: 0 0 22px; font-size: 2.05em; line-height: 1.15; }
  .zc-qmd-visual-block h2 { margin: 30px 0 14px; font-size: 1.55em; line-height: 1.2; }
  .zc-qmd-visual-block h3 { margin: 24px 0 12px; font-size: 1.25em; }
  ```
  with:
  ```css
  /* Heading scale pinned from the same compiled theme (fixed ≥1200px sizes):
     h1 2rem w500 mb .5rem; h2 1.65rem w600 mt 2rem mb 1rem pb .5rem with
     bottom rule rgb(221.7,222.3,222.9) ≈ #dededf; h3 1.45rem w600 mt 1.5rem
     opacity .9; h4 1.25rem w500 mt 1.5rem opacity .9; all line-height 1.2. */
  .zc-qmd-visual-block h1 { margin: 0 0 8.5px; font-size: 2em; font-weight: 500; line-height: 1.2; }
  .zc-qmd-visual-block h2 { margin: 34px 0 17px; padding-bottom: 8.5px; border-bottom: 1px solid #dededf; font-size: 1.65em; font-weight: 600; line-height: 1.2; }
  .zc-qmd-visual-block h3 { margin: 25.5px 0 8.5px; font-size: 1.45em; font-weight: 600; line-height: 1.2; opacity: .9; }
  .zc-qmd-visual-block h4 { margin: 25.5px 0 8.5px; font-size: 1.25em; font-weight: 500; line-height: 1.2; opacity: .9; }
  ```

- [ ] **Step 6: Run expecting PASS, guard, type-check.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/build-assets.test.ts test/qmd-visual-editor.test.ts test/qmd-workspace.test.ts && npm run check
  ```
  Expected: all pass (CSS-only change; no DOM test asserts the old font values).

- [ ] **Step 7: Commit.**
  ```bash
  cd /home/chance/quarto-lab && git add integrations/zotero/src/styles.css integrations/zotero/test/build-assets.test.ts && git commit -m "fix(zotero): match Visual Edit typography to the draft preview theme" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  ```

---

### Task 2.5: List grammar parity with the block splitter

**Files:**
- Modify: `integrations/zotero/src/markdown.ts:102-124` (list branches), `integrations/zotero/src/markdown.ts:190-196` (`startsBlock`)
- Test: `integrations/zotero/test/markdown.test.ts` (append)

**Interfaces:**
- Consumes: the splitter's list grammar this task mirrors — `src/qmd-source-model.ts:586-593`: item start `/^\s*(?:[-+*]|\d+[.)])\s+/`, continuation `/^\s{2,}\S/`, blank line ends the block. Also `appendInline(doc, item, text, true, options)` for item bodies (so continuation lines follow Task 2.3's `newlineAsBreak` semantics automatically: `<br>` in chat, space in Visual Edit).
- Produces: no API change — `renderMarkdown` now parses `+` bullets, `1)` numbering, indented item starts, and indented continuation lines into real `<ul>`/`<ol>` markup. List type is decided by the first item's marker; the splitter groups mixed markers into one block, so subsequent items of either marker continue the same list.

- [ ] **Step 1: Write the failing grammar tests.** Append to the end of `integrations/zotero/test/markdown.test.ts` (after the Task 2.3 `describe`):

  ```ts
  describe("list grammar parity with the visual block splitter", () => {
    beforeEach(() => {
      document.body.replaceChildren();
    });

    it("renders + bullets as unordered list items", () => {
      const host = render("+ alpha\n+ beta");
      const items = [...host.querySelectorAll("ul > li")];
      expect(items.map((item) => item.textContent)).toEqual(["alpha", "beta"]);
      expect(host.querySelector("p")).toBeNull();
    });

    it("renders 1) numbering as ordered list items", () => {
      const host = render("1) first\n2) second");
      const items = [...host.querySelectorAll("ol > li")];
      expect(items.map((item) => item.textContent)).toEqual(["first", "second"]);
      expect(host.querySelector("p")).toBeNull();
    });

    it("keeps indented continuation lines inside the previous list item", () => {
      const host = render("- head line\n  continuation line\n- second item");
      const items = [...host.querySelectorAll("ul > li")];
      expect(items).toHaveLength(2);
      expect(items[0]?.textContent).toContain("head line");
      expect(items[0]?.textContent).toContain("continuation line");
      expect(items[1]?.textContent).toBe("second item");
      expect(host.querySelector("p")).toBeNull();
    });

    it("breaks a paragraph when a + bullet or 1) item follows it", () => {
      const host = render("intro text\n+ bullet item");
      expect(host.querySelector("p")?.textContent).toBe("intro text");
      expect(host.querySelector("ul > li")?.textContent).toBe("bullet item");
    });

    it("ends the list at a blank line like the block splitter does", () => {
      const host = render("- item\n\nparagraph after");
      expect(host.querySelectorAll("ul > li")).toHaveLength(1);
      expect(host.querySelector("p")?.textContent).toBe("paragraph after");
    });
  });
  ```

- [ ] **Step 2: Run expecting FAIL.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/markdown.test.ts
  ```
  Expected: 4 of the 5 new tests fail (`+` bullets and `1)` items degrade to a `<p>` with `<br>`; the continuation test finds a stray `<p>`; the paragraph-break test finds both lines in one `<p>`). The blank-line test already passes — it pins current behavior. All pre-existing tests pass.

- [ ] **Step 3: Implement the unified list parser.** In `integrations/zotero/src/markdown.ts`, replace the two list branches at lines 102-124:

  ```ts
      if (/^[-*]\s+/.test(line)) {
        const list = doc.createElement("ul");
        while (index < lines.length && /^[-*]\s+/.test(lines[index] || "")) {
          const item = doc.createElement("li");
          appendInline(doc, item, (lines[index] || "").replace(/^[-*]\s+/, ""), true, options);
          list.appendChild(item);
          index++;
        }
        fragment.appendChild(list);
        continue;
      }

      if (/^\d+\.\s+/.test(line)) {
        const list = doc.createElement("ol");
        while (index < lines.length && /^\d+\.\s+/.test(lines[index] || "")) {
          const item = doc.createElement("li");
          appendInline(doc, item, (lines[index] || "").replace(/^\d+\.\s+/, ""), true, options);
          list.appendChild(item);
          index++;
        }
        fragment.appendChild(list);
        continue;
      }
  ```
  with:
  ```ts
      // Mirrors the visual block splitter's list grammar
      // (src/qmd-source-model.ts:586-593): `[-+*]` and `\d+[.)]` markers with
      // optional indentation, plus 2-space-indented continuation lines.
      const listStart = /^\s*(?:([-+*])|\d+[.)])\s+/.exec(line);
      if (listStart) {
        const list = doc.createElement(listStart[1] ? "ul" : "ol");
        let itemText: string | null = null;
        const flushItem = () => {
          if (itemText === null) return;
          const item = doc.createElement("li");
          appendInline(doc, item, itemText, true, options);
          list.appendChild(item);
          itemText = null;
        };
        while (index < lines.length) {
          const current = lines[index] || "";
          const marker = /^\s*(?:[-+*]|\d+[.)])\s+/.exec(current);
          if (marker) {
            flushItem();
            itemText = current.slice(marker[0].length);
          }
          else if (itemText !== null && /^\s{2,}\S/.test(current)) {
            itemText += `\n${current.trim()}`;
          }
          else {
            break;
          }
          index++;
        }
        flushItem();
        fragment.appendChild(list);
        continue;
      }
  ```

  Then replace `startsBlock` at lines 190-196 so paragraphs break on the extended markers too:

  ```ts
  function startsBlock(lines: readonly string[], index: number): boolean {
    const line = lines[index] || "";
    if (!line.trim()) return true;
    if (/^(#{1,4})\s+|^```|^[-*]\s+|^\d+\.\s+|^>\s+/.test(line)) return true;
    if (readMathBlock(lines, index)) return true;
    return Boolean(readTable(lines, index));
  }
  ```
  with:
  ```ts
  function startsBlock(lines: readonly string[], index: number): boolean {
    const line = lines[index] || "";
    if (!line.trim()) return true;
    if (/^(#{1,4})\s+|^```|^\s*(?:[-+*]|\d+[.)])\s+|^>\s+/.test(line)) return true;
    if (readMathBlock(lines, index)) return true;
    return Boolean(readTable(lines, index));
  }
  ```

- [ ] **Step 4: Run expecting PASS.**
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/markdown.test.ts
  ```
  Expected: all pass, including every pre-existing renderer test.

- [ ] **Step 5: Full-suite guard and type-check** (the renderer feeds chat, noting, and Visual Edit, so run everything):
  ```bash
  cd /home/chance/quarto-lab/integrations/zotero && npm run check && npx vitest run
  ```
  Expected: type-check clean; every test file passes, in particular `test/qmd-visual-editor.test.ts`, `test/qmd-workspace.test.ts`, `test/qmd-source-model.test.ts` (spec's stay-green list) plus `test/sidebar.test.ts`, `test/float-panel.test.ts`, `test/noting.test.ts`.

- [ ] **Step 6: Commit.**
  ```bash
  cd /home/chance/quarto-lab && git add integrations/zotero/src/markdown.ts integrations/zotero/test/markdown.test.ts && git commit -m "fix(zotero): extend Visual Edit list grammar to match the block splitter" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  ```

---

**Section 2 exit gate.** After Task 2.5's commit, run the full verification from the plugin directory — this is the spec's per-commit bar and must pass before starting any other section:

```bash
cd /home/chance/quarto-lab/integrations/zotero && npm run verify
```

Expected: `check` (tsc), the vitest suite, and the esbuild build all succeed. Do not fold CHANGELOG/README/version-bump edits into this section — the spec reserves release chores for a final cross-section commit.

---

## Section 3 — Region screenshot to AI

**Spec reference:** "Design 3 — Region screenshot to AI" in `/home/chance/quarto-lab/docs/superpowers/specs/2026-07-31-zotero-fix-pack-design.md`.

**What exists today (verified):** the only screenshot feature is full-current-page capture: composer "@" menu entry `capture-page` "Screenshot Current Page" (`src/plugin.ts:3048-3053`) → `captureCurrentPageScreenshot` (`src/plugin.ts:2302-2314`) → `ReaderContextService.captureCurrentPageImage` (`src/reader-context.ts:1418-1422`) → adapter `capturePdfPage` (`src/reader-context.ts:3705-3738`, renders the whole PDF.js page at scale 1.5, clamped to 2400x3200 device px, returns `canvas.toDataURL("image/png")`). Pending images buffer in `private pendingScreenshots: string[]` (`src/plugin.ts:226`), render as chips "PDF Screenshot N" (`src/plugin.ts:2998-3004`), are removable via ids `screenshot:<index>` (`src/plugin.ts:2362-2367`), and are sent as the 4th arg of `codex.send` (`src/plugin.ts:1056-1058`). There is no region selection anywhere, no reader capture button (the only injected toolbar button opens the workbench, `src/plugin.ts:644-666`), and zero test coverage of the screenshot pipeline.

**What this section builds:** (1) a new module `src/region-capture.ts` holding pure crop geometry plus the crosshair drag overlay; (2) adapter + service plumbing in `src/reader-context.ts` to locate the current PDF.js page view and render a cropped PNG; (3) plugin wiring: a second reader toolbar button, a "Screenshot Region" Add-Context entry (`capture-region`), typed `pendingScreenshots` so region chips read "Region Screenshot N" while full-page chips keep "PDF Screenshot N", same max-10 cap and send path; (4) a README section documenting both flows.

**Design decisions (already made — do not revisit):**
- Zotero Reader internals (`_internalReader._primaryView._iframeWindow`) stay inside the `createZotero9ReadAdapter` adapter in `src/reader-context.ts`; `src/plugin.ts` never touches them (it currently never does — keep it that way). The plugin gets the page view element and the cropped PNG through two new *optional* adapter methods mirrored by two new service methods.
- The overlay lives in `src/region-capture.ts` as a plain function (like `float-panel.ts`'s `beginDrag` document-level mousemove/mouseup pattern at `src/float-panel.ts:855-872`), not a class — it has no persistent state. All overlay styles are inline `cssText` because the overlay is injected into the Reader's PDF.js iframe document, where the plugin stylesheet (`src/styles.css`) is **not** loaded.
- CSS→device conversion happens inside the adapter (which is the only place that knows the rendered canvas size), using the pure function from `src/region-capture.ts`. The overlay reports the drag rect in CSS px relative to the page view plus the page view's CSS size.
- Minimum drag size is 8 CSS px on each axis (`MIN_REGION_CSS_PX`); smaller drags cancel silently. Crop rects are clamped to canvas bounds; a selection entirely outside becomes `null` (no capture, error surfaced through the existing `reportError` path as "could not render").

All test commands run from `/home/chance/quarto-lab/integrations/zotero`; all git commands from `/home/chance/quarto-lab`. Tests are vitest; DOM tests need the `// @vitest-environment happy-dom` header comment on line 1 of the test file (see `test/plugin-state.test.ts:1`); `test/setup-dom.ts` is auto-loaded via `vitest.config.ts` and only patches `document.compatMode` — no other shim exists, so `getBoundingClientRect` returns zeros unless a test stubs it (stub it, as shown below).

### Task 3.1: Pure crop geometry module

**Files:**
- Create: `integrations/zotero/src/region-capture.ts`
- Test: `integrations/zotero/test/region-capture.test.ts` (new file)

**Interfaces:**
- Consumes: nothing (pure module, zero imports).
- Produces (later tasks rely on these exact names):
  - `export interface RegionRect { x: number; y: number; width: number; height: number }`
  - `export interface RegionSize { width: number; height: number }`
  - `export interface RegionSelection { rect: RegionRect; view: RegionSize }`
  - `export const MIN_REGION_CSS_PX = 8`
  - `export function normalizeRegionRect(x1: number, y1: number, x2: number, y2: number): RegionRect`
  - `export function meetsMinimumRegionSize(rect: RegionRect, minimum?: number): boolean`
  - `export function cssRegionToCanvasRegion(selection: RegionSelection, canvas: RegionSize): RegionRect | null`

- [ ] **Step 1: Write the failing geometry test file.** Create `integrations/zotero/test/region-capture.test.ts` with exactly:

```ts
// @vitest-environment happy-dom

import { describe, expect, it } from "vitest";

import {
  MIN_REGION_CSS_PX,
  cssRegionToCanvasRegion,
  meetsMinimumRegionSize,
  normalizeRegionRect,
} from "../src/region-capture";

describe("region crop geometry", () => {
  it("normalizes any two drag corners into a positive rect", () => {
    expect(normalizeRegionRect(110, 90, 10, 20)).toEqual({ x: 10, y: 20, width: 100, height: 70 });
    expect(normalizeRegionRect(10, 20, 110, 90)).toEqual({ x: 10, y: 20, width: 100, height: 70 });
    expect(normalizeRegionRect(5, 5, 5, 5)).toEqual({ x: 5, y: 5, width: 0, height: 0 });
  });

  it("rejects drags below the minimum size on either axis", () => {
    expect(meetsMinimumRegionSize({ x: 0, y: 0, width: MIN_REGION_CSS_PX, height: MIN_REGION_CSS_PX })).toBe(true);
    expect(meetsMinimumRegionSize({ x: 0, y: 0, width: MIN_REGION_CSS_PX - 1, height: 100 })).toBe(false);
    expect(meetsMinimumRegionSize({ x: 0, y: 0, width: 100, height: MIN_REGION_CSS_PX - 1 })).toBe(false);
  });

  it("scales a CSS-pixel selection to canvas device pixels", () => {
    expect(cssRegionToCanvasRegion(
      { rect: { x: 30, y: 40, width: 120, height: 60 }, view: { width: 300, height: 400 } },
      { width: 600, height: 800 },
    )).toEqual({ x: 60, y: 80, width: 240, height: 120 });
  });

  it("clamps a selection that overhangs the page to the canvas bounds", () => {
    expect(cssRegionToCanvasRegion(
      { rect: { x: -20, y: -10, width: 340, height: 430 }, view: { width: 300, height: 400 } },
      { width: 600, height: 800 },
    )).toEqual({ x: 0, y: 0, width: 600, height: 800 });
  });

  it("returns null for selections fully outside the page", () => {
    expect(cssRegionToCanvasRegion(
      { rect: { x: 400, y: 500, width: 50, height: 50 }, view: { width: 300, height: 400 } },
      { width: 600, height: 800 },
    )).toBeNull();
  });

  it("returns null for degenerate views and sub-pixel selections", () => {
    expect(cssRegionToCanvasRegion(
      { rect: { x: 0, y: 0, width: 10, height: 10 }, view: { width: 0, height: 0 } },
      { width: 600, height: 800 },
    )).toBeNull();
    expect(cssRegionToCanvasRegion(
      { rect: { x: 10, y: 10, width: 0.1, height: 0.1 }, view: { width: 300, height: 400 } },
      { width: 600, height: 800 },
    )).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test expecting FAIL.** `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/region-capture.test.ts` — expect a module-resolution failure: `Failed to resolve import "../src/region-capture" from "test/region-capture.test.ts"`.

- [ ] **Step 3: Write the geometry module.** Create `integrations/zotero/src/region-capture.ts` with exactly:

```ts
/**
 * Region-screenshot geometry and drag overlay (Fix Pack A, Design 3).
 *
 * The geometry half is pure so crop math unit-tests without a DOM: the
 * overlay reports a drag rect in CSS pixels relative to the PDF.js page
 * view, and the Zotero adapter converts it to device pixels on the page
 * canvas it renders (scale 1.5, clamped to 2400x3200 — see capturePdfPage
 * in reader-context.ts).
 */

export interface RegionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface RegionSize {
  width: number;
  height: number;
}

/** A completed drag: CSS-pixel rect relative to the page view, plus that view's CSS size. */
export interface RegionSelection {
  rect: RegionRect;
  view: RegionSize;
}

/** Drags smaller than this on either axis (CSS px) are discarded as accidental clicks. */
export const MIN_REGION_CSS_PX = 8;

/** Order two drag corners into a rect with non-negative width and height. */
export function normalizeRegionRect(x1: number, y1: number, x2: number, y2: number): RegionRect {
  return {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    width: Math.abs(x2 - x1),
    height: Math.abs(y2 - y1),
  };
}

export function meetsMinimumRegionSize(rect: RegionRect, minimum = MIN_REGION_CSS_PX): boolean {
  return rect.width >= minimum && rect.height >= minimum;
}

/**
 * Convert a CSS-pixel selection on the page view into device pixels on the
 * rendered page canvas, clamped to the canvas bounds. Returns null when the
 * view is degenerate or the clamped selection has no visible pixels.
 */
export function cssRegionToCanvasRegion(
  selection: RegionSelection,
  canvas: RegionSize,
): RegionRect | null {
  const { rect, view } = selection;
  if (!(view.width > 0) || !(view.height > 0)) return null;
  if (!(canvas.width > 0) || !(canvas.height > 0)) return null;
  const scaleX = canvas.width / view.width;
  const scaleY = canvas.height / view.height;
  const left = Math.max(0, Math.round(rect.x * scaleX));
  const top = Math.max(0, Math.round(rect.y * scaleY));
  const right = Math.min(canvas.width, Math.round((rect.x + rect.width) * scaleX));
  const bottom = Math.min(canvas.height, Math.round((rect.y + rect.height) * scaleY));
  const width = right - left;
  const height = bottom - top;
  if (width < 1 || height < 1) return null;
  return { x: left, y: top, width, height };
}
```

- [ ] **Step 4: Run the test expecting PASS.** `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/region-capture.test.ts` — all 6 tests pass.

- [ ] **Step 5: Type-check and verify.** `cd /home/chance/quarto-lab/integrations/zotero && npm run check && npm run verify` — both clean (verify runs check + full test suite + build; the spec requires it green at every commit).

- [ ] **Step 6: Commit.**
```sh
cd /home/chance/quarto-lab && git add integrations/zotero/src/region-capture.ts integrations/zotero/test/region-capture.test.ts && git commit -m "feat(zotero): add region screenshot crop geometry" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task 3.2: Crosshair drag overlay

**Files:**
- Modify: `integrations/zotero/src/region-capture.ts` (append after `cssRegionToCanvasRegion`)
- Test: `integrations/zotero/test/region-capture.test.ts` (append a describe block; extend imports)

**Interfaces:**
- Consumes: `normalizeRegionRect`, `meetsMinimumRegionSize`, `RegionRect`, `RegionSelection` (same module).
- Produces (Task 3.4 relies on these exact names):
  - `export interface RegionSelectionCallbacks { onComplete(selection: RegionSelection): void; onCancel(): void }`
  - `export function startRegionSelection(host: HTMLElement, callbacks: RegionSelectionCallbacks): () => void` — returns a disposer that removes the overlay without firing either callback.
  - DOM contract: overlay element class `zc-region-overlay` appended to `host`; selection box child class `zc-region-overlay-box`.

- [ ] **Step 1: Write the failing overlay tests.** In `integrations/zotero/test/region-capture.test.ts`, replace the two import statements at the top:

```ts
import { describe, expect, it } from "vitest";

import {
  MIN_REGION_CSS_PX,
  cssRegionToCanvasRegion,
  meetsMinimumRegionSize,
  normalizeRegionRect,
} from "../src/region-capture";
```

with:

```ts
import { describe, expect, it, vi } from "vitest";

import {
  MIN_REGION_CSS_PX,
  cssRegionToCanvasRegion,
  meetsMinimumRegionSize,
  normalizeRegionRect,
  startRegionSelection,
} from "../src/region-capture";
```

then append this describe block at the end of the file:

```ts
describe("startRegionSelection overlay", () => {
  // happy-dom computes no layout: getBoundingClientRect returns zeros unless
  // stubbed. Stub the page-view host the same way a real 400x600 CSS-pixel
  // PDF.js page at viewport offset (100, 50) would measure.
  function mountHost(): HTMLElement {
    const host = document.createElement("div");
    document.body.appendChild(host);
    host.getBoundingClientRect = () => ({
      left: 100,
      top: 50,
      width: 400,
      height: 600,
      right: 500,
      bottom: 650,
      x: 100,
      y: 50,
      toJSON: () => ({}),
    }) as DOMRect;
    return host;
  }

  it("completes a drag with the selection rect and view size, then removes the overlay", () => {
    const host = mountHost();
    const onComplete = vi.fn();
    const onCancel = vi.fn();
    startRegionSelection(host, { onComplete, onCancel });

    const overlay = host.querySelector<HTMLElement>(".zc-region-overlay")!;
    expect(overlay).not.toBeNull();
    expect(overlay.style.cursor).toBe("crosshair");
    overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 110, clientY: 60, bubbles: true }));
    document.dispatchEvent(new MouseEvent("mousemove", { clientX: 310, clientY: 210, bubbles: true }));
    const box = overlay.querySelector<HTMLElement>(".zc-region-overlay-box")!;
    expect(box.style.display).toBe("block");
    expect(box.style.width).toBe("200px");
    expect(box.style.height).toBe("150px");
    document.dispatchEvent(new MouseEvent("mouseup", { clientX: 310, clientY: 210, bubbles: true }));

    expect(onComplete).toHaveBeenCalledWith({
      rect: { x: 10, y: 10, width: 200, height: 150 },
      view: { width: 400, height: 600 },
    });
    expect(onCancel).not.toHaveBeenCalled();
    expect(host.querySelector(".zc-region-overlay")).toBeNull();
    host.remove();
  });

  it("cancels on Escape without capturing", () => {
    const host = mountHost();
    const onComplete = vi.fn();
    const onCancel = vi.fn();
    startRegionSelection(host, { onComplete, onCancel });
    const overlay = host.querySelector<HTMLElement>(".zc-region-overlay")!;
    overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 120, clientY: 70, bubbles: true }));

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(onComplete).not.toHaveBeenCalled();
    expect(host.querySelector(".zc-region-overlay")).toBeNull();
    host.remove();
  });

  it("discards drags below the minimum size", () => {
    const host = mountHost();
    const onComplete = vi.fn();
    const onCancel = vi.fn();
    startRegionSelection(host, { onComplete, onCancel });
    const overlay = host.querySelector<HTMLElement>(".zc-region-overlay")!;
    overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 110, clientY: 60, bubbles: true }));
    document.dispatchEvent(new MouseEvent("mouseup", { clientX: 114, clientY: 63, bubbles: true }));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(onComplete).not.toHaveBeenCalled();
    expect(host.querySelector(".zc-region-overlay")).toBeNull();
    host.remove();
  });

  it("returns a disposer that removes the overlay without firing callbacks", () => {
    const host = mountHost();
    const onComplete = vi.fn();
    const onCancel = vi.fn();
    const dispose = startRegionSelection(host, { onComplete, onCancel });

    dispose();

    expect(host.querySelector(".zc-region-overlay")).toBeNull();
    expect(onComplete).not.toHaveBeenCalled();
    expect(onCancel).not.toHaveBeenCalled();
    host.remove();
  });
});
```

- [ ] **Step 2: Run the test expecting FAIL.** `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/region-capture.test.ts` — the file fails to import: `The requested module '../src/region-capture' does not provide an export named 'startRegionSelection'`.

- [ ] **Step 3: Implement the overlay.** Append to the end of `integrations/zotero/src/region-capture.ts`:

```ts
export interface RegionSelectionCallbacks {
  /** The drag produced a valid selection; the overlay has already been removed. */
  onComplete(selection: RegionSelection): void;
  /** Escape, or a drag below MIN_REGION_CSS_PX; the overlay has already been removed. */
  onCancel(): void;
}

/**
 * Install a crosshair drag overlay over `host` (the current PDF.js page
 * view). Exactly one callback fires unless the returned disposer runs first:
 * Escape or a too-small drag cancels; mouse-up on a large-enough drag
 * completes with the selection in CSS pixels relative to `host`.
 *
 * The overlay lives inside the Reader's PDF.js iframe document, where the
 * plugin stylesheet is not loaded, so every style must stay inline.
 */
export function startRegionSelection(
  host: HTMLElement,
  callbacks: RegionSelectionCallbacks,
): () => void {
  const doc = host.ownerDocument;
  const overlay = doc.createElement("div");
  overlay.className = "zc-region-overlay";
  overlay.style.cssText =
    "position:absolute;inset:0;z-index:2147483647;cursor:crosshair;background:rgba(0,0,0,0.04)";
  const box = doc.createElement("div");
  box.className = "zc-region-overlay-box";
  box.style.cssText =
    "position:absolute;display:none;border:1px dashed #1a73e8;background:rgba(26,115,232,0.14);pointer-events:none";
  overlay.appendChild(box);
  host.appendChild(overlay);

  let startX = 0;
  let startY = 0;
  let dragging = false;
  let disposed = false;

  const localPoint = (event: MouseEvent): { x: number; y: number } => {
    const bounds = host.getBoundingClientRect();
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
  };

  const paintBox = (rect: RegionRect): void => {
    box.style.display = "block";
    box.style.left = `${rect.x}px`;
    box.style.top = `${rect.y}px`;
    box.style.width = `${rect.width}px`;
    box.style.height = `${rect.height}px`;
  };

  const dispose = (): void => {
    if (disposed) return;
    disposed = true;
    doc.removeEventListener("keydown", onKeyDown, true);
    doc.removeEventListener("mousemove", onMouseMove, true);
    doc.removeEventListener("mouseup", onMouseUp, true);
    overlay.remove();
  };

  const onKeyDown = (event: KeyboardEvent): void => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    dispose();
    callbacks.onCancel();
  };

  const onMouseDown = (event: MouseEvent): void => {
    if (event.button !== 0) return;
    event.preventDefault();
    const point = localPoint(event);
    startX = point.x;
    startY = point.y;
    dragging = true;
    paintBox({ x: startX, y: startY, width: 0, height: 0 });
  };

  const onMouseMove = (event: MouseEvent): void => {
    if (!dragging) return;
    const point = localPoint(event);
    paintBox(normalizeRegionRect(startX, startY, point.x, point.y));
  };

  const onMouseUp = (event: MouseEvent): void => {
    if (!dragging) return;
    dragging = false;
    const point = localPoint(event);
    const rect = normalizeRegionRect(startX, startY, point.x, point.y);
    const bounds = host.getBoundingClientRect();
    dispose();
    if (!meetsMinimumRegionSize(rect)) {
      callbacks.onCancel();
      return;
    }
    callbacks.onComplete({ rect, view: { width: bounds.width, height: bounds.height } });
  };

  overlay.addEventListener("mousedown", onMouseDown);
  doc.addEventListener("keydown", onKeyDown, true);
  doc.addEventListener("mousemove", onMouseMove, true);
  doc.addEventListener("mouseup", onMouseUp, true);
  return dispose;
}
```

- [ ] **Step 4: Run the test expecting PASS.** `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/region-capture.test.ts` — all 10 tests pass.

- [ ] **Step 5: Type-check and verify.** `cd /home/chance/quarto-lab/integrations/zotero && npm run check && npm run verify` — clean.

- [ ] **Step 6: Commit.**
```sh
cd /home/chance/quarto-lab && git add integrations/zotero/src/region-capture.ts integrations/zotero/test/region-capture.test.ts && git commit -m "feat(zotero): add crosshair drag overlay for region selection" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task 3.3: Adapter and service region capture

**Files:**
- Modify: `integrations/zotero/src/reader-context.ts:20` (imports), `:283` (`ZoteroReadAdapter` interface, after `capturePdfPage?`), `:1418-1422` (service, after `captureCurrentPageImage`), `:3705-3738` (Zotero 9 adapter, after `capturePdfPage`)
- Test: `integrations/zotero/test/reader-context.test.ts` (two insertion points, given below)

**Interfaces:**
- Consumes: `cssRegionToCanvasRegion(selection, canvas)` and `type RegionSelection` from `./region-capture`; existing private `ensureSnapshot(context?)` (`src/reader-context.ts:2108`), existing helpers `readerPdfWindow(reader)` (`:3401`), `asRecord`, `property`, `method` (all already used by `capturePdfPage`).
- Produces (Task 3.4 relies on these exact signatures):
  - `ZoteroReadAdapter.getPdfPageElement?(reader: TReader, pageIndex: number): HTMLElement | null`
  - `ZoteroReadAdapter.capturePdfPageRegion?(reader: TReader, pageIndex: number, region: RegionSelection): Promise<string | null>`
  - `ReaderContextService.getCurrentPageViewElement(context?: ReaderContext): Promise<HTMLElement | null>`
  - `ReaderContextService.captureCurrentPageRegionImage(region: RegionSelection, context?: ReaderContext): Promise<string | null>`

- [ ] **Step 1: Write the failing service-level tests.** In `integrations/zotero/test/reader-context.test.ts`, inside `describe("ReaderContextService")`, find the closing of the test `"observes a live page change even though Zotero exposes no page-change plugin event"` (ends at line ~1142 with `expect(adapter.readIndexedFullText).not.toHaveBeenCalled();\n  });`) and insert immediately after that `});`:

```ts
  it("captures a cropped region image and locates the page view through the adapter", async () => {
    const pageElement = {} as HTMLElement;
    const capturePdfPageRegion = vi.fn(async () => "data:image/png;base64,region");
    const getPdfPageElement = vi.fn(() => pageElement);
    const { adapter, reader, attachment } = makeAdapter({ capturePdfPageRegion, getPdfPageElement });
    const service = new ReaderContextService(adapter, host);
    const context = await service.acceptReaderHook({ reader, item: attachment });

    const region = { rect: { x: 5, y: 6, width: 40, height: 30 }, view: { width: 300, height: 400 } };
    await expect(service.captureCurrentPageRegionImage(region, context))
      .resolves.toBe("data:image/png;base64,region");
    expect(capturePdfPageRegion).toHaveBeenCalledWith(reader, 1, region);

    await expect(service.getCurrentPageViewElement(context)).resolves.toBe(pageElement);
    expect(getPdfPageElement).toHaveBeenCalledWith(reader, 1);
  });

  it("returns null for region capture when the runtime adapter lacks the capability", async () => {
    const { adapter, reader, attachment } = makeAdapter();
    const service = new ReaderContextService(adapter, host);
    const context = await service.acceptReaderHook({ reader, item: attachment });

    const region = { rect: { x: 0, y: 0, width: 10, height: 10 }, view: { width: 100, height: 100 } };
    await expect(service.captureCurrentPageRegionImage(region, context)).resolves.toBeNull();
    await expect(service.getCurrentPageViewElement(context)).resolves.toBeNull();
  });
```

(`makeAdapter`'s `getPageStats` returns `pageIndex: 1` — that is why the adapter must be called with `1`. `host` is the `MemoryHost` from the describe's `beforeEach`.)

- [ ] **Step 2: Write the failing Zotero 9 adapter tests.** In the same file, inside `describe("createZotero9ReadAdapter")`, insert immediately before the line `  function makeOutlineReader(pdfDocument: unknown): unknown {` (line ~2327):

```ts
  it("crops the rendered page to the selection in device pixels", async () => {
    const getViewport = vi.fn(() => ({ width: 600, height: 800 }));
    const render = vi.fn(() => ({ promise: Promise.resolve() }));
    const makeCanvas = (dataUrl: string) => {
      const context2d = { drawImage: vi.fn() };
      return {
        width: 0,
        height: 0,
        getContext: vi.fn(() => context2d),
        toDataURL: vi.fn(() => dataUrl),
        context2d,
      };
    };
    const fullCanvas = makeCanvas("data:image/png;base64,full");
    const cropCanvas = makeCanvas("data:image/png;base64,cropped");
    const canvases = [fullCanvas, cropCanvas];
    const reader = {
      _internalReader: {
        _primaryView: {
          _iframeWindow: {
            PDFViewerApplication: {
              pdfDocument: { getPage: vi.fn(async () => ({ getViewport, render })) },
            },
            document: { createElement: vi.fn(() => canvases.shift()) },
          },
        },
      },
    };
    const adapter = createZotero9ReadAdapter({});

    const region = { rect: { x: 30, y: 40, width: 120, height: 60 }, view: { width: 300, height: 400 } };
    await expect(adapter.capturePdfPageRegion!(reader, 0, region))
      .resolves.toBe("data:image/png;base64,cropped");

    expect(getViewport).toHaveBeenCalledWith({ scale: 1.5 });
    expect(fullCanvas.getContext).toHaveBeenCalledWith("2d", { alpha: false });
    // CSS 300x400 -> device 600x800 doubles every coordinate; drawImage crops
    // the full render into the small canvas at origin.
    expect(cropCanvas.context2d.drawImage)
      .toHaveBeenCalledWith(fullCanvas, 60, 80, 240, 120, 0, 0, 240, 120);
  });

  it("rejects a region outside the page without rendering anything", async () => {
    const createElement = vi.fn();
    const reader = {
      _internalReader: {
        _primaryView: {
          _iframeWindow: {
            PDFViewerApplication: {
              pdfDocument: {
                getPage: vi.fn(async () => ({
                  getViewport: vi.fn(() => ({ width: 600, height: 800 })),
                  render: vi.fn(() => ({ promise: Promise.resolve() })),
                })),
              },
            },
            document: { createElement },
          },
        },
      },
    };
    const adapter = createZotero9ReadAdapter({});

    const region = { rect: { x: 400, y: 500, width: 50, height: 50 }, view: { width: 300, height: 400 } };
    await expect(adapter.capturePdfPageRegion!(reader, 0, region)).resolves.toBeNull();
    expect(createElement).not.toHaveBeenCalled();
  });

  it("locates the current PDF.js page view element for the overlay", () => {
    const pageElement = { className: "page" };
    const querySelector = vi.fn(() => pageElement);
    const reader = {
      _internalReader: { _primaryView: { _iframeWindow: { document: { querySelector } } } },
    };
    const adapter = createZotero9ReadAdapter({});

    expect(adapter.getPdfPageElement!(reader, 4)).toBe(pageElement);
    expect(querySelector).toHaveBeenCalledWith('.page[data-page-number="5"]');
    expect(adapter.getPdfPageElement!(reader, -1)).toBeNull();
  });
```

- [ ] **Step 3: Run the test expecting FAIL.** `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/reader-context.test.ts` — the five new tests fail with `TypeError: service.captureCurrentPageRegionImage is not a function` / `TypeError: adapter.capturePdfPageRegion is not a function` / `TypeError: adapter.getPdfPageElement is not a function`; every pre-existing test still passes.

- [ ] **Step 4: Add the import.** In `integrations/zotero/src/reader-context.ts`, replace:

```ts
import { noteHtmlToQmdBody, qmdAuthorityMarker } from "./note-draft-bridge";
```

with:

```ts
import { noteHtmlToQmdBody, qmdAuthorityMarker } from "./note-draft-bridge";
import { cssRegionToCanvasRegion, type RegionSelection } from "./region-capture";
```

- [ ] **Step 5: Extend the adapter interface.** In `integrations/zotero/src/reader-context.ts` (inside `interface ZoteroReadAdapter`, line ~283), replace:

```ts
  /** Render one zero-based page as a bounded PNG data URL for multimodal context. */
  capturePdfPage?(reader: TReader, pageIndex: number): Promise<string | null>;
```

with:

```ts
  /** Render one zero-based page as a bounded PNG data URL for multimodal context. */
  capturePdfPage?(reader: TReader, pageIndex: number): Promise<string | null>;
  /**
   * Render one zero-based page cropped to a CSS-pixel selection as a bounded
   * PNG data URL. The selection's coordinates are relative to the page view
   * element returned by getPdfPageElement.
   */
  capturePdfPageRegion?(
    reader: TReader,
    pageIndex: number,
    region: RegionSelection,
  ): Promise<string | null>;
  /** The PDF.js page view element for one zero-based page, used to host the region-capture overlay. */
  getPdfPageElement?(reader: TReader, pageIndex: number): HTMLElement | null;
```

- [ ] **Step 6: Add the service methods.** In `integrations/zotero/src/reader-context.ts`, replace:

```ts
  async captureCurrentPageImage(context?: ReaderContext): Promise<string | null> {
    const snapshot = await this.ensureSnapshot(context);
    if (!this.zotero.capturePdfPage) return null;
    return this.zotero.capturePdfPage(snapshot.hook.reader, snapshot.context.page.pageIndex);
  }
```

with:

```ts
  async captureCurrentPageImage(context?: ReaderContext): Promise<string | null> {
    const snapshot = await this.ensureSnapshot(context);
    if (!this.zotero.capturePdfPage) return null;
    return this.zotero.capturePdfPage(snapshot.hook.reader, snapshot.context.page.pageIndex);
  }

  async captureCurrentPageRegionImage(
    region: RegionSelection,
    context?: ReaderContext,
  ): Promise<string | null> {
    const snapshot = await this.ensureSnapshot(context);
    if (!this.zotero.capturePdfPageRegion) return null;
    return this.zotero.capturePdfPageRegion(
      snapshot.hook.reader,
      snapshot.context.page.pageIndex,
      region,
    );
  }

  async getCurrentPageViewElement(context?: ReaderContext): Promise<HTMLElement | null> {
    const snapshot = await this.ensureSnapshot(context);
    if (!this.zotero.getPdfPageElement) return null;
    return this.zotero.getPdfPageElement(snapshot.hook.reader, snapshot.context.page.pageIndex);
  }
```

- [ ] **Step 7: Implement the Zotero 9 adapter methods.** In `integrations/zotero/src/reader-context.ts`, inside the object returned by `createZotero9ReadAdapter`, replace the tail of `capturePdfPage` plus the start of the next method:

```ts
        const data = canvas.toDataURL("image/png");
        canvas.width = 0;
        canvas.height = 0;
        return data.startsWith("data:image/png;base64,") ? data : null;
      }
      catch {
        return null;
      }
    },

    async extractPdfOutline(reader) {
```

with:

```ts
        const data = canvas.toDataURL("image/png");
        canvas.width = 0;
        canvas.height = 0;
        return data.startsWith("data:image/png;base64,") ? data : null;
      }
      catch {
        return null;
      }
    },

    async capturePdfPageRegion(reader, pageIndex, region) {
      if (!Number.isInteger(pageIndex) || pageIndex < 0) return null;
      try {
        const win = readerPdfWindow(reader);
        const application = asRecord(win.PDFViewerApplication);
        const document = asRecord(application.pdfDocument ?? property(application.pdfViewer, "pdfDocument"));
        const getPage = method(document, "getPage");
        if (!getPage) return null;
        const page = await getPage(pageIndex + 1);
        const getViewport = method(page, "getViewport");
        const render = method(page, "render");
        if (!getViewport || !render) return null;
        const viewport = getViewport({ scale: 1.5 }) as { width?: number; height?: number };
        const width = Math.max(1, Math.min(2400, Math.round(Number(viewport.width) || 0)));
        const height = Math.max(1, Math.min(3200, Math.round(Number(viewport.height) || 0)));
        if (!width || !height) return null;
        const crop = cssRegionToCanvasRegion(region, { width, height });
        if (!crop) return null;
        const ownerDocument = property(win, "document") as Document | undefined;
        if (!ownerDocument?.createElement) return null;
        const canvas = ownerDocument.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context2d = canvas.getContext("2d", { alpha: false });
        if (!context2d) return null;
        const task = render({ canvasContext: context2d, viewport }) as any;
        await (task?.promise || task);
        const cropCanvas = ownerDocument.createElement("canvas");
        cropCanvas.width = crop.width;
        cropCanvas.height = crop.height;
        const cropContext = cropCanvas.getContext("2d", { alpha: false });
        if (!cropContext) return null;
        cropContext.drawImage(
          canvas,
          crop.x,
          crop.y,
          crop.width,
          crop.height,
          0,
          0,
          crop.width,
          crop.height,
        );
        const data = cropCanvas.toDataURL("image/png");
        canvas.width = 0;
        canvas.height = 0;
        cropCanvas.width = 0;
        cropCanvas.height = 0;
        return data.startsWith("data:image/png;base64,") ? data : null;
      }
      catch {
        return null;
      }
    },

    getPdfPageElement(reader, pageIndex) {
      if (!Number.isInteger(pageIndex) || pageIndex < 0) return null;
      const win = readerPdfWindow(reader);
      const ownerDocument = property(win, "document") as Document | undefined;
      if (!ownerDocument?.querySelector) return null;
      return ownerDocument.querySelector(
        `.page[data-page-number="${pageIndex + 1}"]`,
      ) as HTMLElement | null;
    },

    async extractPdfOutline(reader) {
```

(TypeScript note: `drawImage` on the mock is untyped through `canvas.getContext(...)` because the adapter's `ownerDocument` is a real `Document` type — the code above compiles against `lib.dom` exactly like the existing `capturePdfPage` does.)

- [ ] **Step 8: Run the test expecting PASS.** `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/reader-context.test.ts` — all tests pass, including the five new ones.

- [ ] **Step 9: Type-check and verify.** `cd /home/chance/quarto-lab/integrations/zotero && npm run check && npm run verify` — clean.

- [ ] **Step 10: Commit.**
```sh
cd /home/chance/quarto-lab && git add integrations/zotero/src/reader-context.ts integrations/zotero/test/reader-context.test.ts && git commit -m "feat(zotero): capture cropped PDF page regions through the reader adapter" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task 3.4: Plugin wiring — toolbar button, Add-Context entry, typed chips, send path

**Files:**
- Modify: `integrations/zotero/src/plugin.ts:35` (import), `:226` (`pendingScreenshots` field), `:660-666` (reader toolbar), `:1056` (`sendChat`), `:2310` (full-page push), `:2314` (insert new methods after `captureCurrentPageScreenshot`), `:2326-2329` (`addInteractionContext` branch), `:2998-3004` (chip labels), `:3048-3053` (suggestion list)
- Test: `integrations/zotero/test/plugin-state.test.ts` (append a describe block at end of file)

**Interfaces:**
- Consumes: `startRegionSelection(host, callbacks)` and `type RegionSelection` from `./region-capture` (Task 3.2); `ReaderContextService.getCurrentPageViewElement(context?)` and `.captureCurrentPageRegionImage(region, context?)` (Task 3.3); existing `this.codex.getActiveReaderContext?.()`, `this.reportError(error)`, `this.renderChatViews()`, `this.activeChatView(): SidebarView | null` (`src/plugin.ts:3159`), `this.openResearchChat(_body?: HTMLElement, focus = true): Promise<void>` (`src/plugin.ts:971`), `this.acceptReaderHook(event: any): Promise<void>` (`src/plugin.ts:792`), `CodexService.send(text, model, effort, imageUrls, options)`.
- Produces: `private startRegionScreenshot(): Promise<void>` and `private captureRegionScreenshot(selection: RegionSelection, context: ReaderContext): Promise<void>` on `ZoteroChatPlugin`; suggestion id `"capture-region"` labeled `"Screenshot Region"`; `pendingScreenshots` retyped to `Array<{ image: string; kind: "page" | "region" }>`; reader toolbar button titled `"Capture Region Screenshot (QLab)"`.

- [ ] **Step 1: Write the failing plugin tests.** Append to the end of `integrations/zotero/test/plugin-state.test.ts` (after the closing `});` of `describe("clampFloatSize", ...)`):

```ts
describe("Region screenshots (Design 3)", () => {
  const paperContext = () => ({
    attachment: { key: "ATTACH", libraryID: 1, title: "Paper", creators: [] },
    parent: { title: "Paper", creators: [], tags: [] },
    page: { pageNumber: 5, pageLabel: "5" },
  });

  it("offers Screenshot Region in the Add-Context menu only while a reader is active", () => {
    const plugin = new ZoteroChatPlugin() as any;

    const withoutReader = plugin.contextSuggestions()
      .find((item: { id: string }) => item.id === "capture-region");
    expect(withoutReader).toMatchObject({
      label: "Screenshot Region",
      kind: "selection",
      disabled: true,
    });

    plugin.context = paperContext();
    const withReader = plugin.contextSuggestions()
      .find((item: { id: string }) => item.id === "capture-region");
    expect(withReader?.disabled).toBe(false);

    plugin.pendingScreenshots = Array.from({ length: 10 }, (_, index) => ({
      image: `data:image/png;base64,${index}`,
      kind: "page" as const,
    }));
    expect(plugin.contextSuggestions()
      .find((item: { id: string }) => item.id === "capture-region")?.disabled).toBe(true);
  });

  it("starts the region flow from the Add-Context menu entry", () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.startRegionScreenshot = vi.fn(async () => {});
    plugin.updateInteractionContext = vi.fn();
    plugin.renderChatViews = vi.fn();

    plugin.addInteractionContext({ id: "capture-region", kind: "selection", label: "Screenshot Region" });

    expect(plugin.startRegionScreenshot).toHaveBeenCalledOnce();
    expect(plugin.updateInteractionContext).not.toHaveBeenCalled();
  });

  it("labels pending page and region screenshots independently", () => {
    const plugin = new ZoteroChatPlugin() as any;
    plugin.context = paperContext();
    plugin.pendingScreenshots = [
      { image: "data:image/png;base64,a", kind: "page" },
      { image: "data:image/png;base64,b", kind: "region" },
      { image: "data:image/png;base64,c", kind: "page" },
    ];

    const labels = plugin.contextChips().map((chip: { label: string }) => chip.label);

    expect(labels).toContain("PDF Screenshot 1");
    expect(labels).toContain("Region Screenshot 1");
    expect(labels).toContain("PDF Screenshot 2");
    expect(plugin.contextChips().map((chip: { id: string }) => chip.id))
      .toEqual(expect.arrayContaining(["screenshot:0", "screenshot:1", "screenshot:2"]));
  });

  it("sends pending screenshots as bare data URIs and clears them after the send", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const send = vi.fn(async () => {});
    plugin.codex = {
      state: { connected: true, activeThreadId: null },
      isSignedIn: () => true,
      send,
      getActiveReaderContext: () => null,
    };
    plugin.pendingScreenshots = [
      { image: "data:image/png;base64,a", kind: "page" },
      { image: "data:image/png;base64,b", kind: "region" },
    ];

    await plugin.sendChat("what is in this figure?");

    expect(send).toHaveBeenCalledWith(
      "what is in this figure?",
      "",
      "medium",
      ["data:image/png;base64,a", "data:image/png;base64,b"],
      {},
    );
    expect(plugin.pendingScreenshots).toEqual([]);
  });

  it("injects a region-capture button beside the workbench button in the reader toolbar", async () => {
    const previousZotero = (globalThis as any).Zotero;
    const listeners = new Map<string, (event: any) => void>();
    (globalThis as any).Zotero = {
      Reader: {
        registerEventListener: vi.fn((type: string, handler: (event: any) => void) => {
          listeners.set(type, handler);
        }),
      },
    };
    try {
      const plugin = new ZoteroChatPlugin() as any;
      plugin.installShortcutHandler = vi.fn();
      plugin.acceptReaderHook = vi.fn(async () => {});
      plugin.startRegionScreenshot = vi.fn(async () => {});
      plugin.registerReaderHooks();

      const appended: HTMLElement[] = [];
      listeners.get("renderToolbar")!({
        doc: document,
        append: (element: HTMLElement) => appended.push(element),
        reader: { id: "reader-1" },
      });

      expect(appended).toHaveLength(2);
      const regionButton = appended[1] as HTMLButtonElement;
      expect(regionButton.title).toBe("Capture Region Screenshot (QLab)");
      regionButton.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(plugin.acceptReaderHook).toHaveBeenCalledOnce();
      expect(plugin.startRegionScreenshot).toHaveBeenCalledOnce();
    }
    finally {
      (globalThis as any).Zotero = previousZotero;
    }
  });

  it("attaches a Region Screenshot chip after a completed overlay drag", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const pageElement = document.createElement("div");
    document.body.appendChild(pageElement);
    pageElement.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 400, height: 600,
      right: 400, bottom: 600, x: 0, y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
    plugin.context = paperContext();
    plugin.codex = { getActiveReaderContext: () => plugin.context };
    plugin.readerContext = {
      getCurrentPageViewElement: vi.fn(async () => pageElement),
      captureCurrentPageRegionImage: vi.fn(async () => "data:image/png;base64,region"),
    };
    plugin.activeChatView = vi.fn(() => null);
    plugin.openResearchChat = vi.fn(async () => {});
    plugin.renderChatViews = vi.fn();

    await plugin.startRegionScreenshot();
    const overlay = pageElement.querySelector<HTMLElement>(".zc-region-overlay")!;
    expect(overlay).not.toBeNull();
    overlay.dispatchEvent(new MouseEvent("mousedown", { button: 0, clientX: 40, clientY: 60, bubbles: true }));
    document.dispatchEvent(new MouseEvent("mouseup", { clientX: 140, clientY: 160, bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(plugin.readerContext.captureCurrentPageRegionImage).toHaveBeenCalledWith(
      { rect: { x: 40, y: 60, width: 100, height: 100 }, view: { width: 400, height: 600 } },
      plugin.context,
    );
    expect(plugin.pendingScreenshots).toEqual([
      { image: "data:image/png;base64,region", kind: "region" },
    ]);
    expect(plugin.openResearchChat).toHaveBeenCalledWith(undefined, false);
    pageElement.remove();
  });
});
```

- [ ] **Step 2: Run the test expecting FAIL.** `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/plugin-state.test.ts` — the six new tests fail (`expected undefined to match object { label: 'Screenshot Region', … }`; `expected "spy" to be called once` for `startRegionScreenshot`; missing "Region Screenshot 1" label; `send` called with an array of objects instead of strings; `expected [ …1 element ] to have a length of 2` for the toolbar; `plugin.startRegionScreenshot is not a function`). All pre-existing tests still pass.

- [ ] **Step 3: Add the import and retype the buffer.** In `integrations/zotero/src/plugin.ts`, replace:

```ts
import { FloatPanelView, latestExchange } from "./float-panel";
```

with:

```ts
import { FloatPanelView, latestExchange } from "./float-panel";
import { startRegionSelection, type RegionSelection } from "./region-capture";
```

and replace (line 226):

```ts
  private pendingScreenshots: string[] = [];
```

with:

```ts
  private pendingScreenshots: Array<{ image: string; kind: "page" | "region" }> = [];
```

- [ ] **Step 4: Update the full-page push, send path, and chip labels.** Three edits in `integrations/zotero/src/plugin.ts`. First, in `captureCurrentPageScreenshot` (line 2310), replace:

```ts
    this.pendingScreenshots.push(image);
```

with:

```ts
    this.pendingScreenshots.push({ image, kind: "page" });
```

Second, in `sendChat` (line 1056), replace:

```ts
    const screenshots = [...this.pendingScreenshots];
```

with:

```ts
    const screenshots = this.pendingScreenshots.map((shot) => shot.image);
```

(the following two lines — `await this.codex.send(...)` and `if (screenshots.length) this.pendingScreenshots = [];` — stay unchanged). Third, in `contextChips` (lines 2998-3004), replace:

```ts
    this.pendingScreenshots.forEach((_image, index) => chips.push({
      id: `screenshot:${index}`,
      kind: "selection",
      label: `PDF Screenshot ${index + 1}`,
      detail: "Sent with the next message",
      removable: true,
    }));
```

with:

```ts
    let pageShots = 0;
    let regionShots = 0;
    this.pendingScreenshots.forEach((shot, index) => chips.push({
      id: `screenshot:${index}`,
      kind: "selection",
      label: shot.kind === "region"
        ? `Region Screenshot ${++regionShots}`
        : `PDF Screenshot ${++pageShots}`,
      detail: "Sent with the next message",
      removable: true,
    }));
```

(`removeInteractionContext`'s `screenshot:<index>` splice at `src/plugin.ts:2362-2367` needs no change — it splices whole entries.)

- [ ] **Step 5: Add the region capture methods.** In `integrations/zotero/src/plugin.ts`, replace:

```ts
    this.pendingScreenshots.push({ image, kind: "page" });
    this.chatError = "";
    this.renderChatViews();
    this.activeChatView()?.focusComposer();
  }

  private addInteractionContext(suggestion: ResearchContextSuggestion, win?: Window): void {
```

with:

```ts
    this.pendingScreenshots.push({ image, kind: "page" });
    this.chatError = "";
    this.renderChatViews();
    this.activeChatView()?.focusComposer();
  }

  /**
   * Design 3: overlay the current PDF.js page view with a crosshair and
   * attach the dragged region as a cropped screenshot. Reached from the
   * reader toolbar button and the "Screenshot Region" Add-Context entry.
   */
  private async startRegionScreenshot(): Promise<void> {
    if (this.pendingScreenshots.length >= 10) {
      throw new Error("A message can contain at most 10 PDF screenshots");
    }
    const context = this.codex.getActiveReaderContext?.() || this.context;
    if (!context) throw new Error("Open a PDF before capturing a region screenshot");
    const pageElement = await this.readerContext.getCurrentPageViewElement(context);
    if (!pageElement) throw new Error("Zotero could not locate the current PDF page view");
    startRegionSelection(pageElement, {
      onCancel: () => {},
      onComplete: (selection) => {
        void this.captureRegionScreenshot(selection, context)
          .catch((error) => this.reportError(error));
      },
    });
  }

  private async captureRegionScreenshot(
    selection: RegionSelection,
    context: ReaderContext,
  ): Promise<void> {
    if (this.pendingScreenshots.length >= 10) {
      throw new Error("A message can contain at most 10 PDF screenshots");
    }
    const image = await this.readerContext.captureCurrentPageRegionImage(selection, context);
    if (!image) throw new Error("Zotero could not render the selected PDF region as an image");
    this.pendingScreenshots.push({ image, kind: "region" });
    this.chatError = "";
    if (!this.activeChatView()) await this.openResearchChat(undefined, false);
    this.renderChatViews();
    this.activeChatView()?.focusComposer();
  }

  private addInteractionContext(suggestion: ResearchContextSuggestion, win?: Window): void {
```

- [ ] **Step 6: Dispatch the Add-Context entry.** In `addInteractionContext` (`src/plugin.ts:2326-2329` region), replace:

```ts
    if (suggestion.id === "capture-page") {
      void this.captureCurrentPageScreenshot().catch((error) => this.reportError(error));
      return;
    }
```

with:

```ts
    if (suggestion.id === "capture-page") {
      void this.captureCurrentPageScreenshot().catch((error) => this.reportError(error));
      return;
    }
    if (suggestion.id === "capture-region") {
      void this.startRegionScreenshot().catch((error) => this.reportError(error));
      return;
    }
```

- [ ] **Step 7: Add the suggestion entry.** In `contextSuggestions` (`src/plugin.ts:3048-3053` region), replace:

```ts
    }, {
      id: "capture-page",
      kind: "selection",
      label: "Screenshot Current Page",
      detail: "Attach the rendered PDF page for figures, equations, or layout",
      disabled: !context || this.pendingScreenshots.length >= 10,
    }, ...papers.map((paper): ResearchContextSuggestion => ({
```

with:

```ts
    }, {
      id: "capture-page",
      kind: "selection",
      label: "Screenshot Current Page",
      detail: "Attach the rendered PDF page for figures, equations, or layout",
      disabled: !context || this.pendingScreenshots.length >= 10,
    }, {
      id: "capture-region",
      kind: "selection",
      label: "Screenshot Region",
      detail: "Drag a rectangle on the current PDF page to attach just that region",
      disabled: !context || this.pendingScreenshots.length >= 10,
    }, ...papers.map((paper): ResearchContextSuggestion => ({
```

- [ ] **Step 8: Add the reader toolbar button.** In `registerReaderHooks` (`src/plugin.ts:660-666`), replace:

```ts
      button.addEventListener("click", () => {
        void this.acceptReaderHook(event).then(async () => {
          await this.openWorkbenchTab();
        }).catch((error) => this.reportError(error));
      });
      append(button);
    }, PLUGIN_ID);
```

with:

```ts
      button.addEventListener("click", () => {
        void this.acceptReaderHook(event).then(async () => {
          await this.openWorkbenchTab();
        }).catch((error) => this.reportError(error));
      });
      append(button);

      const regionButton = doc.createElement("button");
      regionButton.type = "button";
      regionButton.title = "Capture Region Screenshot (QLab)";
      regionButton.setAttribute("aria-label", regionButton.title);
      regionButton.style.cssText = "display:grid;place-items:center;width:32px;height:32px;border:0;border-radius:8px;background:transparent;cursor:pointer;padding:5px;font-size:15px;line-height:1";
      regionButton.textContent = "⬚";
      regionButton.addEventListener("click", () => {
        void this.acceptReaderHook(event).then(async () => {
          await this.startRegionScreenshot();
        }).catch((error) => this.reportError(error));
      });
      append(regionButton);
    }, PLUGIN_ID);
```

(`⬚` is the dotted-square glyph; a text glyph is used instead of a second copy of the data-URI icon because the Reader toolbar document renders plain text fine and the existing `readerToolbarIcon` already identifies the workbench button.)

- [ ] **Step 9: Run the test expecting PASS.** `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/plugin-state.test.ts` — all tests pass, including the six new ones.

- [ ] **Step 10: Type-check and verify.** `cd /home/chance/quarto-lab/integrations/zotero && npm run check && npm run verify` — `check` proves the `pendingScreenshots` retyping left no stragglers (the only readers are lines 1056-1058, 2303, 2310, 2362-2367, 2998-3004, 3053, all updated above); `verify` proves the whole suite and build stay green.

- [ ] **Step 11: Commit.**
```sh
cd /home/chance/quarto-lab && git add integrations/zotero/src/plugin.ts integrations/zotero/test/plugin-state.test.ts && git commit -m "feat(zotero): wire region screenshots into the reader toolbar and chat" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task 3.5: README — document both screenshot flows

**Files:**
- Modify: `integrations/zotero/README.md:94` (insert a new section immediately before the `## Build and test` heading)

**Interfaces:**
- Consumes: the shipped behavior from Tasks 3.1-3.4 plus the existing full-page flow (labels "PDF Screenshot N" / "Region Screenshot N", max 10 per message, `@` menu entries "Screenshot Current Page" and "Screenshot Region", reader toolbar button "Capture Region Screenshot (QLab)", Escape/min-size cancel).
- Produces: README section `## Screenshots to the AI chat`. This is the Design 3 documentation deliverable; the separate release-chores commit (spec "Cross-cutting") must NOT duplicate it — that commit only adds CHANGELOG entries and the version bump, and may cross-link this section.

- [ ] **Step 1: Write the section.** In `integrations/zotero/README.md`, replace:

```markdown
## Build and test
```

with:

```markdown
## Screenshots to the AI chat

Two capture flows attach rendered PDF images to the next chat message. Both
produce PNG images sent inline with the message, appear as removable chips
above the composer, and share one limit of 10 screenshots per message.

**Full page.** In the chat composer, open the Add-Context menu (click the `@`
button in the chips row, or type `@` in the input) and choose **Screenshot
Current Page**. The currently visible PDF page is rendered and attached as a
"PDF Screenshot N" chip.

**Region.** Click the region-capture button in the Reader toolbar (the dotted
square next to the QLab button), or choose **Screenshot Region** from the same
Add-Context menu. The current page view gets a crosshair overlay: drag a
rectangle around the figure, equation, or table you need and release to attach
it as a "Region Screenshot N" chip. Press Escape to cancel; drags smaller than
8 pixels on a side are discarded. If no chat surface is open, a completed
region capture opens the Workbench and focuses the composer.

Both entries require an open PDF. Click any screenshot chip to remove it
before sending; screenshots ride along with the next message only and are
never stored in Zotero.

## Build and test
```

- [ ] **Step 2: Verify.** `cd /home/chance/quarto-lab/integrations/zotero && npm run verify` — still green (docs-only change; this run satisfies the spec's every-commit gate).

- [ ] **Step 3: Commit.**
```sh
cd /home/chance/quarto-lab && git add integrations/zotero/README.md && git commit -m "docs(zotero): document the full-page and region screenshot flows" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Section acceptance check (from the spec — run after Task 3.5)

- Toolbar: `registerReaderHooks` appends a second button titled "Capture Region Screenshot (QLab)"; clicking it and dragging attaches a "Region Screenshot N" chip and focuses the composer (covered by the toolbar and overlay-drag tests in `test/plugin-state.test.ts`); Escape during the drag attaches nothing (`test/region-capture.test.ts`).
- Menu: "Screenshot Region" appears in the "@" Add-Context menu and is disabled without an active reader; "Screenshot Current Page" is untouched (`contextSuggestions` tests; the `capture-page` entry and `captureCurrentPageScreenshot` body are unchanged except the typed push).
- Transport: a region chip's cropped PNG data URI reaches `codex.send` as a bare string in the 4th argument (send-path test); the existing data-URI whitelist and 10-image cap in `src/codex-service.ts:1002-1008` are untouched.
- Cap and errors: both capture paths throw the same "at most 10 PDF screenshots" error at the cap; degenerate drags and out-of-bounds crops attach nothing; all failures surface via `reportError`.
- README documents both flows.
- `cd /home/chance/quarto-lab/integrations/zotero && npm run verify` passes.

---

## Section 4 — Open a paper's chat without the paper open

**Context for the implementer.** Conversations are Codex threads keyed per PDF attachment by `paperKey = "${libraryID}-${attachmentKey}"` (built by `paperIdentity()`, `src/codex-service.ts:1952-1954`) and persisted in profile `sessions.json` (`SessionFile`, `src/codex-service.ts:172-184`). Reopening a stored conversation is gated on the in-memory map `paperContexts` (`src/codex-service.ts:267`), which today is populated only by a live Reader capture in the current Zotero run — so after a restart, clicking a stored conversation tab throws "Open this conversation's Zotero paper once…" (`src/codex-service.ts:855-863` and `788-797`). This section (spec "Design 4") adds a host hook that seeds `paperContexts` by opening the paper's PDF in a **background** Reader tab (the proven pipeline inside `chooseWorkbenchPaper`, `src/plugin.ts:1845-1927`), a new public `CodexService.openConversationForPaper(paperKey)`, and a `zotero-itemmenu` entry "Open QLab Chat for This Paper". The independence contract test (`test/codex-service.test.ts:529-598`, "keeps PDF focus, selected chat, and running turns independent") must pass **unchanged** — do not edit any line of that test.

All test commands run from `/home/chance/quarto-lab/integrations/zotero`; all git commands run from `/home/chance/quarto-lab`. Every commit in this section touches only Design-4 files — never mix in changes from Sections 1–3.

### Task 4.1: CodexService — seeding hook unblocks conversation tabs and History (entry point A)

**Files:**
- Modify: `integrations/zotero/src/codex-service.ts:145-150` (CodexServiceCallbacks), `integrations/zotero/src/codex-service.ts:788-792` (openGlobalThread known-thread gate), `integrations/zotero/src/codex-service.ts:855-863` (switchThreadInternal gate), `integrations/zotero/src/codex-service.ts:889-892` (insertion point for the new private helper, right after `switchThreadInternal`'s closing brace)
- Test: `integrations/zotero/test/codex-service.test.ts` (append a new describe block after the file's final `});` at line 1529)

**Interfaces:**
- Consumes: `CodexService` constructor `(bridge: NativeBridge, readerContext: ReaderContextService, version: string, callbacks: CodexServiceCallbacks, agentToolProvider: CodexAgentToolProvider | null = null)`; private fields `this.callbacks`, `this.paperContexts: Map<string, ReaderContext>`, `this.activePaperKey`, `this.activeContext`; `private findSessionThread(threadId: string): { paperKey: string; record: SessionRecord } | null` (codex-service.ts:1802); `type ReaderContext` (already imported at codex-service.ts:25).
- Produces: `CodexServiceCallbacks.seedPaperContext?(paperKey: string): Promise<ReaderContext>` (new optional host hook — Tasks 4.2 and 4.3 rely on this exact name and signature); `private async seedPaperContextFromHost(paperKey: string, missingHookMessage: string): Promise<ReaderContext>` (service-internal — Task 4.2 calls it).

- [ ] **Step 1: Write the failing tests.** Append this entire block at the very end of `integrations/zotero/test/codex-service.test.ts` (after the last `});` on line 1529). It defines two helpers the rest of this section's service tests also use:

```ts
describe("CodexService conversation reopening", () => {
  function reopeningContext(): ReaderContext {
    return {
      ...paperContext(),
      attachment: { ...paperContext().attachment, id: 17, key: "SECOND", title: "Second PDF" },
      parent: { ...paperContext().parent!, id: 16, key: "SECOND-PARENT", title: "A Different Paper" },
      workspace: { ...paperContext().workspace!, root: "/profile/papers/1-SECOND" },
    };
  }

  function serviceWithSeeder(
    client: Record<string, unknown>,
    seedPaperContext: (paperKey: string) => Promise<ReaderContext>,
  ) {
    const callbacks = { onState: vi.fn(), onError: vi.fn(), seedPaperContext };
    const service = new CodexService(
      {} as NativeBridge,
      { tools: [] } as unknown as ReaderContextService,
      "test",
      callbacks,
    );
    const internal = service as any;
    internal.client = client;
    internal.saveSessions = vi.fn(async () => {});
    service.state.connected = true;
    internal.sessions = {
      version: 1,
      papers: {
        "1-SECOND": {
          threadId: "thread-b",
          title: "Stored conversation",
          paperTitle: "A Different Paper",
          workspace: "/profile/papers/1-SECOND",
          updatedAt: "2026-07-30",
        },
      },
      openThreads: ["thread-b"],
    };
    return { service, internal, callbacks };
  }

  it("reopens a stored conversation tab by seeding its paper context through the host hook", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service } = serviceWithSeeder(client, seedPaperContext);

    await service.switchThread("thread-b");

    expect(seedPaperContext).toHaveBeenCalledWith("1-SECOND");
    expect(client.threadResume).toHaveBeenCalledWith(expect.objectContaining({ threadId: "thread-b" }));
    expect(service.state.activeThreadId).toBe("thread-b");
    expect(service.getActiveReaderContext()?.attachment.key).toBe("SECOND");
  });

  it("reopens a known History conversation by seeding its paper context through the host hook", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service, internal } = serviceWithSeeder(client, seedPaperContext);
    internal.globalHistory = [{
      id: "thread-b",
      title: "Stored conversation",
      updatedAt: "2026-07-30T00:00:00.000Z",
      source: "codex",
      sourceLabel: "Codex CLI",
      pinned: false,
    }];

    await service.openGlobalThread("thread-b");

    expect(seedPaperContext).toHaveBeenCalledWith("1-SECOND");
    expect(service.state.activeThreadId).toBe("thread-b");
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({ threadId: "thread-b" });
  });
});
```

- [ ] **Step 2: Run the tests expecting FAIL.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/codex-service.test.ts`. Expected: the two new tests fail — the first rejects with `Error: Open this conversation's Zotero paper once, then select the conversation tab again`, the second with `Error: Open this conversation's Zotero paper once, then select it from History again`. All pre-existing tests (including "keeps PDF focus, selected chat, and running turns independent") still pass.

- [ ] **Step 3: Add the hook to the callbacks interface.** In `integrations/zotero/src/codex-service.ts`, replace this (lines 145-150):

```ts
export interface CodexServiceCallbacks {
  onState(): void;
  onError(error: Error): void;
  /** Lets the host reveal the real terminal without coupling service to UI. */
  onFallbackRequested?(error: Error): void;
}
```

with this:

```ts
export interface CodexServiceCallbacks {
  onState(): void;
  onError(error: Error): void;
  /** Lets the host reveal the real terminal without coupling service to UI. */
  onFallbackRequested?(error: Error): void;
  /**
   * Rebuilds a `${libraryID}-${attachmentKey}` paper's Reader context by
   * opening its PDF in a background Reader tab. Reader access is a
   * plugin-layer capability, so the service only consumes this hook.
   */
  seedPaperContext?(paperKey: string): Promise<ReaderContext>;
}
```

- [ ] **Step 4: Add the private seeding helper.** In `integrations/zotero/src/codex-service.ts`, replace this (the tail of `switchThreadInternal` plus the comment that follows it, lines 888-894):

```ts
    await this.requireClient().threadRead(response.thread.id, true);
    this.syncActiveTurnState();
    await this.saveSessions();
    this.callbacks.onState();
  }

  /** Closes a Workbench tab while leaving the conversation available in History. */
```

with this:

```ts
    await this.requireClient().threadRead(response.thread.id, true);
    this.syncActiveTurnState();
    await this.saveSessions();
    this.callbacks.onState();
  }

  /**
   * Seeds paperContexts for a paper that has not been opened in this Zotero
   * run, via the host's background-Reader pipeline. Falls back to the legacy
   * "open the paper once" error when no host hook is installed.
   */
  private async seedPaperContextFromHost(paperKey: string, missingHookMessage: string): Promise<ReaderContext> {
    const seed = this.callbacks.seedPaperContext;
    if (!seed) throw new Error(missingHookMessage);
    const context = await seed(paperKey);
    if (!context?.workspace) {
      throw new Error("Zotero Reader has not prepared this paper yet; try again shortly");
    }
    this.paperContexts.set(paperKey, context);
    return context;
  }

  /** Closes a Workbench tab while leaving the conversation available in History. */
```

- [ ] **Step 5: Route `switchThreadInternal` through the hook.** In `integrations/zotero/src/codex-service.ts`, replace this (lines 855-863):

```ts
  private async switchThreadInternal(threadId: string): Promise<void> {
    const located = this.findSessionThread(threadId);
    if (!located) throw new Error("This conversation could not be found in the local Workbench history");
    const paperKey = located.paperKey;
    const context = this.paperContexts.get(paperKey)
      || (this.activePaperKey === paperKey ? this.activeContext : null);
    if (!context?.workspace) {
      throw new Error("Open this conversation's Zotero paper once, then select the conversation tab again");
    }
```

with this:

```ts
  private async switchThreadInternal(threadId: string): Promise<void> {
    const located = this.findSessionThread(threadId);
    if (!located) throw new Error("This conversation could not be found in the local Workbench history");
    const paperKey = located.paperKey;
    let context = this.paperContexts.get(paperKey)
      || (this.activePaperKey === paperKey ? this.activeContext : null);
    if (!context?.workspace) {
      context = await this.seedPaperContextFromHost(
        paperKey,
        "Open this conversation's Zotero paper once, then select the conversation tab again",
      );
    }
```

- [ ] **Step 6: Route `openGlobalThread` through the hook.** In `integrations/zotero/src/codex-service.ts`, replace this (lines 788-792):

```ts
    const known = this.findSessionThread(threadId);
    const knownContext = known ? this.paperContexts.get(known.paperKey) : null;
    if (known && known.paperKey !== this.activePaperKey && !knownContext) {
      throw new Error("Open this conversation's Zotero paper once, then select it from History again");
    }
```

with this:

```ts
    const known = this.findSessionThread(threadId);
    let knownContext = known ? this.paperContexts.get(known.paperKey) ?? null : null;
    if (known && known.paperKey !== this.activePaperKey && !knownContext) {
      knownContext = await this.seedPaperContextFromHost(
        known.paperKey,
        "Open this conversation's Zotero paper once, then select it from History again",
      );
    }
```

Note: the seeding call sits before any state mutation in both methods (in `openGlobalThread` only the pre-existing `openThread(activeThreadId)` bookkeeping at line 787 precedes it, unchanged), so a hook failure propagates to the caller — `selectThread` (`src/plugin.ts:1096-1116`) and `selectHistoryConversation` (`src/plugin.ts:1118-1134`) already funnel these rejections into `reportError`, satisfying the "visible error" requirement with zero plugin changes.

- [ ] **Step 7: Run the tests expecting PASS.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/codex-service.test.ts`. Expected: entire file green, including the independence contract test at lines 529-598 and the two new tests.

- [ ] **Step 8: Full gate.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npm run verify`. Expected: check + test + build all pass.

- [ ] **Step 9: Commit.** Command: `cd /home/chance/quarto-lab && git add integrations/zotero/src/codex-service.ts integrations/zotero/test/codex-service.test.ts && git commit -m "fix(zotero): reopen stored conversations by seeding paper context through a host hook" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

### Task 4.2: CodexService.openConversationForPaper

**Files:**
- Modify: `integrations/zotero/src/codex-service.ts:839-855` (insert the new public method between `switchThread`'s closing brace and `switchThreadInternal`)
- Test: `integrations/zotero/test/codex-service.test.ts` (add four tests inside the `describe("CodexService conversation reopening", …)` block created in Task 4.1, after its last `it`)

**Interfaces:**
- Consumes: `private enqueuePaperTransition<T>(operation: () => Promise<T>): Promise<T>` (codex-service.ts:1847); `private async switchThreadInternal(threadId: string): Promise<void>`; `private async newThreadInternal(context: ReaderContext, paperKey: string): Promise<void>` (codex-service.ts:634); `private async seedPaperContextFromHost(paperKey: string, missingHookMessage: string): Promise<ReaderContext>` (Task 4.1); `interface SessionRecord { threadId: string; title: string; paperTitle?: string; workspace: string; updatedAt: string; backend?: "codex" | "engine" }`.
- Produces: `openConversationForPaper(paperKey: string): Promise<void>` (public — Task 4.4's plugin code calls exactly this).

- [ ] **Step 1: Write the failing tests.** In `integrations/zotero/test/codex-service.test.ts`, inside `describe("CodexService conversation reopening", …)`, insert these four tests immediately before the describe's closing `});`:

```ts
  it("opens a paper's stored conversation after seeding the context through the host hook", async () => {
    const client = {
      threadResume: vi.fn(async ({ threadId }: { threadId: string }) => ({ thread: { id: threadId, turns: [] } })),
      threadRead: vi.fn(async (threadId: string) => ({ thread: { id: threadId, turns: [] } })),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service } = serviceWithSeeder(client, seedPaperContext);

    await service.openConversationForPaper("1-SECOND");

    expect(seedPaperContext).toHaveBeenCalledWith("1-SECOND");
    expect(client.threadResume).toHaveBeenCalledWith(expect.objectContaining({ threadId: "thread-b" }));
    expect(service.state.activeThreadId).toBe("thread-b");
    expect(service.getActiveReaderContext()?.attachment.key).toBe("SECOND");
  });

  it("starts a fresh thread when the paper has no stored conversation", async () => {
    const client = {
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
      threadResume: vi.fn(),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service, internal } = serviceWithSeeder(client, seedPaperContext);
    internal.sessions = { version: 1, papers: {} };

    await service.openConversationForPaper("1-SECOND");

    expect(seedPaperContext).toHaveBeenCalledWith("1-SECOND");
    expect(client.threadResume).not.toHaveBeenCalled();
    expect(client.threadStart).toHaveBeenCalled();
    expect(service.state.activeThreadId).toBe("thread-new");
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({ threadId: "thread-new" });
  });

  it("falls back to a fresh thread when the stored thread no longer exists on the backend", async () => {
    const client = {
      threadResume: vi.fn(async () => { throw new Error("thread not found"); }),
      threadStart: vi.fn(async () => ({ thread: { id: "thread-new" } })),
      threadSetName: vi.fn(async () => ({})),
    };
    const seedPaperContext = vi.fn(async () => reopeningContext());
    const { service, internal } = serviceWithSeeder(client, seedPaperContext);

    await service.openConversationForPaper("1-SECOND");

    expect(service.state.activeThreadId).toBe("thread-new");
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({ threadId: "thread-new" });
    expect(internal.sessions.history["1-SECOND"]).toEqual([
      expect.objectContaining({ threadId: "thread-b" }),
    ]);
  });

  it("surfaces a seeding failure without touching conversation state", async () => {
    const client = {
      threadResume: vi.fn(),
      threadStart: vi.fn(),
    };
    const seedPaperContext = vi.fn(async () => {
      throw new Error("This Zotero item has no readable PDF attachment");
    });
    const { service, internal } = serviceWithSeeder(client, seedPaperContext);

    await expect(service.openConversationForPaper("1-SECOND"))
      .rejects.toThrow("This Zotero item has no readable PDF attachment");

    expect(service.state.activeThreadId).toBeNull();
    expect(client.threadResume).not.toHaveBeenCalled();
    expect(client.threadStart).not.toHaveBeenCalled();
    expect(internal.paperContexts.has("1-SECOND")).toBe(false);
    expect(internal.sessions.papers["1-SECOND"]).toMatchObject({ threadId: "thread-b" });
  });
```

- [ ] **Step 2: Run the tests expecting FAIL.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/codex-service.test.ts`. Expected: the four new tests fail with `TypeError: service.openConversationForPaper is not a function`; everything else passes.

- [ ] **Step 3: Implement the method.** In `integrations/zotero/src/codex-service.ts`, replace this (the tail of `switchThread` and the head of `switchThreadInternal` — the `void pending.then(clear, clear);` occurrence directly above `switchThreadInternal`, not the one in `newThread`):

```ts
    void pending.then(clear, clear);
    return pending;
  }

  private async switchThreadInternal(threadId: string): Promise<void> {
```

with this:

```ts
    void pending.then(clear, clear);
    return pending;
  }

  /**
   * Opens a paper's stored conversation even when the paper has not been
   * opened in this Zotero run: seeds the Reader context through the host
   * hook when needed, resumes sessions.papers[paperKey].threadId, and falls
   * back to a fresh thread when nothing is stored or the stored thread no
   * longer exists on the backend.
   */
  openConversationForPaper(paperKey: string): Promise<void> {
    return this.enqueuePaperTransition(() => this.openConversationForPaperInternal(paperKey));
  }

  private async openConversationForPaperInternal(paperKey: string): Promise<void> {
    let context = this.paperContexts.get(paperKey) ?? null;
    if (!context?.workspace) {
      context = await this.seedPaperContextFromHost(
        paperKey,
        "Open this conversation's Zotero paper once, then try again",
      );
    }
    const stored = this.sessions.papers[paperKey];
    if (stored && (stored.backend ?? "codex") === this.state.backend) {
      if (stored.threadId === this.state.activeThreadId && !this.state.switchingThreadId) {
        this.callbacks.onState();
        return;
      }
      try {
        await this.switchThreadInternal(stored.threadId);
        return;
      }
      catch {
        // The stored thread no longer exists on this backend; archive the
        // stale pointer instead of losing it, mirroring setPaperInternal's
        // resume-failure branch, then fall through to a fresh thread.
        this.sessions.history ||= {};
        const history = this.sessions.history[paperKey] ||= [];
        if (!history.some((record) => record.threadId === stored.threadId)) {
          history.unshift(stored);
        }
        this.sessions.history[paperKey] = history.slice(0, 30);
        delete this.sessions.papers[paperKey];
      }
    }
    await this.newThreadInternal(context, paperKey);
  }

  private async switchThreadInternal(threadId: string): Promise<void> {
```

- [ ] **Step 4: Run the tests expecting PASS.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/codex-service.test.ts`. Expected: whole file green, contract test at 529-598 included.

- [ ] **Step 5: Full gate.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npm run verify`. Expected: pass.

- [ ] **Step 6: Commit.** Command: `cd /home/chance/quarto-lab && git add integrations/zotero/src/codex-service.ts integrations/zotero/test/codex-service.test.ts && git commit -m "feat(zotero): add CodexService.openConversationForPaper with fresh-thread fallback" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

### Task 4.3: Plugin — factor the background pipeline out of chooseWorkbenchPaper and wire the hook

**Files:**
- Modify: `integrations/zotero/src/plugin.ts:366-374` (CodexService callbacks object built in `startup`), `integrations/zotero/src/plugin.ts:1869-1911` (chooseWorkbenchPaper body), `integrations/zotero/src/plugin.ts:1929` (insert three private methods immediately before `chooseAdditionalPaper`)
- Test: `integrations/zotero/test/plugin-state.test.ts` (append a new describe block at end of file, after line 1349)

**Interfaces:**
- Consumes: `Zotero.Reader.open(attachmentID, null, { allowDuplicate, openInBackground, preventJumpback, openInWindow? })`; `Zotero.Items.getByLibraryAndKeyAsync(libraryID, key)` (optional-chained, same pattern as plugin.ts:2496-2497); `this.readerContext.acceptReaderHook({ reader, item, params }): Promise<ReaderContext>`; `isDedicatedWorkbenchWindow(win: Window | null | undefined): boolean` (imported at plugin.ts:41); `CodexServiceCallbacks.seedPaperContext` from Task 4.1.
- Produces (all private on `ZoteroChatPlugin`): `resolvePaperAttachment(item: any): Promise<any>`; `seedReaderContextInBackground(attachment: any, win: Window): Promise<ReaderContext>`; `seedPaperContextForKey(paperKey: string): Promise<ReaderContext>` — Task 4.4 relies on `resolvePaperAttachment`.

- [ ] **Step 1: Write the failing tests.** Append this at the very end of `integrations/zotero/test/plugin-state.test.ts` (`readFileSync`, `join`, `ZoteroChatPlugin`, and `vi` are already imported at the top of that file):

```ts
describe("QLab paper conversation reopening", () => {
  it("seeds a paper context by opening its PDF in a background Reader tab", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const context = { attachment: { key: "ATTACH", libraryID: 1 }, workspace: { root: "/w" } };
    const attachment = { id: 7, key: "ATTACH", libraryID: 1, isPDFAttachment: () => true };
    const open = vi.fn(async () => ({ itemID: 7 }));
    const win = { setTimeout: (fn: () => void) => setTimeout(fn, 0) } as unknown as Window;
    (globalThis as any).Zotero = {
      Items: { getByLibraryAndKeyAsync: vi.fn(async () => attachment) },
      Reader: { open },
      getMainWindow: () => win,
    };
    const plugin = new ZoteroChatPlugin() as any;
    plugin.readerContext = { acceptReaderHook: vi.fn(async () => context) };

    try {
      await expect(plugin.seedPaperContextForKey("1-ATTACH")).resolves.toBe(context);
      expect((globalThis as any).Zotero.Items.getByLibraryAndKeyAsync).toHaveBeenCalledWith(1, "ATTACH");
      expect(open).toHaveBeenCalledWith(7, null, expect.objectContaining({
        allowDuplicate: false,
        openInBackground: true,
        preventJumpback: true,
      }));
      expect(plugin.readerContext.acceptReaderHook).toHaveBeenCalledWith({
        reader: { itemID: 7 },
        item: attachment,
        params: {},
      });
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("rejects seeding for an item with no readable PDF attachment", async () => {
    const originalZotero = (globalThis as any).Zotero;
    const item = {
      isPDFAttachment: () => false,
      isRegularItem: () => true,
      getBestAttachment: async () => null,
    };
    (globalThis as any).Zotero = {
      Items: { getByLibraryAndKeyAsync: vi.fn(async () => item) },
      Reader: { open: vi.fn() },
      getMainWindow: () => ({}) as Window,
    };
    const plugin = new ZoteroChatPlugin() as any;

    try {
      await expect(plugin.seedPaperContextForKey("1-NOPDF"))
        .rejects.toThrow("This Zotero item has no readable PDF attachment");
      expect((globalThis as any).Zotero.Reader.open).not.toHaveBeenCalled();
    }
    finally {
      (globalThis as any).Zotero = originalZotero;
    }
  });

  it("supplies the background seeding hook to the codex service at startup", () => {
    const plugin = readFileSync(join(process.cwd(), "src/plugin.ts"), "utf8");
    const startup = plugin.slice(
      plugin.indexOf("async startup("),
      plugin.indexOf("async shutdown("),
    );
    expect(startup).toContain("seedPaperContext: (paperKey) => this.seedPaperContextForKey(paperKey)");
  });
});
```

- [ ] **Step 2: Run the tests expecting FAIL.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/plugin-state.test.ts`. Expected: first two new tests fail with `TypeError: plugin.seedPaperContextForKey is not a function`; the third fails on the `toContain` assertion. Pre-existing tests pass.

- [ ] **Step 3: Add the three private methods.** In `integrations/zotero/src/plugin.ts`, replace this (the boundary between `chooseWorkbenchPaper` and `chooseAdditionalPaper`, lines 1925-1929):

```ts
    this.renderChatViews();
    if (tabID) this.workbenchTabs.entries(win).find((entry) => entry.id === tabID)?.view.focusComposer();
    else preferredView?.focusComposer();
  }

  private async chooseAdditionalPaper(win: Window): Promise<void> {
```

with this:

```ts
    this.renderChatViews();
    if (tabID) this.workbenchTabs.entries(win).find((entry) => entry.id === tabID)?.view.focusComposer();
    else preferredView?.focusComposer();
  }

  /** Resolves a Zotero item (regular item or attachment) to its readable PDF attachment. */
  private async resolvePaperAttachment(item: any): Promise<any> {
    let attachment = item;
    if (!item?.isPDFAttachment?.()) {
      attachment = item?.isRegularItem?.() ? await item.getBestAttachment?.() : null;
    }
    const isPDF = Boolean(attachment?.isPDFAttachment?.())
      || attachment?.attachmentContentType === "application/pdf";
    if (!attachment?.id || !isPDF) {
      throw new Error("This Zotero item has no readable PDF attachment");
    }
    return attachment;
  }

  /** Opens the attachment in a background Reader tab and captures its context without disturbing the user's view. */
  private async seedReaderContextInBackground(attachment: any, win: Window): Promise<ReaderContext> {
    const opened = await Zotero.Reader.open(attachment.id, null, {
      allowDuplicate: false,
      openInBackground: true,
      preventJumpback: true,
      ...(isDedicatedWorkbenchWindow(win) ? { openInWindow: true } : {}),
    });
    let accepted: ReaderContext | null = null;
    let lastError: unknown = null;
    for (let attempt = 0; attempt < 80 && !accepted; attempt++) {
      const reader = opened || Zotero.Reader?._readers?.find(
        (candidate: any) => String(candidate?.itemID) === String(attachment.id),
      );
      if (reader) {
        try {
          accepted = await this.readerContext.acceptReaderHook({
            reader,
            item: attachment,
            params: {},
          });
        }
        catch (error) {
          lastError = error;
        }
      }
      if (!accepted) await new Promise<void>((resolve) => win.setTimeout(resolve, 75));
    }
    if (!accepted) {
      throw lastError instanceof Error
        ? lastError
        : new Error("Zotero Reader has not prepared this paper yet; try again shortly");
    }
    return accepted;
  }

  /** Host hook for CodexService: rebuilds a `${libraryID}-${attachmentKey}` paper context via a background Reader tab. */
  private async seedPaperContextForKey(paperKey: string): Promise<ReaderContext> {
    const separator = paperKey.indexOf("-");
    const attachmentKey = paperKey.slice(separator + 1);
    if (separator <= 0 || !attachmentKey) {
      throw new Error("This conversation's Zotero paper could not be identified");
    }
    const libraryID = Number(paperKey.slice(0, separator));
    const item = await Zotero.Items?.getByLibraryAndKeyAsync?.(libraryID, attachmentKey)
      ?? Zotero.Items?.getByLibraryAndKey?.(libraryID, attachmentKey);
    if (!item) throw new Error("This conversation's Zotero paper is no longer in the library");
    const attachment = await this.resolvePaperAttachment(item);
    const win = Zotero.getMainWindow?.() || Zotero.getMainWindows?.()[0];
    if (!win) throw new Error("The Zotero main window is unavailable");
    return this.seedReaderContextInBackground(attachment, win);
  }

  private async chooseAdditionalPaper(win: Window): Promise<void> {
```

- [ ] **Step 4: Make chooseWorkbenchPaper consume the factored pipeline.** In `integrations/zotero/src/plugin.ts`, replace this (lines 1869-1911 — the exact block between the dialog result and `this.addedContextIDs.delete`):

```ts
    const selected = await Zotero.Items.getAsync(selectedID);
    if (!selected) throw new Error("The selected Zotero item does not exist");
    let attachment = selected;
    if (!selected.isPDFAttachment?.()) {
      attachment = selected.isRegularItem?.() ? await selected.getBestAttachment?.() : null;
    }
    const isPDF = Boolean(attachment?.isPDFAttachment?.())
      || attachment?.attachmentContentType === "application/pdf";
    if (!attachment?.id || !isPDF) {
      throw new Error("This Zotero item has no readable PDF attachment");
    }

    const opened = await Zotero.Reader.open(attachment.id, null, {
      allowDuplicate: false,
      openInBackground: true,
      preventJumpback: true,
      ...(isDedicatedWorkbenchWindow(win) ? { openInWindow: true } : {}),
    });
    let accepted: ReaderContext | null = null;
    let lastError: unknown = null;
    for (let attempt = 0; attempt < 80 && !accepted; attempt++) {
      const reader = opened || Zotero.Reader?._readers?.find(
        (candidate: any) => String(candidate?.itemID) === String(attachment.id),
      );
      if (reader) {
        try {
          accepted = await this.readerContext.acceptReaderHook({
            reader,
            item: attachment,
            params: {},
          });
        }
        catch (error) {
          lastError = error;
        }
      }
      if (!accepted) await new Promise<void>((resolve) => win.setTimeout(resolve, 75));
    }
    if (!accepted) {
      throw lastError instanceof Error
        ? lastError
        : new Error("Zotero Reader has not prepared this paper yet; try again shortly");
    }
```

with this:

```ts
    const selected = await Zotero.Items.getAsync(selectedID);
    if (!selected) throw new Error("The selected Zotero item does not exist");
    const attachment = await this.resolvePaperAttachment(selected);
    const accepted = await this.seedReaderContextInBackground(attachment, win);
```

(Do not touch `chooseAdditionalPaper` — its near-duplicate loop is outside this spec's scope.)

- [ ] **Step 5: Wire the hook into the CodexService callbacks.** In `integrations/zotero/src/plugin.ts`, replace this (inside the `new CodexService(...)` call in `startup`, lines 369-374):

```ts
        onFallbackRequested: (error) => {
          this.chatPhase = "unavailable";
          this.chatError = `${error.message}. You can still open the Advanced Terminal from the top bar.`;
          this.renderChatViews();
        },
      },
```

with this:

```ts
        onFallbackRequested: (error) => {
          this.chatPhase = "unavailable";
          this.chatError = `${error.message}. You can still open the Advanced Terminal from the top bar.`;
          this.renderChatViews();
        },
        seedPaperContext: (paperKey) => this.seedPaperContextForKey(paperKey),
      },
```

- [ ] **Step 6: Run the tests expecting PASS.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/plugin-state.test.ts`. Expected: all green, including the three new tests.

- [ ] **Step 7: Full gate.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npm run verify`. Expected: pass (type-check confirms the refactored `chooseWorkbenchPaper` still compiles; `test/runtime-compat.test.ts` source assertions are unaffected).

- [ ] **Step 8: Commit.** Command: `cd /home/chance/quarto-lab && git add integrations/zotero/src/plugin.ts integrations/zotero/test/plugin-state.test.ts && git commit -m "feat(zotero): supply the background reader seeding hook from the plugin" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

### Task 4.4: Plugin — "Open QLab Chat for This Paper" library item menu entry (entry point B)

**Files:**
- Modify: `integrations/zotero/src/plugin.ts:3772-3804` (installQLabMenu), `integrations/zotero/src/plugin.ts:3806-3816` (removeQLabMenu id list), `integrations/zotero/src/plugin.ts:3816` (insert `openConversationForItem` right after `removeQLabMenu`)
- Test: `integrations/zotero/test/plugin-state.test.ts` (add two tests inside the `describe("QLab paper conversation reopening", …)` block created in Task 4.3, before its closing `});`)

**Interfaces:**
- Consumes: `openConversationForPaper(paperKey: string): Promise<void>` (Task 4.2); `private async resolvePaperAttachment(item: any): Promise<any>` (Task 4.3); `private async openWorkbenchTab(win = Zotero.getMainWindow()): Promise<void>` (plugin.ts:1805); `private activeWorkbenchEntry(win = Zotero.getMainWindow())` (plugin.ts:3168); `private updateInteractionContext(): void` (plugin.ts:2376); `private reportError(error: unknown): void` (plugin.ts:3761); `doc.createXULElement("menuitem")` / `menuitem.setAttribute("label", …)` / `"command"` events (existing installQLabMenu pattern).
- Produces: menu item DOM id `qlab-zotero-open-paper-chat` on the `zotero-itemmenu` popup; `private async openConversationForItem(win: Window, item: any): Promise<void>`.

- [ ] **Step 1: Write the failing tests.** In `integrations/zotero/test/plugin-state.test.ts`, inside `describe("QLab paper conversation reopening", …)`, insert these two tests immediately before the describe's closing `});`:

```ts
  it("injects Open QLab Chat for This Paper into the library item context menu", () => {
    const plugin = new ZoteroChatPlugin() as any;
    const doc = document.implementation.createHTMLDocument("Main");
    (doc as any).createXULElement = (name: string) => doc.createElement(name);
    const toolsPopup = doc.createElement("menupopup");
    toolsPopup.id = "menu_ToolsPopup";
    const itemPopup = doc.createElement("menupopup");
    itemPopup.id = "zotero-itemmenu";
    doc.body.append(toolsPopup, itemPopup);
    const item = { id: 6, isPDFAttachment: () => false, isRegularItem: () => true };
    const win = {
      document: doc,
      ZoteroPane: { getSelectedItems: () => [item] },
    } as unknown as Window;
    plugin.openConversationForItem = vi.fn(async () => {});

    plugin.installQLabMenu(win);

    const menuItem = doc.getElementById("qlab-zotero-open-paper-chat");
    expect(menuItem).not.toBeNull();
    expect(menuItem?.getAttribute("label")).toBe("Open QLab Chat for This Paper");
    menuItem?.dispatchEvent(new Event("command"));
    expect(plugin.openConversationForItem).toHaveBeenCalledWith(win, item);

    plugin.removeQLabMenu(win);
    expect(doc.getElementById("qlab-zotero-open-paper-chat")).toBeNull();
  });

  it("opens the stored conversation for a right-clicked library item through the codex service", async () => {
    const plugin = new ZoteroChatPlugin() as any;
    const attachment = { id: 7, key: "ATTACH", libraryID: 1, isPDFAttachment: () => true };
    const item = {
      isPDFAttachment: () => false,
      isRegularItem: () => true,
      getBestAttachment: async () => attachment,
    };
    const openConversationForPaper = vi.fn(async () => {});
    plugin.codex = { openConversationForPaper };
    plugin.openWorkbenchTab = vi.fn(async () => {});
    plugin.updateInteractionContext = vi.fn();
    plugin.renderChatViews = vi.fn();
    plugin.activeWorkbenchEntry = vi.fn(() => null);
    const win = {} as Window;

    await plugin.openConversationForItem(win, item);

    expect(plugin.openWorkbenchTab).toHaveBeenCalledWith(win);
    expect(openConversationForPaper).toHaveBeenCalledWith("1-ATTACH");
    expect(plugin.renderChatViews).toHaveBeenCalled();
  });
```

- [ ] **Step 2: Run the tests expecting FAIL.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/plugin-state.test.ts`. Expected: the first new test fails at `expect(menuItem).not.toBeNull()` (received null); the second fails with `TypeError: plugin.openConversationForItem is not a function`.

- [ ] **Step 3: Inject the menu item.** In `integrations/zotero/src/plugin.ts`, replace this (the end of `installQLabMenu`, line 3803-3804):

```ts
    popup.append(separator, workbench, standalone, choose, importItem);
  }
```

with this:

```ts
    popup.append(separator, workbench, standalone, choose, importItem);

    const itemPopup = doc.getElementById("zotero-itemmenu");
    if (itemPopup && !doc.getElementById("qlab-zotero-open-paper-chat")) {
      const paperChat = doc.createXULElement("menuitem");
      paperChat.id = "qlab-zotero-open-paper-chat";
      paperChat.setAttribute("label", "Open QLab Chat for This Paper");
      paperChat.addEventListener("command", () => {
        const item = (win as any).ZoteroPane?.getSelectedItems?.()?.[0];
        if (!item) {
          this.reportError(new Error("Select a Zotero library item first"));
          return;
        }
        void this.openConversationForItem(win, item).catch((error) => this.reportError(error));
      });
      itemPopup.append(paperChat);
    }
  }
```

- [ ] **Step 4: Remove the item on window unload.** In `integrations/zotero/src/plugin.ts`, replace this (removeQLabMenu id list, lines 3806-3816 pre-edit):

```ts
  private removeQLabMenu(win: Window): void {
    for (const id of [
      "qlab-zotero-separator",
      "qlab-zotero-open-workbench",
      "qlab-zotero-open-standalone",
      "qlab-zotero-choose-root",
      "qlab-zotero-import-literature",
    ]) {
      win.document.getElementById(id)?.remove();
    }
  }
```

with this:

```ts
  private removeQLabMenu(win: Window): void {
    for (const id of [
      "qlab-zotero-separator",
      "qlab-zotero-open-workbench",
      "qlab-zotero-open-standalone",
      "qlab-zotero-choose-root",
      "qlab-zotero-import-literature",
      "qlab-zotero-open-paper-chat",
    ]) {
      win.document.getElementById(id)?.remove();
    }
  }

  /** Opens the right-clicked library item's stored QLab conversation (or a fresh thread when none is stored). */
  private async openConversationForItem(win: Window, item: any): Promise<void> {
    const attachment = await this.resolvePaperAttachment(item);
    const paperKey = `${attachment.libraryID ?? "0"}-${attachment.key}`;
    await this.openWorkbenchTab(win);
    this.selectedImportedChatID = null;
    await this.codex.openConversationForPaper(paperKey);
    this.updateInteractionContext();
    this.chatError = "";
    this.renderChatViews();
    this.activeWorkbenchEntry(win)?.view.focusComposer();
  }
```

(`${attachment.libraryID ?? "0"}-${attachment.key}` intentionally matches both `paperIdentity()` in codex-service.ts:1952-1954 and the `ConversationPaper.id` construction at plugin.ts:1984.)

- [ ] **Step 5: Run the tests expecting PASS.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/plugin-state.test.ts`. Expected: all green.

- [ ] **Step 6: Full gate.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npm run verify`. Expected: pass.

- [ ] **Step 7: Commit.** Command: `cd /home/chance/quarto-lab && git add integrations/zotero/src/plugin.ts integrations/zotero/test/plugin-state.test.ts && git commit -m "feat(zotero): add Open QLab Chat for This Paper to the library item menu" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

### Task 4.5: Regression gate — independence contract and full verification

**Files:**
- Test: `integrations/zotero/test/codex-service.test.ts:529-598` (must be byte-identical to before this section), `integrations/zotero/test/plugin-state.test.ts`, `integrations/zotero/test/runtime-compat.test.ts`

**Interfaces:**
- Consumes: everything landed in Tasks 4.1-4.4. Produces: nothing — verification only, no commit.

- [ ] **Step 1: Prove the contract test is untouched.** Command: `cd /home/chance/quarto-lab && git diff HEAD~4 -- integrations/zotero/test/codex-service.test.ts | grep '^-' | grep -v '^---'` (HEAD~4 = the state before this section's four commits). Expected: empty output — the diff contains only added lines, so `test/codex-service.test.ts:529-598` ("keeps PDF focus, selected chat, and running turns independent") is unchanged. If any `-` lines appear, stop and restore the original test content before proceeding.

- [ ] **Step 2: Run the contract test and both touched suites.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npx vitest run test/codex-service.test.ts test/plugin-state.test.ts test/runtime-compat.test.ts`. Expected: all pass, explicitly including "keeps PDF focus, selected chat, and running turns independent" (this section's seeding never touches `focusedContext`/`focusedPaperKey`, so focus and selection remain independent axes) and runtime-compat's "keeps QLab out of Zotero's item sidebar" (this section adds a context-menu item, not an ItemPaneManager section).

- [ ] **Step 3: Full gate.** Command: `cd /home/chance/quarto-lab/integrations/zotero && npm run verify`. Expected: check + full test suite + build all pass. No commit in this task; the CHANGELOG/README/version bump for the whole Fix Pack lands in the separate release-chores commit defined by the spec's Cross-cutting section.

---

## Section 5 — Release chores (last, after Sections 1–4)

Per the spec's Cross-cutting rules: CHANGELOG entries for all four items and the
version bump land as their own final commit. (README was already updated by
Task 3.5 and needs nothing further here.)

### Task 5.1: CHANGELOG entries and version 0.10.0

**Files:**
- Modify: `integrations/zotero/CHANGELOG.md:1-3` (insert a new release section under `# Changelog`)
- Modify: `integrations/zotero/manifest.json:4` (`"version": "0.9.0"`)
- Modify: `integrations/zotero/package.json:3` (`"version": "0.9.0"`)
- Test: `integrations/zotero/test/manifest.test.ts:25` (asserts the exact manifest version)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: nothing consumed later; this is the final commit.

- [ ] **Step 1: Update the version test first.** In `integrations/zotero/test/manifest.test.ts`, replace:

  ```ts
    expect(manifest.version).toBe("0.9.0");
  ```

  with:

  ```ts
    expect(manifest.version).toBe("0.10.0");
  ```

- [ ] **Step 2: Run the test and confirm it fails.** From `/home/chance/quarto-lab/integrations/zotero`:

  ```bash
  npx vitest run test/manifest.test.ts
  ```

  Expected: FAIL — `expected '0.9.0' to be '0.10.0'`.

- [ ] **Step 3: Bump both version fields.** In `integrations/zotero/manifest.json` replace `"version": "0.9.0",` with `"version": "0.10.0",`. In `integrations/zotero/package.json` replace `"version": "0.9.0",` with `"version": "0.10.0",`.

- [ ] **Step 4: Add the CHANGELOG section.** In `integrations/zotero/CHANGELOG.md`, replace:

  ```markdown
  # Changelog

  ## 0.9.0
  ```

  with:

  ```markdown
  # Changelog

  ## 0.10.0

  - Fix Research Action chips (Summarize, Evidence QA, Compare Papers) on Workbench surfaces: clicks now dispatch the action, and chips are no longer rebuilt mid-click during streaming re-renders.
  - Align Visual Edit with the compiled draft preview: KaTeX on both sides (draft previews now compile with `html-math-method: katex`), Pandoc-style soft line breaks, matched typography, and full list-grammar support.
  - Add region screenshots: a reader toolbar capture button with a crosshair drag overlay, plus a "Screenshot Region" Add-Context entry; cropped regions attach as "Region Screenshot" chips.
  - Reopen a paper's stored conversation without its PDF open: conversation tabs and History seed the paper in a background reader tab, and library items gain "Open QLab Chat for This Paper".

  ## 0.9.0
  ```

- [ ] **Step 5: Run the full gate.** From `/home/chance/quarto-lab/integrations/zotero`:

  ```bash
  npm run verify
  ```

  Expected: PASS (type check, full vitest suite, build).

- [ ] **Step 6: Commit.**

  ```bash
  cd /home/chance/quarto-lab && git add integrations/zotero/CHANGELOG.md integrations/zotero/manifest.json integrations/zotero/package.json integrations/zotero/test/manifest.test.ts && git commit -m "chore(zotero): release 0.10.0 — Fix Pack A" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  ```
