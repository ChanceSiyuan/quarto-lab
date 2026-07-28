"""Parse the small Markdown surface owned by the Knowledge Graph."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import TypeAlias
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.token import Token
import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode



def _expose_link_target_to_policy(_target: str) -> bool:
    return True


MARKDOWN = MarkdownIt("commonmark", {"html": True})
# markdown-it otherwise hides protocols such as ``file:`` and ``javascript:``
# from its AST while Pandoc still renders them. Expose every parsed target here
# and let the KnowledgeGraph's stricter target policy accept or reject it.
MARKDOWN.validateLink = _expose_link_target_to_policy

SAFE_FRONTMATTER_KEYS = frozenset(
    {
        "abstract",
        "aliases",
        "bibliography",
        "categories",
        "date",
        "description",
        "lang",
        "subtitle",
        "tags",
        "title",
    }
)
QUARTO_SHORTCODE_PATTERN = re.compile(r"\{\{[<%]")
HTML_URL_ATTRIBUTES = frozenset(
    {
        "action",
        "background",
        "cite",
        "data",
        "formaction",
        "href",
        "longdesc",
        "manifest",
        "poster",
        "src",
        "xlink:href",
    }
)
FORBIDDEN_HTML_TAGS = frozenset(
    {
        "base",
        "embed",
        "foreignobject",
        "form",
        "frame",
        "frameset",
        "iframe",
        "link",
        "object",
        "portal",
        "script",
        "style",
    }
)


def _is_escaped(source: str, offset: int) -> bool:
    backslashes = 0
    cursor = offset - 1
    while cursor >= 0 and source[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def _mask_range(characters: list[str], start: int, end: int) -> None:
    for offset in range(start, end):
        if characters[offset] not in "\r\n":
            characters[offset] = " "


def _mask_math(source: str) -> str:
    """Blank Quarto math while preserving every source position."""
    characters = list(source)
    cursor = 0
    while cursor < len(source):
        if source.startswith("$$", cursor) and not _is_escaped(source, cursor):
            closing = source.find("$$", cursor + 2)
            while closing >= 0 and _is_escaped(source, closing):
                closing = source.find("$$", closing + 2)
            if closing >= 0:
                _mask_range(characters, cursor, closing + 2)
                cursor = closing + 2
                continue
        if (
            source.startswith(r"\(", cursor)
            or source.startswith(r"\[", cursor)
        ) and not _is_escaped(source, cursor):
            closing_delimiter = (
                r"\)" if source.startswith(r"\(", cursor) else r"\]"
            )
            closing = source.find(closing_delimiter, cursor + 2)
            if closing >= 0:
                _mask_range(characters, cursor, closing + 2)
                cursor = closing + 2
                continue
        if (
            source[cursor] == "$"
            and not _is_escaped(source, cursor)
            and (cursor + 1 >= len(source) or source[cursor + 1] != "$")
            and cursor + 1 < len(source)
            and not source[cursor + 1].isspace()
        ):
            line_end = source.find("\n", cursor + 1)
            if line_end < 0:
                line_end = len(source)
            closing = cursor + 1
            masked = False
            while True:
                closing = source.find("$", closing, line_end)
                if closing < 0:
                    break
                if (
                    not _is_escaped(source, closing)
                    and source[closing - 1].isspace() is False
                    and (
                        closing + 1 >= len(source)
                        or not source[closing + 1].isdigit()
                    )
                ):
                    _mask_range(characters, cursor, closing + 1)
                    cursor = closing + 1
                    masked = True
                    break
                closing += 1
            if masked:
                continue
        cursor += 1
    return "".join(characters)


def _parse_markdown(body: str) -> list[Token]:
    return MARKDOWN.parse(_mask_math(body))


@dataclass(frozen=True)
class MarkdownLink:
    label: str
    target: str
    line: int
    column: int
    kind: str = "link"


@dataclass(frozen=True)
class PageMetadata:
    title: str
    description: str
    aliases: tuple[str, ...]
    body: str


@dataclass(frozen=True)
class ParseIssue:
    code: str
    message: str
    line: int
    column: int


@dataclass(frozen=True)
class UnsafeHtml:
    kind: str
    line: int
    column: int


@dataclass(frozen=True)
class ParsedDocument:
    """One immutable source/AST snapshot for a single graph load."""

    path: Path
    source: str
    lines: tuple[str, ...]
    body: str
    line_offset: int
    tokens: tuple[Token, ...]


DocumentInput: TypeAlias = Path | ParsedDocument


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


class _DuplicateKeyError(ConstructorError):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if key in mapping:
            raise _DuplicateKeyError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def parse_document(path: Path) -> ParsedDocument:
    """Read and Markdown-parse a page exactly once for one graph load."""
    source = path.read_text(encoding="utf-8")
    lines = tuple(source.splitlines())
    body = source
    line_offset = 0
    if not lines or lines[0] != "---":
        return ParsedDocument(
            path=path,
            source=source,
            lines=lines,
            body=body,
            line_offset=line_offset,
            tokens=tuple(_parse_markdown(body)),
        )
    for index, line in enumerate(lines[1:], start=1):
        if line != "---":
            continue
        line_offset = index + 1
        body = "\n".join(lines[line_offset:])
        break
    return ParsedDocument(
        path=path,
        source=source,
        lines=lines,
        body=body,
        line_offset=line_offset,
        tokens=tuple(_parse_markdown(body)),
    )


def _document(value: DocumentInput) -> ParsedDocument:
    return value if isinstance(value, ParsedDocument) else parse_document(value)


def page_metadata(path: DocumentInput) -> PageMetadata:
    document = _document(path)
    body = document.body
    lines = document.lines
    raw_frontmatter = ""
    if lines and lines[0] == "---":
        closing = next(
            (index for index, line in enumerate(lines[1:], start=1) if line == "---"),
            None,
        )
        if closing is not None:
            raw_frontmatter = "\n".join(lines[1:closing])
    try:
        parsed = (
            yaml.load(raw_frontmatter, Loader=_UniqueKeyLoader)
            if raw_frontmatter
            else {}
        )
    except yaml.YAMLError:
        parsed = {}
    data = parsed if isinstance(parsed, dict) else {}
    aliases_value = data.get("aliases", ())
    aliases = (
        tuple(str(alias) for alias in aliases_value)
        if isinstance(aliases_value, list)
        else ()
    )
    return PageMetadata(
        title=str(data.get("title", "")).strip(),
        description=str(data.get("description", "")).strip(),
        aliases=aliases,
        body=body,
    )


def frontmatter_parse_issues(path: DocumentInput) -> tuple[ParseIssue, ...]:
    lines = _document(path).lines
    if not lines or lines[0] != "---":
        return (
            ParseIssue(
                code="FRONTMATTER_MISSING",
                message="Trusted knowledge requires an opening YAML frontmatter block.",
                line=1,
                column=1,
            ),
        )
    closing = next(
        (index for index, line in enumerate(lines[1:], start=1) if line == "---"),
        None,
    )
    if closing is None:
        return (
            ParseIssue(
                code="FRONTMATTER_INVALID",
                message="Opening YAML frontmatter has no exact closing delimiter.",
                line=1,
                column=1,
            ),
        )
    raw_frontmatter = "\n".join(lines[1:closing])
    try:
        parsed = yaml.load(raw_frontmatter, Loader=_UniqueKeyLoader)
    except _DuplicateKeyError as error:
        mark = error.problem_mark
        return (
            ParseIssue(
                code="FRONTMATTER_DUPLICATE_KEY",
                message=error.problem or "Duplicate YAML key.",
                line=(mark.line + 2) if mark is not None else 1,
                column=(mark.column + 1) if mark is not None else 1,
            ),
        )
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        return (
            ParseIssue(
                code="FRONTMATTER_INVALID",
                message=getattr(error, "problem", None) or "Invalid YAML frontmatter.",
                line=(mark.line + 2) if mark is not None else 1,
                column=(mark.column + 1) if mark is not None else 1,
            ),
        )
    if not isinstance(parsed, dict):
        return (
            ParseIssue(
                code="FRONTMATTER_INVALID",
                message="YAML frontmatter must be a mapping.",
                line=2,
                column=1,
            ),
        )
    data = parsed
    shortcode_matches = tuple(QUARTO_SHORTCODE_PATTERN.finditer(raw_frontmatter))
    if shortcode_matches:
        issues: list[ParseIssue] = []
        for match in shortcode_matches:
            prefix = raw_frontmatter[: match.start()]
            issues.append(
                ParseIssue(
                    code="QUARTO_SHORTCODE_FORBIDDEN",
                    message=(
                        "Quarto shortcodes are forbidden in trusted "
                        "frontmatter."
                    ),
                    line=prefix.count("\n") + 2,
                    column=match.start() - prefix.rfind("\n"),
                )
            )
        return tuple(issues)
    yaml_document = yaml.compose(raw_frontmatter, Loader=yaml.SafeLoader)
    decoded_shortcodes = _yaml_shortcode_nodes(yaml_document)
    if decoded_shortcodes:
        return tuple(
            ParseIssue(
                code="QUARTO_SHORTCODE_FORBIDDEN",
                message=(
                    "Quarto shortcodes are forbidden in trusted "
                    "frontmatter."
                ),
                line=node.start_mark.line + 2,
                column=node.start_mark.column + 1,
            )
            for node in decoded_shortcodes
        )
    decoded_html = tuple(
        node
        for node in _yaml_scalar_nodes(yaml_document)
        if contains_html_markup(str(node.value))
    )
    if decoded_html:
        return tuple(
            ParseIssue(
                code="FRONTMATTER_HTML_FORBIDDEN",
                message="HTML is forbidden in trusted frontmatter.",
                line=node.start_mark.line + 2,
                column=node.start_mark.column + 1,
            )
            for node in decoded_html
        )
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return (
            ParseIssue(
                code="TITLE_REQUIRED",
                message="Trusted knowledge requires a nonempty string title.",
                line=2,
                column=1,
            ),
        )
    aliases = data.get("aliases")
    if aliases is not None and not (
        isinstance(aliases, list)
        and all(
            isinstance(alias, str) and alias.strip()
            for alias in aliases
        )
    ):
        return (
            ParseIssue(
                code="ALIASES_INVALID",
                message="Aliases must be a list of nonempty strings.",
                line=_frontmatter_key_line(raw_frontmatter, "aliases"),
                column=1,
            ),
        )
    bibliography = data.get("bibliography")
    if bibliography is not None and not (
        (isinstance(bibliography, str) and bibliography.strip())
        or (
            isinstance(bibliography, list)
            and bool(bibliography)
            and all(
                isinstance(item, str) and item.strip()
                for item in bibliography
            )
        )
    ):
        return (
            ParseIssue(
                code="BIBLIOGRAPHY_INVALID",
                message=(
                    "Bibliography must be a nonempty path or list of paths."
                ),
                line=_frontmatter_key_line(
                    raw_frontmatter,
                    "bibliography",
                ),
                column=1,
            ),
        )
    return ()


def _yaml_scalar_nodes(
    node: Node | None,
    seen: set[int] | None = None,
) -> tuple[ScalarNode, ...]:
    if node is None:
        return ()
    visited = seen if seen is not None else set()
    identity = id(node)
    if identity in visited:
        return ()
    visited.add(identity)
    if isinstance(node, ScalarNode):
        return (node,)
    if isinstance(node, SequenceNode):
        return tuple(
            matched
            for child in node.value
            for matched in _yaml_scalar_nodes(child, visited)
        )
    if isinstance(node, MappingNode):
        return tuple(
            matched
            for key, value in node.value
            for child in (key, value)
            for matched in _yaml_scalar_nodes(child, visited)
        )
    return ()


def _yaml_shortcode_nodes(node: Node | None) -> tuple[ScalarNode, ...]:
    return tuple(
        scalar
        for scalar in _yaml_scalar_nodes(node)
        if QUARTO_SHORTCODE_PATTERN.search(str(scalar.value))
    )


def _frontmatter_key_line(raw_frontmatter: str, wanted: str) -> int:
    try:
        document = yaml.compose(raw_frontmatter, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return 1
    if not isinstance(document, MappingNode):
        return 1
    for key_node, _ in document.value:
        if isinstance(key_node, ScalarNode) and key_node.value == wanted:
            return key_node.start_mark.line + 2
    return 1


def bibliography_links(path: DocumentInput) -> tuple[MarkdownLink, ...]:
    """Return valid frontmatter bibliography paths with source locations."""
    lines = _document(path).lines
    if not lines or lines[0] != "---":
        return ()
    closing = next(
        (index for index, line in enumerate(lines[1:], start=1) if line == "---"),
        None,
    )
    if closing is None:
        return ()
    raw_frontmatter = "\n".join(lines[1:closing])
    try:
        parsed = yaml.load(raw_frontmatter, Loader=_UniqueKeyLoader)
    except yaml.YAMLError:
        return ()
    if not isinstance(parsed, dict):
        return ()
    raw_value = parsed.get("bibliography")
    if isinstance(raw_value, str) and raw_value.strip():
        paths = (raw_value,)
    elif (
        isinstance(raw_value, list)
        and raw_value
        and all(isinstance(item, str) and item.strip() for item in raw_value)
    ):
        paths = tuple(raw_value)
    else:
        return ()
    line = _frontmatter_key_line(raw_frontmatter, "bibliography")
    return tuple(
        MarkdownLink(
            label="bibliography",
            target=unquote(target),
            line=line,
            column=1,
            kind="bibliography",
        )
        for target in paths
    )


def _heading_text(token: Token) -> str:
    if not token.children:
        return token.content.strip()
    return "".join(child.content for child in token.children).strip()


def _inline_markdown_links(
    token: Token,
    *,
    line_offset: int,
    source_lines: tuple[str, ...],
) -> tuple[MarkdownLink, ...]:
    if token.children is None or token.map is None:
        return ()
    source_start = line_offset + token.map[0]
    source_end = line_offset + token.map[1]
    raw = "\n".join(source_lines[source_start:source_end])
    cursor = 0
    links: list[MarkdownLink] = []

    for index, child in enumerate(token.children):
        kind: str
        target: str
        label: str
        marker: str
        if child.type == "link_open":
            kind = "link"
            target = unquote(child.attrGet("href") or "")
            label_parts: list[str] = []
            for nested in token.children[index + 1 :]:
                if nested.type == "link_close":
                    break
                label_parts.append(nested.content)
            label = "".join(label_parts)
            marker = "["
        elif child.type == "image":
            kind = "image"
            target = unquote(child.attrGet("src") or "")
            label = child.content
            marker = "!["
        else:
            continue

        marker_at = raw.find(marker, cursor)
        if marker_at < 0:
            marker_at = cursor
        bracket_at = marker_at + (1 if kind == "image" else 0)
        prefix = raw[:bracket_at]
        line = source_start + prefix.count("\n") + 1
        column = bracket_at - prefix.rfind("\n")
        links.append(
            MarkdownLink(
                label=label,
                target=target,
                line=line,
                column=column,
                kind=kind,
            )
        )
        cursor = max(marker_at + len(marker), cursor)
    return tuple(links)


def markdown_links(path: DocumentInput) -> tuple[MarkdownLink, ...]:
    """Return Markdown links/images and raw-HTML anchors outside code."""
    document = _document(path)
    line_offset = document.line_offset
    source_lines = document.lines
    links: list[MarkdownLink] = []
    for token in document.tokens:
        if token.type == "inline":
            links.extend(
                _inline_markdown_links(
                    token,
                    line_offset=line_offset,
                    source_lines=source_lines,
                )
            )
    return (*links, *raw_html_links(document))


class _ActiveHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[tuple[str, int, int]] = []
        self.images: list[tuple[str, int, int]] = []
        self.links: list[tuple[str, int, int]] = []
        self.resources: list[tuple[str, int, int]] = []
        self.saw_tag = False

    def _inspect_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.saw_tag = True
        line, column = self.getpos()
        lowered = tag.casefold()
        attributes = {name.casefold(): value for name, value in attrs}
        forbidden_tag = lowered in FORBIDDEN_HTML_TAGS
        javascript_url = any(
            name.casefold() in HTML_URL_ATTRIBUTES
            and _is_javascript_url(value)
            for name, value in attrs
        )
        if javascript_url:
            self.events.append(("javascript-url", line, column))
        if (
            lowered == "img"
            and attributes.get("src")
            and not _is_javascript_url(attributes["src"])
            and not forbidden_tag
        ):
            self.images.append((attributes["src"] or "", line, column))
        if (
            lowered == "a"
            and attributes.get("href")
            and not _is_javascript_url(attributes["href"])
            and not forbidden_tag
        ):
            self.links.append((attributes["href"] or "", line, column))
        if forbidden_tag:
            self.events.append((lowered, line, column))
        if not forbidden_tag:
            for raw_name, value in attrs:
                name = raw_name.casefold()
                if (
                    name in HTML_URL_ATTRIBUTES
                    and value
                    and not _is_javascript_url(value)
                    and not (
                        (lowered == "img" and name == "src")
                        or (lowered == "a" and name == "href")
                    )
                ):
                    self.resources.append((value, line, column))
        if attributes.get("srcset"):
            self.events.append(("srcset", line, column))
        style = attributes.get("style")
        if style and css_loads_resource(style):
            self.events.append(("style-url", line, column))
        if (
            lowered == "meta"
            and (attributes.get("http-equiv") or "").strip().casefold()
            == "refresh"
        ):
            self.events.append(("meta-refresh", line, column))
        for name, _ in attrs:
            if name.casefold().startswith("on"):
                self.events.append(("inline-handler", line, column))

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self._inspect_tag(tag, attrs)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self._inspect_tag(tag, attrs)

    def handle_endtag(self, _tag: str) -> None:
        self.saw_tag = True


def contains_html_markup(value: str) -> bool:
    """Return whether decoded metadata contains an HTML element."""
    parser = _ActiveHTMLParser()
    parser.feed(value)
    parser.close()
    return parser.saw_tag


def _is_javascript_url(value: str | None) -> bool:
    if value is None:
        return False
    without_ascii_controls = re.sub(r"[\x00-\x20]+", "", value)
    return without_ascii_controls.casefold().startswith("javascript:")


def css_loads_resource(value: str) -> bool:
    """Conservatively reject CSS constructs that can fetch or execute."""
    without_comments = re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL)
    if "\\" in without_comments:
        return True
    lowered = re.sub(r"[\x00-\x20]+", "", without_comments).casefold()
    return any(
        marker in lowered
        for marker in (
            "//",
            "@import",
            "behavior:",
            "cross-fade(",
            "data:",
            "expression(",
            "http:",
            "https:",
            "image(",
            "image-set(",
            "src(",
            "url(",
        )
    )


def _fragment_location(
    *,
    first_line: int,
    first_column: int,
    relative_line: int,
    relative_column: int,
) -> tuple[int, int]:
    return (
        first_line + relative_line - 1,
        (
            first_column + relative_column
            if relative_line == 1
            else relative_column + 1
        ),
    )


def _unsafe_html_fragment(
    fragment: str,
    *,
    first_line: int,
    first_column: int,
) -> tuple[UnsafeHtml, ...]:
    parser = _ActiveHTMLParser()
    parser.feed(fragment)
    unsafe: list[UnsafeHtml] = []
    for kind, relative_line, relative_column in parser.events:
        line, column = _fragment_location(
            first_line=first_line,
            first_column=first_column,
            relative_line=relative_line,
            relative_column=relative_column,
        )
        unsafe.append(
            UnsafeHtml(
                kind=kind,
                line=line,
                column=column,
            )
        )
    return tuple(unsafe)


def unsafe_html(path: DocumentInput) -> tuple[UnsafeHtml, ...]:
    """Return active publish-time constructs outside code tokens."""
    document = _document(path)
    line_offset = document.line_offset
    source_lines = document.lines
    unsafe: list[UnsafeHtml] = []
    for token in document.tokens:
        if token.type == "html_block" and token.map is not None:
            unsafe.extend(
                _unsafe_html_fragment(
                    token.content,
                    first_line=line_offset + token.map[0] + 1,
                    first_column=1,
                )
            )
        elif token.type == "inline" and token.children and token.map is not None:
            source_start = line_offset + token.map[0]
            source_end = line_offset + token.map[1]
            raw = "\n".join(source_lines[source_start:source_end])
            cursor = 0
            for child in token.children:
                if child.type != "html_inline":
                    continue
                found = raw.find(child.content, cursor)
                if found < 0:
                    found = cursor
                prefix = raw[:found]
                first_line = source_start + prefix.count("\n") + 1
                first_column = found - prefix.rfind("\n")
                unsafe.extend(
                    _unsafe_html_fragment(
                        child.content,
                        first_line=first_line,
                        first_column=first_column,
                    )
                )
                cursor = max(found + len(child.content), cursor)
    for match in QUARTO_SHORTCODE_PATTERN.finditer(document.body):
        prefix = document.body[: match.start()]
        unsafe.append(
            UnsafeHtml(
                kind="quarto-shortcode",
                line=line_offset + prefix.count("\n") + 1,
                column=match.start() - prefix.rfind("\n"),
            )
        )
    return tuple(unsafe)


def _raw_html_link_fragment(
    fragment: str,
    *,
    first_line: int,
    first_column: int,
) -> tuple[MarkdownLink, ...]:
    parser = _ActiveHTMLParser()
    parser.feed(fragment)
    return tuple(
        MarkdownLink(
            label="",
            target=unquote(target),
            line=first_line + relative_line - 1,
            column=(
                first_column + relative_column
                if relative_line == 1
                else relative_column + 1
            ),
            kind="link",
        )
        for target, relative_line, relative_column in parser.links
    )


def raw_html_links(path: DocumentInput) -> tuple[MarkdownLink, ...]:
    """Return raw-HTML anchors as ordinary link dependencies."""
    document = _document(path)
    line_offset = document.line_offset
    source_lines = document.lines
    links: list[MarkdownLink] = []
    for token in document.tokens:
        if token.type == "html_block" and token.map is not None:
            links.extend(
                _raw_html_link_fragment(
                    token.content,
                    first_line=line_offset + token.map[0] + 1,
                    first_column=1,
                )
            )
        elif token.type == "inline" and token.children and token.map is not None:
            source_start = line_offset + token.map[0]
            source_end = line_offset + token.map[1]
            raw = "\n".join(source_lines[source_start:source_end])
            cursor = 0
            for child in token.children:
                if child.type != "html_inline":
                    continue
                found = raw.find(child.content, cursor)
                if found < 0:
                    found = cursor
                prefix = raw[:found]
                first_line = source_start + prefix.count("\n") + 1
                first_column = found - prefix.rfind("\n")
                links.extend(
                    _raw_html_link_fragment(
                        child.content,
                        first_line=first_line,
                        first_column=first_column,
                    )
                )
                cursor = max(found + len(child.content), cursor)
    return tuple(links)


def _raw_html_resource_fragment(
    fragment: str,
    *,
    first_line: int,
    first_column: int,
) -> tuple[MarkdownLink, ...]:
    parser = _ActiveHTMLParser()
    parser.feed(fragment)
    resources: list[MarkdownLink] = []
    for target, relative_line, relative_column in parser.resources:
        line, column = _fragment_location(
            first_line=first_line,
            first_column=first_column,
            relative_line=relative_line,
            relative_column=relative_column,
        )
        resources.append(
            MarkdownLink(
                label="",
                target=unquote(target),
                line=line,
                column=column,
                kind="resource",
            )
        )
    return tuple(resources)


def raw_html_resources(path: DocumentInput) -> tuple[MarkdownLink, ...]:
    """Return non-anchor raw-HTML URL attributes as asset dependencies."""
    document = _document(path)
    line_offset = document.line_offset
    source_lines = document.lines
    resources: list[MarkdownLink] = []
    for token in document.tokens:
        if token.type == "html_block" and token.map is not None:
            resources.extend(
                _raw_html_resource_fragment(
                    token.content,
                    first_line=line_offset + token.map[0] + 1,
                    first_column=1,
                )
            )
        elif token.type == "inline" and token.children and token.map is not None:
            source_start = line_offset + token.map[0]
            source_end = line_offset + token.map[1]
            raw = "\n".join(source_lines[source_start:source_end])
            cursor = 0
            for child in token.children:
                if child.type != "html_inline":
                    continue
                found = raw.find(child.content, cursor)
                if found < 0:
                    found = cursor
                prefix = raw[:found]
                first_line = source_start + prefix.count("\n") + 1
                first_column = found - prefix.rfind("\n")
                resources.extend(
                    _raw_html_resource_fragment(
                        child.content,
                        first_line=first_line,
                        first_column=first_column,
                    )
                )
                cursor = max(found + len(child.content), cursor)
    return tuple(resources)


def _raw_html_image_fragment(
    fragment: str,
    *,
    first_line: int,
    first_column: int,
) -> tuple[MarkdownLink, ...]:
    parser = _ActiveHTMLParser()
    parser.feed(fragment)
    return tuple(
        MarkdownLink(
            label="",
            target=unquote(target),
            line=first_line + relative_line - 1,
            column=(
                first_column + relative_column
                if relative_line == 1
                else relative_column + 1
            ),
            kind="image",
        )
        for target, relative_line, relative_column in parser.images
    )


def raw_html_images(path: DocumentInput) -> tuple[MarkdownLink, ...]:
    """Return passive raw-HTML images as local asset dependencies."""
    document = _document(path)
    line_offset = document.line_offset
    source_lines = document.lines
    images: list[MarkdownLink] = []
    for token in document.tokens:
        if token.type == "html_block" and token.map is not None:
            images.extend(
                _raw_html_image_fragment(
                    token.content,
                    first_line=line_offset + token.map[0] + 1,
                    first_column=1,
                )
            )
        elif token.type == "inline" and token.children and token.map is not None:
            source_start = line_offset + token.map[0]
            source_end = line_offset + token.map[1]
            raw = "\n".join(source_lines[source_start:source_end])
            cursor = 0
            for child in token.children:
                if child.type != "html_inline":
                    continue
                found = raw.find(child.content, cursor)
                if found < 0:
                    found = cursor
                prefix = raw[:found]
                first_line = source_start + prefix.count("\n") + 1
                first_column = found - prefix.rfind("\n")
                images.extend(
                    _raw_html_image_fragment(
                        child.content,
                        first_line=first_line,
                        first_column=first_column,
                    )
                )
                cursor = max(found + len(child.content), cursor)
    return tuple(images)


def forbidden_frontmatter_keys(
    path: DocumentInput,
) -> tuple[tuple[str, int], ...]:
    """Return forbidden top-level YAML keys and their one-based lines."""
    lines = _document(path).lines
    if not lines or lines[0] != "---":
        return ()
    closing = next(
        (index for index, line in enumerate(lines[1:], start=1) if line == "---"),
        None,
    )
    if closing is None:
        return ()
    try:
        document = yaml.compose("\n".join(lines[1:closing]), Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return ()
    if not isinstance(document, MappingNode):
        return ()
    forbidden: list[tuple[str, int]] = []
    for key_node, _ in document.value:
        if not isinstance(key_node, ScalarNode):
            continue
        key = key_node.value
        if key not in SAFE_FRONTMATTER_KEYS:
            forbidden.append((key, key_node.start_mark.line + 2))
    return tuple(forbidden)


def _section_list_links(
    path: DocumentInput,
    wanted: str,
) -> tuple[MarkdownLink, ...]:
    """Return direct list links below one exact level-two section heading."""
    document = _document(path)
    line_offset = document.line_offset
    source_lines = document.lines
    tokens = document.tokens
    links: list[MarkdownLink] = []
    in_section = False
    in_top_level_list = False

    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            inline = tokens[index + 1]
            in_section = (
                token.tag == "h2"
                and _heading_text(inline).casefold() == wanted.casefold()
            )
            continue
        if token.type in {"bullet_list_open", "ordered_list_open"} and token.level == 0:
            in_top_level_list = in_section
            continue
        if token.type in {"bullet_list_close", "ordered_list_close"} and token.level == 0:
            in_top_level_list = False
            continue
        if not (
            in_section
            and in_top_level_list
            and token.type == "list_item_open"
            and token.level == 1
        ):
            continue
        inline = None
        for candidate in tokens[index + 1 :]:
            if candidate.type == "list_item_close" and candidate.level == token.level:
                break
            if candidate.type == "inline" and candidate.level == token.level + 2:
                inline = candidate
                break
        if inline is None or inline.map is None:
            continue
        links.extend(
            link
            for link in _inline_markdown_links(
                inline,
                line_offset=line_offset,
                source_lines=source_lines,
            )
            if link.kind == "link"
        )

    return tuple(links)


def reading_map_links(path: DocumentInput) -> tuple[MarkdownLink, ...]:
    """Return direct list links under a level-two ``Reading map`` heading."""
    return _section_list_links(path, "Reading map")


def related_topics_links(path: DocumentInput) -> tuple[MarkdownLink, ...]:
    """Return direct list links under a level-two ``Related topics`` heading."""
    return _section_list_links(path, "Related topics")


def level_two_heading_lines(
    path: DocumentInput,
    wanted: str,
) -> tuple[int, ...]:
    """Return one-based lines for an exact level-two heading."""
    document = _document(path)
    line_offset = document.line_offset
    tokens = document.tokens
    lines: list[int] = []
    for index, token in enumerate(tokens):
        if (
            token.type == "heading_open"
            and token.tag == "h2"
            and token.map is not None
            and _heading_text(tokens[index + 1]).casefold() == wanted.casefold()
        ):
            lines.append(line_offset + token.map[0] + 1)
    return tuple(lines)
