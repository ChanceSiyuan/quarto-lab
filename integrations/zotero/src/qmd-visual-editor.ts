import { renderMarkdown } from "./markdown";
import {
  applyQmdVisualBlock,
  qmdMathSpans,
  visualQmdBlocks,
  type QmdMathSpan,
  type QmdVisualBlock,
} from "./qmd-source-model";

const SAVE_DELAY_MS = 420;

export interface QmdSourceSnapshot {
  source: string;
  revision: string;
}

export interface QmdVisualEditorOptions {
  save(source: string, expectedRevision: string): Promise<QmdSourceSnapshot>;
  onStatus?(message: string, state: "editing" | "saving" | "saved" | "conflict" | "error"): void;
}

interface ActiveEdit {
  block: QmdVisualBlock;
  element: HTMLTextAreaElement | HTMLInputElement;
  text: string;
  savedText: string;
  replacement(value: string): string;
  timer: ReturnType<typeof setTimeout> | null;
  saving: Promise<void> | null;
  closeAfterSave: boolean;
}

const SEMANTIC_LABELS: Record<string, string> = {
  thm: "Theorem",
  lem: "Lemma",
  def: "Definition",
  prp: "Proposition",
  cor: "Corollary",
  exm: "Example",
  proof: "Proof",
};

function theoremBody(source: string): string {
  const lines = source.replace(/\r\n?/g, "\n").split("\n").slice(1, -1);
  while (!lines[0]?.trim()) lines.shift();
  if (/^#{1,6}\s+/.test(lines[0] || "")) lines.shift();
  while (!lines[0]?.trim()) lines.shift();
  return lines.join("\n");
}

function frontmatterSummary(doc: Document, source: string): DocumentFragment {
  const fragment = doc.createDocumentFragment();
  const values = new Map<string, string>();
  for (const line of source.split(/\r?\n/).slice(1, -1)) {
    const match = /^(?<key>[A-Za-z][\w-]*):\s*(?<value>.*)$/.exec(line);
    const key = match?.groups?.key;
    const value = match?.groups?.value;
    if (key !== undefined && value !== undefined) values.set(key, value.replace(/^['"]|['"]$/g, ""));
  }
  const title = doc.createElement("strong");
  title.textContent = values.get("title") || "Document metadata";
  const description = doc.createElement("span");
  description.textContent = values.get("description") || "Click to edit YAML frontmatter";
  fragment.append(title, description);
  return fragment;
}

/**
 * A source-driven visual QMD editor. It never edits compiled HTML: every
 * visible region retains an exact source range and saves the QMD authority.
 */
export class QmdVisualEditor {
  readonly root: HTMLElement;

  private source = "";
  private revision = "";
  private editable = false;
  private active: ActiveEdit | null = null;
  private destroyed = false;

  constructor(private readonly doc: Document, private readonly options: QmdVisualEditorOptions) {
    this.root = doc.createElement("article");
    this.root.className = "zc-qmd-visual-editor";
    this.root.setAttribute("aria-label", "Visual QMD editor");
  }

  setDocument(snapshot: QmdSourceSnapshot, editable: boolean): void {
    this.cancelActive();
    this.source = snapshot.source;
    this.revision = snapshot.revision;
    this.editable = editable;
    this.render();
  }

  snapshot(): QmdSourceSnapshot {
    return { source: this.source, revision: this.revision };
  }

  isEditing(): boolean {
    return this.active !== null;
  }

  destroy(): void {
    this.destroyed = true;
    this.cancelActive();
    this.root.remove();
  }

  private render(): void {
    if (this.destroyed) return;
    this.root.replaceChildren();
    const counters = new Map<string, number>();
    for (const block of visualQmdBlocks(this.source)) {
      const element = this.renderBlock(block, counters);
      element.dataset.blockId = block.id;
      element.dataset.blockKind = block.kind;
      if (this.editable) {
        element.tabIndex = 0;
        element.title = block.kind === "theorem"
          ? "Click text to edit the whole QMD block; click a formula to edit only its LaTeX"
          : "Click to edit this QMD block";
        element.addEventListener("click", (event) => {
          if ((event.target as Element | null)?.closest(".zc-qmd-visual-math-editor")) return;
          this.openBlockEditor(block, element);
        });
        element.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && event.target === element) {
            event.preventDefault();
            this.openBlockEditor(block, element);
          }
        });
      }
      this.root.appendChild(element);
    }
  }

  private renderBlock(block: QmdVisualBlock, counters: Map<string, number>): HTMLElement {
    if (block.kind === "frontmatter") {
      const card = this.doc.createElement("section");
      card.className = "zc-qmd-visual-block zc-qmd-visual-frontmatter";
      card.appendChild(frontmatterSummary(this.doc, block.source));
      return card;
    }

    if (block.kind === "theorem" || block.kind === "callout") {
      const card = this.doc.createElement("section");
      card.className = `zc-qmd-visual-block zc-qmd-visual-card is-${block.semantic || "callout"}`;
      const header = this.doc.createElement("header");
      const semantic = block.semantic || "callout";
      const next = (counters.get(semantic) || 0) + 1;
      counters.set(semantic, next);
      const label = SEMANTIC_LABELS[semantic] || "Callout";
      header.textContent = `${label}${semantic === "proof" ? "" : ` ${next}`}${block.title ? `: ${block.title}` : ""}`;
      const body = this.doc.createElement("div");
      body.className = "zc-qmd-visual-card-body";
      body.appendChild(renderMarkdown(this.doc, theoremBody(block.source)));
      card.append(header, body);
      this.bindFormulaEditors(card, block);
      return card;
    }

    const wrapper = this.doc.createElement("section");
    wrapper.className = `zc-qmd-visual-block is-${block.kind}`;
    if (block.kind === "raw" || block.kind === "code") {
      const pre = this.doc.createElement("pre");
      pre.textContent = block.source;
      wrapper.appendChild(pre);
    }
    else {
      wrapper.appendChild(renderMarkdown(this.doc, block.source));
      this.bindFormulaEditors(wrapper, block);
    }
    return wrapper;
  }

  private bindFormulaEditors(container: HTMLElement, block: QmdVisualBlock): void {
    if (!this.editable) return;
    const spans = qmdMathSpans(block.source);
    const rendered = [...container.querySelectorAll<HTMLElement>(".zc-math-inline,.zc-math-display")];
    let cursor = 0;
    rendered.forEach((element) => {
      const latex = element.dataset.latex?.trim() || "";
      let spanIndex = spans.findIndex((candidate, index) => index >= cursor && candidate.latex.trim() === latex);
      if (spanIndex < 0) spanIndex = cursor;
      const span = spans[spanIndex];
      if (!span) return;
      cursor = spanIndex + 1;
      element.title = "Edit LaTeX";
      element.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        this.openFormulaEditor(block, span, element);
      });
    });
  }

  private openBlockEditor(block: QmdVisualBlock, element: HTMLElement): void {
    if (!this.editable || this.active) return;
    const textarea = this.doc.createElement("textarea");
    textarea.className = "zc-qmd-visual-source-editor";
    textarea.value = block.source;
    textarea.rows = Math.max(3, Math.min(28, block.source.split(/\r?\n/).length + 1));
    textarea.setAttribute("aria-label", block.kind === "theorem"
      ? "Edit theorem, lemma, or definition QMD source"
      : "Edit QMD source block");
    element.replaceChildren(textarea);
    this.beginEdit(block, textarea, (value) => value);
  }

  private openFormulaEditor(block: QmdVisualBlock, math: QmdMathSpan, element: HTMLElement): void {
    if (!this.editable || this.active) return;
    const editor = math.display ? this.doc.createElement("textarea") : this.doc.createElement("input");
    editor.className = "zc-qmd-visual-math-editor";
    editor.value = math.latex.trim();
    editor.setAttribute("aria-label", math.display ? "Edit display LaTeX" : "Edit inline LaTeX");
    element.replaceChildren(editor);
    this.beginEdit(block, editor, (value) => {
      const leading = /^\s*/.exec(math.latex)?.[0] || "";
      const trailing = /\s*$/.exec(math.latex)?.[0] || "";
      const latex = math.display ? value.trim() : value.replace(/\s+/g, " ").trim();
      return `${block.source.slice(0, math.start)}${leading}${latex}${trailing}${block.source.slice(math.end)}`;
    });
  }

  private beginEdit(
    block: QmdVisualBlock,
    element: HTMLTextAreaElement | HTMLInputElement,
    replacement: (value: string) => string,
  ): void {
    const initial = replacement(element.value);
    this.active = {
      block, element, text: initial, savedText: block.source,
      replacement, timer: null, saving: null, closeAfterSave: false,
    };
    element.addEventListener("input", () => {
      if (!this.active || this.active.element !== element) return;
      this.active.text = this.active.replacement(element.value);
      this.options.onStatus?.("Editing Draft…", "editing");
      this.scheduleSave();
    });
    element.addEventListener("keydown", (event) => {
      const keyboard = event as KeyboardEvent;
      if (keyboard.key === "Escape") {
        keyboard.preventDefault();
        this.cancelActive();
        this.render();
      }
      else if (keyboard.key === "Enter" && element.tagName === "INPUT") {
        keyboard.preventDefault();
        element.blur();
      }
    });
    element.addEventListener("blur", () => {
      if (!this.active || this.active.element !== element) return;
      this.active.text = this.active.replacement(element.value);
      this.active.closeAfterSave = true;
      void this.flushActive();
    });
    element.focus();
    element.select();
  }

  private scheduleSave(): void {
    const active = this.active;
    if (!active) return;
    if (active.timer) clearTimeout(active.timer);
    active.timer = setTimeout(() => {
      active.timer = null;
      void this.flushActive();
    }, SAVE_DELAY_MS);
  }

  private async flushActive(): Promise<void> {
    const active = this.active;
    if (!active) return;
    if (active.timer) { clearTimeout(active.timer); active.timer = null; }
    if (active.saving) {
      await active.saving;
      if (this.active === active && active.text !== active.savedText) return this.flushActive();
      return;
    }
    if (active.text === active.savedText) {
      if (active.closeAfterSave) { this.active = null; this.render(); }
      return;
    }
    const textAtStart = active.text;
    const task = (async () => {
      this.options.onStatus?.("Saving Draft…", "saving");
      const result = applyQmdVisualBlock(this.source, active.block, textAtStart);
      if (!result.changed) { active.savedText = textAtStart; return; }
      const snapshot = await this.options.save(result.source, this.revision);
      if (this.destroyed || this.active !== active) return;
      this.source = snapshot.source;
      this.revision = snapshot.revision;
      active.savedText = textAtStart;
      const next = visualQmdBlocks(this.source).find((candidate) => candidate.start === active.block.start)
        || visualQmdBlocks(this.source).find((candidate) => candidate.source === textAtStart);
      if (next) active.block = next;
      this.options.onStatus?.("Draft saved · website preview is rebuilding", "saved");
    })().catch((error) => {
      this.options.onStatus?.(
        error instanceof Error ? error.message : String(error),
        /changed|conflict|revision/i.test(String(error)) ? "conflict" : "error",
      );
      active.closeAfterSave = false;
    }).finally(() => {
      if (this.active === active) active.saving = null;
    });
    active.saving = task;
    await task;
    if (this.active !== active) return;
    if (active.text !== active.savedText) return this.flushActive();
    if (active.closeAfterSave) { this.active = null; this.render(); }
  }

  private cancelActive(): void {
    if (!this.active) return;
    if (this.active.timer) clearTimeout(this.active.timer);
    this.active = null;
  }
}
