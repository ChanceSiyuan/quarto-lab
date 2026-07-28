# AGENTS.md

This repository is a human-reviewed Quarto knowledge system for quantum
computing. The current phase implements trusted reading, validation,
resolution, and static rendering. It does not implement an autonomous
research backend.

## Physical trust boundary

- `theory/**/*.qmd` is the only Trusted Knowledge authority.
- `drafts/` and `conference/` are untrusted sibling workspaces. Never use them
  as factual fallback, resolver input, or public content.
- `.knowledge/literature/` is external Evidence, not learned knowledge. Do not
  promote extracted paper text into `theory/`.
- `_site/`, `work/`, caches, notebooks, and generated navigation are not source
  authority.
- The root `index.qmd` is separately validated Site Chrome. It may link humans
  into `theory/`, but it never enters the graph or an agent Reading Bundle.

Only the user's explicit approval promotes a draft into `theory/`. Do not edit,
move, rewrite, split, or publish a draft as trusted knowledge without that
approval.

## Resolver-first research answers

Before stating a research fact or interpretation that may be covered by the
user's learned knowledge:

```bash
make knowledge-resolve QUERY="<the user's research question>"
```

- On `match`, read every path in `bundle.orderedFiles` before answering.
- On `ambiguous`, present the alternatives; do not choose silently.
- On `no-match`, say the learned knowledge has no match. Use a separately
  named external-research/source-audit workflow if the user wants one.
- Never search `drafts/`, `conference/`, or literature as a trusted fallback.

## Trusted page contract

- Every directory containing trusted QMD descendants has a direct
  `index.qmd`.
- Every topic index contains exactly one `## Reading map`.
- That map lists every direct content page and child-topic `index.qmd` exactly
  once, in human reading order.
- `## Related topics` is optional and may link only to trusted indexes.
- Reading maps are the sole order authority for human sidebars and agent
  Reading Bundles. Do not recreate `_sidebar.yml`, `_metadata.yml`, AUTO
  blocks, or filesystem-derived navigation.
- Trusted frontmatter keys are limited to `title`, `description`, `aliases`,
  `date`, `lang`, `categories`, `subtitle`, `abstract`, `tags`, and
  `bibliography`. A nonempty `title` is required, and decoded metadata strings
  may not contain HTML.
- Trusted Markdown and raw-HTML links, images, and media/resource URLs must
  remain inside `theory/`, except for the approved root `references.bib`.
  Non-page dependencies must be allowlisted regular assets; SVG content is
  audited. Symlinks, active HTML, and network-loading CSS are forbidden.
- Quarto shortcodes are forbidden in the entire trusted body, including inline
  and fenced code, and in raw HTML, decoded frontmatter, and base
  configuration. Quarto expands them even with `--no-execute`, so
  include/embed/env shortcodes can read outside the projected tree or leak the
  build environment.

## Stable commands

```bash
make help
make knowledge-check
make knowledge-resolve QUERY="triangular TFIM"
make knowledge-build
make knowledge-preview
make test
```

`./scripts/render_site.sh` is a compatibility alias for
`make knowledge-build`.

The safe builder validates first, creates a temporary hook-free Quarto
project, separately validates the fixed root homepage, copies only validated
QMD and dependencies, reconstructs `_quarto.yml` from a strict safe schema,
derives navigation from Reading maps, reasserts `execute.enabled: false`, and
invokes Quarto with `--no-execute`. It audits output and atomically replaces
`_site/` only after a complete success. Never bypass it with a direct Quarto
render or edit `_site/`.

## Change discipline

- Preserve unrelated user changes in this intentionally evolving repository.
- Add or change behavior test-first.
- Keep `drafts/` and `conference/` unpublished.
- Keep generated files out of Git.
- Ask before any deployment. The repository currently has no deployment
  workflow.
- Agent skills are sourced in `skills/` and registered in `Ion.toml`; generated
  consumer copies are not source authority. Install them only through
  `./scripts/install_skills.sh`, which verifies exact pins and swaps both
  consumers transactionally.
