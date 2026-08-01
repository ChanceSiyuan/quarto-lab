# Research Loop

Research Loop is a human-and-agent workspace for building trusted research
knowledge and deciding which research problems deserve attention.

It brings two workflows together:

- a reviewed **knowledge base** that agents can safely answer from; and
- an auditable **problem-assessment method** that separates research value from
  suitability for bounded, automated research.

The local app serves the Problem Console at `/` and the knowledge site at
`/knowledge/`.

## A knowledge base you can trust

Research Loop makes trust a physical boundary, not a prompt instruction.

| Tree | Role | Trust |
|---|---|---|
| `knowledge/` | Human-reviewed research notes | The only trusted answer source and the only content published at `/knowledge/` |
| `drafts/` | Imported notes and agent-written work | Untrusted; never published or used as an answer source |
| `literature/` | Papers and external evidence | Evidence to inspect, not conclusions the project has accepted |

Every knowledge page is reviewed before merge. Curated reading maps define how
pages belong to topics and the order in which they should be read. Validation
checks ownership, links, citations, categories, cycles, path escapes, and safe
Quarto frontmatter.

Before answering a research question, an agent resolves it against the trusted
tree and reads the complete returned bundle:

```bash
make knowledge-resolve QUERY="your research question"
```

The resolver returns `match`, `ambiguous`, or `no-match`. It never silently
falls back to drafts or downloaded literature when trusted knowledge is absent.

## A method for evaluating research problems

Research Loop evaluates each candidate through three separate lenses:

| Measure | Question |
|---|---|
| **Scientific Demand Score** | Does the literature show sustained scientific attention? It combines evidence-weighted influence, momentum, and breadth rather than summing raw citations. |
| **Expected Attributable Net Social Value (EANSV)** | How much expected social value is attributable to doing this research, after subtracting the without-research counterfactual and research cost? |
| **Autoresearch Fit** | Can progress be measured through a bounded, reproducible, hard-to-game loop with useful feedback and practical attempt times? |

These measures keep scientific demand, attributable social value, and execution
fit distinct. A popular topic is not automatically valuable, a broad market
forecast is not credited to one problem, and a valuable problem is not assumed
to be suitable for autonomous search.

Assessments bind the problem description, the trusted knowledge resolver result,
and a frozen evidence snapshot. Completed runs are immutable and keep their
scores, rationales, confidence, provenance, and evidence references together.
Missing evidence stays unknown rather than becoming a fake zero.

The method is advisory, not a calibrated scientific or investment forecast. It
does not treat citations as proof of novelty, external evidence as trusted
knowledge, or scenario assumptions as observed outcomes.

## Quick start

Requirements: Node.js `22.23.1`, Quarto `1.9.38`, and an absolute private-data
directory for local autoresearch isolation.

```bash
AUTORESEARCH_PRIVATE_ROOT=/absolute/private-data make dev
```

Then open the local URL printed by the development server. Use the homepage to
browse problems and `/knowledge/` to browse reviewed knowledge.

## Core commands

| Command | Purpose |
|---|---|
| `make dev` | Start the local Problem Console |
| `make knowledge-check` | Validate the trusted knowledge tree |
| `make knowledge-resolve QUERY="..."` | Resolve a question to its trusted reading bundle |
| `make knowledge-preview` | Preview the knowledge site |
| `make build` | Validate, render, and build the complete app |
| `make test` | Run the full local test suite |

Run `make help` for the complete command list.

## Project structure

| Path | Purpose |
|---|---|
| `knowledge/` | Reviewed, trusted knowledge |
| `problems/` | Research problems, attempts, and local assessment records |
| `drafts/` | Untrusted work in progress |
| `literature/` | External references and evidence |
| `skills/` | Agent workflows for reading, reviewing, and evaluating research |
| `src/` | Problem Console and application code |

## Methodology and workflows

- [Assessment methodology](.research-loop/docs/project/assessment-methodology.md)
- [Running local assessments](.research-loop/docs/project/local-assessments.md)
- [Agent workflow boundaries](.research-loop/docs/project/skills.md)
- [Repository rules](AGENTS.md)

Generated output under `public/knowledge/` is build-owned. Do not edit or commit
it directly.
