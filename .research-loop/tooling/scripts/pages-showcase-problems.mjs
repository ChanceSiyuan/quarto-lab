import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import {
  getPagesChallenge,
  PAGES_CHALLENGE_IDS,
} from "../../../src/lib/pages-showcase/challenge-catalog.mjs";

const OFFICIAL_DISPLAY_IDS = new Set([
  "Prob-124",
  "Prob-125",
  "Prob-126",
  "Prob-127",
  "Prob-128",
]);

export const PAGES_PUBLIC_PROBLEM_IDS = PAGES_CHALLENGE_IDS;

const DISPLAY_FILES = Object.freeze(["problem.json", "problem.md"]);
const CATALOG_TIMESTAMP = "2026-07-30T00:00:00.000Z";

function buildCatalogManifest(challenge) {
  return {
    createdAt: CATALOG_TIMESTAMP,
    gate: {
      readiness: "specified",
      type: `quantum-harness:qh-${challenge.issueNumber}`,
    },
    id: challenge.id,
    lastActivity: {
      at: CATALOG_TIMESTAMP,
      summary: "Scored for public research triage; autoresearch has not been started.",
    },
    provenance: { sourceCount: 1 },
    schemaVersion: 1,
    status: "archived",
    summary: challenge.summary,
    title: challenge.title,
    updatedAt: CATALOG_TIMESTAMP,
  };
}

function buildCatalogMarkdown(challenge) {
  return [
    `# ${challenge.title}`,
    "",
    "## Public source",
    challenge.sourceUrl,
    "",
    "## Assessment status",
    "Scored for research triage from the public issue text. Autoresearch has not been started.",
    "",
  ].join("\n");
}

export function createPagesShowcaseRoutes() {
  return [
    "/",
    "/problems/Prob-000",
    ...PAGES_PUBLIC_PROBLEM_IDS.map((id) => `/problems/${id}`),
    "/problems/Prob-000/autoresearch",
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
    if (!OFFICIAL_DISPLAY_IDS.has(id)) {
      const challenge = getPagesChallenge(id);
      await writeFile(join(targetDir, "problem.json"), `${JSON.stringify(buildCatalogManifest(challenge))}\n`);
      await writeFile(join(targetDir, "problem.md"), buildCatalogMarkdown(challenge));
      continue;
    }
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
