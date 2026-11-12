"use client";

import { useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type Row = components["schemas"]["SubscriptionRow"];

export const PAGE_SIZE = 50;
export const REASON_MIN = 5;

/** Platform subscriptions (list, filters, paging) and, for an owner, a full refund with a reason and a second confirmation. */
export function SubscriptionsAdmin({ isOwner }: { isOwner: boolean }) {
  const [plan, setPlan] = useState("");
  const [refunded, setRefunded] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [total, setTotal] = useState(0);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function fail(p: Problem) {
    if (p.code === "UNAUTHENTICATED") {
      window.location.replace(`/session?next=${encodeURIComponent("/subscriptions")}`);
      return;
    }
    setProblem(p);
  }

  useEffect(() => {
    let current = true;
    const query = {
      limit: PAGE_SIZE,
      offset,
      ...(plan ? { plan } : {}),
      ...(refunded ? { refunded: refunded === "yes" } : {}),
    };
    void attempt((c) => c.GET("/platform/subscriptions", { params: { query } })).then((result) => {
      if (!current) return;
      if (!result.ok) return fail(result.problem);
      setProblem(null);
      setRows(result.data.items);
      setTotal(result.data.total);
    });
    return () => {
      current = false;
    };
  }, [plan, refunded, offset]);

  async function refund(row: Row) {
    if (busy) return;
    setBusy(true);
    setProblem(null);
    setNotice(null);
    const result = await attempt((c) =>
      c.POST("/platform/refunds", {
        body: { subscription_id: row.id, reason: reason.trim(), confirm: true },
      }),
    );
    setBusy(false);
    if (!result.ok) return fail(result.problem);
    const updated = result.data.subscription;
    setRows((current) => (current ?? []).map((r) => (r.id === row.id ? updated : r)));
    setNotice(`${row.company_name} was refunded in full.`);
    setReason("");
  }

  const reasonOk = reason.trim().length >= REASON_MIN;

  return (
    <>
      <PageHeader
        title="Subscriptions"
        description="Annual and 10-year purchases. Only an owner can refund, and a refund is always in full."
      />
      <div className="mb-6 grid gap-3 sm:grid-cols-2">
        <Select
          label="Plan"
          value={plan}
          onChange={(e) => {
            setOffset(0);
            setPlan(e.target.value);
          }}
        >
          <option value="">All plans</option>
          <option value="annual">Annual</option>
          <option value="ten_year">10-year</option>
        </Select>
        <Select
          label="Refunded"
          value={refunded}
          onChange={(e) => {
            setOffset(0);
            setRefunded(e.target.value);
          }}
        >
          <option value="">Any</option>
          <option value="yes">Refunded</option>
          <option value="no">Not refunded</option>
        </Select>
      </div>
      {isOwner ? (
        <div className="mb-6">
          <TextField
            label="Refund reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            hint={`Required for a refund, at least ${REASON_MIN} characters. Saved in the audit log.`}
          />
        </div>
      ) : null}
      {problem ? (
        <Alert tone="danger" title="That did not work" className="mb-6">
          {problem.message}
        </Alert>
      ) : null}
      {notice ? (
        <Alert tone="success" title={notice} className="mb-6">
          The refund is in the audit log.
        </Alert>
      ) : null}
      {rows === null ? (
        <p className="text-callout text-label-secondary">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-callout text-label-secondary">No subscriptions match.</p>
      ) : (
        <ul className="grid gap-3" aria-label="Subscriptions">
          {rows.map((row) => (
            <li
              key={row.id}
              className="border-separator flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4"
            >
              <span className="text-callout min-w-0 break-words">
                {row.company_name}
                <span className="text-footnote text-label-secondary block">
                  {row.plan === "ten_year" ? "10-year" : "Annual"} · started{" "}
                  {formatUk(row.created_at.slice(0, 10))}
                  {row.current_period_end
                    ? ` · renews ${formatUk(row.current_period_end.slice(0, 10))}`
                    : ""}
                </span>
                {row.stripe_subscription_id ? (
                  <span className="text-footnote text-label-secondary block break-all">
                    Subscription {row.stripe_subscription_id}
                  </span>
                ) : null}
                {row.stripe_payment_intent_id ? (
                  <span className="text-footnote text-label-secondary block break-all">
                    Payment {row.stripe_payment_intent_id}
                  </span>
                ) : null}
              </span>
              <span className="flex items-center gap-3">
                <StatusChip tone={row.refunded_at ? "danger" : "success"}>
                  {row.refunded_at
                    ? `Refunded ${formatUk(row.refunded_at.slice(0, 10))}`
                    : row.status}
                </StatusChip>
                {isOwner && !row.refunded_at ? (
                  <ConfirmDialog
                    trigger={
                      <Button variant="gray" size="sm" disabled={busy || !reasonOk}>
                        Refund
                      </Button>
                    }
                    title="Refund this payment in full?"
                    description={`${row.company_name} will be refunded the latest payment in full. This cannot be undone.`}
                    confirmLabel="Refund in full"
                    destructive
                    onConfirm={() => refund(row)}
                  />
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-6 flex items-center justify-between gap-3">
        <Button
          variant="gray"
          size="sm"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
        >
          Previous
        </Button>
        <span className="text-footnote text-label-secondary">{total} in total</span>
        <Button
          variant="gray"
          size="sm"
          disabled={offset + PAGE_SIZE >= total}
          onClick={() => setOffset(offset + PAGE_SIZE)}
        >
          Next
        </Button>
      </div>
    </>
  );
}
