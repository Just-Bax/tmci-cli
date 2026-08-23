from __future__ import annotations

import httpx
import pytest

from tmci.client import Client
from tmci.errors import SessionExpired
from tmci.session import Session

pytestmark = pytest.mark.usefixtures("tmci_home")

BASE = "https://lms.tmci.uz"


def make_client(handler, cookies=None) -> Client:
    session = Session(cookies=cookies or {"tmci_session": "abc", "XSRF-TOKEN": "old"})
    return Client(session, base_url=BASE, transport=httpx.MockTransport(handler))


def set_cookie_handler(request: httpx.Request) -> httpx.Response:
    """Answer the way the LMS does: re-issue both cookies with no Domain
    attribute, so the jar files them under the request host."""
    return httpx.Response(
        200,
        html="<html>ok</html>",
        headers=[
            ("set-cookie", "XSRF-TOKEN=fresh; path=/; secure; samesite=lax"),
            ("set-cookie", "tmci_session=fresh-session; path=/; httponly; samesite=lax"),
        ],
    )


def test_response_cookies_do_not_duplicate_the_seeded_ones():
    client = make_client(set_cookie_handler)
    client.get_html("/student/my-courses")

    names = [c.name for c in client._http.cookies.jar]
    assert sorted(names) == ["XSRF-TOKEN", "tmci_session"]


def test_a_request_after_login_does_not_raise_cookie_conflict():
    client = make_client(set_cookie_handler)

    # Regression: seeding cookies without a domain left two XSRF-TOKEN entries
    # in the jar, and Cookies.get() refused to choose between them.
    client.get_html("/student/my-courses")
    client.get_html("/student/my-courses")


def test_rotated_cookies_are_written_back_to_the_session():
    client = make_client(set_cookie_handler)
    client.get_html("/student/my-courses")

    assert client.session.cookies["XSRF-TOKEN"] == "fresh"
    assert client.session.cookies["tmci_session"] == "fresh-session"


def test_seeded_cookies_are_sent_to_the_lms():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["cookie"] = request.headers.get("cookie", "")
        return httpx.Response(200, html="<html>ok</html>")

    make_client(handler).get_html("/student/my-courses")

    assert "tmci_session=abc" in seen["cookie"]


def test_a_parent_domain_duplicate_resolves_to_the_host_cookie():
    client = make_client(set_cookie_handler)
    client._http.cookies.set("XSRF-TOKEN", "parent", domain=".tmci.uz", path="/")

    assert client._current_cookies()["XSRF-TOKEN"] == "old"


def test_login_redirect_is_reported_as_an_expired_session():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, html="<html>login</html>")
        return httpx.Response(302, headers={"location": f"{BASE}/auth/login"})

    with pytest.raises(SessionExpired):
        make_client(handler).get_html("/student/my-courses")


def test_json_endpoint_sends_the_ajax_header():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"types": {}})

    assert make_client(handler).get_json("/x") == {"types": {}}
    assert seen["x-requested-with"] == "XMLHttpRequest"


def test_a_file_download_that_returns_the_login_page_is_an_expired_session():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            html="<html><form action='/auth/login'></form></html>",
            headers={"content-type": "text/html"},
        )

    with pytest.raises(SessionExpired):
        make_client(handler).fetch_file(f"{BASE}/f/1")


def test_is_authenticated_follows_the_login_redirect():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, html="<html>login</html>")
        return httpx.Response(302, headers={"location": f"{BASE}/auth/login"})

    assert make_client(handler).is_authenticated() is False


def test_is_authenticated_accepts_the_dashboard():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html="<html>dashboard</html>")

    assert make_client(handler).is_authenticated() is True
