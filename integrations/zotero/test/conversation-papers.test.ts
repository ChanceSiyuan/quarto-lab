import { describe, expect, it } from "vitest";

import { ConversationPaperRegistry } from "../src/conversation-papers";

const paper = (id: string) => ({
  id,
  libraryID: "1",
  attachmentKey: `attachment-${id}`,
  title: `Paper ${id}`,
  mode: "retrieval" as const,
});

describe("ConversationPaperRegistry", () => {
  it("keeps secondary papers isolated between conversations", () => {
    const registry = new ConversationPaperRegistry();
    registry.add("thread-a", paper("a"));
    registry.add("thread-b", paper("b"));

    expect(registry.list("thread-a").map((entry) => entry.id)).toEqual(["a"]);
    expect(registry.list("thread-b").map((entry) => entry.id)).toEqual(["b"]);
  });

  it("toggles retrieval/full mode without duplicating a paper", () => {
    const registry = new ConversationPaperRegistry();
    registry.add("thread", paper("a"));
    registry.add("thread", { ...paper("a"), title: "Updated" });

    expect(registry.toggleMode("thread", "a")).toMatchObject({ mode: "full" });
    expect(registry.list("thread")).toHaveLength(1);
    expect(registry.list("thread")[0]).toMatchObject({ title: "Updated", mode: "full" });
  });

  it("round-trips its persisted profile state", () => {
    const registry = new ConversationPaperRegistry();
    registry.add("thread", paper("a"));
    const restored = new ConversationPaperRegistry();
    restored.restore(JSON.parse(registry.serialize()));

    expect(restored.list("thread")).toEqual([paper("a")]);
  });
});
