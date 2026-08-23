from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from .errors import ParseError
from .models import Content, Course, StudentInfo, Theme

CALENDAR_PREFIX = "/student/my-course/calendar/"

# The LMS splits these by delivery mode (distance vs in-person); both fold into
# one kind.
_ITEM_BUCKETS: tuple[tuple[str, str], ...] = (
    ("subjectFiles", "file"),
    ("distanceFiles", "file"),
    ("videos", "video"),
    ("distanceVideos", "video"),
    ("subjectLinks", "link"),
    ("distanceLinks", "link"),
)

_URL_KEYS = ("url", "file_url", "download_url", "link", "href", "resource_url", "path")

# Files carry a storage path in "file" that is not served publicly (it 404s).
# Downloads go through this route instead, keyed by bucket name and record id.
FILE_DOWNLOAD_ROUTE = "/student/my-course/calendar/resource/file-download/"


def parse_courses(html: str) -> list[Course]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(f"a.my-course__card, a[href*='{CALENDAR_PREFIX}']")
    if not cards:
        raise ParseError("No course cards found on /student/my-courses")

    semester = _selected_semester(soup)
    courses: list[Course] = []
    seen: set[str] = set()
    for card in cards:
        course = _parse_course_card(card, semester)
        if course is None or course.slug in seen:
            continue
        seen.add(course.slug)
        courses.append(course)
    return courses


def _selected_semester(soup: BeautifulSoup) -> str | None:
    option = soup.select_one("select.js-semester option[selected]") or soup.select_one(
        "select.js-semester option"
    )
    if option is None:
        return None
    return " ".join(option.get_text(strip=True).split()) or None


def _parse_course_card(card: Tag, semester: str | None) -> Course | None:
    href = card.get("href") or ""
    if not href:
        return None
    path = urlparse(href).path if href.startswith("http") else href

    match = re.search(rf"{re.escape(CALENDAR_PREFIX)}([^/?#]+)", path)
    if not match:
        return None
    slug = match.group(1)

    title = card.select_one("h5.my-course__card-title")
    if title is not None:
        for child in title.select("object, span"):
            child.decompose()
        name = title.get_text(strip=True)
    else:
        name = " ".join(card.get_text(" ", strip=True).split())
    if not name:
        name = slug

    lecture, tutorial = _parse_teachers(card)
    return Course(
        name=name,
        slug=slug,
        url=f"{CALENDAR_PREFIX}{slug}",
        lecture_teacher=lecture,
        tutorial_teacher=tutorial,
        semester=semester,
    )


def _parse_teachers(card: Tag) -> tuple[str | None, str | None]:
    lecture = tutorial = None
    for row in card.select("div.my-course__card-content div.flex.items-center"):
        badge = row.select_one("span.bg-info")
        if badge is None:
            continue
        label = badge.get_text(strip=True).lower()
        badge.decompose()
        who = " ".join(row.get_text(" ", strip=True).split())
        if not who:
            continue
        if "lecture" in label:
            lecture = who
        elif "tutorial" in label:
            tutorial = who
    return lecture, tutorial


def slug_to_data_path(slug: str) -> str:
    slug = slug.strip()
    marker = CALENDAR_PREFIX.strip("/")
    if marker in slug:
        slug = slug.split(marker, 1)[1]
    slug = slug.strip("/")
    if slug.startswith("data/"):
        slug = slug[len("data/") :]
    return f"{CALENDAR_PREFIX}data/{slug.strip('/')}"


def extract_types(payload: Any) -> dict[str, list[Any]]:
    if not isinstance(payload, dict):
        raise ParseError("Calendar endpoint did not return a JSON object")
    if payload.get("success") is False:
        raise ParseError(str(payload.get("message") or "Calendar request rejected by LMS"))

    for candidate in (payload.get("types"), (payload.get("data") or {}).get("types")):
        if isinstance(candidate, dict):
            return {k: v for k, v in candidate.items() if isinstance(v, list)}

    direct = {k: v for k, v in payload.items() if isinstance(v, list)}
    if direct:
        return direct
    raise ParseError("No content sections found in calendar payload")


def parse_calendar(payload: Any) -> list[Theme]:
    themes: list[Theme] = []
    content_counter = 0

    for section, items in extract_types(payload).items():
        position = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            position += 1
            theme = Theme(
                index=len(themes) + 1,
                position=position,
                section=section,
                title=_clean(item.get("theme")) or f"{section.title()} {position}",
                number=_clean(item.get("number")),
                date=_clean(item.get("date_format")),
            )
            for entry, bucket, kind in _iter_materials(item):
                content_counter += 1
                theme.contents.append(
                    _build_content(
                        entry,
                        bucket=bucket,
                        kind=kind,
                        section=section,
                        index=content_counter,
                        position=len(theme.contents) + 1,
                        theme_index=theme.index,
                        theme_title=theme.title,
                    )
                )
            themes.append(theme)

    return themes


def _iter_materials(item: dict[str, Any]):
    for key, kind in _ITEM_BUCKETS:
        for entry in item.get(key) or []:
            if isinstance(entry, dict):
                yield entry, key, kind


def _build_content(
    entry: dict[str, Any],
    bucket: str,
    kind: str,
    section: str,
    index: int,
    position: int,
    theme_index: int,
    theme_title: str,
) -> Content:
    title = _clean(entry.get("title")) or f"Untitled {kind}"
    extension = _clean(entry.get("file_extension"))
    lms_id = entry.get("id")
    return Content(
        index=index,
        position=position,
        theme_index=theme_index,
        section=section,
        kind=kind,
        title=title,
        theme_title=theme_title,
        description=_clean(entry.get("description")),
        url=_material_url(entry, bucket, kind, lms_id),
        file_name=f"{title}.{extension}" if extension and kind != "link" else None,
        lms_id=str(lms_id) if lms_id is not None else None,
    )


def _material_url(entry: dict[str, Any], bucket: str, kind: str, lms_id: Any) -> str | None:
    if kind != "link" and lms_id is not None:
        return f"{FILE_DOWNLOAD_ROUTE}{bucket}-{lms_id}"
    return _pick_url(entry)


def _pick_url(entry: dict[str, Any]) -> str | None:
    """Links carry their target inline, but under no consistent key."""
    for key in _URL_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_student_info(html: str) -> StudentInfo:
    """Read the profile page. Every field is optional: a missing one must not
    cost the caller the whole profile."""
    soup = BeautifulSoup(html, "html.parser")
    profile = soup.select_one("div.profile") or soup

    name_el = profile.select_one("p.font-18.font-weight-bold")
    return StudentInfo(
        full_name=name_el.get_text(strip=True) if name_el else None,
        student_number=_labelled(profile, "Student number:"),
        group_name=_labelled(profile, "Group:"),
        specialization=_labelled(profile, "Specialization"),
        study_language=_labelled(profile, "Study language:"),
        degree=_labelled(profile, "Degree:"),
        email=_labelled(profile, "E-mail:"),
    )


def _labelled(container: Any, label: str) -> str | None:
    """Match on the label prefix only. The LMS is inconsistent about the space
    before the colon (`Specialization :` but `Degree:`)."""
    prefix = label.rstrip(" :").lower()
    for node in container.select("p.profile__sidebar-info, p, li, td"):
        text = " ".join(node.get_text(" ", strip=True).split())
        if text.lower().startswith(prefix):
            value = text[len(prefix) :].strip(" :\t")
            if value:
                return value
    return None


def _clean(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None
