"""Helpers for parsing the UK-formatted numbers and dates that HL's pages contain.

The C# version used ``CultureInfo("en-GB")`` for this. Python's ``locale`` module is process-global and
depends on what is installed, so the small subset of en-GB behaviour that HL actually emits is
implemented explicitly here instead.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

_BODY = re.compile(r"[\d,]*\.?\d*")
_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d %b %Y")


def _parse(text: str, *, allow_currency: bool) -> Decimal:
    s = text.strip()  # str.strip() also removes non-breaking spaces
    negative = False

    if allow_currency and s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()

    if s.startswith(("+", "-")):
        negative ^= s[0] == "-"
        s = s[1:].strip()
    elif s.endswith(("+", "-")):
        negative ^= s[-1] == "-"
        s = s[:-1].strip()

    if allow_currency and s.startswith("£"):
        s = s[1:].strip()

    if not _BODY.fullmatch(s) or not any(c.isdigit() for c in s):
        raise ValueError(f"Not a valid number: {text!r}")

    try:
        value = Decimal(s.replace(",", ""))
    except InvalidOperation as e:
        raise ValueError(f"Not a valid number: {text!r}") from e

    return -value if negative else value


def parse_currency(text: str) -> Decimal:
    """Parse a currency value such as ``£1,234.56`` or ``-£5.00``."""
    return _parse(text, allow_currency=True)


def parse_decimal(text: str) -> Decimal:
    """Parse a plain number such as ``1,234.5``."""
    return _parse(text, allow_currency=False)


def try_parse_decimal(text: str) -> Decimal | None:
    """Like :func:`parse_decimal` but returns ``None`` when the text is not a number."""
    try:
        return parse_decimal(text)
    except ValueError:
        return None


def parse_datetime(text: str) -> datetime:
    """Parse a UK date (``dd/mm/yyyy``), optionally followed by a time."""
    s = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Not a valid date: {text!r}")
