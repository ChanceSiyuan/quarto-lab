# Issue 67 Quantum Tanner Witness-To-Autoresearch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document and test the complete quantum Tanner candidate-generator-to-witness-finder-to-autoresearch workflow for a cold local operator.

**Architecture:** Keep the existing `campaigns/examples/quantum-tanner-autoresearch/README.md` as the single workflow guide. Strengthen `tests/test_search_docs.py` with command-snippet and scientific guardrail assertions, then update the README to satisfy those tests.

**Tech Stack:** Markdown, Python pathlib/re tests, pytest, existing `autoqec_search` CLI command names.

## Global Constraints

Do not implement or change the witness finder itself.
Do not run or document cluster/SLURM execution; cluster execution remains issue #20.
Use source-checkout command blocks with `PYTHONPATH=src python3 -m autoqec_search.cli ...`.
Mention installed `autoqec-search ...` command names where useful.
Document both single-candidate witness finding and batch witness attachment.
Batch witness attachment docs must include `--timeout-seconds`, `--require-all`, and `--fail-on-skipped`.
State that upper-bound witnesses are screening evidence only and must not be promoted as exact Zoo distance evidence.
State that the current `p=0.001` memory-X screening path requires generated witnesses to be X-like for direct screening admission.
State that Z-like witnesses can be valid generic CSS witnesses but are incompatible with the current memory-X screening task.
Document inspection of `witness_finder_summary.json` and `screening.json` after partial witness attachment or screening skips/failures.

---

### Task 1: Docs Tests And Workflow README

**Files:**
- Modify: `tests/test_search_docs.py`
- Modify: `campaigns/examples/quantum-tanner-autoresearch/README.md`

**Interfaces:**
- Consumes: existing `_bash_blocks(document: str) -> list[str]` helper and `QT_WORKFLOW_DOC`.
- Produces: docs tests that fail if #67 workflow commands or guardrails are omitted.

- [ ] **Step 1: Write failing docs tests**

Add assertions in `tests/test_search_docs.py` that require:

```python
def test_quantum_tanner_autoresearch_docs_describe_witness_finder_to_autoresearch_path() -> None:
    document = QT_WORKFLOW_DOC.read_text()
    commands = "\n".join(_bash_blocks(document))

    assert "autoqec-search generate-quantum-tanner-candidates" in document
    assert "autoqec-search find-upper-bound-witness" in document
    assert "autoqec-search attach-quantum-tanner-witnesses" in document
    assert "autoqec-search run" in document
    assert "autoqec-search compare-surface-copy" in document
    assert "python3 -m autoqec_search.cli find-upper-bound-witness" in commands
    assert "--basis x" in commands
    assert "--timeout-seconds 300" in commands
    assert "--require-all" in commands
    assert "--fail-on-skipped" in commands
    assert "witness_finder_summary.json" in document
    assert "screening.json" in document
```

Extend `_assert_quantum_tanner_guardrails(document)` with exact strings for:

```python
assert "upper-bound witnesses are screening evidence only" in document
assert "must not be promoted as exact Zoo distance evidence" in document
assert "requires generated witnesses to be X-like" in document
assert "Z-like witnesses can remain valid generic CSS witnesses" in document
assert "incompatible with this memory-X screening task" in document
assert "witness_finder_summary.json" in document
assert "screening.json" in document
```

Extend the negative-control loop in
`test_quantum_tanner_autoresearch_workflow_states_scientific_guardrails` so
removing each new guardrail string fails the helper.

- [ ] **Step 2: Run red test**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py::test_quantum_tanner_autoresearch_docs_describe_witness_finder_to_autoresearch_path tests/test_search_docs.py::test_quantum_tanner_autoresearch_workflow_states_scientific_guardrails -q
```

Expected: fail because the current README does not yet include the new exact
single-candidate, installed-command, X-like basis, and summary/screening
guardrail strings.

- [ ] **Step 3: Update README workflow**

Edit `campaigns/examples/quantum-tanner-autoresearch/README.md` to:

- expand "Command Form" with installed command examples for generator, witness
  finder, batch attach, validate, run, report, and compare-surface-copy;
- add a single-candidate witness command after candidate generation:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli find-upper-bound-witness --hx benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d4/hx.json --hz benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/instances/quantum-tanner-toric-d4/hz.json --basis x --out campaigns/examples/quantum-tanner-autoresearch/witnesses/quantum-tanner-toric-d4-upper-bound-witness.json --qec-code-bin /path/to/qec-code --iterations 1000 --restarts 8 --seed 12345 --timeout-seconds 300
```

- make the batch command include `--iterations 1000 --restarts 8 --seed 12345
  --timeout-seconds 300`;
- add strict-mode command blocks showing `--require-all` and
  `--fail-on-skipped`;
- explicitly state the X-like memory-X basis policy and the Z-like generic CSS
  caveat;
- describe inspecting `witness_finder_summary.json` counts/candidates/reasons
  and run-level candidate `screening.json` files when some candidates are
  skipped or failed;
- keep the existing validation, autoresearch run, report, and surface-copy
  comparison commands.

- [ ] **Step 4: Run green docs tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py::test_quantum_tanner_autoresearch_docs_describe_witness_finder_to_autoresearch_path tests/test_search_docs.py::test_quantum_tanner_autoresearch_workflow_states_scientific_guardrails -q
```

Expected: pass.

- [ ] **Step 5: Run issue verification and full gate**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py tests/test_search_upper_bound_witness_finder.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m pytest
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit and create PR**

Commit the docs and tests on
`agent/issue-67-m3-document-and-verify-the-witness-finder-to-aut-run-1`, push
to origin, and open a pull request against `main` with `Closes #67`.

## Self-Review

The plan covers candidate generation, single-candidate witness finding, batch
witness attachment, validation, autoresearch, screening inspection,
surface-copy comparison, exact-distance warnings, X-like memory-X policy,
Z-like incompatibility, issue verification, and full pytest. No placeholders
remain.
