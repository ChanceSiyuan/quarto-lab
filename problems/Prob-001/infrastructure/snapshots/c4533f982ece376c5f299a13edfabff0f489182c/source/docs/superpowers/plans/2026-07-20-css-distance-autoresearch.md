# Blinded CSS Distance Autoresearch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a blinded, fixed-five-minute autoresearch campaign that finds and verifies randomized CSS logical-operator upper-bound witnesses.

**Architecture:** A public proposal container sees only a narrow `proposal-workspace/`, while a networkless evaluator owns an opaque issue-#38 holdout and independently verifies witnesses. Each algorithm has a Git worktree and sanitized `LOG.md`; screening and finalist phases retain only aggregate metrics.

**Tech Stack:** Python 3.11, pytest, Docker Desktop, Git worktrees, NumPy, pinned `codedistance==0.0.8` source commit.

## Global Constraints

- Hard timeout: 300 seconds per algorithm/case run.
- Randomized upper-bound algorithms only; no exact SAT, MaxSAT, ILP, MIP, or exhaustive search.
- Proposal agents must never see issue-#38 matrices, selected ids, targets, witnesses, or per-case results.
- Every algorithm attempt has its own Git worktree and `LOG.md`.
- A result is accepted only after independent kernel and non-stabilizer row-space verification.

---

### Task 1: Enforce the public-only proposal mount

**Files:**
- Modify: `src/autoqec_search/css_distance_container.py`
- Modify: `tests/test_search_css_distance_container.py`

**Interfaces:**
- Consumes: `build_proposal_command(..., proposal_workspace: Path, ...)`
- Produces: a Docker argv whose only writable project mount is `/workspace` backed by a directory named `proposal-workspace`

- [ ] **Step 1: Write the failing containment tests**

Add tests that pass an experiment worktree root and expect
`CssDistanceContainerError("proposal workspace must be a dedicated public directory")`,
then pass `<worktree>/proposal-workspace` and assert that exact source is the
only `/workspace` mount.  Add a symlink child and assert rejection.

- [ ] **Step 2: Run the tests and verify the expected failure**

Run: `PYTHONPATH=src python3 -m pytest -q tests/test_search_css_distance_container.py -k 'proposal_command'`

Expected: the worktree-root rejection test fails because the current command
accepts any directory.

- [ ] **Step 3: Implement the minimal validator**

Add `validate_public_proposal_workspace(path: Path) -> Path` that requires an
existing, non-symlink directory named `proposal-workspace`, rejects symlinks
anywhere below it, and rejects private marker names.  Call it before building
the proposal mount and pass the validated path to `validate_mount_allowlist`.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH=src python3 -m pytest -q tests/test_search_css_distance_container.py`

Expected: all containment tests pass.

### Task 2: Repair pinned baseline adapters

**Files:**
- Modify: `.worktrees/css-distance-codedistance-qdist-rndmw/candidate.py`
- Modify: `.worktrees/css-distance-codedistance-qdist-evol/candidate.py`
- Modify: `.worktrees/css-distance-codedistance-decoder-dist/candidate.py`
- Modify: each corresponding `LOG.md`

**Interfaces:**
- Consumes: AutoQEC `dense_binary_matrix` or `sparse_rows` JSON and the pinned `CSScodeDistance` API
- Produces: one candidate-contract JSON object with an actual returned logical vector

- [ ] **Step 1: Capture the public-fixture failures**

Run each unmodified candidate in the evaluator image against a tiny public CSS
fixture and record the traceback showing the pinned upstream `CSSCode` circular
import bug or missing `LOCheck` parameter.

- [ ] **Step 2: Apply the minimal compatibility adapter**

Import `codedistance.distance` as a module, import `CSSCode` explicitly from
`codedistance.code_library`, assign it into the distance module, set
`params["LOCheck"] = 0`, and read the returned vector from `result["L"]`.
Do not change the algorithms or iteration count.

- [ ] **Step 3: Smoke-test every adapter**

Run each candidate through `candidate-entrypoint.py` in the pinned evaluator
image on the tiny public fixture with a 30-second shell timeout.

Expected: exit 0, a completed/found contract object, and a verifier-accepted
logical witness.

- [ ] **Step 4: Append the compatibility evidence to each log**

Record only the public fixture, upstream compatibility issue, command outcome,
and runtime.  Do not record holdout identities or answers.

### Task 3: Finalize and canary-check the blinded proposal attempt

**Files:**
- Modify: `.worktrees/css-distance-proposal-001/candidate.py`
- Modify: `.worktrees/css-distance-proposal-001/LOG.md`
- Modify: `campaigns/examples/css-distance-autoresearch/README.md`

**Interfaces:**
- Consumes: blinded `proposal-workspace/candidate.py`
- Produces: root-level evaluator entrypoint with only mechanical matrix-format adaptation

- [ ] **Step 1: Add public matrix-contract smoke input**

Use a tiny CSS fixture that is not in the private issue-#38 selection.  Run the
blinded candidate unchanged and verify it fails to parse object-form JSON.

- [ ] **Step 2: Add only the missing format branches**

In `load_matrix`, recognize `dense_binary_matrix` via `payload["data"]` and
`sparse_rows` via `payload["rows"]` plus `payload["num_cols"]`.  Leave every
search heuristic unchanged.

- [ ] **Step 3: Materialize the evaluator entrypoint**

Copy the adapted candidate content to the experiment worktree root as
`candidate.py`, preserve the original proposal under `proposal-workspace/`, and
append this mechanical adaptation to `LOG.md`.

- [ ] **Step 4: Run the live containment canary**

Invoke `run_proposal_canary` with the pinned proposal image, the dedicated
public workspace, a host-only canary path, and Codex auth.  Require both host
read and outbound network attempts to report `denied`.

### Task 4: Run private screening and finalist evaluations

**Files:**
- Modify: each experiment worktree `LOG.md`
- Create: private run artifacts below the operator-only work root

**Interfaces:**
- Consumes: opaque ten-case holdout, screening seed, finalist seeds, evaluator image
- Produces: sanitized aggregate summaries and ranked candidates

- [ ] **Step 1: Verify evaluator preflight**

Run Docker daemon/image checks and require label
`org.autoqec.baseline=a4afe9c09bbf5790da9ecc05b65c5b62343979ad`.

- [ ] **Step 2: Screen all four candidates**

For each baseline and the blinded proposal, invoke
`run-css-distance-candidate --phase screening --timeout-seconds 300`.
Poll long-running commands without interrupting them.  Confirm every worktree
log receives only fields allowed by `sanitize_log_summary`.

- [ ] **Step 3: Advance accepted candidates**

Run `--phase finalists` for candidates whose screening summary is accepted.
Do not expose finalist seed or case-level output to proposal workspaces.

- [ ] **Step 4: Rank from sanitized summaries**

Order by weighted target hits, normalized quality, verified witnesses, and
runtime.  Retain timeout/crash counts as failure evidence.

### Task 5: Completion audit and campaign report

**Files:**
- Modify: `LOG.md`
- Create: `campaigns/examples/css-distance-autoresearch/results.md`

**Interfaces:**
- Consumes: survey, worktree logs, evaluator summaries, test output
- Produces: reproducible final recommendation and limitations

- [ ] **Step 1: Run focused tests**

Run: `PYTHONPATH=src python3 -m pytest -q tests/test_search_css_distance_autoresearch.py tests/test_search_css_distance_container.py tests/test_search_css_distance_eval.py tests/test_css_distance_autoresearch_campaign.py`

Expected: all focused tests pass.

- [ ] **Step 2: Run the full suite**

Run: `PYTHONPATH=src python3 -m pytest -q`

Expected: zero failures; only documented optional-backend deselections.

- [ ] **Step 3: Audit every explicit requirement**

Verify the survey predates attempts, source pin is open-source and exact,
every experiment has a worktree and log, no proposal mount reaches the holdout,
every process has a 300-second deadline, only upper bounds are claimed, and the
winner has fresh independently verified finalist evidence.

- [ ] **Step 4: Write the report and update the root log**

Document methods, aggregate results, winner, reproducibility commands,
containment evidence, and unresolved limitations without revealing private
case identities or answers to future proposal agents.

