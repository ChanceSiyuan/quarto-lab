export const AI_CONTEXT_MAX_SOURCE_BYTES = 2_000_000;
export const AI_CONTEXT_MAX_UTILITY_INPUT_CHARS = 80_000;
export const AI_CONTEXT_MAX_UTILITY_OUTPUT_CHARS = 64_000;
export const AI_CONTEXT_MAX_REOPEN_CHARS = 32_000;
export const AI_CONTEXT_MANAGED_START = "<!-- qlab-ai-context-managed:start -->";
export const AI_CONTEXT_MANAGED_END = "<!-- qlab-ai-context-managed:end -->";

export type AIContextKind = "conversation" | "reading";
export type AIContextStatus = "active" | "complete";
export type AIContextCategory = "theory" | "experiment" | "codes";

export interface AIContextPaper {
  libraryID: string;
  itemKey: string;
  title: string;
  attachmentKey?: string;
  creators?: string[];
  year?: string;
  abstract?: string;
}

export interface AIContextMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

export interface AIContextProjectionIntent {
  mode: "attached" | "standalone";
  targets: Array<{ libraryID: string; itemKey: string }>;
}

export interface AIContextManifest {
  schemaVersion: 1;
  id: string;
  contextKey: string;
  kind: AIContextKind;
  sourceThreadId: string | null;
  createdAt: string;
  updatedAt: string;
  status: AIContextStatus;
  papers: AIContextPaper[];
  projection: AIContextProjectionIntent;
  capturedEntryIds: string[];
}

export interface AIContextSynthesis {
  title: string;
  description: string;
  category: AIContextCategory;
  status: AIContextStatus;
  memoryMarkdown: string;
  progressMarkdown: string;
  nextStepMarkdown: string;
  readingPlan: Array<{ itemKey: string; rationale: string; guidance: string }>;
}

export interface AIContextManagedContent {
  manifest: AIContextManifest;
  synthesis: AIContextSynthesis;
  messages: AIContextMessage[];
}

export interface AIContextDocument {
  relativePath: string;
  manifest: AIContextManifest;
  title: string;
  description: string;
  category: AIContextCategory;
  synthesis: AIContextSynthesis;
  messages: AIContextMessage[];
  source: string;
}

const encoder = new TextEncoder();
const decoder = new TextDecoder("utf-8", { fatal: true });
const ID_PATTERN = /^[A-Za-z0-9._:-]{1,120}$/u;
const RECORD_ID_PATTERN = /^[A-Za-z0-9._-]{1,120}$/u;
const MANIFEST_PREFIX = "<!-- qlab-ai-context-manifest:v1:";
const SYNTHESIS_PREFIX = "<!-- qlab-ai-context-synthesis:v1:";
const MESSAGE_PREFIX = "<!-- qlab-ai-context-message:v1:";
const READING_PREFIX = "<!-- qlab-ai-context-reading:v1:";

function fail(category: "manifest" | "frontmatter" | "path" | "synthesis", detail: string): never {
  throw new Error(`${category}: ${detail}`);
}

function object(value: unknown, category: "manifest" | "synthesis"): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(category, "expected object");
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[], category: "manifest" | "synthesis"): void {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    fail(category, `expected keys ${expected.join(",")}; received ${actual.join(",")}`);
  }
}

function bounded(value: unknown, minimum: number, maximum: number, category: "manifest" | "synthesis", name: string): string {
  if (typeof value !== "string" || [...value].length < minimum || [...value].length > maximum) {
    fail(category, `${name} must contain ${minimum}..${maximum} characters`);
  }
  return value;
}

function id(value: unknown, name: string): string {
  if (typeof value !== "string" || !ID_PATTERN.test(value)) fail("manifest", `${name} is invalid`);
  return value;
}

function validatedRecordId(value: unknown): string {
  if (typeof value !== "string" || !RECORD_ID_PATTERN.test(value)) fail("manifest", "record ID is invalid");
  return value;
}

function identityKey(libraryID: string, itemKey: string): string {
  return JSON.stringify([libraryID, itemKey]);
}

function encode(value: unknown): string {
  let binary = "";
  for (const byte of encoder.encode(JSON.stringify(value))) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/gu, "-").replace(/\//gu, "_").replace(/=+$/u, "");
}

function decode(token: string, category: "manifest" | "synthesis"): unknown {
  if (!/^[A-Za-z0-9_-]+$/u.test(token) || token.includes("=")) fail(category, "invalid unpadded base64url");
  const padded = token.replace(/-/gu, "+").replace(/_/gu, "/") + "=".repeat((4 - token.length % 4) % 4);
  try {
    const bytes = Uint8Array.from(atob(padded), (character) => character.charCodeAt(0));
    const value: unknown = JSON.parse(decoder.decode(bytes));
    if (encode(value) !== token) fail(category, "noncanonical base64url");
    return value;
  }
  catch (error) {
    if (error instanceof Error && /^(manifest|synthesis):/u.test(error.message)) throw error;
    return fail(category, "invalid UTF-8 JSON");
  }
}

function validatePaper(value: unknown): AIContextPaper {
  const input = object(value, "manifest");
  const required = ["libraryID", "itemKey", "title"];
  const allowed = new Set([...required, "attachmentKey", "creators", "year", "abstract"]);
  for (const key of required) if (!Object.hasOwn(input, key)) fail("manifest", `paper misses ${key}`);
  for (const key of Object.keys(input)) if (!allowed.has(key)) fail("manifest", `paper has unknown ${key}`);
  const paper: AIContextPaper = {
    libraryID: id(input.libraryID, "libraryID"),
    itemKey: id(input.itemKey, "itemKey"),
    title: bounded(input.title, 1, 2_000, "manifest", "paper title"),
  };
  if (input.attachmentKey !== undefined) paper.attachmentKey = id(input.attachmentKey, "attachmentKey");
  if (input.year !== undefined) paper.year = bounded(input.year, 1, 20, "manifest", "year");
  if (input.abstract !== undefined) paper.abstract = bounded(input.abstract, 1, 20_000, "manifest", "abstract");
  if (input.creators !== undefined) {
    if (!Array.isArray(input.creators)) fail("manifest", "creators must be an array");
    paper.creators = input.creators.map((creator) => bounded(creator, 1, 500, "manifest", "creator"));
  }
  return paper;
}

function validateManifest(value: unknown): AIContextManifest {
  const input = object(value, "manifest");
  exactKeys(input, [
    "schemaVersion", "id", "contextKey", "kind", "sourceThreadId", "createdAt", "updatedAt",
    "status", "papers", "projection", "capturedEntryIds",
  ], "manifest");
  if (input.schemaVersion !== 1) fail("manifest", "unsupported schema version");
  if (input.kind !== "conversation" && input.kind !== "reading") fail("manifest", "invalid kind");
  if (input.status !== "active" && input.status !== "complete") fail("manifest", "invalid status");
  if (input.sourceThreadId !== null) id(input.sourceThreadId, "sourceThreadId");
  if (!Array.isArray(input.papers) || !Array.isArray(input.capturedEntryIds)) fail("manifest", "invalid arrays");
  const papers = input.papers.map(validatePaper);
  const projection = object(input.projection, "manifest");
  exactKeys(projection, ["mode", "targets"], "manifest");
  if (projection.mode !== "attached" && projection.mode !== "standalone") fail("manifest", "invalid projection mode");
  if (!Array.isArray(projection.targets)) fail("manifest", "projection targets must be an array");
  const targets = projection.targets.map((target) => {
    const parsed = object(target, "manifest");
    exactKeys(parsed, ["libraryID", "itemKey"], "manifest");
    return { libraryID: id(parsed.libraryID, "target libraryID"), itemKey: id(parsed.itemKey, "target itemKey") };
  });
  if (projection.mode === "standalone" && targets.length) fail("manifest", "standalone has parent targets");
  const capturedEntryIds = input.capturedEntryIds.map((entry) => id(entry, "captured entry ID"));
  if (new Set(capturedEntryIds).size !== capturedEntryIds.length) fail("manifest", "duplicate captured entry ID");
  const paperKeys = papers.map((paper) => identityKey(paper.libraryID, paper.itemKey));
  const targetKeys = targets.map((target) => identityKey(target.libraryID, target.itemKey));
  if (new Set(paperKeys).size !== paperKeys.length) fail("manifest", "duplicate paper identity");
  if (new Set(targetKeys).size !== targetKeys.length) fail("manifest", "duplicate projection target");
  const parsedRecordId = validatedRecordId(input.id);
  const parsedSourceThread = input.sourceThreadId as string | null;
  const parsedContextKey = id(input.contextKey, "contextKey");
  if (projection.mode === "attached") {
    if (papers.length < 1 || papers.length > 50
      || paperKeys.slice().sort().join("\0") !== targetKeys.slice().sort().join("\0")) {
      fail("manifest", "attached targets must match 1..50 papers exactly");
    }
  }
  else if (papers.length !== 0) fail("manifest", "standalone projection cannot contain papers");
  if (input.kind === "reading") {
    if (parsedSourceThread !== null || projection.mode !== "attached"
      || parsedContextKey !== `reading:${parsedRecordId}`) {
      fail("manifest", "invalid Reading Context identity");
    }
  }
  else if (projection.mode === "standalone") {
    if (parsedSourceThread === null || parsedContextKey !== `standalone:${parsedRecordId}`) {
      fail("manifest", "invalid standalone Context identity");
    }
  }
  else if (parsedSourceThread === null || parsedContextKey !== `conversation:${parsedSourceThread}`) {
    fail("manifest", "invalid conversation Context identity");
  }
  return {
    schemaVersion: 1,
    id: parsedRecordId,
    contextKey: parsedContextKey,
    kind: input.kind,
    sourceThreadId: input.sourceThreadId as string | null,
    createdAt: bounded(input.createdAt, 1, 80, "manifest", "createdAt"),
    updatedAt: bounded(input.updatedAt, 1, 80, "manifest", "updatedAt"),
    status: input.status,
    papers,
    projection: { mode: projection.mode, targets },
    capturedEntryIds,
  };
}

const OMITTED_RATIONALE = "No generated transition rationale was available; preserve the stable selection order.";
const OMITTED_GUIDANCE = "No generated guidance was available; inspect this paper directly and record evidence limits.";

export function validateAIContextSynthesis(value: unknown, papers: readonly AIContextPaper[]): AIContextSynthesis {
  const input = object(value, "synthesis");
  exactKeys(input, [
    "title", "description", "category", "status", "memoryMarkdown", "progressMarkdown",
    "nextStepMarkdown", "readingPlan",
  ], "synthesis");
  const title = bounded(input.title, 1, 120, "synthesis", "title");
  if (/^(AI Context|Reading Context)\s*·/u.test(title)) fail("synthesis", "title includes product prefix");
  if (input.category !== "theory" && input.category !== "experiment" && input.category !== "codes") fail("synthesis", "invalid category");
  if (input.status !== "active" && input.status !== "complete") fail("synthesis", "invalid status");
  if (!Array.isArray(input.readingPlan)) fail("synthesis", "readingPlan must be an array");
  const readingPlan = input.readingPlan.map((entry) => {
    const parsed = object(entry, "synthesis");
    exactKeys(parsed, ["itemKey", "rationale", "guidance"], "synthesis");
    return {
      itemKey: id(parsed.itemKey, "reading itemKey"),
      rationale: bounded(parsed.rationale, 1, 2_000, "synthesis", "rationale"),
      guidance: bounded(parsed.guidance, 1, 2_000, "synthesis", "guidance"),
    };
  });
  const selected = papers.map(({ itemKey }) => itemKey);
  const generated = readingPlan.map(({ itemKey }) => itemKey);
  if (new Set(generated).size !== generated.length) fail("synthesis", "duplicate reading paper");
  if (generated.some((itemKey) => !selected.includes(itemKey))) fail("synthesis", "unknown reading paper");
  for (const itemKey of selected) {
    if (!generated.includes(itemKey)) readingPlan.push({ itemKey, rationale: OMITTED_RATIONALE, guidance: OMITTED_GUIDANCE });
  }
  return {
    title,
    description: bounded(input.description, 1, 500, "synthesis", "description"),
    category: input.category,
    status: input.status,
    memoryMarkdown: bounded(input.memoryMarkdown, 1, 48_000, "synthesis", "memory"),
    progressMarkdown: bounded(input.progressMarkdown, 1, 8_000, "synthesis", "progress"),
    nextStepMarkdown: bounded(input.nextStepMarkdown, 1, 8_000, "synthesis", "next step"),
    readingPlan,
  };
}

function safeMarkdown(value: string): string {
  return value.replace(/&/gu, "&amp;").replace(/</gu, "&lt;").replace(/>/gu, "&gt;");
}

function fenceFor(text: string): string {
  let longest = 0;
  let run = 0;
  for (const character of text) {
    if (character === "`") run += 1;
    else {
      longest = Math.max(longest, run);
      run = 0;
    }
  }
  longest = Math.max(longest, run);
  return "`".repeat(Math.max(3, longest + 1));
}

function validateMessages(messages: readonly AIContextMessage[]): AIContextMessage[] {
  const seen = new Set<string>();
  return messages.map((message) => {
    const messageId = id(message.id, "message ID");
    if (message.role !== "user" && message.role !== "assistant") fail("manifest", "invalid message role");
    if (seen.has(messageId)) fail("manifest", "duplicate message ID");
    seen.add(messageId);
    return { id: messageId, role: message.role, text: String(message.text) };
  });
}

function renderManaged(content: AIContextManagedContent): string {
  const manifest = validateManifest(content.manifest);
  const synthesis = validateAIContextSynthesis(content.synthesis, manifest.papers);
  if (manifest.status !== synthesis.status) fail("synthesis", "status disagrees with manifest");
  const messages = validateMessages(content.messages);
  if (manifest.capturedEntryIds.join("\0") !== messages.map(({ id: messageId }) => messageId).join("\0")) {
    fail("manifest", "captured entry IDs do not match transcript order");
  }
  const plan = synthesis.readingPlan.map((entry) => [
    `${READING_PREFIX}${encode(entry)} -->`,
    `### ${entry.itemKey}`,
    "",
    `**Why:** ${safeMarkdown(entry.rationale)}`,
    "",
    `**Guidance:** ${safeMarkdown(entry.guidance)}`,
  ].join("\n")).join("\n\n");
  const transcript = messages.map((message) => {
    const fence = fenceFor(message.text);
    const metadata = encode({ id: message.id, role: message.role, utf8Bytes: encoder.encode(message.text).byteLength });
    return `${MESSAGE_PREFIX}${metadata} -->\n### ${message.role === "user" ? "User" : "Assistant"}\n\n`
      + `${fence}text\n${message.text}\n${fence}`;
  }).join("\n\n");
  return [
    AI_CONTEXT_MANAGED_START,
    `${MANIFEST_PREFIX}${encode(manifest)} -->`,
    `${SYNTHESIS_PREFIX}${encode(synthesis)} -->`,
    "", "## Compressed memory", "", safeMarkdown(synthesis.memoryMarkdown),
    "", "## Reading plan", "", plan,
    "", "## Progress", "", safeMarkdown(synthesis.progressMarkdown),
    "", "## Next step", "", safeMarkdown(synthesis.nextStepMarkdown),
    "", "## Conversation log", "", transcript,
    "", AI_CONTEXT_MANAGED_END,
  ].join("\n");
}

export function aiContextRelativePath(recordId: string, semanticTitle: string): string {
  recordId = validatedRecordId(recordId);
  const slug = bounded(semanticTitle, 1, 120, "synthesis", "title").normalize("NFKD").toLowerCase()
    .replace(/[^a-z0-9]+/gu, "-").replace(/^-+|-+$/gu, "").slice(0, 80);
  return `drafts/ai-contexts/${recordId}-${slug || "context"}.qmd`;
}

function safePath(relativePath: string): void {
  if (!/^drafts\/ai-contexts\/[A-Za-z0-9._-]+\.qmd$/u.test(relativePath)) {
    fail("path", "expected drafts/ai-contexts/*.qmd");
  }
}

function frontmatter(manifest: AIContextManifest, synthesis: AIContextSynthesis): string {
  const prefix = manifest.kind === "reading" ? "Reading Context" : "AI Context";
  return [
    "---",
    `title: ${JSON.stringify(`${prefix} · ${synthesis.title}`)}`,
    `description: ${JSON.stringify(synthesis.description)}`,
    `categories: [${synthesis.category}]`,
    "---",
  ].join("\n");
}

function enforceSourceBudget(source: string): void {
  if (encoder.encode(source).byteLength > AI_CONTEXT_MAX_SOURCE_BYTES) fail("path", "source exceeds 2,000,000 UTF-8 bytes");
}

export function renderNewAIContextDocument(content: AIContextManagedContent): string {
  const manifest = validateManifest(content.manifest);
  const synthesis = validateAIContextSynthesis(content.synthesis, manifest.papers);
  const source = `${frontmatter(manifest, synthesis)}\n\n${renderManaged({ ...content, manifest, synthesis })}\n`;
  enforceSourceBudget(source);
  return source;
}

function singleLine(managed: string, prefix: string, category: "manifest" | "synthesis"): string {
  const lines = managed.split("\n").filter((line) => line.startsWith(prefix));
  if (lines.length !== 1 || !lines[0]!.endsWith(" -->")) fail(category, `expected one ${prefix}`);
  return lines[0]!.slice(prefix.length, -4);
}

function parseFrontmatter(source: string): { title: string; description: string; category: AIContextCategory; end: number } {
  const match = /^---\ntitle: ("(?:[^"\\]|\\.)*")\ndescription: ("(?:[^"\\]|\\.)*")\ncategories: \[(theory|experiment|codes)\]\n---\n/u.exec(source);
  if (!match) fail("frontmatter", "expected title, description, categories in order");
  try {
    return { title: JSON.parse(match[1]!), description: JSON.parse(match[2]!), category: match[3] as AIContextCategory, end: match[0].length };
  }
  catch { return fail("frontmatter", "invalid quoted scalar"); }
}

function markerCount(source: string, marker: string): number {
  return source.split(marker).length - 1;
}

function parseMessages(managed: string): { messages: AIContextMessage[]; structural: string } {
  const messages: AIContextMessage[] = [];
  const marker = /<!-- qlab-ai-context-message:v1:([A-Za-z0-9_-]+) -->\n### (User|Assistant)\n\n(`{3,})text\n/gu;
  const structural: string[] = [];
  let structuralCursor = 0;
  let match: RegExpExecArray | null;
  while ((match = marker.exec(managed))) {
    const metadata = object(decode(match[1]!, "manifest"), "manifest");
    exactKeys(metadata, ["id", "role", "utf8Bytes"], "manifest");
    const messageId = id(metadata.id, "message ID");
    if (metadata.role !== "user" && metadata.role !== "assistant") fail("manifest", "invalid message role");
    if (!Number.isSafeInteger(metadata.utf8Bytes) || Number(metadata.utf8Bytes) < 0) fail("manifest", "invalid message byte count");
    const expectedHeading = metadata.role === "user" ? "User" : "Assistant";
    if (match[2] !== expectedHeading) fail("manifest", "message heading disagrees with role");
    const close = `\n${match[3]!}`;
    const closeIndex = managed.indexOf(close, marker.lastIndex);
    if (closeIndex < 0) fail("manifest", "missing transcript fence");
    const text = managed.slice(marker.lastIndex, closeIndex);
    if (encoder.encode(text).byteLength !== metadata.utf8Bytes) fail("manifest", "message byte count changed");
    messages.push({ id: messageId, role: metadata.role, text });
    structural.push(managed.slice(structuralCursor, marker.lastIndex));
    structural.push(text.replace(/[^\n]/gu, " "));
    structuralCursor = closeIndex;
    marker.lastIndex = closeIndex + close.length;
  }
  structural.push(managed.slice(structuralCursor));
  const masked = structural.join("");
  if (markerCount(masked, MESSAGE_PREFIX) !== messages.length) fail("manifest", "malformed message marker");
  return { messages: validateMessages(messages), structural: masked };
}

export function parseAIContextDocument(relativePath: string, source: string): AIContextDocument {
  safePath(relativePath);
  enforceSourceBudget(source);
  const parsedFrontmatter = parseFrontmatter(source);
  const start = source.indexOf(AI_CONTEXT_MANAGED_START);
  const end = source.lastIndexOf(AI_CONTEXT_MANAGED_END);
  if (start < parsedFrontmatter.end || end <= start) fail("manifest", "managed markers out of order");
  const managed = source.slice(start, end + AI_CONTEXT_MANAGED_END.length);
  const parsedMessages = parseMessages(managed);
  const structuralSource = source.slice(0, start) + parsedMessages.structural
    + source.slice(end + AI_CONTEXT_MANAGED_END.length);
  if (markerCount(structuralSource, AI_CONTEXT_MANAGED_START) !== 1
    || markerCount(structuralSource, AI_CONTEXT_MANAGED_END) !== 1) {
    fail("manifest", "expected one managed region");
  }
  if (markerCount(structuralSource, MANIFEST_PREFIX) !== 1
    || markerCount(structuralSource, SYNTHESIS_PREFIX) !== 1) {
    fail("manifest", "managed metadata must occur exactly once");
  }
  const manifest = validateManifest(decode(singleLine(parsedMessages.structural, MANIFEST_PREFIX, "manifest"), "manifest"));
  const synthesis = validateAIContextSynthesis(
    decode(singleLine(parsedMessages.structural, SYNTHESIS_PREFIX, "synthesis"), "synthesis"),
    manifest.papers,
  );
  if (manifest.status !== synthesis.status) fail("synthesis", "status disagrees with manifest");
  const messages = parsedMessages.messages;
  if (manifest.capturedEntryIds.join("\0") !== messages.map(({ id: messageId }) => messageId).join("\0")) {
    fail("manifest", "captured entry IDs do not match transcript");
  }
  if (managed !== renderManaged({ manifest, synthesis, messages })) {
    fail("manifest", "managed region is noncanonical");
  }
  const expectedPrefix = manifest.kind === "reading" ? "Reading Context · " : "AI Context · ";
  if (!parsedFrontmatter.title.startsWith(expectedPrefix)) fail("frontmatter", "title prefix disagrees with kind");
  return {
    relativePath,
    manifest,
    title: parsedFrontmatter.title,
    description: parsedFrontmatter.description,
    category: parsedFrontmatter.category,
    synthesis,
    messages,
    source,
  };
}

export function replaceAIContextManagedRegion(source: string, content: AIContextManagedContent): string {
  enforceSourceBudget(source);
  parseAIContextDocument(
    `drafts/ai-contexts/${validatedRecordId(content.manifest.id)}.qmd`,
    source,
  );
  const start = source.indexOf(AI_CONTEXT_MANAGED_START);
  const end = source.lastIndexOf(AI_CONTEXT_MANAGED_END);
  const changed = source.slice(0, start) + renderManaged(content)
    + source.slice(end + AI_CONTEXT_MANAGED_END.length);
  enforceSourceBudget(changed);
  return changed;
}

export function aiContextReopenContext(document: AIContextDocument): string {
  const plan = document.synthesis.readingPlan.map((entry, index) =>
    `${index + 1}. ${entry.itemKey}: ${entry.rationale}\n   Guidance: ${entry.guidance}`).join("\n");
  return [...[
    "## Compressed memory", document.synthesis.memoryMarkdown,
    "## Reading plan", plan,
    "## Progress", document.synthesis.progressMarkdown,
    "## Next step", document.synthesis.nextStepMarkdown,
  ].join("\n\n")].slice(0, AI_CONTEXT_MAX_REOPEN_CHARS).join("");
}
