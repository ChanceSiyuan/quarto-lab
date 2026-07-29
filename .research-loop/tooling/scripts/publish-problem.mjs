import { resolve } from "node:path";

import { publishStagedDraft } from "../../../src/lib/problems/draft-publisher.mjs";

function readArg(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

const rootDir = resolve(readArg("--root") ?? process.cwd());
const stageDir = readArg("--stage");
const expectedId = readArg("--id");

if (!stageDir || !expectedId) {
  console.log(JSON.stringify({
    status: "error",
    code: "INVALID_ARGUMENTS",
    errors: ["--stage and --id are required."],
  }));
  process.exitCode = 2;
} else {
  try {
    console.log(JSON.stringify(await publishStagedDraft({ rootDir, stageDir, expectedId })));
  } catch (error) {
    console.log(JSON.stringify({
      status: "error",
      code: error.code ?? "PUBLISH_FAILED",
      errors: error.errors ?? [error.message],
    }));
    process.exitCode = 1;
  }
}
