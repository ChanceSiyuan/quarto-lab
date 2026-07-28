# Issue 44 Quantum Tanner Upper-Bound Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate quantum Tanner autoresearch candidates by verified upper-bound witnesses before running rbposd at exactly `p=0.001`.

**Architecture:** Add a runnable quantum Tanner campaign/search space backed by the existing fixture catalog. Add a screening helper used only by the quantum Tanner p001 run path, write per-candidate `screening.json`, pass admitted upper-bound payloads into evaluation, and surface screening state in loaders/reports.

**Tech Stack:** Python 3, pytest, JSON schemas/artifacts, existing `autoqec_search.run_loop`, `autoqec_search.eval_run`, `autoqec_search.report`, `autoqec_search.quantum_tanner_catalog`, and `autoqec_search.structure` verifier.

## Global Constraints

- `screening.json` fields are exactly the issue-facing fields: `screening_status`, `distance_bound_type`, `distance_upper_bound`, and `reason`.
- `screening_status` values are `admitted`, `skipped`, or `failed`.
- Admitted quantum Tanner candidates run only through `quantum-tanner-rbposd-p001-v1` at exactly `p=0.001`.
- Admitted Tanner manifests record `logical_failure_aggregation: "any_logical"` when explicit logical observables are used.
- Skipped and failed candidates remain visible in run logs and report models.
- Keep `candidate.json` schema-valid; do not add a new candidate status.
- Do not add SLURM execution, new decoders, or Zoo promotion.
- Focused verification command must print `5 passed`: `PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_run_gating.py`.
- Workspace validation must pass: `PYTHONPATH=src python3 -m autoqec_search.cli validate --root .`.
- Full verification must pass: `PYTHONPATH=src python3 -m pytest`.

---

## File Structure

- Create `tests/test_search_quantum_tanner_run_gating.py`: five issue-level red/green tests with fake rsinter.
- Create `campaigns/examples/quantum-tanner-autoresearch/campaign.json`: runnable campaign.
- Create `campaigns/examples/quantum-tanner-autoresearch/search_space.json`: three catalog-backed candidates with d4 valid witness, d6 missing payload, d8 invalid witness.
- Create `campaigns/examples/quantum-tanner-autoresearch/witnesses/*.json`: committed witness payloads.
- Modify `benchmarks/schemas/search-space.schema.json`: optional catalog-backed candidate kind and upper-bound input fields.
- Create `src/autoqec_search/screening.py`: screening decision logic and artifact validation helpers.
- Modify `src/autoqec_search/eval_run.py`: optional `distance_payload_override` and optional explicit observables injection.
- Modify `src/autoqec_search/run_loop.py`: resolve catalog candidates, gate quantum Tanner p001 runs, resume skipped/failed candidates, and extend run-log statuses.
- Modify `src/autoqec_search/load.py`: require and validate `screening.json` for quantum Tanner p001 runs.
- Modify `src/autoqec_search/report.py`: add per-candidate screening payloads to the report model.
- Modify `src/autoqec_search/run_render.py`: render `skip` and `fail` run-log statuses.
- Modify inventory tests that assert campaign counts/lists.

---

### Task 1: Write Failing Gating Tests

**Files:**
- Create: `tests/test_search_quantum_tanner_run_gating.py`

**Interfaces:**
- Consumes: `run_autoresearch`, `build_report_model`, CLI validate.
- Produces: failing tests that describe the #44 behavior before implementation.

- [ ] Write tests that copy the repo into a temp git repo, monkeypatch fake rsinter, run `quantum-tanner-autoresearch`, and assert admitted/skipped/failed screening artifacts.
- [ ] Include a fake rsinter writer that records the spec path and emits exactly one JSONL row at `p=0.001` with explicit observable metadata.
- [ ] Run `PYTHONPATH=src python3 -m pytest -q tests/test_search_quantum_tanner_run_gating.py` and confirm failure because campaign/gating does not exist yet.

### Task 2: Add Campaign And Schema Inputs

**Files:**
- Create: `campaigns/examples/quantum-tanner-autoresearch/campaign.json`
- Create: `campaigns/examples/quantum-tanner-autoresearch/search_space.json`
- Create: `campaigns/examples/quantum-tanner-autoresearch/witnesses/quantum-tanner-toric-d4-upper-bound-witness.json`
- Create: `campaigns/examples/quantum-tanner-autoresearch/witnesses/quantum-tanner-toric-d8-invalid-witness.json`
- Modify: `benchmarks/schemas/search-space.schema.json`
- Modify: `tests/test_search_cli.py`
- Modify: `tests/test_search_load.py`

**Interfaces:**
- Produces: a schema-valid campaign with candidate-level upper-bound witness inputs.

- [ ] Add the campaign using suite `quantum-tanner-rbposd-p001-v1`, fixed seed 7, and max candidates 3.
- [ ] Add three catalog-backed candidate specs using `fixture_catalog_path`.
- [ ] Put the valid d4 X witness vector at columns `[0, 1, 8, 12]`.
- [ ] Put the invalid d8 X witness vector with column `[0]`.
- [ ] Extend the schema so catalog-backed candidates and upper-bound inputs validate.
- [ ] Update workspace inventory expectations from 5 to 6 campaigns and include `quantum-tanner-autoresearch`.

### Task 3: Implement Screening And Evaluation Wiring

**Files:**
- Create: `src/autoqec_search/screening.py`
- Modify: `src/autoqec_search/eval_run.py`
- Modify: `src/autoqec_search/run_loop.py`
- Modify: `src/autoqec_search/run_render.py`

**Interfaces:**
- Produces: `screen_upper_bound_candidate`, `screening.json` writer, admitted evaluation override, skipped/failed run rows.

- [ ] Add screening decisions for valid witness, missing input, invalid witness, and upper-bound payload loading.
- [ ] Add optional `distance_payload_override` and `observables_x_override` to `evaluate_resolved_candidate_into_run`.
- [ ] In `run_autoresearch`, apply screening only when suite id is `quantum-tanner-rbposd-p001-v1`.
- [ ] For admitted candidates, write `screening.json`, attach explicit X observables, and evaluate with the verifier distance payload.
- [ ] For skipped/failed candidates, write `screening.json`, keep schema-valid placeholder/crash artifacts, append visible rows, and do not call rsinter.
- [ ] Update resume logic so skipped/failed screening artifacts are terminal.
- [ ] Extend run-log status rendering/counting for `skip` and `fail`.

### Task 4: Loader And Report Surfacing

**Files:**
- Modify: `src/autoqec_search/load.py`
- Modify: `src/autoqec_search/report.py`

**Interfaces:**
- Produces: workspace validation for quantum Tanner screening artifacts and `model["candidates"][i]["screening"]`.

- [ ] Validate required screening fields for quantum Tanner p001 runs.
- [ ] Check statuses, bound types, upper-bound positivity for admitted candidates, and reasons for all decisions.
- [ ] Add optional screening payloads to report candidate records.

### Task 5: Verification, Review, Commit, PR

**Files:**
- All touched files.

**Interfaces:**
- Produces: verified branch and pull request.

- [ ] Run `PYTHONPATH=src pytest -q tests/test_search_quantum_tanner_run_gating.py` and confirm `5 passed`.
- [ ] Run `PYTHONPATH=src python3 -m autoqec_search.cli validate --root .`.
- [ ] Run `PYTHONPATH=src python3 -m pytest`.
- [ ] Run `git diff --check`.
- [ ] Request/perform code review and fix important findings.
- [ ] Commit, push the worker branch, and create a pull request that closes #44.

## Self-Review

The plan covers the issue's required inputs, outputs, report visibility, p=0.001 guard, logical aggregation, schema validity, and validation command. No placeholders remain. Function names and artifact fields match the design.
