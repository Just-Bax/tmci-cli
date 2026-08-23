from __future__ import annotations

from typing import Any

import httpx

from . import BASE_URL
from .errors import SessionExpired, TmciError
from .session import Session, touch

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

LOGIN_PATH = "/auth/login"


class Client:
    """Cookie-authenticated HTTP client for the LMS.

    Every response is checked for the login redirect: an expired session gets a
    302 to /auth/login, not a 401, so an unchecked call parses the login page.
    """

    def __init__(
        self,
        session: Session,
        base_url: str = BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.host = httpx.URL(self.base_url).host
        self._http = httpx.Client(
            base_url=self.base_url,
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )
        # Seeded without a domain these land under "", and the server's own
        # Set-Cookie then adds a second entry under the host, leaving two
        # cookies of the same name in the jar.
        for name, value in session.cookies.items():
            self._http.cookies.set(name, value, domain=self.host, path="/")

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _check(self, response: httpx.Response) -> httpx.Response:
        if LOGIN_PATH in str(response.url):
            raise SessionExpired
        response.raise_for_status()
        self._refresh_cookies()
        return response

    def _current_cookies(self) -> dict[str, str]:
        """Cookies.get() raises CookieConflict when one name exists under several
        domains, which a redirect chain can produce."""
        exact: dict[str, str] = {}
        wider: dict[str, str] = {}
        for cookie in self._http.cookies.jar:
            target = exact if (cookie.domain or "").lstrip(".") == self.host else wider
            target[cookie.name] = cookie.value
        return {**wider, **exact}

    def _refresh_cookies(self) -> None:
        current = self._current_cookies()
        changed = False
        for name in list(self.session.cookies):
            value = current.get(name)
            if value and value != self.session.cookies[name]:
                self.session.cookies[name] = value
                changed = True
        # The LMS slides the 2h expiry forward on every response, so the stored
        # copy only needs to keep roughly in step with it.
        if changed or self.session.age_seconds > 60:
            touch(self.session)

    def get_html(self, path: str) -> str:
        return self._check(self._http.get(path)).text

    def get_json(self, path: str) -> Any:
        response = self._check(
            self._http.get(
                path,
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
        )
        try:
            return response.json()
        except ValueError:
            raise TmciError(
                f"Expected JSON from {path}, got {response.headers.get('content-type')}"
            ) from None

    def fetch_file(self, url: str, referer: str | None = None) -> httpx.Response:
        headers = {"Referer": referer or f"{self.base_url}/student/my-courses"}
        response = self._http.get(url, headers=headers)
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" in content_type and LOGIN_PATH in response.text:
            raise SessionExpired
        response.raise_for_status()
        return response

    def is_authenticated(self) -> bool:
        try:
            response = self._http.get("/dashboard")
        except httpx.HTTPError:
            return False
        return LOGIN_PATH not in str(response.url)

    def logout(self) -> None:
        try:
            self._http.get("/logout")
        except httpx.HTTPError:
            pass
