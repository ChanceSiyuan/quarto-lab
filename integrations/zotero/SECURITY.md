# Security model

QLab runs inside Zotero and communicates only with the locally installed Codex
CLI. It has no Claude backend, remote SSH transport, external model-provider
configuration, or API-key store.

## Trust boundaries

- The Reader exposes only approval-gated Agent mode; there is no mode switch.
  Network access is disabled. Its ordinary writable roots are the
  selected QLab repository's `literature/`, `drafts/`, and generated `work/`.
- `knowledge/` is trusted content. A promotion command only prepares an exact
  proposal; applying it requires a later, explicit user approval and must be
  followed by `make knowledge-check`.
- PDF text, annotations, bibliographic fields, filenames, LaTeX, Markdown, and
  model output are untrusted input. None of them counts as user approval.
- Draft and Knowledge previews use the repository's local Make targets. They
  never deploy content.

The optional advanced terminal starts only local Codex in a read-only sandbox
with user-reviewed escalation. An escalation approved inside that terminal is
a full local Codex action and is not constrained by the structured command
palette, so users should inspect it carefully.

## Zotero and PDF changes

Structured changes to Zotero metadata, collection membership, attachment
links, or PDF bytes are rendered as a Diff. Only the user's Apply click can
continue. The plugin revalidates the target and creates a checkpoint first.
Recovery is best-effort and is not a substitute for Zotero sync history or a
filesystem backup.

The QLab literature importer is separate. It reads QLab metadata and creates or
refreshes a `QLab Literature` collection in Zotero. Existing PDF and LaTeX files
are linked as attachments; the importer does not move, copy, or delete them.

## Local process and credentials

The bundled macOS helper uses a profile-private Unix-domain socket and a fresh
secret. Codex authentication remains owned by the installed Codex CLI; the
plugin does not read or copy Codex token files, browser cookies, Zotero Web API
keys, or model-provider keys.

Zotero extensions and a user-approved local agent have broad account-level
capabilities. Install XPI files only from a trusted source and keep independent
backups before material changes.
