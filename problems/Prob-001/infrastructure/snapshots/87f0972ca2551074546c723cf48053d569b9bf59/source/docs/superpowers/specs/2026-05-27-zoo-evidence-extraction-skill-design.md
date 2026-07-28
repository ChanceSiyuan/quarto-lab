# Zoo Evidence Extraction Skill Design

## Goal

Design a project-level skill for AutoQEC that extracts structured QEC Zoo evidence drafts from a single paper already indexed in this repository's `.knowledge/` directory, then supports a separate approval step that converts reviewed drafts into formal evidence records under `zoo/evidence/`.

The skill is intentionally limited to the evidence layer. It does not directly update canonical code cards.

## Scope

This skill supports two actions:

1. `extract`
   - input: one `.knowledge/<paper>.md` file
   - output: one or more `zoo/evidence/<paper-id>/*.draft.json` files

2. `approve`
   - input: one or more `zoo/evidence/<paper-id>/*.draft.json` files
   - output: reviewed formal `zoo/evidence/<paper-id>/*.json` files

The skill is project-local and lives under `.claude/skills/`.

## Non-Goals

- no batch processing across multiple `.knowledge/*.md` files in v1
- no direct editing of `zoo/codes/**/card.json`
- no ingestion from raw PDF paths in v1
- no ingestion from arXiv IDs or DOIs in v1
- no heavy extraction pipeline or standalone CLI in v1
- no inclusion of draft evidence in normal Zoo builds

## Repository Dependencies

The skill is tightly coupled to the current AutoQEC repository structure:

- `.knowledge/*.md` as the source text for paper understanding
- `zoo/evidence/` as the output target
- `zoo/codes/**/card.json` for known code identifiers
- `zoo/schemas/evidence.schema.json` as the formal evidence contract
- existing `zoo` loader and builder behavior

This is a project-level skill, not a general-purpose global skill.

## Skill Placement

The skill should be stored at:

```text
.claude/skills/extract-zoo-evidence/SKILL.md
```

V1 should start with a single `SKILL.md` file only. No helper scripts are required in the first version.

## Trigger Conditions

The skill should trigger for requests such as:

- "extract zoo evidence from this paper"
- "turn this `.knowledge` paper into zoo evidence drafts"
- "generate QEC Zoo evidence for this paper"
- "approve these zoo evidence drafts"

The skill should not trigger for:

- generic paper summarization
- requests to update canonical code cards
- batch processing of all papers in `.knowledge/`
- rebuilding `zoo/views` or the static site

## Input Contract

### Extract

- exactly one `.knowledge/<paper>.md` file

### Approve

- one or more `zoo/evidence/<paper-id>/*.draft.json` files

If the user provides anything outside these contracts, the skill should stop and explain the mismatch instead of guessing.

## Output Model

### Main Decision

The skill only produces evidence drafts in v1. It does not directly modify canonical code cards.

### Draft Location

Draft files are written directly under:

```text
zoo/evidence/<paper-id>/
```

Draft files must use the `.draft.json` suffix so normal Zoo build flows can ignore them.

## Draft Naming Rules

Each draft file represents one claim under one context.

Recommended pattern:

```text
<code-slug>.<claim-type>.<nn>.draft.json
```

Examples:

- `bivariate-bicycle-code.parameter-claim.01.draft.json`
- `surface-code.threshold-evidence.02.draft.json`
- `rotated-surface-code.decoder-claim.01.draft.json`

The numeric suffix prevents naming collisions when one paper contains multiple claims of the same type for the same code.

## Granularity

The granularity rule is:

- one evidence file per single claim
- one file per single contextual envelope

This means a paper can yield multiple draft files for the same code when it presents multiple distinct claims or multiple contexts.

The skill should not aggregate all claims for a code into one file.

## Supported Claim Shapes

The skill should preferentially extract claim categories that map naturally to the current Zoo evidence model, including:

- `parameter_claim`
- `decoder_claim`
- `threshold_evidence`
- `distance_claim`
- `relation_claim`

If a paper contains a claim that does not fit a stable v1 claim type, the skill should either:

- leave it out, or
- record it only if it can still be represented faithfully without inventing a misleading type

## Known vs Unknown Codes

### Known Code

If the code already exists under `zoo/codes/<slug>/card.json`, the skill should use that slug as `code_id`.

### Unknown Code

If the paper discusses a code that is not yet represented in `zoo/codes/`, the skill should still allow draft creation.

Unknown-code drafts must include:

- `proposed_code_slug`
- `proposed_title`

These drafts are allowed to exist, but they are not eligible for formal approval until a canonical card for that code exists.

## Draft vs Formal Evidence

### Draft Evidence

Draft evidence may be slightly wider than the formal schema in order to support review-time metadata.

Draft-only fields allowed in v1:

- `proposed_code_slug`
- `proposed_title`
- `approval_notes` (optional)

### Formal Evidence

Formal evidence files:

- must use the `.json` suffix
- must not retain draft-only fields
- must fully satisfy `zoo/schemas/evidence.schema.json`

Approval is therefore not just a rename. It is a review-and-normalize step followed by rename.

## Build Boundary

Normal Zoo loading and building must ignore `*.draft.json`.

Only approved `.json` evidence files should enter:

- the loader
- index generation
- markdown generation
- site generation

This preserves a clean boundary between provisional extraction output and source-of-truth records.

## Extract Workflow

### Phase 1: Read

Read exactly one `.knowledge/<paper>.md` file.

### Phase 2: Identify Code Mentions

Identify code entities discussed in the paper and attempt to map each one to an existing `zoo/codes/` entry.

### Phase 3: Extract Claims

For each code, extract only claims that can be grounded in the paper text and represented as structured evidence.

Each claim should be paired with the minimum necessary context:

- noise model
- decoder
- distance method
- assumptions
- parameter point

### Phase 4: Write Draft Files

Write one `*.draft.json` per claim/context pair under `zoo/evidence/<paper-id>/`.

### Phase 5: Print Summary

Always print a concise terminal summary that includes:

- input paper path
- paper id
- recognized codes
- generated draft files
- unknown codes
- low-confidence mappings
- next-step recommendation for approval

## Approve Workflow

### Phase 1: Load Drafts

Read one or more `*.draft.json` files selected by the user.

### Phase 2: Review

For each draft, verify:

- `paper_id`
- `code_id`
- claim type choice
- faithfulness of `claim.statement`
- appropriateness of extracted context
- whether the file still depends on a non-canonical code

### Phase 3: Gate Unknown Codes

If a draft references a code with no canonical card yet, approval must stop for that draft.

The skill should tell the user to create the canonical card first.

### Phase 4: Normalize

Before approval:

- remove draft-only fields
- make sure the record conforms to the formal evidence schema

### Phase 5: Promote

Rename:

```text
*.draft.json -> *.json
```

### Phase 6: Print Summary

Always print:

- approved files
- rejected or deferred files
- reasons for rejection
- recommendation to run `make zoo-build`

## Failure Conditions

The skill should stop rather than guess when:

- the input is not exactly one `.knowledge/*.md` file for `extract`
- the supplied input is not one or more `*.draft.json` files for `approve`
- the paper id cannot be determined reliably
- code mapping is too ambiguous
- the claim cannot be represented without inventing unsupported semantics
- formal schema validation fails during approval
- approval depends on a code that still lacks a canonical card

## Style Rules for Extraction

The skill should favor conservative extraction:

- do not elevate conditional claims into universal statements
- do not collapse multiple contexts into one
- do not invent threshold values, decoder names, or assumptions
- keep claim statements faithful to the paper
- preserve uncertainty in the evidence layer instead of hiding it

## User Experience

The skill should be explicit about what it did.

For `extract`, it should report:

- what paper was processed
- which codes were found
- what drafts were written
- which drafts need manual attention

For `approve`, it should report:

- what was promoted
- what was rejected or deferred
- what still blocks formal inclusion in the Zoo

## Future Extensions

These are explicitly deferred from v1:

- helper scripts for validation or rename
- PDF input support
- arXiv/DOI input support
- batch extraction
- automatic canonical-card update suggestions written to files
- a global generalized version of this skill

## Recommended Implementation Order

1. add the project-level skill skeleton at `.claude/skills/extract-zoo-evidence/SKILL.md`
2. update the Zoo loader/build flow so `*.draft.json` is ignored
3. define the draft JSON shape clearly in the skill instructions
4. add a lightweight approval flow inside the skill
5. optionally add small helper scripts later if the manual mechanical steps become repetitive
