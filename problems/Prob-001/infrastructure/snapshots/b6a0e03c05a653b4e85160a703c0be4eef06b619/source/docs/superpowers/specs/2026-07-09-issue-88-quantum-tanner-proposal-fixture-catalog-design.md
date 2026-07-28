# Issue 88 Quantum Tanner Proposal Fixture Catalog Design

Issue: #88, "Add a quantum Tanner proposal fixture catalog"

## Context

Issue #87 added the strict v1 JSON Schema for untrusted quantum Tanner AI
proposal objects at `benchmarks/schemas/quantum-tanner-proposal.schema.json`.
The next layer needs offline known-answer proposal fixtures so validation,
materialization, and ingestion tests can reuse the same examples without
generating AI output during tests.

The catalog in this issue is a schema-level yardstick. It records which JSON
proposal files are expected to pass or fail Draft 2020-12 schema validation,
and why. It deliberately does not prove group laws, materialize a CSS code,
run `qec-code`, evaluate rbposd, or call an AI service.

## Clarifying Decisions

Because this Agent Desk run is non-interactive, these decisions are resolved
from the issue text and nearby repository patterns.

1. The catalog lives at `tests/fixtures/quantum_tanner_proposals/catalog.json`.
2. The catalog entries use repo-relative fixture paths.
3. Each entry records `fixture_id`, `path`, `provenance`, `expected_status`,
   and `expected_error_kind`; invalid entries also record an
   `expected_error_pointer` to make the intended failure hand-reviewable.
4. The valid catalog fixture is non-toric at the proposal level and marks
   `"non-toric"` in `search_hints.tags`.
5. A focused pytest helper is the repository-local checker for this issue.
   The CLI validation command remains unchanged and is run as a regression
   check.

## Approaches Considered

Recommended: add the catalog and a focused checker in
`tests/test_search_quantum_tanner_proposals.py`. This is the narrowest fit for
the issue because it validates the catalog against the existing schema, keeps
the fixture contract close to the schema tests, and avoids adding public
runtime API before deterministic proposal validation exists.

Alternative: add a production module under `src/autoqec_search/` for proposal
fixture catalog loading. This would be easier to import from future runtime
code, but it creates API surface before any runtime consumer exists.

Alternative: wire proposal catalog validation into
`python3 -m autoqec_search.cli validate --root .`. This makes the catalog part
of workspace validation, but proposals are still test fixtures rather than
committed workspace records, so this is broader than the requested
schema-level fixture yardstick.

## Architecture

`tests/fixtures/quantum_tanner_proposals/catalog.json` is the durable fixture
index. It has `catalog_id`, `schema_version`, `schema_path`, and an `entries`
array. Each entry points to one JSON proposal fixture and records provenance
centrally:

- valid entry: `valid-dihedral-d3.json`, a small non-toric dihedral proposal.
- invalid entry: `invalid-missing-local-codes.json`, missing the required
  top-level `local_codes` object.
- invalid entry: `invalid-bad-field.json`, using unsupported
  `local_codes.field: "GF(4)"`.

The checker in `tests/test_search_quantum_tanner_proposals.py` loads the
catalog, checks catalog shape, resolves all paths under the repository root,
loads each fixture, validates it with `Draft202012Validator`, and compares the
actual schema verdict with the catalog's expected verdict.

For valid fixtures, the checker requires schema success and counts a fixture as
non-toric when `"non-toric"` appears in `search_hints.tags`. For invalid
fixtures, the checker requires schema failure, compares
`ValidationError.validator` with `expected_error_kind`, and compares the JSON
pointer with `expected_error_pointer` when present.

Any mismatch raises an assertion whose message contains
`fixture verdict mismatch`, matching the required negative-control test.

## Testing

Add two required catalog tests to
`tests/test_search_quantum_tanner_proposals.py`:

1. `test_quantum_tanner_proposal_fixture_catalog_is_complete` runs the checker
   against the committed catalog and asserts at least one schema-valid non-toric
   proposal and at least two schema-invalid fixtures.
2. `test_quantum_tanner_proposal_fixture_catalog_detects_bad_expected_verdict`
   deep-copies the catalog, mutates one entry's expected verdict inside the
   test, and asserts the checker fails with `fixture verdict mismatch`.

The focused verification command should pass:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_fixture_catalog_is_complete \
  tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_fixture_catalog_detects_bad_expected_verdict \
  -q
```

The workspace validation command should still pass:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

The branch verification also runs the full pytest suite requested by the
Agent Desk instructions:

```bash
PYTHONPATH=src python3 -m pytest
```

## Out of Scope

No finite-group law validation, proposal materialization, rbposd evaluation,
live AI calls, or workspace CLI proposal registration is added in this issue.
