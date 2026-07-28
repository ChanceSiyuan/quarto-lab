# CSS Distance 24+12 Blind Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and materialize an auditable 24-instance blind CSS-distance development suite plus a 12-instance sealed final holdout without exposing case data to algorithm-proposal agents.

**Architecture:** A focused suite module validates provenance-rich source records and performs deterministic stratified selection from private randomness. A seal module owns salted commitments and candidate-freeze validation. Clear split manifests and evaluator copies stay in an owner-only private root; redistribution-approved source matrices may be committed for later public reproducibility, while proposal containers continue to mount only the redacted proposal workspace.

**Tech Stack:** Python 3.11+, stdlib `hashlib`, `json`, `secrets`, `pathlib`, `os`, existing AutoQEC GF(2) and witness helpers, JSON Schema Draft 2020-12, pytest, Git, and the pinned `qec-code` exporter.

## Global Constraints

- The suite contains exactly 24 blind development cases and 12 sealed final-holdout cases.
- Family counts are development/final: geometric 8/4, BB 6/3, APM-Kasai 4/2, and quantum Tanner 6/3.
- Geometric cases are surface/toric balanced 4/4 in development and 2/2 in final.
- At least half of each split has exact reference distance; at least one quarter of each split has only a verified upper-bound target.
- Each split represents small (`n <= 128`), medium (`129 <= n <= 512`), and large (`n > 512`) cases.
- Every randomized method/instance uses at least 20 committed seeds.
- Every algorithm invocation has a hard 300-second wall-clock limit.
- Proposal agents see no case ids, matrices, targets, witnesses, construction parameters, case rows, family rows, or development/final allocation.
- Clear manifests, selection secret, and random salt live only below an owner-only private root outside Git worktrees.
- Final evaluation is unavailable until candidate code, Git commit, image digest, method config, seed manifest, and development-summary hash are frozen.
- Exact references require exact/paper evidence. Upper references require an independently verified logical witness and remain labeled `upper`.
- External baseline code is not redistributed while the `codeDistancePYPI` license metadata conflict remains unresolved.

---

### Task 1: Add source-pool schemas and scientific validation

**Files:**
- Create: `benchmarks/schemas/css-distance-source-pool.schema.json`
- Create: `benchmarks/schemas/css-distance-split-manifest.schema.json`
- Create: `benchmarks/schemas/css-distance-suite-commitment.schema.json`
- Create: `benchmarks/schemas/css-distance-candidate-freeze.schema.json`
- Create: `src/autoqec_search/css_distance_suite.py`
- Create: `tests/test_search_css_distance_suite.py`

**Interfaces:**
- Consumes: existing `matrix_data()`, `gf2_rank()`, and `verify_css_upper_bound_witness()` from `autoqec_search.structure`.
- Produces: `ValidatedSuiteCase`, `canonical_json_bytes(payload)`, `canonical_rowspace_fingerprint(rows)`, `load_and_validate_source_pool(root, path)`, and `validate_split_manifest(root, payload, source_cases)`.

- [ ] **Step 1: Write failing source-record and matrix-integrity tests**

Add fixture helpers that write sparse-row matrices and construct records with this exact shape:

```python
def _record(case_id: str, family: str, construction_kind: str) -> dict:
    return {
        "case_id": case_id,
        "family": family,
        "construction_kind": construction_kind,
        "construction": {"name": case_id},
        "n": 5,
        "k": 1,
        "hx_path": f"instances/{case_id}/hx.json",
        "hz_path": f"instances/{case_id}/hz.json",
        "hx_sha256": "filled-by-helper",
        "hz_sha256": "filled-by-helper",
        "hx_rowspace_sha256": "filled-by-helper",
        "hz_rowspace_sha256": "filled-by-helper",
        "reference": {
            "bound_type": "exact",
            "value": 3,
            "evidence": {"kind": "fixture", "citation": "test"},
        },
        "provenance": {
            "source_repository": "https://example.test/source",
            "source_commit": "a" * 40,
            "generator_command": ["fixture-generator", case_id],
            "license_status": "redistribution-approved",
        },
    }
```

Cover: valid exact record; valid upper record with verified X witness; unsafe paths; hash drift; noncommuting checks; incorrect `k`; invalid upper witness; unknown family; duplicate construction canonical JSON; and duplicate `(hx_rowspace_sha256, hz_rowspace_sha256)`.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py -q
```

Expected: collection fails because `autoqec_search.css_distance_suite` does not exist.

- [ ] **Step 3: Add strict Draft 2020-12 schemas**

Use `additionalProperties: false` at every record layer. Define exact enums:

```json
{
  "family": {"enum": ["geometric", "bivariate-bicycle", "apm-kasai", "quantum-tanner"]},
  "construction_kind": {"enum": ["surface", "toric", "bb", "apm-kasai", "quantum-tanner"]},
  "bound_type": {"enum": ["exact", "upper"]},
  "license_status": {"const": "redistribution-approved"}
}
```

The source schema requires every field shown in Step 1. The split schema requires `schema_version`, `split`, `created_at`, and `cases`; split is `development` or `final`. The commitment schema contains only safe counts, hashes, timestamps, and policy versions. The freeze schema contains only candidate and configuration hashes—never case data.

- [ ] **Step 4: Implement canonicalization, RREF fingerprinting, and record validation**

Start `css_distance_suite.py` with these public contracts:

```python
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json

from autoqec_search.load import SearchIntegrityError
from autoqec_search.structure import gf2_rank, matrix_data, verify_css_upper_bound_witness

FAMILY_COUNTS = {
    "development": {"geometric": 8, "bivariate-bicycle": 6, "apm-kasai": 4, "quantum-tanner": 6},
    "final": {"geometric": 4, "bivariate-bicycle": 3, "apm-kasai": 2, "quantum-tanner": 3},
}
GEOMETRIC_KIND_COUNTS = {
    "development": {"surface": 4, "toric": 4},
    "final": {"surface": 2, "toric": 2},
}
TIME_LIMIT_SECONDS = 300
MINIMUM_SEEDS = 20

@dataclass(frozen=True)
class ValidatedSuiteCase:
    record: dict
    hx_payload: dict
    hz_payload: dict

def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
```

Implement canonical GF(2) RREF by converting each row to an integer, eliminating every pivot from all other rows, sorting nonzero rows by pivot, and hashing canonical JSON of the resulting dense rows. Validate paths descriptor-safely or with existing no-follow helpers, compare file and row-space hashes, check `H_X H_Z^T = 0`, and calculate `k = n - rank(H_X) - rank(H_Z)`. For `upper`, require `reference.witness` and require `verify_css_upper_bound_witness(...)["status"] == "pass"` with weight equal to `reference.value`.

- [ ] **Step 5: Implement source-pool and split-level invariants**

`load_and_validate_source_pool()` must return a tuple sorted by `case_id`, reject duplicate ids/constructions/row spaces, and never include a private path in an error. `validate_split_manifest()` must check exact family and geometric-kind counts, no overlap, minimum exact/upper fractions, all three size bands, and construction parameters/sizes absent from the other split.

- [ ] **Step 6: Run focused tests and confirm GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py -q
```

Expected: all Task 1 tests pass.

- [ ] **Step 7: Commit**

```bash
git add benchmarks/schemas/css-distance-*.schema.json src/autoqec_search/css_distance_suite.py tests/test_search_css_distance_suite.py
git commit -m "feat(search): validate CSS distance paper source pool"
```

---

### Task 2: Implement private stratified selection and salted commitments

**Files:**
- Modify: `src/autoqec_search/css_distance_suite.py`
- Modify: `tests/test_search_css_distance_suite.py`

**Interfaces:**
- Consumes: validated source cases and fixed allocation constants from Task 1.
- Produces: `prepare_blind_suite(root, source_pool_path, work_root, commitment_path, created_at, secret=None, salt=None) -> dict`, `verify_suite_commitment(private_root, commitment) -> dict`, and owner-only clear manifests below `work_root/private/css-distance-paper-suite/`.

- [ ] **Step 1: Write failing 24/12 selection and tamper tests**

Build a 48-case eligible fixture pool so selection has choices in every stratum. Call:

```python
commitment = prepare_blind_suite(
    root=tmp_path,
    source_pool_path=Path("pool.json"),
    work_root=tmp_path / "operator",
    commitment_path=tmp_path / "commitment.json",
    created_at="2026-07-21T00:00:00Z",
    secret=bytes(range(32)),
    salt=bytes(range(32, 64)),
)
```

Assert exactly 24/12 records, fixed family counts, 4/4 and 2/2 geometric balance, deterministic repeated output, opaque case names, mode `0700` directories and `0600` secret/manifests, no private fields in the public commitment, and passing commitment verification. Add negative controls that alter one target, split assignment, salt, source-pool root, and matrix hash.

- [ ] **Step 2: Run the selection tests and confirm RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py -q -k 'selection or commitment or permissions'
```

Expected: failures because selection and commitment functions are absent.

- [ ] **Step 3: Implement deterministic stratified ordering**

Use an HMAC-like deterministic score without adding dependencies:

```python
def _selection_score(secret: bytes, label: str, case_id: str) -> bytes:
    return hashlib.sha256(secret + b"\x00" + label.encode() + b"\x00" + case_id.encode()).digest()
```

First allocate family and geometric-kind quotas. Within each stratum, enforce reference and size-band coverage, then order remaining eligible cases by `_selection_score`. Reject insufficient strata instead of rebalancing. Use stable opaque ids `development-000` through `development-023` and `final-000` through `final-011` only inside evaluator-facing copies; preserve the reveal mapping in the private manifest.

Reject `work_root` if it is equal to or nested below any path returned by `git worktree list --porcelain`. Resolve this check before creating the private root, without following symlinks. This makes the operator boundary structural rather than dependent on an ignored directory convention.

- [ ] **Step 4: Write clear private artifacts atomically**

Create:

```text
work_root/private/css-distance-paper-suite/
  selection-secret.bin
  salt.bin
  development/manifest.json
  development/development-000/hx.json (and development-001 through development-023)
  development/development-000/hz.json (and development-001 through development-023)
  final/manifest.json
  final/final-000/hx.json (and final-001 through final-011)
  final/final-000/hz.json (and final-001 through final-011)
```

Use `os.open(..., 0o600)` with `O_CREAT|O_EXCL|O_NOFOLLOW`, directory mode `0700`, fsync, and atomic rename. Do not overwrite an existing private suite.

- [ ] **Step 5: Build and verify the public commitment**

Hash `salt || canonical_manifest`, `salt || secret`, and canonical source-pool records. The public payload is exactly:

```python
{
    "schema_version": 1,
    "selection_policy_version": 1,
    "created_at": created_at,
    "source_commit": source_commit,
    "counts": {"development": 24, "final": 12},
    "family_counts": FAMILY_COUNTS,
    "geometric_kind_counts": GEOMETRIC_KIND_COUNTS,
    "source_pool_sha256": source_pool_hash,
    "development_manifest_commitment": salted_hash(dev_manifest),
    "final_manifest_commitment": salted_hash(final_manifest),
    "selection_secret_commitment": salted_hash(secret),
}
```

`verify_suite_commitment()` returns safe counts and `status=pass`; errors contain only safe labels.

- [ ] **Step 6: Run focused tests and confirm GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/autoqec_search/css_distance_suite.py tests/test_search_css_distance_suite.py
git commit -m "feat(search): seal 24+12 CSS distance split"
```

---

### Task 3: Add candidate freeze and final-open gate

**Files:**
- Create: `src/autoqec_search/css_distance_seal.py`
- Create: `tests/test_search_css_distance_seal.py`

**Interfaces:**
- Consumes: suite commitment, private final manifest, seed manifest, candidate worktree, container image digest, method config, and development summary.
- Produces: `create_candidate_freeze(...) -> dict`, `validate_candidate_freeze(...) -> dict`, and `open_final_manifest(...) -> dict`.

- [ ] **Step 1: Write failing freeze/gate tests**

Initialize a temporary Git repository with committed `candidate.py`. Assert freeze succeeds only for a clean worktree and records:

```python
{
    "schema_version": 1,
    "created_at": "2026-07-21T00:00:00Z",
    "git_commit": "0000000000000000000000000000000000000000",
    "candidate_path": "candidate.py",
    "candidate_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "image_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "method_config_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "seed_manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "development_summary_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "suite_commitment_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "time_limit_seconds": 300,
}
```

Negative controls: no freeze, dirty worktree, candidate change, checkout change, image/config/seed drift, malformed digest, suite commitment drift, and an existing final-run ledger. Patch the final-manifest loader and assert every rejection happens before it is called.

- [ ] **Step 2: Run tests and confirm RED**

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_seal.py -q
```

Expected: import failure for `css_distance_seal`.

- [ ] **Step 3: Implement freeze creation**

Use non-interactive `git status --porcelain` and `git rev-parse HEAD`. Restrict `candidate_path` to a regular file below the worktree. Hash canonical JSON for method config, seed manifest, development summary, and suite commitment. Require an image digest matching `^sha256:[0-9a-f]{64}$`, exactly `time_limit_seconds=300`, and at least 20 unique plain-integer seeds.

- [ ] **Step 4: Implement fail-closed final opening**

`open_final_manifest()` must validate all freeze inputs and commitment material before reading the private final manifest. It creates an append-only `final-run-ledger.jsonl` attempt record before returning data. If the ledger already contains a non-infrastructure attempt for the same suite commitment, reject reuse. The returned manifest remains in process memory and is never printed.

- [ ] **Step 5: Run tests and confirm GREEN**

Run the command from Step 2. Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/autoqec_search/css_distance_seal.py tests/test_search_css_distance_seal.py
git commit -m "feat(search): gate sealed CSS distance holdout"
```

---

### Task 4: Expose preparation, validation, and freeze CLIs

**Files:**
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_cli.py`
- Modify: `tests/test_search_css_distance_suite.py`
- Modify: `tests/test_search_css_distance_seal.py`

**Interfaces:**
- Consumes: Task 1-3 APIs.
- Produces: `prepare-css-distance-paper-suite`, `validate-css-distance-paper-suite`, and `freeze-css-distance-paper-candidate` commands.

- [ ] **Step 1: Write failing CLI tests**

Test exact parser names and safe output. Preparation arguments:

```text
--root --source-pool --work-root --commitment-out --created-at
```

Validation arguments:

```text
--root --source-pool --work-root --commitment
```

Freeze arguments:

```text
--candidate-worktree --candidate --image-digest --method-config --seeds
--development-summary --commitment --out --created-at
```

Preparation stdout must equal `prepared blinded CSS-distance paper suite development=24 final=12`; validation stdout must equal `status=pass development=24 final=12 time_limit_seconds=300 minimum_seeds=20`; neither may print a private root or case data.

- [ ] **Step 2: Run CLI tests and confirm RED**

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_cli.py tests/test_search_css_distance_suite.py tests/test_search_css_distance_seal.py -q -k 'paper_suite or paper_candidate'
```

Expected: parser/dispatch failures because commands are not registered.

- [ ] **Step 3: Add parsers and dispatch**

Import only public Task 1-3 functions in `cli.py`. Route all expected integrity failures through existing clean CLI error handling. Never include exception payloads that contain private data. Require the repository root and all public inputs to exist before invoking the preparation function.

- [ ] **Step 4: Run CLI tests and confirm GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/cli.py tests/test_search_cli.py tests/test_search_css_distance_suite.py tests/test_search_css_distance_seal.py
git commit -m "feat(search): expose blinded CSS distance suite cli"
```

---

### Task 5: Curate and materialize the 36-case scientific source pool

**Files:**
- Create: `benchmarks/css_distance_paper_validation/source_pool.json`
- Create: `benchmarks/css_distance_paper_validation/seeds.json`
- Create: `benchmarks/css_distance_paper_validation/curation.json`
- Create: `benchmarks/css_distance_paper_validation/README.md`
- Create: `scripts/build_css_distance_paper_pool.py`
- Create: `tests/test_css_distance_paper_pool.py`
- Create/modify: `benchmarks/css_distance_paper_validation/instances/**`

**Interfaces:**
- Consumes: issue #38 matrices, qec-code generation, repository knowledge/evidence records, paper-pinned BB polynomial definitions, APM affine tables/witnesses, and quantum-Tanner generation contracts.
- Produces: 36 redistribution-approved source records that pass `load_and_validate_source_pool()` and satisfy the candidate counts needed by the split selector.

- [ ] **Step 1: Write the failing committed-pool test**

Assert 36 entries and these exact family totals:

```python
assert Counter(case.record["family"] for case in cases) == {
    "geometric": 12,
    "bivariate-bicycle": 9,
    "apm-kasai": 6,
    "quantum-tanner": 9,
}
```

Also assert the 20 fixed seeds are unique plain integers, no absolute paths occur, all license statuses are approved, all matrix hashes/fingerprints match, and all upper witnesses verify.

- [ ] **Step 2: Run the pool test and confirm RED**

```bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_paper_pool.py -q
```

Expected: failure because the pool does not exist.

- [ ] **Step 3: Build 12 geometric cases**

Use pinned qec-code exports for surface and toric distances `5, 7, 9, 11, 13, 17`. Record exact references from the family formulas. This gives six surface and six toric cases spanning small, medium, and large size bands.

- [ ] **Step 4: Build nine non-equivalent BB cases**

Implement the standard commuting bivariate circulant construction in the curation script and pin polynomial records from repository paper evidence. Use six exact-reference cases and three upper-reference stress cases. Include issue #38 `bb72` and `bb144`, Bravyi et al. Table 3 constructions with different `(l,m,A,B)`, and at least two coprime-BB constructions from Wang and Mueller Table 2/4. Reject disconnected or canonical-rowspace-duplicate outputs.

- [ ] **Step 5: Import six APM/Kasai cases**

Use six distinct affine-map rows from Kasai's representative-code Table 2, including issue #38-compatible cases and multiple `P` values. Pin the source artifact/repository commit, import the corresponding sparse checks and reported witnesses, and independently verify every upper witness. All six remain `bound_type=upper`.

- [ ] **Step 6: Build nine quantum-Tanner cases**

Use the pinned quantum-Tanner generator/materializer with distinct construction specs, including issue #38 toric d4/d6/d8 fixtures and six additional finite specs. Require unique construction canonical JSON and row-space fingerprints. Prefer more than one local-code/group construction when redistribution-safe material is available; otherwise record the toric sweep limitation explicitly in curation metadata and do not claim family-wide generalization.

- [ ] **Step 7: Commit the seed and curation manifests**

Use this exact seed list:

```json
{
  "schema_version": 1,
  "time_limit_seconds": 300,
  "seeds": [104729, 130363, 155921, 196613, 262147, 327673, 393241, 458789, 524309, 589867, 655373, 720899, 786433, 851971, 917519, 983063, 1048583, 1114129, 1179661, 1245187]
}
```

`curation.json` records the source pin, generator command, paper/evidence key, redistribution decision, and reference type for each case. Do not include split assignments.

- [ ] **Step 8: Run pool validation and confirm GREEN**

```bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_paper_pool.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate-css-distance-paper-suite --root . --source-pool benchmarks/css_distance_paper_validation/source_pool.json --work-root "$PRIVATE_SUITE_ROOT" --commitment benchmarks/css_distance_paper_validation/commitment.json
```

Before Task 6 creates the private split, the first command passes and the second is expected to fail safely with `private suite is not materialized`.

- [ ] **Step 9: Commit**

```bash
git add benchmarks/css_distance_paper_validation benchmarks/schemas scripts/build_css_distance_paper_pool.py tests/test_css_distance_paper_pool.py
git commit -m "data: curate CSS distance paper source pool"
```

---

### Task 6: Commit the split seal, logs, and operator workflow

**Files:**
- Create: `benchmarks/css_distance_paper_validation/commitment.json`
- Modify: `benchmarks/css_distance_paper_validation/README.md`
- Modify: `campaigns/examples/css-distance-autoresearch/README.md`
- Modify: `LOG.md`
- Modify: `tests/test_search_docs.py`
- Modify: `tests/test_css_distance_paper_pool.py`

**Interfaces:**
- Consumes: the 36-case source pool, Task 4 preparation CLI, and a new operator-owned private root.
- Produces: one committed safe commitment proving a 24/12 split and an owner-only materialized suite ready for blind development evaluation.

- [ ] **Step 1: Add failing commitment and leakage tests**

Assert `commitment.json` validates against its schema and contains exact safe counts but none of these keys or values recursively: `case_id`, `construction`, `hx_path`, `hz_path`, `reference`, `witness`, `target`, `development-000`, or `final-000`. Scan tracked docs, `LOG.md`, and experiment logs for all source case ids selected into either split; the only allowed occurrences are source-pool/curation artifacts, never proposal prompts or algorithm logs.

- [ ] **Step 2: Materialize the private split**

Set an explicit private path outside the repository, create it with `0700`, and run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli prepare-css-distance-paper-suite \
  --root . \
  --source-pool benchmarks/css_distance_paper_validation/source_pool.json \
  --work-root "$PRIVATE_SUITE_ROOT" \
  --commitment-out benchmarks/css_distance_paper_validation/commitment.json \
  --created-at 2026-07-21T00:00:00Z
```

Expected stdout: `prepared blinded CSS-distance paper suite development=24 final=12` with no path or case data.

- [ ] **Step 3: Validate the materialized split**

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate-css-distance-paper-suite \
  --root . \
  --source-pool benchmarks/css_distance_paper_validation/source_pool.json \
  --work-root "$PRIVATE_SUITE_ROOT" \
  --commitment benchmarks/css_distance_paper_validation/commitment.json
```

Expected stdout: `status=pass development=24 final=12 time_limit_seconds=300 minimum_seeds=20`.

- [ ] **Step 4: Document the operator-only boundary and update LOG.md**

Document preparation, validation, backup/reveal custody, proposal containment, candidate freeze, and the prohibition on final evaluation before freeze. In `LOG.md`, record only safe counts, command names, commitment hashes, source commit, and test results.

- [ ] **Step 5: Run negative controls**

On copies below a temporary private root, verify nonzero exits for: 23 development cases, 11 final cases, altered target, altered matrix, altered witness, swapped split, bad salt, fewer than 20 seeds, and final open without freeze. Confirm stdout/stderr contain none of the private markers.

- [ ] **Step 6: Run focused tests and commit**

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py tests/test_search_css_distance_seal.py tests/test_css_distance_paper_pool.py tests/test_search_docs.py -q
git add benchmarks/css_distance_paper_validation/commitment.json benchmarks/css_distance_paper_validation/README.md campaigns/examples/css-distance-autoresearch/README.md LOG.md tests/test_search_docs.py tests/test_css_distance_paper_pool.py
git commit -m "docs: seal 24+12 CSS distance validation suite"
```

Expected: all focused tests pass and the commit contains no clear split manifest or secret.

---

### Task 7: Complete verification and handoff

**Files:**
- Modify only if verification reveals a defect in Task 1-6 files.

**Interfaces:**
- Consumes: the complete branch and operator-owned materialized suite.
- Produces: evidence that every design requirement is met and a clean branch ready for review.

- [ ] **Step 1: Run formatting and static checks**

```bash
git diff --check main...HEAD
python3 -m compileall -q src/autoqec_search
```

Expected: both exit zero.

- [ ] **Step 2: Run the full focused suite**

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_css_distance_suite.py \
  tests/test_search_css_distance_seal.py \
  tests/test_css_distance_paper_pool.py \
  tests/test_search_css_distance_autoresearch.py \
  tests/test_search_css_distance_container.py \
  tests/test_search_css_distance_eval.py \
  tests/test_search_cli.py \
  tests/test_search_docs.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run repository validation and full tests**

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m pytest -q
```

Expected: workspace validation and all non-deselected tests pass.

- [ ] **Step 4: Audit requirements and leakage**

Check every numbered verification item in the design against test names and current artifacts. Run `git status --short`, inspect `git diff main...HEAD`, verify the private root is outside every listed Git worktree, and scan tracked files plus experiment `LOG.md` files for private manifest values. Any missing or indirect evidence is a failure, not a completion claim.

- [ ] **Step 5: Commit verification fixes, if any**

```bash
git add benchmarks/css_distance_paper_validation benchmarks/schemas/css-distance-candidate-freeze.schema.json benchmarks/schemas/css-distance-source-pool.schema.json benchmarks/schemas/css-distance-split-manifest.schema.json benchmarks/schemas/css-distance-suite-commitment.schema.json campaigns/examples/css-distance-autoresearch/README.md scripts/build_css_distance_paper_pool.py src/autoqec_search/css_distance_seal.py src/autoqec_search/css_distance_suite.py src/autoqec_search/cli.py tests/test_css_distance_paper_pool.py tests/test_search_cli.py tests/test_search_css_distance_seal.py tests/test_search_css_distance_suite.py tests/test_search_docs.py LOG.md
git commit -m "fix(search): close blind suite verification gaps"
```

Skip this step if no files changed.

- [ ] **Step 6: Prepare review handoff**

Report the 24/12 counts, family allocations, commitment hash, private-root custody status, seed count, 300-second limit, negative-control outcomes, focused/full test results, and remaining work for the five-method 20-seed execution. Do not report case identities, split membership, targets, or witnesses.
