import re
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import unquote_plus

import httpx
from bs4 import BeautifulSoup, Tag

from .._html import cells, child, collapse_whitespace, load, rows_of
from .._parsing import parse_currency, parse_datetime, parse_decimal, try_parse_decimal
from ..constants import BASE_URL
from ..entities import (
    AccountEntity,
    CashSummaryEntity,
    GainsLossEntity,
    StockEntity,
    TransactionEntity,
)
from ..errors import AccountNotFoundError, HLError, ParseError
from ..requestor import Requestor

_ACCOUNT_OPENING_DATE = re.compile(r"var\s*aod\s*=\s*'(\d{2}/\d{2}/\d{4})'")


def _add_years(d: date, years: int) -> date:
    """Like C#'s ``DateTime.AddYears``: 29 February moves to 28 February in a non-leap year."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def _url_date(d: date) -> str:
    return f"{d.day:02}%2F{d.month:02}%2F{d.year}"


class AccountOperations:
    def __init__(self, requestor: Requestor) -> None:
        self._requestor = requestor

    # -- Accounts ---------------------------------------------------------------------------------------

    def list_accounts(self) -> list[AccountEntity]:
        """Gets a list of all accounts."""
        response = self._requestor.get("my-accounts/portfolio_overview")
        return self.parse_accounts(load(response.content))

    @staticmethod
    def parse_accounts(doc: BeautifulSoup) -> list[AccountEntity]:
        """Parse the document to extract the list of accounts."""
        table = doc.find("table", id="portfolio")
        if table is None:
            raise ParseError("Unable to find the portfolio table.")

        accounts: list[AccountEntity] = []
        for row in rows_of(table):
            columns = cells(row)
            name_link = child(columns[0], "a")
            accounts.append(
                AccountEntity(
                    id=int(str(name_link["href"])[len(BASE_URL) :].split("/")[3]),
                    name=name_link.get_text().strip("\n\r").strip(),
                    stock_value=parse_currency(child(columns[1], "a").get_text()),
                    cash_value=parse_currency(columns[2].get_text()),
                    total_value=parse_currency(child(columns[3], "strong").get_text()),
                    available=parse_currency(child(columns[4], "a").get_text()),
                )
            )

        return accounts

    # -- Stocks -----------------------------------------------------------------------------------------

    def list_stocks(self, account_id: int) -> list[StockEntity]:
        """List the stocks held in an account."""
        response = self._requestor.get(f"my-accounts/account_summary/account/{account_id}")
        self._check(response, account_id, "stock")
        return self.parse_stocks(load(collapse_whitespace(response.text)))

    @staticmethod
    def parse_stocks(doc: BeautifulSoup) -> list[StockEntity]:
        """Parse the document to extract the stock information."""
        rows: list[Tag] = []
        for table in doc.find_all("table", class_="holdings-table"):
            body = table.find("tbody", recursive=False)
            if isinstance(body, Tag):
                rows.extend(body.find_all("tr"))

        stocks: list[StockEntity] = []
        for row in rows:
            columns = cells(row)
            name_and_type = columns[1].get_text().strip("\r\n").strip().split("\n")
            stocks.append(
                StockEntity(
                    id=str(child(columns[0], "a")["href"])[len(BASE_URL) :].split("/")[3],
                    name=name_and_type[0].strip(),
                    unit_type=name_and_type[-1].strip(),
                    units_held=parse_decimal(columns[2].get_text()),
                    price=parse_decimal(child(columns[3], "span").get_text()),
                    value=parse_decimal(child(child(columns[4], "span"), "span").get_text()),
                    cost=parse_decimal(child(columns[5], "span").get_text()),
                    gains_loss=GainsLossEntity(
                        pounds=parse_decimal(child(columns[16], "span").get_text()),
                        percentage=parse_decimal(child(columns[17], "span").get_text()),
                    ),
                )
            )

        return stocks

    # -- Cash -------------------------------------------------------------------------------------------

    def get_cash_summary(self, account_id: int) -> CashSummaryEntity:
        """Gets the cash summary for an account."""
        response = self._requestor.get(f"my-accounts/cash/account/{account_id}")
        self._check(response, account_id, "cash summary")
        return self.parse_cash_summary(load(collapse_whitespace(response.text)))

    @staticmethod
    def parse_cash_summary(doc: BeautifulSoup) -> CashSummaryEntity:
        """Parse the document to extract the cash summary."""
        table = doc.find("table", class_="cash-generic-table")
        if table is None:
            raise ParseError("Unable to find the cash summary table.")

        rows = rows_of(table)
        footer = rows_of(table, "tfoot")[0]

        def last(row: Tag) -> str:
            return cells(row)[-1].get_text()

        return CashSummaryEntity(
            cash_on_capital_account=parse_currency(last(rows[0])),
            income_loyalty_bonus=parse_currency(last(rows[1])),
            fixed_rate_offers=parse_currency(last(rows[2])),
            total_cash=parse_currency(last(footer)),
        )

    # -- Transactions -----------------------------------------------------------------------------------

    def list_transactions(
        self,
        account_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TransactionEntity]:
        """List the transactions of an account.

        Args:
            account_id: The account ID.
            start_date: Optional start date. Defaults to (and is clamped to) the account opening date.
            end_date: Optional end date. Defaults to (and is clamped to) today.
        """
        response = self._requestor.get(f"my-accounts/capital-transaction-history/account/{account_id}")
        self._check(response, account_id, "transactions")

        match = _ACCOUNT_OPENING_DATE.search(response.text)
        if match is None:
            raise HLError(f"Unable to get account opening date for account: {account_id}")
        opening_date = datetime.strptime(match.group(1), "%d/%m/%Y").date()

        if start_date is None or start_date < opening_date:
            start_date = opening_date
        if end_date is None or end_date > date.today():
            end_date = date.today()

        # HL only returns a limited period at a time, so request one year at a time.
        all_transactions: list[TransactionEntity] = []
        current = start_date
        while current < end_date:
            chunk_end = min(_add_years(current, 1), end_date)
            all_transactions.extend(self._list_transactions_for_period(account_id, current, chunk_end))
            # Dates are inclusive on both ends
            current = date.fromordinal(chunk_end.toordinal() + 1)

        return all_transactions

    def _list_transactions_for_period(self, account_id: int, start: date, end: date) -> list[TransactionEntity]:
        page = 1
        output: list[TransactionEntity] = []

        while True:
            response = self._requestor.get(
                f"my-accounts/capital-transaction-history/account/{account_id}"
                f"?period=custom&page={page}&startDate={_url_date(start)}&endDate={_url_date(end)}&filter="
            )
            self._check(response, account_id, "transactions")

            doc = load(collapse_whitespace(response.text))
            output.extend(self.parse_transactions(doc))
            if not doc.find("a", class_="next-button"):
                return output

            page += 1

    @staticmethod
    def parse_transactions(doc: BeautifulSoup) -> list[TransactionEntity]:
        """Parse the document to extract the transactions."""
        table = doc.find("table", class_="transaction-history-table")
        if table is None:
            return []

        transactions: list[TransactionEntity] = []
        for row in rows_of(table):
            columns = cells(row)
            link = columns[2].find("a", recursive=False)
            value = try_parse_decimal(columns[6].get_text().strip("\r\n"))

            transactions.append(
                TransactionEntity(
                    trade_date=parse_datetime(columns[0].get_text().strip("\r\n")),
                    settle_date=parse_datetime(columns[1].get_text().strip("\r\n")),
                    reference=(link if isinstance(link, Tag) else columns[2]).get_text().strip("\r\n"),
                    reference_link=str(link["href"]) if isinstance(link, Tag) else None,
                    description=unquote_plus(columns[3].get_text().strip("\r\n").strip()),
                    unit_cost=try_parse_decimal(columns[4].get_text().strip("\r\n")),
                    quantity=try_parse_decimal(columns[5].get_text().strip("\r\n")),
                    value=Decimal(0) if value is None else value,
                )
            )

        return transactions

    # -- Shared -----------------------------------------------------------------------------------------

    @staticmethod
    def _check(response: httpx.Response, account_id: int, what: str) -> None:
        if response.is_success:
            return
        if response.status_code == 404:
            raise AccountNotFoundError(f"Unable to find account: {account_id}")
        raise HLError(f"Unable to get {what} for account: {account_id}")
