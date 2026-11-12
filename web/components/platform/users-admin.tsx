"use client";

import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type UserRow = components["schemas"]["UserRow"];

export const SEARCH_MIN = 3;

/** Platform users: search by e-mail, then lock or unlock an account (reason optional). */
export function UsersAdmin() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<UserRow[] | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const term = q.trim();
  const tooShort = term.length < SEARCH_MIN;

  function fail(p: Problem) {
    // An expired platform session: start again and come back here. FORBIDDEN is shown as a message.
    if (p.code === "UNAUTHENTICATED") {
      window.location.replace(`/session?next=${encodeURIComponent("/users")}`);
      return;
    }
    setProblem(p);
  }

  async function search(event?: FormEvent) {
    event?.preventDefault();
    if (tooShort) return;
    setBusy(true);
    setProblem(null);
    setNotice(null);
    const result = await attempt((c) =>
      c.GET("/platform/users", { params: { query: { q: term } } }),
    );
    setBusy(false);
    if (!result.ok) return fail(result.problem);
    setRows(result.data.items);
  }

  async function act(user: UserRow, action: "lock" | "unlock") {
    setBusy(true);
    setProblem(null);
    setNotice(null);
    const body = reason.trim() ? { reason: reason.trim() } : null;
    const params = { params: { path: { user_id: user.id } }, body };
    const result = await attempt((c) =>
      action === "lock"
        ? c.POST("/platform/users/{user_id}/lock", params)
        : c.POST("/platform/users/{user_id}/unlock", params),
    );
    setBusy(false);
    if (!result.ok) return fail(result.problem);
    setRows((current) => (current ?? []).map((r) => (r.id === user.id ? result.data : r)));
    setNotice(action === "lock" ? `${user.email} is locked.` : `${user.email} is unlocked.`);
  }

  return (
    <>
      <PageHeader
        title="Users"
        description="Search by e-mail address. Locking signs the person out and stops them signing in."
      />
      <form onSubmit={search} className="mb-6 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-start">
        <TextField
          label="E-mail address"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          hint={`Type at least ${SEARCH_MIN} characters.`}
        />
        <Button type="submit" disabled={busy || tooShort}>
          Search
        </Button>
      </form>
      <div className="mb-6">
        <TextField
          label="Reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          hint="Saved in the audit log with a lock or unlock."
        />
      </div>
      {problem ? (
        <Alert tone="danger" title="That did not work" className="mb-6">
          {problem.message}
        </Alert>
      ) : null}
      {notice ? (
        <Alert tone="success" title={notice} className="mb-6">
          The change is in the audit log.
        </Alert>
      ) : null}
      {rows === null ? (
        <p className="text-callout text-label-secondary">Search to see users.</p>
      ) : rows.length === 0 ? (
        <p className="text-callout text-label-secondary">No user matches that e-mail address.</p>
      ) : (
        <ul className="grid gap-3" aria-label="Users found">
          {rows.map((user) => (
            <li
              key={user.id}
              className="border-separator flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4"
            >
              <span className="text-callout min-w-0 break-words">
                {user.first_name} {user.last_name}
                <span className="text-footnote text-label-secondary block break-all">
                  {user.email}
                </span>
                <span className="text-footnote text-label-secondary block">
                  {user.last_login_at
                    ? `Last signed in ${formatUk(user.last_login_at.slice(0, 10))}`
                    : "Never signed in"}
                  {user.companies.length
                    ? ` · ${user.companies.map((c) => c.name).join(", ")}`
                    : ""}
                </span>
              </span>
              <span className="flex items-center gap-3">
                <StatusChip tone={user.locked ? "danger" : "success"}>
                  {user.locked ? "Locked" : "Active"}
                </StatusChip>
                {user.locked ? (
                  <ConfirmDialog
                    trigger={
                      <Button variant="gray" size="sm" disabled={busy}>
                        Unlock
                      </Button>
                    }
                    title="Unlock this user?"
                    description={`${user.email} will be able to sign in again.`}
                    confirmLabel="Unlock"
                    onConfirm={() => act(user, "unlock")}
                  />
                ) : (
                  <ConfirmDialog
                    trigger={
                      <Button variant="gray" size="sm" disabled={busy}>
                        Lock
                      </Button>
                    }
                    title="Lock this user?"
                    description={`${user.email} will be signed out and cannot sign in until you unlock them.`}
                    confirmLabel="Lock"
                    destructive
                    onConfirm={() => act(user, "lock")}
                  />
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
