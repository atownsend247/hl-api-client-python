"""Tests for the contract note parser using PDFs built by hand.

These prove the content-stream walking and field mapping logic. They do NOT prove the parser works on a
real HL contract note; that needs real samples.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from hl_client import ParseError, TransactionType, parse_contract_note


def build_pdf(items: list[tuple[float | int, float | int, str]]) -> bytes:
    """A one page PDF whose content stream draws each text item as ``q BT x y Td (text) Tj ET Q``."""
    stream = "\n".join(f"q\nBT\n{x} {y} Td\n({text}) Tj\nET\nQ" for x, y, text in items).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def test_parses_a_foreign_stock_purchase() -> None:
    pdf = build_pdf(
        [
            (62.36, 687.4, "Mr A Client"),
            (62.36, 677.48, "1 Some Street"),
            (62.36, 667.56, "Townsville"),
            (34.02, 158.03, "Stocks & Shares ISA"),
            (374.17, 158.03, "05/03/2021"),
            (433.7, 582.52, "ABC123"),
            (56.69, 582.52, "03/03/2021"),
            (249.45, 582.52, "14:32"),
            (249.45, 593.86, "ignored"),
            (260.5, 538.58, "BOUGHT"),
            (119.06, 454.96, "US0378331005"),
            (119.06, 445.04, "Apple Inc"),
            (119.06, 435.12, "Ordinary Shares"),
            (119.06, 454.82, "STOCK CODE: AAPL"),
            (40.0, 435.83, "10"),
            (119.06, 398.27, "Price (USD)"),
            (388.35, 398.27, "150.5"),
            (119.06, 388.35, "Exchange rate"),
            (388.35, 388.35, "1.25"),
            (119.06, 378.43, "Price (pence)"),
            (388.35, 378.43, "12040"),
            (119.06, 290.55, "Commission"),
            (493.94, 290.55, "11.95"),
            (119.06, 280.63, "FX Charge"),
            (493.94, 280.63, "5.5"),
            (119.06, 270.71, "Transfer Stamp"),
            (493.94, 270.71, "0.5"),
            (119.06, 323.15, "Market Order"),
            (119.06, 333.07, "Venue of Execution: NASDAQ"),
            (470.0, 371.34, "GBP 1,204.00"),
            (450.5, 158.03 + 0, "1,221.95"),
            (31.18, 123.44, "First note."),
            (31.18, 109.27, "Second note."),
        ]
    )

    note = parse_contract_note(pdf)

    assert note.client_name == "Mr A Client"
    assert note.client_address == ["1 Some Street", "Townsville"]
    assert note.account == "Stocks & Shares ISA"
    assert note.settlement_date == datetime(2021, 3, 5)
    assert note.contract_note_id == "ABC123"
    assert note.order_time == datetime(2021, 3, 3, 14, 32)
    assert note.transaction_type is TransactionType.BUY
    assert (note.isin, note.unit_name, note.unit_type, note.symbol) == (
        "US0378331005",
        "Apple Inc",
        "Ordinary Shares",
        "AAPL",
    )
    assert note.quantity == Decimal(10)
    assert (note.unit_price, note.unit_currency) == (Decimal("150.5"), "USD")
    assert note.exchange_rate == Decimal("1.25")
    assert note.unit_price_gbp == Decimal("120.40")
    assert (note.commission, note.fx_charge, note.transfer_fee) == (
        Decimal("11.95"),
        Decimal("5.5"),
        Decimal("0.5"),
    )
    assert (note.order_type, note.venue) == ("Market Order", "NASDAQ")
    assert note.total_amount_gbp_excluding_fees == Decimal("1204.00")
    assert note.total_amount_gbp_including_fees == Decimal("1221.95")
    assert note.note == "First note. Second note."


def test_uk_stock_uses_single_price_as_gbp() -> None:
    pdf = build_pdf([(260.5, 538.58, "SOLD"), (370.0, 435.83, "2.5")])

    note = parse_contract_note(pdf)

    assert note.transaction_type is TransactionType.SELL
    assert (note.unit_price, note.unit_price_gbp, note.unit_currency) == (
        Decimal("2.5"),
        Decimal("2.5"),
        "GBP",
    )


def test_unknown_coordinates_are_an_error() -> None:
    with pytest.raises(ParseError, match="Failed to identify"):
        parse_contract_note(build_pdf([(1.5, 2.5, "mystery")]))


def test_accepts_a_path(tmp_path: Path) -> None:
    path = tmp_path / "note.pdf"
    path.write_bytes(build_pdf([(62.36, 687.4, "Someone")]))

    assert parse_contract_note(path).client_name == "Someone"
