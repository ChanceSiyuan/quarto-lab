# CSS Distance Autoresearch Worktree Log

## 2026-07-21

- Packaged proposal 002 as the experimental `quotient-coset-upper-bound`
  in-process CSS witness finder and prepared the draft PR/paper-validation
  handoff.

## 2026-07-19

- Worktree: `/Users/nzy/mcode/AutoQEC/.worktrees/css-distance-autoresearch`
- Branch: `codex/css-distance-autoresearch`
- Objective: adapt the autoresearch loop to randomized upper-bound CSS distance witness search, with 300 second hard caps per algorithm run.

### Context Checked

- Read repository instructions in `CLAUDE.md`.
- Verified this checkout is a linked worktree under the ignored `.worktrees/` root.
- Confirmed issue #38 through authenticated `gh issue view 38 --repo nzy1997/AutoQEC`.
- Confirmed issue #38 artifacts include the expanded distance ladder, `random-window-upper-bound`, external `codedistance` baselines, and the per-solver 300 second cap.
- Reviewed `.knowledge/NOTES.md` code-distance survey notes and the pinned brief bibliography.

### Dataset Handling

- The evaluator uses the issue #38 distance ladder as the source of a private holdout.
- Public proposal agents must not receive holdout answers, hidden targets, witness vectors, or private case metadata.
- Logged summaries must use sanitized scalar aggregates only.

### Implementation State

- Untracked harness files exist for:
  - `campaigns/examples/css-distance-autoresearch/source.json`
  - `campaigns/examples/css-distance-autoresearch/research-brief.md`
  - `containers/css-distance-autoresearch/`
  - `src/autoqec_search/css_distance_container.py`
  - `src/autoqec_search/css_distance_eval.py`
  - focused tests for campaign metadata, container command construction, and evaluation.
- The starting implementation is pinned to `https://github.com/m-webster/codeDistancePYPI` at commit `a4afe9c09bbf5790da9ecc05b65c5b62343979ad`.
- The source pin records the upstream license conflict: LICENSE says MIT; package metadata says GNUv3. Operator review is still required before reuse beyond experiments.

### Fixes Applied

- Added explicit `sandbox_workspace_write.network_access=false` to the Codex proposal command so proposal agents run with web search disabled and workspace-write sandbox network disabled.
- Added `src/autoqec_search/css_distance_autoresearch.py` with controller primitives for per-algorithm worktree creation, redacted proposal prompt construction, sanitized evaluation logging, and private screening/finalist scoring.
- Added `autoqec-search prepare-css-distance-algorithm` for creating isolated algorithm worktrees with `LOG.md`.
- Added `autoqec-search prepare-css-distance-proposal` for writing proposal prompts from the public brief and source pin while failing closed on private holdout markers.
- Added `autoqec-search materialize-css-distance-holdout` for creating the private issue #38 holdout without printing answer-file or case details.
- Added `autoqec-search run-css-distance-candidate` for Docker-preflighted screening/finalist evaluation of one candidate worktree with the 300 second default timeout.
- Added `run_proposal_canary` to execute the proposal-agent host/network containment canary through the same guarded Codex Docker command used for proposals.
- Added clean CLI error handling for CSS-distance evaluator/container failures.

### Baseline Candidate Worktrees

- Created `.worktrees/css-distance-codedistance-qdist-rndmw` on branch `autoresearch/css-distance/codedistance-qdist-rndmw`.
- Created `.worktrees/css-distance-codedistance-qdist-evol` on branch `autoresearch/css-distance/codedistance-qdist-evol`.
- Created `.worktrees/css-distance-codedistance-decoder-dist` on branch `autoresearch/css-distance/codedistance-decoder-dist`.
- Each worktree contains `candidate.py` and its own sanitized `LOG.md`.
- Candidate entrypoints compile with `python3 -m py_compile`.

### Runtime State

- Materialized the private holdout under `/private/tmp/autoqec-css-distance-20260719/private/holdout`.
- The first candidate screening attempt stopped at Docker preflight because `docker` is not installed in this environment.

### Verification

- `python3 -m pytest -q tests/test_search_css_distance_container.py tests/test_search_css_distance_eval.py tests/test_css_distance_autoresearch_campaign.py`
- Result: `45 passed in 0.71s`.
- `PYTHONPATH=src python3 -m pytest -q`
- Result: `1084 passed, 7 deselected in 540.19s (0:09:00)`.
- `PYTHONPATH=src python3 -m pytest -q tests/test_search_css_distance_autoresearch.py tests/test_search_css_distance_container.py tests/test_search_css_distance_eval.py tests/test_css_distance_autoresearch_campaign.py`
- Result: `51 passed in 0.91s`.
- `PYTHONPATH=src python3 -m pytest -q tests/test_search_css_distance_autoresearch.py tests/test_search_css_distance_container.py tests/test_search_css_distance_eval.py tests/test_css_distance_autoresearch_campaign.py`
- Result: `53 passed in 0.93s`.
- `PYTHONPATH=src python3 -m pytest -q tests/test_search_css_distance_autoresearch.py tests/test_search_css_distance_container.py tests/test_search_css_distance_eval.py tests/test_css_distance_autoresearch_campaign.py`
- Result: `54 passed in 0.93s`.
- `PYTHONPATH=src python3 -m pytest -q`
- Result: `1093 passed, 7 deselected in 535.89s (0:08:55)`.
- `PYTHONPATH=src python3 -m pytest -q tests/test_search_css_distance_autoresearch.py tests/test_search_css_distance_container.py tests/test_search_css_distance_eval.py tests/test_css_distance_autoresearch_campaign.py`
- Result: `56 passed in 0.95s`.
- `PYTHONPATH=src python3 -m pytest -q tests/test_search_css_distance_autoresearch.py tests/test_search_css_distance_container.py tests/test_search_css_distance_eval.py tests/test_css_distance_autoresearch_campaign.py`
- Result: `59 passed in 0.92s`.
- `PYTHONPATH=src python3 -m pytest -q`
- Result: `1098 passed, 7 deselected in 534.42s (0:08:54)`.
- `python3 -m py_compile .worktrees/css-distance-codedistance-qdist-rndmw/candidate.py .worktrees/css-distance-codedistance-qdist-evol/candidate.py .worktrees/css-distance-codedistance-decoder-dist/candidate.py`
- Result: passed.
- `PYTHONPATH=src python3 -m autoqec_search.cli materialize-css-distance-holdout --ladder benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2.json --work-root /private/tmp/autoqec-css-distance-20260719`
- Result: materialized 10 private holdout cases without printing case ids or answers.
- `PYTHONPATH=src python3 -m autoqec_search.cli run-css-distance-candidate --algorithm-id codedistance-qdist-rndmw --candidate-worktree .worktrees/css-distance-codedistance-qdist-rndmw --work-root /private/tmp/autoqec-css-distance-20260719 --image autoqec-css-distance-evaluator:a4afe9c --baseline a4afe9c09bbf5790da9ecc05b65c5b62343979ad --phase screening --timeout-seconds 300`
- Result: clean preflight failure, `Docker Desktop is required: install and start Docker Desktop, then retry.`

### Open Items

- Build the pinned proposal and evaluator container images once Docker is installed.
- Run actual baseline candidate evaluations under Docker once Docker/image preflight is ready.

## 2026-07-20 Continuation

- Completed a fresh SOTA/benchmark audit before resuming experiments.
- Committed the strict blind two-plane campaign design and implementation plan at `f571924`.
- Tightened proposal containment so only a dedicated `proposal-workspace/` can be mounted; worktree roots, symlinks, hardlinks, and private marker names are rejected.
- Repaired default Codex-auth discovery after a regression test reproduced the path-conversion bug.
- Live proposal canary passed: the container could neither read the host-only path nor reach the outbound canary URL.
- Repaired only pinned-package compatibility in the three `codedistance==0.0.8` baseline adapters; all three independently verify a weight-3 witness on the public rotated-surface d=3 fixture.
- Preserved the blinded hybrid proposal and added only AutoQEC matrix-format adaptation; its public weight-3 witness independently verifies.
- Docker and both pinned images are now available, so private screening can proceed.

### Completed Autoresearch Campaign

- Ran three pinned open-source baselines and four blinded proposals in seven dedicated experiment worktrees; every worktree has its own `LOG.md` and branch commits.
- Proposal containers received only public inputs. Live canaries passed for proposals 001 through 004: host-path access and outbound DNS were both denied.
- Corrected the public result contract after proposal 001 returned a semantically valid witness under an unaccepted status string; its original rejected result remains preserved as negative evidence.
- Found and repaired evaluator-process cleanup: every Docker run now receives a unique name and a timed-out run is force-removed in `finally`. A deliberate 0.2 second timeout left zero evaluator containers.
- Screening retained two non-dominated finalists: pinned `codedistance/decoderDist` and blinded proposal 002 randomized quotient-coset descent.
- Quality-first finalist winner: `decoderDist`, with 24 verified witnesses over 30 runs, 21 target hits, 30 weighted target hits, normalized quality 0.6222222222222222, six timeouts, and 2645.7915905839764 seconds total runtime.
- Practical recommendation: proposal 002, with 30 verified witnesses over 30 runs, 18 target hits, 24 weighted target hits, normalized quality 0.7703457807624474, zero timeouts, and 19.497326540993527 seconds total runtime.
- Proposal 002 completed the finalist set about 136 times faster while retaining 80% of the quality winner's weighted hits.
- Full sanitized findings and algorithm description are recorded in `campaigns/examples/css-distance-autoresearch/results.md`.

### Final Verification

- Focused CSS-distance harness suite: `65 passed in 1.13s`.
- Fresh full repository suite after the timeout-cleanup fix and final report: `1104 passed, 7 deselected in 510.47s (0:08:30)`.
- Public-output leakage audit found none of the private holdout markers in campaign files or experiment logs.
- All seven experiment worktrees are clean and contain committed `LOG.md` files.
- Final Docker audit found zero containers matching `autoqec-css-distance-`.

## 2026-07-21 Paper-Validation Suite Worktree

- Started the 24 blind-development / 12 sealed-final CSS-distance validation
  suite on branch `codex/css-distance-paper-validation`.
- Added Task 1 validation contracts for provenance-rich source pools and split
  manifests, including CSS commutation, rank-derived `k`, SHA-256 matrix
  hashes, canonical row-space fingerprints, duplicate construction rejection,
  duplicate row-space rejection, upper-witness verification, exact 24/12 split
  count checks, fixed family allocations, surface/toric balance, reference
  coverage, and size-band coverage.
- Added public JSON Schema contracts for source pools, split manifests, suite
  commitments, and candidate freeze records.  No split membership, case target,
  witness, matrix, or private path was committed.
- Verification: `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py -q`
  passed with `12 passed in 0.08s`.
- Compatibility check: `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py tests/test_search_css_distance_eval.py -q`
  passed with `47 passed in 0.87s`.
- Static checks: `git diff --check` and
  `python3 -m compileall -q src/autoqec_search/css_distance_suite.py` passed.
- Added Task 2 deterministic suite preparation and verification: fixed
  24-case development and 12-case final materialization, owner-only private
  directory/file modes, public salted commitments, source-pool commitment
  hashing, deterministic repeatability for an explicit secret/salt, and
  verifier failures for target, split, salt, source-pool, and matrix tampering.
- Task 2 focused verification:
  `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py -q`
  passed with `18 passed in 0.90s`.
- Task 2 compatibility verification:
  `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py tests/test_search_css_distance_eval.py -q`
  passed with `53 passed in 1.73s`.
- Static checks after Task 2: `git diff --check` and
  `python3 -m compileall -q src/autoqec_search/css_distance_suite.py` passed.
- Added Task 3 candidate freeze and sealed-final gate: clean Git worktree
  requirement, candidate file hash pinning, image digest validation, 20-seed
  minimum validation, method/config/development-summary/suite-commitment
  hashing, drift rejection before final-manifest loading, and a final-run
  ledger that blocks accidental reuse of the sealed holdout.
- Task 3 focused verification:
  `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_seal.py -q`
  passed with `10 passed in 0.94s`.
- Task 3 compatibility verification:
  `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py tests/test_search_css_distance_seal.py tests/test_search_css_distance_eval.py -q`
  passed with `63 passed in 2.55s`.
- Static checks after Task 3: `git diff --check` and
  `python3 -m compileall -q src/autoqec_search/css_distance_suite.py src/autoqec_search/css_distance_seal.py`
  passed.
- Added Task 4 CLI wiring for `prepare-css-distance-paper-suite`,
  `validate-css-distance-paper-suite`, and
  `freeze-css-distance-paper-candidate`.  The preparation and validation
  commands print only aggregate counts/status, the 300-second limit, and the
  20-seed minimum; the freeze command writes the freeze record without printing
  candidate or private paths.
- Task 4 CLI verification:
  `PYTHONPATH=src python3 -m pytest tests/test_search_cli.py -q -k 'paper_suite or paper_candidate'`
  passed with `3 passed, 21 deselected in 0.08s`.
- Task 4 focused compatibility verification:
  `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py tests/test_search_css_distance_seal.py tests/test_search_css_distance_eval.py tests/test_search_cli.py -q`
  passed with `87 passed in 5.88s`.
- Static checks after Task 4: `git diff --check` and
  `python3 -m compileall -q src/autoqec_search/css_distance_suite.py src/autoqec_search/css_distance_seal.py src/autoqec_search/cli.py`
  passed.
- Fixed a selector-policy mismatch before source-pool curation: the original
  deterministic selector required exact-reference cases inside every
  family/kind stratum, but the 36-case plan intentionally keeps APM/Kasai as
  upper-bound-only.  The selector now preserves fixed family quotas, then
  deterministically rebalances exact/upper coverage at the split level without
  changing family counts.
- Regression verification:
  `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py::test_prepare_blind_suite_accepts_upper_only_apm_when_split_coverage_holds -q`
  passed with `1 passed in 0.18s`.
- Focused compatibility verification after the selector-policy fix:
  `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py tests/test_search_css_distance_seal.py tests/test_search_css_distance_eval.py tests/test_search_cli.py -q`
  passed with `88 passed in 4.95s`.
- Added Task 5 source-pool curation artifacts under
  `benchmarks/css_distance_paper_validation/`: 36 public CSS matrix records,
  72 matrix files, fixed 20-seed manifest, curation metadata, and a rebuild
  script.  Public counts are geometric 12 (surface 6 / toric 6),
  bivariate-bicycle 9, APM/Kasai 6, and quantum Tanner 9; reference labels are
  23 exact and 13 verified upper.  No development/final split assignment,
  private root, selection secret, salt, or clear holdout manifest was committed.
- Source-pool RED/GREEN regression: the initial pool could let a low-entropy
  secret assign every large case to development, leaving the final holdout
  without large-size coverage.  Replaced one generated medium APM fixture with
  a large verified-upper APM fixture and added a zero-secret split-preparation
  regression.
- Selector robustness check:
  `PYTHONPATH=src python3 - <<'PY' ... _select_blind_cases(..., i.to_bytes(32, 'big')) for i in range(512) ... PY`
  passed for 512 deterministic secrets.
- Task 5 pool verification:
  `PYTHONPATH=src python3 -m pytest tests/test_css_distance_paper_pool.py -q`
  passed with `6 passed in 160.13s`.
- Actual CLI preparation/validation smoke test using a temporary private root
  printed only safe aggregate lines:
  `prepared blinded CSS-distance paper suite development=24 final=12` and
  `status=pass development=24 final=12 time_limit_seconds=300 minimum_seeds=20`.
- Task 5 focused compatibility verification:
  `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py tests/test_search_css_distance_seal.py tests/test_search_css_distance_eval.py tests/test_search_cli.py tests/test_css_distance_paper_pool.py -q`
  passed with `94 passed in 164.37s`.
- Static checks after Task 5: `git diff --check` and
  `python3 -m compileall -q src/autoqec_search` passed.
- Materialized the private 24/12 suite in an operator-owned root outside Git
  worktrees and committed only the public seal
  `benchmarks/css_distance_paper_validation/commitment.json`.  The committed
  commitment file SHA-256 is
  `2bf1c35b6f4a1ef52e4f6bffe05314df1d5940cccc1f0d0780891b108c0f4d4c`;
  source commit is `c34135bd511eb87f6f1a343a326a674ad6ef4770`; source-pool
  hash is `a89ec5ad816eb470cf6f9d6813372d408cdccd730c76f8cfc29bf0094f60dfcf`.
  Public salted commitments are development
  `b5cc22a218f3cfd23b8b74667e8f30af1a906242f2111a9ae47f5d85fb075b4f`,
  final `87c7afcfeed0ca1e054ef48fc9480ff8fababb7a7855d99980bc4a9436859951`,
  and selection secret
  `15637825e4dc4f7268e54d69d498f28a99b42ff0671a722addaaf445ba714712`.
- Actual Task 6 CLI validation printed only
  `status=pass development=24 final=12 time_limit_seconds=300 minimum_seeds=20`.
- Added public documentation for the operator-only suite boundary, candidate
  freeze requirement, proposal-agent non-disclosure rule, 20 committed seeds,
  and 300-second algorithm-run cap.
- Task 6 RED/GREEN verification:
  `PYTHONPATH=src python3 -m pytest tests/test_css_distance_paper_pool.py::test_css_distance_paper_commitment_is_public_and_schema_valid tests/test_css_distance_paper_pool.py::test_css_distance_paper_public_docs_do_not_leak_source_case_ids tests/test_search_docs.py::test_css_distance_paper_suite_docs_describe_operator_boundary -q`
  passed with `3 passed in 0.03s`.
- Final verification:
  `git diff --check main...HEAD` and
  `python3 -m compileall -q src/autoqec_search` passed;
  `PYTHONPATH=src python3 -m pytest tests/test_search_css_distance_suite.py tests/test_search_css_distance_seal.py tests/test_css_distance_paper_pool.py tests/test_search_css_distance_autoresearch.py tests/test_search_css_distance_container.py tests/test_search_css_distance_eval.py tests/test_search_cli.py tests/test_search_docs.py -q`
  passed with `142 passed in 171.29s`;
  `PYTHONPATH=src python3 -m autoqec_search.cli validate --root .` passed with
  `validated search workspace under .: 6 campaigns, 5 suites, 4 runs`; and
  `PYTHONPATH=src python3 -m pytest -q` passed with
  `1184 passed, 7 deselected in 566.14s (0:09:26)`.
- Private-root custody audit: operator-owned private suite exists outside all
  Git worktrees, `verify_suite_commitment` returned development 24 / final 12,
  secret/salt/manifests have `0600` mode, private split directories have
  `0700` mode, development validates with family counts
  8/6/4/6 and reference counts 16 exact / 8 upper, and final validates with
  family counts 4/3/2/3 and reference counts 7 exact / 5 upper.  Proposal-facing
  leakage scan over `LOG.md` and CSS-distance campaign public docs found zero
  source-case ids, opaque ids, secret names, or salt names; tracked-file audit
  found zero private manifest, secret, or salt artifacts.
