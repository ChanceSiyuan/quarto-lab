---
name: render-site
description: Use when building, previewing, or debugging this Quarto knowledge site; checking whether trusted .qmd changes render; investigating site assets, citations, navigation, or render failures; or when the user says "render the site", "preview the site", or "Quarto build".
---

# Render the validated knowledge site

Render only through the repository's safe KnowledgeGraph seam. Never invoke
`quarto render` or `quarto preview` directly.

## Commands

| Task | Command |
|---|---|
| Validate trusted knowledge | `make knowledge-check` |
| Build the site | `make knowledge-build` |
| Preview the site | `make knowledge-preview` |
| Run tests | `make test` |

`./scripts/render_site.sh` is a compatibility alias for the same safe build.

## Required workflow

1. Run `make knowledge-check`.
2. If validation fails, fix the reported source file and rerun it.
3. Run `make knowledge-build`.
4. Inspect the generated page under `_site/`; never edit `_site/` itself.

The builder validates `theory/`, projects only trusted QMD plus referenced
assets and bibliographies into a temporary hook-free Quarto project, sets
`execute.enabled: false`, and invokes Quarto with `--no-execute`. It derives
the sidebar from each topic's single `## Reading map`, audits rendered
filenames, and atomically replaces the last verified `_site/` only after the
complete render succeeds.

## Navigation and trust

- `theory/**/*.qmd` is the only trusted knowledge authority.
- `drafts/` and `conference/` are untrusted and must never appear in a build.
- Every directory containing trusted QMD descendants needs a direct
  `index.qmd`.
- Each topic index owns exactly one `## Reading map`.
- List every direct child page or child-topic index exactly once, in the
  intended human reading order.
- Do not recreate `_sidebar.yml`, `_metadata.yml`, AUTO blocks, or a separate
  agent index.

## Remote fallback

If the local `.venv` or Quarto installation is unavailable, use the same safe
command on the DGX:

```sh
ssh chance@100.106.69.117 \
  'bash -lc "export PATH=$HOME/.local/bin:$PATH && cd ~/quarto-lab && make knowledge-build"'
```

Do not substitute a direct Quarto command on either machine.

## Verification

- Confirm `make knowledge-check` reports zero diagnostics.
- Confirm the requested HTML page and referenced assets exist under `_site/`.
- Confirm citations do not render as unresolved `?@key`.
- Confirm the sidebar order matches the parent `## Reading map`.
- Confirm no `.qmd`, `.bib`, draft, conference, notebook, cache, or source
  script appears under `_site/`.
- On failure, report the real diagnostic. The previous `_site/` must remain
  intact.

Deployment is outside this skill. Ask the user before attempting it.
