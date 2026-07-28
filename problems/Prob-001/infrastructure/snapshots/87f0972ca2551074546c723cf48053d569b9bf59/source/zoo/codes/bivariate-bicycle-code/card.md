# Bivariate Bicycle Code

A qLDPC code family built from pairs of bivariate circulant polynomials.

## Family, Aliases, and Kind

- `family`: None
- `aliases`: BB code
- `kind`: `code_family`

## Construction

- `type`: `qldpc_css`
- Constructed from commuting parity-check matrices derived from bivariate bicycle polynomial data.

## Parameter Formulas

- `logical_qubits`: construction dependent
- `distance_formula`: not fixed in closed form
- `rate_scaling`: family dependent

## Assumptions

- CSS construction
- circulant polynomial input data

## Known Decoders

- belief propagation
- ordered statistics decoding

## Distance Methods

- algorithmic search
- matrix-based lower-bound analysis

## Relations

- None

## Linked Evidence

### BB codes are bivariate bicycle CSS LDPC constructions

- `paper_id`: `2308.07915`
- `claim_type`: `construction_note`
- `statement`: The paper defines BB codes as CSS LDPC codes QC(A,B) built from commuting bivariate shift-matrix polynomials; the resulting family has weight-6 checks and a degree-6 Tanner graph with thickness at most 2.
- `quote_ref`: `fulltext:l183-l205`

### BP-OSD is the decoder used for circuit-level BB simulations

- `paper_id`: `2308.07915`
- `claim_type`: `decoder_claim`
- `statement`: The paper bases its numerical experiments on BP-OSD and extends that decoder from a memory-only toy model to the circuit-based noise model used for BB-code fault-tolerant memory simulations.
- `quote_ref`: `fulltext:l132-l133`

### Table 3 distances and upper bounds for BB instances

- `paper_id`: `2308.07915`
- `claim_type`: `distance_claim`
- `statement`: The paper reports distances for several explicit BB instances and states that these values were computed by a mixed integer programming approach; two larger instances are marked only with upper bounds.
- `quote_ref`: `fulltext:l209-l221`

### Representative finite-length BB constructions from Table 3

- `paper_id`: `2308.07915`
- `claim_type`: `parameter_claim`
- `statement`: The paper lists explicit finite-length BB constructions by giving (l,m) and the defining polynomials A and B for several instances.
- `quote_ref`: `fulltext:l209-l221`

### Pseudo-thresholds reported for 144- and 288-qubit BB codes

- `paper_id`: `2308.07915`
- `claim_type`: `threshold_evidence`
- `statement`: For the circuit-based noise model, Table 1 reports pseudo-thresholds 0.0065 for the [[144,12,12]] BB code and 0.0069 for the [[288,12,18]] BB code, with the surrounding text summarizing both as close to 0.007.
- `quote_ref`: `fulltext:l121-l126;l138`

### BB-code overhead comparison against the surface code at p = 10^-3

- `paper_id`: `2308.07915`
- `claim_type`: `relation_claim`
- `statement`: In the comparison around Figure 2B, the paper states that at p = 10^-3 the [[144,12,12]] BB code can preserve 12 logical qubits for nearly one million syndrome cycles using 288 physical qubits, whereas separate surface-code patches would require nearly 3000 physical qubits.
- `quote_ref`: `fulltext:l148-l150`

### Representative finite-length BB-code parameter points

- `paper_id`: `2408.10001`
- `claim_type`: `parameter_claim`
- `statement`: The paper reports explicit finite-length parameter sets for coprime bivariate bicycle constructions.
- `quote_ref`: `construction:p4:table1`

## Generated Instances

- None

## Source Papers

- `2308.07915`
- `2408.10001`
