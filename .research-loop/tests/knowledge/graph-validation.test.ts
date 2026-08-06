/**
 * The knowledge graph is the trust boundary of the published site: only pages
 * that survive `validateKnowledge` are ever projected, rendered, or resolved.
 * These tests therefore work on a real tree on disk — a clone of
 * `tests/fixtures/knowledge/valid` under `mkdtemp` — and mutate exactly one
 * property of it per case, so every diagnostic is pinned to the mistake that
 * causes it rather than to a hand-built graph object.
 */

import assert from "node:assert/strict";
import {
  appendFile,
  cp,
  mkdir,
  mkdtemp,
  readFile,
  realpath,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test, { type TestContext } from "node:test";

import { loadKnowledge } from "../../../src/lib/knowledge/graph.js";
import { validateGraph, validateKnowledge } from "../../../src/lib/knowledge/validate.js";
import type { Diagnostic } from "../../../src/lib/knowledge/types.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..", "..");
const FIXTURES = path.join(REPO_ROOT, ".research-loop", "tests", "fixtures", "knowledge");

/**
 * Builds a throwaway repository: the valid fixture as `knowledge/`, the
 * knowledge bibliography as `literature/ref.bib`. The temporary directory is
 * resolved through `realpath` so that a symlinked system temp directory (macOS
 * `/var` → `/private/var`) cannot be mistaken for a symlink inside the tree.
 */
async function makeRepo(t: TestContext): Promise<string> {
  const repo = await mkdtemp(path.join(await realpath(tmpdir()), "knowledge-graph-"));
  t.after(() => rm(repo, { recursive: true, force: true }));
  await cp(path.join(FIXTURES, "valid"), path.join(repo, "knowledge"), {
    recursive: true,
  });
  await mkdir(path.join(repo, "literature"), { recursive: true });
  await cp(path.join(FIXTURES, "ref.bib"), path.join(repo, "literature", "ref.bib"));
  return repo;
}

function knowledgeFile(repo: string, relative: string): string {
  return path.join(repo, "knowledge", ...relative.split("/"));
}

/** Replaces the first occurrence of `search`, failing if the fixture moved on. */
async function patch(
  repo: string,
  relative: string,
  search: string,
  replacement: string,
): Promise<void> {
  const file = knowledgeFile(repo, relative);
  const text = await readFile(file, "utf8");
  assert.ok(
    text.includes(search),
    `fixture ${relative} no longer contains ${JSON.stringify(search)}`,
  );
  await writeFile(file, text.replace(search, replacement));
}

async function append(repo: string, relative: string, text: string): Promise<void> {
  await appendFile(knowledgeFile(repo, relative), text);
}

async function writePage(
  repo: string,
  relative: string,
  lines: readonly string[],
): Promise<void> {
  const file = knowledgeFile(repo, relative);
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, `${lines.join("\n")}\n`);
}

/** `CODE repository/relative/path.qmd`, the shape every case asserts. */
function where(diagnostics: readonly Diagnostic[]): string[] {
  return diagnostics.map(
    (diagnostic) => `${diagnostic.code} ${diagnostic.location.file}`,
  );
}

/** `CODE file:line:column`, for the cases that pin exact positions. */
function at(diagnostics: readonly Diagnostic[]): string[] {
  return diagnostics.map(
    (diagnostic) =>
      `${diagnostic.code} ${diagnostic.location.file}:${diagnostic.location.line}:${diagnostic.location.column}`,
  );
}

test("the untouched fixture is a valid knowledge graph", async (t) => {
  const repo = await makeRepo(t);
  const report = await validateKnowledge({ repoRoot: repo });

  assert.deepEqual(where(report.diagnostics), []);
  assert.equal(report.ok, true);
});

test("the graph exposes curated containment, related edges, and assets", async (t) => {
  const repo = await makeRepo(t);
  const graph = await loadKnowledge({ repoRoot: repo });

  assert.equal(graph.repoRoot, repo);
  assert.equal(graph.knowledgeRoot, path.join(repo, "knowledge"));
  assert.deepEqual(
    [...graph.pages.keys()].sort(),
    [
      "index.qmd",
      "ising/index.qmd",
      "ising/proof.qmd",
      "ising/proposal.qmd",
      "ising/verified-code.qmd",
    ],
    "only .qmd files under the knowledge root are pages",
  );

  assert.deepEqual(graph.childrenByIndex.get("index.qmd"), ["ising/index.qmd"]);
  assert.deepEqual(graph.childrenByIndex.get("ising/index.qmd"), [
    "ising/proof.qmd",
    "ising/proposal.qmd",
    "ising/verified-code.qmd",
  ]);

  assert.equal(graph.parentByPage.get("index.qmd"), undefined);
  assert.equal(graph.parentByPage.get("ising/index.qmd"), "index.qmd");
  assert.equal(graph.parentByPage.get("ising/proof.qmd"), "ising/index.qmd");

  assert.deepEqual(graph.relatedByIndex.get("ising/index.qmd"), ["index.qmd"]);
  assert.deepEqual(
    graph.relatedByIndex.get("index.qmd"),
    [],
    "an index without `## Related topics` has no related edges",
  );

  assert.deepEqual(
    [...graph.assets],
    [["ising/diagram.svg", path.join(repo, "knowledge", "ising", "diagram.svg")]],
    "only referenced non-page files are assets",
  );

  const report = await validateGraph(graph, {
    bibliographyPath: path.join(repo, "literature", "ref.bib"),
  });
  assert.deepEqual(where(report.diagnostics), []);
});

test("children follow the curated reading order, not the filesystem", async (t) => {
  const repo = await makeRepo(t);
  await patch(
    repo,
    "ising/index.qmd",
    [
      "- [Proof of the critical temperature](proof.qmd)",
      "- [Proposal for a finite-size study](proposal.qmd)",
      "- [Verified transfer-matrix code](verified-code.qmd)",
    ].join("\n"),
    [
      "- [Verified transfer-matrix code](verified-code.qmd)",
      "- [Proposal for a finite-size study](proposal.qmd)",
      "- [Proof of the critical temperature](proof.qmd)",
    ].join("\n"),
  );

  const graph = await loadKnowledge({ repoRoot: repo });
  assert.deepEqual(graph.childrenByIndex.get("ising/index.qmd"), [
    "ising/verified-code.qmd",
    "ising/proposal.qmd",
    "ising/proof.qmd",
  ]);

  const report = await validateGraph(graph, {
    bibliographyPath: path.join(repo, "literature", "ref.bib"),
  });
  assert.deepEqual(where(report.diagnostics), [], "reordering a map stays valid");
});

test("the committed production scaffold is a valid knowledge graph", async () => {
  const report = await validateKnowledge({ repoRoot: REPO_ROOT });
  assert.deepEqual(where(report.diagnostics), []);
  assert.equal(report.ok, true);
});

interface Case {
  name: string;
  mutate: (repo: string) => Promise<void>;
  /** Every expected diagnostic as `CODE file`, in the order the report uses. */
  expected: readonly string[];
}

const CASES: readonly Case[] = [
  {
    name: "a directory with pages but no index.qmd is not a topic",
    mutate: (repo) =>
      writePage(repo, "ising/lattice/note.qmd", [
        "---",
        "title: Lattice geometry",
        "description: How the lattice is discretized.",
        "categories: [theory]",
        "---",
        "",
        "The lattice is square.",
      ]),
    expected: ["TOPIC_INDEX_MISSING knowledge/ising/lattice/index.qmd"],
  },
  {
    name: "a deleted topic index is reported once, with no orphan cascade",
    mutate: (repo) => rm(knowledgeFile(repo, "ising/index.qmd")),
    expected: [
      "LINK_MISSING knowledge/index.qmd",
      "TOPIC_INDEX_MISSING knowledge/ising/index.qmd",
    ],
  },
  {
    name: "an index without a `## Reading map` section is rejected",
    mutate: (repo) =>
      patch(
        repo,
        "ising/index.qmd",
        [
          "## Reading map",
          "",
          "- [Proof of the critical temperature](proof.qmd)",
          "- [Proposal for a finite-size study](proposal.qmd)",
          "- [Verified transfer-matrix code](verified-code.qmd)",
          "",
        ].join("\n"),
        "",
      ),
    expected: ["INDEX_READING_MAP_REQUIRED knowledge/ising/index.qmd"],
  },
  {
    name: "a direct child missing from its parent's reading map is an orphan",
    mutate: (repo) =>
      patch(
        repo,
        "ising/index.qmd",
        "- [Proposal for a finite-size study](proposal.qmd)\n",
        "",
      ),
    expected: ["ORPHAN_CHILD knowledge/ising/proposal.qmd"],
  },
  {
    name: "a reading map may not claim a page from another directory",
    mutate: async (repo) => {
      await patch(
        repo,
        "ising/index.qmd",
        "- [Proposal for a finite-size study](proposal.qmd)\n",
        "",
      );
      await append(repo, "index.qmd", "- [Proposal](ising/proposal.qmd)\n");
    },
    expected: [
      "NON_DIRECT_CHILD knowledge/index.qmd",
      "ORPHAN_CHILD knowledge/ising/proposal.qmd",
    ],
  },
  {
    name: "a reading map may not claim a file that is not a knowledge page",
    mutate: (repo) => append(repo, "index.qmd", "- [Diagram](ising/diagram.svg)\n"),
    expected: ["NON_DIRECT_CHILD knowledge/index.qmd"],
  },
  {
    name: "a page listed by two reading maps has two parents",
    mutate: (repo) => append(repo, "index.qmd", "- [Proof](ising/proof.qmd)\n"),
    expected: [
      "NON_DIRECT_CHILD knowledge/index.qmd",
      "DUPLICATE_PARENT knowledge/ising/proof.qmd",
    ],
  },
  {
    name: "reading maps that contain each other are a containment cycle",
    mutate: (repo) =>
      patch(
        repo,
        "ising/index.qmd",
        "- [Verified transfer-matrix code](verified-code.qmd)\n",
        "- [Verified transfer-matrix code](verified-code.qmd)\n- [Root](../index.qmd)\n",
      ),
    expected: [
      "CONTAINMENT_CYCLE knowledge/index.qmd",
      "NON_DIRECT_CHILD knowledge/ising/index.qmd",
    ],
  },
  {
    name: "a related topic must point at a topic index",
    mutate: (repo) =>
      patch(
        repo,
        "ising/index.qmd",
        "- [Research Loop Knowledge](../index.qmd)",
        "- [The proof](proof.qmd)",
      ),
    expected: ["RELATED_TARGET_NOT_INDEX knowledge/ising/index.qmd"],
  },
  {
    name: "a link is resolved after its query and fragment are removed",
    mutate: (repo) =>
      patch(
        repo,
        "ising/proof.qmd",
        "(proposal.qmd#open-questions)",
        "(missing.qmd?exact=1#open-questions)",
      ),
    expected: ["LINK_MISSING knowledge/ising/proof.qmd"],
  },
  {
    name: "a link to a directory is not a link to a page",
    mutate: (repo) => append(repo, "ising/proof.qmd", "\nSee [the topic](../ising).\n"),
    expected: ["LINK_MISSING knowledge/ising/proof.qmd"],
  },
  {
    name: "a relative link may not escape the knowledge tree",
    mutate: async (repo) => {
      await mkdir(path.join(repo, "outside"), { recursive: true });
      await writeFile(path.join(repo, "outside", "secret.md"), "secret\n");
      await append(
        repo,
        "ising/proof.qmd",
        "\nSee [the secret](../../outside/secret.md).\n",
      );
    },
    expected: ["LINK_OUTSIDE_KNOWLEDGE knowledge/ising/proof.qmd"],
  },
  {
    name: "an absolute path is not a knowledge link",
    mutate: (repo) =>
      append(repo, "ising/proof.qmd", "\nSee [the password file](/etc/passwd).\n"),
    expected: ["LINK_OUTSIDE_KNOWLEDGE knowledge/ising/proof.qmd"],
  },
  {
    name: "a foreign URL scheme is not a knowledge link",
    mutate: (repo) =>
      append(repo, "ising/proof.qmd", "\nSee [the trap](javascript:alert).\n"),
    expected: ["LINK_OUTSIDE_KNOWLEDGE knowledge/ising/proof.qmd"],
  },
  {
    name: "a zotero deep link is a sanctioned external target",
    mutate: (repo) =>
      append(
        repo,
        "ising/proof.qmd",
        "\nSee [the pdf](zotero://open-pdf/library/items/AB12CD34?page=7)"
        + " and [the item](zotero://select/library/items/AB12CD34).\n",
      ),
    expected: [],
  },
  {
    name: "schemes other than zotero keep failing",
    mutate: (repo) =>
      append(repo, "ising/proof.qmd", "\nSee [the relic](vbscript:MsgBox).\n"),
    expected: ["LINK_OUTSIDE_KNOWLEDGE knowledge/ising/proof.qmd"],
  },
  {
    name: "a link to a symlink inside the tree is rejected",
    mutate: async (repo) => {
      await symlink("diagram.svg", knowledgeFile(repo, "ising/figure.svg"));
      await append(repo, "ising/proof.qmd", "\n![A copy](figure.svg)\n");
    },
    expected: [
      "SYMLINK_FORBIDDEN knowledge/ising/figure.svg",
      "SYMLINK_FORBIDDEN knowledge/ising/proof.qmd",
    ],
  },
  {
    name: "a symlink that escapes the tree is rejected as a symlink",
    mutate: async (repo) => {
      await mkdir(path.join(repo, "outside"), { recursive: true });
      await writeFile(path.join(repo, "outside", "secret.md"), "secret\n");
      await symlink("../../outside/secret.md", knowledgeFile(repo, "ising/secret.md"));
      await append(repo, "ising/proof.qmd", "\nSee [the secret](secret.md).\n");
    },
    expected: [
      "SYMLINK_FORBIDDEN knowledge/ising/proof.qmd",
      "SYMLINK_FORBIDDEN knowledge/ising/secret.md",
    ],
  },
  {
    name: "a page reached through a symlinked directory is rejected",
    mutate: async (repo) => {
      await symlink(".", knowledgeFile(repo, "ising/mirror"));
      await append(repo, "ising/proof.qmd", "\nSee [a mirror](mirror/proof.qmd).\n");
    },
    expected: [
      "SYMLINK_FORBIDDEN knowledge/ising/mirror",
      "SYMLINK_FORBIDDEN knowledge/ising/proof.qmd",
    ],
  },
  {
    // Quarto renders `knowledge/` as a project and follows symbolic links, so a
    // symlinked page nobody references is published without ever having been
    // validated. The walk must report it, not silently skip it.
    name: "an unreferenced symlinked page is reported by discovery",
    mutate: async (repo) => {
      await mkdir(path.join(repo, "outside"), { recursive: true });
      await writeFile(
        path.join(repo, "outside", "smuggled.qmd"),
        "---\ntitle: Smuggled\n---\n\n<script>alert(1)</script>\n",
      );
      await symlink(
        "../../outside/smuggled.qmd",
        knowledgeFile(repo, "ising/smuggled.qmd"),
      );
    },
    expected: ["SYMLINK_FORBIDDEN knowledge/ising/smuggled.qmd"],
  },
  {
    name: "an unreferenced symlinked directory is reported without being walked",
    mutate: async (repo) => {
      await mkdir(path.join(repo, "outside", "topic"), { recursive: true });
      await writeFile(
        path.join(repo, "outside", "topic", "index.qmd"),
        "---\ntitle: Outside\n---\n",
      );
      await symlink("../../outside/topic", knowledgeFile(repo, "ising/linked"));
    },
    expected: ["SYMLINK_FORBIDDEN knowledge/ising/linked"],
  },
  {
    // A dot directory is not an input to Quarto and not a page here, so a file
    // inside one may not become an asset either: the projection copies exactly
    // what `assets` names.
    name: "an asset under a dot directory is not part of the tree",
    mutate: async (repo) => {
      await mkdir(knowledgeFile(repo, ".hidden"), { recursive: true });
      await writeFile(knowledgeFile(repo, ".hidden/img.svg"), "<svg/>\n");
      await append(repo, "ising/proof.qmd", "\n![Hidden](../.hidden/img.svg)\n");
    },
    expected: ["LINK_OUTSIDE_KNOWLEDGE knowledge/ising/proof.qmd"],
  },
  {
    name: "an asset under an underscore directory is not part of the tree",
    mutate: async (repo) => {
      await mkdir(knowledgeFile(repo, "ising/_private"), { recursive: true });
      await writeFile(knowledgeFile(repo, "ising/_private/img.svg"), "<svg/>\n");
      await append(repo, "ising/proof.qmd", "\n![Private](_private/img.svg)\n");
    },
    expected: ["LINK_OUTSIDE_KNOWLEDGE knowledge/ising/proof.qmd"],
  },
  {
    name: "an underscore-prefixed page is not part of the tree",
    mutate: async (repo) => {
      await writePage(repo, "ising/_partial.qmd", [
        "---",
        "title: A fragment",
        "description: An include fragment Quarto never renders on its own.",
        "categories: [theory]",
        "---",
        "",
        "Included prose.",
      ]);
      await append(repo, "ising/proof.qmd", "\nSee [the fragment](_partial.qmd).\n");
    },
    expected: ["LINK_OUTSIDE_KNOWLEDGE knowledge/ising/proof.qmd"],
  },
  {
    // The curated sections mean nothing on a content page: no sidebar, no
    // containment, no related edges. Their links are still checked.
    name: "a content page may not declare the curated sections",
    mutate: (repo) =>
      append(
        repo,
        "ising/proposal.qmd",
        [
          "",
          "## Reading map",
          "",
          "- [Nowhere](nowhere.qmd)",
          "",
          "## Related topics",
          "",
          "- [The topic](index.qmd)",
          "",
        ].join("\n"),
      ),
    expected: [
      "RESERVED_SECTION_FORBIDDEN knowledge/ising/proposal.qmd",
      "LINK_MISSING knowledge/ising/proposal.qmd",
      "RESERVED_SECTION_FORBIDDEN knowledge/ising/proposal.qmd",
    ],
  },
  {
    // The declaration comes from the parser's own heading rule, so a fenced
    // sample that merely shows `## Reading map` never counts as one. A cheaper
    // scan of the body text would call this index curated and publish a topic
    // whose children are unreachable.
    name: "a reading map heading inside a code fence is not a declaration",
    mutate: (repo) =>
      patch(
        repo,
        "ising/index.qmd",
        "## Reading map\n",
        "```markdown\n## Reading map\n```\n",
      ),
    expected: ["INDEX_READING_MAP_REQUIRED knowledge/ising/index.qmd"],
  },
  {
    name: "a citation must exist in the configured bibliography",
    mutate: (repo) => patch(repo, "ising/proof.qmd", "@fixture2026", "@missing2026"),
    expected: ["CITATION_MISSING knowledge/ising/proof.qmd"],
  },
  {
    // `aliases` is on the frontmatter allowlist because the resolver reads it
    // as synonyms; Quarto reads it as redirect paths. The projection already
    // refuses these, but only once a build is under way — validation is where
    // an author is told, before anything renders.
    name: "an alias Quarto would read as a path is rejected",
    mutate: (repo) =>
      patch(
        repo,
        "ising/index.qmd",
        "aliases: [ising, 2d ising]",
        'aliases: [ising, "../../../../../../tmp/quarto-alias-escape"]',
      ),
    expected: ["ALIAS_PATH_FORBIDDEN knowledge/ising/index.qmd"],
  },
  {
    name: "a raw script tag is rejected",
    mutate: (repo) =>
      append(repo, "ising/proposal.qmd", "\n<script>alert(1)</script>\n"),
    expected: ["SCRIPT_FORBIDDEN knowledge/ising/proposal.qmd"],
  },
  {
    name: "a raw inline event handler is rejected",
    mutate: (repo) =>
      append(repo, "ising/proposal.qmd", '\n<div onclick="alert(1)">click</div>\n'),
    expected: ["INLINE_HANDLER_FORBIDDEN knowledge/ising/proposal.qmd"],
  },
  {
    // Every parse diagnostic reaches the report, which is what makes the
    // frontmatter allowlist a boundary rather than a suggestion: a page that
    // tries to turn rendering into execution can never be published, however
    // well-formed the rest of the graph is. Parser-level codes are asserted in
    // `parser.test.ts`; the graph's contract is only that it surfaces them.
    name: "a page diagnostic from the parser fails validation",
    mutate: (repo) =>
      patch(
        repo,
        "ising/proof.qmd",
        "categories: [theory]",
        "categories: [theory]\nexecute: true",
      ),
    expected: ["FRONTMATTER_KEY_FORBIDDEN knowledge/ising/proof.qmd"],
  },
];

for (const validationCase of CASES) {
  test(validationCase.name, async (t) => {
    const repo = await makeRepo(t);
    await validationCase.mutate(repo);

    const report = await validateKnowledge({ repoRoot: repo });
    assert.deepEqual(where(report.diagnostics), [...validationCase.expected]);
    assert.equal(report.ok, validationCase.expected.length === 0);
  });
}

/**
 * Every alias form Quarto would turn into a path. This is the same list
 * `quarto-project.test.ts` holds the projection to: one rule, one predicate,
 * enforced at review time here and again at build time there.
 */
const PATH_LIKE_ALIASES: readonly string[] = [
  "../../../../../../tmp/quarto-alias-escape",
  "/etc/passwd",
  "a/b",
  "..",
  ".",
  "~",
  "windows\\path",
];

test("every alias Quarto would read as a path fails validation", async (t) => {
  for (const alias of PATH_LIKE_ALIASES) {
    const repo = await makeRepo(t);
    await patch(
      repo,
      "ising/index.qmd",
      "aliases: [ising, 2d ising]",
      `aliases: [${JSON.stringify(alias)}]`,
    );

    const report = await validateKnowledge({ repoRoot: repo });

    assert.deepEqual(
      where(report.diagnostics),
      ["ALIAS_PATH_FORBIDDEN knowledge/ising/index.qmd"],
      `the alias ${JSON.stringify(alias)} must be reported, and nothing else`,
    );
    assert.ok(
      report.diagnostics[0].message.includes(JSON.stringify(alias)),
      `the refusal must quote the alias: ${report.diagnostics[0].message}`,
    );
    assert.match(report.diagnostics[0].message, /redirect/);
  }
});

test("an alias that is only another name for the page stays valid", async (t) => {
  const repo = await makeRepo(t);
  await patch(
    repo,
    "ising/index.qmd",
    "aliases: [ising, 2d ising]",
    'aliases: [ising, "2d ising", "ising v1.2", "quspin hamiltonian"]',
  );

  const report = await validateKnowledge({ repoRoot: repo });

  assert.deepEqual(
    where(report.diagnostics),
    [],
    "a period inside a synonym is not a path; only a bare `.` or `..` is",
  );
});

test("excluded and symlinked files never enter the graph", async (t) => {
  const repo = await makeRepo(t);
  await mkdir(knowledgeFile(repo, ".hidden"), { recursive: true });
  await writeFile(knowledgeFile(repo, ".hidden/img.svg"), "<svg/>\n");
  await mkdir(knowledgeFile(repo, "ising/_private"), { recursive: true });
  await writeFile(knowledgeFile(repo, "ising/_private/img.svg"), "<svg/>\n");
  await symlink("diagram.svg", knowledgeFile(repo, "ising/figure.svg"));
  await append(
    repo,
    "ising/proof.qmd",
    [
      "",
      "![Hidden](../.hidden/img.svg)",
      "",
      "![Private](_private/img.svg)",
      "",
      "![Linked](figure.svg)",
      "",
    ].join("\n"),
  );

  const graph = await loadKnowledge({ repoRoot: repo });

  assert.deepEqual(
    [...graph.assets.keys()],
    ["ising/diagram.svg"],
    "the projection copies what `assets` names, so nothing unvalidated may enter it",
  );
  assert.equal(graph.pages.has(".hidden/img.svg"), false);
});

test("diagnostics are sorted by file, line, column, then code", async (t) => {
  const repo = await makeRepo(t);
  await append(repo, "index.qmd", "\n[a missing topic](nowhere/index.qmd)\n");
  await writePage(repo, "ising/proof.qmd", [
    /*  1 */ "---",
    /*  2 */ "title: Proof of the critical temperature",
    /*  3 */ "description: The duality argument that fixes the critical temperature.",
    /*  4 */ "categories: [theory]",
    /*  5 */ "---",
    /*  6 */ "",
    /*  7 */ "[missing link](missing.qmd)",
    /*  8 */ "",
    /*  9 */ "[@nowhere2026] is not in the bibliography.",
    /* 10 */ "",
    /* 11 */ "<script>alert(1)</script>",
    /* 12 */ "",
    /* 13 */ '<div onclick="alert(1)">click</div>',
  ]);

  const report = await validateKnowledge({ repoRoot: repo });

  assert.deepEqual(at(report.diagnostics), [
    "LINK_MISSING knowledge/index.qmd:12:1",
    "LINK_MISSING knowledge/ising/proof.qmd:7:1",
    "CITATION_MISSING knowledge/ising/proof.qmd:9:2",
    "SCRIPT_FORBIDDEN knowledge/ising/proof.qmd:11:1",
    "INLINE_HANDLER_FORBIDDEN knowledge/ising/proof.qmd:13:6",
  ]);
});

test("an unclosed fence fails the tree instead of hiding the page below it", async (t) => {
  // Reproduced against Quarto 1.9.38 before this diagnostic existed: the page
  // below validated clean — `make knowledge-check` printed "the trusted tree is
  // valid" — and the rendered `proof.html` carried
  // `href="../../../../../../../../etc/hostname"`. remark runs an unclosed
  // fence to end of file and calls all of it code, so the escaping link and the
  // unknown citekey were never in the graph to be checked; Pandoc closes the
  // fence at end of file, ignores the leftover, and renders the tail. An
  // unclosed fence is a typo, not an attack, which is exactly why it may not
  // silently take half a page out of validation.
  const repo = await makeRepo(t);
  await writePage(repo, "ising/proof.qmd", [
    /*  1 */ "---",
    /*  2 */ "title: Proof of the critical temperature",
    /*  3 */ "description: The duality argument that fixes the critical temperature.",
    /*  4 */ "categories: [theory]",
    /*  5 */ "---",
    /*  6 */ "",
    /*  7 */ "```python",
    /*  8 */ 'print("unclosed fence")',
    /*  9 */ "",
    /* 10 */ "[escape](../../../../../../../../etc/hostname)",
    /* 11 */ "![img](../../../../../../../../etc/hostname)",
    /* 12 */ "@definitely_not_in_the_bibliography",
  ]);

  const report = await validateKnowledge({ repoRoot: repo });

  assert.equal(report.ok, false);
  assert.deepEqual(at(report.diagnostics), [
    "FENCE_UNCLOSED knowledge/ising/proof.qmd:7:1",
  ]);
  // One diagnostic, not four: the link, image, and citation below the opener
  // are still invisible to every other check. That is the whole reason this one
  // has to fail the page — it reports the *cause*, and the author closes the
  // fence and gets the other three.
  assert.match(report.diagnostics[0]?.message ?? "", /never closed/);

  // Closing the fence turns the silence into the three real diagnostics.
  await patch(repo, "ising/proof.qmd", 'print("unclosed fence")\n', 'print("ok")\n```\n');
  assert.deepEqual(at((await validateKnowledge({ repoRoot: repo })).diagnostics), [
    "LINK_OUTSIDE_KNOWLEDGE knowledge/ising/proof.qmd:11:1",
    "LINK_OUTSIDE_KNOWLEDGE knowledge/ising/proof.qmd:12:1",
    "CITATION_MISSING knowledge/ising/proof.qmd:13:1",
  ]);
});

test("every diagnostic message names the page and the problem", async (t) => {
  const repo = await makeRepo(t);
  await patch(
    repo,
    "ising/index.qmd",
    "- [Proposal for a finite-size study](proposal.qmd)\n",
    "",
  );

  const report = await validateKnowledge({ repoRoot: repo });
  const [orphan] = report.diagnostics;

  assert.equal(orphan?.code, "ORPHAN_CHILD");
  assert.match(orphan?.message ?? "", /knowledge\/ising\/index\.qmd/);
});

test("a graph is validated against the bibliography it is given", async (t) => {
  const repo = await makeRepo(t);
  await writeFile(
    path.join(repo, "literature", "other.bib"),
    "@article{other2026,\n  title = {Another fixture},\n  keywords = {ed}\n}\n",
  );

  const report = await validateKnowledge({
    repoRoot: repo,
    bibliographyPath: path.join(repo, "literature", "other.bib"),
  });

  assert.deepEqual(where(report.diagnostics), [
    "CITATION_MISSING knowledge/ising/proof.qmd",
  ]);
});
