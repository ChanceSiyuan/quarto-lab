# Issue 66 Quantum Tanner Witness Attachment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a batch command that attaches verified X-compatible upper-bound witnesses to generated quantum Tanner search-space candidates.

**Architecture:** A new `autoqec_search.quantum_tanner_witness_batch` module owns path resolution, candidate processing, atomic JSON writes, and summary construction. `autoqec_search.cli` exposes the module through `attach-quantum-tanner-witnesses`. Tests exercise the command through generated quantum Tanner workspaces and fake qec-code binaries.

**Tech Stack:** Python standard library, existing `autoqec_search.quantum_tanner_catalog`, `autoqec_search.upper_bound_witness_finder`, pytest, jsonschema.

## Global Constraints

Keep writes repository-relative and deterministic: `witnesses/<candidate-id>-upper-bound-witness.json`.
Preserve existing hand-authored witnesses unless `--force` is supplied.
Write witness files atomically and do not update a search-space entry until witness conversion and verification succeed.
Default mode records candidate-level skips/failures in `witness_finder_summary.json`; strict mode through `--require-all` or `--fail-on-skipped` returns nonzero for any skipped or failed candidate.
Do not treat upper-bound witnesses as exact distance evidence.

---

### Task 1: Batch Module And Core Tests

**Files:**
- Create: `src/autoqec_search/quantum_tanner_witness_batch.py`
- Modify: `tests/test_search_quantum_tanner_generator.py`

**Interfaces:**
- Consumes: `resolve_quantum_tanner_fixture_entry(root, entry, catalog_path=...)`, `run_qec_code_random_window_upper_bound(...)`, `convert_qec_code_random_window_upper_bound_result(...)`.
- Produces: `attach_quantum_tanner_witnesses(root: Path, *, campaign_id: str | None, search_space_path: Path | None, fixture_catalog_path: Path, witness_dir: Path, basis: str, qec_code_bin: str, iterations: int, restarts: int, seed: int, target_weight: int | None, timeout_seconds: float, force: bool = False, out_search_space_path: Path | None = None, summary_path: Path | None = None) -> dict[str, Any]`.

- [ ] **Step 1: Write failing success test**

Add a test that copies the generated quantum Tanner workspace to `/tmp/autoqec-generated-qt-root`, generates candidates with the existing helper, runs `attach_quantum_tanner_witnesses(...)` with a fake qec-code returning X-like random-window results, and asserts two witness files plus two `upper_bound_witness_path` fields.

- [ ] **Step 2: Run red test**

Run: `PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py::test_attach_quantum_tanner_witnesses_writes_two_witnesses_and_updates_search_space -q`
Expected: fail with missing `autoqec_search.quantum_tanner_witness_batch`.

- [ ] **Step 3: Implement module**

Implement safe repo-relative path helpers, raw catalog loading by candidate id, search-space path resolution from `--campaign` or `--search-space`, deterministic witness path construction, per-candidate attachment, atomic JSON writes, and summary counts.

- [ ] **Step 4: Run green test**

Run: `PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py::test_attach_quantum_tanner_witnesses_writes_two_witnesses_and_updates_search_space -q`
Expected: pass.

### Task 2: CLI Wiring And Negative Controls

**Files:**
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_quantum_tanner_generator.py`

**Interfaces:**
- Consumes: `attach_quantum_tanner_witnesses(...)`.
- Produces CLI command `attach-quantum-tanner-witnesses` with `--root`, `--campaign`, `--search-space`, `--fixture-catalog`, `--witness-dir`, `--out-search-space`, `--summary-out`, `--basis`, `--qec-code-bin`, `--iterations`, `--restarts`, `--seed`, `--target-weight`, `--timeout-seconds`, `--force`, `--require-all`, and `--fail-on-skipped`.

- [ ] **Step 1: Write failing CLI and negative tests**

Add a CLI success test that runs the new command, validates `/tmp/autoqec-generated-qt-root`, and checks stdout summary counts. Add strict-mode negative tests for a missing `hz.json` candidate and an incompatible Z-like fake qec-code result.

- [ ] **Step 2: Run red tests**

Run: `PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py::test_attach_quantum_tanner_witnesses_cli_updates_generated_search_space tests/test_search_quantum_tanner_generator.py::test_attach_quantum_tanner_witnesses_strict_fails_for_missing_hz_without_search_update tests/test_search_quantum_tanner_generator.py::test_attach_quantum_tanner_witnesses_strict_fails_for_incompatible_basis_without_search_update -q`
Expected: fail because the CLI command does not exist.

- [ ] **Step 3: Implement CLI**

Add parser arguments, require exactly one of `--campaign` and `--search-space`, call `attach_quantum_tanner_witnesses(...)`, print deterministic `attached/skipped/failed` counts and output paths, and return 1 in strict mode if any candidate status is not `attached`.

- [ ] **Step 4: Run green tests**

Run the three tests from Step 2 again.
Expected: pass.

### Task 3: Documentation, Full Verification, And PR

**Files:**
- Modify: `campaigns/examples/quantum-tanner-autoresearch/README.md`

**Interfaces:**
- Consumes: completed CLI command.
- Produces: operator-facing documentation for the separate witness attachment step.

- [ ] **Step 1: Update docs**

Document the command after candidate generation and before autoresearch, including default partial mode, strict mode, and the fact that witnesses are upper-bound screening inputs.

- [ ] **Step 2: Run issue verification**

Run:
`PYTHONPATH=src python3 -m pytest tests/test_search_upper_bound_witness_finder.py tests/test_search_quantum_tanner_generator.py tests/test_search_run_cli.py -q`
`PYTHONPATH=src python3 -m autoqec_search.cli validate --root /tmp/autoqec-generated-qt-root`

- [ ] **Step 3: Run repository gate**

Run: `PYTHONPATH=src python3 -m pytest`

- [ ] **Step 4: Commit and create PR**

Commit the implementation and open a PR against `main` from `agent/issue-66-m3-attach-found-witnesses-to-generated-quantum-t-run-1`.

## Self-Review

The plan covers the issue objective, default and strict exit semantics, atomic witness/search-space writes, deterministic summary records, generated `[4, 6]` success verification, and negative controls for missing `hz.json` and incompatible basis. No placeholders remain.
