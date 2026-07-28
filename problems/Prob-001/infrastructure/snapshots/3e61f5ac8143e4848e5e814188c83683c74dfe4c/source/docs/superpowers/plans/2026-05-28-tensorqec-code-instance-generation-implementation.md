# TensorQEC Code Instance Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-local `tensorQEC.jl` generation workflow that creates finite CSS code instances, stores `Hx` and `Hz` under `zoo/codes/**/instances/`, and teaches the existing AutoQEC Zoo loader/build pipeline to validate and surface those instances.

**Architecture:** Treat generated finite-size instances as a third Zoo source-of-truth layer alongside canonical cards and paper evidence. Keep workflow orchestration in two project-level skills, package-specific generation in small Julia scripts under `julia/tensorqec_env/`, and validation/loading/indexing in the existing Python `autoqec_zoo` package. Do not mutate canonical cards with `instance_refs`; discover instances by directory scan.

**Tech Stack:** Python 3.11+, `jsonschema`, `pytest`, existing `autoqec_zoo` loader/builder, Julia 1.x, `TensorQEC.jl`, JSON-based matrix artifacts

---

## File Structure

- `zoo/schemas/code-instance.schema.json`: formal schema for `instance.json`
- `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/{instance.json,hx.json,hz.json}`: checked-in seed instance covering the new storage contract
- `src/autoqec_zoo/load.py`: add instance discovery, validation, and integrity checks
- `src/autoqec_zoo/build.py`: carry instance counts and emit an instance index
- `src/autoqec_zoo/render_markdown.py`: optionally show per-code instance summaries in card markdown
- `src/autoqec_zoo/render_site.py`: surface `instance_count` in existing site state without adding a dedicated instance UI
- `src/autoqec_zoo/cli.py`: continue to validate/build successfully when instances exist
- `tests/test_source_data.py`: validate the checked-in instance against the new schema
- `tests/test_load.py`: instance loader regressions
- `tests/test_build.py`: build regressions and instance index coverage
- `tests/test_site.py`: static-site state regression for instance counts
- `tests/test_cli.py`: CLI regression proving builds still succeed with instances present
- `julia/tensorqec_env/Project.toml`: repository-local Julia environment for setup and generation scripts
- `julia/tensorqec_env/Manifest.toml`: checked-in Julia dependency resolution for the local TensorQEC environment
- `julia/tensorqec_env/scripts/setup.jl`: setup and smoke-test entry point
- `julia/tensorqec_env/scripts/generate_instance.jl`: normalize inputs, call `TensorQEC`, and write JSON artifacts
- `julia/tensorqec_env/scripts/support.jl`: shared Julia helpers for slugging, matrix extraction, and JSON payload assembly
- `.claude/skills/setup-tensorqec/SKILL.md`: setup workflow skill
- `.claude/skills/generate-code-instance/SKILL.md`: interactive generation workflow skill
- `README.md`: mention instance generation and the two project-level skills
- `CLAUDE.md`: repo-local guidance for when to use the new skills
- `Makefile`: optional Julia helper targets if they reduce friction without overcomplicating the repo

### Task 1: Add the instance schema and one checked-in seed instance

**Files:**
- Create: `zoo/schemas/code-instance.schema.json`
- Create: `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/instance.json`
- Create: `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/hx.json`
- Create: `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/hz.json`
- Modify: `tests/test_source_data.py`

- [ ] **Step 1: Write the failing source-data test for instance validation**

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
    instance_validator.validate(_load_json(instance_root / "instance.json"))

    for matrix_name in ["hx.json", "hz.json"]:
        payload = _load_json(instance_root / matrix_name)
        assert payload["format"] == "dense_binary_matrix"
        assert payload["n_rows"] == len(payload["data"])
        assert all(len(row) == payload["n_cols"] for row in payload["data"])
        assert all(bit in [0, 1] for row in payload["data"] for bit in row)
```

- [ ] **Step 2: Run the focused source-data test to confirm the schema and seed files are missing**

Run: `python3 -m pytest tests/test_source_data.py::test_seed_instance_validates_against_checked_in_instance_schema -v`
Expected: FAIL with a file-not-found error for `zoo/schemas/code-instance.schema.json`

- [ ] **Step 3: Add the instance schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "code_id",
    "family_id",
    "title",
    "instance_kind",
    "matrix_format",
    "artifacts",
    "parameters",
    "derived_properties",
    "provenance"
  ],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"
    },
    "code_id": { "type": "string", "minLength": 1 },
    "family_id": { "type": "string", "minLength": 1 },
    "title": { "type": "string", "minLength": 1 },
    "instance_kind": { "const": "finite_css_instance" },
    "matrix_format": { "const": "dense_binary_json" },
    "artifacts": {
      "type": "object",
      "additionalProperties": false,
      "required": ["hx", "hz"],
      "properties": {
        "hx": { "const": "hx.json" },
        "hz": { "const": "hz.json" }
      }
    },
    "parameters": {
      "type": "object",
      "minProperties": 1,
      "additionalProperties": {
        "type": ["string", "integer", "number", "boolean", "null", "array", "object"]
      }
    },
    "derived_properties": {
      "type": "object",
      "additionalProperties": false,
      "required": ["n", "kx", "kz", "mx", "mz"],
      "properties": {
        "n": { "type": "integer", "minimum": 1 },
        "kx": { "type": ["integer", "null"], "minimum": 0 },
        "kz": { "type": ["integer", "null"], "minimum": 0 },
        "mx": { "type": "integer", "minimum": 0 },
        "mz": { "type": "integer", "minimum": 0 }
      }
    },
    "provenance": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "generator",
        "generator_env",
        "generated_at",
        "generator_script",
        "generator_parameters"
      ],
      "properties": {
        "generator": { "const": "tensorQEC.jl" },
        "generator_env": { "type": "string", "minLength": 1 },
        "generated_at": {
          "type": "string",
          "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"
        },
        "generator_script": { "type": "string", "minLength": 1 },
        "generator_parameters": {
          "type": "object",
          "minProperties": 1,
          "additionalProperties": {
            "type": ["string", "integer", "number", "boolean", "null", "array", "object"]
          }
        }
      }
    }
  }
}
```

- [ ] **Step 4: Add one small checked-in rotated surface-code instance**

`instance.json`

```json
{
  "id": "rotated-surface-code-d3",
  "code_id": "rotated-surface-code",
  "family_id": "surface-code",
  "title": "Rotated Surface Code d=3",
  "instance_kind": "finite_css_instance",
  "matrix_format": "dense_binary_json",
  "artifacts": {
    "hx": "hx.json",
    "hz": "hz.json"
  },
  "parameters": {
    "distance": 3,
    "layout": "rotated"
  },
  "derived_properties": {
    "n": 9,
    "kx": null,
    "kz": null,
    "mx": 4,
    "mz": 4
  },
  "provenance": {
    "generator": "tensorQEC.jl",
    "generator_env": "julia/tensorqec_env",
    "generated_at": "2026-05-28T00:00:00Z",
    "generator_script": "julia/tensorqec_env/scripts/generate_instance.jl",
    "generator_parameters": {
      "distance": 3,
      "layout": "rotated"
    }
  }
}
```

`hx.json`

```json
{
  "format": "dense_binary_matrix",
  "n_rows": 4,
  "n_cols": 9,
  "data": [
    [0, 0, 1, 0, 0, 1, 0, 0, 0],
    [1, 1, 0, 1, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 1, 0, 1, 1],
    [0, 0, 0, 1, 0, 0, 1, 0, 0]
  ]
}
```

`hz.json`

```json
{
  "format": "dense_binary_matrix",
  "n_rows": 4,
  "n_cols": 9,
  "data": [
    [1, 1, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 1, 0, 1, 1, 0, 0, 0],
    [0, 0, 0, 1, 1, 0, 1, 1, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 1]
  ]
}
```

- [ ] **Step 5: Run the focused source-data test again**

Run: `python3 -m pytest tests/test_source_data.py::test_seed_instance_validates_against_checked_in_instance_schema -v`
Expected: PASS

- [ ] **Step 6: Run the full source-data suite**

Run: `python3 -m pytest tests/test_source_data.py -v`
Expected: PASS

- [ ] **Step 7: Commit the schema and seed instance**

```bash
git add zoo/schemas/code-instance.schema.json \
  zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/instance.json \
  zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/hx.json \
  zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/hz.json \
  tests/test_source_data.py
git commit -m "feat: add zoo code instance schema"
```

### Task 2: Extend the loader to discover and validate generated instances

**Files:**
- Modify: `src/autoqec_zoo/load.py`
- Modify: `tests/test_load.py`

- [ ] **Step 1: Write the failing loader test for valid instance collection**

```python
def test_load_zoo_collects_instances() -> None:
    dataset = load_zoo(REPO_ROOT / "zoo")

    assert sorted(dataset.instances) == ["rotated-surface-code-d3"]
    instance = dataset.instances["rotated-surface-code-d3"]
    assert instance["code_id"] == "rotated-surface-code"
    assert instance["family_id"] == "surface-code"
    assert instance["derived_properties"]["n"] == 9
```

- [ ] **Step 2: Add failing integrity tests for missing artifacts and mismatches**

```python
def test_load_zoo_rejects_instance_missing_hx(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)
    (work_root / "codes" / "rotated-surface-code" / "instances" / "rotated-surface-code-d3" / "hx.json").unlink()

    with pytest.raises(IntegrityError, match="missing hx artifact"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_code_directory_mismatch(tmp_path: Path) -> None:
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
    payload = json.loads(instance_path.read_text())
    payload["code_id"] = "surface-code"
    instance_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="instance code_id mismatch"):
        load_zoo(work_root)


def test_load_zoo_rejects_instance_dimension_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)
    hz_path = (
        work_root
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "hz.json"
    )
    payload = json.loads(hz_path.read_text())
    payload["n_cols"] = 8
    hz_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="matrix column mismatch"):
        load_zoo(work_root)
```

- [ ] **Step 3: Run the focused loader tests to confirm `ZooDataset` and loader logic do not yet support instances**

Run: `python3 -m pytest tests/test_load.py::test_load_zoo_collects_instances tests/test_load.py::test_load_zoo_rejects_instance_missing_hx tests/test_load.py::test_load_zoo_rejects_instance_code_directory_mismatch tests/test_load.py::test_load_zoo_rejects_instance_dimension_mismatch -v`
Expected: FAIL because `ZooDataset` has no `instances` field and the loader does not scan `instances/`

- [ ] **Step 4: Extend `ZooDataset` and add matrix-loading helpers**

```python
@dataclass(frozen=True)
class ZooDataset:
    cards: dict[str, dict]
    evidence: dict[str, dict]
    instances: dict[str, dict]


def _load_matrix(path: Path) -> dict:
    payload = _load_json(path)
    if payload.get("format") != "dense_binary_matrix":
        raise IntegrityError(f"unsupported matrix format: {path}")
    if payload["n_rows"] != len(payload["data"]):
        raise IntegrityError(f"matrix row count mismatch: {path}")
    for row in payload["data"]:
        if len(row) != payload["n_cols"]:
            raise IntegrityError(f"matrix column mismatch: {path}")
        if any(bit not in (0, 1) for bit in row):
            raise IntegrityError(f"matrix contains non-binary entries: {path}")
    return payload
```

- [ ] **Step 5: Add instance discovery and integrity checks to `load_zoo`**

```python
instance_validator = _validator(schema_root / "code-instance.schema.json")
instances_by_id: dict[str, dict] = {}

for card_path in sorted((root / "codes").glob("*/card.json")):
    ...

for instance_path in sorted((root / "codes").glob("*/instances/*/instance.json")):
    instance = _load_json(instance_path)
    instance_validator.validate(instance)

    code_dir = instance_path.parents[2].name
    if instance["code_id"] != code_dir:
        raise IntegrityError(
            f"instance code_id mismatch for {instance_path}: "
            f"{instance['code_id']} != {code_dir}"
        )

    artifact_root = instance_path.parent
    hx_rel = instance["artifacts"]["hx"]
    hz_rel = instance["artifacts"]["hz"]
    hx_path = artifact_root / hx_rel
    hz_path = artifact_root / hz_rel
    if not hx_path.exists():
        raise IntegrityError(f"missing hx artifact: {hx_path}")
    if not hz_path.exists():
        raise IntegrityError(f"missing hz artifact: {hz_path}")

    hx = _load_matrix(hx_path)
    hz = _load_matrix(hz_path)
    if hx["n_cols"] != hz["n_cols"]:
        raise IntegrityError(
            f"matrix column mismatch: {hx_path} vs {hz_path}"
        )
    if instance["derived_properties"]["n"] != hx["n_cols"]:
        raise IntegrityError(f"instance n mismatch: {instance_path}")
    if instance["derived_properties"]["mx"] != hx["n_rows"]:
        raise IntegrityError(f"instance mx mismatch: {instance_path}")
    if instance["derived_properties"]["mz"] != hz["n_rows"]:
        raise IntegrityError(f"instance mz mismatch: {instance_path}")

    instances_by_id[instance["id"]] = {
        **instance,
        "hx_matrix": hx,
        "hz_matrix": hz,
    }

for instance_id, instance in instances_by_id.items():
    if instance["code_id"] not in cards:
        raise IntegrityError(f"unknown instance code_id on {instance_id}: {instance['code_id']}")
    expected_family_id = cards[instance["code_id"]].get("family") or instance["code_id"]
    if instance["family_id"] != expected_family_id:
        raise IntegrityError(f"instance family_id mismatch on {instance_id}: {instance['family_id']}")

return ZooDataset(cards=cards, evidence=evidence_by_id, instances=instances_by_id)
```

- [ ] **Step 6: Run the focused loader tests again**

Run: `python3 -m pytest tests/test_load.py::test_load_zoo_collects_instances tests/test_load.py::test_load_zoo_rejects_instance_missing_hx tests/test_load.py::test_load_zoo_rejects_instance_code_directory_mismatch tests/test_load.py::test_load_zoo_rejects_instance_dimension_mismatch -v`
Expected: PASS

- [ ] **Step 7: Run the full loader suite**

Run: `python3 -m pytest tests/test_load.py -v`
Expected: PASS

- [ ] **Step 8: Commit the loader extension**

```bash
git add src/autoqec_zoo/load.py tests/test_load.py
git commit -m "feat: load zoo code instances"
```

### Task 3: Carry instances through build output without adding a heavy UI

**Files:**
- Modify: `src/autoqec_zoo/build.py`
- Modify: `src/autoqec_zoo/render_markdown.py`
- Modify: `src/autoqec_zoo/render_site.py`
- Modify: `tests/test_build.py`
- Modify: `tests/test_site.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing build test for a machine-readable instance index**

```python
def test_build_writes_instance_index(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-28")

    instance_index = json.loads((work_root / "views" / "instance-index.json").read_text())
    assert instance_index["generated_at"] == "2026-05-28"
    assert instance_index["items"] == [
        {
            "id": "rotated-surface-code-d3",
            "code_id": "rotated-surface-code",
            "family_id": "surface-code",
            "title": "Rotated Surface Code d=3",
            "n": 9,
            "mx": 4,
            "mz": 4,
        }
    ]
```

- [ ] **Step 2: Add failing tests for `instance_count` propagation to markdown and site state**

```python
def test_build_card_markdown_includes_instance_summary(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-28")

    card_md = (work_root / "codes" / "rotated-surface-code" / "card.md").read_text()
    assert "## Generated Instances" in card_md
    assert "`rotated-surface-code-d3`" in card_md


def test_build_site_state_exposes_instance_count(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-28")

    html = (work_root / "views" / "site" / "index.html").read_text()
    assert '"instance_count": 1' in html
```

- [ ] **Step 3: Run the focused build/site tests to confirm the new artifacts are absent**

Run: `python3 -m pytest tests/test_build.py::test_build_writes_instance_index tests/test_build.py::test_build_card_markdown_includes_instance_summary tests/test_site.py::test_build_site_state_exposes_instance_count -v`
Expected: FAIL because `instance-index.json` is not emitted and markdown/site state ignore instances

- [ ] **Step 4: Extend build indexes and code summaries with `instance_count`**

```python
def _build_code_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        instance_count = sum(
            1 for instance in dataset.instances.values() if instance["code_id"] == card["id"]
        )
        items.append(
            {
                "id": card["id"],
                "title": card["title"],
                "kind": card["kind"],
                "family": card.get("family"),
                "summary": card["summary"],
                "source_count": len(card["source_refs"]),
                "evidence_count": len(card["evidence_refs"]),
                "instance_count": instance_count,
                "known_decoders": card["known_decoders"],
            }
        )
    return {"generated_at": generated_at, "items": items}


def _build_instance_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for instance in sorted(dataset.instances.values(), key=lambda item: item["id"]):
        items.append(
            {
                "id": instance["id"],
                "code_id": instance["code_id"],
                "family_id": instance["family_id"],
                "title": instance["title"],
                "n": instance["derived_properties"]["n"],
                "mx": instance["derived_properties"]["mx"],
                "mz": instance["derived_properties"]["mz"],
            }
        )
    return {"generated_at": generated_at, "items": items}
```

- [ ] **Step 5: Add a minimal generated-instance section to card markdown**

```python
def render_card_markdown(card: dict, evidence_records: list[dict], instance_records: list[dict]) -> str:
    ...
    lines.extend(["", "## Generated Instances", ""])
    if instance_records:
        for instance in instance_records:
            lines.append(
                f"- `{instance['id']}` — n={instance['derived_properties']['n']}, "
                f"mx={instance['derived_properties']['mx']}, mz={instance['derived_properties']['mz']}"
            )
    else:
        lines.append("- None")
    ...
```

- [ ] **Step 6: Carry `instance_count` into site state and keep the UI text simple**

```python
codes.append(
    {
        **index_item,
        ...
        "instance_count": index_item["instance_count"],
    }
)
```

In `render_site.py`, update the code-list meta line:

```javascript
meta.textContent = `${familyLabel(code)} | ${code.evidence_count} evidence | ${code.instance_count} instances`;
```

- [ ] **Step 7: Emit `instance-index.json` during build**

```python
views = {
    "code-index.json": _build_code_index(dataset, generated_at),
    "family-index.json": _build_family_index(dataset, generated_at),
    "relation-index.json": _build_relation_index(dataset, generated_at),
    "evidence-index.json": _build_evidence_index(dataset, generated_at),
    "instance-index.json": _build_instance_index(dataset, generated_at),
}

for card in dataset.cards.values():
    evidence_records = [dataset.evidence[item] for item in card["evidence_refs"]]
    instance_records = [
        instance for instance in dataset.instances.values() if instance["code_id"] == card["id"]
    ]
    (root / "codes" / card["id"] / "card.md").write_text(
        render_card_markdown(card, evidence_records, instance_records)
    )
```

- [ ] **Step 8: Run the focused build/site/CLI tests again**

Run: `python3 -m pytest tests/test_build.py::test_build_writes_instance_index tests/test_build.py::test_build_card_markdown_includes_instance_summary tests/test_site.py::test_build_site_state_exposes_instance_count tests/test_cli.py::test_build_command_writes_expected_artifacts -v`
Expected: PASS

- [ ] **Step 9: Run the full build/site/CLI suites**

Run: `python3 -m pytest tests/test_build.py tests/test_site.py tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 10: Commit the build integration**

```bash
git add src/autoqec_zoo/build.py src/autoqec_zoo/render_markdown.py src/autoqec_zoo/render_site.py \
  tests/test_build.py tests/test_site.py tests/test_cli.py
git commit -m "feat: surface zoo code instances in build outputs"
```

### Task 4: Add the repository-local Julia environment and setup script

**Files:**
- Create: `julia/tensorqec_env/Project.toml`
- Create: `julia/tensorqec_env/Manifest.toml`
- Create: `julia/tensorqec_env/scripts/setup.jl`
- Create: `julia/tensorqec_env/scripts/support.jl`

- [ ] **Step 1: Add a Python regression test that checks the Julia environment files exist**

```python
def test_tensorqec_environment_files_exist() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert (repo_root / "julia" / "tensorqec_env" / "Project.toml").exists()
    assert (repo_root / "julia" / "tensorqec_env" / "scripts" / "setup.jl").exists()
```

Place this in `tests/test_source_data.py`.

- [ ] **Step 2: Run the focused file-existence test to confirm the Julia env is missing**

Run: `python3 -m pytest tests/test_source_data.py::test_tensorqec_environment_files_exist -v`
Expected: FAIL because `julia/tensorqec_env/Project.toml` does not exist

- [ ] **Step 3: Create the repository-local Julia environment manifest**

`julia/tensorqec_env/Project.toml`

```toml
name = "AutoQECTensorQECEnv"
uuid = "0f7b8499-c495-4e03-8804-1d27156a6ffa"
version = "0.1.0"

[deps]
Dates = "ade2ca70-3891-5945-98fb-dc099432e06a"
JSON = "682c06a0-de6a-54ab-a142-c8b1cf79cde6"
TensorQEC = "0500ac79-7fb5-4262-aaea-37bb1845d1ef"
```

- [ ] **Step 4: Add the setup smoke-test script**

`julia/tensorqec_env/scripts/setup.jl`

```julia
using Pkg

const ENV_ROOT = normpath(joinpath(@__DIR__, ".."))

Pkg.activate(ENV_ROOT)
Pkg.instantiate()

using TensorQEC

tanner = CSSTannerGraph(SurfaceCode(3, 3))

println("tensorqec_env ready")
println("environment=$(ENV_ROOT)")
println("surface_n=$(tanner.stgx.nq)")
println("surface_mx=$(tanner.stgx.ns)")
println("surface_mz=$(tanner.stgz.ns)")
```

- [ ] **Step 5: Add a tiny shared helper module stub for later generation work**

`julia/tensorqec_env/scripts/support.jl`

```julia
module AutoQECTensorQECSupport

export normalize_slug_token

function normalize_slug_token(value)
    text = lowercase(string(value))
    text = replace(text, "_" => "-", " " => "-")
    text = replace(text, r"[^a-z0-9-]" => "")
    text = replace(text, r"-+" => "-")
    return strip(text, '-')
end

end
```

- [ ] **Step 6: Run the focused file-existence test again**

Run: `python3 -m pytest tests/test_source_data.py::test_tensorqec_environment_files_exist -v`
Expected: PASS

- [ ] **Step 7: Run the Julia setup smoke test**

Run: `julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/setup.jl`
Expected: PASS and output lines including `tensorqec_env ready`, `surface_n=9`, `surface_mx=4`, `surface_mz=4`, and a newly created `julia/tensorqec_env/Manifest.toml`

- [ ] **Step 8: Commit the Julia environment bootstrap**

```bash
git add julia/tensorqec_env/Project.toml julia/tensorqec_env/Manifest.toml julia/tensorqec_env/scripts/setup.jl julia/tensorqec_env/scripts/support.jl tests/test_source_data.py
git commit -m "feat: add tensorqec environment bootstrap"
```

### Task 5: Implement the Julia generator for rotated, unrotated, and BB-code instances

**Files:**
- Create: `julia/tensorqec_env/scripts/generate_instance.jl`
- Modify: `julia/tensorqec_env/scripts/support.jl`

- [ ] **Step 1: Add a Julia-facing Python smoke test that executes the generator for rotated surface code**

Add to `tests/test_cli.py`:

```python
def test_tensorqec_generator_writes_rotated_surface_instance(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "instance-out"
    if shutil.which("julia") is None:
        pytest.skip("julia not installed")
    result = subprocess.run(
        [
            "julia",
            "--project=julia/tensorqec_env",
            "julia/tensorqec_env/scripts/generate_instance.jl",
            "--code-id",
            "rotated-surface-code",
            "--distance",
            "3",
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0
    assert (output_root / "instance.json").exists()
    payload = json.loads((output_root / "instance.json").read_text())
    assert payload["id"] == "rotated-surface-code-d3"
    assert payload["code_id"] == "rotated-surface-code"
```

- [ ] **Step 2: Add a second smoke test proving unrotated surface code is handled by the local adapter**

```python
def test_tensorqec_generator_writes_unrotated_surface_instance(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "instance-out"
    if shutil.which("julia") is None:
        pytest.skip("julia not installed")
    result = subprocess.run(
        [
            "julia",
            "--project=julia/tensorqec_env",
            "julia/tensorqec_env/scripts/generate_instance.jl",
            "--code-id",
            "surface-code",
            "--distance",
            "3",
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0
    payload = json.loads((output_root / "instance.json").read_text())
    assert payload["id"] == "surface-code-d3"
    assert payload["parameters"]["layout"] == "unrotated"
```

- [ ] **Step 3: Add a BB-code smoke test and start by keeping the case small**

```python
def test_tensorqec_generator_writes_bbcode_instance(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = tmp_path / "instance-out"
    if shutil.which("julia") is None:
        pytest.skip("julia not installed")
    result = subprocess.run(
        [
            "julia",
            "--project=julia/tensorqec_env",
            "julia/tensorqec_env/scripts/generate_instance.jl",
            "--code-id",
            "bivariate-bicycle-code",
            "--m",
            "2",
            "--n",
            "2",
            "--vc",
            "[[1,0],[0,0]]",
            "--hd",
            "[[0,1],[0,0]]",
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0
    payload = json.loads((output_root / "instance.json").read_text())
    assert payload["code_id"] == "bivariate-bicycle-code"
    assert payload["family_id"] == "bivariate-bicycle-code"
```

- [ ] **Step 4: Run the focused generator tests to confirm the script does not exist yet**

Run: `python3 -m pytest tests/test_cli.py::test_tensorqec_generator_writes_rotated_surface_instance tests/test_cli.py::test_tensorqec_generator_writes_unrotated_surface_instance tests/test_cli.py::test_tensorqec_generator_writes_bbcode_instance -v`
Expected: FAIL because `julia/tensorqec_env/scripts/generate_instance.jl` does not exist

- [ ] **Step 5: Extend the Julia support module with matrix extraction and JSON helpers**

`julia/tensorqec_env/scripts/support.jl`

```julia
module AutoQECTensorQECSupport

using Dates
using JSON
using TensorQEC

export matrix_payload, css_payloads, write_instance_bundle, normalized_now_utc
export normalize_slug_token, rotated_surface_slug, unrotated_surface_slug, bbcode_slug

function normalize_slug_token(value)
    text = lowercase(string(value))
    text = replace(text, "_" => "-", " " => "-")
    text = replace(text, r"[^a-z0-9-]" => "")
    text = replace(text, r"-+" => "-")
    return strip(text, '-')
end

normalized_now_utc() = Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SSZ")

function matrix_payload(H)
    dense = Int.(getproperty.(H, :x))
    return Dict(
        "format" => "dense_binary_matrix",
        "n_rows" => size(dense, 1),
        "n_cols" => size(dense, 2),
        "data" => [collect(dense[i, :]) for i in 1:size(dense, 1)],
    )
end

function css_payloads(code)
    tanner = CSSTannerGraph(code)
    return matrix_payload(tanner.stgx.H), matrix_payload(tanner.stgz.H)
end

rotated_surface_slug(distance::Int) = "rotated-surface-code-d$(distance)"
unrotated_surface_slug(distance::Int) = "surface-code-d$(distance)"

function bbcode_slug(m::Int, n::Int)
    return "bivariate-bicycle-code-m$(m)-n$(n)"
end

function write_json(path::String, payload)
    mkpath(dirname(path))
    open(path, "w") do io
        JSON.print(io, payload, 2)
        write(io, "\n")
    end
end

function write_instance_bundle(output_root::String, instance_payload, hx_payload, hz_payload)
    mkpath(output_root)
    write_json(joinpath(output_root, "instance.json"), instance_payload)
    write_json(joinpath(output_root, "hx.json"), hx_payload)
    write_json(joinpath(output_root, "hz.json"), hz_payload)
end

end
```

- [ ] **Step 6: Implement the generator script with one local adapter for unrotated surface code**

`julia/tensorqec_env/scripts/generate_instance.jl`

```julia
using Pkg
Pkg.activate(normpath(joinpath(@__DIR__, "..")))
Pkg.instantiate()

using JSON
using TensorQEC

include("support.jl")
using .AutoQECTensorQECSupport

function parse_args(args)
    parsed = Dict{String, String}()
    i = 1
    while i <= length(args)
        key = args[i]
        startswith(key, "--") || error("expected flag, got $(key)")
        i == length(args) && error("missing value for $(key)")
        parsed[key[3:end]] = args[i + 1]
        i += 2
    end
    return parsed
end

function parse_pair_vector(text::String)
    raw = JSON.parse(text)
    return Tuple{Int, Int}[Tuple(Int.(pair)) for pair in raw]
end

function repetition_tanner_graph(distance::Int)
    checks = [[i, i + 1] for i in 1:(distance - 1)]
    return SimpleTannerGraph(distance, checks)
end

function make_unrotated_surface_code(distance::Int)
    rep = repetition_tanner_graph(distance)
    return product_graph(rep, rep)
end

function payload_for_rotated_surface(distance::Int, output_root::String)
    code = SurfaceCode(distance, distance)
    hx, hz = css_payloads(code)
    instance_id = rotated_surface_slug(distance)
    return Dict(
        "id" => instance_id,
        "code_id" => "rotated-surface-code",
        "family_id" => "surface-code",
        "title" => "Rotated Surface Code d=$(distance)",
        "instance_kind" => "finite_css_instance",
        "matrix_format" => "dense_binary_json",
        "artifacts" => Dict("hx" => "hx.json", "hz" => "hz.json"),
        "parameters" => Dict("distance" => distance, "layout" => "rotated"),
        "derived_properties" => Dict(
            "n" => hx["n_cols"],
            "kx" => nothing,
            "kz" => nothing,
            "mx" => hx["n_rows"],
            "mz" => hz["n_rows"],
        ),
        "provenance" => Dict(
            "generator" => "tensorQEC.jl",
            "generator_env" => "julia/tensorqec_env",
            "generated_at" => normalized_now_utc(),
            "generator_script" => "julia/tensorqec_env/scripts/generate_instance.jl",
            "generator_parameters" => Dict("distance" => distance, "layout" => "rotated"),
        ),
    ), hx, hz
end

function payload_for_unrotated_surface(distance::Int, output_root::String)
    tanner = make_unrotated_surface_code(distance)
    hx = matrix_payload(tanner.stgx.H)
    hz = matrix_payload(tanner.stgz.H)
    instance_id = unrotated_surface_slug(distance)
    return Dict(
        "id" => instance_id,
        "code_id" => "surface-code",
        "family_id" => "surface-code",
        "title" => "Surface Code d=$(distance)",
        "instance_kind" => "finite_css_instance",
        "matrix_format" => "dense_binary_json",
        "artifacts" => Dict("hx" => "hx.json", "hz" => "hz.json"),
        "parameters" => Dict("distance" => distance, "layout" => "unrotated"),
        "derived_properties" => Dict(
            "n" => hx["n_cols"],
            "kx" => nothing,
            "kz" => nothing,
            "mx" => hx["n_rows"],
            "mz" => hz["n_rows"],
        ),
        "provenance" => Dict(
            "generator" => "tensorQEC.jl",
            "generator_env" => "julia/tensorqec_env",
            "generated_at" => normalized_now_utc(),
            "generator_script" => "julia/tensorqec_env/scripts/generate_instance.jl",
            "generator_parameters" => Dict("distance" => distance, "layout" => "unrotated"),
        ),
    ), hx, hz
end

function payload_for_bbcode(m::Int, n::Int, vc_text::String, hd_text::String)
    vc = Tuple(parse_pair_vector(vc_text))
    hd = Tuple(parse_pair_vector(hd_text))
    code = BivariateBicycleCode(m, n, vc, hd)
    hx, hz = css_payloads(code)
    instance_id = bbcode_slug(m, n)
    return Dict(
        "id" => instance_id,
        "code_id" => "bivariate-bicycle-code",
        "family_id" => "bivariate-bicycle-code",
        "title" => "Bivariate Bicycle Code m=$(m), n=$(n)",
        "instance_kind" => "finite_css_instance",
        "matrix_format" => "dense_binary_json",
        "artifacts" => Dict("hx" => "hx.json", "hz" => "hz.json"),
        "parameters" => Dict(
            "m" => m,
            "n" => n,
            "vc" => JSON.parse(vc_text),
            "hd" => JSON.parse(hd_text),
        ),
        "derived_properties" => Dict(
            "n" => hx["n_cols"],
            "kx" => nothing,
            "kz" => nothing,
            "mx" => hx["n_rows"],
            "mz" => hz["n_rows"],
        ),
        "provenance" => Dict(
            "generator" => "tensorQEC.jl",
            "generator_env" => "julia/tensorqec_env",
            "generated_at" => normalized_now_utc(),
            "generator_script" => "julia/tensorqec_env/scripts/generate_instance.jl",
            "generator_parameters" => Dict(
                "m" => m,
                "n" => n,
                "vc" => JSON.parse(vc_text),
                "hd" => JSON.parse(hd_text),
            ),
        ),
    ), hx, hz
end

function main(args)
    parsed = parse_args(args)
    code_id = get(parsed, "code-id", nothing)
    output_root = get(parsed, "output-root", nothing)
    code_id === nothing && error("--code-id is required")
    output_root === nothing && error("--output-root is required")

    instance_payload, hx, hz =
        if code_id == "rotated-surface-code"
            payload_for_rotated_surface(parse(Int, parsed["distance"]), output_root)
        elseif code_id == "surface-code"
            payload_for_unrotated_surface(parse(Int, parsed["distance"]), output_root)
        elseif code_id == "bivariate-bicycle-code"
            payload_for_bbcode(
                parse(Int, parsed["m"]),
                parse(Int, parsed["n"]),
                parsed["vc"],
                parsed["hd"],
            )
        else
            error("unsupported code-id: $(code_id)")
        end

    write_instance_bundle(output_root, instance_payload, hx, hz)
    println(JSON.json(Dict("id" => instance_payload["id"], "output_root" => output_root)))
end

main(ARGS)
```

- [ ] **Step 7: Run the focused generator smoke tests**

Run: `python3 -m pytest tests/test_cli.py::test_tensorqec_generator_writes_rotated_surface_instance tests/test_cli.py::test_tensorqec_generator_writes_unrotated_surface_instance tests/test_cli.py::test_tensorqec_generator_writes_bbcode_instance -v`
Expected: PASS, or SKIP with `julia not installed` on machines where Julia is unavailable

- [ ] **Step 8: Run the generator script directly once for manual inspection**

Run: `julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/generate_instance.jl --code-id rotated-surface-code --distance 3 --output-root /tmp/autoqec-rotated-surface-code-d3`
Expected: PASS and stdout JSON containing `"id":"rotated-surface-code-d3"`

- [ ] **Step 9: Commit the generator**

```bash
git add julia/tensorqec_env/scripts/generate_instance.jl julia/tensorqec_env/scripts/support.jl tests/test_cli.py
git commit -m "feat: add tensorqec instance generator"
```

### Task 6: Add the two project-level skills, docs, and end-to-end repository verification

**Files:**
- Create: `.claude/skills/setup-tensorqec/SKILL.md`
- Create: `.claude/skills/generate-code-instance/SKILL.md`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `Makefile`

- [ ] **Step 1: Add a docs regression test that the repo guidance mentions the new skills**

Add to `tests/test_source_data.py`:

```python
def test_repo_docs_reference_tensorqec_skills() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "setup-tensorqec" in readme
    assert "generate-code-instance" in readme
    assert "setup-tensorqec" in claude
    assert "generate-code-instance" in claude
```

- [ ] **Step 2: Run the focused docs test to confirm the references are missing**

Run: `python3 -m pytest tests/test_source_data.py::test_repo_docs_reference_tensorqec_skills -v`
Expected: FAIL because the docs do not yet mention the new skills

- [ ] **Step 3: Add the setup skill**

`.claude/skills/setup-tensorqec/SKILL.md`

```markdown
---
name: setup-tensorqec
description: Use when setting up or verifying the repository-local Julia environment for TensorQEC-based finite code-instance generation.
---

# setup-tensorqec

## Overview

This is a project-level AutoQEC skill for preparing the repository-local `tensorQEC.jl` environment under `julia/tensorqec_env/`.

Use it when the user asks to install, configure, or verify the local TensorQEC generation environment.

## Workflow

1. Check that `julia` is available on the machine.
2. Run:

```bash
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/setup.jl
```

3. Report:
   - Julia availability
   - environment path
   - whether `TensorQEC` imported successfully
   - the smoke-test matrix dimensions
4. If the setup succeeds, recommend `generate-code-instance` for the next step.

## Failure Conditions

Stop and report clearly if:

- Julia is not installed
- package instantiation fails
- `TensorQEC` cannot be imported
- the smoke test fails
```

- [ ] **Step 4: Add the generation skill**

`.claude/skills/generate-code-instance/SKILL.md`

```markdown
---
name: generate-code-instance
description: Use when generating a finite-size CSS parity-check instance for a supported code family and storing it under zoo/codes/**/instances/.
---

# generate-code-instance

## Overview

This is a project-level AutoQEC skill for generating finite-size CSS instances with `tensorQEC.jl` and storing them in the structured Zoo layer.

Supported v1 families:

- `rotated-surface-code`
- `surface-code`
- `bivariate-bicycle-code`

## Workflow

1. Confirm that `julia/tensorqec_env/` is already set up. If not, stop and point the user to `setup-tensorqec`.
2. Resolve the target family:
   - if the user says `surface code`, ask whether they want `rotated` or `unrotated`
3. Collect required parameters one at a time:
   - rotated/unrotated surface code: `distance`
   - bivariate bicycle code: the current adapter contract fields `m`, `n`, `vc`, `hd`
4. Compute the target instance slug:
   - rotated surface code: `rotated-surface-code-d<distance>`
   - unrotated surface code: `surface-code-d<distance>`
   - BB code: `bivariate-bicycle-code-m<m>-n<n>`
5. Refuse to overwrite an existing directory under `zoo/codes/<code-id>/instances/<instance-slug>/`.
6. Run the Julia generator into a temporary directory:

```bash
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/generate_instance.jl \
  --code-id <code-id> \
  ...family-specific args... \
  --output-root <tmp-output-root>
```

7. Validate the generated bundle by loading it through the repo's Python loader if practical, then move it into:

```text
zoo/codes/<code-id>/instances/<instance-slug>/
```

8. Report the created instance id, path, parameters, and matrix dimensions.

## Rules

- Do not edit `card.json`.
- Do not route generated data through `zoo/evidence/`.
- Do not guess unsupported families.
- Stop if generation output fails schema or matrix validation.
```

- [ ] **Step 5: Add user-facing docs and small helper targets**

`README.md` addition:

```markdown
## Finite Instance Generation

This repo can generate finite-size CSS parity-check instances under `zoo/codes/**/instances/` using a repository-local Julia environment.

Project-level skills:

- `.claude/skills/setup-tensorqec`
- `.claude/skills/generate-code-instance`
```

`CLAUDE.md` addition:

```markdown
## Generated Code Instances

When the user asks to generate or store finite-size parity-check matrices, use the project skills:

- `setup-tensorqec` to prepare `julia/tensorqec_env/`
- `generate-code-instance` to create `instance.json`, `hx.json`, and `hz.json` under `zoo/codes/<code-id>/instances/`

Generated instances are program-produced source-of-truth records. They are neither canonical card facts nor paper evidence.
```

`Makefile` addition:

```make
.PHONY: tensorqec-setup

tensorqec-setup:
	julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/setup.jl
```

- [ ] **Step 6: Run the focused docs regression again**

Run: `python3 -m pytest tests/test_source_data.py::test_repo_docs_reference_tensorqec_skills -v`
Expected: PASS

- [ ] **Step 7: Run the full repository test suite**

Run: `python3 -m pytest -v`
Expected: PASS

- [ ] **Step 8: Run the build command end to end**

Run: `python3 -m autoqec_zoo.cli build --root zoo --date 2026-05-28`
Expected: PASS and stdout containing `built zoo artifacts under zoo`

- [ ] **Step 9: Run the Julia setup helper through Make**

Run: `make tensorqec-setup`
Expected: PASS and output containing `tensorqec_env ready`

- [ ] **Step 10: Commit the skills and docs**

```bash
git add .claude/skills/setup-tensorqec/SKILL.md .claude/skills/generate-code-instance/SKILL.md \
  README.md CLAUDE.md Makefile tests/test_source_data.py
git commit -m "feat: add tensorqec generation skills"
```

## Self-Review

### Spec coverage

- Two separate project-level skills: covered in Task 6
- Repository-local Julia environment under `julia/tensorqec_env/`: covered in Task 4
- V1 supported families `rotated-surface-code`, `surface-code`, `bivariate-bicycle-code`: covered in Task 5 and Task 6
- Instance storage under `zoo/codes/<code-id>/instances/<instance-slug>/`: covered in Task 1 and Task 5
- Separate `instance.json`, `hx.json`, `hz.json`: covered in Task 1 and Task 5
- `Hx/Hz` CSS-only storage: covered in Task 1, Task 2, and Task 5
- Program provenance distinct from evidence: covered in Task 1 schema and Task 5 generator payloads
- Python loader/build support for instances: covered in Task 2 and Task 3
- No `instance_refs` edits in `card.json`: enforced by Task 2 and Task 6 skill rules
- Minimal build integration without a heavy dedicated UI: covered in Task 3

### Placeholder scan

- No `TBD`, `TODO`, or “similar to Task N” placeholders remain.
- Every task includes concrete file paths, code snippets, commands, and expected outcomes.

### Type consistency

- `instance.json` uses `instance_kind`, `matrix_format`, `artifacts`, `derived_properties`, and `provenance` consistently across schema, loader, generator, and tests.
- Dataset field name `instances` is used consistently across loader and build tasks.
- Instance index filename `instance-index.json` is used consistently across build tasks and tests.
