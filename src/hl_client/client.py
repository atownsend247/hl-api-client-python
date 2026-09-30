"""The base client."""

from datetime import date
from types import TracebackType

from .authentication import Stage1, Stage2
from .operations.account import AccountOperations
from .operations.linked_account import LinkedAccountOperations
from .operations.message import MessageOperations
from .requestor import Requestor


class Client:
    def __init__(self, requestor: Requestor | None = None) -> None:
        self._requestor = requestor or Requestor()
        self.is_authenticated = False

        self.account_operations = AccountOperations(self._requestor)
        self.message_operations = MessageOperations(self._requestor)
        self.linked_account_operations = LinkedAccountOperations(self._requestor)

    def authenticate(self, username: str, password: str, birthday: date, security_number: str) -> None:
        """Authenticate the client.

        Beware: HL will lock your account if you submit invalid credentials too many times.
        """
        Stage1(self._requestor, username, birthday).run()
        Stage2(self._requestor, password, security_number).run()
        self.is_authenticated = True

    def close(self) -> None:
        self._requestor.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
