from __future__ import annotations

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
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(browser_profile_dir()),
                headless=False,
                args=["--no-first-run", "--no-default-browser-check"],
            )
        except Exception as exc:
            if _looks_like_missing_browser(exc):
                raise LoginFailed(
                    "Chromium is not installed for Playwright.\nRun: playwright install chromium"
                ) from exc
            raise LoginFailed(f"Could not start the browser: {exc}") from exc

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


def browser_is_installed() -> bool:
    """Look for the unpacked browser on disk. Asking Playwright itself would
    start its driver, which prints teardown noise on a plain status check."""
    root = _browsers_root()
    return root.is_dir() and any(root.glob("chromium*"))
