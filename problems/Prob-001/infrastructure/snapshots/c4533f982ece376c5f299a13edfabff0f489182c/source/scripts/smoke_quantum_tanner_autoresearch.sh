#!/usr/bin/env bash
set -euo pipefail

RUN_ID="qt-smoke"
WORK_ROOT=""
CHECK_BAD_OBSERVABLES=0
KEEP_EXISTING_WORK_ROOT=0

usage() {
  cat <<'EOF'
Usage:
  scripts/smoke_quantum_tanner_autoresearch.sh --work-root <path> [--check-bad-observables] [--keep-existing-work-root]

Environment:
  QEC_CODE_BIN   qec-code executable path or command name (default: qec-code)
  RSINTER_BIN    rsinter executable path or command name (default: rsinter)
EOF
}

fail() {
  echo "FAIL quantum_tanner_autoresearch_smoke" >&2
  echo "error: $*" >&2
  exit 1
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
    --check-bad-observables)
      CHECK_BAD_OBSERVABLES=1
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
QEC_CODE_BIN_RESOLVED="$(resolve_executable "${QEC_CODE_BIN:-qec-code}" "qec-code")"
RSINTER_BIN_RESOLVED="$(resolve_executable "${RSINTER_BIN:-rsinter}" "rsinter")"
export PATH="$(dirname "$RSINTER_BIN_RESOLVED"):$(dirname "$QEC_CODE_BIN_RESOLVED"):$PATH"

prepare_work_root() {
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
}

ensure_distance_ladder() {
  if command -v autoqec-distance-ladder >/dev/null 2>&1; then
    return
  fi
  if [[ ! -x "$CHECKOUT/target/debug/autoqec-distance-ladder" ]]; then
    cargo --manifest-path "$CHECKOUT/Cargo.toml" build --bin autoqec-distance-ladder
  fi
  export PATH="$CHECKOUT/target/debug:$PATH"
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

generate_candidates() {
  run_cli generate-quantum-tanner-candidates \
    --root "$CHECKOUT" \
    --config "$CHECKOUT/campaigns/examples/quantum-tanner-autoresearch/generator.json" \
    --qec-code-bin "$QEC_CODE_BIN_RESOLVED" \
    --force
}

attach_witnesses() {
  run_cli attach-quantum-tanner-witnesses \
    --root "$CHECKOUT" \
    --campaign quantum-tanner-autoresearch \
    --fixture-catalog campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json \
    --witness-dir campaigns/examples/quantum-tanner-autoresearch/witnesses \
    --basis x \
    --qec-code-bin "$QEC_CODE_BIN_RESOLVED" \
    --force \
    --require-all
}

run_default_smoke() {
  generate_candidates
  attach_witnesses
  commit_temp_checkout "prepare quantum Tanner smoke inputs"
  run_cli validate --root "$CHECKOUT"
  run_cli run \
    --root "$CHECKOUT" \
    --campaign quantum-tanner-autoresearch \
    --wall-clock 90s \
    --run-id "$RUN_ID" \
    --distance-method random-window-upper-bound \
    --qec-code-bin "$QEC_CODE_BIN_RESOLVED"

  local worktree_root="$CHECKOUT/.worktrees/$RUN_ID"
  local run_root="$worktree_root/results/search/quantum-tanner-autoresearch/$RUN_ID"
  run_cli compare-surface-copy \
    --root "$worktree_root" \
    --run "results/search/quantum-tanner-autoresearch/$RUN_ID" \
    --baseline benchmarks/baselines/rotated-surface-single-logical-p001.json \
    --out "$run_root/surface-copy-comparison.html"

  python3 - "$run_root" <<'PY'
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


run_root = Path(sys.argv[1])


def fail(message: str) -> None:
    print("FAIL quantum_tanner_autoresearch_smoke", file=sys.stderr)
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(name: str) -> dict:
    path = run_root / name
    if not path.is_file():
        fail(f"missing {name}: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        fail(f"{name} must be a JSON object")
    return payload


def fmt_number(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


run_status = load_json("run_status.json")
if run_status.get("status") != "finalized":
    fail(f"run_status status is {run_status.get('status')!r}")
if run_status.get("frontier_size") != 2:
    fail(f"frontier_size is {run_status.get('frontier_size')!r}")

frontier = load_json("frontier.json")
items = frontier.get("items")
if not isinstance(items, list):
    fail("frontier items must be a list")
by_id = {item.get("candidate_id"): item for item in items if isinstance(item, dict)}
expected_ids = ["quantum-tanner-toric-d4", "quantum-tanner-toric-d6"]
if sorted(by_id) != expected_ids:
    fail(f"frontier candidates mismatch: {sorted(by_id)!r}")

for candidate_id in expected_ids:
    item = by_id[candidate_id]
    if item.get("p") != 0.001:
        fail(f"{candidate_id} p is {item.get('p')!r}")
    if item.get("ler") != 0:
        fail(f"{candidate_id} ler is {item.get('ler')!r}")

experiment_log = run_root / "experiment-log.tsv"
if not experiment_log.is_file():
    fail(f"missing experiment-log.tsv: {experiment_log}")
with experiment_log.open(newline="") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
crashes = sum(1 for row in rows if row.get("status") == "crash")
if crashes != 0:
    fail(f"crashes is {crashes}")

if not ((run_root / "report.html").is_file() or (run_root / "run-summary.html").is_file()):
    fail("missing report.html and run-summary.html")

surface = load_json("surface-copy-comparison.json")
if surface.get("status") != "ok":
    fail(f"surface copy status is {surface.get('status')!r}")
counts = surface.get("counts")
if not isinstance(counts, dict):
    fail("surface copy counts must be an object")
expected_counts = {"rows": 2, "accepted": 1, "rejected": 1}
for key, expected in expected_counts.items():
    if counts.get(key) != expected:
        fail(f"surface copy {key} is {counts.get(key)!r}")
if not (run_root / "surface-copy-comparison.html").is_file():
    fail("missing surface-copy-comparison.html")

print("PASS quantum_tanner_autoresearch_smoke")
print(f"run_root={run_root}")
print("frontier_size=2")
print(f"crashes={crashes}")
for candidate_id in expected_ids:
    item = by_id[candidate_id]
    print(
        f"{candidate_id} p={fmt_number(item['p'])} "
        f"ler={fmt_number(item['ler'])}"
    )
print("surface_copy_status=ok")
print("surface_copy_rows=2")
print("surface_copy_accepted=1")
print("surface_copy_rejected=1")
print(f"report_html={run_root / 'report.html'}")
print(f"run_summary_html={run_root / 'run-summary.html'}")
print(f"surface_copy_json={run_root / 'surface-copy-comparison.json'}")
print(f"surface_copy_html={run_root / 'surface-copy-comparison.html'}")
PY
}

prepare_bad_observables_control() {
  python3 - "$CHECKOUT" <<'PY'
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


root = Path(sys.argv[1])
source = (
    root
    / "benchmarks"
    / "distance_ladders"
    / "generated-quantum-tanner"
    / "instances"
    / "quantum-tanner-toric-d4"
)
target = (
    root
    / "campaigns"
    / "examples"
    / "quantum-tanner-autoresearch"
    / "bad-observables"
    / "quantum-tanner-toric-d4"
)
if target.exists():
    shutil.rmtree(target)
shutil.copytree(source, target)

def sparse_rows_to_dense(payload: dict) -> dict:
    num_cols = int(payload["num_cols"])
    dense_rows = []
    for sparse_row in payload["rows"]:
        dense_row = [0] * num_cols
        for column in sparse_row:
            dense_row[int(column)] = 1
        dense_rows.append(dense_row)
    return {
        "format": "dense_binary_matrix",
        "n_rows": len(dense_rows),
        "n_cols": num_cols,
        "data": dense_rows,
    }


for matrix_name in ("hx.json", "hz.json"):
    matrix_path = target / matrix_name
    matrix_payload = json.loads(matrix_path.read_text())
    matrix_path.write_text(
        json.dumps(sparse_rows_to_dense(matrix_payload), indent=2, sort_keys=True) + "\n"
    )

instance_path = target / "instance.json"
instance = json.loads(instance_path.read_text())
instance["artifacts"] = {"hx": "hx.json", "hz": "hz.json", "observables_x": "observables_x.json"}
instance_path.write_text(json.dumps(instance, indent=2, sort_keys=True) + "\n")

observables = {"format": "sparse_rows", "num_cols": 16, "rows": [[0, 2, 3, 4]]}
(target / "observables_x.json").write_text(
    json.dumps(observables, indent=2, sort_keys=True) + "\n"
)

search_space = {
    "campaign_id": "quantum-tanner-autoresearch",
    "mode": "explicit_list",
    "candidate_specs": [
        {
            "candidate_id": "quantum-tanner-toric-d4",
            "code_family": "quantum-tanner-code",
            "instance_path": "campaigns/examples/quantum-tanner-autoresearch/bad-observables/quantum-tanner-toric-d4",
            "upper_bound_payload": {
                "status": "completed",
                "method": "css-upper-bound-witness",
                "bound_type": "upper",
                "upper_bound": 4,
                "basis": "x",
            },
            "provenance": {
                "kind": "negative-control",
                "label": "one-row-x-observables",
            },
        }
    ],
}
search_space_path = (
    root / "campaigns" / "examples" / "quantum-tanner-autoresearch" / "search_space.json"
)
search_space_path.write_text(json.dumps(search_space, indent=2, sort_keys=True) + "\n")
PY
}

run_bad_observables_control() {
  local bad_run_id="${RUN_ID}-bad-observables"
  generate_candidates
  prepare_bad_observables_control
  commit_temp_checkout "prepare bad observables negative control"
  local run_output
  local run_status
  set +e
  run_output="$(run_cli run \
    --root "$CHECKOUT" \
    --campaign quantum-tanner-autoresearch \
    --wall-clock 90s \
    --run-id "$bad_run_id" \
    --distance-method random-window-upper-bound \
    --qec-code-bin "$QEC_CODE_BIN_RESOLVED" 2>&1)"
  run_status=$?
  set -e
  if [[ "$run_status" -ne 0 && -z "$run_output" ]]; then
    fail "negative-control autoresearch failed without output"
  fi

  local run_root="$CHECKOUT/.worktrees/$bad_run_id/results/search/quantum-tanner-autoresearch/$bad_run_id"
  python3 - "$run_root" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


run_root = Path(sys.argv[1])
expected = "explicit X observables define 1 rows, expected k = 2"
manifest_path = (
    run_root
    / "candidates"
    / "quantum-tanner-toric-d4"
    / "evaluations"
    / "quantum-tanner-css-memory-x-rbposd-p001-v1"
    / "rbposd-osd10-v1"
    / "manifest.json"
)
if not manifest_path.is_file():
    print("FAIL quantum_tanner_autoresearch_smoke", file=sys.stderr)
    print(f"error: missing negative-control manifest: {manifest_path}", file=sys.stderr)
    raise SystemExit(1)
manifest = json.loads(manifest_path.read_text())
error = str(manifest.get("error", ""))
if manifest.get("status") != "crash" or expected not in error:
    print("FAIL quantum_tanner_autoresearch_smoke", file=sys.stderr)
    print(f"error: negative control did not reject with expected message: {error}", file=sys.stderr)
    raise SystemExit(1)
print("PASS quantum_tanner_bad_observables_check")
print("negative_control=ok")
print(expected)
print(f"run_root={run_root}")
PY
}

prepare_work_root
ensure_distance_ladder
if [[ "$CHECK_BAD_OBSERVABLES" -eq 1 ]]; then
  run_bad_observables_control
else
  run_default_smoke
fi
