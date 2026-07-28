import { spawn } from "node:child_process";
import { watch } from "node:fs";
import { mkdir, readdir } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ignoredRoots = new Set([".generated", ".git", "node_modules", ".next", ".vinext", "dist", ".wrangler"]);

export async function ensureProblemWatchDir(rootDir) {
  const problemsPath = join(rootDir, "problems");
  await mkdir(problemsPath, { recursive: true });
  return problemsPath;
}

export async function watchProblemFiles({ rootDir, onChange, watchFn = watch }) {
  const problemsPath = await ensureProblemWatchDir(rootDir);
  const problemWatchers = new Map();
  let closed = false;

  function watchProblemDir(name) {
    const problemPath = join(problemsPath, name);
    const watcher = watchFn(problemPath, { recursive: false }, (_eventType, filename) => {
      const changedName = filename?.toString();
      if (!changedName || changedName === "problem.json" || changedName === "problem.md") onChange();
    });
    problemWatchers.set(name, watcher);
  }

  async function refreshProblemWatchers() {
    if (closed) return;

    const entries = await readdir(problemsPath, { withFileTypes: true });
    if (closed) return;

    const problemDirs = new Set(
      entries
        .filter((entry) => entry.isDirectory() && !ignoredRoots.has(entry.name))
        .map((entry) => entry.name),
    );

    for (const [name, watcher] of problemWatchers) {
      if (!problemDirs.has(name)) {
        watcher.close();
        problemWatchers.delete(name);
      }
    }

    for (const name of problemDirs) {
      if (!problemWatchers.has(name)) watchProblemDir(name);
    }
  }

  let refresh = Promise.resolve();
  const rootWatcher = watchFn(problemsPath, { recursive: false }, (_eventType, filename) => {
    const changedName = filename?.toString();
    if (changedName && ignoredRoots.has(changedName)) return;

    refresh = refresh
      .then(refreshProblemWatchers)
      .catch((error) => console.error(error.message));
    onChange();
  });

  refresh = refresh.then(refreshProblemWatchers);
  await refresh;

  return {
    close() {
      closed = true;
      rootWatcher.close();
      for (const watcher of problemWatchers.values()) watcher.close();
      problemWatchers.clear();
    },
  };
}

export function runIndexBuild(rootDir, spawnFn = spawn) {
  return new Promise((resolveBuild, rejectBuild) => {
    const builder = spawnFn(
      process.execPath,
      ["scripts/build-problem-index.mjs", "--reserve-id", "QMB-001"],
      { cwd: rootDir, stdio: "inherit" },
    );
    builder.on("error", rejectBuild);
    builder.on("exit", (code) => {
      if (code === 0) resolveBuild();
      else rejectBuild(new Error(`Problem index build exited with status ${code}.`));
    });
  });
}

export async function main({ rootDir = process.cwd() } = {}) {
  const resolvedRootDir = resolve(rootDir);

  await runIndexBuild(resolvedRootDir);

  let timer;
  const watcher = await watchProblemFiles({
    rootDir: resolvedRootDir,
    onChange() {
      clearTimeout(timer);
      timer = setTimeout(() => {
        runIndexBuild(resolvedRootDir).catch((error) => console.error(error.message));
      }, 150);
    },
  });

  const child = spawn("vinext", ["dev"], {
    cwd: resolvedRootDir,
    env: { ...process.env, WRANGLER_LOG_PATH: ".wrangler/wrangler.log" },
    stdio: "inherit",
  });

  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.on(signal, () => child.kill(signal));
  }

  child.on("exit", (code, signal) => {
    watcher.close();
    clearTimeout(timer);
    process.exitCode = code ?? (signal ? 1 : 0);
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  await main();
}
