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
  checkBlockers(): Promise<readonly TargetSwitchBlocker[]>;
  resolveBlockers(blockers: readonly TargetSwitchBlocker[]): Promise<"continue" | "cancel">;
  stage(snapshot: RepositoryTargetSnapshot, signal: AbortSignal): Promise<Staged>;
  persist(snapshot: RepositoryTargetSnapshot): Promise<void>;
  publish(snapshot: RepositoryTargetSnapshot, staged: Staged): void;
  disposeStaged(staged: Staged): Promise<void>;
  disposeOld(previous: RepositoryTargetSnapshot | null): Promise<void>;
  markDegraded(snapshot: RepositoryTargetSnapshot, error: Error): void;
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

const SUPERSEDED_ERROR = "Repository target switch superseded by a newer request";
const CANCELLED_ERROR = "Repository target switch cancelled";
const NEW_BLOCKERS_ERROR = "Resolve new switch blockers before switching repositories";

export class RepositoryTargetController<Staged> {
  private active: RepositoryTargetSnapshot | null;
  private latestEpoch: number;
  private nextAttemptId = 0;
  private currentAttempt: ActiveAttempt | undefined;
  private queuedRequest: SwitchRequest | undefined;

  constructor(
    private readonly runtime: TargetSwitchRuntime<Staged>,
    initialSnapshot: RepositoryTargetSnapshot | null = null,
  ) {
    this.active = initialSnapshot;
    this.latestEpoch = initialSnapshot?.targetEpoch ?? 0;
  }

  switchTo(target: ResolvedLocalRepositoryTarget): Promise<RepositoryTargetSnapshot> {
    const request = this.createRequest(target);
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
    let staged: Staged | undefined;
    let published = false;
    try {
      await this.prepareBlockers(attempt);
      this.assertPreparing(attempt);

      const previous = this.active;
      const next: RepositoryTargetSnapshot = {
        target: attempt.request.target,
        targetEpoch: this.latestEpoch + 1,
      };
      staged = await this.runtime.stage(next, attempt.abortController.signal);
      this.assertPreparing(attempt);

      attempt.phase = "committing";
      await this.runtime.persist(next);
      this.assertCurrent(attempt);

      this.active = next;
      this.latestEpoch = next.targetEpoch;
      published = true;
      try {
        this.runtime.publish(next, staged);
      }
      catch (error) {
        this.markDegradedSafely(next, error);
      }

      try {
        await this.runtime.disposeOld(previous);
      }
      catch (error) {
        this.markDegradedSafely(next, error);
      }
      attempt.request.resolve(next);
    }
    catch (error) {
      if (staged !== undefined && !published) {
        try {
          await this.runtime.disposeStaged(staged);
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
    const blockers = await this.runtime.checkBlockers();
    this.assertPreparing(attempt);
    if (blockers.length === 0) return;

    const resolution = await this.runtime.resolveBlockers(blockers);
    this.assertPreparing(attempt);
    if (resolution === "cancel") throw new Error(CANCELLED_ERROR);

    const remaining = await this.runtime.checkBlockers();
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

  private markDegradedSafely(snapshot: RepositoryTargetSnapshot, error: unknown): void {
    const degradation = error instanceof Error ? error : new Error(String(error));
    try {
      this.runtime.markDegraded(snapshot, degradation);
    }
    catch {
      // Reporting failure cannot roll back an already-published target.
    }
  }
}
