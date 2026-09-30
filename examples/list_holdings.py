"""Log in and print every account and stock holding.

Set HL_USERNAME, HL_PASSWORD, HL_BIRTHDAY (YYYY-MM-DD) and HL_SECURITY_CODE first.
"""

import os
from datetime import date

from hl_client import Client


def main() -> None:
    username = os.environ["HL_USERNAME"]
    password = os.environ["HL_PASSWORD"]
    birthday = date.fromisoformat(os.environ["HL_BIRTHDAY"])
    security_code = os.environ["HL_SECURITY_CODE"]

    with Client() as client:
        client.authenticate(username, password, birthday, security_code)

        for client_account in client.linked_account_operations.list_accounts():
            print(f"- Client account {client_account.client_number}: {client_account.name}")

            if not client_account.currently_selected and not client.linked_account_operations.switch(
                client_account.client_number
            ):
                print("Failed to switch to account, skipping")
                continue

            for account in client.account_operations.list_accounts():
                print(f"  - Account: {account.name}")
                print(f"          Current Value: {account.total_value}")
                print(f"          Total Share Value: {account.stock_value}")
                print(f"          Cash Held on Account: {account.cash_value}")

                print("    Stocks & Funds")
                for stock in client.account_operations.list_stocks(account.id):
                    print(f"      - Stock Holding: {stock.name} {stock.units_held} {stock.unit_type}")
                    print(f"          Current Value: {stock.value}")
                    print(f"          Bought at: {stock.cost}")
                    print(f"          Bought at price: {stock.price}")

                    if stock.gains_loss.percentage > 0:
                        print(f"          You have made a PROFIT of {stock.gains_loss.pounds} to date.")
                    elif stock.gains_loss.percentage == 0:
                        print("          You have not made a profit or loss to date.")
                    else:
                        print(f"          You have made a LOSS of {stock.gains_loss.pounds} to date.")

                print()


if __name__ == "__main__":
    main()
