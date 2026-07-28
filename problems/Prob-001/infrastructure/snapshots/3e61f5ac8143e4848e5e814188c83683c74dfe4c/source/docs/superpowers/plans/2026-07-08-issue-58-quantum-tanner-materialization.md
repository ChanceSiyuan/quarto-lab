# Issue 58 Quantum Tanner Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize generated quantum Tanner candidates into `instance.json`, `hx.json`, and `hz.json` by invoking the existing Rust distance-ladder exporter.

**Architecture:** Extend the existing Python quantum Tanner generator with an optional post-generation materialization step. The step shells out to an explicit `autoqec-distance-ladder` exporter binary, passes the generated manifest and configured qec-code binary, records subprocess output, and reports success only after the exporter completes.

**Tech Stack:** Python 3.14, stdlib `dataclasses`, `json`, `pathlib`, `subprocess`, existing Rust `autoqec-distance-ladder` binary, pytest, cargo integration tests.

## Global Constraints

- Reuse `autoqec-distance-ladder export` for materialization; do not duplicate qec-code matrix command construction in Python.
- Keep `qec_code_bin` explicit and pass it through to the exporter as `--qec-code-bin`.
- Keep overwrite policy explicit through a Python `force` argument and CLI `--force`; include `--force` in the exporter command only when requested.
- The existing default generator behavior remains spec/manifest generation only; materialization is opt-in through `materialize=True` or CLI `--materialize`.
- Dry-run must not write specs, manifests, or instances and must not invoke the exporter.
- Exporter failures must raise `SearchIntegrityError` and include the failed exporter command plus stdout and stderr.
- A failed exporter run must not return a successful generation plan.
- Do not emit `fixture_catalog.json` or `search_space.json`.
- Required issue verification is `PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q` and `cargo test distance_ladder --quiet`.
- Required Agent Desk verification also includes `PYTHONPATH=src python3 -m pytest`.

---

## File Structure

- Modify `src/autoqec_search/quantum_tanner_generator.py`: add exporter-bin config normalization, subprocess result dataclass, materialization command builder/runner, opt-in materialization parameters, and summary output.
- Modify `src/autoqec_search/cli.py`: add `--materialize`, `--distance-ladder-exporter-bin`, and `--force` flags to `generate-quantum-tanner-sweep`.
- Modify `tests/fixtures/quantum_tanner_sweep/good.json`: include the default exporter bin so validation and summary cover it.
- Modify `tests/test_search_quantum_tanner_generator.py`: add fake qec-code helpers, exporter binary discovery/build helper, API materialization tests, negative-control failure test, and CLI materialization test.

### Task 1: Red Tests For Exporter-Based Materialization

**Files:**
- Modify: `tests/fixtures/quantum_tanner_sweep/good.json`
- Modify: `tests/test_search_quantum_tanner_generator.py`

**Interfaces:**
- Consumes: existing `generate_quantum_tanner_sweep(repo_root, config, dry_run=False)`.
- Produces expected API:
  `generate_quantum_tanner_sweep(repo_root, config, dry_run=False, materialize=True, force=True)`.
- Produces expected config field: `QuantumTannerSweepConfig.distance_ladder_exporter_bin`.

- [ ] **Step 1: Add the default exporter bin to the fixture**

Patch `tests/fixtures/quantum_tanner_sweep/good.json` so the object includes:

```json
"distance_ladder_exporter_bin": "autoqec-distance-ladder"
```

- [ ] **Step 2: Add test helpers**

Add imports:

```python
import shutil
```

Update the generator imports to include the existing public functions. Add this helper to locate a runnable exporter binary for tests:

```python
def _distance_ladder_exporter_bin() -> Path:
    binary = REPO_ROOT / "target" / "debug" / "autoqec-distance-ladder"
    if not binary.exists():
        subprocess.run(
            ["cargo", "build", "--bin", "autoqec-distance-ladder", "--quiet"],
            cwd=REPO_ROOT,
            check=True,
        )
    return binary
```

Add a fake qec-code writer that supports success and wrong-width modes:

```python
def _write_fake_qec_code(path: Path, *, wrong_hx_width: bool = False) -> Path:
    wrong_flag = "1" if wrong_hx_width else "0"
    path.write_text(
        f"""#!/bin/sh
set -eu
if [ "$1" != "code" ] || [ "$2" != "css" ] || [ "$3" != "quantum-tanner" ]; then
  echo "unexpected qec-code args: $*" >&2
  exit 9
fi
spec="$5"
matrix="$6"
distance="$(basename "$spec" .json | sed 's/toric-d//')"
n=$((distance * distance))
if [ "{wrong_flag}" = "1" ] && [ "$matrix" = "hx" ]; then
  n=$((n + 1))
fi
case "$matrix" in
  hx)
    printf '{{"format":"sparse_rows","num_cols":%s,"rows":[[0,1]]}}\\n' "$n"
    ;;
  hz)
    printf '{{"format":"sparse_rows","num_cols":%s,"rows":[[2,3]]}}\\n' "$n"
    ;;
  *)
    echo "unexpected matrix: $matrix" >&2
    exit 9
    ;;
esac
""",
    )
    path.chmod(0o755)
    return path
```

- [ ] **Step 3: Add the materialization API test**

Append:

```python
def test_generation_materializes_instances_through_distance_ladder_exporter(tmp_path: Path) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
        )
    )

    plan = generate_quantum_tanner_sweep(
        tmp_path.parent,
        config,
        dry_run=False,
        materialize=True,
        force=True,
    )

    assert plan.materialization is not None
    assert plan.materialization.returncode == 0
    assert "autoqec-distance-ladder" in plan.materialization.command[0]
    for candidate in config.candidates:
        instance_dir = tmp_path.parent / candidate.instance_dir
        assert (instance_dir / "instance.json").is_file()
        assert (instance_dir / "hx.json").is_file()
        assert (instance_dir / "hz.json").is_file()
        instance = json.loads((instance_dir / "instance.json").read_text())
        assert instance["qec_code_spec"] == candidate.qec_code_spec
        assert instance["quantum_tanner_spec"].endswith(
            f"generated/quantum_tanner_specs/toric-d{candidate.distance}.json"
        )
```

- [ ] **Step 4: Add the negative-control API test**

Append:

```python
def test_generation_materialization_failure_surfaces_exporter_output_and_returns_no_plan(tmp_path: Path) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "bad-qec-code", wrong_hx_width=True)
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
        )
    )

    with pytest.raises(SearchIntegrityError) as excinfo:
        generate_quantum_tanner_sweep(
            tmp_path.parent,
            config,
            dry_run=False,
            materialize=True,
            force=True,
        )

    message = str(excinfo.value)
    assert "distance-ladder exporter failed" in message
    assert "command:" in message
    assert "stdout:" in message
    assert "stderr:" in message
    assert "expected num_cols=16" in message
```

- [ ] **Step 5: Add the CLI materialization test**

Change `_run_generate_cli` to accept optional extra args:

```python
def _run_generate_cli(
    config_path: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    root = config_path.parent.parent
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "generate-quantum-tanner-sweep",
            "--config",
            str(config_path),
            "--root",
            str(root),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        env=env,
    )
```

Append:

```python
def test_cli_materializes_quantum_tanner_sweep(tmp_path: Path) -> None:
    fake_qec_code = _write_fake_qec_code(tmp_path / "qec-code")
    config_path = _write_config(
        tmp_path / "qt-sweep.json",
        _temp_generation_payload(
            tmp_path,
            qec_code_bin=str(fake_qec_code),
            distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
        ),
    )

    result = _run_generate_cli(config_path, "--materialize", "--force")

    assert result.returncode == 0, result.stderr
    assert "materialized 2 quantum Tanner instances" in result.stdout
    assert (tmp_path / "instances" / "quantum-tanner-toric-d4" / "instance.json").is_file()
    assert (tmp_path / "instances" / "quantum-tanner-toric-d6" / "hz.json").is_file()
```

- [ ] **Step 6: Run focused tests to verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
```

Expected: FAIL because `distance_ladder_exporter_bin`, `materialize`, `force`, and `materialization` do not exist yet.

### Task 2: Implement Materialization And CLI Flags

**Files:**
- Modify: `src/autoqec_search/quantum_tanner_generator.py`
- Modify: `src/autoqec_search/cli.py`

**Interfaces:**
- Produces: `MaterializationResult(command: tuple[str, ...], returncode: int, stdout: str, stderr: str)`.
- Produces: `QuantumTannerGenerationPlan.materialization: MaterializationResult | None`.
- Produces: `materialize_quantum_tanner_sweep(plan, config, force=False) -> MaterializationResult`.
- Extends: `generate_quantum_tanner_sweep(..., materialize=False, force=False)`.

- [ ] **Step 1: Add config and plan fields**

In `src/autoqec_search/quantum_tanner_generator.py`, import `subprocess`.

Add:

```python
DEFAULT_DISTANCE_LADDER_EXPORTER_BIN = "autoqec-distance-ladder"


@dataclass(frozen=True)
class MaterializationResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
```

Add `distance_ladder_exporter_bin: str` to `QuantumTannerSweepConfig`.
Add `materialization: MaterializationResult | None = None` to
`QuantumTannerGenerationPlan`.

In `normalize_quantum_tanner_sweep_config`, parse:

```python
distance_ladder_exporter_bin = normalized_payload.get(
    "distance_ladder_exporter_bin",
    DEFAULT_DISTANCE_LADDER_EXPORTER_BIN,
)
if not isinstance(distance_ladder_exporter_bin, str) or not distance_ladder_exporter_bin:
    raise SearchIntegrityError("distance_ladder_exporter_bin must be a non-empty string")
```

Include the field in the returned config and add this line to
`render_quantum_tanner_sweep_summary`:

```python
f"distance_ladder_exporter_bin: {config.distance_ladder_exporter_bin}",
```

- [ ] **Step 2: Add exporter command construction and failure formatting**

Add:

```python
def _exporter_command(
    plan: QuantumTannerGenerationPlan,
    config: QuantumTannerSweepConfig,
    *,
    force: bool,
) -> tuple[str, ...]:
    command = (
        config.distance_ladder_exporter_bin,
        "export",
        "--manifest",
        str(plan.manifest_path),
        "--qec-code-bin",
        config.qec_code_bin,
    )
    if force:
        command = (*command, "--force")
    return command
```

Add:

```python
def _format_exporter_failure(command: tuple[str, ...], result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        [
            "distance-ladder exporter failed",
            "command: " + " ".join(command),
            f"exit_code: {result.returncode}",
            "stdout:",
            result.stdout.rstrip(),
            "stderr:",
            result.stderr.rstrip(),
        ]
    )
```

- [ ] **Step 3: Implement materialization runner**

Add:

```python
def materialize_quantum_tanner_sweep(
    plan: QuantumTannerGenerationPlan,
    config: QuantumTannerSweepConfig,
    *,
    force: bool = False,
) -> MaterializationResult:
    command = _exporter_command(plan, config, force=force)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, cwd=plan.repo_root)
    except OSError as err:
        raise SearchIntegrityError(
            "distance-ladder exporter failed\n"
            + "command: "
            + " ".join(command)
            + f"\nerror: {err}"
        ) from err
    if completed.returncode != 0:
        raise SearchIntegrityError(_format_exporter_failure(command, completed))
    return MaterializationResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
```

Update `generate_quantum_tanner_sweep` signature:

```python
def generate_quantum_tanner_sweep(
    repo_root: Path,
    config: QuantumTannerSweepConfig,
    *,
    dry_run: bool = False,
    materialize: bool = False,
    force: bool = False,
) -> QuantumTannerGenerationPlan:
```

After writing specs and manifest, invoke the materializer only when
`materialize` is true:

```python
materialization = None
if materialize:
    materialization = materialize_quantum_tanner_sweep(plan, config, force=force)
    plan = replace(plan, materialization=materialization)
return plan
```

Import `replace` from `dataclasses`.

- [ ] **Step 4: Extend summary rendering**

Update `render_quantum_tanner_generation_summary` to append materialization
details when `plan.materialization is not None`:

```python
if plan.materialization is not None:
    lines.extend(
        [
            f"materialized {len(plan.manifest['entries'])} quantum Tanner instances",
            "exporter_command: " + " ".join(plan.materialization.command),
        ]
    )
```

- [ ] **Step 5: Add CLI flags**

In `src/autoqec_search/cli.py`, add parser flags:

```python
generate_qt_sweep_parser.add_argument("--materialize", action="store_true")
generate_qt_sweep_parser.add_argument("--distance-ladder-exporter-bin", default=None)
generate_qt_sweep_parser.add_argument("--force", action="store_true")
```

In the command handler, override the config only when the CLI flag is present:

```python
if args.distance_ladder_exporter_bin is not None:
    config = replace(
        config,
        distance_ladder_exporter_bin=args.distance_ladder_exporter_bin,
    )
```

Import `replace` from `dataclasses`. Pass:

```python
materialize=args.materialize,
force=args.force,
```

to `generate_quantum_tanner_sweep`.

- [ ] **Step 6: Run focused tests to verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
```

Expected: PASS.

### Task 3: Verification, Review, And Branch Completion

**Files:**
- Review all changed files.

**Interfaces:**
- Consumes: completed Task 1 and Task 2 changes.
- Produces: verified PR branch for issue #58.

- [ ] **Step 1: Run issue verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
cargo test distance_ladder --quiet
```

Expected: both commands PASS.

- [ ] **Step 2: Run Agent Desk verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: PASS.

- [ ] **Step 3: Inspect diff for scope**

Run:

```bash
git diff --stat
git diff -- docs/superpowers/specs/2026-07-08-issue-58-quantum-tanner-materialization-design.md docs/superpowers/plans/2026-07-08-issue-58-quantum-tanner-materialization.md tests/fixtures/quantum_tanner_sweep/good.json tests/test_search_quantum_tanner_generator.py src/autoqec_search/quantum_tanner_generator.py src/autoqec_search/cli.py
```

Expected: only issue #58 docs, generator, CLI, fixture, and tests changed.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add docs/superpowers/specs/2026-07-08-issue-58-quantum-tanner-materialization-design.md docs/superpowers/plans/2026-07-08-issue-58-quantum-tanner-materialization.md tests/fixtures/quantum_tanner_sweep/good.json tests/test_search_quantum_tanner_generator.py src/autoqec_search/quantum_tanner_generator.py src/autoqec_search/cli.py
git commit -m "Implement quantum Tanner materialization"
```

- [ ] **Step 5: Push and open PR**

Run:

```bash
git push -u origin agent/issue-58-m3-materialize-generated-quantum-tanner-instance-run-1
gh pr create --base main --head agent/issue-58-m3-materialize-generated-quantum-tanner-instance-run-1 --title "Implement #58: Materialize generated quantum Tanner instances" --body-file /tmp/issue-58-pr-body.md
```

The PR body must summarize the generator materialization path, mention exporter
reuse and failure reporting, list verification commands, and include
`Closes #58`.

## Self-Review

The plan covers every design requirement: exporter reuse, explicit qec-code and
force policy, dry-run behavior, failure output, non-success on exporter failure,
CLI integration, positive materialization test, negative wrong-width control,
issue verification, full pytest verification, commit, push, and PR creation.
No placeholders remain.
