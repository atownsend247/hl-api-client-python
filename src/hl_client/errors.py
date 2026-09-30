"""Exceptions raised by the client."""


class HLError(Exception):
    """Base class for every error raised by this library."""


class AuthenticationError(HLError):
    """A login stage was rejected or its page did not look as expected."""


class ParseError(HLError):
    """A page did not have the structure the parser expects (HL may have changed it)."""


class AccountNotFoundError(HLError):
    """HL returned 404 for the requested account."""
