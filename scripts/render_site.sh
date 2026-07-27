#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$repo_root/.venv/bin/python" ]]; then
  export PATH="$repo_root/.venv/bin:$PATH"
fi

cd "$repo_root"
quarto render "$@"
