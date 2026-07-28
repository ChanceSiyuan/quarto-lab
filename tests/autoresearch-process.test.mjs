import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";

import {
  MAX_STDERR_BYTES,
  ProcessExecutionError,
  ProcessOutputLimitError,
  runProcess,
} from "../lib/autoresearch/process.mjs";

function child() {
  const value = new EventEmitter();
  value.stdout = new EventEmitter();
  value.stderr = new EventEmitter();
  value.kill = () => {};
  return value;
}

test("runs argv with shell disabled, bounded separate streams, and complete stdout lines", async () => {
  const calls = [];
  const lines = [];
  const result = runProcess({
    command: "codex", args: ["exec"], cwd: "/stage", env: { PATH: "/safe", SECRET: "no" }, timeoutMs: 1_000,
    onStdoutLine: (line) => lines.push(line),
    spawnFn(command, args, options) {
      calls.push({ command, args, options });
      const value = child();
      queueMicrotask(() => {
        value.stdout.emit("data", Buffer.from('{"one"'));
        value.stdout.emit("data", Buffer.from(':1}\n{"two":2}\npartial'));
        value.stderr.emit("data", Buffer.from("warning\n"));
        value.emit("exit", 0, null);
        value.emit("close", 0, null);
      });
      return value;
    },
  });

  assert.deepEqual(await result, { stdout: '{"one":1}\n{"two":2}\npartial', stderr: "warning\n", code: 0, signal: null });
  assert.equal(calls[0].options.shell, false);
  assert.deepEqual(calls[0].options.stdio, ["ignore", "pipe", "pipe"]);
  assert.deepEqual(calls[0].options.env, { PATH: "/safe" });
  assert.deepEqual(lines, ['{"one":1}', '{"two":2}']);
});

test("rejects nonzero exits with code and signal", async () => {
  await assert.rejects(() => runProcess({
    command: "codex", args: [], cwd: "/stage", env: {}, timeoutMs: 1_000,
    spawnFn() { const value = child(); queueMicrotask(() => { value.emit("exit", 17, "SIGTERM"); value.emit("close", 17, "SIGTERM"); }); return value; },
  }), (error) => error instanceof ProcessExecutionError && error.code === 17 && error.signal === "SIGTERM");
});

test("rejects stderr output over its fixed byte limit", async () => {
  await assert.rejects(() => runProcess({
    command: "codex", args: [], cwd: "/stage", env: {}, timeoutMs: 1_000,
    spawnFn() {
      const value = child();
      queueMicrotask(() => value.stderr.emit("data", Buffer.alloc(MAX_STDERR_BYTES + 1)));
      return value;
    },
  }), (error) => error instanceof ProcessOutputLimitError && error.stream === "stderr");
});

test("captures trailing stream output emitted after exit and before close", async () => {
  const result = runProcess({
    command: "codex", args: [], cwd: "/stage", env: {}, timeoutMs: 1_000,
    spawnFn() {
      const value = child();
      queueMicrotask(() => {
        value.stdout.emit("data", Buffer.from("before\n"));
        value.emit("exit", 0, null);
        value.stderr.emit("data", Buffer.from("after-exit\n"));
        value.stdout.emit("data", Buffer.from("after-exit\n"));
        value.emit("close", 0, null);
      });
      return value;
    },
  });
  assert.deepEqual(await result, { stdout: "before\nafter-exit\n", stderr: "after-exit\n", code: 0, signal: null });
});

test("escalates output overflow to SIGKILL after its grace period", async () => {
  const signals = [];
  const timers = [];
  const originalSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (callback, delay) => {
    const timer = { callback, delay, unref() { return this; } };
    timers.push(timer);
    return timer;
  };
  try {
    const pending = runProcess({
      command: "codex", args: [], cwd: "/stage", env: {}, timeoutMs: 100, graceMs: 9,
      killFn(_child, signal) { signals.push(signal); },
      spawnFn() { const value = child(); queueMicrotask(() => value.stdout.emit("data", Buffer.alloc(4 * 1024 * 1024 + 1))); return value; },
    });
    await assert.rejects(pending, ProcessOutputLimitError);
    assert.deepEqual(signals, ["SIGTERM"]);
    assert.equal(timers[1].delay, 9);
    timers[1].callback();
    assert.deepEqual(signals, ["SIGTERM", "SIGKILL"]);
  } finally {
    globalThis.setTimeout = originalSetTimeout;
  }
});

test("terminates with SIGTERM then SIGKILL after the precise grace period", async () => {
  const signals = [];
  let now = 0;
  const timers = [];
  const originalSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (callback, delay) => {
    const timer = { callback, delay, unref() { return this; } };
    timers.push(timer);
    return timer;
  };
  try {
    const pending = runProcess({
      command: "codex", args: [], cwd: "/stage", env: {}, timeoutMs: 7, graceMs: 11,
      killFn(_child, signal) { signals.push({ signal, at: now }); },
      spawnFn() { return child(); },
    });
    assert.equal(timers[0].delay, 7);
    now = 7; timers[0].callback();
    assert.deepEqual(signals, [{ signal: "SIGTERM", at: 7 }]);
    assert.equal(timers[1].delay, 11);
    now = 18; timers[1].callback();
    assert.deepEqual(signals, [{ signal: "SIGTERM", at: 7 }, { signal: "SIGKILL", at: 18 }]);
    await assert.rejects(pending, (error) => error.name === "ProcessTimeoutError");
  } finally {
    globalThis.setTimeout = originalSetTimeout;
  }
});
