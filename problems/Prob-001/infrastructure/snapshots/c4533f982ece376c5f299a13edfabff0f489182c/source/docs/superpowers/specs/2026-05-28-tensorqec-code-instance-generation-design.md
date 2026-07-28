# TensorQEC Code Instance Generation Design

## Goal

Design the first AutoQEC workflow for generating finite-size parity-check matrices from a code package, then storing the generated artifacts in the repository's structured `zoo/` layer.

The first version targets `tensorQEC.jl` only. It introduces:

- one project-level skill for setting up a repository-local Julia environment with `tensorQEC.jl`
- one project-level skill for generating finite-size code instances from that environment
- one new structured data layer for program-generated finite CSS instances stored alongside canonical code cards

The design must align with the repository's existing `zoo/` model:

- canonical code facts live in `zoo/codes/**/card.json`
- paper-conditioned claims live in `zoo/evidence/**/*.json`
- generated finite-size instances are a third source-of-truth class and must not be collapsed into either cards or evidence

## Scope

This design covers:

- project-level skill boundaries and trigger conditions
- repository-local Julia environment placement for `tensorQEC.jl`
- finite-instance storage layout under `zoo/codes/**/instances/`
- the source-of-truth contract for generated instances
- the v1 JSON format for `Hx` and `Hz`
- naming and uniqueness rules for generated instances
- validation and loading requirements in `autoqec_zoo`
- test boundaries for the v1 implementation

## V1 Supported Families

The first version supports a narrow whitelist:

- `rotated-surface-code`
- `surface-code`
- `bivariate-bicycle-code`

For the surface-code family, the workflow distinguishes `rotated` and `unrotated` layouts through interactive parameter collection.

For `bivariate-bicycle-code`, the skill supports the family only through the parameter contract exposed by the Julia adapter. The Python and skill layers do not hard-code speculative BB-code parameter names in v1.

## Non-Goals

- no support for non-`tensorQEC.jl` generators in v1
- no support for non-CSS matrix storage in v1
- no direct embedding of full matrices into canonical code cards
- no reuse of the paper-evidence schema for generated instances
- no automatic updates to `zoo/codes/**/card.json` when new instances are generated
- no requirement that v1 add a rich instance-browsing website or instance-focused markdown page
- no attempt to generalize the workflow to every code family `tensorQEC.jl` may eventually expose

## Main Decisions

### Two Separate Skills

V1 uses two project-level skills:

- `.claude/skills/setup-tensorqec/SKILL.md`
- `.claude/skills/generate-code-instance/SKILL.md`

They are intentionally separate because they serve different lifecycles:

- setup is infrequent and environment-oriented
- generation is the recurring workflow used during normal research and curation

### Repository-Local Julia Environment

The `tensorQEC.jl` environment lives under:

```text
julia/tensorqec_env/
```

This keeps Julia package state isolated from the Python package and from repo-root documentation concerns.

### Instances Live Under Code Directories

Generated finite-size instances are stored under the corresponding code entry:

```text
zoo/codes/<code-id>/instances/<instance-slug>/
```

This keeps generated instances colocated with the canonical card they refine while still preserving a clear boundary between:

- canonical card data
- paper evidence
- program-generated finite instances

### CSS Storage Only in V1

Each generated instance stores separate `Hx` and `Hz` matrices.

V1 does not store:

- a merged stabilizer matrix
- row-level Pauli labels
- non-CSS code representations

This matches the initial supported families and avoids premature generalization.

### Skill + Lightweight Python Support Layer

The workflow uses a mixed architecture:

- skills orchestrate user interaction and workflow control
- Julia scripts generate matrices and generator metadata
- Python `autoqec_zoo` code owns validation, loading, and future indexing contracts

This keeps the repository's data model in the repository codebase rather than burying it inside skill prose or Julia-only logic.

## Repository Dependencies

The design is coupled to the current repository shape:

- `.claude/skills/` for project-level skills
- `src/autoqec_zoo/` for structured-zoo loading and build logic
- `zoo/codes/**/card.json` for canonical code identities
- `zoo/schemas/` for source-of-truth JSON schemas
- `tests/` for data-contract and build-regression coverage

It also depends on a Julia toolchain being available on the user's machine.

## Directory Layout

Recommended v1 structure:

```text
.claude/
  skills/
    setup-tensorqec/
      SKILL.md
    generate-code-instance/
      SKILL.md

julia/
  tensorqec_env/
    Project.toml
    Manifest.toml
    scripts/
      setup.jl
      generate_instance.jl

zoo/
  schemas/
    code-card.schema.json
    evidence.schema.json
    code-instance.schema.json
  codes/
    surface-code/
      card.json
      instances/
        <instance-slug>/
          instance.json
          hx.json
          hz.json
    rotated-surface-code/
      card.json
      instances/
        <instance-slug>/
          instance.json
          hx.json
          hz.json
    bivariate-bicycle-code/
      card.json
      instances/
        <instance-slug>/
          instance.json
          hx.json
          hz.json
```

## Source-of-Truth Boundaries

The source-of-truth layers become:

- canonical code cards:
  - `zoo/codes/**/card.json`
- paper evidence:
  - `zoo/evidence/**/*.json`
- generated finite instances:
  - `zoo/codes/**/instances/*/instance.json`
  - `zoo/codes/**/instances/*/hx.json`
  - `zoo/codes/**/instances/*/hz.json`

Derived artifacts remain rebuildable from those source layers.

V1 does not require generated instances to appear in every derived view. The initial requirement is that the loader and build pipeline understand and validate them without corrupting the rest of the Zoo layer.

## Skill Design

### `setup-tensorqec`

#### Goal

Prepare and verify the repository-local Julia environment used by later instance-generation workflows.

#### Trigger Conditions

Use when the user asks to:

- set up `tensorQEC.jl`
- configure the Julia environment for AutoQEC
- install or verify the code-generation environment

#### Responsibilities

- check whether Julia is installed
- create or update `julia/tensorqec_env/`
- ensure `Project.toml` and `Manifest.toml` are present
- install or resolve `tensorQEC.jl` inside that environment
- run a minimal import or smoke-test script
- print a concise status summary and next step

#### Explicit Non-Responsibilities

- no instance generation
- no `zoo/` writes
- no card or evidence editing

#### Failure Conditions

Stop and report clearly when:

- Julia is missing
- package resolution fails
- `tensorQEC.jl` cannot be imported
- the smoke-test API fails

### `generate-code-instance`

#### Goal

Interactively collect supported parameters, call the Julia generator, then store a validated finite-size CSS instance under the correct `zoo/codes/<code-id>/instances/` directory.

#### Trigger Conditions

Use when the user asks to:

- generate a finite-size parity-check matrix
- create a code instance for a supported family
- store a generated surface-code or BB-code matrix in the Zoo layer

#### Responsibilities

- resolve the target code family or variant
- ask follow-up questions one step at a time when required parameters are missing
- distinguish `rotated` and `unrotated` surface-code requests
- collect family-specific parameters
- summarize the planned generation before writing files
- call the Julia generator
- write `instance.json`, `hx.json`, and `hz.json`
- refuse silent overwrite when an instance already exists
- print the created instance id, path, parameters, and matrix dimensions

#### Explicit Non-Responsibilities

- no environment installation beyond checking that setup has already succeeded
- no edits to canonical card facts
- no use of the evidence pipeline
- no unsupported-family best-effort guessing

## Interaction Model

### Surface Code

If the user says `surface code` without specifying a layout, the skill asks whether they want:

- `rotated`
- `unrotated`

Then it asks for the required finite-size parameter:

- `distance`

The resolved `code_id` becomes:

- `rotated-surface-code` for rotated
- `surface-code` for unrotated

### Bivariate Bicycle Code

The BB-code path is supported in v1, but the user-facing parameter contract is delegated to the Julia adapter.

That means:

- the skill does not hard-code speculative mathematical parameter names
- the Julia generation script must expose what parameters are required for this family
- the skill asks follow-up questions based on that declared contract

This avoids designing against guessed package APIs.

## Instance Data Model

Each instance directory contains exactly three v1 source files:

- `instance.json`
- `hx.json`
- `hz.json`

### `instance.json`

Recommended shape:

```json
{
  "id": "rotated-surface-code-d3",
  "code_id": "rotated-surface-code",
  "family_id": "surface-code",
  "title": "Rotated Surface Code d=3",
  "instance_kind": "finite_css_instance",
  "matrix_format": "dense_binary_json",
  "artifacts": {
    "hx": "hx.json",
    "hz": "hz.json"
  },
  "parameters": {
    "distance": 3,
    "layout": "rotated"
  },
  "derived_properties": {
    "n": 17,
    "kx": null,
    "kz": null,
    "mx": 8,
    "mz": 8
  },
  "provenance": {
    "generator": "tensorQEC.jl",
    "generator_env": "julia/tensorqec_env",
    "generated_at": "2026-05-28T12:00:00Z",
    "generator_script": "julia/tensorqec_env/scripts/generate_instance.jl",
    "generator_parameters": {
      "distance": 3,
      "layout": "rotated"
    }
  }
}
```

### `hx.json` and `hz.json`

Recommended v1 shape:

```json
{
  "format": "dense_binary_matrix",
  "n_rows": 8,
  "n_cols": 17,
  "data": [
    [1, 0, 0, 1, 0],
    [0, 1, 1, 0, 0]
  ]
}
```

The example data block above is illustrative only. Actual matrices must contain full rectangular binary data.

## Data Model Rules

### Instance Identity

- `id` is the canonical instance slug
- `code_id` must match the containing code directory
- `family_id` must agree with the canonical card's family relationship

### Parameters

- `parameters` stores the explicit user-input or generator-input parameters for this run
- the stored parameter set must be sufficient to reconstruct the instance slug deterministically

### Derived Properties

`derived_properties` stores stable summaries obtained from the generated result, including:

- `n`
- `mx`
- `mz`
- optional logical-qubit summaries such as `kx` and `kz` when available

V1 should not guess properties that the generator does not expose reliably.

### Provenance

Generated instances use program provenance, not literature provenance.

V1 provenance must primarily record:

- generator name
- repository-local Julia environment path
- generator script path
- generation timestamp
- normalized generator parameters

This provenance is separate from `zoo/evidence/` and should not be forced into the evidence schema.

## Naming Rules

The instance slug is derived from:

- `code_id`
- a normalized parameter summary

Examples:

- `rotated-surface-code-d3`
- `surface-code-d5`

For BB codes, the exact suffix fields must reflect the actual required parameters emitted by the Julia adapter.

Slug rules:

- lowercase ASCII only
- words separated with `-`
- deterministic for the same normalized parameter set
- unique within one `code_id`

If a target instance directory already exists, the workflow must stop and report the collision rather than overwrite it silently.

## Validation Model

V1 introduces a new schema:

```text
zoo/schemas/code-instance.schema.json
```

The Python support layer should validate:

- `instance.json` against the instance schema
- `hx.json` and `hz.json` artifact presence
- matrix dimensional consistency
- `code_id` consistency with the parent directory
- `family_id` consistency with the canonical card
- consistency between `derived_properties` and matrix sizes
- provenance presence and generator identity

## Loader and Build Integration

The `autoqec_zoo` loader should gain an instance-loading path in addition to cards and evidence.

Key rule:

- instance discovery is directory-driven, not card-driven

That means the loader finds instances through:

```text
zoo/codes/<code-id>/instances/*/instance.json
```

V1 should not require manually maintained `instance_refs` inside `card.json`.

This preserves the meaning of canonical cards as stable summaries rather than mutable inventories of generated artifacts.

The build pipeline should:

- validate instances when present
- avoid breaking existing card/evidence views
- optionally expose a minimal machine-readable instance index in a later implementation step if needed

The build pipeline does not need to surface a full instance-browse UI in v1.

## Julia Adapter Contract

The Julia generation script is the boundary between workflow orchestration and package-specific logic.

Its contract should support:

- receiving a supported `code_id`
- receiving normalized generation parameters
- returning `Hx`
- returning `Hz`
- returning derived metadata needed for `instance.json`
- exposing required parameters for code families whose input shape should not be hard-coded in the skill

For v1:

- surface-code parameter collection may be modeled directly in the skill
- BB-code parameter collection should defer to the Julia adapter's declared requirements

## Testing Strategy

The highest-value automated checks are data-contract and repository-integration tests.

### Python Tests

Add focused tests for:

- loading a valid finite instance
- rejecting missing `hx.json`
- rejecting missing `hz.json`
- rejecting mismatched `code_id`
- rejecting inconsistent matrix dimensions
- confirming normal Zoo build flows still succeed when instances are present

### Julia Smoke Tests

Add minimal generation checks for:

- rotated surface code
- unrotated surface code
- one representative bivariate-bicycle-code parameter set

The Julia tests only need to prove that the environment and generator contract work. The main regression surface remains the repository data contract.

### Workflow Coverage

V1 does not require heavy automated tests for conversational skill text.

The automation focus should stay on:

- schema validity
- loader correctness
- build compatibility
- Julia generator contract stability

## Failure Handling

The generation workflow should stop instead of guessing when:

- the user requests an unsupported family
- the Julia environment is not set up
- the adapter cannot determine required parameters
- the generator returns malformed or non-binary matrices
- the generated files would collide with an existing instance directory
- the resulting instance fails schema or consistency validation

## Migration and Future Extension

This design leaves room for later extensions without changing the v1 boundary:

- support for sparse matrix artifact formats
- richer instance indexes or browse pages
- more generator backends beyond `tensorQEC.jl`
- optional links from canonical cards to curated representative instances
- non-CSS code support with a different artifact contract

Those extensions are intentionally out of scope for the first version.

## Summary

V1 adds a narrow but coherent program-generated instance layer to AutoQEC:

- two separate project-level skills
- one repository-local Julia environment
- one finite-instance storage contract under `zoo/codes/**/instances/`
- one JSON-based `Hx`/`Hz` artifact model
- one Python validation and loader extension path

This keeps the repository aligned with its existing structured-Zoo architecture while making finite-size code generation a first-class workflow instead of an ad hoc side channel.
