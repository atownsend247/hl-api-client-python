from datetime import datetime

from .._html import cells, child, collapse_whitespace, load, rows_of
from ..entities import MessageEntity
from ..errors import HLError, ParseError
from ..requestor import Requestor


class MessageOperations:
    def __init__(self, requestor: Requestor) -> None:
        self._requestor = requestor

    def list_inbox(self, year: int | None = None, month: int | None = None) -> list[MessageEntity]:
        """Lists the messages in your inbox, optionally for a given year (and month)."""
        if year is None and month is not None:
            raise ValueError("You can only select a month with a valid year.")

        response = self._requestor.get(
            f"secure_messaging/inbox?year={-1 if year is None else year}&month={-1 if month is None else month}"
        )
        if not response.is_success:
            raise HLError("Unable to get inbox.")

        doc = load(collapse_whitespace(response.text))
        table = doc.find("table", class_="inbox-table")
        if table is None:
            raise ParseError("Unable to find the inbox table.")

        messages: list[MessageEntity] = []
        for row in rows_of(table):
            columns = cells(row)
            messages.append(
                MessageEntity(
                    id=int(str(child(columns[0], "a")["href"]).split("/")[-1]),
                    title=child(columns[1], "a").get_text().strip(),
                    received_at=datetime.strptime(columns[2].get_text().strip(), "%d/%m/%Y"),
                )
            )

        return messages

    def get(self, message_id: int) -> MessageEntity:
        """Gets a specific message."""
        response = self._requestor.get(f"secure_messaging/view/message/{message_id}")
        if not response.is_success:
            raise HLError("Unable to get message.")

        doc = load(collapse_whitespace(response.text))
        container = doc.find("div", id="smcWindow")
        if container is None:
            raise ParseError("Unable to find the message window.")

        header = child(container, "h2")
        spans = header.find_all("span", recursive=False)
        paragraphs = container.find_all("p", recursive=False)

        return MessageEntity(
            id=message_id,
            title=spans[-1].decode_contents(),
            received_at=datetime.strptime(spans[0].get_text().strip(), "%d %b %Y"),
            message=",".join(f"{p.get_text().strip()}\n" for p in paragraphs),
        )
