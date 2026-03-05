**Role:** Academic researcher building a review wiki on analog Rydberg quantum simulation.
**Working directory:** `theory/Topics/simulation_model/`
**Duration:** Work continuously until all phases are complete.

---

## Ground rules (NEVER violate)

1. **Reference constraint:** ONLY cite papers already in `refs.bib`. Read `refs.bib`
   first to know what papers are available. If a claim needs a reference not in
   `refs.bib`, either (a) web-search for the paper, verify it exists, add its
   BibTeX to `refs.bib`, then cite it, or (b) mark the claim with `<!-- TODO:
   find reference -->` and move on. NEVER fabricate a citation.

2. **No rewrite rule:** For the 7 existing files (index.qmd, TFIM.qmd,
   ferm_Hubbard.qmd, Boson-Hubbard.qmd, honeycomb.qmd, puccd.qmd,
   Effective_ham.qmd), you may ONLY:
   - Append new sections at the end (before `:::{#refs}` if present)
   - Insert a short `:::{.callout-tip}` context block after the YAML header
   - Add links in index.qmd to new sub-pages
   - Fill in "(t.b.c.)" or "(todo)" placeholders
   You must NOT rewrite, delete, reorganize, or rephrase any existing text.

3. **Git protocol:** After completing each file (new or modified), run:
   ```
   git add <modified-files> && git commit -m "<type>: <filename> — <summary>"
   ```
   where `<type>` is `create` for new files or `append` for existing files.
   Commit one logical unit at a time (a .qmd file + its refs.bib additions).
   NEVER use `git add -A` or `git add .`.

4. **Proof style:** Theorem/Lemma statements must be precise and correct.
   Proofs must be SHORT sketches: state the key idea in ≤10 lines, then cite
   the source. Do not write full algebraic derivations.

5. **Reader assumption:** The reader is a quantum computing experimentalist.
   They know Rydberg blockade, tweezer arrays, second quantization, basic QI.
   Do not explain undergraduate material. Get to the physics immediately.

6. **If stuck:** If you encounter an error, cannot find information, or are
   unsure about a fact, add `<!-- TODO: ... -->` and move to the next task.
   Do not spend more than 5 minutes on any single blocker.

---

## Phase 1: Read and plan (~30 min)

1. Read ALL 7 existing `.qmd` files and `refs.bib` in full.
2. For each of the 102 references in `refs.bib`, mentally classify which
   model category it belongs to: (a) spin/TFIM, (b) XY/XXZ, (c) topological,
   (d) LGT, (e) Hubbard, (f) density wave, (g) dynamics, (h) optimization,
   (i) quantum chemistry, (j) theory/toolbox, (k) other platform.
   You will use this classification throughout.

---

## Phase 2: Enhance index.qmd (~1 hour)

Append the following to `index.qmd` (before `:::{#refs}`):

### 2a. Notation callout
Insert near the top (after the "Overview" section) a callout:
```
:::{.callout-note}
## Notation
$\Omega$: Rabi frequency. $\Delta$: laser detuning. $n_i = |r_i\rangle\langle r_i|$:
Rydberg projector. $C_6$: van der Waals coefficient ($V = C_6/R^6$). $C_3$: dipolar
coefficient ($V = C_3/R^3$). $R_b = (C_6/\Omega)^{1/6}$: blockade radius.
:::
```

### 2b. Per-section status blurbs
For each model section in index.qmd that currently has only a Hamiltonian + 1-2 lines,
append 3-5 sentences covering: largest system demonstrated, key open problem, next
milestone. Use only refs already in `refs.bib`.

### 2c. Research groups table
Append a new section `# Research Groups {#sec-groups}` with a table:

| Group | Location | Species | Max $N$ | Key analog results |
|---|---|---|---|---|
| Lukin | Harvard/QuEra | $^{87}$Rb | 289 | TFIM, QSL, MIS, coarsening |
| ... | ... | ... | ... | ... |

Fill from information already present in the existing .qmd files and refs.bib.

### 2d. Global experiment timeline
Append a section `# Experiment Timeline {#sec-timeline}` with a chronological
table covering ALL analog Rydberg experiments referenced across the entire review.
Columns: Year | Group | $N$ | Model | Key result | Ref.

### 2e. Update links
For each new sub-page you will create in Phase 3, add a `See the [detailed notes](filename.qmd).` link in the corresponding index.qmd section.

**Commit:** `git add index.qmd && git commit -m "append: index.qmd — notation, status blurbs, groups table, timeline"`

---

## Phase 3: Create new sub-pages (~6 hours)

Create 6 new files. For each, follow this template:

```
---
title: "<Title>"
date: "2026-03-05"
categories:
  - Readings
bibliography: refs.bib
lang: en
---

[← Back to Index](index.qmd)

# <Model Name>

<2-3 sentences: what model, which Rydberg mechanism, why it matters for
condensed matter / HEP / quantum information.>

## Hamiltonian & Rydberg mapping

<Display the Hamiltonian. Explain which atomic states encode which degrees
of freedom, and which interaction mechanism (vdW / dipolar / dressing / Floquet)
generates which Hamiltonian term. Include parameter regime table if applicable.>

## Key phenomena

<Phase diagram highlights, key observables, classical simulation barriers.
Use theorem callouts for important theoretical results (proof sketch style).>

## Experiment overview

<Organize by research group. For each experiment entry:
**Author et al. (Year)** [@cite] — *N atoms, geometry.* One-sentence result.

End with a summary comparison table:
| Year | Group | Ref | $N$ | Dim | Key physics | What's new |
>

## Open problems

<3-6 bullet points. Concrete: "Demonstrate X on Y geometry with N > Z atoms"
or "Resolve whether the observed phase is truly topological by measuring ..."
Cite relevant theory proposals from refs.bib where available.>

## References
::: {#refs}
:::
```

### Pages to create (in this order):

**File 1: `XY_XXZ.qmd`** — Dipolar XY model, XXZ Heisenberg, spin squeezing, magnon spectroscopy.
Key refs: bornet2023scalable, chen2025spectroscopy, scholl2022microwave, chen2024anisotropic, chen2025floating.

**File 2: `topological.qmd`** — QSL/toric code on ruby lattice, SPT/bosonic SSH, Haldane phase.
Key refs: semeghini2021probing, verresen2021prediction, deleseleuc2019observation, fromonteil2025haldane, kornjaca2023trimer.

**File 3: `LGT.qmd`** — U(1) LGT / Schwinger model, Z₂ LGT, string breaking, quantum dimer models.
Key refs: surace2020lattice, observation2025string, homeier2023z2, geier2023floquet, samajdar2020quantum, dimer2025gadgets, zhou2022thermalization, wang2023interrelated.

**File 4: `density_wave.qmd`** — Devil's staircase, commensurate Z₂/Z₃/Z₄ phases, floating phase, Kibble-Zurek dynamics.
Key refs: ebadi2021quantum, keesling2019quantum, chen2025floating, scholl2021quantum.

**File 5: `dynamics.qmd`** — PXP / quantum many-body scars, discrete time crystals, quantum coarsening / Higgs mode, information scrambling.
Key refs: bernien2017probing, bluvstein2021controlling, bluvstein2025quantum, kongkhambut2024higher, chen2024collapse, zhang2025anomalous, maskara2025emergent.

**File 6: `optimization.qmd`** — Maximum independent set, quantum speedup, graph problems on 3D arrays.
Key refs: ebadi2022quantum, song2021quantum, kim2022finding.

**After each file:** Commit immediately.
```
git add <new-file>.qmd refs.bib && git commit -m "create: <new-file>.qmd — <brief summary>"
```

**Pacing:** Spend roughly 1 hour per file. If a file is going faster (e.g.,
optimization.qmd has fewer refs), use the extra time to deepen the next one.
Prioritize the experiment overview table — that is the highest-value content.

---

## Phase 4: Expand existing sub-pages (~2 hours)

### 4a. Boson-Hubbard.qmd
Append:
- `## Experiment overview` section covering qiao2025 and qiao2025doped
  (bosonic t-J-V realization on $^{87}$Sr tweezer arrays).
- `## Open problems` section (fermionic vs bosonic statistics, scaling,
  connection to cuprate physics).

### 4b. honeycomb.qmd
Append:
- `## Open problems` section (pure Kitaev realization, non-Abelian anyon braiding,
  scaling digital vs analog approaches).

### 4c. puccd.qmd
Append:
- `## Experiment status` section (has any neutral-atom pUCCD been demonstrated?
  If not, state this and describe what would be needed).
- `## Open problems` section.

### 4d. ferm_Hubbard.qmd
- Fill in the "(t.b.c.)" placeholder in the QPU error section (~line 496).
  Write 5-10 sentences on how to quantify the adiabatic state preparation
  error, referencing the quasi-adiabatic protocol and citing relevant refs.

### 4e. TFIM.qmd
Append:
- `## Open problems` section if not present (critical dynamics in 2D,
  finite-temperature phase diagram, scaling beyond 300 atoms, etc.).

**After each file:** Commit immediately.

---

## Phase 5: Final consistency pass (~30 min)

1. Read `index.qmd` and verify every model section links to a sub-page.
   Fix any broken links.
2. Read each sub-page and verify the `[← Back to Index](index.qmd)` link
   is present.
3. Verify refs.bib has no duplicate keys (search for any key appearing twice).
4. Commit any fixes:
   ```
   git add -u && git commit -m "fix: cross-references and link consistency"
   ```
5. Run `quarto render theory/Topics/simulation_model/` to check for build errors.
   If there are errors, fix them and commit.

---

## Summary of expected output

| File | Action | Est. words added |
|---|---|---|
| `index.qmd` | Append notation, blurbs, groups, timeline | ~2000 |
| `XY_XXZ.qmd` | Create | ~2500 |
| `topological.qmd` | Create | ~2500 |
| `LGT.qmd` | Create | ~3000 |
| `density_wave.qmd` | Create | ~2000 |
| `dynamics.qmd` | Create | ~3000 |
| `optimization.qmd` | Create | ~1500 |
| `Boson-Hubbard.qmd` | Append | ~800 |
| `honeycomb.qmd` | Append | ~500 |
| `puccd.qmd` | Append | ~500 |
| `ferm_Hubbard.qmd` | Append | ~300 |
| `TFIM.qmd` | Append | ~300 |
| **Total** | | **~19,000** |

Git log should show ~14 commits, each individually revertible.
