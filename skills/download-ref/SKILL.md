---
name: download-ref
user-invocable: false
description: Use when the user pastes an arXiv ID, a DOI, a paper title, a local PDF path, or a bibliography stub and wants it added to the literature knowledge base — phrases like "download this arXiv", "add a shadow-tomography reference", "pull in DOI 10…", "render this PDF", "add a bibliography stub for".
---

# download-ref

Renders literature PDFs into Markdown under `.knowledge/literature/<topic>/`
and indexes them. Raw PDFs and extracted figures stay local (gitignored). The
workflow MUST be run via the bundled scripts — manual editing of `INDEX.md` or
rendered Markdown is not the intended path.

<example name="activate good">
User: "Pull arXiv 2002.08953 into the shadow-tomography references." → download-ref fires.
</example>

<example name="activate not-applicable">
User: "Cite Huang-Kueng-Preskill in the intro of the multicopy post." → download-ref does NOT fire (entry already in the KB); cite it from the topic's `refs.bib` directly.
</example>

## When to activate

Trigger phrases: "download this arXiv ID", "add a shadow-tomography
reference", "pull in DOI 10...", "render this PDF I have", "add a
bibliography stub for ...".

This is the repo-local adaptation of the `quantum.harness` download workflow.
That harness organizes references by numerical method; this digital garden
organizes them by research topic, mirroring the sections under `theory/`.

## Relation to the site bibliographies

The KB is the research library; the website cites from per-topic bib files.

| File | Role |
|---|---|
| `.knowledge/literature/ref.bib` | KB source of truth (this skill maintains it) |
| `theory/<Section>/refs.bib` | citation source for sections that declare one |
| `references.bib` (repo root) | site-wide default bibliography (`_quarto.yml`); sections without a `refs.bib` (e.g. `theory/quantum_complexity`) cite from it |

When a post cites a KB paper, copy its entry from the KB `ref.bib` verbatim
into whichever bibliography that post's frontmatter actually resolves to —
the section `refs.bib` when the section has one, otherwise the root
`references.bib`. Same cite key everywhere, so the files stay mergeable.

## Layout

```text
.knowledge/literature/
  ref.bib                           # source of truth (committed)
  <topic>/
    INDEX.md
    <rendered-reference>.md
    .raw/                           # metadata + PDFs, gitignored
    .figures/                       # extracted PDF images, gitignored
```

| Path | Committed? |
|---|---|
| `ref.bib` (combined library) | YES |
| `INDEX.md` (per-topic) | YES |
| `<rendered-reference>.md` | YES |
| `.raw/` | NO (gitignored) |
| `.figures/` | NO (gitignored) |

`ref.bib` is the human-edited source of truth. Each entry's `keywords`
field carries one or more topic slugs (`keywords = {shadow-tomography}`,
or multiple comma-separated slugs for a paper relevant to several topics).
Per-topic JSON manifests are derived from ref.bib via `bibtex_to_manifest.py`.

sci-brain interop: `helpers/resolve_kb.py` (vendored from upstream) is the
shared "where does the KB live" resolver used by the installed `survey`,
`ideas`, and `researchstyle` skills — it returns `<git-root>/.knowledge`.
Those tools manage their own survey KB under `.knowledge/`; this skill's
per-topic literature tree lives beside it under `.knowledge/literature/`.
They coexist and share only bib conventions (cite keys, keywords). For the
`download-ref --from-bib … --kb …` invocation that `survey` makes, see
"Bulk mode" below.

Topic slugs MUST match an existing literature dir
`.knowledge/literature/<topic>` when one exists. Each slug is a kebab-case
identifier for the `theory/` section it supports — usually the directory
name, though a few are normalized spellings, so the table below is
authoritative (`experiments` covers lab notes):

```text
shadow-tomography       (theory/Shadow_tomography)
compatibility           (theory/compatibility)
virtual-distillation    (theory/Virtual_Distillation)
magic                   (theory/Magic)
qec                     (theory/QEC)
stab-simulation         (theory/stab_simulation)
noisy-complexity        (theory/Noisy_complexity)
quantum-complexity      (theory/quantum_complexity)
learning-theory         (theory/learning_theo)
nonlocal-games          (theory/Nonlocal_Games_Survey)
boolean-analysis        (theory/Boolean_ana)
lgt                     (theory/LGT)
optimization            (theory/optimization)
factoring               (theory/Factoring)
fermi-hubbard           (theory/Fermi-Hubbard)
spin-liquid             (theory/Spin_liquid)
tn-sim                  (theory/TN_sim)
topo-matter             (theory/topo_matter)
dynamics                (theory/Dynamics)
supremacy               (theory/supermacy)
fingerprint             (theory/Fingerprint)
osf                     (theory/OSF)
experiments             (Experiments/)
```

Introduce a new slug only when no existing `theory/` section matches the
topic (and expect a matching section to appear later).

## Scripts

The helper scripts are bundled with this skill:

```sh
HELPERS="$(pwd)/skills/download-ref/helpers"
```

Safe to re-run: already-downloaded PDFs are kept, metadata JSON is refetched
and overwritten, and rendered markdown is overwritten from raw sources.

## Workflow

Run steps 1–7 in order. Step 2 (bib edit) is your authored input; steps
3–6 (derive manifest / fetch / render / index) are idempotent and safe to
re-run. Step 7 (verify) is REQUIRED before reporting.

### 1. Resolve paths

```sh
TOPIC=shadow-tomography
KB="$(pwd)/.knowledge/literature/$TOPIC"
BIB="$(pwd)/.knowledge/literature/ref.bib"
mkdir -p "$KB"
touch "$BIB"    # first use: the KB does not exist yet; it starts empty here
```

### 2. Add (or edit) the entry in `ref.bib`

Open `.knowledge/literature/ref.bib` and add an entry. For an arXiv preprint:

```bibtex
@article{huang_2020_predicting,
  author = {H.-Y. Huang and R. Kueng and J. Preskill},
  title = {Predicting many properties of a quantum system from very few measurements},
  year = {2020},
  journal = {Nature Physics},
  eprint = {2002.08953},
  archivePrefix = {arXiv},
  doi = {10.1038/s41567-020-0932-7},
  keywords = {shadow-tomography}
}
```

Patterns by entry type:

| Source | BibTeX type | Required fields |
|---|---|---|
| arXiv preprint (with venue) | `@article` | `eprint`, `archivePrefix = {arXiv}`, optional `doi`, `journal` |
| DOI-only journal article | `@article` | `doi`, `journal` |
| Book, lecture notes, closed source | `@book` or `@misc` | `title`, `author`, `year`, `note` |

`keywords = {<topic>, ...}` is mandatory — it pins the entry to one or more
topic dirs. `year` and `author` act as overrides on top of Semantic Scholar;
to override the displayed venue use `harness_venue = {...}` —
`bibtex_to_manifest.py` deliberately ignores `journal`/`booktitle` as venue
overrides. Stub entries (no arxiv / no doi) become local-only references
with no fetch step.

Cite key convention: `lastname_year_firstword` (lowercase, ASCII, stop-words
dropped). `append_bibtex.py` (propose mode) and `md_to_bibtex.py` both
follow this rule.

### 3. Derive the per-topic manifest

```sh
MANIFEST="/tmp/manifest-$TOPIC.json"
python3 "$HELPERS/bibtex_to_manifest.py" "$BIB" --method "$TOPIC" > "$MANIFEST"
```

(The helper's `--method` flag predates this repo; pass the topic slug.)
The output is the legacy JSON manifest that `fetch_metadata.py` and
`render.py` already consume — derived, not committed. Re-run after every
bib edit.

### 4. Fetch metadata and PDFs

```sh
python3 "$HELPERS/fetch_metadata.py" \
  --kb "$KB" \
  --manifest "$MANIFEST" \
  --download-arxiv-pdfs
```

The helper writes to `$KB/.raw/`. For DOI references, it tries Semantic Scholar
metadata and uses an arXiv preprint when one is available.

### 5. Render markdown

Rendering uses `pymupdf4llm` when installed, then falls back to `markitdown` or
`pdftotext`. If `pymupdf4llm` is missing, full text can still render but figures
may be absent.

| Use case | Command |
|---|---|
| Standard render (manifest) | `python3 "$HELPERS/render.py" --kb "$KB" --manifest "$MANIFEST"` |
| Single PDF in hand | `python3 "$HELPERS/render.py" --pdf sources/paper.pdf --out sources/paper.md` |
| Long book/lecture notes | add `--text-only` |

Single-PDF mode emits plain Markdown WITHOUT KB frontmatter — fine for
ad-hoc reading, but `index.py` will skip such a file even inside a topic
dir. To include a local PDF in the KB, add a bib entry and go through the
manifest route instead.

### 6. Regenerate the topic index

```sh
python3 "$HELPERS/index.py" \
  --kb "$KB" \
  --title "$TOPIC literature references" \
  --source-note "Literature references for the quarto-lab digital garden. Raw PDFs and extracted figures are local-only and gitignored."
```

Keep the title/source-note stable for repeat runs in the same topic folder.

### 7. Verify

```sh
git check-ignore "$KB/.raw/" "$KB/.figures/" || true
test -f "$KB/INDEX.md"
find "$KB" -maxdepth 1 -name '*.md' -print
```

<checklist name="verify-render">
- `.raw/` and `.figures/` are gitignored (verify with `git check-ignore`)
- `INDEX.md` exists at the topic root
- Each manifest entry has a corresponding `.md` file at the topic root
- Each entry's `INDEX.md` row carries the right full-text mark (`✅` / `—`), with stubs listed in their own section
- The new entry appears in `ref.bib` with a `keywords =` field
</checklist>

Report the rendered files, which entries have `full_text: yes`, and which are
metadata-only or stubs.

## Bulk mode (`--from-bib`)

The `survey` skill invokes this skill as
`download-ref --from-bib <ref.bib> --kb <dir>` to fetch PDFs and render full
text for every entry of an existing bib. Bulk mode has no topic slugs: skip
step 2 (the bib already exists — and bibs built by `append_bibtex.py` carry
no `keywords` field, which is fine here), and derive the manifest with NO
`--method` filter:

```sh
BIB=<ref.bib>
KB=<dir>
MANIFEST=/tmp/download-ref-manifest.json
python3 "$HELPERS/bibtex_to_manifest.py" "$BIB" > "$MANIFEST"
```

Run steps 4–5 unchanged against `$KB`. For step 6, the KB (often
`.knowledge/` itself) may belong to `survey` — reuse the title already in
its `INDEX.md` when one exists, and only fall back to
`--title "$(basename "$KB") references"` for a fresh dir. In step 7, skip
the `keywords` checklist item.

## Bootstrap: rebuilding `ref.bib` from rendered markdown

If `ref.bib` is missing or drifts from the rendered `.md` corpus:

```sh
python3 "$HELPERS/md_to_bibtex.py"      # writes .knowledge/literature/ref.bib
```

The script walks `.knowledge/literature/<topic>/*.md`, parses YAML
frontmatter, and emits one entry per unique canonical reference (merging
papers shared across topics into a single entry with multi-topic
`keywords`). Re-running overwrites the file — review the diff before
committing.

## Notes

- DO NOT commit `.raw/` or `.figures/`.
- DO NOT hand-edit the derived per-topic JSON manifest — change `ref.bib`.
- DO NOT put multiple topics in one folder; one topic folder per `theory/` section.
- For paywalled books, add a `@book` / `@misc` entry to `ref.bib` (no `eprint`,
  no `doi`) — the manifest derivation will route it as a stub.
