"""Project one validated KnowledgeGraph into an execution-disabled Quarto tree."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
from typing import Any, Iterable
from xml.etree import ElementTree

import yaml
from yaml.nodes import MappingNode, ScalarNode

from .assets import audit_trusted_asset
from .graph import KnowledgeGraph
from .parser import (
    css_loads_resource,
    contains_html_markup,
    markdown_links,
    raw_html_images,
    raw_html_resources,
    unsafe_html,
)
from .targets import TargetKind, classify_target, lexical_local_path
from .validate import KnowledgeValidationError, validate_knowledge


@dataclass(frozen=True)
class QuartoProject:
    project_dir: Path
    output_dir: Path


HOMEPAGE_FRONTMATTER_KEYS = frozenset(
    {"about", "comments", "lang", "title"}
)
HOMEPAGE_ABOUT_TEMPLATES = frozenset(
    {"broadside", "jolla", "marquee", "solana", "trestles"}
)


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _local_target(target: str) -> str | None:
    classified = classify_target(target)
    if classified.kind is not TargetKind.LOCAL:
        return None
    return classified.path


def _require_contained_file(root: Path, source: Path) -> Path:
    lexical = Path(os.path.abspath(source))
    if not lexical.is_relative_to(root):
        raise ValueError(f"Projected dependency escapes its allowed root: {source}")
    if any(
        component.is_symlink()
        for component in [root, *lexical.parents]
        if component == root or component.is_relative_to(root)
    ) or lexical.is_symlink():
        raise ValueError(f"Projected dependency traverses a symlink: {source}")
    if not lexical.is_file():
        raise ValueError(f"Projected dependency is not a file: {source}")
    resolved = lexical.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Projected dependency escapes its allowed root: {source}")
    return lexical


def _reading_targets(graph: KnowledgeGraph, index: Path) -> tuple[Path, ...]:
    pages = set(graph.pages)
    targets: list[Path] = []
    for link in dict(graph.reading_maps)[index]:
        target_text = _local_target(link.target)
        if target_text is None:
            continue
        target = lexical_local_path(index.parent, classify_target(link.target))
        if target in pages:
            targets.append(target)
    return tuple(targets)


def _audit_fixed_dependency(relative: str, path: Path) -> None:
    if relative == "_includes/comment-github-link.html":
        source = path.read_text(encoding="utf-8")
        if (
            re.search(r"\{\{[<%]", source)
            or unsafe_html(path)
            or raw_html_images(path)
            or raw_html_resources(path)
        ):
            raise ValueError(f"unsafe fixed Quarto HTML include: {path}")
        return
    if relative == "styles.css":
        source = path.read_text(encoding="utf-8")
        if css_loads_resource(source):
            raise ValueError(f"unsafe fixed Quarto stylesheet: {path}")
        return
    if relative == "aps.csl":
        source = path.read_bytes()
        lowered = source.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ValueError(f"unsafe fixed Quarto CSL file: {path}")
        try:
            root = ElementTree.fromstring(source)
        except ElementTree.ParseError as error:
            raise ValueError(f"unsafe fixed Quarto CSL file: {path}") from error
        if str(root.tag).rsplit("}", maxsplit=1)[-1].casefold() != "style":
            raise ValueError(f"unsafe fixed Quarto CSL file: {path}")
        return
    if relative == "references.bib":
        if path.suffix.casefold() != ".bib":
            raise ValueError(f"unsafe fixed Quarto bibliography: {path}")
        return
    raise ValueError(f"unsupported fixed Quarto dependency: {relative}")


def _trusted_asset(graph: KnowledgeGraph, source: Path) -> Path:
    asset = _require_contained_file(graph.knowledge_root, source)
    audit_trusted_asset(asset)
    return asset


def _homepage_frontmatter(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("Root homepage requires opening YAML frontmatter.")
    closing = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line == "---"
        ),
        None,
    )
    if closing is None:
        raise ValueError("Root homepage frontmatter has no closing delimiter.")
    source = "\n".join(lines[1:closing])
    try:
        document = yaml.compose(source, Loader=yaml.SafeLoader)
        parsed = yaml.safe_load(source)
    except yaml.YAMLError as error:
        raise ValueError("Root homepage frontmatter is invalid YAML.") from error
    if not isinstance(document, MappingNode) or not isinstance(parsed, dict):
        raise ValueError("Root homepage frontmatter must be a mapping.")
    if _contains_quarto_shortcode(parsed):
        raise ValueError("Root homepage Quarto shortcodes are forbidden.")
    if _contains_html_in_metadata(parsed):
        raise ValueError("Root homepage metadata may not contain HTML.")

    keys: set[str] = set()
    for key_node, _ in document.value:
        if not isinstance(key_node, ScalarNode):
            raise ValueError("Root homepage frontmatter keys must be strings.")
        key = key_node.value
        if key in keys:
            raise ValueError(
                f"Root homepage has duplicate frontmatter key: {key}"
            )
        keys.add(key)
    unexpected = sorted(keys - HOMEPAGE_FRONTMATTER_KEYS)
    if unexpected:
        raise ValueError(
            "Root homepage has unsupported frontmatter key: "
            f"{unexpected[0]}"
        )

    title = parsed.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Root homepage requires a nonempty title.")
    lang = parsed.get("lang")
    if lang is not None and (
        not isinstance(lang, str)
        or re.fullmatch(
            r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*",
            lang,
        )
        is None
    ):
        raise ValueError("Root homepage lang must be a locale identifier.")
    if parsed.get("comments", False) is not False:
        raise ValueError("Root homepage comments must remain disabled.")

    about = parsed.get("about")
    if about is not None:
        if not isinstance(about, dict):
            raise ValueError("Root homepage about must be a mapping.")
        unexpected_about = sorted(
            str(key)
            for key in set(about) - {"image", "links", "template"}
        )
        if unexpected_about:
            raise ValueError(
                "Root homepage about has unsupported key: "
                f"{unexpected_about[0]}"
            )
        image = about.get("image")
        if image is not None and (
            not isinstance(image, str)
            or not image.startswith("https://")
        ):
            raise ValueError(
                "Root homepage about image must use an HTTPS URL."
            )
        template = about.get("template")
        if template is not None and template not in HOMEPAGE_ABOUT_TEMPLATES:
            raise ValueError("Root homepage about template is unsupported.")
        links = about.get("links", [])
        if not isinstance(links, list):
            raise ValueError("Root homepage about links must be a list.")
        for link in links:
            if not isinstance(link, dict) or set(link) - {
                "href",
                "icon",
                "text",
            }:
                raise ValueError(
                    "Root homepage about links use an unsupported shape."
                )
            href = link.get("href")
            if not isinstance(href, str) or not href.startswith(
                ("https://", "mailto:")
            ):
                raise ValueError(
                    "Root homepage about links must use HTTPS or mailto."
                )
            for key in ("icon", "text"):
                value = link.get(key)
                if value is not None and (
                    not isinstance(value, str) or not value.strip()
                ):
                    raise ValueError(
                        f"Root homepage about link {key} must be text."
                    )
    return parsed


def _validated_homepage(graph: KnowledgeGraph) -> Path:
    homepage = _require_contained_file(
        graph.repo_root,
        graph.repo_root / "index.qmd",
    )
    _homepage_frontmatter(homepage)
    if re.search(r"\{\{[<%]", homepage.read_text(encoding="utf-8")):
        raise ValueError("Root homepage Quarto shortcodes are forbidden.")
    if unsafe_html(homepage):
        raise ValueError("Root homepage contains active HTML.")
    trusted_pages = set(graph.pages)
    for link in (
        *markdown_links(homepage),
        *raw_html_images(homepage),
        *raw_html_resources(homepage),
    ):
        classified = classify_target(link.target)
        if classified.kind is TargetKind.EMPTY:
            continue
        if (
            classified.kind is TargetKind.EXTERNAL
            and classified.scheme in {"https", "mailto"}
        ):
            continue
        if classified.kind is not TargetKind.LOCAL:
            raise ValueError(
                f"Root homepage target is unsafe: {link.target}"
            )
        target = lexical_local_path(homepage.parent, classified)
        if link.kind == "image" or target not in trusted_pages:
            raise ValueError(
                "Root homepage local target is not trusted: "
                f"{link.target}"
            )
    return homepage


def _sidebar_entry(graph: KnowledgeGraph, page: Path) -> dict[str, object]:
    metadata = dict(graph.metadata)[page]
    href = page.relative_to(graph.repo_root).as_posix()
    if page.name != "index.qmd":
        return {"text": metadata.title, "href": href}
    children = [
        _sidebar_entry(graph, child)
        for child in _reading_targets(graph, page)
    ]
    return {
        "section": metadata.title,
        "href": href,
        "contents": children,
    }


def _config_mapping(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"Quarto base configuration {path} must be a mapping.")
    return value


def _reject_config_keys(
    value: dict[str, object],
    allowed: set[str],
    path: str,
) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(
            "unsupported Quarto base configuration key: "
            f"{path}.{unexpected[0]}"
        )


def _nonempty_config_text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Quarto base configuration {path} must be nonempty text."
        )
    return value


def _contains_quarto_shortcode(
    value: object,
    seen: set[int] | None = None,
) -> bool:
    if isinstance(value, str):
        return re.search(r"\{\{[<%]", value) is not None
    visited = seen if seen is not None else set()
    identity = id(value)
    if identity in visited:
        return False
    visited.add(identity)
    if isinstance(value, dict):
        return any(
            _contains_quarto_shortcode(key, visited)
            or _contains_quarto_shortcode(nested, visited)
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return any(
            _contains_quarto_shortcode(nested, visited)
            for nested in value
        )
    return False


def _contains_html_in_metadata(
    value: object,
    seen: set[int] | None = None,
) -> bool:
    if isinstance(value, str):
        return contains_html_markup(value)
    visited = seen if seen is not None else set()
    identity = id(value)
    if identity in visited:
        return False
    visited.add(identity)
    if isinstance(value, dict):
        return any(
            _contains_html_in_metadata(key, visited)
            or _contains_html_in_metadata(nested, visited)
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return any(
            _contains_html_in_metadata(nested, visited)
            for nested in value
        )
    return False


def _reject_config_shortcodes(value: object) -> None:
    if _contains_quarto_shortcode(value):
        raise ValueError(
            "Quarto shortcodes are forbidden in base configuration."
        )


def _reject_config_html(value: object) -> None:
    if _contains_html_in_metadata(value):
        raise ValueError("HTML is forbidden in base configuration.")


def _generated_navbar(
    graph: KnowledgeGraph,
    value: object,
) -> dict[str, object]:
    navbar = _config_mapping(value, "website.navbar")
    _reject_config_keys(navbar, {"left", "right"}, "website.navbar")
    trusted_hrefs = {
        "index.qmd",
        *(
            page.relative_to(graph.repo_root).as_posix()
            for page in graph.pages
        ),
    }
    generated: dict[str, object] = {}
    for side in ("left", "right"):
        if side not in navbar:
            continue
        raw_items = navbar[side]
        if not isinstance(raw_items, list):
            raise ValueError(
                f"Quarto base configuration website.navbar.{side} "
                "must be a list."
            )
        items: list[dict[str, str]] = []
        for index, item_value in enumerate(raw_items):
            path = f"website.navbar.{side}.{index}"
            item = _config_mapping(item_value, path)
            _reject_config_keys(item, {"href", "icon", "text"}, path)
            href = _nonempty_config_text(item.get("href"), f"{path}.href")
            classified = classify_target(href)
            if not (
                (
                    classified.kind is TargetKind.EXTERNAL
                    and classified.scheme in {"https", "mailto"}
                )
                or (
                    classified.kind is TargetKind.LOCAL
                    and classified.path in trusted_hrefs
                )
            ):
                raise ValueError(
                    f"Quarto base configuration {path}.href is not safe."
                )
            generated_item = {"href": href}
            for key in ("icon", "text"):
                if key in item:
                    generated_item[key] = _nonempty_config_text(
                        item[key],
                        f"{path}.{key}",
                    )
            items.append(generated_item)
        generated[side] = items
    return generated


def _generated_html(
    value: object,
) -> tuple[dict[str, object], dict[str, str]]:
    html = _config_mapping(value, "format.html")
    allowed = {
        "citations-hover",
        "code-copy",
        "css",
        "html-math-method",
        "include-after-body",
        "theme",
        "toc",
    }
    _reject_config_keys(html, allowed, "format.html")
    generated: dict[str, object] = {}
    dependencies: dict[str, str] = {}
    for key in ("citations-hover", "code-copy", "toc"):
        if key in html:
            if not isinstance(html[key], bool):
                raise ValueError(
                    f"Quarto base configuration format.html.{key} "
                    "must be boolean."
                )
            generated[key] = html[key]
    if "html-math-method" in html:
        method = html["html-math-method"]
        if method not in {"katex", "mathjax"}:
            raise ValueError(
                "Quarto base configuration format.html.html-math-method "
                "is unsupported."
            )
        generated["html-math-method"] = method
    if "theme" in html:
        theme = html["theme"]
        if isinstance(theme, str):
            themes = (theme,)
        elif (
            isinstance(theme, dict)
            and set(theme) == {"dark", "light"}
            and all(isinstance(item, str) for item in theme.values())
        ):
            themes = tuple(theme.values())
        else:
            raise ValueError(
                "Quarto base configuration format.html.theme is unsupported."
            )
        if any(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", item) is None
            for item in themes
        ):
            raise ValueError(
                "Quarto base configuration format.html.theme is unsupported."
            )
        generated["theme"] = theme
    if "css" in html:
        if html["css"] != "styles.css":
            raise ValueError(
                "Quarto base configuration format.html.css may only be "
                "styles.css."
            )
        generated["css"] = "styles.css"
        dependencies["styles.css"] = "styles.css"
    if "include-after-body" in html:
        include = "_includes/comment-github-link.html"
        if html["include-after-body"] != include:
            raise ValueError(
                "Quarto base configuration format.html.include-after-body "
                f"may only be {include}."
            )
        generated["include-after-body"] = include
        dependencies[include] = include
    return generated, dependencies


def _generated_comments(value: object) -> object:
    if value is False:
        return False
    comments = _config_mapping(value, "comments")
    _reject_config_keys(comments, {"giscus"}, "comments")
    giscus = _config_mapping(comments.get("giscus"), "comments.giscus")
    allowed = {
        "category",
        "category-id",
        "input-position",
        "loading",
        "mapping",
        "reactions-enabled",
        "repo",
        "repo-id",
        "theme",
    }
    _reject_config_keys(giscus, allowed, "comments.giscus")
    generated: dict[str, object] = {}
    for key in ("category", "category-id", "repo", "repo-id"):
        generated[key] = _nonempty_config_text(
            giscus.get(key),
            f"comments.giscus.{key}",
        )
    enum_values = {
        "input-position": {"bottom", "top"},
        "loading": {"eager", "lazy"},
        "mapping": {
            "number",
            "og:title",
            "pathname",
            "specific",
            "title",
            "url",
        },
    }
    for key, choices in enum_values.items():
        selected = giscus.get(key)
        if selected not in choices:
            raise ValueError(
                f"Quarto base configuration comments.giscus.{key} "
                "is unsupported."
            )
        generated[key] = selected
    reactions = giscus.get("reactions-enabled")
    if not isinstance(reactions, bool):
        raise ValueError(
            "Quarto base configuration comments.giscus.reactions-enabled "
            "must be boolean."
        )
    generated["reactions-enabled"] = reactions
    theme = _nonempty_config_text(
        giscus.get("theme"),
        "comments.giscus.theme",
    )
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", theme) is None:
        raise ValueError(
            "Quarto base configuration comments.giscus.theme is unsupported."
        )
    generated["theme"] = theme
    return {"giscus": generated}


def _generated_crossref(value: object) -> dict[str, object]:
    crossref = _config_mapping(value, "crossref")
    _reject_config_keys(crossref, {"custom"}, "crossref")
    custom = crossref.get("custom")
    if not isinstance(custom, list):
        raise ValueError(
            "Quarto base configuration crossref.custom must be a list."
        )
    generated: list[dict[str, object]] = []
    for index, item_value in enumerate(custom):
        path = f"crossref.custom.{index}"
        item = _config_mapping(item_value, path)
        allowed = {
            "key",
            "kind",
            "reference-prefix",
            "space-before-numbering",
        }
        _reject_config_keys(item, allowed, path)
        generated_item: dict[str, object] = {}
        for key in ("key", "kind", "reference-prefix"):
            generated_item[key] = _nonempty_config_text(
                item.get(key),
                f"{path}.{key}",
            )
        for key in ("key", "kind"):
            if (
                re.fullmatch(
                    r"[A-Za-z][A-Za-z0-9_-]*",
                    str(generated_item[key]),
                )
                is None
            ):
                raise ValueError(
                    f"Quarto base configuration {path}.{key} is unsupported."
                )
        spacing = item.get("space-before-numbering")
        if not isinstance(spacing, bool):
            raise ValueError(
                f"Quarto base configuration {path}.space-before-numbering "
                "must be boolean."
            )
        generated_item["space-before-numbering"] = spacing
        generated.append(generated_item)
    return {"custom": generated}


def _generated_config(graph: KnowledgeGraph) -> tuple[dict[str, Any], dict[str, str]]:
    config_path = graph.repo_root / "_quarto.yml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("_quarto.yml must contain a YAML mapping.")
    _reject_config_shortcodes(raw)
    _reject_config_html(raw)
    allowed_top_level = {
        "bibliography",
        "comments",
        "crossref",
        "csl",
        "editor",
        "execute",
        "format",
        "preview",
        "project",
        "website",
    }
    unexpected = sorted(set(raw) - allowed_top_level)
    if unexpected:
        raise ValueError(
            "Quarto base configuration has unsupported top-level key: "
            f"{unexpected[0]}"
        )
    if raw.get("execute") != {"enabled": False}:
        raise ValueError(
            "Quarto base configuration must disable execution exactly."
        )

    project = _config_mapping(raw.get("project"), "project")
    _reject_config_keys(project, {"output-dir", "render", "type"}, "project")
    if project.get("type") != "website":
        raise ValueError(
            "Quarto base configuration project.type must be website."
        )
    if "output-dir" in project and project["output-dir"] != "_site":
        raise ValueError(
            "Quarto base configuration project.output-dir must be _site."
        )
    if "render" in project:
        render = project["render"]
        allowed_render = {
            "index.qmd",
            "theory/index.qmd",
            "theory/**/*.qmd",
        }
        if (
            not isinstance(render, list)
            or not all(
                isinstance(item, str) and item in allowed_render
                for item in render
            )
        ):
            raise ValueError(
                "Quarto base configuration project.render is unsupported."
            )

    raw_website = _config_mapping(raw.get("website"), "website")
    _reject_config_keys(raw_website, {"navbar", "title"}, "website")
    website: dict[str, object] = {
        "title": _nonempty_config_text(
            raw_website.get("title"),
            "website.title",
        )
    }
    if "navbar" in raw_website:
        website["navbar"] = _generated_navbar(
            graph,
            raw_website["navbar"],
        )
    website["sidebar"] = {
        "contents": [
            _sidebar_entry(graph, graph.knowledge_root / "index.qmd")
        ]
    }
    raw_format = _config_mapping(raw.get("format"), "format")
    _reject_config_keys(raw_format, {"html"}, "format")
    html, dependencies = _generated_html(raw_format.get("html"))

    config: dict[str, Any] = {
        "project": {
            "type": "website",
            "output-dir": "_site",
            "render": ["index.qmd", "theory/**/*.qmd"],
        },
        "website": website,
        "format": {"html": html},
    }
    if "comments" in raw:
        config["comments"] = _generated_comments(raw["comments"])
    if "bibliography" in raw:
        if raw["bibliography"] != "references.bib":
            raise ValueError(
                "Quarto base configuration bibliography may only be "
                "references.bib."
            )
        config["bibliography"] = "references.bib"
        dependencies["references.bib"] = "references.bib"
    if "csl" in raw:
        if raw["csl"] != "aps.csl":
            raise ValueError(
                "Quarto base configuration csl may only be aps.csl."
            )
        config["csl"] = "aps.csl"
        dependencies["aps.csl"] = "aps.csl"
    if "crossref" in raw:
        config["crossref"] = _generated_crossref(raw["crossref"])
    config["execute"] = {"enabled": False}
    return config, dependencies


def _page_dependencies(graph: KnowledgeGraph) -> Iterable[Path]:
    page_set = set(graph.pages)
    bibliographies = dict(graph.bibliographies)
    for page, links in graph.all_links:
        for link in links:
            target_text = _local_target(link.target)
            if target_text is None:
                continue
            target = lexical_local_path(page.parent, classify_target(link.target))
            if target not in page_set:
                yield _trusted_asset(graph, target)
        for reference in bibliographies[page]:
            relative = reference.target
            if _local_target(relative) != relative:
                raise ValueError(
                    f"Bibliography path must be local and relative: {relative}"
                )
            bibliography = Path(os.path.abspath(page.parent / relative))
            shared = graph.repo_root / "references.bib"
            if bibliography == shared:
                yield _require_contained_file(graph.repo_root, bibliography)
            elif bibliography.is_relative_to(graph.knowledge_root):
                yield _require_contained_file(
                    graph.knowledge_root,
                    bibliography,
                )
            else:
                raise ValueError(
                    "Bibliography path must remain in theory/ or resolve to "
                    f"references.bib: {relative}"
                )


def materialize_quarto_project(
    *,
    graph: KnowledgeGraph,
    workspace: Path | str,
) -> QuartoProject:
    """Copy validated inputs into a deterministic, hook-free Quarto project."""
    report = validate_knowledge(graph.repo_root)
    if not report.ok:
        raise KnowledgeValidationError(report.diagnostics)
    if graph != report.graph:
        raise ValueError(
            "KnowledgeGraph does not match freshly validated repository state."
        )
    graph = report.graph
    root_index = _validated_homepage(graph)
    dependencies = tuple(
        sorted(
            set(_page_dependencies(graph)),
            key=lambda path: path.relative_to(graph.repo_root).as_posix(),
        )
    )
    config, fixed_dependencies = _generated_config(graph)
    fixed_sources: list[tuple[str, Path]] = []
    for relative in sorted(fixed_dependencies):
        if _local_target(relative) != relative:
            raise ValueError(
                f"Quarto base dependency must be local and relative: {relative}"
            )
        source = _require_contained_file(
            graph.repo_root,
            Path((graph.repo_root / relative).absolute()),
        )
        _audit_fixed_dependency(relative, source)
        fixed_sources.append((relative, source))

    workspace_path = Path(workspace)
    project_dir = workspace_path / "project"
    project_dir.mkdir(parents=True, exist_ok=False)

    _copy_file(root_index, project_dir / "index.qmd")
    for page in graph.pages:
        _copy_file(
            page,
            project_dir / page.relative_to(graph.repo_root),
        )
    for dependency in dependencies:
        _copy_file(
            dependency,
            project_dir / dependency.relative_to(graph.repo_root),
        )

    for relative, source in fixed_sources:
        _copy_file(source, project_dir / relative)
    (project_dir / "_quarto.yml").write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return QuartoProject(
        project_dir=project_dir,
        output_dir=project_dir / "_site",
    )
