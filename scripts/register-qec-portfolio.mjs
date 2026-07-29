import { randomUUID } from "node:crypto";
import { execFile as execFileCallback } from "node:child_process";
import { relative, resolve } from "node:path";
import { promisify } from "node:util";

import { QEC_PORTFOLIO_PROBLEMS, validateQecPortfolioCatalog } from "../lib/qec-portfolio/catalog.mjs";
import { registerQecPortfolio } from "../lib/qec-portfolio/registration.mjs";

const execFile = promisify(execFileCallback);

function readArg(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

const rootDir = resolve(readArg("--root") ?? process.cwd());
const validation = validateQecPortfolioCatalog();

if (!validation.ok) {
  console.log(JSON.stringify({ status: "error", code: "INVALID_QEC_PORTFOLIO_CATALOG", errors: validation.errors }));
  process.exitCode = 1;
} else {
  async function publish({ id, stageDir }) {
    const relativeStage = relative(rootDir, stageDir);
    const { stdout } = await execFile("make", ["problem-publish", `STAGE=${relativeStage}`, `ID=${id}`], { cwd: rootDir });
    return JSON.parse(stdout);
  }

  const summary = await registerQecPortfolio({
    rootDir,
    records: QEC_PORTFOLIO_PROBLEMS,
    publish,
    runId: `qec-portfolio-${randomUUID()}`,
  });
  console.log(JSON.stringify(summary));
  if (summary.failed.length > 0) process.exitCode = 1;
}
