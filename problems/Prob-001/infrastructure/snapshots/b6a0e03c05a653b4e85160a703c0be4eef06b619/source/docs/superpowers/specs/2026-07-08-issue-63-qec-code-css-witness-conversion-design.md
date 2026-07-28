# Issue 63 qec-code CSS Witness Conversion Design

## Context

Issue #63 builds on the merged #61 witness fixture catalog and #62 qec-code random-window wrapper. The wrapper already executes `qec-code code css-distance random-window-upper-bound --json` and validates basic result shape. The missing piece is a checked conversion from qec-code's Pauli-style witness payload into AutoQEC's CSS upper-bound witness payload:

```json
{"basis": "x", "vector": [0, 0, 1, 1]}
```

The conversion must be lossless for pure CSS observables, must reject mixed observables, and must call `verify_css_upper_bound_witness()` against the same `hx` and `hz` before returning an AutoQEC distance payload.

## Approaches Considered

1. Add conversion helpers to `autoqec_search.upper_bound_witness_finder` and reuse the existing qec-code validation path.
   This is the chosen approach because the module already owns qec-code result contracts, command execution, and `SearchIntegrityError` reporting.

2. Create a new `qec_code_witness_conversion.py` module.
   This would isolate the converter but would split one small contract across two modules before there is a second caller.

3. Convert at each future call site after `run_qec_code_random_window_upper_bound()`.
   This would make the JSON contract easy to misuse and would duplicate rejection logic.

## Design

`upper_bound_witness_finder.py` will expose a converter that accepts a completed qec-code random-window result plus the matching `hx` and `hz` matrix payloads. It will first validate the qec-code payload, then map `logical_class` to an AutoQEC basis:

- `x_like` selects `witness.x` and produces `{"basis": "x", "vector": witness.x}`.
- `z_like` selects `witness.z` and produces `{"basis": "z", "vector": witness.z}`.
- Legacy fixture spellings `x` and `z` are not accepted by the production converter; fixtures that test other malformed conditions use `x_like` or `z_like` so the intended rejection reason remains specific.
- `mixed` and all other classes are rejected.

For the CSS witness contract, the selected vector must be nonzero, the complementary Pauli component must be all zero, `x` and `z` widths must match, all witness entries must be plain binary integers, and `upper_bound` must equal `witness.weight`. A result with nonzero support in both Pauli components is rejected as mixed-observable input, not converted by silently dropping one side.

After selecting the basis and vector, the converter calls `verify_css_upper_bound_witness(hx, hz, witness_payload)`. A failing verifier result raises `SearchIntegrityError` with the verifier reason. A passing verifier result returns:

- `witness_payload`: the AutoQEC CSS witness JSON payload.
- `distance_payload`: the verifier-produced payload compatible with `css-upper-bound-witness`.
- `verification`: the complete verifier result for diagnostics.
- `qec_code_result`: a sidecar copy of the original qec-code result so provenance, options, and optional `search_stats` remain available.

The existing runner will continue returning the raw qec-code payload. A new convenience function will run qec-code and immediately convert/verify the result for callers that want AutoQEC-ready output.

## Error Handling

All conversion failures raise `SearchIntegrityError`. The error reasons stay stable and machine-readable where fixtures already define them: `unsupported_logical_class`, `non_binary_witness_entry`, `x_z_width_mismatch`, `upper_bound_weight_mismatch`, and `missing_witness`. New conversion-specific failures use similarly direct reasons such as `selected_witness_vector_zero`, `nonzero_complementary_pauli_support`, and `invalid_css_upper_bound_witness: <reason>`.

No witness JSON file is written by the converter. Callers only receive a payload after validation and verifier success, so negative controls cannot produce a witness artifact through this API.

## Testing

Tests will be added before production code. The focused tests cover:

- X-like qec-code fixture conversion to `{"basis": "x", "vector": [...]}` and matching `css-upper-bound-witness` distance payload.
- Z-like qec-code fixture conversion to `{"basis": "z", "vector": [...]}` and matching verifier output.
- Preservation of `search_stats` and provenance in the sidecar result.
- Rejection of `mixed`, non-binary entries, width mismatch, nonzero complementary Pauli support, `upper_bound != witness.weight`, zero selected vector, and verifier failure.
- Runner convenience coverage using the fake qec-code executable.

Required verification:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness_finder.py tests/test_search_upper_bound_witness.py -q
PYTHONPATH=src python3 -m pytest
```

## Scope

This design does not choose a quantum Tanner benchmark basis, does not edit campaign search spaces, and does not add mixed-observable support.

## Approval

Approved automatically for this non-interactive Agent Desk run under the Standing Answer Policy. The issue body provides the full contract and verification requirements, so no user clarification is needed.
