from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from .cache import Cache
from .client import Client
from .errors import TmciError
from .models import Content, Course, CourseDetail, StudentInfo, Theme
from .parsers import (
    CALENDAR_PREFIX,
    parse_calendar,
    parse_courses,
    parse_student_info,
    slug_to_data_path,
)
from .refs import resolve_content, resolve_course, resolve_theme, select_contents

COURSES_PATH = "/student/my-courses"
STUDENT_INFO_PATH = "/student/info"

# Windows rejects paths past 260 characters unless long-path support is on, and
# reports it as a bare FileNotFoundError.
MAX_PATH_CHARS = 240
THEME_DIR_CHARS = 80
MIN_NAME_CHARS = 12

_ILLEGAL_FILENAME_CHARS = re.compile('[\\\\/:*?"<>|\x00-\x1f]')


class LmsService:
    """Everything the commands are allowed to know about the LMS: they go
    through here rather than touching httpx or BeautifulSoup."""

    def __init__(self, client: Client, cache: Cache | None = None) -> None:
        self.client = client
        self.cache = cache or Cache(ttl_seconds=0)

    def student(self) -> StudentInfo:
        return parse_student_info(self.client.get_html(STUDENT_INFO_PATH))

    def courses(self) -> list[Course]:
        cached = self.cache.get("courses")
        if cached is None:
            html = self.client.get_html(COURSES_PATH)
            courses = parse_courses(html)
            self.cache.set("courses", [c.to_dict() for c in courses])
            return courses
        return [Course(**row) for row in cached]

    def course(self, ref: str) -> Course:
        return resolve_course(self.courses(), ref)

    def raw_calendar(self, course: Course) -> Any:
        key = f"calendar:{course.slug}"
        cached = self.cache.get(key)
        if cached is None:
            cached = self.client.get_json(slug_to_data_path(course.slug))
            self.cache.set(key, cached)
        return cached

    def themes(self, course: Course) -> list[Theme]:
        return parse_calendar(self.raw_calendar(course))

    def detail(self, ref: str) -> CourseDetail:
        course = self.course(ref)
        return CourseDetail(course=course, themes=self.themes(course))

    def theme(self, detail: CourseDetail, ref: str) -> Theme:
        return resolve_theme(detail.themes, ref)

    def content(self, detail: CourseDetail, ref: str) -> Content:
        return resolve_content(detail.contents, ref)

    def filter_contents(
        self,
        detail: CourseDetail,
        theme: str | None = None,
        section: str | None = None,
        kind: str | None = None,
        refs: list[str] | None = None,
    ) -> list[Content]:
        themes = detail.themes
        if section:
            needle = section.strip().lower()
            themes = [t for t in themes if needle in t.section.lower()]
        if theme:
            themes = [resolve_theme(themes, theme)]

        contents = [c for t in themes for c in t.contents]
        if kind:
            wanted = kind.strip().lower()
            contents = [c for c in contents if c.kind == wanted]

        if not refs:
            return contents

        picked: list[Content] = []
        for ref in refs:
            for content in select_contents(contents, ref):
                if content not in picked:
                    picked.append(content)
        return picked

    def download(self, course: Course, content: Content, dest_root: Path) -> Path:
        if not content.url:
            raise TmciError(f"'{content.title}' has no download URL in the LMS data.")
        if content.kind == "link":
            raise TmciError(f"'{content.title}' is a link, not a file: {content.url}")

        absolute = self.absolute_url(content.url)
        referer = urljoin(self.client.base_url + "/", f"{CALENDAR_PREFIX.strip('/')}/{course.slug}")
        response = self.client.fetch_file(absolute, referer=referer)

        target_dir = dest_root / _safe_filename(course.slug) / _safe_filename(content.section)
        target_dir = target_dir / _theme_dirname(content)

        name = _resolve_filename(response.headers, content, absolute)
        path = _fit_path_limit(target_dir, f"{content.position:02d} {name}")

        target_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        return path

    def absolute_url(self, url: str) -> str:
        if url.startswith(("http://", "https://")):
            return url
        return urljoin(self.client.base_url + "/", url.lstrip("/"))


def _theme_dirname(content: Content) -> str:
    return _safe_filename(
        f"{content.theme_index:02d} {content.theme_title or content.section}", THEME_DIR_CHARS
    )


def _fit_path_limit(directory: Path, name: str) -> Path:
    """Shorten the file name, never the directory, to fit the Windows path limit."""
    budget = MAX_PATH_CHARS - len(str(directory)) - 1
    if budget < MIN_NAME_CHARS:
        raise TmciError(
            f"Download path is too long ({len(str(directory))} chars): {directory}\n"
            "Pass --out with a shorter directory."
        )
    return directory / _truncate(name, budget)


def _truncate(name: str, limit: int) -> str:
    """Trim from the stem, never the extension, or the file stops opening."""
    if len(name) <= limit:
        return name
    stem, dot, extension = name.rpartition(".")
    if dot and 0 < len(extension) <= 8 and limit > len(extension) + 1:
        return f"{stem[: limit - len(extension) - 1]}.{extension}"
    return name[:limit]


def _resolve_filename(headers: Any, content: Content, url: str) -> str:
    # The LMS puts its opaque storage name in content-disposition
    # (XbpEKjAp....zip), so the title it shows students wins over the header.
    if content.file_name:
        return _safe_filename(content.file_name)

    from_header = _filename_from_disposition(headers.get("content-disposition"))
    if from_header:
        return _safe_filename(from_header)

    extension = Path(urlparse(url).path).suffix
    if not extension:
        mime = (headers.get("content-type") or "").split(";")[0].strip()
        extension = mimetypes.guess_extension(mime) or ""
    return _safe_filename(f"{content.title}{extension}")


def _filename_from_disposition(value: str | None) -> str | None:
    if not value:
        return None
    encoded = re.search(r"filename\*\s*=\s*(?:[\w-]+'')?([^;]+)", value, re.IGNORECASE)
    if encoded:
        return unquote(encoded.group(1).strip().strip('"')) or None
    plain = re.search(r'filename\s*=\s*("?)([^";]+)\1', value, re.IGNORECASE)
    if plain:
        return plain.group(2).strip() or None
    return None


def _safe_filename(name: str, limit: int = 150) -> str:
    cleaned = _ILLEGAL_FILENAME_CHARS.sub("-", name).strip().strip(".")
    return _truncate(cleaned, limit) if cleaned else "download"
