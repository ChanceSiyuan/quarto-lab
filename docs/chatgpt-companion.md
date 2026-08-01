# ChatGPT Companion

ChatGPT Companion is a safe handoff between the QLab Workbench in Zotero and
an ordinary ChatGPT chat. It gives the user one way to ask ChatGPT with the
same bounded paper and Draft context that is visible in Zotero, while the QLab
app supplies live, read-only repository context.

It is not an embedded ChatGPT client. There is no cookie or credential reuse,
no DOM automation, no response-stream scraping, no ChatGPT UI impersonation,
and no product-limit bypass. Zotero opens the normal ChatGPT surface and the
user remains in control of every paste and import.

## Product availability

OpenAI's current documentation says that Pro users can connect MCP servers
with `read`/`fetch` permissions in Developer Mode. Full MCP availability and
write actions have different plan requirements. It also says ChatGPT cannot
connect directly to a local MCP server, and that custom apps must be selected
in the chat that uses them. Availability, UI, plan requirements, and
permissions may change, so verify the current account and workspace controls
before setup. See [Developer mode and MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta).

This workflow applies only when Developer Mode and custom read-only apps are
available to the user's account. It does not convert an unavailable product
surface into an available one. In particular, use an ordinary supported
ChatGPT chat rather than assuming that every ChatGPT mode can invoke a custom
app.

## User workflow

1. In the QLab Workbench, compose a question and confirm the visible context
   chips. Paper metadata, the current page and selection, secondary papers,
   screenshot provenance, and an eligible Draft excerpt are bounded inputs.
2. Click **Ask in ChatGPT ↗**. Zotero synchronously freezes the visible
   context into a private capsule, saves it in the Zotero profile, copies a
   provenance-labelled prompt, and opens ChatGPT.
3. In the destination ChatGPT chat, enable the **QLab app**, then paste the
   copied prompt and send it. The QLab app can search and fetch the read-only
   repository context described below.
4. Continue the conversation in ChatGPT. ChatGPT cannot retrieve the private
   Zotero capsule; the pasted prompt is the handoff.
5. Optional: copy one ChatGPT answer, return to the matching pending handoff in
   Zotero, and use the **explicit clipboard import** action. Clipboard reading
   happens only on that click.

An imported answer is a labelled, current-session overlay for that paper,
Draft, or question-only subject. It is never added to Codex history, never sent
to Codex, and never treated as a ChatGPT conversation archive. Companion also
works while Codex is signed out, disconnected, unavailable, or has no active
thread: opening a handoff makes no Codex request or turn and consumes no Codex
chat turn.

## Two context clocks

The two sides deliberately have different freshness rules:

- The **frozen Zotero capsule** is an auditable snapshot of the exact chips and
  source state at the click. If an active Draft cannot be revalidated at the
  same path and revision, its body is omitted with a warning. Screenshot
  entries carry provenance only; no screenshot image is copied.
- **Live Knowledge retrieval** happens later through the QLab MCP app.
  `search` returns opaque candidates and `fetch` resolves the selected result
  again. A reviewed Knowledge fetch returns the repository revision and
  per-file hashes for the complete ordered bundle.

Consequently, a ChatGPT answer can say both which Zotero snapshot it received
and which current repository revision it fetched. The private capsule ID is a
provenance binding, not a repository locator.

## Trust domains

The service enforces this distinction in retrieval, not only in a prompt:

```text
reviewed knowledge ≠ literature ≠ problem ≠ draft
```

| Domain | Authority in ChatGPT Companion | MCP exposure |
|---|---|---|
| `knowledge/` | Human-reviewed repository knowledge | Searchable; a fetch returns the complete matched bundle and live hashes |
| `literature/` | External evidence, not an approved conclusion | Searchable as bounded bibliographic metadata |
| `problems/` | Open research questions, not conclusions | Searchable only when visible under repository policy |
| `drafts/` | Unreviewed work | Never MCP searchable or fetchable |

A bounded Draft excerpt may be present only inside the user-pasted frozen
Zotero capsule. Draft is never available to MCP search, and ChatGPT must not
silently substitute Literature, a Problem, or Draft text for reviewed
Knowledge.

## Configure the read-only MCP service

The repository supplies a loopback MCP process. It does not deploy a public
endpoint, provision a tunnel, configure ChatGPT, or make a local service
internet-accessible. The operator owns the HTTPS connection and must review
the current OpenAI setup instructions.

### 1. Prepare a read-only repository root

Production must point at a read-only mirror or an OS-level read-only mount, not
the writable working checkout. The Linux launcher verifies the mount through
`findmnt` and refuses a writable repository root. The development override
named `QLAB_COMPANION_UNSAFE_ALLOW_WRITABLE_ROOT_FOR_DEVELOPMENT` is for local
tests only and must not be used for a connected production app.

The mirror should contain only the repository content intended for this
service. Do not include `.git` credentials, environment files, secrets,
private autoresearch data, build caches, `node_modules`, or unpublished
artifacts.

### 2. Set launch variables

Use distinct HTTPS origins for the MCP endpoint and credential-free
public-content base. The access token must be at least 32 bytes of entropy and
must not contain control characters. From the repository root, for example, in
a private Linux shell:

```sh
export QLAB_COMPANION_REPO_ROOT=/srv/quarto-lab-readonly
export QLAB_COMPANION_ENDPOINT_BASE_URL=https://mcp.example.org/
export QLAB_COMPANION_PUBLIC_BASE_URL=https://research.example.org/
export QLAB_COMPANION_ACCESS_TOKEN="$(openssl rand -hex 32)"
export QLAB_COMPANION_TRUSTED_TUNNEL=1
npm run companion:mcp
```

`QLAB_COMPANION_ENDPOINT_BASE_URL` is the externally visible MCP origin.
`QLAB_COMPANION_PUBLIC_BASE_URL` is the separate, credential-free origin used
for citations. The server listens on loopback `127.0.0.1:7676` by default and
derives a secret capability path from the token. The full app endpoint has the
form `https://<host>/<capability-path>`; it is a token-bearing bearer
capability even though the raw token is not placed in the URL.

The service deliberately omits that secret path from its logs. In a second
private shell with the same variables, print it once for direct entry in the
ChatGPT app form:

```sh
node --import tsx --input-type=module -e \
  'import { deriveCompanionCapabilityPath } from "./src/lib/companion/server.ts"; const token = process.env.QLAB_COMPANION_ACCESS_TOKEN; const base = process.env.QLAB_COMPANION_ENDPOINT_BASE_URL; if (!token || !base) throw new Error("missing Companion endpoint environment"); process.stdout.write(new URL(deriveCompanionCapabilityPath(token), base).href + "\n")'
```

Do not pipe, save, or paste this output anywhere except the app configuration;
clear the terminal scrollback afterward according to local security policy.

Treat both the raw token and derived capability endpoint as secrets. Token
material must never enter citations, copied prompts, or logs. In particular,
disable or redact request-target logging at every proxy and tunnel layer; a
standard access log that records the request path leaks the capability.

### 3. Connect loopback to ChatGPT

ChatGPT cannot connect directly to localhost. When available for the target
account and product, prefer OpenAI Secure MCP Tunnel. Otherwise use an
authenticated HTTPS reverse tunnel that you operate and trust. Either path
must leave the QLab process bound to loopback; trusted-tunnel mode does not
authorize a public `0.0.0.0` bind.

For a user-managed reverse proxy or tunnel:

- terminate with valid HTTPS and authenticate access at the outer boundary;
- forward only the exact secret capability path to `127.0.0.1:7676`;
- preserve the MCP HTTP methods, content type, and session headers;
- reject every other path and do not rewrite the capability path;
- redact the full request target, query, headers, and upstream URL from access
  and error logs;
- keep the upstream origin loopback-only and block direct network access; and
- rotate `QLAB_COMPANION_ACCESS_TOKEN` and recreate the ChatGPT app after any
  suspected exposure or operator handoff.

Do not put the raw token in a query string, URL user-info, endpoint-base
variable, public-content-base variable, proxy configuration committed to Git,
or a shell-history command. Rotation changes the derived capability path and
invalidates the old endpoint.

### 4. Create and enable the QLab app

When the account exposes the required Developer Mode/custom app controls:

1. Enable Developer Mode using the current ChatGPT settings for the account or
   workspace.
2. Create a custom app named **QLab** using the complete secret
   `https://<host>/<capability-path>` endpoint exposed by the selected tunnel.
3. Scan and inspect the tools. This server must expose only `search` and
   `fetch`, both annotated read-only and non-destructive.
4. Open the destination chat and enable the QLab app there before pasting the
   Zotero prompt. App creation alone does not select it for a chat.

Never add a write, shell, build, Git, Draft, Zotero-mutation, or Codex tool to
this server. Connecting an app is a separate ChatGPT account action and does
not share or transfer Codex usage.

## Security checklist

- [ ] Repository root is an OS-level read-only mirror/mount; writable-root
      refusal has been observed.
- [ ] Endpoint and public-content origins are distinct HTTPS origins.
- [ ] Token contains at least 32 bytes of entropy and has a rotation plan.
- [ ] MCP remains on loopback and explicit trusted-tunnel mode is enabled.
- [ ] Reverse proxy forwards only the capability path and preserves MCP
      transport behavior.
- [ ] Request-target logging is disabled or redacted end to end.
- [ ] Token/capability values are absent from citations, copied prompts, logs,
      screenshots, issue reports, and committed configuration.
- [ ] QLab app tool scan shows only read-only `search` and `fetch`.
- [ ] Draft content cannot be found through MCP search or fetch.

## Troubleshooting

| Symptom | Check |
|---|---|
| QLab app is unavailable | Confirm the current plan/workspace supports Developer Mode and custom read-only apps, and that the required administrator setting is enabled. |
| ChatGPT cannot connect to localhost | This is expected. Use Secure MCP Tunnel when available or a trusted authenticated HTTPS reverse tunnel. |
| App exists but ChatGPT does not use it | Enable the QLab app in the destination chat, then paste the frozen prompt. |
| MCP exits immediately | Check all four required variables, HTTPS/distinct origins, token length, and the OS-level read-only mount. |
| Tunnel returns `404` | Confirm it forwards the exact derived capability path without rewriting it. Wrong, missing, and unknown paths intentionally look alike. |
| Search has no reviewed answer | Report a Knowledge gap. Do not relabel Literature, Problems, or Draft as reviewed Knowledge. |
| Draft was omitted | The Draft changed, moved, failed revalidation, or exceeded a safety bound after the click; create a new handoff from the current Draft. |
| Imported answer is gone after restart | Expected: imports are current-session overlays, not persistent Codex or ChatGPT history. |

## Platform verification status

The Linux implementation and automated verification are complete. Native
Zotero and keychain/filesystem behavior on macOS remains deferred for explicit
macOS verification; this document does not claim that validation has happened.
