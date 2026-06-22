# Calling codex, opencode & agy headless (reference for Claude Code)

How to invoke the three local coding CLIs non-interactively from a Bash call, and the rules that stop you
wasting a call. All are the `claude -p` equivalent. All facts below are verified on this box.

## Pick one
(currently only support codex)
| | `codex exec` | `opencode run` | `agy -p` |
| --- | --- | --- | --- |
| Model | `gpt-5.5` @ `xhigh` | `deepseek-v4-pro` (`-m deepseek/deepseek-v4-flash` = fast) | `Gemini 3.5 Flash (High)` — **Gemini only** |
| Auth | ChatGPT sub, `~/.codex/auth.json` — no env key | needs `DEEPSEEK_API_KEY` in env | Google OAuth, `~/.gemini/` — no env key |
| Concurrency | **parallel OK** | **parallel OK** (separate `run` procs) | **parallel OK** |
| Files | read + edit via sandbox | read/grep/edit, native | read/edit, native (no sandbox needed) |
| Structured out | `--output-schema` (JSON) | `--format json` | **none** — ask for JSON in prompt, parse loosely |
| Best for | heavy reasoning, `review`, structured output | DeepSeek work, parallel fan-out | easiest file read/write, parallel, Gemini |

## Invoke

```bash
# ask / explain (let them read files themselves — don't paste file contents)
codex exec "explain ./src and read ./config.toml" < /dev/null
opencode run "read ./README.md and list the headings"
agy -p "read ./config.toml and summarize it"

# edit files
codex exec --sandbox workspace-write "fix the bug in ./app.py and save" < /dev/null
opencode run --dangerously-skip-permissions "add tests for utils.py"
agy --dangerously-skip-permissions -p "add tests for utils.py"

# pick model / effort
codex exec -c model_reasoning_effort="high" "..." < /dev/null
opencode run -m deepseek/deepseek-v4-flash "..."          # (opencode effort flags hang — don't use)
agy --model "Gemini 3.5 Flash (Low|Medium|High)" -p "..." # or "Gemini 3.1 Pro (Low|High)"; effort is in the name

# structured JSON output (automation)
codex exec --output-schema schema.json -o out.json "extract X as JSON" < /dev/null
opencode run --format json "..."                          # raw JSON events on stdout
# agy: no JSON flag — say "respond with only JSON: {...}" in the prompt and parse loosely

# continue a session
codex exec resume --last "now add error handling" < /dev/null   # or: resume <id>
opencode run -c "now add tests"                                 # or: -s <id>
agy -c "now add tests"                                          # or: --conversation <id>

# big / multi-line prompt: build a file; pass to codex/agy as arg, to opencode via STDIN
{ echo "Critique this:"; echo; cat plan.md; } > /tmp/p.txt
codex exec "$(cat /tmp/p.txt)" -o /tmp/out.md < /dev/null
cat /tmp/p.txt | opencode run > /tmp/out.md                # NOT a giant "$(...)" arg

# parallel fan-out — all three parallelize via separate processes (verified 5-way for opencode)
codex exec "task A" < /dev/null > a.md &
opencode run "task B" > b.md &
agy -p "task C" > c.md &
wait
# cap concurrency with a job pool when fanning out many:
printf '%s\n' "${prompts[@]}" | xargs -P 5 -I{} sh -c 'opencode run "{}" > "out-$$.md"'

# codex built-in repo review
codex exec review < /dev/null
```

## Hard rules (break one = wasted / hung call)

**codex**
- Always append `< /dev/null` (else it waits on stdin).
- Use `-o <file>` to capture the final answer; raw stdout is noisy (header + `tokens used`).
- `--skip-git-repo-check` when not in a git repo. `--sandbox workspace-write` to let it edit files.

**opencode**
- **Parallel OK** — separate `opencode run` processes run concurrently (verified 5-way, true parallelism, no cross-talk). Cap fan-out with `xargs -P` to avoid rate limits. (The only thing that fails is `serve`+`--attach`: attached runs return empty output — don't use that route for concurrency.)
- **Big prompts via stdin** (`cat f | opencode run`), never a large `"$(cat f)"` arg — the arg form hangs (~19 KB → 300 s timeout).
- **Never `-f/--file`** — it's an array flag that eats the trailing message. Tell it to read the path instead.
- **Never `--variant` / `--thinking`** — they hang on DeepSeek V4 (even trivial prompts). For effort-tuned work use codex or agy.
- `--dangerously-skip-permissions` required to write in headless. v4-pro is slow on big tasks (minutes) — background it with `timeout` and read the output file.

**agy** (easiest; few rules)
- **Gemini only.** Default is `Gemini 3.5 Flash (High)`. If you switch model, stay within Gemini (`Gemini 3.5 Flash (Low|Medium|High)` / `Gemini 3.1 Pro (Low|High)`) — never the Claude/GPT-OSS options `agy models` also lists. Effort is the parenthetical in the name, not a separate flag.
- Reads/writes files natively, no sandbox flag needed. Add `--dangerously-skip-permissions` to write without prompts.
- No JSON/structured-output flag — request JSON in the prompt if you need to parse it.
- `--print-timeout` defaults to 5m; raise it for long tasks.

## Flags

**codex** (`codex exec --help`): `-m <model>` · `-c model_reasoning_effort="low|medium|high|xhigh"` (effort) · `-s/--sandbox read-only|workspace-write|danger-full-access` · `-o <file>` · `--output-schema <file>` · `--json` · `-C/--cd <dir>` · `--add-dir <dir>` · `-p/--profile <name>` · `--skip-git-repo-check` · `exec resume --last|<id>` · `exec review` · `--dangerously-bypass-approvals-and-sandbox` (only if sandbox breaks).

**opencode** (`opencode run --help`): `-m deepseek/deepseek-v4-pro|...-flash` · `--format json` · `--dangerously-skip-permissions` · `-c/--continue` · `-s/--session <id>` · redirect stdout `> file` (no `-o`; one `> build · model` header line). Avoid `--variant`, `--thinking`, `-f`. Note `-p` here = `--password`, not print.

**agy** (`agy --help`): `-p/--print` (headless) · `--model "Gemini 3.5 Flash (High)"` (Gemini only; effort in the name) · `--dangerously-skip-permissions` · `-c/--continue` · `--conversation <id>` · `--add-dir <dir>` · `--sandbox` (opt-in terminal restrictions; OFF by default) · `--print-timeout 5m`. No JSON/structured-output flag. `agy models` lists choices.

## Setup facts

- **Auth:** codex = subscription token (no env). agy = Google OAuth in `~/.gemini/antigravity-cli/` (no env). opencode needs `DEEPSEEK_API_KEY` — it lives in `~/.bashrc`, which non-interactive shells skip, so a Bash call may not see it. If opencode auth-fails, export it first (e.g. read it from `~/.bashrc`).
- **agy default model:** `Gemini 3.5 Flash (High)`, set in `~/.gemini/antigravity-cli/settings.json` (`"model"` key takes the display name). Gemini-only by preference.
- **codex sandbox:** works (reads in default `read-only`, writes with `--sandbox workspace-write`). It runs commands in a bubblewrap sandbox; the Ubuntu AppArmor block was disabled persistently via `/etc/sysctl.d/99-codex-userns.conf` (`kernel.apparmor_restrict_unprivileged_userns=0`). If it regresses (warning: "needs access to create user namespaces"), re-apply that sysctl or fall back to `--dangerously-bypass-approvals-and-sandbox`. agy's `--sandbox` is opt-in and off by default, so agy has no such issue.
- **MCP:** all three support it; headless runs use whatever is configured. codex: `codex mcp ...` (`~/.codex/config.toml`). opencode: `mcp` block in `~/.config/opencode/opencode.json`. agy: `~/.gemini/config/mcp_config.json` (`/mcp` in TUI).
- **Config:** codex `~/.codex/config.toml` · opencode `~/.config/opencode/opencode.json` · agy `~/.gemini/antigravity-cli/settings.json`.
