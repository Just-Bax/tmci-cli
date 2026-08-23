from __future__ import annotations

import re

from .errors import Ambiguous, NotFound
from .models import Content, Course, Theme

_HIERARCHICAL = re.compile(r"^(\d+)\.(\d+)$")
_SECTIONED = re.compile(r"^([A-Za-z][\w-]*):(\d+)$")


def resolve_course(courses: list[Course], ref: str) -> Course:
    needle = ref.strip().lower()
    if not needle:
        raise NotFound("No course given.")

    for course in courses:
        if course.slug.lower() == needle:
            return course

    matches = [c for c in courses if needle in c.name.lower()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        listed = ", ".join(f"{c.name} ({c.slug})" for c in matches[:5])
        raise Ambiguous(f"'{ref}' matches several courses: {listed}")
    raise NotFound(f"No course matching '{ref}'. Run 'tmci list courses' to see them.")


def resolve_theme(themes: list[Theme], ref: str) -> Theme:
    needle = ref.strip()
    if not needle:
        raise NotFound("No theme given.")

    sectioned = _SECTIONED.match(needle)
    if sectioned:
        section, position = sectioned.group(1).lower(), int(sectioned.group(2))
        for theme in themes:
            if theme.section.lower() == section and theme.position == position:
                return theme
        raise NotFound(f"No theme {position} in section '{sectioned.group(1)}'.")

    if needle.isdigit():
        wanted = int(needle)
        for theme in themes:
            if theme.index == wanted:
                return theme
        raise NotFound(f"No theme {wanted} in this course.")

    lowered = needle.lower()
    matches = [t for t in themes if lowered in t.title.lower()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        listed = ", ".join(f"{t.index}: {t.title}" for t in matches[:5])
        raise Ambiguous(f"'{ref}' matches several themes: {listed}")
    raise NotFound(f"No theme matching '{ref}'.")


def select_contents(contents: list[Content], ref: str) -> list[Content]:
    """Title matches can be plural on purpose, so 'tmci download X week 3'
    can pull a whole week at once."""
    needle = ref.strip()
    if not needle:
        raise NotFound("No content given.")

    hierarchical = _HIERARCHICAL.match(needle)
    if hierarchical:
        theme_index, position = int(hierarchical.group(1)), int(hierarchical.group(2))
        found = [c for c in contents if c.theme_index == theme_index and c.position == position]
        if not found:
            raise NotFound(f"No content {needle} in this course.")
        return found

    lowered = needle.lower()

    # A bare number never falls through to titles. Indexes are course-wide but
    # filters narrow the list, so "5" can drop out of a filtered set and would
    # otherwise silently match any title containing a 5.
    if needle.isdigit():
        wanted = int(needle)
        exact = [c for c in contents if c.index == wanted]
        exact += [c for c in contents if c.lms_id == needle and c not in exact]
        if exact:
            return exact
        raise NotFound(f"No content numbered {needle} here. Use a ref like 3.2 to be exact.")

    by_id = [c for c in contents if c.lms_id and c.lms_id.lower() == lowered]
    if by_id:
        return by_id

    by_title = [c for c in contents if lowered in c.title.lower()]
    if by_title:
        return by_title

    raise NotFound(f"No content matching '{ref}'.")


def resolve_content(contents: list[Content], ref: str) -> Content:
    found = select_contents(contents, ref)
    if len(found) > 1:
        listed = ", ".join(f"{c.ref}: {c.title}" for c in found[:5])
        raise Ambiguous(f"'{ref}' matches several items: {listed}")
    return found[0]
