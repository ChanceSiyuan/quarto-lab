# Code Distance Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable workflow that computes code distance for an existing Zoo instance, stores it at `derived_properties.distance`, and extends new-instance generation to offer that computation automatically when `n <= 200`.

**Architecture:** Keep the workflow split across the existing repository layers: the JSON schema and checked-in fixtures define the contract, Julia scripts own matrix-to-distance computation, Python tests validate the data and generated artifacts, and project skills orchestrate user-facing flow. Reuse one distance-computation path for both the standalone `compute-code-distance` skill and the optional post-generation branch in `generate-code-instance`.

**Tech Stack:** Python, pytest, jsonschema, Julia, TensorQEC.jl, project-local skill markdown

---

## File Structure

- Modify: `zoo/schemas/code-instance.schema.json`
  - Add `derived_properties.distance` as a required `integer | null` field.
- Modify: `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/instance.json`
  - Update the checked-in seed instance to include `"distance": null`.
- Modify: `julia/tensorqec_env/scripts/support.jl`
  - Write `"distance" => nothing` for newly generated instances and add any small helper needed by the new Julia script.
- Create: `julia/tensorqec_env/scripts/compute_distance.jl`
  - Read `hx.json` and `hz.json`, reconstruct the CSS representation, compute distance through `TensorQEC`, and print JSON.
- Modify: `src/autoqec_zoo/load.py`
  - Accept the new `distance` field via schema validation and preserve current integrity checks.
- Modify: `src/autoqec_zoo/build.py`
  - Include distance in instance indexes only when needed by tests and downstream rendering.
- Modify: `src/autoqec_zoo/render_markdown.py`
  - Render distance in generated instance summaries when present; tolerate `null`.
- Modify: `.claude/skills/generate-code-instance/SKILL.md`
  - Add the `n <= 200` decision step and skip policy.
- Create: `.claude/skills/compute-code-distance/SKILL.md`
  - Define the standalone workflow for existing instances.
- Modify: `README.md`
  - Reference the new skill and the optional post-generation distance workflow.
- Modify: `CLAUDE.md`
  - Reference the new skill in repo guidance.
- Modify: `tests/test_source_data.py`
  - Cover schema validation and checked-in fixture expectations for `distance`.
- Modify: `tests/test_build.py`
  - Cover rendered/indexed behavior when distance is null and when distance is populated.
- Modify: `tests/test_cli.py`
  - Cover Julia generation defaulting to `distance: null` and the new distance script on a small fixture.

### Task 1: Extend the Instance Schema Contract

**Files:**
- Modify: `zoo/schemas/code-instance.schema.json`
- Modify: `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/instance.json`
- Test: `tests/test_source_data.py`

- [ ] **Step 1: Write the failing schema test for required `distance`**

```python
def test_seed_instance_validates_against_checked_in_instance_schema() -> None:
    instance_schema = _load_json(ZOO_ROOT / "schemas" / "code-instance.schema.json")
    instance_validator = Draft202012Validator(instance_schema)

    instance_root = (
        ZOO_ROOT
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    instance_payload = _load_json(instance_root / "instance.json")
    instance_validator.validate(instance_payload)

    derived_properties = instance_payload["derived_properties"]
    assert "distance" in derived_properties
    assert derived_properties["distance"] is None


def test_instance_schema_rejects_missing_or_zero_distance() -> None:
    instance_schema = _load_json(ZOO_ROOT / "schemas" / "code-instance.schema.json")
    instance_validator = Draft202012Validator(instance_schema)
    valid_payload = _load_json(
        ZOO_ROOT
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "instance.json"
    )

    missing_distance = json.loads(json.dumps(valid_payload))
    del missing_distance["derived_properties"]["distance"]
    with pytest.raises(ValidationError):
        instance_validator.validate(missing_distance)

    zero_distance = json.loads(json.dumps(valid_payload))
    zero_distance["derived_properties"]["distance"] = 0
    with pytest.raises(ValidationError):
        instance_validator.validate(zero_distance)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_source_data.py::test_seed_instance_validates_against_checked_in_instance_schema tests/test_source_data.py::test_instance_schema_rejects_missing_or_zero_distance -v`
Expected: FAIL because the checked-in schema and seed instance do not yet define `derived_properties.distance`.

- [ ] **Step 3: Update the schema and seed instance**

```json
{
  "derived_properties": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "n",
      "kx",
      "kz",
      "mx",
      "mz",
      "distance"
    ],
    "properties": {
      "n": {
        "type": "integer",
        "minimum": 1
      },
      "kx": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 0
      },
      "kz": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 0
      },
      "mx": {
        "type": "integer",
        "minimum": 0
      },
      "mz": {
        "type": "integer",
        "minimum": 0
      },
      "distance": {
        "type": [
          "integer",
          "null"
        ],
        "minimum": 1
      }
    }
  }
}
```

```json
{
  "derived_properties": {
    "n": 9,
    "kx": null,
    "kz": null,
    "mx": 4,
    "mz": 4,
    "distance": null
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_source_data.py::test_seed_instance_validates_against_checked_in_instance_schema tests/test_source_data.py::test_instance_schema_rejects_missing_or_zero_distance -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add zoo/schemas/code-instance.schema.json \
  zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/instance.json \
  tests/test_source_data.py
git commit -m "feat: add instance distance schema field"
```

### Task 2: Default Generated Instances to `distance: null`

**Files:**
- Modify: `julia/tensorqec_env/scripts/support.jl`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing generator test for default null distance**

```python
def test_tensorqec_generator_writes_rotated_surface_instance(tmp_path: Path) -> None:
    result, output_root = _run_tensorqec_generator(
        tmp_path,
        "--code-id",
        "rotated-surface-code",
        "--distance",
        "3",
        fresh_depot=True,
    )

    assert result.returncode == 0, result.stderr

    instance = _load_json(output_root / "instance.json")
    Draft202012Validator(INSTANCE_SCHEMA).validate(instance)
    assert instance["derived_properties"] == {
        "n": 9,
        "kx": None,
        "kz": None,
        "mx": 4,
        "mz": 4,
        "distance": None,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::test_tensorqec_generator_writes_rotated_surface_instance -v`
Expected: FAIL because the generated `instance.json` does not yet include `distance`.

- [ ] **Step 3: Update the Julia bundle writer**

```julia
function write_instance_bundle(
    output_root;
    id,
    code_id,
    family_id,
    title,
    parameters,
    generator_parameters,
    hx_payload,
    hz_payload,
)
    mkpath(output_root)

    instance_payload = Dict(
        "id" => id,
        "code_id" => code_id,
        "family_id" => family_id,
        "title" => title,
        "instance_kind" => "finite_css_instance",
        "matrix_format" => "dense_binary_json",
        "artifacts" => Dict(
            "hx" => "hx.json",
            "hz" => "hz.json",
        ),
        "parameters" => parameters,
        "derived_properties" => Dict(
            "n" => hx_payload["n_cols"],
            "kx" => nothing,
            "kz" => nothing,
            "mx" => hx_payload["n_rows"],
            "mz" => hz_payload["n_rows"],
            "distance" => nothing,
        ),
        "provenance" => Dict(
            "generator" => "tensorQEC.jl",
            "generator_env" => "julia/tensorqec_env",
            "generated_at" => normalized_now_utc(),
            "generator_script" => "julia/tensorqec_env/scripts/generate_instance.jl",
            "generator_parameters" => generator_parameters,
        ),
    )

    _write_json(joinpath(output_root, "instance.json"), instance_payload)
    _write_json(joinpath(output_root, "hx.json"), hx_payload)
    _write_json(joinpath(output_root, "hz.json"), hz_payload)
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py::test_tensorqec_generator_writes_rotated_surface_instance -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add julia/tensorqec_env/scripts/support.jl tests/test_cli.py
git commit -m "feat: default generated instances to null distance"
```

### Task 3: Add the Julia Distance Computation Script

**Files:**
- Create: `julia/tensorqec_env/scripts/compute_distance.jl`
- Modify: `julia/tensorqec_env/scripts/support.jl`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing integration test for distance computation**

```python
def test_tensorqec_distance_script_computes_small_rotated_surface_distance(
    tmp_path: Path,
) -> None:
    result, output_root = _run_tensorqec_generator(
        tmp_path,
        "--code-id",
        "rotated-surface-code",
        "--distance",
        "3",
    )
    assert result.returncode == 0, result.stderr

    julia = shutil.which("julia")
    if julia is None:
        pytest.skip("julia is not installed")

    distance_result = subprocess.run(
        [
            julia,
            "--project=julia/tensorqec_env",
            "julia/tensorqec_env/scripts/compute_distance.jl",
            "--hx-path",
            str(output_root / "hx.json"),
            "--hz-path",
            str(output_root / "hz.json"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert distance_result.returncode == 0, distance_result.stderr
    assert json.loads(distance_result.stdout) == {"distance": 3}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::test_tensorqec_distance_script_computes_small_rotated_surface_distance -v`
Expected: FAIL because `compute_distance.jl` does not exist yet.

- [ ] **Step 3: Implement the Julia distance script**

```julia
ENV_ROOT = normpath(joinpath(@__DIR__, ".."))
ENV["JULIA_PKG_PRECOMPILE_AUTO"] = "0"

import Pkg

Pkg.activate(ENV_ROOT)
Pkg.instantiate()

using JSON
using TensorQEC

include(joinpath(@__DIR__, "support.jl"))
using .AutoQECTensorQECSupport

function parse_args(args)
    if isodd(length(args))
        error("expected explicit --flag value pairs")
    end

    parsed = Dict{String, String}()
    index = 1
    while index <= length(args)
        key = args[index]
        value = args[index + 1]
        startswith(key, "--") || error("unexpected argument: $key")
        parsed[key[3:end]] = value
        index += 2
    end
    return parsed
end

function require_arg(parsed, key)
    haskey(parsed, key) || error("missing required --$key")
    return parsed[key]
end

function main(args)
    parsed = parse_args(args)
    hx_payload = load_matrix_payload(require_arg(parsed, "hx-path"))
    hz_payload = load_matrix_payload(require_arg(parsed, "hz-path"))
    distance = css_code_distance(hx_payload, hz_payload)
    JSON.print(stdout, Dict("distance" => distance))
    write(stdout, '\n')
end

main(ARGS)
```

```julia
function load_matrix_payload(path)
    payload = JSON.parsefile(path)
    payload["format"] == "dense_binary_matrix" || error("unsupported matrix format: $path")
    return payload
end

function css_code_distance(hx_payload, hz_payload)
    hx = parity_check_matrix(hx_payload["data"])
    hz = parity_check_matrix(hz_payload["data"])
    return Int(code_distance(CSSTannerGraph(hx, hz)))
end
```

Note: if `TensorQEC.jl` exposes a different exact constructor or distance API, adjust the helper names to the real package surface while preserving the same CLI contract and test expectation.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py::test_tensorqec_distance_script_computes_small_rotated_surface_distance -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add julia/tensorqec_env/scripts/compute_distance.jl \
  julia/tensorqec_env/scripts/support.jl \
  tests/test_cli.py
git commit -m "feat: add tensorqec distance computation script"
```

### Task 4: Surface the Distance Field in Python Load/Build/Markdown Paths

**Files:**
- Modify: `src/autoqec_zoo/load.py`
- Modify: `src/autoqec_zoo/build.py`
- Modify: `src/autoqec_zoo/render_markdown.py`
- Test: `tests/test_build.py`

- [ ] **Step 1: Write the failing build test for rendered distance**

```python
def test_build_card_markdown_includes_instance_distance_when_present(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    instance_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "instance.json"
    )
    instance_payload = json.loads(instance_path.read_text())
    instance_payload["derived_properties"]["distance"] = 3
    instance_path.write_text(json.dumps(instance_payload, indent=2) + "\n")

    build_zoo(work_root, generated_at="2026-05-28")

    card_md = (work_root / "codes" / "rotated-surface-code" / "card.md").read_text()
    instance_index = json.loads((work_root / "views" / "instance-index.json").read_text())

    assert "distance=3" in card_md
    assert instance_index["items"][0]["distance"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_build.py::test_build_card_markdown_includes_instance_distance_when_present -v`
Expected: FAIL because rendered markdown and instance indexes do not yet include distance.

- [ ] **Step 3: Update build and markdown rendering**

```python
def _build_instance_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for instance in sorted(dataset.instances.values(), key=lambda item: item.payload["id"]):
        payload = instance.payload
        derived = payload["derived_properties"]
        items.append(
            {
                "id": payload["id"],
                "code_id": payload["code_id"],
                "family_id": payload["family_id"],
                "title": payload["title"],
                "n": derived["n"],
                "mx": derived["mx"],
                "mz": derived["mz"],
                "distance": derived["distance"],
            }
        )
    return {"generated_at": generated_at, "items": items}
```

```python
if instance_records:
    for instance in instance_records:
        derived = instance["derived_properties"]
        summary = f"- `{instance['id']}` — n={derived['n']}, mx={derived['mx']}, mz={derived['mz']}"
        if derived["distance"] is not None:
            summary += f", distance={derived['distance']}"
        lines.append(summary)
```

Keep `load.py` unchanged unless a dedicated integrity check for the new field is needed; the schema validator already enforces type and presence.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_build.py::test_build_card_markdown_includes_instance_distance_when_present tests/test_build.py::test_build_writes_instance_index -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_zoo/build.py \
  src/autoqec_zoo/render_markdown.py \
  tests/test_build.py
git commit -m "feat: display instance distance in zoo outputs"
```

### Task 5: Add the Standalone `compute-code-distance` Skill Contract

**Files:**
- Create: `.claude/skills/compute-code-distance/SKILL.md`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Test: `tests/test_source_data.py`

- [ ] **Step 1: Write the failing documentation test for the new skill**

```python
def test_repo_docs_reference_tensorqec_skills() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "setup-tensorqec" in readme
    assert "generate-code-instance" in readme
    assert "compute-code-distance" in readme
    assert "setup-tensorqec" in claude
    assert "generate-code-instance" in claude
    assert "compute-code-distance" in claude


def test_tensorqec_environment_files_exist() -> None:
    env_root = REPO_ROOT / "julia" / "tensorqec_env"

    assert (env_root / "Project.toml").is_file()
    assert (env_root / "Manifest.toml").is_file()
    assert (env_root / "scripts" / "setup.jl").is_file()
    assert (env_root / "scripts" / "support.jl").is_file()
    assert (env_root / "scripts" / "compute_distance.jl").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_source_data.py::test_repo_docs_reference_tensorqec_skills tests/test_source_data.py::test_tensorqec_environment_files_exist -v`
Expected: FAIL because the new skill and script are not yet documented.

- [ ] **Step 3: Add the skill and repo guidance**

```md
---
name: compute-code-distance
description: Use when computing code distance for an existing finite-size CSS instance stored under zoo/codes/**/instances/.
---

# compute-code-distance

## Overview

This is a project-level AutoQEC skill for computing code distance from an existing stored CSS instance and recording the result on `instance.json`.

## Workflow

1. Confirm that `julia/tensorqec_env/` is already set up. If not, stop and point the user to `setup-tensorqec`.
2. Resolve the target instance from an exact instance id or exact instance directory path.
3. Read `instance.json`, `hx.json`, and `hz.json`.
4. Stop if `instance_kind` is not `finite_css_instance` or the matrix artifacts are missing.
5. If `derived_properties.distance` already has a value, ask whether to overwrite it.
6. Run:

```bash
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/compute_distance.jl \
  --hx-path <instance-root>/hx.json \
  --hz-path <instance-root>/hz.json
```

7. Parse the JSON result and update `instance.json` so `derived_properties.distance` equals the computed value.
8. Report the instance id, path, `n`, and computed distance.

## Rules

- Do not edit `card.json`.
- Do not create evidence records.
- Do not overwrite an existing recorded distance without explicit user confirmation.
- Stop if the Julia command fails or returns malformed JSON.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_source_data.py::test_repo_docs_reference_tensorqec_skills tests/test_source_data.py::test_tensorqec_environment_files_exist -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/compute-code-distance/SKILL.md README.md CLAUDE.md tests/test_source_data.py
git commit -m "docs: add compute code distance skill guidance"
```

### Task 6: Extend `generate-code-instance` Skill with Thresholded Distance Flow

**Files:**
- Modify: `.claude/skills/generate-code-instance/SKILL.md`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Test: `tests/test_source_data.py`

- [ ] **Step 1: Write the failing documentation test for threshold policy**

```python
def test_generate_code_instance_skill_docs_cover_distance_threshold() -> None:
    skill_doc = (REPO_ROOT / ".claude" / "skills" / "generate-code-instance" / "SKILL.md").read_text()

    assert "derived_properties.n <= 200" in skill_doc
    assert "derived_properties.n > 200" in skill_doc
    assert "compute-code-distance" in skill_doc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_source_data.py::test_generate_code_instance_skill_docs_cover_distance_threshold -v`
Expected: FAIL because the current skill file does not mention the threshold flow.

- [ ] **Step 3: Update the generation skill guidance**

```md
## Workflow

1. Confirm that `julia/tensorqec_env/` is already set up. If not, stop and point the user to `setup-tensorqec`.
2. Resolve the target family.
3. Collect required parameters one at a time.
4. Compute the target instance slug.
5. Refuse to overwrite an existing directory.
6. Run the Julia generator into a temporary directory.
7. Validate the generated bundle with the repo's existing Python validation/build path if practical, then move it into `zoo/codes/<code-id>/instances/<instance-slug>/`.
8. Read the generated `instance.json`.
9. If `derived_properties.n <= 200`, ask whether to compute code distance now.
10. If the user agrees, run the `compute-code-distance` workflow on the new instance.
11. If `derived_properties.n > 200`, report that automatic distance computation is skipped because the instance exceeds the threshold.
12. Report the created instance id, path, parameters, matrix dimensions, and whether distance was computed.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_source_data.py::test_generate_code_instance_skill_docs_cover_distance_threshold -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/generate-code-instance/SKILL.md README.md CLAUDE.md tests/test_source_data.py
git commit -m "docs: add distance threshold flow to generation skill"
```

### Task 7: Run the Focused Regression Suite

**Files:**
- Test: `tests/test_source_data.py`
- Test: `tests/test_build.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Run source data tests**

Run: `python3 -m pytest tests/test_source_data.py -v`
Expected: PASS

- [ ] **Step 2: Run build tests**

Run: `python3 -m pytest tests/test_build.py -v`
Expected: PASS

- [ ] **Step 3: Run CLI and Julia integration tests**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: PASS, with Julia-dependent tests skipped only when Julia is unavailable.

- [ ] **Step 4: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: PASS

- [ ] **Step 5: Commit final verification state**

```bash
git add tests/test_source_data.py tests/test_build.py tests/test_cli.py \
  src/autoqec_zoo/build.py src/autoqec_zoo/render_markdown.py \
  julia/tensorqec_env/scripts/support.jl julia/tensorqec_env/scripts/compute_distance.jl \
  zoo/schemas/code-instance.schema.json \
  zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/instance.json \
  .claude/skills/compute-code-distance/SKILL.md \
  .claude/skills/generate-code-instance/SKILL.md README.md CLAUDE.md
git commit -m "test: verify code distance workflow end to end"
```

## Self-Review

Spec coverage check:

- new standalone skill: Task 5
- Julia distance script: Task 3
- schema extension and default null value: Tasks 1 and 2
- post-generation threshold policy: Task 6
- Python load/build/render compatibility: Task 4
- tests for schema, integration, and threshold documentation: Tasks 1, 3, 4, 5, 6, 7

Placeholder scan:

- no `TODO`, `TBD`, or deferred implementation markers remain
- every code-changing task includes concrete code or exact contract text

Type consistency:

- the field name is always `derived_properties.distance`
- the threshold is always defined on `derived_properties.n`
- the Julia CLI contract is always `--hx-path` and `--hz-path`

