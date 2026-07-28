# Pages-Only Research Example Design

Date: 2026-07-28
Status: Approved in conversation

## Purpose

Keep the synthetic `QMB-001` research example available on the GitHub Pages
showcase while completely disabling it in local deployments.

The local problem console must contain only real problems from the workspace.
The public showcase must contain only the synthetic example and must never
publish real local problems accidentally.

## Data Isolation

Move the complete example fixture from:

```text
problems/QMB-001/
```

to:

```text
examples/showcase/problems/QMB-001/
```

This includes the problem manifest, problem Markdown, generation records,
example manifest, attempt records, and attempt logs. The example presentation
helpers will import fixture files from the new location.

The two deployment modes use separate problem roots:

- local development and ordinary production builds index only `problems/`;
- the GitHub Pages build indexes only `examples/showcase/problems/`.

The Pages build does not combine the roots. This prevents future real problems
under `problems/` from appearing in the public showcase.

## Index Construction

Extend the problem-index build entry point so callers can select the problem
root explicitly. Its default remains the workspace `problems/` directory.
The Pages build passes the showcase directory explicitly.

Index validation, ordering, diagnostics, summaries, and duplicate handling stay
shared between both modes. No hostname, request header, or runtime visibility
check controls access to the example.

`QMB-001` remains reserved when deriving the next local problem ID, even though
it is not present in the local index. A new local problem must therefore not
reuse the public example's identifier. The generic index builder will accept a
`reservedIds` input, and the local build entry point will pass `QMB-001`; this
reservation affects only ID allocation, not indexed records, summaries,
diagnostics, routing, or display.

## Build Behavior

### Local

`npm run dev`, `npm run build`, and the application produced by the ordinary
build use the default local problem root.

Consequently:

- the homepage does not list `QMB-001` or include it in summary counts;
- `/problems/QMB-001` returns 404; and
- `/problems/QMB-001/attempts/<attemptId>` returns 404.

The local file watcher continues to watch only `problems/`. Editing the showcase
fixture does not trigger a local rebuild.

### GitHub Pages

`npm run pages:build` is a self-contained showcase build. It:

1. generates the problem index from `examples/showcase/problems/`;
2. creates a vinext production build from that showcase-only index;
3. snapshots the existing `QMB-001` and attempt routes; and
4. writes the static artifact under `out/` using the existing Pages URL
   rewriting and script stripping.

The generated Pages artifact continues to show the example homepage, research
ledger, five attempt dossiers, and synthetic-data disclaimers.

## Tests

Automated coverage will verify both modes independently.

Local-build assertions:

- generated local index omits `QMB-001`;
- local summary counts omit the example;
- local homepage HTML contains no example title or link;
- local problem and attempt routes return 404; and
- the next local problem ID does not reuse `QMB-001`.

Pages-build assertions:

- the static artifact contains the example homepage and all known routes;
- example links use the GitHub Pages base path;
- example disclaimers remain present; and
- local workspace problems are not included in the artifact.

The test command will validate the ordinary local build before running the
Pages-specific build so the two generated application variants cannot mask one
another.

## Documentation

Update the README to state that:

- `problems/` is the local problem library;
- `examples/showcase/problems/` contains public synthetic display data; and
- `pages:build` deliberately builds from the showcase root only.

## Completion Criteria

The change is complete when local development and ordinary production builds
cannot display or route to `QMB-001`, the GitHub Pages artifact still presents
the full example, real local problems cannot leak into that artifact, and all
focused tests, the complete test command, and lint pass.
