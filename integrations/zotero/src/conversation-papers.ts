export type ConversationPaperMode = "retrieval" | "full";

export interface ConversationPaper {
  id: string;
  libraryID: string;
  attachmentKey: string;
  attachmentID?: string;
  itemKey?: string;
  title: string;
  pdfPath?: string;
  textPath?: string;
  sourceUrls?: string[];
  dois?: string[];
  mode: ConversationPaperMode;
}

interface ConversationPaperFile {
  version: 1;
  threads: Record<string, ConversationPaper[]>;
}

/** Keeps explicit secondary-paper attachments scoped to their conversation. */
export class ConversationPaperRegistry {
  private readonly threads = new Map<string, ConversationPaper[]>();

  constructor(private readonly maximumPerThread = 8) {}

  list(threadID: string): ConversationPaper[] {
    return (this.threads.get(threadID) || []).map((paper) => ({ ...paper }));
  }

  add(threadID: string, paper: ConversationPaper): ConversationPaper[] {
    if (!threadID) throw new Error("A conversation is required before attaching another paper");
    const current = this.threads.get(threadID) || [];
    const existing = current.findIndex((entry) => entry.id === paper.id);
    const next = [...current];
    if (existing >= 0) next[existing] = { ...paper };
    else {
      if (next.length >= this.maximumPerThread) {
        throw new Error(`A conversation can attach at most ${this.maximumPerThread} papers`);
      }
      next.push({ ...paper });
    }
    this.threads.set(threadID, next);
    return this.list(threadID);
  }

  remove(threadID: string, paperID: string): ConversationPaper[] {
    const next = (this.threads.get(threadID) || []).filter((paper) => paper.id !== paperID);
    if (next.length) this.threads.set(threadID, next);
    else this.threads.delete(threadID);
    return this.list(threadID);
  }

  toggleMode(threadID: string, paperID: string): ConversationPaper | null {
    const papers = this.threads.get(threadID) || [];
    const paper = papers.find((entry) => entry.id === paperID);
    if (!paper) return null;
    paper.mode = paper.mode === "retrieval" ? "full" : "retrieval";
    return { ...paper };
  }

  serialize(): string {
    return JSON.stringify({
      version: 1,
      threads: Object.fromEntries(this.threads),
    } satisfies ConversationPaperFile, null, 2) + "\n";
  }

  restore(value: unknown): void {
    this.threads.clear();
    if (!value || typeof value !== "object") return;
    const file = value as Partial<ConversationPaperFile>;
    if (file.version !== 1 || !file.threads || typeof file.threads !== "object") return;
    for (const [threadID, raw] of Object.entries(file.threads)) {
      if (!threadID || !Array.isArray(raw)) continue;
      const papers = raw.filter(isConversationPaper).slice(0, this.maximumPerThread);
      if (papers.length) this.threads.set(threadID, papers.map((paper) => ({ ...paper })));
    }
  }
}

function isConversationPaper(value: unknown): value is ConversationPaper {
  if (!value || typeof value !== "object") return false;
  const paper = value as Partial<ConversationPaper>;
  return typeof paper.id === "string"
    && typeof paper.libraryID === "string"
    && typeof paper.attachmentKey === "string"
    && typeof paper.title === "string"
    && (paper.mode === "retrieval" || paper.mode === "full");
}
