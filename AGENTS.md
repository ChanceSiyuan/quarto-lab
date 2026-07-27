# Research Loop Implementation Guardrails

- Implement only in `/home/chance/research-loop`. Treat `/home/chance/quantum.harness` as read-only migration input.
- Preserve the current dashboard source and appearance. Do not rewrite `app/page.tsx`, `app/globals.css`, or `app/layout.tsx` to make tests pass.
- `knowledge/**/*.qmd` is the only trusted content authority. Never publish `drafts/`; keep `literature/` as external evidence that the resolver does not silently use.
- Disable code execution for every Quarto render or preview: every subprocess must include `--no-execute`. Never compile downloaded LaTeX.
- Use test-first commits. Do not combine unrelated tasks or silently repair unrelated repository state.
- Reuse the opaque Sites project ID in `.openai/hosting.json` exactly: `appgprj_6a66e89526a88191a9e969c6f441086c`. Never invent, reformat, or replace it; do not create a replacement site.
