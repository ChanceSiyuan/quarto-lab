# ATT-002 - Random kernel sampling

Example data - synthetic results for interface demonstration only.

## Public Contract Smoke

passed

## Containment

passed

## Development Metrics

- runs: 24
- verified witnesses: 15/24
- target hits: 12
- timeouts: 0
- crashes: 0
- invalid claims: 4
- normalized quality: 0.500
- runtime: 42.6 s
- p95: 2.9 s
- speedup: 42.7x

## Decision

rejected

## Learning Carried Forward

- A fast proposal stage needs a stronger quotient-space constraint.
- Display invalid claims separately from crashes and misses.
- Do not rank candidates by speed alone.
