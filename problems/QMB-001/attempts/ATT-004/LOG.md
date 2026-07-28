# ATT-004 - Residual-seeded local search

Example data - synthetic results for interface demonstration only.

## Public Contract Smoke

passed

## Containment

passed

## Development Metrics

- runs: 24
- verified witnesses: 24/24
- target hits: 22
- timeouts: 0
- crashes: 0
- invalid claims: 0
- normalized quality: 0.970
- runtime: 39.8 s
- p95: 3.8 s
- speedup: 45.7x

## Decision

accepted

## Learning Carried Forward

- Seeding is more valuable than adding more restarts.
- The accepted core can be wrapped in a portfolio scheduler.
- Promotion should require perfect synthetic target hits.
