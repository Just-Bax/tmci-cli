from __future__ import annotations

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4
EXIT_PARSE = 5


class TmciError(Exception):
    """Base class for errors the CLI knows how to report."""

    exit_code = EXIT_ERROR


class NotLoggedIn(TmciError):
    exit_code = EXIT_AUTH

    def __init__(self) -> None:
        super().__init__("Not logged in. Run 'tmci login' first.")


class SessionExpired(TmciError):
    exit_code = EXIT_AUTH

    def __init__(self) -> None:
        super().__init__("LMS session expired. Run 'tmci login' again.")


class NotFound(TmciError):
    exit_code = EXIT_NOT_FOUND


class Ambiguous(TmciError):
    exit_code = EXIT_NOT_FOUND


class ParseError(TmciError):
    """The LMS returned a page we could not read, usually because its markup changed."""

    exit_code = EXIT_PARSE


class LoginFailed(TmciError):
    exit_code = EXIT_AUTH
