# sci-brain 0.3 Knowledge-Base Migration Design

**Date:** 2026-06-06
**Status:** approved (design), pending implementation plan

## Goal

Complete this repository's migration from the pre-0.3 `sci-brain` survey layout to
the 0.3 project-knowledge-base layout.

After migration, the repository must use exactly one active literature store:

- project knowledge base at `.knowledge/`
- project bibliography at `ref.bib`

The old per-topic survey registries under `.claude/survey/` must be absorbed into the
project KB and then removed from the active workflow.

## Current State

The repository is in a half-migrated state.

Already on the 0.3 layout:

- `.knowledge/INDEX.md`
- `.knowledge/NOTES.md`
- `.knowledge/.raw/`
- `.knowledge/.figures/`
- rendered paper markdown files under `.knowledge/`
- project-level `ref.bib`

Still on the pre-0.3 layout:

- `.claude/survey/finite-code-transversal-gates/`
- `.claude/survey/finite-length-bb-lp-exact-distance-transversal-gates/`
- `.claude/survey/high-distance-codes-with-transversal-logical-operations/`
- `.claude/survey/qec-code-discovery-patterns/`

Each legacy survey directory contains `summary.md` and `references.bib`, which means
the repository currently has two competing locations for survey notes and bibliography
state.

## Scope

This migration covers:

- moving legacy survey notes into `.knowledge/NOTES.md`
- merging legacy `references.bib` entries into `ref.bib`
- normalizing imported note citations to the canonical keys in `ref.bib`
- updating repository documentation to describe only the 0.3 layout
- removing `.claude/survey/` after successful migration

## Non-Goals

- no rewrite of existing paper markdown in `.knowledge/`
- no automatic fetching of missing full-text papers from imported BibTeX entries
- no redesign of `.knowledge/INDEX.md` title/source-note wording unless required for
  correctness
- no changes to `zoo/`, `articles/`, Julia tooling, or unrelated skills

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Migration mode | **In-place merge** | The project KB already exists and should become the only source of truth. |
| KB truth source | **`.knowledge/` + `ref.bib`** | Matches `sci-brain` 0.3 upstream layout. |
| Legacy survey handling | **Import then delete** | Avoids leaving two active layouts in the repo. |
| Note merge style | **Append legacy surveys as clearly labeled imported sections** | Preserves original topic boundaries and minimizes semantic rewriting risk. |
| BibTeX conflict policy | **Keep existing `ref.bib` keys canonical** | Current project bibliography is already in use by the KB and articles. |
| Full-text backfill | **Do not do in this migration** | Keeps this change focused on layout convergence, not corpus expansion. |

## Target State

After migration:

- `.knowledge/` is the only active literature cache
- `ref.bib` is the only active bibliography namespace
- `.knowledge/NOTES.md` contains both the current project notes and imported content
  from the four legacy surveys
- imported note links point directly at files inside `.knowledge/`
- imported note citations resolve against `ref.bib`
- repository docs describe only the 0.3 project-KB workflow
- `.claude/survey/` no longer exists

## Merge Design

### Legacy Survey Notes

Each legacy `summary.md` is imported into `.knowledge/NOTES.md` as one separate
section.

Each imported section must:

- retain the original survey title and internal structure
- add a short provenance line identifying the source directory and original update
  date when present
- rewrite legacy relative links such as `../../../.knowledge/<paper>.md` to links that
  resolve from `.knowledge/NOTES.md`

This design preserves the original survey framing instead of redistributing sentences
throughout existing notes, which would introduce unnecessary editorial risk.

### Legacy Bibliography

Legacy `references.bib` entries are merged into `ref.bib` conservatively.

The canonical source of cite keys is the existing project `ref.bib`. Imported entries
are handled by the following precedence:

1. match existing entries by `doi`
2. otherwise match by `eprint` / arXiv identifier
3. otherwise match by normalized title
4. if no match exists, append the new entry to `ref.bib`

If an imported survey note cites a legacy key that maps to an already-existing paper
under a different canonical key, the note citation must be rewritten to the canonical
project key instead of duplicating the BibTeX record.

### Imported Content Boundaries

The migration treats legacy surveys as note content and bibliography content only.

It does not:

- fetch new PDFs
- render missing `.knowledge/*.md` files
- regenerate the project corpus from BibTeX alone

That work remains a separate follow-up task, likely via `sci-brain:download-ref` in a
bulk-from-Bib flow if needed later.

## Implementation Steps

1. Inspect all legacy survey directories and extract:
   - survey title
   - last-updated line if present
   - outbound paper links
   - inline cite keys
   - BibTeX entries
2. Build a legacy-to-canonical cite-key mapping by comparing legacy entries against the
   existing `ref.bib`.
3. Append any truly new BibTeX entries to `ref.bib`.
4. Import each legacy `summary.md` into `.knowledge/NOTES.md` as its own labeled
   section, rewriting:
   - relative `.knowledge/` links
   - inline cite keys to canonical keys
5. Update documentation files that still imply the legacy survey layout is active.
6. Verify links, citations, and doc references.
7. Delete `.claude/survey/` once verification passes.

## Documentation Updates

At minimum, implementation must review and update:

- `CLAUDE.md`
- `README.md`
- any project-local onboarding or workflow text that implies `.claude/survey/*` is a
  live storage location

Post-migration documentation must consistently describe:

- project literature state at `.knowledge/`
- bibliography state at `ref.bib`
- survey / review / download-ref workflows as writers to the project KB

## Verification

Implementation must verify all of the following:

- every imported paper link in `.knowledge/NOTES.md` resolves to an existing file under
  `.knowledge/`
- every imported `[@citekey]` in `.knowledge/NOTES.md` exists in `ref.bib`
- legacy-only BibTeX entries were either appended or mapped to existing canonical
  entries without duplication
- repository docs no longer describe `.claude/survey/` as an active KB layout
- no internal repository instructions depend on `.claude/survey/` after deletion

## Risks and Mitigations

### Cite-Key Drift

Risk: legacy surveys use a different cite-key scheme than the current project
`ref.bib`.

Mitigation: keep existing `ref.bib` keys canonical and rewrite imported note citations
to those keys.

### Duplicate Bibliography Entries

Risk: the same paper may appear in multiple surveys with different keys or field
shapes.

Mitigation: deduplicate by `doi`, then `eprint`, then normalized title before any
append.

### Editorial Distortion

Risk: aggressive rewriting of survey notes could change meaning or remove useful topic
framing.

Mitigation: import each legacy survey as a bounded section with minimal changes beyond
provenance, link repair, and cite-key normalization.

## Success Criteria

This migration is complete when:

- the repository has one active `sci-brain` KB layout
- all retained survey content lives under `.knowledge/NOTES.md`
- all retained bibliography content lives under `ref.bib`
- the legacy survey directories are gone
- future `sci-brain` workflows can operate without any dependence on the pre-0.3
  layout
