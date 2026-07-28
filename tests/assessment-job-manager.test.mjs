import assert from "node:assert/strict";
import test from "node:test";

import { createAssessmentJobManager } from "../lib/assessments/job-manager.mjs";

function fakeRepository() {
  return {
    getProblem(id) {
      return id === "Prob-001"
        ? { id, title: "Fixture", summary: "Summary" }
        : null;
    },
    async readProblemMarkdown(id) {
      return `# ${id}\n\nProblem body.`;
    },
  };
}

function fakeStore() {
  const runs = [];
  return {
    runs,
    async createAcceptedRun({ problemId, parentRunId = null }) {
      const run = { schemaVersion: 1, runId: `20260728T01020${runs.length}Z-a1b2c3`, problemId, parentRunId, status: "queued", stagingDir: `/tmp/${runs.length}` };
      runs.push(run);
      return run;
    },
    async appendEvent() {},
    async writeTerminalArtifacts(run, artifacts) {
      run.status = artifacts.status;
      run.artifacts = artifacts;
      return run;
    },
    async listRuns(problemId) {
      return runs.filter((run) => run.problemId === problemId);
    },
    async findRun(runId) {
      return runs.find((run) => run.runId === runId) ?? null;
    },
    async readClarification(problemId, runId) {
      return runs.find((run) => run.problemId === problemId && run.runId === runId)?.artifacts?.clarification ?? null;
    },
  };
}

test("rejects unknown problem IDs before accepting a run", async () => {
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store: fakeStore(),
    codex: { preflight: async () => ({ ok: true }), run: async () => ({ ok: true }) },
  });
  const result = await manager.start("Prob-999");
  assert.equal(result.accepted, false);
  assert.equal(result.code, "UNKNOWN_PROBLEM");
});

test("returns the active run for duplicate starts", async () => {
  let release;
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async () => new Promise((resolve) => { release = () => resolve({ ok: false, code: "CODEX_EXIT", message: "done", eventsText: "", stderr: "" }); }),
    },
  });
  const first = await manager.start("Prob-001");
  const second = await manager.start("Prob-001");
  assert.equal(second.runId, first.runId);
  release();
});

test("runs jobs one at a time in FIFO order", async () => {
  const order = [];
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ problem }) => {
        order.push(problem.id);
        return { ok: false, code: "CODEX_EXIT", message: "forced failure", eventsText: "", stderr: "" };
      },
    },
  });
  await manager.start("Prob-001");
  await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.deepEqual(order, ["Prob-001"]);
  assert.equal(store.runs.length, 1);
});

test("selection consumes a clarification run and records the selected alternative", async () => {
  const alternative = { page: "knowledge/topic.qmd", topic: "topic", title: "Topic", matchKind: "title" };
  const store = fakeStore();
  const manager = createAssessmentJobManager({
    rootDir: "/repo",
    repository: fakeRepository(),
    store,
    codex: {
      preflight: async () => ({ ok: true }),
      run: async ({ selectedAlternative }) => selectedAlternative
        ? { ok: false, code: "CODEX_EXIT", message: "done", eventsText: "", stderr: "" }
        : { ok: true, envelope: { outcome: "needs_input", clarification: { alternatives: [alternative] } }, stderr: "" },
    },
  });

  const parent = await manager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal((await manager.select(parent.runId, { ...alternative, title: "Wrong" })).code, "INVALID_SELECTION");
  const child = await manager.select(parent.runId, alternative);
  const repeated = await manager.select(parent.runId, alternative);
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(repeated.runId, child.runId);
  assert.equal(store.runs.length, 2);
  assert.deepEqual(store.runs[1].artifacts.selection, alternative);
  assert.equal((await manager.getProblemState("Prob-001")).activeJob, null);
});

test("hydrates a persisted clarification after restart for deduplication and selection", async () => {
  const alternative = { page: "knowledge/topic.qmd", topic: "topic", title: "Topic", matchKind: "title" };
  const store = fakeStore();
  const codex = {
    preflight: async () => ({ ok: true }),
    run: async ({ selectedAlternative }) => selectedAlternative
      ? { ok: false, code: "CODEX_EXIT", message: "done", eventsText: "", stderr: "" }
      : { ok: true, envelope: { outcome: "needs_input", clarification: { alternatives: [alternative] } }, stderr: "" },
  };
  const firstManager = createAssessmentJobManager({ rootDir: "/repo", repository: fakeRepository(), store, codex });
  const parent = await firstManager.start("Prob-001");
  await new Promise((resolve) => setTimeout(resolve, 20));

  const restartedManager = createAssessmentJobManager({ rootDir: "/repo", repository: fakeRepository(), store, codex });
  const state = await restartedManager.getProblemState("Prob-001");
  const duplicate = await restartedManager.start("Prob-001");
  const child = await restartedManager.select(parent.runId, alternative);
  await new Promise((resolve) => setTimeout(resolve, 20));
  const retriedSelection = await createAssessmentJobManager({ rootDir: "/repo", repository: fakeRepository(), store, codex })
    .select(parent.runId, alternative);

  assert.equal(state.activeJob.runId, parent.runId);
  assert.deepEqual(state.activeJob.clarification.alternatives, [alternative]);
  assert.equal(duplicate.runId, parent.runId);
  assert.equal(child.accepted, true);
  assert.equal(retriedSelection.runId, child.runId);
  assert.equal(store.runs.length, 2);
  assert.equal(store.runs[1].parentRunId, parent.runId);
});
