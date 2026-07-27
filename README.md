# Research Loop

A shared human-and-agent knowledge system. The existing dashboard stays at `/`,
a Quarto site of reviewed research knowledge is published at `/knowledge/`, and
both are packaged into one deployable artifact by the existing vinext build.

- `/` — the preserved Research Loop dashboard. Its source and appearance are
  authoritative: `app/page.tsx`, `app/globals.css`, and `app/layout.tsx` are not
  rewritten to accommodate the knowledge system.
- `/knowledge/` — a static Quarto website rendered from `knowledge/**/*.qmd`
  into the gitignored `public/knowledge/`, with code execution disabled.

## The trust boundary

Three trees, three different levels of trust. The separation is physical, so
nothing can quietly promote itself.

| Tree | Status | What it means |
|---|---|---|
| `knowledge/` | trusted | The only content authority. A page is here because a human reviewed it and merged it. It is the only thing published at `/knowledge/`. |
| `drafts/` | untrusted | Imported cards, pasted notes, agent output. No required categories, hierarchy, catalog, or frontmatter. Never published; never an answer source. |
| `literature/` | external | Papers and their pinned arXiv sources — evidence to check a claim against, not a conclusion this project has drawn. Never published. |

Agents answer research questions by resolving against `knowledge/` and reading
the whole returned bundle; a question the trusted tree does not cover gets an
explicit "no match" rather than a quiet fallback to the other two trees. See
`AGENTS.md` for the rules and `docs/skills.md` for the skills that implement
them.

## Knowledge pages

Every page is a `.qmd` file with a small, strictly allowlisted frontmatter:
`title`, `description`, `categories`, and `aliases`. Nothing else is accepted —
the allowlist is what keeps a page from turning a render into code execution.

- **Three categories.** A content page declares exactly one of `theory`,
  `experiment`, or `codes`. A topic's `index.qmd` declares none.
- **The reading map is curated, not derived.** Each `index.qmd` carries a
  `## Reading map` section listing the pages that belong to that topic, in the
  order a reader should meet them. That list defines ownership, the site's
  sidebar order, and the resolver's ordering. A page no reading map lists is an
  orphan, and validation fails.
- **`## Related topics` is a cross-reference.** It may point anywhere in the
  tree and changes no ownership.

`make knowledge-check` enforces all of it: allowlists, categories, orphans,
duplicate parents, broken links, cycles, path escapes, and citation keys that
are not in `literature/ref.bib`.

## Prerequisites

- Node.js `22.23.1` (pinned in `.node-version`)
- Quarto `1.9.38` on `PATH`, for rendering and previewing

## Commands

```bash
make help
```

| Command | What it does |
|---|---|
| `make dev` | Install locked dependencies when needed, then serve the dashboard locally |
| `make build` | Validate and render `knowledge/` into `public/knowledge/`, then build the deployable app |
| `make test` | Lint, unit tests, rendered-output tests, and browser tests |
| `make knowledge-check` | Validate the trusted knowledge tree |
| `make knowledge-resolve QUERY="triangular TFIM"` | Print the reading bundle for one research question, as JSON |
| `make knowledge-preview` | Serve the trusted knowledge site locally |
| `make draft-preview FILE=drafts/note.md` | Render exactly one untrusted draft note locally |
| `make literature-index` | Regenerate every `literature/<method>/INDEX.md` from `ref.bib` |
| `make literature-fetch KEY=citekey` | Fetch one reference's version-pinned arXiv source |
| `make literature-sync` | Fetch the pinned source of every arXiv reference |
| `make migration-verify` | Re-check the imported harness cards against their manifest |

Equivalent package scripts exist underneath (`npm run knowledge:check`, and so
on), but documentation and skills use the Make targets, so there is one stable
name for each workflow.

`make knowledge-resolve` prints one JSON document and exits 0 for `match`,
`ambiguous`, and `no-match` alike — a status is an answer, not a failure. The
argument-taking targets refuse an empty variable with a one-line usage message
and exit 2.

## Deployment

`.openai/hosting.json` pins the existing Sites project
`appgprj_6a66e89526a88191a9e969c6f441086c`. That exact project is reused: it is
never reformatted, replaced, or re-created. Deployment may remain blocked while
that project is not visible to the current account; local completion — build,
tests, and rendered output — is valid on its own, and the artifact is ready for
whenever access returns.

## Not in this phase

- No autonomous solver backend, queue, or agent that runs unattended.
- No D1 or R2 data model. The bindings in `.openai/hosting.json` stay `null`,
  `db/schema.ts` is intentionally empty, and `examples/d1/` plus
  `drizzle.config.ts` remain an unused optional surface.
- No published draft or literature source: `drafts/`, `literature/`, and the
  local `.raw/` and `.figures/` trees never reach the deployed artifact.
- No embeddings, no `.knowledge` compatibility tree, and no generated Markdown
  mirror of the knowledge pages.

## Hosting platform notes

OpenAI workspace sites can read the current user's email from
`oai-authenticated-user-email`.

SIWC-authenticated workspace sites may also receive
`oai-authenticated-user-full-name` when the user's SIWC profile has a non-empty
`name` claim. The full-name value is percent-encoded UTF-8 and is accompanied by
`oai-authenticated-user-full-name-encoding: percent-encoded-utf-8`.

Treat the full name as optional and fall back to email when it is absent:

```tsx
import { headers } from "next/headers";

export default async function Home() {
  const requestHeaders = await headers();
  const email = requestHeaders.get("oai-authenticated-user-email");
  const encodedFullName = requestHeaders.get("oai-authenticated-user-full-name");
  const fullName =
    encodedFullName &&
    requestHeaders.get("oai-authenticated-user-full-name-encoding") ===
      "percent-encoded-utf-8"
      ? decodeURIComponent(encodedFullName)
      : null;

  const displayName = fullName ?? email;
  // ...
}
```

Import the ready-to-use helpers from `app/chatgpt-auth.ts` when the site needs
optional or required ChatGPT sign-in:

- Use `getChatGPTUser()` for optional signed-in UI.
- Use `requireChatGPTUser(returnTo)` for server-rendered pages that should send
  anonymous visitors through Sign in with ChatGPT.
- Use `chatGPTSignInPath(returnTo)` and `chatGPTSignOutPath(returnTo)` for
  browser links or actions.
- Pass a same-origin relative `returnTo` path for the destination after sign-in
  or sign-out. The helper validates and safely encodes it.
- Mark protected pages with `export const dynamic = "force-dynamic"` because
  they depend on per-request identity headers.

Dispatch owns `/signin-with-chatgpt`, `/signout-with-chatgpt`, `/callback`, the
OAuth cookies, and identity header injection. Do not implement app routes for
those reserved paths. Routes that do not import and call the helper remain
anonymous-compatible.

SIWC establishes identity only; it does not prove workspace membership. Use the
Sites hosting platform's access policy controls for workspace-wide restrictions,
or enforce explicit server-side membership or allowlist checks.

This starter does not use `wrangler.jsonc`.

## Learn More

- [Quarto Documentation](https://quarto.org/docs/guide/)
- [vinext Documentation](https://github.com/cloudflare/vinext)
- [Drizzle D1 Guide](https://orm.drizzle.team/docs/get-started/d1-new)
