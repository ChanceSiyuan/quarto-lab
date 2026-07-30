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

Research Loop asks two different questions about every candidate:

| Score | Question |
|---|---|
| **Research Value (V)** | Is this problem important, novel, plausible, generalizable, and worth its cost? |
| **Autoresearch Fit (A)** | Can progress be measured through a bounded, reproducible, hard-to-game search loop? |
| **Combined Priority (S)** | Is the problem strong on both dimensions? |

V and A are weighted scores from 0–100. S is their harmonic mean, so an
important but untestable problem—or an easy but low-value problem—does not rank
high by accident.

The assessment produces one advisory verdict:

- `DO_NOW` — high research value and strong autoresearch fit;
- `REFRAME` — valuable, but needs a more bounded formulation;
- `NOT_AUTORESEARCH` — valuable, but unsuitable for this research loop; or
- `DEFER` — current evidence does not justify priority.

Assessments bind the problem description, the trusted knowledge resolver result,
and a frozen evidence snapshot. Completed runs are immutable and keep their
scores, rationales, confidence, provenance, and evidence references together.
Missing evidence stays unknown rather than becoming a fake zero.

The method is advisory, not a calibrated scientific or investment forecast. It
does not treat citations as proof of novelty, external evidence as trusted
knowledge, or modeled technical success as a completed benchmark.

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
