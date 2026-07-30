import type { ChatEntry, HistoryConversationOption } from "./sidebar";

export interface ImportedChatGPTConversation {
  id: string;
  title: string;
  updatedAt: string;
  entries: ChatEntry[];
}

export interface StoredChatGPTArchive {
  version: 1;
  importedAt: string;
  conversations: ImportedChatGPTConversation[];
}

type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as UnknownRecord
    : null;
}

function timestamp(value: unknown): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number) || number <= 0) return new Date(0).toISOString();
  return new Date(number < 10_000_000_000 ? number * 1000 : number).toISOString();
}

function messageText(message: UnknownRecord): string {
  const content = record(message.content);
  if (!content) return "";
  if (typeof content.text === "string") return content.text.trim();
  if (!Array.isArray(content.parts)) return "";
  return content.parts.map((part) => {
    if (typeof part === "string") return part;
    const value = record(part);
    if (!value) return "";
    if (typeof value.text === "string") return value.text;
    if (typeof value.content === "string") return value.content;
    return "";
  }).filter(Boolean).join("\n").trim();
}

function conversationNodes(conversation: UnknownRecord): UnknownRecord[] {
  const mapping = record(conversation.mapping);
  if (!mapping) return [];
  const nodes = Object.values(mapping).map(record).filter((node): node is UnknownRecord => Boolean(node));
  const current = typeof conversation.current_node === "string" ? conversation.current_node : "";
  if (!current) {
    return nodes.sort((left, right) => {
      const leftMessage = record(left.message);
      const rightMessage = record(right.message);
      return Number(leftMessage?.create_time || 0) - Number(rightMessage?.create_time || 0);
    });
  }
  const chain: UnknownRecord[] = [];
  const seen = new Set<string>();
  let nodeID: string | null = current;
  while (nodeID && !seen.has(nodeID)) {
    seen.add(nodeID);
    const node = record(mapping[nodeID]);
    if (!node) break;
    chain.push(node);
    nodeID = typeof node.parent === "string" ? node.parent : null;
  }
  return chain.reverse();
}

function parseConversation(value: unknown, index: number): ImportedChatGPTConversation | null {
  const conversation = record(value);
  if (!conversation) return null;
  const id = String(conversation.id || conversation.conversation_id || `chatgpt-${index}`);
  const entries: ChatEntry[] = [];
  for (const [nodeIndex, node] of conversationNodes(conversation).entries()) {
    const message = record(node.message);
    if (!message) continue;
    const metadata = record(message.metadata);
    if (metadata?.is_visually_hidden_from_conversation === true) continue;
    const author = record(message.author);
    const role = String(author?.role || "").toLowerCase();
    if (role !== "user" && role !== "assistant") continue;
    const text = messageText(message);
    if (!text) continue;
    entries.push({
      id: `chatgpt:${id}:${String(message.id || node.id || nodeIndex)}`,
      kind: role,
      text,
      state: "complete",
    });
  }
  if (!entries.length) return null;
  return {
    id: `chatgpt:${id}`,
    title: String(conversation.title || "Untitled ChatGPT conversation").trim()
      || "Untitled ChatGPT conversation",
    updatedAt: timestamp(conversation.update_time || conversation.create_time),
    entries,
  };
}

export function parseChatGPTExport(text: string): StoredChatGPTArchive {
  const parsed: unknown = JSON.parse(text);
  const root = record(parsed);
  const values = Array.isArray(parsed)
    ? parsed
    : Array.isArray(root?.conversations) ? root.conversations : null;
  if (!values) throw new Error("Choose conversations.json from a ChatGPT data export");
  const conversations = values
    .map(parseConversation)
    .filter((conversation): conversation is ImportedChatGPTConversation => Boolean(conversation))
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  if (!conversations.length) {
    throw new Error("No readable user/assistant conversations were found in this export");
  }
  return {
    version: 1,
    importedAt: new Date().toISOString(),
    conversations,
  };
}

export function parseStoredChatGPTArchive(text: string): StoredChatGPTArchive {
  const parsed = record(JSON.parse(text));
  if (parsed?.version !== 1 || !Array.isArray(parsed.conversations)) {
    throw new Error("The saved ChatGPT history archive is invalid");
  }
  return {
    version: 1,
    importedAt: typeof parsed.importedAt === "string" ? parsed.importedAt : new Date(0).toISOString(),
    conversations: parsed.conversations
      .map((value, index) => {
        const item = record(value);
        if (!item || !Array.isArray(item.entries)) return null;
        const entries = item.entries.filter((entry): entry is ChatEntry => {
          const candidate = record(entry);
          return Boolean(
            candidate
            && typeof candidate.id === "string"
            && (candidate.kind === "user" || candidate.kind === "assistant")
            && typeof candidate.text === "string",
          );
        });
        if (!entries.length) return null;
        return {
          id: typeof item.id === "string" ? item.id : `chatgpt:stored-${index}`,
          title: typeof item.title === "string" ? item.title : "Untitled ChatGPT conversation",
          updatedAt: typeof item.updatedAt === "string" ? item.updatedAt : new Date(0).toISOString(),
          entries,
        };
      })
      .filter((conversation): conversation is ImportedChatGPTConversation => Boolean(conversation)),
  };
}

export function importedChatOptions(
  archive: StoredChatGPTArchive | null,
  activeID: string | null,
): HistoryConversationOption[] {
  return (archive?.conversations || []).map((conversation) => ({
    id: conversation.id,
    title: conversation.title,
    preview: conversation.entries.find((entry) => entry.kind === "user")?.text,
    updatedAt: conversation.updatedAt,
    source: "chatgpt",
    sourceLabel: "Imported ChatGPT",
    pinned: false,
    active: conversation.id === activeID,
    readOnly: true,
  }));
}
