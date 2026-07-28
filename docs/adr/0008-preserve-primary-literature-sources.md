# Preserve primary literature sources instead of rendered full text

**Status: deferred architecture; no new importer is implemented in this
phase.**

The adapted `download-ref` workflow will create version-pinned Literature Source Bundles under top-level `literature/`: canonical BibTeX and generated method indexes are committed, while original archives, safely extracted TeX trees, PDFs, source figures, and deterministic manifests stay in ignored `.raw/<citekey>/` and `.figures/<citekey>/` directories. The importer preflights archives, records hashes, swaps complete bundles atomically, never compiles TeX, and never creates a lossy rendered Markdown copy; agents verify formulas against the source TeX or PDF and treat all literature as external Evidence rather than Trusted Knowledge. A DOI-only or local-PDF record may explicitly declare `latexAvailable: false`; it remains usable as PDF-only Evidence, and the workflow never reconstructs pseudo-source LaTeX from PDF text.
