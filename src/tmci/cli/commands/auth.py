from __future__ import annotations

import argparse
import sys

from ... import BASE_URL
from ... import session as session_store
from ...client import Client
from ...errors import LoginFailed, NotLoggedIn, TmciError
from ...login import cookies_from_header, install_chromium, interactive_login
from ...paths import config_file
from ...session import Session
from ..context import Context
from ..output import build_table, emit, note


def register(subparsers: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    login = subparsers.add_parser(
        "login", parents=[common], help="sign in to the LMS through a browser window"
    )
    login.add_argument(
        "--cookie", help="skip the browser and use a tmci_session value or full Cookie header"
    )
    login.add_argument(
        "--timeout", type=int, default=300, help="seconds to wait for sign-in (default 300)"
    )
    login.set_defaults(func=cmd_login)

    logout = subparsers.add_parser(
        "logout", parents=[common], help="end the LMS session and delete local data"
    )
    logout.set_defaults(func=cmd_logout)

    whoami = subparsers.add_parser(
        "whoami", parents=[common], help="show who is currently signed in"
    )
    whoami.set_defaults(func=cmd_whoami)


def cmd_login(ctx: Context) -> int:
    args = ctx.args
    if args.cookie:
        cookies = cookies_from_header(args.cookie)
        if not cookies:
            raise TmciError("Could not read a tmci_session value from --cookie.")
    else:
        note(
            ctx,
            f"Opening a browser at [cyan]{ctx.config.base_url or BASE_URL}/auth/login[/cyan].\n"
            "Sign in there and this command will finish on its own.\n"
            "[dim]Your password goes into the real LMS page. "
            "Only the session cookie is stored.[/dim]",
        )
        cookies = _login_installing_browser_if_needed(ctx, args.timeout * 1000)

    session = Session(cookies=cookies)
    with Client(session, base_url=ctx.config.base_url) as client:
        if not client.is_authenticated():
            raise TmciError("That session is not valid. Try 'tmci login' again.")

    session_store.save(session)
    ctx.cache.clear()
    emit(
        ctx,
        {"status": "logged_in", "config_file": str(config_file())},
        text=f"[green]Logged in.[/green] Session stored in {config_file()}",
    )
    return 0


def _login_installing_browser_if_needed(ctx: Context, timeout_ms: int) -> dict[str, str]:
    try:
        return interactive_login(base_url=ctx.config.base_url, timeout_ms=timeout_ms)
    except LoginFailed as exc:
        if "Chromium is not installed" not in str(exc):
            raise

    note(
        ctx,
        "\n[yellow]The browser used for signing in is not downloaded yet[/yellow] "
        "(about 150MB, one time).",
    )
    if not sys.stdin.isatty():
        raise TmciError("Run 'playwright install chromium' first.")
    if input("Download it now? [Y/n] ").strip().lower() not in ("", "y", "yes"):
        raise TmciError("Cancelled. Run 'playwright install chromium' when you are ready.")
    if not install_chromium():
        raise TmciError("Download failed. Run 'playwright install chromium' by hand.")
    return interactive_login(base_url=ctx.config.base_url, timeout_ms=timeout_ms)


def cmd_logout(ctx: Context) -> int:
    try:
        ctx.client.logout()
    except NotLoggedIn:
        emit(ctx, {"status": "not_logged_in"}, text="Not logged in.")
        return 0

    session_store.clear()
    cleared = ctx.cache.clear()
    emit(
        ctx,
        {"status": "logged_out", "cache_entries_cleared": cleared},
        text="[green]Logged out.[/green]",
    )
    return 0


def cmd_whoami(ctx: Context) -> int:
    student = ctx.service.student()
    data = student.to_dict()

    def table():
        rows = [[k.replace("_", " ").title(), v] for k, v in data.items() if v]
        return build_table(
            "Signed in",
            [{"header": "Field", "style": "dim"}, {"header": "Value"}],
            rows or [["Session", "active"]],
        )

    emit(ctx, data, table)
    return 0
