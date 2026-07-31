import { randomID } from "./platform";
import type { DiffReview } from "./sidebar";

export const NOTE_FROM_QMD_TOOL = "zotero_propose_note_from_qmd" as const;

export type DraftCategory = "theory" | "experiment" | "codes";
export type NoteDraftSyncState = "unlinked" | "in-sync" | "qmd-changed" | "note-changed" | "both-changed";

const ALLOWED_FRONTMATTER_KEYS = new Set(["title", "description", "categories", "aliases"]);
const DRAFT_CATEGORIES = new Set<DraftCategory>(["theory", "experiment", "codes"]);
const MAX_NOTE_HTML_CHARS = 2_000_000;

export interface QmdAuthorityIdentity {
  authority: "qmd";
  libraryID: number | string;
  noteKey: string;
  parentItemKey: string;
}

export interface NoteDraftLink {
  schemaVersion: 1;
  authority: "qmd";
  qmdPath: string;
  qmdSha256: string;
  zotero: {
    libraryID: number | string;
    noteKey: string;
    parentItemKey: string;
    version: number;
    /** SHA-256 of the exact persisted native-Note HTML. */
    contentSha256: string;
  };
  syncedAt: string;
}

export interface QmdSnapshot {
  source: string;
  sha256: string;
}

export interface ZoteroNoteSnapshot {
  html: string;
  title: string;
  parentItemKey: string;
  version: number;
  /** SHA-256 of `html`, computed by the Zotero host. */
  contentSha256: string;
}

export interface NoteWriteResult {
  noteKey: string;
  version: number;
}

export interface NoteDraftBridgeHost {
  readQmd(qmdPath: string): Promise<QmdSnapshot>;
  readNote(libraryID: number | string, noteKey: string): Promise<ZoteroNoteSnapshot>;
  readLink(qmdPath: string): Promise<NoteDraftLink | null>;
  writeLink(link: NoteDraftLink): Promise<void>;
  createNote(input: {
    libraryID: number | string;
    parentItemKey: string;
    title: string;
    html: string;
  }): Promise<NoteWriteResult>;
  updateNote(input: {
    libraryID: number | string;
    noteKey: string;
    parentItemKey: string;
    expectedVersion: number;
    title: string;
    html: string;
  }): Promise<NoteWriteResult>;
  /**
   * Narrow compensating operation used only after an accepted update was
   * written but its QMD/Note link could not be committed. The host must
   * restore the exact previous Note HTML and parent without re-rendering it.
   */
  restoreNote(input: {
    libraryID: number | string;
    noteKey: string;
    expectedVersion: number;
    title: string;
    html: string;
    parentItemKey: string;
  }): Promise<NoteWriteResult>;
  /** Used to remove a newly created Note if persisting the link fails. */
  deleteNote?(libraryID: number | string, noteKey: string): Promise<void>;
}

export interface NoteDraftBridgeCallbacks {
  onState(): void;
}

export interface NoteDraftToolSpec {
  type: "function";
  name: typeof NOTE_FROM_QMD_TOOL;
  description: string;
  inputSchema: Record<string, unknown>;
}

export type NoteDraftResolution =
  | { decision: "rejected" }
  | { decision: "accepted"; noteKey: string; version: number };

interface ParsedDraft {
  title: string;
  description: string;
  category: DraftCategory;
  body: string;
}

interface PendingNoteExport {
  id: string;
  createdAt: string;
  qmdPath: string;
  qmd: QmdSnapshot;
  title: string;
  html: string;
  mode: "create" | "update" | "bind";
  target: {
    libraryID: number | string;
    parentItemKey: string;
    noteKey?: string;
    noteVersion?: number;
    noteContentSha256?: string;
    noteSnapshot?: ZoteroNoteSnapshot;
  };
  link: NoteDraftLink | null;
  review: DiffReview;
}

export class NoteDraftConflictError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NoteDraftConflictError";
  }
}

/**
 * Produces an inert Markdown body from a native Zotero Note's HTML.
 *
 * Active nodes are removed before traversal; attributes are ignored except
 * for explicitly validated http(s)/mailto links and image alt text.
 */
export function noteHtmlToQmdBody(noteHtml: string): string {
  if (typeof noteHtml !== "string" || noteHtml.length > MAX_NOTE_HTML_CHARS) {
    throw new Error("The Zotero Note is missing or too large to import safely");
  }
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<!doctype html><html><body>${noteHtml}</body></html>`, "text/html");
  doc.querySelectorAll("script,style,iframe,object,embed,form,input,button,textarea,select,option,meta,link,base,svg,math")
    .forEach((node) => node.remove());
  const body = nodeChildrenToMarkdown(doc.body, 0)
    .replace(/[ \t]+\n/gu, "\n")
    .replace(/\n{3,}/gu, "\n\n")
    .trim();
  return body;
}

/** Build a compliant, untrusted Draft from a native Note. */
export function buildQmdDraftFromNote(input: {
  title: string;
  description: string;
  category: DraftCategory;
  noteHtml: string;
  identity: Omit<QmdAuthorityIdentity, "authority">;
}): string {
  const title = normalizedScalar(input.title, "title");
  const description = normalizedScalar(input.description, "description");
  if (!DRAFT_CATEGORIES.has(input.category)) {
    throw new Error("Draft category must be theory, experiment, or codes");
  }
  const marker = qmdAuthorityMarker({ authority: "qmd", ...input.identity });
  const body = noteHtmlToQmdBody(input.noteHtml);
  return [
    "---",
    `title: ${JSON.stringify(title)}`,
    `description: ${JSON.stringify(description)}`,
    `categories: [${input.category}]`,
    "---",
    "",
    marker,
    "",
    body,
    "",
  ].join("\n");
}

/** Render a strict QMD Draft into inert native-Note HTML. QMD remains authoritative. */
export function qmdToSafeNoteHtml(source: string, options: { qmdPath: string }): string {
  const qmdPath = validateDraftPath(options.qmdPath);
  const draft = parseStrictDraft(source);
  const body = stripQmdAuthorityMarker(draft.body);
  const rendered = qmdBodyToHtml(body);
  const backlink = safeHtmlComment("qlab-qmd-draft", { authority: "qmd", qmdPath });
  return `${rendered}\n${backlink}`.trim();
}

export function parseQmdAuthorityMarker(source: string): QmdAuthorityIdentity | null {
  const match = /<!--\s*qlab-zotero-note:\s*(\{[^\r\n]*\})\s*-->/u.exec(source);
  if (!match?.[1]) return null;
  try {
    const value = JSON.parse(match[1]) as unknown;
    if (!isRecord(value) || value.authority !== "qmd") return null;
    const libraryID = readLibraryID(value.libraryID);
    const noteKey = readKey(value.noteKey, "noteKey");
    const parentItemKey = readKey(value.parentItemKey, "parentItemKey");
    return { authority: "qmd", libraryID, noteKey, parentItemKey };
  }
  catch {
    return null;
  }
}

export function classifyNoteDraftSync(
  link: NoteDraftLink | null,
  currentQmdSha256: string,
  currentNoteVersion: number,
  currentNoteContentSha256: string,
): NoteDraftSyncState {
  if (!link) return "unlinked";
  const qmdChanged = currentQmdSha256 !== link.qmdSha256;
  const noteChanged = currentNoteVersion !== link.zotero.version
    || currentNoteContentSha256 !== link.zotero.contentSha256;
  if (qmdChanged && noteChanged) return "both-changed";
  if (qmdChanged) return "qmd-changed";
  if (noteChanged) return "note-changed";
  return "in-sync";
}

/** Review-gated QMD -> native Zotero Note export. */
export class NoteDraftBridgeService {
  readonly tools: readonly NoteDraftToolSpec[] = [NOTE_FROM_QMD_TOOL_SPEC];

  private readonly pending = new Map<string, PendingNoteExport>();
  private resolveQueue: Promise<unknown> = Promise.resolve();

  constructor(
    private readonly host: NoteDraftBridgeHost,
    private readonly callbacks: NoteDraftBridgeCallbacks,
    private readonly now: () => Date = () => new Date(),
    private readonly idFactory: (prefix: string) => string = randomID,
  ) {}

  getReviews(): DiffReview[] {
    return [...this.pending.values()]
      .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
      .map((entry) => ({ ...entry.review }));
  }

  async invokeTool(tool: string, rawArguments: Record<string, unknown>): Promise<Record<string, unknown>> {
    if (tool !== NOTE_FROM_QMD_TOOL) throw new Error(`Unknown Zotero Note tool: ${tool}`);
    const qmdPath = validateDraftPath(rawArguments.qmdPath);
    const qmd = validateQmdSnapshot(await this.host.readQmd(qmdPath));
    const parsed = parseStrictDraft(qmd.source);
    const html = qmdToSafeNoteHtml(qmd.source, { qmdPath });
    const link = await this.host.readLink(qmdPath);
    const embeddedIdentity = parseQmdAuthorityMarker(qmd.source);

    let mode: PendingNoteExport["mode"];
    let target: PendingNoteExport["target"];
    if (link) {
      validateLink(link, qmdPath);
      const note = validateNoteSnapshot(await this.host.readNote(link.zotero.libraryID, link.zotero.noteKey));
      assertNoteIdentity(note, link.zotero.parentItemKey);
      const sync = classifyNoteDraftSync(link, qmd.sha256, note.version, note.contentSha256);
      if (sync === "both-changed") {
        throw new NoteDraftConflictError("Both the QMD Draft and the Zotero Note changed. Choose an import or export direction before continuing.");
      }
      if (sync === "note-changed") {
        throw new NoteDraftConflictError("The Zotero Note changed after the last QMD export. Import it into a Draft working copy or resolve the conflict first.");
      }
      if (sync === "in-sync") {
        return { status: "already_in_sync", qmdPath, noteKey: link.zotero.noteKey };
      }
      mode = "update";
      target = {
        libraryID: link.zotero.libraryID,
        parentItemKey: link.zotero.parentItemKey,
        noteKey: link.zotero.noteKey,
        noteVersion: note.version,
        noteContentSha256: note.contentSha256,
        noteSnapshot: note,
      };
    }
    else if (embeddedIdentity) {
      const note = validateNoteSnapshot(await this.host.readNote(
        embeddedIdentity.libraryID,
        embeddedIdentity.noteKey,
      ));
      assertNoteIdentity(note, embeddedIdentity.parentItemKey);
      mode = "bind";
      target = {
        libraryID: embeddedIdentity.libraryID,
        parentItemKey: embeddedIdentity.parentItemKey,
        noteKey: embeddedIdentity.noteKey,
        noteVersion: note.version,
        noteContentSha256: note.contentSha256,
        noteSnapshot: note,
      };
    }
    else {
      mode = "create";
      target = {
        libraryID: readLibraryID(rawArguments.libraryID),
        parentItemKey: readKey(rawArguments.parentItemKey, "parentItemKey"),
      };
    }

    const id = this.idFactory("note-review");
    const createdAt = this.now().toISOString();
    const review: DiffReview = {
      id,
      title: readReviewTitle(rawArguments.title, mode),
      summary: mode === "create"
        ? "Create a native Zotero Note mirror from the authoritative QMD Draft"
        : mode === "bind"
          ? "Link this imported QMD Draft to its existing source Zotero Note"
          : "Update the linked Zotero Note mirror from the authoritative QMD Draft",
      diff: buildNoteDiff(mode, qmdPath, parsed, html, target),
      state: "pending",
    };
    this.pending.set(id, {
      id, createdAt, qmdPath, qmd, title: parsed.title, html, mode, target, link, review,
    });
    this.callbacks.onState();
    return {
      status: "awaiting_user_review",
      reviewId: id,
      message: "The Zotero Note mirror has not been written. The user must accept this review.",
      diff: review.diff,
    };
  }

  async resolveReview(reviewId: string, decision: "accept" | "reject"): Promise<NoteDraftResolution> {
    const pending = this.pending.get(reviewId);
    if (!pending) throw new Error("This Zotero Note review has expired");
    if (pending.review.state !== "pending") {
      throw new Error("This Zotero Note review was already resolved or is being applied");
    }
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
    pending: PendingNoteExport,
    decision: "accept" | "reject",
  ): Promise<NoteDraftResolution> {
    if (decision === "reject") {
      pending.review.state = "rejected";
      pending.review.summary = "The Note export was rejected; Zotero was not changed.";
      this.callbacks.onState();
      return { decision: "rejected" };
    }
    try {
      const qmd = validateQmdSnapshot(await this.host.readQmd(pending.qmdPath));
      if (qmd.sha256 !== pending.qmd.sha256 || qmd.source !== pending.qmd.source) {
        throw new Error("The QMD Draft changed after this review was prepared");
      }

      let written: NoteWriteResult;
      let persistedNote: ZoteroNoteSnapshot;
      if (pending.mode === "bind") {
        const noteKey = pending.target.noteKey!;
        const currentLink = await this.host.readLink(pending.qmdPath);
        if (currentLink) {
          throw new Error("The QMD-to-Note link changed after this review was prepared");
        }
        const marker = parseQmdAuthorityMarker(qmd.source);
        if (!marker || markerFingerprint(marker) !== markerFingerprint({
          authority: "qmd",
          libraryID: pending.target.libraryID,
          noteKey,
          parentItemKey: pending.target.parentItemKey,
        })) {
          throw new Error("The QMD Draft source-Note marker changed after this review was prepared");
        }
        persistedNote = validateNoteSnapshot(await this.host.readNote(pending.target.libraryID, noteKey));
        assertNoteUnchanged(persistedNote, pending.target);
        written = { noteKey, version: persistedNote.version };
      }
      else if (pending.mode === "update") {
        const noteKey = pending.target.noteKey!;
        const expectedVersion = pending.target.noteVersion!;
        const currentLink = await this.host.readLink(pending.qmdPath);
        if (!currentLink || linkFingerprint(currentLink) !== linkFingerprint(pending.link!)) {
          throw new Error("The QMD-to-Note link changed after this review was prepared");
        }
        const note = validateNoteSnapshot(await this.host.readNote(pending.target.libraryID, noteKey));
        assertNoteUnchanged(note, pending.target);
        written = validateWriteResult(await this.host.updateNote({
          libraryID: pending.target.libraryID,
          noteKey,
          parentItemKey: pending.target.parentItemKey,
          expectedVersion,
          title: pending.title,
          html: pending.html,
        }));
        if (written.noteKey !== noteKey) throw new Error("Zotero returned a different Note key while updating");
        try {
          persistedNote = validateNoteSnapshot(await this.host.readNote(pending.target.libraryID, noteKey));
          assertWrittenNote(persistedNote, written, pending.target.parentItemKey);
        }
        catch (error) {
          await this.rollbackUpdatedNote(pending, written, error);
          throw error;
        }
      }
      else {
        written = validateWriteResult(await this.host.createNote({
          libraryID: pending.target.libraryID,
          parentItemKey: pending.target.parentItemKey,
          title: pending.title,
          html: pending.html,
        }));
        try {
          persistedNote = validateNoteSnapshot(await this.host.readNote(pending.target.libraryID, written.noteKey));
          assertWrittenNote(persistedNote, written, pending.target.parentItemKey);
        }
        catch (error) {
          await this.rollbackCreatedNote(pending, written, error);
          throw error;
        }
      }

      const nextLink: NoteDraftLink = {
        schemaVersion: 1,
        authority: "qmd",
        qmdPath: pending.qmdPath,
        qmdSha256: pending.qmd.sha256,
        zotero: {
          libraryID: pending.target.libraryID,
          noteKey: written.noteKey,
          parentItemKey: pending.target.parentItemKey,
          version: written.version,
          contentSha256: persistedNote.contentSha256,
        },
        syncedAt: this.now().toISOString(),
      };
      try {
        await this.host.writeLink(nextLink);
      }
      catch (error) {
        if (pending.mode === "create") await this.rollbackCreatedNote(pending, written, error);
        if (pending.mode === "update") await this.rollbackUpdatedNote(pending, written, error);
        throw error;
      }

      pending.review.state = "accepted";
      pending.review.summary = pending.mode === "bind"
        ? "The QMD Draft is now linked to its existing source Zotero Note; QMD remains authoritative."
        : "The native Zotero Note mirror now matches the authoritative QMD Draft.";
      this.callbacks.onState();
      return { decision: "accepted", noteKey: written.noteKey, version: written.version };
    }
    catch (error) {
      pending.review.state = "failed";
      pending.review.summary = "The Note export failed. Generate a fresh review after resolving the reported revision conflict.";
      this.callbacks.onState();
      throw error;
    }
  }

  private async rollbackCreatedNote(
    pending: PendingNoteExport,
    written: NoteWriteResult,
    cause: unknown,
  ): Promise<void> {
    if (!this.host.deleteNote) return;
    try {
      await this.host.deleteNote(pending.target.libraryID, written.noteKey);
    }
    catch (rollbackError) {
      throw new Error(
        `Could not save the QMD/Note link, and deleting the new Note also failed: ${describeError(rollbackError)}`,
        { cause },
      );
    }
  }

  private async rollbackUpdatedNote(
    pending: PendingNoteExport,
    written: NoteWriteResult,
    cause: unknown,
  ): Promise<void> {
    const previous = pending.target.noteSnapshot;
    if (!previous || !pending.target.noteKey) {
      throw new Error("Could not restore the previous Zotero Note snapshot", { cause });
    }
    try {
      const restored = validateWriteResult(await this.host.restoreNote({
        libraryID: pending.target.libraryID,
        noteKey: pending.target.noteKey,
        expectedVersion: written.version,
        title: previous.title,
        html: previous.html,
        parentItemKey: previous.parentItemKey,
      }));
      if (restored.noteKey !== pending.target.noteKey) {
        throw new Error("Zotero returned a different Note key while restoring");
      }
      if (pending.link) {
        await this.host.writeLink({
          ...pending.link,
          zotero: {
            ...pending.link.zotero,
            version: restored.version,
            contentSha256: previous.contentSha256,
          },
        });
      }
    }
    catch (rollbackError) {
      throw new Error(
        `Could not save the QMD/Note link, and restoring the previous Note also failed: ${describeError(rollbackError)}`,
        { cause },
      );
    }
  }
}

export const NOTE_FROM_QMD_TOOL_SPEC: NoteDraftToolSpec = {
  type: "function",
  name: NOTE_FROM_QMD_TOOL,
  description: "Propose a reviewed export of an authoritative QMD Draft to a native Zotero Note mirror.",
  inputSchema: {
    type: "object",
    additionalProperties: false,
    required: ["qmdPath"],
    properties: {
      qmdPath: { type: "string", pattern: "^drafts/(?!.*(?:^|/)\\.\\.?/).+\\.qmd$" },
      libraryID: { anyOf: [{ type: "number" }, { type: "string" }] },
      parentItemKey: { type: "string", minLength: 1, maxLength: 200 },
      title: { type: "string", maxLength: 160 },
    },
  },
};

function parseStrictDraft(source: string): ParsedDraft {
  const normalized = source.replace(/\r\n?/gu, "\n");
  if (!normalized.startsWith("---\n")) throw new Error("QMD Draft is missing YAML frontmatter");
  const end = normalized.indexOf("\n---\n", 4);
  if (end < 0) throw new Error("QMD Draft frontmatter is not closed");
  const values = new Map<string, string>();
  const sequences = new Map<string, string[]>();
  const keys: string[] = [];
  let activeSequence: string | null = null;
  for (const rawLine of normalized.slice(4, end).split("\n")) {
    if (!rawLine.trim() || /^\s*#/u.test(rawLine)) continue;
    const match = /^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$/u.exec(rawLine);
    if (!match) {
      if (!activeSequence) throw new Error("QMD Draft frontmatter contains an unsupported nested value");
      const item = /^\s+-\s+(.+)$/u.exec(rawLine);
      if (!item) throw new Error("QMD Draft frontmatter contains an unsupported nested value");
      sequences.get(activeSequence)!.push(item[1]!.trim());
      continue;
    }
    const key = match[1]!;
    if (!ALLOWED_FRONTMATTER_KEYS.has(key)) throw new Error(`Unsupported QMD Draft frontmatter key: ${key}`);
    if (values.has(key) || sequences.has(key)) throw new Error(`Duplicate QMD Draft frontmatter key: ${key}`);
    keys.push(key);
    const scalar = match[2]!.trim();
    if (!scalar && (key === "categories" || key === "aliases")) {
      sequences.set(key, []);
      activeSequence = key;
    }
    else {
      values.set(key, scalar);
      activeSequence = null;
    }
  }
  const expectedKeys = ["title", "description", "categories", ...(keys.includes("aliases") ? ["aliases"] : [])];
  if (keys.join("\u0000") !== expectedKeys.join("\u0000")) {
    throw new Error("QMD Draft frontmatter must contain title, description, categories, and optional aliases in that order");
  }
  const title = parseYamlScalar(values.get("title"), "title");
  const description = parseYamlScalar(values.get("description"), "description");
  const categoryValue = values.get("categories");
  const inlineCategory = categoryValue && /^\[\s*(theory|experiment|codes)\s*\]$/u.exec(categoryValue)?.[1];
  const sequenceCategories = sequences.get("categories") ?? [];
  const category = inlineCategory ?? (sequenceCategories.length === 1 ? sequenceCategories[0] : undefined);
  if (!category || !DRAFT_CATEGORIES.has(category as DraftCategory)) {
    throw new Error("QMD Draft categories must contain exactly one of theory, experiment, or codes");
  }
  return {
    title,
    description,
    category: category as DraftCategory,
    body: normalized.slice(end + "\n---\n".length),
  };
}

function parseYamlScalar(value: string | undefined, field: string): string {
  if (!value) throw new Error(`QMD Draft frontmatter requires ${field}`);
  let parsed = value;
  if (value.startsWith('"')) {
    try {
      const candidate = JSON.parse(value) as unknown;
      if (typeof candidate !== "string") throw new Error("not a string");
      parsed = candidate;
    }
    catch {
      throw new Error(`QMD Draft ${field} must be a valid string`);
    }
  }
  else if (value.startsWith("'") && value.endsWith("'")) {
    parsed = value.slice(1, -1).replace(/''/gu, "'");
  }
  return normalizedScalar(parsed, field);
}

function normalizedScalar(value: string, field: string): string {
  const normalized = value.replace(/[\u0000-\u001F\u007F]/gu, " ").replace(/\s+/gu, " ").trim();
  if (!normalized) throw new Error(`${field} must not be empty`);
  if (normalized.length > 1_000) throw new Error(`${field} is too long`);
  return normalized;
}

export function qmdAuthorityMarker(identity: QmdAuthorityIdentity): string {
  const safe: QmdAuthorityIdentity = {
    authority: "qmd",
    libraryID: readLibraryID(identity.libraryID),
    noteKey: readKey(identity.noteKey, "noteKey"),
    parentItemKey: readKey(identity.parentItemKey, "parentItemKey"),
  };
  return safeHtmlComment("qlab-zotero-note", safe);
}

function stripQmdAuthorityMarker(body: string): string {
  return body.replace(/<!--\s*qlab-zotero-note:\s*\{[^\r\n]*\}\s*-->\s*/gu, "");
}

function safeHtmlComment(label: string, value: object): string {
  const json = JSON.stringify(value).replace(/--/gu, "\\u002d\\u002d").replace(/>/gu, "\\u003e");
  return `<!-- ${label}: ${json} -->`;
}

function qmdBodyToHtml(body: string): string {
  const lines = body.replace(/\r\n?/gu, "\n").split("\n");
  const output: string[] = [];
  let paragraph: string[] = [];
  let list: "ul" | "ol" | null = null;
  let codeFence: { marker: string; lines: string[] } | null = null;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    output.push(`<p>${inlineQmdToHtml(paragraph.join(" "))}</p>`);
    paragraph = [];
  };
  const closeList = () => {
    if (!list) return;
    output.push(`</${list}>`);
    list = null;
  };

  for (const line of lines) {
    if (codeFence) {
      if (line.trim().startsWith(codeFence.marker)) {
        output.push(`<pre><code>${escapeHtml(codeFence.lines.join("\n"))}</code></pre>`);
        codeFence = null;
      }
      else codeFence.lines.push(line);
      continue;
    }
    const fence = /^\s*(```+|~~~+)/u.exec(line);
    if (fence) {
      flushParagraph(); closeList();
      codeFence = { marker: fence[1]![0]!.repeat(3), lines: [] };
      continue;
    }
    const heading = /^(#{1,6})\s+(.+)$/u.exec(line);
    if (heading) {
      flushParagraph(); closeList();
      const level = heading[1]!.length;
      output.push(`<h${level}>${inlineQmdToHtml(heading[2]!)}</h${level}>`);
      continue;
    }
    const unordered = /^\s*[-*+]\s+(.+)$/u.exec(line);
    const ordered = /^\s*\d+[.)]\s+(.+)$/u.exec(line);
    if (unordered || ordered) {
      flushParagraph();
      const kind = unordered ? "ul" : "ol";
      if (list !== kind) { closeList(); output.push(`<${kind}>`); list = kind; }
      output.push(`<li>${inlineQmdToHtml((unordered ?? ordered)![1]!)}</li>`);
      continue;
    }
    if (!line.trim()) {
      flushParagraph(); closeList();
      continue;
    }
    paragraph.push(line.trim());
  }
  if (codeFence) output.push(`<pre><code>${escapeHtml(codeFence.lines.join("\n"))}</code></pre>`);
  flushParagraph(); closeList();
  return output.join("\n");
}

function inlineQmdToHtml(value: string): string {
  // Escape first: raw HTML in a Draft is always displayed as inert text in
  // the Note mirror. Then add only this deliberately small formatting set.
  return escapeHtml(value)
    .replace(/`([^`]+)`/gu, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/gu, "<strong>$1</strong>")
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/gu, "<em>$1</em>");
}

function nodeChildrenToMarkdown(node: Node, depth: number): string {
  return [...node.childNodes].map((child) => nodeToMarkdown(child, depth)).join("");
}

function nodeToMarkdown(node: Node, depth: number): string {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? "";
  if (node.nodeType !== Node.ELEMENT_NODE) return "";
  const element = node as Element;
  const tag = element.tagName.toLowerCase();
  const children = () => nodeChildrenToMarkdown(element, depth + 1).trim();
  if (/^h[1-6]$/u.test(tag)) return `${"#".repeat(Number(tag[1]))} ${children()}\n\n`;
  if (["p", "div", "section", "article", "header", "footer"].includes(tag)) return `${children()}\n\n`;
  if (tag === "br") return "\n";
  if (tag === "strong" || tag === "b") return `**${children()}**`;
  if (tag === "em" || tag === "i") return `*${children()}*`;
  if (tag === "code" && element.parentElement?.tagName.toLowerCase() !== "pre") return `\`${children().replace(/`/gu, "\\`")}\``;
  if (tag === "pre") return `\n\`\`\`\n${element.textContent ?? ""}\n\`\`\`\n\n`;
  if (tag === "blockquote") return `${children().split("\n").map((line) => `> ${line}`).join("\n")}\n\n`;
  if (tag === "ul" || tag === "ol") return `${nodeChildrenToMarkdown(element, depth)}\n`;
  if (tag === "li") {
    const ordered = element.parentElement?.tagName.toLowerCase() === "ol";
    return `${"  ".repeat(Math.max(0, depth - 2))}${ordered ? "1." : "-"} ${children()}\n`;
  }
  if (tag === "a") {
    const label = children();
    const href = safeLink(element.getAttribute("href"));
    return href ? `[${label}](${href})` : label;
  }
  if (tag === "img") return element.getAttribute("alt")?.trim() || "";
  return nodeChildrenToMarkdown(element, depth);
}

function safeLink(value: string | null): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!/^(https?:|mailto:)/iu.test(trimmed)) return null;
  return trimmed.replace(/[\s()]/gu, (character) => encodeURIComponent(character));
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/gu, "&amp;")
    .replace(/</gu, "&lt;")
    .replace(/>/gu, "&gt;")
    .replace(/"/gu, "&quot;")
    .replace(/'/gu, "&#39;");
}

function validateDraftPath(value: unknown): string {
  if (typeof value !== "string") throw new Error("qmdPath must identify a safe Draft");
  const normalized = value.replace(/\\/gu, "/").replace(/^\.\//u, "");
  const parts = normalized.split("/");
  if (!normalized.startsWith("drafts/")
      || !normalized.endsWith(".qmd")
      || parts.some((part) => !part || part === "." || part === ".." || part.startsWith("."))) {
    throw new Error("qmdPath must identify a safe Draft .qmd file below drafts/");
  }
  return normalized;
}

function validateQmdSnapshot(value: QmdSnapshot): QmdSnapshot {
  if (!value || typeof value.source !== "string" || !value.source || typeof value.sha256 !== "string" || !value.sha256) {
    throw new Error("The QMD Draft could not be read or fingerprinted");
  }
  return { source: value.source, sha256: value.sha256 };
}

function validateNoteSnapshot(value: ZoteroNoteSnapshot): ZoteroNoteSnapshot {
  if (!value
      || typeof value.html !== "string"
      || typeof value.title !== "string"
      || !Number.isSafeInteger(value.version)
      || value.version < 0
      || typeof value.contentSha256 !== "string"
      || !value.contentSha256.trim()) {
    throw new Error("The linked Zotero Note could not be read safely");
  }
  return {
    html: value.html,
    title: value.title,
    parentItemKey: readKey(value.parentItemKey, "parentItemKey"),
    version: value.version,
    contentSha256: value.contentSha256.trim(),
  };
}

function validateWriteResult(value: NoteWriteResult): NoteWriteResult {
  return {
    noteKey: readKey(value?.noteKey, "noteKey"),
    version: readVersion(value?.version),
  };
}

function validateLink(link: NoteDraftLink, qmdPath: string): void {
  if (link.schemaVersion !== 1 || link.authority !== "qmd" || link.qmdPath !== qmdPath) {
    throw new Error("The QMD-to-Zotero Note link is invalid");
  }
  readLibraryID(link.zotero.libraryID);
  readKey(link.zotero.noteKey, "noteKey");
  readKey(link.zotero.parentItemKey, "parentItemKey");
  readVersion(link.zotero.version);
  if (typeof link.zotero.contentSha256 !== "string" || !link.zotero.contentSha256.trim()) {
    throw new Error("The QMD-to-Zotero Note link has no Note content fingerprint");
  }
  if (!link.qmdSha256) throw new Error("The QMD-to-Zotero Note link has no QMD fingerprint");
}

function readLibraryID(value: unknown): number | string {
  if (typeof value === "number" && Number.isSafeInteger(value) && value >= 0) return value;
  if (typeof value === "string" && value.trim() && value.length <= 200) return value.trim();
  throw new Error("libraryID must be a non-negative integer or non-empty string");
}

function readKey(value: unknown, field: string): string {
  if (typeof value !== "string" || !/^[A-Za-z0-9._:-]{1,200}$/u.test(value.trim())) {
    throw new Error(`${field} is invalid`);
  }
  return value.trim();
}

function readVersion(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new Error("Zotero Note version is invalid");
  }
  return value;
}

function readReviewTitle(value: unknown, mode: "create" | "update" | "bind"): string {
  if (typeof value === "string" && value.trim()) return sanitizeDiff(value.trim().slice(0, 160));
  if (mode === "create") return "Create Zotero Note from QMD Draft";
  if (mode === "bind") return "Link QMD Draft to Existing Zotero Note";
  return "Update Zotero Note from QMD Draft";
}

function buildNoteDiff(
  mode: "create" | "update" | "bind",
  qmdPath: string,
  parsed: ParsedDraft,
  html: string,
  target: PendingNoteExport["target"],
): string {
  const plainPreview = noteHtmlToQmdBody(html).slice(0, 2_000);
  return [
    mode === "create"
      ? "+ Create native Zotero Note"
      : mode === "bind"
        ? "= Link existing Zotero Note (no Note content will be changed)"
        : "~ Update native Zotero Note",
    `  Authoritative Draft: ${sanitizeDiff(qmdPath)}`,
    `  Zotero parent: ${sanitizeDiff(String(target.parentItemKey))}`,
    `  Title: ${sanitizeDiff(parsed.title)}`,
    `  Category: ${parsed.category}`,
    "",
    ...plainPreview.split("\n").map((line) => `+ ${sanitizeDiff(line)}`),
  ].join("\n").trimEnd();
}

function linkFingerprint(link: NoteDraftLink): string {
  return JSON.stringify(link);
}

function markerFingerprint(marker: QmdAuthorityIdentity): string {
  return JSON.stringify({
    authority: marker.authority,
    libraryID: String(marker.libraryID),
    noteKey: marker.noteKey,
    parentItemKey: marker.parentItemKey,
  });
}

function assertNoteIdentity(note: ZoteroNoteSnapshot, parentItemKey: string): void {
  if (note.parentItemKey !== parentItemKey) {
    throw new NoteDraftConflictError("The Zotero Note parent changed after this QMD Draft was linked");
  }
}

function assertNoteUnchanged(
  note: ZoteroNoteSnapshot,
  target: PendingNoteExport["target"],
): void {
  if (note.version !== target.noteVersion
      || note.contentSha256 !== target.noteContentSha256
      || note.parentItemKey !== target.parentItemKey) {
    throw new Error("The Zotero Note changed after this review was prepared");
  }
}

function assertWrittenNote(
  note: ZoteroNoteSnapshot,
  written: NoteWriteResult,
  expectedParentItemKey: string,
): void {
  if (note.version !== written.version || note.parentItemKey !== expectedParentItemKey) {
    throw new Error("Zotero could not verify the Note that was just written");
  }
}

function sanitizeDiff(value: string): string {
  return value
    .replace(/[\u0000-\u001F\u007F-\u009F\u202A-\u202E\u2066-\u2069]/gu, " ")
    .replace(/[ \t]+/gu, " ")
    .trim();
}

function describeError(error: unknown): string {
  return sanitizeDiff(error instanceof Error ? error.message : String(error)).slice(0, 500) || "unknown error";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
