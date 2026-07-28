// Quantum code distance — technology review. Organized by technical approach.
// Compile: typst compile 2026-06-09-quantum-code-distance-review.typ
#import "@preview/cetz:0.4.0"

#set page(margin: 1.6cm, numbering: "1")
#set text(size: 10pt)
#set par(justify: true, leading: 0.62em)
#set heading(numbering: "1.")
#show link: set text(fill: blue.darken(30%))

// ---- reusable helpers (from review-writer scaffold) ---------------------
#let section_box(title, body, fill: rgb("f7f8fc"), stroke: rgb("d9deeb")) = rect(
  width: 100%, inset: 10pt, radius: 6pt, fill: fill, stroke: stroke,
  [#strong[#title] #v(0.3em) #body],
)
#let proscons(pros, cons) = grid(
  columns: (1fr, 1fr), gutter: 0.6em,
  rect(width: 100%, inset: 7pt, radius: 5pt, fill: rgb("eef6ef"), stroke: rgb("bcd9c4"))[
    #text(weight: "semibold", fill: green.darken(30%))[Strengths]
    #pros
  ],
  rect(width: 100%, inset: 7pt, radius: 5pt, fill: rgb("fbecec"), stroke: rgb("e3c6c6"))[
    #text(weight: "semibold", fill: red.darken(20%))[Limitations]
    #cons
  ],
)
#let compare_table(rows) = table(
  columns: (17%, 19%, 23%, 15%, 26%),
  stroke: (x, y) => if y == 0 { 0.8pt + black } else { 0.4pt + rgb("d7dbe6") },
  inset: 6pt,
  table.header(
    [#strong[Approach]], [#strong[Scalability]], [#strong[Verifiability / cost]], [#strong[Maturity]], [#strong[Best-fit use case]],
  ),
  ..rows,
)
#let problem_table(rows) = table(
  columns: (5%, 24%, 38%, 23%, 10%),
  stroke: (x, y) => if y == 0 { 0.8pt + black } else { 0.4pt + rgb("d7dbe6") },
  inset: 6pt,
  table.header(
    [#strong[No.]], [#strong[Problem]], [#strong[Why it matters]], [#strong[Who could solve it]], [#strong[Urgency]],
  ),
  ..rows,
)
#let crit = text(fill: red.darken(10%), weight: "bold")[Critical]
#let high = text(fill: orange.darken(20%), weight: "bold")[High]
#let med = text(fill: olive.darken(10%), weight: "bold")[Medium]

// ---- title --------------------------------------------------------------
#heading(numbering: none)[Computing the Code Distance of Quantum Error-Correcting Codes]
#align(center)[
  #text(size: 12pt, weight: "semibold")[State-of-the-Art Review]
  #v(0.25em)
  #text(fill: gray.darken(20%))[review draft]
  #v(0.25em)
  #text(fill: gray.darken(10%))[Generated 2026-06-09 from a #raw("/survey") knowledge base (25 references).]
]
#v(0.8em)

#section_box(
  [Scope],
  [This report assesses how the *minimum distance* $d$ of a quantum error-correcting code is computed in practice. It is written for someone deciding which tool or method to use, or scoping research in the area. The review is organized #emph[by technical approach]: each method family is described with its mechanism, current best results, and trade-offs. Code *construction* and *decoding* are out of scope except where they bear on distance computation.],
)

= What and Why

A quantum error-correcting code stores $k$ logical qubits in $n$ physical qubits via a *stabilizer group* $S$ of commuting Pauli operators. Its *distance* $d$ is the minimum weight of a Pauli operator that commutes with every stabilizer but is not itself a stabilizer — the lightest non-trivial *logical* operator, $d = min "wt"(N(S) without S)$ @gottesman_1997_stabilizer @webster_2026_distance. A distance-$d$ code detects $d-1$ errors and corrects $floor(d slash 2)$, so $d$ sets the fault-tolerance budget directly. Unlike $n$ and $k$, which are read off the construction, $d$ must be *computed* — and that is the problem this report surveys.

Why it is hard, and why that matters now: distance computation is a minimum-weight codeword search over a coset, the same combinatorial object that makes the classical minimum-distance problem *NP-hard* @vardy_1997_intractability @dumer_2003_hardness. The quantum version inherits this and more — it is NP-hard to compute and even to approximate @kapshikar_2022_hardness @grigorescu_2025_hardness, while *degeneracy* makes the related optimal-decoding problem #box[\#P]-complete @iyer_2013_hardness. As hardware groups move to high-rate qLDPC codes with hundreds to thousands of qubits, certifying their distance has become a live bottleneck rather than a textbook exercise.

Working in the symplectic representation, each Pauli maps to a length-$2n$ binary vector $(x|z)$, stabilizers form a check matrix $H$, and $d$ is the minimum symplectic weight of a logical operator — a vector $e$ with $H e = 0$ but $L e != 0$ @hernando_2024_fast @webster_2026_distance. What distinguishes the field is the resulting *split by guarantee* (@fig-arch): *exact* methods certify $d$ by squeezing matching lower and upper bounds together but cost exponentially; *heuristic* methods only ever exhibit a light logical operator, returning an upper bound with quantified confidence. Every approach below sits on one side of this line.

#v(0.4em)
#figure(
  grid(
    columns: (30%, 6%, 30%, 6%, 28%),
    align: horizon,
    rect(width: 100%, inset: 8pt, radius: 5pt, fill: rgb("eef2ff"), stroke: rgb("3b5bdb"))[
      #set text(size: 8.5pt)
      *Input* \ Code $[[n,k,d]]$ as check matrix $H$, logicals $L$. Goal: min-weight $e$ with $H e = 0$, $L e != 0$.
    ],
    align(center)[#text(size: 7.5pt, weight: "bold")[NP-hard] \ #text(13pt)[→]],
    rect(width: 100%, inset: 8pt, radius: 5pt, fill: rgb("e6f4ea"), stroke: rgb("1e7e34"))[
      #set text(size: 8.5pt)
      *Exact — certified $d$* \ Brouwer–Zimmermann, SAT/MIP, connected-cluster. Bounds meet ⟹ proof. _Exponential._
    ],
    align(center)[#text(13pt)[/]],
    rect(width: 100%, inset: 8pt, radius: 5pt, fill: rgb("fdf2e9"), stroke: rgb("d97706"))[
      #set text(size: 8.5pt)
      *Heuristic — upper bound* \ QDistRnd/QDistEvol, BP-OSD, Stim, annealing. Finds a light logical ⟹ $d <= "UB"$.
    ],
  ),
  caption: [One problem, two solution families with fundamentally different guarantees.],
) <fig-arch>

= Technical Approaches

The lineage runs from classical hardness foundations to quantum-specific tooling (@fig-timeline). Six method families are in active use; the first three certify $d$, the last three return upper bounds. A cross-approach summary closes the section.

#figure(
  cetz.canvas(length: 1cm, {
    import cetz.draw: *
    let y = 0
    line((0, y), (15.4, y), mark: (end: "straight"), stroke: 1pt)
    let ms = (
      (0.4, "1978", "Decoding\nNP-complete", true, rgb("#3b5bdb")),
      (2.0, "1997", "Min-dist\nNP-hard", false, rgb("#3b5bdb")),
      (3.6, "2003", "Approx.\nhardness", true, rgb("#3b5bdb")),
      (5.2, "2013", "#P-complete\ndecoding", false, rgb("#3b5bdb")),
      (6.8, "2013", "Linked\ncluster", true, rgb("#1e7e34")),
      (8.4, "2021", "BP-OSD\nqLDPC", false, rgb("#1e7e34")),
      (10.0, "2022", "Quantum\ndist NP-hard", true, rgb("#3b5bdb")),
      (11.6, "2024", "40× sympl.\nBZ", false, rgb("#1e7e34")),
      (13.2, "2025", "CSS approx\nhardness", true, rgb("#3b5bdb")),
      (14.8, "2026", "Benchmark\n+ QDistEvol", false, rgb("#1e7e34")),
    )
    for (mx, yr, lbl, above, col) in ms {
      circle((mx, y), radius: 0.12, fill: col, stroke: none)
      let ly = if above { 0.55 } else { -0.55 }
      let anch = if above { "south" } else { "north" }
      content((mx, ly), anchor: anch, box(width: 1.5cm)[
        #set text(size: 6.5pt)
        #align(center)[#text(weight: "bold", col)[#yr] \ #lbl]
      ])
    }
  }),
  caption: [Field landscape. Blue = complexity/hardness results; green = algorithms and tooling.],
) <fig-timeline>

== Exact enumeration: Brouwer–Zimmermann

*What it is.* Build several (partial) information sets by repeated reduced row-echelon form on the generator matrix over disjoint column blocks, then enumerate weight-$t$ row combinations of each systematic generator for increasing $t$. Each information set yields a lower bound on the weight of not-yet-seen codewords; when the summed lower bound reaches the lightest codeword found, the search is *certified complete* @webster_2026_distance @hernando_2016_algorithm. The stabilizer version computes the symplectic weight of the normalizer matrix @hernando_2024_fast.

*State of the art.* The fastest implementation is the symplectic Brouwer–Zimmermann of Hernando–Quintana-Ortí–Grassl, *up to $40 times$ faster than Magma* and turning "days into seconds" on shared-memory multicore @hernando_2024_fast; its classical predecessor is ACM Algorithm 994 @hernando_2016_algorithm. Magma's proprietary BZ remains the strongest exact baseline on small non-CSS codes (98.7% solved within 8 h in the 2026 benchmark) @webster_2026_distance.

#proscons(
  list(
    [Certifies $d$ with a proof, not just a bound @webster_2026_distance.],
    [Even/doubly-even weight jumps and Gray-code enumeration accelerate termination @webster_2026_distance.],
    [Mature, openly available high-performance implementations @hernando_2024_fast @hernando_2016_algorithm.],
  ),
  list(
    [Exponential cost; times out on large lifted-product / bivariate-bicycle codes @webster_2026_distance.],
    [The strongest baseline (Magma) is proprietary and cannot separate $X$/$Z$ distance @webster_2026_distance @ismail_2024_quantum.],
  ),
)

== Constraint solvers: SAT and MIP

*What it is.* Encode "minimum-weight $e$ with $H e = 0$ and $L e != 0$" directly for an off-the-shelf solver. MaxSAT uses soft clauses to penalize each error bit and Tseitin-encoded XOR clauses for the parity constraints; mixed-integer programming minimizes Hamming weight subject to mod-2 constraints expressed with integer slack variables @webster_2026_distance.

*State of the art.* In the 2026 benchmark, MIP (Gurobi) is the best *exact* method for bivariate-bicycle and quantum-Tanner codes — precisely the high-rate families where cluster search and BZ time out — and found the lowest distance on 4 of 7 of the hardest bivariate-bicycle *circuits* @webster_2026_distance. The 2-block symplectic encoding outperforms the 3-block one for Gurobi @webster_2026_distance.

#proscons(
  list(
    [Certified, and inherits decades of solver engineering @webster_2026_distance.],
    [Solves structured high-rate codes that other exact methods cannot finish @webster_2026_distance.],
  ),
  list(
    [Exponential in the number of integer variables @webster_2026_distance.],
    [Orders of magnitude slower than BZ on small codes (Gurobi $tilde 6.7 times 10^3$ s vs Magma $tilde 31$ s) @webster_2026_distance.],
    [On the hardest families it completes only the smallest members within 8 h @webster_2026_distance.],
  ),
)

== Connected-cluster search

*What it is.* The support of a minimum-weight codeword forms a single connected cluster on the Tanner-derived graph, so only growing *connected* clusters need be enumerated by breadth-first search — exponentially fewer candidates than generic weight-$w$ errors @kovalev_2013_linked @dumer_2014_numerical.

*State of the art.* It is the fastest *exact* method on hyperbolic-surface and colour CSS codes — clearing all 21 surface codes in $1.0$ s versus $2.2 times 10^5$ s for Magma — and its cost exponent is *linear* in the relative distance @webster_2026_distance @kovalev_2013_linked.

#proscons(
  list(
    [Cost linear in relative distance; exploits LDPC sparsity @kovalev_2013_linked @dumer_2014_numerical.],
    [Beats other deterministic methods at small relative distance and random-window at high rate @kovalev_2013_linked @dumer_2014_numerical.],
    [Certified, and the fastest exact route on surface/colour codes @webster_2026_distance.],
  ),
  list(
    [Cluster count explodes with Tanner-graph degree; times out on bivariate-bicycle codes @webster_2026_distance.],
    [The C implementation yields no partial lower bound if terminated early @kovalev_2013_linked @webster_2026_distance.],
  ),
)

== Probabilistic and evolutionary sampling: QDistRnd / QDistEvol

*What it is.* A random column permutation followed by RREF surfaces a low-weight logical operator; iterating tightens the upper bound. QDistRnd is the random-window form; QDistEvol replaces random restarts with a genetic search over permutations driven by a continuous (minimum-weight, average-weight) fitness @pryadko_2022_qdistrnd @webster_2024_engineering.

*State of the art.* QDistRnd is the de-facto-standard GAP package, with a quantified failure probability $P_"fail" < e^(-chevron.l n chevron.r)$ from repeat counts @pryadko_2022_qdistrnd. The evolutionary QDistEvol is the clear winner on high-rate qLDPC in the 2026 benchmark: lowest distance on 13/20 bivariate-bicycle codes (vs 8/20 for QDistRnd and BP-OSD) and 19/19 lifted-product codes; on a 756-qubit code its per-trial success is $tilde 50$–$60%$ against $tilde 2%$ for plain QDistRnd @webster_2026_distance @webster_2024_engineering.

#proscons(
  list(
    [Scales to thousands of qubits where exact search is hopeless @webster_2026_distance @pryadko_2022_qdistrnd.],
    [Quantified failure probability from repeated low-weight finds @pryadko_2022_qdistrnd.],
    [QDistEvol gives the best accuracy and throughput on qLDPC codes @webster_2026_distance.],
  ),
  list(
    [Upper bound only — never proves no lighter logical exists @pryadko_2022_qdistrnd @webster_2026_distance.],
    [Highly sensitive to representation/permutation (a $[[48,5,10]]$ code went $0% arrow.r 100%$ after DEM permutation + stabilizer mixing) @webster_2026_distance.],
    [QDistEvol needs structure: only $tilde 27%$ success on unstructured code-table codes @webster_2026_distance.],
  ),
)

== Decoder- and circuit-based search: BP-OSD and Stim

*What it is.* Pick a random non-trivial logical, then decode the syndrome that is zero on checks but anti-commutes with it; belief-propagation + ordered-statistics decoding (BP-OSD) returns a low-weight logical operator. Stim instead searches the *detector error model* of a full syndrome-extraction circuit for an undetectable logical error, giving the *circuit-level* distance @panteleev_2019_degenerate @gidney_2021_stim @webster_2026_distance.

*State of the art.* BP-OSD was established to estimate distances of generalized-bicycle qLDPC codes @panteleev_2019_degenerate. Stim analyzes a distance-100 surface-code circuit (20k qubits, 8M gates) in $tilde 15$ s, and its graphlike-error search is *exact* whenever every error flips at most two detectors @gidney_2021_stim @webster_2026_distance.

#proscons(
  list(
    [The only practical route to *circuit-level* distance, what governs real experiments @gidney_2021_stim @webster_2026_distance.],
    [Stim's graphlike search is exact for string-like errors (e.g. surface codes) @webster_2026_distance.],
    [BP-OSD is competitive on very sparse, large CSS codes @webster_2026_distance.],
  ),
  list(
    [Upper bound only outside the graphlike-exact regime @webster_2026_distance.],
    [BP-OSD never clearly beat plain random-information-set sampling on any benchmark dataset @webster_2026_distance.],
    [BP convergence is hampered by length-4 loops in qLDPC Tanner graphs @kovalev_2013_linked @panteleev_2019_degenerate.],
  ),
)

== Optimization metaheuristics: annealing / QUBO and quantum ISD

*What it is.* Recast the minimum-distance problem as a QUBO (with only logarithmic multiplicative overhead in variables for the mod-2 arithmetic) and solve it on a quantum annealer, hybrid solver, or by simulated annealing @ismail_2024_quantum; or use quantum-walk-accelerated information-set decoding to search for low-weight codewords @kachigar_2017_quantum.

*State of the art.* The QUBO/annealing approach is "competitive, on par with the best classical QUBO solvers" but still lags the best *deterministic* distance algorithms @ismail_2024_quantum; quantum ISD lowers the asymptotic exponent for finding low-weight codewords of random linear codes @kachigar_2017_quantum. This family is the least mature — promising but not yet a production tool.

#proscons(
  list(
    [Only logarithmic variable overhead in the QUBO encoding @ismail_2024_quantum.],
    [May ride future quantum-hardware scaling @ismail_2024_quantum; quantum ISD has a proven asymptotic speedup @kachigar_2017_quantum.],
  ),
  list(
    [Upper bound only, with no optimality certificate @ismail_2024_quantum.],
    [Currently lags the best deterministic methods; the advantage may vanish at scale @ismail_2024_quantum.],
    [Quantum ISD presumes fault-tolerant hardware that does not yet exist @kachigar_2017_quantum.],
  ),
)

== Shared infrastructure

Cutting across the approaches: Stim supplies the fast stabilizer simulation and detector-error-model machinery many circuit-level methods build on @gidney_2021_stim; the Munich Quantum Toolkit bundles code-analysis utilities @wille_2024_mqt; and best-known-distance references come from Grassl's `codetables.de` and quantum-code databases @aydin_2021_database, which are how any computed bound is checked against the literature.

== At-a-glance comparison

#compare_table((
  [Brouwer–Zimmermann], [Small–medium $n$ @hernando_2024_fast], [Certified; exponential @webster_2026_distance], [Mature @hernando_2024_fast], [Small non-CSS codes, code tables @webster_2026_distance],
  [SAT / MIP], [Moderate, structured @webster_2026_distance], [Certified; exponential @webster_2026_distance], [Maturing @webster_2026_distance], [High-rate qLDPC where cluster/BZ time out @webster_2026_distance],
  [Connected-cluster], [Linear in $d$, degree-sensitive @kovalev_2013_linked], [Certified @webster_2026_distance], [Mature @webster_2026_distance], [Sparse LDPC, surface/colour codes @webster_2026_distance],
  [QDistRnd / QDistEvol], [Thousands of qubits @webster_2026_distance], [Upper bound; $P_"fail"$ @pryadko_2022_qdistrnd], [Mature @pryadko_2022_qdistrnd], [High-rate qLDPC (QDistEvol wins) @webster_2026_distance],
  [BP-OSD / Stim], [Very large / circuits @gidney_2021_stim], [Upper bound (Stim exact if graphlike) @webster_2026_distance], [Mature @gidney_2021_stim], [Circuit-level distance, very sparse checks @webster_2026_distance],
  [Annealing / ISD], [Emerging @ismail_2024_quantum], [Upper bound; no certificate @ismail_2024_quantum], [Experimental @kachigar_2017_quantum], [Research; future hardware @ismail_2024_quantum],
))

= Open Problems

The open problems descend from one root — NP-hardness — into the practical bottlenecks (@fig-deps).

#figure(
  cetz.canvas(length: 1cm, {
    import cetz.draw: *
    let node(pos, name, label, col) = {
      rect((pos.at(0) - 1.1, pos.at(1) - 0.45), (pos.at(0) + 1.1, pos.at(1) + 0.45),
        name: name, fill: col.lighten(75%), stroke: col + 1pt, radius: 3pt)
      content((pos.at(0), pos.at(1)), box(width: 2cm)[#set text(size: 6.8pt); #align(center)[#label]])
    }
    node((0, 0), "hard", [NP-hardness\ of distance], rgb("#b00020"))
    node((-3.2, -2), "scale", [Exact methods\ don't scale], rgb("#b00020"))
    node((3.2, -2), "ub", [Heuristics give\ upper bounds only], rgb("#d97706"))
    node((-3.2, -4), "circ", [Circuit distance\ #sym.gt.eq code distance], rgb("#d97706"))
    node((0, -4), "qldpc", [qLDPC two-sided\ bounds open], rgb("#3b7dd8"))
    node((3.2, -4), "ml", [No learned\ estimator], rgb("#3b7dd8"))
    line("hard.south", "scale.north", mark: (end: "straight"))
    line("hard.south", "ub.north", mark: (end: "straight"))
    line("scale.south", "circ.north", mark: (end: "straight"))
    line("scale.south", "qldpc.north", mark: (end: "straight"))
    line("ub.south", "qldpc.north", mark: (end: "straight"))
    line("ub.south", "ml.north", mark: (end: "straight"))
  }),
  caption: [Problem dependencies. Red = critical, orange = high, blue = medium urgency.],
) <fig-deps>

#v(0.4em)
#problem_table((
  [1], [Exact distance at scale @webster_2026_distance @hernando_2024_fast],
  [No certified method finishes within 8 h for large lifted-product / bivariate-bicycle codes — exactly those being built for hardware.],
  [Better SAT/MIP encodings; faster symplectic BZ; partial-LB cluster search (Webster, Grassl, Higgott).], [#crit],
  [2], [Upper-bound-only heuristics @webster_2026_distance @pryadko_2022_qdistrnd],
  [Every scalable method can silently overstate $d$; a wrong $d$ undermines the code's fault-tolerance guarantee.],
  [Confidence-bounded sampling beyond QDistRnd's $P_"fail"$; certified hybrids (Pryadko, UCL).], [#crit],
  [3], [Circuit vs code distance @webster_2026_distance @gidney_2021_stim],
  [Detector-error models are $tilde 100 times$ larger than check matrices; circuit distance is what governs experiments.],
  [Scalable DEM-aware search (Google Quantum AI / Stim; UCL `codeDistance`).], [#high],
  [4], [Square-root approximation gap @grigorescu_2025_hardness @kapshikar_2022_hardness],
  [No hardness known for additive gap $tau n^epsilon$ with $1 slash 2 < epsilon <= 1$; a conjectured "$sqrt(n)$ barrier" limits reductions.],
  [Complexity theory (Grigorescu, Guruswami, Kapshikar groups).], [#high],
  [5], [Two-sided qLDPC bounds @dumer_2014_numerical @panteleev_2019_degenerate],
  [Numerical methods give upper bounds, expansion arguments give lower bounds; closing the gap is still case-by-case.],
  [Coding theorists on bivariate-bicycle / APM-LDPC families @kasai_2026_heuristic @delfosse_2014_note.], [#med],
  [6], [No learned distance estimator @webster_2024_engineering],
  [ML is used for decoding and code discovery but not for estimating $d$ — a possible fast-screening gap.],
  [ML-for-QEC groups; open opportunity.], [#med],
))

#v(0.7em)
#section_box(
  [Bottom line],
  [No single method dominates. For *certified* distance, pick by structure: Brouwer–Zimmermann (Magma or the $40 times$ symplectic implementation) on small non-CSS codes @hernando_2024_fast, connected-cluster on surface/colour codes, and MIP on high-rate families where the others time out @webster_2026_distance. For codes too large to certify — the qLDPC regime hardware actually targets — the evolutionary QDistEvol is the current best *upper-bound* tool, with Stim for circuit-level distance @webster_2026_distance @gidney_2021_stim. The standing caveat is that every scalable method returns an upper bound, so a reported $d$ on a large code is a working estimate, not a proof @pryadko_2022_qdistrnd @webster_2026_distance.],
  fill: rgb("eef6ef"), stroke: rgb("bcd9c4"),
)

#v(0.5em)
#text(8.5pt, style: "italic")[Sources: 25-reference knowledge base built by `/survey` on 2026-06-09. Three pre-arXiv IEEE classics (Berlekamp 1978, Vardy 1997, Dumer 2003) are cited from metadata; all others are grounded in rendered full text. The central comparative source is the Webster–Jacob–Higgott 2026 benchmark @webster_2026_distance.]

#bibliography("2026-06-09-quantum-code-distance-review.bib", title: "References", style: "ieee")
