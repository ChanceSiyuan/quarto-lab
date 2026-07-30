import { defineConfig, devices } from "@playwright/test";
import { accessSync, constants, realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PORT = 4174;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const FAKE_CODEX_BIN = path.join(ROOT, ".research-loop", "tests", "fixtures", "fake-codex");
export const FAKE_CODEX_EXECUTABLE = realpathSync(path.join(FAKE_CODEX_BIN, "codex"));

function resolveExecutable(name: string, searchPath: string): string {
  for (const directory of searchPath.split(path.delimiter)) {
    if (!directory) continue;
    const candidate = path.join(directory, name);
    try {
      accessSync(candidate, constants.X_OK);
      return realpathSync(candidate);
    } catch { /* keep searching */ }
  }
  throw new Error(`${name} is not executable on the assessment test PATH`);
}

const ASSESSMENT_PATH = `${FAKE_CODEX_BIN}${path.delimiter}${process.env.PATH ?? ""}`;
export const ASSESSMENT_CODEX_BIN = resolveExecutable("codex", ASSESSMENT_PATH);
if (ASSESSMENT_CODEX_BIN !== FAKE_CODEX_EXECUTABLE) {
  throw new Error(
    `Unsafe assessment test configuration: codex resolved to ${ASSESSMENT_CODEX_BIN}, ` +
      `expected fixture ${FAKE_CODEX_EXECUTABLE}`,
  );
}

export default defineConfig({
  testDir: ".research-loop/tests/e2e",
  testMatch: /local-assessment\.spec\.ts/,
  globalTeardown: "./.research-loop/tests/e2e/local-assessment-teardown.ts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `node --import tsx .research-loop/tests/e2e/local-assessment-dev-server.ts --port ${PORT} --hostname 127.0.0.1`,
    cwd: ROOT,
    env: {
      ...process.env,
      PATH: ASSESSMENT_PATH,
    },
    url: BASE_URL,
    reuseExistingServer: false,
    timeout: 300_000,
    stdout: "pipe",
    stderr: "pipe",
    gracefulShutdown: { signal: "SIGTERM", timeout: 5_000 },
  },
});
