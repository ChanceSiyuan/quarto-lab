---
name: generate-issues
description: Use when a user wants actionable research directions proposed from a QMD note, asks what to try next, or requests extension, proof, literature, or coding issues.
---

# Generate Issues

Act as a research collaborator: analyze one source note, connect it to current
and foundational literature, and propose three to five distinct, actionable
research issues.

## Workflow

1. If the note is trusted knowledge, resolve its topic and read the complete
   returned bundle before analysis:

```bash
make knowledge-resolve QUERY="<source note title or research question>"
```

2. Check mathematical consistency, isolate the hard step, and state the
   physical or computational intuition.
3. Search current primary literature and foundational sources. Look for
   cross-field connections, conflicting results, and reproducible baselines;
   cite each source with a one-line reason.
4. Propose three to five non-overlapping issues across useful types:
   extension/generalization, rigorous fix, literature comparison, or a bounded
   coding experiment. Each proposal must have a falsifiable outcome.
5. Present titles, rationale, plan, evidence, and proposed filenames first.
   Obtain explicit approval before writing issue files.
6. After approval, write each proposal as an untrusted QMD under
   `projects/<project>/issues/`. Include `title`, `date`, `categories: [issue]`,
   and `status: Open`, followed by `Problem / Opportunity`, `Proposed Plan`,
   `Relevant Literature`, and `Preliminary Analysis` with real equations or a
   concrete experimental design.

Never place agent-generated issues in `knowledge/`, edit a reading map, or
present a proposal as an established result. Increment issue numbers from the
highest existing issue and show the final diff.
