#!/usr/bin/env bash
# Install/refresh agent skills as REAL copies (no symlinks) for BOTH consumers:
#   .claude/skills/  — read by Claude Code
#   .agents/skills/  — read natively by Codex CLI (Agent Skills spec)
#
# ion's native layout is symlink-based (.agents/skills/<name> -> skills/<name>
# or ~/.local/share/ion/repos/<hash>/...). Cache links dangle on any machine
# that never ran ion (e.g. the other side of the DGX sync), so this script
# lets ion resolve/fetch everything, then dereferences the links into real
# directories in both target dirs. Both dirs are generated artifacts
# (gitignored); local skill sources live in skills/.
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
  echo "the target dirs hold real copies, so machines that only CONSUME" >&2
  echo "skills (e.g. the DGX) never need ion." >&2
  exit 1
fi

# Start from a clean ion layer: if .agents/skills holds real dirs from a
# previous run, ion would skip them and updates would never propagate.
rm -rf .agents/skills

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
  if [ -L "$src" ]; then
    rm "$src"
    cp -r "$real" "$src"
  fi
  echo "installed: $name"
done

if [ "${#manifest_names[@]}" -eq 0 ]; then
  echo "error: ion produced no skills in .agents/skills — refusing to prune" >&2
  exit 1
fi

# Prune skills that were removed from Ion.toml since the last run
# (.agents/skills is rebuilt from scratch above, so only .claude needs this).
for dir in .claude/skills/*/; do
  name=$(basename "$dir")
  keep=false
  for m in "${manifest_names[@]}"; do
    [ "$m" = "$name" ] && keep=true && break
  done
  "$keep" || { rm -rf "$dir"; echo "pruned: $name"; }
done

find .claude/skills .agents/skills -maxdepth 1 -type l -delete
echo "done: $(ls .claude/skills | wc -l) skills in .claude/skills," \
     "$(ls .agents/skills | wc -l) in .agents/skills (no symlinks)"
