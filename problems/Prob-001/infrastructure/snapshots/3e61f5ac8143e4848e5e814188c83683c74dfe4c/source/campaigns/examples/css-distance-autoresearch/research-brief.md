# CSS Distance Autoresearch: Upper-Bound Baseline

## Scope

This task pins an upper-bound-only baseline for finding finite CSS logical
operator witnesses. It is grounded in the distance survey in
`.knowledge/NOTES.md` and its bibliography entries
[@arxiv260322532; @pryadko_2022_qdistrnd; @liang_2024_determining;
@kovalev_2013_linked; @kasai_2026_heuristic]. The pinned implementation is
recorded in `source.json`; this brief does not add a launcher or evaluator.

## Source and reproducibility

The source pin deliberately preserves `license: "MIT"` because the pinned
commit's LICENSE file declares MIT. The same commit's package metadata declares GNUv3.
`source.json` records both statements as a metadata conflict requiring operator
review; the campaign does not conceal or resolve that upstream inconsistency.

The `decoderDist` baseline uses method ID `decoderDist` with its decoder
parameter pinned to `bposd`. Recording this baseline configuration avoids
silently inheriting a different decoder if upstream defaults change.

## Upper-bound methods

The practical upper-bound landscape combines several complementary witness
searches:

- **Random information-set methods.** QDistRnd and the pinned QDistRndMW
  baseline sample or transform information sets to expose low-weight
  codewords/logicals. QDistEvol uses evolutionary search for the same
  witness-finding objective.
- **Decoder residual search.** A decoder residual can be used to propose a
  low-weight logical witness. BP-OSD is a common decoder-based route for this
  purpose, but it remains a heuristic witness generator rather than an exact
  distance certificate.
- **Sparsity-aware clusters.** The connected/linked cluster methods use LDPC
  structure to grow candidate supports and are another upper-bound route.
- **Structure-aware APM witnesses.** For APM-LDPC constructions, quotient,
  lift, and fiber structure can guide witness generation instead of treating
  the parity-check matrices as unstructured binary matrices.

These methods can exhibit a logical operator and therefore establish an
upper-bound on distance. They do not establish that no lower-weight logical
operator exists. Accordingly, this campaign records only upper-bound results;
it must not label them as exact distance.

## Certification gate

Every result is accepted only after independent binary-linear-algebra checks:

1. the proposed operator satisfies the appropriate CSS kernel condition; and
2. it is outside the corresponding stabilizer row-space, completing
   non-stabilizer row-space verification.

The first check rejects non-commuting candidates. The second prevents a
stabilizer from being misreported as a logical operator. Passing these checks
certifies the reported witness as an upper-bound witness, not the minimum
distance.

## Deliberate exclusion

For task 1, exact SAT/MaxSAT is out of scope. Exact methods are valuable for
small and moderate instances, but the research objective here is to establish
a reproducible upper-bound baseline before introducing an exact solver path.
The literature notes that exact distance remains computationally expensive and
that upper-bound methods have non-certifying convergence with respect to the
global minimum [@arxiv260322532; @grigorescu_2025_hardness]. Future work
may compare against exact methods, but must keep exact and upper-bound evidence
separate.
