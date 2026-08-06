import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { parseKnowledgePage } from "../../../src/lib/knowledge/parser.js";
import {
  ALLOWED_FRONTMATTER_KEYS,
  KNOWLEDGE_CATEGORIES,
  type ParsedKnowledgePage,
} from "../../../src/lib/knowledge/types.js";

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

test("finds handlers behind a quoted angle bracket in an earlier attribute", () => {
  // Pandoc renders a live handler for every one of these.
  const cases: readonly { markup: string; column: number }[] = [
    { markup: '<div title="a < b" onclick="alert(1)">x</div>', column: 20 },
    { markup: '<div title="a<3" onclick="alert(1)">x</div>', column: 18 },
    { markup: '<div title="<" onclick="alert(1)">x</div>', column: 16 },
    { markup: '<div title="a<=b" onclick="alert(1)">x</div>', column: 19 },
    { markup: '<div title="a>b" onclick="alert(1)">x</div>', column: 18 },
    { markup: "<div title='a < b' onclick='alert(1)'>x</div>", column: 20 },
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

test("follows a tag across a blank line when the element is a real one", () => {
  // `quarto pandoc` renders a live handler for the `div` shapes; `a` and `img`
  // it drops, but a real element name is reported either way.
  const cases: readonly { markup: string; line: number; column: number }[] = [
    { markup: '<div\n\nonclick="alert(1)">y</div>', line: 8, column: 1 },
    { markup: '<div\n\n  onclick="alert(1)"\n\n>y</div>', line: 8, column: 3 },
    { markup: '<a href="x"\n\nonmouseover="alert(1)">y</a>', line: 8, column: 1 },
    { markup: "<img\n\nsrc=x\n\nonerror=alert(1)>", line: 10, column: 1 },
    { markup: '<div class="a"\n\n\nonclick=alert(1)>y</div>', line: 9, column: 1 },
  ];

  for (const { markup, line, column } of cases) {
    const page = parse("ising/index.qmd", indexPage(`${markup}\n`));

    assert.deepEqual(
      page.unsafeHtml.map((entry) => ({
        kind: entry.kind,
        line: entry.location.line,
        column: entry.location.column,
      })),
      [{ kind: "inline-handler", line, column }],
      markup,
    );
  }

  // An invented element name does not span a blank line, and Pandoc agrees:
  // `<my-widget⏎⏎onclick=…>` renders no handler at all.
  const invented = parse(
    "ising/index.qmd",
    indexPage('<my-widget\n\nonclick="alert(1)">y</my-widget>\n'),
  );
  assert.deepEqual(invented.unsafeHtml, []);
});

test("keeps reading a tag through an unbalanced quote", () => {
  // A quote only opens a value after `=`; anywhere else it is a character.
  const reported: readonly { markup: string; column: number }[] = [
    { markup: "<div id=a' onclick=alert(1)>x</div>", column: 12 },
    { markup: '<div id=a" onclick=alert(1)>x</div>', column: 12 },
    { markup: "<div title=it's onclick=alert(1)>x</div>", column: 17 },
    { markup: '<div data-x=a"b onclick=alert(1)>x</div>', column: 17 },
    { markup: "<div id=a'b' onclick=alert(1)>x</div>", column: 14 },
  ];

  for (const { markup, column } of reported) {
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

  // A quoted value that never closes swallows the rest of the file, so the tag
  // never closes and no renderer makes one. `quarto pandoc` emits no handler
  // for either of these.
  for (const markup of [
    "<div id='a onclick=alert(1)>x</div>",
    '<div id="a onclick=alert(1)>x</div>',
  ]) {
    const page = parse("ising/index.qmd", indexPage(`${markup}\n`));
    assert.deepEqual(page.unsafeHtml, [], markup);
  }
});

test("an unclosed fence hides nothing, because Pandoc does not treat it as code", () => {
  const cases: readonly {
    body: string;
    expected: { kind: string; line: number; column: number }[];
  }[] = [
    {
      body: "```python\nx = 1\n\n<script>alert(1)</script>\n",
      expected: [{ kind: "script", line: 9, column: 1 }],
    },
    {
      body: "```python\nx = 1\n\n<div onclick=alert(1)>y</div>\n",
      expected: [{ kind: "inline-handler", line: 9, column: 6 }],
    },
    {
      body: "```\n<script>alert(1)</script>\n",
      expected: [{ kind: "script", line: 7, column: 1 }],
    },
    {
      body: "~~~python\nx = 1\n\n<div onclick=alert(1)>y</div>\n",
      expected: [{ kind: "inline-handler", line: 9, column: 6 }],
    },
  ];

  for (const testCase of cases) {
    const page = parse("ising/index.qmd", indexPage(testCase.body));

    assert.deepEqual(
      page.unsafeHtml.map((entry) => ({
        kind: entry.kind,
        line: entry.location.line,
        column: entry.location.column,
      })),
      testCase.expected,
      testCase.body,
    );
  }

  // A closed fence is still ordinary escaped code.
  const closed = parse(
    "ising/index.qmd",
    indexPage('```python\nx = 1\n```\n\n<script>alert(1)</script>\n```html\n<div onclick=x>\n```\n'),
  );
  assert.deepEqual(
    closed.unsafeHtml.map((entry) => ({ kind: entry.kind, line: entry.location.line })),
    [{ kind: "script", line: 10 }],
  );

  // A metadata block after an unclosed fence is not hidden either. The fence
  // itself is reported at its opener, ahead of what it was hiding.
  const metadata = parse(
    "ising/index.qmd",
    indexPage("```python\nx = 1\n\n---\nexecute:\n  enabled: true\n---\n"),
  );
  assert.deepEqual(diagnostics(metadata), [
    { code: "FENCE_UNCLOSED", line: 6, column: 1 },
    { code: "FRONTMATTER_INVALID", line: 9, column: 1 },
  ]);
});

test("an unclosed fence is reported, because the graph cannot see past it", () => {
  // The scans above look through an unclosed fence; `localLinks`, `citations`,
  // and the two curated sections cannot, because they are read from the mdast
  // tree and remark has swallowed the whole tail of the page into one code
  // node. Reproduced against Quarto 1.9.38: the page below validates clean and
  // publishes `href="../../../../../../../../etc/hostname"`. So the fence is a
  // diagnostic of its own.
  const escaping = parse(
    "ising/index.qmd",
    indexPage(
      [
        /*  6 */ "```python",
        /*  7 */ 'print("unclosed fence")',
        /*  8 */ "",
        /*  9 */ "[escape](../../../../../../../../etc/hostname)",
        /* 10 */ "@definitely_not_in_the_bibliography",
      ].join("\n"),
    ),
  );
  assert.deepEqual(diagnostics(escaping), [
    { code: "FENCE_UNCLOSED", line: 6, column: 1 },
  ]);
  // Everything below the opener really is invisible — which is exactly why the
  // page may not be allowed to pass.
  assert.deepEqual(targets(escaping.localLinks), []);
  assert.deepEqual(escaping.citations, []);

  // Every fence shape, at the opener, wherever it sits in the file.
  const shapes: readonly { body: string; line: number; column: number }[] = [
    { body: "Intro.\n\n```python\nx = 1\n", line: 8, column: 1 },
    { body: "Intro.\n\n~~~\nx = 1\n", line: 8, column: 1 },
    { body: "Intro.\n\n   ```js\nx = 1\n", line: 8, column: 4 },
    // Closed one backtick short: the closer is shorter than the opener.
    { body: "````python\nx = 1\n```\n", line: 6, column: 1 },
    // A closing fence indented past the three columns CommonMark allows.
    { body: "```python\nx = 1\n        ```\n", line: 6, column: 1 },
    // Inside a block quote, where the fence closes at the end of the quote and
    // the tail below is Markdown to remark and to Pandoc alike — still a fence
    // the author never closed.
    { body: "> ```python\n> x = 1\n\nTail.\n", line: 6, column: 3 },
  ];
  for (const shape of shapes) {
    assert.deepEqual(
      diagnostics(parse("ising/index.qmd", indexPage(shape.body))),
      [{ code: "FENCE_UNCLOSED", line: shape.line, column: shape.column }],
      shape.body,
    );
  }
});

test("a closed fence inside a container is not reported as unclosed", () => {
  // remark reports a fenced block from its backticks onwards, so every line of
  // its source *after* the first still carries the container prefix (`> `,
  // `>   `, five spaces) that line one lost. Reading those prefixes as content
  // would make every quoted or deeply nested code block look unclosed — and,
  // now that an unclosed fence fails the tree, would fail pages that are fine.
  const closed: readonly string[] = [
    "> ```python\n> x = 1\n> ```\n\nTail.\n",
    "> ```python\n> x = 1\n>```\n\nTail.\n",
    "> > ```python\n> > x = 1\n> > ```\n\nTail.\n",
    "> - ```python\n>   x = 1\n>   ```\n\nTail.\n",
    "- item\n\n  ```python\n  x = 1\n  ```\n\nTail.\n",
    "1. a\n   - b\n\n     ```js\n     y\n     ```\n\nTail.\n",
    "   ```js\ny = 1\n```\n\nTail.\n",
    "~~~\nx = 1\n~~~\n\nTail.\n",
    "```python\nx = 1\n```\n\nTail.\n",
  ];
  for (const body of closed) {
    assert.deepEqual(codes(parse("ising/index.qmd", indexPage(body))), [], body);
  }

  // And a link written below a quoted fence is still collected, which is the
  // property the diagnostic exists to protect.
  const quoted = parse(
    "ising/index.qmd",
    indexPage("> ```python\n> x = 1\n> ```\n\n[Neighbour](other.qmd)\n"),
  );
  assert.deepEqual(codes(quoted), []);
  assert.deepEqual(targets(quoted.localLinks), ["other.qmd"]);
});

test("keeps clean content clean around stray angle brackets", () => {
  const shapes: readonly string[] = [
    // Inline math followed by handler-shaped prose.
    "The transition $x<y$ holds.\n\nThe onset=3 value and online=true flag.\n",
    "For $T<T_c$ the onset=3 value is fixed.\n",
    "Bounds $a<b$ and $c<d$ give online=true in the log.\n",
    // An autolink carrying a handler-shaped query parameter.
    "See <https://example.com/runs?onload=1&online=true> for the log.\n",
    "See [the log](https://example.com/runs?onload=1) and onset=2 here.\n",
    // Inline code holding an unfinished tag, then handler-shaped prose.
    "Write `<div` to open a tag.\n\nThe online=true flag is separate.\n",
    "A `<div` span and then onset=4 in the same paragraph.\n",
    // Comparison operators in prose.
    "If x<y then the online=true branch runs.\n",
  ];

  for (const shape of shapes) {
    const page = parse("ising/index.qmd", indexPage(shape));
    assert.deepEqual(page.unsafeHtml, [], shape);
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

test("reports every metadata block Pandoc actually merges", () => {
  // Each shape was confirmed with `quarto pandoc`: `header-includes` reaches
  // <head>, so the block is live metadata however it is delimited or placed.
  const payload = ["header-includes: |", "  <script>alert(1)</script>"];
  const cases: readonly { name: string; body: readonly string[]; line: number }[] = [
    {
      name: "trailing spaces on the opener",
      body: ["Prose.", "", "---   ", ...payload, "---", "", "After."],
      line: 8,
    },
    {
      name: "a tab after the opener",
      body: ["Prose.", "", "---\t", ...payload, "---", "", "After."],
      line: 8,
    },
    {
      name: "trailing spaces on the closer",
      body: ["Prose.", "", "---", ...payload, "---  ", "", "After."],
      line: 8,
    },
    {
      name: "a `...` closer",
      body: ["Prose.", "", "---", ...payload, "...", "", "After."],
      line: 8,
    },
    {
      name: "directly after a fenced code block",
      body: ["```python", "x = 1", "```", "---", ...payload, "---", "", "After."],
      line: 9,
    },
    {
      name: "directly after a setext heading",
      body: ["Heading text", "===", "---", ...payload, "---", "", "After."],
      line: 8,
    },
    {
      name: "directly after the frontmatter",
      body: ["---", ...payload, "---", "", "After."],
      line: 6,
    },
  ];

  for (const testCase of cases) {
    const page = parse("ising/index.qmd", indexPage(`${testCase.body.join("\n")}\n`));

    assert.deepEqual(
      diagnostics(page),
      [{ code: "FRONTMATTER_INVALID", line: testCase.line, column: 1 }],
      testCase.name,
    );
    // The page's own frontmatter is still read.
    assert.equal(page.title, "A topic", testCase.name);
  }
});

test("follows Pandoc's frontmatter delimiters, including the `...` closer", () => {
  const dotsClosed = parse(
    "ising/index.qmd",
    ["---", "title: A topic", "description: A description.", "...", "", "Body.", ""].join(
      "\n",
    ),
  );
  assert.deepEqual(diagnostics(dotsClosed), []);
  assert.equal(dotsClosed.title, "A topic");
  assert.equal(dotsClosed.body, "\nBody.\n");

  // Ending the block at `...` is what makes a later block visible at all: with
  // `---` as the only closer, everything up to the next `---` was swallowed
  // into the frontmatter and this payload escaped the allowlist entirely.
  const blockAfterDots = parse(
    "ising/index.qmd",
    [
      /*  1 */ "---",
      /*  2 */ "title: A topic",
      /*  3 */ "description: A description.",
      /*  4 */ "...",
      /*  5 */ "",
      /*  6 */ "---",
      /*  7 */ "header-includes: |",
      /*  8 */ "  <script>alert(1)</script>",
      /*  9 */ "---",
      /* 10 */ "",
      /* 11 */ "Body.",
      /* 12 */ "",
    ].join("\n"),
  );
  assert.deepEqual(diagnostics(blockAfterDots), [
    { code: "FRONTMATTER_INVALID", line: 6, column: 1 },
  ]);
  assert.equal(blockAfterDots.title, "A topic");

  // Whitespace after either delimiter is ignored, as Pandoc ignores it.
  const padded = parse(
    "ising/index.qmd",
    ["---  ", "title: A topic", "description: A description.", "--- \t", "", "Body.", ""].join(
      "\n",
    ),
  );
  assert.deepEqual(diagnostics(padded), []);
  assert.equal(padded.title, "A topic");

  // A four-dash or indented closer closes nothing — Pandoc reads no metadata
  // from these files either.
  for (const closer of ["----", "  ---", "- --"]) {
    const unterminated = parse(
      "ising/index.qmd",
      ["---", "title: A topic", "description: A description.", closer, "", "Body.", ""].join(
        "\n",
      ),
    );
    assert.deepEqual(
      diagnostics(unterminated),
      [{ code: "FRONTMATTER_INVALID", line: 1, column: 1 }],
      closer,
    );
  }
});

test("treats a setext underline as a heading, not as a metadata opener", () => {
  // `quarto pandoc` leaves <head> clean for all of these: a `---` that closes an
  // open paragraph underlines a heading, it does not open metadata.
  const bodies: readonly string[] = [
    "Results\n---\nTemperature: 4.2\n\nNotes\n---\n",
    "Introduction\n---\nSome prose.\n\nMethods\n---\nMore prose.\n",
    "Results\n---\n\nMore text.\n",
    "Some text\n---\nheader-includes: |\n  script-like prose\n---\n",
    "Results are\nspread over lines\n---\nTemperature: 4.2\n",
  ];

  for (const body of bodies) {
    const page = parse("ising/index.qmd", indexPage(body));
    assert.deepEqual(diagnostics(page), [], body);
  }

  // The heading itself is ordinary content, so its links still count.
  const page = parse(
    "ising/index.qmd",
    indexPage("Reading map\n---\n\n- [Proof](proof.qmd)\n"),
  );
  assert.deepEqual(diagnostics(page), []);
  assert.deepEqual(targets(page.readingMap), ["proof.qmd"]);
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
        "----",
        "execute: true",
        "----",
        "",
        "  ---",
        "execute: true",
        "  ---",
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
  assert.deepEqual(page.reservedSections, []);
  assert.equal(page.localLinks.length, 4);
});

test("records every declared reserved section, empty ones included", () => {
  // A section with no entries is the one thing the entry lists cannot express:
  // `## Reading map` with prose under it is a topic that has promoted nothing
  // yet, which is exactly the shape of the production scaffold, and the graph
  // has to tell it apart from an index that declares no section at all.
  const declared = parse(
    "ising/index.qmd",
    [
      "---",
      "title: A topic",
      "description: A description.",
      "---",
      "",
      "Prose.",
      "",
      "## Reading map",
      "",
      "No topics have been promoted yet.",
      "",
      "## Related topics",
      "",
      "- [Root](../index.qmd)",
      "",
    ].join("\n"),
  );

  assert.deepEqual(diagnostics(declared), []);
  assert.deepEqual(targets(declared.readingMap), []);
  assert.deepEqual(
    declared.reservedSections.map((section) => ({
      heading: section.heading,
      line: section.location.line,
      column: section.location.column,
    })),
    [
      { heading: "Reading map", line: 8, column: 1 },
      { heading: "Related topics", line: 12, column: 1 },
    ],
  );

  // A fenced sample shows the heading; it does not declare it.
  const fenced = parse(
    "ising/index.qmd",
    indexPage(["```markdown", "## Reading map", "```", ""].join("\n")),
  );
  assert.deepEqual(fenced.reservedSections, []);

  // A repeated heading is one declaration and one diagnostic.
  const repeated = parse(
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
  assert.deepEqual(codes(repeated), ["READING_MAP_DUPLICATE"]);
  assert.deepEqual(
    repeated.reservedSections.map((section) => section.heading),
    ["Reading map"],
  );

  // A content page may declare one too; rejecting that is the graph's job, and
  // it needs to see the declaration to do it.
  const content = parse(
    "ising/proof.qmd",
    contentPage(["## Reading map", "", "- [One](one.qmd)", ""].join("\n")),
  );
  assert.deepEqual(diagnostics(content), []);
  assert.deepEqual(
    content.reservedSections.map((section) => section.heading),
    ["Reading map"],
  );
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
      "[Paper](zotero://open-pdf/library/items/AB12CD34?page=7) and [Trap](javascript:alert(1)).",
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
    "javascript:alert(1)",
  ]);
  assert.deepEqual(
    page.localLinks.map((link) => link.kind),
    ["link", "link", "image", "link", "link", "link"],
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
    /* 19 */ "Quarto cross-references @eq-energy, @fig-phase, and @lem-bound are not bibliography citations, but @figless2026 is.",
    /* 20 */ "",
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
      { key: "figless2026", line: 19, column: 100 },
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
