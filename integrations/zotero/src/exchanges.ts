import type { ChatEntry } from "./sidebar";

export interface Exchange { id: string; entries: ChatEntry[] }

const PROCESS_KINDS = new Set<ChatEntry["kind"]>(["reasoning", "tool", "command"]);

const FRIENDLY_TOOL_NAMES: Record<string, string> = {
  zotero_get_reader_context: "Read Reader Context",
  zotero_get_current_page: "Read Current Page",
  zotero_get_current_selection: "Read Selection",
  zotero_search_current_pdf: "Search Current PDF",
  zotero_read_pdf_pages: "Read Paper Pages",
  zotero_search_library: "Search Library",
  zotero_search_library_items: "Search Zotero Library",
  zotero_read_note: "Read Zotero Note",
  zotero_read_library_pdf_pages: "Read Library Paper Pages",
  zotero_search_library_pdf: "Search Library PDF",
  zotero_list_annotations: "View Annotations",
  zotero_get_pdf_outline: "Read Paper Outline",
  zotero_propose_annotations: "Prepare Annotation Review",
  zotero_propose_note_from_qmd: "Prepare Zotero Note Review",
};

export function isProcessKind(kind: ChatEntry["kind"]): boolean {
  return PROCESS_KINDS.has(kind);
}

export function groupEntries(entries: ChatEntry[]): Exchange[] {
  const groups: Exchange[] = [];
  let current: Exchange | null = null;
  for (const entry of entries) {
    if (entry.kind === "user" || !current) {
      current = { id: entry.kind === "user" ? entry.id : "preamble", entries: [] };
      groups.push(current);
    }
    current.entries.push(entry);
  }
  return groups;
}

export function processEntries(exchange: Exchange): ChatEntry[] {
  return exchange.entries.filter((entry) => isProcessKind(entry.kind));
}

export function contentEntries(exchange: Exchange): ChatEntry[] {
  return exchange.entries.filter((entry) => !isProcessKind(entry.kind));
}

export function friendlyToolName(tool: string): string {
  return FRIENDLY_TOOL_NAMES[tool] ?? tool;
}

export function activityLabel(entries: ChatEntry[]): string {
  for (let index = entries.length - 1; index >= 0; index--) {
    const entry = entries[index]!;
    if (entry.state !== "running") continue;
    if (entry.kind === "reasoning") {
      if (entry.title === "Progress") {
        const progress = entry.text.replace(/\s+/gu, " ").trim();
        if (progress) return progress.length > 120 ? `${progress.slice(0, 117)}…` : progress;
      }
      return "Thinking…";
    }
    if (entry.kind === "tool") return `Calling ${friendlyToolName(entry.title || "tool")}`;
    if (entry.kind === "command") return "Running command…";
    if (entry.kind === "assistant") return "Writing response…";
  }
  return "Thinking…";
}

export function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(1, Math.round(ms / 1000));
  if (totalSeconds < 60) return `${totalSeconds}s`;
  return `${Math.floor(totalSeconds / 60)}m ${totalSeconds % 60}s`;
}

export interface QaExchange {
  question: string;
  answerMarkdown: string;
  meta?: { completedAt?: string; model?: string; elapsedMs?: number };
}

export interface ExchangeMeta {
  elapsedMs?: number;
  completedAt?: string;
  model?: string;
}

/**
 * Turns raw chat entries into the Q&A pairs a note section is built from.
 * Groups without a completed assistant answer (dangling questions, or a
 * leading run of process entries with no user turn) are dropped. Groups
 * whose turn errored (a `kind: "error"` entry is present) are also dropped:
 * codex-service never marks an item `state: "failed"`, so a `kind: "error"`
 * entry is the only reliable signal that the turn's assistant text is a
 * partial answer, not a canonical one.
 */
export function buildQaFromEntries(
  entries: ChatEntry[],
  meta: ReadonlyMap<string, ExchangeMeta> | undefined,
): QaExchange[] {
  const exchanges: QaExchange[] = [];
  for (const group of groupEntries(entries)) {
    if (group.entries.some((entry) => entry.kind === "error")) continue;
    const userEntry = group.entries.find((entry) => entry.kind === "user");
    if (!userEntry) continue;
    const assistantEntries = contentEntries(group).filter((entry) => entry.kind === "assistant");
    if (!assistantEntries.length) continue;
    const answerMarkdown = assistantEntries.map((entry) => entry.text).join("\n\n");
    const exchangeMeta = meta?.get(userEntry.id);
    exchanges.push({
      question: userEntry.text,
      answerMarkdown,
      ...(exchangeMeta ? { meta: exchangeMeta } : {}),
    });
  }
  return exchanges;
}
