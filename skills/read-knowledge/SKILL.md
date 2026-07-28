---
name: read-knowledge
description: Use before stating a research fact or interpretation that might be covered by the user's learned Quarto knowledge, and whenever the user asks what this repository already knows about a research question.
---

# Consult trusted knowledge

Resolve the user's question through the validated KnowledgeGraph before
answering:

```bash
make knowledge-resolve QUERY="<the user's research question>"
```

This skill is read-only: it does not write, move, promote, or render content.

## Handle the result

- On `match`, read every path in `bundle.orderedFiles`, in order, before
  answering. Treat the ancestor indexes as scope and the content pages as the
  selected learned material.
- On `ambiguous`, present the returned alternatives and ask the user which
  topic they mean. Do not silently choose one.
- On `no-match`, say that the user's learned knowledge has no match. Do not
  substitute model memory while implying that it came from the repository.

## Trust boundary

- Never read `drafts/` as trusted knowledge.
- Never read `conference/` as trusted knowledge.
- Never use literature as a trusted fallback. External papers are Evidence,
  not the user's learned interpretation.
- Never bypass graph validation or reconstruct ranking from filenames.

If the user wants facts beyond a `no-match`, or asks to verify the learned
notes against primary sources, explicitly name that as a separate
`external-research/source-audit` workflow and keep its claims distinct from the
local Reading Bundle.
