from __future__ import annotations

import json
from typing import Any

import pytest

from tmci.cache import Cache
from tmci.errors import SessionExpired
from tmci.models import Course
from tmci.service import LmsService

MY_COURSES_HTML = """
<html><body>
<select class="js-semester">
  <option value="1">2025-2026 Autumn</option>
  <option value="2" selected>2025-2026 Spring</option>
</select>
<a class="my-course__card" href="/student/my-course/calendar/31-21-en">
  <h5 class="my-course__card-title">Data Structures<span class="badge">new</span></h5>
  <div class="my-course__card-content">
    <div class="flex items-center"><span class="bg-info">Lecture</span>Prof. A. Karimov</div>
    <div class="flex items-center"><span class="bg-info">Tutorial</span>M. Yusupova</div>
  </div>
</a>
<a class="my-course__card" href="https://lms.tmci.uz/student/my-course/calendar/32-21-en">
  <h5 class="my-course__card-title">Operating Systems</h5>
</a>
</body></html>
"""

STUDENT_INFO_HTML = """
<html><body><div class="profile">
  <p class="font-18 font-weight-bold">Ali Valiyev</p>
  <p class="profile__sidebar-info">Student number: 21-0031</p>
  <p class="profile__sidebar-info">Group: 31-21-en</p>
  <p class="profile__sidebar-info">Specialization : Computer Science</p>
  <p class="profile__sidebar-info">Degree: Bachelor</p>
  <p class="profile__sidebar-info">E-mail: ali@example.uz</p>
</div></body></html>
"""

# Shaped after a real /student/my-course/calendar/data response: "number" is an
# int, files carry an unserved storage path in "file" rather than a URL, and the
# snake_case duplicates of each bucket are present but ignored.
CALENDAR_PAYLOAD: dict[str, Any] = {
    "success": True,
    "types": {
        "lecture": [
            {
                "id": 99046,
                "number": 1,
                "theme": "Arrays and lists",
                "date_format": "02-02-2026",
                "subjectFiles": [
                    {
                        "id": 101,
                        "title": "Week 1 slides",
                        "file_extension": "pdf",
                        "file": "subject-files/101/abc.pdf",
                        "size_format": "1.2 MB",
                    }
                ],
                "subject_files": [{"id": 101, "title": "Week 1 slides"}],
                "subjectLinks": [
                    {"id": 55, "title": "Reading", "link": "https://example.org/reading"}
                ],
            },
            {
                "id": 99047,
                "number": 2,
                "theme": "Linked lists",
                "date_format": "09-02-2026",
                "subjectFiles": [
                    {
                        "id": 102,
                        "title": "Week 2 slides",
                        "file_extension": "pdf",
                        "file": "subject-files/102/def.pdf",
                    }
                ],
            },
        ],
        "tutorial": [
            {
                "id": 99048,
                "number": 1,
                "theme": "Lab 1",
                "date_format": "03-02-2026",
                "distanceFiles": [
                    {
                        "id": 202,
                        "title": "Lab handout",
                        "file_extension": "docx",
                        "file": "distance-files/202/ghi.docx",
                    }
                ],
                # No id, so no download route can be built for it.
                "videos": [{"title": "Walkthrough", "file_extension": "mp4"}],
            }
        ],
    },
}


class FakeResponse:
    def __init__(self, content: bytes, headers: dict[str, str] | None = None) -> None:
        self.content = content
        self.headers = headers or {}


class FakeClient:
    """Stands in for Client so service tests never touch the network."""

    base_url = "https://lms.tmci.uz"

    def __init__(
        self,
        html: dict[str, str] | None = None,
        payloads: dict[str, Any] | None = None,
        files: dict[str, FakeResponse] | None = None,
    ) -> None:
        self.html = html or {
            "/student/my-courses": MY_COURSES_HTML,
            "/student/info": STUDENT_INFO_HTML,
        }
        self.payloads = payloads or {
            "/student/my-course/calendar/data/31-21-en": CALENDAR_PAYLOAD,
            "/student/my-course/calendar/data/32-21-en": {"types": {}},
        }
        self.files = files or {}
        self.calls: list[str] = []
        self.expired = False

    def get_html(self, path: str) -> str:
        self.calls.append(path)
        if self.expired:
            raise SessionExpired
        return self.html[path]

    def get_json(self, path: str) -> Any:
        self.calls.append(path)
        if self.expired:
            raise SessionExpired
        return json.loads(json.dumps(self.payloads[path]))

    def fetch_file(self, url: str, referer: str | None = None) -> FakeResponse:
        self.calls.append(url)
        return self.files.get(url, FakeResponse(b"file-bytes"))

    def close(self) -> None:
        pass


@pytest.fixture
def tmci_home(tmp_path, monkeypatch):
    monkeypatch.setenv("TMCI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture
def service(fake_client, tmci_home):
    return LmsService(fake_client, Cache(root=tmci_home / "cache", ttl_seconds=0))


@pytest.fixture
def cached_service(fake_client, tmci_home):
    cache_root = tmci_home / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    return LmsService(fake_client, Cache(root=cache_root, ttl_seconds=600))


@pytest.fixture
def course():
    return Course(name="Data Structures", slug="31-21-en", url="/x")
