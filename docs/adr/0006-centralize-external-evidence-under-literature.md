# Centralize external evidence under literature

**Status: deferred architecture; not implemented in the current phase.**

A future top-level `literature/` tree will own canonical external
bibliographic metadata, generated method indexes, and ignored pinned source
material under `.raw/` and `.figures/`. A single `literature/ref.bib` will
replace manually synchronized bibliography authorities; lossy rendered
full-text Markdown is not Evidence, and trusted resolution may use literature
only through an explicitly named external-research or source-audit workflow.

Until that migration is designed and approved, the existing
`.knowledge/literature/` remains external, untrusted input and is never read by
the trusted resolver or copied into the public site.
