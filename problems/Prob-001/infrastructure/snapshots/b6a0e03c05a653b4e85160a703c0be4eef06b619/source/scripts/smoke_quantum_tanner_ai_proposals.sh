#!/usr/bin/env bash
set -euo pipefail

RUN_ID="qt-ai-proposal-smoke"
WORK_ROOT=""
CHECK_TORIC_ONLY_RESPONSE=0
KEEP_EXISTING_WORK_ROOT=0

usage() {
  cat <<'EOF'
Usage:
  scripts/smoke_quantum_tanner_ai_proposals.sh --work-root <path> [--check-toric-only-response] [--keep-existing-work-root]

Environment:
  QEC_CODE_BIN   qec-code executable path or command name (default: qec-code)
  RSINTER_BIN    rsinter executable path or command name (default: rsinter)
EOF
}

fail() {
  echo "FAIL quantum_tanner_ai_proposal_smoke" >&2
  echo "error: $*" >&2
  exit 1
}

canonicalize_path() {
  python3 - "$1" <<'PY'
import sys
from pathlib import Path

print(Path(sys.argv[1]).expanduser().resolve(strict=False))
PY
}

resolve_executable() {
  local configured="$1"
  local label="$2"
  if [[ -z "$configured" ]]; then
    fail "$label executable is empty"
  fi
  if [[ "$configured" == */* ]]; then
    if [[ ! -x "$configured" ]]; then
      fail "$label executable is not executable: $configured"
    fi
    local dir
    dir="$(cd "$(dirname "$configured")" && pwd -P)"
    printf '%s/%s\n' "$dir" "$(basename "$configured")"
    return
  fi
  local found
  found="$(command -v "$configured" || true)"
  if [[ -z "$found" ]]; then
    fail "$label executable not found on PATH: $configured"
  fi
  printf '%s\n' "$found"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-root)
      [[ $# -ge 2 ]] || fail "--work-root requires a path"
      WORK_ROOT="$2"
      shift 2
      ;;
    --check-toric-only-response)
      CHECK_TORIC_ONLY_RESPONSE=1
      shift
      ;;
    --keep-existing-work-root)
      KEEP_EXISTING_WORK_ROOT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ -n "$WORK_ROOT" ]] || fail "--work-root is required"

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
WORK_ROOT="$(canonicalize_path "$WORK_ROOT")"
QEC_CODE_BIN_RESOLVED=""
RSINTER_BIN_RESOLVED=""

reject_work_root_inside_source() {
  local source_prefix="${SOURCE_ROOT%/}/"
  local work_prefix="${WORK_ROOT%/}/"
  if [[ "$work_prefix" == "$source_prefix"* ]]; then
    fail "--work-root must be outside the caller checkout: $WORK_ROOT"
  fi
}

resolve_backend_executables() {
  QEC_CODE_BIN_RESOLVED="$(resolve_executable "${QEC_CODE_BIN:-qec-code}" "qec-code")"
  RSINTER_BIN_RESOLVED="$(resolve_executable "${RSINTER_BIN:-rsinter}" "rsinter")"
  local shim_dir="$WORK_ROOT/tool-shims"
  local rsinter_shim="$shim_dir/rsinter"
  mkdir -p "$shim_dir"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'exec %q "$@"\n' "$RSINTER_BIN_RESOLVED"
  } > "$rsinter_shim"
  chmod +x "$rsinter_shim"
  export PATH="$shim_dir:$(dirname "$QEC_CODE_BIN_RESOLVED"):$PATH"
}

prepare_work_root() {
  reject_work_root_inside_source
  if [[ -e "$WORK_ROOT" ]]; then
    if [[ ! -d "$WORK_ROOT" ]]; then
      fail "--work-root exists and is not a directory: $WORK_ROOT"
    fi
    if [[ "$KEEP_EXISTING_WORK_ROOT" -ne 1 && -n "$(ls -A "$WORK_ROOT")" ]]; then
      fail "--work-root must be empty or use --keep-existing-work-root: $WORK_ROOT"
    fi
  else
    mkdir -p "$WORK_ROOT"
  fi
  CHECKOUT="$WORK_ROOT/checkout"
  if [[ -e "$CHECKOUT" ]]; then
    fail "checkout already exists: $CHECKOUT"
  fi
  git clone --quiet --local "$SOURCE_ROOT" "$CHECKOUT"
  git -C "$CHECKOUT" config user.email "autoqec@example.com"
  git -C "$CHECKOUT" config user.name "AutoQEC Smoke"
  AI_BATCH_ROOT="$WORK_ROOT/ai-batch"
  INGESTED_ROOT="$AI_BATCH_ROOT/ingested"
  WORKTREE_AI_BATCH_ROOT="$CHECKOUT/.worktrees/$RUN_ID/ai-batch"
}

run_cli() {
  PYTHONPATH="$CHECKOUT/src" python3 -m autoqec_search.cli "$@"
}

commit_temp_checkout() {
  local message="$1"
  git -C "$CHECKOUT" add -A
  if git -C "$CHECKOUT" diff --cached --quiet; then
    return
  fi
  git -C "$CHECKOUT" commit -m "$message" >/dev/null
}

prepare_ai_batch() {
  mkdir -p "$AI_BATCH_ROOT"
  run_cli prepare-quantum-tanner-ai-batch \
    --root "$CHECKOUT" \
    --campaign quantum-tanner-autoresearch \
    --out "$AI_BATCH_ROOT/request" \
    --count 2 \
    --max-group-order 32 \
    --max-physical-qubits 64
}

ingest_mixed_response() {
  mkdir -p "$INGESTED_ROOT"
  run_cli ingest-quantum-tanner-ai-batch \
    --root "$CHECKOUT" \
    --response "$CHECKOUT/tests/fixtures/quantum_tanner_ai_responses/mixed-valid-invalid.json" \
    --out "$INGESTED_ROOT" \
    --max-group-order 32 \
    --max-physical-qubits 64
}

ingest_toric_only_response() {
  local response_path="$AI_BATCH_ROOT/toric-only-response.json"
  python3 - "$CHECKOUT" "$response_path" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
out_path = Path(sys.argv[2])
proposal_path = (
    root
    / "tests"
    / "fixtures"
    / "quantum_tanner_proposals"
    / "known-toric-template-duplicate.json"
)
proposal = json.loads(proposal_path.read_text())
payload = {
    "response_metadata": {
        "source": "fixture",
        "model": "offline-fixture",
        "generated_at": "2026-07-10T00:00:00Z",
    },
    "proposals": [proposal],
}
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY
  mkdir -p "$INGESTED_ROOT"
  run_cli ingest-quantum-tanner-ai-batch \
    --root "$CHECKOUT" \
    --response "$response_path" \
    --out "$INGESTED_ROOT" \
    --max-group-order 32 \
    --max-physical-qubits 64
}

reset_campaign_search_space() {
  python3 - "$CHECKOUT" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
path = root / "campaigns/examples/quantum-tanner-autoresearch/search_space.json"
path.unlink()
PY
}

accepted_proposal_paths() {
  python3 - "$INGESTED_ROOT/summary.json" "$INGESTED_ROOT" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text())
root = Path(sys.argv[2])
for record in summary["accepted_records"]:
    print(root / record["path"])
PY
}

materialize_accepted_proposals() {
  local proposals=()
  while IFS= read -r proposal; do
    proposals+=("$proposal")
  done < <(accepted_proposal_paths)
  [[ "${#proposals[@]}" -gt 0 ]] || fail "AI response accepted no proposals"

  local proposal_args=()
  local proposal
  for proposal in "${proposals[@]}"; do
    proposal_args+=(--proposal "$proposal")
  done

  run_cli materialize-quantum-tanner-proposals \
    --root "$CHECKOUT" \
    --out-root campaigns/examples/quantum-tanner-autoresearch/proposal-instances \
    --qec-code-bin "$QEC_CODE_BIN_RESOLVED" \
    --force \
    "${proposal_args[@]}"
}

import_proposal_instances() {
  run_cli import-quantum-tanner-proposal-instances \
    --root "$CHECKOUT" \
    --campaign quantum-tanner-autoresearch \
    --instance-root campaigns/examples/quantum-tanner-autoresearch/proposal-instances \
    --search-space campaigns/examples/quantum-tanner-autoresearch/search_space.json
}

prune_search_space_to_proposals() {
  python3 - "$CHECKOUT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
path = root / "campaigns/examples/quantum-tanner-autoresearch/search_space.json"
search_space = json.loads(path.read_text())
candidate_specs = search_space.get("candidate_specs", [])
proposal_candidates = [
    candidate
    for candidate in candidate_specs
    if candidate.get("provenance", {}).get("kind") == "proposal-derived"
]
if not proposal_candidates:
    raise SystemExit("no proposal-derived candidates found after import")
search_space["candidate_specs"] = proposal_candidates
path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")
PY
}

write_witnesses_and_patch_search_space() {
  python3 - "$CHECKOUT" "$QEC_CODE_BIN_RESOLVED" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
qec_code = sys.argv[2]
search_space_path = root / "campaigns/examples/quantum-tanner-autoresearch/search_space.json"
witness_dir = root / "campaigns/examples/quantum-tanner-autoresearch/witnesses"
witness_dir.mkdir(parents=True, exist_ok=True)
search_space = json.loads(search_space_path.read_text())
for candidate in search_space["candidate_specs"]:
    candidate_id = candidate["candidate_id"]
    instance_dir = root / candidate["instance_path"]
    witness_path = witness_dir / f"{candidate_id}-upper-bound-witness.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "find-upper-bound-witness",
            "--hx",
            str(instance_dir / "hx.json"),
            "--hz",
            str(instance_dir / "hz.json"),
            "--basis",
            "x",
            "--out",
            str(witness_path),
            "--qec-code-bin",
            qec_code,
            "--iterations",
            "32",
            "--restarts",
            "1",
            "--seed",
            "12345",
            "--timeout-seconds",
            "60",
        ],
        check=True,
        cwd=root,
        env={"PYTHONPATH": str(root / "src"), **os.environ},
    )
    candidate["upper_bound_witness_path"] = str(witness_path.relative_to(root))
search_space_path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")
PY
}

complete_observables() {
  run_cli complete-quantum-tanner-proposal-observables \
    --root "$CHECKOUT" \
    --search-space campaigns/examples/quantum-tanner-autoresearch/search_space.json \
    --basis x \
    --qec-code-bin "$QEC_CODE_BIN_RESOLVED" \
    --force
}

run_autoresearch_smoke() {
  run_cli validate --root "$CHECKOUT"
  commit_temp_checkout "prepare quantum Tanner AI proposal smoke inputs"
  run_cli run \
    --root "$CHECKOUT" \
    --campaign quantum-tanner-autoresearch \
    --wall-clock 90s \
    --run-id "$RUN_ID" \
    --distance-method random-window-upper-bound \
    --qec-code-bin "$QEC_CODE_BIN_RESOLVED"
}

write_comparison_and_feedback() {
  local worktree_root="$CHECKOUT/.worktrees/$RUN_ID"
  RUN_ROOT="$worktree_root/results/search/quantum-tanner-autoresearch/$RUN_ID"
  mkdir -p "$WORKTREE_AI_BATCH_ROOT"
  cp -R "$AI_BATCH_ROOT/." "$WORKTREE_AI_BATCH_ROOT/"
  run_cli compare-surface-copy \
    --root "$worktree_root" \
    --run "results/search/quantum-tanner-autoresearch/$RUN_ID" \
    --baseline benchmarks/baselines/rotated-surface-single-logical-p001.json \
    --out "$RUN_ROOT/surface-copy-comparison.html"
  run_cli summarize-quantum-tanner-ai-feedback \
    --root "$worktree_root" \
    --run "results/search/quantum-tanner-autoresearch/$RUN_ID" \
    --proposal-summary "$INGESTED_ROOT/summary.json" \
    --surface-copy "$RUN_ROOT/surface-copy-comparison.json" \
    --out-json "$RUN_ROOT/quantum-tanner-ai-feedback.json" \
    --out-html "$RUN_ROOT/quantum-tanner-ai-feedback.html"
}

verify_default_smoke() {
  PYTHONPATH="$CHECKOUT/src" python3 - "$RUN_ROOT" "$INGESTED_ROOT/summary.json" <<'PY'
import json
import sys
from pathlib import Path

from autoqec_search.quantum_tanner_proposals import validate_quantum_tanner_proposal

run_root = Path(sys.argv[1])
summary = json.loads(Path(sys.argv[2]).read_text())

def fail(message: str) -> None:
    print("FAIL quantum_tanner_ai_proposal_smoke", file=sys.stderr)
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)

if summary.get("accepted") != 1:
    fail(f"accepted count is {summary.get('accepted')!r}")
if summary.get("rejected") != 1:
    fail(f"rejected count is {summary.get('rejected')!r}")

accepted_records = summary.get("accepted_records", [])
non_toric = 0

def is_known_toric_template(proposal: dict) -> bool:
    group = proposal["base_group"]
    order = int(group["order"])
    root = int(order**0.5)
    if root * root != order or group.get("identity") != 0:
        return False
    a_generators = set(proposal["a_generator_indices"])
    b_generators = set(proposal["b_generator_indices"])
    x_generators = {root, root * (root - 1)}
    y_generators = {1, root - 1}
    if not (
        (a_generators == x_generators and b_generators == y_generators)
        or (a_generators == y_generators and b_generators == x_generators)
    ):
        return False
    local_codes = proposal["local_codes"]
    if local_codes["h_a"] != [[1, 1]] or local_codes["h_b"] != [[1, 1]]:
        return False
    table = group["multiplication_table"]
    for left in range(order):
        lx, ly = divmod(left, root)
        for right in range(order):
            rx, ry = divmod(right, root)
            expected = root * ((lx + rx) % root) + ((ly + ry) % root)
            if table[left][right] != expected:
                return False
    return True

for record in accepted_records:
    proposal_path = Path(sys.argv[2]).parent / record["path"]
    proposal = json.loads(proposal_path.read_text())
    validated = validate_quantum_tanner_proposal(proposal, max_group_order=32)
    if record.get("fingerprint") != validated.fingerprint:
        fail(f"accepted proposal fingerprint mismatch for {proposal_path}")
    if not is_known_toric_template(proposal):
        non_toric += 1
if non_toric != 1:
    fail(f"non_toric structural accepted proposals is {non_toric}")

run_status = json.loads((run_root / "run_status.json").read_text())
if run_status.get("status") != "finalized":
    fail(f"run status is {run_status.get('status')!r}")

surface = json.loads((run_root / "surface-copy-comparison.json").read_text())
if surface.get("status") != "ok":
    fail(f"surface copy status is {surface.get('status')!r}")

feedback = json.loads((run_root / "quantum-tanner-ai-feedback.json").read_text())
if feedback.get("counts", {}).get("p001_ler_rows") != 1:
    fail("feedback does not contain exactly one p=0.001 LER row")
if feedback.get("counts", {}).get("rejected_proposals") != 1:
    fail("feedback rejected proposal count mismatch")

for name in ("surface-copy-comparison.html", "quantum-tanner-ai-feedback.html"):
    if not (run_root / name).is_file():
        fail(f"missing {name}")

print("PASS quantum_tanner_ai_proposal_smoke")
print("proposal_accepted=1")
print("proposal_rejected=1")
print("non_toric_candidates=1")
print("p=0.001")
print("surface_copy_status=ok")
print("feedback_status=ok")
print(f"run_root={run_root}")
print(f"surface_copy_json={run_root / 'surface-copy-comparison.json'}")
print(f"surface_copy_html={run_root / 'surface-copy-comparison.html'}")
print(f"feedback_json={run_root / 'quantum-tanner-ai-feedback.json'}")
print(f"feedback_html={run_root / 'quantum-tanner-ai-feedback.html'}")
PY
}

run_toric_only_negative_control() {
  ingest_toric_only_response
  mkdir -p "$WORKTREE_AI_BATCH_ROOT"
  cp -R "$AI_BATCH_ROOT/." "$WORKTREE_AI_BATCH_ROOT/"
  python3 - "$INGESTED_ROOT/summary.json" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text())
accepted = summary.get("accepted")
rejected_records = summary.get("rejected_records", [])
if accepted != 0:
    raise SystemExit(f"expected accepted == 0, got {accepted!r}")
if not rejected_records:
    raise SystemExit("expected at least one rejected record")
error_kind = rejected_records[0].get("error_kind")
if error_kind != "KnownToricTemplateDuplicate":
    raise SystemExit(f"expected KnownToricTemplateDuplicate, got {error_kind!r}")
print("KnownToricTemplateDuplicate")
raise SystemExit(1)
PY
}

run_default_flow() {
  resolve_backend_executables
  prepare_ai_batch
  ingest_mixed_response
  reset_campaign_search_space
  materialize_accepted_proposals
  import_proposal_instances
  prune_search_space_to_proposals
  write_witnesses_and_patch_search_space
  complete_observables
  run_autoresearch_smoke
  write_comparison_and_feedback
  verify_default_smoke
}

prepare_work_root

if [[ "$CHECK_TORIC_ONLY_RESPONSE" -eq 1 ]]; then
  run_toric_only_negative_control
else
  run_default_flow
fi
