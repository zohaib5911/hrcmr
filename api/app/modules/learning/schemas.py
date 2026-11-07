"""Course content, assignments, progress and quiz shapes (plan 6.9 and 8.14).

Learners never receive a correct answer until they have submitted the check; the editor is the only
place the answers are shown.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.core.schemas import RequestModel

Line120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Line160 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Line200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Line240 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Para400 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
Para600 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
Body4000 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Slug = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", min_length=3, max_length=80)
]
HttpsUrl = Annotated[
    str, StringConstraints(pattern=r"^https://[^\s]+$", min_length=12, max_length=1000)
]


class SectionIn(RequestModel):
    title: Line120
    body: Body4000
    key_points: list[Line240] = Field(default_factory=list, max_length=6)


class QuestionIn(RequestModel):
    prompt: Para400
    options: list[Line240] = Field(min_length=2, max_length=5)
    answer: int = Field(ge=0, le=4)
    explanation: Para600

    @model_validator(mode="after")
    def answer_is_one_of_the_options(self) -> Self:
        if self.answer >= len(self.options):
            raise ValueError("The correct answer must be one of the options.")
        return self


class QuizIn(RequestModel):
    questions: list[QuestionIn] = Field(min_length=1, max_length=10)


class CourseIn(RequestModel):
    slug: Slug
    title: Line160
    summary: Para400
    duration_minutes: int = Field(ge=5, le=120)
    audience: Literal["all_staff", "managers"]
    sections: list[SectionIn] = Field(min_length=3, max_length=8)
    quiz: QuizIn
    pass_mark: int = Field(ge=1, le=100)
    source_title: Line200
    source_publisher: Line120
    source_url: HttpsUrl
    source_updated_on: date
    content_reviewed_on: date
    licence_note: Para400 | None = None
    published: bool = False


class SectionOut(BaseModel):
    title: str
    body: str
    key_points: list[str]


class QuestionAdminOut(BaseModel):
    prompt: str
    options: list[str]
    answer: int
    explanation: str


class QuestionOut(BaseModel):
    """What a learner sees: the question and its options, never the answer."""

    prompt: str
    options: list[str]


class CourseAdminOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    summary: str
    duration_minutes: int
    audience: str
    sections: list[SectionOut]
    questions: list[QuestionAdminOut]
    pass_mark: int
    source_title: str
    source_publisher: str
    source_url: str
    source_updated_on: date
    content_reviewed_on: date
    licence_note: str | None
    published: bool
    version: int


class CourseOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    summary: str
    duration_minutes: int
    audience: str
    sections: list[SectionOut]
    questions: list[QuestionOut]
    pass_mark: int
    source_title: str
    source_publisher: str
    source_url: str
    source_updated_on: date
    content_reviewed_on: date
    licence_note: str | None
    version: int


class CourseCardOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    summary: str
    duration_minutes: int
    audience: str
    section_count: int
    question_count: int
    source_title: str
    content_reviewed_on: date


class CourseAssignmentIn(RequestModel):
    course_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    # everyone: all current staff; departments: staff in these departments; named: these people.
    scope: Literal["everyone", "departments", "named"] = "named"
    department_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    employee_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    due_on: date


class AssignmentCreatedOut(BaseModel):
    created: int
    already_assigned: int


class ProgressIn(RequestModel):
    section: int = Field(ge=0, le=7)


class CourseAssignmentOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    slug: str
    title: str
    summary: str
    duration_minutes: int
    section_count: int
    question_count: int
    pass_mark: int
    due_on: date
    status: str
    section: int
    quiz_score: int | None
    passed: bool
    completed_at: datetime | None


class AssignmentDetailOut(BaseModel):
    assignment: CourseAssignmentOut
    course: CourseOut


class QuizAnswersIn(RequestModel):
    answers: list[int] = Field(min_length=1, max_length=10)


class QuestionResultOut(BaseModel):
    correct: bool
    correct_option: int
    explanation: str


class QuizResultOut(BaseModel):
    score: int
    passed: bool
    pass_mark: int
    best_score: int
    results: list[QuestionResultOut]


class ReportRowOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    employee_id: uuid.UUID
    employee_name: str
    department: str | None
    due_on: date
    status: str
    quiz_score: int | None
    completed_at: datetime | None


class ReportPageOut(BaseModel):
    items: list[ReportRowOut]
    total: int


class LearningSummaryOut(BaseModel):
    assignments: int
    not_started: int
    in_progress: int
    completed: int
    overdue: int
