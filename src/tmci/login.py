from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import BASE_URL
from .errors import LoginFailed
from .paths import browser_profile_dir
from .session import cookies_from_playwright

LOGIN_PATH = "/auth/login"
LOGIN_WAIT_MS = 5 * 60 * 1000

_MISSING_BROWSER_HINTS = ("executable doesn't exist", "please run the following command")


def interactive_login(base_url: str = BASE_URL, timeout_ms: int = LOGIN_WAIT_MS) -> dict[str, str]:
    """Open a real browser at the LMS login page and return the session cookies
    once the user has signed in.

    The credentials never pass through this process: the user types them into the
    genuine page. A real browser is also the only way past the login form's
    reCAPTCHA v3, which the LMS validates server-side.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise LoginFailed(
            "Playwright is not installed.\n"
            "Run: pip install playwright && playwright install chromium"
        ) from None

    base_url = base_url.rstrip("/")
    with sync_playwright() as p:
        context = _launch(p)

        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(f"{base_url}{LOGIN_PATH}", wait_until="domcontentloaded", timeout=60000)

            if LOGIN_PATH in page.url:
                try:
                    page.wait_for_url(
                        lambda url: LOGIN_PATH not in url,
                        timeout=timeout_ms,
                    )
                except Exception as exc:
                    raise LoginFailed(
                        "Timed out waiting for sign-in. The browser window was closed "
                        "or the login never completed."
                    ) from exc

            cookies = cookies_from_playwright(context.cookies())
        finally:
            context.close()

    if not cookies:
        raise LoginFailed("Signed in, but no session cookie was issued by the LMS.")
    return cookies


def _launch(p: Any, headless: bool = False) -> Any:
    options = {
        "user_data_dir": str(browser_profile_dir()),
        "headless": headless,
        "args": ["--no-first-run", "--no-default-browser-check"],
    }
    try:
        return p.chromium.launch_persistent_context(**options)
    except Exception as exc:
        if not _looks_like_missing_browser(exc):
            raise LoginFailed(f"Could not start the browser: {exc}") from exc
        _fetch_browser()

    try:
        return p.chromium.launch_persistent_context(**options)
    except Exception as exc:
        raise LoginFailed(f"Could not start the browser: {exc}") from exc


def _fetch_browser() -> None:
    """Download the browser mid-login, rather than sending the user away.

    The old advice, "playwright install chromium", names a command the user does
    not have: the tool install exposes the tmci entry point and nothing else.
    """
    if not install_chromium():
        raise LoginFailed(
            "The sign-in browser could not be downloaded.\n"
            "Check your connection, then run: tmci setup"
        )


def _looks_like_missing_browser(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(hint in message for hint in _MISSING_BROWSER_HINTS)


def install_chromium() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
    )
    return result.returncode == 0


def cookies_from_header(raw: str) -> dict[str, str]:
    """Accept either a bare tmci_session value or a full Cookie header."""
    raw = raw.strip()
    if "=" not in raw:
        return {"tmci_session": raw}
    jar: dict[str, Any] = {}
    for part in raw.split(";"):
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        jar[name.strip()] = value.strip()
    return {k: v for k, v in jar.items() if k in ("tmci_session", "XSRF-TOKEN") and v}


def _browsers_root() -> Path:
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if override:
        return Path(override)
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def _pinned_builds() -> list[str]:
    """The browser directories this Playwright expects, from its own manifest.

    Playwright pins a build number per version, and the marker file is written
    only once a download finishes.
    """
    import playwright

    manifest = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
    entries = json.loads(manifest.read_text(encoding="utf-8"))["browsers"]
    return [
        f"{entry['name'].replace('-', '_')}-{entry['revision']}"
        for entry in entries
        if entry["name"].startswith("chromium") and entry.get("installByDefault")
    ]


def browser_is_installed() -> bool:
    """Whether every browser build this Playwright pins is on disk and complete.

    Matching the directory name alone accepts a chromium left behind by some
    other project, which sits in the same place under a different build number
    and cannot launch. That reported ready here while the launch failed, so
    'tmci setup' sent the user to 'tmci setup'. An unreadable manifest counts as
    missing: installing again is harmless, claiming a browser that will not
    start is not.
    """
    root = _browsers_root()
    try:
        wanted = _pinned_builds()
    except Exception:
        return False
    return bool(wanted) and all((root / name / "INSTALLATION_COMPLETE").exists() for name in wanted)
