/**
 * Pure, Gecko-free construction of the read-only ChatGPT handoff payload.
 * Callers must snapshot their live Zotero state before calling this function.
 */

export const COMPANION_CAPSULE_BOUNDS = Object.freeze({
  question: 8_000,
  selection: 8_000,
  pageExcerpt: 12_000,
  draftExcerpt: 20_000,
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
    mode: string | null;
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
const OPAQUE_ID = /^[A-Za-z0-9_-]{16,128}$/;
const CONTROL = /[\u0000-\u001F\u007F-\u009F]/gu;

function codePoints(value: string): string[] {
  return Array.from(value);
}

function normalizeMetadata(value: unknown): string {
  return typeof value === "string" ? value.normalize("NFKC").replace(CONTROL, "�") : "";
}

function boundedMetadata(value: unknown, maximum: number): { value: string; truncated: boolean } {
  const normalized = normalizeMetadata(value);
  const points = codePoints(normalized);
  return points.length > maximum
    ? { value: points.slice(0, maximum).join(""), truncated: true }
    : { value: normalized, truncated: false };
}

function safeRelativePath(value: unknown): string | null {
  const path = normalizeMetadata(value);
  if (!path || path.startsWith("/") || /^[A-Za-z]:[\\/]/.test(path)) return null;
  const parts = path.split("/");
  return parts.every((part) => part && part !== "." && part !== "..") ? path : null;
}

function safeExternalUrl(value: unknown): string {
  const url = normalizeMetadata(value);
  return /^https?:\/\//iu.test(url) ? url : "";
}

function safePageSource(value: unknown): string {
  const source = normalizeMetadata(value);
  return source.startsWith("/") || /^[A-Za-z]:[\\/]/.test(source) || /^file:/iu.test(source)
    ? ""
    : source;
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

function normalizedChip(input: CompanionContextItemInput): {
  id: string;
  kind: CompanionContextKind;
  sourceIdentity: string;
  mode: string | null;
} {
  if (!CONTEXT_KINDS.has(input.kind as CompanionContextKind)) {
    throw new Error("The context snapshot contains an unsupported chip kind");
  }
  return {
    id: normalizeMetadata(input.id),
    kind: input.kind as CompanionContextKind,
    sourceIdentity: normalizeMetadata(input.sourceIdentity),
    mode: input.mode === undefined || input.mode === null ? null : normalizeMetadata(input.mode),
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
  const id = dependencies.id();
  if (!OPAQUE_ID.test(id)) throw new Error("The capsule ID must be an opaque identifier");
  const created = dependencies.now();
  const createdAt = created instanceof Date ? created.toISOString() : created;
  if (typeof createdAt !== "string" || Number.isNaN(Date.parse(createdAt))) {
    throw new Error("The capsule timestamp is invalid");
  }

  const warnings: string[] = [];
  const contextItems: ChatGPTCompanionCapsule["contextItems"] = [];
  let paper: ChatGPTCompanionCapsule["paper"] = null;
  let page: ChatGPTCompanionCapsule["page"] = null;
  let selection: ChatGPTCompanionCapsule["selection"] = null;
  let draft: ChatGPTCompanionCapsule["draft"] = null;
  const secondaryPapers: ChatGPTCompanionCapsule["secondaryPapers"] = [];
  const screenshotProvenance: ChatGPTCompanionCapsule["screenshotProvenance"] = [];

  for (const rawChip of input.contextItems) {
    const chip = normalizedChip(rawChip);
    let included = false;
    let supported = true;
    let authority: CompanionAuthority = "external_evidence";
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
        title: normalizeMetadata(input.paper.title),
        creators: normalizeMetadata(input.paper.creators),
        year: normalizeMetadata(input.paper.year),
        doi: normalizeMetadata(input.paper.doi),
        url: safeExternalUrl(input.paper.url),
      };
      included = true;
    }
    else if (chip.kind === "page" && input.page) {
      const excerpt = boundedMetadata(input.page.excerpt, COMPANION_CAPSULE_BOUNDS.pageExcerpt);
      if (excerpt.truncated) warning = chipWarning("Current page excerpt was truncated to 12,000 Unicode code points.", warnings);
      page = {
        authority: "external_evidence",
        pageNumber: safePageNumber(input.page.pageNumber) || 1,
        pageLabel: normalizeMetadata(input.page.pageLabel),
        excerpt: excerpt.value,
        source: safePageSource(input.page.source),
      };
      included = true;
    }
    else if (chip.kind === "selection" && input.selection) {
      const text = boundedMetadata(input.selection.text, COMPANION_CAPSULE_BOUNDS.selection);
      if (text.truncated) warning = chipWarning("Selection was truncated to 8,000 Unicode code points.", warnings);
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
        const candidate = (input.secondaryPapers || []).find((paperInput) => paperInput.id === rawChip.sourceIdentity);
        if (!candidate) warning = chipWarning("Secondary paper citation identity was unavailable and was omitted.", warnings);
        else {
          const mode = chip.mode === "full" || chip.mode === "retrieval" ? chip.mode : candidate.mode;
          if (!mode) warning = chipWarning("Secondary paper mode was unavailable and was omitted.", warnings);
          else {
            secondaryPapers.push({
              authority: "external_evidence",
              title: normalizeMetadata(candidate.title),
              creators: normalizeMetadata(candidate.creators),
              year: normalizeMetadata(candidate.year),
              doi: normalizeMetadata(candidate.doi),
              url: safeExternalUrl(candidate.url),
              mode,
            });
            warning = chipWarning("Secondary paper local PDF and full text were not transferred.", warnings);
            included = true;
          }
        }
      }
    }
    else if (chip.kind === "draft" && input.draft) {
      const relativePath = safeRelativePath(input.draft.relativePath);
      if (!relativePath) warning = chipWarning("Draft was omitted because its path was not repository-relative.", warnings);
      else {
        const excerpt = boundedMetadata(input.draft.excerpt, COMPANION_CAPSULE_BOUNDS.draftExcerpt);
        if (excerpt.truncated) warning = chipWarning("Draft excerpt was truncated to 20,000 Unicode code points.", warnings);
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
        const candidate = (input.screenshotProvenance || []).find((shot) => shot.id === rawChip.sourceIdentity);
        if (!candidate) warning = chipWarning("Screenshot provenance was unavailable and pixels were not transferred.", warnings);
        else {
          screenshotProvenance.push({
            kind: candidate.kind,
            paperTitle: normalizeMetadata(candidate.paperTitle),
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

  const subjectDraftPath = safeRelativePath(input.subject?.draftPath);
  if (input.subject?.draftPath && !subjectDraftPath) warnings.push("Subject Draft path was omitted because it is not repository-relative.");
  const unsigned: Omit<ChatGPTCompanionCapsule, "contentHash"> = {
    schemaVersion: 1,
    id,
    createdAt,
    subject: {
      paperKey: input.subject?.paperKey === null || input.subject?.paperKey === undefined
        ? null
        : normalizeMetadata(input.subject.paperKey),
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
  if (!contentHash) throw new Error("The capsule checksum is invalid");
  return freeze({ ...unsigned, contentHash });
}

export function verifyCompanionCapsule(
  capsule: ChatGPTCompanionCapsule,
  hash: CompanionCapsuleDependencies["hash"],
): boolean {
  if (capsule.schemaVersion !== 1 || !OPAQUE_ID.test(capsule.id) || !capsule.contentHash) return false;
  const { contentHash, ...unsigned } = capsule;
  try {
    return hash(canonicalCompanionCapsuleJson(unsigned)) === contentHash;
  }
  catch {
    return false;
  }
}
