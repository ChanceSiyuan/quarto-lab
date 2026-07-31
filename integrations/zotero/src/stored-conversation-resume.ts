import type { AgentClient } from "./agent-client";
import {
  CodexDisconnectedError,
  CodexRequestTimeoutError,
  CodexRpcError,
  type ThreadResumeParams,
  type ThreadResumeResponse,
} from "./codex-app-server";

export type StoredConversationResumeResult =
  | { kind: "resumed"; threadId: string }
  | { kind: "missing" };

function hasMissingStoredThreadMessage(error: Error): boolean {
  const message = error.message.trim().toLowerCase();
  return message === "thread not found" || message === "conversation not found";
}

export function isMissingStoredThreadError(error: unknown): boolean {
  if (error instanceof CodexRequestTimeoutError || error instanceof CodexDisconnectedError) {
    return false;
  }
  if (error instanceof CodexRpcError) {
    return error.method === "thread/resume" && hasMissingStoredThreadMessage(error);
  }
  if (!(error instanceof Error) || Object.getPrototypeOf(error) !== Error.prototype) {
    return false;
  }
  return hasMissingStoredThreadMessage(error);
}

export async function resumeStoredThread(
  client: Pick<AgentClient, "threadResume" | "threadRead">,
  params: ThreadResumeParams,
): Promise<StoredConversationResumeResult> {
  let resumed: ThreadResumeResponse;
  try {
    resumed = await client.threadResume(params);
  } catch (error) {
    if (isMissingStoredThreadError(error)) return { kind: "missing" };
    throw error;
  }
  const read = await client.threadRead(resumed.thread.id, true);
  return { kind: "resumed", threadId: read.thread.id };
}
