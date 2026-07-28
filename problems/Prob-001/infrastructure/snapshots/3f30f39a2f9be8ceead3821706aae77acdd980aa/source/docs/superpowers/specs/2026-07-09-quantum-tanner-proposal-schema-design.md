# Quantum Tanner Proposal Schema Design

## Context

Issue #87 adds the first boundary for untrusted AI-suggested quantum Tanner candidates. The boundary is a strict, versioned JSON Schema for the explicit data later consumed by deterministic validator/materializer work: a finite group table, A/B generator indices, and GF(2) local parity-check matrices.

## Approaches Considered

1. Add only a standalone schema plus focused schema tests. This is the recommended approach because the issue is explicitly schema-level and excludes mathematical validation, materialization, API calls, benchmarks, and search strategy changes.
2. Add a Python validation helper around `jsonschema`. This would make stable error-path formatting reusable, but it adds public API surface before a caller exists.
3. Integrate proposal validation into `autoqec_search.cli validate`. This is broader than the issue because proposals are not yet committed workspace records.

## Design

Add `benchmarks/schemas/quantum-tanner-proposal.schema.json` as a Draft 2020-12 schema with top-level `additionalProperties: false`. The v1 contract requires `proposal_id`, `schema_version`, `construction_mode`, `base_group`, `a_generator_indices`, `b_generator_indices`, `local_codes`, and `provenance`; `search_hints` is optional but strictly shaped.

The schema allows only `schema_version: 1` and `construction_mode: "lr_cayley_no_cover_v1"`. `base_group` requires a nonempty name, element-order description, positive order, nonnegative identity index, and a multiplication table represented as nonempty arrays of nonnegative integer indices. The schema deliberately does not prove the table is square, closed, associative, or consistent with `order`.

Generator arrays require at least one nonnegative integer and reject duplicate indices within each array. The schema deliberately does not check symmetry, inverse closure, cross-set constraints, or index bounds against the group order.

`local_codes` requires `field: "GF(2)"`, `matrix_role: "parity_check"`, `h_a`, and `h_b`. Matrix entries are restricted to binary values, and rows must be nonempty. The schema deliberately does not enforce rectangular matrices or width compatibility with generator sets.

`provenance` is required and strict, with `source`, `model`, and `generated_at` required. `generated_at` is constrained to UTC timestamps via a regex pattern (`YYYY-MM-DDTHH:MM:SSZ`) so invalid values fail with plain Draft 2020-12 validation (without needing `FormatChecker`).

## Testing

Add `tests/fixtures/quantum_tanner_proposals/dihedral-d4-proposal.json` as a structurally valid non-toric fixture using a small dihedral group. Add `tests/test_search_quantum_tanner_proposals.py` to load the schema with `Draft202012Validator.check_schema`, validate the positive fixture, and assert rejection for missing `local_codes.field`, unknown top-level fields, unsupported construction modes, and unsupported local-code modes.

The required focused verification command should pass:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_schema_accepts_non_toric_fixture \
  tests/test_search_quantum_tanner_proposals.py::test_quantum_tanner_proposal_schema_rejects_missing_required_fields \
  -q
```

The repository validation command should still pass because this issue adds a reusable schema contract but does not register proposal files as workspace records:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```
