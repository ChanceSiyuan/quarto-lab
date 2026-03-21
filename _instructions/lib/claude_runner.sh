# lib/claude_runner.sh — Shared infrastructure for Claude review/polish scripts
#
# Source this file after setting REPO_ROOT:
#   source "$REPO_ROOT/_instructions/lib/claude_runner.sh"
#
# Required globals (set before sourcing):
#   REPO_ROOT       — repository root directory
#
# Optional globals (set before sourcing to enable features):
#   CALL_LOG        — path to call log file (enables budget tracking)
#   PROGRESS_FILE   — path to progress file (enables progress tracking)
#
# Config globals (set before sourcing to override defaults):
#   MAX_RETRIES, RETRY_WAIT, PAUSE_BETWEEN, MODEL, DRY_RUN, MAX_ITERATIONS
#   OPUS_WEEKLY_CAP, OPUS_BUDGET_PERCENT

# ──────────────────────────── Defaults ────────────────────────────

: "${MAX_RETRIES:=20}"
: "${RETRY_WAIT:=600}"
: "${PAUSE_BETWEEN:=10}"
: "${MODEL:=opus}"
: "${DRY_RUN:=false}"
: "${MAX_ITERATIONS:=30}"
: "${OPUS_WEEKLY_CAP:=50}"
: "${OPUS_BUDGET_PERCENT:=100}"

# Nameref discard target for run_claude when no output capture is needed
_rc_discard=""

# ──────────────────────────── Argument parsing ────────────────────

# Usage: parse_common_args REMAINING_ARRAY "$@"
# Parses --dry-run, --model=*, --cap=*, --max=*, --start-round=*
# and puts everything else into the named array.
parse_common_args() {
  local -n _remaining="$1"
  shift
  _remaining=()
  for arg in "$@"; do
    case "$arg" in
      --dry-run)       DRY_RUN=true ;;
      --model=*)       MODEL="${arg#--model=}" ;;
      --cap=*)         OPUS_WEEKLY_CAP="${arg#--cap=}" ;;
      --max=*)         MAX_ITERATIONS="${arg#--max=}" ;;
      --start-round=*) START_ROUND="${arg#--start-round=}" ;;
      *)               _remaining+=("${arg%/}") ;;   # strip trailing slash
    esac
  done
}

# ──────────────────────────── File discovery ──────────────────────

detect_bib() {
  local dir="$1"
  if [ -f "$dir/refs.bib" ]; then
    echo "$dir/refs.bib"
  elif [ -f "$REPO_ROOT/references.bib" ]; then
    echo "$REPO_ROOT/references.bib"
  else
    echo ""
  fi
}

detect_qmd() {
  local dir="$1"
  if [ -f "$dir/index.qmd" ]; then
    echo "$dir/index.qmd"
  else
    find "$dir" -maxdepth 1 -name '*.qmd' | head -1
  fi
}

# ──────────────────────────── Budget tracking ─────────────────────
# Active only when CALL_LOG is set.

get_week_id() { date +%G-W%V; }

count_weekly_calls() {
  [ -z "${CALL_LOG:-}" ] && echo "0" && return
  local week_id count
  week_id=$(get_week_id)
  count=$(grep -c "^${week_id}" "$CALL_LOG" 2>/dev/null) || true
  echo "${count:-0}"
}

record_call() {
  [ -n "${CALL_LOG:-}" ] && echo "$(get_week_id) $(date +%s) $(date)" >> "$CALL_LOG"
}

check_budget() {
  [ -z "${CALL_LOG:-}" ] && return 0
  local used max_allowed
  used=$(count_weekly_calls)
  max_allowed=$(( OPUS_WEEKLY_CAP * OPUS_BUDGET_PERCENT / 100 ))
  if [ "$used" -ge "$max_allowed" ]; then
    echo "  BUDGET EXHAUSTED: $used / $max_allowed calls this week."
    return 1
  fi
  echo "  Budget: $used / $max_allowed calls used this week."
  return 0
}

# ──────────────────────────── Progress tracking ───────────────────
# Active only when PROGRESS_FILE is set.

is_round_phase_done() {
  [ -z "${PROGRESS_FILE:-}" ] && return 1
  grep -qF "round${1}_phase${2}" "$PROGRESS_FILE" 2>/dev/null
}

mark_round_phase_done() {
  [ -n "${PROGRESS_FILE:-}" ] && echo "round${1}_phase${2}" >> "$PROGRESS_FILE"
}

# ──────────────────────────── Core: run_claude ────────────────────
#
# Usage:
#   run_claude "description" "prompt" "preamble"
#   run_claude "description" "prompt" "preamble" OUTPUT_VAR
#
# Args:
#   $1 — description (for logging)
#   $2 — prompt text
#   $3 — system prompt preamble (pass "" to skip)
#   $4 — variable name to capture output into (optional)
#
# Returns:
#   0 — success
#   1 — non-recoverable error
#   2 — budget exhausted

run_claude() {
  local desc="$1" prompt="$2" preamble="${3:-}"
  local -n _rc_out="${4:-_rc_discard}"
  local attempt=1

  if $DRY_RUN; then
    echo "[DRY-RUN] Would run: $desc"
    echo "[DRY-RUN] Prompt length: ${#prompt} chars"
    return 0
  fi

  while [ $attempt -le $MAX_RETRIES ]; do
    if ! check_budget; then
      return 2
    fi

    echo ""
    echo "--------------------------------------------"
    echo "  STARTING: $desc (attempt $attempt/$MAX_RETRIES)"
    echo "  $(date)"
    echo "--------------------------------------------"

    local sys_args=()
    [ -n "$preamble" ] && sys_args=(--append-system-prompt "$preamble")

    local output
    output=$(claude -p \
      --dangerously-skip-permissions \
      --model "$MODEL" \
      --max-turns 50 \
      "${sys_args[@]}" \
      "$prompt" 2>&1) && {
      record_call
      echo "$output"
      _rc_out="$output"
      echo ""
      echo "  FINISHED: $desc at $(date)"
      echo "--------------------------------------------"
      sleep 5
      return 0
    }

    if echo "$output" | grep -qi "limit\|rate\|quota\|resets\|throttl\|overloaded"; then
      echo "$output"
      echo "  RATE LIMITED — waiting ${RETRY_WAIT}s (attempt $attempt/$MAX_RETRIES)"
      sleep $RETRY_WAIT
      attempt=$((attempt + 1))
    else
      echo "$output"
      echo "  ERROR (non-rate-limit): $desc — skipping."
      echo "--------------------------------------------"
      sleep 5
      return 1
    fi
  done

  echo "  GAVE UP after $MAX_RETRIES retries: $desc"
  return 1
}
