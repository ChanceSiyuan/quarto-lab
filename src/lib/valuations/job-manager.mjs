import { createHash } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { join, resolve } from "node:path";

import { createRunId } from "../assessments/paths.mjs";
import { QUANTUM_AREAS, classifyQuantumScope } from "../problems/schema.mjs";
import { calculateCitationMetrics } from "./citations.mjs";
import { runValuationResearch } from "./codex-research-adapter.mjs";
import { redactPrivate } from "./privacy.mjs";
import { createValuationSnapshotStore, canonicalJson } from "./snapshot-store.mjs";
import { unknownValue } from "./types.mjs";

const ACTIVE_STATUSES = new Set(["queued", "researching", "needs_confirmation", "confirming"]);

function defaultResearcher() {
  return { run: runValuationResearch };
}

function candidateHash(candidate) {
  return createHash("sha256").update(canonicalJson(candidate)).digest("hex");
}

function publicCandidate(candidate, scope) {
  const visible = redactPrivate({ ...candidate, scope });
  return { ...visible, contentHash: candidateHash(visible) };
}

function publicJob(job) {
  if (!job) return null;
  const value = {
    runId: job.runId,
    problemId: job.problemId,
    status: job.status,
    queuePosition: job.queuePosition ?? 0,
    error: job.error ?? null,
    snapshotId: job.snapshotId ?? null,
  };
  if (job.scope) value.scope = structuredClone(job.scope);
  if (job.candidate) value.candidate = structuredClone(job.candidate);
  return value;
}

function sameIds(values, allowed) {
  return Array.isArray(values)
    && values.every((value) => typeof value === "string" && allowed.has(value))
    && new Set(values).size === values.length;
}

function validDecisions(decisions, assumptions) {
  if (!Array.isArray(decisions)) return false;
  const byId = new Map(assumptions.map((assumption) => [assumption.id, assumption]));
  if (decisions.some((item) => !item || typeof item.id !== "string" || !["accept", "reject"].includes(item.decision) || !byId.has(item.id))) return false;
  const ids = decisions.map((item) => item.id);
  if (new Set(ids).size !== ids.length) return false;
  return assumptions.filter((item) => item.confirmationRequired).every((item) => ids.includes(item.id));
}

function automaticDecisions(candidate, decisions) {
  const selected = new Map(decisions.map((item) => [item.id, item.decision]));
  return candidate.materialAssumptions.map((assumption) => ({
    id: assumption.id,
    decision: selected.get(assumption.id) ?? "accepted_automatically",
  }));
}

function providerFailure(error) {
  return {
    code: error?.code ?? "OPENALEX_PROVIDER_ERROR",
    message: error?.message ?? "OpenAlex request failed.",
  };
}

function paperSource(paper) {
  const id = String(paper?.id ?? "paper").trim() || "paper";
  const doi = typeof paper?.doi === "string" && paper.doi.length > 0 ? paper.doi : null;
  return {
    id: `citation-${id}`,
    url: doi ? `https://doi.org/${doi}` : `https://openalex.org/${id}`,
    locator: `OpenAlex work ${id}`,
    kind: "citation-index",
  };
}

function citationSources(papers) {
  const sources = new Map();
  for (const paper of Array.isArray(papers) ? papers : []) {
    const source = paperSource(paper);
    if (!sources.has(source.id)) sources.set(source.id, source);
  }
  return [...sources.values()];
}

function citationAtomicEvidence(id, value, { unit, papers, estimateKind = null, formulaId = null }) {
  if (value?.state === "unknown") return value;
  const sources = citationSources(papers);
  return {
    ...value,
    id,
    unit,
    visibility: "public",
    evidenceState: formulaId ? "inferred" : "reported",
    evidenceTier: "authoritative-secondary",
    sourceIds: sources.map((source) => source.id),
    sources,
    ...(estimateKind ? { estimateKind } : {}),
    ...(formulaId ? { derivation: { formulaId, inputIds: sources.map((source) => source.id) } } : {}),
  };
}

function valuationOutputs({ papers, providerError, now }) {
  if (providerError) {
    return {
      complete: false,
      scientificAttention: unknownValue("OpenAlex citation evidence is unavailable."),
      citation: { scientificAttention: unknownValue("OpenAlex citation evidence is unavailable.") },
      feasibility: unknownValue("No quantitative feasibility model was confirmed."),
      value: unknownValue("No quantitative value model was confirmed."),
    };
  }
  const citation = calculateCitationMetrics(papers, { currentYear: new Date(now()).getUTCFullYear() });
  const scientificAttention = citationAtomicEvidence("scientific-attention", citation.scientificAttention, {
    unit: citation.scientificAttention.unit,
    papers,
    estimateKind: "scientific-demand-model",
    formulaId: citation.formulaId,
  });
  const momentum = citationAtomicEvidence("citation-momentum", citation.momentum, { unit: "fraction", papers });
  return {
    complete: true,
    scientificAttention,
    citation: { ...citation, scientificDemand: scientificAttention, scientificAttention, momentum },
    feasibility: unknownValue("No quantitative feasibility model was confirmed."),
    value: unknownValue("No quantitative value model was confirmed."),
  };
}

export function createValuationJobManager({
  rootDir = process.cwd(),
  repository,
  researcher = defaultResearcher(),
  openAlex,
  store = createValuationSnapshotStore({ rootDir }),
  now = () => new Date(),
} = {}) {
  if (!repository?.getProblem || !repository?.readProblemMarkdown) throw new TypeError("repository must provide getProblem and readProblemMarkdown.");
  if (typeof researcher?.run !== "function") throw new TypeError("researcher must provide run.");
  if (typeof openAlex?.expand !== "function") throw new TypeError("openAlex must provide expand.");
  if (typeof store?.freeze !== "function" || typeof store?.readInputs !== "function") throw new TypeError("store must provide readInputs and freeze.");

  const workspaceRoot = resolve(rootDir);
  const jobs = new Map();
  const activeByProblem = new Map();
  const readySnapshots = new Map();
  const queue = [];
  let active = null;
  let closed = false;

  function queuePosition(job) {
    const index = queue.indexOf(job);
    return index < 0 ? 0 : index + 1;
  }

  async function stage(job) {
    const directory = join(workspaceRoot, ".generated", "valuation-runs", job.runId);
    await mkdir(directory, { recursive: true });
    job.stagingDir = directory;
  }

  function finish(job, status, error = null) {
    job.status = status;
    job.error = error;
    job.updatedAt = new Date(now()).toISOString();
    if (!ACTIVE_STATUSES.has(status) && activeByProblem.get(job.problemId) === job.runId) activeByProblem.delete(job.problemId);
  }

  async function research(job) {
    job.status = "researching";
    job.updatedAt = new Date(now()).toISOString();
    try {
      await stage(job);
      const [problemMarkdown, currentInputs] = await Promise.all([
        repository.readProblemMarkdown(job.problemId),
        store.readInputs(job.problemId),
      ]);
      job.currentInputs = structuredClone(currentInputs);
      const result = await researcher.run({
        rootDir: workspaceRoot,
        problem: job.problem,
        problemMarkdown,
        quantumScope: job.scope,
        currentInputs: redactPrivate(currentInputs),
        priorSnapshotSummary: readySnapshots.get(job.problemId) ? { snapshotId: readySnapshots.get(job.problemId) } : null,
        onChild: (child) => { job.child = child; },
      });
      job.child = null;
      if (closed) {
        finish(job, "research_failed", { code: "SHUTDOWN", message: "Valuation service shut down before research completed." });
        return;
      }
      if (!result?.ok) {
        finish(job, "research_failed", { code: result?.code ?? "RESEARCH_FAILED", message: result?.message ?? "Valuation research failed." });
        return;
      }
      job.candidate = publicCandidate(result.candidate, job.scope);
      job.researchDiagnostics = { stderr: result.stderr ?? "", eventsText: result.eventsText ?? "" };
      job.status = "needs_confirmation";
      job.updatedAt = new Date(now()).toISOString();
    } catch (error) {
      finish(job, "research_failed", { code: error?.code ?? "RESEARCH_FAILED", message: error.message });
    }
  }

  async function drain() {
    if (active || closed) return;
    active = queue.shift() ?? null;
    if (!active) return;
    active.queuePosition = 0;
    try {
      await research(active);
    } finally {
      active = null;
      void drain();
    }
  }

  async function start(problemId, { scopeOverride } = {}) {
    const existingId = activeByProblem.get(problemId);
    if (existingId) return { accepted: true, runId: existingId, status: jobs.get(existingId).status };
    if (closed) return { accepted: false, code: "SHUTDOWN" };
    const problem = repository.getProblem(problemId);
    if (!problem) return { accepted: false, code: "UNKNOWN_PROBLEM" };

    const scope = classifyQuantumScope(problem, { legacyArea: scopeOverride ?? null });
    if (scope.status === "unsupported") return { accepted: false, code: "UNSUPPORTED_DOMAIN" };
    if (scope.status === "needs_input") {
      if (scopeOverride !== undefined && !QUANTUM_AREAS.includes(scopeOverride)) return { accepted: false, code: "INVALID_SCOPE_OVERRIDE" };
      return { accepted: false, status: "needs_input", supportedAreas: [...QUANTUM_AREAS] };
    }
    if (scopeOverride !== undefined && scope.source !== "legacy") return { accepted: false, code: "INVALID_SCOPE_OVERRIDE" };

    const timestamp = new Date(now());
    const job = {
      runId: createRunId(timestamp),
      problemId,
      problem: structuredClone(problem),
      scope,
      status: "queued",
      createdAt: timestamp.toISOString(),
      updatedAt: timestamp.toISOString(),
      queuePosition: queue.length + (active ? 1 : 0) + 1,
      candidate: null,
      error: null,
    };
    jobs.set(job.runId, job);
    activeByProblem.set(problemId, job.runId);
    queue.push(job);
    void drain();
    return { accepted: true, runId: job.runId, status: "queued" };
  }

  async function confirm(runId, confirmation) {
    const job = jobs.get(runId);
    if (!job) return { accepted: false, code: "UNKNOWN_RUN" };
    if (job.status !== "needs_confirmation") return { accepted: false, code: "CONFIRMATION_NOT_READY" };
    const candidate = job.candidate;
    if (confirmation?.candidateHash !== candidate?.contentHash) return { accepted: false, code: "CANDIDATE_MISMATCH" };
    const anchors = new Set(candidate.anchorCandidates.map((item) => item.id));
    if (!sameIds(confirmation.acceptedAnchorIds, anchors) || confirmation.acceptedAnchorIds.length === 0
      || !validDecisions(confirmation.assumptionDecisions, candidate.materialAssumptions)) return { accepted: false, code: "INVALID_CONFIRMATION" };

    job.confirmation = {
      acceptedAnchorIds: [...confirmation.acceptedAnchorIds],
      assumptionDecisions: automaticDecisions(candidate, confirmation.assumptionDecisions),
    };
    job.status = "confirming";
    job.updatedAt = new Date(now()).toISOString();
    void (async () => {
      let papers = [];
      let error = null;
      try {
        const chosen = candidate.anchorCandidates.filter((item) => job.confirmation.acceptedAnchorIds.includes(item.id));
        papers = await openAlex.expand({
          anchors: chosen.map((item) => item.persistentId),
          topicIds: [],
          normalizedProblem: job.problem.summary,
        });
      } catch (caught) {
        error = providerFailure(caught);
      }
      if (closed) {
        finish(job, "research_failed", { code: "SHUTDOWN", message: "Valuation service shut down before confirmation completed." });
        return;
      }
      try {
        const outputs = valuationOutputs({ papers, providerError: error, now });
        const snapshot = await store.freeze(job.problemId, {
          manifest: {
            schemaVersion: 1,
            problemId: job.problemId,
            createdAt: new Date(now()).toISOString(),
            scope: job.scope,
            candidateHash: candidate.contentHash,
            confirmedCandidate: candidate,
            currentInputs: job.currentInputs,
            confirmation: job.confirmation,
            complete: outputs.complete,
            scientificAttention: outputs.scientificAttention,
            citation: outputs.citation,
            feasibility: outputs.feasibility,
            value: outputs.value,
            ...(error ? { providerError: error } : {}),
          },
          papers,
          marketEvidence: candidate.marketEvidence,
        });
        job.snapshotId = snapshot.manifest.snapshotId;
        readySnapshots.set(job.problemId, job.snapshotId);
        finish(job, "ready");
      } catch (caught) {
        finish(job, "research_failed", { code: caught?.code ?? "SNAPSHOT_FAILED", message: caught.message });
      }
    })();
    return { accepted: true, runId, status: "confirming" };
  }

  return Object.freeze({
    start,
    confirm,
    getJob(runId) { return publicJob(jobs.get(runId)); },
    async getProblemState(problemId) {
      const values = [...jobs.values()].filter((job) => job.problemId === problemId);
      const activeJob = values.find((job) => ACTIVE_STATUSES.has(job.status));
      let readySnapshotId = readySnapshots.get(problemId) ?? null;
      if (!readySnapshotId) {
        const snapshots = await store.list(problemId);
        readySnapshotId = snapshots.at(-1) ?? null;
        if (readySnapshotId) readySnapshots.set(problemId, readySnapshotId);
      }
      return {
        problemId,
        activeJob: activeJob ? publicJob({ ...activeJob, queuePosition: queuePosition(activeJob) }) : null,
        readySnapshotId,
        jobs: values.map(publicJob),
      };
    },
    async shutdown() {
      closed = true;
      for (const job of queue.splice(0)) finish(job, "research_failed", { code: "SHUTDOWN", message: "Valuation service shut down before research started." });
      active?.child?.kill?.("SIGTERM");
    },
  });
}
