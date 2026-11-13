"use client";

import { PageHeader } from "@/components/app/page-header";
import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { KpiCard } from "@/components/ui/kpi-card";
import type { components } from "@/lib/api/client";

export type PlatformMetrics = components["schemas"]["MetricsOut"];

const pounds = (pence: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(pence / 100);

/** Where each admin screen lives on the admin host (public paths, never `/platform/...`). */
export const ADMIN_LINKS: readonly { href: string; label: string }[] = [
  { href: "/companies", label: "Companies" },
  { href: "/users", label: "Users" },
  { href: "/subscriptions", label: "Subscriptions and refunds" },
  { href: "/queues", label: "Deletion and export queues" },
  { href: "/contact", label: "Contact messages" },
  { href: "/jobs", label: "Jobs" },
  { href: "/register", label: "Sponsor register" },
  { href: "/audit", label: "Audit log" },
  { href: "/rules", label: "SOC rules" },
  { href: "/courses", label: "Courses" },
  { href: "/dossier-links", label: "Dossier links" },
  { href: "/settings", label: "Settings" },
];

/** The admin landing page: platform figures as cards, then a list of every admin screen. */
export function PlatformOverview({
  metrics,
  queueWaiting,
}: {
  metrics: PlatformMetrics | null;
  queueWaiting: number | null;
}) {
  return (
    <>
      <PageHeader title="Platform admin" />
      {metrics ? (
        <section aria-label="Platform figures" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <KpiCard label="Signups, 24 hours" value={metrics.signups_24h} />
          <KpiCard label="Signups, 7 days" value={metrics.signups_7d} />
          <KpiCard label="Active companies" value={metrics.companies_active} />
          <KpiCard
            label="Plans"
            value={Object.values(metrics.plans_active).reduce((a, b) => a + b, 0)}
            subLabel={Object.entries(metrics.plans_active)
              .map(([plan, n]) => `${plan}: ${n}`)
              .join(" · ")}
          />
          <KpiCard label="Paid and entitled" value={metrics.paid_entitled} />
          <KpiCard
            label="MRR estimate"
            value={metrics.mrr_pence}
            format={pounds}
            subLabel={`ARR estimate ${pounds(metrics.arr_pence)}`}
          />
          <KpiCard label="Churn, 30 days" value={metrics.churn_30d} />
          <KpiCard label="Refunds, 30 days" value={metrics.refunds_30d} />
          {queueWaiting !== null ? (
            <KpiCard label="Job queue depth" value={queueWaiting} subLabel="Jobs waiting" />
          ) : null}
        </section>
      ) : (
        <p role="alert" className="text-body text-label-secondary">
          We could not load the platform figures. Reload the page to try again.
        </p>
      )}
      <nav aria-label="Admin screens" className="mt-8">
        <GroupedList heading="Admin screens">
          {ADMIN_LINKS.map((l) => (
            <GroupedRow key={l.href} title={l.label} href={l.href} />
          ))}
        </GroupedList>
      </nav>
    </>
  );
}
