# Quarto Knowledge System for Research Loop

Date: 2026-07-27

Status: approved design

## Context

`research-loop` is currently a small Next.js/vinext control-dashboard prototype
deployed through OpenAI Sites and Cloudflare assets. Its `/` page, visual design,
localStorage-backed demo interactions, Worker entry point, and Sites packaging
must remain functional.

The quantum harness contains a large hidden `.knowledge/` corpus and a collection
of workflow skills, but its knowledge cards are optimized for agent dispatch, not
for a human-maintained body of learned knowledge. This design moves the knowledge
workflow into `research-loop` as a Quarto-native system that humans and agents read
from the same `.qmd` sources.

The destination repository is `/home/chance/research-loop`. The quantum harness is
the migration source only.

## Goals

- Make `knowledge/` a visible, human-readable, Quarto-native knowledge base.
- Keep `knowledge/**/*.qmd` as the only source of truth for trusted knowledge.
- Organize trusted knowledge by research object for coherent human reading.
- Give agents deterministic, auditable access to the same topic graph.
- Keep unfinished work physically outside the trusted knowledge tree.
- Preserve external papers separately from the user's learned knowledge.
- Preserve the existing Research Loop dashboard and Sites deployment shape.
- Import every old non-literature card without implicitly certifying it.

## Non-goals

- Building the real Discover → Verify → Solve → Publish backend in this phase.
- Adding D1, R2, queues, schedulers, leases, or an autonomous agent runner.
- Replacing the existing dashboard with Quarto.
- Publishing drafts or literature source material.
- Executing numerical code while rendering the website.
- Bulk-certifying existing harness cards as user-approved knowledge.
- Maintaining a compatibility `.knowledge` symlink or a generated Markdown mirror.

## Trust model

The physical directory is the trust boundary:

- `knowledge/` contains only notes the user has learned, reviewed, and chosen to
  promote.
- `drafts/` contains unfinished, uncertain, imported, or AI-authored notes.
- `literature/` contains external source material and bibliographic evidence.

There are no draft, confidence, trust, or review-status labels. A note becomes
trusted when the user chooses its location in `knowledge/` and merges the reviewed
Git change. Git history is the audit record; no database copies the note body.

## Repository shape

```text
research-loop/
├── app/                              # existing dashboard, preserved
├── worker/                           # existing vinext Worker, preserved
├── knowledge/
│   ├── _quarto.yml
│   ├── index.qmd
│   ├── quantum-magnetism/
│   │   ├── index.qmd
│   │   └── transverse-field-ising/
│   │       ├── index.qmd
│   │       ├── criticality-proof.qmd
│   │       └── triangular-sse-results.qmd
│   └── software/
│       ├── index.qmd
│       └── quspin/
│           ├── index.qmd
│           ├── hamiltonian-api.qmd
│           └── verified-examples.qmd
├── drafts/
│   ├── _quarto.yml                   # preview-only project
│   └── imported-quantum-harness/     # lossless migration candidates
├── literature/
│   ├── ref.bib
│   └── <method>/
│       ├── INDEX.md
│       ├── .raw/<citekey>/
│       │   ├── source.tar.gz
│       │   ├── source/
│       │   ├── paper.pdf
│       │   └── manifest.json
│       └── .figures/<citekey>/
├── lib/knowledge/
├── scripts/
├── skills/
├── AGENTS.md
├── CLAUDE.md                         # points Claude Code to AGENTS.md
├── .claude/skills -> ../skills       # local-skill discovery
└── public/knowledge/                 # generated, gitignored
```

The example research topics illustrate shape only. The initial implementation
must not invent trusted subject-matter notes merely to populate the site.

## Topic and page model

### Physical organization

The physical tree is organized by research object, not by document type. Topic
depth is flexible. Every topic directory has an `index.qmd`; a simple topic may
contain only that index, while a complex topic may contain many sibling notes and
nested topics.

Software repositories are first-class research objects. Generic QuSpin knowledge,
for example, lives under `knowledge/software/quspin/`; physics topics link to it
instead of copying API facts.

Each fact or explanation has one canonical home. Other topics use cross-links.

### Curated index contract

`index.qmd` is authored by the user and is the authoritative human-and-agent
navigation interface. It is never replaced by a generated file.

An index has two machine-readable Markdown sections:

```markdown
## Reading map

- [Criticality](criticality.qmd)
- [Triangular-lattice results](triangular-sse-results.qmd)
- [Honeycomb lattice](honeycomb/index.qmd)

## Related topics

- [QuSpin](../../software/quspin/index.qmd)
```

- `Reading map` defines containment and reading order.
- `Related topics` defines cross-topic relationships without changing ownership.
- Prose outside these sections is unconstrained.
- Every direct content page and child topic must be reachable from its parent's
  reading map.

Generated sidebars are derived from this contract. They are not independently
edited.

### Content categories

Every non-index knowledge page has exactly one category:

- `theory`: definitions and assumptions needed for strict derivations, together
  with rigorous propositions, theorems, proofs, or analytic derivations.
- `experiment`: experimental proposals, platforms, protocols, observables,
  controls, error considerations, and feasibility.
- `codes`: repository/API usage, implementation knowledge, verified examples,
  and reproducible numerical results.

`index.qmd` is navigation and has no category. A mixed draft is not automatically
split during promotion; the user may request splitting separately.

### Minimal frontmatter

```yaml
---
title: QuSpin Hamiltonian API
description: Verified Hamiltonian construction interfaces and their boundaries.
categories: [codes]
aliases: [quspin hamiltonian]
---
```

- Every page, including `index.qmd`, requires `title` and `description`.
- Every non-index content page additionally requires exactly one allowed
  `categories` entry; `index.qmd` must omit it.
- `aliases` is optional and supports names, abbreviations, and old terminology.
- Git supplies authorship and modification history.
- Citations and evidence live in the body, not duplicated metadata.

### Evidence contracts

Page layout is free-form, but promoted knowledge should expose the evidence needed
for its category:

- `theory`: objects, assumptions, claim, derivation/proof, applicable boundary,
  and sources.
- `experiment`: objective, platform, protocol, observables, controls, uncertainty,
  and feasibility.
- `codes`: repository and fixed version, API inputs/outputs, runnable entry or
  example, parameters, result, and verification link.

Numerical conclusions belong to `codes` and link to scripts, data, parameters, and
a fixed commit or run. Quarto rendering never executes these programs.

## KnowledgeGraph deep module

One TypeScript module owns all knowledge semantics:

```text
lib/knowledge/
├── parser.ts       # frontmatter, Reading map, local links
├── graph.ts        # topic/page nodes and containment/reference edges
├── validate.ts     # invariants and diagnostics
├── resolve.ts      # deterministic ranking and reading bundles
└── index.ts        # small public interface
```

Its public surface is intentionally small:

```text
loadKnowledge()
validateKnowledge()
resolveKnowledge(query)
buildKnowledgeSite()
```

CLI, Quarto build hooks, Make targets, and agent skills are thin adapters. This
prevents navigation, website, and agent retrieval rules from drifting apart.

### Validation invariants

- Only `knowledge/**/*.qmd` enters the trusted graph.
- Every topic directory has `index.qmd`.
- Every content page has valid minimal frontmatter and one allowed category.
- Every direct child is present in its parent's reading map.
- Local links and citations resolve.
- A physical child has exactly one containing parent.
- Related-topic links may form cycles; containment edges may not.
- Trusted QMD cannot contain executable `<script>` tags, inline event handlers,
  or asset paths that escape the repository/topic boundary.

### Deterministic resolver

The resolver does not use embeddings in the first version. It ranks exact title
and alias matches first, followed by description and body-term matches. It returns:

1. the root-to-topic chain of `index.qmd` files;
2. the matched content pages in deterministic order; and
3. explicit alternatives when a query is ambiguous.

It never silently chooses between equal research objects. Drafts and literature
are excluded. A research/source-audit workflow may separately opt into literature.

An optional derived snapshot/cache may accelerate queries, but it is gitignored,
rebuildable from QMD, and never a second content authority.

## Agent integration

The repository gains an `AGENTS.md` and three focused local skills:

- `read-knowledge`: resolve a research question and read the complete returned
  bundle—ancestor indexes, target index, and selected content pages—before
  answering.
- `review-draft`: review one note and recommend placement.
- `download-ref`: maintain the external literature corpus.

`AGENTS.md` makes `read-knowledge` a mandatory first step before an agent states a
research fact or interpretation that may be covered by the learned knowledge base.
If the resolver has no match, the agent says so; it may enter an explicitly named
external-research workflow, but it cannot silently treat `literature/` as learned
knowledge. Static tests verify that every research-answer entry skill routes through
the resolver command and that the skill requires reading every file in the bundle.

Prompt instructions cannot mathematically force every arbitrary language model to
comply. Reliability comes from an automatically discoverable skill, a single CLI,
an observable resolver call, and tests that ensure entry skills route through the
same interface.

`skills/` is the canonical committed source for these local skills.
`.claude/skills -> ../skills` exposes them to Claude Code, `CLAUDE.md` points to
the canonical `AGENTS.md`, and Codex reads `AGENTS.md` directly. Agent correctness
does not depend on an unconfigured skill directory being discovered implicitly.

## Draft workflow

`drafts/` has no category, naming, hierarchy, sidebar, catalog, or frontmatter
requirement. It may be flat, nested, or messy. Its separate Quarto project exists
only to preview a selected note locally and is never part of the production build.

Promotion is deliberately lightweight:

1. The user identifies one draft note.
2. The agent reviews natural-language grammar, factual errors or uncertain claims,
   and Quarto/Markdown formatting errors.
3. The agent recommends either an existing knowledge topic and filename, or a new
   topic directory with `index.qmd`. It also recommends the page's single category.
4. The user decides whether to correct the note, where it belongs, and whether to
   promote it.
5. Only after confirmation does the agent create or use a non-`main` branch,
   move/convert the note, add minimal frontmatter, update the curated index, and
   run mechanical validation.
6. The change is presented as a Git diff or PR; only the user's merge makes the
   note trusted knowledge. The agent never promotes a note by writing directly to
   `main`.

One draft remains one knowledge note by default. The agent does not automatically
split, comprehensively restructure, or rewrite it.

## Literature workflow

`literature/` remains organized by method, preserving the useful shape of the
quantum harness. `ref.bib` is the bibliographic source of truth, and method indexes
are derived from its `keywords` assignments.

PDF-to-Markdown output is not a reliable source for mathematical papers: current
harness renders contain replacement characters and displaced equations. Therefore:

- committed `rendered.md` full text is removed from the design;
- arXiv entries prefer the complete version-pinned source archive;
- the full TeX tree, custom macros, style files, and PDF live under `.raw/`;
- source images are normalized/copied under `.figures/`;
- `manifest.json` records arXiv version, URL, checksum, extraction result, and main
  TeX entry point;
- DOI/PDF-only sources may have an optional search extraction under `.raw/derived/`,
  but formulas must be checked against the PDF;
- downloaded LaTeX is never compiled automatically.

`.raw/` and `.figures/` remain local and gitignored. Downloads are on demand by
default. `make literature-sync` explicitly rebuilds all available sources.

Archives are downloaded to a temporary directory, bounded by size, checked for
path traversal, checksummed, and atomically installed. A failure leaves existing
sources untouched.

## Quarto and Sites integration

The existing application stays at `/`. The knowledge website is a static Quarto
subsite at `/knowledge/` within the same Sites deployment:

```text
Sites deployment
├── /             existing Next.js/vinext dashboard
└── /knowledge/   Quarto-rendered static HTML
```

Build flow:

1. load and validate KnowledgeGraph;
2. materialize a temporary Quarto project containing generated sidebar data and
   three category-view pages derived from the graph;
3. render that project to a temporary output directory with execution disabled;
4. atomically replace gitignored `public/knowledge/`;
5. run the existing vinext/Sites build.

Quarto supplies mathematics, citations, cross-references, search, and the three
category views. The generated `theory`, `experiment`, and `codes` pages contain
only graph-derived links and descriptions and live in the temporary project, never
the trusted source tree. Sidebar data is generated from the curated index graph.
Drafts and literature are excluded from the render project and Sites bundle.

The generated Quarto configuration sets `website.site-path: /knowledge/`, so
search, canonical links, navigation, and static resources stay under the dashboard
subpath. `npm run build` is the authoritative clean-checkout build and performs the
knowledge build before `vinext build`; `make build` delegates to it rather than
creating a second build path.

If integration testing shows that vinext/Cloudflare assets do not resolve nested
`index.html` paths, the Worker receives only a thin `/knowledge/*` static-asset
fallback. It must not become a second renderer.

The existing `.openai/hosting.json` project ID must be reused exactly. Current
Sites inspection returns `Project not found`, so production save/deploy is blocked
until access is restored or the binding is corrected. No replacement project may
be silently created.

## Migration

The current harness contains approximately 280 non-literature Markdown cards
(about 13 MB), plus 124 literature Markdown files (about 11 MB).

### Non-literature cards

- Copy models, methods, physics, software, solvable, and root reference cards
  byte-for-byte into `drafts/imported-quantum-harness/`.
- Preserve their relative paths and `.md` names. At least 72 files contain `.md`
  internal links, so bulk renaming would not be lossless.
- Record and verify checksums before and after copying.
- Commit a source-independent migration manifest under `docs/migrations/` with
  every imported relative path, byte size, and SHA-256 digest, so clean-checkout CI
  can verify the imported corpus without access to the harness repository.
- Convert an individual card to `.qmd` only when the user promotes it.

### Literature

- Copy `ref.bib` and preserve method identities.
- Regenerate method indexes from `ref.bib`.
- Do not copy lossy rendered full-text Markdown.
- Fetch arXiv source archives on demand; provide an explicit full sync command.

### Initial trusted site

The initial `knowledge/` contains only its curated navigation scaffolding. Tests use
fixtures outside the production knowledge tree; implementation must not fabricate
trusted scientific notes as demo content.

## Commands

The Makefile exposes stable human-facing entry points:

```text
make knowledge-check
make knowledge-resolve QUERY="triangular TFIM"
make knowledge-preview
make draft-preview FILE=drafts/example.qmd
make literature-fetch KEY=<citekey>
make literature-sync
make build
```

Equivalent package scripts may exist underneath, but documentation and skills use
the Make targets.

## Error handling

- Knowledge validation or Quarto failure aborts the production build.
- Rendering occurs in a temporary directory, so failure cannot leave a partially
  updated `public/knowledge/`.
- Resolver ambiguity is returned as data, never guessed away.
- Draft preview failure does not affect the trusted site.
- Literature download/extraction failure does not modify the previous local copy.
- Quarto website render has code execution disabled globally.

## Test strategy

### Unit tests

- frontmatter and category parsing;
- reading-map and related-topic parsing;
- orphan, duplicate-parent, bad-link, cycle, and path-escape diagnostics;
- deterministic alias/title/body ranking and ambiguity behavior;
- archive traversal and size-bound rejection.

### Integration tests

- a fixture topic tree produces the expected graph and sidebar model;
- Quarto renders fixture mathematics, citations, nested topics, and categories;
- `public/knowledge/` is replaced only after a successful render;
- drafts and literature do not appear in the production output;
- `/knowledge/` and nested topic routes are served by the bundled Worker/assets;
- a browser-level HTTP test exercises the real preview/static-assets pipeline
  rather than a fake `ASSETS.fetch` implementation that always returns 404;
- imported harness cards match source checksums;
- a fixture arXiv archive preserves TeX and extracts figures without producing
  rendered Markdown.
- `read-knowledge` returns and requires reading ancestor indexes, the target index,
  and selected content pages;
- `review-draft` reports language, factual, and formatting findings plus exactly
  one existing-topic or new-topic placement recommendation, without moving or
  splitting the note.

### Regression tests

- the existing `/` dashboard still renders its Research Loop content;
- stage advancement, reset, and localStorage behavior remain unchanged;
- a headless-browser regression test advances a stage, reloads to verify
  localStorage persistence, and resets the demo;
- the existing vinext/Sites package shape remains valid;
- obsolete starter-skeleton assertions are replaced with assertions for the real
  current dashboard rather than deleted without coverage.

## Acceptance criteria

- `/` retains the current dashboard behavior and appearance.
- `/knowledge/` is a searchable Quarto website with correct mathematics.
- no draft or literature source is publicly reachable.
- website, category views, sidebar, and agent resolver derive from one graph.
- invalid categories, orphan pages, dead links, unresolved citations, and unsafe
  markup fail validation with actionable file/line diagnostics.
- resolver results contain the complete bundle: ancestor indexes, target index,
  and selected content pages.
- research-answer Agent instructions require resolver use and expose a testable
  invocation; a no-match result cannot silently fall through to literature.
- draft review reports only language, factual, and format findings plus placement;
  it does not edit, move, split, or promote before user confirmation.
- promotion changes are made on a non-`main` branch and become trusted only after
  user review and merge.
- all old non-literature cards are preserved as untrusted draft candidates with
  matching checksums.
- literature fetch stores versioned TeX and figures and never commits lossy full
  text renders.
- generated site/cache artifacts are gitignored.
- local tests and production build pass before a Sites version is saved.
- production deploy uses the existing opaque Sites project ID after access is
  restored.

## Known implementation prerequisites

- Quarto 1.9.38 is available in the current environment.
- The current shell does not expose `node` or `npm`, while the project requires
  Node.js 22.13 or newer. The implementation phase must locate or install the
  repository's intended Node runtime before build verification.
- The current Sites project ID is not visible to the connected Sites identity.
  Local implementation can proceed, but production deployment cannot be claimed
  complete until that external access issue is resolved.
