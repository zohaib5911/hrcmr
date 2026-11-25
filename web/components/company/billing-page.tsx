"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { attempt, type Problem } from "@/lib/auth/request";
import type { components } from "@/lib/api/client";

import { FormSheet } from "./form-sheet";

type Billing = components["schemas"]["BillingOut"];
type Plan = "annual" | "ten_year";

/** Plan 8.16. Stripe charges the price configured for each plan; these words are the terms. */
const PLANS: Record<Plan, { name: string; price: string; about: string; choose: string }> = {
  annual: {
    name: "1 year plan",
    price: "£50 a year",
    about: "Renews every year, by card. Cancel any time to stop the next renewal.",
    choose: "Choose 1 year",
  },
  ten_year: {
    name: "10 year plan",
    price: "£240, paid once",
    about: "One payment that covers 10 years. It does not renew.",
    choose: "Choose 10 years",
  },
};

type Tone = "success" | "info" | "warning" | "neutral";

/** Stripe's subscription statuses, and the words a person sees for them. */
const STATUS: Record<string, { label: string; tone: Tone }> = {
  active: { label: "Active", tone: "success" },
  trialing: { label: "Trial", tone: "info" },
  past_due: { label: "Payment due", tone: "warning" },
  canceled: { label: "Cancelled", tone: "neutral" },
  refunded: { label: "Refunded", tone: "neutral" },
};

/** Stripe's statuses in which a paid plan is still the company's plan (as the API counts them). */
const LIVE = new Set<string>(["active", "trialing", "past_due"]);

const LONDON_DATE = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Europe/London",
});

function onDay(instant: string | null): string {
  return instant ? LONDON_DATE.format(new Date(instant)) : "";
}

/** Is ``moment`` before ``instant``? False when there is no instant. */
function before(instant: string | null, moment: Date): boolean {
  return instant !== null && moment.getTime() < new Date(instant).getTime();
}

function paidPlan(billing: Billing): Plan | null {
  return billing.plan === "annual" || billing.plan === "ten_year" ? billing.plan : null;
}

function isLive(billing: Billing, plan: Plan | null, moment: Date): boolean {
  if (plan === null || !LIVE.has(billing.subscription_status ?? "")) return false;
  return billing.ends_at === null || before(billing.ends_at, moment);
}

/**
 * The company's plan (plan 8.16). The page is decided on the server's clock (``now``), so what
 * is shown and what the API then allows agree. Only a Company Admin gets the plan at all.
 */
export function BillingPage({
  billing,
  checkout,
  now,
}: {
  billing: Billing | null;
  checkout: string | undefined;
  now: string;
}) {
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportNote, setExportNote] = useState<{
    tone: "success" | "warning" | "danger";
    title: string;
    text: string;
  } | null>(null);
  const [exportStepUp, setExportStepUp] = useState(false);
  const [pendingPlanAction, setPendingPlanAction] = useState<Plan | "cancel" | null>(null);
  const [exportPassword, setExportPassword] = useState("");
  const [exportStepUpProblem, setExportStepUpProblem] = useState<Problem | null>(null);
  const moment = new Date(now);

  if (!billing) {
    return (
      <>
        <PageHeader title="Billing" description="The company's plan and payment details." />
        <Alert tone="info" title="Only Company Admins can see this">
          Ask a Company Admin to look after the company&apos;s plan.
        </Alert>
      </>
    );
  }

  const plan = paidPlan(billing);
  const live = isLive(billing, plan, moment);
  const pastDue = billing.subscription_status === "past_due";
  const inGrace = pastDue && before(billing.payment_grace_ends_at, moment);
  const lapsed = pastDue && billing.payment_grace_ends_at !== null && !inGrace;
  const status: { label: string; tone: Tone } | undefined = billing.subscription_status
    ? STATUS[billing.subscription_status]
    : undefined;

  async function openPortal() {
    setBusy(true);
    const outcome = await attempt((api) => api.POST("/billing/portal-session"));
    if (outcome.ok) {
      window.location.assign(outcome.data.url);
      return;
    }
    setBusy(false);
    toast.show({ title: outcome.problem.message, tone: "danger" });
  }

  async function choose(next: Plan) {
    setBusy(true);
    const outcome = await attempt((api) =>
      api.POST("/billing/checkout-session", { body: { plan: next } }),
    );
    if (outcome.ok) {
      window.location.assign(outcome.data.url);
      return;
    }
    setBusy(false);
    if (outcome.problem.code === "STEP_UP_REQUIRED") {
      setPendingPlanAction(next);
      setExportStepUpProblem(null);
      setExportStepUp(true);
      return;
    }
    toast.show({ title: outcome.problem.message, tone: "danger" });
  }

  /** Asks for the export (C3.1.11). A recent sign-in is needed: the step-up sheet asks for it. */
  async function requestExport(): Promise<void> {
    setExportBusy(true);
    const outcome = await attempt((api) => api.POST("/companies/me/export"));
    setExportBusy(false);
    if (outcome.ok) {
      setExportNote({
        tone: "success",
        title: "Export requested",
        text: "We are preparing your export. We will e-mail you a link.",
      });
      return;
    }
    if (outcome.problem.code === "STEP_UP_REQUIRED") {
      setExportStepUp(true);
      return;
    }
    const inProgress = outcome.problem.code === "EXPORT_IN_PROGRESS";
    setExportNote({
      tone: inProgress ? "warning" : "danger",
      title: inProgress ? "An export is already being prepared" : "The export was not started",
      text: outcome.problem.message,
    });
  }

  async function confirmExportPassword(event: FormEvent): Promise<void> {
    event.preventDefault();
    setExportBusy(true);
    const confirmed = await attempt((api) =>
      api.POST("/auth/step-up", { body: { password: exportPassword } }),
    );
    setExportBusy(false);
    setExportPassword("");
    if (!confirmed.ok) {
      setExportStepUpProblem(confirmed.problem);
      return;
    }
    setExportStepUp(false);
    setExportStepUpProblem(null);
    const action = pendingPlanAction;
    setPendingPlanAction(null);
    if (action === "cancel") await cancel();
    else if (action !== null) await choose(action);
    else await requestExport();
  }

  async function cancel() {
    const outcome = await attempt((api) => api.POST("/billing/cancel"));
    if (!outcome.ok) {
      if (outcome.problem.code === "STEP_UP_REQUIRED") {
        setPendingPlanAction("cancel");
        setExportStepUpProblem(null);
        setExportStepUp(true);
        return;
      }
      toast.show({ title: outcome.problem.message, tone: "danger" });
      return;
    }
    toast.show({
      title: `Your plan ends on ${onDay(outcome.data.ends_at)}`,
      description: "It will not renew.",
      tone: "success",
    });
    router.refresh();
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Billing"
        description="The company's plan, cancelling renewal, and payment details."
      />

      {checkout === "success" ? (
        <Alert tone="success" title="Thank you">
          Your plan starts once Stripe confirms the payment. If it still says Free, refresh this
          page in a minute.
        </Alert>
      ) : null}
      {checkout === "cancelled" ? (
        <Alert tone="info" title="Checkout was cancelled">
          Nothing was charged.
        </Alert>
      ) : null}
      {!billing.payments_enabled ? (
        <Alert tone="info" title="Online payment is not available yet">
          Contact support to set up a plan.
        </Alert>
      ) : null}
      {inGrace ? (
        <Alert tone="warning" title="Your last payment did not go through">
          Full access continues until {onDay(billing.payment_grace_ends_at)}. Update your payment
          details before then.
        </Alert>
      ) : null}
      {lapsed ? (
        <Alert tone="danger" title="Full access has ended">
          Your last payment did not go through. Update your payment details to carry on.
        </Alert>
      ) : null}
      {before(billing.comp_until, moment) ? (
        <Alert tone="info" title="Complimentary access">
          Complimentary access until {onDay(billing.comp_until)}.
        </Alert>
      ) : null}

      <Card>
        <CardHeader title="Your plan" headingLevel={2} />
        <CardBody>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-3">
            <dt className="text-label-secondary">Plan</dt>
            <dd className="text-label">{plan ? PLANS[plan].name : "Free"}</dd>
            <dt className="text-label-secondary">Price</dt>
            <dd className="text-label">{plan ? PLANS[plan].price : "Free"}</dd>
            <dt className="text-label-secondary">Renewal</dt>
            <dd className="text-label">
              {!live || plan === null
                ? "Not applicable"
                : billing.cancel_at
                  ? `Ends ${onDay(billing.cancel_at)}. It will not renew.`
                  : plan === "annual"
                    ? `Renews ${onDay(billing.ends_at)}`
                    : `Runs until ${onDay(billing.ends_at)}. It does not renew.`}
            </dd>
            <dt className="text-label-secondary">Status</dt>
            <dd>
              <StatusChip tone={status?.tone ?? "neutral"}>
                {status?.label ?? (plan ? "Not active" : "Free")}
              </StatusChip>
            </dd>
            <dt className="text-label-secondary">Started</dt>
            <dd className="text-label">{billing.started_at ? onDay(billing.started_at) : "—"}</dd>
          </dl>
        </CardBody>
      </Card>

      {plan === null && billing.payments_enabled ? (
        <section aria-labelledby="choose-plan" className="flex flex-col gap-3">
          <h2 id="choose-plan" className="text-title-3 text-label">
            Choose a plan
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {(Object.keys(PLANS) as Plan[]).map((key) => (
              <Card key={key}>
                <CardHeader title={PLANS[key].name} description={PLANS[key].price} />
                <CardBody className="flex flex-col gap-4">
                  <p className="text-label-secondary">{PLANS[key].about}</p>
                  <Button variant="filled" disabled={busy} onClick={() => void choose(key)}>
                    {PLANS[key].choose}
                  </Button>
                </CardBody>
              </Card>
            ))}
          </div>
        </section>
      ) : null}

      {live && plan !== null ? (
        <Card>
          <CardHeader title="Cancel your plan" headingLevel={2} />
          <CardBody className="flex flex-col gap-4">
            {plan === "annual" && billing.cancel_at === null ? (
              <>
                <p className="text-label-secondary">
                  Cancelling stops the renewal. Your plan stays active until{" "}
                  {onDay(billing.ends_at)}, the end of the paid year. There is no refund.
                </p>
                <ConfirmDialog
                  trigger={<Button variant="gray">Cancel subscription</Button>}
                  title="Cancel your subscription?"
                  description={`Your plan stays active until ${onDay(billing.ends_at)}, then it ends and nothing more is charged.`}
                  confirmLabel="Cancel subscription"
                  destructive
                  onConfirm={cancel}
                />
              </>
            ) : plan === "annual" ? (
              <p className="text-label-secondary">
                Cancellation requested. Your plan ends on {onDay(billing.cancel_at)} and will not
                renew.
              </p>
            ) : (
              <p className="text-label-secondary">
                Your 10 year plan is a one-off purchase that does not renew, so there is nothing to
                cancel. It runs until {onDay(billing.ends_at)}.
              </p>
            )}
          </CardBody>
        </Card>
      ) : null}

      {live && plan !== null ? (
        <Card>
          <CardHeader
            title="Changing plan"
            headingLevel={2}
            description="Switching between 1 year and 10 years is done by support for now."
            actions={
              <Button asChild variant="gray">
                <a
                  href={`mailto:${billing.support_email}?subject=${encodeURIComponent("Plan change")}`}
                >
                  Contact support
                </a>
              </Button>
            }
          />
        </Card>
      ) : null}

      {billing.payments_enabled && billing.has_billing_account ? (
        <Card>
          <CardHeader
            title="Payment details and invoices"
            headingLevel={2}
            description="Update your card and see your invoices, in Stripe's secure page."
            actions={
              <Button variant="gray" disabled={busy} onClick={() => void openPortal()}>
                Payment details and invoices
              </Button>
            }
          />
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Export all your data"
          headingLevel={2}
          description="A zip of every record and document the company holds. We e-mail you a link, which works for 7 days."
          actions={
            <Button variant="gray" disabled={exportBusy} onClick={() => void requestExport()}>
              Request an export
            </Button>
          }
        />
        {exportNote ? (
          <CardBody>
            <Alert tone={exportNote.tone} title={exportNote.title}>
              {exportNote.text}
            </Alert>
          </CardBody>
        ) : null}
      </Card>

      {exportStepUp ? (
        <FormSheet
          open
          onOpenChange={(open) => {
            if (!open) {
              setExportStepUp(false);
              setPendingPlanAction(null);
              setExportStepUpProblem(null);
              setExportPassword("");
            }
          }}
          title="Confirm it is you"
          description={
            pendingPlanAction === null
              ? "Confirm your password to export the company's data."
              : "Confirm your password to change the company's plan."
          }
          onSubmit={(event) => void confirmExportPassword(event)}
          busy={exportBusy}
          problem={exportStepUpProblem}
          saveLabel="Continue"
        >
          <TextField
            label="Your password"
            type="password"
            autoComplete="current-password"
            value={exportPassword}
            onChange={(event) => setExportPassword(event.target.value)}
            required
          />
        </FormSheet>
      ) : null}
    </div>
  );
}
