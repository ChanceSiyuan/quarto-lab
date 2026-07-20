---
name: render-site
description: Use when rendering, previewing, or debugging the site build — "render the site", "quarto render", "preview this post", render/venv errors, navigation or sidebar regeneration, or verifying that a new/edited .qmd builds.
---

# render-site

How to build this Quarto site correctly from either working copy. The repo
exists in two byte-synced places: the laptop-side copy
(`/home/chance/dgx/quarto-lab`, an SSH sync where the local `.venv` may be
broken) and the DGX (`chance@100.106.69.117`, repo at `~/quarto-lab`) where
the toolchain is intact.

<example name="activate good">
User: "Render the site and check the new Magic note builds." → render-site fires.
</example>

<example name="activate not-applicable">
User: "Deploy the site." → render-site does NOT cover deployment; the old `sync.sh` was removed (commit f4a0491). Ask the user for the current deployment path.
</example>

## Where to render

Check the venv first:

```sh
python -c 1 2>/dev/null || true
test -x .venv/bin/python && echo local-ok || echo local-broken
```

| State | Action |
|---|---|
| `local-ok` AND repo on local disk | render in place: `./scripts/render_site.sh` |
| `local-ok` but repo is the slow SSH-mounted copy (`/home/chance/dgx/…`) | prefer the DGX over SSH (below) — even single-file renders scan the whole project tree and time out over the mount |
| `local-broken` (dangling `.venv/bin/python` symlink) | render on the DGX over SSH (below); local edits are already there — the copies stay byte-identical |

```sh
ssh chance@100.106.69.117 'bash -lc "export PATH=$HOME/.local/bin:$PATH && cd ~/quarto-lab && quarto render"'
```

Quarto on the DGX lives at `~/.local/bin/quarto`, hence the login shell +
PATH export. A full site render is ~200 files → `_site/` (~42 MB).

## Commands

| Task | Command |
|---|---|
| Full render | `./scripts/render_site.sh` (wraps `quarto render`) |
| Single file | `quarto render theory/<Section>/<note>.qmd` |
| Preview server | `quarto preview` (port 4200) |
| Fast profile | `quarto render --profile fast` (skips nav generation) |
| Nav/sidebar regen only | `.venv/bin/python scripts/update_theory_nav.py` |
| Nav generator tests | `.venv/bin/python -m pytest tests/` |

## Navigation is generated — do not hand-edit

The pre-render hook (`_quarto.yml`) runs `scripts/update_theory_nav.py`.
Generator-owned artifacts (treat all of these as generated):

- the `# BEGIN/END AUTO NOTE SIDEBARS` block in `_quarto.yml`
- `<!-- BEGIN/END AUTO NOTES TABLE -->` blocks in section `index.qmd` files
  (missing indexes are created whole; theory/experiment overview tables are
  rewritten too)
- `sidebar:` ids inserted into section `_metadata.yml` files

New notes under `theory/<Section>/` are picked up automatically. Set `QUARTO_SKIP_NAV=1` to skip the hook, and
note the `fast` profile skips it by design. Valid note statuses:
`stable`, `draft`, `rough`.

## Rules

- NEVER edit `_site/` — it is generated output.
- NEVER hand-edit content between the AUTO markers; edit sources and re-run
  the generator.
- A failed render must be fixed at the source and re-rendered; report the
  actual error, not a guess.

## Verify a content change

<checklist name="verify-render">
- The touched file renders cleanly (single-file render is enough for drafts)
- Citations resolve (no `?@key` in output HTML)
- The note appears in its section's generated notes table / sidebar
- No stray edits inside AUTO-generated blocks (`git diff` shows only intended files)
</checklist>
