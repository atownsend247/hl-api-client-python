# hl-client (Python)

A Python 3.13 port of the C# Hargreaves Lansdown client in this repository. It logs in to HL's web portal
and parses the pages into typed data (accounts, holdings, cash, transactions, messages, contract notes).

HL has no public API for regular customers, so this scrapes the same routes the web portal uses.
**Your account will be locked if you enter invalid credentials too many times.**

See [../documentation/python-port.md](../documentation/python-port.md) for how the port maps to the C# code,
the decisions made, and what is untested.

## Setup

```sh
cd python
uv sync            # creates .venv with Python 3.13 and installs everything
uv run pytest      # run the tests
uv run ruff check . && uv run mypy
```

## Usage

```python
from datetime import date
from hl_client import Client

with Client() as client:
    client.authenticate("username", "password", date(1990, 1, 31), "security-number")

    for account in client.account_operations.list_accounts():
        print(account.name, account.total_value)
        for stock in client.account_operations.list_stocks(account.id):
            print("  ", stock.name, stock.value)
```

A runnable version is in [examples/list_holdings.py](examples/list_holdings.py).

Contract notes (PDFs you have downloaded) are parsed with `hl_client.parse_contract_note(path_or_bytes)`.
