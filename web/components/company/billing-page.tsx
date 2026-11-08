"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { StatusChip } from "@/components/ui/status-chip";
import { useToast } from "@/components/ui/toast";
import { attempt } from "@/lib/auth/request";
import type { components } from "@/lib/api/client";

type Billing = components["schemas"]["BillingOut"];
type Plan = "annual" | "ten_year";

/** Plan 8.16. Stripe charges the price configured for each plan; these words are the terms. */
const PLANS: Record<Plan, { name: string; price: string; about: string; choose: string }> = {
  annual: {
    name: "1 year plan",
    price: "£50 a year",
    about: "Renews every year, by card.",
    choose: "Choose 1 year",
  },
  ten_year: {
    name: "10 year plan",
    price: "£240, paid once",
    about: "One payment that covers 10 years.",
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
  const refundable = live && before(billing.cooling_off_ends_at, moment);
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
    toast.show({ title: outcome.problem.message, tone: "danger" });
  }

  async function cancel() {
    const outcome = await attempt((api) => api.POST("/billing/cancel"));
    if (!outcome.ok) {
      toast.show({ title: outcome.problem.message, tone: "danger" });
      return;
    }
    toast.show({
      title: outcome.data.refunded
        ? "Your plan is cancelled and refunded"
        : `Your plan ends on ${onDay(outcome.data.ends_at)}`,
      description: outcome.data.refunded
        ? "The payment goes back to the card you paid with."
        : "It will not renew.",
      tone: "success",
    });
    router.refresh();
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Billing"
        description="The company's plan, the money-back guarantee, and payment details."
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
      {refundable ? (
        <Alert tone="info" title="14-day money-back guarantee">
          You can cancel until {onDay(billing.cooling_off_ends_at)} for a full refund.
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
                  <p className="text-label-secondary">
                    {PLANS[key].about} Cancel within 14 days for a full refund.
                  </p>
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
            {refundable ? (
              <>
                <p className="text-label-secondary">
                  Cancel now and get a full refund. Your plan ends straight away.
                </p>
                <ConfirmDialog
                  trigger={<Button variant="gray">Cancel and refund</Button>}
                  title="Cancel and refund?"
                  description="Your plan ends straight away and the full payment goes back to the card you paid with. To have a plan again, you will need to subscribe."
                  confirmLabel="Cancel and refund"
                  destructive
                  onConfirm={cancel}
                />
              </>
            ) : plan === "annual" && billing.cancel_at === null ? (
              <>
                <p className="text-label-secondary">
                  Your plan stays active until {onDay(billing.ends_at)}. It will not renew, and
                  there is no refund after 14 days.
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
                Your 10 year plan does not renew, so there is nothing to cancel. To end it early,
                contact support.
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
    </div>
  );
}
