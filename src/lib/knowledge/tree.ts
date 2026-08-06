/**
 * The topic tree block: a ```qlab-tree YAML fence on the root index page that
 * the site renders as an interactive canvas.
 *
 * This module owns extraction, validation, and compilation. Validation joins
 * `knowledge-check` (see validate.ts), so a malformed block fails the build
 * with line-numbered diagnostics; the browser only ever receives compiled
 * JSON. Compilation is deterministic — identical input yields deep-equal
 * output — because the projection embeds its result byte-for-byte.
 */

import { parse as parseYaml } from "yaml";

export interface TreeDiagnostic {
  code: string;
  message: string;
  /** 1-based source line — the fence line for whole-block problems. */
  line: number;
}

export interface CompiledTreeNode {
  /** Slug of the label path, e.g. "tensor-networks/mps-dmrg". */
  id: string;
  label: string;
  /** Site URL of the note page, or null for a grey link. */
  noteUrl: string | null;
  zotero: string | null;
  x: number | null;
  y: number | null;
  children: CompiledTreeNode[];
}

export interface CompiledTree {
  root: string;
  nodes: CompiledTreeNode[];
}

const FENCE = /^```([^`\n]*)\s*$/;
const TREE_FENCE_INFO = "qlab-tree";
const DEFAULT_ROOT_TITLE = "Research Knowledge";

/** Finds the ```qlab-tree fence; null when the page has none (or it never closes). */
export function extractTreeBlock(
  source: string,
): { yamlText: string; startLine: number } | null {
  const lines = source.split("\n");
  let inOtherFence = false;
  for (let index = 0; index < lines.length; index += 1) {
    const match = FENCE.exec(lines[index] ?? "");
    if (!match) continue;
    const info = (match[1] ?? "").trim();
    if (inOtherFence) {
      if (info === "") inOtherFence = false;
      continue;
    }
    if (info !== TREE_FENCE_INFO) {
      // Any other opener (named or anonymous) swallows lines until its closer.
      inOtherFence = true;
      continue;
    }
    // Opening qlab-tree fence found; collect until the closing fence.
    for (let end = index + 1; end < lines.length; end += 1) {
      const closer = FENCE.exec(lines[end] ?? "");
      if (closer && (closer[1] ?? "").trim() === "") {
        return {
          yamlText: lines.slice(index + 1, end).join("\n"),
          startLine: index + 1,
        };
      }
    }
    return null; // unclosed — the parser's FENCE_UNCLOSED already reports it
  }
  return null;
}

export function compileTree(input: {
  yamlText: string;
  startLine: number;
  pages: ReadonlySet<string>;
  sitePath: string;
}): { tree: CompiledTree | null; diagnostics: TreeDiagnostic[] } {
  const diagnostics: TreeDiagnostic[] = [];
  const report = (code: string, message: string): void => {
    diagnostics.push({ code, message, line: input.startLine });
  };

  let document: unknown;
  try {
    document = parseYaml(input.yamlText);
  }
  catch (error) {
    report(
      "TREE_YAML_INVALID",
      `the qlab-tree block is not valid YAML: ${error instanceof Error ? error.message : String(error)}`,
    );
    return { tree: null, diagnostics };
  }
  if (typeof document !== "object" || document === null || Array.isArray(document)) {
    report("TREE_YAML_INVALID", "the qlab-tree block must be a YAML mapping");
    return { tree: null, diagnostics };
  }
  const mapping = document as { root?: unknown; nodes?: unknown };
  if (mapping.nodes !== undefined && !Array.isArray(mapping.nodes)) {
    report("TREE_YAML_INVALID", "`nodes` must be a list of nodes");
    return { tree: null, diagnostics };
  }
  const root = typeof mapping.root === "string" && mapping.root.trim()
    ? mapping.root.trim()
    : DEFAULT_ROOT_TITLE;

  const compileNodes = (raw: unknown[], parentPath: string): CompiledTreeNode[] => {
    const siblings = new Set<string>();
    const compiled: CompiledTreeNode[] = [];
    for (const entry of raw) {
      if (typeof entry !== "object" || entry === null || Array.isArray(entry)) {
        report("TREE_YAML_INVALID", "every node must be a YAML mapping");
        continue;
      }
      const node = entry as {
        label?: unknown;
        note?: unknown;
        zotero?: unknown;
        x?: unknown;
        y?: unknown;
        children?: unknown;
      };
      const label = typeof node.label === "string" ? node.label.trim() : "";
      if (!label) {
        report("TREE_LABEL_INVALID", "every node needs a non-empty `label`");
        continue;
      }
      if (siblings.has(label.toLowerCase())) {
        report("TREE_LABEL_INVALID", `sibling labels must be unique: "${label}"`);
        continue;
      }
      siblings.add(label.toLowerCase());
      const id = parentPath ? `${parentPath}/${slugify(label)}` : slugify(label);

      let noteUrl: string | null = null;
      if (node.note !== undefined) {
        const note = typeof node.note === "string" ? node.note : "";
        if (!input.pages.has(note)) {
          report("TREE_NOTE_MISSING", `\`${String(node.note)}\` is not a page of the knowledge tree`);
        }
        else {
          noteUrl = input.sitePath + note.replace(/\.qmd$/u, ".html");
        }
      }

      let zotero: string | null = null;
      if (node.zotero !== undefined) {
        const link = typeof node.zotero === "string" ? node.zotero : "";
        if (!link.startsWith("zotero://")) {
          report("TREE_LINK_SCHEME", `\`zotero\` must be a zotero:// link, got \`${String(node.zotero)}\``);
        }
        else {
          zotero = link;
        }
      }

      const coordinate = (value: unknown, name: string): number | null => {
        if (value === undefined) return null;
        if (typeof value !== "number" || !Number.isFinite(value)) {
          report("TREE_COORD_INVALID", `\`${name}\` of "${label}" must be a finite number`);
          return null;
        }
        return value;
      };
      const x = coordinate(node.x, "x");
      const y = coordinate(node.y, "y");

      let children: CompiledTreeNode[] = [];
      if (node.children !== undefined) {
        if (!Array.isArray(node.children)) {
          report("TREE_YAML_INVALID", `\`children\` of "${label}" must be a list`);
        }
        else {
          children = compileNodes(node.children, id);
        }
      }
      compiled.push({ id, label, noteUrl, zotero, x, y, children });
    }
    return compiled;
  };

  const nodes = compileNodes(Array.isArray(mapping.nodes) ? mapping.nodes : [], "");
  if (diagnostics.length > 0) return { tree: null, diagnostics };
  return { tree: { root, nodes }, diagnostics };
}

function slugify(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/gu, "-")
    .replace(/^-+|-+$/gu, "") || "node";
}
