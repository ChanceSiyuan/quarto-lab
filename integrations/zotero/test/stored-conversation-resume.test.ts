import { describe, expect, it, vi } from "vitest";
import type { AgentClient } from "../src/agent-client";
import {
  CodexDisconnectedError,
  CodexRequestTimeoutError,
  CodexRpcError,
  type ThreadResumeParams,
} from "../src/codex-app-server";
import {
  isMissingStoredThreadError,
  resumeStoredThread,
} from "../src/stored-conversation-resume";

const params: ThreadResumeParams = {
  threadId: "stored-thread",
  cwd: "/workspace/paper",
};

describe("isMissingStoredThreadError", () => {
  it("classifies only exact missing messages at the resume boundary", () => {
    const rpcMissing = new CodexRpcError(
      { code: -32602, message: "thread not found" },
      "thread/resume",
      7,
    );

    expect(isMissingStoredThreadError(rpcMissing)).toBe(true);
    expect(isMissingStoredThreadError(new Error("thread not found"))).toBe(true);
    expect(isMissingStoredThreadError(new Error("thread resume failed"))).toBe(false);
    expect(isMissingStoredThreadError(
      new CodexRequestTimeoutError("thread/resume", 30_000, 8),
    )).toBe(false);
    expect(isMissingStoredThreadError(new CodexDisconnectedError())).toBe(false);
    expect(isMissingStoredThreadError(new CodexRpcError(
      { code: -32603, message: "authentication required" },
      "thread/resume",
      9,
    ))).toBe(false);
    expect(isMissingStoredThreadError(new CodexRpcError(
      { code: -32602, message: "thread not found" },
      "thread/read",
      10,
    ))).toBe(false);
  });

  it("normalizes a whole missing message without accepting substrings", () => {
    expect(isMissingStoredThreadError(new Error("  Conversation Not Found  "))).toBe(true);
    expect(isMissingStoredThreadError(new Error("conversation not found while resuming"))).toBe(false);
  });

  it("does not classify a non-RPC Error subclass as a missing stored thread", () => {
    class OperationalError extends Error {}

    expect(isMissingStoredThreadError(new OperationalError("thread not found"))).toBe(false);
  });
});

describe("resumeStoredThread", () => {
  it("uses the read-confirmed thread id after resuming the requested thread", async () => {
    const client: Pick<AgentClient, "threadResume" | "threadRead"> = {
      threadResume: vi.fn(async () => ({ thread: { id: "requested-thread" } })),
      threadRead: vi.fn(async () => ({ thread: { id: "canonical-thread" } })),
    };

    await expect(resumeStoredThread(client, params)).resolves.toEqual({
      kind: "resumed",
      threadId: "canonical-thread",
    });
    expect(client.threadResume).toHaveBeenCalledWith(params);
    expect(client.threadRead).toHaveBeenCalledWith("requested-thread", true);
  });

  it("returns missing when resume reports an exact missing thread", async () => {
    const client: Pick<AgentClient, "threadResume" | "threadRead"> = {
      threadResume: vi.fn(async () => {
        throw new CodexRpcError(
          { code: -32602, message: "thread not found" },
          "thread/resume",
          7,
        );
      }),
      threadRead: vi.fn(async () => ({ thread: { id: "unreachable" } })),
    };

    await expect(resumeStoredThread(client, params)).resolves.toEqual({ kind: "missing" });
    expect(client.threadRead).not.toHaveBeenCalled();
  });

  it("propagates a timeout from resume", async () => {
    const timeout = new CodexRequestTimeoutError("thread/resume", 30_000, 8);
    const client: Pick<AgentClient, "threadResume" | "threadRead"> = {
      threadResume: vi.fn(async () => {
        throw timeout;
      }),
      threadRead: vi.fn(async () => ({ thread: { id: "unreachable" } })),
    };

    await expect(resumeStoredThread(client, params)).rejects.toBe(timeout);
  });

  it("propagates a read failure after a successful resume", async () => {
    const readFailure = new Error("read failed");
    const client: Pick<AgentClient, "threadResume" | "threadRead"> = {
      threadResume: vi.fn(async () => ({ thread: { id: "requested-thread" } })),
      threadRead: vi.fn(async () => {
        throw readFailure;
      }),
    };

    await expect(resumeStoredThread(client, params)).rejects.toBe(readFailure);
  });
});
