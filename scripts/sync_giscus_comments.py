#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "workspace"
COMMENTS_ROOT = WORKSPACE / "comments"

GQL_URL = "https://api.github.com/graphql"


def load_giscus_config():
    config_path = ROOT / "_quarto.yml"
    if not config_path.exists():
        return {}

    text = config_path.read_text(encoding="utf-8")

    # Try PyYAML if available
    try:
        import yaml  # type: ignore

        cfg = yaml.safe_load(text)
        giscus = (cfg or {}).get("comments", {}).get("giscus", {})
        return {
            "repo": giscus.get("repo"),
            "category_id": giscus.get("category-id"),
            "mapping": giscus.get("mapping"),
        }
    except Exception:
        pass

    # Fallback regex parsing
    repo = None
    category_id = None
    mapping = None

    # Extract giscus block
    in_comments = False
    in_giscus = False
    for line in text.splitlines():
        if re.match(r"^comments:\s*$", line):
            in_comments = True
            continue
        if in_comments and re.match(r"^\s+giscus:\s*$", line):
            in_giscus = True
            continue
        if in_comments and not line.startswith(" "):
            in_comments = False
            in_giscus = False

        if in_giscus:
            m = re.match(r"^\s+repo:\s*['\"]?([^'\"]+)['\"]?\s*$", line)
            if m:
                repo = m.group(1).strip()
            m = re.match(r"^\s+category-id:\s*['\"]?([^'\"]+)['\"]?\s*$", line)
            if m:
                category_id = m.group(1).strip()
            m = re.match(r"^\s+mapping:\s*['\"]?([^'\"]+)['\"]?\s*$", line)
            if m:
                mapping = m.group(1).strip()

    return {"repo": repo, "category_id": category_id, "mapping": mapping}


def graphql_request(token: str, query: str, variables: dict):
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = Request(GQL_URL, data=payload)
    req.add_header("Authorization", f"bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")

    with urlopen(req) as resp:
        data = json.load(resp)

    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")

    return data.get("data", {})


def fetch_repo_id(token: str, owner: str, name: str) -> str:
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) { id }
    }
    """
    data = graphql_request(token, query, {"owner": owner, "name": name})
    return data["repository"]["id"]


def fetch_all_discussions(token: str, owner: str, name: str, category_id: str | None):
    query = """
    query($owner: String!, $name: String!, $first: Int!, $after: String, $categoryId: ID) {
      repository(owner: $owner, name: $name) {
        discussions(first: $first, after: $after, categoryId: $categoryId) {
          nodes { id title url category { id name } }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """

    discussions = []
    after = None
    while True:
        variables = {"owner": owner, "name": name, "first": 50, "after": after, "categoryId": category_id}
        data = graphql_request(token, query, variables)
        conn = data["repository"]["discussions"]
        discussions.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return discussions


def fetch_discussion_comments(token: str, discussion_id: str):
    query = """
    query($id: ID!, $first: Int!, $after: String) {
      node(id: $id) {
        ... on Discussion {
          comments(first: $first, after: $after, orderBy: {field: CREATED_AT, direction: ASC}) {
            nodes {
              id
              body
              createdAt
              author { login }
              replies(first: 50) {
                nodes { id body createdAt author { login } }
                pageInfo { hasNextPage endCursor }
              }
            }
            pageInfo { hasNextPage endCursor }
          }
        }
      }
    }
    """

    comments = []
    after = None
    while True:
        data = graphql_request(token, query, {"id": discussion_id, "first": 50, "after": after})
        conn = data["node"]["comments"]
        comments.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return comments


def fetch_discussion_meta(token: str, discussion_id: str) -> tuple[str, str]:
    query = """
    query($id: ID!) {
      node(id: $id) {
        ... on Discussion { title url }
      }
    }
    """
    data = graphql_request(token, query, {"id": discussion_id})
    node = data.get("node") or {}
    return node.get("title", ""), node.get("url", "")


def create_discussion(token: str, repo_id: str, category_id: str, title: str, body: str):
    query = """
    mutation($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
      createDiscussion(input: {repositoryId: $repoId, categoryId: $categoryId, title: $title, body: $body}) {
        discussion { id title url category { id name } }
      }
    }
    """
    data = graphql_request(
        token,
        query,
        {"repoId": repo_id, "categoryId": category_id, "title": title, "body": body},
    )
    return data["createDiscussion"]["discussion"]


def format_date(dt_str: str) -> str:
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    # Format like "Feb 3, 2026" without leading zero
    return dt.strftime("%b %d, %Y").replace(" 0", " ")


def render_post(author: str, created_at: str, body: str, verb: str = "commented") -> str:
    author = author or "unknown"
    date_str = format_date(created_at)
    body = body.strip() or "*No content.*"

    return (
        "::: {.issue-post}\n"
        "::: {.post-header}\n"
        "::: {.post-author}\n"
        f"**{author}** {verb} on {date_str}\n"
        ":::\n"
        ":::\n\n"
        "::: {.post-body}\n"
        f"{body}\n"
        ":::\n"
        ":::\n"
    )


def comments_to_markdown(comments):
    parts = []
    reply_truncations = 0
    for comment in comments:
        parts.append(render_post(comment.get("author", {}).get("login"), comment["createdAt"], comment.get("body", ""), verb="commented"))
        # Replies (if any)
        replies = comment.get("replies", {}).get("nodes", []) or []
        for reply in replies:
            parts.append(render_post(reply.get("author", {}).get("login"), reply["createdAt"], reply.get("body", ""), verb="replied"))
        if comment.get("replies", {}).get("pageInfo", {}).get("hasNextPage"):
            reply_truncations += 1
    if reply_truncations:
        parts.append(f"*Note: {reply_truncations} comment(s) have more than 50 replies; additional replies were not fetched.*\n")
    return "\n".join(parts).strip() + "\n" if parts else ""


def write_if_changed(path: Path, content: str) -> bool:
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if old == content:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def qmd_from_title(title: str) -> Path | None:
    if not title:
        return None
    path = None
    if title.startswith("/"):
        path = title
    else:
        m = re.search(r"(/workspace/\\S+)", title)
        if m:
            path = m.group(1)
        elif "workspace/" in title:
            idx = title.find("workspace/")
            path = "/" + title[idx:]

    if not path:
        return None

    if path.endswith(".html"):
        path = path[:-5] + ".qmd"
    elif not path.endswith(".qmd"):
        path = path + ".qmd"

    qmd = ROOT / path.lstrip("/")
    if not qmd.exists():
        return None
    return qmd


def main():
    parser = argparse.ArgumentParser(description="Sync giscus discussions into workspace/comments/*.md")
    parser.add_argument("--render", action="store_true", help="Run quarto render if comment files changed")
    parser.add_argument(
        "--render-scope",
        choices=["changed", "project"],
        default="changed",
        help="Render only changed issue pages (default) or the full project",
    )
    parser.add_argument("--discussion-id", help="GraphQL discussion node ID (single discussion mode)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of pages (for testing)")
    parser.add_argument("--create-missing", action="store_true", help="Create missing discussions (requires category-id and token with write access)")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN not set.", file=sys.stderr)
        sys.exit(1)

    cfg = load_giscus_config()
    repo = os.environ.get("GITHUB_REPO") or cfg.get("repo")
    if not repo or "/" not in repo:
        print("ERROR: Cannot determine repo. Set GITHUB_REPO=owner/name or configure _quarto.yml giscus.repo.", file=sys.stderr)
        sys.exit(1)

    owner, name = repo.split("/", 1)
    category_id = os.environ.get("GISCUS_CATEGORY_ID") or cfg.get("category_id")
    mapping = cfg.get("mapping")
    if mapping and mapping != "pathname":
        print(f"WARNING: giscus mapping is '{mapping}', but this script assumes 'pathname'.", file=sys.stderr)

    if args.discussion_id:
        title, discussion_url = fetch_discussion_meta(token, args.discussion_id)
        qmd = qmd_from_title(title)
        if not qmd:
            print("ERROR: Could not map discussion title to a local qmd file.", file=sys.stderr)
            sys.exit(1)

        try:
            rel_from_workspace = qmd.relative_to(WORKSPACE)
        except ValueError:
            print("ERROR: QMD is not under workspace/; skipping.", file=sys.stderr)
            sys.exit(1)

        comment_path = COMMENTS_ROOT / rel_from_workspace.with_suffix(".md")
        comments = fetch_discussion_comments(token, args.discussion_id)
        md = comments_to_markdown(comments) or "*No comments yet.*\n"
        header = f"<!-- AUTO-GENERATED from {discussion_url or args.discussion_id} -->\n"
        link = f"[Comment on GitHub]({discussion_url})\n" if discussion_url else ""
        content = header + "\n" + link + "\n" + md
        changed = write_if_changed(comment_path, content)

        if args.render and changed:
            if args.render_scope == "project":
                subprocess.run(["quarto", "render"], cwd=str(ROOT), check=True)
            else:
                subprocess.run(["quarto", "render", str(qmd)], cwd=str(ROOT), check=True)
        sys.exit(0)

    discussions = fetch_all_discussions(token, owner, name, category_id)
    repo_id = None
    if args.create_missing:
        if not category_id:
            print("ERROR: --create-missing requires giscus category-id.", file=sys.stderr)
            sys.exit(1)
        repo_id = fetch_repo_id(token, owner, name)

    issue_files = sorted(WORKSPACE.glob("**/issues/issue*.qmd"))
    if args.limit:
        issue_files = issue_files[: args.limit]

    changed = False
    synced = 0
    skipped = 0
    changed_qmds = set()

    for qmd in issue_files:
        rel_from_root = qmd.relative_to(ROOT)
        # pathname as used by giscus mapping=pathname
        html_path = "/" + rel_from_root.with_suffix(".html").as_posix()
        html_path_no_ext = "/" + rel_from_root.with_suffix("").as_posix()
        candidates = {
            html_path,
            html_path.lstrip("/"),
            html_path_no_ext,
            html_path_no_ext.lstrip("/"),
        }

        discussion = None
        for d in discussions:
            title = d.get("title", "")
            if any(c and c in title for c in candidates):
                discussion = d
                break

        rel_from_workspace = qmd.relative_to(WORKSPACE)
        comment_path = COMMENTS_ROOT / rel_from_workspace.with_suffix('.md')

        if not discussion:
            if args.create_missing and repo_id:
                title = html_path
                body = f"Auto-created discussion for {html_path}."
                discussion = create_discussion(token, repo_id, category_id, title, body)
                discussions.append(discussion)
            else:
                content = "<!-- AUTO-GENERATED: no discussion found -->\n\n*No comments yet.*\n"
            if write_if_changed(comment_path, content):
                changed = True
                changed_qmds.add(str(qmd))
            skipped += 1
            continue

        comments = fetch_discussion_comments(token, discussion["id"])
        md = comments_to_markdown(comments)
        if not md.strip():
            md = "*No comments yet.*\n"

        header = f"<!-- AUTO-GENERATED from {discussion['url']} -->\n"
        link = f"[Comment on GitHub]({discussion['url']})\n"
        content = header + "\n" + link + "\n" + md

        if write_if_changed(comment_path, content):
            changed = True
            changed_qmds.add(str(qmd))
        synced += 1

    print(f"Synced {synced} discussions, skipped {skipped} pages (no discussion).")

    if args.render and changed:
        if args.render_scope == "project":
            print("Changes detected; running full quarto render...")
            subprocess.run(["quarto", "render"], cwd=str(ROOT), check=True)
        else:
            targets = sorted(changed_qmds)
            print(f"Changes detected; rendering {len(targets)} page(s)...")
            subprocess.run(["quarto", "render", *targets], cwd=str(ROOT), check=True)
    elif args.render:
        print("No comment changes; skipping quarto render.")


if __name__ == "__main__":
    main()
