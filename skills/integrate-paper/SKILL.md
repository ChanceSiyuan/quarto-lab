---
name: integrate-paper
description: Use when integrating results from this repo's .qmd research notes into a LaTeX manuscript — "integrate into the paper", "fill the main body from my notes", "transfer these qmd results into main.tex", "restructure the appendix".
---

# integrate-paper

Fill and restructure a LaTeX manuscript (typically revtex4-2, PRL-style main
body + Supplemental Material) from results scattered across this repo's
Quarto research notes. The `.qmd` notes are the primary content source; the
`.tex` file owns notation and structure. But notes can contain superseded
claims — corrections from the user's discussion ALWAYS override the notes
(in the archived instance, the notes' f-compatibility SDP equivalence was
known-invalid: the Γ-SDP is only a relaxation, exact only for rank-1 POVMs).
Ask the user for the current list of corrections before treating any note
as ground truth, and record them in the section map.

<example name="activate good">
User: "Fill sec1–sec6 of _resource/main.tex from theory/Shadow_tomography." → integrate-paper fires.
</example>

<example name="activate not-applicable">
User: "Complete the (t.b.c.) proofs in this qmd." → use `complete-gaps` (qmd-side work, no manuscript).
</example>

## Inputs to establish first

| Input | Example |
|---|---|
| Target manuscript | `_resource/main.tex` |
| Source note dirs | `theory/Shadow_tomography`, `theory/compatibility` |
| Section map | which placeholder sections get which results |
| Page budget | main body ≤ 4 pages (PRL) |

If the user has not supplied a section map, propose one after reading the
sources and confirm it before writing.

## Workflow

1. **Read all source `.qmd` files** and extract theorems, proofs, examples,
   and figures — note their anchors (`@thm-*`, `@def-*`) so nothing is lost.
2. **Map results onto the paper skeleton**: which results are main-body
   statements, which are appendix proofs, which are dropped.
3. **Fill the main body** concisely in the journal's style (`\prlsection`,
   theorem environments, proofs deferred to the appendix). Respect the page
   budget.
4. **Reorganize the appendix**: merge existing appendix content with new
   material from the notes; keep existing derivations that survive, add
   sections for new frameworks and proofs.
5. **Maintain notation consistency** with the manuscript's existing macros
   (e.g. `\tr`, `\ox`, `\1`, `\ket`, `\bra`, `\proj`) — translate qmd
   notation, never import it verbatim.
6. **Write/refresh the abstract** enumerating the main results.
7. **Complete the bibliography**: every result imported from a note carries
   its citations into the `.bib` file.

## Verify before reporting

<checklist name="verify-integration">
- Every placeholder section in the target `.tex` is filled or explicitly deferred
- The manuscript compiles (`latexmk -pdf` or the project's build command)
- No orphan `\ref`/`\cite` keys; the .bib contains every new citation
- Main body within the page budget; proofs live in the appendix/SM
- Notation matches the manuscript's macro layer throughout
</checklist>

## Reference instance

The original worked example of this workflow (multi-copy shadow tomography,
with its full section map and insight list) is archived at
`_instructions/integrate_paper.md` — consult it as a model for granularity,
not as content for a new paper.
