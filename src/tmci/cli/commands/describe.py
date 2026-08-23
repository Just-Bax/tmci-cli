from __future__ import annotations

import argparse

from ..context import Context
from ..output import build_table, emit


def register(subparsers: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    group = subparsers.add_parser("describe", help="show details of one course, theme or content")
    resources = group.add_subparsers(dest="resource", required=True)

    course = resources.add_parser("course", parents=[common], help="one course")
    course.add_argument("course", help="course slug or part of its name")
    course.set_defaults(func=cmd_course)

    theme = resources.add_parser("theme", parents=[common], help="one theme and its materials")
    theme.add_argument("course", help="course slug or part of its name")
    theme.add_argument("ref", help="theme index, section:index, or part of the title")
    theme.set_defaults(func=cmd_theme)

    content = resources.add_parser("content", parents=[common], help="one material item")
    content.add_argument("course", help="course slug or part of its name")
    content.add_argument("ref", help="theme.item, index, LMS id, or part of the title")
    content.set_defaults(func=cmd_content)


def cmd_course(ctx: Context) -> int:
    detail = ctx.service.detail(ctx.args.course)
    course = detail.course
    data = detail.to_dict(include_contents=False)

    def table():
        rows = [
            ["Course", course.name],
            ["Slug", course.slug],
            ["Semester", course.semester or "-"],
            ["Lecturer", course.lecture_teacher or "-"],
            ["Tutor", course.tutorial_teacher or "-"],
        ]
        for row in detail.summary():
            rows.append(
                [
                    row["section"],
                    f"{_plural(row['themes'], 'theme')}, {_plural(row['contents'], 'item')}",
                ]
            )
        return build_table(None, [{"header": "Field", "style": "dim"}, {"header": "Value"}], rows)

    emit(ctx, data, table)
    return 0


def cmd_theme(ctx: Context) -> int:
    detail = ctx.service.detail(ctx.args.course)
    theme = ctx.service.theme(detail, ctx.args.ref)
    data = theme.to_dict()

    def table():
        return build_table(
            f"[{theme.index}] {theme.label} ({theme.section})",
            [
                {"header": "Ref", "style": "cyan", "no_wrap": True},
                {"header": "Kind", "no_wrap": True},
                {"header": "Title"},
            ],
            [[c.ref, c.kind, c.title] for c in theme.contents],
        )

    emit(ctx, data, table, empty="This theme has no materials.")
    return 0


def cmd_content(ctx: Context) -> int:
    detail = ctx.service.detail(ctx.args.course)
    content = ctx.service.content(detail, ctx.args.ref)
    theme = next((t for t in detail.themes if t.index == content.theme_index), None)

    data = content.to_dict()
    data["theme"] = theme.to_dict(include_contents=False) if theme else None
    data["absolute_url"] = ctx.service.absolute_url(content.url) if content.url else None

    def table():
        rows = [
            ["Ref", content.ref],
            ["Title", content.title],
            ["Kind", content.kind],
            ["Section", content.section],
            ["Theme", theme.label if theme else "-"],
            ["File name", content.file_name or "-"],
            ["LMS id", content.lms_id or "-"],
            ["URL", data["absolute_url"] or "-"],
        ]
        if content.description:
            rows.append(["Description", content.description])
        return build_table(None, [{"header": "Field", "style": "dim"}, {"header": "Value"}], rows)

    emit(ctx, data, table)
    return 0


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
