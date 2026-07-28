# Add Problem Skill Design

## Goal

Replace the long prompt behind `+ Add problem` with a short hand-off between
two distinct responsibilities:

1. `sci-brain:brainstorm-ideas` discusses and shapes a candidate research
   problem with the user.
2. A new repository-local `add-problem` skill records a user-confirmed
   candidate in the Problem Console as a draft.

The add flow does not qualify the candidate. A later, separately designed
skill will assess research value, novelty, publication threshold, executable
gate quality, and fresh evaluation, then decide whether a draft should become
accepted or rejected.

## Scope

This change:

- shortens the Codex deep-link prompt;
- adds one local skill at `skills/add-problem/SKILL.md`;
- adds a deterministic repository command for validating and safely publishing
  one staged draft;
- records the visible discussion and the user's registration confirmation;
- extends documentation and contract tests.

This change does not:

- add an autonomous backend or unattended job;
- accept, reject, score, or otherwise qualify a research problem;
- change the Problem Console layout or preserved dashboard files;
- publish drafts into the trusted `knowledge/` tree;
- add a second local orchestration skill.

The user still sends the prefilled Codex prompt and explicitly confirms every
write. "Automatic chaining" means that one Codex task continues from the
discussion skill into the local registration skill while retaining the visible
conversation context.

## Considered Approaches

### Skill-only shell instructions

Put the complete publishing procedure in `SKILL.md` and let each agent assemble
shell commands. This minimizes production code, but collision handling,
path validation, cleanup, and manifest-last publication would vary between
runs and would be difficult to test as one contract.

### Skill plus deterministic publisher — selected

Let the skill own the conversation-derived hand-off: shaping the draft, showing
the preview, and obtaining confirmation. Put fragile filesystem mechanics
behind a tested Make target. This follows the repository convention that
executable behavior belongs in `scripts/` and `lib/`, behind a stable command.

### Separate orchestration and registration skills

Add a local entry skill which invokes both the sci-brain discussion skill and a
registration skill. The browser prompt already provides this small amount of
orchestration, so another local skill would add discovery and maintenance cost
without creating a useful independent capability.

## Components

### Short launch prompt

`buildAddProblemPrompt` will produce a compact prompt equivalent to:

```text
Use sci-brain:brainstorm-ideas to help me shape one research problem.

When I decide the candidate is ready to save, follow
skills/add-problem/SKILL.md to add it to this repository as a draft.
Do not assess it as accepted or rejected. Do not write files until I explicitly
confirm.

Candidate ID hint: Prob-NNN
```

The repository path remains in the `path` parameter of the `codex://` deep link
and in the fallback text. The candidate ID is a hint, not a reservation. If the
sci-brain skill is unavailable, Codex reports that dependency instead of
silently recreating a partial copy of it.

The prompt contains no manifest schema, qualification rubric, Markdown schema,
or publishing algorithm. Those rules live with their owning skill or command.

### `add-problem` skill

The local skill triggers when a user wants to register the candidate produced
by a research-idea discussion in this repository's Problem Console. It has four
responsibilities:

1. Check that the visible conversation contains enough material to form a
   title, summary, draft Markdown, and audit record. Ask one question at a time
   for genuinely missing content.
2. Convert the discussion into an exact preview of the manifest and five files
   without writing them.
3. Ask for explicit confirmation of the draft and exact file list.
4. After confirmation, stage the files and invoke the deterministic publisher.

The skill always creates `status: "draft"`. It never writes `rejection`, never
sets gate readiness to `executable` or `passed`, and never presents an
accept/reject rubric.

If no gate was discussed, it records:

```json
{
  "type": "unspecified",
  "readiness": "missing"
}
```

If the discussion explicitly names a candidate gate, the skill records a
concise descriptive type and `readiness: "specified"`. This preserves the
idea without claiming the gate is executable. A future qualification skill
owns that assessment.

`provenance.sourceCount` is the number of distinct external sources explicitly
named or linked in the visible discussion. It is zero when none were named;
the add skill does not infer or search for sources to inflate the count.

### Draft `problem.md`

A newly registered draft uses these exact second-level headings:

1. `Candidate Question`
2. `Motivation and Context`
3. `Discussion Summary`
4. `Evidence Mentioned`
5. `Open Qualification Questions`

These headings intentionally differ from the seven headings required for an
accepted problem. Merely changing `status` cannot turn a draft into a valid
accepted record; the future qualification skill must produce the accepted
document contract deliberately.

### Generation record

Every saved draft has this directory contract:

```text
problems/Prob-NNN/problem.json
problems/Prob-NNN/problem.md
problems/Prob-NNN/generation/initial-prompt.md
problems/Prob-NNN/generation/transcript.md
problems/Prob-NNN/generation/decision.md
```

- `initial-prompt.md` stores the exact short user-visible launch prompt.
- `transcript.md` stores the user-visible discussion from launch through the
  preview. It excludes system instructions, hidden context, tool calls, and
  tool output.
- `decision.md` records the decision to register the candidate as a draft, the
  exact preview shown to the user, and the user's explicit confirmation. It is
  not a research-quality decision.

The manifest uses one timestamp for `createdAt`, `updatedAt`, and
`lastActivity.at`. `lastActivity.summary` states that the draft was registered
from a brainstorming discussion.

### Deterministic publisher

A stable command publishes one already prepared draft:

```bash
make problem-publish STAGE=".generated/problem-staging/<token>/Prob-NNN" ID="Prob-NNN"
```

The implementation lives in a focused library module called by a small script;
the Make target is the agent-facing interface. `STAGE` must resolve inside the
repository's `.generated/problem-staging/` tree, contain no symlink escape, and
end in the same ID supplied by `ID` and stored in `problem.json`.

Before creating a target, the publisher validates:

- the exact five-file contract;
- the existing manifest schema;
- `status` is exactly `draft` and `rejection` is absent;
- gate readiness is only `missing` or `specified`;
- all five draft headings are present outside fenced code blocks;
- each generation record is non-empty;
- every existing `problems/Prob-NNN` directory name and every parseable
  manifest ID is reserved, including invalid records.

After validation, it creates `problems/Prob-NNN` exclusively. It copies
`problem.md` and the three generation records first. It copies the validated
manifest under a temporary name in the target and atomically renames that file
to `problem.json` last. It then rebuilds the generated problem index and checks
that the new draft is present.

The publisher does not choose a different ID silently. On collision, it reports
the next reserved-safe ID. The skill updates every previewed path and manifest
field, then asks the user to confirm the changed file list before retrying.

## Data Flow

1. The user clicks `+ Add problem`, sends the short prompt, and works with
   `sci-brain:brainstorm-ideas` in the new Codex task.
2. When the user says the candidate is ready to save, Codex reads
   `skills/add-problem/SKILL.md`.
3. The skill derives the draft fields and presents the full summary, manifest,
   and exact five-file list in the conversation.
4. If content is missing, the skill asks one question at a time and presents a
   revised preview. It writes nothing during this loop.
5. After explicit confirmation, the skill creates a unique staging directory
   under `.generated/problem-staging/` and writes the five staged files.
6. The skill invokes `make problem-publish` with the staged path and candidate
   ID.
7. The publisher validates and publishes the draft, rebuilds the index, and
   reports the resulting problem path.
8. The skill reports success and leaves qualification for a separate future
   workflow.

There is no accepted/rejected branch. Before registration, the user can simply
decline the preview; no record is written. After registration, the record is a
draft regardless of the discussion's apparent quality.

## Failures and Recovery

### Invalid staged content

Validation fails before the target directory is created. The staged files stay
available for inspection or correction, and the publisher names every failed
contract. The skill never weakens the schema or deletes content to force a
pass.

### Reserved ID or existing target

The publisher fails without writing or overwriting anything and reports a new
reserved-safe ID. Because the ID appears in paths, manifest content, and audit
records, the skill regenerates the preview and obtains another explicit
confirmation.

### Failure before manifest publication

The publisher removes only the incomplete target directory that its own
exclusive create succeeded in making. It never removes a pre-existing path.
The staged source remains intact. Since `problem.json` was not published, the
indexer cannot treat the incomplete target as a problem record.

### Index refresh failure after manifest publication

Once `problem.json` is published, the draft is durable and is not rolled back.
The command reports that the problem was saved but the index is stale. The
skill tells the user to retry only the index build; it does not republish the
draft or allocate a duplicate ID.

### Existing unrelated diagnostics

Damaged records continue to reserve their directory and manifest IDs. Their
diagnostics are reported by the rebuilt index, but they do not block publishing
a new independently valid draft.

## Testing

### Launch prompt tests

- The prompt names `sci-brain:brainstorm-ideas` and
  `skills/add-problem/SKILL.md`.
- It includes the candidate ID hint and explicit confirmation requirement.
- It says the saved record is a draft and forbids accept/reject assessment.
- It stays below a fixed concise size budget.
- It does not contain the manifest field list, accepted/rejected rubric,
  atomic-publication algorithm, or repeated five-path contract.
- The deep link and fallback still carry the same prompt and workspace path.

### Skill contract tests

- `add-problem` joins the canonical local skill list and has valid trigger-only
  frontmatter.
- The body fixes draft-only status, gate readiness limits, exact preview,
  explicit confirmation, staging boundary, and publisher command.
- It prohibits research-quality assessment and accepted/rejected decisions.
- `docs/skills.md`, `AGENTS.md`, and the Make target agree with the skill.

### Publisher unit tests

- Publish a complete draft and rebuild an index containing it.
- Refuse accepted, rejected, executable, passed, or rejection-bearing
  manifests.
- Refuse missing files, empty audit records, incorrect draft headings, invalid
  manifest fields, mismatched IDs, paths outside staging, and symlink escapes.
- Reserve IDs found in damaged directories and invalid but parseable manifests.
- Refuse a collision without changing the existing target.
- Inject a copy failure and prove that only the newly created incomplete target
  is removed while staging remains.
- Inject an index failure after manifest publication and prove the draft remains
  durable and is reported as published with a stale index.

### Repository verification

Run the focused problem and agent suites while iterating, then run
`make test` before completion. Verify the generated deep link and fallback in
the built output. No test workaround may rewrite the preserved dashboard
source or appearance.

## Documentation

Update `docs/skills.md` with the fourth local skill's ownership, trusted inputs,
writes, prohibited behavior, and `make problem-publish` command. Update the
README creation instructions to describe discussion followed by draft
registration, with qualification explicitly deferred.

Add a concise `AGENTS.md` rule directing problem registration through
`add-problem`. The rule names `problems/` as a workflow record, not trusted
knowledge, and preserves the existing trust boundary.

## Success Criteria

- Clicking `+ Add problem` pre-fills a short, readable prompt.
- One Codex task can discuss a candidate with sci-brain and then register it via
  the local skill after explicit confirmation.
- Every new record produced by this flow is a draft and carries no implicit
  qualification result.
- A candidate cannot overwrite an existing or invalid reserved problem.
- A published manifest is never visible before its Markdown and generation
  records are complete.
- The console index contains the new draft after a successful run.
- The local skill, command, documentation, tests, and build agree on the same
  contract.
