import { existsSync, watch } from "node:fs";
import { spawn } from "node:child_process";
import { join, relative, resolve } from "node:path";

const rootDir = process.cwd();
const ignoredRoots = new Set([".generated", ".git", "node_modules", ".next", ".vinext", "dist", ".wrangler"]);

function runIndexBuild() {
  return new Promise((resolveBuild, rejectBuild) => {
    const builder = spawn(process.execPath, ["scripts/build-problem-index.mjs"], { stdio: "inherit" });
    builder.on("error", rejectBuild);
    builder.on("exit", (code) => {
      if (code === 0) resolveBuild();
      else rejectBuild(new Error(`Problem index build exited with status ${code}.`));
    });
  });
}

await runIndexBuild();

const watchPath = existsSync(join(rootDir, "problems")) ? join(rootDir, "problems") : rootDir;
let timer;
const watcher = watch(watchPath, { recursive: true }, (_eventType, filename) => {
  const changedPath = filename ? relative(rootDir, resolve(watchPath, filename)) : "";
  if (changedPath.split(/[\\/]/).some((part) => ignoredRoots.has(part))) return;

  clearTimeout(timer);
  timer = setTimeout(() => {
    runIndexBuild().catch((error) => console.error(error.message));
  }, 150);
});

const child = spawn("vinext", ["dev"], {
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
