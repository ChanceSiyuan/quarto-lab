/**
 * The projection is the last gate between a validated graph and a rendered
 * website: whatever it writes into the temporary project is what Quarto reads,
 * and whatever Quarto reads is what the world sees. These tests therefore pin
 * three properties.
 *
 * - **It copies trusted content, and invents only code-owned chrome.** Every
 *   page and every referenced asset arrives byte-for-byte; generated
 *   navigation, bibliography plumbing, and the Research Loop stylesheet are
 *   written from this module; nothing else arrives at all — not drafts, not
 *   literature, not an unreferenced file sitting next to a diagram, not a
 *   `_`-prefixed page.
 * - **It re-asserts the safety schema rather than trusting it.** The committed
 *   base `_quarto.yml` is read, compared against the fixed schema exactly, and
 *   then *regenerated*; a filter, an include, a resource, an extension, or an
 *   execution override anywhere in the base file stops the projection instead
 *   of travelling into the render.
 * - **It is deterministic and escapes what it emits.** Sidebar order comes from
 *   the reading maps alone, category listings from curated order then POSIX
 *   path, and a title carrying `]`, `:`, quotes, or a newline round-trips
 *   through the generated YAML and cannot break out of a Markdown link.
 *
 * Every case works on a real tree under `mkdtemp`, because "these bytes on disk
 * become those bytes in the project" is not a statement a hand-built graph
 * object can make.
 */

import assert from "node:assert/strict";
import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { fileURLToPath } from "node:url";

import { parse } from "yaml";

import { loadKnowledge, type KnowledgeGraph } from "../../../src/lib/knowledge/graph.js";
import { materializeQuartoProject } from "../../../src/lib/knowledge/quarto.js";
import { validateKnowledge } from "../../../src/lib/knowledge/validate.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..", "..");
const FIXTURES = path.join(REPO_ROOT, ".research-loop", "tests", "fixtures", "knowledge");

/** The committed base configuration, which every fixture tree also carries. */
const BASE_CONFIG = [
  "project:",
  "  type: website",
  "website:",
  "  title: Research Loop Knowledge",
  "  site-path: /knowledge/",
  "  search: true",
  "format:",
  "  html:",
  "    toc: true",
  "    css: research-loop.css",
  "crossref:",
  "  custom:",
  "    - kind: float",
  "      key: lem",
  "      reference-prefix: Lemma",
  "      space-before-numbering: true",
  "    - kind: float",
  "      key: thm",
  "      reference-prefix: Theorem",
  "      space-before-numbering: true",
  "    - kind: float",
  "      key: def",
  "      reference-prefix: Definition",
  "      space-before-numbering: true",
  "execute:",
  "  enabled: false",
  "",
].join("\n");

async function makeTempDir(t: TestContext, prefix: string): Promise<string> {
  const directory = await mkdtemp(path.join(await realpath(tmpdir()), prefix));
  t.after(() => rm(directory, { recursive: true, force: true }));
  return directory;
}

/** A throwaway repository holding the shared valid fixture as `knowledge/`. */
async function makeRepo(t: TestContext): Promise<string> {
  const repo = await makeTempDir(t, "knowledge-quarto-");
  await cp(path.join(FIXTURES, "valid"), path.join(repo, "knowledge"), {
    recursive: true,
  });
  await mkdir(path.join(repo, "literature"), { recursive: true });
  await cp(path.join(FIXTURES, "ref.bib"), path.join(repo, "literature", "ref.bib"));
  return repo;
}

/** A throwaway repository holding exactly the given knowledge pages. */
async function makeTree(
  t: TestContext,
  pages: Record<string, string>,
): Promise<string> {
  const repo = await makeTempDir(t, "knowledge-quarto-");
  await mkdir(path.join(repo, "knowledge"), { recursive: true });
  await writeFile(path.join(repo, "knowledge", "_quarto.yml"), BASE_CONFIG);
  for (const [relative, source] of Object.entries(pages)) {
    const file = path.join(repo, "knowledge", ...relative.split("/"));
    await mkdir(path.dirname(file), { recursive: true });
    await writeFile(file, source);
  }
  await mkdir(path.join(repo, "literature"), { recursive: true });
  await cp(path.join(FIXTURES, "ref.bib"), path.join(repo, "literature", "ref.bib"));
  return repo;
}

/** One `.qmd` source: frontmatter in the given order, then the body. */
function qmd(frontmatter: Record<string, string>, body: readonly string[]): string {
  return [
    "---",
    ...Object.entries(frontmatter).map(([key, value]) => `${key}: ${value}`),
    "---",
    "",
    ...body,
    "",
  ].join("\n");
}

/** An index body whose `## Reading map` lists the given targets, in order. */
function indexBody(targets: readonly string[]): string[] {
  return [
    "Nothing here.",
    "",
    "## Reading map",
    "",
    ...(targets.length === 0
      ? ["No pages have been promoted yet."]
      : targets.map((target) => `- [Entry](${target})`)),
  ];
}

/** Every file under a directory, as sorted POSIX paths relative to it. */
async function fileTree(root: string): Promise<string[]> {
  const found: string[] = [];
  const walk = async (directory: string, prefix: string): Promise<void> => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const id = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
      if (entry.isDirectory()) {
        await walk(path.join(directory, entry.name), id);
      } else {
        found.push(id);
      }
    }
  };
  await walk(root, "");
  return found.sort();
}

/** The bibliography a temporary repository validates against. */
function bibliographyOf(repo: string): string {
  return path.join(repo, "literature", "ref.bib");
}

async function project(
  t: TestContext,
  repo: string,
): Promise<{
  graph: KnowledgeGraph;
  workspace: string;
  result: Awaited<ReturnType<typeof materializeQuartoProject>>;
}> {
  const graph = await loadKnowledge({ repoRoot: repo });
  const workspace = await makeTempDir(t, "knowledge-workspace-");
  const result = await materializeQuartoProject({
    graph,
    workspace,
    bibliographyPath: bibliographyOf(repo),
  });
  return { graph, workspace, result };
}

/** The parsed generated configuration of a materialized project. */
async function generatedConfig(projectDir: string): Promise<Record<string, unknown>> {
  const text = await readFile(path.join(projectDir, "_quarto.yml"), "utf8");
  return parse(text) as Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// What is copied, and what is not.
// ---------------------------------------------------------------------------

test("the projection holds exactly the graph, the bibliography, and generated navigation", async (t) => {
  const repo = await makeRepo(t);
  assert.equal(
    (await validateKnowledge({ repoRoot: repo })).ok,
    true,
    "the shared fixture must itself be a valid tree",
  );
  const { graph, workspace, result } = await project(t, repo);

  assert.equal(
    path.dirname(result.projectDir),
    workspace,
    "the projection owns a directory inside the workspace it was given",
  );
  assert.equal(result.outputDir, path.join(result.projectDir, "_site"));

  assert.deepEqual(await fileTree(result.projectDir), [
    "_quarto.yml",
    "categories/codes/index.qmd",
    "categories/experiment/index.qmd",
    "categories/theory/index.qmd",
    "index.qmd",
    "ising/diagram.svg",
    "ising/index.qmd",
    "ising/proof.qmd",
    "ising/proposal.qmd",
    "ising/verified-code.qmd",
    "references/ref.bib",
    "research-loop.css",
  ]);

  // Byte-for-byte, not "equivalent": the projection may not normalize, rewrite
  // links, or re-encode a page on its way into the render.
  for (const [id, page] of graph.pages) {
    assert.deepEqual(
      await readFile(path.join(result.projectDir, ...id.split("/"))),
      await readFile(page.absolutePath),
      `page ${id} is copied byte-for-byte`,
    );
  }
  for (const [id, absolutePath] of graph.assets) {
    assert.deepEqual(
      await readFile(path.join(result.projectDir, ...id.split("/"))),
      await readFile(absolutePath),
      `asset ${id} is copied byte-for-byte`,
    );
  }
  assert.deepEqual(
    await readFile(path.join(result.projectDir, "references", "ref.bib")),
    await readFile(bibliographyOf(repo)),
    "the bibliography is copied byte-for-byte",
  );
  const stylesheet = await readFile(path.join(result.projectDir, "research-loop.css"), "utf8");
  assert.match(stylesheet, /--rl-paper:\s*#f3f0e8;/);
  assert.match(stylesheet, /--rl-green:\s*#174c3b;/);
  assert.match(stylesheet, /#quarto-header/);
  assert.match(stylesheet, /#quarto-sidebar/);
  assert.match(stylesheet, /#quarto-document-content/);
  assert.match(stylesheet, /\.rl-home-link/);
  // The header buttons carry a minimum height; without a matching icon size
  // the Bootstrap glyph inside them inherits the body scale and dwarfs them.
  assert.match(stylesheet, /\.quarto-btn-toggle[\s\S]*?font-size/);
  assert.match(stylesheet, /\.quarto-search-button .bi[\s\S]{0,200}?font-size/);
  assert.deepEqual(
    [...graph.assets.keys()],
    ["ising/diagram.svg"],
    "the only asset of the fixture is the diagram its proof embeds",
  );
});

test("drafts, literature, unreferenced files, and excluded paths never reach the project", async (t) => {
  const repo = await makeRepo(t);
  await mkdir(path.join(repo, "drafts", "imported"), { recursive: true });
  await writeFile(path.join(repo, "drafts", "imported", "note.md"), "# Untrusted\n");
  await writeFile(path.join(repo, "literature", "INDEX.md"), "# Literature\n");
  // Sitting beside a copied asset, and never referenced by any page.
  await writeFile(path.join(repo, "knowledge", "ising", "unused.svg"), "<svg/>\n");
  await mkdir(path.join(repo, "knowledge", "_partials"), { recursive: true });
  await writeFile(
    path.join(repo, "knowledge", "_partials", "hidden.qmd"),
    qmd({ title: "Hidden", description: "Excluded." }, ["Nothing here."]),
  );

  const { graph, result } = await project(t, repo);

  assert.deepEqual(
    [...graph.pages.keys()],
    [
      "index.qmd",
      "ising/index.qmd",
      "ising/proof.qmd",
      "ising/proposal.qmd",
      "ising/verified-code.qmd",
    ],
    "generated category pages and excluded files are never graph pages",
  );

  const tree = await fileTree(result.projectDir);
  for (const forbidden of ["unused.svg", "hidden.qmd", "_partials", "drafts", "literature", "INDEX.md"]) {
    assert.equal(
      tree.some((entry) => entry.includes(forbidden)),
      false,
      `${forbidden} must not appear in ${JSON.stringify(tree)}`,
    );
  }
});

test("generated pages are written to the project, never into the knowledge tree", async (t) => {
  const repo = await makeRepo(t);
  const before = await fileTree(path.join(repo, "knowledge"));
  await project(t, repo);

  assert.deepEqual(
    await fileTree(path.join(repo, "knowledge")),
    before,
    "materializing changes nothing under knowledge/",
  );
  assert.deepEqual(before, [
    "_quarto.yml",
    "index.qmd",
    "ising/diagram.svg",
    "ising/index.qmd",
    "ising/proof.qmd",
    "ising/proposal.qmd",
    "ising/verified-code.qmd",
  ]);
});

test("projecting the same graph twice produces byte-identical projects", async (t) => {
  const repo = await makeRepo(t);
  const first = await project(t, repo);
  const second = await project(t, repo);

  const files = await fileTree(first.result.projectDir);
  assert.deepEqual(files, await fileTree(second.result.projectDir));
  for (const file of files) {
    assert.deepEqual(
      await readFile(path.join(first.result.projectDir, ...file.split("/"))),
      await readFile(path.join(second.result.projectDir, ...file.split("/"))),
      `${file} is identical across runs`,
    );
  }
});

// ---------------------------------------------------------------------------
// The generated configuration.
// ---------------------------------------------------------------------------

test("the generated configuration re-asserts every fixed safety setting", async (t) => {
  const repo = await makeRepo(t);
  const { result } = await project(t, repo);
  const config = await generatedConfig(result.projectDir);

  assert.deepEqual(Object.keys(config).sort(), [
    "bibliography",
    "crossref",
    "execute",
    "format",
    "project",
    "website",
  ]);
  const website = config.website as Record<string, unknown>;
  assert.equal(website.title, "Research Loop Knowledge");
  assert.equal(website["site-path"], "/knowledge/");
  assert.equal(website.search, true);
  assert.deepEqual(config.project, { type: "website", "output-dir": "_site" });
  assert.deepEqual(config.format, { html: { toc: true, css: "research-loop.css" } });
  assert.deepEqual(config.crossref, {
    custom: [
      { kind: "float", key: "lem", "reference-prefix": "Lemma", "space-before-numbering": true },
      { kind: "float", key: "thm", "reference-prefix": "Theorem", "space-before-numbering": true },
      { kind: "float", key: "def", "reference-prefix": "Definition", "space-before-numbering": true },
    ],
  });
  assert.deepEqual(config.execute, { enabled: false });
  assert.equal(
    config.bibliography,
    "references/ref.bib",
    "the bibliography is configured at the copy inside the project",
  );

  // The whole point of regenerating rather than copying: none of the keys that
  // turn rendering into code execution or into file disclosure may be present.
  const serialized = await readFile(path.join(result.projectDir, "_quarto.yml"), "utf8");
  for (const forbidden of [
    "filters",
    "include-in-header",
    "include-before-body",
    "include-after-body",
    "resources",
    "extensions",
    "pre-render",
    "post-render",
    "metadata-files",
  ]) {
    assert.equal(
      serialized.includes(forbidden),
      false,
      `the generated configuration must not mention ${forbidden}`,
    );
  }
});

test("the committed base configuration must match the fixed safe schema exactly", async (t) => {
  const repo = await makeRepo(t);
  const graph = await loadKnowledge({ repoRoot: repo });
  const baseConfig = path.join(repo, "knowledge", "_quarto.yml");

  const materialize = async (): Promise<unknown> => {
    const workspace = await makeTempDir(t, "knowledge-workspace-");
    return materializeQuartoProject({
      graph,
      workspace,
      bibliographyPath: bibliographyOf(repo),
    });
  };

  await assert.doesNotReject(materialize, "the committed base configuration is accepted");

  const rejections: readonly (readonly [string, string, RegExp])[] = [
    ["a Lua filter", `${BASE_CONFIG}filters:\n  - evil.lua\n`, /filters/],
    ["a resource glob", `${BASE_CONFIG}resources:\n  - "../../../etc/**"\n`, /resources/],
    [
      "an injected header",
      BASE_CONFIG.replace("    toc: true\n", "    toc: true\n    include-in-header: evil.html\n"),
      /include-in-header/,
    ],
    [
      "an execution override",
      BASE_CONFIG.replace("  enabled: false\n", "  enabled: true\n"),
      /execute\.enabled/,
    ],
    [
      "a pre-render hook",
      BASE_CONFIG.replace("  type: website\n", "  type: website\n  pre-render: ./evil.sh\n"),
      /pre-render/,
    ],
    [
      "a relocated site path",
      BASE_CONFIG.replace("  site-path: /knowledge/\n", "  site-path: /\n"),
      /site-path/,
    ],
    [
      "a disabled search",
      BASE_CONFIG.replace("  search: true\n", "  search: false\n"),
      /website\.search/,
    ],
    ["a missing execution block", BASE_CONFIG.replace("execute:\n  enabled: false\n", ""), /execute/],
    ["an empty file", "", /project/],
  ];

  for (const [label, text, expected] of rejections) {
    await writeFile(baseConfig, text);
    await assert.rejects(
      materialize,
      (error: unknown) => {
        assert.ok(error instanceof Error, `${label} must be refused`);
        assert.match(error.message, expected, label);
        return true;
      },
      `${label} must stop the projection`,
    );
  }

  await rm(baseConfig);
  await assert.rejects(materialize, /_quarto\.yml/, "a missing base configuration is refused");
});

// ---------------------------------------------------------------------------
// The sidebar: curated order, and nothing else.
// ---------------------------------------------------------------------------

/**
 * A tree whose reading maps disagree with alphabetical order at every level,
 * so a sidebar built from the filesystem cannot pass by accident.
 */
const NESTED_TREE: Record<string, string> = {
  "index.qmd": qmd(
    { title: "Research Loop Knowledge", description: "The root." },
    indexBody(["zeta/index.qmd", "alpha.qmd"]),
  ),
  "alpha.qmd": qmd(
    { title: "Alpha note", description: "Curated last, first alphabetically.", categories: "[theory]" },
    ["Nothing here."],
  ),
  "zeta/index.qmd": qmd(
    { title: "Zeta topic", description: "Curated first, last alphabetically." },
    indexBody(["two.qmd", "sub/index.qmd", "one.qmd"]),
  ),
  "zeta/one.qmd": qmd(
    { title: "One", description: "Curated last.", categories: "[experiment]" },
    ["Nothing here."],
  ),
  "zeta/two.qmd": qmd(
    { title: "Two", description: "Curated first.", categories: "[codes]" },
    ["Nothing here."],
  ),
  "zeta/sub/index.qmd": qmd(
    { title: "Deep subtopic", description: "A subtopic." },
    indexBody(["three.qmd"]),
  ),
  "zeta/sub/three.qmd": qmd(
    { title: "Three", description: "The only page of the subtopic.", categories: "[theory]" },
    ["Nothing here."],
  ),
};

test("the nested sidebar comes from the reading maps and from nothing else", async (t) => {
  const repo = await makeTree(t, NESTED_TREE);
  assert.equal(
    (await validateKnowledge({ repoRoot: repo })).ok,
    true,
    "the nested fixture must itself be a valid tree",
  );
  const { result } = await project(t, repo);
  const config = await generatedConfig(result.projectDir);
  const website = config.website as Record<string, unknown>;

  assert.deepEqual(website.sidebar, {
    contents: [
      { text: "Research Loop Knowledge", href: "index.qmd" },
      {
        section: "Zeta topic",
        href: "zeta/index.qmd",
        contents: [
          { text: "Two", href: "zeta/two.qmd" },
          {
            section: "Deep subtopic",
            href: "zeta/sub/index.qmd",
            contents: [{ text: "Three", href: "zeta/sub/three.qmd" }],
          },
          { text: "One", href: "zeta/one.qmd" },
        ],
      },
      { text: "Alpha note", href: "alpha.qmd" },
      {
        section: "Categories",
        contents: [
          { text: "Theory", href: "categories/theory/index.qmd" },
          { text: "Experiment", href: "categories/experiment/index.qmd" },
          { text: "Codes", href: "categories/codes/index.qmd" },
        ],
      },
    ],
  });
});

test("a page no reading map reaches is copied but never enters the sidebar", async (t) => {
  // Such a tree is invalid — `ORPHAN_CHILD` — and the projection is the pure
  // layer: it projects whatever graph it is handed. What it may never do is
  // invent a navigation position the author did not curate.
  const repo = await makeTree(t, {
    "index.qmd": qmd({ title: "Root", description: "The root." }, indexBody([])),
    "loose.qmd": qmd(
      { title: "Loose", description: "Curated by nobody.", categories: "[theory]" },
      ["Nothing here."],
    ),
  });
  assert.equal((await validateKnowledge({ repoRoot: repo })).ok, false);

  const { result } = await project(t, repo);
  const config = await generatedConfig(result.projectDir);
  const website = config.website as Record<string, unknown>;
  const sidebar = website.sidebar as { contents: readonly unknown[] };

  assert.deepEqual(sidebar.contents[0], { text: "Root", href: "index.qmd" });
  assert.equal(
    JSON.stringify(sidebar.contents).includes("loose.qmd"),
    false,
    "an uncurated page has no curated position",
  );
  assert.deepEqual(
    (await fileTree(result.projectDir)).includes("loose.qmd"),
    true,
    "it is still projected: the graph named it",
  );
});

// ---------------------------------------------------------------------------
// The three category views.
// ---------------------------------------------------------------------------

test("exactly three category pages are generated, in curated then POSIX order", async (t) => {
  // `orphan.qmd` and `another-orphan.qmd` are reachable from no reading map, so
  // they have no curated rank and fall back to POSIX path order — after every
  // curated page, and in `another-orphan`, `orphan` order rather than the order
  // the filesystem enumerated them in.
  const repo = await makeTree(t, {
    ...NESTED_TREE,
    "orphan.qmd": qmd(
      { title: "Orphan", description: "Uncurated, second by path.", categories: "[theory]" },
      ["Nothing here."],
    ),
    "another-orphan.qmd": qmd(
      { title: "Another orphan", description: "Uncurated, first by path.", categories: "[theory]" },
      ["Nothing here."],
    ),
  });
  const { result } = await project(t, repo);

  const theory = await readFile(
    path.join(result.projectDir, "categories", "theory", "index.qmd"),
    "utf8",
  );
  assert.deepEqual(theory.split("\n").filter((line) => line.startsWith("- ")), [
    "- [Three](../../zeta/sub/three.qmd) — The only page of the subtopic.",
    "- [Alpha note](../../alpha.qmd) — Curated last, first alphabetically.",
    "- [Another orphan](../../another-orphan.qmd) — Uncurated, first by path.",
    "- [Orphan](../../orphan.qmd) — Uncurated, second by path.",
  ]);
  assert.match(theory, /^---\ntitle: Theory\n/, "the category page names its own category");

  const experiment = await readFile(
    path.join(result.projectDir, "categories", "experiment", "index.qmd"),
    "utf8",
  );
  assert.deepEqual(experiment.split("\n").filter((line) => line.startsWith("- ")), [
    "- [One](../../zeta/one.qmd) — Curated last.",
  ]);

  const codes = await readFile(
    path.join(result.projectDir, "categories", "codes", "index.qmd"),
    "utf8",
  );
  assert.deepEqual(codes.split("\n").filter((line) => line.startsWith("- ")), [
    "- [Two](../../zeta/two.qmd) — Curated first.",
  ]);

  assert.deepEqual(
    (await fileTree(result.projectDir)).filter((file) => file.startsWith("categories/")),
    [
      "categories/codes/index.qmd",
      "categories/experiment/index.qmd",
      "categories/theory/index.qmd",
    ],
    "exactly three category pages, and no other generated page",
  );
});

test("category URLs are exactly the three subpaths of the knowledge site", async (t) => {
  const repo = await makeRepo(t);
  const { result } = await project(t, repo);

  assert.deepEqual(result.categoryUrls, {
    theory: "/knowledge/categories/theory/",
    experiment: "/knowledge/categories/experiment/",
    codes: "/knowledge/categories/codes/",
  });
});

test("a category nothing is filed under still gets a page", async (t) => {
  const repo = await makeTree(t, {
    "index.qmd": qmd({ title: "Root", description: "The root." }, indexBody(["only.qmd"])),
    "only.qmd": qmd(
      { title: "Only", description: "The only page.", categories: "[theory]" },
      ["Nothing here."],
    ),
  });
  const { result } = await project(t, repo);

  const experiment = await readFile(
    path.join(result.projectDir, "categories", "experiment", "index.qmd"),
    "utf8",
  );
  assert.deepEqual(experiment.split("\n").filter((line) => line.startsWith("- ")), []);
  assert.match(experiment, /experiment/);
});

// ---------------------------------------------------------------------------
// Escaping: a title is data, never syntax.
// ---------------------------------------------------------------------------

const NASTY_TITLE = 'Weird ]: "quoted" [title]';
const NASTY_DESCRIPTION = "First: \"line\"\nSecond ] line";

test("titles and descriptions carrying YAML and Markdown syntax are escaped", async (t) => {
  const repo = await makeTree(t, {
    "index.qmd": qmd(
      { title: "Research Loop Knowledge", description: "The root." },
      indexBody(["nasty.qmd"]),
    ),
    // Single-quoted YAML and a literal block scalar: the only frontmatter forms
    // that can carry `]`, `:`, a quote, and a newline into a title.
    "nasty.qmd": [
      "---",
      `title: '${NASTY_TITLE.replace(/'/gu, "''")}'`,
      "description: |",
      '  First: "line"',
      "  Second ] line",
      "categories: [theory]",
      "---",
      "",
      "Nothing here.",
      "",
    ].join("\n"),
  });
  const { graph, result } = await project(t, repo);

  assert.equal(graph.pages.get("nasty.qmd")?.title, NASTY_TITLE);
  assert.equal(graph.pages.get("nasty.qmd")?.description, NASTY_DESCRIPTION);

  // YAML: the generated configuration must parse back to the exact strings.
  const config = await generatedConfig(result.projectDir);
  const website = config.website as Record<string, unknown>;
  const sidebar = website.sidebar as { contents: readonly Record<string, unknown>[] };
  assert.deepEqual(sidebar.contents[1], { text: NASTY_TITLE, href: "nasty.qmd" });

  // Markdown: the link label may not end early, and the newline may not break
  // the list item in two.
  const theory = await readFile(
    path.join(result.projectDir, "categories", "theory", "index.qmd"),
    "utf8",
  );
  assert.deepEqual(theory.split("\n").filter((line) => line.startsWith("- ")), [
    '- [Weird \\]: "quoted" \\[title\\]](../../nasty.qmd) — First: "line" Second \\] line',
  ]);

  // And the category page's own frontmatter is still valid YAML.
  const [, frontmatter] = theory.split("---\n");
  assert.deepEqual(parse(frontmatter), {
    title: "Theory",
    description: "Every trusted knowledge page filed under the theory category.",
  });
});

// ---------------------------------------------------------------------------
// Shortcodes: the one way a validated page could still reach outside.
// ---------------------------------------------------------------------------

test("a page carrying any Quarto shortcode stops the projection", async (t) => {
  // Verified against Quarto 1.9.38: `{{< include ../../secret.qmd >}}` on a page
  // inside a rendered project reads and publishes a file *outside* the project
  // directory, and `{{< env RESEARCH_LOOP_SECRET >}}` renders the build host's
  // environment variable into the published HTML — both under `--no-execute`,
  // because shortcodes expand before execution is even considered. The parser
  // does not model shortcodes, so validation cannot see any of it.
  //
  // The gate is therefore an allowlist of shortcodes known to read nothing, and
  // it is empty: `env` was missed precisely because the rule used to be a list
  // of the dangerous names known at the time. Every name below is refused,
  // whether it reads a file (`include`, `embed`), the environment (`env`),
  // project metadata (`meta`, `var`), or nothing at all (`pagebreak`, `kbd`).
  for (const shortcode of [
    "{{< include ../../../etc/passwd >}}",
    "{{< embed ../../notebook.ipynb#fig >}}",
    "{{<include x.qmd>}}",
    "{{< env RESEARCH_LOOP_SECRET >}}",
    "{{<env HOME>}}",
    "{{< ENV RESEARCH_LOOP_SECRET >}}",
    "{{< meta title >}}",
    "{{< var site.url >}}",
    "{{< pagebreak >}}",
    "{{< kbd Ctrl-C >}}",
    "{{< video https://example.com/clip.mp4 >}}",
    "{{< contents note >}}",
    "{{< /contents >}}",
    "{{< bi github >}}",
    // The escaped form, which Quarto renders as literal shortcode text: refused
    // too, because deciding it is inert means parsing Quarto's escaping rules.
    "{{{< env RESEARCH_LOOP_SECRET >}}}",
    // A name nobody has shipped yet, which is the case a denylist cannot cover.
    "{{< notyetinvented arg >}}",
    "{{< >}}",
  ]) {
    const repo = await makeTree(t, {
      "index.qmd": qmd(
        { title: "Root", description: "The root." },
        indexBody(["page.qmd"]),
      ),
      "page.qmd": qmd(
        { title: "Page", description: "A page.", categories: "[theory]" },
        ["Nothing here.", "", shortcode],
      ),
    });
    const graph = await loadKnowledge({ repoRoot: repo });
    const workspace = await makeTempDir(t, "knowledge-workspace-");

    await assert.rejects(
      () =>
        materializeQuartoProject({
          graph,
          workspace,
          bibliographyPath: bibliographyOf(repo),
        }),
      (error: unknown) => {
        assert.ok(error instanceof Error);
        assert.match(error.message, /page\.qmd/);
        assert.match(error.message, /shortcode/);
        return true;
      },
      `${shortcode} must stop the projection`,
    );
  }
});

test("a trusted page may not sit where the projection generates", async (t) => {
  for (const id of ["categories/theory/index.qmd", "references/note.qmd"]) {
    const repo = await makeTree(t, {
      "index.qmd": qmd({ title: "Root", description: "The root." }, indexBody([id])),
      [id]: qmd({ title: "Collision", description: "A page.", categories: "[theory]" }, [
        "Nothing here.",
      ]),
      [`${path.posix.dirname(id)}/index.qmd`]: qmd(
        { title: "Colliding topic", description: "A topic." },
        indexBody([]),
      ),
    });
    const graph = await loadKnowledge({ repoRoot: repo });
    const workspace = await makeTempDir(t, "knowledge-workspace-");

    await assert.rejects(
      () =>
        materializeQuartoProject({
          graph,
          workspace,
          bibliographyPath: bibliographyOf(repo),
        }),
      (error: unknown) => {
        assert.ok(error instanceof Error);
        assert.match(error.message, /projection generates/);
        return true;
      },
      `${id} must stop the projection`,
    );
  }
});

test("a trusted asset may not sit where the projection generates the stylesheet", async (t) => {
  const repo = await makeTree(t, {
    "index.qmd": qmd({ title: "Root", description: "The root." }, indexBody(["page.qmd"])),
    "page.qmd": qmd({ title: "Page", description: "A page.", categories: "[theory]" }, [
      "![Colliding stylesheet](research-loop.css)",
    ]),
  });
  await writeFile(path.join(repo, "knowledge", "research-loop.css"), "body { color: red; }\n");
  const graph = await loadKnowledge({ repoRoot: repo });
  const workspace = await makeTempDir(t, "knowledge-workspace-");

  await assert.rejects(
    () =>
      materializeQuartoProject({
        graph,
        workspace,
        bibliographyPath: bibliographyOf(repo),
      }),
    (error: unknown) => {
      assert.ok(error instanceof Error);
      assert.match(error.message, /generated file name/);
      return true;
    },
  );
});

test("an alias that Quarto would read as a path stops the projection", async (t) => {
  // Verified against Quarto 1.9.38: every alias becomes a redirect *directory*
  // written relative to the rendered page, so `../../…` makes the renderer call
  // `mkdir` outside the output directory, the project, and the workspace. The
  // resolver means "another name for this page" by the same key, and no name
  // needs a separator.
  for (const alias of [
    "../../../../../../tmp/quarto-alias-escape",
    "/etc/passwd",
    "a/b",
    "..",
    ".",
    "~",
    "windows\\path",
  ]) {
    const repo = await makeTree(t, {
      "index.qmd": qmd({ title: "Root", description: "The root." }, indexBody(["page.qmd"])),
      "page.qmd": [
        "---",
        "title: Page",
        "description: A page.",
        "categories: [theory]",
        `aliases: [${JSON.stringify(alias)}]`,
        "---",
        "",
        "Nothing here.",
        "",
      ].join("\n"),
    });
    const graph = await loadKnowledge({ repoRoot: repo });
    assert.deepEqual(graph.pages.get("page.qmd")?.aliases, [alias], "the alias parses");
    const workspace = await makeTempDir(t, "knowledge-workspace-");

    await assert.rejects(
      () =>
        materializeQuartoProject({
          graph,
          workspace,
          bibliographyPath: bibliographyOf(repo),
        }),
      (error: unknown) => {
        assert.ok(error instanceof Error);
        assert.match(error.message, /alias/);
        assert.match(error.message, /page\.qmd/);
        return true;
      },
      `the alias ${JSON.stringify(alias)} must stop the projection`,
    );
  }
});

test("an alias that is only another name is projected untouched", async (t) => {
  const repo = await makeRepo(t);
  const { graph, result } = await project(t, repo);

  assert.deepEqual(graph.pages.get("ising/index.qmd")?.aliases, ["ising", "2d ising"]);
  assert.match(
    await readFile(path.join(result.projectDir, "ising", "index.qmd"), "utf8"),
    /aliases: \[ising, 2d ising\]/,
  );
});

test("the refusal names the shortcode and the line it sits on", async (t) => {
  // `env` is the case that motivated widening the rule, so it is asserted by
  // name: under Quarto 1.9.38 and `--no-execute`, `{{< env RESEARCH_LOOP_SECRET
  // >}}` renders as the build host's value of that variable and publishes it.
  // Frontmatter is scanned as well as the body, because Quarto expands
  // shortcodes in metadata too.
  const cases: readonly { lines: readonly string[]; message: RegExp }[] = [
    {
      lines: ["Nothing here.", "", "Secret is: {{< env RESEARCH_LOOP_SECRET >}}"],
      message: /`page\.qmd` line 9: .*`env` Quarto shortcode/u,
    },
    {
      lines: ["```", "{{< include ../../../etc/passwd >}}", "```"],
      message: /`page\.qmd` line 8: .*`include` Quarto shortcode/u,
    },
    {
      lines: ["Nothing here.", "", "{{< >}}"],
      message: /`page\.qmd` line 9: .*a Quarto shortcode/u,
    },
  ];

  for (const { lines, message } of cases) {
    const repo = await makeTree(t, {
      "index.qmd": qmd(
        { title: "Root", description: "The root." },
        indexBody(["page.qmd"]),
      ),
      "page.qmd": qmd(
        { title: "Page", description: "A page.", categories: "[theory]" },
        lines,
      ),
    });
    const graph = await loadKnowledge({ repoRoot: repo });
    const workspace = await makeTempDir(t, "knowledge-workspace-");

    await assert.rejects(
      () =>
        materializeQuartoProject({
          graph,
          workspace,
          bibliographyPath: bibliographyOf(repo),
        }),
      (error: unknown) => {
        assert.ok(error instanceof Error);
        assert.match(error.message, message);
        return true;
      },
      lines.join("\n"),
    );
  }

  // The scan is stateless: the same page refused twice is refused twice, so a
  // module-level regular expression cannot carry `lastIndex` from one page to
  // the next and let the second one through.
  const repo = await makeTree(t, {
    "index.qmd": qmd(
      { title: "Root", description: "The root." },
      indexBody(["a.qmd", "b.qmd"]),
    ),
    "a.qmd": qmd({ title: "A", description: "A page.", categories: "[theory]" }, [
      "{{< env RESEARCH_LOOP_SECRET >}}",
    ]),
    "b.qmd": qmd({ title: "B", description: "A page.", categories: "[theory]" }, [
      "{{< env RESEARCH_LOOP_SECRET >}}",
    ]),
  });
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const graph = await loadKnowledge({ repoRoot: repo });
    const workspace = await makeTempDir(t, "knowledge-workspace-");
    await assert.rejects(
      () =>
        materializeQuartoProject({
          graph,
          workspace,
          bibliographyPath: bibliographyOf(repo),
        }),
      /env` Quarto shortcode/u,
      `attempt ${attempt} must be refused`,
    );
  }
});

test("a page carrying no shortcode is projected untouched", async (t) => {
  // The refusal keys on `{{<`, so ordinary prose about Quarto, ordinary braces,
  // and inline code must all survive it byte-for-byte.
  const body = [
    "A page may talk about braces: {{ not a shortcode }} and {< nor this >}.",
    "",
    "`{{` and `<` next to each other in code spans are fine too.",
  ];
  const repo = await makeTree(t, {
    "index.qmd": qmd({ title: "Root", description: "The root." }, indexBody(["page.qmd"])),
    "page.qmd": qmd(
      { title: "Page", description: "A page.", categories: "[theory]" },
      body,
    ),
  });
  const { result } = await project(t, repo);

  const projected = await readFile(path.join(result.projectDir, "page.qmd"), "utf8");
  for (const line of body) {
    assert.ok(projected.includes(line), line);
  }
});
