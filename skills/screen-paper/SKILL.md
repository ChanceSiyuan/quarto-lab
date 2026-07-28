---
name: screen-paper
description: Use when a user wants a rapid relevance verdict on a paper, asks whether an abstract is worth deeper reading, or requests triage rather than a detailed scientific review.
---

# Screen Paper

Rapidly screen one paper against the user's screening criteria. This is triage,
not a deep review: identify novelty, limitations, feasibility, and relevance
without pretending an abstract supports a full technical judgment.

## Ground the criteria

Use criteria explicitly supplied in the request. If learned Research Loop
context is relevant, resolve it first:

```bash
make knowledge-resolve QUERY="<the user's screening topic>"
```

Read every returned bundle file before applying learned criteria. On no match,
say that the learned knowledge supplies no filter and use only the explicit
criteria. Do not hardcode one lab, hardware platform, or research program.

## Evaluation

1. **Scientific significance:** breakthrough, useful synthesis, or incremental
   variation?
2. **Problem addressed:** what bottleneck or missing capability does the paper
   claim to resolve?
3. **New limitations:** assumptions, overhead, sampling cost, scaling,
   robustness, or implementation constraints.
4. **Exact novelty:** one or two sentences that distinguish the contribution
   from prior work.
5. **Fit:** feasibility under the user's platform, methods, and available
   evidence; note differentiation and saturation only when supported.

Choose exactly one verdict:

- **Pass** — unsuitable, redundant, or outside the criteria;
- **Skim** — useful awareness, weak case for deep work;
- **Deep Dive** — strong fit; name one concrete derivation, experiment, or code
  result to reproduce.

State whether full text or only an abstract was available. Do not modify
repository content. For **Deep Dive**, offer `download-ref` or
`generate-issues` as a separate, user-authorized next action.
