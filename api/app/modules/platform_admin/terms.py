"""Terms versions for the platform owners (T17.5, plan 8.18 Settings).

Publishing a version inserts it with ``published_at`` now. The newest one is the current terms
(auth/accounts.py ``current_terms``), and acceptance is checked for that version on every request
(rbac/deps.py, rbac/platform.py), so everyone accepts the new terms before using the product.
Publishing is owner-only; the handler checks it. A version is never edited or deleted here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.errors import AppError
from app.modules.audit.service import AuditContext, record
from app.modules.identity.models import TermsVersion
from app.modules.platform_admin.schemas import TermsVersionRow, TermsVersionsOut

if TYPE_CHECKING:
    from datetime import datetime

    from app.db.session import GlobalSession


def row(terms: TermsVersion, *, current: bool) -> TermsVersionRow:
    return TermsVersionRow(
        id=terms.id,
        version=terms.version,
        url=terms.url,
        published_at=terms.published_at,
        current=current,
    )


async def versions(db: GlobalSession) -> TermsVersionsOut:
    found = (
        (await db.execute(select(TermsVersion).order_by(TermsVersion.published_at.desc())))
        .scalars()
        .all()
    )
    items = [row(terms, current=index == 0) for index, terms in enumerate(found)]
    return TermsVersionsOut(items=items, total=len(items))


async def publish(
    db: GlobalSession,
    context: AuditContext,
    *,
    version: str,
    url: str,
    reason: str,
    now: datetime,
) -> TermsVersion:
    taken = (
        await db.execute(select(TermsVersion.id).where(TermsVersion.version == version))
    ).first()
    if taken is not None:
        raise AppError(
            "VERSION_EXISTS",
            "That terms version already exists. Choose a new version.",
            status_code=409,
        )
    terms = TermsVersion(version=version, url=url, published_at=now)
    db.add(terms)
    await db.flush()
    await record(
        db,
        context,
        "platform.terms_published",
        entity_type="terms_version",
        entity_id=terms.id,
        after={"version": version, "url": url},
        reason=reason,
        summary=f"Published terms version {version}",
    )
    return terms
