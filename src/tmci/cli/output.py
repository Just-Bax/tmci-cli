from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.table import Table

from .context import Context

_TableBuilder = Callable[[], Table]


def console(ctx: Context, stderr: bool = False) -> Console:
    return Console(stderr=stderr, no_color=not ctx.use_color)


def emit(
    ctx: Context,
    data: Any,
    table: _TableBuilder | None = None,
    empty: str = "",
    text: str | None = None,
) -> None:
    """Single decision point for how a command's result reaches the user:
    commands build data and describe how to show it, nothing else prints."""
    if ctx.as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    out = console(ctx)
    if text is not None:
        out.print(text)
        return
    if not data and empty:
        out.print(empty)
        return
    if table is not None:
        out.print(table())


def note(ctx: Context, message: str) -> None:
    """Human-facing progress or status text, suppressed in JSON mode."""
    if not ctx.as_json:
        console(ctx).print(message)


def warn(ctx: Context, message: str) -> None:
    if not ctx.as_json:
        console(ctx, stderr=True).print(message)


def build_table(title: str | None, columns: list[dict[str, Any]], rows: list[list[str]]) -> Table:
    table = Table(title=title, title_justify="left")
    for column in columns:
        table.add_column(**column)
    for row in rows:
        table.add_row(*row)
    return table
