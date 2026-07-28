# Rotated Surface Code

A surface-code variant with a rotated lattice layout that reduces physical-qubit count for the same code distance.

## Family, Aliases, and Kind

- `family`: `surface-code`
- `aliases`: rotated planar code
- `kind`: `code_variant`

## Construction

- `type`: `topological_css`
- Defined on a rotated square lattice with boundary choices that preserve one logical qubit while compressing the layout.

## Parameter Formulas

- `logical_qubits`: typically 1
- `distance_formula`: d
- `block_length_formula`: 2d^2 - 1

## Assumptions

- 2D nearest-neighbor geometry
- stabilizer measurements available

## Known Decoders

- MWPM
- Union-Find

## Distance Methods

- analytical from geometry

## Relations

- `variant_of` -> `surface-code`

## Linked Evidence

No linked evidence yet.

## Generated Instances

- `rotated-surface-code-d3` — n=9, mx=4, mz=4, distance=3
- `rotated-surface-code-d5` — n=25, mx=12, mz=12, distance=5
- `rotated-surface-code-d7` — n=49, mx=24, mz=24, distance=7
- `rotated-surface-d3-example` — n=9, mx=4, mz=4, distance=3
- `rotated-surface-d5-example` — n=25, mx=12, mz=12, distance=5
- `rotated-surface-d7-example` — n=49, mx=24, mz=24, distance=7

## Source Papers

- None
