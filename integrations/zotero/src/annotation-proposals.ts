import type { AnchorRecord } from "./paper-trail";
import { randomID } from "./platform";
import type { JsonValue } from "./reader-context";
import type { DiffReview } from "./sidebar";

export const ANNOTATION_PROPOSAL_TOOL = "zotero_propose_annotations" as const;

const MAX_BATCH_SIZE = 100;
const MAX_COMMENT_CHARS = 20_000;
const MAX_TAGS = 32;
const MAX_TAG_CHARS = 100;

export interface AnnotationProposalToolSpec {
  type: "function";
  name: typeof ANNOTATION_PROPOSAL_TOOL;
  description: string;
  inputSchema: Record<string, unknown>;
}

/**
 * A fully bound annotation target. `position` can only originate in a
 * persisted Reader anchor; the Agent tool has no position/page arguments.
 */
export interface AnnotationProposalTarget {
  anchorId: string;
  libraryID: number | string;
  itemKey: string | null;
  attachmentKey: string;
  pageNumber?: number;
  position: JsonValue;
  selectedText: string;
  comment: string;
  tags: string[];
}

export interface AnnotationProposalHost {
  /** Re-reads the attachment file at Apply time; null means unavailable. */
  readAttachmentPdfSha256(
    libraryID: number | string,
    attachmentKey: string,
  ): Promise<string | null>;
  createHighlight(target: AnnotationProposalTarget): Promise<string>;
  deleteAnnotation(libraryID: number | string, annotationKey: string): Promise<void>;
}

export interface AnnotationProposalCallbacks {
  /** Returns all persisted anchors visible to the current Agent session. */
  getAnchors(): readonly AnchorRecord[];
  /** Persists the Zotero key only after every create in the batch succeeds. */
  setAnnotationKey(anchorId: string, annotationKey: string | undefined): Promise<void>;
  onState(): void;
}

export interface AnnotationProposalResolution {
  decision: "accepted" | "rejected";
  annotationKeys: string[];
}

interface RequestedAnchor {
  anchorId: string;
  comment?: string;
  tags: string[];
}

interface BoundAnchor {
  request: RequestedAnchor;
  target: AnnotationProposalTarget;
  pdfSha256: string | null;
  fingerprint: string;
}

interface PendingAnnotationBatch {
  id: string;
  createdAt: string;
  anchors: BoundAnchor[];
  review: DiffReview;
}

export class AnnotationProposalApplyError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "AnnotationProposalApplyError";
  }
}

/**
 * Review gate for Agent-proposed Zotero highlights.
 *
 * The model may select existing anchor IDs and supply comments/tags, but it
 * can never supply geometry. Each proposal snapshots the exact persisted
 * Reader position and revalidates it immediately before Apply.
 */
export class AnnotationProposalService {
  readonly tools: readonly AnnotationProposalToolSpec[] = [ANNOTATION_PROPOSAL_TOOL_SPEC];

  private readonly pending = new Map<string, PendingAnnotationBatch>();
  private resolveQueue: Promise<unknown> = Promise.resolve();

  constructor(
    private readonly host: AnnotationProposalHost,
    private readonly callbacks: AnnotationProposalCallbacks,
    private readonly now: () => Date = () => new Date(),
    private readonly idFactory: (prefix: string) => string = randomID,
  ) {}

  getReviews(): DiffReview[] {
    return [...this.pending.values()]
      .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
      .map((entry) => ({ ...entry.review }));
  }

  async invokeTool(
    tool: string,
    rawArguments: Record<string, unknown>,
    anchorsOverride?: readonly AnchorRecord[],
  ): Promise<Record<string, unknown>> {
    if (tool !== ANNOTATION_PROPOSAL_TOOL) {
      throw new Error(`Unknown Zotero annotation tool: ${tool}`);
    }
    const requests = parseRequestedAnchors(rawArguments);
    const available = new Map(
      (anchorsOverride ?? this.callbacks.getAnchors()).map((entry) => [entry.anchorId, entry]),
    );
    const anchors = requests.map((request) => bindAnchor(request, available.get(request.anchorId)));
    const id = this.idFactory("annotation-review");
    const createdAt = this.now().toISOString();
    const review: DiffReview = {
      id,
      title: readReviewTitle(rawArguments.title),
      summary: `${anchors.length} Zotero highlight${anchors.length === 1 ? "" : "s"} awaiting one batch approval`,
      diff: buildAnnotationDiff(anchors),
      state: "pending",
    };
    this.pending.set(id, { id, createdAt, anchors, review });
    this.callbacks.onState();
    return {
      status: "awaiting_user_review",
      reviewId: id,
      annotations: anchors.length,
      message: "The highlights are bound to existing Reader selections. Nothing has been written to Zotero; the user must accept the batch review.",
      diff: review.diff,
    };
  }

  async resolveReview(
    reviewId: string,
    decision: "accept" | "reject",
  ): Promise<AnnotationProposalResolution> {
    const pending = this.pending.get(reviewId);
    if (!pending) throw new Error("This annotation review has expired");
    if (pending.review.state !== "pending") {
      throw new Error("This annotation review was already resolved or is being applied");
    }
    // Claim synchronously, before the first await, to make double-clicks safe.
    pending.review.state = "resolving";
    this.callbacks.onState();
    return this.runExclusive(() => this.runResolveReview(pending, decision));
  }

  private runExclusive<T>(run: () => Promise<T>): Promise<T> {
    const result = this.resolveQueue.catch(() => {}).then(run);
    this.resolveQueue = result;
    return result;
  }

  private async runResolveReview(
    pending: PendingAnnotationBatch,
    decision: "accept" | "reject",
  ): Promise<AnnotationProposalResolution> {
    if (decision === "reject") {
      pending.review.state = "rejected";
      pending.review.summary = "The annotation batch was rejected; Zotero was not changed.";
      this.callbacks.onState();
      return { decision: "rejected", annotationKeys: [] };
    }

    const created: Array<{ anchorId: string; libraryID: number | string; annotationKey: string }> = [];
    const persisted: string[] = [];
    try {
      const current = new Map(this.callbacks.getAnchors().map((entry) => [entry.anchorId, entry]));
      for (const bound of pending.anchors) {
        const live = current.get(bound.target.anchorId);
        if (!live || annotationAnchorFingerprint(live) !== bound.fingerprint) {
          throw new Error(`Reader selection ${bound.target.anchorId} changed after this review was prepared`);
        }
        if (live.annotationKey) {
          throw new Error(`Reader selection ${bound.target.anchorId} already has a Zotero annotation`);
        }
        if (live.position === undefined || live.position === null) {
          throw new Error(`Reader selection ${bound.target.anchorId} no longer has an exact Reader position`);
        }
      }

      // Anchor fingerprints only prove that our persisted metadata did not
      // change. Re-hash every distinct attachment before the first write so a
      // replaced or missing PDF cannot receive annotations at stale geometry.
      // This is deliberately a complete preflight: a bad attachment anywhere
      // in the batch prevents every annotation write.
      const currentPdfHashes = new Map<string, string | null>();
      for (const bound of pending.anchors) {
        const attachmentIdentity = stableJson([
          bound.target.libraryID,
          bound.target.attachmentKey,
        ]);
        if (!currentPdfHashes.has(attachmentIdentity)) {
          currentPdfHashes.set(
            attachmentIdentity,
            await this.host.readAttachmentPdfSha256(
              bound.target.libraryID,
              bound.target.attachmentKey,
            ),
          );
        }
        const currentPdfSha256 = normalizePdfSha256(currentPdfHashes.get(attachmentIdentity));
        const recordedPdfSha256 = normalizePdfSha256(bound.pdfSha256);
        if (!recordedPdfSha256) {
          throw new Error(
            `Reader selection ${bound.target.anchorId} was recorded without a verifiable PDF hash`,
          );
        }
        if (!currentPdfSha256) {
          throw new Error(
            `Attachment PDF ${bound.target.attachmentKey} is unavailable at annotation Apply`,
          );
        }
        if (currentPdfSha256 !== recordedPdfSha256) {
          throw new Error(
            `Attachment PDF ${bound.target.attachmentKey} changed after this review was prepared`,
          );
        }
      }

      for (const bound of pending.anchors) {
        const annotationKey = normalizeAnnotationKey(await this.host.createHighlight(cloneTarget(bound.target)));
        created.push({
          anchorId: bound.target.anchorId,
          libraryID: bound.target.libraryID,
          annotationKey,
        });
      }

      // Persist only after the external batch succeeded. A persistence error
      // rolls back both sides below rather than leaving half-linked anchors.
      for (const entry of created) {
        await this.callbacks.setAnnotationKey(entry.anchorId, entry.annotationKey);
        persisted.push(entry.anchorId);
      }

      pending.review.state = "accepted";
      pending.review.summary = `${created.length} Zotero highlight${created.length === 1 ? "" : "s"} created.`;
      this.callbacks.onState();
      return { decision: "accepted", annotationKeys: created.map((entry) => entry.annotationKey) };
    }
    catch (error) {
      const rollbackErrors: string[] = [];
      for (const anchorId of [...persisted].reverse()) {
        try {
          await this.callbacks.setAnnotationKey(anchorId, undefined);
        }
        catch (rollbackError) {
          rollbackErrors.push(describeError(rollbackError));
        }
      }
      for (const entry of [...created].reverse()) {
        try {
          await this.host.deleteAnnotation(entry.libraryID, entry.annotationKey);
        }
        catch (rollbackError) {
          rollbackErrors.push(describeError(rollbackError));
        }
      }
      pending.review.state = "failed";
      pending.review.summary = rollbackErrors.length
        ? "Annotation Apply failed and rollback was incomplete. No automatic retry will occur."
        : "Annotation Apply failed and all writes were rolled back.";
      this.callbacks.onState();
      const suffix = rollbackErrors.length
        ? ` Rollback was incomplete: ${rollbackErrors.join("; ")}`
        : " All annotations created by this batch were rolled back.";
      throw new AnnotationProposalApplyError(`Annotation batch failed: ${describeError(error)}.${suffix}`, {
        cause: error,
      });
    }
  }
}

export const ANNOTATION_PROPOSAL_TOOL_SPEC: AnnotationProposalToolSpec = {
  type: "function",
  name: ANNOTATION_PROPOSAL_TOOL,
  description: "Propose one reviewed batch of Zotero highlights using existing Reader-selection anchor IDs. Geometry cannot be supplied or invented.",
  inputSchema: {
    type: "object",
    additionalProperties: false,
    properties: {
      title: { type: "string", maxLength: 160 },
      anchorIds: {
        type: "array",
        minItems: 1,
        maxItems: MAX_BATCH_SIZE,
        uniqueItems: true,
        items: { type: "string", minLength: 1, maxLength: 200 },
      },
      annotations: {
        type: "array",
        minItems: 1,
        maxItems: MAX_BATCH_SIZE,
        items: {
          type: "object",
          additionalProperties: false,
          required: ["anchorId"],
          properties: {
            anchorId: { type: "string", minLength: 1, maxLength: 200 },
            comment: { type: "string", maxLength: MAX_COMMENT_CHARS },
            tags: {
              type: "array",
              maxItems: MAX_TAGS,
              uniqueItems: true,
              items: { type: "string", minLength: 1, maxLength: MAX_TAG_CHARS },
            },
          },
        },
      },
    },
    oneOf: [
      { required: ["anchorIds"] },
      { required: ["annotations"] },
    ],
  },
};

function parseRequestedAnchors(raw: Record<string, unknown>): RequestedAnchor[] {
  const hasIds = raw.anchorIds !== undefined;
  const hasAnnotations = raw.annotations !== undefined;
  if (hasIds === hasAnnotations) {
    throw new Error("Provide exactly one of anchorIds or annotations");
  }
  let requests: RequestedAnchor[];
  if (hasIds) {
    if (!Array.isArray(raw.anchorIds)) throw new Error("anchorIds must be an array");
    requests = raw.anchorIds.map((value) => ({ anchorId: readAnchorId(value), tags: [] }));
  }
  else {
    if (!Array.isArray(raw.annotations)) throw new Error("annotations must be an array");
    requests = raw.annotations.map((value) => {
      if (!isRecord(value)) throw new Error("Each annotation proposal must be an object");
      const comment = value.comment === undefined ? undefined : readBoundedText(value.comment, "comment", MAX_COMMENT_CHARS);
      const tags = value.tags === undefined ? [] : readTags(value.tags);
      return { anchorId: readAnchorId(value.anchorId), comment, tags };
    });
  }
  if (!requests.length || requests.length > MAX_BATCH_SIZE) {
    throw new Error(`Annotation batches must contain 1-${MAX_BATCH_SIZE} anchors`);
  }
  const ids = requests.map((entry) => entry.anchorId);
  if (new Set(ids).size !== ids.length) throw new Error("An anchor may appear only once in a batch");
  return requests;
}

function bindAnchor(request: RequestedAnchor, anchor: AnchorRecord | undefined): BoundAnchor {
  if (!anchor) throw new Error(`Anchor ${request.anchorId} is not an existing Reader selection`);
  if (anchor.annotationKey) throw new Error(`Anchor ${request.anchorId} already has a Zotero annotation`);
  if (anchor.position === undefined || anchor.position === null) {
    throw new Error(`Anchor ${request.anchorId} has no exact Reader position and cannot become a highlight`);
  }
  if (!anchor.selectedText.trim()) throw new Error(`Anchor ${request.anchorId} has no selected Reader text`);
  const comment = request.comment?.trim() || defaultComment(anchor);
  const target: AnnotationProposalTarget = {
    anchorId: anchor.anchorId,
    libraryID: anchor.libraryID,
    itemKey: anchor.itemKey,
    attachmentKey: anchor.attachmentKey,
    pageNumber: anchor.pageNumber,
    position: cloneJson(anchor.position),
    selectedText: anchor.selectedText,
    comment,
    tags: [...request.tags],
  };
  return {
    request,
    target,
    pdfSha256: anchor.pdfSha256,
    fingerprint: annotationAnchorFingerprint(anchor),
  };
}

function annotationAnchorFingerprint(anchor: AnchorRecord): string {
  return stableJson({
    anchorId: anchor.anchorId,
    libraryID: anchor.libraryID,
    itemKey: anchor.itemKey,
    attachmentKey: anchor.attachmentKey,
    pdfSha256: anchor.pdfSha256,
    annotationKey: anchor.annotationKey ?? null,
    pageNumber: anchor.pageNumber ?? null,
    position: anchor.position ?? null,
    selectedText: anchor.selectedText,
  });
}

function buildAnnotationDiff(anchors: readonly BoundAnchor[]): string {
  const lines = ["Proposed Zotero annotations", ""];
  for (const [index, bound] of anchors.entries()) {
    const page = bound.target.pageNumber ? `PDF page ${bound.target.pageNumber}` : "PDF page unavailable";
    lines.push(`+ ${index + 1}. ${sanitizeDiffLine(page)} · anchor ${sanitizeDiffLine(bound.target.anchorId)}`);
    lines.push(`+ Selection: ${sanitizeDiffLine(bound.target.selectedText)}`);
    lines.push(`+ Comment: ${sanitizeDiffLine(bound.target.comment)}`);
    if (bound.target.tags.length) lines.push(`+ Tags: ${bound.target.tags.map(sanitizeDiffLine).join(", ")}`);
    lines.push("");
  }
  return lines.join("\n").trimEnd();
}

function defaultComment(anchor: AnchorRecord): string {
  const answer = anchor.answerSummary?.trim();
  return answer ? `Q: ${anchor.question}\n\nA: ${answer}` : `Q: ${anchor.question}`;
}

function cloneTarget(target: AnnotationProposalTarget): AnnotationProposalTarget {
  return { ...target, position: cloneJson(target.position), tags: [...target.tags] };
}

function cloneJson<T extends JsonValue>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (isRecord(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function readReviewTitle(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return "Review proposed Zotero annotations";
  return sanitizeDiffLine(value.trim().slice(0, 160));
}

function readAnchorId(value: unknown): string {
  return readBoundedText(value, "anchorId", 200).trim();
}

function readBoundedText(value: unknown, field: string, max: number): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${field} must be a non-empty string`);
  if (value.length > max) throw new Error(`${field} exceeds ${max} characters`);
  return value;
}

function readTags(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > MAX_TAGS) throw new Error(`tags must contain at most ${MAX_TAGS} strings`);
  const tags = value.map((tag) => readBoundedText(tag, "tag", MAX_TAG_CHARS).trim());
  if (new Set(tags).size !== tags.length) throw new Error("tags must be unique");
  return tags;
}

function normalizeAnnotationKey(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) throw new Error("Zotero returned an invalid annotation key");
  return value.trim();
}

function normalizePdfSha256(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim().toLowerCase();
  return /^[a-f0-9]{64}$/u.test(normalized) ? normalized : null;
}

function sanitizeDiffLine(value: string): string {
  return value
    .replace(/[\u0000-\u001F\u007F-\u009F\u202A-\u202E\u2066-\u2069]/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}

function describeError(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  return sanitizeDiffLine(text).slice(0, 500) || "unknown error";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
