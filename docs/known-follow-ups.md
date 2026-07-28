# Known follow-ups

Residual items from the whole-branch review of the human-agent Quarto knowledge system
(branch `feat/human-agent-quarto-knowledge`, reviewed at commit `2108c0a`). None block use;
the two items that did block merge were fixed in `e761250` and `2108c0a`.

## Should-fix-soon (14)

1. **`lib/knowledge/site.ts:4`** — "This is the only module in the repository
   that spawns a program" is false: `lib/drafts/preview.ts:89`,
   `lib/migration/harness.ts:346`, and `scripts/build-e2e-fixture.ts:41` all
   spawn. Reword to "the only module that spawns Quarto for the trusted tree
   and the only one that replaces a published directory".
2. **Three copies of the shell-free spawn runner** —
   `lib/knowledge/site.ts:118`, `lib/drafts/preview.ts:86`,
   `scripts/build-e2e-fixture.ts:39`. All three are correct today; that is
   precisely why they will drift. `ProcessRunner` already lives in `site.ts` and
   `preview.ts` already imports the type from it — extract the implementation
   too (or move both to a `lib/process.ts`).
3. **`lib/knowledge/validate.ts:46`** deep-imports
   `../literature/bibliography.js` rather than the public
   `../literature/index.js`, which exports the same `loadBibliography`. The
   plan's boundary rule is about consumers, so this is not a violation, but it
   is the only cross-module deep import in `lib/` and it undermines the
   "one public door" story.
4. **`lib/knowledge/site.ts:68`** — `FORBIDDEN_OUTPUT_COMPONENTS` omits
   `rendered.md`, which `tests/built-static-assets.test.mjs:56` *does* check and
   describes as "mirror[ing] the site builder's own refusal list". Add
   `rendered.md` so the two lists actually mirror.
5. **Assets are published with no content check.** `lib/knowledge/quarto.ts:435`
   copies every referenced non-`.qmd` file byte-for-byte, and
   `graph.ts:resolveTarget` accepts any extension. Pages get `SCRIPT_FORBIDDEN`;
   an `.svg` asset with an embedded `<script>` gets nothing and is served at
   `/knowledge/<topic>/diagram.svg`, same origin as the dashboard. Add an asset
   extension allowlist, or run the existing unsafe-HTML scan over `.svg`/`.html`
   assets.
6. **`tsconfig.json`** includes `**/*.ts` and excludes only `node_modules`, so
   any scratch `.ts` under the gitignored `work/`, `dist/`, or
   `public/knowledge/` breaks `npx tsc --noEmit` — which is a Task 16 acceptance
   command. Add those directories to `exclude`. (Ledger, Task 8 minor.)
7. **`lib/knowledge/types.ts:50`** — `PATH_LIKE_ALIAS` rejects any `/`, so
   `aliases: ["spin-1/2 chain"]` fails validation. In a quantum-many-body
   knowledge base that is a common synonym. Ship as-is if you like the
   conservative rule, but say so in `README.md` under "Knowledge pages" — right
   now the only place it is written down is the diagnostic text.
8. **`skills/download-ref/SKILL.md:23`** — `.figures/<citekey>/  # images
   extracted from the PDF` is wrong. `lib/literature/figures.ts` copies figures
   out of the *extracted source archive* and never touches the PDF (which is the
   whole safety argument of that module). An agent reading this could reasonably
   try to rasterize a PDF.
9. **`lib/literature/fetch.ts:571`** — `syncLiterature` aborts the whole run on
   the first hard failure. Combined with the documented refusal of v7 and
   pax/GNU-extended-header tars (`lib/literature/archive.ts:311,332`), one
   awkward arXiv dialect stops the entire 65-entry corpus sync. Collect failures
   and report them at the end, or at least document the abort in
   `skills/download-ref/SKILL.md`.
10. **`lib/literature/bibliography.ts:233`** — bare
    `decodeURIComponent(match[1])` can throw a raw `URIError` on a malformed
    `%` escape in an arXiv URL, escaping the module's own `fail()` message
    convention. (Ledger, Task 3 minor.) Wrap it.
11. **`lib/knowledge/parser.ts:1177` and `lib/knowledge/graph.ts:156`** define
    two identical private `diagnosticFile` functions. The circular import
    forbids sharing between those two files — move it to `types.ts`, which both
    already import.
12. **Stale method directories are never reported.** If a keyword leaves
    `ref.bib`, `lib/literature/indexes.ts:155` writes the surviving indexes and
    leaves the orphaned `literature/<method>/INDEX.md` committed and unmentioned.
    (Ledger, Task 3 minor.) Report them rather than delete them.
13. **`lib/migration/harness.ts:426`** — `listDestinationFiles` records files
    only, so an empty directory under `drafts/imported-quantum-harness` passes
    `verify` unreported. (Ledger, Task 2 minor.) Harmless; cheap to close.
14. **Commit authorship is split** between `chensiyuan <chance@DGX-Station…>`
    and `ch <Eric.M.990909@gmail.com>` (ledger line 45). Cosmetic; normalize
    with a rebase before merge if the history matters.

## Inherited from the `origin/main` merge (2)

Both arrived with the Problem Console / GitHub Pages showcase work and reproduce
on `origin/main` on its own. Neither is caused by the merge, and neither was
patched inside the merge commit; they are recorded here so they are not mistaken
for knowledge-system defects.

15. **`npx --no-install tsc --noEmit` reports 8 `TS7006` implicit-`any`
    errors** in `app/problem-console.tsx` (2), `app/problems/[id]/page.tsx` (3),
    and `app/problems/[id]/attempts/[attemptId]/page.tsx` (3). `lib/problems/*.mjs`
    is untyped JavaScript, so every value that crosses that boundary is `any`
    and each `.map((row) => …)` callback trips `noImplicitAny`. Verified
    identical on `origin/main` alone; this branch was `tsc`-clean before the
    merge. `tsc --noEmit` is a plan acceptance command but is wired into no npm
    script, so `npm test` still passes. Fix by adding JSDoc `@param`/`@returns`
    types to `lib/problems/*.mjs`, or — cheaply — by annotating the callbacks
    with `ReturnType<typeof buildProblemPresentation>`.
16. **`npm run pages:build` copies orphan knowledge stylesheets into `out/`.**
    `scripts/build-pages-showcase.mjs:70` (`shouldCopyClientAsset`) is an
    extension allowlist over all of `dist/client`, so it sweeps up Quarto's
    bundled CSS under `dist/client/knowledge/site_libs/`. The GitHub Pages
    artifact therefore carries 4 files / ~624 KB at `out/knowledge/site_libs/**`
    (Bootstrap, Bootstrap Icons, Quarto syntax highlighting, tippy) with no
    knowledge HTML to use them, and `bootstrap-icons.css` points at a
    `bootstrap-icons.woff` that the `.woff2`-only allowlist leaves behind.
    Nothing on the Pages site links to them, so this is dead weight, not a leak
    of unpublished content — the knowledge HTML, `search.json`, and JS are all
    excluded. Scope the copy to the showcase routes' own assets if it matters.

## Accepted residual risk

The unsafe-HTML scanner in `lib/knowledge/parser.ts` does not model every Pandoc
tagsoup edge case. Known gaps: tags whose name is outside `HTML_ELEMENT_NAMES` spanning
a blank line; a stray quote re-opening an attribute value; a `::: {.callout}` fenced div
followed by a YAML metadata block. These were adjudicated as accepted risk: a page becomes
trusted only through user review and merge, and every Quarto render and preview subprocess
passes `--no-execute`, which is the lock that actually holds.

Two related holes WERE closed and must stay closed:

- `{{< env >}}` expanded under `--no-execute` and published the build host's environment.
  `lib/knowledge/quarto.ts` now refuses every `{{<` shortcode (empty allowlist).
- An unclosed code fence hid links and citations from validation while Quarto still
  rendered them. The parser now emits `FENCE_UNCLOSED`.
