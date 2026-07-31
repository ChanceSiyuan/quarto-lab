# Shared UI Components

## Framework split

The repository contains two independent UI runtimes:

- The dashboard is Next.js 16 / React 19 with handwritten CSS.
- QLab Workbench is a Zotero 9 Gecko extension. It uses imperative TypeScript
  DOM construction, XUL hosts, and handwritten CSS; it has no React component
  library.

There is no shared `components/ui` directory and no third-party component
system such as shadcn, Radix, MUI, or Chakra. The QMD file explorer is a
page-specific portion of `QmdWorkspaceView`, so its actual render branch must
be passed directly to Superdesign rather than represented by an invented
generic component.

## ProblemStatus

- Source: `src/app/problem-console.tsx`
- Description: Dashboard status badge; the only small named React UI primitive.
- Props: `problemId`, `status`

```tsx
function ProblemStatus({ problemId, status }: { problemId: string; status: string }) {
  return (
    <span className={`status-badge status-${judgmentStatusTone(status, problemId)}`}>
      {judgmentStatusCopy(status, problemId)}
    </span>
  );
}
```

## QMD tree descriptors

- Source: `integrations/zotero/src/editor-tree.ts`
- Description: The shared semantic primitive that keeps trusted Knowledge and
  untrusted Draft visibly distinct in every file-list surface.

```ts
export type EditorTreeId = "knowledge" | "drafts";

export interface EditorTree {
  id: EditorTreeId;
  prefix: string;
  label: string;
  published: boolean;
  validateCommand: string | null;
  renderCommand: "knowledge-preview" | "draft-preview";
}

export const EDITOR_TREES: readonly EditorTree[] = [
  {
    id: "knowledge",
    prefix: "knowledge/",
    label: "Trusted Knowledge",
    published: true,
    validateCommand: "npm run knowledge:check",
    renderCommand: "knowledge-preview",
  },
  {
    id: "drafts",
    prefix: "drafts/",
    label: "Draft",
    published: false,
    validateCommand: null,
    renderCommand: "draft-preview",
  },
];
```

## QMD icon button pattern

- Source: `integrations/zotero/src/qmd-workspace.ts`
- Description: Compact toolbar action created with real DOM elements.

```ts
private iconButton(
  className: string,
  text: string,
  label: string,
  onClick: () => void,
): HTMLButtonElement {
  const button = this.button(className, text, onClick);
  button.title = label;
  button.setAttribute("aria-label", label);
  return button;
}
```

## CSS primitives

The dashboard exposes `status-badge`, `primary-action`, `state-action`,
`detail-shell`, `metric-strip`, and table-to-card responsive patterns through
`src/app/globals.css`. Workbench exposes `zc-icon-button`, compact selects,
thread tabs, context chips, review cards, and approval cards through
`integrations/zotero/src/styles.css`. These are CSS contracts rather than
separately exported components.
