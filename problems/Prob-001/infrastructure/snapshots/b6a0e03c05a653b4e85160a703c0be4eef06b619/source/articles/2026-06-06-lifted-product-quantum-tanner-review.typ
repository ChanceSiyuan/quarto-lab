#import "@preview/cetz:0.4.0"

#set page(margin: 1.6cm)
#set text(size: 10pt)
#set par(justify: true, leading: 0.62em)
#set heading(numbering: "1.")

#let title = [Lifted-Product and Quantum Tanner Codes for Finite-Length Quantum Code Search]
#let authors = [AutoQEC review draft]
#let bib = bibliography("2026-06-06-lifted-product-quantum-tanner-review.bib")

#show link: set text(fill: blue.darken(30%))

#let smallcaps(label, body) = [
  #text(weight: "semibold", smallcaps(label))
  #body
]

#let section_box(title, body, fill: rgb("f7f8fc"), stroke: rgb("d9deeb")) = rect(
  width: 100%,
  inset: 10pt,
  radius: 6pt,
  fill: fill,
  stroke: stroke,
  body,
)

#let problem_table(rows) = table(
  columns: (5%, 27%, 38%, 20%, 10%),
  stroke: (x, y) => if y == 0 { 0.8pt + black } else { 0.4pt + rgb("d7dbe6") },
  inset: 6pt,
  table.header(
    [#strong[No.]], [#strong[Problem]], [#strong[Why it matters]], [#strong[Who could solve it]], [#strong[Urgency]],
  ),
  ..rows,
)

#let pros_cons_table(rows) = table(
  columns: (5%, 47.5%, 47.5%),
  stroke: (x, y) => if y == 0 { 0.8pt + black } else { 0.4pt + rgb("d7dbe6") },
  inset: 6pt,
  table.header([#strong[No.]], [#strong[Advantages]], [#strong[Matching limitations]]),
  ..rows,
)

#let milestone_table(rows) = table(
  columns: (35%, 33%, 22%, 10%),
  stroke: (x, y) => if y == 0 { 0.8pt + black } else { 0.4pt + rgb("d7dbe6") },
  inset: 6pt,
  table.header([#strong[Milestone]], [#strong[Result]], [#strong[Group / Company]], [#strong[Year]]),
  ..rows,
)

= #title

#align(center)[
  #text(size: 12pt, weight: "semibold")[Review]
  #v(0.25em)
  #text(fill: gray.darken(20%))[#authors]
  #v(0.25em)
  #text(fill: gray.darken(10%))[Generated 2026-06-06 from the AutoQEC knowledge base.]
]

#v(0.9em)

#section_box(
  [Scope],
  [
    This report assesses the #strong[lifted-product / quantum Tanner] branch of qLDPC codes as the strongest current target for searching better #emph[finite-length] quantum code instances. It is aimed at internal technical decision-making, not as a general introduction to all qLDPC families.
  ],
)

= What Is It

If the practical question is which quantum error-correcting code family is now most worth searching for stronger finite-length instances, then the strongest current answer is not the 2D-local topological line, but the qLDPC branch centered on #strong[lifted-product] and #strong[quantum Tanner] constructions. The attraction of this branch is not only that it offers better asymptotic parameter tradeoffs than planar surface-code-style families, but that it now has enough internal structure to support explicit finite-length design and nontrivial decoding theory @breuckmann_2021_balanced @leverrier_2022_quantum @panteleev_2022_almost.

At a high level, these constructions replace geometric locality with algebraic and combinatorial structure. In lifted-product codes, one starts from structured classical LDPC ingredients such as quasi-cyclic or protograph-derived parity-check matrices, then applies product and lifting operations to build sparse CSS quantum checks. In quantum Tanner codes, one starts from graphs or square complexes together with local codes, then defines paired Tanner constructions that share a common combinatorial substrate and together form a CSS code @leverrier_2022_quantum @guemard_2025_moderate @raveendran_2025_minimum. For an automated search project, this matters because the search space is not “all sparse CSS matrices,” but a constrained parameterized family with meaningful priors.

What makes this direction different from the dominant surface-code baseline is the trade. Surface-style codes are geometrically simple and hardware-friendly, but their locality strongly constrains parameter scaling. Lifted-product and Tanner families instead trade more complicated connectivity for better rate-distance potential, and in some cases for structured decoders with provable guarantees @leverrier_2023_decoding @leverrier_2025_efficient. The key practical implication is that a search effort in this area must optimize not only `[[n,k,d]]`, but also decoder tractability and connectivity cost.

#v(0.6em)
#figure(
  grid(
    columns: (31%, 3%, 31%, 3%, 32%),
    gutter: 0.6em,
    align(center + horizon)[
      #rect(
        inset: 8pt,
        radius: 5pt,
        fill: rgb("eef3ff"),
        stroke: rgb("b8c7ee"),
        width: 100%,
        [
          *Structured classical ingredients*
          - QC / protograph LDPC
          - local tensor-product codes
          - graphs / square complexes
        ],
      )
    ],
    align(center + horizon)[#text(size: 16pt, weight: "semibold")[→]],
    align(center + horizon)[
      #rect(
        inset: 8pt,
        radius: 5pt,
        fill: rgb("eef8f0"),
        stroke: rgb("bed9c4"),
        width: 100%,
        [
          *Lift / Product / Tanner construction*
          - balanced or lifted product
          - covering / quotient
          - paired CSS check design
        ],
      )
    ],
    align(center + horizon)[#text(size: 16pt, weight: "semibold")[→]],
    align(center + horizon)[
      #rect(
        inset: 8pt,
        radius: 5pt,
        fill: rgb("fff5eb"),
        stroke: rgb("e7c7a5"),
        width: 100%,
        [
          *Finite-length qLDPC search target*
          - sparse $H_X, H_Z$
          - candidate $[[n,k,d]]$
          - score by decoder + connectivity
        ],
      )
    ],
  ),
  caption: [Architecture of the search target: structured ingredients are mapped through product/lift/Tanner operations into finite-length qLDPC families with decoder-aware evaluation.]
)

= Pros and Cons

#pros_cons_table((
  [1],
  [*Better parameter potential than 2D-local baselines.* This line already contains asymptotically good or almost-good qLDPC constructions, so it is the most credible current destination for continued finite-length code search rather than a speculative alternative @breuckmann_2021_balanced @leverrier_2022_quantum @panteleev_2022_almost.],
  [*The connectivity burden is harder.* These gains come from algebraic products, lifts, coverings, and quotients rather than geometric locality, so hardware realization is usually more complex than for planar topological codes @breuckmann_2021_balanced @leverrier_2022_quantum @guemard_2025_moderate.],

  [2],
  [*The search space is structured.* QC lifted-product and lifted-Tanner families are parameterized enough to support systematic enumeration and pruning, which is exactly what an AutoQEC-style project needs @raveendran_2025_minimum @guemard_2025_moderate.],
  [*The same structure narrows expressivity.* Guarantees often hold only for restricted subclasses, specific base matrices, specific coverings, or specific local codes, which means a badly chosen ansatz can waste the whole search budget @raveendran_2025_minimum @guemard_2025_moderate.],

  [3],
  [*Decoding theory is no longer missing.* Quantum Tanner codes now have structured decoders with linear-weight adversarial guarantees, and those ideas partially transfer to neighboring lifted-product subclasses @leverrier_2023_decoding @leverrier_2025_efficient.],
  [*Decoder maturity is uneven across subclasses.* A family can look good parametrically while still lacking a decoder with useful finite-length constants or implementable heuristics @leverrier_2023_decoding @leverrier_2025_efficient @panteleev_2021_degenerate.],

  [4],
  [*Finite-length evidence now exists.* Moderate-length lifted Tanner examples and finite-length LP design rules show that this is no longer only an asymptotic theorem playground @panteleev_2021_degenerate @guemard_2025_moderate @raveendran_2025_minimum.],
  [*Finite-length constants remain fragile.* Small structural changes can create harmful low-weight logical operators or collapse the effective minimum distance, so family-level optimism does not automatically transfer to a specific code instance @panteleev_2021_degenerate @raveendran_2025_minimum.],

  [5],
  [*Theory and search can inform each other.* Balanced-product, quantum Tanner, almost-linear-distance, and finite-length design papers form a coherent ladder from asymptotic skeleton to explicit search priors @breuckmann_2021_balanced @panteleev_2022_almost @guemard_2025_moderate @raveendran_2025_minimum.],
  [*Asymptotic success does not guarantee the best short codes.* The regime that matters for $n approx 10^2 - 10^3$ still has to be mapped separately; asymptotic quality is a guide, not a finished answer @panteleev_2022_almost @panteleev_2021_degenerate @raveendran_2025_minimum.],

  [6],
  [*The families are more interpretable than raw sparse-matrix brute force.* Failures and successes can usually be tied back to a local code, covering choice, base matrix, or product operation, which improves the scientific value of a search campaign @guemard_2025_moderate @raveendran_2025_minimum.],
  [*Evaluation is still expensive.* Distance estimation, low-weight logical screening, and decoder-aware scoring remain costly enough that naive brute force will stall without good proxies and family-specific pruning @raveendran_2025_minimum @leverrier_2023_decoding.],
))

= State of the Art

== Milestone Table

#milestone_table((
  [[Balanced-product construction @breuckmann_2021_balanced]],
  [One of the first explicit non-random qLDPC constructions to push beyond the early $sqrt(N)$ barrier and place quotient/product structure at center stage.],
  [Breuckmann, Eberhardt],
  [2021],

  [[Degenerate finite-length qLDPC baseline @panteleev_2021_degenerate]],
  [Established that finite-length qLDPC instances can already be competitive and should not be treated only as asymptotic shadows.],
  [Panteleev, Kalachev],
  [2021],

  [[Quantum Tanner codes @leverrier_2022_quantum]],
  [Defined the quantum Tanner construction as a full qLDPC program and provided a new asymptotically good backbone.],
  [Leverrier, Zémor],
  [2022],

  [[Almost-linear minimum distance qLDPC @panteleev_2022_almost]],
  [Delivered the central almost-linear-distance benchmark for the lifted-product branch.],
  [Panteleev, Kalachev],
  [2022],

  [[Decoding Quantum Tanner Codes @leverrier_2023_decoding]],
  [Introduced structured decoders for quantum Tanner codes and showed transferability to neighboring lifted-product families.],
  [Leverrier, Zémor],
  [2023],

  [[High-threshold low-overhead BB memory @bravyi_2024_high]],
  [Gave a practical memory-level demonstration that nonlocal qLDPC codes can compete with surface-code thresholds and overhead.],
  [IBM Quantum / Bravyi et al.],
  [2024],

  [[Moderate-length lifted quantum Tanner codes @guemard_2025_moderate]],
  [Produced explicit moderate-length lifted-Tanner examples, including instances with $d > sqrt(n)$.],
  [Guémard, Zémor],
  [2025],

  [[Finite-length LP design constraints @raveendran_2025_minimum]],
  [Turned finite-length QC lifted-product design into a more explicit combinatorial constraint problem.],
  [Raveendran, Declercq, Vasić],
  [2025],

  [[Constant-fraction decoding guarantee @leverrier_2025_efficient]],
  [Strengthened the Tanner decoding line toward constant-fraction adversarial decoding and linear-time convergence.],
  [Leverrier, Zémor],
  [2025],

  [[Generalized-check-node Tanner decoding @mostad_2026_improved]],
  [Shows that Tanner decoding is still actively improving at the finite-length algorithmic level.],
  [Mostad, Rosnes, Lin],
  [2026],

  [[High-girth square-base HGP via CPM lifts @okada_2026_highgirth]],
  [Extends the finite-length product/lift design space toward stronger girth and regularity constraints.],
  [Okada, Kasai],
  [2026],
))

== Who Is Building What

- *Anthony Leverrier / Gilles Zémor* are the central figures in the quantum Tanner line. They introduced the core construction @leverrier_2022_quantum, then developed dedicated decoding algorithms @leverrier_2023_decoding, and later pushed decoding guarantees further @leverrier_2025_efficient. This is the main line to watch if decoder-aware search is the goal.

- *Pavel Panteleev / Gleb Kalachev* anchor the lifted-product and almost-linear-distance branch. Their work supplies both a major asymptotic benchmark @panteleev_2022_almost and an important finite-length baseline @panteleev_2021_degenerate. For AutoQEC they serve as both theoretical reference and evaluation baseline.

- *Nikolas Breuckmann / Jens Eberhardt* represent the balanced-product viewpoint @breuckmann_2021_balanced. Their contribution is especially important as theoretical infrastructure: it explains which quotient/product mechanisms are worth preserving even when the actual search is shifted to more actionable finite-length subclasses.

- *Virgile Guémard / Gilles Zémor* drive the current moderate-length lifted-Tanner branch @guemard_2025_moderate. This is one of the most directly relevant lines for searching strong explicit instances rather than proving new asymptotic theorems.

- *Raveendran / Declercq / Vasić* focus on finite-length lifted-product design conditions @raveendran_2025_minimum. Their work is especially useful for turning generic LP enthusiasm into a constrained and automatable search space.

- *IBM Quantum / Bravyi et al.* provide the industrial realism check. Their BB-memory result is not itself a Tanner or lifted-product construction, but it matters because it demonstrates that high-rate nonlocal qLDPC ideas can translate into credible end-to-end memory protocols @bravyi_2024_high.

- *Mostad / Rosnes / Lin* show that decoder development for Tanner-family codes remains active, not settled, via generalized-check-node improvements @mostad_2026_improved.

- *Okada / Kasai* indicate that finite-length product/lift structure design is still widening, especially along high-girth and regular lifted constructions @okada_2026_highgirth.

= Key Problems

#problem_table((
  [1],
  [Turning asymptotic theory into strong finite-length priors],
  [The field already knows which large-scale constructions are good, but not yet which local codes, coverings, base matrices, and quotient operations should be searched first in the $10^2 - 10^3$ qubit regime @breuckmann_2021_balanced @leverrier_2022_quantum @panteleev_2022_almost.],
  [AutoQEC-style search systems plus coding theorists],
  [*Critical*],

  [2],
  [Controlling low-weight logical operators and bad degeneracy patterns],
  [Many candidate finite-length instances fail not because $n$ or $k$ look weak, but because hidden low-weight logicals or pathological degeneracy ruin the code after construction @panteleev_2021_degenerate @raveendran_2025_minimum.],
  [Finite-length LP / QC / distance-analysis researchers],
  [*Critical*],

  [3],
  [Integrating decoder quality into the search objective],
  [A code family can look excellent on $[[n,k,d]]$ while still being a poor practical target if its decoder is weak, unstable, or too specialized. Decoder tractability must become a first-class search metric @leverrier_2023_decoding @leverrier_2025_efficient @mostad_2026_improved.],
  [Decoder researchers and search-system builders],
  [*High*],

  [4],
  [Building a larger moderate-length instance library],
  [The finite-length evidence is now real, but still thin. Without a wider benchmark library, it is difficult to tell which favorable examples reflect generic family behavior and which are isolated lucky points @guemard_2025_moderate @raveendran_2025_minimum.],
  [Academic groups and automated search projects],
  [*High*],

  [5],
  [Quantifying connectivity/layout cost alongside code parameters],
  [Surface-style codes remain the engineering reference partly because their implementation cost is legible. Nonlocal qLDPC families need equally explicit accounting for check scheduling, long-range couplers, thickness, and layout burden @bravyi_2024_high @postema_2025_existence @breuckmann_2021_balanced.],
  [Hardware-aware QEC and architecture researchers],
  [*High*],

  [6],
  [Coupling strong code families to richer fault-tolerance stacks],
  [Good memory performance does not automatically imply a good full-stack platform. The lifted-product / Tanner line still needs clearer stories about logical gates, syndrome-extraction overhead, and protocol integration @bravyi_2024_high @guemard_2025_moderate @leverrier_2022_quantum.],
  [Fault-tolerance protocol and architecture teams],
  [*Medium*],
))

= Bottom Line

For the specific goal of #strong[searching stronger finite-length code instances], the best current research bet is the #strong[lifted-product / quantum Tanner] branch of qLDPC codes. It has the strongest combination of asymptotic credibility, finite-length search structure, and decoder progress. Balanced-product is the right theoretical skeleton; moderate-length lifted Tanner and constrained finite-length lifted-product families are the most actionable search spaces; decoder-aware evaluation should be part of the search loop from the beginning @breuckmann_2021_balanced @guemard_2025_moderate @raveendran_2025_minimum @leverrier_2023_decoding @leverrier_2025_efficient.

The main caution is that this is still not a “search all sparse CSS codes and pick the best one” problem. Success depends on choosing the right parameterized family, the right finite-length constraints, and the right decoder-aware objective. Within those constraints, however, this is the most defensible place to spend the next serious search budget.

#v(1.2em)
#bibliography("2026-06-06-lifted-product-quantum-tanner-review.bib", title: [References])
