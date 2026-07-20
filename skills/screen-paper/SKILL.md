---
name: screen-paper
description: Use when the user wants a rapid relevance screen of a quantum computing paper — "screen this paper", "is this worth reading", "review this abstract", or a pasted arXiv link/abstract with a request for a verdict rather than a deep summary.
---

# screen-paper

Rapidly screen a quantum computing paper against this lab's research focus
and return a three-tier verdict. This is triage, not review: skip
mathematical derivations; judge experimental feasibility, scientific value,
and platform-specific advantage.

<example name="activate good">
User: "Screen arXiv 2506.12345 — worth a deep dive?" → screen-paper fires.
</example>

<example name="activate not-applicable">
User: "Summarize the proof of Theorem 2 in this paper." → screen-paper does NOT fire (that is deep reading, not triage).
</example>

## Research context (the filter)

The team works on the **Neutral Atom (Rydberg) platform**, looking for
differentiated directions in **error mitigation (e.g. virtual distillation)**
and **Hamiltonian evolution**, while avoiding saturated areas and outdated
approaches such as Quantum Annealing.

## Evaluation framework

Work through all four parts, in order, concisely.

### 1. The 4 core criteria (80% rule)

- **Scientific significance** — genuine breakthrough or incremental/repetitive?
- **Main limitations addressed** — what existing problem does it claim to solve?
- **New limitations introduced** — new trade-offs, assumptions, overheads
  (e.g. error correlation, sample cost)?
- **Innovation point** — the exact novelty, in one or two sentences.

### 2. Neutral-atom adaptability & advantage

- **Connectivity & SWAP gates** — does the method need frequent SWAPs?
  (Native advantage here; avoid schemes that lean on continuous SWAP networks.)
- **Feasibility** — realistic on current/near-term neutral-atom systems?
- **Differentiation** — does it exploit unique strengths (all-to-all
  connectivity, coherent atom movement, e.g. scaling virtual distillation to
  M≥3) that superconducting platforms cannot easily match?

### 3. Red ocean vs. blue ocean

- Is the topic homogenized (30+ groups plausibly doing the same thing)?
- Does the paper offer an angle other labs would find hard to replicate?

### 4. Verdict (pick exactly one)

| Verdict | Meaning |
|---|---|
| **Pass** | Not suitable for the platform, or too saturated |
| **Skim** | Good for awareness; not worth deep implementation |
| **Deep Dive** | Highly relevant and differentiating — add 1–2 sentences on the specific experiment or code to reproduce |

## Follow-ups

- Verdict is **Deep Dive** → offer to add the paper to the literature KB
  (`download-ref`) and/or propose concrete directions (`generate-issues`).
- Full text unavailable → screen from the abstract but say so explicitly in
  the verdict.
