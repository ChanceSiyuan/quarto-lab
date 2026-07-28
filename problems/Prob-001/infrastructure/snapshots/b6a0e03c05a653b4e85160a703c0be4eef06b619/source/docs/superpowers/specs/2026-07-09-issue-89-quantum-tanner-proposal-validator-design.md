# Issue 89: Quantum Tanner Proposal Validator Design

## Goal

Add a deterministic validator for schema-valid quantum Tanner AI proposal JSON
files before any proposal is materialized or benchmarked. The validator treats
the proposal as untrusted input and must fail fast on oversized finite groups
before doing cubic associativity checks.

## Scope

The validator accepts one proposal JSON file that conforms to
`benchmarks/schemas/quantum-tanner-proposal.schema.json` and an optional maximum
group order. It returns a normalized validation summary on success, or a typed
rejection on failure. It does not materialize `hx` or `hz`, run decoders, call
external algebra systems, use network access, or depend on `qec-code`, `rsinter`,
GAP, Oscar, qLDPC, or Julia.

## Architecture

Add `src/autoqec_search/quantum_tanner_proposals.py` as a focused pure-Python
module. It will expose:

- `validate_quantum_tanner_proposal_file(path, max_group_order=32)` for CLI and
  tests.
- `validate_quantum_tanner_proposal(payload, max_group_order=32)` for in-memory
  callers.
- `QuantumTannerProposalValidationError` with typed subclasses for the issue
  contract: `GroupOrderLimitExceeded`, `InvalidGroupTable`,
  `NonSymmetricGeneratorSet`, `InvalidLocalCodeMatrix`,
  `LocalCodeWidthMismatch`, and `KnownToricTemplateDuplicate`.

The existing `autoqec_search.cli` parser gets a thin
`validate-quantum-tanner-proposal` command that loads a file, delegates to the
module, prints a `PASS quantum_tanner_proposal proposal_id=...` line plus a
stable JSON summary, and returns nonzero with the typed error name on rejection.

## Validation Flow

1. Check the declared group order and multiplication table are consistent,
   rectangular, and in range.
2. Enforce `max_group_order` before associativity so oversized inputs cannot
   trigger cubic work.
3. Verify identity laws and inverses for every group element.
4. Verify associativity only after the order guard passes.
5. Validate A/B generator coordinate lists for range, duplicates, and inverse
   symmetry while preserving the user-provided coordinate order.
6. Validate local-code matrices as nonempty rectangular GF(2) matrices.
7. Require `h_a` width to equal `|A|` and `h_b` width to equal `|B|`.
8. Reject obvious toric-template duplicates by comparing canonical construction
   invariants against the committed quantum Tanner toric fixture pattern rather
   than relying on proposal labels.
9. Build a normalized summary and SHA-256 fingerprint from canonical validated
   content only.

## Fixture Plan

Reuse the proposal fixture directory from issue 88. The existing
`valid-dihedral-d3` fixture will be adjusted so its generator sets are closed
under inverses and its local-code widths match those generator coordinates.
Additional semantic negative fixtures will cover a bad group table,
nonsymmetric generators, local-code width mismatch, a known toric duplicate,
and an oversized table whose multiplication law is intentionally not fully
validated after the order guard.

## Testing

Add focused tests to `tests/test_search_quantum_tanner_proposals.py` for the six
issue cases. The positive test asserts stable summary fields and a stable
fingerprint. Negative tests assert typed rejection names rather than generic
messages. The oversized test monkeypatches or otherwise guards associativity to
prove `GroupOrderLimitExceeded` is returned before full associativity work.

Also verify the CLI manually on the valid, toric-duplicate, and oversized
fixtures, and run the full repository test suite with `PYTHONPATH=src python3 -m
pytest`.

## Self-Review

- No placeholders or open requirements remain.
- The design keeps semantic validation separate from JSON Schema validation.
- The order guard is explicitly before cubic associativity.
- The success fingerprint excludes file paths, timestamps outside the proposal
  content, and output directories.
- The scope is limited to proposal validation and CLI reporting.
