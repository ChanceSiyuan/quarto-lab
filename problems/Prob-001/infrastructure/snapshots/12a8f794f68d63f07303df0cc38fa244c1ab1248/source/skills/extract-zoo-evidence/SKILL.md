---
name: extract-zoo-evidence
description: Use when extracting QEC Zoo evidence drafts from a single paper already indexed in this repo's .knowledge/ directory, or when reviewing and approving zoo evidence draft files into formal evidence records.
---

# extract-zoo-evidence

## Overview

This is a project-level AutoQEC skill for the structured Zoo layer.

It supports exactly two actions:

- `extract`: read one `.knowledge/<paper>.md` file and write one or more `zoo/evidence/<paper-id>/*.draft.json` files
- `approve`: review one or more `zoo/evidence/<paper-id>/*.draft.json` files and promote approved drafts to formal `.json` evidence records

This skill does not:

- process multiple papers at once
- read raw PDFs directly
- download arXiv or DOI inputs
- edit `zoo/codes/**/card.json`
- rebuild `zoo/views`

## When to Use

- The user wants structured Zoo evidence extracted from a single paper already present in `.knowledge/`
- The user wants to approve one or more Zoo evidence draft files
- The request is specifically about creating or promoting `zoo/evidence/` records, not about canonical card editing

Do not use:

- for generic paper summaries
- for bulk `.knowledge/` ingestion
- for canonical card authoring
- for rebuilding Zoo views or the static site

## Input Contract

### Extract

Input must be exactly one `.knowledge/<paper>.md` file.

### Approve

Input must be one or more `zoo/evidence/<paper-id>/*.draft.json` files.

If the input does not match one of these shapes, stop and explain the mismatch.

## Draft Naming

Write draft files under:

- `zoo/evidence/<paper-id>/`

Use this filename pattern:

- `<code-slug>.<claim-type>.<nn>.draft.json`

The `<claim-type>` filename segment is the kebab-case form of the structured `claim_type` value.

Examples:

- `parameter_claim` -> `parameter-claim`
- `threshold_evidence` -> `threshold-evidence`

Draft filename examples:

- `bivariate-bicycle-code.parameter-claim.01.draft.json`
- `surface-code.threshold-evidence.02.draft.json`

Draft files are provisional and must not be treated as formal Zoo evidence.

## Draft Rules

Each draft file contains exactly one claim under one context.

Allowed draft-only fields:

- `proposed_code_slug`
- `proposed_title`
- `approval_notes`

If a code is not yet present under `zoo/codes/`, drafts may still be written. In that case:

- set `code_id` to the proposed slug that would be used for the future canonical card
- also include the same value in `proposed_code_slug`
- include `proposed_title`

Unknown-code drafts are not eligible for approval until a canonical card exists.

## Extract Workflow

1. Read exactly one `.knowledge/<paper>.md` file.
2. Determine the paper id from the knowledge-base record.
3. Identify code mentions and map them to existing `zoo/codes/**/card.json` entries when possible.
4. For each code, extract only claims that can be represented faithfully as Zoo evidence.
5. Use one draft file per single claim and single contextual envelope.
6. Write the draft files under `zoo/evidence/<paper-id>/`.
7. Print a terminal summary including:
   - input paper path
   - paper id
   - recognized codes
   - generated draft files
   - unknown codes
   - low-confidence mappings
   - next-step approval recommendation

## Extraction Style

Be conservative:

- do not invent unsupported semantics
- do not merge distinct contexts
- do not upgrade paper-conditional claims into canonical truth
- keep `claim.statement` faithful to the paper
- keep uncertainty in the evidence layer

Prefer claim types such as:

- `parameter_claim`
- `decoder_claim`
- `threshold_evidence`
- `distance_claim`
- `relation_claim`

If a claim cannot be represented faithfully, omit it rather than distort it.

## Approve Workflow

1. Read one or more `*.draft.json` files selected by the user.
2. For each draft, review:
   - `paper_id`
   - `code_id`
   - claim type choice
   - faithfulness of `claim.statement`
   - appropriateness of extracted context
   - whether the draft still depends on a non-canonical code
3. If the draft references a code that does not yet have a canonical card, stop approval for that draft.
4. Before promotion:
   - remove draft-only fields
   - ensure the record fully satisfies `zoo/schemas/evidence.schema.json`
5. Promote approved drafts by renaming:
   - `*.draft.json -> *.json`
6. Print a terminal summary including:
   - approved files
   - rejected or deferred files
   - reasons
   - recommendation to run `make zoo-build`

## Build Boundary

Normal Zoo loading and building ignore `*.draft.json`.

Only approved `.json` evidence files should enter the loader, indexes, markdown views, and site generation.

## Failure Conditions

Stop rather than guess when:

- the input is not exactly one `.knowledge/*.md` file for extract
- the input is not one or more `*.draft.json` files for approve
- the paper id cannot be determined reliably
- code mapping is too ambiguous
- the claim cannot be represented faithfully
- approval depends on a code with no canonical card
- the formal evidence schema does not validate after draft-only fields are removed
