import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { parseKnowledgePage } from "../../lib/knowledge/parser.js";
import {
  ALLOWED_FRONTMATTER_KEYS,
  KNOWLEDGE_CATEGORIES,
  type ParsedKnowledgePage,
} from "../../lib/knowledge/types.js";

const REPO_ROOT = "/repo";
const KNOWLEDGE_ROOT = "/repo/knowledge";

function parse(relativePath: string, source: string): ParsedKnowledgePage {
  return parseKnowledgePage({
    repoRoot: REPO_ROOT,
    knowledgeRoot: KNOWLEDGE_ROOT,
    absolutePath: path.join(KNOWLEDGE_ROOT, relativePath),
    source,
  });
}

/** The diagnostics of a page, reduced to the parts a test pins down. */
function diagnostics(
  page: ParsedKnowledgePage,
): { code: string; line: number; column: number }[] {
  return page.parseDiagnostics.map((diagnostic) => ({
    code: diagnostic.code,
    line: diagnostic.location.line,
    column: diagnostic.location.column,
  }));
}

function codes(page: ParsedKnowledgePage): string[] {
  return page.parseDiagnostics.map((diagnostic) => diagnostic.code);
}

function targets(links: ParsedKnowledgePage["localLinks"]): string[] {
  return links.map((link) => link.target);
}

/** Wraps body text in the minimal valid frontmatter of a content page. */
function contentPage(body: string, category = "theory"): string {
  return [
    "---",
    "title: A page",
    "description: A description.",
    `categories: [${category}]`,
    "---",
    "",
    body,
  ].join("\n");
}

/** Wraps body text in the minimal valid frontmatter of an index page. */
function indexPage(body: string): string {
  return ["---", "title: A topic", "description: A description.", "---", "", body].join(
    "\n",
  );
}

// The line numbers of this fixture are asserted verbatim below; keep them in
// sync with the comments when editing.
const INDEX_SOURCE = [
  /*  1 */ "---",
  /*  2 */ "title: Ising model",
  /*  3 */ "description: Critical behaviour of the two-dimensional Ising model.",
  /*  4 */ "aliases: [ising, 2d ising]",
  /*  5 */ "---",
  /*  6 */ "",
  /*  7 */ "Prose links to [the notes](notes.qmd) and cites [@fixture2026].",
  /*  8 */ "",
  /*  9 */ "![Phase diagram](diagram.svg)",
  /* 10 */ "",
  /* 11 */ "```python",
  /* 12 */ "# [@ignored] is not a citation",
  /* 13 */ 'print("[Not a link](nowhere.qmd)")',
  /* 14 */ "```",
  /* 15 */ "",
  /* 16 */ '<script>alert("x")</script>',
  /* 17 */ "",
  /* 18 */ "<div onclick=\"alert('x')\">click</div>",
  /* 19 */ "",
  /* 20 */ "## Reading map",
  /* 21 */ "",
  /* 22 */ "- [Proof](proof.qmd)",
  /* 23 */ "- [Honeycomb](honeycomb/index.qmd)",
  /* 24 */ "",
  /* 25 */ "## Related topics",
  /* 26 */ "",
  /* 27 */ "- [QuSpin](../software/quspin/index.qmd)",
  /* 28 */ "",
].join("\n");

test("the parser contract exposes the fixed categories and frontmatter allowlist", () => {
  assert.deepEqual([...KNOWLEDGE_CATEGORIES], ["theory", "experiment", "codes"]);
  assert.deepEqual(
    [...ALLOWED_FRONTMATTER_KEYS],
    ["title", "description", "categories", "aliases"],
  );
});

test("parses a valid index page into typed knowledge", () => {
  const page = parse("ising/index.qmd", INDEX_SOURCE);

  assert.deepEqual(diagnostics(page), []);
  assert.equal(page.id, "ising/index.qmd");
  assert.equal(page.absolutePath, "/repo/knowledge/ising/index.qmd");
  assert.equal(page.topicId, "ising/index.qmd");
  assert.equal(page.kind, "index");
  assert.equal(page.title, "Ising model");
  assert.equal(
    page.description,
    "Critical behaviour of the two-dimensional Ising model.",
  );
  assert.equal(page.category, undefined);
  assert.deepEqual([...page.aliases], ["ising", "2d ising"]);

  // The body is everything after the closing delimiter, frontmatter excluded.
  assert.ok(!page.body.includes("title: Ising model"));
  assert.ok(page.body.startsWith("\nProse links to "));
  assert.ok(page.body.endsWith("\n"));
});

test("collects reading-map and related-topic entries with true file locations", () => {
  const page = parse("ising/index.qmd", INDEX_SOURCE);

  assert.deepEqual(
    page.readingMap.map((link) => ({ ...link, location: { ...link.location } })),
    [
      {
        kind: "link",
        label: "Proof",
        target: "proof.qmd",
        location: { file: "knowledge/ising/index.qmd", line: 22, column: 3 },
      },
      {
        kind: "link",
        label: "Honeycomb",
        target: "honeycomb/index.qmd",
        location: { file: "knowledge/ising/index.qmd", line: 23, column: 3 },
      },
    ],
  );

  assert.deepEqual(
    page.relatedTopics.map((link) => ({ ...link, location: { ...link.location } })),
    [
      {
        kind: "link",
        label: "QuSpin",
        target: "../software/quspin/index.qmd",
        location: { file: "knowledge/ising/index.qmd", line: 27, column: 3 },
      },
    ],
  );
});

test("collects every local link and image, and skips fenced code", () => {
  const page = parse("ising/index.qmd", INDEX_SOURCE);

  assert.deepEqual(targets(page.localLinks), [
    "notes.qmd",
    "diagram.svg",
    "proof.qmd",
    "honeycomb/index.qmd",
    "../software/quspin/index.qmd",
  ]);

  const [notes, diagram] = page.localLinks;
  assert.deepEqual({ ...notes, location: { ...notes.location } }, {
    kind: "link",
    label: "the notes",
    target: "notes.qmd",
    location: { file: "knowledge/ising/index.qmd", line: 7, column: 16 },
  });
  assert.deepEqual({ ...diagram, location: { ...diagram.location } }, {
    kind: "image",
    label: "Phase diagram",
    target: "diagram.svg",
    location: { file: "knowledge/ising/index.qmd", line: 9, column: 1 },
  });
});

test("collects citations from text and ignores fenced code", () => {
  const page = parse("ising/index.qmd", INDEX_SOURCE);

  assert.deepEqual(
    page.citations.map((citation) => ({
      key: citation.key,
      line: citation.location.line,
      column: citation.location.column,
    })),
    [{ key: "fixture2026", line: 7, column: 50 }],
  );
});

test("reports raw script tags and inline event handlers", () => {
  const page = parse("ising/index.qmd", INDEX_SOURCE);

  assert.deepEqual(
    page.unsafeHtml.map((entry) => ({
      kind: entry.kind,
      line: entry.location.line,
      column: entry.location.column,
    })),
    [
      { kind: "script", line: 16, column: 1 },
      { kind: "inline-handler", line: 18, column: 6 },
    ],
  );
});

test("finds unsafe HTML that tag-shaped scanning would miss", () => {
  const page = parse(
    "ising/index.qmd",
    indexPage(
      // `indexPage` puts the first body line on source line 6.
      [
        /*  6 */ '<div title="a>b" onclick="alert(1)">quoted angle bracket</div>',
        /*  7 */ "",
        /*  8 */ "<a",
        /*  9 */ '  onmouseover="alert(2)"',
        /* 10 */ '  href="notes.qmd">split across lines</a>',
        /* 11 */ "",
        /* 12 */ '<SCRIPT SRC="evil.js"></SCRIPT>',
        /* 13 */ "",
        /* 14 */ "Inline <span ONFOCUS=\"alert(3)\">handler</span> in a paragraph.",
        /* 15 */ "",
        /* 16 */ "```html",
        /* 17 */ '<script>alert("in a fence")</script>',
        /* 18 */ "```",
        /* 19 */ "",
        /* 20 */ '<div on="not a handler" data-only="x">safe</div>',
        /* 21 */ "",
      ].join("\n"),
    ),
  );

  assert.deepEqual(
    page.unsafeHtml.map((entry) => ({
      kind: entry.kind,
      line: entry.location.line,
      column: entry.location.column,
    })),
    [
      { kind: "inline-handler", line: 6, column: 18 },
      { kind: "inline-handler", line: 9, column: 3 },
      { kind: "script", line: 12, column: 1 },
      { kind: "inline-handler", line: 14, column: 14 },
    ],
  );
});

test("finds event handlers whatever delimiter precedes them", () => {
  const cases: readonly { markup: string; column: number }[] = [
    { markup: "<svg/onload=alert(1)>", column: 6 },
    { markup: '<img/onerror="alert(1)" src=x>', column: 6 },
    { markup: '<div id="a"onclick=alert(1)>x</div>', column: 12 },
    { markup: "<div\tonmouseover=alert(1)>x</div>", column: 6 },
    { markup: "<a href='x'ONFOCUS=alert(1)>x</a>", column: 12 },
  ];

  for (const { markup, column } of cases) {
    const page = parse("ising/index.qmd", indexPage(`${markup}\n`));

    assert.deepEqual(
      page.unsafeHtml.map((entry) => ({
        kind: entry.kind,
        line: entry.location.line,
        column: entry.location.column,
      })),
      [{ kind: "inline-handler", line: 6, column }],
      markup,
    );
  }
});

test("does not mistake prose or a URL query parameter for a handler", () => {
  const page = parse(
    "ising/index.qmd",
    indexPage(
      [
        "Sensors turn online=true when the run starts, and onerror=abort is a flag.",
        "",
        "See [the dashboard](https://example.com/runs?online=true&onerror=abort).",
        "",
        "<p>Documentation says onclick handlers are banned.</p>",
        "",
        '<div data-onclick="x" data-only="y">safe</div>',
        "",
      ].join("\n"),
    ),
  );

  assert.deepEqual(page.unsafeHtml, []);
});

test("scans Pandoc raw blocks, which are code nodes carrying raw HTML", () => {
  const page = parse(
    "ising/index.qmd",
    indexPage(
      [
        /*  6 */ "```{=html}",
        /*  7 */ '<script>alert("fenced raw")</script>',
        /*  8 */ "```",
        /*  9 */ "",
        /* 10 */ "Inline `<img src=x onerror=alert(1)>`{=html} raw block.",
        /* 11 */ "",
        /* 12 */ "```html",
        /* 13 */ '<script>alert("ordinary fence")</script>',
        /* 14 */ "```",
        /* 15 */ "",
        /* 16 */ "Ordinary span `<script>alert(2)</script>` stays escaped.",
        /* 17 */ "",
      ].join("\n"),
    ),
  );

  assert.deepEqual(
    page.unsafeHtml.map((entry) => ({
      kind: entry.kind,
      line: entry.location.line,
      column: entry.location.column,
    })),
    [
      { kind: "script", line: 7, column: 1 },
      { kind: "inline-handler", line: 10, column: 20 },
    ],
  );
});

test("reports a Pandoc metadata block written after the frontmatter", () => {
  const page = parse(
    "ising/index.qmd",
    indexPage(
      [
        /*  6 */ "Prose before the block.",
        /*  7 */ "",
        /*  8 */ "---",
        /*  9 */ "execute:",
        /* 10 */ "  enabled: true",
        /* 11 */ "header-includes: |",
        /* 12 */ "  <script>alert(1)</script>",
        /* 13 */ "---",
        /* 14 */ "",
        /* 15 */ "Prose after the block.",
        /* 16 */ "",
      ].join("\n"),
    ),
  );

  assert.deepEqual(diagnostics(page), [
    { code: "FRONTMATTER_INVALID", line: 8, column: 1 },
  ]);
  assert.match(page.parseDiagnostics[0]?.message ?? "", /metadata block/i);

  // A block closed by `...` counts too, and the frontmatter is still read.
  const dots = parse(
    "ising/index.qmd",
    indexPage(["Prose.", "", "---", "resources: [../../secrets]", "...", ""].join("\n")),
  );
  assert.deepEqual(diagnostics(dots), [
    { code: "FRONTMATTER_INVALID", line: 8, column: 1 },
  ]);
  assert.equal(dots.title, "A topic");
});

test("leaves horizontal rules and fenced YAML samples alone", () => {
  const page = parse(
    "ising/index.qmd",
    indexPage(
      [
        "Before the rule.",
        "",
        "---",
        "",
        "After the rule.",
        "",
        "```yaml",
        "---",
        "execute:",
        "  enabled: true",
        "---",
        "```",
        "",
        "---",
        "Not a mapping, just prose between rules.",
        "---",
        "",
      ].join("\n"),
    ),
  );

  assert.deepEqual(diagnostics(page), []);
});

test("resolves reference-style links, images, and bare definitions", () => {
  const page = parse(
    "ising/index.qmd",
    indexPage(
      [
        /*  6 */ "## Reading map",
        /*  7 */ "",
        /*  8 */ "- [Proof][proof]",
        /*  9 */ "- [Proposal]",
        /* 10 */ "- [Missing][nowhere]",
        /* 11 */ "",
        /* 12 */ "## Related topics",
        /* 13 */ "",
        /* 14 */ "- [QuSpin][quspin]",
        /* 15 */ "",
        /* 16 */ "Body ![Figure][fig] and [external][site].",
        /* 17 */ "",
        /* 18 */ "[proof]: proof.qmd",
        /* 19 */ "[Proposal]: proposal.qmd",
        /* 20 */ "[quspin]: ../software/quspin/index.qmd",
        /* 21 */ "[fig]: diagram.svg",
        /* 22 */ "[site]: https://example.com",
        /* 23 */ "[evil]: javascript:alert(1)",
        /* 24 */ "",
      ].join("\n"),
    ),
  );

  assert.deepEqual(diagnostics(page), []);
  assert.deepEqual(targets(page.readingMap), ["proof.qmd", "proposal.qmd"]);
  assert.deepEqual(
    page.readingMap.map((link) => ({ label: link.label, line: link.location.line })),
    [
      { label: "Proof", line: 8 },
      { label: "Proposal", line: 9 },
    ],
  );
  assert.deepEqual(targets(page.relatedTopics), ["../software/quspin/index.qmd"]);

  // Used definitions are reported at the usage; an unused one at its own line,
  // so a dangling `javascript:` target still reaches link validation.
  assert.deepEqual(
    page.localLinks.map((link) => ({
      kind: link.kind,
      target: link.target,
      line: link.location.line,
    })),
    [
      { kind: "link", target: "proof.qmd", line: 8 },
      { kind: "link", target: "proposal.qmd", line: 9 },
      { kind: "link", target: "../software/quspin/index.qmd", line: 14 },
      { kind: "image", target: "diagram.svg", line: 16 },
      { kind: "link", target: "javascript:alert(1)", line: 23 },
    ],
  );
});

test("a reference-style duplicate is still a duplicate", () => {
  const page = parse(
    "ising/index.qmd",
    indexPage(
      [
        "## Reading map",
        "",
        "- [Proof](proof.qmd)",
        "- [Proof again][proof]",
        "",
        "[proof]: proof.qmd",
        "",
      ].join("\n"),
    ),
  );

  assert.deepEqual(diagnostics(page), [
    { code: "READING_MAP_DUPLICATE", line: 9, column: 3 },
  ]);
  assert.deepEqual(targets(page.readingMap), ["proof.qmd"]);
});

test("derives ids and owning topic ids from the path", () => {
  const cases: readonly {
    relativePath: string;
    id: string;
    topicId: string;
    kind: string;
  }[] = [
    { relativePath: "index.qmd", id: "index.qmd", topicId: "index.qmd", kind: "index" },
    {
      relativePath: "overview.qmd",
      id: "overview.qmd",
      topicId: "index.qmd",
      kind: "content",
    },
    {
      relativePath: "ising/index.qmd",
      id: "ising/index.qmd",
      topicId: "ising/index.qmd",
      kind: "index",
    },
    {
      relativePath: "ising/proof.qmd",
      id: "ising/proof.qmd",
      topicId: "ising/index.qmd",
      kind: "content",
    },
    {
      relativePath: "software/quspin/api/hamiltonian.qmd",
      id: "software/quspin/api/hamiltonian.qmd",
      topicId: "software/quspin/api/index.qmd",
      kind: "content",
    },
  ];

  for (const expected of cases) {
    const page = parse(
      expected.relativePath,
      expected.relativePath.endsWith("index.qmd")
        ? indexPage("Body.\n")
        : contentPage("Body.\n"),
    );

    assert.equal(page.id, expected.id, expected.relativePath);
    assert.equal(page.topicId, expected.topicId, expected.relativePath);
    assert.equal(page.kind, expected.kind, expected.relativePath);
    assert.equal(
      page.absolutePath,
      path.join(KNOWLEDGE_ROOT, expected.relativePath),
      expected.relativePath,
    );
    assert.ok(!page.id.includes("\\"), "ids use POSIX separators");
    assert.ok(!page.topicId.includes("\\"), "topic ids use POSIX separators");
  }
});

test("reports diagnostic locations as repository-relative POSIX paths", () => {
  const page = parse("ising/proof.qmd", "# No frontmatter\n");

  assert.deepEqual(diagnostics(page), [
    { code: "FRONTMATTER_MISSING", line: 1, column: 1 },
  ]);
  assert.equal(page.parseDiagnostics[0]?.location.file, "knowledge/ising/proof.qmd");
  assert.ok((page.parseDiagnostics[0]?.message.length ?? 0) > 0);
});

test("accepts each allowed category on a content page", () => {
  for (const category of KNOWLEDGE_CATEGORIES) {
    const page = parse("ising/proof.qmd", contentPage("Body.\n", category));

    assert.deepEqual(diagnostics(page), [], category);
    assert.equal(page.category, category);
    assert.equal(page.title, "A page");
    assert.equal(page.description, "A description.");
    assert.deepEqual([...page.aliases], []);
  }
});

test("only direct list-item links beneath the reserved headings are structural", () => {
  const source = [
    /*  1 */ "---",
    /*  2 */ "title: Scoping",
    /*  3 */ "description: Reserved headings capture direct list-item links only.",
    /*  4 */ "---",
    /*  5 */ "",
    /*  6 */ "## Reading map",
    /*  7 */ "",
    /*  8 */ "Prose with [a prose link](prose.qmd) does not count.",
    /*  9 */ "",
    /* 10 */ "- [Direct entry](direct.qmd)",
    /* 11 */ "- plain text without a link",
    /* 12 */ "- [Parent entry](parent.qmd)",
    /* 13 */ "  - [Nested entry](nested.qmd)",
    /* 14 */ "- `[Inline code](inline.qmd)` is not a link",
    /* 15 */ "",
    /* 16 */ "```markdown",
    /* 17 */ "## Reading map",
    /* 18 */ "",
    /* 19 */ "- [Fenced entry](fenced.qmd)",
    /* 20 */ "```",
    /* 21 */ "",
    /* 22 */ "### Nested unrelated heading",
    /* 23 */ "",
    /* 24 */ "- [After nested heading](after-heading.qmd)",
    /* 25 */ "",
    /* 26 */ "## Related topics",
    /* 27 */ "",
    /* 28 */ "- [Related](../software/quspin/index.qmd)",
    /* 29 */ "- also plain text",
    /* 30 */ "",
    /* 31 */ "## Other prose",
    /* 32 */ "",
    /* 33 */ "- [Other](other.qmd)",
    /* 34 */ "",
  ].join("\n");

  const page = parse("ising/index.qmd", source);

  assert.deepEqual(diagnostics(page), []);
  assert.deepEqual(targets(page.readingMap), ["direct.qmd", "parent.qmd"]);
  assert.deepEqual(page.readingMap.map((link) => link.location.line), [10, 12]);
  assert.deepEqual(targets(page.relatedTopics), ["../software/quspin/index.qmd"]);
  assert.deepEqual(page.relatedTopics.map((link) => link.location.line), [28]);

  // Every real link is still reported for link checking, in document order.
  assert.deepEqual(targets(page.localLinks), [
    "prose.qmd",
    "direct.qmd",
    "parent.qmd",
    "nested.qmd",
    "after-heading.qmd",
    "../software/quspin/index.qmd",
    "other.qmd",
  ]);
});

test("a reserved heading only counts at level two and outside code", () => {
  const source = [
    "---",
    "title: Levels",
    "description: Only level-two reserved headings are structural.",
    "---",
    "",
    "# Reading map",
    "",
    "- [Level one](one.qmd)",
    "",
    "### Reading map",
    "",
    "- [Level three](three.qmd)",
    "",
    "## reading map",
    "",
    "- [Lowercase](lower.qmd)",
    "",
    "## Related topics extra",
    "",
    "- [Suffixed](suffixed.qmd)",
    "",
  ].join("\n");

  const page = parse("ising/index.qmd", source);

  assert.deepEqual(diagnostics(page), []);
  assert.deepEqual(targets(page.readingMap), []);
  assert.deepEqual(targets(page.relatedTopics), []);
  assert.equal(page.localLinks.length, 4);
});

test("separates local targets from external ones", () => {
  const source = indexPage(
    [
      "[External](https://example.com/page) and [Insecure](http://example.com).",
      "",
      "[Mail](mailto:someone@example.com) and [Fragment](#section).",
      "",
      "[Anchored](notes.qmd#anchor) and [Queried](notes.qmd?x=1).",
      "",
      "![Figure](figures/plot.png)",
      "",
      "[Escape](../../outside.qmd) and [Absolute](/etc/passwd).",
      "",
    ].join("\n"),
  );

  const page = parse("ising/index.qmd", source);

  assert.deepEqual(diagnostics(page), []);
  assert.deepEqual(targets(page.localLinks), [
    "notes.qmd#anchor",
    "notes.qmd?x=1",
    "figures/plot.png",
    "../../outside.qmd",
    "/etc/passwd",
  ]);
  assert.deepEqual(
    page.localLinks.map((link) => link.kind),
    ["link", "link", "image", "link", "link"],
  );
  assert.deepEqual(page.citations, []);
});

test("recognizes Pandoc citation keys in text and nowhere else", () => {
  const source = [
    /*  1 */ "---",
    /*  2 */ "title: Citations",
    /*  3 */ "description: Citation keys come from Markdown text nodes only.",
    /*  4 */ "categories: [theory]",
    /*  5 */ "---",
    /*  6 */ "",
    /*  7 */ "One bracket [@alpha2026; @beta2026, pp. 3-5] and in text @gamma2026.",
    /*  8 */ "",
    /*  9 */ "Mail chance@example.com and <https://example.com/@handle> are not keys.",
    /* 10 */ "",
    /* 11 */ "Inline `@nope` and a fence:",
    /* 12 */ "",
    /* 13 */ "```text",
    /* 14 */ "@alsonope",
    /* 15 */ "```",
    /* 16 */ "",
    /* 17 */ "Suppressed author [-@delta2026] still counts.",
    /* 18 */ "",
  ].join("\n");

  const page = parse("ising/proof.qmd", source);

  assert.deepEqual(diagnostics(page), []);
  assert.deepEqual(
    page.citations.map((citation) => ({
      key: citation.key,
      line: citation.location.line,
      column: citation.location.column,
    })),
    [
      { key: "alpha2026", line: 7, column: 14 },
      { key: "beta2026", line: 7, column: 26 },
      { key: "gamma2026", line: 7, column: 58 },
      { key: "delta2026", line: 17, column: 21 },
    ],
  );
});

test("offsets body locations by the frontmatter, and by nothing when it is absent", () => {
  const withFrontmatter = parse(
    "ising/index.qmd",
    [
      "---",
      "title: A topic",
      "description: A description.",
      "aliases:",
      "  - one",
      "  - two",
      "---",
      "",
      "## Reading map",
      "",
      "- [Proof](proof.qmd)",
      "",
    ].join("\n"),
  );
  const withoutFrontmatter = parse(
    "ising/index.qmd",
    ["## Reading map", "", "- [Proof](proof.qmd)", ""].join("\n"),
  );

  assert.deepEqual(diagnostics(withFrontmatter), []);
  assert.equal(withFrontmatter.readingMap[0]?.location.line, 11);
  assert.equal(withFrontmatter.readingMap[0]?.location.column, 3);

  assert.deepEqual(diagnostics(withoutFrontmatter), [
    { code: "FRONTMATTER_MISSING", line: 1, column: 1 },
  ]);
  assert.equal(withoutFrontmatter.readingMap[0]?.location.line, 3);
  assert.equal(withoutFrontmatter.readingMap[0]?.location.column, 3);
});

test("rejects every frontmatter key outside the allowlist", () => {
  const forbidden: readonly string[] = [
    "execute: {enabled: true}",
    "filters: [evil.lua]",
    "include-before-body: evil.html",
    "include-after-body: evil.html",
    "include-in-header: evil.html",
    "resources: [../../secrets]",
    "format: {html: {toc: false}}",
    "bibliography: other.bib",
    "unknown-key: whatever",
    "jupyter: python3",
  ];

  for (const line of forbidden) {
    const key = line.slice(0, line.indexOf(":"));
    const page = parse(
      "ising/proof.qmd",
      [
        "---",
        "title: A page",
        "description: A description.",
        "categories: [theory]",
        line,
        "---",
        "",
        "Body.",
        "",
      ].join("\n"),
    );

    assert.deepEqual(
      diagnostics(page),
      [{ code: "FRONTMATTER_KEY_FORBIDDEN", line: 5, column: 1 }],
      line,
    );
    assert.match(page.parseDiagnostics[0]?.message ?? "", new RegExp(key));

    // The allowed keys of the same page are still parsed.
    assert.equal(page.title, "A page");
    assert.equal(page.category, "theory");
  }
});

test("reports every parse problem of a page instead of stopping at the first", () => {
  const page = parse(
    "ising/proof.qmd",
    [
      "---",
      "execute: {enabled: true}",
      "filters: [evil.lua]",
      "---",
      "",
      "## Reading map",
      "",
      "- [One](one.qmd)",
      "",
      "## Reading map",
      "",
      "- [Two](two.qmd)",
      "",
    ].join("\n"),
  );

  assert.deepEqual(diagnostics(page), [
    { code: "FRONTMATTER_KEY_FORBIDDEN", line: 2, column: 1 },
    { code: "FRONTMATTER_KEY_FORBIDDEN", line: 3, column: 1 },
    { code: "TITLE_REQUIRED", line: 1, column: 1 },
    { code: "DESCRIPTION_REQUIRED", line: 1, column: 1 },
    { code: "CATEGORY_REQUIRED", line: 1, column: 1 },
    { code: "READING_MAP_DUPLICATE", line: 10, column: 1 },
  ]);
});

test("reports each frontmatter diagnostic code at its own location", () => {
  const cases: readonly {
    name: string;
    relativePath: string;
    source: string;
    expected: { code: string; line: number; column: number }[];
  }[] = [
    {
      name: "FRONTMATTER_MISSING: no frontmatter at all",
      relativePath: "ising/proof.qmd",
      source: "# Just a heading\n",
      expected: [{ code: "FRONTMATTER_MISSING", line: 1, column: 1 }],
    },
    {
      // Pandoc would still read the block as metadata, so both are reported:
      // the page has no frontmatter, and it carries a stray metadata block.
      name: "FRONTMATTER_MISSING: frontmatter does not open on line one",
      relativePath: "ising/proof.qmd",
      source: ["", "---", "title: A page", "---", ""].join("\n"),
      expected: [
        { code: "FRONTMATTER_MISSING", line: 1, column: 1 },
        { code: "FRONTMATTER_INVALID", line: 2, column: 1 },
      ],
    },
    {
      name: "FRONTMATTER_INVALID: the block is never closed",
      relativePath: "ising/proof.qmd",
      source: ["---", "title: A page", "description: A description.", ""].join("\n"),
      expected: [{ code: "FRONTMATTER_INVALID", line: 1, column: 1 }],
    },
    {
      name: "FRONTMATTER_INVALID: the top level is not a mapping",
      relativePath: "ising/proof.qmd",
      source: ["---", "- one", "- two", "---", ""].join("\n"),
      expected: [{ code: "FRONTMATTER_INVALID", line: 2, column: 1 }],
    },
    {
      name: "TITLE_REQUIRED: absent",
      relativePath: "ising/index.qmd",
      source: ["---", "description: A description.", "---", ""].join("\n"),
      expected: [{ code: "TITLE_REQUIRED", line: 1, column: 1 }],
    },
    {
      name: "TITLE_REQUIRED: blank",
      relativePath: "ising/index.qmd",
      source: ["---", 'title: "  "', "description: A description.", "---", ""].join(
        "\n",
      ),
      expected: [{ code: "TITLE_REQUIRED", line: 2, column: 8 }],
    },
    {
      name: "DESCRIPTION_REQUIRED: absent",
      relativePath: "ising/index.qmd",
      source: ["---", "title: A topic", "---", ""].join("\n"),
      expected: [{ code: "DESCRIPTION_REQUIRED", line: 1, column: 1 }],
    },
    {
      name: "DESCRIPTION_REQUIRED: not a string",
      relativePath: "ising/index.qmd",
      source: ["---", "title: A topic", "description: [a, b]", "---", ""].join("\n"),
      expected: [{ code: "DESCRIPTION_REQUIRED", line: 3, column: 14 }],
    },
    {
      name: "CATEGORY_REQUIRED: a content page without categories",
      relativePath: "ising/proof.qmd",
      source: ["---", "title: A page", "description: A description.", "---", ""].join(
        "\n",
      ),
      expected: [{ code: "CATEGORY_REQUIRED", line: 1, column: 1 }],
    },
    {
      name: "CATEGORY_REQUIRED: an empty category list",
      relativePath: "ising/proof.qmd",
      source: [
        "---",
        "title: A page",
        "description: A description.",
        "categories: []",
        "---",
        "",
      ].join("\n"),
      expected: [{ code: "CATEGORY_REQUIRED", line: 4, column: 13 }],
    },
    {
      name: "CATEGORY_INVALID: an unknown category",
      relativePath: "ising/proof.qmd",
      source: [
        "---",
        "title: A page",
        "description: A description.",
        "categories: [speculation]",
        "---",
        "",
      ].join("\n"),
      expected: [{ code: "CATEGORY_INVALID", line: 4, column: 14 }],
    },
    {
      name: "CATEGORY_INVALID: two categories",
      relativePath: "ising/proof.qmd",
      source: [
        "---",
        "title: A page",
        "description: A description.",
        "categories: [theory, codes]",
        "---",
        "",
      ].join("\n"),
      expected: [{ code: "CATEGORY_INVALID", line: 4, column: 13 }],
    },
    {
      name: "CATEGORY_INVALID: a bare string instead of a list",
      relativePath: "ising/proof.qmd",
      source: [
        "---",
        "title: A page",
        "description: A description.",
        "categories: theory",
        "---",
        "",
      ].join("\n"),
      expected: [{ code: "CATEGORY_INVALID", line: 4, column: 13 }],
    },
    {
      name: "INDEX_CATEGORY_FORBIDDEN: an index page with a category",
      relativePath: "ising/index.qmd",
      source: [
        "---",
        "title: A topic",
        "description: A description.",
        "categories: [theory]",
        "---",
        "",
      ].join("\n"),
      expected: [{ code: "INDEX_CATEGORY_FORBIDDEN", line: 4, column: 1 }],
    },
    {
      name: "ALIASES_INVALID: not a list",
      relativePath: "ising/index.qmd",
      source: [
        "---",
        "title: A topic",
        "description: A description.",
        "aliases: ising",
        "---",
        "",
      ].join("\n"),
      expected: [{ code: "ALIASES_INVALID", line: 4, column: 10 }],
    },
    {
      name: "ALIASES_INVALID: a blank entry",
      relativePath: "ising/index.qmd",
      source: [
        "---",
        "title: A topic",
        "description: A description.",
        'aliases: [ising, "  "]',
        "---",
        "",
      ].join("\n"),
      expected: [{ code: "ALIASES_INVALID", line: 4, column: 18 }],
    },
    {
      name: "ALIASES_INVALID: a non-string entry",
      relativePath: "ising/index.qmd",
      source: [
        "---",
        "title: A topic",
        "description: A description.",
        "aliases: [2]",
        "---",
        "",
      ].join("\n"),
      expected: [{ code: "ALIASES_INVALID", line: 4, column: 11 }],
    },
    {
      name: "FRONTMATTER_KEY_FORBIDDEN: an unknown key",
      relativePath: "ising/index.qmd",
      source: [
        "---",
        "title: A topic",
        "description: A description.",
        "resources: [../../secrets]",
        "---",
        "",
      ].join("\n"),
      expected: [{ code: "FRONTMATTER_KEY_FORBIDDEN", line: 4, column: 1 }],
    },
  ];

  for (const testCase of cases) {
    const page = parse(testCase.relativePath, testCase.source);

    assert.deepEqual(diagnostics(page), testCase.expected, testCase.name);
    for (const diagnostic of page.parseDiagnostics) {
      assert.ok(diagnostic.message.length > 0, testCase.name);
      assert.equal(
        diagnostic.location.file,
        `knowledge/${testCase.relativePath}`,
        testCase.name,
      );
    }
  }
});

test("reports each body diagnostic code at its own location", () => {
  const duplicateReadingMap = parse(
    "ising/index.qmd",
    indexPage(
      [
        "## Reading map",
        "",
        "- [One](one.qmd)",
        "",
        "## Reading map",
        "",
        "- [Two](two.qmd)",
        "",
      ].join("\n"),
    ),
  );
  const duplicateReadingMapEntry = parse(
    "ising/index.qmd",
    indexPage(
      ["## Reading map", "", "- [One](one.qmd)", "- [Again](one.qmd)", ""].join("\n"),
    ),
  );
  const duplicateRelatedTopics = parse(
    "ising/index.qmd",
    indexPage(
      [
        "## Related topics",
        "",
        "- [One](a/index.qmd)",
        "",
        "## Related topics",
        "",
        "- [Two](b/index.qmd)",
        "",
      ].join("\n"),
    ),
  );
  const duplicateRelatedTopicsEntry = parse(
    "ising/index.qmd",
    indexPage(
      [
        "## Related topics",
        "",
        "- [One](a/index.qmd)",
        "- [Again](a/index.qmd)",
        "",
      ].join("\n"),
    ),
  );

  assert.deepEqual(diagnostics(duplicateReadingMap), [
    { code: "READING_MAP_DUPLICATE", line: 10, column: 1 },
  ]);
  assert.deepEqual(diagnostics(duplicateReadingMapEntry), [
    { code: "READING_MAP_DUPLICATE", line: 9, column: 3 },
  ]);
  assert.deepEqual(diagnostics(duplicateRelatedTopics), [
    { code: "RELATED_TOPICS_DUPLICATE", line: 10, column: 1 },
  ]);
  assert.deepEqual(diagnostics(duplicateRelatedTopicsEntry), [
    { code: "RELATED_TOPICS_DUPLICATE", line: 9, column: 3 },
  ]);

  // A duplicated section keeps the entries of the first occurrence only.
  assert.deepEqual(targets(duplicateReadingMap.readingMap), ["one.qmd"]);
  assert.deepEqual(targets(duplicateRelatedTopics.relatedTopics), ["a/index.qmd"]);
  assert.deepEqual(targets(duplicateReadingMapEntry.readingMap), ["one.qmd"]);
});

test("never throws on a hostile or malformed page", () => {
  const sources: readonly string[] = [
    "",
    "---",
    "---\n",
    "---\n---\n",
    "---\n---",
    "----\n",
    "---\r\ntitle: A topic\r\ndescription: A description.\r\n---\r\n\r\nBody.\r\n",
    "---\n\ttab: 1\n---\n",
    "---\ntitle: A topic\ntitle: Twice\ndescription: A description.\n---\n",
    "﻿---\ntitle: A topic\ndescription: A description.\n---\n\nBody.\n",
    indexPage("## Reading map\n\n- [Broken](\n"),
    indexPage("<script"),
    indexPage("<div on=\"x\">"),
  ];

  for (const source of sources) {
    const page = parse("ising/index.qmd", source);
    assert.ok(Array.isArray(page.parseDiagnostics), JSON.stringify(source));
    assert.equal(page.id, "ising/index.qmd");
  }

  // A CRLF page with valid frontmatter is still a valid page.
  const crlf = parse(
    "ising/index.qmd",
    "---\r\ntitle: A topic\r\ndescription: A description.\r\n---\r\n\r\nBody.\r\n",
  );
  assert.deepEqual(diagnostics(crlf), []);
  assert.equal(crlf.title, "A topic");

  // A byte-order mark does not hide the frontmatter.
  const bom = parse(
    "ising/index.qmd",
    "﻿---\ntitle: A topic\ndescription: A description.\n---\n\nBody.\n",
  );
  assert.deepEqual(diagnostics(bom), []);
  assert.equal(bom.title, "A topic");

  // A duplicated key is a YAML error, not a silent last-one-wins.
  const duplicated = parse(
    "ising/index.qmd",
    "---\ntitle: A topic\ntitle: Twice\ndescription: A description.\n---\n",
  );
  assert.deepEqual(codes(duplicated), ["FRONTMATTER_INVALID"]);
});
