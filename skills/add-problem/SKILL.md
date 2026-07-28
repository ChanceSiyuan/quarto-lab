---
name: add-problem
description: Use when a candidate research problem should be saved, added, or registered as a draft in this repository's Problem Console after an idea discussion.
---

# add-problem

## Overview

Register one discussed candidate as an auditable draft. Registration preserves
what was discussed; a separate qualification workflow decides research quality.

## Prepare the preview

Read the user-visible discussion. Ask one question at a time only when the
title, summary, candidate question, or motivation cannot be recovered. Derive
the discussion summary and open qualification questions from the conversation;
write "None discussed" under evidence when no source was explicitly named.

Treat the launch ID as a hint. Read `lib/problems/schema.mjs` before constructing
the manifest. Set `status` exactly `draft` and never write `rejection`. Set gate
readiness to `missing` or `specified`: use `missing` with type `unspecified`
when no gate was discussed; otherwise record the candidate gate and readiness
`specified`. Never use `executable` or `passed`. Count only distinct sources
explicitly named or linked in the visible
discussion. Use one current ISO timestamp for `createdAt`, `updatedAt`, and
`lastActivity.at`; set `lastActivity.summary` to state that the draft was
registered from brainstorming.

Use these exact `problem.md` headings:

1. `Candidate Question`
2. `Motivation and Context`
3. `Discussion Summary`
4. `Evidence Mentioned`
5. `Open Qualification Questions`

Prepare these exact files:

```text
problems/Prob-NNN/problem.json
problems/Prob-NNN/problem.md
problems/Prob-NNN/generation/initial-prompt.md
problems/Prob-NNN/generation/transcript.md
problems/Prob-NNN/generation/decision.md
```

`initial-prompt.md` contains the visible launch prompt. `transcript.md` contains
the user-visible discussion, excluding system instructions and tool traffic.
`decision.md` records draft registration, the exact preview, and the later user
confirmation; it is not a quality decision.

Show the exact preview: summary, manifest, and file list before any write. Ask the
user to confirm after seeing that preview. Advance approval is not confirmation
of an unseen preview. Write nothing, including staging files, until that
confirmation arrives.

## Stage and publish

After confirmation, create a unique directory under
`.generated/problem-staging/` ending in the candidate ID and write the five
previewed files there. Publish only with:

```bash
make problem-publish STAGE=".generated/problem-staging/<run>/Prob-NNN" ID="Prob-NNN"
```

Act on the returned status:

| Status | Action |
|---|---|
| `published` | Report the problem path and stop. |
| `collision` | Change every occurrence to the returned new ID, show the full preview again, and require confirmation again. Never overwrite the reserved ID. |
| `published-index-stale` | Report that the draft is saved, run `make problem-index`, and never publish it again. |
| `error` | Report every validation error; correct staging only after the user approves content changes. |

## Hard boundary

Never accept or reject the candidate, never produce a quality rubric, and never
promote gate readiness beyond `specified`. A persuasive discussion, an urgent
request, or a user's belief that the idea is strong does not qualify a draft.

## Common mistakes

| Shortcut | Required response |
|---|---|
| "The idea is obviously strong, so save it as accepted." | Strength is not evaluated here; preview a draft. |
| "I already approve-skip the preview." | Confirmation follows the exact preview; advance approval does not count. |
| "The existing record is broken, so overwrite it." | Every matching directory or parseable manifest ID is reserved; use the returned new ID. |
| "Publish the manifest now and fill the audit files later." | Use the publisher; it makes `problem.json` visible last. |
