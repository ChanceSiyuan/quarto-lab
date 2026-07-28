# Issue 83 Quantum Tanner Smoke Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repeatable quantum Tanner autoresearch smoke script that emits PASS/FAIL evidence plus a deterministic incomplete-observables negative control.

**Architecture:** Keep orchestration in `scripts/smoke_quantum_tanner_autoresearch.sh`, using the existing candidate generation, witness attachment, autoresearch, and surface-copy comparison CLI commands inside an isolated checkout under `--work-root`. Add a small explicit-observable k-row guard in `eval_run.py` so the negative control fails with repository-owned diagnostics before backend execution.

**Tech Stack:** Bash, Python 3.11+, pytest, git, existing `autoqec_search.cli`, fake executable fixtures for script tests, existing quantum Tanner campaign contracts.

## Global Constraints

- Do not broaden the quantum Tanner search space beyond generated `quantum-tanner-toric-d4` and `quantum-tanner-toric-d6`.
- Keep the smoke task budget at `max_shots = 64` and `css_memory.seed = 12345`.
- Default script output must include `frontier_size=2`, `crashes=0`, d4/d6 `p=0.001 ler=0`, `surface_copy_status=ok`, `surface_copy_rows=2`, `surface_copy_accepted=1`, and `surface_copy_rejected=1`.
- The output run directory must contain finalized `run_status.json`, `frontier.json`, `report.html` or `run-summary.html`, and surface-copy JSON/HTML with JSON `status: ok`.
- The negative-control mode must verify the error text `explicit X observables define 1 rows, expected k = 2`.
- The script must not dirty the caller's checkout; all generated evidence lives under `--work-root`.
- `QEC_CODE_BIN` and `RSINTER_BIN` select external tools; when unset, resolve `qec-code` and `rsinter` from `PATH`.

---

### Task 1: Guard Explicit X Observable Row Counts

**Files:**
- Modify: `src/autoqec_search/eval_run.py`
- Modify: `tests/test_search_eval_run.py`

**Interfaces:**
- Consumes: `evaluate_resolved_candidate_into_run(..., observables_x_override: dict | None)`.
- Produces: `_validate_explicit_x_observable_count(candidate_id: str, observables_x: dict[str, Any], structure: dict) -> None`.
- Raises: `SearchIntegrityError("explicit X observables define <rows> rows, expected k = <k>")` when explicit X observables are emitted for a CSS task and row count differs from `structure["k"]`.

- [x] **Step 1: Write the failing unit test**

  Add a k=2 candidate helper in `tests/test_search_eval_run.py` after `_candidate`:

  ```python
  def _k2_candidate() -> ResolvedCandidate:
      return ResolvedCandidate(
          spec=CandidateInput(
              candidate_id="qt-k2-candidate",
              campaign_id="quantum-tanner-autoresearch",
              code_family="quantum-tanner-code",
              parameters={},
              provenance={"kind": "test", "label": "synthetic"},
          ),
          artifact_root=Path("fixtures/qt-k2-candidate"),
          instance={
              "id": "qt-k2-candidate",
              "code_id": "quantum-tanner-code",
              "parameters": {},
              "derived_properties": {"distance": 4},
          },
          hx={
              "format": "dense_binary_matrix",
              "n_rows": 2,
              "n_cols": 4,
              "data": [[0, 0, 1, 0], [0, 0, 0, 1]],
          },
          hz={
              "format": "dense_binary_matrix",
              "n_rows": 0,
              "n_cols": 4,
              "data": [],
          },
          source_kind="explicit-zoo-instance",
      )
  ```

  Add this test near the explicit-observables tests:

  ```python
  def test_css_eval_rejects_incomplete_explicit_x_observables_for_k2_candidate(
      tmp_path: Path,
      monkeypatch: pytest.MonkeyPatch,
  ) -> None:
      task = {
          "id": "quantum-tanner-css-memory-x-rbposd-p001-v1",
          "input_type": "css",
          "observable": "logical_x",
          "p_list": [0.001],
          "rounds_policy": {"kind": "fixed", "rounds": 3},
          "collection": {"max_shots": 64, "max_errors": 16, "batch_size": 16},
          "css_memory": {
              "basis": "x",
              "schedule": "greedy",
              "seed": 12345,
              "observables": "optional",
          },
      }

      def fail_run_rsinter(*args: object, **kwargs: object) -> None:
          raise AssertionError("rsinter should not run with incomplete observables")

      monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fail_run_rsinter)

      with pytest.raises(
          SearchIntegrityError,
          match="explicit X observables define 1 rows, expected k = 2",
      ):
          evaluate_resolved_candidate_into_run(
              run_root=tmp_path / "run",
              run_id="bad-observables",
              campaign_id="quantum-tanner-autoresearch",
              candidate=_k2_candidate(),
              workspace=_workspace(),
              suite={"decoder_ids": ["rmatching-default-v1"]},
              task=task,
              selected_decoder_ids=["rmatching-default-v1"],
              selected_p_values=[0.001],
              created_at="2026-07-09T00:00:00Z",
              rsinter_executable="/bin/rsinter",
              rsinter_version="rsinter test",
              distance_payload_override={
                  "status": "completed",
                  "method": "css-upper-bound-witness",
                  "bound_type": "upper",
                  "upper_bound": 4,
                  "basis": "x",
              },
              observables_x_override={
                  "format": "sparse_rows",
                  "num_cols": 4,
                  "rows": [[0, 2, 3]],
              },
          )
  ```

- [x] **Step 2: Run RED verification**

  Run:

  ```bash
  PYTHONPATH=src python3 -m pytest tests/test_search_eval_run.py::test_css_eval_rejects_incomplete_explicit_x_observables_for_k2_candidate -q
  ```

  Expected: FAIL because the incomplete observable payload reaches fake `rsinter`.

- [x] **Step 3: Implement the guard**

  In `src/autoqec_search/eval_run.py`, add:

  ```python
  def _explicit_observable_row_count(observables_x: dict[str, Any]) -> int:
      rows = observables_x.get("rows") if isinstance(observables_x, dict) else None
      return len(rows) if isinstance(rows, list) else 0


  def _validate_explicit_x_observable_count(
      *,
      candidate_id: str,
      observables_x: dict[str, Any],
      structure: dict,
  ) -> None:
      expected_k = structure.get("k")
      if type(expected_k) is not int or expected_k <= 0:
          return
      row_count = _explicit_observable_row_count(observables_x)
      if row_count != expected_k:
          raise SearchIntegrityError(
              "explicit X observables define "
              f"{row_count} rows, expected k = {expected_k}"
          )
  ```

  After the existing basis compatibility check in `evaluate_resolved_candidate_into_run`, add:

  ```python
  if should_emit_observables and observables_x is not None:
      _validate_explicit_x_observable_count(
          candidate_id=candidate_id,
          observables_x=observables_x,
          structure=structure,
      )
  ```

  Replace the local emitted-observable row counting block with:

  ```python
  observable_count = _explicit_observable_row_count(observables_x)
  ```

- [x] **Step 4: Run GREEN verification**

  Run:

  ```bash
  PYTHONPATH=src python3 -m pytest tests/test_search_eval_run.py::test_css_eval_rejects_incomplete_explicit_x_observables_for_k2_candidate -q
  ```

  Expected: PASS.

### Task 2: Add the Quantum Tanner Smoke Script and Script Tests

**Files:**
- Create: `scripts/smoke_quantum_tanner_autoresearch.sh`
- Create: `tests/test_smoke_quantum_tanner_autoresearch_script.py`
- Modify: `benchmarks/schemas/search-space.schema.json`

**Interfaces:**
- Produces command: `QEC_CODE_BIN=/path/to/qec-code RSINTER_BIN=/path/to/rsinter scripts/smoke_quantum_tanner_autoresearch.sh --work-root /tmp/autoqec-qt-smoke`.
- Produces command: `scripts/smoke_quantum_tanner_autoresearch.sh --work-root /tmp/autoqec-qt-smoke --check-bad-observables`.
- Writes: `<work-root>/checkout/.worktrees/qt-smoke/results/search/quantum-tanner-autoresearch/qt-smoke/`.
- Writes: `<run-root>/surface-copy-comparison.json` and `<run-root>/surface-copy-comparison.html`.

- [x] **Step 1: Write failing script tests with fake tools**

  Create `tests/test_smoke_quantum_tanner_autoresearch_script.py` with helpers that copy the repo, initialize git, and write three fake executables:

  ```python
  from __future__ import annotations

  import json
  import os
  import shutil
  import subprocess
  import sys
  from pathlib import Path


  REPO_ROOT = Path(__file__).resolve().parents[1]


  def _copy_repo(tmp_path: Path) -> Path:
      work_root = tmp_path / "repo"

      def ignore(_directory: str, names: list[str]) -> set[str]:
          ignored = {".git", ".worktrees", "__pycache__", ".pytest_cache", ".mypy_cache"}
          ignored.update(name for name in names if name.endswith(".pyc"))
          return ignored & set(names)

      shutil.copytree(REPO_ROOT, work_root, ignore=ignore)
      subprocess.run(["git", "init"], cwd=work_root, check=True, capture_output=True, text=True)
      subprocess.run(["git", "config", "user.email", "autoqec@example.com"], cwd=work_root, check=True, capture_output=True, text=True)
      subprocess.run(["git", "config", "user.name", "AutoQEC"], cwd=work_root, check=True, capture_output=True, text=True)
      subprocess.run(["git", "add", "-A"], cwd=work_root, check=True, capture_output=True, text=True)
      subprocess.run(["git", "commit", "-m", "initial"], cwd=work_root, check=True, capture_output=True, text=True)
      return work_root
  ```

  The fake distance-ladder executable should read the generated manifest and write sparse-row CSS fixtures:

  ```python
  def _write_fake_distance_ladder(bin_dir: Path) -> Path:
      executable = bin_dir / "autoqec-distance-ladder"
      executable.write_text(
          f"""#!{sys.executable}
  import json
  import sys
  from pathlib import Path

  args = sys.argv[1:]
  manifest_path = Path(args[args.index("--manifest") + 1])
  manifest = json.loads(manifest_path.read_text())
  artifact_root = (manifest_path.parent / manifest["artifact_root"]).resolve()
  for entry in manifest["entries"]:
      candidate_id = entry["instance_id"]
      n = int(entry["n"])
      d = int(entry["expected_distance"])
      instance_dir = artifact_root / candidate_id
      instance_dir.mkdir(parents=True, exist_ok=True)
      spec_path = (manifest_path.parent / entry["quantum_tanner_spec"]).resolve()
      instance = {{
          "instance_id": candidate_id,
          "id": candidate_id,
          "code_id": entry["code_id"],
          "n": n,
          "k": 2,
          "expected_distance": d,
          "expected_bound_type": "exact",
          "qec_code_spec": entry["qec_code_spec"],
          "quantum_tanner_spec": str(spec_path.relative_to(manifest_path.parents[2])),
          "derived_properties": {{"distance": d}},
          "parameters": {{"distance": d}},
          "artifacts": {{"hx": "hx.json", "hz": "hz.json"}},
          "generator": {{"tool": "qec-code"}},
      }}
      hx = {{"format": "sparse_rows", "num_cols": n, "rows": [[i] for i in range(2, n)]}}
      hz = {{"format": "sparse_rows", "num_cols": n, "rows": []}}
      (instance_dir / "instance.json").write_text(json.dumps(instance, indent=2) + "\\n")
      (instance_dir / "hx.json").write_text(json.dumps(hx, indent=2) + "\\n")
      (instance_dir / "hz.json").write_text(json.dumps(hz, indent=2) + "\\n")
  print("fake distance ladder export")
  """
      )
      executable.chmod(0o755)
      return executable
  ```

  The fake `qec-code` should return X witnesses of weight 4 for n=16 and weight 6 for n=36. The fake `rsinter` should require two explicit observables, emit `shots_used = 64`, `logical_errors = 0`, and all required explicit-observable metadata.

  Add:

  ```python
  def test_smoke_quantum_tanner_autoresearch_script_prints_pass_summary(tmp_path: Path) -> None:
      repo = _copy_repo(tmp_path)
      bin_dir = _write_fake_tools(tmp_path)
      work_root = tmp_path / "smoke"
      result = subprocess.run(
          [
              str(repo / "scripts" / "smoke_quantum_tanner_autoresearch.sh"),
              "--work-root",
              str(work_root),
          ],
          cwd=repo,
          env={
              **os.environ,
              "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
              "QEC_CODE_BIN": str(bin_dir / "qec-code"),
              "RSINTER_BIN": str(bin_dir / "rsinter"),
          },
          capture_output=True,
          text=True,
      )
      assert result.returncode == 0, result.stdout + result.stderr
      for expected in (
          "PASS quantum_tanner_autoresearch_smoke",
          "frontier_size=2",
          "crashes=0",
          "quantum-tanner-toric-d4 p=0.001 ler=0",
          "quantum-tanner-toric-d6 p=0.001 ler=0",
          "surface_copy_status=ok",
          "surface_copy_rows=2",
          "surface_copy_accepted=1",
          "surface_copy_rejected=1",
      ):
          assert expected in result.stdout
      run_root = work_root / "checkout" / ".worktrees" / "qt-smoke" / "results" / "search" / "quantum-tanner-autoresearch" / "qt-smoke"
      assert json.loads((run_root / "run_status.json").read_text())["status"] == "finalized"
      assert json.loads((run_root / "surface-copy-comparison.json").read_text())["status"] == "ok"
  ```

  Add:

  ```python
  def test_smoke_quantum_tanner_bad_observables_check_prints_negative_control(
      tmp_path: Path,
  ) -> None:
      repo = _copy_repo(tmp_path)
      bin_dir = _write_fake_tools(tmp_path)
      result = subprocess.run(
          [
              str(repo / "scripts" / "smoke_quantum_tanner_autoresearch.sh"),
              "--work-root",
              str(tmp_path / "bad-observables"),
              "--check-bad-observables",
          ],
          cwd=repo,
          env={
              **os.environ,
              "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
              "QEC_CODE_BIN": str(bin_dir / "qec-code"),
              "RSINTER_BIN": str(bin_dir / "rsinter"),
          },
          capture_output=True,
          text=True,
      )
      assert result.returncode == 0, result.stdout + result.stderr
      assert "negative_control=ok" in result.stdout
      assert "explicit X observables define 1 rows, expected k = 2" in result.stdout
  ```

- [x] **Step 2: Run RED verification**

  Run:

  ```bash
  PYTHONPATH=src python3 -m pytest tests/test_smoke_quantum_tanner_autoresearch_script.py -q
  ```

  Expected: FAIL because `scripts/smoke_quantum_tanner_autoresearch.sh` does not exist yet.

- [x] **Step 3: Implement the script**

  Create `scripts/smoke_quantum_tanner_autoresearch.sh` with:

  ```bash
  #!/usr/bin/env bash
  set -euo pipefail

  RUN_ID="qt-smoke"
  WORK_ROOT=""
  CHECK_BAD_OBSERVABLES=0
  KEEP_EXISTING_WORK_ROOT=0
  ```

  Implement `usage`, `fail`, `resolve_executable`, argument parsing, source-root detection, work-root preparation, local clone, git identity setup, optional distance-ladder build, candidate generation, witness attachment, temp-checkout commit, autoresearch run, surface-copy comparison, JSON summary verification, and negative-control preparation.

  The default run must execute these commands inside the isolated checkout:

  ```bash
  PYTHONPATH="$CHECKOUT/src" python3 -m autoqec_search.cli generate-quantum-tanner-candidates --root "$CHECKOUT" --config "$CHECKOUT/campaigns/examples/quantum-tanner-autoresearch/generator.json" --qec-code-bin "$QEC_CODE_BIN_RESOLVED" --force
  PYTHONPATH="$CHECKOUT/src" python3 -m autoqec_search.cli attach-quantum-tanner-witnesses --root "$CHECKOUT" --campaign quantum-tanner-autoresearch --fixture-catalog campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json --witness-dir campaigns/examples/quantum-tanner-autoresearch/witnesses --basis x --qec-code-bin "$QEC_CODE_BIN_RESOLVED" --force --require-all
  git -C "$CHECKOUT" add -A
  git -C "$CHECKOUT" commit -m "prepare quantum Tanner smoke inputs"
  PYTHONPATH="$CHECKOUT/src" python3 -m autoqec_search.cli validate --root "$CHECKOUT"
  PYTHONPATH="$CHECKOUT/src" python3 -m autoqec_search.cli run --root "$CHECKOUT" --campaign quantum-tanner-autoresearch --wall-clock 90s --run-id "$RUN_ID" --distance-method random-window-upper-bound --qec-code-bin "$QEC_CODE_BIN_RESOLVED"
  PYTHONPATH="$CHECKOUT/src" python3 -m autoqec_search.cli compare-surface-copy --root "$CHECKOUT/.worktrees/$RUN_ID" --run "results/search/quantum-tanner-autoresearch/$RUN_ID" --baseline benchmarks/baselines/rotated-surface-single-logical-p001.json --out "$RUN_ROOT/surface-copy-comparison.html"
  ```

  The negative-control mode must generate candidates, copy the generated d4 fixture to `campaigns/examples/quantum-tanner-autoresearch/bad-observables/quantum-tanner-toric-d4`, add one-row `observables_x.json`, point the search space at that explicit instance with an inline upper-bound payload, commit the temp checkout, run autoresearch, and require the expected diagnostic in stdout/stderr.

  Extend the explicit-instance schema to accept `upper_bound_payload` and `upper_bound_payload_path` so the negative-control candidate can use the same upper-bound screening path as catalog-backed candidates. Convert copied sparse matrices to dense JSON in the negative-control fixture because explicit-instance resolution expects matrix payloads.

- [x] **Step 4: Run GREEN verification**

  Run:

  ```bash
  PYTHONPATH=src python3 -m pytest tests/test_smoke_quantum_tanner_autoresearch_script.py -q
  ```

  Expected: PASS.

### Task 3: Document the Smoke Interface and Run Verification

**Files:**
- Modify: `campaigns/examples/quantum-tanner-autoresearch/README.md`
- Modify: `docs/superpowers/plans/2026-07-09-issue-83-quantum-tanner-smoke-demo.md`

**Interfaces:**
- Documents: default smoke command, expected PASS lines, fixed seed/shot count, artifact paths, negative-control command.

- [x] **Step 1: Update README smoke section**

  Add a new section before "1. Generate Candidate Inputs":

  ```markdown
  ## Repeatable Smoke Demo

  From a clean checkout with `qec-code`, `rsinter`, Python dependencies, and the Rust distance-ladder binary available or buildable:

  ```bash
  QEC_CODE_BIN=$(command -v qec-code) RSINTER_BIN=$(command -v rsinter) scripts/smoke_quantum_tanner_autoresearch.sh --work-root /tmp/autoqec-qt-smoke
  ```

  The smoke script clones the checkout into `/tmp/autoqec-qt-smoke/checkout`, generates only the d4/d6 quantum Tanner candidates from `generator.json`, attaches X-basis upper-bound witnesses, runs the p=0.001 rbposd OSD10 suite with 64 shots and seed 12345, and writes the surface-copy comparison beside the run artifacts.

  Expected PASS summary includes:

  ```text
  frontier_size=2
  crashes=0
  quantum-tanner-toric-d4 p=0.001 ler=0
  quantum-tanner-toric-d6 p=0.001 ler=0
  surface_copy_status=ok
  surface_copy_rows=2
  surface_copy_accepted=1
  surface_copy_rejected=1
  ```

  Negative control:

  ```bash
  QEC_CODE_BIN=$(command -v qec-code) RSINTER_BIN=$(command -v rsinter) scripts/smoke_quantum_tanner_autoresearch.sh --work-root /tmp/autoqec-qt-smoke-bad --check-bad-observables
  ```

  This intentionally supplies one explicit X observable row for a k=2 Tanner candidate and requires `explicit X observables define 1 rows, expected k = 2`.
  ```

- [x] **Step 2: Run focused checks**

  Run:

  ```bash
  PYTHONPATH=src python3 -m pytest tests/test_search_eval_run.py::test_css_eval_rejects_incomplete_explicit_x_observables_for_k2_candidate tests/test_smoke_quantum_tanner_autoresearch_script.py -q
  ```

  Expected: PASS.

- [x] **Step 3: Run required repo verification**

  Run:

  ```bash
  PYTHONPATH=src python3 -m pytest
  ```

  Expected: PASS.

## Self-Review

- Spec coverage: Task 1 implements the negative-control rejection text, Task 2 implements the default and negative script modes plus artifact verification, and Task 3 documents the interface and fixed budget.
- Marker scan: no unresolved implementation markers are intended in this plan.
- Type consistency: script paths, JSON keys, and helper names match the design spec.

## Execution Choice

Plan complete and saved to `docs/superpowers/plans/2026-07-09-issue-83-quantum-tanner-smoke-demo.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.

Under the Agent Desk standing answer policy, choose **Subagent-Driven (recommended)**.
