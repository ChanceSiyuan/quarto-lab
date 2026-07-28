"""Validate the minimum physical shape of trusted knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .assets import TrustedAssetError, audit_trusted_asset
from .graph import KnowledgeGraph, load_knowledge
from .targets import TargetKind, classify_target, lexical_local_path
from .types import Diagnostic


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    graph: KnowledgeGraph
    diagnostics: tuple[Diagnostic, ...]


class KnowledgeValidationError(ValueError):
    """Raised when a public operation receives an invalid trusted graph."""

    def __init__(self, diagnostics: tuple[Diagnostic, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__("\n".join(diagnostics))


def _diagnostic(
    graph: KnowledgeGraph,
    path: Path,
    line: int,
    column: int,
    code: str,
    message: str,
) -> Diagnostic:
    return Diagnostic(
        file=path.relative_to(graph.repo_root).as_posix(),
        line=line,
        column=column,
        code=code,
        message=message,
    )


def _symlink_component(knowledge_root: Path, target: Path) -> Path | None:
    if not target.is_relative_to(knowledge_root):
        return None
    current = knowledge_root
    if current.is_symlink():
        return current
    for part in target.relative_to(knowledge_root).parts:
        current = current / part
        if current.is_symlink():
            return current
        if not current.exists():
            break
    return None


def validate_knowledge(repo_root: Path | str) -> ValidationReport:
    graph = load_knowledge(repo_root)
    diagnostics: list[Diagnostic] = []
    known_symlinks = set(graph.symlinks)
    root_index = graph.knowledge_root / "index.qmd"
    if root_index not in graph.pages:
        diagnostics.append(
            _diagnostic(
                graph,
                root_index,
                1,
                1,
                "ROOT_INDEX_MISSING",
                "Root index is required.",
            )
        )

    for symlink in graph.symlinks:
        diagnostics.append(
            _diagnostic(
                graph,
                symlink,
                1,
                1,
                "SYMLINK_FORBIDDEN",
                "Trusted knowledge may not contain symbolic links.",
            )
        )

    directories_with_pages: set[Path] = set()
    for page in graph.pages:
        directory = page.parent
        while directory.is_relative_to(graph.knowledge_root):
            directories_with_pages.add(directory)
            if directory == graph.knowledge_root:
                break
            directory = directory.parent
    for directory in sorted(directories_with_pages):
        index = directory / "index.qmd"
        if index not in graph.pages:
            relative = directory.relative_to(graph.repo_root).as_posix()
            diagnostics.append(
                Diagnostic(
                    file=relative,
                    line=1,
                    column=1,
                    code="TOPIC_INDEX_MISSING",
                    message="A directory containing QMD pages requires index.qmd.",
                )
            )

    for page, issues in graph.frontmatter_issues:
        relative = page.relative_to(graph.repo_root).as_posix()
        for issue in issues:
            diagnostics.append(
                Diagnostic(
                    file=relative,
                    line=issue.line,
                    column=issue.column,
                    code=issue.code,
                    message=issue.message,
                )
            )
    for page, forbidden_keys in graph.forbidden_frontmatter:
        relative = page.relative_to(graph.repo_root).as_posix()
        for key, line in forbidden_keys:
            diagnostics.append(
                Diagnostic(
                    file=relative,
                    line=line,
                    column=1,
                    code="FRONTMATTER_KEY_FORBIDDEN",
                    message=(
                        "Frontmatter key is not allowed in trusted knowledge: "
                        f"{key}"
                    ),
                )
            )

    for page, references in graph.bibliographies:
        relative = page.relative_to(graph.repo_root).as_posix()
        for reference in references:
            target_text = reference.target
            classified = classify_target(target_text)
            if classified.kind is not TargetKind.LOCAL:
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=reference.line,
                        column=reference.column,
                        code="BIBLIOGRAPHY_OUTSIDE_KNOWLEDGE",
                        message=(
                            "Bibliography path must be local and relative: "
                            f"{target_text}"
                        ),
                    )
                )
                continue
            if classified.path != target_text:
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=reference.line,
                        column=reference.column,
                        code="BIBLIOGRAPHY_INVALID",
                        message=(
                            "Bibliography paths may not contain query or "
                            f"fragment syntax: {target_text}"
                        ),
                    )
                )
                continue
            target = lexical_local_path(page.parent, classified)
            shared_bibliography = graph.repo_root / "references.bib"
            if not (
                target.is_relative_to(graph.knowledge_root)
                or target == shared_bibliography
            ):
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=reference.line,
                        column=reference.column,
                        code="BIBLIOGRAPHY_OUTSIDE_KNOWLEDGE",
                        message=(
                            "Bibliography must remain in theory/ or resolve "
                            f"to references.bib: {target_text}"
                        ),
                    )
                )
                continue
            if target.suffix.casefold() != ".bib":
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=reference.line,
                        column=reference.column,
                        code="BIBLIOGRAPHY_INVALID",
                        message=(
                            "Bibliography dependency must have a .bib suffix: "
                            f"{target_text}"
                        ),
                    )
                )
                continue
            symlink = (
                _symlink_component(graph.knowledge_root, target)
                if target.is_relative_to(graph.knowledge_root)
                else target if target.is_symlink() else None
            )
            if symlink is not None:
                if symlink not in known_symlinks:
                    diagnostics.append(
                        Diagnostic(
                            file=relative,
                            line=reference.line,
                            column=reference.column,
                            code="SYMLINK_FORBIDDEN",
                            message=(
                                "Bibliography paths may not traverse symlinks: "
                                f"{target_text}"
                            ),
                        )
                    )
                continue
            if not target.is_file():
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=reference.line,
                        column=reference.column,
                        code="BIBLIOGRAPHY_MISSING",
                        message=(
                            "Bibliography dependency does not exist: "
                            f"{target_text}"
                        ),
                    )
                )

    page_set = set(graph.pages)
    special_links = {
        (page, link.line, link.column, link.target)
        for page, links in (*graph.reading_maps, *graph.related_maps)
        for link in links
    }
    for page, links in graph.all_links:
        relative = page.relative_to(graph.repo_root).as_posix()
        for link in links:
            if (page, link.line, link.column, link.target) in special_links:
                continue
            classified = classify_target(link.target)
            if classified.kind in {TargetKind.EMPTY, TargetKind.EXTERNAL}:
                continue
            if classified.kind is TargetKind.UNSUPPORTED_SCHEME:
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_SCHEME_UNSUPPORTED",
                        message=(
                            "Unsupported target scheme is forbidden: "
                            f"{link.target}"
                        ),
                    )
                )
                continue
            if classified.kind is TargetKind.ABSOLUTE:
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_ABSOLUTE",
                        message=f"Absolute local targets are forbidden: {link.target}",
                    )
                )
                continue
            if classified.kind is TargetKind.BACKSLASH:
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_OUTSIDE_KNOWLEDGE",
                        message=f"Backslash local targets are forbidden: {link.target}",
                    )
                )
                continue
            target = lexical_local_path(page.parent, classified)
            if not target.is_relative_to(graph.knowledge_root):
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_OUTSIDE_KNOWLEDGE",
                        message=f"Local target escapes theory/: {link.target}",
                    )
                )
                continue
            symlink = _symlink_component(graph.knowledge_root, target)
            if symlink is not None:
                if symlink not in known_symlinks:
                    diagnostics.append(
                        Diagnostic(
                            file=relative,
                            line=link.line,
                            column=link.column,
                            code="SYMLINK_FORBIDDEN",
                            message=(
                                "Local targets may not traverse symlinks: "
                                f"{link.target}"
                            ),
                        )
                    )
                continue
            if not target.exists():
                missing_code = {
                    "image": "IMAGE_MISSING",
                    "resource": "ASSET_MISSING",
                }.get(link.kind, "LINK_MISSING")
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code=missing_code,
                        message=(
                            f"Local {link.kind} target does not exist: {link.target}"
                        ),
                    )
                )
                continue
            if target not in page_set:
                try:
                    audit_trusted_asset(target)
                except TrustedAssetError as error:
                    diagnostics.append(
                        Diagnostic(
                            file=relative,
                            line=link.line,
                            column=link.column,
                            code=error.code,
                            message=f"{error}: {link.target}",
                        )
                    )

    html_codes = {
        "script": ("SCRIPT_FORBIDDEN", "Raw script elements are forbidden."),
        "inline-handler": (
            "INLINE_HANDLER_FORBIDDEN",
            "Inline HTML event handlers are forbidden.",
        ),
        "iframe": ("IFRAME_FORBIDDEN", "Raw iframe elements are forbidden."),
        "object": ("OBJECT_FORBIDDEN", "Raw object elements are forbidden."),
        "embed": ("EMBED_FORBIDDEN", "Raw embed elements are forbidden."),
        "form": ("FORM_FORBIDDEN", "Raw form elements are forbidden."),
        "style": ("STYLE_FORBIDDEN", "Raw style elements are forbidden."),
        "style-url": (
            "STYLE_URL_FORBIDDEN",
            "Network-loading CSS in inline styles is forbidden.",
        ),
        "srcset": (
            "SRCSET_FORBIDDEN",
            "Raw HTML srcset attributes are forbidden.",
        ),
        "base": ("BASE_FORBIDDEN", "Raw base elements are forbidden."),
        "link": ("LINK_ELEMENT_FORBIDDEN", "Raw link elements are forbidden."),
        "frame": ("FRAME_FORBIDDEN", "Raw frame elements are forbidden."),
        "frameset": (
            "FRAMESET_FORBIDDEN",
            "Raw frameset elements are forbidden.",
        ),
        "foreignobject": (
            "FOREIGN_OBJECT_FORBIDDEN",
            "Raw foreignObject elements are forbidden.",
        ),
        "portal": ("PORTAL_FORBIDDEN", "Raw portal elements are forbidden."),
        "javascript-url": (
            "JAVASCRIPT_URL_FORBIDDEN",
            "JavaScript URLs in raw HTML are forbidden.",
        ),
        "meta-refresh": (
            "META_REFRESH_FORBIDDEN",
            "Raw meta refresh elements are forbidden.",
        ),
        "quarto-shortcode": (
            "QUARTO_SHORTCODE_FORBIDDEN",
            "Quarto shortcodes are forbidden in trusted knowledge.",
        ),
    }
    for page, unsafe_items in graph.unsafe_html:
        relative = page.relative_to(graph.repo_root).as_posix()
        for item in unsafe_items:
            code, message = html_codes[item.kind]
            diagnostics.append(
                Diagnostic(
                    file=relative,
                    line=item.line,
                    column=item.column,
                    code=code,
                    message=message,
                )
            )

    heading_lines_by_index = dict(graph.reading_map_headings)
    for index, heading_lines in graph.reading_map_headings:
        if len(heading_lines) != 1:
            relative = index.relative_to(graph.repo_root).as_posix()
            diagnostics.append(
                Diagnostic(
                    file=relative,
                    line=1,
                    column=1,
                    code="INDEX_READING_MAP_REQUIRED",
                    message=(
                        "A topic index requires exactly one level-two Reading map."
                    ),
                )
            )

    for index, links in graph.reading_maps:
        if len(heading_lines_by_index[index]) != 1:
            continue
        direct_content = {
            page for page in graph.pages if page.parent == index.parent and page != index
        }
        direct_topics = {
            topic
            for topic in graph.topics
            if topic != index and topic.parent.parent == index.parent
        }
        direct_children = direct_content | direct_topics
        mapped_targets: set[Path] = set()
        has_invalid_target = False
        for link in links:
            classified = classify_target(link.target)
            if classified.kind in {
                TargetKind.EMPTY,
                TargetKind.EXTERNAL,
                TargetKind.UNSUPPORTED_SCHEME,
            }:
                has_invalid_target = True
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="NON_DIRECT_CHILD",
                        message=(
                            "Reading-map entries must target direct local children: "
                            f"{link.target}"
                        ),
                    )
                )
                continue
            if classified.kind is TargetKind.ABSOLUTE:
                has_invalid_target = True
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_ABSOLUTE",
                        message=f"Absolute local targets are forbidden: {link.target}",
                    )
                )
                continue
            if classified.kind is TargetKind.BACKSLASH:
                has_invalid_target = True
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_OUTSIDE_KNOWLEDGE",
                        message=f"Backslash local targets are forbidden: {link.target}",
                    )
                )
                continue
            target = lexical_local_path(index.parent, classified)
            if not target.is_relative_to(graph.knowledge_root):
                has_invalid_target = True
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_OUTSIDE_KNOWLEDGE",
                        message=f"Local target escapes theory/: {link.target}",
                    )
                )
                continue
            symlink = _symlink_component(graph.knowledge_root, target)
            if symlink is not None:
                has_invalid_target = True
                if symlink not in known_symlinks:
                    relative = index.relative_to(graph.repo_root).as_posix()
                    diagnostics.append(
                        Diagnostic(
                            file=relative,
                            line=link.line,
                            column=link.column,
                            code="SYMLINK_FORBIDDEN",
                            message=(
                                "Local targets may not traverse symlinks: "
                                f"{link.target}"
                            ),
                        )
                    )
                continue
            if target not in page_set:
                has_invalid_target = True
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_MISSING",
                        message=(
                            "Reading-map target does not exist: "
                            f"{link.target}"
                        ),
                    )
                )
                continue
            if target not in direct_children:
                has_invalid_target = True
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="NON_DIRECT_CHILD",
                        message=(
                            "Reading-map target is not a direct child: "
                            f"{link.target}"
                        ),
                    )
                )
                continue
            if target in mapped_targets:
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="DUPLICATE_CHILD",
                        message=(
                            "Direct child occurs more than once in Reading map: "
                            f"{link.target}"
                        ),
                    )
                )
                continue
            mapped_targets.add(target)

        if has_invalid_target:
            continue
        for child in sorted(direct_children - mapped_targets):
            child_relative = child.relative_to(graph.repo_root).as_posix()
            index_relative = index.relative_to(graph.repo_root).as_posix()
            diagnostics.append(
                Diagnostic(
                    file=child_relative,
                    line=1,
                    column=1,
                    code="ORPHAN_CHILD",
                    message=(
                        "Direct child is missing from "
                        f"{index_relative} Reading map."
                    ),
                )
            )

    for index, heading_lines in graph.related_topic_headings:
        if len(heading_lines) > 1:
            relative = index.relative_to(graph.repo_root).as_posix()
            diagnostics.append(
                Diagnostic(
                    file=relative,
                    line=heading_lines[1],
                    column=1,
                    code="RELATED_TOPICS_DUPLICATE",
                    message="A topic index may contain at most one Related topics heading.",
                )
            )

    topic_set = set(graph.topics)
    for index, links in graph.related_maps:
        if len(dict(graph.related_topic_headings)[index]) > 1:
            continue
        for link in links:
            classified = classify_target(link.target)
            if classified.kind in {
                TargetKind.EMPTY,
                TargetKind.EXTERNAL,
                TargetKind.UNSUPPORTED_SCHEME,
            }:
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="RELATED_TARGET_NOT_INDEX",
                        message=(
                            "Related-topic target must be a local index.qmd: "
                            f"{link.target}"
                        ),
                    )
                )
                continue
            if classified.kind is TargetKind.ABSOLUTE:
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_ABSOLUTE",
                        message=f"Absolute local targets are forbidden: {link.target}",
                    )
                )
                continue
            if classified.kind is TargetKind.BACKSLASH:
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_OUTSIDE_KNOWLEDGE",
                        message=f"Backslash local targets are forbidden: {link.target}",
                    )
                )
                continue
            target = lexical_local_path(index.parent, classified)
            if not target.is_relative_to(graph.knowledge_root):
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_OUTSIDE_KNOWLEDGE",
                        message=f"Local target escapes theory/: {link.target}",
                    )
                )
                continue
            symlink = _symlink_component(graph.knowledge_root, target)
            if symlink is not None:
                if symlink not in known_symlinks:
                    relative = index.relative_to(graph.repo_root).as_posix()
                    diagnostics.append(
                        Diagnostic(
                            file=relative,
                            line=link.line,
                            column=link.column,
                            code="SYMLINK_FORBIDDEN",
                            message=(
                                "Local targets may not traverse symlinks: "
                                f"{link.target}"
                            ),
                        )
                    )
                continue
            if target not in page_set:
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="LINK_MISSING",
                        message=(
                            "Related-topic target does not exist: "
                            f"{link.target}"
                        ),
                    )
                )
                continue
            if target not in topic_set:
                relative = index.relative_to(graph.repo_root).as_posix()
                diagnostics.append(
                    Diagnostic(
                        file=relative,
                        line=link.line,
                        column=link.column,
                        code="RELATED_TARGET_NOT_INDEX",
                        message=(
                            "Related-topic target must be an index.qmd: "
                            f"{link.target}"
                        ),
                    )
                )

    diagnostics.sort(key=lambda diagnostic: diagnostic.sort_key)
    return ValidationReport(
        ok=not diagnostics,
        graph=graph,
        diagnostics=tuple(diagnostics),
    )
