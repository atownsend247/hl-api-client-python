"""Tests that run the operations end to end against a mocked HL server."""

from datetime import date, datetime

import httpx
import pytest
from html_table_builder import HtmlTableBuilder, page

from hl_client import AccountNotFoundError, AuthenticationError, Client, HLError, Requestor
from hl_client.constants import BASE_URL

STEP_ONE = '<form><input type="hidden" name="hl_vt" value="tok1"></form>'
STEP_TWO = """
<form>
  <input type="hidden" name="hl_vt" value="tok2">
  <div class="secure-number-container">
    <div class="secure-number-grey-box"></div>
    <div class="secure-number-container__label"></div>
    <div class="secure-number-grey-box"></div>
    <div class="secure-number-container__label"></div>
    <div class="secure-number-container__label"></div>
  </div>
</form>
"""


def make_client(handler: httpx.MockTransport) -> Client:
    return Client(Requestor(transport=handler))


def login_handler(seen: dict[str, dict[str, str]], *, fail_step_two: bool = False) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/my-accounts/login-step-one":
            return httpx.Response(200, html=page(STEP_ONE))
        if request.method == "GET" and path == "/my-accounts/login-step-two":
            return httpx.Response(200, html=page(STEP_TWO))
        if request.method == "POST" and path == "/my-accounts/login-step-one":
            seen["one"] = dict(httpx.QueryParams(request.content.decode()))
            return httpx.Response(302, headers={"location": "/my-accounts/login-step-two"})
        if request.method == "POST" and path == "/my-accounts/login-step-two":
            seen["two"] = dict(httpx.QueryParams(request.content.decode()))
            target = "/my-accounts/login-step-two" if fail_step_two else "/my-accounts"
            return httpx.Response(302, headers={"location": target})
        return httpx.Response(200, html=page(""))

    return httpx.MockTransport(handle)


def test_authenticate_submits_both_stages() -> None:
    seen: dict[str, dict[str, str]] = {}
    client = make_client(login_handler(seen))

    client.authenticate("user", "pass", date(1990, 2, 3), "123456")

    assert client.is_authenticated
    assert seen["one"] == {"username": "user", "date-of-birth": "030290", "hl_vt": "tok1"}
    # Digits at (0-based) positions 1, 3 and 4 of the security number were requested.
    assert seen["two"] == {
        "online-password-verification": "pass",
        "secure-number[1]": "2",
        "secure-number[2]": "4",
        "secure-number[3]": "5",
        "submit": "Log in",
        "hl_vt": "tok2",
    }


def test_authenticate_fails_when_not_redirected() -> None:
    client = make_client(login_handler({}, fail_step_two=True))

    with pytest.raises(AuthenticationError):
        client.authenticate("user", "pass", date(1990, 2, 3), "123456")

    assert not client.is_authenticated


def test_short_security_number_is_rejected() -> None:
    client = make_client(login_handler({}))

    with pytest.raises(AuthenticationError, match="digits"):
        client.authenticate("user", "pass", date(1990, 2, 3), "123")


def test_linked_accounts_list_and_switch() -> None:
    def tab(number: int, title: str, current: bool = False) -> str:
        cls = ' class="current-tab"' if current else ""
        return f'<li{cls}><a href="{BASE_URL}my-accounts?client_no={number}" title="{title}">x</a></li>'

    def handle(request: httpx.Request) -> httpx.Response:
        current_is_2 = "client_no=2" in str(request.url)
        tabs = tab(1, "Alice (1)", not current_is_2) + tab(2, "Bob (2)", current_is_2)
        return httpx.Response(200, html=page(f'<ul class="linked-account-tabs">{tabs}</ul>'))

    client = make_client(httpx.MockTransport(handle))

    accounts = client.linked_account_operations.list_accounts()
    assert [(a.client_number, a.name, a.currently_selected) for a in accounts] == [
        (1, "Alice", True),
        (2, "Bob", False),
    ]
    assert client.linked_account_operations.switch(2) is True


def test_list_stocks_404_is_account_not_found() -> None:
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(404)))

    with pytest.raises(AccountNotFoundError):
        client.account_operations.list_stocks(5)


def test_list_stocks_server_error() -> None:
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(500)))

    with pytest.raises(HLError):
        client.account_operations.list_stocks(5)


def test_list_transactions_pages_and_chunks_by_year() -> None:
    requested: list[str] = []
    row = HtmlTableBuilder(class_="transaction-history-table").add_row(
        "15/10/2020", "20/10/2020", "ref", "desc", "", "", "1"
    )

    def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "period=custom" not in url:
            return httpx.Response(200, text="<script>var aod = '01/01/2020';</script>")
        requested.append(url.split("?", 1)[1])
        more = '<a class="next-button">next</a>' if "page=1" in url and "startDate=01%2F01%2F2020" in url else ""
        return httpx.Response(200, html=page(str(row) + more))

    client = make_client(httpx.MockTransport(handle))

    transactions = client.account_operations.list_transactions(
        7, start_date=date(2019, 6, 1), end_date=date(2021, 3, 1)
    )

    # Start is clamped to the opening date (1 Jan 2020); year-long chunks are 2020-01-01..2021-01-01 and
    # 2021-01-02..2021-03-01, and the first chunk has a second page.
    assert len(requested) == 3
    assert "page=1&startDate=01%2F01%2F2020&endDate=01%2F01%2F2021" in requested[0]
    assert "page=2&startDate=01%2F01%2F2020&endDate=01%2F01%2F2021" in requested[1]
    assert "page=1&startDate=02%2F01%2F2021&endDate=01%2F03%2F2021" in requested[2]
    assert len(transactions) == 3


def test_list_inbox_and_get_message() -> None:
    inbox = HtmlTableBuilder(class_="inbox-table").add_row(
        '<a href="/secure_messaging/view/message/42"></a>', '<a href="#"> Hello </a>', " 03/04/2020 "
    )
    message = (
        '<div id="smcWindow"><h2><span>03 Apr 2020</span><span>The title</span></h2><p> first </p><p> second </p></div>'
    )

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html=page(message if "view/message" in str(request.url) else inbox))

    client = make_client(httpx.MockTransport(handle))

    (entry,) = client.message_operations.list_inbox(2020, 4)
    assert (entry.id, entry.title, entry.received_at) == (42, "Hello", datetime(2020, 4, 3))

    full = client.message_operations.get(42)
    assert (full.title, full.received_at) == ("The title", datetime(2020, 4, 3))
    assert full.message == "first\n,second\n"  # the ',' separator is inherited from the C# version


def test_list_inbox_month_needs_year() -> None:
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(200)))

    with pytest.raises(ValueError, match="month"):
        client.message_operations.list_inbox(month=3)
