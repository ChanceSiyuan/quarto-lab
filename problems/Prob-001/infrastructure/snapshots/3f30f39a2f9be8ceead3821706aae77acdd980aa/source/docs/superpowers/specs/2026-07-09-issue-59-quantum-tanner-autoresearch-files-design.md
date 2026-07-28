# Issue 59 Quantum Tanner Autoresearch Files Design

## Context

Issue #59 completes the generated quantum Tanner candidate path by emitting the
two autoresearch inputs already consumed by the search layer:
`fixture_catalog.json` and `search_space.json`. The existing sweep generator can
normalize a sweep config, write quantum Tanner specs, write a distance-ladder
manifest, and optionally materialize `instance.json`, `hx.json`, and `hz.json`
through the distance-ladder exporter. The catalog validator from #55 can already
validate non-default generated catalog paths, but workspace validation currently
only validates the default committed smoke catalog path.

## Scope

The generator will convert materialized candidate instance directories into:

- A configured fixture catalog at `QuantumTannerSweepConfig.catalog_path`.
- A configured explicit-list search space at
  `QuantumTannerSweepConfig.search_space_path`.

The emitted search-space candidate specs will reference the configured catalog
path through `fixture_catalog_path`, omit upper-bound witness fields, and be
ordered by distance then candidate id. Workspace validation will validate each
quantum Tanner `fixture_catalog_path` referenced by loaded search spaces, so a
generated workspace validates the same catalog the generated search space
consumes.

Out of scope: running autoresearch, rbposd, surface-copy comparison, witness
finding, or adding upper-bound witness records.

## Data Shape

Each catalog entry is derived from the normalized candidate plus its
materialized `instance.json`:

- `candidate_id`, `code_id`, `n`, `k`, and `distance` come from the candidate
  and source instance.
- `hx`, `hz`, `source_fixture_path`, and `source_instance` point at the
  generated instance directory artifacts.
- `provenance` preserves `qec_code_spec`, `quantum_tanner_spec`, generator,
  construction mode, and base group when available.
- `search_ready` is `true` only when `instance.json`, `hx.json`, and `hz.json`
  are present and pass the existing catalog validator.
- `adaptation` remains `catalog-normalized-finite-css-instance`.

The search space has `mode: "explicit_list"` and one catalog-backed candidate
spec per catalog entry. Candidate specs contain `candidate_id`, `code_family`,
`fixture_catalog_path`, and minimal provenance `{kind, label}`.

## Validation

Emission will fail before writing catalog/search-space files if a candidate is
missing a materialized artifact. This keeps missing `hz.json` and similar
partial-generation states from becoming search-ready candidates.

The CLI workspace validator will collect catalog paths from loaded search
spaces and call `validate_quantum_tanner_fixture_catalog()` for each distinct
path. This covers generated catalog paths as well as the committed default
catalog, and it makes `validate --root <generated-root>` fail on missing
artifacts referenced by the emitted catalog.

## Testing

Tests will follow TDD and cover:

- Generated catalog/search-space files for a `[4, 6]` sweep after materializing
  fake quantum Tanner instances.
- Deterministic order by distance and candidate id.
- Search-space schema compatibility and catalog-backed specs without witness
  fields.
- `resolve_quantum_tanner_fixture_entry()` for both generated entries.
- Workspace validation of the emitted `fixture_catalog_path`.
- Negative control: deleting one generated `hz.json` before emission or
  validation fails with a missing artifact error.
