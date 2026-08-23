from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Kind = Literal["file", "link", "video"]


@dataclass(slots=True)
class Course:
    name: str
    slug: str
    url: str
    lecture_teacher: str | None = None
    tutorial_teacher: str | None = None
    semester: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Content:
    index: int
    position: int
    theme_index: int
    section: str
    kind: Kind
    title: str
    theme_title: str | None = None
    description: str | None = None
    url: str | None = None
    file_name: str | None = None
    lms_id: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.theme_index}.{self.position}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ref"] = self.ref
        return data


@dataclass(slots=True)
class Theme:
    index: int
    position: int
    section: str
    title: str
    number: str | None = None
    date: str | None = None
    contents: list[Content] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.number}. {self.title}" if self.number else self.title

    def to_dict(self, include_contents: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "index": self.index,
            "position": self.position,
            "section": self.section,
            "number": self.number,
            "date": self.date,
            "title": self.title,
            "label": self.label,
            "content_count": len(self.contents),
        }
        if include_contents:
            data["contents"] = [c.to_dict() for c in self.contents]
        return data


@dataclass(slots=True)
class CourseDetail:
    course: Course
    themes: list[Theme] = field(default_factory=list)

    @property
    def contents(self) -> list[Content]:
        return [content for theme in self.themes for content in theme.contents]

    @property
    def sections(self) -> list[str]:
        seen: list[str] = []
        for theme in self.themes:
            if theme.section not in seen:
                seen.append(theme.section)
        return seen

    def summary(self) -> list[dict[str, Any]]:
        rows = []
        for section in self.sections:
            themes = [t for t in self.themes if t.section == section]
            rows.append(
                {
                    "section": section,
                    "themes": len(themes),
                    "contents": sum(len(t.contents) for t in themes),
                }
            )
        return rows

    def to_dict(self, include_contents: bool = True) -> dict[str, Any]:
        return {
            "course": self.course.to_dict(),
            "sections": self.summary(),
            "themes": [t.to_dict(include_contents) for t in self.themes],
        }


@dataclass(slots=True)
class StudentInfo:
    full_name: str | None = None
    student_number: str | None = None
    group_name: str | None = None
    specialization: str | None = None
    study_language: str | None = None
    degree: str | None = None
    email: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
