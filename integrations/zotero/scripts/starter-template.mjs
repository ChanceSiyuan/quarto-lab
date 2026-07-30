import { cp, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

/**
 * Infrastructure copied from the checkout that builds the XPI. Personal
 * knowledge, literature, drafts, generated output, and Git history are never
 * included. The generated files below establish those content boundaries.
 */
export const STARTER_COPY_PATHS = Object.freeze([
  ".gitignore",
  ".node-version",
  "AGENTS.md",
  "CLAUDE.md",
  "Makefile",
  "README.md",
  "eslint.config.mjs",
  "next.config.ts",
  "package-lock.json",
  "package.json",
  "playwright.assessment.config.ts",
  "playwright.autoresearch.config.ts",
  "playwright.config.ts",
  "postcss.config.mjs",
  "qlab",
  "tsconfig.json",
  "vite.config.ts",
  "worker-configuration.d.ts",
  ".research-loop",
  "schemas",
  "skills",
  "src",
  "public/favicon.svg",
  "public/og.png",
  "knowledge/_quarto.yml",
  "drafts/_quarto.yml",
]);

export const STARTER_GENERATED_FILES = Object.freeze({
  ".openai/hosting.json": `${JSON.stringify({
    project_id: null,
    d1: null,
    r2: null,
  }, null, 2)}\n`,
  ".research-loop/starter.json": `${JSON.stringify({
    schemaVersion: 1,
    state: "ready",
    source: "research-loop-zotero-xpi",
  }, null, 2)}\n`,
  "knowledge/index.qmd": `---
title: Research Knowledge
description: This tree contains only notes the user has reviewed and accepted as trusted knowledge.
---

# Research Knowledge

This tree starts empty. A Draft becomes trusted Knowledge only after the user reviews and promotes it.

## Reading map

No trusted pages have been added yet.
`,
  "drafts/index.qmd": `---
title: Draft Workspace
description: "Entry point for unreviewed notes that can be previewed safely before promotion into trusted Knowledge."
categories: [theory]
---

# Draft workspace

Everything under this directory is unreviewed working material. Previewing a Draft never promotes it into trusted Knowledge.

## Examples

- [Theorem, lemma, definition, and collapsed proof blocks](examples/theorem-blocks.qmd)
`,
  "drafts/examples/theorem-blocks.qmd": `---
title: Theorem blocks starter
description: "A safe QMD example for definitions, lemmas, theorems, cross-references, and collapsed proofs."
categories: [theory]
---

# Theorem-style blocks

Use an identifier beginning with \`def-\`, \`lem-\`, or \`thm-\`. The repository-level Quarto configuration supplies numbering and labels. Refer to a block with \`@def-vector-space\`, \`@lem-zero-unique\`, or \`@thm-linear-map-zero\`.

:::: {#def-vector-space .callout-note icon="false"}
## Vector space

A vector space is a set equipped with vector addition and scalar multiplication satisfying the usual linearity axioms.
::::

The label above can be cited as @def-vector-space.

:::: {#lem-zero-unique .callout-important icon="false"}
## Uniqueness of the zero vector

Every vector space has exactly one additive identity.
::::

:::: {.callout-note collapse="true"}
## Proof of @lem-zero-unique (click to expand)

If \(0\) and \(0'\) are both additive identities, then
\[
0 = 0 + 0' = 0'.
\]
::::

:::: {#thm-linear-map-zero .callout-important icon="false"}
## Linear maps preserve zero

For every linear map \(T: V \to W\), one has \(T(0_V)=0_W\).
::::

:::: {.callout-note collapse="true"}
## Proof of @thm-linear-map-zero (click to expand)

By linearity,
\[
T(0_V)=T(0_V+0_V)=T(0_V)+T(0_V),
\]
so cancellation gives \(T(0_V)=0_W\).
::::

## Authoring checklist

- Keep frontmatter to \`title\`, \`description\`, \`categories\`, and optional \`aliases\`.
- Use exactly one category: \`theory\`, \`experiment\`, or \`codes\`.
- Keep theorem identifiers unique within the page.
- Use four-colon fences for theorem-style and collapsed callout blocks.
- Preview the Draft before proposing promotion to \`knowledge/\`.
`,
  "literature/ref.bib": "% Reviewed citations used by trusted Knowledge are stored here.\n",
});

export async function stageStarterTemplate(researchLoopRoot, targetRoot) {
  await mkdir(targetRoot, { recursive: true });
  for (const relativePath of STARTER_COPY_PATHS) {
    const source = path.join(researchLoopRoot, relativePath);
    const target = path.join(targetRoot, relativePath);
    await mkdir(path.dirname(target), { recursive: true });
    await cp(source, target, { recursive: true, dereference: true });
  }
  for (const [relativePath, contents] of Object.entries(STARTER_GENERATED_FILES)) {
    const target = path.join(targetRoot, relativePath);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, contents);
  }
}
