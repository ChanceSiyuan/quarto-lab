# Quantum Tanner Long-Running Autoresearch Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one resumable command that asks a fresh Codex CLI session for non-toric quantum Tanner proposals each round and evaluates accepted proposals through the existing upper-bound, rbposd `p=0.001`, and copied-surface pipeline.

**Architecture:** A thin Bash entry point launches a Python orchestrator. The orchestrator stores atomic JSON state outside the repository, creates an isolated clone per attempt, invokes `codex exec` with a generated response schema, and composes existing AutoQEC CLI commands for deterministic evaluation. Every model round is ephemeral; only cumulative accepted fingerprints and rejection counts cross round boundaries.

**Tech Stack:** Python 3.11, Bash, `argparse`, `dataclasses`, `json`, `pathlib`, `subprocess`, Codex CLI, existing AutoQEC CLI, pytest.

## Global Constraints

- The numerical benchmark remains `p=0.001` with suite `quantum-tanner-rbposd-p001-v1` and decoder `rbposd-osd10-v1`.
- Distance results are upper-bound screening evidence and must never be promoted as exact distance evidence.
- Every Codex proposal round uses a fresh `--ephemeral` session with `--sandbox read-only` and the generated `--output-schema`.
- The target round count is positive and finite; there is no unbounded default loop.
- A failed or interrupted attempt is preserved; resume creates a new numbered attempt and never overwrites evidence.
- The launcher test suite uses fake Codex, qec-code, and rsinter executables and must not consume live model tokens.
- Existing uncommitted changes outside the files named below must remain untouched.

---

## File Structure

- Create `src/autoqec_search/quantum_tanner_long_run.py`: typed configuration, atomic state management, subprocess orchestration, round execution, resume handling, and CLI parser.
- Create `scripts/run_quantum_tanner_autoresearch.sh`: source-checkout entry point that sets `PYTHONPATH` and executes the Python module.
- Create `tests/test_search_quantum_tanner_long_run.py`: unit tests for configuration, atomic state, cumulative feedback, historical deduplication, and attempt allocation.
- Modify `tests/test_smoke_quantum_tanner_ai_proposals_script.py`: add fake Codex and launcher-level end-to-end tests while reusing the existing fake qec-code and rsinter helpers.
- Modify `tests/test_search_docs.py`: enforce the documented launcher command, resume command, context isolation, and scientific guardrails.
- Modify `README.md`: add a concise Quantum Tanner long-run entry point.
- Modify `campaigns/examples/quantum-tanner-autoresearch/README.md`: add detailed launch, inspect, stop, resume, and token/context instructions.

---

### Task 1: Atomic Launcher State And Feedback Core

**Files:**
- Create: `src/autoqec_search/quantum_tanner_long_run.py`
- Create: `tests/test_search_quantum_tanner_long_run.py`

**Interfaces:**
- Produces: `LauncherConfig`, `initialize_state()`, `load_resume_state()`, `merge_feedback()`, `reject_historical_fingerprints()`, `allocate_attempt_dir()`, and `atomic_write_json()`.
- Consumes: only Python standard-library types and `autoqec_search.load.SearchIntegrityError`.

- [ ] **Step 1: Write failing configuration and state tests**

Create tests that pin the JSON contract and immutable scientific configuration:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_long_run import (
    LauncherConfig,
    allocate_attempt_dir,
    initialize_state,
    load_resume_state,
    merge_feedback,
    reject_historical_fingerprints,
)


def _config(*, rounds: int = 2) -> LauncherConfig:
    return LauncherConfig(
        rounds=rounds,
        proposals_per_round=2,
        max_group_order=32,
        max_physical_qubits=64,
        run_wall_clock="90s",
        model=None,
    )


def test_initialize_state_records_pinned_source_and_scientific_config(tmp_path: Path) -> None:
    state = initialize_state(tmp_path, source_root=tmp_path / "repo", source_commit="abc123", config=_config())
    persisted = json.loads((tmp_path / "state.json").read_text())
    assert state == persisted
    assert persisted["schema_version"] == 1
    assert persisted["source_commit"] == "abc123"
    assert persisted["configuration"]["run_wall_clock"] == "90s"
    assert persisted["next_round"] == 1
    assert persisted["accepted_fingerprints"] == []


def test_resume_allows_round_target_growth_but_rejects_scientific_drift(tmp_path: Path) -> None:
    initialize_state(tmp_path, source_root=tmp_path / "repo", source_commit="abc123", config=_config())
    resumed = load_resume_state(tmp_path, config=_config(rounds=5))
    assert resumed["target_rounds"] == 5
    with pytest.raises(SearchIntegrityError, match="configuration drift: max_group_order"):
        load_resume_state(
            tmp_path,
            config=LauncherConfig(5, 2, 48, 64, "90s", None),
        )


def test_attempt_allocation_preserves_previous_attempts(tmp_path: Path) -> None:
    first = allocate_attempt_dir(tmp_path, round_number=1)
    second = allocate_attempt_dir(tmp_path, round_number=1)
    assert first.name == "attempt-001"
    assert second.name == "attempt-002"
    assert first.is_dir() and second.is_dir()


def test_feedback_merge_is_cumulative_and_historical_duplicates_fail() -> None:
    merged = merge_feedback(
        {"accepted_fingerprints": ["fp-a"], "rejection_kinds": {"BadGroup": 1}},
        {"accepted_fingerprints": ["fp-b"], "rejection_kinds": {"BadGroup": 2, "BadCode": 1}},
    )
    assert merged == {
        "accepted_fingerprints": ["fp-a", "fp-b"],
        "rejection_kinds": {"BadCode": 1, "BadGroup": 3},
    }
    with pytest.raises(SearchIntegrityError, match="historical proposal fingerprint"):
        reject_historical_fingerprints(["fp-a", "fp-c"], {"fp-a"})
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_long_run.py -q
```

Expected: collection fails because `autoqec_search.quantum_tanner_long_run` does not exist.

- [ ] **Step 3: Implement the state contract**

Implement the following exact public shapes in `quantum_tanner_long_run.py`:

```python
@dataclass(frozen=True)
class LauncherConfig:
    rounds: int
    proposals_per_round: int
    max_group_order: int
    max_physical_qubits: int
    run_wall_clock: str
    model: str | None

    def scientific_dict(self) -> dict[str, object]:
        return {
            "proposals_per_round": self.proposals_per_round,
            "max_group_order": self.max_group_order,
            "max_physical_qubits": self.max_physical_qubits,
            "run_wall_clock": self.run_wall_clock,
            "model": self.model,
        }
```

Validate all integer fields as positive and validate `run_wall_clock` with the same positive-duration syntax accepted by `autoqec-search run`. Implement atomic JSON writes by writing a sibling `.<name>.tmp` file, flushing and `os.fsync()`-ing it, and replacing the destination with `Path.replace()`.

The initial state must contain:

```python
{
    "schema_version": 1,
    "source_root": str(source_root.resolve()),
    "source_commit": source_commit,
    "configuration": config.scientific_dict(),
    "target_rounds": config.rounds,
    "completed_rounds": [],
    "next_round": 1,
    "accepted_fingerprints": [],
    "rejection_kinds": {},
    "status": "running",
}
```

`load_resume_state()` must require `schema_version == 1`, compare every key in `scientific_dict()`, reject a target lower than the number of completed rounds, update only `target_rounds`, and write the result atomically.

`merge_feedback()` must return a sorted unique fingerprint list and summed, key-sorted rejection counts. `reject_historical_fingerprints()` must report the sorted intersection. `allocate_attempt_dir()` must create `rounds/round-NNNN/attempt-NNN` without deleting existing directories.

- [ ] **Step 4: Run state tests and verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_long_run.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the state core**

```bash
git add src/autoqec_search/quantum_tanner_long_run.py tests/test_search_quantum_tanner_long_run.py
git commit -m "feat: add quantum Tanner long-run state"
```

---

### Task 2: One-Round Codex And Numerical Pipeline

**Files:**
- Modify: `src/autoqec_search/quantum_tanner_long_run.py`
- Create: `scripts/run_quantum_tanner_autoresearch.sh`
- Modify: `tests/test_smoke_quantum_tanner_ai_proposals_script.py`

**Interfaces:**
- Consumes: Task 1 state helpers and existing `autoqec_search.cli` subcommands.
- Produces: executable launcher, `main(argv: list[str] | None = None) -> int`, one completed attempt with proposal, run, surface comparison, and feedback evidence.

- [ ] **Step 1: Add a fake Codex and a failing one-round launcher test**

Extend the existing smoke test module with `_write_fake_codex()`. The executable must assert the launcher supplied `exec`, `--ephemeral`, `--sandbox read-only`, `--output-schema`, `--output-last-message`, and a stdin prompt containing `round 1`, `non-toric`, `inverse-closed`, and `local parity-check`. It writes a response envelope containing the committed valid C8 proposal fixture to the requested output path.

Add this test:

```python
def test_long_run_launcher_completes_one_round_with_fake_tools(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    (repo / "uncommitted-operator-note.txt").write_text("not part of the run\n")
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    result = subprocess.run(
        [
            str(repo / "scripts" / "run_quantum_tanner_autoresearch.sh"),
            "--work-root", str(work_root),
            "--rounds", "1",
            "--proposals-per-round", "1",
            "--max-group-order", "32",
            "--max-physical-qubits", "64",
            "--run-wall-clock", "90s",
        ],
        cwd=repo,
        env={
            **_script_env(bin_dir, rsinter_name="custom-rsinter"),
            "CODEX_BIN": str(codex_bin),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "source checkout is dirty; uncommitted changes are excluded" in result.stderr
    state = json.loads((work_root / "state.json").read_text())
    assert state["status"] == "completed"
    assert state["next_round"] == 2
    attempt = work_root / "rounds" / "round-0001" / "attempt-001"
    status = json.loads((attempt / "status.json").read_text())
    assert status["status"] == "completed"
    assert status["accepted"] == 1
    assert Path(status["feedback_json"]).is_file()
    assert Path(status["surface_copy_json"]).is_file()
    assert not (attempt / "checkout" / "uncommitted-operator-note.txt").exists()


def test_long_run_all_invalid_response_completes_without_numerical_run(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run-invalid"
    result = subprocess.run(
        [
            str(repo / "scripts" / "run_quantum_tanner_autoresearch.sh"),
            "--work-root", str(work_root),
            "--rounds", "1",
            "--proposals-per-round", "1",
            "--max-group-order", "32",
            "--max-physical-qubits", "64",
            "--run-wall-clock", "90s",
        ],
        cwd=repo,
        env={
            **_script_env(bin_dir, rsinter_name="custom-rsinter"),
            "CODEX_BIN": str(codex_bin),
            "FAKE_CODEX_INVALID_ONLY": "1",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    attempt = work_root / "rounds" / "round-0001" / "attempt-001"
    status = json.loads((attempt / "status.json").read_text())
    assert status["status"] == "completed"
    assert status["accepted"] == 0
    assert status["run_root"] is None
    assert not (attempt / "checkout" / ".worktrees").exists()
```

- [ ] **Step 2: Run the launcher test and verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_long_run_launcher_completes_one_round_with_fake_tools -q
```

Expected: FAIL because `scripts/run_quantum_tanner_autoresearch.sh` does not exist.

- [ ] **Step 3: Add the shell entry point**

Create an executable script with this complete behavior:

```bash
#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
export PYTHONPATH="$SOURCE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m autoqec_search.quantum_tanner_long_run --source-root "$SOURCE_ROOT" "$@"
```

Mark it executable with `chmod +x scripts/run_quantum_tanner_autoresearch.sh`
before running the launcher test.

- [ ] **Step 4: Implement tool resolution and one-round orchestration**

Add the `Toolchain` value object:

```python
@dataclass(frozen=True)
class Toolchain:
    codex: str
    qec_code: str
    rsinter: str
```

Implement these public signatures exactly: `resolve_executable(configured:
str, *, label: str) -> str`, `run_command(command: list[str], *, cwd: Path,
env: dict[str, str], log_path: Path, stdin_text: str | None = None) -> None`,
`run_attempt(source_root: Path, work_root: Path, state: dict[str, Any], config:
LauncherConfig, tools: Toolchain) -> dict[str, Any]`, `build_parser() ->
argparse.ArgumentParser`, and `main(argv: list[str] | None = None) -> int`.

`resolve_executable()` must accept an executable path or resolve a command name with `shutil.which()`. Before creating state, run `codex --version`, `qec-code --version`, and `rsinter --version`, capturing versions in the attempt status.

For one attempt, execute these stages and atomically rewrite `status.json` after each stage:

1. clone `source_root` to `attempt/checkout` with `git clone --quiet --local`, checkout `state["source_commit"]`, and configure a local AutoQEC git identity;
2. run `prepare-quantum-tanner-ai-batch` into `attempt/request`, always passing `work_root/cumulative-feedback.json`;
3. save `attempt/agent-prompt.md` by appending round-specific non-toric, inverse-closed generator, local parity-check, unique-ID, and historical-fingerprint instructions to `request/prompt.md`;
4. invoke Codex with `exec --ephemeral --sandbox read-only -C <checkout> --output-schema <schema> --output-last-message <response.json> -`, adding `--model` only when configured;
5. ingest into `attempt/ingested`, read `summary.json`, and reject historical fingerprints before invoking qec-code;
6. when accepted is zero, merge ingestion feedback and complete the round without numerical work;
7. remove the cloned campaign `search_space.json`, materialize all accepted proposal paths into the campaign `proposal-instances` directory, and import them into a newly created search space;
8. for each imported candidate, call `find-upper-bound-witness` with basis X, 1000 iterations, 8 restarts, seed 12345, and timeout 300 seconds; then set `upper_bound_witness_path` in the search-space JSON;
9. call `complete-quantum-tanner-proposal-observables --basis x --force`, validate the workspace, commit generated inputs, and run campaign `quantum-tanner-autoresearch` using `random-window-upper-bound` and run id `qt-long-rNNNN-aNNN`;
10. run `compare-surface-copy` with `benchmarks/baselines/rotated-surface-single-logical-p001.json` and `summarize-quantum-tanner-ai-feedback` into the finalized run root;
11. merge feedback into cumulative state, append a completed-round record, increment `next_round`, and atomically update top-level state.

Create `work_root/tool-shims/rsinter` as a symlink to the resolved rsinter executable and prepend the shim directory plus the qec-code directory to PATH for all AutoQEC commands. Every AutoQEC subprocess must set `PYTHONPATH=<checkout>/src`.

- [ ] **Step 5: Run the one-round test and verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_long_run_launcher_completes_one_round_with_fake_tools -q
```

Expected: PASS and no live Codex call.

- [ ] **Step 6: Commit the one-round launcher**

```bash
git add src/autoqec_search/quantum_tanner_long_run.py scripts/run_quantum_tanner_autoresearch.sh tests/test_smoke_quantum_tanner_ai_proposals_script.py
git commit -m "feat: launch quantum Tanner AI autoresearch"
```

---

### Task 3: Multi-Round Feedback, Failure Preservation, And Resume

**Files:**
- Modify: `src/autoqec_search/quantum_tanner_long_run.py`
- Modify: `tests/test_search_quantum_tanner_long_run.py`
- Modify: `tests/test_smoke_quantum_tanner_ai_proposals_script.py`

**Interfaces:**
- Consumes: Task 2 launcher and attempt status contract.
- Produces: cumulative two-round execution, signal-aware failures, historical duplicate gate, and `--resume` attempt allocation.

- [ ] **Step 1: Add failing two-round and resume tests**

Make fake Codex emit structurally valid cyclic C8 in round 1 and cyclic C10 in round 2, while recording each prompt in a call-log directory. Add tests asserting:

```python
def _run_long_launcher(
    repo: Path,
    *,
    bin_dir: Path,
    codex_bin: Path,
    work_root: Path,
    rounds: int,
    extra_env: dict[str, str] | None = None,
    resume: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(repo / "scripts" / "run_quantum_tanner_autoresearch.sh"),
        "--work-root", str(work_root),
        "--rounds", str(rounds),
        "--proposals-per-round", "1",
        "--max-group-order", "32",
        "--max-physical-qubits", "64",
        "--run-wall-clock", "90s",
    ]
    if resume:
        command.append("--resume")
    env = {
        **_script_env(bin_dir, rsinter_name="custom-rsinter"),
        "CODEX_BIN": str(codex_bin),
        **(extra_env or {}),
    }
    return subprocess.run(
        command,
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


def test_long_run_launcher_uses_fresh_codex_rounds_and_cumulative_feedback(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    call_log = tmp_path / "codex-calls"
    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=2,
        extra_env={"CODEX_CALL_LOG": str(call_log)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    state = json.loads((work_root / "state.json").read_text())
    first_prompt = (call_log / "001.prompt").read_text()
    second_prompt = (call_log / "002.prompt").read_text()
    first_fingerprint = state["completed_rounds"][0]["accepted_fingerprints"][0]
    assert "accepted_fingerprints\": []" in first_prompt
    assert "accepted_fingerprints" in second_prompt
    assert first_fingerprint in second_prompt
    assert (work_root / "rounds" / "round-0002" / "attempt-001").is_dir()
    assert len(state["completed_rounds"]) == 2


def test_resume_preserves_failed_attempt_and_creates_next_attempt(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    call_log = tmp_path / "codex-calls"
    first = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={
            "FAKE_CODEX_FAIL_ON_CALL": "1",
            "CODEX_CALL_LOG": str(call_log),
        },
    )
    assert first.returncode != 0
    round_root = work_root / "rounds" / "round-0001"
    failed_status = json.loads(
        (round_root / "attempt-001" / "status.json").read_text()
    )
    assert failed_status["status"] == "failed"
    resumed = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={"CODEX_CALL_LOG": str(call_log)},
        resume=True,
    )
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert (round_root / "attempt-001" / "status.json").is_file()
    assert (round_root / "attempt-002" / "status.json").is_file()
    assert json.loads((round_root / "attempt-002" / "status.json").read_text())["status"] == "completed"


def test_historical_duplicate_stops_before_qec_code(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "long-run"
    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=2,
        extra_env={
            "FAKE_CODEX_REPEAT": "1",
            "CODEX_CALL_LOG": str(tmp_path / "codex-calls"),
        },
    )
    assert result.returncode != 0
    assert "historical proposal fingerprint" in result.stderr
    second_checkout = (
        work_root
        / "rounds"
        / "round-0002"
        / "attempt-001"
        / "checkout"
    )
    assert not (
        second_checkout
        / "campaigns"
        / "examples"
        / "quantum-tanner-autoresearch"
        / "proposal-instances"
    ).exists()
```

Add a unit test that catches SIGINT handling through a directly invoked `mark_attempt_interrupted()` helper and verifies it preserves all previous status keys while setting `status: interrupted`.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_long_run.py \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py \
  -k 'long_run or attempt' -q
```

Expected: new multi-round, resume, or duplicate assertions fail.

- [ ] **Step 3: Implement the outer loop and resume behavior**

`main()` must:

```python
while int(state["next_round"]) <= int(state["target_rounds"]):
    attempt_result = run_attempt(source_root, work_root, state, config, tools)
    state = complete_round(work_root, state, attempt_result)
state["status"] = "completed"
atomic_write_json(work_root / "state.json", state)
```

On a new run, reject a non-empty work root. On resume, require existing
`state.json`, load the pinned source commit and scientific config, and allocate
the next attempt number for `state["next_round"]`. Do not reuse an existing
checkout or delete any attempt path.

Wrap each attempt in `try/except BaseException`. For ordinary failures, write
`status: failed`, `failed_stage`, `error_kind`, and `message`, then re-raise.
Install SIGINT/SIGTERM handlers only while an attempt is active; they call
`mark_attempt_interrupted(status_path, signal_name)` and then raise
`KeyboardInterrupt`.

When a round completes, write cumulative feedback first, then state. The
completed-round record must contain round number, attempt number, accepted
fingerprints, accepted and rejected counts, proposal summary path, and nullable
run/feedback/surface paths.

- [ ] **Step 4: Run multi-round and resume tests and verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_long_run.py \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit multi-round resilience**

```bash
git add src/autoqec_search/quantum_tanner_long_run.py tests/test_search_quantum_tanner_long_run.py tests/test_smoke_quantum_tanner_ai_proposals_script.py
git commit -m "feat: resume quantum Tanner proposal rounds"
```

---

### Task 4: Operator Documentation And Help Contract

**Files:**
- Modify: `README.md`
- Modify: `campaigns/examples/quantum-tanner-autoresearch/README.md`
- Modify: `tests/test_search_docs.py`

**Interfaces:**
- Consumes: final launcher option names and output contract.
- Produces: copy-paste start/resume commands and automated documentation checks.

- [ ] **Step 1: Add failing documentation assertions**

Add:

```python
LONG_RUN_SCRIPT = REPO_ROOT / "scripts" / "run_quantum_tanner_autoresearch.sh"


def test_quantum_tanner_docs_describe_long_running_codex_launcher() -> None:
    root_readme = (REPO_ROOT / "README.md").read_text()
    workflow = QT_WORKFLOW_DOC.read_text()
    assert LONG_RUN_SCRIPT.is_file()
    assert "scripts/run_quantum_tanner_autoresearch.sh" in root_readme
    assert "--work-root /tmp/autoqec-qt-long" in workflow
    assert "--rounds 20" in workflow
    assert "--proposals-per-round 4" in workflow
    assert "--run-wall-clock 30m" in workflow
    assert "--resume" in workflow
    assert "codex exec --ephemeral" in workflow
    assert "fresh Codex context" in workflow
    assert "does not consume Codex tokens" in workflow
    assert "upper-bound screening evidence" in workflow
    assert "state.json" in workflow
    assert "cumulative-feedback.json" in workflow
```

- [ ] **Step 2: Run docs test and verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py::test_quantum_tanner_docs_describe_long_running_codex_launcher -q
```

Expected: FAIL because the README text is absent.

- [ ] **Step 3: Document the launcher**

Add a short root README subsection that links to
`campaigns/examples/quantum-tanner-autoresearch/README.md` and shows the launcher
name.

Add a detailed `Long-Running AI Autoresearch` section near the top of the
campaign README with:

```bash
codex login status

QEC_CODE_BIN=/Users/nzy/rcode/rstim/target/release/qec-code \
RSINTER_BIN=/Users/nzy/rcode/rstim/target/release/rsinter \
scripts/run_quantum_tanner_autoresearch.sh \
  --work-root /tmp/autoqec-qt-long \
  --rounds 20 \
  --proposals-per-round 4 \
  --max-group-order 64 \
  --max-physical-qubits 512 \
  --run-wall-clock 30m
```

Document Ctrl-C stopping and the exact resume form:

```bash
QEC_CODE_BIN=/Users/nzy/rcode/rstim/target/release/qec-code \
RSINTER_BIN=/Users/nzy/rcode/rstim/target/release/rsinter \
scripts/run_quantum_tanner_autoresearch.sh \
  --work-root /tmp/autoqec-qt-long \
  --rounds 20 \
  --proposals-per-round 4 \
  --max-group-order 64 \
  --max-physical-qubits 512 \
  --run-wall-clock 30m \
  --resume
```

Explain that each round uses a fresh Codex context, only cumulative structured
feedback crosses rounds, and waiting on qec-code/rsinter does not consume Codex
tokens. Show the `rounds/round-NNNN/attempt-NNN` layout and point operators to
`status.json`, finalized `report.html`, `surface-copy-comparison.html`, and
`quantum-tanner-ai-feedback.html`.

- [ ] **Step 4: Verify launcher help and docs**

Run:

```bash
scripts/run_quantum_tanner_autoresearch.sh --help
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py -q
```

Expected: help exits 0 and all docs tests pass.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md campaigns/examples/quantum-tanner-autoresearch/README.md tests/test_search_docs.py
git commit -m "docs: explain long-running quantum Tanner search"
```

---

### Task 5: Full Verification, Merge, And Push

**Files:**
- Verify all files changed by Tasks 1-4.
- Preserve: unrelated working-tree changes.

**Interfaces:**
- Consumes: complete feature branch.
- Produces: verified `main` containing the degenerate-face fix, launcher, tests, and documentation.

- [ ] **Step 1: Run targeted launcher and AI proposal tests**

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_long_run.py \
  tests/test_search_quantum_tanner_ai_handoff.py \
  tests/test_search_quantum_tanner_proposals.py \
  tests/test_search_quantum_tanner_proposal_materialization.py \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py \
  tests/test_search_docs.py \
  -q
```

Expected: zero failures.

- [ ] **Step 2: Run workspace validation and shell checks**

```bash
bash -n scripts/run_quantum_tanner_autoresearch.sh
git diff --check
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: shell syntax valid, no whitespace errors, workspace validation exits 0.

- [ ] **Step 3: Re-run the real numerical smoke**

```bash
QEC_CODE_BIN=/Users/nzy/rcode/rstim/target/release/qec-code \
RSINTER_BIN=/Users/nzy/rcode/rstim/target/release/rsinter \
scripts/smoke_quantum_tanner_ai_proposals.sh \
  --work-root /tmp/autoqec-qt-ai-merge-$(date +%Y%m%d-%H%M%S)
```

Expected: `PASS quantum_tanner_ai_proposal_smoke`, one non-toric candidate, `p=0.001`, surface comparison OK, and feedback OK.

- [ ] **Step 4: Review commit scope**

```bash
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
```

Expected: only the approved degenerate-face fix, design/plan, launcher, tests, and README changes are committed. The pre-existing unstaged smoke-script edit remains unstaged.

- [ ] **Step 5: Merge and verify on main**

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git merge --ff-only codex/fix-qt-ai-degenerate-face
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_long_run.py \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py \
  tests/test_search_docs.py \
  -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: fast-forward merge and zero verification failures.

- [ ] **Step 6: Push main**

```bash
git push origin main
```

Expected: `origin/main` advances to the verified local main commit.
