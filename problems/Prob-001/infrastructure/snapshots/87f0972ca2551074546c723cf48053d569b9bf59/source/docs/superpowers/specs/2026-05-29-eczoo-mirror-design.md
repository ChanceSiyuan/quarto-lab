# Local mirror of the Error Correction Zoo — design

**Date:** 2026-05-29
**Status:** approved (design), pending implementation plan

## Goal

Build a local, offline-usable mirror of the [Error Correction Zoo](https://errorcorrectionzoo.org)
(`errorcorrectionzoo/eczoo_data`, by Albert & Faist) as a **separate reference layer**
inside this repo's `zoo/`. The mirror gives us the full catalog of QEC codes, their
properties, and — most valuably — the **relation graph** between codes, without
disturbing the existing hand-curated `zoo/codes/**/card.json` + `zoo/evidence/**`.

## Decisions (from brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Integration | **Separate reference layer** | Keeps provenance clean; curated cards stay authoritative and may *link* to eczoo by id. |
| Coverage | **Full mirror** | Complete catalog + intact relation graph; never miss a code. |
| Acquisition | **Vendored snapshot, committed** | Fully offline & reproducible without network; accepts CC-BY-SA bookkeeping. |
| Interface | **Derived index + static browse site** | Machine-queryable (JSON index) and human-browsable offline (site), matching existing `views/` pattern. |
| eczoo site placement | **Separate slice** under `external/eczoo/views/site/` | Avoids merging two differently-licensed corpora into one site. |

## Licensing (CC-BY-SA 4.0)

The eczoo content is CC-BY-SA 4.0. Because we **redistribute** (vendored snapshot),
both obligations apply to the eczoo-derived material:

- **Attribution (BY):** credit "The Error Correction Zoo" (Albert & Faist),
  link the license, indicate changes (YAML→JSON, field filtering). Carried once in
  `external/eczoo/NOTICE.md` + upstream `LICENSE`.
- **ShareAlike (SA):** the vendored raw YAML **and** any derived artifact (index JSON,
  browse.md, site) are adaptations and must be marked CC-BY-SA 4.0.

ShareAlike attaches **only to the eczoo-derived material**, not the whole repo. Our
`autoqec_zoo` importer code, JSON schemas, and original `card.json`/evidence remain
under the repo's own license; mere aggregation does not relicense independent work.

> **Verify first:** confirm the upstream LICENSE is actually CC-BY-SA 4.0 (and capture
> its exact wording) as the first implementation step before finalizing NOTICE.md.

## Layout

```
zoo/external/eczoo/
  LICENSE                 # upstream CC-BY-SA 4.0 text, carried verbatim
  NOTICE.md               # attribution: title, authors, URL, license link, changes made
  SNAPSHOT.md             # upstream commit SHA + fetch date (reproducibility)
  raw/codes/**/*.yml      # vendored YAML, upstream tree preserved (CC-BY-SA)
  index/
    eczoo-codes.json      # derived flat records (CC-BY-SA)
    eczoo-relations.json  # derived edge list (CC-BY-SA)
  views/
    browse.md             # derived human-readable (CC-BY-SA)
    site/                 # derived static site, reuses existing site assets (CC-BY-SA)
```

## Components

1. **Fetcher** — `make eczoo-fetch`
   - Clones `errorcorrectionzoo/eczoo_data` at a **pinned commit**.
   - Copies the `codes/` YAML tree + upstream LICENSE into `raw/`.
   - Writes the resolved commit SHA + fetch date into `SNAPSHOT.md`.
   - Idempotent (re-run replaces `raw/` and re-stamps SNAPSHOT.md).

2. **Importer / indexer** — new module `autoqec_zoo/eczoo.py`
   - Parses raw YAML; normalizes into two derived artifacts.
   - `eczoo-codes.json`: one record per code —
     `{code_id, name, short_name, family_path, parameters, feature_summary, source_path}`.
   - `eczoo-relations.json`: edge list `{source, target, type}` where
     `type ∈ {parent, child, cousin}`. Computes **inverse edges**: each upstream
     `parent` edge yields a matching `child` edge; `cousin` is symmetric.
   - Validates output against new schemas (see below).
   - **No silent drops:** logs any unparseable file; prints `input_count` vs
     `indexed_count` summary.
   - Flags (but keeps) relation targets that don't resolve to a known `code_id`.

3. **View builder** — extends existing build flow
   - Emits `external/eczoo/views/browse.md` and the static `site/` slice.
   - Reuses existing `zoo/views/site/assets/` (styles/app) where practical.

4. **Cross-link convention**
   - Add optional `eczoo_ref` (string `code_id`) to `zoo/schemas/code-card.schema.json`.
   - Backward-compatible; lets a curated card point at its eczoo entry.

5. **Schemas** — new under `zoo/schemas/`
   - `eczoo-code.schema.json` and `eczoo-relation.schema.json`.

6. **Makefile targets**
   - `eczoo-fetch` — vendor snapshot.
   - `eczoo-build` — importer + view builder over `raw/`.
   - `eczoo-update` — `eczoo-fetch` then `eczoo-build`.

## Data flow

```
upstream git
  → eczoo-fetch → raw/*.yml (committed)
    → importer → index/*.json (committed)
      → view builder → browse.md + site/ (committed)
```

## Error handling & integrity

- Importer never silently drops a code; logs skips and prints a count reconciliation.
- A test asserts `input_count == indexed_count + logged_skips`.
- Unresolved relation targets are flagged in the build log.
- Fetch pins a commit SHA recorded in `SNAPSHOT.md` → reproducible snapshot.

## Testing

- Transform unit tests on a few fixture YAMLs (a topological code, an LDPC/BB code,
  one with cousins).
- Schema-validation test over the generated index.
- Relation-graph test: every `parent` edge has its inverse `child` edge; `cousin`
  edges are symmetric.
- No-silent-drop count test.

## Out of scope (YAGNI)

- Pretty LaTeX/markdown rendering of descriptions (stored/displayed as-is).
- Resolving eczoo `\cite` keys into `.knowledge/` (possible future step).
- Auto-promoting eczoo entries into curated cards (owned by the existing
  `extract-zoo-evidence` flow).

## Assumptions to verify in implementation step 1

- Upstream YAML schema fields: `code_id`, `name`, `short_name`, `introduction`,
  `description`, `protection`, `features.*`, `relations.parents`/`relations.cousins`,
  `_meta`. Confirm exact names/shape against the cloned repo before finalizing the
  field mapping.
- Upstream license is CC-BY-SA 4.0; capture exact wording for NOTICE.md.
