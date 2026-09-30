"""The data returned by the client.

Each class corresponds to a ``*Entity`` class in the C# version and keeps its name so the two code bases
are easy to compare.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


@dataclass(slots=True)
class AccountEntity:
    id: int
    name: str
    stock_value: Decimal
    cash_value: Decimal
    total_value: Decimal
    available: Decimal


@dataclass(slots=True)
class CashSummaryEntity:
    cash_on_capital_account: Decimal
    """The cash capital on an account."""
    income_loyalty_bonus: Decimal
    fixed_rate_offers: Decimal
    total_cash: Decimal


@dataclass(slots=True)
class ClientAccountEntity:
    client_number: int
    name: str
    currently_selected: bool


@dataclass(slots=True)
class GainsLossEntity:
    pounds: Decimal
    percentage: Decimal


@dataclass(slots=True)
class StockEntity:
    id: str
    name: str
    unit_type: str
    units_held: Decimal
    price: Decimal
    value: Decimal
    cost: Decimal
    gains_loss: GainsLossEntity


@dataclass(slots=True)
class TransactionEntity:
    trade_date: datetime
    settle_date: datetime
    reference: str
    reference_link: str | None
    description: str
    unit_cost: Decimal | None
    quantity: Decimal | None
    value: Decimal


@dataclass(slots=True)
class MessageEntity:
    id: int
    title: str
    received_at: datetime
    message: str | None = None


class MessageNewTypes:
    """The possible new message types."""

    GENERAL_ENQUIRY = "A0021"
    """Vantage ISA, Fund and Share Account or general enquiry."""
    PENSIONS_RETIREMENT = "A0030"
    """Pensions and Retirement."""
    CORPORATE_ACTION_INSTRUCTIONS_OR_VOTING_INSTRUCTIONS_OR_AGM_REQUESTS = "OCA"
    """Corporate Action instructions / Voting instructions / AGM requests."""


class TransactionType(Enum):
    UNKNOWN = "Unknown"
    BUY = "Buy"
    SELL = "Sell"


@dataclass(slots=True)
class ContractNoteEntity:
    """The content of a contract note. Fields the PDF does not contain keep their defaults."""

    transaction_type: TransactionType = TransactionType.UNKNOWN
    contract_note_id: str | None = None
    isin: str | None = None
    order_time: datetime | None = None
    unit_name: str | None = None
    unit_type: str | None = None
    quantity: Decimal = Decimal(0)
    unit_price: Decimal = Decimal(0)
    """The unit price in its local currency."""
    unit_currency: str | None = None
    exchange_rate: Decimal = Decimal(0)
    unit_price_gbp: Decimal = Decimal(0)
    commission: Decimal = Decimal(0)
    fx_charge: Decimal = Decimal(0)
    """Foreign currency exchange fees."""
    transfer_fee: Decimal = Decimal(0)
    total_amount_gbp_excluding_fees: Decimal = Decimal(0)
    total_amount_gbp_including_fees: Decimal = Decimal(0)
    venue: str | None = None
    order_type: str | None = None
    symbol: str | None = None
    account: str | None = None
    settlement_date: datetime | None = None
    note: str | None = None
    client_name: str | None = None
    client_address: list[str] = field(default_factory=list)
