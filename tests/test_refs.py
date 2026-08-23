from __future__ import annotations

import pytest

from tmci.errors import Ambiguous, NotFound
from tmci.models import Content, Course, Theme
from tmci.refs import resolve_content, resolve_course, resolve_theme, select_contents

COURSES = [
    Course(name="Data Structures", slug="31-21-en", url="/a"),
    Course(name="Operating Systems", slug="32-21-en", url="/b"),
    Course(name="Data Science", slug="33-21-en", url="/c"),
]


def content(index, position, theme_index, title, section="lecture", lms_id=None):
    return Content(
        index=index,
        position=position,
        theme_index=theme_index,
        section=section,
        kind="file",
        title=title,
        lms_id=lms_id,
    )


THEMES = [
    Theme(
        index=1,
        position=1,
        section="lecture",
        title="Arrays and lists",
        contents=[content(1, 1, 1, "Week 1 slides", lms_id="101")],
    ),
    Theme(
        index=2,
        position=2,
        section="lecture",
        title="Linked lists",
        contents=[content(2, 1, 2, "Week 2 slides", lms_id="102")],
    ),
    Theme(
        index=3,
        position=1,
        section="tutorial",
        title="Lab 1",
        contents=[
            content(3, 1, 3, "Lab handout", section="tutorial", lms_id="203"),
            content(4, 2, 3, "Walkthrough", section="tutorial", lms_id="7"),
        ],
    ),
]

ALL_CONTENTS = [c for t in THEMES for c in t.contents]


def test_course_by_exact_slug():
    assert resolve_course(COURSES, "32-21-en").name == "Operating Systems"


def test_course_slug_is_case_insensitive():
    assert resolve_course(COURSES, "32-21-EN").slug == "32-21-en"


def test_course_by_unique_name_substring():
    assert resolve_course(COURSES, "operating").slug == "32-21-en"


def test_course_ambiguous_substring_lists_candidates():
    with pytest.raises(Ambiguous, match="Data Structures"):
        resolve_course(COURSES, "data")


def test_course_not_found():
    with pytest.raises(NotFound):
        resolve_course(COURSES, "chemistry")


def test_theme_by_index():
    assert resolve_theme(THEMES, "2").title == "Linked lists"


def test_theme_by_section_and_position():
    assert resolve_theme(THEMES, "tutorial:1").title == "Lab 1"


def test_theme_section_prefix_is_case_insensitive():
    assert resolve_theme(THEMES, "Tutorial:1").index == 3


def test_theme_by_title_substring():
    assert resolve_theme(THEMES, "arrays").index == 1


def test_theme_ambiguous_title():
    with pytest.raises(Ambiguous):
        resolve_theme(THEMES, "lists")


def test_theme_unknown_index():
    with pytest.raises(NotFound):
        resolve_theme(THEMES, "99")


def test_theme_unknown_section_position():
    with pytest.raises(NotFound):
        resolve_theme(THEMES, "lecture:9")


def test_content_hierarchical_ref():
    assert resolve_content(ALL_CONTENTS, "3.2").title == "Walkthrough"


def test_content_flat_index():
    assert resolve_content(ALL_CONTENTS, "3").title == "Lab handout"


def test_hierarchical_and_flat_refs_do_not_collide():
    assert resolve_content(ALL_CONTENTS, "3").ref == "3.1"
    assert resolve_content(ALL_CONTENTS, "3.1").index == 3


def test_content_by_lms_id():
    assert resolve_content(ALL_CONTENTS, "203").title == "Lab handout"


def test_flat_index_wins_over_lms_id_when_both_match():
    # Content 4 has lms_id "7"; there is no content index 7, so the id must win.
    assert resolve_content(ALL_CONTENTS, "7").title == "Walkthrough"


def test_content_by_title_substring():
    assert resolve_content(ALL_CONTENTS, "handout").index == 3


def test_select_contents_returns_every_title_match():
    found = select_contents(ALL_CONTENTS, "slides")
    assert [c.index for c in found] == [1, 2]


def test_resolve_content_rejects_ambiguous_title():
    with pytest.raises(Ambiguous):
        resolve_content(ALL_CONTENTS, "slides")


def test_content_unknown_hierarchical_ref():
    with pytest.raises(NotFound):
        select_contents(ALL_CONTENTS, "9.9")


def test_content_not_found():
    with pytest.raises(NotFound):
        select_contents(ALL_CONTENTS, "nothing-like-this")


def test_empty_ref_is_rejected():
    with pytest.raises(NotFound):
        select_contents(ALL_CONTENTS, "   ")


def test_a_bare_number_never_matches_a_title():
    # "0" is a substring of "TW 10"; a numeric ref must not degrade to that.
    numbered = [content(1, 1, 1, "TW 10"), content(2, 1, 2, "TW 20")]

    with pytest.raises(NotFound, match="No content numbered 0"):
        select_contents(numbered, "0")


def test_a_number_missing_from_a_filtered_set_is_an_error_not_a_title_match():
    # Indexes are course-wide, so a filtered list can legitimately lack index 5.
    filtered = [content(7, 1, 3, "Week 5 recap")]

    with pytest.raises(NotFound):
        select_contents(filtered, "5")


def test_numeric_ref_still_finds_an_lms_id_when_no_index_matches():
    items = [content(1, 1, 1, "Slides", lms_id="12393")]

    assert select_contents(items, "12393")[0].title == "Slides"
