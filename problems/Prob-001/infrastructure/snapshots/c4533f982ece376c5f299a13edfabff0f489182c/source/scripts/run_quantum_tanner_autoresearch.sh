#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SOURCE_COMMIT="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
BOOTSTRAP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/autoqec-quantum-tanner.XXXXXX")"

cleanup() {
  rm -rf "$BOOTSTRAP_ROOT"
}
trap cleanup EXIT

git -C "$SOURCE_ROOT" archive "$SOURCE_COMMIT" src/autoqec_search \
  | tar -xf - -C "$BOOTSTRAP_ROOT"
(
  cd "$BOOTSTRAP_ROOT"
  PYTHONPATH="$BOOTSTRAP_ROOT/src" \
    python3 -m autoqec_search.quantum_tanner_long_run "$@" \
      --source-root "$SOURCE_ROOT" \
      --source-commit "$SOURCE_COMMIT"
)
