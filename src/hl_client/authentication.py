"""The two-stage HL login flow (login-step-one, then login-step-two)."""

from abc import ABC, abstractmethod
from datetime import date

from bs4 import BeautifulSoup

from .errors import AuthenticationError
from .requestor import Requestor


class BaseStage(ABC):
    """Base class for a login stage: load the page, then submit the form with its verification token."""

    def __init__(self, requestor: Requestor, path: str, expected_response: str) -> None:
        self._requestor = requestor
        self.path = path
        self.expected_response = expected_response
        self.document: BeautifulSoup | None = None

    def load_page(self) -> None:
        response = self._requestor.get(self.path)
        self.document = BeautifulSoup(response.content, "lxml")

    def get_verification_token(self) -> str:
        """Load the verification token (``hl_vt``) for this stage."""
        assert self.document is not None, "load_page() must be called first"
        inputs = [i for i in self.document.find_all("input") if i.get("name") == "hl_vt"]
        if len(inputs) != 1:
            raise AuthenticationError("Unable to find verification token for Stage.")
        return str(inputs[0].get("value", ""))

    @abstractmethod
    def build_fields(self) -> dict[str, str]:
        """Build the form fields for this stage."""

    @staticmethod
    def _rejection_reason(response) -> str | None:
        """Best-effort extraction of whatever error/validation message HL
        rendered on the page we landed on instead of redirecting, e.g. "that
        username and date of birth don't match" vs. an account lockout
        notice - the two look identical as a bare redirect-path mismatch."""
        soup = BeautifulSoup(response.content, "lxml")
        for tag in soup.find_all(class_=True):
            if tag.find_parent("noscript"):
                continue
            classes = " ".join(tag.get("class") or [])
            if any(keyword in classes for keyword in ("error", "alert", "notification", "validation")):
                text = tag.get_text(" ", strip=True)
                if text:
                    return text[:300]
        return None

    def submit(self) -> None:
        fields = self.build_fields()
        fields["hl_vt"] = self.get_verification_token()

        response = self._requestor.post(self.path, data=fields)

        # A successful stage redirects to the next page.
        if response.url.path != f"/{self.expected_response}":
            reason = self._rejection_reason(response)
            detail = f" - page said: {reason!r}" if reason else ""
            raise AuthenticationError(
                f"Unable to submit Stage: expected to land on /{self.expected_response}, "
                f"got {response.status_code} {response.url.path}{detail}"
            )

    def run(self) -> None:
        self.load_page()
        self.submit()


class Stage1(BaseStage):
    """Login stage 1: username and date of birth."""

    def __init__(self, requestor: Requestor, username: str, birthday: date) -> None:
        super().__init__(requestor, "my-accounts/login-step-one", "my-accounts/login-step-two")
        self._username = username
        self._birthday = birthday

    def build_fields(self) -> dict[str, str]:
        return {
            "username": self._username,
            "date-of-birth": self._birthday.strftime("%d%m%y"),
        }


class Stage2(BaseStage):
    """Login stage 2: password and three digits of the security number."""

    def __init__(self, requestor: Requestor, password: str, security_number: str) -> None:
        super().__init__(requestor, "my-accounts/login-step-two", "my-accounts")
        self._password = password
        self._security_number = security_number

    def build_fields(self) -> dict[str, str]:
        assert self.document is not None, "load_page() must be called first"

        # Determine the inputs needed from the security number
        containers = self.document.find_all("div", class_="secure-number-container")
        if len(containers) != 1:
            raise AuthenticationError("Unable to find the secure number container for Stage 2.")

        # Keep only the boxes and the labelled boxes; a labelled box is a digit HL is asking for.
        elements = containers[0].find_all("div", class_=["secure-number-grey-box", "secure-number-container__label"])
        if not elements:
            raise AuthenticationError("Unable to get security number inputs to determine which codes are required.")

        required_digits = [
            i for i, e in enumerate(elements) if "secure-number-container__label" in (e.get("class") or [])
        ]
        if len(required_digits) < 3:
            raise AuthenticationError("Expected HL to ask for three security number digits.")

        try:
            digits = [int(self._security_number[required_digits[i]]) for i in range(3)]
        except (ValueError, IndexError) as e:
            raise AuthenticationError("The security number does not have the digits HL asked for.") from e

        return {
            "online-password-verification": self._password,
            "secure-number[1]": str(digits[0]),
            "secure-number[2]": str(digits[1]),
            "secure-number[3]": str(digits[2]),
            "submit": "Log in",
        }
