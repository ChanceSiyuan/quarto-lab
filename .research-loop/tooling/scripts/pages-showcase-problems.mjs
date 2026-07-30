import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, join } from "node:path";

export const PAGES_PUBLIC_PROBLEM_IDS = Object.freeze([
  "Prob-124",
  "Prob-125",
  "Prob-126",
  "Prob-127",
  "Prob-128",
]);

const DISPLAY_FILES = Object.freeze(["problem.json", "problem.md"]);

export function createPagesShowcaseRoutes() {
  return [
    "/",
    "/problems/Prob-000",
    ...PAGES_PUBLIC_PROBLEM_IDS.map((id) => `/problems/${id}`),
    "/problems/Prob-000/autoresearch",
    "/problems/Prob-127/autoresearch",
    "/problems/Prob-000/attempts/ATT-001",
    "/problems/Prob-000/attempts/ATT-002",
    "/problems/Prob-000/attempts/ATT-003",
    "/problems/Prob-000/attempts/ATT-004",
    "/problems/Prob-000/attempts/ATT-005",
  ];
}

export async function stagePagesShowcaseProblems({
  fixtureProblemsDir,
  officialProblemsDir,
  stageProblemsDir,
}) {
  await rm(stageProblemsDir, { recursive: true, force: true });
  await mkdir(dirname(stageProblemsDir), { recursive: true });
  await cp(
    join(fixtureProblemsDir, "Prob-000"),
    join(stageProblemsDir, "Prob-000"),
    { recursive: true },
  );

  for (const id of PAGES_PUBLIC_PROBLEM_IDS) {
    const targetDir = join(stageProblemsDir, id);
    await mkdir(targetDir, { recursive: true });
    for (const file of DISPLAY_FILES) {
      try {
        await cp(join(officialProblemsDir, id, file), join(targetDir, file));
      } catch (error) {
        if (error.code === "ENOENT") {
          throw new Error(`Pages showcase source missing: problems/${id}/${file}`);
        }
        throw error;
      }
    }
  }

  return {
    problemsDir: stageProblemsDir,
    problemIds: ["Prob-000", ...PAGES_PUBLIC_PROBLEM_IDS],
  };
}
