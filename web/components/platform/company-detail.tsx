"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type Company = components["schemas"]["CompanyDetailOut"];
type Context = components["schemas"]["PlatformContextOut"];
type Action = "suspend" | "reactivate" | "extend-plan" | "mark-for-deletion" | "impersonate";
const LABELS: Record<Action, string> = {
  suspend: "Suspend",
  reactivate: "Reactivate",
  "extend-plan": "Extend plan",
  "mark-for-deletion": "Mark for deletion",
  impersonate: "Start support mode",
};

function ReasonAction({
  action,
  busy,
  run,
}: {
  action: Action;
  busy: boolean;
  run: (action: Action, reason: string, days: number, ticket: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [days, setDays] = useState("30");
  const [ticket, setTicket] = useState("");
  const valid =
    reason.trim().length >= 5 &&
    reason.trim().length <= 500 &&
    (action !== "extend-plan" ||
      (Number.isInteger(Number(days)) && Number(days) >= 1 && Number(days) <= 365)) &&
    (action !== "impersonate" || /^[A-Za-z0-9][A-Za-z0-9#._/-]{1,79}$/.test(ticket.trim()));
  return (
    <ConfirmDialog
      trigger={
        <Button variant="gray" disabled={busy}>
          {LABELS[action]}
        </Button>
      }
      title={`${LABELS[action]}?`}
      description={
        action === "impersonate"
          ? "Open the tenant app in read-only support mode for 30 minutes. The company can see this action in its audit trail."
          : "This change is recorded in the platform audit trail with your reason."
      }
      confirmLabel="Confirm"
      destructive={action === "mark-for-deletion" || action === "suspend"}
      confirmDisabled={!valid || busy}
      onConfirm={() => run(action, reason.trim(), Number(days), ticket.trim())}
    >
      <TextField
        label="Reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        minLength={5}
        maxLength={500}
        required
        hint="5 to 500 characters."
      />
      {action === "extend-plan" ? (
        <TextField
          label="Days"
          type="number"
          min={1}
          max={365}
          value={days}
          onChange={(e) => setDays(e.target.value)}
          required
        />
      ) : null}
      {action === "impersonate" ? (
        <TextField
          label="Ticket reference"
          value={ticket}
          onChange={(e) => setTicket(e.target.value)}
          maxLength={80}
          required
          hint="Letters, numbers, #, dot, underscore, slash or hyphen."
        />
      ) : null}
    </ConfirmDialog>
  );
}

export function CompanyDetail({
  company: initial,
  context,
  go = (path) => window.location.assign(path),
}: {
  company: Company | null;
  context: Context | null;
  go?: (path: string) => void;
}) {
  const [company, setCompany] = useState(initial);
  const [support, setSupport] = useState(context?.support ?? null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!support) return;
    const delay = Math.min(2147483647, Math.max(0, Date.parse(support.expires_at) - Date.now()));
    const timer = window.setTimeout(() => setNow(Date.now()), delay);
    return () => window.clearTimeout(timer);
  }, [support]);
  if (!company || !context)
    return (
      <Alert tone="danger" title="Company could not be loaded">
        Try reloading this page.
      </Alert>
    );
  const id = company.id;
  const live =
    support &&
    !Number.isNaN(Date.parse(support.expires_at)) &&
    Date.parse(support.expires_at) > now;

  async function act(action: Action, reason: string, days: number, ticket: string) {
    setBusy(true);
    setProblem(null);
    const params = { path: { company_id: id } };
    try {
      if (action === "impersonate") {
        const result = await attempt((c) =>
          c.POST("/platform/companies/{company_id}/impersonate", {
            params,
            body: { reason, ticket_ref: ticket },
          }),
        );
        if (!result.ok) {
          setProblem(result.problem);
          return;
        }
        setSupport(result.data);
        go(context!.web_origin + "/dashboard");
        return;
      }
      const result = await attempt((c) => {
        switch (action) {
          case "suspend":
            return c.POST("/platform/companies/{company_id}/suspend", { params, body: { reason } });
          case "reactivate":
            return c.POST("/platform/companies/{company_id}/reactivate", {
              params,
              body: { reason },
            });
          case "extend-plan":
            return c.POST("/platform/companies/{company_id}/extend-plan", {
              params,
              body: { reason, days },
            });
          case "mark-for-deletion":
            return c.POST("/platform/companies/{company_id}/mark-for-deletion", {
              params,
              body: { reason },
            });
        }
      });
      if (result.ok) setCompany(result.data);
      else setProblem(result.problem);
    } finally {
      setBusy(false);
    }
  }
  async function sessionAction(action: "writes" | "end") {
    if (!support) return;
    setBusy(true);
    setProblem(null);
    try {
      const params = { path: { support_id: support.id } };
      const result = await attempt((c) =>
        action === "writes"
          ? c.POST("/platform/impersonation/{support_id}/writes", {
              params,
              body: { enabled: true, confirm: true },
            })
          : c.POST("/platform/impersonation/{support_id}/end", { params }),
      );
      if (!result.ok) setProblem(result.problem);
      else setSupport(result.data.ended_at ? null : result.data);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="mx-auto grid max-w-6xl gap-6">
      <a href="/companies" className="text-accent-text">
        All companies
      </a>
      <PageHeader title={company.name} description={company.contact_email ?? company.slug} />
      {problem ? (
        <Alert tone="danger" title="That did not work">
          {problem.message}
        </Alert>
      ) : null}
      <Card>
        <CardHeader
          title="Company profile"
          actions={
            <StatusChip tone={company.status === "active" ? "success" : "warning"}>
              {company.status}
            </StatusChip>
          }
        />
        <CardBody className="grid gap-3 break-words pb-5">
          <p>
            Trading name: {company.trading_name ?? "—"} · Registered number:{" "}
            {company.registered_number ?? "—"}
          </p>
          <p>
            Plan: {company.plan} · Subscription: {company.subscription_status ?? "—"}
          </p>
          <p>
            Plan started:{" "}
            {company.subscription_started_at
              ? formatUk(company.subscription_started_at.slice(0, 10))
              : "—"}{" "}
            · Ends:{" "}
            {company.subscription_ends_at
              ? formatUk(company.subscription_ends_at.slice(0, 10))
              : "—"}
          </p>
          <p>Stripe customer: {company.stripe_customer_id ?? "—"}</p>
          <p>Stripe subscription: {company.stripe_subscription_id ?? "—"}</p>
          <div className="flex flex-wrap gap-2">
            {company.status === "active" ? (
              <ReasonAction action="suspend" busy={busy} run={act} />
            ) : null}
            {company.status === "suspended" ? (
              <ReasonAction action="reactivate" busy={busy} run={act} />
            ) : null}
            {["active", "suspended"].includes(company.status) ? (
              <>
                <ReasonAction action="extend-plan" busy={busy} run={act} />
                {context.owner ? (
                  <ReasonAction action="mark-for-deletion" busy={busy} run={act} />
                ) : null}
              </>
            ) : null}
            {company.status === "active" ? (
              <ReasonAction action="impersonate" busy={busy} run={act} />
            ) : null}
          </div>
        </CardBody>
      </Card>
      {live ? (
        <Card>
          <CardHeader title="Live support session" />
          <CardBody className="grid gap-3 pb-5">
            <p>
              {support.write_enabled ? "Changes are on." : "Read-only."} Expires{" "}
              {new Date(support.expires_at).toLocaleString("en-GB")}.
            </p>
            {context.owner ? (
              <div className="flex flex-wrap gap-2">
                {!support.write_enabled ? (
                  <ConfirmDialog
                    trigger={<Button disabled={busy}>Turn on writes</Button>}
                    title="Allow changes to this company?"
                    description="Support mode will be able to change company data. Type ENABLE as a second confirmation."
                    requireText="ENABLE"
                    confirmLabel="Turn on writes"
                    onConfirm={() => sessionAction("writes")}
                  />
                ) : null}
                <ConfirmDialog
                  trigger={
                    <Button variant="gray" disabled={busy}>
                      End
                    </Button>
                  }
                  title="End support mode?"
                  description="Access through this support session ends immediately."
                  confirmLabel="End session"
                  onConfirm={() => sessionAction("end")}
                />
              </div>
            ) : null}
          </CardBody>
        </Card>
      ) : null}
      <Card>
        <CardHeader title="People" />
        <CardBody className="grid gap-3 pb-5">
          {company.people.length ? (
            company.people.map((p) => (
              <p key={p.user_id} className="break-words">
                {p.first_name} {p.last_name} · {p.email} · {p.role} · {p.status}
                {p.locked ? " · Locked" : ""} · MFA {p.mfa_enabled ? "on" : "off"}
              </p>
            ))
          ) : (
            <p>No people.</p>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Recent platform actions" />
        <CardBody className="grid gap-3 pb-5">
          {company.events.length ? (
            company.events.map((e, i) => (
              <p key={i}>
                {formatUk(e.created_at.slice(0, 10))} · {e.action} · {e.reason ?? e.summary ?? "—"}
              </p>
            ))
          ) : (
            <p>No platform actions.</p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
