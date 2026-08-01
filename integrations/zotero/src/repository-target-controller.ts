import type {
  RepositoryTargetSnapshot,
  ResolvedLocalRepositoryTarget,
} from "./repository-target";

export type TargetSwitchBlocker =
  | { kind: "running-turn" }
  | { kind: "unsaved-qmd"; path: string }
  | { kind: "pending-keep"; path: string }
  | { kind: "unknown-operation" };

export interface TargetSwitchRuntime<Staged> {
  /**
   * Runtime hooks must not call or await controller.switchTo() from their
   * synchronous invocation stack. They also must not request a switch from an
   * async continuation after first awaiting; that continuation cannot be
   * attributed reliably. Follow-up switches must originate outside the hook
   * and its continuations. External requests made while an async hook is pending
   * are allowed and follow the controller's normal supersession/queue rules.
   */
  checkBlockers(): Promise<readonly TargetSwitchBlocker[]>;
  resolveBlockers(blockers: readonly TargetSwitchBlocker[]): Promise<"continue" | "cancel">;
  /**
   * Returns one fully owned staged value. A rejection (including abort) must be
   * exception-safe: the runtime cleans any resources allocated before rejecting.
   */
  stage(snapshot: RepositoryTargetSnapshot, signal: AbortSignal): Promise<Staged>;
  persist(snapshot: RepositoryTargetSnapshot): Promise<void>;
  /**
   * Synchronously and atomically transfers every staged owner to the snapshot.
   * It must return exactly undefined, must not be async, and must validate all
   * throwing conditions before external publication. Partial publication followed
   * by a throw violates the runtime contract and cannot be recovered generically.
   */
  publish(snapshot: RepositoryTargetSnapshot, staged: Staged): undefined;
  disposeStaged(staged: Staged): Promise<void>;
  disposeOld(previous: RepositoryTargetSnapshot | null): Promise<void>;
  /** Synchronously records degradation and returns exactly undefined. */
  markDegraded(snapshot: RepositoryTargetSnapshot, error: Error): undefined;
}

type SwitchPhase = "preparing" | "committing";

type SwitchRequest = {
  readonly attemptId: number;
  readonly target: ResolvedLocalRepositoryTarget;
  readonly promise: Promise<RepositoryTargetSnapshot>;
  readonly resolve: (snapshot: RepositoryTargetSnapshot) => void;
  readonly reject: (error: unknown) => void;
};

type ActiveAttempt = {
  readonly request: SwitchRequest;
  readonly abortController: AbortController;
  phase: SwitchPhase;
};

type StagedState<Staged> =
  | { readonly completed: false }
  | { readonly completed: true; readonly value: Staged };

const SUPERSEDED_ERROR = "Repository target switch superseded by a newer request";
const CANCELLED_ERROR = "Repository target switch cancelled";
const NEW_BLOCKERS_ERROR = "Resolve new switch blockers before switching repositories";
const PUBLISH_CONTRACT_ERROR = "Repository target runtime publish must return undefined synchronously";
const REENTRANT_SWITCH_ERROR = "Repository target switch cannot be requested synchronously from a runtime hook";
const INVALID_EPOCH_ERROR = "Repository target epoch must be a non-negative safe integer";
const EXHAUSTED_EPOCH_ERROR = "Repository target epoch exhausted";

export class RepositoryTargetController<Staged> {
  private active: RepositoryTargetSnapshot | null;
  private latestReservedEpoch: number;
  private nextAttemptId = 0;
  private currentAttempt: ActiveAttempt | undefined;
  private queuedRequest: SwitchRequest | undefined;
  private runtimeHookDepth = 0;

  constructor(
    private readonly runtime: TargetSwitchRuntime<Staged>,
    initialSnapshot: RepositoryTargetSnapshot | null = null,
  ) {
    const initialEpoch = initialSnapshot?.targetEpoch ?? 0;
    if (!Number.isSafeInteger(initialEpoch) || initialEpoch < 0) {
      throw new RangeError(INVALID_EPOCH_ERROR);
    }
    this.active = initialSnapshot;
    this.latestReservedEpoch = initialEpoch;
  }

  switchTo(target: ResolvedLocalRepositoryTarget): Promise<RepositoryTargetSnapshot> {
    const request = this.createRequest(target);
    if (this.runtimeHookDepth > 0) {
      request.reject(new Error(REENTRANT_SWITCH_ERROR));
      return request.promise;
    }
    const current = this.currentAttempt;
    if (!current) {
      this.start(request);
      return request.promise;
    }

    if (current.phase === "preparing") {
      current.abortController.abort();
      current.request.reject(new Error(SUPERSEDED_ERROR));
      this.currentAttempt = undefined;
      this.start(request);
      return request.promise;
    }

    this.queuedRequest?.reject(new Error(SUPERSEDED_ERROR));
    this.queuedRequest = request;
    return request.promise;
  }

  activeSnapshot(): RepositoryTargetSnapshot | null {
    return this.active;
  }

  isCurrent(targetId: string, targetEpoch: number): boolean {
    return this.active?.target.targetId === targetId
      && this.active.targetEpoch === targetEpoch;
  }

  private createRequest(target: ResolvedLocalRepositoryTarget): SwitchRequest {
    const attemptId = ++this.nextAttemptId;
    let resolve!: (snapshot: RepositoryTargetSnapshot) => void;
    let reject!: (error: unknown) => void;
    const promise = new Promise<RepositoryTargetSnapshot>((resolvePromise, rejectPromise) => {
      resolve = resolvePromise;
      reject = rejectPromise;
    });
    return { attemptId, target, promise, resolve, reject };
  }

  private start(request: SwitchRequest): void {
    if (this.active?.target.targetId === request.target.targetId) {
      request.resolve(this.active);
      return;
    }

    const attempt: ActiveAttempt = {
      request,
      abortController: new AbortController(),
      phase: "preparing",
    };
    this.currentAttempt = attempt;
    void this.run(attempt);
  }

  private async run(attempt: ActiveAttempt): Promise<void> {
    let stagedState: StagedState<Staged> = { completed: false };
    let published = false;
    try {
      await this.prepareBlockers(attempt);
      this.assertPreparing(attempt);

      const previous = this.active;
      const next: RepositoryTargetSnapshot = {
        target: attempt.request.target,
        targetEpoch: this.reserveEpoch(),
      };
      const staged = await this.invokeRuntimeHook(
        () => this.runtime.stage(next, attempt.abortController.signal),
      );
      stagedState = { completed: true, value: staged };
      this.assertPreparing(attempt);

      attempt.phase = "committing";
      await this.invokeRuntimeHook(() => this.runtime.persist(next));
      this.assertCurrent(attempt);

      try {
        const publicationResult: unknown = this.invokeRuntimeHook(
          () => this.runtime.publish(next, staged),
        );
        if (publicationResult !== undefined) {
          this.absorbUnexpectedThenable(publicationResult);
          throw new Error(PUBLISH_CONTRACT_ERROR);
        }
      }
      catch (error) {
        this.markDegradedSafely(next, error);
        throw error;
      }
      this.active = next;
      published = true;

      try {
        await this.invokeRuntimeHook(() => this.runtime.disposeOld(previous));
      }
      catch (error) {
        this.markDegradedSafely(next, error);
      }
      attempt.request.resolve(next);
    }
    catch (error) {
      if (stagedState.completed && !published) {
        const staged = stagedState.value;
        try {
          await this.invokeRuntimeHook(() => this.runtime.disposeStaged(staged));
        }
        catch {
          // The primary transaction failure determines the caller-visible result.
        }
      }
      attempt.request.reject(error);
    }
    finally {
      if (this.currentAttempt?.request.attemptId === attempt.request.attemptId) {
        this.currentAttempt = undefined;
        const queued = this.queuedRequest;
        this.queuedRequest = undefined;
        if (queued) this.start(queued);
      }
    }
  }

  private async prepareBlockers(attempt: ActiveAttempt): Promise<void> {
    const blockers = await this.invokeRuntimeHook(() => this.runtime.checkBlockers());
    this.assertPreparing(attempt);
    if (blockers.length === 0) return;

    const resolution = await this.invokeRuntimeHook(() => this.runtime.resolveBlockers(blockers));
    this.assertPreparing(attempt);
    if (resolution === "cancel") throw new Error(CANCELLED_ERROR);

    const remaining = await this.invokeRuntimeHook(() => this.runtime.checkBlockers());
    this.assertPreparing(attempt);
    if (remaining.length > 0) throw new Error(NEW_BLOCKERS_ERROR);
  }

  private assertPreparing(attempt: ActiveAttempt): void {
    this.assertCurrent(attempt);
    if (attempt.phase !== "preparing" || attempt.abortController.signal.aborted) {
      throw new Error(SUPERSEDED_ERROR);
    }
  }

  private assertCurrent(attempt: ActiveAttempt): void {
    if (this.currentAttempt?.request.attemptId !== attempt.request.attemptId) {
      throw new Error(SUPERSEDED_ERROR);
    }
  }

  private reserveEpoch(): number {
    if (this.latestReservedEpoch >= Number.MAX_SAFE_INTEGER) {
      throw new RangeError(EXHAUSTED_EPOCH_ERROR);
    }
    this.latestReservedEpoch += 1;
    return this.latestReservedEpoch;
  }

  private invokeRuntimeHook<T>(hook: () => T): T {
    this.runtimeHookDepth += 1;
    try {
      return hook();
    }
    finally {
      this.runtimeHookDepth -= 1;
    }
  }

  private markDegradedSafely(snapshot: RepositoryTargetSnapshot, error: unknown): void {
    const degradation = error instanceof Error ? error : new Error(String(error));
    try {
      const result: unknown = this.invokeRuntimeHook(
        () => this.runtime.markDegraded(snapshot, degradation),
      );
      if (result !== undefined) this.absorbUnexpectedThenable(result);
    }
    catch {
      // Reporting failure never replaces the transaction's primary outcome.
    }
  }

  private absorbUnexpectedThenable(value: unknown): void {
    if ((typeof value === "object" && value !== null) || typeof value === "function") {
      const then = (value as { then?: unknown }).then;
      if (typeof then === "function") void Promise.resolve(value).catch(() => {});
    }
  }
}
