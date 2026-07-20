---
name: generate-issues
description: Use when the user wants research directions proposed from a note — "generate issues", "propose research directions", "what's next from this note", "review this result and suggest extensions".
---

# generate-issues

Act as a proactive theory collaborator: analyze a `.qmd` research note,
connect it to the literature via mandatory web search, and propose 3–5
concrete "Research Issues" in the repo's GitHub-style issue format.

<example name="activate good">
User: "Read theory/Magic/stab_rank.qmd and open some research issues." → generate-issues fires.
</example>

<example name="activate not-applicable">
User: "Brainstorm project ideas from the survey KB." → use the sci-brain `ideas` skill (survey-grounded ideation, different pipeline).
</example>

## Procedure

1. **Deep analysis & sanity check.** Read the note thoroughly; check
   mathematical consistency (dimensional analysis, commutation relations);
   identify the core novelty — what is the "hard part", what is the physical
   intuition?
2. **Strategic web search (mandatory).** Find recent (post-2023) and
   foundational literature connected to the note's concepts. Search the
   specific math/physics used, and deliberately look for cross-field
   connections in pure math and CS (e.g. "Clifford group" → symplectic
   algebra, stabilizer rank, Wigner functions).
3. **Propose 3–5 distinct issues**, each one of:
   - **Extension/Generalization** (e.g. qudits d > 2, noise models, other topologies)
   - **Mathematical fix** (rigorous proof for a heuristic argument)
   - **Literature connection** ("this is [Paper X] — compare")
   - **Coding task** (simulate a specific edge case)

Do not just summarize the note — every issue must be actionable.

## Output format

Write each issue as a `.qmd` in the source note's section dir, matching the
structure of existing issue posts there if any. Template:

````markdown
---
title: "[Short, Punchy Title of the Idea]"
date: YYYY-MM-DD
categories: [issue]
status: "Open"
---

::: {.issue-container}
::: {.issue-title-section}
# [🔓 Open]{.status-open} [Title of the Issue] [#[IssueNumber]]{.issue-number}

::: {.issue-meta}
[enhancement]{.label .label-enhancement} [theory]{.label .label-bug}
:::
:::

::: {.post-body}
## Problem / Opportunity
[Why this direction is interesting: generalization? fix? famous-paper connection?]

### Proposed Plan
1.  **Step 1**: [Concrete mathematical or coding step]
2.  **Step 2**: [Next step]
3.  **Step 3**: [Final goal]

### Relevant Literature
* [**Citation Key**]: [Author et al.], "[Title]", [Journal/ArXiv], [Year]. *Reason: why this paper matters here*
:::
:::

::: {.issue-post}
::: {.post-header}
::: {.post-author}
**Claude-Reviewer** commented on [Today's Date]
:::
:::

::: {.post-body}
## Preliminary Analysis
[Sketch of the math or logic, with LaTeX equations.]
:::
:::
````

## Guidelines

- Preliminary analysis must contain real math (a sketch with equations), not
  hand-waving.
- Cited literature must come from the mandatory search step — every
  "Relevant Literature" line needs a one-line reason.
- Issue numbers increment from the highest existing issue in the repo.
