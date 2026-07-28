import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createAssessmentService } from "../lib/assessments/local-service.mjs";

const tokenHeaders = { "x-local-assessment-token": "secret" };
const runId = "20260728T010203Z-a1b2c3";

async function request(server, path, options = {}) {
  const listener = await new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server.address()));
  });
  try {
    return await fetch(`http://127.0.0.1:${listener.port}${path}`, options);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

test("rejects requests missing the capability token", async () => {
  const server = createAssessmentService({ token: "secret", manager: {} });
  const response = await request(server, "/__local/assessments/problems/Prob-001");
  assert.equal(response.status, 401);
});

test("starts jobs through the POST endpoint", async () => {
  const calls = [];
  const server = createAssessmentService({
    token: "secret",
    manager: {
      start: async (problemId) => {
        calls.push(problemId);
        return { accepted: true, runId, status: "queued" };
      },
    },
  });
  const response = await request(server, "/__local/assessments/jobs", {
    method: "POST",
    headers: { ...tokenHeaders, "content-type": "application/json" },
    body: JSON.stringify({ problemId: "Prob-001" }),
  });
  assert.equal(response.status, 202);
  assert.deepEqual(calls, ["Prob-001"]);
  assert.equal((await response.json()).runId, runId);
});

test("rejects traversal IDs before manager calls", async () => {
  const server = createAssessmentService({
    token: "secret",
    manager: { getProblemState: async () => assert.fail("manager should not be called") },
  });
  const response = await request(server, "/__local/assessments/problems/%2e%2e%2fx", { headers: tokenHeaders });
  assert.equal(response.status, 400);
});

test("posts a selection only for a validated parent run", async () => {
  const chosen = { page: "knowledge/topic.qmd", topic: "topic", title: "Topic", matchKind: "title" };
  const server = createAssessmentService({
    token: "secret",
    manager: { select: async (actualRunId, alternative) => {
      assert.equal(actualRunId, runId);
      assert.deepEqual(alternative, chosen);
      return { accepted: true, runId: "20260728T010204Z-d4e5f6", status: "queued" };
    } },
  });
  const response = await request(server, `/__local/assessments/jobs/${runId}/selection`, {
    method: "POST",
    headers: { ...tokenHeaders, "content-type": "application/json" },
    body: JSON.stringify({ alternative: chosen }),
  });
  assert.equal(response.status, 202);
  assert.equal((await response.json()).status, "queued");
});

test("serves report and diagnostic log from the requested run only", async () => {
  const rootDir = await mkdtemp(join(tmpdir(), "assessment-service-"));
  const runDir = join(rootDir, "problems", "Prob-001", "assessments", runId);
  await mkdir(runDir, { recursive: true });
  await writeFile(join(runDir, "report.html"), "<h1>Assessment</h1>");
  await writeFile(join(runDir, "stderr.log"), "diagnostic text\n");

  const report = await request(createAssessmentService({ rootDir, token: "secret", manager: {} }), `/__local/assessments/reports/Prob-001/${runId}`, { headers: tokenHeaders });
  assert.equal(report.status, 200);
  assert.match(report.headers.get("content-type"), /^text\/html; charset=utf-8$/);
  assert.equal(await report.text(), "<h1>Assessment</h1>");

  const log = await request(createAssessmentService({ rootDir, token: "secret", manager: {} }), `/__local/assessments/logs/Prob-001/${runId}`, { headers: tokenHeaders });
  assert.equal(log.status, 200);
  assert.match(log.headers.get("content-type"), /^text\/plain; charset=utf-8$/);
  assert.match(log.headers.get("content-disposition"), /^attachment/);
  assert.equal(await log.text(), "diagnostic text\n");
});
