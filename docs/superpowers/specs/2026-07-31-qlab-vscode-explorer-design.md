# QLab VS Code Explorer Sidebar — Design Spec

- **Date:** 2026-07-31
- **Status:** Visual design approved by user; pending written-spec review
- **Target:** `integrations/zotero` QMD Workspace
- **Superdesign canvas:** <https://superdesign.dev/teams/7623f2af-92ca-422d-8eea-cb9900e4f24c/projects/0d3a1909-fb62-4e3a-832f-6aafbe2d4320>
- **Approved preview:** <https://p.superdesign.dev/draft/10e42432-83c6-497d-9fb3-24118266ec09>
- **Local approved capture:**
  [`.superdesign/references/qlab-vscode-explorer-approved-light-1440x900.png`](../../../.superdesign/references/qlab-vscode-explorer-approved-light-1440x900.png)
- **Capture contract:** 1440x900 CSS pixels, DPR 1, light color scheme,
  SHA-256 `989f92f65b27634f10df36013d0b677183e8ea5452cbc5d9f9004c69843324f5`

Unless prefixed otherwise, source paths below are relative to
`integrations/zotero/`.

## Overview

Replace the QMD Workspace's bespoke 176px Draft/Knowledge file list with a
faithful VS Code Explorer surface. The redesign covers the Explorer's visual
language, tree interaction, keyboard model, accessibility, width persistence,
and trust-aware state. It does not turn QLab into a general-purpose filesystem
manager.

The same Explorer component renders repository entries for a local Repository
Target or an SSH Repository Target. Execution location is shown by the
Workbench target/status surface, not by decorating file-tree rows.

## Source boundary

The trusted knowledge resolver returned only `knowledge/index.qmd`, which has
no Explorer or UI guidance. VS Code measurements and interaction behavior in
this spec are therefore **external official reference material**, not learned
Research Loop knowledge. They were checked against the current
`microsoft/vscode` `main` branch at SHA `3e4479f4` and official VS Code
documentation on 2026-07-31.

No real file under `drafts/` or `literature/` was read for the visual design.
The canvas uses invented QMD names.

## Current problem

`QmdWorkspaceView` constructs the file column directly in
`src/qmd-workspace.ts:154-276` and recursively renders rows in
`src/qmd-workspace.ts:963-1013`. Its current presentation is:

- fixed 176px width;
- an always-visible 18px `‹` collapse strip;
- 10.5px rows with `3px 6px` padding and 11px depth increments;
- Unicode `▾` / `▸` included in the label string;
- no file or folder resource-icon abstraction;
- no Explorer title or action area;
- active and hover states, but no distinct keyboard-focus model;
- incomplete tree ARIA: directories do not expose `aria-expanded`, and rows do
  not expose level, set size, position, or selection.

The tree behavior is useful and must survive the redesign: Knowledge and Draft
are separately visible; QMD extensions are hidden; roots start expanded;
directories sort before files; Draft pending changes bubble to ancestor rows;
and transient index errors retain the last useful tree.

## Goals

1. Make the file column visually and behaviorally recognizable as VS Code
   Explorer rather than a custom nested button list.
2. Preserve the physical trust distinction between trusted Knowledge and
   untrusted Draft.
3. Use one target-independent component for local and SSH repository entries.
4. Preserve current local file-open, refresh, Quick Open, pending-review,
   preview, Visual Edit, and Add-to-Knowledge workflows. SSH promotion remains
   disabled until its separate trust-gated design lands.
5. Add complete keyboard navigation and tree accessibility.
6. Add a real visual regression fixture containing nested, selected, collapsed,
   and pending rows.

## Non-goals

- Reproducing VS Code's Activity Bar, Open Editors view, Search view, Source
  Control view, Status Bar, or complete application shell.
- Implementing arbitrary rename, delete, move, drag-and-drop, copy/paste, or
  multi-selection file mutations in this slice.
- Treating `knowledge/` and `drafts/` as equivalent writable directories.
- Sending local filesystem paths to a remote Codex runtime.
- Designing or enabling remote Draft-to-Knowledge promotion.
- Changing QMD preview, Visual Edit rendering, toolbar command semantics, or
  Quick Open results.
- Adding decorative Local/SSH badges inside the tree.

## Visual contract

### Container and width

- Initial Explorer width is 240px.
- Minimum width is 170px; maximum width is 40% of the QMD Workspace body when
  that is at least 170px. The preview/editor keeps at least 240px. Below a 411px
  body width, Explorer auto-hides and remains available through Toggle Explorer;
  from 411px through 424px the 170px minimum wins over the 40% guideline.
- A VS Code-style sash replaces the visible 18px collapse strip. The visible
  divider is 1px; the hit target is 4px and shows the active accent on hover or
  drag.
- Width is persisted per Repository Target. The local target-switch fix lands a
  minimal `targetId` and `targetEpoch` before this component, so Explorer never
  introduces a second canonical-root persistence scheme.
- The existing hide/show capability remains, but moves to a **Toggle Explorer**
  command (`Cmd/Ctrl+B`) and **Hide Explorer** in the Explorer `…` menu. While
  hidden, a 28px **Show Explorer** icon button appears in the existing QMD
  toolbar; it disappears when the Explorer is visible. Hiding remembers the last
  nonzero width and restoring uses it. No inline `‹` / `›` control remains.

Persisted `userHidden` is distinct from layout-derived `autoHidden`. Below
411px, `autoHidden` removes the side-by-side column without changing
`userHidden`; Show/Toggle Explorer opens a 170px modal-like overlay above the
preview. The overlay closes on Escape, outside click, file activation, explicit
toggle, or resize back to side-by-side width. It traps neither application focus
nor preview state. If `userHidden` is true, Show first clears it and then uses
the appropriate side-by-side or narrow-overlay presentation.

### Explorer title and actions

The column begins with an uppercase `EXPLORER` title area. Primary actions use
Codicons and retain VS Code ordering:

1. New File;
2. New Folder;
3. Refresh Explorer;
4. Collapse All.

Refresh and Collapse All ship in the first UI slice. New File and New Folder
are capability-gated repository mutations:

- they are disabled when selection resolves to Knowledge, multiple parents, or
  another ambiguous creation context;
- they remain disabled when the current repository adapter does not advertise
  safe Draft creation;
- they become enabled only after the Draft create operations are defined on
  `QLabRepository`, including remote path validation and revision semantics;
- disabled actions use `aria-disabled="true"` and a tooltip explaining the
  unavailable capability; they are not dead clickable controls.

Secondary actions belong under the standard `…` overflow. Existing QMD toolbar
actions remain outside the Explorer header. The secondary overflow action is
revealed when the Explorer header is hovered or keyboard-focused, so the
approved resting-state capture remains unchanged.

The approved header geometry is fixed: 35px high, `0 8px 0 20px` padding,
11px/700 uppercase title with 0.5px letter spacing, 22px square action targets,
2px action gap, and 16px Codicons. Action hover uses the list hover token;
keyboard focus uses `focusBorder`. Disabled create actions remain focusable
buttons with `aria-disabled="true"`; click and activation are intercepted and an
accessible description explains the missing Draft capability. Native
`disabled` is not used because it would make that explanation unreachable from
the keyboard.

### Roots and hierarchy

`Trusted Knowledge` and `Draft` render as ordinary top-level directory rows in
one repository tree. They are not cards, pills, colored accordion headers, or
separate file systems.

Their behavior remains asymmetric:

- Knowledge files are read-only and use the existing validation/preview path.
- Draft files expose compliance, review, AI compare/Keep, and Visual Edit.
- A Draft pending-AI decoration appears on the affected file and bubbles to its
  directory ancestors through the Draft root.

Both roots initially expand. Descendant expansion state is remembered per
Repository Target and relative directory path. Switching targets never applies
one repository's expanded or selected paths to another.

### Rows, indentation, and twisties

The current VS Code implementation values are the fidelity baseline:

- row height and line-height: 22px;
- default font size: 13px Workbench UI font;
- depth increment: 8px;
- twisty slot: 16px;
- twisty icon: 10px Codicon;
- twisty right padding: 6px;
- twisty horizontal translation: 3px;
- expanded: down chevron;
- collapsed: the same chevron rotated -90 degrees;
- resource icon box: 16px by 22px with a 6px label gap;
- row right padding: 12px;
- single-line labels with ellipsis;
- 10px overlay scrollbar lane whose thumb appears on tree hover, with a 20px
  minimum thumb and no layout-width change.

File basenames remain extensionless in the displayed tree, while accessible
labels and tooltips may expose the full `.qmd` name and repository-relative
path.

### Resource icons

Resource icons use a `FileIconTheme` abstraction rather than hard-coded emoji,
Unicode folders, or one permanent color:

- toolbar and twisty icons come from the bundled Codicon subset;
- file/folder resource icons come from the active file-icon mapping;
- the first implementation bundles only the icons required for `.qmd`, generic
  files, directories, and repository roots;
- the default mapping follows VS Code's built-in Seti behavior;
- themes that omit folder glyphs do not receive an invented folder icon;
- icon theming cannot hide or blur the Knowledge/Draft trust distinction.

No runtime icon, font, or CSS asset is fetched from a CDN. Required SVG paths or
font subsets are bundled with the XPI and usable offline. Bundled Codicon and
Seti-derived assets retain their upstream MIT license and attribution notices.

### Theme tokens

The component uses VS Code list/tree semantic tokens rather than selectors with
hard-coded state colors:

- `sideBar.background`, `sideBar.border`, `sideBar.foreground`;
- `list.hoverBackground`;
- `list.activeSelectionBackground/Foreground`;
- `list.inactiveSelectionBackground/Foreground`;
- `list.focusBackground/Foreground`;
- `list.focusAndSelectionOutline`;
- `tree.indentGuidesStroke` and active variant;
- `focusBorder`.

The approved light canvas uses Light Modern values:

```text
sidebar background       #F8F8F8
sidebar border           #E5E5E5
foreground               #3B3B3B
active selection bg      #E8E8E8
active selection fg      #000000
hover bg                 #F2F2F2
focus outline            #005FB8
```

The corresponding approved Dark Modern mapping is:

```text
sidebar background       #181818
sidebar border           #2B2B2B
foreground               #CCCCCC
active selection bg      #37373D
active selection fg      #FFFFFF
hover bg                 #2A2D2E
focus outline            #007FD4
```

Tokens not overridden by the chosen Modern theme use the current VS Code base
theme defaults and are captured in the component CSS variables rather than
falling back to QLab's warm dashboard colors. Production does not force light
mode or reuse the root dashboard's warm-paper palette.

### Hover, focus, and selection

These states are separate:

- **focus** is the single keyboard cursor;
- **selection** is the current operation/open-file set;
- **active selection** applies while the tree has keyboard focus;
- **inactive selection** persists after focus leaves the tree;
- hover applies only to a row that is neither focused nor selected;
- focus and selected outlines are 1px with -1px outline offset.

QLab still activates only one QMD at a time, while the Explorer may select
multiple visible rows. `activeFilePath`, `selectedPaths`, and `focusedPath`
therefore remain independent.

## Component boundary

Extract file-tree rendering from the 1,000-line `QmdWorkspaceView` into a
focused `QmdFileExplorer` module. The component owns DOM and ephemeral Explorer
interaction state; it performs no filesystem IO.

```ts
export interface QmdExplorerEntry {
  relativePath: string;
  parentPath: string | null;
  name: string;
  fullName: string;
  kind: "directory" | "qmd";
  tree: "knowledge" | "drafts";
  pending: boolean;
  readOnly: boolean;
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
  availability: "ready" | "connecting" | "disconnected" | "error";
  availabilityMessage: string | null;
  refreshing: boolean;
  capabilities: {
    createDraftFile: boolean;
    createDraftFolder: boolean;
  };
}

export interface QmdFileExplorerCallbacks {
  onOpen(relativePath: string): Promise<void> | void;
  onRefresh(): Promise<void> | void;
  onSelectedPathsChange(paths: ReadonlySet<string>): void;
  onFocusedPathChange(path: string | null): void;
  onExpandedPathsChange(paths: ReadonlySet<string>): void;
  onWidthChange(width: number): void;
  onUserHiddenChange(hidden: boolean): void;
  onCreateDraftFile?(request: {
    parentPath: string;
    name: string;
  }): Promise<{ relativePath: string }>;
  onCreateDraftFolder?(request: {
    parentPath: string;
    name: string;
  }): Promise<{ relativePath: string }>;
}
```

`QmdWorkspaceView` continues to own preview/editor mode, Draft compliance,
review, AI-change comparison, Keep, and index refresh/subscription policy. It
passes index results and current path into `QmdFileExplorer`; file activation
returns through `onOpen`, independently of selection and focus.

The component is controlled for target identity, index, active document,
selection, focus, expansion, visibility, and width. It owns only pointer hover,
type-ahead buffer, in-progress inline creation, layout-derived `autoHidden`,
narrow-overlay visibility, and in-progress sash drag state. A new `(targetId,
targetEpoch)` snapshot cancels those ephemeral interactions and replaces the
complete controlled state; callbacks from an older epoch are ignored by
`QmdWorkspaceView`.

`QmdExplorerEntry` contains explicit directories rather than deriving folders
only from QMD leaf paths. Empty Draft directories therefore remain visible and
New Folder has a representable result. Local indexing may retain the existing
two-second coalesced refresh initially; SSH indexing is event-driven through
`QLabRepository.subscribeQmd` and uses full refresh only for initial load,
watcher overflow, or cursor gaps.

The local/remote repository boundary stays below this component:

```text
LocalQLabRepository or SshQLabRepository
                -> QmdExplorerEntry[]
                -> QmdWorkspaceView
                -> QmdFileExplorer
```

## Interaction model

- Click a directory row outside its twisty: focus and select the directory, then
  toggle it. Clicking only the twisty toggles and focuses the directory without
  replacing the current selection.
- Click a file: focus, select, and activate it through the existing `open(path)`
  flow. `Cmd/Ctrl+click` toggles membership without activation; `Shift+click`
  extends the visible-row range from the selection anchor.
- `Up` / `Down`: move focus and single selection through visible rows without
  activating a file. `Cmd/Ctrl` moves focus only; `Shift` extends selection.
- `Home` / `End`: move focus and single selection to the first or last visible
  row; modifier behavior matches Up/Down.
- `PageUp` / `PageDown`: move focus by one viewport.
- `Left`: collapse a directory; if already collapsed or on a file, focus its
  parent.
- `Right`: expand a directory; if already expanded, focus its first visible
  child.
- `Enter`: select/open the focused file or toggle the focused directory.
- `Space`: open a file while retaining tree focus; toggle a directory.
- `Cmd/Ctrl+A`: select every currently visible row. Multi-selection file
  mutations remain out of scope; the selection model still matches VS Code.
- Typing printable characters performs case-insensitive visible-row type-ahead;
  the buffer resets after one second and repeated prefixes cycle matches.
- `Cmd/Ctrl+P`: retains the existing QMD Quick Open behavior.
- Collapse All closes all descendant directories while leaving the two semantic
  roots visible. If focus becomes hidden, it moves to the nearest visible root;
  hidden selected paths remain selected and reappear when expanded.
- Refresh delegates to the existing index refresh and preserves the old tree on
  a transient error.

New File and New Folder resolve their Draft parent from selection, never from
the active preview: one selected Draft directory uses itself; one selected Draft
file uses its parent; no selection uses the Draft root. Multiple selection or
any selected Knowledge row disables both create actions with an explanation.
Both callbacks are still capability-gated by the repository adapter.

Activation inserts a VS Code-style inline input row as the first child of the
resolved parent and expands that parent. New File requires a single-segment name
ending in `.qmd`; New Folder requires a single nonempty segment. The client
rejects NUL, `/`, `\`, `.`, and `..`, while the repository adapter remains the
authority for platform rules, conflicts, and path safety. Enter submits
`{ parentPath, name }`; before submission, Escape or blur cancels without
mutation. While a request is pending the input is read-only and
`aria-busy="true"`. Success selects the
returned path and opens a file or leaves a folder selected; duplicate, invalid,
disconnect, or other typed failure keeps the input in place, shows an inline
`role="alert"`, and returns focus for correction. A target-epoch change always
cancels the input and ignores its late result.

Only `availability="ready"` may activate a new file or invoke create callbacks;
all other states mask create capabilities to false while preserving cached rows
as selectable orientation:

- `connecting`: expose `aria-busy="true"` on the tree and a polite live status,
  disable repeat Refresh, and coalesce any programmatic refresh request into the
  in-flight connection;
- `disconnected`: show the target-specific disconnect message and label Refresh
  **Reconnect**; activation and mutation remain blocked;
- `error`: show the sanitized `availabilityMessage` as `role="alert"` and label
  Refresh **Retry**; one retry replaces, rather than races, the failed request;
- `ready`: clear the availability announcement, permit activation, and enable
  only the adapter-advertised Draft capabilities. A normal index refresh keeps
  the tree usable, sets `aria-busy`, and coalesces duplicate Refresh actions.

Reconnect/Retry asks the target controller to revalidate repository identity and
then reindex. It never silently rebinds the same path to a local repository.

General VS Code mutation keys such as F2, Delete, copy/paste, and drag/drop are
not registered until the corresponding safe repository operations exist.

## Accessibility

- The tree container uses `role="tree"` and accessible name `QMD Files
  Explorer`.
- Every visible row uses `role="treeitem"`.
- Rows expose correct `aria-level`, `aria-setsize`, and `aria-posinset` based on
  visible siblings.
- Directories expose `aria-expanded`.
- Every selected row exposes `aria-selected="true"`; other selectable rows
  expose false.
- Treeitems use a roving `tabindex` in Gecko: the focused row is `0`, every
  other row is `-1`, and DOM focus moves with the keyboard. This is the one tree
  tab stop; `aria-activedescendant` is not mixed into the implementation.
- Pending-change decorations have the label `AI changes waiting for review` and
  are not conveyed by color alone.
- Disabled title actions remain focusable, expose `aria-disabled="true"`, block
  activation, and reference a reason with `aria-describedby`.
- The sash is a focusable `role="separator"` with
  `aria-orientation="vertical"`, `aria-valuemin`, `aria-valuemax`, and
  `aria-valuenow`. Left/Right adjust by 8px, Shift+Left/Right by 32px, Home/End
  use the current minimum/maximum, and Escape restores the width at drag/focus
  entry. Toggle Explorer remains the non-pointer hide/restore path.
- Compact-folder path compression is not introduced in this slice, avoiding
  its additional screen-reader level semantics.

## Repository Target behavior

Explorer state is target-scoped:

```text
targetId
  -> targetEpoch / index cursor / availability
  -> width / userHidden
  -> expanded relative paths
  -> active / selected / focused relative paths
  -> last useful index
```

The atomic target-switch transaction validates the new target before replacing
Explorer state. A successful switch publishes one immutable snapshot containing
the new `targetId`, `targetEpoch`, entries, focus, selection, expansion, width,
and availability; it never renders an unowned empty tree between targets. A
failed validation retains the complete old Explorer. Any refresh, watch event,
or callback tagged with an older epoch is discarded. Remote status belongs to
the Workbench target/status surface, following VS Code Remote-SSH's separation
between Remote Status and File Explorer.

On SSH disconnect, the last tree may remain visible for orientation but is
marked unavailable at the workspace status level; all mutations are disabled.
It must never be relabeled as local or rebound to a local directory with the
same path string.

## Error handling

- **Transient index error:** keep the last useful rows and report the error in
  the QMD status strip.
- **Active file removed:** clear the preview through the existing active-document
  callback and remove deleted paths from selection; do not select a different
  file silently.
- **Expanded directory removed:** drop only that directory and descendant paths
  from expansion state.
- **Persisted width outside limits:** clamp to `max(170px, min(saved, 40%))`
  while the body is at least 425px; from 411px–424px use 170px; below 411px
  auto-hide. Do not overwrite the saved value until the user resizes.
- **Sash drag interrupted:** retain the last committed width.
- **Target switch during refresh:** discard results tagged with the old
  `(targetId, targetEpoch)`.
- **Remote disconnect:** keep navigation context read-only and disable all
  mutation actions until repository identity is revalidated.

## Testing strategy

### Component behavior

- Render a real `QmdFileExplorer` from literal invented entries and assert the
  visible order, extensionless labels, explicit empty directory,
  directory-first sorting, and root order.
- Exercise clicks and keyboard input against the real DOM component, not a
  source-text assertion or a mocked tree.
- Assert separate active file, focused row, and multi-selection, including
  inactive selection after the tree loses focus.
- Assert pending decoration propagation and its accessible label.
- Assert Collapse All, Refresh, hide/restore, sash width clamping, and persisted
  width callbacks.
- Assert create-parent resolution for one Draft directory, one Draft file, no
  selection, multiple selection, and Knowledge selection.
- Exercise inline file/folder name entry, validation, Enter, Escape, blur,
  duplicate-name error, async failure focus restoration, success selection/open,
  and cancellation of a late result after target switch.
- Exercise ready, connecting, disconnected, and error with a cached tree; prove
  only ready can activate/create, status and ARIA semantics are correct, and
  Refresh coalesces, reconnects, or retries without concurrent requests.
- Resize across 411px and prove `autoHidden` never changes persisted
  `userHidden`; exercise narrow overlay dismissal, wide restoration,
  `Cmd/Ctrl+B`, Explorer Hide, and the conditional QMD toolbar Show action.

### Trust and target isolation

- Select Knowledge and prove create actions are disabled and Draft controls
  remain hidden.
- Select Draft with a capable adapter and prove only Draft create callbacks can
  be reached.
- Switch target A -> B while A's refresh resolves late and prove no A entry
  appears in B's tree.
- Use identical relative paths on local and SSH targets and prove expansion,
  selection, and width remain target-scoped.

### Accessibility

- Assert role, accessible name, levels, positions, set sizes, expanded, and
  selected state on a nested fixture.
- Exercise keyboard focus movement, expansion, opening, boundary behavior, and
  focus retention, including Home/End, type-ahead, range selection, Select All,
  and Collapse All focus fallback.
- Verify pending and disabled states without relying on color.
- Exercise the sash as a keyboard separator and assert value, min, max, step,
  large-step, cancel, and hide/restore behavior.

### Visual regression

Replace the current empty file-column browser fixture with a representative
tree containing:

- both semantic roots;
- expanded and collapsed directories;
- a selected Knowledge file;
- a pending Draft file and ancestor decorations;
- Explorer title actions;
- a visible sash and preview pane.

The committed 1440x900/DPR-1 PNG is the immutable approved design reference.
Capture the real component at 1440x900 and 760x720 in the existing Chromium
layout harness, and run the same structural fixture in Zotero's Gecko runtime.
Geometry assertions allow at most 1 CSS pixel for the 35px header, 22px rows,
8px indentation, 16px icon/twisty boxes, 240px initial width, and sash position.
Text antialiasing is excluded from exact pixel assertions. After the first real
component capture is manually compared with the approved PNG, commit that
same-harness image as the regression golden and enforce a 0.5% maximum differing
pixel ratio. A dark-mode fixture verifies token mapping but does not require a
second design direction.

## Acceptance criteria

1. At the approved viewport, the file column matches the approved Superdesign
   Explorer draft and committed PNG in structure, density, hierarchy, action
   placement, and state visuals within the stated geometry tolerances.
2. Rows are 22px high with 8px depth increments and Codicon twisties.
3. Knowledge and Draft remain distinct top-level directories with unchanged
   trust and publication semantics.
4. Local and SSH repositories use the same component and never share
   target-scoped Explorer state.
5. The visible 18px collapse strip is gone; resizing and hide/restore remain
   accessible.
6. Keyboard navigation, multi-selection, type-ahead, tree ARIA, and keyboard
   sash resizing work against the real component.
7. Current preview, Visual Edit, compliance, review, compare, Keep, Quick Open,
   and index-refresh tests remain green.
8. No runtime assets are fetched from a CDN, and no trusted Knowledge write path
   is added.
9. Empty Draft directories are representable, disconnected remote entries
   cannot activate or mutate content, and late old-target events cannot replace
   the current tree.

## Delivery relationship

This feature has its own implementation plan. Delivery order is:

1. land the minimal local Repository Target ID/epoch and fix atomic switching,
   so a root change cannot leave Explorer, terminal, and Codex on different
   roots;
2. land the local `QmdFileExplorer` extraction and approved UI;
3. introduce the Repository Target model and SSH Chat MVP;
4. connect `SshQLabRepository` entries and target-scoped Explorer persistence;
5. enable capability-gated remote Draft creation only after repository broker
   validation exists.

## Official external references

- [Explorer view and title actions](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/files/browser/views/explorerView.ts)
- [Explorer renderer and 22px delegate](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/files/browser/views/explorerViewer.ts)
- [Explorer row CSS](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/files/browser/media/explorerviewlet.css)
- [Tree twisty CSS](https://github.com/microsoft/vscode/blob/main/src/vs/base/browser/ui/tree/media/tree.css)
- [Tree indentation and ARIA](https://github.com/microsoft/vscode/blob/main/src/vs/base/browser/ui/tree/abstractTree.ts)
- [List selection and focus](https://github.com/microsoft/vscode/blob/main/src/vs/base/browser/ui/list/listWidget.ts)
- [VS Code list/tree theme colors](https://code.visualstudio.com/api/references/theme-color#lists-and-trees)
- [VS Code file icon themes](https://code.visualstudio.com/docs/configure/themes#_file-icon-themes)
- [Remote-SSH status separation](https://code.visualstudio.com/docs/remote/ssh-tutorial#_remote-ssh)
