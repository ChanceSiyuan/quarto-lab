import assert from "node:assert/strict";
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

test("watches the problems/ tree without recursive repo-wide watchers", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-dev-watch-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "problems", "QMB-001"), { recursive: true });

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
    [join(root, "problems"), join(root, "problems", "QMB-001")],
  );
  assert.equal(watched[0].path, join(root, "problems"));
  assert.equal(watched.some((item) => item.path === root), false);
  assert.deepEqual(watched.map((item) => item.options), [{ recursive: false }, { recursive: false }]);
});

test("reconciles problem directories and rebuilds only for index inputs", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-dev-watch-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "problems", "QMB-001"), { recursive: true });

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
  const firstProblemWatch = watches.find((item) => item.path === join(root, "problems", "QMB-001"));

  await mkdir(join(root, "problems", "QMB-002"));
  rootWatch.callback("rename", "QMB-002");
  await waitFor(() => watches.some((item) => item.path === join(root, "problems", "QMB-002")));

  await rm(join(root, "problems", "QMB-001"), { recursive: true });
  rootWatch.callback("rename", "QMB-001");
  await waitFor(() => firstProblemWatch.closed);

  await mkdir(join(root, "problems", ".generated"));
  rootWatch.callback("rename", ".generated");
  await delay(10);
  assert.equal(watches.some((item) => item.path === join(root, "problems", ".generated")), false);

  changes = 0;
  const secondProblemWatch = watches.find((item) => item.path === join(root, "problems", "QMB-002"));
  secondProblemWatch.callback("change", "notes.txt");
  secondProblemWatch.callback("change", "problem.json");
  secondProblemWatch.callback("change", "problem.md");

  assert.equal(changes, 2);
});
