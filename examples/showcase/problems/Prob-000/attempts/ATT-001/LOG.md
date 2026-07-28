# ATT-001 - Exact meet-in-the-middle baseline

Example data - synthetic results for interface demonstration only.

## Public Contract Smoke

passed

## Containment

passed

## Development Metrics

- runs: 24
- verified witnesses: 18/24
- target hits: 11
- timeouts: 6
- crashes: 0
- invalid claims: 0
- normalized quality: 0.540
- runtime: 1820.4 s
- p95: 298.7 s
- speedup: 1.0x

## Decision

rejected

## Learning Carried Forward

- Keep the final witness verifier in every future attempt.
- Treat timeout rate as a first-class rejection signal.
- Use this runtime as the synthetic baseline for speedup display.
