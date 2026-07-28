# Issue 82 Logical-X Observables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete a verified X-like CSS upper-bound witness into exactly `k` independent logical-X observable rows before rsinter is invoked.

**Architecture:** Reuse deterministic GF(2) helpers in `structure.py` to construct a quotient basis of `ker(HZ) / rowspan(HX)` seeded by the verified witness. Screening keeps witness verification and distance evidence separate from the completed benchmark observables.

**Tech Stack:** Python 3.11+, pytest, existing `autoqec_search` dense binary matrix payloads, existing rsinter sparse-row observable wrapper.

## Global Constraints

- Preserve existing invalid witness rejection reasons from `verify_css_upper_bound_witness`, including `not_in_kernel` and `incompatible_upper_bound_witness_basis`.
- Do not make rsinter accept incomplete explicit observables.
- Distance upper-bound payloads must continue to use the verified witness weight.
- Verified X-witness screening must produce `observables_x_override` with exactly `k = n - rank(HX) - rank(HZ)` rows.
- Output observable rows must be in `ker(HZ)` and independent modulo `rowspan(HX)`.
- Loaded upper-bound payload inputs without a witness vector continue to require existing explicit candidate observables.

---

### Task 1: Complete Verified X Witnesses Into Full Observable Bases

**Files:**
- Modify: `src/autoqec_search/structure.py`
- Modify: `src/autoqec_search/screening.py`
- Modify: `tests/test_search_screening.py`
- Modify: `tests/test_search_quantum_tanner_run_gating.py`

**Interfaces:**
- Consumes: `matrix_data(payload, label) -> list[list[int]]`, `gf2_rank(matrix) -> int`, `gf2_vector_in_kernel(rows, vector) -> bool`, and `gf2_vector_in_row_space(rows, vector) -> bool`.
- Produces: `gf2_nullspace(matrix: DenseMatrix, *, num_cols: int | None = None) -> DenseMatrix`.
- Produces: `complete_logical_observable_basis(*, kernel_rows: DenseMatrix, stabilizer_rows: DenseMatrix, preferred_vector: list[int]) -> DenseMatrix`.
- Produces: screening `observables_x_override` payloads shaped as `{"format": "sparse_rows", "num_cols": n, "rows": [...]}` with exactly `k` rows for verified X witnesses.

- [x] **Step 1: Write the failing screening/helper tests**

  In `tests/test_search_screening.py`, extend the structure import:

  ```python
  from autoqec_search.structure import (
      complete_logical_observable_basis,
      gf2_rank,
      gf2_vector_in_kernel,
      matrix_data,
      verify_css_upper_bound_witness,
  )
  ```

  Add these helpers near the existing quantum Tanner helpers:

  ```python
  def _sparse_rows_to_dense_rows(payload: dict) -> list[list[int]]:
      rows = []
      for sparse_row in payload["rows"]:
          dense_row = [0] * payload["num_cols"]
          for column in sparse_row:
              dense_row[column] = 1
          rows.append(dense_row)
      return rows


  def _assert_logical_x_observable_basis(candidate, payload: dict, expected_rows: int) -> None:
      assert payload["format"] == "sparse_rows"
      assert payload["num_cols"] == candidate.hx["n_cols"]
      assert len(payload["rows"]) == expected_rows
      hx = matrix_data(candidate.hx, "hx.json")
      hz = matrix_data(candidate.hz, "hz.json")
      dense_rows = _sparse_rows_to_dense_rows(payload)
      for row in dense_rows:
          assert gf2_vector_in_kernel(hz, row)
      assert gf2_rank([*hx, *dense_rows]) == gf2_rank(hx) + expected_rows
  ```

  Add a direct helper test:

  ```python
  def test_logical_observable_basis_completes_quantum_tanner_d4_witness() -> None:
      candidate_spec = _qt_d4_candidate_spec(
          upper_bound_witness_path=(
              "campaigns/examples/quantum-tanner-autoresearch/witnesses/"
              "quantum-tanner-toric-d4-upper-bound-witness.json"
          )
      )
      candidate = resolve_catalog_backed_candidate(
          REPO_ROOT,
          candidate_spec,
          campaign_id=QT_CAMPAIGN_ID,
      )
      assert candidate is not None
      witness = {
          "basis": "x",
          "vector": [1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
      }
      hx = matrix_data(candidate.hx, "hx.json")
      hz = matrix_data(candidate.hz, "hz.json")

      rows = complete_logical_observable_basis(
          kernel_rows=hz,
          stabilizer_rows=hx,
          preferred_vector=witness["vector"],
      )

      assert rows[0] == witness["vector"]
      assert len(rows) == 2
      for row in rows:
          assert gf2_vector_in_kernel(hz, row)
      assert gf2_rank([*hx, *rows]) == gf2_rank(hx) + 2
  ```

  Update `test_screen_upper_bound_candidate_admits_x_witness_for_memory_x_task` to assert the first sparse row is the witness row and to call `_assert_logical_x_observable_basis(candidate, decision.observables_x_override, expected_rows=2)` instead of comparing with a one-row payload.

  Add the negative control:

  ```python
  def test_screen_upper_bound_candidate_rejects_x_witness_outside_kernel_before_observables(
      tmp_path: Path,
  ) -> None:
      witness_path = tmp_path / "bad-x-witness.json"
      witness_path.write_text(
          '{"basis": "x", "vector": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}'
      )
      candidate_spec = _qt_d4_candidate_spec(
          upper_bound_witness_path="bad-x-witness.json"
      )
      candidate = resolve_catalog_backed_candidate(
          REPO_ROOT,
          candidate_spec,
          campaign_id=QT_CAMPAIGN_ID,
      )
      assert candidate is not None

      decision = screen_upper_bound_candidate(
          tmp_path,
          candidate=candidate,
          candidate_spec=candidate_spec,
          benchmark_task=QT_TASK,
      )

      assert decision.screening_status == "failed"
      assert decision.reason == "not_in_kernel"
      assert decision.observables_x_override is None
  ```

- [x] **Step 2: Update the fake rsinter integration test expectations**

  In `tests/test_search_quantum_tanner_run_gating.py`, update `_write_fake_rsinter` so the fake rsinter reads `observables.css.json`, requires two rows for explicit observables, and records the observed count:

  ```python
  observable_count = 0
  if "observables" in row_params:
      observables_path = spec_path.parent / row_params["observables"]
      observables = json.loads(observables_path.read_text())
      observable_count = len(observables["rows"])
      if observable_count != 2:
          raise SystemExit(f"expected two explicit observables, got {observable_count}")
      row_params.update(
          {
              "logical_failure_aggregation": "any_logical",
              "logical_observable_basis": "x",
              "logical_observable_count": observable_count,
              "logical_observable_source": "explicit",
              "seed": 12345,
          }
      )
  ```

  Use `observable_count` for `case_summary["num_obs"]` and `case_summary["logical_observable_count"]`.

  Update expected manifest metadata in `test_quantum_tanner_autoresearch_records_any_logical_aggregation_for_d4` from `logical_observable_count: 1` to `logical_observable_count: 2`.

  Add an assertion in `test_quantum_tanner_autoresearch_admits_d4_and_writes_screening_json` that the emitted `rsinter/input/observables.css.json` has exactly two rows.

- [x] **Step 3: Run RED verification**

  Run:

  ```bash
  PYTHONPATH=src pytest tests/test_search_screening.py tests/test_search_quantum_tanner_run_gating.py -k "logical_observable_basis or upper_bound_candidate_admits_x_witness"
  ```

  Expected before implementation: FAIL because `complete_logical_observable_basis` is not defined or because the admitted witness still emits only one row.

- [x] **Step 4: Implement deterministic GF(2) basis helpers**

  In `src/autoqec_search/structure.py`, add helper validation and these public helpers after `gf2_rank`:

  ```python
  def _validate_dense_rows(rows: DenseMatrix, *, num_cols: int, label: str) -> DenseMatrix:
      normalized: DenseMatrix = []
      for row in rows:
          if len(row) != num_cols:
              raise SearchIntegrityError(f"{label} row length mismatch")
          if any(not _is_plain_int(bit) or bit not in (0, 1) for bit in row):
              raise SearchIntegrityError(f"{label} contains non-binary entries")
          normalized.append([int(bit) for bit in row])
      return normalized


  def _matrix_width_for_basis(
      kernel_rows: DenseMatrix,
      stabilizer_rows: DenseMatrix,
      preferred_vector: list[int],
  ) -> int:
      widths = [len(preferred_vector)]
      widths.extend(len(row) for row in kernel_rows)
      widths.extend(len(row) for row in stabilizer_rows)
      width = widths[0]
      if any(candidate != width for candidate in widths):
          raise SearchIntegrityError("logical observable basis width mismatch")
      return width


  def gf2_nullspace(matrix: DenseMatrix, *, num_cols: int | None = None) -> DenseMatrix:
      if num_cols is None:
          if not matrix:
              raise SearchIntegrityError("num_cols is required for empty nullspace matrix")
          num_cols = len(matrix[0])
      if not _is_plain_int(num_cols) or num_cols < 0:
          raise SearchIntegrityError("num_cols must be a nonnegative integer")
      rows = _validate_dense_rows(matrix, num_cols=num_cols, label="nullspace matrix")
      rows = [row for row in rows if any(row)]
      pivot_columns: list[int] = []
      rank = 0
      for column in range(num_cols):
          pivot_index = next(
              (index for index in range(rank, len(rows)) if rows[index][column] == 1),
              None,
          )
          if pivot_index is None:
              continue
          rows[rank], rows[pivot_index] = rows[pivot_index], rows[rank]
          for index in range(len(rows)):
              if index != rank and rows[index][column] == 1:
                  rows[index] = [
                      left ^ right
                      for left, right in zip(rows[index], rows[rank], strict=True)
                  ]
          pivot_columns.append(column)
          rank += 1
          if rank == len(rows):
              break
      pivot_set = set(pivot_columns)
      basis: DenseMatrix = []
      for free_column in range(num_cols):
          if free_column in pivot_set:
              continue
          vector = [0] * num_cols
          vector[free_column] = 1
          for row_index, pivot_column in enumerate(pivot_columns):
              if rows[row_index][free_column] == 1:
                  vector[pivot_column] = 1
          basis.append(vector)
      return basis


  def complete_logical_observable_basis(
      *,
      kernel_rows: DenseMatrix,
      stabilizer_rows: DenseMatrix,
      preferred_vector: list[int],
  ) -> DenseMatrix:
      num_cols = _matrix_width_for_basis(kernel_rows, stabilizer_rows, preferred_vector)
      kernel = _validate_dense_rows(kernel_rows, num_cols=num_cols, label="kernel matrix")
      stabilizers = _validate_dense_rows(
          stabilizer_rows,
          num_cols=num_cols,
          label="stabilizer matrix",
      )
      preferred = _validate_witness_vector(preferred_vector)
      if preferred is None or len(preferred) != num_cols:
          raise SearchIntegrityError("preferred logical vector must be binary")
      logical_count = num_cols - gf2_rank(kernel) - gf2_rank(stabilizers)
      if logical_count <= 0:
          raise SearchIntegrityError("logical observable basis has no logical dimension")
      if not gf2_vector_in_kernel(kernel, preferred):
          raise SearchIntegrityError("preferred logical vector is not in kernel")
      if gf2_vector_in_row_space(stabilizers, preferred):
          raise SearchIntegrityError("preferred logical vector is in stabilizer row space")

      selected: DenseMatrix = [preferred]
      current_rank = gf2_rank([*stabilizers, *selected])
      for candidate in gf2_nullspace(kernel, num_cols=num_cols):
          if len(selected) == logical_count:
              break
          next_rank = gf2_rank([*stabilizers, *selected, candidate])
          if next_rank > current_rank:
              selected.append(candidate)
              current_rank = next_rank
      if len(selected) != logical_count:
          raise SearchIntegrityError(
              "could not complete logical observable basis to expected dimension"
          )
      return selected
  ```

- [x] **Step 5: Use completed basis in screening**

  In `src/autoqec_search/screening.py`, import `complete_logical_observable_basis` and `matrix_data` from `autoqec_search.structure`.

  Replace `_observables_from_witness_payload` with dense-row conversion helpers:

  ```python
  def _sparse_rows_from_dense_rows(rows: list[list[int]], *, num_cols: int) -> dict[str, Any]:
      return {
          "format": "sparse_rows",
          "num_cols": num_cols,
          "rows": [
              [index for index, value in enumerate(row) if value == 1]
              for row in rows
          ],
      }


  def _logical_x_observables_from_verified_witness(
      hx_payload: dict[str, Any],
      hz_payload: dict[str, Any],
      witness_payload: dict[str, Any],
  ) -> dict[str, Any]:
      vector = witness_payload.get("vector")
      if not isinstance(vector, list):
          raise SearchIntegrityError("upper-bound witness vector must be a list")
      hx = matrix_data(hx_payload, "hx.json")
      hz = matrix_data(hz_payload, "hz.json")
      rows = complete_logical_observable_basis(
          kernel_rows=hz,
          stabilizer_rows=hx,
          preferred_vector=vector,
      )
      return _sparse_rows_from_dense_rows(rows, num_cols=int(hx_payload["n_cols"]))
  ```

  In the admitted verified-witness return path, set:

  ```python
  observables_x_override = (
      _logical_x_observables_from_verified_witness(
          candidate.hx,
          candidate.hz,
          witness_payload,
      )
      if verification.get("basis") == "x"
      else None
  )
  ```

  Then pass `observables_x_override=observables_x_override` in the `ScreeningDecision`.

- [x] **Step 6: Run GREEN verification**

  Run:

  ```bash
  PYTHONPATH=src pytest tests/test_search_screening.py tests/test_search_quantum_tanner_run_gating.py -k "logical_observable_basis or upper_bound_candidate_admits_x_witness"
  ```

  Expected after implementation: PASS with the helper test and admitted witness test selected.

- [x] **Step 7: Run issue verification and repository validation**

  Run:

  ```bash
  PYTHONPATH=src pytest tests/test_search_screening.py tests/test_search_quantum_tanner_run_gating.py -k "logical_observable_basis or upper_bound_candidate_admits_x_witness"
  PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
  ```

  Expected: both commands exit 0.

- [x] **Step 8: Run full pytest before commit**

  Run:

  ```bash
  PYTHONPATH=src python3 -m pytest
  ```

  Expected: exit 0.

- [x] **Step 9: Commit**

  Commit the implementation and tests:

  ```bash
  git add src/autoqec_search/structure.py src/autoqec_search/screening.py tests/test_search_screening.py tests/test_search_quantum_tanner_run_gating.py
  git commit -m "fix: complete logical x observables from witnesses"
  ```
