/**
 * Decides whether a knowledge graph may be published.
 *
 * Validation is the gate every other consumer stands behind: the projection
 * copies only files this module has accepted, the resolver refuses to answer
 * from an invalid graph, and the site build never starts without a clean
 * report. So the rule here is completeness, not speed — one run reports every
 * problem in the tree, sorted, with a true one-based location, and a page with
 * ten mistakes yields ten diagnostics rather than hiding nine of them.
 *
 * The diagnostics this module adds to the parser's are:
 *
 * ```text
 * TOPIC_INDEX_MISSING        a directory holds pages but has no index.qmd
 * INDEX_READING_MAP_REQUIRED an index declares no `## Reading map` section
 * RESERVED_SECTION_FORBIDDEN a content page declares a curated section
 * ORPHAN_CHILD               no reading map lists a page its parent owns
 * NON_DIRECT_CHILD           a reading map claims something it cannot own
 * DUPLICATE_PARENT           two reading maps list the same page
 * CONTAINMENT_CYCLE          reading maps contain each other
 * RELATED_TARGET_NOT_INDEX   `## Related topics` links to a non-index
 * LINK_MISSING               a local link or image resolves to nothing
 * LINK_OUTSIDE_KNOWLEDGE     a link leaves the knowledge tree, or is excluded
 * SYMLINK_FORBIDDEN          a symbolic link in the tree, or a link through one
 * CITATION_MISSING           a citekey is absent from the bibliography
 * SCRIPT_FORBIDDEN           a page carries a raw `<script` tag
 * INLINE_HANDLER_FORBIDDEN   a page carries a raw event-handler attribute
 * ALIAS_PATH_FORBIDDEN       an alias Quarto would write as a redirect path
 * ```
 *
 * The parser's own codes are forwarded unchanged. One of them is a gate rather
 * than a complaint about form: `FENCE_UNCLOSED` fires when a fenced code block
 * never closes, because remark then reads the rest of the page as code while
 * Pandoc reads it as Markdown — so every link, citation, and curated entry
 * below the opener is invisible to *these* checks and visible to the renderer.
 * A page that cannot be read the same way twice is not a page this module can
 * decide about, so it fails.
 *
 * Every check reports the *cause* once. A missing `index.qmd` does not also
 * orphan the pages it would have owned, an index without a reading map does not
 * orphan its children, and a link that resolves to nothing is reported by the
 * link check rather than a second time by the containment check. A cascade
 * would bury the one line the author has to fix.
 *
 * Containment diagnostics that concern a page as a whole (`ORPHAN_CHILD`,
 * `DUPLICATE_PARENT`) are reported at the top of that page and name the reading
 * maps involved; diagnostics that concern one curated entry are reported at the
 * entry. So "which page is wrong?" and "which line do I edit?" are both
 * answerable, whichever way the author reads the report.
 */

import path from "node:path";

import { loadBibliography } from "../literature/bibliography.js";

import {
  comparePosix,
  declaresSection,
  diagnosticFile,
  indexIdOf,
  loadKnowledge,
  parentIdOf,
  resolvePageTargets,
  walkKnowledgeTree,
  type KnowledgeGraph,
  type LoadKnowledgeOptions,
  type TargetResolution,
  type UnresolvableReason,
} from "./graph.js";
import { INDEX_FILENAME, READING_MAP_HEADING, RELATED_TOPICS_HEADING } from "./parser.js";
import {
  isPathLikeAlias,
  type Diagnostic,
  type ParsedKnowledgePage,
  type SourceLocation,
} from "./types.js";

/** The bibliography a knowledge tree is validated against by default. */
export const BIBLIOGRAPHY_PATH = "literature/ref.bib";

export interface ValidationReport {
  ok: boolean;
  diagnostics: readonly Diagnostic[];
}

/**
 * Thrown when a consumer that may only act on a valid tree is handed an invalid
 * one — the resolver, and later the site build.
 *
 * It carries the complete report rather than the first problem, and its message
 * lists every diagnostic, so a caller that does nothing but print `message`
 * still shows the author everything they have to fix. Validation reports the
 * whole tree in one pass precisely so that this error can too.
 */
export class KnowledgeValidationError extends Error {
  readonly report: ValidationReport;
  readonly diagnostics: readonly Diagnostic[];

  constructor(report: ValidationReport) {
    const { diagnostics } = report;
    super(
      [
        `the knowledge tree has ${diagnostics.length} problem${diagnostics.length === 1 ? "" : "s"}:`,
        ...diagnostics.map(formatDiagnostic),
      ].join("\n"),
    );
    this.name = "KnowledgeValidationError";
    this.report = report;
    this.diagnostics = diagnostics;
  }
}

/** One diagnostic as a line: `file:line:column CODE message`. */
function formatDiagnostic(diagnostic: Diagnostic): string {
  return `${formatLocation(diagnostic.location)} ${diagnostic.code} ${diagnostic.message}`;
}

/**
 * The bibliography a tree is checked against: the one the caller configured, or
 * the one the repository keeps. Every entry point resolves it here, so "which
 * bibliography validated this tree?" has exactly one answer.
 */
export function bibliographyPathFor(repoRoot: string, configured?: string): string {
  return configured === undefined
    ? path.join(repoRoot, ...BIBLIOGRAPHY_PATH.split("/"))
    : path.resolve(configured);
}

/** Which code an unusable link target is reported under. */
const LINK_CODE: Readonly<Record<UnresolvableReason, string>> = {
  missing: "LINK_MISSING",
  "not-a-file": "LINK_MISSING",
  "not-a-page": "LINK_MISSING",
  // The file may well exist; what it is not is part of the knowledge tree,
  // which is what `LINK_OUTSIDE_KNOWLEDGE` says. Reporting it as "missing"
  // would send an author looking for a typo instead of moving the file.
  excluded: "LINK_OUTSIDE_KNOWLEDGE",
  outside: "LINK_OUTSIDE_KNOWLEDGE",
  symlink: "SYMLINK_FORBIDDEN",
};

/** One entry of a reading map, resolved to the page it claims. */
interface Claim {
  /** The claimed page. */
  child: string;
  /** The index whose reading map claims it. */
  parent: string;
  location: SourceLocation;
}

function compareLocations(left: SourceLocation, right: SourceLocation): number {
  return (
    comparePosix(left.file, right.file) ||
    left.line - right.line ||
    left.column - right.column
  );
}

function compareDiagnostics(left: Diagnostic, right: Diagnostic): number {
  return (
    compareLocations(left.location, right.location) ||
    comparePosix(left.code, right.code) ||
    comparePosix(left.message, right.message)
  );
}

function formatLocation(location: SourceLocation): string {
  return `${location.file}:${location.line}:${location.column}`;
}

/**
 * Checks one loaded graph against one bibliography.
 *
 * The bibliography is loaded even when no page cites anything: a knowledge tree
 * that is validated against an unreadable bibliography has not been validated,
 * and `loadBibliography` already fails loudly rather than dropping entries.
 */
export async function validateGraph(
  graph: KnowledgeGraph,
  options: { bibliographyPath: string },
): Promise<ValidationReport> {
  const diagnostics: Diagnostic[] = [];
  const report = (code: string, message: string, location: SourceLocation): void => {
    diagnostics.push({ code, message, location });
  };

  // Sorted once, then used everywhere: no check may depend on the order the
  // filesystem happened to hand the pages over in.
  const pages = [...graph.pages.values()].sort((left, right) =>
    comparePosix(left.id, right.id),
  );
  const fileOf = (page: ParsedKnowledgePage): string =>
    diagnosticFile(graph.repoRoot, page.absolutePath);
  const pageStart = (page: ParsedKnowledgePage): SourceLocation => ({
    file: fileOf(page),
    line: 1,
    column: 1,
  });

  // 1. Everything the parser already knows, including the frontmatter
  // allowlist. A page that does not parse cleanly cannot be published.
  for (const page of pages) {
    diagnostics.push(...page.parseDiagnostics);

    // The allowlist admits `aliases` for the resolver, which reads them as
    // synonyms; Quarto reads the same key as redirect *paths* and builds a
    // directory out of each one, so a separator or a `..` there is a render
    // that writes outside the output directory. The projection refuses these
    // too — this is the same `isPathLikeAlias`, reported at review time so the
    // author hears about it before a build fails.
    for (const alias of page.aliases) {
      if (isPathLikeAlias(alias)) {
        report(
          "ALIAS_PATH_FORBIDDEN",
          `the alias ${JSON.stringify(alias)} looks like a path; Quarto publishes every alias as a redirect directory of that name, so an alias may only be another name for the page — no \`/\`, \`\\\`, \`.\`, \`..\`, or \`~\``,
          pageStart(page),
        );
      }
    }

    for (const unsafe of page.unsafeHtml) {
      report(
        unsafe.kind === "script" ? "SCRIPT_FORBIDDEN" : "INLINE_HANDLER_FORBIDDEN",
        unsafe.kind === "script"
          ? "a knowledge page may not contain a raw `<script` tag; put example markup in a fenced code block"
          : "a knowledge page may not contain a raw event-handler attribute; put example markup in a fenced code block",
        unsafe.location,
      );
    }
  }

  // 2. Symbolic links in the tree. The walk refuses to follow them, so they are
  // invisible to every check below; Quarto, which renders `knowledge/` as a
  // project, follows them happily. Reporting them here is what keeps "not in
  // the graph" and "not on the site" the same statement.
  for (const id of (await walkKnowledgeTree(graph.knowledgeRoot)).symlinkIds) {
    report(
      "SYMLINK_FORBIDDEN",
      "a symbolic link inside the knowledge tree is never validated and never published; replace it with the file itself",
      {
        file: diagnosticFile(
          graph.repoRoot,
          path.join(graph.knowledgeRoot, ...id.split("/")),
        ),
        line: 1,
        column: 1,
      },
    );
  }

  // 3. Every directory holding pages is a topic, and a topic has an index.
  const directories = new Set<string>([""]);
  for (const page of pages) {
    let directory = path.posix.dirname(page.id);
    while (directory !== "." && directory !== "" && directory !== "/") {
      directories.add(directory);
      directory = path.posix.dirname(directory);
    }
  }
  for (const directory of [...directories].sort(comparePosix)) {
    const id = indexIdOf(directory);
    if (graph.pages.has(id)) {
      continue;
    }
    report(
      "TOPIC_INDEX_MISSING",
      `${directory === "" ? "the knowledge tree" : `\`${directory}\``} holds knowledge pages but has no \`${INDEX_FILENAME}\`; a directory is a topic only when it carries one`,
      {
        file: diagnosticFile(graph.repoRoot, path.join(graph.knowledgeRoot, ...id.split("/"))),
        line: 1,
        column: 1,
      },
    );
  }

  // 4. Where every local link and image actually points.
  const resolutions = new Map<string, ReadonlyMap<string, TargetResolution>>();
  for (const page of pages) {
    resolutions.set(page.id, await resolvePageTargets(graph, page));
  }
  const resolutionOf = (
    page: ParsedKnowledgePage,
    target: string,
  ): TargetResolution | undefined => resolutions.get(page.id)?.get(target);

  for (const page of pages) {
    for (const link of page.localLinks) {
      const resolution = resolutionOf(page, link.target);
      if (resolution === undefined || resolution.status !== "unresolvable") {
        continue;
      }
      report(
        LINK_CODE[resolution.reason],
        `\`${link.target}\` ${resolution.detail}`,
        link.location,
      );
    }
  }

  // 5. Curated containment: who claims whom, and may they.
  //
  // The curated sections are the contract of an *index*. On a content page they
  // are silently inert — nothing there owns anything — so an author who writes
  // one has either misunderstood the model or misplaced the page, and the links
  // they curated would never appear in any sidebar. Say so rather than render a
  // page whose reading map means nothing. The links inside such a section are
  // still ordinary local links and are checked by the pass above.
  const claims: Claim[] = [];
  const curates = new Set<string>();
  for (const page of pages) {
    if (page.kind !== "index") {
      for (const section of page.reservedSections) {
        report(
          "RESERVED_SECTION_FORBIDDEN",
          `\`## ${section.heading}\` is the curated contract of an \`${INDEX_FILENAME}\`; a content page cannot own or relate topics, so this section would be ignored`,
          section.location,
        );
      }
      continue;
    }
    if (!declaresSection(page, READING_MAP_HEADING)) {
      report(
        "INDEX_READING_MAP_REQUIRED",
        `every \`${INDEX_FILENAME}\` needs a \`## ${READING_MAP_HEADING}\` section, even an empty one; it is the curated order of the topic`,
        pageStart(page),
      );
      continue;
    }
    curates.add(page.id);

    for (const entry of page.readingMap) {
      const resolution = resolutionOf(page, entry.target);
      if (resolution?.status === "unresolvable") {
        // Already reported, once, by the link check.
        continue;
      }
      if (resolution === undefined || resolution.status !== "page") {
        report(
          "NON_DIRECT_CHILD",
          `\`${entry.target}\` is not a knowledge page; a \`## ${READING_MAP_HEADING}\` lists only the pages of this topic and the indexes of its direct subtopics`,
          entry.location,
        );
        continue;
      }
      claims.push({ child: resolution.id, parent: page.id, location: entry.location });
      if (parentIdOf(resolution.id) !== page.id) {
        report(
          "NON_DIRECT_CHILD",
          `\`${resolution.id}\` is not a direct child of \`${page.id}\`; a \`## ${READING_MAP_HEADING}\` lists only the pages of its own directory and the indexes of its direct subdirectories`,
          entry.location,
        );
      }
    }
  }

  const claimsByChild = new Map<string, Claim[]>();
  for (const claim of claims) {
    const existing = claimsByChild.get(claim.child);
    if (existing === undefined) {
      claimsByChild.set(claim.child, [claim]);
    } else {
      existing.push(claim);
    }
  }

  for (const page of pages) {
    const childClaims = (claimsByChild.get(page.id) ?? [])
      .slice()
      .sort((left, right) => compareLocations(left.location, right.location));
    if (childClaims.length > 1) {
      report(
        "DUPLICATE_PARENT",
        `this page is listed by more than one reading map (${childClaims.map((claim) => formatLocation(claim.location)).join(", ")}); a page has exactly one parent`,
        pageStart(page),
      );
    }

    const parent = parentIdOf(page.id);
    if (parent === undefined || !graph.pages.has(parent) || !curates.has(parent)) {
      // The root index has no parent; a parent that is missing or has no
      // reading map has already been reported on its own account.
      continue;
    }
    if (!childClaims.some((claim) => claim.parent === parent)) {
      const parentPage = graph.pages.get(parent);
      report(
        "ORPHAN_CHILD",
        `the reading map of \`${parentPage === undefined ? parent : fileOf(parentPage)}\` does not list this page; every page appears exactly once in the \`## ${READING_MAP_HEADING}\` of the topic that owns it`,
        pageStart(page),
      );
    }
  }

  reportContainmentCycles(pages, claims, report);

  // 6. Related topics: cross-references that change no ownership, but that must
  // still land on a topic index.
  for (const page of pages) {
    if (page.kind !== "index") {
      continue;
    }
    for (const entry of page.relatedTopics) {
      const resolution = resolutionOf(page, entry.target);
      if (resolution?.status === "unresolvable") {
        continue;
      }
      const target =
        resolution?.status === "page" ? graph.pages.get(resolution.id) : undefined;
      if (target?.kind !== "index") {
        report(
          "RELATED_TARGET_NOT_INDEX",
          `\`${entry.target}\` is not a topic index; \`## ${RELATED_TOPICS_HEADING}\` links only to an \`${INDEX_FILENAME}\``,
          entry.location,
        );
      }
    }
  }

  // 7. Citations, against the one bibliography the repository keeps.
  const citekeys = new Set(
    (await loadBibliography(options.bibliographyPath)).map((entry) => entry.citekey),
  );
  for (const page of pages) {
    for (const citation of page.citations) {
      if (!citekeys.has(citation.key)) {
        report(
          "CITATION_MISSING",
          `\`@${citation.key}\` is not defined in \`${options.bibliographyPath}\``,
          citation.location,
        );
      }
    }
  }

  diagnostics.sort(compareDiagnostics);
  return { ok: diagnostics.length === 0, diagnostics };
}

/**
 * Reports reading maps that contain one another.
 *
 * The claim graph is walked rather than the directory tree: a cycle cannot be
 * built out of directories, only out of curation, and every edge that could
 * close one is also a `NON_DIRECT_CHILD`. The check stays because containment
 * is what the resolver and the sidebar walk, and a ring there is an infinite
 * loop rather than a wrong answer — a second, independent line of defence for a
 * cheap depth-first search.
 *
 * Determinism comes from three places: the pages are visited in sorted order,
 * each cycle is keyed by its members rotated to start at the smallest id, and
 * the diagnostic is reported at the earliest curated entry that takes part.
 */
function reportContainmentCycles(
  pages: readonly ParsedKnowledgePage[],
  claims: readonly Claim[],
  report: (code: string, message: string, location: SourceLocation) => void,
): void {
  const edges = new Map<string, Claim[]>();
  for (const claim of claims) {
    const existing = edges.get(claim.parent);
    if (existing === undefined) {
      edges.set(claim.parent, [claim]);
    } else {
      existing.push(claim);
    }
  }

  const state = new Map<string, "visiting" | "done">();
  const stack: string[] = [];
  const reported = new Set<string>();

  const edgeBetween = (parent: string, child: string): Claim | undefined =>
    (edges.get(parent) ?? []).find((claim) => claim.child === child);

  const reportCycle = (members: readonly string[]): void => {
    let smallest = 0;
    for (let index = 1; index < members.length; index += 1) {
      if (comparePosix(members[index], members[smallest]) < 0) {
        smallest = index;
      }
    }
    const rotated = [...members.slice(smallest), ...members.slice(0, smallest)];
    const key = rotated.join("\n");
    if (reported.has(key)) {
      return;
    }
    reported.add(key);

    const locations: SourceLocation[] = [];
    for (let index = 0; index < rotated.length; index += 1) {
      const claim = edgeBetween(rotated[index], rotated[(index + 1) % rotated.length]);
      if (claim !== undefined) {
        locations.push(claim.location);
      }
    }
    locations.sort(compareLocations);
    const location = locations[0];
    if (location === undefined) {
      return;
    }
    report(
      "CONTAINMENT_CYCLE",
      `the reading maps of ${rotated.map((id) => `\`${id}\``).join(" and ")} contain each other (${[...rotated, rotated[0]].join(" → ")}); containment must be a tree`,
      location,
    );
  };

  const visit = (id: string): void => {
    state.set(id, "visiting");
    stack.push(id);
    for (const claim of edges.get(id) ?? []) {
      const status = state.get(claim.child);
      if (status === "visiting") {
        reportCycle(stack.slice(stack.indexOf(claim.child)));
      } else if (status === undefined) {
        visit(claim.child);
      }
    }
    stack.pop();
    state.set(id, "done");
  };

  for (const page of pages) {
    if (state.get(page.id) === undefined) {
      visit(page.id);
    }
  }
}

/** Loads the knowledge tree and validates it against the bibliography. */
export async function validateKnowledge(
  options: LoadKnowledgeOptions & { bibliographyPath?: string } = {},
): Promise<ValidationReport> {
  const graph = await loadKnowledge(options);
  return validateGraph(graph, {
    bibliographyPath: bibliographyPathFor(graph.repoRoot, options.bibliographyPath),
  });
}
