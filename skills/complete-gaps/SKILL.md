---
name: complete-gaps
description: Use when a draft .qmd contains (t.b.c.) or (todo:*) placeholders, skipped derivation steps, or rough passages that need rigorous completion — "complete the t.b.c.", "fill the missing proofs", "finish this draft", "make this section rigorous".
---

# complete-gaps

Surgically complete a Quarto draft: locate every `(t.b.c.)` and `(todo:*)`,
replace each with a rigorous, step-by-step derivation, and bridge any logical
gaps — without restructuring the draft. Output is the completed `.qmd` plus
an updated bibliography (whichever file the draft's frontmatter points to —
usually the section `refs.bib`, else the root `references.bib`).

<example name="activate good">
User: "theory/compatibility/draft.qmd has three (t.b.c.) proofs — complete them from the paper's tex source." → complete-gaps fires (Mode B).
</example>

<example name="activate not-applicable">
User: "Expand these bullet notes into a full article." → use `expand-notes` (expansion, not completion).
</example>

## Mode: choose ONE

- **Mode A — from chat history.** Source material is a chat between the user
  and an AI assistant. "### User" sections carry the core intent; critically
  evaluate "### Assistant" sections — extract correct derivations, discard
  redundancy, upgrade rigor. Skip basic overviews; focus strictly on
  advanced theoretical depth (e.g. many-body physics, qubit mappings).
- **Mode B — from LaTeX paper.** The paper's source is ground truth.
  `(t.b.c.)` marks: (1) missing proofs inside callout blocks, (2) missing
  inline parameters, (3) messy text needing formal rewriting. Where the paper
  skips steps ("it is easy to see…"), fill in the algebra from domain
  knowledge or literature search. Clean up mangled inline math into proper
  LaTeX.

## Core directives

1. **Targeted completion.** Replace every placeholder with a detailed,
   self-consistent proof. If the source lacks detail, use web search or
   external domain knowledge — never leave a gap silently unfilled.
2. **Missing theorems.** If a derivation silently relies on a theorem or
   identity not stated in the draft, add a new formal block
   (`::: {#thm-new-name .callout-important icon="false"}`): prove it in a
   `collapse="true"` callout if brief, otherwise state it and cite precisely
   (adding the entry to `refs.bib`).
3. **Structure preservation.** Do not heavily alter the draft's structure,
   headings, or core narrative. Modifications are surgical: fill proofs, add
   supporting theorems, insert bridging sentences for coherence — small
   corrections within that scope are fine.
4. **Formatting.** Retain all existing Quarto Div syntax; wrap inserted
   proofs in expandable callouts; keep math notation consistent with the
   equations already in the draft.
5. **Grounding & citation.** Every imported step or theorem must be standard,
   verifiable literature — cited inline and added to `refs.bib`.

## Workflow

1. Inventory the placeholders and any implicit logical gaps.
2. Present an outline FIRST: per-gap completion plan, gaps needing external
   sources, new theorem blocks (prove vs. cite), and papers to add to the bib.
3. **Wait for confirmation on the outline before writing the final files.**
4. Apply the edits; update `refs.bib`.
5. Verify: no `(t.b.c.)`/`(todo:` remains (`grep -n "t.b.c.\|todo:" <file>`),
   render passes (`render-site`), citations resolve.
