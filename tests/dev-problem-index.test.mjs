import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdir, mkdtemp, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";

import { ensureProblemWatchDir, watchProblemFiles } from "../scripts/dev-problem-index.mjs";

async function waitFor(predicate) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (predicate()) return;
    await delay(5);
  }
  assert.fail("Timed out waiting for watcher reconciliation.");
}

test("ensures the dev watcher uses problems/ when the repo starts without one", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-dev-watch-"));
  t.after(() => rm(root, { recursive: true, force: true }));

  const watchPath = await ensureProblemWatchDir(root);

  assert.equal(watchPath, join(root, "problems"));
  assert.equal((await stat(watchPath)).isDirectory(), true);
});

test("dev index builds reserve the showcase problem ID", async () => {
  const { runIndexBuild } = await import("../scripts/dev-problem-index.mjs");
  assert.equal(typeof runIndexBuild, "function");

  const calls = [];
  function spawnFn(command, args, options) {
    calls.push({ command, args, options });
    const child = new EventEmitter();
    queueMicrotask(() => child.emit("exit", 0));
    return child;
  }

  await runIndexBuild("/tmp/research-loop-dev-root", spawnFn);

  assert.deepEqual(calls, [{
    command: process.execPath,
    args: ["scripts/build-problem-index.mjs", "--reserve-id", "Prob-000"],
    options: { cwd: "/tmp/research-loop-dev-root", stdio: "inherit" },
  }]);
});

test("dev wrapper starts the local assessment service and passes proxy env to vinext", async () => {
  const { main } = await import("../scripts/dev-problem-index.mjs");
  const spawnCalls = [];
  const child = new EventEmitter();
  child.kill = () => {};
  function spawnFn(command, args, options) {
    spawnCalls.push({ command, args, options });
    queueMicrotask(() => child.emit("exit", 0));
    return child;
  }
  const service = {
    url: "http://127.0.0.1:39001",
    token: "token-123",
    close: async () => {},
  };
  await main({
    rootDir: "/tmp/research-loop-dev-root",
    spawnFn,
    runIndexBuildFn: async () => {},
    watchProblemFilesFn: async () => ({ close() {} }),
    startAssessmentServiceFn: async () => service,
  });
  const vinext = spawnCalls.find((call) => call.command === "vinext");
  assert.equal(vinext.options.env.LOCAL_ASSESSMENT_SERVICE_URL, service.url);
  assert.equal(vinext.options.env.LOCAL_ASSESSMENT_PROXY_TOKEN, service.token);
});

test("dev wrapper closes the sidecar and watcher when vinext emits an error", async (t) => {
  const { main } = await import("../scripts/dev-problem-index.mjs");
  const originalExitCode = process.exitCode;
  t.after(() => { process.exitCode = originalExitCode; });
  const child = new EventEmitter();
  child.kill = () => {};
  child.on("error", () => {});
  let serviceClosed = 0;
  let watcherClosed = 0;

  await main({
    rootDir: "/tmp/research-loop-dev-root",
    spawnFn: () => child,
    runIndexBuildFn: async () => {},
    watchProblemFilesFn: async () => ({ close() { watcherClosed += 1; } }),
    startAssessmentServiceFn: async () => ({
      url: "http://127.0.0.1:39001",
      close: async () => { serviceClosed += 1; },
    }),
  });

  child.emit("error", new Error("vinext unavailable"));
  await delay(0);

  assert.equal(serviceClosed, 1);
  assert.equal(watcherClosed, 1);
});

test("dev wrapper closes the sidecar when watcher startup rejects", async () => {
  const { main } = await import("../scripts/dev-problem-index.mjs");
  let serviceClosed = 0;

  await assert.rejects(
    main({
      rootDir: "/tmp/research-loop-dev-root",
      runIndexBuildFn: async () => {},
      watchProblemFilesFn: async () => { throw new Error("watcher unavailable"); },
      startAssessmentServiceFn: async () => ({
        url: "http://127.0.0.1:39001",
        close: async () => { serviceClosed += 1; },
      }),
    }),
    /watcher unavailable/,
  );

  assert.equal(serviceClosed, 1);
});

test("watches the problems/ tree without recursive repo-wide watchers", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-dev-watch-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "problems", "Prob-001"), { recursive: true });

  const watched = [];
  const watcher = await watchProblemFiles({
    rootDir: root,
    onChange: () => {},
    watchFn(path, options) {
      watched.push({ path, options });
      return {
        close() {},
        on() {
          return this;
        },
      };
    },
  });
  t.after(() => watcher.close());

  assert.deepEqual(
    watched.map((item) => item.path).sort(),
    [join(root, "problems"), join(root, "problems", "Prob-001")],
  );
  assert.equal(watched[0].path, join(root, "problems"));
  assert.equal(watched.some((item) => item.path === root), false);
  assert.deepEqual(watched.map((item) => item.options), [{ recursive: false }, { recursive: false }]);
});

test("watches research manifests and attempt manifests", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-dev-watch-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "problems", "Prob-001", "attempts", "ATT-001"), { recursive: true });
  await mkdir(join(root, "problems", "Prob-001", "infrastructure", "cohorts"), { recursive: true });

  const watches = [];
  let changes = 0;
  const watcher = await watchProblemFiles({
    rootDir: root,
    onChange: () => { changes += 1; },
    watchFn(path, options, callback) {
      watches.push({ path, options, callback });
      return { close() {} };
    },
  });
  t.after(() => watcher.close());

  assert.ok(watches.some((item) => item.path === join(root, "problems", "Prob-001")));
  assert.ok(watches.some((item) => item.path === join(root, "problems", "Prob-001", "attempts")));
  assert.ok(watches.some((item) => item.path === join(root, "problems", "Prob-001", "attempts", "ATT-001")));
  assert.ok(watches.some((item) => item.path === join(root, "problems", "Prob-001", "infrastructure", "cohorts")));

  const attemptWatch = watches.find((item) => item.path === join(root, "problems", "Prob-001", "attempts", "ATT-001"));
  attemptWatch.callback("change", "candidate.py");
  attemptWatch.callback("change", "attempt.json");
  assert.equal(changes, 1);
});

test("registers newly created attempt directories and rebuilds for their manifests", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-dev-watch-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const attemptsPath = join(root, "problems", "Prob-001", "attempts");
  const newAttemptPath = join(attemptsPath, "ATT-002");
  await mkdir(attemptsPath, { recursive: true });

  const watches = [];
  let changes = 0;
  const watcher = await watchProblemFiles({
    rootDir: root,
    onChange: () => { changes += 1; },
    watchFn(path, options, callback) {
      const record = { callback, closed: false, options, path };
      watches.push(record);
      return { close() { record.closed = true; } };
    },
  });
  t.after(() => watcher.close());

  await mkdir(newAttemptPath);
  const attemptsWatch = watches.find((item) => item.path === attemptsPath && !item.closed);
  attemptsWatch.callback("rename", "ATT-002");
  await waitFor(() => watches.some((item) => item.path === newAttemptPath && !item.closed));

  changes = 0;
  const newAttemptWatch = watches.find((item) => item.path === newAttemptPath && !item.closed);
  newAttemptWatch.callback("change", "attempt.json");
  assert.equal(changes, 1);
});

test("reconciles problem directories and rebuilds only for index inputs", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-dev-watch-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "problems", "Prob-001"), { recursive: true });

  const watches = [];
  let changes = 0;
  const watcher = await watchProblemFiles({
    rootDir: root,
    onChange: () => {
      changes += 1;
    },
    watchFn(path, options, callback) {
      const record = { callback, closed: false, options, path };
      watches.push(record);
      return {
        close() {
          record.closed = true;
        },
      };
    },
  });
  t.after(() => watcher.close());

  const rootWatch = watches.find((item) => item.path === join(root, "problems"));
  const firstProblemWatch = watches.find((item) => item.path === join(root, "problems", "Prob-001"));

  await mkdir(join(root, "problems", "Prob-002"));
  rootWatch.callback("rename", "Prob-002");
  await waitFor(() => watches.some((item) => item.path === join(root, "problems", "Prob-002")));

  await rm(join(root, "problems", "Prob-001"), { recursive: true });
  rootWatch.callback("rename", "Prob-001");
  await waitFor(() => firstProblemWatch.closed);

  await mkdir(join(root, "problems", ".generated"));
  rootWatch.callback("rename", ".generated");
  await delay(10);
  assert.equal(watches.some((item) => item.path === join(root, "problems", ".generated")), false);

  changes = 0;
  const secondProblemWatch = watches.find((item) => item.path === join(root, "problems", "Prob-002"));
  secondProblemWatch.callback("change", "notes.txt");
  secondProblemWatch.callback("change", "problem.json");
  secondProblemWatch.callback("change", "problem.md");

  assert.equal(changes, 2);
});
