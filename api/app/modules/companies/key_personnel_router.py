"""Key personnel (plan.md 8.15): the Authorising Officer, Key Contact and Level 1 and 2 Users.

Their identity documents go through the same upload checks as every file, and are shown only to the
people who manage the company, by a link that works for 60 seconds.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy import select, update

from app.core.errors import AppError, ConflictError, NotFoundError
from app.integrations.storage import PRESIGN_SECONDS
from app.modules.companies.key_personnel_schemas import (
    KeyPersonIn,
    KeyPersonnel,
    KeyPersonOut,
    KeyPersonPatch,
    ProofLink,
)
from app.modules.companies.models import KeyPerson
from app.modules.files.models import File
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.modules.files.service import FileService

router = APIRouter(tags=["company"])

Reads = Annotated[Access, Depends(require("company.profile.read"))]
Writes = Annotated[Access, Depends(require("company.profile.write"))]

PROOF_KINDS = frozenset({"pdf", "jpg", "png"})
PROOF_MAX_BYTES = 10 * 1024 * 1024
ROLE_NAMES = {
    "authorising_officer": "Authorising Officer",
    "key_contact": "Key Contact",
    "level1_user": "Level 1 User",
    "level2_user": "Level 2 User",
}
# The details a person shares with the Authorising Officer when they are the same individual.
_SHARED = ("first_name", "last_name", "designation", "phone", "email")


def _out(row: KeyPerson, proof_name: str | None) -> KeyPersonOut:
    return KeyPersonOut(
        id=row.id,
        role=row.role,  # type: ignore[arg-type]
        first_name=row.first_name,
        last_name=row.last_name,
        designation=row.designation,
        phone=row.phone,
        email=row.email,
        same_as_authorising_officer=row.same_as_authorising_officer,
        is_settled_or_british=row.is_settled_or_british,
        has_proof_of_id=row.proof_of_id_file_id is not None,
        proof_of_id_name=proof_name,
    )


def _snapshot(row: KeyPerson) -> dict[str, object]:
    return {
        "role": row.role,
        **{name: getattr(row, name) for name in _SHARED},
        "same_as_authorising_officer": row.same_as_authorising_officer,
        "is_settled_or_british": row.is_settled_or_british,
    }


async def _proof_name(access: Access, row: KeyPerson) -> str | None:
    if row.proof_of_id_file_id is None:
        return None
    return (
        await access.db.execute(
            select(File.original_name).where(File.id == row.proof_of_id_file_id)
        )
    ).scalar_one_or_none()


async def _person(access: Access, person_id: uuid.UUID) -> KeyPerson:
    row = (
        await access.db.execute(
            select(KeyPerson).where(KeyPerson.id == person_id, KeyPerson.archived_at.is_(None))
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def _officer(access: Access) -> KeyPerson | None:
    return (
        await access.db.execute(
            select(KeyPerson).where(
                KeyPerson.role == "authorising_officer", KeyPerson.archived_at.is_(None)
            )
        )
    ).scalar_one_or_none()


def _copy_from_officer(row: KeyPerson, officer: KeyPerson) -> None:
    for name in _SHARED:
        setattr(row, name, getattr(officer, name))


async def _must_have_officer(access: Access) -> KeyPerson:
    officer = await _officer(access)
    if officer is None:
        raise ConflictError(
            "Add the Authorising Officer first.", field="same_as_authorising_officer"
        )
    return officer


@router.get("/key-personnel", summary="The company's key personnel")
async def list_key_personnel(access: Reads) -> KeyPersonnel:
    order = {"authorising_officer": 0, "key_contact": 1, "level1_user": 2, "level2_user": 3}
    rows = (
        await access.db.execute(
            select(KeyPerson, File.original_name)
            .outerjoin(File, File.id == KeyPerson.proof_of_id_file_id)
            .where(KeyPerson.archived_at.is_(None))
            .order_by(KeyPerson.created_at)
        )
    ).all()
    rows = sorted(rows, key=lambda pair: order[pair[0].role])
    return KeyPersonnel(
        people=[_out(row, name) for row, name in rows],
        roles_filled=len({row.role for row, _ in rows}),
    )


@router.post("/key-personnel", status_code=201, summary="Add a key person")
async def add_key_person(body: KeyPersonIn, access: Writes) -> KeyPersonOut:
    if body.role != "level2_user":
        taken = (
            await access.db.execute(
                select(KeyPerson.id).where(
                    KeyPerson.role == body.role, KeyPerson.archived_at.is_(None)
                )
            )
        ).first()
        if taken:
            raise ConflictError(f"You already have a {ROLE_NAMES[body.role]}.", field="role")
    if not body.same_as_authorising_officer:
        for name in ("first_name", "last_name"):
            if getattr(body, name) is None:
                label = "first" if name == "first_name" else "last"
                raise AppError(
                    "VALIDATION_ERROR", f"Enter a {label} name.", status_code=422, field=name
                )
    row = KeyPerson(company_id=access.company_id, **body.model_dump())
    if body.same_as_authorising_officer:
        if body.role == "authorising_officer":
            raise AppError(
                "VALIDATION_ERROR",
                "The Authorising Officer cannot be the same as themselves.",
                status_code=422,
                field="same_as_authorising_officer",
            )
        _copy_from_officer(row, await _must_have_officer(access))
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "key_person.added", entity_type="key_person", entity_id=row.id, after=_snapshot(row)
    )
    await access.db.commit()
    return _out(row, None)


@router.patch("/key-personnel/{person_id}", summary="Change a key person's details")
async def update_key_person(
    person_id: uuid.UUID, body: KeyPersonPatch, access: Writes
) -> KeyPersonOut:
    row = await _person(access, person_id)
    before = _snapshot(row)
    changes = body.model_dump(exclude_unset=True)
    for required in ("first_name", "last_name"):
        if required in changes and changes[required] is None:
            raise AppError(
                "VALIDATION_ERROR", "That cannot be empty.", status_code=422, field=required
            )
    if changes.get("same_as_authorising_officer") is True:
        if row.role == "authorising_officer":
            raise AppError(
                "VALIDATION_ERROR",
                "The Authorising Officer cannot be the same as themselves.",
                status_code=422,
                field="same_as_authorising_officer",
            )
        _copy_from_officer(row, await _must_have_officer(access))
        changes = {
            name: value for name, value in changes.items() if name not in _SHARED
        }  # their own details are replaced by the officer's
    for name, value in changes.items():
        setattr(row, name, value)
    if row.same_as_authorising_officer and row.role != "authorising_officer":
        # Still the same person: details cannot drift away from the officer's.
        _copy_from_officer(row, await _must_have_officer(access))
    if row.role == "authorising_officer":
        await _follow_officer(access, row)
    after = _snapshot(row)
    if before != after:
        await access.audit(
            "key_person.updated",
            entity_type="key_person",
            entity_id=row.id,
            before=before,
            after=after,
        )
    await access.db.commit()
    return _out(row, await _proof_name(access, row))


async def _follow_officer(access: Access, officer: KeyPerson) -> None:
    """Everyone marked as the same person as the officer takes the officer's current details."""
    await access.db.execute(
        update(KeyPerson)
        .where(
            KeyPerson.same_as_authorising_officer.is_(True),
            KeyPerson.archived_at.is_(None),
            KeyPerson.id != officer.id,
        )
        .values({name: getattr(officer, name) for name in _SHARED})
    )


@router.delete("/key-personnel/{person_id}", status_code=204, summary="Remove a key person")
async def archive_key_person(person_id: uuid.UUID, access: Writes) -> None:
    row = await _person(access, person_id)
    row.archived_at = datetime.now(UTC)
    if row.role == "authorising_officer":
        # Without an officer nobody can be "the same as" them; they keep the details they had.
        await access.db.execute(
            update(KeyPerson)
            .where(KeyPerson.same_as_authorising_officer.is_(True))
            .values(same_as_authorising_officer=False)
        )
    await access.audit(
        "key_person.removed",
        entity_type="key_person",
        entity_id=row.id,
        summary=f"{ROLE_NAMES[row.role]}: {row.first_name} {row.last_name}",
    )
    await access.db.commit()


def _files(request: Request) -> FileService:
    service: FileService = request.app.state.files
    return service


@router.post(
    "/key-personnel/{person_id}/proof-of-id", status_code=204, summary="Upload proof of identity"
)
async def upload_proof(
    person_id: uuid.UUID, request: Request, file: UploadFile, access: Writes
) -> None:
    row = await _person(access, person_id)
    record = await _files(request).upload(
        access,
        file.file,
        filename=file.filename,
        owner_type="key_person",
        owner_id=row.id,
        category="proof_of_id",
        kinds=PROOF_KINDS,
        max_bytes=PROOF_MAX_BYTES,
        commit=False,
    )
    row.proof_of_id_file_id = record.id
    await access.audit(
        "key_person.proof_of_id_added",
        entity_type="key_person",
        entity_id=row.id,
        after={"file_id": record.id},
    )
    await access.db.commit()


@router.delete(
    "/key-personnel/{person_id}/proof-of-id", status_code=204, summary="Remove proof of identity"
)
async def remove_proof(person_id: uuid.UUID, access: Writes) -> None:
    row = await _person(access, person_id)
    if row.proof_of_id_file_id is None:
        return
    before = row.proof_of_id_file_id
    row.proof_of_id_file_id = None
    await access.audit(
        "key_person.proof_of_id_removed",
        entity_type="key_person",
        entity_id=row.id,
        before={"file_id": before},
    )
    await access.db.commit()


@router.get(
    "/key-personnel/{person_id}/proof-of-id", summary="A 60-second link to the identity document"
)
async def proof_link(person_id: uuid.UUID, request: Request, access: Writes) -> ProofLink:
    row = await _person(access, person_id)
    if row.proof_of_id_file_id is None:
        raise NotFoundError
    url, _ = await _files(request).download_url(access, row.proof_of_id_file_id)
    return ProofLink(url=url, expires_in=PRESIGN_SECONDS)
