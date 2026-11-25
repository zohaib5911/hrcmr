"""T16.5: deleting a company account. A 6-digit e-mailed code schedules it for 7 days on, the other
Company Admins and support are told, any admin can withdraw it, and the hourly executor then purges
every tenant row and stored object of that company only, keeping a stub and the payment records."""

from __future__ import annotations

import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.crypto import DecryptionError, decrypt
from app.db.base import Base
from app.integrations.storage import StoredObject
from app.jobs.deletion import deletion_executor_hourly
from app.modules.email.outbox import PAYLOAD_CONTEXT
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig
from tests.db.test_exports import step_up

API = "/api/v1"
URL = f"{API}/companies/me/deletion-request"


class FakeStripe:
    def __init__(self, *, status: str = "active", fail: bool = False) -> None:
        self.status, self.fail = status, fail
        self.calls: list[tuple[str, str]] = []

    async def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        self.calls.append(("retrieve", subscription_id))
        if self.fail:
            raise RuntimeError("stripe is down")
        return {"id": subscription_id, "status": self.status}

    async def cancel_now(self, subscription_id: str) -> dict[str, Any]:
        self.calls.append(("cancel", subscription_id))
        self.status = "canceled"
        return {"id": subscription_id, "status": "canceled"}


async def _rows(rig: dict[str, Any], sql: str, **params: Any) -> list[Any]:
    async with rig["owner"].connect() as c:
        return list((await c.execute(text(sql), params)).all())


async def _mail(rig: dict[str, Any], template: str) -> list[tuple[str, dict[str, Any]]]:
    rows = await _rows(
        rig,
        "select to_address, payload from email_outbox where template = :t order by created_at",
        t=template,
    )
    out = []
    for to, payload in rows:
        if payload is None:
            continue
        try:  # each test seals with its own key; mail left by other tests is not readable
            out.append((to, json.loads(decrypt(payload, context=PAYLOAD_CONTEXT))))
        except DecryptionError:
            continue
    return out


@pytest.fixture(autouse=True)
def _sent(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> list[tuple[str, str, dict[str, str]]]:
    """The code goes out through the app mailer (not the outbox): keep what it is asked to send."""
    sent: list[tuple[str, str, dict[str, str]]] = []

    async def record(*, to: str, template: str, data: dict[str, str]) -> None:
        sent.append((to, template, data))

    monkeypatch.setattr(rig["app"].state.auth.mailer, "send_template", record)
    rig["sent"] = sent
    return sent


async def _code_for(rig: dict[str, Any], address_start: str) -> str:
    sent = [d for to, t, d in rig["sent"] if t == "deletion_code" and to.startswith(address_start)]
    return str(sent[-1]["code"])


async def _admin_email(rig: dict[str, Any], company: uuid.UUID) -> list[str]:
    rows = await _rows(
        rig,
        "select u.email from users u join memberships m on m.user_id = u.id "
        "where m.company_id = :c and m.role = 'company_admin' order by m.created_at",
        c=company,
    )
    return [r[0] for r in rows]


async def _schedule(rig: dict[str, Any], admin: Any) -> dict[str, Any]:
    await step_up(rig, admin)
    started = await admin.post(URL, json={})
    assert started.status_code == 202, started.text
    (email,) = await _admin_email(rig, rig["a"])
    confirmed = await admin.post(f"{URL}/confirm", json={"code": await _code_for(rig, email)})
    assert confirmed.status_code == 200, confirmed.text
    return dict(confirmed.json())


async def test_a_code_schedules_the_deletion_and_any_admin_can_withdraw_it(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    hr = await rig["person"]("hr_admin", rig["a"])
    assert (await hr.post(URL, json={})).status_code == 403
    assert (await admin.get(URL)).json() is None
    await step_up(rig, admin)

    started = await admin.post(URL, json={})
    assert started.status_code == 202, started.text
    assert started.json()["status"] == "awaiting_code"
    again = await admin.post(URL, json={})
    assert (again.status_code, again.json()["error"]["code"]) == (429, "CODE_RECENTLY_SENT")

    # The code goes to the requester only, and is stored as a keyed hash, never as itself.
    (address,) = await _admin_email(rig, rig["a"])
    code = await _code_for(rig, address)
    assert len(code.replace(" ", "")) == 6
    stored = await _rows(
        rig, "select code_hash from deletion_requests where company_id = :c", c=rig["a"]
    )
    assert code.replace(" ", "") not in stored[0][0]

    # A second admin joins before the code is entered: they are the one told.
    other = await rig["person"]("company_admin", rig["a"])
    wrong = await admin.post(
        f"{URL}/confirm", json={"code": "000000" if code != "000 000" else "111111"}
    )
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (400, "INVALID_CODE")
    assert (await other.post(f"{URL}/confirm", json={"code": code})).status_code == 404

    confirmed = await admin.post(f"{URL}/confirm", json={"code": code})
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["status"] == "scheduled"
    when = datetime.fromisoformat(body["scheduled_for"])
    assert timedelta(days=6, hours=23) < when - datetime.now(UTC) <= timedelta(days=7)

    others = await _admin_email(rig, rig["a"])
    told = await _mail(rig, "deletion_scheduled")
    assert [to for to, _ in told] == [others[1]]
    support = await _mail(rig, "deletion_scheduled_support")
    assert [data["company_id"] for _, data in support] == [str(rig["a"])]
    notes = await _rows(
        rig,
        "select kind from notifications where company_id = :c and kind like 'account.%'",
        c=rig["a"],
    )
    assert notes == [("account.deletion_scheduled",)]
    seen = (await other.get(URL)).json()
    assert (seen["status"], seen["requested_by_me"]) == ("scheduled", False)
    blocked = await admin.post(URL, json={})
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (409, "DELETION_SCHEDULED")

    # The other admin withdraws it; the requester hears; nothing is deleted later.
    assert (await other.delete(URL)).status_code == 204
    assert (await admin.get(URL)).json() is None
    assert [to for to, _ in await _mail(rig, "deletion_withdrawn")] == [others[0]]
    actions = {
        r[0]
        for r in await _rows(
            rig, "select action from audit_events where company_id = :c", c=rig["a"]
        )
    }
    assert {
        "company.deletion_requested",
        "company.deletion_scheduled",
        "company.deletion_withdrawn",
    } <= actions
    later = datetime.now(UTC) + timedelta(days=30)
    ctx = {"owner_engine": rig["owner"], "stripe": FakeStripe(), "now": later}
    assert await deletion_executor_hourly(ctx) == 0
    status = await _rows(rig, "select status from companies where id = :c", c=rig["a"])
    assert status == [("active",)]


async def test_five_wrong_codes_end_the_code(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await step_up(rig, admin)
    assert (await admin.post(URL, json={})).status_code == 202
    (address,) = await _admin_email(rig, rig["a"])
    code = (await _code_for(rig, address)).replace(" ", "")
    bad = f"{(int(code) + 1) % 10**6:06d}"
    codes = [(await admin.post(f"{URL}/confirm", json={"code": bad})).json() for _ in range(5)]
    assert [c["error"]["code"] for c in codes] == ["INVALID_CODE"] * 4 + ["CODE_EXPIRED"]
    late = await admin.post(f"{URL}/confirm", json={"code": code})
    assert (late.status_code, late.json()["error"]["code"]) == (400, "CODE_EXPIRED")


async def _seed(rig: dict[str, Any], company: uuid.UUID, tag: str) -> str:
    """A spread of records, including history tables that refuse DELETE, and a stored file."""
    storage = rig["app"].state.files.storage
    key = f"company/{company}/{uuid.uuid4().hex}"
    body = f"file of {tag}".encode()
    await storage.put(key, io.BytesIO(body), content_type="text/plain", size=len(body))
    async with rig["owner"].begin() as c:
        await c.execute(
            text("insert into departments (company_id, name) values (:c, :n)"),
            {"c": company, "n": f"Dept {tag}"},
        )
        employee = (
            await c.execute(
                text(
                    "insert into employees (company_id, employee_number, first_name, last_name, "
                    "email, hire_date) values (:c, 'E1', 'Amira', :t, "
                    "'a@example.com', '2025-01-06') returning id"
                ),
                {"c": company, "t": tag},
            )
        ).scalar_one()
        leave_type = (
            await c.execute(
                text(
                    "insert into leave_types (company_id, name) values (:c, 'Annual') returning id"
                ),
                {"c": company},
            )
        ).scalar_one()
        await c.execute(
            text(
                "insert into leave_ledger (company_id, employee_id, leave_type_id, "
                "leave_year_start, entry_type, days, reason) values "
                "(:c, :e, :l, '2026-01-01', 'grant', 25, 'Yearly')"
            ),
            {"c": company, "e": employee, "l": leave_type},
        )
        await c.execute(
            text(
                "insert into files (company_id, storage_key, original_name, mime, size, sha256, "
                "scan_status, scanned_at, category) values (:c, :k, 'a.txt', 'text/plain', :s, "
                "repeat('0', 64), 'clean', now(), 'other')"
            ),
            {"c": company, "k": key, "s": len(body)},
        )
        await c.execute(
            text(
                "insert into audit_events (company_id, actor_type, action, summary) "
                "values (:c, 'system', 'seed', :t)"
            ),
            {"c": company, "t": f"about {tag}"},
        )
    return key


async def _counts(rig: dict[str, Any], company: uuid.UUID) -> dict[str, int]:
    out: dict[str, int] = {}
    async with rig["owner"].connect() as c:
        for table in Base.metadata.sorted_tables:
            if "company_id" in table.c:
                n = (
                    await c.execute(
                        text(f"select count(*) from {table.name} where company_id = :c"),  # noqa: S608
                        {"c": company},
                    )
                ).scalar_one()
                if n:
                    out[table.name] = n
    return out


async def test_the_executor_deletes_only_the_due_company_and_keeps_a_stub(
    rig: dict[str, Any],
) -> None:
    storage = rig["app"].state.files.storage
    key_a = await _seed(rig, rig["a"], "A")
    key_b = await _seed(rig, rig["b"], "B")
    admin = await rig["person"]("company_admin", rig["a"])
    await rig["person"]("company_admin", rig["b"])
    await rig["person"]("hr_admin", rig["a"])  # also a member of company b, below
    (shared_id,) = (
        r[0]
        for r in await _rows(
            rig,
            "select user_id from memberships where company_id = :c and role = 'hr_admin'",
            c=rig["a"],
        )
    )
    (admin_id,) = (
        r[0]
        for r in await _rows(
            rig,
            "select user_id from memberships where company_id = :c and role = 'company_admin'",
            c=rig["a"],
        )
    )
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into memberships (user_id, company_id, role, status) "
                "values (:u, :c, 'employee', 'active')"
            ),
            {"u": shared_id, "c": rig["b"]},
        )
        await c.execute(
            text(
                "update companies set plan = 'annual', subscription_status = 'active', "
                "stripe_subscription_id = :s, stripe_customer_id = :k where id = :c"
            ),
            {
                "s": f"sub_{uuid.uuid4().hex[:12]}",
                "k": f"cus_{uuid.uuid4().hex[:12]}",
                "c": rig["a"],
            },
        )
        await c.execute(
            text(
                "insert into subscriptions (company_id, plan, status, stripe_subscription_id) "
                "select id, 'annual', 'active', stripe_subscription_id from companies where id = :c"
            ),
            {"c": rig["a"]},
        )
    before_b = await _counts(rig, rig["b"])
    request = await _schedule(rig, admin)
    assert "leave_ledger" in await _counts(rig, rig["a"])

    # Not due yet: nothing happens. Stripe down when due: still nothing, tried again next hour.
    stripe = FakeStripe()
    ctx: dict[str, Any] = {"owner_engine": rig["owner"], "storage": storage, "stripe": stripe}
    assert await deletion_executor_hourly({**ctx, "now": datetime.now(UTC)}) == 0
    due = datetime.now(UTC) + timedelta(days=7, minutes=1)
    assert await deletion_executor_hourly({**ctx, "stripe": FakeStripe(fail=True), "now": due}) == 0
    assert (await _rows(rig, "select status from companies where id = :c", c=rig["a"])) == [
        ("pending_deletion",)
    ]

    assert await deletion_executor_hourly({**ctx, "now": due}) == 0  # waits for its backoff
    later = due + timedelta(hours=1)
    assert await deletion_executor_hourly({**ctx, "now": later}) == 1
    assert [call for call, _ in stripe.calls] == ["retrieve", "cancel"]

    # Company a: only the kept records and one audit stub remain.
    left = await _counts(rig, rig["a"])
    assert left == {"audit_events": 1, "deletion_requests": 1, "subscriptions": 1}
    audit = await _rows(
        rig,
        "select action, actor_type, summary from audit_events where company_id = :c",
        c=rig["a"],
    )
    assert audit == [("company.deleted", "system", None)]
    company = (
        await _rows(
            rig,
            "select name, status, contact_email, slug, subscription_status, stripe_customer_id "
            "from companies where id = :c",
            c=rig["a"],
        )
    )[0]
    assert company[:4] == ("Deleted company", "deleted", None, f"deleted-{rig['a']}")
    assert company[4] == "canceled"
    assert company[5] is not None  # the payment records still point at the customer
    done = await _rows(
        rig,
        "select completed_at, requested_by, code_hash from deletion_requests where id = :i",
        i=uuid.UUID(request["id"]),
    )
    assert done[0][0] is not None
    assert done[0][1:] == (None, None)  # the requester's user account went too

    # People: the admin who only belonged to a is gone; the shared person stays for b.
    users = {
        r[0]
        for r in await _rows(
            rig, "select id from users where id in (:a, :s)", a=admin_id, s=shared_id
        )
    }
    assert users == {shared_id}
    final = await _mail(rig, "account_deleted")
    assert len(final) == 1
    assert final[0][0].startswith("company_admin-")

    # Stored objects: a's are gone, b's are untouched; b's rows are all still there.
    assert not await storage.exists(key_a)
    assert await storage.exists(key_b)
    assert await storage.list_objects(f"company/{rig['a']}/") == []
    after_b = await _counts(rig, rig["b"])
    assert after_b == before_b

    # Running again finds nothing to do.
    assert await deletion_executor_hourly({**ctx, "now": due + timedelta(hours=1)}) == 0


async def _as_owner(rig: dict[str, Any], sql: str, *, purge_for: uuid.UUID | None) -> None:
    async with rig["owner"].begin() as c:
        if purge_for is not None:
            await c.execute(
                text("select set_config('app.purge_company_id', :c, true)"), {"c": str(purge_for)}
            )
        await c.execute(text(sql), {"c": rig["a"]})


async def test_storage_failure_leaves_deletion_frozen_and_retryable(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    scheduled = await _schedule(rig, admin)
    now = datetime.fromisoformat(scheduled["scheduled_for"]) + timedelta(minutes=1)

    storage = rig["app"].state.files.storage
    first = await _seed(rig, rig["a"], "partial")
    prefix = f"company/{rig['a']}/"
    second = prefix + "zz-pending"
    await storage.put(second, io.BytesIO(b"file"), content_type="text/plain", size=4)

    class PartialFailure:
        async def list_objects(self, prefix: str) -> list[StoredObject]:
            objects: list[StoredObject] = await storage.list_objects(prefix)
            return objects

        async def delete(self, key: str) -> None:
            if key == second:
                raise RuntimeError("temporary storage outage")
            await storage.delete(key)

    ctx = {
        "owner_engine": rig["owner"],
        "stripe": FakeStripe(),
        "storage": PartialFailure(),
        "now": now,
    }
    assert await _queue_status(rig) == "scheduled"  # ISS-22: nothing irreversible yet
    assert await deletion_executor_hourly(ctx) == 0
    assert await _rows(rig, "select status from companies where id=:c", c=rig["a"]) == [
        ("pending_deletion",)
    ]
    assert await _queue_status(rig) == "in_progress"
    assert await deletion_executor_hourly(ctx) == 0  # a retry that fails again
    assert await _queue_status(rig) == "in_progress"
    assert await _queue_status(rig, "scheduled") is None  # not under the scheduled filter
    assert (await admin.delete(URL)).status_code == 403
    assert (await admin.get(URL)).status_code == 403
    assert {obj.key for obj in await storage.list_objects(prefix)} == {second}
    assert await _rows(rig, "select storage_key from files where storage_key=:k", k=first) == [
        (first,)
    ]
    ctx["storage"] = storage
    ctx["now"] = now + timedelta(hours=1)  # after the failed purge's backoff (ISS-30)
    assert await deletion_executor_hourly(ctx) == 1
    assert await storage.list_objects(prefix) == []
    assert await _queue_status(rig) == "completed"


async def _queue_status(rig: dict[str, Any], status: str | None = None) -> str | None:
    """What the platform deletion queue shows for company A (optionally under a filter)."""
    from app.db.session import GlobalSession
    from app.modules.platform_admin import queues

    async with GlobalSession(rig["owner"]) as db:
        page = await queues.deletion_requests(db, status=status, limit=100, offset=0)
    return next((row.status for row in page.items if row.company_id == rig["a"]), None)


async def test_only_the_owner_role_in_a_purge_may_delete_history_rows(rig: dict[str, Any]) -> None:
    await _seed(rig, rig["a"], "A")
    ledger = "delete from leave_ledger where company_id = :c"
    # The owner without the purge setting: refused.
    with pytest.raises(DBAPIError, match="append-only"):
        await _as_owner(rig, ledger, purge_for=None)
    # The setting names another company: still refused for this one.
    with pytest.raises(DBAPIError, match="append-only"):
        await _as_owner(rig, "delete from audit_events where company_id = :c", purge_for=rig["b"])
    # Updates stay refused even inside a purge.
    with pytest.raises(DBAPIError, match="append-only"):
        await _as_owner(
            rig, "update leave_ledger set reason = 'x' where company_id = :c", purge_for=rig["a"]
        )
    # The API's own role cannot use the setting: it has no DELETE right on the table at all.
    async with rig["app"].state.engine.connect() as c:
        with pytest.raises(DBAPIError, match="permission denied"):
            await c.execute(text(ledger), {"c": rig["a"]})


async def test_starting_deletion_without_export_requires_recent_step_up(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    refused = await admin.post(URL, json={"export_requested": False})
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "STEP_UP_REQUIRED"
    assert (
        await _rows(rig, "select id from deletion_requests where company_id = :c", c=rig["a"]) == []
    )
    assert rig["sent"] == []
    await step_up(rig, admin)
    started = await admin.post(URL, json={"export_requested": False})
    assert started.status_code == 202, started.text
    assert started.json()["status"] == "awaiting_code"
    assert len(rig["sent"]) == 1


async def test_persistent_failures_ahead_do_not_starve_a_healthy_purge(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """ISS-30: 20 requests that keep failing, due first, and one healthy request behind them."""
    from app.jobs import deletion as job

    healthy = rig["a"]
    admin = await rig["person"]("company_admin", healthy)
    scheduled = await _schedule(rig, admin)
    now = datetime.fromisoformat(scheduled["scheduled_for"]) + timedelta(minutes=1)
    failing = [uuid.uuid4() for _ in range(job.BATCH)]
    async with rig["owner"].begin() as c:
        for i, request in enumerate(failing):
            company = uuid.uuid4()
            await c.execute(
                text(
                    "insert into companies (id, name, slug, plan, subscription_status) "
                    "values (:c, :n, :n, 'annual', 'active')"
                ),
                {"c": company, "n": f"stuck-{company.hex[:12]}"},
            )
            await c.execute(
                text(
                    "insert into deletion_requests (id, company_id, confirmed_at, scheduled_for) "
                    "values (:i, :c, :t, :s)"
                ),
                # Due earlier than the healthy one, so they come first in the batch.
                {"i": request, "c": company, "t": now, "s": now - timedelta(days=1, minutes=i)},
            )

    real = job.purge_company

    async def purge(
        owner: Any, storage: Any, stripe: Any, company: Any, request: Any, **kw: Any
    ) -> int:
        if request in failing:
            raise RuntimeError("persistent failure")
        return await real(owner, storage, stripe, company, request, **kw)

    monkeypatch.setattr(job, "purge_company", purge)
    ctx = {
        "owner_engine": rig["owner"],
        "stripe": FakeStripe(),
        "storage": rig["app"].state.files.storage,
    }
    first = await job.deletion_executor_hourly({**ctx, "now": now})
    second = await job.deletion_executor_hourly({**ctx, "now": now + timedelta(minutes=5)})
    assert first + second == 1  # the healthy company was reached
    assert await _rows(rig, "select status from companies where id=:c", c=healthy) == [("deleted",)]
    retry = await _rows(
        rig,
        "select count(*) from deletion_requests where id = any(:ids) and completed_at is null "
        "and failures >= 1 and retry_at is not null",
        ids=failing,
    )
    assert retry == [(job.BATCH,)]  # the failed purges remain, waiting to be retried
