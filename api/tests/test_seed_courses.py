"""T13.2: the eight launch courses are complete, cited to an official source and reviewed.

These are file checks against the same schema the editor and the loader use. They do not need the
database, so they run in every test run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.modules.learning.loader import _read_courses
from app.modules.learning.schemas import CourseIn

SEED = Path(__file__).resolve().parents[1] / "seed" / "courses"
OFFICIAL = (
    "https://www.gov.uk/",
    "https://www.acas.org.uk/",
    "https://www.equalityhumanrights.com/",
)
LAUNCH = {
    "employment-rights-essentials",
    "employment-status",
    "equality-and-discrimination-at-work",
    "preventing-sexual-harassment-employer-duty",
    "bullying-and-harassment-at-work",
    "agency-workers-rights",
    "inclusive-recruitment-writing-the-role",
    "inclusive-recruitment-attracting-candidates",
}


def _courses() -> list[CourseIn]:
    return _read_courses(SEED)


def test_there_are_exactly_the_eight_launch_courses() -> None:
    courses = _courses()
    assert {course.slug for course in courses} == LAUNCH
    assert len(courses) == 8


def test_every_course_has_at_least_five_sections_and_exactly_five_questions() -> None:
    for course in _courses():
        assert len(course.sections) >= 5, course.slug
        assert len(course.quiz.questions) == 5, course.slug


def test_every_course_cites_an_official_source_url() -> None:
    for course in _courses():
        assert course.source_url.startswith(OFFICIAL), course.slug


def test_every_course_has_a_source_date_and_a_review_date_that_is_not_in_the_future() -> None:
    today = datetime.now(UTC).date()
    for course in _courses():
        assert course.source_updated_on <= course.content_reviewed_on, course.slug
        assert course.content_reviewed_on <= today, course.slug


def test_durations_are_in_the_planned_range() -> None:
    for course in _courses():
        assert 15 <= course.duration_minutes <= 25, course.slug
