"""A helper for parsing contract note PDF files.

HL's contract notes are machine-generated PDFs where every piece of text is drawn at a fixed position.
The parser walks the page's content stream, remembers the position (``Td``) and text (``Tj``) of each
``q ... Q`` block, and identifies each piece of text purely by its coordinates. The coordinates below were
carried over unchanged from the C# version.

NOTE: this port has not been run against a real HL contract note (none were available). See
documentation/python-port.md.
"""

import io
import math
from datetime import datetime
from decimal import Decimal
from enum import Enum, auto
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ByteStringObject, FloatObject, TextStringObject

from .._parsing import parse_decimal
from ..entities import ContractNoteEntity, TransactionType
from ..errors import ParseError


class ElementType(Enum):
    """The element type found in the PDF."""

    UNKNOWN = auto()
    CLIENT_NAME = auto()
    ADDRESS_LINE_1 = auto()
    ADDRESS_LINE_2 = auto()
    ADDRESS_LINE_3 = auto()
    ADDRESS_LINE_4 = auto()
    ADDRESS_LINE_5 = auto()
    ADDRESS_LINE_6 = auto()
    ACCOUNT_NAME = auto()
    SETTLEMENT_DATE = auto()
    CONTRACT_NOTE_ID = auto()
    ORDER_DATE = auto()
    ORDER_TIME = auto()
    PRICE_DETAIL_TYPE_1 = auto()
    PRICE_DETAIL_VALUE_1 = auto()
    PRICE_DETAIL_TYPE_2 = auto()
    PRICE_DETAIL_VALUE_2 = auto()
    PRICE_DETAIL_TYPE_3 = auto()
    PRICE_DETAIL_VALUE_3 = auto()
    FEE_TYPE_1 = auto()
    FEE_VALUE_1 = auto()
    FEE_TYPE_2 = auto()
    FEE_VALUE_2 = auto()
    FEE_TYPE_3 = auto()
    FEE_VALUE_3 = auto()
    FEE_TYPE_4 = auto()
    FEE_VALUE_4 = auto()
    ORDER_DETAIL_NOTE_1 = auto()
    ORDER_DETAIL_NOTE_2 = auto()
    ORDER_DETAIL_NOTE_3 = auto()
    ORDER_DETAIL_NOTE_4 = auto()
    ISIN = auto()
    UNIT_NAME = auto()
    UNIT_TYPE = auto()
    UNIT_PRICE = auto()
    NOTE_LINE_1 = auto()
    NOTE_LINE_2 = auto()
    STOCK_CODE = auto()
    TRANSACTION_TYPE = auto()
    QUANTITY = auto()
    TOTAL_AMOUNT_INCLUDING_FEES = auto()
    TOTAL_AMOUNT_EXCLUDING_FEES = auto()


E = ElementType

_COORDINATES_TO_ELEMENT_TYPES: dict[tuple[float, float], ElementType] = {
    (62.36, 687.4): E.CLIENT_NAME,
    (62.36, 677.48): E.ADDRESS_LINE_1,
    (62.36, 667.56): E.ADDRESS_LINE_2,
    (62.36, 657.64): E.ADDRESS_LINE_3,
    (62.36, 647.72): E.ADDRESS_LINE_4,
    (62.36, 637.80): E.ADDRESS_LINE_5,
    (62.36, 627.88): E.ADDRESS_LINE_6,
    (34.02, 158.03): E.ACCOUNT_NAME,
    (374.17, 158.03): E.SETTLEMENT_DATE,
    (433.7, 582.52): E.CONTRACT_NOTE_ID,
    (56.69, 582.52): E.ORDER_DATE,
    (249.45, 582.52): E.ORDER_TIME,
    (493.94, 290.55): E.FEE_VALUE_1,
    (493.94, 280.63): E.FEE_VALUE_2,
    (493.94, 270.71): E.FEE_VALUE_3,
    (493.94, 260.79): E.FEE_VALUE_4,
    (119.06, 290.55): E.FEE_TYPE_1,
    (119.06, 280.63): E.FEE_TYPE_2,
    (119.06, 270.71): E.FEE_TYPE_3,
    (119.06, 260.79): E.FEE_TYPE_4,
    (119.06, 323.15): E.ORDER_DETAIL_NOTE_1,
    (119.06, 333.07): E.ORDER_DETAIL_NOTE_2,
    (119.06, 342.99): E.ORDER_DETAIL_NOTE_3,
    (119.06, 352.91): E.ORDER_DETAIL_NOTE_4,
    (119.06, 454.96): E.ISIN,
    (119.06, 445.04): E.UNIT_NAME,
    (119.06, 435.12): E.UNIT_TYPE,
    (119.06, 398.27): E.PRICE_DETAIL_TYPE_1,
    (119.06, 388.35): E.PRICE_DETAIL_TYPE_2,
    (119.06, 378.43): E.PRICE_DETAIL_TYPE_3,
    (388.35, 398.27): E.PRICE_DETAIL_VALUE_1,
    (388.35, 388.35): E.PRICE_DETAIL_VALUE_2,
    (388.35, 378.43): E.PRICE_DETAIL_VALUE_3,
    (31.18, 123.44): E.NOTE_LINE_1,
    (31.18, 109.27): E.NOTE_LINE_2,
}

_IGNORED: set[tuple[float, float]] = {
    (249.45, 593.86),
    (347.81, 435.83),
}

_ADDRESS_LINES = [
    E.ADDRESS_LINE_1,
    E.ADDRESS_LINE_2,
    E.ADDRESS_LINE_3,
    E.ADDRESS_LINE_4,
    E.ADDRESS_LINE_5,
    E.ADDRESS_LINE_6,
]
_PRICE_DETAILS = [
    (E.PRICE_DETAIL_TYPE_1, E.PRICE_DETAIL_VALUE_1),
    (E.PRICE_DETAIL_TYPE_2, E.PRICE_DETAIL_VALUE_2),
    (E.PRICE_DETAIL_TYPE_3, E.PRICE_DETAIL_VALUE_3),
]
_FEES_AND_ORDER_NOTES = [
    (E.FEE_TYPE_1, E.FEE_VALUE_1, E.ORDER_DETAIL_NOTE_1),
    (E.FEE_TYPE_2, E.FEE_VALUE_2, E.ORDER_DETAIL_NOTE_2),
    (E.FEE_TYPE_3, E.FEE_VALUE_3, E.ORDER_DETAIL_NOTE_3),
    (E.FEE_TYPE_4, E.FEE_VALUE_4, E.ORDER_DETAIL_NOTE_4),
]


def _element_type_from_coordinates(x: float, y: float) -> ElementType:
    # Coordinates are compared to two decimal places, the precision the PDFs are written with.
    ry = round(y, 2)

    if ry == 454.82:
        return E.STOCK_CODE
    if 250 < x < 280 and ry == 538.58:
        return E.TRANSACTION_TYPE
    if x < 100 and ry == 435.83:
        return E.QUANTITY
    if x > 400 and ry == 158.03:
        return E.TOTAL_AMOUNT_INCLUDING_FEES
    if 450 < x < 500 and ry in (371.34, 435.83):
        return E.TOTAL_AMOUNT_EXCLUDING_FEES
    if 360 < x < 390 and ry == 435.83:
        return E.UNIT_PRICE

    return _COORDINATES_TO_ELEMENT_TYPES.get((round(x, 2), ry), E.UNKNOWN)


def _get_tokens_for_elements(data: bytes) -> dict[ElementType, str]:
    output: dict[ElementType, str] = {}

    reader = PdfReader(io.BytesIO(data))
    for page in reader.pages:
        content = page.get_contents()
        if content is None:
            continue

        x = y = math.nan
        line_content: str | None = None
        for operands, operator in content.operations:
            if operator == b"q":
                x = y = math.nan
                line_content = None

            elif (
                operator == b"Td"
                and len(operands) == 2
                # Only real numbers count (as in the C# version); integers are ignored.
                and isinstance(operands[0], FloatObject)
                and isinstance(operands[1], FloatObject)
            ):
                x, y = float(operands[0]), float(operands[1])

            elif operator == b"Tj" and operands and isinstance(operands[0], TextStringObject | ByteStringObject):
                text = operands[0]
                line_content = text.decode("latin-1") if isinstance(text, ByteStringObject) else str(text)

            elif operator == b"Q" and line_content and line_content.strip() and not math.isnan(x):
                if (round(x, 2), round(y, 2)) in _IGNORED:
                    continue

                element_type = _element_type_from_coordinates(x, y)
                if element_type is E.UNKNOWN:
                    raise ParseError(f"Failed to identify PDF item at coordinates ({x}, {y}) = {line_content}")

                output[element_type] = line_content

    return output


def parse_contract_note(source: str | Path | bytes) -> ContractNoteEntity:
    """Parse a contract note PDF, given either its path or its bytes."""
    data = source if isinstance(source, bytes) else Path(source).read_bytes()
    tokens = _get_tokens_for_elements(data)
    note = ContractNoteEntity()

    def number(element_type: ElementType, text: str | None) -> Decimal:
        if text is None:
            raise ParseError(f"Contract note is missing a value for {element_type.name}.")
        return parse_decimal(text)

    note.client_name = tokens.get(E.CLIENT_NAME)

    note.client_address = [line for e in _ADDRESS_LINES if (line := tokens.get(e)) is not None and line.strip()]

    note.account = tokens.get(E.ACCOUNT_NAME)

    if (settlement_date := tokens.get(E.SETTLEMENT_DATE)) is not None:
        note.settlement_date = datetime.strptime(settlement_date, "%d/%m/%Y")

    if (transaction_type := tokens.get(E.TRANSACTION_TYPE)) is not None:
        if "BOUGHT" in transaction_type:
            note.transaction_type = TransactionType.BUY
        elif "SOLD" in transaction_type:
            note.transaction_type = TransactionType.SELL
        else:
            raise ParseError(f"Unknown transaction type: {transaction_type}")

    note.contract_note_id = tokens.get(E.CONTRACT_NOTE_ID)

    if (order_date := tokens.get(E.ORDER_DATE)) is not None:
        order_time = datetime.strptime(order_date, "%d/%m/%Y")
        if (time_text := tokens.get(E.ORDER_TIME)) is not None:
            hours, minutes = (int(p) for p in time_text.split(":")[:2])
            order_time = order_time.replace(hour=hours, minute=minutes)
        note.order_time = order_time

    note.unit_name = tokens.get(E.UNIT_NAME)
    note.unit_type = tokens.get(E.UNIT_TYPE)

    if (quantity := tokens.get(E.QUANTITY)) is not None:
        note.quantity = parse_decimal(quantity)

    note.isin = tokens.get(E.ISIN)

    note.note = tokens.get(E.NOTE_LINE_1)
    if (note_line_2 := tokens.get(E.NOTE_LINE_2)) is not None:
        note.note = f"{note.note} {note_line_2}" if note.note and note.note.strip() else note_line_2

    for type_element, value_element in _PRICE_DETAILS:
        detail_type = tokens.get(type_element)
        detail_value = tokens.get(value_element)

        if detail_type == "Price (pence)":
            note.unit_price_gbp = number(value_element, detail_value) / 100
        elif detail_type is not None and detail_type.startswith("Price"):
            note.unit_price = number(value_element, detail_value)
            note.unit_currency = detail_type.split(" ")[-1].replace("(", "").replace(")", "")
        elif detail_type == "Exchange rate":
            note.exchange_rate = number(value_element, detail_value)

    for fee_type_element, fee_value_element, order_note_element in _FEES_AND_ORDER_NOTES:
        fee_type = tokens.get(fee_type_element)
        fee_value = tokens.get(fee_value_element)

        if fee_type == "Commission":
            note.commission = number(fee_value_element, fee_value)
        elif fee_type == "FX Charge":
            note.fx_charge = number(fee_value_element, fee_value)
        elif fee_type == "Transfer Stamp":
            note.transfer_fee = number(fee_value_element, fee_value)

        if (order_detail_note := tokens.get(order_note_element)) is not None:
            if order_detail_note.endswith("Order"):
                note.order_type = order_detail_note
            elif order_detail_note.startswith("Venue of Execution:"):
                note.venue = order_detail_note.replace("Venue of Execution:", "").strip()

    if (stock_code := tokens.get(E.STOCK_CODE)) is not None:
        note.symbol = stock_code.replace("STOCK CODE:", "").strip()

    if (total_including := tokens.get(E.TOTAL_AMOUNT_INCLUDING_FEES)) is not None:
        note.total_amount_gbp_including_fees = parse_decimal(total_including)

    if (total_excluding := tokens.get(E.TOTAL_AMOUNT_EXCLUDING_FEES)) is not None:
        note.total_amount_gbp_excluding_fees = parse_decimal(total_excluding.replace("GBP", "").strip())

    # Notes for UK stocks carry a single unit price, in GBP.
    if (unit_price := tokens.get(E.UNIT_PRICE)) is not None:
        if note.unit_price == 0:
            note.unit_price = parse_decimal(unit_price)
        if note.unit_price_gbp == 0:
            note.unit_price_gbp = parse_decimal(unit_price)
        if note.unit_currency is None:
            note.unit_currency = "GBP"

    return note
