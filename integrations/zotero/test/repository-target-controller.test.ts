import { describe, expect, it, vi } from "vitest";
import {
  RepositoryTargetController,
  type TargetSwitchBlocker,
  type TargetSwitchRuntime,
} from "../src/repository-target-controller";
import type {
  RepositoryTargetSnapshot,
  ResolvedLocalRepositoryTarget,
} from "../src/repository-target";

type StagedTarget = Readonly<{ snapshot: RepositoryTargetSnapshot }>;

type Deferred<T> = Readonly<{
  promise: Promise<T>;
  resolve(value: T): void;
}>;

type HarnessOptions = Readonly<{
  activeRoot?: string | null;
  activeEpoch?: number;
  blockerChecks?: readonly (readonly TargetSwitchBlocker[])[];
  blockerResolution?: "continue" | "cancel";
  deferredBlockerChecks?: readonly number[];
  deferredBlockerResolution?: boolean;
  deferredStageRoots?: readonly string[];
  deferredDisposeOldRoots?: readonly string[];
  persistErrors?: Readonly<Record<string, Error>>;
  publishErrors?: Readonly<Record<string, Error>>;
  disposeStagedErrors?: Readonly<Record<string, Error>>;
  disposeOldErrors?: Readonly<Record<string, Error>>;
  markDegradedError?: Error;
}>;

type Harness = Readonly<{
  controller: RepositoryTargetController<StagedTarget>;
  runtime: TargetSwitchRuntime<StagedTarget> & {
    checkBlockers: ReturnType<typeof vi.fn>;
    resolveBlockers: ReturnType<typeof vi.fn>;
    stage: ReturnType<typeof vi.fn>;
    persist: ReturnType<typeof vi.fn>;
    publish: ReturnType<typeof vi.fn>;
    disposeStaged: ReturnType<typeof vi.fn>;
    disposeOld: ReturnType<typeof vi.fn>;
    markDegraded: ReturnType<typeof vi.fn>;
  };
  events: string[];
  published: RepositoryTargetSnapshot[];
  activeAtPublish: (RepositoryTargetSnapshot | null)[];
  stageSignals: Map<string, AbortSignal>;
  releaseBlockerCheck(callNumber: number): void;
  releaseBlockerResolution(): void;
  resolveStage(root: string): void;
  resolveDisposeOld(root: string): void;
  setPersistHook(hook: (snapshot: RepositoryTargetSnapshot) => void): void;
}>;

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function resolved(canonicalRoot: string): ResolvedLocalRepositoryTarget {
  return {
    kind: "local",
    root: canonicalRoot,
    canonicalRoot,
    repositoryId: `repository:${canonicalRoot}`,
    targetId: `target:${canonicalRoot}`,
  };
}

function snapshot(canonicalRoot: string, targetEpoch: number): RepositoryTargetSnapshot {
  return { target: resolved(canonicalRoot), targetEpoch };
}

function harness(options: HarnessOptions = {}): Harness {
  const initial = options.activeRoot === null
    ? null
    : snapshot(options.activeRoot ?? "/A", options.activeEpoch ?? 1);
  const events: string[] = [];
  const published = initial ? [initial] : [];
  const activeAtPublish: (RepositoryTargetSnapshot | null)[] = [];
  const stageSignals = new Map<string, AbortSignal>();
  const blockerChecks = options.blockerChecks ?? [];
  const deferredChecks = new Map<number, Deferred<void>>();
  const deferredStages = new Map<string, Deferred<void>>();
  const deferredOldDisposals = new Map<string, Deferred<void>>();
  const blockerResolution = deferred<void>();
  let blockerCheckCount = 0;
  let persistHook: ((next: RepositoryTargetSnapshot) => void) | undefined;
  let controller!: RepositoryTargetController<StagedTarget>;

  for (const callNumber of options.deferredBlockerChecks ?? []) {
    deferredChecks.set(callNumber, deferred<void>());
  }
  for (const root of options.deferredStageRoots ?? []) {
    deferredStages.set(root, deferred<void>());
  }
  for (const root of options.deferredDisposeOldRoots ?? []) {
    deferredOldDisposals.set(root, deferred<void>());
  }

  const runtime: Harness["runtime"] = {
    checkBlockers: vi.fn(async () => {
      blockerCheckCount += 1;
      await deferredChecks.get(blockerCheckCount)?.promise;
      return blockerChecks[blockerCheckCount - 1] ?? [];
    }),
    resolveBlockers: vi.fn(async () => {
      if (options.deferredBlockerResolution) await blockerResolution.promise;
      return options.blockerResolution ?? "continue";
    }),
    stage: vi.fn(async (next: RepositoryTargetSnapshot, signal: AbortSignal) => {
      const root = next.target.canonicalRoot;
      events.push(`stage:${root}`);
      stageSignals.set(root, signal);
      await deferredStages.get(root)?.promise;
      return { snapshot: next };
    }),
    persist: vi.fn(async (next: RepositoryTargetSnapshot) => {
      const root = next.target.canonicalRoot;
      events.push(`persist:${root}`);
      persistHook?.(next);
      const error = options.persistErrors?.[root];
      if (error) throw error;
    }),
    publish: vi.fn((next: RepositoryTargetSnapshot) => {
      activeAtPublish.push(controller.activeSnapshot());
      events.push(`publish:${next.target.canonicalRoot}`);
      const error = options.publishErrors?.[next.target.canonicalRoot];
      if (error) throw error;
      published.push(next);
    }),
    disposeStaged: vi.fn(async (staged: StagedTarget) => {
      const root = staged.snapshot.target.canonicalRoot;
      events.push(`dispose-staged:${root}`);
      const error = options.disposeStagedErrors?.[root];
      if (error) throw error;
    }),
    disposeOld: vi.fn(async (previous: RepositoryTargetSnapshot | null) => {
      const root = previous?.target.canonicalRoot ?? "none";
      events.push(`dispose-old:${root}`);
      await deferredOldDisposals.get(root)?.promise;
      const error = options.disposeOldErrors?.[root];
      if (error) throw error;
    }),
    markDegraded: vi.fn(() => {
      if (options.markDegradedError) throw options.markDegradedError;
    }),
  };

  controller = new RepositoryTargetController(runtime, initial);
  return {
    controller,
    runtime,
    events,
    published,
    activeAtPublish,
    stageSignals,
    releaseBlockerCheck(callNumber) {
      deferredChecks.get(callNumber)?.resolve();
    },
    releaseBlockerResolution() {
      blockerResolution.resolve();
    },
    resolveStage(root) {
      deferredStages.get(root)?.resolve();
    },
    resolveDisposeOld(root) {
      deferredOldDisposals.get(root)?.resolve();
    },
    setPersistHook(hook) {
      persistHook = hook;
    },
  };
}

describe("RepositoryTargetController", () => {
  it("disposes only staged B when preference persistence fails, leaving A live", async () => {
    const h = harness({ persistErrors: { "/B": new Error("disk full") } });

    await expect(h.controller.switchTo(resolved("/B"))).rejects.toThrow("disk full");

    expect(h.published.map((item) => item.target.canonicalRoot)).toEqual(["/A"]);
    expect(h.runtime.disposeStaged).toHaveBeenCalledOnce();
    expect(h.runtime.disposeOld).not.toHaveBeenCalled();
    expect(h.events).toEqual(["stage:/B", "persist:/B", "dispose-staged:/B"]);
    expect(h.controller.activeSnapshot()?.target.canonicalRoot).toBe("/A");
  });

  it("delegates the first blockers once and publishes once after the user continues", async () => {
    const blocker: TargetSwitchBlocker = { kind: "running-turn" };
    const h = harness({ blockerChecks: [[blocker], []] });

    await h.controller.switchTo(resolved("/B"));

    expect(h.runtime.resolveBlockers).toHaveBeenCalledOnce();
    expect(h.runtime.resolveBlockers).toHaveBeenCalledWith([blocker]);
    expect(h.runtime.publish).toHaveBeenCalledOnce();
  });

  it("rechecks blockers after user resolution and rejects a newly appearing blocker before staging", async () => {
    const h = harness({
      blockerChecks: [
        [{ kind: "running-turn" }],
        [{ kind: "unsaved-qmd", path: "drafts/a.qmd" }],
      ],
    });

    await expect(h.controller.switchTo(resolved("/B")))
      .rejects.toThrow("Resolve new switch blockers");

    expect(h.runtime.stage).not.toHaveBeenCalled();
    expect(h.runtime.persist).not.toHaveBeenCalled();
  });

  it("persists and synchronously publishes B before disposing A", async () => {
    const h = harness();

    await h.controller.switchTo(resolved("/B"));

    expect(h.events).toEqual(["stage:/B", "persist:/B", "publish:/B", "dispose-old:/A"]);
    expect(h.controller.activeSnapshot()?.target.canonicalRoot).toBe("/B");
    expect(h.activeAtPublish[0]?.target.canonicalRoot).toBe("/B");
  });

  it("keeps B published and records degradation when post-commit disposal fails", async () => {
    const closeError = new Error("terminal close failed");
    const h = harness({ disposeOldErrors: { "/A": closeError } });

    await expect(h.controller.switchTo(resolved("/B")))
      .resolves.toMatchObject({ target: { canonicalRoot: "/B" } });

    expect(h.controller.activeSnapshot()?.target.canonicalRoot).toBe("/B");
    expect(h.runtime.markDegraded).toHaveBeenCalledWith(
      expect.objectContaining({ target: expect.objectContaining({ canonicalRoot: "/B" }) }),
      closeError,
    );
  });

  it("keeps B active and degraded when synchronous publication throws after persistence", async () => {
    const publishError = new Error("surface bind failed");
    const h = harness({ publishErrors: { "/B": publishError } });

    await expect(h.controller.switchTo(resolved("/B")))
      .resolves.toMatchObject({ target: { canonicalRoot: "/B" }, targetEpoch: 2 });

    expect(h.controller.activeSnapshot()?.target.canonicalRoot).toBe("/B");
    expect(h.runtime.publish).toHaveBeenCalledOnce();
    expect(h.runtime.markDegraded).toHaveBeenCalledWith(
      expect.objectContaining({ target: expect.objectContaining({ canonicalRoot: "/B" }) }),
      publishError,
    );
    expect(h.events).toEqual(["stage:/B", "persist:/B", "publish:/B", "dispose-old:/A"]);
    expect(h.runtime.disposeStaged).not.toHaveBeenCalled();
  });

  it("aborts stale staging even when the runtime ignores abort and allows only C to commit", async () => {
    const h = harness({ deferredStageRoots: ["/B"] });
    const switchingToB = h.controller.switchTo(resolved("/B"));
    await vi.waitFor(() => expect(h.runtime.stage).toHaveBeenCalledOnce());

    const switchingToC = h.controller.switchTo(resolved("/C"));

    await expect(switchingToB).rejects.toThrow("superseded");
    await expect(switchingToC).resolves.toMatchObject({ target: { canonicalRoot: "/C" } });
    expect(h.stageSignals.get("/B")?.aborted).toBe(true);
    h.resolveStage("/B");
    await vi.waitFor(() => {
      expect(h.events).toContain("dispose-staged:/B");
    });
    expect(h.published.map((item) => item.target.canonicalRoot)).toEqual(["/A", "/C"]);
  });

  it("rejects a late old-epoch callback after a successful switch", async () => {
    const h = harness();
    const old = h.controller.activeSnapshot()!;

    const next = await h.controller.switchTo(resolved("/B"));

    expect(next.targetEpoch).toBeGreaterThan(old.targetEpoch);
    expect(h.controller.isCurrent(old.target.targetId, old.targetEpoch)).toBe(false);
    expect(h.controller.isCurrent(next.target.targetId, next.targetEpoch)).toBe(true);
  });

  it("cancels after blocker resolution without staging or persisting", async () => {
    const h = harness({
      blockerChecks: [[{ kind: "pending-keep", path: "drafts/a.qmd" }]],
      blockerResolution: "cancel",
    });

    await expect(h.controller.switchTo(resolved("/B"))).rejects.toThrow("cancelled");

    expect(h.runtime.checkBlockers).toHaveBeenCalledOnce();
    expect(h.runtime.stage).not.toHaveBeenCalled();
    expect(h.runtime.persist).not.toHaveBeenCalled();
  });

  it("supersedes an attempt waiting for its first blocker check before the stale runtime returns", async () => {
    const h = harness({ deferredBlockerChecks: [1] });
    const switchingToB = h.controller.switchTo(resolved("/B"));
    await vi.waitFor(() => expect(h.runtime.checkBlockers).toHaveBeenCalledOnce());

    const switchingToC = h.controller.switchTo(resolved("/C"));

    await expect(switchingToB).rejects.toThrow("superseded");
    await expect(switchingToC).resolves.toMatchObject({ target: { canonicalRoot: "/C" } });
    h.releaseBlockerCheck(1);
    await vi.waitFor(() => expect(h.runtime.stage).toHaveBeenCalledOnce());
    expect(h.runtime.stage).toHaveBeenCalledWith(
      expect.objectContaining({ target: expect.objectContaining({ canonicalRoot: "/C" }) }),
      expect.any(AbortSignal),
    );
  });

  it("supersedes an attempt waiting for blocker resolution without staging it", async () => {
    const h = harness({
      blockerChecks: [[{ kind: "running-turn" }], []],
      deferredBlockerResolution: true,
    });
    const switchingToB = h.controller.switchTo(resolved("/B"));
    await vi.waitFor(() => expect(h.runtime.resolveBlockers).toHaveBeenCalledOnce());

    const switchingToC = h.controller.switchTo(resolved("/C"));

    await expect(switchingToB).rejects.toThrow("superseded");
    await expect(switchingToC).resolves.toMatchObject({ target: { canonicalRoot: "/C" } });
    h.releaseBlockerResolution();
    await vi.waitFor(() => expect(h.runtime.stage).toHaveBeenCalledOnce());
    expect(h.runtime.stage).toHaveBeenCalledWith(
      expect.objectContaining({ target: expect.objectContaining({ canonicalRoot: "/C" }) }),
      expect.any(AbortSignal),
    );
  });

  it("finishes an uninterruptible commit and keeps only the latest queued request", async () => {
    const h = harness({ deferredDisposeOldRoots: ["/A"] });
    const switchingToB = h.controller.switchTo(resolved("/B"));
    await vi.waitFor(() => expect(h.events).toContain("dispose-old:/A"));

    const switchingToC = h.controller.switchTo(resolved("/C"));
    const switchingToD = h.controller.switchTo(resolved("/D"));

    await expect(switchingToC).rejects.toThrow("superseded");
    expect(h.stageSignals.get("/B")?.aborted).toBe(false);
    expect(h.events).not.toContain("stage:/D");
    h.resolveDisposeOld("/A");
    await expect(switchingToB).resolves.toMatchObject({ target: { canonicalRoot: "/B" } });
    await expect(switchingToD).resolves.toMatchObject({ target: { canonicalRoot: "/D" }, targetEpoch: 3 });
    expect(h.published.map((item) => item.target.canonicalRoot)).toEqual(["/A", "/B", "/D"]);
  });

  it("queues a reentrant update from persist so preference and active publication cannot diverge", async () => {
    const h = harness();
    let switchingToC: Promise<RepositoryTargetSnapshot> | undefined;
    h.setPersistHook((next) => {
      if (next.target.canonicalRoot === "/B") {
        switchingToC = h.controller.switchTo(resolved("/C"));
      }
    });

    await h.controller.switchTo(resolved("/B"));
    await switchingToC;

    expect(h.events).toEqual([
      "stage:/B", "persist:/B", "publish:/B", "dispose-old:/A",
      "stage:/C", "persist:/C", "publish:/C", "dispose-old:/B",
    ]);
    expect(h.published.map((item) => item.target.canonicalRoot)).toEqual(["/A", "/B", "/C"]);
  });

  it("preserves the primary pre-publication failure when staged cleanup also fails", async () => {
    const h = harness({
      persistErrors: { "/B": new Error("disk full") },
      disposeStagedErrors: { "/B": new Error("cleanup failed") },
    });

    await expect(h.controller.switchTo(resolved("/B"))).rejects.toThrow("disk full");

    expect(h.runtime.disposeStaged).toHaveBeenCalledOnce();
    expect(h.controller.activeSnapshot()?.target.canonicalRoot).toBe("/A");
  });

  it("does not roll back B when degradation reporting itself throws", async () => {
    const h = harness({
      disposeOldErrors: { "/A": new Error("close failed") },
      markDegradedError: new Error("telemetry failed"),
    });

    await expect(h.controller.switchTo(resolved("/B")))
      .resolves.toMatchObject({ target: { canonicalRoot: "/B" } });

    expect(h.controller.activeSnapshot()?.target.canonicalRoot).toBe("/B");
    expect(h.runtime.publish).toHaveBeenCalledOnce();
  });

  it("returns the current snapshot without a new epoch or runtime work for the same target", async () => {
    const h = harness({ activeEpoch: 7 });
    const current = h.controller.activeSnapshot()!;

    await expect(h.controller.switchTo(resolved("/A"))).resolves.toBe(current);

    expect(h.controller.activeSnapshot()?.targetEpoch).toBe(7);
    expect(h.runtime.checkBlockers).not.toHaveBeenCalled();
    expect(h.runtime.stage).not.toHaveBeenCalled();
    expect(h.runtime.publish).not.toHaveBeenCalled();
  });

  it("does not ask the user to resolve blockers when the first check is empty", async () => {
    const h = harness();

    await h.controller.switchTo(resolved("/B"));

    expect(h.runtime.checkBlockers).toHaveBeenCalledOnce();
    expect(h.runtime.resolveBlockers).not.toHaveBeenCalled();
  });
});
