from __future__ import annotations

import argparse
import json

from ..context import Context


def register(subparsers: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    group = subparsers.add_parser(
        "raw",
        parents=[common],
        help="dump the unparsed calendar JSON for a course",
    )
    group.add_argument("course", help="course slug or part of its name")
    group.set_defaults(func=cmd_raw)


def cmd_raw(ctx: Context) -> int:
    course = ctx.service.course(ctx.args.course)
    print(json.dumps(ctx.service.raw_calendar(course), ensure_ascii=False, indent=2))
    return 0
