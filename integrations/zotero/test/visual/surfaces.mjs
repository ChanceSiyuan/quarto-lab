/**
 * The markup the layout checks lay out.
 *
 * Written by hand rather than driven from `sidebar.ts` because these fixtures
 * have to stay legible as *shapes* — the point is to reproduce a reported
 * clipping at a real pane width, not to re-test the DOM builders that
 * `sidebar.test.ts` already covers.
 */

const chip = (label) =>
  `<span class="zc-context-chip"><span class="zc-context-chip-icon">P</span>` +
  `<span class="zc-context-chip-label">${label}</span></span>`;

const option = (title, detail) =>
  `<button class="zc-context-option"><span class="zc-context-option-mark">P</span>` +
  `<span><strong>${title}</strong><small>${detail}</small></span></button>`;

/** The composer with enough chips to wrap onto a third row. */
export function composerWithChips(count) {
  const chips = Array.from({ length: count }, (_, index) => chip(`上下文 ${index + 1}`)).join("");
  return `<section class="zc-sidebar zc-workbench-chat" data-mode="agent">
    <div class="zc-composer-wrap">
      <div class="zc-composer">
        <div class="zc-composer-chips">${chips}
          <button class="zc-add-context-button"></button>
        </div>
        <textarea class="zc-composer-input" rows="1"></textarea>
        <div class="zc-composer-footer"><div class="zc-composer-controls"></div></div>
      </div>
    </div>
  </section>`;
}

/** The @-context menu with more options than fit. */
export function composerWithContextMenu(count) {
  const options = Array.from(
    { length: count },
    (_, index) => option(`选项 ${index + 1}`, "一段足够长的说明文字, 用来撑开这一行"),
  ).join("");
  return `<section class="zc-sidebar zc-workbench-chat" data-mode="agent">
    <div class="zc-composer-wrap">
      <div class="zc-composer">
        <div class="zc-composer-chips"><button class="zc-add-context-button"></button></div>
        <section class="zc-context-menu">
          <header>Add Context<span>Type @ to filter</span></header>
          <div class="zc-context-menu-list">${options}</div>
        </section>
        <textarea class="zc-composer-input" rows="1"></textarea>
        <div class="zc-composer-footer"><div class="zc-composer-controls"></div></div>
      </div>
    </div>
  </section>`;
}

/** The preview toolbar at a narrow pane width. */
export function workspaceToolbar() {
  return `<section class="zc-sidebar zc-workbench-chat is-workspace-open" data-mode="agent">
    <section class="zc-qmd-workspace">
      <header class="zc-qmd-toolbar">
        <button class="zc-qmd-back" title="Back to AI">←</button>
        <button class="zc-qmd-quickopen-button" title="Open a QMD">⌕</button>
        <strong class="zc-qmd-path">drafts/learning_theo/Virtual_Distillation/majorityvote.qmd</strong>
        <span class="zc-qmd-tree-badge" data-tree="drafts">Draft</span>
        <button class="zc-qmd-compliance" title="Draft checks passed">✓</button>
        <button class="zc-qmd-review" title="Add to Knowledge">↑</button>
        <button class="zc-qmd-compare" title="Show AI-modified Draft preview">◉</button>
        <button class="zc-qmd-change-keep" title="Keep AI version">✓</button>
        <select class="zc-qmd-editor-picker"><option>Cursor</option><option>VS Code</option></select>
        <button class="zc-qmd-edit-external" title="Edit in Cursor">✎</button>
        <button class="zc-qmd-refresh" title="Refresh Preview">↻</button>
      </header>
      <div class="zc-qmd-status">Preview ready · refreshes automatically after save</div>
      <div class="zc-qmd-compliance-details" hidden></div>
      <div class="zc-qmd-body">
        <nav class="zc-qmd-filecolumn"></nav>
        <button class="zc-qmd-file-toggle">‹</button>
        <div class="zc-qmd-render"></div>
      </div>
    </section>
  </section>`;
}
