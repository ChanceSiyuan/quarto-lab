---
name: render-site
description: Use when building or previewing the trusted knowledge site, checking QMD rendering, or diagnosing its navigation, citations, assets, and render failures.
---

# Render the validated knowledge site

Render only through the repository's safe knowledge commands. Never invoke `quarto render` or `quarto preview` directly.

## Commands

| Task | Command |
|---|---|
| Validate trusted knowledge | `make knowledge-check` |
| Build the site and application | `make build` |
| Preview the trusted knowledge site | `make knowledge-preview` |

## Workflow

1. Run `make knowledge-check`.
2. If validation fails, fix the reported source page and rerun the check.
3. Use `make build` for a verified published artifact, or `make knowledge-preview` for a local live preview.
4. Inspect the requested page and navigation. Never edit `public/knowledge`; it is generated output.

The safe builder projects only validated `knowledge/**/*.qmd` pages, referenced assets, and `literature/ref.bib` into a temporary hook-free Quarto project. It disables execution, derives navigation from each topic's `## Reading map`, and replaces the previous generated site only after a successful render.

Confirm that citations resolve, the sidebar follows reading-map order, and no source `.qmd`, bibliography, draft, literature full text, notebook, or script appears in the output. On failure, report the actual diagnostic and leave the previous verified site intact.
