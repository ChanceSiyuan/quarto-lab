# Page and Surface Dependency Trees

## QLab QMD Workspace (primary design target)

Entry: `integrations/zotero/src/plugin.ts:1340-1402`

Dependencies:

- `integrations/zotero/src/plugin.ts`
  - `integrations/zotero/src/sidebar.ts`
    - `integrations/zotero/src/qmd-workspace.ts`
      - `integrations/zotero/src/editor-tree.ts`
      - `integrations/zotero/src/qmd-index.ts`
      - `integrations/zotero/src/qmd-render.ts`
      - `integrations/zotero/src/qmd-visual-editor.ts`
        - `integrations/zotero/src/qmd-source-model.ts`
        - `integrations/zotero/src/markdown.ts`
  - `integrations/zotero/src/research-loop-site.ts`
  - `integrations/zotero/src/workbench-tab.ts`
- `integrations/zotero/src/styles.css`

Visual context for the file-explorer redesign is deliberately narrower:

- `qmd-workspace.ts:154-276` — real workspace DOM construction.
- `qmd-workspace.ts:904-1013` — refresh, file-column, and tree-node render.
- `styles.css:1-53` — adaptive plugin tokens.
- `styles.css:983-991` — native Workbench shell.
- `styles.css:1042-1303` — split pane, QMD toolbar/body/explorer.
- `styles.css:1378-1426` — Quick Open.
- full `editor-tree.ts` — trust-aware root descriptors.

Do not use `test/visual/surfaces.mjs` as ground truth: its file-column fixture is
empty and does not exercise nested, selected, or pending tree rows.

## `/` Problem Console

Entry: `src/app/page.tsx`

- `src/app/layout.tsx`
  - `src/app/globals.css`
- `src/app/page.tsx`
  - `src/app/problem-console.tsx`
    - `src/lib/problems/presentation.mjs`
  - generated problem index and presentation repositories

## `/problems/[id]`

Entry: `src/app/problems/[id]/page.tsx`

- `src/app/layout.tsx`
- `src/app/problems/[id]/page.tsx`
  - problem and research repositories
  - `src/app/problems/[id]/assessment-panel.tsx`
  - `src/app/problems/[id]/static-assessment-panel.tsx`
  - `src/app/problems/[id]/research-detail.module.css`

## `/problems/[id]/autoresearch`

Entry: `src/app/problems/[id]/autoresearch/page.tsx`

- `src/app/layout.tsx`
- `src/app/problems/[id]/autoresearch/page.tsx`
  - `src/app/problems/[id]/autoresearch-panel.tsx`
  - `src/app/problems/[id]/autoresearch-panel.module.css`

## `/qec-portfolio`

Entry: `src/app/qec-portfolio/page.tsx`

- `src/app/layout.tsx`
- `src/app/qec-portfolio/page.tsx`
  - `src/app/qec-portfolio/portfolio-panel.tsx`
  - `src/app/qec-portfolio/portfolio-panel.module.css`
