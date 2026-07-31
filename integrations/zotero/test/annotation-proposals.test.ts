import { describe, expect, it, vi } from "vitest";
import type { AnchorRecord } from "../src/paper-trail";
import {
  ANNOTATION_PROPOSAL_TOOL,
  AnnotationProposalService,
  type AnnotationProposalHost,
} from "../src/annotation-proposals";

function anchor(anchorId: string, pageNumber: number, overrides: Partial<AnchorRecord> = {}): AnchorRecord {
  return {
    anchorId,
    libraryID: 1,
    itemKey: "PARENT",
    attachmentKey: "ATTACH",
    pdfSha256: "a".repeat(64),
    pageNumber,
    position: { pageIndex: pageNumber - 1, rects: [[10, 20, 30, 40]] },
    selectedText: `Selection ${anchorId}`,
    question: `Question ${anchorId}`,
    answerSummary: `Answer ${anchorId}`,
    threadId: "thread-1",
    turnRange: [1, 2],
    status: "open",
    createdAt: "2026-07-31T00:00:00.000Z",
    ...overrides,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

function harness(initial = [anchor("a1", 1), anchor("a2", 2)]) {
  let anchors = structuredClone(initial);
  const currentPdfHashes = new Map<string, string | null>();
  for (const entry of initial) {
    currentPdfHashes.set(`${entry.libraryID}:${entry.attachmentKey}`, entry.pdfSha256);
  }
  const host: AnnotationProposalHost = {
    createHighlight: vi.fn(async (target) => `ANN-${target.anchorId}`),
    deleteAnnotation: vi.fn(async () => {}),
    readAttachmentPdfSha256: vi.fn(async (libraryID, attachmentKey) => (
      currentPdfHashes.get(`${libraryID}:${attachmentKey}`) ?? null
    )),
  };
  const onState = vi.fn();
  let sequence = 0;
  const service = new AnnotationProposalService(host, {
    getAnchors: () => structuredClone(anchors),
    setAnnotationKey: async (anchorId, annotationKey) => {
      anchors = anchors.map((entry) => entry.anchorId === anchorId
        ? { ...entry, annotationKey }
        : entry);
    },
    onState,
  }, () => new Date("2026-07-31T00:00:00.000Z"), (prefix) => `${prefix}-${++sequence}`);
  return {
    service,
    host,
    onState,
    anchors: () => structuredClone(anchors),
    mutateAnchor(anchorId: string, patch: Partial<AnchorRecord>) {
      anchors = anchors.map((entry) => entry.anchorId === anchorId ? { ...entry, ...patch } : entry);
    },
    setCurrentPdfHash(libraryID: number | string, attachmentKey: string, hash: string | null) {
      currentPdfHashes.set(`${libraryID}:${attachmentKey}`, hash);
    },
  };
}

describe("AnnotationProposalService", () => {
  it("exposes a dynamic tool that can only reference existing anchor IDs", async () => {
    const { service, host } = harness();

    expect(service.tools[0]?.name).toBe(ANNOTATION_PROPOSAL_TOOL);
    const result = await service.invokeTool(ANNOTATION_PROPOSAL_TOOL, {
      title: "Keep the two cited passages",
      annotations: [
        { anchorId: "a1", comment: "Supports the setup", tags: ["evidence"] },
        { anchorId: "a2" },
      ],
    });

    expect(result).toMatchObject({ status: "awaiting_user_review", reviewId: "annotation-review-1" });
    expect(host.createHighlight).not.toHaveBeenCalled();
    expect(service.getReviews()).toHaveLength(1);
    expect(service.getReviews()[0]).toMatchObject({ state: "pending", title: "Keep the two cited passages" });
    expect(service.getReviews()[0]!.diff).toContain("PDF page 1");
    expect(service.getReviews()[0]!.diff).toContain("Selection a2");

    await expect(service.invokeTool(ANNOTATION_PROPOSAL_TOOL, {
      anchorIds: ["missing"],
    })).rejects.toThrow(/existing Reader selection/i);
  });

  it("creates every annotation after one acceptance and persists keys only after the batch succeeds", async () => {
    const { service, host, anchors } = harness();
    await service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1", "a2"] });

    const result = await service.resolveReview("annotation-review-1", "accept");

    expect(result).toEqual({ decision: "accepted", annotationKeys: ["ANN-a1", "ANN-a2"] });
    expect(host.createHighlight).toHaveBeenCalledTimes(2);
    expect(anchors().map((entry) => entry.annotationKey)).toEqual(["ANN-a1", "ANN-a2"]);
    expect(service.getReviews()[0]?.state).toBe("accepted");
  });

  it("claims a review synchronously so a double acceptance cannot write twice", async () => {
    const { service, host } = harness([anchor("a1", 1)]);
    const gate = deferred<string>();
    vi.mocked(host.createHighlight).mockImplementationOnce(() => gate.promise);
    await service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1"] });

    const first = service.resolveReview("annotation-review-1", "accept");
    const second = service.resolveReview("annotation-review-1", "accept");
    await expect(second).rejects.toThrow(/already resolved|being applied/i);
    gate.resolve("ANN-a1");
    await first;

    expect(host.createHighlight).toHaveBeenCalledTimes(1);
  });

  it("rolls back created annotations in reverse order if any creation fails", async () => {
    const { service, host, anchors } = harness([
      anchor("a1", 1), anchor("a2", 2), anchor("a3", 3),
    ]);
    vi.mocked(host.createHighlight)
      .mockResolvedValueOnce("ANN-a1")
      .mockResolvedValueOnce("ANN-a2")
      .mockRejectedValueOnce(new Error("Zotero write failed"));
    await service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1", "a2", "a3"] });

    await expect(service.resolveReview("annotation-review-1", "accept"))
      .rejects.toThrow(/rolled back/i);

    expect(vi.mocked(host.deleteAnnotation).mock.calls).toEqual([
      [1, "ANN-a2"],
      [1, "ANN-a1"],
    ]);
    expect(anchors().every((entry) => !entry.annotationKey)).toBe(true);
    expect(service.getReviews()[0]?.state).toBe("failed");
  });

  it("revalidates exact Reader positions and refuses stale or already-annotated anchors", async () => {
    const { service, host, mutateAnchor } = harness([anchor("a1", 1)]);
    await service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1"] });
    mutateAnchor("a1", { position: { pageIndex: 0, rects: [[99, 99, 100, 100]] } });

    await expect(service.resolveReview("annotation-review-1", "accept"))
      .rejects.toThrow(/changed after this review/i);
    expect(host.createHighlight).not.toHaveBeenCalled();

    const missingPosition = harness([anchor("a1", 1, { position: undefined })]);
    await expect(missingPosition.service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1"] }))
      .rejects.toThrow(/exact Reader position/i);

    const alreadyWritten = harness([anchor("a1", 1, { annotationKey: "EXISTING" })]);
    await expect(alreadyWritten.service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1"] }))
      .rejects.toThrow(/already has a Zotero annotation/i);
  });

  it("re-reads the attachment PDF hash at acceptance and refuses a changed or missing PDF before writing", async () => {
    const changed = harness([anchor("a1", 1)]);
    await changed.service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1"] });
    changed.setCurrentPdfHash(1, "ATTACH", "b".repeat(64));

    await expect(changed.service.resolveReview("annotation-review-1", "accept"))
      .rejects.toThrow(/PDF.*changed/i);
    expect(changed.host.readAttachmentPdfSha256).toHaveBeenCalledWith(1, "ATTACH");
    expect(changed.host.createHighlight).not.toHaveBeenCalled();
    expect(changed.anchors().every((entry) => !entry.annotationKey)).toBe(true);

    const missing = harness([anchor("a1", 1)]);
    await missing.service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1"] });
    missing.setCurrentPdfHash(1, "ATTACH", null);

    await expect(missing.service.resolveReview("annotation-review-1", "accept"))
      .rejects.toThrow(/PDF.*unavailable/i);
    expect(missing.host.createHighlight).not.toHaveBeenCalled();
  });

  it("conservatively refuses anchors that were recorded without a PDF hash", async () => {
    const instance = harness([anchor("a1", 1, { pdfSha256: null })]);
    instance.setCurrentPdfHash(1, "ATTACH", "a".repeat(64));
    await instance.service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1"] });

    await expect(instance.service.resolveReview("annotation-review-1", "accept"))
      .rejects.toThrow(/recorded without.*PDF hash/i);
    expect(instance.host.readAttachmentPdfSha256).toHaveBeenCalledWith(1, "ATTACH");
    expect(instance.host.createHighlight).not.toHaveBeenCalled();
  });

  it("preflights every attachment hash before creating any annotation in a batch", async () => {
    const instance = harness([
      anchor("a1", 1, { attachmentKey: "ATTACH-1", pdfSha256: "a".repeat(64) }),
      anchor("a2", 2, { attachmentKey: "ATTACH-2", pdfSha256: "b".repeat(64) }),
    ]);
    instance.setCurrentPdfHash(1, "ATTACH-2", "c".repeat(64));
    await instance.service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1", "a2"] });

    await expect(instance.service.resolveReview("annotation-review-1", "accept"))
      .rejects.toThrow(/PDF.*changed/i);
    expect(instance.host.readAttachmentPdfSha256).toHaveBeenCalledTimes(2);
    expect(instance.host.createHighlight).not.toHaveBeenCalled();
    expect(instance.host.deleteAnnotation).not.toHaveBeenCalled();
  });

  it("rejects an entire batch without writing", async () => {
    const { service, host, anchors } = harness();
    await service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1", "a2"] });

    await expect(service.resolveReview("annotation-review-1", "reject"))
      .resolves.toEqual({ decision: "rejected", annotationKeys: [] });
    expect(host.createHighlight).not.toHaveBeenCalled();
    expect(host.deleteAnnotation).not.toHaveBeenCalled();
    expect(anchors().every((entry) => !entry.annotationKey)).toBe(true);
    expect(service.getReviews()[0]?.state).toBe("rejected");
  });

  it("serializes accepted batches so Zotero writes never interleave", async () => {
    const { service, host } = harness();
    const gate = deferred<string>();
    const events: string[] = [];
    vi.mocked(host.createHighlight)
      .mockImplementationOnce(async () => {
        events.push("first:start");
        const key = await gate.promise;
        events.push("first:end");
        return key;
      })
      .mockImplementationOnce(async () => {
        events.push("second:start");
        return "ANN-a2";
      });
    await service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a1"] });
    await service.invokeTool(ANNOTATION_PROPOSAL_TOOL, { anchorIds: ["a2"] });

    const first = service.resolveReview("annotation-review-1", "accept");
    const second = service.resolveReview("annotation-review-2", "accept");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(events).toEqual(["first:start"]);
    gate.resolve("ANN-a1");
    await Promise.all([first, second]);
    expect(events).toEqual(["first:start", "first:end", "second:start"]);
  });
});
