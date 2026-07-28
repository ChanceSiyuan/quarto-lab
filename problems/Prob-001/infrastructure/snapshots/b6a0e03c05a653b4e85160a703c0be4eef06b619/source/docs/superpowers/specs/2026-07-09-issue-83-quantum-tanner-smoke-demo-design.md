# Issue 83 Quantum Tanner Smoke Demo Design

## Context

Issue #83 asks for a repeatable `quantum-tanner-autoresearch` smoke demo that a clean checkout can run end to end. The existing campaign pieces are present: candidate generation emits d4/d6, witness attachment can produce X-basis upper-bound witnesses, autoresearch writes the run notebook and report, and `compare-surface-copy` writes JSON/HTML against `benchmarks/baselines/rotated-surface-single-logical-p001.json`.

The dependency PRs are merged: PR #84 fixes rbposd result-only defaults for issue #81, and PR #85 completes quantum Tanner logical-X observables for issue #82. The worker branch is already an isolated linked worktree, so no nested worktree is needed.

## Clarified Scope

This PR adds a repo-level smoke path, not a broader search campaign. The default demo uses the committed small p=0.001 task with `max_shots = 64` and `css_memory.seed = 12345`, and expects the generated d4 and d6 Tanner candidates to have zero observed logical errors in that budget.

The smoke path must leave the caller's checkout clean. It can copy or clone the checkout into `--work-root`, run the generated campaign there, and report the artifact paths from that isolated checkout. The output directory must contain the finalized autoresearch run artifacts plus `surface-copy-comparison.json` and `surface-copy-comparison.html`.

The negative control must intentionally run a k=2 quantum Tanner candidate with only one explicit X observable row and verify the exact rejection text:

```text
explicit X observables define 1 rows, expected k = 2
```

## Approaches Considered

1. Add `scripts/smoke_quantum_tanner_autoresearch.sh` as the main interface and keep orchestration in shell.
   This is selected because the issue recommends a script, the existing commands already expose the needed behavior, and the script can be run from a clean checkout without creating new Python public APIs.

2. Add a new `autoqec_search.cli smoke-quantum-tanner-autoresearch` command.
   This would be easier to unit test as Python, but it would add another CLI surface for orchestration that is mostly command composition. That is broader than needed for this smoke demo.

3. Commit a static known-good smoke run under `results/search/`.
   This would provide evidence, but it would not prove a clean checkout can regenerate the evidence. It also risks fossilizing one local run instead of documenting the reproducible path.

## Design

Add `scripts/smoke_quantum_tanner_autoresearch.sh` with these modes:

- Default mode: clone the current checkout into `--work-root/checkout`, configure a local git identity, build `target/debug/autoqec-distance-ladder` if needed, generate d4/d6 candidates, attach X witnesses, validate the checkout, run autoresearch with `--run-id qt-smoke`, create the surface-copy comparison, verify required JSON fields, and print a concise PASS summary.
- `--check-bad-observables`: create the isolated checkout, synthesize a one-candidate d4 payload with one explicit X observable row, run autoresearch, and require the expected k-row rejection text.
- `--keep-existing-work-root`: allow reusing an existing work root for local debugging. Default behavior refuses a populated work root so stale evidence cannot be mistaken for a fresh smoke run.

The script reads `QEC_CODE_BIN` and `RSINTER_BIN`. `QEC_CODE_BIN` is passed to generation, witness attachment, and run distance-method options. `RSINTER_BIN` is prepended to `PATH` by its containing directory so `autoqec_search.cli run` resolves the intended decoder backend.

The script verifies:

- `run_status.json.status == "finalized"`
- `run_status.json.frontier_size == 2`
- `experiment-log.tsv` contains no `crash` rows
- `frontier.json` contains `quantum-tanner-toric-d4` and `quantum-tanner-toric-d6`
- each frontier item has `p = 0.001` and `ler = 0`
- the surface-copy comparison JSON has `status: ok`, two rows, one accepted row, and one rejected row

Add a small Python guard in `src/autoqec_search/eval_run.py` before writing explicit CSS observables. When explicit X observables are emitted for a CSS task and the summarized CSS structure has positive integer `k`, the row count must equal `k`. A mismatch raises `SearchIntegrityError` with the exact negative-control message. This keeps the smoke control deterministic and avoids relying on backend-specific rsinter diagnostics.

Extend the search-space schema so explicit `instance_path` candidates may carry `upper_bound_payload` or `upper_bound_payload_path`, matching the existing catalog-backed upper-bound screening inputs. The negative control uses that narrow path because catalog-backed candidates intentionally normalize fixture artifacts and do not load ad hoc `observables_x.json` files.

Update `campaigns/examples/quantum-tanner-autoresearch/README.md` with the single smoke command, the fixed seed/shot count, expected PASS lines, artifact paths, and the negative-control mode.

## Testing

Add focused tests that follow TDD:

- A unit test for `evaluate_resolved_candidate_into_run` that supplies one explicit X observable row for a synthetic `k=2` CSS candidate and asserts the exact rejection message before fake `rsinter` can run.
- A script smoke test using fake `qec-code`, fake `autoqec-distance-ladder`, and fake `rsinter` binaries so the script can exercise its orchestration and PASS parsing without external tool availability.
- A script negative-control test that uses the same fakes and asserts `--check-bad-observables` prints `negative_control=ok`.

Final verification still runs the repo gate requested by Agent Desk:

```bash
PYTHONPATH=src python3 -m pytest
```

If real `qec-code` and `rsinter` are available, also run:

```bash
QEC_CODE_BIN=$(command -v qec-code) RSINTER_BIN=$(command -v rsinter) scripts/smoke_quantum_tanner_autoresearch.sh --work-root /tmp/autoqec-qt-smoke
```

## Approval

This is a non-interactive Agent Desk run. Under the standing answer policy, the shell harness with a narrow Python k-row guard is approved because it matches the issue interface, preserves the existing campaign commands, and gives the required negative control a deterministic repository-owned error.
