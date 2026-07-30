import { describe, expect, it } from "vitest";
import {
  importedChatOptions,
  parseChatGPTExport,
  parseStoredChatGPTArchive,
} from "../src/chatgpt-history";

describe("ChatGPT history import", () => {
  it("follows the active branch and keeps only visible user/assistant messages", () => {
    const archive = parseChatGPTExport(JSON.stringify([{
      id: "conversation-1",
      title: "Quantum notes",
      create_time: 100,
      update_time: 200,
      current_node: "assistant",
      mapping: {
        root: { id: "root", parent: null, message: null },
        user: {
          id: "user",
          parent: "root",
          message: {
            id: "m-user",
            author: { role: "user" },
            create_time: 101,
            content: { content_type: "text", parts: ["Explain the theorem"] },
          },
        },
        hidden: {
          id: "hidden",
          parent: "user",
          message: {
            id: "m-hidden",
            author: { role: "assistant" },
            content: { parts: ["internal"] },
            metadata: { is_visually_hidden_from_conversation: true },
          },
        },
        assistant: {
          id: "assistant",
          parent: "hidden",
          message: {
            id: "m-assistant",
            author: { role: "assistant" },
            create_time: 102,
            content: { content_type: "text", parts: ["Here is the proof."] },
          },
        },
        unused_branch: {
          id: "unused_branch",
          parent: "user",
          message: {
            id: "m-unused",
            author: { role: "assistant" },
            content: { parts: ["Unused branch"] },
          },
        },
      },
    }]));

    expect(archive.conversations).toHaveLength(1);
    expect(archive.conversations[0]).toMatchObject({
      id: "chatgpt:conversation-1",
      title: "Quantum notes",
      updatedAt: new Date(200_000).toISOString(),
    });
    expect(archive.conversations[0]?.entries.map((entry) => [entry.kind, entry.text])).toEqual([
      ["user", "Explain the theorem"],
      ["assistant", "Here is the proof."],
    ]);
  });

  it("round-trips the normalized local archive and exposes read-only history rows", () => {
    const imported = parseChatGPTExport(JSON.stringify([{
      id: "c1",
      title: "A chat",
      current_node: "n1",
      mapping: {
        n1: {
          id: "n1",
          parent: null,
          message: { id: "m1", author: { role: "user" }, content: { parts: ["Hello"] } },
        },
      },
    }]));
    const stored = parseStoredChatGPTArchive(JSON.stringify(imported));
    const options = importedChatOptions(stored, "chatgpt:c1");

    expect(stored.conversations[0]?.entries[0]?.text).toBe("Hello");
    expect(options[0]).toMatchObject({
      id: "chatgpt:c1",
      source: "chatgpt",
      sourceLabel: "Imported ChatGPT",
      active: true,
      readOnly: true,
    });
  });

  it("rejects unrelated JSON instead of silently importing it", () => {
    expect(() => parseChatGPTExport('{"items":[]}')).toThrow(/conversations\.json/);
  });
});
