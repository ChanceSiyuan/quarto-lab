# QLab Workbench Design System

## Product and surface

QLab Workbench is a native Zotero document tab joining local or SSH-hosted
Research Loop repositories to Codex. The target design is its QMD Workspace:
chat remains in the left split pane; the right pane contains a compact toolbar,
status strip, trust-aware file explorer, and Quarto preview or Visual Edit.

## Existing Workbench chrome

- Use the Zotero/Apple system font stack for Workbench chrome.
- Respect the plugin's light/dark tokens from
  `integrations/zotero/src/styles.css:1-53`.
- Workbench tabs fill their host with square edges, no floating-card shadow.
- Controls are compact desktop controls, not web dashboard cards.
- The QMD toolbar is 40px high; preview/editor content consumes all remaining
  height.

## Trust semantics

- `Trusted Knowledge` and `Draft` are top-level semantic roots, not cosmetic
  folders.
- Knowledge is published/read-only and associated with validation.
- Draft is unpublished and may show pending AI changes, review, compare, Keep,
  and Visual Edit actions.
- Do not merge the roots, relabel Knowledge as an ordinary folder, or use one
  undifferentiated status color for both.

## File explorer direction

The approved redesign direction is a faithful VS Code Explorer interaction and
visual model inside QLab's right pane. It must preserve QLab trust semantics
while matching VS Code Explorer density, hierarchy, twisties, file/folder
icons, hover, active selection, keyboard focus, title/actions, and scrollbar.
It follows the active light/dark theme rather than forcing one theme.

The Explorer owns the left column; the rest of Workbench keeps its existing
visual language. Do not introduce cards, pills, gradients, decorative shadows,
oversized headings, or mobile navigation patterns.

## VS Code Explorer fidelity contract

The following values come from the current `microsoft/vscode` implementation
and are hard constraints for the Explorer branch:

- Render one `EXPLORER` title area with the standard actions in this order:
  New File, New Folder, Refresh Explorer, Collapse All. Use the corresponding
  Codicons `new-file`, `new-folder`, `refresh`, and `collapse-all`; overflow
  belongs under `…`.
- Treat `Trusted Knowledge` and `Draft` as the two visible top-level directories
  of one repository, not as separate cards or colored accordion headers.
- Tree rows are exactly 22px high with 22px line-height.
- Default tree indent is 8px per depth. The twisty slot is 16px wide with a
  10px Codicon, 6px right padding, and 3px horizontal translation. Expanded
  uses the down chevron; collapsed rotates it to the right.
- Use a VS Code File Icon Theme abstraction. The canvas uses the built-in Seti
  default: file resources receive the theme icon; folder rows do not invent a
  hard-coded folder glyph when the active theme omits one. Product actions and
  twisties use Codicons.
- Keep keyboard focus and selection as separate states. Active selection,
  inactive selection, keyboard focus, and hover follow `list.*` theme-token
  precedence; hover never overrides selected or focused rows. Focus/selection
  outlines are 1px with -1px offset.
- The widget is `role="tree"`; rows are `role="treeitem"` with `aria-level`,
  `aria-setsize`, `aria-posinset`, `aria-selected`, and directory
  `aria-expanded`.
- Arrow keys, Home/End, PageUp/PageDown, Enter, Space, type-ahead, range
  selection, and Cmd/Ctrl+A follow VS Code tree behavior. Multi-selection is
  visible even though batch mutations remain out of scope. Knowledge remains
  read-only even though navigation is identical.
- Do not place Local/SSH pills inside Explorer rows. Remote connection state is
  a separate Workbench target/status surface; the same Explorer renders either
  local or remote repository data.

For the light canvas, use VS Code Light Modern tokens: sidebar background
`#F8F8F8`, sidebar border `#E5E5E5`, foreground `#3B3B3B`, active selection
background `#E8E8E8`, active selection foreground `#000000`, hover background
`#F2F2F2`, and focus outline `#005FB8`. The production component maps these to
theme variables and supports the corresponding dark theme.

QLab container adaptation: start the Explorer at 240px wide and replace the
current visible 18px `‹` collapse strip with a VS Code-style resizable sash.
Width is persisted per Repository Target. Quick Open and the surrounding QMD
toolbar remain available, but are outside the Explorer visual component.

The approved reference is committed at
`.superdesign/references/qlab-vscode-explorer-approved-light-1440x900.png`
(1440x900 CSS pixels, DPR 1, Light Modern; SHA-256
`989f92f65b27634f10df36013d0b677183e8ea5452cbc5d9f9004c69843324f5`).

## Content fixture for design

Use a representative, invented tree only; do not read real Draft content:

```text
Trusted Knowledge
  QEC
    decoding
      belief-propagation
      neural-decoder
    index
  index
Draft                       pending AI change inherited from a child
  reading-notes
    recent-paper            pending AI change
  experiments
    decoder-benchmark
  scratch
```

The repository paths end in `.qmd`, but current tree rows display the basename
without that extension. Show `belief-propagation` selected. Both roots begin
expanded; one nested folder is expanded and one is collapsed. A pending
decoration appears on the Draft file and bubbles through `reading-notes` to the
`Draft` root.

## Fidelity constraints

- Use only the fonts, colors, spacing, and component styles defined here or in
  the supplied source context.
- Do not introduce another application shell or a browser-style website.
- The artifact must read as a native desktop code editor embedded in Zotero.
- The baseline draft reproduces the current UI exactly; the redesign is created
  only as a branch from that baseline.
