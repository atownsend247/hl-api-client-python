from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from .._html import has_class, load
from ..entities import ClientAccountEntity
from ..errors import ParseError
from ..requestor import Requestor


class LinkedAccountOperations:
    def __init__(self, requestor: Requestor) -> None:
        self._requestor = requestor

    def list_accounts(self) -> list[ClientAccountEntity]:
        """Gets a list of all linked client accounts."""
        response = self._requestor.get("my-accounts")
        return self.parse_accounts(load(response.content))

    @staticmethod
    def parse_accounts(doc: BeautifulSoup) -> list[ClientAccountEntity]:
        """Parse the document to extract the list of client accounts."""
        lists = doc.find_all("ul", class_="linked-account-tabs")
        if not lists:
            return []

        accounts: list[ClientAccountEntity] = []
        for item in lists[0].find_all("li"):
            links = item.find_all("a")
            if len(links) != 1:
                raise ParseError("Expected exactly one link per linked account tab.")
            link = links[0]

            query = parse_qs(urlparse(str(link.get("href", ""))).query)
            client_number = int(query["client_no"][0])

            accounts.append(
                ClientAccountEntity(
                    client_number=client_number,
                    name=str(link.get("title", "")).replace(f"({client_number})", "").strip(),
                    currently_selected=has_class(item, "current-tab"),
                )
            )

        return accounts

    def switch(self, client_number: int) -> bool:
        """Switch to another linked account. Returns whether the switch took effect."""
        response = self._requestor.get(f"my-accounts/linked_accounts_control?method=switch&client_no={client_number}")
        accounts = self.parse_accounts(load(response.content))
        return any(a.currently_selected and a.client_number == client_number for a in accounts)
