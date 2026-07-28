# Issue 82 Logical-X Observables Design

## Context

Issue #82 fixes the quantum Tanner upper-bound screening path. A verified X-like CSS upper-bound witness currently proves one nontrivial logical vector and supplies the distance upper bound, but screening writes that single vector as the explicit rsinter observable set. For the committed toric quantum Tanner fixtures, `k = 2`, so rsinter correctly rejects a one-row `observables.css.json`.

No matching open PR exists for this issue. The worker branch is already an isolated linked worktree, so no new worktree is created.

## Clarified Scope

This PR completes only verified X-basis witness inputs into a full logical-X observable basis before the rsinter benchmark is written. The verified witness weight remains the upper-bound distance evidence. Loaded upper-bound payload inputs keep their existing contract: they are admitted only when the candidate already has explicit `observables_x`, because a distance payload alone does not include a witness vector to seed observable completion.

Invalid witness handling stays before rsinter. A Z-like witness for a memory-X task still fails with `incompatible_upper_bound_witness_basis`; a witness outside `ker(HZ)` still fails with the verifier's existing reason such as `not_in_kernel`.

## Approaches Considered

1. Complete the witness in screening using reusable GF(2) helpers in `structure.py`.
   This keeps the contract explicit: witnesses are screening evidence, and completed observables are benchmark input. It is the selected approach because it matches the issue objective and creates reusable linear-algebra primitives.

2. Teach rsinter integration to accept incomplete observable rows and generate the remainder later.
   This is rejected because the issue explicitly says not to make rsinter accept incomplete observable sets.

3. Commit static `observables_x.json` files for the quantum Tanner fixtures.
   This is rejected because it fixes only current fixtures and leaves future verified witnesses incomplete.

## Design

Add deterministic GF(2) helpers in `src/autoqec_search/structure.py`:

- A nullspace helper that returns dense binary vectors spanning `ker(H)`.
- A quotient-basis helper that receives `kernel_rows`, `stabilizer_rows`, and a preferred verified vector, then returns exactly `k = n - rank(kernel_rows) - rank(stabilizer_rows)` dense rows.
- The preferred vector is first in the returned basis. Additional rows come from a deterministic nullspace scan and are accepted only when they increase rank modulo the stabilizer rowspace and previously selected logical rows.

The helper raises `SearchIntegrityError` when the preferred vector is not binary, has the wrong length, is outside the kernel, is in the stabilizer rowspace, or cannot be completed to the expected quotient dimension. These are integrity errors for direct helper use; screening still preserves existing verifier reasons by calling completion only after `verify_css_upper_bound_witness` passes and after basis compatibility is checked.

Update `src/autoqec_search/screening.py` so verified X-basis witnesses call the quotient helper with `kernel_rows = HZ` and `stabilizer_rows = HX`. The resulting dense rows are converted to `{"format": "sparse_rows", "num_cols": n, "rows": [...]}` for `observables_x_override`. The distance payload still comes unchanged from the witness verifier.

## Testing

Add focused tests in `tests/test_search_screening.py` that:

- Exercise the helper on the known quantum Tanner d4 fixture.
- Assert the admitted memory-X witness produces exactly two rows.
- Assert each row is in `ker(HZ)`.
- Assert the two rows are independent modulo `rowspan(HX)`.
- Keep the Z-like witness negative control and add a witness-outside-`ker(HZ)` negative control that preserves the verifier reason.

Update `tests/test_search_quantum_tanner_run_gating.py` so the fake rsinter expects two explicit logical observables for the admitted d4 candidate, and the run manifest records `logical_observable_count = 2`.

Verification commands:

```bash
PYTHONPATH=src pytest tests/test_search_screening.py tests/test_search_quantum_tanner_run_gating.py -k "logical_observable_basis or upper_bound_candidate_admits_x_witness"
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m pytest
```

## Approval

This is a non-interactive Agent Desk run. Under the standing answer policy, the conservative in-code quotient-basis design is approved because it implements the issue objective directly, preserves existing rejection reasons, and avoids broad unrelated changes.
