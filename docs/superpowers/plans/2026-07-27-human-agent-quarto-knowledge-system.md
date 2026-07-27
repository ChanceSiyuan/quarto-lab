# Human–Agent Quarto Knowledge System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `/home/chance/research-loop` into a shared human-and-agent Quarto knowledge system while preserving the existing Research Loop dashboard, importing the current quantum-harness knowledge as untrusted drafts, and keeping external literature separate.

**Architecture:** One TypeScript `KnowledgeGraph` deep module owns parsing, validation, deterministic resolution, Quarto navigation, and site generation. Trusted content exists only in `knowledge/**/*.qmd`; untrusted notes stay in `drafts/`; external evidence stays in `literature/`. A temporary, execution-disabled Quarto project renders to gitignored `public/knowledge/`, then the existing vinext build packages the dashboard at `/` and the static knowledge site at `/knowledge/` into the same Sites artifact.

**Tech Stack:** Node.js 22.23.1, TypeScript 5.9, Next.js 16/vinext/Vite/Cloudflare Worker, Quarto 1.9.38, Node's test runner with `tsx`, unified/remark, YAML, `@retorquere/bibtex-parser`, `tar`, Playwright Chromium, Git, and OpenAI Sites.

## Global Constraints

- Implement only in `/home/chance/research-loop`. Treat `/home/chance/quantum.harness` as read-only migration input.
- Read the approved design first: `docs/superpowers/specs/2026-07-27-quarto-knowledge-system-design.md`.
- Start from a clean, non-`main` feature branch. Preserve the current dashboard source and appearance; do not rewrite `app/page.tsx`, `app/globals.css`, or `app/layout.tsx` to make tests pass.
- `knowledge/**/*.qmd` is the only trusted content authority. Do not create demonstration physics/software notes in the production tree.
- `drafts/` has no required categories, hierarchy, catalog, or frontmatter. Never publish it.
- `literature/` is external evidence, not learned knowledge. Never let the resolver silently use it.
- Every knowledge content page has exactly one category: `theory`, `experiment`, or `codes`. An `index.qmd` has no category.
- Quarto rendering must have code execution disabled. Never compile downloaded LaTeX.
- Enforce that boundary twice: trusted-page frontmatter uses a strict allowlist, and every Quarto render/preview subprocess includes `--no-execute`.
- No D1, R2, queue, autonomous solver backend, embeddings, `.knowledge` compatibility tree, or generated Markdown mirror in this phase.
- Keep all generated files out of Git: `public/knowledge/`, build workspaces, Playwright output, literature `.raw/`, literature `.figures/`, and staging directories.
- Reuse the opaque Sites project ID in `.openai/hosting.json` exactly: `appgprj_6a66e89526a88191a9e969c6f441086c`. Never invent, reformat, or replace it.
- Current Sites inspection returns `Project not found`. Local completion is valid; production completion is blocked until that exact project becomes visible. Do not create a replacement site.
- Use `superpowers:writing-skills` before authoring or editing any `skills/*/SKILL.md` file. Use `superpowers:verification-before-completion` before claiming completion and `superpowers:requesting-code-review` before handoff.
- Use test-first commits. Do not combine unrelated tasks or silently repair unrelated repository state.

## Fixed External Baselines

- Target repository at plan time: `/home/chance/research-loop`, `main` includes design commits `226bc49` and `425843c` plus this plan.
- Migration source repository: `/home/chance/quantum.harness` at `d2532921cc6779559658d85bc665c42d11012331`.
- Migration corpus: exactly 280 non-literature Markdown files, 11,078,725 bytes in total.
- Bibliography: 85 entries, 13 method keywords/directories, and 65 entries with an arXiv `eprint`.
- Existing dashboard build command: `WRANGLER_LOG_PATH=.wrangler/wrangler.log vinext build`.
- Existing dashboard routes and client state are authoritative: `/`, localStorage key `research-loop-demo`, stage advancement, reload persistence, and reset.

If the source commit changes before execution, stop before migration and ask the user whether the new source revision replaces this approved baseline. Do not silently import a different corpus.

## Target File Map

```text
research-loop/
├── .claude/
│   └── skills -> ../skills
├── .node-version
├── AGENTS.md
├── CLAUDE.md
├── Makefile
├── README.md
├── app/                                  # existing dashboard remains authoritative
├── worker/index.ts                       # change only if real nested-asset test requires it
├── knowledge/
│   ├── _quarto.yml                       # human-readable fixed Quarto base config
│   └── index.qmd                         # empty trusted root/navigation scaffold
├── drafts/
│   ├── _quarto.yml                       # selected-note local preview only
│   └── imported-quantum-harness/          # 280 byte-identical .md candidates
├── literature/
│   ├── ref.bib
│   └── <method>/
│       ├── INDEX.md                      # generated and committed
│       ├── .raw/<citekey>/               # downloaded, local-only
│       └── .figures/<citekey>/           # extracted, local-only
├── lib/
│   ├── drafts/preview.ts
│   ├── knowledge/{types,parser,graph,validate,resolve,quarto,site,index}.ts
│   ├── literature/{bibliography,indexes,archive,figures,arxiv,fetch,index}.ts
│   └── migration/harness.ts
├── scripts/
│   ├── draft-preview.ts
│   ├── build-e2e-fixture.ts
│   ├── knowledge.ts
│   ├── literature.ts
│   └── migrate-quantum-harness.ts
├── skills/
│   ├── read-knowledge/SKILL.md
│   ├── review-draft/SKILL.md
│   └── download-ref/SKILL.md
├── docs/
│   ├── migrations/quantum-harness-knowledge.json
│   └── skills.md
├── tests/
│   ├── agent/skill-contracts.test.ts
│   ├── drafts/preview.test.ts
│   ├── e2e/{dashboard,knowledge}.spec.ts
│   ├── fixtures/{knowledge,literature,archives}/
│   ├── knowledge/*.test.ts
│   ├── literature/*.test.ts
│   ├── migration/harness.test.ts
│   ├── built-static-assets.test.mjs
│   └── rendered-html.test.mjs
├── package.json
├── package-lock.json
└── playwright.config.ts
```

Public module boundaries:

```ts
// lib/knowledge/index.ts
export { loadKnowledge } from "./graph.js";
export { validateKnowledge } from "./validate.js";
export { resolveKnowledge } from "./resolve.js";
export { buildKnowledgeSite, previewKnowledgeSite } from "./site.js";

// lib/literature/index.ts
export { loadBibliography } from "./bibliography.js";
export { writeMethodIndexes } from "./indexes.js";
export { fetchLiteratureEntry, syncLiterature } from "./fetch.js";
```

CLI, Make targets, Quarto projection, and skills must call these public interfaces; they must not recreate graph or literature semantics.

---

## Task 1: Create the implementation branch and pin the toolchain

**Files:**

- Create: `.node-version`
- Create: `AGENTS.md` (minimal implementation guardrails; expanded in Task 12)
- Create: `CLAUDE.md` (points to `AGENTS.md`)
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `.gitignore`

- [ ] Confirm the target repository is clean and includes this plan:

  ```bash
  cd /home/chance/research-loop
  git status --short --branch
  test -f docs/superpowers/plans/2026-07-27-human-agent-quarto-knowledge-system.md
  git switch -c feat/human-agent-quarto-knowledge
  ```

  Expected: no uncommitted files before the branch is created.

- [ ] Confirm the source revision without changing the source repository:

  ```bash
  git -C /home/chance/quantum.harness rev-parse HEAD
  test -z "$(git -C /home/chance/quantum.harness \
    status --porcelain=v1 --untracked-files=all -- .knowledge)"
  ```

  Expected: the revision is `d2532921cc6779559658d85bc665c42d11012331`; `.knowledge` has no uncommitted change. An unrelated dirty file outside `.knowledge` is not a blocker.

- [ ] Before spawning implementation subagents, create a minimal `AGENTS.md` with the Global Constraints from this plan: target/source repository boundary, dashboard preservation, physical trust boundary, Quarto `--no-execute`, test-first commits, and exact Sites project-ID rule. Create `CLAUDE.md` containing exactly `Read and follow @AGENTS.md.`. Task 12 expands these files after the skills exist.

- [ ] Install/use Node 22.23.1. If `node --version` is already `v22.23.1`, retain it. Otherwise, request approval for the write outside the repository, then on this verified `x86_64` host download the official binary, verify it against the official checksum file, and install it:

  ```bash
  mkdir -p /tmp/research-loop-node-22.23.1
  cd /tmp/research-loop-node-22.23.1
  curl -fsSLO https://nodejs.org/dist/v22.23.1/node-v22.23.1-linux-x64.tar.xz
  curl -fsSLO https://nodejs.org/dist/v22.23.1/SHASUMS256.txt
  sha256sum -c --ignore-missing SHASUMS256.txt
  mkdir -p /home/chance/.local/opt
  tar -xJf node-v22.23.1-linux-x64.tar.xz -C /home/chance/.local/opt
  mkdir -p /home/chance/.local/bin
  test ! -e /home/chance/.local/bin/node
  test ! -e /home/chance/.local/bin/npm
  test ! -e /home/chance/.local/bin/npx
  ln -s /home/chance/.local/opt/node-v22.23.1-linux-x64/bin/node /home/chance/.local/bin/node
  ln -s /home/chance/.local/opt/node-v22.23.1-linux-x64/bin/npm /home/chance/.local/bin/npm
  ln -s /home/chance/.local/opt/node-v22.23.1-linux-x64/bin/npx /home/chance/.local/bin/npx
  hash -r
  command -v node
  node --version
  npm --version
  ```

  Expected: checksum `OK`, `command -v node` resolves under `/home/chance/.local/bin`, then `v22.23.1`. If any target link already exists, inspect it and reuse it only if it resolves to Node 22.23.1; never overwrite an unrelated executable. Do not use an unverified archive.

- [ ] Add `.node-version` containing exactly `22.23.1`.

- [ ] Run the current build before modifying dependencies:

  ```bash
  npm ci
  npm run build
  npm test > /tmp/research-loop-baseline-test.log 2>&1; test $? -ne 0
  rg 'starter loading skeleton|Your site is taking shape|Building your site' \
    /tmp/research-loop-baseline-test.log
  ```

  Expected: the current build succeeds. The test exits nonzero and the captured failure names only obsolete starter-loading-skeleton expectations. Inspect the complete log; any build, import, runtime, or unrelated assertion failure must be diagnosed before continuing.

- [ ] Install the exact runtime dependencies:

  ```bash
  npm install --save-exact \
    yaml@2.9.0 \
    unified@11.0.5 \
    remark-parse@11.0.0 \
    unist-util-visit@5.1.0 \
    mdast-util-to-string@4.0.0 \
    @retorquere/bibtex-parser@10.0.0 \
    tar@7.5.19
  npm install --save-dev --save-exact \
    tsx@4.23.1 \
    @playwright/test@1.61.1
  ```

- [ ] Extend `.gitignore` with these repository-root patterns:

  ```gitignore
  /public/knowledge/
  /drafts/.preview/
  /literature/.staging/
  /literature/**/.raw/
  /literature/**/.figures/
  /playwright-report/
  /test-results/
  /tests/e2e/.screenshots-actual/
  ```

  Keep the existing `/work/` ignore. Do not ignore `drafts/imported-quantum-harness/`, `literature/ref.bib`, or method `INDEX.md` files.

- [ ] Verify package reproducibility and types:

  ```bash
  npm ci
  npx --no-install tsc --noEmit
  git diff --check
  ```

  Expected: all commands exit 0.

- [ ] Commit:

  ```bash
  git add .node-version AGENTS.md CLAUDE.md package.json package-lock.json .gitignore
  git commit -m "chore: pin knowledge system toolchain"
  ```

## Task 2: Import all old knowledge cards as untrusted drafts

**Files:**

- Create: `lib/migration/harness.ts`
- Create: `scripts/migrate-quantum-harness.ts`
- Create: `tests/migration/harness.test.ts`
- Create: `drafts/imported-quantum-harness/**/*.md` (generated by the migration)
- Create: `literature/ref.bib` (generated by the migration)
- Create: `docs/migrations/quantum-harness-knowledge.json` (generated by the migration)

Define these stable types:

```ts
export interface MigrationEntry {
  path: string;       // POSIX path relative to drafts/imported-quantum-harness
  bytes: number;
  sha256: string;     // lowercase hex of raw bytes
}

export interface MigrationManifest {
  schemaVersion: 1;
  source: {
    repository: "quantum.harness";
    subtree: ".knowledge";
    revision: string;
  };
  destination: "drafts/imported-quantum-harness";
  files: MigrationEntry[];
  bibliography: {
    path: "literature/ref.bib";
    bytes: number;
    sha256: string;
  };
}

export async function importHarnessKnowledge(options: {
  sourceKnowledgeRoot: string;
  repoRoot: string;
  sourceRevision: string;
}): Promise<MigrationManifest>;

export async function verifyHarnessImport(
  repoRoot: string,
): Promise<{ files: number; bytes: number }>;

export async function verifyHarnessImportAgainstSource(options: {
  sourceKnowledgeRoot: string;
  repoRoot: string;
  sourceRevision: string;
}): Promise<{ files: number; bytes: number }>;
```

- [ ] Write `tests/migration/harness.test.ts` first. Build a temporary source tree containing root, model, software, and literature Markdown, plus `literature/ref.bib`. Assert that import:

  - copies only `.knowledge/**/*.md` outside `.knowledge/literature/**`;
  - preserves relative paths, filenames, raw bytes, line endings, and `.md` extensions;
  - copies only `literature/ref.bib` from the literature subtree;
  - sorts manifest entries by POSIX path;
  - records byte size and SHA-256 correctly;
  - writes no timestamp or host-specific absolute path;
  - stages before install and leaves no partial destination on failure;
  - refuses a conflicting non-verified destination instead of overwriting it;
  - reads blobs from the requested Git revision, not from modified/staged/untracked working-tree files;
  - lets `verifyHarnessImport` work without access to the source repository.

- [ ] Run the test and confirm the intended red state:

  ```bash
  node --import tsx --test tests/migration/harness.test.ts
  ```

  Expected: failure because `lib/migration/harness.ts` does not exist.

- [ ] Implement the migration library with `node:fs/promises`, `node:path`, `node:crypto`, and shell-free Git subprocesses. Resolve the repository containing `sourceKnowledgeRoot`, require its `rev-parse HEAD` to equal `sourceRevision`, enumerate committed paths with NUL-delimited `git ls-tree -rz --name-only <revision> -- .knowledge`, and read each blob with `git show <revision>:<path>`. Never read migration bytes from the working tree. Sort selected paths lexicographically, hash raw `Buffer` values, stage under target `work/`, then atomically rename. Never mutate or normalize note content.

- [ ] Implement CLI subcommands:

  ```text
  migrate-quantum-harness.ts import --source <absolute .knowledge path> --revision <40-char SHA>
  migrate-quantum-harness.ts verify
  migrate-quantum-harness.ts verify-source --source <absolute .knowledge path> --revision <40-char SHA>
  ```

  Reject a missing/relative source path, an invalid revision, unknown flags, and a source whose parent Git revision does not equal `--revision`.

- [ ] Re-run the unit test and typecheck:

  ```bash
  node --import tsx --test tests/migration/harness.test.ts
  npx --no-install tsc --noEmit
  ```

  Expected: pass and exit 0.

- [ ] Run the real, read-only import:

  ```bash
  node --import tsx scripts/migrate-quantum-harness.ts import \
    --source /home/chance/quantum.harness/.knowledge \
    --revision d2532921cc6779559658d85bc665c42d11012331
  node --import tsx scripts/migrate-quantum-harness.ts verify
  find drafts/imported-quantum-harness -type f -name '*.md' | wc -l
  ```

  Expected messages: `Imported 280 cards (11078725 bytes)` and `Verified 280 cards (11078725 bytes)`; final count `280`.

- [ ] Independently compare every imported file and the bibliography to the source:

  ```bash
  node --import tsx scripts/migrate-quantum-harness.ts verify-source \
    --source /home/chance/quantum.harness/.knowledge \
    --revision d2532921cc6779559658d85bc665c42d11012331
  test -z "$(git -C /home/chance/quantum.harness \
    status --porcelain=v1 --untracked-files=all -- .knowledge)"
  ```

  Expected: `Verified source parity for 280 cards (11078725 bytes) and literature/ref.bib`. This command rehashes every manifest path in source and destination, checks the bibliography bytes, rejects an extra/missing imported Markdown file, and ignores source files that are intentionally outside the manifest.

- [ ] Commit the migration implementation and imported candidates:

  ```bash
  git add lib/migration scripts/migrate-quantum-harness.ts tests/migration \
    drafts/imported-quantum-harness literature/ref.bib \
    docs/migrations/quantum-harness-knowledge.json
  git commit -m "feat: import harness cards as untrusted drafts"
  ```

## Task 3: Parse the bibliography and generate method indexes

**Files:**

- Create: `lib/literature/bibliography.ts`
- Create: `lib/literature/indexes.ts`
- Create: `lib/literature/index.ts`
- Create: `scripts/literature.ts`
- Create: `tests/literature/bibliography.test.ts`
- Create: `tests/fixtures/literature/ref.bib`
- Create: `literature/<method>/INDEX.md` for 13 methods

Use this normalized model:

```ts
export interface LiteratureEntry {
  citekey: string;
  type: string;
  title: string;
  authors: readonly string[];
  year?: string;
  doi?: string;
  arxiv?: string;
  methods: readonly string[];
}

export function parseBibliography(input: string): LiteratureEntry[];
export async function loadBibliography(path: string): Promise<LiteratureEntry[]>;
export function entriesByMethod(
  entries: readonly LiteratureEntry[],
): ReadonlyMap<string, readonly LiteratureEntry[]>;
export function renderMethodIndex(
  method: string,
  entries: readonly LiteratureEntry[],
): string;
export async function writeMethodIndexes(
  literatureRoot: string,
  entries: readonly LiteratureEntry[],
): Promise<readonly string[]>;
export function findEntry(
  entries: readonly LiteratureEntry[],
  citekey: string,
): LiteratureEntry;
```

- [ ] Write failing tests using a small BibTeX fixture. Assert normalized authors, title/year/DOI/eprint fields, sorted unique method slugs, duplicate-key rejection, parser-error rejection, empty-title rejection, missing-keyword rejection, unsafe method-slug rejection, unsafe citekey rejection, and deterministic output. A safe method matches `^[a-z0-9]+(?:-[a-z0-9]+)*$`; a safe citekey matches `^[A-Za-z0-9][A-Za-z0-9._:-]*$` and can never contain `/` or `\\`.

- [ ] Assert the generated `INDEX.md` format contains only bibliography-derived metadata and external DOI/arXiv links. It must contain no copied full text, no current date, and no `.raw` or `.figures` links.

- [ ] Run:

  ```bash
  node --import tsx --test tests/literature/bibliography.test.ts
  ```

  Expected: missing-module failure.

- [ ] Implement parsing through `@retorquere/bibtex-parser`; do not implement a second ad-hoc BibTeX grammar. Treat parser warnings/errors as explicit failures. Normalize arXiv identifiers by removing `arXiv:` and URL prefixes while retaining an explicit `vN` suffix when present.

- [ ] Implement `scripts/literature.ts index`, which loads `literature/ref.bib`, generates one directory/index per method keyword, and removes no user-owned file. Permit existing ignored `.raw/` and `.figures/` trees. Refuse a method directory containing any unexpected committed file instead of deleting or overwriting it.

- [ ] Run tests and generate the production indexes:

  ```bash
  node --import tsx --test tests/literature/bibliography.test.ts
  node --import tsx scripts/literature.ts index
  find literature -mindepth 1 -maxdepth 1 -type d | wc -l
  find literature -mindepth 2 -maxdepth 2 -name INDEX.md | wc -l
  npx --no-install tsc --noEmit
  ```

  Expected: `85 bibliography entries; 13 method indexes; 65 arXiv entries`, then both counts are `13`.

- [ ] Run the index command twice and prove determinism:

  ```bash
  find literature -type f \( -name INDEX.md -o -name ref.bib \) -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum > /tmp/research-loop-literature-before.sha256
  node --import tsx scripts/literature.ts index
  find literature -type f \( -name INDEX.md -o -name ref.bib \) -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum > /tmp/research-loop-literature-after.sha256
  cmp /tmp/research-loop-literature-before.sha256 \
    /tmp/research-loop-literature-after.sha256
  ```

  The second run must not change bytes.

- [ ] Commit:

  ```bash
  git add lib/literature/bibliography.ts lib/literature/indexes.ts \
    lib/literature/index.ts scripts/literature.ts tests/literature \
    tests/fixtures/literature literature
  git commit -m "feat: generate literature method indexes"
  ```

## Task 4: Parse QMD into typed knowledge pages

**Files:**

- Create: `lib/knowledge/types.ts`
- Create: `lib/knowledge/parser.ts`
- Create: `tests/knowledge/parser.test.ts`

Define the parser contract:

```ts
export const KNOWLEDGE_CATEGORIES = ["theory", "experiment", "codes"] as const;
export type KnowledgeCategory = (typeof KNOWLEDGE_CATEGORIES)[number];
export type PageKind = "index" | "content";

export interface SourceLocation {
  file: string;
  line: number;
  column: number;
}

export interface Diagnostic {
  code: string;
  message: string;
  location: SourceLocation;
}

export interface MarkdownLink {
  kind: "link" | "image";
  label: string;
  target: string;
  location: SourceLocation;
}

export interface ParsedKnowledgePage {
  id: string;                    // POSIX path relative to knowledge/
  absolutePath: string;
  topicId: string;               // owning index id; an index owns itself
  kind: PageKind;
  title?: string;
  description?: string;
  category?: KnowledgeCategory;
  aliases: readonly string[];
  body: string;
  readingMap: readonly MarkdownLink[];
  relatedTopics: readonly MarkdownLink[];
  localLinks: readonly MarkdownLink[];
  citations: readonly { key: string; location: SourceLocation }[];
  unsafeHtml: readonly {
    kind: "script" | "inline-handler";
    location: SourceLocation;
  }[];
  parseDiagnostics: readonly Diagnostic[];
}

export function parseKnowledgePage(input: {
  repoRoot: string;
  knowledgeRoot: string;
  absolutePath: string;
  source: string;
}): ParsedKnowledgePage;
```

- [ ] Write parser tests with an in-memory `index.qmd` containing valid YAML, `## Reading map`, `## Related topics`, an image, an ordinary local link, citation `[@fixture2026]`, fenced code containing fake `@ignored`, and raw `<script>`/`onclick`. Assert exact IDs and one-based source locations.

- [ ] Add table tests for these exact diagnostic codes:

  ```text
  FRONTMATTER_MISSING
  FRONTMATTER_INVALID
  TITLE_REQUIRED
  DESCRIPTION_REQUIRED
  CATEGORY_REQUIRED
  CATEGORY_INVALID
  INDEX_CATEGORY_FORBIDDEN
  ALIASES_INVALID
  FRONTMATTER_KEY_FORBIDDEN
  READING_MAP_DUPLICATE
  RELATED_TOPICS_DUPLICATE
  ```

  Also assert that only direct list-item links beneath the two level-2 reserved headings enter their special arrays; links in prose, nested unrelated headings, code, and inline code do not. The frontmatter allowlist is exactly `title`, `description`, `categories`, and `aliases`; explicitly test rejection of page-level `execute`, `filters`, `include-before-body`, `include-after-body`, `include-in-header`, `resources`, `format`, and any unknown key.

- [ ] Run the test and confirm missing-module failure:

  ```bash
  node --import tsx --test tests/knowledge/parser.test.ts
  ```

- [ ] Implement exact opening/closing `---` frontmatter extraction with `yaml.parseDocument`, enforce the strict key allowlist, then parse the body with unified/remark. Normalize IDs to POSIX separators. Record all parse diagnostics rather than throwing on the first bad page. Account for frontmatter lines when reporting Markdown AST locations. This allowlist prevents a page from overriding execution or injecting Quarto filters/includes/resources.

- [ ] Recognize Pandoc-style citation keys only in Markdown text nodes, including multiple citations in one bracket. Ignore code, inline code, URLs, and email addresses.

- [ ] Re-run:

  ```bash
  node --import tsx --test tests/knowledge/parser.test.ts
  npx --no-install tsc --noEmit
  ```

  Expected: pass and exit 0.

- [ ] Commit:

  ```bash
  git add lib/knowledge/types.ts lib/knowledge/parser.ts tests/knowledge/parser.test.ts
  git commit -m "feat: parse Quarto knowledge pages"
  ```

## Task 5: Build and validate the curated KnowledgeGraph

**Files:**

- Create: `lib/knowledge/graph.ts`
- Create: `lib/knowledge/validate.ts`
- Create: `tests/knowledge/graph-validation.test.ts`
- Create: `tests/fixtures/knowledge/valid/_quarto.yml`
- Create: `tests/fixtures/knowledge/valid/index.qmd`
- Create: `tests/fixtures/knowledge/valid/ising/index.qmd`
- Create: `tests/fixtures/knowledge/valid/ising/proof.qmd`
- Create: `tests/fixtures/knowledge/valid/ising/proposal.qmd`
- Create: `tests/fixtures/knowledge/valid/ising/verified-code.qmd`
- Create: `tests/fixtures/knowledge/valid/ising/diagram.svg`
- Create: `knowledge/_quarto.yml`
- Create: `knowledge/index.qmd`

Define the graph contract:

```ts
export interface KnowledgeGraph {
  repoRoot: string;
  knowledgeRoot: string;
  pages: ReadonlyMap<string, ParsedKnowledgePage>;
  childrenByIndex: ReadonlyMap<string, readonly string[]>;
  parentByPage: ReadonlyMap<string, string>;
  relatedByIndex: ReadonlyMap<string, readonly string[]>;
  assets: ReadonlyMap<string, string>; // POSIX relative path -> absolute path
}

export interface LoadKnowledgeOptions {
  repoRoot?: string;
  knowledgeDir?: string;
}

export interface ValidationReport {
  ok: boolean;
  diagnostics: readonly Diagnostic[];
}

export async function loadKnowledge(
  options?: LoadKnowledgeOptions,
): Promise<KnowledgeGraph>;

export async function validateGraph(
  graph: KnowledgeGraph,
  options: { bibliographyPath: string },
): Promise<ValidationReport>;

export async function validateKnowledge(
  options?: LoadKnowledgeOptions & { bibliographyPath?: string },
): Promise<ValidationReport>;
```

- [ ] Build a valid fixture. Root reading map links to `ising/index.qmd`; Ising reading map links in order to `proof.qmd`, `proposal.qmd`, and `verified-code.qmd`. Both indexes contain one `Reading map`; at least one contains the optional `Related topics` heading. The three content pages use `theory`, `experiment`, and `codes` respectively. `proof.qmd` cites `fixture2026` and embeds `diagram.svg`. The fixture bibliography defines `fixture2026`. The fixture `_quarto.yml` uses the same fixed safe base config as production.

- [ ] Write table-driven failing tests that clone and mutate the fixture under `mkdtemp`. Assert sorted diagnostics for:

  ```text
  TOPIC_INDEX_MISSING
  INDEX_READING_MAP_REQUIRED
  ORPHAN_CHILD
  NON_DIRECT_CHILD
  DUPLICATE_PARENT
  CONTAINMENT_CYCLE
  RELATED_TARGET_NOT_INDEX
  LINK_MISSING
  LINK_OUTSIDE_KNOWLEDGE
  CITATION_MISSING
  SCRIPT_FORBIDDEN
  INLINE_HANDLER_FORBIDDEN
  SYMLINK_FORBIDDEN
  ```

  Include missing topic index, omitted direct child, cross-directory containment, duplicate parent, containment cycle, broken fragment-stripped link, unresolved citation, `../` escape, absolute path, unsafe HTML, and symlink fixtures. Also assert that omitting `Related topics` is valid and produces an empty related-edge list.

- [ ] Run and confirm failure because graph exports do not exist:

  ```bash
  node --import tsx --test tests/knowledge/graph-validation.test.ts
  ```

- [ ] Implement recursive `.qmd` discovery with `node:fs/promises`. Ignore dot directories, `_quarto.yml`, drafts, literature, and generated outputs by construction. A directory with QMD descendants is a topic only when it has a direct `index.qmd`.

- [ ] Resolve reading-map targets after removing URL query/fragment syntax. A direct content page is owned by its directory index; a child topic index is owned by its direct parent index. Every direct child must occur exactly once in that parent's curated reading map. Related-topic links must resolve to an index but may form cycles.

- [ ] Resolve every local link/image with `realpath`; allow HTTP(S) and `mailto`, reject absolute local paths, symlinks, and any real path outside `knowledgeRoot`. Load citation keys through `lib/literature/bibliography.ts`, not a second BibTeX parser.

- [ ] Sort diagnostics by file, line, column, then code. Never rely on filesystem enumeration order.

- [ ] Create the production trusted scaffold only:

  `knowledge/index.qmd`:

  ```markdown
  ---
  title: Research Loop Knowledge
  description: User-learned and user-approved research knowledge.
  ---

  This site contains only knowledge the user has learned, reviewed, and chosen to promote.

  ## Reading map

  No trusted topics have been promoted yet.

  ## Related topics

  No related trusted topics have been added yet.
  ```

  `knowledge/_quarto.yml` contains exactly these fixed base settings and no hand-maintained sidebar/category pages:

  ```yaml
  project:
    type: website
  website:
    title: Research Loop Knowledge
    site-path: /knowledge/
    search: true
  format:
    html:
      toc: true
  execute:
    enabled: false
  ```

- [ ] Run:

  ```bash
  node --import tsx --test tests/knowledge/graph-validation.test.ts
  npx --no-install tsc --noEmit
  ```

  Expected: pass and exit 0.

- [ ] Commit:

  ```bash
  git add lib/knowledge/graph.ts lib/knowledge/validate.ts \
    tests/knowledge/graph-validation.test.ts tests/fixtures/knowledge \
    knowledge/_quarto.yml knowledge/index.qmd
  git commit -m "feat: validate the curated knowledge graph"
  ```

## Task 6: Add the deterministic agent resolver

**Files:**

- Create: `lib/knowledge/resolve.ts`
- Create: `lib/knowledge/index.ts`
- Create: `scripts/knowledge.ts`
- Create: `tests/knowledge/resolve.test.ts`

Define the resolver result:

```ts
export type MatchKind =
  | "exact-title"
  | "exact-alias"
  | "title-term"
  | "alias-term"
  | "description-term"
  | "body-term";

export interface ResolveCandidate {
  page: string;
  topic: string;
  title: string;
  matchKind: MatchKind;
  tier: number;
  matchedTerms: number;
}

export interface ReadingBundle {
  topic: string;
  ancestorIndexes: readonly string[];
  contentPages: readonly string[];
  orderedFiles: readonly string[];
}

export type ResolveResult =
  | {
      schemaVersion: 1;
      query: string;
      status: "match";
      bundle: ReadingBundle;
      alternatives: readonly ResolveCandidate[];
    }
  | {
      schemaVersion: 1;
      query: string;
      status: "ambiguous";
      bundle: null;
      alternatives: readonly ResolveCandidate[];
    }
  | {
      schemaVersion: 1;
      query: string;
      status: "no-match";
      bundle: null;
      alternatives: readonly [];
    };

export function resolveGraph(graph: KnowledgeGraph, query: string): ResolveResult;
export async function resolveKnowledge(
  query: string,
  options?: LoadKnowledgeOptions & { bibliographyPath?: string },
): Promise<ResolveResult>;
```

All paths exposed in a `ReadingBundle` are POSIX repository-relative paths such as `knowledge/index.qmd`, so an agent can read them without guessing a root.

- [ ] Write failing tests for Unicode NFKC/case normalization, exact title, exact alias, title terms, alias terms, description/body fallback, exact index match, exact content match, stable path tie-break, curated-order tie-break, and equally ranked matches in different topics.

- [ ] Assert the exact tier order: title `0`, alias `1`, title-term `2`, alias-term `3`, description `4`, body `5`. Within a tier, sort by descending matched-term count, then curated reading order, then POSIX path.

- [ ] Assert bundle semantics:

  - an index match includes every direct content page from its reading map;
  - a content match includes the tied selected pages from its single topic;
  - every bundle prepends the root-to-target chain of indexes;
  - `orderedFiles` is ancestor indexes followed by content pages, de-duplicated;
  - equally best candidates from different topics yield `ambiguous`, never an arbitrary winner;
  - no match returns `no-match` and never searches drafts or literature.
  - `resolveKnowledge` refuses an invalid graph by throwing `KnowledgeValidationError` with all diagnostics; it never returns a bundle from unvalidated pages.

- [ ] Run and confirm missing-resolver failure:

  ```bash
  node --import tsx --test tests/knowledge/resolve.test.ts
  ```

- [ ] Export `KnowledgeValidationError` from `validate.ts`. Implement `resolveKnowledge` as load → complete validation against the configured bibliography → pure `resolveGraph`; the CLI and public API may not bypass that gate.

- [ ] Implement tokenization exactly as:

  ```ts
  text
    .normalize("NFKC")
    .toLocaleLowerCase("en-US")
    .match(/[\p{L}\p{N}]+/gu) ?? [];
  ```

  Reject an empty normalized query with `KnowledgeQueryError`. Keep ranking pure and deterministic.

- [ ] Implement only `check` and `resolve --query <text>` in `scripts/knowledge.ts` at this task. Use `node:util.parseArgs`. `check` exits 1 when invalid. `resolve` prints exactly formatted JSON and exits 0 for `match`, `ambiguous`, and `no-match`; invocation/validation failures exit 1. Do not add placeholder `build` or `preview` branches.

- [ ] Run:

  ```bash
  node --import tsx --test tests/knowledge/resolve.test.ts
  node --import tsx scripts/knowledge.ts check
  node --import tsx scripts/knowledge.ts resolve --query "triangular TFIM"
  npx --no-install tsc --noEmit
  ```

  Expected: tests and check pass; the production empty scaffold returns JSON with `status: "no-match"`.

- [ ] Commit:

  ```bash
  git add lib/knowledge/resolve.ts lib/knowledge/index.ts \
    scripts/knowledge.ts tests/knowledge/resolve.test.ts
  git commit -m "feat: resolve deterministic knowledge bundles"
  ```

## Task 7: Project one KnowledgeGraph into a temporary Quarto site

**Files:**

- Create: `lib/knowledge/quarto.ts`
- Create: `tests/knowledge/quarto-project.test.ts`

Use this interface:

```ts
export interface QuartoProject {
  projectDir: string;
  outputDir: string;
  categoryUrls: Readonly<Record<KnowledgeCategory, string>>;
}

export async function materializeQuartoProject(input: {
  graph: KnowledgeGraph;
  workspace: string;
  bibliographyPath: string;
}): Promise<QuartoProject>;
```

- [ ] Write a failing test that materializes the valid fixture and asserts:

  - trusted QMD and referenced assets are copied byte-for-byte;
  - the base `_quarto.yml` is parsed, then its fixed safety settings are reasserted;
  - generated title is `Research Loop Knowledge`;
  - `website.site-path` is `/knowledge/`;
  - search is enabled and `execute.enabled` is `false`;
  - the supplied bibliography is copied to temp `references/ref.bib`, configured as `bibliography: references/ref.bib`, and remains outside the trusted graph;
  - nested sidebar order comes only from reading maps;
  - generated files are exactly `categories/theory/index.qmd`, `categories/experiment/index.qmd`, and `categories/codes/index.qmd`;
  - category entries contain graph-derived title, description, and relative link;
  - category URLs are exactly `/knowledge/categories/theory/`, `/knowledge/categories/experiment/`, and `/knowledge/categories/codes/`;
  - drafts, literature trees, unreferenced files, and generated category pages never enter `graph.pages`.
  - titles/descriptions containing `]`, `:`, quotes, and newlines are escaped safely in generated YAML and Markdown links.

- [ ] Run and confirm missing-module failure:

  ```bash
  node --import tsx --test tests/knowledge/quarto-project.test.ts
  ```

- [ ] Implement a deterministic projection. Copy validated QMD plus validated referenced local assets only. Copy the supplied bibliography bytes to `references/ref.bib`. Parse the committed base config and require it to match the fixed safe schema exactly—no filters, includes, resources, extensions, or execution overrides—then write a generated temp `_quarto.yml` with `bibliography: references/ref.bib` and the graph-derived sidebar.

- [ ] Generate category pages in curated graph order, then POSIX path order. Do not write them to `knowledge/`.

- [ ] Re-run:

  ```bash
  node --import tsx --test tests/knowledge/quarto-project.test.ts
  npx --no-install tsc --noEmit
  ```

  Expected: pass and exit 0.

- [ ] Commit:

  ```bash
  git add lib/knowledge/quarto.ts tests/knowledge/quarto-project.test.ts
  git commit -m "feat: project knowledge into Quarto"
  ```

## Task 8: Render Quarto safely and atomically publish static output

**Files:**

- Create: `lib/knowledge/site.ts`
- Create: `tests/knowledge/quarto-build.integration.test.ts`
- Modify: `lib/knowledge/index.ts`
- Modify: `scripts/knowledge.ts`

Use dependency injection for process tests:

```ts
export interface ProcessRunner {
  run(
    command: string,
    args: readonly string[],
    options: { cwd: string; stdio: "inherit" | "pipe"; shell: false },
  ): Promise<void>;
}

export interface AtomicDirectoryOps {
  rename(from: string, to: string): Promise<void>;
  rm(path: string, options: { recursive: true; force: true }): Promise<void>;
}

export interface BuildKnowledgeSiteOptions extends LoadKnowledgeOptions {
  bibliographyPath?: string;
  quartoBin?: string;
  runner?: ProcessRunner;
  directoryOps?: AtomicDirectoryOps;
}

export interface BuildKnowledgeSiteResult {
  outputDir: string;
  renderedFiles: number;
}

export async function buildKnowledgeSite(
  options?: BuildKnowledgeSiteOptions,
): Promise<BuildKnowledgeSiteResult>;

export async function previewKnowledgeSite(
  options?: BuildKnowledgeSiteOptions,
): Promise<void>;
```

- [ ] Write fake-runner tests first:

  - pre-create `public/knowledge/sentinel.html`, reject the Quarto call, and assert sentinel bytes remain unchanged;
  - on success, have the runner create `_site/index.html` and nested pages, then assert the old sentinel disappears;
  - inject failure during final rename through `AtomicDirectoryOps` and assert the old output is restored;
  - assert command/arguments are arrays and `shell` is exactly `false`.

- [ ] Add a real Quarto integration fixture containing inline/display math, a citation, nested topic, SVG asset, all three categories, a harmless executable code-cell declaration, and a malicious page-level `execute: true` variant. Assert validation rejects the frontmatter override. Invoke the installed Quarto 1.9.38 on the safe fixture and assert root/nested/category HTML exists, the title and bibliography render, mathematics produces MathML/Quarto math markup, and no code-cell output is created.

- [ ] Assert output filenames contain no `.qmd`, `ref.bib`, `drafts`, `literature`, `.raw`, or `.figures` path components.

- [ ] Run and confirm failure before implementation:

  ```bash
  node --import tsx --test tests/knowledge/quarto-build.integration.test.ts
  ```

- [ ] Implement this exact order:

  1. load and validate the graph;
  2. throw `KnowledgeValidationError` containing the complete report on failure;
  3. create a same-filesystem workspace under `work/knowledge-build-*`;
  4. materialize the Quarto project;
  5. spawn `quarto render . --no-execute` with an argument array and `shell: false`;
  6. require `_site/index.html` and audit forbidden output names;
  7. rename the existing `public/knowledge` to a unique sibling backup;
  8. rename the verified `_site` into `public/knowledge`;
  9. restore the backup if either final rename fails;
  10. remove the backup after success and always remove workspaces in `finally`.

- [ ] Implement preview by materializing the same validated project and running `quarto preview . --no-browser --no-execute`. Keep the workspace alive until Quarto exits, then clean it.

- [ ] Add `build` and `preview` branches to `scripts/knowledge.ts` with no path/output override flags. The production CLI always reads `<repo>/knowledge`, validates against `<repo>/literature/ref.bib`, and replaces only `<repo>/public/knowledge`. Tests call the library directly with a temporary `repoRoot`; the output is always `<repoRoot>/public/knowledge` and therefore cannot target an arbitrary directory.

- [ ] Run:

  ```bash
  node --import tsx --test tests/knowledge/*.test.ts
  node --import tsx scripts/knowledge.ts build
  test -f public/knowledge/index.html
  test -f public/knowledge/categories/theory/index.html
  test -f public/knowledge/categories/experiment/index.html
  test -f public/knowledge/categories/codes/index.html
  npx --no-install tsc --noEmit
  git status --short --ignored | rg 'public/knowledge|work/'
  ```

  Expected: tests pass; four HTML checks pass; generated paths appear only with `!!` ignored status.

- [ ] Commit source/tests only:

  ```bash
  git add lib/knowledge/site.ts lib/knowledge/index.ts scripts/knowledge.ts \
    tests/knowledge/quarto-build.integration.test.ts
  git commit -m "feat: build the Quarto knowledge subsite"
  ```

## Task 9: Add safe, selected-file draft preview

**Files:**

- Create: `drafts/_quarto.yml`
- Create: `lib/drafts/preview.ts`
- Create: `scripts/draft-preview.ts`
- Create: `tests/drafts/preview.test.ts`

Use this boundary:

```ts
export function resolveDraftFile(input: {
  repoRoot: string;
  requestedFile: string;
}): Promise<{ draftsRoot: string; absoluteFile: string; relativeFile: string }>;

export async function previewDraft(input: {
  repoRoot?: string;
  requestedFile: string;
  quartoBin?: string;
  runner?: ProcessRunner;
}): Promise<void>;
```

- [ ] Write failing tests that accept nested `.md` and `.qmd` files inside `drafts/`; reject a missing file, directory, wrong extension, absolute external file, `..` escape, and symlink escape. Assert the runner receives `quarto preview <relative-file> --no-browser --no-execute` with `cwd` set to the real drafts root and `shell: false`.

- [ ] Run and confirm missing-module failure:

  ```bash
  node --import tsx --test tests/drafts/preview.test.ts
  ```

- [ ] Create `drafts/_quarto.yml`:

  ```yaml
  project:
    type: default
    output-dir: .preview
  format:
    html:
      toc: true
  execute:
    enabled: false
  ```

  It must define no website/sidebar/category structure.

- [ ] Implement realpath containment, extension checks, and a shell-free Quarto spawn that always adds `--no-execute`. The preview command must never write to `public/knowledge/`.

- [ ] Implement CLI `--file <repo-relative path>` with an actionable error and exit 2 for a missing argument.

- [ ] Run:

  ```bash
  node --import tsx --test tests/drafts/preview.test.ts
  cd drafts
  quarto render imported-quantum-harness/conventions.md \
    --output-dir .preview/smoke --no-execute
  find .preview/smoke -type f -name conventions.html -print -quit | rg .
  cd ..
  npx --no-install tsc --noEmit
  ```

  Expected: pass. The smoke output is ignored and does not alter the production site.

- [ ] Commit:

  ```bash
  git add drafts/_quarto.yml lib/drafts/preview.ts scripts/draft-preview.ts \
    tests/drafts/preview.test.ts
  git commit -m "feat: preview untrusted draft notes safely"
  ```

## Task 10: Safely inspect arXiv source archives and extract figures

**Files:**

- Create: `lib/literature/archive.ts`
- Create: `lib/literature/figures.ts`
- Create: `tests/literature/archive.test.ts`
- Create: `tests/fixtures/archives/**`

Define explicit resource ceilings:

```ts
export const ARCHIVE_LIMITS = {
  compressedBytes: 100 * 1024 * 1024,
  extractedBytes: 512 * 1024 * 1024,
  singleFileBytes: 128 * 1024 * 1024,
  entries: 10_000,
} as const;

export interface ExtractionResult {
  format: "tar" | "tar-gzip" | "gzip-single-tex";
  sourceRoot: string;
  mainTex: string;
  files: readonly { path: string; bytes: number; sha256: string }[];
  figures: readonly { source: string; destination: string; sha256: string }[];
}
```

- [ ] Write tests for plain tar, tar.gz, and a gzip-compressed single TeX file. Assert preservation of `.tex`, `.sty`, `.cls`, `.bib`, and source images; deterministic file manifests; and main-TeX selection.

- [ ] Write malicious archive fixtures manually with 512-byte tar headers so the test tool does not sanitize the attack. Reject `../`, absolute paths, a name field with non-zero bytes after its first NUL terminator, backslash traversal, normalized duplicate names, symlink, hardlink, character/block device, FIFO, too many entries, oversized single file, oversized total, and decompression-bomb ceilings. Ordinary NUL padding in a valid tar header remains valid.

- [ ] Run and confirm missing-module failure:

  ```bash
  node --import tsx --test tests/literature/archive.test.ts
  ```

- [ ] Implement a preflight pass before extraction. Accept only regular files and directories. Validate normalized POSIX paths before writing any entry. Extract into a caller-provided staging directory only after the complete archive passes preflight.

- [ ] Select `mainTex` only from files containing both `\\documentclass` and `\\begin{document}`. Rank preferred basenames (`main`, `paper`, `article`, matching citekey), then shallower depth. If multiple files share the best semantic rank, reject the archive with an ambiguity error and list candidates in lexical order. Reject an archive with no candidate. Lexical order is for deterministic diagnostics, not a silent semantic tie-break.

- [ ] Copy figure extensions `.pdf`, `.png`, `.jpg`, `.jpeg`, `.eps`, `.svg`, `.tif`, and `.tiff` byte-for-byte to the figures staging tree while preserving relative paths. Never convert images and never compile TeX.

- [ ] Run:

  ```bash
  node --import tsx --test tests/literature/archive.test.ts
  npx --no-install tsc --noEmit
  ```

  Expected: all benign/malicious cases pass.

- [ ] Commit:

  ```bash
  git add lib/literature/archive.ts lib/literature/figures.ts \
    tests/literature/archive.test.ts tests/fixtures/archives
  git commit -m "feat: safely unpack literature source archives"
  ```

## Task 11: Fetch version-pinned arXiv sources atomically

**Files:**

- Create: `lib/literature/arxiv.ts`
- Create: `lib/literature/fetch.ts`
- Create: `tests/literature/fetch.test.ts`
- Modify: `lib/literature/index.ts`
- Modify: `scripts/literature.ts`

Define the persisted manifest without timestamps:

```ts
export interface LiteratureManifest {
  schemaVersion: 1;
  citekey: string;
  arxiv: { id: string; version: string };
  source: { url: string; bytes: number; sha256: string };
  pdf: { url: string; bytes: number; sha256: string };
  extraction: {
    format: ExtractionResult["format"];
    mainTex: string;
    files: ExtractionResult["files"];
    figures: ExtractionResult["figures"];
  };
}

export async function fetchLiteratureEntry(options: {
  literatureRoot: string;
  citekey: string;
  fetchImpl?: typeof fetch;
}): Promise<LiteratureManifest>;

export async function syncLiterature(options: {
  literatureRoot: string;
  fetchImpl?: typeof fetch;
}): Promise<{ fetched: number; reused: number; skippedNoArxiv: number }>;
```

- [ ] Write mocked-fetch tests for an explicit eprint version, Atom API latest-version resolution, an existing pinned manifest, source/PDF HTTP errors, timeout, response larger than the compressed limit, invalid archive, extraction failure, repeated fetch reuse, no-arXiv entry, and multi-entry sync.

- [ ] Assert URLs are exactly `https://export.arxiv.org/e-print/<id>vN` for source and `https://arxiv.org/pdf/<id>vN` for PDF. Requests use a descriptive `research-loop/<package version>` User-Agent, follow redirects, stream with byte bounds, and abort after 60 seconds.

- [ ] Assert a failed download/extraction leaves an existing `.raw/<citekey>` and `.figures/<citekey>` byte-identical and removes staging.

- [ ] Run and confirm missing-module failure:

  ```bash
  node --import tsx --test tests/literature/fetch.test.ts
  ```

- [ ] Implement version resolution in this order: explicit `vN` on the BibTeX eprint; existing manifest pin; otherwise arXiv Atom entry ID. Never silently change a previously pinned local version. A future refresh feature is out of scope.

- [ ] Stage the complete result under `literature/.staging/<uuid>`. Store original response as `source.tar.gz`, extracted tree as `source/`, PDF as `paper.pdf`, and deterministic `manifest.json`; stage figures separately. Atomically swap the citekey directories with rollback.

- [ ] Extend CLI:

  ```text
  literature.ts fetch --key <citekey>
  literature.ts sync
  ```

  `fetch` exits 2 for a missing key, 1 for operational failure, 0 for fetched/reused. `sync` processes all 85 entries in citekey order, fetches/reuses the 65 arXiv entries, and explicitly counts the 20 entries without arXiv source.

- [ ] Run unit tests and one real on-demand smoke fetch:

  ```bash
  node --import tsx --test tests/literature/*.test.ts
  node --import tsx scripts/literature.ts fetch --key weinberg_2016_quspin
  test -f literature/ed/.raw/weinberg_2016_quspin/manifest.json
  test -f literature/software/.raw/weinberg_2016_quspin/manifest.json
  npx --no-install tsc --noEmit
  ```

  A multi-method reference may share one content-addressed staged download internally, but each method path required by the approved layout must resolve to the same verified bytes. Do not use Git-tracked symlinks for local-only data.

- [ ] Prove local source material is ignored and no lossy full text exists:

  ```bash
  git status --short --ignored literature | sed -n '1,80p'
  git ls-files 'literature/**' | rg '(^|/)(rendered\.md|\.raw/|\.figures/)' && exit 1 || true
  find literature -name rendered.md -print
  ```

  Expected: `.raw`/`.figures` are ignored, and both tracked/actual `rendered.md` searches are empty.

- [ ] Commit code/tests only:

  ```bash
  git add lib/literature/arxiv.ts lib/literature/fetch.ts \
    lib/literature/index.ts scripts/literature.ts tests/literature/fetch.test.ts
  git commit -m "feat: fetch versioned arXiv source material"
  ```

## Task 12: Add discoverable Agent skills and trust-boundary instructions

**Required skill before this task:** `superpowers:writing-skills`

**Files:**

- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `.claude/skills` symlink to `../skills`
- Create: `skills/read-knowledge/SKILL.md`
- Create: `skills/review-draft/SKILL.md`
- Create: `skills/download-ref/SKILL.md`
- Create: `docs/skills.md`
- Create: `tests/agent/skill-contracts.test.ts`

- [ ] Read `superpowers:writing-skills` completely. Then write failing static-contract tests that parse each skill's YAML frontmatter and body.

- [ ] For `read-knowledge`, assert the skill:

  - triggers before stating a research fact or interpretation that might be covered by learned knowledge;
  - runs `make knowledge-resolve QUERY="<the user's research question>"`;
  - on `match`, reads every path in `bundle.orderedFiles` before answering;
  - on `ambiguous`, presents the alternatives and does not choose silently;
  - on `no-match`, says the learned knowledge has no match;
  - never reads `drafts/` or `literature/` as trusted fallback;
  - names any separate external-research/source-audit workflow explicitly.

- [ ] For `review-draft`, assert the skill:

  - accepts exactly one file under `drafts/`;
  - reports four sections only: language/grammar, factual errors or uncertainty, Quarto/Markdown format, placement recommendation;
  - recommends exactly one existing `knowledge/<topic>/...` destination or one new topic directory plus filename;
  - recommends exactly one category (`theory`, `experiment`, or `codes`) for a content page;
  - does not edit, move, split, rewrite, or promote before user confirmation;
  - after confirmation, creates/uses a non-`main` branch, converts to `.qmd`, updates the parent reading map, validates, and presents a diff/PR;
  - states that only the user's merge makes the note trusted.

- [ ] For `download-ref`, assert the skill:

  - uses `make literature-fetch KEY=<citekey>` and the committed bibliography/index flow;
  - keeps external sources under `literature/`, organized by method keywords;
  - stores source TeX/PDF under `.raw` and images under `.figures`;
  - never compiles TeX, produces `rendered.md`, or promotes paper text into knowledge;
  - verifies formulas against source TeX/PDF rather than lossy extraction.

- [ ] Run and confirm the tests fail because the skills do not exist:

  ```bash
  node --import tsx --test tests/agent/skill-contracts.test.ts
  ```

- [ ] Write a concise target-repository `AGENTS.md` that encodes the physical trust boundary, mandatory resolver-first rule, draft-review/promotion rule, literature separation, production build commands, dashboard preservation, and Sites project-ID rule. Do not copy the quantum harness's method-specific compute instructions into this repository.

- [ ] Write `CLAUDE.md` as one instruction line pointing to `@AGENTS.md`. Create the discovery link:

  ```bash
  mkdir -p .claude
  ln -s ../skills .claude/skills
  test "$(readlink .claude/skills)" = "../skills"
  ```

- [ ] Author the three skills with narrow triggers and the tested commands. `read-knowledge` and `review-draft` are original Research Loop skills. `download-ref` is an adaptation of `/home/chance/quantum.harness/skills/download-ref/SKILL.md`; preserve attribution in `docs/skills.md`, but rewrite commands and paths for this repository.

- [ ] In `docs/skills.md`, include a table with skill, role, ownership/provenance, trusted inputs, writes, and prohibited behavior. State that external Superpowers skills are runtime dependencies and are not copied into this repository.

- [ ] Run:

  ```bash
  node --import tsx --test tests/agent/skill-contracts.test.ts
  npx --no-install tsc --noEmit
  ```

  Expected: pass and exit 0.

- [ ] Commit:

  ```bash
  git add AGENTS.md CLAUDE.md .claude/skills skills docs/skills.md \
    tests/agent/skill-contracts.test.ts
  git commit -m "feat: add knowledge trust boundary skills"
  ```

## Task 13: Expose stable package, Make, and README workflows

**Files:**

- Modify: `package.json`
- Modify: `Makefile`
- Modify: `README.md`

- [ ] Add these package scripts while retaining the original `dev`, `start`, `lint`, and `db:generate` behavior:

  ```json
  {
    "build:app": "WRANGLER_LOG_PATH=.wrangler/wrangler.log vinext build",
    "knowledge:check": "node --import tsx scripts/knowledge.ts check",
    "knowledge:resolve": "node --import tsx scripts/knowledge.ts resolve",
    "knowledge:build": "node --import tsx scripts/knowledge.ts build",
    "knowledge:preview": "node --import tsx scripts/knowledge.ts preview",
    "draft:preview": "node --import tsx scripts/draft-preview.ts",
    "literature:index": "node --import tsx scripts/literature.ts index",
    "literature:fetch": "node --import tsx scripts/literature.ts fetch",
    "literature:sync": "node --import tsx scripts/literature.ts sync",
    "migration:verify": "node --import tsx scripts/migrate-quantum-harness.ts verify",
    "build": "npm run knowledge:build && npm run build:app",
    "start:test": "WRANGLER_LOG_PATH=.wrangler/wrangler.log vinext start --host 127.0.0.1 --port 4173",
    "test:unit": "node --import tsx --test tests/knowledge/*.test.ts tests/migration/*.test.ts tests/literature/*.test.ts tests/drafts/*.test.ts tests/agent/*.test.ts",
    "test:rendered": "node --test tests/rendered-html.test.mjs tests/built-static-assets.test.mjs",
    "test:e2e": "playwright test",
    "test": "npm run lint && npm run test:unit && npm run build && npm run test:rendered && npm run test:e2e && npm run build"
  }
  ```

  The final production `npm run build` after Playwright is intentional: browser tests may temporarily build a nested knowledge fixture, but the deployable artifact must end with the real trusted tree.

- [ ] Expand `Makefile` without changing `.DEFAULT_GOAL := dev`. Add `.PHONY` targets and a concise `help` table for:

  ```text
  dev
  build
  test
  knowledge-check
  knowledge-resolve QUERY="..."
  knowledge-preview
  draft-preview FILE=drafts/path.md
  literature-index
  literature-fetch KEY=citekey
  literature-sync
  migration-verify
  ```

  `knowledge-resolve`, `draft-preview`, and `literature-fetch` must reject an empty variable with one-line usage and exit 2. Make targets delegate to package scripts; they do not duplicate TypeScript logic.

- [ ] Test the argument gates before invoking long-running preview commands:

  ```bash
  make help
  make knowledge-resolve; test $? -eq 2
  make draft-preview; test $? -eq 2
  make literature-fetch; test $? -eq 2
  make knowledge-check
  make knowledge-resolve QUERY="triangular TFIM"
  make migration-verify
  ```

  Expected: help lists every target; missing-argument cases exit 2; validation and migration verification pass; current trusted knowledge returns explicit `no-match`.

- [ ] Rewrite README sections to explain:

  - the preserved dashboard at `/`;
  - the Quarto site at `/knowledge/`;
  - the knowledge/drafts/literature trust boundary;
  - the three page categories and curated reading-map contract;
  - Node 22.23.1 and Quarto 1.9.38 prerequisites;
  - all stable Make commands;
  - that this phase has no autonomous backend, D1/R2 data model, or published draft/literature source;
  - the exact Sites project is reused and deployment may remain blocked by access.

- [ ] Run:

  ```bash
  npm run test:unit
  npm run knowledge:build
  npm run build:app
  git diff --check
  ```

  Expected: pass.

- [ ] Commit:

  ```bash
  git add package.json Makefile README.md
  git commit -m "feat: expose knowledge maintenance commands"
  ```

## Task 14: Replace obsolete dashboard tests and verify static asset packaging

**Files:**

- Modify: `tests/rendered-html.test.mjs`
- Create: `tests/built-static-assets.test.mjs`
- Modify conditionally: `worker/index.ts`

- [ ] Rewrite `tests/rendered-html.test.mjs` before changing application code. Import the real built Worker as the existing test does and assert `/` returns status 200, HTML content type, title `Research Loop — Automata`, `Research Loop`, `Turn open literature into verifiable research`, all four stage names, and the current candidate. Remove every starter-skeleton assertion.

- [ ] Add `tests/built-static-assets.test.mjs` to inspect the actual build output. Assert:

  - `dist/.openai/hosting.json` exists and contains exact project ID `appgprj_6a66e89526a88191a9e969c6f441086c` with `d1`/`r2` still null;
  - the bundled client/static asset tree contains `knowledge/index.html` and all three category index files;
  - no built path contains `drafts`, `literature/.raw`, `literature/.figures`, `rendered.md`, or a source `.qmd`.

- [ ] Run a real build and rendered tests:

  ```bash
  npm run build
  npm run test:rendered
  ```

  Expected: the dashboard assertions and package-shape assertions pass. If they fail because tests made a false assumption about the real output path, inspect `dist/` and correct the test to the actual vinext/Sites package; do not edit the dashboard.

- [ ] Start the built app and probe real HTTP asset behavior, not a fake `ASSETS.fetch`:

  ```bash
  npm run start:test
  ```

  In a second shell:

  ```bash
  curl -fsS http://127.0.0.1:4173/ | rg 'Research Loop'
  curl -fsS http://127.0.0.1:4173/knowledge/ | rg 'Research Loop Knowledge'
  curl -fsS http://127.0.0.1:4173/knowledge/categories/theory/ | rg 'Theory'
  ```

  Stop the server after the probes.

- [ ] Apply this explicit decision gate:

  - If all nested knowledge URLs return the expected HTML, do not modify `worker/index.ts`; add a regression assertion and proceed.
  - If a nested URL returns 404 because the asset layer does not map directory routes to `index.html`, first add a failing real-HTTP test, then add only a `/knowledge` GET/HEAD fallback. Redirect `/knowledge` to `/knowledge/`; try the original static asset path, then `<path>/index.html` for extensionless/directory paths; return the asset response when found; otherwise fall through to the existing vinext handler. Keep image optimization unchanged. Reject non-GET/HEAD methods and never render Quarto in the Worker.

- [ ] Rebuild and repeat all three HTTP probes. Expected: 200 and correct bodies.

- [ ] Prove the dashboard files were not altered:

  ```bash
  git diff 425843c -- app/page.tsx app/globals.css app/layout.tsx
  ```

  Expected: no diff.

- [ ] Commit the tests and only the conditionally required Worker change:

  ```bash
  git add tests/rendered-html.test.mjs tests/built-static-assets.test.mjs
  git add worker/index.ts 2>/dev/null || true
  git commit -m "test: protect dashboard and knowledge assets"
  ```

## Task 15: Add browser behavior and visual regressions

**Files:**

- Create: `playwright.config.ts`
- Create: `tests/e2e/dashboard.spec.ts`
- Create: `tests/e2e/knowledge.spec.ts`
- Create: `tests/e2e/dashboard.spec.ts-snapshots/dashboard-linux.png`
- Modify: `package.json` only if a fixture-build helper script is needed

- [ ] Configure Chromium only, base URL `http://127.0.0.1:4173`, trace on first retry, and a `webServer` that starts the already-built app with `npm run start:test`. Do not reuse an arbitrary existing server in CI.

- [ ] Add a deterministic fixture-build command for browser tests:

  ```text
  node --import tsx scripts/knowledge.ts build \
    --knowledge-dir tests/fixtures/knowledge/valid \
    --bibliography-path tests/fixtures/literature/ref.bib
  npm run build:app
  ```

  Run it in Playwright's pre-test script, not the production build. The fixture must never be copied into `knowledge/` or deployed.

- [ ] Write `dashboard.spec.ts` first. Assert initial Verify stage, click the current action, assert Solve is active and the new audit message appears, reload and assert persistence from localStorage key `research-loop-demo`, click Reset, and assert Verify/default activity is restored. Do not assert the clock value.

- [ ] Add a full-page visual baseline before interaction with animations disabled. Mask no stable dashboard content. Store only the Linux Chromium baseline.

- [ ] Write `knowledge.spec.ts`. Assert:

  - `/knowledge/` has title/site heading `Research Loop Knowledge` and search UI;
  - `/knowledge/ising/` renders fixture mathematics, citation, and SVG;
  - all three `/knowledge/categories/<category>/` routes return their category view;
  - a nested stylesheet/search asset request succeeds;
  - `/drafts/`, an imported draft path, `/literature/`, and `.raw`/`.figures` guesses return 404 and never reveal file content.

- [ ] Install only the required browser and create the baseline:

  ```bash
  npx playwright install chromium
  npm run build:e2e
  npx playwright test --update-snapshots
  npx playwright test
  ```

  Expected: all tests pass on the second, non-update run.

- [ ] Rebuild the real production tree immediately after browser tests and verify the fixture is gone:

  ```bash
  npm run build
  ! rg -l 'fixture2026' public/knowledge dist
  ```

  Expected: production build passes and the fixture marker is absent.

- [ ] Commit:

  ```bash
  git add playwright.config.ts tests/e2e package.json package-lock.json
  git commit -m "test: cover dashboard and knowledge in Chromium"
  ```

## Task 16: Run the complete local acceptance suite

**Files:** no planned source changes; fix failures in the owning earlier task, with a focused commit.

- [ ] Use `superpowers:verification-before-completion` and run from a clean dependency install:

  ```bash
  npm ci
  quarto --version
  node --version
  make help
  make migration-verify
  make literature-index
  make knowledge-check
  make knowledge-resolve QUERY="triangular TFIM"
  npm test
  npm run build
  ```

  Expected versions: Quarto `1.9.38`, Node `v22.23.1`. Expected resolver status on the intentionally empty trusted production tree: `no-match`. Every test/build command exits 0.

- [ ] Verify trust boundaries and migration integrity:

  ```bash
  node --import tsx scripts/migrate-quantum-harness.ts verify
  test "$(find drafts/imported-quantum-harness -type f -name '*.md' | wc -l)" -eq 280
  test "$(find literature -mindepth 2 -maxdepth 2 -name INDEX.md | wc -l)" -eq 13
  ! git ls-files | rg '(^|/)(public/knowledge|work|\.raw|\.figures|rendered\.md)(/|$)'
  ! find public/knowledge -type f | rg '\.qmd$|ref\.bib$|rendered\.md$'
  ! rg -l 'fixture2026' public/knowledge dist
  git -C /home/chance/quantum.harness diff --quiet -- .knowledge
  ```

- [ ] Verify existing functionality and unchanged source:

  ```bash
  git diff 425843c -- app/page.tsx app/globals.css app/layout.tsx
  npm run test:rendered
  npx playwright test tests/e2e/dashboard.spec.ts
  ```

  Expected: no dashboard source diff; regression tests pass.

- [ ] Verify repository hygiene:

  ```bash
  git diff --check
  npx --no-install tsc --noEmit
  npm run lint
  git status --short
  git log --oneline --decorate -20
  ```

  Expected: no uncommitted source changes, no whitespace/type/lint failures, and the task-sized commits above are visible.

- [ ] Use `superpowers:requesting-code-review`. Resolve only concrete review findings, rerun the owning tests and the complete suite, and make focused fix commits.

## Task 17: Save and deploy through the existing Sites project when access exists

**Files:** no repository changes expected.

This task has an external-state gate. A local implementation is not incomplete merely because the already-known Sites access problem persists.

- [ ] Read `.openai/hosting.json` and copy the `project_id` exactly. Because this file exists, use the Sites connector for inspection, version saving, deployment, and production-status checks.

- [ ] Inspect project `appgprj_6a66e89526a88191a9e969c6f441086c` before any Sites mutation.

- [ ] If inspection still returns `Project not found`:

  - stop this task;
  - record `Sites deployment blocked: existing project is not visible to the connected identity`;
  - report the exact project ID and the successful local acceptance evidence;
  - do not call `create_site`, alter `.openai/hosting.json`, invent another ID, save a version, or claim deployment success.

- [ ] If the exact project is visible, ensure the branch is clean and the final production `npm run build` (not the e2e fixture build) is the current artifact. Push the exact source commit state required by Sites; build any archive from that same pushed state.

- [ ] Save a Sites version using that exact `commit_sha`. Deploy only the saved version. Do not change the existing access policy unless the user separately directs it.

- [ ] If deployment status is non-terminal, inspect until terminal. Then verify production routes:

  ```text
  /                                      dashboard title and Research Loop content
  /knowledge/                            Research Loop Knowledge
  /knowledge/categories/theory/          category view
  /knowledge/categories/experiment/      category view
  /knowledge/categories/codes/           category view
  /drafts/                               404
  /literature/                           404
  ```

- [ ] Report the deployed production URL, saved version ID, deployed commit SHA, route checks, and unchanged `d1: null` / `r2: null`. A `RUNNING` status is not completion.

## Final Handoff

The implementation handoff is complete only when it states, without relying on hidden commentary:

1. the feature branch and final commit SHA;
2. `280` imported draft cards and successful manifest verification;
3. `85` bibliography entries, `13` method indexes, and `65` arXiv-capable entries;
4. the trusted production knowledge validation/resolver result;
5. unit, Quarto integration, vinext build, rendered-worker, and Playwright results;
6. whether `worker/index.ts` needed the conditional static fallback;
7. proof that dashboard source/behavior remained unchanged;
8. generated artifact locations and stable Make commands;
9. Sites deployment URL/version/commit if access was restored, or the exact existing-project access blocker if not.

Do not describe the Discover → Verify → Solve → Publish dashboard as an implemented autonomous backend. It remains the preserved control-dashboard prototype in this phase.
