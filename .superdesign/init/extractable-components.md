# Extractable Components

The current QLab UI uses large imperative view classes rather than isolated
layout components. No existing layout can be safely extracted to Superdesign
without inventing an API, so component extraction is skipped for the baseline
design. The following are implementation refactoring candidates, not existing
DraftComponents.

## WorkbenchShell

- Source: `integrations/zotero/src/sidebar.ts`, assembled by `src/plugin.ts`
- Category: layout
- Description: Workbench chat, optional history, resizable right pane, terminal.
- Extractable props: `historyOpen`, `rightPane`, `splitRatio`, `terminalOpen`
- Hardcoded: Zotero tab host, CSS class names, shell iconography.

## QmdWorkspaceShell

- Source: `integrations/zotero/src/qmd-workspace.ts:154-276`
- Category: layout
- Description: Toolbar, status, trust-aware file explorer, preview/editor pane.
- Extractable props: `activePath`, `activeTree`, `fileColumnCollapsed`, `mode`
- Hardcoded: Knowledge/Draft semantics and toolbar actions.

## QmdFileExplorer

- Source: `integrations/zotero/src/qmd-workspace.ts:963-1013`
- Category: layout
- Description: Nested Knowledge/Draft QMD tree with active and pending states.
- Extractable props: `entries`, `expandedPaths`, `activeFilePath`,
  `selectedPaths`, `focusedPath`, `width`, `capabilities`
- Hardcoded: root order, trust labels, QMD-only behavior, VS Code-compatible icons.

## QmdTreeNode

- Source: `integrations/zotero/src/qmd-workspace.ts:971-1013`
- Category: basic
- Description: Directory/file row with twisty, icon, label, and status decoration.
- Extractable props: `kind`, `depth`, `expanded`, `active`, `pending`, `label`
- Hardcoded: row DOM and ARIA behavior once the Explorer design is approved.

## QmdToolbar

- Source: `integrations/zotero/src/qmd-workspace.ts:166-237`
- Category: basic
- Description: Preview/editor command toolbar.
- Extractable props: Draft-only action visibility and state.
- Hardcoded: command identities and accessible labels.
