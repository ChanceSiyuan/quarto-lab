import { resolve } from "node:path";

import { verifyQecPortfolio } from "../lib/qec-portfolio/batch-runner.mjs";

function readArg(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

const summary = await verifyQecPortfolio({ rootDir: resolve(readArg("--root") ?? process.cwd()) });
console.log(JSON.stringify(summary));
if (!summary.ok) process.exitCode = 1;
