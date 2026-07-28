# Agent-Assisted Research

This context describes how research questions become evidence-backed, human-approved knowledge without treating autonomous agent output as established truth.

The implemented phase is intentionally narrower: it provides the trusted
Quarto knowledge boundary, validation, deterministic Reading Bundles, and safe
static rendering. Research Runs, automated literature acquisition, and
autonomous issue execution remain future architecture.

## Language

**Research Issue**:
A durable question or opportunity that is specific enough to investigate and whose resolution can be evaluated. It owns the history of attempts and only the user can declare its terminal outcome.
_Avoid_: Task, idea, ticket

**Research Run**:
A bounded, immutable record of an agent's attempt to investigate a Research Issue through source discovery, analysis, derivation, or computation.
_Avoid_: Autonomous research project, solver run

**Evidence**:
Source material or a reproducible result that supports, weakens, or contradicts a research claim. Evidence is not itself trusted knowledge.
_Avoid_: Knowledge, truth

**Literature Record**:
Canonical bibliographic metadata plus pinned source material for an external work. A Literature Record is Evidence, not a learned interpretation.
_Avoid_: Reading note, trusted knowledge

**Literature Source Bundle**:
A version-pinned, checksummed Literature Record payload containing the original source archive, safely extracted TeX tree, publisher or arXiv PDF, extracted source figures, and a deterministic manifest. It is never compiled and never converted into a lossy full-text Markdown authority.
_Avoid_: Rendered paper, literature knowledge

**PDF-only Evidence**:
A Literature Source Bundle for which no authoritative TeX source is available. Formula checks against it must be labeled PDF-only; text extracted from the PDF is never promoted to source status.
_Avoid_: Reconstructed LaTeX, source-verified formula

**Research Draft**:
An untrusted synthesis or proposed change produced during a Research Run and awaiting human review.
_Avoid_: Knowledge note, result

**Trusted Knowledge**:
A research claim, derivation, interpretation, or procedure that the user has reviewed and explicitly accepted.
_Avoid_: Agent output, generated note

**Trust Closure**:
The property that Trusted Knowledge links only to other Trusted Knowledge for local research claims and uses explicit citations for external Evidence. It never depends on untrusted workspace content.
_Avoid_: Best-effort link hygiene

**Curated Reading Map**:
The ordered list of direct child topics and pages maintained in a topic's `index.qmd`. It is the single ordering authority for human navigation, generated Quarto sidebars, and agent Reading Bundles.
_Avoid_: Filesystem order, separate agent index

**Reading Bundle**:
The validated, repository-relative sequence of topic indexes and content pages returned to an agent for one query. Its order comes only from Curated Reading Maps.
_Avoid_: Search hits, arbitrary context dump

**Promotion**:
The user's explicit decision to accept material from a Research Draft into Trusted Knowledge.
_Avoid_: Publish, merge automatically

**Human Gate**:
The explicit approval required before Trusted Knowledge is changed, a Research Issue is declared resolved, material enters a manuscript, or content is published.
_Avoid_: Optional review, notification

## Surfaces

**Research Workspace**:
The private surface containing Research Issues, Research Runs, Literature Source Bundles, Evidence, and Research Drafts.
_Avoid_: Knowledge site, public notes

**Knowledge Site**:
The public surface containing only Trusted Knowledge that the user has chosen to publish.
_Avoid_: Research workspace, draft preview

**Site Chrome**:
The separately validated, non-research shell around the Knowledge Site, such
as the repository-root homepage and fixed visual configuration. Site Chrome
may help a human enter the knowledge tree, but it is never a Trusted Knowledge
authority or resolver input.
_Avoid_: Root knowledge note, second content tree
