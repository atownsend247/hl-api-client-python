import io
from dataclasses import dataclass
from decimal import Decimal

from hl_client.utilities.csv_serializer import serialize


@dataclass
class Row:
    name: str
    amount: Decimal
    note: str | None


def test_serialize_quotes_only_when_needed() -> None:
    out = io.StringIO()

    serialize(out, [Row("plain", Decimal("1.5"), None), Row('a,"b"', Decimal(2), "x\ny")])

    assert out.getvalue() == 'name,amount,note\nplain,1.5,""\n"a,""b""",2,"x\ny"\n'


def test_serialize_empty_writes_header_only_when_type_is_known() -> None:
    with_type, without_type = io.StringIO(), io.StringIO()

    serialize(with_type, [], Row)
    serialize(without_type, [])

    assert with_type.getvalue() == "name,amount,note\n"
    assert without_type.getvalue() == ""
