"""Deterministically resolve a query into a curated Reading Bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unicodedata

from .graph import KnowledgeGraph
from .parser import PageMetadata
from .targets import TargetKind, classify_target, lexical_local_path
from .validate import KnowledgeValidationError, validate_knowledge


@dataclass(frozen=True)
class _RankedMatch:
    page: Path
    match_kind: str
    tier: int
    matched_terms: int


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().strip()


def _tokenize(text: str) -> tuple[str, ...]:
    normalized = _normalize(text)
    terms: list[str] = []
    current: list[str] = []
    for character in normalized:
        if unicodedata.category(character)[0] in {"L", "N"}:
            current.append(character)
        elif current:
            terms.append("".join(current))
            current = []
    if current:
        terms.append("".join(current))
    return tuple(terms)


def _repo_path(graph: KnowledgeGraph, path: Path) -> str:
    return path.relative_to(graph.repo_root).as_posix()


def _ancestor_indexes(graph: KnowledgeGraph, topic: Path) -> list[Path]:
    ancestors = [topic]
    root_index = graph.knowledge_root / "index.qmd"
    while ancestors[-1] != root_index:
        parent = ancestors[-1].parent.parent / "index.qmd"
        ancestors.append(parent)
    ancestors.reverse()
    return ancestors


def _topic_for(page: Path) -> Path:
    return page if page.name == "index.qmd" else page.parent / "index.qmd"


def _reading_map_targets(graph: KnowledgeGraph, index: Path) -> list[Path]:
    links = dict(graph.reading_maps)[index]
    targets: list[Path] = []
    for link in links:
        classified = classify_target(link.target)
        if classified.kind is not TargetKind.LOCAL:
            continue
        target = lexical_local_path(index.parent, classified)
        if target in graph.pages:
            targets.append(target)
    return targets


def _curated_ranks(graph: KnowledgeGraph) -> dict[Path, int]:
    ranks: dict[Path, int] = {}

    def visit(page: Path) -> None:
        if page in ranks:
            return
        ranks[page] = len(ranks)
        if page.name == "index.qmd":
            for child in _reading_map_targets(graph, page):
                visit(child)

    visit(graph.knowledge_root / "index.qmd")
    for page in sorted(graph.pages, key=lambda item: _repo_path(graph, item)):
        visit(page)
    return ranks


def _match_page(
    page: Path,
    metadata: PageMetadata,
    normalized_query: str,
    query_terms: frozenset[str],
) -> _RankedMatch | None:
    title_terms = frozenset(_tokenize(metadata.title))
    alias_terms = frozenset(
        term for alias in metadata.aliases for term in _tokenize(alias)
    )
    description_terms = frozenset(_tokenize(metadata.description))
    body_terms = frozenset(_tokenize(metadata.body))
    match: tuple[str, int, int] | None
    if normalized_query == _normalize(metadata.title):
        match = ("exact-title", 0, len(query_terms))
    elif normalized_query in {_normalize(alias) for alias in metadata.aliases}:
        match = ("exact-alias", 1, len(query_terms))
    elif overlap := query_terms.intersection(title_terms):
        match = ("title-term", 2, len(overlap))
    elif overlap := query_terms.intersection(alias_terms):
        match = ("alias-term", 3, len(overlap))
    elif overlap := query_terms.intersection(description_terms):
        match = ("description-term", 4, len(overlap))
    elif overlap := query_terms.intersection(body_terms):
        match = ("body-term", 5, len(overlap))
    else:
        match = None
    if match is None:
        return None
    return _RankedMatch(
        page=page,
        match_kind=match[0],
        tier=match[1],
        matched_terms=match[2],
    )


def _candidate_result(
    match: _RankedMatch,
    graph: KnowledgeGraph,
    title: str,
) -> dict[str, object]:
    return {
        "page": _repo_path(graph, match.page),
        "topic": _repo_path(graph, _topic_for(match.page)),
        "title": title,
        "matchKind": match.match_kind,
        "tier": match.tier,
        "matchedTerms": match.matched_terms,
    }


def resolve_knowledge(query: str, repo_root: Path | str) -> dict[str, object]:
    report = validate_knowledge(repo_root)
    if not report.ok:
        raise KnowledgeValidationError(report.diagnostics)
    graph = report.graph
    normalized_query = _normalize(query)
    if not _tokenize(query):
        raise ValueError("Knowledge query must contain at least one letter or number.")
    metadata = dict(graph.metadata)
    query_terms = frozenset(_tokenize(query))
    curated_ranks = _curated_ranks(graph)
    matches = [
        match
        for page, page_metadata in graph.metadata
        if (
            match := _match_page(
                page,
                page_metadata,
                normalized_query,
                query_terms,
            )
        )
    ]
    if not matches:
        return {
            "schemaVersion": 1,
            "query": query,
            "status": "no-match",
            "bundle": None,
            "alternatives": [],
        }
    matches.sort(
        key=lambda match: (
            match.tier,
            -match.matched_terms,
            curated_ranks.get(match.page, len(curated_ranks)),
            _repo_path(graph, match.page),
        )
    )
    semantic_best = (matches[0].tier, matches[0].matched_terms)
    best_matches = [
        match
        for match in matches
        if (match.tier, match.matched_terms) == semantic_best
    ]
    if len({_topic_for(match.page) for match in best_matches}) > 1:
        return {
            "schemaVersion": 1,
            "query": query,
            "status": "ambiguous",
            "bundle": None,
            "alternatives": [
                _candidate_result(
                    match,
                    graph=graph,
                    title=metadata[match.page].title,
                )
                for match in best_matches
            ],
        }
    topic = _topic_for(best_matches[0].page)
    ancestors = _ancestor_indexes(graph, topic)
    if any(match.page.name == "index.qmd" for match in best_matches):
        content_pages = [
            page
            for page in _reading_map_targets(graph, topic)
            if page.name != "index.qmd"
        ]
    else:
        curated_rank = {
            page: rank
            for rank, page in enumerate(_reading_map_targets(graph, topic))
        }
        content_pages = sorted(
            (
                match.page
                for match in best_matches
                if _topic_for(match.page) == topic
            ),
            key=lambda page: (
                curated_rank.get(page, len(curated_rank)),
                _repo_path(graph, page),
            ),
        )
    ordered = list(dict.fromkeys([*ancestors, *content_pages]))
    return {
        "schemaVersion": 1,
        "query": query,
        "status": "match",
        "bundle": {
            "topic": _repo_path(graph, topic),
            "ancestorIndexes": [_repo_path(graph, page) for page in ancestors],
            "contentPages": [_repo_path(graph, page) for page in content_pages],
            "orderedFiles": [_repo_path(graph, page) for page in ordered],
        },
        "alternatives": [],
    }
