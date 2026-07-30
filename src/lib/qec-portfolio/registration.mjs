import { createHash, randomUUID } from "node:crypto";
import { lstat, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

import { validateStagedDraft } from "../problems/draft-contract.mjs";

const PROBLEM_MARKDOWN_DISCUSSION = "This user-approved draft is part of a twenty-problem QEC portfolio. It will be evaluated with frozen external citation and economic evidence, Research Value, Autoresearch Fit, and Combined Priority. Registration does not start an autoresearch campaign.";

function canonicalJson(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function digestFiles(files) {
  const hash = createHash("sha256");
  for (const [path, content] of [...files].sort(([left], [right]) => left.localeCompare(right))) {
    hash.update(path);
    hash.update("\0");
    hash.update(content, "utf8");
    hash.update("\0");
  }
  return hash.digest("hex");
}

function renderedFiles(record) {
  const audit = renderGenerationAudit(record);
  return new Map([
    ["problem.json", canonicalJson(renderProblemManifest(record))],
    ["problem.md", renderProblemMarkdown(record)],
    ["generation/initial-prompt.md", audit.get("initial-prompt.md")],
    ["generation/transcript.md", audit.get("transcript.md")],
    ["generation/decision.md", audit.get("decision.md")],
  ]);
}

async function existingProblemKind(rootDir, id) {
  try {
    return await lstat(join(rootDir, "problems", id));
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

async function relativeFiles(directory, prefix = "") {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relativePath = `${prefix}${entry.name}`;
    if (entry.isDirectory()) files.push(...await relativeFiles(join(directory, entry.name), `${relativePath}/`));
    else files.push(relativePath);
  }
  return files.sort();
}

export function renderProblemManifest(record) {
  return {
    schemaVersion: 1,
    id: record.id,
    title: record.title,
    summary: record.summary,
    domain: "quantum-computing",
    quantumArea: "error-correction-and-fault-tolerance",
    status: "draft",
    gate: { type: record.gateType, readiness: "specified" },
    provenance: { sourceCount: 3 },
    lastActivity: { summary: "Draft registered from QEC portfolio brainstorming.", at: record.updatedAt },
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
  };
}

export function renderProblemMarkdown(record) {
  return [
    "# Candidate Question",
    "",
    record.candidateQuestion,
    "",
    "# Motivation and Context",
    "",
    record.summary,
    "",
    "# Discussion Summary",
    "",
    PROBLEM_MARKDOWN_DISCUSSION,
    "",
    "# Evidence Mentioned",
    "",
    `- Technical anchor: ${record.technicalAnchor.title} — ${record.technicalAnchor.sourceUrl} (${record.technicalAnchor.persistentId}).`,
    "- Market proxy: McKinsey Quantum Technology Monitor 2026; the quantum-computing internal-market range is enabling context, not problem-specific revenue.",
    "- Investment signal: IBM's 2026 five-year quantum investment announcement; investment is not capturable value.",
    "",
    "# Open Qualification Questions",
    "",
    "- Which baseline implementation and sealed benchmark instances will be frozen before optimization?",
    "- Which primary metric, resource constraints, and no-regression checks define success for the declared gate?",
    "- Which evidence would establish novelty beyond the technical anchor rather than attention alone?",
    "",
  ].join("\n");
}

export function renderGenerationAudit(record) {
  return new Map([
    ["initial-prompt.md", `Approved QEC portfolio draft for ${record.id}: ${record.title}. Prepare the exact approved draft only; all visible content must remain English.\n`],
    ["transcript.md", `Scope B was selected: retain Prob-001 and register ${record.id} as one of the exact approved Prob-002 through Prob-021 QEC portfolio drafts.\n`],
    ["decision.md", "Approved after exact preview on 2026-07-29; publish as draft only.\n"],
  ]);
}

export async function stageQecProblem({ rootDir, runId, record }) {
  const stageDir = join(rootDir, ".generated", "problem-staging", runId, record.id);
  await mkdir(dirname(stageDir), { recursive: true });
  await mkdir(stageDir);
  await mkdir(join(stageDir, "generation"));

  const files = renderedFiles(record);
  await Promise.all([...files].map(async ([relativePath, content]) => {
    await writeFile(join(stageDir, relativePath), content, "utf8");
  }));
  await validateStagedDraft({ rootDir, stageDir, expectedId: record.id });
  return { stageDir, digest: digestFiles(files) };
}

export async function verifyPublishedProblem({ rootDir, record, digest }) {
  const files = renderedFiles(record);
  if (digestFiles(files) !== digest) return false;
  try {
    const expected = new Set(files.keys());
    const actual = await relativeFiles(join(rootDir, "problems", record.id));
    const unexpected = actual.filter((relativePath) => !expected.has(relativePath)
      && !relativePath.startsWith("valuation/")
      && !relativePath.startsWith("assessments/"));
    if (unexpected.length > 0) return false;
  } catch {
    return false;
  }
  for (const [relativePath, expected] of files) {
    try {
      if (await readFile(join(rootDir, "problems", record.id, relativePath), "utf8") !== expected) return false;
    } catch {
      return false;
    }
  }
  return true;
}

export async function registerQecPortfolio({ rootDir, records, publish, runId = `qec-portfolio-${randomUUID()}` }) {
  const summary = { published: [], skipped: [], failed: [] };
  for (const record of records) {
    const staged = await stageQecProblem({ rootDir, runId, record });
    const target = await existingProblemKind(rootDir, record.id);
    if (target !== null) {
      if (target.isDirectory() && !target.isSymbolicLink() && await verifyPublishedProblem({ rootDir, record, digest: staged.digest })) {
        summary.skipped.push(record.id);
        continue;
      }
      summary.failed.push({
        id: record.id,
        code: "PROBLEM_COLLISION",
        message: "Existing problem does not match the approved staged draft.",
      });
      break;
    }
    try {
      const result = await publish({ id: record.id, stageDir: staged.stageDir, digest: staged.digest });
      if (result?.status === "published" || result?.status === "published-index-stale") {
        summary.published.push(record.id);
        continue;
      }
      if (result?.status === "collision") {
        summary.failed.push({ id: record.id, code: "PROBLEM_COLLISION", message: "Problem ID is already occupied." });
      } else {
        summary.failed.push({ id: record.id, code: "PUBLISH_FAILED", message: result?.error ?? "Publisher did not confirm publication." });
      }
    } catch (error) {
      summary.failed.push({ id: record.id, code: "PUBLISH_FAILED", message: error.message });
    }
    break;
  }
  return summary;
}
