/**
 * The site build is the only thing in this repository that replaces a published
 * directory, and the only thing that spawns a program. These tests pin both
 * halves of that.
 *
 * The *publication* half is tested with a fake `ProcessRunner` and fake
 * `AtomicDirectoryOps`, because the properties that matter are properties of
 * failure: a render that fails must leave the site that is already published
 * exactly as it was, a rename that fails must put it back, and no run may ever
 * leave a workspace behind. A real Quarto cannot be asked to fail on cue, so
 * these cases inject the failure.
 *
 * The *rendering* half is tested with the real Quarto 1.9.38 on a fixture that
 * carries everything the knowledge site promises — inline and display
 * mathematics, a citation resolved against the bibliography, a nested topic, an
 * SVG asset, all three categories, and an executable code cell that must be
 * shown and never run. A mock cannot tell us that Quarto renders MathML, that
 * citeproc found the bibliography copy, or that `--no-execute` really stopped
 * the Python cell, and those are exactly the claims the site makes.
 *
 * The malicious variant is the point of the whole module: a page that asks for
 * `execute: true` must be refused by validation before a renderer ever sees it.
 */

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { cp, mkdir, mkdtemp, readFile, readdir, realpath, rename, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { fileURLToPath } from "node:url";

import {
  buildKnowledgeSite,
  previewKnowledgeSite,
  type AtomicDirectoryOps,
  type ProcessRunner,
} from "../../lib/knowledge/site.js";
import { KnowledgeValidationError, validateKnowledge } from "../../lib/knowledge/validate.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..");
const FIXTURES = path.join(REPO_ROOT, "tests", "fixtures", "knowledge");

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
  "execute:",
  "  enabled: false",
  "",
].join("\n");

/** Path components a published knowledge site may never contain. */
const FORBIDDEN_OUTPUT = ["ref.bib", "drafts", "literature", ".raw", ".figures"];

// ---------------------------------------------------------------------------
// The integration fixture: everything the knowledge site promises to render.
// ---------------------------------------------------------------------------

const INTEGRATION_TREE: Record<string, string> = {
  "index.qmd": [
    "---",
    "title: Research Loop Knowledge",
    "description: The root of the integration fixture.",
    "---",
    "",
    "This site contains only knowledge the user has reviewed and promoted.",
    "",
    "## Reading map",
    "",
    "- [Ising model](ising/index.qmd)",
    "",
  ].join("\n"),
  "ising/index.qmd": [
    "---",
    "title: Ising model",
    "description: Critical behaviour of the two-dimensional Ising model.",
    "aliases: [ising]",
    "---",
    "",
    "One proof, one proposal, and a verified implementation.",
    "",
    "## Reading map",
    "",
    "- [Proof of the critical temperature](proof.qmd)",
    "- [Finite-size proposal](proposal.qmd)",
    "- [Finite-size scaling](finite-size/index.qmd)",
    "",
  ].join("\n"),
  "ising/proof.qmd": [
    "---",
    "title: Proof of the critical temperature",
    "description: The duality argument that fixes the critical temperature.",
    "categories: [theory]",
    "---",
    "",
    "Self-duality fixes the critical coupling at $\\beta_c = \\tfrac{1}{2}\\ln(1+\\sqrt{2})$,",
    "following [@fixture2026].",
    "",
    "$$",
    "Z(\\beta) = \\sum_{\\{\\sigma\\}} e^{-\\beta H(\\sigma)}",
    "$$",
    "",
    "![Phase diagram of the two-dimensional Ising model](diagram.svg)",
    "",
  ].join("\n"),
  "ising/proposal.qmd": [
    "---",
    "title: Finite-size proposal",
    "description: A finite-size scaling study that would sharpen the exponent estimate.",
    "categories: [experiment]",
    "---",
    "",
    "Measuring the Binder cumulant on lattices up to $L = 128$ separates the two",
    "candidate exponents.",
    "",
  ].join("\n"),
  "ising/finite-size/index.qmd": [
    "---",
    "title: Finite-size scaling",
    "description: The subtopic that collects the finite-size machinery.",
    "---",
    "",
    "A subtopic, one level below the Ising topic.",
    "",
    "## Reading map",
    "",
    "- [Transfer-matrix code](code.qmd)",
    "",
    "## Related topics",
    "",
    "- [Ising model](../index.qmd)",
    "",
  ].join("\n"),
  "ising/finite-size/code.qmd": [
    "---",
    "title: Transfer-matrix code",
    "description: The transfer-matrix implementation checked against the exact solution.",
    "categories: [codes]",
    "---",
    "",
    "The implementation reproduces [the closed form](../proof.qmd).",
    "",
    "```{python}",
    "def free_energy(beta: float) -> float:",
    '    """Exact free energy per site."""',
    "    return -beta",
    "",
    "print(free_energy(0.5))",
    "```",
    "",
  ].join("\n"),
};

/** The page-level execution override validation must refuse. */
const MALICIOUS_PAGE = [
  "---",
  "title: Malicious page",
  "description: A page that tries to turn rendering into code execution.",
  "categories: [codes]",
  "execute: true",
  "---",
  "",
  "```{python}",
  "import subprocess",
  'subprocess.run(["touch", "/tmp/knowledge-build-was-executed"])',
  "```",
  "",
].join("\n");

async function makeTempDir(t: TestContext, prefix: string): Promise<string> {
  const directory = await mkdtemp(path.join(await realpath(tmpdir()), prefix));
  t.after(() => rm(directory, { recursive: true, force: true }));
  return directory;
}

/** A throwaway repository holding the integration fixture as `knowledge/`. */
async function makeRepo(
  t: TestContext,
  extraPages: Record<string, string> = {},
): Promise<string> {
  const repo = await makeTempDir(t, "knowledge-build-repo-");
  const knowledge = path.join(repo, "knowledge");
  await mkdir(knowledge, { recursive: true });
  await writeFile(path.join(knowledge, "_quarto.yml"), BASE_CONFIG);
  for (const [relative, source] of Object.entries({ ...INTEGRATION_TREE, ...extraPages })) {
    const file = path.join(knowledge, ...relative.split("/"));
    await mkdir(path.dirname(file), { recursive: true });
    await writeFile(file, source);
  }
  await cp(
    path.join(FIXTURES, "valid", "ising", "diagram.svg"),
    path.join(knowledge, "ising", "diagram.svg"),
  );
  await mkdir(path.join(repo, "literature"), { recursive: true });
  await cp(path.join(FIXTURES, "ref.bib"), path.join(repo, "literature", "ref.bib"));
  return repo;
}

/** Publishes a marker into `public/knowledge`, standing for an older site. */
async function publishSentinel(repo: string): Promise<string> {
  const sentinel = path.join(repo, "public", "knowledge", "sentinel.html");
  await mkdir(path.dirname(sentinel), { recursive: true });
  await writeFile(sentinel, "<html>the previously published site</html>");
  return sentinel;
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

async function exists(target: string): Promise<boolean> {
  try {
    await stat(target);
    return true;
  } catch {
    return false;
  }
}

/** The build workspaces still on disk; a finished run leaves none. */
async function workspaces(repo: string): Promise<string[]> {
  try {
    return (await readdir(path.join(repo, "work")))
      .filter((name) => name.startsWith("knowledge-build-"))
      .sort();
  } catch {
    return [];
  }
}

/** Whatever `public/` holds beside the published site; a finished run leaves nothing. */
async function publicEntries(repo: string): Promise<string[]> {
  try {
    return (await readdir(path.join(repo, "public"))).sort();
  } catch {
    return [];
  }
}

interface RunCall {
  command: string;
  args: readonly string[];
  options: { cwd: string; stdio: "inherit" | "pipe"; shell: false };
}

/** A `ProcessRunner` that records every call and then does what it is told. */
function recordingRunner(
  onRun: (call: RunCall) => Promise<void> | void = () => undefined,
): { calls: RunCall[]; runner: ProcessRunner } {
  const calls: RunCall[] = [];
  return {
    calls,
    runner: {
      async run(command, args, options) {
        const call = { command, args, options };
        calls.push(call);
        await onRun(call);
      },
    },
  };
}

/** Writes a plausible rendered site into the project Quarto was pointed at. */
async function fakeRender(call: RunCall): Promise<void> {
  const site = path.join(call.options.cwd, "_site");
  for (const relative of [
    "index.html",
    "ising/index.html",
    "ising/finite-size/index.html",
    "categories/theory/index.html",
    "categories/experiment/index.html",
    "categories/codes/index.html",
    "search.json",
  ]) {
    const file = path.join(site, ...relative.split("/"));
    await mkdir(path.dirname(file), { recursive: true });
    await writeFile(file, `<html>${relative}</html>`);
  }
}

/** Real directory operations, with one injected failure. */
function brittleOps(fails: (from: string, to: string) => boolean): AtomicDirectoryOps {
  return {
    async rename(from, to) {
      if (fails(from, to)) {
        throw new Error(`injected rename failure: ${from} -> ${to}`);
      }
      await rename(from, to);
    },
    async rm(target, options) {
      await rm(target, options);
    },
  };
}

// ---------------------------------------------------------------------------
// Publication: what happens when something goes wrong.
// ---------------------------------------------------------------------------

test("a failed render leaves the published site byte-for-byte unchanged", async (t) => {
  const repo = await makeRepo(t);
  const sentinel = await publishSentinel(repo);
  const before = await readFile(sentinel);
  const { calls, runner } = recordingRunner(() => {
    throw new Error("quarto exited with code 1");
  });

  await assert.rejects(
    () => buildKnowledgeSite({ repoRoot: repo, runner }),
    /quarto exited with code 1/,
  );

  assert.equal(calls.length, 1, "the render was attempted exactly once");
  assert.deepEqual(await readFile(sentinel), before);
  assert.deepEqual(await fileTree(path.join(repo, "public", "knowledge")), ["sentinel.html"]);
  assert.deepEqual(await workspaces(repo), [], "the workspace is removed even on failure");
  assert.deepEqual(await publicEntries(repo), ["knowledge"], "no backup is left behind");
});

test("a render that produces no index.html never replaces the published site", async (t) => {
  const repo = await makeRepo(t);
  const sentinel = await publishSentinel(repo);
  const { runner } = recordingRunner(async (call) => {
    await mkdir(path.join(call.options.cwd, "_site"), { recursive: true });
  });

  await assert.rejects(
    () => buildKnowledgeSite({ repoRoot: repo, runner }),
    /index\.html/,
  );

  assert.equal(await exists(sentinel), true);
  assert.deepEqual(await workspaces(repo), []);
});

test("a render that leaks a forbidden path never replaces the published site", async (t) => {
  for (const leaked of [
    "ref.bib",
    "ising/proof.qmd",
    "drafts/note.html",
    "literature/INDEX.html",
    "ising/.raw/paper.pdf",
    "ising/.figures/figure-1.png",
  ]) {
    const repo = await makeRepo(t);
    const sentinel = await publishSentinel(repo);
    const { runner } = recordingRunner(async (call) => {
      await fakeRender(call);
      const file = path.join(call.options.cwd, "_site", ...leaked.split("/"));
      await mkdir(path.dirname(file), { recursive: true });
      await writeFile(file, "leaked");
    });

    await assert.rejects(
      () => buildKnowledgeSite({ repoRoot: repo, runner }),
      (error: unknown) => {
        assert.ok(error instanceof Error);
        assert.match(error.message, new RegExp(leaked.split("/").join("\\/")));
        return true;
      },
      `${leaked} must stop publication`,
    );

    assert.equal(await exists(sentinel), true, `${leaked} must leave the old site in place`);
    assert.deepEqual(await workspaces(repo), []);
  }
});

test("a successful render replaces the published site atomically", async (t) => {
  const repo = await makeRepo(t);
  const sentinel = await publishSentinel(repo);
  const { runner } = recordingRunner(fakeRender);

  const result = await buildKnowledgeSite({ repoRoot: repo, runner });

  assert.equal(result.outputDir, path.join(repo, "public", "knowledge"));
  assert.equal(await exists(sentinel), false, "the previously published site is gone");
  const published = await fileTree(result.outputDir);
  assert.deepEqual(published, [
    "categories/codes/index.html",
    "categories/experiment/index.html",
    "categories/theory/index.html",
    "index.html",
    "ising/finite-size/index.html",
    "ising/index.html",
    "search.json",
  ]);
  assert.equal(result.renderedFiles, published.length);
  assert.deepEqual(await workspaces(repo), [], "the workspace is removed after success");
  assert.deepEqual(await publicEntries(repo), ["knowledge"], "the backup is removed after success");
});

test("a build with nothing published yet needs no backup", async (t) => {
  const repo = await makeRepo(t);
  const { runner } = recordingRunner(fakeRender);

  const result = await buildKnowledgeSite({ repoRoot: repo, runner });

  assert.equal(await exists(path.join(result.outputDir, "index.html")), true);
  assert.deepEqual(await publicEntries(repo), ["knowledge"]);
  assert.deepEqual(await workspaces(repo), []);
});

test("a failure while installing the new site restores the published one", async (t) => {
  const repo = await makeRepo(t);
  const sentinel = await publishSentinel(repo);
  const before = await readFile(sentinel);
  const { runner } = recordingRunner(fakeRender);

  await assert.rejects(
    () =>
      buildKnowledgeSite({
        repoRoot: repo,
        runner,
        // The rename that moves the verified `_site` into place, after the old
        // site has already been moved aside: the one window in which a crash
        // could leave the site missing entirely.
        directoryOps: brittleOps((from) => path.basename(from) === "_site"),
      }),
    /injected rename failure/,
  );

  assert.deepEqual(await readFile(sentinel), before, "the published site is back, unchanged");
  assert.deepEqual(await fileTree(path.join(repo, "public", "knowledge")), ["sentinel.html"]);
  assert.deepEqual(await publicEntries(repo), ["knowledge"], "the backup is gone");
  assert.deepEqual(await workspaces(repo), []);
});

test("a failure while moving the old site aside publishes nothing", async (t) => {
  const repo = await makeRepo(t);
  const sentinel = await publishSentinel(repo);
  const before = await readFile(sentinel);
  const { runner } = recordingRunner(fakeRender);

  await assert.rejects(
    () =>
      buildKnowledgeSite({
        repoRoot: repo,
        runner,
        directoryOps: brittleOps((from) => path.basename(from) === "knowledge"),
      }),
    /injected rename failure/,
  );

  assert.deepEqual(await readFile(sentinel), before);
  assert.deepEqual(await fileTree(path.join(repo, "public", "knowledge")), ["sentinel.html"]);
  assert.deepEqual(await publicEntries(repo), ["knowledge"]);
  assert.deepEqual(await workspaces(repo), []);
});

test("the renderer is spawned as an argument array, never through a shell", async (t) => {
  const repo = await makeRepo(t);
  const { calls, runner } = recordingRunner(fakeRender);

  await buildKnowledgeSite({ repoRoot: repo, runner });

  assert.equal(calls.length, 1);
  const [call] = calls;
  assert.equal(call.command, "quarto");
  assert.equal(Array.isArray(call.args), true, "arguments are an array, not a command line");
  assert.deepEqual(call.args, ["render", ".", "--no-execute"]);
  assert.equal(call.options.shell, false);
  assert.equal(
    Object.prototype.hasOwnProperty.call(call.options, "shell"),
    true,
    "`shell` is passed explicitly rather than left to a default",
  );
  assert.equal(call.options.stdio, "inherit");

  // The workspace is inside the repository, so the rename that publishes the
  // site cannot cross a filesystem boundary.
  const relative = path.relative(repo, call.options.cwd).split(path.sep).join("/");
  assert.match(relative, /^work\/knowledge-build-[^/]+\/project$/);
});

test("a different Quarto binary is honoured, and nothing else is spawned", async (t) => {
  const repo = await makeRepo(t);
  const { calls, runner } = recordingRunner(fakeRender);

  await buildKnowledgeSite({ repoRoot: repo, runner, quartoBin: "/opt/quarto/bin/quarto" });

  assert.deepEqual(
    calls.map((call) => call.command),
    ["/opt/quarto/bin/quarto"],
  );
});

test("preview renders in place, keeps the workspace alive, and never publishes", async (t) => {
  const repo = await makeRepo(t);
  const sentinel = await publishSentinel(repo);
  const seen: string[] = [];
  const { calls, runner } = recordingRunner(async (call) => {
    // Quarto is still running here: the project it is serving must exist.
    seen.push(...(await fileTree(call.options.cwd)));
  });

  await previewKnowledgeSite({ repoRoot: repo, runner });

  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].args, ["preview", ".", "--no-browser", "--no-execute"]);
  assert.equal(calls[0].options.shell, false);
  assert.ok(seen.includes("_quarto.yml"), "the project was materialized before the spawn");
  assert.ok(seen.includes("index.qmd"));
  assert.ok(seen.includes("categories/theory/index.qmd"));
  assert.deepEqual(await workspaces(repo), [], "the workspace is removed once Quarto exits");
  assert.deepEqual(
    await fileTree(path.join(repo, "public", "knowledge")),
    ["sentinel.html"],
    "preview never touches the published site",
  );
  assert.equal(await exists(sentinel), true);
});

test("a failed preview still removes its workspace", async (t) => {
  const repo = await makeRepo(t);
  const { runner } = recordingRunner(() => {
    throw new Error("quarto preview died");
  });

  await assert.rejects(() => previewKnowledgeSite({ repoRoot: repo, runner }), /died/);
  assert.deepEqual(await workspaces(repo), []);
});

test("interrupting a preview removes its workspace", { timeout: 120_000 }, async (t) => {
  // The one exit path a `finally` cannot cover: Ctrl-C reaches this process as
  // well as Quarto, and Node's default disposition is to die at once. The whole
  // CLI is driven here, against the production tree, with a stub on PATH
  // standing in for a Quarto that would otherwise serve until stopped.
  const binDir = await makeTempDir(t, "knowledge-fake-quarto-");
  const stub = path.join(binDir, "quarto");
  await writeFile(stub, '#!/bin/sh\necho "STUB-QUARTO $*"\nsleep 30\n', { mode: 0o755 });

  const child = spawn(process.execPath, ["--import", "tsx", "scripts/knowledge.ts", "preview"], {
    cwd: REPO_ROOT,
    env: { ...process.env, PATH: `${binDir}${path.delimiter}${process.env.PATH ?? ""}` },
    // Its own process group, so the interrupt reaches the stub too — exactly
    // what a terminal does to a foreground job.
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  t.after(() => {
    try {
      process.kill(-child.pid!, "SIGKILL");
    } catch {
      // Already gone, which is the expected case.
    }
  });

  const started = await new Promise<string>((resolve, reject) => {
    let seen = "";
    child.stdout.on("data", (chunk: Buffer) => {
      seen += chunk.toString("utf8");
      if (seen.includes("STUB-QUARTO")) {
        resolve(seen);
      }
    });
    child.on("exit", (code) => reject(new Error(`preview exited early with ${code}: ${seen}`)));
    child.on("error", reject);
  });
  assert.match(started, /STUB-QUARTO preview \. --no-browser --no-execute/);
  assert.equal(
    (await workspaces(REPO_ROOT)).length,
    1,
    "the workspace is alive while Quarto is serving",
  );

  process.kill(-child.pid!, "SIGINT");
  await new Promise<void>((resolve) => child.on("close", () => resolve()));

  assert.deepEqual(
    await workspaces(REPO_ROOT),
    [],
    "an interrupted preview leaves no workspace behind",
  );
});

// ---------------------------------------------------------------------------
// The gate: an invalid tree is refused before anything is spawned or replaced.
// ---------------------------------------------------------------------------

test("a page-level execution override is refused before any renderer runs", async (t) => {
  const repo = await makeRepo(t, {
    "ising/malicious.qmd": MALICIOUS_PAGE,
    "ising/index.qmd": INTEGRATION_TREE["ising/index.qmd"].replace(
      "- [Finite-size scaling](finite-size/index.qmd)\n",
      "- [Finite-size scaling](finite-size/index.qmd)\n- [Malicious page](malicious.qmd)\n",
    ),
  });
  const sentinel = await publishSentinel(repo);
  const { calls, runner } = recordingRunner(fakeRender);

  const report = await validateKnowledge({ repoRoot: repo });
  assert.equal(report.ok, false);
  assert.deepEqual(
    report.diagnostics.map((diagnostic) => diagnostic.code),
    ["FRONTMATTER_KEY_FORBIDDEN"],
    "the frontmatter allowlist is what refuses `execute`",
  );
  assert.match(report.diagnostics[0].location.file, /malicious\.qmd$/);

  await assert.rejects(
    () => buildKnowledgeSite({ repoRoot: repo, runner }),
    (error: unknown) => {
      assert.ok(error instanceof KnowledgeValidationError);
      assert.deepEqual(error.diagnostics, report.diagnostics, "the complete report is carried");
      assert.equal(error.report.ok, false);
      assert.match(error.message, /FRONTMATTER_KEY_FORBIDDEN/);
      return true;
    },
  );

  assert.deepEqual(calls, [], "nothing was spawned");
  assert.equal(await exists(sentinel), true, "nothing was published");
  assert.deepEqual(await workspaces(repo), [], "no workspace was left behind");
});

test("an invalid tree is refused with every diagnostic, not the first", async (t) => {
  const repo = await makeRepo(t, {
    "ising/orphan.qmd": [
      "---",
      "title: Orphan",
      "description: Listed by no reading map.",
      "categories: [theory]",
      "---",
      "",
      "<script>alert(1)</script>",
      "",
    ].join("\n"),
  });
  const { calls, runner } = recordingRunner(fakeRender);

  await assert.rejects(
    () => buildKnowledgeSite({ repoRoot: repo, runner }),
    (error: unknown) => {
      assert.ok(error instanceof KnowledgeValidationError);
      assert.deepEqual(
        error.diagnostics.map((diagnostic) => diagnostic.code).sort(),
        ["ORPHAN_CHILD", "SCRIPT_FORBIDDEN"],
      );
      return true;
    },
  );
  assert.deepEqual(calls, []);
});

// ---------------------------------------------------------------------------
// The real renderer: Quarto 1.9.38 on the integration fixture.
// ---------------------------------------------------------------------------

test("Quarto renders the whole fixture site, and executes nothing", { timeout: 300_000 }, async (t) => {
  const repo = await makeRepo(t);
  const sentinel = await publishSentinel(repo);

  const result = await buildKnowledgeSite({ repoRoot: repo });
  const site = result.outputDir;
  const read = async (relative: string): Promise<string> =>
    readFile(path.join(site, ...relative.split("/")), "utf8");

  assert.equal(site, path.join(repo, "public", "knowledge"));
  assert.equal(await exists(sentinel), false, "the placeholder site was replaced");

  // 1. Every page of the graph, at the path its URL implies, plus the three
  // generated category views and the copied asset.
  const published = await fileTree(site);
  for (const expected of [
    "index.html",
    "ising/index.html",
    "ising/proof.html",
    "ising/proposal.html",
    "ising/finite-size/index.html",
    "ising/finite-size/code.html",
    "categories/theory/index.html",
    "categories/experiment/index.html",
    "categories/codes/index.html",
    "ising/diagram.svg",
    "search.json",
  ]) {
    assert.ok(published.includes(expected), `${expected} is missing from ${published.join(", ")}`);
  }
  assert.equal(result.renderedFiles, published.length);

  // 2. Nothing that is not part of the site may be published.
  for (const file of published) {
    for (const segment of file.split("/")) {
      assert.equal(segment.endsWith(".qmd"), false, `${file} publishes a source page`);
      assert.equal(
        FORBIDDEN_OUTPUT.includes(segment),
        false,
        `${file} carries the forbidden component ${segment}`,
      );
    }
  }
  assert.equal(
    published.some((file) => file.includes("_files/")),
    false,
    "a code cell that ran would have left a figure directory",
  );

  // Quarto reads `aliases` as redirect paths, not as the synonyms the resolver
  // means by the same key. Constrained to a bare name by the projection, each
  // one lands inside the topic that declares it; the projection is what keeps a
  // `../../` alias from making the renderer write outside this tree at all.
  assert.ok(published.includes("ising/ising/index.html"), "the alias redirect is published");
  const redirect = await read("ising/ising/index.html");
  assert.match(redirect, /window\.location\.replace/, "an alias is a redirect, not a page copy");
  assert.match(
    redirect,
    /"":"\.\.\/index\.html"/,
    "and it points back inside the topic that declared it",
  );
  assert.equal(
    published.some((file) => file.startsWith("ising/ising/ising/")),
    false,
    "the redirect does not recurse",
  );

  // 3. The site identity and the generated navigation.
  const root = await read("index.html");
  assert.match(root, /<title>Research Loop Knowledge<\/title>/);
  assert.match(root, /href="\.\/ising\/index\.html"/, "the curated sidebar is rendered");
  assert.match(root, /href="\.\/categories\/theory\/index\.html"/);

  // 4. Mathematics: inline and display, as Quarto's math markup.
  const proof = await read("ising/proof.html");
  assert.match(proof, /class="math inline"/);
  assert.match(proof, /class="math display"/);
  assert.match(proof, /\\beta_c/);

  // 5. The citation, resolved against the bibliography copied into the project.
  assert.match(proof, /csl-bib-body/, "citeproc emitted a bibliography");
  assert.match(proof, /Fixture/, "the cited entry is rendered, not left as a raw key");
  assert.equal(proof.includes("[@fixture2026]"), false, "the citation key was resolved");

  // 6. The asset, referenced and copied.
  assert.match(proof, /<img src="diagram\.svg"/);
  assert.ok((await readFile(path.join(site, "ising", "diagram.svg"), "utf8")).includes("<svg"));

  // 7. The code cell is shown and was never run.
  const code = await read("ising/finite-size/code.html");
  assert.match(code, /free_energy/, "the source of the cell is published");
  assert.equal(code.includes("cell-output"), false, "no cell output was produced");
  assert.equal(code.includes("-0.5"), false, "the cell was never evaluated");

  // 8. The category views list what the graph filed under them.
  assert.match(await read("categories/theory/index.html"), /Proof of the critical temperature/);
  assert.match(await read("categories/experiment/index.html"), /Finite-size proposal/);
  assert.match(await read("categories/codes/index.html"), /Transfer-matrix code/);

  // 9. Nothing is left over.
  assert.deepEqual(await workspaces(repo), []);
  assert.deepEqual(await publicEntries(repo), ["knowledge"]);
});
