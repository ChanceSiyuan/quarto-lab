/**
 * Pure, Gecko-free construction of the read-only ChatGPT handoff payload.
 * Callers must snapshot their live Zotero state before calling this function.
 */

export const COMPANION_CAPSULE_BOUNDS = Object.freeze({
  question: 8_000,
  selection: 8_000,
  pageExcerpt: 12_000,
  draftExcerpt: 20_000,
  contextItems: 34,
  capsuleId: 64,
  chipId: 64,
  sourceIdentity: 64,
  paperKey: 64,
  draftPath: 256,
  contextMode: 32,
  citationTitle: 256,
  citationCreators: 256,
  citationYear: 32,
  citationDoi: 128,
  citationUrl: 256,
  pageLabel: 128,
  pageSource: 32,
  screenshotTitle: 128,
  timestamp: 32,
  contentHash: 64,
  secondaryPapers: 20,
  screenshotProvenance: 8,
  prompt: 48_000,
  importedAnswer: 64_000,
});

/** Maximum distinct global warnings in a persisted handoff capsule. */
export const COMPANION_CAPSULE_WARNING_BOUND = 32;

export const CHATGPT_COMPANION_CAPSULE_BOUNDS = COMPANION_CAPSULE_BOUNDS;

export type CompanionContextKind =
  | "paper"
  | "page"
  | "selection"
  | "annotation"
  | "library"
  | "external-paper"
  | "screenshot"
  | "draft";

export type CompanionAuthority = "external_evidence" | "unreviewed_draft" | "unsupported";

export interface CompanionContextItemInput {
  id: string;
  kind: CompanionContextKind | string;
  sourceIdentity: string;
  mode?: string | null;
}

export interface CompanionPaperInput {
  title?: string;
  creators?: string;
  year?: string;
  doi?: string;
  url?: string;
}

export interface CompanionPageInput {
  pageNumber?: number;
  pageLabel?: string;
  excerpt?: string;
  source?: string;
}

export interface CompanionSelectionInput {
  text?: string;
  pageNumber?: number | null;
}

export interface CompanionSecondaryPaperInput extends CompanionPaperInput {
  id: string;
  mode?: "retrieval" | "full";
}

export interface CompanionDraftInput {
  relativePath: string;
  excerpt?: string;
}

export interface CompanionScreenshotProvenanceInput {
  id: string;
  kind: "page" | "region";
  paperTitle?: string;
  pageNumber?: number | null;
}

export interface CompanionCapsuleInput {
  subject?: { paperKey?: string | null; draftPath?: string | null };
  question: string;
  /** The exact ordered effective chip snapshot captured at the handoff click. */
  contextItems: CompanionContextItemInput[];
  paper?: CompanionPaperInput | null;
  page?: CompanionPageInput | null;
  selection?: CompanionSelectionInput | null;
  secondaryPapers?: CompanionSecondaryPaperInput[];
  draft?: CompanionDraftInput | null;
  screenshotProvenance?: CompanionScreenshotProvenanceInput[];
}

export interface CompanionCapsuleDependencies {
  id: () => string;
  now: () => Date | string;
  /** A deterministic checksum function; injected so this module has no Gecko dependency. */
  hash: (canonicalJson: string) => string;
}

export interface ChatGPTCompanionCapsule {
  schemaVersion: 1;
  id: string;
  createdAt: string;
  subject: { paperKey: string | null; draftPath: string | null };
  /** Preserved code-point-for-code-point from the accepted composer question. */
  question: string;
  contextItems: Array<{
    id: string;
    kind: CompanionContextKind;
    included: boolean;
    supported: boolean;
    sourceIdentity: string;
    mode: "retrieval" | "full" | null;
    authority: CompanionAuthority;
    warning: string | null;
  }>;
  paper: {
    authority: "external_evidence";
    title: string;
    creators: string;
    year: string;
    doi: string;
    url: string;
  } | null;
  page: {
    authority: "external_evidence";
    pageNumber: number;
    pageLabel: string;
    excerpt: string;
    source: string;
  } | null;
  selection: {
    authority: "external_evidence";
    text: string;
    pageNumber: number | null;
  } | null;
  secondaryPapers: Array<{
    authority: "external_evidence";
    title: string;
    creators: string;
    year: string;
    doi: string;
    url: string;
    mode: "retrieval" | "full";
  }>;
  draft: {
    relativePath: string;
    authority: "unreviewed_draft";
    excerpt: string;
    truncated: boolean;
  } | null;
  screenshotProvenance: Array<{
    authority: "external_evidence";
    kind: "page" | "region";
    paperTitle: string;
    pageNumber: number | null;
  }>;
  warnings: string[];
  bounds: Record<string, number>;
  contentHash: string;
}

const CONTEXT_KINDS = new Set<CompanionContextKind>([
  "paper", "page", "selection", "annotation", "library", "external-paper", "screenshot", "draft",
]);
const PAGE_SOURCES = new Set(["pdfjs", "indexed-fulltext", "pdf-worker", "none"]);
const OPAQUE_ID = /^[A-Za-z0-9_-]+$/;
const CONTROL = /[\u0000-\u001F\u007F-\u009F]/gu;
const CONTROL_TEST = /[\u0000-\u001F\u007F-\u009F]/u;

function codePoints(value: string): string[] {
  return Array.from(value);
}

function normalizeMetadata(value: unknown): string {
  return typeof value === "string" ? value.normalize("NFKC").replace(CONTROL, "�") : "";
}

function boundedMetadata(
  value: unknown,
  maximum: number,
  label: string,
  warnings: string[],
): { value: string; truncated: boolean } {
  const normalized = normalizeMetadata(value);
  const points = codePoints(normalized);
  if (points.length <= maximum) return { value: normalized, truncated: false };
  warnings.push(`${label} was truncated to ${maximum.toLocaleString("en-US")} Unicode code points.`);
  return { value: points.slice(0, maximum).join(""), truncated: true };
}

function boundedOmissibleMetadata(
  value: unknown,
  maximum: number,
  label: string,
  warnings: string[],
): string {
  const normalized = normalizeMetadata(value);
  if (codePoints(normalized).length <= maximum) return normalized;
  warnings.push(`${label} exceeded ${maximum.toLocaleString("en-US")} Unicode code points and was omitted.`);
  return "";
}

function unsafeLocator(value: string): boolean {
  return value.startsWith("/")
    || value.startsWith("\\")
    || value.includes("\\")
    || /^[A-Za-z]:[\\/]/u.test(value)
    || /^(?:data|file):/iu.test(value)
    || /^(?:\.{1,2}|drafts|knowledge|literature|work|public)(?:\/|$)/iu.test(value);
}

function exactIdentifier(value: unknown, maximum: number, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-blank identifier`);
  if (CONTROL_TEST.test(value)) throw new Error(`${label} contains a disallowed control character`);
  if (codePoints(value).length > maximum) {
    throw new Error(`${label} exceeds ${maximum.toLocaleString("en-US")} Unicode code points`);
  }
  if (unsafeLocator(value)) throw new Error(`${label} must not contain a filesystem path or data URL`);
  return value;
}

function safeDraftPath(value: unknown): string | null {
  if (typeof value !== "string" || !value || codePoints(value).length > COMPANION_CAPSULE_BOUNDS.draftPath) {
    return null;
  }
  if (CONTROL_TEST.test(value) || value.includes("\\") || !value.startsWith("drafts/")) return null;
  if (value.startsWith("/") || /^[A-Za-z]:[\\/]/u.test(value) || /^(?:data|file):/iu.test(value)) return null;
  const path = value;
  const parts = path.split("/");
  return parts.length > 1 && parts.every((part) => part && part !== "." && part !== "..") ? path : null;
}

function exactDraftIdentity(value: unknown): string {
  if (typeof value !== "string"
    || codePoints(value).length > COMPANION_CAPSULE_BOUNDS.sourceIdentity
    || safeDraftPath(value) !== value) {
    throw new Error("Draft source identity must be an exact POSIX path below drafts/");
  }
  return value;
}

function safeExternalUrl(value: unknown, label: string, warnings: string[]): string {
  const url = boundedOmissibleMetadata(value, COMPANION_CAPSULE_BOUNDS.citationUrl, label, warnings);
  if (!url || /^https?:\/\//iu.test(url)) return url;
  warnings.push(`${label} was not an HTTP(S) URL and was omitted.`);
  return "";
}

function safeDoi(value: unknown, label: string, warnings: string[]): string {
  const doi = boundedOmissibleMetadata(value, COMPANION_CAPSULE_BOUNDS.citationDoi, label, warnings);
  if (!doi || !unsafeLocator(doi)) return doi;
  warnings.push(`${label} was path- or data-shaped and was omitted.`);
  return "";
}

function safePageSource(value: unknown, warnings: string[]): string {
  if (value === undefined || value === null || value === "") return "";
  if (typeof value !== "string"
    || CONTROL_TEST.test(value)
    || codePoints(value).length > COMPANION_CAPSULE_BOUNDS.pageSource
    || unsafeLocator(value)
    || !PAGE_SOURCES.has(value)) {
    warnings.push("Page source was unsafe or unsupported and was omitted.");
    return "";
  }
  return value;
}

function canonicalTimestamp(value: Date | string): string {
  if (value instanceof Date) {
    try {
      return value.toISOString();
    }
    catch {
      throw new Error("The capsule timestamp is invalid");
    }
  }
  const raw = value;
  if (typeof raw !== "string"
    || codePoints(raw).length > COMPANION_CAPSULE_BOUNDS.timestamp
    || CONTROL_TEST.test(raw)) {
    throw new Error("The capsule timestamp is invalid or exceeds its bound");
  }
  const instant = new Date(raw);
  if (Number.isNaN(instant.getTime())) throw new Error("The capsule timestamp is invalid");
  const canonical = instant.toISOString();
  if (!raw.endsWith("Z") || canonical !== raw) {
    throw new Error("The capsule timestamp must be a canonical ISO UTC instant");
  }
  return canonical;
}

function assertArrayBound(value: unknown, maximum: number, label: string): void {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  if (value.length > maximum) throw new Error(`${label} exceed the maximum of ${maximum}`);
}

function safePageNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null;
}

function requireQuestion(question: string): void {
  const points = codePoints(question);
  if (!question.trim()) throw new Error("A non-blank question is required");
  // Newlines and tabs are valid in a question and must remain byte-for-byte
  // visible to the handoff; other control characters are not.
  if (/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/u.test(question)) {
    throw new Error("The question contains a disallowed control character");
  }
  if (points.length > COMPANION_CAPSULE_BOUNDS.question) {
    throw new Error("The question exceeds 8,000 Unicode code points");
  }
}

function canonicalJson(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (!value || typeof value !== "object") throw new Error("Capsule content must be JSON data");
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`).join(",")}}`;
}

/** Canonical checksum input: recursively sorted object keys, with contentHash excluded. */
export function canonicalCompanionCapsuleJson(capsule: Omit<ChatGPTCompanionCapsule, "contentHash">): string {
  return canonicalJson(capsule);
}

function freeze<T>(value: T): T {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const nested of Object.values(value as Record<string, unknown>)) freeze(nested);
    Object.freeze(value);
  }
  return value;
}

function validatedChip(input: CompanionContextItemInput, warnings: string[]): {
  id: string;
  kind: CompanionContextKind;
  sourceIdentity: string;
  mode: "retrieval" | "full" | null;
} {
  if (!CONTEXT_KINDS.has(input.kind as CompanionContextKind)) {
    throw new Error("The context snapshot contains an unsupported chip kind");
  }
  let mode: "retrieval" | "full" | null = null;
  if (input.mode !== undefined && input.mode !== null) {
    if (input.mode === "retrieval" || input.mode === "full") mode = input.mode;
    else warnings.push("Context mode was invalid and was omitted.");
  }
  return {
    id: exactIdentifier(input.id, COMPANION_CAPSULE_BOUNDS.chipId, "Context chip ID"),
    kind: input.kind as CompanionContextKind,
    sourceIdentity: input.kind === "draft"
      ? exactDraftIdentity(input.sourceIdentity)
      : exactIdentifier(
        input.sourceIdentity,
        COMPANION_CAPSULE_BOUNDS.sourceIdentity,
        "Context source identity",
      ),
    mode,
  };
}

function chipWarning(message: string, warnings: string[]): string {
  warnings.push(message);
  return message;
}

export function buildCompanionCapsule(
  input: CompanionCapsuleInput,
  dependencies: CompanionCapsuleDependencies,
): ChatGPTCompanionCapsule {
  requireQuestion(input.question);
  assertArrayBound(input.contextItems, COMPANION_CAPSULE_BOUNDS.contextItems, "Context items");
  const secondaryInputs = input.secondaryPapers || [];
  const screenshotInputs = input.screenshotProvenance || [];
  assertArrayBound(secondaryInputs, COMPANION_CAPSULE_BOUNDS.secondaryPapers, "Secondary papers");
  assertArrayBound(
    screenshotInputs,
    COMPANION_CAPSULE_BOUNDS.screenshotProvenance,
    "Screenshot provenance entries",
  );

  const secondaryByIdentity = new Map<string, CompanionSecondaryPaperInput>();
  for (const candidate of secondaryInputs) {
    const identity = exactIdentifier(
      candidate.id,
      COMPANION_CAPSULE_BOUNDS.sourceIdentity,
      "Secondary paper source identity",
    );
    if (secondaryByIdentity.has(identity)) throw new Error("Secondary paper source identities must be unique");
    secondaryByIdentity.set(identity, candidate);
  }
  const screenshotByIdentity = new Map<string, CompanionScreenshotProvenanceInput>();
  for (const candidate of screenshotInputs) {
    const identity = exactIdentifier(
      candidate.id,
      COMPANION_CAPSULE_BOUNDS.sourceIdentity,
      "Screenshot source identity",
    );
    if (screenshotByIdentity.has(identity)) throw new Error("Screenshot source identities must be unique");
    screenshotByIdentity.set(identity, candidate);
  }

  const id = dependencies.id();
  if (!OPAQUE_ID.test(id)
    || codePoints(id).length < 16
    || codePoints(id).length > COMPANION_CAPSULE_BOUNDS.capsuleId) {
    throw new Error("The capsule ID must be an opaque identifier");
  }
  const createdAt = canonicalTimestamp(dependencies.now());

  const warnings: string[] = [];
  const contextItems: ChatGPTCompanionCapsule["contextItems"] = [];
  let paper: ChatGPTCompanionCapsule["paper"] = null;
  let page: ChatGPTCompanionCapsule["page"] = null;
  let selection: ChatGPTCompanionCapsule["selection"] = null;
  let draft: ChatGPTCompanionCapsule["draft"] = null;
  const secondaryPapers: ChatGPTCompanionCapsule["secondaryPapers"] = [];
  const screenshotProvenance: ChatGPTCompanionCapsule["screenshotProvenance"] = [];

  for (const rawChip of input.contextItems) {
    const chip = validatedChip(rawChip, warnings);
    let included = false;
    let supported = true;
    let authority: CompanionAuthority = chip.kind === "draft" ? "unreviewed_draft" : "external_evidence";
    let warning: string | null = null;

    if (chip.kind === "annotation" || chip.kind === "library") {
      supported = false;
      authority = "unsupported";
      warning = chipWarning(
        chip.kind === "annotation"
          ? "Annotations were omitted because the remote repository MCP cannot access the Zotero database."
          : "Zotero Library was omitted because the remote repository MCP cannot access the Zotero database.",
        warnings,
      );
    }
    else if (chip.kind === "paper" && input.paper) {
      paper = {
        authority: "external_evidence",
        title: boundedMetadata(
          input.paper.title,
          COMPANION_CAPSULE_BOUNDS.citationTitle,
          "Paper title",
          warnings,
        ).value,
        creators: boundedMetadata(
          input.paper.creators,
          COMPANION_CAPSULE_BOUNDS.citationCreators,
          "Paper creators",
          warnings,
        ).value,
        year: boundedMetadata(
          input.paper.year,
          COMPANION_CAPSULE_BOUNDS.citationYear,
          "Paper year",
          warnings,
        ).value,
        doi: safeDoi(input.paper.doi, "Paper DOI", warnings),
        url: safeExternalUrl(input.paper.url, "Paper URL", warnings),
      };
      included = true;
    }
    else if (chip.kind === "page" && input.page) {
      const warningCount = warnings.length;
      const excerpt = boundedMetadata(
        input.page.excerpt,
        COMPANION_CAPSULE_BOUNDS.pageExcerpt,
        "Current page excerpt",
        warnings,
      );
      if (warnings.length > warningCount) warning = warnings[warnings.length - 1] || null;
      page = {
        authority: "external_evidence",
        pageNumber: safePageNumber(input.page.pageNumber) || 1,
        pageLabel: boundedMetadata(
          input.page.pageLabel,
          COMPANION_CAPSULE_BOUNDS.pageLabel,
          "Page label",
          warnings,
        ).value,
        excerpt: excerpt.value,
        source: safePageSource(input.page.source, warnings),
      };
      included = true;
    }
    else if (chip.kind === "selection" && input.selection) {
      const warningCount = warnings.length;
      const text = boundedMetadata(
        input.selection.text,
        COMPANION_CAPSULE_BOUNDS.selection,
        "Selection",
        warnings,
      );
      if (warnings.length > warningCount) warning = warnings[warnings.length - 1] || null;
      selection = {
        authority: "external_evidence",
        text: text.value,
        pageNumber: safePageNumber(input.selection.pageNumber),
      };
      included = true;
    }
    else if (chip.kind === "external-paper") {
      if (secondaryPapers.length >= COMPANION_CAPSULE_BOUNDS.secondaryPapers) {
        warning = chipWarning("Secondary paper was omitted because the maximum of 20 was reached.", warnings);
      }
      else {
        const candidate = secondaryByIdentity.get(chip.sourceIdentity);
        if (!candidate) warning = chipWarning("Secondary paper citation identity was unavailable and was omitted.", warnings);
        else if (candidate.mode !== undefined && candidate.mode !== "retrieval" && candidate.mode !== "full") {
          warning = chipWarning("Secondary paper mode was invalid and the candidate was omitted.", warnings);
        }
        else {
          const mode = chip.mode === "full" || chip.mode === "retrieval" ? chip.mode : candidate.mode;
          if (!mode) warning = chipWarning("Secondary paper mode was unavailable and was omitted.", warnings);
          else {
            secondaryPapers.push({
              authority: "external_evidence",
              title: boundedMetadata(
                candidate.title,
                COMPANION_CAPSULE_BOUNDS.citationTitle,
                "Secondary paper title",
                warnings,
              ).value,
              creators: boundedMetadata(
                candidate.creators,
                COMPANION_CAPSULE_BOUNDS.citationCreators,
                "Secondary paper creators",
                warnings,
              ).value,
              year: boundedMetadata(
                candidate.year,
                COMPANION_CAPSULE_BOUNDS.citationYear,
                "Secondary paper year",
                warnings,
              ).value,
              doi: safeDoi(candidate.doi, "Secondary paper DOI", warnings),
              url: safeExternalUrl(candidate.url, "Secondary paper URL", warnings),
              mode,
            });
            warning = chipWarning("Secondary paper local PDF and full text were not transferred.", warnings);
            included = true;
          }
        }
      }
    }
    else if (chip.kind === "draft" && input.draft) {
      const relativePath = safeDraftPath(input.draft.relativePath);
      if (!relativePath) warning = chipWarning("Draft was omitted because its path was not below drafts/.", warnings);
      else {
        const warningCount = warnings.length;
        const excerpt = boundedMetadata(
          input.draft.excerpt,
          COMPANION_CAPSULE_BOUNDS.draftExcerpt,
          "Draft excerpt",
          warnings,
        );
        if (warnings.length > warningCount) warning = warnings[warnings.length - 1] || null;
        draft = { relativePath, authority: "unreviewed_draft", excerpt: excerpt.value, truncated: excerpt.truncated };
        authority = "unreviewed_draft";
        included = true;
      }
    }
    else if (chip.kind === "screenshot") {
      if (screenshotProvenance.length >= COMPANION_CAPSULE_BOUNDS.screenshotProvenance) {
        warning = chipWarning("Screenshot provenance was omitted because the maximum of 8 was reached.", warnings);
      }
      else {
        const candidate = screenshotByIdentity.get(chip.sourceIdentity);
        if (!candidate) warning = chipWarning("Screenshot provenance was unavailable and pixels were not transferred.", warnings);
        else if (candidate.kind !== "page" && candidate.kind !== "region") {
          warning = chipWarning("Screenshot provenance kind was invalid and the candidate was omitted.", warnings);
        }
        else {
          screenshotProvenance.push({
            authority: "external_evidence",
            kind: candidate.kind,
            paperTitle: boundedMetadata(
              candidate.paperTitle,
              COMPANION_CAPSULE_BOUNDS.screenshotTitle,
              "Screenshot title",
              warnings,
            ).value,
            pageNumber: safePageNumber(candidate.pageNumber),
          });
          warning = chipWarning("Screenshot pixels were not transferred; only provenance was included.", warnings);
          included = true;
        }
      }
    }

    if (supported && !included && !warning) {
      warning = chipWarning("Requested context was unavailable and was omitted.", warnings);
    }
    contextItems.push({ ...chip, included, supported, authority, warning });
  }

  const subjectDraftPath = safeDraftPath(input.subject?.draftPath);
  if (input.subject?.draftPath && !subjectDraftPath) {
    warnings.push("Subject Draft path was omitted because it was not below drafts/.");
  }
  const subjectPaperKey = input.subject?.paperKey === null || input.subject?.paperKey === undefined
    ? null
    : exactIdentifier(input.subject.paperKey, COMPANION_CAPSULE_BOUNDS.paperKey, "Subject paper key");
  const distinctWarnings = [...new Set(warnings)];
  if (distinctWarnings.length > COMPANION_CAPSULE_WARNING_BOUND) {
    throw new Error("The capsule has too many distinct warnings");
  }
  const unsigned: Omit<ChatGPTCompanionCapsule, "contentHash"> = {
    schemaVersion: 1,
    id,
    createdAt,
    subject: {
      paperKey: subjectPaperKey,
      draftPath: subjectDraftPath,
    },
    question: input.question,
    contextItems,
    paper,
    page,
    selection,
    secondaryPapers,
    draft,
    screenshotProvenance,
    warnings: distinctWarnings,
    bounds: { ...COMPANION_CAPSULE_BOUNDS },
  };
  const contentHash = dependencies.hash(canonicalCompanionCapsuleJson(unsigned));
  if (typeof contentHash !== "string"
    || !contentHash
    || CONTROL_TEST.test(contentHash)
    || codePoints(contentHash).length > COMPANION_CAPSULE_BOUNDS.contentHash) {
    throw new Error("The capsule checksum is invalid or exceeds its bound");
  }
  return freeze({ ...unsigned, contentHash });
}

const MAX_WARNING_LENGTH = 128;
const SAFE_WARNING = /^[A-Za-z0-9 .,;:()'’/-]+$/u;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  return isRecord(value)
    && Object.keys(value).length === keys.length
    && keys.every((key) => Object.hasOwn(value, key));
}

function exactMetadata(value: unknown, maximum: number): value is string {
  if (typeof value !== "string") return false;
  const warnings: string[] = [];
  return boundedMetadata(value, maximum, "Stored capsule metadata", warnings).value === value && warnings.length === 0;
}

function exactWarning(value: unknown): value is string {
  return typeof value === "string" && Boolean(value) && codePoints(value).length <= MAX_WARNING_LENGTH
    && SAFE_WARNING.test(value);
}

function exactChecksum(value: unknown): value is string {
  return typeof value === "string" && Boolean(value) && !CONTROL_TEST.test(value)
    && codePoints(value).length <= COMPANION_CAPSULE_BOUNDS.contentHash;
}

function exactIdentifierValue(value: unknown, maximum: number, label: string): value is string {
  try {
    return exactIdentifier(value, maximum, label) === value;
  }
  catch {
    return false;
  }
}

function exactDraftPath(value: unknown): value is string {
  return typeof value === "string" && safeDraftPath(value) === value;
}

function exactTimestamp(value: unknown): value is string {
  try {
    return canonicalTimestamp(value as string) === value;
  }
  catch {
    return false;
  }
}

function exactQuestion(value: unknown): value is string {
  try {
    if (typeof value !== "string") return false;
    requireQuestion(value);
    return true;
  }
  catch {
    return false;
  }
}

function exactUrl(value: unknown): value is string {
  return typeof value === "string" && safeExternalUrl(value, "Stored capsule URL", []) === value;
}

function exactDoi(value: unknown): value is string {
  return typeof value === "string" && safeDoi(value, "Stored capsule DOI", []) === value;
}

function exactPageSource(value: unknown): value is string {
  return typeof value === "string" && safePageSource(value, []) === value;
}

function positiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function exactBounds(value: unknown): boolean {
  return hasExactKeys(value, Object.keys(COMPANION_CAPSULE_BOUNDS))
    && Object.entries(COMPANION_CAPSULE_BOUNDS).every(([key, bound]) => value[key] === bound);
}

function exactCitation(value: unknown, secondary = false): boolean {
  const keys = secondary
    ? ["authority", "title", "creators", "year", "doi", "url", "mode"]
    : ["authority", "title", "creators", "year", "doi", "url"];
  return hasExactKeys(value, keys)
    && value.authority === "external_evidence"
    && exactMetadata(value.title, COMPANION_CAPSULE_BOUNDS.citationTitle)
    && exactMetadata(value.creators, COMPANION_CAPSULE_BOUNDS.citationCreators)
    && exactMetadata(value.year, COMPANION_CAPSULE_BOUNDS.citationYear)
    && exactDoi(value.doi)
    && exactUrl(value.url)
    && (!secondary || value.mode === "retrieval" || value.mode === "full");
}

function exactContextItem(value: unknown): boolean {
  if (!hasExactKeys(value, ["id", "kind", "included", "supported", "sourceIdentity", "mode", "authority", "warning"])
    || !CONTEXT_KINDS.has(value.kind as CompanionContextKind)
    || !exactIdentifierValue(value.id, COMPANION_CAPSULE_BOUNDS.chipId, "Context chip ID")
    || (value.kind === "draft"
      ? !exactDraftPath(value.sourceIdentity)
      : !exactIdentifierValue(value.sourceIdentity, COMPANION_CAPSULE_BOUNDS.sourceIdentity, "Context source identity"))
    || typeof value.included !== "boolean" || typeof value.supported !== "boolean"
    || (value.mode !== null && value.mode !== "retrieval" && value.mode !== "full")
    || (value.warning !== null && !exactWarning(value.warning))) return false;

  if (value.kind === "annotation" || value.kind === "library") {
    return value.authority === "unsupported" && value.supported === false && value.included === false;
  }
  return value.authority === (value.kind === "draft" ? "unreviewed_draft" : "external_evidence")
    && value.supported === true;
}

function payloadsMatchIncludedContext(value: Record<string, unknown>): boolean {
  const contextItems = value.contextItems as Array<Record<string, unknown>>;
  const secondaryPapers = value.secondaryPapers as Array<Record<string, unknown>>;
  const included = (kind: CompanionContextKind): number => contextItems.filter(
    (item) => item.kind === kind && item.included === true,
  ).length;
  const secondaryModesMatch = contextItems
    .filter((item) => item.kind === "external-paper" && item.included === true)
    .every((item, index) => item.mode === null || item.mode === secondaryPapers[index]?.mode);
  return (included("paper") > 0) === (value.paper !== null)
    && (included("page") > 0) === (value.page !== null)
    && (included("selection") > 0) === (value.selection !== null)
    && (included("draft") > 0) === (value.draft !== null)
    && included("external-paper") === secondaryPapers.length
    && secondaryModesMatch
    && included("screenshot") === (value.screenshotProvenance as unknown[]).length;
}

/**
 * Validates the full, persisted capsule shape and all builder safety invariants.
 * The checksum is intentionally checked separately by verifyCompanionCapsule.
 */
export function validateCompanionCapsule(value: unknown): value is ChatGPTCompanionCapsule {
  if (!hasExactKeys(value, [
    "schemaVersion", "id", "createdAt", "subject", "question", "contextItems", "paper", "page", "selection",
    "secondaryPapers", "draft", "screenshotProvenance", "warnings", "bounds", "contentHash",
  ]) || value.schemaVersion !== 1
    || !exactIdentifierValue(value.id, COMPANION_CAPSULE_BOUNDS.capsuleId, "Capsule ID")
    || !OPAQUE_ID.test(value.id) || Array.from(value.id).length < 16
    || !exactTimestamp(value.createdAt) || !exactQuestion(value.question)
    || !exactChecksum(value.contentHash)
    || !hasExactKeys(value.subject, ["paperKey", "draftPath"])
    || (value.subject.paperKey !== null
      && !exactIdentifierValue(value.subject.paperKey, COMPANION_CAPSULE_BOUNDS.paperKey, "Subject paper key"))
    || (value.subject.draftPath !== null && !exactDraftPath(value.subject.draftPath))
    || !exactBounds(value.bounds)
    || !Array.isArray(value.contextItems) || value.contextItems.length > COMPANION_CAPSULE_BOUNDS.contextItems
    || !value.contextItems.every(exactContextItem)
    || !Array.isArray(value.secondaryPapers) || value.secondaryPapers.length > COMPANION_CAPSULE_BOUNDS.secondaryPapers
    || !value.secondaryPapers.every((paper) => exactCitation(paper, true))
    || !Array.isArray(value.screenshotProvenance)
    || value.screenshotProvenance.length > COMPANION_CAPSULE_BOUNDS.screenshotProvenance
    || !Array.isArray(value.warnings) || value.warnings.length > COMPANION_CAPSULE_WARNING_BOUND
    || !value.warnings.every(exactWarning)) return false;

  if (!payloadsMatchIncludedContext(value)) return false;

  if (value.paper !== null && !exactCitation(value.paper)) return false;
  if (value.page !== null && (!hasExactKeys(value.page, ["authority", "pageNumber", "pageLabel", "excerpt", "source"])
    || value.page.authority !== "external_evidence" || !positiveInteger(value.page.pageNumber)
    || !exactMetadata(value.page.pageLabel, COMPANION_CAPSULE_BOUNDS.pageLabel)
    || !exactMetadata(value.page.excerpt, COMPANION_CAPSULE_BOUNDS.pageExcerpt)
    || !exactPageSource(value.page.source))) return false;
  if (value.selection !== null && (!hasExactKeys(value.selection, ["authority", "text", "pageNumber"])
    || value.selection.authority !== "external_evidence"
    || !exactMetadata(value.selection.text, COMPANION_CAPSULE_BOUNDS.selection)
    || (value.selection.pageNumber !== null && !positiveInteger(value.selection.pageNumber)))) return false;
  if (value.draft !== null && (!hasExactKeys(value.draft, ["relativePath", "authority", "excerpt", "truncated"])
    || !exactDraftPath(value.draft.relativePath) || value.draft.authority !== "unreviewed_draft"
    || !exactMetadata(value.draft.excerpt, COMPANION_CAPSULE_BOUNDS.draftExcerpt)
    || typeof value.draft.truncated !== "boolean"
    || (value.draft.truncated && codePoints(value.draft.excerpt).length !== COMPANION_CAPSULE_BOUNDS.draftExcerpt))) return false;
  return value.screenshotProvenance.every((entry) => hasExactKeys(entry, ["authority", "kind", "paperTitle", "pageNumber"])
    && entry.authority === "external_evidence" && (entry.kind === "page" || entry.kind === "region")
    && exactMetadata(entry.paperTitle, COMPANION_CAPSULE_BOUNDS.screenshotTitle)
    && (entry.pageNumber === null || positiveInteger(entry.pageNumber)));
}

export function verifyCompanionCapsule(
  capsule: unknown,
  hash: CompanionCapsuleDependencies["hash"],
): capsule is ChatGPTCompanionCapsule {
  if (!validateCompanionCapsule(capsule)) return false;
  const { contentHash, ...unsigned } = capsule;
  try {
    return hash(canonicalCompanionCapsuleJson(unsigned)) === contentHash;
  }
  catch {
    return false;
  }
}
