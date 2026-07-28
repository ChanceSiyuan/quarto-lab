"""Load the physical trusted-content boundary into a deterministic graph."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .parser import (
    MarkdownLink,
    PageMetadata,
    ParseIssue,
    UnsafeHtml,
    bibliography_links,
    forbidden_frontmatter_keys,
    frontmatter_parse_issues,
    level_two_heading_lines,
    markdown_links,
    page_metadata,
    parse_document,
    raw_html_images,
    raw_html_resources,
    reading_map_links,
    related_topics_links,
    unsafe_html,
)


@dataclass(frozen=True)
class KnowledgeGraph:
    repo_root: Path
    knowledge_root: Path
    pages: tuple[Path, ...]
    topics: tuple[Path, ...]
    reading_maps: tuple[tuple[Path, tuple[MarkdownLink, ...]], ...]
    reading_map_headings: tuple[tuple[Path, tuple[int, ...]], ...]
    metadata: tuple[tuple[Path, PageMetadata], ...]
    bibliographies: tuple[tuple[Path, tuple[MarkdownLink, ...]], ...] = ()
    related_maps: tuple[tuple[Path, tuple[MarkdownLink, ...]], ...] = ()
    related_topic_headings: tuple[tuple[Path, tuple[int, ...]], ...] = ()
    all_links: tuple[tuple[Path, tuple[MarkdownLink, ...]], ...] = ()
    unsafe_html: tuple[tuple[Path, tuple[UnsafeHtml, ...]], ...] = ()
    frontmatter_issues: tuple[tuple[Path, tuple[ParseIssue, ...]], ...] = ()
    forbidden_frontmatter: tuple[
        tuple[Path, tuple[tuple[str, int], ...]],
        ...,
    ] = ()
    symlinks: tuple[Path, ...] = ()


def _discover_knowledge_files(knowledge_root: Path) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    pages: list[Path] = []
    symlinks: list[Path] = []

    def visit(directory: Path) -> None:
        with os.scandir(directory) as scanned:
            entries = sorted(scanned, key=lambda entry: entry.name)
        for entry in entries:
            if entry.name.startswith("."):
                continue
            path = Path(entry.path)
            if entry.is_symlink():
                symlinks.append(path)
            elif entry.is_dir(follow_symlinks=False):
                visit(path)
            elif entry.is_file(follow_symlinks=False) and path.suffix == ".qmd":
                pages.append(path)

    if knowledge_root.is_symlink():
        symlinks.append(knowledge_root)
    elif knowledge_root.is_dir():
        visit(knowledge_root)
    return tuple(pages), tuple(symlinks)


def load_knowledge(repo_root: Path | str) -> KnowledgeGraph:
    root = Path(repo_root).resolve()
    knowledge_root = root / "theory"
    pages, symlinks = _discover_knowledge_files(knowledge_root)
    topics = tuple(path for path in pages if path.name == "index.qmd")
    reading_maps: list[tuple[Path, tuple[MarkdownLink, ...]]] = []
    reading_map_headings: list[tuple[Path, tuple[int, ...]]] = []
    related_maps: list[tuple[Path, tuple[MarkdownLink, ...]]] = []
    related_topic_headings: list[tuple[Path, tuple[int, ...]]] = []
    all_links: list[tuple[Path, tuple[MarkdownLink, ...]]] = []
    unsafe_html_by_page: list[tuple[Path, tuple[UnsafeHtml, ...]]] = []
    metadata: list[tuple[Path, PageMetadata]] = []
    bibliographies: list[tuple[Path, tuple[MarkdownLink, ...]]] = []
    frontmatter_issues: list[tuple[Path, tuple[ParseIssue, ...]]] = []
    forbidden_frontmatter: list[
        tuple[Path, tuple[tuple[str, int], ...]]
    ] = []

    for path in pages:
        document = parse_document(path)
        if path.name == "index.qmd":
            reading_maps.append((path, reading_map_links(document)))
            reading_map_headings.append(
                (
                    path,
                    level_two_heading_lines(document, "Reading map"),
                )
            )
            related_maps.append((path, related_topics_links(document)))
            related_topic_headings.append(
                (
                    path,
                    level_two_heading_lines(document, "Related topics"),
                )
            )
        all_links.append(
            (
                path,
                tuple(
                    sorted(
                        (
                            *markdown_links(document),
                            *raw_html_images(document),
                            *raw_html_resources(document),
                        ),
                        key=lambda link: (
                            link.line,
                            link.column,
                            link.kind,
                            link.target,
                        ),
                    )
                ),
            )
        )
        unsafe_html_by_page.append((path, unsafe_html(document)))
        metadata.append((path, page_metadata(document)))
        bibliographies.append((path, bibliography_links(document)))
        frontmatter_issues.append(
            (path, frontmatter_parse_issues(document))
        )
        forbidden_frontmatter.append(
            (path, forbidden_frontmatter_keys(document))
        )
    return KnowledgeGraph(
        repo_root=root,
        knowledge_root=knowledge_root,
        pages=pages,
        topics=topics,
        reading_maps=tuple(reading_maps),
        reading_map_headings=tuple(reading_map_headings),
        related_maps=tuple(related_maps),
        related_topic_headings=tuple(related_topic_headings),
        all_links=tuple(all_links),
        metadata=tuple(metadata),
        bibliographies=tuple(bibliographies),
        unsafe_html=tuple(unsafe_html_by_page),
        frontmatter_issues=tuple(frontmatter_issues),
        forbidden_frontmatter=tuple(forbidden_frontmatter),
        symlinks=symlinks,
    )
