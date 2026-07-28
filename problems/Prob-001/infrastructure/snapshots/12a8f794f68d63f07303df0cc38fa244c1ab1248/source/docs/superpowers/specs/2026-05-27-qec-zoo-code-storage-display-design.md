# QEC Zoo Code Storage and Display Design

## Goal

Design the first structured `zoo/` layer for this repository so AutoQEC can store and present normalized code knowledge extracted from papers.

The initial scope is limited to:

- storage structure for canonical code cards
- storage structure for paper-level evidence
- derived indexes and presentation artifacts
- clear separation between stable code facts and paper-specific claims

This design does **not** cover the extraction pipeline implementation itself. It defines the data model and display contract that later extraction and browsing code must target.

## Scope

This design supports structured coverage of code properties such as:

- code family
- construction
- parameters
- assumptions
- decoder
- distance method
- threshold evidence
- relations to other codes

It also handles a key modeling distinction:

- abstract code families and concrete variants are first-class entities
- concrete parameter points such as `d=3,5,7` are **not** first-class stored entities by default
- a parameter point appears only inside an evidence record unless a user explicitly requests instance generation through an external code/construction repo

## Non-Goals

- no general graph database
- no always-on stored `instance` entity
- no implementation of paper parsers in this spec
- no attempt to force every decoder, noise model, or distance method into its own first-class entity in v1

## Design Decisions

### Storage Mode

The system uses a dual-layer model:

1. paper-level extraction artifacts are preserved as evidence
2. canonical code cards summarize stable facts across papers

This avoids losing provenance while still supporting a clean Zoo view.

### Code Hierarchy

The knowledge model distinguishes:

1. `code_family`
2. `code_variant`
3. `evidence`

Examples:

- `surface-code` is a family-level object
- `rotated-surface-code` is a variant-level object
- a threshold fit for `rotated-surface-code` at `d in {3,5,7,9}` under a specific decoder and noise model is an evidence record

The repository does not persist parameterized instances such as `rotated-surface-code@d=3` as default standalone entities.

### Canonical vs Conditional Facts

Canonical cards contain only stable facts:

- definitions
- construction summaries
- parameter formulas
- stable assumptions
- known decoder names
- known distance-method names
- explicit code relations

Conditional, conflicting, or context-dependent claims remain in evidence:

- threshold values
- decoder comparisons
- finite-size parameter points
- claims that depend on a specific noise model
- claims that differ across papers

### Main Repository Placement

Structured Zoo data lives under top-level `zoo/`, not under `.knowledge/`.

This keeps:

- `.knowledge/` focused on paper text and notes
- `zoo/` focused on normalized structured code knowledge

## Directory Layout

```text
zoo/
  README.md
  schemas/
    code-card.schema.json
    evidence.schema.json
    view-index.schema.json

  codes/
    surface-code/
      card.json
      card.md
    rotated-surface-code/
      card.json
      card.md
    bivariate-bicycle-code/
      card.json
      card.md

  evidence/
    2308.07915/
      surface-code.thresholds.json
      rotated-surface-code.decoder-comparison.json
    2408.10001/
      bivariate-bicycle-code.parameters.json

  views/
    code-index.json
    family-index.json
    relation-index.json
    evidence-index.json
    browse.md
    site/
      index.html
      assets/
```

## Source of Truth Boundaries

The source-of-truth layer is:

- `zoo/codes/**/card.json`
- `zoo/evidence/**/*.json`

The derived layer is:

- `zoo/codes/**/card.md`
- `zoo/views/*.json`
- `zoo/views/browse.md`
- `zoo/views/site/**`

Derived artifacts must always be rebuildable from the source-of-truth layer.

## Canonical Card Model

Each canonical card represents one code family or one code variant.

Recommended shape:

```json
{
  "id": "rotated-surface-code",
  "kind": "code_variant",
  "title": "Rotated Surface Code",
  "family": "surface-code",
  "aliases": ["rotated planar code"],
  "summary": "A surface-code variant with rotated lattice layout and reduced qubit overhead.",
  "construction": {
    "type": "topological_css",
    "description": "Defined on a rotated square lattice with X/Z plaquettes and boundary conditions."
  },
  "parameters": {
    "logical_qubits": "typically 1",
    "distance_formula": "d",
    "block_length_formula": "2d^2 - 1",
    "rate_scaling": "k/n -> 0"
  },
  "assumptions": [
    "2D nearest-neighbor geometry",
    "stabilizer measurements available"
  ],
  "known_decoders": [
    "MWPM",
    "Union-Find",
    "Tensor-network decoder"
  ],
  "distance_methods": [
    "analytical from geometry",
    "combinatorial decoding graph argument"
  ],
  "relations": [
    {
      "type": "variant_of",
      "target": "surface-code"
    },
    {
      "type": "compared_with",
      "target": "color-code"
    }
  ],
  "evidence_refs": [
    "2308.07915:rotated-surface-code.thresholds",
    "2401.12345:rotated-surface-code.decoder-comparison"
  ],
  "source_refs": [
    "2308.07915",
    "2401.12345"
  ],
  "updated_at": "2026-05-27"
}
```

### Canonical Card Rules

- in v1, `kind` is exactly one of `code_family` or `code_variant`
- `family` points to the parent family when `kind == code_variant`
- `parameters` stores formulas or stable summaries, not paper-local numeric result tables
- `known_decoders` and `distance_methods` are stable inventories, not performance claims
- `relations` contain navigational structure for the Zoo layer
- `evidence_refs` and `source_refs` preserve the bridge to provenance

### What Must Not Be Stored Directly in the Canonical Card

- threshold numbers presented as canonical truth
- decoder superiority claims
- parameter sweeps like `d=3,5,7,9` as a permanent top-level card field
- any claim that only holds under a specific noise model or fitting procedure

## Evidence Model

Each evidence record captures what one paper claims about one code under one context.

Recommended shape:

```json
{
  "id": "2308.07915:rotated-surface-code.thresholds",
  "paper_id": "2308.07915",
  "code_id": "rotated-surface-code",
  "claim_type": "threshold_evidence",
  "title": "Threshold estimates under circuit-level noise",
  "context": {
    "noise_model": "circuit-level depolarizing noise",
    "decoder": "MWPM",
    "distance_method": null,
    "assumptions": [
      "phenomenological repeated syndrome extraction"
    ],
    "parameter_point": {
      "distance_values": [3, 5, 7, 9]
    }
  },
  "claim": {
    "statement": "Threshold is reported around 1%.",
    "value": 0.01,
    "unit": "physical_error_rate",
    "qualifiers": [
      "fit-based estimate",
      "finite-size scaling"
    ]
  },
  "provenance": {
    "section": "Results",
    "quote_ref": "results:p3:para2",
    "confidence": "medium"
  }
}
```

### Evidence Rules

- evidence is paper-local by design
- the same code can have many evidence records across papers
- `claim_type` should be drawn from a controlled set such as:
  - `construction_note`
  - `parameter_claim`
  - `decoder_claim`
  - `distance_claim`
  - `threshold_evidence`
  - `relation_claim`
- concrete parameter points belong in `context.parameter_point`
- provenance remains attached to the record even when a later canonical merge extracts a stable summary

## Multi-Paper Strategy

The repository preserves both layers:

1. `paper-level extraction`
2. `canonical card`

The paper-level layer answers:

- what did this paper say?
- under what assumptions?
- for which decoder or noise model?

The canonical layer answers:

- what stable facts do we want to show as the Zoo summary for this code?

This allows:

- traceable provenance
- incremental updates as new papers arrive
- conflict handling without losing information

## Display Design

The system exposes two outputs from the same data source:

1. repository-native static reading
2. local interactive browsing

### Static Reading

Each code gets:

- `card.json`
- `card.md`

`card.md` is a human-readable projection of the canonical card and should follow a fixed structure:

1. title and summary
2. family, aliases, and kind
3. construction
4. parameter formulas
5. assumptions
6. known decoders
7. distance methods
8. relations
9. linked evidence
10. source papers

Repository-level summary pages:

- `zoo/views/browse.md`
- `zoo/views/code-index.json`
- `zoo/views/family-index.json`
- `zoo/views/relation-index.json`
- `zoo/views/evidence-index.json`

`browse.md` is the main repository-native entry point.

### Interactive Browsing

The local browser UI consumes `zoo/views/*.json`, not raw `codes/` and `evidence/` files.

That keeps the presentation contract stable even if the storage schema evolves.

Recommended first-pass views:

1. `Code List`
   - filters by family, kind, decoder, relation tag
   - shows title, summary, family, source count, evidence count
2. `Code Detail`
   - upper section for canonical facts
   - lower section for paper-specific evidence
   - evidence grouped by claim type
3. `Paper Evidence View`
   - shows what one paper contributed to the Zoo layer
   - supports manual extraction review and provenance inspection

### Display Principle

The UI must visibly separate:

- `Canonical Facts`
- `Paper-Specific Evidence`

The display should not flatten them into a single undifferentiated table. The storage model intentionally distinguishes stable facts from conditional claims, and the browsing layer should preserve that distinction.

## Data Flow

The expected flow is:

```text
paper -> paper-level extraction -> evidence records -> canonical merge -> derived views -> markdown/site
```

Rules:

1. `.knowledge/` papers remain the upstream source
2. new papers first create or update evidence
3. canonical cards are updated only when new evidence changes stable facts
4. all views and markdown pages are regenerated outputs

## Update Policy

### New Paper Arrival

When a new paper is added:

1. extract paper-local claims
2. write or update evidence records
3. re-evaluate affected canonical cards
4. regenerate views and markdown outputs

### Instance Requests

If a user later requests a concrete parameterized instance, instance generation should happen in an external code or construction repo. The resulting object can be linked back into the Zoo layer as a derived artifact, but it should not force v1 to adopt a permanent standalone `instance` entity.

## Error Handling and Uncertainty

The first version must represent unresolved cases explicitly.

Important uncertainty classes:

- `unresolved_code_identity`
  - unclear whether the paper refers to a family, a variant, or a genuinely new code
- `conflicting_claims`
  - different papers disagree on thresholds, decoder comparisons, or derived performance
- `insufficient_evidence`
  - not enough support to elevate a claim into canonical stable facts
- `schema_valid_but_semantically_uncertain`
  - the extraction fits the JSON schema but remains semantically doubtful

These cases belong in the evidence and provenance layer, not silently in canonical summaries.

## Testing Boundaries

Initial verification should focus on data correctness, not UI polish.

### Required Validation

- schema validation for `card.json`
- schema validation for `evidence.json`
- schema validation for view indexes

### Required Behavioral Tests

- aggregation tests for multiple evidence records on one code
- conflict tests to confirm conditional claims do not leak into canonical stable facts
- regeneration tests to confirm deterministic `views/*` output for the same inputs
- smoke tests for markdown and site outputs to catch broken links or missing targets

## Why This Design

This design deliberately stays between two extremes:

- it is stronger than a loose pile of markdown notes
- it is much lighter than a full graph-native knowledge system

That is the right balance for v1 because the repository currently needs:

- provenance-preserving structured extraction
- git-friendly manual inspection
- stable inputs for a future local browser
- room for future instance generation without prematurely committing to an always-on instance model

## Summary

The v1 Zoo layer should:

- live in top-level `zoo/`
- store canonical code cards and paper-level evidence separately
- treat families and variants as first-class, but parameter points as evidence-local by default
- keep canonical cards restricted to stable facts
- preserve all conditional claims in evidence
- generate both markdown and interactive browsing outputs from derived views
