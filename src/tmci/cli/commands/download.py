from __future__ import annotations

import argparse
import webbrowser

from ...errors import TmciError
from ..context import Context
from ..output import emit, note, warn


def register(subparsers: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    download = subparsers.add_parser("download", parents=[common], help="download course materials")
    download.add_argument("course", help="course slug or part of its name")
    download.add_argument("ref", nargs="*", help="theme.item, index, LMS id, or part of a title")
    download.add_argument("--all", action="store_true", help="every file that matches the filters")
    download.add_argument("--theme", help="restrict to one theme")
    download.add_argument("--section", help="restrict to one section")
    download.add_argument("--kind", choices=("file", "link", "video"), help="restrict to one kind")
    download.add_argument("--out", help="directory to save into")
    download.set_defaults(func=cmd_download)

    open_cmd = subparsers.add_parser(
        "open", parents=[common], help="open a link or file in the default browser"
    )
    open_cmd.add_argument("course", help="course slug or part of its name")
    open_cmd.add_argument("ref", help="theme.item, index, LMS id, or part of the title")
    open_cmd.set_defaults(func=cmd_open)


def cmd_download(ctx: Context) -> int:
    args = ctx.args
    narrowed = args.ref or args.theme or args.section or args.kind
    if not narrowed and not args.all:
        raise TmciError(
            "Choose what to download: a ref like 3.2, a --theme/--section/--kind filter, or --all."
        )

    detail = ctx.service.detail(args.course)
    selected = ctx.service.filter_contents(
        detail,
        theme=args.theme,
        section=args.section,
        kind=args.kind,
        refs=args.ref or None,
    )
    if not selected:
        raise TmciError("Nothing matches those filters.")

    root = ctx.download_root()
    results: list[dict[str, object]] = []
    failures = 0

    for item in selected:
        if item.kind == "link":
            url = ctx.service.absolute_url(item.url) if item.url else None
            results.append({"ref": item.ref, "title": item.title, "link": url})
            note(ctx, f"[yellow]link [/yellow] {item.ref:>6}  {item.title}  {url or '-'}")
            continue
        try:
            path = ctx.service.download(detail.course, item, root)
        except TmciError as exc:
            failures += 1
            results.append({"ref": item.ref, "title": item.title, "error": str(exc)})
            warn(ctx, f"[red]skip [/red] {item.ref:>6}  {item.title}: {exc}")
            continue
        results.append({"ref": item.ref, "title": item.title, "path": str(path)})
        note(ctx, f"[green]saved[/green] {item.ref:>6}  {path}")

    if ctx.as_json:
        emit(ctx, results)

    # A partial failure still produced files, so only a total wipe-out is an error.
    return 1 if failures and failures == len(selected) else 0


def cmd_open(ctx: Context) -> int:
    detail = ctx.service.detail(ctx.args.course)
    content = ctx.service.content(detail, ctx.args.ref)
    if not content.url:
        raise TmciError(f"'{content.title}' has no URL in the LMS data.")

    url = ctx.service.absolute_url(content.url)
    opened = webbrowser.open(url)
    emit(
        ctx,
        {"ref": content.ref, "title": content.title, "url": url, "opened": opened},
        text=f"{'Opening' if opened else 'Could not open'} {url}",
    )
    return 0 if opened else 1
