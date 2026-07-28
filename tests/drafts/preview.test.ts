/**
 * The draft preview is the one place in this repository that points a renderer
 * at *untrusted* content: `drafts/` holds whatever an agent or an import wrote,
 * and none of it has passed validation. So the property under test is not "does
 * it render" but "what can it reach": exactly one file, named by the user, that
 * really lives inside the drafts tree.
 *
 * Every rejection case here is a way of naming something else — a file that is
 * not there, a directory, a file that is not a note, an absolute path, a `..`
 * walk, and a symbolic link that leaves the tree. The last one is why
 * containment is checked on the *real* path: a link named `note.md` is an
 * ordinary relative path until the filesystem is asked where it goes.
 *
 * The spawn is pinned in the same way the site build's is: an argument array,
 * `shell: false` passed explicitly, `--no-execute` always, and a working
 * directory that is the real drafts root — never the repository, and never
 * anywhere near `public/knowledge`.
 */

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, readdir, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { fileURLToPath } from "node:url";

import { parse } from "yaml";

import { previewDraft, resolveDraftFile } from "../../lib/drafts/preview.js";
import type { ProcessRunner } from "../../lib/knowledge/site.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..");

/** The one note of the real imported corpus these tests name. */
const REAL_DRAFT = "drafts/imported-quantum-harness/conventions.md";

interface RunCall {
  command: string;
  args: readonly string[];
  options: { cwd: string; stdio: "inherit" | "pipe"; shell: false };
}

/** A `ProcessRunner` that records every call and spawns nothing. */
function recordingRunner(): { calls: RunCall[]; runner: ProcessRunner } {
  const calls: RunCall[] = [];
  return {
    calls,
    runner: {
      run(command, args, options) {
        calls.push({ command, args, options });
        return Promise.resolve();
      },
    },
  };
}

/**
 * A throwaway repository with a drafts tree that carries one of everything:
 * nested notes, a file that is not a note, a link inside the tree, a link out
 * of it, a linked directory, and a published site to keep clear of.
 */
async function makeRepo(t: TestContext): Promise<string> {
  const repo = await mkdtemp(path.join(await realpath(tmpdir()), "draft-preview-"));
  t.after(() => rm(repo, { recursive: true, force: true }));

  const drafts = path.join(repo, "drafts");
  await mkdir(path.join(drafts, "imported", "deep"), { recursive: true });
  await writeFile(
    path.join(drafts, "_quarto.yml"),
    await readFile(path.join(REPO_ROOT, "drafts", "_quarto.yml")),
  );
  await writeFile(path.join(drafts, "imported", "conventions.md"), "# Conventions\n");
  await writeFile(path.join(drafts, "imported", "deep", "note.qmd"), "# A deep note\n");
  await writeFile(path.join(drafts, "imported", "notes.txt"), "not a note\n");

  await mkdir(path.join(repo, "outside"), { recursive: true });
  await writeFile(path.join(repo, "outside", "secret.md"), "# Secret\n");

  await symlink(path.join("..", "outside", "secret.md"), path.join(drafts, "escape.md"));
  await symlink(path.join("..", "outside"), path.join(drafts, "mirror"));
  await symlink(
    path.join("imported", "conventions.md"),
    path.join(drafts, "shortcut.md"),
  );

  await mkdir(path.join(repo, "public", "knowledge"), { recursive: true });
  await writeFile(
    path.join(repo, "public", "knowledge", "index.html"),
    "<html>the published site</html>",
  );
  return repo;
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

// ---------------------------------------------------------------------------
// The committed project file: a preview, and nothing that looks like the site.
// ---------------------------------------------------------------------------

test("the drafts project includes only QMD notes, disables execution, and builds no site", async () => {
  const config: unknown = parse(
    await readFile(path.join(REPO_ROOT, "drafts", "_quarto.yml"), "utf8"),
    { uniqueKeys: true },
  );

  // Compared whole rather than key by key: an extra `website`, `sidebar`,
  // `filters`, or `resources` key would turn the local preview into a
  // publishable site. The render allowlist excludes legacy imported Markdown.
  assert.deepEqual(config, {
    project: { type: "default", "output-dir": ".preview", render: ["**/*.qmd"] },
    format: { html: { toc: true } },
    execute: { enabled: false },
  });
});

test("everything a preview writes into drafts is ignored by git", async () => {
  const ignored = (await readFile(path.join(REPO_ROOT, ".gitignore"), "utf8")).split("\n");

  // Verified against Quarto 1.9.38: one render of a draft note creates the
  // output directory, a `.quarto/` cache, and a `.gitignore` of its own. A
  // preview must leave the working tree exactly as it found it.
  for (const residue of ["/drafts/.preview/", "/drafts/.quarto/", "/drafts/.gitignore"]) {
    assert.ok(ignored.includes(residue), `${residue} must never be committed`);
  }
});

// ---------------------------------------------------------------------------
// What may be previewed.
// ---------------------------------------------------------------------------

test("a nested .md note inside drafts is previewable", async (t) => {
  const repo = await makeRepo(t);

  const resolved = await resolveDraftFile({
    repoRoot: repo,
    requestedFile: "drafts/imported/conventions.md",
  });

  assert.equal(resolved.draftsRoot, await realpath(path.join(repo, "drafts")));
  assert.equal(resolved.relativeFile, "imported/conventions.md");
  assert.equal(
    resolved.absoluteFile,
    path.join(repo, "drafts", "imported", "conventions.md"),
  );
});

test("a nested .qmd note inside drafts is previewable", async (t) => {
  const repo = await makeRepo(t);

  const resolved = await resolveDraftFile({
    repoRoot: repo,
    requestedFile: "drafts/imported/deep/note.qmd",
  });

  assert.equal(resolved.relativeFile, "imported/deep/note.qmd");
});

test("an absolute path inside drafts names the same note", async (t) => {
  const repo = await makeRepo(t);

  const resolved = await resolveDraftFile({
    repoRoot: repo,
    requestedFile: path.join(repo, "drafts", "imported", "conventions.md"),
  });

  assert.equal(resolved.relativeFile, "imported/conventions.md");
});

test("a symbolic link inside drafts previews the file it really points at", async (t) => {
  const repo = await makeRepo(t);

  const resolved = await resolveDraftFile({
    repoRoot: repo,
    requestedFile: "drafts/shortcut.md",
  });

  assert.equal(
    resolved.relativeFile,
    "imported/conventions.md",
    "the real path is what Quarto is given, so the file rendered is the file checked",
  );
});

test("the imported corpus in this repository is previewable", async () => {
  const resolved = await resolveDraftFile({
    repoRoot: REPO_ROOT,
    requestedFile: REAL_DRAFT,
  });

  assert.equal(resolved.draftsRoot, path.join(REPO_ROOT, "drafts"));
  assert.equal(resolved.relativeFile, "imported-quantum-harness/conventions.md");
});

// ---------------------------------------------------------------------------
// What may not.
// ---------------------------------------------------------------------------

const REJECTED: readonly { name: string; requested: (repo: string) => string; expected: RegExp }[] = [
  {
    name: "a file that is not there",
    requested: () => "drafts/imported/missing.md",
    expected: /no file/,
  },
  {
    name: "a directory",
    requested: () => "drafts/imported",
    expected: /directory/,
  },
  {
    name: "the drafts root itself",
    requested: () => "drafts",
    expected: /directory|outside/,
  },
  {
    name: "a file that is not a note",
    requested: () => "drafts/imported/notes.txt",
    expected: /\.qmd/,
  },
  {
    name: "an absolute path outside the repository",
    requested: () => "/etc/passwd",
    expected: /outside/,
  },
  {
    name: "an absolute path inside the repository but outside drafts",
    requested: (repo) => path.join(repo, "outside", "secret.md"),
    expected: /outside/,
  },
  {
    name: "a `..` walk out of drafts",
    requested: () => "drafts/../outside/secret.md",
    expected: /outside/,
  },
  {
    name: "a repository-relative path that never enters drafts",
    requested: () => "outside/secret.md",
    expected: /outside/,
  },
  {
    name: "a `..` walk out of the repository",
    requested: () => "../../../../etc/passwd",
    expected: /outside/,
  },
  {
    name: "a symbolic link that leaves drafts",
    requested: () => "drafts/escape.md",
    expected: /outside/,
  },
  {
    name: "a file reached through a symlinked directory",
    requested: () => "drafts/mirror/secret.md",
    expected: /outside/,
  },
];

for (const rejected of REJECTED) {
  test(`${rejected.name} is not previewable`, async (t) => {
    const repo = await makeRepo(t);
    const requestedFile = rejected.requested(repo);

    await assert.rejects(
      () => resolveDraftFile({ repoRoot: repo, requestedFile }),
      (error: unknown) => {
        assert.ok(error instanceof Error);
        assert.match(error.message, rejected.expected);
        assert.ok(
          error.message.includes(requestedFile),
          `the refusal must name what was asked for: ${error.message}`,
        );
        return true;
      },
    );
  });

  test(`${rejected.name} spawns nothing`, async (t) => {
    const repo = await makeRepo(t);
    const { calls, runner } = recordingRunner();

    await assert.rejects(() =>
      previewDraft({ repoRoot: repo, requestedFile: rejected.requested(repo), runner }),
    );

    assert.deepEqual(calls, [], "a refused preview never reaches the renderer");
  });
}

test("a note whose path could be read as an option is refused", async (t) => {
  // `drafts/` is written by imports and agents, so a directory name is
  // attacker-controlled. `quarto preview --output-dir=/x.md` is a different
  // command from `quarto preview <file>`, and an argument array is no defence
  // against an argument that is itself a flag.
  const repo = await makeRepo(t);
  const trap = path.join(repo, "drafts", "--output-dir=");
  await mkdir(trap, { recursive: true });
  await writeFile(path.join(trap, "note.md"), "# trap\n");
  const { calls, runner } = recordingRunner();

  await assert.rejects(
    () =>
      previewDraft({
        repoRoot: repo,
        requestedFile: "drafts/--output-dir=/note.md",
        runner,
      }),
    (error: unknown) => {
      assert.ok(error instanceof Error);
      assert.match(error.message, /option/);
      return true;
    },
  );
  assert.deepEqual(calls, []);
});

// ---------------------------------------------------------------------------
// How Quarto is invoked.
// ---------------------------------------------------------------------------

test("the preview spawns quarto on one file, with no browser and no execution", async (t) => {
  const repo = await makeRepo(t);
  const { calls, runner } = recordingRunner();

  await previewDraft({
    repoRoot: repo,
    requestedFile: "drafts/imported/deep/note.qmd",
    runner,
  });

  assert.equal(calls.length, 1);
  const [call] = calls;
  assert.equal(call.command, "quarto");
  assert.equal(Array.isArray(call.args), true, "arguments are an array, not a command line");
  assert.deepEqual(call.args, [
    "preview",
    "imported/deep/note.qmd",
    "--no-browser",
    "--no-execute",
  ]);
  assert.equal(
    call.options.cwd,
    await realpath(path.join(repo, "drafts")),
    "Quarto runs in the real drafts root, so `drafts/_quarto.yml` is the project it sees",
  );
  assert.equal(call.options.shell, false);
  assert.equal(
    Object.prototype.hasOwnProperty.call(call.options, "shell"),
    true,
    "`shell` is passed explicitly rather than left to a default",
  );
  assert.equal(call.options.stdio, "inherit");
});

test("a different Quarto binary is honoured, and nothing else is spawned", async (t) => {
  const repo = await makeRepo(t);
  const { calls, runner } = recordingRunner();

  await previewDraft({
    repoRoot: repo,
    requestedFile: "drafts/imported/conventions.md",
    quartoBin: "/opt/quarto/bin/quarto",
    runner,
  });

  assert.deepEqual(
    calls.map((call) => call.command),
    ["/opt/quarto/bin/quarto"],
  );
});

test("a preview never touches the published knowledge site", async (t) => {
  const repo = await makeRepo(t);
  const before = await readFile(path.join(repo, "public", "knowledge", "index.html"));
  const { calls, runner } = recordingRunner();

  await previewDraft({
    repoRoot: repo,
    requestedFile: "drafts/imported/conventions.md",
    runner,
  });

  assert.deepEqual(await fileTree(path.join(repo, "public", "knowledge")), ["index.html"]);
  assert.deepEqual(await readFile(path.join(repo, "public", "knowledge", "index.html")), before);
  assert.equal(
    calls.every((call) => !call.args.some((argument) => argument.includes("public"))),
    true,
    "no argument can name the published site",
  );
});

// ---------------------------------------------------------------------------
// The command line.
// ---------------------------------------------------------------------------

/** Runs `scripts/draft-preview.ts` and reports what the shell would see. */
async function runCli(args: readonly string[]): Promise<{ code: number | null; stderr: string }> {
  const child = spawn(
    process.execPath,
    ["--import", "tsx", "scripts/draft-preview.ts", ...args],
    { cwd: REPO_ROOT, stdio: ["ignore", "pipe", "pipe"] },
  );
  let stderr = "";
  child.stderr.on("data", (chunk: Buffer) => {
    stderr += chunk.toString("utf8");
  });
  const code = await new Promise<number | null>((resolve, reject) => {
    child.on("error", reject);
    child.on("close", (status) => resolve(status));
  });
  return { code, stderr };
}

test("the CLI exits 2 and says what it needs when --file is missing", async () => {
  const { code, stderr } = await runCli([]);

  assert.equal(code, 2);
  assert.match(stderr, /--file/);
  assert.match(stderr, /drafts\//, "the message says where a previewable file must live");
});

test("the CLI exits 2 when --file is given no value", async () => {
  const { code, stderr } = await runCli(["--file"]);

  assert.equal(code, 2);
  assert.match(stderr, /--file/);
});

test("the CLI exits 1 when the file may not be previewed", async () => {
  const { code, stderr } = await runCli(["--file", "knowledge/index.qmd"]);

  assert.equal(code, 1);
  assert.match(stderr, /outside/);
});
