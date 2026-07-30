/**
 * Advisory, single-file readiness checks for a Draft being viewed by a human.
 *
 * A passing result means the note satisfies the parts of the trusted Knowledge
 * contract that can be decided without choosing its destination: frontmatter,
 * category, safe renderable Markdown, and bibliography-backed citations. It
 * does not promote the note and it does not replace the `review-draft` review.
 */

import { readFile } from "node:fs/promises";
import path from "node:path";

import { isMap, isScalar, parseDocument } from "yaml";

import { parseKnowledgePage } from "../knowledge/parser.js";
import type { Diagnostic } from "../knowledge/types.js";
import { loadBibliography } from "../literature/bibliography.js";
import { DRAFTS_DIRECTORY, resolveDraftFile } from "./preview.js";

const REQUIRED_FIELDS = ["title", "description", "categories"] as const;
const OPTIONAL_FIELD = "aliases" as const;

export interface DraftComplianceDiagnostic {
  code: string;
  message: string;
  line: number;
}

export interface DraftComplianceResult {
  ok: boolean;
  relativePath: string;
  diagnostics: DraftComplianceDiagnostic[];
}

export interface CheckDraftOptions {
  repoRoot: string;
  requestedFile: string;
}

function exactFrontmatterFields(source: string): DraftComplianceDiagnostic[] {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|$)/);
  if (!match) return [];

  const document = parseDocument(match[1]!, { prettyErrors: false, uniqueKeys: true });
  if (document.errors.length || !isMap(document.contents)) return [];
  const fields = document.contents.items.map((pair) =>
    isScalar(pair.key) ? String(pair.key.value) : String(pair.key));
  const requiredFieldsMatch = REQUIRED_FIELDS.every((field, index) => fields[index] === field);
  const hasOnlyRequiredFields = fields.length === REQUIRED_FIELDS.length;
  const hasOptionalAliases = fields.length === REQUIRED_FIELDS.length + 1
    && fields[REQUIRED_FIELDS.length] === OPTIONAL_FIELD;
  if (requiredFieldsMatch && (hasOnlyRequiredFields || hasOptionalAliases)) return [];

  return [{
    code: "DRAFT_FRONTMATTER_FIELDS",
    message: "a promotion-ready Draft must contain `title`, `description`, and `categories`, in that order, with optional `aliases` last",
    line: 1,
  }];
}

function compactDiagnostic(diagnostic: Diagnostic): DraftComplianceDiagnostic {
  return {
    code: diagnostic.code,
    message: diagnostic.message,
    line: diagnostic.location.line,
  };
}

function uniqueSorted(
  diagnostics: readonly DraftComplianceDiagnostic[],
): DraftComplianceDiagnostic[] {
  const seen = new Set<string>();
  return [...diagnostics]
    .sort((left, right) => left.line - right.line || left.code.localeCompare(right.code))
    .filter((diagnostic) => {
      const key = `${diagnostic.line}\u0000${diagnostic.code}\u0000${diagnostic.message}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

/** Checks one real file inside drafts/ without writing anywhere. */
export async function checkDraft(options: CheckDraftOptions): Promise<DraftComplianceResult> {
  const resolved = await resolveDraftFile(options);
  const relativePath = `${DRAFTS_DIRECTORY}/${resolved.relativeFile}`;
  const source = await readFile(resolved.absoluteFile, "utf8");

  // Always parse as a content page. A Draft named index.qmd is still a note
  // awaiting placement; it has not become trusted topic navigation yet.
  const syntheticRoot = path.join(path.resolve(options.repoRoot), ".draft-readiness");
  const parsed = parseKnowledgePage({
    repoRoot: path.resolve(options.repoRoot),
    knowledgeRoot: syntheticRoot,
    absolutePath: path.join(syntheticRoot, "draft.qmd"),
    source,
  });
  const diagnostics: DraftComplianceDiagnostic[] = [
    ...exactFrontmatterFields(source),
    ...parsed.parseDiagnostics.map(compactDiagnostic),
    ...parsed.unsafeHtml.map((unsafe) => ({
      code: unsafe.kind === "script" ? "SCRIPT_FORBIDDEN" : "INLINE_HANDLER_FORBIDDEN",
      message: unsafe.kind === "script"
        ? "a trusted Knowledge page may not contain a raw `<script` tag"
        : "a trusted Knowledge page may not contain a raw event-handler attribute",
      line: unsafe.location.line,
    })),
  ];

  try {
    const citekeys = new Set(
      (await loadBibliography(path.join(options.repoRoot, "literature", "ref.bib")))
        .map((entry) => entry.citekey),
    );
    for (const citation of parsed.citations) {
      if (!citekeys.has(citation.key)) diagnostics.push({
        code: "CITATION_MISSING",
        message: `\`@${citation.key}\` is not defined in \`literature/ref.bib\``,
        line: citation.location.line,
      });
    }
  }
  catch (error) {
    diagnostics.push({
      code: "BIBLIOGRAPHY_INVALID",
      message: error instanceof Error ? error.message : String(error),
      line: 1,
    });
  }

  const result = uniqueSorted(diagnostics);
  return { ok: result.length === 0, relativePath, diagnostics: result };
}
