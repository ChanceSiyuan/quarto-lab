#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if (( $# != 0 )); then
  echo "Usage: ./scripts/render_site.sh" >&2
  exit 2
fi

python_bin="python3"
if [[ -x "$repo_root/.venv/bin/python" ]]; then
  python_bin="$repo_root/.venv/bin/python"
fi

cd "$repo_root"
exec "$python_bin" -m scripts.knowledge build
