# QLab Zotero integration

The Zotero 9 extension joins two local workflows without merging their data
models:

1. It imports the selected repository's `literature/` metadata and nested
   collection structure into a Zotero collection named `QLab Literature`.
2. It creates the full QLab Workbench as a native Zotero document tab. Chat
   connects to `codex app-server` beside either the local repository or a
   selected SSH repository. QLab does not register an item-pane or
   Reader-sidebar section.

## Reader flow

```text
Zotero PDF / Tools menu -> native QLab Workbench tab -> Codex on target
                                 |          |
                                 |          `-> optional compact float
                                 v
                    optional Zotero paper selector
                                              |
                                              v
                                      selected QLab repository
                                      |- literature/
                                      |- drafts/
                                      |- knowledge/ (reviewed promotion only)
                                      `- work/ (generated local state)
```

The user first chooses a local QLab root containing `AGENTS.md`, `qlab`,
`literature/`, `drafts/`, and `knowledge/`. The path is stored in Zotero's local
preferences and can be changed from the Workbench or Tools menu. The Workbench
can be created empty; its paper card opens Zotero's native item selector and
binds the chosen regular item or PDF attachment as optional conversation
context. Once a paper is bound, **Open PDF** creates or selects its normal
Zotero Reader tab while the QLab tab remains available beside it.

The Workbench's Terminal control raises a bottom drawer without replacing the
conversation. The drawer starts a real local shell in the selected QLab root,
keeps its PTY alive when collapsed, and offers a switch to the local Codex CLI.
Direct shell commands are user-controlled actions outside the Agent approval
boundary.

The Workbench exposes these stable operations as direct buttons:

- `qlab_get_paper`: resolve the active parent item key to its paper directory.
- `qlab_search_literature`: search local metadata, Markdown, LaTeX, and assets.
- `qlab_propose_patch`: edit only `literature/` and `drafts/` for a described
  task, then show the diff.
- `qlab_propose_promotion`: prepare a review-only `drafts/` to `knowledge/`
  promotion proposal and wait for later explicit approval.
- `qlab_validate`: run the repository's literature and Knowledge checks.
- `qlab_preview`: start the stable Drafts or Knowledge local preview and open
  its localhost address in the system browser.

Choosing a command inserts a complete prompt into the composer. The user can
fill placeholders or edit any detail before sending it.

The **Organize this chat into a Draft** action invokes `capture-chat-draft` in the active
conversation and writes a grounded reading note under `drafts/reading-notes/`.

The Workbench uses Zotero's native tab deck rather than a floating overlay.
Consequently it participates in tab drag ordering, close/close-others,
show-in-library, duplicate, undo-close, session restore, and move-to-window
flows. The compact float intentionally shows only the latest exchange.

## Runtime policy

The UI exposes only approval-gated Agent mode; there is no Ask/Agent selector.
Agent has no network access and ordinarily writes only to `literature/`,
`drafts/`, and generated `work/`. The active PDF and
Reader context are untrusted source material. Promotion into `knowledge/`
requires a reviewed diff, a later explicit approval, and
`make knowledge-check` after application.

There is no Claude runtime, model-provider form, or direct API-key transport.
Authentication and model discovery come from the
Codex CLI installed on the selected local or SSH host. SSH Chat uses a
versioned, checksum-verified helper embedded in the XPI; it never copies
repository content or Codex credentials. Remote preview, Terminal, Main Site,
external editing, initialization, and promotion are deliberately unavailable
until their target-owned implementations land.

## Build

From the repository root:

```bash
make zotero-plugin-test
make zotero-plugin
```

The installable XPI is generated in `integrations/zotero/dist/`. The bundled
local helper is a universal macOS binary for Intel and Apple Silicon. Building
the XPI also requires Zig (or `ZIG=/absolute/path/to/zig`) to produce the
statically linked x86_64 and ARM64 Linux remote helpers.
