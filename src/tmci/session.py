from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from . import store
from .errors import NotLoggedIn

SESSION_COOKIE = "tmci_session"
CSRF_COOKIE = "XSRF-TOKEN"


@dataclass
class Session:
    cookies: dict[str, str]
    saved_at: float = field(default_factory=time.time)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.saved_at

    def to_dict(self) -> dict[str, Any]:
        return {"cookies": self.cookies, "saved_at": self.saved_at}


def cookies_from_playwright(raw: list[dict[str, Any]]) -> dict[str, str]:
    return {
        c["name"]: c["value"]
        for c in raw
        if c.get("name") in (SESSION_COOKIE, CSRF_COOKIE) and c.get("value")
    }


def save(session: Session) -> None:
    store.update(**{store.SESSION_KEY: session.to_dict()})


def load() -> Session:
    data = store.read().get(store.SESSION_KEY)
    if not isinstance(data, dict):
        raise NotLoggedIn

    cookies = data.get("cookies")
    if not isinstance(cookies, dict) or not cookies.get(SESSION_COOKIE):
        raise NotLoggedIn

    return Session(cookies=cookies, saved_at=float(data.get("saved_at", 0)))


def exists() -> bool:
    try:
        load()
    except NotLoggedIn:
        return False
    return True


def clear() -> bool:
    if store.SESSION_KEY not in store.read():
        return False
    store.update(**{store.SESSION_KEY: None})
    return True


def touch(session: Session) -> None:
    """Persist the sliding expiry after a successful request."""
    session.saved_at = time.time()
    save(session)
