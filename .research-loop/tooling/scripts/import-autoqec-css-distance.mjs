import { resolve } from "node:path";

import { importAutoqecCssDistance, verifyImportedProblemTree } from "../../../src/lib/problems/autoqec-css-distance/importer.mjs";

function readArg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index === -1 ? fallback : process.argv[index + 1];
}

const mode = process.argv[2];
const rootDir = resolve(readArg("--root", process.cwd()));

if (mode === "import") {
  const sourceDir = readArg("--source");
  if (!sourceDir) {
    console.error("usage: npm run problem:import:autoqec-css-distance -- --source /path/to/AutoQEC");
    process.exit(2);
  }
  await importAutoqecCssDistance({ rootDir, sourceDir: resolve(sourceDir) });
  console.log("AutoQEC CSS-distance import complete: problems/Prob-001");
} else if (mode === "verify") {
  const id = readArg("--id", "Prob-001");
  const result = await verifyImportedProblemTree({ rootDir, id });
  if (!result.ok) {
    for (const error of result.errors) {
      console.error(`${error.relativePath}: ${error.field}: ${error.message}`);
    }
    process.exit(1);
  }
  console.log(`AutoQEC CSS-distance import verified: ${id}`);
} else {
  console.error("usage: npm run problem:import:autoqec-css-distance -- <import|verify>");
  process.exit(2);
}
