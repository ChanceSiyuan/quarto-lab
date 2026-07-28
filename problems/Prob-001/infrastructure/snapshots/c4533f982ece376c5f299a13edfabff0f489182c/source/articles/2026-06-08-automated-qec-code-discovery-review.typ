#set page(margin: 1.6cm)
#set text(size: 10pt)
#set par(justify: true, leading: 0.62em)
#set heading(numbering: "1.")

#let title = [Automated Discovery of Quantum Error-Correcting Codes]
#let authors = [AutoQEC review draft]

#show link: set text(fill: blue.darken(30%))

#let section_box(title, body, fill: rgb("f7f8fc"), stroke: rgb("d9deeb")) = rect(
  width: 100%,
  inset: 10pt,
  radius: 6pt,
  fill: fill,
  stroke: stroke,
  [#strong[#title] #v(0.3em) #body],
)

#let stage(name, body, fill) = rect(
  width: 100%,
  inset: 7pt,
  radius: 5pt,
  fill: fill,
  stroke: rgb("c7cfe0"),
  align(center)[#text(weight: "semibold", size: 9pt)[#name] #v(0.2em) #text(size: 8pt)[#body]],
)

#let proscons(pros, cons) = grid(
  columns: (1fr, 1fr),
  gutter: 0.6em,
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
  columns: (20%, 18%, 22%, 16%, 24%),
  stroke: (x, y) => if y == 0 { 0.8pt + black } else { 0.4pt + rgb("d7dbe6") },
  inset: 6pt,
  table.header(
    [#strong[Approach]], [#strong[Scalability]], [#strong[Verifiability / cost]], [#strong[Maturity]], [#strong[Best-fit use case]],
  ),
  ..rows,
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

#heading(numbering: none)[#title]

#align(center)[
  #text(size: 12pt, weight: "semibold")[State-of-the-Art Review]
  #v(0.25em)
  #text(fill: gray.darken(20%))[#authors]
  #v(0.25em)
  #text(fill: gray.darken(10%))[Generated 2026-06-08 from the AutoQEC knowledge base (51-reference survey).]
]

#v(0.9em)

#section_box(
  [Scope],
  [
    This report assesses #strong[automated / algorithmic discovery of quantum error-correcting (QEC) codes]: methods that search, optimize, or learn good codes rather than constructing them by hand. The review is organized #emph[by technical approach]; the state of the art and trade-offs are given inside each approach. It is aimed at internal technical decision-making for the AutoQEC search project, not as a general QEC tutorial. A companion report covers the lifted-product / quantum-Tanner family as a concrete search target.
  ],
)

= What and Why

A quantum error-correcting code encodes logical qubits into more physical qubits so that errors can be detected and corrected. The central practical problem is that #emph[finding] a good code — one with high distance, high rate, sparse low-weight checks, a tractable decoder, and a useful logical-gate structure all at once — is a vast combinatorial search. Hand construction has produced the canonical families (surface, color, bivariate-bicycle, lifted-product), but the space of possibilities is far larger than human enumeration can cover, and the best code for a given noise model or hardware layout is rarely the textbook one @Robertson2017 @Cao2022.

Automated code discovery reframes this as an optimization problem and matters now for three reasons. First, near-term fault tolerance needs strong #emph[finite-length] instances tuned to real noise and connectivity, not just good asymptotic families. Second, candidate generation has become cheap — learned controllers can propose thousands of codes — which shifts the binding constraint onto #emph[validation]: exact distance and equivalence checking now dominate the cost @Hernando2026 @Webster2026 @Khesin2024. Third, the same machinery now reaches code classes that resist hand construction, including non-CSS, approximate, and dissipative codes @Khesin2026 @Liu2025 @Wang2022.

What makes this different from hand construction is the locus of effort. Manual work proves a family has good asymptotic parameters; automated discovery instead invests in #emph[shrinking and shaping the search space] so a generic optimizer finds strong finite instances, and in #emph[evaluating candidates fast enough] to keep the loop running. Across the literature the recurring workflow is the same five stages below; the approaches in §3 differ mainly in how they implement stage 3.

#v(0.5em)
#figure(
  grid(
    columns: (19%, 3%, 19%, 3%, 19%, 3%, 19%, 3%, 11%),
    align: center + horizon,
    stage([1. Represent], [family prior / ansatz / graph / tensor net], rgb("eef3ff")),
    align(center + horizon)[#text(size: 14pt)[→]],
    stage([2. Objective], [distance, rate, bias, decoder, gates], rgb("eef3ff")),
    align(center + horizon)[#text(size: 14pt)[→]],
    stage([3. Generate], [RL / evolve / variational / Bayesian / LLM], rgb("e9f7ee")),
    align(center + horizon)[#text(size: 14pt)[→]],
    stage([4. Validate], [proxy → exact distance / equivalence], rgb("fdf2e9")),
    align(center + horizon)[#text(size: 14pt)[→]],
    stage([5. Prune], [no-go + canonical forms], rgb("fbecec")),
  ),
  caption: [The automated QEC code-discovery loop. The approaches in §3 differ chiefly in stage 3; stage 4 is the shared throughput bottleneck and stage 5 feeds structure theorems back as constraints.],
)

= Technical Approaches

The field has moved through three eras: #strong[representation engineering] (1997–2011), where the win came from searching in a better coordinate system; #strong[noise-aware design] (2017–), where realistic channels became routine search inputs; and the current era of #strong[learned controllers and algebraic family mining] (2022–2026), where RL, surrogate models, and even LLM-guided program evolution wrap around classical exact validators. The six approaches below are roughly ordered by that lineage, followed by the cross-cutting validation infrastructure they all depend on.

#v(0.4em)
#figure(
  grid(
    columns: (31%, 3%, 28%, 3%, 35%),
    align: center + horizon,
    stage([1997–2011], [Representation engineering: CWS, subsystem search], rgb("eef3ff")),
    align(center + horizon)[#text(size: 13pt)[→]],
    stage([2017–], [Noise- and hardware-aware design], rgb("eef6ef")),
    align(center + horizon)[#text(size: 13pt)[→]],
    stage([2022–2026], [Learned controllers (RL / variational / Bayesian / LLM) + algebraic family mining], rgb("fdf2e9")),
  ),
  caption: [Field landscape: the searched object widened from "the code" to "code + encoder + circuit + layout," and the generator became a learned controller around exact validators.],
)

== Representation-constrained combinatorial search

*What it is.* Recast discovery as a structured search in a better coordinate system rather than over raw stabilizer tableaux: codeword-stabilized (CWS) graph states with induced classical error patterns and clique-style reductions, or subsystem codes parameterized by physically allowed measurement operators.

*State of the art.* The CWS framework turned code discovery into graph/clique search and produced both new codes and non-existence results such as the absence of a `((7,3,3))` CWS code @Cross2009 @Chuang2009; the first nonadditive code beating the best additive code established that the stabilizer ansatz is too narrow @Rains1997; subsystem-code search optimizes over measurement operators directly @Crosswhite2011.

#proscons(
  list([Exposes codes additive/stabilizer search misses @Rains1997.], [Same machinery yields existence #emph[and] impossibility results @Chuang2009.]),
  list([Strongly representation-dependent; needs symmetry reduction first @Chuang2009.], [Combinatorial blow-up confines it to small `n`.]),
)

== Reinforcement learning

*What it is.* An agent incrementally composes or edits a code — often jointly with its encoder, gate set, and connectivity — under a reward such as the Knill–Laflamme conditions or logical error rate, with the noise and hardware model in the loop.

*State of the art.* Joint code+encoder discovery scales to 20 qubits / distance 5 via a vectorized Clifford simulator @Olle2024; the Quantum-Lego line saturates the CSS linear-programming bound on 13 qubits and finds best-known biased-noise codes near 20 qubits, now with a device-in-the-loop hybrid @Su2025 @Yanay2026; tensor-network RL beats random search by ~65× @Mauron2024; RL also performs stabilizer weight reduction (1–2 orders of magnitude overhead saving) @He2025, fault-tolerant state-prep circuits @Zen2025, and bosonic autonomous codes @Yin2025.

#proscons(
  list([Searches code + encoder + circuit jointly @Olle2024.], [Folds noise/hardware constraints directly into the reward @Su2025 @Yanay2026.], [Strong empirical results to ~20 qubits.]),
  list([Sensitive to reward design and simulator throughput @Olle2024.], [Train/deploy noise mismatch; sample-expensive @Webster2025.], [Optimality is hard to certify.]),
)

== Evolutionary and genetic search

*What it is.* Encode codes or stabilizer circuits as genomes (binary strings, circuit programs), then mutate, recombine, and select on a distance- or performance-based fitness.

*State of the art.* A binary-string genome matches codetables.de distance for `n <= 20`, gains on biased noise, and contributes the QDistEvol distance heuristic @Webster2025; circuit evolution rediscovers codes equivalent to the 5-qubit perfect code, Shor's code, and the 7-qubit color code @Tandeitnik2024.

#proscons(
  list([Simple and competitive with RL at small–medium `n` @Webster2025.], [Naturally couples generation to a distance evaluator @Webster2025.]),
  list([Fitness = repeated distance evaluation, the dominant cost @Webster2025.], [Representation and scaling limits keep it to small codes.]),
)

== Variational, gradient, and surrogate optimization

*What it is.* Make code synthesis differentiable or surrogate-driven: turn the Knill–Laflamme conditions into a variational loss, parameterize codewords on a manifold and follow gradients, or train a model that predicts logical error rate without simulation.

*State of the art.* VarQEC (re)discovers symmetric/asymmetric codes and new non-stabilizer `((6,2,3))` / `((7,2,3))` codes @Cao2022; distinguishability-loss training learns noise-tailored encoders demonstrated on IBM and IQM hardware @Meyer2025; graphical VGQEC interpolates between code families @Shao2026; learned concatenation @Meyer2026 and ML-inspired approximate amplitude-damping codes @Liu2025 extend the frontier; Stiefel-manifold Riemannian optimization @Casanova2025 and Wirtinger-gradient codeword optimization @Seksaria2025 cover the gradient route; a Bayesian-optimization loop with a chain-complex neural surrogate discovers competitive `[[144,36]]` and `[[144,16]]` bivariate-bicycle codes without simulation @Chengyu2026.

#proscons(
  list([Surrogates / differentiability attack the per-candidate evaluation cost @Chengyu2026 @Casanova2025.], [Reaches approximate and noise-adaptive codes @Liu2025 @Cao2022.], [Demonstrated on real hardware @Meyer2025.]),
  list([Surrogate predictions still need exact confirmation @Chengyu2026.], [Approximate codes lack clean `[[n,k,d]]` certification @Liu2025.], [Gradient methods are sensitive to initialization and penalties @Seksaria2025.]),
)

== Algebraic family mining

*What it is.* Fix a structured family — bivariate / multivariate bicycle, two-block group-algebra, lifted-product — and search its parameters with strong algebraic priors and exact validation; the generator is increasingly an LLM or program-evolution loop.

*State of the art.* Coprime bivariate-bicycle codes with explicit cold-atom layouts @Wang2026; LLM-guided evolutionary search over BB-generating programs with a certify-and-deduplicate pipeline @CruzBenito2026; BB sequences from covering graphs @Symons2025; multivariate @Voss2025 and trivariate @Galimova2026 @Jacob2025 generalizations; a multivariate-multicycle unification with complete single-shot decoding @Mian2026; the two-block group-algebra formalization @Wang2023 and non-CSS "mirror" codes @Khesin2026; short transversal-friendly codes @Jain2025; and finite-length distance results for lifted-product / lifted-Tanner families @Postema2025 @Guemard2025 @Raveendran2025.

#proscons(
  list([Exact-verifiable, hardware-mappable, moderate-length (`n` in the 100s) instances @Wang2026 @Mian2026.], [Rich algebraic structure keeps both search and decoding tractable @Mian2026.]),
  list([Some families are provably asymptotically bad @Postema2025.], [Risk of overfitting to algebraically pleasant dead ends.], [Logical-gate structure vs. finite-length distance is often a trade @Postema2025.]),
)

== Autonomous and open-system discovery

*What it is.* Optimize the dissipative code-plus-control object — code subspace, induced decay rates, and control Hamiltonian — directly against a physical Lindbladian, rather than a static code subspace.

*State of the art.* Adjoint-optimization search discovers autonomous bosonic codes such as the $sqrt(3)$ code with a hardware-efficient superconducting implementation @Wang2022; a full open-system search over code space, decay rates, and control finds codes that beat the binomial code on perturbed systems @Ashhab2026.

#proscons(
  list([Targets the real dissipative object, not just the static code @Wang2022.], [Hardware-efficient bosonic results @Wang2022.]),
  list([Physics-model-specific; expensive open-system simulation @Ashhab2026.], [Immature decoder / fault-tolerance story.], [Narrow scope (bosonic / autonomous) so far.]),
)

== Cross-cutting: validation, equivalence, and pruning

*What it is.* Not a discovery method but the shared backend every approach above depends on: exact and heuristic distance computation, equivalence canonicalization for deduplication, theorem-based pruning, and community libraries / databases.

*State of the art.* Distance tooling spans QDistRnd @Pryadko2022, fast exact Brouwer–Zimmermann @Hernando2026, the codeDistance benchmark of exact and heuristic methods @Webster2026, Monte-Carlo upper bounds @Liang2024, and QUBO/annealing formulations @Ismail2024; ZX-calculus canonical forms enable deduplication @Khesin2024; classification and no-go theorems prune whole regions @Haah2021 @Chuang2009 @Postema2025; and the qLDPC library @Perlin2024, SSIP @Cowtan2024, quantumcodes.info @Aydin2022, and the Error Correction Zoo @Albert2022 provide shared infrastructure, with a comprehensive AI-for-QEC review @Wang2024 and SMT/Coq verification @Huang2025 bracketing the field.

#proscons(
  list([Turns "looks good" into "is good"; canonical forms deduplicate @Hernando2026 @Khesin2024.], [Theorems prune whole regions before any search runs @Haah2021.]),
  list([Exact distance / equivalence is the throughput bottleneck once generation is cheap @Webster2026.], [Few no-go theorems are expressed as machine-checkable constraints @Haah2021.]),
)

== At-a-glance comparison

#compare_table((
  [Representation / combinatorial], [Small `n`], [Exact, but blows up @Chuang2009], [Mature concept], [Small exceptional codes; impossibility results],
  [Reinforcement learning], [~20 qubits @Olle2024], [Empirical; costly to certify], [Active, early], [Code + encoder + circuit, noise-tailored],
  [Evolutionary / genetic], [Small–medium `n` @Webster2025], [Fitness = distance eval], [Active, early], [Small biased-noise codes],
  [Variational / gradient / surrogate], [Surrogate scales @Chengyu2026], [Needs exact confirmation], [Active, early], [Approximate / noise-adaptive; qLDPC surrogates],
  [Algebraic family mining], [Moderate `n` (100s) @Wang2026], [Exact-verifiable @Mian2026], [Maturing], [Hardware-mappable LDPC memories],
  [Autonomous / open-system], [Few modes @Ashhab2026], [Physics-sim costly], [Early], [Bosonic / dissipative hardware codes],
))

= Open Problems

#problem_table((
  [1],
  [Scale exact validation],
  [Distance, equivalence, and logical-gate checking dominate cost once candidate generation is cheap, capping every search loop's throughput],
  [Distance-algorithm + equivalence groups (Hernando, Webster, Khesin)],
  [#text(fill: red.darken(10%))[Critical]],

  [2],
  [Unified multi-objective scoring],
  [No single objective jointly scores code parameters, encoder complexity, decoder compatibility, and logical-gate structure, so methods optimize one axis and regress on others],
  [Method groups building the search loops (RL / variational / Bayesian)],
  [#text(fill: red.darken(10%))[Critical]],

  [3],
  [Shared finite-length benchmarks],
  [Without common tasks, RL, variational, Bayesian, and combinatorial methods cannot be compared, so progress claims are not commensurable],
  [Community / benchmark maintainers (codeDistance, code zoo)],
  [#text(fill: orange.darken(20%))[High]],

  [4],
  [Family priors: broad yet tractable],
  [Priors must admit surprises while preserving algebraic structure that keeps validation feasible; too narrow misses codes, too broad stalls],
  [Algebraic-family + LLM-search groups (IBM, Chengyu)],
  [#text(fill: orange.darken(20%))[High]],

  [5],
  [Operationalize no-go theorems],
  [Impossibility and classification results could prune the search space but are rarely expressed as explicit machine-checkable constraints],
  [Theory groups (Haah; Postema; CWS line)],
  [#text(fill: olive.darken(10%))[Medium]],

  [6],
  [Extend cleanly beyond CSS stabilizers],
  [Non-CSS, approximate / noise-adaptive, and dissipative classes need decoders and FT gadgets to match their code-discovery progress],
  [Khesin; Liu; Ashhab / autonomous-QEC groups],
  [#text(fill: olive.darken(10%))[Medium]],
))

#v(0.8em)

#section_box(
  [Bottom line for AutoQEC],
  [
    The field's center of gravity has shifted from "find a new code somewhere" to "find the best code inside a constrained family that matches a noise model, hardware model, and verification budget." The most successful workflows combine a structured representation or family prior, a fast proxy plus an exact validator, and a theorem-backed pruning rule. For a search project the highest-leverage investment is not a cleverer generator but a faster, broader #strong[validator] — exact distance, equivalence, and logical-gate detection — since that is now the throughput bottleneck. Distilled in one sentence: #emph[progress usually comes from reducing the search space more intelligently than the objective space] @Cross2009 @Hernando2026 @Webster2026 @Postema2025.
  ],
  fill: rgb("eef6ef"),
  stroke: rgb("bcd9c4"),
)

#v(0.6em)

#bibliography("2026-06-08-automated-qec-code-discovery-review.bib", title: "References", style: "ieee")
