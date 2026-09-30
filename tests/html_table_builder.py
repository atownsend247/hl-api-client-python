"""Builds an HTML table for testing."""


class HtmlTableBuilder:
    def __init__(self, *, id: str = "", class_: str = "") -> None:
        self.id = id
        self.class_ = class_
        self._body: list[str] = []
        self._footer: list[str] = []

    @staticmethod
    def _row(cells: tuple[str, ...]) -> str:
        return "<tr> " + "".join(f"<td>{c}</td> " for c in cells) + "</tr>"

    def add_row(self, *cells: str) -> "HtmlTableBuilder":
        self._body.append(self._row(cells))
        return self

    def add_footer(self, *cells: str) -> "HtmlTableBuilder":
        self._footer.append(self._row(cells))
        return self

    def __str__(self) -> str:
        attrs = (f' id="{self.id}"' if self.id else "") + (f' class="{self.class_}"' if self.class_ else "")
        out = f"<table{attrs}> <tbody>\n" + "\n".join(self._body) + "\n</tbody>\n"
        if self._footer:
            out += "<tfoot>\n" + "\n".join(self._footer) + "\n</tfoot>\n"
        return out + "</table>\n"


def page(body: object) -> str:
    return f"<html> <head></head> <body>{body}</body> </html>"
