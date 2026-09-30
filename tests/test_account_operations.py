from datetime import datetime
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from html_table_builder import HtmlTableBuilder, page

from hl_client.constants import BASE_URL
from hl_client.errors import ParseError
from hl_client.operations.account import AccountOperations


def doc(table: HtmlTableBuilder) -> BeautifulSoup:
    return BeautifulSoup(page(table), "lxml")


def account_link(account_id: int, name: str) -> str:
    return f'<a href="{BASE_URL}my-accounts/account-summary/account/{account_id}">{name}</a>'


def span(text: str) -> str:
    return f"<span>{text}</span>"


def test_parse_one_account() -> None:
    table = HtmlTableBuilder(id="portfolio").add_row(
        account_link(999, "0"),
        account_link(999, "£1.00"),
        "£2.00",
        "<strong>£3.00</strong>",
        account_link(999, "£4.00"),
    )

    accounts = AccountOperations.parse_accounts(doc(table))

    assert len(accounts) == 1
    account = accounts[0]
    assert (account.id, account.name) == (999, "0")
    assert (account.stock_value, account.cash_value) == (Decimal("1.00"), Decimal("2.00"))
    assert (account.total_value, account.available) == (Decimal("3.00"), Decimal("4.00"))


def test_missing_portfolio_table_is_a_parse_error() -> None:
    with pytest.raises(ParseError):
        AccountOperations.parse_accounts(BeautifulSoup(page(""), "lxml"))


def test_parse_one_stock() -> None:
    table = HtmlTableBuilder(class_="holdings-table").add_row(
        account_link(999, "0"),
        account_link(999, "stock\ntype"),
        "2",
        span("3.00"),
        span(span("4.00")),
        span("5.00"),
        *([""] * 10),
        span("16.00"),
        span("17.00"),
    )

    stocks = AccountOperations.parse_stocks(doc(table))

    assert len(stocks) == 1
    stock = stocks[0]
    assert (stock.id, stock.name, stock.unit_type) == ("999", "stock", "type")
    assert (stock.units_held, stock.price, stock.value, stock.cost) == tuple(
        Decimal(x) for x in ("2", "3.00", "4.00", "5.00")
    )
    assert (stock.gains_loss.pounds, stock.gains_loss.percentage) == (Decimal("16.00"), Decimal("17.00"))


def test_parse_stock_with_thousands_separator() -> None:
    table = HtmlTableBuilder(class_="holdings-table").add_row(
        account_link(1, "0"),
        account_link(1, "a\nb"),
        "1,234.5",
        span("3"),
        span(span("4")),
        span("5"),
        *([""] * 10),
        span("-6.5"),
        span("-7"),
    )

    stock = AccountOperations.parse_stocks(doc(table))[0]

    assert stock.units_held == Decimal("1234.5")
    assert stock.gains_loss.pounds == Decimal("-6.5")


def test_parse_cash_summary() -> None:
    table = (
        HtmlTableBuilder(class_="cash-generic-table")
        .add_row("£1.00")
        .add_row("£2.00")
        .add_row("£3.00")
        .add_footer("£4.00")
    )

    summary = AccountOperations.parse_cash_summary(doc(table))

    assert (
        summary.cash_on_capital_account,
        summary.income_loyalty_bonus,
        summary.fixed_rate_offers,
        summary.total_cash,
    ) == tuple(Decimal(x) for x in ("1.00", "2.00", "3.00", "4.00"))


LINK = '<a href="https://example.com/random-url/">a_name</a>'


def test_parse_empty_transaction() -> None:
    table = HtmlTableBuilder(class_="transaction-history-table").add_row(
        "15/10/2020", "20/10/2010", LINK, "This is a description", "", "", ""
    )

    (transaction,) = AccountOperations.parse_transactions(doc(table))

    assert transaction.trade_date == datetime(2020, 10, 15)
    assert transaction.settle_date == datetime(2010, 10, 20)
    assert transaction.reference == "a_name"
    assert transaction.reference_link == "https://example.com/random-url/"
    assert transaction.description == "This is a description"
    assert transaction.unit_cost is None
    assert transaction.quantity is None
    assert transaction.value == Decimal(0)


def test_parse_one_transaction() -> None:
    table = HtmlTableBuilder(class_="transaction-history-table").add_row(
        "15/10/2020", "20/10/2010", LINK, "This is a description", "5.00", "6.00", "7.00"
    )

    (transaction,) = AccountOperations.parse_transactions(doc(table))

    assert transaction.unit_cost == Decimal("5.00")
    assert transaction.quantity == Decimal("6.00")
    assert transaction.value == Decimal("7.00")


def test_transaction_without_link_uses_cell_text() -> None:
    table = HtmlTableBuilder(class_="transaction-history-table").add_row(
        "15/10/2020", "20/10/2020", "plain-ref", "Desc%20with+encoding", "", "", "1"
    )

    (transaction,) = AccountOperations.parse_transactions(doc(table))

    assert transaction.reference == "plain-ref"
    assert transaction.reference_link is None
    assert transaction.description == "Desc with encoding"


def test_no_transaction_table_gives_no_transactions() -> None:
    assert AccountOperations.parse_transactions(BeautifulSoup(page(""), "lxml")) == []
