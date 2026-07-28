import http from "node:http";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import { PROBLEM_ID_PATTERN } from "../problems/schema.mjs";
import { RUN_ID_PATTERN, assertContained, resolveRunDir } from "./paths.mjs";

const MAX_BODY_BYTES = 16 * 1024;
const TOKEN_HEADER = "x-local-assessment-token";

async function readJsonBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      throw Object.assign(new Error("Request body too large."), { status: 413 });
    }
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
  } catch {
    throw Object.assign(new Error("Request body must be valid JSON."), { status: 400 });
  }
}

function send(response, status, body, headers = {}) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", ...headers });
  response.end(JSON.stringify(body));
}

function sendText(response, status, body, headers) {
  response.writeHead(status, headers);
  response.end(body);
}

function validProblemId(id) {
  return typeof id === "string" && PROBLEM_ID_PATTERN.test(id);
}

function validRunId(id) {
  return typeof id === "string" && RUN_ID_PATTERN.test(id);
}

function rawPathname(request) {
  return request.url.split("?", 1)[0];
}

function pathMatch(pathname, expression) {
  const match = pathname.match(expression);
  return match?.slice(1).map((segment) => {
    try {
      return decodeURIComponent(segment);
    } catch {
      return null;
    }
  }) ?? null;
}

async function readArtifact(rootDir, problemId, runId, filename) {
  const runDir = await resolveRunDir(rootDir, problemId, runId);
  const artifactPath = await assertContained(runDir, join(runDir, filename));
  try {
    return await readFile(artifactPath, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") throw Object.assign(new Error("Assessment artifact was not found."), { status: 404 });
    throw error;
  }
}

export function createAssessmentService({ rootDir = process.cwd(), token, manager } = {}) {
  if (typeof token !== "string" || token.length === 0) {
    throw new Error("A non-empty local assessment token is required.");
  }
  const workspaceRoot = resolve(rootDir);
  return http.createServer(async (request, response) => {
    try {
      if (request.headers[TOKEN_HEADER] !== token) {
        send(response, 401, { error: "UNAUTHORIZED" });
        return;
      }

      const pathname = rawPathname(request);
      if (request.method === "POST" && pathname === "/__local/assessments/jobs") {
        const body = await readJsonBody(request);
        if (!validProblemId(body.problemId)) return send(response, 400, { error: "INVALID_PROBLEM_ID" });
        const result = await manager.start(body.problemId);
        return send(response, result.accepted ? 202 : 400, result);
      }

      const problem = pathMatch(pathname, /^\/__local\/assessments\/problems\/([^/]+)$/);
      if (request.method === "GET" && problem) {
        if (!validProblemId(problem[0])) return send(response, 400, { error: "INVALID_PROBLEM_ID" });
        return send(response, 200, await manager.getProblemState(problem[0]));
      }
      if (request.method === "GET" && pathname.startsWith("/__local/assessments/problems/")) {
        return send(response, 400, { error: "INVALID_PROBLEM_ID" });
      }

      const job = pathMatch(pathname, /^\/__local\/assessments\/jobs\/([^/]+)$/);
      if (request.method === "GET" && job) {
        if (!validRunId(job[0])) return send(response, 400, { error: "INVALID_RUN_ID" });
        const value = manager.getJob(job[0]);
        return value ? send(response, 200, value) : send(response, 404, { error: "UNKNOWN_RUN" });
      }

      const selection = pathMatch(pathname, /^\/__local\/assessments\/jobs\/([^/]+)\/selection$/);
      if (request.method === "POST" && selection) {
        if (!validRunId(selection[0])) return send(response, 400, { error: "INVALID_RUN_ID" });
        const body = await readJsonBody(request);
        const result = await manager.select(selection[0], body.alternative);
        return send(response, result.accepted ? 202 : 400, result);
      }

      const report = pathMatch(pathname, /^\/__local\/assessments\/reports\/([^/]+)\/([^/]+)$/);
      if (request.method === "GET" && report) {
        if (!validProblemId(report[0])) return send(response, 400, { error: "INVALID_PROBLEM_ID" });
        if (!validRunId(report[1])) return send(response, 400, { error: "INVALID_RUN_ID" });
        return sendText(response, 200, await readArtifact(workspaceRoot, report[0], report[1], "report.html"), {
          "content-type": "text/html; charset=utf-8",
        });
      }

      const log = pathMatch(pathname, /^\/__local\/assessments\/logs\/([^/]+)\/([^/]+)$/);
      if (request.method === "GET" && log) {
        if (!validProblemId(log[0])) return send(response, 400, { error: "INVALID_PROBLEM_ID" });
        if (!validRunId(log[1])) return send(response, 400, { error: "INVALID_RUN_ID" });
        return sendText(response, 200, await readArtifact(workspaceRoot, log[0], log[1], "stderr.log"), {
          "content-type": "text/plain; charset=utf-8",
          "content-disposition": `attachment; filename=\"${log[0]}-${log[1]}.log\"`,
        });
      }

      send(response, 404, { error: "NOT_FOUND" });
    } catch (error) {
      send(response, error.status ?? 500, { error: "LOCAL_ASSESSMENT_ERROR", message: error.message });
    }
  });
}
