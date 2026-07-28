# Issue 67 Quantum Tanner Witness-To-Autoresearch Design

## Context

Issue #67 completes the operator-facing path that starts with generated
quantum Tanner candidates, attaches upper-bound witnesses, validates the
workspace, and then runs the existing `p=0.001` rbposd autoresearch campaign.
The generator from issue #60, the X-like screening policy from issue #64, and
the batch witness attachment command from issue #66 are already merged.

The current workflow README documents most individual steps, but it does not
yet keep the complete candidate-generator-to-witness-finder-to-autoresearch
path under a single tested guardrail. It also needs to make the single-candidate
witness command, installed command names, X-like basis requirement, and
partial-failure inspection files explicit for a cold operator.

## Chosen Approach

Update `campaigns/examples/quantum-tanner-autoresearch/README.md` in place and
extend `tests/test_search_docs.py`. The README remains the one local workflow
entry point; the tests assert the workflow retains the required command blocks
and scientific warnings.

This is intentionally documentation and test work only. It does not change
witness-finder behavior, run a long benchmark, or add cluster execution.

## Alternatives Considered

1. Add a new nearby workflow document. This would avoid editing the existing
   README, but it would split the quantum Tanner operator path across files.
2. Add inline comments to the CLI modules. This would help implementers, but
   issue #67 asks for a cold operator workflow that does not require reading
   implementation code.
3. Extend the existing README and docs tests. This is selected because it
   keeps the workflow discoverable beside the campaign files and matches the
   issue's recommended file.

## Documentation Requirements

The workflow must show these source-checkout commands:

- `generate-quantum-tanner-candidates` dry run and materializing run;
- `find-upper-bound-witness` for one candidate, including `--timeout-seconds`;
- `attach-quantum-tanner-witnesses` for the generated batch, including
  `--timeout-seconds`, `--require-all`, and `--fail-on-skipped`;
- `validate --root .`;
- `run --campaign quantum-tanner-autoresearch` with
  `--distance-method random-window-upper-bound`;
- inspection of `witness_finder_summary.json` and candidate `screening.json`
  files after partial attachment or screening skips/failures;
- `compare-surface-copy` after benchmarks complete.

The workflow must also name the installed `autoqec-search` forms where useful,
so installed users can map the source-checkout commands to their environment.

## Scientific Guardrails

The README and docs tests must preserve these statements:

- upper-bound witnesses are screening evidence only;
- upper-bound witnesses and upper-bound distances must not be promoted as
  exact Zoo distance evidence;
- the current `p=0.001` memory-X quantum Tanner screening path admits generated
  witnesses directly only when they are X-like;
- Z-like witnesses can be valid generic CSS witnesses, but they are
  incompatible with this memory-X screening task.

## Test Strategy

Extend `tests/test_search_docs.py` rather than adding command execution tests.
The commands already have functional coverage in generator and witness-finder
tests; issue #67 specifically needs docs guardrails. The docs tests should
fail if the workflow omits candidate generation, single-candidate witness
finding, batch witness attachment, validation, autoresearch, screening
inspection, surface-copy comparison, the exact-distance warning, the X-like
basis requirement, or the summary/screening files used to inspect partial
attachment outcomes.

## Approval

This design is auto-approved under the Agent Desk Standing Answer Policy. The
chosen approach is the conservative option: update the named workflow document
and tests, avoid behavioral changes, and keep long benchmark or cluster work
out of scope.
