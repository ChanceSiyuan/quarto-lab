# Public Problem Examples on GitHub Pages

## Goal

Publish `Prob-124` through `Prob-128` as static GitHub Pages examples while
keeping the existing `Prob-000` showcase and preserving the boundary that
prevents unrelated local problem data from entering the Pages artifact.

## Scope

The Pages homepage will list exactly these six public records:

- `Prob-000`
- `Prob-124`
- `Prob-125`
- `Prob-126`
- `Prob-127`
- `Prob-128`

GitHub Pages will add one static detail route for each of `Prob-124` through
`Prob-128`. The new records will not receive autoresearch or attempt routes.
The existing `Prob-000` detail, autoresearch, and attempt routes remain
unchanged.

## Architecture

The Pages builder will assemble a temporary public problem root under
`.generated/`. It will copy the complete `Prob-000` showcase fixture, then copy
only `problem.json` and `problem.md` from the five explicitly allowlisted
official problem directories. The normal problem indexer will consume that
temporary root, so the homepage and detail pages continue to use the same
repository and rendering code as the local application.

The allowlist is fixed in the Pages builder. The builder will derive the five
new detail routes from that list instead of maintaining a second route list.
Pointing the indexer at the complete `problems/` tree is intentionally out of
scope because it could publish unrelated current or future records.

## Data Flow

1. Remove and recreate the temporary Pages problem root.
2. Copy the existing `Prob-000` fixture into that root.
3. For each allowlisted ID, require and copy its official `problem.json` and
   `problem.md` files.
4. Build `.generated/problem-index.json` from the temporary public root.
5. Build the application and knowledge site through the existing commands.
6. Snapshot the homepage, existing `Prob-000` routes, and the five new detail
   routes into `out/`.

## Failure Behavior

The Pages build fails before application rendering when an allowlisted problem
directory or required public source file is missing. The error identifies the
missing problem ID and relative file. Invalid manifests continue to fail through
the existing problem index validation path.

## Public Boundary

Only the two display inputs from each official record are copied. Generation
records, assessment artifacts, valuation inputs, attempts, infrastructure,
private files, local paths, and sidecar state remain outside the public staging
root. Existing HTML rewriting continues to remove scripts and local Codex
launch controls from the Pages artifact.

## Testing

The Pages showcase tests will verify that:

- the generated index contains exactly the six approved IDs;
- `out/problems/Prob-124/` through `out/problems/Prob-128/` exist;
- the homepage links to all five new detail routes beneath `/research-loop/`;
- each new detail page contains its problem identity and no scripts, Codex
  launcher, localhost URL, or local service route;
- `Prob-001` and its imported AutoQEC material remain absent;
- a missing allowlisted source file produces a clear build failure through a
  focused staging test.

## Deployment

The existing GitHub Pages workflow remains unchanged. A push to `main` runs the
Pages build and tests, uploads `out/`, and deploys the artifact. Local validation
may omit the full Pages build when Quarto is unavailable; the workflow's pinned
Quarto installation is the final deployment gate.
