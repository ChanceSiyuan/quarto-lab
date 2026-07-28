# Quantum Tanner Candidates CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stable end-to-end `generate-quantum-tanner-candidates` CLI and workflow docs for issue #60.

**Architecture:** Reuse the existing quantum Tanner generator APIs from `src/autoqec_search/quantum_tanner_generator.py`. Add a thin operator-facing CLI command in `src/autoqec_search/cli.py` that applies CLI overrides, resolves materialization tools to explicit paths, calls the existing materializing generation path by default, and renders a candidate-oriented summary.

**Tech Stack:** Python 3, argparse, pytest, existing Rust `autoqec-distance-ladder` binary, existing fake `qec-code` shell fixture helpers.

## Global Constraints

- Preserve the existing `generate-quantum-tanner-sweep` command as a lower-level command.
- Add `generate-quantum-tanner-candidates` with `--root`, required `--config`, optional `--qec-code-bin`, optional `--dry-run`, and optional `--force`.
- Non-dry-run candidate generation must write specs, a distance-ladder manifest, materialized instance artifacts, `fixture_catalog.json`-compatible catalog output, and `search_space.json`.
- Dry-run candidate generation must print planned candidates and paths without writing specs, manifest, matrices, catalog, or search-space files.
- Terminal summary must list candidate ids, `n`, `k`, distance labels, and output paths.
- Materialization failures must fail before reporting completed generation and must name the failed materialization step.
- README must explain the generator workflow and state that witness finding is separate later work.
- Keep generated files deterministic and reviewable in git diffs.
- Do not implement witness search, rbposd benchmarking, or surface-copy comparison changes.

---

### Task 1: Add The End-To-End Candidate CLI

**Files:**
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_quantum_tanner_generator.py`

**Interfaces:**
- Consumes: `load_quantum_tanner_sweep_config(Path) -> QuantumTannerSweepConfig`, `generate_quantum_tanner_sweep(repo_root, config, dry_run, materialize, force) -> QuantumTannerGenerationPlan`, and `render_quantum_tanner_generation_summary(plan, dry_run=...) -> str`.
- Produces: CLI command `generate-quantum-tanner-candidates` and helper functions in `cli.py` for qec-code override, exporter resolution, and candidate summary rendering.

- [ ] **Step 1: Write failing tests for the new command**

Add tests to `tests/test_search_quantum_tanner_generator.py` near the existing CLI tests:

```python
def _run_generate_candidates_cli(
    root: Path,
    config_path: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "generate-quantum-tanner-candidates",
            "--root",
            str(root),
            "--config",
            str(config_path),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        env=env,
    )
```

Then add:

```python
def test_cli_generate_quantum_tanner_candidates_dry_run_plans_without_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path.parent
    config_path = _write_config(tmp_path / "qt-sweep.json", _temp_generation_payload(tmp_path))

    result = _run_generate_candidates_cli(root, config_path, "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "would generate 2 quantum Tanner candidates" in result.stdout
    assert "candidate_ids: [4, 6]" in result.stdout
    assert "quantum-tanner-toric-d4" in result.stdout
    assert "n=16" in result.stdout
    assert "k=2" in result.stdout
    assert "distance_label=d4" in result.stdout
    assert "quantum-tanner-toric-d6" in result.stdout
    assert "n=36" in result.stdout
    assert "distance_label=d6" in result.stdout
    assert not (tmp_path / "generated-ladder.json").exists()
    assert not (tmp_path / "generated_fixture_catalog.json").exists()
    assert not (tmp_path.parent / "campaigns" / tmp_path.name / "search_space.json").exists()
    for distance in (4, 6):
        assert not (
            tmp_path / "generated" / "quantum_tanner_specs" / f"toric-d{distance}.json"
        ).exists()
        instance_dir = tmp_path / "instances" / f"quantum-tanner-toric-d{distance}"
        assert not (instance_dir / "instance.json").exists()
        assert not (instance_dir / "hx.json").exists()
        assert not (instance_dir / "hz.json").exists()
```

```python
def test_cli_generate_quantum_tanner_candidates_materializes_and_validates_root(
    tmp_path: Path,
) -> None:
    work_root = _copy_generation_workspace(GENERATED_QT_ROOT / "cli-candidates")
    config_path = _write_config(
        tmp_path / "qt-sweep.json",
        _workspace_generation_payload(work_root, qec_code_bin="qec-code"),
    )
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")

    result = _run_generate_candidates_cli(
        work_root,
        config_path,
        "--qec-code-bin",
        str(fake_qec_code),
        "--force",
    )

    assert result.returncode == 0, result.stderr
    assert "generated 2 quantum Tanner candidates" in result.stdout
    assert "candidate_ids: [4, 6]" in result.stdout
    assert "emitted fixture_catalog:" in result.stdout
    assert "emitted search_space:" in result.stdout
    assert (work_root / "benchmarks/distance_ladders/generated-quantum-tanner.json").is_file()
    assert (
        work_root
        / "campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json"
    ).is_file()
    assert (
        work_root / "campaigns/examples/quantum-tanner-autoresearch/search_space.json"
    ).is_file()
    for distance in (4, 6):
        candidate_id = f"quantum-tanner-toric-d{distance}"
        instance_dir = (
            work_root / "benchmarks/distance_ladders/generated-quantum-tanner/instances" / candidate_id
        )
        assert (instance_dir / "instance.json").is_file()
        assert (instance_dir / "hx.json").is_file()
        assert (instance_dir / "hz.json").is_file()
    assert main(["validate", "--root", str(work_root)]) == 0
```

```python
def test_cli_generate_quantum_tanner_candidates_broken_qec_code_fails_materialization(
    tmp_path: Path,
) -> None:
    work_root = _copy_generation_workspace(GENERATED_QT_ROOT / "cli-broken")
    config_path = _write_config(
        tmp_path / "qt-sweep.json",
        _workspace_generation_payload(work_root, qec_code_bin="qec-code"),
    )
    broken_qec_code = _write_fake_qec_code(tmp_path / "bad-qec-code", wrong_hx_width=True)

    result = _run_generate_candidates_cli(
        work_root,
        config_path,
        "--qec-code-bin",
        str(broken_qec_code),
        "--force",
    )

    assert result.returncode != 0
    assert "distance-ladder exporter failed" in result.stderr
    assert "expected num_cols=16" in result.stderr
    assert "generated 2 quantum Tanner candidates" not in result.stdout
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
```

Expected: FAIL because argparse rejects `generate-quantum-tanner-candidates` as an unknown command.

- [ ] **Step 3: Implement CLI helpers and parser wiring**

In `src/autoqec_search/cli.py`, import `os` and `shutil`, then add helpers near `_default_provenance_path`:

```python
def _is_explicit_tool_path(value: str) -> bool:
    path = Path(value)
    if path.is_absolute():
        return True
    separators = {os.sep}
    if os.altsep is not None:
        separators.add(os.altsep)
    return any(separator in value for separator in separators)


def _resolve_distance_ladder_exporter_bin(root: Path, configured: str) -> str:
    if _is_explicit_tool_path(configured):
        return configured
    found = shutil.which(configured)
    if found:
        return found
    checkout_binary = root / "target" / "debug" / configured
    if checkout_binary.is_file():
        return str(checkout_binary)
    raise SearchIntegrityError(
        "distance-ladder materialization requires autoqec-distance-ladder; "
        f"could not resolve {configured!r} on PATH or at {checkout_binary}"
    )
```

Add a summary helper:

```python
def _render_quantum_tanner_candidate_generation_summary(
    plan: Any,
    *,
    dry_run: bool,
) -> str:
    action = "would generate" if dry_run else "generated"
    distances = [entry["expected_distance"] for entry in plan.manifest["entries"]]
    lines = [
        f"{action} {len(plan.manifest['entries'])} quantum Tanner candidates for {plan.manifest['id']}",
        "candidate_ids: [" + ", ".join(str(distance) for distance in distances) + "]",
        f"manifest_path: {plan.manifest_path}",
    ]
    for entry in plan.manifest["entries"]:
        candidate_id = entry["instance_id"]
        distance = entry["expected_distance"]
        lines.extend(
            [
                f"- {candidate_id}",
                f"  n={entry['n']}",
                f"  k={entry['k']}",
                f"  distance_label=d{distance}",
                f"  quantum_tanner_spec: {entry['quantum_tanner_spec']}",
                f"  instance_dir: {plan.manifest['artifact_root']}/{candidate_id}",
            ]
        )
    if plan.materialization is not None:
        lines.extend(
            [
                f"materialized {len(plan.manifest['entries'])} quantum Tanner instances",
                "exporter_command: " + " ".join(plan.materialization.command),
            ]
        )
    if plan.autoresearch_files is not None:
        lines.extend(
            [
                f"emitted fixture_catalog: {plan.autoresearch_files.catalog_path}",
                f"emitted search_space: {plan.autoresearch_files.search_space_path}",
            ]
        )
    return "\n".join(lines) + "\n"
```

Add parser wiring beside `generate-quantum-tanner-sweep`:

```python
    generate_qt_candidates_parser = subparsers.add_parser(
        "generate-quantum-tanner-candidates",
        help="Generate materialized quantum Tanner candidates and autoresearch inputs",
    )
    generate_qt_candidates_parser.add_argument("--root", default=".")
    generate_qt_candidates_parser.add_argument("--config", required=True)
    generate_qt_candidates_parser.add_argument("--qec-code-bin", default=None)
    generate_qt_candidates_parser.add_argument("--dry-run", action="store_true")
    generate_qt_candidates_parser.add_argument("--force", action="store_true")
```

Add command handling in `main` before `preflight`:

```python
        if args.command == "generate-quantum-tanner-candidates":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            config = load_quantum_tanner_sweep_config(Path(args.config))
            if args.qec_code_bin is not None:
                if not args.qec_code_bin:
                    raise SearchIntegrityError("qec_code_bin must be a non-empty string")
                config = replace(config, qec_code_bin=args.qec_code_bin)
            if not args.dry_run:
                if not _is_explicit_tool_path(config.qec_code_bin):
                    raise SearchIntegrityError(
                        "qec_code_bin must be an explicit path for generate-quantum-tanner-candidates"
                    )
                config = replace(
                    config,
                    distance_ladder_exporter_bin=_resolve_distance_ladder_exporter_bin(
                        root,
                        config.distance_ladder_exporter_bin,
                    ),
                )
            plan = generate_quantum_tanner_sweep(
                root,
                config,
                dry_run=args.dry_run,
                materialize=True,
                force=args.force,
            )
            print(
                _render_quantum_tanner_candidate_generation_summary(
                    plan,
                    dry_run=args.dry_run,
                ),
                end="",
            )
            return 0
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/cli.py tests/test_search_quantum_tanner_generator.py
git commit -m "feat: add quantum tanner candidates cli"
```

---

### Task 2: Document The Generator Workflow

**Files:**
- Modify: `campaigns/examples/quantum-tanner-autoresearch/README.md`
- Modify: `tests/test_search_docs.py`

**Interfaces:**
- Consumes: CLI command from Task 1.
- Produces: README generator workflow with runnable bash command blocks and a docs regression test.

- [ ] **Step 1: Write failing docs test**

Add to `tests/test_search_docs.py`:

```python
def test_quantum_tanner_autoresearch_docs_describe_candidate_generator() -> None:
    document = QT_WORKFLOW_DOC.read_text()
    blocks = _bash_blocks(document)
    commands = "\n".join(blocks)

    assert "generate-quantum-tanner-candidates" in document
    assert "campaigns/examples/quantum-tanner-autoresearch/generator.json" in document
    assert "python3 -m autoqec_search.cli generate-quantum-tanner-candidates --root ." in commands
    assert "--dry-run" in commands
    assert "--qec-code-bin /path/to/qec-code" in commands
    assert "--force" in commands
    assert "PYTHONPATH=src python3 -m autoqec_search.cli validate --root ." in commands
    assert "witness finding is a separate later step" in document

    for block in blocks:
        assert "<" not in block
        assert ">" not in block
```

- [ ] **Step 2: Run docs test and verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py::test_quantum_tanner_autoresearch_docs_describe_candidate_generator -q
```

Expected: FAIL because the README does not yet mention `generate-quantum-tanner-candidates`.

- [ ] **Step 3: Update README**

In `campaigns/examples/quantum-tanner-autoresearch/README.md`, add a generator section before the current preflight section. Use `/path/to/qec-code` exactly because the existing docs test disallows angle-bracket placeholders:

````markdown
## 1. Generate Candidate Inputs

The committed fixture files are review fixtures. To regenerate the quantum
Tanner autoresearch inputs from the sweep config, first preview the exact
candidate ids and output paths:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli generate-quantum-tanner-candidates --root . --config campaigns/examples/quantum-tanner-autoresearch/generator.json --dry-run
```

The dry run prints the planned `[4, 6]` distance ladder candidates and does not
write specs, matrix artifacts, the fixture catalog, or the search space.

After reviewing the preview, run the materializing command with an explicit
`qec-code` executable:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli generate-quantum-tanner-candidates --root . --config campaigns/examples/quantum-tanner-autoresearch/generator.json --qec-code-bin /path/to/qec-code --force
```

This writes generated toric specs, the distance-ladder manifest, finite CSS
instance artifacts, `fixture_catalog.json`-compatible catalog output, and the
campaign `search_space.json`. Validate the generated workspace before any run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

The generator does not find or install upper-bound witnesses. Witness finding
is a separate later step; candidate generation only creates search-ready finite
CSS inputs when the sweep config and materialization artifacts are valid.
````

Renumber the existing workflow sections so the old `## 1. Preflight` becomes
`## 2. Preflight`, and continue the sequence.

- [ ] **Step 4: Run docs tests and verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add campaigns/examples/quantum-tanner-autoresearch/README.md tests/test_search_docs.py
git commit -m "docs: document quantum tanner candidate generation"
```
