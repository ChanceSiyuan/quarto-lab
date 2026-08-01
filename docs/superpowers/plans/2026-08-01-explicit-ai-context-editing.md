# Explicit AI Context Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one explicit **Edit with AI** button that lets the active dedicated AI Context conversation revise its complete QMD in a private working copy, then lets the user review with the eye control and accept with **Keep**.

**Architecture:** Extend `QmdWorkspaceView` with an `on-demand` Agent-copy policy. Opening an AI Context remains zero-write and exposes no editable path to Codex. The button prepares the existing private-copy abstraction, publishes that path to the active Codex thread, and invokes one fixed edit turn whose sandbox is narrowed to that copy's isolated directory. Existing turn-state notifications keep the button busy until the real turn completes; then the existing fingerprint, compare, and Keep machinery refreshes. Visual-editor completion messages carry their originating document generation so stale saves cannot overwrite the current document status.

**Tech Stack:** TypeScript 7, Vitest 4 with Happy DOM, Zotero plugin UI, existing Codex app-server integration, existing QMD working-copy/preview services.

## Constraints

- Work only on `feat/issue-8-aicontext-attachment`; do not merge `main`, open a PR, or deploy.
- Test first for each production change and commit each task separately.
- Double-click/open of an AI Context must not call `prepareChange`, create/synchronize a working copy, or expose an editable path.
- The button text is exactly `Edit with AI`. No modal, extra composer message, new merge engine, or automatic overwrite.
- Clicking the button uses the currently active dedicated AI Context thread and its full existing conversation. It sends one fixed instruction; the user does not type another request.
- Codex may write only the existing private working-copy path. Human Visual Edit and external editors continue to edit the original QMD directly.
- The fixed turn must not inherit the normal QLab Agent write roots (`drafts/`, `literature/`, and all of `work/`); its only writable root is the isolated directory containing the prepared copy.
- The eye compares original and private-copy previews. `Keep` remains the only operation that replaces the original with the reviewed private copy.
- Reopening the AI Context restores the `on-demand` gate, even if a prior private copy exists. Ordinary Draft opens keep their current eager Agent-copy behavior.
- Preserve `src/app/page.tsx`, `src/app/globals.css`, `src/app/layout.tsx`, `.openai/hosting.json`, trusted `knowledge/`, and generated `public/knowledge/`.

## Task 1: Make Visual Edit statuses document-scoped

**Files:**

- Modify: `integrations/zotero/src/qmd-visual-editor.ts`
- Modify: `integrations/zotero/src/qmd-workspace.ts`
- Test: `integrations/zotero/test/qmd-visual-editor.test.ts`
- Test: `integrations/zotero/test/qmd-workspace.test.ts`

- [ ] **Step 1: Add failing editor-generation tests**

Extend the editor test harness so `setDocument` receives a numeric document generation and `save`/`onStatus` record that generation. Cover:

```ts
editor.setDocument({ source: SOURCE, revision: "r1" }, true, 1);
// Start a save, then replace the editor with generation 2 before it settles.
editor.setDocument({ source: SOURCE, revision: "r2" }, true, 2);
oldSave.reject(new Error("old conflict"));
expect(onStatus).not.toHaveBeenCalledWith("old conflict", "conflict", 1);
```

Also prove a current-generation conflict still reports after the workspace switches from Visual Edit to Website Preview.

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
cd integrations/zotero
npx vitest run test/qmd-visual-editor.test.ts test/qmd-workspace.test.ts
```

Expected: the new generation arguments/behavior are absent and at least one new assertion fails.

- [ ] **Step 3: Carry the operation generation through the editor**

Change the interfaces to:

```ts
interface QmdVisualEditorOptions {
  save(source: string, expectedRevision: string, generation: number): Promise<QmdSourceSnapshot>;
  onStatus?(message: string, state: QmdVisualStatus, generation: number): void;
}

setDocument(snapshot: QmdSourceSnapshot, editable: boolean, generation = 0): void;
```

Capture the generation in each `ActiveEdit`. Emit statuses only while that edit remains current. In the workspace, pass `openGeneration` to `setDocument`, pass the callback generation into `saveVisualSource`, and accept a status only when its generation equals the current open generation. Remove the shared `visualSaveGeneration` slot and do not suppress a current save conflict merely because Website Preview is visible.

- [ ] **Step 4: Run focused tests and typecheck**

```bash
cd integrations/zotero
npx vitest run test/qmd-visual-editor.test.ts test/qmd-workspace.test.ts
npm run check
```

- [ ] **Step 5: Commit**

```bash
git add integrations/zotero/src/qmd-visual-editor.ts \
  integrations/zotero/src/qmd-workspace.ts \
  integrations/zotero/test/qmd-visual-editor.test.ts \
  integrations/zotero/test/qmd-workspace.test.ts
git commit -m "fix(zotero): scope visual save status to document"
```

## Task 2: Add the on-demand private-copy button

**Files:**

- Modify: `integrations/zotero/src/qmd-workspace.ts`
- Modify: `integrations/zotero/src/styles.css`
- Test: `integrations/zotero/test/qmd-workspace.test.ts`
- Test: `integrations/zotero/test/visual/surfaces.mjs`

- [ ] **Step 1: Add failing workspace tests**

Add `onEditWithAI` to the workspace harness and cover all of these observable cases:

1. `open(DRAFT, { agentCopy: "on-demand" })` shows a visible text button, calls neither `prepareChange` nor `onEditWithAI`, hides compare/Keep, and publishes `(DRAFT, null)`.
2. One click calls `prepareChange` once, publishes `(DRAFT, CHANGE)`, then calls `onEditWithAI(DRAFT, CHANGE)` once.
3. While prepare/turn is pending, repeated clicks are single-flight and the button is disabled with `aria-busy="true"`. `onEditWithAI` resolving only means the turn was accepted; it does not end the busy state.
4. `syncAgentChanges({ running: true, ... })` marks the real turn as started. Only a later `running: false` ends the action and performs the authoritative fingerprint refresh; then the eye and Keep enable only when `changed` is true.
5. Prepare or turn failure never overwrites the original, reports an error, and leaves the button retryable.
6. Reopen, a different path, or destroy invalidates late prepare/turn completions.
7. Visual Edit before button activation saves the original and does not silently enable Codex editing.
8. Ordinary Drafts still default to eager private-copy preparation.

- [ ] **Step 2: Run the focused workspace test and confirm RED**

```bash
cd integrations/zotero
npx vitest run test/qmd-workspace.test.ts
```

- [ ] **Step 3: Implement the deep workspace policy**

Extend the public seam narrowly:

```ts
interface QmdWorkspaceOptions {
  onEditWithAI?(relativePath: string, changePath: string): Promise<void> | void;
}

interface QmdWorkspaceOpenOptions {
  agentCopy?: "enabled" | "on-demand" | "disabled";
}

interface QmdAgentState {
  activeTurnId: string | null;
  running: boolean;
  diffs: readonly QmdAgentDiff[];
}
```

Add a toolbar button whose visible text and accessible name are `Edit with AI`. Keep separate state for the open policy, whether this open has activated its copy, and the one in-flight button action. A helper such as `agentCopyIsActive()` must be used consistently by `show`, `syncAgentChanges`, preview/Keep controls, Visual Edit saves, and stale-operation guards.

Button flow:

```text
idle -> prepareChange -> publish editable path -> onEditWithAI (turn accepted)
     -> observe running=true -> observe running=false
     -> prepareChange again -> update eye/Keep from authoritative fingerprint
```

The original remains untouched throughout. A stale completion must have no UI, active-document, preview, or status effect. A failed/interrupted/no-diff Codex turn reaches the same `running=false` refresh, leaves the already-authorized private path active for this open, re-enables the button, and does not enable Keep unless the fingerprint says it changed. A pre-existing unrelated running turn disables the button and is never steered by this action.

- [ ] **Step 4: Style the explicit label and update the static visual fixture**

Add only a narrow override such as:

```css
.zc-qmd-toolbar .zc-qmd-enable-ai-editing {
  flex-basis: auto;
  width: auto;
  padding: 0 8px;
  font-size: 11px;
}
```

Do not redesign the toolbar.

- [ ] **Step 5: Run focused tests, visual structure tests, and typecheck**

```bash
cd integrations/zotero
npx vitest run test/qmd-workspace.test.ts
npm run test:visual
npm run check
```

- [ ] **Step 6: Commit**

```bash
git add integrations/zotero/src/qmd-workspace.ts \
  integrations/zotero/src/styles.css \
  integrations/zotero/test/qmd-workspace.test.ts \
  integrations/zotero/test/visual/surfaces.mjs
git commit -m "feat(zotero): gate AI Context edits behind a button"
```

## Task 3: Start one dedicated AI Context edit turn

**Files:**

- Modify: `integrations/zotero/src/codex-service.ts`
- Modify: `integrations/zotero/src/plugin.ts`
- Test: `integrations/zotero/test/codex-service.test.ts`
- Test: `integrations/zotero/test/plugin-ai-context.test.ts`

- [ ] **Step 1: Add failing plugin integration tests**

Prove that AI Context activation now opens with `{ agentCopy: "on-demand" }`. Capture the workspace callback passed by the real `openQmdDocument` seam and prove that clicking it:

- requires the active path, canonical repository root, and dedicated thread to still match the opened AI Context;
- invokes `codex.send` once with the selected model/effort, no screenshots, a writable-root override containing only the private copy's isolated directory, and a fixed instruction to revise the complete active AI Context only through the private copy;
- does not call `aiContexts.save`, the synthesis generator, projection, CAS, repair, or any Knowledge-writing path; and
- surfaces a rejected turn to the workspace so the button can retry.

Add a Codex service test proving `send()` still resolves after `turnStart` acceptance while `state.running` remains true, and proving the requested narrow root becomes the exact `sandboxPolicy.writableRoots` for that turn. Also prove a read-only or steered turn cannot request new writable roots and that the ordinary Agent default remains unchanged.

The turn-level boundary must also cover app-server permission escalation. Record an override by the `(threadId, turnId)` returned from `turnStart`; `requestUserApproval` must use that exact scope instead of broad `qlabWritableRoots` for the scoped turn. Tests must prove a request inside the private-copy directory is accepted while requests for the original AI Context under `drafts/`, another `work/` directory, and network access are rejected. Clear the recorded scope on `turn/completed`, `turn/failed`, interruption, disconnect, and service shutdown.

The fixed instruction should be asserted by meaning, not brittle full-string whitespace. It must include all of these rules:

```text
use the full current dedicated conversation
revise the complete active AI Context QMD
write only the private working-copy path supplied in QMD Editor context
preserve valid frontmatter and managed-marker structure
do not edit the original Draft or trusted knowledge
leave the result for eye/Keep review
```

- [ ] **Step 2: Run focused plugin tests and confirm RED**

```bash
cd integrations/zotero
npx vitest run test/plugin-ai-context.test.ts
```

- [ ] **Step 3: Wire the callback and authority checks**

Pass `onEditWithAI` when constructing `QmdWorkspaceView`. Implement one private plugin method that validates the current dedicated AI Context identity, connection/sign-in state, path, root, and private-copy path before calling `codex.send`. Resolve the already-created private-copy directory through the existing canonical/symlink-safe repository-path guard and pass it as the turn's sole writable root. Do not route through `Save / Update AI Context`; that remains the managed-block capture workflow.

Extend the internal send seam narrowly:

```ts
interface CodexSendOptions {
  readOnly?: boolean;
  writableRoots?: readonly string[];
}
```

`turnModeSettings` must copy this exact override into a `workspaceWrite` policy instead of the normal QLab roots. Reject `readOnly` combined with writable roots, and reject a writable-root override when a turn is already running because steering cannot replace that turn's sandbox. This option is turn-local; it does not mutate thread defaults or later composer turns. Track the override for approval checks only for the returned turn identity and delete it on every terminal/transport cleanup path. The plugin must refuse to start while `codex.state.running` is already true, preventing the fixed action from becoming a steering message.

Open AI Contexts with:

```ts
{ agentCopy: "on-demand" }
```

The existing `QMD Editor` interaction context supplies the exact private-copy path and sandbox authority only after the workspace button publishes it.

- [ ] **Step 4: Run focused tests and typecheck**

```bash
cd integrations/zotero
npx vitest run test/plugin-ai-context.test.ts test/qmd-workspace.test.ts test/codex-service.test.ts
npm run check
```

- [ ] **Step 5: Commit**

```bash
git add integrations/zotero/src/codex-service.ts integrations/zotero/src/plugin.ts \
  integrations/zotero/test/codex-service.test.ts integrations/zotero/test/plugin-ai-context.test.ts
git commit -m "feat(zotero): start AI Context edits from its toolbar"
```

## Task 4: Document and verify the release candidate

**Files:**

- Modify: `integrations/zotero/README.md`
- Modify: `integrations/zotero/CHANGELOG.md`
- Modify: this plan only to mark completed checkboxes if useful

- [ ] **Step 1: Update user-facing behavior**

Document this exact sequence: open is read-only to Codex; click **Edit with AI**; the dedicated conversation revises a private copy; click the eye to compare; click **Keep** to replace the original. State that Visual Edit/external editors still edit the original directly and that reopening requires the button again.

- [ ] **Step 2: Run the complete Zotero verification**

```bash
cd integrations/zotero
npm run check
npm test
npm run test:visual
npm run build
```

- [ ] **Step 3: Run repository gates**

```bash
make knowledge-check
make build
make test
git diff 170fb2d5 -- src/app/page.tsx src/app/globals.css src/app/layout.tsx .openai/hosting.json
git status --short
```

Record pre-existing/environment failures exactly; do not repair unrelated baseline state. Native Zotero 9 double-click/button/eye/Keep behavior is a manual smoke gate if a Zotero runtime is unavailable.

- [ ] **Step 4: Commit docs**

```bash
git add integrations/zotero/README.md integrations/zotero/CHANGELOG.md
git commit -m "docs(zotero): explain explicit AI Context editing"
```

- [ ] **Step 5: Independent review and final branch verification**

Request parallel specification and standards reviews against `170fb2d5`. Resolve only in-scope findings, rerun affected tests, then verify the exact final `HEAD`.

- [ ] **Step 6: Push and comment without merging**

```bash
git push -u origin feat/issue-8-aicontext-attachment
gh issue comment 8 --repo ChanceSiyuan/quarto-lab --body-file .generated/verification/issue-8-comment.md
git ls-remote --heads origin feat/issue-8-aicontext-attachment
```

The issue comment must link the branch, summarize the button/eye/Keep workflow, list exact verification evidence and any native/environment limitation, and state explicitly that nothing was merged to `main` or deployed.
