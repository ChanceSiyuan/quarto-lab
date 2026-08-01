# Routes and UI Surfaces

## Next.js App Router

| Route | Entry | Layout | Summary |
|---|---|---|---|
| `/` | `src/app/page.tsx` | `src/app/layout.tsx` | Problem Console |
| `/problems/[id]` | `src/app/problems/[id]/page.tsx` | RootLayout | Problem qualification/research detail |
| `/problems/[id]/autoresearch` | `src/app/problems/[id]/autoresearch/page.tsx` | RootLayout | Campaign attempt ledger |
| `/problems/[id]/attempts/[attemptId]` | `src/app/problems/[id]/attempts/[attemptId]/page.tsx` | RootLayout | Attempt dossier |
| `/qec-portfolio` | `src/app/qec-portfolio/page.tsx` | RootLayout | QEC comparison portfolio |
| `/knowledge/` | generated Quarto output | separate Quarto layout | Trusted knowledge site |

There is no explicit router configuration beyond the App Router file tree.

## Zotero surfaces

QLab Workbench has no URL router. `ZoteroChatPlugin` constructs these surfaces:

- native Workbench tab;
- standalone Workbench XUL window;
- Reader assistant sidebar;
- compact floating chat;
- conversation history rail;
- Main Site embedded browser;
- QMD Workspace;
- terminal drawer.

The QMD Workspace is reached from the Main Site `Source` action, then switches
between `Trusted Knowledge` and `Draft` through its file explorer or Quick
Open. Its production entry is `plugin.ts:1340-1402`, and its complete rendered
DOM is built by `qmd-workspace.ts:154-276`.
