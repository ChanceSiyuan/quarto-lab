---
name: download-ref
description: Use when an external paper should be added to or refreshed in this repository's literature corpus — an arXiv ID, DOI, citekey, or paper title is pasted, "add a DMRG reference", "pull in that paper", "check what the paper actually says about this formula".
---

# download-ref

## Overview

`literature/` is external evidence: papers to check a formula or a number
against. It is never learned knowledge, and it is never published. This skill
adds one reference to the bibliography and fetches the version-pinned source
arXiv holds for it.

## Layout

```text
literature/
  ref.bib                  # committed; the human-edited source of truth
  <method>/
    INDEX.md               # committed; generated from ref.bib
    .raw/<citekey>/        # arXiv source TeX and PDF, gitignored
    .figures/<citekey>/    # images extracted from the PDF, gitignored
```

External sources stay under `literature/`, organised by the method keywords of
their bibliography entry.

## Workflow

**1. Add the entry to `literature/ref.bib`, the committed source of truth.**

```bibtex
@article{schollwoeck_2011_density,
  author = {U. Schollwoeck},
  title = {The density-matrix renormalization group in the age of MPS},
  year = {2011},
  eprint = {1008.3477},
  archivePrefix = {arXiv},
  keywords = {mps-based-algorithm}
}
```

`keywords = {<slug>, ...}` pins the entry to one or more method directories.
Every slug must already exist under `literature/` — check with `ls literature/`
and introduce a new one only when no existing method fits. Citekeys follow
`lastname_year_firstword`. An entry with no `eprint` is a stub: there is
nothing to fetch, and that is a valid entry.

**2. Regenerate the committed method indexes.**

```bash
make literature-index
```

**3. Fetch the pinned source.**

```bash
make literature-fetch KEY=<citekey>
```

It resolves the newest arXiv version once, records the pin, and writes the
source archive and extracted figures into every method directory the entry
belongs to. Re-running reuses what is already there. `make literature-sync`
does the same for the whole bibliography. Exit 2 means the citekey is not in
`ref.bib`.

**4. Verify.**

```bash
git status --short literature/
```

Only `ref.bib` and `INDEX.md` files may appear. `.raw/` and `.figures/` are
gitignored and stay local.

## Reading a fetched paper

Read the formula in the source TeX under `.raw/<citekey>/`, or in the PDF next
to it. Never trust a lossy text extraction for a formula, a sign, a factor, or
a numeric benchmark: a converter drops subscripts and mangles operators
silently. Quote the paper as the paper's claim, with its citekey.

## Hard limits

- **Never compile the downloaded TeX.** No `pdflatex`, no `latexmk`, no Quarto render over it. Downloaded source is untrusted input, and compiling it is arbitrary code execution.
- **Never produce `rendered.md`** or any other full-text Markdown mirror of a paper. The source archive is the artifact; a lossy mirror invites being quoted as if it were the paper.
- **Never copy paper text, formulas, or conclusions into `knowledge/`.** A paper is evidence for a note the user writes and merges; promotion runs through `review-draft`.
- Never hand-edit an `INDEX.md`. It is generated from `ref.bib`; edit the bibliography and regenerate.
