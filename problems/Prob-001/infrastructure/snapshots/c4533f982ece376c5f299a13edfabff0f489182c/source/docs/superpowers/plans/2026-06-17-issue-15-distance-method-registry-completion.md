# Issue #15 Distance Method Registry Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete issue #15 by making AutoQEC's distance-method registry exact-first, auditable, and safe against upper-bound results being mistaken for exact distances.

**Architecture:** Keep `autoqec_search.distance_methods` as the single registry and loader boundary. Normalize exact `distance.json` payloads with `method`, `bound_type`, `options`, and `provenance`, keep `copied-zoo-exact` as the default, add a guarded `rstim-ilp-exact` entry that fails clearly until a stable external exact CSS backend exists, and remove first-class randomized-upper-bound CLI support from this PR.

**Tech Stack:** Python 3.11, argparse, pytest, JSON artifacts, existing `autoqec_search` eval/run/report/promote modules.

---

## File Structure

- Modify `src/autoqec_search/distance_methods.py`: exact-first method registry, normalized exact payloads, guarded `rstim-ilp-exact`, and strict loader validation for upper-bound payloads.
- Modify `src/autoqec_search/cli.py`: remove randomized-specific CLI options and pass exact-method options only.
- Modify `src/autoqec_search/run_loop.py`: remove randomized option plumbing, resume exact-method metadata, and keep `env.json` distance metadata stable.
- Modify `src/autoqec_search/eval_candidates.py`: keep artifact copying thin and rely on normalized distance payloads.
- Modify `src/autoqec_search/promote.py`: keep exact-only promotion and add coverage for malformed heuristic payloads.
- Modify `src/autoqec_search/report.py`: continue exposing method/bound type while relying on the hardened loader.
- Modify `tests/test_search_distance_methods.py`: update method names, add exact payload contract tests, add guarded backend tests, and add upper-bound misclassification regressions.
- Modify `tests/test_search_eval_cli.py`: remove randomized success test and assert exact payload options/provenance.
- Modify `tests/test_search_run_loop.py`: update CLI/parser and env metadata tests for exact methods.
- Modify `tests/test_search_promote.py`: add malformed randomized payload rejection test.
- Modify `tests/test_search_report.py`: update report method/bound coverage and invalid heuristic payload behavior.
- Modify `README.md`, `CLAUDE.md`, and `tests/test_search_docs.py`: document exact-first issue #15 semantics and remove AutoQEC randomized-upper-bound claims.

## Task 1: Distance Loader Safety Regressions

**Files:**
- Modify: `tests/test_search_distance_methods.py`
- Modify: `tests/test_search_promote.py`
- Test: `tests/test_search_distance_methods.py`
- Test: `tests/test_search_promote.py`

- [ ] **Step 1: Write failing loader tests for malformed randomized payloads**

Add these tests near the existing distance payload loader tests in `tests/test_search_distance_methods.py`:

```python
def test_load_distance_payload_rejects_randomized_payload_without_upper_bound_type() -> None:
    with pytest.raises(SearchIntegrityError, match="randomized-upper-bound.*bound_type upper"):
        load_distance_payload_from_dict(
            {
                "status": "completed",
                "distance": 3,
                "method": "randomized-upper-bound",
                "upper_bound": 3,
            },
            label="test distance",
        )


def test_load_distance_payload_rejects_unknown_upper_bound_method() -> None:
    with pytest.raises(SearchIntegrityError, match="upper-bound distance payload"):
        load_distance_payload_from_dict(
            {
                "status": "completed",
                "distance": 3,
                "method": "some-upper-bound",
                "bound_type": "upper",
                "upper_bound": 3,
            },
            label="test distance",
        )
```

Add this test after `test_evaluate_promotions_rejects_upper_bound_distance_when_verified` in `tests/test_search_promote.py`:

```python
def test_evaluate_promotions_rejects_randomized_distance_without_bound_type(
    tmp_path: Path,
) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    distance_path = run_root / "candidates" / "rotated-surface-d3-example" / "distance.json"
    distance = _load_json(distance_path)
    distance["method"] = "randomized-upper-bound"
    distance["upper_bound"] = distance["distance"]
    distance.pop("bound_type", None)
    _write_json(distance_path, distance)

    with pytest.raises(SearchIntegrityError, match="randomized-upper-bound.*bound_type upper"):
        evaluate_promotions(run_root, {"min_distance": 3, "require_distance_verified": True})
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_distance_methods.py::test_load_distance_payload_rejects_randomized_payload_without_upper_bound_type \
  tests/test_search_distance_methods.py::test_load_distance_payload_rejects_unknown_upper_bound_method \
  tests/test_search_promote.py::test_evaluate_promotions_rejects_randomized_distance_without_bound_type \
  -q
```

Expected: FAIL. The first and promotion tests should show the current bug where `randomized-upper-bound` without `bound_type` is treated as exact or reaches the existing exactness check.

- [ ] **Step 3: Commit the failing safety tests**

Run:

```bash
git add tests/test_search_distance_methods.py tests/test_search_promote.py
git commit -m "test: cover distance bound safety"
```

Expected: commit succeeds with only test files staged.

## Task 2: Exact-First Registry And Payload Contract

**Files:**
- Modify: `src/autoqec_search/distance_methods.py`
- Modify: `tests/test_search_distance_methods.py`
- Test: `tests/test_search_distance_methods.py`

- [ ] **Step 1: Replace randomized success tests with exact contract tests**

In `tests/test_search_distance_methods.py`, remove the helper `_write_fake_qec_code`, `test_randomized_upper_bound_invokes_qec_code_and_normalizes_payload`, and `test_randomized_upper_bound_rejects_result_below_known_exact`.

Update the import block to include `RSTIM_ILP_EXACT` once it exists:

```python
from autoqec_search.distance_methods import (
    COPIED_ZOO_EXACT,
    RSTIM_ILP_EXACT,
    DistanceMethodOptions,
    compute_distance_payload,
    dense_binary_matrix_to_sparse_rows,
    load_distance_payload,
    load_distance_payload_from_dict,
    normalize_distance_method_options,
)
```

Replace `test_copied_zoo_exact_payload_has_exact_bound_type` with:

```python
def test_copied_zoo_exact_payload_has_contract_metadata() -> None:
    payload = compute_distance_payload(
        _candidate(distance=5),
        normalize_distance_method_options(method=COPIED_ZOO_EXACT, qec_code_bin="qec-code"),
    )

    assert payload["status"] == "completed"
    assert payload["distance"] == 5
    assert payload["method"] == COPIED_ZOO_EXACT
    assert payload["bound_type"] == "exact"
    assert payload["options"] == {"method": COPIED_ZOO_EXACT, "qec_code_bin": "qec-code"}
    assert payload["provenance"] == {
        "source": "zoo-instance",
        "source_instance_id": "source-instance",
        "source_instance_path": "/tmp/source-instance",
    }
```

Add:

```python
def test_normalize_distance_method_options_accepts_guarded_rstim_exact() -> None:
    options = normalize_distance_method_options(
        method=RSTIM_ILP_EXACT,
        qec_code_bin="/tmp/qec-code",
    )

    assert options.method == RSTIM_ILP_EXACT
    assert options.qec_code_bin == "/tmp/qec-code"


def test_compute_distance_payload_reports_unavailable_rstim_exact_backend() -> None:
    with pytest.raises(SearchIntegrityError, match="rstim exact CSS distance backend is not available"):
        compute_distance_payload(
            _candidate(distance=3),
            DistanceMethodOptions(method=RSTIM_ILP_EXACT, qec_code_bin="/definitely/missing/qec-code"),
        )
```

- [ ] **Step 2: Run the exact registry tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_distance_methods.py::test_copied_zoo_exact_payload_has_contract_metadata \
  tests/test_search_distance_methods.py::test_normalize_distance_method_options_accepts_guarded_rstim_exact \
  tests/test_search_distance_methods.py::test_compute_distance_payload_reports_unavailable_rstim_exact_backend \
  -q
```

Expected: FAIL because `RSTIM_ILP_EXACT`, payload metadata, and guarded exact backend handling are not implemented yet.

- [ ] **Step 3: Implement exact-first distance methods**

In `src/autoqec_search/distance_methods.py`, remove the `subprocess` and `tempfile` imports and remove the `randomized_upper_bound_payload` function. Keep `dense_binary_matrix_to_sparse_rows` because the guarded `rstim-ilp-exact` path and future exact backend will use it.

Change the constants and dataclass to:

```python
COPIED_ZOO_EXACT = "copied-zoo-exact"
LEGACY_COPIED_ZOO_EXACT = "copied-from-zoo-instance"
RSTIM_ILP_EXACT = "rstim-ilp-exact"
RANDOMIZED_UPPER_BOUND = "randomized-upper-bound"
EXACT_BOUND = "exact"
UPPER_BOUND = "upper"


@dataclass(frozen=True)
class DistanceMethodOptions:
    method: str = COPIED_ZOO_EXACT
    qec_code_bin: str = "qec-code"
```

Replace `normalize_distance_method_options` with:

```python
def normalize_distance_method_options(
    *,
    method: str | None,
    qec_code_bin: str = "qec-code",
    **unused_options: object,
) -> DistanceMethodOptions:
    selected_method = method or COPIED_ZOO_EXACT
    if selected_method not in {COPIED_ZOO_EXACT, RSTIM_ILP_EXACT}:
        raise SearchIntegrityError(f"unknown distance method: {selected_method}")
    if not isinstance(qec_code_bin, str) or not qec_code_bin:
        raise SearchIntegrityError("qec-code executable must be a nonempty string")
    return DistanceMethodOptions(method=selected_method, qec_code_bin=qec_code_bin)
```

Replace `distance_method_metadata` with:

```python
def distance_method_metadata(options: DistanceMethodOptions) -> dict[str, Any]:
    return {
        "method": options.method,
        "bound_type": EXACT_BOUND,
        "qec_code_bin": options.qec_code_bin,
    }
```

Replace `copied_zoo_exact_payload` with:

```python
def copied_zoo_exact_payload(candidate, options: DistanceMethodOptions) -> dict[str, Any]:
    source_instance_id = _source_instance_id(candidate)
    source_instance_path = str(candidate.artifact_root)
    return {
        "status": "completed",
        "distance": _recorded_instance_distance(candidate),
        "method": COPIED_ZOO_EXACT,
        "bound_type": EXACT_BOUND,
        "options": {
            "method": COPIED_ZOO_EXACT,
            "qec_code_bin": options.qec_code_bin,
        },
        "provenance": {
            "source": "zoo-instance",
            "source_instance_id": source_instance_id,
            "source_instance_path": source_instance_path,
        },
        "source_instance_id": source_instance_id,
        "source_instance_path": source_instance_path,
    }
```

Add:

```python
def rstim_ilp_exact_payload(candidate, options: DistanceMethodOptions) -> dict[str, Any]:
    dense_binary_matrix_to_sparse_rows(candidate.hx)
    dense_binary_matrix_to_sparse_rows(candidate.hz)
    raise SearchIntegrityError(
        "rstim exact CSS distance backend is not available; "
        "use copied-zoo-exact for recorded instances or install a qec-code build "
        "with exact CSS distance"
    )
```

Replace `compute_distance_payload` with:

```python
def compute_distance_payload(
    candidate,
    options: DistanceMethodOptions,
) -> dict[str, Any]:
    if options.method == COPIED_ZOO_EXACT:
        return copied_zoo_exact_payload(candidate, options)
    if options.method == RSTIM_ILP_EXACT:
        return rstim_ilp_exact_payload(candidate, options)
    raise SearchIntegrityError(f"unknown distance method: {options.method}")
```

- [ ] **Step 4: Harden loaded distance payload validation**

Replace `_normalize_legacy_bound_type` with:

```python
def _normalize_legacy_bound_type(payload: dict[str, Any], *, label: str) -> str | None:
    bound_type = payload.get("bound_type")
    method = payload.get("method")
    if bound_type == EXACT_BOUND:
        if method == RANDOMIZED_UPPER_BOUND or (
            isinstance(method, str) and "upper" in method
        ):
            raise SearchIntegrityError(f"{method} distance payload must use bound_type upper in {label}")
        return EXACT_BOUND
    if bound_type == UPPER_BOUND:
        if method != RANDOMIZED_UPPER_BOUND:
            raise SearchIntegrityError(f"unsupported upper-bound distance payload in {label}")
        return UPPER_BOUND
    if bound_type is not None:
        raise SearchIntegrityError(f"invalid distance bound_type in {label}")
    if method == RANDOMIZED_UPPER_BOUND:
        raise SearchIntegrityError(
            f"randomized-upper-bound distance payload must use bound_type upper in {label}"
        )
    if method in {LEGACY_COPIED_ZOO_EXACT, COPIED_ZOO_EXACT, RSTIM_ILP_EXACT}:
        return EXACT_BOUND
    if method is None and payload.get("status") in {"completed", "computed"} and type(payload.get("distance")) is int:
        return EXACT_BOUND
    return None
```

Change the call site in `load_distance_payload_from_dict` to:

```python
bound_type = _normalize_legacy_bound_type(payload, label=label)
```

- [ ] **Step 5: Run distance method tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_distance_methods.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit distance registry implementation**

Run:

```bash
git add src/autoqec_search/distance_methods.py tests/test_search_distance_methods.py
git commit -m "fix: harden exact distance registry"
```

Expected: commit succeeds.

## Task 3: CLI And Run-Loop Exact Method Plumbing

**Files:**
- Modify: `src/autoqec_search/cli.py`
- Modify: `src/autoqec_search/run_loop.py`
- Modify: `tests/test_search_run_loop.py`
- Test: `tests/test_search_run_loop.py`

- [ ] **Step 1: Update parser tests for exact-only options**

Replace `test_run_cli_accepts_distance_method_flags` in `tests/test_search_run_loop.py` with:

```python
def test_run_cli_accepts_exact_distance_method_flags() -> None:
    from autoqec_search.cli import build_parser

    args = build_parser().parse_args(
        [
            "run",
            "--root",
            ".",
            "--campaign",
            "rotated-surface-baseline",
            "--distance-method",
            "rstim-ilp-exact",
            "--qec-code-bin",
            "qec-code",
        ]
    )

    assert args.distance_method == "rstim-ilp-exact"
    assert args.qec_code_bin == "qec-code"
```

Update `test_build_env_records_distance_method_metadata` so the metadata uses an exact method:

```python
distance_method={
    "method": "rstim-ilp-exact",
    "qec_code_bin": "qec-code",
    "bound_type": "exact",
},
```

and assert:

```python
assert env["distance_method"]["method"] == "rstim-ilp-exact"
assert env["distance_method"]["bound_type"] == "exact"
```

- [ ] **Step 2: Run parser tests to verify they fail or expose obsolete fields**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_run_loop.py::test_run_cli_accepts_exact_distance_method_flags \
  tests/test_search_run_loop.py::test_build_env_records_distance_method_metadata \
  -q
```

Expected: FAIL until CLI and metadata are simplified.

- [ ] **Step 3: Simplify `eval` and `run` CLI options**

In `src/autoqec_search/cli.py`, remove these eval parser arguments:

```python
eval_parser.add_argument("--distance-iterations", type=int, default=500)
eval_parser.add_argument("--distance-restarts", type=int, default=4)
eval_parser.add_argument("--distance-seed", type=int, default=0)
eval_parser.add_argument("--distance-target-weight", type=int, default=None)
```

Remove these run parser arguments:

```python
run_parser.add_argument("--distance-iterations", type=int, default=500)
run_parser.add_argument("--distance-restarts", type=int, default=4)
run_parser.add_argument("--distance-seed", type=int, default=None)
run_parser.add_argument("--distance-target-weight", type=int, default=None)
```

Change the `eval` call to:

```python
distance_method_options=normalize_distance_method_options(
    method=args.distance_method,
    qec_code_bin=args.qec_code_bin,
),
```

Change the `run_autoresearch` call to:

```python
distance_method=args.distance_method,
qec_code_bin=args.qec_code_bin,
```

- [ ] **Step 4: Simplify run-loop signatures and resume options**

In `src/autoqec_search/run_loop.py`, replace the return in `resume_distance_method_options` with:

```python
return normalize_distance_method_options(
    method=metadata.get("method") if isinstance(metadata.get("method"), str) else None,
    qec_code_bin=metadata.get("qec_code_bin", "qec-code"),
)
```

Change `run_autoresearch` signature to remove randomized parameters:

```python
def run_autoresearch(
    root: Path,
    *,
    campaign_id: str,
    wall_clock: str | None,
    seed: int | None,
    run_id: str | None,
    resume: bool,
    cleanup_worktree: bool,
    allow_dirty_root: bool,
    distance_method: str | None = None,
    qec_code_bin: str = "qec-code",
) -> Path:
```

Replace the non-resume normalization block with:

```python
distance_method_options = normalize_distance_method_options(
    method=distance_method,
    qec_code_bin=qec_code_bin,
)
```

- [ ] **Step 5: Run run-loop tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_run_loop.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit CLI and run-loop plumbing**

Run:

```bash
git add src/autoqec_search/cli.py src/autoqec_search/run_loop.py tests/test_search_run_loop.py
git commit -m "fix: simplify exact distance method cli"
```

Expected: commit succeeds.

## Task 4: Eval, Report, And Promotion Tests

**Files:**
- Modify: `tests/test_search_eval_cli.py`
- Modify: `tests/test_search_report.py`
- Modify: `tests/test_search_promote.py`
- Modify: `src/autoqec_search/report.py`
- Modify: `src/autoqec_search/promote.py`
- Test: `tests/test_search_eval_cli.py`
- Test: `tests/test_search_report.py`
- Test: `tests/test_search_promote.py`

- [ ] **Step 1: Update eval tests for normalized exact payloads**

Remove `_write_fake_qec_code` and `test_eval_randomized_distance_method_writes_upper_bound_payload` from `tests/test_search_eval_cli.py`.

In `test_eval_campaign_candidate_writes_completed_selected_manifest_and_plot`, after the existing `bound_type` assertion, add:

```python
assert distance["options"] == {"method": "copied-zoo-exact", "qec_code_bin": "qec-code"}
assert distance["provenance"]["source"] == "zoo-instance"
assert distance["provenance"]["source_instance_id"] == "rotated-surface-code-d3"
assert distance["source_instance_id"] == "rotated-surface-code-d3"
```

Add this test near other eval failure tests:

```python
def test_eval_rstim_exact_backend_unavailable_is_clear(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.01",
        "--run-id",
        "rstim-exact-unavailable",
        "--distance-method",
        "rstim-ilp-exact",
    )

    assert result.returncode == 1
    assert "rstim exact CSS distance backend is not available" in result.stderr
```

- [ ] **Step 2: Update report and promotion tests for hardened loader semantics**

In `tests/test_search_report.py`, keep `test_build_report_model_exposes_distance_method_and_bound_type` but change it to use a copied exact payload:

```python
{
    "status": "completed",
    "distance": 3,
    "method": "copied-zoo-exact",
    "bound_type": "exact",
    "options": {"method": "copied-zoo-exact", "qec_code_bin": "qec-code"},
    "provenance": {"source": "zoo-instance"},
}
```

and assert:

```python
assert candidate["distance_method"] == "copied-zoo-exact"
assert candidate["distance_bound_type"] == "exact"
```

Add:

```python
def test_build_report_model_rejects_randomized_payload_without_bound_type(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)
    _write_json(
        run_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "distance.json",
        {
            "status": "completed",
            "distance": 3,
            "method": "randomized-upper-bound",
            "upper_bound": 3,
        },
    )

    with pytest.raises(SearchIntegrityError, match="randomized-upper-bound.*bound_type upper"):
        build_report_model(work_root, run_root)
```

No production change should be needed in `report.py` or `promote.py` beyond the hardened loader from Task 2. If a test reveals extra handling, keep changes local and avoid duplicating loader rules.

- [ ] **Step 3: Run focused eval/report/promote tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_eval_cli.py \
  tests/test_search_report.py \
  tests/test_search_promote.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Commit downstream behavior updates**

Run:

```bash
git add tests/test_search_eval_cli.py tests/test_search_report.py tests/test_search_promote.py src/autoqec_search/report.py src/autoqec_search/promote.py
git commit -m "fix: keep distance consumers exact-safe"
```

Expected: commit succeeds. If `src/autoqec_search/report.py` or `src/autoqec_search/promote.py` did not change, omit unchanged files from `git add`.

## Task 5: Documentation And PR Semantics

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_search_docs.py`
- Test: `tests/test_search_docs.py`

- [ ] **Step 1: Update docs tests**

Open `tests/test_search_docs.py` and update the assertions around issue #15 documentation so they require these strings:

```python
assert "copied-zoo-exact" in readme
assert "rstim-ilp-exact" in readme
assert "bound_type: \"exact\"" in readme
assert "randomized upper bounds live in rstim" in readme
assert "rstim exact CSS distance backend is not available" in claude
```

Use the file's existing variable names and assertion style.

- [ ] **Step 2: Run docs tests to verify the current docs fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py -q
```

Expected: FAIL until README and CLAUDE are updated.

- [ ] **Step 3: Update README and CLAUDE distance-method text**

Replace the issue #15 distance-method paragraph in `README.md` and `CLAUDE.md` with this text, adjusted only for local surrounding wording:

```markdown
Distance-method work lives in `src/autoqec_search/distance_methods.py`. The
registry is exact-first. The default `copied-zoo-exact` method records Zoo
`derived_properties.distance` as `bound_type: "exact"` and writes method
options plus provenance into `distance.json`; it must not require `qec-code`.
The guarded `rstim-ilp-exact` method is reserved for the external exact CSS
distance backend and currently fails clearly with
`rstim exact CSS distance backend is not available` when that backend is not
installed. Randomized upper bounds live in rstim and are not a first-class
AutoQEC method for closing issue #15. Promotion requires exact distances by
default and must never treat an upper bound as Zoo `derived_properties.distance`.
```

- [ ] **Step 4: Run docs tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit documentation update**

Run:

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: align distance registry scope"
```

Expected: commit succeeds.

## Task 6: Final Verification And Issue #15 Evidence

**Files:**
- Check: full repository

- [ ] **Step 1: Run the focused issue #15 suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_distance_methods.py \
  tests/test_search_eval_candidates.py \
  tests/test_search_eval_cli.py \
  tests/test_search_run_loop.py \
  tests/test_search_promote.py \
  tests/test_search_report.py \
  tests/test_search_docs.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests -q
```

Expected: PASS with the repository's current deselection count.

- [ ] **Step 3: Validate search workspace**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected:

```text
validated search workspace under .: 2 campaigns, 1 suites, 2 runs
```

- [ ] **Step 4: Check formatting and branch status**

Run:

```bash
git diff --check HEAD
git status --short --branch
```

Expected: `git diff --check HEAD` prints nothing. `git status --short --branch` shows the issue branch ahead of its remote with no unstaged or untracked implementation files.

- [ ] **Step 5: Summarize issue #15 completion**

In the final response, report:

- exact payloads now include options and provenance
- `randomized-upper-bound` is no longer the AutoQEC method used to close issue #15
- malformed randomized/upper-bound payloads cannot be classified as exact
- `rstim-ilp-exact` is guarded with a clear unavailable-backend error
- promotion remains exact-only by default
- exact commands and test outcomes from Steps 1-4
