/**
 * Pure, Gecko-free construction of the read-only ChatGPT handoff payload.
 * Callers must snapshot their live Zotero state before calling this function.
 */

export const COMPANION_CAPSULE_BOUNDS = Object.freeze({
  question: 8_000,
  selection: 8_000,
  pageExcerpt: 12_000,
  draftExcerpt: 20_000,
  contextItems: 64,
  capsuleId: 128,
  chipId: 128,
  sourceIdentity: 512,
  paperKey: 128,
  draftPath: 1_024,
  contextMode: 32,
  citationTitle: 1_024,
  citationCreators: 2_048,
  citationYear: 32,
  citationDoi: 512,
  citationUrl: 2_048,
  pageLabel: 128,
  pageSource: 32,
  screenshotTitle: 1_024,
  timestamp: 32,
  contentHash: 512,
  secondaryPapers: 20,
  screenshotProvenance: 8,
  prompt: 48_000,
  importedAnswer: 64_000,
});

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
    warnings,
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

export function verifyCompanionCapsule(
  capsule: ChatGPTCompanionCapsule,
  hash: CompanionCapsuleDependencies["hash"],
): boolean {
  if (capsule.schemaVersion !== 1
    || !OPAQUE_ID.test(capsule.id)
    || codePoints(capsule.id).length < 16
    || codePoints(capsule.id).length > COMPANION_CAPSULE_BOUNDS.capsuleId
    || !capsule.contentHash) return false;
  const { contentHash, ...unsigned } = capsule;
  try {
    return hash(canonicalCompanionCapsuleJson(unsigned)) === contentHash;
  }
  catch {
    return false;
  }
}
