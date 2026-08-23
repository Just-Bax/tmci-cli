from __future__ import annotations

import pytest
from conftest import CALENDAR_PAYLOAD, FakeClient, FakeResponse

from tmci.errors import TmciError
from tmci.service import LmsService, _safe_filename


def test_courses_are_parsed(service):
    assert [c.slug for c in service.courses()] == ["31-21-en", "32-21-en"]


def test_course_resolution_uses_the_course_list(service):
    assert service.course("operating").slug == "32-21-en"


def test_detail_groups_contents_under_themes(service):
    detail = service.detail("31-21-en")

    assert [t.title for t in detail.themes] == ["Arrays and lists", "Linked lists", "Lab 1"]
    assert [len(t.contents) for t in detail.themes] == [2, 1, 2]


def test_detail_numbers_contents_course_wide_and_within_theme(service):
    detail = service.detail("31-21-en")

    assert [c.index for c in detail.contents] == [1, 2, 3, 4, 5]
    assert [c.ref for c in detail.contents] == ["1.1", "1.2", "2.1", "3.1", "3.2"]


def test_sections_are_discovered_not_hardcoded(service):
    assert service.detail("31-21-en").sections == ["lecture", "tutorial"]


def test_summary_counts_per_section(service):
    assert service.detail("31-21-en").summary() == [
        {"section": "lecture", "themes": 2, "contents": 3},
        {"section": "tutorial", "themes": 1, "contents": 2},
    ]


def test_filter_by_section(service):
    detail = service.detail("31-21-en")
    found = service.filter_contents(detail, section="tutorial")
    assert [c.title for c in found] == ["Lab handout", "Walkthrough"]


def test_filter_by_theme(service):
    detail = service.detail("31-21-en")
    found = service.filter_contents(detail, theme="2")
    assert [c.title for c in found] == ["Week 2 slides"]


def test_filter_by_kind(service):
    detail = service.detail("31-21-en")
    found = service.filter_contents(detail, kind="link")
    assert [c.title for c in found] == ["Reading"]


def test_filter_by_refs_deduplicates(service):
    detail = service.detail("31-21-en")
    found = service.filter_contents(detail, refs=["1.1", "1", "1.1"])
    assert [c.index for c in found] == [1]


def test_filter_combines_section_and_kind(service):
    detail = service.detail("31-21-en")
    found = service.filter_contents(detail, section="tutorial", kind="video")
    assert [c.title for c in found] == ["Walkthrough"]


def test_untitled_theme_falls_back_to_a_positional_name(fake_client, tmci_home):
    fake_client.payloads["/student/my-course/calendar/data/31-21-en"] = {
        "types": {"lecture": [{"subjectFiles": [{"id": 1, "title": "x"}]}]}
    }
    from tmci.cache import Cache

    service = LmsService(fake_client, Cache(root=tmci_home / "c", ttl_seconds=0))
    assert service.detail("31-21-en").themes[0].title == "Lecture 1"


def test_student_info_is_parsed(service):
    student = service.student()
    assert student.full_name == "Ali Valiyev"
    assert student.student_number == "21-0031"
    assert student.specialization == "Computer Science"


def test_download_nests_by_course_section_and_theme(service, course, tmp_path):
    detail = service.detail("31-21-en")
    content = detail.contents[0]

    path = service.download(course, content, tmp_path)

    assert path.read_bytes() == b"file-bytes"
    relative = path.relative_to(tmp_path).parts
    assert relative[0] == "31-21-en"
    assert relative[1] == "lecture"
    assert relative[2] == "01 Arrays and lists"
    assert relative[3] == "01 Week 1 slides.pdf"


def test_download_numbers_files_within_their_theme(fake_client, tmci_home, course, tmp_path):
    from tmci.cache import Cache

    fake_client.payloads["/student/my-course/calendar/data/31-21-en"] = {
        "types": {
            "lecture": [
                {
                    "number": "1",
                    "theme": "Arrays",
                    "subjectFiles": [
                        {"id": 1, "title": "a", "file_extension": "pdf", "url": "/f/1"},
                        {"id": 2, "title": "b", "file_extension": "pdf", "url": "/f/2"},
                    ],
                }
            ]
        }
    }
    service = LmsService(fake_client, Cache(root=tmci_home / "c", ttl_seconds=0))
    detail = service.detail("31-21-en")

    paths = [service.download(course, c, tmp_path) for c in detail.contents]

    assert [p.name for p in paths] == ["01 a.pdf", "02 b.pdf"]
    assert paths[0].parent == paths[1].parent


def test_download_prefers_the_lms_title_over_content_disposition(course, tmci_home, tmp_path):
    from tmci.cache import Cache

    # The LMS sends its opaque storage name in the header, so the student-facing
    # title has to win or every file lands as a hash.
    route = "https://lms.tmci.uz/student/my-course/calendar/resource/file-download/subjectFiles-101"
    client = FakeClient(
        files={
            route: FakeResponse(b"pdf", {"content-disposition": "attachment; filename=XbpEK9z.pdf"})
        }
    )
    service = LmsService(client, Cache(root=tmci_home / "c", ttl_seconds=0))
    content = service.detail("31-21-en").contents[0]

    assert service.download(course, content, tmp_path).name == "01 Week 1 slides.pdf"


def test_download_falls_back_to_the_header_when_the_title_has_no_extension(
    fake_client, tmci_home, course, tmp_path
):
    from tmci.cache import Cache

    fake_client.payloads["/student/my-course/calendar/data/31-21-en"] = {
        "types": {"lecture": [{"theme": "T", "subjectFiles": [{"id": 5, "title": "notes"}]}]}
    }
    route = "https://lms.tmci.uz/student/my-course/calendar/resource/file-download/subjectFiles-5"
    fake_client.files[route] = FakeResponse(
        b"pdf", {"content-disposition": 'attachment; filename="real.pdf"'}
    )
    service = LmsService(fake_client, Cache(root=tmci_home / "c", ttl_seconds=0))
    content = service.detail("31-21-en").contents[0]

    assert service.download(course, content, tmp_path).name == "01 real.pdf"


def test_download_refuses_a_link(service, course, tmp_path):
    detail = service.detail("31-21-en")
    link = next(c for c in detail.contents if c.kind == "link")

    with pytest.raises(TmciError, match="is a link"):
        service.download(course, link, tmp_path)


def test_download_reports_a_missing_url(service, course, tmp_path):
    detail = service.detail("31-21-en")
    video = next(c for c in detail.contents if c.url is None)

    with pytest.raises(TmciError, match="no download URL"):
        service.download(course, video, tmp_path)


def test_relative_urls_are_made_absolute(service):
    assert service.absolute_url("/f/101") == "https://lms.tmci.uz/f/101"


def test_absolute_urls_are_left_alone(service):
    assert service.absolute_url("https://cdn.example/x") == "https://cdn.example/x"


def test_cache_avoids_a_second_fetch(cached_service, fake_client):
    cached_service.courses()
    cached_service.courses()

    assert fake_client.calls.count("/student/my-courses") == 1


def test_cache_survives_a_new_service_instance(cached_service, fake_client, tmci_home):
    from tmci.cache import Cache

    cached_service.detail("31-21-en")
    before = len(fake_client.calls)

    LmsService(fake_client, Cache(root=tmci_home / "cache", ttl_seconds=600)).detail("31-21-en")

    assert len(fake_client.calls) == before


def test_zero_ttl_always_refetches(service, fake_client):
    service.courses()
    service.courses()

    assert fake_client.calls.count("/student/my-courses") == 2


def test_cached_courses_round_trip_unchanged(cached_service):
    first = cached_service.courses()
    second = cached_service.courses()

    assert [c.to_dict() for c in first] == [c.to_dict() for c in second]


def test_raw_calendar_returns_the_untouched_payload(service):
    assert service.raw_calendar(service.course("31-21-en")) == CALENDAR_PAYLOAD


def test_theme_directory_name_is_sanitised():
    assert _safe_filename("01 Week 1/2: intro") == "01 Week 1-2- intro"


def test_long_names_are_truncated_to_fit_the_windows_path_limit(
    fake_client, tmci_home, course, tmp_path
):
    from tmci.cache import Cache
    from tmci.service import MAX_PATH_CHARS

    fake_client.payloads["/student/my-course/calendar/data/31-21-en"] = {
        "types": {
            "lecture": [
                {
                    "theme": "T" * 200,
                    "subjectFiles": [
                        {"id": 1, "title": "F" * 200, "file_extension": "pdf", "file": "x/1.pdf"}
                    ],
                }
            ]
        }
    }
    service = LmsService(fake_client, Cache(root=tmci_home / "c", ttl_seconds=0))
    content = service.detail("31-21-en").contents[0]

    path = service.download(course, content, tmp_path)

    assert len(str(path)) <= MAX_PATH_CHARS
    assert path.suffix == ".pdf"
    assert path.read_bytes() == b"file-bytes"


def test_an_unusably_deep_destination_is_reported_clearly(service, course, tmp_path):
    detail = service.detail("31-21-en")
    deep = tmp_path / ("d" * 200)

    with pytest.raises(TmciError, match="too long"):
        service.download(course, detail.contents[0], deep)


def test_truncating_a_long_name_keeps_the_extension():
    long_name = "F" * 200 + ".pdf"

    assert _safe_filename(long_name).endswith(".pdf")


def test_truncating_leaves_an_extensionless_theme_name_alone():
    assert _safe_filename("T" * 200, 80) == "T" * 80
