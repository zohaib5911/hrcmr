"""Live search for the command palette: people and candidates the caller may read (T14.3).

Each group is returned only to a person who may read that data for the whole company, and only
inside their own company (the tenant session filters every query). A search needs at least two
characters, and each group is capped at eight results.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.core.rbac_matrix import Scope, scope_for
from app.modules.employees.models import Employee
from app.modules.rbac.deps import Access, require
from app.modules.recruitment.models import Candidate

router = APIRouter(tags=["search"])
Searcher = Annotated[Access, Depends(require("company.overview.read"))]
LIMIT = 8
CURRENT = ("active", "on_leave")


class PersonHitOut(BaseModel):
    id: str
    name: str
    employee_number: str
    link: str


class CandidateHitOut(BaseModel):
    id: str
    name: str
    link: str


class SearchOut(BaseModel):
    people: list[PersonHitOut]
    candidates: list[CandidateHitOut]


def _company_wide(role: str, permission: str) -> bool:
    return scope_for(role, permission) is Scope.ALL


@router.get("/search", response_model=SearchOut)
async def search(access: Searcher, q: Annotated[str, Query(max_length=100)] = "") -> SearchOut:
    needle = " ".join(q.split()).lower()
    if len(needle) < 2:
        return SearchOut(people=[], candidates=[])
    people: list[PersonHitOut] = []
    if _company_wide(access.role, "employee.profile.read"):
        full_name = func.lower(Employee.first_name + " " + Employee.last_name)
        rows = (
            await access.db.execute(
                select(
                    Employee.id, Employee.first_name, Employee.last_name, Employee.employee_number
                )
                .where(
                    Employee.company_id == access.company_id,
                    Employee.status.in_(CURRENT),
                    or_(
                        full_name.contains(needle, autoescape=True),
                        func.lower(Employee.employee_number).contains(needle, autoescape=True),
                    ),
                )
                .order_by(Employee.last_name, Employee.first_name)
                .limit(LIMIT)
            )
        ).all()
        people = [
            PersonHitOut(
                id=str(ident),
                name=f"{first} {last}".strip(),
                employee_number=number,
                link=f"/employees/{ident}",
            )
            for ident, first, last, number in rows
        ]
    candidates: list[CandidateHitOut] = []
    if _company_wide(access.role, "recruitment.candidate.read"):
        candidate_name = func.lower(Candidate.first_name + " " + Candidate.last_name)
        candidate_rows = (
            await access.db.execute(
                select(Candidate.id, Candidate.first_name, Candidate.last_name)
                .where(
                    Candidate.company_id == access.company_id,
                    candidate_name.contains(needle, autoescape=True),
                )
                .order_by(Candidate.last_name, Candidate.first_name)
                .limit(LIMIT)
            )
        ).all()
        candidates = [
            CandidateHitOut(
                id=str(ident),
                name=f"{first} {last}".strip(),
                link=f"/recruitment/candidates/{ident}",
            )
            for ident, first, last in candidate_rows
        ]
    return SearchOut(people=people, candidates=candidates)
