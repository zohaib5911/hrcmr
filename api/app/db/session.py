"""Database sessions (plan.md 4.3).

``TenantSession`` is the only way application code reads or writes tenant data. For one company
it guarantees, in this order of defence:

1. **Row-Level Security**: every transaction starts with ``set_config('app.company_id', ...)``,
   so PostgreSQL itself hides and protects other companies' rows (see ``app/db/rls.py``).
   It is re-applied at the start of EVERY transaction, so a ``commit()`` in the middle of a
   request cannot silently drop the scope.
2. **Query scoping**: ORM selects, updates and deletes on any ``TenantMixin`` model get a
   ``company_id = <current>`` filter added automatically, so queries do not rely on RLS alone.
3. **Write stamping**: new rows get the session's ``company_id`` (and creator); a row that names a
   different company is refused before it reaches the database.

``GlobalSession`` has no company. Tenant tables are empty to it (RLS fails closed). It is for
data that is not tenant-owned (people and sign-in, public reference data).

Units of work are explicit: services call ``await session.commit()`` when a use case is complete
(together with its audit event). Leaving a session without committing rolls it back.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.core.errors import AppError
from app.db.base import AuditColumnsMixin, TenantMixin

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import SessionTransaction

COMPANY_KEY = "company_id"
USER_KEY = "user_id"
_SET_COMPANY = text("select set_config('app.company_id', :company_id, true)")
_SET_USER = text("select set_config('app.user_id', :user_id, true)")


class TenantViolationError(RuntimeError):
    """A write tried to cross a company boundary. This is a bug in the caller, never user input."""


class TenantSession(AsyncSession):
    def __init__(
        self, bind: AsyncEngine, *, company_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        super().__init__(
            bind, expire_on_commit=False, info={COMPANY_KEY: company_id, USER_KEY: user_id}
        )

    @property
    def company_id(self) -> uuid.UUID:
        company_id: uuid.UUID = self.info[COMPANY_KEY]
        return company_id


class GlobalSession(AsyncSession):
    """For the few things that happen before a company is known: signing in, accepting an invite.

    Pass ``user_id`` once the person is known, so they can read their own memberships."""

    def __init__(self, bind: AsyncEngine, *, user_id: uuid.UUID | None = None) -> None:
        super().__init__(bind, expire_on_commit=False, info={USER_KEY: user_id})


# --- Session events. They act only on sessions that carry a company id ----------------------------


@event.listens_for(Session, "after_begin")
def _scope_transaction(
    session: Session, transaction: SessionTransaction, connection: Connection
) -> None:
    company_id = session.info.get(COMPANY_KEY)
    if company_id is not None:
        connection.execute(_SET_COMPANY, {"company_id": str(company_id)})
    user_id = session.info.get(USER_KEY)
    if user_id is not None:
        connection.execute(_SET_USER, {"user_id": str(user_id)})


@event.listens_for(Session, "do_orm_execute")
def _scope_queries(state: ORMExecuteState) -> None:
    company_id = state.session.info.get(COMPANY_KEY)
    if company_id is None:
        return
    if state.is_select or state.is_update or state.is_delete:
        state.statement = state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda entity: entity.company_id == company_id,
                include_aliases=True,
                propagate_to_loaders=True,
            )
        )


@event.listens_for(Session, "before_flush")
def _stamp_and_guard(session: Session, flush_context: Any, instances: Any) -> None:
    company_id = session.info.get(COMPANY_KEY)
    if company_id is None:
        return
    user_id = session.info.get(USER_KEY)

    for obj in session.new:
        if isinstance(obj, TenantMixin):
            current = getattr(obj, "company_id", None)  # unset until stamped
            if current is None:
                obj.company_id = company_id
            elif current != company_id:
                raise TenantViolationError(
                    f"cannot create a {type(obj).__name__} for another company"
                )
        if isinstance(obj, AuditColumnsMixin) and user_id is not None:
            obj.created_by = obj.created_by or user_id
            obj.updated_by = user_id

    for obj in session.dirty:
        if not session.is_modified(obj):
            continue
        if isinstance(obj, TenantMixin) and obj.company_id != company_id:
            raise TenantViolationError(f"cannot change a {type(obj).__name__} to another company")
        if isinstance(obj, AuditColumnsMixin) and user_id is not None:
            obj.updated_by = user_id


# --- FastAPI dependencies ----------------------------------------------------------------------


def get_engine(request: Request) -> AsyncEngine:
    engine: AsyncEngine = request.app.state.engine
    return engine


async def global_session_dependency(request: Request) -> AsyncIterator[GlobalSession]:
    async with GlobalSession(get_engine(request)) as session:
        yield session


async def tenant_session_dependency(request: Request) -> AsyncIterator[TenantSession]:
    """A session for the signed-in user's company.

    The authentication layer (Phase 2) sets ``request.state.company_id`` and ``user_id``. Until it
    has, there is no company and the request is refused rather than run unscoped.
    """
    company_id = getattr(request.state, "company_id", None)
    if company_id is None:
        raise AppError("UNAUTHENTICATED", "Sign in to continue.", status_code=401)
    user_id = getattr(request.state, "user_id", None)
    # Normalise whatever the auth layer stored (a string is fine; garbage raises ValueError).
    async with TenantSession(
        get_engine(request),
        company_id=uuid.UUID(str(company_id)),
        user_id=uuid.UUID(str(user_id)) if user_id is not None else None,
    ) as session:
        yield session


TenantDb = Annotated[TenantSession, Depends(tenant_session_dependency)]
GlobalDb = Annotated[GlobalSession, Depends(global_session_dependency)]
