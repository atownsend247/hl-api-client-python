"""A client for pulling information about your accounts from Hargreaves Lansdown's web portal."""

from .client import Client
from .entities import (
    AccountEntity,
    CashSummaryEntity,
    ClientAccountEntity,
    ContractNoteEntity,
    GainsLossEntity,
    MessageEntity,
    MessageNewTypes,
    StockEntity,
    TransactionEntity,
    TransactionType,
)
from .errors import AccountNotFoundError, AuthenticationError, HLError, ParseError
from .requestor import Requestor
from .utilities.contract_note_parser import parse_contract_note

__all__ = [
    "AccountEntity",
    "AccountNotFoundError",
    "AuthenticationError",
    "CashSummaryEntity",
    "Client",
    "ClientAccountEntity",
    "ContractNoteEntity",
    "GainsLossEntity",
    "HLError",
    "MessageEntity",
    "MessageNewTypes",
    "ParseError",
    "Requestor",
    "StockEntity",
    "TransactionEntity",
    "TransactionType",
    "parse_contract_note",
]
