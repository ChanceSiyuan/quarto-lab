# Literature Cache Integrity Design

## Goal

Prevent `literature:fetch` and `literature:sync` from reusing a pinned local
reference after any extracted source file or copied figure has been changed,
removed, or replaced.

## Scope

- Verify every `manifest.extraction.files` entry beneath
  `.raw/<citekey>/source/` by byte count and SHA-256 digest.
- Verify every `manifest.extraction.figures` entry beneath
  `.figures/<citekey>/` by SHA-256 digest.
- Preserve the existing behavior for a complete cache: reuse it without a
  network request.
- Preserve the existing repair behavior for an incomplete cache: download into
  staging and atomically replace every affected method directory.
- Remove the PR-only execution plan
  `docs/superpowers/plans/2026-07-27-human-agent-quarto-knowledge-system.md`.
- Do not change the manifest schema, command-line interface, trust boundary, or
  publication behavior.

## Design

`isComplete` remains the single cache-reuse gate. It will continue to verify the
source archive and PDF, then use the manifest as the allowlist for derived
artifacts:

1. For each extracted file, join its relative manifest path beneath the source
   tree and compare both byte count and SHA-256 digest.
2. For each copied figure, join its destination beneath the figures directory
   and compare its SHA-256 digest.
3. Return `false` on the first missing or mismatched artifact so the existing
   staged download and atomic swap path repairs the cache.

The paths originate from the extraction manifest produced by the archive
validator. This change does not broaden accepted paths or write locations.

## Tests

Follow red-green test-driven development in `tests/literature/fetch.test.ts`:

1. Fetch a reference, alter one extracted source file, fetch it again, and
   assert that the network is used and the verified bytes are restored.
2. Fetch a reference, alter one copied figure, fetch it again, and assert that
   the network is used and the verified bytes are restored.
3. Keep the existing untouched-cache test to prove a valid pin still performs
   no network request.

After the targeted regression tests pass, run the full `npm test` suite. Then
start the production server at `http://127.0.0.1:4173`, open it in the in-app
browser, and inspect the dashboard and `/knowledge/` entry point.

## Acceptance Criteria

- Tampered extracted source and figure content is never reported as reused.
- Repair remains atomic and restores manifest-matching bytes.
- An untouched cache remains network-free.
- The PR-only execution plan is absent from the PR diff.
- Full local verification passes and the locally served site loads in the
  browser.
