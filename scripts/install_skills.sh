#!/usr/bin/env bash
# Install/refresh agent skills as REAL copies (no symlinks) in .claude/skills/.
#
# ion's native layout is symlink-based: .claude/skills -> .agents/skills ->
# skills/<name> or ~/.local/share/ion/repos/<hash>/... . The cache links
# dangle on any machine that never ran ion (e.g. the other side of the DGX
# sync), so this script lets ion resolve/fetch everything, then dereferences
# the links into real directories and drops the intermediate .agents layer.
#
# Run after editing a local skill in skills/, after `ion update`, or after
# changing Ion.toml.
set -euo pipefail
shopt -s nullglob
cd "$(dirname "$0")/.."

# ion installs to ~/.local/bin, which login shells may not have on PATH.
export PATH="$HOME/.local/bin:$PATH"
if ! command -v ion >/dev/null 2>&1; then
  echo "error: 'ion' not found. Run this script on a machine that has it —" >&2
  echo ".claude/skills/ holds real copies, so machines that only CONSUME" >&2
  echo "skills (e.g. the DGX) never need ion." >&2
  exit 1
fi

# Keep ion's output visible: it reports success but WARNS here when a local
# skill path in Ion.toml is missing — silencing it hides stale installs.
ion --json add --allow-warnings

mkdir -p .claude/skills
manifest_names=()
for src in .agents/skills/*; do
  name=$(basename "$src")
  manifest_names+=("$name")
  real=$(readlink -f "$src") || { echo "skip broken link: $name" >&2; continue; }
  rm -rf ".claude/skills/$name"
  cp -r "$real" ".claude/skills/$name"
  echo "installed: $name"
done

if [ "${#manifest_names[@]}" -eq 0 ]; then
  echo "error: ion produced no skills in .agents/skills — refusing to prune" >&2
  exit 1
fi

# Prune skills that were removed from Ion.toml since the last run.
for dir in .claude/skills/*/; do
  name=$(basename "$dir")
  keep=false
  for m in "${manifest_names[@]}"; do
    [ "$m" = "$name" ] && keep=true && break
  done
  "$keep" || { rm -rf "$dir"; echo "pruned: $name"; }
done

# Drop only ion's symlink layer; leave any unrelated .agents/ content alone.
rm -rf .agents/skills
rmdir .agents 2>/dev/null || true
find .claude/skills -maxdepth 1 -type l -delete
echo "done: $(ls .claude/skills | wc -l) skills in .claude/skills (no symlinks)"
