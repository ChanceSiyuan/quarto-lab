# Dashboard ↔ Knowledge Entry Point

Date: 2026-07-28

Status: approved design

## Context

Two surfaces already exist and are deliberately disjoint:

- `/` — the Problem Console, a Next.js/vinext page rendered from
  `.generated/problem-index.json`, showing problems, attempts, and lifecycle
  status. This is where autoresearch progress is visible.
- `/knowledge/` — a static Quarto site rendered from `knowledge/**/*.qmd` into
  gitignored `public/knowledge/`, published inside the same Sites artifact.

They share no import, module, or route. The knowledge site is reached only by
typing its URL, so a user watching research progress has no way into the
knowledge the loop produces, and a reader of a knowledge page has no way back.

This design adds navigation in both directions. Nothing else.

## Goals

- A user on the dashboard can reach the trusted knowledge base in one click.
- A user on any knowledge page can return to the dashboard in one click.
- The link works in local development, in the Sites deployment, and under a
  base path, without host configuration.
- Our code stays out of the files upstream actively develops, so console
  refactors and this feature do not collide.

## Non-goals

- No knowledge statistics, counts, or recent-page list on the dashboard. The
  dashboard does not learn what is in the knowledge base; it only points at it.
- No change to Problem Console behavior, filters, or data.
- No second publish surface. `/knowledge/` remains part of the Sites artifact.

## Architecture

Two independent edges, each owned by the side that renders it.

### Dashboard → knowledge

A new component `app/knowledge-link.tsx`, owned by this feature, renders the
entry point. Upstream's `app/problem-console.tsx` gains exactly one import and
one `<KnowledgeLink />` element inside its existing `console-topbar`, beside the
brand, mode indicator, and index health blocks.

The seam is deliberate. `problem-console.tsx` is the file upstream changes most;
confining our contribution to one import and one element means their refactors
do not conflict with our markup, and our changes do not complicate their diffs.
Styling lives in the new component's own contiguous block appended to
`app/globals.css`, for the same reason.

The link is a plain anchor to `/knowledge/` in the application source. It leaves
the app router for a static site, which is what a full page navigation is for;
no client-side routing is involved. The GitHub Pages showcase is the one
exception at artifact time: `scripts/build-pages-showcase.mjs` rewrites the
snapshot link to the repository base path, `/research-loop/knowledge/`, and
copies the rendered knowledge site into `out/knowledge/`.

### Knowledge → dashboard

`lib/knowledge/quarto.ts` holds `FIXED_BASE_CONFIG`, the fixed safe schema for
the Quarto project. It gains a `website.navbar` block, and the committed
`knowledge/_quarto.yml` gains the identical block.

The generated project configuration is **built from that constant**, not copied
from the committed file:

```ts
website: { ...FIXED_BASE_CONFIG.website, sidebar: { contents: sidebarContents(graph) } }
```

The committed `_quarto.yml` is parsed, compared with the constant for exact
equality, and then discarded. This has a useful consequence: the navbar cannot
be controlled by a page or by an edited config file. Changing where it points
requires editing TypeScript, which goes through code review. No runtime
validation of navbar hrefs is needed, because there is no runtime input.

The two copies must move in lockstep. If they drift, the existing exact-equality
check fails with its existing actionable diagnostic. That is the guard, and it
already exists.

## The href, and why it is `../`

Quarto rewrites navbar hrefs relative to each rendered page. Measured against
Quarto 1.9.38 with `site-path: /knowledge/`:

| Configured `href` | Root page | Nested page | Result |
|---|---|---|---|
| `/` | `./` | — | Points at the knowledge root. Wrong. |
| `/index.html` | `./index.html` | `../index.html` | Points at the knowledge root. Wrong. |
| `http://host/x` | unchanged | unchanged | Correct but requires a hardcoded host. |
| `../` | `./../` | `../../` | Resolves to the site root from every page. |

`../` is the answer. Quarto adjusts it for page depth, so a category page at
`/knowledge/categories/theory/` receives `../../../`, which resolves to `/` just
as the root page's `./../` does. Because it stays relative, it is correct on
`127.0.0.1:4173`, on the Sites domain, and under a base path such as GitHub
Pages, where an absolute URL would be wrong.

The root-relative spellings are the trap: they look correct, render without
error, and silently return the reader to the page they were already on.

This depends on one invariant: `site-path: /knowledge/` keeps the published site
exactly one level below the dashboard root. That invariant is already part of
the fixed schema, and the integration test asserts the rendered hrefs rather
than the configured one, so a future Quarto that changes its rewriting rules
fails the build instead of shipping a dead link.

## Development flow

`make dev` runs the problem-index watcher and serves `public/` — but nothing
builds `public/knowledge/`, so on a fresh clone the new link would 404.

The Makefile already expresses "make this file if it is missing or stale" with
the `node_modules/.package-lock.json: package-lock.json` rule. This follows it:
`public/knowledge/index.html` becomes a file target whose prerequisites are the
knowledge sources, and `dev` depends on it. The site is built once, skipped
thereafter, and rebuilt when `knowledge/` changes. No new script, and dev and
production stay consistent.

## Error handling

- An invalid knowledge tree fails `make dev` loudly rather than serving a stale
  or absent site. This matches the existing rule that validation failure aborts
  a build.
- Drift between `FIXED_BASE_CONFIG` and the committed `_quarto.yml` fails the
  existing exact-equality check.
- The link itself is a static anchor with no runtime failure mode. If the site
  is unbuilt in production, the Worker's `/knowledge` fallback finds no asset
  and falls through to the app router, which 404s — unchanged from today.

## Testing

- **Unit** (`tests/knowledge/quarto-project.test.ts`): the generated
  configuration carries the navbar; a committed base config that omits or alters
  it is rejected.
- **Integration** (`tests/knowledge/quarto-build.integration.test.ts`, real
  Quarto): the rendered navbar href is depth-correct at the root page, a nested
  topic page, and a category page. Asserting the rendered output rather than the
  configuration is what catches a Quarto upgrade that changes rewriting.
- **Browser** (Playwright): one focused round trip — `/` → click Knowledge →
  `/knowledge/` → click the navbar entry → `/`.

## Dependencies

This design assumes the merge of `origin/main` has landed, because it edits
`app/problem-console.tsx`, which arrives with that merge.
