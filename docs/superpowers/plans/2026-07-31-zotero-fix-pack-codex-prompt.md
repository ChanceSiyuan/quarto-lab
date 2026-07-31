# Codex execution prompt — Zotero Fix Pack A

You are implementing an approved, fully-specified plan in the repo at /home/chance/quarto-lab (branch: main).

Read these two documents completely before touching any code:

1. `docs/superpowers/specs/2026-07-31-zotero-fix-pack-design.md` — the user-approved design (scope authority)
2. `docs/superpowers/plans/2026-07-31-zotero-fix-pack.md` — the implementation plan (execution authority)

Execute the plan exactly, in order: Section 1 → 2 → 3 → 4 → 5, tasks in numeric order, checkbox steps literally. Rules:

- TDD discipline is mandatory: write each failing test first, RUN it and confirm it fails for the stated reason before writing the implementation. If a test the plan expects to fail passes instead (or fails differently), STOP that task and report — do not adapt the test to pass.
- Before every commit run, from `integrations/zotero`: `npm run verify` (tsc --noEmit + vitest + build). Commit only when green, using the exact git commands and messages in the plan. Never mix content from two sections in one commit.
- The plan's code blocks were written against the current checkout. If an edit anchor no longer matches, re-read the surrounding source and apply the minimal equivalent change — do not redesign, do not expand scope beyond the plan.
- Hard invariants (from the spec): `knowledge/_quarto.yml` is never modified (only `drafts/_quarto.yml` gains `html-math-method: katex`); chat math sizing and chat newline-as-`<br>` behavior are unchanged; the independence contract test at `integrations/zotero/test/codex-service.test.ts:529-598` must keep passing unchanged.
- Do not edit the plan or spec files. Do not push.

When finished (or if blocked), report: per-section status, every commit hash + message, the final `npm run verify` output, and any deviations from the plan with justification.
