"""Small helpers for walking parsed HTML, mirroring the HtmlAgilityPack calls used by the C# version."""

import re

from bs4 import BeautifulSoup, Tag

from .errors import ParseError

_REPEATED_WHITESPACE = re.compile(r"( |\t|\r?\n)\1+")


def load(html: str | bytes) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def collapse_whitespace(html: str) -> str:
    """Collapse runs of the same whitespace into one, as the C# version does before parsing."""
    return _REPEATED_WHITESPACE.sub(r"\1", html)


def child(node: Tag, name: str) -> Tag:
    """The first *direct* child element with the given name (XPath ``name``)."""
    found = node.find(name, recursive=False)
    if not isinstance(found, Tag):
        raise ParseError(f"Expected a <{name}> element inside <{node.name}>.")
    return found


def rows_of(table: Tag, section: str = "tbody") -> list[Tag]:
    """Every ``<tr>`` inside the table's ``<tbody>`` (or ``<tfoot>``)."""
    return list(child(table, section).find_all("tr"))


def cells(row: Tag) -> list[Tag]:
    return list(row.find_all("td"))


def has_class(node: Tag, name: str) -> bool:
    return name in (node.get("class") or [])
