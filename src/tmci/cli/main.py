from __future__ import annotations

import argparse
import json
import sys

from .. import __version__
from ..errors import EXIT_USAGE, TmciError
from ..paths import home
from .commands import GROUPS
from .context import Context
from .output import console


def build_common() -> argparse.ArgumentParser:
    """Flags every leaf command shares, so they appear in each command's own
    help rather than only at the root."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine readable output")
    common.add_argument("--no-color", action="store_true", help="disable coloured output")
    common.add_argument("--refresh", action="store_true", help="ignore cached LMS responses")
    return common


def build_parser() -> argparse.ArgumentParser:
    common = build_common()
    parser = argparse.ArgumentParser(
        prog="tmci",
        description="Command line client for the TMC Institute LMS.",
    )
    parser.add_argument("--version", action="version", version=f"tmci {__version__}")
    parser.add_argument("--home", action="store_true", help="print the config directory and exit")

    subparsers = parser.add_subparsers(dest="command")
    for module in GROUPS:
        module.register(subparsers, common)
    return parser


def force_utf8_output() -> None:
    """Windows consoles and redirected pipes default to a legacy codepage, so a
    single non-ASCII title would otherwise abort a render part-written."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    force_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.home:
        print(home())
        return 0
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE

    ctx = Context(args)
    try:
        return args.func(ctx)
    except TmciError as exc:
        _report(ctx, exc)
        return exc.exit_code
    except KeyboardInterrupt:
        _report(ctx, TmciError("Cancelled."))
        return 130
    finally:
        ctx.close()


def _report(ctx: Context, exc: TmciError) -> None:
    if ctx.as_json:
        print(json.dumps({"error": str(exc), "exit_code": exc.exit_code}))
    else:
        console(ctx, stderr=True).print(f"[red]{exc}[/red]")


if __name__ == "__main__":
    sys.exit(main())
