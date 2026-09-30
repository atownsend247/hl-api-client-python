from datetime import datetime
from decimal import Decimal

import pytest

from hl_client._parsing import parse_currency, parse_datetime, parse_decimal, try_parse_decimal


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("£1.00", "1.00"),
        (" £1,234.56 ", "1234.56"),
        ("-£5.00", "-5.00"),
        ("(£5.00)", "-5.00"),
        ("£\xa07", "7"),
        ("0", "0"),
    ],
)
def test_parse_currency(text: str, expected: str) -> None:
    assert parse_currency(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["", "abc", "£", "1.2.3", "--1"])
def test_parse_decimal_rejects_garbage(text: str) -> None:
    with pytest.raises(ValueError, match="valid number"):
        parse_decimal(text)


def test_parse_decimal_does_not_accept_currency_symbol() -> None:
    with pytest.raises(ValueError, match="valid number"):
        parse_decimal("£1.00")


def test_try_parse_decimal() -> None:
    assert try_parse_decimal("") is None
    assert try_parse_decimal("1,000.5") == Decimal("1000.5")
    assert try_parse_decimal("-2") == Decimal(-2)


def test_parse_datetime_is_day_first() -> None:
    assert parse_datetime(" 03/04/2020\n") == datetime(2020, 4, 3)
    assert parse_datetime("03/04/2020 13:45") == datetime(2020, 4, 3, 13, 45)


def test_parse_datetime_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="valid date"):
        parse_datetime("yesterday")
