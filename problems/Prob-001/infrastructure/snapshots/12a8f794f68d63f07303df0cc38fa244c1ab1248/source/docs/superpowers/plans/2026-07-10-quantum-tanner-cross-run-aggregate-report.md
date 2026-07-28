# Quantum Tanner Cross-Run Aggregate Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Automatically maintain an append-ordered campaign-level Quantum Tanner results ledger and English HTML report across every terminal attempt in one launcher --work-root.

**Architecture:** Add a focused quantum_tanner_aggregate module that owns ledger persistence, stage-tolerant candidate normalization, HTML rendering, and compact AI history. The long-run launcher calls that module after terminal attempts and during resume reconciliation; per-run reports and the generic search report path remain unchanged.

**Tech Stack:** Python 3 standard library, existing autoqec_search helpers, pytest, fake Codex/qec-code/rsinter subprocess integration tests, self-contained HTML/CSS.

## Global Constraints

- Aggregation is scoped to one --work-root; there is no machine-global index.
- aggregate/results.jsonl preserves creation order and never content-deduplicates, groups, reorders, edits, or deletes code rows.
- Operational replay protection may identify an installed attempt batch by (attempt_key, candidate_ordinal).
- Every accepted code is recorded, including evaluated, skipped, failed, and interrupted statuses; pre-acceptance rejections are excluded.
- Failed and skipped codes are included in the next AI prompt history and historical fingerprint enforcement set.
- Matrices with at most 64 binary entries are shown to AI; larger matrices use dimensions and canonical SHA-256.
- Aggregate HTML is English-only, self-contained, offline-safe, and atomically regenerated.
- Source-run frontier membership is recorded without performing a new cross-run ranking.
- Random-window upper bounds remain screening evidence, never exact distance.
- Existing per-run report.html and construction-definitions.html behavior remains unchanged.
- Aggregate directories must be real directories, and existing ledger/state/report files must be single-link regular files; unsafe aliases fail without modifying external targets.

---

## File Structure

- Create src/autoqec_search/quantum_tanner_aggregate.py for aggregate persistence, collection, rendering, history, and reconciliation.
- Create tests/test_search_quantum_tanner_aggregate.py for focused unit coverage.
- Modify src/autoqec_search/quantum_tanner_long_run.py for lifecycle integration.
- Modify tests/test_search_quantum_tanner_long_run.py for launcher error-path unit coverage.
- Modify tests/test_smoke_quantum_tanner_ai_proposals_script.py for fake-tool integration coverage.
- Modify campaigns/examples/quantum-tanner-autoresearch/README.md, README.md, CLAUDE.md, and tests/test_search_docs.py for operator documentation.

---

### Task 1: Durable Append-Ordered Ledger

**Files:**
- Create: src/autoqec_search/quantum_tanner_aggregate.py
- Create: tests/test_search_quantum_tanner_aggregate.py

**Interfaces:**
- Produces: AggregatePaths, AggregateUpdate, aggregate_paths(work_root), initialize_aggregate(work_root), load_aggregate_records(work_root), append_attempt_records(work_root, attempt_key, records).
- Consumes: SearchIntegrityError from autoqec_search.load; it must not import the launcher.

- [ ] **Step 1: Write failing ledger tests**

Create tests/test_search_quantum_tanner_aggregate.py with:

~~~python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.quantum_tanner_aggregate import (
    aggregate_paths,
    append_attempt_records,
    initialize_aggregate,
    load_aggregate_records,
)


def _record(candidate_id: str, fingerprint: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "proposal_fingerprint": fingerprint,
        "candidate_ordinal": 0,
        "status": "evaluated",
    }


def test_initialize_aggregate_writes_empty_durable_files(tmp_path: Path) -> None:
    update = initialize_aggregate(tmp_path)
    paths = aggregate_paths(tmp_path)

    assert update.appended_records == 0
    assert paths.ledger.read_text() == ""
    assert json.loads(paths.state.read_text()) == {
        "installed_attempts": {},
        "next_sequence": 1,
        "schema_version": 1,
    }
    assert paths.report.is_file()


def test_append_preserves_order_and_matching_visible_content(tmp_path: Path) -> None:
    initialize_aggregate(tmp_path)
    append_attempt_records(
        tmp_path, "round-0001/attempt-001",
        [_record("same-visible-code", "fp-a")],
    )
    append_attempt_records(
        tmp_path, "round-0002/attempt-001",
        [_record("same-visible-code", "fp-b")],
    )

    records = load_aggregate_records(tmp_path)
    assert [record["sequence"] for record in records] == [1, 2]
    assert [record["proposal_fingerprint"] for record in records] == ["fp-a", "fp-b"]


def test_replaying_installed_attempt_is_operational_noop(tmp_path: Path) -> None:
    initialize_aggregate(tmp_path)
    first = append_attempt_records(
        tmp_path, "round-0001/attempt-001", [_record("candidate-a", "fp-a")]
    )
    replay = append_attempt_records(
        tmp_path, "round-0001/attempt-001", [_record("candidate-a", "fp-a")]
    )

    assert first.appended_records == 1
    assert replay.appended_records == 0
    assert len(load_aggregate_records(tmp_path)) == 1


def test_initialize_rejects_symlinked_aggregate_without_touching_target(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_text("keep\n")
    (tmp_path / "aggregate").symlink_to(external, target_is_directory=True)

    with pytest.raises(SearchIntegrityError, match="unsafe aggregate directory"):
        initialize_aggregate(tmp_path)

    assert sentinel.read_text() == "keep\n"
    assert sorted(path.name for path in external.iterdir()) == ["sentinel.txt"]
~~~

- [ ] **Step 2: Run the tests and verify the missing-module failure**

Run:

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_aggregate.py -q
~~~

Expected: collection fails with ModuleNotFoundError for autoqec_search.quantum_tanner_aggregate.

- [ ] **Step 3: Implement paths and atomic persistence**

Create the module with these public types and the atomic text primitive:

~~~python
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from autoqec_search.load import SearchIntegrityError


AGGREGATE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AggregatePaths:
    root: Path
    ledger: Path
    report: Path
    state: Path


@dataclass(frozen=True)
class AggregateUpdate:
    appended_records: int
    ledger_path: Path
    report_path: Path


def aggregate_paths(work_root: Path) -> AggregatePaths:
    root = Path(work_root).resolve() / "aggregate"
    return AggregatePaths(
        root=root,
        ledger=root / "results.jsonl",
        report=root / "report.html",
        state=root / "state.json",
    )


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        tmp_path.unlink(missing_ok=True)
~~~

Implement load_aggregate_records with line-numbered JSON/schema validation. initialize_aggregate writes empty results.jsonl, schema-1 state, and a valid empty HTML report only when missing. append_attempt_records must:

1. validate unique integer candidate_ordinal values in the incoming batch;
2. assign attempt_key and monotonically increasing sequence;
3. atomically replace the prior-plus-new JSONL;
4. render report.html;
5. atomically update state.json;
6. scan ledger attempt keys before trusting state, so a crash between ledger and state writes repairs the checkpoint without replay.

Use the state shape shown in the failing test. Distinct attempts with matching visible code fields remain distinct records.

Before any read or write, validate aggregate/ with `os.lstat` as a real
directory. Validate each existing ledger, report, and state path as a regular
file with `st_nlink == 1`; open reads with `O_NOFOLLOW` where supported. Mirror
the launcher error wording `unsafe aggregate directory` and
`unsafe aggregate file` so alias failures are concise and testable.

- [ ] **Step 4: Run focused tests**

Run:

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_aggregate.py -q
~~~

Expected: 4 passed.

- [ ] **Step 5: Commit**

~~~bash
git add src/autoqec_search/quantum_tanner_aggregate.py tests/test_search_quantum_tanner_aggregate.py
git commit -m "feat: add quantum tanner aggregate ledger"
~~~

---

### Task 2: Stage-Tolerant Attempt Collector

**Files:**
- Modify: src/autoqec_search/quantum_tanner_aggregate.py
- Modify: tests/test_search_quantum_tanner_aggregate.py

**Interfaces:**
- Consumes: Task 1 APIs and describe_local_code(matrix) from autoqec_search.quantum_tanner_report.
- Produces: collect_attempt_records(attempt_dir) and install_terminal_attempt(work_root, attempt_dir).

Import `datetime` and `timezone` from `datetime`; all ledger timestamps use UTC
with a trailing `Z`.

- [ ] **Step 1: Add failing collector fixtures**

Add a fixture that creates an accepted proposal even when no numerical artifacts exist:

~~~python
def _write_accepted_attempt(
    attempt_dir: Path,
    *,
    terminal_status: str,
    stage: str,
    candidate_id: str = "candidate-a",
) -> None:
    accepted = attempt_dir / "ingested" / "accepted"
    accepted.mkdir(parents=True)
    proposal = {
        "schema_version": 1,
        "proposal_id": candidate_id,
        "base_group": {"name": "D4", "order": 8},
        "a_generator_indices": [4, 6],
        "b_generator_indices": [5, 7],
        "local_codes": {
            "field": "GF(2)",
            "matrix_role": "parity_check",
            "h_a": [[1, 1]],
            "h_b": [[1, 1]],
        },
    }
    proposal_path = accepted / f"000-{candidate_id}.json"
    proposal_path.write_text(json.dumps(proposal))
    summary_path = attempt_dir / "ingested" / "summary.json"
    summary_path.write_text(json.dumps({
        "accepted": 1,
        "accepted_fingerprints": ["fp-a"],
        "accepted_records": [{
            "fingerprint": "fp-a",
            "path": f"accepted/000-{candidate_id}.json",
            "proposal_id": candidate_id,
            "proposal_index": 0,
        }],
        "rejected": 0,
    }))
    (attempt_dir / "status.json").write_text(json.dumps({
        "accepted": 1,
        "accepted_fingerprints": ["fp-a"],
        "attempt": 1,
        "attempt_dir": str(attempt_dir),
        "proposal_summary_path": str(summary_path),
        "round": 1,
        "run_root": None,
        "source_commit": "abc123",
        "stage": stage,
        "status": terminal_status,
    }))
~~~

Add this failure-stage assertion:

~~~python
def test_collector_keeps_ingested_candidate_after_materialization_failure(tmp_path: Path) -> None:
    attempt = tmp_path / "rounds" / "round-0001" / "attempt-001"
    _write_accepted_attempt(attempt, terminal_status="failed", stage="failed")

    record = collect_attempt_records(attempt)[0]

    assert record["candidate_id"] == "candidate-a"
    assert record["proposal_fingerprint"] == "fp-a"
    assert record["status"] == "failed"
    assert record["construction"]["base_group"] == {"name": "D4", "order": 8}
    assert record["construction"]["local_code_a"]["label"] == "Rep(2) [2,1,2]"
    assert record["code"]["n"] is None
~~~

Add an evaluated fixture under checkout/.worktrees/run/results/search/quantum-tanner-autoresearch/run with:

- candidates/candidate-a/artifacts/instance.json containing derived_properties n=8 and k=2;
- screening.json containing admitted and distance_upper_bound=2;
- a completed evaluation manifest containing 0 errors, 64 shots, LER 0, CI 0 to 0.056626, and 1.25 seconds;
- frontier.json naming candidate-a.

Assert status evaluated, code equals n=8/k=2/rate=0.25, benchmark shots=64, X upper bound=2, and source_run_frontier is true.

Add separate cases for screening skipped, witness summary failed, a noncompleted
rsinter manifest becoming a failed row, terminal interrupted, and rejected-only
accepted=0 returning no records.

- [ ] **Step 2: Run and verify undefined collector APIs**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_aggregate.py -q
~~~

Expected: failures state collect_attempt_records and install_terminal_attempt are undefined.

- [ ] **Step 3: Implement proposal-first normalization**

Implement `_load_json_object(path, label)` so it raises `SearchIntegrityError`
for a missing, malformed, or non-object JSON file. Implement
`_proposal_record(accepted, proposal)` from the accepted-record metadata and
proposal JSON. Implement `_overlay_materialized_instance`, `_overlay_witness`,
and `_overlay_run_candidate` as optional-file readers: a missing optional file
returns without mutation, while a present malformed file raises a path-specific
`SearchIntegrityError`. These helpers mutate only the `code`, `screening`,
`benchmark`, `source_run_frontier`, `artifacts`, `status`, and `reason` fields
of the normalized record shown below.

The normalized record must have these stable keys:

~~~python
{
    "schema_version": 1,
    "candidate_ordinal": accepted_record["proposal_index"],
    "candidate_id": accepted_record["proposal_id"],
    "proposal_fingerprint": accepted_record["fingerprint"],
    "round": status["round"],
    "attempt": status["attempt"],
    "source_commit": status["source_commit"],
    "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "status": "failed",
    "stage": status["stage"],
    "reason": status.get("message"),
    "construction": {
        "base_group": {"name": group.get("name"), "order": group.get("order")},
        "a_generator_indices": proposal.get("a_generator_indices"),
        "b_generator_indices": proposal.get("b_generator_indices"),
        "h_a": local_codes.get("h_a"),
        "h_b": local_codes.get("h_b"),
        "local_code_a": describe_local_code(local_codes["h_a"]),
        "local_code_b": describe_local_code(local_codes["h_b"]),
    },
    "code": {"n": None, "k": None, "rate": None},
    "screening": {"status": None, "reason": None, "x_upper_bound": None},
    "benchmark": None,
    "source_run_frontier": False,
    "artifacts": {"report": None, "definitions": None},
}
~~~

Overlay later-stage evidence without requiring it. A completed manifest makes the row evaluated. A screening skip makes it skipped. A witness failure, terminal failure, interruption, or accepted code absent from a completed run remains visible with its typed reason. install_terminal_attempt rejects nonterminal status and otherwise calls collect then Task 1 append.

- [ ] **Step 4: Run aggregate tests**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_aggregate.py -q
~~~

Expected: all collector and ledger tests pass.

- [ ] **Step 5: Commit**

~~~bash
git add src/autoqec_search/quantum_tanner_aggregate.py tests/test_search_quantum_tanner_aggregate.py
git commit -m "feat: collect terminal quantum tanner attempts"
~~~

---

### Task 3: Aggregate HTML And AI History

**Files:**
- Modify: src/autoqec_search/quantum_tanner_aggregate.py
- Modify: tests/test_search_quantum_tanner_aggregate.py

**Interfaces:**
- Consumes: normalized records from Task 2.
- Produces: render_aggregate_report_html(records), write_aggregate_report(work_root), candidate_history_prompt(work_root), historical_fingerprints(work_root).

- [ ] **Step 1: Add failing report tests**

Build four full records with evaluated, skipped, failed, and interrupted statuses, append them, then assert:

~~~python
html = aggregate_paths(tmp_path).report.read_text()
assert html.count('data-candidate-row="true"') == 4
for heading in (
    "Round / attempt", "Finite code / candidate", "Status / reason",
    "Base group", "A / B generators", "Local classical code",
    "CSS parameters", "Code rate", "X upper bound", "Screening",
    "errors / shots", "LER", "95% CI", "Decoding time", "Source artifacts",
):
    assert heading in html
for status in ("evaluated", "skipped", "failed", "interrupted"):
    assert f'class="badge {status}"' in html
assert "Zero observed errors do not prove a zero logical error rate" in html
assert not re.search(r"[\u3400-\u9fff，。；：！？【】（）]", html)
~~~

Also assert:

- missing values render em dashes;
- candidate strings are HTML-escaped;
- report and definition links are relative to aggregate/report.html;
- source-run frontier is labeled without any aggregate winner claim;
- summary cards count completed rounds, total codes, evaluated, skipped, failed/interrupted, and source-run frontier rows.

- [ ] **Step 2: Add failing AI-history tests**

~~~python
history = candidate_history_prompt(tmp_path)
assert "small-code" in history
assert "fp-small" in history
assert "failed" in history
assert '"h_a": [[1, 1]]' in history
assert '"h_a_dimensions": [1, 65]' in history
assert '"h_a_sha256":' in history
assert historical_fingerprints(tmp_path) == {"fp-small", "fp-large"}
~~~

The large fixture uses h_a=[[1] * 65]. Include skipped and failed rows so both must appear.

- [ ] **Step 3: Run and verify renderer/history failures**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_aggregate.py -q
~~~

Expected: the temporary report lacks the table and history APIs are undefined.

- [ ] **Step 4: Implement renderer and history compaction**

render_aggregate_report_html must escape cells, render six cards and the 15 approved columns, use status-specific badges, embed ledger JSON, and include exactly:

~~~text
Zero observed errors do not prove a zero logical error rate; use the recorded 95% confidence interval. X upper bounds are randomized screening evidence, not exact code distances.
~~~

Use relative links:

~~~python
def _relative_artifact_href(report_path: Path, artifact: object) -> str | None:
    if not isinstance(artifact, str) or not artifact:
        return None
    return os.path.relpath(Path(artifact), start=report_path.parent)
~~~

Use deterministic matrix compaction:

~~~python
def _matrix_history(matrix: object, *, label: str) -> dict[str, object]:
    if not isinstance(matrix, list) or not matrix:
        return {label: None}
    cells = sum(len(row) for row in matrix if isinstance(row, list))
    if cells <= 64:
        return {label: matrix}
    canonical = json.dumps(matrix, separators=(",", ":"), sort_keys=True).encode()
    return {
        f"{label}_dimensions": [len(matrix), len(matrix[0])],
        f"{label}_sha256": hashlib.sha256(canonical).hexdigest(),
    }
~~~

candidate_history_prompt emits an English heading, compact ordered JSON, and an instruction not to repeat listed IDs, fingerprints, group/generator sets, or local codes. historical_fingerprints returns all nonempty ledger fingerprints regardless of status. append_attempt_records refreshes HTML after ledger replacement and before state checkpoint.

- [ ] **Step 5: Run and commit**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_aggregate.py -q
git add src/autoqec_search/quantum_tanner_aggregate.py tests/test_search_quantum_tanner_aggregate.py
git commit -m "feat: render quantum tanner aggregate history"
~~~

Expected: all aggregate unit tests pass before commit.

---

### Task 4: Successful Launcher Integration And Duplicate Guard

**Files:**
- Modify: src/autoqec_search/quantum_tanner_long_run.py around initialize_state, run_attempt, and _run_locked_launcher.
- Modify: tests/test_smoke_quantum_tanner_ai_proposals_script.py around existing one-round, two-round, and historical-duplicate tests.

**Interfaces:**
- Consumes: aggregate_paths, initialize_aggregate, install_terminal_attempt, candidate_history_prompt, historical_fingerprints.
- Produces: automatic successful append, state path discovery, stdout paths, prompt history, and aggregate-backed hard duplicate guard.

- [ ] **Step 1: Add failing one-round expectations**

Extend test_long_run_launcher_completes_one_round_with_fake_tools:

~~~python
aggregate = work_root / "aggregate"
records = [
    json.loads(line)
    for line in (aggregate / "results.jsonl").read_text().splitlines()
]
assert len(records) == 1
assert records[0]["status"] == "evaluated"
assert records[0]["benchmark"]["shots"] == 64
assert (aggregate / "report.html").read_text().count(
    'data-candidate-row="true"'
) == 1
assert state["aggregate_ledger"] == str(aggregate / "results.jsonl")
assert state["aggregate_report"] == str(aggregate / "report.html")
assert f"aggregate_report={aggregate / 'report.html'}" in result.stdout
~~~

Extend the existing two-round test to require two ledger rows in round order and the first fingerprint in the second saved Codex prompt.

Change the historical-duplicate smoke test to empty accepted_fingerprints in both state.json and cumulative-feedback.json before resume. Assert the aggregate still blocks the repeat before materialization/backend calls and the ledger row count does not change.

- [ ] **Step 2: Run focused smoke tests and verify failure**

~~~bash
PYTHONPATH=src python3 -m pytest \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_long_run_launcher_completes_one_round_with_fake_tools \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_long_run_launcher_uses_fresh_codex_rounds_and_cumulative_feedback \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_cumulative_feedback_ahead_of_state_blocks_historical_duplicate \
  -q
~~~

Expected: aggregate paths, second-prompt history, and aggregate duplicate guard assertions fail.

- [ ] **Step 3: Initialize and advertise the aggregate**

Import the aggregate APIs. For a new run call initialize_aggregate and persist:

~~~python
paths = aggregate_paths(work_root)
state["aggregate_ledger"] = str(paths.ledger)
state["aggregate_report"] = str(paths.report)
~~~

Before each successful launcher return print:

~~~python
print(f"aggregate_ledger={paths.ledger}")
print(f"aggregate_report={paths.report}")
~~~

- [ ] **Step 4: Feed history to Codex and enforce aggregate fingerprints**

Before round requirements append:

~~~python
prompt += "\n" + candidate_history_prompt(work_root)
~~~

After ingestion build the hard guard set:

~~~python
historical = (
    set(state_feedback["accepted_fingerprints"])
    | set(cumulative_feedback["accepted_fingerprints"])
    | historical_fingerprints(work_root)
)
reject_historical_fingerprints(accepted_fingerprints, historical)
~~~

Run this guard while the parsed ingestion values are still local variables.
Only after it passes may the launcher assign `status["accepted"]`,
`status["accepted_fingerprints"]`, `status["proposal_summary_path"]`, and
`status["rejected"]`. Therefore a historical repeat is rejected before campaign
acceptance and the exception-path collector sees no accepted batch to append.

After persisting completed status, call install_terminal_attempt before returning. A zero-accepted attempt installs an empty operational batch while leaving the candidate ledger empty.

- [ ] **Step 5: Run focused and unit tests**

~~~bash
PYTHONPATH=src python3 -m pytest \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_long_run_launcher_completes_one_round_with_fake_tools \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_long_run_launcher_uses_fresh_codex_rounds_and_cumulative_feedback \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_cumulative_feedback_ahead_of_state_blocks_historical_duplicate \
  tests/test_search_quantum_tanner_aggregate.py \
  tests/test_search_quantum_tanner_long_run.py \
  -q
~~~

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

~~~bash
git add src/autoqec_search/quantum_tanner_long_run.py tests/test_smoke_quantum_tanner_ai_proposals_script.py
git commit -m "feat: aggregate quantum tanner launcher rounds"
~~~

---

### Task 5: Failure, Interruption, And Resume Reconciliation

**Files:**
- Modify: src/autoqec_search/quantum_tanner_aggregate.py
- Modify: src/autoqec_search/quantum_tanner_long_run.py in exception and resume paths.
- Modify: tests/test_search_quantum_tanner_aggregate.py
- Modify: tests/test_search_quantum_tanner_long_run.py
- Modify: tests/test_smoke_quantum_tanner_ai_proposals_script.py

**Interfaces:**
- Produces: reconcile_terminal_attempts(work_root), attempt_dir/aggregate-error.json diagnostics, primary-error preservation, and report-only resume/backfill.

- [ ] **Step 1: Add a failing terminal-scan test**

~~~python
def test_reconcile_terminal_attempts_installs_failed_and_interrupted_batches(tmp_path: Path) -> None:
    initialize_aggregate(tmp_path)
    failed = tmp_path / "rounds" / "round-0001" / "attempt-001"
    interrupted = tmp_path / "rounds" / "round-0001" / "attempt-002"
    _write_accepted_attempt(failed, terminal_status="failed", stage="failed")
    _write_accepted_attempt(
        interrupted, terminal_status="interrupted", stage="prompted"
    )

    update = reconcile_terminal_attempts(tmp_path)

    assert update.appended_records == 2
    assert [record["status"] for record in load_aggregate_records(tmp_path)] == [
        "failed", "interrupted"
    ]
~~~

Add a launcher unit test that makes the primary attempt path raise RuntimeError("backend broke") and the aggregate hook raise SearchIntegrityError("aggregate broke"). Assert backend broke remains primary and aggregate-error.json records the aggregate error.

- [ ] **Step 2: Add failing witness-backend and backfill integration tests**

Teach the fake qec-code executable to exit 23 for only the
`code css-distance random-window-upper-bound` invocation when
`FAKE_QEC_CODE_WITNESS_FAIL=1`; materialization must still succeed. Add a test
that runs one accepted proposal with that variable and asserts:

~~~python
def test_long_run_appends_witness_failed_code_before_returning_nonzero(tmp_path: Path) -> None:
    repo = _copy_repo(tmp_path)
    bin_dir = _write_fake_tools(tmp_path, rsinter_name="custom-rsinter")
    codex_bin = _write_fake_codex(bin_dir, repo)
    work_root = tmp_path / "failed-aggregate"
    result = _run_long_launcher(
        repo,
        bin_dir=bin_dir,
        codex_bin=codex_bin,
        work_root=work_root,
        rounds=1,
        extra_env={"FAKE_QEC_CODE_WITNESS_FAIL": "1"},
    )

    assert result.returncode != 0
    records = [
        json.loads(line)
        for line in (work_root / "aggregate" / "results.jsonl").read_text().splitlines()
    ]
    assert len(records) == 1
    assert records[0]["candidate_id"] == "ai-valid-dihedral-d3"
    assert records[0]["status"] == "failed"
    assert "witness" in records[0]["reason"]
    assert 'class="badge failed"' in (
        work_root / "aggregate" / "report.html"
    ).read_text()
~~~

Add test_resume_rebuilds_missing_aggregate_without_rerunning_tools:

1. complete one round;
2. record Codex and backend logs;
3. delete aggregate/;
4. invoke the same work root with --resume and --rounds 1;
5. assert the aggregate is rebuilt and tool logs are byte-identical.

- [ ] **Step 3: Run and verify failures**

~~~bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_aggregate.py \
  tests/test_search_quantum_tanner_long_run.py \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_long_run_appends_witness_failed_code_before_returning_nonzero \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_resume_rebuilds_missing_aggregate_without_rerunning_tools \
  -q
~~~

Expected: reconciliation and failure/backfill assertions fail.

- [ ] **Step 4: Implement terminal scanning and resume-before-preflight**

reconcile_terminal_attempts initializes a missing aggregate, scans sorted rounds/round-NNNN/attempt-NNN/status.json, accepts completed/failed/interrupted terminal statuses, and installs each batch in filesystem order.

Call it on resume after state validation but before the early completed-target return and before tool preflight. This guarantees report-only backfill does not invoke Codex, qec-code, or rsinter.

- [ ] **Step 5: Aggregate exceptions without masking primary failure**

After persisting terminal attempt status in run_attempt:

~~~python
try:
    install_terminal_attempt(work_root, attempt_dir)
except BaseException as aggregate_exc:
    atomic_write_json(
        attempt_dir / "aggregate-error.json",
        {
            "attempt_key": _completed_attempt_id(round_number, attempt_number),
            "error_kind": type(aggregate_exc).__name__,
            "message": str(aggregate_exc),
        },
    )
raise
~~~

The bare raise remains tied to the original attempt exception. If aggregation alone fails after a successful terminal attempt, let it stop the launcher so resume retries before new AI work.

- [ ] **Step 6: Run and commit**

~~~bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_aggregate.py \
  tests/test_search_quantum_tanner_long_run.py \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_long_run_appends_witness_failed_code_before_returning_nonzero \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py::test_resume_rebuilds_missing_aggregate_without_rerunning_tools \
  -q
git add \
  src/autoqec_search/quantum_tanner_aggregate.py \
  src/autoqec_search/quantum_tanner_long_run.py \
  tests/test_search_quantum_tanner_aggregate.py \
  tests/test_search_quantum_tanner_long_run.py \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py
git commit -m "fix: reconcile terminal quantum tanner aggregates"
~~~

Expected: all selected tests pass before commit.

---

### Task 6: Documentation And Full Verification

**Files:**
- Modify: campaigns/examples/quantum-tanner-autoresearch/README.md around durable outputs.
- Modify: README.md long-running Quantum Tanner entry.
- Modify: CLAUDE.md long-running Quantum Tanner guidance.
- Modify: tests/test_search_docs.py long-run documentation test.

**Interfaces:**
- Consumes: stable paths and behavior from Tasks 1-5.
- Produces: copy-paste operator documentation and complete regression evidence.

- [ ] **Step 1: Add failing documentation assertions**

~~~python
for document in (workflow, readme, claude):
    assert "aggregate/report.html" in document
assert "aggregate/results.jsonl" in workflow
assert "one finite code per row" in workflow
assert "evaluated, skipped, failed, and interrupted" in workflow
assert "before the next Codex proposal" in workflow
assert "--resume" in workflow
~~~

- [ ] **Step 2: Run and verify docs failure**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py -q
~~~

Expected: aggregate path and automatic-history assertions fail.

- [ ] **Step 3: Update operator docs**

Document these stable paths:

~~~text
<work-root>/aggregate/report.html
<work-root>/aggregate/results.jsonl
~~~

Explain append order, included statuses, rejection exclusion, pre-Codex candidate history, hard fingerprint guard, and --resume rebuilding a missing aggregate without repeating numerical work when source HEAD still matches the pinned commit. Add concise references from README.md and CLAUDE.md.

- [ ] **Step 4: Run focused feature verification**

~~~bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_aggregate.py \
  tests/test_search_quantum_tanner_long_run.py \
  tests/test_smoke_quantum_tanner_ai_proposals_script.py \
  tests/test_search_quantum_tanner_report.py \
  tests/test_search_docs.py \
  -q
~~~

Expected: all selected tests pass.

- [ ] **Step 5: Run repository-wide verification**

~~~bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m pytest -q
git diff --check
~~~

Expected: validation succeeds, the complete suite passes with only documented skips/deselections, and git diff --check prints nothing.

- [ ] **Step 6: Commit docs**

~~~bash
git add \
  campaigns/examples/quantum-tanner-autoresearch/README.md \
  README.md \
  CLAUDE.md \
  tests/test_search_docs.py
git commit -m "docs: explain quantum tanner aggregate report"
~~~

- [ ] **Step 7: Inspect final state**

~~~bash
git log --oneline -8
git status --short
~~~

Expected: task commits appear in order and the worktree is clean.
