from __future__ import annotations

import argparse

from ..context import Context
from ..output import build_table, emit


def register(subparsers: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    group = subparsers.add_parser("list", help="list courses, themes or contents")
    resources = group.add_subparsers(dest="resource", required=True)

    courses = resources.add_parser("courses", parents=[common], help="enrolled courses")
    courses.set_defaults(func=cmd_courses)

    themes = resources.add_parser("themes", parents=[common], help="themes in a course")
    themes.add_argument("course", help="course slug or part of its name")
    themes.add_argument("--section", help="only one section, for example lecture")
    themes.set_defaults(func=cmd_themes)

    contents = resources.add_parser("contents", parents=[common], help="materials in a course")
    contents.add_argument("course", help="course slug or part of its name")
    contents.add_argument("--theme", help="only one theme, by ref")
    contents.add_argument("--section", help="only one section, for example lecture")
    contents.add_argument("--kind", choices=("file", "link", "video"), help="only one kind")
    contents.set_defaults(func=cmd_contents)


def cmd_courses(ctx: Context) -> int:
    courses = ctx.service.courses()
    data = [c.to_dict() for c in courses]

    def table():
        return build_table(
            courses[0].semester if courses else "My courses",
            [
                {"header": "Slug", "style": "cyan", "no_wrap": True},
                {"header": "Course"},
                {"header": "Lecturer", "style": "dim"},
                {"header": "Tutor", "style": "dim"},
            ],
            [
                [c.slug, c.name, c.lecture_teacher or "-", c.tutorial_teacher or "-"]
                for c in courses
            ],
        )

    emit(ctx, data, table, empty="No courses found for the current semester.")
    return 0


def cmd_themes(ctx: Context) -> int:
    detail = ctx.service.detail(ctx.args.course)
    themes = detail.themes
    if ctx.args.section:
        needle = ctx.args.section.strip().lower()
        themes = [t for t in themes if needle in t.section.lower()]

    data = [t.to_dict(include_contents=False) for t in themes]

    def table():
        return build_table(
            f"{detail.course.name} ({detail.course.slug})",
            [
                {"header": "#", "style": "cyan", "no_wrap": True, "justify": "right"},
                {"header": "Section", "no_wrap": True},
                {"header": "Date", "style": "dim", "no_wrap": True},
                {"header": "Theme"},
                {"header": "Items", "justify": "right"},
            ],
            [
                [str(t.index), t.section, t.date or "-", t.label, str(len(t.contents))]
                for t in themes
            ],
        )

    emit(ctx, data, table, empty="No themes published for this course yet.")
    return 0


def cmd_contents(ctx: Context) -> int:
    args = ctx.args
    detail = ctx.service.detail(args.course)
    contents = ctx.service.filter_contents(
        detail, theme=args.theme, section=args.section, kind=args.kind
    )
    data = [c.to_dict() for c in contents]

    def table():
        return build_table(
            f"{detail.course.name} ({detail.course.slug})",
            [
                {"header": "Ref", "style": "cyan", "no_wrap": True},
                {"header": "#", "style": "dim", "no_wrap": True, "justify": "right"},
                {"header": "Kind", "no_wrap": True},
                {"header": "Section", "style": "dim", "no_wrap": True},
                {"header": "Title"},
            ],
            [[c.ref, str(c.index), c.kind, c.section, c.title] for c in contents],
        )

    emit(ctx, data, table, empty="No materials match.")
    return 0
