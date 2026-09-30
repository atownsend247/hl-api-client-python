"""The general class for making any request."""

import httpx

from .constants import BASE_URL


class Requestor:
    """Wraps an ``httpx.Client`` that keeps the session cookies (notably ``HLWEBsession``) between requests."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=BASE_URL,
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    def get(self, path: str) -> httpx.Response:
        return self._http.get(path)

    def post(self, path: str, data: dict[str, str] | None = None) -> httpx.Response:
        return self._http.post(path, data=data)

    def close(self) -> None:
        self._http.close()
