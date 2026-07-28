# Quantum Tanner Partial-Witness Continuation Design

## Context

The long-running Quantum Tanner launcher currently invokes
`find-upper-bound-witness --basis x` sequentially for every proposal-derived
candidate. Any nonzero candidate result raises `SearchIntegrityError` and
aborts the attempt before observable completion or the numerical run. A valid
generic Z-like witness therefore prevents unrelated candidates from reaching
the p=0.001 rbposd benchmark.

## Chosen Behavior

Treat witness discovery as a candidate-level gate:

- attach the witness path only when the candidate command succeeds;
- record candidate failures in a deterministic witness summary and continue;
- preserve failed candidates in the search space without a witness path;
- skip observable completion for proposal candidates without a witness;
- let the existing run-loop screening record those candidates as
  `missing_upper_bound_payload`;
- exclude placeholder/skipped candidates with no completed LER point from the
  surface-copy comparison without requiring computed structure fields;
- continue to the numerical run when at least one candidate has a compatible
  witness;
- fail the attempt clearly when no candidate has a compatible witness.

This preserves scientific meaning: a Z-like witness is not relabeled as an
X-like witness, and upper bounds remain screening evidence rather than exact
distance evidence.

## Alternatives

1. Remove failed candidates from the search space. This is smaller but loses
   screening visibility and feedback for later proposal rounds.
2. Add an X-only search option to `qec-code`. This may be useful separately,
   but it changes the backend contract and is unnecessary for allowing other
   candidates to run.
3. Keep failed candidates and use the existing missing-witness screening path.
   This is selected because it preserves candidates, reports the failure, and
   reuses established run-loop semantics.

## Data and Error Handling

The attempt writes `witness_finder_summary.json` beside the generated witness
files. Each candidate record contains its id, `attached` or `failed` status,
reason, witness path when attached, and log path. Counts report attached and
failed candidates. Malformed candidate metadata remains an attempt-level
error; only failures from the candidate witness command are isolated.

Observable completion skips only an absent witness-path field. An explicit
`null`, a malformed present path, or an invalid witness remains an error.

## Verification

- A regression test proves that one witness command failure does not prevent
  later candidates from being attempted and that the summary/search space
  contain the correct mixed outcome.
- An observable-completion regression test proves that missing-witness
  proposal candidates are skipped while witnessed candidates are completed.
- A surface-copy regression test proves that placeholder candidates with
  `structure.n/k = null` are ignored while completed candidates are compared.
- Existing focused suites and the long-run smoke contracts remain green.
- The interrupted four-candidate attempt is continued manually from its
  materialized checkout so D12/D4/D8 can reach rsinter without spending a new
  Codex proposal round.
