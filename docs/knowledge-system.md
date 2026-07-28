# Quarto Knowledge System

## Scope

This phase makes the existing Quarto garden readable through one validated
model shared by humans and agents. It deliberately does not implement an
autonomous research runner or a new literature ingestion pipeline.

The governing decisions are ADRs 0003–0005 and 0009:

- `theory/` is Trusted Knowledge;
- `drafts/` and `conference/` are untrusted siblings;
- trusted local dependencies are transitively closed;
- one Reading map controls both human and agent order.

## Deep module

`lib.knowledge` owns the full trusted-content lifecycle:

```python
load_knowledge(repo_root)
validate_knowledge(repo_root)
resolve_knowledge(query, repo_root)
materialize_quarto_project(graph=graph, workspace=workspace)
build_knowledge_site(repo_root=repo_root)
preview_knowledge_site(repo_root=repo_root)
```

Callers use these interfaces rather than recreating discovery, trust, order,
or rendering semantics.

## Data flow

```text
theory/**/*.qmd
      │
      ▼
parse ──► KnowledgeGraph ──► complete validation
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
              deterministic resolve     temporary projection
                     │                         │
              Reading Bundle          quarto --no-execute
                                               │
                                         output audit
                                               │
                                      atomic _site swap
```

No resolver or renderer may consume a partially validated graph.

The repository-root `index.qmd` is not part of that graph. It is a
human-facing Site Chrome page, validated under a separate narrow contract
before projection and never returned to an agent.

## Validation invariants

- Discovery is deterministic and does not follow symlinks.
- Every QMD-bearing directory is represented by a direct `index.qmd`.
- Reading maps exactly cover direct children and are the only containment
  edges.
- Related-topic edges are optional, index-only, and may cycle.
- Trusted frontmatter cannot change execution or inject Quarto extensions,
  filters, includes, resources, or formats; decoded metadata may not contain
  HTML.
- All local links and resource URLs, including raw-HTML anchors, images, audio,
  video, sources, and posters, remain inside `theory/`; approved root
  `references.bib` is the sole bibliography exception.
- Only HTTP, HTTPS, and mailto external schemes are recognized; other schemes
  are rejected explicitly.
- Active HTML, network-loading CSS, symlink traversal, and Quarto shortcodes in
  any body text (including inline/fenced code), raw HTML, decoded frontmatter,
  or base configuration are rejected.
- Every local non-page dependency must already be a regular file with an
  allowlisted suffix, and SVG safety is part of graph validation rather than a
  later renderer-only surprise.
- Diagnostics are structured and sorted by file, line, column, then code.

## Resolution

Text is normalized with Unicode NFKC and case folding. Ranking tiers are:

1. exact title;
2. exact alias;
3. title terms;
4. alias terms;
5. description terms;
6. body terms.

Within a tier, matched-term count, curated Reading-map order, and POSIX path
provide stable ordering. Equally best results in different topics return
`ambiguous`; the resolver never picks one arbitrarily.

A Reading Bundle contains the root-to-topic index chain followed by selected
content pages. All paths are repository-relative.

## Safe rendering

The renderer never invokes Quarto against the repository source tree. It
materializes a hook-free project under `work/`, reasserts execution disabled,
and additionally passes `--no-execute`. The public projector performs its own
complete validation and rejects stale or tampered graph values. `_quarto.yml`
is reconstructed from strict nested allowlists, so Pandoc arguments, Lua
filters, extensions, hooks, and arbitrary includes cannot pass through. Only
validated QMD, the separately validated homepage, referenced local assets and
bibliographies, and audited fixed site assets enter the project.

The rendered tree is required to contain `index.html`; its root and descendants
must be real, non-symlink paths. It is rejected if it contains source
QMD/BibTeX/TeX, drafts, conference notes, literature, notebooks, caches,
Python/shell/Lua scripts, or symlinks. The previous `_site/` is moved aside only
after that audit and is restored if final publication fails.
