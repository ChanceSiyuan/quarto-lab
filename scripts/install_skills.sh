#!/usr/bin/env bash
# Install/refresh agent skills as REAL copies (no symlinks) for BOTH consumers:
#   .claude/skills/  — read by Claude Code
#   .agents/skills/  — read natively by Codex CLI (Agent Skills spec)
#
# Remote revisions are explicit in Ion.toml and must match Ion.lock. Ion may
# reuse its cache or fetch those pinned revisions on a fresh machine, but it
# installs them first into an isolated staging project so failure cannot damage
# the last working consumer copies.
set -euo pipefail
shopt -s nullglob

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
cd "$repo_root"

# Prefer the caller's PATH. Fall back to Ion's conventional user install path
# without changing HOME or hiding a caller-selected Ion executable.
if command -v ion >/dev/null 2>&1; then
  ion_bin=$(command -v ion)
elif [ -x "$HOME/.local/bin/ion" ]; then
  ion_bin="$HOME/.local/bin/ion"
else
  echo "error: 'ion' not found. Install Ion before refreshing agent skills." >&2
  exit 1
fi
if [ -x "$repo_root/.venv/bin/python" ]; then
  python_bin="$repo_root/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python_bin=$(command -v python3)
else
  echo "error: Python 3.11+ is required to verify Ion.toml against Ion.lock." >&2
  exit 1
fi
if ! "$python_bin" -c 'import tomllib' >/dev/null 2>&1; then
  echo "error: Python 3.11+ with tomllib is required for skill pin verification." >&2
  exit 1
fi

work_root="$repo_root/work"
install_lock="$work_root/skills-install.lock"
mkdir -p "$work_root"
if ! mkdir "$install_lock" 2>/dev/null; then
  echo "error: another skill installation appears to be running: $install_lock" >&2
  exit 1
fi

stage_root=$(mktemp -d "$work_root/skills-install.XXXXXX")
lock_candidate="$repo_root/.Ion.lock.install.$$"
transaction_active=false
cleanup() {
  status=$?
  trap - EXIT INT TERM
  if "$transaction_active" && ! rollback_transaction; then
    echo "error: automatic skill rollback failed; recovery files remain in $stage_root" >&2
    return 1
  fi
  rm -rf "$stage_root"
  rm -f "$lock_candidate"
  rmdir "$install_lock" 2>/dev/null || true
  return "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

verify_skill_pins() {
  "$python_bin" - "$1" "$2" <<'PY'
from __future__ import annotations

from pathlib import Path
import re
import sys
import tomllib


manifest_path = Path(sys.argv[1])
lock_path = Path(sys.argv[2])

with manifest_path.open("rb") as handle:
    manifest = tomllib.load(handle)
with lock_path.open("rb") as handle:
    lock = tomllib.load(handle)

skills = manifest.get("skills", {})
locked_entries = lock.get("skill", [])
locked: dict[str, dict[str, object]] = {}
for entry in locked_entries:
    name = entry.get("name")
    if not isinstance(name, str) or name in locked:
        raise SystemExit(f"error: duplicate or invalid skill entry in Ion.lock: {name!r}")
    locked[name] = entry

manifest_names = set(skills)
lock_names = set(locked)
if manifest_names != lock_names:
    missing = ", ".join(sorted(manifest_names - lock_names)) or "(none)"
    extra = ", ".join(sorted(lock_names - manifest_names)) or "(none)"
    raise SystemExit(
        "error: Ion.toml/Ion.lock skill sets differ "
        f"(missing from lock: {missing}; extra in lock: {extra})"
    )

for name, spec in skills.items():
    entry = locked[name]
    if not isinstance(spec, dict):
        raise SystemExit(
            f"error: skill {name!r} must use a full Ion.toml entry with an explicit type or rev"
        )

    if spec.get("type") == "local":
        if entry.get("kind") != "local":
            raise SystemExit(f"error: local skill {name!r} is not local in Ion.lock")
        local_path = spec.get("path")
        if local_path is not None:
            skill_file = manifest_path.parent / str(local_path) / "SKILL.md"
            if not skill_file.is_file():
                raise SystemExit(
                    f"error: local skill {name!r} is missing {skill_file}"
                )
        continue

    source = spec.get("source")
    revision = spec.get("rev")
    if not isinstance(source, str):
        raise SystemExit(f"error: remote skill {name!r} has no source")
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise SystemExit(
            f"error: remote skill {name!r} needs an explicit 40-character rev in Ion.toml"
        )

    parts = source.split("/")
    if len(parts) < 3:
        raise SystemExit(
            f"error: remote skill {name!r} must use owner/repository/path syntax"
        )
    expected_source = f"https://github.com/{parts[0]}/{parts[1]}.git"
    expected_path = "/".join(parts[2:])
    if entry.get("kind") != "git":
        raise SystemExit(f"error: remote skill {name!r} is not git-locked")
    if entry.get("source") != expected_source or entry.get("path") != expected_path:
        raise SystemExit(
            f"error: remote skill {name!r} source/path differs between Ion.toml and Ion.lock"
        )
    if entry.get("commit") != revision:
        raise SystemExit(
            f"error: remote skill {name!r} rev differs from its Ion.lock commit"
        )
PY
}

# Complete every manifest/lock pin check before touching either consumer.
if ! verify_skill_pins "$repo_root/Ion.toml" "$repo_root/Ion.lock"
then
  echo "error: skill pin preflight failed; no consumer files were changed." >&2
  exit 1
fi

stage_project="$stage_root/project"
mkdir -p "$stage_project"
cp "$repo_root/Ion.toml" "$stage_project/Ion.toml"
cp "$repo_root/Ion.lock" "$stage_project/Ion.lock"
ln -s "$repo_root/skills" "$stage_project/skills"

set +e
(
  cd "$stage_project"
  "$ion_bin" --json add --allow-warnings
)
ion_status=$?
set -e
if [ "$ion_status" -ne 0 ]; then
  echo "error: staged Ion installation failed; existing consumers were preserved." >&2
  exit "$ion_status"
fi

if ! verify_skill_pins "$repo_root/Ion.toml" "$stage_project/Ion.lock"
then
  echo "error: post-install pin verification failed; existing consumers were preserved." >&2
  exit 1
fi

if ! "$python_bin" - "$repo_root/Ion.toml" \
  "$stage_project/.agents/skills" "$stage_project/.claude/skills" <<'PY'
from pathlib import Path
import sys
import tomllib


with Path(sys.argv[1]).open("rb") as handle:
    expected = set(tomllib.load(handle)["skills"])

for raw_directory in sys.argv[2:]:
    directory = Path(raw_directory)
    actual = {entry.name for entry in directory.iterdir()} if directory.is_dir() else set()
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "(none)"
        extra = ", ".join(sorted(actual - expected)) or "(none)"
        raise SystemExit(
            f"error: staged consumer {directory} differs from Ion.toml "
            f"(missing: {missing}; extra: {extra})"
        )
PY
then
  echo "error: staged Ion output was incomplete; existing consumers were preserved." >&2
  exit 1
fi

prepared_agents="$stage_root/prepared-agents"
prepared_claude="$stage_root/prepared-claude"
mkdir -p "$prepared_agents" "$prepared_claude"
for source_skill in "$stage_project/.agents/skills/"*; do
  name=$(basename "$source_skill")
  real_skill=$(readlink -f "$source_skill") || {
    echo "error: staged skill link is broken: $name" >&2
    exit 1
  }
  if [ ! -d "$real_skill" ]; then
    echo "error: staged skill is not a directory: $name" >&2
    exit 1
  fi
  if [ ! -f "$real_skill/SKILL.md" ]; then
    echo "error: staged skill has no SKILL.md: $name" >&2
    exit 1
  fi
  if find "$real_skill" -mindepth 1 -type l -print -quit | grep -q .; then
    echo "error: staged skill tree contains a symlink: $name" >&2
    exit 1
  fi
  if find "$real_skill" -mindepth 1 ! -type d ! -type f -print -quit | grep -q .; then
    echo "error: staged skill tree contains a special file: $name" >&2
    exit 1
  fi
  cp -a "$real_skill" "$prepared_agents/$name"
  cp -a "$real_skill" "$prepared_claude/$name"
done
cp "$stage_project/Ion.lock" "$lock_candidate"

for consumer_parent in "$repo_root/.agents" "$repo_root/.claude"; do
  if [ -L "$consumer_parent" ] || {
    [ -e "$consumer_parent" ] && [ ! -d "$consumer_parent" ]
  }; then
    echo "error: consumer parent must be a real repository directory: $consumer_parent" >&2
    exit 1
  fi
done
mkdir -p "$repo_root/.agents" "$repo_root/.claude"
agents_target="$repo_root/.agents/skills"
claude_target="$repo_root/.claude/skills"
agents_backup="$stage_root/previous-agents"
claude_backup="$stage_root/previous-claude"
lock_backup="$stage_root/previous-Ion.lock"

rollback_transaction() {
  rollback_failed=false
  if [ -e "$agents_backup" ] || [ -L "$agents_backup" ]; then
    rm -rf "$agents_target" || rollback_failed=true
    mv "$agents_backup" "$agents_target" || rollback_failed=true
  elif [ ! -e "$prepared_agents" ]; then
    rm -rf "$agents_target" || rollback_failed=true
  fi
  if [ -e "$claude_backup" ] || [ -L "$claude_backup" ]; then
    rm -rf "$claude_target" || rollback_failed=true
    mv "$claude_backup" "$claude_target" || rollback_failed=true
  elif [ ! -e "$prepared_claude" ]; then
    rm -rf "$claude_target" || rollback_failed=true
  fi
  if [ -f "$lock_backup" ]; then
    mv -f "$lock_backup" "$repo_root/Ion.lock" || rollback_failed=true
  fi
  if "$rollback_failed"; then
    return 1
  fi
  transaction_active=false
}

cp "$repo_root/Ion.lock" "$lock_backup"
transaction_active=true
if [ -e "$agents_target" ] || [ -L "$agents_target" ]; then
  mv "$agents_target" "$agents_backup"
fi
if [ -e "$claude_target" ] || [ -L "$claude_target" ]; then
  if ! mv "$claude_target" "$claude_backup"; then
    echo "error: could not stage existing consumers for replacement; rolling back." >&2
    exit 1
  fi
fi

if ! mv "$prepared_agents" "$agents_target"; then
  echo "error: could not install .agents skills; rolling back." >&2
  exit 1
fi
if ! mv "$prepared_claude" "$claude_target"; then
  echo "error: could not install .claude skills; rolling back." >&2
  exit 1
fi
if ! mv -f "$lock_candidate" "$repo_root/Ion.lock"; then
  echo "error: could not atomically update Ion.lock; rolling back." >&2
  exit 1
fi
transaction_active=false

echo "done: $(find "$claude_target" -mindepth 1 -maxdepth 1 -type d | wc -l)" \
  "skills in .claude/skills," \
  "$(find "$agents_target" -mindepth 1 -maxdepth 1 -type d | wc -l)" \
  "in .agents/skills (no symlinks)"
