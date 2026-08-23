from __future__ import annotations

import pytest
from conftest import CALENDAR_PAYLOAD, MY_COURSES_HTML, STUDENT_INFO_HTML

from tmci.errors import ParseError
from tmci.parsers import (
    extract_types,
    parse_calendar,
    parse_courses,
    parse_student_info,
    slug_to_data_path,
)


def test_parse_courses_extracts_slug_name_and_teachers():
    courses = parse_courses(MY_COURSES_HTML)

    assert [c.slug for c in courses] == ["31-21-en", "32-21-en"]
    first = courses[0]
    assert first.name == "Data Structures"
    assert first.lecture_teacher == "Prof. A. Karimov"
    assert first.tutorial_teacher == "M. Yusupova"
    assert first.url == "/student/my-course/calendar/31-21-en"


def test_parse_courses_prefers_the_selected_semester():
    assert parse_courses(MY_COURSES_HTML)[0].semester == "2025-2026 Spring"


def test_parse_courses_handles_absolute_hrefs():
    assert parse_courses(MY_COURSES_HTML)[1].name == "Operating Systems"


def test_parse_courses_deduplicates_repeated_slugs():
    html = MY_COURSES_HTML.replace(
        "</body>",
        """
    <a class="my-course__card" href="/student/my-course/calendar/31-21-en">
      <h5 class="my-course__card-title">Data Structures again</h5>
    </a></body>""",
    )
    assert len(parse_courses(html)) == 2


def test_parse_courses_raises_when_markup_changes():
    with pytest.raises(ParseError):
        parse_courses("<html><body><p>nothing here</p></body></html>")


@pytest.mark.parametrize(
    "given",
    [
        "31-21-en",
        "/student/my-course/calendar/31-21-en",
        "/student/my-course/calendar/data/31-21-en",
        "https://lms.tmci.uz/student/my-course/calendar/31-21-en/",
    ],
)
def test_slug_to_data_path_is_idempotent(given):
    assert slug_to_data_path(given) == "/student/my-course/calendar/data/31-21-en"


def test_parse_calendar_returns_themes():
    themes = parse_calendar(CALENDAR_PAYLOAD)

    assert [t.title for t in themes] == ["Arrays and lists", "Linked lists", "Lab 1"]
    assert [t.section for t in themes] == ["lecture", "lecture", "tutorial"]


def test_themes_are_indexed_course_wide_and_positioned_per_section():
    themes = parse_calendar(CALENDAR_PAYLOAD)

    assert [t.index for t in themes] == [1, 2, 3]
    assert [t.position for t in themes] == [1, 2, 1]


def test_theme_label_includes_the_lms_number():
    assert parse_calendar(CALENDAR_PAYLOAD)[0].label == "1. Arrays and lists"


def test_contents_hang_off_their_theme():
    themes = parse_calendar(CALENDAR_PAYLOAD)

    assert [c.title for c in themes[0].contents] == ["Week 1 slides", "Reading"]
    assert [c.title for c in themes[2].contents] == ["Lab handout", "Walkthrough"]


def test_content_kinds_fold_distance_and_in_person_buckets():
    themes = parse_calendar(CALENDAR_PAYLOAD)

    assert [c.kind for c in themes[0].contents] == ["file", "link"]
    assert [c.kind for c in themes[2].contents] == ["file", "video"]


def test_content_refs_are_theme_dot_position():
    themes = parse_calendar(CALENDAR_PAYLOAD)
    assert [c.ref for c in themes[2].contents] == ["3.1", "3.2"]


def test_content_index_is_continuous_across_themes():
    themes = parse_calendar(CALENDAR_PAYLOAD)
    indexes = [c.index for t in themes for c in t.contents]
    assert indexes == [1, 2, 3, 4, 5]


def test_files_get_a_name_and_links_do_not():
    contents = parse_calendar(CALENDAR_PAYLOAD)[0].contents

    assert contents[0].file_name == "Week 1 slides.pdf"
    assert contents[1].file_name is None


def test_files_download_through_the_route_not_the_storage_path():
    themes = parse_calendar(CALENDAR_PAYLOAD)

    # The payload's "file" key is a storage path that 404s; the bucket name and
    # record id build the served route instead.
    assert themes[0].contents[0].url == (
        "/student/my-course/calendar/resource/file-download/subjectFiles-101"
    )
    assert themes[2].contents[0].url == (
        "/student/my-course/calendar/resource/file-download/distanceFiles-202"
    )


def test_links_keep_their_inline_target():
    assert parse_calendar(CALENDAR_PAYLOAD)[0].contents[1].url == "https://example.org/reading"


def test_a_file_without_an_id_has_no_url():
    assert parse_calendar(CALENDAR_PAYLOAD)[2].contents[1].url is None


def test_integer_theme_numbers_are_kept():
    themes = parse_calendar(CALENDAR_PAYLOAD)

    assert themes[0].number == "1"
    assert themes[0].label == "1. Arrays and lists"


def test_theme_carries_its_lesson_date():
    assert parse_calendar(CALENDAR_PAYLOAD)[0].date == "02-02-2026"


def test_snake_case_bucket_duplicates_are_ignored():
    # The LMS repeats every bucket in snake_case; reading both would double
    # every file.
    assert len(parse_calendar(CALENDAR_PAYLOAD)[0].contents) == 2


def test_untitled_theme_gets_a_positional_fallback():
    payload = {"types": {"lecture": [{"subjectFiles": [{"id": 1, "title": "a"}]}]}}
    assert parse_calendar(payload)[0].title == "Lecture 1"


def test_theme_with_no_materials_is_kept():
    payload = {"types": {"lecture": [{"number": "1", "theme": "Intro"}]}}
    themes = parse_calendar(payload)

    assert len(themes) == 1
    assert themes[0].contents == []


def test_malformed_entries_are_skipped():
    payload = {"types": {"lecture": ["not a dict", {"subjectFiles": ["also not a dict"]}]}}
    themes = parse_calendar(payload)

    assert len(themes) == 1
    assert themes[0].contents == []


def test_extract_types_unwraps_a_data_envelope():
    assert extract_types({"data": {"types": {"lecture": []}}}) == {"lecture": []}


def test_extract_types_accepts_a_bare_map():
    assert extract_types({"lecture": [], "tutorial": []}) == {"lecture": [], "tutorial": []}


def test_extract_types_reports_the_lms_error_message():
    with pytest.raises(ParseError, match="Subject not available"):
        extract_types({"success": False, "message": "Subject not available"})


def test_extract_types_rejects_an_unrecognised_payload():
    with pytest.raises(ParseError):
        extract_types({"foo": "bar"})


def test_parse_student_info_reads_the_labelled_fields():
    student = parse_student_info(STUDENT_INFO_HTML)

    assert student.full_name == "Ali Valiyev"
    assert student.student_number == "21-0031"
    assert student.group_name == "31-21-en"
    assert student.degree == "Bachelor"
    assert student.email == "ali@example.uz"


def test_parse_student_info_tolerates_the_inconsistent_colon_spacing():
    assert parse_student_info(STUDENT_INFO_HTML).specialization == "Computer Science"


def test_parse_student_info_never_raises_on_a_sparse_page():
    student = parse_student_info("<html><body><div class='profile'></div></body></html>")

    assert student.full_name is None
    assert student.student_number is None
