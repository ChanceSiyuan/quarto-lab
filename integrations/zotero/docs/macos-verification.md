# macOS verification checklist

Everything in this change that can be checked without a Mac is checked by
`npm test`, `npm run check`, and `npm run test:visual` (layout, in headless
Chromium). What follows is the remainder — the parts that only exist inside a
Zotero chrome window on macOS.

Open the Browser Toolbox with `Cmd+Opt+Shift+I` and run the snippets in its
console with the preview open.

## 1. The external editor button

This is the new surface, and the one thing no test here can exercise: detection
reads `/Applications`, and launching spawns `/usr/bin/open`.

1. Open a knowledge page (main site → a page → Source, or the preview's Open…).
2. The button reads **Edit in Cursor** — or whichever editor you have. With
   two or more installed, a picker sits beside it.
3. Click it. The editor opens **the repository as its workspace** with that
   file showing — not the file alone.
4. Change a line and save. The Zotero preview re-renders on its own; you should
   not have to press Refresh.
5. Pick a different editor from the list, click again: it opens there, and the
   choice survives restarting Zotero.
6. If no editor is installed the button is disabled and says No Editor Found
   rather than failing silently on click.

```js
// What detection is looking for:
["Cursor.app", "Visual Studio Code.app", "VSCodium.app", "Zed.app", "Sublime Text.app"]
  .flatMap((bundle) => ["/Applications", "/System/Applications", `${Services.dirsvc.get("Home", Ci.nsIFile).path}/Applications`]
    .map((dir) => `${dir}/${bundle}`))
```

If your editor lives somewhere else entirely, say where — the directory list is
the thing to widen, not the bundle names.

## 2. Preview, and its cost

The render process starts when a file is opened and about six seconds later
serves its first byte on Linux; expect more on a cold macOS cache. Check that:

1. Switching between two files reuses one process rather than accumulating them.
2. Closing the workspace stops it — `pgrep -laf "quarto preview"` returns nothing.
3. A page whose frontmatter you deliberately break keeps showing the **last good
   render** with the failure in the status line, rather than going blank.

## 3. Drafts

1. Open a draft through Open… (the `✎` rows). It renders.
2. The badge reads Draft and the status line says it will not be published.
3. Edit it in Cursor, save, and the preview follows.
4. Run `npm run build` and confirm nothing from `drafts/` reaches
   `public/knowledge/`.

## 4. Nothing is left behind

```bash
git worktree list        # only the checkout
ls work/                 # no knowledge-editor/ directory
```

The old editor ran `git worktree add` on every open and never removed it. This
one creates no worktree at all. Quarto's own render workspace
(`work/knowledge-build-*`) appears while a preview runs and is removed when it
stops — if one survives, note whether Quarto was stopped by closing the
workspace or by killing Zotero, because only the first is a bug.

## 5. Layout

The chat/preview splitter drags, clamps between roughly a quarter and two
thirds, and the ratio survives closing and reopening the workbench tab. The
account and history menus open directly under their own buttons, with the
preview open and closed. The composer's context chips never show a row cut
through its glyphs.

## 6. The site itself

The knowledge site is still browsable on its own, without the preview: the Main Site
button, navigation, search, and the header icons at a sane size.

## Packaging

`npm run build` cannot finish on Linux: it calls `make -C native universal`,
which needs the macOS toolchains for both architectures. The esbuild stage runs
first and does pass there, so a bundling regression would already have been
caught; producing the XPI is a Mac step and has not been done for this change.
